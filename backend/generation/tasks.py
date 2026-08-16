from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from monitoring.models import IncidentSeverity, OperationalIncident

from .echecs import marquer_echec
from .models import GenerationJob, JobStatus, QAStatus
from .runner import run_generation_job

# Un job RUNNING depuis plus de 2h est considere bloque (crash worker, timeout reseau).
_STUCK_JOB_TIMEOUT_HOURS = 2


@shared_task(name="generation.reset_stuck_generation_jobs")  # type: ignore[untyped-decorator]
def reset_stuck_generation_jobs() -> int:
    """Risque 6 — detecte et reset les jobs bloques en RUNNING depuis trop longtemps.

    Cree un incident HIGH pour chaque job concerne afin que l'admin puisse
    relancer manuellement depuis le dashboard.
    """
    cutoff = timezone.now() - timedelta(hours=_STUCK_JOB_TIMEOUT_HOURS)
    stuck_jobs = list(
        GenerationJob.objects.filter(status=JobStatus.RUNNING, updated_at__lt=cutoff)
        .select_related("order")
    )
    for job in stuck_jobs:
        GenerationJob.objects.filter(pk=job.pk).update(
            status=JobStatus.FAILED,
            error_message=(
                f"Job bloque detecte par le gardien automatique "
                f"(aucune activite depuis >{_STUCK_JOB_TIMEOUT_HOURS}h)."
            ),
        )
        OperationalIncident.objects.create(
            title=f"Job IA bloque — reset automatique (job {job.id})",
            severity=IncidentSeverity.HIGH,
            job=job,
            order=job.order,
            details={
                "stuck_since": str(job.updated_at),
                "deliverable_type": job.deliverable_type,
                "hint": "Relancer manuellement depuis le dashboard admin.",
            },
        )
    return len(stuck_jobs)


def _controler_les_demandes_du_client(job: GenerationJob) -> None:
    """Relit le brief du client et dit ce qui n'a pas reçu de réponse.

    Ne lève jamais : une panne de ce contrôle ne rend pas l'étude fausse, elle
    rend sa couverture inconnue. Faire mourir un dossier de vingt-trois
    chapitres sur ce point coûterait bien plus que ce qu'il rapporte.

    Mais l'incident, lui, se voit — et il porte chaque question insuffisamment
    traitée avec ce qui lui manque, en toutes lettres. C'est l'information que
    la cliente relira avant de remettre l'étude à SON client.
    """
    from integrations.claude import get_claude_client  # noqa: PLC0415

    from .couverture import controler_la_couverture  # noqa: PLC0415

    try:
        soumission = job.order.intake_submission
        variables = soumission.normalized_variables
        texte = "\n\n".join(
            c.content for c in job.chapters.order_by("chapter_number") if c.content
        )
        rapport = controler_la_couverture(
            client=get_claude_client(), variables=variables, document=texte
        )
    except Exception:  # noqa: BLE001 — un contrôle ne fait pas échouer l'étude
        import logging  # noqa: PLC0415
        logging.getLogger(__name__).exception(
            "Contrôle de couverture impossible pour le job %s", job.id
        )
        return

    if not rapport.passe_executee:
        OperationalIncident.objects.create(
            title=f"Couverture des demandes NON contrôlée (job {job.id})",
            severity=IncidentSeverity.MEDIUM,
            job=job,
            order=job.order,
            details=rapport.as_details(),
        )
        return

    if rapport.insuffisantes:
        OperationalIncident.objects.create(
            title=(
                f"{len(rapport.insuffisantes)} demande(s) client "
                f"insuffisamment traitée(s) (job {job.id})"
            ),
            severity=IncidentSeverity.MEDIUM,
            job=job,
            order=job.order,
            details=rapport.as_details(),
        )


def _assembler_ce_qui_est_ecrit(job: GenerationJob) -> None:
    """Assemble le document d'un dossier EN ÉCHEC, s'il a écrit des chapitres.

    ## Pourquoi

    Demande de la cliente, 13/08/2026 : « il faut que les documents qui ont
    été en échec soient utilisables aussi ». Un dossier arrêté au dernier
    chapitre en a produit vingt-et-un : ils sont écrits, contrôlés, PAYÉS. Les
    perdre parce que le vingt-deuxième a échoué revient à jeter l'essentiel
    pour un accident de fin de course.

    ## Ce que cela coûte

    RIEN au modèle. L'assemblage est de la mise en page sur du texte déjà
    produit : aucun appel, aucun jeton, aucun centime. C'est la raison pour
    laquelle il n'y a pas d'arbitrage à faire — le seul choix était entre
    « disponible » et « perdu ».

    ## Ce que cela ne fait pas

    Aucun email. Le document existe et se télécharge, chez l'administrateur
    comme dans l'espace du client — qui liste tout artefact prêt, quel que soit
    le statut du dossier. Mais un dossier en échec ne s'envoie pas tout seul :
    c'est un document incomplet, et son envoi reste une décision.

    Ne lève jamais : un échec d'assemblage ne doit pas masquer l'échec
    d'origine, qui est celui qu'on veut voir remonter.
    """
    from .models import ChapterStatus  # noqa: PLC0415

    if not job.chapters.filter(status=ChapterStatus.DONE).exists():
        return

    import logging  # noqa: PLC0415

    try:
        from documents.livrable_word import (  # noqa: PLC0415
            assembler_livrable_word,
            chaine_word_active,
        )
        if chaine_word_active(job):
            assembler_livrable_word(job)
        else:
            from documents.services import assemble_document  # noqa: PLC0415
            assemble_document(job)
    except Exception:  # noqa: BLE001 — ne masque jamais l'échec d'origine
        logging.getLogger(__name__).exception(
            "Assemblage impossible pour le dossier en échec %s", job.id
        )
    else:
        logging.getLogger(__name__).info(
            "Dossier %s en échec : document assemblé avec les %s chapitre(s) "
            "écrits, téléchargeable sans nouvel appel au modèle.",
            job.id, job.chapters.filter(status=ChapterStatus.DONE).count(),
        )


@shared_task(name="generation.run_generation_job")  # type: ignore[untyped-decorator]
def run_generation_job_task(job_id: str) -> str:
    """Lance la generation complete d'un job (chapitres + QA + gate + livraison).

    Pipeline :
    1. Génération de tous les chapitres (runner)
    2. Passe QA post-génération (correction code fence, tables coupées,
       complétion IA des troncatures sévères)
    3. GATE DE LIVRAISON — NON BLOQUANT depuis le 13/08/2026 : contamination,
       cohérence chiffrée vs brief, complétude des verticales, troncature. Ce
       qui reste après les trois passes de correction ouvre un incident HIGH
       et marque `qa_status` BLOCKED, mais N'ARRÊTE PLUS l'envoi.
       Décision cliente : « l'envoi du document doit être auto et sans aucune
       action de ma part ». Sur les quatre motifs qu'elle a relevés ce jour-là,
       trois étaient FAUX — retenir un livrable payé sur nos propres défauts,
       puis lui demander de trancher, lui faisait porter nos erreurs.
    4. Livraison (assemblage PDF + email client) — TOUJOURS.
    """
    job = GenerationJob.objects.get(id=job_id)
    try:
        run_generation_job(job)
    except Exception as erreur:  # noqa: BLE001 — dernier filet, voir `echecs`
        # Sans ce filet, une exception qui traverse le pipeline laisse le job
        # affiche `running` jusqu'a ce que le gardien des jobs bloques passe
        # — deux heures plus tard. Vecu le 31/07/2026 : refus de l'API en 0,9
        # seconde, job « en cours » pendant quatorze minutes (regle 1).
        #
        # On attrape `Exception` et non une liste de types : une liste fermee
        # serait incomplete par construction, et c'est precisement le cas non
        # prevu qui produit le silence (regle 4).
        marquer_echec(job, erreur, etape="generation")
        _assembler_ce_qui_est_ecrit(job)
        raise

    if job.status == JobStatus.DONE:
        # ── Passe QA (corrective) ───────────────────────────────────────────
        #
        # AUCUNE ETAPE D'AMELIORATION NE DOIT EMPORTER LA LIVRAISON.
        #
        # Business plan `b8da2640`, 13/08/2026 : 21 chapitres sur 22, 3,55 €
        # payes, `qa_status` reste a `failed` — et aucun document, aucun email.
        # Une exception levee ENTRE la passe QA et le gate faisait sortir toute
        # la fin du pipeline, assemblage compris.
        #
        # Le correctif precedent protegeait la seule boucle de correction. Le
        # principe etait juste, applique un cran trop bas : c'est la SEQUENCE
        # entiere d'amelioration — QA, controle de couverture, correction —
        # qui doit pouvoir echouer sans detruire ce qui est ecrit.
        #
        # Chaque etape journalise son echec ; aucune ne decide plus si le
        # document existe.
        import logging  # noqa: PLC0415

        _journal = logging.getLogger(__name__)

        from .qa import run_qa_pass  # noqa: PLC0415
        try:
            run_qa_pass(job)
        except Exception:  # noqa: BLE001 — la QA n'est pas la livraison
            _journal.exception(
                "Passe QA interrompue pour le job %s : la suite continue.", job.id
            )

        # ── Boucle d'auto-correction + gate de livraison (bloquant) ─────────
        # Avant de bloquer, on régénère les chapitres fautifs (contamination,
        # incohérence chiffrée, troncature) avec les défauts en consigne, puis
        # on repasse le gate. Borné par EVKHA_CORRECTION_ROUNDS (défaut 3).
        # ── Les questions du client ont-elles reçu une réponse ? ────────────
        #
        # Angle mort exact, signalé par la cliente le 09/08/2026 : « éviter
        # d'avoir une étude très complète en apparence mais qui laisse
        # certaines questions initiales insuffisamment traitées ». Le gate
        # regarde la troncature et la cohérence, la conformité regarde la
        # forme, la vérification regarde les chiffres — personne ne relisait le
        # brief pour se demander si on y avait répondu (règle 9).
        #
        # Le résultat ne BLOQUE pas : il nomme. Un approfondissement
        # automatique réécrirait des chapitres, donc dépenserait, et ce projet
        # a appris quatre fois qu'on règle mal ce qu'on n'a pas d'abord mesuré.
        try:
            _controler_les_demandes_du_client(job)
        except Exception:  # noqa: BLE001 — un controle n'est pas la livraison
            _journal.exception(
                "Controle de couverture interrompu pour le job %s.", job.id
            )

        # `inclure_les_checks=True` : la boucle automatique corrige AUTANT que
        # la reprise manuelle. Décision cliente du 13/08/2026 — « les points
        # relevés par le contrôle doivent être corrigés en même temps et
        # automatiquement ».
        #
        # Ces motifs étaient exclus « parce que le manuel demande alors une
        # reprise humaine ». Il n'y a plus de reprise humaine : les exclure
        # revenait à garder pour un geste qui n'existe plus les notes les plus
        # actionnables de toutes — « dédupliquer les deux entrées Xerfi du
        # tableau 21.2 » se corrige mieux que « incohérence détectée ».
        from .correction import run_correction_loop  # noqa: PLC0415

        # LA CORRECTION NE DOIT PAS EMPORTER LA LIVRAISON AVEC ELLE.
        #
        # Etude concurrentielle `b6cb8076`, 13/08/2026 : dix chapitres sur dix,
        # 1,96 € payes, et RIEN — ni assemblage, ni email. La boucle de
        # correction avait bute sur le chapitre 8, son exception a traverse, et
        # tout ce qui suit — assemblage, livraison — n'a jamais ete atteint.
        #
        # La correction est une AMELIORATION du document, pas sa condition
        # d'existence. Un document imparfait mais complet vaut infiniment mieux
        # qu'un document parfait qui n'arrive jamais : c'est la meme lecon que
        # « un chapitre qui coince ne tue plus l'etude » (02/08) et que le CHECK
        # INITIAL cesse d'etre fatal (12/08), appliquee un cran plus loin.
        #
        # L'echec est journalise et le gate rejoue sur le document tel qu'il
        # est : le rapport dira ce qui n'a pas pu etre corrige, et la suite
        # s'execute normalement.
        try:
            report = run_correction_loop(job, inclure_les_checks=True)
        except Exception:  # noqa: BLE001 — la correction n'est pas la livraison
            import logging  # noqa: PLC0415

            logging.getLogger(__name__).exception(
                "Boucle de correction interrompue pour le job %s : le document "
                "part tel quel, le gate tranche sur son etat reel.", job.id,
            )
            from .gate import run_delivery_gate  # noqa: PLC0415
            report = run_delivery_gate(job)

        if not report.passed:
            # LE DOCUMENT PART QUAND MÊME. Décision cliente du 13/08/2026 :
            # « l'envoi du document doit être auto et sans aucune action de ma
            # part ».
            #
            # Ce qu'elle a mesuré ce jour-là : sur les quatre motifs qu'elle a
            # relevés, TROIS étaient faux — un identifiant refusé alors que
            # notre propre consigne demande de l'écrire, un mot de son métier
            # pris pour du jargon interne, un titre en gras compté comme phrase
            # tronquée. Retenir un livrable payé sur des motifs que nous
            # inventons, puis lui demander de trancher, revenait à lui faire
            # porter nos défauts.
            #
            # L'incident RESTE, en HIGH : ce qui n'a pas pu être fermé après
            # trois passes de correction doit se voir. Ce qui disparaît, c'est
            # l'attente — pas la trace.
            #
            # RISQUE ASSUMÉ, et il est réel : un motif VRAI part désormais chez
            # le client final. Le rempart n'est plus le blocage, ce sont les
            # trois passes de correction et la justesse des contrôles — c'est
            # pourquoi un contrôle qui crie faux coûte maintenant plus cher
            # qu'avant, et doit être réparé le jour où il se voit.
            GenerationJob.objects.filter(pk=job.pk).update(qa_status=QAStatus.BLOCKED)
            OperationalIncident.objects.create(
                title=(
                    f"Gate qualité : {len(report.failures)} point(s) non résolu(s), "
                    f"document livré quand même (job {job.id})"
                ),
                severity=IncidentSeverity.HIGH,
                job=job,
                order=job.order,
                details=report.as_details(),
            )

        # Mémorise les faits de marché validés pour les futurs runs
        # sur le même secteur/pays (fact store inter-runs).
        try:
            from .fact_store import export_facts  # noqa: PLC0415
            export_facts(job)
        except Exception:  # noqa: BLE001
            import logging  # noqa: PLC0415
            logging.getLogger(__name__).exception(
                "fact_store: export non bloquant échoué pour le job %s", job.id
            )

        from delivery.tasks import deliver_job_task  # noqa: PLC0415
        deliver_job_task.delay(job_id)

    return str(job.id)


@shared_task(name="generation.recontroler_et_corriger")  # type: ignore[untyped-decorator]
def recontroler_et_corriger_task(job_id: str) -> str:
    """Boucle de correction en TACHE DE FOND, puis verdict — jamais en requête.

    La première version du recontrôle « corriger » tournait dans la requête
    HTTP (10/08/2026, job `026fecea`) : le serveur web a tué le worker à son
    délai de garde, la réponse a été un 500, et le chapitre en cours de
    régénération est resté fantôme en `running` — le motif du dossier de la
    cliente du 09/08, reproduit en miniature par l'outil censé réparer.

    Une régénération est une génération : elle vit là où vivent les
    générations. Le Cost Engine borne la dépense au plafond du dossier,
    comme pendant la production. Aucune livraison ici — seule l'étiquette
    change, et l'incident porte les motifs frais si le blocage tient.
    """
    job = GenerationJob.objects.select_related("order").get(id=job_id)

    from .checks_blocs import rejouer_les_checks_ouverts  # noqa: PLC0415
    from .correction import run_correction_loop  # noqa: PLC0415
    from .gate import run_delivery_gate  # noqa: PLC0415

    # `inclure_les_checks` : cette tâche N'EST lancée que par le bouton
    # « corriger » du recontrôle — donc par une décision humaine, celle-là même
    # que le manuel exige avant de rejouer un CHECK de bloc.
    rapport = run_correction_loop(job, inclure_les_checks=True)

    # LA RÉGÉNÉRATION SEULE NE DÉBLOQUE RIEN.
    #
    # Le gate lit les incidents CHECK encore OUVERTS. Réécrire les chapitres
    # ne rejoue pas le CHECK et ne ferme pas l'incident : le dossier reste
    # bloqué sur un verdict rendu avant la correction. Mesuré sur `cc0dfe14`
    # (11/08/2026) : dix-sept chapitres régénérés pour 0,74 €, dix-neuf motifs
    # avant, vingt-et-un après — la boucle ne pouvait pas converger.
    #
    # C'est le défaut de la règle 9 dans sa forme la plus coûteuse : une
    # réparation qui n'atteint pas ce qui juge. On rejoue donc les CHECK dont
    # les chapitres viennent d'être réécrits, et on ferme les incidents que le
    # document ne justifie plus.
    rejoues = rejouer_les_checks_ouverts(job)
    if rejoues:
        rapport = run_delivery_gate(job)

    verdict = QAStatus.PASSED if rapport.passed else QAStatus.BLOCKED
    GenerationJob.objects.filter(pk=job.pk).update(qa_status=verdict)

    if not rapport.passed:
        OperationalIncident.objects.create(
            title=f"Gate qualité (correction) : toujours bloqué (job {job.id})",
            severity=IncidentSeverity.HIGH,
            job=job,
            order=job.order,
            details=rapport.as_details(),
        )
    return f"{job.id}:{verdict}"

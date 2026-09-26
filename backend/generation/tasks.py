from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.core.cache import cache
from django.utils import timezone

from delivery.models import DeliveryBatch
from monitoring.models import IncidentSeverity, OperationalIncident

from .echecs import marquer_echec
from .models import GenerationJob, JobStatus, QAStatus
from .runner import run_generation_job

_log = logging.getLogger(__name__)

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


#: Au-dela, un controle final « en cours » ne l'est plus : il est mort.
#: L'assemblage le plus lourd mesure quelques minutes ; vingt, c'est un
#: processus tue.
_CONTROLE_FINAL_PERDU_MINUTES = 20


@shared_task(name="generation.livrer_les_dossiers_oublies")  # type: ignore[untyped-decorator]
def livrer_les_dossiers_oublies() -> int:
    """Livre les dossiers qu'un controle final mort a laisses en plan.

    ## Pourquoi ce gardien existe

    Le 12/09/2026, la tache de controle final a ete TUEE deux fois sur un
    dossier de deux cents pages — sans exception, donc sans incident. Le
    document etait pret, paye, et personne ne l'envoyait : le dossier gardait
    seulement une trace « en cours ».

    Sortir le controle dans sa propre tache reduit le risque ; il ne le
    supprime pas, puisqu'un processus tue n'execute aucun `except`. Ce gardien
    est le filet : ce qui meurt en silence finit par se voir et par partir
    (regle 1).
    """
    echeance = timezone.now() - timedelta(minutes=_CONTROLE_FINAL_PERDU_MINUTES)
    oublies = [
        job
        for job in GenerationJob.objects.filter(
            status=JobStatus.DONE, updated_at__lt=echeance
        ).select_related("order")
        if (job.controle_final or {}).get("motif_d_arret") == "en cours"
        and not DeliveryBatch.objects.filter(order=job.order).exists()
    ]
    for job in oublies:
        OperationalIncident.objects.create(
            title=f"Controle final interrompu, document livre par le gardien (job {job.id})",
            severity=IncidentSeverity.HIGH,
            job=job,
            order=job.order,
            details={
                "type": "controle_final",
                "consigne": (
                    "Le controle du document assemble ne s'est jamais termine "
                    "(processus interrompu). Le document part tel qu'il est : "
                    "le relire avant de le remettre au client final."
                ),
            },
        )
        # Le verdict du gate n'est plus rendu par la génération : sans cette
        # ligne, un dossier dont le contrôle a été tué partirait sans verdict
        # du tout, `qa_status` resté à sa valeur initiale.
        _livrer(job)
        _verdict_sans_risque(job)
    return len(oublies)


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

    if rapport.insuffisantes or rapport.non_examinees:
        # Deux comptes, jamais additionnés. Sur le dossier `f7f2fad9`, 87 passages que le
        # contrôle n'avait pas lus sortaient titrés « demandes insuffisamment
        # traitées » : un verdict sur le document que personne n'avait rendu.
        titre = f"{len(rapport.insuffisantes)} demande(s) client insuffisamment traitée(s)"
        if rapport.non_examinees:
            titre += f", {len(rapport.non_examinees)} passage(s) non examiné(s)"
        OperationalIncident.objects.create(
            title=f"{titre} (job {job.id})",
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
    3. Contrôle de couverture des demandes du client (il nomme, il ne corrige
       pas).
    4. `controler_puis_livrer_task`, dans sa propre tâche : le contrôleur final
       — UN SEUL agent correcteur depuis le 13/09/2026, qui lit le fichier Word
       ET les motifs du gate —, puis la livraison, TOUJOURS, puis le verdict du
       gate sur le document qui est parti. Le verdict n'arrête pas l'envoi :
       décision cliente du 13/08/2026, « l'envoi du document doit être auto et
       sans aucune action de ma part ».

    Exception : un dossier HORS chaîne Word n'a pas de contrôleur final ; la
    boucle de correction du gate reste son seul correcteur.
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
        _effacer_les_textes_orphelins()
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
        # entiere d'amelioration — QA, controle de couverture —
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

        # Hors chaîne Word, pas de contrôleur final : la boucle du gate reste
        # le SEUL correcteur de ces dossiers. La supprimer pour eux aussi les
        # laissait partir sans qu'aucun motif ait été retenté (relecture du
        # 13/09/2026). Elle ne double rien : le contrôleur sort aussitôt.
        try:
            from documents.livrable_word import chaine_word_active  # noqa: PLC0415

            if not chaine_word_active(job):
                from .correction import run_correction_loop  # noqa: PLC0415

                run_correction_loop(job, inclure_les_checks=True)
        except Exception:  # noqa: BLE001 — la correction n'est pas la livraison
            _journal.exception(
                "Correction hors chaîne Word interrompue pour le job %s.", job.id
            )

        # PLUS DE BOUCLE DE CORRECTION ICI pour la chaîne Word, et plus de
        # verdict du gate non plus.
        #
        # Jusqu'au 13/09/2026, cette tâche réécrivait les chapitres fautifs aux
        # yeux du gate, puis confiait le document à la relecture finale, qui
        # réécrivait ceux qui l'étaient aux siens. Deux correcteurs en série :
        # sur la stratégie `a678b10a`, le premier a dépensé près de deux euros
        # sans fermer ses motifs, et le second a trouvé le budget vide. Le
        # contrôleur final lit désormais les motifs du gate lui-même.
        #
        # Le VERDICT du gate — `qa_status` et l'incident — est rendu après la
        # correction, sur le document qui part (`_rendre_le_verdict_du_gate`).
        # Le rendre ici annonçait des points « non résolus » qu'on n'avait pas
        # encore essayé de résoudre (règle 2 : un motif doit être vrai du
        # document que le lecteur reçoit).

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

        # ── Relecture FINALE, sur le fichier lui-même ───────────────────
        #
        # Tout ce qui precede juge la MATIERE du document : chapitres valides,
        # markdown rendu. Le `.docx` que le client ouvre n'etait relu par
        # personne avant l'envoi, et ses reserves partaient avec lui.
        #
        # Ici, le document est assemble, RELU, ses chapitres fautifs reecrits,
        # puis refait — et c'est le document relu qui part.
        #
        # Elle tourne dans SA PROPRE TACHE, et c'est la lecon du 12/09/2026 :
        # lancee ici, dans le processus qui vient d'ecrire vingt-et-un
        # chapitres, elle a ete TUEE deux fois sur un dossier de deux cents
        # pages — sans exception, donc sans incident, sans trace et sans
        # document envoye. Elle refait l'assemblage complet alors que la
        # memoire de la generation est encore occupee.
        #
        # Une tache separee repart sur une memoire liberee, et surtout la
        # livraison ne depend plus de sa survie.
        controler_puis_livrer_task.delay(job_id)

    _effacer_les_textes_orphelins()
    return str(job.id)


def _rendre_le_verdict_du_gate(job: GenerationJob) -> None:
    """Le gate juge le document TEL QU'IL PART : après la correction.

    LE DOCUMENT PART QUAND MÊME. Décision cliente du 13/08/2026 : « l'envoi du
    document doit être auto et sans aucune action de ma part ». Sur les quatre
    motifs qu'elle avait relevés ce jour-là, trois étaient faux — retenir un
    livrable payé sur des motifs que nous inventons revenait à lui faire porter
    nos défauts.

    L'incident RESTE, en HIGH : ce que la correction n'a pas pu fermer doit se
    voir. Ce qui disparaît, c'est l'attente — pas la trace.
    """
    from .gate import run_delivery_gate  # noqa: PLC0415

    job.refresh_from_db()
    report = run_delivery_gate(job)
    if report.passed:
        # Sans effacer un `failed` posé par la passe QA : le gate ne juge pas
        # ce qu'elle a jugé, et son vert ne vaut pas pour elle.
        GenerationJob.objects.filter(pk=job.pk).exclude(
            qa_status=QAStatus.FAILED
        ).update(qa_status=QAStatus.PASSED)
        return
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


def _verdict_sans_risque(job: GenerationJob) -> None:
    """Le verdict ne doit jamais emporter la livraison — ni se taire en panne.

    Un gate qui plante laissait `qa_status` à la valeur de la passe QA, souvent
    « passed », et aucun incident : un document parti sans juge ressemblait à
    un document jugé sain (règle 1, relecture du 13/09/2026).
    """
    try:
        _rendre_le_verdict_du_gate(job)
    except Exception as erreur:  # noqa: BLE001 — un verdict n'est pas la livraison
        import logging  # noqa: PLC0415

        logging.getLogger(__name__).exception(
            "Verdict du gate impossible pour le job %s : le document part tel quel.",
            job.id,
        )
        GenerationJob.objects.filter(pk=job.pk).update(qa_status=QAStatus.BLOCKED)
        OperationalIncident.objects.create(
            title=f"Verdict du gate impossible, document livré sans verdict (job {job.id})",
            severity=IncidentSeverity.HIGH,
            job=job,
            order=job.order,
            details={"type": "verdict_gate", "erreur": f"{type(erreur).__name__} : {erreur}"},
        )


@shared_task(name="generation.controler_puis_livrer")  # type: ignore[untyped-decorator]
def controler_puis_livrer_task(job_id: str) -> str:
    """Relit le document assemble, le fait corriger, PUIS le livre.

    La livraison ne depend jamais de la relecture : une panne devient un
    incident et le document part tel quel. Le client a paye un document ; un
    perfectionnement qui l'emporte est pire que son absence.
    """
    job = GenerationJob.objects.get(id=job_id)
    try:
        from .controle_final import relire_avant_envoi  # noqa: PLC0415

        relire_avant_envoi(job)
    except Exception as exc:  # noqa: BLE001 — la livraison prime toujours
        import logging  # noqa: PLC0415

        logging.getLogger(__name__).exception(
            "Controle final impossible pour le job %s : le document part tel quel",
            job.id,
        )
        OperationalIncident.objects.create(
            title=f"Controle final du document impossible (job {job.id})",
            severity=IncidentSeverity.HIGH,
            job=job,
            order=job.order,
            details={
                "type": "controle_final",
                "erreur": f"{type(exc).__name__} : {exc}",
                "consigne": (
                    "Le document est parti sans cette relecture. "
                    "Le relire avant de le remettre au client final."
                ),
            },
        )

    job.refresh_from_db()
    # L'envoi AVANT le verdict. Une fois la relecture terminée, le gardien ne
    # rattrape plus ce dossier : un worker tué pendant le rendu du gate — deux
    # cents pages — le priverait de son envoi pour de bon. Le verdict, lui,
    # n'est qu'une étiquette et un incident (relecture du 13/09/2026).
    _livrer(job)
    _verdict_sans_risque(job)
    _effacer_les_textes_orphelins()
    return str(job.id)


def _effacer_les_textes_orphelins() -> None:
    """Le dossier a fini : le texte des pièces retirées pendant qu'il tournait part.

    Ne lève jamais — c'est du ménage de rétention, pas une étape du dossier ;
    la purge des pièces jointes le refait de toute façon.
    """
    try:
        from .documents_client import effacer_les_textes_orphelins  # noqa: PLC0415

        effacer_les_textes_orphelins()
    except Exception:  # noqa: BLE001
        import logging  # noqa: PLC0415

        logging.getLogger(__name__).exception("Effacement des textes orphelins impossible")


def _livrer(job: GenerationJob) -> None:
    """Envoie le document terminé — sauf reprise de validation « sans envoi ».

    Une reprise lancée avec `sans_envoi` (`job_regenerer`) s'assemble et
    devient téléchargeable dans la console, mais aucun courriel ne part :
    on la lit avant que le client la reçoive, et l'envoi se fait ensuite par
    « Renvoyer ». Tout autre dossier livre comme avant.

    Le drapeau ne vaut QUE sur une reprise prouvée : le `raw_payload` d'une
    commande Systeme.io est le webhook brut, et une clé `sans_envoi` venue de
    là suffirait sinon à priver un client de son document (audit du
    11/09/2026).
    """
    from organisations.liaison import est_une_reprise_a_nos_frais  # noqa: PLC0415

    brut = job.order.raw_payload if isinstance(job.order.raw_payload, dict) else {}
    if brut.get("sans_envoi") is True and est_une_reprise_a_nos_frais(job):
        from delivery.services import assembler_sans_envoyer  # noqa: PLC0415

        assembler_sans_envoyer(job)
        return

    from delivery.tasks import deliver_job_task  # noqa: PLC0415

    deliver_job_task.delay(str(job.id))


#: Deux heures : au-delà, une boucle de correction est morte avec son worker,
#: et le verrou ne doit pas empêcher la suivante pour toujours.
_VERROU_CORRECTION_S = 2 * 3600


def _cle_de_verrou(job_id: str) -> str:
    return f"evkha:correction:{job_id}"


def verrou_de_correction(job_id: str) -> bool:
    """Vrai si CETTE boucle de correction obtient le dossier, faux si une autre l'a.

    Rien ne l'empêchait : deux clics sur « corriger » lançaient deux boucles
    sur le même dossier, chacune sous le plafond, chacune payée (audit du
    26/09/2026). `cache.add` est atomique sur Redis — le cache de production —
    comme sur le cache local des tests.
    """
    return bool(cache.add(_cle_de_verrou(job_id), 1, _VERROU_CORRECTION_S))


def liberer_verrou_de_correction(job_id: str) -> None:
    cache.delete(_cle_de_verrou(job_id))


def correction_en_cours(job_id: str) -> bool:
    return cache.get(_cle_de_verrou(job_id)) is not None


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
    if not verrou_de_correction(job_id):
        _log.warning("Job %s : une correction est déjà en cours, appel ignoré.", job_id)
        return f"{job.id}:deja_en_cours"
    try:
        return _corriger_et_juger(job)
    except Exception as erreur:
        # Sans ceci, un plantage laissait l'ancien `qa_status` en place et
        # aucune trace : le tableau de bord montrait un dossier « en
        # correction » qui ne l'était plus (audit du 26/09/2026).
        OperationalIncident.objects.create(
            title=f"Correction interrompue par une erreur (job {job.id})",
            severity=IncidentSeverity.HIGH,
            job=job,
            order=job.order,
            details={"erreur": f"{type(erreur).__name__} : {str(erreur)[:400]}"},
        )
        raise
    finally:
        liberer_verrou_de_correction(job_id)


def _corriger_et_juger(job: GenerationJob) -> str:
    """La boucle de correction puis le verdict — le corps de la tâche ci-dessus."""
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

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


@shared_task(name="generation.run_generation_job")  # type: ignore[untyped-decorator]
def run_generation_job_task(job_id: str) -> str:
    """Lance la generation complete d'un job (chapitres + QA + gate + livraison).

    Pipeline :
    1. Génération de tous les chapitres (runner)
    2. Passe QA post-génération (correction code fence, tables coupées,
       complétion IA des troncatures sévères)
    3. GATE DE LIVRAISON (Brique 3, brief client juillet 2026) — BLOQUANT :
       contamination pipeline, cohérence chiffrée vs brief, complétude des
       verticales, troncature. Un seul échec → le document NE PART PAS chez
       le client ; incident HIGH + statut qa BLOCKED ; le PDF est tout de
       même assemblé pour relecture admin (sans email). La livraison ne peut
       alors être déclenchée que manuellement depuis le dashboard.
    4. Livraison (assemblage PDF + email client) — uniquement si gate PASSED
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
        raise

    if job.status == JobStatus.DONE:
        # ── Passe QA (corrective) ───────────────────────────────────────────
        from .qa import run_qa_pass  # noqa: PLC0415
        run_qa_pass(job)

        # ── Boucle d'auto-correction + gate de livraison (bloquant) ─────────
        # Avant de bloquer, on régénère les chapitres fautifs (contamination,
        # incohérence chiffrée, troncature) avec les défauts en consigne, puis
        # on repasse le gate. Borné par EVKHA_CORRECTION_ROUNDS (défaut 1).
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
        _controler_les_demandes_du_client(job)

        from .correction import run_correction_loop  # noqa: PLC0415
        report = run_correction_loop(job)

        if not report.passed:
            GenerationJob.objects.filter(pk=job.pk).update(qa_status=QAStatus.BLOCKED)
            OperationalIncident.objects.create(
                title=f"Gate qualité : livraison bloquée (job {job.id})",
                severity=IncidentSeverity.HIGH,
                job=job,
                order=job.order,
                details=report.as_details(),
            )
            # Document assemblé pour relecture admin — AUCUN email client.
            # Par la MÊME chaîne que la livraison : relire un document produit
            # autrement que celui qui serait parti ne dit rien de ce qui serait
            # parti (règle 3).
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
            except Exception:  # noqa: BLE001 — l'assemblage admin ne doit pas masquer le blocage
                import logging  # noqa: PLC0415
                logging.getLogger(__name__).exception(
                    "Assemblage PDF admin impossible pour le job bloqué %s", job.id
                )
            return str(job.id)

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

    from .correction import run_correction_loop  # noqa: PLC0415

    # `inclure_les_checks` : cette tâche N'EST lancée que par le bouton
    # « corriger » du recontrôle — donc par une décision humaine, celle-là même
    # que le manuel exige avant de rejouer un CHECK de bloc.
    rapport = run_correction_loop(job, inclure_les_checks=True)
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

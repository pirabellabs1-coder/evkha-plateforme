"""La livraison a sa file, sa file a son ouvrier, et l'e-mail a le Word.

## Le defaut mesure

17/08/2026. Une cliente commande ses quatre etudes d'un coup. Le worker tient
deux creneaux, les quatre generations les occupent une heure, et les taches de
livraison attendent dans la MEME file. L'etude de concurrence finit a 16:32 :
son document part a 17:27. Cinquante-cinq minutes pendant lesquelles un
livrable termine et paye existait en base sans que rien ne l'envoie.

## Ce que ces tests verrouillent

Le routage et l'ouvrier sont un COUPLE. Router `delivery.*` vers une file que
personne ne consomme ne ralentit pas la livraison : il l'arrete. Le test lit
donc les deux artefacts — les reglages Django et le compose de production — et
refuse qu'ils divergent.

C'est la meme precaution que `test_echeances_periodiques` prend pour les taches
periodiques, et pour la meme raison : un branchement qui n'existe que dans un
seul des deux fichiers ne tourne pas.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

#: Repere pris sur CE fichier — `backend/tests/x.py` → `backend` → racine.
#: `settings.BASE_DIR` ne dit pas la meme chose selon l'environnement, et un
#: test qui cherche au mauvais endroit ne verrouille rien (regle 1).
RACINE = Path(__file__).resolve().parents[2]

#: Le compose que Coolify construit — `docker_compose_location` de l'application
#: `evkha-api`. Ce n'est PAS `docker-compose.yml`, qui sert au poste local.
COMPOSE_PROD = RACINE / "docker-compose.prod.yml"

FILE_LIVRAISON = "livraison"


def _compose() -> str:
    assert COMPOSE_PROD.is_file(), f"Compose de production introuvable : {COMPOSE_PROD}"
    return COMPOSE_PROD.read_text(encoding="utf-8")


def test_les_taches_de_livraison_ont_leur_propre_file() -> None:
    """Le routage existe, et il vise bien la file nommee.

    Echoue sur le code d'avant : aucun `CELERY_TASK_ROUTES`, donc les
    livraisons partaient dans la file par defaut, derriere les generations.
    """
    from evkha.celery import app

    for tache in (
        "delivery.deliver_job",
        "delivery.send_email_for_job",
        "delivery.generate_pdf_for_failed_job",
    ):
        route = app.amqp.router.route({}, tache)
        assert str(route["queue"].name) == FILE_LIVRAISON, (
            f"{tache} ne part pas dans la file « {FILE_LIVRAISON} »."
        )


def test_les_generations_restent_dans_la_file_par_defaut() -> None:
    """Contre-epreuve : on n'a pas deplace TOUT le monde.

    Si les generations suivaient les livraisons, on aurait simplement renomme
    le probleme.
    """
    from evkha.celery import app

    route = app.amqp.router.route({}, "generation.run_generation_job")
    assert str(route["queue"].name) != FILE_LIVRAISON


def test_un_ouvrier_consomme_la_file_de_livraison() -> None:
    """LE test qui compte : une file sans ouvrier ne livre plus rien.

    On lit le compose de production, pas une intention. Un `-Q livraison` sur
    une ligne `celery ... worker` suffit : peu importe le nom du service.
    """
    contenu = _compose()
    consommateurs = [
        ligne for ligne in contenu.splitlines()
        if "celery" in ligne and "worker" in ligne
        and re.search(rf"-Q\s+\S*\b{FILE_LIVRAISON}\b", ligne)
    ]
    assert consommateurs, (
        f"Aucun worker du compose de production ne consomme « {FILE_LIVRAISON} ». "
        "Les livraisons routees vers cette file ne seraient JAMAIS executees."
    )


def test_un_ouvrier_consomme_toujours_la_file_par_defaut() -> None:
    """Contre-epreuve symetrique : les generations gardent le leur.

    Un `-Q livraison` ajoute au worker EXISTANT — au lieu d'un second service —
    aurait fait passer ce depot de « la livraison attend » a « plus rien ne se
    genere ».
    """
    contenu = _compose()
    sans_restriction = [
        ligne for ligne in contenu.splitlines()
        if "celery" in ligne and "worker" in ligne and "-Q" not in ligne
    ]
    assert sans_restriction, (
        "Plus aucun worker ne consomme la file par defaut : les generations "
        "ne partiraient plus."
    )


@pytest.mark.parametrize("kind", ["docx", "pdf"])
def test_l_email_de_livraison_emporte_le_word_et_le_pdf(kind: str) -> None:
    """Les deux chemins d'envoi joignent la MEME chose.

    Echoue sur le code d'avant : `send_email_for_job` filtrait sur les seuls
    PDF. Le 17/08/2026 la cliente a recu quatre PDF et aucun Word, parce que
    ses documents sont partis par cette route-la.
    """
    from delivery.services import PIECES_JOINTES_LIVREES

    assert kind in {str(k) for k in PIECES_JOINTES_LIVREES}


@pytest.mark.django_db
def test_la_route_de_secours_joint_le_word_elle_aussi() -> None:
    """Le test de comportement, sur la route qui a REELLEMENT servi.

    Echoue sur le code d'avant : `send_email_for_job` ne joignait que les PDF,
    et c'est par elle que les quatre dossiers du 17/08/2026 sont partis.
    """
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from delivery.services import send_email_for_job
    from documents.models import ArtifactKind, ArtifactStatus, DocumentArtifact
    from generation.models import GenerationJob, JobStatus
    from integrations.brevo import EmailSendResult
    from orders.models import Order

    offer = Offer.objects.create(
        name="Etude", slug="file-livraison-word",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="cliente@test.local")
    commande = Order.objects.create(
        systeme_order_id="file-livraison-word", customer=client, offer=offer,
    )
    job = GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.MARKET_STUDY,
        status=JobStatus.DONE,
    )
    for kind in (ArtifactKind.DOCX, ArtifactKind.PDF):
        DocumentArtifact.objects.create(
            job=job, kind=kind, status=ArtifactStatus.READY,
            download_url=f"https://exemple.test/{kind}",
        )

    recues: list[tuple[str, ...]] = []

    class _Mouchard:
        def send_delivery_email(self, *, recipient_email, subject, html_body, attachments):
            recues.append(tuple(a.filename for a in attachments))
            return EmailSendResult(provider_message_id="test")

    send_email_for_job(job, email_client=_Mouchard())

    assert recues, "Aucun e-mail n'a ete construit."
    jointes = recues[0]
    assert any(f.endswith(".docx") for f in jointes), (
        f"Le Word n'est pas joint : {jointes}. C'est le document que la "
        "cliente retravaille."
    )
    assert any(f.endswith(".pdf") for f in jointes), f"Le PDF manque : {jointes}"

"""Un document que le système déclare défectueux ne doit pas être téléchargeable.

Le contrôle de rendu bloquait l'envoi du courriel — et **rien d'autre**.

`_assembler_livrable` écrit les artefacts en `READY`, avec leur URL, AVANT que
la vérification ne tranche. Quand elle bloque, `LivrableRetenuError` empêche
l'e-mail de partir, un lot FAILED est enregistré… et le job reste `DONE`.
L'espace client, lui, listait tous les `DOCX`/`PDF` du job sans regarder ni
leur statut ni celui du job.

Résultat : le client téléchargeait d'un bouton, depuis son espace, le document
que la plateforme venait de déclarer défectueux — et le remettait à son propre
client. C'est la règle 3 dans sa forme la plus directe : le contrôle protégeait
le courriel, pas ce que le lecteur allait ouvrir.

Deux vues listaient ces fichiers chacune de leur côté, avec deux filtres
différents (l'une sur `download_url`, l'autre sur rien). D'où le prédicat
unique de `suivi.fichiers_du_client`, que les deux appellent (règle 5).
"""
from __future__ import annotations

from typing import Any

import pytest

from organisations import inscription, suivi

pytestmark = pytest.mark.django_db

EMAIL = "claire@cabinet-duval.fr"


@pytest.fixture
def dossier() -> Any:
    """Un job terminé, avec ses deux artefacts prêts et téléchargeables."""
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from documents.models import ArtifactKind, ArtifactStatus, DocumentArtifact
    from generation.models import GenerationJob, JobStatus
    from orders.models import Order

    organisation = inscription.ouvrir_compte(
        raison_sociale="Cabinet Duval",
        email=EMAIL,
        mot_de_passe="un-mot-de-passe-solide-42",
        activer_abonnement=False,
    ).organisation

    offre = Offer.objects.create(
        name="Étude de marché",
        slug="etude-retenue",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    commande = Order.objects.create(
        systeme_order_id="cmd-retenue",
        customer=Customer.objects.get(email=EMAIL),
        offer=offre,
        organisation=organisation,
    )
    job = GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.MARKET_STUDY,
        status=JobStatus.DONE,
    )
    for genre in (ArtifactKind.DOCX, ArtifactKind.PDF):
        DocumentArtifact.objects.create(
            job=job,
            kind=genre,
            status=ArtifactStatus.READY,
            storage_key=f"livrables/etude.{genre}",
            download_url=f"http://exemple/media/livrables/etude.{genre}",
        )

    class Dossier:
        pass

    Dossier.organisation = organisation
    Dossier.job = job
    return Dossier


def _jeton() -> str:
    from organisations import authentification

    jeton, _ = authentification.ouvrir_session(EMAIL, "un-mot-de-passe-solide-42")
    return str(jeton)


# ── Un document retenu disparaît des deux écrans ─────────────────────────────


def test_un_job_en_intervention_n_offre_aucun_fichier(dossier: Any) -> None:
    """Le test qui échoue sur le code d'avant.

    Les artefacts restent `READY` en base — le rendu a réussi. C'est le JOB qui
    dit que le document ne doit pas partir.
    """
    from generation.models import GenerationJob, JobStatus

    assert suivi.fichiers_du_client(dossier.job), "l'amorce du test est fausse"

    GenerationJob.objects.filter(pk=dossier.job.pk).update(
        status=JobStatus.INTERVENTION_REQUISE
    )
    dossier.job.refresh_from_db()

    assert suivi.fichiers_du_client(dossier.job) == [], (
        "le client peut telecharger un document declare defectueux"
    )


def test_la_page_de_suivi_ne_propose_plus_le_telechargement(
    client: Any, dossier: Any
) -> None:
    """Le vrai chemin, par l'API (règle 7)."""
    from generation.models import GenerationJob, JobStatus

    GenerationJob.objects.filter(pk=dossier.job.pk).update(
        status=JobStatus.INTERVENTION_REQUISE
    )

    reponse = client.get(
        f"/api/espace/livrables/{dossier.job.id}/",
        HTTP_AUTHORIZATION=f"Bearer {_jeton()}",
    )
    assert reponse.status_code == 200
    assert reponse.json()["fichiers"] == []


def test_la_bibliotheque_ne_propose_plus_le_telechargement(
    client: Any, dossier: Any
) -> None:
    """La SECONDE vue, qui avait son propre filtre — et donc son propre trou.

    Corriger la seule page de suivi aurait laissé la liste des livrables offrir
    les mêmes fichiers, deux clics plus loin.
    """
    from generation.models import GenerationJob, JobStatus

    GenerationJob.objects.filter(pk=dossier.job.pk).update(
        status=JobStatus.INTERVENTION_REQUISE
    )

    reponse = client.get(
        "/api/espace/livrables/", HTTP_AUTHORIZATION=f"Bearer {_jeton()}"
    )
    assert reponse.status_code == 200
    livrable = reponse.json()["livrables"][0]
    assert livrable["fichiers"] == []


def test_un_job_echoue_ou_annule_n_offre_rien_non_plus(dossier: Any) -> None:
    """La CLASSE, pas le seul cas de la retenue (règle 4).

    Un job annulé — dont le crédit vient d'être restitué — ne doit pas laisser
    le document derrière lui : le client aurait rendu son crédit ET gardé
    l'étude.
    """
    from generation.models import GenerationJob, JobStatus

    for statut in (JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.RUNNING):
        GenerationJob.objects.filter(pk=dossier.job.pk).update(status=statut)
        dossier.job.refresh_from_db()
        assert suivi.fichiers_du_client(dossier.job) == [], f"statut {statut}"


# ── Ce que le correctif ne doit pas casser ───────────────────────────────────


def test_un_document_livrable_reste_telechargeable(client: Any, dossier: Any) -> None:
    """Contre-épreuve : le cas normal, qui est aussi le plus fréquent."""
    reponse = client.get(
        f"/api/espace/livrables/{dossier.job.id}/",
        HTTP_AUTHORIZATION=f"Bearer {_jeton()}",
    )
    fichiers = reponse.json()["fichiers"]

    assert len(fichiers) == 2
    assert {f["kind"] for f in fichiers} == {"docx", "pdf"}


def test_un_artefact_expire_n_est_plus_propose(dossier: Any) -> None:
    """La rétention a fait son œuvre : le fichier n'existe plus sur le disque.

    Continuer à l'afficher enverrait le client sur un lien mort et lui ferait
    croire à une panne.
    """
    from documents.models import ArtifactStatus, DocumentArtifact

    DocumentArtifact.objects.filter(job=dossier.job).update(
        status=ArtifactStatus.EXPIRED
    )

    assert suivi.fichiers_du_client(dossier.job) == []


def test_les_etats_livrables_sont_une_liste_fermee() -> None:
    """On énumère ce qui est livrable, jamais ce qui ne l'est pas.

    Une liste d'exclusions serait incomplète dès qu'un statut est ajouté — et
    le nouveau statut laisserait passer les documents par défaut (règle 4).
    """
    assert suivi.ETATS_LIVRABLES == ("done",)

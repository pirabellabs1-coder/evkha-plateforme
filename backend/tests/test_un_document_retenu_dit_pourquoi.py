"""Un statut sans raison ne se corrige pas.

Cliente, 12/08/2026, capture d'écran à l'appui : « ça dit en attente de
relecture pourtant rien ne se passe ».

Elle avait raison deux fois.

D'abord sur le libellé : « En attente de relecture » annonce une étape qui
n'existe pas. Rien ne relit, rien n'est programmé, rien n'arrivera — le
document est retenu par le contrôle qualité et attend une décision humaine.
Un libellé qui promet un processus fait attendre.

Ensuite sur le fond, et c'est le plus grave : l'écran ne disait nulle part
POURQUOI. Pour connaître les neuf motifs de son business plan, il a fallu
interroger un incident par l'API. Or c'est sur cet écran qu'on décide
d'envoyer ou non.
"""
from __future__ import annotations

import json

import pytest


@pytest.fixture
def dossier_retenu():  # type: ignore[no-untyped-def]
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import GenerationJob, JobStatus, QAStatus
    from monitoring.models import IncidentSeverity, OperationalIncident
    from orders.models import Order

    offre = Offer.objects.create(
        name="BP", slug="test-motifs",
        deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    client = Customer.objects.create(email="motifs@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-motifs", customer=client, offer=offre,
    )
    job = GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.BUSINESS_PLAN,
        status=JobStatus.DONE,
        qa_status=QAStatus.BLOCKED,
    )
    OperationalIncident.objects.create(
        title=f"Gate qualité : bloqué (job {job.id})",
        severity=IncidentSeverity.HIGH,
        job=job,
        order=commande,
        details={"failures": [
            {
                "check": "coherence_chiffree",
                "chapitre": 9,
                "detail": (
                    "Valeurs divergentes pour un meme libelle : "
                    "seuil_rentabilite : 4 000 € au ch. 9 ; 64 000 € au ch. 10."
                ),
            },
            {
                "check": "reference_client_illisible",
                "chapitre": None,
                "detail": (
                    "ca_previsionnel : le brief client ne donne aucun montant "
                    "exploitable."
                ),
            },
        ]},
    )
    return job


@pytest.mark.django_db
def test_le_detail_rend_les_motifs_du_controle(
    client_admin, dossier_retenu  # type: ignore[no-untyped-def]
) -> None:
    """C'est sur cet écran qu'on décide d'envoyer : la raison doit y être."""
    reponse = client_admin.get(f"/api/dashboard/jobs/{dossier_retenu.id}/")

    assert reponse.status_code == 200
    motifs = json.loads(reponse.content)["qa_motifs"]
    assert len(motifs) == 2
    assert motifs[0]["check"] == "coherence_chiffree"
    assert motifs[0]["chapitre"] == 9
    assert "seuil_rentabilite" in motifs[0]["detail"]


@pytest.mark.django_db
def test_un_motif_transversal_garde_son_absence_de_chapitre(
    client_admin, dossier_retenu  # type: ignore[no-untyped-def]
) -> None:
    """`chapitre: null` n'est pas le chapitre zéro.

    Le brief qui ne donne aucun montant ne se répare dans AUCUN chapitre :
    l'afficher sur le 0 enverrait corriger là où il n'y a rien à corriger.
    """
    reponse = client_admin.get(f"/api/dashboard/jobs/{dossier_retenu.id}/")
    motifs = json.loads(reponse.content)["qa_motifs"]

    transversal = next(m for m in motifs if m["check"] == "reference_client_illisible")
    assert transversal["chapitre"] is None


@pytest.mark.django_db
def test_un_dossier_sain_ne_rend_aucun_motif(
    client_admin, dossier_retenu  # type: ignore[no-untyped-def]
) -> None:
    """CONTRE-ÉPREUVE : pas d'incident, pas de liste — et pas d'erreur."""
    from monitoring.models import OperationalIncident

    OperationalIncident.objects.all().delete()
    reponse = client_admin.get(f"/api/dashboard/jobs/{dossier_retenu.id}/")

    assert reponse.status_code == 200
    assert json.loads(reponse.content)["qa_motifs"] == []


@pytest.mark.django_db
def test_le_plus_recent_controle_fait_foi(
    client_admin, dossier_retenu  # type: ignore[no-untyped-def]
) -> None:
    """Un recontrôle qui résout des motifs ne doit pas laisser lire les anciens.

    Sans cet ordre, l'écran afficherait les quatorze motifs d'avant un
    correctif au lieu des neuf d'après — et on corrigerait ce qui est déjà
    réparé.
    """
    from monitoring.models import IncidentSeverity, OperationalIncident

    OperationalIncident.objects.create(
        title=f"Gate qualité (recontrôle) (job {dossier_retenu.id})",
        severity=IncidentSeverity.HIGH,
        job=dossier_retenu,
        details={"failures": [
            {"check": "troncature", "chapitre": 4, "detail": "Phrase coupée."},
        ]},
    )

    reponse = client_admin.get(f"/api/dashboard/jobs/{dossier_retenu.id}/")
    motifs = json.loads(reponse.content)["qa_motifs"]

    assert len(motifs) == 1
    assert motifs[0]["check"] == "troncature"


def test_l_ecran_ne_promet_plus_une_relecture_inexistante() -> None:
    """La cause, pas seulement la donnée.

    Les motifs pourraient être rendus par l'API sans que l'écran les montre —
    et le libellé continuerait de faire attendre une relecture qui n'arrive
    jamais.
    """
    ecran = _ecran_sans_commentaires("JobDetail.tsx")

    assert "En attente de relecture" not in ecran
    assert "qa_motifs" in ecran, "les motifs ne sont pas affichés"
    assert "Ce que le contrôle qualité a retenu" in ecran


def test_aucun_ecran_ne_demande_une_relecture() -> None:
    """« Je n'ai rien à faire dans le document jusqu'à envoi au client. »

    Demande de la cliente du 13/08/2026, et elle a raison sur le fond : trois
    des quatre motifs qu'elle a relevés ce jour-là étaient FAUX — un contrôle
    qui refuse ce que notre propre consigne demande d'écrire, un mot de son
    métier pris pour du jargon interne, un titre en gras compté comme phrase
    tronquée.

    Lui demander de « relire » revenait à lui faire porter nos défauts. Son
    geste est l'ENVOI : les écrans disent donc un état — ce que la correction
    automatique n'a pas su fermer — jamais une tâche qui lui incombe.
    """
    for fichier in ("JobDetail.tsx", "Jobs.tsx"):
        ecran = _ecran_sans_commentaires(fichier)
        for interdit in ("relecture", "à relire", "à revoir"):
            assert interdit not in ecran, f"{fichier} : « {interdit} »"


def _ecran_sans_commentaires(fichier: str) -> str:
    """Le texte AFFICHÉ, commentaires retirés.

    Un commentaire a le droit de citer l'ancien libellé pour dire pourquoi il a
    changé — c'est même ce que ce dépôt demande. Sans ce nettoyage, le test
    tomberait sur l'explication au lieu de l'interface, et pousserait à effacer
    la mémoire du défaut pour faire passer le contrôle.
    """
    import re
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / fichier
    ).read_text(encoding="utf-8")
    sans_blocs = re.sub(r"/\*[\s\S]*?\*/", " ", source)
    return "\n".join(
        ligne for ligne in sans_blocs.split("\n")
        if not ligne.strip().startswith("//")
    )

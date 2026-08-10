"""Un document refusé par le gate ne doit pas ressembler à un document validé.

## Ce qui s'est passé le 10/08/2026

Trois dossiers en production portaient `qa_status = "blocked"` ET
`delivery_status = "sent"` — étude de marché comprise. Le gate les avait
refusés, ils sont partis chez la cliente.

Le gate n'est pas en cause : il bloque bien le chemin automatique
(`generation/tasks.py` rend la main avant d'appeler la livraison, et un test le
verrouille). La combinaison vient d'une action manuelle — `job_redeliver` ou
`job_send_email` — et cette dérogation est **prévue et documentée** :
« livraison possible uniquement par action manuelle admin (decision humaine
assumée) ».

## Le vrai défaut : une dérogation qu'on ne voit pas

`qa_status` était sérialisé par le backend depuis toujours, et **aucun écran ne
le lisait**. Un dossier bloqué s'affichait exactement comme un dossier validé :
même badge, même bouton « Envoyer par email », aucun avertissement. On ne peut
pas assumer une décision qu'on ignore avoir prise.

Ces tests verrouillent la matière que l'écran consomme. Si le champ disparaît
du payload, l'avertissement disparaît de l'écran — en silence, et c'est
précisément le mode de panne que la règle 1 condamne : un contrôle qui n'a plus
rien à comparer et qui se tait.

**Le comportement du backend n'est pas modifié.** La dérogation reste possible ;
elle devient visible.
"""
from __future__ import annotations

import pytest
from django.test import Client, override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.models import GenerationJob, JobStatus, QAStatus
from orders.models import Order


def _job(qa_status: str) -> GenerationJob:
    offre = Offer.objects.create(
        slug=f"offre-{qa_status}",
        name="Étude de la concurrence",
        deliverable_type=DeliverableType.COMPETITOR_STUDY,
    )
    client = Customer.objects.create(email=f"{qa_status}@test.local")
    commande = Order.objects.create(
        systeme_order_id=f"cmd-{qa_status}", customer=client, offer=offre,
    )
    return GenerationJob.objects.create(
        order=commande, status=JobStatus.DONE, qa_status=qa_status,
    )


def _get(url: str) -> dict | list:
    with override_settings(DEBUG=True, EVKHA_DASHBOARD_AUTH_DISABLED=True):
        reponse = Client().get(url)
    assert reponse.status_code == 200, reponse.content
    return reponse.json()


@pytest.mark.django_db
def test_le_detail_expose_le_verdict_du_gate() -> None:
    """C'est la matière du badge « Qualité : bloqué »."""
    job = _job(QAStatus.BLOCKED)

    data = _get(f"/api/dashboard/jobs/{job.id}/")

    assert data["qa_status"] == "blocked"


@pytest.mark.django_db
def test_la_liste_expose_aussi_le_verdict() -> None:
    """L'écran de détail n'est pas le seul d'où l'on peut envoyer.

    La liste porte son propre bouton d'envoi. N'avertir que sur une des deux
    pages ferait de l'avertissement une décoration : l'autre bouton envoie le
    même document, au même client, en un clic (règle 4).
    """
    _job(QAStatus.BLOCKED)

    items = _get("/api/dashboard/jobs/")

    assert isinstance(items, list)
    assert [item["qa_status"] for item in items] == ["blocked"]


@pytest.mark.django_db
def test_un_dossier_valide_se_distingue_d_un_dossier_bloque() -> None:
    """CONTRE-ÉPREUVE : sans elle, un champ constant passerait ces tests.

    Un backend qui renverrait « blocked » partout ferait crier l'interface sur
    tous les dossiers, et l'avertissement ne voudrait plus rien dire — le
    défaut inverse, tout aussi coûteux.
    """
    _job(QAStatus.BLOCKED)
    _job(QAStatus.PASSED)

    verdicts = {item["qa_status"] for item in _get("/api/dashboard/jobs/")}

    assert verdicts == {"blocked", "passed"}

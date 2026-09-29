"""Le rapport interne dit ce que la production a corrigé — à l'administrateur seul.

29/09/2026 : le client ne voit qu'une progression fluide et un document propre.
Ce qui a été trouvé et corrigé en route se lit ici, pour repérer les chapitres
et les prompts de rédacteur qui produisent le plus de reprises.
"""
from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from dashboard.qualite import famille_du_motif
from generation.models import GenerationJob
from orders.models import Order

pytestmark = pytest.mark.django_db

URL = "/api/dashboard/qualite/"


def _dossier(suffixe: str, **champs: Any) -> GenerationJob:
    offre, _ = Offer.objects.get_or_create(
        slug="bp-qualite",
        defaults={"name": "BP", "deliverable_type": DeliverableType.BUSINESS_PLAN},
    )
    client = Customer.objects.create(email=f"qualite-{suffixe}@exemple.fr")
    commande = Order.objects.create(systeme_order_id=f"q-{suffixe}", customer=client, offer=offre)
    return GenerationJob.objects.create(
        order=commande, deliverable_type=DeliverableType.BUSINESS_PLAN, **champs,
    )


def _memoire(*chapitres: tuple[int, list[str], bool]) -> dict[str, Any]:
    return {"chapitres": {
        str(n): {"titre": f"Chapitre {n}", "reperes": ["ca_previsionnel_an1"],
                 "verifie": ["x"], "motifs": motifs, "replie": replie}
        for n, motifs, replie in chapitres
    }}


def test_le_rapport_agrege_par_chapitre_et_par_motif(client_admin: Any) -> None:
    _dossier("a", memoire_active=True, memoire_etude=_memoire(
        (16, ["Chiffre écrit en clair « 8 576,08 € » : …", "Repère inconnu {{x}} : …"], True),
        (13, ["La TVA est présentée comme un choix, elle est OBLIGATOIRE (2028) : …"], False),
    ), controle_final={"rendu_pdf": [
        {"controle": "entete_trop_long", "detail": "…", "page": None},
    ]})
    _dossier("b", memoire_active=True, memoire_etude=_memoire(
        (16, ["Chiffre écrit en clair « 12 € » : …"], False),
    ))

    corps = client_admin.get(URL).json()

    assert len(corps["dossiers"]) == 2
    premier = corps["chapitres"][0]
    assert (premier["chapitre"], premier["motifs"], premier["replis"]) == (16, 3, 1)
    assert premier["passages"] == 2
    familles = {f["famille"]: f["occurrences"] for f in corps["familles_de_motifs"]}
    assert familles["Chiffre écrit en clair"] == 2
    assert corps["constats_pdf"] == [{"controle": "entete_trop_long", "occurrences": 1}]


def test_un_dossier_ancien_n_apparait_pas(client_admin: Any) -> None:
    """Contre-épreuve : sans mémoire ni contrôle final, rien à rapporter."""
    _dossier("c")
    assert client_admin.get(URL).json()["dossiers"] == []


def test_le_rapport_exige_le_jeton() -> None:
    assert Client().get(URL).status_code in (401, 403)


def test_la_famille_d_un_motif() -> None:
    assert famille_du_motif("Repère inconnu {{revenu}} : il n'existe pas") == "Repère inconnu"
    motif = "« 13 acteurs » contredit la base (11 concurrents)"
    assert famille_du_motif(motif) == "contredit la base"

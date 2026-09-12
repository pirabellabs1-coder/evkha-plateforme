"""L'instrument de mesure doit être plus honnête que ce qu'il mesure.

`mesurer_livrable` compte les trois défauts que le client a nommés le
12/09/2026 : figures non rendues, sources sans adresse, chiffres hors socle.
Il sert à répondre par des NOMBRES à la question « est-ce que l'entraînement
des prompts a servi ». Un instrument qui se flatte rendrait cette réponse
pire qu'absente.

Sa première version a menti deux fois, et les deux mensonges sont nommés dans
CLAUDE.md :

    « 17/14 rendues, 121 % »   — les figures ajoutées par la passe de
                                 complétion comptées comme demandées et
                                 obtenues (règle 2 : un motif faux est pire
                                 qu'absent)
    « 0 source extérieure »    — alors que le chapitre Sources était
                                 INTROUVABLE (règle 1 : un contrôle qui n'a
                                 rien à comparer est un échec, pas un succès)

Ces tests échouent sur cette première version.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.mesure import mesurer_les_sources
from generation.models import GenerationJob
from orders.models import Order

_AVEC_TABLEAU = """| Source | Apport | Année |
| --- | --- | --- |
| Insee, https://www.insee.fr/x | Population | 2025 |
| Numeum | Marché logiciel | 2024 |
| Données du projet | Chiffre d'affaires | 2026 |
"""

_ADRESSE_INVENTEE = """- Insee, 2025 — https://example.com/etude
- Numeum, 2024 — https://www.numeum.fr/vrai
"""


def test_un_chapitre_sources_absent_ne_rend_pas_zero() -> None:
    """LE test : zéro source et pas de chapitre ne sont pas le même constat.

    Confondre les deux ferait passer un document sans aucune traçabilité pour
    un document irréprochable — exactement à l'envers.
    """
    assert mesurer_les_sources([(1, "Analyse du marché", "Du texte.")]) is None


def test_le_chapitre_sources_se_trouve_par_son_TITRE_pas_par_le_markdown() -> None:
    """Le défaut qui a fait mentir la mesure sur QUATRE dossiers Zenitek.

    La première version redécoupait le markdown assemblé sur ses titres `#`.
    Le titre ainsi reconstruit portait son numéro — « 20. Sources » — et le
    détecteur, qui attend un titre COMMENÇANT par « sources », ne trouvait
    rien. Résultat : `sources: null` annoncé sur quatre stratégies qui avaient
    toutes leur chapitre `str.20.sources`.

    Deux découpages du même document, pas d'accord entre eux (règle 5). La
    mesure lit désormais les sections telles que `render_client_document` les
    rend — celles-là mêmes que le gate emploie.
    """
    numerote = mesurer_les_sources([(20, "20. Sources", _ADRESSE_INVENTEE)])
    assert numerote is None, (
        "un titre numéroté n'est PAS reconnu : c'est justement pourquoi la "
        "mesure ne doit pas fabriquer ses titres elle-même"
    )
    propre = mesurer_les_sources([(20, "Sources", _ADRESSE_INVENTEE)])
    assert propre is not None and propre.exterieures == 2


def test_les_sources_du_client_sont_comptees_a_part() -> None:
    """Son prévisionnel n'est pas publié et ne le sera jamais.

    Les compter comme « sans adresse » accuserait le document d'un défaut
    qu'il n'a pas — et un contrôle qui crie faux finit débranché.
    """
    mesure = mesurer_les_sources([(20, "Sources", _AVEC_TABLEAU)])
    assert mesure is not None
    assert (mesure.exterieures, mesure.du_client) == (2, 1)
    assert mesure.sans_adresse == 1, "Numeum est cité sans son adresse"


def test_une_adresse_inventee_compte_comme_une_absence() -> None:
    """C'est le défaut WAOME, et il est PIRE qu'une absence.

    Une URL en `example.com` a l'apparence du sérieux : le lecteur la suit,
    et ne trouve rien. La mesure ne doit pas la créditer.
    """
    mesure = mesurer_les_sources([(20, "Sources", _ADRESSE_INVENTEE)])
    assert mesure is not None
    exterieures, sans_adresse = mesure.exterieures, mesure.sans_adresse
    assert exterieures == 2
    assert sans_adresse == 1, "l'adresse en example.com ne vaut pas une source"


# ── La mesure doit être prenable LÀ OÙ SONT LES DOCUMENTS ────────────────────


JETON = "m" * 64


@pytest.fixture
def api(settings: Any) -> Client:
    settings.DEBUG = False
    settings.EVKHA_DASHBOARD_AUTH_DISABLED = False
    settings.EVKHA_DASHBOARD_TOKEN = JETON
    settings.EVKHA_DASHBOARD_TOKEN_PRECEDENT = ""
    return Client(HTTP_AUTHORIZATION=f"Bearer {JETON}")


@pytest.mark.django_db
def test_la_mesure_se_prend_par_l_api(api: Client) -> None:
    """Une commande de gestion tourne sur la machine du développeur.

    Les dossiers du client, eux, vivent en production : sans cette route, les
    trois nombres seraient inatteignables exactement là où ils comptent.
    """
    offre = Offer.objects.create(
        name="EM", slug="mesure-api", deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="mesure@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-mesure", customer=client, offer=offre,
    )
    dossier = GenerationJob.objects.create(
        order=commande, deliverable_type=DeliverableType.MARKET_STUDY,
    )

    reponse = api.get(f"/api/dashboard/jobs/{dossier.id}/mesure/")
    assert reponse.status_code == 200, reponse.content
    charge = json.loads(reponse.content)

    assert charge["job_id"] == str(dossier.id)
    # Ce dossier n'a ni socle ni chapitre : la mesure est IMPOSSIBLE, et elle
    # le dit au lieu de rendre des zéros qui passeraient pour un sans-faute.
    assert charge["echec"], "un dossier vide doit rendre un échec, pas des zéros"


@pytest.mark.django_db
def test_la_mesure_ne_s_ouvre_pas_sans_jeton() -> None:
    """Elle lit le contenu de dossiers clients : elle est derrière la garde."""
    reponse = Client().get("/api/dashboard/jobs/00000000-0000-0000-0000-000000000000/mesure/")
    assert reponse.status_code in (401, 403), reponse.status_code

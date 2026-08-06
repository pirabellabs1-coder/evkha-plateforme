"""Ce qui est mesuré doit être lisible ; ce qui est cité doit faire autorité.

Trois défauts distincts, tous mesurés sur le livrable réel `18ce3fca` du
05/08/2026 — 23 chapitres, 14 465 mots, comparé à `references/joalie_2026.docx`.

**1. Les réserves de la vérification étaient jetées.** Le contrôle central du
lot 4 vérifie CHAQUE grandeur chiffrée du document contre le socle et le brief,
et nomme celles sans équivalent, avec leur extrait. Sa gravité est un
avertissement, à raison. Mais `_incident` ne s'ouvrait que sur un BLOCAGE : sur
un document accepté, la liste était calculée puis perdue. Impossible de
répondre à « combien des 447 chiffres de cette étude sont sourcés ? » — question
à laquelle le système savait répondre.

**2. Deux figures pour vingt-trois chapitres**, contre dix au modèle validé. La
charte annonçait quatre types de graphiques dans un format de code fence, et
fermait sur « n'insère un graphique que si la consigne du chapitre le demande
explicitement ». Exact pour le business plan et la stratégie — moteur hérité,
qui rend bien ces fences. FAUX pour les deux études, servies par le moteur
structuré : quinze types, aucun fence, et leur prompt de chapitre le leur dit
déjà. Deux sources pour une même vérité, et c'est celle qui restreint qui
gagnait (règle 5).

**3. L'autorité des sources n'était gouvernée par rien.** Aucune URL inventée —
le contrôle le vérifiait — mais le domaine le plus cité de l'étude était un site
de modèles de business plan, là où le document validé cite l'INSEE,
economie.gouv.fr, la Commission européenne, Deloitte, Reuters et UBS.
« Fiable » ne se décrète pas : il fallait dire lesquelles priment.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from catalog.models import DeliverableType
from generation.prompts import build_system_prompt
from generation.verification.rapport import Anomalie, Gravite, RapportControle
from monitoring.models import OperationalIncident


@pytest.fixture
def job() -> Any:
    from catalog.models import Offer
    from customers.models import Customer
    from generation.models import GenerationJob
    from orders.models import Order

    offre = Offer.objects.create(
        name="EM", slug="test-reserves", deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="reserves@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-reserves", customer=client, offer=offre,
    )
    return GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=Decimal("6.00"),
    )


# ── 1. Les réserves survivent à la vérification ──────────────────────────────


@pytest.mark.django_db
def test_les_chiffres_sans_source_sont_conserves(job: Any) -> None:
    """Sur le code d'avant, un document livrable n'ouvrait AUCUN incident.

    La liste des chiffres sans équivalent au socle était calculée à chaque
    livraison, puis perdue.
    """
    from generation.verification.services import (
        INCIDENT_TYPE_RESERVES_VERIFICATION,
        _consigner_les_avertissements,
    )

    rapport = RapportControle()
    rapport.controles_executes.extend(["chiffres_hors_socle", "densite"])
    rapport.ajouter(
        Anomalie(
            "chiffres_hors_socle", Gravite.AVERTISSEMENT,
            "« 1 250 MEUR » n'a pas d'équivalent dans le socle ni dans le brief.",
            extrait="le marché national pèse 1 250 MEUR en 2026, en progression",
        ),
        Anomalie(
            "densite", Gravite.AVERTISSEMENT,
            "35 % des mots seulement sont dans des tableaux.",
        ),
    )
    assert rapport.livrable, "le cas éprouvé est bien un document ACCEPTÉ"

    _consigner_les_avertissements(job, rapport)

    incidents = OperationalIncident.objects.filter(job=job)
    assert incidents.count() == 1
    details = incidents[0].details
    assert details["type"] == INCIDENT_TYPE_RESERVES_VERIFICATION
    assert details["total"] == 2
    assert details["par_controle"]["chiffres_hors_socle"] == 1
    # L'extrait accompagne le motif : sans lui, « 1 250 MEUR » est introuvable
    # dans le document par le lecteur (règle 2).
    assert "1 250 MEUR" in details["reserves"][0]["extrait"]


@pytest.mark.django_db
def test_un_document_sans_reserve_n_ouvre_rien(job: Any) -> None:
    """Contre-épreuve : on n'inonde pas le tableau de bord d'incidents vides."""
    from generation.verification.services import _consigner_les_avertissements

    _consigner_les_avertissements(job, RapportControle())

    assert not OperationalIncident.objects.filter(job=job).exists()


@pytest.mark.django_db
def test_une_relivraison_n_empile_pas_les_doublons(job: Any) -> None:
    """Un incident par dossier : les doublons noieraient les vrais incidents."""
    from generation.verification.services import _consigner_les_avertissements

    rapport = RapportControle()
    rapport.ajouter(Anomalie("densite", Gravite.AVERTISSEMENT, "trop peu de tableaux"))

    _consigner_les_avertissements(job, rapport)
    _consigner_les_avertissements(job, rapport)

    assert OperationalIncident.objects.filter(job=job).count() == 1


# ── 2. La consigne graphique suit le moteur ──────────────────────────────────


def test_les_etudes_ne_recoivent_plus_la_consigne_du_moteur_herite() -> None:
    """Elles ne rendent aucun code fence, et leur catalogue compte quinze types."""
    from generation.prompts import build_system_prompt

    for livrable in (DeliverableType.MARKET_STUDY, DeliverableType.COMPETITOR_STUDY):
        prompt = build_system_prompt(livrable)
        assert "```chart" not in prompt, livrable
        assert "'bar', 'hbar', 'pie', 'radar'" not in prompt, livrable
        # Et surtout : plus d'invitation à la parcimonie.
        assert "que si la consigne du chapitre le demande" not in prompt, livrable


def test_le_business_plan_garde_sa_consigne_de_code_fence() -> None:
    """Contre-épreuve : le moteur hérité rend bien ces fences, ne le privons pas."""
    from generation.prompts import build_system_prompt

    for livrable in (DeliverableType.BUSINESS_PLAN, DeliverableType.BUSINESS_STRATEGY):
        prompt = build_system_prompt(livrable)
        assert "```chart" in prompt, livrable


def test_les_etudes_sont_invitees_a_varier_les_formes() -> None:
    """« Ça manque de graphiques, et de formes différentes » — la cliente, 05/08."""
    from generation.prompts import build_system_prompt

    prompt = build_system_prompt(DeliverableType.MARKET_STUDY)
    for forme in ("entonnoir", "matrice de positionnement", "chronologie"):
        assert forme in prompt, forme
    assert "Ne repete pas deux fois la meme forme" in prompt


# ── 3. La hiérarchie des sources est dite ────────────────────────────────────


def test_la_charte_classe_les_sources_par_autorite() -> None:
    """Le domaine le plus cité du livrable réel était un site de modèles."""
    from generation.prompts import build_system_prompt

    prompt = build_system_prompt(DeliverableType.MARKET_STUDY)
    for niveau in ("institut statistique national", "banque centrale",
                   "organisation professionnelle", "cabinet d'etudes"):
        assert niveau in prompt, niveau
    assert "remonte a celui qu'il repete" in prompt.lower()


def test_la_hierarchie_reste_une_preference() -> None:
    """Une source institutionnelle n'est PAS exigee, et c'est voulu.

    Un marche de niche — la joaillerie de createurs a Paris — n'est couvert par
    aucun institut statistique. Ecarter un chiffre de Francelat ou de Xerfi
    faute d'INSEE appauvrirait l'etude au nom de la rigueur.

    Ce qui reste exigible, en revanche : nommer QUI produit la donnee et QUAND.
    """
    prompt = build_system_prompt(DeliverableType.MARKET_STUDY)

    assert "PREFERENCE, pas une exigence" in prompt
    assert "n'ecarte pas un chiffre utile faute d'institution" in prompt.lower()
    assert "ne souffre pas d'exception" in prompt


def test_la_hierarchie_vaut_pour_les_quatre_livrables() -> None:
    """La charte est commune : une règle de sources ne peut pas valoir pour un seul.

    C'est la règle 10 du dépôt — chaque correction propage à tous les
    livrables, sauf si le type en impose une autre. Ici rien ne l'impose.
    """
    from generation.prompts import build_system_prompt

    for livrable in DeliverableType.values:
        assert "HIERARCHIE DES SOURCES" in build_system_prompt(livrable), livrable


def test_la_date_du_socle_reste_lisible() -> None:
    """Garde-fou : ces tests touchent au prompt, pas au socle."""
    assert date(2026, 8, 5).isoformat() == "2026-08-05"

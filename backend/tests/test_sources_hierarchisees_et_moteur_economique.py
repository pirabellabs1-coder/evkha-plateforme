"""Deux renforcements demandés le 13/08/2026, sur deux études notées 8/10.

La cliente les pose explicitement pour LES QUATRE livrables :

  1. « Toujours privilégier la source primaire et la plus récente disponible :
     organismes publics, fédérations professionnelles, statistiques
     officielles, sites officiels des concurrents, puis sources secondaires en
     complément. Il faut également vérifier que la source citée confirme
     réellement le chiffre, et pas seulement qu'elle parle du même sujet. »

  2. « La pipeline ne doit pas appliquer la même logique à un commerce local,
     un e-commerce, une agence de services ou un abonnement. Les scénarios
     doivent partir du vrai moteur économique du projet. Pour une activité
     locale, la zone de chalandise doit avoir plus de poids que la part d'un
     marché national. »
"""
from __future__ import annotations

import pytest


def _prompt(livrable: str) -> str:
    from generation.socle.prompt import construire_prompt_socle

    return construire_prompt_socle(
        deliverable_type=livrable,
        variables={"SECTEUR": "boulangerie", "PAYS": "France", "ZONE": "Lyon"},
    )


@pytest.fixture(params=[
    "market_study", "competitor_study", "business_plan", "business_strategy",
])
def livrable(request) -> str:  # type: ignore[no-untyped-def]
    """Les QUATRE : la cliente a dit « cela est valable pour tous »."""
    return str(request.param)


# ── 1. La hiérarchie des sources ────────────────────────────────────────────


def test_la_hierarchie_des_sources_est_ordonnee(livrable: str) -> None:
    """Du plus primaire au plus secondaire, et dans cet ordre.

    Une liste non ordonnée laisserait un blog valoir une statistique publique.
    """
    p = _prompt(livrable)

    assert "HIÉRARCHIE DES SOURCES" in p
    rangs = [
        "statistiques publiques",   # 1
        "fédérations",              # 2
        "OFFICIELS des acteurs",    # 3
        "études sectorielles",      # 4
        "presse et blogs",          # 5
    ]
    positions = [p.find(mot) for mot in rangs]
    assert all(pos > 0 for pos in positions), rangs
    assert positions == sorted(positions), (
        "les rangs doivent apparaître du plus primaire au plus secondaire"
    )


def test_l_annee_de_la_mesure_prime_sur_celle_de_l_article(livrable: str) -> None:
    """« La plus récente disponible » se juge sur la MESURE, pas sur la reprise.

    Un chiffre de 2023 cité par un article de 2026 reste un chiffre de 2023 :
    sans cette règle, une reprise récente d'une vieille donnée passerait pour
    de l'actualité.
    """
    p = _prompt(livrable)

    assert "l'année de la MESURE qui compte" in p
    assert "va dans `annee`" in p


def test_la_source_doit_porter_le_chiffre_lui_meme(livrable: str) -> None:
    """LE second point de la cliente, et le plus exigeant.

    Une source qui traite du même sujet sans porter la valeur transforme une
    estimation en fait publié — c'est la règle 2 du dépôt appliquée aux
    sources : un chiffre faux est pire qu'un chiffre absent.
    """
    p = _prompt(livrable)

    assert "DOIT PORTER CE CHIFFRE-LÀ" in p
    # Et l'issue est donnée, sinon la règle est inapplicable.
    assert "`estimee`" in p and "`source` reste VIDE" in p


# ── 2. Le moteur économique ─────────────────────────────────────────────────


def test_le_chiffrage_part_du_moteur_economique(livrable: str) -> None:
    """Pas d'un pourcentage d'un marché national appliqué à tout."""
    p = _prompt(livrable)

    assert "MOTEUR ÉCONOMIQUE RÉEL, PAS D'UNE PART DE MARCHÉ" in p


@pytest.mark.parametrize("moteur", [
    "zone de chalandise",     # commerce physique
    "taux de conversion",     # commerce en ligne
    "missions réalisables",   # services et conseil
    "taux d'attrition",       # abonnement
    "taux d'occupation",      # capacité d'accueil
])
def test_chaque_type_d_activite_a_son_moteur(livrable: str, moteur: str) -> None:
    """Cinq moteurs nommés, parce qu'une consigne générique ne décide rien."""
    assert moteur in _prompt(livrable), moteur


def test_la_zone_prime_sur_le_marche_national_pour_une_activite_locale(
    livrable: str,
) -> None:
    """L'exemple donné par la cliente, écrit tel qu'elle le pose.

    « Pour une activité locale, la zone de chalandise doit avoir plus de poids
    que la part d'un marché national. »
    """
    p = _prompt(livrable)

    assert "marché NATIONAL ne dit rien d'une boutique de quartier" in p


def test_une_activite_mixte_chiffre_chaque_verticale(livrable: str) -> None:
    """Un même taux appliqué à tout écrase ce qui distingue les verticales.

    Le cas est réel : une plateforme qui vend à l'unité en B2C et par
    abonnement en B2B n'a pas un moteur, elle en a deux.
    """
    p = _prompt(livrable)

    assert "chiffre chaque verticale avec SON" in p
    assert "additionne" in p


# ── 3. La règle atteint aussi les CHAPITRES, pas seulement le socle ─────────


@pytest.mark.django_db
def test_la_qualite_des_sources_atteint_les_chapitres() -> None:
    """Le socle n'est pas le seul à citer des sources.

    Les tableaux, les notes de figure et la bibliographie du dernier chapitre
    sont écrits par les CHAPITRES, à partir des sources web collectées pour
    eux. La hiérarchie posée dans le seul prompt du socle serait donc restée
    sans effet là où le lecteur voit les références — le même défaut que le
    contrôle qui exige ce qu'aucune consigne ne demande, pris par l'autre
    bout.
    """
    from decimal import Decimal

    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.chapitres.runner import _bloc_sources
    from generation.models import GenerationJob
    from orders.models import Order

    offre = Offer.objects.create(
        name="EM", slug="test-sources-chapitre",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="sources@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-sources", customer=client, offer=offre,
    )
    job = GenerationJob.objects.create(
        order=commande, deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=Decimal("8.00"),
        research_brief="## Chapitre 3\n- https://insee.fr/x — Données 2025.",
    )

    bloc = _bloc_sources(job, 3)

    assert "QUALITÉ DES SOURCES" in bloc
    assert "statistiques publiques" in bloc
    assert "les blogs en dernier" in bloc
    assert "DOIT PORTER CE QUE TU LUI FAIS DIRE" in bloc


@pytest.mark.django_db
def test_un_chapitre_sans_source_collectee_reste_prudent() -> None:
    """CONTRE-ÉPREUVE : sans matière, la consigne ne doit pas inviter à citer.

    Le repli existant interdit déjà d'inventer une URL. Il ne faut pas que la
    hiérarchie, ajoutée pour élever la qualité, se lise comme une invitation à
    trouver une source à tout prix.
    """
    from decimal import Decimal

    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.chapitres.runner import _bloc_sources
    from generation.models import GenerationJob
    from orders.models import Order

    offre = Offer.objects.create(
        name="EM", slug="test-sources-vide",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="vide@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-vide", customer=client, offer=offre,
    )
    job = GenerationJob.objects.create(
        order=commande, deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=Decimal("8.00"), research_brief="",
    )

    bloc = _bloc_sources(job, 3)

    assert "N'invente" in bloc
    assert "QUALITÉ DES SOURCES" not in bloc

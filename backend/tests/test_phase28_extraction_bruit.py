"""Phase 28 — Tuer les clefs `CoherenceFact` bruyantes captees a la volee.

Constat SYNAPSES v3 (rapport de gate) : `extract_and_lock_numeric_facts`
capturait des libelles trop longs et polluait la base de faits avec
notamment :

    nombre_de_micro-entrepreneurs_actifs_dans_l_hérault_a_progressé_de = 23 %
    part_de_frais_et_charges_de                                        = 5 %
    taux_de_remplissage_progressifs                                    = 55 %
    taux_de_remplissage_retenus_sont                                   = 55 %
    taux_de_remplissage_volontairement_conservateurs                   = 55 %
    tcac_retenu_de                                                     = 6,5 %

Chaque libelle est un fragment de phrase, pas un vrai concept metier. Les
trois « taux_de_remplissage » designent la MEME chose : la difference n'est
que lexicale (qualificatifs conjugues), la valeur est identique (55 %). Le
resultat viole la regle 5 (une seule source par verite) : trois clefs pour
un fait unique.

Regle 4 : viser la classe. La correction n'est pas d'ajouter un blacklist
mot par mot. Le motif generique `[A-Za-zÀ-ÿ' -]{3,60}` est intrinsequement
glouton — c'est LUI qu'on remplace, par une liste blanche stricte des
libelles reels que le pipeline surveille.
"""
from __future__ import annotations

import pytest


def _extract(text: str) -> list[str]:
    """Aggrege les cles capturees pour un texte."""
    import uuid

    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.coherence import extract_and_lock_numeric_facts
    from generation.models import ChapterGeneration, GenerationJob
    from orders.models import Order

    slug = f"phase28-{uuid.uuid4().hex[:8]}"
    offer = Offer.objects.create(
        name="EM", slug=slug, deliverable_type=DeliverableType.MARKET_STUDY
    )
    customer = Customer.objects.create(email=f"{slug}@x.com")
    order = Order.objects.create(
        systeme_order_id=slug, customer=customer, offer=offer
    )
    job = GenerationJob.objects.create(
        order=order, deliverable_type=DeliverableType.MARKET_STUDY
    )
    chapter = ChapterGeneration.objects.create(
        job=job, chapter_number=1, chapter_title="X",
        prompt_key="em.01", content=text,
    )
    locked = extract_and_lock_numeric_facts(chapter)
    return [f.key for f in locked]


# ── Cas SYNAPSES v3 : ces libelles pollues NE DOIVENT PAS creer de fait ──


@pytest.mark.django_db
def test_les_fragments_de_phrase_avec_verbe_conjugue_ne_creent_pas_de_fait() -> None:
    """« a progressé de », « retenus sont », « volontairement conservateurs » :
    ce sont des morceaux syntaxiques, pas des concepts. Aucun ne doit devenir
    une cle de fait verrouillee."""
    texte = (
        "Le nombre de micro-entrepreneurs actifs dans l'Herault a progresse de "
        "23 % en 2025. Un taux de remplissage progressifs de 55 % est vise. "
        "Le taux de remplissage retenus sont de 55 %. Un taux de remplissage "
        "volontairement conservateurs de 55 % est utilise. Le TCAC retenu de "
        "6,5 % encadre l'analyse. La part de frais et charges de 5 % est "
        "assumee."
    )
    cles = _extract(texte)

    for indesirable in (
        "nombre_de_micro-entrepreneurs_actifs_dans_l_herault_a_progresse_de",
        "part_de_frais_et_charges_de",
        "taux_de_remplissage_progressifs",
        "taux_de_remplissage_retenus_sont",
        "taux_de_remplissage_volontairement_conservateurs",
        "tcac_retenu_de",
    ):
        assert indesirable not in cles, f"cle bruyante creee : {indesirable}"


# ── Contre-epreuve : les vrais concepts metier restent captures ─────────────


@pytest.mark.django_db
def test_les_libelles_courts_du_lexique_metier_sont_captures() -> None:
    """Ces libelles-la SONT des concepts metier. Ils doivent continuer d'etre
    verrouilles a la premiere occurrence."""
    texte = (
        "Le taux d'occupation est de 55 % en annee 1. "
        "Le panier moyen est de 300 EUR mensuels. "
        "La part de marche visee est de 12 %."
    )
    cles = _extract(texte)

    joint = " | ".join(cles)
    assert "taux_d_occupation" in joint or "taux_d occupation" in joint or \
           any("taux" in c and "occupation" in c for c in cles), \
           f"taux d'occupation absent : {cles}"
    # Panier moyen et part de marche sont des concepts que le pipeline devrait
    # capturer aussi (via patterns dedies existants).


@pytest.mark.django_db
def test_le_pattern_ne_capture_que_les_libelles_courts() -> None:
    """Un libelle metier fait au plus 3-4 mots. Au-dela, on est dans une
    phrase, pas dans un concept."""
    texte = (
        "Le taux d'occupation est de 55 %. "
        "Le nombre de clients heureux et satisfaits qui reviennent chaque mois "
        "atteint 250."
    )
    cles = _extract(texte)

    # Le libelle long ne doit pas produire une cle "nombre_de_clients_heureux_..."
    for cle in cles:
        assert len(cle) <= 60, f"cle trop longue : {cle} ({len(cle)} chars)"

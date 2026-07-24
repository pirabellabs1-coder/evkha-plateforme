"""Phase 29 — Adaptation des consignes par livrable.

Reecrit le 24/07/2026 apres adoption du manuel Evangeline. Les regles WAOME
de juillet 2026 (fourchette sourcee avec mediane annoncee, 5 registres
methodologiques imposes en preambule) ont ete EXPLICITEMENT rejetees par
Evangeline dans le manuel EM du 24/07/2026 : elles polluaient le texte
livre (les regles etaient recopiees mot-pour-mot).

Nouvelles regles verifiees ici :
- BP / EC / STR : chiffre unique, jamais de fourchette (regle originale
  conservee — le manuel ne les couvre pas).
- EM (manuel §3) : voix EVKHA verbatim, fourchettes serrees autorisees,
  taux/% en valeur fixe unique, PAS de mediane forcee, PAS de registres
  methodologiques imposes.
"""
from __future__ import annotations

from catalog.models import DeliverableType
from generation.prompts import build_system_prompt

# ── 1. Fourchettes : strict en BP/EC/STR, regle Evangeline en EM ───────────


def test_le_prompt_bp_interdit_toute_fourchette() -> None:
    """Un BP bancaire ne cite JAMAIS de fourchette. Chiffre unique."""
    prompt = build_system_prompt(DeliverableType.BUSINESS_PLAN, country="France")

    assert "recopie jamais" in prompt.lower() or "trancher" in prompt.lower()
    assert "chiffre unique" in prompt.lower() or "valeur unique" in prompt.lower()


def test_le_prompt_em_pose_la_regle_evangeline_fourchettes_serrees() -> None:
    """Manuel Evangeline 24/07/2026 §3 : les fourchettes SERREES sont
    autorisees (« entre 1 000 et 1 400 »), les taux/pourcentages sont
    TOUJOURS en valeur fixe unique. C'est la regle qui remplace l'ancienne
    « mediane annoncee obligatoire » explicitement rejetee par Evangeline."""
    prompt = build_system_prompt(DeliverableType.MARKET_STUDY, country="France")
    lower = prompt.lower()

    assert "fourchette" in lower
    assert "serree" in lower or "coherente" in lower
    # Taux/% en valeur fixe unique
    assert "valeur fixe" in lower or "valeur unique" in lower
    assert "taux" in lower or "pourcentage" in lower


def test_le_prompt_em_ne_force_plus_la_mediane_annoncee() -> None:
    """Manuel 24/07 : la formule « mediane retenue X » est ELLE-MEME la
    cause du recrachage observe sur WAOME v4. Elle a ete supprimee du
    charter EM. Contre-epreuve : le prompt n'impose plus cette formulation."""
    prompt = build_system_prompt(DeliverableType.MARKET_STUDY, country="France")
    lower = prompt.lower()

    assert "mediane retenue" not in lower
    assert "annonce la mediane" not in lower


def test_le_prompt_ec_interdit_toute_fourchette() -> None:
    """L'etude de concurrence chiffre les parts de marche : chiffre unique."""
    prompt = build_system_prompt(DeliverableType.COMPETITOR_STUDY, country="France")

    assert "chiffre unique" in prompt.lower() or "valeur unique" in prompt.lower()


def test_le_prompt_str_interdit_toute_fourchette() -> None:
    """Une strategie business tranche. Aucun arbitrage n'est une fourchette."""
    prompt = build_system_prompt(DeliverableType.BUSINESS_STRATEGY, country="France")

    assert "chiffre unique" in prompt.lower() or "valeur unique" in prompt.lower()


# ── 2. Voix EVKHA (manuel §3) — EM ──────────────────────────────────────────


def test_le_prompt_em_pose_la_voix_evkha_verbatim_du_manuel() -> None:
    """Le charter EM reprend verbatim les points-cles §3 du manuel :
    ton professionnel/neutre/credible/fluide/accessible, pas de « tu/vous »,
    pas d'emoji, pas de ton vendeur, pas de vocabulaire pipeline."""
    prompt = build_system_prompt(DeliverableType.MARKET_STUDY, country="France")
    lower = prompt.lower()

    for expected in (
        "professionnel",
        "neutre",
        "fluide",
        "accessible",
        "novice",
        "emoji",
        "ton vendeur",
        "pipeline",
    ):
        assert expected in lower, f"element de voix EVKHA absent : {expected!r}"


def test_le_prompt_em_ne_contient_plus_les_registres_methodologiques() -> None:
    """Contre-epreuve : les 5 registres methodologiques WAOME (faits
    documentes, estimations sectorielles, etc.) ont ete SUPPRIMES du
    charter EM le 24/07/2026 avec l'adoption du manuel Evangeline. Ils
    ne doivent plus apparaitre dans le prompt EM."""
    prompt = build_system_prompt(DeliverableType.MARKET_STUDY, country="France")
    lower = prompt.lower()

    # Ces libelles etaient injectes verbatim par l'ancien code.
    for absent in (
        "registres methodologiques",
        "ambitions commerciales",
    ):
        assert absent not in lower, f"element WAOME encore present : {absent!r}"


# ── 3. Contre-epreuves : le rôle EM est aligné manuel §3 ────────────────────


def test_le_role_em_precise_specialiste_secteur_zone() -> None:
    """Manuel §3 : « analyste senior en etude de marche, spécialiste du
    secteur et de la zone étudiés »."""
    prompt = build_system_prompt(DeliverableType.MARKET_STUDY, country="France")
    lower = prompt.lower()

    assert "analyste senior" in lower
    assert "specialiste" in lower
    assert "secteur" in lower
    assert "zone" in lower


def test_le_prompt_bp_ne_contient_pas_les_regles_specifiques_em() -> None:
    """Contre-epreuve : les elements EM (voix EVKHA verbatim, fourchettes
    serrees autorisees) sont specifiques a l'analyse externe. Un BP a sa
    propre logique (etat chiffre CLIENT strict)."""
    prompt = build_system_prompt(DeliverableType.BUSINESS_PLAN, country="France")
    lower = prompt.lower()

    # Le BP ne doit pas ouvrir la porte aux fourchettes serrees.
    assert "fourchette" in lower  # (l'interdiction est mentionnee)
    # Mais il doit trancher, pas autoriser les fourchettes serrees.
    assert "recopie jamais" in lower or "trancher" in lower

"""Phase 29 — Adaptation des consignes par livrable, tiree de WAOME (20/07/2026).

Evangeline a envoye une etude de marche de reference (WAOME Studio) qui a
mis en lumiere deux ecarts entre notre consigne actuelle et son standard :

  1. La regle « JAMAIS de fourchette » est trop stricte pour l'EM. WAOME
     ecrit systematiquement « TAM 130-200 M€, mediane retenue 150 M€ » :
     fourchette SOURCEE + valeur retenue. C'est le format d'une etude
     analytique honnete. Le meme format est INTERDIT dans un BP bancaire
     qui exige un chiffre unique.

  2. Elle distingue en preambule cinq REGISTRES METHODOLOGIQUES : faits
     documentes, estimations sectorielles, hypotheses projet, ambitions
     commerciales, elements a tester. Sans ce cadre, l'IA melange tout et
     un banquier ne sait plus ce qu'il lit.

Regle 4 (viser la classe) : la consigne fourchettes n'est plus universelle,
elle est adaptee au TYPE de livrable. La correction WAOME propage aux
prochaines etudes de marche, pas seulement a WAOME.

Regle 5 (source unique) : les 5 registres sont exportes comme constante,
importee par prompt et documentation.
"""
from __future__ import annotations

from catalog.models import DeliverableType
from generation.prompts import build_system_prompt

# ── 1. Fourchettes : strict en BP/EC, permis SOURCÉ en EM ──────────────────


def test_le_prompt_bp_interdit_toute_fourchette() -> None:
    """Un BP bancaire ne cite JAMAIS de fourchette. Chiffre unique
    obligatoire — c'est la consigne d'origine."""
    prompt = build_system_prompt(DeliverableType.BUSINESS_PLAN, country="France")

    # La regle « fourchettes du brief » reste presente et interdit la recopie
    assert "recopie jamais" in prompt.lower() or "trancher" in prompt.lower()
    assert "chiffre unique" in prompt.lower() or "valeur unique" in prompt.lower()


def test_le_prompt_em_autorise_la_fourchette_sourcee_avec_mediane() -> None:
    """Une etude de marche cite les intervalles publies (« TAM 130-200 M€ »)
    a CONDITION d'annoncer la mediane retenue. Sans cette adaptation, le
    modele ne pourrait pas ecrire du WAOME-like."""
    prompt = build_system_prompt(DeliverableType.MARKET_STUDY, country="France")

    assert "mediane" in prompt.lower()
    assert "fourchette" in prompt.lower()
    # La fourchette pure est interdite ; c'est la MEDIANE annoncee qui la
    # rend acceptable dans une EM.
    assert any(x in prompt.lower() for x in ("retenue", "annoncee", "declaree"))


def test_le_prompt_ec_interdit_toute_fourchette() -> None:
    """L'etude de concurrence chiffre les parts de marche : chiffre unique."""
    prompt = build_system_prompt(DeliverableType.COMPETITOR_STUDY, country="France")

    assert "chiffre unique" in prompt.lower() or "valeur unique" in prompt.lower()


def test_le_prompt_str_interdit_toute_fourchette() -> None:
    """Une strategie business tranche. Aucun arbitrage n'est une fourchette."""
    prompt = build_system_prompt(DeliverableType.BUSINESS_STRATEGY, country="France")

    assert "chiffre unique" in prompt.lower() or "valeur unique" in prompt.lower()


# ── 2. Registres methodologiques — EM uniquement ────────────────────────────


def test_le_prompt_em_pose_les_cinq_registres_methodologiques() -> None:
    """Preambule WAOME : faits documentes, estimations sectorielles,
    hypotheses projet, ambitions commerciales, elements a tester. Sans ce
    cadre, l'IA melange sources verifiees et projections calibrees."""
    prompt = build_system_prompt(DeliverableType.MARKET_STUDY, country="France")

    for registre in (
        "faits documentes",
        "estimations sectorielles",
        "hypotheses",
        "ambitions",
        "elements a tester",
    ):
        assert registre in prompt.lower(), f"registre absent : {registre!r}"


def test_les_5_registres_sont_exportes_comme_constante_unique() -> None:
    """Regle 5 : une seule source. Le prompt IMPORTE la liste, ne la recopie
    pas. Si demain on modifie le libelle d'un registre, la modification se
    propage automatiquement."""
    from generation.checks_evangeline import REGISTRES_METHODO

    prompt = build_system_prompt(DeliverableType.MARKET_STUDY, country="France")
    for _cle, (intitule, _description) in REGISTRES_METHODO.items():
        assert intitule.lower() in prompt.lower(), (
            f"registre {intitule!r} non injecte au prompt"
        )


# ── 3. Contre-epreuves : les registres ne s'appliquent qu'a l'EM ───────────


def test_le_prompt_bp_ne_contient_pas_les_registres_em() -> None:
    """Contre-epreuve : les registres sont specifiques a l'analyse externe
    d'une EM. Un BP a sa propre logique (etat chiffre CLIENT / previsionnel /
    hypotheses assumees) — polluer le prompt BP avec les registres EM
    embrouillerait le modele."""
    prompt = build_system_prompt(DeliverableType.BUSINESS_PLAN, country="France")

    assert "faits documentes" not in prompt.lower()

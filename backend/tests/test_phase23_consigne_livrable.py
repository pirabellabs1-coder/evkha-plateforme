"""Phase 23 — La consigne specifique par livrable est bien injectee au prompt.

Suite de la relecture d'Evangeline (juillet 2026), fiches 2 et 4. Deux consignes
ont ete ajoutees a `build_system_prompt` :

- EC : exactement 8 concurrents directs et 3 indirects, sous les sous-sections
  qu'utilisera le gate pour les compter.
- STR : les 4 piliers de la strategie, dans l'ordre et avec leur objectif.

L'enjeu, cote loop : le prompt et le check doivent tirer leurs libelles de la
MEME source (regle 5 du CLAUDE.md). Sinon le check devient un miroir du prompt
et ne verifie plus qu'il produit ce qu'il faut, il verifie qu'il produit ce
qu'il produit. C'est ici que les regles 5 et 9 (contrôle et réparation qui ne
jugent pas sur la meme evidence) se recoupent : le check compte les puces, le
prompt exige les puces, et les DEUX exigent EXACTEMENT le meme nombre — pris a
la meme constante.
"""
from __future__ import annotations

from catalog.models import DeliverableType
from generation.checks_evangeline import (
    ATTENDUS_CONCURRENTS,
    PILIERS_STRATEGIE,
    verifier_concurrents_dans_ec,
    verifier_piliers_strategie,
)
from generation.prompts import build_system_prompt

# ── 1. EC : la consigne 8 + 3 est bien injectee au prompt ────────────────────


def test_le_prompt_ec_impose_les_8_concurrents_directs() -> None:
    """Sans cette consigne, le modele redige 4 ou 12 concurrents au hasard.
    AVANT ce commit : la chaine « 8 concurrents directs » etait absente du prompt."""
    prompt = build_system_prompt(DeliverableType.COMPETITOR_STUDY)

    assert "8 concurrents directs" in prompt
    assert "3 concurrents indirects" in prompt


def test_le_nombre_de_concurrents_du_prompt_vient_de_la_source_du_check() -> None:
    """Regle 5 : une SEULE source de verite.

    Si demain la cliente passe a 10 directs, la modification d'une seule
    constante (`ATTENDUS_CONCURRENTS`) doit propager AU prompt ET au check.
    Ce test verrouille l'importation.
    """
    prompt = build_system_prompt(DeliverableType.COMPETITOR_STUDY)

    assert str(ATTENDUS_CONCURRENTS["directs"]) + " concurrents directs" in prompt
    assert str(ATTENDUS_CONCURRENTS["indirects"]) + " concurrents indirects" in prompt


def test_le_prompt_ec_impose_les_sous_sections_que_le_check_recherche() -> None:
    """Regle 9 : le prompt et le check ne doivent pas juger sur la meme
    evidence, MAIS ils doivent partager la meme convention structurelle.
    Sinon le prompt produit une prose que le check ne peut pas compter.

    Un `verifier_concurrents_dans_ec` sur un output conforme a la consigne
    doit sortir 0 divergence. C'est la contre-epreuve la plus utile."""
    prompt = build_system_prompt(DeliverableType.COMPETITOR_STUDY)

    assert "## Concurrents directs" in prompt
    assert "## Concurrents indirects" in prompt

    output_conforme = (
        "## Concurrents directs\n\n"
        + "\n".join(
            f"- Acteur {i} — analyse."
            for i in range(1, ATTENDUS_CONCURRENTS["directs"] + 1)
        )
        + "\n\n## Concurrents indirects\n\n"
        + "\n".join(
            f"- Substitut {i} — analyse."
            for i in range(1, ATTENDUS_CONCURRENTS["indirects"] + 1)
        )
    )

    assert verifier_concurrents_dans_ec([(1, output_conforme)]) == []


# ── 2. STR : les 4 piliers sont poses dans le prompt ─────────────────────────


def test_le_prompt_strategie_pose_les_4_piliers_verbatim() -> None:
    """Fiche 4 : les 4 piliers sont TOUJOURS traites. Sans consigne, l'IA
    invente sa propre grille."""
    prompt = build_system_prompt(DeliverableType.BUSINESS_STRATEGY)

    for _cle, (intitule, _motif) in PILIERS_STRATEGIE.items():
        assert intitule in prompt, f"{intitule} absent du prompt strategie"


def test_le_prompt_strategie_impose_la_vision_et_le_plan_d_action() -> None:
    """Fiche 4 : « la stratégie donne une vision stratégique + un plan
    d'action opérationnel »."""
    prompt = build_system_prompt(DeliverableType.BUSINESS_STRATEGY)

    assert "vision strategique" in prompt.lower()
    assert "plan d'action operationnel" in prompt.lower()


def test_un_output_strategie_pose_les_4_piliers_apres_ce_prompt() -> None:
    """Contre-epreuve : un document qui pose les 4 piliers verbatim passe le
    check. La forme minimale qui matche les regex de `verifier_piliers`.

    Ce test verrouille le pacte : le prompt exige les libelles, le check les
    trouve, meme convention, MEME source (regle 5)."""
    corpus = "\n\n".join(
        f"## {intitule} — {motif_intro}\nDeveloppement du pilier."
        for _cle, (intitule, motif_intro) in [
            ("positionnement",  ("Pilier 1", "Positionnement & Specialisation")),
            ("offre",           ("Pilier 2", "Structuration de l'offre")),
            ("editorial",       ("Pilier 3", "Planning editorial")),
            ("tarification",    ("Pilier 4", "Analyse de la tarification")),
        ]
    )

    assert verifier_piliers_strategie(corpus) == []


# ── 3. Contre-epreuves : pas de bruit sur les autres livrables ──────────────


def test_le_prompt_bp_ne_contient_pas_la_consigne_concurrents() -> None:
    """Contre-epreuve : la consigne 8+3 concurrents est SPECIFIQUE a l'EC.
    Un business plan n'a pas de « ## Concurrents directs » avec 8 puces."""
    prompt = build_system_prompt(DeliverableType.BUSINESS_PLAN)

    assert "8 concurrents directs" not in prompt


def test_le_prompt_em_ne_contient_pas_la_consigne_piliers() -> None:
    """Contre-epreuve : les 4 piliers ne s'appliquent qu'a la strategie."""
    prompt = build_system_prompt(DeliverableType.MARKET_STUDY)

    assert "PILIER 1" not in prompt
    assert "PILIER 4" not in prompt

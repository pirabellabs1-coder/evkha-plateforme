"""Phase 30 — Aligner le check fourchettes sur la nouvelle regle EM (WAOME).

Constate sur EM WAOME (job 49953f14, 20/07/2026) : 68 fourchettes signalees
comme interdites, alors que TOUTES sont conformes au format EM autorise
(« estime entre 36 et 45 milliards, mediane retenue 40 milliards »). Le
prompt a bien ete adapte (phase 29), mais le CHECK GATE conserve sa regle
stricte. Anti-pattern judge-alignment (methode Bles Software) : le juge
n'est plus aligne sur la vraie regle metier.

Regle 9 du CLAUDE.md : le controle et sa reparation ne doivent pas juger
sur la meme evidence. La MEME logique s'applique ici : la regle prompt et
la regle check doivent partir de la meme source. Sinon le loop tourne mais
compte des faux positifs, ce qui remonte comme du bruit dans le journal.

Fix : `_check_fourchettes` reçoit le type de livrable. Pour EM, une
fourchette suivie (dans la meme phrase ou les 100 caracteres suivants)
d'une mention de « mediane retenue X » ou « valeur retenue X » est
consideree LEGITIME. Pour BP/EC/STR, on garde le strict.

Regle 5 (source unique) : le format « mediane retenue » vient d'une seule
regex partagee, importee par le check et documentee dans la consigne
prompt.
"""
from __future__ import annotations

import pytest

from catalog.models import DeliverableType
from generation.checks_evangeline import detecter_fourchettes

# ── EM : la fourchette suivie de « mediane retenue X » est acceptee ────────


@pytest.mark.parametrize(
    "texte",
    [
        # Exemples reels extraits du doc EM WAOME (job 49953f14).
        "estime entre 36 et 45 milliards de dollars en 2024, avec une "
        "mediane retenue a 40 milliards de dollars.",
        "fourchette estimee entre 1,8 et 2,6 milliards d'euros en 2025, "
        "mediane retenue 2,1 milliards d'euros.",
        "estimee a 15-20 % du marche global, mediane retenue 17 %.",
        "estimee a 8-10 %, mediane retenue 9 %.",
    ],
)
def test_les_fourchettes_sourcees_avec_mediane_annoncee_passent_en_em(
    texte: str,
) -> None:
    """Format WAOME : la fourchette est LEGITIME si la mediane retenue est
    annoncee dans la meme phrase (ou juste apres). C'est le registre
    « estimations sectorielles » d'Evangeline."""
    trouvees = detecter_fourchettes(
        chapitre_numero=1,
        texte=texte,
        deliverable_type=DeliverableType.MARKET_STUDY,
    )

    assert trouvees == [], (
        f"faux positif : la fourchette suivie de « mediane retenue » "
        f"aurait du etre acceptee. Detectees : {[t.extrait for t in trouvees]}"
    )


def test_une_fourchette_nue_reste_interdite_en_em() -> None:
    """Contre-epreuve : sans annonce de mediane, la fourchette reste un
    defaut meme en EM. Le lecteur ne saurait pas quelle valeur retenir
    pour la suite."""
    texte = (
        "Le marche europeen represente entre 20 et 40 % du marche mondial. "
        "Cette large amplitude reflete la difficulte a mesurer."
    )

    trouvees = detecter_fourchettes(
        chapitre_numero=1,
        texte=texte,
        deliverable_type=DeliverableType.MARKET_STUDY,
    )

    assert len(trouvees) == 1
    assert "20" in trouvees[0].extrait and "40" in trouvees[0].extrait


def test_la_fourchette_reste_interdite_en_bp() -> None:
    """Un BP bancaire n'accepte JAMAIS de fourchette, meme avec mediane
    annoncee. Chiffre unique obligatoire — c'est la regle SYNAPSES."""
    texte = (
        "L'investissement est estime entre 180 et 280 kEUR, mediane retenue "
        "230 kEUR."
    )

    trouvees = detecter_fourchettes(
        chapitre_numero=1,
        texte=texte,
        deliverable_type=DeliverableType.BUSINESS_PLAN,
    )

    assert len(trouvees) == 1, (
        "un BP ne doit JAMAIS accepter de fourchette, meme sourcee"
    )


def test_la_fourchette_reste_interdite_en_ec() -> None:
    """Meme regle pour l'etude de concurrence : parts de marche uniques."""
    texte = "Le concurrent detient une part de marche entre 15 et 25 %, mediane 20 %."

    trouvees = detecter_fourchettes(
        chapitre_numero=1,
        texte=texte,
        deliverable_type=DeliverableType.COMPETITOR_STUDY,
    )

    assert len(trouvees) == 1


def test_la_fourchette_reste_interdite_en_str() -> None:
    """Strategie business : chaque arbitrage tranche. Aucune fourchette."""
    texte = (
        "L'ambition de croissance est fixee entre 20 et 30 % annuel, "
        "mediane retenue 25 %."
    )

    trouvees = detecter_fourchettes(
        chapitre_numero=1,
        texte=texte,
        deliverable_type=DeliverableType.BUSINESS_STRATEGY,
    )

    assert len(trouvees) == 1


# ── Contre-epreuve : les fausses « medianes » ne trompent pas ──────────────


def test_le_mot_mediane_ailleurs_dans_le_paragraphe_ne_suffit_pas() -> None:
    """La mediane doit etre annoncee POUR la fourchette, pas juste dans le
    voisinage. Un paragraphe qui parle d'une autre mediane 300 mots plus
    loin ne legitime pas la fourchette."""
    texte = (
        "Le marche est estime entre 20 et 40 %. " +
        "Autre paragraphe sur les acteurs. " * 20 +
        "Enfin, la mediane retenue de l'echantillon est 22 %."
    )

    trouvees = detecter_fourchettes(
        chapitre_numero=1,
        texte=texte,
        deliverable_type=DeliverableType.MARKET_STUDY,
    )

    assert len(trouvees) == 1, (
        "la mediane doit etre annoncee A PROXIMITE de la fourchette"
    )


def test_la_signature_appelle_le_type_de_livrable() -> None:
    """La signature de `detecter_fourchettes` accepte desormais un parametre
    `deliverable_type` optionnel. Sans lui, comportement par defaut strict
    (compatible avec les appels existants sans regression)."""
    texte = "Estime entre 100 et 200 EUR, mediane 150 EUR."

    # Sans deliverable_type : mode strict (retrocompat)
    strict = detecter_fourchettes(chapitre_numero=1, texte=texte)
    assert len(strict) == 1

    # Avec EM : mediane annoncee, la fourchette passe
    em = detecter_fourchettes(
        chapitre_numero=1, texte=texte,
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    assert em == []

"""Un pourcentage que le document CALCULE doit tomber juste.

Cliente, 11/08/2026 : « bien vérifier la cohérence des chiffres… il y a des
erreurs dans les calculs et pourcentages ». Une extrapolation est légitime —
le manuel l'autorise et elle est souvent nécessaire — mais une extrapolation
FAUSSE ruine la crédibilité de tout le document : un pourcentage qui ne tombe
pas juste se repère au premier coup d'œil et fait douter de chaque chiffre.

## Ce que le contrôle ne devine pas

Uniquement les calculs que le document POSE lui-même, dans l'ordre part,
tout, résultat — la forme exacte que la consigne demande d'écrire. Un
pourcentage isolé n'est pas jugé : il n'y a rien à quoi le comparer, et
inventer l'opération produirait des motifs faux (règle 2).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from generation.verification.controles import controler_les_calculs_annonces
from generation.verification.lecture import DocumentLu


def _document(*phrases: str) -> DocumentLu:
    return DocumentLu(chemin=Path("memoire.docx"), paragraphes=list(phrases))


# ── Les calculs justes traversent ────────────────────────────────────────────


@pytest.mark.parametrize(
    "phrase",
    [
        "Le projet vise 130 000 € sur 1,36 Md€, soit 0,0096 % du marché.",
        "L'objectif est de 25 M€ sur 500 M€, soit 5 % du total.",
        "Nous retenons 2 000 sur 40 000, soit 5 % des acheteurs.",
        # Arrondi éditorial sur le résultat : 0,00956 écrit 0,0096.
        "Un chiffre d'affaires de 130 000 € sur 1,36 Md€, soit 0,0096 %.",
        # Arrondi sur l'opérande : 12,4 % réel écrit 12 %.
        "Le segment pèse 62 M€ sur 500 M€, soit 12 % du marché.",
    ],
)
def test_un_calcul_juste_ne_produit_aucune_reserve(phrase: str) -> None:
    assert controler_les_calculs_annonces(_document(phrase)) == []


# ── Les calculs faux sont nommés ─────────────────────────────────────────────


def test_un_pourcentage_faux_est_signale() -> None:
    """Le défaut exact que la cliente a relevé dans un document livré."""
    anomalies = controler_les_calculs_annonces(
        _document("Le projet vise 130 000 € sur 1,36 Md€, soit 9,6 % du marché.")
    )

    assert len(anomalies) == 1
    assert anomalies[0].controle == "calcul_faux"
    assert "9,6" in anomalies[0].detail or "9.6" in anomalies[0].detail
    # Le motif dit ce que le calcul donne VRAIMENT : sans cela, il faut
    # reprendre la division à la main pour savoir quoi corriger (règle 2).
    assert "0.0095" in anomalies[0].detail


def test_une_part_qui_depasse_le_tout_est_signalee() -> None:
    anomalies = controler_les_calculs_annonces(
        _document("Ce segment pèse 600 M€ sur 500 M€, soit 12 % du marché.")
    )

    assert len(anomalies) == 1


def test_les_echelles_sont_ramenees_avant_de_diviser() -> None:
    """« 130 000 € sur 1,36 Md€ » : sans conversion, le rapport est absurde."""
    justes = controler_les_calculs_annonces(
        _document("Un SOM de 0,13 M€ sur 1,36 Md€, soit 0,0096 %.")
    )

    assert justes == []


# ── Ce qui n'est PAS jugé ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "phrase",
    [
        "Le marché progresse de 3,4 % par an depuis 2022.",
        "Trois acteurs détiennent 45 % du marché à eux seuls.",
        "La marge brute atteint 62 % sur les abonnements.",
        "Le taux de conversion s'établit à 2,8 % en moyenne.",
    ],
)
def test_un_pourcentage_isole_n_est_pas_juge(phrase: str) -> None:
    """CONTRE-ÉPREUVE : sans opérandes écrits, il n'y a rien à vérifier.

    Deviner l'opération — chercher deux nombres ailleurs dans le paragraphe et
    supposer qu'ils forment le calcul — produirait des motifs faux en série.
    Un contrôle qui invente ce qu'il vérifie est pire qu'absent.
    """
    assert controler_les_calculs_annonces(_document(phrase)) == []


def test_le_meme_calcul_faux_n_est_signale_qu_une_fois() -> None:
    """Un rapport à trente réserves identiques noie celle qui compte."""
    phrase = "Le projet vise 130 000 € sur 1,36 Md€, soit 9,6 %."
    anomalies = controler_les_calculs_annonces(_document(phrase, phrase, phrase))

    assert len(anomalies) == 1


def test_la_passe_execute_le_controle() -> None:
    """La cause, pas seulement la fonction : elle pourrait n'être appelée nulle
    part — c'est le défaut de la règle 8, mesuré six fois sur ce projet."""
    from pathlib import Path as _P

    source = (
        _P(__file__).resolve().parents[1]
        / "generation" / "verification" / "services.py"
    ).read_text(encoding="utf-8")

    assert "controler_les_calculs_annonces" in source
    assert '"calculs_annonces"' in source

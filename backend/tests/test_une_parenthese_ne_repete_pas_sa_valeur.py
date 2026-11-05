"""« Retenir 0,1 % de 188 M€ (188 M€), soit 188 000 € ».

## La coquille

Audit de la cliente du 04/11/2026 sur l'étude SUN TZU, point 6 : « La même
page comporte d'ailleurs une coquille importante : "Retenir 0,1 % de 188 M€
(188 M€), soit 188 000 €". La valeur entre parenthèses est erronée. »

## L'arithmétique, elle, est JUSTE

0,1 % de 188 M€ font bien 188 000 €. `arithmetique.verifier` a donc raison de
ne rien dire — vérifié : il ne signale rien sur cette phrase, ni sur ses
variantes. Le défaut n'est pas un calcul faux, c'est une parenthèse qui redit
sa propre base.

C'est important parce que cela désigne le bon correctif : rien à faire
recalculer, rien à arbitrer, donc rien à faire réécrire au modèle.

## Pourquoi elle se RÉPARE au lieu de se signaler

Cette forme n'a aucun usage légitime, et ce fichier le prouve par ses
contre-épreuves : une parenthèse qui DATE la valeur, qui en donne la SOURCE,
qui la ramène à une AUTRE BASE, ou qui porte une autre valeur, apporte
quelque chose. Répéter la valeur à l'identique n'apporte rien.

L'égalité EXACTE des deux écritures est donc le critère, et il ne laisse
aucune place à l'arbitrage. Une réparation déterministe ne coûte rien — et
c'est ce qui décide, parce que la réparation payante, elle, n'a pas lieu :
mesuré le 05/11/2026 sur l'étude `25be2162`, la relecture finale a réclamé
0,80 € (`MARGE_DE_BUDGET + RESERVE_DU_REJEU`), n'a trouvé que 0,50 €, et n'a
réécrit AUCUN chapitre.

Ces tests échouent sur le code d'avant : `reparer_texte` laissait la
parenthèse en place, et aucun contrôle ne la voyait.
"""
from __future__ import annotations

import pytest

from generation.chapitres.typographie import _PARENTHESE_QUI_SE_REPETE, reparer_texte

EURO = "€"
FINE = " "
INSECABLE = " "


def _retire(texte: str) -> bool:
    return bool(_PARENTHESE_QUI_SE_REPETE.search(texte))


# ---------------------------------------------------------------------------
# Ce qui se répare
# ---------------------------------------------------------------------------


def test_la_coquille_de_son_audit_disparait() -> None:
    """Le cas réel, recopié de son audit."""
    phrase = f"Retenir 0,1 % de 188 M{EURO} (188 M{EURO}), soit 188 000 {EURO}."

    repare = reparer_texte(phrase)

    assert f"(188{FINE}M{EURO})" not in repare
    assert "(188" not in repare
    # Ce qui compte survit : la base, le taux et le résultat.
    assert "0,1" in repare
    assert "188 000" in repare


@pytest.mark.parametrize(
    "phrase",
    [
        # Les espaces de part et d'autre, et l'insécable comme l'ordinaire.
        f"de 188 M{EURO} ( 188 M{EURO} ), soit",
        f"de 188{INSECABLE}M{EURO} (188{INSECABLE}M{EURO}), soit",
        # Un pourcentage se répète aussi bien qu'un montant.
        "La part atteint 6,2 % (6,2 %) du marché",
        # Et un nombre nu : « 11 (11) acteurs ».
        "Le panel compte 11 (11) acteurs",
    ],
)
def test_toutes_ses_formes_sont_vues(phrase: str) -> None:
    assert _retire(phrase)


def test_la_reparation_est_idempotente() -> None:
    """La rejouer ne doit rien changer : c'est le contrat de `reparer_texte`."""
    phrase = f"0,1 % de 188 M{EURO} (188 M{EURO})"

    une_fois = reparer_texte(phrase)

    assert reparer_texte(une_fois) == une_fois


# ---------------------------------------------------------------------------
# Contre-épreuves : les parenthèses qui APPORTENT quelque chose
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phrase",
    [
        # Elle DATE la valeur.
        f"Le marché pèse 188 M{EURO} (2025)",
        # Elle en donne la SOURCE.
        f"Le marché pèse 188 M{EURO} (Insee)",
        # Elle ramène la même valeur à une AUTRE BASE.
        f"Le marché pèse 188 M{EURO} (188 000 {EURO} par jour)",
        # Elle porte une valeur DIFFÉRENTE — l'écart que la cliente relève
        # justement entre les 188 M€ et les 176 Md€.
        f"passe de 188 M{EURO} (176 Md{EURO})",
        # Deux pourcentages distincts.
        "6,2 % (7 %)",
    ],
)
def test_une_parenthese_qui_apporte_quelque_chose_est_gardee(phrase: str) -> None:
    assert not _retire(phrase)
    assert "(" in reparer_texte(phrase)


def test_le_controle_d_arithmetique_a_raison_de_se_taire() -> None:
    """La preuve que le défaut n'est PAS un calcul faux.

    Sans ce test, quelqu'un pourrait croire que `arithmetique.verifier` a
    manqué quelque chose et aller « renforcer » un contrôle qui fonctionne.
    """
    from generation.arithmetique import verifier

    juste = f"Retenir 0,1 % de 188 M{EURO}, soit 188 000 {EURO}."

    assert verifier(juste) == []

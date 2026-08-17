"""Le contrôle des sources prenait une division pour une origine.

## Le motif, relevé sur le business plan 73dde3ab du 17/08/2026

    Le montant 34,4 % est attribué à 3 sources différentes dans le
    document : « 320 000 € à 430 000 € » ; « (430 000 - 320 000 » ;
    « 430 000 moins 320 000, rapportés à 320 000 ».

Aucune des trois n'est une source. Ce sont les trois écritures d'une même
division — la croissance du chiffre d'affaires entre l'exercice 1 et
l'exercice 3 — et le document avait raison de les poser : un lecteur veut
pouvoir refaire l'opération.

Le motif lisait « un montant, une parenthèse, puis l'origine ». Après un
résultat, ce qui suit la parenthèse n'est pas l'origine : c'est le calcul.

## Le discriminant

« Insee, 2025 » porte UN nombre — son millésime. « 430 000 moins 320 000,
rapportés à 320 000 » en porte trois. Chercher des mots n'aurait rien donné :
« moins » et « rapportés à » en sont, et un organisme peut s'appeler
« Fédération des entreprises de boulangerie ».

Un nom d'organisme porte au plus un nombre. C'est tout ce qu'il fallait.
"""
from __future__ import annotations

import pytest

from generation.arithmetique import sources_divergentes

# ── Les trois fausses sources du document, et leurs vraies voisines ──────────

CALCULS = [
    pytest.param(
        "La progression atteint 34,4 % (430 000 - 320 000) / 320 000.",
        id="une-soustraction-entre-parentheses",
    ),
    pytest.param(
        "Le chiffre d'affaires passe de 320 000 € à 430 000 € sur trois ans.",
        id="une-fourchette-de-trajectoire",
    ),
    pytest.param(
        "Soit 34,4 % (430 000 moins 320 000, rapportés à 320 000).",
        id="la-meme-division-en-toutes-lettres",
    ),
]


@pytest.mark.parametrize("phrase", CALCULS)
def test_un_calcul_n_est_jamais_lu_comme_une_source(phrase: str) -> None:
    assert sources_divergentes([phrase]) == [], (
        f"« {phrase} » pose une opération, pas une origine"
    )


def test_deux_calculs_du_meme_resultat_ne_divergent_pas() -> None:
    """Le cas exact du document : trois écritures, un seul chiffre."""
    document = [
        "La progression atteint 34,4 % (430 000 - 320 000) / 320 000.",
        "Soit 34,4 % (430 000 moins 320 000, rapportés à 320 000).",
    ]
    assert sources_divergentes(document) == []


# ── La contre-épreuve : deux VRAIES sources doivent toujours diverger ────────


def test_un_meme_montant_a_deux_organismes_est_toujours_signale() -> None:
    """Sans ce test, le correctif n'aurait fait que désarmer le contrôle.

    Règle 1 : un contrôle qui n'a plus rien à comparer n'est pas un succès,
    c'est un échec silencieux.
    """
    document = [
        "Le marché pèse 16,5 Md€ (Insee, 2025).",
        "Le marché pèse 16,5 Md€ (Xerfi, 2026).",
    ]
    divergences = sources_divergentes(document)
    assert divergences, "deux organismes pour un même montant, cela se signale"


def test_un_organisme_au_nom_chiffre_reste_une_source() -> None:
    """« Insee, 2025 » porte un nombre : c'est son millésime, pas un calcul."""
    document = [
        "Le marché pèse 16,5 Md€ (Insee, 2025).",
        "Le marché pèse 16,5 Md€ (Fédération de la boulangerie, 2024).",
    ]
    assert sources_divergentes(document), (
        "un millésime ne doit pas faire passer une source pour une opération"
    )

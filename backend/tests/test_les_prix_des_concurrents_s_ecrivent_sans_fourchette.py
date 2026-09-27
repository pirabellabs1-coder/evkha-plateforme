"""Les prix des concurrents s'écrivent sans fourchette — décision du 27/09/2026.

## La décision

La dernière étude concurrentielle (`e71fa43a`, 21/09/2026) portait deux formes
que la règle stricte bloquait sans que la cliente les ait jamais vues :

- l'ÉTENDUE des prix d'un panel : « les tarifs du marché s'étalent entre … et … » ;
- la GRILLE d'un seul concurrent : « Concurrent X : …-… € ».

Question posée à Evangéline ; réponse (« cas 1 : A, cas 2 : A ») : la règle
stricte tient. L'étendue s'écrit en trois valeurs séparées — le prix le plus
bas, le prix le plus haut (concurrent, prix, source) et le prix médian du
panel ; la grille s'écrit formule par formule, chaque prix avec sa source.

## Le défaut que la décision a fait voir

Le gate bloquait ces formes, mais AUCUNE consigne ne disait quoi écrire à la
place — chaque génération les réécrivait et payait une correction. Pire, la
consigne commune (« quand une donnée donne deux bornes, tu tranches : la
valeur du milieu par défaut ») aurait fait inventer, pour la grille d'un
concurrent, un prix qu'il n'affiche nulle part.

## Ce que ce fichier verrouille

1. la consigne de rédaction (BP, EC, STR) et la consigne de correction disent
   la forme décidée, et interdisent de trancher le prix d'un concurrent ;
2. le gate bloque les trois formes refusées en EC ;
3. contre-épreuve (règle 6) : il laisse passer les deux formes décidées.
"""

from __future__ import annotations

import pytest

from generation.checks_evangeline import detecter_fourchettes

BP, EC, STR = "business_plan", "competitor_study", "business_strategy"


def _plages(texte: str, livrable: str) -> list[str]:
    return [f.extrait for f in detecter_fourchettes(0, texte, livrable)]


@pytest.mark.parametrize("livrable", [BP, EC, STR])
def test_la_consigne_dit_comment_ecrire_les_prix_des_concurrents(livrable: str) -> None:
    from generation.prompts import _consigne_specifique_livrable

    consigne = _consigne_specifique_livrable(livrable)
    assert "PRIX DES CONCURRENTS" in consigne
    # Cas 2 : la grille d'un concurrent, formule par formule.
    assert "formule par formule" in consigne
    # Cas 1 : trois valeurs séparées.
    for attendu in ("prix le plus bas", "prix le plus haut", "prix médian"):
        assert attendu in consigne, attendu
    # Le prix d'un concurrent ne se tranche pas en valeur du milieu.
    assert "jamais une estimation" in consigne
    assert "tu ne le tranches jamais" in consigne
    # La consigne ne montre pas la faute qu'elle interdit.
    assert _plages(consigne, livrable) == []


def test_la_correction_dit_la_meme_forme() -> None:
    from generation.correction import _CHECK_LABELS

    libelle = _CHECK_LABELS["fourchette_interdite"]
    assert "formule par formule" in libelle
    for attendu in ("prix le plus bas", "prix le plus", "prix médian du panel"):
        assert attendu in libelle, attendu
    assert "ne rien trancher" in libelle
    for livrable in (BP, EC, STR):
        assert _plages(libelle, livrable) == []


@pytest.mark.parametrize("texte", [
    "Les tarifs du marché s'étalent entre 150 € et 890 €.",
    "Concurrent X : 150-300 € par séance.",
    "Concurrent X : de 150 à 300 € selon la formule.",
])
def test_en_ec_les_formes_refusees_restent_bloquees(texte: str) -> None:
    """Cas 1 et cas 2, réponse A : le gate ne s'assouplit pas."""
    assert _plages(texte, EC), texte


@pytest.mark.parametrize("texte", [
    # Cas 1, forme décidée : trois valeurs séparées.
    "Le moins cher est Alpha à 150 € (site Alpha, 2026) ; le plus cher est "
    "Bêta à 890 € (site Bêta, 2026) ; le prix médian des huit prix relevés "
    "est de 390 €.",
    # Cas 2, forme décidée : formule par formule, en prose ou en tableau.
    "Concurrent X : offre Essentiel à 150 €, offre Premium à 300 € (grille "
    "publiée, site X, 2026).",
    "| Concurrent X | Essentiel | 150 € | site X |\n"
    "| Concurrent X | Premium | 300 € | site X |",
])
def test_contre_epreuve_les_formes_decidees_passent(texte: str) -> None:
    assert _plages(texte, EC) == [], texte

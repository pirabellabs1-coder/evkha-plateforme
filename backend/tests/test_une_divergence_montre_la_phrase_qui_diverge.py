"""Le motif d'une divergence montre la valeur qui diverge ET la phrase qui la porte.

## Le défaut mesuré

Corpus du 14/09/2026, seize motifs `coherence_chiffree` de ce type :

    investissement_total : 27 600 € au ch. 0 ; 27 600 € au ch. 13 ; 27 600 €
    au ch. 13 ; 27 600 € au ch. 13 ; 27 600 euros au ch. 15 ; 27 600 € au
    ch. 18 ; 27 600 € au ch. 18 ; 27 600 € au ch. 19 ; 1 600 € au ch. 20

La valeur fautive — ou la lecture fautive du contrôle — est la dernière d'une
énumération, sans la phrase qui la porte. Ni le lecteur ni la passe de
correction ne peuvent la retrouver dans un chapitre de trois pages : c'est un
motif introuvable (règle 2).
"""
from __future__ import annotations

from generation.checks_evangeline import (
    DivergenceChiffree,
    collecter_mentions,
    detecter_divergences,
)


def _divergences(chapitres: dict[int, str]) -> list[DivergenceChiffree]:
    mentions = []
    for numero, texte in chapitres.items():
        mentions.extend(collecter_mentions(numero, texte))
    return detecter_divergences(mentions)


def test_chaque_valeur_une_fois_et_la_phrase_de_la_minoritaire() -> None:
    divs = _divergences({
        0: "Le seuil de rentabilité est de 18 667 €.",
        9: "Le seuil de rentabilité est de 18 667 €.",
        13: "Le seuil de rentabilité est de 18 667 €.",
        15: "Avec ce loyer, le seuil de rentabilité est de 35 609 € dès l'ouverture.",
    })
    assert len(divs) == 1
    resume = divs[0].resume
    assert resume.count("18 667") == 1, resume
    assert "ch. 0, 9, 13" in resume
    assert "« Avec ce loyer, le seuil de rentabilité est de 35 609 €" in resume
    assert "« Le seuil" not in resume, "la valeur majoritaire n'a pas besoin de sa phrase"


def test_sans_majorite_chaque_valeur_montre_sa_phrase() -> None:
    """CONTRE-ÉPREUVE : à égalité, on ne sait pas laquelle est juste — on montre les deux."""
    divs = _divergences({
        9: "Le seuil de rentabilité est de 90 000 euros.",
        12: "Le seuil de rentabilité est de 180 000 €.",
    })
    resume = divs[0].resume
    assert "« Le seuil de rentabilité est de 90 000 euros" in resume
    assert "« Le seuil de rentabilité est de 180 000 €" in resume

"""Conformité d'un chapitre au modèle de référence de l'étude de marché.

Le modèle (`references/modele_etude_marche.json`) fixe la charpente : séquence
des blocs, dosage, longueurs cibles, nombre minimal de graphiques. La niche du
client ne fait varier que le contenu. Ce paquet mesure l'écart entre ce que le
moteur produit et cette charpente, **avant** le rendu.

Pourquoi avant : le rendu ne peut pas rattraper un chapitre qui n'a pas assez de
graphiques ou trop de tableaux. Mesurer après revient à constater les dégâts.

## Ce que ce contrôle NE regarde PAS

La règle 9 demande de nommer ce qu'un contrôle laisse de côté, parce que c'est
là que la réparation ne cherchera pas non plus.

- **La séquence des blocs.** `ChapitrePayload` porte trois listes séparées —
  `sections`, `encadres`, `graphiques` — sans entrelacement. Il ne peut donc pas
  exprimer « graphique entre le deuxième et le troisième paragraphe ». Le
  contrôle est déclaré NON EXÉCUTÉ, jamais réussi.
- **La longueur de chaque paragraphe.** Même cause : sans ordre, on ne sait pas
  quel paragraphe correspond à quelle cible. Seul le volume total est vérifié.
- **L'exactitude arithmétique des chiffres.** On vérifie qu'un identifiant cité
  existe au socle, pas qu'une somme est juste.
"""
from __future__ import annotations

from .chargement import (
    ModeleIntrouvableError,
    chapitre_du_modele,
    charger_modele,
    dosage_attendu,
)
from .conformite import (
    Ecart,
    Gravite,
    RapportConformite,
    verifier_chapitre,
)

__all__ = [
    "Ecart",
    "Gravite",
    "ModeleIntrouvableError",
    "RapportConformite",
    "chapitre_du_modele",
    "charger_modele",
    "dosage_attendu",
    "verifier_chapitre",
]

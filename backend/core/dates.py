"""Source UNIQUE des dates ecrites en francais.

Deux listes de mois vivaient dans le depot : une accentuee dans
`generation/rendering.py`, une SANS accents dans `rendu_word/assemblage.py` —
celle de la page de couverture. Chaque document livre depuis le lot 3 portait
donc « 26 aout 2026 » en premiere page (relecture du 26/09/2026). Et la ligne
du socle injectee dans chaque prompt de chapitre datait ses chiffres en ISO
(« arrete au 2026-08-08 »), forme que le modele recopie volontiers.

REGLE : aucun module n'ecrit un mois en toutes lettres pour son compte.
"""
from __future__ import annotations

from datetime import date

MOIS_FR: dict[int, str] = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril",
    5: "mai", 6: "juin", 7: "juillet", 8: "août",
    9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre",
}


def date_francaise(jour: date, *, jour_sur_deux_chiffres: bool = False) -> str:
    """« 8 août 2026 » — ou « 08 août 2026 » quand l'appelant aligne des colonnes."""
    numero = f"{jour.day:02d}" if jour_sur_deux_chiffres else str(jour.day)
    return f"{numero} {MOIS_FR[jour.month]} {jour.year}"

"""L'instrument de mesure doit être plus honnête que ce qu'il mesure.

`mesurer_livrable` compte les trois défauts que le client a nommés le
12/09/2026 : figures non rendues, sources sans adresse, chiffres hors socle.
Il sert à répondre par des NOMBRES à la question « est-ce que l'entraînement
des prompts a servi ». Un instrument qui se flatte rendrait cette réponse
pire qu'absente.

Sa première version a menti deux fois, et les deux mensonges sont nommés dans
CLAUDE.md :

    « 17/14 rendues, 121 % »   — les figures ajoutées par la passe de
                                 complétion comptées comme demandées et
                                 obtenues (règle 2 : un motif faux est pire
                                 qu'absent)
    « 0 source extérieure »    — alors que le chapitre Sources était
                                 INTROUVABLE (règle 1 : un contrôle qui n'a
                                 rien à comparer est un échec, pas un succès)

Ces tests échouent sur cette première version.
"""
from __future__ import annotations

from generation.management.commands.mesurer_livrable import _mesurer_les_sources

_AVEC_TABLEAU = """# Sources

| Source | Apport | Année |
| --- | --- | --- |
| Insee, https://www.insee.fr/x | Population | 2025 |
| Numeum | Marché logiciel | 2024 |
| Données du projet | Chiffre d'affaires | 2026 |
"""

_ADRESSE_INVENTEE = """# Sources

- Insee, 2025 — https://example.com/etude
- Numeum, 2024 — https://www.numeum.fr/vrai
"""


def test_un_chapitre_sources_absent_ne_rend_pas_zero() -> None:
    """LE test : zéro source et pas de chapitre ne sont pas le même constat.

    Confondre les deux ferait passer un document sans aucune traçabilité pour
    un document irréprochable — exactement à l'envers.
    """
    assert _mesurer_les_sources("# Analyse\n\nDu texte, aucun chapitre Sources.") is None


def test_les_sources_du_client_sont_comptees_a_part() -> None:
    """Son prévisionnel n'est pas publié et ne le sera jamais.

    Les compter comme « sans adresse » accuserait le document d'un défaut
    qu'il n'a pas — et un contrôle qui crie faux finit débranché.
    """
    mesure = _mesurer_les_sources(_AVEC_TABLEAU)
    assert mesure is not None
    exterieures, sans_adresse, du_client = mesure
    assert (exterieures, du_client) == (2, 1)
    assert sans_adresse == 1, "Numeum est cité sans son adresse"


def test_une_adresse_inventee_compte_comme_une_absence() -> None:
    """C'est le défaut WAOME, et il est PIRE qu'une absence.

    Une URL en `example.com` a l'apparence du sérieux : le lecteur la suit,
    et ne trouve rien. La mesure ne doit pas la créditer.
    """
    mesure = _mesurer_les_sources(_ADRESSE_INVENTEE)
    assert mesure is not None
    exterieures, sans_adresse, _ = mesure
    assert exterieures == 2
    assert sans_adresse == 1, "l'adresse en example.com ne vaut pas une source"

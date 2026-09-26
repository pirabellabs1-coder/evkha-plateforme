"""Ce que le client colle dans « Tableaux financiers » est lu comme le reste du brief.

Business plan `eab58554`, 26/09/2026, motif du gate : « Le brief liste des
verticales d'activité que la lecture automatique n'a pas retenues ». Le
client avait écrit, dans le champ TABLEAUX_FINANCIERS de l'espace client :

    VERTICALES D'ACTIVITÉS : B2C – utilisateurs ; B2B – professionnels ; B2G – …
    SEUIL DE RENTABILITE : 90 000 €

Forme que `_extract_verticales` lit sans difficulté — mais `TABLEAUX_FINANCIERS`
n'était pas dans `_FREE_TEXT_SOURCES`, la liste des champs que l'intake ET le
gate relisent. Le gate avait vu le mot « verticales » dans un AUTRE champ
(« trois verticales :⏎B2C⏎… », illisible) et bloqué ; la forme lisible dormait
dans un champ que personne n'ouvrait. Même classe que les encadrés du
formulaire BP de juillet 2026 : un champ créé exprès pour l'état chiffré,
jamais lu (règle 1, côté lecteur).
"""
from __future__ import annotations

from intake.financials import _FREE_TEXT_SOURCES, enrich_variables_from_free_text

TABLEAU = (
    "RESULTAT NET : 12 000 €\n"
    "TAUX D'OCCUPATION : Non applicable – activité numérique / plateforme\n"
    "VERTICALES D'ACTIVITÉS : B2C – utilisateurs particuliers ; "
    "B2B – professionnels et établissements pet-friendly ; B2G – offices de tourisme\n"
    "SEUIL DE RENTABILITE : 90 000 €"
)


def test_le_champ_est_une_source_de_texte_libre() -> None:
    assert "TABLEAUX_FINANCIERS" in _FREE_TEXT_SOURCES


def test_les_verticales_et_le_seuil_du_tableau_sont_retenus() -> None:
    variables: dict[str, object] = {"TABLEAUX_FINANCIERS": TABLEAU}

    ajoutees = enrich_variables_from_free_text(variables)

    assert ajoutees["VERTICALES"] == (
        "B2C – utilisateurs particuliers / B2B – professionnels et établissements "
        "pet-friendly / B2G – offices de tourisme"
    )
    assert ajoutees["SEUIL_RENTABILITE"] == "90 000 €"
    assert ajoutees["RESULTAT_NET_PREVISIONNEL"] == "12 000 €"


def test_un_champ_structure_garde_la_main() -> None:
    """Contre-épreuve : le texte libre ne remplit qu'une clé absente."""
    variables: dict[str, object] = {
        "TABLEAUX_FINANCIERS": TABLEAU,
        "SEUIL_RENTABILITE": "95 000 €",
    }
    ajoutees = enrich_variables_from_free_text(variables)
    assert "SEUIL_RENTABILITE" not in ajoutees
    assert variables["SEUIL_RENTABILITE"] == "95 000 €"

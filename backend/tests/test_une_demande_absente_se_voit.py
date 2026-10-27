"""Un mot de la demande du client qui n'apparaît NULLE PART dans l'étude.

Étude de marché à l'export, cliente, 26/10/2026 : « la demande prioritaire du
client — les langues et dialectes parlés dans chaque pays — n'est pas traitée ;
le FOCUS parle des conditions d'entrée ». Le contrôle de couverture tournait :
il interroge un modèle, et le modèle avait jugé la demande couverte.

Ce contrôle-ci ne juge rien, il constate — et il se vérifie par une recherche
dans le document (règle 9 : un contrôle et sa réparation ne jugent pas sur la
même évidence).
"""
from __future__ import annotations

from generation.couverture import MOTS_ABSENTS_MIN, demandes_absentes

BRIEF = {
    "DEMANDES_SPECIFIQUES": (
        "Je voudrais connaître les langues et dialectes parlés dans chaque pays "
        "ciblé, pour adapter nos étiquettes."
    ),
}

ETUDE_QUI_ESQUIVE = (
    "Les conditions d'entrée sur le marché coréen imposent un enregistrement "
    "sanitaire préalable. Les droits de douane atteignent 8 % sur les produits "
    "transformés, et la distribution reste concentrée sur trois acteurs."
)

ETUDE_QUI_REPOND = (
    "Chaque pays ciblé impose sa langue d'étiquetage : le coréen en Corée du "
    "Sud, le japonais au Japon. Les dialectes régionaux ne sont pas exigés sur "
    "l'emballage, mais ils comptent pour la communication locale."
)


def test_une_demande_esquivee_est_nommee() -> None:
    [absente] = demandes_absentes(BRIEF, ETUDE_QUI_ESQUIVE)
    assert absente.champ == "DEMANDES_SPECIFIQUES"
    mots = {m.lower() for m in absente.mots}
    assert "langues" in mots or "langue" in mots
    assert any("dialect" in m.lower() for m in absente.mots)
    # Règle 2 : la ligne de l'incident doit être vérifiable par le lecteur.
    assert "mots absents" in absente.ligne()


def test_une_demande_traitee_ne_dit_rien() -> None:
    """Contre-épreuve : le correctif ne doit pas punir ce qui est juste."""
    assert demandes_absentes(BRIEF, ETUDE_QUI_REPOND) == []


def test_une_flexion_differente_suffit() -> None:
    """Contre-épreuve : « dialectal » répond à « dialectes »."""
    assert demandes_absentes(
        BRIEF,
        "La langue d'étiquetage et la variation dialectale sont traitées pays "
        "par pays, avec les étiquettes exigées et l'adaptation attendue.",
    ) == []


def test_un_seul_mot_absent_ne_suffit_pas() -> None:
    """Un mot manquant est courant et innocent : il en faut deux."""
    assert MOTS_ABSENTS_MIN == 2
    assert demandes_absentes(
        {"DEMANDES_SPECIFIQUES": "Je veux connaître les langues parlées sur place."},
        "Les étiquettes doivent être traduites dans la langue locale de chaque pays.",
    ) == []


def test_le_vocabulaire_de_toute_etude_ne_compte_pas() -> None:
    """Contre-épreuve : « concurrence », « croissance » se trouvent partout."""
    assert demandes_absentes(
        {"OBJECTIF_STRATEGIQUE": "Comprendre la concurrence et la croissance du secteur."},
        "Rien ici.",
    ) == []


def test_un_document_vide_ne_declenche_rien() -> None:
    """Règle 1 inversée : sans document, il n'y a rien à constater — et on se
    tait plutôt que de déclarer toutes les demandes absentes."""
    assert demandes_absentes(BRIEF, "") == []


def test_un_brief_vide_ne_declenche_rien() -> None:
    assert demandes_absentes({}, ETUDE_QUI_ESQUIVE) == []
    assert demandes_absentes(None, ETUDE_QUI_ESQUIVE) == []

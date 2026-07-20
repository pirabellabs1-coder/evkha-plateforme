"""Phase 26 — Les nouveaux champs Tally d'Evangeline sont reconnus, TOUS.

Contexte : Evangeline a ajoute aux quatre formulaires Tally les champs que
je lui avais demandes (pays, ville, nom du porteur, modele economique
actuel, offres, positionnement actuel, canaux, enjeux strategiques...).
Tobias : « les informations devraient etre recuperees depuis ces champs et
utilisees a la lettre, pas d'omission, pas d'oubli ».

Constat AVANT ce commit (measure sur formulaires scrapes le 19/07/2026) :
14 des nouveaux libelles n'etaient pas reconnus par `_canonical_key`. Sans
mapping, ces champs arrivent en base et sont JAMAIS lus.

Chaque libelle de test vient d'un scrape reel des 4 formulaires Tally
en ligne, jamais reformule pour l'occasion (regle 8 du CLAUDE.md :
chercher avant de conclure).
"""
from __future__ import annotations

import pytest

from intake.services import _canonical_key

# ── Champs presents sur les 4 formulaires ───────────────────────────────────


@pytest.mark.parametrize(
    ("libelle", "attendu"),
    [
        ("Nom du projet / de l'entreprise",                    "NOM_ENTREPRISE"),
        ("Nom du projet ou de l'entreprise",                   "NOM_ENTREPRISE"),
        ("Nom de l'entreprise (ou future) qui sera étudiée",   "NOM_ENTREPRISE"),
        ("Nom de l'entreprise concernée par la stratégie :",   "NOM_ENTREPRISE"),
        ("Pays",                                               "PAYS"),
        ("Ville ou zone géographique",                         "ZONE"),
        ("Secteur d'activité",                                 "SECTEUR"),
        ("Secteur et domaine d'activité :",                    "SECTEUR"),
    ],
)
def test_les_champs_communs_aux_quatre_formulaires_sont_reconnus(
    libelle: str, attendu: str
) -> None:
    assert _canonical_key(libelle) == attendu


# ── Champs specifiques BP : porteur de projet, dates ────────────────────────


@pytest.mark.parametrize(
    ("libelle", "attendu"),
    [
        ("Nom du porteur de projet :",                        "NOM_PORTEUR"),
        ("Parcours pour l'histoire du projet, tranche d'âge :", "PARCOURS_PORTEUR"),
        ("Contact pro : téléphone, mail, site, réseaux sociaux :", "CONTACT_PORTEUR"),
        ("Date de création prévue / statut actuel :",         "DATE_CREATION_PREVUE"),
    ],
)
def test_les_champs_porteur_de_projet_bp_sont_reconnus(
    libelle: str, attendu: str
) -> None:
    assert _canonical_key(libelle) == attendu


# ── Champs specifiques STR : modele economique, offres, enjeux ──────────────


@pytest.mark.parametrize(
    ("libelle", "attendu"),
    [
        (
            "Comment votre entreprise génère-t-elle ses revenus aujourd'hui ?",
            "MODELE_ECONOMIQUE_ACTUEL",
        ),
        (
            "Quelles sont vos offres / prestations actuelles ?",
            "OFFRES_ACTUELLES",
        ),
        (
            "Selon vous, quelles offres sont les plus rentables ?",
            "OFFRES_RENTABLES",
        ),
        (
            "Lesquelles sont les plus chronophages ou peu rentables ?",
            "OFFRES_CHRONOPHAGES",
        ),
        (
            "Vos revenus sont-ils plutôt réguliers, irréguliers, saisonniers, "
            "ou imprévisibles ?",
            "REGULARITE_REVENUS",
        ),
        (
            "Comment positionnez-vous votre entreprise aujourd'hui ?",
            "POSITIONNEMENT_ACTUEL",
        ),
        (
            "Sur quels canaux attirez-vous actuellement vos clients ?",
            "CANAUX_ACQUISITION",
        ),
        (
            "Combien d'heures par semaine consacrez-vous à votre entreprise ?",
            "CHARGE_DIRIGEANT_HEURES",
        ),
        (
            "Indiquez les sujets qui vous préoccupent réellement aujourd'hui ?",
            "ENJEUX_STRATEGIQUES",
        ),
        (
            "Si vous deviez résumer en une phrase la question stratégique "
            "principale à laquelle vous voulez que cette stratégie réponde ?",
            "QUESTION_STRATEGIQUE",
        ),
    ],
)
def test_les_champs_strategie_business_sont_reconnus(
    libelle: str, attendu: str
) -> None:
    assert _canonical_key(libelle) == attendu


# ── Contre-epreuve : le texte ordinaire n'est toujours pas capture ──────────


@pytest.mark.parametrize(
    "libelle",
    [
        "Note à lire avant de commencer",
        "Submit",
        "Modèle EVKHA structuré selon les normes professionnelles",
        "",
        "   ",
    ],
)
def test_le_texte_ordinaire_ne_devient_pas_un_champ(libelle: str) -> None:
    """Les nouveaux ajouts au mapping ne doivent pas rendre la table
    gloutonne. Si une phrase ordinaire matche, on cree un « fait client » qui
    n'existe pas — c'est pire que le manque."""
    assert _canonical_key(libelle) is None

"""Quatre verbes pris pour un sujet « non traité ».

## Le motif, relevé sur le business plan 73dde3ab du 17/08/2026

    Chapitre 20 declare « non traite » un sujet que le document traite
    ailleurs : indique, initial, partiellement, reprend.

Aucun des quatre ne nomme un sujet : deux verbes conjugués, un adjectif, un
adverbe, ramassés dans une phrase de justification.

## Pourquoi la distinctivité ne suffisait pas

Ce contrôle avait déjà été resserré le 12/08/2026, après un motif faux sur
« chaque, chiffrée, explicite, manque » : un mot présent dans la moitié des
chapitres ne désigne aucun sujet, et cette mesure-là a tenu.

Elle ne suffit pas. « partiellement » est assez long, assez rare — et ne
nomme toujours rien. Rallonger la liste des mots communs aurait été réparer
l'instance une deuxième fois, sans connaître les quatre mots suivants.

## Le discriminant : un sujet est une LOCUTION

« Canaux d'acquisition des concurrents » se retrouve ailleurs **côte à côte**.
Des mots épars qui se croisent aux quatre coins d'un chapitre ne prouvent
rien — c'est leur DISPERSION qui les trahit, pas leur rareté.

Le contrôle exige donc que deux des mots porteurs se retrouvent à moins de
cent caractères l'un de l'autre dans le chapitre qui contredirait.
"""
from __future__ import annotations

from generation.checks_post_rendu import detecter_demandes_contredites

#: Le vrai défaut de la cliente (11/08/2026) : le sujet EST une locution, et il
#: est bel et bien traité au chapitre 3.
CONTRADICTION_REELLE = [
    (
        3,
        "Les canaux d'acquisition des concurrents",
        "Les canaux d'acquisition des concurrents sont analysés en détail : "
        "référencement local, vitrine, bouche-à-oreille et partenariats.",
    ),
    (
        8,
        "Validation des demandes",
        "Analyser les canaux d'acquisition des concurrents : non traitée.",
    ),
]

#: Le motif faux : les mots viennent d'une justification, pas d'un sujet, et
#: ils sont dispersés dans le chapitre qui est censé le « traiter ».
#:
#: Les mots sont ceux du motif réel ; leur DISPERSION est reconstruite. Le
#: texte du chapitre 20 du document n'était plus accessible au moment d'écrire
#: ce fichier, et inventer une adjacence aurait fait dire au test l'inverse de
#: ce qu'il vérifie. Ce cas prouve donc la règle, pas la disparition du motif
#: exact — c'est une limite, et elle est écrite plutôt que tue (règle 1).
MOTS_EPARS = [
    (
        6,
        "Positionnement",
        ("Remplissage neutre. " * 10).join(
            [
                "Le calendrier est arrêté.",
                "Le plan indique une ouverture au printemps.",
                "Ce choix était initial.",
                "La zone est partiellement desservie.",
                "Le risque reste couvert.",
            ]
        ),
    ),
    (
        20,
        "Validation des demandes",
        "Le calendrier indique un local initial partiellement couvert : "
        "non traitée.",
    ),
]


def test_une_vraie_contradiction_est_toujours_trouvee() -> None:
    """Sans ce test, le correctif n'aurait fait que désarmer le contrôle."""
    defauts = detecter_demandes_contredites(CONTRADICTION_REELLE)
    assert defauts, (
        "« canaux d'acquisition » est traité au chapitre 3 et déclaré non "
        "traité au chapitre 8 — c'est le défaut que la cliente a vu"
    )
    assert defauts[0].chapitre == 8


def test_des_mots_epars_ne_font_pas_un_sujet() -> None:
    defauts = detecter_demandes_contredites(MOTS_EPARS)
    assert defauts == [], (
        "« indique », « initial », « partiellement », « reprend » ne nomment "
        "aucun sujet ; ils se croisent, ils ne se suivent pas"
    )

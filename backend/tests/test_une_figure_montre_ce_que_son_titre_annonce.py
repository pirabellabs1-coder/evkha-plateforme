"""Deux figures qui comparent des groupes différents ne peuvent pas être identiques.

Cliente, 11/08/2026, sur une étude notée 8,5/10 :

    « les radars comparatifs (chapitres 1, 2.3, 7.6, 7.7) réutilisent tous la
    même image, censée représenter tantôt les 8 concurrents directs, tantôt
    les 3 indirects. Résultat, le radar "concurrents indirects" du chapitre
    7.7 affiche en réalité les données des directs. »

## Un seul défaut, pas deux

Le rendu n'était pas en cause : chaque figure produit bien sa propre image.
Les quatre radars étaient identiques parce qu'ils résolvaient les MÊMES
DONNÉES — les quatre chapitres citaient les mêmes critères, `notes_sur`
rendait la liste entière, et le résolveur gardait les cinq premiers.

Rien ne permettait à un chapitre de dire QUELS acteurs sa figure compare.
C'est le résolveur écrit le matin même qui manquait cette entrée : il ne
pouvait produire rien d'autre.
"""
from __future__ import annotations

import datetime as dt

from generation.rendu_word.donnees_graphiques import resoudre
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import (
    Concurrent,
    Critere,
    DonneeSocle,
    NoteConcurrent,
    Socle,
    Zone,
)

CRITERES = [
    Critere(code="prix", intitule="Prix", note_1="cher", note_5="accessible"),
    Critere(code="offre", intitule="Offre", note_1="étroite", note_5="large"),
    Critere(code="notoriete", intitule="Notoriété", note_1="nulle", note_5="forte"),
]


def _acteur(nom: str, type_: str, prix: int, offre: int, notoriete: int) -> Concurrent:
    return Concurrent(
        nom=nom, type=type_,
        notes=[
            NoteConcurrent(critere="prix", note=prix),
            NoteConcurrent(critere="offre", note=offre),
            NoteConcurrent(critere="notoriete", note=notoriete),
        ],
    )


def _socle() -> Socle:
    return Socle(
        secteur="or physique",
        zone=Zone(pays="France"),
        date_socle=dt.date(2026, 8, 11),
        donnees=[
            DonneeSocle(
                id="taille_marche", libelle="Marché", valeur=600, unite="MEUR",
                annee=2026, perimetre=Perimetre.NATIONAL,
                fiabilite=Fiabilite.ESTIMEE,
            )
        ],
        grille_notation=CRITERES,
        concurrents=[
            _acteur("Direct A", "direct", 4, 3, 4),
            _acteur("Direct B", "direct", 3, 4, 3),
            _acteur("Direct C", "direct", 5, 2, 2),
            _acteur("Direct D", "direct", 2, 5, 5),
            _acteur("Direct E", "direct", 4, 4, 3),
            _acteur("Direct F", "direct", 1, 3, 2),
            _acteur("Indirect X", "indirect", 2, 2, 5),
            _acteur("Indirect Y", "indirect", 5, 5, 1),
            _acteur("Indirect Z", "indirect", 3, 1, 4),
        ],
    )


CODES = ["prix", "offre", "notoriete"]


def test_le_radar_des_indirects_ne_montre_que_des_indirects() -> None:
    """Le défaut exact : le radar « indirects » affichait des directs."""
    resolution = resoudre(_socle(), "radar", [*CODES, "indirects"])

    assert resolution.retenu, resolution.motif
    assert resolution.donnees is not None
    noms = [nom for nom, _ in resolution.donnees["series"]]
    assert noms == ["Indirect X", "Indirect Y", "Indirect Z"]


def test_deux_radars_de_groupes_differents_ne_sont_pas_identiques() -> None:
    """La conséquence visible : quatre chapitres, la même image."""
    socle = _socle()
    directs = resoudre(socle, "radar", [*CODES, "directs"])
    indirects = resoudre(socle, "radar", [*CODES, "indirects"])

    assert directs.donnees is not None
    assert indirects.donnees is not None
    assert directs.donnees["series"] != indirects.donnees["series"]


def test_les_acteurs_se_citent_aussi_par_leur_nom() -> None:
    """Un chapitre qui compare trois acteurs précis n'a pas de sélecteur."""
    resolution = resoudre(
        _socle(), "radar", [*CODES, "Direct A", "Indirect Z"]
    )

    assert resolution.donnees is not None
    assert [nom for nom, _ in resolution.donnees["series"]] == [
        "Direct A", "Indirect Z"
    ]


def test_la_carte_de_positionnement_respecte_la_selection() -> None:
    """Même entrée pour les trois figures d'acteurs (règle 4)."""
    resolution = resoudre(
        _socle(), "matrice_positionnement", ["prix", "offre", "indirects"]
    )

    assert resolution.donnees is not None
    assert [nom for nom, _, _ in resolution.donnees["points"]] == [
        "Indirect X", "Indirect Y", "Indirect Z"
    ]


def test_la_carte_de_chaleur_respecte_la_selection() -> None:
    resolution = resoudre(
        _socle(), "carte_chaleur", ["prix", "offre", "directs"]
    )

    assert resolution.donnees is not None
    assert all(nom.startswith("Direct") for nom in resolution.donnees["lignes"])


# ── Les contre-épreuves ──────────────────────────────────────────────────────


def test_sans_selecteur_la_figure_prend_tous_les_acteurs() -> None:
    """CONTRE-ÉPREUVE : le comportement d'avant reste le défaut par défaut.

    Un chapitre qui ne précise rien compare tout le monde — c'est légitime, et
    c'est ce que font les figures de synthèse.
    """
    resolution = resoudre(_socle(), "matrice_positionnement", ["prix", "offre"])

    assert resolution.donnees is not None
    assert len(resolution.donnees["points"]) == 9


def test_un_nom_inconnu_du_socle_est_ignore() -> None:
    """CONTRE-ÉPREUVE : un chapitre ne peut pas inventer un concurrent.

    Le sélecteur ne crée jamais d'acteur ; il ne fait que restreindre. Un nom
    qui ne figure pas dans la base consolidée ne doit rien ajouter.
    """
    resolution = resoudre(
        _socle(), "radar", [*CODES, "Direct A", "Acteur Fantôme"]
    )

    assert resolution.donnees is not None
    assert [nom for nom, _ in resolution.donnees["series"]] == ["Direct A"]


def test_une_selection_sans_acteur_note_explique_pourquoi() -> None:
    """Le motif nomme la restriction : sans elle, on chercherait ailleurs."""
    resolution = resoudre(_socle(), "radar", [*CODES, "Acteur Fantôme"])

    assert not resolution.retenu
    assert "aucun acteur" in resolution.motif


def test_la_consigne_dit_comment_choisir_les_acteurs() -> None:
    """La cause, pas seulement le résolveur : sans consigne, personne ne cite
    ces sélecteurs et le défaut se reproduit à l'identique."""
    from generation.chapitres.runner import _bloc_grille

    socle = _socle()
    bloc = _bloc_grille(socle)

    assert "`directs`" in bloc or "directs" in bloc
    assert "indirects" in bloc
    assert "QUELS acteurs" in bloc

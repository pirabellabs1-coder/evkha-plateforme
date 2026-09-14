"""Des barres sur les critères de la grille comparent les acteurs notés.

## Le défaut mesuré

Corpus du 14/09/2026 : les études concurrentielles `b6cb8076`, `1caf5b8a`,
`a3323207` et `c7c6ba96` perdaient leurs figures sur « identifiants absents du
socle : prix, offre, qualite_service, directs ». Ces codes ne sont PAS absents :
ce sont les critères de `grille_notation`, et « directs » le sélecteur
d'acteurs. Le radar et la carte de positionnement savaient les lire ; les
barres groupées et horizontales, non — la figure passait en tableau.

Contre-épreuves : des critères que personne n'a notés, et un camembert de
notes (des notes ne sont pas les parts d'un tout), restent refusés.
"""
from __future__ import annotations

import datetime as dt

from generation.rendu_word.donnees_graphiques import resoudre
from generation.socle.schema import Concurrent, Critere, NoteConcurrent, Socle, Zone

CRITERES = [
    Critere(code="prix", intitule="Accessibilité tarifaire",
            note_1="prime de plus de 15 %", note_5="prime sous 3 %"),
    Critere(code="offre", intitule="Étendue de l'offre",
            note_1="un seul format", note_5="tous formats"),
    Critere(code="notoriete", intitule="Notoriété",
            note_1="aucune mention", note_5="référence du secteur"),
]


def _acteur(nom: str, type_acteur: str = "direct", **notes: int) -> Concurrent:
    return Concurrent(
        nom=nom, type=type_acteur,
        notes=[NoteConcurrent(critere=code, note=n) for code, n in notes.items()],
    )


def _socle(*acteurs: Concurrent) -> Socle:
    return Socle(
        secteur="or physique", zone=Zone(pays="France"), date_socle=dt.date(2026, 9, 14),
        concurrents=list(acteurs), grille_notation=CRITERES,
    )


def test_des_barres_groupees_sur_des_criteres_comparent_les_acteurs() -> None:
    socle = _socle(
        _acteur("VeraCash", prix=4, offre=3, notoriete=4),
        _acteur("AuCOFFRE", prix=3, offre=4, notoriete=3),
        _acteur("Kara", "indirect", prix=5, offre=2, notoriete=1),
    )
    resolution = resoudre(socle, "barres_groupees", ["prix", "offre", "notoriete", "directs"])
    assert resolution.retenu, resolution.motif
    assert resolution.donnees is not None
    assert resolution.donnees["etiquettes"] == [
        "Accessibilité tarifaire", "Étendue de l'offre", "Notoriété",
    ]
    assert [nom for nom, _ in resolution.donnees["series"]] == ["VeraCash", "AuCOFFRE"]


def test_des_barres_horizontales_sur_un_critere_classent_les_acteurs() -> None:
    socle = _socle(
        _acteur("VeraCash", prix=4, offre=3, notoriete=4),
        _acteur("AuCOFFRE", prix=3, offre=4, notoriete=3),
    )
    resolution = resoudre(socle, "barres_horizontales", ["notoriete", "directs"])
    assert resolution.retenu, resolution.motif
    assert resolution.donnees is not None
    assert list(zip(resolution.donnees["etiquettes"], resolution.donnees["valeurs"],
                    strict=True)) == [("VeraCash", 4.0), ("AuCOFFRE", 3.0)]


def test_des_criteres_que_personne_n_a_notes_restent_refuses() -> None:
    """CONTRE-ÉPREUVE."""
    socle = _socle(Concurrent(nom="VeraCash"), Concurrent(nom="AuCOFFRE"))
    resolution = resoudre(socle, "barres_groupees", ["prix", "offre"])
    assert not resolution.retenu


def test_un_camembert_de_notes_reste_refuse() -> None:
    """CONTRE-ÉPREUVE : des notes ne sont pas les parts d'un tout."""
    socle = _socle(
        _acteur("VeraCash", prix=4, offre=3, notoriete=4),
        _acteur("AuCOFFRE", prix=3, offre=4, notoriete=3),
    )
    assert not resoudre(socle, "camembert", ["notoriete", "directs"]).retenu


def test_les_barres_de_notes_se_dessinent() -> None:
    """Règle 3 : ce que le résolveur rend, le dessin doit l'accepter."""
    from generation.rendu_word.graphiques import rendre
    from generation.rendu_word.palette import construire_palette

    socle = _socle(
        _acteur("VeraCash", prix=4, offre=3, notoriete=4),
        _acteur("AuCOFFRE", prix=3, offre=4, notoriete=3),
    )
    palette = construire_palette()
    for forme, ids in (("barres_groupees", ["prix", "offre"]), ("barres_horizontales", ["prix"])):
        resolution = resoudre(socle, forme, ids)
        assert resolution.donnees is not None
        image = rendre(palette, resolution.type_graphique, resolution.donnees, titre="Notes")
        assert image[:4] == b"\x89PNG"

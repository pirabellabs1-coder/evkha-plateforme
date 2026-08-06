"""Un previsionnel se dessine : CA, resultat et tresorerie sur trois exercices.

Etape 3 du plan du 06/08/2026, PREALABLE a la bascule du business plan sur le
moteur structure.

## Le defaut, mesure avant d'ecrire

`series_par_perimetre` groupait les points par perimetre geographique — la
bonne cle pour des trajectoires de marche (mondial, national), et la SEULE
possible a l'epoque. Mais toutes les donnees d'un previsionnel partagent le
perimetre ENTREPRISE : `ca_previsionnel_an2` et `resultat_net_an2` tombaient
dans le meme seau, a la meme annee — `groupes[cle][annee] = valeur`, le second
ecrasait le premier.

Consequence : une figure « CA vs resultat sur trois exercices » rendait UNE
serie melant les deux grandeurs, sans erreur, sans avertissement. Pas une
figure absente — une figure FAUSSE dont chaque chiffre pris isolement est
juste. C'est la pire categorie de defaut de ce depot (regle 2).

## La convention qui repare

Les identifiants annuels du referentiel BP suivent `<serie>_anN`
(`test_referentiels_bp_et_str` la verrouille). Le groupement lit ce radical
AVANT le perimetre ; les identifiants sans suffixe retombent sur le perimetre,
et les deux mondes coexistent dans une meme figure.
"""
from __future__ import annotations

from datetime import date

from generation.rendu_word.donnees_graphiques import resoudre, series_par_perimetre
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Zone


def _entreprise(
    identifiant: str, valeur: float, annee: int, libelle: str = ""
) -> DonneeSocle:
    return DonneeSocle(
        id=identifiant,
        libelle=libelle or f"Libellé de {identifiant}",
        valeur=valeur, unite="EUR", annee=annee,
        perimetre=Perimetre.ENTREPRISE, fiabilite=Fiabilite.SCENARIO,
    )


def _national(identifiant: str, valeur: float, annee: int) -> DonneeSocle:
    return DonneeSocle(
        id=identifiant, libelle=f"Marché national — {identifiant}",
        valeur=valeur, unite="EUR", annee=annee,
        perimetre=Perimetre.NATIONAL, fiabilite=Fiabilite.ESTIMEE,
    )


def _socle(*donnees: DonneeSocle) -> Socle:
    return Socle(
        secteur="joaillerie de créateurs",
        zone=Zone(pays="France"),
        date_socle=date(2026, 8, 6),
        donnees=list(donnees),
    )


PREVISIONNEL = (
    ("ca_previsionnel", (135_000, 218_000, 320_000)),
    ("resultat_net", (-12_000, 24_000, 61_000)),
    ("tresorerie_fin", (28_000, 47_000, 96_000)),
)


def _donnees_du_previsionnel() -> list[DonneeSocle]:
    donnees = []
    for radical, valeurs in PREVISIONNEL:
        for exercice, valeur in enumerate(valeurs, start=1):
            donnees.append(_entreprise(
                f"{radical}_an{exercice}", valeur, 2025 + exercice,
                libelle=f"{radical.replace('_', ' ')} — exercice {exercice}",
            ))
    return donnees


def test_trois_series_d_entreprise_restent_trois_series() -> None:
    """LE test de ce fichier. Sur le code d'avant : UNE serie, valeurs melees.

    Neuf donnees, trois radicaux, un seul perimetre. Le groupement par
    perimetre n'en faisait qu'un seau ou chaque annee gardait la DERNIERE
    valeur ecrite — la tresorerie effacait le resultat, qui effacait le CA.
    """
    donnees = _donnees_du_previsionnel()
    valeurs = [d.valeur for d in donnees]
    annees = [2026, 2027, 2028]

    series = series_par_perimetre(donnees, valeurs, annees)

    assert len(series) == 3
    par_nom = {nom: points for nom, points in series}
    # Chaque serie porte SES valeurs, dans l'ordre des exercices.
    assert list(par_nom.values())[0] is not None
    assert [points for _, points in sorted(par_nom.items())] == [
        [135_000.0, 218_000.0, 320_000.0],   # ca previsionnel
        [-12_000.0, 24_000.0, 61_000.0],     # resultat net
        [28_000.0, 47_000.0, 96_000.0],      # tresorerie fin
    ]


def test_le_nom_de_serie_ne_designe_pas_un_exercice() -> None:
    """« CA previsionnel — exercice 1 » nommerait UN point ; la serie en a trois."""
    donnees = _donnees_du_previsionnel()
    valeurs = [d.valeur for d in donnees]

    series = series_par_perimetre(donnees, valeurs, [2026, 2027, 2028])

    for nom, _ in series:
        assert "exercice" not in nom.lower(), nom


def test_les_trajectoires_geographiques_gardent_leur_groupement() -> None:
    """CONTRE-EPREUVE : la reparation du 05/08 (perimetre) tient toujours.

    `marche_national_taille` et `marche_national_projection` n'ont pas de
    suffixe annuel : ils retombent sur le perimetre, comme avant. Le correctif
    du BP ne doit pas recasser les courbes de marche de l'EM (regle 6,
    contre-epreuve).
    """
    donnees = [
        _national("marche_national_taille", 4_400_000_000, 2026),
        _national("marche_national_projection", 5_100_000_000, 2028),
    ]

    series = series_par_perimetre(donnees, [d.valeur for d in donnees], [2026, 2028])

    assert len(series) == 1
    assert series[0][1] == [4_400_000_000.0, 5_100_000_000.0]


def test_marche_et_previsionnel_coexistent_dans_une_figure() -> None:
    """Un perimetre et un radical dans la meme figure : deux series.

    « Marche national vs CA du projet » est exactement la figure qu'un
    chapitre 6 de business plan appelle.
    """
    donnees = [
        _national("marche_national_taille", 4_000_000, 2026),
        _national("marche_national_projection", 4_600_000, 2028),
        _entreprise("ca_previsionnel_an1", 135_000, 2026),
        _entreprise("ca_previsionnel_an3", 320_000, 2028),
    ]

    series = series_par_perimetre(donnees, [d.valeur for d in donnees], [2026, 2028])

    assert len(series) == 2


def test_une_serie_annuelle_trouee_reste_ecartee() -> None:
    """CONTRE-EPREUVE : pas d'interpolation. Une pente inventee est un mensonge."""
    donnees = [
        _entreprise("ca_previsionnel_an1", 135_000, 2026),
        # an2 manquant.
        _entreprise("ca_previsionnel_an3", 320_000, 2028),
        _entreprise("resultat_net_an1", -12_000, 2026),
        _entreprise("resultat_net_an2", 24_000, 2027),
        _entreprise("resultat_net_an3", 61_000, 2028),
    ]

    series = series_par_perimetre(
        donnees, [d.valeur for d in donnees], [2026, 2027, 2028]
    )

    assert len(series) == 1
    assert series[0][1] == [-12_000.0, 24_000.0, 61_000.0]


def test_le_previsionnel_se_dessine_de_bout_en_bout() -> None:
    """Du socle a la resolution `courbes`, comme le rendu la demandera.

    C'est la verification « hors ligne, sans un appel au modele » que la
    methode du 05/08 impose avant toute generation payante.
    """
    socle = _socle(*_donnees_du_previsionnel())

    resolution = resoudre(socle, "courbes", [
        "ca_previsionnel_an1", "ca_previsionnel_an2", "ca_previsionnel_an3",
        "resultat_net_an1", "resultat_net_an2", "resultat_net_an3",
    ])

    assert resolution.donnees is not None, resolution.motif
    assert len(resolution.donnees["series"]) == 2

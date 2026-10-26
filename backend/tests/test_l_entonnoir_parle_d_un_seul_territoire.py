"""Le TAM, le SAM et le SOM doivent parler du même territoire.

26/10/2026, étude de marché à l'export relevée par la cliente : « pour un
projet qui vend à l'export, le TAM retenu était le marché français du
e-commerce alimentaire, et le SAM était constitué des exportations. Le SAM
n'est donc pas un sous-ensemble du TAM. Le ratio SAM = 23,5 % du TAM n'a pas de
sens, et il est pourtant répété partout. »

`_controler_emboitement_marche` ne pouvait pas le voir : il compare des
MONTANTS. Un SAM à l'export qui pèse moins que le marché intérieur français
satisfait TAM ≥ SAM sans difficulté. Les deux nombres étaient ordonnés ; ils ne
parlaient simplement pas du même monde — et le ratio qui en sort est
arithmétiquement impeccable et sémantiquement vide.
"""
from __future__ import annotations

from datetime import date

from catalog.models import DeliverableType
from generation.socle.referentiel import Fiabilite, Perimetre, definition
from generation.socle.schema import (
    DonneeSocle,
    Socle,
    Zone,
    _controler_emboitement_marche,
    _controler_territoire_de_l_entonnoir,
    valider_socle,
)


def _donnee(
    identifiant: str,
    valeur: float,
    perimetre: Perimetre,
    annee: int = 2025,
) -> DonneeSocle:
    return DonneeSocle(
        id=identifiant,
        libelle=identifiant.upper(),
        valeur=valeur,
        unite="MdEUR",
        annee=annee,
        perimetre=perimetre,
        fiabilite=Fiabilite.ESTIMEE,
    )


def _socle(*donnees: DonneeSocle) -> Socle:
    return Socle(
        secteur="e-commerce alimentaire",
        zone=Zone(pays="France"),
        date_socle=date(2026, 10, 26),
        donnees=list(donnees),
    )


#: Le socle du défaut, et il est ATTEIGNABLE : `som` y garde le seul périmètre
#: que le référentiel lui admet (`entreprise`). Une première version le posait
#: sur `monde` — un socle que `valider_socle` refuse de toute façon pour une
#: autre raison, donc un test qui ne verrouillait rien de réel (règle 6).
def _socle_a_l_export() -> Socle:
    return _socle(
        _donnee("tam", 10.0, Perimetre.NATIONAL),
        _donnee("sam", 2.35, Perimetre.MONDE),
        _donnee("som", 0.05, Perimetre.ENTREPRISE),
    )


def test_le_defaut_mesure_est_refuse() -> None:
    """TAM national (marché français), SAM mondial (les exportations)."""
    motifs = _controler_territoire_de_l_entonnoir(_socle_a_l_export())
    assert motifs, "un SAM mondial sous un TAM national doit être refusé"
    assert "`sam`" in motifs[0]
    # Le motif doit dire QUOI corriger, et de quel côté (règle 2).
    assert "TAM" in motifs[0]


def test_le_defaut_est_refuse_par_le_chemin_de_production() -> None:
    """Le même socle, jugé par `valider_socle` — le seul chemin réel.

    Un contrôle qui n'est atteint que par un appel direct ne protège rien :
    c'est `valider_socle` que le builder appelle.
    """
    motifs = valider_socle(_socle_a_l_export(), DeliverableType.MARKET_STUDY)
    assert any("plus large" in m for m in motifs), motifs


def test_les_montants_seuls_ne_voyaient_rien() -> None:
    """Le contrôle d'avant, rejoué sur le même socle : il ne trouve rien.

    C'est ce qui rend le nouveau contrôle nécessaire et non redondant
    (règle 6 : un test doit échouer sur le code d'avant).
    """
    assert _controler_emboitement_marche(_socle_a_l_export()) == []


def test_un_entonnoir_sur_un_seul_territoire_passe() -> None:
    """Contre-épreuve : trois étages sur la même zone ne déclenchent rien."""
    socle = _socle(
        _donnee("tam", 10.0, Perimetre.NATIONAL),
        _donnee("sam", 2.35, Perimetre.NATIONAL),
        _donnee("som", 0.05, Perimetre.NATIONAL),
    )
    assert _controler_territoire_de_l_entonnoir(socle) == []


def test_un_entonnoir_qui_se_resserre_passe() -> None:
    """Contre-épreuve : du mondial vers le national vers le régional, c'est juste.

    C'est l'entonnoir CORRECT d'un projet à l'export : on part du marché
    mondial adressable, on resserre sur les pays visés, puis sur la part
    réellement captable.
    """
    socle = _socle(
        _donnee("tam", 100.0, Perimetre.MONDE),
        _donnee("sam", 10.0, Perimetre.CONTINENT),
        _donnee("som", 0.5, Perimetre.NATIONAL),
    )
    assert _controler_territoire_de_l_entonnoir(socle) == []


def test_deux_etages_a_plus_d_un_an_d_ecart_sont_refuses() -> None:
    """Un ratio entre un TAM 2023 et un SAM 2026 mélange deux états du marché."""
    socle = _socle(
        _donnee("tam", 10.0, Perimetre.NATIONAL, annee=2023),
        _donnee("sam", 2.35, Perimetre.NATIONAL, annee=2026),
    )
    motifs = _controler_territoire_de_l_entonnoir(socle)
    assert any("écart" in m for m in motifs), motifs


def test_un_som_projete_loin_du_tam_mesure_ne_declenche_rien() -> None:
    """Contre-épreuve : le SOM est une PROJECTION, pas une mesure de marché.

    Un TAM publié en 2024 et un SOM d'année 1 en 2027 forment un socle
    parfaitement correct — c'est même ce que la consigne du dépôt demande pour
    un projet non encore lancé. Une version précédente les comparait, et comme
    `tam`, `sam` et `som` sont OBLIGATOIRES, le motif survivait aux trois
    tentatives : le dossier mourait à zéro chapitre.
    """
    socle = _socle(
        _donnee("tam", 10.0, Perimetre.NATIONAL, annee=2024),
        _donnee("sam", 2.35, Perimetre.NATIONAL, annee=2025),
        _donnee("som", 0.05, Perimetre.ENTREPRISE, annee=2027),
    )
    assert _controler_territoire_de_l_entonnoir(socle) == []


def test_un_an_d_ecart_reste_admis() -> None:
    """Contre-épreuve : deux publications ne sortent jamais le même mois.

    Refuser un décalage d'un an tuerait des études pour un écart que le lecteur
    ne verrait même pas — et ce dépôt a mesuré ce que coûte une règle trop
    stricte.
    """
    socle = _socle(
        _donnee("tam", 10.0, Perimetre.NATIONAL, annee=2024),
        _donnee("sam", 2.35, Perimetre.NATIONAL, annee=2025),
    )
    assert _controler_territoire_de_l_entonnoir(socle) == []


def test_le_socle_peut_exprimer_un_projet_a_l_export() -> None:
    """Sans cela, le contrôle ci-dessus serait décoratif (règle 1).

    Le référentiel n'admettait que « national » pour le TAM comme pour le SAM.
    Un socle ne POUVAIT donc pas déclarer un SAM mondial : le contrôle
    d'emboîtement n'aurait jamais eu rien à refuser, et il aurait rendu un
    succès sur toutes les études — la forme exacte du défaut que la règle 1
    interdit.

    Pire, l'échelle unique est ce qui a PRODUIT le défaut : « national » ne dit
    pas QUELLE nation, et un projet qui vend de la France vers la Corée n'avait
    aucune façon correcte de se décrire.
    """
    tam = definition(DeliverableType.MARKET_STUDY, "tam")
    sam = definition(DeliverableType.MARKET_STUDY, "sam")
    assert tam is not None and sam is not None, "TAM et SAM sont au référentiel"
    admis_tam, admis_sam = tam.admis, sam.admis
    assert Perimetre.CONTINENT in admis_tam, admis_tam
    assert Perimetre.MONDE in admis_tam, admis_tam
    assert Perimetre.MONDE in admis_sam, admis_sam


def test_un_entonnoir_incomplet_ne_declenche_rien() -> None:
    """Contre-épreuve : avec un seul étage, il n'y a rien à comparer."""
    socle = _socle(_donnee("tam", 10.0, Perimetre.NATIONAL))
    assert _controler_territoire_de_l_entonnoir(socle) == []
    assert _controler_territoire_de_l_entonnoir(_socle()) == []


def test_un_tam_mondial_n_ecrase_pas_le_marche_mondial_dans_les_figures() -> None:
    """Deux grandeurs d'un même périmètre ne doivent pas se confondre en figure.

    `cle_de_serie` groupe par PÉRIMÈTRE pour qu'une trajectoire se trace à
    partir de deux identifiants (`marche_mondial_taille` puis
    `marche_mondial_projection`). En ouvrant le TAM au périmètre « monde », le
    TAM rejoignait cette clé : à année égale, l'un écrasait l'autre en silence
    — le dernier gagne, sous la légende du premier (relecture du 26/10/2026).
    """
    from generation.rendu_word.donnees_graphiques import cle_de_serie

    tam = _donnee("tam", 100.0, Perimetre.MONDE)
    marche = _donnee("marche_mondial_taille", 4000.0, Perimetre.MONDE)
    assert cle_de_serie(tam) != cle_de_serie(marche)
    # Et la trajectoire du marché mondial continue de se former : deux
    # identifiants du même périmètre restent UNE série (contre-épreuve).
    projection = _donnee("marche_mondial_projection", 6000.0, Perimetre.MONDE)
    assert cle_de_serie(marche) == cle_de_serie(projection)

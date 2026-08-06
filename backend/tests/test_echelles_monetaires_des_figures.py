"""Une monnaie a trois echelles n'est pas trois unites.

Mesure decisive, generation reelle `18ce3fca` du 05/08/2026 — rendue possible
par l'incident qui conserve desormais les motifs d'abandon :

    demandes=14  rendus=2

    Chapitre  9 · Du marche national au marche atteignable
                  unites heterogenes : EUR, MEUR, MdEUR
    Chapitre 14 · TAM, SAM, SOM et premiere marche
                  unites heterogenes : EUR, MEUR, MdEUR
    Chapitre 15 · De la joaillerie francaise au marche atteignable
                  unites heterogenes : EUR, MEUR, MdEUR
    Chapitre 17 · TAM, SAM, SOM appliques a la priorisation
                  unites heterogenes : EUR, MEUR, MdEUR

**Onze abandons sur douze pour « unites heterogenes »**, dont six listaient une
seule monnaie a plusieurs echelles. `_unite_commune` comparait les unites comme
des CHAINES : `{"EUR", "MEUR", "MdEUR"}` faisait trois unites, donc abandon.

Le moteur refusait donc de dessiner l'entonnoir TAM / SAM / SOM — la figure la
plus attendue d'une etude de marche — parce qu'il ne savait pas que mille
millions font un milliard.

La conversion existait pourtant depuis le lot 1, complete, dans
`socle.schema.valeur_en_unites_de_base`, qui decompose `MdEUR` en magnitude et
devise. Ce module ne l'appelait pas : le defaut de la regle 8 applique a une
fonction plutot qu'a un service.

Contre-epreuve, verifiee ci-dessous : ce qui doit rester refuse l'est. Deux
DEVISES sans taux de change, et un taux a cote d'un montant, produiraient une
figure fausse dont chaque chiffre est juste.
"""
from __future__ import annotations

from datetime import date

import pytest

from generation.rendu_word.donnees_graphiques import resoudre
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Zone


def _donnee(identifiant: str, valeur: float, unite: str) -> DonneeSocle:
    return DonneeSocle(
        id=identifiant,
        libelle=f"Libellé de {identifiant}",
        valeur=valeur,
        unite=unite,
        annee=2026,
        perimetre=Perimetre.NATIONAL,
        fiabilite=Fiabilite.ESTIMEE,
    )


def _mondial(identifiant: str, valeur: float, annee: int) -> DonneeSocle:
    return DonneeSocle(
        id=identifiant, libelle=f"Marché mondial — {identifiant}", valeur=valeur,
        unite="MdEUR", annee=annee, perimetre=Perimetre.MONDE,
        fiabilite=Fiabilite.ESTIMEE,
    )


def _continental(identifiant: str, valeur: float, annee: int) -> DonneeSocle:
    return DonneeSocle(
        id=identifiant, libelle=f"Marché européen — {identifiant}", valeur=valeur,
        unite="MdEUR", annee=annee, perimetre=Perimetre.CONTINENT,
        fiabilite=Fiabilite.ESTIMEE,
    )


def _socle(*donnees: DonneeSocle) -> Socle:
    return Socle(
        secteur="joaillerie de créateurs",
        zone=Zone(pays="France", ville="Paris"),
        date_socle=date(2026, 8, 5),
        donnees=list(donnees),
    )


# ── L'entonnoir TAM / SAM / SOM, qui n'était jamais dessiné ──────────────────


def test_un_entonnoir_en_trois_echelles_d_euros_est_dessine() -> None:
    """LE cas qui a coûté six figures sur la génération réelle.

    Sur le code d'avant : « unités hétérogènes : EUR, MEUR, MdEUR », abandon.

    Ce que le LECTEUR voit est vérifié ici, et pas seulement la valeur interne :
    chaque marche porte sa propre échelle, parce qu'un entonnoir n'a pas d'axe
    commun. « 1,8 M€ », jamais « 0,0018 Md€ » — ni, comme le livrable réel
    `4b827759` l'a montré, « 3.2e+11 kEUR ».
    """
    socle = _socle(
        _donnee("tam", 1.2, "MdEUR"),
        _donnee("sam", 240.0, "MEUR"),
        _donnee("som", 1_800_000.0, "EUR"),
    )

    resolution = resoudre(socle, "entonnoir", ["tam", "sam", "som"])

    assert resolution.retenu, resolution.motif
    affichees = resolution.donnees["valeurs_affichees"]  # type: ignore[index]
    assert affichees == ["1.2 MdEUR", "240 MEUR", "1.8 MEUR"], affichees
    # Aucune notation scientifique nulle part.
    assert not any("e+" in texte or "e-" in texte for texte in affichees)


def test_l_echelle_d_un_axe_garde_le_sommet_lisible() -> None:
    """Un axe, lui, exige UNE unité commune : on choisit celle du sommet.

    C'est la seule règle qui interdit mécaniquement la notation scientifique.
    Celle qu'elle remplace — « l'échelle qui laisse le plus de valeurs
    au-dessus de 1 » — a produit `3.2e+11 kEUR` sur le livrable `4b827759` :
    elle optimisait les petites valeurs au prix des grandes.
    """
    socle = _socle(
        _donnee("mondial", 300.0, "MdEUR"),
        _donnee("national", 4_500.0, "MEUR"),
    )

    resolution = resoudre(socle, "barres", ["mondial", "national"])

    assert resolution.retenu, resolution.motif
    valeurs = resolution.donnees["valeurs"]  # type: ignore[index]
    assert valeurs == pytest.approx([300.0, 4.5])
    assert 1 <= max(valeurs) < 1000, valeurs


def test_une_unite_unique_traverse_sans_conversion() -> None:
    """Contre-épreuve : le cas normal ne doit rien changer aux valeurs."""
    socle = _socle(
        _donnee("croissance_monde", 5.5, "%"),
        _donnee("croissance_france", 7.0, "%"),
    )

    resolution = resoudre(socle, "barres", ["croissance_monde", "croissance_france"])

    assert resolution.retenu, resolution.motif
    assert resolution.donnees["valeurs"] == pytest.approx([5.5, 7.0])  # type: ignore[index]


# ── Ce qui doit RESTER refusé ────────────────────────────────────────────────


def test_deux_devises_restent_refusees() -> None:
    """Sans taux de change, l'euro et le dollar sur un axe font une figure fausse."""
    socle = _socle(
        _donnee("marche_europe", 90.0, "MdEUR"),
        _donnee("marche_us", 120.0, "MdUSD"),
    )

    resolution = resoudre(socle, "barres", ["marche_europe", "marche_us"])

    assert not resolution.retenu
    assert "hétérogènes" in resolution.motif


def test_un_taux_a_cote_d_un_montant_reste_refuse() -> None:
    """Deux NATURES de grandeur, pas deux échelles d'une même grandeur."""
    socle = _socle(
        _donnee("taille_marche", 90.0, "MdEUR"),
        _donnee("croissance", 5.5, "%"),
    )

    resolution = resoudre(socle, "barres", ["taille_marche", "croissance"])

    assert not resolution.retenu
    assert "hétérogènes" in resolution.motif


def test_une_trajectoire_sur_deux_perimetres_donne_deux_series() -> None:
    """Les courbes etaient STRUCTURELLEMENT infaisables.

    Le socle interdit les doublons — « un identifiant, une seule valeur » — et
    chaque donnee porte UNE annee. Une courbe « mondial 2026 -> 2035 » se
    declare donc avec deux identifiants : `..._taille` et `..._projection`.
    Le resolveur groupait par LIBELLE : deux identifiants, deux libelles, deux
    series d'un seul point, aucune couvrant les deux annees, toutes ecartees.
    Motif rendu : « aucune serie complete ».

    Quatre formes sur quinze — courbes, aires, barres groupees, barres
    empilees, les plus attendues d'une etude de marche — ne pouvaient donc
    JAMAIS etre dessinees. Mesure du 05/08/2026, hors ligne et sans un appel au
    modele.

    Le regroupement se fait desormais par PERIMETRE, qui vient du referentiel :
    la taille d'un marche et sa projection le partagent par construction.
    """
    socle = _socle(
        _mondial("marche_mondial_taille", 310.0, 2026),
        _mondial("marche_mondial_projection", 480.0, 2035),
        _continental("marche_continental_taille", 96.0, 2026),
        _continental("marche_continental_projection", 141.0, 2035),
    )

    resolution = resoudre(socle, "courbes", [
        "marche_mondial_taille", "marche_mondial_projection",
        "marche_continental_taille", "marche_continental_projection",
    ])

    assert resolution.retenu, resolution.motif
    series = resolution.donnees["series"]  # type: ignore[index]
    assert len(series) == 2, series
    assert resolution.donnees["abscisses"] == ["2026", "2035"]  # type: ignore[index]
    valeurs = {nom: points for nom, points in series}
    assert list(valeurs.values())[0] == pytest.approx([310.0, 480.0])


def test_une_serie_trouee_reste_ecartee() -> None:
    """Contre-epreuve : une valeur manquante ne s'interpole pas.

    Une pente inventee entre deux points reels est un mensonge invisible.
    """
    socle = _socle(
        _mondial("marche_mondial_taille", 310.0, 2026),
        _mondial("marche_mondial_projection", 480.0, 2035),
        _continental("marche_continental_taille", 96.0, 2026),
    )

    resolution = resoudre(socle, "courbes", [
        "marche_mondial_taille", "marche_mondial_projection",
        "marche_continental_taille",
    ])

    assert resolution.retenu, resolution.motif
    # Seul le perimetre MONDE couvre les deux annees.
    assert len(resolution.donnees["series"]) == 1  # type: ignore[index]


def test_la_derniere_marche_d_un_entonnoir_reste_visible() -> None:
    """Un TAM/SAM/SOM enjambe plusieurs ordres de grandeur.

    Largeur strictement proportionnelle : marche national 4 200 M€, parisien
    240 M€, atteignable 1,8 M€ — la troisieme marche n'avait AUCUN pixel. Le
    lecteur ne voyait pas qu'une troisieme etape existait. Une figure qui efface
    une de ses donnees est fausse, quelle que soit la rigueur du calcul.

    La largeur porte desormais l'ORDRE ; le chiffre, exact, est ecrit sur chaque
    marche.
    """
    from generation.rendu_word.graphiques import (
        _ENTONNOIR_LARGEUR_MIN,
        entonnoir,
    )
    from generation.rendu_word.palette import construire_palette

    assert _ENTONNOIR_LARGEUR_MIN >= 0.2, (
        "une marche sous 20 % de la largeur redevient illisible"
    )
    png = entonnoir(
        construire_palette(primaire="#1A1A1A", secondaire="#C9A227", fond_clair=""),
        [("Marché national", 4200.0), ("Marché parisien", 240.0),
         ("Marché atteignable", 1.8)],
        unite=" MEUR",
    )
    assert png.startswith(b"\x89PNG")
    assert len(png) > 5_000


def test_deux_baremes_de_notes_restent_refuses() -> None:
    """`note_sur_5` et `note_sur_10` ne sont pas deux échelles : deux barèmes.

    Les ramener l'un à l'autre changerait le sens des notes du radar.
    """
    socle = _socle(
        _donnee("critere_a", 4.0, "note_sur_5"),
        _donnee("critere_b", 8.0, "note_sur_10"),
        _donnee("critere_c", 3.0, "note_sur_5"),
    )

    resolution = resoudre(socle, "radar", ["critere_a", "critere_b", "critere_c"])

    assert not resolution.retenu
    assert "notation" in resolution.motif or "notés" in resolution.motif

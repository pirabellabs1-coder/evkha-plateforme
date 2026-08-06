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
    """
    socle = _socle(
        _donnee("tam", 1.2, "MdEUR"),
        _donnee("sam", 240.0, "MEUR"),
        _donnee("som", 1_800_000.0, "EUR"),
    )

    resolution = resoudre(socle, "entonnoir", ["tam", "sam", "som"])

    assert resolution.retenu, resolution.motif
    etapes = resolution.donnees["etapes"]  # type: ignore[index]
    # Tout est ramené à la plus grande échelle présente : 1,2 Md€ = 1 200 M€…
    valeurs = [valeur for _libelle, valeur in etapes]
    assert valeurs == pytest.approx([1200.0, 240.0, 1.8])
    assert resolution.donnees["unite"].strip() == "MEUR"  # type: ignore[index]


def test_l_echelle_retenue_est_celle_du_plus_grand_montant() -> None:
    """Un axe en euros pour des milliards serait illisible, et l'inverse aussi."""
    socle = _socle(
        _donnee("mondial", 300.0, "MdEUR"),
        _donnee("national", 4_500.0, "MEUR"),
    )

    resolution = resoudre(socle, "barres", ["mondial", "national"])

    assert resolution.retenu, resolution.motif
    assert resolution.donnees["valeurs"] == pytest.approx([300.0, 4.5])  # type: ignore[index]


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

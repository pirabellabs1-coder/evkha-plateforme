"""Les titres doivent etre navigables, les figures lisibles.

Mesure sur le PREMIER livrable reel complet — job `90cbb3d9`, 05/08/2026,
23 chapitres, 3,32 EUR — ouvert et compare a `references/joalie_2026.docx` :

    style                        usages   niveau plan
    Etude Corps                     115             —
    Etude Tableau en-tete            70             —      <- titres de section
    Etude Bandeau                 1 + 22            —      <- titres de chapitre
    ...
    paragraphes navigables            0
    (modele valide : 83)

Trois defauts distincts, tous invisibles a la relecture du code :

1. **`sous_titre()` posait le style des EN-TETES DE TABLEAU** sur les titres de
   section, pendant que « Etude Titre section », defini pour cet usage exact,
   n'etait employe NULLE PART. Word affiche le nom du style dans son ruban :
   le lecteur qui cliquait dans un titre y lisait « tableau ».

2. **Aucun style ne portait de niveau de plan.** C'est `w:outlineLvl`, et rien
   d'autre, qui fait qu'un paragraphe entre dans le volet de navigation et dans
   une table des matieres automatique. Les 22 titres etaient parfaitement
   visibles a l'oeil et le document restait sans structure navigable.

3. **« Etude Titre chapitre » etait exige de tout gabarit et employe nulle
   part** : les titres de chapitre vivent dans le bandeau colore. Deux styles
   pour une meme verite, dont un mort (regles 5 et 8).

Et sur les figures : les etiquettes d'axe portaient le `libelle` COMPLET du
socle — 96 signes — qui se chevauchaient et debordaient de l'image.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from docx import Document
from docx.oxml.ns import qn

from generation.rendu_word import gabarit
from generation.rendu_word.donnees_graphiques import ETIQUETTE_MAX, etiquette_de
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle


def _donnee(libelle: str) -> DonneeSocle:
    return DonneeSocle(
        id="marche_mondial_croissance",
        libelle=libelle,
        valeur=5.5,
        unite="%",
        annee=2026,
        perimetre=Perimetre.MONDE,
        fiabilite=Fiabilite.ESTIMEE,
    )


# ── Les etiquettes de figure ─────────────────────────────────────────────────


def test_une_etiquette_trop_longue_est_ramenee_a_sa_tete() -> None:
    """LE libelle qui a produit les deux figures illisibles du livrable reel.

    Le segment de queue — « ordre de grandeur sectoriel luxe/joaillerie » —
    est ecarte : il precise la methode, pas la grandeur, et n'a rien a faire
    sur un axe.
    """
    donnee = _donnee(
        "Croissance annuelle estimée du marché mondial de la joaillerie, "
        "ordre de grandeur sectoriel luxe/joaillerie"
    )

    etiquette = etiquette_de(donnee)

    assert etiquette.startswith("Croissance annuelle")
    assert "ordre de grandeur" not in etiquette
    # Chaque LIGNE tient dans la largeur ; le tout peut en occuper deux.
    lignes = etiquette.split("\n")
    assert len(lignes) <= 2, etiquette
    assert all(len(ligne) <= ETIQUETTE_MAX for ligne in lignes), etiquette


def test_une_etiquette_deja_courte_traverse_intacte() -> None:
    """Contre-epreuve : on ne mutile pas ce qui est deja lisible."""
    assert etiquette_de(_donnee("Croissance du marché français")) == (
        "Croissance du marché français"
    )


def test_une_etiquette_longue_est_REPLIEE_et_non_tronquee() -> None:
    """Le document valide replie ses etiquettes, il ne les coupe pas.

    Il ecrit « Attractivité du / segment » et « Capacité de / preuve » sur deux
    lignes. Couper a « Marché parisien de la joaillerie… » ferait perdre au
    lecteur precisement ce qui distingue cette barre de la suivante.

    Ce test echoue sur la version d'avant, qui rendait une seule ligne suivie
    de points de suspension.
    """
    libelle = "Chiffre affaires prévisionnel consolidé du réseau national"

    etiquette = etiquette_de(_donnee(libelle))

    assert "\n" in etiquette, etiquette
    # Rien n'est perdu : tous les mots du libelle se retrouvent dans l'etiquette.
    assert etiquette.replace("\n", " ") == libelle
    # Aucun mot coupe en plein milieu.
    for mot in etiquette.replace("\n", " ").split():
        assert mot in libelle


def test_l_identifiant_technique_ne_sert_jamais_d_etiquette() -> None:
    """`marche_mondial_croissance` est un repere de code, pas un mot de lecteur."""
    assert "_" not in etiquette_de(_donnee("Croissance du marché mondial"))


# ── Les titres, et leur navigabilite ─────────────────────────────────────────


@pytest.fixture
def gabarit_neuf(tmp_path: Path) -> Any:
    chemin = gabarit.construire_gabarit(tmp_path / "gabarit.docx")
    return Document(str(chemin))


def _niveau_plan(document: Any, nom: str) -> str | None:
    ppr = document.styles[nom].element.find(qn("w:pPr"))
    if ppr is None:
        return None
    lvl = ppr.find(qn("w:outlineLvl"))
    return None if lvl is None else str(lvl.get(qn("w:val")))


def test_les_styles_de_titre_portent_un_niveau_de_plan(gabarit_neuf: Any) -> None:
    """Sans `outlineLvl`, Word ne tient pas un paragraphe pour un titre.

    Sur le gabarit d'avant, ces deux appels renvoyaient None et le livrable
    reel comptait ZERO entree navigable contre 83 au modele valide.
    """
    assert _niveau_plan(gabarit_neuf, gabarit.STYLE_BANDEAU) == "0"
    assert _niveau_plan(gabarit_neuf, gabarit.STYLE_SECTION) == "1"


def test_le_corps_n_entre_pas_dans_la_table_des_matieres(gabarit_neuf: Any) -> None:
    """Contre-epreuve : on n'a pas transforme tout le document en titres."""
    for nom in (gabarit.STYLE_CORPS, gabarit.STYLE_TABLEAU_CELLULE,
                gabarit.STYLE_SOURCE, gabarit.STYLE_LEGENDE):
        assert _niveau_plan(gabarit_neuf, nom) is None, nom


def test_le_gabarit_n_exige_plus_de_style_mort() -> None:
    """« Étude Titre chapitre » etait exige de tout gabarit et jamais employe."""
    assert "Étude Titre chapitre" not in gabarit.STYLES_ATTENDUS


def test_le_titre_de_section_emploie_le_style_prevu_pour_lui() -> None:
    """Il portait le style des en-tetes de TABLEAU, nom compris."""
    import inspect

    from generation.rendu_word import composants

    source = inspect.getsource(composants.sous_titre)
    assert "STYLE_SECTION" in source
    assert "STYLE_TABLEAU_ENTETE" not in source

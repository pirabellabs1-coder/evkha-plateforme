"""Lot 0 — moteur de rendu documentaire.

Ces tests n'attrapent pas tout : l'œil reste juge. Ils attrapent les
**régressions** — un composant qui perd sa couleur, un tableau dont la largeur
repasse en pourcentage, une police par défaut qui réapparaît.

La référence est `references/joalie_2026.docx`, versionnée dans le dépôt.
Chaque comparaison se fait contre elle, jamais contre des valeurs recopiées.
"""
from __future__ import annotations

import collections
import re
import statistics
import zipfile
from pathlib import Path
from typing import Any

import pytest

from generation.rendu_word import composants, graphiques, secteurs
from generation.rendu_word.depuis_json import BlocInconnuError, rendre_etude
from generation.rendu_word.fixture import construire_fixture
from generation.rendu_word.gabarit import charger_gabarit
from generation.rendu_word.palette import (
    REF_CREME,
    REF_CREME_ALT,
    REF_FOND_GRAPHIQUE,
    REF_OR_BRONZE,
    REF_PRUNE,
    REF_PRUNE_FONCE,
    REF_ROSE_GRISE,
    REF_ROSE_PALE,
    construire_palette,
)

RACINE = Path(__file__).resolve().parents[2]
REFERENCE = RACINE / "references" / "joalie_2026.docx"

#: Tolérance sur les volumes. Le contenu est factice : on vise l'ordre de
#: grandeur de la référence, pas l'égalité stricte.
TOLERANCE = 0.30


def _profil(chemin: Path) -> dict[str, Any]:
    with zipfile.ZipFile(chemin) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
        medias = [n for n in archive.namelist() if n.startswith("word/media/")]

    tables = re.findall(r"<w:tbl>.*?</w:tbl>", xml, re.S)

    def lignes(table: str) -> int:
        return len(re.findall(r"<w:tr(?:\s[^>]*)?>.*?</w:tr>", table, re.S))

    def cellules(table: str) -> int:
        return len(re.findall(r"<w:tc(?:\s[^>]*)?>.*?</w:tc>", table, re.S))

    formes = collections.Counter((lignes(t), cellules(t)) for t in tables)
    return {
        "paragraphes": len(re.findall(r"<w:p[ >]", xml)),
        "tableaux": len(tables),
        "bandeaux": formes[(1, 1)],
        "encadres": formes[(1, 2)],
        "grilles": formes[(1, 3)],
        "sauts": xml.count('w:type="page"'),
        "images": len(medias),
        "fonds": collections.Counter(re.findall(r'w:fill="([0-9A-Fa-f]{6})"', xml)),
        "polices": set(re.findall(r'w:ascii="([^"]+)"', xml)),
        "xml": xml,
    }


@pytest.fixture(scope="module")
def demo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    destination = tmp_path_factory.mktemp("lot0") / "demo.docx"
    return rendre_etude(construire_fixture(), destination)


@pytest.fixture(scope="module")
def profil_demo(demo: Path) -> dict[str, Any]:
    return _profil(demo)


@pytest.fixture(scope="module")
def profil_reference() -> dict[str, Any]:
    if not REFERENCE.is_file():
        pytest.skip(f"Référence absente : {REFERENCE}")
    return _profil(REFERENCE)


# ── Le document se produit ───────────────────────────────────────────────────


def test_la_fixture_couvre_vingt_deux_chapitres() -> None:
    etude = construire_fixture()
    assert len(etude["chapitres"]) == 22
    assert sum(len(c["blocs"]) for c in etude["chapitres"]) > 250


def test_le_livrable_est_produit(demo: Path) -> None:
    assert demo.is_file()
    assert demo.stat().st_size > 200_000, "Volume trop faible pour 22 chapitres."


# ── Conformité de structure à la référence ───────────────────────────────────


def test_un_bandeau_par_chapitre_du_client(
    profil_demo: dict[str, Any], profil_reference: dict[str, Any]
) -> None:
    """Exigence exacte, pas approchée : un bandeau par chapitre RENDU.

    Vingt-et-un, et non vingt-deux : la fiche projet (chapitre 0) est la carte
    d'identité interne de la commande et ne part plus chez le client. Elle
    était déjà absente du sommaire ; elle l'est désormais aussi du corps.

    Le document de RÉFÉRENCE, lui, en porte vingt-deux : c'est le `.docx` de la
    cliente, que notre code ne touche pas. L'écart attendu est donc exactement
    d'un bandeau, et c'est celui-là qu'on vérifie — écrire « les deux sont
    égaux » reviendrait à réclamer l'impression de la fiche interne.
    """
    attendu = len([c for c in construire_fixture()["chapitres"] if c["numero"] > 0])
    assert attendu == 21
    assert profil_demo["bandeaux"] == attendu
    assert profil_reference["bandeaux"] - profil_demo["bandeaux"] == 1, (
        "l'écart au document de référence n'est plus la seule fiche projet : "
        f"référence {profil_reference['bandeaux']}, rendu {profil_demo['bandeaux']}"
    )


def test_les_grilles_de_chiffres_cles_sont_au_bon_nombre(
    profil_demo: dict[str, Any], profil_reference: dict[str, Any]
) -> None:
    assert profil_demo["grilles"] == profil_reference["grilles"]


@pytest.mark.parametrize("mesure", ["paragraphes", "tableaux", "encadres", "sauts"])
def test_les_volumes_sont_de_l_ordre_de_la_reference(
    mesure: str, profil_demo: dict[str, Any], profil_reference: dict[str, Any]
) -> None:
    attendu = profil_reference[mesure]
    obtenu = profil_demo[mesure]
    ratio = obtenu / max(attendu, 1)
    assert 1 - TOLERANCE <= ratio <= 1 + TOLERANCE, (
        f"{mesure} : {obtenu} contre {attendu} dans la référence (ratio {ratio:.2f})."
    )


# ── Densité éditoriale ───────────────────────────────────────────────────────
# Le défaut le plus visible de la première version n'était ni une couleur ni une
# forme : c'était un MUR DE TEXTE. 26 758 mots au lieu de 10 129, une médiane de
# 112 mots par paragraphe au lieu de 12, et 15 % des mots dans les tableaux au
# lieu de 52 %. Retour de la cliente : « toujours trop de texte ».
# Ces trois mesures sont donc verrouillées ici.


def _prose(xml: str) -> list[str]:
    """Paragraphes hors tableaux : la prose courante, pas le contenu des cellules."""
    corps = re.search(r"<w:body>(.*)</w:body>", xml, re.S)
    assert corps is not None
    hors_tableaux = re.sub(r"<w:tbl>.*?</w:tbl>", "", corps.group(1), flags=re.S)
    textes = []
    for paragraphe in re.findall(r"<w:p[ >].*?</w:p>", hors_tableaux, re.S):
        texte = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", paragraphe)).strip()
        if texte:
            textes.append(texte)
    return textes


def _tous_les_mots(xml: str) -> int:
    return len("".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml)).split())


def test_le_document_n_est_pas_un_mur_de_texte(
    profil_demo: dict[str, Any], profil_reference: dict[str, Any]
) -> None:
    """Le volume total reste de l'ordre de celui de la référence."""
    attendu = _tous_les_mots(profil_reference["xml"])
    obtenu = _tous_les_mots(profil_demo["xml"])
    assert obtenu <= attendu * 1.3, (
        f"{obtenu} mots contre {attendu} dans la référence : le document est trop bavard."
    )


def test_les_paragraphes_restent_courts(profil_demo: dict[str, Any]) -> None:
    """Médiane de 12 mots dans la référence. On tolère jusqu'à 30."""
    longueurs = [len(t.split()) for t in _prose(profil_demo["xml"])]
    mediane = statistics.median(longueurs)
    assert mediane <= 30, f"Médiane de {mediane} mots : les paragraphes sont trop longs."


def test_peu_de_paragraphes_longs(profil_demo: dict[str, Any]) -> None:
    """12 % de paragraphes de plus de 60 mots dans la référence."""
    longueurs = [len(t.split()) for t in _prose(profil_demo["xml"])]
    part = sum(1 for n in longueurs if n > 60) / max(len(longueurs), 1)
    assert part <= 0.25, f"{part:.0%} de paragraphes longs : trop de blocs massifs."


def test_l_information_vit_dans_les_tableaux(
    profil_demo: dict[str, Any], profil_reference: dict[str, Any]
) -> None:
    """52 % des mots de la référence sont dans des tableaux, pas dans la prose.

    C'est la caractéristique de fond du livrable : un document de tableaux
    relié par de la prose courte, et non l'inverse.
    """
    def part_tableaux(xml: str) -> float:
        total = _tous_les_mots(xml)
        prose = sum(len(t.split()) for t in _prose(xml))
        return (total - prose) / max(total, 1)

    reference = part_tableaux(profil_reference["xml"])
    obtenue = part_tableaux(profil_demo["xml"])
    assert reference > 0.45
    assert obtenue >= 0.40, (
        f"{obtenue:.0%} des mots sont dans des tableaux contre {reference:.0%} "
        "dans la référence : le document redevient un texte suivi."
    )


# ── Charte ───────────────────────────────────────────────────────────────────


def test_aucune_couleur_hors_de_la_charte_de_reference(
    profil_demo: dict[str, Any], profil_reference: dict[str, Any]
) -> None:
    """Attrape la réapparition d'un bleu Word ou d'un gris par défaut.

    Le référentiel n'est pas seulement l'ensemble des fonds *déjà employés*
    dans le document de référence, mais l'ensemble des **jetons déclarés** de
    la charte : l'or bronze et le rose grisé y figurent, même si la référence
    ne les utilise que dans ses graphiques. Restreindre la liste aux fonds
    observés reviendrait à interdire un jeton parfaitement légitime dès qu'un
    nouveau composant s'en sert.
    """
    autorises = set(profil_reference["fonds"]) | {
        jeton.lstrip("#").upper()
        for jeton in (
            REF_PRUNE, REF_PRUNE_FONCE, REF_CREME, REF_CREME_ALT,
            REF_ROSE_PALE, REF_ROSE_GRISE, REF_OR_BRONZE, REF_FOND_GRAPHIQUE,
            "#FFFFFF",
        )
    }
    intrus = set(profil_demo["fonds"]) - autorises
    assert intrus == set(), f"Couleurs hors charte : {sorted('#' + c for c in intrus)}"


def test_seules_les_deux_polices_de_la_charte_sont_employees(
    profil_demo: dict[str, Any]
) -> None:
    assert profil_demo["polices"] == {"Aptos", "Georgia"}


def test_aucun_style_word_par_defaut_visible(profil_demo: dict[str, Any]) -> None:
    """Pas de Calibri, pas de bleu de titre Word."""
    xml = profil_demo["xml"]
    assert "Calibri" not in xml
    for bleu in ("4F81BD", "365F91", "1F497D"):
        assert bleu not in xml, f"Couleur Word par défaut présente : #{bleu}"


def test_les_jetons_de_reference_sont_tous_employes(profil_demo: dict[str, Any]) -> None:
    for jeton in (REF_PRUNE, REF_CREME, REF_ROSE_PALE):
        assert jeton.lstrip("#") in profil_demo["fonds"], f"Jeton absent : {jeton}"


def test_la_palette_de_reference_reprend_les_jetons_mesures() -> None:
    palette = construire_palette(
        primaire=REF_PRUNE, secondaire=REF_OR_BRONZE, fond_clair=REF_CREME
    )
    assert palette.fond_clair == REF_CREME
    assert palette.fond_clair_alt == REF_CREME_ALT
    assert palette.rose_pale == REF_ROSE_PALE
    assert palette.or_bronze == REF_OR_BRONZE


def test_changer_de_client_change_le_document(tmp_path: Path) -> None:
    """Critère d'acceptation : le logo et les couleurs sont paramétrables."""
    etude = construire_fixture(nombre_chapitres=2)
    a = rendre_etude(etude, tmp_path / "a.docx")
    etude["marque"]["couleur_principale"] = "#0B1F3B"
    etude["marque"]["couleur_fond"] = ""
    b = rendre_etude(etude, tmp_path / "b.docx")
    assert _profil(a)["xml"] != _profil(b)["xml"]
    assert "0B1F3B" in _profil(b)["fonds"]


# ── Pièges du lot 0 ──────────────────────────────────────────────────────────


def test_les_largeurs_sont_en_dxa_jamais_en_pourcentage(
    profil_demo: dict[str, Any]
) -> None:
    xml = profil_demo["xml"]
    assert 'w:type="pct"' not in xml, "Une largeur en pourcentage casse le rendu."
    assert xml.count('<w:tblW w:w=') >= 100
    assert xml.count("<w:tcW ") >= 300, "Chaque cellule doit porter sa largeur."


def test_les_fonds_sont_de_type_clear_jamais_solid(profil_demo: dict[str, Any]) -> None:
    """`solid` rend en noir dans Word."""
    assert 'w:val="solid"' not in profil_demo["xml"]
    assert 'w:val="clear"' in profil_demo["xml"]


def test_aucune_puce_saisie_en_dur(profil_demo: dict[str, Any]) -> None:
    textes = re.findall(r"<w:t[^>]*>([^<]*)</w:t>", profil_demo["xml"])
    for texte in textes:
        assert not texte.lstrip().startswith(("•", "- ", "▪")), texte[:60]


def test_la_couverture_a_un_fond_pleine_page(profil_demo: dict[str, Any]) -> None:
    xml = profil_demo["xml"]
    assert xml.count("<v:rect") == 2, "Couverture et quatrième de couverture."
    assert "z-index:-" in xml, "La forme doit être ancrée DERRIÈRE le texte."
    assert REF_PRUNE.lstrip("#") in xml


def test_les_sauts_de_page_sont_explicites(profil_demo: dict[str, Any]) -> None:
    """La référence en compte 30 : le flux automatique ne suffit pas."""
    assert profil_demo["sauts"] >= 25


# ── Graphiques ───────────────────────────────────────────────────────────────


def test_les_graphiques_sont_des_png_a_la_bonne_largeur() -> None:
    palette = construire_palette(primaire=REF_PRUNE, fond_clair=REF_CREME)
    png = graphiques.barres_verticales(palette, ["A", "B", "C"], [3.0, 5.0, 2.0], " %")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    largeur = int.from_bytes(png[16:20], "big")
    assert largeur >= 1800, f"Largeur {largeur} px, cible 2000."


#: Un jeu minimal par type du catalogue. Sert de contre-épreuve : si un type
#: est ajouté sans jeu de données ici, le test échoue au lieu de l'ignorer.
_JEUX_MINIMAUX: dict[str, dict[str, Any]] = {
    "barres": {"etiquettes": ["A", "B"], "valeurs": [1.0, 2.0]},
    "barres_horizontales": {"etiquettes": ["A", "B"], "valeurs": [1.0, 2.0]},
    "barres_groupees": {
        "etiquettes": ["A", "B"], "series": [("S1", [1.0, 2.0]), ("S2", [2.0, 1.0])]
    },
    "barres_empilees": {
        "etiquettes": ["A", "B"], "series": [("S1", [1.0, 2.0]), ("S2", [2.0, 1.0])]
    },
    "courbes": {"abscisses": ["2024", "2025"], "series": [("S", [1.0, 2.0])]},
    "aires": {
        "abscisses": ["2024", "2025"], "series": [("S1", [1.0, 2.0]), ("S2", [2.0, 3.0])]
    },
    "camembert": {"etiquettes": ["A", "B"], "valeurs": [60.0, 40.0]},
    "anneau": {"etiquettes": ["A", "B"], "valeurs": [60.0, 40.0], "centre": "1 000 €"},
    "entonnoir": {"etapes": [("Total", 100.0), ("Atteignable", 12.0)]},
    "radar": {
        "axes_noms": ["A", "B", "C"], "series": [("Projet", [4.0, 3.0, 2.0])]
    },
    "jauges": {"notes": [("A", 4.0), ("B", 2.5)]},
    "matrice_positionnement": {"points": [("A", 1.0, 2.0), ("B", 3.0, 4.0)]},
    "carte_chaleur": {
        "lignes": ["R1", "R2"], "colonnes": ["C1", "C2"],
        "valeurs": [[1.0, 4.0], [3.0, 2.0]],
    },
    "pyramide_ages": {
        "tranches": ["18-24", "25-34"], "gauche": [8.0, 12.0], "droite": [7.0, 11.0]
    },
    "chronologie": {"jalons": [("0-30 j", "Cadrer"), ("3 mois", "Tester")]},
}


@pytest.mark.parametrize("type_graphique", sorted(graphiques.RENDU_PAR_TYPE))
def test_tous_les_types_du_catalogue_sont_rendus(type_graphique: str) -> None:
    palette = construire_palette(primaire=REF_PRUNE, fond_clair=REF_CREME)
    donnees = _JEUX_MINIMAUX[type_graphique]
    png = graphiques.rendre(palette, type_graphique, donnees)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    largeur = int.from_bytes(png[16:20], "big")
    assert largeur >= 1800, f"{type_graphique} : {largeur} px, cible 2000."


def test_le_catalogue_decrit_exactement_les_types_rendus() -> None:
    """Une seule source par vérité (règle 5).

    Le catalogue est lu par la couche de génération pour composer le prompt ;
    `RENDU_PAR_TYPE` est lu par le moteur de rendu. Si les deux divergent, le
    modèle propose un type que personne ne sait dessiner — ou l'inverse, un
    type dessinable reste inaccessible.
    """
    assert set(graphiques.CATALOGUE) == set(graphiques.RENDU_PAR_TYPE)
    assert graphiques.TYPES_DISPONIBLES == tuple(sorted(graphiques.RENDU_PAR_TYPE))


def test_le_contrat_de_chapitre_connait_les_memes_types() -> None:
    """L'énumération du lot 2 doit suivre le catalogue du moteur de rendu.

    Elle est écrite à la main pour rester vérifiable statiquement ; c'est donc
    ici, et nulle part ailleurs, que l'écart est détecté.
    """
    from generation.chapitres.schema import TypeGraphique

    assert {membre.value for membre in TypeGraphique} == set(
        graphiques.RENDU_PAR_TYPE
    )


def test_un_type_de_graphique_inconnu_ne_casse_pas_le_rendu() -> None:
    palette = construire_palette(primaire=REF_PRUNE)
    png = graphiques.rendre(
        palette, "camembert_3d", {"etiquettes": ["A"], "valeurs": [1.0]}
    )
    assert png[:4] == b"\x89PNG"


# ── Contrat JSON ─────────────────────────────────────────────────────────────


def test_un_bloc_inconnu_est_refuse(tmp_path: Path) -> None:
    """Mieux vaut échouer au rendu que produire un document amputé en silence.

    Le bloc fautif est posé dans un chapitre DU CLIENT, pas dans la fiche
    projet : celle-ci n'est plus rendue (elle est interne), et l'y placer
    ferait passer ce test pour la mauvaise raison — le rendu ne la lit plus.
    """
    etude = construire_fixture(nombre_chapitres=2)
    client = next(c for c in etude["chapitres"] if c["numero"] > 0)
    client["blocs"].append({"type": "carrousel_3d"})
    with pytest.raises(BlocInconnuError):
        rendre_etude(etude, tmp_path / "ko.docx")


def test_le_gabarit_reste_le_point_de_depart_du_rendu() -> None:
    assert charger_gabarit() is not None


# ── Dépendance au secteur d'activité ─────────────────────────────────────────
# Contrainte posée par la cliente : « ça dépend toujours du secteur
# d'activité ». Un plan de visuels figé par numéro de chapitre sortirait une
# saisonnalité mensuelle dans une étude sur le conseil et une pyramide des âges
# dans une étude sur la logistique. Ces tests verrouillent le fait que le
# secteur change réellement le document.


def test_deux_secteurs_ne_donnent_pas_les_memes_graphiques() -> None:
    joaillerie = secteurs.graphiques_conseilles(
        secteurs.profil_du_secteur("bijouterie joaillerie")
    )
    restauration = secteurs.graphiques_conseilles(
        secteurs.profil_du_secteur("restauration rapide")
    )
    assert joaillerie[:4] != restauration[:4], (
        "Les visuels prioritaires sont identiques : le secteur n'est pas pris "
        "en compte."
    )


def test_un_secteur_ne_propose_jamais_un_type_qu_il_proscrit() -> None:
    for profil in (*secteurs.PROFILS, secteurs.PROFIL_GENERIQUE):
        conseilles = secteurs.graphiques_conseilles(profil)
        interdits = set(conseilles) & set(profil.graphiques_a_eviter)
        assert not interdits, f"{profil.code} propose {sorted(interdits)}."


def test_aucun_type_conseille_n_est_indessinable() -> None:
    """Contre-épreuve : un profil ne peut pas nommer un type qui n'existe pas."""
    for profil in (*secteurs.PROFILS, secteurs.PROFIL_GENERIQUE):
        inconnus = set(secteurs.graphiques_conseilles(profil)) - set(
            graphiques.RENDU_PAR_TYPE
        )
        assert not inconnus, f"{profil.code} déclare {sorted(inconnus)}."


def test_les_types_conseilles_sont_sans_doublon() -> None:
    """Deux fois la même figure dans un document se voit à la lecture."""
    for profil in (*secteurs.PROFILS, secteurs.PROFIL_GENERIQUE):
        conseilles = secteurs.graphiques_conseilles(profil)
        assert len(conseilles) == len(set(conseilles)), profil.code


@pytest.mark.parametrize(
    ("saisie", "code_attendu"),
    [
        ("Bijouterie / joaillerie", "luxe_joaillerie"),
        ("restauration rapide", "restauration"),
        ("boulangerie-pâtisserie", "restauration"),
        # Flexions : le mot-clé déclaré est « ostéopathe », la cliente saisit
        # « ostéopathie ». Une comparaison mot à mot exacte échouait ici.
        ("cabinet d'ostéopathie", "sante_bien_etre"),
        ("transporteur routier", "transport_logistique"),
        ("société de conseil en stratégie", "services_entreprises"),
        ("plateforme SaaS B2B", "numerique"),
        ("agence immobilière", "immobilier"),
        ("domaine viticole", "agroalimentaire"),
    ],
)
def test_le_secteur_saisi_est_rattache_au_bon_profil(
    saisie: str, code_attendu: str
) -> None:
    assert secteurs.profil_du_secteur(saisie).code == code_attendu


@pytest.mark.parametrize("saisie", ["", "   ", "activité inclassable zzz"])
def test_un_secteur_non_reconnu_retombe_sur_le_profil_generique(saisie: str) -> None:
    """Règle 1 : ne jamais rendre un document sans visuel en silence."""
    profil = secteurs.profil_du_secteur(saisie)
    assert profil.code == secteurs.CODE_GENERIQUE
    assert profil.graphiques_privilegies


def test_le_rapprochement_par_prefixe_ne_confond_pas_deux_metiers() -> None:
    """Contre-épreuve de la règle morphologique.

    Le rapprochement par préfixe absorbe les flexions ; il ne doit pas pour
    autant rattacher « cabaret » à « bar », ni « bio » à « biologie médicale ».
    """
    assert secteurs.profil_du_secteur("cabaret").code != "restauration"
    assert secteurs.profil_du_secteur("barbecue").code != "restauration"


def test_la_consigne_visuelle_nomme_ce_qu_il_faut_eviter() -> None:
    """Sans la partie « à éviter », le modèle propose une pyramide des âges en B2B."""
    profil = secteurs.profil_du_secteur("société de conseil")
    consigne = secteurs.consigne_visuelle(profil)
    assert profil.libelle in consigne
    assert "pyramide_ages" in consigne
    assert "à ne pas employer" in consigne


def test_changer_de_secteur_change_les_graphiques_du_document() -> None:
    """La preuve au niveau du document, pas seulement du sélecteur (règle 7)."""
    def types(secteur: str) -> list[str]:
        etude = construire_fixture(nombre_chapitres=22, secteur=secteur)
        return [
            bloc["graphique"]
            for chapitre in etude["chapitres"]
            for bloc in chapitre["blocs"]
            if bloc["type"] == "graphique"
        ]

    joaillerie, sante = types("joaillerie"), types("cabinet d'ostéopathie")
    assert joaillerie and sante
    assert joaillerie != sante
    assert "pyramide_ages" in sante, "Un bassin de patientèle appelle une pyramide."
    assert "pyramide_ages" not in joaillerie, "Hors sujet en joaillerie."


# ── Densité de visuels ───────────────────────────────────────────────────────


def test_le_document_porte_plus_de_visuels_que_la_reference(
    profil_demo: dict[str, Any], profil_reference: dict[str, Any]
) -> None:
    """La cliente a demandé davantage de graphiques une fois la densité réglée.

    Un plancher, et non une fourchette : la référence a été composée à la main
    avec onze images, la demande explicite est d'aller au-delà.
    """
    assert profil_demo["images"] >= profil_reference["images"], (
        f"{profil_demo['images']} images contre {profil_reference['images']} "
        "dans la référence."
    )


def test_aucun_graphique_n_apparait_deux_fois(demo: Path) -> None:
    """Word déduplique les images identiques : deux fois la même figure se voit."""
    etude = construire_fixture(nombre_chapitres=22)
    demandes = [
        bloc["graphique"]
        for chapitre in etude["chapitres"]
        for bloc in chapitre["blocs"]
        if bloc["type"] == "graphique"
    ]
    assert len(demandes) == len(set(demandes)), sorted(demandes)


def test_les_composants_sont_appelables_isolement(tmp_path: Path) -> None:
    """Chaque composant doit être testable seul, sans le générateur."""
    document = charger_gabarit()
    palette = construire_palette(primaire=REF_PRUNE, fond_clair=REF_CREME)
    composants.bandeau_chapitre(document, palette, 3, "Titre", "Accroche")
    composants.encadre(document, palette, "Verdict", ["Ligne"], verdict=True)
    composants.grille_chiffres(document, palette, [("1", "a", "s")])
    composants.tableau(document, palette, ["A", "B"], [["1", "2"]])
    composants.paragraphe(document, palette, "Texte")
    composants.matrice_quadrants(
        document, palette,
        [("Forces", ["F1"]), ("Faiblesses", ["F2"]),
         ("Opportunités", ["O1"]), ("Menaces", ["M1"])],
    )
    composants.barre_repartition(
        document, palette, [("Boutique", 60.0), ("En ligne", 40.0)]
    )
    chemin = tmp_path / "composants.docx"
    document.save(str(chemin))
    profil = _profil(chemin)
    assert profil["bandeaux"] == 1
    assert profil["encadres"] == 1
    assert profil["grilles"] == 1


def test_la_matrice_a_quatre_cases_reste_complete_meme_incomplete(
    tmp_path: Path,
) -> None:
    """Trois cases fournies : la quatrième reste blanche, la grille tient.

    Un `IndexError` ici ferait échouer tout le rendu d'un document livrable.
    """
    document = charger_gabarit()
    palette = construire_palette(primaire=REF_PRUNE, fond_clair=REF_CREME)
    composants.matrice_quadrants(
        document, palette, [("A", ["1"]), ("B", ["2"]), ("C", ["3"])]
    )
    document.save(str(tmp_path / "quadrants.docx"))


def test_la_barre_de_repartition_ne_deborde_pas_de_la_largeur_utile(
    tmp_path: Path,
) -> None:
    """Une part minuscule reçoit une largeur plancher : le total doit rester borné.

    Sans le rognage, cinq parts dont quatre marginales dépassaient la largeur
    de page et Word rendait un tableau tronqué.
    """
    document = charger_gabarit()
    palette = construire_palette(primaire=REF_PRUNE, fond_clair=REF_CREME)
    composants.barre_repartition(
        document, palette,
        [("Dominante", 96.0), ("A", 1.0), ("B", 1.0), ("C", 1.0), ("D", 1.0)],
    )
    chemin = tmp_path / "repartition.docx"
    document.save(str(chemin))
    with zipfile.ZipFile(chemin) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    # Le composant a deux rangées : on mesure une rangée, pas le tableau entier.
    rangees = re.findall(r"<w:tr(?:\s[^>]*)?>.*?</w:tr>", xml, re.S)
    assert rangees
    for rangee in rangees:
        largeurs = [int(v) for v in re.findall(r'<w:tcW w:w="(\d+)"', rangee)]
        assert largeurs
        assert sum(largeurs) <= composants.LARGEUR_UTILE_DXA, sum(largeurs)

"""Extrait les schemas du dossier HTML et les rend en images.

Le Word doit porter LES MEMES figures que la version consultable. Elles sont
donc lues dans la source unique — `docs/dossier-soleau.html` — et rendues en
PNG, plutot que redessinees a la main pour le Word (ce qui creerait deux
dessins d'une meme figure, et donc deux verites).

    .venv/Scripts/python.exe backend/scripts/schemas_soleau.py

Les variables CSS ne traversent pas un fichier SVG autonome : elles sont
resolues ici, avec les couleurs du site EVKHA.
"""
from __future__ import annotations

import re
from pathlib import Path

import pypdfium2 as pdfium
from bs4 import BeautifulSoup
from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg

RACINE = Path(__file__).resolve().parents[2]
SOURCE = RACINE / "docs" / "dossier-soleau.html"
SORTIE = RACINE / "docs" / "schemas"

#: Couleurs du site EVKHA, relevees sur evkha.fr. Le SVG autonome ne peut pas
#: lire les variables CSS de la page : elles sont figees ici, et nulle part
#: ailleurs, pour que le rendu Word et le rendu HTML montrent la meme figure.
COULEURS = {
    "var(--jaune)": "#F8C51C",
    "var(--jaune-f)": "#B8890A",
    "var(--noir)": "#000000",
    "var(--blanc)": "#FFFFFF",
    "var(--doux)": "#FAF9F6",
    "var(--creme)": "#FDF6DF",
    "var(--gris)": "#5F5F63",
    "var(--trait)": "#E8E5DC",
    "var(--encre)": "#17171A",
    "currentColor": "#17171A",
}

#: Attributs SVG dont la casse compte, et que l'analyseur HTML aplatit.
#:
#: Seuls ceux effectivement employes dans les schemas y figurent : allonger la
#: liste « au cas ou » donnerait l'illusion d'une couverture generale, alors
#: qu'un attribut oublie se manifeste de toute facon par une image blanche.
CASSE_SVG = {
    "viewbox": "viewBox",
    "refx": "refX",
    "refy": "refY",
    "markerwidth": "markerWidth",
    "markerheight": "markerHeight",
    "markerunits": "markerUnits",
    "textlength": "textLength",
    "preserveaspectratio": "preserveAspectRatio",
}

#: Resolution du rendu. Une image inseree dans un Word occupe environ 16 cm ;
#: a 200 points par pouce, le texte des schemas reste net a l'impression.
#:
#: Le rendu passe par un PDF intermediaire : la sortie image directe de
#: reportlab reclame une bibliotheque graphique absente de cette machine,
#: alors que sa sortie PDF est native et que le lecteur PDF deja installe sait
#: la convertir.
RESOLUTION = 200


def _resoudre(svg: str) -> str:
    """Rend le SVG autonome : couleurs figees, espace de noms, DIMENSIONS.

    Les dimensions sont le point qui manquait. Dans la page, la largeur est
    donnee par la feuille de style et l'element ne porte qu'un `viewBox` ; hors
    de la page, le convertisseur lit alors une taille NULLE et produit une
    image blanche — sans erreur, ce qui est le pire cas (regle 1).
    """
    for variable, valeur in COULEURS.items():
        svg = svg.replace(variable, valeur)

    # LA CASSE DES ATTRIBUTS EST RESTAUREE.
    #
    # L'analyseur HTML met tous les noms d'attributs en minuscules, parce que
    # HTML les traite ainsi. Le SVG, lui, est du XML : `viewBox` et `viewbox`
    # n'y sont pas le meme attribut, et le second est simplement ignore.
    # Consequence observee : des images entierement blanches, sans erreur.
    for minuscule, exacte in CASSE_SVG.items():
        svg = svg.replace(f"{minuscule}=", f"{exacte}=")

    if "xmlns=" not in svg:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)

    boite = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    if boite is None:
        msg = "Un schema sans viewBox ne peut pas etre dimensionne."
        raise ValueError(msg)
    largeur, hauteur = boite.group(1), boite.group(2)
    if "width=" not in svg.split(">", 1)[0]:
        svg = svg.replace(
            "<svg", f'<svg width="{largeur}" height="{hauteur}"', 1
        )
    return svg


def extraire() -> list[tuple[str, Path]]:
    """Rend chaque figure du dossier en PNG. Retourne (legende, chemin)."""
    SORTIE.mkdir(parents=True, exist_ok=True)
    soupe = BeautifulSoup(SOURCE.read_text(encoding="utf-8"), "html.parser")

    produits: list[tuple[str, Path]] = []
    for index, figure in enumerate(soupe.find_all("figure"), start=1):
        svg = figure.find("svg")
        if svg is None:
            continue
        legende = figure.find("figcaption")
        texte = legende.get_text(" ", strip=True) if legende else ""

        brut = _resoudre(str(svg))
        chemin_svg = SORTIE / f"schema-{index:02d}.svg"
        chemin_svg.write_text(brut, encoding="utf-8")

        dessin = svg2rlg(str(chemin_svg))
        if dessin is None:
            print(f"  schema {index:02d} : illisible, ignore")
            continue

        chemin_pdf = SORTIE / f"schema-{index:02d}.pdf"
        renderPDF.drawToFile(dessin, str(chemin_pdf))
        chemin_png = SORTIE / f"schema-{index:02d}.png"
        # Le document PDF est FERME avant d'effacer le fichier : Windows refuse
        # de supprimer un fichier encore ouvert, et l'erreur ne dit pas que le
        # coupable est le lecteur qu'on vient d'utiliser.
        pdf = pdfium.PdfDocument(str(chemin_pdf))
        try:
            pdf[0].render(scale=RESOLUTION / 72).to_pil().convert("RGB").save(chemin_png)
        finally:
            pdf.close()
        chemin_pdf.unlink()
        produits.append((texte, chemin_png))
        print(f"  schema {index:02d} : {chemin_png.name} "
              f"({int(dessin.width)}x{int(dessin.height)})")

    return produits


if __name__ == "__main__":
    figures = extraire()
    print(f"\n{len(figures)} schemas rendus dans {SORTIE}")

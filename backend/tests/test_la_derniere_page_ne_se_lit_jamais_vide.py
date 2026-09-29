"""La dernière page ne se lit jamais vide, et rien n'ouvre une page blanche.

29/09/2026, business plan ÉCLORE, page 107 (§ 3.15 du diagnostic) : la
quatrième de couverture — un saut de page, douze lignes vides, puis les
mentions en corps 8. Pour un business plan, `mention_legale` n'est jamais
fournie : il restait le nom et la confidentialité, en petit, au bas d'une page
pleine de couleur. Elle se lisait VIDE. Et le paragraphe d'espacement laissé
après le dernier tableau de l'annexe, suivi du paragraphe de saut, ouvrait une
vraie page blanche dès que le tableau remplissait la sienne.

Tenu ici, sur le `.docx` écrit :

- la quatrième de couverture porte le nom en titre, le document et sa date ;
- sans nom ni logo, il n'y a rien à montrer : elle n'est pas produite ;
- entre le dernier tableau et elle, aucune ligne blanche ni paragraphe de saut.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from docx import Document
from docx.oxml.ns import qn

from generation.rendu_word.assemblage import assembler_etude
from generation.rendu_word.depuis_json import rendre_etude
from tests.test_lot3_livrable import _chapitre, _socle

pytestmark = pytest.mark.django_db

NOM = "ÉCLORE (nom de projet provisoire), avec pour signature « Expériences bien-être »"


def _rendre(tmp_path: Path, marque: dict[str, str]) -> Any:
    etude, _ = assembler_etude(
        socle=_socle(), chapitres=[_chapitre(1)], titre="Business plan", marque=marque,
    )
    return Document(str(rendre_etude(etude, tmp_path / "fin.docx")))


def _corps(document: Any) -> list[Any]:
    return [e for e in document.element.body.iterchildren() if e.tag != qn("w:sectPr")]


def _texte(element: Any) -> str:
    return "".join(element.xpath(".//w:t/text()")).strip()


def _quatrieme(document: Any) -> list[Any]:
    """Les éléments de la dernière page : depuis le dernier fond pleine page."""
    corps = _corps(document)
    fonds = [rang for rang, e in enumerate(corps) if "<v:rect" in _xml(e)]
    assert len(fonds) == 2, "couverture et quatrième de couverture attendues"
    return corps[fonds[-1]:]


def _xml(element: Any) -> str:
    from lxml import etree

    return str(etree.tostring(element, encoding="unicode"))


def test_la_quatrieme_de_couverture_porte_un_vrai_contenu(tmp_path: Path) -> None:
    """Le défaut exact : un nom et la confidentialité, en petit, rien d'autre."""
    page = _quatrieme(_rendre(tmp_path, {"nom": NOM}))
    lignes = [_texte(e) for e in page if _texte(e)]
    assert lignes[0] == "ÉCLORE", lignes
    assert any(ligne.startswith("Business plan · ") for ligne in lignes), lignes
    assert any("confidentiel" in ligne.lower() for ligne in lignes), lignes
    # Le nom est un TITRE, pas une mention de corps 8.
    titre = next(e for e in page if _texte(e) == "ÉCLORE")
    tailles = [int(v) for v in titre.xpath(".//w:sz/@w:val")]
    assert tailles and max(tailles) >= 40, "le nom doit être écrit en grand (≥ 20 pt)"


def test_sans_nom_ni_logo_il_n_y_a_pas_de_quatrieme_de_couverture(tmp_path: Path) -> None:
    """Rien à montrer : mieux vaut pas de page qu'une page qui se lit blanche."""
    document = _rendre(tmp_path, {})
    corps = _corps(document)
    fonds = [e for e in corps if "<v:rect" in _xml(e)]
    assert len(fonds) == 1, "seule la couverture doit porter un fond pleine page"


def test_aucune_ligne_blanche_ni_saut_apres_le_dernier_tableau(tmp_path: Path) -> None:
    """Un paragraphe vide puis un paragraphe de saut : la page blanche d'ÉCLORE."""
    corps = _corps(_rendre(tmp_path, {"nom": NOM}))
    dernier_tableau = max(r for r, e in enumerate(corps) if e.tag == qn("w:tbl"))
    suivant = corps[dernier_tableau + 1]
    assert suivant.tag == qn("w:p")
    assert suivant.xpath("./w:pPr/w:pageBreakBefore"), (
        "l'élément qui suit le dernier tableau doit ouvrir la dernière page lui-même"
    )
    assert "<v:rect" in _xml(suivant)


def test_sans_quatrieme_le_document_ne_finit_pas_sur_une_ligne_pleine(tmp_path: Path) -> None:
    """Word exige un paragraphe après un tableau final : il est réduit à un point."""
    corps = _corps(_rendre(tmp_path, {}))
    dernier = corps[-1]
    assert dernier.tag == qn("w:p") and not _texte(dernier)
    assert dernier.xpath(".//w:sz/@w:val") == ["2"], "un paragraphe final d'un point"
    assert corps[-2].tag == qn("w:tbl")

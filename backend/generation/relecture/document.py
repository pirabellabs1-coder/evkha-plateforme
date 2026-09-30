"""Le document tel que le lecteur le lit : des sections, leurs paragraphes, leurs tableaux.

30/09/2026 — les contrôles de relecture (`generation.relecture`) jugent le MÊME
modèle, construit de deux façons :

- depuis un chapitre STRUCTURÉ (`document_du_chapitre`), avant rendu : un
  constat grave y fait reprendre le chapitre avec son motif, c'est la
  correction ;
- depuis le PDF RENDU (`document_du_pdf`), après rendu : la relecture de ce
  que le lecteur va lire (règle 3), et la régression sur un document réel.

Les tableaux ne sont pas du texte à plat : « huit formats » se juge contre les
lignes du tableau voisin, un compte de résultat contre ses colonnes. Le PDF les
rend cellule par cellule ; `find_tables` les reconstitue.
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: « 9.3 Le seuil de rentabilité… » : le titre d'une sous-section.
_SOUS_SECTION = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})\s+(\S.{2,200})$")
#: « CHAPITRE 09 » : le début d'un chapitre (son titre suit).
_CHAPITRE = re.compile(r"^\s*CHAPITRE\s+(\d{1,2})\b")


@dataclass(frozen=True)
class Tableau:
    entetes: tuple[str, ...]
    lignes: tuple[tuple[str, ...], ...]

    def cellules(self) -> Iterable[str]:
        yield from self.entetes
        for ligne in self.lignes:
            yield from ligne


@dataclass
class Section:
    #: « 9.3 », ou « ch. 9 » pour ce qui précède la première sous-section.
    numero: str
    titre: str
    chapitre: int | None
    paragraphes: list[str] = field(default_factory=list)
    tableaux: list[Tableau] = field(default_factory=list)
    #: Titres des figures de la section (spécification, avant rendu).
    figures: list[str] = field(default_factory=list)
    page: int | None = None

    def texte(self) -> str:
        """La prose, puis chaque ligne de tableau : ce que le lecteur lit dans la section."""
        morceaux = [*self.paragraphes]
        for tableau in self.tableaux:
            morceaux.append(" · ".join(tableau.entetes))
            morceaux.extend(" · ".join(ligne) for ligne in tableau.lignes)
        return "\n".join(morceaux)


@dataclass
class Document:
    sections: list[Section]
    #: Texte brut de chaque page (PDF seulement) : la mise en page se juge là.
    pages: list[str] = field(default_factory=list)

    def texte(self) -> str:
        return "\n".join(s.texte() for s in self.sections)


def _propre(texte: str) -> str:
    """Espaces insécables ramenés à l'espace, lignes recollées."""
    texte = texte.replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s*\n\s*", " ", texte).strip()


# ── Depuis un chapitre structuré ────────────────────────────────────────────


def _objet(bloc: Mapping[str, Any], cle: str) -> Mapping[str, Any]:
    """Le contenu d'un bloc, qu'il soit imbriqué (`{"tableau": {...}}`) ou à plat."""
    imbrique = bloc.get(cle)
    return imbrique if isinstance(imbrique, Mapping) else bloc


def document_du_chapitre(payload: Any) -> Document:
    """Le chapitre tel que le modèle l'a écrit (dictionnaire ou modèle pydantic)."""
    donnees: Mapping[str, Any] = (
        payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
    )
    numero = donnees.get("chapitre")
    chapitre = int(str(numero)) if str(numero).isdigit() else None
    courante = Section(
        numero=f"ch. {chapitre}" if chapitre is not None else "ch. ?",
        titre=str(donnees.get("titre") or ""), chapitre=chapitre,
    )
    # L'accroche s'affiche sous le titre du chapitre : le lecteur la lit la
    # première (« Trois univers, huit formats » pour un tableau de sept).
    accroche = str(donnees.get("accroche") or "").strip()
    if accroche:
        courante.paragraphes.append(_propre(accroche))
    sections = [courante]
    for bloc in donnees.get("blocs") or []:
        if not isinstance(bloc, Mapping):
            continue
        genre = bloc.get("type")
        if genre == "titre_sous_section":
            courante = Section(
                numero=str(bloc.get("numero") or ""), titre=str(bloc.get("intitule") or ""),
                chapitre=chapitre,
            )
            sections.append(courante)
        elif genre == "paragraphe":
            courante.paragraphes.append(_propre(str(bloc.get("texte") or "")))
        elif genre == "tableau":
            tableau = _objet(bloc, "tableau")
            courante.tableaux.append(Tableau(
                entetes=tuple(_propre(str(c)) for c in tableau.get("entetes") or []),
                lignes=tuple(
                    tuple(_propre(str(c)) for c in ligne)
                    for ligne in tableau.get("lignes") or [] if isinstance(ligne, list)
                ),
            ))
        elif genre == "encadre":
            encadre = _objet(bloc, "encadre")
            lignes = [str(encadre.get("intitule") or ""), *map(str, encadre.get("lignes") or [])]
            courante.paragraphes.extend(_propre(ligne) for ligne in lignes if ligne.strip())
        elif genre == "graphique":
            graphique = _objet(bloc, "graphique")
            courante.figures.append(_propre(str(graphique.get("titre") or "")))
        elif genre == "grille_kpi":
            # Les chiffres clés sont lus AVANT le texte : un chiffre faux y
            # compte autant qu'en prose (revue du 30/09/2026).
            for cellule in bloc.get("cellules") or []:
                if isinstance(cellule, Mapping) and str(cellule.get("valeur") or "").strip():
                    courante.paragraphes.append(_propre(
                        f"{cellule.get('libelle') or ''} : {cellule.get('valeur')}"
                    ))
    return Document(sections=[s for s in sections if s.paragraphes or s.tableaux or s.figures])


# ── Depuis le PDF rendu ─────────────────────────────────────────────────────


def _lignes_d_en_tete(pages: list[list[str]]) -> set[str]:
    """Les lignes répétées en haut de la plupart des pages (en-tête courant).

    Le numéro de page les rend toutes différentes : on les compare sans chiffres.
    """
    sans_chiffres = Counter(
        re.sub(r"\d+", "#", ligne.strip())
        for lignes in pages for ligne in lignes[:3] if ligne.strip()
    )
    seuil = max(3, len(pages) // 2)
    return {ligne for ligne, n in sans_chiffres.items() if n >= seuil}


def document_du_pdf(chemin: str | Path) -> Document:
    """Le PDF rendu, en sections : titres « N.M », paragraphes, tableaux reconstitués."""
    import importlib  # noqa: PLC0415

    # Lourd, chargé à l'usage ; bibliothèque sans annotations de types.
    pymupdf: Any = importlib.import_module("pymupdf")
    pdf = pymupdf.open(str(chemin))
    pages_brutes = [pdf[i].get_text() for i in range(pdf.page_count)]
    en_tetes = _lignes_d_en_tete([p.splitlines() for p in pages_brutes])
    courante = Section(numero="début", titre="", chapitre=None)
    sections = [courante]
    chapitre_attendu = False
    for rang in range(pdf.page_count):
        page = pdf[rang]
        tableaux = page.find_tables().tables
        zones = [pymupdf.Rect(t.bbox) for t in tableaux]
        elements: list[tuple[float, str, Any]] = []
        for x0, y0, x1, y1, texte, *_ in page.get_text("blocks"):
            rect = pymupdf.Rect(x0, y0, x1, y1)
            if any(zone.intersects(rect) for zone in zones):
                continue
            elements.append((y0, "texte", texte))
        for tableau, zone in zip(tableaux, zones, strict=True):
            elements.append((zone.y0, "tableau", tableau))
        for _, genre, contenu in sorted(elements, key=lambda e: e[0]):
            if genre == "tableau":
                lignes = [
                    tuple(_propre(c or "") for c in ligne) for ligne in contenu.extract()
                ]
                if lignes:
                    courante.tableaux.append(Tableau(entetes=lignes[0], lignes=tuple(lignes[1:])))
                continue
            paragraphe: list[str] = []
            for ligne in str(contenu).splitlines():
                if re.sub(r"\d+", "#", ligne.strip()) in en_tetes:
                    continue
                chapitre = _CHAPITRE.match(ligne)
                titre = _SOUS_SECTION.match(ligne)
                if chapitre or titre:
                    if paragraphe:
                        courante.paragraphes.append(_propre("\n".join(paragraphe)))
                        paragraphe = []
                    if chapitre:
                        numero = int(chapitre.group(1))
                        courante = Section(
                            numero=f"ch. {numero}", titre="", chapitre=numero, page=rang + 1,
                        )
                        chapitre_attendu = True
                    elif titre:
                        numero = int(titre.group(1))
                        courante = Section(
                            numero=f"{numero}.{int(titre.group(2))}",
                            titre=_propre(titre.group(3)), chapitre=numero, page=rang + 1,
                        )
                        chapitre_attendu = False
                    sections.append(courante)
                    continue
                if chapitre_attendu and not courante.titre and ligne.strip():
                    courante.titre = _propre(ligne)
                    chapitre_attendu = False
                    continue
                paragraphe.append(ligne)
            if paragraphe:
                courante.paragraphes.append(_propre("\n".join(paragraphe)))
    return Document(
        sections=[s for s in sections if s.paragraphes or s.tableaux],
        pages=pages_brutes,
    )

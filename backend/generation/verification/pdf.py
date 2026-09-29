"""Le contrôle APRÈS rendu : le PDF lu comme le client le lit.

## Pourquoi

29/09/2026, business plan ÉCLORE (107 pages). Plusieurs défauts n'étaient
visibles que sur le fichier final : un en-tête de deux lignes répété sur 105
pages, l'auteur du PDF égal à une phrase entière, une dernière page qui se
lisait vide, 22 chapitres numérotés quand l'offre en annonce 21. La
vérification existante lisait le XML du Word : ni les en-têtes, ni les pages,
ni les propriétés du PDF (`docs/diagnostic.md`, § 3.13-3.15).

Ce module lit le PDF produit par LibreOffice (pypdf, dépendance déclarée) et
rend des CONSTATS. Il ne bloque rien — l'envoi est automatique (décision
cliente du 13/08/2026) — : les constats partent au rapport interne et en
incident, pour que la cause se corrige à la source.
"""
from __future__ import annotations

import hashlib
import io
import re
from collections import Counter
from dataclasses import dataclass

#: Au-delà, un en-tête courant ne tient plus sur une ligne en A4 portrait.
LONGUEUR_MAX_ENTETE = 90
#: Un corps de page de moins de mots que cela se lit comme une page vide.
MOTS_MIN_PAR_PAGE = 5
#: Une image plus petite est un logo ou un pictogramme, pas une figure.
OCTETS_MIN_FIGURE = 8_000

_BANDEAU_CHAPITRE = re.compile(r"\bCHAPITRE\s+(\d{1,2})\b")


@dataclass(frozen=True)
class ConstatPdf:
    controle: str
    detail: str
    page: int | None = None

    def en_dict(self) -> dict[str, object]:
        return {"controle": self.controle, "detail": self.detail, "page": self.page}


def _lignes(texte: str) -> list[str]:
    return [ligne.strip() for ligne in (texte or "").splitlines() if ligne.strip()]


def _lignes_repetees(pages: list[list[str]]) -> set[str]:
    """Les lignes présentes sur la majorité des pages : en-tête et pied courants."""
    compte: Counter[str] = Counter()
    for lignes in pages:
        compte.update(set(lignes[:3] + lignes[-2:]))
    seuil = max(3, int(len(pages) * 0.6))
    return {ligne for ligne, n in compte.items() if n >= seuil}


def controler_le_pdf(
    pdf: bytes,
    *,
    chapitres_annonces: int | None = None,
    auteur_attendu: str | None = None,
    avec_images: bool = False,
) -> list[ConstatPdf]:
    """Les constats sur le PDF final. Liste vide = rien à redire sur ce qu'on sait lire."""
    from pypdf import PdfReader  # noqa: PLC0415

    lecteur = PdfReader(io.BytesIO(pdf))
    textes = [page.extract_text() or "" for page in lecteur.pages]
    pages = [_lignes(t) for t in textes]
    constats: list[ConstatPdf] = []
    if not pages:
        return [ConstatPdf("pdf_vide", "Le PDF ne contient aucune page.")]

    courantes = _lignes_repetees(pages)

    # En-tête courant : une ligne, et courte.
    entetes = [ligne for ligne in courantes if not re.fullmatch(r"[·\d\s]+", ligne)]
    for ligne in entetes:
        if len(ligne) > LONGUEUR_MAX_ENTETE:
            constats.append(ConstatPdf(
                "entete_trop_long",
                f"En-tête courant de {len(ligne)} signes, répété sur la plupart des pages : "
                f"« {ligne[:80]}… ».",
            ))
            break

    # Pages qui se lisent vides (hors couverture).
    derniere = len(pages)
    for numero, lignes in enumerate(pages, start=1):
        if numero == 1:
            continue
        corps = [ligne for ligne in lignes if ligne not in courantes]
        mots = sum(len(ligne.split()) for ligne in corps)
        if mots < MOTS_MIN_PAR_PAGE:
            quatrieme = numero == derniere and mots > 0
            if not quatrieme:
                constats.append(ConstatPdf(
                    "page_vide", f"La page {numero} ne porte que {mots} mot(s) hors en-tête.",
                    page=numero,
                ))

    # Source seule en haut de page : séparée de son tableau.
    for numero, lignes in enumerate(pages, start=1):
        corps = [ligne for ligne in lignes if ligne not in courantes]
        if corps and corps[0].startswith("Source :"):
            constats.append(ConstatPdf(
                "source_orpheline",
                f"La page {numero} commence par une source seule : « {corps[0][:80]} ».",
                page=numero,
            ))

    # Chapitres numérotés : exactement le nombre annoncé.
    numeros = {int(m.group(1)) for t in textes for m in _BANDEAU_CHAPITRE.finditer(t)}
    if chapitres_annonces is not None and numeros and len(numeros) != chapitres_annonces:
        constats.append(ConstatPdf(
            "nombre_de_chapitres",
            f"{len(numeros)} chapitres numérotés dans le document pour "
            f"{chapitres_annonces} annoncés.",
        ))

    # Propriétés du PDF : l'auteur est le porteur de projet, sur une ligne.
    auteur = str((lecteur.metadata or {}).get("/Author") or "").strip()
    if auteur_attendu and auteur != auteur_attendu.strip():
        constats.append(ConstatPdf(
            "auteur_du_pdf", f"Auteur du PDF « {auteur[:80]} » au lieu de « {auteur_attendu} ».",
        ))
    elif len(auteur) > 60:
        constats.append(ConstatPdf(
            "auteur_du_pdf", f"Auteur du PDF trop long : « {auteur[:80]}… ».",
        ))

    # La même image deux fois : une figure dupliquée. Décoder toutes les images
    # d'un document de cent pages prend plusieurs minutes (mesuré sur ÉCLORE,
    # 29/09/2026) : ce contrôle est donc optionnel. Les doublons sont écartés à
    # la source, à l'assemblage (`rendu_word/assemblage.py`).
    vues: dict[str, int] = {}
    for numero, page in enumerate(lecteur.pages if avec_images else [], start=1):
        if numero in (1, derniere):
            continue
        try:
            images = list(page.images)
        except Exception:  # noqa: BLE001 — une image illisible ne fait pas tomber le contrôle
            continue
        for image in images:
            donnees = getattr(image, "data", b"") or b""
            if len(donnees) < OCTETS_MIN_FIGURE:
                continue
            empreinte = hashlib.sha256(donnees).hexdigest()
            if empreinte in vues:
                constats.append(ConstatPdf(
                    "figure_en_double",
                    f"La même figure apparaît page {vues[empreinte]} et page {numero}.",
                    page=numero,
                ))
            else:
                vues[empreinte] = numero
    return constats


def chapitres_annonces(deliverable_type: str) -> int | None:
    """Le nombre de chapitres VENDUS : ceux du plan, ouverture exclue (décision D9).

    Même lecture que le suivi client (`organisations.suivi.chapitres_annonces`)
    : le plan (`generation/blueprints.py`) est la seule source.
    """
    from generation.blueprints import SectionKind, chapters_for_deliverable  # noqa: PLC0415

    try:
        plan = chapters_for_deliverable(deliverable_type)
    except ValueError:
        return None
    return sum(1 for bp in plan if bp.section_kind != SectionKind.OPENING)


"""Le PDF final est relu comme le client le lit — en-tête, pages, chapitres, auteur.

29/09/2026, business plan ÉCLORE (107 pages) : en-tête de deux lignes répété
sur 105 pages, auteur du PDF égal à une phrase entière, 22 chapitres numérotés
pour 21 annoncés. Rien de cela n'était visible dans le XML du Word, seul relu
jusqu'ici. Sur le vrai PDF (copie locale hors dépôt), `controler_le_pdf`
retrouve les trois en 3,5 s ; ces tests le verrouillent sur des PDF de synthèse.
"""
from __future__ import annotations

import io

import pytest

from catalog.models import DeliverableType
from generation.verification.pdf import chapitres_annonces, controler_le_pdf

reportlab = pytest.importorskip("reportlab")

ENTETE_LONG = (
    "PROJET (nom de projet provisoire), avec pour signature « Expériences bien-être, "
    "créatives et inspirantes » / Business plan"
)


def _pdf(
    pages: list[list[str]], *, entete: str = "Projet / Business plan", auteur: str = ""
) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    tampon = io.BytesIO()
    toile = canvas.Canvas(tampon, pagesize=A4)
    if auteur:
        toile.setAuthor(auteur)
    for lignes in pages:
        toile.setFont("Helvetica", 7)
        toile.drawString(40, 810, entete)
        y = 760
        for ligne in lignes:
            toile.setFont("Helvetica", 10)
            toile.drawString(40, y, ligne)
            y -= 16
        toile.showPage()
    toile.save()
    return tampon.getvalue()


def _corps(n: int) -> list[str]:
    return [f"Paragraphe {i} du document, avec assez de mots pour une page." for i in range(n)]


def _document(chapitres: int) -> list[list[str]]:
    pages = [["Couverture du document de démonstration"]]
    for numero in range(1, chapitres + 1):
        pages.append([f"CHAPITRE {numero:02d}", *_corps(4)])
    pages.append(["Projet", "Document confidentiel — reproduction interdite"])
    return pages


def _controles(constats: list[object]) -> set[str]:
    return {c.controle for c in constats}  # type: ignore[attr-defined]


def test_un_pdf_propre_ne_donne_aucun_constat() -> None:
    pdf = _pdf(_document(21), auteur="Carine Martin")
    assert controler_le_pdf(pdf, chapitres_annonces=21, auteur_attendu="Carine Martin") == []


def test_un_en_tete_trop_long_est_vu() -> None:
    pdf = _pdf(_document(21), entete=ENTETE_LONG)
    assert "entete_trop_long" in _controles(controler_le_pdf(pdf))


def test_un_chapitre_de_trop_est_vu() -> None:
    """ÉCLORE : l'annexe des chiffres numérotée 22 pour 21 chapitres annoncés."""
    pdf = _pdf(_document(22))
    constats = controler_le_pdf(pdf, chapitres_annonces=21)
    assert "nombre_de_chapitres" in _controles(constats)


def test_l_auteur_doit_etre_le_porteur() -> None:
    pdf = _pdf(_document(3), auteur="PROJET (nom de projet provisoire), avec pour signature")
    constats = controler_le_pdf(pdf, auteur_attendu="Carine Martin")
    assert "auteur_du_pdf" in _controles(constats)


def test_une_page_vide_est_vue_mais_pas_la_quatrieme_de_couverture() -> None:
    pages = _document(3)
    pages.insert(2, [])
    constats = controler_le_pdf(_pdf(pages))
    vides = [c for c in constats if c.controle == "page_vide"]
    assert [c.page for c in vides] == [3]


def test_une_source_seule_en_haut_de_page_est_vue() -> None:
    pages = _document(3)
    pages[2] = ["Source : données du projet", *_corps(4)]
    constats = controler_le_pdf(_pdf(pages))
    assert "source_orpheline" in _controles(constats)


@pytest.mark.parametrize(("livrable", "annonce"), [
    (DeliverableType.MARKET_STUDY, 22),
    (DeliverableType.COMPETITOR_STUDY, 9),
    (DeliverableType.BUSINESS_PLAN, 21),
    (DeliverableType.BUSINESS_STRATEGY, 20),
])
def test_le_nombre_annonce_vient_du_plan(livrable: str, annonce: int) -> None:
    assert chapitres_annonces(livrable) == annonce

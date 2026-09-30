"""Relecture, classe 10 — la mise en page, et les trois défauts corrigés au rendu.

Les défauts viennent du business plan ÉCLORE `28a257bf` (30/09/2026) : une
cellule de l'annexe coupée par « … » (produite par `libelle_court`) ; une page
qui ne porte qu'une légende, une page blanche entre deux chapitres (le saut de
page était un caractère) ; des centaines d'espaces ordinaires entre un
nombre et « € » ou « % » (`montant_lisible` en écrivait lui-même) ; un
montant à une décimale parmi des centimes dans un même tableau.

Textes et chiffres FICTIFS : le document de la cliente ne quitte jamais
`tests/fixtures/`.
"""
from __future__ import annotations

from datetime import date

from docx import Document as DocumentWord
from docx.oxml.ns import qn

from generation.relecture import (
    Constat,
    Document,
    Reference,
    Section,
    Tableau,
    document_du_chapitre,
    mise_en_page,
)
from generation.rendu_word import composants
from generation.rendu_word.annexe_chiffres import blocs_annexe, meme_arrondi
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Zone, montant_lisible

DOCUMENT_ENTIER = Reference(livrable="business_plan", document_entier=True)
UN_CHAPITRE = Reference(livrable="business_plan")
INSECABLE = chr(0xA0)
FINE_INSECABLE = chr(0x202F)


def _section(numero: str, *tableaux: Tableau) -> Section:
    return Section(numero=numero, titre="", chapitre=int(numero.split(".")[0]),
                   tableaux=list(tableaux))


def _constats(document: Document, reference: Reference = UN_CHAPITRE) -> list[Constat]:
    constats = mise_en_page.controler(document, reference)
    assert all(c.classe == "mise_en_page" for c in constats)
    return constats


# ── Cellules coupées par « … » ──────────────────────────────────────────────

COUPEE = "Marge des ateliers de rempotage : l'essentiel des frais de terreau…"


def test_une_cellule_coupee_par_des_points_de_suspension_est_signalee() -> None:
    tableau = Tableau(("Donnée", "Valeur"), ((COUPEE, "100 %"),))
    constats = _constats(Document([_section("12.4", tableau)]))
    assert [c.section for c in constats] == ["12.4"], constats
    assert constats[0].extrait.endswith("frais de terreau…")
    assert constats[0].grave, "sur un chapitre, c'est le texte du rédacteur : il se réécrit"
    sur_le_rendu = _constats(Document([_section("12.4", tableau)]), DOCUMENT_ENTIER)
    assert not sur_le_rendu[0].grave


def test_contre_epreuve_amorces_voulues_et_etc() -> None:
    """« Accélérer si… / Ralentir si… » sont des en-têtes voulus ; « etc… » n'est pas une coupe."""
    tableau = Tableau(
        ("Signal", "Accélérer si…", "Ralentir si…"),
        (("Remplissage", "Plus de 80 % deux fois", "Semis, rempotage, bouturage, etc…"),),
    )
    assert _constats(Document([_section("11.5", tableau)])) == []


def test_l_annexe_des_chiffres_n_ecrit_plus_de_libelle_coupe() -> None:
    """Le défaut À LA SOURCE : `libelle_court` coupait à 110 signes avec « … ». Le
    contrôle relit ce que le rendu écrit (règle 3)."""
    libelle = (
        "Taux de marge sur coûts variables du jardin partagé : la quasi-totalité des frais "
        "d'atelier, terreau et outillage compris, traitée comme une charge externe"
    )
    assert len(libelle) > 110
    socle = Socle(
        secteur="jardinage", zone=Zone(pays="France"), date_socle=date(2026, 9, 30),
        donnees=[DonneeSocle(
            id="marge_brute_taux", libelle=libelle, valeur=100.0, unite="%", annee=2027,
            perimetre=Perimetre.ENTREPRISE, fiabilite=Fiabilite.SCENARIO,
        )],
    )
    document = document_du_chapitre({"chapitre": 22, "blocs": blocs_annexe(socle)})
    cellules = [c for s in document.sections for t in s.tableaux for c in t.cellules()]
    assert libelle in cellules, cellules
    assert _constats(document, DOCUMENT_ENTIER) == []


# ── Un arrondi par tableau ──────────────────────────────────────────────────


def test_deux_arrondis_dans_un_meme_tableau_sont_signales() -> None:
    tableau = Tableau(
        ("Indicateur", "2027", "2028", "2029"),
        (("Chiffre d'affaires mensuel moyen", "2 000 €", "3 000 €", "4 166,67 €"),),
    )
    constats = _constats(Document([_section("10.5", tableau)]))
    assert [(c.section, c.extrait) for c in constats] == [("10.5", "4 166,67 €")], constats
    assert "2 000 €" in constats[0].detail and not constats[0].grave


def test_un_montant_a_une_decimale_parmi_des_centimes() -> None:
    tableau = Tableau(("Année", "Revenu mensuel"), (("2027", "3,12 €"), ("2028", "48,07 €"),
                                                    ("2029", "152,5 €")))
    constats = _constats(Document([_section("2.4", tableau)]))
    assert [c.extrait for c in constats] == ["152,5 €"], constats


def test_l_annexe_des_chiffres_ecrit_ses_montants_au_meme_arrondi() -> None:
    """À LA SOURCE : l'annexe construite par notre code écrivait « 2 000 € » à côté
    de « 4 166,67 € ». Le contrôle relit ce qu'elle rend (règle 3)."""
    def donnee(identifiant: str, valeur: float) -> DonneeSocle:
        return DonneeSocle(
            id=identifiant, libelle=identifiant, valeur=valeur, unite="EUR", annee=2027,
            perimetre=Perimetre.ENTREPRISE, fiabilite=Fiabilite.DECLAREE,
        )

    socle = Socle(
        secteur="jardinage", zone=Zone(pays="France"), date_socle=date(2026, 9, 30),
        donnees=[donnee("apport", 2_000.0), donnee("investissement_total", 4_166.67)],
    )
    document = document_du_chapitre({"chapitre": 22, "blocs": blocs_annexe(socle)})
    valeurs = [ligne[1] for s in document.sections for t in s.tableaux for ligne in t.lignes]
    assert valeurs == ["2 000,00 €", "4 166,67 €"], valeurs
    assert _constats(document, DOCUMENT_ENTIER) == []


def test_meme_arrondi_complete_sans_jamais_arrondir() -> None:
    """Par unité, au plus grand nombre de décimales de la colonne ; une grandeur
    non monétaire traverse."""
    paires = [
        (f"2{INSECABLE}000", "€"), (f"4{INSECABLE}166,67", "€"), (f"15{INSECABLE}000", ""),
        ("3,5", "Md€"), ("30", "Md€"), ("8", "%"),
    ]
    assert meme_arrondi(paires) == [
        f"2{INSECABLE}000,00", f"4{INSECABLE}166,67", f"15{INSECABLE}000", "3,5", "30,0", "8",
    ]


def test_contre_epreuve_un_seul_arrondi_phrases_et_encadres() -> None:
    """Tous au centime ; des montants dans une PHRASE de cellule ; un encadré sans
    lignes ; deux unités différentes : rien à dire."""
    au_centime = Tableau(("Indicateur", "2027", "2028"),
                         (("CA mensuel", "2 000,00 €", "4 166,67 €"),))
    phrase = Tableau(("Poste", "Montant"), (
        ("Réserve", "2 000 €"),
        ("Coussin", "1 400 € sur 5 000 €, soit trois mois de charges (398,75 €)"),
    ))
    encadre = Tableau(("VERDICT", "Une réserve de 1 400 € couvre 398,75 € par mois."), ())
    unites = Tableau(("Périmètre", "Valeur"), (("Marché", "16,5 Md€"), ("Projet", "320 000 €")))
    document = Document([_section("15.1", au_centime, phrase, encadre, unites)])
    assert _constats(document) == []


# ── Pages presque vides ─────────────────────────────────────────────────────

MOTS = ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf")


def _page(numero: int, *lignes: str) -> str:
    return "\n".join((
        "Atelier Fictif  /  Business plan",
        f"Document confidentiel — usage interne  ·{numero}", *lignes,
    ))


def _corps(numero: int) -> list[str]:
    mot = MOTS[numero % len(MOTS)]
    return [f"Ligne {mot} {lettre} du texte courant." for lettre in "abcdefghijkl"]


def test_une_page_presque_vide_est_signalee() -> None:
    pages = [
        "BUSINESS PLAN\nAtelier Fictif\n30 septembre 2026",
        _page(2, *_corps(2)), _page(3, *_corps(3)),
        _page(4, "Données du socle vérifié"),
        _page(5), _page(6, *_corps(6)),
        "Atelier Fictif\nBusiness plan · 30 septembre 2026",
    ]
    document = Document(sections=[], pages=pages)
    constats = _constats(document, DOCUMENT_ENTIER)
    presque_vides = [(c.section, c.extrait) for c in constats]
    assert presque_vides == [
        ("p. 4", "Données du socle vérifié"), ("p. 5", "(page blanche)"),
    ], constats
    assert "1 ligne(s) utile(s)" in constats[0].detail


def test_contre_epreuve_couvertures_en_tetes_et_chapitre_seul() -> None:
    """La couverture et la 4e de couverture ont peu de lignes, c'est leur dessin ;
    l'en-tête courant ne compte pas ; sans pages (un chapitre), rien à juger."""
    pages = [
        "BUSINESS PLAN\nAtelier Fictif",
        *(_page(n, *_corps(n)) for n in range(2, 6)),
        "Atelier Fictif",
    ]
    assert _constats(Document(sections=[], pages=pages), DOCUMENT_ENTIER) == []
    assert _constats(Document(sections=[], pages=pages), UN_CHAPITRE) == []


# ── Espace insécable avant « € » et « % » ───────────────────────────────────


def test_une_espace_ordinaire_avant_l_unite_est_signalee_une_fois() -> None:
    pages = [
        "Couverture",
        _page(2, "Le chiffre d'affaires atteint 31 470 € en 2027,", "soit une marge de 8 %."),
        _page(3, f"Le résultat atteint 1{INSECABLE}200 €", "puis 3 400 \n€ en 2029."),
        "Fin",
    ]
    constats = [
        c for c in _constats(Document(sections=[], pages=pages), DOCUMENT_ENTIER)
        if "insécable" in c.detail
    ]
    assert [(c.section, c.extrait) for c in constats] == [
        ("p. 2", "d'affaires atteint 31 470 €")
    ], constats
    assert constats[0].detail.startswith("4 espace(s) ordinaire(s)")


def test_contre_epreuve_espaces_insecables() -> None:
    pages = [
        "Couverture",
        _page(2, f"Le chiffre d'affaires atteint 31{INSECABLE}470{INSECABLE}€ en 2027,",
              f"soit une marge de 8{FINE_INSECABLE}% et 2025-2026 sans unité.",
              # Deux cellules voisines, pas un montant coupé en fin de ligne.
              "2027", "% du chiffre d'affaires"),
        "Fin",
    ]
    constats = _constats(Document(sections=[], pages=pages), DOCUMENT_ENTIER)
    assert not [c for c in constats if "insécable" in c.detail], constats


def test_le_formateur_des_montants_ecrit_une_espace_insecable_et_les_centimes() -> None:
    """Le défaut À LA SOURCE : `montant_lisible` posait une espace ordinaire avant
    l'unité, et « 152,5 € » perdait son zéro de centimes."""
    ecrits = [
        montant_lisible(31_470.0, "EUR"), montant_lisible(16.5, "MdEUR"),
        montant_lisible(152.5, "EUR"), montant_lisible(8.0, "%"),
    ]
    assert all(" " not in ecrit for ecrit in ecrits), ecrits
    assert ecrits[2] == f"152,50{INSECABLE}€"
    pages = ["Couverture", _page(2, *ecrits), "Fin"]
    constats = _constats(Document(sections=[], pages=pages), DOCUMENT_ENTIER)
    assert not [c for c in constats if "insécable" in c.detail], constats


# ── Le saut de page ne crée plus de page blanche ────────────────────────────


def test_un_saut_de_page_vit_sur_le_paragraphe() -> None:
    """Une page blanche entre deux chapitres : un paragraphe qui ne portait QU'UN caractère de
    saut est tombé en haut de page, et son saut en a ouvert une autre. Mesuré au
    rendu LibreOffice le 30/09/2026 : 51 lignes avant le saut donnaient une page
    blanche avec le caractère, aucune avec `page_break_before`."""
    document = DocumentWord()
    document.add_paragraph("Fin du chapitre précédent.")
    composants.saut_de_page(document)
    saut = document.paragraphs[-1]._p
    assert saut.xpath("./w:pPr/w:pageBreakBefore"), "le saut vit sur le paragraphe"
    assert not saut.findall(".//" + qn("w:br")), "plus de caractère de saut"


def test_un_saut_de_page_n_est_pas_une_ligne_blanche_a_retirer() -> None:
    """Contre-épreuve : le nettoyage des lignes blanches finales ne l'emporte pas."""
    document = DocumentWord()
    document.add_paragraph("Dernier paragraphe.")
    composants.saut_de_page(document)
    assert composants.retirer_les_lignes_blanches_finales(document) == 0

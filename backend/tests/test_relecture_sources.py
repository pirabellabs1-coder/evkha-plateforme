"""Relecture, classe 9 — les sources.

Les défauts viennent du business plan ÉCLORE `28a257bf` (30/09/2026) : une
même donnée sourcée écrite en toutes lettres ici, en pourcentage ailleurs ;
l'article L221-18 (rétractation de 14 jours) cité pour des ateliers à date
fixe, que l'article L221-28 12° exclut ; des sources citées absentes du
chapitre des sources, et des sources listées jamais citées ; un chiffre de
marché porté par un blog, écrit comme un fait établi.

Les textes, les sources et les chiffres ci-dessous sont FICTIFS : le document
de la cliente ne quitte jamais `tests/fixtures/` (jamais versionné).
"""
from __future__ import annotations

from generation.relecture import Constat, Document, Reference, Section, Tableau, sources

DOCUMENT_ENTIER = Reference(livrable="business_plan", document_entier=True)
UN_CHAPITRE = Reference(livrable="business_plan")


def _section(numero: str, *paragraphes: str, tableaux: tuple[Tableau, ...] = (),
             titre: str = "") -> Section:
    chapitre = int(numero.removeprefix("ch. ").split(".")[0])
    return Section(
        numero=numero, titre=titre, chapitre=chapitre,
        paragraphes=list(paragraphes), tableaux=list(tableaux),
    )


def _tableau(entetes: tuple[str, ...], *lignes: tuple[str, ...]) -> Tableau:
    return Tableau(entetes=entetes, lignes=tuple(lignes))


def _constats(document: Document, reference: Reference = DOCUMENT_ENTIER) -> list[Constat]:
    constats = sources.controler(document, reference)
    assert all(c.classe == "source" for c in constats)
    return constats


LISTE = _tableau(
    ("Organisme", "Ce que la source étaye", "Adresse"),
    ("Institut Fictif du Jardin", "Pratique du jardinage amateur",
     "https://www.institut-fictif.fr/ etude-jardinage-2025"),
    ("Le Carnet Vert", "Taille du marché du jardinage",
     "https://www.carnet-vert.fr/blog/ marche-du-jardin"),
)


def _chapitre_des_sources(*tableaux: Tableau) -> list[Section]:
    return [
        _section("ch. 9", "D'où viennent les chiffres de cette étude.",
                 titre="SOURCES ET MÉTHODOLOGIE"),
        _section("9.1", "Les chiffres de cadrage viennent de sources publiques.",
                 tableaux=tableaux or (LISTE,), titre="Données sectorielles"),
    ]


# ── Une donnée sourcée, une formulation ─────────────────────────────────────

EN_LETTRES = (
    "Trois jardiniers sur quatre sèment leurs légumes au printemps (Institut Fictif du "
    "Jardin, 2025), un terrain favorable aux ateliers."
)
EXACTE = (
    "72 % des jardiniers sèment leurs légumes au printemps selon l'enquête (Institut "
    "Fictif du Jardin, 2025)."
)


def test_une_donnee_sourcee_en_toutes_lettres_est_signalee() -> None:
    """Le défaut : une proportion en toutes lettres là où la même source publie un
    pourcentage exact."""
    document = Document([_section("2.1", EN_LETTRES), _section("4.2", EXACTE)])
    constats = _constats(document, UN_CHAPITRE)
    assert [c.section for c in constats] == ["2.1"], constats
    assert "Trois jardiniers sur quatre" in constats[0].extrait
    assert "« 72 % »" in constats[0].detail and "4.2" in constats[0].detail
    assert constats[0].grave


def test_deux_valeurs_exactes_pour_la_meme_donnee() -> None:
    divergente = EXACTE.replace("72 %", "68 %")
    document = Document([
        _section("2.1", EXACTE), _section("3.1", EXACTE), _section("4.2", divergente),
    ])
    constats = _constats(document, UN_CHAPITRE)
    assert [c.section for c in constats] == ["4.2"], constats
    assert "« 72 % »" in constats[0].detail
    assert not constats[0].grave, "deux pourcentages d'une source : un signal, pas une réécriture"


def test_contre_epreuve_meme_formulation_ou_autre_sujet() -> None:
    """Deux fois « 72 % » ; une autre donnée de la même source ; une proportion
    en lettres que rien ne contredit : rien à dire."""
    autre_sujet = (
        "La moitié des jardiniers arrosent le soir après le travail (Institut Fictif du "
        "Jardin, 2025)."
    )
    document = Document([
        _section("2.1", EXACTE), _section("4.2", EXACTE), _section("5.1", autre_sujet),
    ])
    assert _constats(document, UN_CHAPITRE) == []
    assert _constats(Document([_section("2.1", EN_LETTRES)]), UN_CHAPITRE) == []


def test_contre_epreuve_une_serie_annuelle_ou_une_source_de_section() -> None:
    """Revue du 30/09/2026 : « 5 % en 2024 » et « 7 % en 2025 » sont une série ; une
    ligne « Source : » de section couvre plusieurs données — rien n'est signalé."""
    serie = Document([
        _section("2.1", "Le marché du jardinage amateur progresse de 5 % en 2024 (Institut "
                        "Fictif du Jardin, 2025)."),
        _section("2.2", "Le marché du jardinage amateur progresse de 7 % en 2025 (Institut "
                        "Fictif du Jardin, 2025)."),
    ])
    assert _constats(serie, UN_CHAPITRE) == []
    ventilation = Document([
        _section("3.1", "Trois jardiniers sur quatre achètent leurs graines en jardinerie.",
                 "Source : Institut Fictif du Jardin, 2025"),
        _section("3.2", "30 % des jardiniers achètent leurs graines en ligne.",
                 "Source : Institut Fictif du Jardin, 2025"),
    ])
    assert _constats(ventilation, UN_CHAPITRE) == []


# ── Les articles de loi ─────────────────────────────────────────────────────

RETRACTATION = _tableau(
    ("Obligation", "Référence", "Ce qu'elle impose"),
    ("Délai de rétractation", "Article L.221-18 du code de la consommation",
     "Quatorze jours pour se rétracter après la réservation"),
)


ACTIVITES = "Les ateliers de rempotage et les week-ends au potager se tiennent à date fixe."


def test_la_retractation_d_un_atelier_a_date_fixe_cite_l221_28() -> None:
    document = Document([_section("7.3", ACTIVITES, tableaux=(RETRACTATION,))])
    constats = _constats(document, UN_CHAPITRE)
    assert [c.section for c in constats] == ["7.3"], constats
    assert "L.221-18" in constats[0].extrait
    assert "L221-28 12°" in constats[0].detail and constats[0].grave


def test_un_contexte_lu_seulement_ailleurs_dans_le_document_est_un_signal() -> None:
    """Les activités sont décrites dans une autre section : constat, mais pas grave."""
    document = Document([
        _section("4.1", ACTIVITES),
        _section("13.6", "Les obligations propres au secteur.", tableaux=(RETRACTATION,)),
    ])
    constats = _constats(document, UN_CHAPITRE)
    assert [(c.section, c.grave) for c in constats] == [("13.6", False)], constats


def test_contre_epreuve_vente_en_ligne_ou_exception_citee() -> None:
    """Une boutique en ligne relève bien de L221-18 ; un atelier de réparation n'est
    pas un loisir ; citer L221-28 12° est juste."""
    boutique = Document([_section(
        "7.3", "La boutique vend des graines en ligne, livrées à domicile.",
        tableaux=(RETRACTATION,),
    )])
    assert _constats(boutique, UN_CHAPITRE) == []
    biens = _tableau(
        ("Obligation", "Référence"),
        ("Rétractation sur les outils vendus en ligne", "Article L221-18 du code de la "
                                                         "consommation"),
    )
    mixte = Document([_section("7.2", ACTIVITES), _section("7.3", "La boutique.",
                                                           tableaux=(biens,))])
    assert _constats(mixte, UN_CHAPITRE) == []
    reparation = Document([_section(
        "7.3", "L'atelier de réparation remet les vélos en état.", tableaux=(RETRACTATION,),
    )])
    assert _constats(reparation, UN_CHAPITRE) == []
    exception = _tableau(
        ("Obligation", "Référence"),
        ("Rétractation", "Pas de droit de rétractation (article L221-28 12°), et non "
                         "L221-18 : activité de loisirs à date déterminée"),
    )
    ateliers = Document([_section(
        "7.3", "Les ateliers de rempotage se tiennent à date fixe.", tableaux=(exception,),
    )])
    assert _constats(ateliers, UN_CHAPITRE) == []


# ── Citées contre listées ───────────────────────────────────────────────────


def test_une_source_citee_absente_de_la_liste_est_signalee() -> None:
    document = Document([
        _section("2.1",
                 "Le jardinage attire de nouveaux pratiquants (Observatoire Régional des "
                 "Loisirs, 2024).",
                 "Source : Institut Fictif du Jardin, 2025"),
        _section("2.2", "Le marché du jardinage est estimé à 4 Md€ (Le Carnet Vert, 2025)."),
        *_chapitre_des_sources(),
    ])
    constats = _constats(document)
    assert [(c.section, "Observatoire Régional des Loisirs" in c.detail) for c in constats] == [
        ("2.1", True)
    ], constats
    assert not constats[0].grave


def test_une_source_listee_jamais_citee_est_signalee() -> None:
    liste = _tableau(
        LISTE.entetes, *LISTE.lignes,
        ("Annuaire Fictif des Pépinières", "Nombre de pépinières",
         "https://www.annuaire-pepinieres.fr/ liste"),
    )
    document = Document([
        _section("2.1", "Source : Institut Fictif du Jardin, 2025 ; Le Carnet Vert, 2025"),
        *_chapitre_des_sources(liste),
    ])
    constats = _constats(document)
    assert [(c.section, c.extrait) for c in constats] == [
        ("9.1", "Annuaire Fictif des Pépinières")
    ], constats


def test_contre_epreuve_liste_et_citations_d_accord() -> None:
    """Chaque source citée est listée, chaque source listée est citée — et sur un
    chapitre seul, la liste n'est pas là : rien à rapprocher."""
    document = Document([
        _section("2.1", "Source : Institut Fictif du Jardin, 2025 ; carnet-vert.fr, 2025",
                 "Le jardinage progresse (France, 2026) et les ateliers aussi (données du "
                 "projet, 2027)."),
        *_chapitre_des_sources(),
    ])
    assert _constats(document) == []
    seul = Document([_section("2.1", "Le jardinage progresse (Observatoire Régional des "
                                     "Loisirs, 2024).")])
    assert _constats(seul, UN_CHAPITRE) == []


def test_sans_chapitre_des_sources_le_document_entier_le_dit() -> None:
    """Règle 1 : sans liste, la comparaison n'a rien à comparer — ce n'est pas un succès."""
    document = Document([_section("2.1", "Source : Institut Fictif du Jardin, 2025")])
    constats = _constats(document)
    assert len(constats) == 1 and "Aucun chapitre « Sources »" in constats[0].detail
    assert _constats(document, UN_CHAPITRE) == []


# ── Un blog ne porte pas un chiffre de marché ───────────────────────────────


def test_un_chiffre_de_marche_porte_par_un_blog_est_signale() -> None:
    document = Document([
        _section("2.2", "Le marché français du jardinage atteint 4 Md€ en 2025 (Le Carnet "
                        "Vert, 2025).",
                 "Source : Institut Fictif du Jardin, 2025"),
        *_chapitre_des_sources(),
    ])
    constats = _constats(document)
    assert [c.section for c in constats] == ["2.2"], constats
    assert "« 4 Md€ »" in constats[0].detail and "estimé" in constats[0].detail
    assert constats[0].grave


def test_sur_un_chapitre_seul_l_adresse_dit_la_nature() -> None:
    """Sans chapitre des sources, une adresse de lettre d'information suffit."""
    document = Document([_section(
        "2.2", "Le marché du jardinage bio pèse 600 M€ (lettre-jardin.substack.com, 2026).",
    )])
    assert [c.section for c in _constats(document, UN_CHAPITRE)] == ["2.2"]


def test_contre_epreuve_chiffre_estime_ou_source_publique() -> None:
    document = Document([
        _section("2.2", "Le marché français du jardinage est estimé à 4 Md€ (Le Carnet Vert, "
                        "2025).",
                 "Le marché des outils atteint 2 Md€ (Institut Fictif du Jardin, 2025)."),
        *_chapitre_des_sources(),
    ])
    assert _constats(document) == []


# ── L'annexe des chiffres ───────────────────────────────────────────────────

ENTETES_ANNEXE = ("Donnée", "Valeur", "Année", "Origine")


def test_l_annexe_rattache_le_chiffre_a_son_blog_et_juge_son_origine() -> None:
    annexe = _tableau(
        ENTETES_ANNEXE,
        ("Marché du jardinage en France", "4 Md€", "2025", "Estimée — Le Carnet Vert, 2025"),
        ("Marché des semences en France", "900 M€", "2025", "Vérifiée — Le Carnet Vert, 2025"),
        ("Jardiniers amateurs en France", "15 000 000", "2024",
         "Estimée — Institut Fictif du Jardin, Chiffres-clés 2024"),
    )
    document = Document([
        _section("3.1", "Le marché du jardinage pèse 4 Md€, un contexte porteur.",
                 "Source : Institut Fictif du Jardin, 2025 ; Le Carnet Vert, 2025"),
        *_chapitre_des_sources(),
        _section("9.3", "Chaque chiffre de cette étude avec son origine.",
                 tableaux=(annexe,)),
    ])
    constats = _constats(document)
    assert any(
        c.section == "3.1" and c.extrait.startswith("Le marché du jardinage pèse 4 Md€")
        for c in constats
    ), constats
    assert any("« Vérifiée »" in c.detail and "Carnet Vert" in c.detail for c in constats)
    assert any("Institut Fictif du Jardin" in c.detail and "recoupement" in c.detail
               for c in constats)
    assert len(constats) == 3, constats


def test_contre_epreuve_origines_justes() -> None:
    annexe = _tableau(
        ENTETES_ANNEXE,
        ("Marché du jardinage en France", "4 Md€", "2025", "Estimée — Le Carnet Vert, 2025"),
        ("Jardiniers amateurs en France", "15 000 000", "2024",
         "Vérifiée — Institut Fictif du Jardin, 2024"),
        ("Panier moyen par participant", "45 €", "2027", "Déclarée — données du projet"),
    )
    document = Document([
        _section("3.1", "Source : Institut Fictif du Jardin, 2025 ; Le Carnet Vert, 2025",
                 "Le marché du jardinage est estimé à 4 Md€."),
        *_chapitre_des_sources(),
        _section("9.3", "Chaque chiffre de cette étude avec son origine.",
                 tableaux=(annexe,)),
    ])
    assert _constats(document) == []

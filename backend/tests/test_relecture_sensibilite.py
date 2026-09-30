"""Relecture, classe 11 — l'analyse de sensibilité (détection seulement).

Le défaut vient du business plan ÉCLORE `28a257bf` (30/09/2026) : une section
de sensibilité titrée sur une baisse de 10 % du chiffre d'affaires, aucun
scénario à −20 %, aucun montant pour −10 %, et une phrase qui renonce au
calcul (il « exigerait » des hypothèses « non arbitrées »).

Textes et chiffres FICTIFS : le document de la cliente ne quitte jamais
`tests/fixtures/`.
"""
from __future__ import annotations

from generation.relecture import Document, Reference, Section, Tableau, sensibilite

BP_ENTIER = Reference(livrable="business_plan", document_entier=True)
BP_CHAPITRE = Reference(livrable="business_plan")

RENONCEMENT = (
    "Le plan ne donne pas de compte de résultat recalculé pour une baisse de 10 % "
    "des ventes : il faudrait ventiler les charges, ce que le porteur n'a pas fait."
)


def _section(numero: str, *paragraphes: str, titre: str = "",
             tableaux: tuple[Tableau, ...] = ()) -> Section:
    chapitre = int(numero.removeprefix("ch. ").split(".")[0])
    return Section(numero=numero, titre=titre, chapitre=chapitre,
                   paragraphes=list(paragraphes), tableaux=list(tableaux))


def _constats(document: Document, reference: Reference) -> list:
    constats = sensibilite.controler(document, reference)
    assert all(c.classe == "sensibilite" for c in constats)
    return constats


# ── La phrase de renoncement ────────────────────────────────────────────────


def test_la_phrase_qui_renonce_au_calcul_est_signalee_sur_un_chapitre() -> None:
    document = Document([
        _section("16.6", RENONCEMENT, titre="Lecture de sensibilité"),
        _section("16.7", "Le scénario à −20 % n'a pas été chiffré, faute de données.",
                 titre="Trésorerie"),
    ])
    constats = _constats(document, BP_CHAPITRE)
    assert [c.section for c in constats] == ["16.6", "16.7"], constats
    assert constats[0].extrait.startswith("Le plan ne donne pas de compte de résultat")
    assert all(c.grave for c in constats)


def test_contre_epreuve_une_conclusion_n_est_pas_un_renoncement() -> None:
    """La négation porte sur le résultat, pas sur le calcul ; ou la section ne parle
    pas de sensibilité ; ou le livrable n'est pas un business plan."""
    document = Document([
        _section(
            "16.6",
            "Le scénario à −20 % ne permet pas de couvrir les charges fixes : le résultat "
            "net devient négatif (−2 400 €).",
            "Le résultat n'est pas négatif dans le scénario à −10 %.",
            "Une baisse de 20 % du chiffre d'affaires rendrait impossible le remboursement.",
            titre="Sensibilité",
        ),
        _section("16.7", "Le dossier ne détaille pas le tableau mensuel de trésorerie.",
                 titre="Trésorerie de la première année"),
    ])
    assert _constats(document, BP_CHAPITRE) == []
    # Revue du 30/09/2026 : quatre conclusions ordinaires qu'une première version
    # prenait pour des renoncements.
    conclusions = Document([_section(
        "16.6",
        "Une baisse de 20 % du chiffre d'affaires n'est pas le scénario central.",
        "À −20 %, le compte de résultat devient déficitaire (−2 400 €), ce qui "
        "nécessiterait un apport complémentaire.",
        "Dans le scénario dégradé, l'entreprise ne peut plus construire sa deuxième serre.",
        titre="Sensibilité",
    ), _section("4.2", "Nos séances de gestion du stress sont très demandées ; ce chiffre "
                       "est impossible à garantir.", titre="L'offre")])
    assert _constats(conclusions, BP_CHAPITRE) == []
    renonce = Document([_section("16.6", RENONCEMENT, titre="Sensibilité")])
    assert _constats(renonce, Reference(livrable="market_study", document_entier=True)) == []


# ── Les deux scénarios, chiffrés ────────────────────────────────────────────


def _scenarios(*lignes: tuple[str, ...]) -> Tableau:
    return Tableau(("Scénario", "Chiffre d'affaires", "Résultat net"),
                   (("Central", "50 000 €", "8 000 €"), *lignes))


MOINS_10 = ("−10 % de chiffre d'affaires", "45 000 €", "3 000 €")
MOINS_20 = ("−20 % de chiffre d'affaires", "40 000 €", "−2 000 €")


def test_le_scenario_a_moins_20_pourcent_manque() -> None:
    document = Document([
        _section("ch. 16", "Trois exercices.", titre="Prévisionnel financier"),
        _section("16.6", "Le scénario central tient ; la baisse se lit ci-dessous.",
                 titre="Sensibilité du résultat", tableaux=(_scenarios(MOINS_10),)),
    ])
    constats = _constats(document, BP_ENTIER)
    assert [c.section for c in constats] == ["16.6"], constats
    assert "−20 %" in constats[0].detail and "−10 %," not in constats[0].detail


def test_un_titre_sans_un_seul_montant_n_est_pas_un_scenario() -> None:
    """Le cas du 30/09 : la baisse de 10 % au titre, pas un chiffre dessous."""
    document = Document([
        _section("ch. 16", "Trois exercices.", titre="Prévisionnel financier"),
        _section("16.6", RENONCEMENT,
                 titre="Sensibilité : chiffre d'affaires en baisse de 10 %"),
    ])
    constats = _constats(document, BP_ENTIER)
    manquants = [c for c in constats if c.detail.startswith("Scénario(s)")]
    assert len(manquants) == 1 and manquants[0].section == "16.6", constats
    assert "−10 %, −20 %" in manquants[0].detail
    assert "annoncé sans un seul montant" in manquants[0].detail


def test_sans_section_de_sensibilite_le_prevesionnel_porte_le_constat() -> None:
    document = Document([
        _section("ch. 16", "Trois exercices.", titre="Prévisionnel financier"),
        _section("16.2", "Le chiffre d'affaires atteint 50 000 € en 2027.",
                 titre="Compte de résultat"),
    ])
    constats = _constats(document, BP_ENTIER)
    assert [c.section for c in constats] == ["ch. 16"], constats


def test_contre_epreuve_les_deux_scenarios_chiffres() -> None:
    """Les deux scénarios chiffrés : rien. Sur un chapitre seul, l'absence ne se
    juge pas (le scénario peut vivre dans un autre chapitre)."""
    complet = Document([
        _section("16.6", "Charges fixes inchangées.", titre="Sensibilité",
                 tableaux=(_scenarios(MOINS_10, MOINS_20),)),
    ])
    assert _constats(complet, BP_ENTIER) == []
    en_phrases = Document([_section(
        "16.6",
        "À −10 % de chiffre d'affaires, le résultat net tombe à 3 000 €.",
        "Une baisse de 20 % du chiffre d'affaires le porte à −2 000 €.",
        titre="Sensibilité",
    )])
    assert _constats(en_phrases, BP_ENTIER) == []
    incomplet = Document([_section("16.6", "Charges fixes inchangées.", titre="Sensibilité",
                                   tableaux=(_scenarios(MOINS_10),))])
    assert _constats(incomplet, BP_CHAPITRE) == []

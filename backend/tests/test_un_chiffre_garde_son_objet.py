"""Un chiffre repris d'un chapitre à l'autre compte-t-il toujours la même chose ?

Cliente, 29/10/2026 : « il reste dans la même zone de chiffre, mais il change
un peu la destination » — 10 000 porteurs de projet devenus 10 000 entreprises
créées. Les phrases ci-dessous sont celles des études de production
(`99a142b0`, `a3d28fc0`, `fedb76a1`), à la virgule près.

Le contrôle est en MESURE SEULE : il ne bloque pas, et il ne fait réécrire
aucun chapitre. Les contre-épreuves comptent autant que les cas positifs
(règle 6) : les formes courantes qui RESSEMBLENT au défaut — un dénominateur
nommé de trois façons, un taux, un participe — ne doivent rien signaler.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from generation.controle_final import REPARABLES_PAR_CHAPITRE
from generation.verification.lecture import DocumentLu
from generation.verification.objet_des_chiffres import (
    CONTROLE,
    REPETITION_MAX,
    controler_objet_des_chiffres,
)
from generation.verification.rapport import Gravite


def _document(*par_chapitre: tuple[int, str]) -> DocumentLu:
    return DocumentLu(
        chemin=Path("etude.docx"),
        paragraphes=[texte for _, texte in par_chapitre],
        chapitre_du_paragraphe=[numero for numero, _ in par_chapitre],
    )


def _details(document: DocumentLu) -> list[str]:
    return [a.detail for a in controler_objet_des_chiffres(document)]


# ── Le défaut : même valeur, autre population ───────────────────────────────


def test_la_population_qui_se_resserre_est_un_glissement() -> None:
    """`99a142b0`, chapitres 1 puis 22."""
    anomalies = controler_objet_des_chiffres(_document(
        (1, "Côté TPE, 40 % des TPE-PME utilisent l'IA en 2026 (France Num)."),
        (2, "40 % des TPE-PME utilisent l'IA, mais seules 11 % automatisent."),
        (22, "Opportunité : 40 % des TPE utilisent l'IA, 11 % automatisent."),
    ))
    glissements = [a for a in anomalies if a.detail.startswith("Glissement")]
    assert len(glissements) == 1
    assert glissements[0].chapitre == 22
    assert glissements[0].gravite is Gravite.AVERTISSEMENT
    assert "40 % des TPE utilisent" in glissements[0].extrait


def test_l_exemple_de_la_cliente_porteurs_puis_entreprises() -> None:
    details = _details(_document(
        (2, "On compte 10 000 porteurs de projet dans la région."),
        (5, "Ces 10 000 porteurs constituent le vivier."),
        (9, "Avec 10 000 entreprises créées chaque année, le marché suit."),
    ))
    assert any(
        d.startswith("Objet changé") and "porteurs" in d and "entreprises" in d
        for d in details
    )


@pytest.mark.parametrize(
    ("avant", "apres"),
    [
        # `a3d28fc0` : une visite n'est pas un visiteur.
        ("Le site vise 100 000 visites en année 1.",
         "Part des 100 000 visiteurs qui commandent en année 1."),
        # `fedb76a1`.
        ("La cible compte 2 000 000 femmes de 25 à 45 ans.",
         "Soit 2 000 000 personnes concernées."),
    ],
)
def test_les_glissements_du_corpus_sont_vus(avant: str, apres: str) -> None:
    assert any("Objet changé" in d for d in _details(_document((1, avant), (4, apres))))


# ── Les contre-épreuves : ce qui ressemble au défaut sans l'être ────────────


@pytest.mark.parametrize(
    "phrases",
    [
        # Un dénominateur nommé de trois façons : le même marché.
        ("Le SAM vaut 10 % du marché.", "Soit 10 % du TAM.", "Donc 10 % du total."),
        # Un taux, au singulier : pas une population.
        ("Cohérent avec 40 % d'usage de l'IA.", "Et 40 % d'adoption de l'IA."),
        # Le participe qualifie, l'objet est plus haut.
        ("Nous visons 1 800 articles en année 3.", "Les 1 800 retenus en année 3."),
        # Un effectif repris dans un calcul.
        ("Il faut 2 000 commandes.", "Soit 133 000 visites (2 000 divisé par 1,5 %)."),
        # « Tout » se dit de cent objets.
        ("100 % des documents sont prêts.", "100 % des producteurs sont équipés."),
        # Un montant n'est pas un effectif : « M » n'est pas un objet.
        ("Le marché pèse 1 000 M€.", "Soit 1 000 Md€ au niveau mondial."),
        # Pluriel et accents : la même population.
        ("On recense 3 000 entreprises.", "Les 3 000 Entreprise du panel."),
        # Une devise de `core/numbers.py` n'est pas un objet.
        ("Le loyer atteint 10 000 FCFA.", "Il faut 10 000 clients."),
        # Mots outils et unités.
        ("Les 1 800 qui restent.", "Il reste 1 800 articles."),
        ("Ils étaient 10 000 aujourd'hui.", "On compte 10 000 visiteurs."),
        ("Une surface de 10 000 m2.", "Pour 10 000 habitants du quartier, 10 000 foyers."),
        ("Le taux est de 20 % de TVA.", "20 % des clientes reviennent."),
    ],
)
def test_ce_qui_ressemble_au_defaut_ne_signale_rien(phrases: tuple[str, ...]) -> None:
    document = _document(*((numero, p) for numero, p in enumerate(phrases, start=1)))
    assert _details(document) == []


def test_une_meme_statistique_dans_trop_de_chapitres_est_comptee() -> None:
    phrase = "Selon France Num, 40 % des TPE-PME utilisent l'IA."
    document = _document(*((n, phrase) for n in range(1, REPETITION_MAX + 2)))
    (repetition,) = controler_objet_des_chiffres(document)
    assert repetition.detail.startswith("Répétition")
    assert repetition.gravite is Gravite.INFORMATION

    juste_assez = _document(*((n, phrase) for n in range(1, REPETITION_MAX + 1)))
    assert controler_objet_des_chiffres(juste_assez) == []


@pytest.mark.parametrize(
    ("avant", "apres"),
    [
        ("30 % des e-commerçants vendent à l'export.", "30 % des e-commerces ferment."),
        ("On compte 2 000 micro-entreprises.", "Et 2 000 micro-crèches."),
    ],
)
def test_un_prefixe_commun_n_est_pas_un_glissement(avant: str, apres: str) -> None:
    """Relecture du 29/10/2026 : un mot commun suffisait, et « e- » ou
    « micro- » sortaient en AVERTISSEMENT. Deux objets différents restent une
    simple information ; seule l'INCLUSION (`TPE` dans `TPE-PME`) glisse."""
    anomalies = controler_objet_des_chiffres(_document((1, avant), (2, apres)))
    assert [a.gravite for a in anomalies] == [Gravite.INFORMATION]


def test_un_glissement_entre_deux_formes_minoritaires_est_nomme() -> None:
    """Avec `entreprises` en tête, `TPE` et `TPE-PME` ne se comparent pas qu'à
    elle : leur glissement doit être nommé."""
    anomalies = controler_objet_des_chiffres(_document(
        (1, "40 % des entreprises recrutent."),
        (2, "40 % des entreprises investissent."),
        (3, "40 % des TPE-PME utilisent l'IA."),
        (4, "40 % des TPE utilisent l'IA."),
    ))
    (glissement,) = [a for a in anomalies if a.detail.startswith("Glissement")]
    assert "TPE-PME" in glissement.detail
    assert "« TPE »" in glissement.detail


def test_une_cellule_sur_plusieurs_lignes_ne_fabrique_pas_de_nombre() -> None:
    """python-docx joint les paragraphes d'une cellule par un saut de ligne :
    « 2 000 » et « 500 clients » ne font pas « 2 000 500 clients »."""
    from generation.verification.objet_des_chiffres import occurrences

    document = DocumentLu(
        chemin=Path("etude.docx"),
        cellules=["Année 1\n2 000\n500 clients"],
        chapitre_de_la_cellule=[3],
    )
    assert [o.valeur for o in occurrences(document)] == []


@pytest.mark.parametrize("espace", [" ", " ", " ", " "])
def test_toutes_les_espaces_de_milliers_donnent_la_meme_valeur(espace: str) -> None:
    from generation.verification.objet_des_chiffres import occurrences

    document = _document((1, f"On compte 10{espace}000 porteurs de projet."))
    assert [o.valeur for o in occurrences(document)] == ["10 000"]


# ── Mesure seule : rien ne bloque, rien ne fait payer ───────────────────────


def test_la_verification_execute_le_controle_sans_rendre_le_document_non_livrable() -> None:
    """Le branchement compte autant que la logique : sans lui, rien ne remonte
    dans `mesure/`. Vrai avec socle comme sans socle."""
    from datetime import date

    from generation.socle.schema import Socle
    from generation.verification.services import (
        verifier_document,
        verifier_document_sans_socle,
    )

    document = _document(
        (1, "40 % des TPE-PME utilisent l'IA."),
        (2, "40 % des TPE utilisent l'IA."),
    )
    socle = Socle.model_validate({
        "secteur": "conseil", "zone": {"pays": "France"},
        "date_socle": date(2026, 10, 1).isoformat(),
        "donnees": [{
            "id": "tam", "libelle": "Marché total", "valeur": 1000.0,
            "unite": "MEUR", "annee": 2026, "perimetre": "national",
            "source": "Source de test", "fiabilite": "observee", "derivee_de": [],
        }],
        "segments_clientele": [], "concurrents": [], "tendances": [], "risques": [],
    })
    for rapport in (
        verifier_document(document, socle, deliverable_type="market_study"),
        verifier_document_sans_socle(document),
    ):
        assert CONTROLE in rapport.controles_executes
        assert any(a.controle == CONTROLE for a in rapport.anomalies)
        assert not [a for a in rapport.anomalies if a.controle == CONTROLE
                    and a.gravite is Gravite.BLOQUANTE]


def test_le_controle_ne_bloque_ni_ne_fait_reecrire() -> None:
    """Un avis de ce contrôle ne doit ni arrêter un document ni relancer un
    chapitre payant tant que ses motifs n'ont pas été triés sur le corpus."""
    anomalies = controler_objet_des_chiffres(_document(
        (1, "40 % des TPE-PME utilisent l'IA."),
        (2, "40 % des TPE utilisent l'IA."),
    ))
    assert anomalies
    assert all(a.gravite is not Gravite.BLOQUANTE for a in anomalies)
    assert CONTROLE not in REPARABLES_PAR_CHAPITRE


def test_une_panne_de_la_mesure_n_arrete_pas_la_livraison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Porte qualité du 29/10/2026 : une exception dans ce contrôle de mesure
    interrompait l'assemblage. Elle est dite dans le rapport, rien ne bloque."""
    from generation.verification import services

    def en_panne(_document: DocumentLu) -> list[object]:
        raise ValueError("imprévu")

    monkeypatch.setattr(
        "generation.verification.objet_des_chiffres.controler_objet_des_chiffres", en_panne
    )
    rapport = services.verifier_document_sans_socle(_document((1, "40 % des TPE.")))
    (signal,) = [a for a in rapport.anomalies if a.controle == CONTROLE]
    assert "Mesure impossible (ValueError)" in signal.detail
    assert signal.gravite is Gravite.INFORMATION
    # Le document minimal échoue ailleurs (intégrité) : ce qui compte, c'est
    # que CE contrôle n'ajoute aucun blocage.
    assert CONTROLE not in {a.controle for a in rapport.bloquantes}

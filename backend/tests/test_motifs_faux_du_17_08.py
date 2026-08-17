"""Les motifs faux de l'etude de marche `f0064333` (17/08/2026), et la boucle.

## Le dossier

Vingt-trois chapitres, 7,30 EUR payes, 23 motifs au gate. La cliente attend son
document. Trois de ces motifs sont FAUX, et chacun repose sur une confusion
differente :

- un TITRE en gras compte comme phrase coupee ;
- une colonne de marches EMBOITES (TAM/SAM/SOM) sommee comme un total ;
- des LIBELLES (« TAM », « France », « An1, previsionnel ») pris pour des
  sources.

Et un quatrieme defaut, qui n'est pas un motif mais leur consequence : un motif
faux ne peut pas etre ferme par une regeneration, donc les trois rondes de
correction se consomment sans rien corriger — et chaque ronde se paie.

## Ce que chaque test verrouille

Chaque cas vient avec sa CONTRE-EPREUVE : le controle doit continuer de voir le
defaut qu'il est la pour voir. Un correctif qui se contente de faire taire un
motif ne vaut rien — il aurait suffi de supprimer le controle.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from generation.arithmetique import sources_divergentes, totaux_faux
from generation.qa import _est_de_la_prose, detect_violations

# ── 1. Un titre en gras n'est pas une phrase coupee ──────────────────────────


def test_un_titre_en_gras_ferme_n_est_pas_de_la_prose() -> None:
    """« **CRITERE DE SELECTION BTOB** » — la ligne EXACTE du chapitre 3.

    Echoue sur le code d'avant : `^\\**\\s*[A-ZÀ-Ý]...$` accepte les asterisques
    ouvrantes et pas les fermantes, donc l'expression ancree sur `$` ne matche
    jamais la ligne telle qu'elle est ecrite. Le motif du 09/08/2026 avait ete
    releve APRES le nettoyage de la queue — on avait corrige sur la trace, pas
    sur la ligne.
    """
    assert not _est_de_la_prose("**CRITÈRE DE SÉLECTION BTOB**")
    # Les deux formes deja couvertes le restent.
    assert not _est_de_la_prose("**CRITÈRE DE SÉLECTION BTOB")
    assert not _est_de_la_prose("CRITÈRE DE SÉLECTION BTOB")
    # Un titre en gras de casse ordinaire, connu de `checks_post_rendu` et
    # ignore de `qa` jusqu'ici (regle 5 : deux avis sur la meme ligne).
    assert not _est_de_la_prose("**Lecture de la fiche projet**")


def test_une_vraie_troncature_reste_vue() -> None:
    """Contre-epreuve : le controle doit garder ses dents.

    Une phrase coupee en plein milieu n'est jamais encadree d'asterisques.
    """
    tronque = (
        "## Chapitre\n\n"
        "Le marche du bien-etre progresse depuis 2020, porte par la demande\n"
        "des particuliers et par une offre qui se structure autour de trois"
    )
    motifs = {v.name for v in detect_violations(tronque, "em.03", 3)}
    assert "sentence_cut" in motifs

    # Et un encadre en gras NON ferme reste une troncature : c'est bien la
    # fermeture qui fait le titre, pas l'ouverture.
    assert _est_de_la_prose("**Ce que cela signifie pour la cliente : le panier")


def test_un_titre_en_gras_suivi_d_un_tableau_ne_crie_plus() -> None:
    """Le piege reel : le chapitre finit par un TABLEAU.

    `_last_prose_line` remonte au-dela des lignes de tableau et tombe sur le
    titre en gras, qu'il jugeait alors comme derniere phrase.
    """
    chapitre = (
        "## Chapitre\n\n"
        "Le marche progresse de six pour cent par an depuis 2020.\n\n"
        "**CRITÈRE DE SÉLECTION BTOB**\n\n"
        "| Critere | Poids |\n| --- | --- |\n| Prix | 30 % |"
    )
    motifs = {v.name for v in detect_violations(chapitre, "em.03", 3)}
    assert "sentence_cut" not in motifs


# ── 2. Des marches emboites ne s'additionnent pas ────────────────────────────


def test_tam_sam_som_n_est_pas_un_total() -> None:
    """Le tableau du chapitre 2, avec ses chiffres reels.

    Echoue sur le code d'avant : `\\btotal\\b` trouve le mot dans
    « Marche total (TAM) », qui est la derniere ligne — la condition de
    POSITION posee le matin meme ne suffit donc pas. Le gate annoncait
    « total de 30 000, lignes 2 400,48 » sur un tableau juste.
    """
    tableau = (
        "| Indicateur | Ordre de grandeur |\n"
        "| --- | --- |\n"
        "| Marché adressable (SAM) | 2 400 M€ |\n"
        "| Marché obtenable (SOM An1) | 0,48 M€ |\n"
        "| Marché total (TAM) | 30 000 M€ |\n"
    )
    assert totaux_faux(tableau) == []


@pytest.mark.parametrize(
    "intitule", ["Total", "Total général", "TOTAL", "Cumul", "Ensemble des postes"]
)
def test_un_vrai_total_faux_reste_vu(intitule: str) -> None:
    """Contre-epreuve : une ligne qui ANNONCE une somme est toujours refaite."""
    tableau = (
        "| Poste | Montant |\n"
        "| --- | --- |\n"
        "| Aménagement | 120 000 € |\n"
        "| Matériel | 60 000 € |\n"
        "| Droit au bail | 80 000 € |\n"
        f"| {intitule} | 300 000 € |\n"
    )
    fautes = totaux_faux(tableau)
    assert len(fautes) == 1
    assert fautes[0].annonce == pytest.approx(300000)
    assert fautes[0].somme == pytest.approx(260000)

    # Et le meme tableau, juste, ne dit rien.
    assert totaux_faux(tableau.replace("300 000 €", "260 000 €")) == []


# ── 3. Une parenthese n'est pas une attribution ──────────────────────────────


def test_les_libelles_ne_sont_pas_des_sources() -> None:
    """Les quatre divergences du dossier, toutes fausses.

    Echoue sur le code d'avant : le contenu d'une parenthese etait pris pour
    une origine sans jamais verifier qu'il NOMME quelqu'un. Un sigle de
    dimensionnement, une geographie, une periode, un renvoi de chapitre y
    passaient tous.
    """
    document = [
        "Le marché total est estimé à 30 000 M€ (TAM) pour 2026.",
        "Sur la France, le marché atteint 30 000 M€ (2026, France).",
        "Le TAM ressort à 30 000 M€ (France) selon la segmentation.",
        "Trajectoire : 30 000 M€ (France, +6 %/an) à horizon 2029.",
        "La part obtenable est de 0,48 M€ (SOM An1) la première année.",
        "Soit 0,48 M€ (2026, entreprise) de chiffre d'affaires.",
        "La croissance est de 7 % (monde) par an.",
        "Elle est de 7 % (chapitres 1, 2 et 9) sur la période.",
        "Le SOM An3 vaut 0,96 M€ (An1, prévisionnel).",
    ]
    assert sources_divergentes(document) == []


def test_une_vraie_divergence_de_source_reste_vue() -> None:
    """Contre-epreuve : le defaut que la cliente a demande de traquer.

    « toujours niveau chiffres ET sources » — un montant credite a l'Insee ici
    et a Xerfi la-bas reste un motif, sous les trois formes d'attribution.
    """
    for document in (
        # La parenthese NUE, qui nomme deux organismes. C'est la forme que le
        # depot verrouille depuis le 30/07 : elle doit survivre au correctif.
        [
            "Le marché pèse 16,5 Md€ (Insee, 2025).",
            "Le marché pèse 16,5 Md€ (Fédération de la boulangerie, 2024).",
        ],
        [
            "Le marché français pèse 1,4 M€ (source : Insee, 2025).",
            "Ce même marché pèse 1,4 M€ — source : Xerfi 2026.",
        ],
        [
            "Le segment vaut 2 400 M€ (d'après l'Insee, 2025).",
            "Le segment vaut 2 400 M€ (selon Xerfi, 2026).",
        ],
    ):
        motifs = sources_divergentes(document)
        assert len(motifs) == 1, document
        assert len(motifs[0].sources) == 2

    # La MEME source citee deux fois n'est pas une divergence.
    assert sources_divergentes([
        "Le marché pèse 1,4 M€ (source : Insee, 2025).",
        "Rappel : 1,4 M€ (source : Insee, 2025) au chapitre 3.",
    ]) == []


# ── 4. Une ronde qui ne ferme rien ne se rejoue pas ──────────────────────────


def _job_a_un_chapitre(slug: str):
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import ChapterGeneration, ChapterStatus, GenerationJob
    from orders.models import Order

    offer = Offer.objects.create(
        name="Test", slug=slug, deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email=f"{slug}@test.local")
    order = Order.objects.create(
        systeme_order_id=slug, customer=customer, offer=offer,
    )
    job = GenerationJob.objects.create(
        order=order,
        deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=Decimal("8.00"),
    )
    ChapterGeneration.objects.create(
        job=job, chapter_number=1, chapter_title="Analyse marche",
        prompt_key="em.01.marche_mondial_europeen",
        status=ChapterStatus.DONE, content="Le marche pese 30 000 M€ (TAM).",
    )
    return job


@pytest.mark.django_db
def test_un_motif_qui_ne_bouge_pas_ne_consomme_qu_une_ronde() -> None:
    """Le defaut central : un motif FAUX ne se ferme jamais.

    Echoue sur le code d'avant : la boucle rejoue les trois rondes, donc trois
    regenerations payantes sur un chapitre correct. Elle doit s'arreter des que
    la premiere n'a rien deplace.
    """
    from generation.correction import run_correction_loop
    from generation.gate import GateFailure, GateReport

    immuable = GateReport(
        passed=False,
        failures=(GateFailure(
            check="calcul_faux",
            chapter_number=1,
            detail="Colonne « Ordre de grandeur » : annonce 30 000, lignes 2 400,48.",
        ),),
    )
    appels: list[int] = []

    def _regen(job, chapter, **_kwargs):
        appels.append(chapter.chapter_number)

    with patch("generation.correction._gate.run_delivery_gate", return_value=immuable), \
         patch("generation.runner.regenerate_chapter", side_effect=_regen):
        rapport = run_correction_loop(_job_a_un_chapitre("motif-sourd"), max_rounds=3)

    assert not rapport.passed
    assert len(appels) == 1, (
        f"{len(appels)} regeneration(s) payees pour un motif que la boucle ne "
        "deplace pas — elle doit s'arreter apres la premiere."
    )


@pytest.mark.django_db
def test_une_ronde_qui_ferme_un_motif_laisse_la_boucle_continuer() -> None:
    """Contre-epreuve : on n'a pas simplement ramene la boucle a une ronde.

    Tant que la correction PRODUIT un effet, elle poursuit. « Produire un
    effet » se lit sur le motif lui-meme : le total annonce se rapproche de la
    somme de ses lignes a chaque passe. Un motif qui BOUGE est un motif que la
    regeneration atteint, meme si elle ne l'a pas encore ferme — il merite la
    passe suivante, contrairement a celui qui revient mot pour mot.
    """
    from generation.correction import run_correction_loop
    from generation.gate import GateFailure, GateReport

    def _motif(annonce: str) -> GateReport:
        return GateReport(
            passed=False,
            failures=(GateFailure(
                check="calcul_faux",
                chapter_number=1,
                detail=f"Colonne « Montant » : annonce {annonce}, lignes 260 000.",
            ),),
        )

    rapports = [
        _motif("300 000"), _motif("280 000"), _motif("270 000"),
        GateReport(passed=True),
    ]
    appels: list[int] = []

    def _gate_qui_progresse(_job):
        return rapports.pop(0) if rapports else GateReport(passed=True)

    def _regen(job, chapter, **_kwargs):
        appels.append(chapter.chapter_number)

    with patch("generation.correction._gate.run_delivery_gate", _gate_qui_progresse), \
         patch("generation.runner.regenerate_chapter", side_effect=_regen):
        rapport = run_correction_loop(_job_a_un_chapitre("motif-qui-bouge"), max_rounds=3)

    assert rapport.passed
    assert len(appels) == 3, "La boucle doit continuer tant qu'elle ferme des motifs."

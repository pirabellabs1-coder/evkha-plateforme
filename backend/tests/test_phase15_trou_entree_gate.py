"""Phase 15 — Fermeture du trou d'entree du gate (audit juillet 2026).

Ces tests couvrent le CHEMIN REEL, pas le chemin ideal : un brief dont le
previsionnel arrive en TEXTE LIBRE. C'est precisement ce que la suite
existante ne testait pas — sa fixture fournissait INVESTISSEMENT_TOTAL et
VERTICALES cle en main —, et c'est pour ca que le trou n'a jamais ete vu.

Regle de fond verifiee ici : un check qui n'a rien a comparer est un ECHEC,
jamais un succes.
"""
from __future__ import annotations

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.coherence import seed_locked_facts_from_variables
from generation.gate import run_delivery_gate
from generation.models import ChapterStatus, GenerationJob, JobStatus
from generation.services import bootstrap_generation_job
from intake.financials import (
    enrich_variables_from_free_text,
    extract_financials_from_text,
)
from intake.models import IntakeStatus, IntakeSubmission
from orders.models import Order

# Brief SYNAPSES tel qu'Evangeline l'ecrit reellement : en prose.
BRIEF_TEXTE_LIBRE = (
    "Tiers-lieu hybride SYNAPSES a Annecy. Investissement total 1 250 000 €, "
    "apport personnel 250 000 €, emprunt bancaire 920 000 €, "
    "subventions 80 000 €. "
    "Le taux d'occupation passe de 55 % en An1 a 85 % en An5. "
    "CA previsionnel : 250 272 € en An1, 296 000 € en An2. "
    "Resultat net 44 245 € des la premiere annee. "
    "Verticales : coworking, self-storage (boxes + garages), "
    "hebergement de serveurs, activites sportives douces."
)


def _submission(variables: dict[str, object], ref: str) -> IntakeSubmission:
    offer = Offer.objects.create(
        name="Business Plan",
        slug=f"bp-{ref}",
        deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    customer = Customer.objects.create(email=f"{ref}@example.com")
    order = Order.objects.create(systeme_order_id=ref, customer=customer, offer=offer)
    return IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables=variables,
    )


def _job(submission: IntakeSubmission, content_by_number: dict[int, str]) -> GenerationJob:
    job = bootstrap_generation_job(submission)
    seed_locked_facts_from_variables(job, submission.normalized_variables)
    for chapter in job.chapters.all():
        chapter.content = content_by_number.get(
            chapter.chapter_number,
            "Analyse chiffree du projet sur la zone cible, couvrant le "
            "coworking, le self-storage, l'hebergement de serveurs et les "
            "activites sportives douces.",
        )
        chapter.status = ChapterStatus.DONE
        chapter.save(update_fields=["content", "status"])
    job.status = JobStatus.DONE
    job.save(update_fields=["status"])
    return job


# ── Extraction de l'etat chiffre depuis le texte libre ───────────────────────


def test_extraction_lit_le_previsionnel_ecrit_en_prose() -> None:
    found = extract_financials_from_text(BRIEF_TEXTE_LIBRE)

    assert found["INVESTISSEMENT_TOTAL"] == "1 250 000 €"
    assert found["EMPRUNT"] == "920 000 €"
    assert found["APPORT"] == "250 000 €"
    assert found["SUBVENTIONS"] == "80 000 €"
    assert found["TAUX_OCCUPATION"] == "55 % / 85 %"
    assert "250 272 €" in found["CA_PREVISIONNEL"]
    assert "296 000 €" in found["CA_PREVISIONNEL"]
    assert found["RESULTAT_NET_PREVISIONNEL"] == "44 245 €"
    assert "self-storage" in found["VERTICALES"]


def test_extraction_n_invente_rien_quand_le_brief_est_muet() -> None:
    """Aucune valeur devinee : sans libelle explicite, pas d'extraction."""
    assert extract_financials_from_text("Projet de coworking chaleureux a Annecy.") == {}


def test_les_champs_structures_priment_sur_le_texte_libre() -> None:
    variables: dict[str, object] = {
        "PROJET": BRIEF_TEXTE_LIBRE,
        "EMPRUNT": "900 000 €",  # saisi explicitement dans Tally
    }
    enrich_variables_from_free_text(variables)

    assert variables["EMPRUNT"] == "900 000 €"  # non ecrase
    assert variables["INVESTISSEMENT_TOTAL"] == "1 250 000 €"  # comble depuis le texte


# ── Le trou d'entree : plus de gate vert sur un referentiel vide ─────────────


@pytest.mark.django_db
def test_bp_sans_etat_chiffre_est_bloque() -> None:
    """AVANT : passed=True sur un document truffe d'incoherences. Le trou."""
    submission = _submission(
        {"SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
         "PROJET": "Tiers-lieu hybride SYNAPSES"},
        "bp_sans_etat",
    )
    job = _job(submission, {})

    report = run_delivery_gate(job)

    assert report.passed is False
    checks = {f.check for f in report.failures}
    assert "etat_chiffre_client" in checks


@pytest.mark.django_db
def test_brief_en_texte_libre_alimente_le_gate_et_bloque_les_incoherences() -> None:
    """Le cas SYNAPSES complet, de bout en bout.

    Le previsionnel est en prose ; l'extraction le verrouille ; le gate
    detecte alors l'emprunt fantaisiste et le CA divergent.
    """
    variables: dict[str, object] = {
        "SECTEUR": "coworking",
        "PAYS": "France",
        "ZONE": "Annecy",
        "PROJET": BRIEF_TEXTE_LIBRE,
    }
    enrich_variables_from_free_text(variables)
    submission = _submission(variables, "bp_texte_libre")

    job = _job(
        submission,
        {
            3: "L'emprunt de 300 000 € structure le plan de financement.",
            15: "Le chiffre d'affaires d'annee 2 s'etablit a 318 400 €.",
        },
    )

    report = run_delivery_gate(job)

    assert report.passed is False
    details = " ".join(f.detail for f in report.failures)
    assert "emprunt" in details  # 300 000 € vs 920 000 € du brief
    assert "ca_previsionnel" in details  # 318 400 € vs 296 000 € du brief


@pytest.mark.django_db
def test_ca_previsionnel_desormais_verifie() -> None:
    """Cause 3 : le CA etait verrouille mais n'avait aucun motif dans le gate."""
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 € / 296 000 €",
            "RESULTAT_NET_PREVISIONNEL": "44 245 €",
        },
        "bp_ca",
    )
    job = _job(submission, {15: "Le CA previsionnel d'annee 2 atteint 318 400 €."})

    report = run_delivery_gate(job)

    assert report.passed is False
    assert any(f.check == "coherence_chiffree" for f in report.failures)


@pytest.mark.django_db
def test_erreur_unite_millions_milliers_est_bloquee() -> None:
    """Cause 5 : EBE reseau a 420 M€ pour 8-10 sites de coworking."""
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 €",
            "RESULTAT_NET_PREVISIONNEL": "44 245 €",
        },
        "bp_unite",
    )
    job = _job(
        submission,
        {18: "En annee 7, le reseau degage un EBE de 420 millions d'euros."},
    )

    report = run_delivery_gate(job)

    assert report.passed is False
    assert any(f.check == "ordre_de_grandeur" for f in report.failures)


@pytest.mark.django_db
def test_taille_de_marche_elevee_n_est_pas_bloquee() -> None:
    """Contre-epreuve : un marche a 12 milliards est legitime, pas une erreur."""
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 €",
            "RESULTAT_NET_PREVISIONNEL": "44 245 €",
        },
        "bp_marche",
    )
    job = _job(
        submission,
        {1: "Le marche mondial du coworking pese 12 milliards d'euros en 2025."},
    )

    report = run_delivery_gate(job)

    assert not [f for f in report.failures if f.check == "ordre_de_grandeur"]


@pytest.mark.django_db
def test_label_interne_dans_le_brut_est_detecte_malgre_le_nettoyage() -> None:
    """Cause 4 : le nettoyeur effacait le token, puis le gate cherchait ce qui
    venait d'etre efface. Le check ne pouvait jamais echouer."""
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 €",
            "RESULTAT_NET_PREVISIONNEL": "44 245 €",
        },
        "bp_fuite",
    )
    job = _job(
        submission,
        {15: "Le resultat net inscrit au previsionnel (FAITS_VERROUILLES) "
             "correspond au scenario central."},
    )

    report = run_delivery_gate(job)

    assert report.passed is False
    assert any(f.check == "contamination" for f in report.failures)


@pytest.mark.django_db
def test_chapitre_manquant_est_detecte() -> None:
    """Cas du brief : « le chapitre 18 est tronque page 88, puis le doc bascule
    brutalement sur les References ». `render_client_document` ne retient que
    les chapitres DONE : un chapitre absent disparaissait du livrable sans que
    les autres checks, qui ne portent que sur les chapitres presents, le voient.
    """
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 €",
            "RESULTAT_NET_PREVISIONNEL": "44 245 €",
        },
        "bp_manquant",
    )
    job = _job(submission, {})

    # Un chapitre n'a jamais abouti : il sort du document rendu.
    orphan = job.chapters.order_by("-chapter_number").first()
    assert orphan is not None
    orphan.status = ChapterStatus.FAILED
    orphan.save(update_fields=["status"])

    report = run_delivery_gate(job)

    assert report.passed is False
    assert any(f.check == "completude_chapitres" for f in report.failures)


@pytest.mark.django_db
def test_verticale_avec_parenthese_ne_produit_pas_de_faux_positif() -> None:
    """« self-storage (boxes + garages) » ne se retrouve jamais litteralement."""
    variables: dict[str, object] = {
        "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
        "PROJET": "SYNAPSES",
        "INVESTISSEMENT_TOTAL": "1 250 000 €",
        "CA_PREVISIONNEL": "250 272 €",
        "RESULTAT_NET_PREVISIONNEL": "44 245 €",
        "VERTICALES": "coworking / self-storage (boxes + garages)",
    }
    submission = _submission(variables, "bp_vert")
    job = _job(
        submission,
        {2: "L'offre couvre le coworking et le self-storage sur la zone."},
    )

    report = run_delivery_gate(job)

    assert not [f for f in report.failures if f.check == "verticales"]


@pytest.mark.django_db
def test_verticale_reellement_absente_est_toujours_bloquee() -> None:
    """Contre-epreuve : le remplacement silencieux reste interdit."""
    variables: dict[str, object] = {
        "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
        "PROJET": "SYNAPSES",
        "INVESTISSEMENT_TOTAL": "1 250 000 €",
        "CA_PREVISIONNEL": "250 272 €",
        "RESULTAT_NET_PREVISIONNEL": "44 245 €",
        "VERTICALES": "coworking / hebergement de serveurs",
    }
    submission = _submission(variables, "bp_vert_ko")
    job = _job(submission, {})  # contenu par defaut : parle d'hebergement

    # Contenu qui efface la verticale « hebergement de serveurs »
    for chapter in job.chapters.all():
        chapter.content = "L'offre se concentre exclusivement sur le coworking."
        chapter.save(update_fields=["content"])

    report = run_delivery_gate(job)

    assert report.passed is False
    assert any(f.check == "verticales" for f in report.failures)

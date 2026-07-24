"""Phase 24 — Les 4 reponses d'Evangeline du 17/07/2026, traduites en verrous.

Q1 : les chiffres marche mondial / continental / national sont verrouilles
     apres les chapitres 1 et 2 EM, chacun a sa propre cle CoherenceFact.
Q2 : la formule « donnee non disponible » est INTERDITE dans le prompt.
     A la place, hypothese construite par croisement, presentee comme telle,
     documentee dans l'encadre methodologie du chapitre Sources.
Q3 : l'ordre de tri des concurrents (similitude offre, cible, taille,
     proximite, anciennete) est injecte dans la consigne EC, importe depuis
     la constante `CRITERES_TRI_CONCURRENTS` (regle 5, source unique).
Q4 : le prompt STR reprend la POSTURE, les 5 OBJECTIFS et l'INTERPRETATION DU
     BRIEF IMPARFAIT du document methodologique « Systeme EVKHA — Strategies
     Business Automatisees » que la cliente a renvoye.

Chaque test cherche une chaine ou un comportement qui N'EXISTAIT PAS avant ce
commit (regle 6 du CLAUDE.md).
"""
from __future__ import annotations

import pytest

from catalog.models import DeliverableType
from generation.checks_evangeline import CRITERES_TRI_CONCURRENTS
from generation.prompts import build_system_prompt

# ── Q1 : les trois niveaux du marche sont verrouilles separement ────────────


@pytest.mark.django_db
def test_les_chiffres_du_marche_sont_verrouilles_par_niveau() -> None:
    """Elle a dit : « on a des chiffres mondiaux, continentaux, nationaux et on
    les garde pour continuer l'etude sur la meme lignee. » Chaque niveau a
    donc sa propre cle CoherenceFact.

    Avant : une seule cle `taille_marche`, le premier niveau vu ecrasait les
    autres. Le chapitre 3 pouvait citer un chiffre national verrouille par
    erreur en pensant que c'etait le mondial.
    """
    from catalog.models import Offer
    from customers.models import Customer
    from generation.coherence import extract_and_lock_chiffres_cles
    from generation.services import bootstrap_generation_job
    from intake.models import IntakeStatus, IntakeSubmission
    from orders.models import Order

    offer = Offer.objects.create(
        name="EM test", slug="em-niveaux", deliverable_type=DeliverableType.MARKET_STUDY
    )
    customer = Customer.objects.create(email="niveaux@example.com")
    order = Order.objects.create(systeme_order_id="ord_niv", customer=customer, offer=offer)
    submission = IntakeSubmission.objects.create(
        order=order, status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "coworking", "PAYS": "France",
                              "ZONE": "Beziers", "PROJET": "coworking"},
    )
    job = bootstrap_generation_job(submission)

    corps = (
        "Le marche mondial du coworking pese 30 milliards en 2025. "
        "Le marche europeen represente 8 milliards. "
        "Le marche national francais atteint 900 millions."
    )
    extract_and_lock_chiffres_cles(job, chapter_number=1, content=corps)

    cles = set(
        job.coherence_facts.filter(is_locked=True).values_list("key", flat=True)
    )
    assert "taille_marche_mondial" in cles
    assert "taille_marche_continental" in cles
    assert "taille_marche_national" in cles


@pytest.mark.django_db
def test_le_tcac_est_verrouille_par_niveau() -> None:
    """Meme logique que la taille du marche : chaque niveau a son TCAC propre."""
    from catalog.models import Offer
    from customers.models import Customer
    from generation.coherence import extract_and_lock_chiffres_cles
    from generation.services import bootstrap_generation_job
    from intake.models import IntakeStatus, IntakeSubmission
    from orders.models import Order

    offer = Offer.objects.create(
        name="EM test 2", slug="em-tcac", deliverable_type=DeliverableType.MARKET_STUDY
    )
    customer = Customer.objects.create(email="tcac@example.com")
    order = Order.objects.create(systeme_order_id="ord_tcac", customer=customer, offer=offer)
    submission = IntakeSubmission.objects.create(
        order=order, status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "coworking", "PAYS": "France",
                              "ZONE": "Beziers", "PROJET": "coworking"},
    )
    job = bootstrap_generation_job(submission)

    extract_and_lock_chiffres_cles(job, chapter_number=1, content=(
        "TCAC mondial de 12,5 % sur la periode. "
        "TCAC europeen de 8,3 %. "
        "TCAC national francais de 6,1 %."
    ))
    cles = set(
        job.coherence_facts.filter(is_locked=True).values_list("key", flat=True)
    )
    assert "tcac_mondial" in cles
    assert "tcac_continental" in cles
    assert "tcac_national" in cles


# ── Q2 : la formule « donnee non disponible » est bannie ────────────────────


def test_le_prompt_interdit_la_formule_donnee_non_disponible() -> None:
    """Manuel Evangeline §3 : « Ne jamais afficher 'donnees non disponibles'
    dans l'etude client. » Le charter mentionne le pluriel avec guillemets ;
    accepter les deux formes pour ne pas dependre du wording exact."""
    prompt = build_system_prompt(DeliverableType.MARKET_STUDY, country="France")
    lower = prompt.lower()

    assert (
        "donnee non disponible" in lower
        or "donnees non disponibles" in lower
    )
    # L'ancienne mention "INTERDICTION VERBATIM" en majuscules a ete retiree
    # avec le manuel Evangeline (24/07/2026) : le nouveau charter enonce
    # directement "Ne jamais afficher..." sans l'auto-designer comme "verbatim".


def test_le_prompt_impose_la_documentation_dans_la_methodologie() -> None:
    """Manuel §3 : « construire une estimation prudente et expliquer
    clairement la methode. » Les sources completes vont dans le chapitre 21.
    L'ancienne assertion sur 'hypothese' portait sur une formulation retiree ;
    on verifie desormais la presence de la notion de methode/estimation."""
    prompt = build_system_prompt(DeliverableType.MARKET_STUDY, country="France")
    lower = prompt.lower()

    assert "methode" in lower
    assert "estimation" in lower
    assert "chapitre 21" in lower


# ── Q3 : l'ordre de tri des concurrents est injecte ─────────────────────────


def test_le_prompt_ec_injecte_l_ordre_de_tri_des_concurrents() -> None:
    """L'ordre EXACT donne par la cliente : similarite / cible / taille /
    proximite / anciennete."""
    prompt = build_system_prompt(DeliverableType.COMPETITOR_STUDY)

    # Les 5 criteres sont injectes dans l'ordre, avec leur numero.
    positions = [prompt.find(c) for c in CRITERES_TRI_CONCURRENTS]
    assert all(p >= 0 for p in positions), (
        "un critere manque dans le prompt : " + repr(positions)
    )
    assert positions == sorted(positions), (
        "les criteres ne sont pas dans l'ordre annonce"
    )


def test_le_prompt_ec_reprend_les_5_criteres_ni_plus_ni_moins() -> None:
    """Contre-epreuve : ni ajout, ni suppression par rapport a la liste
    ordonnee par la cliente (regle 5 : source unique)."""
    prompt = build_system_prompt(DeliverableType.COMPETITOR_STUDY)

    # Le prompt cite un critere par ligne numerotee « N. Libelle ».
    for i, critere in enumerate(CRITERES_TRI_CONCURRENTS, start=1):
        assert f"{i}. {critere}" in prompt


# ── Q4 : le prompt STR reprend la posture et l'interpretation du brief ──────


def test_le_prompt_strategie_pose_la_posture_cabinet_de_conseil() -> None:
    """Document methodologique : « posture cabinet de conseil, DAF, direction
    generale »."""
    prompt = build_system_prompt(DeliverableType.BUSINESS_STRATEGY)

    assert "cabinet de conseil" in prompt.lower()
    assert "daf" in prompt.lower()


def test_le_prompt_strategie_reprend_les_5_objectifs_transversaux() -> None:
    """Document methodologique : Clarification, Structuration, Rentabilite,
    Pilotage, Developpement. Ces cinq axes doivent apparaitre."""
    prompt = build_system_prompt(DeliverableType.BUSINESS_STRATEGY)

    for objectif in ("clarification", "structuration", "rentabilite",
                     "pilotage", "developpement"):
        assert objectif in prompt.lower(), f"{objectif} absent"


def test_le_prompt_strategie_ancre_l_interpretation_du_brief_imparfait() -> None:
    """Document methodologique, section INTERPRETATION : « le desordre initial
    du dirigeant est normal ». Le systeme doit reconstruire, jamais demander
    un brief plus complet."""
    prompt = build_system_prompt(DeliverableType.BUSINESS_STRATEGY)

    assert "desordre" in prompt.lower()
    assert "reconstitu" in prompt.lower() or "reconstruire" in prompt.lower()


def test_le_prompt_strategie_interdit_les_conseils_generiques_verbatim() -> None:
    """Verbatim du document methodologique : « il faut poster plus sur
    Instagram », « le marche est tres porteur »..."""
    prompt = build_system_prompt(DeliverableType.BUSINESS_STRATEGY)

    assert "instagram" in prompt.lower()
    assert "porteur" in prompt.lower()


def test_le_prompt_strategie_impose_les_paragraphes_developpes() -> None:
    """Le PDF EVKHA : « paragraphes developpes, pas d'accumulation de listes »."""
    prompt = build_system_prompt(DeliverableType.BUSINESS_STRATEGY)

    assert "paragraphes developpes" in prompt.lower()

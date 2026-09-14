"""Une réponse libre du client ne prête pas tous ses montants à un seul fait.

## Le défaut mesuré

Corpus du 14/09/2026, business plans `256e63d8`, `1fdc457b`, `9f8f144a` : à la
question « apport », la cliente a répondu par un paragraphe — financements
recherchés, charges fixes, rémunération des trois années, une enveloppe de
sécurité, et « 1600e ont déjà été investis dans la plateforme ».

Le contrôle de cohérence prenait TOUS ces montants pour l'apport. Le document
écrivait « apport personnel de 1 600 € », exactement ce qu'elle avait dit, et
recevait : « le brief client dit » suivi du paragraphe entier. Motif faux
(règle 2), routé vers une réécriture payée qui ne pouvait pas le fermer.
"""
from __future__ import annotations

from typing import Any

import pytest

from generation.gate import _check_numeric_coherence
from generation.models import FactKind, FactProvenance
from generation.rendering import RenderedSection

#: La forme de la réponse réelle, recomposée sans les données de la cliente.
REPONSE_LIBRE = (
    "Financements recherchés : prioritairement subventions et aides à la "
    "création.\nCharges fixes actuelles :\nenviron 200 €/mois de logiciels ;\n"
    "environ 200 €/mois d'expert-comptable ;\nsoit environ 400 €/mois de charges "
    "fixes courantes.\nRémunération envisagée :\nAnnée 1 : 1 000 €/mois "
    "Année 2 : 1 300 €/mois Année 3 : 1 800 €/mois\nUne enveloppe de 8 000 € "
    "est prévue pour sécuriser les six premiers mois."
)


def _job(db: Any, apport: str) -> Any:
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import GenerationJob
    from orders.models import Order

    offer = Offer.objects.create(
        name="BP", slug="bp", deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    customer = Customer.objects.create(email="apport@example.com")
    order = Order.objects.create(systeme_order_id="o_apport", customer=customer, offer=offer)
    job = GenerationJob.objects.create(
        order=order, deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    job.coherence_facts.create(
        kind=FactKind.ASSUMPTION, key="apport", value=apport,
        is_locked=True, provenance=FactProvenance.CLIENT,
    )
    return job


def _motifs(job: Any, texte: str) -> list[tuple[str, int | None]]:
    section = RenderedSection(number=15, title="Financement", kind="chapter", body=texte)
    return [(f.check, f.chapter_number) for f in _check_numeric_coherence(job, (section,))]


@pytest.mark.django_db
def test_le_montant_que_la_cliente_a_ecrit_n_est_pas_une_contradiction(db: Any) -> None:
    """`256e63d8` : « 1600e ont déjà été investis » — le document dit 1 600 €."""
    job = _job(db, REPONSE_LIBRE + " 1600e ont déjà été investis dans la plateforme.")
    assert _motifs(job, "L'apport personnel de 1 600 € finance le prototype.") == []


@pytest.mark.django_db
def test_une_faute_de_frappe_ne_fabrique_pas_de_reference(db: Any) -> None:
    """`1fdc457b` : « la société a déjà invetsi 1600e ». Le mot du fait manque.

    Rien ne dit que ces 1 600 € sont l'apport : on ne l'invente pas, on le dit
    (relecture du 14/09/2026, I4) — une fois, sans réécriture payée.
    """
    job = _job(db, REPONSE_LIBRE + " La société a déjà invetsi 1600e dans le logiciel.")
    assert _motifs(job, "L'apport personnel de 1 600 € finance le prototype.") == [
        ("reference_client_illisible", None),
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("montant", ["8 000", "1 800"])
def test_un_montant_de_la_reponse_n_est_pas_pour_autant_l_apport(db: Any, montant: str) -> None:
    """I4 : 8 000 € est l'enveloppe, 1 800 € la rémunération de l'année 3."""
    job = _job(db, REPONSE_LIBRE)
    assert _motifs(job, f"L'apport personnel de {montant} € finance le prototype.") == [
        ("reference_client_illisible", None),
    ]


@pytest.mark.django_db
def test_j_apporte_est_une_phrase_d_apport(db: Any) -> None:
    job = _job(db, "J'apporte 10 000 € de mes économies. Le prêt bancaire sera de 40 000 €.")
    assert _motifs(job, "L'apport personnel de 40 000 € finance le projet.") == [
        ("coherence_chiffree", 15),
    ]
    assert _motifs(job, "L'apport personnel de 10 000 € finance le projet.") == []


@pytest.mark.django_db
def test_une_reponse_qui_nie_l_apport_n_en_donne_aucun(db: Any) -> None:
    job = _job(db, "Je n'ai pas d'apport personnel. Le prêt sera de 30 000 € sur 5 ans.")
    assert _motifs(job, "L'apport de 30 000 € finance le projet.") == [
        ("reference_client_illisible", None),
    ]


@pytest.mark.django_db
def test_investis_dans_une_phrase_de_pret_ne_porte_pas_l_apport(db: Any) -> None:
    """I5 : le document dit exactement ce que le client a écrit, il n'est pas accusé."""
    job = _job(db, "Le matériel, soit 20 000 € investis, sera financé par un prêt. "
                   "J'apporte 5 000 € personnellement.")
    assert _motifs(job, "L'apport personnel de 5 000 € complète le financement.") == []


@pytest.mark.django_db
def test_sans_apport_dans_la_reponse_on_dit_qu_il_manque_sans_reecrire(db: Any) -> None:
    """`9f8f144a` : aucun apport dans la réponse. Rien n'est CONTREDIT.

    Le motif dit ce qui manque, une seule fois, et sans chapitre : aucune
    réécriture ne fera apparaître un chiffre que le client n'a pas donné.
    """
    job = _job(db, REPONSE_LIBRE)
    motifs = _motifs(
        job,
        "L'apport personnel de 1 600 € finance le prototype. Un apport de 1 600 € "
        "est retenu.",
    )
    assert motifs == [("reference_client_illisible", None)]


@pytest.mark.django_db
def test_la_phrase_qui_parle_de_l_apport_reste_jugee_en_tolerance_zero(db: Any) -> None:
    """CONTRE-ÉPREUVE : la réponse libre donne l'apport, le document en écrit un autre."""
    job = _job(db, REPONSE_LIBRE + " Mon apport personnel sera de 5 000 €.")
    assert _motifs(job, "L'apport personnel de 8 000 € finance le prototype.") == [
        ("coherence_chiffree", 15),
    ], "8 000 € est dans la réponse, mais c'est l'enveloppe, pas l'apport"


@pytest.mark.django_db
def test_une_reponse_simple_reste_jugee_comme_avant(db: Any) -> None:
    """CONTRE-ÉPREUVE : « 25 000 € » n'est pas une réponse libre."""
    job = _job(db, "25 000 €")
    assert _motifs(job, "L'apport personnel de 20 000 € finance le prototype.") == [
        ("coherence_chiffree", 15),
    ]


@pytest.mark.django_db
def test_une_longue_reponse_du_client_est_verrouillee_entiere(db: Any) -> None:
    """La cause racine de `256e63d8` : le fait était coupé à 500 signes.

    « 1600e ont déjà été investis » tenait en fin de réponse ; le gate
    comparait le document à une référence amputée de sa seule phrase utile.
    """
    from generation.coherence import seed_locked_facts_from_variables

    job = _job(db, "provisoire")
    job.coherence_facts.all().delete()
    longue = REPONSE_LIBRE * 3 + " 1600e ont déjà été investis dans la plateforme."
    assert len(longue) > 500
    seed_locked_facts_from_variables(job, {"APPORT": longue})

    assert job.coherence_facts.get(key="apport").value.endswith("investis dans la plateforme.")


# ── L'apport écrit AILLEURS dans le brief (corpus du 14/09/2026, `9f8f144a`) ─


def _brief(job: Any, **variables: str) -> None:
    from intake.models import IntakeSubmission

    IntakeSubmission.objects.create(order=job.order, normalized_variables=variables)


@pytest.mark.django_db
def test_l_apport_ecrit_dans_un_autre_champ_du_brief_est_la_reference(db: Any) -> None:
    """« Apport personnel : à définir » d'un côté ; « 1600e investi dans le dev du
    MVP SaaS déjà par Evangeline » dans le modèle de revenus."""
    job = _job(db, "Apport personnel : à définir. " + REPONSE_LIBRE)
    _brief(job, MODELE_REVENUS=(
        "Abonnement à 49,95 € par mois. 1600e investi dans le dev du mvp saas deja "
        "par evangeline. les 8000e ne sont pas un apport mais un besoin aussi."
    ))
    assert _motifs(job, "L'apport personnel de 1 600 € finance le prototype.") == []


@pytest.mark.django_db
def test_un_montant_que_le_brief_nie_etre_un_apport_n_en_est_pas_la_reference(db: Any) -> None:
    """CONTRE-ÉPREUVE : « les 8000e ne sont pas un apport » ne fait pas de 8 000 € l'apport."""
    job = _job(db, "Apport personnel : à définir. " + REPONSE_LIBRE)
    _brief(job, MODELE_REVENUS=(
        "Abonnement à 49,95 € par mois. 1600e investi dans le dev du mvp saas deja "
        "par evangeline. les 8000e ne sont pas un apport mais un besoin aussi."
    ))
    assert _motifs(job, "L'apport personnel de 8 000 € finance le prototype.") == [
        ("coherence_chiffree", 15),
    ]


@pytest.mark.django_db
def test_la_reponse_entiere_de_la_soumission_supplee_un_fait_tronque(db: Any) -> None:
    """`256e63d8` : le fait ancien est coupé avant « 1600e ont déjà été investis »."""
    job = _job(db, REPONSE_LIBRE)
    _brief(job, APPORT=REPONSE_LIBRE + " 1600e ont déjà été investis dans la plateforme.")
    assert _motifs(job, "L'apport de 1 600 € finance le prototype.") == []


@pytest.mark.django_db
def test_une_faute_de_frappe_dans_la_reponse_entiere_ne_fabrique_toujours_rien(db: Any) -> None:
    """CONTRE-ÉPREUVE (`1fdc457b`) : « invetsi » ne dit pas que ces 1 600 € sont l'apport."""
    job = _job(db, REPONSE_LIBRE)
    _brief(job, APPORT=REPONSE_LIBRE + " la société a déjà invetsi 1600e dans le saas.")
    assert _motifs(job, "L'apport de 1 600 € finance le prototype.") == [
        ("reference_client_illisible", None),
    ]

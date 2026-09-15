"""Une plage que le client a écrite n'est pas une hésitation du rédacteur.

## Le défaut mesuré

Corpus du 15/09/2026. La cliente écrit « le modèle B2B fonctionne par
abonnement et crédits, actuellement de 129 € à 429 €/mois, selon le nombre de
livrables inclus » (`5c5e91b9`), ou « budget de consultation 100-300 € »
(`f8a29b66`). Le document qui reprend sa plage recevait `fourchette_interdite`,
routé vers une réécriture payée qui devait inventer une valeur unique (règle 2).

## Ce qui reste une fourchette

- trois prix DISTINCTS du brief résumés par le rédacteur (« 60 à 75 €/h ») —
  décision du 14/09/2026, la consigne exige « UN prix par variante » ;
- deux montants du client simplement voisins (« un panier à 15 €, un forfait à
  2 500 € ») : la première version de ce correctif les exemptait (relecture du
  15/09) ;
- une forme que le détecteur ne tient pas pour une plage dans le livrable
  (« Mois 1 - 1 500 € ») : elle n'en est pas une chez le client non plus.
"""
from __future__ import annotations

from typing import Any

import pytest

from generation.gate import _check_fourchettes
from generation.rendering import RenderedSection

GRILLE = (
    "La deuxième source de revenus correspond aux interventions ponctuelles :\n\n"
    "60 € TTC par heure pour une intervention à distance ;\n"
    "65 € TTC par heure pour une intervention en atelier ;\n"
    "75 € TTC par heure pour une intervention à domicile."
)


def _job(db: Any, **variables: str) -> Any:
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import GenerationJob
    from intake.models import IntakeSubmission
    from orders.models import Order

    offer = Offer.objects.create(
        name="STR", slug="str", deliverable_type=DeliverableType.BUSINESS_STRATEGY,
    )
    customer = Customer.objects.create(email="plage@example.com")
    order = Order.objects.create(systeme_order_id="o_plage", customer=customer, offer=offer)
    IntakeSubmission.objects.create(order=order, normalized_variables=variables)
    return GenerationJob.objects.create(
        order=order, deliverable_type=DeliverableType.BUSINESS_STRATEGY,
    )


def _plages(job: Any, texte: str) -> list[str]:
    section = RenderedSection(number=2, title="Offre", kind="chapter", body=texte)
    return [f.detail for f in _check_fourchettes(job, (section,))]


@pytest.mark.django_db
@pytest.mark.parametrize(("brief", "texte"), [
    # `5c5e91b9` : l'unité répétée après chaque borne.
    (
        "Le modèle B2B fonctionne par abonnement et crédits, actuellement de "
        "129 € à 429 €/mois, selon le nombre de livrables inclus.",
        "Les abonnements B2B vont de 129 à 429 € par mois.",
    ),
    # `f8a29b66` : un budget de cible, en trait d'union.
    (
        "en priorité les dirigeants de PME (besoin juridique récurrent, budget "
        "de consultation 100-300 €)",
        "Un dirigeant de PME consacre 100 à 300 euros à une consultation.",
    ),
    (
        "Taux de conversion observé sur nos salons : entre 30 % et 40 %.",
        "La conversion en salon, 30-40 %, reste la meilleure du réseau.",
    ),
    # Séparateur de milliers en espace fine insécable.
    (
        "Loyer commercial négocié de 1 200 € à 1 600 € selon l'emplacement.",
        "Le loyer ira de 1 200 à 1 600 € selon l'emplacement retenu.",
    ),
])
def test_la_plage_que_le_client_a_ecrite_n_est_pas_une_fourchette(
    db: Any, brief: str, texte: str,
) -> None:
    job = _job(db, MODELE_REVENUS=brief)
    assert _plages(job, texte) == []


@pytest.mark.django_db
def test_la_plage_d_un_document_depose_par_le_client_n_est_pas_une_fourchette(db: Any) -> None:
    from generation.models import DocumentClientLu

    job = _job(db, OFFRE="Voir la grille jointe.")
    DocumentClientLu.objects.create(
        job=job, nom="grille.docx", statut="lu",
        texte="Formules d'accompagnement : de 129 € à 429 € par mois.",
    )
    assert _plages(job, "Les formules vont de 129 à 429 € par mois.") == []


@pytest.mark.django_db
def test_une_grille_de_prix_distincts_resumee_reste_une_fourchette(db: Any) -> None:
    """CONTRE-ÉPREUVE, décision du 14/09/2026 : la plage efface les trois prix."""
    job = _job(db, OFFRE=GRILLE)
    assert len(_plages(job, "| Interventions ponctuelles (60 à 75 €/h) | Porte d'entrée |")) == 1


@pytest.mark.django_db
@pytest.mark.parametrize(("brief", "texte"), [
    # Deux montants voisins, sans plage : `a678b10a` ch. 13.
    (
        "Le panier moyen est de 15 € et le forfait d'installation de 2 500 €.",
        "un abonné acquis coûterait de 15 à 2 500 euros selon le canal",
    ),
    (
        "Répartition des charges : loyer 20 %, salaires 35 %, marketing 10 %, divers 5 %.",
        "une croissance de 5 à 10 % par an",
    ),
    # Une énumération n'est pas une plage.
    ("Les abonnements à 12 € et 29 € par mois.", "Trois paliers de 12 à 29 € par mois."),
    # Une liste de prix au tiret non plus (`db0d9508`, mesure du 15/09/2026).
    ("Abonnements : 12 € - 19 € - 29 € par mois.", "Deux paliers de 19 à 29 € par mois."),
    # Une étiquette suivie d'un montant n'est pas une plage.
    ("Trésorerie : Mois 1 - 1 500 €.", "un besoin de 1 à 1 500 € selon le mois"),
])
def test_ce_que_le_client_n_a_pas_ecrit_en_plage_reste_une_fourchette(
    db: Any, brief: str, texte: str,
) -> None:
    """CONTRE-ÉPREUVE : relecture du 15/09/2026."""
    job = _job(db, MODELE_REVENUS=brief)
    assert len(_plages(job, texte)) == 1


@pytest.mark.django_db
def test_une_plage_du_client_ne_couvre_pas_une_autre_unite(db: Any) -> None:
    """CONTRE-ÉPREUVE : « 3 à 5 € » chez le client ne couvre pas « 3 à 5 M€ »."""
    job = _job(db, OFFRE="Option de 3 € à 5 € par mois.")
    assert len(_plages(job, "un chiffre d'affaires de 3 à 5 M€")) == 1


def test_la_mesure_montre_le_passage_de_la_plage() -> None:
    """Sans le passage, une plage du client et une plage inventée se ressemblent."""
    from generation.mesure import _phrase_de_la_plage

    corps = "Début du chapitre. | Interventions ponctuelles (60 à 75 €/h) | Porte d'entrée |"
    detail = "Fourchette detectee : « 60 à 75 € ». Le document doit citer un chiffre unique."
    assert "Interventions ponctuelles (60 à 75 €/h)" in _phrase_de_la_plage(corps, detail)


def test_la_mesure_montre_chaque_occurrence_de_la_plage() -> None:
    """Deux motifs identiques d'un même chapitre : la première occurrence, sourcée
    et admise, masquait la seconde, refusée (mesure de 53807ff sur `7567ca2f`)."""
    from generation.mesure import _phrase_de_la_plage

    corps = (
        "Tableau : 20 à 50 € (Cabinet Osmose, 2026). "
        "Plus loin, sans source : 20 à 50 € par mois."
    )
    detail = "Fourchette detectee : « 20 à 50 € ». Le document doit citer un chiffre unique."
    assert "Osmose" in _phrase_de_la_plage(corps, detail, 0)
    assert "sans source" in _phrase_de_la_plage(corps, detail, 1)
    assert _phrase_de_la_plage(corps, detail, 2) == ""

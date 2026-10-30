"""La note du relecteur arrive ENTIÈRE au rédacteur qui doit l'appliquer.

Mesuré sur l'étude IA `bc694571` (30/10/2026), deuxième génération de test
après le correctif de la relecture finale : 16 chapitres réécrits, deux blocs
levés, et huit blocs encore bloqués. Le relecteur l'écrivait à chaque passe :
« défaut de la note précédente encore présent ».

Il avait raison, et la cause était dans la transmission : ses notes font
1 300 à 3 000 caractères, le gate les coupait à 400 — et ce motif coupé est la
consigne que la relecture finale donne au rédacteur. Le bloc G citait les
chapitres 12, 13 et 14 ; seul le 14 tenait dans les 400 premiers caractères.
L'incident lui-même coupait la note à 2 000 caractères.

Ces tests échouent sur le code d'avant.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from generation.checks_blocs import BLOCS_PAR_IDENTIFIANT, INCIDENT_TYPE_CHECK_BLOC
from generation.gate import _check_blocs_evangeline
from generation.meta_discours import consigne_de_correction

pytestmark = pytest.mark.django_db

#: La forme réelle d'une note du bloc G : un point par chapitre, le dernier
#: bien au-delà de 400 caractères.
_NOTE_BLOC_G = (
    "Ch. 14, tableau 14.1 : ajouter un critère « Règles à respecter », note 4, "
    "et justifier la note en une phrase. " + "Détail du point. " * 30
    + "Ch. 12 : aligner la probabilité « possible sur la durée du projet » sur "
    "l'échelle posée en 12.1. " + "Détail du point. " * 130
    + "Ch. 13 : POINT FINAL — remplacer « le retarde » par « retarde le "
    "chiffre d'affaires visé d'au moins six mois »."
)


def _job() -> Any:
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import GenerationJob
    from orders.models import Order

    offre = Offer.objects.create(
        name="EM", slug="em-note-entiere", deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="note-entiere@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id="cmd-note-entiere", customer=client, offer=offre
    )
    return GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=Decimal("18"),
    )


def _incident(job: Any, note: str) -> None:
    from monitoring.models import IncidentSeverity, OperationalIncident

    OperationalIncident.objects.create(
        title="CHECK 7 (bloc G)", severity=IncidentSeverity.MEDIUM, job=job,
        order=job.order,
        details={
            "type": INCIDENT_TYPE_CHECK_BLOC, "bloc": "G", "check": "7",
            "intitule": "Risques et viabilite", "chapitres": [12, 13, 14],
            "note_corrective": note,
        },
    )


def test_le_motif_du_gate_porte_la_note_entiere() -> None:
    """LE défaut : coupée à 400 caractères, la consigne du chapitre 13 disparaissait."""
    assert len(_NOTE_BLOC_G) > 2000
    job = _job()
    _incident(job, _NOTE_BLOC_G)

    echecs = _check_blocs_evangeline(job)

    assert {e.chapter_number for e in echecs} == {12, 13, 14}
    assert all("POINT FINAL" in e.detail for e in echecs)


def test_le_redacteur_du_chapitre_13_recoit_le_point_qui_le_concerne() -> None:
    """Ce que la relecture finale transmet : la consigne bâtie sur le motif."""
    job = _job()
    _incident(job, _NOTE_BLOC_G)
    motif_13 = next(e for e in _check_blocs_evangeline(job) if e.chapter_number == 13)

    consigne = consigne_de_correction([motif_13.detail])

    assert "retarde le chiffre d'affaires visé d'au moins six mois" in consigne


def test_l_incident_garde_la_note_entiere() -> None:
    """La seconde coupe, à 2 000 caractères, à l'ouverture de l'incident."""
    from generation.runner import _log_incident_check
    from monitoring.models import OperationalIncident

    job = _job()

    _log_incident_check(
        job, BLOCS_PAR_IDENTIFIANT["G"], _NOTE_BLOC_G, titre="CHECK 7 echoue apres retry",
    )

    incident = OperationalIncident.objects.get(job=job)
    assert incident.details["note_corrective"] == _NOTE_BLOC_G


def test_une_note_courte_reste_identique() -> None:
    """CONTRE-ÉPREUVE : rien n'est ajouté ni reformulé."""
    job = _job()
    _incident(job, "Ch. 12 : une seule correction.")

    (premier, *_) = _check_blocs_evangeline(job)

    assert "Note du relecteur : Ch. 12 : une seule correction. " in premier.detail

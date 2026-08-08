"""Le business plan et la strategie doivent obtenir un document.

Mesure du 05/08/2026, repetition a blanc GRATUITE du pipeline de production sur
un brief reel (`run_generation_job_task`, doublure IA, socle actif comme en
production) :

    [3/6] Termine en 5 s - 21/21 chapitres - statut=done
    [4/6] Socle verrouille : NON
    [5/6] LIVRAISON IMPOSSIBLE - Job ... : aucun socle verrouille. Le livrable
          Word ne peut pas etre rendu sans socle.

Vingt-et-un chapitres ecrits, zero document. La cause est un drapeau GLOBAL,
`EVKHA_LIVRABLE_WORD=true` en production, qui envoie les QUATRE livrables vers
une chaine que deux d'entre eux ne peuvent pas honorer : `_PAR_LIVRABLE`
(socle/referentiel.py) ne couvre que l'etude de marche et l'etude
concurrentielle, donc le business plan et la strategie tournent sur le moteur
herite — ni socle, ni chapitres structures.

L'echec etait de surcroit SILENCIEUX cote tache : `run_generation_job_task`
attrape l'exception et journalise « Assemblage PDF admin impossible ».

La chaine se choisit desormais sur ce que le dossier CONTIENT, avec les memes
faits que le rendu emploie, et le repli se dit dans les journaux (regle 1).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from documents.livrable_word import chaine_word_active
from generation.models import ChapterGeneration, ChapterStatus, GenerationJob
from orders.models import Order


def _job(livrable: str, slug: str) -> GenerationJob:
    offre = Offer.objects.create(name=slug, slug=slug, deliverable_type=livrable)
    client = Customer.objects.create(email=f"{slug}@test.local")
    commande = Order.objects.create(
        systeme_order_id=f"cmd-{slug}", customer=client, offer=offre,
    )
    return GenerationJob.objects.create(
        order=commande, deliverable_type=livrable, budget_eur=Decimal("3.35"),
    )


@pytest.mark.django_db
def test_un_dossier_sans_socle_ne_part_pas_vers_la_chaine_word(settings: Any) -> None:
    """Strategie : 21 chapitres herites, aucun socle -> chaine HTML/PDF.

    Sur le code d'avant, `chaine_word_active` n'existait pas et le seul drapeau
    decidait : ce dossier partait au rendu Word, qui levait
    `LivrableIncompletError`. Le client n'obtenait rien.
    """
    settings.EVKHA_LIVRABLE_WORD = True
    job = _job(DeliverableType.BUSINESS_STRATEGY, "strategie-sans-socle")
    ChapterGeneration.objects.create(
        job=job, chapter_number=1, chapter_title="Diagnostic",
        prompt_key="str.01.diagnostic", status=ChapterStatus.DONE,
        content="Texte du chapitre, produit par le moteur herite.",
    )

    assert chaine_word_active(job) is False


@pytest.mark.django_db
def test_le_drapeau_baisse_desactive_la_chaine_word(settings: Any) -> None:
    """Contre-epreuve 1 : la bascule reversible du cahier des charges tient."""
    settings.EVKHA_LIVRABLE_WORD = False
    job = _job(DeliverableType.MARKET_STUDY, "em-drapeau-baisse")

    assert chaine_word_active(job) is False


@pytest.mark.django_db
def test_un_dossier_structure_garde_la_chaine_word(
    settings: Any, monkeypatch: Any
) -> None:
    """Contre-epreuve 2 : le correctif ne prive personne du Word.

    Un dossier qui a bien un socle ET des chapitres structures continue d'etre
    rendu par la chaine Word — sans quoi on aurait remplace « aucun document
    pour deux livrables » par « un document degrade pour les quatre ».
    """
    settings.EVKHA_LIVRABLE_WORD = True
    job = _job(DeliverableType.MARKET_STUDY, "em-avec-socle")

    monkeypatch.setattr(
        "generation.socle.services.socle_verrouille", lambda _job: object()
    )
    monkeypatch.setattr(
        "generation.rendu_word.services.payloads_du_job", lambda _job: [object()]
    )

    assert chaine_word_active(job) is True


_HTML_SAIN = """
<html><body>
  <h1>Strategie business</h1>
  <h2>CHAPITRE 01 - Diagnostic</h2>
  <p>Le marche regional pese 12 M EUR et progresse de 4 % par an, porte par
     une demande de services de proximite que l'offre actuelle ne couvre pas.</p>
  <table>
    <tr><th>Indicateur</th><th>Valeur</th></tr>
    <tr><td>Chiffre d'affaires cible</td><td>450 000 EUR</td></tr>
    <tr><td>Marge brute</td><td>62 %</td></tr>
  </table>
  <p>Court commentaire.</p>
</body></html>
"""

_HTML_TABLEAU_VIDE = """
<html><body>
  <p>Un texte, et un tableau dont les lignes ont disparu au rendu.</p>
  <table><tbody></tbody></table>
</body></html>
"""


@pytest.mark.django_db
def test_le_document_herite_est_desormais_controle(settings: Any) -> None:
    """Deux des six controles ne demandent pas de socle : ils tournent enfin.

    Sur le code d'avant, le business plan et la strategie partaient avec ZERO
    controle du fichier : `verifier_livrable` ouvre un `.docx` et compare au
    socle, deux choses que le moteur herite ne produit pas.
    """
    from delivery.services import _controler_document_herite

    settings.EVKHA_LIVRABLE_WORD = True
    job = _job(DeliverableType.BUSINESS_STRATEGY, "str-controle-html")

    assert _controler_document_herite(job, _HTML_SAIN) == ""


@pytest.mark.django_db
def test_un_tableau_vide_retient_le_document_herite(settings: Any) -> None:
    """Le defaut historique du projet : un tableau vide de ses lignes.

    Un client a recu un compte de resultat vide parce que le decoupage des
    tableaux longs detruisait leurs lignes. Ce controle-la existait, mais ne
    s'appliquait qu'aux etudes de marche.
    """
    from delivery.services import _controler_document_herite

    settings.EVKHA_LIVRABLE_WORD = True
    job = _job(DeliverableType.BUSINESS_PLAN, "bp-tableau-vide")

    motif = _controler_document_herite(job, _HTML_TABLEAU_VIDE)
    assert "sans aucune cellule" in motif, motif


@pytest.mark.django_db
def test_l_incident_nomme_ce_qui_a_tourne_ET_ce_qui_manque(settings: Any) -> None:
    """Une moitie de controle tue ne doit pas passer pour un « rien a signaler ».

    Et l'inverse est vrai aussi : un incident qui n'enumererait que les
    controles absents laisserait croire que rien n'a ete verifie.
    """
    from delivery.services import (
        INCIDENT_TYPE_CONTROLE_FICHIER_ABSENT,
        _controler_document_herite,
    )
    from monitoring.models import OperationalIncident

    settings.EVKHA_LIVRABLE_WORD = True
    job = _job(DeliverableType.BUSINESS_PLAN, "bp-incident-partiel")

    _controler_document_herite(job, _HTML_SAIN)
    _controler_document_herite(job, _HTML_SAIN)  # relivraison : pas de doublon

    incidents = OperationalIncident.objects.filter(job=job)
    assert incidents.count() == 1
    incident = incidents.first()
    assert incident is not None
    details = incident.details
    assert details["type"] == INCIDENT_TYPE_CONTROLE_FICHIER_ABSENT
    assert "couverture du socle" in details["controles_manquants"]
    assert any(
        "intégrité" in controle for controle in details["controles_executes"]
    ), details["controles_executes"]

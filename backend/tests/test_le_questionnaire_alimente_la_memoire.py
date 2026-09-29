"""Le questionnaire est la première source de la mémoire — et un vide n'arrête rien.

29/09/2026 : les réponses du client partaient en JSON brut dans chaque
chapitre ; une réponse vide ne posait aucune hypothèse, et une réponse jamais
exploitée ne se voyait nulle part. Ce fichier verrouille :
1. l'état des réponses par question du formulaire du type d'étude ;
2. une réponse obligatoire vide devient une hypothèse prudente nommée ;
3. les questions exploitées par un chapitre, et celles qu'aucun n'exploite ;
4. une étude au questionnaire INCOMPLET va au bout, sur la doublure.
"""
from __future__ import annotations

from typing import Any

import pytest
from django.test import override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres.services import produire_avec_reprises
from generation.memoire.questionnaire import (
    etat_des_reponses,
    hypotheses_pour_les_vides,
    questions_utilisees,
)
from generation.memoire.services import memoire_du_job
from generation.models import GenerationJob
from generation.services import bootstrap_generation_job
from generation.socle import etablir_socle
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StubClaudeClient
from orders.models import Order

BP = DeliverableType.BUSINESS_PLAN
#: Un questionnaire volontairement incomplet : l'identification seulement,
#: plus une réponse chiffrée.
INCOMPLET: dict[str, object] = {
    "PROJET": "Atelier Test", "SECTEUR": "Ateliers créatifs", "PAYS": "France",
    "ZONE": "Lyon", "CA_PREVISIONNEL": "Année 1 : 42 000 € ; année 2 : 55 000 €",
}


def test_chaque_question_du_formulaire_a_son_etat() -> None:
    reponses = etat_des_reponses(INCOMPLET, BP)
    assert len(reponses) == 24, "le business plan pose 24 questions"
    renseignees = {r.code for r in reponses if r.renseignee}
    assert {"PROJET", "CA_PREVISIONNEL"} <= renseignees
    assert "INVESTISSEMENT_TOTAL" not in renseignees


def test_une_reponse_obligatoire_vide_devient_une_hypothese() -> None:
    hypotheses = hypotheses_pour_les_vides(etat_des_reponses(INCOMPLET, BP))
    assert hypotheses, "des réponses obligatoires manquent"
    assert all(h.sujet == "hypothese" for h in hypotheses)
    assert all("HYPOTHÈSE PRUDENTE" in h.justification for h in hypotheses)


def test_un_questionnaire_complet_ne_pose_pas_d_hypothese() -> None:
    """Contre-épreuve."""
    complet = {r.code: "Réponse détaillée du client" for r in etat_des_reponses({}, BP)}
    assert hypotheses_pour_les_vides(etat_des_reponses(complet, BP)) == []


def test_une_reponse_se_retrouve_par_ses_nombres_ou_ses_mots() -> None:
    variables = {
        "CA_PREVISIONNEL": "Année 1 : 42 000 € ; année 2 : 55 000 €",
        "POSITIONNEMENT": "Ateliers intergénérationnels autour de la céramique contemporaine",
        "MOTIVATIONS": "Transmettre un savoir-faire familial ancestral",
    }
    texte = (
        "Le chiffre d'affaires de la première année atteint 42 000 €. Les ateliers "
        "intergénérationnels autour de la céramique forment le cœur de l'offre."
    )
    assert set(questions_utilisees(variables, texte)) == {"CA_PREVISIONNEL", "POSITIONNEMENT"}


@pytest.mark.django_db
def test_une_etude_au_questionnaire_incomplet_va_au_bout() -> None:
    offre = Offer.objects.create(name="BP", slug="bp-incomplet", deliverable_type=BP)
    client = Customer.objects.create(email="incomplet@exemple.fr")
    commande = Order.objects.create(systeme_order_id="cmd-incomplet", customer=client, offer=offre)
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED, normalized_variables=INCOMPLET,
    )
    with override_settings(EVKHA_MEMOIRE_ETUDE=True):
        job: GenerationJob = bootstrap_generation_job(soumission)
    etablir_socle(job, client=StubClaudeClient(), variables=INCOMPLET)

    for numero in (1, 16):
        chapitre = produire_avec_reprises(job, numero, client=StubClaudeClient())
        assert chapitre.etape == "valide"

    memoire = memoire_du_job(job)
    assert memoire is not None
    job.refresh_from_db()
    contenu: dict[str, Any] = job.memoire_etude
    assert any(d["sujet"] == "hypothese" for d in contenu["decisions"])
    assert any(not r["renseignee"] for r in contenu["reponses"])
    assert "HYPOTHÈSE PRUDENTE" in memoire.bloc_pour_le_redacteur()
    assert "questions" in contenu["chapitres"]["16"]

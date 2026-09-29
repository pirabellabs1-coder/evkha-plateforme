"""La mémoire de l'étude ne s'applique qu'aux dossiers créés après sa mise en service.

Engagement du 29/09/2026 : aucune étude déjà générée n'est modifiée, ni
régénérée ; les nouvelles règles valent pour les études lancées après le
déploiement. Le drapeau est donc figé à la CRÉATION du dossier
(`GenerationJob.memoire_active`), jamais relu depuis le réglage ensuite.
"""
from __future__ import annotations

import pytest
from django.test import override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.memoire.services import memoire_du_job
from generation.models import GenerationJob
from generation.services import bootstrap_generation_job
from generation.socle import etablir_socle
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StubClaudeClient
from orders.models import Order

pytestmark = pytest.mark.django_db

BP = DeliverableType.BUSINESS_PLAN
VARIABLES = {
    "SECTEUR": "ateliers", "PAYS": "France", "ZONE": "Île-de-France", "PROJET": "Projet test",
    "DATE_CREATION": "Trajectoire juridique : micro-entreprise de 2027 à 2029.",
}


def _dossier(suffixe: str) -> GenerationJob:
    offre, _ = Offer.objects.get_or_create(
        slug="bp-memoire", defaults={"name": "Business plan", "deliverable_type": BP},
    )
    client = Customer.objects.create(email=f"memoire-{suffixe}@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id=f"cmd-memoire-{suffixe}", customer=client, offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED, normalized_variables=VARIABLES,
    )
    return bootstrap_generation_job(soumission)


def test_un_dossier_cree_avec_le_reglage_porte_la_memoire() -> None:
    with override_settings(EVKHA_MEMOIRE_ETUDE=True):
        job = _dossier("a")
    assert job.memoire_active is True


def test_un_dossier_cree_sans_le_reglage_n_en_a_pas() -> None:
    with override_settings(EVKHA_MEMOIRE_ETUDE=False):
        job = _dossier("b")
    assert job.memoire_active is False


def test_basculer_le_reglage_ne_change_pas_un_dossier_existant() -> None:
    """Une relance repasse par `bootstrap_generation_job` : le drapeau ne bouge pas."""
    with override_settings(EVKHA_MEMOIRE_ETUDE=False):
        job = _dossier("c")
    with override_settings(EVKHA_MEMOIRE_ETUDE=True):
        soumission = IntakeSubmission.objects.get(order=job.order)
        relu = bootstrap_generation_job(soumission)
    assert relu.pk == job.pk
    assert relu.memoire_active is False


def test_la_memoire_se_construit_sur_le_socle_verrouille_et_se_garde() -> None:
    with override_settings(EVKHA_MEMOIRE_ETUDE=True):
        job = _dossier("d")
    assert memoire_du_job(job) is None, "sans socle verrouillé, pas de mémoire à moitié"

    etablir_socle(job, client=StubClaudeClient(), variables=VARIABLES)
    memoire = memoire_du_job(job)

    assert memoire is not None
    assert "ca_previsionnel_evolution_an1_an3" in memoire.faits
    job.refresh_from_db()
    assert job.memoire_etude["faits"]["ca_previsionnel_an1"]["origine"]
    assert any(d["source"] == "brief" for d in job.memoire_etude["decisions"])


def test_un_dossier_sans_memoire_n_est_jamais_touche() -> None:
    with override_settings(EVKHA_MEMOIRE_ETUDE=False):
        job = _dossier("e")
    etablir_socle(job, client=StubClaudeClient(), variables=VARIABLES)

    assert memoire_du_job(job) is None
    job.refresh_from_db()
    assert job.memoire_etude == {}


def test_une_memoire_impossible_a_construire_n_arrete_pas_l_etude(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le dossier retombe sur le chemin d'avant : jamais une étude arrêtée."""
    from generation.memoire import etude

    with override_settings(EVKHA_MEMOIRE_ETUDE=True):
        job = _dossier("f")
    etablir_socle(job, client=StubClaudeClient(), variables=VARIABLES)

    def casse(*_: object, **__: object) -> None:
        raise RuntimeError("panne simulée")

    monkeypatch.setattr(etude.MemoireEtude, "construire", classmethod(casse))
    assert memoire_du_job(job) is None


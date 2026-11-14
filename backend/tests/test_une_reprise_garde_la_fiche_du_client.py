"""Refaire un dossier commandé depuis une fiche client garde CE client.

## Le défaut, trouvé le 14/11/2026 avant une génération de test

`job_regenerer` recopiait le brief VERBATIM et créait une commande SANS
projet. Or le brief d'un dossier passé avant le correctif d'identité
(`3fd5145`) porte la charte de « Ma marque » — celle d'un autre client de
l'abonnée. Reprendre la stratégie Dibitek `d319a9e5` aurait donc réimprimé
« SUNTZU KOUMISITH POLY GROUPES FRANCE », son logo et ses couleurs, alors que
le correctif était en ligne : le test aurait « prouvé » qu'il ne marchait pas.

Le brief reste recopié en entier (`test_un_dossier_se_refait_a_l_identique`) ;
seule la charte est relue sur la fiche, telle qu'elle est AUJOURD'HUI.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from tests.test_un_dossier_se_refait_a_l_identique import BRIEF_RICHE

pytestmark = pytest.mark.django_db

#: Ce qu'un brief d'avant le 13/11/2026 portait : la charte de « Ma marque ».
CHARTE_D_UN_AUTRE = {
    "NOM_ENTREPRISE": "SUNTZU KOUMISITH POLY GROUPES FRANCE",
    "LOGO_URL": "/media/pieces-jointes/x/logo-suntzu.jpeg",
    "COULEUR_PRINCIPALE": "#1B3A8C",
    "COULEUR_SECONDAIRE": "#D7262E",
}


def _dossier(*, avec_fiche: bool, **charte: str) -> Any:
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import GenerationJob, JobStatus
    from intake.models import IntakeSource, IntakeStatus, IntakeSubmission
    from orders.models import Order
    from organisations.models import ClientFinal, Projet

    projet = None
    if avec_fiche:
        from tests.test_lot4_commander import Abonne

        organisation = Abonne("Agence", "reprise-fiche@example.com").organisation
        client = ClientFinal.objects.create(
            organisation=organisation, raison_sociale="Dibitek", **charte
        )
        projet = Projet.objects.create(client=client, nom="Dibitek Forge")
    offre = Offer.objects.create(
        name="STR", slug="test-reprise-fiche",
        deliverable_type=DeliverableType.BUSINESS_STRATEGY,
    )
    commande = Order.objects.create(
        systeme_order_id="cmd-fiche", customer=Customer.objects.create(email="f@test.local"),
        offer=offre, projet=projet,
    )
    IntakeSubmission.objects.create(
        order=commande, source=IntakeSource.MANUAL, status=IntakeStatus.NORMALIZED,
        normalized_variables={**BRIEF_RICHE, **CHARTE_D_UN_AUTRE},
    )
    return GenerationJob.objects.create(
        order=commande, deliverable_type=DeliverableType.BUSINESS_STRATEGY,
        status=JobStatus.DONE,
    )


def _reprendre(client_admin: Any, dossier: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    from generation import tasks
    from generation.models import GenerationJob

    monkeypatch.setattr(tasks.run_generation_job_task, "delay", lambda *a, **k: None)
    reponse = client_admin.post(
        f"/api/dashboard/jobs/{dossier.id}/regenerer/",
        data=json.dumps({"sans_envoi": True}), content_type="application/json",
    )
    assert reponse.status_code == 202, reponse.content
    nouveau = json.loads(reponse.content)["job_id"]
    return GenerationJob.objects.select_related("order").get(id=nouveau)


def test_la_reprise_garde_la_fiche_et_sa_charte_actuelle(
    client_admin: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    dossier = _dossier(
        avec_fiche=True, couleur_principale="#0A7D5A", logo_url="https://exemple.test/d.png"
    )

    reprise = _reprendre(client_admin, dossier, monkeypatch)
    variables = reprise.order.intake_submission.normalized_variables

    assert reprise.order.projet_id == dossier.order.projet_id
    assert variables["NOM_ENTREPRISE"] == "Dibitek"
    assert variables["COULEUR_PRINCIPALE"] == "#0A7D5A"
    assert variables["LOGO_URL"] == "https://exemple.test/d.png"
    # Ce que la fiche ne porte pas est RETIRÉ, pas hérité de l'autre client.
    assert "COULEUR_SECONDAIRE" not in variables
    assert "SUNTZU" not in json.dumps(variables)
    # Le reste du brief est intact.
    assert variables["RESUME_EXECUTIF"] == BRIEF_RICHE["RESUME_EXECUTIF"]


def test_une_reprise_sans_fiche_recopie_le_brief_tel_quel(
    client_admin: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Contre-épreuve : une commande directe garde la marque de son brief."""
    dossier = _dossier(avec_fiche=False)

    reprise = _reprendre(client_admin, dossier, monkeypatch)

    assert reprise.order.projet_id is None
    assert reprise.order.intake_submission.normalized_variables == {
        **BRIEF_RICHE, **CHARTE_D_UN_AUTRE,
    }

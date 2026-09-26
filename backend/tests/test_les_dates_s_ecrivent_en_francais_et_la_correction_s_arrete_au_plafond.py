"""« 26 aout 2026 » en couverture, « arrêté au 2026-08-08 » dans le prompt.

Relecture du 26/09/2026. Deux listes de mois vivaient dans le dépôt : une
accentuée (`rendering.py`), une SANS accents (`rendu_word/assemblage.py`) —
et c'est la seconde qui datait la page de couverture de chaque document livré
(règle 5 : une seule source par vérité). La ligne du socle injectée dans chaque
prompt de chapitre datait ses chiffres en ISO, forme que le modèle recopie.

Et la régénération de correction (`regenerer_chapitre`) appelait la boucle de
reprises SANS les arrêts sans reprise de la première rédaction : un plafond de
dépense franchi pendant une correction était retenté, puis avalé, et la boucle
passait au chapitre suivant — payé lui aussi.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from catalog.models import DeliverableType, Offer
from core.dates import MOIS_FR, date_francaise
from customers.models import Customer
from generation import rendering
from generation.chapitres.runner import _bloc_socle
from generation.chapitres.services import produire_chapitre, regenerer_chapitre
from generation.cost import CostBudgetExceededError
from generation.models import GenerationJob
from generation.rendu_word import assemblage
from generation.services import bootstrap_generation_job
from generation.socle import Socle, etablir_socle
from generation.socle.prompt import construire_prompt_socle
from generation.socle.stub import socle_de_demonstration
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StubClaudeClient
from orders.models import Order

EM = DeliverableType.MARKET_STUDY
_VARIABLES = {
    "SECTEUR": "joaillerie de créateurs",
    "PAYS": "France",
    "ZONE": "Paris",
    "PROJET": "maison d'édition joaillière",
}


# ── Les dates ────────────────────────────────────────────────────────────────


def test_la_date_francaise_porte_ses_accents() -> None:
    assert date_francaise(date(2026, 8, 8)) == "8 août 2026"
    assert date_francaise(date(2026, 12, 25)) == "25 décembre 2026"
    assert date_francaise(date(2026, 2, 1), jour_sur_deux_chiffres=True) == "01 février 2026"


def test_une_seule_liste_de_mois_dans_le_depot() -> None:
    assert rendering._MOIS_FR is MOIS_FR
    source = Path(assemblage.__file__).read_text(encoding="utf-8")
    assert "date_francaise(" in source
    for sans_accent in ('"aout"', '"fevrier"', '"decembre"'):
        assert sans_accent not in source, sans_accent


def test_la_ligne_du_socle_date_ses_chiffres_en_francais() -> None:
    prompt = construire_prompt_socle(deliverable_type=EM, variables=_VARIABLES)
    charge = socle_de_demonstration(prompt)
    socle = Socle.model_validate({**charge, "date_socle": "2026-08-08"})
    socle.deliverable_type = EM

    bloc = _bloc_socle(socle)

    assert "arrêté au 8 août 2026" in bloc
    assert "2026-08-08" not in bloc


# ── La correction s'arrête au plafond ────────────────────────────────────────


@pytest.fixture
def job_em(db: Any) -> GenerationJob:
    offre = Offer.objects.create(name="EM", slug="em-plafond-correction", deliverable_type=EM)
    client = Customer.objects.create(email="plafond-correction@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-plafond-correction", customer=client, offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED, normalized_variables=_VARIABLES,
    )
    job = bootstrap_generation_job(soumission)
    etablir_socle(job, client=StubClaudeClient(), variables=_VARIABLES)
    return job


class _ClientAuPlafond:
    def __init__(self) -> None:
        self.appels = 0

    def complete_structured(self, **_: Any) -> Any:
        self.appels += 1
        msg = "Plafond de depense atteint"
        raise CostBudgetExceededError(msg)


@pytest.mark.django_db
def test_un_plafond_franchi_en_correction_ne_se_retente_pas(job_em: GenerationJob) -> None:
    produire_chapitre(job_em, 1, client=StubClaudeClient())
    client = _ClientAuPlafond()

    with pytest.raises(CostBudgetExceededError):
        regenerer_chapitre(job_em, 1, client=client, note_corrective="un motif")

    assert client.appels == 1, "le plafond n'est pas une panne : on ne réessaie pas"

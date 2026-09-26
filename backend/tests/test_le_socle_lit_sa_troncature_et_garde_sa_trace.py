"""Le socle lit sa troncature, garde la trace de son échec et compte son coût.

Trois défauts relevés le 26/09/2026 dans le constructeur de socle, chacun
reproduit ici et vérifié en échec sur le code d'avant (règle 6) :

1. `produire_socle` ne lisait pas `stop_reason`. Une réponse coupée par
   `max_tokens` arrive avec un payload vide et était refusée pour « aucun
   appel d'outil exploitable » — un motif qui ne dit rien à corriger, donc
   trois tentatives identiques et un dossier mort avant son premier chapitre.
2. `etablir_socle` était `@transaction.atomic` : l'enregistrement INVALIDE
   (motifs, tentatives) était écrit puis annulé par le `raise`. Le tableau de
   bord ne trouvait aucun socle et affichait « en attente » pour un FAILED.
3. `current_job_cost_eur` ne sommait que les chapitres : le coût du socle,
   ajouté à `total_cost_eur` à la validation, était écrasé au premier
   chapitre — hors facture, hors plafond.

Et `verifier_le_socle` avait l'angle mort du point 1 : une réponse tronquée se
validait en `verdicts=[]`, chaque chiffre observé était déclassé « non
examiné » et le rapport disait la passe exécutée — un contrôle qui n'a rien
pu lire déclarait avoir tout jugé (règle 1, à l'envers).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.cost import current_job_cost_eur, record_chapter_cost
from generation.models import ChapterGeneration, GenerationJob, SocleDonnees, SocleStatut
from generation.socle import (
    MAX_TENTATIVES,
    SocleGenerationError,
    etablir_socle,
    produire_socle,
)
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Zone
from generation.socle.stub import socle_de_demonstration
from generation.socle.verification import verifier_le_socle
from integrations.claude import StructuredResult
from orders.models import Order

EM = DeliverableType.MARKET_STUDY
_VARIABLES = {
    "SECTEUR": "joaillerie de créateurs",
    "PAYS": "France",
    "ZONE": "Paris",
    "PROJET": "maison d'édition joaillière",
}
BRIEF = "Fevad, 2025 — le marché français de l'e-commerce animalier atteint 1,2 Md€."


def _coupe() -> StructuredResult:
    """Ce que rend l'API quand `max_tokens` coupe l'appel d'outil : rien d'utile."""
    return StructuredResult(
        payload={}, input_tokens=10, output_tokens=16_384, model="stub",
        stop_reason="max_tokens",
    )


class _ClientToujoursCoupe:
    def __init__(self) -> None:
        self.appels = 0

    def complete_structured(self, **_: Any) -> StructuredResult:
        self.appels += 1
        return _coupe()


class _ClientCoupeUneFois:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete_structured(self, **kwargs: Any) -> StructuredResult:
        prompt = str(kwargs["prompt"])
        self.prompts.append(prompt)
        if len(self.prompts) == 1:
            return _coupe()
        return StructuredResult(
            payload=socle_de_demonstration(prompt), input_tokens=5, output_tokens=5,
            model="stub",
        )


# ── 1. La troncature est lue, et nommée au modèle ────────────────────────────


def test_une_reponse_coupee_est_nommee_comme_telle() -> None:
    client = _ClientToujoursCoupe()
    with pytest.raises(SocleGenerationError) as capture:
        produire_socle(client=client, deliverable_type=EM, variables=_VARIABLES)

    assert client.appels == MAX_TENTATIVES
    assert any("tronquee" in motif for motif in capture.value.motifs), capture.value.motifs


def test_la_tentative_suivante_recoit_le_motif_de_troncature() -> None:
    client = _ClientCoupeUneFois()
    _socle, _conso, tentatives = produire_socle(
        client=client, deliverable_type=EM, variables=_VARIABLES,
    )
    assert tentatives == 2
    assert "tronquee" in client.prompts[1]


# ── La vérification ne déclasse pas ce qu'elle n'a pas lu ────────────────────


def _socle(*donnees: DonneeSocle) -> Socle:
    return Socle(
        secteur="e-commerce animalier", zone=Zone(pays="France"),
        date_socle=date(2026, 8, 9), donnees=list(donnees),
    )


def _observee() -> DonneeSocle:
    return DonneeSocle(
        id="tam", libelle="Marché total", valeur=1.2, unite="MdEUR", annee=2025,
        perimetre=Perimetre.NATIONAL, fiabilite=Fiabilite.OBSERVEE, source="Fevad, 2025",
    )


class _Verificateur:
    def __init__(self, resultat: StructuredResult) -> None:
        self._resultat = resultat

    def complete_structured(self, **_: Any) -> StructuredResult:
        return self._resultat


def test_une_verification_coupee_ne_declasse_rien() -> None:
    socle = _socle(_observee())
    rapport = verifier_le_socle(socle, client=_Verificateur(_coupe()), brief_recherche=BRIEF)

    assert rapport.passe_executee is False
    assert "tronquee" in (rapport.motif_non_executee or "")
    assert socle.donnees[0].fiabilite == Fiabilite.OBSERVEE
    assert rapport.declassees == []


def test_une_verification_sans_aucun_verdict_n_est_pas_une_passe() -> None:
    socle = _socle(_observee())
    vide = StructuredResult(payload={"verdicts": []}, input_tokens=1, output_tokens=1, model="stub")
    rapport = verifier_le_socle(socle, client=_Verificateur(vide), brief_recherche=BRIEF)

    assert rapport.passe_executee is False
    assert socle.donnees[0].fiabilite == Fiabilite.OBSERVEE


# ── 2 et 3. Ce qui reste en base ─────────────────────────────────────────────


@pytest.fixture
def job(db: Any) -> GenerationJob:
    offre = Offer.objects.create(name="EM", slug="socle-trace", deliverable_type=EM)
    client = Customer.objects.create(email="socle-trace@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-socle-trace", customer=client, offer=offre,
    )
    return GenerationJob.objects.create(
        order=commande, deliverable_type=EM, budget_eur=Decimal("8.0000"),
    )


def test_l_echec_du_socle_laisse_sa_trace_en_base(job: GenerationJob) -> None:
    with pytest.raises(SocleGenerationError):
        etablir_socle(job, client=_ClientToujoursCoupe(), variables=_VARIABLES)

    trace = SocleDonnees.objects.get(job=job)
    assert trace.statut == SocleStatut.INVALIDE
    assert trace.tentatives == MAX_TENTATIVES
    assert trace.motifs_rejet, "les motifs du refus sont ce que le tableau de bord montre"


def test_le_cout_du_socle_reste_dans_le_total_apres_le_premier_chapitre(
    job: GenerationJob,
) -> None:
    SocleDonnees.objects.create(job=job, statut=SocleStatut.VALIDE, cost_eur=Decimal("0.5000"))
    chapitre = ChapterGeneration.objects.create(
        job=job, chapter_number=1, chapter_title="Un", prompt_key="em.01",
    )

    record_chapter_cost(chapter=chapitre, input_tokens=30_000, output_tokens=3_000)

    chapitre.refresh_from_db()
    job.refresh_from_db()
    total = current_job_cost_eur(job)
    assert total == chapitre.cost_eur + Decimal("0.5000")
    assert job.total_cost_eur == total, "le total écrit en base est celui de la facture"

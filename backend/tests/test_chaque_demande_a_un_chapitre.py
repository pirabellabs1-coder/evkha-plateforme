"""Chaque demande du client reçoit un chapitre qui en a la charge.

Étude de marché `a6947890` (01/11/2026) : le brief demandait « en priorité » le
coût livré d'un lot de 25 €, le volume de rentabilité, des prix réels relevés.
Le brief partait entier dans chaque chapitre, mais le plan fixe n'a aucun
chapitre « coût d'un lot » : 48 demandes sur 54 insuffisamment traitées. Voir
`generation.repartition`.

Ces tests interrogent le prompt RÉELLEMENT construit (règle 8 : écrit ne veut
pas dire transmis), et le lancement du dossier.
"""
from __future__ import annotations

import dataclasses
import uuid
from typing import Any

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.blueprints import chapters_for_deliverable
from generation.chapitres.configuration import type_document
from generation.chapitres.runner import construire_prompt_chapitre
from generation.models import GenerationJob
from generation.repartition import (
    CLE,
    bloc_de_la_repartition,
    bloc_du_chapitre,
    chapitres_eligibles,
    repartir_les_demandes,
)
from generation.runner import _repartir_les_demandes
from generation.services import bootstrap_generation_job
from intake.models import IntakeSource, IntakeStatus, IntakeSubmission
from integrations.claude import StructuredResult
from monitoring.models import OperationalIncident
from orders.models import Order

from .test_les_prompts_portent_les_demandes import SOCLE

LOT = "Point de vigilance majeur : concilier petits prix et envoi depuis la France."
VOLUME = "À partir de quel volume le modèle devient-il rentable ?"
CONTEXTE = "Nous vendons déjà des produits du terroir en France depuis 2019."

VARIABLES: dict[str, str] = {
    "SECTEUR": "produits du terroir français",
    "PAYS": "Chine",
    "PROJET": "Vente en Asie sur plateformes grand public",
    "DEMANDES_SPECIFIQUES": f"{LOT}\n{VOLUME}",
    "HISTORIQUE": CONTEXTE,
}


class _Client:
    """Rend la réponse qu'on lui donne, et compte les appels."""

    def __init__(self, payload: dict[str, object], stop_reason: str = "end_turn") -> None:
        self.payload = payload
        self.stop_reason = stop_reason
        self.appels: list[dict[str, Any]] = []

    def complete_structured(self, **kwargs: Any) -> StructuredResult:
        self.appels.append(kwargs)
        return StructuredResult(
            payload=self.payload, input_tokens=4_000, output_tokens=600,
            model="claude-sonnet-5", stop_reason=self.stop_reason,
        )


def _numeros() -> dict[str, int]:
    from generation.couverture import candidats_du_brief

    return {c.texte: c.numero for c in candidats_du_brief(VARIABLES)}


def _plan() -> list[Any]:
    return list(chapters_for_deliverable(DeliverableType.MARKET_STUDY))


# ─── La répartition elle-même ───────────────────────────────────────────────


def test_l_annexe_des_reponses_ne_recoit_aucune_demande() -> None:
    """Elle RÉSUME : lui confier une demande, c'est la faire traiter en une ligne."""
    numeros = {c.numero for c in chapitres_eligibles(_plan())}
    assert 14 in numeros  # Potentiel de viabilité
    assert not numeros & {0, 21, 22}


def test_chaque_demande_va_a_son_chapitre_et_le_contexte_n_en_a_aucun() -> None:
    n = _numeros()
    client = _Client({
        "demandes": [
            {"n": n[LOT], "chapitre": 14, "attendu": "le coût livré d'un lot de 25 €"},
            {"n": n[VOLUME], "chapitre": 14, "attendu": "le volume de rentabilité"},
        ],
        "contexte": [v for t, v in n.items() if t not in (LOT, VOLUME)],
    })

    repartition = repartir_les_demandes(client=client, variables=VARIABLES, plan=_plan())

    assert repartition.executee
    assert [(c, t) for c, _, t, _ in repartition.demandes] == [(14, LOT), (14, VOLUME)]
    assert repartition.non_reparties == []
    # Le modèle voit le plan, chapitres de fond seulement.
    prompt = client.appels[0]["prompt"]
    assert "14 — Potentiel de viabilité" in prompt
    assert "Réponses essentielles" not in prompt


def test_un_chapitre_hors_du_plan_n_est_pas_une_affectation() -> None:
    """Le modèle a écrit 22 (l'annexe) ou 99 : la demande n'a personne. Le dire."""
    n = _numeros()
    client = _Client({
        "demandes": [
            {"n": n[LOT], "chapitre": 22, "attendu": ""},
            {"n": n[VOLUME], "chapitre": 99, "attendu": ""},
        ],
        "contexte": [v for t, v in n.items() if t not in (LOT, VOLUME)],
    })

    repartition = repartir_les_demandes(client=client, variables=VARIABLES, plan=_plan())

    assert repartition.demandes == []
    assert repartition.non_reparties == [LOT, VOLUME]
    assert not repartition.executee  # 2 sur 5 : au-delà du seuil


def test_une_reponse_coupee_nomme_le_budget() -> None:
    client = _Client({"demandes": [], "contexte": []}, stop_reason="max_tokens")

    repartition = repartir_les_demandes(client=client, variables=VARIABLES, plan=_plan())

    assert not repartition.executee
    assert "coupée par le budget" in repartition.motif


def test_une_panne_ne_leve_pas() -> None:
    class _EnPanne:
        def complete_structured(self, **_: Any) -> StructuredResult:
            raise TimeoutError("délai dépassé")

    repartition = repartir_les_demandes(
        client=_EnPanne(), variables=VARIABLES, plan=_plan(),
    )

    assert repartition.essais == 3
    assert repartition.input_tokens == 0
    assert not repartition.executee
    assert "TimeoutError" in repartition.motif


def test_une_ligne_fautive_n_emporte_pas_les_autres_ni_le_cout() -> None:
    """`n: 0` invalide sa ligne, pas la réponse entière ; et l'appel reste payé."""
    n = _numeros()
    client = _Client({
        "demandes": [
            {"n": n[LOT], "chapitre": 14, "attendu": "coût d'un lot"},
            {"n": 0, "chapitre": 14, "attendu": "", "en_trop": 1},
        ],
        "contexte": [v for t, v in n.items() if t not in (LOT, VOLUME)],
    })

    repartition = repartir_les_demandes(client=client, variables=VARIABLES, plan=_plan())

    assert [t for _, _, t, _ in repartition.demandes] == [LOT]
    assert VOLUME in repartition.non_reparties
    assert repartition.input_tokens == 4_000


def test_une_reponse_vide_se_retente_et_chaque_essai_se_compte() -> None:
    """Le vrai client rend `{}` quand le modèle n'appelle pas l'outil."""
    n = _numeros()
    bonne = {
        "demandes": [{"n": n[LOT], "chapitre": 14, "attendu": ""},
                     {"n": n[VOLUME], "chapitre": 14, "attendu": ""}],
        "contexte": [v for t, v in n.items() if t not in (LOT, VOLUME)],
    }

    class _VideDAbord(_Client):
        def complete_structured(self, **kwargs: Any) -> StructuredResult:
            resultat = super().complete_structured(**kwargs)
            if len(self.appels) == 1:
                return dataclasses.replace(resultat, payload={})
            return resultat

    client = _VideDAbord(bonne)
    repartition = repartir_les_demandes(client=client, variables=VARIABLES, plan=_plan())

    assert repartition.executee
    assert repartition.essais == 2
    assert repartition.input_tokens == 8_000


def test_la_doublure_ne_confie_qu_a_des_chapitres_eligibles() -> None:
    from generation.couverture import candidats_du_brief
    from generation.repartition import _prompt, repartition_de_demonstration

    chapitres = chapitres_eligibles(_plan())
    charge = repartition_de_demonstration(_prompt(candidats_du_brief(VARIABLES), chapitres))
    demandes = charge["demandes"]
    assert isinstance(demandes, list)

    assert {d["chapitre"] for d in demandes} <= {c.numero for c in chapitres}
    assert len(demandes) == len(_numeros())


# ─── Ce que les chapitres en reçoivent ──────────────────────────────────────

TRACE = {CLE: {"demandes": [
    {"chapitre": 14, "champ": "DEMANDES_SPECIFIQUES", "texte": LOT,
     "attendu": "le coût livré d'un lot de 25 € poste par poste"},
    {"chapitre": 10, "champ": "DEMANDES_SPECIFIQUES", "texte": VOLUME, "attendu": ""},
]}}


def test_le_chapitre_recoit_ses_demandes_et_seulement_les_siennes() -> None:
    bloc = bloc_du_chapitre(TRACE, 14)

    assert LOT in bloc
    assert "poste par poste" in bloc
    assert VOLUME not in bloc
    assert "calcul POSÉ" in bloc
    assert "premiers envois" in bloc  # le renvoi exact que l'étude a fait
    assert bloc_du_chapitre(TRACE, 3) == ""


def test_contre_epreuve_un_dossier_sans_repartition_ne_change_pas() -> None:
    assert bloc_du_chapitre({}, 14) == ""
    assert bloc_de_la_repartition(None) == ""
    assert bloc_de_la_repartition({"chapitres": {}}) == ""


def _dossier(variables: dict[str, str]) -> GenerationJob:
    offre, _ = Offer.objects.get_or_create(
        slug="verif-repartition",
        defaults={"name": "Verif", "deliverable_type": DeliverableType.MARKET_STUDY},
    )
    contact, _ = Customer.objects.get_or_create(email="verif-repartition@test.local")
    commande = Order.objects.create(
        systeme_order_id=f"verif-repartition-{uuid.uuid4().hex[:8]}",
        customer=contact, offer=offre,
    )
    IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED,
        source=IntakeSource.MANUAL, normalized_variables=variables,
    )
    return bootstrap_generation_job(commande.intake_submission)


@pytest.mark.django_db
def test_le_prompt_reellement_envoye_porte_la_demande_confiee() -> None:
    """Le câble, pas la fonction : la demande est dans le prompt du chapitre 14,
    dans sa partie PROPRE ; la table complète est dans la partie commune."""
    job = _dossier(VARIABLES)
    GenerationJob.objects.filter(pk=job.pk).update(memoire_etude=TRACE)
    job.refresh_from_db()

    def prompt(numero: int) -> Any:
        chapitre = job.chapters.get(chapter_number=numero)
        construit, _ = construire_prompt_chapitre(
            chapitre, socle=SOCLE, variables=VARIABLES,
            document=type_document(DeliverableType.MARKET_STUDY),
        )
        return construit

    p14, p3 = prompt(14), prompt(3)

    assert "CONFIÉES À CE CHAPITRE" in p14.par_chapitre
    assert "poste par poste" in p14.par_chapitre
    assert "CONFIÉES À CE CHAPITRE" not in p3.par_chapitre
    # La table est la même pour les deux : condition du cache.
    assert "RÉPARTITION DES DEMANDES DU CLIENT" in p14.par_job
    assert p14.par_job == p3.par_job


# ─── Le lancement du dossier ────────────────────────────────────────────────


@pytest.mark.django_db
def test_le_lancement_garde_la_repartition_et_compte_son_cout() -> None:
    job = _dossier(VARIABLES)
    n = _numeros()
    client = _Client({
        "demandes": [{"n": n[LOT], "chapitre": 14, "attendu": "coût d'un lot"},
                     {"n": n[VOLUME], "chapitre": 14, "attendu": "volume"}],
        "contexte": [v for t, v in n.items() if t not in (LOT, VOLUME)],
    })

    _repartir_les_demandes(job, client=client, variables=VARIABLES)
    job.refresh_from_db()

    trace = job.memoire_etude[CLE]
    assert trace["executee"] is True
    assert [d["texte"] for d in trace["demandes"]] == [LOT, VOLUME]
    fiche = job.chapters.get(chapter_number=0)
    assert fiche.input_tokens == 4_000
    assert job.total_cost_eur > 0

    # Une relance ne repaie pas, et ne change pas ce que les chapitres ont lu.
    _repartir_les_demandes(job, client=client, variables=VARIABLES)
    assert len(client.appels) == 1


@pytest.mark.django_db
def test_un_echec_se_dit_dans_un_incident_sans_arreter_le_dossier() -> None:
    job = _dossier(VARIABLES)
    client = _Client({"demandes": [], "contexte": []})

    _repartir_les_demandes(job, client=client, variables=VARIABLES)

    incident = OperationalIncident.objects.get(job=job)
    assert "NON réparties" in incident.title
    assert incident.details["type"] == "repartition_des_demandes"
    assert len(incident.details["non_reparties"]) == len(_numeros())
    # Trois essais payés, comptés même en échec.
    assert job.chapters.get(chapter_number=0).input_tokens == 12_000

    # Aucun chapitre de fond écrit : la relance retente, personne n'a lu l'échec.
    n = _numeros()
    client.payload = {
        "demandes": [{"n": n[LOT], "chapitre": 14, "attendu": ""},
                     {"n": n[VOLUME], "chapitre": 14, "attendu": ""}],
        "contexte": [v for t, v in n.items() if t not in (LOT, VOLUME)],
    }
    _repartir_les_demandes(job, client=client, variables=VARIABLES)
    job.refresh_from_db()
    assert job.memoire_etude[CLE]["executee"] is True


@pytest.mark.django_db
def test_la_memoire_reconstruite_garde_la_repartition() -> None:
    """Contre-épreuve d'écrasement : `memoire_du_job` réécrit `memoire_etude`."""
    from generation.memoire.services import memoire_du_job

    job = _dossier(VARIABLES)
    GenerationJob.objects.filter(pk=job.pk).update(memoire_etude=TRACE, memoire_active=True)
    job.refresh_from_db()
    memoire_du_job(job)
    job.refresh_from_db()

    assert job.memoire_etude[CLE] == TRACE[CLE]

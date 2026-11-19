"""Audit du 19/11/2026 — l'argent et le cycle de vie d'un dossier.

Six lectures indépendantes du dépôt, chacune vérifiée ensuite dans le code. Ce
fichier verrouille les défauts confirmés qui touchent l'argent d'une cliente ou
l'état d'un dossier :

1. une tâche de génération produisait un dossier quel que soit son état —
   annulé, déjà pris par une autre tâche, déjà terminé ;
2. une résiliation n'arrêtait pas le prélèvement, et la facture suivante
   rouvrait l'abonnement ;
3. un événement Stripe renvoyé après un échec était avalé comme « doublon » ;
4. un crédit remboursé perdait l'étude pour laquelle il avait été payé ;
5. deux plafonds publics étaient lus sans jamais être comptés ;
6. la relecture finale n'avait aucun moyen de dire qu'elle était vivante, et
   son rattrapage des chapitres manquants appelait le modèle sans client ;
7. l'espace client proposait le document pendant qu'on le corrigeait.

Chaque test échoue sur le code d'avant ; chaque règle a sa contre-épreuve.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import timedelta
from typing import Any

import pytest
from django.test import Client, override_settings
from django.utils import timezone
from paiement import abonnements, stripe_api

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation import controle_final, tasks
from generation.models import GenerationJob, JobStatus
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from integrations.models import IntegrationProvider, WebhookEvent, WebhookStatus
from integrations.webhooks import DELAI_D_UN_TRAITEMENT_PERDU, record_webhook_event
from orders.models import Order
from organisations import credits, limitation, services, suivi
from organisations.models import (
    AbonnementOrganisation,
    Formule,
    StatutAbonnement,
    TypeMouvement,
)

pytestmark = pytest.mark.django_db

SECRET = "whsec_secret_de_test_pour_l_audit"
CS = DeliverableType.COMPETITOR_STUDY


def _dossier(suffixe: str = "a") -> GenerationJob:
    offre, _ = Offer.objects.get_or_create(
        slug="ec-audit", defaults={"name": "Étude de la concurrence", "deliverable_type": CS},
    )
    client = Customer.objects.create(email=f"audit-{suffixe}@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id=f"cmd-audit-{suffixe}", customer=client, offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "ateliers", "PAYS": "France", "PROJET": "Audit"},
    )
    return bootstrap_generation_job(soumission)


def _organisation(suffixe: str = "a") -> Any:
    contact = Customer.objects.create(email=f"cabinet-{suffixe}@exemple.fr")
    return services.creer_organisation(raison_sociale=f"Cabinet {suffixe}", contact=contact)


def _formule() -> Formule:
    formule, _ = Formule.objects.get_or_create(
        code="pro-audit",
        defaults={
            "libelle": "Pro", "credits_par_echeance": 3, "prix_mensuel_cents": 18_900,
            "reference_paiement": "price_de_test", "active": True,
        },
    )
    return formule


# ── 1. Une seule tâche produit un dossier ───────────────────────────────────


def test_un_dossier_en_attente_se_prend_une_fois() -> None:
    job = _dossier()

    assert tasks.prendre_le_dossier(str(job.id)) is True
    assert tasks.prendre_le_dossier(str(job.id)) is False

    job.refresh_from_db()
    assert job.status == JobStatus.RUNNING


@pytest.mark.parametrize("statut", [JobStatus.CANCELLED, JobStatus.DONE, JobStatus.RUNNING])
def test_une_tache_ne_produit_pas_un_dossier_qui_n_attend_pas(
    monkeypatch: pytest.MonkeyPatch, statut: str,
) -> None:
    """Annulé en file, déjà pris, déjà terminé : la tâche sort sans rien écrire.

    Avant, un dossier annulé alors qu'il attendait son tour était débité,
    remis « en cours » par-dessus son annulation, généré et livré.
    """
    job = _dossier()
    GenerationJob.objects.filter(pk=job.pk).update(status=statut)
    lances: list[str] = []
    monkeypatch.setattr(tasks, "run_generation_job", lambda j: lances.append(str(j.id)))

    tasks.run_generation_job_task(str(job.id))

    assert lances == []
    job.refresh_from_db()
    assert job.status == statut


def test_un_dossier_en_attente_est_bien_produit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contre-épreuve : la garde ne bloque pas le lancement normal."""
    job = _dossier()
    lances: list[str] = []
    monkeypatch.setattr(tasks, "run_generation_job", lambda j: lances.append(str(j.id)))

    tasks.run_generation_job_task(str(job.id))

    assert lances == [str(job.id)]


# ── 2. Résilier arrête le prélèvement ───────────────────────────────────────


def _abonne_par_carte(reference: str = "sub_audit") -> Any:
    organisation = _organisation()
    abonnement = services.souscrire(organisation, _formule(), doter_immediatement=False)
    abonnement.reference_paiement = reference
    abonnement.save(update_fields=["reference_paiement", "updated_at"])
    return organisation


def test_resilier_arrete_le_prelevement_chez_le_prestataire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organisation = _abonne_par_carte()
    arretes: list[str] = []

    def arreter(reference: str) -> str:
        arretes.append(reference)
        return ""

    monkeypatch.setattr(stripe_api, "arreter_le_renouvellement", arreter)

    assert services.resilier(organisation, motif="demande de la cliente") == 1

    assert arretes == ["sub_audit"]


def test_si_le_prestataire_refuse_rien_n_est_resilie(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un statut « résilié » posé sur un prélèvement qui continue est le défaut."""
    organisation = _abonne_par_carte()

    def refuser(reference: str) -> str:
        raise stripe_api.PaiementIndisponible("Stripe ne répond pas.")

    monkeypatch.setattr(stripe_api, "arreter_le_renouvellement", refuser)

    with pytest.raises(services.ResiliationImpossibleError):
        services.resilier(organisation, motif="demande de la cliente")

    assert AbonnementOrganisation.objects.filter(
        organisation=organisation, statut=StatutAbonnement.ACTIF,
    ).count() == 1


def test_un_abonnement_sans_carte_se_resilie_sans_appeler_personne(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contre-épreuve : un abonnement posé à la main n'a rien à arrêter ailleurs."""
    organisation = _organisation()
    services.souscrire(organisation, _formule(), doter_immediatement=False)
    monkeypatch.setattr(
        stripe_api, "arreter_le_renouvellement",
        lambda ref: pytest.fail("aucun prélèvement à arrêter"),
    )

    assert services.resilier(organisation, motif="compte d'essai") == 1


def test_une_facture_ne_rouvre_pas_un_abonnement_resilie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organisation = _abonne_par_carte()
    monkeypatch.setattr(stripe_api, "arreter_le_renouvellement", lambda ref: "")
    services.resilier(organisation, motif="demande de la cliente")

    with pytest.raises(abonnements.EvenementInexploitable, match="RÉSILIÉ"):
        abonnements.assurer_abonnement(
            organisation_id=str(organisation.id),
            formule_code=_formule().code,
            reference_stripe="sub_audit",
        )

    assert not AbonnementOrganisation.objects.filter(
        organisation=organisation, statut=StatutAbonnement.ACTIF,
    ).exists()


def test_une_nouvelle_souscription_s_ouvre_toujours(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contre-épreuve : revenir après une résiliation crée un AUTRE abonnement
    Stripe, que rien ne bloque."""
    organisation = _abonne_par_carte()
    monkeypatch.setattr(stripe_api, "arreter_le_renouvellement", lambda ref: "")
    services.resilier(organisation, motif="demande de la cliente")

    _, cree = abonnements.assurer_abonnement(
        organisation_id=str(organisation.id),
        formule_code=_formule().code,
        reference_stripe="sub_nouveau",
    )

    assert cree is True


# ── 3. Un événement Stripe renvoyé après un échec est retraité ──────────────


def _noter_dans(traites: list[str]) -> Any:
    """Un traitement d'événement qui réussit, et note l'identifiant reçu."""

    def traiter(evenement: dict[str, Any]) -> str:
        traites.append(str(evenement["id"]))
        return "ok"

    return traiter


def _poster(charge: dict[str, Any]) -> Any:
    corps = json.dumps(charge).encode("utf-8")
    horodatage = int(time.time())
    empreinte = hmac.new(
        SECRET.encode("utf-8"), f"{horodatage}.".encode() + corps, hashlib.sha256,
    ).hexdigest()
    return Client().post(
        "/webhooks/stripe/", data=corps, content_type="application/json",
        headers={"Stripe-Signature": f"t={horodatage},v1={empreinte}"},
    )


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET)
def test_un_evenement_en_echec_est_retraite_a_son_renvoi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le prélèvement est encaissé, le traitement échoue, Stripe renvoie : avant,
    le renvoi était répondu « doublon » et la dotation n'arrivait jamais."""
    evenement = {"id": f"evt_{uuid.uuid4().hex[:16]}", "type": "invoice.paid",
                 "data": {"object": {"id": "in_audit"}}}
    traites: list[str] = []

    def tomber(evt: dict[str, Any]) -> str:
        raise RuntimeError("base injoignable")

    monkeypatch.setattr("paiement.vues.traiter", tomber)
    assert _poster(evenement).status_code == 500

    monkeypatch.setattr("paiement.vues.traiter", _noter_dans(traites))
    reponse = _poster(evenement)

    assert reponse.status_code == 200
    assert traites == [evenement["id"]]
    assert WebhookEvent.objects.get(event_id=evenement["id"]).status == WebhookStatus.PROCESSED


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET)
def test_un_evenement_reussi_n_est_pas_rejoue(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contre-épreuve : la garde d'origine tient."""
    evenement = {"id": f"evt_{uuid.uuid4().hex[:16]}", "type": "invoice.paid",
                 "data": {"object": {"id": "in_audit"}}}
    traites: list[str] = []
    monkeypatch.setattr("paiement.vues.traiter", _noter_dans(traites))

    _poster(evenement)
    reponse = _poster(evenement)

    assert reponse.json().get("doublon") is True
    assert len(traites) == 1


def test_un_evenement_reste_accepte_trop_longtemps_est_a_retraiter() -> None:
    """Le processus est mort en le traitant — pendant un déploiement, par exemple."""
    recu = record_webhook_event(
        provider=IntegrationProvider.STRIPE, event_id="evt_perdu", payload={"a": 1},
        retraiter_les_echecs=True,
    )
    WebhookEvent.objects.filter(pk=recu.event.pk).update(
        updated_at=timezone.now() - DELAI_D_UN_TRAITEMENT_PERDU - timedelta(minutes=1),
    )

    rejoue = record_webhook_event(
        provider=IntegrationProvider.STRIPE, event_id="evt_perdu", payload={"a": 1},
        retraiter_les_echecs=True,
    )

    assert rejoue.is_duplicate and rejoue.a_retraiter


def test_un_evenement_en_cours_de_traitement_n_est_pas_pris_deux_fois() -> None:
    """Contre-épreuve : deux livraisons simultanées du même événement."""
    record_webhook_event(
        provider=IntegrationProvider.STRIPE, event_id="evt_vif", payload={"a": 1},
        retraiter_les_echecs=True,
    )

    second = record_webhook_event(
        provider=IntegrationProvider.STRIPE, event_id="evt_vif", payload={"a": 1},
        retraiter_les_echecs=True,
    )

    assert second.is_duplicate and not second.a_retraiter
    assert WebhookEvent.objects.get(event_id="evt_vif").status == WebhookStatus.ACCEPTED


# ── 4. Un crédit remboursé revient tel qu'il est parti ──────────────────────


def test_un_credit_rembourse_garde_l_etude_pour_laquelle_il_a_ete_paye() -> None:
    organisation = _organisation()
    credits.crediter(
        organisation, 1, motif="Achat à l'unité", type_mouvement=TypeMouvement.ACHAT,
        reference="cs_achat", auteur="stripe", livrable=CS,
    )
    credits.debiter(organisation, 1, reference="job-1", motif="Étude lancée", livrable=CS)

    credits.rembourser(organisation, reference="job-1", motif="Génération en échec")

    assert credits.droits_par_livrable(organisation) == {str(CS): 1}


# ── 5. Un plafond lu est un plafond compté ──────────────────────────────────


def test_les_ouvertures_de_paiement_publiques_sont_comptees(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`depasse` était interrogé, `enregistrer` jamais appelé : le compteur
    restait à zéro."""
    from organisations import vues_publiques

    offre = Offer.objects.create(
        name="Étude", slug="etude-plafond", deliverable_type=CS,
        prix_unitaire_cents=8_900, is_active=True,
    )

    class _Session:
        adresse = "https://paiement.exemple/cs_test"

    monkeypatch.setattr(stripe_api, "creer_paiement_de_livrable", lambda **k: _Session())
    comptes: list[Any] = []
    monkeypatch.setattr(
        limitation, "enregistrer", lambda plafond, cle: comptes.append(plafond),
    )

    reponse = Client().post(
        "/api/public/acheter/", data={"livrable": offre.slug},
        content_type="application/json",
    )

    assert reponse.status_code == 200
    assert comptes == [vues_publiques.PAIEMENTS_PAR_HEURE]


# ── 6. La relecture finale : vivante, et capable de rattraper ───────────────


def test_la_relecture_resout_son_client_avant_de_rattraper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La production appelle `relire_avant_envoi(job)` sans client. Le rattrapage
    recevait donc `None`, plantait sur `None.complete_structured`, et notait le
    chapitre « perdu » sans l'avoir tenté."""
    job = _dossier()
    recus: list[Any] = []
    monkeypatch.setattr(
        "documents.livrable_word.chaine_word_active", lambda job: True,
    )

    def espion(job: Any, rapport: Any, *, client: Any = None) -> None:
        recus.append(client)
        raise RuntimeError("arrêt du test après le rattrapage")

    monkeypatch.setattr(controle_final, "_refaire_les_chapitres_manquants", espion)

    with pytest.raises(RuntimeError, match="arrêt du test"):
        controle_final.relire_et_corriger(job)

    assert recus and recus[0] is not None


def test_le_battement_remet_l_horloge_du_gardien_a_zero() -> None:
    job = _dossier()
    GenerationJob.objects.filter(pk=job.pk).update(
        updated_at=timezone.now() - timedelta(hours=1),
    )

    controle_final.battement(job)

    job.refresh_from_db()
    assert timezone.now() - job.updated_at < timedelta(minutes=1)


def test_le_gardien_n_interrompt_pas_une_relecture_qui_bat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Terminé depuis une heure, relecture « en cours », mais vivante : rien ne
    part. Avant, le document partait chez le client au milieu de sa correction."""
    job = _dossier()
    GenerationJob.objects.filter(pk=job.pk).update(
        status=JobStatus.DONE, controle_final={"motif_d_arret": "en cours"},
        updated_at=timezone.now() - timedelta(hours=1),
    )
    livres: list[str] = []
    monkeypatch.setattr(tasks, "_livrer", lambda j: livres.append(str(j.id)))
    monkeypatch.setattr(tasks, "_verdict_sans_risque", lambda j: None)

    controle_final.battement(job)

    assert tasks.livrer_les_dossiers_oublies() == 0
    assert livres == []


def test_le_gardien_reprend_une_relecture_morte_une_seule_fois(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contre-épreuve, et le second défaut : la trace restée « en cours » faisait
    reprendre le même dossier toutes les dix minutes."""
    job = _dossier()
    GenerationJob.objects.filter(pk=job.pk).update(
        status=JobStatus.DONE, controle_final={"motif_d_arret": "en cours"},
        updated_at=timezone.now() - timedelta(hours=1),
    )
    livres: list[str] = []
    monkeypatch.setattr(tasks, "_livrer", lambda j: livres.append(str(j.id)))
    monkeypatch.setattr(tasks, "_verdict_sans_risque", lambda j: None)

    assert tasks.livrer_les_dossiers_oublies() == 1
    GenerationJob.objects.filter(pk=job.pk).update(
        updated_at=timezone.now() - timedelta(hours=1),
    )
    assert tasks.livrer_les_dossiers_oublies() == 0

    assert livres == [str(job.id)]


# ── 7. Le document n'est pas montré pendant qu'on le corrige ────────────────


def test_un_document_en_relecture_n_est_ni_pret_ni_telechargeable() -> None:
    job = _dossier()
    GenerationJob.objects.filter(pk=job.pk).update(
        status=JobStatus.DONE, controle_final={"motif_d_arret": "en cours"},
    )
    job.refresh_from_db()

    etat = suivi.en_dict(job)

    assert suivi.relecture_en_cours(job) is True
    assert etat["fichiers"] == []
    assert etat["message"] == suivi.MESSAGE_RELECTURE
    assert etat["progression"] < 100


def test_une_relecture_terminee_ne_cache_rien() -> None:
    """Contre-épreuve."""
    job = _dossier()
    GenerationJob.objects.filter(pk=job.pk).update(
        status=JobStatus.DONE,
        controle_final={"motif_d_arret": "aucune anomalie réparable", "passes": 1},
    )
    job.refresh_from_db()

    assert suivi.relecture_en_cours(job) is False


# ── 8. Un paiement, un versement — et seulement une fois encaissé ───────────


def _session_de_credits(organisation: Any, *, payee: bool = True) -> dict[str, Any]:
    return {
        "id": f"cs_{uuid.uuid4().hex[:16]}",
        "status": "complete",
        "payment_status": "paid" if payee else "unpaid",
        "metadata": {
            "achat": "credits",
            "organisation_id": str(organisation.id),
            "quantite": "3",
        },
    }


def test_verser_un_achat_verrouille_le_portefeuille_avant_de_regarder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le webhook et la page de retour arrivent ensemble : sans verrou, les deux
    lisent « pas encore versé » et versent. Le verrou est demandé AVANT la
    lecture — c'est ce qui met la seconde arrivée derrière la première.

    SQLite n'exécute pas le verrou ; ce test tient donc sa PLACE dans la
    séquence, que la base de production arbitre.
    """
    from organisations.models import MouvementCredit, PortefeuilleCredits

    organisation = _organisation()
    sequence: list[str] = []
    verrou = PortefeuilleCredits.objects.select_for_update

    def espion(*args: Any, **kwargs: Any) -> Any:
        sequence.append("verrou")
        return verrou(*args, **kwargs)

    lire = MouvementCredit.objects.filter

    def lecture(*args: Any, **kwargs: Any) -> Any:
        if "reference" in kwargs:
            sequence.append("lecture")
        return lire(*args, **kwargs)

    monkeypatch.setattr(PortefeuilleCredits.objects, "select_for_update", espion)
    monkeypatch.setattr(MouvementCredit.objects, "filter", lecture)

    credits.verser_un_achat(organisation, 1, reference="cs_course", motif="Achat à l'unité")

    assert sequence[:2] == ["verrou", "lecture"]


def test_le_meme_paiement_ne_se_verse_qu_une_fois() -> None:
    organisation = _organisation()

    premier = credits.verser_un_achat(organisation, 2, reference="cs_une_fois", motif="Achat")
    second = credits.verser_un_achat(organisation, 2, reference="cs_une_fois", motif="Achat")

    assert premier is not None and second is None
    assert credits.solde(organisation) == 2


def test_un_achat_de_credits_non_encaisse_ne_verse_rien() -> None:
    """Un prélèvement SEPA termine la session « unpaid ». Avant, les crédits
    — pérennes — étaient versés quand même."""
    organisation = _organisation()

    verdict = abonnements.sur_session_terminee(_session_de_credits(organisation, payee=False))

    assert "attente" in verdict
    assert credits.solde(organisation) == 0


def test_la_confirmation_differee_verse_l_achat() -> None:
    """Contre-épreuve, et l'autre moitié du défaut : personne n'écoutait
    l'événement qui annonce l'encaissement."""
    organisation = _organisation()
    session = _session_de_credits(organisation, payee=False)
    abonnements.sur_session_terminee(session)

    verdict = abonnements.traiter({
        "id": "evt_confirmation",
        "type": "checkout.session.async_payment_succeeded",
        "data": {"object": {**session, "payment_status": "paid"}},
    })

    assert verdict == "3 credits achetes"
    assert credits.solde(organisation) == 3


def test_un_achat_encaisse_tout_de_suite_est_verse_tout_de_suite() -> None:
    """Contre-épreuve : la carte bancaire, le cas de tous les jours."""
    organisation = _organisation()

    verdict = abonnements.sur_session_terminee(_session_de_credits(organisation))

    assert verdict == "3 credits achetes"
    assert credits.solde(organisation) == 3


def test_une_souscription_s_ouvre_sans_encaissement_immediat() -> None:
    """Contre-épreuve : la garde ne vaut que pour un ACHAT. Une souscription
    peut se terminer sans paiement immédiat ; c'est sa facture qui la dote."""
    organisation = _organisation()
    session = {
        "id": "cs_souscription", "status": "complete", "payment_status": "unpaid",
        "subscription": "sub_sans_encaissement",
        "metadata": {"organisation_id": str(organisation.id), "formule_code": _formule().code},
    }

    assert abonnements.sur_session_terminee(session) == "abonnement ouvert"


# ── 9. La première facture se lit, où que Stripe range nos métadonnées ──────


@pytest.mark.parametrize("rangement", ["subscription_details", "parent"])
def test_une_facture_arrivee_avant_la_session_ouvre_l_abonnement(rangement: str) -> None:
    """Une facture ne porte pas nos métadonnées dans SON `metadata`, qui est
    vide : elles sont dans `subscription_details` (et sous `parent` depuis
    2025). Le lecteur ne regardait que le premier — la première facture, si
    elle précédait la session, était rejetée « sans organisation identifiable ».

    Les doublures des autres tests rangeaient les métadonnées là où Stripe ne
    les met jamais : ils passaient sur une forme qui n'existe pas (règle 7).
    """
    organisation = _organisation()
    nos_metadonnees = {
        "organisation_id": str(organisation.id), "formule_code": _formule().code,
    }
    details: dict[str, Any] = {"subscription_details": {"metadata": nos_metadonnees}}
    facture: dict[str, Any] = {
        "id": "in_premiere", "subscription": "sub_premiere", "metadata": {},
        **(details if rangement == "subscription_details" else {"parent": details}),
    }

    abonnements.sur_facture_payee(facture)

    assert AbonnementOrganisation.objects.filter(
        organisation=organisation, statut=StatutAbonnement.ACTIF,
        reference_paiement="sub_premiere",
    ).exists()


def test_une_facture_vraiment_anonyme_reste_refusee() -> None:
    """Contre-épreuve : aucune métadonnée nulle part, aucun abonnement connu."""
    with pytest.raises(abonnements.EvenementInexploitable):
        abonnements.sur_facture_payee(
            {"id": "in_anonyme", "subscription": "sub_inconnu", "metadata": {}}
        )


def test_la_fin_prononcee_par_le_prestataire_ne_lui_redemande_rien(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stripe vient de clore l'abonnement : lui demander de l'arrêter est refusé,
    et ce refus ne doit pas laisser l'abonnement ACTIF chez nous."""
    organisation = _abonne_par_carte("sub_clos")
    monkeypatch.setattr(
        stripe_api, "arreter_le_renouvellement",
        lambda ref: pytest.fail("rien à arrêter : c'est Stripe qui a clos"),
    )

    verdict = abonnements.sur_abonnement_supprime({"id": "sub_clos"})

    assert verdict == "abonnement resilie"
    assert not AbonnementOrganisation.objects.filter(
        organisation=organisation, statut=StatutAbonnement.ACTIF,
    ).exists()


# ── 10. Une commande en production n'attend plus son formulaire ─────────────


def _commande_en_attente(suffixe: str, statut: str) -> IntakeSubmission:
    from orders.models import OrderStatus  # noqa: F401 — lisibilité des appels

    offre, _ = Offer.objects.get_or_create(
        slug="ec-audit", defaults={"name": "Étude de la concurrence", "deliverable_type": CS},
    )
    client = Customer.objects.create(email=f"etat-{suffixe}@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id=f"reprise-{suffixe}", customer=client, offer=offre, status=statut,
    )
    return IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "ateliers", "PAYS": "France", "PROJET": "État"},
    )


def test_une_reprise_ne_reste_pas_en_attente_de_formulaire() -> None:
    """51 commandes de production affichaient cet état avec un document produit :
    seules la livraison le faisait avancer, et une reprise « sans envoi » ne
    livre jamais."""
    from orders.models import OrderStatus

    soumission = _commande_en_attente("attente", OrderStatus.WAITING_INTAKE)

    bootstrap_generation_job(soumission)

    soumission.order.refresh_from_db()
    assert soumission.order.status == OrderStatus.PROCESSING


@pytest.mark.parametrize("statut", ["delivered", "cancelled", "failed"])
def test_un_etat_final_n_est_pas_reecrit(statut: str) -> None:
    """Contre-épreuve : recréer le dossier d'une commande close ne la rouvre pas."""
    soumission = _commande_en_attente(f"final-{statut}", statut)

    bootstrap_generation_job(soumission)

    soumission.order.refresh_from_db()
    assert soumission.order.status == statut


# ── 11. Un événement en cours n'est pas dit « reçu » ────────────────────────


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET)
def test_un_evenement_en_cours_de_traitement_n_est_pas_acquitte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un autre processus l'a pris — ou est mort en le traitant. Lui répondre
    200 arrêtait les renvois de Stripe : s'il était mort, rien n'était jamais
    versé. 409 : Stripe renvoie, et passé le délai le renvoi est retraité."""
    evenement = {"id": f"evt_{uuid.uuid4().hex[:16]}", "type": "invoice.paid",
                 "data": {"object": {"id": "in_audit"}}}
    record_webhook_event(
        provider=IntegrationProvider.STRIPE, event_id=str(evenement["id"]),
        payload=evenement, retraiter_les_echecs=True,
    )
    monkeypatch.setattr(
        "paiement.vues.traiter", lambda evt: pytest.fail("déjà pris par un autre processus"),
    )

    reponse = _poster(evenement)

    assert reponse.status_code == 409
    assert WebhookEvent.objects.get(event_id=evenement["id"]).status == WebhookStatus.ACCEPTED


def test_deux_renvois_d_un_echec_ne_le_reprennent_pas_tous_les_deux() -> None:
    """La reprise est une prise : le second renvoi trouve l'événement pris."""
    recu = record_webhook_event(
        provider=IntegrationProvider.STRIPE, event_id="evt_course", payload={"a": 1},
        retraiter_les_echecs=True,
    )
    WebhookEvent.objects.filter(pk=recu.event.pk).update(status=WebhookStatus.FAILED)

    premier = record_webhook_event(
        provider=IntegrationProvider.STRIPE, event_id="evt_course", payload={"a": 1},
        retraiter_les_echecs=True,
    )
    second = record_webhook_event(
        provider=IntegrationProvider.STRIPE, event_id="evt_course", payload={"a": 1},
        retraiter_les_echecs=True,
    )

    assert premier.a_retraiter is True
    assert second.a_retraiter is False


def test_les_commandes_deja_la_sont_remises_d_accord() -> None:
    """La migration de reprise : celles qui ont un dossier quittent l'attente,
    celles qui attendent vraiment leur formulaire y restent."""
    import importlib

    from django.apps import apps as applications

    from orders.models import OrderStatus

    avec_dossier = _commande_en_attente("reprise-ancienne", OrderStatus.WAITING_INTAKE)
    bootstrap_generation_job(avec_dossier)
    Order.objects.filter(pk=avec_dossier.order_id).update(status=OrderStatus.WAITING_INTAKE)
    livree = _commande_en_attente("deja-livree", OrderStatus.DELIVERED)
    bootstrap_generation_job(livree)
    sans_dossier = _commande_en_attente("attend-vraiment", OrderStatus.WAITING_INTAKE)

    reprise = importlib.import_module(
        "orders.migrations.0006_les_commandes_en_production_quittent_l_attente"
    )
    reprise.sortir_de_l_attente(applications, None)
    reprise.sortir_de_l_attente(applications, None)  # rejouable sans effet

    etats = {
        s.order.systeme_order_id: Order.objects.get(pk=s.order_id).status
        for s in (avec_dossier, livree, sans_dossier)
    }
    assert etats == {
        "reprise-reprise-ancienne": OrderStatus.PROCESSING,
        "reprise-deja-livree": OrderStatus.DELIVERED,
        "reprise-attend-vraiment": OrderStatus.WAITING_INTAKE,
    }


# ── 12. Ce qui ne repart pas tout seul repart quand on le décide ────────────


def test_la_console_demande_le_renvoi_les_chemins_automatiques_non(
    client_admin: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`job_redeliver` est une décision prise à l'écran : il pose
    `renvoi_voulu`. La fin de génération et le gardien passent par `_livrer`,
    qui ne le pose jamais — c'est ce qui les empêche d'écrire deux fois au
    client."""
    from delivery import tasks as livraison

    job = _dossier("renvoi")
    GenerationJob.objects.filter(pk=job.pk).update(status=JobStatus.DONE)
    job.refresh_from_db()
    appels: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    monkeypatch.setattr(
        livraison.deliver_job_task, "delay", lambda *a, **k: appels.append((a, k)),
    )

    reponse = client_admin.post(f"/api/dashboard/jobs/{job.id}/redeliver/")
    tasks._livrer(job)

    assert reponse.status_code == 202
    assert appels == [
        ((str(job.id),), {"renvoi_voulu": True}),
        ((str(job.id),), {}),
    ]


# ── 13. Recommander une étude en échec la relance ───────────────────────────


def test_une_etude_en_echec_recommandee_repart(monkeypatch: pytest.MonkeyPatch) -> None:
    """Porte finale du 19/11/2026. `creer_commande` rend à la cliente son
    dossier en échec ; la tâche, elle, ne prend qu'un dossier en attente. La
    vue répondait « acceptée » et rien ne repartait. Le test va jusqu'à la
    TÂCHE : celui qui s'arrêtait à la mise en file restait vert."""
    from organisations import commandes

    job = _dossier("echec-recommande")
    GenerationJob.objects.filter(pk=job.pk).update(status=JobStatus.FAILED)
    job.refresh_from_db()
    produits: list[str] = []
    monkeypatch.setattr(tasks, "run_generation_job", lambda j: produits.append(str(j.id)))
    monkeypatch.setattr(
        tasks.run_generation_job_task, "delay",
        lambda job_id: tasks.run_generation_job_task(job_id),
    )

    commandes.lancer(job)

    assert produits == [str(job.id)]

"""Suivi de production, invitation de collaborateurs, actions d'administration.

Trois exigences vérifiées ici :

- **§9.4** : le client voit où en est son étude, avec « un message clair en cas
  d'incident, sans jargon technique » ;
- **§9.1** : il invite et révoque des collaborateurs ;
- **§10.2** : EVKHA dote, suspend et traite les demandes **sans passer par
  l'administration Django**.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.models import (
    ChapterGeneration,
    ChapterStatus,
    GenerationJob,
    JobStatus,
    SocleDonnees,
    SocleStatut,
)
from intake.models import IntakeStatus, IntakeSubmission
from orders.models import Order
from organisations import credits, services, suivi
from organisations.authentification import (
    compte_du_jeton,
    creer_compte,
    ouvrir_session,
)
from organisations.models import (
    DemandeCommerciale,
    Formule,
    MembreOrganisation,
    Organisation,
    RoleOrganisation,
    StatutDemande,
    StatutOrganisation,
    TypeDemande,
    TypeMouvement,
)
from tests.conftest import JETON_ADMIN

pytestmark = pytest.mark.django_db

MOT_DE_PASSE = "mot-de-passe-de-test-2026"


class Abonne:
    def __init__(self, nom: str, email: str, role: str = RoleOrganisation.PROPRIETAIRE):
        self.contact = Customer.objects.create(email=email)
        self.organisation = services.creer_organisation(
            raison_sociale=nom, contact=self.contact
        )
        if role != RoleOrganisation.PROPRIETAIRE:
            membre = self.organisation.membres.get(customer=self.contact)
            membre.role = role
            membre.save(update_fields=["role"])
        creer_compte(self.contact, mot_de_passe=MOT_DE_PASSE)
        self.jeton, _ = ouvrir_session(email, MOT_DE_PASSE)

    @property
    def entetes(self) -> dict[str, str]:
        return {"authorization": f"Bearer {self.jeton}"}


@pytest.fixture
def abonne() -> Abonne:
    return Abonne("Agence Lumen", "lumen-suivi@example.com")


@pytest.fixture
def autre() -> Abonne:
    return Abonne("Agence Rivage", "rivage-suivi@example.com")


@pytest.fixture
def api() -> Client:
    # L'administration est protegee, y compris dans la suite : le client
    # de test presente le jeton comme le fera le navigateur de l'equipe.
    return Client(HTTP_AUTHORIZATION=f"Bearer {JETON_ADMIN}")


def charge(reponse: Any) -> dict[str, Any]:
    donnees: dict[str, Any] = json.loads(reponse.content)
    return donnees


def _job(organisation: Organisation, suffixe: str) -> GenerationJob:
    from generation.services import bootstrap_generation_job

    offre = Offer.objects.create(
        name="Étude de marché",
        slug=f"em-{suffixe}",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email=f"c-{suffixe}@example.com")
    commande = Order.objects.create(
        systeme_order_id=f"order-{suffixe}",
        customer=client,
        offer=offre,
        organisation=organisation,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "test", "PAYS": "France"},
    )
    return bootstrap_generation_job(soumission)


# ── Suivi de production (§9.4) ───────────────────────────────────────────────


def test_le_suivi_expose_les_quatre_etapes(abonne: Abonne) -> None:
    job = _job(abonne.organisation, "etapes")
    cles = [etape["cle"] for etape in suivi.en_dict(job)["etapes"]]
    assert cles == ["socle", "chapitres", "verification", "rendu"]


def test_aucun_jargon_technique_ne_parvient_au_client(abonne: Abonne) -> None:
    """« intervention_requise » ne veut rien dire pour un client."""
    job = _job(abonne.organisation, "jargon")
    GenerationJob.objects.filter(pk=job.pk).update(
        status=JobStatus.INTERVENTION_REQUISE,
        error_message="SocleGenerationError: tentative 3/3 — schema mismatch",
    )
    job.refresh_from_db()
    donnees = suivi.en_dict(job)

    assert "intervention_requise" not in donnees["message"]
    assert "SocleGenerationError" not in json.dumps(donnees)
    assert "schema" not in json.dumps(donnees)
    assert "notre équipe" in donnees["message"].lower()


def test_la_progression_est_comptee_et_non_simulee(abonne: Abonne) -> None:
    """Une barre qui avance toute seule se trahit à 99 %."""
    job = _job(abonne.organisation, "progression")
    assert suivi.progression(job) == 0

    SocleDonnees.objects.create(
        job=job, statut=SocleStatut.VALIDE, contenu={"donnees": [{"id": "x"}]}
    )
    apres_socle = suivi.progression(job)
    assert apres_socle == 15

    chapitres = ChapterGeneration.objects.filter(job=job)
    total = chapitres.count()
    assert total > 0
    for chapitre in chapitres[: total // 2]:
        chapitre.status = ChapterStatus.DONE
        chapitre.save(update_fields=["status"])

    assert suivi.progression(job) > apres_socle
    assert suivi.progression(job) < 100


def test_une_etude_terminee_est_a_cent_pour_cent(abonne: Abonne) -> None:
    job = _job(abonne.organisation, "termine")
    GenerationJob.objects.filter(pk=job.pk).update(status=JobStatus.DONE)
    job.refresh_from_db()
    assert suivi.progression(job) == 100
    assert all(etape.etat == "fait" for etape in suivi.etapes(job))


def test_un_echec_fige_l_etape_en_cours(abonne: Abonne) -> None:
    """La laisser « en cours » ferait tourner l'indicateur indéfiniment."""
    job = _job(abonne.organisation, "echec")
    GenerationJob.objects.filter(pk=job.pk).update(status=JobStatus.FAILED)
    job.refresh_from_db()
    etats = {etape.cle: etape.etat for etape in suivi.etapes(job)}
    assert "en_cours" not in etats.values()


def test_aucune_duree_n_est_annoncee_hors_production(abonne: Abonne) -> None:
    """Une estimation fausse est pire que pas d'estimation."""
    job = _job(abonne.organisation, "duree")
    GenerationJob.objects.filter(pk=job.pk).update(status=JobStatus.DONE)
    job.refresh_from_db()
    assert suivi.en_dict(job)["duree_estimee_minutes"] is None


def test_le_suivi_est_cloisonne(api: Client, abonne: Abonne, autre: Abonne) -> None:
    """Un identifiant deviné ne donne accès à rien."""
    job = _job(autre.organisation, "cloisonne")
    reponse = api.get(f"/api/espace/livrables/{job.id}/", headers=abonne.entetes)
    assert reponse.status_code == 404


def test_le_suivi_de_son_etude_est_accessible(api: Client, abonne: Abonne) -> None:
    job = _job(abonne.organisation, "mien")
    reponse = api.get(f"/api/espace/livrables/{job.id}/", headers=abonne.entetes)
    assert reponse.status_code == 200
    assert charge(reponse)["id"] == str(job.id)


# ── Équipe (§9.1) ────────────────────────────────────────────────────────────


def _inviter(api: Client, abonne: Abonne, email: str, role: str) -> Any:
    return api.post(
        "/api/espace/equipe/inviter/",
        data=json.dumps({"email": email, "role": role}),
        content_type="application/json",
        headers=abonne.entetes,
    )


def test_un_proprietaire_invite_un_collaborateur(api: Client, abonne: Abonne) -> None:
    reponse = _inviter(api, abonne, "thomas@example.com", RoleOrganisation.MEMBRE)
    assert reponse.status_code == 201
    assert abonne.organisation.membres.filter(
        customer__email="thomas@example.com"
    ).exists()


def test_l_invitation_ne_donne_aucun_mot_de_passe_utilisable(
    api: Client, abonne: Abonne
) -> None:
    """Personne ne doit connaître le mot de passe d'un autre — intention conservée.

    Ce test exigeait auparavant qu'AUCUN compte ne soit créé. C'était le moyen
    retenu à l'époque, et il rendait l'invitation inopérante : sans compte,
    l'invité ne pouvait ni se connecter, ni s'inscrire — `refuser_si_deja_membre`
    lui répondait « cette adresse a déjà un compte » —, ni passer par Google.

    Le compte est désormais créé, avec un mot de passe **inutilisable**. La
    propriété qui compte est donc vérifiée directement, et elle est plus forte
    que l'ancienne : le compte existe, et il n'ouvre rien.
    """
    from organisations.authentification import (
        AuthentificationRefuseeError,
        ouvrir_session,
    )

    _inviter(api, abonne, "thomas@example.com", RoleOrganisation.MEMBRE)
    invite = Customer.objects.get(email="thomas@example.com")

    assert hasattr(invite, "compte"), "sans compte, l'invite ne peut rien faire"
    assert not invite.compte.user.has_usable_password()

    # Contre-épreuve : aucune saisie n'ouvre la session, pas même la chaîne
    # vide ni la valeur que Django inscrit pour un mot de passe inutilisable.
    for tentative in ("", "!", invite.compte.user.password):
        with pytest.raises(AuthentificationRefuseeError):
            ouvrir_session("thomas@example.com", tentative)


def test_l_invitation_envoie_un_lien_d_activation(
    api: Client, abonne: Abonne
) -> None:
    """L'écran promettait « EVKHA lui transmettra ses identifiants ».

    Personne ne transmettait rien : aucun envoi de courriel n'existait dans
    tout `backend/organisations/`. La fonctionnalité Équipe était décorative.
    """
    reponse = _inviter(api, abonne, "thomas@example.com", RoleOrganisation.MEMBRE)

    assert reponse.status_code == 201
    assert charge(reponse)["invitation_envoyee"] is True


def test_une_adresse_invalide_est_refusee(api: Client, abonne: Abonne) -> None:
    assert _inviter(api, abonne, "pas-un-email", "membre").status_code == 400


def test_un_role_inconnu_est_refuse(api: Client, abonne: Abonne) -> None:
    assert _inviter(api, abonne, "x@example.com", "super_admin").status_code == 400


def test_un_membre_ne_peut_pas_inviter(api: Client) -> None:
    membre = Abonne("Agence M", "m-inv@example.com", role=RoleOrganisation.MEMBRE)
    assert _inviter(api, membre, "x@example.com", "membre").status_code == 403


def test_une_personne_deja_rattachee_ailleurs_est_refusee(
    api: Client, abonne: Abonne, autre: Abonne
) -> None:
    """Le cloisonnement suppose un seul rattachement actif par personne."""
    reponse = _inviter(api, abonne, autre.contact.email, RoleOrganisation.MEMBRE)
    assert reponse.status_code == 409
    assert charge(reponse)["code"] == "deja_rattache"


def test_revoquer_coupe_aussi_les_sessions_ouvertes(
    api: Client, abonne: Abonne
) -> None:
    """Sans cela, « révoquer » ne révoquerait rien pendant deux semaines."""
    invite = Customer.objects.create(email="parti@example.com")
    membre = services.inviter_membre(
        abonne.organisation, invite, role=RoleOrganisation.MEMBRE
    )
    creer_compte(invite, mot_de_passe=MOT_DE_PASSE)
    jeton_invite, _ = ouvrir_session("parti@example.com", MOT_DE_PASSE)
    assert compte_du_jeton(jeton_invite) is not None

    reponse = api.post(
        f"/api/espace/equipe/{membre.id}/revoquer/", headers=abonne.entetes
    )
    assert reponse.status_code == 200
    assert compte_du_jeton(jeton_invite) is None


def test_le_dernier_proprietaire_ne_peut_pas_etre_revoque(
    api: Client, abonne: Abonne
) -> None:
    proprietaire = MembreOrganisation.objects.get(
        organisation=abonne.organisation, customer=abonne.contact
    )
    reponse = api.post(
        f"/api/espace/equipe/{proprietaire.id}/revoquer/", headers=abonne.entetes
    )
    assert reponse.status_code == 409


def test_revoquer_un_membre_d_une_autre_organisation_est_impossible(
    api: Client, abonne: Abonne, autre: Abonne
) -> None:
    cible = MembreOrganisation.objects.get(
        organisation=autre.organisation, customer=autre.contact
    )
    reponse = api.post(
        f"/api/espace/equipe/{cible.id}/revoquer/", headers=abonne.entetes
    )
    assert reponse.status_code == 404


# ── Actions d'administration (§10.2) ─────────────────────────────────────────


def _admin(api: Client, chemin: str, corps: dict[str, Any]) -> Any:
    return api.post(
        f"/api/dashboard{chemin}",
        data=json.dumps(corps, ensure_ascii=False),
        content_type="application/json",
    )


def test_doter_credite_reellement(api: Client, abonne: Abonne) -> None:
    reponse = _admin(
        api,
        f"/supervision/organisations/{abonne.organisation.id}/doter/",
        {"quantite": 5, "motif": "Geste commercial", "auteur": "evangeline"},
    )
    assert reponse.status_code == 201
    assert credits.solde(abonne.organisation) == 5


def test_une_dotation_sans_motif_est_refusee(api: Client, abonne: Abonne) -> None:
    """Un journal dont la moitié des lignes n'explique rien ne sert à personne."""
    reponse = _admin(
        api,
        f"/supervision/organisations/{abonne.organisation.id}/doter/",
        {"quantite": 5, "motif": "   "},
    )
    assert reponse.status_code == 400
    assert credits.solde(abonne.organisation) == 0


def test_une_dotation_enregistre_son_auteur(api: Client, abonne: Abonne) -> None:
    _admin(
        api,
        f"/supervision/organisations/{abonne.organisation.id}/doter/",
        {"quantite": 2, "motif": "Rattrapage", "auteur": "evangeline@evkha.fr"},
    )
    mouvement = abonne.organisation.portefeuille.mouvements.first()
    assert mouvement is not None
    assert mouvement.auteur == "evangeline@evkha.fr"


def test_une_dotation_d_abonnement_ne_peut_pas_etre_saisie_a_la_main(
    api: Client, abonne: Abonne
) -> None:
    """Elle passe par l'échéance, qui porte l'idempotence par période."""
    reponse = _admin(
        api,
        f"/supervision/organisations/{abonne.organisation.id}/doter/",
        {"quantite": 3, "motif": "Dotation", "type": TypeMouvement.DOTATION},
    )
    assert reponse.status_code == 400


def test_suspendre_puis_reactiver(api: Client, abonne: Abonne) -> None:
    chemin = f"/supervision/organisations/{abonne.organisation.id}/statut/"
    assert _admin(api, chemin, {"action": "suspendre", "motif": "Impayé"}).status_code == 200
    abonne.organisation.refresh_from_db()
    assert abonne.organisation.statut == StatutOrganisation.SUSPENDUE

    assert _admin(api, chemin, {"action": "reactiver"}).status_code == 200
    abonne.organisation.refresh_from_db()
    assert abonne.organisation.statut == StatutOrganisation.ACTIVE


def test_une_suspension_sans_motif_est_refusee(api: Client, abonne: Abonne) -> None:
    reponse = _admin(
        api,
        f"/supervision/organisations/{abonne.organisation.id}/statut/",
        {"action": "suspendre"},
    )
    assert reponse.status_code == 400
    abonne.organisation.refresh_from_db()
    assert abonne.organisation.statut == StatutOrganisation.ACTIVE


def test_accorder_des_credits_les_credite_reellement(
    api: Client, abonne: Abonne
) -> None:
    """Marquer « traitée » sans rien faire donnerait à EVKHA une liste propre et
    au client rien du tout."""
    demande = DemandeCommerciale.objects.create(
        organisation=abonne.organisation,
        type=TypeDemande.CREDITS_ADDITIONNELS,
        quantite=4,
    )
    reponse = _admin(
        api, f"/supervision/demandes/{demande.id}/traiter/", {"decision": "accorder"}
    )
    assert reponse.status_code == 200
    demande.refresh_from_db()
    assert demande.statut == StatutDemande.TRAITEE
    assert credits.solde(abonne.organisation) == 4


def test_accorder_un_changement_de_formule_souscrit_reellement(
    api: Client, abonne: Abonne
) -> None:
    formule = Formule.objects.create(
        libelle="Structure", code="structure", credits_par_echeance=10,
        prix_mensuel_cents=42_900,
    )
    demande = DemandeCommerciale.objects.create(
        organisation=abonne.organisation,
        type=TypeDemande.CHANGEMENT_FORMULE,
        formule_visee=formule,
    )
    assert _admin(
        api, f"/supervision/demandes/{demande.id}/traiter/", {"decision": "accorder"}
    ).status_code == 200
    assert abonne.organisation.abonnements.filter(
        statut="actif", formule=formule
    ).exists()


def test_un_refus_sans_raison_est_impossible(api: Client, abonne: Abonne) -> None:
    """La raison est affichée au client : la taire ne l'aide pas."""
    demande = DemandeCommerciale.objects.create(
        organisation=abonne.organisation,
        type=TypeDemande.CREDITS_ADDITIONNELS,
        quantite=2,
    )
    reponse = _admin(
        api, f"/supervision/demandes/{demande.id}/traiter/", {"decision": "refuser"}
    )
    assert reponse.status_code == 400
    demande.refresh_from_db()
    assert demande.statut == StatutDemande.OUVERTE


def test_un_refus_motive_est_enregistre(api: Client, abonne: Abonne) -> None:
    demande = DemandeCommerciale.objects.create(
        organisation=abonne.organisation,
        type=TypeDemande.CREDITS_ADDITIONNELS,
        quantite=2,
    )
    _admin(
        api,
        f"/supervision/demandes/{demande.id}/traiter/",
        {"decision": "refuser", "reponse": "Facture précédente impayée."},
    )
    demande.refresh_from_db()
    assert demande.statut == StatutDemande.REFUSEE
    assert "impayée" in demande.reponse
    assert credits.solde(abonne.organisation) == 0


def test_une_demande_deja_traitee_ne_peut_pas_l_etre_deux_fois(
    api: Client, abonne: Abonne
) -> None:
    """Sinon un double clic créditerait deux fois."""
    demande = DemandeCommerciale.objects.create(
        organisation=abonne.organisation,
        type=TypeDemande.CREDITS_ADDITIONNELS,
        quantite=3,
    )
    chemin = f"/supervision/demandes/{demande.id}/traiter/"
    assert _admin(api, chemin, {"decision": "accorder"}).status_code == 200
    assert _admin(api, chemin, {"decision": "accorder"}).status_code == 409
    assert credits.solde(abonne.organisation) == 3

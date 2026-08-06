"""Lot 4 — API de l'espace client : authentification et cloisonnement.

Le test le plus important de ce module n'est pas qu'une page s'affiche : c'est
qu'**une agence ne puisse jamais voir les données d'une autre**. Le dashboard
interne est protégé par un jeton PARTAGÉ ; si l'espace client avait suivi le
même modèle, chaque client aurait vu le portefeuille, les clients finaux et les
livrables de tous les autres.

Chaque point de terminaison est donc éprouvé trois fois :

1. sans jeton — doit refuser ;
2. avec le jeton d'une AUTRE organisation — doit ne rien montrer de la
   première ;
3. avec le bon jeton — doit fonctionner (la contre-épreuve, règle 6).
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.models import GenerationJob, JobStatus
from intake.models import IntakeStatus, IntakeSubmission
from orders.models import Order
from organisations import credits, services
from organisations.authentification import (
    AuthentificationRefuseeError,
    compte_du_jeton,
    creer_compte,
    fermer_session,
    ouvrir_session,
    revoquer_tous_les_jetons,
)
from organisations.models import (
    ClientFinal,
    Formule,
    MembreOrganisation,
    Organisation,
    RoleOrganisation,
)
from tests.aides_abonnement import abonner

pytestmark = pytest.mark.django_db

MOT_DE_PASSE = "mot-de-passe-de-test-2026"


class Agence:
    """Une organisation complète avec son compte connecté, pour les tests."""

    def __init__(self, nom: str, email: str, role: str = RoleOrganisation.PROPRIETAIRE):
        self.contact = Customer.objects.create(email=email, first_name=nom)
        self.organisation = services.creer_organisation(
            raison_sociale=nom, contact=self.contact
        )
        # L'espace est fermé à qui n'a rien payé : sans abonnement, chaque vue
        # répondrait 402. Aucun crédit versé, le solde reste à zéro.
        abonner(self.organisation)
        if role != RoleOrganisation.PROPRIETAIRE:
            membre = MembreOrganisation.objects.get(
                organisation=self.organisation, customer=self.contact
            )
            membre.role = role
            membre.save(update_fields=["role"])
        creer_compte(self.contact, mot_de_passe=MOT_DE_PASSE)
        self.jeton, _ = ouvrir_session(email, MOT_DE_PASSE)

    @property
    def entetes(self) -> dict[str, str]:
        """En-têtes au format `headers=`, pas les `HTTP_*` historiques.

        Le second passe par `**kwargs`, que le typage du client de test ne sait
        pas distinguer de ses propres paramètres.
        """
        return {"authorization": f"Bearer {self.jeton}"}


@pytest.fixture
def lumen() -> Agence:
    return Agence("Agence Lumen", "lumen@example.com")


@pytest.fixture
def rivage() -> Agence:
    return Agence("Agence Rivage", "rivage@example.com")


@pytest.fixture
def api() -> Client:
    return Client()


def charge(reponse: Any) -> dict[str, Any]:
    donnees: dict[str, Any] = json.loads(reponse.content)
    return donnees


# ── Authentification ─────────────────────────────────────────────────────────


def test_une_session_s_ouvre_avec_les_bons_identifiants(lumen: Agence) -> None:
    jeton, objet = ouvrir_session("lumen@example.com", MOT_DE_PASSE)
    assert jeton
    assert objet.valide
    assert compte_du_jeton(jeton) is not None


def test_un_mauvais_mot_de_passe_est_refuse(lumen: Agence) -> None:
    with pytest.raises(AuthentificationRefuseeError):
        ouvrir_session("lumen@example.com", "faux")


def test_un_email_inconnu_est_refuse_avec_le_meme_message(lumen: Agence) -> None:
    """Distinguer les deux cas renseignerait un attaquant sur les comptes existants."""
    with pytest.raises(AuthentificationRefuseeError) as inconnu:
        ouvrir_session("jamais-vu@example.com", MOT_DE_PASSE)
    with pytest.raises(AuthentificationRefuseeError) as mauvais:
        ouvrir_session("lumen@example.com", "faux")
    assert str(inconnu.value) == str(mauvais.value)


def test_le_jeton_n_est_pas_stocke_en_clair(lumen: Agence) -> None:
    """Une fuite de la base ne doit livrer aucun jeton utilisable."""
    from organisations.models import JetonAcces

    condensats = list(JetonAcces.objects.values_list("condensat", flat=True))
    assert condensats
    assert lumen.jeton not in condensats
    assert all(len(c) == 64 for c in condensats)


def test_un_jeton_revoque_ne_vaut_plus_rien(lumen: Agence) -> None:
    assert fermer_session(lumen.jeton)
    assert compte_du_jeton(lumen.jeton) is None


def test_revoquer_tous_les_jetons_deconnecte_partout(lumen: Agence) -> None:
    """À appeler sur changement de mot de passe : une session ouverte survivrait sinon."""
    second, _ = ouvrir_session("lumen@example.com", MOT_DE_PASSE)
    compte = compte_du_jeton(lumen.jeton)
    assert compte is not None
    assert revoquer_tous_les_jetons(compte) == 2
    assert compte_du_jeton(lumen.jeton) is None
    assert compte_du_jeton(second) is None


def test_un_jeton_expire_ne_vaut_plus_rien(lumen: Agence) -> None:
    from datetime import timedelta

    from django.utils import timezone

    from organisations.models import JetonAcces

    JetonAcces.objects.all().update(expire_le=timezone.now() - timedelta(seconds=1))
    assert compte_du_jeton(lumen.jeton) is None


@pytest.mark.parametrize("jeton_fourni", ["", "n-importe-quoi", "0" * 64])
def test_un_jeton_invalide_ne_vaut_rien(jeton_fourni: str) -> None:
    assert compte_du_jeton(jeton_fourni) is None


def test_la_connexion_par_l_api_renvoie_un_jeton(lumen: Agence, api: Client) -> None:
    reponse = api.post(
        "/api/espace/connexion/",
        data=json.dumps({"email": "lumen@example.com", "mot_de_passe": MOT_DE_PASSE}),
        content_type="application/json",
    )
    assert reponse.status_code == 200
    assert charge(reponse)["jeton"]


def test_la_connexion_refusee_renvoie_401(lumen: Agence, api: Client) -> None:
    reponse = api.post(
        "/api/espace/connexion/",
        data=json.dumps({"email": "lumen@example.com", "mot_de_passe": "faux"}),
        content_type="application/json",
    )
    assert reponse.status_code == 401


def test_la_deconnexion_reussit_meme_sur_un_jeton_mort(api: Client) -> None:
    """Signaler « ce jeton n'existait pas » n'aiderait personne."""
    reponse = api.post(
        "/api/espace/deconnexion/", headers={"authorization": "Bearer inexistant"}
    )
    assert reponse.status_code == 204


# ── Aucun accès sans jeton ───────────────────────────────────────────────────

_POINTS = [
    "/api/espace/moi/",
    "/api/espace/credits/",
    "/api/espace/clients-finaux/",
    "/api/espace/livrables/",
    "/api/espace/equipe/",
]


@pytest.mark.parametrize("chemin", _POINTS)
def test_aucun_point_n_est_accessible_sans_jeton(api: Client, chemin: str) -> None:
    """Échec fermé : aucun chemin ne renvoie « autorisé » par défaut."""
    assert api.get(chemin).status_code == 401


@pytest.mark.parametrize("chemin", _POINTS)
def test_un_jeton_valide_ouvre_chaque_point(
    api: Client, lumen: Agence, chemin: str
) -> None:
    """Contre-épreuve : le garde-fou ne bloque pas un accès légitime."""
    assert api.get(chemin, headers=lumen.entetes).status_code == 200


def test_un_compte_sans_organisation_est_refuse(api: Client) -> None:
    """Un compte existe, mais aucun rattachement : rien à montrer, pas 500."""
    orphelin = Customer.objects.create(email="orphelin@example.com")
    creer_compte(orphelin, mot_de_passe=MOT_DE_PASSE)
    jeton_orphelin, _ = ouvrir_session("orphelin@example.com", MOT_DE_PASSE)
    reponse = api.get(
        "/api/espace/moi/", headers={"authorization": f"Bearer {jeton_orphelin}"}
    )
    assert reponse.status_code == 403
    assert charge(reponse)["code"] == "sans_organisation"


def test_un_membre_revoque_perd_l_acces_a_l_api(api: Client, lumen: Agence) -> None:
    """Le jeton reste valide mais le rattachement ne l'est plus."""
    membre = MembreOrganisation.objects.get(organisation=lumen.organisation)
    services.revoquer_membre  # noqa: B018 - garde-fou du dernier propriétaire
    membre.revoque_le = membre.created_at
    membre.save(update_fields=["revoque_le"])
    assert api.get("/api/espace/moi/", headers=lumen.entetes).status_code == 403


# ── Cloisonnement : le cœur du lot ───────────────────────────────────────────


def test_moi_ne_renvoie_que_sa_propre_organisation(
    api: Client, lumen: Agence, rivage: Agence
) -> None:
    donnees = charge(api.get("/api/espace/moi/", headers=lumen.entetes))
    assert donnees["organisation"]["raison_sociale"] == "Agence Lumen"
    assert donnees["organisation"]["id"] == str(lumen.organisation.id)


def test_le_journal_de_credits_est_cloisonne(
    api: Client, lumen: Agence, rivage: Agence
) -> None:
    credits.crediter(lumen.organisation, 5, motif="Dotation Lumen")
    credits.crediter(rivage.organisation, 9, motif="Dotation Rivage")

    vue_lumen = charge(api.get("/api/espace/credits/", headers=lumen.entetes))
    assert vue_lumen["solde"] == 5
    motifs = [m["motif"] for m in vue_lumen["mouvements"]]
    assert "Dotation Lumen" in motifs
    assert "Dotation Rivage" not in motifs


def test_les_clients_finaux_sont_cloisonnes(
    api: Client, lumen: Agence, rivage: Agence
) -> None:
    ClientFinal.objects.create(organisation=lumen.organisation, raison_sociale="Joalie")
    ClientFinal.objects.create(
        organisation=rivage.organisation, raison_sociale="Secret Rivage"
    )
    noms = [
        c["raison_sociale"]
        for c in charge(api.get("/api/espace/clients-finaux/", headers=lumen.entetes))["clients"]
    ]
    assert noms == ["Joalie"]


def test_une_fiche_d_une_autre_organisation_ne_peut_pas_etre_archivee(
    api: Client, lumen: Agence, rivage: Agence
) -> None:
    """L'identifiant ne suffit pas : la fiche doit appartenir à l'organisation."""
    fiche = ClientFinal.objects.create(
        organisation=rivage.organisation, raison_sociale="Secret Rivage"
    )
    reponse = api.post(
        f"/api/espace/clients-finaux/{fiche.id}/archiver/", headers=lumen.entetes
    )
    assert reponse.status_code == 404
    fiche.refresh_from_db()
    assert not fiche.archive


def test_l_equipe_est_cloisonnee(api: Client, lumen: Agence, rivage: Agence) -> None:
    emails = [
        m["email"] for m in charge(api.get("/api/espace/equipe/", headers=lumen.entetes))["membres"]
    ]
    assert emails == ["lumen@example.com"]


def _job_pour(organisation: Organisation, suffixe: str) -> GenerationJob:
    from generation.services import bootstrap_generation_job

    offre = Offer.objects.create(
        name="Étude de marché",
        slug=f"em-{suffixe}",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email=f"client-{suffixe}@example.com")
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
    job = bootstrap_generation_job(soumission)
    GenerationJob.objects.filter(pk=job.pk).update(status=JobStatus.DONE)
    return job


def test_les_livrables_sont_cloisonnes(
    api: Client, lumen: Agence, rivage: Agence
) -> None:
    """La propriété la plus sensible : un document est un travail payé."""
    mien = _job_pour(lumen.organisation, "lumen")
    autre = _job_pour(rivage.organisation, "rivage")

    identifiants = [
        item["id"]
        for item in charge(api.get("/api/espace/livrables/", headers=lumen.entetes))["livrables"]
    ]
    assert str(mien.id) in identifiants
    assert str(autre.id) not in identifiants


def test_un_job_sans_organisation_n_apparait_dans_aucun_espace(
    api: Client, lumen: Agence
) -> None:
    """Mieux vaut une liste incomplète qu'une liste montrant le document d'autrui."""
    from generation.services import bootstrap_generation_job

    offre = Offer.objects.create(
        name="Étude", slug="em-orphelin", deliverable_type=DeliverableType.MARKET_STUDY
    )
    client = Customer.objects.create(email="orphelin-job@example.com")
    commande = Order.objects.create(
        systeme_order_id="order-orphelin", customer=client, offer=offre
    )
    soumission = IntakeSubmission.objects.create(
        order=commande,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "test", "PAYS": "France"},
    )
    orphelin = bootstrap_generation_job(soumission)

    identifiants = [
        item["id"]
        for item in charge(api.get("/api/espace/livrables/", headers=lumen.entetes))["livrables"]
    ]
    assert str(orphelin.id) not in identifiants


# ── Droits (§12) appliqués par l'API ─────────────────────────────────────────


def test_un_role_lecture_ne_peut_pas_creer_de_fiche_client(api: Client) -> None:
    """Masquer le bouton ne suffit pas : l'API doit refuser."""
    lectrice = Agence("Agence Vue", "vue@example.com", role=RoleOrganisation.LECTURE)
    reponse = api.post(
        "/api/espace/clients-finaux/",
        data=json.dumps({"raison_sociale": "Tentative"}),
        content_type="application/json",
        headers=lectrice.entetes,
    )
    assert reponse.status_code == 403
    assert not ClientFinal.objects.filter(raison_sociale="Tentative").exists()


def test_un_role_lecture_peut_consulter(api: Client) -> None:
    """Contre-épreuve : la lecture seule lit bien."""
    lectrice = Agence("Agence Vue 2", "vue2@example.com", role=RoleOrganisation.LECTURE)
    assert api.get("/api/espace/livrables/", headers=lectrice.entetes).status_code == 200
    assert api.get("/api/espace/clients-finaux/", headers=lectrice.entetes).status_code == 200


def test_un_membre_peut_creer_une_fiche_client(api: Client) -> None:
    membre = Agence("Agence Faire", "faire@example.com", role=RoleOrganisation.MEMBRE)
    reponse = api.post(
        "/api/espace/clients-finaux/",
        data=json.dumps({"raison_sociale": "Joalie", "secteur": "joaillerie"}),
        content_type="application/json",
        headers=membre.entetes,
    )
    assert reponse.status_code == 201
    assert charge(reponse)["raison_sociale"] == "Joalie"


def test_les_droits_renvoyes_correspondent_a_la_table_du_serveur(
    api: Client, lumen: Agence
) -> None:
    """L'interface affiche ces droits ; ils doivent venir du serveur, pas d'une
    matrice recopiée côté navigateur (règle 5)."""
    donnees = charge(api.get("/api/espace/moi/", headers=lumen.entetes))
    attendus = sorted(services.DROITS[RoleOrganisation.PROPRIETAIRE])
    assert donnees["utilisateur"]["droits"] == attendus


# ── Contenu utile ────────────────────────────────────────────────────────────


def test_moi_expose_le_solde_et_l_alerte(api: Client, lumen: Agence) -> None:
    donnees = charge(api.get("/api/espace/moi/", headers=lumen.entetes))
    assert donnees["credits"]["solde"] == 0
    assert donnees["credits"]["alerte"] is True, "Un solde nul doit alerter."

    credits.crediter(lumen.organisation, 5, motif="Dotation")
    donnees = charge(api.get("/api/espace/moi/", headers=lumen.entetes))
    assert donnees["credits"]["solde"] == 5
    assert donnees["credits"]["alerte"] is False


def test_moi_expose_la_formule_souscrite(api: Client, lumen: Agence) -> None:
    formule = Formule.objects.create(
        libelle="Pro", code="pro", credits_par_echeance=3, prix_mensuel_cents=18_900
    )
    services.souscrire(lumen.organisation, formule, doter_immediatement=False)
    abonnement = charge(api.get("/api/espace/moi/", headers=lumen.entetes))["abonnement"]
    assert abonnement["formule"] == "Pro"
    assert abonnement["prix_mensuel_cents"] == 18_900


def test_une_fiche_client_en_doublon_est_refusee(api: Client, lumen: Agence) -> None:
    ClientFinal.objects.create(organisation=lumen.organisation, raison_sociale="Joalie")
    reponse = api.post(
        "/api/espace/clients-finaux/",
        data=json.dumps({"raison_sociale": "Joalie"}),
        content_type="application/json",
        headers=lumen.entetes,
    )
    assert reponse.status_code == 409


def test_une_fiche_sans_raison_sociale_est_refusee(api: Client, lumen: Agence) -> None:
    reponse = api.post(
        "/api/espace/clients-finaux/",
        data=json.dumps({"secteur": "joaillerie"}),
        content_type="application/json",
        headers=lumen.entetes,
    )
    assert reponse.status_code == 400


def test_une_fiche_archivee_disparait_de_la_liste(api: Client, lumen: Agence) -> None:
    fiche = ClientFinal.objects.create(
        organisation=lumen.organisation, raison_sociale="Joalie"
    )
    api.post(f"/api/espace/clients-finaux/{fiche.id}/archiver/", headers=lumen.entetes)
    assert charge(api.get("/api/espace/clients-finaux/", headers=lumen.entetes))["clients"] == []
    avec = charge(
        api.get("/api/espace/clients-finaux/?archives=1", headers=lumen.entetes)
    )["clients"]
    assert len(avec) == 1
    assert avec[0]["archive"] is True


def test_la_charte_saisie_est_relue_telle_quelle(api: Client, lumen: Agence) -> None:
    """Ce sont ces valeurs qui habilleront le document : aucune ne doit dériver."""
    api.post(
        "/api/espace/clients-finaux/",
        data=json.dumps({
            "raison_sociale": "Joalie",
            "couleur_principale": "#3A132C",
            "couleur_secondaire": "#B98B4E",
            "couleur_fond": "#F1EEDB",
            "logo_url": "https://exemple.test/logo.png",
        }),
        content_type="application/json",
        headers=lumen.entetes,
    )
    fiche = charge(api.get("/api/espace/clients-finaux/", headers=lumen.entetes))["clients"][0]
    assert fiche["couleur_principale"] == "#3A132C"
    assert fiche["couleur_secondaire"] == "#B98B4E"
    assert fiche["couleur_fond"] == "#F1EEDB"
    assert fiche["logo_url"] == "https://exemple.test/logo.png"


# ── Formules et demandes commerciales ────────────────────────────────────────


def test_le_catalogue_marque_la_formule_en_cours(api: Client, lumen: Agence) -> None:
    pro = Formule.objects.create(
        libelle="Pro", code="pro", credits_par_echeance=3, prix_mensuel_cents=18_900
    )
    Formule.objects.create(
        libelle="Solo", code="solo", credits_par_echeance=2, prix_mensuel_cents=12_900
    )
    services.souscrire(lumen.organisation, pro, doter_immediatement=False)

    donnees = charge(api.get("/api/espace/formules/", headers=lumen.entetes))
    assert donnees["code_actuel"] == "pro"
    actuelles = [f["code"] for f in donnees["formules"] if f["actuelle"]]
    assert actuelles == ["pro"]


def test_le_cout_par_livrable_est_calcule_et_jamais_stocke(
    api: Client, lumen: Agence
) -> None:
    """Le mémoriser en ferait une troisième valeur susceptible de contredire
    les deux autres (règle 5). Ici : 189 € / 3 crédits = 63 €."""
    Formule.objects.create(
        libelle="Pro", code="pro", credits_par_echeance=3, prix_mensuel_cents=18_900
    )
    formule = charge(api.get("/api/espace/formules/", headers=lumen.entetes))["formules"][0]
    assert formule["cout_par_livrable_cents"] == 6_300


def test_une_formule_inactive_n_est_pas_proposee(api: Client, lumen: Agence) -> None:
    Formule.objects.create(
        libelle="Ancienne", code="ancienne", credits_par_echeance=1, active=False
    )
    codes = [
        f["code"]
        for f in charge(api.get("/api/espace/formules/", headers=lumen.entetes))["formules"]
    ]
    assert "ancienne" not in codes


def test_un_proprietaire_peut_demander_un_changement_de_formule(
    api: Client, lumen: Agence
) -> None:
    Formule.objects.create(
        libelle="Structure", code="structure", credits_par_echeance=10,
        prix_mensuel_cents=42_900,
    )
    reponse = api.post(
        "/api/espace/demandes/",
        data=json.dumps({"type": "changement_formule", "formule": "structure"}),
        content_type="application/json",
        headers=lumen.entetes,
    )
    assert reponse.status_code == 201
    assert charge(reponse)["formule_visee"] == "Structure"
    assert charge(reponse)["statut"] == "ouverte"


def test_une_demande_ne_debite_ni_ne_change_rien(api: Client, lumen: Agence) -> None:
    """Aucun encaissement, aucun changement d'abonnement : c'est une DEMANDE.

    Un bouton qui changerait la formule sans paiement offrirait la montée de
    gamme ; un bouton qui prétendrait débiter une carte serait un mensonge.
    """
    Formule.objects.create(
        libelle="Structure", code="structure", credits_par_echeance=10,
        prix_mensuel_cents=42_900,
    )
    pro = Formule.objects.create(
        libelle="Pro", code="pro", credits_par_echeance=3, prix_mensuel_cents=18_900
    )
    services.souscrire(lumen.organisation, pro, doter_immediatement=False)
    solde_avant = credits.solde(lumen.organisation)

    api.post(
        "/api/espace/demandes/",
        data=json.dumps({"type": "changement_formule", "formule": "structure"}),
        content_type="application/json",
        headers=lumen.entetes,
    )
    abonnement = charge(api.get("/api/espace/moi/", headers=lumen.entetes))["abonnement"]
    assert abonnement["code"] == "pro", "L'abonnement ne doit pas avoir changé."
    assert credits.solde(lumen.organisation) == solde_avant


def test_un_role_membre_ne_peut_pas_engager_l_organisation(api: Client) -> None:
    """Masquer le bouton ne suffit pas : l'API doit refuser."""
    from organisations.models import DemandeCommerciale

    membre = Agence("Agence Faire 2", "faire2@example.com", role=RoleOrganisation.MEMBRE)
    reponse = api.post(
        "/api/espace/demandes/",
        data=json.dumps({"type": "credits_additionnels", "quantite": 3}),
        content_type="application/json",
        headers=membre.entetes,
    )
    assert reponse.status_code == 403
    assert not DemandeCommerciale.objects.exists()


def test_deux_demandes_du_meme_type_sont_refusees(api: Client, lumen: Agence) -> None:
    """Un double clic en ouvrirait deux, et EVKHA traiterait deux fois."""
    corps = json.dumps({"type": "credits_additionnels", "quantite": 2})
    premiere = api.post(
        "/api/espace/demandes/", data=corps,
        content_type="application/json", headers=lumen.entetes,
    )
    seconde = api.post(
        "/api/espace/demandes/", data=corps,
        content_type="application/json", headers=lumen.entetes,
    )
    assert premiere.status_code == 201
    assert seconde.status_code == 409


def test_un_achat_sans_quantite_est_refuse(api: Client, lumen: Agence) -> None:
    reponse = api.post(
        "/api/espace/demandes/",
        data=json.dumps({"type": "credits_additionnels"}),
        content_type="application/json",
        headers=lumen.entetes,
    )
    assert reponse.status_code == 400


def test_un_type_de_demande_inconnu_est_refuse(api: Client, lumen: Agence) -> None:
    reponse = api.post(
        "/api/espace/demandes/",
        data=json.dumps({"type": "remboursement_total"}),
        content_type="application/json",
        headers=lumen.entetes,
    )
    assert reponse.status_code == 400


def test_les_demandes_sont_cloisonnees(
    api: Client, lumen: Agence, rivage: Agence
) -> None:
    api.post(
        "/api/espace/demandes/",
        data=json.dumps({"type": "credits_additionnels", "quantite": 4}),
        content_type="application/json",
        headers=rivage.entetes,
    )
    assert charge(api.get("/api/espace/demandes/", headers=lumen.entetes))["demandes"] == []
    assert len(charge(api.get("/api/espace/demandes/", headers=rivage.entetes))["demandes"]) == 1


# ── Ma marque : le profil unique de l'abonné ─────────────────────────────────
# Décision du 30/07/2026 : l'espace client est celui d'UN abonné qui gère SES
# études, pas d'une agence gérant plusieurs clients finaux.


def test_la_marque_est_celle_de_l_organisation(api: Client, lumen: Agence) -> None:
    donnees = charge(api.get("/api/espace/marque/", headers=lumen.entetes))
    assert donnees["raison_sociale"] == "Agence Lumen"


def test_la_charte_saisie_est_relue_telle_quelle_sur_la_marque(
    api: Client, lumen: Agence
) -> None:
    """Ce sont ces valeurs qui habilleront le document : aucune ne doit dériver."""
    reponse = api.post(
        "/api/espace/marque/",
        data=json.dumps({
            "raison_sociale": "Joalie",
            "secteur": "joaillerie de créateurs",
            "couleur_principale": "#3A132C",
            "couleur_secondaire": "#B98B4E",
            "couleur_fond": "#F1EEDB",
            "logo_url": "https://exemple.test/logo.png",
        }),
        content_type="application/json",
        headers=lumen.entetes,
    )
    assert reponse.status_code == 200
    relu = charge(api.get("/api/espace/marque/", headers=lumen.entetes))
    assert relu["raison_sociale"] == "Joalie"
    assert relu["couleur_principale"] == "#3A132C"
    assert relu["couleur_fond"] == "#F1EEDB"
    assert relu["logo_url"] == "https://exemple.test/logo.png"


def test_un_champ_non_modifiable_est_refuse_et_non_ignore(
    api: Client, lumen: Agence
) -> None:
    """Un abonné ne doit pas pouvoir se réactiver ni relever ses propres seuils.

    Le champ est REFUSÉ, pas ignoré : ignorer laisserait croire à l'appelant que
    sa modification a été prise en compte.
    """
    reponse = api.post(
        "/api/espace/marque/",
        data=json.dumps({"statut": "active", "seuil_alerte_credits": 99}),
        content_type="application/json",
        headers=lumen.entetes,
    )
    assert reponse.status_code == 400
    assert charge(reponse)["code"] == "champ_interdit"
    lumen.organisation.refresh_from_db()
    assert lumen.organisation.seuil_alerte_credits == 1


def test_une_raison_sociale_vide_est_refusee(api: Client, lumen: Agence) -> None:
    reponse = api.post(
        "/api/espace/marque/",
        data=json.dumps({"raison_sociale": "   "}),
        content_type="application/json",
        headers=lumen.entetes,
    )
    assert reponse.status_code == 400


def test_un_role_lecture_ne_peut_pas_modifier_la_marque(api: Client) -> None:
    lectrice = Agence("Agence Vue 3", "vue3@example.com", role=RoleOrganisation.LECTURE)
    assert api.get("/api/espace/marque/", headers=lectrice.entetes).status_code == 200
    reponse = api.post(
        "/api/espace/marque/",
        data=json.dumps({"couleur_principale": "#000000"}),
        content_type="application/json",
        headers=lectrice.entetes,
    )
    assert reponse.status_code == 403


def test_la_marque_est_cloisonnee(api: Client, lumen: Agence, rivage: Agence) -> None:
    api.post(
        "/api/espace/marque/",
        data=json.dumps({"couleur_principale": "#111111"}),
        content_type="application/json",
        headers=rivage.entetes,
    )
    vue = charge(api.get("/api/espace/marque/", headers=lumen.entetes))
    assert vue["couleur_principale"] == ""
    assert vue["raison_sociale"] == "Agence Lumen"


def test_la_marque_alimente_la_palette_du_moteur_de_rendu(
    api: Client, lumen: Agence
) -> None:
    """Bout en bout : ce que le client saisit doit produire la charte attendue."""
    from generation.rendu_word.palette import REF_CREME, REF_PRUNE, construire_palette

    api.post(
        "/api/espace/marque/",
        data=json.dumps({
            "couleur_principale": "#3A132C",
            "couleur_secondaire": "#B98B4E",
            "couleur_fond": "#F1EEDB",
        }),
        content_type="application/json",
        headers=lumen.entetes,
    )
    lumen.organisation.refresh_from_db()
    palette = construire_palette(
        primaire=lumen.organisation.couleur_principale,
        secondaire=lumen.organisation.couleur_secondaire,
        fond_clair=lumen.organisation.couleur_fond,
    )
    assert palette.primaire == REF_PRUNE
    assert palette.fond_clair == REF_CREME

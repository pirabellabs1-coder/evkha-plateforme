"""Espace client — commande d'un document et questionnaires (§9.3).

Les quatre questionnaires sont repris des formulaires Tally. Deux propriétés
comptent plus que le reste :

- une question déclarée au formulaire doit **atteindre le moteur** ; sinon elle
  est posée au client pour rien ;
- une commande doit **débiter au démarrage**, jamais à la création — sans quoi
  un client serait débité d'une étude qui n'a pas démarré.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client

from customers.models import Customer
from generation.models import GenerationJob
from organisations import commandes, credits, formulaires, services
from organisations.authentification import creer_compte, ouvrir_session
from organisations.models import RoleOrganisation
from tests.aides_abonnement import abonner

pytestmark = pytest.mark.django_db

MOT_DE_PASSE = "mot-de-passe-de-test-2026"

#: Réponses complètes à l'étude de marché, pour les cas passants.
SAISIE_EM = {
    "PROJET": "Maison Lumen",
    "SECTEUR": "joaillerie de créateurs",
    "PAYS": "France",
    "ZONE": "Paris",
    "DESCRIPTION_PROJET": "Atelier de joaillerie contemporaine.",
    "POSITIONNEMENT": "Haut de gamme accessible.",
    "POINTS_FORTS": "Expertise vintage.",
    "CLIENTELE_CIBLE": "35-55 ans, cadres.",
    "ZONE_CIBLE": "Paris et Île-de-France.",
    "CONCURRENTS": "Maisons installées.",
    "DIFFERENCIATION": "Triple offre rare.",
    "RESULTATS_ATTENDUS": "Dimensionner le marché.",
    "DEMANDES_SPECIFIQUES": "Quelle part est réaliste ?",
    "ELEMENTS_A_RETENIR": "Aucun document interne.",
}


class Abonne:
    def __init__(self, nom: str, email: str, role: str = RoleOrganisation.PROPRIETAIRE):
        self.contact = Customer.objects.create(email=email)
        self.organisation = services.creer_organisation(
            raison_sociale=nom, contact=self.contact
        )
        # L'espace est fermé à qui n'a rien payé : sans abonnement, chaque vue
        # répondrait 402. Aucun crédit versé, le solde reste à zéro.
        abonner(self.organisation)
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
    return Abonne("Agence Lumen", "lumen-cmd@example.com")


@pytest.fixture
def api() -> Client:
    return Client()


def charge(reponse: Any) -> dict[str, Any]:
    donnees: dict[str, Any] = json.loads(reponse.content)
    return donnees


def _poster(api: Client, abonne: Abonne, corps: dict[str, Any]) -> Any:
    return api.post(
        "/api/espace/commander/",
        data=json.dumps(corps, ensure_ascii=False),
        content_type="application/json",
        headers=abonne.entetes,
    )


# ── Les questionnaires ───────────────────────────────────────────────────────


def test_les_quatre_questionnaires_sont_declares() -> None:
    """Le catalogue est DÉRIVÉ des formulaires : ajouter l'un ajoute l'autre."""
    assert set(formulaires.FORMULAIRES) == {
        "market_study",
        "competitor_study",
        "business_plan",
        "business_strategy",
    }
    assert set(commandes.TYPES_COMMANDABLES) == set(formulaires.FORMULAIRES)


@pytest.mark.parametrize("type_document", list(formulaires.FORMULAIRES))
def test_chaque_questionnaire_a_des_sections_et_des_obligatoires(
    type_document: str,
) -> None:
    questionnaire = formulaires.FORMULAIRES[type_document]
    assert questionnaire.sections
    assert questionnaire.obligatoires
    assert questionnaire.note.strip()


@pytest.mark.parametrize("type_document", list(formulaires.FORMULAIRES))
def test_chaque_questionnaire_identifie_le_projet_le_secteur_et_le_pays(
    type_document: str,
) -> None:
    """Le moteur interpole `SECTEUR` et `PAYS` dans toutes ses trames.

    Un questionnaire qui ne les collecte pas produirait une étude sans sujet.
    """
    identifiants = {
        champ.identifiant for champ in formulaires.FORMULAIRES[type_document].champs
    }
    assert {"PROJET", "SECTEUR", "PAYS"} <= identifiants


def test_aucun_identifiant_de_champ_n_est_duplique() -> None:
    """Deux champs de même identifiant : le second écraserait silencieusement
    la réponse au premier."""
    for type_document, questionnaire in formulaires.FORMULAIRES.items():
        identifiants = [champ.identifiant for champ in questionnaire.champs]
        assert len(identifiants) == len(set(identifiants)), type_document


def test_le_questionnaire_est_servi_par_l_api(api: Client, abonne: Abonne) -> None:
    reponse = api.get("/api/espace/formulaire/business_plan/", headers=abonne.entetes)
    assert reponse.status_code == 200
    donnees = charge(reponse)
    assert donnees["titre"] == "Questionnaire — Business plan"
    intitules = [
        champ["libelle"]
        for section in donnees["sections"]
        for champ in section["champs"]
    ]
    assert "Nom du porteur de projet" in intitules


def test_un_questionnaire_inconnu_renvoie_404(api: Client, abonne: Abonne) -> None:
    reponse = api.get("/api/espace/formulaire/inexistant/", headers=abonne.entetes)
    assert reponse.status_code == 404


# ── Les réponses atteignent le moteur ────────────────────────────────────────


def test_toute_reponse_saisie_devient_une_variable_de_prompt(abonne: Abonne) -> None:
    """Une question posée pour rien est pire qu'une question absente."""
    variables, manquants = commandes.variables_de_commande(
        abonne.organisation, "market_study", SAISIE_EM
    )
    assert manquants == []
    for identifiant, valeur in SAISIE_EM.items():
        assert variables[identifiant] == valeur


def test_la_marque_est_injectee_et_ne_peut_pas_etre_surchargee(abonne: Abonne) -> None:
    """La charte du document est celle de la fiche, pas d'un champ oublié."""
    abonne.organisation.logo_url = "https://exemple.test/vrai.png"
    abonne.organisation.couleur_principale = "#3A132C"
    abonne.organisation.save()

    saisie = {**SAISIE_EM, "LOGO_URL": "https://autre.test/faux.png"}
    variables, _ = commandes.variables_de_commande(
        abonne.organisation, "market_study", saisie
    )
    assert variables["LOGO_URL"] == "https://exemple.test/vrai.png"
    assert variables["COULEUR_PRINCIPALE"] == "#3A132C"


def test_le_secteur_de_la_fiche_sert_de_repli_sans_ecraser(abonne: Abonne) -> None:
    """Un abonné peut commander une étude sur un secteur voisin du sien."""
    abonne.organisation.secteur = "conseil"
    abonne.organisation.save()

    avec, _ = commandes.variables_de_commande(
        abonne.organisation, "market_study", SAISIE_EM
    )
    assert avec["SECTEUR"] == "joaillerie de créateurs"

    repli, _ = commandes.variables_de_commande(
        abonne.organisation, "market_study", {**SAISIE_EM, "SECTEUR": ""}
    )
    assert repli["SECTEUR"] == "conseil"


def test_la_zone_retombe_sur_le_pays(abonne: Abonne) -> None:
    """Une zone vide ferait échouer les trames qui l'interpolent."""
    variables, _ = commandes.variables_de_commande(
        abonne.organisation, "market_study", {**SAISIE_EM, "ZONE": ""}
    )
    assert variables["ZONE"] == "France"


# ── Refus ────────────────────────────────────────────────────────────────────


def test_une_commande_incomplete_nomme_les_questions(
    api: Client, abonne: Abonne
) -> None:
    """« CLIENTELE_CIBLE manquant » ne dit rien au client."""
    credits.crediter(abonne.organisation, 3, motif="Dotation")
    reponse = _poster(api, abonne, {"type": "market_study", "saisie": {"PROJET": "T"}})
    assert reponse.status_code == 400
    detail = charge(reponse)["error"]
    assert "Secteur d'activité" in detail
    assert "CLIENTELE_CIBLE" not in detail


def test_une_commande_sans_credit_est_refusee(api: Client, abonne: Abonne) -> None:
    """« Aucun découvert » : le refus arrive AVANT tout appel facturé."""
    reponse = _poster(api, abonne, {"type": "market_study", "saisie": SAISIE_EM})
    assert reponse.status_code == 400
    assert "insuffisant" in charge(reponse)["error"].lower()
    assert not GenerationJob.objects.exists()


def test_une_organisation_suspendue_ne_peut_pas_commander(
    api: Client, abonne: Abonne
) -> None:
    credits.crediter(abonne.organisation, 3, motif="Dotation")
    services.suspendre(abonne.organisation)
    reponse = _poster(api, abonne, {"type": "market_study", "saisie": SAISIE_EM})
    assert reponse.status_code == 400
    assert "suspendue" in charge(reponse)["error"].lower()


def test_un_role_lecture_ne_peut_pas_commander(api: Client) -> None:
    lectrice = Abonne(
        "Agence Vue", "vue-cmd@example.com", role=RoleOrganisation.LECTURE
    )
    credits.crediter(lectrice.organisation, 3, motif="Dotation")
    assert _poster(
        api, lectrice, {"type": "market_study", "saisie": SAISIE_EM}
    ).status_code == 403


def test_un_type_non_commandable_est_refuse(api: Client, abonne: Abonne) -> None:
    credits.crediter(abonne.organisation, 3, motif="Dotation")
    reponse = _poster(api, abonne, {"type": "audit_rgpd", "saisie": SAISIE_EM})
    assert reponse.status_code == 400


def test_un_corps_illisible_donne_400_et_non_500(api: Client, abonne: Abonne) -> None:
    """Un encodage autre qu'UTF-8 levait `UnicodeDecodeError` en erreur 500.

    Constaté en envoyant un questionnaire accentué depuis un terminal Windows :
    le client recevait une page d'erreur serveur au lieu d'un refus explicite.
    """
    reponse = api.post(
        "/api/espace/commander/",
        data="Secteur d'activité".encode("latin-1"),
        content_type="application/json",
        headers=abonne.entetes,
    )
    assert reponse.status_code == 400


# ── Le chemin passant ────────────────────────────────────────────────────────


def test_une_commande_complete_cree_le_job_et_debite(
    api: Client, abonne: Abonne
) -> None:
    """Bout en bout : la commande produit un job ET consomme un crédit."""
    credits.crediter(abonne.organisation, 3, motif="Dotation")
    reponse = _poster(api, abonne, {"type": "market_study", "saisie": SAISIE_EM})

    assert reponse.status_code == 202
    donnees = charge(reponse)
    assert donnees["cout_credits"] == 1

    job = GenerationJob.objects.get(id=donnees["job_id"])
    assert job.order.organisation == abonne.organisation
    assert credits.solde(abonne.organisation) == 2


def test_les_reponses_du_client_arrivent_au_moteur(api: Client, abonne: Abonne) -> None:
    """Règle 7 : la preuve est dans ce que le moteur reçoit, pas dans la réponse HTTP."""
    from intake.models import IntakeSubmission

    credits.crediter(abonne.organisation, 3, motif="Dotation")
    reponse = _poster(api, abonne, {"type": "market_study", "saisie": SAISIE_EM})
    job = GenerationJob.objects.get(id=charge(reponse)["job_id"])

    soumission = IntakeSubmission.objects.get(order=job.order)
    assert soumission.normalized_variables["SECTEUR"] == "joaillerie de créateurs"
    assert (
        soumission.normalized_variables["DEMANDES_SPECIFIQUES"]
        == "Quelle part est réaliste ?"
    )


def test_la_commande_est_rattachee_a_l_organisation(
    api: Client, abonne: Abonne
) -> None:
    """Sans ce rattachement, aucun débit n'aurait lieu et le livrable
    n'apparaîtrait dans aucun espace."""
    credits.crediter(abonne.organisation, 3, motif="Dotation")
    reponse = _poster(api, abonne, {"type": "market_study", "saisie": SAISIE_EM})
    job = GenerationJob.objects.get(id=charge(reponse)["job_id"])
    assert job.order.organisation_id == abonne.organisation.id

    listes = charge(api.get("/api/espace/livrables/", headers=abonne.entetes))
    assert str(job.id) in [item["id"] for item in listes["livrables"]]


def test_le_catalogue_signale_ce_que_le_solde_ne_couvre_pas(
    api: Client, abonne: Abonne
) -> None:
    vide = charge(api.get("/api/espace/catalogue/", headers=abonne.entetes))
    assert all(not doc["couvert"] for doc in vide["documents"])

    credits.crediter(abonne.organisation, 2, motif="Dotation")
    plein = charge(api.get("/api/espace/catalogue/", headers=abonne.entetes))
    assert all(doc["couvert"] for doc in plein["documents"])

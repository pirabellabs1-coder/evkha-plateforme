"""Lot 4 — organisations, portefeuille de crédits, clients finaux.

Ce module manipule ce que le client a payé. Les tests portent donc d'abord sur
ce qui coûte de l'argent quand ça rate : le découvert, le double débit, le
remboursement inexact, et la dotation qui efface ce qu'elle vient de créditer.

Chaque refus a sa contre-épreuve — le cas légitime doit passer (règle 6).
"""
from __future__ import annotations

import pytest
from django.test import Client

from customers.models import Customer
from organisations import credits, services
from organisations.models import (
    ClientFinal,
    Formule,
    MembreOrganisation,
    Organisation,
    ReportCredits,
    RoleOrganisation,
    StatutAbonnement,
    TypeMouvement,
)
from tests.conftest import JETON_ADMIN

pytestmark = pytest.mark.django_db

def _administration() -> Client:
    """Client de test qui presente le jeton d'administration.

    Les routes de supervision vivent sous `/api/dashboard/`. Ces tests ne
    passaient auparavant que grace au contournement de developpement lu dans
    le `.env` local ; ils empruntent desormais le vrai chemin.
    """
    return Client(HTTP_AUTHORIZATION=f"Bearer {JETON_ADMIN}")



# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def contact() -> Customer:
    return Customer.objects.create(email="agence@example.com")


@pytest.fixture
def organisation(contact: Customer) -> Organisation:
    return services.creer_organisation(
        raison_sociale="Agence Test", contact=contact
    )


@pytest.fixture
def formule_pro() -> Formule:
    """La formule Pro du site : 189 €/mois, 3 crédits, aucun report."""
    return Formule.objects.create(
        libelle="Pro", code="pro", credits_par_echeance=3,
        prix_mensuel_cents=18_900, report_credits=ReportCredits.AUCUN,
    )


# ── Création ─────────────────────────────────────────────────────────────────


def test_creer_une_organisation_cree_le_portefeuille_et_le_proprietaire(
    organisation: Organisation, contact: Customer
) -> None:
    """Les trois sont indissociables.

    Une organisation sans propriétaire n'est plus administrable ; un
    portefeuille créé plus tard laisse une fenêtre où une commande échoue sans
    raison compréhensible.
    """
    assert credits.solde(organisation) == 0
    membre = MembreOrganisation.objects.get(
        organisation=organisation, customer=contact
    )
    assert membre.role == RoleOrganisation.PROPRIETAIRE
    assert membre.actif


# ── Le solde est le journal ──────────────────────────────────────────────────


def test_le_solde_est_la_somme_du_journal(organisation: Organisation) -> None:
    credits.crediter(organisation, 5, motif="Dotation initiale")
    credits.debiter(organisation, 2, reference="job-1", motif="Étude de marché")
    assert credits.solde(organisation) == 3
    assert organisation.portefeuille.solde == 3


def test_les_deux_lectures_du_solde_concordent(organisation: Organisation) -> None:
    """Règle 5 : deux lectures divergentes du même chiffre est LE défaut du projet."""
    credits.crediter(organisation, 10, motif="Dotation")
    credits.debiter(organisation, 4, reference="job-2", motif="Étude")
    assert credits.solde(organisation) == organisation.portefeuille.solde


# ── Entrées ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("quantite", [0, -3])
def test_une_entree_doit_etre_positive(
    organisation: Organisation, quantite: int
) -> None:
    with pytest.raises(ValueError):
        credits.crediter(organisation, quantite, motif="Erreur")


def test_un_mouvement_sans_motif_est_refuse(organisation: Organisation) -> None:
    """Un journal dont la moitié des lignes n'explique rien ne sert à personne."""
    with pytest.raises(ValueError):
        credits.crediter(organisation, 3, motif="   ")


def test_une_dotation_manuelle_enregistre_son_auteur(
    organisation: Organisation,
) -> None:
    """« Dotation manuelle avec motif enregistré » — exigence du §11."""
    mouvement = credits.crediter(
        organisation, 2, motif="Geste commercial après incident",
        auteur="evangeline@evkha.fr",
    )
    assert mouvement.auteur == "evangeline@evkha.fr"
    assert mouvement.type == TypeMouvement.GESTE


# ── Aucun découvert ──────────────────────────────────────────────────────────


def test_un_debit_superieur_au_solde_est_refuse(organisation: Organisation) -> None:
    """« Aucun découvert » — exigence explicite du §11."""
    credits.crediter(organisation, 1, motif="Dotation")
    with pytest.raises(credits.SoldeInsuffisantError) as echec:
        credits.debiter(organisation, 2, reference="job-3", motif="Étude")
    assert echec.value.solde == 1
    assert echec.value.requis == 2
    assert credits.solde(organisation) == 1, "Le solde ne doit pas avoir bougé."


def test_un_debit_couvert_par_le_solde_passe(organisation: Organisation) -> None:
    """Contre-épreuve : le contrôle ne bloque pas ce qui est légitime."""
    credits.crediter(organisation, 2, motif="Dotation")
    credits.debiter(organisation, 2, reference="job-4", motif="Étude")
    assert credits.solde(organisation) == 0


def test_un_debit_a_zero_credit_est_refuse(organisation: Organisation) -> None:
    with pytest.raises(ValueError):
        credits.debiter(organisation, 0, reference="job-5", motif="Étude")


def test_une_organisation_suspendue_ne_peut_plus_consommer(
    organisation: Organisation,
) -> None:
    credits.crediter(organisation, 5, motif="Dotation")
    services.suspendre(organisation, motif="Impayé")
    with pytest.raises(credits.OrganisationSuspendueError):
        credits.debiter(organisation, 1, reference="job-6", motif="Étude")
    assert credits.solde(organisation) == 5


def test_une_organisation_reactivee_peut_de_nouveau_consommer(
    organisation: Organisation,
) -> None:
    credits.crediter(organisation, 5, motif="Dotation")
    services.suspendre(organisation)
    services.reactiver(organisation)
    credits.debiter(organisation, 1, reference="job-7", motif="Étude")
    assert credits.solde(organisation) == 4


# ── Aucun double débit ───────────────────────────────────────────────────────


def test_deux_debits_de_la_meme_reference_sont_impossibles(
    organisation: Organisation,
) -> None:
    """Une tâche Celery relancée après incident réseau ne doit pas facturer deux fois.

    La garantie est une contrainte d'unicité EN BASE, pas une vérification en
    Python : ce projet a déjà payé deux fois chaque chapitre pour une raison de
    cette famille.
    """
    credits.crediter(organisation, 10, motif="Dotation")
    credits.debiter(organisation, 3, reference="job-8", motif="Étude de marché")
    with pytest.raises(credits.MouvementDejaEnregistreError):
        credits.debiter(organisation, 3, reference="job-8", motif="Étude de marché")
    assert credits.solde(organisation) == 7


def test_une_relance_passe_meme_a_solde_zero(organisation: Organisation) -> None:
    """LE défaut mesuré en production le 13/08/2026.

    Trois relances refusées d'un coup sur « Solde insuffisant : 0 crédit(s)
    disponible(s) pour 1 requis », alors que les trois études étaient DÉJÀ
    PAYÉES et qu'il ne leur manquait qu'un chapitre — tué par un contrôle
    défectueux, pas par le client.

    L'idempotence existait et était documentée — « une relance ne repaie pas »
    — mais le contrôle de SOLDE passait devant : un client à zéro crédit ne
    pouvait plus relancer une étude qu'il avait réglée. Le solde ne concerne
    que les débits NEUFS ; refuser une relance déjà payée revient à facturer
    deux fois le même travail.
    """
    credits.crediter(organisation, 1, motif="Dotation")
    credits.debiter(organisation, 1, reference="job-relance", motif="Étude")
    assert credits.solde(organisation) == 0

    # Sur le code d'avant, cette ligne levait `SoldeInsuffisantError`.
    with pytest.raises(credits.MouvementDejaEnregistreError):
        credits.debiter(organisation, 1, reference="job-relance", motif="Étude")

    assert credits.solde(organisation) == 0, "une relance ne débite rien"


def test_une_commande_neuve_reste_refusee_a_solde_zero(
    organisation: Organisation,
) -> None:
    """CONTRE-ÉPREUVE : on lève le blocage des relances, pas celui du découvert.

    « Commande bloquée, aucun découvert » reste la règle pour une référence
    que le portefeuille n'a jamais vue.
    """
    credits.crediter(organisation, 1, motif="Dotation")
    credits.debiter(organisation, 1, reference="job-a", motif="Étude")

    with pytest.raises(credits.SoldeInsuffisantError):
        credits.debiter(organisation, 1, reference="job-b", motif="Autre étude")


def test_deux_references_distinctes_se_debitent_normalement(
    organisation: Organisation,
) -> None:
    credits.crediter(organisation, 10, motif="Dotation")
    credits.debiter(organisation, 3, reference="job-9", motif="Étude")
    credits.debiter(organisation, 3, reference="job-10", motif="Étude")
    assert credits.solde(organisation) == 4


# ── Remboursement ────────────────────────────────────────────────────────────


def test_un_remboursement_restitue_exactement_le_debit(
    organisation: Organisation,
) -> None:
    """Le montant est relu sur le débit, jamais fourni par l'appelant."""
    credits.crediter(organisation, 5, motif="Dotation")
    credits.debiter(organisation, 3, reference="job-11", motif="Étude")
    mouvement = credits.rembourser(
        organisation, reference="job-11", motif="Échec définitif de génération"
    )
    assert mouvement.quantite == 3
    assert credits.solde(organisation) == 5


def test_un_remboursement_sans_debit_est_refuse(organisation: Organisation) -> None:
    """Sinon un appel malencontreux créerait des crédits à partir de rien."""
    credits.crediter(organisation, 5, motif="Dotation")
    with pytest.raises(credits.MouvementDejaEnregistreError):
        credits.rembourser(organisation, reference="jamais-debite", motif="Échec")
    assert credits.solde(organisation) == 5


def test_un_remboursement_ne_peut_pas_etre_passe_deux_fois(
    organisation: Organisation,
) -> None:
    credits.crediter(organisation, 5, motif="Dotation")
    credits.debiter(organisation, 3, reference="job-12", motif="Étude")
    credits.rembourser(organisation, reference="job-12", motif="Échec")
    with pytest.raises(credits.MouvementDejaEnregistreError):
        credits.rembourser(organisation, reference="job-12", motif="Échec")
    assert credits.solde(organisation) == 5


# ── Contrôle préalable ───────────────────────────────────────────────────────


def test_le_recapitulatif_annonce_un_solde_insuffisant(
    organisation: Organisation,
) -> None:
    """Écran de récapitulatif avant lancement (§9.3)."""
    credits.crediter(organisation, 1, motif="Dotation")
    possible, raison = credits.peut_commander(organisation, 2)
    assert not possible
    assert "insuffisant" in raison


def test_le_recapitulatif_accepte_une_commande_couverte(
    organisation: Organisation,
) -> None:
    credits.crediter(organisation, 3, motif="Dotation")
    possible, raison = credits.peut_commander(organisation, 2)
    assert possible
    assert raison == ""


# ── Échéances et report ──────────────────────────────────────────────────────


def test_une_dotation_de_periode_ne_passe_qu_une_fois(
    organisation: Organisation,
) -> None:
    """Une tâche périodique relancée dans le mois ne dote pas deux fois."""
    credits.doter(organisation, 3, periode="2026-08")
    with pytest.raises(credits.MouvementDejaEnregistreError):
        credits.doter(organisation, 3, periode="2026-08")
    assert credits.solde(organisation) == 3


def test_l_echeance_expire_le_solde_avant_de_doter(
    organisation: Organisation, formule_pro: Formule
) -> None:
    """L'ordre est décisif.

    Doter puis expirer purgerait la dotation du mois entrant : le client
    perdrait ce qu'il vient de payer. Ici, deux crédits non consommés du mois
    précédent disparaissent, et les trois de la nouvelle échéance restent.
    """
    abonnement = services.souscrire(
        organisation, formule_pro, doter_immediatement=False
    )
    credits.crediter(organisation, 2, motif="Reste du mois précédent")

    ajoutes = services.appliquer_echeance(abonnement, periode="2026-09")

    assert ajoutes == 3
    assert credits.solde(organisation) == 3, (
        "Les crédits du mois précédent devaient expirer, la nouvelle dotation rester."
    )


def test_une_echeance_deja_appliquee_ne_dote_pas_deux_fois(
    organisation: Organisation, formule_pro: Formule
) -> None:
    abonnement = services.souscrire(
        organisation, formule_pro, doter_immediatement=False
    )
    services.appliquer_echeance(abonnement, periode="2026-09")
    assert services.appliquer_echeance(abonnement, periode="2026-09") == 0
    assert credits.solde(organisation) == 3


def test_un_report_integral_conserve_le_solde(organisation: Organisation) -> None:
    """Contre-épreuve de l'expiration : elle ne doit s'appliquer qu'aux formules sans report."""
    formule = Formule.objects.create(
        libelle="Report total", code="report-total", credits_par_echeance=3,
        report_credits=ReportCredits.INTEGRAL,
    )
    abonnement = services.souscrire(organisation, formule, doter_immediatement=False)
    credits.crediter(organisation, 2, motif="Reste du mois précédent")
    services.appliquer_echeance(abonnement, periode="2026-09")
    assert credits.solde(organisation) == 5


def test_un_report_plafonne_ne_conserve_que_le_plafond(
    organisation: Organisation,
) -> None:
    formule = Formule.objects.create(
        libelle="Report plafonné", code="report-plafonne", credits_par_echeance=3,
        report_credits=ReportCredits.PLAFONNE, plafond_report=1,
    )
    abonnement = services.souscrire(organisation, formule, doter_immediatement=False)
    credits.crediter(organisation, 4, motif="Reste du mois précédent")
    services.appliquer_echeance(abonnement, periode="2026-09")
    assert credits.solde(organisation) == 4  # 1 reporté + 3 dotés


def test_l_expiration_est_ecrite_au_journal_et_non_une_remise_a_zero(
    organisation: Organisation,
) -> None:
    """Le journal reste la seule vérité : un solde remis à zéro hors journal
    rendrait les deux chiffres incohérents."""
    credits.crediter(organisation, 4, motif="Dotation")
    credits.expirer_solde(organisation, periode="2026-08")
    expirations = organisation.portefeuille.mouvements.filter(
        type=TypeMouvement.EXPIRATION
    )
    assert expirations.count() == 1
    assert expirations.first().quantite == -4  # type: ignore[union-attr]
    assert credits.solde(organisation) == 0


def test_expirer_un_solde_nul_n_ecrit_rien(organisation: Organisation) -> None:
    assert credits.expirer_solde(organisation, periode="2026-08") is None


# ── Abonnement ───────────────────────────────────────────────────────────────


def test_souscrire_resilie_l_abonnement_precedent(
    organisation: Organisation, formule_pro: Formule
) -> None:
    """Changement de formule (§9.6). La base n'accepte qu'un abonnement actif."""
    autre = Formule.objects.create(
        libelle="Structure", code="structure", credits_par_echeance=10,
        prix_mensuel_cents=42_900,
    )
    premier = services.souscrire(organisation, formule_pro, doter_immediatement=False)
    second = services.souscrire(organisation, autre, doter_immediatement=False)

    premier.refresh_from_db()
    assert premier.statut == StatutAbonnement.RESILIE
    assert premier.fin_le is not None
    assert second.statut == StatutAbonnement.ACTIF
    assert organisation.abonnements.filter(statut=StatutAbonnement.ACTIF).count() == 1


def test_les_options_de_la_formule_descendent_sur_l_organisation(
    organisation: Organisation,
) -> None:
    formule = Formule.objects.create(
        libelle="Premium", code="premium", credits_par_echeance=5,
        validation_socle_par_client=True, controle_qualite_avant_envoi=True,
    )
    services.souscrire(organisation, formule, doter_immediatement=False)
    organisation.refresh_from_db()
    assert organisation.validation_socle_par_client
    assert organisation.controle_qualite_avant_envoi


def test_souscrire_dote_immediatement_par_defaut(
    organisation: Organisation, formule_pro: Formule
) -> None:
    services.souscrire(organisation, formule_pro)
    assert credits.solde(organisation) == 3


# ── Rôles et permissions (§12) ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("role", "action", "attendu"),
    [
        (RoleOrganisation.PROPRIETAIRE, "gerer_abonnement", True),
        (RoleOrganisation.PROPRIETAIRE, "commander", True),
        (RoleOrganisation.MEMBRE, "commander", True),
        (RoleOrganisation.MEMBRE, "gerer_membres", False),
        (RoleOrganisation.MEMBRE, "consulter_factures", False),
        (RoleOrganisation.LECTURE, "consulter_livrables", True),
        (RoleOrganisation.LECTURE, "commander", False),
        (RoleOrganisation.LECTURE, "gerer_clients_finaux", False),
    ],
)
def test_les_droits_suivent_le_tableau_du_cahier_des_charges(
    organisation: Organisation, role: str, action: str, attendu: bool
) -> None:
    autre = Customer.objects.create(email=f"{role}-{action}@example.com")
    membre = services.inviter_membre(organisation, autre, role=role)
    assert services.peut(membre, action) is attendu


@pytest.mark.parametrize("role", list(RoleOrganisation))
@pytest.mark.parametrize(
    "action", ["corriger_socle", "relancer_generation", "doter_credits"]
)
def test_aucun_role_d_organisation_n_obtient_les_droits_d_evkha(
    organisation: Organisation, role: str, action: str
) -> None:
    """Corriger un socle ou doter un compte reste réservé à EVKHA (§12)."""
    autre = Customer.objects.create(email=f"admin-{role}-{action}@example.com")
    membre = services.inviter_membre(organisation, autre, role=role)
    assert not services.peut(membre, action)


def test_un_membre_revoque_perd_tous_ses_droits(
    organisation: Organisation,
) -> None:
    """Sans ce contrôle, révoquer un accès ne révoquerait rien."""
    autre = Customer.objects.create(email="revoque@example.com")
    membre = services.inviter_membre(
        organisation, autre, role=RoleOrganisation.PROPRIETAIRE
    )
    assert services.peut(membre, "commander")
    services.revoquer_membre(membre)
    assert not services.peut(membre, "commander")
    assert not services.peut(membre, "consulter_livrables")


def test_exiger_leve_une_erreur_explicite(organisation: Organisation) -> None:
    autre = Customer.objects.create(email="lecture@example.com")
    membre = services.inviter_membre(
        organisation, autre, role=RoleOrganisation.LECTURE
    )
    with pytest.raises(services.AccesRefuseError) as echec:
        services.exiger(membre, "commander")
    assert "commander" in str(echec.value)


def test_le_dernier_proprietaire_ne_peut_pas_etre_revoque(
    organisation: Organisation, contact: Customer
) -> None:
    """Sinon l'organisation devient inadministrable et il faut intervenir en base."""
    proprietaire = MembreOrganisation.objects.get(
        organisation=organisation, customer=contact
    )
    with pytest.raises(services.AccesRefuseError):
        services.revoquer_membre(proprietaire)
    proprietaire.refresh_from_db()
    assert proprietaire.actif


def test_un_proprietaire_peut_etre_revoque_s_il_en_reste_un_autre(
    organisation: Organisation, contact: Customer
) -> None:
    """Contre-épreuve : le garde-fou ne doit pas empêcher un départ légitime."""
    second = Customer.objects.create(email="second-proprio@example.com")
    services.inviter_membre(
        organisation, second, role=RoleOrganisation.PROPRIETAIRE
    )
    premier = MembreOrganisation.objects.get(
        organisation=organisation, customer=contact
    )
    services.revoquer_membre(premier)
    premier.refresh_from_db()
    assert not premier.actif


def test_reinviter_un_membre_revoque_reactive_son_acces(
    organisation: Organisation,
) -> None:
    """Une révocation suivie d'une nouvelle invitation est un cas normal."""
    autre = Customer.objects.create(email="reinvite@example.com")
    membre = services.inviter_membre(organisation, autre)
    services.revoquer_membre(membre)
    reactive = services.inviter_membre(
        organisation, autre, role=RoleOrganisation.LECTURE
    )
    assert reactive.pk == membre.pk
    assert reactive.actif
    assert reactive.role == RoleOrganisation.LECTURE
    assert (
        MembreOrganisation.objects.filter(
            organisation=organisation, customer=autre
        ).count()
        == 1
    )


# ── Clients finaux et charte ─────────────────────────────────────────────────


@pytest.fixture
def client_final(organisation: Organisation) -> ClientFinal:
    return ClientFinal.objects.create(
        organisation=organisation,
        raison_sociale="Joalie",
        secteur="joaillerie de créateurs",
        pays="France",
        logo_url="https://exemple.test/logo.png",
        couleur_principale="#3A132C",
        couleur_secondaire="#B98B4E",
        couleur_fond="#F1EEDB",
    )


def test_la_charte_du_client_final_alimente_le_moteur_de_rendu(
    client_final: ClientFinal,
) -> None:
    """La correspondance vit ici, pas dans le moteur de rendu (règle 5)."""
    charte = services.charte_du_client_final(client_final)
    assert charte == {
        "nom": "Joalie",
        "logo_url": "https://exemple.test/logo.png",
        "couleur_principale": "#3A132C",
        "couleur_secondaire": "#B98B4E",
        "couleur_fond": "#F1EEDB",
    }


def test_la_charte_produit_bien_la_palette_de_reference(
    client_final: ClientFinal,
) -> None:
    """Bout en bout : la fiche client doit rendre la charte mesurée sur la référence."""
    from generation.rendu_word.palette import REF_CREME, REF_PRUNE, construire_palette

    charte = services.charte_du_client_final(client_final)
    palette = construire_palette(
        primaire=charte["couleur_principale"],
        secondaire=charte["couleur_secondaire"],
        fond_clair=charte["couleur_fond"],
    )
    assert palette.primaire == REF_PRUNE
    assert palette.fond_clair == REF_CREME


def test_archiver_un_client_final_ne_le_supprime_pas(
    organisation: Organisation, client_final: ClientFinal
) -> None:
    """« Archivage d'une fiche sans perte des documents déjà produits » (§9.2)."""
    services.archiver_client_final(client_final)
    client_final.refresh_from_db()
    assert client_final.archive
    assert ClientFinal.objects.filter(pk=client_final.pk).exists()
    assert services.clients_finaux_actifs(organisation) == []


def test_un_client_final_actif_reste_listable(
    organisation: Organisation, client_final: ClientFinal
) -> None:
    assert services.clients_finaux_actifs(organisation) == [client_final]


def test_deux_clients_finaux_de_meme_nom_sont_refuses(
    organisation: Organisation, client_final: ClientFinal
) -> None:
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        ClientFinal.objects.create(
            organisation=organisation, raison_sociale="Joalie"
        )


# ── Formules du site ─────────────────────────────────────────────────────────


def test_les_formules_du_site_sont_creees_avec_les_bons_montants() -> None:
    """Valeurs relevées sur evkha.fr : elles doivent survivre au peuplement."""
    from django.core.management import call_command

    call_command("seed_formules", verbosity=0)
    attendus = {"solo": (2, 12_900), "pro": (3, 18_900),
                "pro-plus": (5, 24_900), "structure": (10, 42_900)}
    for code, (credits_mois, prix) in attendus.items():
        formule = Formule.objects.get(code=code)
        assert formule.credits_par_echeance == credits_mois
        assert formule.prix_mensuel_cents == prix
        assert formule.report_credits == ReportCredits.AUCUN


def test_le_peuplement_n_ecrase_pas_un_reglage_fait_en_administration() -> None:
    """« Une formule se modifie sans déploiement » : le seed ne doit pas défaire ça."""
    from django.core.management import call_command

    call_command("seed_formules", verbosity=0)
    formule = Formule.objects.get(code="pro")
    formule.credits_par_echeance = 4
    formule.save()

    call_command("seed_formules", verbosity=0)
    formule.refresh_from_db()
    assert formule.credits_par_echeance == 4, "Le réglage admin a été écrasé."


def test_le_peuplement_force_realigne_sur_les_valeurs_du_site() -> None:
    """Contre-épreuve : l'échappatoire existe et fonctionne."""
    from django.core.management import call_command

    call_command("seed_formules", verbosity=0)
    formule = Formule.objects.get(code="pro")
    formule.credits_par_echeance = 4
    formule.save()

    call_command("seed_formules", "--forcer", verbosity=0)
    formule.refresh_from_db()
    assert formule.credits_par_echeance == 3


def test_le_cout_par_livrable_correspond_a_l_affichage_du_site() -> None:
    """Le site annonce 64,50 / 63 / 49,80 / 42,90 € par livrable inclus.

    Si une formule est modifiée sans que la page publique le soit, les deux se
    contredisent devant le client. Ce test rend l'écart visible.
    """
    from django.core.management import call_command

    call_command("seed_formules", verbosity=0)
    affiches = {"solo": 64.50, "pro": 63.00, "pro-plus": 49.80, "structure": 42.90}
    for code, attendu in affiches.items():
        formule = Formule.objects.get(code=code)
        calcule = formule.prix_mensuel_cents / 100 / formule.credits_par_echeance
        assert calcule == pytest.approx(attendu, abs=0.01), code


# ── Cohérence avec l'existant ────────────────────────────────────────────────


def test_les_codes_de_formule_couvrent_les_paliers_deja_declares() -> None:
    """`customers.SubscriptionTier` existe depuis le flux Systeme.io.

    Deux listes de paliers qui divergent, c'est le défaut récurrent de ce dépôt
    (règle 5). Ce test échoue si un palier est ajouté d'un côté seulement.
    """
    from django.core.management import call_command

    from customers.models import SubscriptionTier

    call_command("seed_formules", verbosity=0)
    codes = {formule.code.replace("-", "_") for formule in Formule.objects.all()}
    assert {palier.value for palier in SubscriptionTier} <= codes


# ── Supervision (espace administrateur) ──────────────────────────────────────


def test_la_synthese_dit_la_nature_du_revenu(client: object) -> None:
    """Un chiffre dont on ignore la nature est un chiffre faux.

    Ce test verrouillait l'état d'avant : « aucun prestataire de paiement
    n'étant branché, la plateforme ne connaît aucun encaissement réel ». C'était
    exact jusqu'au 07/08/2026. Stripe est désormais branché, chaque facture
    payée laisse une ligne, et cet avertissement serait devenu FAUX — donc pire
    que pas d'avertissement du tout, parce qu'on ne cherche pas ce qu'on croit
    impossible.

    Ce que le test tient désormais : les deux revenus sont donnés SÉPARÉMENT,
    et la réponse dit lequel est lequel. Les confondre, ou n'en montrer qu'un,
    ferait passer un impayé pour une recette.
    """
    reponse = _administration().get("/api/dashboard/supervision/synthese/")
    assert reponse.status_code == 200
    revenu = reponse.json()["revenu"]

    assert revenu["nature"] == "contractuel"
    assert "recurrent_mensuel_cents" in revenu
    assert "encaisse_periode_cents" in revenu
    assert "encaisse_total_cents" in revenu
    # L'avertissement explique la difference entre les deux.
    assert "contractuel" in revenu["avertissement"]
    assert "impayé" in revenu["avertissement"]
    # Et il n'affirme plus ce qui n'est plus vrai.
    assert "aucun prestataire" not in revenu["avertissement"].lower()


def test_la_synthese_compte_le_revenu_des_abonnements_actifs(
    organisation: Organisation, formule_pro: Formule
) -> None:
    services.souscrire(organisation, formule_pro, doter_immediatement=False)
    charge = _administration().get("/api/dashboard/supervision/synthese/").json()
    assert charge["revenu"]["recurrent_mensuel_cents"] == 18_900


def test_un_abonnement_resilie_ne_compte_plus_dans_le_revenu(
    organisation: Organisation, formule_pro: Formule
) -> None:
    """Contre-épreuve : sans cela le revenu ne ferait que croître."""
    abonnement = services.souscrire(organisation, formule_pro, doter_immediatement=False)
    abonnement.statut = StatutAbonnement.RESILIE
    abonnement.save(update_fields=["statut"])
    charge = _administration().get("/api/dashboard/supervision/synthese/").json()
    assert charge["revenu"]["recurrent_mensuel_cents"] == 0


def test_l_evolution_couvre_douze_mois_meme_sans_activite() -> None:
    """Omettre les mois vides ferait d'un creux une ligne qui saute : le
    graphique mentirait sur la forme de la courbe."""
    charge = _administration().get("/api/dashboard/supervision/evolution/").json()
    assert len(charge["mois"]) == 12
    for serie in charge["series"]:
        assert len(serie["valeurs"]) == 12


def test_la_supervision_expose_le_solde_et_la_consommation_par_organisation(
    organisation: Organisation,
) -> None:
    credits.crediter(organisation, 5, motif="Dotation")
    credits.debiter(organisation, 2, reference="job-supervision", motif="Étude")

    charge = _administration().get("/api/dashboard/supervision/organisations/").json()
    ligne = next(
        o for o in charge["organisations"] if o["raison_sociale"] == "Agence Test"
    )
    assert ligne["solde"] == 3
    assert ligne["credits_consommes"] == 2

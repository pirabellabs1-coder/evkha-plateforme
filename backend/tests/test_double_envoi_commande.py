"""Deux clics sur « Commander » ne doivent pas produire deux études payées.

Chaque POST fabriquait un `systeme_order_id` neuf — `uuid4()` —, donc une
commande neuve, donc un `GenerationJob` neuf. Or le débit est idempotent par
JOB : `reference_de_debit` vaut `f"job:{job.id}"`. Deux jobs, deux références,
deux débits.

La garantie « aucun double débit » était donc vraie à la lettre et sans effet
sur le seul chemin où le client peut la déclencher lui-même : un double-clic,
un navigateur qui rejoue la requête, un réseau qui hésite.

Ce qui est refusé, c'est la MÊME soumission deux fois de suite — pas le même
contenu pour toujours : recommander la même étude un an plus tard est
parfaitement légitime.
"""
from __future__ import annotations

from typing import Any

import pytest

from organisations import commandes, credits, inscription

pytestmark = pytest.mark.django_db

EMAIL = "claire@cabinet-duval.fr"


@pytest.fixture
def atelier() -> Any:
    from customers.models import Customer
    from organisations.models import TypeMouvement

    organisation = inscription.ouvrir_compte(
        raison_sociale="Cabinet Duval",
        email=EMAIL,
        mot_de_passe="un-mot-de-passe-solide-42",
        activer_abonnement=False,
    ).organisation
    credits.crediter(
        organisation, 10, motif="Dotation", reference="dot",
        type_mouvement=TypeMouvement.DOTATION,
    )

    class Atelier:
        pass

    Atelier.organisation = organisation
    Atelier.demandeur = Customer.objects.get(email=EMAIL)
    return Atelier


#: Une saisie complète d'étude de marché, telle que le questionnaire l'exige.
def _saisie() -> dict[str, str]:
    from organisations import formulaires

    questionnaire = formulaires.formulaire("market_study")
    assert questionnaire is not None
    return {
        champ.identifiant: "Vente de voitures d'occasion à Paris"
        for champ in questionnaire.champs
    }


def _commander(atelier: Any) -> Any:
    return commandes.creer_commande(
        atelier.organisation,
        demandeur=atelier.demandeur,
        type_document="market_study",
        saisie=_saisie(),
    )


# ── Le double envoi ──────────────────────────────────────────────────────────


def test_deux_envois_identiques_ne_font_qu_une_etude(atelier: Any) -> None:
    """Le test qui échoue sur le code d'avant : deux jobs étaient créés."""
    from generation.models import GenerationJob

    premier = _commander(atelier)
    second = _commander(atelier)

    assert second.id == premier.id, "deux etudes creees pour un double envoi"
    assert GenerationJob.objects.count() == 1


def test_le_double_envoi_ne_debite_pas_deux_fois(atelier: Any) -> None:
    """La conséquence qui compte : l'argent.

    Le débit se fait au lancement, par job. Deux jobs auraient produit deux
    références distinctes, donc deux débits — l'idempotence n'y pouvait rien.
    """
    from organisations import liaison

    premier = _commander(atelier)
    second = _commander(atelier)

    liaison.debiter_pour_job(premier)
    liaison.debiter_pour_job(second)

    assert credits.solde(atelier.organisation) == 9, (
        f"solde {credits.solde(atelier.organisation)} : le double envoi a ete facture"
    )


def test_l_appelant_recoit_son_etude_et_pas_une_erreur(atelier: Any) -> None:
    """Refuser d'un message d'erreur serait faux : la commande a bien été prise.

    La personne vient de cliquer deux fois sur le bouton d'une action qui a
    réussi. Lui répondre « commande déjà passée » la ferait douter de la
    première.
    """
    premier = _commander(atelier)
    second = _commander(atelier)

    assert second.id == premier.id
    assert second.status == premier.status


# ── Ce que le correctif ne doit PAS empêcher ─────────────────────────────────


def test_une_saisie_differente_cree_bien_une_seconde_etude(atelier: Any) -> None:
    """Contre-épreuve : deux études distinctes restent deux études."""
    from generation.models import GenerationJob

    premier = _commander(atelier)

    autre = _saisie()
    premiere_cle = next(iter(autre))
    autre[premiere_cle] = "Vente de voitures d'occasion à Lyon"
    second = commandes.creer_commande(
        atelier.organisation,
        demandeur=atelier.demandeur,
        type_document="market_study",
        saisie=autre,
    )

    assert second.id != premier.id
    assert GenerationJob.objects.count() == 2


def test_la_meme_etude_reste_commandable_plus_tard(atelier: Any) -> None:
    """La fenêtre vise le double-clic, pas une unicité définitive du contenu.

    Recommander la même étude après un délai est légitime — un marché bouge,
    et l'abonné peut vouloir une actualisation.
    """
    from django.utils import timezone

    from orders.models import Order

    premier = _commander(atelier)

    # On recule la commande au-delà de la fenêtre, comme le ferait le temps.
    Order.objects.filter(pk=premier.order.pk).update(
        created_at=timezone.now() - commandes.FENETRE_ANTI_DOUBLON * 2
    )

    second = _commander(atelier)
    assert second.id != premier.id, "impossible de recommander la meme etude"


def test_deux_organisations_ne_se_bloquent_pas_l_une_l_autre(atelier: Any) -> None:
    """Cloisonnement : la fenêtre est propre à chaque organisation.

    Deux agences peuvent commander la même étude le même jour — c'est même
    attendu sur un sujet d'actualité.
    """
    from customers.models import Customer
    from organisations.models import TypeMouvement

    voisine = inscription.ouvrir_compte(
        raison_sociale="Agence Rivage",
        email="rivage@exemple.fr",
        mot_de_passe="un-autre-mot-de-passe-42",
        activer_abonnement=False,
    ).organisation
    credits.crediter(
        voisine, 5, motif="Dotation", reference="dot-2",
        type_mouvement=TypeMouvement.DOTATION,
    )

    premier = _commander(atelier)
    second = commandes.creer_commande(
        voisine,
        demandeur=Customer.objects.get(email="rivage@exemple.fr"),
        type_document="market_study",
        saisie=_saisie(),
    )

    assert second.id != premier.id, "une agence a bloque la commande d'une autre"


# ── Là où deux correctifs de la même session se détruisaient ─────────────────


def test_apres_un_abandon_l_abonne_peut_recommander_la_meme_etude(
    atelier: Any,
) -> None:
    """Le test qui manquait, et qui a laissé passer un défaut réel.

    Enchaînement rejoué sur les vraies routes par une relecture adversariale :

    1. l'étude échoue ;
    2. le client clique « Renoncer », son crédit revient ;
    3. il recommande la même étude — geste que l'écran l'invite explicitement à
       faire (« Vous pouvez commander une nouvelle étude quand vous le
       souhaitez ») ;
    4. la fenêtre anti-doublon retrouvait la commande d'origine et lui rendait
       le job ANNULÉ ET REMBOURSÉ ;
    5. la vue répondait « commande acceptée », relançait ce job mort, et
       `debiter_pour_job` le refusait puisque les crédits avaient été restitués.

    Dix minutes durant, le client ne pouvait plus commander, avec un
    portefeuille plein et un écran affichant un échec.

    Les deux correctifs — anti-doublon et refus de relance après remboursement —
    sont justes séparément. Aucun test ne les croisait : `test_double_envoi`
    n'abandonnait jamais, `test_remboursement` ne repassait jamais par
    `creer_commande`.
    """
    from generation.models import GenerationJob, JobStatus
    from organisations import liaison

    premier = _commander(atelier)
    liaison.debiter_pour_job(premier)
    GenerationJob.objects.filter(pk=premier.pk).update(status=JobStatus.FAILED)

    # Le client renonce : son crédit revient.
    premier.refresh_from_db()
    GenerationJob.objects.filter(pk=premier.pk).update(status=JobStatus.CANCELLED)
    premier.refresh_from_db()
    assert liaison.rembourser_job(premier, motif="Abandon client")
    assert credits.solde(atelier.organisation) == 10

    # Il recommande aussitôt la même étude.
    second = _commander(atelier)

    assert second.id != premier.id, (
        "la fenetre anti-doublon a rendu le job abandonne : le client est "
        "enferme jusqu'a expiration de la fenetre"
    )
    autorise, raison = liaison.debiter_pour_job(second)
    assert autorise, raison
    assert credits.solde(atelier.organisation) == 9


def test_un_job_annule_sans_remboursement_n_est_pas_rendu_non_plus(
    atelier: Any,
) -> None:
    """La CLASSE, pas le seul cas du remboursement (règle 4).

    On énumère ce qui SERT — en attente, en cours, terminé, en échec — jamais
    ce qui ne sert pas. Un statut ajouté demain serait sinon considéré
    utilisable par défaut, et le défaut reviendrait sous une autre forme.
    """
    from generation.models import GenerationJob, JobStatus

    premier = _commander(atelier)
    GenerationJob.objects.filter(pk=premier.pk).update(status=JobStatus.CANCELLED)

    assert _commander(atelier).id != premier.id


def test_un_job_en_echec_RECUPERABLE_est_toujours_rendu(atelier: Any) -> None:
    """Contre-épreuve : le double-clic reste un double-clic.

    Une étude en échec non abandonnée est relançable sans repayer — c'est ce
    que le §13 demande. La rendre est la bonne réponse à un second clic.
    """
    from generation.models import GenerationJob, JobStatus

    premier = _commander(atelier)
    GenerationJob.objects.filter(pk=premier.pk).update(status=JobStatus.FAILED)

    assert _commander(atelier).id == premier.id

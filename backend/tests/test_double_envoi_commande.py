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

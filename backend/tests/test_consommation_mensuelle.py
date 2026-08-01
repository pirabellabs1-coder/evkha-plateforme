"""Crédits reçus et consommés, mois par mois.

C'est la question qu'un abonné se pose : **ma formule est-elle la bonne ?** Le
journal ligne à ligne y répond mal — il faut additionner de tête sur des
dizaines de lignes.

L'agrégation est faite par le SERVEUR. Deux additions du même journal
finiraient par ne pas dire la même chose, et le graphique contredirait le
compteur affiché juste à côté (règle 5).
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

pytestmark = pytest.mark.django_db


@pytest.fixture
def espace(db: object) -> Any:
    """Une organisation, son propriétaire et un jeton de session."""
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from orders.models import Order
    from organisations import authentification, services

    offre = Offer.objects.create(name="EM", slug="em-conso",
                                 deliverable_type=DeliverableType.MARKET_STUDY)
    contact = Customer.objects.create(email="conso@exemple.fr")
    Order.objects.create(systeme_order_id="ord-conso", customer=contact,
                         offer=offre)
    organisation = services.creer_organisation(
        raison_sociale="Cabinet Conso", contact=contact
    )
    authentification.creer_compte(contact, mot_de_passe="un-mot-de-passe-long-42")
    jeton, _ = authentification.ouvrir_session(
        "conso@exemple.fr", "un-mot-de-passe-long-42"
    )
    return organisation, jeton


def _lire(client: Client, jeton: str) -> Any:
    reponse = client.get(
        "/api/espace/consommation/", HTTP_AUTHORIZATION=f"Bearer {jeton}"
    )
    assert reponse.status_code == 200, reponse.content
    return reponse.json()


def _dater(mouvement: Any, recul_jours: int) -> None:
    """Recule la date d'un mouvement. `auto_now_add` impose une reecriture."""
    if not recul_jours:
        return
    type(mouvement).objects.filter(pk=mouvement.pk).update(
        created_at=timezone.now() - timedelta(days=recul_jours)
    )


def _crediter(organisation: Any, quantite: int, *, recul_jours: int = 0) -> None:
    """Passe par le SERVICE, jamais par un `create` direct.

    Une première version de ce test fabriquait les mouvements à la main et
    écrivait des débits POSITIFS. Le solde, qui est une simple somme du
    journal, montait alors au lieu de descendre : le test validait une
    arithmétique que le produit ne produit jamais (règle 6 — un test doit
    exercer le vrai chemin, sinon il verrouille une fiction).
    """
    from organisations import credits
    from organisations.models import TypeMouvement

    mouvement = credits.crediter(
        organisation, quantite, motif="essai",
        type_mouvement=TypeMouvement.DOTATION,
    )
    _dater(mouvement, recul_jours)


def _debiter(organisation: Any, quantite: int, *, reference: str,
             recul_jours: int = 0) -> None:
    from organisations import credits

    mouvement = credits.debiter(
        organisation, quantite, reference=reference, motif="essai"
    )
    _dater(mouvement, recul_jours)


def test_les_douze_mois_sont_toujours_rendus(espace: Any, client: Client) -> None:
    """Un mois sans mouvement doit apparaître à zéro.

    Un graphique qui saute les mois vides laisse croire à une consommation
    continue alors qu'il y a eu des mois blancs — et c'est précisément ce qu'un
    abonné regarde pour juger sa formule.
    """
    _organisation, jeton = espace
    from organisations.vues_espace import MOIS_HISTORIQUE

    mois = _lire(client, jeton)["mois"]
    assert len(mois) == MOIS_HISTORIQUE
    assert all(m["recus"] == 0 and m["consommes"] == 0 for m in mois)


def test_aucun_mois_n_apparait_deux_fois(espace: Any, client: Client) -> None:
    """Le pas de trente jours peut retomber deux fois dans le même mois.

    Sans garde, février se serait affiché en double — et la somme des colonnes
    aurait cessé de correspondre au total annoncé.
    """
    _organisation, jeton = espace
    cles = [m["mois"] for m in _lire(client, jeton)["mois"]]
    assert len(cles) == len(set(cles)), cles


def test_les_entrees_et_les_sorties_sont_separees(
    espace: Any, client: Client
) -> None:
    organisation, jeton = espace
    _crediter(organisation, 5)
    _debiter(organisation, 2, reference="cmd-1")

    charge = _lire(client, jeton)
    assert charge["total_recu"] == 5
    assert charge["total_consomme"] == 2
    assert charge["mois"][-1]["recus"] == 5
    assert charge["mois"][-1]["consommes"] == 2


def test_un_remboursement_reduit_la_consommation(
    espace: Any, client: Client
) -> None:
    """`REMBOURSEMENT` est positif au journal et figure dans les SORTIES.

    L'additionner comme une sortie gonflerait la consommation du mois où l'on a
    justement rendu des crédits au client — le graphique accuserait le client
    de ce qu'on lui a remboursé.
    """
    from organisations import credits
    from organisations.models import TypeMouvement

    organisation, jeton = espace
    _crediter(organisation, 10)
    _debiter(organisation, 3, reference="cmd-2")
    credits.crediter(
        organisation, 1, motif="regeneration ratee",
        type_mouvement=TypeMouvement.REMBOURSEMENT,
    )

    assert _lire(client, jeton)["total_consomme"] == 2


def test_les_mouvements_anciens_sortent_de_la_fenetre(
    espace: Any, client: Client
) -> None:
    """Contre-épreuve de la fenêtre : au-delà, la courbe écrase les mois récents."""
    organisation, jeton = espace
    _crediter(organisation, 99, recul_jours=500)
    _debiter(organisation, 99, reference="cmd-ancienne", recul_jours=500)

    charge = _lire(client, jeton)
    assert charge["total_consomme"] == 0
    assert charge["total_recu"] == 0


def test_l_agregation_concorde_avec_le_journal(espace: Any, client: Client) -> None:
    """Règle 5 : le graphique et le compteur doivent dire la même chose.

    S'ils divergent, l'abonné voit un solde qui ne correspond pas à ce qu'il
    lit juste au-dessus, et ne sait plus lequel croire.
    """
    organisation, jeton = espace
    _crediter(organisation, 10)
    _debiter(organisation, 4, reference="cmd-3")

    charge = _lire(client, jeton)
    journal = client.get(
        "/api/espace/credits/", HTTP_AUTHORIZATION=f"Bearer {jeton}"
    ).json()
    assert charge["total_recu"] - charge["total_consomme"] == journal["solde"]


def test_l_agregation_exige_une_session(client: Client) -> None:
    assert client.get("/api/espace/consommation/").status_code == 401

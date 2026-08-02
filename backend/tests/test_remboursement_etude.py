"""Un crédit payé pour un document jamais reçu doit revenir — sans écrire à personne.

Le crédit est débité au lancement de la génération. `rembourser_job` existait,
était testée, et **n'était appelée par aucun chemin du produit** : la recherche
ne la trouvait que dans ses propres tests. Le module `credits` annonce pourtant
en tête « Aucun crédit perdu sur échec », et `commandes.py` bâtit son ordre des
opérations sur « le remboursement automatique ». Garantie écrite deux fois,
tenue zéro fois (règles 1 et 8).

**Le piège, et c'est lui qui a dicté la conception.** La correction évidente —
rembourser dès la bascule en `FAILED` — était un trou de caisse. `FAILED` est
rattrapable dans ce dépôt, et `debiter_pour_job` traite une référence déjà
consommée comme « autorisé, pas de nouveau débit ». Après un remboursement, la
ligne de débit reste en place : la relance passait donc le contrôle et
produisait l'étude **gratuitement**. La docstring de `rembourser_job` nommait ce
risque ; rien ne l'empêchait.

Le remboursement est donc lié à un abandon EXPLICITE, et un abandon interdit la
relance — contrôlé dans la couche qui tient l'argent, pas dans une vue.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from organisations import credits, inscription, liaison

pytestmark = pytest.mark.django_db

EMAIL = "claire@cabinet-duval.fr"
MOT_DE_PASSE = "un-mot-de-passe-solide-42"


@pytest.fixture
def atelier() -> Any:
    """Une organisation dotée, une commande, un job — par les vrais chemins."""
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import GenerationJob, JobStatus
    from orders.models import Order
    from organisations.models import TypeMouvement

    ouverture = inscription.ouvrir_compte(
        raison_sociale="Cabinet Duval",
        email=EMAIL,
        mot_de_passe=MOT_DE_PASSE,
        activer_abonnement=False,
    )
    organisation = ouverture.organisation
    credits.crediter(
        organisation, 5, motif="Dotation", reference="dot-1",
        type_mouvement=TypeMouvement.DOTATION,
    )

    offre = Offer.objects.create(
        name="Étude de marché",
        slug="etude-remboursement",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    contact = Customer.objects.get(email=EMAIL)
    commande = Order.objects.create(
        systeme_order_id="cmd-remboursement",
        customer=contact,
        offer=offre,
        organisation=organisation,
    )

    class Atelier:
        pass

    Atelier.organisation = organisation
    Atelier.commande = commande
    Atelier.offre = offre

    def nouveau_job(statut: str = JobStatus.FAILED) -> Any:
        return GenerationJob.objects.create(
            order=commande,
            deliverable_type=DeliverableType.MARKET_STUDY,
            status=statut,
        )

    Atelier.nouveau_job = staticmethod(nouveau_job)
    return Atelier


def _jeton() -> str:
    from organisations import authentification

    jeton, _ = authentification.ouvrir_session(EMAIL, MOT_DE_PASSE)
    return str(jeton)


def _abandonner(client: Any, job: Any) -> Any:
    return client.post(
        f"/api/espace/livrables/{job.id}/abandonner/",
        data=json.dumps({}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {_jeton()}",
    )


# ── Le crédit revient ────────────────────────────────────────────────────────


def test_abandonner_une_etude_en_echec_rend_le_credit(
    client: Any, atelier: Any
) -> None:
    """Le test qui échoue sur le code d'avant : la route n'existait pas.

    Le seul recours était une demande commerciale traitée à la main — un
    parcours qui oblige à contacter un humain, ce que ce produit exclut.
    """
    job = atelier.nouveau_job()
    autorise, _ = liaison.debiter_pour_job(job)
    assert autorise
    assert credits.solde(atelier.organisation) == 4

    reponse = _abandonner(client, job)

    assert reponse.status_code == 200, reponse.content
    charge = reponse.json()
    assert charge["credits_restitues"] is True
    assert charge["solde"] == 5
    assert credits.solde(atelier.organisation) == 5


def test_le_mouvement_de_remboursement_est_trace(client: Any, atelier: Any) -> None:
    """Un crédit qui revient sans ligne au journal serait un solde inexpliqué."""
    from organisations.models import TypeMouvement

    job = atelier.nouveau_job()
    liaison.debiter_pour_job(job)
    _abandonner(client, job)

    ligne = (
        credits.portefeuille_de(atelier.organisation)
        .mouvements.filter(type=TypeMouvement.REMBOURSEMENT)
        .first()
    )
    assert ligne is not None
    assert ligne.reference == liaison.reference_de_debit(job)
    assert "abandonn" in ligne.motif.lower()


# ── Le trou de caisse que la correction évidente aurait ouvert ───────────────


def test_une_etude_remboursee_ne_peut_plus_etre_relancee_gratuitement(
    client: Any, atelier: Any
) -> None:
    """LE test de ce fichier.

    Enchaînement complet : débit, remboursement, relance. La ligne de débit
    existe toujours après le remboursement — `debiter_pour_job` aurait donc
    répondu « déjà débité, on relance sans repayer », et l'étude aurait été
    produite gratuitement, crédit rendu ET document livré.
    """
    job = atelier.nouveau_job()
    liaison.debiter_pour_job(job)
    _abandonner(client, job)
    assert credits.solde(atelier.organisation) == 5

    autorise, raison = liaison.debiter_pour_job(job)

    assert not autorise, "l'etude serait produite gratuitement"
    assert "restitu" in raison.lower()
    assert credits.solde(atelier.organisation) == 5


def test_une_relance_ordinaire_reste_possible(client: Any, atelier: Any) -> None:
    """Contre-épreuve : le correctif ne doit pas casser la reprise sur incident.

    Une étude en échec NON abandonnée doit pouvoir repartir sans repayer —
    c'est ce que le §13 demande, et c'était le motif d'origine du « déjà
    débité → autorisé ».
    """
    job = atelier.nouveau_job()
    liaison.debiter_pour_job(job)

    autorise, raison = liaison.debiter_pour_job(job)

    assert autorise, raison
    assert credits.solde(atelier.organisation) == 4, "la relance a repaye"


# ── Ce que l'abandon refuse ──────────────────────────────────────────────────


def test_une_etude_en_cours_ne_s_abandonne_pas(client: Any, atelier: Any) -> None:
    """Elle consomme déjà des appels facturés : rendre le crédit paierait EVKHA.

    C'est la contre-épreuve de périmètre : l'abandon répare un échec, il n'est
    pas un bouton « annuler quand ça prend du temps ».
    """
    from generation.models import JobStatus

    job = atelier.nouveau_job(JobStatus.RUNNING)
    liaison.debiter_pour_job(job)

    reponse = _abandonner(client, job)

    assert reponse.status_code == 409
    assert reponse.json()["code"] == "etat_incompatible"
    assert credits.solde(atelier.organisation) == 4


def test_une_etude_livree_ne_s_abandonne_pas(client: Any, atelier: Any) -> None:
    from generation.models import JobStatus

    job = atelier.nouveau_job(JobStatus.DONE)
    liaison.debiter_pour_job(job)

    assert _abandonner(client, job).status_code == 409
    assert credits.solde(atelier.organisation) == 4


def test_un_double_clic_ne_rend_pas_deux_credits(client: Any, atelier: Any) -> None:
    job = atelier.nouveau_job()
    liaison.debiter_pour_job(job)

    assert _abandonner(client, job).status_code == 200
    seconde = _abandonner(client, job)

    assert seconde.status_code == 409
    assert seconde.json()["code"] in {"deja_restitue", "etat_incompatible"}
    assert credits.solde(atelier.organisation) == 5


def test_l_etude_d_une_autre_organisation_est_invisible(
    client: Any, atelier: Any
) -> None:
    """Cloisonnement : le risque n°1 d'un SaaS B2B.

    Sans ce filtre, un identifiant deviné permettrait de faire annuler l'étude
    d'une autre agence — et de lui rendre un crédit qu'elle n'a pas demandé.
    """
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import GenerationJob, JobStatus
    from orders.models import Order

    autre = inscription.ouvrir_compte(
        raison_sociale="Agence Rivage",
        email="rivage@exemple.fr",
        mot_de_passe="un-autre-mot-de-passe-42",
        activer_abonnement=False,
    ).organisation
    offre = Offer.objects.create(
        name="Étude", slug="etude-rivage", deliverable_type=DeliverableType.MARKET_STUDY
    )
    commande = Order.objects.create(
        systeme_order_id="cmd-rivage",
        customer=Customer.objects.get(email="rivage@exemple.fr"),
        offer=offre,
        organisation=autre,
    )
    job_voisin = GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.MARKET_STUDY,
        status=JobStatus.FAILED,
    )

    reponse = _abandonner(client, job_voisin)

    assert reponse.status_code == 404, "une agence a atteint l'etude d'une autre"


# ── L'annulation depuis l'administration ─────────────────────────────────────


def test_annuler_depuis_l_administration_rend_le_credit(
    client_admin: Any, atelier: Any
) -> None:
    """L'annulation était l'abandon explicite que personne ne prononçait."""
    from generation.models import JobStatus

    job = atelier.nouveau_job(JobStatus.RUNNING)
    liaison.debiter_pour_job(job)
    assert credits.solde(atelier.organisation) == 4

    reponse = client_admin.post(f"/api/dashboard/jobs/{job.id}/cancel/")

    assert reponse.status_code == 200, reponse.content
    assert reponse.json()["credits_restitues"] is True
    assert credits.solde(atelier.organisation) == 5

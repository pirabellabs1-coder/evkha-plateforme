"""L'échéance mensuelle des abonnements B2B se déclenche toute seule.

`appliquer_echeance` existait depuis le lot 4 et n'était appelée que par
`souscrire` — la dotation initiale — et par une action manuelle de
l'administration Django. **Aucune tâche périodique.** Un abonné recevait donc
ses crédits une fois, à la souscription, et plus jamais : ni réinitialisation
en fin de mois, ni nouvelle dotation. Personne ne l'aurait vu avant la bascule
d'un mois sur l'autre, c'est-à-dire sur une facture.

Ces tests vérifient la tâche **et** son inscription à l'ordonnanceur. Une tâche
correcte que rien ne déclenche ne dote personne — c'était précisément l'état
d'avant, et un test qui n'exerce que la fonction ne l'aurait pas vu (règle 9 :
demandez-vous ce que votre contrôle ne regarde pas).
"""
from __future__ import annotations

import pytest
from django.conf import settings

from customers.models import Customer
from organisations import credits, services
from organisations.models import (
    Formule,
    Organisation,
    ReportCredits,
    StatutAbonnement,
    TypeMouvement,
)
from organisations.tasks import appliquer_echeances

pytestmark = pytest.mark.django_db

NOM_TACHE = "organisations.appliquer_echeances"


def _formule(code: str = "pro", credits_mois: int = 3) -> Formule:
    return Formule.objects.create(
        code=code,
        libelle=code.title(),
        credits_par_echeance=credits_mois,
        prix_mensuel_cents=18_900,
        devise="EUR",
        report_credits=ReportCredits.AUCUN,
        plafond_report=0,
        regenerations_offertes=1,
        active=True,
    )


def _organisation(email: str, raison: str) -> Organisation:
    contact = Customer.objects.create(email=email)
    return services.creer_organisation(raison_sociale=raison, contact=contact)


def _periode_precedente() -> str:
    """Le mois d'avant, dérivé de l'horloge et non écrit en dur.

    Une période codée en dur ferait passer ces tests aujourd'hui et échouer le
    mois prochain, sans qu'aucun changement de code l'explique.
    """
    annee, mois = (int(p) for p in services.periode_courante().split("-"))
    return f"{annee - 1}-12" if mois == 1 else f"{annee}-{mois - 1:02d}"


def _abonne_au_mois_precedent(organisation: Organisation, formule: Formule):  # type: ignore[no-untyped-def]
    """Abonné dont la dernière échéance date du mois d'avant.

    `souscrire` dote la période COURANTE : reculer ensuite le marqueur ne
    suffirait pas, la dotation du mois en cours existe déjà et `doter` la
    refuserait en doublon — son idempotence fonctionne. On souscrit donc sans
    dotation, puis on écrit celle du mois précédent.
    """
    abonnement = services.souscrire(
        organisation, formule, doter_immediatement=False
    )
    precedente = _periode_precedente()
    credits.doter(organisation, formule.credits_par_echeance, periode=precedente)
    abonnement.derniere_periode_dotee = precedente
    abonnement.save(update_fields=["derniere_periode_dotee"])
    return abonnement


# ── L'inscription à l'ordonnanceur ───────────────────────────────────────────


def test_la_tache_est_inscrite_a_l_ordonnanceur() -> None:
    """Sans cette entrée, la tâche est du code mort et personne n'est doté."""
    taches = {
        entree["task"] for entree in settings.CELERY_BEAT_SCHEDULE.values()
    }
    assert NOM_TACHE in taches, (
        "La tâche d'échéance n'est pas dans CELERY_BEAT_SCHEDULE : elle ne "
        "s'exécutera jamais en production."
    )


def test_la_verification_est_horaire_et_non_mensuelle() -> None:
    """Une exécution unique le 1er ne rattrape pas un worker arrêté ce jour-là."""
    entree = next(
        e for e in settings.CELERY_BEAT_SCHEDULE.values() if e["task"] == NOM_TACHE
    )
    planification = entree["schedule"]
    assert isinstance(planification, (int, float)), (
        "Une planification exprimée autrement qu'en secondes demande de "
        "vérifier à la main qu'elle passe plus d'une fois par mois."
    )
    assert planification <= 3600.0


# ── La tâche ─────────────────────────────────────────────────────────────────


def test_dote_un_abonnement_actif_a_la_periode_suivante() -> None:
    organisation = _organisation("mensuel@exemple.fr", "Mensuel")
    _abonne_au_mois_precedent(organisation, _formule(credits_mois=3))
    assert credits.solde(organisation) == 3

    resultat = appliquer_echeances()

    assert resultat["dotees"] == 1
    assert credits.solde(organisation) == 3, "réinitialisé à 3, pas cumulé à 6"


def test_ne_dote_pas_deux_fois_la_meme_periode() -> None:
    """Idempotence : la tâche tourne chaque heure, elle ne doit rien empiler."""
    organisation = _organisation("idempotent@exemple.fr", "Idempotent")
    services.souscrire(organisation, _formule(credits_mois=4))

    premier = appliquer_echeances()
    second = appliquer_echeances()

    assert premier["dotees"] == 0, "la souscription vient de doter la période"
    assert premier["deja_a_jour"] == 1
    assert second["deja_a_jour"] == 1
    assert credits.solde(organisation) == 4


def test_les_credits_achetes_traversent_l_echeance() -> None:
    """Le lien avec l'autre correctif : la réinitialisation épargne les achats."""
    organisation = _organisation("achats@exemple.fr", "Achats")
    _abonne_au_mois_precedent(organisation, _formule(credits_mois=2))
    credits.crediter(
        organisation, 3, motif="Achat de 3 crédits", type_mouvement=TypeMouvement.ACHAT
    )

    appliquer_echeances()

    detail = credits.detail_solde(organisation)
    assert detail.expirables == 2, "l'abonnement est reparti à 2"
    assert detail.perennes == 3, "les 3 crédits achetés sont intacts"


def test_ecarte_les_organisations_suspendues() -> None:
    """Doter une organisation suspendue reviendrait à livrer ce qu'on a coupé."""
    organisation = _organisation("suspendu@exemple.fr", "Suspendu")
    _abonne_au_mois_precedent(organisation, _formule(credits_mois=3))
    services.suspendre(organisation, motif="Impayé")

    resultat = appliquer_echeances()

    assert resultat["ecartees_suspendues"] == 1
    assert resultat["dotees"] == 0
    assert credits.solde(organisation) == 3, "le solde existant n'est pas touché"


def test_un_abonnement_resilie_n_est_plus_dote() -> None:
    """Il ne reçoit plus rien — c'est la moitié évidente de la règle."""
    organisation = _organisation("resilie@exemple.fr", "Résilié")
    abonnement = _abonne_au_mois_precedent(organisation, _formule(credits_mois=3))
    abonnement.statut = StatutAbonnement.RESILIE
    abonnement.save(update_fields=["statut"])

    resultat = appliquer_echeances()

    assert resultat["dotees"] == 0
    assert resultat["deja_a_jour"] == 0
    assert resultat["ecartees_suspendues"] == 0
    assert resultat["en_echec"] == 0


def test_la_reserve_d_un_resilie_expire_a_la_bascule_de_periode() -> None:
    """L'autre moitié, qui manquait — et qui laissait une fuite ouverte.

    `expirer_solde` n'était appelé que pour les abonnements ACTIFS. Une fois
    résilié, plus d'échéance, donc plus JAMAIS d'expiration : l'ancien abonné
    gardait sa réserve indéfiniment et continuait de consommer l'API, alors
    que sa formule annonce que les crédits non consommés expirent.

    On ne lui reprend rien au moment du clic — le mois en cours est payé. La
    réserve s'éteint à la bascule de période, ici.
    """
    from organisations import credits

    organisation = _organisation("fuite@exemple.fr", "Fuite")
    abonnement = _abonne_au_mois_precedent(organisation, _formule(credits_mois=3))
    credits.crediter(
        organisation, 5, motif="Reste du mois paye", reference="reste",
        type_mouvement=TypeMouvement.DOTATION,
    )
    abonnement.statut = StatutAbonnement.RESILIE
    abonnement.save(update_fields=["statut"])
    assert credits.solde(organisation) > 0

    resultat = appliquer_echeances()

    assert resultat["reserves_resiliees_expirees"] == 1
    assert credits.solde(organisation) == 0, (
        "l'ancien abonne garde sa reserve et continue de consommer l'API"
    )


def test_les_credits_ACHETES_survivent_a_la_resiliation() -> None:
    """Contre-épreuve : ce qui a été payé à part n'est pas de la réserve.

    Un abonné qui a acheté des crédits supplémentaires ne doit pas les perdre
    parce qu'il résilie son abonnement — ce sont deux transactions distinctes.
    """
    from organisations import credits

    organisation = _organisation("achete@exemple.fr", "Achat")
    abonnement = _abonne_au_mois_precedent(organisation, _formule(credits_mois=3))
    credits.crediter(
        organisation, 4, motif="Credits supplementaires", reference="achat-1",
        type_mouvement=TypeMouvement.ACHAT,
    )
    abonnement.statut = StatutAbonnement.RESILIE
    abonnement.save(update_fields=["statut"])

    appliquer_echeances()

    assert credits.solde(organisation) >= 4, (
        "les credits achetes ont ete purges avec la reserve d'abonnement"
    )


def test_un_abonnement_en_echec_n_empeche_pas_les_autres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sinon un seul cas cassé prive tous les abonnés suivants de leurs crédits.

    C'est la contre-épreuve de la boucle : elle doit continuer, et le dire.
    """
    casse = _organisation("casse@exemple.fr", "Casse")
    sain = _organisation("sain@exemple.fr", "Sain")
    for organisation, code in ((casse, "f-casse"), (sain, "f-sain")):
        _abonne_au_mois_precedent(organisation, _formule(code, credits_mois=3))

    vraie = services.appliquer_echeance

    def parfois_casse(abonnement, **kwargs):  # type: ignore[no-untyped-def]
        if abonnement.organisation_id == casse.id:
            msg = "panne simulée"
            raise RuntimeError(msg)
        return vraie(abonnement, **kwargs)

    monkeypatch.setattr(
        "organisations.tasks.services.appliquer_echeance", parfois_casse
    )

    resultat = appliquer_echeances()

    assert resultat["en_echec"] == 1
    assert resultat["dotees"] == 1, "l'abonné sain a bien été doté"
    assert credits.solde(sain) == 3

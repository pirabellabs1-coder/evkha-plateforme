"""Remettre la plateforme à zéro — et ne jamais le refaire par accident.

Demandé par la cliente le 07/08/2026, avant l'ouverture réelle : la base de
recette portait deux organisations d'essai, sept contacts, trente-huit
générations et quatre-vingt-cinq incidents accumulés pendant la mise au point.

Le danger n'est pas l'effacement, c'est sa RÉPÉTITION. L'API de Coolify
n'expose aucune exécution de commande dans le conteneur : la commande est donc
jouée au démarrage, et une variable d'environnement oubliée effacerait la base
à chaque redémarrage — y compris six mois plus tard, avec de vrais clients
dedans. D'où la confirmation datée, qui se périme d'elle-même à minuit.

Ces tests tiennent les deux moitiés :

1. avec la bonne phrase, tout part — et les compteurs sont à zéro ;
2. sans elle, avec celle d'hier, ou avec une variable vide, **rien** ne part ;
3. ce qui doit survivre survit : formules, catalogue, administratrice.
"""
from __future__ import annotations

from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.utils import timezone

from customers.models import Customer
from organisations.management.commands.reinitialiser_la_plateforme import (
    PREFIXE_CONFIRMATION,
    phrase_attendue,
)
from organisations.models import Formule, Organisation

from .aides_abonnement import formule_de_test


def _peupler() -> None:
    """Une plateforme habitée : contact, organisation, compte client."""
    from organisations import services

    formule_de_test()
    contact = Customer.objects.create(email="partenaire@exemple.fr")
    organisation = services.creer_organisation(
        raison_sociale="Agence de test", contact=contact
    )
    utilisateur = User.objects.create_user(
        username="partenaire@exemple.fr", password="motdepasse"
    )
    from organisations.models import CompteClient

    CompteClient.objects.create(user=utilisateur, customer=contact, actif=True)
    assert organisation.pk is not None


def _jouer(monkeypatch: pytest.MonkeyPatch, valeur: str | None) -> str:
    monkeypatch.delenv("EVKHA_REINITIALISER", raising=False)
    if valeur is not None:
        monkeypatch.setenv("EVKHA_REINITIALISER", valeur)
    sortie = StringIO()
    call_command("reinitialiser_la_plateforme", stdout=sortie)
    return sortie.getvalue()


@pytest.mark.django_db
def test_la_bonne_phrase_remet_tout_a_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _peupler()
    assert Organisation.objects.exists()

    sortie = _jouer(monkeypatch, phrase_attendue())

    assert not Organisation.objects.exists()
    assert not Customer.objects.exists()
    assert "remise a zero" in sortie


@pytest.mark.django_db
def test_les_formules_et_leurs_tarifs_stripe_survivent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Les recréer coûterait de recoller quatre `price_` à la main.

    Et une erreur de recopie ferait payer le mauvais montant à un client, sans
    qu'aucune alerte ne se déclenche — le pire genre de défaut.
    """
    _peupler()
    formule = Formule.objects.first()
    assert formule is not None
    formule.reference_paiement = "price_1Test"
    formule.save()

    _jouer(monkeypatch, phrase_attendue())

    formule.refresh_from_db()
    assert formule.reference_paiement == "price_1Test"


@pytest.mark.django_db
def test_l_administratrice_garde_son_compte(monkeypatch: pytest.MonkeyPatch) -> None:
    """L'effacer fermerait la porte de l'administration derrière elle."""
    _peupler()
    User.objects.create_superuser(username="admin@evkha.fr", password="secret")

    _jouer(monkeypatch, phrase_attendue())

    assert User.objects.filter(username="admin@evkha.fr").exists()
    # Le compte client, lui, part avec son contact : le laisser derriere
    # empecherait une reinscription avec la meme adresse.
    assert not User.objects.filter(username="partenaire@exemple.fr").exists()


# ── Le garde-fou, qui compte plus que l'effacement lui-même ──────────────────


@pytest.mark.django_db
def test_sans_variable_rien_n_est_efface(monkeypatch: pytest.MonkeyPatch) -> None:
    """La commande reste dans la chaîne de démarrage : elle doit être inerte."""
    _peupler()

    _jouer(monkeypatch, None)

    assert Organisation.objects.exists()
    assert Customer.objects.exists()


@pytest.mark.django_db
def test_la_phrase_d_hier_ne_vaut_plus_rien(monkeypatch: pytest.MonkeyPatch) -> None:
    """C'est TOUT l'objet de la date.

    Une variable qu'on a oublié de retirer devient inoffensive d'elle-même à
    minuit. Sans cela, un redémarrage six mois plus tard effacerait une base
    pleine de vrais clients — et personne ne ferait le lien avec une variable
    posée un jour de recette.
    """
    _peupler()
    hier = (timezone.now().date() - timedelta(days=1)).isoformat()

    sortie = _jouer(monkeypatch, PREFIXE_CONFIRMATION + hier)

    assert Organisation.objects.exists()
    assert Customer.objects.exists()
    assert "confirmation refusee" in sortie


@pytest.mark.django_db
def test_une_phrase_approximative_est_refusee(monkeypatch: pytest.MonkeyPatch) -> None:
    """« true » ne doit surtout pas suffire.

    C'est la valeur qu'on tape machinalement dans une variable d'environnement,
    et c'est exactement pour cela qu'elle ne doit rien déclencher ici.
    """
    _peupler()

    for approximation in ("true", "oui", "EFFACER-TOUT", "effacer-tout-2026-08-07"):
        sortie = _jouer(monkeypatch, approximation)
        assert Organisation.objects.exists(), approximation
        assert "confirmation refusee" in sortie, approximation


@pytest.mark.django_db
def test_l_effacement_est_atomique(monkeypatch: pytest.MonkeyPatch) -> None:
    """Une base à moitié effacée est pire qu'une base pleine.

    Des commandes sans client et des générations sans commande produiraient des
    erreurs incompréhensibles, longtemps après.
    """
    from organisations.management.commands import reinitialiser_la_plateforme

    _peupler()
    monkeypatch.setattr(
        reinitialiser_la_plateforme.User.objects,
        "filter",
        lambda **_: (_ for _ in ()).throw(RuntimeError("panne au milieu")),
    )

    with pytest.raises(RuntimeError):
        _jouer(monkeypatch, phrase_attendue())

    # Rien n'a ete efface : la transaction a tout rendu.
    assert Organisation.objects.exists()
    assert Customer.objects.exists()


def test_la_phrase_attendue_porte_la_date_du_jour() -> None:
    attendue = phrase_attendue()
    assert attendue.startswith(PREFIXE_CONFIRMATION)
    assert attendue.endswith(timezone.now().date().isoformat())


@pytest.mark.django_db
def test_la_commande_annonce_ce_qu_elle_a_efface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un effacement silencieux ne laisse rien à vérifier après coup."""
    _peupler()

    sortie = _jouer(monkeypatch, phrase_attendue())

    assert "organisations" in sortie
    assert "contacts clients" in sortie
    # Et il rappelle de retirer la variable : la date protege de demain, pas
    # d'un second redemarrage aujourd'hui.
    assert "RETIREZ" in sortie


@pytest.mark.django_db
def test_une_formation_vendue_n_empeche_pas_la_remise_a_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AchatFormation.organisation` est en PROTECT : sans vider les achats
    d'abord, la commande levait — et elle est reliée par un `&&` sec au
    démarrage du conteneur. La formation, elle, est du catalogue : elle reste."""
    from catalog.models import AchatFormation, Formation

    _peupler()
    formation = Formation.objects.create(
        slug="methode-pop", titre="Méthode P.O.P", prix_cents=85_000
    )
    AchatFormation.objects.create(
        organisation=Organisation.objects.get(),
        formation=formation,
        reference_paiement="cs_test_reinitialisation0001",
        montant_cents=85_000,
        devise="EUR",
        email="partenaire@exemple.fr",
    )

    _jouer(monkeypatch, phrase_attendue())

    assert not AchatFormation.objects.exists()
    assert not Organisation.objects.exists()
    assert Formation.objects.filter(slug="methode-pop").exists()


@pytest.mark.django_db
def test_le_suivi_des_eleves_n_empeche_pas_la_remise_a_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le suivi d'une leçon et un émargement tiennent en PROTECT l'achat ET le
    contact : s'ils ne partent pas d'abord, la commande lève sur l'un puis sur
    l'autre — et le conteneur ne démarre plus. Le programme, lui, reste."""
    from django.db.models import ProtectedError

    from catalog.models import (
        AchatFormation,
        Emargement,
        Formation,
        LeconDeFormation,
        ModuleDeFormation,
        SeanceEnPresentiel,
        SuiviDeLecon,
    )

    _peupler()
    contact = Customer.objects.get()
    formation = Formation.objects.create(
        slug="methode-pop", titre="Méthode P.O.P", prix_cents=85_000
    )
    module = ModuleDeFormation.objects.create(formation=formation, titre="Poser")
    lecon = LeconDeFormation.objects.create(module=module, titre="Choisir sa cible")
    achat = AchatFormation.objects.create(
        organisation=Organisation.objects.get(),
        formation=formation,
        reference_paiement="cs_test_reinitialisation0002",
        montant_cents=85_000,
        devise="EUR",
        email="partenaire@exemple.fr",
    )
    maintenant = timezone.now()
    SuiviDeLecon.objects.create(
        achat=achat, eleve=contact, lecon=lecon,
        premiere_ouverture_le=maintenant, derniere_ouverture_le=maintenant,
    )
    seance = SeanceEnPresentiel.objects.create(
        formation=formation, intitule="Atelier", debut=maintenant, duree_minutes=60
    )
    Emargement.objects.create(
        seance=seance, achat=achat, eleve=contact, signe_le=maintenant,
        nom_signe="Partenaire Exemple", mode="papier",
    )
    # Le piège est réel : tant que ces traces existent, ni l'achat ni le
    # contact ne peuvent partir.
    with pytest.raises(ProtectedError):
        AchatFormation.objects.all().delete()
    with pytest.raises(ProtectedError):
        Customer.objects.all().delete()

    sortie = _jouer(monkeypatch, phrase_attendue())

    assert "remise a zero" in sortie
    for modele in (SuiviDeLecon, Emargement, SeanceEnPresentiel, AchatFormation):
        assert not modele.objects.exists(), modele.__name__
    assert not Customer.objects.exists()
    assert not Organisation.objects.exists()
    assert LeconDeFormation.objects.filter(pk=lecon.pk).exists()
    assert Formation.objects.filter(slug="methode-pop").exists()

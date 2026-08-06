"""Son nom se corrige seul ; son adresse de connexion se prouve.

Demande de la cliente le 06/08/2026 : « possibilite de changer le nom et autre
mais pas le mail, et pour changer le mail un mail de confirmation doit etre
envoye sur l'autre mail ».

## Pourquoi l'adresse n'est pas un champ de profil

Elle est l'IDENTIFIANT de connexion, et la destination des liens de
reinitialisation. Qui la change prend le compte. Un jeton de session suffit a
lire l'espace ; il ne doit pas suffire a deplacer l'identifiant, sans quoi cinq
minutes devant un ecran reste ouvert donnent l'acces definitif.

D'ou deux preuves, et il en faut deux :

- le **mot de passe actuel** a la demande — c'est bien le titulaire ;
- un **clic dans la boite visee** ensuite — l'adresse existe et lui appartient.

La seconde protege aussi d'une faute de frappe, qui enfermerait quelqu'un
dehors definitivement.

## L'usage unique sans table

Le jeton porte l'ANCIENNE adresse en plus de la nouvelle. Une fois le changement
applique, l'ancienne ne correspond plus a celle du compte, et le meme lien
rejoue est refuse — meme effet qu'un jeton consomme, sans etat a maintenir ni
purge a faire tourner.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client
from django.test.utils import override_settings

from customers.models import Customer
from organisations import identifiants, services
from organisations.authentification import creer_compte, ouvrir_session
from organisations.models import CompteClient, MembreOrganisation, RoleOrganisation

pytestmark = pytest.mark.django_db

MOT_DE_PASSE = "mot-de-passe-de-test-2026"
REGLAGES = {"EVKHA_APP_URL": "https://exemple.fr"}


class Personne:
    def __init__(
        self,
        email: str = "titulaire@exemple.fr",
        role: str = RoleOrganisation.PROPRIETAIRE,
    ):
        self.contact = Customer.objects.create(
            email=email, first_name="Camille", last_name="Ancien"
        )
        self.organisation = services.creer_organisation(
            raison_sociale="Atelier Test", contact=self.contact
        )
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
        return {"Authorization": f"Bearer {self.jeton}"}

    def relire(self) -> Customer:
        return Customer.objects.get(pk=self.contact.pk)

    def compte(self) -> CompteClient:
        return CompteClient.objects.select_related("user", "customer").get(
            customer=self.contact
        )


def poster(chemin: str, corps: dict[str, Any], entetes: dict[str, str] | None = None) -> Any:
    return Client().post(
        chemin, data=json.dumps(corps), content_type="application/json",
        headers=entetes or {},
    )


class Boite:
    """Retient les courriels au lieu de les envoyer.

    On verifie QUI recoit quoi : c'est toute la question ici. Un test qui
    constaterait seulement « la vue repond 202 » ne dirait pas si la
    confirmation est partie vers la bonne boite — et c'est exactement l'erreur
    qui rendrait le controle inutile.
    """

    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def __call__(self, *, destinataire: str, sujet: str, corps_html: str) -> bool:
        self.messages.append((destinataire, sujet))
        return True

    def destinataires(self) -> list[str]:
        return [d for d, _ in self.messages]


@pytest.fixture
def boite(monkeypatch: pytest.MonkeyPatch) -> Boite:
    from organisations import courriels

    b = Boite()
    monkeypatch.setattr(courriels, "_envoyer", b)
    return b


# ── 1. Le nom se corrige, sans droit particulier ─────────────────────────────


def test_chacun_corrige_son_prenom_et_son_nom() -> None:
    personne = Personne()

    reponse = poster(
        "/api/espace/profil/",
        {"prenom": "Camille", "nom": "Duval"},
        personne.entetes,
    )

    assert reponse.status_code == 200
    relu = personne.relire()
    assert (relu.first_name, relu.last_name) == ("Camille", "Duval")


def test_meme_un_role_lecture_ecrit_son_propre_nom() -> None:
    """Aucun droit du §12 ne s'applique : ce sont SES nom et prenom.

    Les subordonner a `gerer_marque` ou a `gerer_membres` empecherait quelqu'un
    de corriger une faute sur son propre etat civil.
    """
    personne = Personne(email="lecteur@exemple.fr", role=RoleOrganisation.LECTURE)

    reponse = poster(
        "/api/espace/profil/", {"prenom": "Lou", "nom": "Marchand"}, personne.entetes
    )

    assert reponse.status_code == 200
    assert personne.relire().first_name == "Lou"


def test_le_profil_ne_change_jamais_l_adresse() -> None:
    """Le champ est ignore, pas honore. C'est LA propriete de ce fichier."""
    personne = Personne()

    poster(
        "/api/espace/profil/",
        {"prenom": "Camille", "nom": "Duval", "email": "vole@exemple.fr"},
        personne.entetes,
    )

    assert personne.relire().email == "titulaire@exemple.fr"


# ── 2. L'adresse exige le mot de passe, puis un clic dans la boite visee ─────


@override_settings(**REGLAGES)
def test_sans_le_mot_de_passe_actuel_rien_ne_part(boite: Boite) -> None:
    """Un jeton de session ne suffit pas a deplacer un identifiant de connexion."""
    personne = Personne()

    reponse = poster(
        "/api/espace/adresse/",
        {"mot_de_passe": "ce-n-est-pas-le-bon", "nouvelle_adresse": "neuve@exemple.fr"},
        personne.entetes,
    )

    assert reponse.status_code == 403
    assert reponse.json()["code"] == "mot_de_passe_actuel"
    assert boite.messages == []


@override_settings(**REGLAGES)
def test_la_confirmation_part_vers_la_NOUVELLE_adresse(boite: Boite) -> None:
    """L'envoyer a l'ancienne ne prouverait rien de la boite visee.

    On saurait que le titulaire est d'accord, jamais que l'adresse existe et
    lui appartient — donc une faute de frappe passerait, et enfermerait la
    personne dehors.
    """
    personne = Personne()

    reponse = poster(
        "/api/espace/adresse/",
        {"mot_de_passe": MOT_DE_PASSE, "nouvelle_adresse": "Neuve@Exemple.FR"},
        personne.entetes,
    )

    assert reponse.status_code == 202
    assert "neuve@exemple.fr" in boite.destinataires()
    # L'ancienne est prevenue : sans cela, une reprise de compte serait
    # silencieuse — le titulaire ne l'apprendrait qu'en ne recevant plus rien.
    assert "titulaire@exemple.fr" in boite.destinataires()


@override_settings(**REGLAGES)
def test_rien_ne_change_avant_le_clic(boite: Boite) -> None:
    """CONTRE-EPREUVE : demander n'est pas obtenir."""
    personne = Personne()

    poster(
        "/api/espace/adresse/",
        {"mot_de_passe": MOT_DE_PASSE, "nouvelle_adresse": "neuve@exemple.fr"},
        personne.entetes,
    )

    assert personne.relire().email == "titulaire@exemple.fr"


@override_settings(**REGLAGES)
def test_le_clic_applique_le_changement_partout(boite: Boite) -> None:
    """`Customer.email` ET `User.username` : la connexion cherche dans le second.

    Ne changer que le premier laisserait la personne se connecter avec
    l'ancienne adresse et lire la nouvelle a l'ecran — deux verites pour un
    identifiant.
    """
    personne = Personne()
    lien = identifiants.lien_de_changement_d_adresse(
        personne.compte(), "neuve@exemple.fr"
    )
    jeton = lien.split("jeton=")[1]

    reponse = poster("/api/public/adresse/confirmer/", {"jeton": jeton})

    assert reponse.status_code == 200
    compte = personne.compte()
    assert compte.customer.email == "neuve@exemple.fr"
    assert compte.user.username == "neuve@exemple.fr"
    # Et l'on se connecte reellement avec la nouvelle.
    assert ouvrir_session("neuve@exemple.fr", MOT_DE_PASSE)[0]


@override_settings(**REGLAGES)
def test_le_meme_lien_ne_sert_qu_une_fois(boite: Boite) -> None:
    """L'usage unique, sans table ni purge.

    Le jeton signe l'ANCIENNE adresse. Une fois le changement applique, elle ne
    correspond plus a celle du compte : rejouer le lien est refuse.
    """
    personne = Personne()
    lien = identifiants.lien_de_changement_d_adresse(
        personne.compte(), "neuve@exemple.fr"
    )
    jeton = lien.split("jeton=")[1]
    poster("/api/public/adresse/confirmer/", {"jeton": jeton})

    seconde = poster("/api/public/adresse/confirmer/", {"jeton": jeton})

    assert seconde.status_code == 400
    assert seconde.json()["code"] == "lien_invalide"


@override_settings(**REGLAGES)
def test_un_jeton_fabrique_ailleurs_est_refuse(boite: Boite) -> None:
    """Le sel de signature est propre a cet usage.

    Un jeton emis par nous pour autre chose ne doit pas ouvrir cette porte.
    """
    from django.core import signing

    personne = Personne()
    faux = signing.dumps(
        {
            "compte": str(personne.compte().id),
            "ancienne": "titulaire@exemple.fr",
            "nouvelle": "vole@exemple.fr",
        },
        salt="un-autre-usage",
    )

    reponse = poster("/api/public/adresse/confirmer/", {"jeton": faux})

    assert reponse.status_code == 400
    assert personne.relire().email == "titulaire@exemple.fr"


@override_settings(**REGLAGES)
def test_une_adresse_deja_prise_est_refusee_a_la_demande(boite: Boite) -> None:
    personne = Personne()
    Customer.objects.create(email="occupee@exemple.fr")

    reponse = poster(
        "/api/espace/adresse/",
        {"mot_de_passe": MOT_DE_PASSE, "nouvelle_adresse": "occupee@exemple.fr"},
        personne.entetes,
    )

    assert reponse.status_code == 400
    assert reponse.json()["code"] == "adresse_refusee"
    assert boite.messages == []


@override_settings(**REGLAGES)
def test_une_adresse_prise_ENTRE_TEMPS_est_refusee_au_clic(boite: Boite) -> None:
    """Trois jours separent la demande du clic. Le controle a lieu deux fois.

    Ne verifier qu'a la demande laisserait deux comptes se disputer un meme
    identifiant de connexion.
    """
    personne = Personne()
    lien = identifiants.lien_de_changement_d_adresse(
        personne.compte(), "neuve@exemple.fr"
    )
    jeton = lien.split("jeton=")[1]
    Customer.objects.create(email="neuve@exemple.fr")

    reponse = poster("/api/public/adresse/confirmer/", {"jeton": jeton})

    assert reponse.status_code == 409
    assert personne.relire().email == "titulaire@exemple.fr"


@override_settings(**REGLAGES)
def test_un_lien_perime_ne_vaut_plus(boite: Boite) -> None:
    personne = Personne()
    jeton = identifiants.jeton_de_changement_d_adresse(
        personne.compte(), "neuve@exemple.fr"
    )

    # Quatre jours : au-dela des trois de validite.
    with override_settings():
        import organisations.identifiants as module

        ancien = module._VALIDITE_ADRESSE_S
        module._VALIDITE_ADRESSE_S = -1
        try:
            reponse = poster("/api/public/adresse/confirmer/", {"jeton": jeton})
        finally:
            module._VALIDITE_ADRESSE_S = ancien

    assert reponse.status_code == 400
    assert personne.relire().email == "titulaire@exemple.fr"

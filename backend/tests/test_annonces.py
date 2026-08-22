"""Les annonces : ce que la cliente ecrit part par deux chemins, une seule fois.

Une annonce touche TOUS les clients d'un coup et ne se rattrape pas. Chaque
test ici verrouille une des barrieres qui rendent ce geste sur :

- un brouillon n'existe pour personne ;
- un envoi ne se rejoue pas ;
- une annonce envoyee ne se modifie plus ;
- une fenetre fermee ne revient pas, sur aucun appareil ;
- une adresse presente dans deux organisations ne recoit qu'un courriel.
"""
from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from organisations import services
from organisations.models import (
    Annonce,
    AnnonceVue,
    MembreOrganisation,
    Organisation,
    RoleOrganisation,
    StatutAnnonce,
    StatutOrganisation,
)

pytestmark = pytest.mark.django_db


def _client_final(email: str, prenom: str = "Camille") -> Any:
    """Un compte, tel que l'espace le connait."""
    from customers.models import Customer  # noqa: PLC0415

    return Customer.objects.create(email=email, first_name=prenom, last_name="Essai")


def _organisation(raison: str, email: str) -> tuple[Organisation, MembreOrganisation]:
    """Une organisation complete, par le meme chemin que la production.

    `services.creer_organisation` cree l'organisation, son proprietaire ET son
    portefeuille d'un seul geste. Les monter a la main ici ferait un second
    chemin de creation, qui divergerait du vrai au premier champ ajoute.
    """
    organisation = services.creer_organisation(
        raison_sociale=raison, contact=_client_final(email)
    )
    return organisation, organisation.membres.get()


def _session(membre: MembreOrganisation) -> Client:
    """Un client HTTP authentifie comme ce membre.

    La session s'ouvre sur un COMPTE de connexion, pas sur la fiche client :
    ce sont deux objets distincts, et c'est `compte_sans_mot_de_passe` qui
    fait le pont — le meme chemin que celui emprunte apres un paiement.
    """
    from organisations import authentification, identifiants  # noqa: PLC0415

    compte = identifiants.compte_sans_mot_de_passe(membre.customer)
    jeton = authentification.ouvrir_session_sans_mot_de_passe(compte)
    return Client(HTTP_AUTHORIZATION=f"Bearer {jeton}")


def _annonce(**surcharges: Any) -> Annonce:
    valeurs: dict[str, Any] = {
        "titre": "Le business plan arrive en octobre",
        "message": "Bonjour,\n\nLe business plan sera disponible le mois prochain.",
        "lien_libelle": "Voir les livrables",
        "lien_cible": "/espace/livrables",
    }
    valeurs.update(surcharges)
    return Annonce.objects.create(**valeurs)


# ── 1. Un brouillon n'existe pour personne ───────────────────────────────────


def test_un_brouillon_ne_s_affiche_NULLE_PART() -> None:
    """C'est tout l'interet du statut : rediger, relire, puis decider.

    Sans lui, chaque frappe serait publiee — et une annonce a moitie ecrite
    partirait chez tous les clients.
    """
    _, membre = _organisation("Agence Essai", "camille@example.com")
    _annonce()

    reponse = _session(membre).get("/api/espace/annonces/")

    assert reponse.status_code == 200
    assert reponse.json()["annonces"] == []


def test_une_annonce_envoyee_s_affiche(client_admin: Any) -> None:
    """Contre-epreuve : le statut ne doit pas non plus tout retenir."""
    _, membre = _organisation("Agence Essai", "camille@example.com")
    annonce = _annonce()

    client_admin.post(f"/api/dashboard/annonces/{annonce.id}/envoyer/")

    vues = _session(membre).get("/api/espace/annonces/").json()["annonces"]
    assert [a["titre"] for a in vues] == ["Le business plan arrive en octobre"]
    assert vues[0]["lien_cible"] == "/espace/livrables"


# ── 2. L'envoi ne se rejoue pas ──────────────────────────────────────────────


def test_un_second_envoi_est_refuse(client_admin: Any) -> None:
    """Le courriel est parti. Le renvoyer ferait un doublon dans toutes les
    boites aux lettres, et rien ne permettrait de le reprendre."""
    _organisation("Agence Essai", "camille@example.com")
    annonce = _annonce()

    premier = client_admin.post(f"/api/dashboard/annonces/{annonce.id}/envoyer/")
    second = client_admin.post(f"/api/dashboard/annonces/{annonce.id}/envoyer/")

    assert premier.status_code == 200
    assert second.status_code == 409
    assert second.json()["code"] == "annonce_deja_envoyee"


def test_une_annonce_envoyee_ne_se_modifie_plus(client_admin: Any) -> None:
    """Il y aurait deux versions du meme message, dont une deja lue."""
    _organisation("Agence Essai", "camille@example.com")
    annonce = _annonce()
    client_admin.post(f"/api/dashboard/annonces/{annonce.id}/envoyer/")

    reponse = client_admin.post(
        f"/api/dashboard/annonces/{annonce.id}/",
        data={"titre": "Finalement en novembre"},
        content_type="application/json",
    )

    assert reponse.status_code == 409
    annonce.refresh_from_db()
    assert annonce.titre == "Le business plan arrive en octobre"


def test_le_statut_precede_les_courriels(client_admin: Any) -> None:
    """L'ordre est delibere : si l'envoi s'interrompt au milieu, l'annonce est
    deja visible dans les espaces et un second appel ne reexpediera rien."""
    _organisation("Agence Essai", "camille@example.com")
    annonce = _annonce()

    client_admin.post(f"/api/dashboard/annonces/{annonce.id}/envoyer/")

    annonce.refresh_from_db()
    assert annonce.statut == StatutAnnonce.ENVOYEE
    assert annonce.envoyee_le is not None


# ── 3. Les destinataires ─────────────────────────────────────────────────────


def test_une_adresse_dans_deux_organisations_ne_recoit_qu_un_courriel(
    client_admin: Any,
) -> None:
    """C'est la meme personne. Deux exemplaires du meme message se lisent
    comme une erreur, pas comme une insistance."""
    partagee = _client_final("consultant@example.com")
    for raison in ("Agence Une", "Agence Deux"):
        services.creer_organisation(raison_sociale=raison, contact=partagee)

    listing = client_admin.get("/api/dashboard/annonces/").json()

    assert listing["destinataires"] == 1


def test_une_organisation_SUSPENDUE_n_est_pas_destinataire(client_admin: Any) -> None:
    """Son acces est ferme : lui annoncer une nouveaute qu'elle ne peut pas
    atteindre serait au mieux inutile."""
    _organisation("Agence Active", "active@example.com")
    suspendue, _ = _organisation("Agence Suspendue", "suspendue@example.com")
    suspendue.statut = StatutOrganisation.SUSPENDUE
    suspendue.save(update_fields=["statut"])

    listing = client_admin.get("/api/dashboard/annonces/").json()

    assert listing["destinataires"] == 1


# ── 4. La fenetre ne revient pas ─────────────────────────────────────────────


def test_une_annonce_fermee_ne_revient_pas(client_admin: Any) -> None:
    """La trace vit en BASE : rangee dans le navigateur, la fenetre
    reapparaitrait sur un autre appareil."""
    _, membre = _organisation("Agence Essai", "camille@example.com")
    annonce = _annonce()
    client_admin.post(f"/api/dashboard/annonces/{annonce.id}/envoyer/")
    session = _session(membre)

    assert len(session.get("/api/espace/annonces/").json()["annonces"]) == 1
    session.post(f"/api/espace/annonces/{annonce.id}/fermer/")

    assert session.get("/api/espace/annonces/").json()["annonces"] == []


def test_fermer_deux_fois_est_sans_effet(client_admin: Any) -> None:
    """Deux onglets qui ferment la fenetre au meme instant passeraient tous
    deux un `if deja_vue` ecrit en Python. La contrainte d'unicite tranche."""
    _, membre = _organisation("Agence Essai", "camille@example.com")
    annonce = _annonce()
    client_admin.post(f"/api/dashboard/annonces/{annonce.id}/envoyer/")
    session = _session(membre)

    premier = session.post(f"/api/espace/annonces/{annonce.id}/fermer/")
    second = session.post(f"/api/espace/annonces/{annonce.id}/fermer/")

    assert premier.status_code == 200
    assert second.status_code == 200
    assert AnnonceVue.objects.filter(annonce=annonce, membre=membre).count() == 1


def test_la_fermeture_d_un_membre_ne_vaut_pas_pour_son_collegue(
    client_admin: Any,
) -> None:
    """Deux collaborateurs se connectent separement. Celui qui n'a pas lu
    l'annonce doit la voir."""
    organisation, patronne = _organisation("Agence Essai", "patronne@example.com")
    collegue = MembreOrganisation.objects.create(
        organisation=organisation,
        customer=_client_final("collegue@example.com", "Alex"),
        role=RoleOrganisation.MEMBRE,
    )
    annonce = _annonce()
    client_admin.post(f"/api/dashboard/annonces/{annonce.id}/envoyer/")

    _session(patronne).post(f"/api/espace/annonces/{annonce.id}/fermer/")

    restantes = _session(collegue).get("/api/espace/annonces/").json()["annonces"]
    assert [a["id"] for a in restantes] == [str(annonce.id)]


# ── 5. La destination du bouton ──────────────────────────────────────────────


def test_une_destination_INVENTEE_est_ignoree(client_admin: Any) -> None:
    """Le champ envoie des clients quelque part. Une saisie libre permettrait
    de les envoyer n'importe ou, y compris hors du domaine."""
    reponse = client_admin.post(
        "/api/dashboard/annonces/",
        data={
            "titre": "Essai",
            "message": "Un message.",
            "lien_libelle": "Cliquez",
            "lien_cible": "https://ailleurs.example.com/piege",
        },
        content_type="application/json",
    )

    assert reponse.status_code == 201
    assert reponse.json()["annonce"]["lien_cible"] == ""


def test_une_destination_CONNUE_est_conservee(client_admin: Any) -> None:
    """Contre-epreuve : le filtre ne doit pas non plus tout refuser."""
    reponse = client_admin.post(
        "/api/dashboard/annonces/",
        data={
            "titre": "Essai",
            "message": "Un message.",
            "lien_libelle": "Voir",
            "lien_cible": "/espace/livrables",
        },
        content_type="application/json",
    )

    assert reponse.json()["annonce"]["lien_cible"] == "/espace/livrables"


def test_une_annonce_sans_titre_est_refusee(client_admin: Any) -> None:
    """Le titre EST l'objet du courriel : sans lui, le message arrive sans
    objet et se fait ignorer."""
    reponse = client_admin.post(
        "/api/dashboard/annonces/",
        data={"message": "Un message sans titre."},
        content_type="application/json",
    )

    assert reponse.status_code == 400
    assert reponse.json()["code"] == "titre_manquant"


# ── 6. Ce qui part par courriel ──────────────────────────────────────────────


def test_le_courriel_porte_le_titre_en_OBJET(client_admin: Any, monkeypatch: Any) -> None:
    """Un objet generique — « Nouvelle information EVKHA » — se ferait ignorer,
    et rendrait l'annonce invisible pour ceux qui ne se connectent pas."""
    from organisations import courriels  # noqa: PLC0415

    envois: list[dict[str, Any]] = []

    def _capturer(**kwargs: Any) -> bool:
        envois.append(kwargs)
        return True

    monkeypatch.setattr(courriels, "_envoyer", _capturer)
    _organisation("Agence Essai", "camille@example.com")
    annonce = _annonce()

    client_admin.post(f"/api/dashboard/annonces/{annonce.id}/envoyer/")

    assert len(envois) == 1
    assert envois[0]["sujet"] == "Le business plan arrive en octobre"
    assert envois[0]["destinataire"] == "camille@example.com"
    # Le corps porte les DEUX paragraphes de la cliente, pas un bloc recolle.
    assert "Bonjour," in envois[0]["corps_html"]
    assert "disponible le mois prochain" in envois[0]["corps_html"]


def test_le_nombre_de_courriels_partis_est_conserve(
    client_admin: Any, monkeypatch: Any
) -> None:
    """C'est la seule trace : un envoi ne se rejoue pas pour etre recompte."""
    from organisations import courriels  # noqa: PLC0415

    monkeypatch.setattr(courriels, "_envoyer", lambda **_: True)
    for numero in range(3):
        _organisation(f"Agence {numero}", f"client{numero}@example.com")
    annonce = _annonce()

    reponse = client_admin.post(f"/api/dashboard/annonces/{annonce.id}/envoyer/")

    assert reponse.json()["courriels_envoyes"] == 3
    annonce.refresh_from_db()
    assert annonce.courriels_envoyes == 3


def test_un_courriel_qui_echoue_n_arrete_pas_les_autres(
    client_admin: Any, monkeypatch: Any
) -> None:
    """Une adresse invalide ne doit pas priver les autres de l'annonce."""
    from organisations import courriels  # noqa: PLC0415

    def _capricieux(**kwargs: Any) -> bool:
        return "casse" not in kwargs["destinataire"]

    monkeypatch.setattr(courriels, "_envoyer", _capricieux)
    _organisation("Agence Une", "bonne@example.com")
    _organisation("Agence Deux", "casse@example.com")
    _organisation("Agence Trois", "autre@example.com")
    annonce = _annonce()

    reponse = client_admin.post(f"/api/dashboard/annonces/{annonce.id}/envoyer/")

    assert reponse.json()["destinataires"] == 3
    assert reponse.json()["courriels_envoyes"] == 2


# ── 7. Le droit d'ecrire ─────────────────────────────────────────────────────


def test_un_client_ne_peut_pas_REDIGER_une_annonce() -> None:
    """L'administration est la seule porte : une annonce ecrite par un client
    partirait chez tous les autres."""
    _, membre = _organisation("Agence Essai", "camille@example.com")

    reponse = _session(membre).post(
        "/api/dashboard/annonces/",
        data={"titre": "Faux", "message": "Faux"},
        content_type="application/json",
    )

    assert reponse.status_code in (401, 403)
    assert Annonce.objects.count() == 0


def test_le_role_LECTURE_peut_fermer_une_annonce(client_admin: Any) -> None:
    """Fermer n'est pas ecrire : c'est dire « j'ai lu ». Le refuser laisserait
    la fenetre revenir a chaque connexion d'un compte en lecture seule."""
    organisation, _ = _organisation("Agence Essai", "patronne@example.com")
    lecteur = MembreOrganisation.objects.create(
        organisation=organisation,
        customer=_client_final("lecteur@example.com", "Dominique"),
        role=RoleOrganisation.LECTURE,
    )
    assert not services.peut(lecteur, "commander")
    annonce = _annonce()
    client_admin.post(f"/api/dashboard/annonces/{annonce.id}/envoyer/")

    reponse = _session(lecteur).post(f"/api/espace/annonces/{annonce.id}/fermer/")

    assert reponse.status_code == 200
    assert _session(lecteur).get("/api/espace/annonces/").json()["annonces"] == []

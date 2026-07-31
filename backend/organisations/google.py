"""Connexion par compte Google.

Le navigateur obtient un jeton d'identité auprès de Google, l'envoie ici, et
**le serveur le vérifie auprès de Google** avant d'en tirer quoi que ce soit.
C'est le seul ordre acceptable : un jeton que le client se contenterait de nous
décrire serait un formulaire où l'on écrit l'adresse de quelqu'un d'autre.

## Pourquoi pas la bibliothèque officielle

`google-auth` valide la signature hors ligne, ce qui évite un aller-retour
réseau par connexion. Elle ajouterait une dépendance à l'image pour une
fonction appelée quelques fois par jour. On interroge donc le point de
vérification documenté par Google (`tokeninfo`), avec `httpx` déjà présent.

Le compromis est assumé et se voit : une panne de Google rend la connexion
Google indisponible — jamais l'application entière, puisque le mot de passe
reste un chemin valide.

## Ce que la plateforme retient

Le prénom, le nom et l'adresse viennent de Google et sont écrits sur le contact
**s'ils manquent**. Ils ne sont jamais réécrits par-dessus : quelqu'un qui a
corrigé son nom dans ses paramètres ne doit pas le voir revenir à chaque
connexion.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from django.conf import settings

_log = logging.getLogger(__name__)

#: Point de vérification documenté par Google.
URL_VERIFICATION = "https://oauth2.googleapis.com/tokeninfo"

#: Au-delà, on considère Google injoignable. Court volontairement : une
#: connexion qui met dix secondes est vécue comme une panne de notre côté.
DELAI_S = 6.0


class GoogleRefuseError(ValueError):
    """Le jeton n'est pas exploitable. Message destiné au visiteur."""

    def __init__(self, message: str, code: str, statut: int = 400) -> None:
        self.code = code
        self.statut = statut
        super().__init__(message)


@dataclass(frozen=True)
class IdentiteGoogle:
    """Ce que Google atteste, et rien de plus."""

    email: str
    prenom: str
    nom: str
    #: Google a vérifié cette adresse. Une adresse non vérifiée permettrait à
    #: quelqu'un de créer un compte Google au nom d'autrui puis de récupérer
    #: l'espace correspondant chez nous.
    email_verifie: bool


def identifiant_client() -> str:
    """Identifiant OAuth de l'application, ou chaîne vide s'il n'est pas posé.

    Il est PUBLIC par construction — le navigateur l'envoie à Google — et vit
    donc dans les réglages, pas dans un secret. Le secret OAuth, lui, n'est pas
    nécessaire ici : le navigateur obtient le jeton d'identité, nous ne faisons
    que le vérifier.
    """
    return str(getattr(settings, "EVKHA_GOOGLE_CLIENT_ID", "") or "")


def configure() -> bool:
    """La connexion Google est-elle utilisable ?

    L'interface s'en sert pour n'afficher le bouton que s'il peut marcher. Un
    bouton « Continuer avec Google » qui échoue faute de réglage est pire que
    pas de bouton : il fait douter du reste de la page (règle 1).
    """
    return bool(identifiant_client())


def verifier(jeton_identite: str) -> IdentiteGoogle:
    """Vérifie le jeton auprès de Google et rend l'identité attestée.

    Trois contrôles, et aucun n'est facultatif :

    1. Google reconnaît le jeton (signature, date d'expiration) ;
    2. il a été émis **pour notre application** — sans cette vérification, un
       jeton obtenu par n'importe quel autre site serait accepté ici ;
    3. l'adresse est vérifiée par Google.
    """
    if not configure():
        raise GoogleRefuseError(
            "La connexion Google n'est pas configurée sur cette plateforme.",
            "google_non_configure",
            503,
        )
    if not jeton_identite:
        raise GoogleRefuseError("Jeton Google absent.", "jeton_absent")

    try:
        reponse = httpx.get(
            URL_VERIFICATION, params={"id_token": jeton_identite}, timeout=DELAI_S
        )
    except httpx.HTTPError as erreur:
        _log.warning("Verification Google injoignable : %s", erreur)
        raise GoogleRefuseError(
            "Google est momentanément injoignable. Réessayez, ou "
            "connectez-vous avec votre mot de passe.",
            "google_injoignable",
            503,
        ) from erreur

    if reponse.status_code != 200:
        raise GoogleRefuseError(
            "Connexion Google refusée. Réessayez.", "jeton_invalide", 401
        )

    charge = reponse.json()

    # `aud` = destinataire du jeton. Sans ce controle, un jeton emis pour un
    # autre site serait accepte ici : c'est la faille classique de cette
    # integration.
    if str(charge.get("aud", "")) != identifiant_client():
        _log.warning("Jeton Google emis pour une autre application")
        raise GoogleRefuseError(
            "Connexion Google refusée.", "jeton_autre_application", 401
        )

    email = str(charge.get("email", "")).strip().lower()
    if not email:
        raise GoogleRefuseError(
            "Ce compte Google ne communique pas d'adresse e-mail.",
            "email_absent",
        )

    # Google rend « true »/« false » en CHAINE sur ce point d'entree.
    verifie = str(charge.get("email_verified", "")).lower() == "true"
    if not verifie:
        raise GoogleRefuseError(
            "Cette adresse Google n'est pas vérifiée. Vérifiez-la chez Google, "
            "puis réessayez.",
            "email_non_verifie",
            403,
        )

    return IdentiteGoogle(
        email=email,
        prenom=str(charge.get("given_name", "")).strip(),
        nom=str(charge.get("family_name", "")).strip(),
        email_verifie=True,
    )


def completer_le_contact(contact: object, identite: IdentiteGoogle) -> list[str]:
    """Complète les champs VIDES du contact avec ce que Google atteste.

    Rend la liste des champs effectivement écrits, pour la journaliser.

    Ne réécrit jamais une valeur existante : quelqu'un qui a corrigé son nom
    dans ses paramètres ne doit pas le voir revenir à chaque connexion. C'est
    la même règle que partout ailleurs — une seule source par vérité, et ici
    la source est la personne, pas Google.
    """
    ecrits: list[str] = []
    for champ, valeur in (("first_name", identite.prenom), ("last_name", identite.nom)):
        if valeur and not str(getattr(contact, champ, "") or "").strip():
            setattr(contact, champ, valeur)
            ecrits.append(champ)
    if ecrits:
        contact.save(update_fields=[*ecrits, "updated_at"])  # type: ignore[attr-defined]
    return ecrits

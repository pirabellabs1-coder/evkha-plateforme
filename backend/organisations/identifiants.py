"""Définir, retrouver et changer son mot de passe — sans passer par personne.

Ce module comble le seul trou qui rendait la fonctionnalité Équipe **totalement
inopérante**, et qui enfermait dehors quiconque perdait son mot de passe.

## Ce qui manquait, vérifié ligne à ligne

`inviter` créait un `Customer` et un `MembreOrganisation`, et déclarait en
docstring : « Le compte de connexion n'est PAS créé ici : il le sera à la
première connexion, une fois le mot de passe défini. » Or **aucune route ne
permettait de définir ce mot de passe**, et aucun courriel ne partait : la
recherche de `send_mail`, `EmailMessage` et `brevo` dans tout
`backend/organisations/` ne renvoyait rien.

Les trois portes restantes étaient fermées :

- la connexion exige un `CompteClient`, que l'invité n'a pas ;
- l'inscription publique bute sur `refuser_si_deja_membre`, qui répond
  « cette adresse a déjà un compte » — message faux, la personne n'en a pas ;
- la connexion Google tombe sur le même refus.

L'écran, lui, affirmait : « EVKHA lui transmettra ses identifiants de
connexion. » Personne ne transmettait rien.

Second manque, de la même famille : `set_password` n'apparaissait qu'une seule
fois dans tout le dépôt, à la création du compte. Aucune route pour changer son
mot de passe, le réinitialiser, ni fermer ses sessions. Un abonné dont le mot
de passe fuit ne pouvait rien faire pendant les quatorze jours de validité de
ses jetons. Et tout compte ouvert par Google porte un mot de passe aléatoire
que personne ne connaît : si Google devient injoignable — cas que `google.py`
prévoit explicitement —, la personne est enfermée dehors définitivement.

## Pourquoi aucune table nouvelle

Django fournit `PasswordResetTokenGenerator`, et il fait exactement ce qu'il
faut : le jeton est **sans état**, sa signature intègre le condensat du mot de
passe et la date de dernière connexion, si bien qu'il cesse de valoir dès que
le mot de passe change. Un jeton utilisé est donc mort — sans table, sans
migration, sans tâche de nettoyage.

Écrire notre propre jeton à usage unique aurait demandé une table, sa purge, et
la discipline de la faire tourner. Trois occasions de se tromper sur un chemin
qui garde des comptes.

## Le compte est créé DÈS l'invitation

Avec un mot de passe **inutilisable** (`set_unusable_password`) : `check_password`
le refuse toujours, donc personne ne se connecte tant que le mot de passe n'est
pas choisi. Mais le compte existe, ce qui donne au générateur de jetons une
identité à signer — et fait disparaître le message « cette adresse a déjà un
compte » qui bloquait l'invité sur le formulaire public.
"""
from __future__ import annotations

import logging
import secrets

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.exceptions import ValidationError
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from customers.models import Customer

from .authentification import revoquer_tous_les_jetons
from .models import CompteClient

_log = logging.getLogger(__name__)

#: Générateur de jetons de Django, tel quel.
#:
#: Sa validité vient de `PASSWORD_RESET_TIMEOUT` (trois jours par défaut). Ne
#: pas la raccourcir sans raison : une invitation reçue le vendredi soir doit
#: encore valoir le lundi matin.
_jetons = PasswordResetTokenGenerator()

class LienInvalideError(ValueError):
    """Le lien est expiré, déjà utilisé, ou n'a jamais été émis par nous.

    Un seul type d'erreur et un seul message : distinguer « expiré » de
    « inconnu » dirait à un attaquant que l'adresse visée existe.
    """


class MotDePasseRefuseError(ValueError):
    """Le mot de passe ne satisfait pas les validateurs du projet."""


MESSAGE_LIEN = (
    "Ce lien n'est plus valable. Il expire au bout de trois jours, et ne "
    "sert qu'une fois. Demandez-en un nouveau."
)


def compte_sans_mot_de_passe(customer: Customer) -> CompteClient:
    """Ouvre un compte de connexion INUTILISABLE tant qu'aucun mot de passe n'est choisi.

    `set_unusable_password` inscrit une valeur qu'aucune saisie ne peut
    reproduire : `check_password` renvoie toujours faux. Le compte existe donc
    — ce qui débloque l'invitation et la réinitialisation — sans ouvrir le
    moindre accès.
    """
    user, cree = User.objects.get_or_create(
        username=customer.email, defaults={"email": customer.email}
    )
    if cree:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    compte, _ = CompteClient.objects.get_or_create(user=user, customer=customer)
    return compte


def lien_pour(compte: CompteClient, *, chemin: str = "/definir-mot-de-passe") -> str:
    """URL complète que la personne recevra par courriel.

    L'identifiant est encodé en base64 **et** accompagné du jeton signé : le
    premier dit qui, le second prouve que nous l'avons émis. Sans le second,
    changer un chiffre dans l'URL suffirait à prendre le compte du voisin.
    """
    # L'adresse du FRONT, pas celle de l'API : ces liens menent a des pages de
    # l'espace client. Construits sur `EVKHA_BASE_URL`, ils envoyaient l'invite
    # sur un 404 en production — la fonctionnalite Equipe etait livree, testee,
    # et inutilisable (regle 8, encore).
    base = str(getattr(settings, "EVKHA_APP_URL", "") or "").rstrip("/")
    if not base:
        # On ne fabrique PAS un lien de repli sur l'API : il aurait l'air
        # valide et ne menerait nulle part. `evkha.C004` refuse le demarrage
        # en production ; en developpement, le front local.
        base = "http://localhost:5173"
    identifiant = urlsafe_base64_encode(force_bytes(compte.user_id))
    jeton = _jetons.make_token(compte.user)
    return f"{base}{chemin}?id={identifiant}&jeton={jeton}"


def compte_du_lien(identifiant: str, jeton: str) -> CompteClient:
    """Résout le compte visé par un lien, ou refuse.

    Refuse pour toutes les raisons à la fois — identifiant illisible, compte
    inconnu, jeton périmé, jeton déjà consommé — avec le même message. C'est
    volontaire : une réponse plus précise permettrait de sonder des adresses.
    """
    try:
        cle = force_str(urlsafe_base64_decode(identifiant))
        compte = (
            CompteClient.objects.select_related("user", "customer")
            .filter(user_id=int(cle), actif=True)
            .first()
        )
    except (TypeError, ValueError, OverflowError):
        raise LienInvalideError(MESSAGE_LIEN) from None

    if compte is None or not _jetons.check_token(compte.user, jeton):
        raise LienInvalideError(MESSAGE_LIEN)
    return compte


def definir_mot_de_passe(compte: CompteClient, mot_de_passe: str) -> int:
    """Pose le mot de passe et **ferme toutes les sessions ouvertes**.

    La révocation n'est pas un supplément de précaution : quelqu'un qui
    réinitialise son mot de passe le fait souvent parce qu'il le croit
    compromis. Laisser vivre les jetons délivrés avant laisserait l'intrus
    connecté quatorze jours de plus — la réinitialisation aurait l'air d'agir
    sans rien changer.

    Retourne le nombre de sessions fermées.
    """
    # Les MEMES validateurs que l'inscription, et surtout pas une regle ecrite
    # ici : deux avis sur ce qu'est un mot de passe acceptable finiraient par se
    # contredire, et la porte la plus permissive gagnerait (regle 5).
    try:
        validate_password(mot_de_passe, user=compte.user)
    except ValidationError as exc:
        raise MotDePasseRefuseError(" ".join(exc.messages)) from exc

    compte.user.set_password(mot_de_passe)
    compte.user.save(update_fields=["password"])
    fermees = revoquer_tous_les_jetons(compte)
    _log.info(
        "Mot de passe redefini pour %s : %s session(s) fermee(s).",
        compte.customer.email, fermees,
    )
    return fermees


def mot_de_passe_provisoire() -> str:
    """Mot de passe aléatoire, pour les comptes ouverts par un tiers (Google).

    Il n'est communiqué à personne et n'est jamais utilisé : le compte ouvre
    par Google. Il existe seulement pour que le compte ne soit pas dans l'état
    « sans mot de passe utilisable », qui empêcherait la personne de basculer
    plus tard vers le mot de passe si Google devenait injoignable.
    """
    return secrets.token_urlsafe(32)

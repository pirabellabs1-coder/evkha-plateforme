"""Authentification par jeton nominatif pour l'espace client (lot 4).

Le dashboard interne est protégé par un **jeton unique partagé**
(`dashboard/middleware.py`). C'est acceptable pour une console d'exploitation
utilisée par EVKHA seule. C'est inacceptable ici : avec un secret commun,
chaque agence verrait le portefeuille, les clients finaux et les livrables de
toutes les autres. L'espace client exige donc une identité par personne.

## Choix retenus, et pourquoi

**Jeton opaque en base, pas de cookie de session.** Le front est hébergé sur un
autre domaine que l'API (Vercel d'un côté, le VPS de l'autre). Un cookie de
session imposerait `SameSite=None`, donc `CORS_ALLOW_CREDENTIALS`, donc de
rouvrir la porte au CSRF que l'en-tête `Authorization` referme. Un jeton porté
explicitement traverse les domaines sans rien de tout cela.

**Le jeton n'est jamais stocké en clair.** Seul son condensat SHA-256 est
enregistré. Une fuite de la base ne livre donc aucun jeton utilisable — même
raisonnement que pour un mot de passe.

**Les mots de passe restent gérés par Django.** `django.contrib.auth` fournit
le hachage, la validation et la rotation d'algorithme. En écrire une variante
serait la pire décision possible de ce module.

**Échec fermé.** Un jeton absent, inconnu, expiré ou révoqué donne 401. Aucun
chemin ne renvoie « autorisé » par défaut.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta

from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.utils import timezone

from customers.models import Customer

from .models import CompteClient, JetonAcces

_log = logging.getLogger(__name__)

#: Durée de vie d'un jeton. Assez longue pour ne pas déconnecter un utilisateur
#: en pleine commande, assez courte pour qu'un jeton oublié sur un poste
#: partagé ne serve pas indéfiniment.
DUREE_VALIDITE = timedelta(days=14)

#: 32 octets d'entropie, rendus en hexadécimal. `secrets` et non `random` :
#: le second est prévisible et n'a rien à faire dans un contexte de sécurité.
OCTETS_JETON = 32


def _condenser(jeton: str) -> str:
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()


class AuthentificationRefuseeError(PermissionError):
    """Identifiants invalides, compte inactif, ou jeton inutilisable.

    Un seul type d'erreur pour tous les cas, et un message volontairement
    identique : distinguer « e-mail inconnu » de « mot de passe faux »
    renseignerait un attaquant sur les comptes existants.
    """


MESSAGE_REFUS = "Identifiants invalides."


def creer_compte(customer: Customer, *, mot_de_passe: str) -> CompteClient:
    """Crée l'identifiant de connexion d'un contact existant.

    Le nom d'utilisateur Django est l'adresse e-mail : c'est ce que la personne
    saisit, et maintenir un second identifiant n'apporterait rien.
    """
    user, cree = User.objects.get_or_create(
        username=customer.email, defaults={"email": customer.email}
    )
    if cree or not user.has_usable_password():
        user.set_password(mot_de_passe)
        user.save(update_fields=["password"])
    compte, _ = CompteClient.objects.get_or_create(user=user, customer=customer)
    return compte


def ouvrir_session(email: str, mot_de_passe: str) -> tuple[str, JetonAcces]:
    """Vérifie les identifiants et délivre un jeton. Retourne (jeton_en_clair, jeton).

    Le jeton en clair n'est renvoyé qu'ici, une seule fois : il n'est stocké
    nulle part et ne peut donc pas être relu ensuite.
    """
    compte = (
        CompteClient.objects.select_related("user", "customer")
        .filter(user__username__iexact=email.strip(), actif=True)
        .first()
    )
    if compte is None:
        # Comparaison factice pour que le temps de réponse ne trahisse pas
        # l'existence du compte.
        check_password(mot_de_passe, "pbkdf2_sha256$1$abc$" + "0" * 44)
        raise AuthentificationRefuseeError(MESSAGE_REFUS)

    if not compte.user.check_password(mot_de_passe):
        raise AuthentificationRefuseeError(MESSAGE_REFUS)

    jeton_clair = secrets.token_hex(OCTETS_JETON)
    jeton = JetonAcces.objects.create(
        compte=compte,
        condensat=_condenser(jeton_clair),
        expire_le=timezone.now() + DUREE_VALIDITE,
    )
    compte.derniere_connexion = timezone.now()
    compte.save(update_fields=["derniere_connexion", "updated_at"])
    return jeton_clair, jeton


def compte_du_jeton(jeton_clair: str) -> CompteClient | None:
    """Compte associé à un jeton, ou None s'il est inutilisable.

    Ne lève pas : l'appelant décide du code de réponse. Met à jour la date
    d'utilisation, ce qui permet de repérer un jeton actif après un départ.
    """
    if not jeton_clair:
        return None
    jeton = (
        JetonAcces.objects.select_related("compte", "compte__customer")
        .filter(condensat=_condenser(jeton_clair))
        .first()
    )
    if jeton is None or not jeton.valide or not jeton.compte.actif:
        return None
    JetonAcces.objects.filter(pk=jeton.pk).update(
        derniere_utilisation=timezone.now()
    )
    return jeton.compte


def fermer_session(jeton_clair: str) -> bool:
    """Révoque un jeton. Vrai si un jeton a effectivement été révoqué."""
    nombre = JetonAcces.objects.filter(
        condensat=_condenser(jeton_clair), revoque_le__isnull=True
    ).update(revoque_le=timezone.now())
    return bool(nombre)


def revoquer_tous_les_jetons(compte: CompteClient) -> int:
    """Déconnecte partout. À appeler sur changement de mot de passe ou révocation."""
    return int(
        JetonAcces.objects.filter(compte=compte, revoque_le__isnull=True).update(
            revoque_le=timezone.now()
        )
    )


def purger_jetons_expires() -> int:
    """Supprime les jetons hors d'usage. Aucun intérêt à conserver un condensat mort."""
    limite = timezone.now() - timedelta(days=30)
    nombre, _ = JetonAcces.objects.filter(expire_le__lt=limite).delete()
    return int(nombre)

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


# ── Changer son adresse de connexion ─────────────────────────────────────────
#
# L'adresse n'est pas un champ de profil comme un autre : c'est l'IDENTIFIANT de
# connexion, et c'est là que partent les liens de réinitialisation. La modifier
# sans preuve reviendrait à offrir la reprise d'un compte à quiconque emprunte
# un écran resté ouvert cinq minutes.
#
# D'où deux exigences, et pas une seule : le mot de passe actuel au moment de la
# demande, puis un clic dans la BOÎTE VISÉE. La première prouve que c'est bien
# le titulaire ; la seconde, que l'adresse existe et lui appartient.

#: Sel de signature propre à cet usage. Un jeton fabriqué pour autre chose ne
#: doit pas pouvoir servir ici, même émis par nous.
_SEL_ADRESSE = "evkha.changement-adresse"

#: Trois jours, comme les autres liens de ce module. Un courriel reçu le
#: vendredi soir doit encore valoir le lundi matin.
_VALIDITE_ADRESSE_S = 3 * 24 * 3600


class AdresseRefuseeError(ValueError):
    """La nouvelle adresse ne convient pas, et la personne doit savoir pourquoi.

    Contrairement à `LienInvalideError`, ce message-là est PRÉCIS : il répond à
    quelqu'un d'authentifié qui vient de taper une adresse, pas à un inconnu qui
    sonde un lien. Lui cacher que l'adresse est déjà prise l'enverrait chercher
    une panne inexistante.
    """


def jeton_de_changement_d_adresse(compte: CompteClient, nouvelle: str) -> str:
    """Signe la demande, sans rien écrire en base.

    Le jeton porte l'ANCIENNE adresse en plus de la nouvelle, et c'est ce qui le
    rend à usage unique sans table ni purge : une fois le changement appliqué,
    l'ancienne ne correspond plus à celle du compte et le même lien, rejoué, est
    refusé. Même effet qu'un jeton consommé, sans l'état à maintenir.
    """
    from django.core import signing  # noqa: PLC0415

    return signing.dumps(
        {
            "compte": str(compte.id),
            "ancienne": compte.customer.email,
            "nouvelle": nouvelle,
        },
        salt=_SEL_ADRESSE,
    )


def lien_de_changement_d_adresse(compte: CompteClient, nouvelle: str) -> str:
    base = str(getattr(settings, "EVKHA_APP_URL", "") or "").rstrip("/")
    if not base:
        base = "http://localhost:5173"
    jeton = jeton_de_changement_d_adresse(compte, nouvelle)
    return f"{base}/confirmer-adresse?jeton={jeton}"


def verifier_adresse_libre(nouvelle: str, *, compte: CompteClient) -> str:
    """Normalise l'adresse et refuse si elle est déjà celle de quelqu'un.

    Le contrôle a lieu DEUX fois — ici, à la demande, et à la confirmation. Ce
    n'est pas une redondance : trois jours séparent les deux, et quelqu'un peut
    s'inscrire avec cette adresse entre-temps. Ne vérifier qu'à la demande
    laisserait deux comptes se disputer un même identifiant de connexion.
    """
    adresse = str(nouvelle or "").strip().lower()
    if "@" not in adresse or len(adresse) < 5:
        raise AdresseRefuseeError("Cette adresse e-mail n'est pas valide.")
    if adresse == compte.customer.email.lower():
        raise AdresseRefuseeError("C'est déjà votre adresse.")
    if Customer.objects.filter(email__iexact=adresse).exclude(
        pk=compte.customer_id
    ).exists():
        raise AdresseRefuseeError("Cette adresse est déjà utilisée par un compte.")
    return adresse


def appliquer_changement_d_adresse(jeton: str) -> tuple[CompteClient, str]:
    """Applique le changement porté par un lien, ou refuse.

    Retourne `(compte, ancienne_adresse)` — l'ancienne sert à prévenir la boîte
    qui perd le compte, ce qui est le seul moyen de repérer une reprise dont on
    n'est pas l'auteur.

    Les sessions ne sont PAS fermées ici, contrairement au changement de mot de
    passe : l'adresse change, pas le secret. Fermer les sessions punirait une
    correction de faute de frappe.
    """
    from django.core import signing  # noqa: PLC0415

    try:
        charge = signing.loads(
            jeton, salt=_SEL_ADRESSE, max_age=_VALIDITE_ADRESSE_S
        )
    except signing.BadSignature:
        raise LienInvalideError(MESSAGE_LIEN) from None

    compte = (
        CompteClient.objects.select_related("customer", "user")
        .filter(id=charge.get("compte"), actif=True)
        .first()
    )
    if compte is None:
        raise LienInvalideError(MESSAGE_LIEN)

    ancienne = str(charge.get("ancienne") or "")
    # LE contrôle d'usage unique. Si l'adresse du compte n'est plus celle que le
    # jeton a signée, c'est que le changement a déjà eu lieu — ou qu'un autre
    # est passé entre-temps. Dans les deux cas, ce lien ne vaut plus.
    if compte.customer.email.lower() != ancienne.lower():
        raise LienInvalideError(MESSAGE_LIEN)

    nouvelle = verifier_adresse_libre(str(charge.get("nouvelle") or ""), compte=compte)

    compte.customer.email = nouvelle
    compte.customer.save(update_fields=["email"])
    # `User.username` porte l'adresse : la connexion la cherche là. Ne changer
    # que `Customer.email` laisserait la personne se connecter avec l'ancienne
    # et lire la nouvelle à l'écran — deux vérités pour un identifiant.
    if compte.user.username != nouvelle:
        compte.user.username = nouvelle
        compte.user.email = nouvelle
        compte.user.save(update_fields=["username", "email"])

    _log.info("Adresse de connexion changee : %s -> %s", ancienne, nouvelle)
    return compte, ancienne

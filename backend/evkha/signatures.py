"""Signature des liens de téléchargement.

`/media/` était servi **sans aucun contrôle d'accès**. L'étude de marché
complète d'un client final — chiffre d'affaires, marges, concurrents — et le
bilan qu'une agence avait déposé étaient téléchargeables par quiconque
détenait l'URL, indéfiniment, y compris par un membre révoqué qui l'avait vue
passer.

Deux protections étaient invoquées dans le commentaire de la route. Aucune
n'existait : les pièces jointes conservaient le nom d'origine du client sous
`pieces-jointes/<id-organisation>/<nom>`, et la « rétention 7 jours » ne
supprimait rien du disque.

## Pourquoi une signature, et pas une authentification

Deux consommateurs légitimes ne peuvent présenter aucune session :

- **Brevo** récupère les pièces jointes par URL, depuis Internet, pour les
  joindre au courriel ;
- le **client final de l'abonné** ouvre son lien de livraison sans avoir de
  compte chez nous — il n'est pas notre utilisateur.

Exiger un jeton de session fermerait la livraison. La signature répond au vrai
besoin : le lien reste ouvrable par qui le reçoit, mais il ne peut pas être
**deviné**, et il **expire**.

## Chaque lien porte sa propre échéance

La durée de vie était **globale**, alors que la conservation d'un document se
règle **par offre** — et que le courriel de livraison annonce au client la
seconde. Une offre à trente jours aurait donc produit un lien mort au huitième,
avec un 404 que rien ne distingue d'une suppression. La durée voyage désormais
dans le jeton, et elle est signée : celui qui détient le lien ne peut pas la
rallonger.

## Ce que cela ne protège pas

Un lien transmis reste utilisable jusqu'à son expiration : c'est inhérent à un
lien porteur. Ce qui disparaît, c'est l'énumération — deviner le nom d'un
fichier ne suffit plus — et la validité éternelle.
"""
from __future__ import annotations

from django.conf import settings
from django.core import signing

#: Sel de signature. Distinct de tout autre usage de `SECRET_KEY` : deux
#: signatures de natures différentes ne doivent jamais être interchangeables.
SEL = "evkha.media"

#: Nom du paramètre portant la signature dans l'URL.
PARAMETRE = "s"


#: Préfixe de la durée portée par le jeton. Il rend le format reconnaissable
#: sans ambiguïté : l'horodatage de Django est en base 62 et peut commencer par
#: une lettre, donc seul un marqueur choisi permet de distinguer à coup sûr un
#: jeton neuf d'un jeton de l'ancien format.
MARQUEUR_DUREE = "d"


def duree_de_validite() -> int:
    """Durée de vie d'un lien qui n'en précise aucune, en secondes.

    Ce n'est plus qu'un **repli**. La durée qui compte est celle que l'appelant
    passe à `lien()`, parce que lui seul connaît l'offre du dossier — voir
    `evkha/retention.py`. Une durée globale ne pouvait pas être juste : le
    courriel promet la rétention de l'offre, qui se règle offre par offre.
    """
    from . import retention  # noqa: PLC0415 — evite un cycle a l'import

    return int(getattr(
        settings, "EVKHA_MEDIA_DUREE_LIEN_S", retention.jours_par_defaut() * 24 * 3600
    ))


def signer(chemin: str, duree_s: int | None = None) -> str:
    """Jeton horodaté valable pour CE chemin, et pour cette durée seulement.

    Le chemin fait partie du message signé : une signature valable pour un
    fichier ne vaut donc rien pour un autre. Sans cela, il suffirait de
    recopier la signature d'un document qu'on possède sur l'URL d'un document
    qu'on convoite.

    **La durée aussi est signée**, et c'est ce qui permet à chaque lien de
    porter sa propre échéance. Le vérificateur ne connaît ni le dossier ni son
    offre — il ne voit qu'un chemin et un jeton. Faute de porter la durée, il
    ne pouvait qu'appliquer une valeur globale, et un lien annoncé pour trente
    jours mourait au septième. Une durée signée ne peut pas être rallongée par
    celui qui détient le lien : y toucher invalide la signature.

    `TimestampSigner` et non `Signer` : la seconde ne porte aucune date, et le
    lien serait éternel. La durée de vie annoncée par ce module doit exister
    dans le jeton, pas seulement dans sa documentation (règle 1).
    """
    propre = chemin.lstrip("/")
    secondes = int(duree_s if duree_s is not None else duree_de_validite())
    message = f"{propre}:{MARQUEUR_DUREE}{secondes}"
    signe = signing.TimestampSigner(salt=SEL).sign(message)
    # `sign` rend « message:horodatage:signature ». Seule la partie qui suit le
    # chemin voyage dans l'URL — le chemin y figure déjà.
    return str(signe[len(propre) + 1 :])


def lien(chemin: str, duree_s: int | None = None) -> str:
    """Chemin d'accès complet, signature comprise, relatif au domaine."""
    propre = chemin.lstrip("/")
    return f"/media/{propre}?{PARAMETRE}={signer(propre, duree_s)}"


def _duree_portee(presentee: str) -> int | None:
    """Durée inscrite dans le jeton, ou `None` s'il est de l'ancien format.

    Les liens déjà envoyés aux clients ne portent pas de durée. Les refuser
    d'un bloc casserait des livraisons en cours pour une amélioration interne :
    on les accepte encore, avec la durée de repli qui était la leur.
    """
    morceaux = presentee.split(":")
    if len(morceaux) != 3:
        return None
    tete = morceaux[0]
    if not tete.startswith(MARQUEUR_DUREE) or not tete[1:].isdigit():
        return None
    return int(tete[1:])


def signature_valable(chemin: str, presentee: str) -> bool:
    """La signature présentée est-elle valable pour ce chemin, et non expirée ?

    `unsign` vérifie les deux d'un coup, en temps constant. Écrire la
    comparaison à la main exposerait à la reconstituer en mesurant les temps de
    réponse — et à oublier la date, qui est la moitié de l'intérêt.
    """
    propre = chemin.lstrip("/")
    if not presentee:
        return False
    portee = _duree_portee(presentee)
    try:
        signing.TimestampSigner(salt=SEL).unsign(
            f"{propre}:{presentee}",
            max_age=portee if portee is not None else duree_de_validite(),
        )
    except signing.BadSignature:
        # Couvre la signature fausse ET la signature expirée
        # (`SignatureExpired` en hérite) : dans les deux cas, on refuse.
        return False
    return True

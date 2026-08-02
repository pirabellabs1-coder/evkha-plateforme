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


def duree_de_validite() -> int:
    """Durée de vie d'un lien, en secondes.

    Alignée par défaut sur la rétention des documents — sept jours : un lien
    qui survivrait au fichier enverrait le client sur une erreur, et un lien
    qui mourrait avant lui le priverait d'un document encore disponible.
    """
    return int(getattr(settings, "EVKHA_MEDIA_DUREE_LIEN_S", 7 * 24 * 3600))


def signer(chemin: str) -> str:
    """Jeton horodaté valable pour CE chemin, et pour lui seul.

    Le chemin fait partie du message signé : une signature valable pour un
    fichier ne vaut donc rien pour un autre. Sans cela, il suffirait de
    recopier la signature d'un document qu'on possède sur l'URL d'un document
    qu'on convoite.

    `TimestampSigner` et non `Signer` : la seconde ne porte aucune date, et le
    lien serait éternel. La durée de vie annoncée par ce module doit exister
    dans le jeton, pas seulement dans sa documentation (règle 1).
    """
    propre = chemin.lstrip("/")
    signe = signing.TimestampSigner(salt=SEL).sign(propre)
    # `sign` rend « chemin:horodatage:signature ». Seule la queue voyage dans
    # l'URL — le chemin y figure déjà, le répéter n'apporterait rien.
    return str(signe[len(propre) + 1 :])


def lien(chemin: str) -> str:
    """Chemin d'accès complet, signature comprise, relatif au domaine."""
    propre = chemin.lstrip("/")
    return f"/media/{propre}?{PARAMETRE}={signer(propre)}"


def signature_valable(chemin: str, presentee: str) -> bool:
    """La signature présentée est-elle valable pour ce chemin, et non expirée ?

    `unsign` vérifie les deux d'un coup, en temps constant. Écrire la
    comparaison à la main exposerait à la reconstituer en mesurant les temps de
    réponse — et à oublier la date, qui est la moitié de l'intérêt.
    """
    propre = chemin.lstrip("/")
    if not presentee:
        return False
    try:
        signing.TimestampSigner(salt=SEL).unsign(
            f"{propre}:{presentee}", max_age=duree_de_validite()
        )
    except signing.BadSignature:
        # Couvre la signature fausse ET la signature expirée
        # (`SignatureExpired` en hérite) : dans les deux cas, on refuse.
        return False
    return True

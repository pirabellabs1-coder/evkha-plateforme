"""Chargement du logo du client final pour la couverture (lot 3).

Le formulaire ne fournit qu'une **URL**. La chaîne HTML s'en contentait — le
navigateur du lecteur allait la chercher. Un `.docx` ne le peut pas : une image
Word est embarquée, pas référencée. Il faut donc récupérer les octets au
moment du rendu.

C'est le seul appel réseau sortant de toute la chaîne de rendu, et il est
déclenché par une URL saisie dans un formulaire. Il est donc borné
explicitement :

- schémas `http` et `https` uniquement — pas de `file://`, pas de `data:` ;
- délai court, et une seule tentative : un logo n'immobilise pas une
  génération ;
- taille plafonnée, pour qu'une URL pointant vers un fichier volumineux ne
  fasse pas enfler le livrable ;
- types d'image reconnus par leur **signature binaire**, jamais par l'en-tête
  `Content-Type` annoncé, qui n'engage que celui qui l'envoie.

Tout échec est silencieux du point de vue du document — la couverture se rend
sans logo — mais jamais du point de vue du journal : le motif est tracé.
"""
from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

#: Au-delà, on renonce : le logo n'a pas à peser plus qu'un chapitre entier.
TAILLE_MAX_OCTETS = 5 * 1024 * 1024
DELAI_S = 5.0

#: Signatures des formats que Word sait embarquer et que python-docx accepte.
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"BM", "bmp"),
)


def format_image(contenu: bytes) -> str | None:
    """Format déduit des premiers octets, ou None si ce n'est pas une image.

    Un SVG est volontairement refusé : python-docx ne sait pas l'embarquer, et
    l'accepter produirait un document que Word ouvre en signalant une image
    corrompue — un échec bien plus difficile à diagnostiquer qu'une couverture
    sans logo.
    """
    for signature, nom in _SIGNATURES:
        if contenu.startswith(signature):
            return nom
    return None


def _depuis_le_disque(reference: str) -> bytes | None:
    """Logo déposé dans l'espace client, relu localement.

    Depuis que le client **téléverse** son logo au lieu d'en donner l'URL, le
    fichier est déjà sur le disque du serveur. Aller le rechercher par HTTP
    serait absurde : le serveur s'appellerait lui-même, échouerait dès que
    l'URL publique diffère de l'URL interne, et rendrait le rendu dépendant du
    réseau pour un fichier qu'il a sous la main.

    La lecture est **confinée** au répertoire des médias : une référence
    contenant `..` ne peut pas remonter ailleurs sur le disque.
    """
    from pathlib import Path  # noqa: PLC0415

    from django.conf import settings  # noqa: PLC0415

    racine = Path(str(getattr(settings, "MEDIA_ROOT", "") or "media")).resolve()
    prefixe = str(getattr(settings, "MEDIA_URL", "/media/"))
    relatif = reference[len(prefixe) :] if reference.startswith(prefixe) else reference

    try:
        chemin = (racine / relatif.lstrip("/")).resolve()
        chemin.relative_to(racine)
    except (ValueError, OSError):
        _log.warning("Logo ignoré : chemin hors du répertoire des médias.")
        return None

    if not chemin.is_file():
        return None
    return chemin.read_bytes()


def charger_logo(url: str) -> bytes | None:
    """Octets du logo, ou None si la référence est inexploitable.

    Deux cas, dans cet ordre :

    1. un fichier **déposé** dans l'espace client — relu sur le disque ;
    2. une URL externe, héritée de l'ancien formulaire — récupérée par HTTP.

    Ne lève jamais : un logo absent est un défaut d'apparence, pas une raison
    de perdre un livrable pour lequel le client a payé.
    """
    url = (url or "").strip()
    if not url:
        return None

    if not url.startswith(("http://", "https://")):
        depose = _depuis_le_disque(url)
        if depose is not None and format_image(depose) is not None:
            return depose
        _log.warning("Logo ignoré : référence inexploitable (%s).", url[:80])
        return None

    try:
        contenu = _telecharger_hors_du_reseau_interne(url)
    except Exception as erreur:  # noqa: BLE001 — aucune cause ne justifie de perdre le livrable
        _log.warning("Logo non récupéré (%s) : %s", url[:80], erreur)
        return None
    if contenu is None:
        return None

    if len(contenu) > TAILLE_MAX_OCTETS:
        _log.warning(
            "Logo ignoré : %s octets, plafond %s.", len(contenu), TAILLE_MAX_OCTETS
        )
        return None
    if format_image(contenu) is None:
        _log.warning("Logo ignoré : le contenu récupéré n'est pas une image reconnue.")
        return None
    return contenu


#: Nombre de redirections suivies. Chacune est contrôlée avant d'être suivie.
REDIRECTIONS_MAX = 3


class AdresseInterneRefuseeError(ValueError):
    """L'URL vise le réseau de la plateforme, pas Internet."""


def _vise_le_reseau_interne(url: str) -> bool:
    """L'hôte de cette URL résout-il vers une adresse non publique ?

    On vérifie l'adresse RÉSOLUE, pas le nom écrit. Sans cela, il suffirait de
    faire pointer un domaine public vers 127.0.0.1 pour passer : le contrôle
    porterait sur ce que l'appelant écrit, jamais sur ce que le serveur joint
    (règle 1).

    `is_global` couvre d'un coup la boucle locale, les plages privées, le
    lien-local — donc l'API de métadonnées de l'hébergeur en 169.254.169.254 —
    et les adresses réservées. Énumérer les hôtes interdits (`redis`,
    `postgres`, `localhost`…) aurait été sans fin et faux dès le prochain
    service ajouté à la pile (règle 4).
    """
    import ipaddress  # noqa: PLC0415
    import socket  # noqa: PLC0415
    from urllib.parse import urlparse  # noqa: PLC0415

    hote = urlparse(url).hostname
    if not hote:
        return True

    try:
        resolutions = socket.getaddrinfo(hote, None)
    except OSError:
        # Nom introuvable : rien à joindre, donc rien à protéger — mais on
        # refuse quand même, faute de pouvoir juger (règle 1).
        return True

    for famille in resolutions:
        adresse = famille[4][0]
        try:
            if not ipaddress.ip_address(adresse).is_global:
                return True
        except ValueError:
            return True
    return False


def _telecharger_hors_du_reseau_interne(url: str) -> bytes | None:
    """Récupère une URL externe, en refusant tout ce qui pointe chez nous.

    `httpx.get(..., follow_redirects=True)` était appelé sans aucune
    restriction d'hôte. Un abonné qui écrit `http://redis:6379/` dans son
    champ « logo » faisait émettre la requête **par le worker**, à l'intérieur
    du réseau Docker où aucun de ces ports n'est exposé publiquement. Les
    erreurs et les temps de réponse suffisent alors à cartographier la pile.

    Les redirections sont suivies à la main : une URL parfaitement publique
    peut répondre `302 → http://postgres:5432`, et le contrôle initial n'aurait
    rien vu passer. Chaque saut est donc contrôlé (règle 3 : ce qui refait la
    requête après le contrôle doit être contrôlé à son tour).
    """
    import httpx  # noqa: PLC0415

    vue = url
    for _ in range(REDIRECTIONS_MAX + 1):
        if _vise_le_reseau_interne(vue):
            msg = "l'adresse vise le réseau interne de la plateforme"
            raise AdresseInterneRefuseeError(msg)

        reponse = httpx.get(vue, timeout=DELAI_S, follow_redirects=False)
        if reponse.is_redirect:
            suivante = reponse.headers.get("location", "")
            if not suivante:
                return None
            vue = str(httpx.URL(vue).join(suivante))
            continue

        reponse.raise_for_status()
        return bytes(reponse.content)

    _log.warning("Logo ignoré : trop de redirections (%s).", url[:80])
    return None

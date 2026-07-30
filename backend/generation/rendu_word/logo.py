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
        import httpx  # noqa: PLC0415

        reponse = httpx.get(url, timeout=DELAI_S, follow_redirects=True)
        reponse.raise_for_status()
        contenu = reponse.content
    except Exception as erreur:  # noqa: BLE001 — aucune cause ne justifie de perdre le livrable
        _log.warning("Logo non récupéré (%s) : %s", url[:80], erreur)
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

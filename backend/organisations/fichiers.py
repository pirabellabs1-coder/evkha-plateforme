"""Téléversement de fichiers depuis l'espace client.

Les questionnaires demandent un logo et des documents complémentaires
(tableaux financiers, études déjà réalisées, présentations). Jusqu'ici seule
une **URL** était acceptée, ce qui suppose que le client héberge déjà ses
fichiers quelque part — hypothèse fausse pour la plupart.

## Ce qui est vérifié, et pourquoi

**Le type est lu dans les octets, jamais dans le nom du fichier ni dans
l'en-tête `Content-Type`.** Une extension se renomme et un en-tête s'écrit à la
main ; une signature binaire, non. Un fichier annoncé `logo.png` mais contenant
autre chose serait sinon accepté, puis embarqué dans un `.docx` que Word
refuserait d'ouvrir — défaut bien plus difficile à diagnostiquer qu'un refus au
dépôt.

**Les plafonds sont ceux des formulaires Tally** : 2 Mo pour un logo, 10 Mo
pour un document. Les changer ici sans les changer là ferait accepter chez nous
ce que le client croit refusé, ou l'inverse.

**Le SVG est refusé pour un logo.** `python-docx` ne sait pas l'embarquer :
l'accepter produirait un document que Word ouvre en signalant une image
corrompue.

**Aucun fichier n'est exécuté, rendu, ni servi depuis le domaine de l'API.**
Ils sont stockés et relus comme des octets.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

_log = logging.getLogger(__name__)

#: Plafonds repris des formulaires Tally, à l'octet près.
TAILLE_MAX_LOGO = 2 * 1024 * 1024
TAILLE_MAX_DOCUMENT = 10 * 1024 * 1024


@dataclass(frozen=True)
class TypeFichier:
    """Un format accepté, identifié par sa signature binaire."""

    nom: str
    extension: str
    #: Octets de tête. Plusieurs variantes possibles pour un même format.
    signatures: tuple[bytes, ...]
    type_mime: str


#: Images embarquables dans un `.docx`. Le SVG en est volontairement absent.
IMAGES: tuple[TypeFichier, ...] = (
    TypeFichier("PNG", ".png", (b"\x89PNG\r\n\x1a\n",), "image/png"),
    TypeFichier("JPEG", ".jpg", (b"\xff\xd8\xff",), "image/jpeg"),
)

#: Documents joints. `PK\x03\x04` est l'en-tête ZIP : les formats Office
#: modernes (docx, xlsx, pptx) sont des archives ZIP, on ne peut pas les
#: distinguer par leur seule signature — l'extension départage, et c'est
#: acceptable ici puisque le contenu n'est ni exécuté ni rendu.
DOCUMENTS: tuple[TypeFichier, ...] = (
    TypeFichier("PDF", ".pdf", (b"%PDF-",), "application/pdf"),
    TypeFichier(
        "Office",
        ".docx",
        (b"PK\x03\x04",),
        "application/vnd.openxmlformats-officedocument",
    ),
    TypeFichier(
        "Office 97-2003",
        ".doc",
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
        "application/msword",
    ),
)


class FichierRefuseError(ValueError):
    """Le fichier ne peut pas être accepté. Le message est destiné au client."""


def _reconnaitre(contenu: bytes, formats: tuple[TypeFichier, ...]) -> TypeFichier | None:
    return next(
        (
            format_fichier
            for format_fichier in formats
            if any(contenu.startswith(sig) for sig in format_fichier.signatures)
        ),
        None,
    )


def valider_logo(contenu: bytes, nom: str = "") -> TypeFichier:
    """Vérifie qu'un logo est embarquable. Lève `FichierRefuseError` sinon."""
    if not contenu:
        msg = "Le fichier est vide."
        raise FichierRefuseError(msg)
    if len(contenu) > TAILLE_MAX_LOGO:
        msg = (
            f"Le logo dépasse {TAILLE_MAX_LOGO // (1024 * 1024)} Mo "
            f"({len(contenu) / (1024 * 1024):.1f} Mo)."
        )
        raise FichierRefuseError(msg)

    format_trouve = _reconnaitre(contenu, IMAGES)
    if format_trouve is None:
        # Message explicite plutôt que « format invalide » : le SVG est le cas
        # le plus fréquent, et le client doit savoir quoi faire.
        msg = (
            "Format non accepté pour un logo. Utilisez un PNG ou un JPEG — le "
            "SVG ne peut pas être intégré dans un document Word."
        )
        raise FichierRefuseError(msg)
    _log.debug("Logo accepté : %s (%s octets, %s)", nom, len(contenu), format_trouve.nom)
    return format_trouve


def valider_document(contenu: bytes, nom: str = "") -> TypeFichier:
    """Vérifie qu'un document joint est acceptable."""
    if not contenu:
        msg = "Le fichier est vide."
        raise FichierRefuseError(msg)
    if len(contenu) > TAILLE_MAX_DOCUMENT:
        msg = (
            f"Le fichier dépasse {TAILLE_MAX_DOCUMENT // (1024 * 1024)} Mo "
            f"({len(contenu) / (1024 * 1024):.1f} Mo)."
        )
        raise FichierRefuseError(msg)

    format_trouve = _reconnaitre(contenu, (*DOCUMENTS, *IMAGES))
    if format_trouve is None:
        msg = (
            "Format non accepté. Formats attendus : PDF, Word, Excel, "
            "PowerPoint, PNG ou JPEG."
        )
        raise FichierRefuseError(msg)
    _log.debug("Document accepté : %s (%s octets)", nom, len(contenu))
    return format_trouve


#: Extensions qu'un fichier stocké peut porter. Liste FERMÉE, dérivée des
#: formats acceptés — jamais saisie à la main, sinon les deux divergeraient
#: (règle 5). Les variantes Office partagent la même signature ZIP et ne se
#: distinguent que par l'extension : elles sont donc admises explicitement.
EXTENSIONS_ADMISES = frozenset(
    {format_fichier.extension for format_fichier in (*DOCUMENTS, *IMAGES)}
    | {".xlsx", ".pptx", ".jpeg", ".xls", ".ppt"}
)


def nom_sur(nom: str, format_trouve: TypeFichier | None = None) -> str:
    """Nom de fichier débarrassé de tout ce qui pourrait sortir du dossier —
    **et de toute extension que nous n'avons pas choisie**.

    Le nettoyage des séparateurs existait déjà. Il manquait l'essentiel :
    l'extension du client était conservée telle quelle. Or c'est elle, et non
    le contenu, qui décide du `Content-Type` avec lequel un serveur rend un
    fichier.

    Le scénario complet, vérifié : un fichier nommé `rapport.html` dont les
    premiers octets sont `%PDF-` passe la reconnaissance binaire — qui ne
    regarde que la tête — puis est stocké en `.html`, puis servi en
    `text/html` sur le domaine qui héberge `/admin/` et `/api/dashboard/`. Le
    reste du fichier peut être ce qu'on veut. L'inscription étant libre, il n'y
    a aucun préalable à réunir.

    La docstring de ce module affirmait « Aucun fichier n'est exécuté, rendu,
    ni servi depuis le domaine de l'API ». C'était faux, et c'est sur cette
    phrase que reposait l'acceptation de l'extension du client.

    Le correctif ne bannit pas `.html` : énumérer les extensions dangereuses
    est sans fin (`.svg`, `.xhtml`, `.htm`, `.xml`…). Il retient une liste
    **fermée** de ce qui est admis, et remplace tout le reste par l'extension
    du format reconnu dans les octets (règle 4 : la classe, pas l'exemple).
    """
    dernier = nom.replace("\\", "/").rsplit("/", 1)[-1].strip()
    propre = "".join(c for c in dernier if c.isalnum() or c in " ._-()")
    propre = (propre or "fichier")[:120]

    if format_trouve is None:
        return propre

    base, point, extension = propre.rpartition(".")
    if point and f".{extension.lower()}" in EXTENSIONS_ADMISES:
        return propre

    # Aucune extension, ou une extension hors de la liste fermée : c'est le
    # format lu dans les octets qui tranche.
    return f"{base or propre}{format_trouve.extension}"

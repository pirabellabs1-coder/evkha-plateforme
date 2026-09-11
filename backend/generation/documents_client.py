"""Les documents que le client a déposés, enfin LUS par la génération.

## Le défaut, mesuré sur un livrable réel

Stratégie du dossier `f7f2fad9`, livrée le 08/09/2026. La cliente avait joint
son prévisionnel et une étude de marché régionale. Aucun livrable ne lisait les
pièces jointes — le prompt de la fiche projet promettait pourtant au modèle de
« reformuler le brief et les pièces jointes ». Privé de cette matière, le
modèle a comblé le vide : un marché national « estimé à 900 millions d'euros »
sans source, et un « objectif » de 3 000 € qui était en fait le chiffre
d'affaires ACTUEL annualisé. Cliente : « il existait une donnée réelle et
sourcée dans les documents transmis, que le système n'a pas utilisée ».

## Ce que ce module fait

1. Au lancement du dossier, il lit chaque document de la bibliothèque de
   l'organisation — PDF, Word, Excel, PowerPoint — et en garde le texte sur le
   dossier (`DocumentClientLu`). Une relance relit la même matière, jamais une
   bibliothèque qui a bougé entre-temps.
2. Le texte part au socle, qui en tire les chiffres de référence, à sa
   vérification, qui peut alors CONFIRMER un chiffre publié qu'un document
   reproduit, et à chaque chapitre, dans la partie du prompt mise en cache.

## Ce qu'il ne fait pas, et le DIT

Une image, un PDF scanné sans texte, un format Office 97-2003 ne sont pas lus.
Chacun reçoit une ligne `non_lu` ou `illisible` avec sa raison, et un incident
nomme ce qui a été écarté (règle 1) : un document qu'on croit lu et qui ne
l'est pas, c'est exactement le défaut qu'on répare.

Le volume est borné (`LIMITE_TOTALE`) : au-delà, chaque document garde une part
équitable. La coupure est écrite dans la trace et l'incident — jamais dans le
prompt, où le modèle la recopierait au client.

## Pourquoi Excel et PowerPoint sont lus sans bibliothèque

Un `.xlsx` et un `.pptx` sont des archives de XML au format publié et stable.
Les lire directement évite deux dépendances de plus dans l'image pour ce qui
tient en quelques dizaines de lignes. Le `.docx` suit le même chemin, par
cohérence : la bibliothèque `python-docx` ne sert qu'à remplir le gabarit.
"""
from __future__ import annotations

import logging
import posixpath
import re
import time
import zipfile
from collections.abc import Callable, Generator
from dataclasses import dataclass
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from xml.etree import ElementTree

if TYPE_CHECKING:
    from .models import DocumentClientLu, GenerationJob

_log = logging.getLogger(__name__)

#: Caractères de documents transmis au modèle, tous documents confondus. Environ
#: 11 000 jetons : le socle les lit une fois (trois au plus s'il est refusé), les
#: chapitres les relisent depuis le cache, à un dixième du prix.
LIMITE_TOTALE = 40_000

#: Au-delà, les documents suivants ne sont pas lus — et le disent.
MAX_DOCUMENTS = 12

#: Un rapport annuel de trois cents pages n'apporterait rien de plus que ses
#: cent cinquante premières, et coûterait le temps du worker.
MAX_PAGES_PDF = 150

#: Octets RÉELLEMENT décompressés, par partie et par archive. Le plafond ne
#: porte jamais sur la taille que l'archive DÉCLARE : elle est écrite par
#: l'expéditeur. Audit du 11/09/2026 : un `.docx` de 291 Ko déclarant 100
#: octets en décompressait 300 Mo, et faisait monter le worker — partagé par
#: toutes les générations — à 616 Mo avant le moindre refus. Au-delà de ces
#: volumes il n'y a aucun texte utile de plus : le modèle n'en reçoit que
#: 40 000 caractères, et l'arbre XML en mémoire pèse plusieurs fois la partie.
MAX_OCTETS_PARTIE = 15 * 1024 * 1024
MAX_OCTETS_ARCHIVE = 30 * 1024 * 1024
#: Plus bas pour une partie dont on construit l'ARBRE (corps d'un Word, une
#: diapositive, les styles) : en mémoire, un arbre pèse une vingtaine de fois
#: son XML. Six mégaoctets de `document.xml`, c'est plus d'un millier de pages.
MAX_OCTETS_ARBRE = 6 * 1024 * 1024
#: Taille des morceaux décompressés à la fois.
_MORCEAU = 64 * 1024
#: Un classeur réel compte quelques dizaines d'entrées ; dix mille petites
#: parties sous le plafond ne sont pas un classeur.
MAX_ENTREES_ARCHIVE = 2000

#: Temps de lecture d'un PDF. Au-delà, les pages restantes ne sont pas lues,
#: et la coupure est écrite. Un PDF construit pour être lent ne doit pas
#: occuper indéfiniment le worker des autres clients. Les bombes de
#: décompression PDF, elles, sont bornées par pypdf 6 lui-même
#: (`pypdf.filters.ZLIB_MAX_OUTPUT_LENGTH`) — d'où son plancher de version.
DUREE_MAX_PDF_SECONDES = 60.0

#: En dessous, un PDF n'a pas de texte à lire : c'est une image de document.
_MIN_CARACTERES_PDF = 100
#: En dessous, une PAGE n'a pas de texte : scannée, ou faite d'une image.
_MIN_CARACTERES_PAGE = 20

#: Un prévisionnel mensuel sur cinq ans compte soixante et une colonnes : la
#: limite doit le contenir, et ce qui la dépasse se déclare.
_MAX_COLONNES = 120

#: Au-delà, un lecteur s'arrête : le modèle ne recevra jamais plus que
#: `LIMITE_TOTALE` caractères d'un même document.
PLAFOND_EXTRACTION = LIMITE_TOTALE


class _Illisible(Exception):  # noqa: N818 — motif destiné à un humain
    """Le document ne peut pas être lu. Le message dit pourquoi."""


@dataclass(frozen=True)
class Extraction:
    statut: str
    texte: str = ""
    motif: str = ""


# ── Formats ──────────────────────────────────────────────────────────────────

_ANCIENS_FORMATS = {
    ".doc": ".docx", ".xls": ".xlsx", ".ppt": ".pptx",
}
_IMAGES = {".png", ".jpg", ".jpeg"}


def extraire(nom: str, contenu: bytes) -> Extraction:
    """Le texte d'un document, ou la raison pour laquelle il n'en a pas.

    Le format se lit à l'EXTENSION du fichier stocké : les formats Office
    récents partagent tous la signature ZIP, et le type déclaré au dépôt est
    générique (`organisations/fichiers.py`).

    ## Toute perte se déclare

    Chaque lecteur tient la liste de ce qu'il n'a PAS lu — une feuille
    introuvable, des colonnes au-delà de la limite, des pages scannées, un
    graphique dont les données restent dans le fichier. Un document qui a perdu
    quoi que ce soit est « lu en partie », avec ses pertes pour motif ; il ne
    s'affiche jamais « lu en entier ». La relecture du 11/09/2026 a trouvé six
    pertes silencieuses différentes : corriger chacune aurait laissé passer la
    septième (règle 4). C'est la déclaration qui est obligatoire, pas la liste.
    """
    from .models import StatutLecture  # noqa: PLC0415

    extension = Path(nom).suffix.lower()
    if extension in _ANCIENS_FORMATS:
        return Extraction(
            StatutLecture.NON_LU,
            motif=(
                f"format Office 97-2003 ({extension}) non lu : réenregistrer le "
                f"document en {_ANCIENS_FORMATS[extension]}"
            ),
        )
    if extension in _IMAGES:
        return Extraction(
            StatutLecture.NON_LU,
            motif="image : son contenu n'est pas lu",
        )
    lecteur = _LECTEURS.get(extension)
    if lecteur is None:
        return Extraction(StatutLecture.NON_LU, motif=f"format {extension or 'inconnu'} non lu")
    pertes: list[str] = []
    try:
        texte = _nettoyer(lecteur(contenu, pertes))
    except _Illisible as raison:
        return Extraction(StatutLecture.ILLISIBLE, motif=str(raison))
    except Exception as erreur:  # noqa: BLE001 — un fichier abîmé ne tue pas le dossier
        _log.warning("Lecture de %s impossible", nom, exc_info=True)
        return Extraction(
            StatutLecture.ILLISIBLE,
            motif=f"lecture impossible ({type(erreur).__name__})",
        )
    if not texte:
        return Extraction(StatutLecture.ILLISIBLE, motif="le document ne contient aucun texte")
    if pertes:
        return Extraction(StatutLecture.TRONQUE, texte=texte, motif=" ; ".join(pertes))
    return Extraction(StatutLecture.LU, texte=texte)


def _perdre(pertes: list[str], raison: str) -> None:
    if raison not in pertes:
        pertes.append(raison)


def _nettoyer(texte: str) -> str:
    texte = texte.replace("\r", "\n").replace("\xa0", " ")
    # Une tabulation entre deux mots SÉPARE deux colonnes : c'est la mise en
    # page ordinaire d'un prévisionnel sous Word. Réduite à une espace, elle
    # collait l'année au montant — « 2025⇥45 000 € » devenait « 202545 000 € »,
    # un faux chiffre attribué au client (relecture du 11/09/2026).
    texte = re.sub(r"(?<=\S)[ \t]*\t[ \t]*(?=\S)", " | ", texte)
    texte = re.sub(r"[ \t]+", " ", texte)
    texte = re.sub(r" *\n *", "\n", texte)
    texte = re.sub(r"\n{3,}", "\n\n", texte)
    return texte.strip()


def _local(tag: str) -> str:
    """Le nom d'une balise sans son espace de noms.

    Les formats Office existent en deux dialectes (transitionnel et strict)
    aux espaces de noms différents : comparer les noms locaux lit les deux.
    """
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


class _Archive:
    """Une archive Office dont on lit les parties SOUS BUDGET.

    `ZipExtFile.read(n)` ne décompresse qu'environ `n` octets : c'est lui qui
    borne réellement la mémoire, là où `ZipInfo.file_size` n'est qu'une
    déclaration de l'expéditeur.
    """

    def __init__(self, contenu: bytes, pertes: list[str]) -> None:
        self.pertes = pertes
        try:
            self.zip = zipfile.ZipFile(BytesIO(contenu))
        except zipfile.BadZipFile as erreur:
            msg = "archive Office endommagée"
            raise _Illisible(msg) from erreur
        if len(self.zip.infolist()) > MAX_ENTREES_ARCHIVE:
            self.zip.close()
            msg = f"archive de plus de {MAX_ENTREES_ARCHIVE} entrées refusée"
            raise _Illisible(msg)
        self.reste = MAX_OCTETS_ARCHIVE
        self.noms = set(self.zip.namelist())

    def __enter__(self) -> _Archive:
        return self

    def __exit__(self, *exc: object) -> None:
        self.zip.close()

    def contient_un(self, prefixe: str) -> bool:
        return any(nom.startswith(prefixe) for nom in self.noms)

    def evenements(
        self,
        nom: str,
        *,
        plafond: int = MAX_OCTETS_PARTIE,
        quoi: tuple[str, ...] = ("end",),
    ) -> Generator[tuple[str, ElementTree.Element], None, None]:
        """Les événements XML d'une partie, décompressée PAR MORCEAUX.

        Au plafond — de la partie ou de l'archive —, la lecture s'ARRÊTE et la
        perte se déclare : ce qui a été lu reste lu. La première version
        refusait le document entier dès qu'une partie dépassait, si bien
        qu'une seule grosse feuille rendait un prévisionnel illisible
        (contre-relecture du 11/09/2026).
        """
        lecteur = ElementTree.XMLPullParser(events=quoi)
        lu = 0
        queue = b""
        try:
            with self.zip.open(nom) as flux:
                while True:
                    reste = min(plafond, self.reste) - lu
                    if reste <= 0:
                        if flux.read(1):
                            _perdre(
                                self.pertes,
                                f"partie {nom} lue en partie : volume maximal atteint",
                            )
                        return
                    morceau = flux.read(min(_MORCEAU, reste))
                    if not morceau:
                        return
                    # Une partie Office ne porte jamais de DTD. En refuser une
                    # ferme la porte aux entités qui se démultiplient à la
                    # lecture. La fenêtre chevauche deux morceaux : une
                    # déclaration coupée en deux ne passe pas entre eux.
                    fenetre = queue + morceau
                    if b"<!DOCTYPE" in fenetre or b"<!ENTITY" in fenetre:
                        msg = f"partie {nom} refusée : déclaration de document inattendue"
                        raise _Illisible(msg)
                    queue = morceau[-16:]
                    lu += len(morceau)
                    lecteur.feed(morceau)
                    for evenement in lecteur.read_events():
                        yield cast("tuple[str, ElementTree.Element]", evenement)
        finally:
            self.reste -= lu

    def arbre(self, nom: str) -> ElementTree.Element:
        """L'arbre d'une partie — partiel, et déclaré tel, au-delà du plafond.

        Plafond plus bas que pour les feuilles, lues au fil de l'eau : un arbre
        complet pèse en mémoire une vingtaine de fois son XML.
        """
        racine: ElementTree.Element | None = None
        for _, element in self.evenements(nom, plafond=MAX_OCTETS_ARBRE, quoi=("start",)):
            if racine is None:
                racine = element
        if racine is None:
            msg = f"partie {nom} vide ou illisible"
            raise _Illisible(msg)
        return racine

    def cible(self, base: str, cible: str) -> str:
        """Chemin d'une relation, résolu dans l'archive (`../xl/…`, `/xl/…`)."""
        if cible.startswith("/"):
            return cible.lstrip("/")
        return posixpath.normpath(posixpath.join(base, cible))


def _texte_de(element: ElementTree.Element) -> str:
    """Le texte d'un élément : tabulations, sauts de ligne et paragraphes compris.

    Seuls les `t` étaient lus : `w:tab`, `w:br`, `w:cr`, `a:br` disparaissaient,
    et deux nombres voisins se collaient en un seul. Les PARAGRAPHES aussi
    doivent se séparer : une cellule de tableau « CA 2025 » / « 45 000 € » se
    lisait « CA 202545 000 € » (contre-relecture du 11/09/2026). Même classe
    de défaut, même réponse : tout ce qui sépare à l'écran sépare dans le texte.

    Une tabulation de paragraphe (`w:pPr/w:tabs/w:tab`) porte des attributs de
    position : ce n'est pas un caractère, elle ne s'écrit pas. Le rendu de
    repli (`mc:Fallback`) double le rendu moderne d'une zone de texte : on ne
    le lit pas.
    """
    morceaux: list[str] = []

    def visiter(e: ElementTree.Element, racine: bool) -> None:
        nom = _local(e.tag)
        if nom == "Fallback":
            return
        if nom == "t":
            morceaux.append(e.text or "")
        elif nom in ("br", "cr"):
            morceaux.append("\n")
        elif nom == "tab" and not e.attrib:
            morceaux.append("\t")
        for enfant in e:
            visiter(enfant, False)
        if nom == "p" and not racine:
            morceaux.append("\n")

    visiter(element, True)
    return "".join(morceaux).strip("\n")


def _cellule(element: ElementTree.Element) -> str:
    """Le texte d'une cellule de tableau, sur une ligne.

    Ses paragraphes se séparent par « / », jamais par une simple espace : « 2025
    45 000 € » se relirait comme un seul nombre.
    """
    lignes = [ligne.strip() for ligne in _texte_de(element).split("\n")]
    return " / ".join(ligne for ligne in lignes if ligne)


def _plafond_atteint(taille: int, pertes: list[str]) -> bool:
    """Au-delà de ce que le modèle recevra jamais, lire ne sert plus à rien."""
    if taille <= PLAFOND_EXTRACTION:
        return False
    _perdre(
        pertes,
        f"lu sur ses {PLAFOND_EXTRACTION} premiers caractères, au-delà desquels "
        "rien n'est transmis",
    )
    return True


def _graphiques(archive: _Archive, dossier: str, pertes: list[str]) -> None:
    if archive.contient_un(dossier):
        _perdre(pertes, "graphiques : leurs données restent dans le fichier et ne sont pas lues")


# ── PDF ──────────────────────────────────────────────────────────────────────


def _pdf(contenu: bytes, pertes: list[str]) -> str:
    from pypdf import PdfReader  # noqa: PLC0415

    lecteur = PdfReader(BytesIO(contenu))
    if lecteur.is_encrypted:
        try:
            ouvert = lecteur.decrypt("")
        except Exception as erreur:  # noqa: BLE001
            msg = "PDF protégé par un mot de passe"
            raise _Illisible(msg) from erreur
        if not ouvert:
            msg = "PDF protégé par un mot de passe"
            raise _Illisible(msg)
    pages = lecteur.pages
    total = len(pages)
    # Aucun repère de page dans le texte : « [page 12] » donnait au modèle un
    # nombre de plus à citer, et au contrôle chiffré une référence de plus où
    # un chiffre inventé pouvait tomber juste.
    morceaux: list[str] = []
    vides = 0
    taille = 0
    debut = time.monotonic()
    for numero, page in enumerate(pages[:MAX_PAGES_PDF], start=1):
        if time.monotonic() - debut > DUREE_MAX_PDF_SECONDES:
            _perdre(pertes, f"pages {numero} à {total} non lues : délai de lecture dépassé")
            break
        texte = page.extract_text() or ""
        if len(re.sub(r"\s", "", texte)) < _MIN_CARACTERES_PAGE:
            vides += 1
        morceaux.append(texte)
        taille += len(texte)
        if _plafond_atteint(taille, pertes):
            break
    else:
        if total > MAX_PAGES_PDF:
            _perdre(pertes, f"pages {MAX_PAGES_PDF + 1} à {total} non lues")
    texte = "\n\n".join(morceaux)
    if len(re.sub(r"\s", "", texte)) < _MIN_CARACTERES_PDF:
        msg = (
            "aucun texte lisible : document scanné ou composé d'images — "
            "déposer une version exportée depuis le logiciel d'origine"
        )
        raise _Illisible(msg)
    # Un scan de quarante pages dont chaque pied de page porte une ligne de
    # texte passait le seuil global : c'est page par page qu'on le voit.
    if vides >= max(2, len(morceaux) // 5):
        _perdre(pertes, f"{vides} page(s) sans texte lisible (scannées ou en image)")
    return texte


# ── Word ─────────────────────────────────────────────────────────────────────

#: Les enveloppes qui portent des paragraphes sans en être : contrôles de
#: contenu des modèles (`sdt`), balisage personnalisé, insertions suivies.
_ENVELOPPES_DOCX = {"sdt", "sdtContent", "customXml", "smartTag", "ins"}


def _docx(contenu: bytes, pertes: list[str]) -> str:
    with _Archive(contenu, pertes) as archive:
        try:
            racine = archive.arbre("word/document.xml")
        except KeyError as erreur:
            msg = "document Word sans corps de texte"
            raise _Illisible(msg) from erreur
        _graphiques(archive, "word/charts/", pertes)
    corps = next((e for e in racine if _local(e.tag) == "body"), None)
    if corps is None:
        return ""
    lignes: list[str] = []
    _blocs_docx(corps, lignes)
    return "\n".join(lignes)


def _blocs_docx(conteneur: ElementTree.Element, lignes: list[str]) -> None:
    for bloc in conteneur:
        nature = _local(bloc.tag)
        if nature == "p":
            lignes.append(_texte_de(bloc))
        elif nature == "tbl":
            # Un tableau se lit ligne à ligne, cellules séparées : c'est la
            # forme sous laquelle un prévisionnel reste un prévisionnel.
            for rangee in (e for e in bloc if _local(e.tag) == "tr"):
                cellules = [
                    _cellule(c) for c in rangee if _local(c.tag) == "tc"
                ]
                if any(cellules):
                    lignes.append(" | ".join(cellules))
            lignes.append("")
        elif nature in _ENVELOPPES_DOCX:
            # Le texte d'un contrôle de contenu disparaissait : « Marché
            # régional : 14,2 M€ (CCI 2025) » dans un modèle de dossier BPI.
            _blocs_docx(bloc, lignes)


# ── Excel ────────────────────────────────────────────────────────────────────

#: Formats de nombre intégrés d'Excel qui affichent une date.
_FORMATS_DATE = {14, 15, 16, 17, 22}
_FORMATS_POURCENT = {9, 10}


def _colonne(reference: str) -> int:
    """`C12` → 2. Les colonnes d'un tableur se lisent en base 26."""
    lettres = re.match(r"[A-Z]+", reference or "")
    if not lettres:
        return -1
    index = 0
    for lettre in lettres.group(0):
        index = index * 26 + (ord(lettre) - 64)
    return index - 1


def _decimal_fr(valeur: float) -> str:
    """`3.125` → `3,125`. Écrit comme le lit un lecteur français."""
    if valeur.is_integer() and abs(valeur) < 1e15:
        return str(int(valeur))
    return f"{valeur:.10g}".replace(".", ",")


def _milliers(valeur: float) -> str:
    """`45000` → `45 000`, `1234.5` → `1 234,5`."""
    entier, _, decimales = _decimal_fr(valeur).partition(",")
    signe = "-" if entier.startswith("-") else ""
    chiffres = entier.lstrip("-")
    groupes: list[str] = []
    while chiffres:
        groupes.insert(0, chiffres[-3:])
        chiffres = chiffres[:-3]
    return signe + " ".join(groupes) + (f",{decimales}" if decimales else "")


def _nature_du_format(code: str) -> str:
    """`euro`, `date`, `pourcent` ou `nombre`, d'après un code de format.

    Le symbole monétaire se cherche dans le code ENTIER : Excel l'écrit entre
    guillemets (`#,##0 "€"`) ou entre crochets (`[$€-40C]`). Sans lui, un
    montant du prévisionnel sortait nu — `45000` — et le contrôle du Word,
    qui n'admet des documents que les montants portant leur unité, le
    signalait ensuite comme inventé (contre-relecture du 11/09/2026).
    """
    if "€" in code or "EUR" in code.upper():
        return "euro"
    visible = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", code)
    if "%" in visible:
        return "pourcent"
    # Une DATE porte un jour ou une année ; `mm:ss` est une durée, pas une date.
    if re.search(r"[dyj]", visible, re.IGNORECASE):
        return "date"
    return "nombre"


@dataclass
class _Styles:
    """La nature de chaque style de cellule : date, pourcentage ou nombre.

    Sans lui, un en-tête de prévisionnel mensuel se lisait « 46023 | 46054 »
    et une marge de 35 % se lisait « 0.35 », à côté de montants en euros.
    """

    natures: list[str]
    base_1904: bool = False

    def formater(self, brut: str, style: str | None) -> str:
        try:
            valeur = float(brut)
        except ValueError:
            return brut
        nature = "nombre"
        if style is not None and style.isdigit() and int(style) < len(self.natures):
            nature = self.natures[int(style)]
        if nature == "euro":
            return f"{_milliers(round(valeur, 2))} €"
        if nature == "pourcent":
            return f"{_decimal_fr(round(valeur * 100, 2))} %"
        if nature == "date":
            origine = date(1904, 1, 1) if self.base_1904 else date(1899, 12, 30)
            try:
                return (origine + timedelta(days=int(valeur))).strftime("%d/%m/%Y")
            except (OverflowError, ValueError):
                return _decimal_fr(valeur)
        return _decimal_fr(valeur)


def _styles(archive: _Archive, classeur: ElementTree.Element) -> _Styles:
    base_1904 = any(
        _local(e.tag) == "workbookPr" and e.get("date1904") in ("1", "true")
        for e in classeur.iter()
    )
    if "xl/styles.xml" not in archive.noms:
        return _Styles([], base_1904)
    racine = archive.arbre("xl/styles.xml")
    personnalises = {
        e.get("numFmtId", ""): e.get("formatCode", "")
        for e in racine.iter() if _local(e.tag) == "numFmt"
    }
    natures: list[str] = []
    for bloc in racine:
        if _local(bloc.tag) != "cellXfs":
            continue
        for xf in bloc:
            identifiant = xf.get("numFmtId", "0")
            if identifiant in personnalises:
                natures.append(_nature_du_format(personnalises[identifiant]))
            elif identifiant.isdigit() and int(identifiant) in _FORMATS_DATE:
                natures.append("date")
            elif identifiant.isdigit() and int(identifiant) in _FORMATS_POURCENT:
                natures.append("pourcent")
            else:
                natures.append("nombre")
    return _Styles(natures, base_1904)


def _xlsx(contenu: bytes, pertes: list[str]) -> str:
    with _Archive(contenu, pertes) as archive:
        try:
            classeur = archive.arbre("xl/workbook.xml")
            liens = archive.arbre("xl/_rels/workbook.xml.rels")
        except KeyError as erreur:
            msg = "classeur Excel incomplet"
            raise _Illisible(msg) from erreur
        styles = _styles(archive, classeur)
        partagees = _chaines_partagees(archive)
        _graphiques(archive, "xl/charts/", pertes)
        cibles = {
            r.get("Id"): r.get("Target", "")
            for r in liens if _local(r.tag) == "Relationship"
        }
        sorties: list[str] = []
        taille = 0
        for feuille in (e for e in classeur.iter() if _local(e.tag) == "sheet"):
            nom = feuille.get("name", "")
            identifiant = next(
                (v for k, v in feuille.attrib.items() if _local(k) == "id"), None
            )
            chemin = archive.cible("xl", cibles.get(identifiant, ""))
            if chemin not in archive.noms:
                _perdre(pertes, f"feuille « {nom} » introuvable dans le classeur")
                continue
            lignes = _lignes_de_feuille(
                archive, chemin, partagees, styles, pertes,
                reste=PLAFOND_EXTRACTION - taille,
            )
            if lignes:
                bloc = f"### Feuille « {nom} »\n" + "\n".join(lignes)
                sorties.append(bloc)
                taille += len(bloc)
            if _plafond_atteint(taille, pertes):
                break
    return "\n\n".join(sorties)


def _chaines_partagees(archive: _Archive) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.noms:
        return []
    chaines: list[str] = []
    for _, element in archive.evenements("xl/sharedStrings.xml"):
        if _local(element.tag) == "si":
            chaines.append(_texte_de(element))
            element.clear()
    return chaines


def _lignes_de_feuille(
    archive: _Archive,
    chemin: str,
    partagees: list[str],
    styles: _Styles,
    pertes: list[str],
    *,
    reste: int,
) -> list[str]:
    """Les lignes d'une feuille, lues au fil de l'eau.

    `iterparse` + `clear()` : l'arbre complet d'une feuille de 42 Mo pesait
    807 Mo en mémoire (relecture du 11/09/2026), pour n'en garder que quarante
    mille caractères. On lit rangée par rangée et on s'arrête au plafond.
    """
    flux = archive.evenements(chemin)
    try:
        lignes, sans_valeur = _parcourir_la_feuille(flux, partagees, styles, pertes, reste)
    finally:
        flux.close()
    if sans_valeur:
        _perdre(
            pertes,
            f"{sans_valeur} cellule(s) calculée(s) sans valeur enregistrée — "
            "ouvrir et réenregistrer le fichier dans Excel",
        )
    return lignes


def _parcourir_la_feuille(
    flux: Generator[tuple[str, ElementTree.Element], None, None],
    partagees: list[str],
    styles: _Styles,
    pertes: list[str],
    reste: int,
) -> tuple[list[str], int]:
    lignes: list[str] = []
    taille = 0
    sans_valeur = 0
    for _, rangee in flux:
        if _local(rangee.tag) != "row":
            continue
        valeurs: dict[int, str] = {}
        for rang, cellule in enumerate(c for c in rangee if _local(c.tag) == "c"):
            colonne = _colonne(cellule.get("r", ""))
            if colonne < 0:
                colonne = rang
            valeur, calculee_vide = _valeur_de_cellule(cellule, partagees, styles)
            sans_valeur += calculee_vide
            if not valeur:
                continue
            if colonne >= _MAX_COLONNES:
                _perdre(pertes, f"colonnes au-delà de la {_MAX_COLONNES}e non lues")
                continue
            valeurs[colonne] = valeur
        rangee.clear()
        if valeurs:
            largeur = max(valeurs) + 1
            ligne = " | ".join(valeurs.get(i, "") for i in range(largeur))
            lignes.append(ligne)
            taille += len(ligne) + 1
            if _plafond_atteint(taille, pertes) or taille > reste:
                _perdre(pertes, "feuille lue en partie : volume maximal atteint")
                break
    return lignes, sans_valeur


def _valeur_de_cellule(
    cellule: ElementTree.Element, partagees: list[str], styles: _Styles
) -> tuple[str, int]:
    """(valeur affichable, 1 si formule sans valeur calculée enregistrée)."""
    nature = cellule.get("t", "n")
    if nature == "inlineStr":
        return _texte_de(cellule).strip(), 0
    brut = next((e.text or "" for e in cellule if _local(e.tag) == "v"), "")
    formule = any(_local(e.tag) == "f" for e in cellule)
    if not brut:
        return "", int(formule)
    if nature == "s":
        try:
            return partagees[int(brut)].strip(), 0
        except (ValueError, IndexError):
            return "", 0
    if nature == "b":
        return ("VRAI" if brut == "1" else "FAUX"), 0
    if nature in ("str", "e"):
        return brut.strip(), 0
    return styles.formater(brut, cellule.get("s")), 0


# ── PowerPoint ───────────────────────────────────────────────────────────────


def _ordre_des_diapositives(archive: _Archive) -> list[str]:
    """L'ordre de la PRÉSENTATION, pas celui des noms de fichiers.

    Une diapositive déplacée garde son nom (`slide7.xml` peut passer en tête) :
    seul `presentation.xml` dit l'ordre dans lequel on la lit.
    """
    par_nom = sorted(
        (n for n in archive.noms if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
        key=lambda n: int(re.sub(r"\D", "", n)),
    )
    try:
        presentation = archive.arbre("ppt/presentation.xml")
        liens = archive.arbre("ppt/_rels/presentation.xml.rels")
    except KeyError:
        return par_nom
    cibles = {
        r.get("Id"): archive.cible("ppt", r.get("Target", ""))
        for r in liens if _local(r.tag) == "Relationship"
    }
    ordre = [
        cibles.get(next((v for k, v in e.attrib.items() if _local(k) == "id"), ""), "")
        for e in presentation.iter() if _local(e.tag) == "sldId"
    ]
    ordre = [n for n in ordre if n in archive.noms]
    return ordre or par_nom


def _texte_diapositive(racine: ElementTree.Element) -> list[str]:
    lignes: list[str] = []

    def visiter(element: ElementTree.Element) -> None:
        nature = _local(element.tag)
        if nature == "Fallback":
            return
        if nature == "tbl":
            for rangee in (e for e in element.iter() if _local(e.tag) == "tr"):
                cellules = [
                    _cellule(c) for c in rangee if _local(c.tag) == "tc"
                ]
                if any(cellules):
                    lignes.append(" | ".join(cellules))
            return
        if nature == "p":
            texte = _texte_de(element).strip()
            if texte:
                lignes.append(texte)
            return
        for enfant in element:
            visiter(enfant)

    visiter(racine)
    return lignes


def _pptx(contenu: bytes, pertes: list[str]) -> str:
    with _Archive(contenu, pertes) as archive:
        _graphiques(archive, "ppt/charts/", pertes)
        sorties = []
        taille = 0
        for numero, nom in enumerate(_ordre_des_diapositives(archive), start=1):
            lignes = _texte_diapositive(archive.arbre(nom))
            if lignes:
                bloc = f"Diapositive {numero}\n" + "\n".join(lignes)
                sorties.append(bloc)
                taille += len(bloc)
                if _plafond_atteint(taille, pertes):
                    break
    return "\n\n".join(sorties)


_LECTEURS: dict[str, Callable[[bytes, list[str]], str]] = {
    ".pdf": _pdf, ".docx": _docx, ".xlsx": _xlsx, ".pptx": _pptx,
}


# ── Répartition du volume ────────────────────────────────────────────────────


def repartir(longueurs: list[int], limite: int) -> list[int]:
    """Part de chaque document dans `limite` caractères, équitablement.

    Les courts sont servis en entier ; ce qu'ils laissent revient aux longs.
    Un premier document de 200 pages ne doit pas priver de toute lecture le
    prévisionnel déposé après lui.
    """
    parts = [0] * len(longueurs)
    reste = limite
    ordre = sorted(range(len(longueurs)), key=lambda i: longueurs[i])
    for rang, i in enumerate(ordre):
        part = reste // (len(ordre) - rang)
        parts[i] = min(longueurs[i], part)
        reste -= parts[i]
    return parts


def _couper(texte: str, longueur: int) -> str:
    """Coupe à `longueur`, sur une fin de ligne si elle n'est pas trop loin."""
    if len(texte) <= longueur:
        return texte
    coupe = texte[:longueur]
    fin_de_ligne = coupe.rfind("\n")
    if fin_de_ligne > longueur * 0.8:
        coupe = coupe[:fin_de_ligne]
    return coupe.rstrip()


# ── Le dossier ───────────────────────────────────────────────────────────────


def lire_les_documents(job: GenerationJob) -> list[DocumentClientLu]:
    """Lit la bibliothèque de l'organisation et en garde la trace sur le dossier.

    Un dossier se lit UNE fois, avant son socle. Une relance travaille sur la
    matière du premier passage — jamais sur un document ajouté entre-temps, que
    le socle, déjà verrouillé, n'aurait pas vu. D'où la seconde condition :
    un dossier dont le socle existe ou dont un chapitre est écrit n'est plus
    lu, même s'il n'avait trouvé aucun document la première fois (relecture du
    11/09/2026 : sans elle, une relance lisait en cours de route une
    bibliothèque qui avait changé, et les chapitres restants recevaient une
    matière que le socle ignorait).
    """
    from organisations.models import CategorieFichier  # noqa: PLC0415

    from .models import (  # noqa: PLC0415
        ChapterStatus,
        DocumentClientLu,
        SocleDonnees,
        SocleStatut,
    )

    if job.documents_client.exists():
        return list(job.documents_client.all())
    # Un socle VERROUILLÉ, pas un socle quelconque : un socle en échec est
    # reconstruit de zéro à la relance, et doit alors voir les documents.
    if (
        SocleDonnees.objects.filter(job=job, statut=SocleStatut.VALIDE).exists()
        or job.chapters.filter(status=ChapterStatus.DONE).exists()
    ):
        return []

    organisation = organisation_des_documents(job)
    if organisation is None:
        return []
    pieces = list(
        organisation.pieces_jointes.filter(categorie=CategorieFichier.DOCUMENT)
        .order_by("created_at")
    )
    if not pieces:
        return []

    from .models import StatutLecture  # noqa: PLC0415

    lectures: list[tuple[Any, Extraction]] = []
    for rang, piece in enumerate(pieces):
        if rang >= MAX_DOCUMENTS:
            lectures.append((piece, Extraction(
                StatutLecture.NON_LU,
                motif=f"au-delà des {MAX_DOCUMENTS} documents lus par dossier",
            )))
            continue
        lectures.append((piece, _lire_la_piece(piece)))

    parts = repartir(
        [len(e.texte) for _, e in lectures], LIMITE_TOTALE
    )
    lignes = []
    for ordre, ((piece, extraction), part) in enumerate(zip(lectures, parts, strict=True)):
        texte = _couper(extraction.texte, part)
        statut = extraction.statut
        motifs = [extraction.motif] if extraction.motif else []
        if len(texte) < len(extraction.texte):
            statut = StatutLecture.TRONQUE
            motifs.append(
                f"transmis sur {len(texte)} caractères de {len(extraction.texte)} : "
                f"le volume est limité à {LIMITE_TOTALE} caractères pour "
                "l'ensemble des documents"
            )
        lignes.append(DocumentClientLu(
            job=job, piece=piece, ordre=ordre, nom=piece.nom_original[:200],
            depose_le=piece.created_at, statut=statut,
            caracteres_extraits=len(extraction.texte),
            caracteres_retenus=len(texte), motif=" ; ".join(motifs)[:300], texte=texte,
        ))
    DocumentClientLu.objects.bulk_create(lignes)
    _signaler_ce_qui_manque(job, lignes)
    return lignes


def organisation_des_documents(job: GenerationJob) -> Any:
    """La bibliothèque que ce dossier doit lire.

    Pour une reprise, celle du dossier d'ORIGINE : la commande de reprise n'a
    pas d'organisation, et la résoudre par le contact lirait la bibliothèque
    d'une autre organisation si le client en est contact ailleurs.
    """
    from organisations.liaison import (  # noqa: PLC0415
        est_une_reprise_a_nos_frais,
        organisation_du_job,
    )

    from .models import GenerationJob as Job  # noqa: PLC0415

    # Une reprise de reprise remonte jusqu'au dossier d'origine. Bornée : une
    # chaîne de filiation ne boucle pas, mais un compteur ne coûte rien.
    for _ in range(20):
        if not est_une_reprise_a_nos_frais(job):
            break
        job = Job.objects.select_related("order").get(
            id=job.order.raw_payload["reprise_de"]
        )
    return organisation_du_job(job)


def _lire_la_piece(piece: Any) -> Extraction:
    from .models import StatutLecture  # noqa: PLC0415

    nom_stocke = piece.fichier.name if piece.fichier else ""
    try:
        with piece.fichier.open("rb") as flux:
            contenu = flux.read()
    except (OSError, ValueError):
        return Extraction(StatutLecture.ILLISIBLE, motif="fichier absent du volume")
    return extraire(nom_stocke or piece.nom_original, contenu)


def _signaler_ce_qui_manque(job: GenerationJob, lignes: list[DocumentClientLu]) -> None:
    """Un incident nomme chaque document écarté ou coupé. Rien ne part en silence."""
    from monitoring.models import IncidentSeverity, OperationalIncident  # noqa: PLC0415

    from .models import StatutLecture  # noqa: PLC0415

    manquants = [ligne for ligne in lignes if ligne.statut != StatutLecture.LU]
    if not manquants:
        return
    ecartes = [m for m in manquants if m.statut != StatutLecture.TRONQUE]
    OperationalIncident.objects.create(
        title=(
            f"Documents du client : {len(ecartes)} non lu(s), "
            f"{len(manquants) - len(ecartes)} lu(s) en partie (job {job.id})"
        ),
        severity=IncidentSeverity.MEDIUM if ecartes else IncidentSeverity.LOW,
        job=job,
        order=job.order,
        details={
            "type": "documents_client",
            "documents": [
                {"nom": m.nom, "statut": m.statut, "motif": m.motif} for m in manquants
            ],
        },
    )


def documents_lisibles(job: GenerationJob) -> list[DocumentClientLu]:
    return [d for d in job.documents_client.all() if d.texte]


def bloc_documents(job: GenerationJob) -> str:
    """Le texte des documents, tel que le modèle le lit. Vide s'il n'y en a pas.

    Rien sur la LECTURE elle-même n'y figure — ni les documents non lus, ni
    une coupure, ni une page manquante. Le dire au modèle, c'est l'inviter à
    l'écrire au client, et le document parlerait de sa propre fabrication.
    Tout cela vit dans l'incident et sur l'écran du dossier.
    """
    documents = documents_lisibles(job)
    if not documents:
        return ""
    parties = [
        f"DOCUMENTS_DU_CLIENT — {len(documents)} document(s) déposé(s) par le "
        "porteur de projet pour ce dossier. Ils font partie du dossier client au "
        "même titre que le brief."
    ]
    for rang, document in enumerate(documents, start=1):
        depot = f", déposé le {document.depose_le:%d/%m/%Y}" if document.depose_le else ""
        parties.append(
            f"=== DOCUMENT {rang} — « {document.nom} »{depot} ===\n{document.texte}"
        )
    return "\n\n".join(parties)


def effacer_les_textes_orphelins() -> int:
    """Efface le texte des documents dont la pièce jointe a disparu.

    La suppression d'une pièce jointe n'efface PAS le texte d'un dossier encore
    en cours : ses chapitres restants perdraient en route la matière que les
    premiers ont lue, et le cache du prompt avec (relecture du 11/09/2026). Le
    texte part donc ici, dès que le dossier ne travaille plus — appelé en fin
    de génération et par la purge des pièces jointes.
    """
    from django.utils import timezone  # noqa: PLC0415

    return int(
        textes_effacables()
        .filter(piece__isnull=True)
        .update(texte="", texte_efface_le=timezone.now())
    )


def textes_effacables() -> Any:
    """Les textes lus par un dossier qui ne travaille PLUS.

    Un dossier travaille tant qu'il est en attente ou en cours, ET tant
    qu'un de ses chapitres s'écrit : la boucle de correction et le
    recontrôle réécrivent des chapitres sur un dossier déjà terminé
    (contre-relecture du 11/09/2026). Une seule définition, lue par
    l'effacement immédiat comme par l'effacement différé (règle 5).
    """
    from .models import ChapterStatus, DocumentClientLu, JobStatus  # noqa: PLC0415

    return (
        DocumentClientLu.objects.exclude(texte="")
        .exclude(job__status__in=[JobStatus.RUNNING, JobStatus.PENDING])
        .exclude(job__chapters__status=ChapterStatus.RUNNING)
    )


def texte_des_documents(job: GenerationJob) -> str:
    """Le texte brut de tous les documents lus — pour les contrôles chiffrés."""
    return "\n".join(d.texte for d in documents_lisibles(job))

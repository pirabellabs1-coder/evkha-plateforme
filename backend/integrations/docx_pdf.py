"""Conversion Word vers PDF (lot 3).

La cliente veut les deux formats : « si ça peut rendre les PDF vous pouvez
mettre les deux, ça serait top, parce que les gens peuvent modifier ». Le Word
est la source, le PDF en est la **photographie** — jamais un second rendu
depuis le HTML, sans quoi les deux fichiers divergeraient sur la mise en page
et le nombre de pages.

Le seul convertisseur fidèle disponible sur un VPS est LibreOffice en mode sans
interface. Il est lourd (paquet système, pas dépendance Python) et absent de la
machine de développement : d'où le bouchon, actif par défaut, exactement comme
pour le PDF HTML existant.

**Le bouchon ne produit pas un PDF valide et ne prétend pas le contraire.** Il
produit un fichier reconnaissable, sans pagination. Toute mesure de pages
obtenue en environnement bouchonné vaut zéro, et zéro signifie « inconnu » —
jamais « conforme ».
"""
from __future__ import annotations

import hashlib
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from django.conf import settings

_log = logging.getLogger(__name__)

#: Une étude de soixante pages avec quinze figures met quelques dizaines de
#: secondes à convertir. Au-delà, quelque chose est bloqué.
DELAI_CONVERSION_S = 180

#: Noms d'exécutable, par ordre de préférence.
EXECUTABLES = ("soffice", "libreoffice")


class ConversionPdfError(RuntimeError):
    """La conversion a échoué. Le Word reste livrable, le PDF non."""


@dataclass(frozen=True)
class ConversionPdf:
    chemin: Path
    octets: int
    pages: int = 0
    """Nombre de pages, 0 si inconnu. Un bouchon renvoie toujours 0."""


@runtime_checkable
class ConvertisseurDocx(Protocol):
    def convertir(self, source: Path, destination: Path) -> ConversionPdf: ...


def executable_libreoffice() -> str | None:
    """Chemin de LibreOffice, ou None s'il n'est pas installé."""
    for nom in EXECUTABLES:
        chemin = shutil.which(nom)
        if chemin:
            return chemin
    return None


def _compter_pages(pdf: bytes) -> int:
    """Nombre de pages lu dans le PDF, 0 si illisible.

    Compte les objets `/Type /Page` en excluant `/Pages`, le nœud d'arbre. Une
    lecture approximative serait pire qu'aucune : elle alimenterait le contrôle
    de limite de pages avec un chiffre faux (règle 2). En cas de doute, on
    renvoie 0, qui vaut « inconnu ».
    """
    import re  # noqa: PLC0415

    trouves = re.findall(rb"/Type\s*/Page(?![sA-Za-z])", pdf)
    return len(trouves)


class BouchonConvertisseurDocx:
    """Convertisseur déterministe pour le développement et l'intégration continue.

    Écrit un fichier PDF minimal mais syntaxiquement reconnaissable, dérivé du
    contenu du Word pour rester reproductible. Il ne rend rien : il permet
    seulement à la chaîne d'artefacts d'être exercée de bout en bout.
    """

    def convertir(self, source: Path, destination: Path) -> ConversionPdf:
        if not source.is_file():
            msg = f"Word introuvable : {source}"
            raise ConversionPdfError(msg)
        empreinte = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(
            f"%PDF-1.4\n%%bouchon-evkha-{empreinte}\n%%EOF\n".encode()
        )
        return ConversionPdf(
            chemin=destination, octets=destination.stat().st_size, pages=0
        )


class LibreOfficeConvertisseurDocx:
    """Conversion réelle par LibreOffice en mode sans interface.

    LibreOffice impose le nom du fichier produit (même radical que la source,
    extension `.pdf`) et le répertoire de sortie. On le fait donc travailler
    dans un répertoire temporaire, puis on déplace le résultat : sans cela, une
    conversion écraserait la précédente dès que deux jobs partagent un radical.

    `-env:UserInstallation` isole le profil : sans cet argument, deux
    conversions simultanées se disputent le même profil utilisateur et la
    seconde échoue sans message exploitable.
    """

    def __init__(self, executable: str, delai_s: int = DELAI_CONVERSION_S) -> None:
        self._executable = executable
        self._delai_s = delai_s

    def convertir(self, source: Path, destination: Path) -> ConversionPdf:
        if not source.is_file():
            msg = f"Word introuvable : {source}"
            raise ConversionPdfError(msg)

        with tempfile.TemporaryDirectory(prefix="evkha-pdf-") as travail:
            dossier = Path(travail)
            commande = [
                self._executable,
                f"-env:UserInstallation=file:///{dossier.as_posix()}/profil",
                "--headless", "--norestore",
                "--convert-to", "pdf:writer_pdf_Export",
                "--outdir", str(dossier),
                str(source),
            ]
            try:
                resultat = subprocess.run(  # noqa: S603 — arguments construits ici, aucune entrée utilisateur
                    commande, capture_output=True, timeout=self._delai_s, check=False
                )
            except subprocess.TimeoutExpired as erreur:
                msg = f"LibreOffice n'a pas rendu la main en {self._delai_s} s."
                raise ConversionPdfError(msg) from erreur

            produit = dossier / (source.stem + ".pdf")
            if resultat.returncode != 0 or not produit.is_file():
                detail = resultat.stderr.decode("utf-8", "replace").strip()[:400]
                msg = (
                    f"LibreOffice a échoué (code {resultat.returncode}) sur "
                    f"{source.name}. {detail}"
                )
                raise ConversionPdfError(msg)

            octets = produit.read_bytes()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(octets)

        return ConversionPdf(
            chemin=destination, octets=len(octets), pages=_compter_pages(octets)
        )


def get_convertisseur_docx() -> ConvertisseurDocx:
    """Bouchon par défaut ; LibreOffice quand `EVKHA_USE_STUB_PDF=false`.

    Le drapeau est celui du PDF existant, et c'est délibéré : ces deux chaînes
    dépendent du même choix d'environnement, et deux drapeaux séparés
    finiraient par se contredire.

    Si LibreOffice est réclamé mais absent, on échoue ici plutôt que de
    retomber sur le bouchon : livrer un faux PDF en production serait un défaut
    invisible jusqu'à ce qu'un client ouvre le fichier.
    """
    if bool(getattr(settings, "EVKHA_USE_STUB_PDF", True)):
        return BouchonConvertisseurDocx()

    executable = executable_libreoffice()
    if executable is None:
        msg = (
            "LibreOffice est requis pour convertir le Word en PDF "
            f"(exécutables cherchés : {', '.join(EXECUTABLES)}) et reste "
            "introuvable. Installer `libreoffice-writer` sur le VPS, ou "
            "remettre EVKHA_USE_STUB_PDF=true."
        )
        raise ConversionPdfError(msg)
    return LibreOfficeConvertisseurDocx(executable)

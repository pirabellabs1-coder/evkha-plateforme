"""Controle de FIDELITE du PDF Gamma : Gamma a-t-il garde le document ?

Pourquoi ce module existe
-------------------------
Le gate de livraison valide le contenu genere par Claude. Puis Gamma refait le
document — et personne ne controlait sa sortie. Or Gamma REECRIT : mesure sur le
premier vrai BP SYNAPSES (juillet 2026), avec le parametrage d'alors :

    source pipeline : 38 752 mots, 20 chapitres
    PDF Gamma       :  3 835 mots, 10 cartes (chapitres fusionnes)

90 % du document perdu, et 5 verticales sur 10 EFFACEES — dont le
self-stockage, l'hebergement de serveurs et les activites sportives douces,
c'est-a-dire exactement les trois que la cliente signalait comme disparues.
Le gate les avait pourtant validees : elles etaient bien dans le markdown.
Gamma les a supprimees APRES.

Autrement dit, active tel quel, Gamma aggravait le probleme qu'on corrigeait,
et le faisait en silence.

Le parametrage est corrige (`cardSplit=inputTextBreaks`), mais un reglage n'est
pas une garantie : Gamma reste un service externe qui peut changer de
comportement sans nous prevenir. On VERIFIE donc sa sortie au lieu de lui faire
confiance.

Regle : si le PDF Gamma perd des verticales ou une part importante du texte, on
ne le livre pas. Le repli WeasyPrint, lui, ne perd rien — il rend exactement le
markdown valide par le gate. Mieux vaut une mise en page moins belle qu'un
document ampute.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass

_log = logging.getLogger(__name__)

# En dessous de cette part du texte source, le PDF n'est plus une mise en page
# du document : c'est un resume. Seuil large — Gamma reformate, enleve le
# markdown, fusionne des titres : une perte de quelques pourcents est normale.
# A 60 %, il ne s'agit plus de mise en forme.
_SEUIL_FIDELITE_TEXTE = 0.60


@dataclass(frozen=True)
class RapportFidelite:
    fidele: bool
    mots_source: int
    mots_pdf: int
    verticales_perdues: tuple[str, ...]
    motif: str

    @property
    def ratio(self) -> float:
        return (self.mots_pdf / self.mots_source) if self.mots_source else 0.0


def _norm(texte: str) -> str:
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", texte.lower())
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[\s  ]+", " ", sans_accents)


def extraire_texte_pdf(contenu: bytes) -> str:
    """Texte d'un PDF en memoire. Chaine vide si illisible.

    Import paresseux : pypdf est une dependance optionnelle. Son absence ne
    doit jamais casser une livraison — elle desactive juste le controle, et on
    le DIT (cf. `controler_fidelite`).
    """
    try:
        import io

        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        lecteur = PdfReader(io.BytesIO(contenu))
        return "\n".join((page.extract_text() or "") for page in lecteur.pages)
    except Exception:  # noqa: BLE001 — un PDF illisible n'est pas une exception metier
        return ""


def controler_fidelite(
    *,
    texte_pdf: str,
    markdown_source: str,
    verticales: tuple[str, ...],
) -> RapportFidelite:
    """Le PDF Gamma restitue-t-il le document valide par le gate ?"""
    mots_source = len(markdown_source.split())
    mots_pdf = len(texte_pdf.split())

    if not texte_pdf.strip():
        # PDF illisible OU pypdf absent : on ne sait pas, donc on ne se
        # prononce pas. Ne pas savoir n'autorise pas a bloquer une livraison
        # par ailleurs valide — mais le silence non plus : on trace.
        return RapportFidelite(
            fidele=True,
            mots_source=mots_source,
            mots_pdf=0,
            verticales_perdues=(),
            motif="PDF Gamma illisible (pypdf absent ?) : controle non effectue.",
        )

    pdf_norm = _norm(texte_pdf)

    # Une verticale est traitee si tous ses mots porteurs sont presents — meme
    # regle que le gate, pour ne pas avoir deux verites (le gate exigeait
    # autrefois le libelle litteral et bloquait des livrables corrects).
    perdues: list[str] = []
    for verticale in verticales:
        tete = re.split(r"[(\[]", verticale, maxsplit=1)[0]
        mots = [
            m for m in re.split(r"[^\w-]+", _norm(tete))
            if m and m not in {"de", "du", "des", "d", "la", "le", "les", "et", "en", "a"}
        ]
        if mots and not all(m in pdf_norm for m in mots):
            perdues.append(verticale.strip())

    ratio = (mots_pdf / mots_source) if mots_source else 1.0
    motifs: list[str] = []
    if perdues:
        motifs.append(
            f"Gamma a supprime {len(perdues)} verticale(s) du brief : "
            f"{', '.join(perdues)}."
        )
    if ratio < _SEUIL_FIDELITE_TEXTE:
        motifs.append(
            f"Gamma n'a conserve que {ratio:.0%} du texte "
            f"({mots_pdf} mots sur {mots_source}) : c'est un resume, pas une "
            "mise en page."
        )

    return RapportFidelite(
        fidele=not motifs,
        mots_source=mots_source,
        mots_pdf=mots_pdf,
        verticales_perdues=tuple(perdues),
        motif=" ".join(motifs) or "PDF Gamma fidele au document valide.",
    )

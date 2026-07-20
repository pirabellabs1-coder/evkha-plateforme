"""Controle de FIDELITE du rendu : le HTML livre dit-il ce que le gate a valide ?

Pourquoi ce module existe
-------------------------
Le gate valide le MARKDOWN. Le moteur de rendu fabrique ensuite le HTML — et
personne ne regardait son resultat. Or il peut detruire le document.

Cas reel (BP SYNAPSES, juillet 2026). Le markdown du chapitre 18 contenait le
tableau complet du compte de resultat. Le HTML livre contenait :

    <table><thead><tr><th>Rubrique</th><th>Montant</th></tr></thead>
    <tbody><></><></><></><></><></><></></tbody></table>

Toutes les lignes de donnees remplacees par des balises vides. Cause :
`chunk_long_tables` appelait `tbody.decompose()`, qui detruit l'element ET SES
ENFANTS, alors que la liste des lignes a recopier pointait justement dessus.
Le defaut ne frappait que les tableaux de plus de 12 lignes — donc les
tableaux financiers, les plus regardes dans un dossier bancaire. C'est la
cause des « tableaux tronques » signales de longue date par la cliente.

Le bug est corrige. Ce module existe parce qu'un correctif n'est pas une
garantie : c'est la MEME histoire que Gamma, qui refaisait le document apres
le gate et effacait cinq verticales. La regle vaut pour tout moteur de rendu :

    ce qui refait le document apres le controle doit etre controle a son tour.

On verifie donc ce que le lecteur va REELLEMENT lire, pas ce qu'on lui a
envoye. Un test unitaire vert ne prouve rien sur le document livre.
"""
from __future__ import annotations

import html as _html
import re
from collections import Counter
from dataclasses import dataclass

from generation.internal_labels import CALLOUT_MARKERS

# Balise au nom vide : `<></>`. Signature d'un noeud BeautifulSoup detruit puis
# reinsere. Ne peut JAMAIS etre legitime dans un livrable.
_BALISE_VIDE_RE = re.compile(r"<>\s*</>|<>")

# Lignes de donnees d'un tableau HTML (hors entete).
_LIGNE_TD_RE = re.compile(r"<td[\s>]", re.IGNORECASE)
# Lignes de donnees d'un tableau markdown : `| valeur | valeur |`, en excluant
# l'entete et le separateur `|---|---|`.
_LIGNE_MD_RE = re.compile(r"^\s*\|(?!\s*[-:| ]+\|\s*$).+\|\s*$", re.MULTILINE)
_SEPARATEUR_MD_RE = re.compile(r"^\s*\|[\s\-:|]+\|\s*$", re.MULTILINE)

# En dessous, le rendu a perdu des lignes de tableau. Seuil bas : le rendu
# fusionne parfois des cellules ou deplace un tableau, mais il ne doit pas
# ESCAMOTER des donnees.
_SEUIL_LIGNES = 0.90

# ── Prose ───────────────────────────────────────────────────────────────────
# Un mot : au moins deux lettres. Exclut les nombres (deja couverts par le
# gate) et la ponctuation.
_MOT_RE = re.compile(r"[^\W\d_]{2,}")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_BALISE_RE = re.compile(r"<[^>]+>")

# Marqueurs d'encadre : le convertisseur les transforme en cartouches stylises,
# donc ils disparaissent LEGITIMEMENT du HTML. Importes, jamais recopies.
_MOTS_ATTENDUS_ABSENTS = frozenset(m.lower() for m in CALLOUT_MARKERS)


def _prose(texte: str) -> list[str]:
    """Mots reellement lus par le client, balisage exclu.

    Le markdown valide par le gate contient lui-meme des fragments HTML : les
    tableaux sont produits avec un style en ligne. Sans ce depouillement des
    DEUX cotes, `px`, `td`, `padding` et `cccccc` sont comptes comme de la
    prose — mesure constatee sur le dossier SYNAPSES : 3 444 faux « mots
    perdus », soit un ecart de 10 % entierement imaginaire.
    """
    nu = _BALISE_RE.sub(" ", _SCRIPT_STYLE_RE.sub(" ", texte))
    return _MOT_RE.findall(_html.unescape(nu))


@dataclass(frozen=True)
class RapportRendu:
    fidele: bool
    motifs: tuple[str, ...]
    lignes_markdown: int
    lignes_html: int
    balises_vides: int
    mots_perdus: int = 0
    exemples_mots_perdus: tuple[str, ...] = ()

    @property
    def motif(self) -> str:
        return " ".join(self.motifs) or "Rendu fidele au document valide."


def _tableaux_html_sans_donnees(html: str) -> int:
    """Tableaux qui ont une entete mais aucune cellule de donnees."""
    vides = 0
    for tableau in re.findall(r"<table[^>]*>.*?</table>", html, re.IGNORECASE | re.DOTALL):
        if "<th" in tableau.lower() and not _LIGNE_TD_RE.search(tableau):
            vides += 1
    return vides


def _prose_perdue(html: str, markdown: str) -> tuple[int, tuple[str, ...]]:
    """Mots du document valide que le lecteur ne verra pas.

    Comparaison en multi-ensemble : un mot present cinq fois dans le markdown
    et trois fois dans le HTML compte pour deux pertes. Un paragraphe escamote
    est donc detecte par ses mots propres, meme s'il est court — la ou un
    simple ratio de volume (60 mots sur 25 000) resterait invisible.

    Tolerance zero, une seule exception : les marqueurs d'encadre, que le
    convertisseur transforme en cartouches.
    """
    manquants = Counter(w.lower() for w in _prose(markdown))
    manquants -= Counter(w.lower() for w in _prose(html))
    for marqueur in _MOTS_ATTENDUS_ABSENTS:
        del manquants[marqueur]
    return sum(manquants.values()), tuple(w for w, _ in manquants.most_common(8))


def controler_rendu(*, html: str, markdown: str) -> RapportRendu:
    """Le HTML restitue-t-il le document que le gate a valide ?

    Quatre defauts, tous constates ou possibles sur le rendu reel :
    - des balises vides `<></>` (noeud detruit puis reinsere) ;
    - un tableau avec une entete et aucune donnee ;
    - des lignes de tableau disparues entre le markdown et le HTML ;
    - de la PROSE disparue entre le markdown et le HTML.

    Le quatrieme est venu d'une lecture de ce module a la grille du « Loop
    Doctor » de `Forward-Future/loopy` : un controle et sa reparation ne
    doivent pas juger sur la meme evidence. Les trois premiers ne parlent que
    de tableaux, et la reparation aussi — donc toute omission de texte passait,
    verifiee : un paragraphe entier supprime du HTML etait declare « fidele ».
    """
    motifs: list[str] = []

    balises_vides = len(_BALISE_VIDE_RE.findall(html))
    if balises_vides:
        motifs.append(
            f"{balises_vides} balise(s) vide(s) `<></>` dans le HTML livre : "
            "des elements ont ete detruits puis reinseres par le moteur de "
            "rendu. C'est la signature des tableaux tronques."
        )

    tables_vides = _tableaux_html_sans_donnees(html)
    if tables_vides:
        motifs.append(
            f"{tables_vides} tableau(x) avec une entete et AUCUNE donnee. "
            "Le lecteur verra des colonnes vides."
        )

    # Lignes de tableau : markdown vs HTML.
    lignes_md = len(_LIGNE_MD_RE.findall(markdown)) - len(
        _SEPARATEUR_MD_RE.findall(markdown)
    )
    lignes_md = max(lignes_md, 0)
    lignes_html = len(re.findall(r"<tr[\s>]", html, re.IGNORECASE))
    if lignes_md and lignes_html < lignes_md * _SEUIL_LIGNES:
        motifs.append(
            f"Le rendu ne contient que {lignes_html} lignes de tableau pour "
            f"{lignes_md} dans le document valide : des donnees ont disparu "
            "a la mise en page."
        )

    mots_perdus, exemples = _prose_perdue(html, markdown)
    if mots_perdus:
        motifs.append(
            f"{mots_perdus} mot(s) du document valide sont absents du HTML "
            f"livre (ex. : {', '.join(exemples)}). Du texte a ete escamote a "
            "la mise en page."
        )

    return RapportRendu(
        fidele=not motifs,
        motifs=tuple(motifs),
        lignes_markdown=lignes_md,
        lignes_html=lignes_html,
        balises_vides=balises_vides,
        mots_perdus=mots_perdus,
        exemples_mots_perdus=exemples,
    )

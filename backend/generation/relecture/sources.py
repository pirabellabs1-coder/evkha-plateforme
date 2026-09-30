"""Sources (classe 9).

## Les défauts, mesurés

Business plan ÉCLORE `28a257bf` (30/09/2026), relu par la cliente :

- la MÊME donnée d'un institut de sondage écrite en toutes lettres (« deux
  … sur trois ») dans une section, en pourcentage exact dans trois autres :
  deux formulations, deux valeurs. La cliente : le pourcentage publié, jamais
  la proportion qui l'arrondit ;
- l'article L221-18 du code de la consommation (rétractation de 14 jours)
  cité pour des ateliers et des week-ends à date fixe : ce droit est EXCLU
  par l'article L221-28 12° ;
- quatre sources citées dans le texte absentes du chapitre des sources, et
  neuf sources listées que le texte ne cite nulle part ;
- la taille du marché national portée par un article de BLOG (l'adresse
  listée est une page `/blog/`) : l'annexe la dit « Estimée », le texte
  l'écrit comme un fait établi.

## Ce que chaque contrôle regarde

1. Citées contre listées (document ENTIER seulement : sur un chapitre seul,
   le chapitre des sources n'est pas là, rien à comparer). Le chapitre des
   sources se reconnaît par son titre, comme le fait déjà
   `checks_post_rendu` (règle 5) ; une source « listée » est une ligne qui
   porte une adresse.
2. Une même donnée sourcée garde sa formulation : une proportion en toutes
   lettres (« deux sur trois », « les deux tiers ») là où la même source, sur
   le même sujet, publie un pourcentage exact ; ou deux pourcentages exacts
   différents. Le sujet se juge sur les mots pleins autour du chiffre.
3. Un blog ou une newsletter ne porte pas un chiffre de marché : le chiffre
   s'écrit « estimé », ou il sort. La nature se lit dans l'adresse ou le nom
   de la source (liste générique des formes de blog et de lettre).
4. L'origine annoncée dans l'annexe des chiffres : « Estimée » veut dire
   « construite par recoupement, faute de publication » — une seule
   publication citée derrière contredit le mot ; et un blog ne vérifie pas un
   chiffre de marché.
5. Les articles de loi : une liste de règles GÉNÉRIQUES (article cité,
   contexte, article attendu), pas une liste de phrases de cliente.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from .constat import Constat, Reference
from .document import Document, Section, Tableau

CLASSE = "source"

# ── Outils de lecture ───────────────────────────────────────────────────────


def _sans_accents(texte: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn"
    )


def cle(texte: str) -> str:
    """Le texte réduit à ses lettres et chiffres, minuscules, sans accents.

    « Institut Fictif », « institut-fictif.fr » et « INSTITUT FICTIF » se comparent ainsi.
    """
    return re.sub(r"[^a-z0-9]", "", _sans_accents(texte).lower())


def mots(texte: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _sans_accents(texte).lower())


#: Une fin de phrase : ponctuation forte, puis une capitale, un chiffre ou un
#: guillemet. Un point dans « exemple.fr » ou « 7.3 » ne coupe pas.
_FIN_DE_PHRASE = re.compile(r"(?<=[.!?…])\s+(?=[«\"(A-ZÀ-ÖØ-Þ0-9])")


def phrases(paragraphe: str) -> list[str]:
    return [p.strip() for p in _FIN_DE_PHRASE.split(paragraphe) if p.strip()]


def extrait_court(texte: str, plafond: int = 160) -> str:
    """Le début exact du passage, coupé au mot : le lecteur le retrouve tel quel."""
    texte = " ".join(texte.split())
    if len(texte) <= plafond:
        return texte
    tete = texte[:plafond]
    espace = tete.rfind(" ")
    return tete[:espace] if espace > 0 else tete


@dataclass(frozen=True)
class Unite:
    """Ce qu'on lit d'un tenant : une phrase de prose, ou une cellule et sa ligne."""

    section: Section
    #: La phrase, ou la cellule.
    texte: str
    #: La ligne entière du tableau (vide pour la prose) : la source d'une
    #: donnée s'écrit souvent dans la cellule voisine.
    ligne: str = ""

    @property
    def contexte(self) -> str:
        return self.ligne or self.texte

    @property
    def extrait(self) -> str:
        """Ce qu'on cite au lecteur : la cellule, ou sa ligne si la cellule est
        trop courte pour se retrouver seule (« 4 Md€ »)."""
        if self.ligne and len(self.texte.split()) < 5:
            return extrait_court(self.ligne)
        return extrait_court(self.texte)


def unites(section: Section, *, tableaux: Iterable[Tableau] | None = None) -> Iterator[Unite]:
    for paragraphe in section.paragraphes:
        for phrase in phrases(paragraphe):
            yield Unite(section, phrase)
    for tableau in section.tableaux if tableaux is None else tableaux:
        for ligne in (tableau.entetes, *tableau.lignes):
            texte_ligne = " | ".join(c for c in ligne if c)
            for cellule in ligne:
                if cellule.strip():
                    yield Unite(section, cellule, texte_ligne)


# ── Les citations ───────────────────────────────────────────────────────────

_ANNEE = re.compile(r"\b(?:19|20)\d{2}\b")
#: Un nom de domaine : ce qui désigne une source par son adresse.
_DOMAINE = re.compile(
    r"\b(?:[a-z0-9-]+\.)+(?:fr|com|org|net|eu|io|app|info|co|be|ch|ca|de|uk|int)\b",
    re.IGNORECASE,
)
_ADRESSE = re.compile(r"https?://|www\.", re.IGNORECASE)
#: « Source : A, 2026 ; B » — la fine insécable du rendu (`source_lisible`)
#: ou toute autre espace avant les deux-points.
_LIGNE_SOURCE = re.compile(r"^\s*Sources?\s*:\s*(.+)$", re.IGNORECASE | re.DOTALL)
_PARENTHESE = re.compile(r"\(([^()]{2,200})\)")

#: Ce qui désigne le DOSSIER lui-même, pas une source extérieure : ni à lister
#: au chapitre des sources, ni à y chercher.
_INTERNE = re.compile(
    r"(?i)donn[ée]es? du (?:projet|socle|dossier)|\bprojet\b|\bdossier\b|\bporteu[rs]e?\b"
    r"|\bclient(?:e)?\b|\bbrief\b|pr[ée]visionnel|\bcalcul|\bestimation|\bhypoth[èe]se"
    r"|grille de notation|sites? (?:officiels?|internet|web)|\bsocle\b|recoupement"
)

#: Mots qui font d'un nom une INSTITUTION, même en un seul mot.
_INSTITUTION = re.compile(
    r"(?i)\b(?:institut\w*|observatoire|f[ée]d[ée]ration|minist[èe]re|chambre|banque"
    r"|agence|association|syndicat|conseil|commission|office|centre|universit[ée]"
    r"|bar[oô]m[èe]tre|rapport|[ée]tude)\b"
)


@dataclass(frozen=True)
class Citation:
    nom: str
    section: Section
    #: Le passage où elle se lit.
    extrait: str


def _nom_de_segment(segment: str) -> str:
    """« Sondeur, Titre, 2025 » → « Sondeur » ; « exemple.fr, 2025 » → « exemple.fr »."""
    tete = segment.split(",")[0]
    tete = re.split(r"\s+:\s+|\s+—\s+|\s+–\s+", tete)[0]
    tete = _ANNEE.sub("", tete) if not _DOMAINE.search(tete) else tete
    return tete.strip(" .;:()«»\"'")


def _est_domaine(nom: str) -> bool:
    return bool(_DOMAINE.fullmatch(nom.strip().removeprefix("www.")))


def _connue(nom: str, connues: set[str]) -> bool:
    """Déjà nommée ailleurs comme source — « lettredujardin » pour
    « lettredujardin.substack.com » : le début du nom, pas un morceau
    (« france » n'est pas « Chambre de commerce d'Île-de-France »)."""
    compact = cle(nom)
    return bool(compact) and any(
        k == compact or (len(compact) >= 5 and k.startswith(compact)) for k in connues
    )


def _semble_une_source(nom: str, connues: set[str]) -> bool:
    """Un nom propre de source : domaine, institution, sigle, nom composé, ou déjà connue."""
    if not nom or _INTERNE.search(nom):
        return False
    if _est_domaine(nom) or _connue(nom, connues):
        return True
    if not nom[0].isupper():
        return False
    capitales = [m for m in re.findall(r"[^\W\d_][\w'’-]*", nom) if m[0].isupper()]
    sigle = any(re.fullmatch(r"[A-Z][A-Za-z]*[A-Z][A-Za-z]*", m) for m in capitales)
    return len(capitales) >= 2 or sigle or bool(_INSTITUTION.search(nom))


def _segments_de_source(texte: str) -> list[str]:
    return [s.strip() for s in re.split(r"\s;\s|;\s", texte) if s.strip()]


def _liste_de_citations(paragraphe: str, connues: set[str]) -> list[str] | None:
    """« Sondeur, Titre, 2025 ; Blog, Titre, 2025. » : un PARAGRAPHE fait de citations.

    Une phrase ordinaire (« Le marché croît, selon l'étude parue en 2025. »),
    une cellule (« Revenu mensuel, 2028 ») ont la même forme : il faut qu'au
    moins un nom soit déjà donné comme source ailleurs — ligne « Source : »,
    liste du chapitre des sources.
    """
    segments = _segments_de_source(paragraphe.rstrip(". "))
    if not segments or len(paragraphe) > 400:
        return None
    for segment in segments:
        if not (segment[:1].isupper() or _DOMAINE.match(segment)):
            return None
        if "," not in segment or not _ANNEE.search(segment.rsplit(",", 1)[-1]):
            return None
    if not any(_connue(_nom_de_segment(s), connues) for s in segments):
        return None
    return segments


def _segments_declares(paragraphe: str, connues: set[str]) -> list[str]:
    """Les citations d'un paragraphe ENTIER : ligne « Source : » ou liste de citations."""
    ligne = _LIGNE_SOURCE.match(paragraphe)
    if ligne:
        return _segments_de_source(ligne.group(1))
    return _liste_de_citations(paragraphe, connues) or []


def noms_declares(document: Document) -> set[str]:
    """Les noms donnés comme SOURCES : lignes « Source : », lignes du chapitre des
    sources qui portent une adresse, listes de citations.

    Ils servent à reconnaître, dans une parenthèse, un nom d'un seul mot
    (« (Sondeur, 2025) ») sans prendre « (France, 2026) » pour une source.
    """
    connus: set[str] = set()
    for section in document.sections:
        for paragraphe in section.paragraphes:
            ligne = _LIGNE_SOURCE.match(paragraphe)
            for segment in _segments_de_source(ligne.group(1)) if ligne else []:
                nom = _nom_de_segment(segment)
                if nom and not _INTERNE.search(nom):
                    connus.add(cle(nom))
        for tableau in section.tableaux:
            for rang in tableau.lignes:
                if rang and rang[0].strip() and any(map(_adresse, rang[1:])):
                    connus.add(cle(re.split(r"[,(]", rang[0])[0]))
    for section in document.sections:
        for paragraphe in section.paragraphes:
            for segment in _liste_de_citations(paragraphe, connus) or []:
                connus.add(cle(_nom_de_segment(segment)))
    return {c for c in connus if c}


def citations_de(texte: str, connues: set[str]) -> list[str]:
    """Les noms de sources cités dans un passage : ligne « Source : », parenthèses.

    Une liste de citations sans « Source : » ne se reconnaît qu'à l'échelle du
    paragraphe entier (`_segments_declares`), jamais dans une cellule.
    """
    noms: list[str] = []
    ligne = _LIGNE_SOURCE.match(texte)
    for segment in _segments_de_source(ligne.group(1)) if ligne else []:
        nom = _nom_de_segment(segment)
        if nom and not _INTERNE.search(nom) and (nom[0].isupper() or _est_domaine(nom)):
            noms.append(nom)
    for parenthese in _PARENTHESE.findall(texte):
        for segment in _segments_de_source(parenthese):
            nom = _nom_de_segment(segment)
            datee = bool(_ANNEE.search(segment)) or _est_domaine(nom)
            if datee and _semble_une_source(nom, connues):
                noms.append(nom)
    return list(dict.fromkeys(noms))


# ── Le chapitre des sources ─────────────────────────────────────────────────


@dataclass
class SourceListee:
    nom: str
    section: Section
    #: Toute la ligne : nom, ce qu'elle étaye, adresse.
    texte: str
    adresse: str = ""
    cles: set[str] = field(default_factory=set)


def _est_annexe_des_chiffres(tableau: Tableau) -> bool:
    """Le tableau « Donnée | Valeur | Année | Origine » de l'annexe construite."""
    return "origine" in {cle(c) for c in tableau.entetes}


def chapitre_des_sources(document: Document) -> int | None:
    """Le numéro du chapitre « Sources… », reconnu comme `checks_post_rendu` le reconnaît."""
    from ..checks_post_rendu import _TITRE_SOURCES_RE  # noqa: PLC0415 — règle 5

    numeros = [
        s.chapitre for s in document.sections
        if s.chapitre is not None and s.numero == f"ch. {s.chapitre}"
        and _TITRE_SOURCES_RE.match(s.titre or "")
    ]
    return numeros[-1] if numeros else None


def _adresse(texte: str) -> str:
    if not (_ADRESSE.search(texte) or _DOMAINE.search(texte)):
        return ""
    # Une adresse coupée en fin de ligne du PDF se lit « portail- auto… » :
    # on recolle avant d'en lire le domaine.
    recollee = re.sub(r"(?<=[-/.])\s+", "", texte)
    domaine = _DOMAINE.search(recollee)
    return domaine.group(0).lower() if domaine else ""


#: Hébergeurs de blogs et de lettres : leur nom ne désigne pas la source.
_HEBERGEURS = frozenset({"substack", "medium", "wordpress", "blogspot", "overblog", "beehiiv"})


def _cles_de_source(nom: str, adresse: str) -> set[str]:
    cles = {cle(nom), cle(re.split(r"[,(]", nom)[0])}
    if adresse:
        hote = adresse.removeprefix("www.")
        cles.add(cle(hote))
        etiquettes = [e for e in hote.split(".")[:-1] if cle(e) not in _HEBERGEURS]
        if len(etiquettes) == 1 and "gouv" not in hote:
            cles.add(cle(etiquettes[0]))
    return {c for c in cles if len(c) >= 4}


def sources_listees(document: Document, chapitre: int) -> tuple[list[SourceListee], str]:
    """Les sources EXTÉRIEURES listées (celles qui portent une adresse), et tout le texte
    du chapitre des sources, où l'on cherche une source citée."""
    listees: list[SourceListee] = []
    textes: list[str] = []
    for section in document.sections:
        if section.chapitre != chapitre:
            continue
        for paragraphe in section.paragraphes:
            textes.append(paragraphe)
            adresse = _adresse(paragraphe)
            if adresse:
                nom = re.split(r"\s+[—–:]\s+", paragraphe, maxsplit=1)[0].lstrip("-•* ")
                listees.append(SourceListee(nom, section, paragraphe, adresse))
        for tableau in section.tableaux:
            if _est_annexe_des_chiffres(tableau):
                continue
            for ligne in (tableau.entetes, *tableau.lignes):
                texte = " | ".join(ligne)
                textes.append(texte)
                adresse = next((a for a in map(_adresse, ligne[1:]) if a), "")
                if adresse and ligne and ligne[0].strip():
                    listees.append(SourceListee(ligne[0].strip(), section, texte, adresse))
    for source in listees:
        source.cles = _cles_de_source(source.nom, source.adresse)
    return listees, "\n".join(textes)


def _dans(nom: str, meule: str, mots_de_la_meule: set[str]) -> bool:
    """`nom` figure-t-il dans `meule` ? Sous-chaîne pour un nom long, mot entier sinon."""
    compact = cle(nom)
    if not compact:
        return True
    if len(compact) >= 5:
        return compact in meule
    return compact in mots_de_la_meule


# ── 1. Citées contre listées ────────────────────────────────────────────────


def _citations_du_document(document: Document, chapitre: int) -> list[Citation]:
    connues = noms_declares(document)
    citations: list[Citation] = []
    for section in document.sections:
        hors_sources = section.chapitre != chapitre
        tableaux = [
            t for t in section.tableaux if hors_sources or _est_annexe_des_chiffres(t)
        ]
        paragraphes = section.paragraphes if hors_sources else []
        vue = Section(section.numero, section.titre, section.chapitre, paragraphes, tableaux)
        for paragraphe in paragraphes:
            for segment in _liste_de_citations(paragraphe, connues) or []:
                nom = _nom_de_segment(segment)
                if nom and not _INTERNE.search(nom):
                    citations.append(Citation(nom, section, extrait_court(paragraphe)))
        for unite in unites(vue):
            for nom in citations_de(unite.texte, connues):
                citations.append(Citation(nom, section, unite.extrait))
            for nom in _sources_d_origine(unite.texte):
                citations.append(Citation(nom, section, unite.extrait))
    return citations


def _natures() -> dict[str, str]:
    """Les mots de l'annexe des chiffres (« Vérifiée », « Estimée »…) par fiabilité :
    ceux que le rendu écrit (règle 5)."""
    from ..rendu_word.annexe_chiffres import _NATURE  # noqa: PLC0415

    return {str(fiabilite): mot for fiabilite, mot in _NATURE.items()}


def _nature(membre: str) -> str:
    """Le mot de l'annexe pour une fiabilité : `_nature("OBSERVEE")` → « Vérifiée »."""
    from ..socle.referentiel import Fiabilite  # noqa: PLC0415

    return _natures()[str(Fiabilite[membre])]


def _origine(cellule: str) -> tuple[str, str] | None:
    """« Estimée — Blog Fictif, 2026 » → (« Estimée », « Blog Fictif, 2026 »)."""
    natures = "|".join(map(re.escape, _natures().values()))
    trouve = re.match(rf"^\s*({natures})\s*[—–-]\s*(.+)$", cellule, re.DOTALL)
    return (trouve.group(1), trouve.group(2).strip()) if trouve else None


def _sources_d_origine(cellule: str) -> list[str]:
    origine = _origine(cellule)
    if origine is None:
        return []
    nom = _nom_de_segment(origine[1])
    return [nom] if nom and not _INTERNE.search(nom) and nom[:1].isupper() else []


def _citees_contre_listees(document: Document, chapitre: int) -> list[Constat]:
    listees, texte_du_chapitre = sources_listees(document, chapitre)
    meule = cle(texte_du_chapitre)
    mots_meule = set(mots(texte_du_chapitre))
    constats: list[Constat] = []

    par_nom: dict[str, list[Citation]] = defaultdict(list)
    for citation in _citations_du_document(document, chapitre):
        par_nom[cle(citation.nom)].append(citation)
    for occurrences in par_nom.values():
        premiere = occurrences[0]
        if _dans(premiere.nom, meule, mots_meule):
            continue
        ailleurs = list(dict.fromkeys(c.section.numero for c in occurrences))
        constats.append(Constat(
            CLASSE, premiere.section.numero, premiere.extrait,
            f"« {premiere.nom} » est cité ({', '.join(ailleurs)}) mais ne figure pas au "
            "chapitre des sources. Toute source citée y figure, avec son adresse : "
            "l'ajouter à la liste, ou retirer la citation et le chiffre qu'elle porte.",
            grave=False,
        ))

    corps = [
        texte for section in document.sections
        for texte in _textes_hors_liste(section, chapitre)
    ]
    corps_compact = cle("\n".join(corps))
    corps_mots = set(mots("\n".join(corps)))
    for source in listees:
        if any(_dans(c, corps_compact, corps_mots) for c in source.cles):
            continue
        constats.append(Constat(
            CLASSE, source.section.numero, extrait_court(source.nom),
            f"« {source.nom} » est listée au chapitre des sources mais le texte ne la cite "
            "nulle part. Toute source listée sert au moins une fois : la citer là où sa "
            "donnée est employée, ou la retirer de la liste.",
            grave=False,
        ))
    return constats


def _textes_hors_liste(section: Section, chapitre: int) -> Iterator[str]:
    """Ce que le lecteur lit hors de la liste des sources (l'annexe des chiffres comprise)."""
    if section.chapitre != chapitre:
        yield section.texte()
        return
    for tableau in section.tableaux:
        if _est_annexe_des_chiffres(tableau):
            yield from (" | ".join(ligne) for ligne in tableau.lignes)


# ── 2. Une donnée sourcée, une formulation ──────────────────────────────────

_NOMBRES_EN_LETTRES = {
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6,
    "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
}
_DENOMINATEURS = {
    "demi": 2, "demie": 2, "tiers": 3, "quart": 4, "quarts": 4, "cinquieme": 5,
    "cinquiemes": 5, "dixieme": 10, "dixiemes": 10,
}
_EN_LETTRES = "|".join(_NOMBRES_EN_LETTRES)
#: « Deux clients sur trois », « 3 clients sur 4 ».
_SUR = re.compile(
    rf"(?i)\b({_EN_LETTRES}|\d{{1,2}})\s+(?:[\w'’-]+\s+){{0,3}}?sur\s+({_EN_LETTRES}|\d{{1,2}})\b"
)
#: « les deux tiers », « un quart », « la moitié ».
_FRACTION = re.compile(
    rf"(?i)\b(?:({_EN_LETTRES})\s+(tiers|quarts?|cinqui[èe]mes?|dixi[èe]mes?)|(moiti[ée]))\b"
)
_POURCENT = re.compile(r"(?<![\d,])(\d{1,3}(?:,\d+)?)[^\S\r\n]?%")

#: Mots sans poids pour dire DE QUOI parle un chiffre.
_VIDES = frozenset(
    "les des une aux par pour sur sous dans avec sans plus moins parmi pres environ "
    "leur leurs cette ces ses son sont est ont qui que quoi dont tout tous toute "
    "toutes deja entre chez vers selon apres avant aussi ainsi encore tres deux "
    "trois quatre cinq sept huit neuf dix onze douze tiers quart quarts moitie "
    "proportion part pourcent source".split()
)


def _valeur_en_lettres(mot: str) -> int | None:
    mot = _sans_accents(mot.lower())
    return int(mot) if mot.isdigit() else _NOMBRES_EN_LETTRES.get(mot)


@dataclass(frozen=True)
class Proportion:
    #: « exacte » (un pourcentage écrit) ou « en_lettres » (« deux sur trois »).
    forme: str
    valeur: float
    debut: int
    fin: int


def proportions(texte: str) -> list[Proportion]:
    trouvees: list[Proportion] = []
    for m in _POURCENT.finditer(texte):
        trouvees.append(Proportion("exacte", float(m.group(1).replace(",", ".")), *m.span()))
    for m in _SUR.finditer(texte):
        num, den = _valeur_en_lettres(m.group(1)), _valeur_en_lettres(m.group(2))
        if num and den and 0 < num < den:
            trouvees.append(Proportion("en_lettres", round(100 * num / den, 1), *m.span()))
    for m in _FRACTION.finditer(texte):
        if m.group(3):
            num, den = 1, 2
        else:
            num = _valeur_en_lettres(m.group(1)) or 0
            den = _DENOMINATEURS.get(_sans_accents(m.group(2).lower()), 0)
        if num and den and num < den:
            trouvees.append(Proportion("en_lettres", round(100 * num / den, 1), *m.span()))
    return trouvees


def _sujet(texte: str, proportion: Proportion, sources: Iterable[str]) -> set[str]:
    """Les mots pleins autour du chiffre : quatre avant, douze après."""
    exclus = {m for s in sources for m in mots(s)}
    avant = mots(texte[: proportion.debut])[-4:]
    dedans = mots(texte[proportion.debut : proportion.fin])
    apres = mots(texte[proportion.fin :])[:12]
    return {
        m for m in (*avant, *dedans, *apres)
        if len(m) >= 4 and not m.isdigit() and m not in _VIDES and m not in exclus
    }


def _meme_sujet(a: set[str], b: set[str]) -> bool:
    communs = a & b
    return len(communs) >= 3 and len(communs) / min(len(a), len(b)) >= 0.6


@dataclass(frozen=True)
class Enonce:
    source: str
    unite: Unite
    forme: str
    valeur: float
    sujet: frozenset[str]
    rang: int


def _sources_de_section(section: Section, connues: set[str]) -> list[str]:
    noms: list[str] = []
    for paragraphe in section.paragraphes:
        for segment in _segments_declares(paragraphe, connues):
            nom = _nom_de_segment(segment)
            if nom and not _INTERNE.search(nom):
                noms.append(nom)
    return noms


def _enonces(document: Document) -> list[Enonce]:
    connues = noms_declares(document)
    enonces: list[Enonce] = []
    rang = 0
    for section in document.sections:
        de_la_section = _sources_de_section(section, connues)
        for unite in unites(section):
            if _LIGNE_SOURCE.match(unite.texte) or _liste_de_citations(unite.texte, connues):
                continue
            trouvees = proportions(unite.texte)
            if not trouvees:
                continue
            sources = citations_de(unite.contexte, connues) or de_la_section
            if not sources:
                continue
            exactes = [p for p in trouvees if p.forme == "exacte"]
            # « Près des deux tiers (65 %) » : le chiffre exact est écrit, c'est
            # lui qui fait foi pour la phrase.
            retenue = exactes[0] if exactes else trouvees[0]
            sujet = frozenset(_sujet(unite.texte, retenue, sources))
            if len(sujet) < 3:
                continue
            for source in sources:
                rang += 1
                enonces.append(
                    Enonce(source, unite, retenue.forme, retenue.valeur, sujet, rang)
                )
    return enonces


def _formulations_divergentes(document: Document) -> list[Constat]:
    par_source: dict[str, list[Enonce]] = defaultdict(list)
    for enonce in _enonces(document):
        par_source[cle(enonce.source)].append(enonce)
    constats: list[Constat] = []
    for enonces in par_source.values():
        for enonce in enonces:
            voisins = [
                e for e in enonces
                if e.unite is not enonce.unite and e.forme == "exacte"
                and _meme_sujet(set(e.sujet), set(enonce.sujet))
            ]
            if not voisins:
                continue
            valeurs = Counter(round(e.valeur, 1) for e in voisins)
            if enonce.forme == "exacte":
                valeurs[round(enonce.valeur, 1)] += 1
            reference, _ = valeurs.most_common(1)[0]
            # L'exemple cité en modèle : un énoncé au chiffre exact SEUL (pas
            # « près des deux tiers (65 %) »), le premier dans le document.
            premiere = min(
                (e for e in voisins if round(e.valeur, 1) == reference),
                key=lambda e: (
                    any(p.forme == "en_lettres" for p in proportions(e.unite.texte)), e.rang,
                ),
                default=voisins[0],
            )
            ecrite = _nombre(reference)
            ailleurs = ", ".join(dict.fromkeys(
                e.unite.section.numero for e in voisins if round(e.valeur, 1) == reference
            ))
            if enonce.forme == "en_lettres":
                detail = (
                    f"La même donnée ({enonce.source}) s'écrit « {ecrite} % » en {ailleurs} "
                    f"(« {extrait_court(premiere.unite.texte, 90)} ») : une donnée sourcée "
                    f"garde la même formulation dans tout le document. Écrire « {ecrite} % » "
                    "ici aussi, jamais une proportion en toutes lettres qui l'arrondit."
                )
            elif round(enonce.valeur, 1) != reference and (
                valeurs[round(enonce.valeur, 1)] < valeurs[reference]
                or enonce.rang > premiere.rang
            ):
                detail = (
                    f"La même donnée ({enonce.source}) vaut « {ecrite} % » en {ailleurs} et "
                    f"« {_nombre(enonce.valeur)} % » ici : une donnée sourcée garde la même "
                    f"valeur dans tout le document. Reprendre « {ecrite} % »."
                )
            else:
                continue
            constats.append(Constat(
                CLASSE, enonce.unite.section.numero, enonce.unite.extrait, detail,
            ))
    return constats


def _nombre(valeur: float) -> str:
    return f"{valeur:g}".replace(".", ",")


# ── 3. Blogs et newsletters : pas de chiffre de marché ──────────────────────

#: Ce qui fait d'une source un blog ou une lettre d'information : son nom, ou
#: la forme de son adresse. Formes génériques, pas des noms de cliente.
_BLOG = re.compile(
    r"(?i)newsletter|lettre d.information|\bblog|substack\.|beehiiv|medium\.com"
    r"|wordpress\.com|blogspot\.|over-blog|linkedin\.com/pulse"
)
_MARCHE = re.compile(r"(?i)\bmarch[ée]s?\b")
_ESTIME = re.compile(r"(?i)\bestim")


def _montants(texte: str) -> list[tuple[str, float, str | None]]:
    from ..memoire.controle import nombres_du_texte  # noqa: PLC0415 — règle 5

    return [n for n in nombres_du_texte(texte) if n[2] in {"%", "k€", "M€", "Md€", "€"}]


def _chiffre_de_marche(texte: str) -> list[tuple[str, float, str | None]]:
    """Les montants et pourcentages d'un passage qui parle d'un marché."""
    if not _MARCHE.search(texte):
        return []
    return [n for n in _montants(texte) if n[2] != "€" or n[1] >= 1e6]


def _natures_blog(listees: Iterable[SourceListee]) -> list[SourceListee]:
    return [s for s in listees if _BLOG.search(f"{s.texte} {s.adresse}")]


def _blog_parmi(noms: Iterable[str], blogs: list[SourceListee]) -> str | None:
    """Le premier de ces noms qui désigne un blog ou une newsletter."""
    for nom in noms:
        if _BLOG.search(nom):
            return nom
        compact = cle(nom)
        for blog in blogs:
            if len(compact) >= 4 and any(compact in c or c in compact for c in blog.cles):
                return blog.nom
    return None


def _blogs_listes(document: Document) -> list[SourceListee]:
    chapitre = chapitre_des_sources(document)
    return _natures_blog(sources_listees(document, chapitre)[0]) if chapitre is not None else []


def _blogs_et_chiffres_de_marche(document: Document, chapitre: int | None) -> list[Constat]:
    listees, _ = sources_listees(document, chapitre) if chapitre is not None else ([], "")
    blogs = _natures_blog(listees)
    connues = noms_declares(document)

    def blog_de(texte: str) -> str | None:
        """Le blog cité par ce passage, s'il en cite un."""
        return _blog_parmi(citations_de(texte, connues), blogs)

    constats: list[Constat] = []
    #: (valeur, unité) → le blog qui la porte.
    portes: dict[tuple[float, str | None], str] = {}
    for section in document.sections:
        for tableau in section.tableaux:
            if not _est_annexe_des_chiffres(tableau):
                continue
            for ligne in tableau.lignes:
                origine = next((o for o in map(_origine, ligne) if o), None)
                blog = _blog_parmi(
                    [nom for cellule in ligne for nom in _sources_d_origine(cellule)], blogs,
                )
                chiffres = _chiffre_de_marche(" | ".join(ligne[:2]))
                if origine is None or blog is None or not chiffres:
                    continue
                for _, valeur, unite in chiffres:
                    portes[(valeur, unite)] = blog
                if origine[0] == _nature("OBSERVEE"):
                    constats.append(Constat(
                        CLASSE, section.numero, extrait_court(" | ".join(ligne)),
                        f"Chiffre de marché « {origine[0]} » alors que sa source, {blog}, est un "
                        "blog ou une newsletter : ils ne vérifient pas un chiffre de marché. "
                        "L'origine s'écrit « Estimée », ou le chiffre sort de l'étude.",
                        grave=False,
                    ))

    for section in document.sections:
        tableaux = [
            t for t in section.tableaux
            if not _est_annexe_des_chiffres(t)
            and not (section.chapitre == chapitre and any(map(_adresse, t.cellules())))
        ]
        vue = Section(
            section.numero, section.titre, section.chapitre, section.paragraphes, tableaux,
        )
        #: Un constat par blog et par section : le rédacteur corrige la section.
        vus: set[str] = set()
        for unite in unites(vue):
            if _LIGNE_SOURCE.match(unite.texte) or _ESTIME.search(unite.contexte):
                continue
            # Le chiffre est dans CETTE cellule ; « marché » et la source peuvent
            # être dans la ligne.
            chiffres = [n for n in _chiffre_de_marche(unite.contexte) if n[0] in unite.texte]
            if not chiffres:
                continue
            blog = blog_de(unite.contexte)
            portes_ici = [
                (ecriture, portes[(v, u)]) for ecriture, v, u in chiffres if (v, u) in portes
            ]
            if blog is None and not portes_ici:
                continue
            nom_blog = blog or portes_ici[0][1]
            ecrits = [e for e, _ in portes_ici] or [n[0] for n in chiffres]
            if nom_blog in vus:
                continue
            vus.add(nom_blog)
            constats.append(Constat(
                CLASSE, section.numero, unite.extrait,
                f"« {' », « '.join(dict.fromkeys(ecrits))} » : chiffre de marché porté par "
                f"{nom_blog}, un blog ou une newsletter, écrit comme un fait établi. Un blog ne "
                "porte pas un chiffre de marché : écrire « estimé à … » avec sa source, ou "
                "retirer le chiffre.",
            ))
    return constats


# ── 4. L'origine annoncée dans l'annexe des chiffres ────────────────────────


def _origines_contradictoires(document: Document) -> list[Constat]:
    """« Estimée — une seule publication » : le mot dit « faute de publication »."""
    estimee = _nature("ESTIMEE")
    blogs = _blogs_listes(document)
    constats: list[Constat] = []
    for section in document.sections:
        for tableau in section.tableaux:
            if not _est_annexe_des_chiffres(tableau):
                continue
            for ligne in tableau.lignes:
                origine = next((o for o in map(_origine, ligne) if o), None)
                if origine is None or origine[0] != estimee:
                    continue
                source = origine[1]
                nom = _nom_de_segment(source)
                if (
                    not nom or _INTERNE.search(source) or ";" in source
                    or _blog_parmi([nom, source], blogs)
                    or not _semble_une_source(nom, set())
                ):
                    # Un blog cité derrière « Estimée » : c'est exactement ce
                    # qu'il faut écrire (contrôle 3).
                    continue
                constats.append(Constat(
                    CLASSE, section.numero, extrait_court(" | ".join(ligne)),
                    f"Origine « {estimee} » avec une seule publication citée ({nom}). "
                    "« Estimée » veut dire construite par recoupement, faute de publication : "
                    "si la source publie ce chiffre, il est « Vérifiée » ; sinon, l'origine "
                    "dit le recoupement ou le calcul.",
                    grave=False,
                ))
    return constats


# ── 5. Les articles de loi ──────────────────────────────────────────────────


@dataclass(frozen=True)
class RegleJuridique:
    """Un article cité à tort dans un contexte donné, et celui qui s'applique."""

    #: L'article cité.
    cite: re.Pattern[str]
    #: Ce dont parle le passage (sinon l'article peut être juste).
    sujet: re.Pattern[str]
    #: Le contexte de l'activité qui rend l'article faux (dans la section ou le
    #: document).
    contexte: re.Pattern[str]
    #: L'article qui, s'il est cité dans le passage, rend la citation juste.
    attendu: re.Pattern[str]
    detail: str


#: Activités de loisirs fournies à une date ou une période déterminée
#: (art. L221-28 12° du code de la consommation) : ateliers, séjours,
#: spectacles, hébergement, restauration, locations de voiture.
_LOISIRS_A_DATE = re.compile(
    r"(?i)\b(?:ateliers?|s[ée]jours?|week-ends?|soir[ée]es?|spectacles?|concerts?|excursions?"
    r"|visites? guid[ée]es?|cours collectifs?|activit[ée]s? de loisirs?|loisirs?"
    r"|h[ée]bergements?|locations? de voitures?|s[ée]ances?|sessions?)\b"
)

REGLES_JURIDIQUES: tuple[RegleJuridique, ...] = (
    RegleJuridique(
        cite=re.compile(r"(?i)\bL\.?\s?221-18\b"),
        sujet=re.compile(r"(?i)r[ée]tractation"),
        contexte=_LOISIRS_A_DATE,
        attendu=re.compile(r"(?i)\bL\.?\s?221-28\b"),
        detail=(
            "Pour des activités de loisirs fournies à une date déterminée (ateliers, séjours, "
            "soirées), le droit de rétractation est EXCLU : article L221-28 12° du code de la "
            "consommation. L'article L221-18 (délai de 14 jours) ne s'applique pas. Écrire : "
            "« pas de droit de rétractation — article L221-28 12° du code de la consommation "
            "(activités de loisirs à date déterminée) »."
        ),
    ),
)

#: Au-delà de ce nombre de mentions dans le document, l'activité EST de
#: celles que vise la règle, même si la section n'en reparle pas.
_MENTIONS_DE_CONTEXTE = 3


def _articles_de_loi(document: Document) -> list[Constat]:
    constats: list[Constat] = []
    texte_du_document = document.texte()
    for regle in REGLES_JURIDIQUES:
        dans_le_document = len(regle.contexte.findall(texte_du_document))
        for section in document.sections:
            texte_section = section.texte()
            contexte = bool(regle.contexte.search(texte_section)) or (
                dans_le_document >= _MENTIONS_DE_CONTEXTE
            )
            if not contexte:
                continue
            vus: set[str] = set()
            for unite in unites(section):
                # Le passage qui CITE l'article est l'extrait ; la ligne
                # entière dit de quoi il parle (« Délai de rétractation »
                # vit souvent dans la cellule voisine).
                passage = unite.contexte
                if not regle.cite.search(unite.texte):
                    continue
                if not regle.sujet.search(passage) or regle.attendu.search(passage):
                    continue
                if passage in vus:
                    continue
                vus.add(passage)
                constats.append(Constat(
                    CLASSE, section.numero, unite.extrait, regle.detail,
                ))
    return constats


# ── Le contrôle ─────────────────────────────────────────────────────────────


def controler(document: Document, reference: Reference) -> list[Constat]:
    constats = [*_articles_de_loi(document), *_formulations_divergentes(document)]
    chapitre = chapitre_des_sources(document) if reference.document_entier else None
    constats += _blogs_et_chiffres_de_marche(document, chapitre)
    if reference.document_entier:
        constats += _origines_contradictoires(document)
        if chapitre is None:
            # Règle 1 : sans chapitre des sources, la comparaison n'a rien à
            # comparer — c'est un constat, pas un silence.
            derniere = document.sections[-1] if document.sections else None
            constats.append(Constat(
                CLASSE, derniere.numero if derniere else "début",
                derniere.titre if derniere else "",
                "Aucun chapitre « Sources » reconnu dans le document : les sources citées ne "
                "peuvent pas être rapprochées d'une liste. Le document se termine par un "
                "chapitre « Sources et méthodologie ».",
                grave=False,
            ))
        else:
            constats += _citees_contre_listees(document, chapitre)
    return constats

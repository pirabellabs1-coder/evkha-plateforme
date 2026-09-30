"""Comptages, dénombrements et décisions contradictoires (classe 6).

« N sur M », « N formats », « N familles » vérifiés contre la mémoire ou le
tableau voisin ; une même décision (date, seuil, statut) écrite de deux
façons.

## Le défaut, relevé par la cliente

Business plan ÉCLORE `28a257bf` (30/09/2026) : « Toute phrase "N sur M",
"N concurrents", "N formats", "N familles", "N leviers" est vérifiée contre la
mémoire ou contre le tableau voisin. » Elle lisait :

- « N concurrents directs sur M » (10.2, 10.7) avec un M que la base ne
  connaît pas — et les deux phrases se contredisent entre elles ;
- « N concurrents directs sur M restent en dessous du niveau visé » (5.2)
  quand la grille de notation les y place tous ;
- « la moitié des concurrents directs » sur devis (8.3) quand le document
  compte ailleurs, trois fois, un autre nombre de prix fermes ;
- « N formats » (ch. 8, 8.1) au-dessus d'un tableau qui en liste un de moins ;
  « trois familles de fournisseurs » (12.6) au-dessus de cinq fournisseurs
  que rien ne range en familles ;
- et des décisions écrites de deux façons : une offre lancée « en phase 3 »
  (4.4) ou « à l'automne » d'une autre année (12.2) ; le départ du poste
  daté d'une année partout, mais de « fin » de cette année en 18.6 ; l'apport
  « engagé » (15.2) puis « à confirmer » (15.3) ; les fournisseurs « réglés
  après la session » (14.4) quand quatre sections parlent d'acomptes versés
  avant ; la TVA « dès que le chiffre d'affaires dépasse le seuil de
  franchise » (11.3), qui n'est pas la règle.

## Ce qui fait foi, dans l'ordre

1. **La mémoire** : le compte des concurrents (décision « concurrents »), les
   décisions du cadrage (date du départ), la règle de TVA
   (`memoire.regles.FRANCHISE_TVA`).
2. **Le tableau voisin** : celui de la section, ou de la suivante pour
   l'accroche d'un chapitre, dont une colonne porte le nom compté.
3. **Le document lui-même** : quand ni l'un ni l'autre ne tranche, la valeur
   que la majorité des sections écrit ; sans majorité, chaque version est
   signalée — le lecteur ne peut pas savoir laquelle croire.

Aucun appel au modèle ; aucun chiffre inventé : un compte qu'on ne sait pas
refaire n'est pas jugé (règle 2).
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from generation.arithmetique import _COMPTE_EN_LETTRES
from generation.memoire.regles import FRANCHISE_TVA, Seuil

from .constat import Constat, Reference
from .document import Document, Section, Tableau
from .fuites import PHRASE, RENVOI, est_un_encadre, racines, texte_lisible

# ── Nombres, phrases, propositions ──────────────────────────────────────────

#: Les nombres en lettres du dépôt (`arithmetique`, règle 5) : de deux à
#: seize, et vingt. « Un », « une » sont d'abord des articles.
#:
#: Un compte est un nombre ENTIER et SEUL : ni le « dix » de « dix-sept », ni
#: le « 2 » de « 2 500 », ni le « 5 » de « 5,5 » (revue du 30/09/2026 : « sur
#: dix-sept » lu « sur dix », « 300 acteurs sur 2 500 » lu « sur 2 »).
_NB = (
    r"(?<![\w-])(?:\d{1,3}(?![\d])(?![.,]\d)(?!\s\d{3}\b)|"
    + "|".join(sorted(_COMPTE_EN_LETTRES, key=len, reverse=True))
    + r")(?![-‑]\w)"
)
_EN_LETTRES = {valeur: mot for mot, valeur in _COMPTE_EN_LETTRES.items()}


def _nombre(brut: str) -> int:
    brut = brut.strip().lower()
    return int(brut) if brut.isdigit() else _COMPTE_EN_LETTRES[brut]


def _ecrire(n: int) -> str:
    return _EN_LETTRES.get(n, str(n))


_PHRASES = PHRASE
#: Une proposition s'arrête au point-virgule, au deux-points, au tiret long.
_COUPURES = re.compile(r"\s*;\s+|\s+:\s+|:\s+|\s+[—–]\s+")


def _spans(motif: re.Pattern[str], texte: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in motif.finditer(texte)]


def _propositions(texte: str) -> list[tuple[int, int]]:
    """Les bornes de chaque proposition : phrases, puis coupures fortes."""
    bornes: list[tuple[int, int]] = []
    for phrase in _PHRASES.finditer(texte):
        debut = phrase.start()
        for coupure in _COUPURES.finditer(texte, phrase.start(), phrase.end()):
            bornes.append((debut, coupure.start()))
            debut = coupure.end()
        bornes.append((debut, phrase.end()))
    return [(a, b) for a, b in bornes if texte[a:b].strip()]


def _borne_autour(bornes: list[tuple[int, int]], position: int) -> tuple[int, int]:
    for debut, fin in bornes:
        if debut <= position < fin:
            return debut, fin
    return 0, 0


def _court(texte: str, largeur: int = 170) -> str:
    """Le début du passage, coupé à un mot entier et SANS « … » ajouté.

    L'extrait doit se retrouver tel quel dans le document (règle 2) : une
    ellipse qu'il ne contient pas le rendrait introuvable.
    """
    texte = texte.strip(" ,;")
    return texte if len(texte) <= largeur else texte[:largeur].rsplit(" ", 1)[0]


# ── Ce que le lecteur lit, cellule par cellule ───────────────────────────────


@dataclass(frozen=True)
class _Passage:
    """Un texte lu d'un tenant, et d'où il vient."""

    section: str
    texte: str
    #: Pour une cellule de tableau de données : sa ligne, les en-têtes, son rang.
    ligne: tuple[str, ...] | None = None
    entetes: tuple[str, ...] = ()
    colonne: int = -1


def _tableaux_fusionnes(section: Section) -> list[Tableau]:
    """Les tableaux de la section, ceux qu'une page a coupés en deux recollés.

    Le PDF répète l'en-tête sur la page suivante : deux tableaux consécutifs aux
    mêmes en-têtes sont un seul tableau (« Poste » : 8 lignes puis 4 = douze).
    """
    fusion: list[Tableau] = []
    for tableau in section.tableaux:
        if fusion and fusion[-1].entetes == tableau.entetes:
            fusion[-1] = Tableau(fusion[-1].entetes, fusion[-1].lignes + tableau.lignes)
        else:
            fusion.append(tableau)
    return fusion


def _passages(document: Document) -> Iterator[_Passage]:
    for section in document.sections:
        if section.titre:
            yield _Passage(section.numero, texte_lisible(section.titre))
        for paragraphe in section.paragraphes:
            yield _Passage(section.numero, texte_lisible(paragraphe))
        for tableau in _tableaux_fusionnes(section):
            if est_un_encadre(tableau):
                for cellule in tableau.cellules():
                    yield _Passage(section.numero, texte_lisible(cellule))
                continue
            entetes = tuple(texte_lisible(e) for e in tableau.entetes)
            for ligne in tableau.lignes:
                propre = tuple(texte_lisible(c) for c in ligne)
                for colonne, cellule in enumerate(propre):
                    if cellule:
                        yield _Passage(section.numero, cellule, propre, entetes, colonne)


# ═════════════════════════════════════════════════════════════════════════════
# 1. Les comptes de concurrents, contre la base de la mémoire
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class _Base:
    total: int
    directs: int
    indirects: int
    libelle: str

    def attendus(self, nom: str, qualificatif: str) -> set[int]:
        """Les comptes qui désignent la population ENTIÈRE nommée ainsi."""
        if qualificatif.startswith("direct"):
            return {self.directs}
        if qualificatif.startswith("indirect"):
            return {self.indirects}
        if nom.startswith("acteur"):
            return {self.total}
        return {self.total, self.directs}

    def taille(self, population: str) -> int:
        return {"directs": self.directs, "indirects": self.indirects}.get(
            population, self.total
        )


def _base(reference: Reference) -> _Base | None:
    """Le compte de la base, lu dans la décision « concurrents » de la mémoire.

    La décision est une phrase (`memoire.decisions`, « N concurrents analysés
    (D directs, I indirects) ») : si sa forme change sans que ce lecteur suive,
    les comptes cesseraient d'être jugés EN SILENCE (règle 1). Une décision
    présente mais illisible se dit donc au journal ; le test
    `test_la_base_se_lit_dans_la_vraie_memoire` la relit telle que la mémoire
    l'écrit.
    """
    memoire = reference.memoire
    if memoire is None:
        return None
    decision = next((d for d in memoire.decisions if d.sujet == "concurrents"), None)
    if decision is None:
        return None
    total = re.search(r"(\d+)\s+concurrents", decision.valeur)
    directs = re.search(r"(\d+)\s+directs", decision.valeur)
    indirects = re.search(r"(\d+)\s+indirects", decision.valeur)
    if not (total and directs and indirects):
        import logging  # noqa: PLC0415

        logging.getLogger(__name__).warning(
            "Relecture des comptages : décision « concurrents » illisible (%r) — les "
            "comptes de concurrents ne sont PAS jugés.", decision.valeur,
        )
        return None
    return _Base(
        int(total.group(1)), int(directs.group(1)), int(indirects.group(1)), decision.valeur
    )


_POP = r"(?P<nom>concurrents?|acteurs?)(?:\s+(?P<q>directs?|indirects?))?"
#: « six concurrents directs sur dix »
_N_SUR_M = re.compile(rf"\b(?P<n>{_NB})\s+{_POP}\s+sur\s+(?P<m>{_NB})\b", re.IGNORECASE)
#: « sur 11 acteurs analysés », « les 8 concurrents directs recensés », « sur
#: onze acteurs (huit directs, … » : la population ENTIÈRE du panel. Seul ce
#: qui suit le compte le dit — le participe du panel, « du panel », ou la
#: répartition entre parenthèses. « L'un des deux concurrents directs du
#: centre-ville », « les deux acteurs les plus proches » en sont des parties
#: (faux positifs relevés à la revue du 30/09/2026).
_ENTIERE = re.compile(
    rf"\b(?:sur|parmi|des|les)\s+(?:les\s+)?(?P<m>{_NB})\s+{_POP}"
    rf"(?=\s+(?:analys|recens|étudi|not[ée]|retenu|compar)\w*"
    rf"|\s+(?:du\s+panel|de\s+la\s+base)\b|\s*\(\s*{_NB}\s+(?:concurrents\s+)?directs)",
    re.IGNORECASE,
)
#: « Cinq concurrents directs publient… » : une partie de la population.
_PARTIE = re.compile(rf"\b(?P<n>{_NB})\s+{_POP}\b", re.IGNORECASE)
#: « La zone compte 23 concurrents directs, dont 8 étudiés » : le premier
#: compte est celui du marché, le second celui du panel.
_DONT = re.compile(rf"(?i)\bdont\s+{_NB}\b")
#: Une phrase qui parle du panel analysé, et pas du marché en général.
_PANEL = re.compile(r"(?i)\b(?:panel|base|analys\w*|recens\w*|comparaison|grille|not[ée]s?)\b")


def _population(qualificatif: str | None) -> str:
    q = (qualificatif or "").lower()
    if q.startswith("direct"):
        return "directs"
    if q.startswith("indirect"):
        return "indirects"
    return "total"


def _comptes_contre_la_base(
    document: Document, base: _Base, predicats: _Predicats,
) -> list[Constat]:
    from generation.memoire.controle import _ATTRIBUE_AU_CLIENT  # noqa: PLC0415

    grilles = _grilles(document)
    constats: list[Constat] = []
    for passage in _passages(document):
        texte = passage.texte
        bornes = _propositions(texte)
        for debut, fin in bornes:
            proposition = texte[debut:fin]
            if _ATTRIBUE_AU_CLIENT.search(proposition):
                continue
            couverts: list[tuple[int, int]] = []
            for m in _N_SUR_M.finditer(proposition):
                couverts.append((m.start(), m.end()))
                faute = _juger_n_sur_m(
                    m, proposition, base, grilles, predicats, passage.section,
                )
                if faute:
                    constats.append(Constat(
                        "comptage", passage.section, _court(proposition), faute,
                    ))
            for m in _ENTIERE.finditer(proposition):
                if any(a <= m.start("m") < b for a, b in couverts):
                    continue
                couverts.append((m.start(), m.end()))
                ecrit = _nombre(m.group("m"))
                attendus = base.attendus(m.group("nom").lower(), (m.group("q") or "").lower())
                if ecrit not in attendus:
                    constats.append(Constat(
                        "comptage", passage.section, _court(proposition),
                        f"« {m.group(0).strip()} » : la base de comparaison compte "
                        f"{base.libelle}. Écrire le compte de la base, "
                        f"« {_ecrire(min(attendus, key=lambda a: abs(a - ecrit)))} »."
                    ))
            # Un sous-ensemble plus grand que la base n'est une faute que s'il
            # parle du panel, et si la phrase ne distingue pas elle-même le
            # marché du panel (« dont 8 étudiés »).
            if not _PANEL.search(proposition) or _DONT.search(proposition):
                continue
            for m in _PARTIE.finditer(proposition):
                if any(a <= m.start() < b for a, b in couverts) or not m.group("q"):
                    continue
                ecrit = _nombre(m.group("n"))
                plafond = base.taille(_population(m.group("q")))
                if ecrit > plafond:
                    constats.append(Constat(
                        "comptage", passage.section, _court(proposition),
                        f"« {m.group(0).strip()} » : la base n'en compte que {plafond} "
                        f"({base.libelle}). Un sous-ensemble ne dépasse pas la base."
                    ))
    return constats


def _juger_n_sur_m(
    m: re.Match[str], proposition: str, base: _Base, grilles: list[_Grille],
    predicats: _Predicats, section: str,
) -> str:
    """Le motif d'un « N sur M » faux, ou rien s'il tient (ou ne se juge pas)."""
    n, total = _nombre(m.group("n")), _nombre(m.group("m"))
    nom, qualificatif = m.group("nom").lower(), (m.group("q") or "").lower()
    if not (qualificatif or _PANEL.search(proposition)):
        return ""
    population = _population(qualificatif)
    attendus = base.attendus(nom, qualificatif)
    ecrit = m.group(0).strip()
    if total not in attendus:
        bon = base.taille(population)
        conseil = f"écrire « sur {_ecrire(bon)} »"
        consensus = predicats.consensus.get(population)
        predicat = _predicat_de(proposition, m.end())
        if consensus is not None and predicat is not None:
            v_ferme, sections = consensus
            ailleurs = [s for s in sections if s != section] or sections
            compte = v_ferme if predicat == "ferme" else bon - v_ferme
            conseil = (
                f"ailleurs, le document compte {v_ferme} {nom} {qualificatif} sur {bon} avec "
                f"un prix ferme ({', '.join(ailleurs)}) : écrire « {_ecrire(compte)} "
                f"{nom} {qualificatif} sur {_ecrire(bon)} »".replace("  ", " ")
            )
        return (
            f"« {ecrit} » : « sur {m.group('m')} » ne correspond à aucun compte de la base "
            f"({base.libelle}) ; {conseil}."
        )
    recompte = _recompter_par_la_grille(proposition, total, grilles)
    if recompte is not None and recompte[0] != n:
        compte, grille, criteres, sens = recompte
        return (
            f"« {ecrit} » : la grille de notation ({grille}) en donne {compte} sur {total} "
            f"{sens} sur {' ou '.join('« ' + c + ' »' for c in criteres)}. Écrire "
            f"« {_ecrire(compte)} {nom} {qualificatif} sur {_ecrire(total)} »"
            .replace("  ", " ") + "."
        )
    return ""


# ── La grille de notation : le compte se refait ──────────────────────────────

_NOTE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*/\s*(\d+)\s*$")
#: La ligne du projet lui-même dans une grille : « ÉCLORE (positionnement visé) ».
_LIGNE_DU_PROJET = re.compile(r"(?i)\bvis[ée]e?\b|\bpositionnement\b|\(\s*projet|\bnotre\b")
_EN_DESSOUS = re.compile(
    r"(?i)\ben[- ]dessous\b|\bsous\s+(?:le|leur|son)\s+niveau|\binf[ée]rieur|"
    r"\bn['’]atteign\w*\s+pas|\bn['’]atteint\s+pas"
)
_AU_DESSUS = re.compile(r"(?i)\bau[- ]dessus\b|\bd[ée]pass\w*|\bsup[ée]rieur")


@dataclass(frozen=True)
class _Grille:
    section: str
    colonnes: tuple[str, ...]
    lignes: tuple[tuple[str, tuple[float | None, ...]], ...]
    projet: tuple[float | None, ...] | None


def _note(cellule: str) -> float | None:
    trouve = _NOTE.match(cellule)
    return float(trouve.group(1).replace(",", ".")) if trouve else None


def _grilles(document: Document) -> list[_Grille]:
    """Les tableaux de notation : une colonne d'acteurs, au moins deux colonnes de notes."""
    grilles: list[_Grille] = []
    for section in document.sections:
        for tableau in _tableaux_fusionnes(section):
            if est_un_encadre(tableau) or len(tableau.lignes) < 3:
                continue
            largeur = len(tableau.entetes)
            colonnes = [
                j for j in range(1, largeur)
                if sum(
                    1 for ligne in tableau.lignes if j < len(ligne) and _note(ligne[j]) is not None
                ) >= 0.8 * len(tableau.lignes)
            ]
            if len(colonnes) < 2:
                continue
            projet: tuple[float | None, ...] | None = None
            lignes: list[tuple[str, tuple[float | None, ...]]] = []
            for ligne in tableau.lignes:
                if not ligne:
                    continue
                notes = tuple(_note(ligne[j]) if j < len(ligne) else None for j in colonnes)
                libelle = texte_lisible(ligne[0])
                if _LIGNE_DU_PROJET.search(libelle):
                    projet = notes
                else:
                    lignes.append((libelle, notes))
            grilles.append(_Grille(
                section.numero,
                tuple(texte_lisible(tableau.entetes[j]) for j in colonnes),
                tuple(lignes),
                projet,
            ))
    return grilles


def _recompter_par_la_grille(
    proposition: str, taille: int, grilles: list[_Grille],
) -> tuple[int, str, list[str], str] | None:
    """Le compte refait sur la grille dont la population a la taille annoncée.

    Ne juge que ce qui se lit sans deviner : des critères nommés par leurs
    colonnes (« l'attention aux venues seules », « la combinaison des
    dimensions »), un sens (en dessous, au-dessus du niveau visé ou d'une note
    écrite), un connecteur (« ou » : l'un des critères suffit ; sinon tous).
    """
    candidates = [g for g in grilles if len(g.lignes) == taille]
    if not candidates:
        return None
    grille = candidates[0]
    mots = racines(proposition)
    criteres = [
        j for j, entete in enumerate(grille.colonnes)
        if (r := racines(entete)) and len(r & mots) >= min(2, len(r))
    ]
    if not criteres:
        return None
    ecrite = re.search(r"\b([1-9])\s*(?:/|sur)\s*([1-9]\d?)\b(?!\s+(?:concurrents|acteurs))",
                       proposition)
    if _EN_DESSOUS.search(proposition):
        sens, dessous = "en dessous", True
    elif _AU_DESSUS.search(proposition):
        sens, dessous = "au-dessus", False
    else:
        return None
    if ecrite is None and grille.projet is None:
        return None

    def seuil(j: int) -> float | None:
        if ecrite is not None:
            return float(ecrite.group(1))
        return grille.projet[j] if grille.projet else None

    un_suffit = re.search(r"\bou\b", proposition) is not None
    compte = 0
    for _, notes in grille.lignes:
        verdicts = []
        for j in criteres:
            note, limite = notes[j], seuil(j)
            if note is None or limite is None:
                return None
            verdicts.append(note < limite if dessous else note > limite)
        if (any(verdicts) if un_suffit else all(verdicts)):
            compte += 1
    reference = "de la note écrite" if ecrite is not None else "du niveau visé"
    return compte, grille.section, [grille.colonnes[j] for j in criteres], f"{sens} {reference}"


# ═════════════════════════════════════════════════════════════════════════════
# 2. Une même proportion, écrite partout pareil : prix ferme ou sur devis
# ═════════════════════════════════════════════════════════════════════════════

#: Deux prédicats complémentaires sur un panel : publier un prix, ou renvoyer
#: vers un devis. Ce que l'un compte, l'autre le déduit.
_FERME = re.compile(
    r"(?i)\bprix\s+(?:fermes?|affich\w*|publi\w*)|\btarifs?\s+(?:fermes?|affich\w*|publi\w*)"
    r"|\bpubli\w*\s+(?:un\s+|leurs?\s+|des\s+|le\s+)?(?:prix|tarifs?)|\bfermement\b"
)
_DEVIS = re.compile(r"(?i)\bsur\s+devis\b|\bsur\s+demande\b|\bdemande\s+de\s+devis\b")
_FRACTIONS = {
    "la moitié": 0.5, "un tiers": 1 / 3, "deux tiers": 2 / 3, "un quart": 0.25,
    "trois quarts": 0.75,
}
_FRACTION = re.compile(
    r"(?i)\b(?P<f>la\s+moitié|un\s+tiers|deux\s+tiers|un\s+quart|trois\s+quarts)\s+"
    r"(?:des|du|de\s+ces|de\s+leurs?)\s+(?P<nom>concurrents?|acteurs?|panel)"
    r"(?:\s+(?:concurrentiels?|concurrents?|de\s+concurrents))?(?:\s+(?P<q>directs?|indirects?))?"
)
_COMPTE_PREDICAT = re.compile(
    rf"(?i)\b(?P<n>{_NB})\s+(?:(?P<autres>autres)\s+)?(?:(?P<nom>concurrents?|acteurs?)"
    rf"(?:\s+(?P<q>directs?|indirects?))?(?:\s+sur\s+(?P<m>{_NB}))?|(?P<prix>prix|tarifs))\b"
)
#: « N prix » ne compte le panel que s'il en parle : « Sur le panel …, cinq
#: prix », « 5 prix fermes relevés dans le panel ». « Le projet affiche trois
#: prix fermes » compte les prix du PROJET (revue du 30/09/2026).
_PANEL_AVANT = re.compile(r"(?i)\b(?:panel|concurrents?|acteurs?)\b")
_PANEL_APRES = re.compile(r"(?i)^[^.;:]*?\b(?:relevés?|du\s+panel|dans\s+le\s+panel)\b")


def _predicat_de(proposition: str, position: int) -> str | None:
    """Le prédicat qui suit le compte ; à défaut, celui qui le précède."""
    apres = proposition[position:]
    candidats = [(m.start(), "ferme") for m in _FERME.finditer(apres)]
    candidats += [(m.start(), "devis") for m in _DEVIS.finditer(apres)]
    if candidats:
        return min(candidats)[1]
    avant = proposition[:position]
    candidats = [(m.end(), "ferme") for m in _FERME.finditer(avant)]
    candidats += [(m.end(), "devis") for m in _DEVIS.finditer(avant)]
    return max(candidats)[1] if candidats else None


@dataclass(frozen=True)
class _Mention:
    section: str
    extrait: str
    population: str
    #: Combien de la population publient un prix ferme, selon cette phrase.
    ferme: float
    exacte: bool


@dataclass
class _Predicats:
    mentions: list[_Mention]
    #: Par population : le compte « prix ferme » que la majorité écrit, et où.
    consensus: dict[str, tuple[int, list[str]]]


def _predicats(document: Document, base: _Base | None) -> _Predicats:
    mentions: list[_Mention] = []
    for passage in _passages(document):
        texte = passage.texte
        for debut, fin in _propositions(texte):
            proposition = texte[debut:fin]
            if not re.search(r"(?i)\b(?:concurrents?|acteurs?|panel)\b", proposition):
                continue
            for m in _COMPTE_PREDICAT.finditer(proposition):
                # « 5 prix fermes » : le prédicat est dans le nom compté lui-même.
                predicat = _predicat_de(
                    proposition, m.start("prix") if m.group("prix") else m.end()
                )
                if predicat is None:
                    continue
                if m.group("prix"):
                    if not (
                        _PANEL_AVANT.search(proposition[:m.start()])
                        or _PANEL_APRES.match(proposition[m.end():])
                    ):
                        continue
                    q = re.search(r"(?i)\bconcurrents?\s+(directs?|indirects?)", proposition)
                    population = _population(q.group(1) if q else None)
                else:
                    population = _population(m.group("q"))
                if m.group("m"):
                    if base is None or _nombre(m.group("m")) != base.taille(population):
                        continue  # une base fausse : jugée par le compte, pas ici
                taille = base.taille(population) if base else None
                n = _nombre(m.group("n"))
                if predicat == "ferme":
                    ferme: float = n
                elif taille is not None:
                    ferme = taille - n
                else:
                    continue
                mentions.append(_Mention(
                    passage.section, _court(proposition), population, ferme, exacte=True,
                ))
            for m in _FRACTION.finditer(proposition):
                predicat = _predicat_de(proposition, m.end())
                population = _population(m.group("q"))
                if predicat is None or base is None:
                    continue
                taille = base.taille(population)
                part = _FRACTIONS[re.sub(r"\s+", " ", m.group("f").lower())] * taille
                mentions.append(_Mention(
                    passage.section, _court(proposition), population,
                    part if predicat == "ferme" else taille - part, exacte=False,
                ))
    consensus: dict[str, tuple[int, list[str]]] = {}
    for population in {m.population for m in mentions}:
        exactes = [m for m in mentions if m.population == population and m.exacte]
        appuis: dict[float, set[str]] = {}
        for mention in exactes:
            appuis.setdefault(mention.ferme, set()).add(mention.section)
        if not appuis:
            continue
        rang = sorted(appuis.items(), key=lambda item: -len(item[1]))
        if len(rang[0][1]) >= 2 and (len(rang) == 1 or len(rang[0][1]) > len(rang[1][1])):
            consensus[population] = (int(rang[0][0]), sorted(rang[0][1], key=_ordre))
    return _Predicats(mentions, consensus)


def _ordre(section: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", section)) or (0,)


def _proportions_discordantes(predicats: _Predicats, base: _Base | None) -> list[Constat]:
    """Une proportion qui contredit le compte que le document écrit partout ailleurs."""
    constats: list[Constat] = []
    for mention in predicats.mentions:
        consensus = predicats.consensus.get(mention.population)
        if consensus is None:
            continue
        v_ferme, sections = consensus
        if abs(mention.ferme - v_ferme) <= 0.5:
            continue
        ailleurs = [s for s in sections if s != mention.section] or sections
        taille = base.taille(mention.population) if base else None
        devis = f", soit {taille - v_ferme} sur devis" if taille is not None else ""
        sur = f" sur {taille}" if taille is not None else ""
        constats.append(Constat(
            "comptage", mention.section, mention.extrait,
            f"Le document compte ailleurs {v_ferme}{sur} concurrents avec un prix ferme "
            f"({', '.join(ailleurs)}){devis} : cette proportion le contredit. Écrire le "
            "même compte partout."
        ))
    return constats


# ═════════════════════════════════════════════════════════════════════════════
# 3. « N formats », « N familles » : contre le tableau voisin
# ═════════════════════════════════════════════════════════════════════════════

#: Les noms qu'un document compte, et qu'un tableau liste ligne à ligne.
#: Vocabulaire générique de la structure d'une étude (règle 4 : la classe).
_NOMS_COMPTES = frozenset(racines(
    "formats univers leviers piliers segments étapes axes critères prestations postes "
    "besoins risques indicateurs canaux phases paliers signaux mécanismes dispositifs "
    "horizons offres fournisseurs profils scénarios volets jalons demandes obligations "
    "actions gammes cibles services produits"
))
#: Les noms qui REGROUPENT : trois familles de fournisseurs peuvent en contenir
#: cinq, à condition que le tableau dise lesquels vont ensemble.
_NOMS_DE_GROUPE = frozenset(racines("familles catégories groupes masses types"))

#: « Trois univers, huit formats », « deux critères sur quatre ». Seul « sur M »
#: désigne un TOUT : « les trois actions de la première année », « les deux
#: risques du lancement » sont des parties d'un tableau plus long (revue du
#: 30/09/2026). Un compte annoncé ne se juge donc que s'il DÉPASSE le tableau.
_ANNONCE = re.compile(
    rf"(?i)\b(?P<n>{_NB})\s+(?:(?:grandes?|principales?|principaux|nouvelles?|nouveaux)\s+)?"
    r"(?P<nom>[^\W\d_]{3,})(?:\s+(?:de|d['’])\s*(?P<complement>[^\W\d_]{3,}))?"
    rf"(?:\s+sur\s+(?P<m>{_NB}))?"
)


def _racine(mot: str) -> str:
    return next(iter(racines(mot)), "")


@dataclass(frozen=True)
class _Colonne:
    section: str
    entete: str
    #: Les valeurs distinctes, telles que le tableau les écrit (casse comprise).
    valeurs: tuple[str, ...]
    tableau: Tableau


def _colonnes(sections: Iterable[Section]) -> list[_Colonne]:
    colonnes: list[_Colonne] = []
    for section in sections:
        for tableau in _tableaux_fusionnes(section):
            if est_un_encadre(tableau) or len(tableau.lignes) < 2:
                continue
            for j, entete in enumerate(tableau.entetes):
                distinctes: dict[str, str] = {}
                for ligne in tableau.lignes:
                    cellule = texte_lisible(ligne[j]) if j < len(ligne) else ""
                    if cellule.strip(" —-"):
                        distinctes.setdefault(cellule.lower(), cellule)
                colonnes.append(_Colonne(
                    section.numero, texte_lisible(entete), tuple(distinctes.values()), tableau,
                ))
    return colonnes


def _colonne_de(colonnes: list[_Colonne], racine: str) -> _Colonne | None:
    return next((c for c in colonnes if racine in racines(c.entete)), None)


def _colonnes_du_tableau(colonne: _Colonne) -> list[_Colonne]:
    """Toutes les colonnes du tableau qui porte `colonne`."""
    return _colonnes([Section(colonne.section, "", None, tableaux=[colonne.tableau])])


def _comptes_contre_les_tableaux(document: Document) -> list[Constat]:
    constats: list[Constat] = []
    sections = document.sections
    for rang, section in enumerate(sections):
        memes = _colonnes([section])
        # L'accroche d'un chapitre annonce ce que sa première section montre.
        accroche = section.numero.startswith("ch.")
        suivantes = _colonnes(sections[rang + 1:rang + 2]) if accroche else []
        textes = [section.titre, *section.paragraphes] + [
            c for t in section.tableaux if est_un_encadre(t) for c in t.cellules()
        ]
        for brut in textes:
            texte = texte_lisible(brut)
            if RENVOI.match(texte):
                # « Figure présentée au chapitre 3 — … sur les cinq critères » :
                # le compte est celui de la figure citée, pas du tableau d'ici.
                continue
            for m in _ANNONCE.finditer(texte):
                constat = _juger_une_annonce(m, texte, section, memes, suivantes)
                if constat is not None:
                    constats.append(constat)
    return constats


def _juger_une_annonce(
    m: re.Match[str], texte: str, section: Section,
    memes: list[_Colonne], suivantes: list[_Colonne],
) -> Constat | None:
    nom = _racine(m.group("nom"))
    groupe = nom in _NOMS_DE_GROUPE
    if not (groupe or nom in _NOMS_COMPTES):
        return None
    avant, apres = texte[:m.start()], texte[m.end():]
    # « 2 à 3 partenariats » : une fourchette, pas un compte. « Trois leviers de
    # sécurisation par risque » : un compte PAR ligne, pas un total.
    if re.search(rf"(?i)\b{_NB}\s*(?:à|-)\s*$", avant):
        return None
    if re.match(r"^(?:\s+\S+){0,2}\s+par\b", apres):
        return None
    n = _nombre(m.group("n"))
    # « deux critères sur quatre » : c'est « quatre », le tout, qui se compare
    # au tableau — à l'égalité près.
    total = _nombre(m.group("m")) if m.group("m") else None
    entier = total is not None
    annonce = m.group(0).strip()
    compte_annonce = total if total is not None else n

    if groupe:
        colonne = _colonne_de(memes, nom) or _colonne_de(suivantes, nom)
        if colonne is not None:
            lignes = len(colonne.valeurs)
            if compte_annonce > lignes or (entier and compte_annonce != lignes):
                return _constat_d_annonce(section, annonce, colonne, compte_annonce, grave=True)
            return None
        complement = _racine(m.group("complement") or "")
        colonne = _colonne_de(memes, complement) if complement else None
        if colonne is None:
            return None
        lignes = len(colonne.valeurs)
        if lignes > compte_annonce:
            # Le tableau range-t-il ses lignes en autant de familles ? Une
            # colonne à N valeurs distinctes dit lesquelles vont ensemble.
            for autre in _colonnes_du_tableau(colonne):
                if len(autre.valeurs) == compte_annonce:
                    return None
            return _constat_d_annonce(section, annonce, colonne, compte_annonce, grave=False,
                                      regroupe=True)
        if lignes < compte_annonce:
            return _constat_d_annonce(section, annonce, colonne, compte_annonce, grave=True)
        return None

    colonne = _colonne_de(memes, nom) or _colonne_de(suivantes, nom)
    if colonne is None:
        return None
    lignes = len(colonne.valeurs)
    if compte_annonce > lignes or (entier and compte_annonce != lignes):
        return _constat_d_annonce(section, annonce, colonne, compte_annonce, grave=True)
    return None


def _constat_d_annonce(
    section: Section, annonce: str, colonne: _Colonne, annonce_n: int, *,
    grave: bool, regroupe: bool = False,
) -> Constat:
    lignes = len(colonne.valeurs)
    exemples = " ; ".join(_court(v, 40) for v in colonne.valeurs[:4])
    if lignes > 4:
        exemples += " ; …"
    lieu = "ici" if colonne.section == section.numero else f"en {colonne.section}"
    if regroupe:
        conseil = (
            f"le tableau ({lieu}) liste {lignes} lignes « {colonne.entete} » ({exemples}) "
            f"sans dire lesquelles forment les {annonce_n} groupes annoncés : écrire le "
            "compte des lignes, ou ranger chaque ligne dans son groupe."
        )
    else:
        conseil = (
            f"le tableau ({lieu}) en liste {lignes} dans la colonne « {colonne.entete} » "
            f"({exemples}) : écrire « {_ecrire(lignes)} », ou compléter le tableau."
        )
    return Constat(
        "comptage", section.numero, annonce, f"« {annonce} » : {conseil}", grave=grave,
    )


# ═════════════════════════════════════════════════════════════════════════════
# 4. Une décision écrite de deux façons
# ═════════════════════════════════════════════════════════════════════════════

_MOIS = (
    "janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|"
    "novembre|décembre|decembre"
)
_DATE = re.compile(
    r"(?i)(?:\b(?P<qualif>début|debut|fin|courant|milieu|mi-)\s*(?:d['’]année\s+)?"
    r"|\b(?P<saison>printemps|été|automne|hiver)\s+"
    rf"|\b(?P<mois>{_MOIS})\s+)?"
    r"(?<![\d,.])(?P<annee>20[2-4]\d)\b(?![,.]?\d)"
    r"|\bphase\s+(?P<phase>[1-9])\b"
)
_INTERVALLE = re.compile(
    r"(?i)\b20[2-4]\d\s*(?:[-–]|à|au|et)\s*20[2-4]\d\b|\bentre\s+20[2-4]\d\s+et\s+20[2-4]\d\b"
)
_PHASE_DATEE = re.compile(r"(?i)\bphase\s+([1-9])\s*\(\s*(20[2-4]\d)\s*\)")


@dataclass(frozen=True)
class _Date:
    annee: int | None
    precision: str
    debut: int
    fin: int
    #: Tel qu'écrit : « phase 3 », « à l'automne 2031 », « Fin 2031 ».
    ecrit: str = ""

    def dite(self) -> str:
        """La forme comparable : même année ET même précision, ou une autre date."""
        if self.annee is None:
            return self.precision
        return f"{self.precision} {self.annee}".strip()


def _dates(texte: str, phases: dict[int, int]) -> list[_Date]:
    exclues = _spans(_INTERVALLE, texte)
    dates: list[_Date] = []
    for m in _DATE.finditer(texte):
        if any(a <= m.start("annee" if m.group("annee") else 0) < b for a, b in exclues):
            continue
        ecrit = m.group(0).strip()
        if m.group("phase"):
            numero = int(m.group("phase"))
            suite = texte[m.end():m.end() + 12]
            if re.match(r"\s*\(\s*20", suite):
                continue  # « Phase 3 (2031) » : un intitulé qui DÉFINIT la phase
            annee = phases.get(numero)
            precision = "" if annee is not None else f"phase {numero}"
            dates.append(_Date(annee, precision, m.start(), m.end(), ecrit))
            continue
        precision = (m.group("qualif") or m.group("saison") or m.group("mois") or "").lower()
        precision = {"debut": "début", "mi-": "mi", "milieu": "mi", "aout": "août",
                     "fevrier": "février", "decembre": "décembre"}.get(precision, precision)
        dates.append(_Date(int(m.group("annee")), precision, m.start(), m.end(), ecrit))
    return dates


def _phases(document: Document) -> dict[int, int]:
    """« Phase 3 (2031) » : l'année de chaque phase, telle que le document la définit."""
    phases: dict[int, int] = {}
    for passage in _passages(document):
        for m in _PHASE_DATEE.finditer(passage.texte):
            phases.setdefault(int(m.group(1)), int(m.group(2)))
    return phases


def _plus_proche(dates: list[_Date], position: int) -> _Date | None:
    """La date la plus proche du mot qui la porte ; deux à égale distance : aucune."""
    if not dates:
        return None
    distances = sorted(
        (min(abs(d.debut - position), abs(d.fin - position)), rang)
        for rang, d in enumerate(dates)
    )
    if len(distances) > 1 and distances[0][0] == distances[1][0]:
        if dates[distances[0][1]].dite() != dates[distances[1][1]].dite():
            return None
    return dates[distances[0][1]]


def _une(dates: list[_Date]) -> _Date | None:
    """La date d'un texte, s'il n'en porte qu'une (au sens de sa lecture)."""
    distinctes = {d.dite(): d for d in dates}
    return next(iter(distinctes.values())) if len(distinctes) == 1 else None


def _date_du_sujet(
    passage: _Passage, position: int, phases: dict[int, int],
) -> tuple[_Date, str] | None:
    """La date qui accompagne le sujet, et le texte où le lecteur la lit.

    Dans sa proposition, puis sa phrase ; dans un tableau, la date de la ligne
    (« 2031 | Quitte son poste »), de la colonne (« 2031 » en en-tête), ou la
    seule date d'une autre cellule (« Départ du poste salarié | Fin 2031… »).
    """
    texte = passage.texte
    for bornes in (_propositions(texte), _spans(_PHRASES, texte)):
        debut, fin = _borne_autour(bornes, position)
        dates = _dates(texte[debut:fin], phases)
        if dates:
            date = _plus_proche(dates, position - debut)
            return (date, texte[debut:fin]) if date is not None else None
    if passage.ligne is None:
        return None
    candidats: list[str] = []
    if passage.colonne > 0:
        candidats.append(passage.ligne[0])
    if 0 <= passage.colonne < len(passage.entetes):
        candidats.append(passage.entetes[passage.colonne])
    for cellule in candidats:
        date = _une(_dates(cellule, phases))
        if date is not None:
            return date, texte
    autres = [
        (d, cellule) for j, cellule in enumerate(passage.ligne) if j != passage.colonne
        for d in _dates(cellule, phases)
    ]
    date = _une([d for d, _ in autres])
    if date is None:
        return None
    # La cellule qui porte la date est celle que le lecteur doit corriger.
    return date, next(cellule for d, cellule in autres if d.dite() == date.dite())


@dataclass(frozen=True)
class _Version:
    """Ce qu'une section écrit d'une décision."""

    sujet: str
    section: str
    #: La forme comparable : « 2031 » pour « phase 3 » quand la phase 3 est 2031.
    valeur: str
    extrait: str
    #: La forme écrite, quand elle diffère de la forme comparable.
    ecrit: str = ""

    def dite(self) -> str:
        if self.ecrit and self.ecrit.lower() != self.valeur.lower():
            return f"{self.ecrit} ({self.valeur})"
        return self.valeur


def _contradictions(
    versions: list[_Version], reference: str | None = None, *, libelle: str,
    consigne: str = "",
) -> list[Constat]:
    """Une décision, plusieurs valeurs : chaque version minoritaire est signalée.

    La référence de la mémoire tranche quand elle existe ; sinon la valeur que
    le plus de sections écrivent ; sans majorité, toutes les versions — le
    lecteur ne peut pas savoir laquelle croire.
    """
    par_valeur: dict[str, set[str]] = {}
    ecrites: dict[str, str] = {}
    for version in versions:
        par_valeur.setdefault(version.valeur, set()).add(version.section)
        ecrites.setdefault(version.valeur, version.dite())
    if reference is None and len(par_valeur) < 2:
        return []
    if reference is not None:
        retenue: str | None = reference
    else:
        rang = sorted(par_valeur.items(), key=lambda item: -len(item[1]))
        retenue = rang[0][0] if len(rang[0][1]) > len(rang[1][1]) else None
    constats: list[Constat] = []
    vus: set[tuple[str, str]] = set()
    for version in versions:
        if version.valeur == retenue or (version.section, version.extrait) in vus:
            continue
        vus.add((version.section, version.extrait))
        autres = " ; ".join(
            f"« {ecrites[valeur]} » ({', '.join(sorted(sections, key=_ordre))})"
            for valeur, sections in par_valeur.items() if valeur != version.valeur
        )
        if retenue is not None:
            source = "la décision du projet" if reference is not None else "le reste du document"
            fin = f" Écrire « {retenue} », comme {source}."
        else:
            fin = " Une seule valeur pour une même décision : trancher, puis l'écrire partout."
        constats.append(Constat(
            "decision", version.section, version.extrait,
            f"{libelle} : « {version.dite()} » ici, {autres or 'une autre valeur'} "
            f"ailleurs.{fin}{consigne}",
        ))
    return constats


# ── Le départ du poste (et tout événement daté du cadrage) ───────────────────

_DEPART = re.compile(
    r"(?i)\b(?:quitt\w*\s+(?:son|le|mon|leur)\s+(?:poste|emploi)|d[ée]part\s+du\s+poste"
    r"|d[ée]mission\s+(?:de\s+son|du)\s+(?:poste|emploi))"
)


def _dates_du_depart(document: Document, reference: Reference) -> list[Constat]:
    phases = _phases(document)
    versions: list[_Version] = []
    for passage in _passages(document):
        for m in _DEPART.finditer(passage.texte):
            trouvee = _date_du_sujet(passage, m.start(), phases)
            if trouvee is None:
                continue
            date, ou = trouvee
            versions.append(_Version(
                "depart", passage.section, date.dite(), _court(ou), date.ecrit,
            ))
    attendue: str | None = None
    if reference.memoire is not None:
        cadrees = set()
        for decision in reference.memoire.decisions:
            if decision.source != "brief":
                continue
            valeur = texte_lisible(decision.valeur)
            for m in _DEPART.finditer(valeur):
                trouvee = _date_du_sujet(_Passage("", valeur), m.start(), phases)
                if trouvee is not None:
                    cadrees.add(trouvee[0].dite())
        if len(cadrees) == 1:
            attendue = cadrees.pop()
    return _contradictions(
        versions, attendue, libelle="Le départ du poste salarié est daté",
        consigne=" Même année, même précision : un « fin » ou un « courant » ajouté est "
                 "une autre date.",
    )


# ── Le lancement d'une offre nommée ──────────────────────────────────────────

#: Ce qui date un LANCEMENT, et rien d'autre. « Premier(s) » seulement devant une
#: session, un format ou un nom propre (« les premières » suivi du nom de
#: l'offre) : « les deux premières années », « les 12 premiers mois » ne lancent
#: rien (faux positifs mesurés sur les encadrés d'ÉCLORE, 30/09/2026). Ni « à
#: partir de », ni « à compter de » seuls : « revalorisé de 3 % à partir de
#: 2030 » date un prix (revue du même jour) ; ni « ouvrés ».
_LANCEMENT = re.compile(
    r"\b(?:(?i:lancements?|lanc[ée]e?s?|ouvertures?|ouvrir|ouvre|ouvrent|ouvrira|ouvriront"
    r"|ouverte?s?|introductions?|introduite?s?|démarrages?)\b"
    r"|(?i:premi[èe]re?s?)\s+(?:(?i:sessions?|parcours|week-?ends?|ateliers?|séjours?"
    r"|éditions?|soirées?|cercles?)\b|[A-ZÀ-Ý]\w+))"
)
#: Une phrase de prix date une revalorisation, pas un lancement.
_DE_PRIX = re.compile(r"(?i)\b(?:prix|tarifs?|revaloris\w*)\b")
_FORMAT_DECLINE = r"(?:week-?ends?|parcours|ateliers?|soirées?|cercles?|séjours?|formules?)"


def _offres(document: Document) -> dict[str, re.Pattern[str]]:
    """Les offres nommées, telles que le tableau les écrit : la première colonne
    d'un tableau « Univers », « Offre », « Gamme »…

    La clé est le nom ÉCRIT (il sert au libellé du constat) ; le motif accepte
    le singulier et le pluriel.
    """
    offres: dict[str, re.Pattern[str]] = {}
    tetes = racines("univers offre gamme activité")
    for section in document.sections:
        for tableau in _tableaux_fusionnes(section):
            if est_un_encadre(tableau) or not tableau.entetes:
                continue
            if not racines(tableau.entetes[0]) & tetes:
                continue
            for ligne in tableau.lignes:
                nom = texte_lisible(ligne[0]) if ligne else ""
                if not nom or len(nom.split()) > 2 or not nom[:1].isupper():
                    continue
                base = re.sub(r"s$", "", nom)
                if not any(re.sub(r"s$", "", connu) == base for connu in offres):
                    offres[nom] = re.compile(rf"\b{re.escape(base)}s?\b")
    return offres


def _offres_citees(texte: str, offres: dict[str, re.Pattern[str]]) -> list[tuple[str, bool]]:
    """Les offres d'un texte, chacune avec « déclinaison » (« week-end [Offre] ») ou non."""
    citees: list[tuple[str, bool]] = []
    for nom, motif in offres.items():
        for m in motif.finditer(texte):
            avant, apres = texte[max(0, m.start() - 20):m.start()], texte[m.end():m.end() + 16]
            decline = bool(
                re.search(rf"(?i){_FORMAT_DECLINE}\s+(?:des?\s+|d['’])?$", avant)
                or re.match(rf"(?i)^\s*[—–-]\s*{_FORMAT_DECLINE}", apres)
            )
            citees.append((nom, decline))
    return citees


def _lancement_dans_le_passage(
    passage: _Passage, offres: dict[str, re.Pattern[str]], phases: dict[int, int],
) -> _Version | None:
    """Une phrase du passage porte à elle seule l'offre, le mot du lancement et sa date.

    La PHRASE, pas le passage : un encadré entier (« Opportunité — … Limite —
    … Décision — … ») est un seul passage, et une date de sa première phrase
    ne date pas le lancement nommé dans la dernière.
    """
    for phrase in _PHRASES.finditer(passage.texte):
        texte = phrase.group(0)
        citees = _offres_citees(texte, offres)
        noms = {nom for nom, _ in citees}
        lance = _LANCEMENT.search(texte)
        if lance is None or len(noms) != 1 or any(decline for _, decline in citees):
            continue
        if _DE_PRIX.search(texte):
            continue
        date = _plus_proche(_dates(texte, phases), lance.start())
        if date is not None:
            return _Version(noms.pop(), passage.section, date.dite(), _court(texte), date.ecrit)
    return None


def _lancement_dans_la_ligne(
    passage: _Passage, offres: dict[str, re.Pattern[str]], phases: dict[int, int],
) -> _Version | None:
    """La ligne entière : l'offre dans une cellule, « Non, phase 3 » dans une autre.

    La cellule datée doit parler du lancement, par elle-même (« avant le
    lancement des premiers parcours à l'automne ») ou par son en-tête
    (« Priorité au lancement ») ; la ligne ne doit nommer qu'une offre, et
    jamais une déclinaison (« Week-end [Offre] (à partir de [année]) » date le
    week-end, pas l'offre).
    """
    if passage.ligne is None:
        return None
    entete = passage.entetes[passage.colonne] if passage.colonne < len(passage.entetes) else ""
    if not (_LANCEMENT.search(passage.texte) or _LANCEMENT.search(entete)):
        return None
    if _DE_PRIX.search(passage.texte) or _DE_PRIX.search(entete):
        return None
    if any(decline for _, decline in _offres_citees(passage.texte, offres)):
        return None
    dates = _dates(passage.texte, phases)
    if len({d.dite() for d in dates}) != 1:
        return None
    noms = {nom for cellule in passage.ligne for nom, _ in _offres_citees(cellule, offres)}
    if len(noms) != 1:
        return None
    return _Version(noms.pop(), passage.section, dates[0].dite(), passage.texte, dates[0].ecrit)


def _dates_de_lancement(document: Document) -> list[Constat]:
    offres = _offres(document)
    if not offres:
        return []
    phases = _phases(document)
    versions: list[_Version] = []
    lignes_vues: set[tuple[str, tuple[str, ...]]] = set()
    for passage in _passages(document):
        cle = (passage.section, passage.ligne or ())
        if passage.ligne is not None and cle in lignes_vues:
            continue
        version = _lancement_dans_le_passage(passage, offres, phases) or (
            _lancement_dans_la_ligne(passage, offres, phases)
        )
        if version is None:
            continue
        versions.append(version)
        if passage.ligne is not None:
            lignes_vues.add(cle)
    constats: list[Constat] = []
    for offre in sorted({v.sujet for v in versions}):
        constats += _contradictions(
            [v for v in versions if v.sujet == offre],
            libelle=f"Le lancement de l'offre « {offre} » est daté",
        )
    return constats


# ── L'apport : engagé, ou à confirmer ────────────────────────────────────────

#: L'apport du porteur de projet — pas un apport en nature, ni un « apport
#: complémentaire » hypothétique, qui sont d'autres sujets.
_APPORT = re.compile(
    r"(?i)(?<!second\s)(?<!nouvel\s)(?<!autre\s)\bapports?(?:\s+personnels?)?\b"
    r"(?!\s+(?:en\s+nature|complémentaires?|supplémentaires?))"
)
#: Ce qui dit l'apport INCERTAIN — mais seulement quand c'est l'apport qu'il
#: qualifie : « l'apport … reste une hypothèse », « sous réserve de confirmer
#: l'apport ». « L'apport et les hypothèses de fréquentation », « un reste à
#: vivre suffisant » parlent d'autre chose (revue du 30/09/2026).
_INCERTAIN_APRES = re.compile(
    r"(?i)^[^.;:,]{0,30}?(?:\b(?:reste|est|demeure|sera|restera)\s+(?:encore\s+)?"
    r"(?:une\s+|l['’]une\s+des\s+)?(?:hypoth[èe]ses?|à\s+(?:confirmer|sécuriser|verser|valider"
    r"|mobiliser)|non\s+(?:encore\s+)?(?:confirmée?|engagée?|versée?|acquise?))"
    r"|\bn['’](?:est|a)\s+pas\s+(?:encore\s+)?(?:été\s+)?(?:confirm|engag|vers|acquis|sécuris))"
)
_INCERTAIN_AVANT = re.compile(
    r"(?i)(?:\bsous\s+réserve\s+(?:de\s+\w+\s+)?|\b(?:à|reste\s+à)\s+(?:confirmer|sécuriser"
    r"|verser|valider|mobiliser)\s+)(?:l['’]|cet?\s+|son\s+|leur\s+)?$"
)
#: Ce qui le dit ACQUIS, collé à lui : le participe, accent compris —
#: « Confirme qu'aucun apport… » (un verbe conjugué) n'est pas « confirmé ».
_ENGAGE_APRES = re.compile(
    r"(?i)^[^.;:,]{0,30}?\b(?:est|a\s+été|déjà|sont)?\s*(?:engagée?s?|acquise?s?|versée?s?"
    r"|confirmée?s?|sécurisée?s?)(?!\w)"
)
_STATUT = re.compile(r"(?i)statut|état|situation")


def _statut_de_cellule(cellule: str) -> str | None:
    """Une cellule « Statut » : « Engagé au lancement », « À confirmer »."""
    if re.search(r"(?i)\bà\s+confirmer\b|\bhypoth[èe]se|\bnon\s+(?:encore\s+)?engag", cellule):
        return "à confirmer"
    if re.match(r"(?i)^\s*(?:engagée?s?|acquise?s?|versée?s?|confirmée?s?)\b", cellule):
        return "engagé"
    return None


def _statut_autour(texte: str, debut: int, fin: int) -> str | None:
    """Le statut que la proposition donne à L'APPORT, cité en [debut, fin)."""
    apres, avant = texte[fin:], texte[:debut]
    if _INCERTAIN_APRES.match(apres) or _INCERTAIN_AVANT.search(avant):
        return "à confirmer"
    if _ENGAGE_APRES.match(apres):
        return "engagé"
    return None


def _statuts_de_l_apport(document: Document) -> list[Constat]:
    versions: list[_Version] = []
    for passage in _passages(document):
        texte = passage.texte
        if passage.ligne is not None and passage.colonne == 0 and _APPORT.match(texte):
            for j, cellule in enumerate(passage.ligne[1:], start=1):
                if j < len(passage.entetes) and _STATUT.search(passage.entetes[j]):
                    statut = _statut_de_cellule(cellule)
                    if statut:
                        versions.append(_Version("apport", passage.section, statut, cellule))
            continue
        bornes = _propositions(texte)
        for m in _APPORT.finditer(texte):
            debut, fin = _borne_autour(bornes, m.start())
            statut = _statut_autour(texte[debut:fin], m.start() - debut, m.end() - debut)
            if statut:
                versions.append(_Version("apport", passage.section, statut,
                                         _court(texte[debut:fin])))
    # Une section qui dit les deux nuance (« chiffré, mais à confirmer ») : elle
    # ne tranche pas, elle ne se compte pas.
    par_section: dict[str, set[str]] = {}
    for version in versions:
        par_section.setdefault(version.section, set()).add(version.valeur)
    nettes = [v for v in versions if len(par_section[v.section]) == 1]
    return _contradictions(
        nettes, libelle="L'apport personnel est présenté",
        consigne=" Un apport engagé n'est plus une hypothèse, et une hypothèse ne se "
                 "présente pas comme engagée.",
    )


# ── Les fournisseurs : payés avant, ou après ─────────────────────────────────

_FOURNISSEURS = re.compile(r"(?i)\b(?:fournisseurs?|salles?|intervenantes?|lieux|prestataires?)\b")
_ACOMPTE = re.compile(r"(?i)\bacomptes?\b")
#: L'argent que l'entreprise REÇOIT : l'acompte de la cliente, à la réservation
#: ou « demandé à la commande ». L'autre sens du même mot. Le participe est lu
#: COLLÉ à l'acompte : « le chiffre d'affaires encaissé » d'une autre cellule
#: de la ligne ne dit rien de qui paie l'acompte.
_DE_LA_CLIENTE = re.compile(
    r"(?i)\bà\s+la\s+réservation\b|\bclientes?\b|\bparticipantes?\b"
    r"|\bacomptes?\b[^.;|]{0,40}?\b(?:demandée?s?|encaissée?s?|perçue?s?|reçue?s?)\b"
)
_PAR_L_ENTREPRISE = re.compile(
    r"(?i)\b(?:trésorerie|réserve|financ\w*|couvr\w*|absorb\w*|amort\w*)"
)
_REGLEMENT = re.compile(r"(?i)\b(?:réglé|payé|paiement|règlement|décaiss)\w*")
_APRES = re.compile(
    r"(?i)\baprès\b|\bau\s+moment\b|\bune\s+fois\b|\bà\s+réception\b|\bà\s+l['’]issue\b"
)
#: « Le solde est réglé après la livraison » complète un acompte versé avant :
#: c'est une seule politique, pas deux.
_SOLDE = re.compile(r"(?i)\bsoldes?\b|\breste\s+(?:dû|à\s+payer|à\s+régler)")

_AVANT_LA_PRESTATION = "payés en partie avant la prestation (acomptes)"
_APRES_LA_PRESTATION = "payés après la prestation"


def _moment_du_paiement(unite: str) -> tuple[str, re.Pattern[str]] | None:
    """Avant (des acomptes que l'entreprise verse) ou après la prestation."""
    if _DE_LA_CLIENTE.search(unite):
        return None  # l'acompte, le paiement de la cliente : l'autre sens
    if _ACOMPTE.search(unite) and (_FOURNISSEURS.search(unite) or _PAR_L_ENTREPRISE.search(unite)):
        return _AVANT_LA_PRESTATION, _ACOMPTE
    if (
        _FOURNISSEURS.search(unite) and _REGLEMENT.search(unite) and _APRES.search(unite)
        and not _SOLDE.search(unite)
    ):
        return _APRES_LA_PRESTATION, _APRES
    return None


def _calendrier_des_fournisseurs(document: Document) -> list[Constat]:
    versions: list[_Version] = []
    lignes_vues: set[tuple[str, tuple[str, ...]]] = set()
    for passage in _passages(document):
        if passage.ligne is not None:
            if (passage.section, passage.ligne) in lignes_vues:
                continue
            lignes_vues.add((passage.section, passage.ligne))
            unites = [" | ".join(passage.ligne)]
        else:
            unites = [p.group(0) for p in _PHRASES.finditer(passage.texte)]
        for unite in unites:
            moment = _moment_du_paiement(unite)
            if moment is None:
                continue
            valeur, repere = moment
            extrait = unite if passage.ligne is None else next(
                (c for c in passage.ligne if repere.search(c)), passage.texte
            )
            versions.append(_Version("fournisseurs", passage.section, valeur, _court(extrait)))
    return _contradictions(
        versions, libelle="Les fournisseurs sont dits",
        consigne=" Le besoin en fonds de roulement et la réserve de trésorerie en dépendent.",
    )


# ── La TVA : la règle, pas une approximation ─────────────────────────────────

_TVA = re.compile(r"\bTVA\b")
_IMMEDIAT = re.compile(
    r"(?i)\bdès\s+(?:que|qu['’]|le\s+(?:dépassement|franchissement)|son\s+(?:dépassement"
    r"|franchissement)|le\s+premier\s+euro)|\bimmédiatement\b"
    r"|\bau\s+(?:franchissement|dépassement)\s+(?:du|de\s+ce)\s+seuil\b"
)
_SEUIL_DE_FRANCHISE = re.compile(r"(?i)\bseuil\s+de\s+franchise\b")
_REGLE_EXACTE = re.compile(
    r"(?i)\bmajor[ée]|\b1er\s+janvier\b|\bpremier\s+janvier\b|\bannée\s+suivante\b"
    r"|\bexercice\s+suivant\b"
)


def _seuil_de_la_memoire(reference: Reference) -> Seuil | None:
    """Le seuil de franchise que la règle a appliqué à CE projet (services ou ventes).

    La décision « regime_tva » de la mémoire cite le seuil de sa nature
    d'activité : un commerce de détail n'a pas les seuils d'une prestation de
    services (revue du 30/09/2026 — la consigne dictait 37 500 € à une
    activité de vente, une erreur de droit écrite par le contrôle lui-même).
    """
    from generation.memoire.controle import nombres_du_texte  # noqa: PLC0415

    if reference.memoire is None:
        return None
    for decision in reference.memoire.decisions:
        if decision.sujet != "regime_tva":
            continue
        cites = {round(v) for _, v, _ in nombres_du_texte(decision.justification)}
        for seuil in FRANCHISE_TVA.values():
            # Au-delà du seuil majoré, la justification ne cite plus que lui.
            if round(seuil.valeur) in cites or (
                seuil.majore is not None and round(seuil.majore) in cites
            ):
                return seuil
    return None


def _regle_de_tva(document: Document, reference: Reference) -> list[Constat]:
    """« TVA dès que le CA dépasse le seuil de franchise » : ce n'est pas la règle.

    Art. 293 B du CGI (`memoire.regles.FRANCHISE_TVA`) : la franchise se perd
    IMMÉDIATEMENT au-delà du seuil majoré ; entre le seuil et le seuil majoré,
    au 1er janvier de l'année suivante. Business plan ÉCLORE, 11.3 : la TVA
    « obligatoire dès que le chiffre d'affaires HT dépasse le seuil de
    franchise ».

    Le seuil vient de la phrase si elle l'écrit, sinon de la mémoire ; à défaut,
    la règle est énoncée SANS montant : un seuil deviné serait une erreur de
    droit dans la consigne de réécriture (règle 2).
    """
    from generation.memoire.controle import nombres_du_texte  # noqa: PLC0415

    du_projet = _seuil_de_la_memoire(reference)
    constats: list[Constat] = []
    for passage in _passages(document):
        for phrase in _PHRASES.finditer(passage.texte):
            texte = phrase.group(0)
            if not (_TVA.search(texte) and _IMMEDIAT.search(texte)):
                continue
            if _REGLE_EXACTE.search(texte):
                continue
            valeurs = {round(v) for _, v, _ in nombres_du_texte(texte)}
            ecrit = next(
                (s for s in FRANCHISE_TVA.values() if round(s.valeur) in valeurs), None
            )
            if ecrit is None and not _SEUIL_DE_FRANCHISE.search(texte):
                continue
            seuil = ecrit or du_projet
            if seuil is not None and seuil.majore is not None:
                if round(seuil.majore) in valeurs:
                    continue
                valeur = f"{seuil.valeur:,.0f}".replace(",", " ")
                majore = f"{seuil.majore:,.0f}".replace(",", " ")
                regle = (
                    f"La TVA n'est pas due « dès » le seuil de franchise ({valeur} €). Règle "
                    f"exacte (art. 293 B du CGI) : au-delà du seuil majoré ({majore} €), la "
                    "franchise se perd immédiatement ; entre le seuil et le seuil majoré, la "
                    "TVA s'applique au 1er janvier de l'année suivante. Écrire la règle ainsi."
                )
            else:
                regle = (
                    "La TVA n'est pas due « dès » le seuil de franchise. Règle exacte (art. "
                    "293 B du CGI) : au-delà du seuil MAJORÉ, la franchise se perd "
                    "immédiatement ; entre le seuil et le seuil majoré, la TVA s'applique au "
                    "1er janvier de l'année suivante. Écrire la règle ainsi."
                )
            constats.append(Constat("decision", passage.section, _court(texte), regle))
    return constats


# ═════════════════════════════════════════════════════════════════════════════


def controler(document: Document, reference: Reference) -> list[Constat]:
    base = _base(reference)
    predicats = _predicats(document, base)
    constats: list[Constat] = []
    if base is not None:
        constats += _comptes_contre_la_base(document, base, predicats)
    constats += _proportions_discordantes(predicats, base)
    constats += _comptes_contre_les_tableaux(document)
    constats += _dates_de_lancement(document)
    constats += _dates_du_depart(document, reference)
    constats += _statuts_de_l_apport(document)
    constats += _calendrier_des_fournisseurs(document)
    constats += _regle_de_tva(document, reference)
    return constats

"""Qualité rédactionnelle et cohérence des indicateurs (points 2, 9, 11, 12 de la cliente).

Business plan ÉCLORE `28a257bf`, repris à la main par la cliente le 30/09/2026.
Quatre défauts que les onze premières classes ne regardaient pas :

2.  un LIBELLÉ qui assimile deux indicateurs : « Résultat net (revenu de la
    dirigeante avant impôt) » confond le résultat comptable et ce que la
    dirigeante prélève. Un indicateur porte UN nom, jamais deux.
9.  une ÉVOLUTION en pourcentage calculée sur une base minuscule : « +1 021,7 % »
    parce que l'EBE passe de 782 € à 8 772 €. Sous mille euros de départ, le
    pourcentage n'a pas de sens — l'écart en euros, si.
11. une RÉPÉTITION : « quitte son poste et passe à temps plein après avoir
    quitté son poste ». Une passe anti-répétition sur les tableaux et les
    phrases.
12. la trésorerie de fin d'exercice ET le prélèvement du dirigeant présentés
    comme disponibles en même temps : c'est le MÊME argent compté deux fois (la
    trésorerie de fin d'exercice est déjà nette des prélèvements).

Aucun contrôle ne bloque : un constat grave fait reprendre le chapitre avec sa
consigne, un signal est tracé (règle 1 : ce qu'on ne peut pas corriger, on le
dit). Les seuils viennent de la cliente (30/09/2026).
"""
from __future__ import annotations

import re
import unicodedata

from ..orthographe import MOT, graphies_suspectes
from .constat import Constat, Reference
from .document import Document
from .fuites import textes_de_la_section
from .valeurs import nombres, phrases_de

# ── 2. Un libellé n'assimile pas deux indicateurs ────────────────────────────

#: Les indicateurs qu'un libellé ne doit pas confondre, et le mot qui les nomme.
#: « Résultat net (revenu…) », « CAF (résultat…) », « Trésorerie (revenu…) ».
_INDICATEURS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("le résultat net", re.compile(r"(?i)r[ée]sultat\s+net|r[ée]sultat\s+comptable")),
    ("la capacité d'autofinancement", re.compile(r"(?i)capacit[ée] d.autofinancement|\bCAF\b")),
    ("l'excédent brut d'exploitation", re.compile(r"(?i)exc[ée]dent brut|\bEBE\b")),
    ("la trésorerie", re.compile(r"(?i)tr[ée]sorerie")),
    (
        "le revenu ou prélèvement du dirigeant",
        re.compile(
            r"(?i)revenu\s+(?:de|du|de\s+la)|pr[ée]l[èe]vement|r[ée]mun[ée]ration\s+(?:de|du|de\s+la)"
            r"|ce\s+que\s+(?:la|le)\s+dirigeant\w*\s+(?:se\s+verse|per[çc]oit|touche)"
        ),
    ),
)
#: Un libellé est une amorce courte : « Résultat net (avant impôt) » précise le
#: MÊME indicateur, ce n'est pas une confusion. La parenthèse qui NOMME un autre
#: indicateur, si.
_PRECISION_LEGITIME = re.compile(
    r"(?i)^\W*\(?\s*(?:avant|apr[èe]s|hors|net)\b[^)]*\)?\s*$"
)


def _mot_dans_parenthese(libelle: str) -> str:
    trouve = re.search(r"\(([^)]*)\)", libelle)
    return trouve.group(1) if trouve else ""


def _libelles_qui_melangent(document: Document) -> list[Constat]:
    """Un libellé dont la parenthèse nomme un AUTRE indicateur que sa tête."""
    constats: list[Constat] = []
    for section in document.sections:
        libelles: list[str] = []
        for tableau in section.tableaux:
            libelles += [ligne[0] for ligne in tableau.lignes if ligne]
            libelles += list(tableau.entetes)
        for libelle in libelles:
            interieur = _mot_dans_parenthese(libelle)
            if not interieur or _PRECISION_LEGITIME.match("(" + interieur + ")"):
                continue
            tete = libelle.split("(", 1)[0]
            noms_tete = {nom for nom, motif in _INDICATEURS if motif.search(tete)}
            noms_paren = {nom for nom, motif in _INDICATEURS if motif.search(interieur)}
            autres = noms_paren - noms_tete
            if noms_tete and autres:
                constats.append(Constat(
                    "libelle_melange", section.numero, libelle[:200],
                    "Ce libellé nomme " + " et ".join(sorted(noms_tete)) + ", puis "
                    + " et ".join(sorted(autres)) + " entre parenthèses : "
                    "un indicateur ne porte qu'UN nom. Écris le nom de "
                    "l'indicateur réellement affiché, sans lui en accoler un autre — le résultat "
                    "net, la CAF, le prélèvement du dirigeant et la trésorerie sont distincts.",
                ))
    return constats


# ── 9. Pas d'évolution en pourcentage sur une base faible ────────────────────

#: Sous ce chiffre d'affaires de départ, un pourcentage d'évolution n'a pas de
#: sens : on écrit l'écart en euros (cliente, 30/09/2026).
SEUIL_BASE_FAIBLE = 1000.0
_EVOLUTION = re.compile(
    r"(?i)[-+]?\d[\d\s  ]*(?:[.,]\d+)?\s?%|\b[ée]volution\b|\bprogression\b"
    r"|\bcroissance\b|\bhausse\b|\bbond\b|\bx\s?\d"
)


def _pourcentages(texte: str) -> list[float]:
    return [n.valeur for n in nombres(texte) if n.pourcentage]


def _montants(texte: str) -> list[float]:
    return [n.valeur for n in nombres(texte) if n.monetaire and n.valeur > 0]


def _est_une_evolution(pourcent: float, montants: list[float]) -> float | None:
    """La base (< SEUIL) sur laquelle ce pourcentage EST l'évolution, ou None.

    Diagnostic POSITIF : le pourcentage doit valoir (haut − bas) ÷ bas × 100
    pour deux montants de la ligne. Sans cela, « marge de 15 % » ou « 60 % des
    ventes » ne sont pas des évolutions et ne se jugent pas ici.
    """
    for bas in montants:
        if bas >= SEUIL_BASE_FAIBLE:
            continue
        for haut in montants:
            if haut <= bas:
                continue
            attendu = (haut - bas) / bas * 100.0
            if abs(attendu - pourcent) <= max(1.0, abs(pourcent) * 0.03):
                return bas
    return None


def _evolutions_sur_base_faible(document: Document) -> list[Constat]:
    constats: list[Constat] = []
    for section in document.sections:
        unites: list[tuple[str, str]] = []  # (texte jugé, passage affiché)
        for tableau in section.tableaux:
            for ligne in tableau.lignes:
                if ligne:
                    unites.append((" · ".join(ligne), " · ".join(ligne)[:200]))
        for phrase in phrases_de(section, cellules=False):
            unites.append((phrase, phrase[:200]))
        for texte, passage in unites:
            montants = _montants(texte)
            for pourcent in _pourcentages(texte):
                if abs(pourcent) < 100:  # une évolution absurde est GRANDE
                    continue
                base = _est_une_evolution(pourcent, montants)
                if base is None:
                    continue
                constats.append(Constat(
                    "evolution", section.numero, passage,
                    f"Évolution de {pourcent:.0f} % calculée sur une base de "
                    f"{base:,.0f} €".replace(",", " ")
                    + " : sous mille euros de départ, le pourcentage trompe. "
                    "Écris l'écart en euros, pas en pourcentage.",
                ))
                break
    return constats


# ── 11. Pas de répétition dans une même phrase ou cellule ────────────────────

_MOTS_VIDES = frozenset(
    "le la les un une des du de d au aux à a et ou où que qui quoi dont ne pas "
    "se sa son ses leur leurs ce cette ces cet en y il elle ils elles on nous vous "
    "pour par sur sous dans avec sans plus moins est sont être avoir puis alors "
    "plein temps".split()
)
#: En deçà, une suite répétée est trop courte pour être une redite (« de la
#: société » revient sans faute). Une redite est un SIGNAL, jamais une reprise
#: payée : une reformulation automatique sur une répétition de quatre mots
#: rejouerait le défaut des faux positifs graves (revue du 30/09/2026). La passe
#: la relève et la trace ; la cliente demandait « une passe anti-répétition ».
_MOTS_MIN_SIGNAL = 3
#: Une ligne de sources répète les noms par nature (« Nom : Site officiel Nom,
#: URL ») : ce n'est pas une redite de rédaction, et les sources ont leur classe.
_LIGNE_DE_SOURCE = re.compile(
    r"(?i)https?://|www\.|\bsite officiel\b|\bsource\b|\burl\b|\.(?:fr|com|org|net)\b"
)


def _sans_accent(mot: str) -> str:
    plat = "".join(
        c for c in unicodedata.normalize("NFD", mot.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z]", "", plat)


def _est_plein(mot: str) -> bool:
    """Un mot qui porte du sens — pas un article, une préposition, un pronom.

    Le test porte sur le mot d'ORIGINE : le radical de « le » est « l », qui
    n'est plus dans la liste des mots vides et ferait passer « le plus » pour
    deux mots pleins.
    """
    return bool(_sans_accent(mot)) and _sans_accent(mot) not in _MOTS_VIDES


def _radical(mot: str) -> str:
    """Le mot sans accent, en minuscules, sans sa terminaison de conjugaison.

    « quitte » et « quitté » deviennent « quitt » : la redite se voit malgré
    l'accord (« passe à temps plein après avoir quitté son poste »).
    """
    plat = "".join(
        c for c in unicodedata.normalize("NFD", mot.lower()) if unicodedata.category(c) != "Mn"
    )
    plat = re.sub(r"[^a-z]", "", plat)
    return re.sub(r"(ements?|ers?|ees?|es|er|ez|ent|ait|era|e|s)$", "", plat) or plat


def _repetitions(document: Document) -> list[Constat]:
    constats: list[Constat] = []
    for section in document.sections:
        # Un paragraphe, ou UNE cellule prise seule : la redite se lit à
        # l'intérieur d'un même texte. Une ligne de tableau recollée par « · »
        # ferait passer pour une redite un terme qui revient d'une colonne à
        # l'autre (« 182 € TTC (donnée du projet) · 224 € TTC (donnée… »), ce
        # qui est la forme normale d'un tableau, pas une faute (revue du
        # 30/09/2026).
        unites = list(section.paragraphes)
        for tableau in section.tableaux:
            unites += [cellule for ligne in tableau.lignes for cellule in ligne]
        for texte in unites:
            if _LIGNE_DE_SOURCE.search(texte):
                continue
            mots = texte.split()
            if len(mots) < _MOTS_MIN_SIGNAL * 2:
                continue
            radicaux = [_radical(m) for m in mots]
            taille = _MOTS_MIN_SIGNAL
            vus: dict[tuple[str, ...], int] = {}
            for i in range(len(radicaux) - taille + 1):
                fenetre = tuple(radicaux[i : i + taille])
                if any(not r for r in fenetre):
                    continue
                if sum(1 for m in mots[i : i + taille] if _est_plein(m)) < 2:
                    continue
                if fenetre in vus and i - vus[fenetre] >= taille:
                    fragment = " ".join(mots[i : i + taille])
                    constats.append(Constat(
                        "repetition", section.numero, texte[:200],
                        f"« {fragment} » revient deux fois dans le même passage. "
                        "Reformule pour supprimer la redite.",
                        grave=False,
                    ))
                    break
                vus[fenetre] = i
    return constats


# ── 12. Trésorerie et prélèvement ne sont pas disponibles deux fois ──────────

_TRESORERIE = re.compile(r"(?i)tr[ée]sorerie|excédent de tr[ée]sorerie|solde de tr[ée]sorerie")
_DISPONIBLE = re.compile(r"(?i)disponible|disponibilit|utilisable|mobilisable|reste\b|dispose")
_PRELEVEMENT = re.compile(
    r"(?i)se\s+verse|se\s+r[ée]mun[èe]re|pr[ée]l[èe]ve|pr[ée]l[èe]vement|r[ée]mun[ée]ration\s+"
    r"(?:de|du|de\s+la)\s+dirigeant|revenu\s+(?:de|du|de\s+la)\s+dirigeant"
)
#: La trésorerie de fin d'exercice est DÉJÀ nette des prélèvements : le dire ne
#: compte pas deux fois le même argent.
_DEJA_NETTE = re.compile(
    r"(?i)apr[èe]s\s+pr[ée]l[èe]vement|net\w*\s+de\s+pr[ée]l[èe]vement|une\s+fois\s+pr[ée]lev"
    r"|d[ée]duction\s+faite|d[ée]duit\w*|une\s+fois\s+(?:la|le)\s+dirigeant"
)


def _double_compte(document: Document) -> list[Constat]:
    """La même phrase présente la trésorerie ET un prélèvement comme disponibles."""
    constats: list[Constat] = []
    for section in document.sections:
        for phrase in phrases_de(section):
            if _DEJA_NETTE.search(phrase):
                continue
            if (
                _TRESORERIE.search(phrase)
                and _DISPONIBLE.search(phrase)
                and _PRELEVEMENT.search(phrase)
            ):
                constats.append(Constat(
                    "double_compte", section.numero, phrase[:200],
                    "La trésorerie de fin d'exercice et le prélèvement du dirigeant sont "
                    "présentés comme disponibles ensemble : c'est le même argent compté deux "
                    "fois. La trésorerie de fin d'exercice est DÉJÀ nette des prélèvements — "
                    "dis lequel des deux tu montres.",
                    grave=False,
                ))
    return constats



# ═════════════════════════════════════════════════════════════════════════════
# 13. Orthographe : le même mot écrit de deux façons dans le même document
# ═════════════════════════════════════════════════════════════════════════════

def _orthographe_a_deux_graphies(document: Document) -> list[Constat]:
    """Le même mot écrit avec et sans ses accents dans le même document.

    ## Le défaut, mesuré

    Étude de marché à l'export, cliente, 26/10/2026 : « toutefise », « precise »,
    « acheteurs transfrontalier ». Aucun dictionnaire français n'est installé
    dans l'image, et en ajouter un est une décision d'infrastructure.

    Mais une faute d'accent se trahit sans dictionnaire : le document écrit
    « précise » ailleurs. **Le corpus de référence, c'est le document
    lui-même.** Deux graphies du même mot dans un même livrable sont un défaut
    quelle que soit celle qui est juste — et le lecteur retrouve les deux
    (règle 2).

    ## Ce que ce contrôle NE voit pas, et pourquoi c'est écrit ici

    Une faute écrite de façon CONSTANTE — « toutefise » partout, un mot dont la
    forme juste n'apparaît nulle part — reste invisible : il n'y a rien à
    comparer (règle 1). La fermer demande un dictionnaire français dans
    l'image, décision qui appartient au client.

    Signalé, jamais grave : la graphie ne change aucun chiffre, et une reprise
    de chapitre payée pour un accent coûterait plus qu'elle ne rapporte.
    """
    suspects = graphies_suspectes(s.texte() for s in document.sections)
    if not suspects:
        return []
    constats: list[Constat] = []
    vus: set[str] = set()
    for section in document.sections:
        # `textes_de_la_section` et non `phrases_de` : ce dernier écarte toute
        # cellule de 40 signes ou moins, or le livrable de référence loge 52 %
        # de ses mots dans des tableaux, et c'est là qu'une graphie fautive
        # isolée passait inaperçue (revue du 27/10/2026).
        for phrase in textes_de_la_section(section):
            for mot in MOT.findall(phrase):
                juste = suspects.get(mot)
                if juste is None or mot in vus:
                    continue
                vus.add(mot)
                constats.append(Constat(
                    "orthographe", section.numero, phrase[:200],
                    f"« {mot} » s'écrit « {juste} » ailleurs dans le document : le "
                    "même mot ne s'écrit pas de deux façons. Garde la graphie "
                    "accentuée.",
                    grave=False,
                ))
    return constats


# ── Un nombre en chiffres n'appelle pas de « de » ───────────────────────────

#: Ce qui suit « de » quand le « de » est fautif : une monnaie, une mesure, une
#: population. « 5 000 de plus », « 3 % de marge » sont corrects ;
#: « 275 000 000 de dollars » ne l'est pas — « de » n'appelle un complément
#: qu'après un mot d'échelle (« millions de », « milliards de »).
_APRES_DE = (
    "euros?|dollars?|yens?|livres?|francs?|dirhams?|yuans?|"
    "tonnes?|kilos?|kilogrammes?|litres?|hectares?|kilom[eè]tres?|"
    "habitants?|clients?|visiteurs?|unit[eé]s?|pi[eè]ces?|articles?|"
    "personnes?|salari[eé]s?|entreprises?|foyers?|m[eé]nages?"
)

#: Un nombre écrit en chiffres, séparateurs de milliers compris. Le mot
#: d'échelle, lui, est un mot : il ne peut pas tomber dans ce motif.
_CHIFFRES_PUIS_DE = re.compile(
    r"(?<![\w,.])(?P<nombre>\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d{4,})"
    r"\s+d[e\u2019']\s*(?P<objet>" + _APRES_DE + r")\b",
    re.IGNORECASE,
)


def _nombres_sans_echelle(document: Document) -> list[Constat]:
    """« 275 000 000 de dollars » : il manque le mot d'échelle.

    Relevé par la cliente le 26/10/2026 sur l'étude à l'export :
    « 275 000 000 de ». En français, « de » ne suit un nombre qu'après un mot
    d'échelle — « 275 millions de dollars » — ou disparaît :
    « 275 000 000 dollars ». Écrit tel quel, le lecteur bute sur la phrase et
    doute du chiffre.
    """
    constats: list[Constat] = []
    for section in document.sections:
        # Idem : « 275 000 000 de dollars » tient en 22 signes, et un tableau
        # est son habitat naturel — `phrases_de` ne l'aurait jamais vu.
        for phrase in textes_de_la_section(section):
            for trouve in _CHIFFRES_PUIS_DE.finditer(phrase):
                nombre, objet = trouve.group("nombre"), trouve.group("objet")
                constats.append(Constat(
                    "orthographe", section.numero, phrase[:200],
                    f"« {nombre} de {objet} » : après un nombre écrit en chiffres, "
                    "« de » n'a pas de place. Écris le mot d'échelle — « 275 millions "
                    f"de {objet} » — ou retire le « de » : « {nombre} {objet} ».",
                ))
    return constats



# ═════════════════════════════════════════════════════════════════════════════
# 14. Les formulations que les cahiers des charges interdisent nommément
# ═════════════════════════════════════════════════════════════════════════════

#: Ce que les cahiers des charges écrivent sous « Ne jamais écrire », mot pour
#: mot, et qu'aucun contrôle ne lisait.
#:
#: ## Pourquoi un contrôle, et pas une consigne de plus
#:
#: Ces phrases sont déjà interdites dans les prompts (`prompts.py`,
#: `prompt_library.py`). Depuis cinq mois. La cliente les relève encore —
#: « l'étude passe son temps à dire données à définir, à vérifier : je n'aime
#: pas cela, j'aime apporter de vraies réponses » (09/08/2026), et le
#: 28/10/2026 : « Aucun texte générique ni placeholder ».
#:
#: Une septième formulation de la consigne n'y changera rien. Un motif qui fait
#: reprendre le chapitre avec la phrase exacte, oui.
#:
#: ## D'où vient chaque ligne
#:
#: `references/systemes/02-etude-concurrence-cdc-v1.pdf` (18/05/2026),
#: `03-business-plan-v1.pdf` et `04-strategie-business-v1.pdf`. Rien n'est
#: inventé ici : chaque motif traduit une puce de ces documents.

#: L'ABSENCE DE DONNÉE, dite au lecteur. Les cahiers de l'étude de la
#: concurrence ET du business plan la listent tous les deux : c'est une règle
#: de maison, appliquée aux quatre livrables.
_ABSENCE_DE_DONNEE: tuple[tuple[str, str], ...] = (
    (r"n.(?:avons|ai)\s+pas\s+trouv[ée]\s+de\s+donn[ée]es", "nous n'avons pas trouvé de données"),
    (r"(?:les\s+)?donn[ée]es\s+sont\s+indisponibles", "les données sont indisponibles"),
    (r"peu\s+de\s+sources\s+existent", "peu de sources existent"),
    (r"aucune\s+information\s+(?:n.est\s+)?disponible", "aucune information disponible"),
)

#: Ce que chaque livrable interdit EN PLUS, sans condition.
_INTERDITES_PAR_LIVRABLE: dict[str, tuple[tuple[str, str], ...]] = {
    "business_plan": (
        (r"le\s+projet\s+est\s+tr[èe]s\s+ambitieux\s+et\s+innovant",
         "le projet est très ambitieux et innovant"),
    ),
    "business_strategy": (
        (r"il\s+faut\s+poster\s+plus", "il faut poster plus sur Instagram"),
        (r"il\s+faut\s+[êe]tre\s+pr[ée]sent\s+sur\s+tous\s+les\s+r[ée]seaux",
         "il faut être présent sur tous les réseaux"),
    ),
}

#: Celles que le cahier n'interdit QUE « sans chiffres à l'appui » (business
#: plan) ou « sans analyse » (stratégie). La condition ne se lit pas en code :
#: on vérifie qu'un chiffre figure dans la même phrase, et on se contente de
#: SIGNALER — un motif grave sur une affirmation peut-être justifiée punirait
#: ce qui ne l'a pas mérité (règle 2).
_A_JUSTIFIER: tuple[tuple[str, str], ...] = (
    (r"le\s+march[ée]\s+est\s+tr[èe]s\s+porteur", "le marché est très porteur"),
    (r"l.entreprise\s+doit\s+se\s+d[ée]marquer", "l'entreprise doit se démarquer"),
    (r"la\s+strat[ée]gie\s+semble\s+coh[ée]rente", "la stratégie semble cohérente"),
)

#: Un chiffre dans la phrase : ce qui transforme une affirmation en constat.
_UN_CHIFFRE = re.compile(r"\d")


def _formulations_interdites(document: Document, livrable: str) -> list[Constat]:
    """Les phrases que le cahier des charges du livrable interdit nommément.

    Deux sévérités, et la différence vient du cahier lui-même :

    - l'absence de donnée dite au lecteur est interdite SANS condition — le
      chapitre se reprend ;
    - « le marché est très porteur » n'est interdit que « sans chiffres à
      l'appui » : on ne le signale que si la phrase ne porte aucun chiffre, et
      jamais gravement, parce que la justification peut vivre dans la phrase
      suivante et que le code ne sait pas la lire.
    """
    interdites = (*_ABSENCE_DE_DONNEE, *_INTERDITES_PAR_LIVRABLE.get(livrable, ()))
    constats: list[Constat] = []
    for section in document.sections:
        for phrase in textes_de_la_section(section):
            for motif, telle_quelle in interdites:
                if not re.search(motif, phrase, re.IGNORECASE):
                    continue
                constats.append(Constat(
                    "redaction", section.numero, phrase[:200],
                    f"« {telle_quelle} » : le cahier des charges l'interdit "
                    "nommément. Écris ce que les sources PERMETTENT de dire, "
                    "puis ce qui manque exactement et qui le publie — un "
                    "client paie un livrable, pas le relevé de ce qu'on n'a "
                    "pas trouvé.",
                ))
            if _UN_CHIFFRE.search(phrase):
                continue
            for motif, telle_quelle in _A_JUSTIFIER:
                if re.search(motif, phrase, re.IGNORECASE):
                    constats.append(Constat(
                        "redaction", section.numero, phrase[:200],
                        f"« {telle_quelle} » sans un chiffre dans la phrase : "
                        "le cahier des charges ne l'admet qu'appuyé. Donne la "
                        "valeur, la croissance ou la part qui le montre.",
                        grave=False,
                    ))
    return constats


def controler(document: Document, reference: Reference) -> list[Constat]:
    return [
        # Le seul contrôle de ce module qui dépend du LIVRABLE : chaque cahier
        # des charges a sa propre liste de « Ne jamais écrire ».
        *_formulations_interdites(document, str(reference.livrable or "")),
        *_libelles_qui_melangent(document),
        *_evolutions_sur_base_faible(document),
        *_repetitions(document),
        *_double_compte(document),
        *_orthographe_a_deux_graphies(document),
        *_nombres_sans_echelle(document),
    ]

"""Fuites internes et renvois de figures (classe 7).

Le vocabulaire de la chaîne dans le texte final, une phrase brute de la
mémoire collée telle quelle ; un renvoi « Figure présentée au chapitre X »
hors sujet.

## Le défaut, relevé par la cliente

Business plan ÉCLORE `28a257bf` (30/09/2026). Le lecteur lisait :

- des étiquettes de notre chaîne : « phrase du client » (11.4), « Données du
  socle vérifié » sous deux figures (6.4, 8.5) ;
- le document qui parle de sa source au lieu du projet : « selon les termes
  du dossier » (16.7), « précisé dans le dossier » (12.2), « le client n'a
  pas arbitré » (16.6), « aucune ligne n'est recalculée » (16.2) ;
- une ligne de la mémoire recopiée mot pour mot, avec son « AAAA : » de
  prise de notes (12.1, 19.4) ;
- « Figure présentée au chapitre 1 — Repères financiers du lancement » sous
  « Taille et dynamique du marché » (6.1) : un renvoi vers une figure qui
  parle d'autre chose.

## Une seule liste (règle 5)

Le vocabulaire interdit est `chapitres.schema._VOCABULAIRE_INTERNE`, la liste
qui refuse déjà un chapitre avant validation. Ce module l'IMPORTE : ce que la
relecture du PDF signale est exactement ce que la validation des chapitres
refuse, et une locution ajoutée là est jugée ici sans que personne y pense.

## Le test de sujet d'un renvoi, partagé avec le rendu

`renvoi_sur_le_sujet` est la fonction qui décide si une figure « porte sur »
une section. Le rendu Word (`rendu_word.assemblage`) l'emploie pour ne poser un
renvoi que s'il est à propos ; cette relecture l'emploie pour signaler ceux qui
restent. Une seule évidence, deux usages (règle 5).
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Iterator

from .constat import Constat, Reference
from .document import Document, Section, Tableau

# ── Texte lisible, racines ───────────────────────────────────────────────────

#: « micro- entreprise », « Val- d'Oise » : la césure du PDF, recollée.
_CESURE = re.compile(r"(\w)-\s+(\w)")


def texte_lisible(texte: str) -> str:
    """Le texte comme le lecteur le lit : césures recollées, espaces uniques.

    Le PDF coupe « micro-entreprise » en fin de ligne et la reconstitution des
    cellules rend « micro- entreprise » : sans ce recollage, une phrase de la
    mémoire recopiée mot pour mot ne se reconnaît plus.
    """
    return re.sub(r"\s+", " ", _CESURE.sub(r"\1-\2", texte or "")).strip()


def _sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c))


#: Les mots qui ne disent pas de quoi parle un titre : mots outils, nombres en
#: lettres, et le vocabulaire de la présentation (« repères », « données »,
#: « comparé ») qu'un titre de figure et un titre de section partagent sans
#: parler de la même chose.
_MOTS_VIDES = frozenset(_sans_accents(m) for m in (
    "avec sans dans pour sous vers entre chez leur leurs cette ceux celle celles "
    "dont elle elles tous toutes tout toute plus moins tres ainsi aussi afin apres "
    "avant depuis pendant selon comment quel quelle quels quelles votre notre nos "
    "deux trois quatre cinq sept huit neuf onze douze treize quatorze quinze seize "
    "vingt cent mille premier premiere premiers premieres "
    "repere reperes donnee donnees figure figures graphique graphiques tableau "
    "tableaux compare comparee compares comparees comparaison vue ensemble "
    "principal principaux principale principales cela signifie"
).split())


def racines(texte: str) -> set[str]:
    """Les racines des mots qui portent le sens : minuscules, sans accents, six lettres.

    Grossier par choix : « critères » et « critère », « activités » et
    « activité », « signaux » et « signal » se rejoignent ; un mot de moins de
    quatre lettres, un sigle en capitales (le nom du projet, « CA », « TVA ») et
    un mot vide ne comptent pas. Le nom du projet figure dans les titres de
    figure comme dans les titres de section : il ferait passer n'importe quel
    renvoi pour « à propos ».
    """
    trouvees: set[str] = set()
    mots = re.findall(r"[^\W\d_]+", texte or "")
    # Un titre ENTIER en capitales (« ANALYSE DE MARCHÉ », le chapitre tel que
    # le PDF l'imprime) n'est pas une suite de sigles : il se lit en minuscules.
    if sum(1 for mot in mots if mot.isupper()) > len(mots) / 2:
        mots = [mot.lower() for mot in mots]
    for mot in mots:
        if len(mot) >= 2 and mot.isupper():
            continue
        propre = _sans_accents(mot.lower())
        if propre.endswith("aux") and len(propre) > 4:
            propre = propre[:-3] + "al"
        elif propre.endswith(("s", "x")) and len(propre) > 4:
            propre = propre[:-1]
        if len(propre) < 4 or propre in _MOTS_VIDES:
            continue
        trouvees.add(propre[:6])
    return trouvees


def renvoi_sur_le_sujet(titre_figure: str, sujets: Iterable[str]) -> bool:
    """La figure citée porte-t-elle sur le sujet de la section qui la cite ?

    La demande de la cliente (30/09/2026) : « un renvoi n'est autorisé que si
    la figure citée porte sur le sujet de la section — vérifie le titre de la
    figure contre le titre de la section ». Un mot de sens commun suffit :
    « Positionnement … sur les cinq critères de la grille » est à propos sous
    « Grille de notation commune : cinq critères » ; « Repères financiers du
    lancement » ne l'est pas sous « Taille et dynamique du marché ».

    Un titre de figure, ou un sujet, dont aucun mot ne porte de sens ne se juge
    pas : on ne déclare pas un renvoi hors sujet sur rien (règle 2).
    """
    figure = racines(titre_figure)
    sujet: set[str] = set()
    for texte in sujets:
        sujet |= racines(texte)
    if not figure or not sujet:
        return True
    return bool(figure & sujet)


# ── Où lire le texte d'une section ───────────────────────────────────────────


def est_un_encadre(tableau: Tableau) -> bool:
    """Un encadré (« VERDICT | Opportunité — … ») que le PDF rend comme un tableau.

    Il n'a pas de colonnes de données : son intitulé est en capitales, ou une
    de ses cellules d'en-tête est une phrase entière.
    """
    entetes = [e for e in tableau.entetes if e.strip()]
    if not entetes:
        return False
    premier = entetes[0].strip()
    if len(premier) > 3 and premier.upper() == premier and any(c.isalpha() for c in premier):
        return True
    return any(len(e.split()) > 14 for e in entetes)


def textes_de_la_section(section: Section) -> Iterator[str]:
    """Tout ce que le lecteur lit dans la section : titre, prose, chaque cellule."""
    if section.titre:
        yield section.titre
    yield from section.paragraphes
    for tableau in section.tableaux:
        yield from tableau.cellules()


#: Une phrase : jusqu'au point, au point d'exclamation ou d'interrogation.
#: Partagée avec `comptages` (règle 5).
PHRASE = re.compile(r"[^.!?]+(?:[.!?]+|$)")


def phrase_autour(texte: str, debut: int, fin: int, largeur: int = 180) -> str:
    """La phrase qui porte le passage [debut, fin), bornée à des mots entiers.

    Une phrase trop longue est coupée autour du passage, jamais au milieu d'un
    mot : l'extrait doit se retrouver tel quel dans le document (règle 2).
    """
    for m in PHRASE.finditer(texte):
        if m.start() <= debut < m.end():
            phrase = m.group(0)
            if len(phrase.strip()) <= largeur:
                return phrase.strip()
            relatif = debut - m.start()
            gauche = max(0, relatif - largeur // 3)
            droite = min(len(phrase), max(gauche + largeur, fin - m.start()))
            while gauche > 0 and not phrase[gauche - 1].isspace():
                gauche -= 1
            while droite < len(phrase) and not phrase[droite].isspace():
                droite += 1
            return phrase[gauche:droite].strip()
    return texte[max(0, debut - 40):fin + 60].strip()


def _jusqu_au_bout_du_mot(texte: str, fin: int) -> int:
    """« socle vérifi » → « socle vérifié » : un motif arrête sa racine, le lecteur lit le mot."""
    while fin < len(texte) and (texte[fin].isalpha() or texte[fin] in "'’"):
        fin += 1
    return fin


# ── 1. Le vocabulaire de la chaîne ───────────────────────────────────────────


def _vocabulaire_interne(document: Document) -> list[Constat]:
    """Chaque locution de `_VOCABULAIRE_INTERNE`, là où le lecteur la lit.

    Les adresses web sont masquées comme le fait la validation des chapitres
    (`schema._sans_les_adresses`), mais à LONGUEUR ÉGALE : l'extrait se relit
    alors dans le texte d'origine, adresse comprise (règle 2).
    """
    from generation.chapitres.schema import (  # noqa: PLC0415 — schéma lourd, chargé à l'usage
        _ADRESSE_WEB,
        _VOCABULAIRE_INTERNE,
    )

    constats: list[Constat] = []
    for section in document.sections:
        for brut in textes_de_la_section(section):
            lu = texte_lisible(brut)
            masque = _ADRESSE_WEB.sub(lambda m: " " * len(m.group(0)), lu)
            for _, motif in _VOCABULAIRE_INTERNE:
                for trouve in motif.finditer(masque):
                    fin = _jusqu_au_bout_du_mot(lu, trouve.end())
                    # Le nom du motif (« socle verrouillé/bloqué ») n'est PAS
                    # dans le détail : le détail part au rédacteur, et un
                    # motif qui nomme le dispositif l'apprend (voir
                    # `test_nos_propres_motifs_ne_parlent_pas_du_dispositif`).
                    constats.append(Constat(
                        classe="fuite",
                        section=section.numero,
                        extrait=phrase_autour(lu, trouve.start(), fin),
                        detail=(
                            f"« {lu[trouve.start():fin]} » parle de la fabrication du "
                            "document, pas du projet : le lecteur ne doit jamais le lire. "
                            "Retirer la mention, ou écrire ce que le projet établit : sa "
                            "donnée, sa décision, sa source publique."
                        ),
                    ))
    return constats


# ── 2. Une ligne de la mémoire recopiée ──────────────────────────────────────

#: En deçà, une phrase de la mémoire est un simple fait (« TVA obligatoire »)
#: que le document a toutes les raisons de reprendre à l'identique.
MOTS_MINIMUM_D_UNE_LIGNE_COLLEE = 6

#: « AAAA : à temps plein… », « Création : immatriculation… » : l'intitulé de
#: prise de notes qui trahit une ligne recopiée.
_INTITULE_DE_NOTE = re.compile(r"^\s*([\wÀ-ÿ' -]{1,40}?)\s*:\s")


def _forme_comparable(texte: str) -> str:
    """Casse, apostrophes, espaces et ponctuation finale ramenés à une forme."""
    texte = texte_lisible(texte).lower().replace("’", "'")
    return texte.strip(" ;,.:—-")


#: Au-delà de cette part du paragraphe (ou de la cellule), la ligne de la
#: mémoire n'est plus citée DANS une phrase : elle EST le paragraphe.
PART_D_UNE_LIGNE_COLLEE = 0.8


def _lignes_de_la_memoire(reference: Reference) -> list[str]:
    """Les phrases du brief que la mémoire garde mot pour mot (source « brief »).

    Ni les justifications, ni les décisions des règles ou du socle : une
    justification vraie (« chiffre d'affaires HT sous le seuil de franchise »)
    peut se reprendre, et une décision de règle se CITE à l'identique.
    """
    memoire = reference.memoire
    if memoire is None:
        return []
    lignes = [d.valeur for d in memoire.decisions if d.source == "brief"]
    return [
        ligne for ligne in dict.fromkeys(lignes)
        if len(_forme_comparable(ligne).split()) >= MOTS_MINIMUM_D_UNE_LIGNE_COLLEE
    ]


def _phrases_de_la_memoire(document: Document, reference: Reference) -> list[Constat]:
    """Une ligne de la mémoire collée telle quelle dans le texte.

    La décision doit être TENUE (même date, même statut) ; la phrase, elle,
    s'écrit avec les mots du document. « AAAA : à temps plein, après … »
    imprimé seul dans un paragraphe et dans une cellule (ÉCLORE, 12.1 et 19.4)
    est une note de cadrage, pas une phrase d'étude.
    """
    lignes = _lignes_de_la_memoire(reference)
    if not lignes:
        return []
    constats: list[Constat] = []
    for section in document.sections:
        for brut in textes_de_la_section(section):
            lu = texte_lisible(brut)
            # Même longueur que `lu` : la position trouvée ici se relit dans `lu`.
            comparable = lu.lower().replace("’", "'")
            for ligne in lignes:
                cible = _forme_comparable(ligne)
                debut = comparable.find(cible)
                if debut < 0:
                    continue
                # L'extrait tel que le DOCUMENT l'écrit (sa casse, ses apostrophes).
                ecrite = lu[debut:debut + len(cible)]
                intitule = _INTITULE_DE_NOTE.match(ecrite)
                # La décision TENUE dans une phrase rédigée est ce qu'on demande
                # (« Le passage en société au 1er janvier s'accompagne… ») : seule
                # la ligne imprimée pour elle-même, ou avec son intitulé de prise
                # de notes, est une ligne collée.
                seule = len(cible) >= PART_D_UNE_LIGNE_COLLEE * len(lu.strip(" .;"))
                if not (seule or intitule):
                    continue
                sans_intitule = (
                    f" Pas d'intitulé « {intitule.group(1)} : » de prise de notes."
                    if intitule else ""
                )
                constats.append(Constat(
                    classe="fuite",
                    section=section.numero,
                    extrait=ecrite,
                    detail=(
                        "Cette ligne reprend mot pour mot une décision de cadrage du "
                        "projet. La décision se tient — même date, même statut — mais "
                        "s'écrit en phrase complète, avec les mots du document et son "
                        f"sujet (qui fait quoi, quand).{sans_intitule}"
                    ),
                ))
    return constats


# ── 3. Les renvois de figures ────────────────────────────────────────────────

#: La ligne que pose le rendu Word à la place d'une figure déjà dessinée
#: ailleurs (`rendu_word.assemblage._renvoi`).
RENVOI = re.compile(
    r"^\s*Figure\s+présentée\s+(?:au\s+chapitre\s+(?P<chapitre>\d{1,2})|plus\s+haut\s+dans"
    r"\s+ce\s+chapitre)\s+[—–-]\s+(?P<titre>.+)$"
)


def sujets_de_la_section(section: Section) -> list[str]:
    """Ce dont parle une section : son titre, et les en-têtes de ses tableaux de données.

    Les en-têtes disent ce que la section MONTRE (« Part du chiffre d'affaires
    par univers » sous « Le panier moyen pondéré ») ; la prose, elle, cite de
    tout, et un mot glané dans un paragraphe ferait passer n'importe quel
    renvoi pour à propos. Les encadrés de conclusion n'en font pas partie.
    """
    sujets = [section.titre]
    for tableau in section.tableaux:
        if not est_un_encadre(tableau):
            sujets.extend(tableau.entetes)
    return [s for s in sujets if s.strip()]


def _renvois_hors_sujet(document: Document) -> list[Constat]:
    constats: list[Constat] = []
    for section in document.sections:
        paragraphes = [texte_lisible(p) for p in section.paragraphes]
        for rang, paragraphe in enumerate(paragraphes):
            trouve = RENVOI.match(paragraphe)
            if trouve is None:
                continue
            ligne, titre = paragraphe, trouve.group("titre")
            suite = paragraphes[rang + 1] if rang + 1 < len(paragraphes) else ""
            # Le titre long passe à la ligne : « …comparé aux » / « concurrents
            # directs ». La suite commence par une minuscule, et elle est courte.
            if suite and suite[:1].islower() and len(suite) < 80:
                ligne, titre = f"{ligne} {suite}", f"{titre} {suite}"
            if renvoi_sur_le_sujet(titre, sujets_de_la_section(section)):
                continue
            constats.append(Constat(
                classe="renvoi_figure",
                section=section.numero,
                extrait=ligne,
                detail=(
                    f"La figure citée (« {titre} ») ne porte pas sur le sujet de la "
                    f"section (« {section.titre} ») : le lecteur qui la cherche trouve "
                    "une autre question. Retirer ce renvoi, ou citer une figure qui "
                    "traite ce sujet."
                ),
                # Le renvoi est posé par le rendu, pas écrit par le rédacteur :
                # réécrire le chapitre ne le retirerait pas. Signalé seulement ;
                # la correction est dans `rendu_word.assemblage`.
                grave=False,
            ))
    return constats


def controler(document: Document, reference: Reference) -> list[Constat]:
    return [
        *_vocabulaire_interne(document),
        *_phrases_de_la_memoire(document, reference),
        *_renvois_hors_sujet(document),
    ]

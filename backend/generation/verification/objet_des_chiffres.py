"""Un chiffre garde-t-il le MÊME objet d'un chapitre à l'autre ?

## Le défaut visé

Retour de la cliente du 29/10/2026 sur deux études de marché : « il reste
dans la même zone de chiffre, mais il change un peu la destination ». Son
exemple : 10 000 porteurs de projet deviennent, trois chapitres plus loin,
10 000 entreprises créées. Mesuré le même jour sur l'étude `99a142b0` :
« 40 % des TPE-PME utilisent l'IA » (France Num) est repris dans douze
chapitres, devient « 40 % [des TPE] » au chapitre 20 et s'applique à
« 1 000 000 TPE » au chapitre 3.

Aucun contrôle ne le voyait. `controler_chiffres_hors_socle` compare des
VALEURS : 40 reste 40, quoi qu'il compte. Et ce chiffre-là n'est même pas
dans le socle — une source citée dans la phrase suffit à l'excuser.

## Ce que le contrôle relève

Pour chaque grandeur du document, l'OBJET qu'elle compte, lu dans le texte qui
la suit : « 40 % des TPE-PME » → `TPE-PME` ; « 10 000 porteurs » →
`porteurs`. Puis, pour une même valeur, les objets qu'elle reçoit :

- **glissement** : deux objets apparentés mais différents — un mot commun,
  « TPE-PME » et « TPE ». C'est la forme exacte du défaut : la population se
  resserre ou s'élargit sans que le chiffre bouge.
- **objet changé** : deux objets sans mot commun — « porteurs » et
  « entreprises ». C'est l'exemple de la cliente, mais c'est aussi le cas de
  deux statistiques légitimes qui tombent sur la même valeur (« 40 % des
  dépenses éligibles », une aide régionale) ; le rapport les montre côte à
  côte pour qu'un lecteur tranche.
- **répétition** : la même statistique, avec le même objet, dans plus de
  `REPETITION_MAX` chapitres.

## Mode mesure seule

Gravité **avertissement** ou **information**, jamais blocage, et le nom du
contrôle n'est PAS dans `controle_final.REPARABLES_PAR_CHAPITRE` : il ne
déclenche aucune réécriture payante. On le fait tourner sur le corpus, on lit
ce qu'il trouve, on trie vrais et faux motifs, puis on décide (règle 2 : un
contrôle qui frappe à tort est pire qu'absent).

Ce que le contrôle ne voit pas, dit pour qu'on le sache (règle 9) :

- un objet placé AVANT le nombre (« les TPE : 40 % utilisent l'IA ») ;
- les nombres écrits en lettres ;
- tout ce qui suit le PREMIER mot de l'objet : « 40 % des TPE et PME » face à
  « 40 % des TPE » reste muet, et « des petites entreprises » face à « des
  grandes entreprises » sort en « objet changé » sur `petites` / `grandes` ;
- un nom qui a la forme d'un participe (`_FIN_DE_PARTICIPE`) : « nuitées »,
  « entrées », « données », « contenus » sont écartés avec « créées ».
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass

from core.numbers import CURRENCY_ALTERNATION, MAGNITUDE_WORDS, SPACE_CLASS

from .lecture import DocumentLu
from .rapport import Anomalie, Gravite

CONTROLE = "objet_des_chiffres"

#: Au-delà, une statistique répétée encombre plus qu'elle n'informe. La
#: cliente : « une même statistique n'apparaît que là où elle sert ».
REPETITION_MAX = 3

#: Début d'un nombre : ni une lettre ou un chiffre collés (« An1 000 »), ni un
#: chiffre suivi d'une espace — sinon « 1 000 % » se lirait « 000 % ». Les
#: espaces sont celles de `core/numbers.py` (règle 5) : JAMAIS le saut de ligne,
#: qui joint les paragraphes d'une cellule — « Année 1\n2 000\n500 clients »
#: se lirait « 2 000 500 clients ».
_DEBUT = rf"(?<![A-Za-z\d,.])(?<!\d{SPACE_CLASS})"

#: Un mot d'objet : lettres, chiffres collés, trait d'union (« TPE-PME »).
_MOT = r"[A-Za-zÀ-ÖØ-öø-ÿ][\wÀ-ÖØ-öø-ÿ'’-]*"

#: Pourcentage suivi de la POPULATION qu'il compte : « 40 % DES TPE-PME »,
#: « 41 % de cyberacheteurs ». Seulement un pluriel, ou un sigle.
#:
#: Le singulier est écarté à dessein, mesuré sur `99a142b0` et `6832779f` : il
#: introduit un DÉNOMINATEUR (« 10 % du marché », « 10 % du TAM », « 10 % du
#: total » — trois façons de nommer le même) ou un taux (« 40 % d'usage »,
#: « 40 % d'adoption »). Les compter faisait du bruit sans un seul glissement de
#: population de plus.
_POURCENTAGE = re.compile(
    rf"{_DEBUT}(\d{{1,3}}(?:,\d+)?){SPACE_CLASS}?%{SPACE_CLASS}+"
    rf"(?:des{SPACE_CLASS}+({_MOT})|(?:de{SPACE_CLASS}+|d['’])((?:[A-ZÀ-Ý][A-ZÀ-Ý-]{{1,}}|{_MOT}[sx])(?![\wÀ-ÿ'’-])))"
)

#: Effectif suivi de son objet : « 10 000 porteurs », « 1 000 000 TPE ».
#: Seulement à partir de mille, écrit avec séparateur de milliers : en deçà, ou
#: sans séparateur, on attrape des années, des numéros, des codes.
_EFFECTIF = re.compile(
    rf"{_DEBUT}(\d{{1,3}}(?:{SPACE_CLASS}\d{{3}})+){SPACE_CLASS}+"
    rf"(?:de{SPACE_CLASS}+|d['’])?({_MOT})"
)

#: Mots qui suivent un nombre sans être ce qu'il compte : unités, durées,
#: articles, prépositions. Liste FERMÉE et courte à dessein : un mot absent ne
#: crée qu'un objet de plus, visible dans le rapport ; un mot de trop y
#: cacherait un vrai glissement.
_PAS_UN_OBJET = frozenset({
    "a", "au", "aux", "en", "et", "ou", "par", "pour", "sur", "sous", "dans",
    "avec", "contre", "entre", "soit", "plus", "moins", "environ", "le", "la",
    "les", "l", "un", "une", "ce", "cette", "ces", "son", "sa", "ses", "leur",
    "leurs", "votre", "vos", "notre", "nos", "an", "ans", "annee", "annees",
    "mois", "jour", "jours", "semaine", "semaines", "heure", "heures", "fois",
    "habitant", "habitants", "qui", "que", "dont", "selon", "hors", "chacun",
    "seulement", "aujourd'hui", "aujourd’hui",
    # Unités hors devise. Les devises et les magnitudes, elles, viennent de
    # `core/numbers.py` (`_EST_UNE_UNITE`) : pas de seconde liste (règle 5).
    "ht", "ttc", "m2", "km", "kg", "ha", "tva",
    # Restes d'unité : « 5 002 MdUSD », « 1 000 Md ».
    "md", "mds", "usd", "mdusd", "musd", "k",
    # Verbes qui suivent un effectif repris dans un calcul : « 2 000 divisé
    # par », « s'écarte de 3 000 doit déclencher » (corpus du 29/10/2026).
    "divise", "multiplie", "doit", "peut", "est", "sont",
})

#: Participes passés : « 2 400 REVENDIQUÉS », « 1 800 RETENUS », « 10 000
#: entreprises CRÉÉES ». Lus sur le mot écrit, avec ses accents : sur la clé,
#: « créées » ne se distinguerait plus d'un nom. « -és » seul n'y est PAS :
#: il emporterait « salariés » et « employés », qui sont des populations.
_FIN_DE_PARTICIPE = re.compile(r"(?:ée|ées|qué|qués|tenus?|ndus?|évus?)$", re.IGNORECASE)

#: Pourcentages qui disent « tout » ou « rien » : « 100 % des documents »,
#: « 100 % des envois ». Ils reviennent légitimement avec cent objets.
_TOUT_OU_RIEN = frozenset({"0 %", "100 %"})

#: Une devise ou une magnitude n'est pas un objet : « 10 000 FCFA ».
_EST_UNE_UNITE = re.compile(rf"(?:{CURRENCY_ALTERNATION}|{MAGNITUDE_WORDS})", re.IGNORECASE)


@dataclass(frozen=True)
class Occurrence:
    """Une grandeur et l'objet qu'elle compte, telle que le lecteur la lit."""

    valeur: str
    """La valeur normalisée, avec son unité : `40 %`, `10 000`."""
    objet: str
    """L'objet tel qu'écrit dans le document."""
    cle: str
    """L'objet normalisé — casse, accents, pluriel — pour comparer."""
    chapitre: int | None
    extrait: str
    forme: str = ""
    """La grandeur et son objet, tels qu'écrits : `40 % des TPE-PME`."""


def _sans_accents(texte: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn"
    )


def _cle(objet: str) -> str:
    """`Entreprises` et `entreprise` comptent la même chose ; `TPE-PME` et `TPE`
    non — le trait d'union est gardé, c'est lui qui porte le glissement."""
    mot = _sans_accents(objet).lower().strip("'’-")
    mot = re.sub(r"^(?:l|d)['’]", "", mot)
    if len(mot) > 3 and mot.endswith(("s", "x")) and not mot.endswith("ss"):
        mot = mot[:-1]
    return mot


def _mots(cle: str) -> set[str]:
    return {m for m in re.split(r"[-\s]+", cle) if m}


def _apparentes(a: str, b: str) -> bool:
    """L'une des populations contient l'autre : `TPE` dans `TPE-PME`.

    L'INCLUSION, pas un mot commun : « e-commerçants » et « e-commerces »,
    « micro-entreprises » et « micro-crèches » partagent un préfixe sans que
    l'une soit une part de l'autre (relecture du 29/10/2026)."""
    mots_a, mots_b = _mots(a), _mots(b)
    return mots_a < mots_b or mots_b < mots_a


def _extrait(texte: str, debut: int, fin: int) -> str:
    return texte[max(0, debut - 60) : min(len(texte), fin + 60)].replace("\n", " ").strip()


def occurrences(document: DocumentLu) -> list[Occurrence]:
    """Toutes les grandeurs dont l'objet se lit juste après le nombre."""
    # Un document lu sans bandeaux n'a pas de chapitres : `None` partout.
    chapitres_p = document.chapitre_du_paragraphe or [None] * len(document.paragraphes)
    chapitres_c = document.chapitre_de_la_cellule or [None] * len(document.cellules)
    textes = [
        *zip(document.paragraphes, chapitres_p, strict=True),
        *zip(document.cellules, chapitres_c, strict=True),
    ]
    trouvees: list[Occurrence] = []
    for texte, chapitre in textes:
        for motif, unite in ((_POURCENTAGE, " %"), (_EFFECTIF, "")):
            for m in motif.finditer(texte):
                objet = next(g for g in m.groups()[1:] if g)
                cle = _cle(objet)
                brut = _sans_accents(objet).lower()
                # Moins de deux lettres : un reste d'unité (« 1 000 M€ » lu
                # « 1 000 M »), pas un objet. La liste se lit sur le mot BRUT :
                # sur la clé, « dans » serait devenu « dan ».
                if (
                    len(cle) < 2
                    or brut in _PAS_UN_OBJET
                    or cle in _PAS_UN_OBJET
                    or cle.isdigit()
                    or _FIN_DE_PARTICIPE.search(objet)
                    or _EST_UNE_UNITE.fullmatch(objet)
                ):
                    continue
                valeur = re.sub(SPACE_CLASS, " ", m.group(1)) + unite
                if valeur in _TOUT_OU_RIEN:
                    continue
                trouvees.append(Occurrence(
                    valeur=valeur, objet=objet, cle=cle, chapitre=chapitre,
                    extrait=_extrait(texte, m.start(), m.end()),
                    forme=re.sub(SPACE_CLASS, " ", m.group(0)),
                ))
    return trouvees


def controler_objet_des_chiffres(document: DocumentLu) -> list[Anomalie]:
    """Glissements d'objet, objets changés et répétitions — sans jamais bloquer."""
    par_valeur: dict[str, list[Occurrence]] = defaultdict(list)
    for occurrence in occurrences(document):
        par_valeur[occurrence.valeur].append(occurrence)

    anomalies: list[Anomalie] = []
    for valeur, liste in par_valeur.items():
        par_cle: dict[str, list[Occurrence]] = defaultdict(list)
        for occurrence in liste:
            par_cle[occurrence.cle].append(occurrence)

        # La forme de référence est la plus fréquente : c'est elle que le
        # document installe, les autres s'en écartent.
        # Chaque autre forme est comparée à TOUTES celles qui la précèdent, pas
        # à la seule référence : avec `entreprises` en tête, `TPE` et `TPE-PME`
        # sortiraient en deux « objets changés » et le glissement entre elles ne
        # serait jamais nommé.
        cles = sorted(par_cle, key=lambda c: (-len(par_cle[c]), c))
        for rang, autre in enumerate(cles[1:], start=1):
            ecart = par_cle[autre][0]
            parente = next((c for c in cles[:rang] if _apparentes(c, autre)), None)
            modele = par_cle[parente or cles[0]][0]
            if parente is not None:
                anomalies.append(Anomalie(
                    CONTROLE, Gravite.AVERTISSEMENT,
                    f"Glissement : « {valeur} » compte « {modele.objet} » ailleurs "
                    f"(ch. {modele.chapitre or '—'}) et « {ecart.objet} » ici. "
                    "Le chiffre est le même, la population ne l'est plus.",
                    chapitre=ecart.chapitre, extrait=ecart.extrait,
                ))
            else:
                anomalies.append(Anomalie(
                    CONTROLE, Gravite.INFORMATION,
                    f"Objet changé : « {valeur} » compte « {modele.objet} » ailleurs "
                    f"(ch. {modele.chapitre or '—'}) et « {ecart.objet} » ici. "
                    "Deux statistiques distinctes, ou la même mal reprise ?",
                    chapitre=ecart.chapitre, extrait=ecart.extrait,
                ))

        for memes in par_cle.values():
            chapitres = sorted({o.chapitre for o in memes if o.chapitre})
            if len(chapitres) > REPETITION_MAX:
                anomalies.append(Anomalie(
                    CONTROLE, Gravite.INFORMATION,
                    f"Répétition : « {valeur} {memes[0].objet} » revient dans "
                    f"{len(chapitres)} chapitres ({', '.join(map(str, chapitres))}).",
                    chapitre=chapitres[-1], extrait=memes[-1].extrait,
                ))
    return anomalies


@dataclass(frozen=True)
class ChiffreEcrit:
    """Un couple valeur–objet déjà écrit, et les chapitres qui l'emploient."""

    valeur: str
    forme: str
    chapitres: tuple[int, ...]


def chiffres_deja_ecrits(document: DocumentLu) -> list[ChiffreEcrit]:
    """Chaque couple valeur–objet du document, à sa première forme écrite.

    C'est le registre que reçoit le chapitre suivant : le contrôle ci-dessus
    constate un glissement APRÈS coup, ce registre le prévient. Une même
    valeur peut y figurer avec deux objets — « 30 % des femmes », « 30 % des
    hommes » sont deux statistiques —, mais jamais un même couple deux fois.
    Ordre de première apparition.
    """
    premieres: dict[tuple[str, str], Occurrence] = {}
    chapitres: dict[tuple[str, str], set[int]] = defaultdict(set)
    for occurrence in occurrences(document):
        cle = (occurrence.valeur, occurrence.cle)
        premieres.setdefault(cle, occurrence)
        if occurrence.chapitre is not None:
            chapitres[cle].add(occurrence.chapitre)
    return [
        ChiffreEcrit(valeur=o.valeur, forme=o.forme, chapitres=tuple(sorted(chapitres[cle])))
        for cle, o in premieres.items()
    ]

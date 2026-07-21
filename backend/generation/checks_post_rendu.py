"""Checks post-rendu transverses — anti-troncature, anti-doublons, coherence
numerique/textuelle.

Ces controles s'appliquent APRES l'assemblage du document, sur le corpus
final tel qu'il sera livre au client. Contrairement aux strategies par
livrable (`strategies/em.py`, ...) qui portent la logique metier, ces
checks portent sur la QUALITE de rendu — commune a tous les livrables.

Tous les motifs partent d'un defaut REEL nomme par Evangeline sur WAOME
EM v1 (retour 21/07/2026) :

  - « L'annexe est reellement tronquee a la fin de la phrase "aupres des
    prospects grandes mar..." » -> `detecter_troncatures`
  - « Chaque titre de chapitre apparait deux fois, la sous-section 2.4
    apparait deux fois. » -> `detecter_doublons_titres`
  - « "Trois familles de clientele" presente quatre categories. » ->
    `detecter_desaccords_numeriques`
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

# ══════════════════════════════════════════════════════════════════════════
# 1. TRONCATURE
# ══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Troncature:
    """Un chapitre qui se termine sans ponctuation forte."""

    chapitre: int
    titre: str
    fin_capturee: str  # 60 derniers caracteres pour lecture


# Ponctuations acceptees en fin de chapitre. « … » et « : » sont admis
# (fin d'annonce, transition assumee), en revanche « , » ou « ; » ne
# ferment pas une phrase et signalent une coupure.
_PONCTUATION_FIN_VALIDE = frozenset(".!?»…:)]}")

# Une fin de ligne markdown/HTML est acceptable meme sans ponctuation
# quand elle FERME une structure. On NE peut PAS excuser une ligne de
# liste — WAOME l'a montre : la derniere puce du chapitre 21 disait
# « - **Justification :** ... aupres des prospects grandes mar », une
# vraie troncature. Le fait d'etre dans une puce n'exempte pas de finir
# proprement (soit par une ponctuation, soit par une puce suivante).
_STRUCTURES_STRUCTURELLES = (
    re.compile(r"[|+-]\s*$"),                                    # fin de tableau
    re.compile(r"</?[a-zA-Z][^>]*>\s*$"),                        # balise HTML
    re.compile(r"```\s*$"),                                       # fin de code fence
)


def _dernier_mot_est_tronque(dernier_mot: str) -> bool:
    """Un mot final court sans ponctuation est probablement tronque.

    Une phrase francaise se termine rarement sur un mot de 2-3 lettres.
    « et », « ou », « du », « en » sont des mots-outils qui INTRODUISENT
    ce qui suit, donc ne devraient jamais etre les derniers d'un
    chapitre. « mar », « fon », « prop » sont visiblement tronques.
    """
    if len(dernier_mot) >= 5:
        return False
    # Blancs, chiffres purs (« 2024 ») et unites (« M€ ») ne sont pas
    # des mots tronques.
    if not dernier_mot or dernier_mot.isdigit():
        return False
    if dernier_mot.lower() in {
        "an", "ans", "eur", "usd", "mois", "jour", "site", "hors",
        "hall", "pack", "menu", "gaz", "flux", "tva",
    }:
        return False
    return True


def detecter_troncatures(
    sections: list[tuple[int, str, str]]
) -> list[Troncature]:
    """Chaque section doit se terminer proprement.

    Trois motifs de troncature retenus :
      1. Corps entierement vide (ou blanc) — chapitre avorte.
      2. Derniere ligne non structurelle ne finissant pas par une
         ponctuation forte.
      3. Dernier mot court (< 5 lettres) hors mots-outils reconnus,
         indiquant probablement une coupure a mi-mot (« mar »).
    """
    troncatures: list[Troncature] = []
    for numero, titre, corps in sections:
        corps_nettoye = corps.rstrip()
        if not corps_nettoye:
            troncatures.append(Troncature(
                chapitre=numero, titre=titre, fin_capturee="(vide)",
            ))
            continue

        # Structure en fin (tableau, liste, code, HTML) ? On accepte.
        derniere_ligne = corps_nettoye.split("\n")[-1].rstrip()
        if any(m.search(derniere_ligne) for m in _STRUCTURES_STRUCTURELLES):
            continue

        dernier_char = corps_nettoye[-1]
        fin_capture = corps_nettoye[-60:].replace("\n", " ")

        if dernier_char in _PONCTUATION_FIN_VALIDE:
            continue

        # Pas de ponctuation forte : verifier si le dernier MOT est
        # visiblement tronque. Un mot moyen/long sans ponctuation reste
        # une coupure, mais un mot court est un signal plus fort encore.
        mots = re.findall(r"[\wÀ-ÿ]+", corps_nettoye)
        dernier_mot = mots[-1] if mots else ""
        if _dernier_mot_est_tronque(dernier_mot):
            troncatures.append(Troncature(
                chapitre=numero, titre=titre, fin_capturee=fin_capture,
            ))
            continue

        # Dernier mot suffisamment long mais sans ponctuation : toujours
        # une coupure suspecte pour un livrable client.
        troncatures.append(Troncature(
            chapitre=numero, titre=titre, fin_capturee=fin_capture,
        ))
    return troncatures


# ══════════════════════════════════════════════════════════════════════════
# 2. DOUBLONS DE TITRES
# ══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class DoublonTitre:
    """Un titre apparait plus d'une fois dans le meme chapitre."""

    chapitre: int
    intitule: str
    occurrences: int


# Un titre markdown : `# X`, `## X`, `### X` — on capture le niveau (nombre
# de `#`) et l'intitule normalise (trim, sans numerotation initiale).
_TITRE_MD_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def _normaliser_intitule(brut: str) -> str:
    """Enleve la numerotation initiale et normalise les espaces pour
    reconnaitre « 22. Sources » et « Sources » comme le meme titre."""
    sans_num = re.sub(r"^\d+(?:\.\d+)*\s*[—\-–\.\)]?\s*", "", brut)
    return re.sub(r"\s+", " ", sans_num).strip().lower()


def detecter_doublons_titres(
    sections: list[tuple[int, str, str]]
) -> list[DoublonTitre]:
    """Cherche les intitules qui apparaissent 2+ fois dans un CHAPITRE.

    On compare chapitre par chapitre (pas cross-chapitres) pour eviter
    les faux positifs sur les titres generiques (« Synthese », « Sources »)
    qu'on retrouve legitimement dans plusieurs chapitres.
    """
    doublons: list[DoublonTitre] = []
    for numero, _titre, corps in sections:
        compte: Counter[str] = Counter()
        # On retient l'intitule normalise ET l'intitule affiche.
        affichage: dict[str, str] = {}
        for m in _TITRE_MD_RE.finditer(corps):
            intitule_norm = _normaliser_intitule(m.group(2))
            if not intitule_norm:
                continue
            compte[intitule_norm] += 1
            affichage.setdefault(intitule_norm, m.group(2).strip())
        for intitule_norm, n in compte.items():
            if n >= 2:
                doublons.append(DoublonTitre(
                    chapitre=numero,
                    intitule=affichage[intitule_norm],
                    occurrences=n,
                ))
    return doublons


# ══════════════════════════════════════════════════════════════════════════
# 3. DESACCORDS NUMERIQUE / TEXTUEL
# ══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class DesaccordNumerique:
    """Une annonce quantitative (« trois X ») ne correspond pas au compte
    reel d'items qui suivent."""

    chapitre: int
    detail: str


# Nombres en toutes lettres qu'on reconnait pour verifier le compte.
_NOMBRES_LETTRES: dict[str, int] = {
    "un": 1, "une": 1,
    "deux": 2,
    "trois": 3,
    "quatre": 4,
    "cinq": 5,
    "six": 6,
    "sept": 7,
    "huit": 8,
    "neuf": 9,
    "dix": 10,
}

# « trois familles », « quatre segments », « cinq piliers »... Le mot qui
# suit doit etre au pluriel et designer une CATEGORIE structurelle du
# document, pas une donnee chiffree (« 3 M€ »).
_NOMS_STRUCTURELS = (
    "famille", "familles",
    "segment", "segments",
    "categorie", "categories",
    "pilier", "piliers",
    "axe", "axes",
    "niveau", "niveaux",
    "critere", "criteres",
    "grande", "grandes",  # « trois grandes categories »
    "type", "types",
    "groupe", "groupes",
    "chapitre", "chapitres",
    "etape", "etapes",
    "phase", "phases",
)


def _construire_motif_annonce() -> re.Pattern[str]:
    nombres = "|".join(_NOMBRES_LETTRES.keys())
    noms = "|".join(re.escape(n) for n in _NOMS_STRUCTURELS)
    return re.compile(
        rf"\b({nombres})\s+({noms})\b[^:.\n]{{0,60}}[:.]",
        re.IGNORECASE,
    )


_ANNONCE_RE = _construire_motif_annonce()
_ITEM_LISTE_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+\S", re.MULTILINE)


def detecter_desaccords_numeriques(
    sections: list[tuple[int, str, str]]
) -> list[DesaccordNumerique]:
    """Verifie que « N X » est suivi d'exactement N items de liste.

    Approche pragmatique : on cherche « trois X », puis on compte les
    items de liste dans les 500 caracteres qui suivent. Ecart = defaut.
    """
    desaccords: list[DesaccordNumerique] = []
    for numero, _titre, corps in sections:
        for m in _ANNONCE_RE.finditer(corps):
            nombre_annonce = _NOMBRES_LETTRES[m.group(1).lower()]
            nom = m.group(2).lower()
            # Fenetre : depuis la fin du match jusqu'au prochain double
            # saut de ligne suivi d'un non-item, ou 500 chars max.
            fenetre = corps[m.end() : m.end() + 500]
            # On s'arrete au prochain titre H1/H2/H3 pour ne pas compter
            # les items du chapitre suivant.
            fin_titre = re.search(r"\n#{1,6}\s", fenetre)
            if fin_titre:
                fenetre = fenetre[: fin_titre.start()]
            n_items = len(_ITEM_LISTE_RE.findall(fenetre))
            if n_items == 0 or n_items == nombre_annonce:
                continue
            desaccords.append(DesaccordNumerique(
                chapitre=numero,
                detail=(
                    f"Annonce « {m.group(1)} {nom} » suivie de {n_items} items "
                    f"de liste. Le compte ne correspond pas au chiffre annonce."
                ),
            ))
    return desaccords


__all__ = [
    "DesaccordNumerique",
    "DoublonTitre",
    "Troncature",
    "detecter_desaccords_numeriques",
    "detecter_doublons_titres",
    "detecter_troncatures",
]


# Deduplique le type d'import — evite l'avertissement sur `defaultdict`
# quand un check en aurait besoin plus tard.
_ = defaultdict

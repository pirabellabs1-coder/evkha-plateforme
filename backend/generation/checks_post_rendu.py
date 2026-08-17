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
#: Une ligne ENTIEREMENT en gras est un TITRE, et un titre ne prend pas de
#: ponctuation finale.
#:
#: EXPORTEE, et c'est le point : `qa.py` jugeait la meme question de son cote,
#: avec une expression qui acceptait les asterisques OUVRANTES et pas les
#: FERMANTES. « **CRITERE DE SELECTION BTOB** » passait donc pour de la prose
#: la-bas et pour un titre ici — deux avis sur la meme ligne (regle 5), et
#: c'est le mauvais qui bloquait la livraison.
TITRE_EN_GRAS = re.compile(r"^\s*\*{2}[^*]+\*{2}\s*$")

_STRUCTURES_STRUCTURELLES = (
    re.compile(r"[|+-]\s*$"),                                    # fin de tableau
    re.compile(r"</?[a-zA-Z][^>]*>\s*$"),                        # balise HTML
    re.compile(r"```\s*$"),                                       # fin de code fence
    # Marqueur graphique du moteur structuré : un `BlocGraphique` sérialisé
    # par `payload_vers_markdown`, résolu en figure au rendu. Un chapitre a le
    # DROIT de se fermer sur une figure — le contrat le permet — et le job
    # réel `026fecea` (10/08/2026) s'est fait compter « tronqué » pour avoir
    # terminé « Sources et méthodologie » sur son graphique tarifaire. Motif
    # faux : rien n'était perdu, le rendu allait dessiner la figure.
    re.compile(r"-->\s*$"),                                       # fin de commentaire
    # Une ligne qui se termine par une URL complète est une ligne complète :
    # « … rachat bijoux Paris depuis 1977 — https://www.interor.fr/ » est une
    # référence de source, pas une phrase coupée. Le même recontrôle l'a
    # comptée « perte probable de contenu client ». Le risque résiduel — une
    # troncature qui tomberait PILE à la fin d'une URL valide — est accepté :
    # l'inverse condamne chaque liste de sources du contrat.
    re.compile(r"https?://\S+/?\s*$"),                            # référence sourcée
    # Une ligne ENTIÈREMENT en gras est un TITRE, et un titre ne prend pas de
    # point final. Le nettoyage des fioritures retirait les astérisques puis
    # jugeait « Lecture de la fiche projet » comme une phrase inachevée.
    #
    # Cette règle vit désormais dans `TITRE_EN_GRAS`, plus bas : `qa.py` la
    # cherchait de son côté et ne la trouvait pas (règle 5).
    #
    # Relevé par la cliente le 13/08/2026, sur un chapitre retenu pour ce seul
    # motif : « pourquoi c'est à nous de corriger ? ». Elle a raison — faire
    # relire « il manque un point » à quelqu'un qui a payé un livrable est
    # l'inverse d'un service, et le motif était FAUX en plus d'être trivial.
    #
    # La distinction tient : une vraie troncature — « auprès des prospects
    # grandes mar » — n'est jamais encadrée par des astérisques.
    TITRE_EN_GRAS,                                                # titre en gras
)


# Marqueurs d'emphase markdown qui FERMENT le texte apres la ponctuation.
# Un encadre en italique se termine par « ... la structure.* » : le point est
# bien la, le « * » n'est qu'un delimiteur. Sans ce nettoyage, la generation
# reelle du 24/07/2026 (job 4c573e40) faisait remonter le chapitre 6 comme
# tronque alors qu'il etait complet.
_FIORITURES_FINALES = "*_`\"'"


def sans_fioritures_finales(texte: str) -> str:
    """Retire les delimiteurs d'emphase/citation en toute fin de texte.

    Ne touche pas aux ponctuations : « » et … restent des fins valides.
    """
    return texte.rstrip().rstrip(_FIORITURES_FINALES).rstrip()


def sans_emphase(texte: str) -> str:
    """Le TEXTE d'une ligne, debarrasse de ses delimiteurs aux DEUX bouts.

    `sans_fioritures_finales` ne nettoie que la queue, ce qui suffit pour juger
    d'une ponctuation finale. Pour juger de la NATURE d'une ligne — titre,
    source, phrase — il faut la lire entiere : une expression ancree sur `$` ne
    reconnait pas « **CRITERE DE SELECTION BTOB** » si elle n'a prevu que
    l'asterisque de gauche. C'est ce qui a bloque l'etude `f0064333` du
    17/08/2026.

    Meme liste de delimiteurs que ci-dessus, et deliberement : deux listes
    d'asterisques finiraient par diverger (regle 5).
    """
    return texte.strip().strip(_FIORITURES_FINALES).strip()


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

        # Un encadre en italique ou une citation ferme APRES la ponctuation :
        # on juge le texte, pas le delimiteur.
        corps_nettoye = sans_fioritures_finales(corps_nettoye) or corps_nettoye
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


# ══════════════════════════════════════════════════════════════════════════
# 4. SOURCES TRACABLES — chaque source citee doit etre verifiable
# ══════════════════════════════════════════════════════════════════════════
#
# Retour Evangeline WAOME EM v1 (21/07/2026) : « les sources listees ne sont
# pas verifiables, plusieurs manquent d'URL, une reference "Maisons du Monde
# privatisation 2023" est factuellement fausse ». Sous contract SaaS, un
# livrable rempli de sources bidon sort tel quel chez le client.
#
# Trois signaux distincts, chacun independent, categorie unique
# `sources_non_tracables` cote gate :
#   - chapitre Sources absent ou vide,
#   - ratio URLs / puces < 50 % (majorite non tracable),
#   - URLs manifestement bidon (example.com, source.fr, placeholder).


@dataclass(frozen=True)
class SourceNonTracable:
    """Un defaut de tracabilite dans le chapitre Sources."""

    chapitre: int
    motif: str  # « absent », « vide », « ratio_faible », « url_bidon »
    detail: str


# Un chapitre est identifie comme « Sources » si son titre commence par
# « Source » ou « Sources » — les blueprints EM/EC/BP/STR utilisent
# « Sources et methodologie », d'autres variantes plausibles sont tolerees.
_TITRE_SOURCES_RE = re.compile(r"^\s*sources?\b", re.IGNORECASE)

# Une puce de source markdown : `- `, `* `, `• `, ou numerotee.
_PUCE_SOURCE_RE = re.compile(r"^\s*(?:[-•*]|\d+\.)\s+\S", re.MULTILINE)

# URL http(s) trouvee dans la puce.
_URL_RE = re.compile(r"https?://[^\s\)\]\<\>»,]+", re.IGNORECASE)

# URLs manifestement bidon. RFC 2606 reserve example.com/net/org et .example
# aux exemples ; « source.fr » et variantes sont des placeholders inventes ;
# les crochets `[...]` signalent un template non substitue.
_URL_BIDON_RE = re.compile(
    r"://(?:www\.)?example\.(?:com|net|org|fr)"
    r"|://(?:www\.)?sources?\.fr\b"
    r"|://(?:www\.)?placeholder\."
    r"|://(?:www\.)?(?:xxx|aaa|test|dummy|todo)\."
    r"|://\S*\[",  # crochets = template
    re.IGNORECASE,
)

# Seuil minimal de tracabilite. Un chapitre Sources avec moins de la moitie
# de ses puces liees a une URL est majoritairement non verifiable.
# Regle 4 : viser la classe, pas l'exemple — un ratio strict (100 % URL)
# ferait remonter les documents client legitimes sans lien.
_RATIO_URL_MINIMAL = 0.5

# En-dessous de ce nombre absolu d'URLs reelles, un livrable n'est pas
# credible cote source, meme si le ratio est bon (peu de puces au total).
_MIN_URLS_ABSOLUES = 2


def _trouver_chapitre_sources(
    sections: list[tuple[int, str, str]],
) -> tuple[int, str, str] | None:
    """Retourne la section identifiee comme le chapitre Sources.

    Convention blueprints : le chapitre s'appelle « Sources » ou
    « Sources et methodologie ». Si plusieurs matches (cas theorique), on
    retient le dernier — le plus recent dans l'ordre du document est
    generalement celui qui recapitule.
    """
    candidats = [
        s for s in sections if _TITRE_SOURCES_RE.match(s[1] or "")
    ]
    return candidats[-1] if candidats else None


def detecter_sources_non_tracables(
    sections: list[tuple[int, str, str]],
) -> list[SourceNonTracable]:
    """Verifie que le chapitre Sources contient des references verifiables.

    Trois branches independantes signalent chacune leur defaut :
      - chapitre absent : livrable sans source du tout, tres grave.
      - chapitre vide : chapitre ecrit mais rien ne suit le titre.
      - ratio URLs / puces < seuil : majorite non tracable (cas WAOME).
      - URLs bidon detectees : hallucination du modele.

    Silencieux si le chapitre Sources n'est pas identifiable par titre —
    on ne signale pas un chapitre qui n'a jamais eu vocation a lister
    des sources (regle 4 : eviter les faux positifs sur les blueprints
    qui n'ont pas de chapitre Sources).
    """
    defauts: list[SourceNonTracable] = []

    sources_section = _trouver_chapitre_sources(sections)
    if sources_section is None:
        # Si AUCUN chapitre du document n'a un titre "Sources", c'est
        # signale UNE fois — le livrable n'est source par personne.
        # On imprime le probleme au chapitre max+1 pour rester lisible.
        max_num = max((s[0] for s in sections), default=0)
        defauts.append(SourceNonTracable(
            chapitre=max_num,
            motif="absent",
            detail=(
                "Aucun chapitre « Sources » identifie dans le document. Un "
                "livrable EVKHA sans chapitre de sources n'est pas verifiable "
                "et ne peut pas etre delivre a un banquier."
            ),
        ))
        return defauts

    numero, titre, corps = sources_section
    puces = _PUCE_SOURCE_RE.findall(corps)
    if not puces:
        defauts.append(SourceNonTracable(
            chapitre=numero,
            motif="vide",
            detail=(
                f"Chapitre « {titre} » vide : aucune source listee. Le "
                "document cite des chiffres sans reference verifiable."
            ),
        ))
        return defauts

    urls = _URL_RE.findall(corps)
    urls_bidon = [u for u in urls if _URL_BIDON_RE.search(u)]
    urls_valides = [u for u in urls if not _URL_BIDON_RE.search(u)]

    if urls_bidon:
        exemples = ", ".join(urls_bidon[:3])
        defauts.append(SourceNonTracable(
            chapitre=numero,
            motif="url_bidon",
            detail=(
                f"URL(s) placeholder ou factice(s) detectee(s) dans « {titre} » : "
                f"{exemples}. Ces URLs sont des exemples reserves (example.com, "
                "source.fr, crochets non substitues) ou n'existent pas. Cas WAOME "
                "confirme : hallucination de source, remplace par une reference "
                "reelle ou une hypothese assumee."
            ),
        ))

    n_puces = len(puces)
    n_urls_valides = len(urls_valides)
    ratio = n_urls_valides / n_puces if n_puces else 0.0

    if ratio < _RATIO_URL_MINIMAL or n_urls_valides < _MIN_URLS_ABSOLUES:
        defauts.append(SourceNonTracable(
            chapitre=numero,
            motif="ratio_faible",
            detail=(
                f"Chapitre « {titre} » : {n_urls_valides} URL(s) verifiable(s) "
                f"pour {n_puces} source(s) listee(s) (ratio "
                f"{ratio:.0%}). Un banquier attend au moins la moitie des "
                "sources avec un lien reel (documents client sans URL "
                "acceptes, mais pas comme majorite). Cas WAOME : Evangeline "
                "a signale que la moitie des sources n'etaient pas verifiables."
            ),
        ))

    return defauts


# ══════════════════════════════════════════════════════════════════════════
# 5. TON NEUTRE — bannir les superlatifs marketing
# ══════════════════════════════════════════════════════════════════════════
#
# Retour Evangeline WAOME EM v1 (21/07/2026) : « le ton est trop
# publicitaire, on lit du plaquette commerciale ». Un banquier disqualifie
# un dossier qui vend au lieu de decrire.
#
# La liste noire cible des expressions bi-mots — « leader incontestable »,
# « solution revolutionnaire », « unique en son genre » — pas les mots
# isoles (« leader » factuellement utilise reste legitime, regle 4).


@dataclass(frozen=True)
class TonPublicitaire:
    """Une expression au ton publicitaire dans un chapitre editorial."""

    chapitre: int
    expression: str  # extrait exact fautif
    extrait: str     # contexte 60 chars autour


# Chaque motif capture une locution superlative typique d'un contenu
# marketing. On evite les mots seuls trop generiques (« leader » factuel).
_MOTIFS_TON_PUB: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("leader incontestable",
     re.compile(r"\bleader\s+incontest(?:able|e)\b", re.IGNORECASE)),
    ("leader incontestable",  # variante orthographique
     re.compile(r"\bleader\s+incontestable\b", re.IGNORECASE)),
    ("unique en son genre",
     re.compile(r"\bunique\s+en\s+son\s+genre\b", re.IGNORECASE)),
    ("revolutionnaire",
     re.compile(r"\br[eé]volutionnaire\b", re.IGNORECASE)),
    ("incontournable",
     re.compile(r"\bincontournable\b", re.IGNORECASE)),
    ("solution unique",
     re.compile(r"\bsolution\s+unique\b", re.IGNORECASE)),
    ("offre inegalee",
     re.compile(r"\boffre\s+in[eé]gal[eé]e?\b", re.IGNORECASE)),
    ("sans equivalent sur le marche",
     re.compile(r"\bsans\s+[eé]quivalent(?:\s+sur\s+le\s+march[eé])?\b", re.IGNORECASE)),
    ("100 % [pretention]",
     re.compile(r"\b100\s*%\s+(?:garanti|sur\s+mesure|innovant)\b", re.IGNORECASE)),
    ("meilleur(e) du marche",
     re.compile(r"\bmeilleur[e]?\s+(?:du|de\s+la|des)\s+march[eé]s?\b", re.IGNORECASE)),
    ("acteur majeur incontournable",
     re.compile(r"\bacteur\s+(?:majeur|cle)\s+incontournable\b", re.IGNORECASE)),
    ("disruptif",
     re.compile(r"\bdisruptif[ve]?\b", re.IGNORECASE)),
    ("game changer",
     re.compile(r"\bgame[\-\s]changer\b", re.IGNORECASE)),
)

# Titres de chapitre exemptes du check (le ton editorial ne s'y applique
# pas — Sources cite des titres externes, Fiche projet reprend le brief).
_TITRE_EXEMPT_TON_RE = re.compile(r"^\s*(?:sources?|fiche\s+projet)\b", re.IGNORECASE)


def detecter_ton_publicitaire(
    corpus_par_chapitre: dict[int, str],
    *,
    titres_par_chapitre: dict[int, str] | None = None,
) -> list[TonPublicitaire]:
    """Chaque chapitre editorial doit rester descriptif — pas de superlatif.

    `titres_par_chapitre` permet d'exempter Sources / Fiche projet du
    check, ces chapitres citant des titres ou reprenant le brief. Si
    non fourni, aucun chapitre n'est exempte : tolerance ouverte pour les
    appels tests unitaires.
    """
    titres = titres_par_chapitre or {}
    defauts: list[TonPublicitaire] = []
    for numero, corps in corpus_par_chapitre.items():
        titre = titres.get(numero, "")
        if _TITRE_EXEMPT_TON_RE.match(titre):
            continue
        for _label, motif in _MOTIFS_TON_PUB:
            for m in motif.finditer(corps):
                debut = max(0, m.start() - 30)
                fin = min(len(corps), m.end() + 30)
                extrait = corps[debut:fin].replace("\n", " ")
                defauts.append(TonPublicitaire(
                    chapitre=numero,
                    expression=m.group(0),
                    extrait=extrait,
                ))
    return defauts


# ══════════════════════════════════════════════════════════════════════════
# 6. PRUDENCE JURIDIQUE — evenements corporate + risque diffamation
# ══════════════════════════════════════════════════════════════════════════
#
# Retour Evangeline WAOME EM v1 (21/07/2026) : « Maisons du Monde n'a pas
# ete privatisee en 2023, c'est factuellement faux — un livrable sous ma
# marque avec cette erreur m'expose personnellement ». Sous contract SaaS
# (aucune relecture), un fait faux sur un tiers ou une accusation
# non sourcee expose EVKHA au risque juridique.
#
# On ne verifie pas la verite du fait (impossible offline). On exige
# qu'il soit source dans les caracteres environnants. Le fait faux
# tombe (le modele n'a pas d'URL), le fait vrai mal argumente aussi.


@dataclass(frozen=True)
class RisqueJuridique:
    """Une affirmation sensible sans source verifiable adjacente."""

    chapitre: int
    categorie: str  # « evenement_corporate » | « diffamation »
    expression: str
    extrait: str
    detail: str


# Evenements corporate dates : X (verbe) en YYYY. On tolere l'annee
# ecrite en toutes lettres a la marge : la forme numerique YYYY est la
# plus frequente et la plus verifiable.
_EVT_CORPORATE_VERBES = (
    r"(?:a\s+ete|s['’]est|est)?\s*"
    r"(?:privatis[eé]e?|nationalis[eé]e?|rachet[eé]e?|"
    r"acquis[e]?|fusionn[eé]e?|introduit[e]?\s+en\s+bourse|"
    r"delist[eé]e?|liquid[eé]e?|plac[eé]e?\s+en\s+redressement|"
    r"a\s+fait\s+faillite|en\s+cessation\s+de\s+paiement)"
)
_EVT_CORPORATE_RE = re.compile(
    rf"\b{_EVT_CORPORATE_VERBES}\b[^.\n]{{0,60}}?\ben\s+(?:19|20)\d{{2}}\b",
    re.IGNORECASE,
)

# Diffamation potentielle : accusation non datee mais grave.
_DIFFAMATION_MOTIFS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("condamne pour",
     re.compile(r"\bcondamn[eé]e?s?\s+(?:pour|par)\b", re.IGNORECASE)),
    ("pratiques anticoncurrentielles",
     re.compile(r"\bpratiques?\s+anticoncurrentielles?\b", re.IGNORECASE)),
    ("abus de position dominante",
     re.compile(r"\babus\s+de\s+position\s+dominante\b", re.IGNORECASE)),
    ("sanction AMF/CNIL/DGCCRF",
     re.compile(
         r"\bsanction(?:n[eé]e?)?\s+par\s+(?:l['’]?AMF|la\s+CNIL|la\s+DGCCRF)\b",
         re.IGNORECASE,
     )),
    ("poursuivi en justice",
     re.compile(r"\bpoursuivi[e]?s?\s+en\s+justice\b", re.IGNORECASE)),
    ("faillite",
     re.compile(r"\ba\s+fait\s+faillite\b|\ben\s+faillite\b", re.IGNORECASE)),
)

_URL_ADJACENTE_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_MOTS_SOURCE_RE = re.compile(
    r"\bselon\b|\bd['’]apr[eè]s\b|\brapport(?:e)?\b|\btemoigne\b"
    r"|(?:19|20)\d{2}[\)\s]",  # « (Xerfi 2024) » suffit comme source proche
    re.IGNORECASE,
)

# Fenetre autour d'une affirmation ou l'on cherche une source.
_FENETRE_SOURCE = 350


def _est_source(fenetre: str) -> bool:
    """Une source est jugee presente dans la fenetre si :
      - une URL http(s) apparait, OU
      - une locution de citation (« selon », « d'apres », « rapporte »)
        accompagnee d'un nom propre + annee.
    """
    if _URL_ADJACENTE_RE.search(fenetre):
        return True
    # « selon Les Echos », « d'apres Xerfi 2024 », etc. — motif
    # « [locution] [Nom propre] »
    if re.search(
        r"\b(?:selon|d['’]apr[eè]s|rapport[eé]?\s+par)\s+[A-Z][A-Za-zÀ-ÿ\-]+",
        fenetre,
    ):
        return True
    return False


def detecter_prudence_juridique(
    corpus_par_chapitre: dict[int, str],
    *,
    titres_par_chapitre: dict[int, str] | None = None,
) -> list[RisqueJuridique]:
    """Chaque affirmation sensible (evenement corporate date OU
    formulation de type diffamation) doit avoir une source dans une
    fenetre de +/- 350 chars. Sinon, signal.

    Le chapitre Sources est exempte (il cite des titres externes).
    """
    titres = titres_par_chapitre or {}
    defauts: list[RisqueJuridique] = []
    for numero, corps in corpus_par_chapitre.items():
        titre = titres.get(numero, "")
        if _TITRE_EXEMPT_TON_RE.match(titre):
            continue

        for m in _EVT_CORPORATE_RE.finditer(corps):
            debut = max(0, m.start() - _FENETRE_SOURCE)
            fin = min(len(corps), m.end() + _FENETRE_SOURCE)
            fenetre = corps[debut:fin]
            if _est_source(fenetre):
                continue
            extrait_debut = max(0, m.start() - 40)
            extrait_fin = min(len(corps), m.end() + 40)
            defauts.append(RisqueJuridique(
                chapitre=numero,
                categorie="evenement_corporate",
                expression=m.group(0),
                extrait=corps[extrait_debut:extrait_fin].replace("\n", " "),
                detail=(
                    f"Evenement corporate date sans source : « {m.group(0)} ». "
                    "Un livrable EVKHA ne peut pas affirmer qu'une entreprise "
                    "tierce a ete privatisee/rachetee/liquidee sans citer la "
                    "source (URL ou « selon Xerfi 2024 »). Cas WAOME confirme : "
                    "Evangeline a signale une affirmation factuellement fausse "
                    "sur Maisons du Monde privatisation 2023."
                ),
            ))

        for label, motif in _DIFFAMATION_MOTIFS:
            for m in motif.finditer(corps):
                debut = max(0, m.start() - _FENETRE_SOURCE)
                fin = min(len(corps), m.end() + _FENETRE_SOURCE)
                fenetre = corps[debut:fin]
                if _est_source(fenetre):
                    continue
                extrait_debut = max(0, m.start() - 40)
                extrait_fin = min(len(corps), m.end() + 40)
                defauts.append(RisqueJuridique(
                    chapitre=numero,
                    categorie="diffamation",
                    expression=label,
                    extrait=corps[extrait_debut:extrait_fin].replace("\n", " "),
                    detail=(
                        f"Formulation a risque juridique detectee « {label} » "
                        "sans source verifiable adjacente. Attribuer une "
                        "condamnation, un abus de position dominante ou une "
                        "faillite a un tiers expose EVKHA au risque de "
                        "diffamation — exiger une URL ou une citation "
                        "« selon [organisme] »."
                    ),
                ))

    return defauts


__all__ = [
    "DesaccordNumerique",
    "DoublonTitre",
    "RisqueJuridique",
    "SourceNonTracable",
    "TonPublicitaire",
    "Troncature",
    "detecter_desaccords_numeriques",
    "detecter_doublons_titres",
    "detecter_prudence_juridique",
    "detecter_sources_non_tracables",
    "detecter_ton_publicitaire",
    "detecter_troncatures",
]


# Deduplique le type d'import — evite l'avertissement sur `defaultdict`
# quand un check en aurait besoin plus tard.
_ = defaultdict


# ══════════════════════════════════════════════════════════════════════════
# 7. UNE DEMANDE DÉCLARÉE « NON TRAITÉE » QUI EST POURTANT TRAITÉE
# ══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class DemandeContredite:
    """Le document se contredit sur le sort d'une demande du client."""

    chapitre: int
    demande: str
    ailleurs: int
    detail: str


#: Mots trop courants pour distinguer un sujet d'un autre. Sans ce filtre, la
#: moindre demande partagerait ses mots avec tout le document et chaque statut
#: « non traité » serait signalé — un contrôle qui crie toujours ne contrôle
#: plus rien.
_MOTS_TROP_COURANTS = frozenset({
    "client", "clients", "marche", "marché", "projet", "etude", "étude",
    "donnees", "données", "analyse", "analyser", "chapitre", "document",
    "secteur", "France", "france", "entreprise", "entreprises", "acteurs",
    "concurrents", "concurrent", "demande", "demandes", "information",
    "informations", "elements", "éléments", "point", "points", "partie",
})

#: Une ligne qui statue « non traitée » sur une demande.
_NON_TRAITE_RE = re.compile(r"non\s+trait[ée]e?s?\b", re.IGNORECASE)

#: Un mot assez long pour porter un sujet. « canaux », « acquisition »,
#: « fidélité » — pas « des », « pour », « avec ».
_MOT_PORTEUR_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]{6,}")

#: Combien de mots porteurs doivent se retrouver ailleurs pour conclure à la
#: contradiction. DEUX, et non un : un seul mot commun arrive par hasard,
#: deux mots longs d'une même demande, non.
_MOTS_COMMUNS_MIN = 2

#: Ce qui SÉPARE deux demandes écrites sur une même ligne.
#:
#: Une fenêtre en nombre de signes ne suffit pas : la doublure de la
#: répétition à blanc empile trois demandes sur une ligne, et cent-vingt
#: signes avant « non traitée » ramassaient la précédente — « la comparaison
#: tarifaire couvre trois acteurs, voie de complément proposée en annexe ».
#: Quatre mots, aucun du sujet jugé, et les quatre livrables signalés à tort.
#:
#: Le deux-points est ABSENT de la liste, volontairement : c'est lui qui
#: introduit le plus souvent le statut — « analyser les canaux d'acquisition
#: des concurrents : non traitée » — et couper dessus effacerait le sujet
#: qu'on cherche.
_FRONTIERES_DE_DEMANDE = (". ", " — ", " – ", "; ", "• ", "\t")


def detecter_demandes_contredites(
    sections: list[tuple[int, str, str]],
) -> list[DemandeContredite]:
    """Un sujet déclaré « non traité » alors que le document le traite.

    ## Le défaut, signalé sur une étude notée 8,5/10

    Cliente, 11/08/2026 : « les canaux d'acquisition sont bien analysés au
    chapitre 3 puis déclarés "non traités" au chapitre 8 ; on dirait que ça ne
    l'a pas pris en compte, et avoir un point non traité n'est pas très
    acceptable dans une étude qui dit qu'elle va le faire ».

    Elle a raison sur le fond : un point annoncé puis déclaré non traité est
    pire qu'un point absent — il fait douter de tout le reste.

    ## Pourquoi ce contrôle vaut pour les QUATRE livrables

    Le chapitre de validation des demandes existe partout : étude
    concurrentielle 8, stratégie 19, étude de marché 22, business plan 20. Le
    contrôle des statuts, lui, ne vivait que dans la strategy EC, et il
    vérifiait seulement qu'UN statut existe — jamais qu'il soit vrai. La
    contradiction est une classe, pas un cas (règle 4).

    ## Comment il évite de crier à tort

    Une ligne « non traitée » livre ses mots PORTEURS — six lettres au moins,
    hors vocabulaire commun à toute étude. Il en faut DEUX retrouvés dans un
    autre chapitre pour conclure : un mot isolé se croise par hasard, deux
    mots longs d'une même demande, non.

    Le contrôle ne lit pas le SENS : il ne saura jamais qu'un sujet a été
    survolé plutôt que traité. Il attrape la contradiction franche, celle que
    la cliente a vue — et il le dit, plutôt que de laisser croire à une
    garantie plus large (règle 1 dans l'autre sens).
    """
    # Le texte de chaque section, replié une seule fois. Le reconstruire à
    # chaque tour rejoignait tout le document autant de fois qu'il a de
    # chapitres — et surtout, on a besoin du DÉCOUPAGE pour compter dans
    # combien de chapitres un mot apparaît, pas seulement s'il apparaît.
    replies = [(numero, corps.casefold()) for numero, _titre, corps in sections]

    defauts: list[DemandeContredite] = []
    for numero, _titre, corps in sections:
        autres = [(n, texte) for n, texte in replies if n != numero]
        if not autres:
            continue

        # Un mot présent dans la MOITIÉ des autres chapitres ne désigne aucun
        # sujet : c'est un mot de liaison.
        #
        # Business plan `5c5e91b9` (12/08/2026) : le contrôle a conclu à une
        # contradiction au chapitre 20 sur « chaque, chiffrée, explicite,
        # manque ». Quatre mots de six lettres ou plus, absents de la liste des
        # mots trop courants — et présents dans presque tous les chapitres d'un
        # document de vingt-deux. Le motif était faux.
        #
        # Rallonger la liste aurait été réparer l'instance : on ne connaît pas
        # les quatre mots suivants. La DISTINCTIVITÉ, elle, se mesure — et un
        # sujet réellement traité ailleurs ne sature pas le document entier,
        # là où un mot de liaison le fait toujours (règle 4).
        plafond = max(1, len(autres) // 2)
        defauts.extend(
            _contradictions_de_la_section(numero, corps, autres, plafond)
        )
    return defauts


#: Distance sous laquelle deux mots appartiennent encore a la meme locution.
#: « canaux d'acquisition des concurrents » tient en moins de cent caracteres ;
#: deux verbes pris a deux paragraphes d'ecart, non.
_VOISINAGE_D_UN_SUJET = 100


def _se_touchent(mots: list[str], texte: str) -> bool:
    """Vrai si deux de ces mots se retrouvent cote a cote dans ce chapitre."""
    positions: list[tuple[int, str]] = [
        (occurrence.start(), mot)
        for mot in mots
        for occurrence in re.finditer(re.escape(mot), texte)
    ]
    positions.sort()
    return any(
        suivant[0] - courant[0] <= _VOISINAGE_D_UN_SUJET and suivant[1] != courant[1]
        for courant, suivant in zip(positions, positions[1:], strict=False)
    )


def _contradictions_de_la_section(
    numero: int,
    corps: str,
    autres: list[tuple[int, str]],
    plafond: int,
) -> list[DemandeContredite]:
    """Les demandes de CE chapitre que le reste du document contredit."""
    defauts: list[DemandeContredite] = []
    for ligne in corps.splitlines():
        trouve = _NON_TRAITE_RE.search(ligne)
        if trouve is None:
            continue
        # Le SUJET précède le statut : « Analyser les canaux d'acquisition
        # des concurrents : non traitée ». Prendre la ligne entière ramasse
        # la justification qui SUIT — « la donnée n'est pas publiée,
        # méthode d'estimation documentée » — et, quand plusieurs demandes
        # partagent une ligne, les mots des AUTRES demandes.
        #
        # Mesuré à la première exécution : la répétition à blanc a signalé
        # les quatre livrables sur « annexe, comparaison, complément,
        # couvre », mots venus d'une demande voisine et de la mécanique du
        # statut. Un contrôle qui lit trop large accuse à tort (règle 2).
        sujet = ligne[: trouve.start()]
        coupe = max(
            (sujet.rfind(frontiere) + len(frontiere)
             for frontiere in _FRONTIERES_DE_DEMANDE
             if frontiere in sujet),
            default=0,
        )
        sujet = sujet[coupe:]
        porteurs = {
            mot.casefold()
            for mot in _MOT_PORTEUR_RE.findall(sujet)
            if mot.casefold() not in _MOTS_TROP_COURANTS
        }
        # DISTINCTIF, et pas seulement present : un mot de liaison figure
        # dans tous les chapitres et ne designe aucun sujet.
        communs = sorted(
            mot for mot in porteurs
            if 0 < sum(1 for _, texte in autres if mot in texte) <= plafond
        )
        if len(communs) < _MOTS_COMMUNS_MIN:
            continue
        # VOISINS, et pas seulement presents. Un sujet est une LOCUTION :
        # « canaux d'acquisition » se retrouve ailleurs cote a cote. Des mots
        # epars qui se croisent aux quatre coins d'un chapitre ne prouvent
        # rien.
        #
        # Business plan 73dde3ab (17/08/2026) : le controle a conclu a une
        # contradiction au chapitre 20 sur « indique, initial, partiellement,
        # reprend ». Quatre mots assez longs, assez rares — et pourtant aucun
        # sujet : deux verbes, un adjectif, un adverbe, ramasses dans une
        # phrase de justification. La distinctivite seule ne les separait pas
        # d'un vrai sujet ; leur DISPERSION, si.
        if not any(
            _se_touchent(communs, texte) for _, texte in autres
        ):
            continue
        defauts.append(DemandeContredite(
            chapitre=numero,
            demande=ligne.strip()[:160],
            ailleurs=len(communs),
            detail=(
                f"Chapitre {numero} declare « non traite » un sujet que le "
                f"document traite ailleurs : {', '.join(communs[:4])}. "
                "Un point annonce puis declare non traite est pire qu'un "
                "point absent — il fait douter de tout le reste. Reprends "
                "le statut, ou nomme ce qui manque vraiment."
            ),
        ))
    return defauts

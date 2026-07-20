"""Deux controles ajoutes suite a la relecture d'Evangeline (juillet 2026).

Elle a relu la premiere generation « propre » du BP SYNAPSES et pointe quatre
defauts. Deux d'entre eux appellent chacun un controle nouveau, dedie, bloquant :

1. `_check_fourchettes` — Elle a martele en majuscules sur les fiches 1 et 2 :
   « PAS D'INVENTION OU D'EXTRAPOLATION DE MONTANT OU FOURCHETTE, ON S'APPUIE
   SUR DE VRAIES SOURCES FIABLES. SI ON EMET UNE HYPOTHESE C'EST TOUJOURS BASE
   SUR UN CHIFFRE DECIDE ET SOURCE ET NON DES FOURCHETTES ».
   Aujourd'hui rien ne detecte « entre 3 et 5 M€ » ou « 15 a 20 % ». On le fait
   ici, par regex sur les MOTIFS DE PLAGE (nombre, connecteur, nombre, unite
   monetaire ou pourcentage). Le filtre par unite ecarte les faux positifs
   naturels : « An 1 a An 5 », « chapitres 3 a 5 », plages de dates.

2. `_check_chiffre_contre_chiffre` — « Trésorerie de 3 328 458 € apparait a la
   place de 328 458 € », « fin d'annee 1 a la fois a 168 622 € et 163 672 € »,
   « seuil de rentabilite a 122 000, 180 000 a 280 000 et 205 000 ». Meme
   libelle, plusieurs valeurs. Le gate compare aujourd'hui le document au
   brief, pas le chapitre 15 au chapitre 8 du meme document. C'est ici qu'on
   ajoute la contre-verification interne.

Regle 5 du CLAUDE.md : les motifs de plage et la liste des libelles surveilles
sont ici et NULLE PART AILLEURS. Chaque module qui en aurait besoin importe.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from core.numbers import MONEY_CAPTURED, SPACE_CLASS, to_base_units

# ── 1. Fourchettes ───────────────────────────────────────────────────────────

# Un nombre francais « nu » : chiffres et espaces horizontales, decimale
# optionnelle. Simplifie pour ne pas capturer « An1 ».
_NOMBRE = rf"\d(?:\d|{SPACE_CLASS}|[.,]\d+)*"
_UNITE_MONETAIRE = r"Mds€|Md€|M€|k€|kEUR|€|euros?|EUR|FCFA|XOF|XAF|CFA|millions?|milliards?"
_POURCENTAGE = r"%"
# Connecteur simple entre deux nombres. « et » est traite par le prefixe
# optionnel « entre » qui suit, sinon « et » seul matcherait tout et n'importe
# quoi (« 3 emplois et 5 recrutements »).
_CONNECTEUR_NU = rf"{SPACE_CLASS}*(?:a(?:{SPACE_CLASS}+environ)?|-|—|–){SPACE_CLASS}*"
_CONNECTEUR_ENTRE = rf"{SPACE_CLASS}*et{SPACE_CLASS}*"

# Deux motifs : monetaire et pourcentage. Chacun accepte deux formes :
#   1. `NOMBRE connecteur NOMBRE UNITE`         (« 3 a 5 M€ », « 350-550 € »)
#   2. `entre NOMBRE et NOMBRE UNITE`           (« entre 3 et 5 M€ »)
# Le fait d'exiger une UNITE en fin de plage protege des faux positifs des
# numerotations (« annees 3 a 5 »), des dates (« 2020 a 2025 ») et des
# enumerations non chiffrees.
def _construire_motif(unite: str) -> re.Pattern[str]:
    return re.compile(
        rf"\b(?:entre{SPACE_CLASS}+({_NOMBRE}){_CONNECTEUR_ENTRE}({_NOMBRE})"
        rf"|({_NOMBRE}){_CONNECTEUR_NU}({_NOMBRE}))"
        rf"{SPACE_CLASS}*({unite})",
        re.IGNORECASE,
    )


_FOURCHETTE_MONETAIRE = _construire_motif(_UNITE_MONETAIRE)
_FOURCHETTE_POURCENTAGE = _construire_motif(_POURCENTAGE)


@dataclass(frozen=True)
class FourchetteTrouvee:
    """Une fourchette detectee dans un chapitre."""

    chapitre: int
    extrait: str
    borne_basse: str
    borne_haute: str
    unite: str


def detecter_fourchettes(chapitre_numero: int, texte: str) -> list[FourchetteTrouvee]:
    """Liste les fourchettes monetaires et de pourcentages du texte."""
    trouvees: list[FourchetteTrouvee] = []
    for motif in (_FOURCHETTE_MONETAIRE, _FOURCHETTE_POURCENTAGE):
        for match in motif.finditer(texte):
            # Le motif capture soit le premier couple de groupes (« entre X et
            # Y »), soit le second (« X a Y », « X-Y »). L'unite est toujours
            # le dernier groupe.
            borne_basse = match.group(1) or match.group(3)
            borne_haute = match.group(2) or match.group(4)
            trouvees.append(
                FourchetteTrouvee(
                    chapitre=chapitre_numero,
                    extrait=match.group(0),
                    borne_basse=borne_basse,
                    borne_haute=borne_haute,
                    unite=match.group(5),
                )
            )
    return trouvees


# ── 2. Chiffre contre chiffre ────────────────────────────────────────────────
#
# Un meme libelle chiffre ne peut pas rendre deux valeurs differentes dans le
# document livre. La liste des libelles surveilles est explicite : elle
# correspond aux chiffres qu'Evangeline a nomme comme intangibles (fiche 3 du
# document annote). Le contexte adjacent — « an 1 », « an 2 », « année N » —
# discrimine les valeurs annuelles legitimes des veritables incoherences.

# Libelles surveilles : chacun est un motif regex a l'interieur d'un groupe
# non capturant. Ordre = ordre d'affichage dans les motifs (le plus specifique
# d'abord evite qu'un libelle court avale un libelle long).
_S = SPACE_CLASS  # alias local pour tenir dans la largeur de ligne

_LIBELLES_SURVEILLES: dict[str, str] = {
    "tresorerie":           r"tr[ée]sorerie",
    "resultat_net":         rf"r[ée]sultat{_S}+net",
    "ebe":                  r"EBE|exc[ée]dent brut d'exploitation",
    "caf":                  rf"CAF|capacit[ée]{_S}+d['’]autofinancement",
    "bfr":                  rf"BFR|besoin{_S}+en{_S}+fonds{_S}+de{_S}+roulement",
    "seuil_rentabilite":    rf"seuil{_S}+de{_S}+rentabilit[ée]|point{_S}+mort",
    "investissement_total": rf"investissement{_S}+(?:total|initial|global)",
    "ca_previsionnel":      (
        rf"CA{_S}+pr[ée]visionnel"
        rf"|chiffre{_S}+d['’]affaires{_S}+pr[ée]visionnel"
    ),
    "apport":               rf"apport{_S}+(?:personnel|propre|initial)",
    "emprunt":              rf"emprunt{_S}+bancaire|pr[êe]t{_S}+bancaire",
    # Ajouts fiche 3 (juillet 2026, Evangeline) : « Verrouillage
    # trésorerie/CAF/BFR/dette résiduelle par année ». Chacun est ANNUEL —
    # une valeur legitime par exercice, une seule par exercice.
    "dette_residuelle":     rf"dette{_S}+r[ée]siduelle|capital{_S}+restant{_S}+d[ûu]",
    "marge_brute":          rf"marge{_S}+brute",
    "excedent_tresorerie":  rf"exc[ée]dent{_S}+de{_S}+tr[ée]sorerie",
}

# Libelles ANNUELS : la valeur legitime change d'une annee sur l'autre, donc
# on garde la discrimination par annee. Les autres sont GLOBAUX : une seule
# valeur autorisee dans tout le document, meme si le contexte cite « annee 2 »
# (« seuil de rentabilite atteint en annee 2 » reste le meme seuil).
#
# La distinction vient d'Evangeline : quand elle a signale « seuil de
# rentabilite : 122 000, 180 000 a 280 000, 205 000 », elle n'a jamais laisse
# entendre qu'il y avait plusieurs seuils par annee.
_LIBELLES_ANNUELS: frozenset[str] = frozenset({
    "tresorerie",
    "resultat_net",
    "ebe",
    "caf",
    "bfr",
    "ca_previsionnel",
    "dette_residuelle",
    "excedent_tresorerie",
})

# Annee discriminante : « an 1 », « annee 2 », « année N ». Sans annee, le
# libelle est repute global — donc une valeur unique attendue.
_ANNEE_RE = re.compile(
    rf"\ban{SPACE_CLASS}*n?[ée]?e?{SPACE_CLASS}*(\d{{1,2}})\b|\bAN{SPACE_CLASS}*(\d{{1,2}})\b",
    re.IGNORECASE,
)

_MONTANT_CAPTURE_RE = re.compile(MONEY_CAPTURED)

# Connecteurs SYNTAXIQUES entre un libelle et sa valeur : le montant doit
# etre attache au libelle par une preposition ou une ponctuation qui exprime
# une egalite, pas seulement etre a proximite. Sans ce garde-fou, une fenetre
# de 80 caracteres capturait des faux positifs (« CAF... annuite de 920 000 »
# devient « CAF de 920 000 »).
#
# Regle 4 du CLAUDE.md : viser la classe, pas l'exemple. Le pattern matching
# par PROXIMITE cree des faux positifs par construction. On exige une
# LIAISON, exprimee par un verbe de valeur ou une ponctuation d'egalite. Si
# la liaison n'est pas la, on manque plutot que de crier au loup.
# Fenetre entre le libelle et le montant. Assez large pour absorber les
# precisions temporelles (« fin annee 3 »), pas trop pour eviter la fuite
# vers un libelle voisin. Le vrai garde-fou n'est PAS la taille : c'est
# `_MOTS_DE_RUPTURE`, applique DANS la fenetre — si un mot de rupture
# apparait entre le libelle et le montant candidat, le montant designe autre
# chose, on refuse.
_FENETRE_APRES_LIBELLE = 100

# Connecteurs SYNTAXIQUES entre le libelle et sa valeur : la simple proximite
# ne suffit pas, il faut une preposition ou une ponctuation d'egalite quelque
# part entre le libelle et le montant. Sans ce garde-fou, deux phrases
# adjacentes qui n'ont rien a voir se retrouvaient liees.
_CONNECTEURS_VALEUR = re.compile(
    r"(?:"
    r"[:=]"                                            # « CAF : X »
    r"|\b(?:de|d['’]|a|est\s+de|s['’]\s*[eé]l[eè]ve|"
    r"atteint|repr[eé]sente|s['’]\s*[eé]tablit|"
    r"se\s+situe|se\s+trouve|vaut|projet[eé]e?|"
    r"estim[eé]e?|attendue?|cible[eé]e?|"
    r"de\s+l['’]ordre\s+de)\b"
    r")",
    re.IGNORECASE,
)

# Mots qui, glisses entre le libelle et le montant, coupent le lien
# semantique. Ils correspondent a d'AUTRES concepts financiers : si l'un
# apparait entre « CAF » et « 920 000 EUR », c'est que 920 000 designe cet
# autre concept (annuite, marge, salaire, prix...) et pas la CAF.
#
# NOTE IMPORTANTE : les libelles SURVEILLES (apport, emprunt, dette, CA,
# investissement) ne peuvent PAS etre des mots de rupture, sinon leurs
# propres qualificatifs (« apport personnel », « dette residuelle »)
# s'auto-bloquent. Les vrais dangers sont les concepts VOISINS non
# surveilles : annuite, marge, salaire, loyer, prix, cout.
_MOTS_DE_RUPTURE = re.compile(
    r"\b(?:mais|toutefois|cependant|contre|au\s+lieu\s+de|superieur\s+a|"
    r"inferieur\s+a|annuit[eé]|salaire|charges?|amortissement|"
    r"remboursement|loyer|prix|tarif|cout|budget|"
    r"subvention|remuneration)\b",
    re.IGNORECASE,
)

# Ecart relatif tolere entre deux mentions du meme libelle et de la meme annee.
# Zero est trop strict : 168 622 arrondi a 168 600 n'est pas une incoherence.
# On tolere 1 % — au dela, c'est deux valeurs distinctes.
_ECART_TOLERE = 0.01


@dataclass(frozen=True)
class Mention:
    """Une occurrence d'un libelle chiffre dans le document."""

    chapitre: int
    libelle: str  # cle canonique (« tresorerie », « seuil_rentabilite »...)
    annee: int | None
    montant_lu: str
    montant_base: float  # normalise en unite de base (euros, pas M€)


@dataclass(frozen=True)
class DivergenceChiffree:
    """Deux valeurs distinctes pour le meme (libelle, annee)."""

    libelle: str
    annee: int | None
    mentions: tuple[Mention, ...]

    @property
    def resume(self) -> str:
        parties = [f"{m.montant_lu} au ch. {m.chapitre}" for m in self.mentions]
        suffixe = f" (annee {self.annee})" if self.annee is not None else ""
        return f"{self.libelle}{suffixe} : {' ; '.join(parties)}"


def _annee_proche(texte: str) -> int | None:
    """Extrait l'annee mentionnee dans la fenetre de contexte, si presente."""
    match = _ANNEE_RE.search(texte)
    if not match:
        return None
    valeur = match.group(1) or match.group(2)
    return int(valeur)


_MONTANT_CAPTURE_COMPILE = re.compile(MONEY_CAPTURED, re.IGNORECASE)


def collecter_mentions(chapitre_numero: int, texte: str) -> list[Mention]:
    """Collecte les mentions ou le libelle est LIE au montant.

    Regles de capture, dans l'ordre :

    1. Le libelle est mentionne.
    2. Un montant existe dans les 100 caracteres qui suivent.
    3. Entre le libelle et ce montant, un CONNECTEUR de valeur (verbe ou
       ponctuation d'egalite) est present. Sans lui, deux phrases
       adjacentes non liees se retrouveraient artificiellement associees.
    4. Entre le libelle et ce montant, aucun MOT DE RUPTURE non plus
       (annuite, marge, salaire, loyer, prix, cout, budget, subvention).
       Un mot de rupture signale que le montant designe un autre concept
       voisin, pas le libelle.
    5. Pour un libelle annuel (tresorerie, EBE, CAF...), l'annee doit etre
       explicitement citee dans le contexte proche. Sinon, la mention est
       ambigue et on refuse.

    A chaque etape, on prefere manquer un vrai defaut plutot que produire
    un faux positif. Mesure prise apres SYNAPSES v2 (juillet 2026) : 5
    faux positifs sur 10 divergences reportees, dont chacun faisait perdre
    confiance dans les 5 autres, pourtant vraies.
    """
    mentions: list[Mention] = []
    for cle, motif_libelle in _LIBELLES_SURVEILLES.items():
        for occurrence in re.finditer(motif_libelle, texte, re.IGNORECASE):
            fin_libelle = occurrence.end()
            fin_fenetre = min(len(texte), fin_libelle + _FENETRE_APRES_LIBELLE)
            fenetre = texte[fin_libelle:fin_fenetre]

            montant = _MONTANT_CAPTURE_COMPILE.search(fenetre)
            if not montant:
                continue
            entre = fenetre[: montant.start()]
            if not _CONNECTEURS_VALEUR.search(entre):
                continue
            if _MOTS_DE_RUPTURE.search(entre):
                continue

            base = to_base_units(
                _lire_nombre(montant.group(1)), montant.group(2)
            )
            if base <= 0:
                continue

            # Annee : uniquement pertinent pour les libelles ANNUELS. Un
            # seuil de rentabilite « atteint en annee 2 » reste global —
            # sinon deux mentions du meme seuil global (l'une nue, l'autre
            # « en annee 2 ») seraient rangees dans des groupes distincts
            # et la divergence entre elles passerait inapercue.
            if cle in _LIBELLES_ANNUELS:
                debut_ctx = max(0, occurrence.start() - 40)
                fin_ctx = min(len(texte), fin_libelle + montant.end() + 40)
                annee = _annee_proche(texte[debut_ctx:fin_ctx])
                if annee is None:
                    continue
            else:
                annee = None

            mentions.append(
                Mention(
                    chapitre=chapitre_numero,
                    libelle=cle,
                    annee=annee,
                    montant_lu=montant.group(0).strip(),
                    montant_base=base,
                )
            )
    return mentions


def _lire_nombre(raw: str) -> float:
    """Convertit `1 250 000,50` en float. Utilise `core.numbers` pour la classe
    d'espaces (toute espace horizontale Unicode)."""
    nettoye = re.sub(SPACE_CLASS, "", raw).replace(",", ".")
    try:
        return float(nettoye)
    except ValueError:
        return 0.0


def _valeurs_distinctes(mentions: tuple[Mention, ...]) -> bool:
    """Vrai si les mentions portent des montants ecartes de plus de 1 %."""
    valeurs = sorted({m.montant_base for m in mentions if m.montant_base})
    if len(valeurs) < 2:
        return False
    reference = valeurs[0] or 1.0
    return any(abs(v - reference) / abs(reference) > _ECART_TOLERE for v in valeurs)


# ── 3. Chapitre avorte (« Ralph Wiggum loop ») ──────────────────────────────
#
# L'agent declare un chapitre fini sur un contenu manifestement trop court, le
# gate le laisse passer parce qu'il n'est pas VIDE. Constat : le runner accepte
# `ChapterStatus.DONE` sans regarder la longueur, et le gate a un check
# `_check_truncation` qui vise la coupure a mi-phrase mais pas le contenu
# indigent.
#
# On plancher a 30 % du `max_words` prevu par le blueprint : un chapitre de
# 900 mots qui en rend 250 est objectivement avorte, quelle qu'en soit la
# cause (context length, refus du modele, exception silencieuse). Sans
# `max_words` (Annexes, Fiche projet, Sources), on ne peut pas juger — on
# laisse passer plutot que d'inventer une regle.
_PLANCHER_RATIO = 0.30


@dataclass(frozen=True)
class ChapitreAvorte:
    """Un chapitre rend un contenu manifestement trop court."""

    chapitre: int
    titre: str
    mots_rendus: int
    mots_attendus: int
    ratio: float


def _compter_mots(texte: str) -> int:
    """Compte les mots d'un texte, balisage markdown exclu."""
    nu = re.sub(r"[#*_`>|\-]+", " ", texte)
    return len(re.findall(r"[^\W\d_]{2,}", nu))


# ── 4. Concurrents : 8 directs et 3 indirects, exactement ───────────────────
#
# Consigne d'Evangeline (fiche 2, question 4) : « il en faut 8 et on les garde
# tout le long », « il en faut 3 et on les garde tout le long ». Ni plus, ni
# moins. Si le systeme en trouve moins, il complete avec des voisins. S'il en
# trouve plus, il selectionne les plus pertinents. Le gate refuse toute autre
# quantite pour une etude de concurrence.
#
# La detection s'appuie sur la sous-section standard des blueprints EC :
# « Concurrents directs » et « Concurrents indirects ». On compte les entrees
# de liste (`- Nom`, `1. Nom`, `**Nom**`) sous chacune de ces sous-sections.

ATTENDUS_CONCURRENTS: dict[str, int] = {
    "directs":   8,
    "indirects": 3,
}

# Ordre exact donne par Evangeline (Q3 du 17/07/2026) pour arbitrer quand il y a
# plus de concurrents pertinents que la place disponible. Le premier critere
# prime toujours ; on descend au critere suivant si egalite. La CONSTANTE est
# la source unique injectee dans le prompt EC (regle 5 du CLAUDE.md).
CRITERES_TRI_CONCURRENTS: tuple[str, ...] = (
    "Similarite de l'offre (memes produits, memes services)",
    "Cible client comparable",
    "Taille (chiffre d'affaires, notoriete)",
    "Proximite geographique avec le client",
    "Anciennete sur le marche",
)

_SOUS_SECTIONS_CONCURRENTS: dict[str, re.Pattern[str]] = {
    "directs":   re.compile(r"concurrent[s]?\s+direct[s]?", re.IGNORECASE),
    "indirects": re.compile(r"concurrent[s]?\s+indirect[s]?", re.IGNORECASE),
}
_LIGNE_LISTE = re.compile(r"^\s*(?:[-•*]|\d+\.)\s+\S", re.MULTILINE)


@dataclass(frozen=True)
class CompteConcurrents:
    """Nombre trouve vs attendu pour un type de concurrents."""

    type_: str  # « directs » ou « indirects »
    trouves: int
    attendus: int
    chapitre: int


def compter_concurrents(
    chapitre_numero: int, corps: str
) -> list[CompteConcurrents]:
    """Compte les entrees de liste sous les sous-sections concurrents.

    Une section « Concurrents directs » suivie de 6 puces = 6 concurrents.
    On coupe au titre suivant (autre `##`, ou une des sous-sections concurrents
    voisines) pour ne pas melanger les listes.
    """
    resultats: list[CompteConcurrents] = []
    positions: list[tuple[str, int, int]] = []
    for type_, motif in _SOUS_SECTIONS_CONCURRENTS.items():
        for m in motif.finditer(corps):
            positions.append((type_, m.start(), m.end()))
    positions.sort(key=lambda p: p[1])
    for i, (type_, _debut, fin_titre) in enumerate(positions):
        fin_bloc = positions[i + 1][1] if i + 1 < len(positions) else len(corps)
        # Coupure prudente au titre `##` suivant s'il en existe un plus proche.
        for titre in re.finditer(r"^#{2,4}\s", corps[fin_titre:fin_bloc], re.MULTILINE):
            fin_bloc = fin_titre + titre.start()
            break
        bloc = corps[fin_titre:fin_bloc]
        trouves = len(_LIGNE_LISTE.findall(bloc))
        resultats.append(CompteConcurrents(
            type_=type_,
            trouves=trouves,
            attendus=ATTENDUS_CONCURRENTS[type_],
            chapitre=chapitre_numero,
        ))
    return resultats


def verifier_concurrents_dans_ec(
    sections: list[tuple[int, str]],
) -> list[CompteConcurrents]:
    """Compte les concurrents sur l'ensemble des chapitres d'une EC.

    Retourne UNIQUEMENT les comptes qui divergent des attendus. Aucun compte
    trouve = aucune sous-section detectee : on ne signale rien plutot que
    d'inventer un defaut sur un chapitre qui n'a jamais eu vocation a les
    lister (structure du blueprint qui aurait change).
    """
    par_type: dict[str, int] = {"directs": 0, "indirects": 0}
    dernier_chapitre: dict[str, int] = {}
    for numero, corps in sections:
        for c in compter_concurrents(numero, corps):
            par_type[c.type_] += c.trouves
            dernier_chapitre[c.type_] = numero
    divergents: list[CompteConcurrents] = []
    for type_, attendus in ATTENDUS_CONCURRENTS.items():
        trouves = par_type[type_]
        if type_ not in dernier_chapitre or trouves == attendus:
            continue
        divergents.append(CompteConcurrents(
            type_=type_,
            trouves=trouves,
            attendus=attendus,
            chapitre=dernier_chapitre[type_],
        ))
    return divergents


# ── Piliers de la strategie business : les 4 sont toujours poses ────────────
#
# Consigne d'Evangeline (fiche 4, question 1) : pour une strategie business,
# les 4 piliers sont TOUJOURS traites, dans le meme ordre, avec leur objectif
# verbatim. On les verifie present dans le document livre.

PILIERS_STRATEGIE: dict[str, tuple[str, str]] = {
    "positionnement": (
        "PILIER 1",
        rf"positionnement(?:{_S}+&{_S}+|{_S}+et{_S}+)sp[ée]cialisation",
    ),
    "offre":       ("PILIER 2", rf"structuration{_S}+de{_S}+l['’]offre"),
    "editorial":   ("PILIER 3", rf"planning{_S}+[ée]ditorial"),
    "tarification":("PILIER 4", rf"analyse{_S}+de{_S}+la{_S}+tarification"),
}


@dataclass(frozen=True)
class PilierManquant:
    """Un pilier structurant de la strategie est absent du document."""

    cle: str
    intitule: str
    motif: str


def verifier_piliers_strategie(corpus: str) -> list[PilierManquant]:
    """Chaque pilier doit apparaitre au moins une fois dans le document."""
    manquants: list[PilierManquant] = []
    for cle, (intitule, motif) in PILIERS_STRATEGIE.items():
        if not re.search(motif, corpus, re.IGNORECASE):
            manquants.append(PilierManquant(
                cle=cle,
                intitule=intitule,
                motif=motif,
            ))
    return manquants


def detecter_chapitres_avortes(
    sections_avec_plafond: list[tuple[int, str, str, int]],
) -> list[ChapitreAvorte]:
    """Signale les chapitres qui rendent moins de 30 % de leur plafond.

    `sections_avec_plafond` = liste de (numero, titre, corps, max_words). Un
    `max_words == 0` (Annexes, Sources, Fiche projet) desactive le check :
    ces chapitres n'ont pas de cible et rester silencieux est preferable a
    inventer une regle.
    """
    avortes: list[ChapitreAvorte] = []
    for numero, titre, corps, max_words in sections_avec_plafond:
        if max_words <= 0:
            continue
        mots = _compter_mots(corps)
        seuil = int(max_words * _PLANCHER_RATIO)
        if mots < seuil:
            avortes.append(ChapitreAvorte(
                chapitre=numero,
                titre=titre,
                mots_rendus=mots,
                mots_attendus=max_words,
                ratio=mots / max_words if max_words else 0.0,
            ))
    return avortes


def detecter_divergences(mentions: list[Mention]) -> list[DivergenceChiffree]:
    """Regroupe par (libelle, annee) et signale les valeurs distinctes."""
    par_cle: dict[tuple[str, int | None], list[Mention]] = defaultdict(list)
    for m in mentions:
        par_cle[(m.libelle, m.annee)].append(m)

    divergences: list[DivergenceChiffree] = []
    # `sorted` compare les cles element par element. `annee` peut valoir None
    # (libelle global) ou un int (libelle annualise) ; il faut une clef de tri
    # unique — d'ou -1 pour l'absence d'annee, place en tete.
    for (libelle, annee), items in sorted(
        par_cle.items(), key=lambda kv: (kv[0][0], -1 if kv[0][1] is None else kv[0][1])
    ):
        tuple_mentions = tuple(items)
        if _valeurs_distinctes(tuple_mentions):
            divergences.append(
                DivergenceChiffree(libelle=libelle, annee=annee, mentions=tuple_mentions)
            )
    return divergences

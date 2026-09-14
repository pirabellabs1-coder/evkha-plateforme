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
import unicodedata
from collections import defaultdict
from dataclasses import dataclass

from core.numbers import MONEY, MONEY_CAPTURED, SPACE_CLASS, parse_number, to_base_units

# ── 1. Fourchettes ───────────────────────────────────────────────────────────

# Un nombre francais « nu » : chiffres et espaces horizontales, decimale
# optionnelle. Simplifie pour ne pas capturer « An1 ».
_NOMBRE = rf"\d(?:\d|{SPACE_CLASS}|[.,]\d+)*"
_UNITE_MONETAIRE = r"Mds€|Md€|M€|k€|kEUR|€|euros?|EUR|FCFA|XOF|XAF|CFA|millions?|milliards?"
_POURCENTAGE = r"%"
# Connecteur simple entre deux nombres. « et » est traite par le prefixe
# optionnel « entre » qui suit, sinon « et » seul matcherait tout et n'importe
# quoi (« 3 emplois et 5 recrutements »).
# « à » ACCENTUÉ compris : « de 60 à 65 € » passait inaperçu, seul « 60 a 65 € »
# était vu (audit du 14/09/2026, A3).
_CONNECTEUR_NU = rf"{SPACE_CLASS}*(?:[aà](?:{SPACE_CLASS}+environ)?|-|—|–){SPACE_CLASS}*"
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


# Un ÉTIQUETTE devant la « borne basse » : « An 1 — 120 000 € », « Scénario 2 -
# 40 % », « N+1 - 250 000 € ». Le 1, le 2 ne sont pas des bornes, ce sont des
# numéros : le motif les prenait pour une plage de 1 à 120 000, et le motif
# rendu au client était faux (audit du 14/09/2026, A3 ; règle 2).
# ── Ce qui ressemble à une plage et n'en est pas une ─────────────────────────
#
# Relecture du 14/09/2026. Trois formes, chacune mesurée, et une borne à chaque
# garde — la première version écartait aussi de VRAIES plages de prix :
#
# 1. Une TRAJECTOIRE datée : « le CA passe de 120 000 € en 2026 à 180 000 € en
#    2027 ». Avec « à » accentué, « 2026 à 180 000 € » devenait une fourchette,
#    motif faux sur la forme même d'un prévisionnel — et réécrit, donc payé.
#    Une borne basse qui est une ANNÉE écrite en clair, ou qu'un repère de
#    période précède (« au mois 18 à 42 000 € »), n'est pas une borne.
# 2. Une ÉTIQUETTE suivie d'un montant, au TIRET ESPACÉ seulement : « An 1 —
#    120 000 € », « Scénario 2 - 40 % ». Un trait d'union collé entre deux
#    nombres (« 49-59 € ») est une plage en typographie française, et « entre
#    X et Y » / « de X à Y » le disent en toutes lettres.
# 3. Un NUMÉRO suivi d'un montant, au tiret : borne basse entière ≤ 12 et borne
#    haute ≥ 1 000 (« Mois 1 - 1 500 € »). La première version écartait tout
#    rapport supérieur à 20, donc « 5-150 € » et « 1,5-40 M€ » — les plages
#    les plus larges, c'est-à-dire les pires.

_ANNEE = re.compile(r"^(?:19|20)\d{2}$")

_REPERE_DE_PERIODE_AVANT = re.compile(
    r"\b(?:mois|semaine|trimestre|ann[ée]e|an|en|fin|d[ée]but|au|du)\s*$",
    re.IGNORECASE,
)

_ETIQUETTE_AVANT = re.compile(
    r"\b(?:an|ann[ée]e|sc[ée]nario|palier|phase|[ée]tape|horizon|axe|pilier|"
    r"tableau|figure|chapitre|version|lot|top|n\s*\+|t|q)\s*$",
    re.IGNORECASE,
)

#: 4. Un MOUVEMENT entre deux valeurs, ou l'ÉCART entre elles — deux valeurs
#:    décidées, pas une valeur hésitante. Corpus re-mesuré le 14/09/2026 après
#:    déploiement : « le saut de 19 € à 29 € », « basculé de 19 € à 29 € »,
#:    « passer de 120 000 € à 157 500 € », « la confusion entre 19 et 29
#:    euros » étaient comptés comme fourchettes. « Interventions de 60 à 75 €
#:    de l'heure » reste une plage : le brief donnait trois prix distincts, et
#:    la plage les efface.
_MOUVEMENT_AVANT = re.compile(
    # Seuls les mots qui relient DEUX ÉTATS. « Une hausse de 3 à 5 % » dit une
    # hausse comprise entre 3 et 5 % : c'est une plage, et elle reste vue.
    r"\b(?:saut|passage|pass(?:e|er|ent|ant|é|ée|és)|bascul\w*|migr\w*"
    r"|port(?:e|er|ant|é)|glissement|transition|rel[èe]vement|revaloris\w*)\b"
    r"[^.;:\d]{0,30}?\b(?:de|d['’])\s*[+]?\s*$",
    re.IGNORECASE,
)
_ECART_AVANT = re.compile(
    r"\b(?:[ée]cart|diff[ée]rence|confusion|saut|choix|arbitrage|comparaison"
    r"|h[ée]sitation)\b[^.;:\d]{0,25}?\bentre\s*$",
    re.IGNORECASE,
)

_NUMERO_MAX = 12
_MONTANT_MIN_APRES_UN_NUMERO = 1000


def _n_est_pas_une_plage(texte: str, match: re.Match[str]) -> bool:
    """Trajectoire datée, étiquette ou numéro — pas une fourchette."""
    brute_basse = (match.group(1) or match.group(3) or "").strip()
    avant = texte[max(0, match.start() - 20) : match.start()]

    # 4. Mouvement ou écart : deux valeurs, pas une hésitation.
    debut_basse = match.start(1) if match.group(1) is not None else match.start(3)
    avant_long = texte[max(0, debut_basse - 60) : debut_basse]
    if match.group(1) is not None and _ECART_AVANT.search(avant_long):
        return True
    if match.group(3) is not None and _MOUVEMENT_AVANT.search(avant_long):
        connecteur = texte[match.end(3) : match.start(4)].strip()
        if connecteur in ("à", "a"):
            return True

    # 1. Trajectoire : la « borne basse » est une année, ou suit un repère.
    if _ANNEE.match(brute_basse):
        return True
    if match.group(3) is not None and _REPERE_DE_PERIODE_AVANT.search(avant):
        connecteur = texte[match.end(3) : match.start(4)].strip()
        if connecteur in ("à", "a"):
            return True

    if match.group(3) is None:  # « entre X et Y » : c'est une plage, dite
        return False
    connecteur_brut = texte[match.end(3) : match.start(4)]
    connecteur = connecteur_brut.strip()
    if connecteur not in ("-", "—", "–"):
        return False
    tiret_espace = connecteur_brut != connecteur

    # 2. Étiquette, au tiret espacé seulement.
    if tiret_espace and _ETIQUETTE_AVANT.search(avant):
        return True

    # 3. Numéro suivi d'un montant.
    basse, haute = parse_number(match.group(3)), parse_number(match.group(4))
    if basse is None or haute is None:
        return False
    return (
        float(basse).is_integer()
        and "," not in match.group(3) and "." not in match.group(3)
        and 0 < basse <= _NUMERO_MAX
        and haute >= _MONTANT_MIN_APRES_UN_NUMERO
    )


@dataclass(frozen=True)
class FourchetteTrouvee:
    """Une fourchette detectee dans un chapitre."""

    chapitre: int
    extrait: str
    borne_basse: str
    borne_haute: str
    unite: str


# Marqueur d'une mediane annoncee IMMEDIATEMENT apres une fourchette.
# Format WAOME (juillet 2026) : « ..., mediane retenue 40 milliards ». Ce
# motif est la seule chose qui rend une fourchette LEGITIME dans une EM.
# Il doit apparaitre dans les 120 caracteres qui suivent la fourchette,
# sans autre fourchette ni saut de paragraphe intercale — sinon la mediane
# concerne autre chose.
_MEDIANE_ANNONCEE_RE = re.compile(
    r"m[eé]diane(?:\s+retenue)?"
    r"|valeur\s+retenue"
    r"|retenu[e]?\s*(?:[aà]|:)"
    r"|(?:on|nous)\s+retien(?:t|dr)",
    re.IGNORECASE,
)

# La fenêtre s'arrête à la fin de la phrase, de la cellule ou de la ligne : sans
# cette borne, « Dupont : CA entre 600 000 et 800 000 €. Martin : …, valeur
# retenue 1,35 M€ » admettait la plage de Dupont avec la valeur de Martin
# (relecture du 14/09/2026).
_FIN_DE_LA_PLAGE = re.compile(r"[.;\n|]")

# En EC, l'admission vaut pour un CA ou une part ESTIMÉS — jamais pour une
# croissance : la consigne dit « taux de croissance et TCAC restent des valeurs
# uniques », le contrôle doit dire la même chose (règle 5).
_CROISSANCE = re.compile(r"croissance|TCAC|CAGR|[ée]volution\s+annuelle", re.IGNORECASE)
_MEDIANE_FENETRE = 120

# Types de livrable ou la fourchette sourcee avec mediane annoncee est LEGITIME
# (registre « estimations sectorielles » d'Evangeline). Les autres restent
# strictement interdits : chaque valeur unique.
_LIVRABLES_FOURCHETTE_SOURCEE_OK: frozenset[str] = frozenset({
    "market_study",  # DeliverableType.MARKET_STUDY.value
    # Le cahier des charges EC exige une borne basse et une borne haute pour
    # le CA ESTIMÉ d'un concurrent (étape 6.2) ; la cliente exige un chiffre
    # décidé. Une plage IMMÉDIATEMENT suivie de sa valeur retenue satisfait
    # les deux. Sans cette admission, le prompt imposait ce que le gate
    # refusait, et chaque chapitre 6 était repayé (audit du 14/09/2026, A1).
    "competitor_study",  # DeliverableType.COMPETITOR_STUDY.value
})


def detecter_fourchettes(
    chapitre_numero: int,
    texte: str,
    deliverable_type: str | None = None,
) -> list[FourchetteTrouvee]:
    """Liste les fourchettes monetaires et de pourcentages du texte.

    Regle EM (WAOME) : une fourchette suivie dans les 120 caracteres d'une
    mention « mediane retenue X » ou equivalent est un registre
    « estimations sectorielles » legitime, elle N'EST PAS retenue comme
    defaut. L'etude concurrentielle suit la meme forme pour un CA ou une part
    ESTIMES — jamais pour une croissance (14/09/2026, audit A1). BP et STR
    gardent la regle stricte : aucune fourchette, meme suivie d'une valeur.

    Par defaut (sans deliverable_type), le comportement est strict — c'est
    la retro-compatibilite avec les appels existants qui ne passaient pas
    ce parametre.
    """
    fourchette_sourcee_ok = (
        deliverable_type is not None
        and deliverable_type in _LIVRABLES_FOURCHETTE_SOURCEE_OK
    )
    trouvees: list[FourchetteTrouvee] = []
    for motif in (_FOURCHETTE_MONETAIRE, _FOURCHETTE_POURCENTAGE):
        for match in motif.finditer(texte):
            # Le motif capture soit le premier couple de groupes (« entre X et
            # Y »), soit le second (« X a Y », « X-Y »). L'unite est toujours
            # le dernier groupe.
            borne_basse = match.group(1) or match.group(3)
            borne_haute = match.group(2) or match.group(4)
            if _n_est_pas_une_plage(texte, match):
                continue
            if fourchette_sourcee_ok:
                fenetre = texte[match.end() : match.end() + _MEDIANE_FENETRE]
                coupure = _FIN_DE_LA_PLAGE.search(fenetre)
                if coupure:
                    fenetre = fenetre[: coupure.start()]
                debut_phrase = max(
                    texte.rfind(".", 0, match.start()),
                    texte.rfind("\n", 0, match.start()),
                )
                phrase = texte[debut_phrase + 1 : match.end() + len(fenetre)]
                croissance = (
                    deliverable_type == "competitor_study"
                    and bool(_CROISSANCE.search(phrase))
                )
                if _MEDIANE_ANNONCEE_RE.search(fenetre) and not croissance:
                    # La mediane est annoncee IMMEDIATEMENT apres : registre
                    # « estimations sectorielles » d'Evangeline, on laisse.
                    continue
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
    # La marge brute change d'un exercice à l'autre, comme l'EBE. Rangée parmi
    # les libellés GLOBAUX, elle opposait « 227 200 € » (exercice 1) à
    # « 265 000 € » (exercice 3) : 6 business plans du corpus accusés de
    # « valeurs divergentes » sur leur propre prévisionnel (14/09/2026).
    "marge_brute",
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
    rf"\ban{SPACE_CLASS}*n?[ée]?e?{SPACE_CLASS}*(\d{{1,2}})\b|\bAN{SPACE_CLASS}*(\d{{1,2}})\b"
    # « l'exercice 1 » : le prévisionnel parle en EXERCICES autant qu'en années.
    rf"|\bexercice{SPACE_CLASS}*(\d{{1,2}})\b"
    # « la première année », « le troisième exercice » : sans eux, « le résultat
    # net de la première année, 9 000 euros » prenait l'année d'une phrase
    # voisine (business plan `73dde3ab`, corpus du 14/09/2026).
    r"|\b(premi[èe]re?|deuxi[èe]me|seconde?|troisi[èe]me|quatri[èe]me|cinqui[èe]me)"
    rf"{SPACE_CLASS}+(?:ann[ée]e|exercice)\b",
    re.IGNORECASE,
)

_RANG_ORDINAL = {
    "premier": 1, "premiere": 1, "première": 1, "deuxieme": 2, "deuxième": 2,
    "second": 2, "seconde": 2, "troisieme": 3, "troisième": 3,
    "quatrieme": 4, "quatrième": 4, "cinquieme": 5, "cinquième": 5,
}

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
    r"\b(?:mais|toutefois|cependant|contre|au\s+lieu\s+de|sup[ée]rieur\w*\s+[àa]|"
    r"inf[ée]rieur\w*\s+[àa]|annuit[eé]|salaire|charges?|amortissement|"
    # Accents : le texte n'est pas désaccentué avant cette recherche, et
    # « coût », « rémunération », « supérieur à » n'étaient jamais reconnus.
    r"remboursement|loyer|prix|tarif|co[uû]ts?|budget|"
    r"subvention|r[ée]mun[ée]ration"
    # Une comparaison ou une DÉCOMPOSITION après le libellé : « dont le chiffre
    # d'affaires ne dépasse pas 10 millions… », « le chiffre d'affaires se
    # décompose en 40 716 € issus des abonnements » — le montant est un seuil
    # légal ou une composante (corpus du 14/09/2026).
    r"|d[ée]pass\w*|exc[èe]d\w*|se\s+d[ée]compos\w*|dont|r[ée]parti\w*|ventil\w*"
    # Mesures du business plan 73dde3ab, 17/08/2026. « Part de l'apport dans
    # le besoin total de 195 000 EUR » liait 195 000 a l'apport : le montant
    # appartient a l'agregat que la preposition vient de nommer.
    r"|besoin\s+total|besoin\s+de\s+financement|financement\s+global"
    r"|masse\s+salariale|chiffre\s+d['’]affaires"
    # « marge brute unitaire de 4,68 EUR » face a « la marge brute de
    # l'exercice 1 s'eleve a 230 400 EUR » : ce n'est pas la meme grandeur,
    # et les opposer produisait une divergence sur un document juste.
    r"|unitaire|par\s+unit[eé]|par\s+ticket|par\s+client)\b",
    re.IGNORECASE,
)

#: Une phrase qui présente une variante, pas la valeur retenue : condition,
#: scénario nommé, sensibilité, ou verbe au conditionnel.
_PHRASE_DE_SCENARIO = re.compile(
    # « Scénario » SEUL n'en fait pas partie : « le seuil de rentabilité pour ce
    # scénario est de 180 000 € » était l'une des trois valeurs concurrentes
    # que la cliente a signalées (SYNAPSES). Il faut une variante NOMMÉE.
    r"\b(?:si|pessimiste|optimiste|d[ée]grad[ée]e?|sensibilit[ée]|"
    r"stress|variante|en\s+cas\s+d|hypoth[èe]se\s+(?:basse|haute))\b"
    r"|\b\w{3,}(?:rait|raient)\b",
    re.IGNORECASE,
)

#: Ce qui, juste après un montant, en fait une grandeur PAR unité ou par période.
_PAR_UNITE_APRES = re.compile(
    r"\s*(?:HT|TTC)?\s*(?:par|/)\s*(?:mois|an|ann[ée]e|semaine|jour|trimestre|abonn[ée]s?|"
    r"clients?|unit[ée]s?|couverts?|tickets?|commandes?|heures?|personnes?|habitants?|"
    r"utilisateurs?|licences?|adh[ée]rents?|m[²2]|mètres?)\b"
    r"|\s*(?:mensuel(?:le)?s?|hebdomadaires?|unitaires?)\b",
    re.IGNORECASE,
)

#: Une phrase qui se termine emporte son sujet avec elle.
#:
#: « ...et du taux de marge brute. La masse salariale prevsionnelle represente
#: a elle seule 70 000 euros » : 70 000 ne dit rien de la marge brute, il
#: appartient a la phrase suivante. La fenetre de 100 caracteres traversait
#: les points sans les voir.
#: Un saut de ligne coupe aussi : une grille « **27 600 €** — Investissement
#: total » écrit la valeur AVANT son libellé, et le libellé allait prendre la
#: valeur de la ligne suivante (« **1 600 €** — Apport personnel »). Un titre
#: sans point faisait de même avec le paragraphe qu'il annonce (corpus du
#: 14/09/2026, six motifs).
_FIN_DE_PHRASE = re.compile(r"[.!?]\s|\n")

#: Juste AVANT le libellé, une comparaison : le montant qui suit est un ÉCART,
#: pas la grandeur. « dépasse le seuil de rentabilité de 35 609 € », « ne
#: dépasse le seuil de rentabilité que de 4 000 € ».
_COMPARAISON_AVANT = re.compile(
    r"(?:d[ée]pass\w*|exc[èe]d\w*|sup[ée]rieure?s?\s+[àa]u?|inf[ée]rieure?s?\s+[àa]u?|"
    r"au-dessus\s+d[ue]?|en\s+dessous\s+d[ue]?)"
    r"(?:\s+(?:le|la|les|l['’]|du|des|de\s+la|son|sa|ses|leur|leurs))?\s*$",
    re.IGNORECASE,
)

#: « 54 276 euros DE chiffre d'affaires » : ce qui introduit, après un montant,
#: la grandeur qu'il mesure.
_COMPLEMENT_DE_GRANDEUR = re.compile(
    r"\s*(?:HT|TTC)?\s*(?:de|d['’])\s*(?:l['’]\s*|la\s+|le\s+|les\s+)?", re.IGNORECASE,
)

#: Un montant puis « de » juste avant le libellé : la valeur précède son libellé.
_VALEUR_AVANT_LIBELLE = re.compile(
    rf"{MONEY}{SPACE_CLASS}*(?:HT|TTC)?{SPACE_CLASS}*(?:de|d['’])"
    rf"{SPACE_CLASS}*(?:l['’]{SPACE_CLASS}*|la{SPACE_CLASS}+|le{SPACE_CLASS}+|les{SPACE_CLASS}+)?$",
    re.IGNORECASE,
)

#: Une COORDINATION entre le libellé et le montant : « intégrée au calcul du
#: seuil de rentabilité et au compte de résultat du chapitre 16 : 12 000 euros ».
#: Le montant appartient au dernier terme coordonné.
_COORDINATION = re.compile(
    r"\bet\s+(?:au|aux|à\s+la|à\s+l['’]|du|de\s+la|des|le|la|les|l['’])\b", re.IGNORECASE,
)

#: Un opérateur dans une parenthèse : « (18 667 €/54 276 €) », « (54 276 €
#: moins 18 667 €) ». Le montant qu'elle contient est un OPÉRANDE.
_OPERATEUR = re.compile(r"/|÷|\bmoins\b|\bplus\b|\s[-−×x*+]\s", re.IGNORECASE)

#: Un nombre puis « à » juste avant le montant : « de 9 000 à 45 000 euros
#: entre l'année 1 et l'année 3 ». Le montant est la FIN d'une trajectoire,
#: et l'année la plus proche n'est pas forcément la sienne.
_DEBUT_DE_TRAJECTOIRE = re.compile(r"\s*(?:HT|TTC)?\s*[àa]\s+\d")
_FIN_DE_TRAJECTOIRE = re.compile(r"\d[\d\s\u00a0\u202f,.]*\s*(?:€|euros?)?\s+[àa]\s*$")

#: Au-dela d'une cellule franchie, le montant est ailleurs dans le tableau.
#:
#: « Seuil de rentabilite annuel | donnees du projet | 195 000 EUR » : une
#: barre separe un libelle de SA valeur, deux barres separent deux lignes.
_CELLULES_MAX_FRANCHIES = 1

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
    #: La phrase qui porte la valeur, telle que le lecteur la trouvera.
    extrait: str = ""


@dataclass(frozen=True)
class DivergenceChiffree:
    """Deux valeurs distinctes pour le meme (libelle, annee)."""

    libelle: str
    annee: int | None
    mentions: tuple[Mention, ...]

    @property
    def resume(self) -> str:
        """Chaque valeur UNE fois, avec ses chapitres ; la phrase des minoritaires.

        Le motif énumérait chaque mention : « 27 600 € au ch. 0 ; 27 600 € au
        ch. 13 ; … (huit fois) … ; 1 600 € au ch. 20 ». La valeur qui diverge
        était la dernière d'une liste tronquée à la lecture, sans la phrase qui
        la porte — introuvable par le lecteur comme par la correction (règle 2,
        corpus du 14/09/2026 : seize motifs de ce type).
        """
        par_valeur: dict[float, list[Mention]] = {}
        for mention in self.mentions:
            par_valeur.setdefault(mention.montant_base, []).append(mention)
        groupes = sorted(par_valeur.values(), key=len, reverse=True)
        # La valeur la plus fréquente, si elle l'est strictement, se passe de
        # phrase : c'est la divergente que le lecteur doit retrouver.
        majoritaire = len(groupes) > 1 and len(groupes[0]) > len(groupes[1])
        parties = []
        for rang, groupe in enumerate(groupes):
            chapitres = ", ".join(str(n) for n in dict.fromkeys(m.chapitre for m in groupe))
            partie = f"{groupe[0].montant_lu} (ch. {chapitres})"
            if not (rang == 0 and majoritaire) and groupe[0].extrait:
                partie += f" — « {groupe[0].extrait} »"
            parties.append(partie)
        suffixe = f" (annee {self.annee})" if self.annee is not None else ""
        return f"{self.libelle}{suffixe} : {' ; '.join(parties)}"


def _annee_proche(texte: str, pres_de: int | None = None) -> int | None:
    """L'annee mentionnee dans la fenetre de contexte, la plus PROCHE du montant.

    La premiere venue ne suffit pas : « la trajectoire devient positive dès
    l'année 2 et solide en année 3 (résultat net de 42 000 €) » rangeait
    42 000 € dans l'année 2 (business plan `5c5e91b9`, corpus du 14/09/2026).
    """
    trouvees = list(_ANNEE_RE.finditer(texte))
    if not trouvees:
        return None
    match = trouvees[0] if pres_de is None else min(
        trouvees, key=lambda m: min(abs(m.start() - pres_de), abs(m.end() - pres_de)),
    )
    valeur = match.group(1) or match.group(2) or match.group(3)
    if valeur is None:
        return _RANG_ORDINAL.get(match.group(4).casefold())
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
            if _FIN_DE_PHRASE.search(entre):
                continue
            if entre.count("|") > _CELLULES_MAX_FRANCHIES:
                continue
            debut_phrase_libelle = max(
                texte.rfind(c, 0, occurrence.start()) for c in ".!?\n"
            ) + 1
            avant_libelle = texte[debut_phrase_libelle:occurrence.start()]
            if _COMPARAISON_AVANT.search(avant_libelle):
                continue
            # La valeur est écrite AVANT le libellé : « les 54 276 € de chiffre
            # d'affaires prévisionnel de l'année 1 et même les 269 721 € projetés
            # en année 3 ». Le premier montant qui suit appartient à la suite.
            if _VALEUR_AVANT_LIBELLE.search(avant_libelle):
                continue
            if entre.rfind("(") > entre.rfind(")"):
                fermeture = fenetre.find(")", montant.start())
                interieur = fenetre[entre.rfind("(") + 1:fermeture if fermeture >= 0 else None]
                if _OPERATEUR.search(interieur):
                    continue
            if _FIN_DE_TRAJECTOIRE.search(entre):
                continue
            # Et son DÉBUT : « passe de 54 276 € à 269 721 € entre l'année 1 et
            # l'année 3 ». Aucun des deux montants n'a d'année propre dans la
            # phrase — l'année la plus proche est celle de l'autre.
            if _DEBUT_DE_TRAJECTOIRE.match(fenetre[montant.end():]):
                continue
            if _COORDINATION.search(entre):
                continue
            # Un AUTRE libelle surveille entre les deux : le montant est le
            # sien. « ...un point de marge brute en moins ramenerait
            # l'excedent brut d'exploitation a 34 800 euros » — 34 800 est
            # l'EBE, et l'EBE est deja surveille pour lui-meme.
            #
            # Regle 4 : viser la CLASSE. Enumerer les concepts voisins serait
            # sans fin, alors que la liste de ce qui est surveille EST la
            # liste de ce qui peut se confondre — et elle se tient a jour
            # toute seule (regle 5).
            if any(
                autre != cle and re.search(motif_autre, entre, re.IGNORECASE)
                for autre, motif_autre in _LIBELLES_SURVEILLES.items()
            ):
                continue

            # Une PÉRIODICITÉ ou une unité APRÈS le montant : « marge brute de
            # 4 € par abonné », « trésorerie de 1 500 € par mois ». Ce n'est pas
            # la grandeur du libellé, et l'opposer au total de l'exercice
            # produisait une divergence sur un document juste. Le cas AVANT le
            # montant (« marge brute unitaire ») est déjà dans les mots de rupture.
            if _PAR_UNITE_APRES.match(fenetre[montant.end():]):
                continue
            # Un AUTRE libellé nommé juste APRÈS le montant : « seuil de
            # rentabilité déjà établis : 54 276 euros de chiffre d'affaires ».
            # Le montant est le sien — symétrique du libellé glissé avant.
            apres = texte[fin_libelle + montant.end():fin_libelle + montant.end() + 40]
            complement = _COMPLEMENT_DE_GRANDEUR.match(apres)
            if complement and (
                _MOTS_DE_RUPTURE.match(apres, complement.end())
                or any(
                    autre != cle
                    and re.compile(motif_autre, re.IGNORECASE).match(apres, complement.end())
                    for autre, motif_autre in _LIBELLES_SURVEILLES.items()
                )
            ):
                continue
            # Une valeur de SCÉNARIO n'est pas la valeur retenue : « un point de
            # marge en moins ramènerait l'EBE à 34 800 € », « dans le scénario
            # pessimiste, le résultat net tombe à 42 500 € ». Opposée à la valeur
            # centrale, elle faisait accuser un prévisionnel qui présente sa
            # sensibilité — ce qu'un banquier attend (corpus du 14/09/2026).
            debut_phrase = max(texte.rfind(c, 0, occurrence.start()) for c in ".!?\n") + 1
            if _PHRASE_DE_SCENARIO.search(texte[debut_phrase:fin_libelle + montant.end()]):
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
                annee = _annee_proche(
                    texte[debut_ctx:fin_ctx], pres_de=fin_libelle + montant.start() - debut_ctx,
                )
                if annee is None:
                    continue
            else:
                annee = None

            # Centrée sur le LIBELLÉ : partir du début d'une longue phrase montrait
            # souvent une autre valeur que celle retenue (« le résultat net de la
            # première année, 9 000 euros… » pour une mention à 45 000 €).
            phrase = " ".join(
                texte[max(debut_phrase, occurrence.start() - 60):fin_libelle + montant.end() + 40]
                .split()
            )
            mentions.append(
                Mention(
                    chapitre=chapitre_numero,
                    libelle=cle,
                    annee=annee,
                    montant_lu=montant.group(0).strip(),
                    montant_base=base,
                    extrait=phrase[:180],
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
#: Fraction de la MEDIANE des chapitres du meme document sous laquelle un
#: chapitre est tenu pour avorte. A 40 %, un chapitre de 250 mots au milieu de
#: chapitres de 625 est signale ; un chapitre de 470, non — et il ne devait pas
#: l'etre, le document valide par la cliente ayant lui-meme des parties courtes.
_PLANCHER_RATIO_VOISINS = 0.40

#: Plancher absolu, independant de la mediane : un chapitre de trente mots est
#: avorte meme si tout le document est court. Sans lui, un document
#: uniformement indigent se declarerait sain — un controle qui se compare a
#: lui-meme se donne toujours raison (regle 9).
_PLANCHER_ABSOLU_MOTS = 120


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
# ── 5 registres methodologiques (WAOME, juillet 2026) ──────────────────────
# Evangeline distingue 5 natures d'information dans une etude de marche :
# faits verifies, estimations, hypotheses projet, ambitions dirigeantes,
# elements a tester. Sans ce cadre, le modele melange sources publiees et
# projections calibrees — un lecteur bancaire ne peut plus arbitrer. On
# expose la liste comme constante (regle 5) importee par le prompt EM et
# par la documentation methodologique du chapitre Sources.
REGISTRES_METHODO: dict[str, tuple[str, str]] = {
    "faits":       ("Faits documentes",
                    "Chiffres et donnees publies par des sources identifiees "
                    "(institutions, cabinets, textes reglementaires)."),
    "estimations": ("Estimations sectorielles",
                    "Valeurs projetees a partir de croisements methodologiques, "
                    "presentees en fourchette avec la mediane retenue."),
    "hypotheses":  ("Hypotheses projet",
                    "Choix structurants a valider par l'execution."),
    "ambitions":   ("Ambitions commerciales",
                    "Objectifs chiffres du dirigeant, calibres par l'etude."),
    "a_tester":    ("Elements a tester",
                    "Points de verification pratique a confirmer dans les "
                    "6-12 premiers mois d'activite."),
}


# Criteres de selection des concurrents — « Cahier des charges technique V1 —
# Etude de la concurrence », etape 1.4, CRITERES DE SELECTION (p. 11-12).
# Repris verbatim et dans leur ordre : cette constante est la source unique
# injectee dans le prompt EC (prompts.py), donc la formuler autrement revient a
# trier sur d'autres criteres que ceux du document.
#
# Corrige le 05/08/2026. La liste precedente en comptait cinq, dont trois du
# document manquaient — visibilite digitale et terrain, intensite concurrentielle
# observee, potentiel d'enseignement strategique — et dont une, « Anciennete sur
# le marche », n'apparait NULLE PART dans les 33 pages. Le systeme retenait donc
# ses onze acteurs sur une grille qui n'etait pas celle de la cliente.
CRITERES_TRI_CONCURRENTS: tuple[str, ...] = (
    "Influence sur le marché (notoriété, parts de marché perçues)",
    "Proximité avec l'offre du projet",
    "Proximité avec la clientèle cible",
    "Présence sur la zone ou accessibilité depuis cette zone",
    "Visibilité digitale et terrain",
    "Intensité concurrentielle observée",
    "Potentiel d'enseignement stratégique pour le projet",
)

#: Un TITRE de section, pas une mention. L'ancien motif attrapait la phrase
#: « concurrents directs » n'importe où — prose, cellule de tableau, rappel de
#: consigne. Tant qu'un seul chapitre parlait des concurrents, l'écart passait
#: inaperçu ; la base consolidée transmise partout (10/08/2026) a mis la
#: phrase dans chaque chapitre, et le recontrôle de `026fecea` a rendu
#: QUARANTE-SEPT « sections » à zéro concurrent — quarante-sept motifs
#: introuvables dans le document (règle 2).
_SOUS_SECTIONS_CONCURRENTS: dict[str, re.Pattern[str]] = {
    "directs": re.compile(
        r"^#{2,4}\s+(?:\d[\w.]*\s+)?.{0,40}concurrent[s]?\s+direct[s]?",
        re.IGNORECASE | re.MULTILINE,
    ),
    "indirects": re.compile(
        r"^#{2,4}\s+(?:\d[\w.]*\s+)?.{0,40}concurrent[s]?\s+indirect[s]?",
        re.IGNORECASE | re.MULTILINE,
    ),
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
        # Le compteur ne sait compter que des PUCES. Une section qui liste ses
        # acteurs en TABLEAU — la forme normale du contrat structuré — lui est
        # invisible : zéro puce n'y signifie pas zéro concurrent, mais une
        # matière qu'il ne sait pas lire. Juger « 0 trouvé » là-dessus, c'est
        # comparer à une extraction fausse — pire qu'un contrôle absent
        # (règle 2). On ne juge que ce qu'on a su compter.
        if trouves == 0:
            continue
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
    """Chaque section « Concurrents » presente les cardinaux exacts — PAR CHAPITRE.

    La version d'origine ADDITIONNAIT les comptes de tous les chapitres. Elle
    etait juste tant qu'un seul chapitre listait les acteurs. Depuis que la
    base consolidee est transmise a chaque chapitre (10/08/2026), plusieurs
    chapitres la reprennent legitimement — c'est meme la consigne (« liste
    figee du chapitre 1 »). Le job reel `026fecea` a ete bloque sur
    « 20 trouves, 8 attendus » : 8 au chapitre 1, 8 au chapitre 2, 4 en
    synthese. Vingt concurrents que personne n'a ecrits — le motif etait
    introuvable dans le document (regle 2).

    Le compte se juge donc la ou il se fait : toute section qui liste doit
    lister juste, et un document qui reprend deux fois ses huit directs est
    plus conforme, pas moins. Aucune sous-section detectee = silence — on ne
    signale rien plutot que d'inventer un defaut sur un chapitre qui n'a
    jamais eu vocation a lister (regle 4).
    """
    divergents: list[CompteConcurrents] = []
    for numero, corps in sections:
        for c in compter_concurrents(numero, corps):
            if c.trouves != c.attendus:
                divergents.append(c)
    return divergents


# ── Piliers de la strategie business : les 4 sont toujours poses ────────────
#
# Consigne d'Evangeline (fiche 4, question 1) : pour une strategie business, les
# 4 piliers sont TOUJOURS traites. On les verifie presents dans le document.
#
# ARBITRAGE DU 05/08/2026 — deux documents de la cliente se contredisent.
#
# La fiche 4 nommait ces piliers « Planning editorial » et « Analyse de la
# tarification ». Le cahier des charges « STRATEGIES BUSINESS AUTOMATISEES »
# (96 pages) n'emploie JAMAIS ces deux expressions — verifie sur l'integralite
# du document — et exclut explicitement que le systeme devienne « un calendrier
# editorial ». Sa colonne vertebrale est en sept parties, dont PARTIE IV
# « VISIBILITE & ACQUISITION » et PARTIE V « RENTABILITE & MODELE ECONOMIQUE ».
#
# Le controle etait donc pire qu'inutile : il BLOQUAIT au gate une strategie
# strictement conforme au cahier des charges. Et pas seulement sur ces deux
# piliers — le pilier 1 exigeait « positionnement & specialisation » quand le
# document ecrit « positionnement & differenciation ». Trois piliers sur quatre
# echouaient sur un document conforme.
#
# Plutot que de supprimer le controle (il porte une intention reelle : quatre
# axes structurants doivent etre traites) ou de choisir un document contre
# l'autre, chaque pilier accepte DESORMAIS les deux vocabulaires. Il continue
# d'echouer bruyamment si un axe est absent des deux facons a la fois — ce qui
# est le seul cas ou l'on peut affirmer qu'il manque (regles 1 et 2).
#
# A rouvrir avec Evangeline : lequel des deux documents fait foi.

PILIERS_STRATEGIE: dict[str, tuple[str, str]] = {
    "positionnement": (
        "PILIER 1",
        rf"positionnement(?:{_S}+&{_S}+|{_S}+et{_S}+)"
        rf"(?:sp[ée]cialisation|diff[ée]renciation)",
    ),
    "offre": ("PILIER 2", rf"structuration{_S}+de{_S}+l['’]offre"),
    "visibilite": (
        "PILIER 3",
        rf"(?:planning{_S}+[ée]ditorial|visibilit[ée]|acquisition)",
    ),
    "rentabilite": (
        "PILIER 4",
        rf"(?:analyse{_S}+de{_S}+la{_S}+tarification|rentabilit[ée]"
        rf"|mod[èe]le{_S}+[ée]conomique)",
    ),
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


# ── Les DECISIONS que chaque pilier doit livrer ────────────────────────────
#
# Cliente, 12/08/2026, sur une strategie notee 7,5/10 :
#
#   « le document est encore trop proche d'un audit / diagnostic strategique :
#   il analyse beaucoup, explique beaucoup et repete parfois les constats. Je
#   souhaite que la strategie apporte davantage de solutions, methodes,
#   decisions et actions directement applicables. […] Mes 4 piliers doivent
#   devenir la colonne vertebrale OBLIGATOIRE du livrable. […] A la fin, le
#   client ne doit pas simplement se dire "je comprends mieux mon entreprise",
#   mais "je sais exactement ce que je dois faire maintenant, dans quel ordre,
#   comment et avec quels indicateurs". »
#
# Le controle des piliers ci-dessus verifiait qu'un AXE est traite. Il rendait
# donc `passed` sur un chapitre qui analyse le positionnement pendant mille
# six cents mots sans jamais dire lequel est retenu — exactement le document
# qu'elle decrit. Un axe traite n'est pas une decision prise.
#
# ## Une seule liste, deux lecteurs (regle 5)
#
# `prompts.py` construit la consigne a partir de cette declaration, et la
# strategy STR juge le document sur la meme. Ecrire la demande d'un cote et le
# controle de l'autre, c'est la contradiction interne qui a coute 5,22 € le
# 10/08 : une consigne qui ordonne ce qu'un controle ignore, ou l'inverse.
#
# ## Verrouillee ou seulement demandee
#
# Une decision porte un `motif` quand elle a une formulation francaise stable
# — « cible prioritaire », « planning editorial », « 90 jours ». Elle n'en
# porte pas quand sa presence ne se lit pas sans interpreter : « montrer le
# parcours logique du client entre les offres » est une exigence de fond, pas
# une chaine de caracteres. Pretendre la controler produirait un motif faux,
# pire qu'un controle absent (regle 2). Ces demandes-la vivent dans la
# consigne et se jugent a la relecture — le champ vide le DIT, au lieu de
# laisser croire que tout est verrouille.
#
# ## Pourquoi le document entier, mais un chapitre nomme
#
# Le jugement porte sur le corpus COMPLET : rien ne garantit que le modele
# pose la cible prioritaire au chapitre 8 plutot qu'au 6, et bloquer sur son
# emplacement punirait un document juste. Le chapitre porteur ne sert qu'a
# router la reparation vers celui qui doit l'accueillir.


@dataclass(frozen=True)
class DecisionAttendue:
    """Une decision que le livrable doit prendre, pas seulement eclairer."""

    libelle: str
    #: Vide = demandee par la consigne, non verrouillee par le gate. Une
    #: LOCUTION (« canaux a eviter ») : sa presence suffit.
    motif: str = ""
    #: L'intitule que le chapitre porteur ecrit en tete de ligne de son
    #: tableau « Decisions retenues ». Il satisfait le `motif` (un test le
    #: verifie) : la consigne fait ecrire ce que le controle reconnait.
    etiquette: str = ""
    #: La meme decision prise par un VERBE (« Nous excluons Facebook Ads »).
    #: Jugee plus severement que la locution : la phrase doit DECIDER — ni
    #: negation pres du verbe, ni tiers qui agit a la place du projet. Voir
    #: `_forme_qui_decide`.
    forme_verbale: str = ""


@dataclass(frozen=True)
class BlocDeDecisions:
    """Un pilier — ou la feuille de route — et ce qu'il doit trancher."""

    cle: str
    intitule: str
    #: Chapitre qui accueille naturellement ces decisions, pour router la
    #: reparation. Le controle, lui, lit tout le document.
    chapitre_porteur: int
    decisions: tuple[DecisionAttendue, ...]
    #: Le chapitre porteur recoit-il le tableau « Decisions retenues » ? Non
    #: pour la feuille de route : son prompt pose deja ses horizons et ses
    #: indicateurs dans deux tableaux, et un troisieme les repeterait.
    tableau_de_decisions: bool = True


_D = DecisionAttendue

#: Espace SOUPLE : elle accepte le retour a la ligne, contrairement a `_S`.
#:
#: `_S` a raison ailleurs — un libelle financier ne se coupe pas en deux
#: paragraphes. Ici il a tort : un document markdown coupe ses lignes ou il
#: veut, et « les canaux \n a eviter » est le meme francais que « les canaux a
#: eviter ». Mesure du 12/08/2026 : deux decisions sur vingt-quatre echouaient
#: sur un document qui les prend, uniquement a cause d'un retour a la ligne.
#: Un controle qui depend de la LARGEUR DE COLONNE juge autre chose que ce
#: qu'il prétend juger (regle 2).
_E = r"\s"


# ## Une decision se prend aussi par un VERBE
#
# Les motifs attendaient une locution collee : « canaux a eviter », « offre
# phare », « frequence de publication ». Les documents, eux, decident comme un
# consultant ecrit. Mesure du 14/09/2026 sur les douze strategies du corpus
# (12 sur 12 bloquees, 40 motifs) — phrases relevees dans les Word livres :
#
#     « Nous excluons Facebook Ads, Google Ads et les flyers non cibles »
#     « Toute action publicitaire (Facebook, Google) est reportee »
#     « deux publications par semaine sur les canaux prioritaires »
#     « nous resserrons le positionnement sur l'ancrage local »
#
# Toutes accusees de ne rien decider. Et le controleur final reecrivait — donc
# payait — les chapitres 8, 10 et 13 sur ces motifs, sans jamais les fermer.
#
# ## Mais un verbe ne decide pas toujours
#
# Relecture du meme jour : la premiere version acceptait « Nous n'excluons
# aucun canal », « Aucun reseau n'est encore exclu », « Les concurrents
# publient une video par semaine », « La radio est deconseillee par certains
# experts ». Un verbe de decision nie, ou porte par un tiers, ne decide rien
# pour le projet. D'ou deux champs : la LOCUTION (`motif`), jugee comme avant,
# et la FORME VERBALE (`forme_verbale`), acceptee seulement si elle decide.

#: Ce qu'une decision de visibilite peut viser, plateformes nommees comprises.
_CANAL = (
    r"\b(?:canal|canaux|leviers?|r[ée]seaux?|plateformes?|publicit[ée]s?"
    r"|publicitaires?|ads|campagnes?|flyers?|prospection|salons?|e-?mailing"
    r"|affichage|presse|radio|annuaires?|marketplaces?|facebook|instagram"
    r"|linkedin|tiktok|youtube|pinterest|snapchat|google|meta)\b"
)

#: « Est » suivi d'au plus un mot, puis le participe.
_ATTRIBUT = r"\b(?:est|sont|reste|restent|sera|seront|demeure|demeurent)\s+(?:\w+\s+)?"

#: Le verbe qui ECARTE, conjugue comme une decision du projet.
_VERBE_QUI_ECARTE = (
    r"\b(?:excluons|[ée]cartons|reportons|renon[çc]ons|abandonnons|proscrivons"
    r"|[ée]vitons|suspendons|gelons|diff[ée]rons|arr[êe]tons)\b"
    r"|\b(?:excluez|[ée]cartez|reportez|renoncez|abandonnez|proscrivez|[ée]vitez"
    r"|suspendez|arr[êe]tez)\b(?!-)"
    r"|\bon\s+(?:exclut|[ée]carte|reporte|[ée]vite|abandonne|renonce\s+[àa])\b"
)
_A_ECARTER = (
    r"\b[àa]\s+(?:[ée]viter|exclure|proscrire|[ée]carter|abandonner|reporter"
    r"|diff[ée]rer)\b"
)
_PARTICIPE_QUI_ECARTE = (
    r"(?:exclue?s?|[ée]cart[ée]e?s?|report[ée]e?s?|abandonn[ée]e?s?|proscrite?s?"
    r"|suspendue?s?|gel[ée]e?s?|diff[ée]r[ée]e?s?|d[ée]conseill[ée]e?s?)\b"
)

#: Entre le verbe et ce qu'il vise : pas de virgule ni de nouvelle proposition.
#: « Évitez les erreurs de facturation, puis lancez la campagne » n'écarte pas
#: la campagne.
_ECART = r"[^.!?\n,;:]{0,50}?"

_OFFRE = r"\b(?:offres?|formules?|paliers?|prestations?|abonnements?|gammes?)\b"

_COMPTE = r"(?:\d+|une?|deux|trois|quatre|cinq|six|sept|huit|neuf|dix)"
_PUBLICATION = (
    r"(?:publications?|posts?|contenus?|articles?|vid[ée]os?|newsletters?"
    r"|stories|reels?|envois?)"
)

DECISIONS_STRATEGIE: tuple[BlocDeDecisions, ...] = (
    BlocDeDecisions(
        cle="positionnement",
        intitule="PILIER 1 — Positionnement & spécialisation",
        chapitre_porteur=8,
        decisions=(
            _D("la cible prioritaire, nommée",
               rf"(?:cible|client[èe]le|segment)s?{_E}+"
               rf"(?:prioritaires?|principa(?:l|le|ux|les))",
               etiquette="Cible prioritaire"),
            _D("la cible secondaire",
               rf"(?:cible|client[èe]le|segment)s?{_E}+"
               rf"(?:secondaires?|compl[ée]mentaires?)",
               etiquette="Cible secondaire",
               forme_verbale=(
                   r"\b(?:cibles|segments|publics|profils|client[èe]les)\b"
                   r"[^.!?\n]{0,60}?\b(?:secondaires|en\s+second\s+rang)\b"
               )),
            _D("le positionnement retenu",
               rf"positionnement{_E}+"
               rf"(?:retenu|recommand[ée]|choisi|cible|d[ée]fendu"
               rf"|propos[ée]|pr[ée]conis[ée])",
               etiquette="Positionnement retenu",
               forme_verbale=(
                   r"\b(?:retenons|choisissons|resserrons|recentrons|assumons"
                   r"|adoptons|d[ée]fendons|arbitrons)\b[^.!?\n]{0,60}?positionnement"
                   r"|\b(?:positionnons|repositionnons)\b"
               )),
            _D("la spécialisation recommandée",
               etiquette="Spécialisation recommandée"),
            _D("le produit ou service à pousser en priorité",
               rf"(?:offre|produit|service|prestation|formule|palier|abonnement)s?{_E}+"
               rf"(?:phares?|locomotives?|[àa]{_E}+pousser)",
               etiquette="Offre à pousser en priorité",
               forme_verbale=(
                   r"\b(?:offre|produit|service|prestation|formule|palier|abonnement)s?"
                   r"(?:\s+\S+)?\s+(?:prioritaires?|[àa]\s+pousser|[àa]\s+mettre\s+en\s+avant)"
               )),
            _D("la proposition de valeur", rf"proposition{_E}+de{_E}+valeur",
               etiquette="Proposition de valeur"),
            _D("les éléments concrets de différenciation",
               etiquette="Éléments de différenciation"),
            _D("le message commercial principal",
               rf"(?:message|discours|accroche|promesse)s?{_E}+"
               rf"(?:commercial|commerciale|principal|principale|cl[ée])",
               etiquette="Message commercial principal"),
            _D("ce qu'il faut volontairement abandonner ou repousser",
               r"(?:abandonner|abandonn[ée]e?s?|renoncer|renonc[ée]e?s?"
               r"|[ée]carter|[ée]cart[ée]e?s?|repousser|repouss[ée]e?s?"
               r"|non-?priorit[ée]s?)",
               etiquette="À abandonner ou repousser"),
        ),
    ),
    BlocDeDecisions(
        cle="offre",
        intitule="PILIER 2 — Structuration de l'offre",
        chapitre_porteur=10,
        decisions=(
            _D("les offres à conserver, modifier, supprimer ou reporter",
               rf"[àa]{_E}+(?:conserver|maintenir|supprimer|arr[êe]ter"
               rf"|reporter|retravailler)",
               etiquette="Offres à conserver, modifier, supprimer ou reporter",
               forme_verbale=(
                   r"\b(?:conservons|maintenons|supprimons|arr[êe]tons|reportons"
                   r"|suspendons|gelons|retirons|abandonnons|gardons)\b"
                   rf"{_ECART}{_OFFRE}"
                   rf"|{_OFFRE}[^.!?\n]{{0,120}}?{_ATTRIBUT}"
                   r"(?:conserv[ée]e?s?|maintenue?s?|supprim[ée]e?s?|arr[êe]t[ée]e?s?"
                   r"|report[ée]e?s?|suspendue?s?|gel[ée]e?s?|retir[ée]e?s?"
                   r"|abandonn[ée]e?s?)\b"
               )),
            _D("l'offre d'entrée de gamme",
               rf"(?:entr[ée]e{_E}+de{_E}+gamme"
               rf"|offre{_E}+d['’](?:appel|entr[ée]e))",
               etiquette="Offre d'entrée de gamme"),
            _D("l'offre premium",
               rf"premium|haut{_E}+de{_E}+gamme|gamme{_E}+sup[ée]rieure"
               rf"|offre{_E}+haute",
               etiquette="Offre premium"),
            _D("les possibilités d'upsell et de cross-sell",
               rf"up-?sell|cross-?sell|vente{_E}+(?:additionnelle|crois[ée]e)"
               rf"|mont[ée]e{_E}+en{_E}+gamme",
               etiquette="Vente additionnelle et montée en gamme"),
            _D("le parcours du client entre les offres",
               rf"parcours{_E}+(?:client|d['’]achat|utilisateur)",
               etiquette="Parcours client entre les offres"),
            _D("le rôle de chaque offre : acquisition, marge, "
               "récurrence ou fidélisation",
               etiquette="Rôle de chaque offre"),
        ),
    ),
    BlocDeDecisions(
        cle="visibilite",
        intitule="PILIER 3 — Visibilité, acquisition & planning éditorial",
        chapitre_porteur=13,
        decisions=(
            # Au SINGULIER aussi : « le blog reste un canal secondaire »,
            # « LinkedIn est le canal prioritaire ». Seul le pluriel était lu.
            # Le singulier passe par la FORME VERBALE, qui écarte la négation
            # et le tiers (« il n'y a pas de canal à éviter », « un média
            # secondaire selon Médiamétrie ») — le motif nominal ne le fait pas.
            _D("les canaux prioritaires",
               rf"(?:canaux|leviers|r[ée]seaux){_E}+"
               rf"(?:prioritaires|principaux|majeurs|structurants"
               rf"|de{_E}+premier{_E}+plan)",
               forme_verbale=(
                   r"\b(?:canal|levier)\b[^.!?\n]{0,30}?\b(?:prioritaire|principal|majeur)\b"
               ),
               etiquette="Canaux prioritaires"),
            _D("les canaux secondaires",
               rf"(?:canaux|leviers|r[ée]seaux){_E}+"
               rf"(?:secondaires|compl[ée]mentaires|d['’]appoint"
               rf"|de{_E}+soutien)",
               etiquette="Canaux secondaires",
               forme_verbale=(
                   r"\b(?:canaux|leviers|r[ée]seaux|plateformes|supports|m[ée]dias)\b"
                   r"[^.!?\n]{0,60}?\b(?:secondaires|d['’]appoint|en\s+second\s+rang)\b"
                   r"|\b(?:canal|levier)\b[^.!?\n]{0,30}?\b(?:secondaire|d['’]appoint)\b"
               )),
            _D("les canaux à éviter",
               rf"(?:canaux|leviers|r[ée]seaux|plateformes|supports){_E}+"
               rf"(?:[àa]{_E}+(?:[ée]viter|proscrire|exclure|abandonner"
               rf"|ne{_E}+pas{_E}+(?:investir|privil[ée]gier))"
               rf"|d[ée]conseill[ée]s?|non{_E}+retenus?)",
               etiquette="Canaux à éviter",
               forme_verbale=(
                   rf"(?:{_VERBE_QUI_ECARTE}){_ECART}{_CANAL}"
                   rf"|{_CANAL}{_ECART}(?:{_A_ECARTER}|{_ATTRIBUT}{_PARTICIPE_QUI_ECARTE})"
                   rf"|{_A_ECARTER}{_ECART}{_CANAL}"
               )),
            _D("les thématiques et types de contenus recommandés",
               etiquette="Thématiques et contenus recommandés"),
            _D("la fréquence de publication",
               rf"(?:fr[ée]quence|rythme|cadence){_E}+(?:de{_E}+)?"
               rf"(?:publication|parution|diffusion|contenus?)",
               etiquette="Fréquence de publication",
               forme_verbale=(
                   rf"\b{_COMPTE}\s+{_PUBLICATION}\s+(?:\S+\s+){{0,3}}?"
                   r"(?:par|chaque|/)\s*(?:jour|semaine|quinzaine|mois)"
                   rf"|\d+\s*{_PUBLICATION}\s*/\s*(?:semaine|mois)"
                   rf"|{_PUBLICATION}\s+(?:hebdomadaires?|mensuel(?:le)?s?"
                   r"|quotidien(?:ne)?s?|bimensuel(?:le)?s?)"
                   rf"|\bpubli\w*\s+(?:\S+\s+){{0,3}}?{_COMPTE}\s+fois\s+par\s+(?:jour|semaine|mois)"
               )),
            _D("un planning éditorial concret, sur un mois au minimum",
               rf"(?:planning|calendrier|programme){_E}+[ée]ditorial",
               etiquette="Planning éditorial du premier mois"),
            _D("l'acquisition hors réseaux sociaux : prospection, "
               "partenariats, référencement, prescription, événements, emailing",
               r"prospection|partenariats?|r[ée]f[ée]rencement|emailing"
               r"|prescription|[ée]v[ée]nements?",
               etiquette="Prospection, partenariats et prescription"),
            _D("les outils pratiques pour mettre tout cela en œuvre",
               etiquette="Outils de mise en œuvre"),
        ),
    ),
    BlocDeDecisions(
        cle="rentabilite",
        intitule="PILIER 4 — Tarification & rentabilité",
        chapitre_porteur=14,
        decisions=(
            _D("une recommandation tarifaire concrète : un prix cible chiffré",
               rf"(?:prix|tarif)s?{_E}+"
               rf"(?:cibles?|recommand[ée]s?|conseill[ée]s?|pr[ée]conis[ée]s?)"
               rf"|(?:recommandation|proposition|strat[ée]gie|grille)s?{_E}+"
               rf"(?:tarifaires?|de{_E}+prix)"
               rf"|fourchette{_E}+(?:tarifaire|de{_E}+prix)",
               etiquette="Prix cible recommandé"),
            _D("le prix par niveau d'offre", etiquette="Prix par niveau d'offre"),
            _D("la logique de montée en gamme",
               etiquette="Logique de montée en gamme"),
            _D("l'impact attendu sur la marge",
               rf"(?:impact|effet|cons[ée]quence)[^.]{{0,60}}marge"
               rf"|marges?{_E}+(?:attendues?|cibles?|projet[ée]es?"
               rf"|suppl[ée]mentaires?)",
               etiquette="Impact attendu sur la marge"),
            _D("la distinction explicite entre les prix issus du dossier "
               "et les prix recommandés par l'analyse",
               etiquette="Prix du dossier et prix recommandés"),
        ),
    ),
    BlocDeDecisions(
        cle="feuille_de_route",
        intitule="FEUILLE DE ROUTE OPÉRATIONNELLE",
        chapitre_porteur=17,
        tableau_de_decisions=False,
        decisions=(
            _D("les actions à 30, 60 et 90 jours",
               rf"\b(?:30|60|90){_E}*jours", etiquette="30 jours"),
            _D("les actions à 6 et 12 mois",
               rf"\b(?:6|12|six|douze){_E}*mois", etiquette="6 mois"),
            _D("ce qui est prioritaire et ce qui est secondaire"),
            _D("les indicateurs à suivre",
               rf"\bKPI\b|indicateurs?{_E}+(?:cl[ée]s?|de{_E}+"
               rf"(?:suivi|performance|pilotage|r[ée]ussite))",
               etiquette="Indicateur de réussite"),
            _D("le seuil à partir duquel poursuivre, modifier ou arrêter "
               "une action",
               rf"seuils?{_E}+(?:de{_E}+)?(?:d[ée]cision|d[ée]clenchement|alerte)"
               rf"|crit[èe]re{_E}+d['’]arr[êe]t|point{_E}+de{_E}+bascule"
               rf"|r[èe]gle{_E}+d['’]arbitrage"
               rf"|(?:poursuivre|maintenir|continuer)[^.]{{0,90}}"
               rf"(?:modifier|ajuster)[^.]{{0,90}}"
               rf"(?:arr[êe]ter|abandonner|stopper)",
               etiquette="Seuil de décision"),
        ),
    ),
)


@dataclass(frozen=True)
class DecisionManquante:
    """Une decision attendue que le document ne prend nulle part."""

    cle_bloc: str
    intitule_bloc: str
    chapitre_porteur: int
    libelle: str


#: Une negation PRES du verbe : « Nous n'excluons aucun canal », « Aucun reseau
#: n'est encore exclu ». Cherchee dans la forme trouvee et juste avant elle —
#: pas dans toute la phrase, ou « Nous excluons Facebook Ads tant que le seuil
#: n'est pas atteint » serait refusee pour sa subordonnee.
_NEGATION = re.compile(
    r"\bn['’]|\bne\b|\baucune?s?\b|\bpas\s+(?:de|d['’]|encore)\b|\bsans\b|\bni\b",
    re.IGNORECASE,
)

#: Un tiers qui agit ou juge a la place du projet : « les concurrents
#: publient », « deconseillee par certains experts », « souvent reportees par
#: les TPE », « les offres du marche sont maintenues ».
_TIERS = re.compile(
    r"\b(?:concurrents?|TPE|PME|experts?|certains|certaines|la\s+plupart|souvent"
    r"|en\s+moyenne|(?:du|le|au|sur\s+le)\s+march[ée]|chez\s+(?:le|la|les|l['’]))\b",
    re.IGNORECASE,
)

_AVANT = 15
_AUTOUR = 40


def _forme_qui_decide(forme: str, corpus: str) -> bool:
    """Une occurrence de la forme verbale decide-t-elle pour le projet ?"""
    for trouve in re.finditer(forme, corpus, re.IGNORECASE):
        debut, fin = trouve.start(), trouve.end()
        # Les fenetres s'arretent a la phrase : un tiers ou une negation de la
        # phrase voisine ne retire rien a celle-ci.
        phrase_debut = max(corpus.rfind(c, 0, debut) for c in ".!?\n") + 1
        fins = [i for i in (corpus.find(c, fin) for c in ".!?\n") if i != -1]
        phrase_fin = min(fins) if fins else len(corpus)
        pres = corpus[max(phrase_debut, debut - _AVANT):fin]
        autour = corpus[max(phrase_debut, debut - _AUTOUR):min(phrase_fin, fin + _AUTOUR)]
        if _NEGATION.search(pres) or _TIERS.search(autour):
            continue
        return True
    return False


#: Une case « Ce qui est retenu » qui ne retient rien.
_CASE_VIDE = re.compile(r"^\s*(?:[—–-]|n\s*/?\s*a)?[\s.]*$", re.IGNORECASE)
_CASE_SANS_DECISION = re.compile(
    r"[àa]\s+(?:d[ée]finir|pr[ée]ciser|d[ée]terminer|confirmer|trancher)"
    r"|non\s+(?:tranch|d[ée]fini|renseign|d[ée]cid)\w*|ind[ée]termin\w*|\binconnu\w*"
    r"|\bne\s+permet\w*\s+pas|insuffisant\w*|pas\s+de\s+donn[ée]es",
    re.IGNORECASE,
)


def _sans_decisions_non_tranchees(corpus: str) -> str:
    """Retire du corpus les lignes « Decisions retenues » dont la case est vide.

    Relecture du 14/09/2026 : le tableau injecte au chapitre porteur ecrit
    l'etiquette que le motif reconnait. Sans ce filtre, « | Canaux a eviter |
    A definir | … | » fermait le motif sans que rien ne soit decide — le
    controle et sa reparation jugeaient sur la meme evidence (regle 9).
    """
    etiquettes = {
        _plat(d.etiquette)
        for bloc in DECISIONS_STRATEGIE for d in bloc.decisions if d.etiquette
    }
    lignes = []
    for ligne in corpus.splitlines():
        cellules = [c.strip() for c in ligne.strip().strip("|").split("|")]
        if (
            ligne.lstrip().startswith("|")
            and len(cellules) >= 2
            and _plat(cellules[0].strip("*")) in etiquettes
            and (_CASE_VIDE.match(cellules[1]) or _CASE_SANS_DECISION.search(cellules[1]))
        ):
            continue
        lignes.append(ligne)
    return "\n".join(lignes)


def _plat(texte: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texte.casefold())
        if unicodedata.category(c) != "Mn"
    ).strip()


def verifier_decisions_strategie(corpus: str) -> list[DecisionManquante]:
    """Les decisions VERROUILLEES que le document ne prend pas.

    Les autres — celles sans motif — sont demandees par la consigne et ne
    sont pas jugees ici : voir le commentaire de `DECISIONS_STRATEGIE`.
    """
    corpus = _sans_decisions_non_tranchees(corpus)
    manquantes: list[DecisionManquante] = []
    for bloc in DECISIONS_STRATEGIE:
        for decision in bloc.decisions:
            if not decision.motif:
                continue
            if re.search(decision.motif, corpus, re.IGNORECASE):
                continue
            if decision.forme_verbale and _forme_qui_decide(decision.forme_verbale, corpus):
                continue
            manquantes.append(DecisionManquante(
                cle_bloc=bloc.cle,
                intitule_bloc=bloc.intitule,
                chapitre_porteur=bloc.chapitre_porteur,
                libelle=decision.libelle,
            ))
    return manquantes


def detecter_chapitres_avortes(
    sections_avec_plafond: list[tuple[int, str, str, int]],
) -> list[ChapitreAvorte]:
    """Signale les chapitres manifestement plus courts QUE LEURS VOISINS.

    ## Pourquoi la reference a change

    Le seuil valait 30 % de `max_words`. Or `max_words` est une borne de
    PLANIFICATION — elle dimensionne la fenetre de tokens, le blueprint le dit
    lui-meme : « cible editoriale indicative […] injectee comme borne haute ».
    Ce n'est pas une cible a atteindre, et un plancher calcule dessus compare a
    la mauvaise reference (regle 2).

    Mesure du 05/08/2026, livrable reel `4b827759` : le gate a declare SIX
    chapitres « non produits », a 470 mots pour un plafond de 1 800. Or ce
    document pese 14 387 mots, soit 24 % de PLUS que le document valide par la
    cliente (11 580), et ses chapitres font 625 mots en moyenne. Le controle
    signalait donc comme avortes des chapitres a 75 % de la moyenne de leur
    propre document — et il le faisait sur un document plus dense que la
    reference.

    ## La nouvelle reference : le document lui-meme

    Un chapitre est avorte quand il est tres en dessous de SES VOISINS, pas
    d'un plafond theorique. La mediane des chapitres du meme document est une
    reference reelle, disponible, et qui s'adapte a chaque livrable sans
    constante a maintenir.

    Le plancher absolu reste : un chapitre de trente mots est avorte quelle que
    soit la mediane, y compris si tout le document est court.
    """
    mesures = [
        (numero, titre, _compter_mots(corps), max_words)
        for numero, titre, corps, max_words in sections_avec_plafond
        if max_words > 0
    ]
    if not mesures:
        return []

    longueurs = sorted(mots for _n, _t, mots, _m in mesures)
    mediane = longueurs[len(longueurs) // 2]
    seuil = max(int(mediane * _PLANCHER_RATIO_VOISINS), _PLANCHER_ABSOLU_MOTS)

    return [
        ChapitreAvorte(
            chapitre=numero,
            titre=titre,
            mots_rendus=mots,
            mots_attendus=seuil,
            ratio=mots / seuil if seuil else 0.0,
        )
        for numero, titre, mots, _max_words in mesures
        if mots < seuil
    ]


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

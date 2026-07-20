"""Extraction deterministe de l'etat chiffre client depuis le brief en texte libre.

Contexte (audit juillet 2026, cause racine n2) : l'etat chiffre client
(Brique 1) n'existait que si le formulaire Tally comportait des champs
structures INVESTISSEMENT_TOTAL, EMPRUNT, VERTICALES... En pratique le
porteur (et Evangeline elle-meme) ecrit le previsionnel EN TEXTE LIBRE dans
le brief. Ce texte n'atteignait jamais `seed_locked_facts_from_variables` :
aucun fait CLIENT n'etait verrouille, et les checks 2 et 3 du gate de
livraison s'auto-desactivaient en silence.

Ce module lit le texte du brief et en extrait les valeurs que le CLIENT a
lui-meme ecrites. Il n'INVENTE rien et n'estime rien :
- un motif doit etre explicitement libelle (« investissement total : X € »),
  sinon la cle n'est pas extraite ;
- la valeur retournee est la chaine telle qu'ecrite par le client, pas une
  valeur recalculee.

Les champs Tally structures restent prioritaires : l'extraction ne comble
que les cles absentes (cf. `enrich_variables_from_free_text`).
"""
from __future__ import annotations

import re

from core.numbers import MONEY, SPACE_CLASS

# Espaces et devises viennent de `core.numbers` — la source UNIQUE, partagee
# avec le gate. Ce module avait ses propres copies : identiques a l'oeil, mais
# deja divergentes (il manquait XAF, CFA et Mds€ ici). Le gate savait lire un
# montant en XAF, l'extraction non : pour le Cameroun, le Gabon, le Tchad ou
# le Congo — tous mappes vers XAF par `generation/coherence.py` — aucun fait
# client n'etait verrouille et le dossier bloquait sans cause lisible.
# Deux lectures du meme texte, c'est le defaut qu'on corrige : il n'en reste
# qu'une seule.
_SP = SPACE_CLASS

# Montant : « 1 250 000 € », « 920 000 EUR », « 44 245,50 € », « 1,25 M€ ».
_AMOUNT = MONEY

# Entre le libelle et le montant, le client ecrit « de », « : », « s'eleve a »...
# Remplissage court, SANS chiffre ni fin de phrase. Reserve aux libelles
# EXPLICITES (multi-mots) : « investissement total ... 1 250 000 € ».
_FILLER = r"[^.\n\d]{0,30}?"

# Connecteurs admis apres un libelle GENERIQUE (un seul mot). Volontairement
# limitatif : c'est le correctif de l'audit F3. Avec `_FILLER`, le libelle
# « investissement » capturait « investissement PUBLICITAIRE de 5 000 € » et
# le rangeait dans INVESTISSEMENT_TOTAL. Consequences en cascade : le check 0
# du gate etait satisfait par une valeur fausse (fausse securite, pire que le
# trou d'origine), et la reference d'ordre de grandeur tombait a 5 000 €, ce
# qui faisait bloquer tout investissement legitime a 1,2 M€.
# Un qualificatif qui n'est pas un connecteur (« publicitaire », « marketing »,
# « en formation ») change le sens du libelle : on refuse alors d'extraire.
_CONNECTOR = (
    r"(?:\s*(?:de|d'|:|=|s'[ée]l[èe]ve\s+[àa]|est\s+de|estim[ée]\s+[àa]|atteint)?\s*)"
)

# Un TOTAL, un CAPITAL ou un EMPRUNT ne sont jamais recurrents. Si le montant
# est suivi d'une periodicite, c'est un flux (loyer, mensualite, budget mensuel)
# — pas la valeur cherchee. Regle semantique, pas liste de domaines : elle vaut
# pour tous les libelles generiques sans avoir a enumerer « publicitaire »,
# « marketing », « en formation »...
_NOT_RECURRING = (
    r"(?!\s*(?:/|par\s+|\s*)(?:mois|an\b|ann[ée]e|semaine|jour|trimestre"
    r"|mensuel|annuel))"
)

# Fin de segment : point suivi d'un blanc, saut de ligne, ou fin de texte.
_SEGMENT_END = r"(?=\.[\s]|\.$|\n|$)"


def _amount_pattern(label: str) -> re.Pattern[str]:
    """« <libelle explicite> <remplissage court> <montant> ».

    Le `\\b` initial est indispensable : sans lui, un libelle court comme « CA »
    matche a l'interieur d'un autre mot (« ban-CA-ire ») et rattache le montant
    de la phrase voisine a la mauvaise cle.
    """
    return re.compile(rf"\b{label}{_FILLER}({_AMOUNT})", re.IGNORECASE)


def _strict_amount_pattern(label: str) -> re.Pattern[str]:
    """« <libelle generique> <connecteur> <montant non recurrent> ».

    Deux verrous par rapport a `_amount_pattern` :
    - pas de remplissage libre entre le libelle et le montant : un qualificatif
      inserе (« investissement PUBLICITAIRE de 5 000 € ») change le sens et
      doit faire echouer le motif ;
    - le montant ne doit pas etre suivi d'une periodicite : « 5 000 € par
      mois » est un flux, jamais un total ni un capital.

    A reserver aux libelles qui restent NON AMBIGUS reduits a un mot (apport,
    emprunt). Pour « investissement », meme durci, le libelle nu reste
    ambigu — il n'a donc pas de repli generique du tout.
    """
    return re.compile(rf"\b{label}{_CONNECTOR}({_AMOUNT}){_NOT_RECURRING}", re.IGNORECASE)


# Chaque cle canonique -> motifs, du plus specifique au plus general.
# Les libelles sont volontairement stricts : sans libelle explicite, pas
# d'extraction (mieux vaut un gate qui bloque qu'une valeur devinee).
_MONEY_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    # AUCUN repli sur « investissement » nu (audit) : le mot qualifie aussi bien
    # l'enveloppe du projet qu'un budget publicitaire, un investissement en
    # formation ou en R&D. Durcir le motif ne suffit pas — « investissement de
    # 5 000 € par mois EN PUBLICITE » place le qualificatif APRES le montant et
    # passait encore. Le libelle nu est intrinsequement ambigu : on ne devine
    # pas, on exige un libelle explicite. Sans lui, le check 0 du gate bloque et
    # un humain saisit la valeur — un blocage honnete vaut mieux qu'une fausse
    # reference, qui satisfait le check 0 avec une valeur inventee.
    "INVESTISSEMENT_TOTAL": (
        _amount_pattern(rf"investissement{_SP}+(?:total|initial|global|de{_SP}+d[ée]part)"),
        _amount_pattern(rf"(?:montant{_SP}+de{_SP}+l'|enveloppe{_SP}+d')investissement"),
        _amount_pattern(rf"co[ûu]t{_SP}+total{_SP}+du{_SP}+projet"),
        _amount_pattern(rf"budget{_SP}+(?:total|global){_SP}*(?:du{_SP}+projet)?"),
        # « Besoin total : 1 250 000 € HT » : formulation du brief SYNAPSES reel.
        # Je l'avais ratee — le montant etait sous les yeux du gate, qui
        # reclamait pourtant la donnee comme absente.
        _amount_pattern(rf"besoin{_SP}+(?:total|de{_SP}+financement|global)"),
    ),
    "APPORT": (
        _amount_pattern(rf"apport{_SP}+(?:personnel|propre|en{_SP}+capital|initial)"),
        _strict_amount_pattern(r"apport"),
    ),
    "EMPRUNT": (
        _amount_pattern(rf"(?:emprunt|pr[êe]t){_SP}+(?:bancaire|professionnel)"),
        _strict_amount_pattern(r"emprunt"),
    ),
    "SUBVENTIONS": (
        _amount_pattern(
            rf"(?:subventions?|aides?{_SP}+(?:et{_SP}+subventions?|publiques?))"
        ),
    ),
    "SEUIL_RENTABILITE": (
        _amount_pattern(rf"seuil{_SP}+de{_SP}+rentabilit[ée]"),
        _amount_pattern(rf"point{_SP}+mort"),
    ),
}

# Trajectoires pluriannuelles : « CA An1 250 272 €, An2 296 000 € ». On isole le
# segment de phrase qui suit le libelle, puis on collecte TOUS les montants
# qu'il contient, joints par « / » — format deja compris par
# `seed_locked_facts_from_variables` et par le gate (valeur multiple = fourchette).
_TRAJECTORY_LABELS: dict[str, str] = {
    "CA_PREVISIONNEL": (
        rf"(?:chiffre{_SP}+d['’]affaires?|CA)\b"
        # Le brief SYNAPSES reel ecrit « CA theorique a 100 % d'occupation :
        # 455 040 €/an » a cote de la vraie trajectoire. Ce montant etait avale
        # comme premiere valeur : toutes les annees se decalaient (An1 devenait
        # 455 040 au lieu de 250 272), et le gate accusait ensuite des chiffres
        # justes en citant une reference fausse. Un CA theorique, maximal ou a
        # 100 % d'occupation n'est PAS le previsionnel : on l'ecarte.
        rf"(?!{_SP}*(?:th[ée]orique|maximal|maximum|potentiel|a{_SP}+100))"
        rf"(?:{_SP}+(?:pr[ée]visionnel|projet[ée]|cible|attendu))?"
    ),
    "EBE_PREVISIONNEL": rf"(?:EBE|exc[ée]dent{_SP}+brut{_SP}+d['’]exploitation)\b",
    "RESULTAT_NET_PREVISIONNEL": rf"r[ée]sultat{_SP}+net\b",
}

# Tout libelle financier connu ferme le segment du libelle precedent.
#
# `_values_after_every_label` bornait chaque segment au saut de ligne et a la
# fin de phrase. Son propre commentaire annoncait le risque : « le segment
# deborderait sur le libelle suivant et lui volerait ses montants ». Deux
# bornes sur trois etaient posees, la troisieme manquait.
#
# Le formulaire Tally de juillet 2026 demande au client, noir sur blanc :
# « Resultat net previsionnel- EBE previsionnel- Taux d'occupation- Seuil de
# rentabilite ». Un separateur qui n'est ni un saut de ligne ni un point. Sur
# une reponse conforme a cette consigne, mesure :
#
#     RESULTAT_NET_PREVISIONNEL = 145 000 € / 310 000 € / 640 000 €
#     EBE_PREVISIONNEL          = 310 000 € / 640 000 €
#
# soit le resultat net, l'EBE et le seuil de rentabilite fusionnes en un seul
# fait CLIENT verrouille. Le gate aurait ensuite accuse d'incoherence un
# document citant les bons chiffres.
#
# Borner au tiret aurait ete reparer l'exemple : le client suivant ecrit avec
# un point-virgule, une puce ou un slash. Ce qui ferme un champ, ce n'est pas
# un caractere, c'est le debut du champ suivant.
_LIBELLES_FRONTIERE: tuple[str, ...] = (
    rf"(?:chiffre{_SP}+d['’]affaires?|CA)\b",
    rf"(?:EBE|exc[ée]dent{_SP}+brut{_SP}+d['’]exploitation)\b",
    rf"r[ée]sultat{_SP}+net\b",
    rf"seuil{_SP}+de{_SP}+rentabilit[ée]\b",
    rf"point{_SP}+mort\b",
    rf"taux{_SP}+d['’]occupation\b",
    r"verticales?\b",
    rf"lignes?{_SP}+d['’]activit[ée]s?\b",
    rf"investissement{_SP}+(?:total|initial|global)\b",
    rf"besoin{_SP}+(?:total|de{_SP}+financement|global)\b",
    rf"budget{_SP}+(?:total|global)\b",
    rf"apport{_SP}+(?:personnel|propre|initial)\b",
    rf"(?:emprunt|pr[êe]t){_SP}+(?:bancaire|professionnel)\b",
    r"subventions?\b",
)
_FRONTIERE_RE = re.compile("|".join(_LIBELLES_FRONTIERE), re.IGNORECASE)

_AMOUNT_RE = re.compile(_AMOUNT, re.IGNORECASE)
_PERCENT_RE = re.compile(rf"\d+(?:[.,]\d+)?{_SP}*%")

# Verticales : « Verticales : coworking, self-storage, hebergement de serveurs »
_VERTICALES_RE = re.compile(
    rf"(?:verticales?|lignes?{_SP}+d['’]activit[ée]s?"
    rf"|activit[ée]s{_SP}+du{_SP}+projet)"
    rf"(?:{_SP}+d['’]activit[ée]s?)?{_SP}*[:\-]{_SP}*(.{{3,300}}?){_SEGMENT_END}",
    re.IGNORECASE,
)


def _clean(raw: str) -> str:
    """Normalise les espaces d'une valeur sans en alterer le contenu."""
    return re.sub(rf"{_SP}+", " ", raw).strip(" :;,-. ")



def _extract_money(text: str) -> dict[str, str]:
    """Un libelle -> UNE valeur, ou rien.

    `search()` prenait la premiere occurrence et ignorait les suivantes : deux
    montants concurrents dans le brief (« investissement de 300 000 € en
    communication ... investissement de 1 250 000 € ») et le premier s'imposait
    EN SILENCE comme fait CLIENT intangible.

    Regle desormais : une ambiguite n'est pas tranchee par l'ordre du texte.
    Si un libelle designe plusieurs montants differents, on n'extrait RIEN — le
    check 0 du gate bloque alors le dossier et un humain saisit la valeur. Un
    blocage honnete vaut mieux qu'une reference choisie au hasard : c'est tout
    l'interet d'avoir rendu le check 0 bloquant.
    """
    found: dict[str, str] = {}
    for key, patterns in _MONEY_PATTERNS.items():
        for pattern in patterns:
            values = list(dict.fromkeys(_clean(m.group(1)) for m in pattern.finditer(text)))
            if not values:
                continue
            if len(values) == 1:
                found[key] = values[0]
            # len > 1 : ambigu -> aucune extraction, et on ne tente pas les
            # motifs suivants (plus generiques, donc encore plus ambigus).
            break
    return found


def _values_after_every_label(
    text: str, label: str, value_re: re.Pattern[str]
) -> list[str]:
    """Collecte les valeurs qui suivent CHAQUE occurrence d'un libelle.

    Correctif de l'audit F1. La version precedente prenait un seul segment
    borne au saut de ligne : sur un brief en puces (le format le plus naturel),

        - CA previsionnel An1 : 250 272 €
        - CA previsionnel An2 : 296 000 €

    seule l'annee 1 etait capturee. `ca_previsionnel` devenait une valeur
    UNIQUE, le gate exigeait alors l'egalite stricte, et toute mention
    legitime de l'An2 devenait un echec bloquant — avec un motif faux
    (« document dit 296 000, brief client dit 250 272 »). C'est le mecanisme
    qui envoie corriger un chiffre qui n'etait pas faux.

    Supprimer simplement le `\\n` du borneur ne suffit pas : le segment
    deborderait sur le libelle suivant et lui volerait ses montants. On itere
    donc sur chaque occurrence du libelle, en bornant chacune a sa ligne et a
    sa phrase. Les deux formats sont ainsi couverts :
    - puces      : N occurrences x 1 valeur ;
    - une ligne  : 1 occurrence x N valeurs.

    Troisieme borne, ajoutee en juillet 2026 : le LIBELLE SUIVANT, quel qu'il
    soit et quel que soit le separateur qui l'introduit (cf.
    `_LIBELLES_FRONTIERE`). Sans elle, la consigne du formulaire Tally
    (« Resultat net previsionnel- EBE previsionnel- Seuil de rentabilite »)
    faisait avaler au resultat net les montants de ses deux voisins.
    """
    values: list[str] = []
    for match in re.finditer(rf"\b{label}", text, re.IGNORECASE):
        rest = text[match.end() :]
        segment = rest.split("\n", 1)[0]
        segment = re.split(r"\.\s|\.$", segment, maxsplit=1)[0]
        suivant = _FRONTIERE_RE.search(segment)
        if suivant:
            segment = segment[: suivant.start()]
        values.extend(_clean(m.group(0)) for m in value_re.finditer(segment))
    return values


def _extract_trajectories(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for key, label in _TRAJECTORY_LABELS.items():
        amounts = _values_after_every_label(text, label, _AMOUNT_RE)
        if amounts:
            # dict.fromkeys : dedoublonne en preservant l'ordre d'apparition,
            # qui est l'ordre chronologique dans un previsionnel.
            found[key] = " / ".join(dict.fromkeys(amounts))
    return found


def _extract_occupation(text: str) -> dict[str, str]:
    # « taux d' » OBLIGATOIRE : le prefixe etait optionnel, donc le motif se
    # reduisait a « occupation » nu. Une phrase comme « l'occupation des sols
    # est limitee a 60 % de la parcelle » produisait TAUX_OCCUPATION = 60 %,
    # verrouille en fait CLIENT intangible, injecte dans le contexte du modele
    # et oppose en tolerance zero a toute mention du VRAI taux d'occupation.
    percents = _values_after_every_label(
        text, rf"taux{_SP}+d['’]?{_SP}*occupation", _PERCENT_RE
    )
    if not percents:
        return {}
    return {"TAUX_OCCUPATION": " / ".join(dict.fromkeys(percents))}


def _extract_verticales(text: str) -> dict[str, str]:
    match = _VERTICALES_RE.search(text)
    if not match:
        return {}
    # Separateurs : virgule, point-virgule, slash. PAS « et » (audit F3) :
    # « recherche et developpement » est UNE verticale, pas deux, et la
    # decouper injectait deux verticales fantomes dans les faits CLIENT — donc
    # dans le contexte du modele. La tolerance au « et » est traitee cote
    # correspondance (gate), la ou elle ne corrompt pas la donnee de reference.
    items = [
        _clean(part)
        for part in re.split(rf"{_SP}*[,;/]+{_SP}*", match.group(1))
        if _clean(part)
    ]
    if not items:
        return {}
    return {"VERTICALES": " / ".join(items)}


def extract_financials_from_text(text: str) -> dict[str, str]:
    """Extrait l'etat chiffre client d'un brief redige en texte libre.

    Ne retourne QUE les cles explicitement libellees par le client. Aucune
    valeur n'est estimee, deduite ou completee : une cle absente du texte
    reste absente du resultat (le gate de livraison bloquera alors le dossier
    plutot que de laisser le modele improviser).
    """
    if not text or not text.strip():
        return {}
    found: dict[str, str] = {}
    found.update(_extract_money(text))
    found.update(_extract_trajectories(text))
    found.update(_extract_occupation(text))
    found.update(_extract_verticales(text))
    return found


# Champs du brief susceptibles de contenir le previsionnel en texte libre.
_FREE_TEXT_SOURCES: tuple[str, ...] = (
    "PROJET",
    "ELEMENTS_A_RETENIR",
    "DEMANDES_SPECIFIQUES",
    "MODELE_ECONOMIQUE",
    "MODELE_REVENUS",
    "CONTEXTE_ETUDE_PRECEDENTE",
    # Encadres que la cliente a ajoutes au formulaire BP en juillet 2026 et
    # qui portent le previsionnel : « Resultat net previsionnel- EBE- Taux
    # d'occupation- Seuil de rentabilite- Verticales » d'un cote, apports,
    # aides et postes de depenses de l'autre. Sans ces deux entrees, les
    # champs que la cliente a crees EXPRES pour l'etat chiffre arrivaient en
    # base et n'etaient jamais lus.
    "ETAT_CHIFFRE_LIBRE",
    "BESOINS_FINANCIERS",
)


# Cles dont la valeur est verrouillee telle quelle comme fait CLIENT par
# `coherence.seed_locked_facts_from_variables`, tolerance zero au gate.
_CLES_FINANCIERES: tuple[str, ...] = (
    "INVESTISSEMENT_TOTAL", "APPORT", "EMPRUNT", "SUBVENTIONS",
    "CA_PREVISIONNEL", "EBE_PREVISIONNEL", "RESULTAT_NET_PREVISIONNEL",
    "TAUX_OCCUPATION", "SEUIL_RENTABILITE",
)


def raffiner_champs_financiers(variables: dict[str, object]) -> dict[str, str]:
    """Relit les champs financiers structures au lieu de les gober bruts.

    Le formulaire Tally de juillet 2026 a enfin un champ dedie « 12.CA
    previsionnel (ou CA an1 a an5) ». Le client y ecrit une phrase, pas un
    nombre — la consigne le lui demande explicitement (« ecrire les valeurs
    dans l'ordre chronologique, separees par des virgules », « pourquoi ce
    calcul et estimation ? »).

    Or un champ structure gagne toujours sur l'extraction, et sa valeur brute
    est verrouillee telle quelle en fait CLIENT. Toutes les regles d'exclusion
    de ce module etaient donc court-circuitees par le champ meme qui devait les
    rendre inutiles. Mesure sur une reponse realiste :

        CA_PREVISIONNEL = « CA previsionnel An1 : 250 272 €, An2 : 296 000 €,
        An3 : 318 400 €. CA theorique a 100 % d'occupation : 455 040 €/an »
        -> le gate y lit [250272, 296000, 318400, 100, 455040]

    Le CA theorique — que `_TRAJECTORY_LABELS` ecarte expres depuis le brief
    SYNAPSES — redevenait un CA client legitime. Et « 100 », venu de « 100 % »,
    aussi : un document citant « 100 € » de CA aurait ete declare conforme.

    L'extracteur connait ces pieges ; la valeur brute non. On le fait donc
    relire le champ. S'il n'y trouve rien (le client a tape « 1 250 000 € » nu,
    sans libelle), la valeur brute est deja propre et on la garde.
    """
    corrigees: dict[str, str] = {}
    for cle in _CLES_FINANCIERES:
        brut = str(variables.get(cle) or "").strip()
        if not brut:
            continue
        relu = extract_financials_from_text(brut).get(cle)
        if relu and relu != brut:
            variables[cle] = relu
            corrigees[cle] = relu
    return corrigees


def enrich_variables_from_free_text(variables: dict[str, object]) -> dict[str, str]:
    """Complete les variables avec l'etat chiffre trouve dans le texte du brief.

    Mutation en place. Les champs Tally structures gagnent TOUJOURS : on ne
    remplit qu'une cle absente ou vide. Retourne les cles effectivement
    ajoutees (utile pour tracer ce qui vient du texte plutot que du
    formulaire).
    """
    corpus = "\n".join(str(variables.get(key) or "") for key in _FREE_TEXT_SOURCES).strip()
    if not corpus:
        return {}

    extracted = extract_financials_from_text(corpus)
    added: dict[str, str] = {}
    for key, value in extracted.items():
        if not str(variables.get(key) or "").strip():
            variables[key] = value
            added[key] = value
    return added

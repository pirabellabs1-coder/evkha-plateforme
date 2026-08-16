"""Gate de livraison — Brique 3 du brief client (juillet 2026).

Couche de relecture automatique exécutée APRÈS la passe QA et AVANT toute
livraison. Contrairement à la QA (qui corrige ce qu'elle peut et trace le
reste), le gate est BLOQUANT : si un seul check critique échoue, le document
ne part pas chez le client. La livraison ne peut alors être déclenchée que
manuellement depuis le dashboard admin (décision humaine assumée).

Les quatre checks (brief client, verbatim) :
1. Contamination pipeline — aucun token interne (FAITS_VERROUILLES,
   VARIABLES_PROJET, marqueurs [[...]], placeholders) dans le texte final.
2. Cohérence chiffrée — les nombres clés extraits du document sont comparés
   à l'état chiffré verrouillé du brief client, tolérance zéro.
3. Complétude verticales — chaque verticale d'activité listée dans le brief
   doit apparaître dans le livrable.
4. Troncature — aucun chapitre ne se termine en pleine phrase ou dans une
   structure HTML ouverte.

Le check de contamination opère à DEUX niveaux (audit juillet 2026, cause 4) :
- sur le contenu BRUT du chapitre, pour détecter que le modèle a confondu
  contexte interne et rédaction — même si le Rendering Engine neutralise
  ensuite le token, le défaut doit être vu et régénéré ;
- sur le HTML RENDU, filet de sécurité sur ce que le client verra vraiment.

Auparavant seul le rendu était scanné, avec la même liste de tokens que le
nettoyeur qui venait de les effacer : le check ne pouvait mathématiquement
jamais échouer.

RÈGLE FONDAMENTALE (audit juillet 2026, cause 2) : un check qui n'a rien à
comparer est un ÉCHEC, jamais un succès. Un gate sans état chiffré client
donnait `passed: True` sur un document truffé d'incohérences.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from catalog.models import DeliverableType
from core.numbers import (
    CURRENCY_ALTERNATION,
    MAGNITUDE_WORDS,
    MONEY_CAPTURED,
    NUMBER_BODY,
    SPACE_CLASS,
    amounts_in,
    parse_amount,
)

from .internal_labels import callout_alternation, forbidden_words_alternation
from .models import ChapterStatus, FactProvenance, GenerationJob
from .rendering import RenderedSection, render_client_document

# ── Check 1 : contamination pipeline ─────────────────────────────────────────
# Tokens interdits dans le texte final (brief client : "grep des tokens
# interdits... Si un seul apparaît → rejet").
# Les listes sont derivees de `internal_labels.py` (source UNIQUE). Elles
# etaient auparavant recopiees ici et dans rendering.py : trois copies a
# synchroniser a la main, donc un oubli garanti — c'est exactement ce qui est
# arrive au label CHIFFRES_A_CITER, qui a rouvert le defaut de fuite.
_FORBIDDEN_TOKEN_RE = re.compile(
    r"\b(?:" + forbidden_words_alternation() + r")\b"
    r"|\[\[/?(?:" + callout_alternation() + r")\]\]"
    r"|\{\{\s*[a-zA-Z_][a-zA-Z0-9_]*\s*\}\}"
)

# Variante appliquee au contenu BRUT : les marqueurs [[UNDERSTAND]] y sont
# legitimes (le convertisseur les transforme en encadres mentor), donc on n'y
# cherche que les labels internes et les placeholders non resolus.
_INTERNAL_LABEL_ONLY_RE = re.compile(
    r"\b(?:" + forbidden_words_alternation() + r")\b"
    r"|\{\{\s*[a-zA-Z_][a-zA-Z0-9_]*\s*\}\}"
)

# ── Check 2 : cohérence chiffrée vs état client ──────────────────────────────
# Chaque clé de fait client est associée aux motifs qui repèrent sa valeur
# dans le texte généré. Tolérance zéro : toute valeur extraite qui ne
# correspond à aucun nombre du fait client est bloquante.
# `_MONEY` capture le nombre (groupe 1) ET son unite (groupe 2). Sans l'unite,
# le gate lisait « 1,25 » la ou le brief dit « 1,25 M€ » et le comparait a
# « 1 250 000 » ecrit par le modele : meme montant, blocage, motif mensonger.
# La devise vient de `core.numbers` : elle couvre la zone franc (XOF/XAF/FCFA),
# que l'extraction acceptait deja mais qu'aucun motif du gate ne reconnaissait
# — l'etat chiffre etait alors verrouille puis jamais compare.
_MONEY = MONEY_CAPTURED

_CLIENT_FACT_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "investissement_total": (
        re.compile(
            r"investissement\s+(?:total|initial|global|de\s+d[ée]part)\s*"
            r"(?:de\s+|estim[ée]\s+[àa]\s+|s'[ée]l[èe]ve\s+[àa]\s+|:\s*)?"
            + _MONEY,
            re.IGNORECASE,
        ),
    ),
    "emprunt": (
        re.compile(
            r"(?:emprunt|pr[êe]t\s+bancaire)\s*"
            r"(?:de\s+|d'un\s+montant\s+de\s+|:\s*)?"
            + _MONEY,
            re.IGNORECASE,
        ),
    ),
    "apport": (
        re.compile(
            r"apport\s+(?:personnel|propre|en\s+capital)?\s*"
            r"(?:de\s+|:\s*)?"
            + _MONEY,
            re.IGNORECASE,
        ),
    ),
    "taux_occupation": (
        re.compile(
            r"taux\s+d['e]?occupation\s*"
            r"(?:de\s+|cible\s+de\s+|moyen\s+de\s+|:\s*|atteint\s+|est\s+de\s+)?"
            r"(\d+(?:[.,]\d+)?)\s*(%)",
            re.IGNORECASE,
        ),
    ),
    "seuil_rentabilite": (
        re.compile(
            r"seuil\s+de\s+rentabilit[ée]\s*"
            r"(?:se\s+situe\s+[àa]\s+|est\s+de\s+|:\s*|de\s+|atteint\s+[àa]\s+)?"
            + _MONEY,
            re.IGNORECASE,
        ),
    ),
    "resultat_net_previsionnel": (
        re.compile(
            r"r[ée]sultat\s+net\s*"
            r"(?:pr[ée]visionnel|projet[ée]|attendu|d[e']?ann[ée]e\s*\d)?\s*"
            r"(?:de\s+|:\s*|est\s+de\s+|atteint\s+)?"
            + _MONEY,
            re.IGNORECASE,
        ),
    ),
    "ebe_previsionnel": (
        re.compile(
            r"(?:EBE|exc[ée]dent\s+brut\s+d['e]?exploitation)\s*"
            r"(?:pr[ée]visionnel|projet[ée]|d[e']?ann[ée]e\s*\d)?\s*"
            r"(?:de\s+|:\s*|est\s+de\s+|atteint\s+)?"
            + _MONEY,
            re.IGNORECASE,
        ),
    ),
    # Audit juillet 2026, cause 3 : `ca_previsionnel` et `subventions` etaient
    # verrouilles comme faits CLIENT mais n'avaient AUCUN motif ici — le gate
    # ne les verifiait donc jamais. Or le CA est precisement le chiffre que la
    # cliente cite comme divergent (296 000 € au resume, 318 400 € au chap. 15).
    "ca_previsionnel": (
        re.compile(
            r"(?:chiffre\s+d['e’]?affaires?|CA)\b"
            # Qualificatifs CUMULABLES : « CA prévisionnel d'année 2 » en empile
            # deux. Un groupe optionnel unique ne matchait que le premier et
            # laissait le montant hors de portee du gate.
            r"(?:\s*(?:pr[ée]visionnel|projet[ée]|cible|attendu"
            r"|d[e']?\s*ann[ée]e\s*\d|an\s*\d))*\s*"
            r"(?:de\s+|:\s*|est\s+de\s+|atteint\s+|s['’][ée]tablit\s+[àa]\s+)?"
            + _MONEY,
            re.IGNORECASE,
        ),
    ),
    "subventions": (
        re.compile(
            r"(?:subventions?|aides?\s+(?:publiques?|et\s+subventions?))\s*"
            r"(?:de\s+|:\s*|s['’][ée]l[èe]vent?\s+[àa]\s+|atteignent\s+)?"
            + _MONEY,
            re.IGNORECASE,
        ),
    ),
}


# ── Check 0 : présence de l'état chiffré client ──────────────────────────────
# Audit juillet 2026, cause 2 — LE trou d'entrée. Les checks 2 et 3 se
# contentaient de `continue` / `return []` quand le fait client etait absent :
# un dossier sans etat chiffre passait donc le gate sans la moindre anomalie.
# Le gate promettait une garantie qu'il n'assurait pas.
#
# Desormais : pour un livrable dont la coherence repose sur un previsionnel,
# l'absence de la donnee de reference est un ECHEC BLOQUANT. Le dossier part en
# relecture admin, qui saisit l'etat chiffre — au lieu de laisser le modele
# improviser des chiffres que plus rien ne vient contredire.
#
# Volontairement limite au business plan : une etude de marche ou de
# concurrence n'a pas de previsionnel client a respecter, et l'exiger
# bloquerait des dossiers parfaitement legitimes.
#
# ON N'EXIGE QUE LES ENTREES, JAMAIS LES SORTIES (precision cliente, juillet
# 2026). Deux cas d'usage reels pour un BP :
#   1. la cliente a construit le previsionnel (Excel) et en resume les chiffres
#      dans le brief : le resultat net est alors une DONNEE ;
#   2. le porteur commande un BP SANS previsionnel : il fournit des estimations
#      (investissement, CA vise) et le resultat net est ce que le business plan
#      doit CALCULER.
# Exiger `resultat_net_previsionnel` bloquait donc systematiquement le cas 2 —
# on aurait reclame au client la reponse qu'il vient acheter.
#
# Ce que le BP ne peut pas deviner sans le client : combien il investit, et
# quel chiffre d'affaires il vise. Le reste se derive. Un resultat net fourni
# reste verifie en tolerance zero (il est dans `_CLIENT_FACT_PATTERNS`) ; s'il
# est calcule, c'est le Coherence Engine qui le verrouille a sa premiere
# mention et empeche les trajectoires divergentes entre chapitres.
_REQUIRED_CLIENT_FACTS: dict[str, tuple[str, ...]] = {
    DeliverableType.BUSINESS_PLAN: (
        "investissement_total",
        "ca_previsionnel",
    ),
}

_FACT_LABELS: dict[str, str] = {
    "investissement_total": "investissement total",
    "ca_previsionnel": "chiffre d'affaires prévisionnel",
    "resultat_net_previsionnel": "résultat net prévisionnel",
    "emprunt": "emprunt",
    "apport": "apport",
    "subventions": "subventions",
    "ebe_previsionnel": "EBE prévisionnel",
    "seuil_rentabilite": "seuil de rentabilité",
    "taux_occupation": "taux d'occupation",
    "verticales": "verticales d'activité",
}

# ── Check 0 bis : le brief a-t-il ete LU ? ──────────────────────────────────
# `_REQUIRED_CLIENT_FACTS` ne couvre que le business plan. Or le defaut decrit
# par la cliente — « le previsionnel que j'avais explicitement injecte dans le
# brief a ete ignore », les trois verticales effacees — portait sur la
# STRATEGIE SYNAPSES, pas sur le BP. Pour ce type de livrable, aucun etat
# chiffre n'est exige : si l'extraction echouait, plus rien n'etait verrouille
# et TOUS les autres checks se sautaient en silence. Le trou d'entree restait
# donc ouvert sur l'un des deux documents dont elle se plaint.
#
# Exiger un previsionnel pour tous les types bloquerait des etudes de marche
# qui n'en ont legitimement pas. La regle qui vaut pour TOUT type est autre, et
# c'est exactement sa phrase :
#
#   si le client a ECRIT une donnee et que le pipeline n'a pas su la LIRE,
#   on ne peut rien verifier — donc on ne fait pas semblant, on bloque.
#
# On ne cherche donc pas « un montant quelque part » (le brief peut citer le
# prix d'un concurrent), mais un LIBELLE de previsionnel suivi d'un montant a
# courte distance : la signature d'une ligne de previsionnel que l'extraction
# aurait du capturer.
_BRIEF_FINANCIAL_HINTS: dict[str, str] = {
    "investissement_total": r"investissement|budget\s+total|co[ûu]t\s+total",
    "emprunt": r"emprunt|pr[êe]t\s+bancaire",
    "apport": r"apport",
    "subventions": r"subventions?|aides?\s+publiques?",
    "ca_previsionnel": r"chiffre\s+d['e’]?affaires?|\bCA\b",
    "ebe_previsionnel": r"\bEBE\b|exc[ée]dent\s+brut",
    "resultat_net_previsionnel": r"r[ée]sultat\s+net",
    "seuil_rentabilite": r"seuil\s+de\s+rentabilit[ée]|point\s+mort",
}
_HINT_GAP = r"[^.\n]{0,60}?"

_BRIEF_OCCUPATION_HINT = re.compile(
    rf"taux\s+d['’]?\s*occupation{_HINT_GAP}\d+(?:[.,]\d+)?{SPACE_CLASS}*%",
    re.IGNORECASE,
)
_BRIEF_VERTICALES_HINT = re.compile(
    r"verticales?|lignes?\s+d['’]activit[ée]s?|activit[ée]s\s+du\s+projet",
    re.IGNORECASE,
)

# Clés dont la valeur client est une TRAJECTOIRE pluriannuelle (An1..An5), par
# opposition aux scalaires (investissement, emprunt, apport...). Le document
# peut légitimement citer plusieurs valeurs différentes pour ces clés : une
# par année. Le gate ne peut donc les juger qu'en fourchette, et seulement si
# le brief donne au moins deux points (audit F1).
_TRAJECTORY_FACT_KEYS: frozenset[str] = frozenset({
    "ca_previsionnel",
    "ebe_previsionnel",
    "resultat_net_previsionnel",
    "taux_occupation",
})

# Cles de faits client exprimees en MONNAIE. Servent d'echelle au check
# d'ordre de grandeur : la reference est le plus grand montant fourni par le
# client, quel que soit le type de livrable. `taux_occupation` en est exclu —
# c'est un pourcentage, pas un montant, et il ecraserait l'echelle.
_MONETARY_FACT_KEYS: tuple[str, ...] = (
    "investissement_total",
    "ca_previsionnel",
    "ebe_previsionnel",
    "resultat_net_previsionnel",
    "emprunt",
    "apport",
    "subventions",
    "seuil_rentabilite",
    "capital_initial",
)

# ── Check 5 : ordre de grandeur ──────────────────────────────────────────────
# Audit juillet 2026, cause 5 : l'erreur d'unite « millions/milliers » (un EBE
# reseau a 420 millions d'euros pour 8-10 sites de coworking) n'etait detectee
# par aucun controle. On ne verifie QUE les montants rattaches a un libelle
# financier du projet : une taille de marche (« le marche mondial pese 12
# milliards ») est legitimement grande et ne doit pas etre bloquee.
_PROJECT_MONEY_LABEL = (
    r"(?:EBE|exc[ée]dent\s+brut|chiffre\s+d['e’]?affaires?|\bCA\b"
    r"|r[ée]sultat\s+net|investissement)"
)
# UN SEUL motif : le nombre, la devise et les mots de magnitude viennent de
# `core.numbers`. Il y avait ici deux motifs avec chacun leur liste — le
# second n'acceptait que l'euro, donc le controle d'unite etait inoperant en
# zone franc alors que le reste du gate y lisait les montants. Une troisieme
# liste de devises a maintenir, c'est le defaut qu'on corrige.
# Couvre desormais « 420 millions », « 420 M€ », « 420 000 000 € » et
# « 420 000 000 FCFA » — la meme erreur d'unite, quelle que soit l'ecriture.
_PROJECT_MONEY_RE = re.compile(
    _PROJECT_MONEY_LABEL
    + r"[^.\n]{0,40}?"
    + rf"({NUMBER_BODY}){SPACE_CLASS}*({CURRENCY_ALTERNATION}|{MAGNITUDE_WORDS})",
    re.IGNORECASE,
)
# Facteur volontairement genereux : un plan de duplication multi-sites peut
# legitimement projeter plusieurs fois le CA initial. Au-dela de x100, ce
# n'est plus une projection, c'est une erreur d'unite.
_MAGNITUDE_FACTOR = 100

# ── Check 4 : troncature ─────────────────────────────────────────────────────
# Violations QA considérées comme des troncatures bloquantes si elles
# subsistent après la passe QA (le document partirait incomplet).
_BLOCKING_TRUNCATION = frozenset(
    {"empty_content", "sentence_cut", "cut_html_table", "truncated_in_tag", "abrupt_ending"}
)


@dataclass(frozen=True)
class GateFailure:
    check: str  # "contamination" | "coherence_chiffree" | "verticales" | "troncature"
    detail: str
    chapter_number: int | None = None


@dataclass(frozen=True)
class GateReport:
    passed: bool
    failures: tuple[GateFailure, ...] = field(default_factory=tuple)

    def as_details(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "failures": [
                {
                    "check": f.check,
                    "chapitre": f.chapter_number,
                    "detail": f.detail,
                }
                for f in self.failures
            ],
        }


def _strip_accents_lower(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn"
    )


def _amount_from_match(match: re.Match[str]) -> float | None:
    """Montant d'une occurrence, normalise en unites de base.

    Le groupe 2 porte l'unite (€, M€, k€, FCFA, %...) quand le motif la
    capture. Sans elle, « 1,25 M€ » etait lu 1.25 et compare a 1 250 000.
    """
    unit = match.group(2) if match.re.groups >= 2 else None
    return parse_amount(match.group(1), unit)


def _verticale_needle(verticale: str) -> str:
    """Réduit une verticale du brief à sa forme cherchable dans la prose.

    Le client écrit « self-storage (boxes + garages) » ; le rédacteur écrira
    « self-storage ». Chercher la chaîne littérale complète produisait un
    faux positif bloquant systématique. On ne garde donc que la tête du
    libellé, avant toute parenthèse ou précision.
    """
    head = re.split(r"[(\[]", verticale, maxsplit=1)[0]
    return _strip_accents_lower(head).strip(" -–—:")


# Mots-outils : ils ne portent pas le sens d'une verticale et ne doivent pas
# etre exiges dans le livrable.
_MOTS_OUTILS: frozenset[str] = frozenset({
    "de", "du", "des", "d", "la", "le", "les", "l", "un", "une",
    "et", "ou", "en", "a", "au", "aux", "pour", "sur", "avec",
})


def _mot_present(mot: str, full_text: str) -> bool:
    """Un mot porteur du needle est-il traite dans le document ?

    Deux voies :
      a) Match strict par frontiere de mot (`\\b...\\b`) : le mot apparait
         tel quel (ou dans une variante en pluriel/majuscule geree par le
         `\\w*` implicite). Le simple `in` du code precedent capturait « pro »
         dans « projet » — faux positif discret qui empechait de detecter
         les vraies absences.
      b) Match par RADICAL (regle 4 : viser la classe) : si le mot fait au
         moins 5 lettres, on tolere qu'un mot du texte commence par les 60 %
         premieres lettres du needle, avec un plancher de 4 lettres.
         Constate SYNAPSES v3 : brief « bureaux prives » vs doc « bureaux
         privatifs » — meme radical `priv`, meme sens, faux positif que
         cette voie eteint sans laisser passer les vraies verticales
         effacees (« self », « evenementiel » restent bloques).
    """
    if re.search(rf"\b{re.escape(mot)}\b", full_text, re.IGNORECASE):
        return True
    if len(mot) < 5:
        # Trop court pour tolerer une troncature sans creer des faux
        # positifs (« pro » matcherait « projet », « proche »...).
        return False
    n_radical = max(4, -(-len(mot) * 3 // 5))  # ceil(0.6 * len)
    if n_radical >= len(mot):
        return False
    radical = mot[:n_radical]
    return bool(re.search(rf"\b{re.escape(radical)}\w*", full_text, re.IGNORECASE))


def _verticale_present(needle: str, full_text: str) -> bool:
    """La verticale est-elle traitée dans le livrable ?

    On ne cherche PAS le libellé exact du brief. Le client écrit
    « domiciliation d'entreprises » ; le rédacteur écrit « domiciliation
    commerciale », « domiciliation à 30 euros », « la domiciliation ». Exiger
    la phrase littérale bloquait un document qui traite le sujet 48 fois —
    faux positif constaté sur le premier vrai dossier SYNAPSES, et c'est
    exactement le travers qu'on combat : accuser un livrable correct.

    Règle : la verticale est traitée si TOUS ses mots porteurs apparaissent
    quelque part dans le document, pas forcément côte à côte ni dans l'ordre.
    Chaque mot du needle doit etre PRESENT au sens de `_mot_present` :
    match strict OU par radical commun (>= 4 lettres). Le radical rattrape
    « bureaux prives » vs « bureaux privatifs » constate SYNAPSES v3, sans
    laisser passer une verticale reellement effacee (« self-storage » n'a
    pas de synonyme radical dans un document sans stockage).
    """
    mots = [m for m in re.split(r"[^\w-]+", needle) if m and m not in _MOTS_OUTILS]
    if not mots:
        return True
    return all(_mot_present(mot, full_text) for mot in mots)


#: Un montant qui porte SON unité. `amounts_in` la rend facultative — c'est
#: juste pour lire « 55 % An1 -> 85 % An5 », et faux pour décider si une
#: réponse client contient un montant.
_MONTANT_AVEC_DEVISE = re.compile(MONEY_CAPTURED, re.IGNORECASE)


def _exige_une_devise(patterns: tuple[re.Pattern[str], ...]) -> bool:
    """Le fait se cherche-t-il dans le document avec une unité monétaire ?

    Déduit des motifs eux-mêmes, et non d'une seconde liste de clés à tenir à
    jour : ajouter un fait monétaire à `_CLIENT_FACT_PATTERNS` suffit, le
    contrôle suit (règle 5).
    """
    return any(_MONEY in motif.pattern for motif in patterns)


def _extrait(valeur: str, largeur: int = 90) -> str:
    """Le début d'une réponse client, entre guillemets, pour un motif lisible.

    Le message reproduisait la réponse ENTIÈRE — sur le business plan
    `2a8872d0`, un paragraphe de mille signes dans un motif d'échec. Un motif
    qu'on ne peut pas lire ne se corrige pas (règle 2).
    """
    aplati = " ".join(valeur.split())
    if len(aplati) <= largeur:
        return f"« {aplati} »"
    return f"« {aplati[:largeur].rstrip()}… »"


def _client_numbers(value: str) -> list[float]:
    """Montants d'une valeur de fait client, normalises en unites de base.

    Une valeur client peut etre multiple ("55 % An1 -> 85 % An5") : les
    valeurs du document sont alors acceptees si elles tombent DANS la
    fourchette [min, max] (annees intermediaires).

    Delegue a `core.numbers` : c'est la MEME lecture que celle de
    l'extraction du brief. Les deux divergeaient — l'espace fine insecable
    de Word etait capturee ici puis rejetee par float(), ce qui vidait
    `expected` et sautait le check EN SILENCE.
    """
    return amounts_in(value)


def _check_completude_chapitres(
    job: GenerationJob, sections: tuple[RenderedSection, ...]
) -> list[GateFailure]:
    """Tous les chapitres prévus par le blueprint sont-ils dans le livrable ?

    `render_client_document` ne retient que les chapitres DONE : un chapitre
    manquant disparaît donc du document SANS que les autres checks s'en
    aperçoivent — ils validaient alors un livrable amputé. C'est le scénario
    du brief : « le chapitre 18 est tronqué page 88, puis le doc bascule
    brutalement sur les Références ».

    Le runner échoue normalement le job entier si un chapitre échoue, mais
    rien ne le garantissait au niveau du gate (relances manuelles,
    régénérations ciblées). Défense en profondeur.
    """
    from .blueprints import chapters_for_deliverable  # noqa: PLC0415

    expected = {bp.number for bp in chapters_for_deliverable(job.deliverable_type)}
    if not expected:
        return []
    present = {section.number for section in sections}
    missing = sorted(expected - present)
    if not missing:
        return []
    return [
        GateFailure(
            check="completude_chapitres",
            detail=(
                f"Chapitre(s) absent(s) du livrable : {missing}. "
                "Le document partirait amputé sans que les autres contrôles "
                "le voient (ils ne portent que sur les chapitres présents)."
            ),
        )
    ]


def _brief_free_text(job: GenerationJob) -> str:
    """Le texte libre du brief, tel que le client l'a ecrit."""
    from intake.financials import _FREE_TEXT_SOURCES  # noqa: PLC0415
    from intake.models import IntakeSubmission  # noqa: PLC0415

    submission = IntakeSubmission.objects.filter(order=job.order).first()
    if submission is None:
        return ""
    variables = submission.normalized_variables or {}
    return "\n".join(str(variables.get(key) or "") for key in _FREE_TEXT_SOURCES)


def _client_fact_keys(job: GenerationJob) -> set[str]:
    return {
        fact.key
        for fact in job.coherence_facts.filter(
            is_locked=True, provenance=FactProvenance.CLIENT
        )
        if fact.value.strip()
    }


def _check_brief_lu(job: GenerationJob) -> list[GateFailure]:
    """Le client a-t-il ecrit des donnees que le pipeline n'a pas su lire ?

    Vaut pour TOUS les types de livrable — c'est ce qui manquait. Le trou
    d'entree n'etait ferme que pour le business plan, alors que le prevision-
    nel ignore et les verticales effacees concernaient la STRATEGIE SYNAPSES.
    Pour ce type, rien n'etait exige : extraction ratee -> zero fait -> tous
    les checks se sautaient en silence, et le document partait avec des
    chiffres inventes.

    Ne bloque PAS un dossier sans previsionnel (une etude de marche n'en a pas
    forcement) : uniquement un dossier ou le client a ecrit la donnee et ou on
    ne l'a pas comprise. Echouer bruyamment sur ce qu'on n'a pas su lire est la
    seule reponse honnete — l'alternative, c'est le modele qui improvise et
    plus rien pour le contredire.
    """
    brief = _brief_free_text(job)
    if not brief.strip():
        return []

    locked = _client_fact_keys(job)
    failures: list[GateFailure] = []

    # Les faits financiers (CA, investissement, emprunt...) sont des cibles de
    # validation seulement pour les types de livrable qui les exigent. Pour une
    # EM, le CA client est un contexte sectoriel, pas un chiffre a verifier dans
    # le document : le gate ne doit pas bloquer si le brief en mentionne un.
    required_financial_keys: frozenset[str] = frozenset(
        _REQUIRED_CLIENT_FACTS.get(str(job.deliverable_type), ())
    )

    for key, hint in _BRIEF_FINANCIAL_HINTS.items():
        if required_financial_keys and key not in required_financial_keys:
            continue
        if key in locked:
            continue
        pattern = re.compile(rf"(?:{hint}){_HINT_GAP}{MONEY_CAPTURED}", re.IGNORECASE)
        match = pattern.search(brief)
        if match:
            failures.append(GateFailure(
                check="brief_non_lu",
                detail=(
                    f"Le brief mentionne « {_FACT_LABELS.get(key, key)} » avec un "
                    f"montant ({match.group(0).strip()!r}), mais la lecture automatique "
                    "ne l'a pas retenu : cette valeur n'est donc verifiee nulle "
                    "part. Reformuler la ligne du brief ou saisir la valeur en "
                    "clair avant relance."
                ),
            ))

    if "taux_occupation" not in locked and _BRIEF_OCCUPATION_HINT.search(brief):
        failures.append(GateFailure(
            check="brief_non_lu",
            detail=(
                "Le brief donne un taux d'occupation que la lecture automatique "
                "n'a pas retenu : il n'est verifie nulle part."
            ),
        ))

    if "verticales" not in locked and _BRIEF_VERTICALES_HINT.search(brief):
        failures.append(GateFailure(
            check="brief_non_lu",
            detail=(
                "Le brief liste des verticales d'activite que la lecture automatique "
                "n'a pas retenues : rien ne garantit qu'elles figurent dans le "
                "livrable. C'est le defaut SYNAPSES — trois verticales effacees "
                "au profit d'un modele generique."
            ),
        ))

    return failures


def _check_etat_chiffre_present(job: GenerationJob) -> list[GateFailure]:
    """Le référentiel de comparaison existe-t-il ? Sinon, ÉCHEC (jamais succès).

    C'est le correctif du trou d'entrée (audit juillet 2026, cause 2). Sans
    cette barrière, les checks de cohérence chiffrée et de complétude des
    verticales n'ont rien à comparer et se sautent en silence : le gate rend
    `passed: True` sur un document truffé d'incohérences.
    """
    required = _REQUIRED_CLIENT_FACTS.get(str(job.deliverable_type), ())
    if not required:
        return []

    present = _client_fact_keys(job)
    missing = [key for key in required if key not in present]
    if not missing:
        return []

    labels = ", ".join(_FACT_LABELS.get(key, key) for key in missing)
    return [
        GateFailure(
            check="etat_chiffre_client",
            detail=(
                f"État chiffré client incomplet : {labels} absent(s) du brief. "
                "Sans cette donnée de référence, la cohérence chiffrée du "
                "document ne peut pas être vérifiée : le dossier part en "
                "relecture admin pour saisie du prévisionnel."
            ),
        )
    ]


def _check_contamination(
    job: GenerationJob, sections: tuple[RenderedSection, ...]
) -> list[GateFailure]:
    """Détecte les labels internes à DEUX niveaux : contenu brut et HTML rendu.

    Le rendu seul ne suffisait pas (audit juillet 2026, cause 4) : le
    Rendering Engine efface les labels internes avec la MÊME liste que celle
    du gate, donc le check ne pouvait jamais échouer. Le client ne voyait
    rien — mais le signal que le modèle confond contexte interne et rédaction
    était perdu, sans incident ni régénération.

    Le contenu brut contient légitimement les paires [[UNDERSTAND]] que le
    convertisseur transforme en encadrés mentor : on n'y cherche donc que les
    labels internes, pas les marqueurs d'encadré.
    """
    from .rendering import _md_to_html, strip_callout_markers  # noqa: PLC0415

    failures: list[GateFailure] = []

    # Niveau 1 : contenu BRUT, avant tout nettoyage.
    for chapter in job.chapters.filter(status=ChapterStatus.DONE):
        match = _INTERNAL_LABEL_ONLY_RE.search(chapter.content or "")
        if match:
            failures.append(GateFailure(
                check="contamination",
                chapter_number=chapter.chapter_number,
                detail=(
                    f"Label interne dans la rédaction : {match.group(0)!r}. "
                    "Le modèle a confondu le contexte de génération avec le "
                    "contenu ; le chapitre doit être régénéré."
                ),
            ))

    # Niveau 2 : HTML rendu, filet de sécurité sur ce que le client verra.
    for section in sections:
        rendered = strip_callout_markers(_md_to_html(section.body))
        match = _FORBIDDEN_TOKEN_RE.search(rendered)
        if match:
            failures.append(GateFailure(
                check="contamination",
                chapter_number=section.number,
                detail=f"Token interne dans le texte final : {match.group(0)!r}",
            ))
    return failures


def _check_ordres_de_grandeur(
    job: GenerationJob, sections: tuple[RenderedSection, ...]
) -> list[GateFailure]:
    """Détecte les erreurs d'unité (« millions » au lieu de « milliers »).

    Référence = le plus grand montant de l'état chiffré client. Tout montant
    du document rattaché à un libellé financier du projet et dépassant ce
    plafond d'un facteur _MAGNITUDE_FACTOR est une erreur d'unité, pas une
    projection (audit juillet 2026, cause 5 : EBE réseau à 420 M€ pour 8-10
    sites de coworking).
    """
    client_facts = {
        fact.key: fact.value
        for fact in job.coherence_facts.filter(
            is_locked=True, provenance=FactProvenance.CLIENT
        )
    }
    # Reference = le plus grand montant que le CLIENT a lui-meme fourni, toutes
    # cles monetaires confondues. La version precedente ne regardait que
    # `investissement_total` et `ca_previsionnel`, deux cles exigees du seul
    # business plan : le check etait donc muet sur les trois autres livrables,
    # alors que l'erreur « millions/milliers » est une faute de redaction, pas
    # une specificite du BP. Une etude de marche qui fournit un CA client est
    # desormais couverte.
    # L'échelle se construit sur des MONTANTS, pas sur des nombres.
    #
    # Reprise `5c5e91b9` (12/08/2026) : la cliente avait répondu « pour s1 2027
    # 20 abonnés » à la question du chiffre d'affaires prévisionnel. Le lecteur
    # y voyait l'année, 2027, et le contrôle en faisait une référence de
    # 2 027 € — puis reprochait au document ses « 260 000 €, plus de 100× la
    # référence client », en suggérant une erreur d'unité qui n'existait pas.
    #
    # C'est le défaut réparé le matin même dans `_check_numeric_coherence`, et
    # laissé intact ici : deux contrôles, la même lecture, une seule réparée.
    # Règle 9 du dépôt — ce qu'un contrôle ne regarde pas est exactement là où
    # sa réparation ne cherche pas non plus.
    #
    # Une unité monétaire est donc EXIGÉE côté brief, comme elle l'est déjà
    # côté document (`_PROJECT_MONEY_RE`). Sans elle, il n'y a pas d'échelle —
    # et l'absence de chiffre exploitable est signalée par
    # `reference_client_illisible`, qui nomme le vrai problème.
    reference = 0.0
    for key in _MONETARY_FACT_KEYS:
        valeur = client_facts.get(key, "")
        if not _MONTANT_AVEC_DEVISE.search(valeur):
            continue
        numbers = _client_numbers(valeur)
        if numbers:
            reference = max(reference, max(numbers))
    if reference <= 0:
        # LIMITE ASSUMEE, pas un oubli : sans le moindre chiffre client, il
        # n'existe aucune echelle a laquelle rapporter les montants du document.
        # Une etude de marche sans previsionnel n'est donc pas couverte par ce
        # check — `_check_etat_chiffre_present` a deja statue pour le BP, seul
        # livrable ou la donnee est exigible.
        return []

    ceiling = reference * _MAGNITUDE_FACTOR
    failures: list[GateFailure] = []
    for section in sections:
        for match in _PROJECT_MONEY_RE.finditer(section.body):
            # `_amount_from_match` porte la normalisation d'unite partagee :
            # « 420 millions », « 420 M€ » et « 420 000 000 € » donnent le meme
            # montant. Un parsing local reintroduirait la divergence.
            absolute = _amount_from_match(match)
            if absolute is None:
                continue
            if absolute > ceiling:
                failures.append(GateFailure(
                    check="ordre_de_grandeur",
                    chapter_number=section.number,
                    detail=(
                        f"Montant hors d'échelle : {match.group(0).strip()!r} "
                        f"= {absolute:,.0f} €, soit plus de {_MAGNITUDE_FACTOR}× "
                        f"la référence client ({reference:,.0f} €). "
                        "Erreur d'unité probable (millions au lieu de milliers)."
                    ),
                ))
    return failures


# « résultat net d'année 1 », « CA An2 », « EBE an 3 » : l'année que le
# document attribue au montant qu'il cite.
_YEAR_IN_MENTION_RE = re.compile(r"(?:ann[ée]e|an)\s*(\d)", re.IGNORECASE)


# « Une AUGMENTATION DE L'emprunt de 59 000 € » : 59 000 n'est pas l'emprunt,
# c'est de combien il varie. Un delta n'est pas une valeur — le confondre
# revient a accuser le document d'avoir change un chiffre qu'il n'a pas touche.
# Cas reel bloque a tort dans les annexes du BP SYNAPSES, sur une analyse de
# sensibilite que le brief demande explicitement.
_DELTA_AVANT_RE = re.compile(
    r"(?:augmentation|hausse|baisse|r[ée]duction|diminution|variation|majoration"
    r"|surco[ûu]t|[ée]cart|delta|suppl[ée]ment)\s+(?:de\s+|d['’])?(?:l['’]|la\s+|le\s+)?$",
    re.IGNORECASE,
)


def _est_un_delta(texte: str, position: int) -> bool:
    """Le montant qui suit est-il une VARIATION plutot qu'une valeur ?"""
    return bool(_DELTA_AVANT_RE.search(texte[max(0, position - 40) : position]))


def _est_un_scenario(phrase: str, expected: list[float]) -> bool:
    """La phrase COMPARE-t-elle au chiffre du brief, au lieu de le remplacer ?

    Un business plan bancaire DOIT contenir des variantes chiffrées : stress
    tests, sensibilité, scénarios de financement. Le brief SYNAPSES en demande
    explicitement. La tolérance zéro les interdisait toutes.

    Cas réel bloqué à tort : « emprunt additionnel de 59 000 € porté de
    920 000 € à 979 000 € ». Le document ne substitue rien — il cite la valeur
    du brief et raisonne dessus. Accuser ici, c'est reprocher au document de
    faire son travail.

    Règle : si la valeur du brief figure dans la MÊME phrase, le document la
    respecte et la discute ; il ne la remplace pas. Une hallucination, elle,
    pose son chiffre seul (« l'emprunt de 300 000 € structure le plan ») sans
    jamais mentionner la vraie valeur — et reste donc bloquée.
    """
    nombres = amounts_in(phrase)
    return any(any(n == e for e in expected) for n in nombres)


def _phrase_autour(texte: str, position: int) -> str:
    """La phrase qui contient la position donnée."""
    debut = max(texte.rfind(".", 0, position), texte.rfind("\n", 0, position)) + 1
    fin_point = texte.find(".", position)
    fin_ligne = texte.find("\n", position)
    candidats = [f for f in (fin_point, fin_ligne) if f != -1]
    fin = min(candidats) + 1 if candidats else len(texte)
    return texte[debut:fin]


def _mention_est_conforme(
    *,
    found: float,
    mention: str,
    expected: list[float],
    is_trajectory: bool,
    lo: float,
    hi: float,
    phrase: str = "",
) -> bool:
    """Le montant cité par le document est-il conforme au brief ?

    L'ANNÉE est le discriminant, et c'est elle qui résout la tension entre les
    deux erreurs possibles :

    - accuser à tort : le brief donne le CA An1, le document parle du CA An2 —
      une valeur différente est parfaitement légitime. Bloquer ici, c'est
      envoyer corriger un chiffre qui n'était pas faux (la boucle v3 -> v18) ;
    - ne rien voir : le brief donne le résultat net An1 = 44 245 €, le document
      écrit « résultat net d'année 1 : 21 874 € ». MÊME ANNÉE, autre valeur.
      C'est le défaut n°3 signalé par la cliente, et il doit bloquer.

    Sauter toute trajectoire à valeur unique — le correctif precedent —
    supprimait la premiere erreur mais rouvrait la seconde. Comparer année par
    année les traite toutes les deux.

    Les valeurs du brief sont chronologiques : `_extract_trajectories` les
    collecte dans l'ordre d'apparition, qui est l'ordre des années dans un
    prévisionnel.
    """
    if any(found == e for e in expected):
        return True

    # Le document COMPARE-t-il au chiffre du brief ? Alors il ne le remplace
    # pas : c'est un scenario, et un BP bancaire en exige.
    if phrase and _est_un_scenario(phrase, expected):
        return True

    # Un scalaire (investissement, emprunt) n'a qu'une valeur possible : toute
    # divergence est bloquante, sans fourchette ni exception d'année.
    if not is_trajectory:
        return False

    year = _YEAR_IN_MENTION_RE.search(mention)
    if year is not None:
        index = int(year.group(1)) - 1
        if 0 <= index < len(expected):
            # Année connue du brief : comparaison exacte, tolérance zéro.
            return found == expected[index]
        # Année hors du prévisionnel fourni : on ne sait pas juger, on n'accuse
        # pas. Ne pas savoir n'autorise pas à accuser.
        return True

    # Mention sans année. Avec un seul point de référence, impossible de savoir
    # de quelle année parle le document.
    if len(expected) == 1:
        return True
    # Avec une trajectoire, une valeur intermédiaire reste plausible.
    return lo <= found <= hi


def _check_numeric_coherence(
    job: GenerationJob, sections: tuple[RenderedSection, ...]
) -> list[GateFailure]:
    """Tolérance zéro entre les chiffres du document et l'état client.

    Pour chaque fait client numérique, toutes les occurrences repérées dans
    le document doivent correspondre à un nombre du brief (exactement, ou
    dans la fourchette si le brief donne une trajectoire multi-années).
    """
    failures: list[GateFailure] = []
    client_facts = {
        fact.key: fact.value
        for fact in job.coherence_facts.filter(
            is_locked=True, provenance=FactProvenance.CLIENT
        )
    }

    for key, patterns in _CLIENT_FACT_PATTERNS.items():
        client_value = client_facts.get(key, "")
        expected = _client_numbers(client_value)
        if not expected:
            continue  # pas de donnée client structurée pour cette clé

        # Le document est cherché avec `_MONEY` : une unité monétaire est
        # OBLIGATOIRE de ce côté. Le brief, lui, était lu par `amounts_in`, où
        # l'unité est facultative — d'où la comparaison d'un montant à des
        # nombres qui n'en sont pas. On ne juge pas sans référence opposable.
        if _exige_une_devise(patterns) and not _MONTANT_AVEC_DEVISE.search(client_value):
            failures.append(GateFailure(
                check="reference_client_illisible",
                # `None` et non `0` : un échec à zéro est routé vers le
                # chapitre 1 pour réécriture (`correction.py`), et aucune
                # réécriture ne fera apparaître un chiffre que le client n'a
                # pas donné. On paierait une reprise pour rien. Sans chapitre,
                # l'échec bloque la livraison et remonte au rapport — ce qui
                # est exactement ce qu'on veut : une action humaine.
                chapter_number=None,
                detail=(
                    f"{key} : le brief client ne donne aucun montant "
                    f"exploitable — sa réponse est en texte libre "
                    f"({_extrait(client_value)}). Le document ne peut donc pas "
                    "être confronté à une référence, et ce n'est pas au "
                    "rédacteur de la deviner : il faut obtenir le chiffre "
                    "auprès du client."
                ),
            ))
            continue

        is_trajectory = key in _TRAJECTORY_FACT_KEYS
        lo, hi = min(expected), max(expected)
        for section in sections:
            for pattern in patterns:
                for m in pattern.finditer(section.body):
                    found = _amount_from_match(m)
                    if found is None:
                        continue
                    # « augmentation de l'emprunt de 59 000 € » : un delta,
                    # pas la valeur de l'emprunt. Rien a comparer.
                    if _est_un_delta(section.body, m.start()):
                        continue
                    if not _mention_est_conforme(
                        found=found,
                        mention=m.group(0),
                        expected=expected,
                        is_trajectory=is_trajectory,
                        lo=lo,
                        hi=hi,
                        phrase=_phrase_autour(section.body, m.start()),
                    ):
                        failures.append(GateFailure(
                            check="coherence_chiffree",
                            chapter_number=section.number,
                            detail=(
                                # `m.group(0)` et non `m.group(1)` : le groupe 1
                                # ne porte que les chiffres, sans l'unite. Le
                                # message annoncait « document dit '3' » pour un
                                # document disant « 3 M€ » — un motif introuvable
                                # dans le texte, qui envoie chercher a cote.
                                f"{key} : le document dit {m.group(0).strip()!r} "
                                f"(soit {found:,.0f}), le brief client dit "
                                f"{client_value!r}"
                            ),
                        ))
    return failures


def _check_arithmetique(
    sections: tuple[RenderedSection, ...]
) -> list[GateFailure]:
    """Refait les opérations que le document POSE lui-même.

    Demande de la cliente, 13/08/2026 : « vérifier automatiquement tous les
    calculs simples : pourcentages, ratios, taux de conversion, marges,
    évolutions, parts de marché, additions, moyennes et projections ».

    Le déclencheur est mesuré : « 102 / 50 000 000 = 0,000204 % », écrit douze
    fois dans un business plan. L'unité fautive est réparée à la source ; ce
    contrôle attrape la classe entière — un résultat qui ne découle pas de ses
    propres termes, quelle qu'en soit la cause.

    Ne juge QUE les opérations explicites, celles dont le texte donne les deux
    termes et le résultat. Deviner un terme manquant produirait des motifs
    faux, et ce projet a mesuré ce qu'ils coûtent.
    """
    from .arithmetique import totaux_faux, verifier  # noqa: PLC0415

    failures: list[GateFailure] = []
    for section in sections:
        for faute in verifier(section.body):
            failures.append(GateFailure(
                check="calcul_faux",
                chapter_number=section.number,
                detail=str(faute),
            ))
        # Les tableaux qui ANNONCENT un total : la somme se refait, elle aussi.
        for total in totaux_faux(section.body):
            failures.append(GateFailure(
                check="calcul_faux",
                chapter_number=section.number,
                detail=str(total),
            ))
    return failures


def _check_sources_coherentes(
    sections: tuple[RenderedSection, ...]
) -> list[GateFailure]:
    """Une meme donnee ne peut pas venir de deux sources differentes.

    Demande de la cliente, 13/08/2026 : « tester les coherences interchapitres
    toujours niveau chiffres ET sources ». La coherence des CHIFFRES etait
    controlee depuis longtemps ; celle des SOURCES ne l'etait pas.

    Le motif porte sur le DOCUMENT, pas sur un chapitre : la divergence n'existe
    qu'entre deux endroits, et l'accrocher a l'un des deux enverrait corriger
    au hasard.
    """
    from .arithmetique import sources_divergentes  # noqa: PLC0415

    return [
        GateFailure(check="source_divergente", detail=str(divergence))
        for divergence in sources_divergentes([s.body for s in sections])
    ]


def _check_verticales(
    job: GenerationJob, sections: tuple[RenderedSection, ...]
) -> list[GateFailure]:
    """Chaque verticale d'activité du brief doit apparaître dans le livrable."""
    fact = job.coherence_facts.filter(
        is_locked=True, provenance=FactProvenance.CLIENT, key="verticales"
    ).first()
    if fact is None or not fact.value.strip():
        return []

    verticales = [v.strip() for v in re.split(r"[/,;]|\n", fact.value) if v.strip()]
    if not verticales:
        return []

    full_text = _strip_accents_lower("\n".join(s.body for s in sections))
    failures: list[GateFailure] = []
    for verticale in verticales:
        needle = _verticale_needle(verticale)
        if needle and not _verticale_present(needle, full_text):
            failures.append(GateFailure(
                check="verticales",
                detail=(
                    f"Verticale du brief absente du livrable : {verticale!r}. "
                    "Le remplacement silencieux d'une activité client par un "
                    "modèle générique est interdit."
                ),
            ))
    return failures


def _check_truncation(sections: tuple[RenderedSection, ...]) -> list[GateFailure]:
    from .qa import detect_violations  # import local : éviter le cycle qa->gate

    failures: list[GateFailure] = []
    for section in sections:
        violations = detect_violations(section.body, prompt_key="", chapter_number=section.number)
        for v in violations:
            if v.name in _BLOCKING_TRUNCATION:
                failures.append(GateFailure(
                    check="troncature",
                    chapter_number=section.number,
                    detail=f"{v.name}: {v.detail}",
                ))
    return failures


def _check_fourchettes(
    job: GenerationJob, sections: tuple[RenderedSection, ...]
) -> list[GateFailure]:
    """Aucune fourchette monetaire ni de pourcentage dans le livrable.

    Regle stricte pour BP / EC / STR : chaque valeur est unique. En EM
    (manuel Evangeline juillet 2026, §3), une fourchette serree et
    coherente est autorisee (« entre 1 000 et 1 400 »), les taux/% sont
    en valeur fixe unique. Cette nuance ne se detecte pas fiablement en
    regex, elle est desormais controlee par les CHECK Sonnet 1/5/6/7 du
    module `checks_blocs.py`. On skippe donc ce check pour EM.
    """
    if str(job.deliverable_type) == DeliverableType.MARKET_STUDY:
        return []

    from .checks_evangeline import detecter_fourchettes  # noqa: PLC0415

    failures: list[GateFailure] = []
    for section in sections:
        for f in detecter_fourchettes(
            section.number, section.body,
            deliverable_type=str(job.deliverable_type),
        ):
            failures.append(GateFailure(
                check="fourchette_interdite",
                chapter_number=f.chapitre,
                detail=(
                    f"Fourchette detectee : « {f.extrait} ». Le document doit "
                    "citer un chiffre unique, decide et source, pas une plage."
                ),
            ))
    return failures


# _check_concurrents_ec : migre dans `strategies/ec.py` (etape 6).
# La logique est desormais portee par la ECStrategy, appelee via
# `_check_strategie_livrable`. Regle 4 : chaque livrable a son manuel.


# _check_piliers_strategie : migre dans `strategies/str_.py` (etape 5).
# La logique est desormais portee par la STRStrategy, appelee via
# `_check_strategie_livrable`. Regle 4 : chaque livrable a son manuel.


def _check_post_rendu(
    sections: tuple[RenderedSection, ...],
    *,
    deliverable_type: str = "",
) -> list[GateFailure]:
    """Verifications transverses sur le rendu final.

    Pour EM (manuel Evangeline juillet 2026), on conserve uniquement les
    GARDES-CATASTROPHE deterministes :
      - troncature (chapitre coupe mid-phrase — bug reel WAOME 21/07/2026)
      - sources absent/vide ou URL bidon (example.com, source.fr...)
    Les autres regles historiques (doublons de titres, desaccords « trois
    familles » vs 4 items, ton publicitaire, prudence juridique) sont
    couvertes en amont par le nouveau charter (voix EVKHA §3) et par les
    CHECK Sonnet inter-blocs, qui evaluent le sens en langage naturel.
    Les conserver ici cree des faux positifs bloquants sur des livrables
    conformes au manuel.

    Pour BP/EC/STR : tous les checks restent actifs (manuel ne les couvre pas).
    """
    from .checks_post_rendu import (  # noqa: PLC0415
        detecter_demandes_contredites,
        detecter_desaccords_numeriques,
        detecter_doublons_titres,
        detecter_prudence_juridique,
        detecter_sources_non_tracables,
        detecter_ton_publicitaire,
        detecter_troncatures,
    )

    is_em = deliverable_type == DeliverableType.MARKET_STUDY

    triplets = [(s.number, s.title, s.body) for s in sections]

    failures: list[GateFailure] = []
    for t in detecter_troncatures(triplets):
        failures.append(GateFailure(
            check="troncature_rendu",
            chapter_number=t.chapitre,
            detail=(
                f"Chapitre « {t.titre} » tronque : la derniere ligne ne se "
                f"termine pas par une ponctuation forte. Fin capturee : "
                f"« ...{t.fin_capturee} ». Perte probable de contenu client."
            ),
        ))
    for s in detecter_sources_non_tracables(triplets):
        # Pour EM : on garde absent, vide, url_bidon (garde-catastrophe).
        # On retire ratio_faible : le manuel ne fixe pas de ratio et les
        # CHECK Sonnet 8 (bloc H) + FINAL evaluent la traçabilite en langage
        # naturel.
        if is_em and s.motif == "ratio_faible":
            continue
        failures.append(GateFailure(
            check=f"sources_non_tracables_{s.motif}",
            chapter_number=s.chapitre,
            detail=s.detail,
        ))

    # AVANT le retour anticipé de l'étude de marché : la contradiction vaut
    # pour les QUATRE livrables. Le chapitre de validation des demandes existe
    # partout — EC 8, stratégie 19, étude de marché 22, business plan 20 — et
    # le contrôle des statuts ne vivait que dans la strategy EC, où il
    # vérifiait seulement qu'UN statut existe, jamais qu'il soit vrai.
    #
    # « Les canaux d'acquisition sont bien analysés au chapitre 3 puis
    # déclarés non traités au chapitre 8 » (cliente, 11/08/2026, sur une étude
    # notée 8,5/10). Un point annoncé puis déclaré non traité est pire qu'un
    # point absent : il fait douter de tout le reste.
    for contradiction in detecter_demandes_contredites(triplets):
        failures.append(GateFailure(
            check="demande_contredite",
            chapter_number=contradiction.chapitre,
            detail=contradiction.detail,
        ))

    if is_em:
        return failures

    # BP/EC/STR : anciens checks conserves.
    for d in detecter_doublons_titres(triplets):
        failures.append(GateFailure(
            check="doublon_titre",
            chapter_number=d.chapitre,
            detail=(
                f"Titre « {d.intitule} » apparait {d.occurrences} fois dans "
                f"le meme chapitre. Verifier l'assemblage."
            ),
        ))
    for n in detecter_desaccords_numeriques(triplets):
        failures.append(GateFailure(
            check="desaccord_numerique",
            chapter_number=n.chapitre,
            detail=n.detail,
        ))
    corpus_par_chapitre = {s.number: s.body for s in sections}
    titres_par_chapitre = {s.number: s.title for s in sections}
    for t in detecter_ton_publicitaire(
        corpus_par_chapitre, titres_par_chapitre=titres_par_chapitre,
    ):
        failures.append(GateFailure(
            check="ton_publicitaire",
            chapter_number=t.chapitre,
            detail=(
                f"Expression au ton publicitaire detectee : « {t.expression} ». "
                f"Contexte : « ...{t.extrait}... ». Un livrable bancaire reste "
                "descriptif et source — supprimer le superlatif ou le "
                "remplacer par un fait chiffre."
            ),
        ))
    for r in detecter_prudence_juridique(
        corpus_par_chapitre, titres_par_chapitre=titres_par_chapitre,
    ):
        failures.append(GateFailure(
            check=f"prudence_juridique_{r.categorie}",
            chapter_number=r.chapitre,
            detail=r.detail + f" Extrait : « ...{r.extrait}... ».",
        ))
    return failures


def _check_strategie_livrable(
    job: GenerationJob, sections: tuple[RenderedSection, ...]
) -> list[GateFailure]:
    """Delegue les checks specifiques du livrable a sa strategy dediee.

    Chaque type de livrable (EM, EC, BP, STR) a sa propre logique metier
    exposee via `strategies/`. Cette porte d'entree unique appelle
    `problemes_de_coherence` sur la strategy — un livrable qui n'a pas
    encore de strategy dediee retombe sur le fallback neutre, aucune
    regression.

    C'est ici que passent les checks arithmetiques EM (TCAC recalcule,
    ratios), et bientot les checks BP (charges obligatoires, IS bracket),
    EC (matrice concurrentielle) et STR (piliers traites).
    """
    from .strategies import get_strategy  # noqa: PLC0415

    corpus = {s.number: s.body for s in sections}
    strategy = get_strategy(str(job.deliverable_type))
    return [
        GateFailure(
            check=f"strategy_{strategy.deliverable_type}_{p.categorie}",
            chapter_number=p.chapitre,
            detail=p.detail,
        )
        for p in strategy.problemes_de_coherence(job, corpus)
    ]


def _check_chapitres_avortes(
    job: GenerationJob, sections: tuple[RenderedSection, ...]
) -> list[GateFailure]:
    """Ralph Wiggum : un chapitre trop court, declare fini quand meme.

    Le runner passe `ChapterStatus.DONE` sans regarder la longueur, et le
    check `_check_truncation` cible la coupure a mi-phrase, pas le contenu
    indigent. Un chapitre de 900 mots qui en rend 250 est objectivement
    avorte, quel qu'en soit le motif (fenetre de contexte, refus du modele,
    exception avalee). On plancher a 30 % du `max_words` du blueprint.
    """
    from .blueprints import chapters_for_deliverable  # noqa: PLC0415
    from .checks_evangeline import detecter_chapitres_avortes  # noqa: PLC0415

    plafonds: dict[int, tuple[str, int]] = {
        bp.number: (bp.title, bp.max_words)
        for bp in chapters_for_deliverable(job.deliverable_type)
    }
    entrees = [
        (s.number, plafonds.get(s.number, (s.title, 0))[0], s.body,
         plafonds.get(s.number, ("", 0))[1])
        for s in sections
    ]
    failures: list[GateFailure] = []
    for a in detecter_chapitres_avortes(entrees):
        failures.append(GateFailure(
            check="chapitre_avorte",
            chapter_number=a.chapitre,
            detail=(
                f"Chapitre {a.chapitre} ({a.titre}) : {a.mots_rendus} mots "
                f"pour un plafond de {a.mots_attendus} (soit {a.ratio:.0%}). "
                "Contenu indigent — le chapitre a ete declare fini alors qu'il "
                "n'a pas ete produit."
            ),
        ))
    return failures


def _check_chiffre_contre_chiffre(
    sections: tuple[RenderedSection, ...],
) -> list[GateFailure]:
    """Un meme libelle chiffre = une seule valeur dans tout le document.

    Constat sur le BP SYNAPSES relu par Evangeline : tresorerie de 3 328 458 €
    contre 328 458 €, fin d'annee 1 a 168 622 puis 163 672, seuil de
    rentabilite avec trois valeurs concurrentes. Le gate comparait le document
    au brief, il ne comparait pas le chapitre 15 au chapitre 8. On le fait ici.
    """
    from .checks_evangeline import collecter_mentions, detecter_divergences  # noqa: PLC0415

    mentions = []
    for section in sections:
        mentions.extend(collecter_mentions(section.number, section.body))

    failures: list[GateFailure] = []
    for div in detecter_divergences(mentions):
        failures.append(GateFailure(
            check="coherence_chiffree",
            chapter_number=div.mentions[0].chapitre,
            detail=(
                f"Valeurs divergentes pour un meme libelle : {div.resume}. "
                "Une seule methode de calcul et un seul chiffre par libelle "
                "dans le document."
            ),
        ))
    return failures


def _check_blocs_evangeline(job: GenerationJob) -> list[GateFailure]:
    """Un CHECK de bloc reste-t-il en echec non resolu ?

    Manuel EVKHA, repete a la fin de CHAQUE bloc (pp. 8-16) : « Si une reponse
    est non : corriger le bloc concerne, refaire le controle, puis seulement
    continuer. » Et p.17, « Livraison autorisee » : « La livraison est possible
    uniquement lorsque le fond, les chiffres, les demandes client, les sources,
    la continuite et la presentation sont tous valides. »

    Le runner rejoue le bloc une fois ; si le CHECK echoue encore, il ouvre un
    incident. Avant ce garde-fou, cet incident etait purement informatif : le
    document partait quand meme chez le client avec un controle non valide.
    Desormais il BLOQUE la livraison. L'admin qui traite l'incident (statut
    ACKNOWLEDGED/RESOLVED) rend la livraison possible — c'est la traduction du
    « corriger, refaire le controle, puis seulement continuer ».
    """
    from monitoring.models import IncidentStatus, OperationalIncident  # noqa: PLC0415

    from .checks_blocs import INCIDENT_TYPE_CHECK_BLOC  # noqa: PLC0415

    ouverts = OperationalIncident.objects.filter(
        job=job,
        status=IncidentStatus.OPEN,
        details__type=INCIDENT_TYPE_CHECK_BLOC,
    )

    failures: list[GateFailure] = []
    for incident in ouverts:
        details = incident.details or {}
        chapitres = details.get("chapitres") or []
        detail = (
            f"CHECK {details.get('check', '?')} (bloc "
            f"{details.get('bloc', '?')} — {details.get('intitule', '')}) "
            f"non valide sur les chapitres {chapitres}. "
            f"Note du relecteur : {str(details.get('note_corrective', ''))[:400]} "
            "Livraison bloquee tant que le controle n'est pas valide "
            "(manuel EVKHA, « Livraison autorisee »)."
        )
        # UNE entree par chapitre nomme, et le numero est PORTE.
        #
        # Il ne l'etait pas, volontairement : « la boucle a deja rejoue le bloc
        # sans succes, le manuel demande une reprise humaine ». Le raisonnement
        # tient pour le chemin AUTOMATIQUE, et `_is_regenerable` l'y maintient
        # — ce check reste hors de la whitelist, donc la generation ne rejoue
        # rien d'elle-meme.
        #
        # Mais la reprise humaine EXISTE desormais : c'est le bouton
        # « corriger » du recontrole, ou l'admin decide apres avoir lu la note.
        # Sans numero de chapitre, cette reprise ne savait rien regenerer et la
        # note du relecteur — « dedupliquer les deux entrees Xerfi du tableau
        # 21.2 », precise et actionnable — restait lettre morte. Mesure sur
        # `cc0dfe14` (11/08/2026) : sept CHECK bloquants, sept chapitres
        # nommes dans le texte, zero routable.
        for numero in chapitres or [None]:
            failures.append(GateFailure(
                check="check_bloc_non_resolu",
                chapter_number=numero,
                detail=detail,
            ))
    return failures


def _check_arithmetique_marche(job: GenerationJob) -> list[GateFailure]:
    """Bloque un document dont l'emboitement TAM > SAM > SOM est faux.

    Verdict Evangeline du 24/07/2026 sur le run 010e3bf2 : « TAM, SAM et SOM
    incoherents », « erreurs de calcul importantes ». Aucun check du gate ne
    regardait ces trois chiffres — ils n'existaient meme pas dans le registre.
    Le controle porte sur les faits VERROUILLES et non sur le texte rendu :
    c'est la valeur verrouillee que les chapitres 14 et 15 reutilisent, donc
    c'est elle qui doit etre juste.
    """
    from .coherence import anomalies_tam_sam_som  # noqa: PLC0415

    return [
        GateFailure(
            check="arithmetique_marche",
            detail=(
                f"{anomalie} Manuel EVKHA p. 6 : la ligne TAM / SAM / SOM est "
                "reutilisee aux chapitres 2, 14 et 15."
            ),
        )
        for anomalie in anomalies_tam_sam_som(job)
    ]


def run_delivery_gate(job: GenerationJob) -> GateReport:
    """Exécute les quatre checks bloquants sur le document tel que livré.

    Lecture seule : aucune écriture en base. L'appelant (tasks.py) décide
    des effets (statut BLOCKED, incident, blocage de l'email).
    """
    if not job.chapters.filter(status=ChapterStatus.DONE).exists():
        return GateReport(
            passed=False,
            failures=(GateFailure(check="troncature", detail="Aucun chapitre généré."),),
        )

    document = render_client_document(job)
    sections = document.sections

    failures: list[GateFailure] = []
    # Check 0 EN PREMIER : sans état chiffré client, les checks 2 et 3 n'ont
    # rien à comparer. Les laisser « passer » était le trou d'entrée du gate.
    failures.extend(_check_etat_chiffre_present(job))
    # Vaut pour TOUS les types de livrable, contrairement au check ci-dessus
    # qui ne couvre que le business plan.
    failures.extend(_check_brief_lu(job))
    failures.extend(_check_completude_chapitres(job, sections))
    failures.extend(_check_contamination(job, sections))
    failures.extend(_check_numeric_coherence(job, sections))
    failures.extend(_check_verticales(job, sections))
    failures.extend(_check_truncation(sections))
    failures.extend(_check_ordres_de_grandeur(job, sections))
    failures.extend(_check_arithmetique(sections))
    failures.extend(_check_sources_coherentes(sections))
    failures.extend(_check_arithmetique_marche(job))
    # Checks ajoutes suite a la relecture d'Evangeline (juillet 2026) : ils
    # verifient DEUX regles qu'aucun check precedent n'imposait sur le document
    # livre. Independants du brief et du type de livrable, ils s'appliquent aux
    # quatre types (etude de marche, etude de concurrence, business plan,
    # strategie).
    failures.extend(_check_fourchettes(job, sections))
    failures.extend(_check_chiffre_contre_chiffre(sections))
    failures.extend(_check_chapitres_avortes(job, sections))
    failures.extend(_check_strategie_livrable(job, sections))
    failures.extend(_check_post_rendu(sections, deliverable_type=str(job.deliverable_type)))
    # Manuel EVKHA p.17 : livraison possible UNIQUEMENT si tous les controles
    # sont valides. Un CHECK de bloc encore en echec bloque l'envoi.
    failures.extend(_check_blocs_evangeline(job))

    return GateReport(passed=not failures, failures=tuple(failures))

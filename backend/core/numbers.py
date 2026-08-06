"""Source UNIQUE de lecture des nombres et des montants du pipeline.

Pourquoi ce module existe
-------------------------
`intake/financials.py` (extraction du brief) et `generation/gate.py` (controle
de coherence) manipulaient chacun leur propre idee de ce qu'est un nombre.
Ils n'etaient pas d'accord, et le desaccord etait silencieux :

- financials acceptait l'espace fine insecable U+202F comme separateur de
  milliers — c'est celle que Word et Excel inserent en francais. Le gate ne
  strippait que l'espace normale et U+00A0 : `float()` levait ValueError, le
  nombre etait jete, et le check se sautait SANS RIEN DIRE. Un brief colle
  depuis Word desarmait toute la coherence chiffree.
- financials extrayait « 1,25 M€ » ; le gate lisait « 1.25 » et le comparait a
  « 1 250 000 » ecrit par le modele. Meme montant, blocage, motif mensonger.
- financials acceptait FCFA/XOF ; les motifs du gate n'acceptaient que l'euro.
  Pour ces dossiers, l'etat chiffre etait verrouille puis jamais compare.

Ces defauts sont le MEME : deux lectures divergentes du meme texte.

AUCUNE LISTE FERMEE DE CARACTERES
---------------------------------
Une premiere version enumerait les espaces admises (' ', U+00A0, U+202F, tab).
C'etait encore une liste a rallonger a chaque decouverte : U+2009 (espace fine
des typographes) la traversait, coupait le nombre en morceaux et produisait
`[1.0, 250.0, 0.0]` pour « 1 250 000 € ». Le gate bloquait alors un document
disant EXACTEMENT le montant du brief, avec le motif « document dit 1 250 000,
brief client dit 1 250 000 € » — deux chaines identiques. Pire que le defaut
d'origine, qui se contentait de se taire.

On raisonne donc par CLASSE : toute espace horizontale Unicode (`[^\\S\\r\\n]`)
separe des milliers ; le saut de ligne, lui, est exclu — un montant ne s'etale
jamais sur deux lignes, et l'admettre ferait deborder les motifs d'une phrase a
l'autre.

REGLE : aucun module ne parse un nombre ou une devise pour son compte. Les
motifs se composent a partir des constantes exportees ici.
"""
from __future__ import annotations

import re

# Toute espace horizontale Unicode : espace, insecable (U+00A0), fine insecable
# (U+202F), fine (U+2009), tabulation... Le saut de ligne en est exclu.
SPACE_CLASS = r"[^\S\r\n]"

# Corps d'un nombre francais : chiffres separes par des espaces horizontales,
# decimale optionnelle. Le lookbehind evite de capturer le « 1 » de « An1 » ou
# le « 4 » de « M4 » : un chiffre colle a une lettre est un indice d'annee ou de
# mois, pas un montant.
NUMBER_BODY = rf"-?\d(?:\d|{SPACE_CLASS})*(?:[.,]\d+)?"
_NUMBER_START = r"(?<![A-Za-z\d])"

# Fin de mot, cote DROIT d'une unite. Sans elle, « euro » se reconnaissait au
# debut d'« Europe » : le sous-titre « 1.2 Europe et France » etait lu comme le
# montant « 1,2 euro », et la passe de verification le signalait comme un chiffre
# sans equivalent au socle. Un motif d'echec introuvable dans le document par le
# lecteur est pire qu'absent (regle 2) — releve sur le livrable `4b827759`.
#
# Elle est posee DANS l'alternation, et pas a chaque emploi : les quatre motifs
# qui s'en servent la recevraient sinon separement, et l'un d'eux finirait par
# l'oublier (regle 5).
_FIN_D_UNITE = r"(?![A-Za-zÀ-ÖØ-öø-ÿ])"

# Devises reconnues, prefixes longs AVANT les courts (sinon « M€ » serait
# tronque en « € »). Zone euro + zone franc CFA : la table `_COUNTRY_CURRENCY`
# de generation/coherence.py mappe une douzaine de pays vers XOF/XAF.
CURRENCY_ALTERNATION = (
    rf"(?:Mds€|Md€|M€|k€|kEUR|€|euros?|EUR|FCFA|XOF|XAF|CFA){_FIN_D_UNITE}"
)

# Mots de magnitude ecrits en toutes lettres (« 420 millions d'euros »).
MAGNITUDE_WORDS = rf"(?:millions?|milliards?){_FIN_D_UNITE}"

# Montant SANS groupe capturant — a envelopper par l'appelant.
MONEY = rf"{NUMBER_BODY}{SPACE_CLASS}*(?:{CURRENCY_ALTERNATION})"

# Montant AVEC groupes : (1) le nombre, (2) l'unite. L'unite est indispensable :
# sans elle « 1,25 M€ » est lu 1.25 et compare a 1 250 000.
MONEY_CAPTURED = rf"({NUMBER_BODY}){SPACE_CLASS}*({CURRENCY_ALTERNATION})"

# Nombre + unite optionnelle (devise OU mot de magnitude), pour lire une valeur
# de fait client qui peut etre multiple : « 250 272 € / 296 000 € », « 55 % ».
AMOUNT_WITH_UNIT_RE = re.compile(
    rf"{_NUMBER_START}({NUMBER_BODY}){SPACE_CLASS}*"
    rf"({CURRENCY_ALTERNATION}|{MAGNITUDE_WORDS})?",
    re.IGNORECASE,
)

# Facteur vers l'unite de base. Une unite absente ou inconnue vaut 1 : le
# montant est deja exprime en unites (€, FCFA, %...).
_UNIT_MULTIPLIERS: dict[str, float] = {
    "k€": 1_000,
    "keur": 1_000,
    "m€": 1_000_000,
    "md€": 1_000_000_000,
    "mds€": 1_000_000_000,
    "million": 1_000_000,
    "millions": 1_000_000,
    "milliard": 1_000_000_000,
    "milliards": 1_000_000_000,
}

_ALL_WHITESPACE_RE = re.compile(r"\s")


def parse_number(raw: str) -> float | None:
    """Lit un nombre francais, quelle que soit l'espace utilisee en milliers.

    Strippe TOUTE espace Unicode, pas une liste choisie : c'est la seule facon
    de ne pas devoir rallonger le code au prochain caractere exotique.

    Retourne None si la chaine n'est pas un nombre — jamais d'exception, mais
    l'appelant DOIT traiter le None : le jeter en silence est precisement ce
    qui desarmait le gate.
    """
    if not raw:
        return None
    cleaned = _ALL_WHITESPACE_RE.sub("", raw).replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def to_base_units(value: float, unit: str | None) -> float:
    """Ramene un montant a son unite de base (« 1,25 M€ » -> 1 250 000)."""
    if not unit:
        return value
    return value * _UNIT_MULTIPLIERS.get(unit.strip().lower(), 1)


def parse_amount(raw: str, unit: str | None = None) -> float | None:
    """Nombre + unite -> montant en unites de base. None si illisible."""
    number = parse_number(raw)
    if number is None:
        return None
    return to_base_units(number, unit)


def amounts_in(text: str) -> list[float]:
    """Tous les montants d'un texte, normalises en unites de base."""
    found: list[float] = []
    for match in AMOUNT_WITH_UNIT_RE.finditer(text):
        amount = parse_amount(match.group(1), match.group(2))
        if amount is not None:
            found.append(amount)
    return found

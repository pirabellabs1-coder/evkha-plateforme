"""Brique 1 — Etat chiffre client injecte par SUBSTITUTION de tokens.

Brief client (juillet 2026), verbatim : « Ces valeurs doivent etre injectees
par substitution de tokens dans le texte genere, pas laissees a la libre
interpretation du modele. Le modele n'ecrit pas "environ X €", il recoit le
nombre deja ecrit et le retranscrit. »

Jusqu'ici les chiffres client n'etaient qu'un bloc de contexte (DONNEES_CLIENT)
que le modele restait libre de reformuler, arrondir ou ignorer — exactement le
mecanisme que le brief rejette. La Brique 1 avait ete reinterpretee en
« meilleur prompt », alors que 20 iterations montraient que le niveau prompt ne
suffit pas.

Fonctionnement
--------------
1. Le prompt liste les tokens disponibles (`{{emprunt}}`, `{{investissement_total}}`...).
2. Quand le modele cite un chiffre du previsionnel, il ecrit le token.
3. Ce module remplace chaque token par la valeur EXACTE du brief, avant toute
   validation. Le nombre livre ne transite jamais par le modele.

Filet de securite (defense en profondeur) : si le modele ecrit le nombre en
clair au lieu du token, le gate de livraison le compare a l'etat client en
tolerance zero. Si le modele invente un token inconnu, il reste non resolu et
le gate le bloque (`unresolved_curly_placeholder` / contamination). Les deux
modes de defaillance sont donc couverts.

Portee volontairement limitee aux faits SCALAIRES
-------------------------------------------------
Les trajectoires pluriannuelles (CA An1..An5, EBE, resultat net) sont exclues :
un token unique `{{ca_previsionnel}}` resoudrait vers « 250 272 € / 296 000 € »,
ce qui n'a aucun sens dans une phrase. Les decouper par annee supposerait de
deviner a quelle annee correspond chaque valeur — c'est precisement le genre
d'inference qui a produit les incoherences d'origine. Ces trajectoires restent
donc couvertes par le gate (comparaison en fourchette), pas par substitution.

Les faits scalaires couverts ici sont ceux que le cas SYNAPSES a vu deraper :
investissement total (1 250 000 € ignore) et emprunt (920 000 € devenu
300 000 €).
"""
from __future__ import annotations

import re

from .models import FactProvenance, GenerationJob

# Faits client scalaires : une valeur, une seule lecture possible.
SUBSTITUTABLE_FACT_KEYS: tuple[str, ...] = (
    "investissement_total",
    "apport",
    "emprunt",
    "subventions",
    "seuil_rentabilite",
    "capital_initial",
)

# Token accepte : {{cle}}, tolerant aux espaces internes et a la casse.
_TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def substitutable_facts(job: GenerationJob) -> dict[str, str]:
    """Faits CLIENT scalaires disponibles a la substitution pour ce job."""
    return {
        fact.key: fact.value
        for fact in job.coherence_facts.filter(
            is_locked=True, provenance=FactProvenance.CLIENT
        )
        if fact.key in SUBSTITUTABLE_FACT_KEYS and fact.value.strip()
    }


def tokens_catalogue(job: GenerationJob) -> str:
    """Bloc lisible listant les tokens utilisables, pour le prompt.

    Chaque ligne montre le token ET la valeur exacte : le modele voit le
    nombre deja ecrit (exigence du brief) et n'a aucune raison de l'estimer.
    """
    facts = substitutable_facts(job)
    if not facts:
        return ""
    lines = [f"- {{{{{key}}}}} = {value}" for key, value in sorted(facts.items())]
    return "\n".join(lines)


def resolve_client_fact_tokens(content: str, job: GenerationJob) -> tuple[str, list[str]]:
    """Remplace les tokens client par leur valeur exacte.

    Retourne (contenu_resolu, tokens_non_resolus). Un token inconnu est laisse
    INTACT volontairement : le supprimer masquerait le probleme, alors que le
    laisser le fait bloquer par le gate — le defaut doit etre vu, pas efface.
    """
    facts = substitutable_facts(job)
    unresolved: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1).lower()
        value = facts.get(key)
        if value is None:
            unresolved.append(match.group(0))
            return match.group(0)
        return value

    return _TOKEN_RE.sub(_replace, content), unresolved

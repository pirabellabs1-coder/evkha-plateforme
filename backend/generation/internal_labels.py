"""Source UNIQUE des intitules internes du pipeline.

Pourquoi ce module existe
-------------------------
Le brief client de juillet 2026 signale un PDF livre contenant « en parfaite
coherence avec les FAITS_VERROUILLES » : un intitule interne du pipeline avait
fuite dans la redaction. Trois defenses ont ete mises en place... chacune avec
SA PROPRE liste de labels, recopiee a la main :

- le nettoyeur du Rendering Engine (`strip_internal_label_tokens`) ;
- le check de contamination du gate sur le contenu brut ;
- le meme check sur le HTML rendu.

Resultat previsible : en ajoutant le bloc CHIFFRES_A_CITER au contexte
(Brique 1), le label a ete oublie des trois listes. Le defaut exact que ces
defenses etaient censees empecher a donc ete rouvert, sous un autre nom, par
le commit cense les renforcer. Un audit independant l'a attrape.

La correction n'est pas d'ajouter CHIFFRES_A_CITER aux trois endroits — ce
serait reparer l'instance et laisser la cause. C'est qu'il n'existe plus
qu'UNE liste : tout label ajoute ici est automatiquement connu du nettoyeur
ET des deux niveaux du gate. Le prochain oubli devient structurellement
impossible plutot que corrige au cas par cas.

REGLE : tout nouvel intitule ecrit en MAJUSCULES_AVEC_UNDERSCORES injecte dans
le contexte du modele DOIT etre ajoute a `INTERNAL_LABEL_NAMES` ci-dessous, et
nulle part ailleurs.
"""
from __future__ import annotations

import re

# Intitules injectes dans le contexte de generation (cf. `context.py`).
# Le modele ne doit JAMAIS les recopier dans sa redaction.
INTERNAL_LABEL_NAMES: tuple[str, ...] = (
    "FAITS_VERROUILLES",
    "VARIABLES_PROJET",
    "DONNEES_CLIENT",
    "CHIFFRES_A_CITER",
    "REPERES_DEJA_ENONCES",
    "RESUME_OPERATIONNEL_PRECEDENT",
    "RESUME_OPERATIONNEL",
    "FICHE_SECTORIELLE",
    "SOURCES_WEB",
    "CHAPITRE_CIBLE",
    "CHAPITRE_PARENT",
    "SECTIONS_PRECEDENTES",
    "PROMPT_KEY",
    "SECTION_A_GENERER",
    "CONSIGNE_DU_CHAPITRE",
    "DATE_DU_JOUR",
    "CONTEXTE_ETUDE_PRECEDENTE",
    # Intitulés du prompt de la chaîne Word (`chapitres/runner.py`,
    # `socle/prompt.py`). `BRIEF_CLIENT` y circulait depuis le lot 2 sans être
    # listé ; `DOCUMENTS_DU_CLIENT` arrive le 11/09/2026 avec la lecture des
    # pièces jointes. Relevé par la relecture du même jour.
    "BRIEF_CLIENT",
    "DOCUMENTS_DU_CLIENT",
    # Marqueur de coupure de cache du system prompt
    # (integrations.claude.SYSTEM_CACHE_BREAK). Il est normalement consomme par
    # `_cacheable_system` avant l'appel API et n'atteint donc jamais le modele,
    # mais il transite bien par le system prompt : la REGLE de ce module
    # s'applique sans exception, et le jour ou un appelant oublie de passer par
    # `_cacheable_system`, le gate l'attrape au lieu de le livrer.
    "EVKHA_CACHE_BREAK",
    # Registre JSON de coherence inter-chapitres (lot 84, 20/09/2026).
    # Injecte dans les deux chaines (context.py et chapitres/runner.py).
    "REGISTRE_CHIFFRES",
)

# Marqueurs de placeholder jamais tolerables dans un livrable (brief client :
# « grep des tokens interdits... Si un seul apparait -> rejet »).
PLACEHOLDER_TOKENS: tuple[str, ...] = ("TODO", "PLACEHOLDER", "XXX")

# Placeholders en clair que le prompt demande au modele de REMPLACER — lot 85
# lui fait ecrire « prix non publie en ligne au [date du jour] » puis substituer
# la date reelle. S'il oublie, la chaine part telle quelle chez le client. Ces
# formes portent des crochets et des minuscules : elles ne passent pas par
# l'alternation a `\b` de PLACEHOLDER_TOKENS, d'ou une liste et une
# alternation ECHAPPEES a part. Comparaison insensible a la casse.
PLACEHOLDER_PHRASES: tuple[str, ...] = (
    "[date du jour]",
    "[à compléter]",
    "[a completer]",
    "[à définir]",
    "[a definir]",
    "lorem ipsum",
)

# Marqueurs d'encadre mentor. LEGITIMES dans le contenu brut (le convertisseur
# les transforme en encadres stylises), interdits dans le HTML final.
CALLOUT_MARKERS: tuple[str, ...] = ("UNDERSTAND", "CONSIDER", "ATTENTION", "ACTION")


def labels_alternation() -> str:
    """Alternation regex des intitules internes, pour composer un motif."""
    return "|".join(INTERNAL_LABEL_NAMES)


def forbidden_words_alternation() -> str:
    """Intitules internes + placeholders, en alternation regex."""
    return "|".join((*INTERNAL_LABEL_NAMES, *PLACEHOLDER_TOKENS))


def placeholder_phrases_alternation() -> str:
    """Placeholders en clair, ECHAPPES : a composer sans `\\b`, avec `(?i:...)`."""
    return "|".join(re.escape(phrase) for phrase in PLACEHOLDER_PHRASES)


def callout_alternation() -> str:
    """Alternation regex des marqueurs d'encadre mentor."""
    return "|".join(CALLOUT_MARKERS)

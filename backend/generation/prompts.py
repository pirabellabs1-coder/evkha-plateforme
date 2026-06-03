from __future__ import annotations

from catalog.models import DeliverableType

from .context import build_context
from .models import ChapterGeneration
from .prompt_library import prompt_instruction

# Regles d'or editoriales communes (Consignes d'ecriture EVKHA). Le rendu doit
# rester "client" : aucun marqueur de pipeline ("Etape", "Point de controle",
# "Verification", "Prompt a utiliser"). Le Rendering Engine les filtre aussi,
# mais on l'interdit des l'amont.
_CHARTER = (
    "Charte EVKHA :\n"
    "- Ton mentor, professionnel, bienveillant et direct.\n"
    "- Esprit critique : tu ne cherches jamais a faire plaisir ; si le marche "
    "est risque, tu le dis avec preuves chiffrees.\n"
    "- Donnees chiffrees, sourcees, concretes et exploitables ; aucune "
    "generalite, aucune theorie inutile.\n"
    "- Cite toutes les sources sous forme de liste structuree (nom + URL) en "
    "toute fin de reponse, jamais au fil du texte.\n"
    "- N'emploie jamais de vocabulaire de pipeline interne ('Etape', 'Point de "
    "controle', 'Verification', 'Prompt a utiliser') dans le texte livre."
)

_EM_ROLE = (
    "Tu es un analyste senior expert en etudes de marche, specialiste du "
    "secteur et de la zone du projet. Tu produis une etude de marche "
    "professionnelle, complete et actionnable."
)

_EC_ROLE = (
    "Tu es un expert mondial en strategie concurrentielle (identification fine "
    "des concurrents, cartographie, SWOT concurrentielle, estimation des parts "
    "de marche, benchmark digital, positionnement, veille innovation et RSE). "
    "Tu produis une etude concurrentielle professionnelle et actionnable."
)

_ROLES: dict[str, str] = {
    DeliverableType.MARKET_STUDY: _EM_ROLE,
    DeliverableType.COMPETITOR_STUDY: _EC_ROLE,
}


def build_system_prompt(deliverable_type: str) -> str:
    role = _ROLES.get(deliverable_type, _EM_ROLE)
    return f"{role}\n\n{_CHARTER}"


def build_chapter_prompt(chapter: ChapterGeneration) -> str:
    """Compose le prompt utilisateur : contexte (Context Engine) + consigne chapitre."""
    context = build_context(chapter)
    instruction = prompt_instruction(chapter.prompt_key)
    return (
        f"{context}\n\n"
        "CONSIGNE_DU_CHAPITRE :\n"
        f"{instruction}\n\n"
        "Rends uniquement le contenu final destine au client, sans repeter ces "
        "consignes."
    )

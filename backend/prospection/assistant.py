"""L'assistant conversationnel de la prospection.

Evangéline discute avec lui pour affiner sa cible ; quand la discussion aboutit
à des critères précis, il PROPOSE une recherche (il ne la lance pas lui-même —
un passage réel est facturé, et il reste gardé par une confirmation côté admin).

Comme les agents, il reçoit son client par injection (défaut : la fabrique), et
ne lève jamais sur une réponse malformée : il retombe sur un message neutre.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import brief
from .agents import _client_structure, _texte
from .models import Campagne

if TYPE_CHECKING:
    from integrations.claude import StructuredClaudeClient

_MODELE = "claude-sonnet"

#: On borne l'historique transmis : une discussion sans fin ferait grossir le
#: coût de chaque tour sans rien apporter au conseil.
_MAX_TOURS = 20

_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "reponse": {"type": "string"},
        "proposition_recherche": {
            "type": "object",
            "properties": {
                "criteres": {"type": "string"},
                "limite": {"type": "integer", "minimum": 1, "maximum": 25},
            },
        },
    },
    "required": ["reponse"],
}


def _systeme(campagne: Campagne | None) -> str:
    contexte = ""
    if campagne is not None:
        contexte = (
            f"\n\nCampagne en cours : « {campagne.nom} », secteur "
            f"{campagne.secteur or 'non précisé'}, zone {campagne.zone or 'non précisée'}, "
            f"offre {campagne.offre_visee or 'non précisée'}."
        )
    return (
        f"{brief.brief_assistant()}\n\n"
        "Tu es l'assistant de prospection d'EVKHA. Tu aides à définir QUI cibler "
        "et COMMENT, en t'appuyant sur les 5 cibles ci-dessus : secteur, zone, "
        "signes d'intérêt, et l'angle du message. Tu vouvoies ton "
        "interlocutrice, tu es concis et concret, et tu formules tes conseils "
        "comme des avis, pas des ordres. "
        "Quand la discussion aboutit à une cible précise, remplis "
        "`proposition_recherche` avec des `criteres` en une phrase actionnable "
        "(ce qui affinera la recherche web) ; sinon laisse ce champ vide et pose "
        "la question qui manque. Tu ne lances jamais la recherche toi-même : tu "
        "la proposes, et c'est un humain qui la déclenche." + contexte
    )


def _transcription(messages: list[Any]) -> str:
    lignes = []
    for m in messages[-_MAX_TOURS:]:
        if not isinstance(m, dict):
            continue
        role = "Vous" if str(m.get("role")) == "assistant" else "Interlocutrice"
        contenu = str(m.get("content") or "").strip()
        if contenu:
            lignes.append(f"{role} : {contenu}")
    return "\n".join(lignes)


def repondre(
    messages: list[Any],
    *,
    campagne: Campagne | None = None,
    client: StructuredClaudeClient | None = None,
) -> dict[str, Any]:
    """Rend la réponse de l'assistant et, le cas échéant, une proposition de recherche.

    Forme : `{"reponse": str, "proposition_recherche": {"criteres", "limite"} | None}`.
    """
    client = _client_structure(client)
    resultat = client.complete_structured(
        system=_systeme(campagne),
        prompt=(
            f"Discussion jusqu'ici :\n{_transcription(messages) or '(début de la discussion)'}"
            "\n\nRéponds au dernier message."
        ),
        outil_nom="repondre_prospection",
        outil_description="Rend la réponse de l'assistant et une proposition de recherche.",
        schema=_SCHEMA,
        model=_MODELE,
    )
    charge = resultat.payload
    reponse = str(charge.get("reponse") or "").strip()
    proposition: dict[str, Any] | None = None
    brut = charge.get("proposition_recherche")
    if isinstance(brut, dict):
        criteres = _texte(brut, "criteres", 400)
        if criteres:
            limite = brut.get("limite")
            proposition = {
                "criteres": criteres,
                "limite": limite if isinstance(limite, int) and 1 <= limite <= 25 else 10,
            }
    defaut = "Je n'ai pas de réponse pour l'instant — pouvez-vous préciser votre cible ?"
    return {
        "reponse": reponse or defaut,
        "proposition_recherche": proposition,
    }

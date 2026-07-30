"""Passe 1 — production du socle de données.

Un appel au modèle, contraint par un schéma JSON, validé contre le
référentiel. Une réponse invalide déclenche une nouvelle tentative avec les
motifs exacts du refus ; jamais un passage en force.
"""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from .prompt import construire_prompt_socle
from .referentiel import identifiants_pour, livrable_couvert
from .schema import Socle, valider_socle

_log = logging.getLogger(__name__)

OUTIL_NOM = "produire_socle"
OUTIL_DESCRIPTION = (
    "Enregistre le socle de données chiffrées de l'étude. Chaque donnée porte "
    "un identifiant du référentiel imposé, une valeur numérique, une unité, "
    "une année, un périmètre et un statut de fiabilité."
)

#: Nombre maximum d'appels au modèle pour un socle. Au-delà, on rend la main :
#: un modèle qui échoue trois fois sur un schéma explicite n'échouera pas moins
#: la quatrième, et chaque tentative se paie.
MAX_TENTATIVES = 3


class SocleGenerationError(RuntimeError):
    """La passe 1 n'a pas produit de socle recevable après toutes les tentatives."""

    def __init__(self, motifs: list[str], tentatives: int) -> None:
        self.motifs = motifs
        self.tentatives = tentatives
        super().__init__(
            f"Socle non recevable après {tentatives} tentative(s) : " + " ; ".join(motifs)
        )


def schema_outil(deliverable_type: str) -> dict[str, Any]:
    """Schéma JSON de l'outil, restreint aux identifiants du livrable.

    L'énumération des identifiants est injectée dans le schéma lui-même :
    le modèle ne peut donc pas produire un identifiant inconnu, l'API le
    refuse avant nous.
    """
    schema = Socle.model_json_schema()

    # `deliverable_type` est un champ de travail interne, jamais rempli par le
    # modèle : il n'a rien à faire dans le contrat exposé.
    schema.get("properties", {}).pop("deliverable_type", None)
    if "required" in schema:
        schema["required"] = [nom for nom in schema["required"] if nom != "deliverable_type"]

    identifiants = sorted(identifiants_pour(deliverable_type))
    donnee = schema.get("$defs", {}).get("DonneeSocle", {})
    if donnee and identifiants:
        donnee.setdefault("properties", {}).setdefault("id", {})["enum"] = identifiants

    return schema


def _analyser(charge: dict[str, Any], deliverable_type: str) -> tuple[Socle | None, list[str]]:
    """Valide la charge utile. Retourne (socle, motifs). Socle non nul = accepté."""
    if not charge:
        return None, ["Le modèle n'a produit aucun appel d'outil exploitable."]

    try:
        socle = Socle.model_validate(charge)
    except ValidationError as erreur:
        motifs = [
            f"{'.'.join(str(p) for p in item['loc'])} : {item['msg']}"
            for item in erreur.errors()[:12]
        ]
        return None, motifs

    motifs = valider_socle(socle, deliverable_type)
    if motifs:
        return None, motifs

    socle.deliverable_type = deliverable_type
    return socle, []


def produire_socle(
    *,
    client: Any,
    deliverable_type: str,
    variables: Mapping[str, object],
    brief_recherche: str = "",
    max_tokens: int = 8192,
) -> tuple[Socle, dict[str, int], int]:
    """Produit et valide le socle.

    Retourne `(socle, consommation, tentatives)`. Lève `SocleGenerationError`
    si aucune tentative n'aboutit — le job doit alors s'arrêter avant toute
    rédaction, puisqu'il n'a rien sur quoi la fonder.
    """
    if not livrable_couvert(deliverable_type):
        msg = f"Aucun référentiel de socle pour le livrable « {deliverable_type} »."
        raise SocleGenerationError([msg], 0)

    schema = schema_outil(deliverable_type)
    consommation = {"input_tokens": 0, "output_tokens": 0}
    motifs: list[str] = []
    systeme = (
        "Tu produis des socles de données pour des études de marché "
        "professionnelles. Tu réponds exclusivement par un appel de l'outil "
        f"`{OUTIL_NOM}`."
    )

    for tentative in range(1, MAX_TENTATIVES + 1):
        prompt = construire_prompt_socle(
            deliverable_type=deliverable_type,
            variables=variables,
            brief_recherche=brief_recherche,
            motifs_precedents=motifs or None,
        )
        resultat = client.complete_structured(
            system=systeme,
            prompt=prompt,
            outil_nom=OUTIL_NOM,
            outil_description=OUTIL_DESCRIPTION,
            schema=schema,
            max_tokens=max_tokens,
        )
        consommation["input_tokens"] += resultat.input_tokens
        consommation["output_tokens"] += resultat.output_tokens

        socle, motifs = _analyser(dict(resultat.payload), deliverable_type)
        if socle is not None:
            return socle, consommation, tentative

        _log.warning(
            "Socle refusé (tentative %s/%s) : %s",
            tentative, MAX_TENTATIVES, " ; ".join(motifs[:5]),
        )

    raise SocleGenerationError(motifs, MAX_TENTATIVES)

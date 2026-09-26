"""Passe 1 — production du socle de données.

Un appel au modèle, contraint par un schéma JSON, validé contre le
référentiel. Une réponse invalide déclenche une nouvelle tentative avec les
motifs exacts du refus ; jamais un passage en force.
"""
from __future__ import annotations

import logging
from collections.abc import Collection, Mapping
from typing import Any

from pydantic import ValidationError

from core.numbers import amounts_in
from integrations.claude import motif_de_troncature

from .prompt import construire_prompt_socle
from .referentiel import identifiants_du_client, identifiants_pour, livrable_couvert
from .schema import (
    DonneeSocle,
    Socle,
    reparer_la_grille,
    reparer_les_filiations,
    retirer_les_zeros_qui_manquent,
    valeur_en_unites_de_base,
    valider_socle,
)

_log = logging.getLogger(__name__)

OUTIL_NOM = "produire_socle"

#: Plafond de SORTIE de l'appel qui produit le socle.
#:
#: ## Le défaut mesuré
#:
#: 12/08/2026, reprise `779862a5` : « Socle non recevable après 3 tentatives :
#: le modèle n'a produit aucun appel d'outil exploitable. » Zéro chapitre, là
#: où le dossier d'origine en produisait vingt-et-un.
#:
#: La charge revenait VIDE. Le client cherche un bloc `tool_use` dans la
#: réponse ; quand elle est coupée en plein appel d'outil, il n'en trouve
#: aucun et rend `{}` — un motif qui accuse le modèle alors que c'est la
#: fenêtre qui manquait.
#:
#: Ce qui a changé le même jour : le socle d'un business plan réclame
#: désormais la base concurrents (onze acteurs à neuf champs, une grille et ses
#: cinquante-cinq notes) EN PLUS de son prévisionnel financier. Son prompt est
#: passé de 11 000 à 15 000 signes, et sa charge de sortie a grossi d'autant.
#: L'étude concurrentielle tenait dans 8 192 jetons parce qu'elle n'a pas le
#: prévisionnel ; le business plan porte les deux.
#:
#: ## Pourquoi élargir plutôt que rogner
#:
#: Rogner la demande — moins de concurrents pour un business plan — est
#: probablement la bonne réponse de fond, mais elle exige un CHIFFRE, et ce
#: chiffre appartient à la cliente (voir le commentaire de
#: `_BASE_CONCURRENTS` dans `socle/prompt.py`). Une fenêtre trop étroite, elle,
#: n'est la réponse à aucune question : elle coupe le travail au milieu.
#:
#: Le plafond ne coûte rien en soi — seuls les jetons RÉELLEMENT produits sont
#: facturés. Il autorise, il ne dépense pas.
_PLAFOND_DE_SORTIE_SOCLE = 16384
OUTIL_DESCRIPTION = (
    # « données chiffrées » et non « socle de données » : cette description
    # part au modèle avec le schéma de l'outil, et `_VOCABULAIRE_INTERNE`
    # punit la seconde formule dans le texte livré. Un prompt ne doit jamais
    # écrire ce qu'un contrôle interdit (règle 5) — deux chapitres perdus sur
    # ce mécanisme le 12/09/2026, reprise Zenitek `db0d9508`.
    "Enregistre les données chiffrées de référence de l'étude. Chaque donnée porte "
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

    # Le TITRE racine (« Socle ») ne sert à rien au contrat, et il nomme une
    # enveloppe : trois fois de suite, le modèle a rangé toute la charge sous
    # `{"socle": …}` (génération `44bbd696`, 15/09/2026). Le client retire
    # désormais une telle enveloppe (`sans_enveloppe`) ; on cesse aussi de la
    # suggérer.
    schema.pop("title", None)

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


#: Écart relatif toléré entre un objectif du socle et le montant écrit par le
#: client : l'arrondi d'une recopie, pas une estimation.
_ECART_OBJECTIF_CLIENT = 0.005


def _objectifs_inventes(
    socle: Socle, deliverable_type: str, montants_client: Collection[float],
) -> list[DonneeSocle]:
    """Les objectifs du client que le socle chiffre sans que le client les donne.

    Génération test `6c9dc734` (stratégie, 15/09/2026) : le brief donnait
    51 030 € en année 1 et 685 004 € en année 3 ; le socle a produit
    `ca_objectif_horizon` = 1 070 000 € « à horizon 2031 », et le document l'a
    présenté comme la trajectoire visée — un objectif que personne n'avait fixé,
    dans un dossier qu'un banquier lira. Seul le client fixe ses objectifs : la
    valeur doit être un montant qu'il a écrit.
    """
    du_client = identifiants_du_client(deliverable_type)
    inventes: list[DonneeSocle] = []
    for item in socle.donnees:
        if item.id not in du_client:
            continue
        base = valeur_en_unites_de_base(item.valeur, item.unite)
        valeur = base[0] if base else item.valeur
        if not any(
            abs(valeur - montant) <= abs(montant) * _ECART_OBJECTIF_CLIENT
            for montant in montants_client
        ):
            inventes.append(item)
    return inventes


def _analyser(
    charge: dict[str, Any],
    deliverable_type: str,
    *,
    dernier_recours: bool = False,
    montants_client: Collection[float] | None = None,
) -> tuple[Socle | None, list[str]]:
    """Valide la charge utile. Retourne (socle, motifs). Socle non nul = accepté.

    `dernier_recours` répare la grille de notation au lieu de la refuser. Voir
    `reparer_la_grille` : sur les premières tentatives le refus fait corriger
    le modèle, mais à la dernière il tuerait l'étude avant son premier
    chapitre — ce qui est arrivé à `6a44baff` le 10/08/2026.
    """
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

    if montants_client is not None:
        inventes = _objectifs_inventes(socle, deliverable_type, montants_client)
        if inventes and not dernier_recours:
            return None, [
                f"`{item.id}` = {item.valeur:g} {item.unite} : un objectif que le brief ne "
                "chiffre pas. Seul le client fixe ses objectifs — retire cette donnée."
                for item in inventes
            ]
        if inventes:
            objectifs_retires = {item.id for item in inventes}
            socle.donnees = [
                item for item in socle.donnees if item.id not in objectifs_retires
            ]
            _log.warning(
                "Socle : objectifs non donnés par le client retirés — %s.",
                ", ".join(sorted(objectifs_retires)),
            )

    if dernier_recours:
        orphelines = reparer_les_filiations(socle)
        if orphelines:
            _log.warning(
                "Socle : filiations retirees faute de parent — %s. La donnee "
                "reste, sa provenance declaree ne pointait vers rien.",
                ", ".join(orphelines),
            )
        inconnues = retirer_les_zeros_qui_manquent(socle, deliverable_type)
        if inconnues:
            _log.warning(
                "Socle : données inconnues écrites 0 retirées — %s.", ", ".join(inconnues),
            )
        retires = reparer_la_grille(socle)
        if retires:
            _log.warning(
                "Socle : critères retirés faute d'acteurs notés — %s. "
                "Les figures qui les citaient seront abandonnées avec un motif.",
                ", ".join(retires),
            )

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
    documents_client: str = "",
    max_tokens: int = _PLAFOND_DE_SORTIE_SOCLE,
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

    # Les montants que le client a écrits : ses réponses et ses documents.
    montants_client = amounts_in(
        "\n".join(str(valeur) for valeur in variables.values() if valeur)
        + "\n" + documents_client
    )

    for tentative in range(1, MAX_TENTATIVES + 1):
        prompt = construire_prompt_socle(
            deliverable_type=deliverable_type,
            variables=variables,
            brief_recherche=brief_recherche,
            documents_client=documents_client,
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

        # Une réponse coupée par `max_tokens` arrive avec un `payload` vide ou
        # amputé. Sans ce test, `_analyser` la refusait pour « aucun appel
        # d'outil exploitable » — un motif qui ne dit pas au modèle ce qu'il
        # doit changer, donc trois tentatives identiques et un dossier mort
        # avant son premier chapitre (relecture du 26/09/2026).
        motifs = motif_de_troncature(
            str(getattr(resultat, "stop_reason", "end_turn")), max_tokens
        )
        if motifs:
            _log.warning(
                "Socle tronqué (tentative %s/%s) : %s",
                tentative, MAX_TENTATIVES, motifs[0],
            )
            continue

        socle, motifs = _analyser(
            dict(resultat.payload),
            deliverable_type,
            dernier_recours=tentative == MAX_TENTATIVES,
            montants_client=montants_client,
        )
        if socle is not None:
            return socle, consommation, tentative

        _log.warning(
            "Socle refusé (tentative %s/%s) : %s",
            tentative, MAX_TENTATIVES, " ; ".join(motifs[:5]),
        )

    raise SocleGenerationError(motifs, MAX_TENTATIVES)

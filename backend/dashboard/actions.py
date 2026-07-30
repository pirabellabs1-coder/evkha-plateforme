"""Actions d'administration EVKHA (§10.2, §10.6).

Elles renvoyaient toutes vers l'administration Django. C'est le seul écran du
produit qu'un exploitant n'a pas choisi : il ne porte pas la charte, il expose
tous les modèles sans distinction, et il oblige à comprendre la structure de la
base pour créditer un compte.

Ces vues remplacent cet usage. Elles sont **volontairement étroites** : doter,
suspendre, réactiver, traiter une demande. Tout le reste — corriger un socle,
éditer une trame — reste ailleurs tant qu'il n'a pas son propre écran, parce
qu'une action à moitié portée est pire que pas d'action du tout.

## Traçabilité

Chaque geste enregistre **qui**, **quoi**, **pourquoi**. Une dotation sans
motif est refusée : le §11 exige que chaque mouvement soit journalisé avec son
motif, et un journal dont la moitié des lignes n'explique rien ne sert à
personne.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from organisations import credits, services
from organisations.models import (
    DemandeCommerciale,
    Formule,
    Organisation,
    StatutDemande,
    TypeMouvement,
)

_log = logging.getLogger(__name__)


def _corps(request: HttpRequest) -> dict[str, Any]:
    try:
        charge = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return charge if isinstance(charge, dict) else {}


def _refus(message: str, code: str, statut: int) -> JsonResponse:
    return JsonResponse({"error": message, "code": code}, status=statut)


def _auteur(request: HttpRequest, charge: dict[str, Any]) -> str:
    """Qui a fait le geste.

    L'espace administrateur est encore protégé par un jeton PARTAGÉ : il ne
    distingue pas les administrateurs entre eux. L'auteur est donc **déclaré**
    et non déduit — le dire ici évite de croire à une traçabilité qui n'existe
    pas encore. Elle deviendra réelle quand les deux profils du §12 seront en
    place.
    """
    return str(charge.get("auteur", "")).strip() or "administration EVKHA"


def _organisation(identifiant: str) -> Organisation | None:
    return Organisation.objects.filter(id=identifiant).first()


# ── Crédits ──────────────────────────────────────────────────────────────────


@csrf_exempt
@require_http_methods(["POST"])
def doter(request: HttpRequest, organisation_id: str) -> HttpResponse:
    """Ajoute des crédits à une organisation, avec motif obligatoire (§10.2)."""
    organisation = _organisation(organisation_id)
    if organisation is None:
        return _refus("Organisation introuvable.", "introuvable", 404)

    charge = _corps(request)
    try:
        quantite = int(charge.get("quantite", 0))
    except (TypeError, ValueError):
        return _refus("Quantité invalide.", "quantite", 400)

    motif = str(charge.get("motif", "")).strip()
    if not motif:
        return _refus(
            "Un motif est obligatoire : un journal sans explication ne sert à "
            "personne.",
            "motif_manquant",
            400,
        )

    type_mouvement = str(charge.get("type", TypeMouvement.GESTE))
    if type_mouvement not in (TypeMouvement.GESTE, TypeMouvement.ACHAT):
        return _refus(
            "Seuls un geste commercial ou un achat peuvent être saisis à la "
            "main. Une dotation d'abonnement passe par l'échéance.",
            "type_interdit",
            400,
        )

    try:
        mouvement = credits.crediter(
            organisation,
            quantite,
            motif=motif,
            type_mouvement=type_mouvement,
            auteur=_auteur(request, charge),
        )
    except ValueError as refus:
        return _refus(str(refus), "quantite", 400)

    _log.info("Dotation de %s crédit(s) à %s : %s", quantite, organisation, motif)
    return JsonResponse(
        {
            "id": str(mouvement.id),
            "quantite": mouvement.quantite,
            "solde": credits.solde(organisation),
        },
        status=201,
    )


# ── Statut d'une organisation ────────────────────────────────────────────────


@csrf_exempt
@require_http_methods(["POST"])
def basculer_statut(request: HttpRequest, organisation_id: str) -> HttpResponse:
    """Suspend ou réactive une organisation (§10.2).

    Une suspension empêche toute nouvelle consommation ; les documents déjà
    produits restent accessibles. Le §13 le demande explicitement — retirer
    l'accès à un travail payé serait une autre décision, commerciale, et pas
    celle-ci.
    """
    organisation = _organisation(organisation_id)
    if organisation is None:
        return _refus("Organisation introuvable.", "introuvable", 404)

    charge = _corps(request)
    action = str(charge.get("action", ""))
    if action == "suspendre":
        motif = str(charge.get("motif", "")).strip()
        if not motif:
            return _refus(
                "Indiquez le motif de la suspension.", "motif_manquant", 400
            )
        services.suspendre(organisation, motif=f"{_auteur(request, charge)} — {motif}")
    elif action == "reactiver":
        services.reactiver(organisation)
    else:
        return _refus(
            "Action inconnue. Attendu : « suspendre » ou « reactiver ».",
            "action_inconnue",
            400,
        )

    return JsonResponse(
        {"id": str(organisation.id), "statut": organisation.statut}
    )


# ── Demandes commerciales ────────────────────────────────────────────────────


@csrf_exempt
@require_http_methods(["POST"])
def traiter_demande(request: HttpRequest, demande_id: str) -> HttpResponse:
    """Accorde ou refuse une demande venue d'un espace client (§10.2).

    Accorder un changement de formule applique **réellement** la souscription,
    et accorder des crédits les crédite réellement. Marquer « traitée » sans
    rien faire donnerait à EVKHA une liste propre et au client rien du tout.
    """
    demande = (
        DemandeCommerciale.objects.select_related("organisation", "formule_visee")
        .filter(id=demande_id)
        .first()
    )
    if demande is None:
        return _refus("Demande introuvable.", "introuvable", 404)
    if demande.statut != StatutDemande.OUVERTE:
        return _refus("Cette demande est déjà traitée.", "deja_traitee", 409)

    charge = _corps(request)
    decision = str(charge.get("decision", ""))
    reponse = str(charge.get("reponse", "")).strip()
    auteur = _auteur(request, charge)

    if decision == "refuser":
        if not reponse:
            return _refus(
                "Indiquez la raison du refus : elle est affichée au client.",
                "reponse_manquante",
                400,
            )
        demande.statut = StatutDemande.REFUSEE
    elif decision == "accorder":
        if demande.type == "changement_formule":
            if demande.formule_visee is None:
                return _refus(
                    "La formule visée n'existe plus.", "formule_absente", 409
                )
            services.souscrire(
                demande.organisation, demande.formule_visee, doter_immediatement=False
            )
        elif demande.type == "credits_additionnels":
            credits.crediter(
                demande.organisation,
                demande.quantite,
                motif=f"Achat de crédits accordé — demande du {demande.created_at:%d/%m/%Y}",
                type_mouvement=TypeMouvement.ACHAT,
                auteur=auteur,
            )
        demande.statut = StatutDemande.TRAITEE
    else:
        return _refus(
            "Décision inconnue. Attendu : « accorder » ou « refuser ».",
            "decision_inconnue",
            400,
        )

    demande.reponse = reponse
    demande.traitee_le = timezone.now()
    demande.save(update_fields=["statut", "reponse", "traitee_le", "updated_at"])
    _log.info("Demande %s %s par %s", demande.id, demande.statut, auteur)

    return JsonResponse(
        {
            "id": str(demande.id),
            "statut": demande.statut,
            "solde": credits.solde(demande.organisation),
        }
    )


# ── Formules ─────────────────────────────────────────────────────────────────


@require_http_methods(["GET"])
def formules(request: HttpRequest) -> HttpResponse:
    """Formules actives, pour alimenter les listes de l'administration."""
    return JsonResponse({
        "formules": [
            {
                "code": formule.code,
                "libelle": formule.libelle,
                "credits_par_echeance": formule.credits_par_echeance,
                "prix_mensuel_cents": formule.prix_mensuel_cents,
            }
            for formule in Formule.objects.filter(active=True).order_by(
                "prix_mensuel_cents"
            )
        ]
    })

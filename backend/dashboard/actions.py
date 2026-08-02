"""Actions d'administration EVKHA (§10.2, §10.6).

Elles renvoyaient toutes vers l'administration Django. C'est le seul écran du
produit qu'un exploitant n'a pas choisi : il ne porte pas la charte, il expose
tous les modèles sans distinction, et il oblige à comprendre la structure de la
base pour créditer un compte.

Ces vues remplacent cet usage. Elles sont **volontairement étroites** : ouvrir
un abonné, doter, suspendre, réactiver, traiter une demande. Tout le reste —
corriger un socle, éditer une trame — reste ailleurs tant qu'il n'a pas son
propre écran, parce qu'une action à moitié portée est pire que pas d'action du
tout.

## Ouvrir un abonné

`creer_organisation` existait dans `organisations/services.py` et n'était
appelée **par rien** hors des tests. L'espace administrateur savait souscrire
une formule, suspendre, réactiver — mais aucun chemin du produit ne créait une
organisation ni son compte de connexion. Autrement dit : impossible d'accueillir
un abonné autrement qu'en écrivant du Python dans un terminal. C'est le trou que
`creer_abonne` comble.

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

from organisations import credits, inscription, services
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


# ── Ouvrir un abonné ─────────────────────────────────────────────────────────


@csrf_exempt
@require_http_methods(["POST"])
def creer_abonne(request: HttpRequest) -> HttpResponse:
    """Crée l'organisation, son propriétaire et ses identifiants d'un seul geste.

    Les trois sont indissociables. Une organisation sans compte de connexion est
    invisible à son propre abonné ; un compte sans organisation ne peut rien
    afficher, puisque les vues de l'espace client reçoivent l'organisation
    résolue depuis le jeton.

    Le mot de passe est **validé par les validateurs du projet** plutôt que par
    une règle écrite ici : deux avis sur ce qu'est un mot de passe acceptable
    finiraient par se contredire (règle 5).

    Il n'est **jamais renvoyé** dans la réponse. L'administrateur qui ouvre le
    compte le connaît déjà — il vient de le saisir — et le journaliser en ferait
    une copie qu'on ne peut plus reprendre.
    """
    charge = _corps(request)
    auteur = _auteur(request, charge)
    raison_sociale = str(charge.get("raison_sociale", "")).strip()
    email = str(charge.get("email", "")).strip().lower()
    mot_de_passe = str(charge.get("mot_de_passe", ""))

    # Controles, unicite et orchestration viennent de `organisations.inscription`,
    # partages avec l'inscription publique de la page partenaires. Les dupliquer
    # ici ferait deux facons d'ouvrir un compte, qui finiraient par diverger sur
    # ce qui compte : les credits (regle 5).
    try:
        inscription.controler_saisie(
            raison_sociale=raison_sociale, email=email, mot_de_passe=mot_de_passe
        )
        inscription.refuser_si_deja_membre(email, nommer_organisation=True)
        formule = inscription.formule_ou_refus(str(charge.get("formule", "")))
        ouverture = inscription.ouvrir_compte(
            raison_sociale=raison_sociale,
            email=email,
            mot_de_passe=mot_de_passe,
            prenom=str(charge.get("prenom", "")).strip(),
            nom=str(charge.get("nom", "")).strip(),
            formule=formule,
            # L'administration ouvre un compte DEJA negocie : elle active et
            # dote. C'est le seul point ou les deux chemins different.
            activer_abonnement=True,
        )
    except inscription.InscriptionRefuseeError as refus:
        return _refus(str(refus), refus.code, refus.statut)

    organisation = ouverture.organisation
    abonnement = ouverture.abonnement

    _log.info(
        "Abonné ouvert : organisation %s (%s), propriétaire %s, formule %s, par %s",
        organisation.id,
        raison_sociale,
        email,
        formule.code if formule else "aucune",
        auteur,
    )

    return JsonResponse(
        {
            "organisation": {
                "id": str(organisation.id),
                "raison_sociale": organisation.raison_sociale,
            },
            "proprietaire": {"email": email},
            "formule": formule.code if formule else None,
            "credits_dotes": (
                abonnement.formule.credits_par_echeance if abonnement else 0
            ),
            "solde": credits.solde(organisation),
        },
        status=201,
    )


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
            # `doter_immediatement=True` : sans cela, l'abonne attendait le
            # prochain passage de la tache horaire pour voir ses credits, en
            # ayant deja perdu les precedents. Il regardait un solde a zero sur
            # une demande qu'on venait de lui ACCORDER.
            services.souscrire(
                demande.organisation, demande.formule_visee, doter_immediatement=True
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

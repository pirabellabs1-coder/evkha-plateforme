"""Les signalements clients, vus de l'administration — et l'assistance.

Deux gestes, et ils vont ensemble : lire ce qu'un client a signalé, puis aller
voir de près dans son espace. C'est la demande de la cliente le 04/09/2026, et
elle tient en une phrase — « on peut se connecter à l'espace et aller voir le
problème de plus près » — assortie d'une limite tout aussi nette : l'agent ne
doit pas pouvoir dépenser l'argent du client.

## Ce que l'assistance est, et ce qu'elle n'est pas

C'est une **vraie session** sur le compte visé. Une vue en lecture seule aurait
été plus rassurante à décrire, et inutile : on assiste quelqu'un pour réparer,
donc pour agir. Relancer une génération, corriger une charte, dépenser des
crédits déjà acquis restent possibles.

Ce qui est refusé l'est **côté serveur**, par le décorateur de l'espace
(`vues_espace.espace(interdit_en_assistance=True)`), sur deux familles : tout
ce qui parle d'argent au prestataire de paiement, et tout ce qui donne ou
retire un accès. Ce n'est pas un bouton caché dans l'interface — masquer un
bouton n'empêche personne d'appeler la route.

Le décorateur porte la liste à jour ; on ne la recopie pas ici. Un audit du
04/09/2026 a trouvé qu'une sixième route de paiement manquait à l'appel
pendant que cette prose en annonçait trois, et c'est exactement le faux repère
sur lequel la relecture suivante se serait appuyée.

## Sur la durée

La session d'assistance a la durée d'une session ordinaire. La cliente a
explicitement écarté une minuterie courte : elle éjectait l'agent au moment
précis où il enquête. Ce qui la borne est donc ailleurs — la révocation
explicite (`fermer_une_assistance`), la liste des assistances ouvertes, et la
trace laissée sur chaque jeton (`ouvert_par`, `created_at`,
`derniere_utilisation`).

## Sur le compte choisi

L'organisation peut compter plusieurs membres. On ouvre l'assistance sur le
compte du **propriétaire**, et à défaut sur le plus ancien membre actif : c'est
celui qui voit tout, donc le seul depuis lequel un problème est reproductible.
Choisir « le premier venu » aurait produit des sessions qui ne montrent pas le
problème signalé, sans que rien ne l'explique.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from organisations.authentification import ouvrir_une_assistance
from organisations.models import (
    CompteClient,
    JetonAcces,
    MembreOrganisation,
    Organisation,
    RoleOrganisation,
    Signalement,
    StatutSignalement,
    SujetSignalement,
)

_log = logging.getLogger(__name__)

#: Ce qu'on écrit dans `JetonAcces.ouvert_par`.
#:
#: La console est protégée par un jeton PARTAGÉ entre les administrateurs : elle
#: ne connaît aucun nom d'agent. On écrit donc ce qu'on sait vraiment. Inventer
#: un identifiant nominatif donnerait à la trace une précision qu'elle n'a pas,
#: et c'est exactement le genre de faux repère sur lequel on s'appuie le jour
#: d'un litige.
OUVERT_PAR = "console d'administration"


def _corps(request: HttpRequest) -> dict[str, Any]:
    try:
        return dict(json.loads(request.body or b"{}"))
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
        return {}


def _refus(message: str, code: str, statut: int) -> JsonResponse:
    return JsonResponse({"error": message, "code": code}, status=statut)


def _en_dict(signalement: Signalement) -> dict[str, Any]:
    return {
        "id": str(signalement.id),
        "organisation": signalement.organisation.raison_sociale,
        "organisation_id": str(signalement.organisation_id),
        "auteur": signalement.auteur.email if signalement.auteur else "",
        "sujet": signalement.sujet,
        "sujet_libelle": SujetSignalement(signalement.sujet).label,
        "message": signalement.message,
        "statut": signalement.statut,
        "statut_libelle": StatutSignalement(signalement.statut).label,
        "reponse": signalement.reponse,
        "livrable_id": str(signalement.livrable_id) if signalement.livrable_id else None,
        "cree_le": signalement.created_at.isoformat(),
        "traite_le": (
            signalement.traite_le.isoformat() if signalement.traite_le else None
        ),
    }


@require_http_methods(["GET"])
def liste(request: HttpRequest) -> HttpResponse:
    """Tous les signalements, les non traités d'abord.

    Le tri met « nouveau » avant « en cours » avant « traité » parce que c'est
    l'ordre alphabétique des codes — heureux hasard qu'on ne veut pas subir le
    jour où un statut s'ajoute. L'ordre est donc écrit, pas déduit.

    `a_traiter` est renvoyé à part et compte les DEUX statuts ouverts. Une
    pastille qui ne compterait que les nouveaux tomberait à zéro dès qu'on prend
    un dossier en charge, et laisserait croire qu'il n'y a plus rien à faire.
    """
    # Clés en `str` et non en `StatutSignalement` : `Signalement.statut` est une
    # chaîne une fois relue de la base, et un dictionnaire indexé par l'énuméré
    # ne l'y retrouverait pas — chaque signalement tomberait sur la valeur par
    # défaut, et le tri n'ordonnerait plus rien sans que rien ne le dise.
    ordre: dict[str, int] = {
        StatutSignalement.NOUVEAU.value: 0,
        StatutSignalement.EN_COURS.value: 1,
        StatutSignalement.TRAITE.value: 2,
    }
    lot = list(
        Signalement.objects.select_related("organisation", "auteur").order_by(
            "-created_at"
        )[:300]
    )
    lot.sort(key=lambda s: (ordre.get(s.statut, 9), -s.created_at.timestamp()))
    return JsonResponse({
        "signalements": [_en_dict(s) for s in lot],
        "a_traiter": Signalement.objects.filter(
            statut__in=[StatutSignalement.NOUVEAU, StatutSignalement.EN_COURS]
        ).count(),
        "statuts": [{"code": c.value, "libelle": c.label} for c in StatutSignalement],
    })


@csrf_exempt
@require_http_methods(["POST"])
def traiter(request: HttpRequest, signalement_id: str) -> HttpResponse:
    """Change le statut d'un signalement, et écrit la réponse au client.

    `traite_le` suit le statut dans les DEUX sens : posée en arrivant à
    « traité », effacée si l'on rouvre. Une date qui resterait après réouverture
    dirait qu'un dossier en cours est réglé — et c'est la colonne sur laquelle
    on compte les délais.

    La réponse est facultative mais **jamais effacée par omission** : un appel
    qui ne porte que le statut ne doit pas faire disparaître ce qui a déjà été
    écrit au client.
    """
    signalement = Signalement.objects.filter(id=signalement_id).first()
    if signalement is None:
        return _refus("Signalement introuvable.", "introuvable", 404)

    charge = _corps(request)
    statut = str(charge.get("statut", "")).strip()
    if statut and statut not in StatutSignalement.values:
        return _refus("Statut inconnu.", "statut_inconnu", 400)

    champs = []
    if statut:
        signalement.statut = statut
        champs.append("statut")
        signalement.traite_le = (
            timezone.now() if statut == StatutSignalement.TRAITE else None
        )
        champs.append("traite_le")
    if "reponse" in charge:
        signalement.reponse = str(charge.get("reponse", "")).strip()
        champs.append("reponse")

    if champs:
        champs.append("updated_at")
        signalement.save(update_fields=champs)
    return JsonResponse(_en_dict(signalement))


def _compte_a_assister(organisation: Organisation) -> CompteClient | None:
    """Le compte depuis lequel on verra ce que le client voit.

    Le propriétaire d'abord : c'est le seul rôle qui voit tout. À défaut, le
    plus ancien membre actif — un compte créé hier peut n'avoir jamais ouvert le
    document dont on parle.
    """
    membres = (
        MembreOrganisation.objects.select_related("customer")
        .filter(organisation=organisation, revoque_le__isnull=True)
        .order_by("created_at")
    )
    proprietaires = [m for m in membres if m.role == RoleOrganisation.PROPRIETAIRE]
    for membre in proprietaires + list(membres):
        compte = CompteClient.objects.filter(
            customer=membre.customer, actif=True
        ).first()
        if compte is None:
            continue
        # Le compte choisi doit retomber sur CETTE organisation, et par le même
        # chemin que le décorateur de l'espace — qui prend la première
        # appartenance active, sans tri (`vues_espace.espace`). L'invariant
        # « une seule appartenance par personne » n'est imposé qu'au point
        # d'invitation ; si une seconde existait, la console annoncerait une
        # organisation et en ouvrirait une autre. On refuse plutôt que
        # d'ouvrir la mauvaise.
        vue_par_le_decorateur = (
            MembreOrganisation.objects.filter(
                customer=membre.customer, revoque_le__isnull=True
            )
            .values_list("organisation_id", flat=True)
            .first()
        )
        if vue_par_le_decorateur != organisation.pk:
            _log.warning(
                "Assistance refusee : %s appartient d'abord a %s, pas a %s",
                membre.customer.email,
                vue_par_le_decorateur,
                organisation.pk,
            )
            continue
        return compte
    return None


@csrf_exempt
@require_http_methods(["POST"])
def ouvrir_assistance(request: HttpRequest, organisation_id: str) -> HttpResponse:
    """Délivre à la console un jeton de session sur l'espace de ce client.

    Le jeton en clair n'est rendu qu'ici, une fois : rien ne le conserve. La
    console le pose dans le navigateur et ouvre `/espace`, où l'interface
    affiche un bandeau qu'on ne peut pas manquer.

    **Ce que cette route ouvre, elle le ferme aussi** : le jeton porte
    `assistance=True`, ce qui fait refuser côté serveur toute vue qui engage une
    dépense. Sans ce drapeau, la route serait un contournement complet du
    paiement — un agent pourrait souscrire avec la carte d'une cliente.
    """
    organisation = Organisation.objects.filter(id=organisation_id).first()
    if organisation is None:
        return _refus("Organisation introuvable.", "introuvable", 404)

    compte = _compte_a_assister(organisation)
    if compte is None:
        return _refus(
            "Cette organisation n'a aucun compte de connexion actif : il n'y a "
            "pas d'espace à ouvrir.",
            "sans_compte",
            409,
        )

    jeton = ouvrir_une_assistance(compte, par=OUVERT_PAR)
    _log.warning(
        "Assistance ouverte sur %s (%s) depuis la console",
        organisation.raison_sociale,
        organisation.pk,
    )
    return JsonResponse({
        "jeton": jeton,
        "organisation": organisation.raison_sociale,
        "compte": compte.user.username,
    })


@require_http_methods(["GET"])
def assistances(request: HttpRequest) -> HttpResponse:
    """Les sessions d'assistance encore ouvertes.

    Elles n'ont pas de minuterie : sans cet écran, une session oubliée serait
    invisible, et c'est précisément ce qui rendrait la durée illimitée
    dangereuse. La liste est la contrepartie du choix.
    """
    lot = (
        JetonAcces.objects.select_related("compte", "compte__customer")
        .filter(assistance=True, revoque_le__isnull=True, expire_le__gt=timezone.now())
        .order_by("-created_at")[:100]
    )
    return JsonResponse({
        "assistances": [
            {
                "id": str(jeton.id),
                "compte": jeton.compte.user.username,
                "ouvert_par": jeton.ouvert_par,
                "ouvert_le": jeton.created_at.isoformat(),
                "derniere_utilisation": (
                    jeton.derniere_utilisation.isoformat()
                    if jeton.derniere_utilisation
                    else None
                ),
            }
            for jeton in lot
        ]
    })


@csrf_exempt
@require_http_methods(["POST"])
def fermer_une_assistance(request: HttpRequest, jeton_id: str) -> HttpResponse:
    """Révoque une session d'assistance depuis la console.

    Ne révoque QUE les jetons d'assistance : `assistance=True` fait partie du
    filtre. Sans lui, cette route déconnecterait un client de sa propre session
    depuis un identifiant deviné.
    """
    nombre = JetonAcces.objects.filter(
        id=jeton_id, assistance=True, revoque_le__isnull=True
    ).update(revoque_le=timezone.now())
    if not nombre:
        return _refus("Aucune assistance ouverte sous cet identifiant.", "introuvable", 404)
    return JsonResponse({"ferme": True})

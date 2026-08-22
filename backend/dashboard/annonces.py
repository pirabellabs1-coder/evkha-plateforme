"""Les annonces, vues de l'administration : rédiger, relire, envoyer.

Une annonce touche TOUS les clients d'un seul geste. C'est ce qui la rend utile
— « le business plan arrive le mois prochain » se dit une fois — et c'est aussi
ce qui impose que l'envoi soit un geste distinct de la rédaction.

Tant qu'elle est en brouillon, elle n'existe pour personne : aucun courriel
n'est parti, rien ne s'affiche dans les espaces clients. `envoyer` est le seul
chemin qui la publie, et il ne se rejoue pas.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from organisations import courriels
from organisations.models import (
    Annonce,
    AnnonceVue,
    MembreOrganisation,
    StatutAnnonce,
    StatutOrganisation,
)

_log = logging.getLogger(__name__)

#: Destinations proposées par l'administration. Une LISTE FERMÉE, et c'est le
#: point : le champ envoie des clients quelque part, et une saisie libre
#: permettrait de les envoyer n'importe où — y compris hors du domaine.
DESTINATIONS: dict[str, str] = {
    "/espace": "Le tableau de bord",
    "/espace/commander": "Commander un document",
    "/espace/livrables": "Mes livrables",
    "/espace/achats": "Mes achats",
    "/espace/credits": "Crédits et abonnement",
}


def _refus(message: str, code: str, statut: int = 400) -> HttpResponse:
    return JsonResponse({"erreur": message, "code": code}, status=statut)


def _corps(request: HttpRequest) -> dict[str, Any]:
    try:
        charge = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return charge if isinstance(charge, dict) else {}


def _vue(annonce: Annonce) -> dict[str, Any]:
    return {
        "id": str(annonce.id),
        "titre": annonce.titre,
        "message": annonce.message,
        "lien_libelle": annonce.lien_libelle,
        "lien_cible": annonce.lien_cible,
        "statut": annonce.statut,
        "envoyee": annonce.est_envoyee,
        "envoyee_le": annonce.envoyee_le.isoformat() if annonce.envoyee_le else "",
        "courriels_envoyes": annonce.courriels_envoyes,
        "cree_le": annonce.created_at.isoformat(),
        # Combien de personnes l'ont ouverte. La seule mesure honnête de ce
        # qu'une annonce a produit — le nombre de courriels partis ne dit que
        # ce qu'on a tenté.
        "lue_par": annonce.vues.count(),
    }


def _destinataires() -> list[MembreOrganisation]:
    """Les membres à qui une annonce s'adresse.

    Les organisations SUSPENDUES en sont exclues : leur accès est fermé, et
    leur annoncer une nouveauté qu'elles ne peuvent pas atteindre serait au
    mieux inutile.

    Une adresse peut appartenir à deux organisations — un consultant présent
    chez deux agences. Elle ne reçoit qu'un courriel : c'est la même personne,
    et deux exemplaires du même message se lisent comme une erreur.
    """
    membres = (
        MembreOrganisation.objects.select_related("customer", "organisation")
        .exclude(organisation__statut=StatutOrganisation.SUSPENDUE)
        .order_by("created_at")
    )
    vus: set[str] = set()
    retenus: list[MembreOrganisation] = []
    for membre in membres:
        adresse = (membre.customer.email or "").strip().lower()
        if not adresse or adresse in vus:
            continue
        vus.add(adresse)
        retenus.append(membre)
    return retenus


@csrf_exempt
@require_http_methods(["GET", "POST"])
def annonces(request: HttpRequest) -> HttpResponse:
    """Liste les annonces, ou en rédige une."""
    if request.method == "GET":
        return JsonResponse({
            "annonces": [_vue(a) for a in Annonce.objects.all()],
            "destinations": [
                {"cible": cible, "libelle": libelle}
                for cible, libelle in DESTINATIONS.items()
            ],
            # Combien de personnes recevront la prochaine annonce. Affiché
            # AVANT l'envoi : on ne demande pas de confirmer un geste dont on
            # ignore la portée.
            "destinataires": len(_destinataires()),
        })

    charge = _corps(request)
    titre = str(charge.get("titre") or "").strip()
    message = str(charge.get("message") or "").strip()
    if not titre:
        return _refus("Donnez un titre : c'est l'objet du courriel.", "titre_manquant")
    if not message:
        return _refus("Écrivez le message à annoncer.", "message_manquant")

    annonce = Annonce.objects.create(
        titre=titre[:160],
        message=message,
        lien_libelle=str(charge.get("lien_libelle") or "").strip()[:60],
        lien_cible=_destination(charge.get("lien_cible")),
    )
    _log.info("Annonce redigee : %s", annonce.titre)
    return JsonResponse({"annonce": _vue(annonce)}, status=201)


def _destination(brut: Any) -> str:
    """La cible demandée, si elle fait partie des destinations connues.

    Tout le reste devient une chaîne vide, donc aucun bouton. Accepter un
    chemin libre reviendrait à laisser un formulaire d'administration envoyer
    les clients où bon lui semble.
    """
    cible = str(brut or "").strip()
    return cible if cible in DESTINATIONS else ""


@csrf_exempt
@require_http_methods(["POST", "DELETE"])
def annonce(request: HttpRequest, annonce_id: str) -> HttpResponse:
    """Modifie une annonce, ou la supprime."""
    cible = Annonce.objects.filter(id=annonce_id).first()
    if cible is None:
        return _refus("Cette annonce n'existe pas.", "annonce_inconnue", 404)

    if request.method == "DELETE":
        titre = cible.titre
        cible.delete()
        _log.info("Annonce supprimee : %s", titre)
        return JsonResponse({"supprimee": titre})

    if cible.est_envoyee:
        # Le courriel est parti, et l'annonce est affichée chez des clients qui
        # l'ont peut-être déjà lue. La modifier ferait deux versions d'un même
        # message, dont une déjà dans des boîtes aux lettres.
        return _refus(
            "Cette annonce a déjà été envoyée : elle ne peut plus être "
            "modifiée. Rédigez-en une nouvelle.",
            "annonce_envoyee",
            409,
        )

    charge = _corps(request)
    if "titre" in charge:
        cible.titre = str(charge["titre"]).strip()[:160]
    if "message" in charge:
        cible.message = str(charge["message"]).strip()
    if "lien_libelle" in charge:
        cible.lien_libelle = str(charge["lien_libelle"]).strip()[:60]
    if "lien_cible" in charge:
        cible.lien_cible = _destination(charge["lien_cible"])

    if not cible.titre or not cible.message:
        return _refus(
            "Une annonce a besoin d'un titre et d'un message.", "annonce_incomplete"
        )

    cible.save()
    return JsonResponse({"annonce": _vue(cible)})


@csrf_exempt
@require_http_methods(["POST"])
def envoyer(request: HttpRequest, annonce_id: str) -> HttpResponse:
    """Envoie l'annonce : courriel à tous, et affichage dans les espaces.

    ## L'ordre compte

    Le statut passe à « envoyée » AVANT le premier courriel. C'est délibéré :
    si l'envoi s'interrompt au milieu — service de courriel injoignable,
    conteneur redémarré —, l'annonce est déjà visible dans les espaces clients,
    et un second appel ne repartira pas du début pour réexpédier des courriels
    déjà reçus.

    Le prix de ce choix est assumé : une panne totale du service de courriel
    laisse une annonce affichée sans courriel parti. C'est l'inverse qui serait
    grave — des clients recevant deux fois le même message.
    """
    cible = Annonce.objects.filter(id=annonce_id).first()
    if cible is None:
        return _refus("Cette annonce n'existe pas.", "annonce_inconnue", 404)
    if cible.est_envoyee:
        return _refus(
            "Cette annonce a déjà été envoyée. Un second envoi ferait un "
            "doublon dans toutes les boîtes aux lettres.",
            "annonce_deja_envoyee",
            409,
        )
    if not cible.titre or not cible.message:
        return _refus(
            "Une annonce a besoin d'un titre et d'un message.", "annonce_incomplete"
        )

    destinataires = _destinataires()
    cible.statut = StatutAnnonce.ENVOYEE
    cible.envoyee_le = timezone.now()
    cible.save(update_fields=["statut", "envoyee_le", "updated_at"])

    lien = _adresse_du_lien(cible)
    bouton = cible.lien_libelle or "Ouvrir mon espace"
    partis = 0
    for membre in destinataires:
        if courriels.annoncer(
            destinataire=membre.customer.email,
            titre=cible.titre,
            message=cible.message,
            lien=lien,
            bouton=bouton,
        ):
            partis += 1

    cible.courriels_envoyes = partis
    cible.save(update_fields=["courriels_envoyes", "updated_at"])
    _log.info(
        "Annonce « %s » envoyee : %s courriels sur %s destinataires.",
        cible.titre, partis, len(destinataires),
    )
    return JsonResponse({
        "annonce": _vue(cible),
        "destinataires": len(destinataires),
        "courriels_envoyes": partis,
    })


def _adresse_du_lien(annonce_cible: Annonce) -> str:
    """L'adresse complète vers laquelle le bouton du courriel envoie.

    Lue dans les réglages : un domaine écrit ici survivrait à un déménagement
    et enverrait les clients sur une adresse morte.
    """
    from django.conf import settings  # noqa: PLC0415

    base = str(getattr(settings, "EVKHA_APP_URL", "") or "").rstrip("/")
    return f"{base}{annonce_cible.lien_cible or '/espace'}"


@require_http_methods(["GET"])
def lecteurs(request: HttpRequest, annonce_id: str) -> HttpResponse:
    """Qui a ouvert l'annonce. Utile pour savoir si le message est passé."""
    vues = (
        AnnonceVue.objects.filter(annonce_id=annonce_id)
        .select_related("membre__customer", "membre__organisation")
        .order_by("-created_at")[:200]
    )
    return JsonResponse({
        "lecteurs": [
            {
                "organisation": v.membre.organisation.raison_sociale,
                "email": v.membre.customer.email,
                "vue_le": v.created_at.isoformat(),
            }
            for v in vues
        ],
    })

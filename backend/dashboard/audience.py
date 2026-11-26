"""L'audience du site, pour la gérante : qui a pris quelle ressource, qui
est inscrit à la lettre — à l'écran et en fichier pour un tableur.

Ces réponses portent des adresses e-mail : ni cache, ni copie. La protection
est celle de tout `/api/dashboard/` (le jeton de l'administration).
"""
from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import datetime
from typing import Any

from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from audience.adresses import empreinte
from audience.models import Contact, Demande, Opposition, Origine
from catalog.suivi import cellule_sure

_log = logging.getLogger(__name__)

_LIBELLES = dict(Origine.choices)


def _sans_cache(reponse: HttpResponse) -> HttpResponse:
    reponse["Cache-Control"] = "no-store"
    return reponse


def _contacts() -> list[Contact]:
    return list(
        Contact.objects.prefetch_related(
            Prefetch("demandes", queryset=Demande.objects.order_by("created_at"))
        )
    )


def _vue(contact: Contact) -> dict[str, Any]:
    demandes = list(contact.demandes.all())
    origines = list(dict.fromkeys(d.origine for d in demandes))
    return {
        "id": str(contact.id),
        "email": contact.email,
        "premiere_demande_le": contact.created_at.isoformat(),
        "derniere_demande_le": (
            demandes[-1].created_at.isoformat() if demandes else contact.created_at.isoformat()
        ),
        "demandes": [_LIBELLES.get(o, o) for o in origines],
        "provenances": [d.provenance for d in demandes if d.provenance],
        "inscrit_a_la_lettre": contact.inscrit_a_la_lettre,
        "lettre_le": contact.lettre_le.isoformat() if contact.lettre_le else None,
        "desinscrit_le": contact.desinscrit_le.isoformat() if contact.desinscrit_le else None,
    }


@require_http_methods(["GET"])
def liste(request: HttpRequest) -> HttpResponse:
    contacts = [_vue(c) for c in _contacts()]
    return _sans_cache(
        JsonResponse(
            {
                "contacts": contacts,
                "total": len(contacts),
                "inscrits_a_la_lettre": sum(1 for c in contacts if c["inscrit_a_la_lettre"]),
            }
        )
    )


_COLONNES = [
    "Adresse e-mail",
    "Ressources et inscriptions",
    "Inscrit à la newsletter",
    "Inscription à la newsletter le",
    "Provenance (ajout par l'administration)",
    "Première demande",
    "Dernière demande",
]


def _jour(valeur: str | None) -> str:
    """La date à l'heure de Paris : une demande faite à 00:30 n'est pas de la
    veille (même choix que `catalog.suivi`)."""
    if not valeur:
        return ""
    return timezone.localtime(datetime.fromisoformat(valeur)).date().isoformat()


@require_http_methods(["GET"])
def liste_csv(request: HttpRequest) -> HttpResponse:
    """UTF-8 avec indicateur d'ordre des octets et `;` : ce qu'un Excel réglé
    en français ouvre sans retouche (même choix que `catalog.suivi.en_csv`).
    Chaque cellule passe par `cellule_sure` : une adresse commençant par `=`
    ne devient pas une formule.

    `?lettre=1` : les SEULS inscrits à la lettre — le fichier à importer dans
    l'outil d'envoi. Sans lui, l'export complet, téléchargeurs compris, qui
    n'ont pas consenti à recevoir la lettre."""
    seulement_la_lettre = request.GET.get("lettre") == "1"
    tampon = io.StringIO()
    ecrivain = csv.writer(tampon, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(_COLONNES)
    contacts = [_vue(c) for c in _contacts()]
    if seulement_la_lettre:
        contacts = [c for c in contacts if c["inscrit_a_la_lettre"]]
    for c in contacts:
        ecrivain.writerow(
            [
                cellule_sure(c["email"]),
                cellule_sure(", ".join(c["demandes"])),
                "oui" if c["inscrit_a_la_lettre"] else "non",
                _jour(c["lettre_le"]),
                cellule_sure(" ; ".join(c["provenances"])),
                _jour(c["premiere_demande_le"]),
                _jour(c["derniere_demande_le"]),
            ]
        )
    reponse = HttpResponse(
        ("﻿" + tampon.getvalue()).encode("utf-8"),
        content_type="text/csv; charset=utf-8",
    )
    nom = "newsletter-evkha-inscrits.csv" if seulement_la_lettre else "audience-evkha.csv"
    reponse["Content-Disposition"] = f'attachment; filename="{nom}"'
    _log.info("Audience exportée (%d contacts).", len(contacts))
    return _sans_cache(reponse)


@csrf_exempt
@require_http_methods(["POST"])
def desinscrire(request: HttpRequest, contact_id: str) -> HttpResponse:
    """Retire un contact de la lettre (à sa demande, transmise à la gérante).
    L'historique des demandes reste : il ne s'efface pas."""
    contact = Contact.objects.filter(pk=contact_id).first() if _uuid(contact_id) else None
    if contact is None:
        return JsonResponse({"erreur": "Contact introuvable.", "code": "introuvable"}, status=404)
    contact.desinscrire(timezone.now())
    return _sans_cache(JsonResponse({"contact": _vue(contact)}))


@csrf_exempt
@require_http_methods(["POST"])
def supprimer(request: HttpRequest, contact_id: str) -> HttpResponse:
    """Efface un contact ET ses demandes, à sa demande (RGPD, art. 17).
    Irréversible : l'écran demande confirmation. Rien n'est journalisé de
    l'adresse."""
    contact = Contact.objects.filter(pk=contact_id).first() if _uuid(contact_id) else None
    if contact is None:
        return JsonResponse({"erreur": "Contact introuvable.", "code": "introuvable"}, status=404)
    with transaction.atomic():
        Opposition.objects.get_or_create(empreinte=empreinte(contact.email))
        contact.delete()
    _log.info("Contact de l'audience effacé à sa demande.")
    return _sans_cache(JsonResponse({"supprime": True}))


def _uuid(valeur: str) -> bool:
    try:
        uuid.UUID(valeur)
    except ValueError:
        return False
    return True

"""Les deux formulaires publics de l'audience.

- `POST /api/public/ressources/` : `{email, ressource, lettre, site}` — note
  l'adresse et la demande, et rend le lien du PDF, que la page ouvre aussitôt ;
- `POST /api/public/lettre/` : `{email, site}` — inscrit à la lettre.

Publiques et sans compte : ce sont des formulaires du site vitrine. D'où :

- un plafond par adresse IP (`limitation.compter`), compté AVANT d'écrire —
  sur le préfixe /64 en IPv6, qui appartient à un seul abonné — et un
  plafond global, qui borne le pire cas quelles que soient les adresses ;
- du JSON seulement (415 sinon) : un `text/plain` est une requête « simple »
  qu'une page tierce peut faire poster par ses visiteurs, sans contrôle CORS ;
- une ligne par contact ET par origine : répéter une demande ne fait pas
  grossir la base ;
- une requête anonyme n'annule JAMAIS une désinscription (audit du
  25/11/2026) : une personne désinscrite qui veut revenir le demande à la
  gérante ;
- un champ piège `site`, invisible pour une personne : rempli, la requête
  rend la même réponse qu'un succès, sans rien écrire — un robot n'apprend
  rien ;
- AUCUNE fuite : la réponse ne dit jamais si l'adresse était déjà connue.

Le lien rendu est celui du fichier statique (`frontend/public/ressources/`) :
le formulaire récolte l'adresse, il ne protège pas un secret. Les deux PDF
sont gratuits.
"""
from __future__ import annotations

import ipaddress
import json
import logging
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from organisations import limitation

from .models import Contact, Demande, Origine, Ressource

_log = logging.getLogger(__name__)

#: Assez pour une famille derrière la même box, trop peu pour remplir la base.
INSCRIPTIONS_PAR_HEURE = limitation.Plafond("audience", maximum=20, fenetre_s=3600)
#: Toutes adresses confondues : très au-delà du trafic d'un site vitrine.
INSCRIPTIONS_GLOBALES_PAR_HEURE = limitation.Plafond(
    "audience-global", maximum=300, fenetre_s=3600
)

#: Le fichier de chaque ressource, servi par le site (`frontend/public/`).
FICHIERS: dict[str, str] = {
    Ressource.CHECKLIST: "/ressources/checklist-creer-sa-micro-entreprise-en-10-etapes.pdf",
    Ressource.LEXIQUE: "/ressources/lexique-evkha-de-l-entrepreneuriat.pdf",
}


def _refus(message: str, code: str, statut: int = 400) -> HttpResponse:
    return JsonResponse({"erreur": message, "code": code}, status=statut)


def cle_de_l_appelant(request: HttpRequest) -> str:
    """L'adresse IP du visiteur, ramenée à son /64 en IPv6 : un abonné en
    détient au moins 2^64, et compter l'adresse exacte ne plafonnerait rien."""
    brute = limitation.adresse_client(request)
    try:
        ip = ipaddress.ip_address(brute)
    except ValueError:
        return brute
    if ip.version == 6:
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    return str(ip)


def _plafond_atteint(request: HttpRequest) -> bool:
    """Le plafond de l'appelant d'abord : une salve venue d'une seule adresse
    s'y arrête, sans entamer le plafond global des autres visiteurs."""
    if not limitation.compter(INSCRIPTIONS_PAR_HEURE, cle_de_l_appelant(request)):
        return True
    return not limitation.compter(INSCRIPTIONS_GLOBALES_PAR_HEURE, "tout")


def _corps(request: HttpRequest) -> dict[str, Any] | None:
    try:
        charge = json.loads(request.body or b"{}")
    except (ValueError, RecursionError):
        return None
    return charge if isinstance(charge, dict) else None


def adresse_normalisee(brut: object) -> str | None:
    """L'adresse saisie, nettoyée et en minuscules, ou `None` si elle n'en est
    pas une. Minuscules : `Marie@Exemple.fr` et `marie@exemple.fr` sont la
    même personne, et la contrainte d'unicité doit le savoir."""
    if not isinstance(brut, str):
        return None
    adresse = brut.strip().lower()
    if not adresse or len(adresse) > 254:
        return None
    try:
        validate_email(adresse)
    except ValidationError:
        return None
    return adresse


def _robot(charge: dict[str, Any]) -> bool:
    piege = charge.get("site")
    return isinstance(piege, str) and piege.strip() != ""


def _trop() -> HttpResponse:
    return _refus(
        "Trop de demandes depuis votre connexion. Réessayez dans une heure.",
        "trop_de_demandes",
        429,
    )


def _noter(adresse: str, origine: str, lettre: bool) -> None:
    """Le contact (créé s'il est nouveau), sa demande — une par origine —, et
    son consentement à la lettre s'il l'a donné.

    Le consentement ne se pose qu'une fois : une inscription active garde sa
    date, et une DÉSINSCRIPTION n'est jamais annulée par une requête
    anonyme — sinon n'importe qui pourrait réinscrire l'adresse d'un tiers
    qui a demandé à partir."""
    with transaction.atomic():
        contact, _ = Contact.objects.select_for_update().get_or_create(email=adresse)
        if lettre and contact.lettre_le is None and contact.desinscrit_le is None:
            contact.lettre_le = timezone.now()
            contact.save(update_fields=["lettre_le", "updated_at"])
        Demande.objects.get_or_create(contact=contact, origine=origine)


@csrf_exempt
@require_POST
def ressource(request: HttpRequest) -> HttpResponse:
    if request.content_type != "application/json":
        return _refus("Format de requête refusé.", "format_refuse", 415)
    charge = _corps(request)
    if charge is None:
        return _refus("Requête illisible.", "corps_invalide")

    nom = charge.get("ressource")
    # Une liste ou un objet ne se cherchent pas dans un dict (non hachables) :
    # sans ce garde, `{"ressource": []}` levait une erreur 500.
    if not isinstance(nom, str) or nom not in FICHIERS:
        return _refus("Cette ressource n'existe pas.", "ressource_inconnue")
    lien = FICHIERS[nom]

    adresse = adresse_normalisee(charge.get("email"))
    if adresse is None:
        return _refus(
            "Indiquez une adresse e-mail valide.", "adresse_invalide"
        )

    if _robot(charge):
        return JsonResponse({"lien": lien})

    if _plafond_atteint(request):
        return _trop()

    _noter(adresse, nom, charge.get("lettre") is True)
    return JsonResponse({"lien": lien})


@csrf_exempt
@require_POST
def lettre(request: HttpRequest) -> HttpResponse:
    if request.content_type != "application/json":
        return _refus("Format de requête refusé.", "format_refuse", 415)
    charge = _corps(request)
    if charge is None:
        return _refus("Requête illisible.", "corps_invalide")

    adresse = adresse_normalisee(charge.get("email"))
    if adresse is None:
        return _refus(
            "Indiquez une adresse e-mail valide.", "adresse_invalide"
        )

    if _robot(charge):
        return JsonResponse({"inscrit": True})

    if _plafond_atteint(request):
        return _trop()

    _noter(adresse, Origine.LETTRE, lettre=True)
    return JsonResponse({"inscrit": True})

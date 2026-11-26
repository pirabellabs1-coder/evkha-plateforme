"""Les deux liens publics de la lettre : confirmer l'inscription, s'en aller.

Montés hors `/api/` (`/l/confirmation/<jeton>/`, `/l/desinscription/<jeton>/`),
sans compte. La désinscription se fait par le jeton opaque du contact ; la
confirmation par un jeton SIGNÉ, valable sept jours et pour une seule
demande. Aucun des deux ne porte de donnée personnelle lisible.

**Un GET n'écrit rien.** Les passerelles de messagerie et les antivirus
visitent les liens d'un courriel à sa réception (audit du 19/11/2026, vu sur
la prospection) : un lien qui agissait à la visite inscrirait ou désinscrirait
une personne qui n'a rien fait. La page DEMANDE, le bouton (POST) EXÉCUTE.
C'est aussi le POST qu'envoie le bouton « Se désinscrire » des messageries
(RFC 8058, en-tête `List-Unsubscribe-Post` posé par `lettre.envoi`).

Pas de jeton CSRF : aucune session ni cookie, donc aucune autorité ambiante
qu'un site tiers pourrait détourner ; le jeton du lien autorise l'acte.
"""
from __future__ import annotations

from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from audience.models import Contact

from .gabarit import contact_a_confirmer

_PAGE = (
    "<!doctype html><html lang=fr><head><meta charset=utf-8>"
    "<meta name=viewport content='width=device-width, initial-scale=1'>"
    "<meta name=robots content=noindex>"
    "<title>{titre} — EVKHA</title></head>"
    "<body style='font-family:system-ui,sans-serif;max-width:40rem;margin:4rem auto;"
    "padding:0 1rem;line-height:1.6;color:#1a1a1a'>"
    "<p style='font-weight:700;letter-spacing:3px'>EVKHA</p>{corps}"
    "<p style='margin-top:2rem'><a href='https://evkha.fr' style='color:#1a1a1a'>"
    "Retour au site</a></p></body></html>"
)

_BOUTON = (
    "display:inline-block;padding:.7rem 1.4rem;border:0;border-radius:8px;"
    "background:#1a1a1a;color:#fff;font:inherit;font-weight:600;cursor:pointer"
)


def _page(titre: str, corps: str, status: int = 200) -> HttpResponse:
    reponse = HttpResponse(
        _PAGE.format(titre=titre, corps=corps), status=status, content_type="text/html"
    )
    reponse["Cache-Control"] = "no-store"
    reponse["Referrer-Policy"] = "no-referrer"
    return reponse


def _introuvable() -> HttpResponse:
    return _page(
        "Lien introuvable",
        "<h1>Lien introuvable</h1><p>Ce lien n'est plus valide. Vous pouvez "
        "vous réinscrire depuis le site, ou nous écrire à contact@evkha.fr.</p>",
        status=404,
    )


def _formulaire(bouton: str) -> str:
    return (
        "<form method='post'>"
        f"<button type='submit' style='{_BOUTON}'>{bouton}</button></form>"
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def confirmation(request: HttpRequest, jeton: str) -> HttpResponse:
    """Le jeton est SIGNÉ et daté (`gabarit.jeton_de_confirmation`) : valable
    sept jours, et pour la seule demande en cours."""
    contact = contact_a_confirmer(jeton)
    if contact is None:
        return _page(
            "Lien expiré",
            "<h1>Ce lien n'est plus valable</h1><p>Il a expiré ou a déjà servi. "
            "Pour recevoir la newsletter, inscrivez-vous à nouveau depuis le site : "
            "un nouveau lien vous sera envoyé.</p>",
            status=404,
        )
    if contact.inscrit_a_la_lettre:
        return _page(
            "Inscription confirmée",
            "<h1>Votre inscription est confirmée</h1><p>Vous recevrez la "
            "prochaine newsletter d'EVKHA à cette adresse.</p>",
        )
    if request.method == "POST":
        with transaction.atomic():
            verrou = Contact.objects.select_for_update().get(pk=contact.pk)
            if not verrou.inscrit_a_la_lettre:
                verrou.confirmer(timezone.now())
        return _page(
            "Inscription confirmée",
            "<h1>Merci, votre inscription est confirmée</h1><p>Vous recevrez la "
            "newsletter d'EVKHA à cette adresse. Chaque message porte un lien pour "
            "vous désinscrire en un clic.</p>",
        )
    return _page(
        "Confirmer l'inscription",
        "<h1>Confirmez votre inscription</h1><p>Un clic, et vous recevrez la "
        "newsletter d'EVKHA à cette adresse.</p>"
        + _formulaire("Confirmer mon inscription")
        + "<p style='color:#666;font-size:.9rem'>Tant que vous n'avez pas "
        "confirmé, rien n'est enregistré.</p>",
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def desinscription(request: HttpRequest, jeton: str) -> HttpResponse:
    contact = Contact.objects.filter(jeton=jeton).first()
    if contact is None:
        return _introuvable()
    if request.method == "POST":
        with transaction.atomic():
            verrou = Contact.objects.select_for_update().get(pk=contact.pk)
            verrou.desinscrire(timezone.now())
        return _page(
            "Désinscription faite",
            "<h1>Vous êtes désinscrit·e</h1><p>Vous ne recevrez plus la newsletter "
            "d'EVKHA. Aucune autre démarche n'est nécessaire.</p>",
        )
    if not contact.inscrit_a_la_lettre and contact.confirmation_demandee_le is None:
        return _page(
            "Déjà désinscrit·e",
            "<h1>Vous êtes déjà désinscrit·e</h1><p>Cette adresse ne reçoit "
            "plus la newsletter d'EVKHA.</p>",
        )
    return _page(
        "Se désinscrire",
        "<h1>Confirmez votre désinscription</h1><p>Vous ne recevrez plus la "
        "newsletter d'EVKHA.</p>"
        + _formulaire("Me désinscrire")
        + "<p style='color:#666;font-size:.9rem'>Tant que vous n'avez pas "
        "confirmé, rien n'est modifié.</p>",
    )

"""Espace admin — prospection (phase 2 : les écrans).

Routes sous `/api/dashboard/prospection/…`, donc protégées par le jeton admin
(`DashboardAuthMiddleware`). Elles pilotent le sous-système `prospection` :
campagnes, prospects, séquence de relances, et la FILE DE VALIDATION des
messages. L'envoi passe TOUJOURS par `prospection.services`, qui refuse tout
message non validé — ces vues ne contournent jamais l'invariant.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods
from prospection import services
from prospection.models import (
    Campagne,
    Evenement,
    Message,
    Prospect,
    Sequence,
    StatutMessage,
    StatutProspect,
    TypeEvenement,
)

_log = logging.getLogger(__name__)


def _json(data: Any, status: int = 200) -> JsonResponse:
    return JsonResponse(data, status=status, safe=False)


def _erreur(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"erreur": message}, status=status)


def _corps(request: HttpRequest) -> dict[str, Any]:
    try:
        charge = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, ValueError):
        return {}
    return charge if isinstance(charge, dict) else {}


# ── Sérialisation ────────────────────────────────────────────────────────────


def _campagne_dict(c: Campagne) -> dict[str, Any]:
    return {
        "id": str(c.id), "nom": c.nom, "secteur": c.secteur, "zone": c.zone,
        "offre_visee": c.offre_visee, "statut": c.statut, "notes": c.notes,
        "cree_par": c.cree_par, "cree_le": c.created_at.isoformat(),
        "prospects": c.prospects.count(),
    }


def _prospect_dict(p: Prospect, *, avec_messages: bool = False) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": str(p.id), "campagne_id": str(p.campagne_id) if p.campagne_id else None,
        "raison_sociale": p.raison_sociale, "secteur": p.secteur, "zone": p.zone,
        "email": p.email, "nom_contact": p.nom_contact, "fonction": p.fonction,
        "site_web": p.site_web, "source": p.source, "statut": p.statut,
        "score_adequation": p.score_adequation, "raison_score": p.raison_score,
        "contactable": p.contactable,
        "desinscrit_le": p.desinscrit_le and p.desinscrit_le.isoformat(),
        "notes": p.notes, "cree_le": p.created_at.isoformat(),
    }
    if avec_messages:
        d["messages"] = [_message_dict(m) for m in p.messages.all()]
    return d


def _message_dict(m: Message) -> dict[str, Any]:
    return {
        "id": str(m.id), "prospect_id": str(m.prospect_id),
        "campagne_id": str(m.campagne_id) if m.campagne_id else None,
        "sequence_id": str(m.sequence_id) if m.sequence_id else None,
        "objet": m.objet, "corps": m.corps, "statut": m.statut,
        "valide_par": m.valide_par, "valide_le": m.valide_le and m.valide_le.isoformat(),
        "programme_pour": m.programme_pour and m.programme_pour.isoformat(),
        "envoye_le": m.envoye_le and m.envoye_le.isoformat(),
        "provider_message_id": m.provider_message_id, "error_message": m.error_message,
        "envoyable": m.envoyable, "cree_le": m.created_at.isoformat(),
    }


def _sequence_dict(s: Sequence) -> dict[str, Any]:
    return {
        "id": str(s.id), "ordre": s.ordre, "delai_jours": s.delai_jours,
        "est_une_relance": s.est_une_relance,
        "objet_gabarit": s.objet_gabarit, "corps_gabarit": s.corps_gabarit,
    }


# ── Aperçu ───────────────────────────────────────────────────────────────────


@require_GET
@csrf_exempt
def apercu(request: HttpRequest) -> JsonResponse:
    """Les compteurs de l'écran d'accueil de la prospection."""
    par_statut = {s: Prospect.objects.filter(statut=s).count() for s, _ in StatutProspect.choices}
    return _json({
        "campagnes_actives": Campagne.objects.filter(statut="active").count(),
        "prospects": Prospect.objects.count(),
        "prospects_par_statut": par_statut,
        "a_valider": Message.objects.filter(statut=StatutMessage.BROUILLON).count(),
        "valides_en_attente": Message.objects.filter(statut=StatutMessage.VALIDE).count(),
        "envoyes": Message.objects.filter(statut=StatutMessage.ENVOYE).count(),
    })


# ── Campagnes ────────────────────────────────────────────────────────────────


@csrf_exempt
@require_http_methods(["GET", "POST"])
def campagnes(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return _json([_campagne_dict(c) for c in Campagne.objects.all()[:200]])
    corps = _corps(request)
    nom = str(corps.get("nom") or "").strip()
    if not nom:
        return _erreur("Le nom de la campagne est obligatoire.")
    c = Campagne.objects.create(
        nom=nom, secteur=str(corps.get("secteur") or ""), zone=str(corps.get("zone") or ""),
        offre_visee=str(corps.get("offre_visee") or ""), notes=str(corps.get("notes") or ""),
        cree_par=str(corps.get("cree_par") or "administrateur"),
    )
    return _json(_campagne_dict(c), status=201)


@csrf_exempt
@require_http_methods(["GET"])
def campagne_detail(request: HttpRequest, campagne_id: str) -> JsonResponse:
    try:
        c = Campagne.objects.get(id=campagne_id)
    except (Campagne.DoesNotExist, ValueError):
        return _erreur("Campagne introuvable.", status=404)
    return _json({
        **_campagne_dict(c),
        "sequence": [_sequence_dict(s) for s in c.sequence.all()],
        "prospects_liste": [_prospect_dict(p) for p in c.prospects.all()[:500]],
    })


@csrf_exempt
@require_http_methods(["PUT"])
def campagne_sequence(request: HttpRequest, campagne_id: str) -> JsonResponse:
    """Définit la séquence d'une campagne : le 1ᵉʳ mail (ordre 0) et ses relances.

    Remplace la séquence en bloc (`etapes` = liste ordonnée). On attend au moins
    le premier message ; la cliente a demandé quatre ou cinq relances.
    """
    try:
        c = Campagne.objects.get(id=campagne_id)
    except (Campagne.DoesNotExist, ValueError):
        return _erreur("Campagne introuvable.", status=404)
    etapes = _corps(request).get("etapes")
    if not isinstance(etapes, list) or not etapes:
        return _erreur("`etapes` doit être une liste non vide (au moins le premier message).")
    c.sequence.all().delete()
    creees = [
        Sequence.objects.create(
            campagne=c, ordre=i,
            delai_jours=int(e.get("delai_jours") or 0),
            objet_gabarit=str(e.get("objet_gabarit") or ""),
            corps_gabarit=str(e.get("corps_gabarit") or ""),
        )
        for i, e in enumerate(etapes) if isinstance(e, dict)
    ]
    return _json([_sequence_dict(s) for s in creees], status=200)


# ── Prospects ────────────────────────────────────────────────────────────────


@csrf_exempt
@require_http_methods(["GET", "POST"])
def prospects(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        qs = Prospect.objects.all()
        if campagne_id := request.GET.get("campagne"):
            qs = qs.filter(campagne_id=campagne_id)
        if statut := request.GET.get("statut"):
            qs = qs.filter(statut=statut)
        return _json([_prospect_dict(p) for p in qs[:500]])
    corps = _corps(request)
    raison = str(corps.get("raison_sociale") or "").strip()
    if not raison:
        return _erreur("La raison sociale est obligatoire.")
    campagne = None
    if cid := corps.get("campagne_id"):
        campagne = Campagne.objects.filter(id=cid).first()
    p = Prospect.objects.create(
        campagne=campagne, raison_sociale=raison,
        secteur=str(corps.get("secteur") or ""), zone=str(corps.get("zone") or ""),
        email=str(corps.get("email") or ""), nom_contact=str(corps.get("nom_contact") or ""),
        fonction=str(corps.get("fonction") or ""), site_web=str(corps.get("site_web") or ""),
        source=str(corps.get("source") or "manuel"), notes=str(corps.get("notes") or ""),
    )
    return _json(_prospect_dict(p), status=201)


@csrf_exempt
@require_http_methods(["GET"])
def prospect_detail(request: HttpRequest, prospect_id: str) -> JsonResponse:
    try:
        p = Prospect.objects.get(id=prospect_id)
    except (Prospect.DoesNotExist, ValueError):
        return _erreur("Prospect introuvable.", status=404)
    return _json(_prospect_dict(p, avec_messages=True))


@csrf_exempt
@require_http_methods(["POST"])
def prospect_desinscrire(request: HttpRequest, prospect_id: str) -> JsonResponse:
    try:
        p = Prospect.objects.get(id=prospect_id)
    except (Prospect.DoesNotExist, ValueError):
        return _erreur("Prospect introuvable.", status=404)
    services.desinscrire(p)
    return _json(_prospect_dict(p))


# ── Messages : la file de validation ─────────────────────────────────────────


@csrf_exempt
@require_http_methods(["GET", "POST"])
def messages(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        qs = Message.objects.select_related("prospect").all()
        if statut := request.GET.get("statut"):
            qs = qs.filter(statut=statut)
        if prospect_id := request.GET.get("prospect"):
            qs = qs.filter(prospect_id=prospect_id)
        if campagne_id := request.GET.get("campagne"):
            qs = qs.filter(campagne_id=campagne_id)
        return _json([_message_dict(m) for m in qs[:500]])
    corps = _corps(request)
    try:
        prospect = Prospect.objects.get(id=str(corps.get("prospect_id") or ""))
    except (Prospect.DoesNotExist, ValueError):
        return _erreur("Prospect introuvable.", status=404)
    objet, texte = str(corps.get("objet") or "").strip(), str(corps.get("corps") or "").strip()
    if not objet or not texte:
        return _erreur("L'objet et le corps du message sont obligatoires.")
    sequence = None
    if sid := corps.get("sequence_id"):
        sequence = Sequence.objects.filter(id=sid).first()
    m = Message.objects.create(
        prospect=prospect, campagne=prospect.campagne, sequence=sequence,
        objet=objet, corps=texte,
    )
    return _json(_message_dict(m), status=201)


def _message_ou_404(message_id: str) -> Message | None:
    try:
        return Message.objects.select_related("prospect").get(id=message_id)
    except (Message.DoesNotExist, ValueError):
        return None


@csrf_exempt
@require_http_methods(["PUT"])
def message_detail(request: HttpRequest, message_id: str) -> JsonResponse:
    """Édite un brouillon (objet/corps) : Evangéline retouche avant de valider."""
    m = _message_ou_404(message_id)
    if m is None:
        return _erreur("Message introuvable.", status=404)
    if m.statut != StatutMessage.BROUILLON:
        return _erreur("Seul un brouillon se modifie ; revalidez après coup.", status=409)
    corps = _corps(request)
    if "objet" in corps:
        m.objet = str(corps.get("objet") or "").strip() or m.objet
    if "corps" in corps:
        m.corps = str(corps.get("corps") or "").strip() or m.corps
    m.save(update_fields=["objet", "corps", "updated_at"])
    return _json(_message_dict(m))


@csrf_exempt
@require_http_methods(["POST"])
def message_valider(request: HttpRequest, message_id: str) -> JsonResponse:
    m = _message_ou_404(message_id)
    if m is None:
        return _erreur("Message introuvable.", status=404)
    par = str(_corps(request).get("par") or "").strip() or "administrateur"
    try:
        services.valider_message(m, par=par)
    except services.EnvoiRefuseError as refus:
        return _erreur(str(refus), status=409)
    return _json(_message_dict(m))


@csrf_exempt
@require_http_methods(["POST"])
def message_envoyer(request: HttpRequest, message_id: str) -> JsonResponse:
    """Envoie un message DÉJÀ validé. Refuse tout le reste (l'invariant du système)."""
    m = _message_ou_404(message_id)
    if m is None:
        return _erreur("Message introuvable.", status=404)
    try:
        services.envoyer_message(m)
    except services.EnvoiRefuseError as refus:
        return _erreur(str(refus), status=409)
    return _json(_message_dict(m))


@csrf_exempt
@require_http_methods(["POST"])
def message_annuler(request: HttpRequest, message_id: str) -> JsonResponse:
    m = _message_ou_404(message_id)
    if m is None:
        return _erreur("Message introuvable.", status=404)
    try:
        services.annuler_message(m)
    except services.EnvoiRefuseError as refus:
        return _erreur(str(refus), status=409)
    return _json(_message_dict(m))


@require_GET
@csrf_exempt
def message_evenements(request: HttpRequest, message_id: str) -> JsonResponse:
    """Les événements d'un message (ouvert, cliqué, répondu…) — source des métriques."""
    m = _message_ou_404(message_id)
    if m is None:
        return _erreur("Message introuvable.", status=404)
    evenements = [
        {"type": e.type, "horodatage": e.horodatage.isoformat(), "charge": e.charge}
        for e in Evenement.objects.filter(message=m)
    ]
    types = {t for t, _ in TypeEvenement.choices}
    resume = {t: sum(1 for e in evenements if e["type"] == t) for t in types}
    return _json({"evenements": evenements, "resume": resume})


# ── Les agents (phase 3) : recherche, qualification, rédaction ────────────────
#
# Ces trois actions appellent le modèle (et, pour la recherche, la recherche
# web). En production, c'est un COÛT réel — le même garde-fou que pour les
# générations : rien ne tourne sans un acte délibéré. D'où `confirmer: true`
# obligatoire dans le corps ; sans lui l'action est refusée et RIEN n'est appelé.
# Les agents, eux, ne font que PRÉPARER : la recherche crée des fiches, la
# qualification pose un score, la rédaction crée des BROUILLONS. Aucun n'envoie.


def _confirme(request: HttpRequest) -> bool:
    return _corps(request).get("confirmer") is True


def _confirmation_requise(action: str) -> JsonResponse:
    return JsonResponse(
        {
            "erreur": (
                f"L'action « {action} » appelle le modèle et coûte en production. "
                "Relancez avec `confirmer: true` pour l'autoriser."
            ),
            "confirmation_requise": True,
        },
        status=400,
    )


@csrf_exempt
@require_http_methods(["POST"])
def campagne_rechercher(request: HttpRequest, campagne_id: str) -> JsonResponse:
    """Agent de recherche : propose des prospects pour la campagne (fiches, rien d'envoyé)."""
    try:
        c = Campagne.objects.get(id=campagne_id)
    except (Campagne.DoesNotExist, ValueError):
        return _erreur("Campagne introuvable.", status=404)
    if not _confirme(request):
        return _confirmation_requise("recherche de prospects")
    from prospection import agents  # noqa: PLC0415

    limite = int(_corps(request).get("limite") or 10)
    crees = agents.rechercher_des_prospects(c, limite=limite)
    return _json({"crees": len(crees), "prospects": [_prospect_dict(p) for p in crees]})


@csrf_exempt
@require_http_methods(["POST"])
def prospect_qualifier(request: HttpRequest, prospect_id: str) -> JsonResponse:
    """Agent de qualification : pose le score d'abonnement du prospect."""
    try:
        p = Prospect.objects.get(id=prospect_id)
    except (Prospect.DoesNotExist, ValueError):
        return _erreur("Prospect introuvable.", status=404)
    if not _confirme(request):
        return _confirmation_requise("qualification")
    from prospection import agents  # noqa: PLC0415

    agents.qualifier_un_prospect(p)
    return _json(_prospect_dict(p))


@csrf_exempt
@require_http_methods(["POST"])
def prospect_rediger(request: HttpRequest, prospect_id: str) -> JsonResponse:
    """Agent de rédaction : prépare le 1ᵉʳ message et les relances, EN BROUILLON."""
    try:
        p = Prospect.objects.get(id=prospect_id)
    except (Prospect.DoesNotExist, ValueError):
        return _erreur("Prospect introuvable.", status=404)
    if not _confirme(request):
        return _confirmation_requise("rédaction des messages")
    from prospection import agents  # noqa: PLC0415

    corps = _corps(request)
    crees = agents.rediger_les_messages(
        p,
        nb_relances=int(corps.get("nb_relances") or 4),
        remplacer=corps.get("remplacer") is True,
    )
    return _json({"crees": len(crees), "messages": [_message_dict(m) for m in crees]})

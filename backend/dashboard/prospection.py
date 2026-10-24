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
from collections.abc import Callable
from typing import Any

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods
from prospection import services
from prospection.models import (
    Campagne,
    Conversation,
    Evenement,
    Message,
    MessageConversation,
    Prospect,
    ReglageAutomatisation,
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


def _taux(numerateur: int, denominateur: int) -> float:
    """Un taux en pourcentage, arrondi, ou 0 quand il n'y a rien à diviser."""
    return round(100 * numerateur / denominateur, 1) if denominateur else 0.0


@require_GET
@csrf_exempt
def metriques(request: HttpRequest) -> JsonResponse:
    """Les métriques de la prospection, recalculées à partir des `Evenement`.

    Une seule source de vérité : aucun taux n'est stocké, tout se recompte depuis
    les événements, donc un recompte donne toujours le même chiffre. Les
    « ouvertures » comptent les MESSAGES ouverts au moins une fois (uniques) ;
    « ouvertures_total » compte tous les événements d'ouverture (réouvertures
    comprises). Filtrable par `?campagne=`.
    """
    msgs = Message.objects.all()
    evts = Evenement.objects.all()
    if campagne_id := request.GET.get("campagne"):
        msgs = msgs.filter(campagne_id=campagne_id)
        evts = evts.filter(message__campagne_id=campagne_id)
        prospects = Prospect.objects.filter(campagne_id=campagne_id)
    else:
        prospects = Prospect.objects.all()

    envoyes = msgs.filter(statut=StatutMessage.ENVOYE).count()

    def _uniques(type_evt: str) -> int:
        return evts.filter(type=type_evt).values("message_id").distinct().count()

    ouverts = _uniques(TypeEvenement.OUVERT)
    cliques = _uniques(TypeEvenement.CLIQUE)
    repondu = _uniques(TypeEvenement.REPONDU)
    contactes = prospects.exclude(statut=StatutProspect.NOUVEAU).exclude(
        statut=StatutProspect.QUALIFIE
    ).count()
    convertis = prospects.filter(statut=StatutProspect.CONVERTI).count()
    desinscrits = prospects.filter(statut=StatutProspect.DESINSCRIT).count()

    return _json({
        "envoyes": envoyes,
        "ouvertures": ouverts,
        "ouvertures_total": evts.filter(type=TypeEvenement.OUVERT).count(),
        "taux_ouverture": _taux(ouverts, envoyes),
        "clics": cliques,
        "taux_clic": _taux(cliques, envoyes),
        "reponses": repondu,
        "taux_reponse": _taux(repondu, envoyes),
        "rebonds": _uniques(TypeEvenement.REBOND),
        "desinscriptions": desinscrits,
        "prospects_contactes": contactes,
        "conversions": convertis,
        "taux_conversion": _taux(convertis, contactes),
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


@csrf_exempt
@require_http_methods(["POST"])
def prospect_statut(request: HttpRequest, prospect_id: str) -> JsonResponse:
    """Fait avancer un prospect dans le pipeline (a répondu, converti, exclu…).

    C'est l'acte humain qui classe un prospect selon ce qu'il devient : une
    réponse reçue, une conversion, une exclusion. La désinscription passe par le
    service (elle annule aussi les messages en file) ; les autres états se
    posent directement.
    """
    try:
        p = Prospect.objects.get(id=prospect_id)
    except (Prospect.DoesNotExist, ValueError):
        return _erreur("Prospect introuvable.", status=404)
    vise = str(_corps(request).get("statut") or "")
    valides = {s for s, _ in StatutProspect.choices}
    if vise not in valides:
        return _erreur(f"Statut inconnu : « {vise} ».")
    if vise == StatutProspect.DESINSCRIT:
        services.desinscrire(p)
    else:
        p.statut = vise
        p.save(update_fields=["statut", "updated_at"])
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


def _executer_agent(
    action: str, fn: Callable[[], Any]
) -> tuple[Any, JsonResponse | None]:
    """Exécute un agent (appel modèle/recherche) et NOMME toute panne IA.

    Une erreur de l'API Claude — crédits épuisés, quota, réseau — n'est pas un
    bug du logiciel. La laisser remonter rendait un 500 nu sous le bouton, sans
    dire à la cliente ce qui se passe ni quoi faire : c'est exactement ce qui est
    arrivé le 24/10/2026, « credit balance is too low » transformé en « Server
    Error (500) ». On la capte, on la journalise EN ENTIER, et on rend un message
    lisible (règle 1 : échouer, mais à voix haute). Rien n'est créé en cas de
    panne — l'agent ne touche la base qu'après l'appel modèle réussi.
    """
    try:
        return fn(), None
    except Exception as exc:  # noqa: BLE001 — aucune panne d'agent ne doit rendre un 500 nu
        _log.exception("Agent « %s » en échec", action)
        credits_epuises = "credit balance is too low" in str(exc).lower()
        message = (
            "Crédits IA épuisés : rechargez le compte Anthropic (Plans & Billing) "
            "avant de relancer cette action."
            if credits_epuises
            else f"Le service IA n'a pas pu exécuter « {action} ». Réessayez plus tard."
        )
        return None, _erreur(message, status=502)


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

    corps = _corps(request)
    limite = int(corps.get("limite") or 10)
    criteres = str(corps.get("criteres") or "")
    crees, err = _executer_agent(
        "recherche de prospects",
        lambda: agents.rechercher_des_prospects(c, limite=limite, criteres=criteres),
    )
    if err is not None:
        return err
    return _json({"crees": len(crees), "prospects": [_prospect_dict(p) for p in crees]})


def _conversation_dict(c: Conversation, *, avec_messages: bool = False) -> dict[str, Any]:
    d: dict[str, Any] = {
        "id": str(c.id), "titre": c.titre,
        "campagne_id": str(c.campagne_id) if c.campagne_id else None,
        "cree_par": c.cree_par, "maj_le": c.updated_at.isoformat(),
        "nb_messages": c.messages.count(),
    }
    if avec_messages:
        d["messages"] = [
            {"role": m.role, "content": m.contenu, "le": m.created_at.isoformat()}
            for m in c.messages.all()
        ]
    return d


@require_GET
@csrf_exempt
def conversations(request: HttpRequest) -> JsonResponse:
    """Les discussions gardées en mémoire (les plus récentes d'abord)."""
    qs = Conversation.objects.all()
    if cid := request.GET.get("campagne"):
        qs = qs.filter(campagne_id=cid)
    return _json([_conversation_dict(c) for c in qs[:100]])


@require_GET
@csrf_exempt
def conversation_detail(request: HttpRequest, conversation_id: str) -> JsonResponse:
    """Une discussion et tout son historique — pour la rouvrir et la continuer."""
    try:
        c = Conversation.objects.get(id=conversation_id)
    except (Conversation.DoesNotExist, ValueError):
        return _erreur("Discussion introuvable.", status=404)
    return _json(_conversation_dict(c, avec_messages=True))


def _reglage_dict(r: ReglageAutomatisation) -> dict[str, Any]:
    return {
        "active": r.active,
        "prospects_par_jour": r.prospects_par_jour,
        "campagne_id": str(r.campagne_id) if r.campagne_id else None,
        "jours": [int(j) for j in r.jours.split(",") if j.strip().isdigit()],
        "derniere_execution": r.derniere_execution and r.derniere_execution.isoformat(),
    }


@csrf_exempt
@require_http_methods(["GET", "PUT"])
def automatisation(request: HttpRequest) -> JsonResponse:
    """Les réglages de la prospection automatique quotidienne (lire / modifier).

    Désactivée par défaut. L'activer lance, chaque jour, la recherche + la
    qualification + la préparation des e-mails (facturé) ; rien ne part sans
    validation. La désactiver arrête tout. Garde-fou : au plus 50 prospects/jour.
    """
    r = ReglageAutomatisation.charger()
    if request.method == "GET":
        return _json(_reglage_dict(r))
    corps = _corps(request)
    if "active" in corps:
        r.active = bool(corps.get("active"))
    if "prospects_par_jour" in corps:
        r.prospects_par_jour = max(1, min(int(corps.get("prospects_par_jour") or 20), 50))
    if "campagne_id" in corps:
        cid = corps.get("campagne_id")
        r.campagne = Campagne.objects.filter(id=cid).first() if cid else None
    if "jours" in corps and isinstance(corps.get("jours"), list):
        valides = [int(j) for j in corps["jours"] if str(j).isdigit() and 0 <= int(j) <= 6]
        r.jours = ",".join(str(j) for j in valides)
    if "cree_par" in corps:
        r.cree_par = str(corps.get("cree_par") or "")
    # Refus clair : activer sans campagne ne prospecterait rien.
    if r.active and r.campagne is None:
        return _erreur("Choisissez une campagne avant d'activer l'automatisation.")
    r.save()
    return _json(_reglage_dict(r))


@csrf_exempt
@require_http_methods(["POST"])
def assistant(request: HttpRequest) -> JsonResponse:
    """L'assistant conversationnel : discuter pour affiner la cible.

    La discussion est GARDÉE EN MÉMOIRE (modèle `Conversation`) : on envoie un
    seul `message`, le serveur relit tout l'historique, répond, et enregistre le
    tour de l'humain ET celui de l'assistant. Sans `conversation_id`, une
    nouvelle discussion s'ouvre. Pas de garde `confirmer` (c'est l'usage attendu
    d'un assistant ; seul le LANCEMENT d'une recherche est facturé et confirmé).
    """
    corps = _corps(request)
    texte = str(corps.get("message") or "").strip()
    if not texte:
        return _erreur("`message` est obligatoire.")

    campagne = None
    if cid := corps.get("campagne_id"):
        campagne = Campagne.objects.filter(id=cid).first()

    conv = None
    if conv_id := corps.get("conversation_id"):
        conv = Conversation.objects.filter(id=conv_id).first()
    if conv is None:
        conv = Conversation.objects.create(
            campagne=campagne, titre=texte[:200],
            cree_par=str(corps.get("cree_par") or "administrateur"),
        )

    historique = [
        {"role": m.role, "content": m.contenu} for m in conv.messages.all()
    ]
    historique.append({"role": "user", "content": texte})

    from prospection import assistant as agent_assistant  # noqa: PLC0415

    reponse = agent_assistant.repondre(historique, campagne=conv.campagne)

    MessageConversation.objects.create(conversation=conv, role="user", contenu=texte)
    MessageConversation.objects.create(
        conversation=conv, role="assistant", contenu=reponse["reponse"]
    )
    conv.save(update_fields=["updated_at"])  # remonte en tête de liste

    return _json({
        "conversation_id": str(conv.id),
        **reponse,
        "messages": _conversation_dict(conv, avec_messages=True)["messages"],
    })


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

    _, err = _executer_agent("qualification", lambda: agents.qualifier_un_prospect(p))
    if err is not None:
        return err
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
    crees, err = _executer_agent(
        "rédaction des messages",
        lambda: agents.rediger_les_messages(
            p,
            nb_relances=int(corps.get("nb_relances") or 4),
            remplacer=corps.get("remplacer") is True,
        ),
    )
    if err is not None:
        return err
    return _json({"crees": len(crees), "messages": [_message_dict(m) for m in crees]})

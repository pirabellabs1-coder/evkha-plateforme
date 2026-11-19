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
import uuid
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods
from prospection import services
from prospection.agents import _MAX_PROSPECTS_PAR_RECHERCHE
from prospection.file import Place, place, places
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
    normaliser_adresse,
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


def _entier(valeur: object, defaut: int) -> int:
    """Un entier lu dans le corps d'une requête, ou `defaut` s'il est illisible.

    `int(corps.get(...))` sur une saisie rendait un 500 dès qu'elle n'était pas
    un nombre (audit du 19/11/2026) : une entrée cliente ne lève pas.
    """
    if isinstance(valeur, bool):
        return defaut
    if isinstance(valeur, int):
        return valeur
    if isinstance(valeur, float):
        # `json.loads` accepte `Infinity` et `NaN` : ni l'un ni l'autre n'est un entier.
        return int(valeur) if valeur == valeur and abs(valeur) != float("inf") else defaut
    if isinstance(valeur, str) and valeur.strip().lstrip("-").isdigit():
        return int(valeur.strip())
    return defaut


def _champ(corps: dict[str, Any], cle: str, longueur: int = 200) -> str:
    """Un champ texte du corps, nettoyé et BORNÉ à la taille de sa colonne.

    PostgreSQL refuse une valeur plus longue que la colonne (SQLite, non) : sans
    borne, une saisie trop longue rendait un 500 en production seulement.
    """
    valeur = corps.get(cle)
    return str(valeur).strip()[:longueur] if isinstance(valeur, (str, int, float)) else ""


def _adresse_saisie(corps: dict[str, Any]) -> tuple[str, JsonResponse | None]:
    """L'adresse saisie, normalisée et VALIDÉE — ou le refus à rendre.

    Audit du 19/11/2026 : la création manuelle enregistrait telle quelle la
    chaîne reçue. Vide reste permis (une fiche se crée avant qu'on ait trouvé
    son adresse) ; non vide, elle doit avoir la forme d'une adresse.
    """
    brut = corps.get("email")
    if brut is None or (isinstance(brut, str) and not brut.strip()):
        return "", None
    # On valide la saisie TELLE QUELLE (aux espaces de bord près), puis on
    # normalise : normaliser d'abord retirerait les espaces intérieurs et
    # ferait passer « a b@c.fr x » pour l'adresse « ab@c.frx ».
    saisie = brut.strip() if isinstance(brut, str) else ""
    try:
        validate_email(saisie)
    except ValidationError:
        return "", _erreur(f"« {brut} » n'a pas la forme d'une adresse e-mail.")
    return normaliser_adresse(saisie), None


# ── Sérialisation ────────────────────────────────────────────────────────────


def _campagne_dict(c: Campagne) -> dict[str, Any]:
    return {
        "id": str(c.id), "nom": c.nom, "secteur": c.secteur, "zone": c.zone,
        "offre_visee": c.offre_visee, "statut": c.statut, "notes": c.notes,
        "cree_par": c.cree_par, "cree_le": c.created_at.isoformat(),
        "prospects": c.prospects.count(),
    }


def _prospect_dict(
    p: Prospect,
    *,
    avec_messages: bool = False,
    interdites: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """La fiche telle que l'écran la lit.

    `contactable` vient de `services.motif_de_non_contact`, LA définition
    (règle 5) : opposition de l'adresse — même posée sur une autre fiche —,
    rebond définitif, réponse reçue, exclusion, adresse absente. L'écran
    affiche `motif_non_contact` au lieu de laisser deviner.

    `interdites` : le résultat de `services.interdictions` quand on sérialise
    un lot (`_prospects_dicts`) — une requête pour 500 fiches, pas 500.
    """
    if interdites is None:
        interdites = services.interdictions([p.email])
    motif = services.motif_de_non_contact(p, interdites=interdites)
    d: dict[str, Any] = {
        "id": str(p.id), "campagne_id": str(p.campagne_id) if p.campagne_id else None,
        "raison_sociale": p.raison_sociale, "secteur": p.secteur, "zone": p.zone,
        "email": p.email, "nom_contact": p.nom_contact, "fonction": p.fonction,
        "site_web": p.site_web, "source": p.source, "statut": p.statut,
        "score_adequation": p.score_adequation, "raison_score": p.raison_score,
        "contactable": motif is None,
        "motif_non_contact": motif,
        # Pourquoi l'ADRESSE est interdite, s'il y a lieu : « desinscription »,
        # « plainte » ou « rebond_definitif » (ce dernier se lève en corrigeant
        # l'adresse de la fiche).
        "adresse_interdite": interdites.get(normaliser_adresse(p.email)),
        "desinscrit_le": p.desinscrit_le and p.desinscrit_le.isoformat(),
        "notes": p.notes, "cree_le": p.created_at.isoformat(),
    }
    if avec_messages:
        messages = list(p.messages.select_related("prospect", "sequence"))
        leurs_places = places(messages)
        messages.sort(key=lambda m: (leurs_places[str(m.id)].etape, m.created_at))
        d["messages"] = [_message_dict(m, leurs_places[str(m.id)]) for m in messages]
    return d


def _prospects_dicts(liste: Iterable[Prospect]) -> list[dict[str, Any]]:
    """Un lot de fiches, la table des adresses interdites lue UNE fois."""
    fiches = list(liste)
    interdites = services.interdictions(p.email for p in fiches)
    return [_prospect_dict(p, interdites=interdites) for p in fiches]


def _message_dict(m: Message, sa_place: Place | None = None) -> dict[str, Any]:
    sa_place = sa_place or place(m)
    return {
        "etape": sa_place.etape, "etape_libelle": sa_place.libelle,
        "pret": sa_place.pret, "rompue": sa_place.rompue,
        "disponible_le": sa_place.disponible_le and sa_place.disponible_le.isoformat(),
        "prospect_nom": m.prospect.raison_sociale,
        "prospect_contact": m.prospect.nom_contact,
        "id": str(m.id), "prospect_id": str(m.prospect_id),
        "campagne_id": str(m.campagne_id) if m.campagne_id else None,
        "sequence_id": str(m.sequence_id) if m.sequence_id else None,
        "objet": m.objet, "corps": m.corps, "statut": m.statut,
        "valide_par": m.valide_par, "valide_le": m.valide_le and m.valide_le.isoformat(),
        "programme_pour": m.programme_pour and m.programme_pour.isoformat(),
        "envoye_le": m.envoye_le and m.envoye_le.isoformat(),
        "provider_message_id": m.provider_message_id, "error_message": m.error_message,
        "destinataire": m.destinataire,
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
    brouillons = list(Message.objects.filter(statut=StatutMessage.BROUILLON))
    leurs_places = places(brouillons)
    tours = [leurs_places[str(m.id)] for m in brouillons]
    return _json({
        "campagnes_actives": Campagne.objects.filter(statut="active").count(),
        "prospects": Prospect.objects.count(),
        "prospects_par_statut": par_statut,
        # Ce qui est À SON TOUR, pas tous les brouillons : les relances rédigées
        # d'avance attendent l'envoi de l'étape d'avant (`prospection.file`).
        "a_valider": sum(1 for p in tours if p.pret),
        # Une relance ROMPUE (étape d'avant annulée) n'attend pas son tour :
        # elle ne viendra jamais, la compter ici annoncerait le contraire.
        "relances_en_attente": sum(1 for p in tours if not p.pret and not p.rompue),
        "valides_en_attente": Message.objects.filter(statut=StatutMessage.VALIDE).count(),
        # Un envoi refusé par le fournisseur n'était compté nulle part (audit du
        # 19/11/2026) : le message disparaissait de l'écran, et ses relances
        # attendaient sans fin une étape qui ne partirait pas.
        "en_echec": Message.objects.filter(statut=StatutMessage.ECHOUE).count(),
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
        # Les RETARDS de remise ne sont plus des rebonds (audit du 19/11/2026) :
        # ils se comptent à part. Les retards tracés AVANT cette date restent
        # typés « rebond » en base — leur charge brute dit lesquels.
        "rebonds": _uniques(TypeEvenement.REBOND),
        "retards": _uniques(TypeEvenement.RETARD),
        "plaintes": _uniques(TypeEvenement.PLAINTE),
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
    except (Campagne.DoesNotExist, ValidationError, ValueError):
        return _erreur("Campagne introuvable.", status=404)
    return _json({
        **_campagne_dict(c),
        "sequence": [_sequence_dict(s) for s in c.sequence.all()],
        "prospects_liste": _prospects_dicts(c.prospects.all()[:500]),
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
    except (Campagne.DoesNotExist, ValidationError, ValueError):
        return _erreur("Campagne introuvable.", status=404)
    etapes = _corps(request).get("etapes")
    if not isinstance(etapes, list) or not etapes:
        return _erreur("`etapes` doit être une liste non vide (au moins le premier message).")
    c.sequence.all().delete()
    creees = [
        Sequence.objects.create(
            campagne=c, ordre=i,
            delai_jours=max(0, _entier(e.get("delai_jours"), 0)),
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
        return _json(_prospects_dicts(qs[:500]))
    corps = _corps(request)
    raison = _champ(corps, "raison_sociale")
    if not raison:
        return _erreur("La raison sociale est obligatoire.")
    adresse, refus = _adresse_saisie(corps)
    if refus is not None:
        return refus
    campagne = None
    if cid := corps.get("campagne_id"):
        try:
            campagne = Campagne.objects.filter(id=cid).first()
        except (ValidationError, ValueError):
            return _erreur("Campagne introuvable.", status=404)
    p = Prospect.objects.create(
        campagne=campagne, raison_sociale=raison,
        secteur=_champ(corps, "secteur"), zone=_champ(corps, "zone"),
        email=adresse, nom_contact=_champ(corps, "nom_contact"),
        fonction=_champ(corps, "fonction"), site_web=_champ(corps, "site_web"),
        source=_champ(corps, "source", 120) or "manuel",
        notes=_champ(corps, "notes", 5000),
    )
    # Une adresse déjà opposée (désinscrite dans une autre campagne) : la fiche
    # naît désinscrite, pas contactable.
    services.heriter_de_l_opposition(p)
    return _json(_prospect_dict(p), status=201)


#: Les champs d'une fiche qu'un humain corrige, et la taille de leur colonne.
#: L'adresse n'y est pas : elle passe par `_adresse_saisie`, qui la valide.
_CHAMPS_MODIFIABLES: dict[str, int] = {
    "raison_sociale": 200, "secteur": 200, "zone": 200, "nom_contact": 200,
    "fonction": 200, "site_web": 200, "notes": 5000,
}


@csrf_exempt
@require_http_methods(["GET", "PUT"])
def prospect_detail(request: HttpRequest, prospect_id: str) -> JsonResponse:
    """Lit une fiche (GET) ou la CORRIGE (PUT) : adresse, contact, notes…

    Audit du 19/11/2026 : aucune route ne modifiait un prospect. Une fiche créée
    sans adresse, ou avec une adresse qui rebondit, restait à jamais telle
    quelle — il fallait la recréer. Seuls les champs présents dans le corps
    sont touchés ; l'adresse est validée, et une adresse déjà opposée
    désinscrit la fiche au lieu de la rendre contactable.
    """
    try:
        p = Prospect.objects.get(id=prospect_id)
    except (Prospect.DoesNotExist, ValidationError, ValueError):
        return _erreur("Prospect introuvable.", status=404)
    if request.method == "GET":
        return _json(_prospect_dict(p, avec_messages=True))
    corps = _corps(request)
    champs: list[str] = []
    for cle, longueur in _CHAMPS_MODIFIABLES.items():
        if cle in corps:
            setattr(p, cle, _champ(corps, cle, longueur))
            champs.append(cle)
    if "raison_sociale" in champs and not p.raison_sociale:
        return _erreur("La raison sociale est obligatoire.")
    if "email" in corps:
        adresse, refus = _adresse_saisie(corps)
        if refus is not None:
            return refus
        p.email = adresse
        champs.append("email")
    if not champs:
        return _erreur("Aucun champ à modifier dans la requête.")
    p.save(update_fields=[*champs, "updated_at"])
    if "email" in champs:
        services.heriter_de_l_opposition(p)
    return _json(_prospect_dict(p, avec_messages=True))


@csrf_exempt
@require_http_methods(["POST"])
def prospect_desinscrire(request: HttpRequest, prospect_id: str) -> JsonResponse:
    try:
        p = Prospect.objects.get(id=prospect_id)
    except (Prospect.DoesNotExist, ValidationError, ValueError):
        return _erreur("Prospect introuvable.", status=404)
    services.desinscrire(p)
    return _json(_prospect_dict(p))


@csrf_exempt
@require_http_methods(["POST"])
def prospect_statut(request: HttpRequest, prospect_id: str) -> JsonResponse:
    """Fait avancer un prospect dans le pipeline (a répondu, converti, exclu…).

    C'est l'acte humain qui classe un prospect selon ce qu'il devient : une
    réponse reçue, une conversion, une exclusion. TOUT passe par
    `services.classer_prospect` (audit du 19/11/2026) : le statut se posait
    ici directement, sans toucher aux messages ni tracer d'événement — les
    relances continuaient de partir vers quelqu'un qui avait répondu, et le
    taux de réponse valait toujours 0.
    """
    try:
        p = Prospect.objects.get(id=prospect_id)
    except (Prospect.DoesNotExist, ValidationError, ValueError):
        return _erreur("Prospect introuvable.", status=404)
    vise = str(_corps(request).get("statut") or "")
    if vise not in StatutProspect.values:
        return _erreur(f"Statut inconnu : « {vise} ».")
    try:
        services.classer_prospect(p, vise)
    except services.ClassementRefuseError as refus:
        return _erreur(str(refus), status=409)
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
        # Le plafond APRÈS le tri et les filtres : appliqué avant, il gardait
        # les 500 brouillons les plus récents — surtout des relances pas encore
        # à leur tour — et affamait les premiers mails des prospects anciens.
        couples = _ordonnes(list(qs), request)[:500]
        return _json([_message_dict(m, p) for m, p in couples])
    corps = _corps(request)
    try:
        prospect = Prospect.objects.get(id=str(corps.get("prospect_id") or ""))
    except (Prospect.DoesNotExist, ValidationError, ValueError):
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


def _ordonnes(
    messages: list[Message], request: HttpRequest
) -> list[tuple[Message, Place]]:
    """Les messages dans l'ordre de la séquence, filtrés par étape et par tour.

    `etape=0` : les premiers messages seuls ; `etape=2` : la deuxième relance.
    `pret=1` : seulement ce qui peut partir maintenant — une relance attend
    l'envoi de l'étape d'avant (`prospection.file`).
    """
    leurs_places = places(messages)
    couples = [(m, leurs_places[str(m.id)]) for m in messages]
    etape = request.GET.get("etape", "")
    if etape.isdigit():
        couples = [(m, p) for m, p in couples if p.etape == int(etape)]
    if request.GET.get("pret") in ("1", "true"):
        couples = [(m, p) for m, p in couples if p.pret]
    couples.sort(key=lambda c: (c[1].etape, c[0].prospect.raison_sociale.lower(), c[0].created_at))
    return couples


def _lot(request: HttpRequest, statut: str) -> list[Message] | JsonResponse:
    """Les messages d'un lot : EXACTEMENT ceux que l'écran affichait (`ids`).

    Un lot calculé par le serveur au moment du clic validait aussi ce qui était
    arrivé depuis l'affichage — un brouillon rédigé par la tâche quotidienne,
    une relance devenue prête — sans qu'un humain l'ait lu (relecture du
    04/11/2026). Les vérifications du service restent entières.
    """
    ids = _corps(request).get("ids")
    if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids):
        return _erreur("Indiquez les messages du lot (`ids`) : ceux que l'écran affiche.")
    try:
        cles = [uuid.UUID(i) for i in ids]
    except ValueError:
        return _erreur("Un identifiant de message est invalide.")
    qs = Message.objects.select_related("prospect", "sequence").filter(
        id__in=cles, statut=statut
    )
    return sorted(qs, key=lambda m: m.created_at)


@csrf_exempt
@require_http_methods(["POST"])
def messages_valider_lot(request: HttpRequest) -> JsonResponse:
    """Valide d'un coup tous les brouillons PRÊTS d'une étape (ou de toutes)."""
    par = str(_corps(request).get("par") or "").strip()
    if not par:
        return _erreur("Une validation est nominative : indiquez qui valide.")
    lot = _lot(request, StatutMessage.BROUILLON)
    if isinstance(lot, JsonResponse):
        return lot
    valides, refus = services.valider_par_lot(lot, par=par)
    return _json({"valides": valides, "refus": refus})


@csrf_exempt
@require_http_methods(["POST"])
def messages_envoyer_lot(request: HttpRequest) -> JsonResponse:
    """Envoie d'un coup les messages VALIDÉS d'une étape. Part RÉELLEMENT."""
    if _corps(request).get("confirmer") is not True:
        return JsonResponse(
            {
                "erreur": "L'envoi par lot part réellement : relancez avec `confirmer: true`.",
                "confirmation_requise": True,
            },
            status=400,
        )
    lot = _lot(request, StatutMessage.VALIDE)
    if isinstance(lot, JsonResponse):
        return lot
    envoyes, refus = services.envoyer_par_lot(lot)
    return _json({"envoyes": envoyes, "refus": refus})


def _message_ou_404(message_id: str) -> Message | None:
    try:
        return Message.objects.select_related("prospect").get(id=message_id)
    except (Message.DoesNotExist, ValidationError, ValueError):
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


@csrf_exempt
@require_http_methods(["POST"])
def message_brouillon(request: HttpRequest, message_id: str) -> JsonResponse:
    """Ramène un message EN ÉCHEC (ou validé) à l'état de brouillon, pour le retoucher.

    Audit du 19/11/2026 : un envoi refusé par le fournisseur était une impasse.
    Trois sorties désormais — revalider tel quel (`valider/`, que
    `services.valider_message` acceptait déjà pour un message en échec),
    annuler (`annuler/`), ou revenir ici en brouillon pour corriger le texte.
    """
    m = _message_ou_404(message_id)
    if m is None:
        return _erreur("Message introuvable.", status=404)
    try:
        services.remettre_en_brouillon(m)
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
    action: str, fn: Callable[[], Any], *, contexte: dict[str, Any] | None = None
) -> tuple[Any, JsonResponse | None]:
    """Exécute un agent (appel modèle/recherche) et NOMME toute panne IA.

    Une erreur de l'API Claude — crédits épuisés, quota, réseau — n'est pas un
    bug du logiciel. La laisser remonter rendait un 500 nu sous le bouton, sans
    dire à la cliente ce qui se passe ni quoi faire : c'est exactement ce qui est
    arrivé le 24/10/2026, « credit balance is too low » transformé en « Server
    Error (500) ». On la capte, on la journalise EN ENTIER, et on rend un message
    lisible (règle 1 : échouer, mais à voix haute). Rien n'est créé en cas de
    panne — l'agent ne touche la base qu'après l'appel modèle réussi.

    Une `ReponseInexploitableError` (audit du 19/11/2026) est une panne comme
    une autre : le modèle a répondu en texte ou sa sortie est coupée. Son
    message est écrit pour l'humain, on le rend tel quel.

    `contexte` : des champs joints à la réponse d'erreur — l'assistant y met
    l'identifiant de la discussion, pour que l'écran ne la perde pas.
    """
    from prospection.agents import ReponseInexploitableError  # noqa: PLC0415

    try:
        return fn(), None
    except Exception as exc:  # noqa: BLE001 — aucune panne d'agent ne doit rendre un 500 nu
        _log.exception("Agent « %s » en échec", action)
        if isinstance(exc, ReponseInexploitableError):
            message = str(exc)
        elif "credit balance is too low" in str(exc).lower():
            message = (
                "Crédits IA épuisés : rechargez le compte Anthropic (Plans & Billing) "
                "avant de relancer cette action."
            )
        else:
            message = f"Le service IA n'a pas pu exécuter « {action} ». Réessayez plus tard."
        return None, JsonResponse({"erreur": message, **(contexte or {})}, status=502)


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
    except (Campagne.DoesNotExist, ValidationError, ValueError):
        return _erreur("Campagne introuvable.", status=404)
    if not _confirme(request):
        return _confirmation_requise("recherche de prospects")
    from prospection import agents  # noqa: PLC0415

    corps = _corps(request)
    limite = _entier(corps.get("limite"), 10)
    criteres = str(corps.get("criteres") or "")
    bilan, err = _executer_agent(
        "recherche de prospects",
        lambda: agents.rechercher_avec_bilan(c, limite=limite, criteres=criteres),
    )
    if err is not None:
        return err
    # Le zéro se DIT (audit du 19/11/2026) : « aucune organisation proposée »
    # (cible hors brief — c'est voulu), « toutes déjà connues », ou des fiches
    # créées sans adresse ne se lisent pas dans un seul compteur à 0.
    return _json({
        "crees": len(bilan.crees),
        "proposees": bilan.proposees,
        "deja_connues": bilan.deja_connues,
        "sans_adresse": bilan.sans_adresse,
        "prospects": _prospects_dicts(bilan.crees),
    })


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
    except (Conversation.DoesNotExist, ValidationError, ValueError):
        return _erreur("Discussion introuvable.", status=404)
    return _json(_conversation_dict(c, avec_messages=True))


def _reglage_dict(r: ReglageAutomatisation) -> dict[str, Any]:
    """Les réglages ET ce qu'a donné la dernière tentative (audit du 19/11/2026).

    L'écran n'affichait que « Activée ✓ » : une panne quotidienne ne se voyait
    nulle part. Il lit désormais l'état, le bilan et la dernière erreur.

    `prospects_par_jour_max` : le plafond RÉELLEMENT appliqué, lu sur sa seule
    source (`agents._MAX_PROSPECTS_PAR_RECHERCHE`). L'écran écrivait « max 50 »
    en dur pendant que la recherche en créait au plus 25. La valeur rendue est
    bornée de même : un réglage enregistré à 50 avant l'audit s'affiche tel
    qu'il sera appliqué.
    """
    return {
        "active": r.active,
        "prospects_par_jour": min(r.prospects_par_jour, _MAX_PROSPECTS_PAR_RECHERCHE),
        "prospects_par_jour_max": _MAX_PROSPECTS_PAR_RECHERCHE,
        "campagne_id": str(r.campagne_id) if r.campagne_id else None,
        "jours": [int(j) for j in r.jours.split(",") if j.strip().isdigit()],
        "derniere_execution": r.derniere_execution and r.derniere_execution.isoformat(),
        "derniere_tentative": r.derniere_tentative and r.derniere_tentative.isoformat(),
        "dernier_etat": r.etat_affiche(),
        "dernier_bilan": r.dernier_bilan,
        "derniere_erreur": r.derniere_erreur,
    }


@csrf_exempt
@require_http_methods(["GET", "PUT"])
def automatisation(request: HttpRequest) -> JsonResponse:
    """Les réglages de la prospection automatique quotidienne (lire / modifier).

    Désactivée par défaut. L'activer lance, chaque jour, la recherche + la
    qualification + la préparation des e-mails (facturé) ; rien ne part sans
    validation. La désactiver arrête tout. Garde-fou : au plus
    `_MAX_PROSPECTS_PAR_RECHERCHE` prospects/jour — le plafond de la recherche
    elle-même, pas un second chiffre (règle 5).
    """
    r = ReglageAutomatisation.charger()
    if request.method == "GET":
        return _json(_reglage_dict(r))
    corps = _corps(request)
    if "active" in corps:
        r.active = bool(corps.get("active"))
    if "prospects_par_jour" in corps:
        r.prospects_par_jour = max(
            1, min(_entier(corps.get("prospects_par_jour"), 20), _MAX_PROSPECTS_PAR_RECHERCHE)
        )
    if "campagne_id" in corps:
        cid = corps.get("campagne_id")
        try:
            r.campagne = Campagne.objects.filter(id=cid).first() if cid else None
        except (ValidationError, ValueError):
            return _erreur("Campagne introuvable.", status=404)
    if "jours" in corps and isinstance(corps.get("jours"), list):
        valides = [int(j) for j in corps["jours"] if str(j).isdigit() and 0 <= int(j) <= 6]
        r.jours = ",".join(str(j) for j in valides)
    if "cree_par" in corps:
        r.cree_par = str(corps.get("cree_par") or "")
    # Refus clair : activer sans campagne ne prospecterait rien.
    if r.active and r.campagne is None:
        return _erreur("Choisissez une campagne avant d'activer l'automatisation.")
    # Seuls les RÉGLAGES sont écrits. Un `save()` entier réécrivait aussi la
    # trace de la tâche (`derniere_tentative`, état, bilan) avec la valeur lue
    # au début de la requête : enregistrer ses réglages pendant que la tâche
    # tournait effaçait sa tentative, et l'heure suivante la relançait.
    r.save(update_fields=[
        "active", "prospects_par_jour", "campagne", "jours", "cree_par", "updated_at",
    ])
    r.refresh_from_db()
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

    Audit du 19/11/2026 — deux défauts sur une panne du modèle :

    - l'appel se faisait HORS de `_executer_agent` : un 500 nu, là où les trois
      autres agents rendent un 502 qui dit quoi faire ;
    - la discussion était créée AVANT l'appel et le tour de l'humain écrit
      APRÈS : chaque essai laissait une discussion vide de plus, et le texte
      saisi était perdu.

    Le tour de l'humain est donc enregistré AVANT l'appel, et la réponse
    d'erreur porte `conversation_id` et `messages` : l'écran reste sur la même
    discussion, le texte y est, et « Réessayer » ne le duplique pas (un tour
    identique resté sans réponse n'est pas réécrit).
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
        try:
            conv = Conversation.objects.filter(id=conv_id).first()
        except (ValidationError, ValueError):
            conv = None
    if conv is None:
        conv = Conversation.objects.create(
            campagne=campagne, titre=texte[:200],
            cree_par=str(corps.get("cree_par") or "administrateur"),
        )

    # Le tour de l'humain d'abord. Un tour identique resté SANS réponse (essai
    # précédent en panne) n'est pas réécrit : réessayer ne double pas le texte.
    dernier = conv.messages.order_by("-created_at").first()
    if dernier is None or dernier.role != "user" or dernier.contenu != texte:
        MessageConversation.objects.create(conversation=conv, role="user", contenu=texte)
    conv.save(update_fields=["updated_at"])  # remonte en tête de liste

    historique = [
        {"role": m.role, "content": m.contenu} for m in conv.messages.all()
    ]

    from prospection import assistant as agent_assistant  # noqa: PLC0415

    la_campagne = conv.campagne
    reponse, err = _executer_agent(
        "assistant de prospection",
        lambda: agent_assistant.repondre(historique, campagne=la_campagne),
        contexte={
            "conversation_id": str(conv.id),
            "messages": _conversation_dict(conv, avec_messages=True)["messages"],
        },
    )
    if err is not None:
        return err

    MessageConversation.objects.create(
        conversation=conv, role="assistant", contenu=reponse["reponse"]
    )
    conv.save(update_fields=["updated_at"])

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
    except (Prospect.DoesNotExist, ValidationError, ValueError):
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
    except (Prospect.DoesNotExist, ValidationError, ValueError):
        return _erreur("Prospect introuvable.", status=404)
    if not _confirme(request):
        return _confirmation_requise("rédaction des messages")
    # Avant l'appel payant : on ne rédige pas pour une fiche à qui on ne peut
    # pas écrire (audit du 19/11/2026). C'est un refus métier (409), pas une
    # panne de l'IA (502) — l'agent pose la même garde, pour la tâche
    # quotidienne.
    motif = services.motif_de_non_contact(p)
    if motif is not None:
        return _erreur(f"Rédaction inutile : {motif}.", status=409)
    from prospection import agents  # noqa: PLC0415

    corps = _corps(request)
    crees, err = _executer_agent(
        "rédaction des messages",
        lambda: agents.rediger_les_messages(
            p,
            nb_relances=_entier(corps.get("nb_relances"), 4),
            remplacer=corps.get("remplacer") is True,
        ),
    )
    if err is not None:
        return err
    return _json({"crees": len(crees), "messages": [_message_dict(m) for m in crees]})

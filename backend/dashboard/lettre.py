"""La lettre d'information, vue de l'administration.

Rédiger (éditeur enrichi, images), relire (aperçu, essai à soi-même),
programmer ou envoyer ; tenir des modèles ; régler des automatisations.

L'ENVOI est un geste distinct de la rédaction, comme pour les annonces : une
lettre en brouillon n'existe pour personne. `programmer` est le seul chemin
qui la fait partir, et la pompe (`lettre.envoi`) l'envoie au plus tard une
minute après l'heure dite.

Protection : celle de tout `/api/dashboard/` (le jeton de l'administration).
Tout corps est NETTOYÉ à l'enregistrement (`lettre.nettoyage`) : l'aperçu,
l'essai et l'envoi lisent ce qui a été gardé, pas ce qui a été posté.
"""

from __future__ import annotations

import io
import json
import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import Any

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Count
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from lettre import envoi as pompe
from lettre import gabarit
from lettre.models import (
    PREFIXE_IMAGES,
    Automatisation,
    Declencheur,
    Envoi,
    Etape,
    Lettre,
    Modele,
    StatutEnvoi,
    StatutLettre,
)
from lettre.nettoyage import nettoyer

from audience.adresses import adresse_normalisee, empreinte, lire_les_adresses
from audience.models import Contact, Demande, Opposition, Origine, inscrits_q
from evkha.signatures import absolu
from organisations import limitation

_log = logging.getLogger(__name__)

#: Assez pour une photo nette, trop peu pour alourdir un courriel.
TAILLE_MAX_IMAGE = 5 * 1024 * 1024
LARGEUR_MAX_IMAGE = 1200
FORMATS_IMAGE = {"JPEG": "jpg", "PNG": "png", "GIF": "gif", "WEBP": "webp"}
#: Lu dans l'EN-TÊTE, avant tout décodage : un PNG de quelques kilo-octets
#: peut annoncer 13 000 × 13 000 points et occuper des centaines de Mo en
#: mémoire au moment d'être réduit.
PIXELS_MAX_IMAGE = 40_000_000
#: Un GIF n'est pas redessiné (il perdrait son animation) : ses dimensions
#: sont donc bornées telles quelles.
COTE_MAX_GIF = 1600
ESSAIS_PAR_HEURE = limitation.Plafond("lettre-essais", maximum=20, fenetre_s=3600)


def _refus(message: str, code: str, statut: int = 400) -> HttpResponse:
    return JsonResponse({"erreur": message, "code": code}, status=statut)


def _sans_cache(reponse: HttpResponse) -> HttpResponse:
    reponse["Cache-Control"] = "no-store"
    return reponse


def _corps(request: HttpRequest) -> dict[str, Any]:
    try:
        charge = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError):
        return {}
    return charge if isinstance(charge, dict) else {}


_CONTROLES = re.compile(r"[\x00-\x1f\x7f]+")


def _texte(charge: dict[str, Any], cle: str, maximum: int) -> str:
    """Une ligne de texte : les retours et caractères de contrôle deviennent
    des espaces (un objet de courriel tient sur une ligne)."""
    valeur = charge.get(cle)
    if not isinstance(valeur, str):
        return ""
    return _CONTROLES.sub(" ", valeur).strip()[:maximum]


def _iso(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment else None


def _uuid(brut: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(brut))
    except ValueError:
        return None


def _compte_inscrits() -> int:
    return Contact.objects.filter(inscrits_q()).count()


# --- Résumé -----------------------------------------------------------------


@require_http_methods(["GET"])
def resume(request: HttpRequest) -> HttpResponse:
    """Les chiffres de tête : qui reçoit la lettre, qui attend de confirmer."""
    en_attente = (
        Contact.objects.filter(confirmation_demandee_le__isnull=False).exclude(inscrits_q()).count()
    )
    return _sans_cache(
        JsonResponse(
            {
                "inscrits": _compte_inscrits(),
                "en_attente_de_confirmation": en_attente,
                "desinscrits": Contact.objects.filter(desinscrit_le__isnull=False)
                .exclude(inscrits_q())
                .count(),
                "declencheurs": [
                    {"valeur": v, "libelle": libelle} for v, libelle in Declencheur.choices
                ],
            }
        )
    )


# --- Lettres ----------------------------------------------------------------


def _bilan(lettre: Lettre) -> dict[str, int]:
    comptes = {
        ligne["statut"]: ligne["n"]
        for ligne in lettre.envois.values("statut").annotate(n=Count("id"))
    }
    return {statut: comptes.get(statut, 0) for statut in StatutEnvoi.values}


def _vue_lettre(lettre: Lettre, *, complet: bool = False) -> dict[str, Any]:
    vue: dict[str, Any] = {
        "id": str(lettre.id),
        "objet": lettre.objet,
        "apercu": lettre.apercu,
        "statut": lettre.statut,
        "programmee_pour": _iso(lettre.programmee_pour),
        "lancee_le": _iso(lettre.lancee_le),
        "terminee_le": _iso(lettre.terminee_le),
        "cree_le": lettre.created_at.isoformat(),
        "modifiee_le": lettre.updated_at.isoformat(),
        "envois": _bilan(lettre),
    }
    if complet:
        vue["corps_html"] = lettre.corps_html
    return vue


def _lire_lettre(charge: dict[str, Any]) -> tuple[dict[str, str], HttpResponse | None]:
    objet = _texte(charge, "objet", 200)
    if not objet:
        return {}, _refus("Donnez un objet : c'est ce qu'on lit dans la boîte.", "objet_manquant")
    corps = charge.get("corps_html")
    return {
        "objet": objet,
        "apercu": _texte(charge, "apercu", 200),
        "corps_html": nettoyer(corps if isinstance(corps, str) else ""),
    }, None


@csrf_exempt
@require_http_methods(["GET", "POST"])
def lettres(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        return _sans_cache(
            JsonResponse(
                {
                    "lettres": [_vue_lettre(lettre) for lettre in Lettre.objects.all()],
                    "inscrits": _compte_inscrits(),
                }
            )
        )
    champs, refus = _lire_lettre(_corps(request))
    if refus:
        return refus
    lettre = Lettre.objects.create(**champs)
    return JsonResponse(_vue_lettre(lettre, complet=True), status=201)


def _trouver_lettre(lettre_id: str) -> Lettre | None:
    cle = _uuid(lettre_id)
    return Lettre.objects.filter(pk=cle).first() if cle else None


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def lettre(request: HttpRequest, lettre_id: str) -> HttpResponse:
    cible = _trouver_lettre(lettre_id)
    if cible is None:
        return _refus("Newsletter introuvable.", "introuvable", 404)
    if request.method == "GET":
        return _sans_cache(JsonResponse(_vue_lettre(cible, complet=True)))
    if request.method == "DELETE":
        if cible.statut not in (StatutLettre.BROUILLON, StatutLettre.ANNULEE):
            return _refus(
                "Une lettre programmée ou envoyée ne se supprime pas : annulez-la d'abord.",
                "lettre_engagee",
                409,
            )
        cible.delete()
        return JsonResponse({"supprimee": True})
    champs, refus = _lire_lettre(_corps(request))
    if refus:
        return refus
    # Écriture SOUS CONDITION : une programmation arrivée entre la lecture et
    # l'écriture (un autre onglet, la pompe) ne doit pas être recouverte par
    # un « brouillon » — les envois partiraient d'une lettre qui ne le dit plus.
    modifiees = Lettre.objects.filter(pk=cible.pk, statut=StatutLettre.BROUILLON).update(
        **champs, updated_at=timezone.now()
    )
    if not modifiees:
        return _refus(
            "Seul un brouillon se modifie. Déprogrammez la lettre pour la reprendre.",
            "lettre_engagee",
            409,
        )
    cible.refresh_from_db()
    return JsonResponse(_vue_lettre(cible, complet=True))


@csrf_exempt
@require_http_methods(["POST"])
def programmer(request: HttpRequest, lettre_id: str) -> HttpResponse:
    """`{"quand": null}` : maintenant ; `{"quand": "<ISO 8601>"}` : plus tard."""
    cible = _trouver_lettre(lettre_id)
    if cible is None:
        return _refus("Newsletter introuvable.", "introuvable", 404)
    if cible.statut != StatutLettre.BROUILLON:
        return _refus("Cette lettre est déjà programmée ou partie.", "lettre_engagee", 409)
    if not cible.corps_html.strip():
        return _refus("La lettre est vide.", "lettre_vide")
    inscrits = _compte_inscrits()
    if inscrits == 0:
        return _refus("Personne n'est encore inscrit à la lettre.", "aucun_inscrit", 409)
    quand_brut = _corps(request).get("quand")
    maintenant = timezone.now()
    quand: datetime | None = maintenant
    if quand_brut not in (None, ""):
        quand = parse_datetime(quand_brut) if isinstance(quand_brut, str) else None
        if quand is None or timezone.is_naive(quand):
            return _refus("Date d'envoi illisible.", "date_invalide")
        # Une minute de tolérance : choisir « maintenant » dans le sélecteur
        # donne une heure ronde, déjà passée de quelques secondes.
        if quand < maintenant - timedelta(minutes=1):
            return _refus("Cette date est déjà passée.", "date_passee")
    programmees = Lettre.objects.filter(pk=cible.pk, statut=StatutLettre.BROUILLON).update(
        statut=StatutLettre.PROGRAMMEE, programmee_pour=quand, updated_at=maintenant
    )
    if not programmees:
        return _refus("Cette lettre est déjà programmée ou partie.", "lettre_engagee", 409)
    cible.refresh_from_db()
    vue = _vue_lettre(cible, complet=True)
    vue["destinataires_prevus"] = inscrits
    return JsonResponse(vue)


@csrf_exempt
@require_http_methods(["POST"])
def annuler(request: HttpRequest, lettre_id: str) -> HttpResponse:
    """Programmée : redevient un brouillon. En cours : ce qui n'est pas parti
    ne partira pas — ce qui est parti l'est."""
    cible = _trouver_lettre(lettre_id)
    if cible is None:
        return _refus("Newsletter introuvable.", "introuvable", 404)
    with transaction.atomic():
        verrou = Lettre.objects.select_for_update().get(pk=cible.pk)
        if verrou.statut == StatutLettre.PROGRAMMEE:
            verrou.statut = StatutLettre.BROUILLON
            verrou.programmee_pour = None
            verrou.save(update_fields=["statut", "programmee_pour", "updated_at"])
        elif verrou.statut == StatutLettre.EN_COURS:
            verrou.envois.filter(statut=StatutEnvoi.A_ENVOYER).delete()
            verrou.statut = StatutLettre.ANNULEE
            verrou.terminee_le = timezone.now()
            verrou.save(update_fields=["statut", "terminee_le", "updated_at"])
        else:
            return _refus("Il n'y a rien à annuler.", "rien_a_annuler", 409)
    return JsonResponse(_vue_lettre(verrou, complet=True))


# --- Aperçu, essai, images --------------------------------------------------


@csrf_exempt
@require_http_methods(["POST"])
def apercu(request: HttpRequest) -> HttpResponse:
    """Le courriel tel qu'il partira, sans rien enregistrer."""
    charge = _corps(request)
    corps = charge.get("corps_html")
    html = gabarit.enrober(
        objet=_texte(charge, "objet", 200) or "(sans objet)",
        apercu=_texte(charge, "apercu", 200),
        corps_html=nettoyer(corps if isinstance(corps, str) else ""),
        lien_sortie=None,
    )
    return _sans_cache(JsonResponse({"html": html}))


@csrf_exempt
@require_http_methods(["POST"])
def essai(request: HttpRequest) -> HttpResponse:
    """Un exemplaire à UNE adresse choisie, objet préfixé « [Essai] »."""
    charge = _corps(request)
    adresse = adresse_normalisee(charge.get("email"))
    if adresse is None:
        return _refus("Indiquez une adresse e-mail valide.", "adresse_invalide")
    objet = _texte(charge, "objet", 200)
    if not objet:
        return _refus("Donnez un objet avant l'essai.", "objet_manquant")
    # Un jeton d'administration volé ne doit pas faire de ce bouton un relais
    # d'envoi au nom d'EVKHA : vingt essais par heure suffisent à relire.
    if not limitation.compter(ESSAIS_PAR_HEURE, "administration"):
        return _refus("Trop d'essais en une heure. Réessayez plus tard.", "trop_d_essais", 429)
    corps = charge.get("corps_html")
    try:
        pompe.envoyer_un_essai(
            objet=objet,
            apercu=_texte(charge, "apercu", 200),
            corps_html=nettoyer(corps if isinstance(corps, str) else ""),
            adresse=adresse,
        )
    except Exception:  # noqa: BLE001 — l'échec est rendu à l'écran, pas avalé
        _log.warning("Essai de lettre non envoyé", exc_info=True)
        return _refus(
            "Le courriel d'essai n'est pas parti. Réessayez dans un instant.",
            "envoi_impossible",
            502,
        )
    return JsonResponse({"envoye": True, "adresse": adresse})


@csrf_exempt
@require_http_methods(["POST"])
def image(request: HttpRequest) -> HttpResponse:
    """Une image glissée dans l'éditeur. Rend son adresse ABSOLUE et publique.

    Le fichier est REDESSINÉ (sauf un GIF, qui perdrait son animation) : les
    métadonnées d'une photo — lieu de prise de vue compris — ne partent pas
    chez des centaines de destinataires, et une photo de 4 000 px est ramenée
    à la largeur d'un courriel.
    """
    from PIL import Image, UnidentifiedImageError  # noqa: PLC0415

    fichier = request.FILES.get("image")
    if fichier is None:
        return _refus("Aucune image reçue.", "image_manquante")
    if fichier.size is None or fichier.size > TAILLE_MAX_IMAGE:
        return _refus("Image trop lourde : 5 Mo au plus.", "image_trop_lourde")
    brut = fichier.read()
    try:
        with Image.open(io.BytesIO(brut)) as controle:
            controle.verify()
        source: Image.Image = Image.open(io.BytesIO(brut))
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        SyntaxError,
        ValueError,
    ):
        return _refus("Ce fichier n'est pas une image lisible.", "image_illisible")
    forme = source.format or ""
    extension = FORMATS_IMAGE.get(forme)
    if extension is None:
        return _refus("Formats acceptés : JPEG, PNG, GIF, WebP.", "format_refuse")
    if source.width * source.height > PIXELS_MAX_IMAGE:
        return _refus("Image trop grande : réduisez-la avant de l'envoyer.", "image_trop_grande")
    if forme == "GIF":
        if max(source.width, source.height) > COTE_MAX_GIF:
            return _refus(
                f"GIF trop grand : {COTE_MAX_GIF} points de côté au plus.", "image_trop_grande"
            )
        donnees = brut
    else:
        if source.width > LARGEUR_MAX_IMAGE:
            hauteur = round(source.height * LARGEUR_MAX_IMAGE / source.width)
            source = source.resize((LARGEUR_MAX_IMAGE, hauteur))
        if forme == "JPEG" and source.mode not in ("RGB", "L"):
            source = source.convert("RGB")
        sortie = io.BytesIO()
        options: dict[str, Any] = {"quality": 85} if forme in ("JPEG", "WEBP") else {}
        source.save(sortie, format=forme, **options)
        donnees = sortie.getvalue()
    nom = default_storage.save(
        f"{PREFIXE_IMAGES}/{uuid.uuid4().hex}.{extension}", ContentFile(donnees)
    )
    return JsonResponse({"url": absolu(default_storage.url(nom))}, status=201)


# --- Abonnés ajoutés par la gérante -------------------------------------------

#: Assez pour reprendre une liste entière d'un coup, borné pour une requête.
AJOUTS_MAX = 10_000


@csrf_exempt
@require_http_methods(["POST"])
def ajouter_des_abonnes(request: HttpRequest) -> HttpResponse:
    """`{"texte", "provenance", "consentement": true}` : abonne directement les
    adresses lues dans le texte (`audience.adresses.lire_les_adresses`).

    Pas de courriel de confirmation : la gérante atteste, case cochée, que ces
    personnes ont accepté la newsletter, et dit d'où vient la liste — la
    provenance est gardée sur chaque `Demande` (preuve du consentement).

    Jamais réabonnées par ce chemin : une personne désinscrite, une personne
    effacée à sa demande (`Opposition`), une ligne d'export marquée comme
    désinscrite ou en rebond. Leur retrait vaut plus qu'une liste importée ;
    elles seules peuvent revenir, par le site et son courriel de confirmation.
    """
    charge = _corps(request)
    if charge.get("consentement") is not True:
        return _refus(
            "Cochez la case : ces personnes doivent avoir accepté de recevoir la newsletter.",
            "consentement_manquant",
        )
    provenance = _texte(charge, "provenance", 200)
    if not provenance:
        return _refus(
            "Dites d'où vient la liste (par exemple : export Systeme.io de novembre).",
            "provenance_manquante",
        )
    texte = charge.get("texte")
    if not isinstance(texte, str) or "@" not in texte:
        return _refus("Collez au moins une adresse e-mail.", "aucune_adresse")
    lecture = lire_les_adresses(texte)
    if len(lecture.valides) + len(lecture.invalides) > AJOUTS_MAX:
        return _refus(
            f"{AJOUTS_MAX} adresses au plus en une fois : coupez la liste en deux.",
            "trop_d_adresses",
        )
    maintenant = timezone.now()
    with transaction.atomic():
        existants = {c.email: c for c in Contact.objects.filter(email__in=lecture.valides)}
        # L'opposition vaut pour TOUTE adresse lue — y compris celle d'une
        # personne effacée qui a, depuis, repris une ressource sans cocher la
        # newsletter : son contact existe de nouveau, son refus aussi.
        opposees = set(
            Opposition.objects.filter(
                empreinte__in=[empreinte(a) for a in lecture.valides]
            ).values_list("empreinte", flat=True)
        )
        nouvelles = [
            a for a in lecture.valides if a not in existants and empreinte(a) not in opposees
        ]
        Contact.objects.bulk_create(
            [Contact(email=a, lettre_le=maintenant) for a in nouvelles],
            batch_size=1000,
            ignore_conflicts=True,
        )
        crees = list(
            Contact.objects.filter(email__in=nouvelles, lettre_le=maintenant).values_list(
                "pk", flat=True
            )
        )
        deja = [c for c in existants.values() if c.inscrit_a_la_lettre]
        desinscrites = [
            c
            for c in existants.values()
            if not c.inscrit_a_la_lettre and c.desinscrit_le is not None
        ]
        connues = [
            c.pk
            for c in existants.values()
            if not c.inscrit_a_la_lettre
            and c.desinscrit_le is None
            and empreinte(c.email) not in opposees
        ]
        Contact.objects.filter(pk__in=connues).update(
            lettre_le=maintenant, confirmations_sans_reponse=0, updated_at=maintenant
        )
        Demande.objects.bulk_create(
            [
                Demande(contact_id=pk, origine=Origine.AJOUT, provenance=provenance)
                for pk in [*crees, *connues]
            ],
            batch_size=1000,
        )
    return JsonResponse(
        {
            "ajoutees": len(crees) + len(connues),
            "deja_inscrites": len(deja),
            "desinscrites_non_reinscrites": len(
                {c.email for c in desinscrites}
                | {a for a in lecture.valides if empreinte(a) in opposees}
            ),
            "lignes_ecartees": lecture.lignes_ecartees,
            "invalides": lecture.invalides[:20],
            "invalides_total": len(lecture.invalides),
            "inscrits": _compte_inscrits(),
        }
    )


# --- Modèles ----------------------------------------------------------------


def _vue_modele(modele: Modele) -> dict[str, Any]:
    return {
        "id": str(modele.id),
        "nom": modele.nom,
        "objet": modele.objet,
        "apercu": modele.apercu,
        "corps_html": modele.corps_html,
        "modifie_le": modele.updated_at.isoformat(),
    }


def _lire_modele(charge: dict[str, Any]) -> tuple[dict[str, str], HttpResponse | None]:
    nom = _texte(charge, "nom", 120)
    if not nom:
        return {}, _refus("Donnez un nom au modèle.", "nom_manquant")
    corps = charge.get("corps_html")
    return {
        "nom": nom,
        "objet": _texte(charge, "objet", 200),
        "apercu": _texte(charge, "apercu", 200),
        "corps_html": nettoyer(corps if isinstance(corps, str) else ""),
    }, None


@csrf_exempt
@require_http_methods(["GET", "POST"])
def modeles(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        vues = [_vue_modele(m) for m in Modele.objects.all()]
        return _sans_cache(JsonResponse({"modeles": vues}))
    champs, refus = _lire_modele(_corps(request))
    if refus:
        return refus
    return JsonResponse(_vue_modele(Modele.objects.create(**champs)), status=201)


@csrf_exempt
@require_http_methods(["PUT", "DELETE"])
def modele(request: HttpRequest, modele_id: str) -> HttpResponse:
    cle = _uuid(modele_id)
    cible = Modele.objects.filter(pk=cle).first() if cle else None
    if cible is None:
        return _refus("Modèle introuvable.", "introuvable", 404)
    if request.method == "DELETE":
        cible.delete()
        return JsonResponse({"supprime": True})
    champs, refus = _lire_modele(_corps(request))
    if refus:
        return refus
    for nom, valeur in champs.items():
        setattr(cible, nom, valeur)
    cible.save()
    return JsonResponse(_vue_modele(cible))


# --- Automatisations --------------------------------------------------------


def _vue_automatisation(automatisation: Automatisation) -> dict[str, Any]:
    etapes = list(automatisation.etapes.order_by("ordre"))
    return {
        "id": str(automatisation.id),
        "nom": automatisation.nom,
        "declencheur": automatisation.declencheur,
        "active": automatisation.active,
        "active_depuis": _iso(automatisation.active_depuis),
        "etapes": [
            {
                "id": str(etape.id),
                "delai_jours": etape.delai_jours,
                "objet": etape.objet,
                "apercu": etape.apercu,
                "corps_html": etape.corps_html,
                "envoyes": etape.envois.filter(statut=StatutEnvoi.ENVOYE).count(),
            }
            for etape in etapes
        ],
    }


def _lire_etapes(brut: Any) -> tuple[list[dict[str, Any]], HttpResponse | None]:
    if not isinstance(brut, list) or len(brut) > 20:
        return [], _refus("Une automatisation compte 20 messages au plus.", "etapes_invalides")
    etapes = []
    for rang, element in enumerate(brut, start=1):
        if not isinstance(element, dict):
            return [], _refus("Message illisible.", "etapes_invalides")
        objet = _texte(element, "objet", 200)
        if not objet:
            return [], _refus(f"Le message {rang} n'a pas d'objet.", "objet_manquant")
        delai = element.get("delai_jours", 0)
        if not isinstance(delai, int) or isinstance(delai, bool) or not 0 <= delai <= 365:
            return [], _refus(f"Délai du message {rang} : de 0 à 365 jours.", "delai_invalide")
        corps = element.get("corps_html")
        etapes.append(
            {
                "id": _uuid(str(element.get("id") or "")),
                "delai_jours": delai,
                "objet": objet,
                "apercu": _texte(element, "apercu", 200),
                "corps_html": nettoyer(corps if isinstance(corps, str) else ""),
            }
        )
    return etapes, None


def _enregistrer_automatisation(
    cible: Automatisation | None, charge: dict[str, Any]
) -> tuple[Automatisation | None, HttpResponse | None]:
    nom = _texte(charge, "nom", 120)
    if not nom:
        return None, _refus("Donnez un nom à l'automatisation.", "nom_manquant")
    declencheur = charge.get("declencheur")
    if not isinstance(declencheur, str) or declencheur not in Declencheur.values:
        return None, _refus("Choisissez ce qui déclenche l'automatisation.", "declencheur_invalide")
    etapes, refus = _lire_etapes(charge.get("etapes"))
    if refus:
        return None, refus
    active = charge.get("active") is True
    if active and not etapes:
        return None, _refus("Ajoutez au moins un message avant d'activer.", "etapes_invalides")
    with transaction.atomic():
        if cible is None:
            cible = Automatisation(nom=nom, declencheur=declencheur)
        else:
            # Deux enregistrements simultanés se suivent au lieu de se heurter
            # sur l'unicité (automatisation, ordre).
            cible = Automatisation.objects.select_for_update().get(pk=cible.pk)
        if not cible._state.adding and (
            cible.declencheur != declencheur and cible.etapes.filter(envois__isnull=False).exists()
        ):
            return None, _refus(
                "Des messages sont déjà partis : créez une autre automatisation "
                "pour un autre déclencheur.",
                "declencheur_fige",
                409,
            )
        cible.nom = nom
        cible.declencheur = declencheur
        if active and not cible.active:
            # Seuls les événements à venir comptent : activer n'écrit pas d'un
            # coup à toutes les personnes déjà inscrites.
            cible.active_depuis = timezone.now()
        if cible.active and not active:
            # En pause : ce qui attendait en file ne part pas.
            Envoi.objects.filter(etape__automatisation=cible, statut=StatutEnvoi.A_ENVOYER).delete()
        cible.active = active
        cible.save()
        existantes = {etape.id: etape for etape in cible.etapes.all()}
        gardees = {e["id"] for e in etapes if e["id"] in existantes}
        for cle, etape in existantes.items():
            if cle not in gardees:
                etape.delete()
        # Deux temps : l'unicité (automatisation, ordre) refuserait un échange
        # de places fait directement. Chaque étape gardée prend d'abord une
        # place provisoire, distincte des places définitives.
        for provisoire, etape in enumerate(cible.etapes.all(), start=1000):
            etape.ordre = provisoire
            etape.save(update_fields=["ordre"])
        for rang, donnees in enumerate(etapes, start=1):
            champs = {k: v for k, v in donnees.items() if k != "id"}
            existante = existantes.get(donnees["id"]) if donnees["id"] in gardees else None
            if existante is None:
                Etape.objects.create(automatisation=cible, ordre=rang, **champs)
            else:
                for nom_champ, valeur in champs.items():
                    setattr(existante, nom_champ, valeur)
                existante.ordre = rang
                existante.save()
    return cible, None


@csrf_exempt
@require_http_methods(["GET", "POST"])
def automatisations(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        return _sans_cache(
            JsonResponse(
                {"automatisations": [_vue_automatisation(a) for a in Automatisation.objects.all()]}
            )
        )
    cible, refus = _enregistrer_automatisation(None, _corps(request))
    if refus:
        return refus
    assert cible is not None
    return JsonResponse(_vue_automatisation(cible), status=201)


@csrf_exempt
@require_http_methods(["PUT", "DELETE"])
def automatisation(request: HttpRequest, automatisation_id: str) -> HttpResponse:
    cle = _uuid(automatisation_id)
    cible = Automatisation.objects.filter(pk=cle).first() if cle else None
    if cible is None:
        return _refus("Automatisation introuvable.", "introuvable", 404)
    if request.method == "DELETE":
        # Ce qui attend en file ne partira plus ; l'historique de ce qui est
        # parti disparaît avec elle.
        cible.delete()
        return JsonResponse({"supprimee": True})
    resultat, refus = _enregistrer_automatisation(cible, _corps(request))
    if refus:
        return refus
    assert resultat is not None
    return JsonResponse(_vue_automatisation(resultat))

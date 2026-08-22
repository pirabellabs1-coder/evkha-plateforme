"""La boutique : catalogue public, fiche produit, achat et remise.

Separee de `vues_publiques` pour la meme raison que celle-ci l'est de
`vues_espace` : ce qui est ouvert doit se voir au premier coup d'oeil dans
l'arborescence, pas se decouvrir en lisant les decorateurs.

Un produit de boutique est une etude DEJA REDIGEE. Le paiement n'ouvre aucune
production : il ouvre un acces a un fichier.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from catalog.models import ProduitBoutique

from . import authentification, limitation

_log = logging.getLogger(__name__)

#: Paiements ouverts par adresse IP et par heure. Plus large que les
#: inscriptions : quelqu'un qui hesite entre deux etudes en ouvre
#: legitimement plusieurs. Le plafond ne protege que d'un script.
ACHATS_PAR_HEURE = limitation.Plafond("boutique", maximum=20, fenetre_s=3600)

#: Nombre d'etudes proches proposees en bas d'une fiche.
PRODUITS_PROCHES = 3


def _refus(message: str, code: str, statut: int = 400) -> HttpResponse:
    return JsonResponse({"erreur": message, "code": code}, status=statut)


def _url(fichier: Any) -> str:
    """Adresse d'un fichier public — image ou extrait — ou chaine vide.

    L'image de couverture et l'extrait sont PUBLICS : ils servent a vendre.
    Le document achete, lui, ne passe jamais par ici (voir `vues_espace`).

    ABSOLUE : la page qui l'affiche est servie par `app2.evkha.fr`, `/media/`
    par `api2.evkha.fr`, et le proxy du frontend ne couvre que `/api/`.
    """
    from evkha import signatures  # noqa: PLC0415 — evite un cycle a l'import

    try:
        return signatures.absolu(fichier.url) if fichier else ""
    except ValueError:
        return ""


def _resume(produit: ProduitBoutique) -> dict[str, Any]:
    """Ce que la GRILLE affiche. Volontairement court."""
    return {
        "slug": produit.slug,
        "titre": produit.titre,
        "theme": produit.theme,
        "prix_cents": produit.prix_cents,
        "devise": produit.devise,
        "pages": produit.nombre_de_pages,
        "mise_a_jour": (
            produit.mise_a_jour_le.isoformat() if produit.mise_a_jour_le else ""
        ),
        "image": _url(produit.image),
        # La note voyage avec la grille : une carte qui la tait oblige a
        # ouvrir chaque fiche pour comparer.
        "note": produit.note_moyenne,
        "nombre_d_avis": produit.nombre_d_avis,
    }


def _fiche(produit: ProduitBoutique) -> dict[str, Any]:
    """Ce que la FICHE affiche, en plus du resume."""
    return {
        **_resume(produit),
        "description": produit.description,
        # Le sommaire est saisi une ligne par entree : on le rend en liste
        # plutot que de laisser la page decouper un texte, ce qui ferait deux
        # avis sur ce qu'est une ligne.
        "sommaire": [
            ligne.strip()
            for ligne in produit.sommaire.splitlines()
            if ligne.strip()
        ],
        "extrait": _url(produit.extrait),
        "editable": bool(produit.fichier_editable),
        "avis": [
            {
                "auteur": avis.auteur,
                "qualite": avis.qualite,
                "note": avis.note,
                "texte": avis.texte,
                "date": avis.created_at.date().isoformat(),
            }
            # Les avis NON PUBLIES sont ecartes ici et non par la requete :
            # `note_moyenne` filtre deja en Python sur la meme collection
            # prechargee, et deux filtres ecrits differemment finiraient par
            # ne plus dire la meme chose (regle 5).
            for avis in produit.avis.all()
            if avis.publie
        ],
    }


def _en_ligne() -> Any:
    """Les produits reellement vendables.

    `en_ligne` seul ne suffit pas : une fiche publiee sans fichier ou sans
    prix encaisserait sans rien remettre, ou ouvrirait un paiement de zero.
    Le filtre porte donc sur les DEUX conditions, ici et nulle part ailleurs.
    """
    return (
        ProduitBoutique.objects.filter(en_ligne=True, prix_cents__gt=0)
        .exclude(fichier="")
        .prefetch_related("avis")
        .order_by("rang", "titre")
    )


#: Avis mis en avant sur la page de la boutique, toutes etudes confondues.
AVIS_A_LA_UNE = 3


@require_GET
def catalogue(request: HttpRequest) -> HttpResponse:
    """La grille de la boutique, ses themes, et quelques avis.

    Les avis remontent ICI et pas seulement sur les fiches : le visiteur qui
    arrive sur la boutique n'a encore choisi aucune etude, et c'est a ce
    moment-la qu'il decide si la maison est serieuse. Les lui reserver pour
    apres le clic, c'est les montrer a qui est deja convaincu.

    Ils sont pris sur l'ensemble du catalogue en ligne, du plus recent au plus
    ancien, et chacun porte le titre de l'etude dont il parle — un temoignage
    sans son objet ne veut rien dire.
    """
    produits = list(_en_ligne())
    themes = sorted({p.theme for p in produits if p.theme})

    # UN SEUL avis par etude. Sans cette contrainte, trois cartes cote a cote
    # parlaient deux fois de la meme etude — le lecteur en deduit qu'il n'y a
    # que celle-la, ce qui est l'inverse de l'effet cherche. Le plus recent de
    # chaque etude, puis les plus recents de l'ensemble.
    meilleurs = []
    for produit in produits:
        lisibles = [
            avis
            for avis in produit.avis.all()
            # Un avis sans texte ne temoigne de rien : il ne porte qu'une note,
            # deja comptee dans la moyenne de sa carte.
            if avis.publie and avis.texte.strip()
        ]
        if not lisibles:
            continue
        # Le MIEUX NOTE de l'etude, le plus recent a egalite. C'est un choix
        # editorial, et il s'assume : ce bloc est une vitrine, pas la liste des
        # avis. La liste complete — bonnes notes ET moins bonnes — est sur la
        # fiche de chaque etude, ou elle decide de l'achat.
        meilleurs.append(
            max(lisibles, key=lambda avis: (avis.note, avis.created_at))
        )

    a_la_une = [
        {
            "auteur": avis.auteur,
            "qualite": avis.qualite,
            "note": avis.note,
            "texte": avis.texte,
            "date": avis.created_at.date().isoformat(),
            "etude": avis.produit.titre,
            "slug": avis.produit.slug,
        }
        for avis in sorted(
            meilleurs, key=lambda avis: (avis.note, avis.created_at), reverse=True
        )[:AVIS_A_LA_UNE]
    ]

    return JsonResponse({
        "produits": [_resume(p) for p in produits],
        "themes": themes,
        "avis": a_la_une,
    })


@require_GET
def fiche(request: HttpRequest, slug: str) -> HttpResponse:
    """Une fiche produit, et les etudes proches.

    Les etudes proches se calculent par THEME. Demander a la cliente de relier
    les produits a la main serait un travail a refaire a chaque ajout au
    catalogue — et le premier oublie ferait une fiche sans suggestion.
    """
    produit = _en_ligne().filter(slug=slug).first()
    if produit is None:
        return _refus("Cette étude n'est pas disponible.", "produit_inconnu", 404)

    proches = _en_ligne().exclude(pk=produit.pk)
    if produit.theme:
        memes = list(proches.filter(theme=produit.theme)[:PRODUITS_PROCHES])
    else:
        memes = []
    # Un theme trop etroit ne doit pas laisser la fiche sans suggestion : on
    # complete avec le reste du catalogue.
    if len(memes) < PRODUITS_PROCHES:
        deja = {p.pk for p in memes}
        for autre in proches:
            if autre.pk not in deja:
                memes.append(autre)
            if len(memes) >= PRODUITS_PROCHES:
                break

    return JsonResponse({
        "produit": _fiche(produit),
        "proches": [_resume(p) for p in memes[:PRODUITS_PROCHES]],
    })


@csrf_exempt
@require_POST
def acheter(request: HttpRequest) -> HttpResponse:
    """Ouvre le paiement d'un produit, sans compte prealable.

    Rien de ce que le navigateur envoie ne fixe le prix : on ne lit qu'un
    slug, et le montant est celui du produit.
    """
    from paiement import stripe_api  # noqa: PLC0415

    try:
        charge = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return _refus("Requête illisible.", "corps_invalide")
    if not isinstance(charge, dict):
        return _refus("Requête illisible.", "corps_invalide")

    adresse_ip = limitation.adresse_client(request)
    if limitation.depasse(ACHATS_PAR_HEURE, adresse_ip):
        return _refus(
            "Trop de paiements ouverts depuis cette connexion. Réessayez dans "
            "une heure, ou écrivez-nous à contact@evkha.fr.",
            "trop_de_tentatives",
            429,
        )

    slug = str(charge.get("produit") or "").strip()
    produit = _en_ligne().filter(slug=slug).first()
    if produit is None:
        return _refus("Cette étude n'est pas disponible.", "produit_inconnu", 404)

    email = str(charge.get("email") or "").strip()
    try:
        session = stripe_api.creer_paiement_de_produit(produit=produit, email=email)
    except stripe_api.PaiementIndisponible as refus:
        _log.error("Achat du produit %s impossible : %s", slug, refus)
        return _refus(str(refus), "paiement_indisponible", 503)

    # Le panier est note AVANT que la personne ne parte payer. C'est tout
    # l'interet : celui qui n'aboutit pas est justement celui qu'on veut voir.
    from paiement import boutique as remise  # noqa: PLC0415

    remise.noter_la_tentative(session=session, produit=produit, email=email)

    return JsonResponse({"adresse": session.adresse})


@csrf_exempt
@require_POST
def retour(request: HttpRequest) -> HttpResponse:
    """L'acheteur revient du paiement : on vérifie, on livre, on ouvre l'accès.

    On n'attend PAS le webhook. Stripe redirige le navigateur et poste son
    événement en parallèle, sans ordre garanti. Le traitement est idempotent :
    celui des deux qui arrive d'abord livre, l'autre ne fait rien.

    L'identifiant de session ne prouve rien par lui-même — il arrive par
    l'adresse de retour, donc de l'extérieur. C'est le prestataire qui dit si
    elle est payée, et `livrer_le_produit` refuse tout ce qui ne l'est pas.
    """
    from paiement import boutique as remise  # noqa: PLC0415
    from paiement import stripe_api  # noqa: PLC0415

    try:
        charge = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return _refus("Requête illisible.", "corps_invalide")
    if not isinstance(charge, dict):
        return _refus("Requête illisible.", "corps_invalide")

    identifiant = str(charge.get("session") or "").strip()
    if not identifiant:
        return _refus("Paiement introuvable.", "session_absente")

    try:
        session = stripe_api.relire_la_session(identifiant)
    except stripe_api.PaiementIndisponible as refus:
        return _refus(str(refus), "session_illisible", 503)

    if not remise.est_un_achat_de_produit(session):
        return _refus("Ce paiement ne concerne pas la boutique.", "achat_autre", 409)

    try:
        resultat = remise.livrer_le_produit(session)
    except remise.AchatInexploitable as refus:
        _log.error("Retour de boutique inexploitable (%s) : %s", identifiant, refus)
        return _refus(
            "Votre paiement a bien été reçu, mais votre accès n'a pas pu être "
            "ouvert. Écrivez-nous à contact@evkha.fr, nous le faisons "
            "immédiatement.",
            "achat_inexploitable",
            409,
        )

    if resultat.nouveau:
        remise.prevenir_l_acheteur(resultat)

    # C'est le prestataire qui a prouvé l'identité : il a encaissé une carte et
    # collecté l'adresse. La personne n'a pas de mot de passe et n'en a pas
    # besoin pour entrer ; elle en choisira un depuis le courriel.
    jeton_clair = authentification.ouvrir_session_sans_mot_de_passe(resultat.compte)
    return JsonResponse({
        "jeton": jeton_clair,
        "titre": resultat.produit.titre,
        "slug": resultat.produit.slug,
        "telechargement": remise.lien_de_telechargement(resultat.achat),
        "editable": remise.lien_de_telechargement(resultat.achat, editable=True),
    })

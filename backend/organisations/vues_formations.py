"""Les formations : ce que les pages publiques en lisent.

Séparées de `vues_publiques` pour la même raison que `vues_boutique` : ce qui
est ouvert doit se voir dans l'arborescence.

Les prix des formations étaient écrits en dur dans les pages, et leur
programme n'existait que dans un outil externe. Cette vue rend les deux, tels
que la cliente les tient depuis l'administration.

## Ce qui ne sort JAMAIS d'ici

L'adresse d'une vidéo, le texte d'une leçon, le document joint : c'est le
contenu que l'acheteur paie. Pas même pour une leçon « en aperçu libre » —
`en_apercu_libre` est rendu comme une étiquette, pas comme un accès.

Chaque dictionnaire est donc écrit clé par clé. Sérialiser le modèle « moins
les champs sensibles » publierait d'office le prochain champ ajouté (règle 4 :
on autorise, on n'interdit pas).

## L'achat

Une formation se paie par Stripe, ici (décision de la cliente du 20/11/2026).
`acheter` ouvre le paiement sans compte préalable, `retour` reçoit l'acheteur
qui en revient. Ni l'une ni l'autre ne rend le contenu des leçons : il se lit
dans l'espace client (`vues_espace.mes_formations`), derrière une session.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from catalog import formations as regles
from catalog.models import Formation, LeconDeFormation, ModuleDeFormation

from . import authentification, limitation, retours

_log = logging.getLogger(__name__)

#: Paiements de formation ouverts par adresse IP et par heure. Un plafond à
#: part de celui de la boutique : les deux ne se comptent pas ensemble, et
#: épuiser l'un ne ferme pas l'autre. Il ne protège que d'un script — chaque
#: ouverture crée une session chez le prestataire.
ACHATS_PAR_HEURE = limitation.Plafond("formations", maximum=20, fenetre_s=3600)


def _refus(message: str, code: str, statut: int = 400) -> HttpResponse:
    return JsonResponse({"erreur": message, "code": code}, status=statut)


def _corps(request: HttpRequest) -> dict[str, Any] | None:
    """La charge JSON de la requête, ou `None` si elle est illisible."""
    try:
        charge = json.loads(request.body or b"{}")
    # `UnicodeDecodeError` et `RecursionError` : un corps mal encodé ou
    # imbriqué à l'excès rendait sinon une erreur 500.
    except (ValueError, RecursionError):
        return None
    return charge if isinstance(charge, dict) else None


def _lecon(position: int, lecon: LeconDeFormation) -> dict[str, Any]:
    return {
        "rang": position,
        "titre": lecon.titre,
        "nature": lecon.nature,
        "duree_minutes": lecon.duree_minutes,
        "en_apercu_libre": lecon.en_apercu_libre,
    }


def _module(position: int, module: ModuleDeFormation) -> dict[str, Any]:
    return {
        "rang": position,
        "titre": module.titre,
        "description": module.description,
        "lecons": [
            _lecon(numero, lecon)
            for numero, lecon in enumerate(module.lecons.all(), start=1)
        ],
    }


def _fiche(formation: Formation) -> dict[str, Any]:
    # `rang` est la PLACE dans le programme affiché, de 1 à n — pas le rang
    # stocké, qui part de zéro et garde un trou à chaque retrait. La page
    # écrit « Module 2 » : elle n'a pas à savoir qu'un module a été retiré.
    modules = [
        _module(numero, module)
        for numero, module in enumerate(formation.modules.all(), start=1)
    ]
    return {
        "slug": formation.slug,
        "titre": formation.titre,
        "sous_titre": formation.sous_titre,
        "accroche": formation.accroche,
        "prix_cents": formation.prix_cents,
        "devise": formation.devise,
        "duree_heures": formation.duree_heures,
        "heures_de_coaching": formation.heures_de_coaching,
        "lien_d_achat": formation.lien_d_achat,
        "image": regles.adresse_de_l_image(formation),
        "nombre_de_modules": len(modules),
        "modules": modules,
    }


@require_GET
def catalogue(request: HttpRequest) -> HttpResponse:
    """Les formations en ligne, avec leur prix et leur programme."""
    return JsonResponse(
        {"formations": [_fiche(formation) for formation in regles.publiees()]}
    )


def _adresse_saisie(brut: object) -> str:
    """L'adresse proposée avant le paiement, si elle en est une ; sinon rien.

    Elle est FACULTATIVE et ne sert qu'à préremplir la page du prestataire,
    qui la collecte de toute façon. Une saisie qui n'est pas une adresse est
    donc écartée plutôt que refusée : transmise telle quelle, elle faisait
    rejeter l'ouverture par le prestataire, et le visiteur lisait « paiement
    indisponible » pour une faute de frappe.
    """
    if not isinstance(brut, str):
        return ""
    adresse = regles.texte_propre(brut)
    try:
        validate_email(adresse)
    except ValidationError:
        return ""
    return adresse


@csrf_exempt
@require_POST
def acheter(request: HttpRequest) -> HttpResponse:
    """Ouvre le paiement d'une formation, sans compte préalable.

    Rien de ce que le navigateur envoie ne fixe le prix : on ne lit qu'un
    slug, et le montant est celui de la formation.

    Le compte naît du paiement (`paiement.formations.livrer_la_formation`) :
    au moment du clic, le visiteur n'a ni compte ni jeton.
    """
    from paiement import formations as remise  # noqa: PLC0415
    from paiement import stripe_api  # noqa: PLC0415

    charge = _corps(request)
    if charge is None:
        return _refus("Requête illisible.", "corps_invalide")

    adresse_ip = limitation.adresse_client(request)
    if limitation.depasse(ACHATS_PAR_HEURE, adresse_ip):
        return _refus(
            "Trop de paiements ouverts depuis cette connexion. Réessayez dans "
            "une heure, ou écrivez-nous à contact@evkha.fr.",
            "trop_de_tentatives",
            429,
        )

    brut = charge.get("formation")
    slug = brut.strip() if isinstance(brut, str) else ""
    try:
        formation = regles.a_vendre(slug)
    except regles.Refus as refus:
        return _refus(refus.message, refus.code, refus.statut)

    email = _adresse_saisie(charge.get("email"))

    # Interrogé plus haut, COMPTÉ ici — AVANT l'appel au prestataire. Un
    # plafond lu sans être compté ne s'atteint jamais (audit du 19/11/2026) ;
    # compté APRÈS l'appel, il ne voyait ni les ouvertures que le prestataire
    # refuse, ni les requêtes parties ensemble, qui lisaient toutes zéro
    # (audit du 20/11/2026). Une demande refusée plus haut — slug inconnu,
    # formation sans programme — n'a rien coûté : elle n'est pas comptée.
    limitation.enregistrer(ACHATS_PAR_HEURE, adresse_ip)

    try:
        session = stripe_api.creer_paiement_de_formation(
            formation=formation, email=email
        )
    except stripe_api.PaiementIndisponible as refus:
        # Le slug de la FORMATION trouvée, pas la saisie du visiteur ; et le
        # motif est une phrase à nous, pas le message du prestataire.
        _log.error("Achat de la formation %s impossible : %s", formation.slug, refus)
        return _refus(str(refus), "paiement_indisponible", 503)

    # Le panier est noté AVANT que la personne ne parte payer : celui qui
    # n'aboutit pas est justement celui qu'on veut voir.
    remise.noter_la_tentative(session=session, formation=formation, email=email)
    return JsonResponse({"adresse": session.adresse})


@csrf_exempt
@require_POST
def retour(request: HttpRequest) -> HttpResponse:
    """L'acheteur revient du paiement : on vérifie, on livre, on ouvre l'accès.

    On n'attend PAS le webhook : Stripe redirige le navigateur et poste son
    événement en parallèle, sans ordre garanti. La livraison est rejouable ;
    celui des deux qui arrive d'abord livre, l'autre ne fait rien.

    L'identifiant de session ne prouve rien par lui-même — il arrive par
    l'adresse de retour, donc de l'extérieur. La session est RELUE chez le
    prestataire, et `livrer_la_formation` refuse tout ce qui n'est pas payé.

    La réponse ne porte AUCUN contenu de leçon : le programme se lit dans
    l'espace, derrière la session que cette vue ouvre — ou non.
    """
    from paiement import formations as remise  # noqa: PLC0415
    from paiement import stripe_api  # noqa: PLC0415
    from paiement.achats import reference_abregee  # noqa: PLC0415

    # Plafond, corps, FORME de l'identifiant : la garde commune aux trois
    # pages de retour, avant tout appel au prestataire (`retours`).
    try:
        identifiant = retours.session_presentee(request)
    except retours.Refus as refus:
        return _refus(refus.message, refus.code, refus.statut)

    try:
        session = stripe_api.relire_la_session(identifiant)
    except stripe_api.PaiementIndisponible as refus:
        return _refus(str(refus), "session_illisible", 503)

    # Une session de boutique ou d'étude présentée ici serait livrée comme une
    # formation : chaque page de retour ne traite que SON achat.
    if not remise.est_un_achat_de_formation(session):
        return _refus(
            "Ce paiement ne concerne pas une formation.", "achat_autre", 409
        )

    try:
        resultat = remise.livrer_la_formation(session)
    except remise.AchatInexploitable as refus:
        # L'identifiant est celui que `retours` a validé, et il est abrégé ;
        # le motif est écrit par nous, sans adresse.
        _log.error(
            "Retour de formation inexploitable (%s) : %s",
            reference_abregee(identifiant), refus,
        )
        return _refus(
            "Votre paiement n'a pas pu être rattaché à votre formation. S'il "
            "a bien été débité, écrivez-nous à contact@evkha.fr : nous "
            "ouvrons votre accès immédiatement.",
            "achat_inexploitable",
            409,
        )

    if resultat.nouveau:
        remise.prevenir_l_acheteur(resultat)

    # Le prestataire prouve qu'une carte a été encaissée — pas que le payeur
    # possède l'adresse qu'il a saisie. La session n'est ouverte que sur le
    # compte que CE paiement vient de créer, une seule fois
    # (`authentification.ouvrir_la_session_d_un_achat`) ; sinon l'acheteur se
    # connecte, ou suit le lien de son courriel.
    #
    # Sans compte né de ce paiement — le rejeu d'une session déjà livrée à
    # quelqu'un qui avait un compte —, il n'y a rien à ouvrir.
    jeton_clair = (
        authentification.ouvrir_la_session_d_un_achat(resultat.compte, identifiant)
        if resultat.compte is not None
        else None
    )
    return JsonResponse({
        "jeton": jeton_clair,
        "connexion_requise": jeton_clair is None,
        "titre": resultat.formation.titre,
        "slug": resultat.formation.slug,
    })

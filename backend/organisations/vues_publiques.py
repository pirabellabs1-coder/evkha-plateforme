"""Ce que le public voit avant d'avoir un compte.

La page partenaires est ouverte : quelqu'un qui découvre l'offre n'a ni jeton,
ni organisation. Ces vues sont donc les seules de l'application à répondre
sans authentification — et c'est précisément pour ça qu'elles vivent dans un
fichier séparé de `vues_espace`, où **tout** est nominatif. Mélanger les deux
ferait qu'un jour une vue privée hériterait du décorateur public par
inadvertance.

Elles n'exposent que le catalogue commercial. Aucune donnée d'organisation,
aucun compteur, aucun identifiant : rien qui n'est pas déjà sur la plaquette.
"""
from __future__ import annotations

import json
import logging

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import authentification, inscription
from .models import Formule

_log = logging.getLogger(__name__)

#: Inscriptions autorisées par adresse IP et par heure.
#:
#: Un point d'entrée ouvert qui crée des comptes est une invitation à en créer
#: mille. Le plafond est volontairement bas : une personne s'inscrit une fois,
#: et le seul cas légitime de répétition — plusieurs collaborateurs d'un même
#: bureau — passe par l'invitation depuis l'espace, pas par ce formulaire.
INSCRIPTIONS_PAR_HEURE = 5


@require_GET
def formules_publiques(request: HttpRequest) -> HttpResponse:
    """Catalogue des formules, pour la page partenaires.

    Même source que `vues_espace.formules` : la table. La page publique et
    l'espace client ne peuvent donc pas afficher deux tarifs différents
    (règle 5) — c'était le risque en recopiant les prix dans le React.

    Le coût par livrable inclus est **calculé ici**, jamais stocké : c'est un
    rapport entre deux champs de la formule. Le mémoriser en ferait une
    troisième valeur susceptible de contredire les deux autres.
    """
    formules = Formule.objects.filter(active=True).order_by("rang", "prix_mensuel_cents")
    return JsonResponse({
        "formules": [
            {
                "code": f.code,
                "libelle": f.libelle,
                "credits_par_echeance": f.credits_par_echeance,
                "prix_mensuel_cents": f.prix_mensuel_cents,
                "prix_credit_supplementaire_cents": f.prix_credit_supplementaire_cents,
                "cout_par_livrable_cents": (
                    round(f.prix_mensuel_cents / f.credits_par_echeance)
                    if f.credits_par_echeance
                    else 0
                ),
                "devise": f.devise,
                "avantages": list(f.avantages or []),
                "mise_en_avant": f.mise_en_avant,
            }
            for f in formules
        ],
    })


def _refus(message: str, code: str, statut: int = 400) -> HttpResponse:
    """Refus lisible PAR LE VISITEUR, avec un code pour l'interface.

    Le message est écrit pour quelqu'un qui remplit un formulaire ; le code
    permet à l'interface de désigner le champ fautif sans comparer une phrase
    — un texte que l'on compare finit toujours par être reformulé.
    """
    return JsonResponse({"erreur": message, "code": code}, status=statut)


def _adresse(request: HttpRequest) -> str:
    """Adresse d'origine, telle que le proxy la transmet.

    Derrière nginx, `REMOTE_ADDR` vaut l'adresse du proxy et serait donc la
    même pour tout le monde : le plafond horaire s'appliquerait alors à
    l'ensemble des visiteurs au lieu de chacun.
    """
    transmise = str(request.META.get("HTTP_X_FORWARDED_FOR", "") or "")
    if transmise:
        return transmise.split(",")[0].strip()
    return str(request.META.get("REMOTE_ADDR", "") or "inconnue")


@csrf_exempt
@require_POST
def inscrire(request: HttpRequest) -> HttpResponse:
    """Ouvre un compte depuis la page partenaires, sans intervention humaine.

    **Aucun crédit n'est délivré.** Le prestataire de paiement n'est pas
    branché : la formule choisie est enregistrée comme demande, et EVKHA
    l'active à l'encaissement. Créditer ici ferait des livrables gratuits à qui
    remplit un formulaire — voir `inscription.ouvrir_compte`.

    La session est ouverte dans la foulée : renvoyer la personne vers un écran
    de connexion juste après lui avoir fait choisir un mot de passe est une
    friction gratuite, et la première chose qu'elle veut voir est son espace.
    """
    try:
        charge = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return _refus("Requête illisible.", "corps_invalide")
    if not isinstance(charge, dict):
        return _refus("Requête illisible.", "corps_invalide")

    cle = f"inscription:{_adresse(request)}"
    # `get_or_set` peut rendre None si le cache est indisponible ; on lit alors
    # zero plutot que de laisser une comparaison echouer. Un cache en panne ne
    # doit pas fermer l'inscription — il fait seulement tomber la protection,
    # et c'est le bon arbitrage : le plafond protege d'un abus, il n'est pas la
    # condition d'un service legitime.
    tentatives = cache.get_or_set(cle, 0, 3600) or 0
    if int(tentatives) >= INSCRIPTIONS_PAR_HEURE:
        return _refus(
            "Trop de créations de compte depuis cette connexion. Réessayez "
            "dans une heure, ou écrivez-nous à contact@evkha.fr.",
            "trop_de_tentatives",
            429,
        )

    raison_sociale = str(charge.get("raison_sociale", "")).strip()
    email = str(charge.get("email", "")).strip().lower()
    mot_de_passe = str(charge.get("mot_de_passe", ""))

    try:
        inscription.controler_saisie(
            raison_sociale=raison_sociale, email=email, mot_de_passe=mot_de_passe
        )
        inscription.refuser_si_deja_membre(email, nommer_organisation=False)
        formule = inscription.formule_ou_refus(str(charge.get("formule", "")))
        ouverture = inscription.ouvrir_compte(
            raison_sociale=raison_sociale,
            email=email,
            mot_de_passe=mot_de_passe,
            prenom=str(charge.get("prenom", "")).strip(),
            nom=str(charge.get("nom", "")).strip(),
            formule=formule,
            # Rien n'est encaisse : on enregistre l'intention, on n'active pas.
            activer_abonnement=False,
        )
    except inscription.InscriptionRefuseeError as refus:
        return _refus(str(refus), refus.code, refus.statut)

    # Le compteur n'avance QU'APRES une inscription reussie : compter les
    # echecs punirait quelqu'un qui se trompe de mot de passe cinq fois.
    try:
        cache.incr(cle)
    except ValueError:  # cle expiree entre le controle et l'increment
        cache.set(cle, 1, 3600)

    jeton_clair, _ = authentification.ouvrir_session(email, mot_de_passe)
    _log.info(
        "Inscription publique : organisation %s, formule demandee %s",
        ouverture.organisation.id,
        formule.code if formule else "aucune",
    )

    return JsonResponse(
        {
            "jeton": jeton_clair,
            "organisation": {
                "id": str(ouverture.organisation.id),
                "raison_sociale": ouverture.organisation.raison_sociale,
            },
            "formule_demandee": formule.code if formule else None,
            # Dit explicitement ce qui n'a PAS eu lieu : l'interface doit
            # pouvoir annoncer « souscription en cours de validation » plutot
            # que laisser croire a un abonnement actif.
            "abonnement_actif": False,
            "demande_id": str(ouverture.demande.id) if ouverture.demande else None,
        },
        status=201,
    )

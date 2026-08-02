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
import secrets

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import (
    authentification,
    courriels,
    google,
    identifiants,
    inscription,
    limitation,
)
from .models import Formule

_log = logging.getLogger(__name__)

#: Inscriptions autorisées par adresse IP et par heure.
#:
#: Un point d'entrée ouvert qui crée des comptes est une invitation à en créer
#: mille. Le plafond est volontairement bas : une personne s'inscrit une fois,
#: et le seul cas légitime de répétition — plusieurs collaborateurs d'un même
#: bureau — passe par l'invitation depuis l'espace, pas par ce formulaire.
INSCRIPTIONS_PAR_HEURE = limitation.Plafond(
    "inscription", maximum=5, fenetre_s=3600
)


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

    adresse = limitation.adresse_client(request)
    if limitation.depasse(INSCRIPTIONS_PAR_HEURE, adresse):
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
    limitation.enregistrer(INSCRIPTIONS_PAR_HEURE, adresse)

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


@require_GET
def reglages_publics(request: HttpRequest) -> HttpResponse:
    """Ce que l'interface publique doit savoir avant d'afficher quoi que ce soit.

    Aujourd'hui : la connexion Google est-elle utilisable, et sous quel
    identifiant d'application. Sans cet appel, l'interface afficherait un
    bouton « Continuer avec Google » qui échouerait faute de réglage — pire que
    pas de bouton, parce qu'il fait douter du reste de la page (règle 1).

    L'identifiant OAuth est PUBLIC par construction : le navigateur l'envoie à
    Google. Ce n'est pas un secret qui fuit ici.
    """
    return JsonResponse({
        "google": {
            "actif": google.configure(),
            "client_id": google.identifiant_client(),
        },
    })


@csrf_exempt
@require_POST
def google_session(request: HttpRequest) -> HttpResponse:
    """Connecte — ou inscrit — depuis un compte Google.

    Un SEUL point d'entrée pour les deux : au moment où la personne clique, ni
    elle ni nous ne savons si elle a déjà un compte. Deux points d'entrée
    obligeraient l'interface à deviner, et à se tromper une fois sur deux.

    - **adresse connue** → session ouverte, et les champs d'identité VIDES du
      contact sont complétés par ce que Google atteste ;
    - **adresse inconnue** → compte créé, comme par le formulaire : aucun
      crédit, l'intention enregistrée comme demande.

    Le compte créé par Google reçoit un mot de passe aléatoire qu'il ne connaît
    pas. Il n'en a pas besoin pour entrer, et la personne peut en définir un
    par la procédure d'oubli. Laisser un mot de passe VIDE serait pire : le
    compte deviendrait accessible à quiconque poste une chaîne vide.
    """
    try:
        charge = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return _refus("Requête illisible.", "corps_invalide")
    if not isinstance(charge, dict):
        return _refus("Requête illisible.", "corps_invalide")

    try:
        identite = google.verifier(str(charge.get("jeton_google", "")))
    except google.GoogleRefuseError as refus:
        return _refus(str(refus), refus.code, refus.statut)

    from .models import CompteClient  # noqa: PLC0415 — evite un cycle a l'import

    compte = (
        CompteClient.objects.select_related("customer")
        .filter(user__username__iexact=identite.email, actif=True)
        .first()
    )

    if compte is not None:
        # La plateforme prend en compte ce que Google atteste, sans jamais
        # ecraser ce que la personne a saisi elle-meme.
        ecrits = google.completer_le_contact(compte.customer, identite)
        jeton_clair = authentification.ouvrir_session_sans_mot_de_passe(compte)
        _log.info(
            "Connexion Google : %s (champs completes : %s)",
            identite.email, ", ".join(ecrits) or "aucun",
        )
        return JsonResponse({
            "jeton": jeton_clair,
            "compte_cree": False,
            "champs_completes": ecrits,
        })

    # Compte inconnu : on inscrit, avec les memes garanties que le formulaire.
    adresse = limitation.adresse_client(request)
    if limitation.depasse(INSCRIPTIONS_PAR_HEURE, adresse):
        return _refus(
            "Trop de créations de compte depuis cette connexion. Réessayez "
            "dans une heure, ou écrivez-nous à contact@evkha.fr.",
            "trop_de_tentatives",
            429,
        )

    raison_sociale = str(charge.get("raison_sociale", "")).strip()
    if not raison_sociale:
        # On NE DEVINE PAS la raison sociale a partir de l'adresse : une
        # organisation nommee « gmail » apparaitrait sur les documents remis
        # aux clients de l'abonne. L'interface redemande le champ.
        return _refus(
            "Indiquez la raison sociale pour créer votre espace.",
            "raison_sociale_manquante",
        )

    try:
        inscription.refuser_si_deja_membre(
            identite.email, nommer_organisation=False
        )
        formule = inscription.formule_ou_refus(str(charge.get("formule", "")))
        ouverture = inscription.ouvrir_compte(
            raison_sociale=raison_sociale,
            email=identite.email,
            # Aleatoire et jamais communique : la personne entre par Google.
            mot_de_passe=secrets.token_urlsafe(32),
            prenom=identite.prenom,
            nom=identite.nom,
            formule=formule,
            activer_abonnement=False,
            message="Souscription demandée depuis la page partenaires (compte Google).",
        )
    except inscription.InscriptionRefuseeError as refus:
        return _refus(str(refus), refus.code, refus.statut)

    limitation.enregistrer(INSCRIPTIONS_PAR_HEURE, adresse)

    compte = CompteClient.objects.select_related("customer").get(
        user__username__iexact=identite.email
    )
    jeton_clair = authentification.ouvrir_session_sans_mot_de_passe(compte)
    _log.info(
        "Inscription Google : organisation %s, formule demandee %s",
        ouverture.organisation.id, formule.code if formule else "aucune",
    )
    return JsonResponse(
        {
            "jeton": jeton_clair,
            "compte_cree": True,
            "organisation": {
                "id": str(ouverture.organisation.id),
                "raison_sociale": ouverture.organisation.raison_sociale,
            },
            "formule_demandee": formule.code if formule else None,
            "abonnement_actif": False,
            "demande_id": str(ouverture.demande.id) if ouverture.demande else None,
        },
        status=201,
    )


# ── Mot de passe : définir, oublier ──────────────────────────────────────────

#: Demandes de réinitialisation tolérées depuis une même adresse, par heure.
#:
#: Sans plafond, ce point d'entrée devient un moyen d'inonder la boîte de
#: quelqu'un dont on connaît l'adresse — et de faire passer nos envois pour du
#: courrier indésirable auprès des fournisseurs de messagerie.
REINITIALISATIONS_PAR_HEURE = limitation.Plafond(
    "reinitialisation", maximum=5, fenetre_s=3600
)


@csrf_exempt
@require_POST
def mot_de_passe_oublie(request: HttpRequest) -> HttpResponse:
    """Envoie un lien de réinitialisation — et répond toujours la même chose.

    **La réponse ne dit jamais si l'adresse est connue.** Distinguer les deux
    transformerait ce formulaire en annuaire : on y saisirait des adresses
    jusqu'à trouver lesquelles ont un compte, c'est-à-dire qui travaille avec
    la plateforme. C'est la même raison qui fait que `connexion` refuse d'un
    seul message.

    Il n'existait aucune route de ce genre : `set_password` n'apparaissait
    qu'une fois dans tout le dépôt, à la création du compte. Quelqu'un qui
    perdait son mot de passe était enfermé dehors définitivement.
    """
    try:
        charge = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return _refus("Requête illisible.", "corps_invalide")
    if not isinstance(charge, dict):
        return _refus("Requête illisible.", "corps_invalide")

    adresse = limitation.adresse_client(request)
    if limitation.depasse(REINITIALISATIONS_PAR_HEURE, adresse):
        return _refus(
            "Trop de demandes depuis cette connexion. Réessayez dans une heure.",
            "trop_de_tentatives",
            429,
        )
    limitation.enregistrer(REINITIALISATIONS_PAR_HEURE, adresse)

    email = str(charge.get("email", "")).strip().lower()
    from .models import CompteClient  # noqa: PLC0415 — evite un cycle a l'import

    compte = (
        CompteClient.objects.select_related("user", "customer")
        .filter(user__username__iexact=email, actif=True)
        .first()
    )
    if compte is not None:
        courriels.reinitialiser_le_mot_de_passe(
            destinataire=compte.customer.email,
            lien=identifiants.lien_pour(compte),
        )
    else:
        # Journalisé, jamais renvoyé : l'exploitation doit pouvoir constater
        # qu'une personne se trompe d'adresse, sans que l'appelant l'apprenne.
        _log.info("Reinitialisation demandee pour une adresse inconnue.")

    return JsonResponse({
        "message": (
            "Si un compte existe pour cette adresse, un lien vient d'être "
            "envoyé. Vérifiez aussi vos indésirables."
        )
    })


@csrf_exempt
@require_POST
def definir_mot_de_passe(request: HttpRequest) -> HttpResponse:
    """Pose le mot de passe depuis un lien reçu par courriel.

    Sert aux DEUX parcours — activer une invitation, réinitialiser un mot de
    passe oublié — parce que c'est le même geste et que le jeton porte déjà la
    distinction. En faire deux routes ferait diverger les contrôles.

    La session est ouverte dans la foulée : renvoyer vers un écran de connexion
    juste après avoir fait choisir un mot de passe est une friction gratuite.
    """
    try:
        charge = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return _refus("Requête illisible.", "corps_invalide")
    if not isinstance(charge, dict):
        return _refus("Requête illisible.", "corps_invalide")

    try:
        compte = identifiants.compte_du_lien(
            str(charge.get("id", "")), str(charge.get("jeton", ""))
        )
    except identifiants.LienInvalideError as refus:
        return _refus(str(refus), "lien_invalide", 400)

    try:
        identifiants.definir_mot_de_passe(
            compte, str(charge.get("mot_de_passe", ""))
        )
    except identifiants.MotDePasseRefuseError as refus:
        return _refus(str(refus), "mot_de_passe_faible", 400)

    jeton_clair = authentification.ouvrir_session_sans_mot_de_passe(compte)
    return JsonResponse({"jeton": jeton_clair, "email": compte.customer.email})

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


#: Ouvertures de paiement autorisées par adresse IP et par heure.
#:
#: Plus large que les inscriptions : quelqu'un qui hésite entre deux livrables
#: ouvre légitimement deux ou trois paiements, et en abandonne. Le plafond ne
#: protège que d'un script qui ouvrirait des sessions Stripe en boucle.
PAIEMENTS_PAR_HEURE = limitation.Plafond("achat", maximum=20, fenetre_s=3600)


@require_GET
def livrables_publics(request: HttpRequest) -> HttpResponse:
    """Les livrables achetables à l'unité, avec leur tarif.

    Même principe que `formules_publiques` : le prix vient de la table, jamais
    d'une constante recopiée dans le React. Une page de vente qui annonce
    149 EUR et un paiement qui en prélève 189 est le pire défaut possible sur
    ce parcours, et c'est exactement ce que produit une seconde source (règle 5).

    Les offres sans tarif à l'unité — abonnements, crédits supplémentaires — ne
    sortent pas d'ici : elles ne se vendent pas seules.

    **Le nombre de chapitres n'est PAS rendu ici, et c'est délibéré.** J'avais
    commencé par le lire du plan de production, au nom de la règle 5. Mesuré :
    le plan compte 23 entrées pour l'étude de marché et 10 pour l'étude de
    concurrence, quand `evkha.fr` en annonce 22 et 9. L'écart n'est pas une
    erreur — le plan porte une fiche projet en ouverture et une annexe, qui ne
    sont pas vendues comme des chapitres.

    Ce sont donc deux vérités différentes : ce qu'on PRODUIT, et ce qu'on
    ANNONCE. Les confondre aurait réécrit l'argumentaire commercial de la
    cliente au premier chargement de page, sans que personne l'ait décidé. Le
    nombre annoncé vit avec le reste de l'argumentaire, dans `contenu.ts`.
    """
    from catalog.models import Offer  # noqa: PLC0415 — evite un cycle a l'import

    offres = (
        Offer.objects.filter(is_active=True, prix_unitaire_cents__gt=0)
        .exclude(deliverable_type="")
        .order_by("prix_unitaire_cents")
    )
    return JsonResponse({
        "livrables": [
            {
                "slug": o.slug,
                "libelle": o.name,
                "type": o.deliverable_type,
                "prix_cents": o.prix_unitaire_cents,
            }
            for o in offres
        ],
    })


@csrf_exempt
@require_POST
def acheter(request: HttpRequest) -> HttpResponse:
    """Ouvre le paiement d'UN livrable, sans compte préalable.

    Rien de ce que le navigateur envoie ne fixe un prix : on ne lit qu'un slug,
    et le tarif est celui du catalogue. Accepter un montant depuis le client
    reviendrait à laisser choisir combien payer — la même règle que l'achat de
    crédits, et pour la même raison.

    L'adresse est facultative ici : Stripe la collecte de toute façon sur sa
    propre page, et c'est celle-là qui fait foi au retour. La demander avant
    sert seulement à pré-remplir, pour épargner une saisie.
    """
    from paiement import stripe_api  # noqa: PLC0415

    from catalog.models import Offer  # noqa: PLC0415

    try:
        charge = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return _refus("Requête illisible.", "corps_invalide")
    if not isinstance(charge, dict):
        return _refus("Requête illisible.", "corps_invalide")

    adresse_ip = limitation.adresse_client(request)
    if limitation.depasse(PAIEMENTS_PAR_HEURE, adresse_ip):
        return _refus(
            "Trop de paiements ouverts depuis cette connexion. Réessayez dans "
            "une heure, ou écrivez-nous à contact@evkha.fr.",
            "trop_de_tentatives",
            429,
        )

    slug = str(charge.get("livrable") or "").strip()
    offre = Offer.objects.filter(
        slug=slug, is_active=True, prix_unitaire_cents__gt=0
    ).first()
    if offre is None:
        return _refus(
            "Ce livrable n'est pas disponible à l'achat.", "livrable_inconnu", 404
        )

    try:
        session = stripe_api.creer_paiement_de_livrable(
            offre=offre, email=str(charge.get("email") or "").strip()
        )
    except stripe_api.PaiementIndisponible as refus:
        _log.error("Achat de %s impossible : %s", slug, refus)
        return _refus(str(refus), "paiement_indisponible", 503)

    return JsonResponse({"adresse": session.adresse})


@csrf_exempt
@require_POST
def retour_de_paiement(request: HttpRequest) -> HttpResponse:
    """L'acheteur revient de Stripe : on vérifie, on livre, on ouvre la session.

    **On n'attend pas le webhook.** Stripe redirige le navigateur et poste son
    événement en parallèle, sans ordre garanti. Faire patienter quelqu'un qui
    vient de payer devant un écran de chargement, en espérant qu'un serveur
    tiers se manifeste, serait le pire moment du parcours pour lui demander de
    la confiance. Le traitement est idempotent : celui des deux qui arrive
    d'abord livre, l'autre ne fait rien.

    **L'identifiant de session ne prouve rien par lui-même** — il arrive par
    l'adresse de retour, donc de l'extérieur. C'est Stripe qui dit si la
    session est payée, et `livrer_l_achat` refuse tout ce qui ne l'est pas.
    """
    from paiement import achats, stripe_api  # noqa: PLC0415

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

    if not achats.est_un_achat_de_livrable(session):
        return _refus("Ce paiement ne concerne pas un livrable.", "achat_autre", 409)

    try:
        achat = achats.livrer_l_achat(session)
    except achats.AchatInexploitable as refus:
        _log.error("Retour de paiement inexploitable (%s) : %s", identifiant, refus)
        return _refus(
            "Votre paiement a bien été reçu, mais votre espace n'a pas pu être "
            "ouvert. Écrivez-nous à contact@evkha.fr, nous le faisons "
            "immédiatement.",
            "achat_inexploitable",
            409,
        )

    if achat.nouveau:
        achats.prevenir_l_acheteur(achat)

    # C'est Stripe qui a prouvé l'identité — il a encaissé une carte et
    # collecté l'adresse. La personne n'a pas de mot de passe et n'en a pas
    # besoin pour entrer ; elle en choisira un depuis le courriel.
    jeton_clair = authentification.ouvrir_session_sans_mot_de_passe(achat.compte)
    return JsonResponse({
        "jeton": jeton_clair,
        "livrable": achat.offre.deliverable_type,
        "libelle": achat.offre.name,
    })


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
        offre = inscription.livrable_ou_refus(str(charge.get("livrable", "")))
        ouverture = inscription.ouvrir_compte(
            raison_sociale=raison_sociale,
            email=email,
            mot_de_passe=mot_de_passe,
            prenom=str(charge.get("prenom", "")).strip(),
            nom=str(charge.get("nom", "")).strip(),
            formule=formule,
            # Rien n'est encaisse : on enregistre l'intention, on n'active pas.
            activer_abonnement=False,
            # Un compte ouvert pour acheter UNE etude n'est pas un compte
            # d'abonne : il ne verra ni formules, ni achat de credits.
            a_l_unite=offre is not None,
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
            # L'etude a payer, s'il y en a une. L'interface enchaine dessus :
            # le compte est ouvert, le paiement s'ouvre dans la foulee. On rend
            # le slug plutot qu'un booleen pour que la page n'ait pas a relire
            # son adresse — deux lectures de la meme intention finissent
            # toujours par diverger.
            "livrable_demande": offre.slug if offre else None,
            # Dit explicitement ce qui n'a PAS eu lieu : l'interface doit
            # pouvoir annoncer « souscription en cours de validation » plutot
            # que laisser croire a un abonnement actif.
            "abonnement_actif": False,
            # Plus aucune demande n'est ouverte a l'inscription : le
            # visiteur paie lui-meme. La cle reste, a `null`, pour ne pas
            # casser une page encore ouverte dans un navigateur.
            "demande_id": None,
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
        # Le livrable traverse ce chemin comme la formule. Sans cela, quelqu'un
        # qui clique « Continuer avec Google » depuis une page d'achat obtenait
        # un compte d'ABONNE, sans paiement et sans etude : le parcours le plus
        # rapide etait aussi le seul qui ne menait nulle part.
        offre = inscription.livrable_ou_refus(str(charge.get("livrable", "")))
        ouverture = inscription.ouvrir_compte(
            raison_sociale=raison_sociale,
            email=identite.email,
            # Aleatoire et jamais communique : la personne entre par Google.
            mot_de_passe=secrets.token_urlsafe(32),
            prenom=identite.prenom,
            nom=identite.nom,
            formule=formule,
            activer_abonnement=False,
            a_l_unite=offre is not None,
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
            "livrable_demande": offre.slug if offre else None,
            "abonnement_actif": False,
            # Plus aucune demande n'est ouverte a l'inscription : le
            # visiteur paie lui-meme. La cle reste, a `null`, pour ne pas
            # casser une page encore ouverte dans un navigateur.
            "demande_id": None,
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


@csrf_exempt
@require_POST
def confirmer_la_nouvelle_adresse(request: HttpRequest) -> HttpResponse:
    """Applique le changement d'adresse porté par le lien reçu par courriel.

    **Publique**, et il le faut : la personne clique depuis sa boîte, souvent
    depuis un autre appareil que celui où sa session est ouverte. Exiger un
    jeton de session rendrait le lien inutilisable pour ceux qui en ont le plus
    besoin — précisément ceux qui ont perdu l'accès à l'ancienne adresse.

    Ce n'est pas un relâchement : le lien EST la preuve. Il est signé par nous,
    valable trois jours, et cesse de valoir dès que l'adresse du compte n'est
    plus celle qu'il a signée — donc dès qu'il a servi une fois. Il a fallu, en
    amont, le mot de passe actuel pour l'obtenir.
    """
    try:
        charge = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return _refus("Requête illisible.", "corps_invalide")
    if not isinstance(charge, dict):
        return _refus("Requête illisible.", "corps_invalide")

    try:
        compte, _ancienne = identifiants.appliquer_changement_d_adresse(
            str(charge.get("jeton", ""))
        )
    except identifiants.LienInvalideError as refus:
        return _refus(str(refus), "lien_invalide", 400)
    except identifiants.AdresseRefuseeError as refus:
        # Trois jours séparent la demande de ce clic : quelqu'un a pu prendre
        # l'adresse entre-temps. On le dit plutôt que de renvoyer un « lien
        # invalide » qui enverrait chercher au mauvais endroit (règle 2).
        return _refus(str(refus), "adresse_refusee", 409)

    return JsonResponse({"email": compte.customer.email})

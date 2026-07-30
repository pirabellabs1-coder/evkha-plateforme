"""API de l'espace client (lot 4, §9).

Toutes les vues sont **cloisonnées par organisation**. C'est la propriété la
plus importante du module : une agence ne doit jamais voir le portefeuille, les
clients finaux ou les livrables d'une autre. Le cloisonnement ne repose pas sur
un filtre que chaque vue devrait penser à écrire, mais sur un décorateur qui
résout l'organisation depuis le jeton et la passe en argument. Une vue ne peut
donc pas *oublier* de filtrer : elle n'a jamais accès à autre chose.

Les droits du §12 sont vérifiés par le même décorateur, contre la table unique
de `services.DROITS`.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from django.core.files.base import ContentFile
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from customers.models import Customer
from documents.models import ArtifactKind, DocumentArtifact
from generation.models import GenerationJob

from . import commandes, credits, fichiers, formulaires, services, suivi
from .authentification import (
    AuthentificationRefuseeError,
    compte_du_jeton,
    fermer_session,
    ouvrir_session,
    revoquer_tous_les_jetons,
)
from .models import (
    CategorieFichier,
    ClientFinal,
    DemandeCommerciale,
    Formule,
    MembreOrganisation,
    Organisation,
    PieceJointe,
    RoleOrganisation,
    StatutAbonnement,
    StatutDemande,
    TypeDemande,
)

_log = logging.getLogger(__name__)


def _jeton(request: HttpRequest) -> str:
    entete = request.headers.get("Authorization", "")
    return entete[7:].strip() if entete.lower().startswith("bearer ") else ""


def _refus(message: str, code: str, statut: int) -> JsonResponse:
    return JsonResponse({"error": message, "code": code}, status=statut)


def espace(action: str = "") -> Callable[..., Any]:
    """Résout le membre et son organisation depuis le jeton, puis vérifie le droit.

    La vue décorée reçoit `(request, membre, organisation, ...)`. Elle n'a aucun
    moyen d'accéder à une autre organisation : c'est ce qui rend le cloisonnement
    structurel plutôt que déclaratif.
    """

    def decorateur(vue: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
        @wraps(vue)
        def enveloppe(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            compte = compte_du_jeton(_jeton(request))
            if compte is None:
                return _refus("Authentification requise.", "unauthorized", 401)

            membre = (
                MembreOrganisation.objects.select_related("organisation", "customer")
                .filter(customer=compte.customer, revoque_le__isnull=True)
                .first()
            )
            if membre is None:
                return _refus(
                    "Aucune organisation active pour ce compte.", "sans_organisation", 403
                )
            if action and not services.peut(membre, action):
                return _refus(
                    f"Votre rôle ne permet pas l'action « {action} ».", "interdit", 403
                )
            return vue(request, membre, membre.organisation, *args, **kwargs)

        return enveloppe

    return decorateur


def _corps(request: HttpRequest) -> dict[str, Any]:
    """Charge JSON de la requête, ou dictionnaire vide si elle est illisible.

    `UnicodeDecodeError` est attrapée au même titre que `JSONDecodeError` : un
    corps envoyé dans un encodage autre qu'UTF-8 la lève, et elle remontait en
    erreur 500. Un client mal configuré doit recevoir un refus explicite, pas
    une page d'erreur serveur — constaté en envoyant un questionnaire accentué
    depuis un terminal Windows.
    """
    try:
        charge = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return charge if isinstance(charge, dict) else {}


# ── Session ──────────────────────────────────────────────────────────────────


@csrf_exempt
@require_http_methods(["POST"])
def connexion(request: HttpRequest) -> HttpResponse:
    """Ouvre une session et renvoie le jeton. Le jeton n'est lisible qu'ici."""
    charge = _corps(request)
    try:
        jeton, objet = ouvrir_session(
            str(charge.get("email", "")), str(charge.get("mot_de_passe", ""))
        )
    except AuthentificationRefuseeError as refus:
        return _refus(str(refus), "identifiants_invalides", 401)
    return JsonResponse({"jeton": jeton, "expire_le": objet.expire_le.isoformat()})


@csrf_exempt
@require_http_methods(["POST"])
def deconnexion(request: HttpRequest) -> HttpResponse:
    """Révoque le jeton courant. Renvoie 204 même si le jeton était déjà mort.

    Une déconnexion doit toujours réussir du point de vue de l'appelant :
    signaler « ce jeton n'existait pas » n'aiderait personne et renseignerait
    un attaquant.
    """
    fermer_session(_jeton(request))
    return HttpResponse(status=204)


# ── Compte et organisation ───────────────────────────────────────────────────


@require_http_methods(["GET"])
@espace()
def moi(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Tout ce dont l'interface a besoin au chargement : identité, rôle, solde, formule."""
    abonnement = (
        organisation.abonnements.select_related("formule")
        .filter(statut=StatutAbonnement.ACTIF)
        .first()
    )
    disponible = credits.solde(organisation)
    return JsonResponse({
        "utilisateur": {
            "email": membre.customer.email,
            "prenom": membre.customer.first_name,
            "nom": membre.customer.last_name,
            "role": membre.role,
            "droits": sorted(services.DROITS.get(str(membre.role), frozenset())),
        },
        "organisation": {
            "id": str(organisation.id),
            "raison_sociale": organisation.raison_sociale,
            "statut": organisation.statut,
            "marque_blanche": organisation.marque_blanche,
            "validation_socle_par_client": organisation.validation_socle_par_client,
        },
        "credits": {
            "solde": disponible,
            "seuil_alerte": organisation.seuil_alerte_credits,
            "alerte": disponible <= organisation.seuil_alerte_credits,
        },
        "abonnement": None if abonnement is None else {
            "formule": abonnement.formule.libelle,
            "code": abonnement.formule.code,
            "credits_par_echeance": abonnement.formule.credits_par_echeance,
            "prix_mensuel_cents": abonnement.formule.prix_mensuel_cents,
            "devise": abonnement.formule.devise,
            "debut_le": abonnement.debut_le.isoformat(),
            "derniere_periode_dotee": abonnement.derniere_periode_dotee,
        },
    })


# ── Crédits ──────────────────────────────────────────────────────────────────


@require_http_methods(["GET"])
@espace("consulter_livrables")
def journal_credits(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Consommation ligne par ligne (§9.6). Le solde courant accompagne le journal.

    Le solde est recalculé ici plutôt que déduit côté interface : deux additions
    du même journal finiraient par ne pas dire la même chose (règle 5).
    """
    limite = min(int(request.GET.get("limite", 100) or 100), 500)
    mouvements = (
        credits.portefeuille_de(organisation)
        .mouvements.all()
        .order_by("-created_at")[:limite]
    )
    return JsonResponse({
        "solde": credits.solde(organisation),
        "mouvements": [
            {
                "id": str(m.id),
                "date": m.created_at.isoformat(),
                "type": m.type,
                "quantite": m.quantite,
                "motif": m.motif,
                "reference": m.reference,
                "auteur": m.auteur,
            }
            for m in mouvements
        ],
    })


# ── Clients finaux ───────────────────────────────────────────────────────────


def _client_final_en_dict(client: ClientFinal) -> dict[str, Any]:
    return {
        "id": str(client.id),
        "raison_sociale": client.raison_sociale,
        "secteur": client.secteur,
        "pays": client.pays,
        "region": client.region,
        "ville": client.ville,
        "contact_email": client.contact_email,
        "logo_url": client.logo_url,
        "couleur_principale": client.couleur_principale,
        "couleur_secondaire": client.couleur_secondaire,
        "couleur_fond": client.couleur_fond,
        "archive": client.archive,
    }


@csrf_exempt
@require_http_methods(["GET", "POST"])
@espace()
def clients_finaux(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    if request.method == "GET":
        inclure_archives = request.GET.get("archives") == "1"
        requete = organisation.clients_finaux.all()
        if not inclure_archives:
            requete = requete.filter(archive_le__isnull=True)
        return JsonResponse({
            "clients": [
                _client_final_en_dict(c) for c in requete.order_by("raison_sociale")
            ]
        })

    if not services.peut(membre, "gerer_clients_finaux"):
        return _refus("Votre rôle ne permet pas cette action.", "interdit", 403)

    charge = _corps(request)
    raison_sociale = str(charge.get("raison_sociale", "")).strip()
    if not raison_sociale:
        return _refus("La raison sociale est obligatoire.", "champ_manquant", 400)
    if organisation.clients_finaux.filter(raison_sociale=raison_sociale).exists():
        return _refus(
            f"Une fiche « {raison_sociale} » existe déjà.", "doublon", 409
        )

    client = ClientFinal.objects.create(
        organisation=organisation,
        raison_sociale=raison_sociale,
        secteur=str(charge.get("secteur", "")).strip(),
        pays=str(charge.get("pays", "")).strip(),
        region=str(charge.get("region", "")).strip(),
        ville=str(charge.get("ville", "")).strip(),
        contact_email=str(charge.get("contact_email", "")).strip(),
        logo_url=str(charge.get("logo_url", "")).strip(),
        couleur_principale=str(charge.get("couleur_principale", "")).strip(),
        couleur_secondaire=str(charge.get("couleur_secondaire", "")).strip(),
        couleur_fond=str(charge.get("couleur_fond", "")).strip(),
    )
    return JsonResponse(_client_final_en_dict(client), status=201)


@csrf_exempt
@require_http_methods(["POST"])
@espace("gerer_clients_finaux")
def archiver_client_final(
    request: HttpRequest,
    membre: MembreOrganisation,
    organisation: Organisation,
    client_id: str,
) -> HttpResponse:
    """Archive une fiche. Les documents déjà produits restent intacts (§9.2)."""
    client = organisation.clients_finaux.filter(id=client_id).first()
    if client is None:
        return _refus("Fiche introuvable.", "introuvable", 404)
    services.archiver_client_final(client)
    return JsonResponse(_client_final_en_dict(client))


# ── Ma marque ────────────────────────────────────────────────────────────────
# L'espace client est celui d'UN abonné qui gère SES études : un seul profil de
# marque, pas une liste. Ce sont ces valeurs qui habillent ses documents.


#: Champs modifiables par le client. Liste fermée : sans elle, une charge JSON
#: contenant `statut` ou `seuil_alerte_credits` laisserait un abonné se
#: réactiver lui-même ou changer ses propres plafonds.
CHAMPS_MARQUE = (
    "raison_sociale",
    "secteur",
    "pays",
    "region",
    "ville",
    "logo_url",
    "couleur_principale",
    "couleur_secondaire",
    "couleur_fond",
    "mention_confidentialite",
)


def _marque_en_dict(organisation: Organisation) -> dict[str, Any]:
    return {champ: getattr(organisation, champ) for champ in CHAMPS_MARQUE}


@csrf_exempt
@require_http_methods(["GET", "POST"])
@espace()
def marque(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Profil et charte de l'abonné (§9.2, adapté à un abonné unique)."""
    if request.method == "GET":
        return JsonResponse(_marque_en_dict(organisation))

    if not services.peut(membre, "gerer_clients_finaux"):
        return _refus("Votre rôle ne permet pas cette action.", "interdit", 403)

    charge = _corps(request)
    inconnus = sorted(set(charge) - set(CHAMPS_MARQUE))
    if inconnus:
        # Refuser plutôt qu'ignorer : un champ silencieusement ignoré fait
        # croire à l'appelant que sa modification a été prise en compte.
        return _refus(
            f"Champs non modifiables : {', '.join(inconnus)}.", "champ_interdit", 400
        )

    raison = str(charge.get("raison_sociale", organisation.raison_sociale)).strip()
    if not raison:
        return _refus("La raison sociale est obligatoire.", "champ_manquant", 400)

    for champ in CHAMPS_MARQUE:
        if champ in charge:
            setattr(organisation, champ, str(charge[champ]).strip())
    organisation.raison_sociale = raison
    organisation.save(update_fields=[*CHAMPS_MARQUE, "updated_at"])
    return JsonResponse(_marque_en_dict(organisation))


# ── Livrables ────────────────────────────────────────────────────────────────


@require_http_methods(["GET"])
@espace("consulter_livrables")
def livrables(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Bibliothèque des documents produits pour cette organisation (§9.5).

    Le filtre porte sur `order__organisation` : un job dont la commande n'est
    pas rattachée n'apparaît pas. C'est volontaire — mieux vaut une liste
    incomplète qu'une liste qui montre le document d'une autre agence.
    """
    jobs = (
        GenerationJob.objects.filter(order__organisation=organisation)
        .select_related("order", "order__offer")
        .order_by("-created_at")[:200]
    )
    artefacts_par_job: dict[str, list[dict[str, str]]] = {}
    for artefact in DocumentArtifact.objects.filter(
        job__in=jobs, kind__in=[ArtifactKind.DOCX, ArtifactKind.PDF]
    ):
        artefacts_par_job.setdefault(str(artefact.job_id), []).append({
            "kind": artefact.kind,
            "statut": artefact.status,
            "url": artefact.download_url,
        })

    return JsonResponse({
        "livrables": [
            {
                "id": str(job.id),
                "type": job.deliverable_type,
                "statut": job.status,
                "offre": job.order.offer.name,
                "chapitres_faits": job.chapters.filter(status="done").count(),
                "cree_le": job.created_at.isoformat(),
                "termine_le": job.completed_at.isoformat() if job.completed_at else None,
                "fichiers": artefacts_par_job.get(str(job.id), []),
            }
            for job in jobs
        ]
    })


# ── Formules et demandes commerciales ────────────────────────────────────────


@require_http_methods(["GET"])
@espace()
def formules(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Catalogue des formules, avec celle en cours marquée (§9.6).

    Le coût par livrable est **calculé ici**, jamais stocké : c'est un rapport
    entre deux champs de la formule. Le mémoriser en ferait une troisième
    valeur susceptible de contredire les deux autres (règle 5).
    """
    actif = (
        organisation.abonnements.select_related("formule")
        .filter(statut=StatutAbonnement.ACTIF)
        .first()
    )
    code_actuel = actif.formule.code if actif else ""

    return JsonResponse({
        "code_actuel": code_actuel,
        "formules": [
            {
                "code": formule.code,
                "libelle": formule.libelle,
                "credits_par_echeance": formule.credits_par_echeance,
                "prix_mensuel_cents": formule.prix_mensuel_cents,
                "devise": formule.devise,
                "cout_par_livrable_cents": (
                    round(formule.prix_mensuel_cents / formule.credits_par_echeance)
                    if formule.credits_par_echeance
                    else 0
                ),
                "report_credits": formule.report_credits,
                "regenerations_offertes": formule.regenerations_offertes,
                "actuelle": formule.code == code_actuel,
            }
            for formule in Formule.objects.filter(active=True).order_by(
                "prix_mensuel_cents"
            )
        ],
    })


def _demande_en_dict(demande: DemandeCommerciale) -> dict[str, Any]:
    return {
        "id": str(demande.id),
        "type": demande.type,
        "statut": demande.statut,
        "formule_visee": demande.formule_visee.libelle if demande.formule_visee else "",
        "quantite": demande.quantite,
        "message": demande.message,
        "reponse": demande.reponse,
        "date": demande.created_at.isoformat(),
        "traitee_le": demande.traitee_le.isoformat() if demande.traitee_le else None,
    }


@csrf_exempt
@require_http_methods(["GET", "POST"])
@espace()
def demandes(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Demandes de changement de formule ou d'achat de crédits.

    Aucun encaissement : le prestataire de paiement n'est pas branché. Un
    bouton qui prétendrait débiter une carte serait un mensonge, et un bouton
    inerte une impasse. La demande est donc enregistrée, horodatée, et EVKHA la
    traite — ce qui correspond au fonctionnement actuel de l'entreprise.
    """
    if request.method == "GET":
        return JsonResponse({
            "demandes": [
                _demande_en_dict(d)
                for d in organisation.demandes.select_related("formule_visee")[:50]
            ]
        })

    if not services.peut(membre, "gerer_abonnement"):
        return _refus(
            "Seul un propriétaire peut engager l'organisation.", "interdit", 403
        )

    charge = _corps(request)
    type_demande = str(charge.get("type", ""))
    if type_demande not in TypeDemande.values:
        return _refus(
            f"Type de demande inconnu : {type_demande!r}.", "type_inconnu", 400
        )

    formule_visee = None
    if type_demande == TypeDemande.CHANGEMENT_FORMULE:
        formule_visee = Formule.objects.filter(
            code=str(charge.get("formule", "")), active=True
        ).first()
        if formule_visee is None:
            return _refus("Formule inconnue.", "formule_inconnue", 400)

    quantite = int(charge.get("quantite", 0) or 0)
    if type_demande == TypeDemande.CREDITS_ADDITIONNELS and quantite <= 0:
        return _refus(
            "Indiquez le nombre de crédits souhaités.", "quantite_manquante", 400
        )

    if organisation.demandes.filter(
        type=type_demande, statut=StatutDemande.OUVERTE
    ).exists():
        return _refus(
            "Une demande de ce type est déjà en cours de traitement.",
            "demande_en_cours",
            409,
        )

    demande = DemandeCommerciale.objects.create(
        organisation=organisation,
        demandeur=membre.customer,
        type=type_demande,
        formule_visee=formule_visee,
        quantite=quantite,
        message=str(charge.get("message", ""))[:2000],
    )
    _log.info(
        "Demande %s de %s : %s", demande.type, organisation, demande.formule_visee
    )
    return JsonResponse(_demande_en_dict(demande), status=201)


# ── Commander un document ────────────────────────────────────────────────────


@require_http_methods(["GET"])
@espace()
def catalogue(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Types commandables, coût, et ce que le solde permet (§9.3)."""
    disponible = credits.solde(organisation)
    return JsonResponse({
        "solde": disponible,
        "peut_commander": services.peut(membre, "commander"),
        "documents": [
            {**entree, "couvert": disponible >= entree["cout_credits"]}
            for entree in commandes.catalogue()
        ],
    })


@require_http_methods(["GET"])
@espace()
def formulaire(
    request: HttpRequest,
    membre: MembreOrganisation,
    organisation: Organisation,
    type_document: str,
) -> HttpResponse:
    """Questionnaire d'un type de document (§9.3).

    Le serveur déclare les questions, l'interface les affiche. Les redéclarer
    côté React les ferait diverger au premier ajout de question (règle 5).
    """
    questionnaire = formulaires.formulaire(type_document)
    if questionnaire is None:
        return _refus(
            f"Aucun questionnaire pour « {type_document} ».", "introuvable", 404
        )
    return JsonResponse(formulaires.en_dict(questionnaire))


@csrf_exempt
@require_http_methods(["POST"])
@espace("commander")
def commander(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Lance une génération. Le débit se fait au démarrage, pas ici.

    Le message d'erreur renvoyé est celui du service, écrit pour le client :
    « solde insuffisant » lui dit quoi faire, « erreur interne » non.
    """
    charge = _corps(request)
    try:
        job = commandes.creer_commande(
            organisation,
            membre.customer,
            type_document=str(charge.get("type", "")),
            saisie=charge.get("saisie", {}) or {},
        )
    except commandes.CommandeRefuseeError as refus:
        return _refus(str(refus), "commande_refusee", 400)

    # Hors de la transaction de création : une tâche consommée avant la
    # validation ne trouverait pas le job en base.
    commandes.lancer(job)
    return JsonResponse(
        {
            "job_id": str(job.id),
            "statut": job.status,
            "type": job.deliverable_type,
            "cout_credits": commandes.cout_affiche(job),
        },
        status=202,
    )


# ── Pièces jointes ───────────────────────────────────────────────────────────


def _piece_en_dict(piece: PieceJointe) -> dict[str, Any]:
    return {
        "id": str(piece.id),
        "categorie": piece.categorie,
        "nom": piece.nom_original,
        "taille_octets": piece.taille_octets,
        "type_mime": piece.type_mime,
        "date": piece.created_at.isoformat(),
        "url": piece.fichier.url if piece.fichier else "",
    }


@csrf_exempt
@require_http_methods(["GET", "POST"])
@espace()
def pieces_jointes(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Dépôt et liste des fichiers de l'organisation.

    Le format est vérifié sur les **octets**, jamais sur l'extension ni sur
    l'en-tête `Content-Type` : l'une se renomme, l'autre s'écrit à la main.
    """
    if request.method == "GET":
        requete = organisation.pieces_jointes.all()
        categorie = request.GET.get("categorie", "")
        if categorie:
            requete = requete.filter(categorie=categorie)
        return JsonResponse({"pieces": [_piece_en_dict(p) for p in requete[:100]]})

    if not services.peut(membre, "gerer_clients_finaux"):
        return _refus("Votre rôle ne permet pas cette action.", "interdit", 403)

    envoye = request.FILES.get("fichier")
    if envoye is None:
        return _refus("Aucun fichier reçu.", "fichier_manquant", 400)

    categorie = request.POST.get("categorie", CategorieFichier.DOCUMENT)
    if categorie not in CategorieFichier.values:
        return _refus(f"Catégorie inconnue : {categorie!r}.", "categorie", 400)

    contenu = envoye.read()
    # `UploadedFile.name` est optionnel : un envoi sans nom de fichier est
    # possible, et le laisser filer ferait échouer la validation sur un
    # `None` plutôt que sur le contenu.
    nom_envoye = envoye.name or "fichier"
    try:
        format_trouve = (
            fichiers.valider_logo(contenu, nom_envoye)
            if categorie == CategorieFichier.LOGO
            else fichiers.valider_document(contenu, nom_envoye)
        )
    except fichiers.FichierRefuseError as refus:
        return _refus(str(refus), "fichier_refuse", 400)

    nom = fichiers.nom_sur(nom_envoye)
    piece = PieceJointe(
        organisation=organisation,
        categorie=categorie,
        nom_original=nom,
        type_mime=format_trouve.type_mime,
        taille_octets=len(contenu),
        depose_par=membre.customer,
    )
    piece.fichier.save(nom, ContentFile(contenu), save=False)
    piece.save()

    # Un nouveau logo remplace le précédent : en conserver plusieurs laisserait
    # le rendu choisir, et il choisirait mal.
    if categorie == CategorieFichier.LOGO:
        organisation.pieces_jointes.filter(
            categorie=CategorieFichier.LOGO
        ).exclude(pk=piece.pk).delete()
        organisation.logo_url = piece.fichier.url
        organisation.save(update_fields=["logo_url", "updated_at"])

    return JsonResponse(_piece_en_dict(piece), status=201)


@csrf_exempt
@require_http_methods(["POST"])
@espace("gerer_clients_finaux")
def supprimer_piece_jointe(
    request: HttpRequest,
    membre: MembreOrganisation,
    organisation: Organisation,
    piece_id: str,
) -> HttpResponse:
    """Supprime un fichier. Le filtre porte sur l'organisation, pas sur l'identifiant seul."""
    piece = organisation.pieces_jointes.filter(id=piece_id).first()
    if piece is None:
        return _refus("Fichier introuvable.", "introuvable", 404)
    etait_logo = piece.categorie == CategorieFichier.LOGO
    piece.fichier.delete(save=False)
    piece.delete()
    if etait_logo:
        organisation.logo_url = ""
        organisation.save(update_fields=["logo_url", "updated_at"])
    return HttpResponse(status=204)


# ── Suivi d'une génération ───────────────────────────────────────────────────


@require_http_methods(["GET"])
@espace("consulter_livrables")
def suivi_livrable(
    request: HttpRequest,
    membre: MembreOrganisation,
    organisation: Organisation,
    job_id: str,
) -> HttpResponse:
    """Progression détaillée d'une étude (§9.4).

    Le filtre porte sur `order__organisation` : un identifiant deviné ne donne
    accès à rien.
    """
    job = (
        GenerationJob.objects.filter(id=job_id, order__organisation=organisation)
        .select_related("order")
        .first()
    )
    if job is None:
        return _refus("Étude introuvable.", "introuvable", 404)
    return JsonResponse(suivi.en_dict(job))


# ── Équipe ───────────────────────────────────────────────────────────────────


@csrf_exempt
@require_http_methods(["POST"])
@espace("gerer_membres")
def inviter(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Rattache un collaborateur à l'organisation (§9.1).

    Le compte de connexion n'est PAS créé ici : il le sera à la première
    connexion, une fois le mot de passe défini. Créer un compte avec un mot de
    passe choisi par l'invitant reviendrait à ce qu'une personne connaisse le
    mot de passe d'une autre.
    """
    charge = _corps(request)
    email = str(charge.get("email", "")).strip().lower()
    role = str(charge.get("role", RoleOrganisation.MEMBRE))

    if "@" not in email:
        return _refus("Adresse e-mail invalide.", "email_invalide", 400)
    if role not in RoleOrganisation.values:
        return _refus(f"Rôle inconnu : {role!r}.", "role_inconnu", 400)

    invite, _ = Customer.objects.get_or_create(
        email=email,
        defaults={
            "first_name": str(charge.get("prenom", "")).strip(),
            "last_name": str(charge.get("nom", "")).strip(),
        },
    )

    # Une personne déjà rattachée AILLEURS ne peut pas l'être ici : le
    # cloisonnement suppose un seul rattachement actif par personne. Le dire
    # explicitement vaut mieux qu'un comportement surprenant.
    ailleurs = (
        MembreOrganisation.objects.filter(customer=invite, revoque_le__isnull=True)
        .exclude(organisation=organisation)
        .exists()
    )
    if ailleurs:
        return _refus(
            "Cette personne appartient déjà à une autre organisation.",
            "deja_rattache",
            409,
        )

    nouveau = services.inviter_membre(organisation, invite, role=role)
    return JsonResponse(
        {
            "id": str(nouveau.id),
            "email": invite.email,
            "role": nouveau.role,
            "actif": nouveau.actif,
            "compte_a_creer": not hasattr(invite, "compte"),
        },
        status=201,
    )


@csrf_exempt
@require_http_methods(["POST"])
@espace("gerer_membres")
def revoquer(
    request: HttpRequest,
    membre: MembreOrganisation,
    organisation: Organisation,
    membre_id: str,
) -> HttpResponse:
    """Retire l'accès d'un collaborateur.

    Ses jetons de session sont révoqués dans la foulée : sans cela, la personne
    resterait connectée jusqu'à l'expiration — c'est-à-dire que « révoquer »
    ne révoquerait rien pendant deux semaines.
    """
    cible = organisation.membres.filter(id=membre_id).first()
    if cible is None:
        return _refus("Collaborateur introuvable.", "introuvable", 404)
    try:
        services.revoquer_membre(cible)
    except services.AccesRefuseError as refus:
        return _refus(str(refus), "dernier_proprietaire", 409)

    compte = getattr(cible.customer, "compte", None)
    if compte is not None:
        revoquer_tous_les_jetons(compte)
    return JsonResponse({"id": str(cible.id), "actif": False})


@require_http_methods(["GET"])
@espace()
def equipe(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Collaborateurs de l'organisation (§9.1)."""
    return JsonResponse({
        "membres": [
            {
                "id": str(m.id),
                "email": m.customer.email,
                "prenom": m.customer.first_name,
                "nom": m.customer.last_name,
                "role": m.role,
                "actif": m.actif,
                "invite_le": m.invite_le.isoformat() if m.invite_le else None,
            }
            for m in organisation.membres.select_related("customer").order_by(
                "customer__email"
            )
        ],
        "roles_disponibles": [
            {"code": role.value, "libelle": role.label} for role in RoleOrganisation
        ],
    })

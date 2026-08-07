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
from datetime import datetime, timedelta
from functools import wraps
from typing import Any

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from paiement import stripe_api as paiement_stripe

from customers.models import Customer
from generation.models import GenerationJob, JobStatus

from . import (
    commandes,
    courriels,
    credits,
    fichiers,
    formulaires,
    identifiants,
    liaison,
    limitation,
    services,
    suivi,
)
from .authentification import (
    AuthentificationRefuseeError,
    compte_du_jeton,
    fermer_session,
    ouvrir_session,
    revoquer_tous_les_jetons,
)
from .models import (
    AbonnementOrganisation,  # noqa: F401 — type de retour de `abonnement_actif`
    CategorieFichier,
    ClientFinal,
    DemandeCommerciale,
    Formule,
    MembreOrganisation,
    MouvementCredit,
    Organisation,
    PieceJointe,
    RoleOrganisation,
    StatutAbonnement,
    StatutDemande,
    TypeDemande,
    TypeMouvement,
)

_log = logging.getLogger(__name__)


def _jeton(request: HttpRequest) -> str:
    entete = request.headers.get("Authorization", "")
    return entete[7:].strip() if entete.lower().startswith("bearer ") else ""


def _refus(message: str, code: str, statut: int) -> JsonResponse:
    return JsonResponse({"error": message, "code": code}, status=statut)


#: Méthodes qui MODIFIENT quelque chose. Liste fermée, et volontairement pas
#: son complément : un verbe exotique inconnu doit compter comme une écriture,
#: pas passer pour une lecture (règle 1).
METHODES_SURES = frozenset({"GET", "HEAD", "OPTIONS"})


#: Durée d'engagement minimale, en mois.
#:
#: Ce n'est pas une invention technique : la page publique l'annonce depuis
#: toujours (« Engagement minimum de 3 mois, puis sans engagement »), et la
#: cliente l'a confirmée le 07/08/2026 comme une regle deja en vigueur sur ses
#: autres pages de vente. Rien ne l'appliquait cote code : un abonne pouvait
#: resilier le lendemain de sa souscription.
#:
#: Le nombre vit ICI et nulle part ailleurs. Le recopier dans le texte de la
#: page ferait deux verites pour une meme regle, et le jour ou l'engagement
#: passe a six mois, l'une des deux resterait a trois (regle 5).
MOIS_ENGAGEMENT = 3


def fin_de_l_engagement(
    abonnement: AbonnementOrganisation,
) -> datetime | None:
    """La date de fin d'engagement si elle est A VENIR, sinon `None`.

    Rendre `None` quand l'engagement est echu plutot qu'une date passee : le
    seul usage est de savoir s'il faut refuser, et une date passee obligerait
    chaque appelant a refaire la comparaison — donc a pouvoir se tromper.

    Le calcul part de `debut_le`, la date de souscription. Trois mois se
    comptent en mois calendaires, pas en 90 jours : un abonnement du 31 janvier
    finit son engagement le 30 avril, ce qu'un client comprend, la ou le
    1er mai le surprendrait.
    """
    debut = abonnement.debut_le
    if debut is None:
        return None

    mois = debut.month - 1 + MOIS_ENGAGEMENT
    annee = debut.year + mois // 12
    mois = mois % 12 + 1
    # Le meme quantieme, ramene au dernier jour du mois s'il n'existe pas —
    # 31 janvier + 3 mois donne le 30 avril, et non le 1er mai.
    import calendar  # noqa: PLC0415

    jour = min(debut.day, calendar.monthrange(annee, mois)[1])
    fin = debut.replace(year=annee, month=mois, day=jour)

    return fin if fin > timezone.now() else None


def abonnement_actif(organisation: Organisation) -> AbonnementOrganisation | None:
    """L'abonnement actif de cette organisation, s'il y en a un.

    Une seule fonction pour la garde ET pour l'affichage (`moi`, `formules`) :
    deux facons de repondre a « cette organisation a-t-elle un abonnement ? »
    finiraient par ne pas etre d'accord, et le desaccord se lirait comme un
    espace ferme qui s'annonce ouvert (regle 5).
    """
    return (
        organisation.abonnements.select_related("formule")
        .filter(statut=StatutAbonnement.ACTIF)
        .first()
    )


def acces_ouvert(organisation: Organisation) -> bool:
    """Cette organisation a-t-elle droit à son espace ?

    **Ce n'est pas « a-t-elle un abonnement actif ».** J'ai commencé par écrire
    cela, et 90 tests l'ont démenti d'un coup — à raison. Deux cas légitimes
    tombaient :

    - une organisation **résiliée** qui a encore des crédits ACHETÉS. Ceux-là
      sont pérennes par construction (`credits.detail_solde`), et lui fermer la
      porte reviendrait à encaisser un achat puis à en interdire l'usage ;
    - une organisation **dotée à la main** depuis l'administration — geste
      commercial, dépannage, compte de démonstration — qui n'a jamais eu de
      formule.

    Le critère juste n'est pas l'abonnement du jour, c'est : **quelqu'un a-t-il
    décidé que cette organisation reçoive quelque chose ?** Or un crédit n'entre
    dans un portefeuille que par deux portes, toutes deux volontaires : une
    souscription payée, ou un geste d'administration. Un mouvement, quel qu'il
    soit, prouve donc qu'une décision a été prise.

    Restent les deux clauses ci-dessous, et elles posent deux questions
    différentes — « paie-t-elle aujourd'hui ? » et « a-t-elle jamais reçu
    quelque chose ? ». La première seule fermerait la porte aux résiliés ; la
    seconde seule la fermerait à un abonné dont la formule ne dote rien
    (`credits_par_echeance = 0`) ou dont la première échéance n'est pas encore
    tombée.

    Ce qu'aucune des deux ne laisse passer, c'est exactement le cas visé : un
    compte créé par le formulaire public, qui n'a rien payé et à qui personne
    n'a rien accordé.
    """
    if abonnement_actif(organisation) is not None:
        return True
    return MouvementCredit.objects.filter(
        portefeuille__organisation=organisation
    ).exists()


def espace(
    action: str = "", *, ecriture: str = "", exige_abonnement: bool = False
) -> Callable[..., Any]:
    """Résout le membre et son organisation depuis le jeton, puis vérifie le droit.

    La vue décorée reçoit `(request, membre, organisation, ...)`. Elle n'a aucun
    moyen d'accéder à une autre organisation : c'est ce qui rend le cloisonnement
    structurel plutôt que déclaratif.

    **`ecriture` existe parce que le droit était vérifié sans regarder la
    méthode HTTP.** Quatre vues servent GET *et* POST sous un seul décorateur :
    `marque`, `demandes`, `clients_finaux` et `pieces_jointes`. Elles ne
    pouvaient donc déclarer qu'un seul droit — et déclaraient le plus faible,
    c'est-à-dire aucun.

    Conséquence vérifiée : un compte « Lecture seule » pouvait réécrire la
    charte graphique de l'agence, qui part sur **chaque document livré** chez
    les clients de l'abonné. Il pouvait aussi ouvrir une demande commerciale et
    téléverser des fichiers.

    Le défaut n'était pas quatre oublis, c'était que le décorateur ne savait
    pas distinguer une lecture d'une écriture (règle 4). `test_droits_par_methode`
    verrouille désormais la propriété : aucune vue de l'espace n'accepte
    d'écriture sans droit d'écriture.

    **`exige_abonnement` protège la COMMANDE, pas la vue.**

    J'avais d'abord fermé l'espace entier : sans abonnement, toutes les pages
    répondaient 402 et l'interface les remplaçait par un écran de paiement. La
    cliente l'a corrigé le jour même, et elle a raison sur les deux points.

    D'abord parce que c'est faux du point de vue de qui a déjà payé : quelqu'un
    dont l'abonnement s'arrête doit continuer à voir les documents qu'il a
    commandés. Les lui cacher, c'est reprendre ce qui est livré.

    Ensuite parce que la barrière ne protégeait rien de plus que le solde. Ce
    qui coûte de l'argent à EVKHA, c'est **produire une étude** — et cela est
    déjà tenu par le portefeuille, sous verrou de ligne, avec une clé
    d'idempotence en base. Fermer la lecture ajoutait de la gêne sans ajouter de
    sûreté.

    Le défaut d'origine reste réel : le formulaire public délivrait une session
    immédiate, et rien ne distinguait « a payé » de « n'a pas payé ». La réponse
    juste n'était pas de fermer les yeux du client, c'était de fermer sa main.

    Le prédicat est `acces_ouvert` et non « abonnement actif », pour la même
    raison : un résilié qui a ACHETÉ des crédits doit pouvoir les dépenser.

    La déclaration reste **au point d'usage** : une liste centrale s'oublie au
    moment où l'on ajoute une route. `test_barriere_de_paiement` vérifie
    qu'exactement les vues qui engagent une production la portent.
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

            exige = action
            if request.method not in METHODES_SURES and ecriture:
                exige = ecriture
            if exige and not services.peut(membre, exige):
                return _refus(
                    f"Votre rôle ne permet pas l'action « {exige} ».", "interdit", 403
                )

            # 402 « Payment Required » et non 403 : le refus n'est pas un
            # manque de droit, c'est un abonnement à activer. L'interface
            # distingue les deux — un 403 la ferait écrire « votre rôle ne
            # permet pas », ce qui enverrait chercher un administrateur au lieu
            # du paiement.
            if exige_abonnement and not acces_ouvert(membre.organisation):
                return _refus(
                    "Votre abonnement n'est pas actif. Activez-le pour "
                    "commander un document.",
                    "souscription_requise",
                    402,
                )
            return vue(request, membre, membre.organisation, *args, **kwargs)

        enveloppe.action_lecture = action  # type: ignore[attr-defined]
        enveloppe.action_ecriture = ecriture  # type: ignore[attr-defined]
        enveloppe.exige_abonnement = exige_abonnement  # type: ignore[attr-defined]
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

#: Échecs tolérés sur un même compte depuis une même adresse, par quart d'heure.
#:
#: Assez haut pour que quelqu'un cherche son mot de passe sans être arrêté —
#: c'est le cas légitime, et il est fréquent. Trop bas pour qu'un dictionnaire
#: serve à quoi que ce soit : 10 essais par quart d'heure, c'est 960 par jour,
#: là où une attaque en réclame des millions.
CONNEXIONS_PAR_COMPTE = limitation.Plafond("connexion-compte", maximum=10, fenetre_s=900)

#: Échecs tolérés depuis une même adresse, tous comptes confondus.
#:
#: Vise le balayage : un mot de passe courant essayé sur beaucoup d'adresses
#: e-mail. Le plafond par compte ne le voit pas, chaque compte n'étant essayé
#: qu'une seule fois. La marge tient compte des bureaux partageant une sortie
#: unique, où plusieurs personnes se trompent le même matin.
CONNEXIONS_PAR_ADRESSE = limitation.Plafond(
    "connexion-adresse", maximum=30, fenetre_s=900
)


@csrf_exempt
@require_http_methods(["POST"])
def connexion(request: HttpRequest) -> HttpResponse:
    """Ouvre une session et renvoie le jeton. Le jeton n'est lisible qu'ici.

    Cette vue n'avait **aucun plafond de tentatives** : un mot de passe pouvait
    être essayé aussi vite que le réseau le permettait. L'inscription publique
    en avait un depuis le début ; la porte réellement intéressante pour un
    attaquant, elle, était grande ouverte.

    Deux plafonds, et le second n'est pas redondant :

    - par **compte et adresse**, contre l'essai méthodique d'un mot de passe ;
    - par **adresse seule**, contre le balayage d'un même mot de passe sur
      quantité d'adresses e-mail, que le premier plafond ne verrait jamais
      puisque chaque compte n'est essayé qu'une fois.

    Le premier est volontairement lié à l'adresse d'origine et pas au seul
    e-mail : un plafond par e-mail permettrait à n'importe qui de bloquer le
    compte d'autrui en se trompant exprès. La protection deviendrait l'attaque.

    Un succès efface le compteur : quelqu'un qui cherche son mot de passe, le
    trouve, puis revient le lendemain ne doit pas payer ses hésitations de la
    veille.
    """
    charge = _corps(request)
    email = str(charge.get("email", "")).strip().lower()
    adresse = limitation.adresse_client(request)
    par_compte = f"{email}|{adresse}"

    if limitation.depasse(CONNEXIONS_PAR_COMPTE, par_compte) or limitation.depasse(
        CONNEXIONS_PAR_ADRESSE, adresse
    ):
        # Réponse identique que le compte existe ou non : sinon ce refus
        # deviendrait un moyen de savoir quelles adresses sont enregistrées.
        return _refus(
            "Trop de tentatives de connexion. Réessayez dans un quart d'heure, "
            "ou écrivez-nous à contact@evkha.fr.",
            "trop_de_tentatives",
            429,
        )

    try:
        jeton, objet = ouvrir_session(email, str(charge.get("mot_de_passe", "")))
    except AuthentificationRefuseeError as refus:
        limitation.enregistrer(CONNEXIONS_PAR_COMPTE, par_compte)
        limitation.enregistrer(CONNEXIONS_PAR_ADRESSE, adresse)
        return _refus(str(refus), "identifiants_invalides", 401)

    limitation.oublier(CONNEXIONS_PAR_COMPTE, par_compte)
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


@csrf_exempt
@require_http_methods(["POST"])
@espace()
def changer_mot_de_passe(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Change son mot de passe et **ferme toutes les sessions**, y compris celle-ci.

    Aucune route de ce genre n'existait : `set_password` n'apparaissait qu'une
    fois dans tout le dépôt, à la création du compte. Un abonné dont le mot de
    passe fuit ne pouvait rien faire pendant les quatorze jours de validité de
    ses jetons.

    Le mot de passe ACTUEL est exigé. Sans lui, un jeton volé — la situation
    même dont on cherche à sortir — suffirait à changer le mot de passe et à
    verrouiller le titulaire hors de son propre compte.

    Toutes les sessions tombent, celle qui vient de faire la demande comprise :
    c'est ce qu'on veut, puisqu'on ne sait pas laquelle est l'intruse. Un jeton
    neuf est rendu pour que la personne ne soit pas déconnectée de l'écran où
    elle se trouve.
    """
    charge = _corps(request)
    compte = compte_du_jeton(_jeton(request))
    if compte is None:  # pragma: no cover — le decorateur l'a deja verifie
        return _refus("Authentification requise.", "unauthorized", 401)

    if not compte.user.check_password(str(charge.get("mot_de_passe_actuel", ""))):
        return _refus(
            "Le mot de passe actuel est incorrect.", "mot_de_passe_actuel", 403
        )

    try:
        fermees = identifiants.definir_mot_de_passe(
            compte, str(charge.get("nouveau_mot_de_passe", ""))
        )
    except identifiants.MotDePasseRefuseError as refus:
        return _refus(str(refus), "mot_de_passe_faible", 400)

    return JsonResponse({
        "sessions_fermees": fermees,
        "jeton": authentification_ouvrir(compte),
    })


def authentification_ouvrir(compte: Any) -> str:
    """Délivre un jeton neuf après un changement de mot de passe réussi.

    Nommé à part pour que l'import paresseux reste lisible : le module
    d'authentification importe déjà celui-ci.
    """
    from .authentification import ouvrir_session_sans_mot_de_passe  # noqa: PLC0415

    return str(ouvrir_session_sans_mot_de_passe(compte))


# ── Compte et organisation ───────────────────────────────────────────────────


@require_http_methods(["GET"])
@espace()
def moi(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Tout ce dont l'interface a besoin au chargement : identité, rôle, solde, formule."""
    abonnement = abonnement_actif(organisation)
    # Souscription demandee mais pas encore activee. Sans elle, quelqu'un qui
    # vient de s'inscrire depuis la page partenaires lit « Contactez EVKHA pour
    # souscrire » — exactement ce qu'il vient de faire — et croit son
    # inscription perdue (regle 1 : le systeme sait, il doit le dire).
    demande = (
        organisation.demandes.select_related("formule_visee")
        .filter(type=TypeDemande.CHANGEMENT_FORMULE, statut=StatutDemande.OUVERTE)
        .order_by("-created_at")
        .first()
    )
    disponible = credits.solde(organisation)
    return JsonResponse({
        # LA décision de la garde, telle quelle. L'interface ne la rejoue pas :
        # elle en déduirait « pas d'abonnement, donc payer », ce qui afficherait
        # un mur de paiement à un résilié qui a encore des crédits ACHETÉS — et
        # que le serveur, lui, laisse entrer. Deux réponses à la même question
        # finissent toujours par diverger (règle 5) ; celle-ci décide de ce que
        # le client voit, donc elle vient d'un seul endroit.
        "acces_ouvert": acces_ouvert(organisation),
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
            # L'abonnement se reconduit-il ? Et jusqu'à quand est-il payé ?
            # Sans ces deux-là, l'interface ne peut ni proposer d'arrêter, ni
            # dire à quelqu'un qui vient d'arrêter jusqu'à quand il garde son
            # accès — elle écrirait « actif » à quelqu'un qui a résilié.
            "renouvellement_actif": abonnement.renouvellement_actif,
            "fin_de_periode_le": (
                abonnement.fin_de_periode_le.isoformat()
                if abonnement.fin_de_periode_le
                else ""
            ),
            # Un abonnement ouvert à la main n'a pas de prélèvement derrière
            # lui : les boutons d'arrêt et de changement n'ont rien à piloter.
            "pilote_par_carte": bool(str(abonnement.reference_paiement or "").strip()),
            # Tarif du credit supplementaire, pour que l'espace puisse le
            # proposer a l'achat. Il vient de la FORMULE : le recopier dans
            # le React en ferait une seconde verite, et la page publique
            # finirait par annoncer un prix que la caisse ne pratique pas.
            "prix_credit_supplementaire_cents": (
                abonnement.formule.prix_credit_supplementaire_cents
            ),
            # La regle de report N'ETAIT PAS exposee, et l'interface ecrivait
            # « Aucun » en dur : elle affirmait donc au client ce qu'il advient
            # de ses credits sans jamais l'avoir lu. Une formule a report
            # plafonne aurait affiche le contraire de la verite.
            "report_credits": abonnement.formule.report_credits,
            "plafond_report": abonnement.formule.plafond_report,
        },
        "souscription_en_attente": None if demande is None else {
            "formule": (
                demande.formule_visee.libelle if demande.formule_visee else ""
            ),
            "code": demande.formule_visee.code if demande.formule_visee else "",
            "demandee_le": demande.created_at.isoformat(),
        },
    })


# ── Crédits ──────────────────────────────────────────────────────────────────


#: Profondeur de l'historique de consommation, en mois. Douze : c'est la durée
#: sur laquelle un abonné juge si sa formule est la bonne. Au-delà, la courbe
#: écrase les mois récents, qui sont ceux qui décident.
MOIS_HISTORIQUE = 12


@require_http_methods(["GET"])
@espace("consulter_livrables")
def consommation(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Crédits reçus et consommés, mois par mois.

    C'est la question que se pose un abonné : **ma formule est-elle la bonne ?**
    Le journal ligne à ligne y répond mal — il faut additionner de tête, sur
    des dizaines de lignes.

    L'agrégation se fait ICI, jamais dans l'interface. Deux additions du même
    journal finiraient par ne pas dire la même chose, et c'est déjà la raison
    pour laquelle le solde est recalculé côté serveur (règle 5).

    Les natures viennent de `credits.ENTREES` / `credits.SORTIES` : réécrire la
    liste ici la ferait diverger de celle qui calcule le solde, et le graphique
    contredirait le compteur affiché juste à côté.
    """
    from django.db.models.functions import TruncMonth  # noqa: PLC0415

    # `localtime` et non `now` : `TruncMonth` groupe dans le fuseau du projet
    # (Europe/Paris), pas en UTC. Un mouvement du 31 juillet a 22 h 33 UTC tombe
    # le 1er aout a Paris. Batir le calendrier en UTC et grouper en local, c'est
    # mesurer les deux cotes differemment — le defaut de la regle 2 : les
    # colonnes du graphique se decalent d'un mois pendant les deux dernieres
    # heures de chaque mois, et personne ne le voit.
    maintenant = timezone.localtime()
    debut = (maintenant - timedelta(days=31 * MOIS_HISTORIQUE)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    lignes = (
        credits.portefeuille_de(organisation)
        .mouvements.filter(created_at__gte=debut)
        .annotate(mois=TruncMonth("created_at"))
        .values("mois", "type")
        .annotate(total=Sum("quantite"))
    )

    # SIGNES DU JOURNAL — ils ne sont pas uniformes, et s'y tromper inverse le
    # graphique :
    #
    # - une ENTREE est stockee POSITIVE (dotation, achat, geste) ;
    # - un DEBIT et une EXPIRATION sont stockes NEGATIFS — c'est ce qui permet
    #   au solde d'etre une simple somme du journal ;
    # - un REMBOURSEMENT est stocke POSITIF tout en figurant dans les SORTIES :
    #   il REND des credits.
    #
    # La consommation affichee est donc « ce qui est sorti, moins ce qui a ete
    # rendu ». Compter le remboursement comme une sortie accuserait le client
    # de ce qu'on vient justement de lui rembourser.
    # UN CREDIT EXPIRE N'A PAS ETE CONSOMME — il a ete PERDU.
    #
    # Les deux etaient additionnes sous « consommes », parce que tous deux
    # figurent dans `credits.SORTIES` et sont negatifs au journal. Consequence
    # mesuree le 06/08/2026 sur un compte reel : « 40 consommes » affiche en
    # face de « 22 documents produits ». Le client lisait qu'il avait utilise
    # presque deux fois ce qu'il avait recu.
    #
    # Et le defaut ne s'arretait pas a l'affichage : `_rythme` somme cette
    # colonne pour projeter une date d'epuisement. Elle annoncait donc
    # « 23 credits/mois » et « epuisement le 19 aout » a quelqu'un qui en
    # consomme reellement bien moins — une alarme fondee sur des credits que le
    # client n'a PAS utilises. Or l'expiration est la consequence d'une
    # non-consommation : la compter comme de la consommation predit d'autant
    # plus de depenses qu'on depense moins.
    #
    # Les deux chiffres restent rendus, separement. Celui des expirations n'est
    # pas cache : il est le vrai argument d'un changement de formule, et le
    # taire reviendrait a masquer au client ce qu'il perd (regle 1).
    par_mois: dict[str, dict[str, int]] = {}
    for ligne in lignes:
        cle = ligne["mois"].strftime("%Y-%m")
        seau = par_mois.setdefault(
            cle, {"recus": 0, "consommes": 0, "expires": 0}
        )
        quantite = int(ligne["total"] or 0)
        if ligne["type"] in credits.ENTREES:
            seau["recus"] += quantite
        elif ligne["type"] == TypeMouvement.REMBOURSEMENT:
            # Positif au journal, et il REND un credit : il reduit la
            # consommation nette du mois.
            seau["consommes"] -= quantite
        elif ligne["type"] == TypeMouvement.EXPIRATION:
            # Deja negatif au journal : on le repasse en positif pour l'axe.
            seau["expires"] -= quantite
        elif ligne["type"] in credits.SORTIES:
            seau["consommes"] -= quantite

    # Les mois SANS mouvement doivent apparaitre a zero : un graphique qui les
    # saute laisse croire a une consommation continue alors qu'il y a eu des
    # mois blancs.
    # On recule de mois CALENDAIRES, jamais par pas de trente jours : un pas
    # fixe retombe deux fois dans le meme mois et en saute d'autres, si bien
    # qu'on n'obtient ni douze entrees ni douze mois distincts.
    mois: list[dict[str, str | int]] = []
    total_recu = 0
    total_consomme = 0
    total_expire = 0
    annee, numero = maintenant.year, maintenant.month
    calendrier: list[tuple[int, int]] = []
    for _ in range(MOIS_HISTORIQUE):
        calendrier.append((annee, numero))
        numero -= 1
        if numero == 0:
            annee, numero = annee - 1, 12
    for annee_mois, numero_mois in reversed(calendrier):
        cle = f"{annee_mois:04d}-{numero_mois:02d}"
        seau = par_mois.get(cle, {"recus": 0, "consommes": 0, "expires": 0})
        total_recu += seau["recus"]
        total_consomme += seau["consommes"]
        total_expire += seau["expires"]
        mois.append({
            "mois": cle,
            "libelle": _MOIS_COURTS[numero_mois - 1],
            "recus": seau["recus"],
            "consommes": seau["consommes"],
            "expires": seau["expires"],
        })

    return JsonResponse({
        "mois": mois,
        "total_consomme": total_consomme,
        # Rendu meme a zero : l'interface doit pouvoir dire « rien de perdu »,
        # ce qui n'est pas la meme chose que ne rien dire.
        "total_expire": total_expire,
        "total_recu": total_recu,
        "rythme": _rythme(organisation, mois, maintenant),
    })


def _rythme(
    organisation: Organisation,
    mois: list[dict[str, str | int]],
    maintenant: Any,
) -> dict[str, Any]:
    """Rythme de consommation et date d'épuisement — ou le refus de les donner.

    C'est la question qu'un abonné se pose vraiment : « ma formule tient-elle ? ».
    Le journal ligne à ligne n'y répond pas, et le graphique demande de faire la
    moyenne de tête.

    **Deux pièges, et ils donnent tous les deux un chiffre faux plutôt qu'une
    absence de chiffre** — c'est-à-dire le pire des cas (règles 1 et 2) :

    1. *Diviser par douze.* Un compte ouvert il y a deux mois qui a consommé
       6 crédits ne consomme pas 0,5 crédit par mois : il en consomme 3. La
       moyenne ne porte donc que sur les mois réellement écoulés depuis le
       premier mouvement.

    2. *Compter le mois en cours.* Le 3 du mois, la consommation partielle
       tirerait la moyenne vers le bas et promettrait une autonomie qui
       n'existe pas. Le mois courant est exclu du calcul.

    3. *Compter les crédits EXPIRÉS comme de la consommation.* C'était le cas :
       `consommes` additionnait débits et expirations. Un compte qui laissait
       expirer huit crédits par mois se voyait donc annoncer un rythme de huit
       crédits par mois et une date d'épuisement imminente — alors qu'il ne
       consommait presque rien. Le piège est retors parce qu'il s'inverse :
       moins on consomme, plus il expire, donc plus la projection annonce une
       consommation forte. Seuls les débits comptent désormais.

    Quand l'historique ne permet pas de conclure, on ne conclut pas : `motif`
    dit pourquoi, et l'interface affiche cette raison au lieu d'une date
    inventée.
    """
    solde = credits.solde(organisation)
    courant = f"{maintenant.year:04d}-{maintenant.month:02d}"

    premier = (
        credits.portefeuille_de(organisation)
        .mouvements.order_by("created_at")
        .values_list("created_at", flat=True)
        .first()
    )
    if premier is None:
        return _sans_rythme(solde, "aucun_mouvement")

    debut_local = timezone.localtime(premier)
    depuis = f"{debut_local.year:04d}-{debut_local.month:02d}"

    # Mois révolus : après l'ouverture du compte, et avant le mois en cours.
    revolus = [
        ligne
        for ligne in mois
        if depuis <= str(ligne["mois"]) < courant
    ]
    if not revolus:
        # Compte ouvert ce mois-ci : rien n'est encore mesurable. Le dire vaut
        # mieux qu'extrapoler quelques jours sur un an.
        return _sans_rythme(solde, "pas_assez_d_historique")

    consomme = sum(int(ligne["consommes"]) for ligne in revolus)
    mensuel = consomme / len(revolus)
    if mensuel <= 0:
        return _sans_rythme(solde, "aucune_consommation", mois_observes=len(revolus))

    mois_restants = solde / mensuel
    jours_restants = int(mois_restants * 30.44)  # durée moyenne d'un mois
    return {
        "mensuel": round(mensuel, 1),
        "mois_observes": len(revolus),
        "solde": solde,
        "jours_restants": jours_restants,
        "epuisement_le": (maintenant + timedelta(days=jours_restants)).date().isoformat(),
        "motif": "",
    }


def _sans_rythme(solde: int, motif: str, *, mois_observes: int = 0) -> dict[str, Any]:
    """Forme unique du refus : l'interface n'a qu'un seul cas à traiter."""
    return {
        "mensuel": 0.0,
        "mois_observes": mois_observes,
        "solde": solde,
        "jours_restants": None,
        "epuisement_le": None,
        "motif": motif,
    }


#: Libellés courts, pour un axe qui doit tenir en largeur.
_MOIS_COURTS = (
    "janv.", "févr.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc.",
)


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
@espace("consulter_livrables", ecriture="gerer_clients_finaux")
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
@espace("consulter_livrables", ecriture="gerer_marque")
def marque(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Profil et charte de l'abonné (§9.2, adapté à un abonné unique)."""
    if request.method == "GET":
        return JsonResponse(_marque_en_dict(organisation))

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
    # Le MEME predicat que la page de suivi : cette liste offrait auparavant
    # tous les DOCX/PDF sans regarder leur statut ni celui du job, si bien
    # qu'un document retenu par le controle qualite restait telechargeable.
    artefacts_par_job: dict[str, list[dict[str, str]]] = {
        str(job.id): suivi.fichiers_du_client(job) for job in jobs
    }

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
    actif = abonnement_actif(organisation)
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


# Sans abonnement : c'est LA vue qui sert à en obtenir un. C'est aussi la seule
# des quatre renonciations qui écrit quelque chose — d'où le POST exigé et le
# droit `gerer_abonnement` : un compte « Lecture seule » ne doit pas pouvoir
# engager sa société dans un prélèvement mensuel.
# `csrf_exempt` comme toutes les vues POST de l'espace : l'authentification se
# fait par jeton porteur dans l'en-tête, jamais par cookie de session — il n'y a
# donc pas de requête intersite à forger. Son oubli m'a coûté un « Erreur 403 »
# à l'écran alors que les seize tests de ce chemin étaient verts : le client de
# test Django n'applique pas la vérification CSRF, un navigateur si (règle 7).
@csrf_exempt
@require_http_methods(["POST"])
@espace("gerer_abonnement", ecriture="gerer_abonnement")
def ouvrir_le_paiement(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Ouvre une session Stripe Checkout et renvoie l'adresse où aller payer.

    La formule vient du corps de la requête, mais **rien de ce que le
    navigateur envoie ne fixe un prix** : on ne lit qu'un code, et le montant
    est celui du tarif Stripe rattaché à cette formule. Accepter un montant
    depuis le client reviendrait à laisser choisir combien payer.

    Le cas « déjà abonné » est refusé ici, alors que le décorateur laisse
    passer : la renonciation sert à souscrire, pas à souscrire deux fois. Sans
    ce refus, un abonné actif pourrait ouvrir une seconde souscription Stripe et
    se retrouver prélevé deux fois pour un seul espace.
    """
    if abonnement_actif(organisation) is not None:
        return _refus(
            "Votre abonnement est déjà actif. Pour changer de formule, passez "
            "par une demande.",
            "deja_abonne",
            409,
        )

    code = str(_corps(request).get("formule") or "").strip()
    formule = Formule.objects.filter(code=code, active=True).first()
    if formule is None:
        return _refus("Cette formule n'existe pas.", "formule_inconnue", 400)

    try:
        adresse = paiement_stripe.creer_session_de_paiement(
            organisation, formule, email=membre.customer.email
        )
    except paiement_stripe.PaiementIndisponible as exc:
        # 503 et non 400 : la demande était valable, c'est nous qui ne pouvons
        # pas la servir. Le message vient de l'exception, qui est écrite pour
        # être lue par la personne — jamais le message brut de Stripe.
        _log.error(
            "Paiement impossible pour l'organisation %s (formule %s) : %s",
            organisation.id, code, exc,
        )
        return _refus(str(exc), "paiement_indisponible", 503)

    return JsonResponse({"adresse": adresse}, status=200)


@csrf_exempt
@require_http_methods(["POST"])
@espace()
def modifier_son_profil(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Corrige son prénom et son nom. Sans droit particulier, et c'est voulu.

    Ce sont les siens : un rôle « Lecture seule » doit pouvoir écrire son propre
    nom correctement. Aucun droit du §12 ne s'applique ici, parce qu'aucun de
    ces champs n'engage l'organisation — ils n'apparaissent que sur les écrans
    et dans les courriels qui s'adressent à la personne elle-même.

    L'adresse n'est PAS modifiable ici. Elle est l'identifiant de connexion et
    la destination des liens de réinitialisation : la changer sans preuve
    offrirait la reprise du compte à qui emprunte un écran resté ouvert. Voir
    `demander_une_nouvelle_adresse` juste en dessous.
    """
    charge = _corps(request)
    contact = membre.customer
    contact.first_name = str(charge.get("prenom", "")).strip()[:150]
    contact.last_name = str(charge.get("nom", "")).strip()[:150]
    contact.save(update_fields=["first_name", "last_name"])
    return JsonResponse({
        "prenom": contact.first_name,
        "nom": contact.last_name,
    })


@csrf_exempt
@require_http_methods(["POST"])
@espace()
def demander_une_nouvelle_adresse(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Ouvre un changement d'adresse. **Rien ne change avant confirmation.**

    Deux preuves, et il en faut deux :

    - **le mot de passe actuel**, ici. Un jeton de session suffit à lire
      l'espace ; il ne doit pas suffire à déplacer l'identifiant de connexion,
      sans quoi cinq minutes devant un écran resté ouvert donnent le compte ;
    - **un clic dans la boîte visée**, ensuite. C'est la seule façon de savoir
      que l'adresse existe et appartient bien à la personne. Sans elle, une
      faute de frappe enfermerait quelqu'un dehors définitivement.

    L'ancienne adresse est prévenue au même moment. Sans cet avertissement, une
    reprise de compte serait silencieuse : le voleur change l'adresse, et le
    titulaire ne l'apprend qu'en cessant de recevoir quoi que ce soit.
    """
    compte = compte_du_jeton(_jeton(request))
    if compte is None:
        return _refus("Authentification requise.", "unauthorized", 401)

    charge = _corps(request)
    if not compte.user.check_password(str(charge.get("mot_de_passe", ""))):
        return _refus(
            "Mot de passe incorrect.", "mot_de_passe_actuel", 403
        )

    try:
        nouvelle = identifiants.verifier_adresse_libre(
            str(charge.get("nouvelle_adresse", "")), compte=compte
        )
    except identifiants.AdresseRefuseeError as refus:
        return _refus(str(refus), "adresse_refusee", 400)

    ancienne = compte.customer.email
    lien = identifiants.lien_de_changement_d_adresse(compte, nouvelle)
    envoye = courriels.confirmer_la_nouvelle_adresse(
        destinataire=nouvelle, lien=lien
    )
    if envoye:
        courriels.prevenir_l_ancienne_adresse(
            destinataire=ancienne, nouvelle=nouvelle
        )

    _log.info("Changement d'adresse demande : %s -> %s", ancienne, nouvelle)
    return JsonResponse({
        "adresse_visee": nouvelle,
        "courriel_envoye": envoye,
        # Rendu SEULEMENT quand l'envoi echoue, comme pour l'invitation : une
        # panne de messagerie ne doit pas laisser la personne sans recours.
        "lien_confirmation": "" if envoye else lien,
    }, status=202)


#: Nombre de crédits qu'un achat unique peut porter.
#:
#: Un plafond, parce qu'une quantité venue du navigateur ne se croit pas :
#: `quantite = 100000` produirait une facture de six millions d'euros que
#: personne ne paiera, mais aussi une session Stripe absurde dans le journal.
#: Cinquante couvre très largement le besoin d'un partenaire — la plus grosse
#: formule en inclut dix par mois.
ACHAT_CREDITS_MAX = 50


@csrf_exempt
@require_http_methods(["POST"])
@espace("gerer_abonnement", ecriture="gerer_abonnement")
def acheter_des_credits(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Ouvre un paiement ponctuel pour des crédits supplémentaires.

    La page publique annonce « Crédit supplémentaire : 59 € » sur chaque
    formule depuis le premier jour, et **aucun chemin ne permettait d'en
    acheter** : pas de bouton, pas de route, pas de paiement. Un partenaire à
    court de crédits en milieu de mois n'avait qu'à attendre le suivant.

    **Rien de ce que le navigateur envoie ne fixe un prix.** On ne lit qu'une
    quantité ; le tarif unitaire est celui de la formule de l'organisation, en
    administration. Accepter un montant depuis le client reviendrait à laisser
    choisir combien payer.

    L'abonnement actif est exigé, et ce n'est pas une restriction gratuite :
    c'est lui qui porte la formule, donc le tarif. Sans lui, il n'existe aucun
    prix à appliquer — et en inventer un par défaut ferait payer à quelqu'un un
    tarif que personne ne lui a annoncé.
    """
    abonnement = abonnement_actif(organisation)
    if abonnement is None:
        return _refus(
            "L'achat de crédits supplémentaires est réservé aux abonnés. "
            "Souscrivez à une formule pour en bénéficier.",
            "sans_abonnement",
            409,
        )

    brut = _corps(request).get("quantite")
    try:
        quantite = int(str(brut))
    except (TypeError, ValueError):
        return _refus("Indiquez un nombre de crédits.", "quantite_invalide", 400)

    if quantite < 1 or quantite > ACHAT_CREDITS_MAX:
        return _refus(
            f"Le nombre de crédits doit être compris entre 1 et "
            f"{ACHAT_CREDITS_MAX}.",
            "quantite_invalide",
            400,
        )

    try:
        adresse = paiement_stripe.creer_paiement_de_credits(
            organisation=organisation,
            formule=abonnement.formule,
            quantite=quantite,
            email=organisation.contact.email if organisation.contact_id else "",
        )
    except paiement_stripe.PaiementIndisponible as exc:
        return _refus(str(exc), "paiement_indisponible", 503)

    _log.info(
        "Achat de credits ouvert : organisation=%s quantite=%s",
        organisation.id, quantite,
    )
    return JsonResponse({"url": adresse})


@csrf_exempt
@require_http_methods(["POST"])
@espace("gerer_abonnement", ecriture="gerer_abonnement")
def arreter_l_abonnement(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Refuse l'arrêt en libre-service, et dit à qui écrire.

    Cette vue coupait la reconduction chez Stripe d'un seul clic. La cliente a
    tranché autrement le 07/08/2026 : « l'annulation doit se faire
    manuellement, donc la personne doit la contacter ». Elle traite ces
    demandes elle-même, au moins au début — c'est aussi l'occasion de retenir
    un abonné qui part.

    **Le point d'entrée subsiste, et refuse.** Le supprimer aurait laissé les
    pages encore ouvertes dans un navigateur appeler une adresse disparue : le
    client aurait vu une erreur technique là où il attend une marche à suivre.
    Ici il reçoit la bonne, et rien n'est arrêté — aucun appel ne part chez
    Stripe.

    Le message rappelle l'engagement de trois mois quand il court encore. Ce
    n'est pas un refus supplémentaire — l'arrêt passe par EVKHA dans tous les
    cas — mais l'abonné a le droit de savoir jusqu'à quand il est engagé AVANT
    d'écrire, plutôt que de l'apprendre en réponse à son courriel.

    L'ancien enchaînement vers Stripe vit dans `_arret_automatique_retire`,
    hors service. Il est conservé parce que la cliente prévoit de rouvrir le
    libre-service une fois le volume installé : le réécrire de mémoire ce
    jour-là coûterait ses défauts.
    """
    abonnement = abonnement_actif(organisation)
    if abonnement is None:
        return _refus("Aucun abonnement actif à arrêter.", "sans_abonnement", 409)

    fin_engagement = fin_de_l_engagement(abonnement)
    engagement = (
        f" Votre engagement de {MOIS_ENGAGEMENT} mois court jusqu'au "
        f"{fin_engagement:%d/%m/%Y}."
        if fin_engagement is not None
        else ""
    )
    return _refus(
        "L'arrêt d'un abonnement se fait sur demande auprès d'EVKHA. "
        f"Écrivez-nous à {settings.EVKHA_SENDER_EMAIL} et nous nous en "
        f"occupons.{engagement}",
        "arret_sur_demande",
        409,
    )


def _arret_automatique_retire(
    abonnement: AbonnementOrganisation, organisation: Organisation
) -> HttpResponse:
    """L'ancien arrêt en libre-service, hors service depuis le 07/08/2026.

    Il coupait la reconduction chez Stripe au terme de la période payée, sans
    rien reprendre au client : le statut restait ACTIF, les crédits déposés
    restaient consommables, et c'est le webhook `customer.subscription.deleted`
    qui prononçait la fin le moment venu.

    Plus personne ne l'appelle. Il reste écrit pour le jour où l'arrêt
    redeviendra libre-service.
    """
    reference = str(abonnement.reference_paiement or "").strip()
    if not reference:
        return _refus(
            "Cet abonnement n'a pas été souscrit par carte. Écrivez-nous pour "
            "l'arrêter.",
            "abonnement_hors_carte",
            409,
        )

    try:
        fin = paiement_stripe.arreter_le_renouvellement(reference)
    except paiement_stripe.PaiementIndisponible as exc:
        return _refus(str(exc), "paiement_indisponible", 503)

    abonnement.renouvellement_actif = False
    if fin:
        abonnement.fin_de_periode_le = datetime.fromisoformat(fin)
    abonnement.save(
        update_fields=["renouvellement_actif", "fin_de_periode_le", "updated_at"]
    )
    _log.info("Renouvellement arrete : organisation=%s", organisation.id)
    return JsonResponse({
        "renouvellement_actif": False,
        "fin_de_periode_le": (
            abonnement.fin_de_periode_le.isoformat()
            if abonnement.fin_de_periode_le
            else ""
        ),
    })


@csrf_exempt
@require_http_methods(["POST"])
@espace("gerer_abonnement", ecriture="gerer_abonnement")
def reprendre_l_abonnement(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Revient sur un arrêt, tant que le terme n'est pas atteint.

    Sans ce retour, une hésitation devient un départ définitif : reprendre
    exigerait une nouvelle souscription, donc une nouvelle saisie de carte.
    """
    abonnement = abonnement_actif(organisation)
    if abonnement is None:
        return _refus("Aucun abonnement actif.", "sans_abonnement", 409)
    if abonnement.renouvellement_actif:
        return _refus("Votre abonnement est déjà reconduit.", "deja_actif", 409)

    reference = str(abonnement.reference_paiement or "").strip()
    if not reference:
        return _refus(
            "Cet abonnement n'a pas été souscrit par carte.",
            "abonnement_hors_carte",
            409,
        )

    try:
        paiement_stripe.reprendre_le_renouvellement(reference)
    except paiement_stripe.PaiementIndisponible as exc:
        return _refus(str(exc), "paiement_indisponible", 503)

    abonnement.renouvellement_actif = True
    abonnement.save(update_fields=["renouvellement_actif", "updated_at"])
    _log.info("Renouvellement repris par le client : organisation=%s", organisation.id)
    return JsonResponse({"renouvellement_actif": True})


@csrf_exempt
@require_http_methods(["POST"])
@espace("gerer_abonnement", ecriture="gerer_abonnement")
def changer_de_formule(
    request: HttpRequest, membre: MembreOrganisation, organisation: Organisation
) -> HttpResponse:
    """Change de formule tout de suite, chez Stripe et chez nous.

    C'était une `DemandeCommerciale` qu'un humain accordait — et, plus grave,
    l'accorder ne touchait pas Stripe : le prélèvement suivant repartait sur
    l'ancien tarif, et la formule « changée » se défaisait d'elle-même à
    l'échéance.

    L'ordre compte. Stripe d'abord : s'il refuse, rien n'a bougé chez nous et le
    client garde ce qu'il paie. L'inverse laisserait une organisation sur une
    formule qu'aucun prélèvement ne finance.
    """
    abonnement = abonnement_actif(organisation)
    if abonnement is None:
        return _refus("Aucun abonnement actif.", "sans_abonnement", 409)

    code = str(_corps(request).get("formule") or "").strip()
    formule = Formule.objects.filter(code=code, active=True).first()
    if formule is None:
        return _refus("Cette formule n'existe pas.", "formule_inconnue", 400)
    if formule.pk == abonnement.formule_id:
        return _refus("C'est déjà votre formule.", "formule_identique", 409)

    reference = str(abonnement.reference_paiement or "").strip()
    if not reference:
        return _refus(
            "Cet abonnement n'a pas été souscrit par carte. Écrivez-nous pour "
            "en changer.",
            "abonnement_hors_carte",
            409,
        )

    try:
        paiement_stripe.changer_de_formule(reference, formule)
    except paiement_stripe.PaiementIndisponible as exc:
        return _refus(str(exc), "paiement_indisponible", 503)

    # `doter_immediatement=False` : Stripe facture la différence au prorata et
    # émettra sa facture ; c'est `invoice.paid` qui dotera. Doter ici donnerait
    # les crédits de la nouvelle formule avant que la différence soit encaissée,
    # et une seconde fois à l'arrivée de la facture.
    nouveau = services.souscrire(organisation, formule, doter_immediatement=False)
    nouveau.reference_paiement = reference
    nouveau.derniere_periode_dotee = abonnement.derniere_periode_dotee
    nouveau.renouvellement_actif = abonnement.renouvellement_actif
    nouveau.fin_de_periode_le = abonnement.fin_de_periode_le
    nouveau.save(update_fields=[
        "reference_paiement", "derniere_periode_dotee", "renouvellement_actif",
        "fin_de_periode_le", "updated_at",
    ])
    _log.info(
        "Formule changee par le client : organisation=%s -> %s",
        organisation.id, formule.code,
    )
    return JsonResponse({"formule": formule.code, "libelle": formule.libelle})


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
@espace("gerer_abonnement", ecriture="gerer_abonnement")
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


# LA seule vue qui exige un abonnement, et c'est la seule qui engage EVKHA :
# elle lance une production qui coûte de l'argent réel. Lire son espace, ses
# documents ou son journal de crédits reste ouvert — un abonné dont le
# prélèvement s'arrête ne doit pas perdre la vue de ce qu'il a déjà payé.
@csrf_exempt
@require_http_methods(["POST"])
@espace("commander", exige_abonnement=True)
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
    from evkha import signatures  # noqa: PLC0415 — evite un cycle a l'import

    return {
        "id": str(piece.id),
        "categorie": piece.categorie,
        "nom": piece.nom_original,
        "taille_octets": piece.taille_octets,
        "type_mime": piece.type_mime,
        "date": piece.created_at.isoformat(),
        # L'URL brute etait rendue telle quelle : `pieces-jointes/<id
        # d'organisation>/<nom d'origine du client>` se devine, et `/media/`
        # servait sans rien verifier. Le bilan financier depose par une agence
        # etait donc telechargeable par qui avait vu passer le chemin.
        "url": signatures.lien(piece.fichier.name) if piece.fichier else "",
    }


@csrf_exempt
@require_http_methods(["GET", "POST"])
@espace("consulter_livrables", ecriture="commander")
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

    # Le format reconnu dans les octets est transmis : c'est lui qui impose
    # l'extension de stockage. La conserver telle que le client l'a ecrite
    # laissait deposer un `.html` — servi ensuite en `text/html` sur le domaine
    # de l'API. Voir `fichiers.nom_sur`.
    nom = fichiers.nom_sur(nom_envoye, format_trouve)
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


#: États depuis lesquels une étude peut être abandonnée par son commanditaire.
#:
#: Volontairement PAS `running` : une étude en cours de production consomme
#: déjà des appels facturés, et l'abandonner en vol rendrait un crédit pour un
#: travail réellement effectué. Volontairement pas `done` non plus : le
#: document est livré.
ETATS_ABANDONNABLES = ("failed", "intervention_requise")


@csrf_exempt
@require_http_methods(["POST"])
@espace("commander")
def abandonner_livrable(
    request: HttpRequest,
    membre: MembreOrganisation,
    organisation: Organisation,
    job_id: str,
) -> HttpResponse:
    """Renonce à une étude en échec et récupère le crédit — **sans personne**.

    C'était le seul recours manquant, et il coûtait cher. Le crédit est débité
    au lancement ; aucun chemin du produit n'écrivait jamais de remboursement.
    Un abonné dont l'étude échouait payait donc un document qu'il ne recevrait
    pas, et devait ouvrir une demande commerciale traitée à la main — un
    parcours qui oblige à contacter un humain, ce que ce produit exclut.

    L'abandon est un acte **explicite**, et c'est ce que `rembourser_job`
    attendait depuis le début : rembourser sur la simple bascule en `FAILED`
    offrirait l'étude à qui échoue puis relance, puisque la ligne de débit
    resterait en place.

    Une fois abandonnée, l'étude ne peut plus être relancée — `debiter_pour_job`
    le refuse, dans la couche qui tient l'argent et non dans une vue.
    """
    job = (
        GenerationJob.objects.filter(id=job_id, order__organisation=organisation)
        .select_related("order")
        .first()
    )
    if job is None:
        return _refus("Étude introuvable.", "introuvable", 404)

    if job.status not in ETATS_ABANDONNABLES:
        return _refus(
            "Cette étude ne peut pas être abandonnée : elle n'est pas en échec.",
            "etat_incompatible",
            409,
        )

    if liaison.credits_restitues(job):
        # Idempotent : un double clic ne rend pas deux crédits. Le journal
        # l'interdirait de toute façon, mais un 409 muet laisserait croire à
        # une panne.
        return _refus(
            "Le crédit de cette étude vous a déjà été restitué.",
            "deja_restitue",
            409,
        )

    GenerationJob.objects.filter(pk=job.pk).update(status=JobStatus.CANCELLED)
    job.refresh_from_db(fields=["status"])
    restitue = liaison.rembourser_job(
        job, motif="Étude abandonnée par le client après échec"
    )

    return JsonResponse({
        "job_id": str(job.id),
        "statut": job.status,
        "credits_restitues": restitue,
        "solde": credits.solde(organisation),
    })


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

    try:
        nouveau = services.inviter_membre(organisation, invite, role=role)
    except services.AccesRefuseError as refus:
        # Retrograder le dernier proprietaire. `inviter_membre` ecrase le role
        # d'un membre existant : sans cette traduction, le refus remontait en
        # erreur 500 et personne ne savait pourquoi.
        return _refus(str(refus), "dernier_proprietaire", 409)

    # Le compte de connexion est cree ICI, avec un mot de passe INUTILISABLE.
    # Il ne l'etait nulle part : l'invite se retrouvait sans compte, donc
    # incapable de se connecter, refuse a l'inscription publique (« cette
    # adresse a deja un compte » — faux) et refuse par Google pour la meme
    # raison. La fonctionnalite Equipe ne fonctionnait pas du tout, alors que
    # l'ecran promettait « EVKHA lui transmettra ses identifiants ».
    compte = identifiants.compte_sans_mot_de_passe(invite)
    lien = identifiants.lien_pour(compte)
    envoye = courriels.inviter_un_collaborateur(
        destinataire=invite.email,
        organisation=organisation.raison_sociale,
        lien=lien,
    )

    return JsonResponse(
        {
            "id": str(nouveau.id),
            "email": invite.email,
            "role": nouveau.role,
            "actif": nouveau.actif,
            "invitation_envoyee": envoye,
            # Rendu a l'ecran QUAND l'envoi a echoue : une panne de messagerie
            # ne doit pas laisser l'invitant sans recours. Il recopie le lien.
            "lien_activation": "" if envoye else lien,
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

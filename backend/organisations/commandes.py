"""Commande d'un document depuis l'espace client (§9.3).

Conséquence directe du changement de rôle : EVKHA ne produit plus les documents
à la place de ses abonnés, donc l'abonné doit pouvoir commander lui-même.

## Ordre des opérations, et pourquoi il n'est pas interchangeable

1. **Contrôle préalable** du solde — pour refuser tout de suite, avec un message
   compréhensible, plutôt qu'au milieu du pipeline ;
2. **création** de la commande, de la soumission et du job ;
3. **mise en file** de la génération, qui débitera à son démarrage.

Le débit n'est **pas** fait ici. Il appartient à `run_generation_job`, qui seul
verrouille le portefeuille et qui est le point où l'argent commence réellement à
être dépensé. Débiter ici puis échouer au bootstrap laisserait un client débité
d'une étude qui n'a jamais démarré — et le remboursement automatique ne couvre
que les échecs *après* démarrage. Une seule autorité sur le débit, au plus près
de la dépense (règle 5).

Le contrôle préalable est donc **indicatif** et assumé comme tel : entre lui et
le débit réel, une autre commande peut passer. C'est `debiter` qui tranche.
"""
from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.models import GenerationJob
from generation.services import bootstrap_generation_job
from intake.models import IntakeSource, IntakeStatus, IntakeSubmission
from orders.models import Order, OrderStatus

from . import credits, formulaires
from .liaison import cout_en_credits
from .models import Organisation

#: Fenêtre pendant laquelle une soumission identique est traitée comme un
#: double envoi, et non comme une nouvelle commande.
#:
#: Assez large pour couvrir un double-clic, un rejeu de formulaire ou une
#: relance réseau ; assez courte pour ne jamais empêcher quelqu'un de
#: recommander délibérément la même étude.
FENETRE_ANTI_DOUBLON = timedelta(minutes=10)

_log = logging.getLogger(__name__)

#: Types commandables depuis l'espace : les quatre du catalogue, chacun avec
#: son questionnaire. La liste est DÉRIVÉE des formulaires déclarés — ajouter un
#: questionnaire suffit à rendre le type commandable, sans toucher ici (règle 5).
TYPES_COMMANDABLES: tuple[str, ...] = tuple(formulaires.FORMULAIRES)

# Clés en `str` et non en `DeliverableType` : les valeurs viennent d'une charge
# JSON, donc toujours sous forme de chaîne. Typer les tables avec l'énumération
# obligerait à convertir à chaque lecture, pour un gain nul.
LIBELLES: dict[str, str] = {
    DeliverableType.MARKET_STUDY.value: "Étude de marché",
    DeliverableType.COMPETITOR_STUDY.value: "Étude de la concurrence",
    DeliverableType.BUSINESS_PLAN.value: "Business plan",
    DeliverableType.BUSINESS_STRATEGY.value: "Stratégie d'entreprise",
}

DESCRIPTIONS: dict[str, str] = {
    DeliverableType.MARKET_STUDY.value: (
        "22 chapitres. Dimensionnement du marché, segmentation, concurrence, "
        "tendances, risques et recommandations."
    ),
    DeliverableType.COMPETITOR_STUDY.value: (
        "9 chapitres. Cartographie des acteurs, positionnement, forces et "
        "faiblesses, espace stratégique à prendre."
    ),
}

#: Le logo, les couleurs et la raison sociale ne sont PAS demandés : ils
#: viennent de la fiche « Ma marque ». Les redemander à chaque commande serait
#: exactement la ressaisie que cette fiche existe pour éviter.


class CommandeRefuseeError(RuntimeError):
    """La commande ne peut pas être lancée. Le message est destiné au client."""


def catalogue() -> list[dict[str, Any]]:
    """Types de documents commandables, avec leur coût en crédits."""
    return [
        {
            "type": type_document,
            "libelle": LIBELLES.get(type_document, type_document),
            "description": DESCRIPTIONS.get(type_document, ""),
            "cout_credits": 1,
            "questions": len(formulaires.FORMULAIRES[type_document].champs),
        }
        for type_document in TYPES_COMMANDABLES
    ]


def _offre_pour(type_document: str) -> Offer:
    """Offre technique rattachée au type. Créée à la demande.

    Ces offres ne sont pas des produits commerciaux : le prix est porté par la
    formule d'abonnement, pas par l'offre. Elles n'existent que parce que
    `Order` en exige une.
    """
    offre, _ = Offer.objects.get_or_create(
        slug=f"espace-{type_document.replace('_', '-')}",
        defaults={
            "name": LIBELLES.get(type_document, type_document),
            "deliverable_type": type_document,
            "is_active": True,
        },
    )
    return offre


def variables_de_commande(
    organisation: Organisation, type_document: str, saisie: dict[str, Any]
) -> tuple[dict[str, str], list[str]]:
    """Variables du brief. Retourne (variables, champs obligatoires manquants).

    Les champs retenus sont ceux que le QUESTIONNAIRE déclare, pas une seconde
    liste tenue ici : sans cela, ajouter une question au formulaire la ferait
    afficher sans jamais atteindre le modèle.

    La marque de l'organisation est injectée en dernier et **ne peut pas** être
    surchargée par la saisie : la charte du document est celle de la fiche, pas
    celle d'un champ de formulaire oublié.
    """
    questionnaire = formulaires.formulaire(type_document)
    if questionnaire is None:
        return {}, ["type"]

    variables: dict[str, str] = {}
    for champ in questionnaire.champs:
        valeur = str(saisie.get(champ.identifiant, "") or "").strip()
        if valeur:
            variables[champ.identifiant] = valeur

    # Repli : la zone par défaut est le pays. Le laisser vide ferait échouer des
    # prompts qui l'interpolent, pour une information que le client a déjà
    # donnée sous un autre nom.
    variables.setdefault("ZONE", variables.get("PAYS", ""))

    # Le secteur de la fiche sert de repli, jamais d'écrasement : le client peut
    # commander une étude sur un secteur voisin du sien.
    if not variables.get("SECTEUR") and organisation.secteur:
        variables["SECTEUR"] = organisation.secteur

    # `couleur_fond` et `mention_confidentialite` manquaient a cette liste.
    # L'abonne les saisit dans « Ma Marque », le moteur de rendu les LIT
    # (`depuis_json.rendre_etude`, `assemblage.mentions_finales`) — et ils
    # n'arrivaient jamais jusqu'a lui. Chaque document partait donc avec la
    # mention de confidentialite par defaut, et le fond de reference.
    #
    # Deux champs de formulaire sans effet, sans qu'aucun ecran ne le dise :
    # l'abonne croit avoir personnalise ce que son client va lire.
    marque = {
        "NOM_ENTREPRISE": organisation.raison_sociale,
        "LOGO_URL": organisation.logo_url,
        "COULEUR_PRINCIPALE": organisation.couleur_principale,
        "COULEUR_SECONDAIRE": organisation.couleur_secondaire,
        "COULEUR_FOND": organisation.couleur_fond,
        "MENTION_CONFIDENTIALITE": organisation.mention_confidentialite,
    }
    variables.update({cle: valeur for cle, valeur in marque.items() if valeur})

    manquants = [
        identifiant
        for identifiant in questionnaire.obligatoires
        if not variables.get(identifiant)
    ]
    return variables, manquants


@transaction.atomic
def creer_commande(
    organisation: Organisation,
    demandeur: Customer,
    *,
    type_document: str,
    saisie: dict[str, Any],
) -> GenerationJob:
    """Crée la commande et le job. Ne débite pas — voir l'en-tête du module.

    Lève `CommandeRefuseeError` avec un message destiné au client : « Erreur
    interne » n'aide personne à comprendre qu'il lui manque un crédit.
    """
    if type_document not in TYPES_COMMANDABLES:
        msg = f"Ce type de document n'est pas commandable : {type_document!r}."
        raise CommandeRefuseeError(msg)

    if not organisation.active:
        msg = (
            "Votre organisation est suspendue. Contactez EVKHA pour rétablir "
            "votre accès."
        )
        raise CommandeRefuseeError(msg)

    variables, manquants = variables_de_commande(organisation, type_document, saisie)
    if manquants:
        questionnaire = formulaires.formulaire(type_document)
        libelles = {c.identifiant: c.libelle for c in questionnaire.champs} if questionnaire else {}
        # Le message nomme les QUESTIONS, pas les identifiants techniques : un
        # client à qui l'on répond « CLIENTELE_CIBLE manquant » ne sait pas quoi
        # corriger.
        noms = [libelles.get(champ, champ) for champ in manquants]
        msg = "Merci de répondre à : " + " · ".join(noms)
        raise CommandeRefuseeError(msg)

    cout = 1
    possible, raison = credits.peut_commander(organisation, cout)
    if not possible:
        raise CommandeRefuseeError(raison)

    # DOUBLE ENVOI. Chaque POST fabriquait un `systeme_order_id` neuf, donc une
    # commande neuve, donc un job neuf — et le debit est idempotent par JOB.
    # Deux clics sur « Commander », un navigateur qui rejoue la requete, un
    # reseau qui hesite : deux etudes identiques produites, deux credits
    # preleves. La garantie « aucun double debit » etait vraie a la lettre et
    # sans effet ici.
    #
    # On ne pose pas d'unicite definitive sur le contenu : recommander la meme
    # etude un an plus tard est legitime. Ce qu'on refuse, c'est la MEME
    # soumission deux fois de suite (regle 4) — et l'appelant recoit le job
    # deja cree, pas une erreur : il vient de commander, il doit voir son etude.
    recente = (
        Order.objects.filter(
            organisation=organisation,
            offer=_offre_pour(type_document),
            created_at__gte=timezone.now() - FENETRE_ANTI_DOUBLON,
            raw_payload__saisie=saisie,
        )
        .order_by("-created_at")
        .first()
    )
    if recente is not None:
        deja = GenerationJob.objects.filter(order=recente).order_by("-created_at").first()
        if deja is not None:
            _log.info(
                "Commande identique renvoyee pour %s : job %s (double envoi).",
                organisation, deja.id,
            )
            return deja

    commande = Order.objects.create(
        customer=demandeur,
        offer=_offre_pour(type_document),
        organisation=organisation,
        systeme_order_id=f"espace-{uuid.uuid4().hex[:12]}",
        status=OrderStatus.PROCESSING,
        raw_payload={"origine": "espace_client", "saisie": saisie},
    )
    soumission = IntakeSubmission.objects.create(
        order=commande,
        source=IntakeSource.MANUAL,
        status=IntakeStatus.NORMALIZED,
        raw_payload=saisie,
        normalized_variables=variables,
        missing_fields=[],
    )
    job = bootstrap_generation_job(soumission)
    _log.info(
        "Commande %s créée depuis l'espace client de %s (job %s).",
        commande.systeme_order_id, organisation, job.id,
    )
    return job


def lancer(job: GenerationJob) -> None:
    """Met la génération en file.

    Hors de la transaction de `creer_commande` : une tâche mise en file dans une
    transaction non encore validée peut être consommée avant que le job existe
    en base, et le worker ne trouve alors rien.
    """
    from generation.tasks import run_generation_job_task  # noqa: PLC0415

    run_generation_job_task.delay(str(job.id))


def cout_affiche(job: GenerationJob) -> int:
    """Coût en crédits d'un job, pour l'affichage. Une seule source (règle 5)."""
    return cout_en_credits(job)

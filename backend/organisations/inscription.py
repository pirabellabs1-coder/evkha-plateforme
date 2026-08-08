"""Ouvrir un compte : le geste, partagé par l'administration et le public.

Il existait déjà, mais uniquement derrière l'administration (`dashboard.actions
.creer_abonne`). Un visiteur de la page partenaires ne pouvait donc pas
souscrire seul : il fallait qu'un humain lui ouvre le compte à la main.

Ce module porte l'orchestration commune — organisation, propriétaire,
identifiants — pour que les deux chemins ne divergent pas (règle 5). Ils ne
diffèrent que sur **un** point, et c'est le point important :

- l'**administration** ouvre un compte déjà négocié : elle peut souscrire la
  formule et doter les crédits dans la foulée ;
- le **public** n'a rien payé. On enregistre son intention comme demande
  commerciale, et **aucun crédit n'est délivré**. Créditer avant encaissement
  ferait des livrables gratuits à qui remplit un formulaire.

C'est aussi ce que corrigera Stripe : la demande devient une souscription
active quand le paiement est confirmé, pas quand le formulaire est envoyé.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from customers.models import Customer, CustomerType

from . import authentification, services
from .models import (
    AbonnementOrganisation,
    DemandeCommerciale,
    Formule,
    MembreOrganisation,
    Organisation,
)


class InscriptionRefuseeError(ValueError):
    """Saisie inexploitable. Le message est écrit POUR LE VISITEUR.

    Il porte aussi un `code`, pour que l'interface sache quel champ signaler
    sans avoir à reconnaître une phrase — un texte que l'on compare finit
    toujours par être reformulé sans que le test s'en aperçoive.
    """

    def __init__(self, message: str, code: str, statut: int = 400) -> None:
        self.code = code
        self.statut = statut
        super().__init__(message)


@dataclass(frozen=True)
class Ouverture:
    """Ce qui a été créé. `abonnement` est None quand rien n'a été activé."""

    organisation: Organisation
    contact: Customer
    formule: Formule | None
    #: Souscription réellement activée. Reste None sur le chemin public : tant
    #: que rien n'est encaissé, il n'y a pas d'abonnement, seulement une
    #: intention.
    abonnement: AbonnementOrganisation | None
    #: Demande enregistrée sur le chemin public, à traiter par EVKHA.
    demande: DemandeCommerciale | None


def formule_ou_refus(code: str) -> Formule | None:
    """Formule active portant ce code. Vide = pas de formule, ce n'est pas une erreur."""
    code = (code or "").strip()
    if not code:
        return None
    formule = Formule.objects.filter(code=code, active=True).first()
    if formule is None:
        msg = f"Aucune formule active ne porte le code « {code} »."
        raise InscriptionRefuseeError(msg, "formule_introuvable", 404)
    return formule


def controler_saisie(*, raison_sociale: str, email: str, mot_de_passe: str) -> None:
    """Refuse ce qui ne peut pas produire un compte utilisable.

    Le mot de passe passe par les validateurs du projet, jamais par une règle
    écrite ici : deux avis sur ce qu'est un mot de passe acceptable finiraient
    par se contredire (règle 5).
    """
    if not raison_sociale:
        raise InscriptionRefuseeError(
            "Indiquez la raison sociale.", "raison_sociale_manquante"
        )
    if not email or "@" not in email:
        raise InscriptionRefuseeError(
            "Indiquez une adresse e-mail valide.", "email_invalide"
        )
    if not mot_de_passe:
        raise InscriptionRefuseeError(
            "Choisissez un mot de passe.", "mot_de_passe_manquant"
        )
    try:
        validate_password(mot_de_passe)
    except ValidationError as exc:
        raise InscriptionRefuseeError(
            " ".join(exc.messages), "mot_de_passe_faible"
        ) from exc


def refuser_si_deja_membre(email: str, *, nommer_organisation: bool) -> None:
    """Une personne ne peut appartenir qu'à une organisation.

    Le décorateur `espace()` retient la PREMIÈRE adhésion trouvée : deux
    rattachements rendraient l'espace imprévisible — parfois l'une, parfois
    l'autre. Mieux vaut refuser ici que livrer un espace instable.

    La règle est la même pour tout le monde ; le MESSAGE, non, et c'est
    délibéré :

    - en **administration**, nommer l'organisation existante est l'information
      utile — elle dit quoi faire (inviter depuis cet espace) ;
    - en **public**, la nommer permettrait à n'importe qui de sonder des
      adresses pour découvrir qui travaille où. On dit seulement qu'un compte
      existe.

    Le paramètre est obligatoire : un défaut aurait fini par livrer le nom de
    l'organisation sur le formulaire public sans que personne ne le décide.
    """
    deja = (
        MembreOrganisation.objects.select_related("organisation")
        .filter(customer__email__iexact=email, revoque_le__isnull=True)
        .first()
    )
    if deja is None:
        return
    if nommer_organisation:
        msg = (
            f"« {email} » appartient déjà à l'organisation "
            f"« {deja.organisation.raison_sociale} ». Invitez cette personne "
            "depuis son espace au lieu de créer une seconde organisation."
        )
    else:
        msg = (
            f"« {email} » a déjà un compte. Connectez-vous, ou faites-vous "
            "inviter par votre organisation."
        )
    raise InscriptionRefuseeError(msg, "deja_membre", 409)


@transaction.atomic
def ouvrir_compte(
    *,
    raison_sociale: str,
    email: str,
    mot_de_passe: str,
    prenom: str = "",
    nom: str = "",
    formule: Formule | None = None,
    activer_abonnement: bool,
    message: str = "",
) -> Ouverture:
    """Crée l'organisation, son propriétaire et ses identifiants.

    `activer_abonnement` sépare les deux chemins, et le nom est volontairement
    explicite : un booléen appelé `souscrire` aurait laissé croire qu'on peut
    l'omettre. Ici l'appelant DOIT dire s'il encaisse ou non.

    - **True** (administration) : la formule est souscrite, les crédits dotés.
    - **False** (public) : une demande est enregistrée, aucun crédit n'est
      délivré. Le visiteur entre dans son espace et y voit sa demande en cours.
    """
    contact, _ = Customer.objects.get_or_create(
        email=email,
        defaults={
            "first_name": prenom,
            "last_name": nom,
            "company_name": raison_sociale,
            "customer_type": CustomerType.B2B,
        },
    )
    organisation = services.creer_organisation(
        raison_sociale=raison_sociale, contact=contact
    )
    authentification.creer_compte(contact, mot_de_passe=mot_de_passe)

    abonnement = None
    demande = None
    if formule is not None:
        if activer_abonnement:
            abonnement = services.souscrire(organisation, formule)
        else:
            # La formule choisie est MEMORISEE, elle n'est plus DEMANDEE.
            #
            # Cette inscription ouvrait une `DemandeCommerciale` qui atterrissait
            # dans la file << A traiter >> de l'administration. C'etait juste
            # avant Stripe : quelqu'un devait accorder la souscription a la main.
            # Depuis, le visiteur paie lui-meme et ses credits arrivent par le
            # webhook — la demande n'attendait plus rien de personne, et polluait
            # une file censee ne contenir que ce qui reclame une decision
            # humaine. La cliente l'a dit le 07/08/2026 : << elle n'a pas besoin
            # d'accorder quoi que ce soit >>.
            #
            # L'intention, elle, sert encore : l'ecran de souscription
            # pre-selectionne la formule choisie sur la page partenaires, pour
            # que le visiteur n'ait pas a la rechoisir apres son inscription.
            organisation.formule_pressentie = formule
            organisation.save(update_fields=["formule_pressentie", "updated_at"])

    return Ouverture(
        organisation=organisation,
        contact=contact,
        formule=formule,
        abonnement=abonnement,
        demande=demande,
    )

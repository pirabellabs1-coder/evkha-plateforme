"""Remet la plateforme à zéro : clients, documents, crédits, incidents.

Demandé par la cliente le 07/08/2026, avant l'ouverture réelle : la base de
recette portait deux organisations d'essai, sept contacts, trente-huit
générations et quatre-vingt-cinq incidents accumulés pendant la mise au point.
Aucun de ces chiffres ne devait subsister le jour où un vrai partenaire arrive.

**L'API de Coolify n'expose aucune exécution de commande dans le conteneur** —
`execute`, `command` et `exec` répondent toutes 404. Cette commande est donc
jouée au démarrage, comme `assurer_admin`. Ce qui pose un problème redoutable :
une variable d'environnement oubliée effacerait la base à CHAQUE redémarrage,
y compris six mois plus tard, avec de vrais clients dedans.

D'où la confirmation **datée**. `EVKHA_REINITIALISER` doit valoir exactement
`EFFACER-TOUT-AAAA-MM-JJ`, avec la date du jour. Passé minuit, la même valeur
ne vaut plus rien : une variable qu'on a oublié de retirer devient inoffensive
d'elle-même. C'est le seul garde-fou qui ne dépend pas de la mémoire de
quelqu'un.

Ce qui est CONSERVÉ, et pourquoi :

- les **formules** et leurs tarifs Stripe — les recréer coûterait de recoller
  quatre identifiants `price_` à la main, et une erreur de recopie ferait payer
  le mauvais montant à un client ;
- le **catalogue de livrables** — même raison ;
- les comptes **superutilisateur et personnel** — les effacer fermerait la porte
  de l'administration sur l'administratrice elle-même.

Les comptes clients Django (`auth_user` non-personnel) partent AVEC leur
contact : les laisser derrière empêcherait une réinscription avec la même
adresse, sans qu'aucun message ne dise pourquoi.
"""
from __future__ import annotations

import os
from typing import Any

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

#: Préfixe de la phrase de confirmation. La date du jour la complète.
PREFIXE_CONFIRMATION = "EFFACER-TOUT-"


def phrase_attendue() -> str:
    """La confirmation valable AUJOURD'HUI, et aujourd'hui seulement."""
    return PREFIXE_CONFIRMATION + timezone.now().date().isoformat()


class Command(BaseCommand):
    help = "Efface clients, documents, credits et incidents. Confirmation datee requise."

    def handle(self, *args: Any, **options: Any) -> None:
        demande = os.environ.get("EVKHA_REINITIALISER", "").strip()
        if not demande:
            return

        attendue = phrase_attendue()
        if demande != attendue:
            self.stdout.write(self.style.WARNING(
                "reinitialiser_la_plateforme : confirmation refusee. "
                f"EVKHA_REINITIALISER vaut « {demande} », attendu « {attendue} ». "
                "Rien n'a ete efface."
            ))
            return

        compte = self._effacer()

        self.stdout.write(self.style.SUCCESS(
            "reinitialiser_la_plateforme : plateforme remise a zero."
        ))
        for etiquette, nombre in compte.items():
            self.stdout.write(f"    {nombre:6} {etiquette}")
        self.stdout.write(self.style.WARNING(
            "RETIREZ EVKHA_REINITIALISER de l'environnement. La phrase datee la "
            "rend inoffensive des demain, mais un redemarrage aujourd'hui "
            "effacerait de nouveau."
        ))

    @transaction.atomic
    def _effacer(self) -> dict[str, int]:
        """Efface dans l'ordre des dépendances, et compte ce qui part.

        Une seule transaction : un effacement à moitié fait laisserait des
        commandes sans client et des générations sans commande — une base
        incohérente est pire qu'une base pleine.
        """
        from catalog.models import Offer  # noqa: PLC0415, F401 — conserve
        from customers.models import Customer, Subscription  # noqa: PLC0415
        from delivery.models import DeliveryBatch, DeliveryEvent  # noqa: PLC0415
        from documents.models import DocumentArtifact  # noqa: PLC0415
        from generation.models import (  # noqa: PLC0415
            ChapterGeneration,
            CoherenceFact,
            GenerationJob,
            SocleDonnees,
        )
        from intake.models import IntakeSubmission  # noqa: PLC0415
        from integrations.models import WebhookEvent  # noqa: PLC0415
        from monitoring.models import OperationalIncident  # noqa: PLC0415
        from orders.models import Order  # noqa: PLC0415
        from organisations.models import (  # noqa: PLC0415
            AbonnementOrganisation,
            ClientFinal,
            CompteClient,
            DemandeCommerciale,
            Encaissement,
            JetonAcces,
            MembreOrganisation,
            MouvementCredit,
            Organisation,
            PieceJointe,
            PortefeuilleCredits,
        )

        # Les identifiants des comptes clients, relevés AVANT de les effacer :
        # ce sont ces utilisateurs Django qu'il faudra retirer ensuite.
        utilisateurs_clients = list(
            CompteClient.objects.values_list("user_id", flat=True)
        )

        compte: dict[str, int] = {}

        def vider(modele: Any, etiquette: str) -> None:
            nombre = modele.objects.count()
            if nombre:
                modele.objects.all().delete()
            compte[etiquette] = nombre

        # Production : du plus dépendant vers le moins.
        vider(DeliveryEvent, "evenements de livraison")
        vider(DeliveryBatch, "lots de livraison")
        vider(DocumentArtifact, "documents produits")
        vider(ChapterGeneration, "chapitres generes")
        vider(CoherenceFact, "faits de coherence")
        vider(SocleDonnees, "socles de donnees")
        vider(GenerationJob, "generations")
        vider(IntakeSubmission, "formulaires recus")
        vider(Order, "commandes")

        # Organisations et crédits.
        vider(Encaissement, "encaissements")
        vider(MouvementCredit, "mouvements de credit")
        vider(PortefeuilleCredits, "portefeuilles")
        vider(AbonnementOrganisation, "abonnements")
        vider(JetonAcces, "jetons d'acces")
        vider(PieceJointe, "pieces jointes")
        vider(DemandeCommerciale, "demandes commerciales")
        vider(ClientFinal, "clients finaux")
        vider(CompteClient, "comptes d'espace")
        vider(MembreOrganisation, "membres")
        vider(Organisation, "organisations")

        # Contacts et abonnements historiques.
        vider(Subscription, "abonnements historiques")
        vider(Customer, "contacts clients")

        # Supervision et journaux d'evenements.
        vider(OperationalIncident, "incidents")
        vider(WebhookEvent, "evenements de webhook")

        # Les utilisateurs Django des comptes clients. JAMAIS un
        # superutilisateur ni un membre du personnel : effacer l'administratrice
        # fermerait la porte derriere elle.
        clients = User.objects.filter(
            id__in=utilisateurs_clients, is_superuser=False, is_staff=False
        )
        compte["comptes de connexion"] = clients.count()
        clients.delete()

        return compte

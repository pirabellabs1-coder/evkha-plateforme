"""Les adresses de l'audience, et ce que chacune a demandé.

UNE ligne par adresse (`Contact`), et une ligne par demande (`Demande`) :
la gérante veut savoir QUI s'intéresse à QUOI, et une même personne peut
prendre la checklist puis le lexique, puis s'inscrire à la lettre.

## Le consentement à la lettre est un fait daté, jamais déduit

Prendre une ressource ne vaut PAS inscription à la lettre : la case est
distincte, décochée par défaut, et ne conditionne pas le téléchargement
(règle relevée dans `contenuRessources.FORMULAIRES`). `lettre_le` n'est posé
que par un consentement explicite ; `desinscrit_le` le retire sans effacer
l'historique des demandes.

## Le double consentement (26/11/2026)

Cocher la case ne suffit plus : `confirmation_demandee_le` est posé, et la
pompe de `lettre.envoi` envoie un courriel de confirmation. Seul le clic sur
ce lien — preuve que la personne lit cette boîte — pose `lettre_le`. C'est
aussi ce qui permet de revenir après une désinscription : une requête
anonyme ne le peut pas, la boîte aux lettres si. Une personne qui demande l'EFFACEMENT (RGPD,
art. 17) est supprimée avec ses demandes (`dashboard.audience.supprimer`).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from django.db import models
from django.db.models import F, Q

from core.models import UUIDModel


class Ressource(models.TextChoices):
    CHECKLIST = "checklist", "Checklist : créer sa micro-entreprise en 10 étapes"
    LEXIQUE = "lexique", "Lexique EVKHA de l'entrepreneuriat"


class Origine(models.TextChoices):
    """D'où vient une demande : une ressource, ou l'inscription seule."""

    CHECKLIST = "checklist", "Checklist"
    LEXIQUE = "lexique", "Lexique"
    LETTRE = "lettre", "Lettre d'information"


class Contact(UUIDModel):
    #: Unique, en minuscules : `audience.vues_publiques.adresse_normalisee`.
    email = models.EmailField(max_length=254, unique=True)
    #: Consentement explicite à la lettre d'information. Vide = pas inscrit.
    lettre_le = models.DateTimeField(null=True, blank=True)
    desinscrit_le = models.DateTimeField(null=True, blank=True)
    #: Le secret du lien de DÉSINSCRIPTION. Opaque, sans donnée personnelle.
    #: La confirmation, elle, a son propre jeton signé et daté
    #: (`lettre.gabarit.jeton_de_confirmation`) : un lien de désinscription
    #: transféré ne doit pas permettre de réinscrire quelqu'un.
    jeton = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    #: Dernière demande d'inscription en attente de confirmation.
    confirmation_demandee_le = models.DateTimeField(null=True, blank=True)
    #: Dernier courriel de confirmation parti (la pompe le compare à la demande).
    confirmation_envoyee_le = models.DateTimeField(null=True, blank=True)
    #: Courriels de confirmation partis sans clic en retour. Au-delà de
    #: `audience.vues_publiques.RELANCES_MAX`, plus rien ne part : le
    #: formulaire public ne doit pas servir à écrire sans fin à un tiers.
    confirmations_sans_reponse = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "contact"
        verbose_name_plural = "contacts"

    def __str__(self) -> str:
        return self.email

    @property
    def inscrit_a_la_lettre(self) -> bool:
        return self.lettre_le is not None and (
            self.desinscrit_le is None or self.desinscrit_le < self.lettre_le
        )

    def desinscrire(self, quand: datetime) -> None:
        """Retire de la lettre ET annule une confirmation en attente : sinon
        le courriel de confirmation partirait encore, et son lien réinscrirait
        la personne. Le SEUL chemin de désinscription — la page publique et
        l'administration y passent toutes deux (règle 5)."""
        if self.inscrit_a_la_lettre:
            self.desinscrit_le = quand
        self.confirmation_demandee_le = None
        self.save(update_fields=["desinscrit_le", "confirmation_demandee_le", "updated_at"])

    def confirmer(self, quand: datetime) -> None:
        """Le clic dans le courriel de confirmation : l'inscription est faite.

        La date de la DEMANDE reste : avec `lettre_le`, elle est la trace du
        double consentement (une demande, puis un clic dans la boîte)."""
        self.lettre_le = quand
        self.confirmations_sans_reponse = 0
        self.save(update_fields=["lettre_le", "confirmations_sans_reponse", "updated_at"])


def inscrits_q() -> Q:
    """Le filtre SQL de `Contact.inscrit_a_la_lettre` — la même règle, écrite
    à côté pour que les deux ne divergent pas (règle 5)."""
    return Q(lettre_le__isnull=False) & (
        Q(desinscrit_le__isnull=True) | Q(desinscrit_le__lt=F("lettre_le"))
    )


class Demande(UUIDModel):
    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, related_name="demandes"
    )
    origine = models.CharField(max_length=16, choices=Origine.choices)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "demande"
        verbose_name_plural = "demandes"

    def __str__(self) -> str:
        return f"{self.contact.email} · {self.origine}"

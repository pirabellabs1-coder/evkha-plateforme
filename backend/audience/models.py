"""Les adresses de l'audience, et ce que chacune a demandé.

UNE ligne par adresse (`Contact`), et une ligne par demande (`Demande`) :
la gérante veut savoir QUI s'intéresse à QUOI, et une même personne peut
prendre la checklist puis le lexique, puis s'inscrire à la lettre.

## Le consentement à la lettre est un fait daté, jamais déduit

Prendre une ressource ne vaut PAS inscription à la lettre : la case est
distincte, décochée par défaut, et ne conditionne pas le téléchargement
(règle relevée dans `contenuRessources.FORMULAIRES`). `lettre_le` n'est posé
que par un consentement explicite ; `desinscrit_le` le retire sans effacer
l'historique des demandes. Une personne qui demande l'EFFACEMENT (RGPD,
art. 17) est supprimée avec ses demandes (`dashboard.audience.supprimer`).
"""
from __future__ import annotations

from django.db import models

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

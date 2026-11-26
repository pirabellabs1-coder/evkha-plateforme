"""La lettre d'information d'EVKHA : modèles, lettres, automatisations, envois.

Les ABONNÉS ne vivent pas ici : ce sont les `audience.Contact` dont
`inscrit_a_la_lettre` est vrai — une seule source pour savoir qui a consenti
(règle 5). Ce module dit ce qu'on leur écrit, et garde la trace de chaque
message parti.

## Un envoi = une ligne, et une seule

`Envoi` porte une contrainte d'unicité par (lettre, contact) et par
(étape, contact). C'est elle, et non une précaution du code, qui garantit
qu'une personne ne reçoit pas deux fois le même message — après un
redémarrage, une pompe lancée deux fois, un déploiement en plein envoi.
"""
from __future__ import annotations

from django.db import models
from django.db.models import Q

from audience.models import Contact
from core.models import UUIDModel

#: Les images glissées dans les lettres. Préfixe PUBLIC (`evkha.media`) : une
#: image de courriel doit s'afficher sans signature, chez n'importe quel
#: destinataire, des mois après l'envoi.
PREFIXE_IMAGES = "lettre-vitrine"


class Modele(UUIDModel):
    """Un point de départ réutilisable : on en tire une lettre en un clic."""

    nom = models.CharField(max_length=120)
    objet = models.CharField(max_length=200, blank=True)
    apercu = models.CharField(max_length=200, blank=True)
    corps_html = models.TextField(blank=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "modèle de lettre"
        verbose_name_plural = "modèles de lettre"

    def __str__(self) -> str:
        return self.nom


class StatutLettre(models.TextChoices):
    BROUILLON = "brouillon", "Brouillon"
    PROGRAMMEE = "programmee", "Programmée"
    EN_COURS = "en_cours", "Envoi en cours"
    ENVOYEE = "envoyee", "Envoyée"
    ANNULEE = "annulee", "Annulée"


class Lettre(UUIDModel):
    """Une lettre envoyée UNE fois à tous les inscrits du moment."""

    objet = models.CharField(max_length=200)
    #: Le texte gris qu'affichent les messageries à côté de l'objet.
    apercu = models.CharField(max_length=200, blank=True)
    corps_html = models.TextField(blank=True)
    statut = models.CharField(
        max_length=16, choices=StatutLettre.choices, default=StatutLettre.BROUILLON
    )
    programmee_pour = models.DateTimeField(null=True, blank=True)
    lancee_le = models.DateTimeField(null=True, blank=True)
    terminee_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "lettre"
        verbose_name_plural = "lettres"

    def __str__(self) -> str:
        return self.objet


class Declencheur(models.TextChoices):
    INSCRIPTION = "inscription", "Confirmation de l'inscription à la lettre"
    CHECKLIST = "checklist", "Téléchargement de la checklist"
    LEXIQUE = "lexique", "Téléchargement du lexique"


class Automatisation(UUIDModel):
    """Une suite de messages partant d'un événement, chacune à son délai.

    Elle ne concerne que les personnes dont l'événement est POSTÉRIEUR à son
    activation (`active_depuis`) : activer une suite de bienvenue ne doit pas
    écrire d'un coup à toute la liste existante.
    """

    nom = models.CharField(max_length=120)
    declencheur = models.CharField(max_length=16, choices=Declencheur.choices)
    active = models.BooleanField(default=False)
    active_depuis = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "automatisation"
        verbose_name_plural = "automatisations"

    def __str__(self) -> str:
        return self.nom


class Etape(UUIDModel):
    automatisation = models.ForeignKey(
        Automatisation, on_delete=models.CASCADE, related_name="etapes"
    )
    ordre = models.PositiveSmallIntegerField()
    #: Jours après l'ÉVÉNEMENT (et non après l'étape précédente) : 0 = aussitôt.
    delai_jours = models.PositiveSmallIntegerField(default=0)
    objet = models.CharField(max_length=200)
    apercu = models.CharField(max_length=200, blank=True)
    corps_html = models.TextField(blank=True)

    class Meta:
        ordering = ["automatisation", "ordre"]
        constraints = [
            models.UniqueConstraint(
                fields=["automatisation", "ordre"], name="lettre_etape_ordre_unique"
            )
        ]

    def __str__(self) -> str:
        return f"{self.automatisation.nom} · {self.ordre}"


class StatutEnvoi(models.TextChoices):
    A_ENVOYER = "a_envoyer", "À envoyer"
    EN_COURS = "en_cours", "En cours"
    ENVOYE = "envoye", "Envoyé"
    ECHEC = "echec", "Échec"
    #: Désinscription, automatisation mise en pause ou lettre annulée entre la
    #: mise en file et le départ.
    IGNORE = "ignore", "Non envoyé"


class Envoi(UUIDModel):
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="envois")
    lettre = models.ForeignKey(
        Lettre, null=True, blank=True, on_delete=models.CASCADE, related_name="envois"
    )
    etape = models.ForeignKey(
        Etape, null=True, blank=True, on_delete=models.CASCADE, related_name="envois"
    )
    statut = models.CharField(
        max_length=16, choices=StatutEnvoi.choices, default=StatutEnvoi.A_ENVOYER
    )
    erreur = models.CharField(max_length=300, blank=True)
    message_id = models.CharField(max_length=200, blank=True)
    pris_le = models.DateTimeField(null=True, blank=True)
    envoye_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["lettre", "contact"],
                condition=Q(lettre__isnull=False),
                name="lettre_envoi_unique_par_lettre",
            ),
            models.UniqueConstraint(
                fields=["etape", "contact"],
                condition=Q(etape__isnull=False),
                name="lettre_envoi_unique_par_etape",
            ),
            models.CheckConstraint(
                condition=(
                    Q(lettre__isnull=False, etape__isnull=True)
                    | Q(lettre__isnull=True, etape__isnull=False)
                ),
                name="lettre_envoi_une_seule_source",
            ),
        ]
        indexes = [models.Index(fields=["statut"])]

    def __str__(self) -> str:
        return f"{self.contact.email} · {self.statut}"

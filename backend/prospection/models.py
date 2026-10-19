"""Le modèle de données de la prospection (espace admin).

Un sous-système neuf, demandé le 18/10/2026 : trouver des prospects, juger
s'ils sont susceptibles de prendre un abonnement, préparer des e-mails et leurs
relances, les suivre (ouvertures, réponses, conversions). Rien d'automatique à
l'envoi : chaque message est RELU et VALIDÉ par un humain avant de partir
(exigence de l'utilisateur, et règle de sécurité du système).

Les états portent l'invariant. Un `Message` ne peut passer à ENVOYE que depuis
VALIDE ou PROGRAMME — jamais depuis BROUILLON. L'invariant vit dans
`services.envoyer_message` (une transition d'état ne se contraint pas en base),
et un test échoue si un brouillon pouvait partir.
"""
from __future__ import annotations

from django.db import models

from core.models import UUIDModel


class StatutCampagne(models.TextChoices):
    ACTIVE = "active", "Active"
    EN_PAUSE = "en_pause", "En pause"
    TERMINEE = "terminee", "Terminée"


class StatutProspect(models.TextChoices):
    NOUVEAU = "nouveau", "Nouveau"
    QUALIFIE = "qualifie", "Qualifié"
    CONTACTE = "contacte", "Contacté"
    EN_RELANCE = "en_relance", "En relance"
    A_REPONDU = "a_repondu", "A répondu"
    CONVERTI = "converti", "Converti"
    EXCLU = "exclu", "Exclu"
    DESINSCRIT = "desinscrit", "Désinscrit"


class StatutMessage(models.TextChoices):
    BROUILLON = "brouillon", "Brouillon"
    VALIDE = "valide", "Validé"
    PROGRAMME = "programme", "Programmé"
    ENVOYE = "envoye", "Envoyé"
    ECHOUE = "echoue", "Échec"
    ANNULE = "annule", "Annulé"


#: Les seuls états d'où un message PEUT partir. Un brouillon n'en fait jamais
#: partie : c'est la garantie « rien ne part sans validation ».
ETATS_ENVOYABLES = frozenset({StatutMessage.VALIDE, StatutMessage.PROGRAMME})


class TypeEvenement(models.TextChoices):
    ENVOYE = "envoye", "Envoyé"
    DELIVRE = "delivre", "Délivré"
    OUVERT = "ouvert", "Ouvert"
    CLIQUE = "clique", "Cliqué"
    REPONDU = "repondu", "A répondu"
    REBOND = "rebond", "Rebond"
    DESINSCRIT = "desinscrit", "Désinscrit"
    PLAINTE = "plainte", "Plainte"


class Campagne(UUIDModel):
    """Un lot de prospection : un secteur, une zone, une offre visée."""

    nom = models.CharField(max_length=200)
    secteur = models.CharField(max_length=200, blank=True)
    zone = models.CharField(max_length=200, blank=True)
    #: L'offre qu'on cherche à vendre, en clair (le catalogue n'est pas figé).
    offre_visee = models.CharField(max_length=200, blank=True)
    statut = models.CharField(
        max_length=16, choices=StatutCampagne.choices, default=StatutCampagne.ACTIVE
    )
    notes = models.TextField(blank=True)
    #: L'humain qui a ouvert la campagne (jamais un envoi automatique).
    cree_par = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.nom


class Prospect(UUIDModel):
    """Une cible de prospection, et ce qu'on sait d'elle."""

    campagne = models.ForeignKey(
        Campagne, on_delete=models.CASCADE, related_name="prospects", null=True, blank=True
    )
    raison_sociale = models.CharField(max_length=200)
    secteur = models.CharField(max_length=200, blank=True)
    zone = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    nom_contact = models.CharField(max_length=200, blank=True)
    fonction = models.CharField(max_length=200, blank=True)
    site_web = models.URLField(blank=True)
    #: D'où vient le prospect : « recherche IA », « import CSV », « manuel »…
    source = models.CharField(max_length=120, blank=True)
    statut = models.CharField(
        max_length=16, choices=StatutProspect.choices, default=StatutProspect.NOUVEAU
    )
    #: Jugé par l'agent de qualification : 0 à 100, avec sa raison.
    score_adequation = models.PositiveSmallIntegerField(null=True, blank=True)
    raison_score = models.TextField(blank=True)
    #: Opt-out : une fois retiré, aucun message ne part plus (voir services).
    consentement_retire = models.BooleanField(default=False)
    desinscrit_le = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["statut"]),
        ]

    def __str__(self) -> str:
        return f"{self.raison_sociale} ({self.email or 'sans e-mail'})"

    @property
    def contactable(self) -> bool:
        """Peut-on lui écrire ? Un e-mail, pas de désinscription, pas exclu."""
        return bool(
            self.email
            and not self.consentement_retire
            and self.statut not in (StatutProspect.DESINSCRIT, StatutProspect.EXCLU)
        )


class Sequence(UUIDModel):
    """Une étape de la séquence d'une campagne : le premier mail, puis les relances.

    `ordre` 0 est le premier message ; 1, 2, 3… les relances (quatre ou cinq,
    demande de l'utilisateur). `delai_jours` est le délai depuis l'étape
    précédente avant de proposer ce message.
    """

    campagne = models.ForeignKey(
        Campagne, on_delete=models.CASCADE, related_name="sequence"
    )
    ordre = models.PositiveSmallIntegerField()
    delai_jours = models.PositiveSmallIntegerField(default=0)
    objet_gabarit = models.CharField(max_length=300, blank=True)
    corps_gabarit = models.TextField(blank=True)

    class Meta:
        ordering = ["campagne_id", "ordre"]
        constraints = [
            models.UniqueConstraint(
                fields=["campagne", "ordre"], name="uniq_sequence_campagne_ordre"
            )
        ]

    def __str__(self) -> str:
        return f"{self.campagne_id} · étape {self.ordre}"

    @property
    def est_une_relance(self) -> bool:
        return self.ordre > 0


class Message(UUIDModel):
    """Un e-mail préparé pour un prospect, à une étape de la séquence.

    Il naît BROUILLON. Il ne part qu'une fois VALIDÉ par un humain
    (`services.valider_message`), puis ENVOYÉ (`services.envoyer_message`), qui
    REFUSE tout message encore en brouillon, annulé, ou dont le prospect s'est
    désinscrit. L'envoi n'est jamais un effet de bord d'une création.
    """

    prospect = models.ForeignKey(
        Prospect, on_delete=models.CASCADE, related_name="messages"
    )
    campagne = models.ForeignKey(
        Campagne, on_delete=models.CASCADE, related_name="messages", null=True, blank=True
    )
    sequence = models.ForeignKey(
        Sequence, on_delete=models.SET_NULL, related_name="messages", null=True, blank=True
    )
    objet = models.CharField(max_length=300)
    corps = models.TextField()
    statut = models.CharField(
        max_length=16, choices=StatutMessage.choices, default=StatutMessage.BROUILLON
    )
    #: Qui a validé, et quand : une validation est un acte humain, horodaté.
    valide_par = models.CharField(max_length=200, blank=True)
    valide_le = models.DateTimeField(null=True, blank=True)
    programme_pour = models.DateTimeField(null=True, blank=True)
    envoye_le = models.DateTimeField(null=True, blank=True)
    provider_message_id = models.CharField(max_length=200, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["statut"]),
            models.Index(fields=["provider_message_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.objet} → {self.prospect_id} ({self.statut})"

    @property
    def envoyable(self) -> bool:
        """L'état autorise-t-il l'envoi ? (le prospect est jugé par le service.)"""
        return self.statut in ETATS_ENVOYABLES


class Evenement(UUIDModel):
    """Un événement sur un message : ouvert, cliqué, a répondu, désinscrit…

    Alimenté par les webhooks Brevo. Les métriques (taux d'ouverture, de
    réponse, de conversion) se calculent à partir de ces lignes — jamais
    stockées à part, pour qu'un recompte donne toujours le même chiffre.
    """

    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="evenements"
    )
    type = models.CharField(max_length=16, choices=TypeEvenement.choices)
    horodatage = models.DateTimeField()
    #: La charge brute du webhook, pour l'audit : on ne jette pas la source.
    charge = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-horodatage"]
        indexes = [models.Index(fields=["message", "type"])]

    def __str__(self) -> str:
        return f"{self.message_id} · {self.type}"

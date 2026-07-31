"""Organisations, portefeuille de crédits et clients finaux (lot 4).

Le cahier des charges (§11 et §15) demande trois choses que le dépôt ne sait
pas faire aujourd'hui :

1. une **organisation** — une agence dont plusieurs collaborateurs partagent un
   même portefeuille de crédits. Le dépôt ne connaît que `Customer`, une
   adresse e-mail isolée ;
2. un **portefeuille** avec un solde et un **journal de mouvements** : débit au
   lancement, remboursement sur échec définitif, dotation manuelle motivée.
   Aujourd'hui un « crédit » est un `Order` pré-créé porteur d'un lien Tally :
   il n'y a ni solde, ni journal, ni remboursement possible ;
3. un **client final** réutilisable, porteur du logo et de la charte. Ces
   informations vivent aujourd'hui dans les variables du formulaire d'une
   commande, donc à ressaisir à chaque étude.

`Customer` n'est pas modifié. Il reste la porte d'entrée du flux Systeme.io en
service, et une organisation le référence. Remplacer `Customer` reviendrait à
toucher `Order`, `intake`, `dashboard` et la facturation existante pour un gain
nul (règle : rien de ce qui fonctionne n'est refait).

## Le solde n'est pas un compteur

Il est **calculé depuis le journal**. Un compteur que l'on incrémente dérive dès
le premier débit interrompu ou la première double écriture, et rien ne permet
alors de savoir lequel des deux chiffres est vrai. Un journal, lui, est
auditable ligne à ligne — ce que le cahier des charges exige explicitement
(« chaque mouvement de crédit est journalisé : date, motif, document concerné,
auteur »). Aux volumes en jeu — quelques dizaines de mouvements par
organisation et par mois — l'agrégat coûte moins qu'un bug de solde.
"""
from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from core.models import UUIDModel
from customers.models import Customer


class RoleOrganisation(models.TextChoices):
    """Rôles du §12. Les droits d'administration EVKHA vivent ailleurs."""

    PROPRIETAIRE = "proprietaire", "Propriétaire"
    MEMBRE = "membre", "Membre"
    LECTURE = "lecture", "Lecture seule"


class StatutOrganisation(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDUE = "suspendue", "Suspendue"


class Organisation(UUIDModel):
    """Agence partenaire ou client direct. Porte l'abonnement et les crédits."""

    raison_sociale = models.CharField(max_length=200)
    #: Contact de rattachement, réutilisé pour la facturation et les e-mails.
    #: `PROTECT` : supprimer un client alors qu'une organisation en dépend
    #: laisserait des crédits sans destinataire.
    contact = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="organisations"
    )
    statut = models.CharField(
        max_length=12, choices=StatutOrganisation.choices,
        default=StatutOrganisation.ACTIVE,
    )
    #: Marque blanche : aucune mention d'EVKHA sur les documents produits (§07).
    marque_blanche = models.BooleanField(default=True)
    #: Options du §10.6, activables par organisation.
    validation_socle_par_client = models.BooleanField(default=False)
    controle_qualite_avant_envoi = models.BooleanField(default=False)
    #: Seuil d'alerte de solde bas (§12, notifications).
    seuil_alerte_credits = models.PositiveSmallIntegerField(default=1)

    # ── Profil et charte de l'abonné ─────────────────────────────────────────
    # Décision du 30/07/2026 : l'espace client est celui d'UN abonné, qui gère
    # SES propres études. Ce n'est donc pas une liste de clients finaux mais un
    # profil unique, porté par l'organisation elle-même.
    #
    # Écart assumé avec le §9.2 du cahier des charges, qui décrit des fiches
    # clients finaux réutilisables pour la marque blanche des agences. Le modèle
    # `ClientFinal` reste en place pour ce cas s'il revient ; il n'alimente plus
    # l'espace client.
    secteur = models.CharField(max_length=200, blank=True)
    pays = models.CharField(max_length=120, blank=True)
    region = models.CharField(max_length=120, blank=True)
    ville = models.CharField(max_length=120, blank=True)

    logo_url = models.URLField(blank=True)
    couleur_principale = models.CharField(max_length=7, blank=True)
    couleur_secondaire = models.CharField(max_length=7, blank=True)
    couleur_fond = models.CharField(max_length=7, blank=True)
    mention_confidentialite = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["raison_sociale"]
        verbose_name = "organisation"
        verbose_name_plural = "organisations"

    def __str__(self) -> str:
        return self.raison_sociale

    @property
    def active(self) -> bool:
        return self.statut == StatutOrganisation.ACTIVE


class MembreOrganisation(UUIDModel):
    """Rattachement d'une personne à une organisation, avec son rôle."""

    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="membres"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="appartenances"
    )
    role = models.CharField(
        max_length=16, choices=RoleOrganisation.choices,
        default=RoleOrganisation.MEMBRE,
    )
    invite_le = models.DateTimeField(null=True, blank=True)
    revoque_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["organisation", "customer"]
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "customer"], name="uniq_membre_par_organisation"
            )
        ]
        verbose_name = "membre d'organisation"
        verbose_name_plural = "membres d'organisation"

    def __str__(self) -> str:
        return f"{self.customer.email} · {self.role}"

    @property
    def actif(self) -> bool:
        return self.revoque_le is None


class ReportCredits(models.TextChoices):
    """Point « à trancher » du §18, tranché : aucun report.

    Réponse de la cliente en entretien : les crédits non consommés ne se
    reportent pas. Les deux autres valeurs existent parce que le cahier des
    charges les nomme et que revenir dessus ne doit pas demander de migration.
    """

    AUCUN = "aucun", "Aucun report"
    INTEGRAL = "integral", "Report intégral"
    PLAFONNE = "plafonne", "Report plafonné"


class Formule(UUIDModel):
    """Offre commerciale : dotation, tarif, options (§11).

    Créée et modifiée depuis l'administration, sans déploiement — c'est une
    exigence de recette (« une formule d'abonnement se crée et se modifie sans
    déploiement »).
    """

    libelle = models.CharField(max_length=140)
    code = models.SlugField(unique=True)
    credits_par_echeance = models.PositiveSmallIntegerField(default=0)
    prix_mensuel_cents = models.PositiveIntegerField(default=0)
    devise = models.CharField(max_length=3, default="EUR")
    report_credits = models.CharField(
        max_length=12, choices=ReportCredits.choices, default=ReportCredits.AUCUN
    )
    #: Utilisé seulement quand `report_credits` vaut « plafonné ».
    plafond_report = models.PositiveSmallIntegerField(default=0)
    #: Régénérations offertes avant facturation en crédits (§11).
    regenerations_offertes = models.PositiveSmallIntegerField(default=1)
    validation_socle_par_client = models.BooleanField(default=False)
    controle_qualite_avant_envoi = models.BooleanField(default=False)
    #: Prix d'un crédit acheté AU-DELÀ de la dotation mensuelle, en centimes.
    #: Il figure sur la page publique (« crédit supplémentaire : 59 € ») et
    #: décroît avec la formule. Stocké et non calculé : ce n'est pas un rapport
    #: entre deux champs, contrairement au coût par livrable inclus — c'est un
    #: tarif commercial décidé formule par formule.
    prix_credit_supplementaire_cents = models.PositiveIntegerField(default=0)
    #: Identifiant du prix chez le prestataire de paiement (Stripe). Vide tant
    #: que la formule n'est pas rattachée à un tarif.
    reference_paiement = models.CharField(max_length=160, blank=True)
    #: Argument commercial propre à la formule, affiché sur la page publique
    #: (« Convention-cadre possible », « Interlocutrice dédiée »). Une liste,
    #: pas un texte libre : la page en fait des puces.
    avantages = models.JSONField(default=list, blank=True)
    #: Ordre d'affichage sur la page publique. À défaut, les formules sortent
    #: par prix croissant — ce qui est l'ordre voulu aujourd'hui, mais qui
    #: cesserait de l'être si une formule annuelle arrivait.
    rang = models.PositiveSmallIntegerField(default=0)
    #: Formule mise en avant (« CHOISIR LA FORMULE PRO » sur la page).
    mise_en_avant = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["prix_mensuel_cents", "libelle"]
        verbose_name = "formule"
        verbose_name_plural = "formules"

    def __str__(self) -> str:
        return self.libelle


class StatutAbonnement(models.TextChoices):
    ACTIF = "actif", "Actif"
    SUSPENDU = "suspendu", "Suspendu"
    RESILIE = "resilie", "Résilié"


class AbonnementOrganisation(UUIDModel):
    """Souscription d'une organisation à une formule, avec ses échéances."""

    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="abonnements"
    )
    formule = models.ForeignKey(
        Formule, on_delete=models.PROTECT, related_name="abonnements"
    )
    statut = models.CharField(
        max_length=12, choices=StatutAbonnement.choices, default=StatutAbonnement.ACTIF
    )
    debut_le = models.DateTimeField()
    fin_le = models.DateTimeField(null=True, blank=True)
    #: Dernière période dotée, au format `AAAA-MM`. C'est la clé d'idempotence
    #: de la dotation mensuelle : sans elle, un planificateur relancé deux fois
    #: créditerait deux fois.
    derniere_periode_dotee = models.CharField(max_length=7, blank=True, db_index=True)
    reference_paiement = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["-debut_le"]
        constraints = [
            models.UniqueConstraint(
                fields=["organisation"],
                condition=models.Q(statut="actif"),
                name="uniq_abonnement_actif_par_organisation",
            )
        ]
        verbose_name = "abonnement"
        verbose_name_plural = "abonnements"

    def __str__(self) -> str:
        return f"{self.organisation} · {self.formule} · {self.statut}"


class PortefeuilleCredits(UUIDModel):
    """Portefeuille d'une organisation. Le solde vit dans le journal.

    Aucun champ `solde` : voir l'en-tête du module. Ce modèle n'existe que pour
    donner un point d'ancrage aux mouvements et un verrou de concurrence lors
    d'un débit.
    """

    organisation = models.OneToOneField(
        Organisation, on_delete=models.CASCADE, related_name="portefeuille"
    )

    class Meta:
        verbose_name = "portefeuille de crédits"
        verbose_name_plural = "portefeuilles de crédits"

    def __str__(self) -> str:
        return f"Portefeuille de {self.organisation}"

    @property
    def solde(self) -> int:
        """Somme algébrique du journal. Seule définition du solde."""
        total = self.mouvements.aggregate(total=Sum("quantite"))["total"]
        return int(total or 0)


class TypeMouvement(models.TextChoices):
    """Les cinq natures de mouvement nommées au §11."""

    DOTATION = "dotation", "Dotation d'abonnement"
    ACHAT = "achat", "Achat de crédits additionnels"
    GESTE = "geste", "Geste commercial"
    DEBIT = "debit", "Débit pour une génération"
    REMBOURSEMENT = "remboursement", "Remboursement sur échec"
    EXPIRATION = "expiration", "Expiration en fin de période"


class MouvementCredit(UUIDModel):
    """Une ligne du journal. Immuable par convention : on ajoute, on ne corrige pas.

    `quantite` est **signée** : positive pour une entrée, négative pour un
    débit ou une expiration. C'est ce qui permet de définir le solde comme une
    simple somme, sans avoir à connaître la sémantique de chaque type — un
    nouveau type de mouvement n'oblige donc pas à retoucher le calcul du solde
    (règle 4 : viser la classe, pas le cas).
    """

    portefeuille = models.ForeignKey(
        PortefeuilleCredits, on_delete=models.CASCADE, related_name="mouvements"
    )
    type = models.CharField(max_length=16, choices=TypeMouvement.choices)
    quantite = models.IntegerField()
    motif = models.CharField(max_length=300)
    #: Référence fonctionnelle : identifiant de job, de commande, de facture.
    #: Sert de clé d'idempotence pour les débits (voir la contrainte).
    reference = models.CharField(max_length=140, blank=True, db_index=True)
    #: Auteur d'un mouvement manuel. Vide pour un mouvement automatique.
    auteur = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(quantite=0), name="mouvement_credit_non_nul"
            ),
            # Un débit ne peut pas être passé deux fois pour la même référence.
            # Sans cette contrainte, une relance de tâche facturerait deux fois
            # la même étude — le défaut du double paiement déjà vécu sur ce
            # projet, sous une autre forme.
            models.UniqueConstraint(
                fields=["portefeuille", "type", "reference"],
                condition=models.Q(type__in=["debit", "remboursement"]),
                name="uniq_mouvement_par_reference",
            ),
        ]
        verbose_name = "mouvement de crédit"
        verbose_name_plural = "mouvements de crédit"

    def __str__(self) -> str:
        return f"{self.quantite:+d} · {self.type} · {self.motif[:40]}"


class ClientFinal(UUIDModel):
    """Entreprise pour laquelle le document est produit, avec sa charte (§9.2).

    La charte appartient au client **du** client : elle change à chaque étude
    pour une même agence. Elle est donc portée ici, réutilisable d'une commande
    à l'autre, et non plus ressaisie dans le formulaire à chaque fois.

    Archivage plutôt que suppression : le cahier des charges demande de pouvoir
    archiver une fiche « sans perte des documents déjà produits ».
    """

    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="clients_finaux"
    )
    raison_sociale = models.CharField(max_length=200)
    secteur = models.CharField(max_length=200, blank=True)
    pays = models.CharField(max_length=120, blank=True)
    region = models.CharField(max_length=120, blank=True)
    ville = models.CharField(max_length=120, blank=True)
    contact_email = models.EmailField(blank=True)

    logo_url = models.URLField(blank=True)
    couleur_principale = models.CharField(max_length=7, blank=True)
    couleur_secondaire = models.CharField(max_length=7, blank=True)
    couleur_fond = models.CharField(max_length=7, blank=True)
    mention_confidentialite = models.CharField(max_length=200, blank=True)

    archive_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["raison_sociale"]
        constraints = [
            models.UniqueConstraint(
                fields=["organisation", "raison_sociale"],
                name="uniq_client_final_par_organisation",
            )
        ]
        verbose_name = "client final"
        verbose_name_plural = "clients finaux"

    def __str__(self) -> str:
        return self.raison_sociale

    @property
    def archive(self) -> bool:
        return self.archive_le is not None


# ── Accès à l'espace client ──────────────────────────────────────────────────
# Ces deux modèles vivent ici et non dans `authentification.py` : le greffon
# mypy de Django ne résout les gestionnaires (`objects`) que pour les modèles
# déclarés dans le module `models` d'une application. La logique, elle, reste
# dans `authentification.py` — un modèle décrit une forme, pas une politique.


class CompteClient(UUIDModel):
    """Lien entre un identifiant de connexion et un contact commercial.

    `User` porte le mot de passe et son hachage — assuré par
    `django.contrib.auth`, jamais réimplémenté. `Customer` porte l'identité
    commerciale et les commandes. Les garder séparés évite de réécrire tout ce
    qui dépend déjà de `Customer`.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="compte_client"
    )
    customer = models.OneToOneField(
        Customer, on_delete=models.CASCADE, related_name="compte"
    )
    actif = models.BooleanField(default=True)
    derniere_connexion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "compte client"
        verbose_name_plural = "comptes client"

    def __str__(self) -> str:
        return self.customer.email


class CategorieFichier(models.TextChoices):
    LOGO = "logo", "Logo"
    DOCUMENT = "document", "Document complémentaire"


def _chemin_piece_jointe(instance: PieceJointe, nom: str) -> str:
    """Range les fichiers par organisation.

    Le nom est repris tel quel — Django l'assainit et ajoute un suffixe en cas
    de collision. Le cloisonnement par répertoire n'est PAS une mesure de
    sécurité : l'accès est contrôlé par l'API, pas par le chemin.
    """
    return f"pieces-jointes/{instance.organisation_id}/{nom}"


class PieceJointe(UUIDModel):
    """Fichier téléversé depuis l'espace client (logo, tableaux, études).

    Les questionnaires demandaient jusqu'ici une **URL**, ce qui supposait que
    le client héberge déjà ses fichiers quelque part. Il les dépose désormais
    directement.

    Le contrôle de format vit dans `fichiers.py` et lit les **octets**, jamais
    l'extension ni l'en-tête déclaré.
    """

    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="pieces_jointes"
    )
    #: Commande à laquelle le fichier se rattache. Vide pour un logo, qui
    #: appartient à l'organisation et sert à toutes ses commandes.
    commande = models.ForeignKey(
        "orders.Order", on_delete=models.CASCADE, null=True, blank=True,
        related_name="pieces_jointes",
    )
    categorie = models.CharField(
        max_length=12, choices=CategorieFichier.choices,
        default=CategorieFichier.DOCUMENT,
    )
    fichier = models.FileField(upload_to=_chemin_piece_jointe)
    nom_original = models.CharField(max_length=200)
    type_mime = models.CharField(max_length=120, blank=True)
    taille_octets = models.PositiveIntegerField(default=0)
    #: Auteur du dépôt. `SET_NULL` : le départ d'un collaborateur ne doit pas
    #: effacer une pièce jointe rattachée à une étude livrée.
    depose_par = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="pieces_deposees",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "pièce jointe"
        verbose_name_plural = "pièces jointes"

    def __str__(self) -> str:
        return f"{self.nom_original} ({self.categorie})"


class TypeDemande(models.TextChoices):
    """Ce qu'un client peut demander depuis son espace."""

    CHANGEMENT_FORMULE = "changement_formule", "Changement de formule"
    CREDITS_ADDITIONNELS = "credits_additionnels", "Achat de crédits additionnels"
    RESILIATION = "resiliation", "Résiliation"


class StatutDemande(models.TextChoices):
    OUVERTE = "ouverte", "Ouverte"
    TRAITEE = "traitee", "Traitée"
    REFUSEE = "refusee", "Refusée"


class DemandeCommerciale(UUIDModel):
    """Demande de changement de formule ou d'achat de crédits (§9.6).

    Le prestataire de paiement n'est pas encore branché : encaisser n'est donc
    pas possible aujourd'hui. Plutôt qu'un bouton qui ne fait rien — ou pire,
    qui laisse croire qu'un paiement est passé —, la demande est **enregistrée**
    et EVKHA la traite. Le client voit sa demande, son statut et sa date.

    Quand Stripe sera branché, ce modèle reste utile : il porte la trace de
    l'intention, ce qu'un webhook de paiement ne dit pas.
    """

    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="demandes"
    )
    #: Auteur de la demande. `SET_NULL` : le départ d'un collaborateur ne doit
    #: pas effacer une demande en cours de traitement.
    demandeur = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="demandes",
    )
    type = models.CharField(max_length=24, choices=TypeDemande.choices)
    statut = models.CharField(
        max_length=12, choices=StatutDemande.choices, default=StatutDemande.OUVERTE
    )
    #: Formule visée, pour un changement. Vide pour un achat de crédits.
    formule_visee = models.ForeignKey(
        Formule, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="demandes",
    )
    #: Nombre de crédits demandés, pour un achat.
    quantite = models.PositiveSmallIntegerField(default=0)
    message = models.TextField(blank=True)
    traitee_le = models.DateTimeField(null=True, blank=True)
    reponse = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # Une seule demande ouverte du même type par organisation : sans
            # cela, un double clic en ouvre deux et EVKHA traite deux fois.
            models.UniqueConstraint(
                fields=["organisation", "type"],
                condition=models.Q(statut="ouverte"),
                name="uniq_demande_ouverte_par_type",
            )
        ]
        verbose_name = "demande commerciale"
        verbose_name_plural = "demandes commerciales"

    def __str__(self) -> str:
        return f"{self.organisation} · {self.type} · {self.statut}"


class JetonAcces(UUIDModel):
    """Jeton de session de l'espace client.

    Seul le **condensat** est conservé : une fuite de la base ne livre aucun
    jeton utilisable, exactement comme pour un mot de passe.
    """

    compte = models.ForeignKey(
        CompteClient, on_delete=models.CASCADE, related_name="jetons"
    )
    condensat = models.CharField(max_length=64, unique=True, db_index=True)
    expire_le = models.DateTimeField()
    revoque_le = models.DateTimeField(null=True, blank=True)
    #: Trace d'usage : permet de repérer un jeton encore actif après un départ.
    derniere_utilisation = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "jeton d'accès"
        verbose_name_plural = "jetons d'accès"

    def __str__(self) -> str:
        return f"Jeton de {self.compte} (expire le {self.expire_le:%d/%m/%Y})"

    @property
    def valide(self) -> bool:
        return self.revoque_le is None and self.expire_le > timezone.now()

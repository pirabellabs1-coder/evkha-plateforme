from __future__ import annotations

from django.db import models

from core.models import UUIDModel


class DeliverableType(models.TextChoices):
    MARKET_STUDY = "market_study", "Etude de marche"
    COMPETITOR_STUDY = "competitor_study", "Etude de concurrence"
    BUSINESS_PLAN = "business_plan", "Business plan"
    BUSINESS_STRATEGY = "business_strategy", "Strategie business"


class DeliveryMode(models.TextChoices):
    LINK_AND_PDF = "link_and_pdf", "Lien de telechargement + PDF"


class Offer(UUIDModel):
    name = models.CharField(max_length=140)
    slug = models.SlugField(unique=True)
    # Vide pour les offres B2B (abonnements, crédits suppl.) dont le type
    # de livrable est choisi via Tally (cf. DELIVERABLE_TYPE hidden field).
    deliverable_type = models.CharField(
        max_length=32,
        choices=DeliverableType.choices,
        blank=True,
        default="",
    )
    credits_per_month = models.PositiveSmallIntegerField(default=0)
    is_subscription = models.BooleanField(default=False)
    is_extra_credit = models.BooleanField(default=False)
    # Nom exact du produit dans Systeme.io (physicalProduct.name dans le payload
    # SALE_NEW du webhook global). Permet de router une vente vers la bonne offre
    # sans passer par un parametre offer_slug dans l'URL de l'automatisation.
    # Renseigner via Django admin ou seed_offers.
    systeme_product_name = models.CharField(max_length=255, blank=True, default="")
    # Moteur de mise en page : WeasyPrint par defaut, Gamma en option.
    #
    # Gamma a ete active partout puis TESTE sur un vrai dossier (juillet 2026).
    # Il borne une carte a ~500 mots, soit `nb_chapitres x 500` de capacite —
    # aucun livrable EVKHA n'y rentre (BP 25 900 mots pour 10 000 de capacite ;
    # EM 32 400 pour 11 500). Mesure : 38 707 mots en entree, 10 121 en sortie,
    # et CINQ verticales sur dix effacees avec le reglage d'origine. Une
    # presentation en cartes et un dossier bancaire de 80 pages ne sont pas le
    # meme objet.
    #
    # WeasyPrint ne tronque rien, implemente deja la charte du Bloc 6 et gere
    # le sommaire pagine que les Consignes exigent.
    #
    # Le flag reste : une offre courte et visuelle pourra reactiver Gamma, au
    # cas par cas et en connaissance de cause. Le controle de fidelite
    # (`delivery/gamma_fidelite.py`) refusera de livrer un rendu ampute.
    gamma_enabled = models.BooleanField(default=False)
    delivery_mode = models.CharField(
        max_length=32,
        choices=DeliveryMode.choices,
        default=DeliveryMode.LINK_AND_PDF,
    )
    retention_days = models.PositiveSmallIntegerField(default=7)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

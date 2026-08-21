from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
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
    #: Prix d'un achat A L'UNITE, en centimes. Zero = l'offre ne se vend pas
    #: seule (abonnements, credits supplementaires, dont le tarif vit sur la
    #: `Formule`).
    #:
    #: Stocke ICI et nulle part ailleurs. Le montant est transmis a Stripe a la
    #: volee, comme pour les credits supplementaires : un tarif preenregistre
    #: chez le prestataire ferait deux verites pour un meme prix (regle 5), et
    #: celle de Stripe gagnerait sans que personne ne l'ait decide. Le champ est
    #: modifiable en administration : changer un prix ne demande pas de
    #: deploiement, exigence deja tenue pour les formules.
    prix_unitaire_cents = models.PositiveIntegerField(default=0)
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


#: Prefixe des fichiers de VITRINE — couverture et extrait. Il est repris
#: tel quel par `evkha.media.PREFIXES_PUBLICS` : ce qui est range dessous est
#: servi SANS signature et EN LIGNE, parce qu'une couverture doit s'afficher
#: dans une balise `<img>` et qu'un extrait sert justement a etre lu avant
#: l'achat.
#:
#: Le nom est defini ici, dans le modele qui y range les fichiers, et importe
#: la-bas. Deux chaines identiques ecrites dans deux modules finiraient par
#: diverger, et le jour ou elles divergent la couverture cesse de s'afficher
#: sans que rien ne le dise (regle 5).
PREFIXE_VITRINE = "boutique-vitrine"


def _chemin_produit(instance: ProduitBoutique, nom: str) -> str:
    """Range les fichiers PAYANTS de la boutique par produit.

    Le cloisonnement par repertoire n'est PAS une mesure de securite : l'acces
    est controle par la signature du lien, jamais par le chemin. Il sert a
    retrouver les fichiers d'un produit quand on en retire un.
    """
    return f"boutique/{instance.slug}/{nom}"


def _chemin_vitrine(instance: ProduitBoutique, nom: str) -> str:
    """Range les fichiers de VITRINE, ceux qui servent a vendre.

    Ils vivent sous un prefixe distinct du document paye, et c'est tout
    l'interet : le prefixe porte l'intention. Rendre public « tout ce qui est
    sous `boutique/` » aurait ouvert l'etude elle-meme, qui y est rangee.
    """
    return f"{PREFIXE_VITRINE}/{instance.slug}/{nom}"


class ProduitBoutique(UUIDModel):
    """Une etude DEJA REDIGEE, vendue telle quelle depuis la boutique.

    ## Pourquoi un modele distinct de `Offer`

    `Offer` decrit ce que la plateforme PRODUIT : un type de livrable, un plan
    de chapitres, un questionnaire, un cout de production. Un produit de
    boutique ne produit rien — c'est un fichier ecrit il y a des mois, remis
    tel quel apres paiement.

    Les confondre reviendrait a donner un `deliverable_type` a un fichier, donc
    a le rendre eligible a une generation qui n'a pas lieu d'etre, et a faire
    porter au meme modele deux cycles de vie qui n'ont rien de commun.

    ## Ce que la cliente remplit elle-meme

    Tout. Titre, description, prix, fichier, image, theme : le catalogue
    s'elargit chaque mois, et rien de ce qui change chaque mois ne doit passer
    par un developpeur.
    """

    titre = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    #: Presentation longue affichee sur la fiche produit.
    description = models.TextField(blank=True)
    #: Sommaire du document, une ligne par entree. Affiche tel quel.
    sommaire = models.TextField(blank=True)
    #: Regroupe les produits proches sur la fiche. Un simple libelle : une
    #: table de themes serait un ecran d'administration de plus pour une
    #: information qui tient en un mot.
    theme = models.CharField(max_length=80, blank=True)

    prix_cents = models.PositiveIntegerField(default=0)
    devise = models.CharField(max_length=3, default="EUR")

    #: Le document vendu. Sans lui, le produit n'est pas publiable — le
    #: controle vit dans `est_publiable`, pas dans une contrainte de base :
    #: la cliente cree souvent la fiche avant d'avoir le fichier final.
    fichier = models.FileField(upload_to=_chemin_produit, blank=True)
    #: Version editable, facultative.
    fichier_editable = models.FileField(upload_to=_chemin_produit, blank=True)
    #: Les quelques pages consultables avant achat. VITRINE : servi sans
    #: signature, parce qu'un extrait qu'il faut demander n'est plus un extrait.
    extrait = models.FileField(upload_to=_chemin_vitrine, blank=True)
    #: La couverture. VITRINE elle aussi : une image signee expirerait, et une
    #: image servie en piece jointe ne s'affiche pas dans une balise `<img>`.
    image = models.ImageField(upload_to=_chemin_vitrine, blank=True)

    nombre_de_pages = models.PositiveSmallIntegerField(default=0)
    #: « Mise a jour tous les 6 mois » est un argument de vente : la date est
    #: donc affichee, et tenue par la cliente.
    mise_a_jour_le = models.DateField(null=True, blank=True)

    #: Retire de la boutique sans rien effacer. Supprimer un produit
    #: detruirait l'historique des ventes ET l'acces de ceux qui l'ont paye :
    #: ce qu'ils ont achete doit rester a eux.
    en_ligne = models.BooleanField(default=False)
    rang = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["rang", "titre"]
        verbose_name = "produit de boutique"
        verbose_name_plural = "produits de boutique"

    def __str__(self) -> str:
        return self.titre

    @property
    def est_publiable(self) -> bool:
        """Vendable seulement s'il a un prix ET un fichier a remettre.

        Un produit a zero euro ouvrirait un paiement de zero euro, accepte par
        le prestataire, qui donnerait le fichier sans contrepartie. Un produit
        sans fichier encaisserait sans rien remettre. Les deux sont des
        defauts silencieux : ils ne se voient qu'au premier acheteur.
        """
        return bool(self.prix_cents > 0 and self.fichier)

    @property
    def visible(self) -> bool:
        return self.en_ligne and self.est_publiable

    @property
    def note_moyenne(self) -> float:
        """Moyenne des avis PUBLIES, a une decimale. `0.0` s'il n'y en a pas.

        Zero et non `None` : la page teste `nombre_d_avis` pour decider
        d'afficher quoi que ce soit, et une moyenne absente ne doit pas
        obliger chaque appelant a se demander quoi en faire.
        """
        notes = [a.note for a in self.avis.all() if a.publie]
        return round(sum(notes) / len(notes), 1) if notes else 0.0

    @property
    def nombre_d_avis(self) -> int:
        return sum(1 for a in self.avis.all() if a.publie)


class AvisProduit(UUIDModel):
    """L'avis d'une lectrice sur une etude de la boutique.

    Ces avis sont SAISIS PAR LA CLIENTE depuis l'administration, et non
    deposes librement par les acheteurs. C'est un choix, et il tient a ce
    qu'un avis publie engage : ouvrir le depot en ligne demanderait une
    moderation, un controle d'achat reel et un recours en cas d'abus — trois
    chantiers pour une boutique qui compte neuf etudes.

    `publie` porte donc la moderation : un avis saisi n'apparait qu'une fois
    coche, ce qui laisse le temps de le relire.
    """

    produit = models.ForeignKey(
        ProduitBoutique, on_delete=models.CASCADE, related_name="avis"
    )
    auteur = models.CharField(max_length=120)
    #: Metier ou ville — « Restauratrice, Lyon ». Facultatif : un avis sans
    #: qualite reste un avis.
    qualite = models.CharField(max_length=120, blank=True)
    #: De 1 a 5. Le domaine est verrouille ici : une note libre finirait par
    #: valoir 7 sur une echelle de 5, et la moyenne n'aurait plus de sens.
    note = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    texte = models.TextField(blank=True)
    publie = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "avis"
        verbose_name_plural = "avis"

    def __str__(self) -> str:
        return f"{self.auteur} — {self.note}/5"


class AchatProduit(UUIDModel):
    """Un produit de boutique paye par une organisation.

    Porte l'acces : tant que cette ligne existe, l'acheteur peut retelecharger
    son fichier. Elle survit au retrait du produit de la boutique.
    """

    organisation = models.ForeignKey(
        "organisations.Organisation",
        on_delete=models.CASCADE,
        related_name="achats_boutique",
    )
    #: `PROTECT` : un produit vendu ne se supprime pas. Le retirer de la
    #: boutique se fait par `en_ligne`, ce qui preserve l'acces de l'acheteur.
    produit = models.ForeignKey(
        ProduitBoutique, on_delete=models.PROTECT, related_name="achats"
    )
    #: Reference de la session de paiement. UNIQUE : c'est le verrou qui
    #: empeche le webhook et la page de retour de compter deux fois le meme
    #: achat, chacun ignorant que l'autre est passe.
    reference_paiement = models.CharField(max_length=200, unique=True)
    montant_cents = models.PositiveIntegerField(default=0)
    devise = models.CharField(max_length=3, default="EUR")
    #: Adresse a laquelle le lien a ete envoye. Conservee telle quelle : elle
    #: peut differer de celle du compte, le prestataire laissant la modifier.
    email = models.EmailField(blank=True)
    telecharge_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "achat de boutique"
        verbose_name_plural = "achats de boutique"

    def __str__(self) -> str:
        return f"{self.produit} — {self.organisation}"

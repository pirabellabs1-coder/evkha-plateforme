"""Routes ouvertes de l'espace partenaires (page publique).

Séparées de `urls.py` pour la même raison que les vues : ce qui est public
doit se voir au premier coup d'œil dans l'arborescence, pas se découvrir en
lisant les décorateurs.
"""
from __future__ import annotations

from django.urls import path

from audience import vues_publiques as vues_audience

from . import pages_boutique, vues_boutique, vues_formations
from . import vues_publiques as vues

app_name = "public"

urlpatterns = [
    path("formules/", vues.formules_publiques, name="formules"),
    # Les ressources gratuites contre une adresse, et la lettre (24/11/2026).
    path("ressources/", vues_audience.ressource, name="ressources"),
    path("lettre/", vues_audience.lettre, name="lettre"),
    # La boutique : catalogue des etudes deja redigees, vendues telles
    # quelles. Aucun compte n'est requis pour la consulter.
    path("boutique/", vues_boutique.catalogue, name="boutique"),
    path("boutique/acheter/", vues_boutique.acheter, name="boutique-acheter"),
    path("boutique/retour/", vues_boutique.retour, name="boutique-retour"),
    # Le plan du site des fiches en vente, servi par nginx a
    # `/sitemap-boutique.xml`. Le point du nom le tient hors de portee de la
    # route d'une fiche : un slug n'en porte pas.
    path("boutique/plan.xml", pages_boutique.plan, name="boutique-plan"),
    path("boutique/<slug:slug>/", vues_boutique.fiche, name="boutique-fiche"),
    # La fiche en HTML complet, pour qui n'execute pas de JavaScript : nginx
    # lui confie `/boutique/<slug>` (voir `pages_boutique`).
    path("boutique/<slug:slug>/page/", pages_boutique.page, name="boutique-page"),
    # L'apercu : les premieres pages du document vendu, decoupees a la demande.
    # Public et sans signature — c'est un support de vente, comme la couverture.
    path(
        "boutique/<slug:slug>/apercu/",
        vues_boutique.apercu,
        name="boutique-apercu",
    ),
    # Achat a l'unite : le catalogue avec ses tarifs, l'ouverture du paiement,
    # et le retour de Stripe. Trois routes PUBLIQUES par necessite — au moment
    # ou la personne clique, elle n'a ni compte ni jeton.
    path("livrables/", vues.livrables_publics, name="livrables"),
    # Les formations en ligne : fiche, prix et programme. Jamais le contenu
    # des leçons, qui est ce que l'acheteur paie.
    path("formations/", vues_formations.catalogue, name="formations"),
    # L'achat d'une formation par Stripe, et le retour du paiement. PUBLIQUES
    # pour la raison des deux routes « acheter » ci-dessous : au moment du
    # clic, la personne n'a ni compte ni jeton.
    path("formations/acheter/", vues_formations.acheter, name="formations-acheter"),
    path("formations/retour/", vues_formations.retour, name="formations-retour"),
    path("acheter/", vues.acheter, name="acheter"),
    path("acheter/retour/", vues.retour_de_paiement, name="acheter-retour"),
    path("inscription/", vues.inscrire, name="inscription"),
    path("reglages/", vues.reglages_publics, name="reglages"),
    # Un seul point d'entree pour la connexion ET l'inscription par Google : au
    # moment du clic, personne ne sait encore si le compte existe.
    path("google/", vues.google_session, name="google"),
    # Definir son mot de passe depuis un lien recu par courriel. Sert aux deux
    # parcours — activer une invitation, reinitialiser un oubli — parce que
    # c'est le meme geste.
    path(
        "mot-de-passe/oublie/",
        vues.mot_de_passe_oublie,
        name="mot-de-passe-oublie",
    ),
    path(
        "mot-de-passe/definir/",
        vues.definir_mot_de_passe,
        name="mot-de-passe-definir",
    ),
    # Confirmer une nouvelle adresse de connexion. PUBLIQUE, et il le faut : la
    # personne clique depuis sa boîte, souvent sur un autre appareil que celui
    # où sa session est ouverte. Exiger un jeton de session ici rendrait le lien
    # inutilisable précisément pour ceux qui en ont le plus besoin.
    path(
        "adresse/confirmer/",
        vues.confirmer_la_nouvelle_adresse,
        name="adresse-confirmer",
    ),
]

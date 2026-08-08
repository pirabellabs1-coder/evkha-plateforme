"""Routes ouvertes de l'espace partenaires (page publique).

Séparées de `urls.py` pour la même raison que les vues : ce qui est public
doit se voir au premier coup d'œil dans l'arborescence, pas se découvrir en
lisant les décorateurs.
"""
from __future__ import annotations

from django.urls import path

from . import vues_publiques as vues

app_name = "public"

urlpatterns = [
    path("formules/", vues.formules_publiques, name="formules"),
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

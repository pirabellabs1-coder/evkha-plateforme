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
]

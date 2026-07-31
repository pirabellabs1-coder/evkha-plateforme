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
]

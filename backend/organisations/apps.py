from __future__ import annotations

from django.apps import AppConfig


class OrganisationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "organisations"
    verbose_name = "Organisations, crédits et clients finaux"

    def ready(self) -> None:
        # `checks` enregistre les verifications Django.
        #
        # `purge` enregistre le `post_delete` qui efface le fichier d'une piece
        # jointe. Sans cet import, le recepteur n'existe pas et les quatre
        # chemins de suppression laissent le fichier sur le volume — c'etait
        # l'etat d'avant. Voir `organisations/purge.py`.
        from . import (  # noqa: F401
            checks,
            purge,
        )

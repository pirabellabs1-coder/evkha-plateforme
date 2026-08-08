"""Crée le compte d'administration Django au démarrage, s'il n'existe pas.

Sans cette commande, personne ne peut entrer dans `/admin/`. `createsuperuser`
est interactif, et l'API de Coolify n'expose aucune exécution de commande dans
le conteneur : les trois routes `execute`, `command` et `exec` répondent 404.
Constaté le 07/08/2026, en cherchant à relier les tarifs Stripe aux formules —
il fallait l'administration pour cela, et on ne pouvait pas y entrer.

Le mot de passe vient de l'environnement, jamais du code. Il n'est **pas**
réappliqué à chaque démarrage : quelqu'un qui change son mot de passe depuis
l'interface le verrait sinon revenir à sa valeur d'origine au déploiement
suivant, sans rien comprendre. Pour le réinitialiser volontairement, il existe
`EVKHA_ADMIN_REINITIALISER=true` — un geste explicite, à retirer ensuite.

    EVKHA_ADMIN_EMAIL=...        adresse, qui sert aussi d'identifiant
    EVKHA_ADMIN_PASSWORD=...     mot de passe initial
    EVKHA_ADMIN_REINITIALISER=   « true » pour forcer le mot de passe

Sans ces variables, la commande ne fait RIEN et le dit. Elle peut donc rester
dans la chaîne de démarrage en permanence, y compris là où aucun compte
d'administration n'est voulu.
"""
from __future__ import annotations

import os
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


def _vrai(valeur: str) -> bool:
    return valeur.strip().lower() in {"1", "true", "oui", "yes"}


class Command(BaseCommand):
    help = "Cree le superutilisateur Django depuis l'environnement, s'il manque."

    def handle(self, *args: Any, **options: Any) -> None:
        adresse = os.environ.get("EVKHA_ADMIN_EMAIL", "").strip()
        secret = os.environ.get("EVKHA_ADMIN_PASSWORD", "")
        reinitialiser = _vrai(os.environ.get("EVKHA_ADMIN_REINITIALISER", ""))

        if not adresse or not secret:
            # Pas une erreur : un environnement sans compte d'administration
            # est un choix legitime. Mais on le DIT, sinon l'absence de compte
            # se decouvre devant un formulaire de connexion qui refuse.
            self.stdout.write(
                "assurer_admin : EVKHA_ADMIN_EMAIL ou EVKHA_ADMIN_PASSWORD "
                "absente — aucun compte d'administration cree."
            )
            return

        Utilisateur = get_user_model()
        compte = Utilisateur.objects.filter(username__iexact=adresse).first()

        if compte is None:
            Utilisateur.objects.create_superuser(
                username=adresse, email=adresse, password=secret
            )
            self.stdout.write(self.style.SUCCESS(
                f"assurer_admin : compte d'administration cree pour {adresse}."
            ))
            return

        # Le compte existe. On garantit ses DROITS — un superutilisateur
        # retrograde par erreur se retrouverait dehors sans recours — mais on
        # ne touche pas au mot de passe sans qu'on le demande.
        modifie = []
        if not compte.is_staff:
            compte.is_staff = True
            modifie.append("is_staff")
        if not compte.is_superuser:
            compte.is_superuser = True
            modifie.append("is_superuser")
        if not compte.is_active:
            compte.is_active = True
            modifie.append("is_active")

        if reinitialiser:
            compte.set_password(secret)
            modifie.append("mot de passe")

        if modifie:
            compte.save()
            self.stdout.write(self.style.SUCCESS(
                f"assurer_admin : {adresse} mis a jour ({', '.join(modifie)})."
            ))
        else:
            self.stdout.write(
                f"assurer_admin : {adresse} existe deja, rien a faire."
            )

        if reinitialiser:
            self.stdout.write(self.style.WARNING(
                "assurer_admin : EVKHA_ADMIN_REINITIALISER est actif. Retirez "
                "cette variable, sinon le mot de passe sera reecrit a chaque "
                "demarrage et tout changement fait depuis l'interface sera perdu."
            ))

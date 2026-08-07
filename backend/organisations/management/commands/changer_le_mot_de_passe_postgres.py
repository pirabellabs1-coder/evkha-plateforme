"""Change le mot de passe de l'utilisateur PostgreSQL, dans la base elle-même.

Le mot de passe de production a fuité en début de projet, dans une lecture de
variables d'environnement mal filtrée. Il n'a jamais été changé depuis.

**Le piège qui rend cette commande nécessaire.** Modifier `POSTGRES_PASSWORD`
dans Coolify ne change RIEN : l'image PostgreSQL ne lit cette variable qu'à la
première initialisation d'un volume vide. Le volume de production existe depuis
des mois — l'utilisateur garderait son mot de passe, et l'application ne
pourrait simplement plus se connecter. Panne totale, sans rien avoir sécurisé.

Le vrai changement passe par `ALTER USER`, exécuté depuis une connexion déjà
authentifiée. C'est ce que fait cette commande, au démarrage du conteneur —
l'API de Coolify n'expose aucune exécution de commande, et il n'existe pas
d'autre chemin.

La séquence, dans cet ordre et pas un autre :

1. poser `EVKHA_NOUVEAU_MOT_DE_PASSE_PG`, déployer : la base accepte désormais
   les DEUX mots de passe ? Non — elle n'accepte plus que le nouveau, et
   l'application tourne encore avec l'ancienne connexion, déjà ouverte ;
2. reporter la même valeur dans `POSTGRES_PASSWORD` **et** dans
   `DATABASE_URL`, puis redéployer : les nouvelles connexions passent ;
3. retirer `EVKHA_NOUVEAU_MOT_DE_PASSE_PG`.

Entre 1 et 2, un redémarrage du conteneur serait fatal : il rouvrirait ses
connexions avec l'ancien mot de passe, qui ne vaut plus rien. C'est pourquoi
l'étape 2 doit suivre l'étape 1 immédiatement.
"""
from __future__ import annotations

import os
from typing import Any

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Change le mot de passe PostgreSQL depuis l'environnement. Sans variable, ne fait rien."

    def handle(self, *args: Any, **options: Any) -> None:
        nouveau = os.environ.get("EVKHA_NOUVEAU_MOT_DE_PASSE_PG", "")
        if not nouveau.strip():
            return

        # Assez long pour ne pas se casser au dictionnaire. Refuser ici plutot
        # qu'accepter : un mot de passe faible pose sur une base de production
        # ne se remarque jamais avant l'incident.
        if len(nouveau) < 24:
            self.stdout.write(self.style.ERROR(
                f"changer_le_mot_de_passe_postgres : refuse, {len(nouveau)} "
                "caracteres. Vingt-quatre au minimum."
            ))
            return

        # Le type de base AVANT l'utilisateur, et pas l'inverse : sur SQLite,
        # `USER` est vide, et se plaindre d'un utilisateur manquant donnerait un
        # motif faux la ou la vraie raison est qu'`ALTER USER` n'existe pas.
        # Un motif faux envoie chercher au mauvais endroit (regle 2).
        if connection.vendor != "postgresql":
            self.stdout.write(
                "changer_le_mot_de_passe_postgres : base non PostgreSQL, ignore."
            )
            return

        utilisateur = connection.settings_dict.get("USER") or ""
        if not utilisateur:
            self.stdout.write(self.style.ERROR(
                "changer_le_mot_de_passe_postgres : aucun utilisateur dans la "
                "configuration de base. Rien n'a ete change."
            ))
            return

        with connection.cursor() as curseur:
            # L'identifiant est cite par le pilote, la valeur passee en
            # PARAMETRE serait refusee par PostgreSQL sur un ALTER USER : on
            # echappe donc le litteral nous-memes, avec la fonction dediee du
            # pilote plutot qu'a la main.
            from psycopg import sql  # noqa: PLC0415

            curseur.execute(
                sql.SQL("ALTER USER {} WITH PASSWORD {}").format(
                    sql.Identifier(utilisateur), sql.Literal(nouveau)
                )
            )

        self.stdout.write(self.style.SUCCESS(
            f"changer_le_mot_de_passe_postgres : mot de passe de « {utilisateur} » "
            f"change ({len(nouveau)} caracteres)."
        ))
        self.stdout.write(self.style.WARNING(
            "ETAPE SUIVANTE, SANS ATTENDRE : reporter la meme valeur dans "
            "POSTGRES_PASSWORD et dans DATABASE_URL, puis redeployer. Un "
            "redemarrage avant cela rouvrirait les connexions avec l'ancien "
            "mot de passe, qui ne vaut plus rien."
        ))

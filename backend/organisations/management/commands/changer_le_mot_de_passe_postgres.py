"""Change le mot de passe de l'utilisateur PostgreSQL, dans la base elle-même.

Le mot de passe de production a fuité en début de projet, dans une lecture de
variables d'environnement mal filtrée. Il n'a jamais été changé depuis.

**Premier piège : `POSTGRES_PASSWORD` ne fait rien.** L'image PostgreSQL ne lit
cette variable qu'à la première initialisation d'un volume vide. Le volume de
production existe depuis des mois — le modifier laisserait le mot de passe fuité
valide ET empêcherait l'application de se connecter. Le vrai changement passe
par `ALTER USER`.

**Second piège, plus vicieux, trouvé avant de déployer.** Une première version
utilisait la connexion Django. Elle changeait le mot de passe… puis `migrate`
démarrait DANS UN AUTRE PROCESSUS, ouvrait une nouvelle connexion avec l'ancien
mot de passe — qui ne valait plus rien — et le conteneur s'arrêtait. Coolify le
relançait, il échouait encore : plateforme à terre jusqu'à correction manuelle.
Chaque commande Django ouvre sa propre connexion ; celle-ci sciait la branche
sur laquelle les suivantes étaient assises.

D'où la connexion EXPLICITE, montée à la main avec l'ancien mot de passe. Elle
ne dépend pas de `DATABASE_URL`, qui peut donc déjà porter le NOUVEAU : tout ce
qui suit dans la chaîne de démarrage fonctionne du premier coup, sans aucune
fenêtre de panne.

La séquence tient en un seul déploiement :

1. `EVKHA_ANCIEN_MOT_DE_PASSE_PG` ← le mot de passe actuel ;
2. `EVKHA_NOUVEAU_MOT_DE_PASSE_PG` ← le nouveau ;
3. `POSTGRES_PASSWORD` et `DATABASE_URL` ← le nouveau, dans le même geste ;
4. déployer ;
5. retirer les deux variables temporaires.

Elle est **idempotente** : si le nouveau mot de passe fonctionne déjà, elle ne
fait rien et le dit. Un redéploiement ultérieur est donc sans danger, même en
laissant les variables en place.
"""
from __future__ import annotations

import os
from typing import Any

from django.core.management.base import BaseCommand
from django.db import connection


def _parametres_sans_mot_de_passe() -> dict[str, Any]:
    """Hôte, port, base et utilisateur, tels que Django les connaît.

    Tout sauf le mot de passe : c'est lui qu'on fait varier. Les relire ici
    plutôt que de les redemander en variables d'environnement évite qu'ils
    divergent de la configuration réelle — on se connecterait alors à une autre
    base que celle que l'application utilise (règle 5).
    """
    reglages = connection.settings_dict
    return {
        "host": reglages.get("HOST") or "localhost",
        "port": str(reglages.get("PORT") or "5432"),
        "dbname": reglages.get("NAME") or "",
        "user": reglages.get("USER") or "",
    }


class Command(BaseCommand):
    help = "Change le mot de passe PostgreSQL depuis l'environnement. Sans variable, ne fait rien."

    def handle(self, *args: Any, **options: Any) -> None:
        nouveau = os.environ.get("EVKHA_NOUVEAU_MOT_DE_PASSE_PG", "")
        ancien = os.environ.get("EVKHA_ANCIEN_MOT_DE_PASSE_PG", "")
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

        # Le type de base AVANT tout le reste : sur SQLite, `ALTER USER`
        # n'existe pas, et se plaindre d'autre chose donnerait un motif faux
        # qui envoie chercher au mauvais endroit (regle 2).
        if connection.vendor != "postgresql":
            self.stdout.write(
                "changer_le_mot_de_passe_postgres : base non PostgreSQL, ignore."
            )
            return

        parametres = _parametres_sans_mot_de_passe()
        if not parametres["user"] or not parametres["dbname"]:
            self.stdout.write(self.style.ERROR(
                "changer_le_mot_de_passe_postgres : configuration de base "
                "incomplete. Rien n'a ete change."
            ))
            return

        import psycopg  # noqa: PLC0415
        from psycopg import sql  # noqa: PLC0415

        # Le nouveau mot de passe fonctionne-t-il DEJA ? Si oui, le changement a
        # eu lieu a un demarrage precedent : on ne le rejoue pas. C'est ce qui
        # rend un redeploiement sans danger, variables laissees en place.
        try:
            psycopg.connect(**parametres, password=nouveau, connect_timeout=10).close()
        except psycopg.OperationalError:
            pass
        else:
            self.stdout.write(
                "changer_le_mot_de_passe_postgres : le nouveau mot de passe est "
                "deja en place, rien a faire."
            )
            return

        if not ancien:
            self.stdout.write(self.style.ERROR(
                "changer_le_mot_de_passe_postgres : EVKHA_ANCIEN_MOT_DE_PASSE_PG "
                "manquante, et le nouveau ne fonctionne pas encore. Rien n'a ete "
                "change."
            ))
            return

        # Connexion EXPLICITE avec l'ancien mot de passe : elle ne depend pas de
        # DATABASE_URL, qui porte deja le nouveau. C'est ce qui permet aux
        # migrations et a gunicorn de fonctionner du premier coup.
        try:
            lien = psycopg.connect(**parametres, password=ancien, connect_timeout=10)
        except psycopg.OperationalError as erreur:
            self.stdout.write(self.style.ERROR(
                "changer_le_mot_de_passe_postgres : impossible de se connecter "
                f"avec l'ancien mot de passe. Rien n'a ete change. ({erreur})"
            ))
            return

        with lien, lien.cursor() as curseur:
            # L'identifiant est cite par le pilote, et la valeur echappee par
            # `Literal` : PostgreSQL refuse un parametre lie sur ALTER USER, et
            # concatener a la main ouvrirait une injection sur la commande la
            # plus sensible du depot.
            curseur.execute(
                sql.SQL("ALTER USER {} WITH PASSWORD {}").format(
                    sql.Identifier(parametres["user"]), sql.Literal(nouveau)
                )
            )
            lien.commit()

        self.stdout.write(self.style.SUCCESS(
            f"changer_le_mot_de_passe_postgres : mot de passe de "
            f"« {parametres['user']} » change ({len(nouveau)} caracteres)."
        ))
        self.stdout.write(self.style.WARNING(
            "Retirer maintenant EVKHA_ANCIEN_MOT_DE_PASSE_PG et "
            "EVKHA_NOUVEAU_MOT_DE_PASSE_PG : elles ne servent plus, et elles "
            "portent des secrets."
        ))

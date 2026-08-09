"""Contrôles de configuration de l'espace d'administration.

Le middleware refuse déjà le contournement quand `DEBUG` est faux — la
protection tient donc quoi qu'il arrive. Mais elle tient en SILENCE : le
drapeau resterait posé sur le serveur, et la personne qui l'a mis croirait
l'administration ouverte alors qu'elle ne l'est plus, ou l'inverse.

Ce contrôle le dit au démarrage, à l'endroit où on le lit (règle 1 : ne pas se
taire). Il complète le middleware, il ne le remplace pas : un contrôle qu'on
peut ignorer d'un `--skip-checks` ne protège rien tout seul.
"""
from __future__ import annotations

from django.conf import settings
from django.core.checks import Error, Warning, register


@register()
def controler_garde_administration(
    app_configs: object, **kwargs: object
) -> list[Error | Warning]:
    """Le tableau de bord est-il réellement protégé ?

    Deux configurations dangereuses, et la seconde est celle qui a été trouvée
    en ligne le 31/07/2026 : le contournement de développement posé sur le
    serveur public, à côté d'un jeton parfaitement valide.
    """
    problemes: list[Error | Warning] = []
    production = not settings.DEBUG
    contournement = bool(getattr(settings, "EVKHA_DASHBOARD_AUTH_DISABLED", False))
    jeton = str(getattr(settings, "EVKHA_DASHBOARD_TOKEN", "") or "")

    if contournement and production:
        problemes.append(Error(
            "EVKHA_DASHBOARD_AUTH_DISABLED est pose alors que DEBUG=False. "
            "Le contournement est IGNORE (le middleware ne l'honore qu'en "
            "developpement), mais sa presence laisse croire que "
            "l'administration est ouverte — ou qu'elle l'est restee.",
            hint="Retirer EVKHA_DASHBOARD_AUTH_DISABLED des variables du serveur.",
            id="evkha.D001",
        ))

    if not jeton and not contournement:
        # Sans jeton, le middleware refuse TOUT : l'administration devient
        # inaccessible. C'est le bon comportement, mais il faut le dire.
        problemes.append(Error(
            "EVKHA_DASHBOARD_TOKEN n'est pas configure : l'administration "
            "refuse toutes les requetes.",
            hint="Definir EVKHA_DASHBOARD_TOKEN (openssl rand -hex 32).",
            id="evkha.D002",
        ))

    if jeton and len(jeton) < 32:
        problemes.append(Warning(
            f"EVKHA_DASHBOARD_TOKEN ne fait que {len(jeton)} signes. Ce jeton "
            "ouvre l'ensemble des donnees clients.",
            hint="Au moins 32 signes (openssl rand -hex 32).",
            id="evkha.D003",
        ))

    problemes.extend(_controler_rotation(jeton))
    return problemes


def _controler_rotation(jeton: str) -> list[Error | Warning]:
    """La fenetre de rotation est-elle ouverte, et l'est-elle pour une raison ?

    `EVKHA_DASHBOARD_TOKEN_PRECEDENT` existe pour qu'un secret PUISSE etre
    change. Avec un jeton unique, tourner la cle casse tous les appelants a la
    seconde du deploiement — donc on repousse, et le meme secret reste en place
    indefiniment. C'est la rotation qui protege un jeton statique, pas sa
    longueur.

    Mais une fenetre qu'on oublie de fermer est pire que pas de rotation du
    tout : elle laisse vivre exactement le secret qu'on voulait retirer, en
    donnant l'impression qu'il l'a ete. On le rappelle donc a chaque demarrage,
    tant qu'elle est ouverte.
    """
    precedent = str(
        getattr(settings, "EVKHA_DASHBOARD_TOKEN_PRECEDENT", "") or ""
    ).strip()
    if not precedent:
        return []

    problemes: list[Error | Warning] = [Warning(
        "EVKHA_DASHBOARD_TOKEN_PRECEDENT est pose : DEUX jetons ouvrent "
        "actuellement l'administration. C'est voulu le temps d'une rotation, "
        "et seulement ce temps-la.",
        hint=(
            "Une fois tous les appelants passes au nouveau jeton, VIDER "
            "EVKHA_DASHBOARD_TOKEN_PRECEDENT."
        ),
        id="evkha.D004",
    )]

    if precedent == jeton:
        problemes.append(Error(
            "EVKHA_DASHBOARD_TOKEN_PRECEDENT porte la MEME valeur que "
            "EVKHA_DASHBOARD_TOKEN : la rotation n'a rien tourne, et la "
            "configuration donne a croire le contraire.",
            hint="Poser l'ANCIENNE valeur dans le precedent, la nouvelle au-dessus.",
            id="evkha.D005",
        ))

    return problemes

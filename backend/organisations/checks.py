"""Contrôles de configuration des protections de l'espace client.

Ces contrôles existent parce qu'une protection peut être **écrite, testée,
verte — et sans effet**. C'est ce qui s'est produit ici.

Les plafonds de tentatives de `limitation.py` s'appuient sur
`django.core.cache`. Or aucun backend de cache n'était déclaré : Django
retombait sur `LocMemCache`, un dictionnaire local au processus, pendant que la
production tourne `gunicorn --workers 2`. Chaque worker tenait son propre
compteur. Le plafond annoncé « 10 essais par quart d'heure » en autorisait donc
20, et repartait de zéro à chaque redéploiement.

Aucun test ne pouvait le voir : la suite tourne dans un seul processus, où
`LocMemCache` se comporte exactement comme un cache partagé (règle 7 — le vert
des tests ne prouve rien sur ce qui est livré).

Un réglage manquant qui dégrade une protection en silence est la forme la plus
dangereuse du défaut de la règle 1. Le contrôle ci-dessous le rend bruyant.
"""
from __future__ import annotations

from django.conf import settings
from django.core.checks import Error, Warning, register

#: Backends qui ne survivent pas au multi-processus.
#:
#: On vise la CLASSE et non l'exemple (règle 4) : le défaut n'est pas
#: « LocMemCache est configuré », c'est « le cache n'est pas partagé entre les
#: processus qui servent les requêtes ». `DummyCache` ne garde rien du tout et
#: relève exactement du même problème — un plafond posé dessus ne compte jamais.
BACKENDS_NON_PARTAGES = (
    "django.core.cache.backends.locmem.LocMemCache",
    "django.core.cache.backends.dummy.DummyCache",
)


@register()
def controler_cache_partage(
    app_configs: object, **kwargs: object
) -> list[Error | Warning]:
    """Le cache tient-il réellement les compteurs qu'on lui confie ?

    Ce contrôle ne regarde pas si Redis répond — un serveur injoignable est un
    incident d'exploitation, visible autrement. Il regarde la seule chose
    qu'une relecture de code ne montre pas : le backend effectivement en
    vigueur au démarrage.
    """
    problemes: list[Error | Warning] = []
    if settings.DEBUG:
        # En développement, un seul processus sert les requêtes : le cache
        # local se comporte comme un cache partagé. Crier ici entraînerait à
        # ignorer le message, et donc à l'ignorer aussi en production.
        return problemes

    caches = getattr(settings, "CACHES", {}) or {}
    backend = str(caches.get("default", {}).get("BACKEND", ""))

    if backend in BACKENDS_NON_PARTAGES:
        problemes.append(Error(
            f"Le cache par defaut est {backend!r}, qui n'est PAS partage entre "
            "les processus. Les plafonds de tentatives (connexion, inscription) "
            "comptent alors separement dans chaque worker gunicorn : le plafond "
            "reel vaut le plafond annonce multiplie par le nombre de workers, "
            "et il repart de zero a chaque redeploiement.",
            hint=(
                "Definir EVKHA_CACHE_URL sur une base Redis DISTINCTE de "
                "CELERY_BROKER_URL, par exemple redis://redis:6379/1."
            ),
            id="evkha.C001",
        ))

    return problemes


@register()
def controler_secret_django(
    app_configs: object, **kwargs: object
) -> list[Error | Warning]:
    """La clé secrète est-elle celle du dépôt ?

    `SECRET_KEY` a une valeur de repli inscrite en clair dans `settings.py` —
    et donc publique. Elle signe les sessions de l'administration Django : qui
    la connaît forge une session d'administrateur.

    Rien ne refusait de démarrer sans la variable. Le dépôt savait pourtant
    déjà faire l'inverse pour le jeton du tableau de bord (`evkha.D002`) : le
    défaut avait été corrigé pour UN secret, pas pour sa classe (règle 4).
    """
    problemes: list[Error | Warning] = []
    if settings.DEBUG:
        return problemes

    # Une cle VIDE ne peut pas arriver jusqu'ici : Django leve
    # `ImproperlyConfigured` des la premiere lecture. Le seul cas silencieux —
    # et donc le seul a controler — est le repli qui a l'air d'une vraie cle.
    secret = str(getattr(settings, "SECRET_KEY", "") or "")
    if secret == REPLI_CONNU:
        problemes.append(Error(
            "DJANGO_SECRET_KEY n'est pas defini : la cle de repli inscrite "
            "dans settings.py est utilisee. Elle est publique — elle figure "
            "dans le depot — et elle signe les sessions d'administration.",
            hint="Definir DJANGO_SECRET_KEY (openssl rand -hex 32).",
            id="evkha.C002",
        ))
    elif len(secret) < 32:
        problemes.append(Warning(
            f"DJANGO_SECRET_KEY ne fait que {len(secret)} signes.",
            hint="Au moins 32 signes (openssl rand -hex 32).",
            id="evkha.C003",
        ))

    return problemes


@register()
def controler_adresse_du_front(
    app_configs: object, **kwargs: object
) -> list[Error | Warning]:
    """Les liens d'invitation menent-ils quelque part ?

    Ils pointent vers des pages de l'espace client. Construits sur
    `EVKHA_BASE_URL` — l'adresse de l'API —, ils renvoyaient un 404 : la
    fonctionnalite Equipe etait livree, testee, et inutilisable.

    Un lien qui ne mene nulle part est pire qu'une invitation non partie : il a
    l'air d'avoir marche, et personne ne cherche la cause (regle 1).
    """
    problemes: list[Error | Warning] = []
    if settings.DEBUG:
        return problemes

    if not str(getattr(settings, "EVKHA_APP_URL", "") or ""):
        problemes.append(Error(
            "EVKHA_APP_URL n'est pas defini : les liens d'invitation et de "
            "reinitialisation de mot de passe menent a une page inexistante.",
            hint=(
                "Definir EVKHA_APP_URL sur l'adresse de l'espace client, "
                "par exemple https://app2.evkha.fr."
            ),
            id="evkha.C004",
        ))
    return problemes


#: Valeur de repli inscrite dans `settings.py`. Nommée ici pour que le contrôle
#: la reconnaisse sans la recopier à l'aveugle : si elle change là-bas et pas
#: ici, le contrôle cesse de protéger sans rien dire — d'où le test dédié qui
#: compare les deux.
REPLI_CONNU = "dev-only-secret-key"

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


#: Bouchons qui remplacent une promesse du produit, et non un simple detail.
#:
#: `EVKHA_USE_STUB_SEARCH` etait ABSENT de la production, donc a `True` par
#: defaut. Chaque « etude de marche » etait donc redigee a partir de resultats
#: portant en toutes lettres « Contenu de demonstration (mode stub EVKHA).
#: Aucune donnee reelle. » — le modele n'avait rien d'autre a citer, d'ou des
#: chapitres qui tournent en rond, et le mot EVKHA se glissait au passage dans
#: un document en marque blanche.
#:
#: Le fournisseur reel est GRATUIT et ne demande aucune cle : la recherche
#: n'etait pas coupee pour economiser, elle l'etait par oubli.
#:
#: On enumere les bouchons qui touchent a la SUBSTANCE du livrable. Le bouchon
#: d'e-mail n'y figure pas : ne pas envoyer un courriel se voit, tandis qu'une
#: etude bâtie sur du vide a l'air d'une etude.
BOUCHONS_INTERDITS_EN_PRODUCTION = (
    ("EVKHA_USE_STUB_AI", "aucun texte n'est redige par le modele"),
    ("EVKHA_USE_STUB_SEARCH", "aucune recherche reelle n'ancre les chiffres"),
)


@register()
def controler_bouchons_de_production(
    app_configs: object, **kwargs: object
) -> list[Error | Warning]:
    """Le produit fait-il reellement ce qu'il vend ?

    Un bouchon rend un service qui a la FORME du vrai. C'est ce qui le rend
    dangereux : rien ne casse, rien n'alerte, et le client recoit un document
    qui ressemble a une etude sans en etre une (regle 1).

    Ce controle est un ERREUR et non un avertissement : un avertissement se
    lit une fois, puis se confond avec le bruit du demarrage.
    """
    problemes: list[Error | Warning] = []
    if settings.DEBUG:
        return problemes

    for nom, consequence in BOUCHONS_INTERDITS_EN_PRODUCTION:
        if bool(getattr(settings, nom, False)):
            problemes.append(Error(
                f"{nom} est actif en production : {consequence}. Le livrable "
                "a la forme d'une etude sans en etre une.",
                hint=f"Poser {nom}=false dans les variables du serveur.",
                id="evkha.C005",
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


@register()
def controler_formules_payables(
    app_configs: object, **kwargs: object
) -> list[Error | Warning]:
    """Les formules proposées peuvent-elles réellement être achetées ?

    Une formule `active` sans `reference_paiement` est un bouton « Souscrire »
    qui échoue au clic. `seed_formules` ne renseigne pas ce champ, et ne le peut
    pas : les identifiants de tarif appartiennent au compte Stripe de la
    cliente, ils n'ont rien à faire dans le dépôt. Sur une base fraîchement
    amorcée, les quatre formules sont donc affichées et aucune n'est achetable.

    Rien n'est cassé pour autant : `stripe_api` lève avec un motif lisible, et
    l'espace client répond 503. Le défaut n'est pas que ça échoue, c'est que ça
    n'échoue **que devant le client**. La liste d'administration le montre déjà,
    mais encore faut-il aller la regarder. Ce contrôle le dit à chaque
    démarrage, dans les journaux, sans que personne n'ait à y penser.

    **`Warning` et jamais `Error`**, pour la raison exacte qui vaut déjà pour
    `STRIPE_SECRET_KEY` : un `Error` fait échouer `migrate`, donc empêcherait de
    déployer la version qui apporte le paiement — alors que les références ne
    peuvent se saisir qu'une fois cette version en ligne. Le contrôle refuserait
    de démarrer parce qu'il n'a rien à dire d'autre que « ce n'est pas encore
    branché ».
    """
    from django.db import DatabaseError  # noqa: PLC0415

    from organisations.models import Formule  # noqa: PLC0415

    try:
        sans_tarif = sorted(
            Formule.objects.filter(active=True)
            .filter(reference_paiement="")
            .values_list("libelle", flat=True)
        )
    except DatabaseError:
        # Les controles systeme tournent AVANT `migrate`. Sur une base neuve,
        # la table n'existe pas encore. Se taire est ici la bonne reponse — il
        # n'y a aucune formule a juger, pas meme zero — la ou lever ferait
        # echouer le tout premier deploiement.
        return []

    if not sans_tarif:
        return []

    return [Warning(
        f"{len(sans_tarif)} formule(s) active(s) sans reference de paiement : "
        f"{', '.join(sans_tarif)}. Le bouton « Souscrire » echouera au clic.",
        hint=(
            "Coller l'identifiant de tarif Stripe (price_…) dans le champ "
            "« Reference paiement » de chaque formule, depuis l'administration. "
            "Il appartient au compte Stripe et ne peut pas venir du depot."
        ),
        id="evkha.W005",
    )]


#: Valeur de repli inscrite dans `settings.py`. Nommée ici pour que le contrôle
#: la reconnaisse sans la recopier à l'aveugle : si elle change là-bas et pas
#: ici, le contrôle cesse de protéger sans rien dire — d'où le test dédié qui
#: compare les deux.
REPLI_CONNU = "dev-only-secret-key"

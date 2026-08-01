"""Deux protections qui existaient dans le code et pas dans la production livrée.

**1. Les plafonds de tentatives ne comptaient pas ce qu'ils annonçaient.**
`limitation.py` s'appuie sur `django.core.cache`. Aucun backend n'était déclaré
dans `settings.py` : Django retombait sur `LocMemCache`, un dictionnaire local
au processus, pendant que la production tourne `gunicorn --workers 2`. Chaque
worker tenait son propre compteur — le plafond « 10 essais par quart d'heure »
en autorisait donc 20, et repartait de zéro à chaque redéploiement.

La suite de tests ne pouvait pas le voir : elle tourne dans UN seul processus,
où `LocMemCache` se comporte exactement comme un cache partagé. C'est la
règle 7 sous sa forme la plus désagréable — le vert ne prouvait rien sur ce qui
était livré.

**2. La clé secrète avait un repli public.** `SECRET_KEY` retombait sur une
valeur inscrite en clair dans le dépôt, qui signe les sessions de
l'administration Django. Le dépôt savait pourtant déjà refuser de démarrer sans
le jeton du tableau de bord : le défaut avait été corrigé pour un secret, pas
pour sa classe (règle 4).
"""
from __future__ import annotations

from typing import Any

import pytest

from organisations import checks

pytestmark = pytest.mark.django_db


LOCMEM = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
}
REDIS = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://redis:6379/1",
    }
}


# ── Le cache doit être partagé entre les processus ───────────────────────────


def test_un_cache_local_est_refuse_en_production(settings: Any) -> None:
    """Le test qui échoue sur le code d'avant : il n'y avait aucun contrôle."""
    settings.DEBUG = False
    settings.CACHES = LOCMEM

    codes = [p.id for p in checks.controler_cache_partage(None)]
    assert "evkha.C001" in codes, "un cache non partage est passe sans un mot"


def test_un_cache_qui_ne_garde_rien_est_refuse_aussi(settings: Any) -> None:
    """La CLASSE du défaut, pas l'exemple (règle 4).

    `DummyCache` n'est pas `LocMemCache`, mais un plafond posé dessus ne compte
    jamais rien du tout. Un contrôle qui n'aurait nommé que `LocMemCache`
    laisserait passer strictement le même défaut sous un autre nom.
    """
    settings.DEBUG = False
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}

    assert "evkha.C001" in [p.id for p in checks.controler_cache_partage(None)]


def test_un_cache_partage_ne_declenche_rien(settings: Any) -> None:
    """Contre-épreuve : le contrôle ne doit pas crier sur une bonne config."""
    settings.DEBUG = False
    settings.CACHES = REDIS

    assert checks.controler_cache_partage(None) == []


def test_le_developpement_n_est_pas_concerne(settings: Any) -> None:
    """Un seul processus sert les requêtes : le cache local y est légitime.

    Crier ici apprendrait à ignorer le message — et donc à l'ignorer aussi le
    jour où il compte.
    """
    settings.DEBUG = True
    settings.CACHES = LOCMEM

    assert checks.controler_cache_partage(None) == []


def test_le_defaut_livre_est_bien_celui_qu_on_croit() -> None:
    """Le contrôle porte-t-il sur le réglage RÉELLEMENT chargé ?

    Sans ce test, on vérifierait des `CACHES` fabriqués par le test lui-même,
    jamais ceux que `settings.py` produit. Le contrôle serait vert sur une
    configuration qui n'existe nulle part.
    """
    from django.conf import settings as reglages

    backend = reglages.CACHES["default"]["BACKEND"]
    if getattr(reglages, "EVKHA_CACHE_URL", ""):
        assert "RedisCache" in backend
    else:
        # Repli assume en developpement et en test — et refuse en production
        # par `evkha.C001`, ce que les tests ci-dessus verrouillent.
        assert backend in checks.BACKENDS_NON_PARTAGES


# ── La clé secrète ───────────────────────────────────────────────────────────


def test_le_repli_de_cle_secrete_est_refuse_en_production(settings: Any) -> None:
    settings.DEBUG = False
    settings.SECRET_KEY = checks.REPLI_CONNU

    assert "evkha.C002" in [p.id for p in checks.controler_secret_django(None)]


# Pas de test « clé vide » : Django lui-même lève `ImproperlyConfigured` a la
# premiere lecture d'une `SECRET_KEY` vide. Ecrire un test qui pretendrait
# l'exercer donnerait une couverture imaginaire — le cas ne peut pas se
# produire, et c'est tres bien ainsi.


def test_une_cle_trop_courte_est_signalee(settings: Any) -> None:
    settings.DEBUG = False
    settings.SECRET_KEY = "trop-court"

    assert "evkha.C003" in [p.id for p in checks.controler_secret_django(None)]


def test_une_vraie_cle_ne_declenche_rien(settings: Any) -> None:
    settings.DEBUG = False
    settings.SECRET_KEY = "f" * 64

    assert checks.controler_secret_django(None) == []


def test_le_repli_surveille_est_celui_qui_est_reellement_ecrit() -> None:
    """Le test qui empêche le contrôle de devenir décoratif.

    `checks.REPLI_CONNU` recopie une valeur qui vit dans `settings.py`. Si elle
    y est modifiée sans l'être ici, le contrôle cesse de reconnaître le repli —
    et se tait sur exactement ce qu'il devait attraper. Deux sources pour une
    même vérité (règle 5) : à défaut de pouvoir les fusionner, on vérifie
    qu'elles disent la même chose.
    """
    import pathlib
    import re

    source = pathlib.Path(__file__).resolve().parents[1] / "evkha" / "settings.py"
    texte = source.read_text(encoding="utf-8")
    trouve = re.search(r'SECRET_KEY\s*=\s*env\([^)]*default="([^"]*)"', texte)

    assert trouve, "la ligne SECRET_KEY de settings.py n'a plus la forme attendue"
    assert trouve.group(1) == checks.REPLI_CONNU, (
        "le repli de settings.py a change : checks.REPLI_CONNU ne le reconnait plus"
    )

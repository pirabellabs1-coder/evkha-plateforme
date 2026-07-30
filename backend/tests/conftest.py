"""Configuration globale pytest.

Deux garde-fous, tous deux autouse : ils doivent s'appliquer meme si personne
n'y pense en ecrivant un test.
"""
from __future__ import annotations

import pytest
from django.conf import settings


@pytest.fixture(autouse=True)
def _celery_eager() -> None:
    """Celery en mode eager : aucune tentative de connexion Redis."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = False


@pytest.fixture(autouse=True)
def _force_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    """La suite de tests ne doit JAMAIS toucher un service externe payant.

    Les reglages venaient du `.env` : le jour ou l'on y passe
    EVKHA_USE_STUB_AI=false pour lancer un vrai dossier, la suite entiere se
    met a appeler la vraie API Anthropic. Constate en direct (juillet 2026) :
    chaque `pytest` partait sur des dizaines d'appels reels, lents et
    FACTURES, pour des tests censes etre deterministes et gratuits.

    Un test qui depend d'un fichier de configuration local n'est pas
    reproductible. On force donc les stubs ici, quoi qu'il y ait dans le `.env`
    et sur la machine de qui que ce soit. Un test qui veut le vrai client doit
    le demander explicitement, jamais l'obtenir par accident.
    """
    for flag in (
        "EVKHA_USE_STUB_AI",
        "EVKHA_USE_STUB_EMAIL",
        "EVKHA_USE_STUB_PDF",
        "EVKHA_USE_STUB_DOCS",
        "EVKHA_USE_STUB_GAMMA",
        "EVKHA_USE_STUB_SEARCH",
    ):
        if hasattr(settings, flag):
            monkeypatch.setattr(settings, flag, True, raising=False)

    # Ceinture-bretelles : meme si un client reel etait instancie, il ne
    # trouverait pas de cle et echouerait bruyamment plutot que de facturer.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.fixture(autouse=True, scope="session")
def _hachage_rapide() -> None:
    """Hachage de mot de passe rapide pendant les tests, jamais en production.

    `creer_compte` d'un compte d'espace client passe par PBKDF2 avec le nombre
    d'iterations de production — ce qui est exactement ce qu'on veut en
    production, et ce qui coute environ un tiers de seconde par appel. Une
    cinquantaine de comptes de test suffisaient a faire depasser la suite de
    plusieurs minutes.

    Ce reglage ne touche QUE la configuration de test : le hachage reel reste
    celui de Django. Affaiblir le hachage de production pour gagner du temps de
    test serait evidemment inacceptable.
    """
    settings.PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.MD5PasswordHasher",
    ]

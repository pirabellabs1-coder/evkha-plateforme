"""Configuration globale pytest.

Force Celery en mode eager (execution synchrone in-process) pour eviter
toute tentative de connexion Redis pendant les tests.
"""
from __future__ import annotations

import pytest
from django.conf import settings


@pytest.fixture(autouse=True)
def _celery_eager() -> None:
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = False

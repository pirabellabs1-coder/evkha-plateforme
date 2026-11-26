"""La tâche périodique de la lettre : voir `lettre.envoi`."""
from __future__ import annotations

from typing import Any

from celery import shared_task

from . import envoi


@shared_task(name="lettre.pomper")  # type: ignore[untyped-decorator]
def pomper() -> dict[str, Any]:
    return envoi.pomper()

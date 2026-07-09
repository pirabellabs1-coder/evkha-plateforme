from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from django.apps import apps

from catalog.models import DeliveryMode, Offer
from delivery.models import EmailProvider
from generation.models import GenerationJob


def test_phase0_scaffolds_the_nine_domain_apps() -> None:
    expected_apps = {
        "catalog",
        "customers",
        "orders",
        "intake",
        "generation",
        "documents",
        "integrations",
        "delivery",
        "monitoring",
    }

    installed_apps = {config.name for config in apps.get_app_configs()}

    assert expected_apps.issubset(installed_apps)


def test_offer_contract_freezes_gamma_delivery_and_retention_defaults() -> None:
    offer = Offer(name="Etude de marche", slug="etude-marche", deliverable_type="market_study")

    assert offer.gamma_enabled is False
    assert offer.delivery_mode == DeliveryMode.LINK_AND_PDF
    assert offer.retention_days == 7


def test_generation_job_contract_freezes_cost_ceiling() -> None:
    job = GenerationJob(deliverable_type="market_study")

    assert job.budget_eur == Decimal("2.0000")
    assert job.total_cost_eur == Decimal("0.0000")


def test_delivery_contract_freezes_brevo_as_email_provider() -> None:
    assert EmailProvider.BREVO.value == "brevo"


def test_n8n_uses_a_dedicated_postgres_database_contract() -> None:
    # Fichiers d'infra situes a la racine du repo ; le test ne peut s'executer
    # qu'a partir de la racine (pytest depuis /). En CI on lance depuis /backend.
    import pytest  # noqa: PLC0415
    root = Path(__file__).parent.parent.parent
    compose_path = root / "docker-compose.yml"
    sql_path = root / "infra/postgres/init/001-create-n8n-db.sql"
    if not compose_path.exists() or not sql_path.exists():
        pytest.skip("infra files not found — run pytest from repo root to enable")
    compose = compose_path.read_text(encoding="utf-8")
    init_script = sql_path.read_text(encoding="utf-8")
    assert "DB_POSTGRESDB_DATABASE: ${N8N_POSTGRES_DB:-n8n}" in compose
    assert "CREATE DATABASE n8n" in init_script

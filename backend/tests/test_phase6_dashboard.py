from __future__ import annotations

import pytest
from django.test import Client, override_settings

# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_overview_accessible_when_auth_disabled() -> None:
    client = Client()
    with override_settings(EVKHA_DASHBOARD_AUTH_DISABLED=True):
        response = client.get("/api/dashboard/overview/")
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert "cost_30d_eur" in data
    assert "incidents" in data


@pytest.mark.django_db
def test_dashboard_returns_401_when_auth_enabled_and_no_token() -> None:
    client = Client()
    with override_settings(
        EVKHA_DASHBOARD_AUTH_DISABLED=False,
        EVKHA_DASHBOARD_TOKEN="super-secret-token-32chars-min",
    ):
        response = client.get("/api/dashboard/overview/")
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


@pytest.mark.django_db
def test_dashboard_accessible_with_correct_bearer_token() -> None:
    token = "super-secret-token-32chars-min"
    client = Client()
    with override_settings(
        EVKHA_DASHBOARD_AUTH_DISABLED=False,
        EVKHA_DASHBOARD_TOKEN=token,
    ):
        response = client.get(
            "/api/dashboard/overview/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
    assert response.status_code == 200


@pytest.mark.django_db
def test_dashboard_returns_401_with_wrong_token() -> None:
    client = Client()
    with override_settings(
        EVKHA_DASHBOARD_AUTH_DISABLED=False,
        EVKHA_DASHBOARD_TOKEN="correct-secret-token-32chars",
    ):
        response = client.get(
            "/api/dashboard/overview/",
            HTTP_AUTHORIZATION="Bearer wrong-token",
        )
    assert response.status_code == 401


@pytest.mark.django_db
def test_dashboard_accepts_token_via_query_param() -> None:
    token = "query-param-token-32chars-minx"
    client = Client()
    with override_settings(
        EVKHA_DASHBOARD_AUTH_DISABLED=False,
        EVKHA_DASHBOARD_TOKEN=token,
    ):
        response = client.get(f"/api/dashboard/overview/?token={token}")
    assert response.status_code == 200


@pytest.mark.django_db
def test_non_dashboard_routes_unaffected_by_middleware() -> None:
    """Le middleware ne doit pas toucher aux routes hors /api/dashboard/."""
    client = Client()
    with override_settings(
        EVKHA_DASHBOARD_AUTH_DISABLED=False,
        EVKHA_DASHBOARD_TOKEN="some-token",
    ):
        response = client.get("/healthz/")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Dashboard endpoints
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_jobs_list_returns_empty_list_initially() -> None:
    client = Client()
    with override_settings(EVKHA_DASHBOARD_AUTH_DISABLED=True):
        response = client.get("/api/dashboard/jobs/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.django_db
def test_job_detail_returns_404_for_unknown_id() -> None:
    import uuid

    client = Client()
    with override_settings(EVKHA_DASHBOARD_AUTH_DISABLED=True):
        response = client.get(f"/api/dashboard/jobs/{uuid.uuid4()}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_incidents_list_returns_empty_list_initially() -> None:
    client = Client()
    with override_settings(EVKHA_DASHBOARD_AUTH_DISABLED=True):
        response = client.get("/api/dashboard/incidents/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

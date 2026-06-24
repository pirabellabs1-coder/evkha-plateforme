from __future__ import annotations

import json
import uuid as _uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from catalog.models import DeliverableType, Offer
from customers.models import Customer, CustomerType
from generation.models import ChapterStatus, GenerationJob, JobStatus
from generation.services import bootstrap_generation_job
from generation.tasks import run_generation_job_task
from intake.models import IntakeSource, IntakeStatus, IntakeSubmission
from monitoring.models import IncidentSeverity, IncidentStatus, OperationalIncident
from orders.models import Order, OrderStatus

_MANUAL_OFFER_NAMES: dict[str, str] = {
    DeliverableType.MARKET_STUDY:      "Manuel — Étude de marché",
    DeliverableType.COMPETITOR_STUDY:  "Manuel — Étude de concurrence",
    DeliverableType.BUSINESS_PLAN:     "Manuel — Business Plan",
    DeliverableType.BUSINESS_STRATEGY: "Manuel — Stratégie Business",
}

_REQUIRED_VARS = ("SECTEUR", "PAYS", "PROJET", "ZONE")
_OPTIONAL_VARS = (
    "POSITIONNEMENT", "CLIENTELE_CIBLE", "MODELE_ECONOMIQUE",
    "ELEMENTS_A_RETENIR", "DEMANDES_SPECIFIQUES", "CONCURRENTS",
    "CAPITAL_INITIAL", "FORME_JURIDIQUE", "MODELE_REVENUS", "EQUIPE",
    "OBJECTIF_STRATEGIQUE", "HORIZON_PLANIFICATION",
    "LOGO_URL", "COULEUR_PRINCIPALE", "COULEUR_SECONDAIRE", "NOM_ENTREPRISE",
    "PHOTO_1", "PHOTO_2", "PHOTO_3",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decimal_default(obj: object) -> str:
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, UUID):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _json(data: Any, status: int = 200) -> JsonResponse:
    return JsonResponse(
        json.loads(json.dumps(data, default=_decimal_default)),
        status=status,
        safe=False,
    )


def _job_summary(job: GenerationJob) -> dict[str, Any]:
    chapters_qs = list(job.chapters.all())
    done = sum(1 for c in chapters_qs if c.status == ChapterStatus.DONE)
    return {
        "id": str(job.id),
        "deliverable_type": job.deliverable_type,
        "status": job.status,
        "total_cost_eur": str(job.total_cost_eur),
        "budget_eur": str(job.budget_eur),
        "chapters_done": done,
        "chapters_total": len(chapters_qs),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "order_id": str(job.order_id),
        "error_message": job.error_message or None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@require_GET
@csrf_exempt
def overview(request: HttpRequest) -> JsonResponse:
    """Vue d'ensemble : metriques du jour + totaux."""
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_30 = now - timedelta(days=30)

    jobs_total = GenerationJob.objects.count()
    jobs_today = GenerationJob.objects.filter(created_at__gte=today_start).count()
    jobs_running = GenerationJob.objects.filter(status=JobStatus.RUNNING).count()
    jobs_failed = GenerationJob.objects.filter(status=JobStatus.FAILED).count()

    cost_30d: Decimal = sum(
        (j.total_cost_eur for j in GenerationJob.objects.filter(created_at__gte=last_30)),
        Decimal("0"),
    )

    incidents_open = OperationalIncident.objects.filter(status=IncidentStatus.OPEN).count()
    incidents_critical = OperationalIncident.objects.filter(
        status=IncidentStatus.OPEN,
        severity__in=[IncidentSeverity.HIGH, IncidentSeverity.CRITICAL],
    ).count()

    return _json(
        {
            "jobs": {
                "total": jobs_total,
                "today": jobs_today,
                "running": jobs_running,
                "failed": jobs_failed,
            },
            "cost_30d_eur": str(cost_30d),
            "incidents": {"open": incidents_open, "critical_or_high": incidents_critical},
        }
    )


@require_GET
@csrf_exempt
def jobs_list(request: HttpRequest) -> JsonResponse:
    """Liste des jobs recents (50 max), filtrable par ?status=."""
    status_filter = request.GET.get("status")
    qs = list(
        GenerationJob.objects.select_related("order__offer", "order__customer").order_by(
            "-created_at"
        )[:50]
    )
    jobs = [_job_summary(j) for j in qs if not status_filter or j.status == status_filter]
    return _json(jobs)


@require_GET
@csrf_exempt
def job_detail(request: HttpRequest, job_id: str) -> JsonResponse:
    """Detail d'un job : infos + chapitres."""
    try:
        job = GenerationJob.objects.select_related("order__offer", "order__customer").get(
            id=job_id
        )
    except GenerationJob.DoesNotExist:
        return _json({"error": "Job not found."}, status=404)
    except Exception:
        return _json({"error": "Invalid job id."}, status=400)

    chapters = [
        {
            "number": c.chapter_number,
            "title": c.chapter_title,
            "prompt_key": c.prompt_key,
            "status": c.status,
            "cost_eur": str(c.cost_eur),
            "input_tokens": c.input_tokens,
            "output_tokens": c.output_tokens,
            "retry_count": c.retry_count,
            "error_message": c.error_message or None,
        }
        for c in job.chapters.order_by("chapter_number")
    ]

    data = _job_summary(job)
    data["chapters"] = chapters
    data["customer_email"] = job.order.customer.email
    data["offer_name"] = job.order.offer.name
    return _json(data)


@require_GET
@csrf_exempt
def system_status(request: HttpRequest) -> JsonResponse:
    """Etat de la configuration : stubs actifs, intégrations."""
    from django.conf import settings  # noqa: PLC0415

    return _json(
        {
            "api": "ok",
            "email_stub": bool(getattr(settings, "EVKHA_USE_STUB_EMAIL", True)),
            "ai_stub": bool(getattr(settings, "EVKHA_USE_STUB_AI", True)),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def create_generation(request: HttpRequest) -> JsonResponse:
    """Génération manuelle depuis le dashboard (ComeUp, tests, etc.)."""
    try:
        body: dict[str, Any] = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, ValueError):
        return _json({"error": "JSON invalide."}, status=400)

    deliverable_type = (body.get("deliverable_type") or "").strip()
    if deliverable_type not in DeliverableType.values:
        return _json(
            {"error": f"Type invalide. Valeurs : {', '.join(DeliverableType.values)}"},
            status=400,
        )

    customer_email = (body.get("customer_email") or "").strip().lower()
    if not customer_email:
        return _json({"error": "customer_email requis."}, status=400)

    variables: dict[str, str] = {}
    for key in _REQUIRED_VARS + _OPTIONAL_VARS:
        val = (body.get(key) or body.get(key.lower()) or "").strip()
        if val:
            variables[key] = val

    missing = [k for k in _REQUIRED_VARS if not variables.get(k)]
    if missing:
        return _json({"error": f"Champs requis manquants : {', '.join(missing)}"}, status=400)

    offer, _ = Offer.objects.get_or_create(
        slug=f"manuel-{deliverable_type.replace('_', '-')}",
        defaults={
            "name": _MANUAL_OFFER_NAMES[deliverable_type],
            "deliverable_type": deliverable_type,
            "is_active": True,
        },
    )

    customer, _ = Customer.objects.update_or_create(
        email=customer_email,
        defaults={
            "first_name":    (body.get("first_name") or "").strip(),
            "last_name":     (body.get("last_name") or "").strip(),
            "company_name":  (body.get("company_name") or "").strip(),
            "customer_type": CustomerType.B2B,
        },
    )

    order = Order.objects.create(
        customer=customer,
        offer=offer,
        systeme_order_id=f"manuel-{_uuid.uuid4().hex[:12]}",
        status=OrderStatus.WAITING_INTAKE,
        raw_payload=body,
    )

    submission = IntakeSubmission.objects.create(
        order=order,
        source=IntakeSource.MANUAL,
        status=IntakeStatus.NORMALIZED,
        raw_payload=body,
        normalized_variables=variables,
        missing_fields=[],
    )

    try:
        job = bootstrap_generation_job(submission)
        run_generation_job_task.delay(str(job.id))
    except Exception as exc:
        return _json({"error": str(exc)}, status=500)

    return _json({"job_id": str(job.id), "status": job.status}, status=202)


@require_GET
@csrf_exempt
def incidents_list(request: HttpRequest) -> JsonResponse:
    """50 incidents les plus recents."""
    qs = OperationalIncident.objects.select_related("order", "job").order_by("-created_at")[:50]
    items = [
        {
            "id": str(inc.id),
            "title": inc.title,
            "severity": inc.severity,
            "status": inc.status,
            "created_at": inc.created_at.isoformat(),
            "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
            "job_id": str(inc.job_id) if inc.job_id else None,
            "order_id": str(inc.order_id) if inc.order_id else None,
            "details": inc.details,
        }
        for inc in qs
    ]
    return _json(items)

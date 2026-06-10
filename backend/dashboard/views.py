from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from generation.models import ChapterStatus, GenerationJob, JobStatus
from monitoring.models import IncidentSeverity, IncidentStatus, OperationalIncident

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

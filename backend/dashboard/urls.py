from __future__ import annotations

from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("overview/", views.overview, name="overview"),
    path("jobs/", views.jobs_list, name="jobs-list"),
    path("jobs/<str:job_id>/", views.job_detail, name="job-detail"),
    path("incidents/", views.incidents_list, name="incidents-list"),
    path("system/", views.system_status, name="system-status"),
]

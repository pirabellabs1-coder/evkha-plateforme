from __future__ import annotations

from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("overview/", views.overview, name="overview"),
    # Jobs
    path("jobs/", views.jobs_list, name="jobs-list"),
    path("jobs/<str:job_id>/", views.job_detail, name="job-detail"),
    path("jobs/<str:job_id>/relaunch/", views.job_relaunch, name="job-relaunch"),
    path("jobs/<str:job_id>/redeliver/", views.job_redeliver, name="job-redeliver"),
    path("jobs/<str:job_id>/send-email/", views.job_send_email, name="job-send-email"),
    # Incidents
    path("incidents/", views.incidents_list, name="incidents-list"),
    path("incidents/<str:incident_id>/resolve/", views.incident_resolve, name="incident-resolve"),
    # Clients
    path("customers/", views.customers_list, name="customers-list"),
    path("customers/<str:customer_id>/", views.customer_detail, name="customer-detail"),
    # Commandes
    path("orders/", views.orders_list, name="orders-list"),
    # Système
    path("system/", views.system_status, name="system-status"),
    # Génération manuelle
    path("generate/", views.create_generation, name="generate"),
]

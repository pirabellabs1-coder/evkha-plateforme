from __future__ import annotations

from django.urls import path

from . import actions, supervision, views

app_name = "dashboard"

urlpatterns = [
    path("overview/", views.overview, name="overview"),
    # Jobs
    path("jobs/", views.jobs_list, name="jobs-list"),
    path("jobs/<str:job_id>/", views.job_detail, name="job-detail"),
    path("jobs/<str:job_id>/cancel/", views.job_cancel, name="job-cancel"),
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
    # Supervision (refonte de l'espace administrateur) — lecture seule
    path("supervision/synthese/", supervision.synthese, name="supervision-synthese"),
    path("supervision/evolution/", supervision.evolution, name="supervision-evolution"),
    path(
        "supervision/organisations/",
        supervision.organisations,
        name="supervision-organisations",
    ),
    path("supervision/demandes/", supervision.demandes, name="supervision-demandes"),
    # Suivi des paiements : aboutis, en cours, abandonnes. Rien n'etait
    # enregistre — une session ouverte puis delaissee ne laissait aucune trace.
    path(
        "supervision/transactions/",
        supervision.transactions,
        name="supervision-transactions",
    ),
    path(
        "supervision/transactions/<str:transaction_id>/relancer/",
        supervision.relancer_la_transaction,
        name="supervision-transaction-relancer",
    ),
    # Actions d'administration : elles remplacent l'usage de /admin/ Django.
    path("supervision/formules/", actions.formules, name="supervision-formules"),
    path(
        "supervision/abonnes/",
        actions.creer_abonne,
        name="supervision-creer-abonne",
    ),
    path(
        "supervision/organisations/<str:organisation_id>/doter/",
        actions.doter,
        name="supervision-doter",
    ),
    path(
        "supervision/organisations/<str:organisation_id>/statut/",
        actions.basculer_statut,
        name="supervision-statut",
    ),
    path(
        "supervision/demandes/<str:demande_id>/traiter/",
        actions.traiter_demande,
        name="supervision-traiter",
    ),
    # Système
    path("system/", views.system_status, name="system-status"),
    # Génération manuelle
    path("generate/", views.create_generation, name="generate"),
]

from __future__ import annotations

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    EVKHA_DEFAULT_RETENTION_DAYS=(int, 7),
    EVKHA_USE_STUB_AI=(bool, True),
    EVKHA_USE_STUB_DOCS=(bool, True),
    EVKHA_USE_STUB_GAMMA=(bool, True),
    EVKHA_USE_STUB_EMAIL=(bool, True),
    EVKHA_USE_STUB_PDF=(bool, True),
    EVKHA_DASHBOARD_AUTH_DISABLED=(bool, True),
    EVKHA_BEHIND_PROXY=(bool, False),
    CSRF_TRUSTED_ORIGINS=(list, []),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-secret-key")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

# Production derriere Traefik/Coolify (TLS termine par le proxy) :
#   EVKHA_BEHIND_PROXY=true
#   CSRF_TRUSTED_ORIGINS=https://evkha.fr,https://www.evkha.fr
# Sans ces deux reglages, le login /admin/ echoue au controle CSRF en HTTPS.
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")
if env("EVKHA_BEHIND_PROXY"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "catalog",
    "customers",
    "orders",
    "intake",
    "generation",
    "documents",
    "integrations",
    "delivery",
    "monitoring",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Protege /api/dashboard/ par Bearer token (Better Auth).
    "dashboard.middleware.DashboardAuthMiddleware",
]

ROOT_URLCONF = "evkha.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "evkha.wsgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = env("DJANGO_TIME_ZONE", default="Europe/Paris")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
# Cible de collectstatic (admin Django) — servi par la route /static/ de urls.py.
STATIC_ROOT = BASE_DIR / "staticfiles"
# Fichiers uploadés / générés (PDF WeasyPrint, HTML preview).
# En production : monter un volume persistant sur MEDIA_ROOT et servir /media/ via nginx.
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/1")

# Tâches périodiques (service beat du compose prod).
# Purge horaire des artefacts expirés — rétention 7 jours (D5).
CELERY_BEAT_SCHEDULE = {
    "purge-expired-artifacts": {
        "task": "delivery.purge_expired_artifacts",
        "schedule": 3600.0,
    },
}

EVKHA_DEFAULT_RETENTION_DAYS = env("EVKHA_DEFAULT_RETENTION_DAYS")
EVKHA_EMAIL_PROVIDER = env("EVKHA_EMAIL_PROVIDER", default="brevo")

# Webhook shared secrets (M1).
SYSTEME_WEBHOOK_SECRET = env("SYSTEME_WEBHOOK_SECRET", default="")
TALLY_WEBHOOK_SECRET = env("TALLY_WEBHOOK_SECRET", default="")

# Brevo — email transactionnel de livraison (utilise quand EVKHA_USE_STUB_EMAIL=false).
BREVO_API_KEY = env("BREVO_API_KEY", default="")
BREVO_SENDER_EMAIL = env("BREVO_SENDER_EMAIL", default="contact@evkha.fr")
BREVO_SENDER_NAME = env("BREVO_SENDER_NAME", default="Evkha")

# Modele Claude actif pour la tarification du Cost Engine (M4).
EVKHA_CLAUDE_MODEL = env("EVKHA_CLAUDE_MODEL", default="claude-sonnet")
EVKHA_ANTHROPIC_MODEL_ID = env("EVKHA_ANTHROPIC_MODEL_ID", default="")

# Adaptateurs externes : stubs deterministes par defaut (dev/CI, aucun reseau).
# Passer a False en production une fois les credentials configures.
EVKHA_USE_STUB_AI = env("EVKHA_USE_STUB_AI")
EVKHA_USE_STUB_DOCS = env("EVKHA_USE_STUB_DOCS")
EVKHA_USE_STUB_GAMMA = env("EVKHA_USE_STUB_GAMMA")
EVKHA_USE_STUB_EMAIL = env("EVKHA_USE_STUB_EMAIL")
EVKHA_USE_STUB_PDF = env("EVKHA_USE_STUB_PDF")

# URL de base publique du serveur (utilisée par WeasyPrint et Brevo pour
# construire des URLs absolues valides pour les fichiers média).
# Exemple production : https://evkha.com
EVKHA_BASE_URL = env("EVKHA_BASE_URL", default="http://localhost:8000")

# Dashboard auth (Phase 6).
# EVKHA_DASHBOARD_AUTH_DISABLED=true en dev/CI (defaut).
# En production : EVKHA_DASHBOARD_AUTH_DISABLED=false
#                  EVKHA_DASHBOARD_TOKEN=<openssl rand -hex 32>
# TODO: remplacer par JWT Better Auth quand BETTER_AUTH_SECRET est configure.
EVKHA_DASHBOARD_AUTH_DISABLED = env("EVKHA_DASHBOARD_AUTH_DISABLED")
EVKHA_DASHBOARD_TOKEN = env("EVKHA_DASHBOARD_TOKEN", default="")

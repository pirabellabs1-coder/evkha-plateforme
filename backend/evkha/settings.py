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
    EVKHA_USE_STUB_SEARCH=(bool, True),
    EVKHA_DASHBOARD_AUTH_DISABLED=(bool, False),
    EVKHA_BEHIND_PROXY=(bool, False),
    CSRF_TRUSTED_ORIGINS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
    EVKHA_AUTORISER_PREVISUALISATIONS_VERCEL=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-secret-key")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

# Production derriere Traefik/Coolify (TLS termine par le proxy) :
#   EVKHA_BEHIND_PROXY=true
#   CSRF_TRUSTED_ORIGINS=https://app.evkha.fr,https://dashboard.evkha.fr
# Sans ces deux reglages, le login /admin/ echoue au controle CSRF en HTTPS.
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")
if env("EVKHA_BEHIND_PROXY"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# ── CORS ─────────────────────────────────────────────────────────────────────
# Le front vit sur un domaine (Vercel), l'API sur un autre (le VPS). Sans
# en-tetes CORS, le navigateur bloque chaque appel : c'est le premier point qui
# casse a la mise en ligne.
#
#   CORS_ALLOWED_ORIGINS=https://app.evkha.fr,https://evkha.vercel.app
#
# `CORS_ALLOW_CREDENTIALS` reste FAUX : l'authentification passe par un jeton
# porte dans l'en-tete Authorization (cf. dashboard/middleware.py), pas par un
# cookie. Autoriser les identifiants ouvrirait l'envoi automatique des cookies
# de session vers un autre domaine sans qu'aucun code ne le demande.
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = False
CORS_URLS_REGEX = r"^/(api|webhooks)/.*$"

# Chaque deploiement de previsualisation Vercel porte un domaine different
# (`projet-git-branche-equipe.vercel.app`) : une liste fixe ne peut pas les
# couvrir. Le motif reste DESACTIVE par defaut, et il doit le rester en
# production : il autoriserait n'importe quel site heberge sur `vercel.app` a
# lire les reponses de l'API pour un porteur de jeton valide.
if env("EVKHA_AUTORISER_PREVISUALISATIONS_VERCEL"):
    CORS_ALLOWED_ORIGIN_REGEXES = [r"^https://[a-z0-9-]+\.vercel\.app$"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "catalog",
    "customers",
    "organisations",
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
    # Le plus haut possible, et OBLIGATOIREMENT avant CommonMiddleware : c'est
    # lui qui doit pouvoir repondre a une requete preflight sans que le reste
    # de la pile ne s'en mele.
    "corsheaders.middleware.CorsMiddleware",
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
# Permet de tester le pipeline webhook en local sans worker Celery/Redis
# (execution synchrone). False par defaut : aucun impact en production.
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)

# Tâches périodiques (service beat du compose prod).
# Purge horaire des artefacts expirés — rétention 7 jours (D5).
CELERY_BEAT_SCHEDULE = {
    "purge-expired-artifacts": {
        "task": "delivery.purge_expired_artifacts",
        "schedule": 3600.0,
    },
    # Garde-fou : recree les tickets de credits B2B le 1er de chaque mois a 02:00 UTC.
    # Idempotent : ne fait rien si les tickets du mois existent deja.
    "refresh-monthly-subscription-credits": {
        "task": "customers.refresh_monthly_credits",
        "schedule": 3600.0,  # check horaire ; le service decide s'il y a quelque chose a faire
    },
    # Echeances des abonnements B2B du lot 4 (portefeuille de credits).
    # `appliquer_echeance` n'etait appelee que par la souscription et par une
    # action manuelle de l'admin Django : un abonne recevait ses credits UNE
    # fois et plus jamais. Verification horaire et non mensuelle, pour
    # rattraper un worker arrete le 1er du mois ; l'echeance est idempotente.
    "appliquer-echeances-abonnements-b2b": {
        "task": "organisations.appliquer_echeances",
        "schedule": 3600.0,
    },
    # Risque 6 — jobs bloques : reset automatique toutes les heures.
    # Un job RUNNING depuis plus de 2h est forcement bloque (crash worker, timeout reseau).
    # L'incident HIGH cree permet a l'admin de relancer manuellement depuis le dashboard.
    "reset-stuck-generation-jobs": {
        "task": "generation.reset_stuck_generation_jobs",
        "schedule": 3600.0,
    },
}

EVKHA_DEFAULT_RETENTION_DAYS = env("EVKHA_DEFAULT_RETENTION_DAYS")
EVKHA_EMAIL_PROVIDER = env("EVKHA_EMAIL_PROVIDER", default="brevo")

# Webhook shared secrets (M1).
SYSTEME_WEBHOOK_SECRET = env("SYSTEME_WEBHOOK_SECRET", default="")
TALLY_WEBHOOK_SECRET = env("TALLY_WEBHOOK_SECRET", default="")

# URLs Tally par type de livrable (envoyees dans les emails de tickets de credit).
# Configurees en prod via env. Chaque URL recoit ?order_id=<ticket_id> en query.
EVKHA_TALLY_URL_MARKET_STUDY = env("EVKHA_TALLY_URL_MARKET_STUDY", default="")
EVKHA_TALLY_URL_COMPETITOR_STUDY = env("EVKHA_TALLY_URL_COMPETITOR_STUDY", default="")
EVKHA_TALLY_URL_BUSINESS_PLAN = env("EVKHA_TALLY_URL_BUSINESS_PLAN", default="")
EVKHA_TALLY_URL_BUSINESS_STRATEGY = env("EVKHA_TALLY_URL_BUSINESS_STRATEGY", default="")

# Brevo — email transactionnel de livraison (utilise quand EVKHA_USE_STUB_EMAIL=false).
BREVO_API_KEY = env("BREVO_API_KEY", default="")
BREVO_SENDER_EMAIL = env("BREVO_SENDER_EMAIL", default="contact@evkha.fr")
BREVO_SENDER_NAME = env("BREVO_SENDER_NAME", default="Evkha")

# Modele Claude actif pour la tarification du Cost Engine (M4).
# claude-sonnet : qualite optimale pour les analyses longues (80 pages). Les budgets
# adaptatifs (EM=4€, BP=3€) absorbent le cout Sonnet meme sur 30 appels.
EVKHA_CLAUDE_MODEL = env("EVKHA_CLAUDE_MODEL", default="claude-sonnet")
EVKHA_ANTHROPIC_MODEL_ID = env("EVKHA_ANTHROPIC_MODEL_ID", default="")

# Extended thinking : budget de reflexion accorde a CHAQUE appel de generation.
# Uniforme par construction — le basculer en cours de job invaliderait le cache
# du system prompt et des messages (doc « Prompt caching »), et re-paierait une
# ecriture de cache a 200 % a chaque bascule.
#
# 1024 = minimum impose par l'API, et le bon reglage ici : le besoin est un
# brouillon de calcul avant redaction (emboitement TAM/SAM/SOM, taux de
# capture), pas une demonstration longue. Cout : 1024 tokens x 0,0000135 EUR
# = 0,0138 EUR par appel, soit ~+0,41 EUR sur un job EM de 30 appels. Le budget
# EM a ete releve en consequence (cf. generation/services.py).
# Mettre 0 pour desactiver.
EVKHA_THINKING_BUDGET_TOKENS = env.int("EVKHA_THINKING_BUDGET_TOKENS", default=1024)

# Outil advisor (beta `advisor-tool-2026-03-01`) sur les CHECKs de bloc : le
# relecteur consulte un second relecteur qui relit toute la transcription avant
# le verdict. Executeur ET conseiller = claude-sonnet-4-6 ; la doc autorise
# cette paire (« les modeles de capacite egale peuvent se conseiller
# mutuellement ») et c'est ce qui garde le Cost Engine juste : un seul tarif.
#
# Cout : ~0,04 EUR par CHECK conseille (sous-inference du conseiller +
# relecture du contexte par l'executeur au tour suivant). Limite aux 5 blocs
# quantifies/transverses = ~0,22 EUR par EM, absorbe par le budget de 4,00 EUR.
# EVKHA_ADVISOR_BLOCS="*" etend a tous les CHECKs (~0,48 EUR : verifier la
# marge de retry avant). Chaine vide = aucun bloc.
# Indisponible sur Bedrock, Vertex et Foundry — API Claude directe uniquement.
EVKHA_ADVISOR_ENABLED = env.bool("EVKHA_ADVISOR_ENABLED", default=True)
EVKHA_ADVISOR_BLOCS = env("EVKHA_ADVISOR_BLOCS", default="A,F,G,I,J")
EVKHA_ADVISOR_MAX_TOKENS = env.int("EVKHA_ADVISOR_MAX_TOKENS", default=2048)

# Outil d'execution de code (`code_execution_20250825`, disponibilite generale,
# aucun en-tete beta) sur les SEULS chapitres qui le declarent dans leur
# blueprint — aujourd'hui le chapitre 2 EM, qui porte le calcul TAM/SAM/SOM.
#
# Pourquoi : le premier reproche d'Evangeline sur le run 010e3bf2 est « erreurs
# de calcul importantes ». Le chapitre 2 emboite un TAM, un SAM, un SOM a sept
# variables, un taux d'annulation et une montee en charge mensuelle — et le
# modele faisait cette arithmetique en prose. La doc designe exactement ce cas
# comme declencheur de l'outil : « Mathematiques non triviales (grands nombres,
# nombreuses etapes, resultats sensibles a la precision) ». Un interpreteur
# supprime cette classe de defaut ; aucune reformulation de prompt ne le fait.
#
# Cout : la doc accorde « 1 550 heures gratuites » par mois et par
# organisation, puis 0,05 $/h par conteneur, avec une facturation minimale de
# 5 minutes. Un conteneur par job EM = 0,083 h, soit ~18 600 jobs par mois
# avant le premier centime. Le cout REEL de la mesure est ailleurs : l'ajout
# d'un outil modifie le niveau `tools`, qui precede `system` dans la hierarchie
# de cache, donc le chapitre 2 re-ecrit son prefixe (~+0,01 EUR) au lieu de le
# relire a 10 %. C'est pour cela que la portee est un seul chapitre : les 20
# autres continuent de toucher l'entree de cache d'origine.
#
# Reseau completement desactive dans le conteneur : aucune donnee client n'en
# sort et aucune source ne peut y etre telechargee (les chiffres restent ceux
# du contexte). Indisponible sur Bedrock, Vertex et Foundry.
EVKHA_CODE_EXECUTION_ENABLED = env.bool("EVKHA_CODE_EXECUTION_ENABLED", default=True)

# Adaptateurs externes : stubs deterministes par defaut (dev/CI, aucun reseau).
# Passer a False en production une fois les credentials configures.
EVKHA_USE_STUB_AI = env("EVKHA_USE_STUB_AI")
EVKHA_USE_STUB_DOCS = env("EVKHA_USE_STUB_DOCS")
EVKHA_USE_STUB_GAMMA = env("EVKHA_USE_STUB_GAMMA")
EVKHA_USE_STUB_EMAIL = env("EVKHA_USE_STUB_EMAIL")
EVKHA_USE_STUB_PDF = env("EVKHA_USE_STUB_PDF")
EVKHA_USE_STUB_SEARCH = env("EVKHA_USE_STUB_SEARCH")

# Recherche web (ancrage anti-hallucination §6). Fournisseur GRATUIT par
# defaut (DuckDuckGo, sans cle) : pour l'activer, EVKHA_USE_STUB_SEARCH=false
# suffit (aucun cout, aucune inscription). Tavily reste une option payante
# activee UNIQUEMENT via EVKHA_SEARCH_PROVIDER=tavily + TAVILY_API_KEY.
EVKHA_SEARCH_PROVIDER = env("EVKHA_SEARCH_PROVIDER", default="duckduckgo")
TAVILY_API_KEY = env("TAVILY_API_KEY", default="")

# Socle de données verrouillé (lot 1 de la refonte du moteur).
#
# Faux par défaut : le moteur historique reste seul en service. Passer à true
# active la passe 1 (production du socle avant toute rédaction) pour les
# livrables couverts par un référentiel — aujourd'hui l'étude de marché et
# l'étude de la concurrence. Le business plan et la stratégie continuent de
# tourner sur l'ancien chemin quelle que soit la valeur de ce réglage.
#
# C'est le drapeau de bascule réversible exigé par le cahier des charges :
# le repasser à false rend le comportement d'avant, sans migration ni purge.
EVKHA_SOCLE_ENABLED = env.bool("EVKHA_SOCLE_ENABLED", default=False)

# Boucle d'auto-correction (concept loopy) : nombre de rondes de régénération
# ciblée des chapitres fautifs avant blocage du gate. 0 = désactivé (le gate
# bloque directement, comportement historique). Défaut 1 (borne le coût API).
EVKHA_CORRECTION_ROUNDS = env.int("EVKHA_CORRECTION_ROUNDS", default=1)

# Gamma — moteur de mise en page du livrable (Generations API v1.0).
# En prod : EVKHA_USE_STUB_GAMMA=false + GAMMA_API_KEY (+ GAMMA_THEME_ID
# optionnel). Le PDF Gamma devient l'artefact client principal quand l'offre
# a gamma_enabled ; WeasyPrint reste le repli.
GAMMA_API_KEY = env("GAMMA_API_KEY", default="")
GAMMA_THEME_ID = env("GAMMA_THEME_ID", default="")

# URL de base publique du serveur (utilisée par WeasyPrint et Brevo pour
# construire des URLs absolues valides pour les fichiers média).
# Exemple production : https://app.evkha.fr
EVKHA_BASE_URL = env("EVKHA_BASE_URL", default="http://localhost:8000")

# Dashboard auth (Phase 6).
# EVKHA_DASHBOARD_AUTH_DISABLED=true en dev/CI (defaut).
# En production : EVKHA_DASHBOARD_AUTH_DISABLED=false
#                  EVKHA_DASHBOARD_TOKEN=<openssl rand -hex 32>
# TODO: remplacer par JWT Better Auth quand BETTER_AUTH_SECRET est configure.
EVKHA_DASHBOARD_AUTH_DISABLED = env("EVKHA_DASHBOARD_AUTH_DISABLED")
EVKHA_DASHBOARD_TOKEN = env("EVKHA_DASHBOARD_TOKEN", default="")

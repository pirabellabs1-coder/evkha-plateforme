from __future__ import annotations

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    EVKHA_DEFAULT_RETENTION_DAYS=(int, 7),
    EVKHA_PIECES_JOINTES_RETENTION_DAYS=(int, 365),
    EVKHA_USE_STUB_AI=(bool, True),
    EVKHA_USE_STUB_DOCS=(bool, True),
    EVKHA_USE_STUB_GAMMA=(bool, True),
    EVKHA_USE_STUB_EMAIL=(bool, True),
    EVKHA_USE_STUB_PDF=(bool, True),
    EVKHA_USE_STUB_SEARCH=(bool, True),
    EVKHA_LIVRABLE_WORD=(bool, True),
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

# ── Taille des dépôts de fichiers ────────────────────────────────────────────
#
# DEUX PLAFONDS SE CONTREDISAIENT, et le plus bas n'était écrit nulle part.
#
# `organisations.fichiers.TAILLE_MAX_DOCUMENT` accepte 10 Mo — le plafond du
# formulaire Tally, repris à l'octet près. Mais Django refuse tout corps de
# requête au-delà de `DATA_UPLOAD_MAX_MEMORY_SIZE`, dont le défaut vaut
# 2,5 Mo, et il le refuse AVANT que la vue ne s'exécute : la validation
# applicative n'était jamais atteinte.
#
# Constaté le 09/08/2026 : un fichier de 3,5 Mo « ne s'ajoutait pas », sans
# message exploitable. L'application annonçait 10 Mo, le cadre coupait à 2,5.
#
# On dérive donc les deux réglages de la MÊME constante (règle 5), avec une
# marge pour l'enveloppe multipart — les en-têtes et les frontières de parties
# s'ajoutent au fichier lui-même, et un fichier de 10,0 Mo pile serait refusé
# sans elle.
from organisations.fichiers import TAILLE_MAX_DOCUMENT  # noqa: E402

_MARGE_MULTIPART = 1 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = TAILLE_MAX_DOCUMENT + _MARGE_MULTIPART
FILE_UPLOAD_MAX_MEMORY_SIZE = DATA_UPLOAD_MAX_MEMORY_SIZE
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
    # Purge des fichiers DEPOSES par le client (bilans, comptes de resultat).
    # Distincte de la purge des artefacts : celle-ci ne touchait que ce que
    # NOUS produisons, et les depots des clients n'expiraient jamais.
    # Retention 12 mois, comptee depuis le depot ; les logos sont exclus.
    "purger-les-pieces-jointes": {
        "task": "organisations.purger_les_pieces_jointes",
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

# Fichiers DÉPOSÉS par le client (bilans, comptes de résultat). Douze mois : le
# cycle d'un bilan. Distinct de la rétention des livrables — voir
# `evkha/retention.py`, qui explique pourquoi les confondre serait faux.
EVKHA_PIECES_JOINTES_RETENTION_DAYS = env("EVKHA_PIECES_JOINTES_RETENTION_DAYS")

# Webhook shared secrets (M1).
SYSTEME_WEBHOOK_SECRET = env("SYSTEME_WEBHOOK_SECRET", default="")
TALLY_WEBHOOK_SECRET = env("TALLY_WEBHOOK_SECRET", default="")

# Stripe — encaissement des abonnements B2B.
#
# Ces deux valeurs vivent dans Coolify, jamais dans le depot. Le defaut vide
# n'est pas une permission : `paiement/stripe_api.py` REFUSE de fonctionner
# sans elles, et le webhook refuse tout evenement. C'est deliberement l'inverse
# de `SYSTEME_WEBHOOK_SECRET`, dont l'absence laisse passer (`is_webhook_
# authorized` est fail-open) — tolerable pour un webhook qui n'a longtemps rien
# credite dans l'espace client, inacceptable pour celui qui ouvre l'acces.
#
# STRIPE_SECRET_KEY   : cle secrete (sk_test_… en recette, sk_live_… en reel).
# STRIPE_WEBHOOK_SECRET : secret de signature du point de terminaison (whsec_…),
#                         propre a CHAQUE point de terminaison Stripe. Celui de
#                         la recette ne valide pas les evenements du reel.
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")

# URLs Tally par type de livrable (envoyees dans les emails de tickets de credit).
# Configurees en prod via env. Chaque URL recoit ?order_id=<ticket_id> en query.
EVKHA_TALLY_URL_MARKET_STUDY = env("EVKHA_TALLY_URL_MARKET_STUDY", default="")
EVKHA_TALLY_URL_COMPETITOR_STUDY = env("EVKHA_TALLY_URL_COMPETITOR_STUDY", default="")
EVKHA_TALLY_URL_BUSINESS_PLAN = env("EVKHA_TALLY_URL_BUSINESS_PLAN", default="")
EVKHA_TALLY_URL_BUSINESS_STRATEGY = env("EVKHA_TALLY_URL_BUSINESS_STRATEGY", default="")

# Courriel transactionnel (utilise quand EVKHA_USE_STUB_EMAIL=false).
#
# Deux fournisseurs possibles derriere le meme protocole. `resend` est celui
# retenu par la cliente ; `brevo` reste branchable sans redeploiement, ce qui
# evite d'avoir a rouvrir le code un soir de panne de fournisseur.
EVKHA_EMAIL_PROVIDER = env("EVKHA_EMAIL_PROVIDER", default="resend")

# L'expediteur ne depend PAS du fournisseur : c'est l'adresse d'EVKHA, et elle
# doit rester la meme si l'on bascule de l'un a l'autre. Les reglages `BREVO_*`
# servent de repli pour ne pas casser une installation qui les portait deja.
EVKHA_SENDER_EMAIL = env(
    "EVKHA_SENDER_EMAIL", default=env("BREVO_SENDER_EMAIL", default="contact@evkha.fr")
)
EVKHA_SENDER_NAME = env(
    "EVKHA_SENDER_NAME", default=env("BREVO_SENDER_NAME", default="Evkha")
)

#: Adresse qui recoit une copie CACHEE de tout courriel transactionnel.
#:
#: La cliente veut voir passer ce qui part a ses partenaires — invitations,
#: liens de mot de passe, livraisons, relances — sans que le destinataire
#: l'apprenne. Vide, aucune copie n'est envoyee : c'est un choix explicite, pas
#: un defaut. Une adresse mise ici recevra TOUT, y compris des liens
#: personnels : la remplir est une decision.
EVKHA_COPIE_COURRIEL = env("EVKHA_COPIE_COURRIEL", default="")

RESEND_API_KEY = env("RESEND_API_KEY", default="")
BREVO_API_KEY = env("BREVO_API_KEY", default="")

# Pas de `BREVO_SENDER_EMAIL` ni de `BREVO_SENDER_NAME` : les deux clients
# lisent `EVKHA_SENDER_*`. Les avoir gardes en copie a l'egal aurait fait deux
# variables pour une seule verite — et une copie prise au CHARGEMENT, donc
# muette a toute modification ulterieure. Le repli sur les anciens noms est
# assure plus haut, a la lecture de l'environnement, la ou il a un sens.

# Modele Claude actif pour la tarification du Cost Engine (M4).
# claude-sonnet : qualite optimale pour les analyses longues (80 pages). Les budgets
# adaptatifs (EM=4€, BP=3€) absorbent le cout Sonnet meme sur 30 appels.
EVKHA_CLAUDE_MODEL = env("EVKHA_CLAUDE_MODEL", default="claude-sonnet")
EVKHA_ANTHROPIC_MODEL_ID = env("EVKHA_ANTHROPIC_MODEL_ID", default="")

# Reflexion adaptative : PROVISION de reflexion reservee a CHAQUE appel de
# generation. Depuis le passage aux modeles recents, ce nombre n'est plus
# transmis a l'API — `thinking.budget_tokens` y a ete supprime et renvoie 400.
# Il sert desormais de reserve interne (cf. `_provision_reflexion` dans
# integrations/claude.py) : place gardee dans max_tokens, et euros provisionnes
# par le throttle.
#
# Uniforme par construction — le basculer en cours de job invaliderait le cache
# du system prompt et des messages (doc « Prompt caching »), et re-paierait une
# ecriture de cache a 200 % a chaque bascule.
#
# 1024 reste le bon ordre de grandeur : le besoin est un brouillon de calcul
# avant redaction (emboitement TAM/SAM/SOM, taux de capture), pas une
# demonstration longue. Cout : 1024 tokens x 0,0000135 EUR = 0,0138 EUR par
# appel, soit ~+0,41 EUR sur un job EM de 30 appels. Les budgets par livrable
# sont dimensionnes en consequence (cf. generation/services.py).
# Mettre 0 pour desactiver la reflexion.
EVKHA_THINKING_BUDGET_TOKENS = env.int("EVKHA_THINKING_BUDGET_TOKENS", default=1024)

# Profondeur de la reflexion adaptative, envoyee en `output_config.effort`.
# Valeurs : low | medium | high | max (xhigh existe sur la famille Opus recente,
# pas sur Sonnet 4.6). « high » est le defaut de l'API et le reglage retenu ici :
# les chapitres quantifies (TAM/SAM/SOM, previsionnel) sont le genre de travail
# ou la profondeur se voit. Descendre a « medium » est le levier d'economie a
# actionner avant de couper la reflexion tout court.
EVKHA_CLAUDE_EFFORT = env("EVKHA_CLAUDE_EFFORT", default="high")

# FREIN D'URGENCE GLOBAL, vide par defaut. Pose, il plafonne TOUS les livrables
# a la meme valeur, sans redeploiement — on le tire sans se demander quel type
# de dossier tourne.
#
# Il portait un defaut de « 3.10 » jusqu'au 08/08/2026, et ce defaut le rendait
# TOUJOURS actif : le plafond par livrable de `cost.PLAFOND_PAR_LIVRABLE`
# n'etait jamais atteint, et une etude de marche annoncee a 4,00 EUR etait en
# realite coupee a 3,10. Un frein d'urgence serre en permanence n'est plus un
# frein d'urgence, c'est le plafond — et il masquait celui qu'on croyait lire.
#
# Vide = la table par livrable s'applique. C'est elle qui fait foi.
EVKHA_PLAFOND_DEPENSE_EUR = env("EVKHA_PLAFOND_DEPENSE_EUR", default="")

# Plafond de mots par section a l'assemblage du Word. 0 = aucune coupe.
# Au-dela, la prose de la section est ramenee a une amorce, sur une frontiere
# de phrase.
#
# Le modele valide par la cliente est un STANDARD, pas un plafond : un client
# dont le besoin est plus large doit recevoir DAVANTAGE, pas la meme chose
# tronquee. L'ancienne valeur, 90, avait ete calibree pour reproduire le volume
# de prose du modele — 90 mots x ~50 sections ~= 4 500 — donc pour ne jamais le
# depasser. 150 laisse a une section la place d'une analyse developpee, ce que
# les cahiers des charges Strategie et Concurrence exigent explicitement
# (« les paragraphes doivent etre rediges »).
#
# Le garde-fou contre le mur de texte n'a pas disparu : il vit en aval, dans
# `verification/controles.py`, qui mesure sur le FICHIER rendu la part des
# tableaux, la mediane des paragraphes et la part des paragraphes longs — trois
# seuils releves sur le modele et valides par la cliente. Relever ce plafond
# deplace donc le curseur vers ces trois seuils : a remesurer sur un dossier
# reel avant de monter plus haut (regle 7).
EVKHA_MOTS_PARAGRAPHE_MAX = env.int("EVKHA_MOTS_PARAGRAPHE_MAX", default=150)

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

# Identifiant OAuth de l'application Google, pour « Continuer avec Google ».
# PUBLIC par construction : le navigateur l'envoie a Google. Le secret OAuth
# n'est pas necessaire — le navigateur obtient le jeton d'identite, le serveur
# se contente de le verifier (voir organisations/google.py).
#
# Vide = la connexion Google est desactivee, et le bouton ne s'affiche PAS.
# Un bouton qui echoue faute de reglage est pire que pas de bouton.
EVKHA_GOOGLE_CLIENT_ID = env("EVKHA_GOOGLE_CLIENT_ID", default="")
EVKHA_USE_STUB_DOCS = env("EVKHA_USE_STUB_DOCS")
EVKHA_USE_STUB_GAMMA = env("EVKHA_USE_STUB_GAMMA")
EVKHA_USE_STUB_EMAIL = env("EVKHA_USE_STUB_EMAIL")
EVKHA_USE_STUB_PDF = env("EVKHA_USE_STUB_PDF")
EVKHA_USE_STUB_SEARCH = env("EVKHA_USE_STUB_SEARCH")

# Chaîne de rendu du livrable client.
#
# `True`  : Word d'abord, PDF converti DEPUIS le Word — le format du lot 3, avec
#           ses graphiques sectoriels et ses contrôles de cohérence.
# `False` : ancienne chaîne, aperçu HTML et PDF WeasyPrint.
#
# Un indicateur et non un remplacement pur : le §16 exige que le basculement
# soit « réversible immédiatement ». Repasser à `false` dans Coolify suffit à
# revenir à la chaîne éprouvée, sans redéployer de code.
EVKHA_LIVRABLE_WORD = env("EVKHA_LIVRABLE_WORD")

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
# livrables couverts par un référentiel — **les quatre depuis le 06/08/2026**,
# business plan et stratégie compris. Ce commentaire nommait encore les deux
# seules études, et un inventaire du 08/08/2026 en a conclu qu'il restait une
# migration à faire. La liste qui fait foi est `_PAR_LIVRABLE`, dans
# `generation/socle/referentiel.py` — ne pas la recopier ici.
#
# C'est le drapeau de bascule réversible exigé par le cahier des charges :
# le repasser à false rend le comportement d'avant, sans migration ni purge.
EVKHA_SOCLE_ENABLED = env.bool("EVKHA_SOCLE_ENABLED", default=False)

# Boucle d'auto-correction (concept loopy) : nombre de rondes de régénération
# ciblée des chapitres fautifs avant blocage du gate. 0 = désactivé (le gate
# bloque directement, comportement historique).
#
# TROIS depuis le 12/08/2026, décision cliente, sur une mesure.
#
# Une seule ronde laissait sur la table ce qui était réparable. Business plan
# `5c5e91b9` : neuf motifs restants, dont six libellés financiers qui se
# contredisent d'un chapitre à l'autre — un investissement total à 68 000,
# 1 400 puis 85 000 €. Choisir une valeur et la propager est exactement ce que
# cette boucle sait faire ; elle n'en avait pas le droit.
#
# Le coût reste borné par le PLAFOND du livrable (`cost.plafond_de_depense`),
# pas par ce nombre : une ronde qui ferait dépasser s'arrête d'elle-même. Ce
# réglage autorise, il ne dépense pas.
#
# CE QU'AUCUNE RONDE NE RÉPARERA : `reference_client_illisible`. Quand le brief
# ne donne aucun montant, le rédacteur invente — et trois rondes de plus le
# feraient inventer de façon COHÉRENTE, ce qui est pire : un dossier bancaire
# plausible et invérifiable au lieu d'un dossier qui signale son propre
# problème. Ce motif désigne une action humaine, et il reste bloquant.
EVKHA_CORRECTION_ROUNDS = env.int("EVKHA_CORRECTION_ROUNDS", default=3)

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

# Adresse de l'ESPACE CLIENT (le front), distincte de celle de l'API.
#
# Les liens d'invitation et de reinitialisation de mot de passe menent a des
# pages du front — `/definir-mot-de-passe`, `/mot-de-passe-oublie`. Ils etaient
# construits sur EVKHA_BASE_URL, qui designe l'API : en production, chaque
# invitation envoyait donc l'invite sur un 404, et la fonctionnalite Equipe
# etait inutilisable alors qu'elle etait livree et testee.
#
# Sans valeur, `evkha.C004` refuse hors DEBUG : un lien qui ne mene nulle part
# est pire qu'une invitation qui n'est pas partie, parce qu'il a l'air d'avoir
# marche (regle 1).
EVKHA_APP_URL = env("EVKHA_APP_URL", default="")

# Dashboard auth (Phase 6).
# EVKHA_DASHBOARD_AUTH_DISABLED=true en dev/CI (defaut).
# En production : EVKHA_DASHBOARD_AUTH_DISABLED=false
#                  EVKHA_DASHBOARD_TOKEN=<openssl rand -hex 32>
# TODO: remplacer par JWT Better Auth quand BETTER_AUTH_SECRET est configure.
EVKHA_DASHBOARD_AUTH_DISABLED = env("EVKHA_DASHBOARD_AUTH_DISABLED")
EVKHA_DASHBOARD_TOKEN = env("EVKHA_DASHBOARD_TOKEN", default="")
# Jeton PRECEDENT, accepte le temps d'une rotation. Un secret qu'on ne peut pas
# changer sans coupure ne se change jamais : avec un jeton unique, tourner la
# cle casse tous les appelants a la seconde du deploiement, donc on repousse.
# Manoeuvre : poser l'ancienne valeur ici, la nouvelle au-dessus, deployer,
# mettre les appelants a jour, puis VIDER cette variable. `evkha.W007` la
# rappelle tant qu'elle est posee, pour qu'une fenetre de rotation ne devienne
# pas un etat permanent.
EVKHA_DASHBOARD_TOKEN_PRECEDENT = env("EVKHA_DASHBOARD_TOKEN_PRECEDENT", default="")

# ── Cache ────────────────────────────────────────────────────────────────────
#
# Il n'y en avait AUCUN de declare. Django retombait donc sur LocMemCache, un
# dictionnaire LOCAL AU PROCESSUS — et la production tourne
# `gunicorn --workers 2`. Les plafonds de tentatives d'organisations/limitation.py
# s'appuient entierement sur `django.core.cache` : chaque worker tenait son
# propre compteur, si bien que le plafond annonce « 10 essais par quart d'heure »
# en autorisait 20, et repartait de zero a chaque redeploiement.
#
# La protection existait dans le code, se lisait, se testait — et ne comptait
# pas ce qu'elle pretendait compter (regle 1). Les tests ne pouvaient pas le
# voir : ils tournent dans un seul processus (regle 7).
#
# Redis est deja la pour Celery. On prend une base DISTINCTE de celle du
# courtier : melanger des cles de cache et une file de taches expose a ce qu'un
# `clear()` du cache efface des taches en attente.
#
# L'adresse est DEDUITE du courtier Celery quand elle n'est pas fournie. Poser
# une variable de plus obligerait a s'en souvenir sur chaque environnement, et
# un oubli ferait echouer `evkha.C001` au demarrage — donc casserait le
# deploiement pour un reglage que le systeme pouvait deduire seul.
#
# On ne deduit QUE si le courtier est bien un Redis : si quelqu'un passe un
# jour a RabbitMQ, mieux vaut retomber sur le cache local et se faire refuser
# bruyamment par le controle que fabriquer une adresse qui ne repond pas.
#
# Le courtier se lit dans `CELERY_BROKER_URL` calcule plus haut, PAS par un
# second `env(...)`. La deduction relisait la variable d'environnement avec un
# repli different (`""` contre `redis://localhost:6379/0`) : deux lectures de
# la meme verite, qui se contredisaient des que la variable n'etait pas posee.
# Les reglages affirmaient alors que le courtier est un Redis pendant que la
# deduction affirmait qu'il n'y en a pas, et le cache retombait en LocMem.
# C'est la regle 5, et elle rendait `test_l_adresse_du_cache_est_deduite_du_
# courtier` rouge sur tout environnement sans `.env` — un poste neuf, la CI,
# l'image Docker.
def _cache_deduit_du_courtier() -> str:
    courtier = str(CELERY_BROKER_URL)
    if not courtier.startswith(("redis://", "rediss://")):
        return ""
    base, _, _ = courtier.rpartition("/")
    return f"{base}/1" if base else ""


EVKHA_CACHE_URL = env("EVKHA_CACHE_URL", default="") or _cache_deduit_du_courtier()

if EVKHA_CACHE_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": EVKHA_CACHE_URL,
        }
    }
else:
    # Developpement et tests : un cache local suffit, un seul processus tourne.
    # En production ce repli est REFUSE par le controle `evkha.C001` — voir
    # organisations/checks.py. Se taire ici rendrait la faille invisible.
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "evkha-local",
        }
    }

# Nombre de relais de confiance devant l'application. Sert a lire l'adresse
# d'origine sans qu'un appelant puisse la choisir — voir organisations/limitation.py.
#
# 1 en production : Traefik, pose par Coolify, ajoute la vraie adresse a droite
# de X-Forwarded-For. 0 quand le serveur est joint directement, sinon l'en-tete
# serait cru sur parole et tous les plafonds de tentatives sauteraient.
EVKHA_PROXIES_DE_CONFIANCE = env.int("EVKHA_PROXIES_DE_CONFIANCE", default=1)

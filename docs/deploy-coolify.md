# Guide de déploiement — VPS IONOS + Coolify

Cible : VPS IONOS L (2 vCPU · 4 GB RAM · Ubuntu 24.04 LTS)
Domaine : evkha.fr (DNS déjà chez IONOS)

---

## Couche 1 — Première connexion SSH

```bash
# Depuis Termius ou terminal local
ssh root@<IP_VPS>

# Mettre à jour le système
apt update && apt upgrade -y
```

---

## Couche 2 — Installation Coolify

```bash
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

Coolify s'installe avec Docker, Docker Compose et un reverse proxy Traefik.
Attendre ~3 minutes. À la fin :

```
Coolify is ready! Open http://<IP_VPS>:8000 in your browser.
```

Ouvrir `http://<IP_VPS>:8000` → créer le compte admin → valider l'email.

---

## Couche 3 — DNS evkha.fr → VPS

Dans le panneau IONOS (domaines) :

| Type | Nom | Valeur | TTL |
|---|---|---|---|
| A | `@` | `<IP_VPS>` | 3600 |
| A | `www` | `<IP_VPS>` | 3600 |

Attendre la propagation (15-60 min). Vérifier :

```bash
dig evkha.fr +short
# doit retourner <IP_VPS>
```

---

## Couche 4 — Déploiement depuis GitHub

### 4.1 Connecter le repo GitHub

Dans Coolify → **Sources** → **Add Source** → GitHub → Autoriser l'accès au repo privé `Systeme-EVKHA-`.

### 4.2 Créer le service Django (API)

**New Resource** → **Docker Compose** → choisir le repo → branche `main`
→ **Compose file** : `docker-compose.prod.yml` (déjà dans le repo).

Puis dans l'UI Coolify, définir le domaine `evkha.fr` sur le service `api`
(port 8000) — Coolify/Traefik génère le certificat Let's Encrypt et route
le trafic automatiquement.

### 4.3 Variables d'environnement

Dans Coolify → service → **Environment Variables** → ajouter :

```env
# --- Django ---
DJANGO_SECRET_KEY=<générer avec : python -c "import secrets; print(secrets.token_hex(50))">
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=evkha.fr,www.evkha.fr

# --- Proxy Traefik (TLS terminé par Coolify) — requis pour /admin/ en HTTPS ---
EVKHA_BEHIND_PROXY=true
CSRF_TRUSTED_ORIGINS=https://evkha.fr,https://www.evkha.fr

# --- Base de données (host = nom du service compose : postgres) ---
POSTGRES_PASSWORD=<mot_de_passe_fort>
DATABASE_URL=postgres://evkha:<même_mot_de_passe>@postgres:5432/evkha

# --- Celery / Redis ---
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# --- IA ---
EVKHA_USE_STUB_AI=false
ANTHROPIC_API_KEY=<clé Anthropic dédiée au projet>

# --- PDF (WeasyPrint — deps système déjà dans le Dockerfile) ---
EVKHA_USE_STUB_PDF=false

# --- Gamma : laisser le stub (client réel non câblé ; offres gamma_enabled=false) ---
EVKHA_USE_STUB_GAMMA=true

# --- Email Brevo (API transactionnelle v3 — client réel implémenté) ---
EVKHA_USE_STUB_EMAIL=false
BREVO_API_KEY=<clé Brevo>
BREVO_SENDER_EMAIL=contact@evkha.fr
BREVO_SENDER_NAME=Evkha

# --- Webhooks secrets (openssl rand -hex 32) ---
SYSTEME_WEBHOOK_SECRET=<générer>
TALLY_WEBHOOK_SECRET=<générer>

# --- Dashboard (Phase 6) ---
EVKHA_DASHBOARD_AUTH_DISABLED=false
EVKHA_DASHBOARD_TOKEN=<openssl rand -hex 32>

# --- URL publique (liens PDF envoyés par Brevo, pièces jointes par URL) ---
EVKHA_BASE_URL=https://evkha.fr
```

---

## Couche 5 — docker-compose.prod.yml (déjà dans le repo)

Le fichier `docker-compose.prod.yml` à la racine du repo définit les
5 services de production :

| Service | Rôle |
|---|---|
| `api` | Gunicorn (2 workers) — `migrate` + `collectstatic` au démarrage |
| `worker` | Celery (génération Claude, PDF WeasyPrint, livraison Brevo) |
| `beat` | Celery beat (purge des artefacts expirés — rétention 7 j) |
| `postgres` | PostgreSQL 16 (volume `pgdata`, pas de port exposé) |
| `redis` | Broker Celery (volume `redisdata`, pas de port exposé) |

Points importants :
- Le volume `media` est **partagé** entre `api` et `worker` : le worker écrit
  les PDFs, l'api les sert sur `/media/`.
- n8n n'est pas déployé : l'orchestration est entièrement portée par Celery
  (les webhooks Systeme.io/Tally arrivent directement sur Django).
- `docker-compose.yml` (sans suffixe) reste le compose de **dev local**.

---

## Couche 6 — Première mise en production

Les migrations et `collectstatic` s'exécutent automatiquement au démarrage
du conteneur `api`. Il reste deux commandes à lancer une seule fois :

```bash
# Accéder au conteneur API
docker exec -it <nom_conteneur_api> bash

# Charger le catalogue des offres B2C (4 offres)
python manage.py loaddata initial_offers

# Créer le superadmin Django
python manage.py createsuperuser
# → email : contact@evkha.fr
# → mot de passe : choisir un mot de passe fort

# Vérifier l'état
python manage.py check --deploy
```

---

## Couche 7 — Configurer Systeme.io webhooks

Une fois le VPS en ligne et `https://evkha.fr` accessible :

| Événement Systeme.io | URL |
|---|---|
| Commandes B2C (order.completed) | `https://evkha.fr/webhooks/systeme/order/` |
| Abonnements B2B (subscription.*) | `https://evkha.fr/webhooks/systeme/subscription/` |
| Formulaires Tally | `https://evkha.fr/webhooks/tally/intake/` |

Dans Systeme.io → **Paramètres** → **Webhooks** → ajouter chaque URL avec le secret configuré dans `SYSTEME_WEBHOOK_SECRET`.

---

## Couche 8 — Surveillance (Uptime Kuma)

Uptime Kuma est inclus dans Coolify. Ajouter ces moniteurs :

| URL | Type | Intervalle |
|---|---|---|
| `https://evkha.fr/healthz/` | HTTP | 60s |
| `https://evkha.fr/admin/` | HTTP | 5min |
| `https://evkha.fr/webhooks/systeme/order/` | HTTP (HEAD) | 5min |

---

## Commandes utiles post-déploiement

```bash
# Voir les logs en temps réel
docker logs <nom_conteneur_api> -f

# Voir les tâches Celery
docker logs <nom_conteneur_worker> -f

# Relancer un déploiement depuis Coolify
# → Dashboard Coolify → service → Deploy

# Accéder à l'admin Django
# https://evkha.fr/admin/
```

---

## Checklist finale avant ouverture clients

- [ ] `https://evkha.fr/healthz/` répond `{"status": "ok"}`
- [ ] `https://evkha.fr/admin/` accessible avec le superadmin
- [ ] 4 offres B2C chargées (visible dans Admin → Catalog → Offers)
- [ ] Test webhook Systeme.io (commande test depuis Systeme.io)
- [ ] Test webhook Tally (soumission test)
- [ ] Email Brevo fonctionnel (test depuis Admin Django ou pipeline)
- [ ] Certificat HTTPS valide (Let's Encrypt via Traefik/Coolify)
- [ ] Uptime Kuma actif sur les 3 endpoints

---

## L'interface Coolify elle-même est en HTTP clair — à traiter

Vérifié le 08/08/2026 : `https://82.165.31.105:8000` refuse la connexion TLS,
`http://82.165.31.105:8000/api/v1/version` répond `200`. Le panneau
d'administration **et son API** ne sont donc joignables qu'en clair.

Ce n'est pas le même sujet que les certificats des applications : Traefik pose
bien du HTTPS sur `api2.evkha.fr` et `app2.evkha.fr`. C'est Coolify lui-même,
sur le port 8000, qui est en dehors de ce dispositif.

**Ce que cela expose.** Chaque appel à cette API transporte un jeton porteur qui
donne le droit de déclencher un déploiement, de lire et d'écrire toutes les
variables d'environnement — donc les clés Anthropic et Stripe, le mot de passe
PostgreSQL, les secrets de webhook. En clair sur le réseau, ce jeton est lisible
par quiconque se trouve sur le chemin.

**Ce qu'il faut faire, et c'est côté serveur — pas côté dépôt :**

1. Poser un nom de domaine sur l'instance Coolify (par exemple
   `coolify.evkha.fr`) dans ses propres réglages : Coolify sait alors demander
   son certificat Let's Encrypt comme il le fait pour les applications.
2. Fermer le port `8000` au monde une fois le domaine en service — le laisser
   ouvert annule le bénéfice, puisque l'accès clair reste possible.
3. Faire tourner le jeton d'API après la bascule : celui en service a circulé
   en clair, il doit être considéré comme connu.

Tant que ce n'est pas fait, ne pas appeler cette API depuis un réseau qu'on ne
maîtrise pas.

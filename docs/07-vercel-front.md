# Vercel — hébergement du front, et ce qui ne peut pas y aller

## 1. Ce qui est livré

| Élément | Fichier |
|---|---|
| Configuration de déploiement Vercel | `frontend/vercel.json` |
| Variables d'environnement documentées | `frontend/.env.example` |
| CORS de l'API | `backend/evkha/settings.py` |
| Tests du CORS | `backend/tests/test_cors_vercel.py` |

Le front se déploie sur Vercel en l'état : `framework: vite`, sortie `dist`,
réécriture de toutes les routes vers `index.html` (l'application utilise
TanStack Router côté client, sans quoi un rafraîchissement sur `/jobs` rendrait
un 404).

### Le point qui aurait cassé au premier déploiement

`django-cors-headers` n'était **pas installé** et aucun réglage CORS n'existait.
Le front et l'API vivant désormais sur deux domaines, le navigateur aurait
bloqué chaque appel. C'est corrigé, avec quatre garde-fous testés :

- `CORS_ALLOW_CREDENTIALS = False` — l'authentification passe par un jeton dans
  l'en-tête `Authorization` (`dashboard/middleware.py`), jamais par un cookie.
  Autoriser les identifiants ferait envoyer le cookie de session vers un autre
  domaine sans qu'aucun code ne le demande.
- `CORS_URLS_REGEX` limité à `/api/` et `/webhooks/` — l'administration Django
  n'a rien à exposer à un autre domaine.
- Le middleware CORS est placé **avant** `CommonMiddleware` : une requête
  préflight `OPTIONS` ne porte pas de jeton, et un middleware
  d'authentification placé avant lui la rejetterait en 401. Le navigateur
  concluerait au blocage sans jamais émettre la vraie requête. Un test couvre
  ce cas précis, authentification active.
- Le motif `*.vercel.app` (nécessaire aux déploiements de prévisualisation, dont
  le domaine change à chaque branche) est **désactivé par défaut**, et un test
  échoue si quelqu'un l'active dans les réglages livrés : il autoriserait
  n'importe quel site hébergé sur `vercel.app` à lire les réponses de l'API pour
  un porteur de jeton valide.

Réglages à poser côté hébergeur, jamais dans le dépôt :

```
CORS_ALLOWED_ORIGINS=https://app.evkha.fr,https://evkha.vercel.app
CSRF_TRUSTED_ORIGINS=https://app.evkha.fr
```

Et dans les variables d'environnement du projet Vercel :

```
VITE_API_URL=https://api.evkha.fr
```

> Les variables `VITE_*` sont inscrites **en clair** dans le paquet JavaScript
> envoyé au navigateur. Aucun secret ne doit y figurer.

---

## 2. Migrer la totalité sur Vercel : ce que cela suppose

La demande était de tout migrer. Voici précisément ce qui s'y oppose, service
par service. Ce ne sont pas des préférences d'architecture mais des limites de
la plateforme.

| Composant | Obstacle sur Vercel | Ce qu'il faudrait |
|---|---|---|
| **Workers Celery** | Vercel n'exécute aucun processus permanent. Une fonction est plafonnée à 300 s (Pro). Une étude de 22 chapitres demande des dizaines de minutes. | Réécrire l'orchestration en file de messages externe (QStash, Inngest) avec une fonction par chapitre. Le lot 2 — reprise sur échec, temporisation croissante, régénération unitaire — serait à reconstruire. |
| **Celery beat** | Pas de planificateur permanent. | Vercel Cron (déclenche du HTTP, granularité la minute). Les trois tâches périodiques existantes sont adaptables. |
| **Redis** | Pas de service hébergeable. | Upstash ou équivalent, payant, hors du VPS. |
| **PostgreSQL** | Pas de base hébergeable. | Neon, Supabase ou équivalent. Migration des données de production. |
| **LibreOffice** | Paquet système de plusieurs centaines de mégaoctets. Une fonction Vercel est plafonnée à 250 Mo décompressés. | **Aucune solution.** La conversion Word → PDF du lot 3 devient impossible ; il faudrait un service de conversion externe ou garder une machine à part. |
| **`MEDIA_ROOT`** | Système de fichiers non persistant. Les `.docx` et `.pdf` produits disparaîtraient. | Stockage objet (S3, R2, Vercel Blob) et réécriture de la chaîne d'artefacts. |
| **Django** | Déployable en fonction WSGI, mais démarrage à froid à chaque requête inactive. | Adaptation de l'entrée WSGI, et acceptation de la latence de démarrage. |

Deux conséquences à peser, indépendamment du coût :

1. **Le cahier des charges met l'hébergement hors périmètre** (§02 : « Le
   serveur, la base de données et leur hébergement, conservés en l'état ») et
   exige une file de tâches rejouable (§14). Une migration complète sort du
   périmètre contractuel et ferait l'objet d'un avenant (§18).
2. **Les lots 1 à 3 viennent d'être validés.** La reprise sur échec, la
   régénération unitaire et la conversion PDF reposent toutes sur le modèle
   worker permanent. Les réécrire ferait perdre ce qui vient d'être accepté,
   sans gain fonctionnel pour le client final.

### Le découpage qui donne le bénéfice de Vercel sans ce coût

```
Vercel                          VPS / Coolify
──────                          ─────────────
Front React (Vite)   ──HTTPS──►  API Django
CDN mondial                      Workers Celery + Redis
Déploiement par push             PostgreSQL
Prévisualisation par branche     LibreOffice
                                 Documents produits
```

Le front gagne le CDN, les déploiements par branche et les prévisualisations.
Le moteur garde ce qui exige un processus permanent. C'est ce qui est en place
à l'issue de cette étape.

---

## 3. Ce qui reste à faire côté hébergement

- Retirer `frontend/Dockerfile` et `frontend/nginx.conf` **une fois** le
  déploiement Vercel confirmé en ligne. Ils sont conservés tant que la bascule
  n'est pas faite : les supprimer avant priverait d'un retour en arrière.
- Brancher le domaine (`app.evkha.fr`) sur le projet Vercel et poser les deux
  variables `CORS_ALLOWED_ORIGINS` et `VITE_API_URL`.
- Vérifier le téléchargement d'un livrable depuis le domaine Vercel : les
  fichiers sont servis par `/media/` sur le VPS, donc soumis au même CORS.

---

## 4. Vérification

```bash
cd frontend && npm run build     # dist/ produit, 3,1 s
ruff check .                     # 42, inchangé
mypy backend                     # 102 erreurs dans 16 fichiers, inchangé
pytest                           # vert — 7 tests CORS ajoutés
python manage.py makemigrations --check --dry-run   # No changes detected
```

Le CORS n'a **pas** été vérifié depuis un vrai navigateur sur un vrai domaine
Vercel : les tests portent sur les en-têtes rendus par Django, ce qui est la
bonne mesure, mais la preuve définitive est un premier déploiement (règle 7).

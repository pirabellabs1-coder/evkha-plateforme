# Phase 6 — Dashboard EVKHA (TanStack Router + React Query)

Interface de supervision pour Evangeline : livrables en cours, couts
IA, incidents operationnels. Aucune base de donnees supplementaire
(lecture seule sur le PostgreSQL existant via l'API Django).

## Architecture

```
[TanStack Router + React Query]   →   [API Django /api/dashboard/]
     frontend/                              backend/dashboard/
     (Vite, port 5173)                      (vues JSON legeres)
```

## Endpoints Django (`backend/dashboard/`)

| Methode | URL | Description |
|---|---|---|
| GET | `/api/dashboard/overview/` | Metriques globales (jobs, cout 30j, incidents) |
| GET | `/api/dashboard/jobs/` | Liste 50 jobs recents, filtrable `?status=` |
| GET | `/api/dashboard/jobs/:id/` | Detail job + chapitres (tokens, cout, erreur) |
| GET | `/api/dashboard/incidents/` | 50 incidents recents |

## Frontend (`frontend/`)

| Fichier | Role |
|---|---|
| `src/api.ts` | Client HTTP + types TypeScript |
| `src/router.tsx` | TanStack Router, layout sidebar + 4 routes |
| `src/pages/Dashboard.tsx` | Stat cards (livrables, cout, incidents) |
| `src/pages/Jobs.tsx` | Table filtrable + barre de progression chapitres |
| `src/pages/JobDetail.tsx` | Tableau chapitres (statut/tokens/cout), refresh auto si running |
| `src/pages/Incidents.tsx` | Incidents ouverts + resolus, lien vers le job |
| `src/index.css` | Palette EVKHA (ivory/slate/clay/olive), design system minimaliste |

## Dev local

```bash
cd frontend && npm install && npm run dev
# → http://localhost:5173 (proxy /api → http://localhost:8000)
```

## Docker Compose

Service `dashboard` : Node 24-alpine, mount `./frontend`, port 5173.
Depends on `web` (Django). Aucune modification des autres services.

## Reste (production)

- **Better Auth** : ajouter un middleware Django qui valide le token
  Better Auth sur les endpoints `/api/dashboard/` (un fichier,
  ~30 lignes). La lib est installee cote frontend, le schema DB
  Better Auth peut vivre dans le meme PostgreSQL.
- **Relance chapitre** : bouton POST sur `/api/dashboard/jobs/:id/retry/`
  (endpoint a ajouter, enfile `run_generation_job_task`).
- **Build prod** : `npm run build` → `dist/` servi par Nginx ou Coolify.

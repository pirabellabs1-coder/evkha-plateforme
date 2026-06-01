# Phase 0 — Fondations et contrats

Cette phase pose uniquement la couche commune du projet EVKHA.

## Inclus

- Monorepo `backend/`, `infra/`, `n8n/`, `docs/`.
- Django, PostgreSQL, Redis, Celery et n8n via `docker-compose.yml`.
- Squelette des 9 apps domaine.
- Modeles Django contractuels et migrations initiales.
- `.env.example` sans secret.
- CI avec Ruff, mypy, pytest, controle migrations et gitleaks.
- Dossier de decisions et template de PR.

## Exclu

- Logique metier de generation IA.
- Appels reseau vers Claude, Google, Gamma, Brevo, Systeme.io ou Tally.
- Workflows n8n executables.
- Rendu documentaire client.

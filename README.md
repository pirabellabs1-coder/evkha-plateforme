# Système EVKHA

Pipeline d'**industrialisation invisible** de livrables stratégiques premium (étude de marché, étude de concurrence, stratégie business, business plan) pour Evkha.

> **Confidentiel — sous NDA.** Aucun secret ne doit être commité. Voir `.gitignore` et `.env.example` (à venir).

## Démarrer ici

📄 **[`docs/master-plan.html`](docs/master-plan.html)** — Plan Maître d'Implémentation.
C'est la **source de vérité unique** du projet : architecture, modules, méthodologie scaffolding, stratégie de branches (Codex × Claude), roadmap, garde-fous et portes qualité.

Ouvrir le fichier dans un navigateur (aucune dépendance, aucun build).

## Protocole de contribution (résumé)

Avant toute tâche : lire le plan maître (§00, §01, §04, §08) + la fiche du module ciblé (§07).
**Contrat d'abord** (modèles/API/types) → squelette + tests → implémentation → vérification (Definition of Done + portes qualité).

- 1 module / tranche = 1 branche = 1 PR.
- Branches : `contract/<module>` (mergées en priorité), `feat/<module>-<tranche>`, `fix/...`, `chore/...`.
- Commits : Conventional Commits.
- `main` protégée : PR + review croisée + CI verte obligatoires.

## Stack

Django · PostgreSQL · Celery/Redis · n8n (orchestration) · Claude API · Google Docs/Drive · Gamma · Docker Compose · Coolify · Uptime Kuma. Dashboard moderne (post-V1) : TanStack Start + Better Auth.

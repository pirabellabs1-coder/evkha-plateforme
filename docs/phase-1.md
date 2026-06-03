# Phase 1 — Socle infra et flux

Cette phase expose les entrees minimales du systeme sans lancer encore la generation IA.

## Endpoints

- `GET /healthz/` : endpoint de supervision pour Uptime Kuma.
- `POST /webhooks/systeme/order/` : reception evenement commande Systeme.io.
- `POST /webhooks/tally/intake/` : reception soumission formulaire Tally.

## Contrats de comportement

- Les webhooks repondent `202` rapidement apres enregistrement local.
- Les evenements sont idempotents par couple `provider` + `event_id`.
- Un doublon ne reenfile pas le traitement Celery.
- Un payload JSON invalide est rejete en `400`.
- La logique metier lourde reste en dehors de la reponse webhook.

## Supervision

Uptime Kuma doit surveiller au minimum :

- `https://<domaine-api>/healthz/`
- l'URL n8n publique ;
- l'URL d'administration Django ;
- l'espace disque et la disponibilite VPS via les moniteurs disponibles sur l'hebergeur.

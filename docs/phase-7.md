# Phase 7 — Accès B2B (scope initial)

Implémente la gestion automatique des abonnements B2B via Systeme.io.
Inclus dans le brief freelance original (p.8, livrable n°3, décision D9).

## Inclus

- **`customers/models.py`** : `SubscriptionTier` (solo/pro/pro_plus/structure),
  `SubscriptionStatus` (active/cancelled/expired), modèle `Subscription`
  (customer FK, tier, status, systeme_subscription_id unique, starts_at, ends_at,
  raw_payload).
- **`customers/services.py`** : `sync_subscription_from_systeme_payload()` —
  gère `subscription.started/renewed` → ACTIVE, `subscription.cancelled/stopped/expired`
  → CANCELLED. Met à jour le `customer_type` B2C → B2B à la première souscription.
- **`customers/migrations/0002_subscription.py`** : migration SQL.
- **`customers/admin.py`** : `SubscriptionAdmin` + colonne "Abonnement actif"
  dans `CustomerAdmin`.
- **`integrations/models.py`** : `SYSTEME_SUB` ajouté à `IntegrationProvider`.
- **`integrations/webhooks.py`** : `SYSTEME_SUB` partagé le même secret que `SYSTEME`.
- **`integrations/views.py`** : `systeme_subscription_webhook` — endpoint dédié
  abonnements.
- **`integrations/tasks.py`** : routage `SYSTEME_SUB` →
  `sync_subscription_from_systeme_payload`.
- **`evkha/urls.py`** : `POST /webhooks/systeme/subscription/`.

## URLs Systeme.io à configurer

Dans le panneau Systeme.io, créer deux webhooks :

| Événement | URL |
|---|---|
| Commande (B2C) | `https://evkha.fr/webhooks/systeme/order/` |
| Abonnement (B2B) | `https://evkha.fr/webhooks/systeme/subscription/` |

Événements à activer pour le webhook abonnement :
`subscription.started` · `subscription.renewed` · `subscription.cancelled`

## Garde-fous vérifiés (`test_phase7_b2b.py`)

- Création d'un abonnement ACTIVE sur `subscription.started`.
- Passage `customer_type` B2C → B2B automatique.
- Annulation sur `subscription.cancelled`.
- Idempotence : double envoi → un seul enregistrement.
- Champs manquants (email, subscription_id) → `SubscriptionIngestionError`.
- `event_type` inconnu → `SubscriptionIngestionError`.
- Slug tier inconnu → fallback SOLO (jamais d'erreur bloquante).
- `Customer.has_active_subscription` : true / false / sans abonnement.
- Endpoint `POST /webhooks/systeme/subscription/` → 202.
- Doublon → 202 `duplicate=True`.
- Task `process_webhook_event` route bien `SYSTEME_SUB` vers le service subscription.

## Exclu (Phase 7b si nécessaire)

- Quota de livrables par formule (Solo/Pro/Pro Plus/Structure avec crédits mensuels).
- Portail self-service pour les abonnés B2B.
- Notification email à Evangeline sur nouvelle souscription B2B.

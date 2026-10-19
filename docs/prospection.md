# Prospection (espace admin) — plan et état

Sous-système neuf, demandé le 18/10/2026 : trouver des prospects, juger s'ils
sont susceptibles de prendre un abonnement, préparer des e-mails et leurs
relances, les suivre (ouvertures, réponses, conversions). **Rien ne part sans
validation humaine.**

## L'invariant, avant tout

Un `Message` naît `brouillon`. Il ne quitte le système que par
`prospection.services.envoyer_message`, qui REFUSE tout message qui n'est pas
`valide`/`programme`, et tout prospect sans e-mail, exclu ou désinscrit. La
désinscription annule les messages encore en file. Verrouillé par
`tests/test_prospection_rien_ne_part_sans_validation.py` (la validation est un
acte nominatif et horodaté).

## Les briques, greffées sur l'existant

- App `prospection`, exposée (à venir) sous `/api/dashboard/prospection/…` —
  même jeton admin que le reste de l'espace.
- E-mail : **Brevo** (`integrations/brevo.py`), déjà branché. Suivi des
  ouvertures/clics/réponses par les **webhooks Brevo** (l'infrastructure de
  webhooks existe pour Tally/Systeme/Stripe).
- Agents IA : client Claude + recherche web déjà en place (`integrations/`).

## Données (`prospection/models.py`)

`Campagne` (secteur, zone, offre visée) · `Prospect` (cible, score d'adéquation,
opt-out) · `Sequence` (étape 0 = 1ᵉʳ mail, 1..N = relances, avec délais) ·
`Message` (un e-mail préparé, avec son état) · `Evenement` (ouvert/cliqué/
répondu/désinscrit, source des métriques).

## Juridique (avis, pas conseil juridique)

Prospection B2B par e-mail en France : permise si le message est professionnel
et la désinscription facile. Opt-out et consentement construits dès le départ ;
suivi d'ouverture par Brevo (natif), pas de pixel maison.

## Phases

1. **Fondations** — modèle + invariant « rien ne part sans validation » +
   migration. **FAIT** (`test_prospection_rien_ne_part_sans_validation.py`).
2. Endpoints admin (CRUD campagnes/prospects/messages, file de validation).
   **FAIT** (`test_prospection_espace_admin.py`).
3. Agents : recherche de prospects, qualification (score d'abonnement),
   rédaction du 1ᵉʳ mail + 4-5 relances — tout en brouillon. **FAIT**
   (`prospection/agents.py`, `test_prospection_agents*.py`). Les agents ne
   produisent que des données ; l'invariant tient. Un passage réel appelle le
   modèle (coût) : endpoints gardés par `confirmer: true`, rien ne tourne sans
   acte délibéré.
4. Envoi validé (file de validation d'Evangéline) + webhooks Brevo de suivi
   (ouvert/cliqué/répondu/désinscrit) + lien de désinscription public.
5. Tableau de bord des métriques : ouvertures, taux d'ouverture, réponses, taux
   de réponse, taux de conversion.

## Décisions tranchées

- Source des prospects : **recherche IA d'abord** (agent `rechercher_des_prospects`),
  import CSV/manuel possible ensuite (création manuelle déjà exposée).
- Suivi d'ouverture : **natif Brevo** (webhooks), pas de pixel maison.
- Modèle des agents : **Sonnet** (la prospection n'a pas la densité d'un
  livrable, et chaque passage est facturé).

# Création du VPS EVKHA — Instructions pas à pas (IONOS)

> **Pour** : Evangeline · **Durée estimée** : 10 minutes  
> **Prérequis** : compte IONOS créé et vérifié (ton domaine est déjà là-bas ✅)

---

## Couche 0 — Ce qu'on construit

Un serveur privé (VPS) qui hébergera tout le système EVKHA :
pipeline de génération, base de données, automatisations n8n.
**Coût : ~4–5 €/mois.**  
Tu crées le serveur, tu me transmets les accès, je m'occupe du reste.

Avantage IONOS : ton domaine est déjà là-bas — tu pourras pointer le DNS
directement depuis le même panneau, sans changer de registrar.

---

## Couche 1 — Trouver la bonne formule

1. Connecte-toi sur **https://www.ionos.fr**
2. Menu : **Serveurs & Hébergement → VPS**
3. Cherche la formule qui correspond à ces caractéristiques :

| Spec | Minimum requis |
|---|---|
| vCPU | **2** |
| RAM | **4 Go** |
| Stockage | ≥ 80 Go SSD |
| OS disponible | Ubuntu 24.04 |

> Chez IONOS, c'est généralement le **VPS L** (~4–5 €/mois).  
> ⚠️ Ne prends pas le S ni le M (trop juste en RAM pour Django + Postgres + Redis + n8n).

---

## Couche 2 — Créer le serveur

**Remplis les options suivantes — dans l'ordre :**

| Option | Valeur à choisir |
|---|---|
| **Formule** | VPS L (ou 4 Go RAM) |
| **Système d'exploitation** | `Ubuntu 24.04` |
| **Localisation** | `Paris` (ou Francfort si Paris indisponible) |
| **Mot de passe root** | Choisis un mot de passe fort — **note-le immédiatement** |
| **Nom du serveur** | `evkha-prod` |

Finalise la commande. Le serveur est prêt en **2–3 minutes**.

✅ *Tu reçois un email de confirmation IONOS avec l'adresse IP du serveur.*

---

## Couche 3 — Récupérer les accès

1. Dans l'email IONOS (ou dans le panneau Cloud), repère l'**adresse IP** du serveur (ex. `85.215.xxx.xxx`)
2. Le **mot de passe root** = celui que tu as choisi pendant la commande  
   *(si tu l'as oublié : panneau IONOS → ton serveur → "Réinitialiser le mot de passe")*

✅ *Tu as maintenant : une adresse IP + un mot de passe root.*

---

## Couche 4 — DNS (bonus IONOS — à faire pendant que je configure)

Puisque ton domaine est chez IONOS, profite-en pour pointer le DNS maintenant :

1. Panneau IONOS → **Domaines & DNS**
2. Sélectionne ton domaine (`evkha.fr` ou autre)
3. Ajoute un enregistrement **A** :
   - **Hôte** : `@` (domaine principal) ou `app` (sous-domaine)
   - **Valeur** : l'adresse IP du serveur
   - **TTL** : 300 (ou laisser par défaut)

> La propagation DNS prend 5–30 minutes. Ça aura le temps de se faire
> pendant que je configure le serveur de mon côté.

---

## Couche 5 — Ce que tu m'envoies

Via WhatsApp (ou le canal habituel) :

```
IP :       xxx.xxx.xxx.xxx
Password : xxxxxxxxxxxx
```

**Et c'est tout.** Je m'occupe de la suite (installation Coolify, déploiement, configuration).

---

## Couche 6 — Vérification rapide (optionnel)

Colle l'IP dans ton navigateur — tu verras une page d'erreur Ubuntu
(c'est normal, ça veut dire que le serveur répond).

---

> **Pour Tobias :** une fois les accès reçus → `docs/deploy-coolify.md`
> (installation Coolify + déploiement EVKHA en 3 commandes).

---

*Historique : initialement prévu sur Hetzner CX22 — basculé sur IONOS
car le domaine evkha.fr est déjà enregistré là-bas (simplification DNS).*

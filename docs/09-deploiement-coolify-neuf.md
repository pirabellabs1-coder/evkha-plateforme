# Déploiement neuf sur Coolify

Ce document décrit la mise en place d'un déploiement **entièrement nouveau**,
à côté de celui qui tourne déjà. L'ancien continue de fonctionner : rien n'est
touché tant que le nouveau n'est pas validé.

C'est le point important. Une bascule directe sur la production existante
suppose que tout fonctionne du premier coup — hypothèse que rien ne soutient,
puisque **aucune génération réelle n'a encore tourné sur cette chaîne**
(règle 7).

---

## 1. La décision à prendre avant de commencer

Un déploiement neuf part avec une **base de données vide**. Vos commandes,
clients et études existants ne s'y trouveront pas.

| Option | Ce qui se passe | Quand la choisir |
|---|---|---|
| **Base vide** (recommandé) | Le nouveau système démarre propre. L'ancien garde ses données et continue de servir les clients en cours. | Pour valider la nouvelle chaîne sans risque. C'est le cas normal. |
| Reprise des données | Copie de la base de production vers la nouvelle. Les migrations du nouveau code s'y appliquent. | Seulement au moment de la bascule définitive, après validation. |

**Ne branchez jamais le nouveau déploiement sur la base de l'ancien.** Les
migrations s'exécuteraient sur les données vivantes, et les deux applications
écriraient dans la même base avec des schémas différents.

---

## 2. Les variables d'environnement

À saisir dans Coolify, onglet *Environment Variables*. Celles marquées
**secret** ne doivent jamais apparaître ailleurs — ni dans le dépôt, ni dans un
message, ni dans une conversation.

### Django

| Variable | Valeur | Note |
|---|---|---|
| `DJANGO_SECRET_KEY` | **secret** | `openssl rand -hex 32`. Sans elle, l'application démarre avec une clé de développement, en silence. |
| `DJANGO_DEBUG` | `false` | En `true`, la moindre erreur affiche le code source et les variables au visiteur. |
| `DJANGO_ALLOWED_HOSTS` | vos domaines, séparés par des virgules | |
| `EVKHA_BEHIND_PROXY` | `true` | Traefik termine le TLS ; sans ce drapeau Django croit être en HTTP. |
| `CSRF_TRUSTED_ORIGINS` | `https://…` de vos domaines | |
| `EVKHA_BASE_URL` | l'URL publique de l'API | Sert à construire les liens de téléchargement. |

### Base de données et file de tâches

| Variable | Valeur |
|---|---|
| `POSTGRES_DB` | `evkha` |
| `POSTGRES_USER` | `evkha` |
| `POSTGRES_PASSWORD` | **secret**, généré |
| `DATABASE_URL` | `postgres://evkha:<mot de passe>@postgres:5432/evkha` |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/1` |

### Services externes

| Variable | Valeur | Conséquence si absente |
|---|---|---|
| `ANTHROPIC_API_KEY` | **secret** | Aucune génération réelle possible. |
| `BREVO_API_KEY` | **secret** | Aucun e-mail envoyé. |
| `SYSTEME_WEBHOOK_SECRET` | **secret** | L'endpoint accepte **toutes** les requêtes sans vérification. Le contrôle de démarrage le signale déjà. |
| `TALLY_WEBHOOK_SECRET` | **secret** | Idem. |

### Les drapeaux qui décident si le système travaille pour de vrai

C'est ici que se joue la différence entre une plateforme qui produit et une
plateforme qui fait semblant.

| Variable | Recette | Production | Ce que `true` signifie |
|---|---|---|---|
| `EVKHA_USE_STUB_AI` | `true` | `false` | Aucun appel à Claude. Les chapitres sont des textes factices. **Gratuit.** |
| `EVKHA_USE_STUB_PDF` | `true` | `false` | Le PDF est un fichier bouchon, pas un vrai document. |
| `EVKHA_USE_STUB_EMAIL` | `true` | `false` | Aucun e-mail ne part. |
| `EVKHA_USE_STUB_DOCS` | `true` | `false` | |

**Commencez tout en `true`.** Vous validez la chaîne complète sans dépenser un
euro et sans risquer d'écrire à un vrai client depuis un environnement de test.
Vous basculez ensuite, un drapeau à la fois.

### Accès à l'administration

| Variable | Valeur |
|---|---|
| `EVKHA_DASHBOARD_AUTH_DISABLED` | `false` — impératif en production |
| `EVKHA_DASHBOARD_TOKEN` | **secret**, `openssl rand -hex 32` |

Laisser `EVKHA_DASHBOARD_AUTH_DISABLED=true` en production ouvre l'espace
administrateur à qui connaît l'adresse.

---

## 3. Les services à créer

Le fichier `docker-compose.prod.yml` en déclare six. Coolify les crée tous à
partir de ce seul fichier.

| Service | Rôle | Peut-il manquer ? |
|---|---|---|
| `api` | Django, l'API des deux espaces | Non |
| `worker` | Celery — c'est **lui** qui produit les études | Non. Sans lui, les commandes restent en attente indéfiniment. |
| `beat` | Tâches périodiques | Non — c'est lui qui détecte les études bloquées |
| `dashboard` | Les deux espaces React | Non |
| `postgres` | Base de données | Non |
| `redis` | File de tâches | Non |

`api` et `worker` partagent le volume `media` : le worker y écrit les documents,
l'API les sert. **Vérifiez que ce partage est bien en place** — sans lui, le
client télécharge un fichier introuvable.

---

## 4. Ordre de mise en route

1. **Créer le projet** dans Coolify, source = votre dépôt Git, fichier
   `docker-compose.prod.yml`.
2. **Saisir les variables**, tous les drapeaux `STUB` à `true`.
3. **Déployer.** La construction installe LibreOffice : comptez cinq à dix
   minutes de plus qu'à l'ordinaire, et environ 400 Mo d'image en plus.
4. **Vérifier que ça répond** : `https://<votre-api>/healthz/` doit renvoyer
   un état correct.
5. **Vérifier LibreOffice**, depuis le terminal du conteneur `worker` :
   `soffice --version`.
6. **Créer les formules** : `python manage.py seed_formules`.
7. **Créer un compte de test** et passer une commande de bout en bout, toujours
   en mode bouchon. Le crédit doit être débité, l'étude progresser, le document
   apparaître.
8. **Basculer `EVKHA_USE_STUB_PDF=false`** et refaire une commande : le PDF doit
   cette fois être un vrai document.
9. **Basculer `EVKHA_USE_STUB_AI=false`** — et seulement là, une génération
   réelle. Une seule. On lit le document ensemble avant d'en lancer une autre.

Les étapes 7 à 9 ne sont pas une formalité. Chacune vérifie une chose que la
précédente ne pouvait pas vérifier.

---

## 5. Ce qui reste faux tant que ce n'est pas fait

- **Aucune génération réelle n'a jamais tourné** sur cette chaîne. Tout est
  vérifié sur des doublures. Le premier vrai dossier trouvera ce que trois
  relectures n'ont pas trouvé — c'est arrivé quatre fois sur ce projet.
- **La conversion PDF n'a jamais tourné** : LibreOffice était absent de la
  machine de développement. Seul le bouchon a été exercé.
- **Le nombre de pages est donc inconnu**, et « inconnu » ne veut pas dire
  « conforme ». Le critère de recette « 55 à 60 pages » ne pourra être vérifié
  qu'après la première conversion réelle.
- **Les polices Aptos et Georgia sont absentes de Linux.** LibreOffice leur
  substituera autre chose et le PDF différera visiblement du Word. Décision à
  prendre : installer les polices, ou changer celles du gabarit.

---

## 6. Bascule, plus tard

Quand le nouveau déploiement aura produit trois études réelles conformes :

1. rediriger les domaines vers le nouveau ;
2. garder l'ancien **allumé** une semaine, sans trafic ;
3. ne le supprimer qu'après.

Le §16 du cahier des charges le dit : « le moteur existant reste en service
jusqu'à validation complète du nouveau », et « le basculement s'opère derrière
un indicateur de configuration, réversible immédiatement ».

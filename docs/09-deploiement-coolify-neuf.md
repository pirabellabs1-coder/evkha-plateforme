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

## 3 bis. Ce qui est déjà créé dans Coolify

Mis en place le 30 juillet 2026 via l'API Coolify, et **déployé** le même jour.

| Élément | Identifiant | Note |
|---|---|---|
| Coolify | `http://82.165.31.105:8000` | En **HTTP**, pas en HTTPS. À corriger. |
| Serveur | `kmsk482jekuqvi22wgbgathv` (`localhost`) | Coolify tourne sur le VPS lui-même. |
| Projet | `flv3qnhvhfcidp0pvm706gcg` (`evkha-plateforme`) | Environnement `production` : `s12w7z0tiwxya79iq36g38bk`. |
| Ressource neuve | `zft1wslml9mp2dlwuvttjbxw` | Compose, branche `espace-client-et-credits`. |
| Clé de déploiement | `oxa4hzqbfjz2fuz662itbugh` (`github-deploy-evkha`) | La même que la production. |
| **Production, à ne pas toucher** | `zuai4axswqlebjukcnxt3jfa` (`evkha-api`) | Branche `main`, `running`. |

### Deux dépôts, et c'est une dette

La clé de déploiement `github-deploy-evkha` n'a **pas** accès à
`EVKHA-SVG/Systeme-EVKHA-`, le dépôt de la cliente — le premier déploiement a
échoué au clonage sur `ERROR: Repository not found`. Et une clé de déploiement
s'ajoute depuis les *Settings* du dépôt, ce qui demande le rôle *Admin* : le
développeur n'y est que collaborateur.

Contournement en place : la branche est recopiée dans un dépôt **privé**,
`pirabellabs1-coder/evkha-plateforme`, dont Coolify clone désormais. Le distant
Git local s'appelle `perso` ; `origin` reste le dépôt de la cliente.

**Les deux dépôts doivent rester identiques** — c'est la règle 5 qui est en jeu.
Tout commit part sur les deux, sans exception. À la bascule en production, il
faudra soit obtenir une clé de déploiement sur le dépôt de la cliente, soit lui
transférer celui-ci. La cliente n'étant pas technique, ce sera au développeur de
le faire.

À noter au passage : la production clone depuis `git@github.com:tobiags/…`, un
chemin que la clé lit mais que le compte du développeur ne voit pas. Soit la
production tourne depuis un dépôt distinct de celui où l'on développe, soit ce
dépôt a disparu et la production ne peut plus se redéployer. **Non tranché** —
à clarifier avant la bascule, pas après.

### Adresses d'accès, sans attendre le DNS

`nip.io` résout n'importe quel `<préfixe>.<ip-en-tirets>.nip.io` vers l'IP
correspondante, sans aucun enregistrement à créer. Let's Encrypt émet des
certificats valides pour ces noms — vérifié, `ssl_verify_result` à 0.

| Espace | Adresse |
|---|---|
| Espace client | `https://app-evkha.82-165-31-105.nip.io/espace` |
| Espace administrateur | `https://app-evkha.82-165-31-105.nip.io/login` puis `/admin` |
| API | `https://api-evkha.82-165-31-105.nip.io/healthz/` |

L'espace administrateur demande le jeton `EVKHA_DASHBOARD_TOKEN` (dans
`env-coolify.txt`, sur le poste de développement). L'espace client demande un
compte, qui n'existe pas encore sur cette base neuve.

`api2.evkha.fr` et `app2.evkha.fr` sont configurés en parallèle et répondent
déjà — le jour où les enregistrements A existeront, il n'y aura rien à refaire.

`EVKHA_BASE_URL` pointe provisoirement sur l'adresse `nip.io` pour que les liens
de téléchargement soient joignables. **À rebasculer sur `api2.evkha.fr`** à la
mise en production.

### Ce qui est vérifié, et comment

Un déploiement vert ne prouve rien (règle 7). Mesuré par requêtes réelles, en
contournant le DNS absent via `curl --resolve` :

| Test | Résultat | Ce que ça prouve |
|---|---|---|
| `GET /healthz/` | 200 `{"status":"ok"}` | Django démarre et Gunicorn sert. **Rien de plus** : cette vue renvoie une constante, elle ne touche ni base, ni Redis, ni Celery. |
| `GET /api/espace/moi/` avec jeton bidon | 401 JSON | La table des jetons est interrogée. |
| `POST /api/espace/connexion/`, identifiants faux | 401 « Identifiants invalides » | La table des comptes existe et le mot de passe est vérifié : **les migrations sont passées**. |
| `GET /admin/login/` | 200, 4 238 o | Django rend ses gabarits. |
| `GET /static/admin/css/base.css` | 200, 22 120 o | `collectstatic` a tourné. |
| `GET app2.evkha.fr/` | 200, 1 322 o | L'espace client est servi. |

**Ce qui n'est pas vérifié**, et qu'il ne faut pas croire acquis : Celery
consomme-t-il réellement ses tâches ; LibreOffice convertit-il (l'API Coolify de
cette version n'expose pas d'exécution de commande, donc `soffice --version`
n'a pas pu être lancé) ; le certificat Let's Encrypt (impossible sans DNS) ; et
aucune génération réelle, évidemment.

Les 33 variables d'environnement sont poussées, tous les drapeaux `STUB` à
`true`. Coolify les enregistre **en double** — un jeu « production » et un jeu
« aperçu », valeurs identiques. C'est son fonctionnement normal, pas un défaut.
Conséquence à connaître : le jeu « aperçu » contient une copie des secrets de
production. Sans déploiement d'aperçu il dort, mais il existe.

### Le piège Traefik, à connaître avant de recommencer ailleurs

Les étiquettes Traefik écrites dans `docker-compose.prod.yml` **ne suffisent
pas**. Coolify ne raccorde un service Compose à son réseau de proxy que si un
domaine lui est déclaré *de son côté*, service par service. Sans cette
déclaration, les conteneurs tournent sur un réseau isolé : Traefik ne les voit
pas, et le site répond exactement comme un domaine inexistant — **404 en HTTP,
503 en HTTPS**. Rien dans les journaux de déploiement ne le signale, puisque le
déploiement, lui, a réussi.

Le symptôme est trompeur : `docker compose` annonce six conteneurs démarrés,
`nginx` journalise ses processus, et pourtant rien n'est joignable. Le test qui
tranche est de comparer avec un hôte inventé : s'il renvoie les mêmes codes que
votre domaine, c'est que Traefik n'a aucune route pour vous.

Correctif appliqué, via l'API (`PATCH /applications/{uuid}`) ou dans l'interface
onglet *Domains* :

```json
"docker_compose_domains": [
  {"name": "api",       "domain": "https://api2.evkha.fr"},
  {"name": "dashboard", "domain": "https://app2.evkha.fr"}
]
```

Un redéploiement est nécessaire ensuite : le raccordement réseau se fait à la
création des conteneurs.

### Ce qui reste à faire

1. **Les deux enregistrements DNS.** `api2.evkha.fr` et `app2.evkha.fr` ne
   résolvent pas. Deux enregistrements A vers `82.165.31.105`, chez IONOS. Sans
   eux, Let's Encrypt ne peut pas émettre de certificat : le site fonctionne
   (vérifié via `curl --resolve`) mais reste injoignable depuis un navigateur.
2. **Coolify en HTTPS.** L'API renvoie la clé **privée** de déploiement dans la
   réponse de `GET /security/keys`, et l'interface parle en HTTP clair. Cette
   clé traverse donc Internet en clair à chaque appel de ce type. Un
   enregistrement `coolify.evkha.fr` et un domaine posé sur l'instance ferment
   la brèche.
3. **`ANTHROPIC_API_KEY` et `BREVO_API_KEY`** sont vides. Sans conséquence tant
   que les drapeaux `STUB` valent `true` — c'est-à-dire tant qu'on n'attend pas
   du système qu'il produise quoi que ce soit de réel.

### Attention au moment de fusionner dans `main`

`docker-compose.prod.yml` exige désormais `API_DOMAIN` et `FRONT_DOMAIN`
(`${API_DOMAIN:?…}`). La production tourne sur `main`, où ces variables
n'existent pas encore. Tant que la branche n'est pas fusionnée, rien ne bouge —
mais **le jour de la fusion, le prochain redéploiement de `evkha-api` échouera**
si ces deux variables ne lui ont pas été ajoutées d'abord (avec
`API_DOMAIN=app.evkha.fr` et son `STACK_NAME` propre). À faire avant la fusion,
pas après.

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

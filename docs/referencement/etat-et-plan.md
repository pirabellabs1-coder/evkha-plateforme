# Référencement d'evkha.fr — état et plan

Rédigé le 20/11/2026, sur la branche `claude/referencement-evkha-fe8713`.
Rien de ce document n'est en ligne : la mise en production se décide ailleurs.

> **Ce document n'annonce aucun gain de position.** Il dit ce qui a été
> mesuré, ce qui a été corrigé dans le code, et ce qui reste. La seule preuve
> d'un progrès sera une mesure dans la Search Console, plusieurs semaines
> après la mise en ligne.

## 1. En bref

1. **Le site était invisible pour un robot qui n'exécute pas de JavaScript.**
   Mesuré sur la production : toutes les adresses rendaient la même page vide.
   C'est corrigé dans le code par un pré-rendu à la construction.
2. **Il n'y avait ni `robots.txt`, ni plan du site, ni adresse canonique.**
   Les trois sont maintenant écrits automatiquement, à partir d'une seule liste.
3. **Les requêtes de tête (« étude de marché », « business plan ») sont tenues
   par des banques, l'État et de grands éditeurs.** EVKHA n'y passera pas de
   front. Les créneaux accessibles : « faire faire » son étude ou son business
   plan, les études par secteur, Lille, et l'offre pour les professionnels.
4. **Trois guides ont été ajoutés au blog.** Ils sont à relire par la gérante
   avant toute mise en ligne (section 8).
5. **Une partie du travail ne peut être faite que par la gérante** : fiche
   Google, Search Console, annuaires, avis (section 7).

## 2. Ce qu'un robot reçoit aujourd'hui (mesuré)

Mesure du 20/11/2026 sur `https://evkha.fr`, par `curl`, avec l'identité de
Googlebot, sans exécuter de JavaScript :

| Adresse demandée | Code | Type | Taille |
|---|---|---|---|
| `/` | 200 | text/html | 3 659 octets |
| `/etudes` | 200 | text/html | 3 659 octets |
| `/formations` | 200 | text/html | 3 659 octets |
| `/blog` | 200 | text/html | 3 659 octets |
| `/robots.txt` | 200 | **text/html** | 3 659 octets |
| `/sitemap.xml` | 200 | **text/html** | 3 659 octets |
| `/llms.txt` | 200 | **text/html** | 3 659 octets |
| `/nimporte-quoi-xyz` | **200** | text/html | 3 659 octets |

C'est le même fichier partout. Son contenu :

- titre : « EVKHA — Espace client » ;
- description : « Espace client EVKHA : suivez vos générations… » ;
- corps : `<div id="root"></div>`, vide ;
- aucune adresse canonique, aucune donnée structurée.

Conséquences :

- **Google** exécute les scripts, mais dans un second passage, plus tardif. Il
  finit par voir les pages, sans garantie de délai.
- **Les robots des moteurs de réponse** (ChatGPT, Perplexity, Claude) et la
  plupart des aperçus de partage n'exécutent pas les scripts : ils ne lisaient
  **rien** du site.
- **`robots.txt` et le plan du site n'existaient pas** : le serveur répondait
  la page vide à leur place.
- **Une adresse inexistante répond 200** au lieu de 404.

Autres mesures :

- `www.evkha.fr` renvoie bien vers `evkha.fr` (301) ; `http` vers `https`.
- La compression (gzip) est active.
- Aucun en-tête de cache sur les fichiers de l'application : chaque visite les
  redemandait.
- La balise de vérification de la Search Console est bien servie.

## 3. Ce qui a été corrigé dans le code

### 3.1 Le pré-rendu (le plus gros changement)

À la construction (`npm run build`), un script écrit **un fichier HTML complet
par page publique** : `frontend/scripts/prerendre.mjs`, avec
`frontend/src/prerendu.ts`. Il monte le vrai routeur et les vraies pages : ce
que le robot reçoit est ce que le visiteur voit.

- 23 pages : accueil, études, boutique, 3 pages de packs, 4 de formations,
  partenaires, Swapn, blog et ses 4 articles, boîte à outils, contact, 4 pages
  légales.
- Chaque page écrite porte son titre, sa description, son adresse canonique,
  ses balises de partage, ses données structurées et tout son texte.
- **Aucun prix n'est figé** : le serveur n'est pas interrogé pendant la
  construction. À la place d'un prix, la page écrite porte « Tarif en cours de
  chargement… », que le navigateur remplace par le vrai montant.
- Le script **échoue bruyamment** : une page vide, « introuvable », sans titre,
  ou deux pages au même titre font échouer la construction. La version en
  ligne reste alors celle d'avant.
- `frontend/nginx.conf` sert ces fichiers (`/etudes` → `etudes.html`).
  `index.html` reste la page vide de l'application, pour l'espace client et
  l'administration.

### 3.2 `robots.txt`, plan du site, `llms.txt`

Les trois sont écrits par le même script, à partir d'une seule liste :
`frontend/src/public/planDuSite.ts`.

- `robots.txt` : tout est ouvert, **y compris aux robots d'IA**, sauf les
  espaces connectés et les pages de paiement.
- `sitemap.xml` : les 23 pages.
- `llms.txt` : le plan du site pour les moteurs de réponse, avec le vrai titre
  et la vraie description de chaque page.

Une page ajoutée au site sans être inscrite dans cette liste fait échouer un
test.

### 3.3 Les balises de chaque page

`useTitreDePage` (`frontend/src/public/site.ts`) posait le titre et la
description. Il pose maintenant aussi :

- l'adresse canonique (toujours sur `https://evkha.fr`, sans paramètre) ;
- les balises de partage (Open Graph, Twitter), identiques au titre et à la
  description ;
- le fil d'Ariane des pages rangées sous une rubrique.

Les pages « introuvable » ne déclarent ni adresse canonique ni fil d'Ariane.

### 3.4 Les données structurées

| Bloc | Où | Ce qu'il dit |
|---|---|---|
| `ProfessionalService` + `WebSite` | accueil | nom, adresse du siège, courriel, fondatrice, réseaux |
| `Service` | page des études | les quatre documents, sans prix |
| `FAQPage` | toute page qui affiche des questions | les questions **telles qu'affichées** |
| `BreadcrumbList` | packs, formations, articles | Accueil › rubrique › page |
| `Course` | formations (existait) | avec le prix lu au serveur |
| `Article` | articles du blog (existait) | sans date inventée |

L'adresse du siège est celle des mentions légales du site (41 rue Jacquemars
Giélée, 59800 Lille). Un test vérifie que les deux restent d'accord. **Aucun
téléphone, aucune note, aucun nombre d'avis, aucun horaire** : le site n'en
publie pas.

### 3.5 Les titres de quatre pages

Les anciens titres ne nommaient aucun document vendu.

| Page | Avant | Après |
|---|---|---|
| Accueil | EVKHA — De l'idée à l'entreprise | Étude de marché, business plan, étude de concurrence — EVKHA |
| Études | Nos études et livrables — EVKHA | Faire faire son étude de marché ou son business plan — EVKHA |
| Boutique | Études en téléchargement immédiat — EVKHA | Études de marché par secteur, à télécharger — EVKHA |
| Partenaires | Partenaires PRO et abonnements — EVKHA | Études et business plans sous votre marque, pour les pros — EVKHA |

À faire valider par la gérante (section 8).

### 3.6 Vitesse

- Cache d'un an sur les fichiers de l'application (`/assets/`), dont le nom
  change à chaque modification.
- La page arrive avec son contenu déjà écrit, sa feuille de style et son
  script préchargés.
- Non mesuré : les Core Web Vitals réels. À lire dans la Search Console après
  mise en ligne.

### 3.7 Les tests

Trois fichiers, dans `frontend/src/test/` :

- `le-referencement-dit-vrai` : pour chacune des 23 pages, titre et
  description uniques, adresse canonique, balises de partage, questions
  déclarées identiques à celles affichées, fil d'Ariane.
- `le-plan-du-site-n-oublie-aucune-page` : aucune page publique hors du plan,
  et la chaîne construction → Docker → nginx est entière.
- `les-guides-du-blog` : chaque guide a sa page, sans prix ni promesse non
  confirmée.

Ils ont été rejoués contre cinq défauts introduits exprès (adresse canonique
retirée, questions non déclarées, nginx sans pré-rendu, page retirée du plan,
prix écrit dans un guide) : les cinq font échouer un test.

## 4. Vérification sur le vrai serveur

*(complété en fin de travail — voir la section 9 pour ce qui n'a pas pu être
vérifié)*

L'image Docker du front a été construite localement (`frontend/Dockerfile`,
Node 20, nginx) et interrogée par `curl` avec l'identité de Googlebot, sans
JavaScript. C'est le même nginx et la même configuration qu'en production ;
seule l'API manquait.

| Adresse | Code | Type | Taille | Titre reçu |
|---|---|---|---|---|
| `/` | 200 | text/html | 64 425 o | Étude de marché, business plan, étude de concurrence — EVKHA |
| `/etudes` | 200 | text/html | 40 217 o | Faire faire son étude de marché ou son business plan — EVKHA |
| `/partenaires` | 200 | text/html | 38 509 o | Études et business plans sous votre marque, pour les pros — EVKHA |
| `/packs/essentiel` | 200 | text/html | 48 106 o | Pack Création Essentiel : étude de marché, prévisionnel… |
| `/blog/comment-faire-une-etude-de-marche` | 200 | text/html | 33 658 o | Comment faire une étude de marché : les 6 étapes — EVKHA |
| `/robots.txt` | 200 | **text/plain** | 434 o | — |
| `/sitemap.xml` | 200 | **text/xml** | 23 adresses | — |
| `/llms.txt` | 200 | **text/plain** | 6 507 o | — |
| `/espace/connexion` | 200 | text/html | 3 724 o | EVKHA — Espace client (page vide de l'application, voulu) |
| `/boutique/une-etude` | 200 | text/html | 3 724 o | EVKHA — Espace client (**reste à faire**, section 7.1) |
| `/nimporte-quoi` | **200** | text/html | 3 724 o | (**reste à faire**, section 7.1) |
| `/partenaires/reunion.jpg` | 200 | image/jpeg | — | l'image est toujours servie |
| un fichier d'application absent | **404** | — | — | au lieu de la page vide en 200 |

Également constaté :

- les fichiers d'application portent `Cache-Control: max-age=31536000` ;
- un nom en `www.` renvoie toujours en 301 ;
- la page des études pré-rendue porte 1 744 mots lisibles, l'accueil 2 937 ;
- dans un navigateur, la page s'affiche comme avant une fois le JavaScript
  chargé.

**Un défaut trouvé par cette vérification, et corrigé.** Dans le navigateur,
la page des études portait ses données structurées **en double** : celles
écrites dans le HTML, plus celles que l'application repose. Aucun test ne
l'avait vu. L'application remet maintenant l'en-tête à neuf avant de prendre
le relais (`frontend/src/enTetePrerendu.ts`).

Les tests lancés, tous verts : les 3 nouveaux fichiers (55 tests), les
9 fichiers de test des pages touchées (443 tests), et les 4 fichiers du
serveur qui lisent `nginx.conf` et le `Dockerfile` (17 tests). Contrôles du
front : `npx tsc -b --force` et `npx eslint src --quiet`, sans erreur.

## 5. Les concurrents

### 5.1 Limites de ce relevé

- **Ce ne sont pas des positions sur Google France.** L'outil de recherche
  utilisé est localisé aux États-Unis. Les sites cités sont ceux qui
  *remontent* sur chaque requête, sans rang fiable, sans annonces, sans
  résultats locaux.
- Les blocs « Autres questions posées » de Google **n'ont pas été observés**.
- **Aucun moteur de réponse n'a été interrogé directement.**
- **Aucun volume de recherche n'est mesuré** : il faut un outil payant ou les
  données de la Search Console.

### 5.2 Qui remonte, par requête

| Requête | Qui remonte | Type d'acteur |
|---|---|---|
| étude de marché | HubSpot, Bpifrance Création, Brevo, Semrush, Shopify, Crédit Agricole (Propulse) | éditeurs de logiciels, institution, banque |
| faire faire une étude de marché | Square, Shopify, HubSpot, service-public.gouv.fr, Journal du Net | éditeurs, État — **aucun prestataire** |
| étude de marché prix | IntoTheMinds, Crédit Agricole, La Poste, Qualtrics | cabinet d'études, banque |
| étude de marché restaurant / coiffure / food truck / institut de beauté | Crédit Agricole, MAPA assurances, Le Blog du Dirigeant, modelesdebusinessplan.com, Xerfi | banque, assureur, vendeur de modèles |
| business plan | Qonto, Legalstart, Shopify, creerentreprise.fr, Indy, Bpifrance | néobanque, juridique en ligne |
| faire faire un business plan | petite-entreprise.net, Le Coin des Entrepreneurs, annonces ComeUp et Fiverr, cabinets comptables | médias, places de marché |
| business plan prix | Crédit Agricole, Indy, Dougs, Le Coin des Entrepreneurs | banque, comptables en ligne |
| business plan banque | Crédit Agricole (dominant), l-expert-comptable.com, Meilleurtaux | banque, comparateurs |
| étude de concurrence | Qualtrics, IntoTheMinds, HubSpot, Mailchimp, Bpifrance | éditeurs |
| stratégie commerciale | Salesforce, HubSpot, Pipedrive | éditeurs de CRM |
| formation création d'entreprise | Onisep, Shine, Legalstart, LegalPlace, CCI, Cnam | institutions, juridique en ligne |
| formation micro-entreprise en ligne | LegalPlace, impots.gouv.fr, CMA, portail-autoentrepreneur.fr | juridique en ligne, État |
| étude de marché Lille | immobilier d'entreprise, marchés publics | **hors sujet** |
| business plan Lille | Métropole de Lille, profils Malt, une page ville d'Indy | collectivité, indépendants |
| business plan marque blanche expert-comptable | aucune page dédiée au dossier rédigé ; des logiciels de prévisionnel | — |

### 5.3 Ce que font les pages bien placées

Relevé sur huit pages lues :

- **Une réponse chiffrée** quand la question porte sur un prix. Ce sont ces
  pages que les synthèses automatiques reprennent.
- **Un sommaire**, des intertitres en forme de questions, souvent un tableau.
- **Un auteur nommé et une date de mise à jour** (Crédit Agricole, IntoTheMinds,
  l-expert-comptable.com, Legalstart).
- **Une page par secteur** (Crédit Agricole, MAPA, modelesdebusinessplan.com).
- **Un modèle ou un extrait à télécharger.**
- Chez les vendeurs de formation : prix, certification et financement affichés.

### 5.4 Ce qu'EVKHA ne fait pas encore

| Ce que font les mieux placés | État chez EVKHA |
|---|---|
| Contenu lisible sans JavaScript | **Corrigé** (pré-rendu) |
| Plan du site, `robots.txt`, adresse canonique | **Corrigé** |
| Guides qui répondent aux questions | **Commencé** : 3 guides, à valider |
| Auteur nommé, date de mise à jour | Auteur déclaré ; **pas de date** tant que la gérante n'a pas publié |
| Page « combien ça coûte » avec des chiffres | **Non fait** : les prix ne s'écrivent pas en dur (section 6) |
| Une page par secteur | **Partiel** : les fiches de la boutique existent, mais ne sont pas pré-rendues (section 6) |
| Extrait ou modèle à télécharger | Non fait |
| Liens venant d'autres sites | Non mesuré ; à construire (section 7) |

## 6. Mots-clés, par intention

**Volume : non mesuré, pour toutes les lignes.** La difficulté est une
estimation, fondée sur qui occupe la première page.

| Intention | Mots-clés | Difficulté estimée | Page d'EVKHA qui y répond |
|---|---|---|---|
| S'informer | étude de marché ; business plan ; stratégie commerciale ; étude de concurrence | Forte | aucune à viser de front |
| S'informer | comment faire une étude de marché ; étude de marché obligatoire ; que contient un business plan ; différence prévisionnel et business plan | Moyenne | les 3 guides du blog |
| Comparer | étude de marché prix ; combien coûte un business plan ; business plan pour la banque | Moyenne | guide « business plan pour la banque » ; page prix à créer |
| Comparer | étude de marché restaurant / coiffure / food truck / institut de beauté | Moyenne à forte | fiches de la boutique |
| Acheter | **faire faire une étude de marché ; faire faire un business plan** ; étude de marché sur mesure | **Faible à moyenne** | page des études (titre récrit) |
| Acheter | étude de marché [secteur] à télécharger, PDF | Moyenne | boutique |
| Acheter | formation création d'entreprise ; formation micro-entreprise en ligne | Forte | pages des formations |
| Local | étude de marché Lille ; business plan Lille ; accompagnement création d'entreprise Lille | **Faible** | aucune ; fiche Google d'abord |
| Professionnels | étude de marché en marque blanche ; business plan pour cabinet ; dossiers de création pour experts-comptables | **Faible** | page partenaires (titre récrit) |
| Dossier d'aide | business plan France Travail ; business plan BGE ; dossier ARCE | Faible à moyenne | page des études (le texte cite BGE et France Travail) |

**Où mettre l'effort**, dans l'ordre : « faire faire », professionnels, Lille,
puis les secteurs. Pas les requêtes de tête.

## 7. Ce qui reste à faire

### 7.1 Dans le code

1. **Les fiches de la boutique ne sont pas pré-rendues.** Leur contenu vient
   de la base de données et change sans mise en ligne. Un robot sans
   JavaScript reçoit encore la page vide pour `/boutique/<étude>`. Or ce sont
   les pages « par secteur » que la concurrence aligne en série. Remède
   proposé : une vue Django qui rend le HTML de la fiche, et un plan du site
   dynamique pour ces fiches. C'est un lot à part, côté serveur.
2. **Les quatre cartes de la page des études** n'apparaissent qu'une fois le
   catalogue reçu. La page pré-rendue porte tout le reste du texte, mais à
   leur place : « Chargement du catalogue… ». Remède : afficher
   l'argumentaire tout de suite et n'attendre que le prix.
3. **Une adresse inexistante répond toujours 200.** La page demande bien à ne
   pas être indexée, mais seulement une fois les scripts exécutés. Un vrai 404
   demande que le serveur connaisse la liste des routes.
4. **Une page « combien coûte une étude de marché / un business plan ».**
   C'est le format le plus repris par les moteurs de réponse. Elle doit lire
   les prix d'EVKHA au serveur, et la gérante doit dire si elle veut y citer
   les prix du marché, avec leurs sources.
5. **Les images** : plusieurs ont un texte alternatif vide. La plupart sont
   décoratives ; l'image d'ouverture de la page des études est à vérifier.
6. **Le menu** n'a pas été touché (consigne). Entrée souhaitée, si la gérante
   valide les guides : rien de plus, le blog y est déjà.

### 7.2 Ce que la gérante doit faire elle-même

1. **Search Console** : soumettre `https://evkha.fr/sitemap.xml` après la mise
   en ligne, puis demander l'indexation de l'accueil et de la page des études.
2. **Fiche Google Business Profile** : la créer ou la revendiquer, avec
   exactement le nom, l'adresse et le courriel du site. Catégorie à choisir
   par elle. Ajouter un téléphone seulement si elle veut le rendre public — il
   faudra alors l'écrire aussi sur le site.
3. **Même nom, même adresse partout** : mentions légales, fiche Google,
   LinkedIn, Facebook, Instagram, annuaires. Aujourd'hui le site écrit
   « EVKHA Business & Formations », « EVKHA Business et Formations » et
   « Evkha » selon les pages.
4. **Annuaires utiles** : Pages Jaunes, annuaire de la CCI Hauts-de-France,
   réseaux d'accompagnement dont elle est partenaire (le site cite Initiative
   France, LegalPlace, Swapn). Demander à ces partenaires un lien vers
   `evkha.fr` : c'est ce qui manque le plus à un site neuf.
5. **Avis** : demander aux clients de laisser un avis sur la fiche Google. Le
   site affiche déjà ceux du profil ComeUp.
6. **Bing Webmaster Tools** : y déclarer le site. ChatGPT s'appuie sur Bing.
7. **Mesurer** : relever dans la Search Console, chaque mois, les requêtes,
   les impressions et les pages indexées.

## 8. Ce que la gérante doit valider

Rien de ce qui suit n'a été tranché à sa place.

**Nouveau, écrit dans ce lot :**

1. **Les trois guides du blog** (`frontend/src/public/contenuGuides.ts`). Ils
   ne viennent pas de son site : ils sont proposés. **Ils portent sa
   signature « Evangéline » et la déclarent comme auteur.** Elle doit les
   relire, les corriger, et dire s'ils peuvent paraître sous son nom. S'ils
   ne conviennent pas, les retirer de la liste suffit.
   - « Comment faire une étude de marché ? »
   - « Business plan pour la banque : que doit-il contenir ? »
   - « Étude de marché, étude de concurrence, business plan : par quoi
     commencer ? »
2. **Les quatre titres de page** récrits (section 3.5).
3. **L'adresse du siège** déclarée aux moteurs : c'est celle des mentions
   légales. Si c'est une adresse personnelle qu'elle ne veut pas voir mise en
   avant, il faut le dire.

**Déjà sur le site, non tranché, et désormais lisible par les robots :**

4. L'ancienneté : « plus de 15 ans », « 15 ans », « 16 ans » selon les pages.
5. « 500+ entrepreneurs formés et accompagnés » et « 500+ porteurs
   accompagnés ».
6. « 100 % de notes 5 étoiles ».
7. « Attestation Qualiopi », le financement des formations, « accès à vie »
   contre « accès illimité », le paiement en plusieurs fois.
8. Le numéro de déclaration d'activité et les numéros SIRET, RCS et TVA des
   mentions légales.

Les guides n'emploient aucun de ces points : un test le verrouille.

## 9. Ce qui n'a pas été vérifié

- **Aucune position, aucun trafic.** Rien n'est en ligne ; et même en ligne,
  seule la Search Console le dira.
- **Les positions réelles sur Google France**, les résultats locaux à Lille,
  les blocs « Autres questions posées » et les réponses des moteurs d'IA :
  non observés (section 5.1).
- **Les volumes de recherche** : non mesurés.
- **Le comportement de Google sur les pages pré-rendues** (délai
  d'indexation, extraits affichés) : à constater après mise en ligne.
- **Les Core Web Vitals** : non mesurés.
- **La validité des données structurées dans l'outil de Google** (« Test des
  résultats enrichis ») : il lui faut une adresse publique. À passer sur
  l'accueil, une formation, un pack et un article après mise en ligne.
- **La suite complète des tests** (front et serveur) n'a pas été lancée : la
  machine était partagée. Seuls les fichiers de test des pages touchées l'ont
  été — voir la section 4. `ruff`, `mypy`, `pytest` et
  `makemigrations --check` n'ont pas été lancés : aucun fichier Python n'a
  été modifié, mais trois tests du serveur lisent `frontend/nginx.conf`
  (voir la section 4).
- **Les guides** n'ont été relus par personne d'autre que leur rédacteur.

## 10. Pour la mise en ligne

- La construction du front lance maintenant le pré-rendu. Si elle échoue, le
  message commence par `prerendre : ÉCHEC —` et dit quelle page.
- Preuve à relever après déploiement (un `200` ne prouve rien) :

```bash
curl -s https://evkha.fr/robots.txt | head -5
curl -s https://evkha.fr/etudes | grep -o "<title>[^<]*"
curl -s https://evkha.fr/sitemap.xml | grep -c "<loc>"
```

  Attendu : un vrai `robots.txt`, le titre « Faire faire son étude de
  marché… », et 23 adresses.
- Les anciennes adresses (`/etudedemarche`, `/formation`…) sont toujours
  redirigées par le navigateur, pas par le serveur : un robot sans JavaScript
  y reçoit la page vide. Des redirections 301 dans `nginx.conf` seraient
  mieux ; non fait ici.

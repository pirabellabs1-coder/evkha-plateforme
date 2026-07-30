# Lot 4 (v2) — organisations, portefeuille de crédits, clients finaux

Première tranche du lot 4 du cahier des charges v2 : le **modèle économique**
côté serveur. C'est ce dont tout le reste de l'espace client dépend — une page
de commande sans solde à afficher ni crédit à débiter ne peut pas être écrite.

---

## 1. Ce que le dépôt savait faire, et ce qu'il ne savait pas

Constat avant d'écrire une ligne (règle 8) :

| Exigence | État réel |
|---|---|
| Organisation, plusieurs collaborateurs, un portefeuille partagé | **Inexistant.** Le dépôt ne connaît que `Customer`, une adresse e-mail isolée. |
| Solde de crédits | **Inexistant.** Un « crédit » est un `Order` pré-créé porteur d'un lien Tally, envoyé par e-mail. |
| Journal des mouvements | **Inexistant.** Aucun débit, aucun remboursement, aucune trace. |
| Client final réutilisable avec sa charte | **Inexistant.** Logo et couleurs vivent dans les variables du formulaire d'une commande, à ressaisir à chaque étude. |
| Paliers Solo / Pro / Pro Plus / Structure | `customers.SubscriptionTier` les déclare déjà. Réutilisés, pas redéclarés. |

`Customer` n'a **pas** été modifié : il reste la porte d'entrée du flux
Systeme.io en service. Le remplacer aurait touché `Order`, `intake`, `dashboard`
et la facturation existante pour un gain nul.

---

## 2. Le solde n'est pas un compteur

`PortefeuilleCredits` ne porte **aucun champ `solde`**. Le solde est la somme
algébrique de `MouvementCredit`.

Un compteur que l'on incrémente dérive dès le premier débit interrompu ou la
première double écriture, et rien ne permet alors de savoir lequel des deux
chiffres est vrai. Un journal est auditable ligne à ligne — exactement ce que
le §11 exige (« chaque mouvement de crédit est journalisé : date, motif,
document concerné, auteur »). Aux volumes en jeu, l'agrégat coûte moins qu'un
bug de solde.

Conséquence appliquée partout : l'expiration de fin de période est écrite comme
un **mouvement négatif**, jamais comme une remise à zéro. Deux chiffres, deux
vérités, c'est le défaut récurrent de ce dépôt (règle 5).

`quantite` est signée. Ajouter un type de mouvement n'oblige donc pas à
retoucher le calcul du solde (règle 4 : viser la classe, pas le cas).

---

## 3. Les trois garanties qui touchent à l'argent

### Aucun découvert

`debiter()` prend un **verrou de ligne** sur le portefeuille, puis lit le solde
et écrit le mouvement dans la même transaction. Sans ce verrou, deux commandes
lancées simultanément sur un solde de 1 liraient toutes les deux « 1
disponible » et passeraient toutes les deux.

`peut_commander()` existe pour l'écran de récapitulatif (§9.3) et est
explicitement **indicatif** : seul `debiter` fait autorité, parce que lui seul
verrouille.

### Aucun double débit

Garanti par une **contrainte d'unicité en base** sur
`(portefeuille, type, reference)`, pas par une vérification en Python : une
tâche Celery relancée après un incident réseau rejouerait sinon le débit. Ce
projet a déjà payé deux fois chaque chapitre pour une raison de cette famille.

### Aucun crédit perdu, aucun crédit offert

`rembourser()` **relit le montant sur le débit d'origine**. Laisser l'appelant
le fournir ouvrirait la porte à un remboursement supérieur au débit, sans que
rien dans le code ne le voie. Un remboursement sans débit correspondant est
refusé.

---

## 4. Le point de conception le plus délicat : quand rembourser

Le §11 dit « remboursement automatique en cas d'échec **définitif** ». Le mot
n'est pas décoratif.

Dans ce dépôt, `JobStatus.FAILED` est un état **rattrapable** : l'administrateur
relance un chapitre ou l'étude depuis le tableau de bord, et le §13 décrit
précisément ce parcours. Rembourser à chaque passage en `FAILED` offrirait donc
l'étude à quiconque échoue une fois puis relance.

Le remboursement est donc un **acte explicite** — `rembourser_job()`, appelé sur
un abandon —, jamais un effet de bord d'un statut. Un test échoue si quelqu'un
le branche sur `_fail`.

Symétriquement, une relance **doit** passer sans repayer : `debiter_pour_job()`
traite le refus d'un double débit comme un **succès**. Traiter ce refus comme un
échec bloquerait toute reprise sur incident — précisément ce que le §13 demande
de préserver.

---

## 5. Le branchement sur le moteur

Un portefeuille non branché serait du code mort. Ce dépôt en a l'expérience :
Gamma était intégré, testé, branché — et n'avait jamais tourné (règle 8).

`run_generation_job()` débite donc **avant le premier appel facturé**. Solde
insuffisant ou organisation suspendue : le job passe en `FAILED` avec
`CreditsInsuffisantsError`, sans qu'un seul euro d'API n'ait été dépensé.

### Coexistence avec le flux en service

Une commande **sans organisation** n'entraîne aucun débit et n'échoue pas : le
flux Systeme.io actuel est déjà payé autrement. Casser la production pour un
module qui n'y est pas encore branché serait absurde.

`Order` reçoit un champ `organisation` **nullable** — additif, aucune commande
existante n'est affectée. À défaut, l'organisation est déduite du client, et
**une ambiguïté ne se résout pas au hasard** : un client rattaché à deux
organisations ne déclenche aucun débit, avec une trace. Débiter le mauvais
portefeuille serait pire qu'un débit manquant, parce que personne ne le verrait.

---

## 6. Les formules réelles

Relevées sur `evkha.fr`, page « Partenariats PRO et abonnements » :

| Code | Cible | Crédits/mois | Prix | Par livrable | Crédit sup. |
|---|---|---|---|---|---|
| `solo` | Coach · Freelance | 2 | 129 € | 64,50 € | 59 € |
| `pro` | Agence · Cabinet | 3 | 189 € | 63,00 € | 55 € |
| `pro-plus` | Agence avec volume | 5 | 249 € | 49,80 € | 45 € |
| `structure` | Incubateur · Association · Réseau | 10 | 429 € | 42,90 € | 39 € |

```bash
python manage.py seed_formules
```

Deux garde-fous, chacun testé :

- le peuplement **n'écrase pas** une formule modifiée en administration. Le
  cahier des charges exige qu'une formule se crée et se modifie sans
  déploiement ; un seed qui réécrit tout défairait cette autonomie.
  `--forcer` existe pour réaligner explicitement.
- un test recalcule le **coût par livrable** et le compare aux 64,50 / 63 /
  49,80 / 42,90 € affichés publiquement. Si une formule change sans que la page
  change, les deux se contredisent devant le client — le test rend l'écart
  visible.

**Report des crédits : aucun**, conformément à la réponse de la cliente en
entretien. Les deux autres règles (`integral`, `plafonne`) existent en base et
sont testées, pour qu'un changement d'avis ne demande pas de migration.

---

## 7. Rôles

Le tableau du §12 est traduit dans une **table unique**, `services.DROITS`. La
dupliquer côté interface la ferait diverger du serveur au premier ajout
d'action.

Deux garde-fous :

- **aucun rôle d'organisation** n'obtient les droits réservés à EVKHA (corriger
  un socle, relancer une génération, modifier les trames, créer un type de
  document, doter un compte). Testé pour les trois rôles × trois actions ;
- un **membre révoqué** perd tous ses droits, quel que soit son rôle. Sans ce
  contrôle, révoquer un accès ne révoquerait rien ;
- le **dernier propriétaire** ne peut pas être révoqué : l'organisation
  deviendrait inadministrable et il faudrait intervenir en base.

---

## 8. Vérification

```bash
ruff check .        # 42, inchangé
mypy backend        # 102 erreurs dans 16 fichiers, inchangé
pytest              # vert — 78 tests ajoutés (61 + 17)
python manage.py makemigrations --check --dry-run   # No changes detected
```

Deux migrations, toutes deux additives :
`organisations/0001_initial` et `orders/0004_order_organisation` (nullable).

---

## 9. Ce qui reste du lot 4

Cette tranche couvre le §11 (crédits), le §12 (rôles) et le §9.2 (clients
finaux). Restent :

- **Stripe** — retenu comme prestataire. Les modèles portent déjà
  `reference_paiement` sur `Formule` et `AbonnementOrganisation`. Manquent le
  prélèvement à échéance, l'émission de factures, la proratisation et la relance
  sur échec de paiement. Il me faut pour cela les clés Stripe **posées dans
  l'environnement, jamais dans la conversation**, et la décision sur la
  suspension après échec de paiement (délai).
- **L'espace client lui-même** (§9.1, 9.3 à 9.7) : API + écrans React —
  commande, formulaire dynamique, suivi de génération, bibliothèque de
  livrables, assistance.
- **L'échéance mensuelle automatique** : `appliquer_echeance` existe et est
  testée, mais n'est pas encore branchée sur `CELERY_BEAT_SCHEDULE`. À faire en
  même temps que Stripe, l'échéance étant déclenchée par le paiement.
- **Rattacher les commandes existantes** à une organisation. Aujourd'hui le
  champ est vide partout, donc aucun débit n'a lieu : c'est volontaire pendant
  la coexistence, mais c'est aussi la raison pour laquelle **le débit n'a jamais
  tourné sur un dossier réel** (règle 7).

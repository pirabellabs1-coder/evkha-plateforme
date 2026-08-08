# Lot 3 — assemblage du livrable Word et conversion PDF

Le lot 0 a construit un moteur de rendu qui consomme une étude décrite en
JSON, avec des données factices. Le lot 1 a produit le socle, le lot 2 les
chapitres structurés. **Le lot 3 est le raccord**, plus la conversion PDF.

---

## 1. Ce qui a été livré

| Module | Rôle |
|---|---|
| `generation/rendu_word/donnees_graphiques.py` | Alimente un graphique depuis le socle, ou explique pourquoi c'est impossible |
| `generation/rendu_word/assemblage.py` | Traduit socle + chapitres en blocs de rendu, et tient le rapport |
| `generation/rendu_word/services.py` | `produire_docx(job)` — lit la base, rend le fichier |
| `generation/rendu_word/logo.py` | Récupère le logo du client final pour la couverture |
| `integrations/docx_pdf.py` | Word → PDF par LibreOffice, avec bouchon |
| `documents/livrable_word.py` | Enregistre les artefacts `DOCX` et `PDF` |
| `generation/management/commands/rendre_livrable.py` | Relecture d'un job réel, sans écriture en base |

`ArtifactKind.DOCX` existait dans le modèle depuis la migration initiale et
n'avait **jamais été produit**. C'est fait.

---

## 2. La règle qui structure tout le lot

> **Aucune valeur n'est fabriquée au rendu.**

Un chapitre ne porte pas de chiffres : il porte un type de visuel et des
identifiants du socle. Si le socle ne peut pas alimenter le type demandé, le
graphique est **abandonné**, et le motif est enregistré. Il n'est jamais
complété, jamais approché, jamais rempli d'un ordre de grandeur plausible.

La raison est asymétrique : un graphique inventé est indétectable à la
lecture, un graphique absent se voit.

Les refus effectivement implémentés et testés :

| Situation | Décision |
|---|---|
| Identifiant absent du socle | Abandon, identifiant nommé dans le motif |
| Unités hétérogènes sur un même axe | Abandon — chaque chiffre est juste, la figure serait fausse |
| Un seul chiffre | Abandon — une barre unique n'apprend rien |
| Part négative en camembert | Abandon |
| Série temporelle trouée | La série est écartée, **jamais interpolée** |
| Jauges ou radar sur des montants | Abandon — une échelle de 1 à 5 n'accueille pas des milliards d'euros |
| Risque sans probabilité ni impact | Ne compte pas (règle 1) |
| Type de graphique inconnu | Abandon, sans deviner |

Quand les chiffres sont bons et que seule la **forme** demandée est
impossible, le graphique est **converti** plutôt qu'abandonné : trois montants
demandés en courbes n'ont pas d'axe temporel, mais font des barres
parfaitement honnêtes. La conversion est tracée elle aussi.

---

## 3. Deux écarts relevés en branchant, et ce qui a été fait

### 3.1 Le contrat de chapitre ne pouvait pas produire un document dense

Le contrat du lot 2 ne prévoyait qu'un champ `contenu` en texte libre par
section. Or le document validé par la cliente porte **52 % de ses mots dans
des tableaux**, avec une médiane de douze mots par paragraphe. Rendre ce
contrat tel quel aurait reproduit mécaniquement le mur de texte qu'elle a
refusé — le schéma l'aurait permis, rien ne l'aurait empêché.

`Section` reçoit donc un champ `tableau` facultatif (`entetes`, `lignes`,
`source`), avec contrôle de la largeur des lignes. Les chapitres produits avant
cet ajout restent valides et se rendent en prose.

Complément indispensable, sans lequel le champ serait resté lettre morte :
**deux blocs de consigne ajoutés au prompt de chapitre**, dans
`chapitres/runner.py` et non dans les 72 fichiers de prompt — les répéter
soixante-douze fois garantirait qu'ils divergent (règle 5).

- `_bloc_forme()` : l'information vit dans les tableaux, le `contenu` est une
  amorce de deux à trois phrases, un encadré au moins par chapitre.
- `_bloc_visuels()` : le catalogue des quinze types, **plus le profil du
  secteur** porté par le socle — ce qu'il faut privilégier, ce qui est hors
  sujet.

À l'assemblage, une prose plus longue que 55 mots est ramenée à une amorce,
coupée **à la phrase** et jamais au milieu d'un groupe nominal.

### 3.2 La pyramide des âges ne peut pas être alimentée

Le type existe au catalogue et les profils « santé, bien-être et soins » et
« services à la personne » le privilégient. Mais le référentiel du socle, validé
en lot 1, ne porte **aucune structure démographique** : ni tranches d'âge, ni
effectifs par tranche.

Ce n'est pas un bug, c'est un manque. Il est donc déclaré explicitement dans
`_pyramide()` et remonte dans le rapport d'assemblage, au lieu d'être subi
ailleurs. Deux issues possibles, et c'est une décision :

1. **étendre le référentiel** du lot 1 avec des identifiants démographiques ;
2. **retirer le type** du catalogue et des profils concernés.

En attendant, le repli sectoriel choisit le type pertinent suivant : les
documents « santé » conservent des visuels, simplement pas celui-là.

---

## 4. La charte du client final

Elle est lue sur la soumission de la commande, jamais sur un profil
persistant : la charte appartient au **client du client** et change à chaque
étude pour un même abonné B2B. `extract_branding` porte déjà cette lecture ;
elle n'est pas refaite (règle 5).

Le logo pose un problème que la chaîne HTML n'avait pas : le formulaire fournit
une **URL**, le navigateur du lecteur allait la chercher. Un `.docx` embarque
ses images. Il faut donc récupérer les octets au rendu — le seul appel réseau
sortant de toute la chaîne, déclenché par une URL saisie dans un formulaire.
Il est borné explicitement :

- schémas `http` et `https` uniquement ;
- délai de 5 s, une seule tentative ;
- 5 Mo maximum ;
- format reconnu par sa **signature binaire**, jamais par l'en-tête
  `Content-Type`, qui n'engage que celui qui l'envoie ; SVG refusé, python-docx
  ne sachant pas l'embarquer.

Tout échec laisse la couverture sans logo et trace le motif : un logo manquant
est un défaut d'apparence, pas une raison de perdre un livrable payé.

---

## 5. Word puis PDF, dans cet ordre

Le PDF est une **photographie du Word**, jamais un second rendu depuis le HTML :
deux moteurs différents livreraient au même client deux fichiers divergents sur
la pagination.

`LibreOfficeConvertisseurDocx` isole le profil utilisateur
(`-env:UserInstallation`) et travaille dans un répertoire temporaire : sans
cela, deux conversions simultanées se disputent le même profil, et deux jobs de
même radical écrasent leur sortie.

Un échec de conversion **ne perd pas le Word** : l'artefact `DOCX` est
enregistré prêt, l'artefact `PDF` marqué en échec, et l'exception n'est pas
propagée. L'échec reste visible en base, ce qui est le point.

`assemble_document` — l'ancienne chaîne HTML/PDF — reste en place et inchangée.
Les deux coexistent le temps de la bascule : remplacer la chaîne en service
avant d'avoir vu un livrable Word sur un dossier réel serait parier sur du code
que personne n'a lu en production (règle 7).

---

## 6. Vérification

### Le document produit par le chemin d'assemblage

Mesuré sur un livrable de 22 chapitres rendu **par `assembler_etude`**, pas par
la fixture du lot 0 :

| Indicateur | Référence | Démo lot 0 | **Lot 3** |
|---|---|---|---|
| Mots | 11 580 | 10 028 | **10 656** |
| Longueur médiane d'un paragraphe | 12 | 8 | **8** |
| Paragraphes de plus de 60 mots | 12 % | 10 % | **0 %** |
| Mots situés dans des tableaux | 58 % | 59 % | **60 %** |
| Tableaux | 114 | 123 | **111** |
| Graphiques | 11 | 14 | **11** |

Rapport d'assemblage : `22 chapitres, 66 tableaux, 11/11 graphiques`, aucun
abandon, aucune conversion.

La densité validée par la cliente est conservée par le chemin réel. Les
paragraphes longs tombent à 0 % contre 12 % dans la référence : le plafond de
55 mots est plus strict que la référence, ce qui va dans le sens du retour reçu
(« toujours trop de texte »).

### Les quatre garde-fous, à la ligne de base

```bash
ruff check .        # 42, inchangé
mypy backend        # 102 erreurs dans 16 fichiers, inchangé
pytest              # vert — 49 tests ajoutés pour ce lot
python manage.py makemigrations --check --dry-run   # No changes detected
```

Aucune migration : le champ `tableau` vit dans le JSON de `payload`, pas dans
une colonne.

---

## 7. Ce qui reste ouvert

- **La conversion PDF n'a jamais tourné pour de vrai.** `soffice` et
  `libreoffice` sont absents de la machine de développement ; seul le bouchon a
  été exercé. Il faut `libreoffice-writer` sur le VPS, et une première
  conversion réelle avant toute livraison client. Tant que ce n'est pas fait,
  le nombre de pages vaut 0, c'est-à-dire **inconnu** — jamais « conforme ».
- **Aucune génération réelle n'a été lancée** (interdit sans accord, ~2 à 4,60 €
  par dossier). Les chapitres de la vérification ci-dessus sont fabriqués à la
  main au format du contrat. La preuve définitive reste un dossier réel
  (règle 7).
- **Décision attendue sur la pyramide des âges** (§3.2).
- **Bascule** : `assemble_document` reste la chaîne en service. Le branchement
  du livrable Word sur le flux de production, et le sort de WeasyPrint, ne sont
  pas dans ce lot.
- **Recalibrage du volume** : `blueprints.py` vise environ 32 400 mots quand la
  référence en fait 11 580. L'écart n'est pas traité ici et conditionne le
  budget par étude.

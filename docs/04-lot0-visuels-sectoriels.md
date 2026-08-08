# Lot 0 — visuels du livrable et dépendance au secteur

## La demande

Après validation de la densité de texte (« c'est parfait »), la cliente a
demandé deux choses :

1. **plus de graphiques et d'éléments visuels**, pour rendre le document plus
   agréable ;
2. avec une réserve explicite : **« ça dépend toujours du secteur
   d'activité »**.

Le second point est le plus structurant. Il interdit la solution évidente —
attribuer un type de graphique à chaque numéro de chapitre — parce qu'elle
produirait une saisonnalité mensuelle dans une étude sur le conseil aux
entreprises et une pyramide des âges dans une étude sur la logistique.

## Ce qui a été livré

### Le catalogue passe de 4 à 15 types

`generation/rendu_word/graphiques.py`

| Famille | Types |
|---|---|
| Comparaisons | `barres`, `barres_horizontales`, `barres_groupees`, `barres_empilees` |
| Évolutions | `courbes`, `aires` |
| Répartitions | `camembert`, `anneau`, `entonnoir` |
| Évaluations | `radar`, `jauges`, `matrice_positionnement`, `carte_chaleur` |
| Démographie et temps | `pyramide_ages`, `chronologie` |

Tous respectent les contraintes du lot 0 : fond `#FDFBF6`, séries dans l'ordre
principale / or bronze / crème / rose grisé, aucun cadre, 200 dpi, 2 000 px de
large.

### Deux composants Word supplémentaires

`generation/rendu_word/composants.py`

- **`matrice_quadrants`** — grille 2×2 à cases colorées. Volontairement
  générique et non nommée « SWOT » : la même forme sert au SWOT, à la matrice
  d'Ansoff, au couple probabilité/impact, à la grille effort/gain. La nommer
  d'après un seul de ses usages aurait conduit à en écrire quatre (règle 4).
- **`barre_repartition`** — bande horizontale découpée au prorata, libellés en
  dessous. Deux rangées et non une seule : c'est ce qui lui donne une forme que
  ni l'encadré (1 rangée × 2 cellules) ni la grille de chiffres (1 × 3) n'ont.
  Sans cette distinction, toute mesure du document qui classe les tableaux par
  leur forme confondrait les trois — c'est arrivé pendant le développement, et
  deux tests ont commencé à mesurer autre chose que ce qu'ils annonçaient.

### Le choix des visuels dépend du secteur

`generation/rendu_word/secteurs.py` — nouveau module. Il ne dessine rien. Il
répond à une seule question : *pour ce secteur, quels types de graphiques
racontent quelque chose, et lesquels sont hors sujet ?*

Treize profils déclarés (luxe et joaillerie, restauration, commerce de détail,
numérique, services aux entreprises, santé et bien-être, services à la
personne, artisanat et industrie, tourisme, immobilier, transport et
logistique, agroalimentaire, formation) plus un profil générique de repli.

Chaque profil déclare :

- ses **mots-clés** de rattachement, appliqués au champ libre du formulaire ;
- ses **types privilégiés**, du plus au moins pertinent ;
- ses **types à éviter** — sans cette liste, le modèle propose une pyramide des
  âges dès qu'un chapitre parle de clientèle, y compris en B2B ;
- ses **angles** : ce que les visuels doivent montrer, en clair.

Exemple de l'écart obtenu, sur le même code et la même fixture :

| Secteur | Quatre premiers visuels |
|---|---|
| Joaillerie | `entonnoir`, `matrice_positionnement`, `courbes`, `anneau` |
| Restauration | `aires`, `barres_empilees`, `camembert`, `entonnoir` |
| Services aux entreprises | `entonnoir`, `barres_horizontales`, `radar`, `matrice_positionnement` |
| Services à la personne | `pyramide_ages`, `carte_chaleur`, `barres_horizontales`, `entonnoir` |

### Le rattachement absorbe les flexions

Une comparaison mot à mot exacte échoue sur toutes les flexions du français :
« ostéopathie » ne vaut pas « ostéopathe », « transporteur » ne vaut pas
« transport », « boulanger » ne vaut pas « boulangerie ». Énumérer ces
variantes dans les listes de mots-clés aurait corrigé des cas au lieu de la
classe de défaut, et la liste aurait raté la variante suivante.

La règle retenue est morphologique : **deux mots d'au moins six caractères qui
partagent leurs six premiers désignent le même métier**. En dessous de ce
seuil, et pour les mots-clés composés, la présence littérale reste exigée —
« bar » ou « vin » ne peuvent pas être approchés sans produire des
rattachements absurdes. La contre-épreuve est testée : « cabaret » et
« barbecue » ne sont pas rattachés à la restauration.

### Le contrat de chapitre suit

`generation/chapitres/schema.py` — l'énumération `TypeGraphique` passe de 7 à
15 valeurs. Elle reste écrite à la main pour rester vérifiable statiquement,
mais un test compare l'énumération, le catalogue et la table de rendu, et
échoue dès que les trois divergent (règle 5).

`graphiques.resume_catalogue()` et `secteurs.consigne_visuelle()` produisent
les fragments de prompt correspondants : le modèle reçoit ce qu'il peut
employer, ce qu'il doit éviter, et les angles à couvrir pour ce métier.

## Vérification

Mesures relevées sur les documents réels, pas sur la fixture.

| Indicateur | Référence | v2 (validée) | v3 |
|---|---|---|---|
| Mots | 11 580 | 9 804 | 10 028 |
| Longueur médiane d'un paragraphe | 12 | 8 | 8 |
| Paragraphes de plus de 60 mots | 12 % | 10 % | 10 % |
| Mots situés dans des tableaux | 58 % | 59 % | 59 % |
| Tableaux | 114 | 118 | 123 |
| **Graphiques distincts** | **11** | **10** | **14** |

La densité validée par la cliente est intacte : les images ne coûtent pas de
mots, et les deux nouveaux composants sont des tableaux courts.

Le test de volume qui encadrait le nombre d'images dans une fourchette de
±30 % autour de la référence a été remplacé par un **plancher** : la référence
a été composée à la main avec onze images, la demande explicite est d'aller
au-delà. Encadrer serait interdire ce qui a été demandé.

Quatre garde-fous, revenus à la ligne de base :

```bash
ruff check .        # 42, inchangé
mypy backend        # 102 erreurs dans 16 fichiers, inchangé
pytest              # vert
python manage.py makemigrations --check --dry-run   # No changes detected
```

## Ce qui reste ouvert

- **Le nombre de pages n'est pas vérifiable ici.** `soffice`, `libreoffice`,
  `pdftoppm` et `pdfinfo` sont absents de la machine : le critère « 55 à
  60 pages » du lot 0 ne peut pas être contrôlé autrement qu'à l'ouverture dans
  Word. Il l'a été à l'œil, pas à la mesure.
- **La police Aptos est absente localement**, matplotlib lui substitue DejaVu
  Sans dans les figures. Les polices sont bien posées sur les runs Word ; le
  rendu des étiquettes de graphique différera légèrement sur un poste équipé.
- Les treize profils couvrent les secteurs les plus probables du portefeuille,
  pas la totalité de la nomenclature. Un secteur non reconnu retombe sur le
  profil générique, qui produit toujours un document complet — jamais un
  document sans visuel (règle 1).

# Lot 4 — passe de vérification du livrable

Les lots 1 à 3 fabriquent le document. Le lot 4 le **relit** et dit s'il peut
partir.

Il ne relit pas les charges utiles des chapitres : il relit le **fichier
livré**. C'est la leçon la plus chère du projet — le markdown était propre, la
barrière passait, et le document partait amputé parce que quelque chose le
refaisait après le contrôle (règle 3). Ce qui se vérifie doit être ce qui se
lit.

---

## 1. Modules

| Module | Rôle |
|---|---|
| `generation/verification/lecture.py` | Ouvre le `.docx` et en extrait la matière comparable |
| `generation/verification/controles.py` | Les six contrôles, indépendants et sans effet de bord |
| `generation/verification/rapport.py` | Anomalies, gravités, sérialisation |
| `generation/verification/services.py` | Enchaîne les contrôles, ouvre l'incident |
| `generation/management/commands/verifier_livrable.py` | Relecture d'un fichier, sans écriture |

La passe est appelée par `documents/livrable_word.py`, **avant** l'enregistrement
des artefacts. À ce point, plus rien ne refait le document.

---

## 2. Les six contrôles

| Contrôle | Ce qu'il cherche | Bloquant quand |
|---|---|---|
| `integrite` | Document amputé | Aucun tableau, tableau sans cellule remplie, aucun texte, chapitre absent |
| `chiffres_hors_socle` | Valeur sans source | Socle vide, ou document sans le moindre chiffre |
| `couverture_socle` | Source jamais citée | Donnée obligatoire absente du socle, ou référentiel inexistant |
| `hierarchie_marches` | Emboîtement TAM ≥ SAM ≥ SOM | Inversion lue dans le texte, ou hiérarchie absente partout |
| `densite` | Retour du mur de texte | — (avertissements seulement) |
| `visuels` | Figures abandonnées au lot 3 | Aucune des figures demandées n'a pu être alimentée |

### Trois gravités, et pourquoi la frontière compte

**Bloquante** est réservé à ce qui se juge sans ambiguïté. Y placer un contrôle
incertain reviendrait à arrêter des livrables corrects — et une barrière qui
crie à tort finit débranchée. C'est arrivé sur ce projet.

C'est pourquoi **un chiffre hors socle n'est pas bloquant**. La passe ne
recalcule pas l'arithmétique interne des chapitres : une somme légitime de deux
valeurs du socle apparaît donc comme hors socle. Elle est nommée, avec son
extrait, et un humain tranche.

### `hierarchie_marches` : trois issues, pas deux

- inversion lue dans le texte → **bloquante** : le document ment ;
- niveaux présents uniquement dans un graphique → **avertissement** : ils sont
  sous les yeux du lecteur, mais la passe ne lit pas les pixels, et elle doit le
  dire au lieu de conclure ;
- niveaux absents partout → **bloquante** : une étude de marché qui n'énonce
  nulle part son dimensionnement n'est pas livrable.

Ce contrôle est une **seconde évidence** : le socle a déjà validé
l'emboîtement au lot 1. On le revérifie ici sur les valeurs telles qu'elles
figurent dans le fichier, parce qu'un socle juste et un document faux est
précisément le cas que le lot 1 ne peut pas voir (règle 9).

---

## 3. L'angle mort trouvé en confrontant la passe à un vrai livrable

Premier essai sur le document du lot 3 : la passe a déclaré absentes toutes les
données de dimensionnement du marché. Elles y étaient — **dans les
graphiques**.

Un chiffre porté par une figure est un pixel. Il est parfaitement sous les yeux
du lecteur et parfaitement invisible à une relecture du texte. Sans correction,
la passe produisait des motifs faux — pires qu'absents (règle 2).

Le lot 3 sait quels identifiants ont alimenté quelle figure :
`RapportAssemblage.identifiants_rendus` a été ajouté et transmis à la passe.
`couverture_socle` et `hierarchie_marches` s'en servent.

C'est aussi la réponse à la question de la règle 9 — *que ne regarde pas mon
contrôle ?* : **il ne lit pas les images**. C'est écrit dans le module, et le
rapport le dit quand le cas se présente.

---

## 4. Ce que la passe ne regarde pas

À écrire noir sur blanc, parce que c'est exactement là où une réparation ne
chercherait pas non plus.

- **Les nombres sans unité.** « Trois portes d'entrée », « 0-30 j »,
  « chapitre 12 » ne sont pas des affirmations de marché. Les contrôler
  produirait des motifs faux en masse. Un test verrouille ce périmètre pour
  qu'il ne dérive pas.
- **L'arithmétique interne** d'un chapitre : une somme, un écart calculé entre
  deux valeurs du socle ne sont pas recalculés.
- **Le contenu des images**, cf. §3.
- **La véracité des sources.** La passe compare au socle, pas au monde. Qu'un
  chiffre soit dans le socle ne dit pas qu'il est vrai — cela dit qu'il a été
  établi, tracé et validé en amont.

---

## 5. Vérification

Les deux essais qui comptent ont été menés sur des fichiers réels, pas sur des
objets en mémoire (règle 7).

**Livrable conforme** — 22 chapitres citant tous les identifiants obligatoires
du référentiel :

```
CONTROLE : 6 contrôles, aucune anomalie. | livrable : True
```

**Livrable défaillant** — socle aux identifiants inventés, chiffres non cités :

```
CONTROLE : 6 contrôles, 5 bloquante, 4 avertissement. | livrable : False
  [bloquante]     couverture_socle    — `marche_mondial_taille` est obligatoire et absente du socle.
  [avertissement] chiffres_hors_socle — « 80 % » n'a pas d'équivalent dans le socle ni dans le brief.
                                        … 80 % des testeurs reformulent l'offre
  [avertissement] hierarchie_marches  — L'emboîtement n'est lisible que dans les graphiques.
```

Chaque motif porte son extrait : il est **retrouvable dans le document par un
lecteur** (règle 2).

Un test injecte un chiffre inventé dans un chapitre, rend le `.docx`, et vérifie
que la passe le retrouve **dans le fichier**. C'est la preuve qui compte.

### Les quatre garde-fous

```bash
ruff check .        # 42, inchangé
mypy backend        # 102 erreurs dans 16 fichiers, inchangé
pytest              # vert — 43 tests ajoutés
python manage.py makemigrations --check --dry-run   # No changes detected
```

Aucune migration : le rapport est sérialisé dans `OperationalIncident.details`,
comme la barrière existante. Pas de nouveau modèle pour un objet dont la durée
de vie est celle d'un assemblage.

---

## 6. Ce qui reste ouvert

- **`gate.py` n'a pas été touché.** Ses 1 307 lignes d'analyse textuelle
  couvrent l'ancienne chaîne, qui reste en service. Une grande partie perd sa
  raison d'être avec la sortie structurée, mais les retirer avant d'avoir vu la
  nouvelle chaîne tourner sur des dossiers réels ferait perdre des garde-fous
  éprouvés en production. C'est une décision à prendre après la bascule, pas
  avant.
- **La passe ne répare rien**, délibérément : une réparation qui juge sur la
  même évidence que le contrôle se donne raison toute seule (règle 9). Elle
  produit un constat, destiné à un humain et au blocage de l'envoi.
- **Le blocage de l'e-mail n'est pas branché** sur ce rapport. `tasks.py`
  bloque déjà l'envoi sur l'ancienne barrière ; brancher la nouvelle relève de
  la bascule.
- **Aucune génération réelle** n'a alimenté cette passe. Les documents vérifiés
  sont assemblés à la main au format du contrat. La preuve définitive reste un
  dossier réel (règle 7).

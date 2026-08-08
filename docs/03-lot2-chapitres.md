# Lot 2 — Orchestration des chapitres

Livré le 29 juillet 2026. **Inerte par défaut** : `EVKHA_SOCLE_ENABLED=false`.

## Le contrat de chapitre

Un chapitre ne rend plus du texte libre, mais une structure :

```json
{
  "chapitre": 4,
  "titre": "Avantages et contraintes structurelles du secteur",
  "sections": [{"titre": "…", "contenu": "…"}],
  "donnees_utilisees": ["marche_national_taille", "tam"],
  "graphiques": [{"type": "barres", "titre": "…", "donnees_ids": ["tam", "sam"]}],
  "resume": "…"
}
```

Deux conséquences directes.

**Un chapitre ne peut plus produire un chiffre.** Tout identifiant de
`donnees_utilisees` doit exister dans le socle verrouillé. C'est un contrôle,
pas une consigne de prompt.

**Un graphique ne peut plus contredire le texte qu'il illustre.** Il ne porte
aucune valeur — seulement des identifiants du socle, résolus au rendu. C'est
l'inverse du moteur actuel, où les valeurs du graphique viennent d'un JSON que
le modèle écrit dans sa prose, sans aucun rapprochement avec le socle.

## Contrôles

| Contrôle | Motivation |
|---|---|
| Donnée absente du socle | Traduction du principe « un chapitre n'a jamais le droit de produire un chiffre ». |
| Graphique adossé à une donnée non déclarée | Un visuel ne repose que sur ce que le chapitre assume. |
| Numéro de chapitre incohérent | Le modèle a répondu pour un autre chapitre. |
| Résumé hors de 150–250 mots | Trop court il perd des chiffres pour la suite, trop long il sature le contexte des chapitres suivants. |
| Deux sections de même titre | Signe d'une génération qui tourne en rond. |
| Type de graphique inconnu | Le rendu doit savoir dessiner chaque type ; un inconnu casserait le lot 3. |

## Prompts versionnés

**72 fichiers** exportés depuis `prompt_library.py` vers
`prompts/<document>/chapitre_NN.md`, verbatim. Ces fichiers sont désormais la
source de vérité.

L'interpolation est volontairement minimale — `{{ nom }}`, ni boucle ni
condition. Une variable inconnue est **laissée visible et signalée** : la
remplacer par du vide produirait un prompt amputé sans que rien ne le dise.

Le bandeau de documentation en tête de fichier est retiré avant l'envoi au
modèle. Il cite la syntaxe des variables, que l'interpolation prendrait pour de
vraies variables — défaut réellement rencontré pendant le développement, et
couvert par un test depuis.

`python manage.py exporter_prompts --verifier` contrôle la complétude sans
rien écrire.

## Orchestration générique

`generation/chapitres/configuration.py` est le **seul** endroit où un type de
document se déclare : dossier de prompts, nombre de tentatives, bornes du
résumé. Le chapitrage vient de `blueprints.py`.

Ajouter un type de document demande donc : des fichiers de prompts, et une
entrée dans ce registre. Aucune ligne du moteur ne change — il n'y a ni
constante `22`, ni `if deliverable_type == …` dans le chemin d'exécution.

## Reprise sur échec

Chaque chapitre est une tâche Celery indépendante et **idempotente** : un
chapitre déjà produit est rendu tel quel, sans appel au modèle. Une étude n'est
plus une tâche unique de trente minutes qu'un redémarrage de worker perd en
entier.

Trois tentatives par chapitre, temporisation exponentielle (30 s puis 120 s).
Les motifs du refus précédent sont **réinjectés** dans la tentative suivante :
on ne demande pas « fais mieux », on dit ce qui a été refusé.

Après trois échecs, l'étude passe en `intervention_requise`, un incident HIGH
est ouvert, et **aucun e-mail client ne peut partir**.

> Lecture retenue de « rejouée jusqu'à trois fois » : **trois tentatives au
> total** (un essai, deux reprises). Réglable par `tentatives_max` dans la
> configuration, sans toucher au code.

## Critères de recette

| Critère | État | Preuve |
|---|---|---|
| Une donnée du chapitre 3 se retrouve à l'identique partout | **structurellement garanti** | Un chapitre ne peut référencer qu'un identifiant du socle. Reste à vérifier sur trois études réelles. |
| Un chapitre peut être régénéré seul | **vérifié** | `test_regenerer_un_chapitre_seul_n_altere_pas_les_autres` |
| Un échec n'interrompt pas l'étude et ne déclenche aucun e-mail | **vérifié** | `test_apres_trois_echecs_l_etude_passe_en_intervention_requise` |
| Ajouter un type ne demande que prompts + configuration | **vérifié** | `test_le_nombre_de_chapitres_vient_de_la_configuration` |
| Rapport de contrôle sans valeur hors socle | **lot 4** | — |
| Word et PDF conformes | **lot 3** | — |

## Vérification

| Contrôle | Référence | Après le lot 2 |
|---|---|---|
| `pytest` | vert, 672 tests | **vert, 731 tests** |
| `ruff check .` | 42 | **42** (aucune ajoutée) |
| `mypy backend` | 102 / 16 fichiers | **102 / 16** (aucune ajoutée) |
| `makemigrations --check` | vert | **vert** |

Le paquet `generation/chapitres` est entièrement propre sous mypy.

Mesure de bout en bout sur la base locale (bouchon, aucun appel réseau) :
socle 29 données, **22 chapitres structurés**, document rendu en 22 sections,
régénération du chapitre 4 sans altérer le chapitre 5.

## Fichiers

| Fichier | Rôle |
|---|---|
| `generation/chapitres/configuration.py` | Registre des types de documents |
| `generation/chapitres/fichiers_prompts.py` | Lecture et interpolation des prompts |
| `generation/chapitres/schema.py` | Contrat de sortie + contrôles |
| `generation/chapitres/runner.py` | Prompt, appel contraint, validation |
| `generation/chapitres/services.py` | Persistance, régénération, blocage |
| `generation/chapitres/tasks.py` | Tâches Celery, reprise exponentielle |
| `generation/chapitres/stub.py` | Chapitre de démonstration |
| `generation/management/commands/exporter_prompts.py` | Migration des prompts |
| `prompts/**/chapitre_NN.md` | 72 prompts versionnés |
| `tests/test_lot2_chapitres.py` | 29 tests |

## Limites assumées

- **Le contenu produit reste celui du bouchon.** Ce lot vérifie la mécanique et
  les contrôles, pas la qualité éditoriale. Celle-ci ne se juge que sur une
  génération réelle, qui demande votre accord.
- **`prompt_library.py` n'est pas supprimé** : l'ancien moteur s'en sert encore.
  Sa suppression viendra à la bascule, pas avant.
- **Le calibrage des longueurs n'est pas traité.** Les cibles de `blueprints.py`
  visent environ 32 400 mots quand le document de référence en fait 12 647.
  C'est une décision séparée, hors périmètre du lot 2.

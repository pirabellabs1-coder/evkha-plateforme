# Lot 1 — Socle de données verrouillé

Livré le 29 juillet 2026. **Inerte par défaut** : `EVKHA_SOCLE_ENABLED=false`.
L'ancien moteur reste seul en service tant que la bascule n'est pas décidée.

## Ce que ça change

Aujourd'hui, le socle est **déduit du texte après l'avoir écrit**, par
expressions régulières (`coherence.py`). Un chiffre halluciné au chapitre 1
devient la vérité de l'étude, et ce que la regex rate n'est verrouillé nulle
part.

Désormais, le socle est **produit avant toute rédaction**, par un appel dédié
dont la sortie est contrainte par un schéma JSON et validée contre un
référentiel fermé d'identifiants.

## Hypothèses appliquées

Faute de réponse, ces trois hypothèses ont été retenues et sont **réversibles**.

1. **Référentiel** dérivé des 21 chapitres du document Joalie v4 : 29
   identifiants pour l'étude de marché, 5 pour l'étude de la concurrence.
   Sectoriellement neutres. À amender avec la cliente.
2. **Chiffres dérivés autorisés**, mais ils doivent déclarer leur filiation
   (`derivee_de`). Les interdire rendrait les chapitres 14, 15 et 19
   impossibles à écrire ; les autoriser sans traçabilité rouvrirait la faille.
3. **Cohabitation** : le nouveau socle vit à côté de `CoherenceFact` sans le
   remplacer.

## Ce qui est contrôlé

Le validateur refuse — et déclenche une nouvelle tentative, jamais un passage
en force :

| Contrôle | Motivation |
|---|---|
| Identifiant hors référentiel | Deux formulations du même indicateur ne peuvent plus créer deux faits distincts qui ne se contredisent jamais. |
| Identifiant en double | Une donnée, une valeur. |
| Donnée obligatoire absente | Règle 1 du `CLAUDE.md` : un contrôle sans donnée est un échec, pas un succès. |
| Périmètre non conforme | Confusion mondial/continental, défaut réellement constaté. |
| Unité incompatible | Un taux de croissance en milliards d'euros. |
| Donnée `observee` sans source | Une donnée observée sans source est une estimation qui s'ignore. |
| Filiation pointant dans le vide | Un dérivé doit se rattacher à une donnée présente. |
| TAM < SAM, ou SAM < SOM | Défaut constaté sur le run `010e3bf2`. |
| Continent ≥ monde | Un continent n'est pas plus grand que le monde. |

L'énumération des identifiants est **injectée dans le schéma d'outil** : l'API
refuse un identifiant inconnu avant même notre validateur.

## Correction manuelle

Exigence du cahier des charges : la cliente doit pouvoir rectifier un chiffre
avant que l'étude ne se construise dessus.

`/admin/generation/socledonnees/` — le champ `contenu` est éditable. Toute
modification **est revalidée** : une correction humaine n'échappe pas aux
contrôles. Deux actions : « Revalider » et « Régénérer », cette dernière
invalidant tous les chapitres, comme le cahier des charges l'impose.

## Fichiers

| Fichier | Rôle |
|---|---|
| `generation/socle/referentiel.py` | Liste fermée des identifiants |
| `generation/socle/schema.py` | Modèles Pydantic + contrôles croisés |
| `generation/socle/prompt.py` | Prompt de la passe 1 |
| `generation/socle/builder.py` | Appel contraint, validation, reprise |
| `generation/socle/services.py` | Persistance, verrouillage, régénération |
| `generation/socle/stub.py` | Socle de démonstration (dev et CI) |
| `generation/models.py` | Modèle `SocleDonnees` (+ migration `0011`) |
| `generation/admin.py` | Consultation et correction |
| `integrations/claude.py` | `complete_structured()` et `StructuredResult` |
| `tests/test_lot1_socle.py` | 30 tests |

`complete_structured` s'appuie sur un protocole **séparé** de `ClaudeClient` :
l'ajouter au contrat existant aurait cassé les objets doubles des tests qui
n'implémentent que `complete()`.

## Vérification

| Contrôle | Référence | Après le lot 1 |
|---|---|---|
| `pytest` | vert, 672 tests | **vert, 702 tests** |
| `ruff check .` | 42 erreurs | **42** (aucune ajoutée) |
| `mypy backend` | 102 erreurs / 16 fichiers | **102 / 16** (aucune ajoutée) |
| `makemigrations --check` | vert | **vert** |

Le paquet `generation/socle` est **entièrement propre sous mypy**.

Mesure sur la base locale (bouchon, aucun appel réseau) : 29 données produites,
socle valide en 1 tentative, coût 0,0332 €.

## Reste à trancher

- Le référentiel est-il complet et correctement nommé ? C'est la seule question
  qui engage la suite : les lots 2 et 4 s'y adossent.
- Périmètre de `segments_clientele`, `concurrents`, `tendances`, `risques` :
  les structures existent et sont validées, mais le prompt ne les exige pas.
- Étude de la concurrence : 5 identifiants seulement, l'essentiel du socle EC
  vivant dans `concurrents`. À confirmer.

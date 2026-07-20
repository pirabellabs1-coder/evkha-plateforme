# Journal des générations réelles EVKHA

Inspiré de `results.tsv` de `karpathy/autoresearch` : chaque génération API
Claude est une **expérience**, chaque expérience est **loggée** avec son
verdict et ses mesures. Sans ce journal, chaque défaut est un incident isolé
et les leçons ne se cumulent pas.

Objectif : à chaque nouveau défaut nommé par la cliente ou par le gate,
   1. On identifie la CLASSE du défaut (règle 4 du `CLAUDE.md`).
   2. On corrige côté code (prompt, check, blueprint).
   3. On rejoue sur le doc existant si possible ; sinon on note en `blocked`
      et on attend la prochaine génération réelle pour valider.
   4. On enregistre ici l'issue de l'expérience : `keep` (correction
      efficace), `discard` (correction sans effet ou pire), `blocked` (défaut
      identifié mais pas encore validé sur un doc réel).

## Colonnes

| Colonne | Type | Contenu |
|---|---|---|
| `date` | ISO | jour du run |
| `job_id` | UUID court | 8 premiers hex de `GenerationJob.id` |
| `commit` | sha court | commit du code utilisé pour le run |
| `livrable` | code | `BP`, `EM`, `EC`, `STR` |
| `cout_eur` | float | coût réel API Anthropic |
| `duree_min` | float | temps de génération (hors export) |
| `gate_failures` | int | nombre de failures du gate final |
| `retours_client` | int | défauts nommés par Évangéline à posteriori |
| `verdict` | enum | `keep` / `discard` / `blocked` |
| `commentaire` | texte | ce qui a été appris de ce run |

## Runs

| date | job_id | commit | livrable | coût € | durée min | gate | retours | verdict | commentaire |
|------|--------|--------|----------|--------|-----------|------|---------|---------|-------------|
| 2026-07-19 | `c3798821` | `e23bbac` | BP | 1,70 | 21,9 | 60 | — | discard | SYNAPSES v2 — brief avec fourchettes de mon cru, modèle les recopie 48× |
| 2026-07-19 | `60b3e577` | `e23bbac` | BP | 1,54 | 21,8 | 12 | 0 bloquant | **keep** | SYNAPSES v3 — brief nettoyé, chiffres uniques, Évangéline valide sur la forme et le fond |

## Ce qui a été appris (par run)

### 2026-07-19 SYNAPSES v2 — `c3798821`

- **48 fourchettes** produites par le modèle : cause = fourchettes recopiées du brief que j'avais mis dans `ELEMENTS_A_RETENIR` (« TCAC 14-16 % », « seuil 180-280 kEUR »). Correction : les valeurs client vont dans leurs champs Tally dédiés, pas dans les champs de contexte narratif.
- **10 divergences** dont 5 faux positifs : cause = check `chiffre contre chiffre` en simple proximité. Correction : phase 25 → exigence de liaison syntaxique + mots de rupture.
- **1 niveau de marché verrouillé** au lieu de 3 : cause = motif regex trop rigide. Correction : phase 25 → pattern universel + discrimination par qualificatif.

### 2026-07-19 SYNAPSES v3 — `60b3e577`

- **48 → 5 fourchettes** (÷ 10) grâce au brief nettoyé + consigne prompt renforcée.
- **12 failures gate** dont 1 vraie divergence (apport 150k vs 180k), 3 hallucinations chiffrées détectées par le nouveau check `coherence_chiffree` vs brief, 5 fourchettes récidivantes, 1 verticale (« bureaux prives » vs « bureaux privatifs »).
- Corrections dérivées :
  - **Phase 27** : `_verticale_present` accepte les radicaux communs ≥ 4 lettres.
  - **Phase 28** : `_CONCEPTS_METIER` remplace les patterns génériques dans `extract_and_lock_numeric_facts` (fin des clefs `taux_de_remplissage_volontairement_conservateurs`).
  - **Phase 29** : consigne « fourchettes » adaptée par livrable (BP/EC/STR stricts, EM sourcée avec médiane annoncée). Registres méthodologiques ajoutés au prompt EM d'après WAOME.

## Règles de tenue du journal

- On ajoute une ligne au tableau **à chaque génération réelle**, immédiatement après le rapport gate.
- Le verdict `keep` n'est posé qu'après **validation d'Évangéline** sur le vrai document livré (règle 7 : le vert des tests ne prouve rien).
- Un défaut nommé par la cliente ou par le gate qui n'est pas encore corrigé s'enregistre en `blocked` ; l'entrée est réouverte au run suivant pour valider `keep`.
- Le commentaire est **factuel** : ce qui a été mesuré, quelle classe de défaut a été touchée, quel commit de code a été fait en réponse.

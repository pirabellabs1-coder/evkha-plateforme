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
| 2026-07-20 | `49953f14` | `a73669b` | EM | 2,03 | 28,8 | 71 → 62 après fix judge-alignment (92676e0) | en attente | **blocked** | WAOME EM v1 — 23 chapitres, 43 730 mots. Le modèle applique bien le format WAOME (fourchettes sourcées + médiane annoncée). Reste 59 micro-fourchettes sans médiane à corriger côté prompt, et 2 vraies divergences chiffrées (marge_brute, résultat_net an3). |
| 2026-08-02 | `c40e6afa` | `2880b2b` | EM | 0,06 | 0,03 | — | non atteint | **discard** | Vente de voitures d'occasion à Paris. MORTE au chapitre 1 : « volume : 2948 signes contre 2457 au modèle, 20 % au-dessus de la tolérance de 15 % ». Le chapitre 0 est passé « non contrôlé » comme prévu. Cause : `derniere_tentative` était déduit de `chapter.retry_count`, compteur que SEULE la tâche Celery par chapitre incrémente — or la production emprunte le runner synchrone, qui appelle `produire_chapitre` une fois et propage. L'étage « accepter puis consigner » n'était donc jamais atteint et tout écart de forme était fatal au premier essai. La doublure produisait des chapitres conformes : la branche de refus n'avait jamais tourné (règles 7 et 9). Correctif : l'appelant DÉCLARE s'il réessaiera. |

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

### 2026-07-20 WAOME EM v1 — `49953f14`

- **68 fourchettes** signalées au gate — mesuré. **Toutes** sont conformes au standard WAOME (« estimé entre X et Y, médiane retenue Z »). Cas d'école de judge-misalignment : le prompt a été adapté à la règle EM (phase 29), le check gate est resté strict. Résultat : le loop tourne mais compte du bruit.
- **Correction immédiate — phase 30** : `detecter_fourchettes` reçoit le type de livrable. Pour EM, une fourchette suivie dans les 120 caractères d'une mention « médiane retenue X » est acceptée. Effet mesuré sur le même doc : 68 → 59 fourchettes signalées (les 9 sourcées + médiane annoncée disparaissent).
- **59 fourchettes restantes** = signal prompt à renforcer : le modèle annonce la médiane pour les macros (mondial, européen, national) mais pas pour toutes les micro-fourchettes qu'il produit dans les chapitres 3+. Correctif prompt à faire avant re-génération.
- **2 vraies divergences chiffrées** :
  - `marge_brute 110 kEUR (ch. 14) vs 10 000 EUR (ch. 21)` — vraie incohérence.
  - `resultat_net an3 : 95k / 270k / 35k` — trois valeurs dans le seul ch. 21.
- **Leçon transverse (méthode Bles Software)** : chaque nouvelle règle prompt DOIT être aussitôt reflétée dans le check gate correspondant. Sinon le judge n'est plus aligné et le loop devient décoratif.

### 2026-07-31 Voitures d'occasion Paris EM — `16a597e6` — **discard**

Première tentative d'appel réel après la pose de la clé. **Aucun document, aucun
coût : 0,0000 €.** L'API a refusé la requête en 0,9 seconde.

- **Refus** : `400 — You have reached your specified API usage limits. You will
  regain access on 2026-08-01 at 00:00 UTC.` Plafond de dépenses configuré sur
  le compte, atteint avant même le socle. Ni la clé, ni le worker, ni le réseau
  n'étaient en cause.
- **Défaut trouvé, et c'est la vraie leçon** : la tâche Celery a levé, mais
  **le job est resté affiché `running` pendant quatorze minutes**. Le gardien
  `reset_stuck_generation_jobs` ne l'aurait requalifié qu'au bout de deux
  heures — délai juste pour un worker mort, absurde pour un crash instantané.
  Un client aurait lu « en cours » sur une génération morte (règle 1).
- **Erreur de diagnostic à noter** : j'ai déduit d'un coût à zéro que l'appel
  n'était jamais revenu, et cherché une panne réseau. Un appel *refusé* ne
  coûte rien non plus. La réponse était dans les journaux du worker depuis le
  début — les lire avant d'émettre une hypothèse aurait fait gagner un quart
  d'heure.
- **Correctif — `generation/echecs.py`** : filet à la frontière de la tâche.
  Toute exception traversant le pipeline requalifie le job en `failed`, ouvre
  un incident HIGH, et écrit un motif *actionnable* (« relever le plafond dans
  Settings → Limits ») en conservant le message d'origine. Vise la classe, pas
  l'erreur de plafond (règle 4). Contre-épreuve jouée : sur le code d'avant, le
  test échoue sur `assert job.status == FAILED — 'running'`.
- **Mesure préalable, à confirmer sur un vrai run** : ~55 000 jetons d'entrée
  pour 21 chapitres, soit environ 1,50 € par étude — et non 4,60 €, qui est le
  plafond de sécurité, pas le prix. Deux gains identifiés et non encore
  appliqués : le socle est réinjecté en clair dans chacun des 21 prompts alors
  que le bloc mis en cache ne fait que 202 jetons — sous le minimum de 1 024,
  donc **le cache ne s'active jamais** (−40 % à récupérer) ; et la génération
  étant asynchrone, l'API Batch vaudrait −50 %.

## Règles de tenue du journal

- On ajoute une ligne au tableau **à chaque génération réelle**, immédiatement après le rapport gate.
- Le verdict `keep` n'est posé qu'après **validation d'Évangéline** sur le vrai document livré (règle 7 : le vert des tests ne prouve rien).
- Un défaut nommé par la cliente ou par le gate qui n'est pas encore corrigé s'enregistre en `blocked` ; l'entrée est réouverte au run suivant pour valider `keep`.
- Le commentaire est **factuel** : ce qui a été mesuré, quelle classe de défaut a été touchée, quel commit de code a été fait en réponse.

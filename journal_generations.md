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
| 2026-08-02 | `8437c9ad` | `9f1ab71` | EM | 0,28 | 0,14 | — | non atteint | **discard** | Même sujet, après le correctif de conformité. Celui-ci TIENT : ch2 « écarts acceptés » sur un volume à +146 %, ch3 à +28 %, ch4 sur la séquence des blocs — quatre chapitres écrits là où le run précédent mourait au premier. Morte au chapitre 5 sur une AUTRE couche, la validation du contrat : « Le résumé fait 254 mots ; attendu entre 150 et 250 ». Quatre mots. Le motif dit lui-même à quoi sert la borne — être relu sans saturer le contexte — donc raccourcir l'atteint et refuser la détruit. Correctif : réparer avant de juger ; un résumé trop COURT reste un motif, rien ne peut l'inventer. |
| 2026-08-02 | `acff2d6c` | `ddabcb2` | EM | 1,21 | 0,61 | — | non atteint | **discard** | Même sujet. Les deux correctifs précédents TIENNENT : 19 chapitres écrits d'affilée, sans un blocage de conformité. Morte au chapitre 20 sur « blocs : Field required ; resume : Field required » — une réponse de modèle incomplète, soit l'aléa transitoire par excellence. DIAGNOSTIC RÉEL, après trois runs : le runner de production appelait `produire_chapitre` UNE fois et laissait remonter. La boucle de reprise existait pourtant, complète, dans la tâche Celery par chapitre — et n'était appelée par rien (règle 8, le défaut de Gamma à l'identique). J'avais corrigé les runs 1 et 2 en rendant deux règles tolérantes : c'était traiter deux instances d'un défaut dont la classe est l'absence de reprise (règle 4). |
| 2026-08-02 | `31b3bb75` | `854e0ec` | EM | 0,08 | 0,04 | — | non atteint | **discard** | La REPRISE FONCTIONNE, et elle a paye des le premier run : ch1 a echoue une fois puis reussi a la seconde tentative. Le ch2, lui, a echoue TROIS fois sur le meme motif — donc deterministe, pas un alea : « le graphique utilise `marche_continental_taille`, absent de `donnees_utilisees` ». Les deux champs sont remplis par le MEME modele sur le MEME chapitre : leur desaccord dit que la declaration est incomplete, pas qu'un chiffre est invente. On la complete, et c'est le SOCLE qui tranche — le controle qui compare a quelque chose (regle 9). Un graphique qui inventerait une donnee reste refuse, verifie par un test dedie. |

| 2026-08-05 | `07745d4a` | `4415784` | EM | 0,01 | 1,0 | — | non atteint | **discard** | Joalie, premier lancement depuis l'espace client déployé. Morte au CHECK INITIAL, avant le chapitre 1. Le relecteur réclamait six éléments dans la fiche projet, dont **la devise, le lecteur final et une section signalant les points non spécifiés** — trois choses que le prompt de la fiche n'a jamais demandées (dix rubriques prescrites, aucune ne les porte). Judge-misalignment, exactement comme le 20/07. Aggravant : le code stoppait l'étude **sans tenter la moindre correction**, au motif que « c'est le brief du client qui est en cause », et invitait l'admin à corriger le brief — ce qu'aucune correction du brief n'aurait réparé. Gate en impasse (règle 1). Deux correctifs : la fiche gagne les rubriques manquantes, et le CHECK INITIAL régénère la fiche une fois avec la note avant de bloquer (règle 4 : la reprise, déjà rendue aux chapitres le 02/08, manquait encore à la fiche). |

| 2026-08-05 | `6557b06b` | `2130519` | EM | 0,41 | 6,3 | — | non atteint | **discard** | Joalie, relance après le correctif du CHECK INITIAL. **La fiche passe** — le gate amont ne tue plus l'étude, et trois chapitres sont écrits. Morte au chapitre 1 sur un désaccord de SCHÉMA : `blocs.3.graphique.graphique : Field required` + quatre `Extra inputs are not permitted`. Le modèle écrivait le graphique **à plat** (`{type: "graphique", type_graphique: …, titre: …}`) au lieu de l'imbriquer. Trois fois le même motif sur deux chapitres : déterministe. Cause nommable : `BlocGraphique.type` vaut « graphique » (nature du bloc) et `Graphique.type` vaut « courbes » (nature du visuel) — **le même mot pour deux sens, emboîtés**, plus une clé d'enveloppe qui répète encore le discriminant. Le modèle a résolu la collision de la seule façon possible. Deux correctifs : le contrat nomme désormais le champ intérieur `type_graphique` (alias, `populate_by_name` garde les payloads en base lisibles), et la forme aplatie est acceptée sur les **trois** blocs à enveloppe — pas sur le seul qui a échoué (règle 4). |

| 2026-08-05 | `4c8cfa53` | `d657500` | EM | 0,43 | 8,5 | — | non atteint | **discard** | Joalie, relance après le correctif de schéma. **Il tient** : les chapitres 1, 2 et 3 passent, là où le run précédent mourait au chapitre 1. Morte à la **RÉPARATION** du chapitre 3, demandée par le CHECK du bloc B : « volume : 966 signes contre 792 au modèle, 22 % au-dessus de la tolérance de 15 % », `essais=1`. Une seule tentative. La boucle de reprise ajoutée le 02/08 vivait dans `generation.runner` et ne servait qu'à la PREMIÈRE écriture ; la réparation appelait `produire_chapitre` une fois, sans déclarer de dernière tentative — donc l'arbitrage de conformité, qui n'accepte un écart de forme que sur la dernière, n'était jamais atteint. Même défaut que le run `c40e6afa`, sur l'autre chemin : instance corrigée, pas la classe (règle 4). Second défaut, indépendant : l'exception de la réparation tuait l'étude alors que le module annonce « incident MEDIUM non bloquant, le contenu reste livré ». Le chapitre 3 avait pourtant une version acceptée. |

| 2026-08-05 | `90cbb3d9` | `7c750da` | EM | 3,32 | 55 | 23 | non atteint | **blocked** | Joalie. **PREMIÈRE ÉTUDE COMPLÈTE : 23/23 chapitres, et un document.** Les trois correctifs du jour sont visibles à l'œuvre : le CHECK INITIAL fait corriger la fiche puis l'accepte (`1→0→1` à 120 s), et sept réparations inter-blocs aboutissent (`n→n-1→n`) là où la précédente mourait sur la première. Quatre chapitres passent en « écarts acceptés » (volume à +38 % et +41 %) — l'étage « accepter puis consigner » fonctionne. Livraison **bloquée par le gate** (23 motifs), donc aucun envoi : 7 `chapitre_avorte`, 6 `check_bloc_non_resolu`, 6 `troncature`, 4 `troncature_rendu`. Mesuré sur le `.docx` livré contre `joalie_2026.docx` : 113 tableaux contre 114, **0 tableau vide** (le modèle en a 1), 63,1 % de mots en tableaux contre 58,2 %, 15 150 mots contre 11 580, polices identiques, aucun marqueur technique. Deux écarts de rendu majeurs : **2 graphiques contre 10** (et les deux montrent la MÊME donnée, en barres verticales puis horizontales, sans titre et avec des étiquettes illisibles), et **0 style de titre** contre 83 au modèle — le document n'a aucune hiérarchie navigable. |

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

### 2026-08-05 Joalie EM — `07745d4a` — **discard**

- **Le brief est parti avec les accents corrompus.** Erreur d'outillage, pas de
  plateforme : PowerShell 5.1 relit un `.ps1` en page de code ANSI, donc
  « joaillerie de créateurs » écrit en UTF-8 dans le script devient
  « joaillerie de crÃ©ateurs » à l'exécution — puis part tel quel dans l'appel.
  Détecté après le lancement, avant que l'étude n'écrive un chapitre de fond.
  **Tout script de lancement doit être ASCII strict**, ou lire son brief depuis
  un `.json` avec un décodage UTF-8 explicite.
- **La mort au CHECK INITIAL n'est pas due à cette corruption** : les trois
  éléments réclamés (devise, lecteur final, points non spécifiés) manquaient au
  prompt, pas au brief. Une relance à accents corrects serait morte au même
  endroit.
- **Répétitions à blanc, gratuites, faites le même jour** — elles ont trouvé ce
  qu'aucun test unitaire n'avait vu :
  - `EVKHA_SOCLE_ENABLED` vaut `false` en local et `true` en production. Une
    répétition qui ne le pose pas observe **un autre logiciel** que celui qui
    tourne chez le client.
  - **Le business plan et la stratégie ne produisaient AUCUN document.** 21 et
    22 chapitres écrits, puis `LivrableIncompletError` : le drapeau global
    `EVKHA_LIVRABLE_WORD=true` envoie les quatre livrables vers une chaîne qui
    exige un socle, que seuls l'EM et l'EC produisent. L'échec était silencieux
    (`except Exception` dans la tâche). Correctif : la chaîne se choisit sur ce
    que le dossier CONTIENT, et le repli se journalise.

## Règles de tenue du journal

- On ajoute une ligne au tableau **à chaque génération réelle**, immédiatement après le rapport gate.
- Le verdict `keep` n'est posé qu'après **validation d'Évangéline** sur le vrai document livré (règle 7 : le vert des tests ne prouve rien).
- Un défaut nommé par la cliente ou par le gate qui n'est pas encore corrigé s'enregistre en `blocked` ; l'entrée est réouverte au run suivant pour valider `keep`.
- Le commentaire est **factuel** : ce qui a été mesuré, quelle classe de défaut a été touchée, quel commit de code a été fait en réponse.

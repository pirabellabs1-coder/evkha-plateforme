# Chantier de fiabilisation — septembre 2026

Demande du client, 13/09/2026 : trois jours d'affilée au moins pour mettre le
système « 100/100 », surtout les prompts et les chiffres. **Aucune génération
réelle n'est autorisée** : chaque correctif se mesure sur le corpus des dossiers
déjà écrits, re-rendus à zéro centime, et sur la doublure.

## Méthode

1. Mesurer le corpus : `GET /api/dashboard/jobs/<id>/mesure/` sur chaque dossier
   terminé (figures, sources, chiffres hors socle, et depuis `dfd90b8` chaque
   anomalie du fichier Word et chaque échec du gate, avec total et exemples).
2. Classer les défauts par fréquence et par gravité, livrable par livrable.
3. Trier les vrais motifs des faux, en retrouvant l'extrait dans le document
   (règle 2). Un contrôle qui accuse à tort est un défaut : le contrôleur final
   réécrit — et fait payer — les chapitres qu'il désigne.
4. Corriger par CLASSE, puis re-mesurer le corpus et comparer.

Limite à dire : un correctif de PROMPT ne se prouve pas sans génération. Il se
vérifie par la doublure et par des tests de classe sur ce qui part au modèle ;
sa preuve sur un vrai document viendra au prochain dossier client.

## Mesure de référence — 13/09/2026, 37 dossiers, code `dfd90b8`

| Classe | BP (7) | EC (11) | STR (12) | EM (7) |
|---|---|---|---|---|
| `chiffres_hors_socle` (fichier Word) | 393 | 409 | 38 | 43 |
| `visuels` (figures abandonnées) | 84 | 56 | 203 | 42 |
| figures dessinées / demandées | 222/270 | 146/181 | 172/360 | 107/134 |
| `densite` | — | 3 | 44 | — |
| `valeur_nulle` | 13 | 5 | 10 | — |
| gate `coherence_chiffree` | 32 | — | — | — |
| gate `check_bloc_non_resolu` | 1 | 1 | — | 88 |
| gate `strategy_…_decision_absente` | — | — | 40 (12/12) | — |
| gate `fourchette_interdite` | 6 | 1 | 5 | — |
| gate `agregat_faux` | — | 9 | — | — |
| gate `brief_non_lu` | — | 1 | 10 | — |
| sources extérieures sans adresse | 15/56 | 54/155 | 22/51 | 21/21 |

## Audit prompts ↔ contrôles — 14/09/2026

Contradictions PROUVÉES par lecture du code (et pour la plupart par exécution
des contrôles sur des phrases). Statut : ✅ corrigé, 🔧 en cours, ⏳ à faire.

| Id | Constat | Livrables | Statut |
|---|---|---|---|
| A1 | EC : fourchette de CA/parts OBLIGATOIRE dans le prompt (`prompts.py` `exception_ca_estime`, EC ch 06), `fourchette_interdite` strict hors EM | EC | ✅ plage admise en EC seulement suivie de sa valeur retenue (cahier des charges ET cliente) ; gate, prompt, CLAUDE.md alignés |
| A2 | Plages produites par les consignes : `_SYSTEME` « entre X et Y », libellé du socle, « 14-16 % → 15 % retenu », `DECISIONS_STRATEGIE` « fourchette ou prix cible », STR ch 17 seuils | BP EC STR | ✅ consignes réécrites sans montrer de plage ; test de classe avec le détecteur du gate sur tout ce qui part au modèle |
| A3 | Détecteur de fourchettes : « de 60 à 65 € » non vu (« à » accentué) ; « An 1 — 120 000 € », « Scénario 2 - 40 % » accusés à tort ; EM jamais contrôlé | tous | ✅ « à » accentué ; « An 1 — », « Scénario 2 - », trajectoires datées (« 120 000 € en 2026 à 180 000 € en 2027 ») écartés ; les vraies plages de prix derrière une étiquette (« l'offre 60 à 65 € ») restent vues — la 1re version les cachait (relecture). EC : valeur retenue dans la MÊME phrase ou trois colonnes de tableau ; croissance/TCAC toujours unique. Consigne de réécriture alignée (elle montrait « X à Y, médiane retenue Z », forme refusée). EM : bornes gardées dans le libellé du socle |
| A4 | `calcul_faux` : « 250 abonnés à 19 € par mois, soit 57 000 € par an » déclaré faux (×12 sur le seul nombre qui précède « par mois ») — la forme que PRIX règles 5-6 demande | BP EC STR | ✅ prix × effectif × période reconnu comme calcul juste ; test sur la forme exacte de PRIX règles 5-6 |
| A5 | `chiffres_hors_socle` punit les calculs que les prompts exigent de montrer ; dérivations coupées à 80 valeurs dont les doublons | tous | ✅ calcul posé, chiffre sourcé, estimation déclarée (hors taille de marché) reconnus ; doublons retirés avant la coupe, brief en tête ; ne fait plus RÉÉCRIRE (trop peu précis). Relecture : une base inventée ne justifie plus le montant qu'on en tire, « estimé à » ne couvre plus une taille de marché, « selon le canal » n'est plus une source, années et petits nombres ne fabriquent plus de calcul. Corpus : 883 → 756 après la 1re étape |
| A6 | Seuil de rentabilité au mois ET à l'année (PRIX règle 6) → `coherence_chiffree` « 16 250 € au ch. 14 ; 195 000 € au ch. 16 » | BP | ⏳ |
| A7 | BP : dirigeant non rémunéré (validé par BP ch 18, « 0 € » interdit) → `remuneration_dirigeant` exige un montant | BP | ⏳ |
| A8 | « Aucun chiffre hors socle » ×135 dans le plan EM, « SOCLE VERROUILLE » dans six prompts EM, « identifiants du socle » dans la règle des figures | EM (BP STR) | ✅ + test de classe sur tout ce qui part au modèle |
| A9 | EC ch 07 demande `barres_verticales`, type inexistant → chapitre refusé par le contrat | EC | ✅ + test : chaque type nommé dans un prompt existe |
| A10 | Chiffre clé sans source (« laisse le champ vide ») rendu sans point final → `sentence_cut` bloquant | EM | ⏳ |
| A11 | Sources : ratio d'URL exigé alors que les prompts disent « URL si disponible, n'invente aucune URL » ; exemption client jugée ligne par ligne | BP EC STR | ⏳ |
| A12 | Tableau de sources reconnu seulement par un en-tête exact « Source(s) »/« Référence(s) » ; « Organisme \| Publication \| Lien » → « vide » | tous | ⏳ |
| A13 | Même source écrite deux fois (« (Eurostat, 2024) » / « (Eurostat 2024) ») → `sources_divergentes` bloquant, sans chapitre routable | tous | ⏳ |
| A14 | STR : structure « à retenir / lecture stratégique » exigée aussi des chapitres Sources, Annexe, fiche projet | STR | ⏳ |
| A15 | STR : décision exigée sous « offre phare / locomotive / à pousser », jamais demandée par le prompt ch 08 ; horizons 30-60-90 j contre 0-3 mois / 3-12 mois / 1-3 ans au ch 17 | STR | ✅ horizons du ch 17 alignés (30/60/90 jours, 6 et 12 mois) ; chaque chapitre porteur reçoit ses décisions sous l'intitulé que le contrôle reconnaît (voir A19) |
| A16 | EC : décompte des concurrents dépendant de la forme (encadré coupé à six lignes, puces de forces/faiblesses) | EC | ⏳ |
| A17 | STR : « paragraphes développés » dans tous les prompts contre le plafond de densité (médiane 25 mots) | STR | ⏳ |
| A18 | « un segment » + encadré de 3 puces → `desaccord_numerique` (7 dossiers : « un axe », « une phase », « deux phases » + puce d'une autre liste) | BP EC STR | ✅ un article n'annonce pas de compte ; l'annonce se ferme sur « : » ; seule la liste contiguë, au premier niveau, est comptée |
| A19 | STR `decision_absente` 12/12 : le contrôle attendait une locution collée (« canaux à éviter ») ; les documents décident par un verbe (« Nous excluons Facebook Ads… », « deux publications par semaine ») ; les prompts des chapitres porteurs ne demandaient pas ces décisions, le ch 13 disait « la fréquence se déduit du tableau ». Le contrôleur réécrivait (payait) les ch 8, 10, 13 sans fermer les motifs | STR | ✅ formes verbales de décision reconnues (contre-épreuves : négation, « Reportez-vous », cadence de prospection) ; tableau « Décisions retenues » injecté au chapitre porteur depuis la même déclaration. Word des 8 stratégies lisibles : 23 → 5 motifs, les 5 restants vrais |
| A20 | BP `coherence_chiffree` « apport » (3 dossiers, 10 motifs) : réponse LIBRE du client (charges, rémunération, enveloppe, « 1600e investis ») ; tous ses montants pris pour l'apport, motif « le brief client dit » + paragraphe entier ; et faux négatif inverse (un apport de 8 000 € accepté parce que l'enveloppe valait 8 000 €) | BP | ✅ seules les phrases qui parlent du fait font référence ; sans elles, un montant écrit par le client est conforme, sinon `reference_client_illisible` une fois, sans réécriture payée |
| A21 | `demande_contredite` (7 dossiers) accuse sur « reprend, statut, suivant, traitée » : mots de la ligne de statut, pas un sujet ; le motif ne citait pas la ligne, introuvable par la lectrice | tous | 🔧 la ligne accusée est citée dans le motif ; correctif de classe après re-mesure (les Word de ces dossiers ont expiré) |
| A22 | `chapitre_desaccentue` (5 dossiers) : les PROMPTS eux-mêmes écrivaient sans accents — 1 067 mots désaccentués dans 76 fichiers, mesurés avec le détecteur du gate ; le modèle reprend la forme montrée | tous | ✅ fichiers `.md` : ~2 170 accents rétablis (mot remplacé seulement s'il n'a qu'une forme accentuée, même terminaison, hors homographes ; impératifs ambigus seulement en tête de consigne) ; test de classe avec le détecteur du gate. ✅ constantes Python envoyées à chaque chapitre (règles des prix — 36 mots —, de fond, des figures, consignes EC/STR, critères de tri EC) : même traitement, jugées avec les prompts comme un seul document ; la doublure reconnaît les consignes sans tenir compte des accents |
| A23 | `troncature_rendu` (6 dossiers) : notre rendu écrit la source en italique sous chaque tableau ; un chapitre fermé sur un tableau finissait sur « *données du projet* » → « perte probable de contenu » | tous | ✅ ligne en italique qui suit une ligne de tableau = légende ; la prose en italique reste jugée |
| A24 | Faits CLIENT tronqués à 500 signes : la réponse « apport » perdait sa dernière phrase (« 1600e ont déjà été investis »), le gate jugeait sur une référence amputée | BP | ✅ `CoherenceFact.value` en texte (migration 0017) |
| A25 | EC `agregat_faux` (4 dossiers) : « 15 % et le cumul des cinq premiers acteurs » confronté à une colonne de ONZE parts ; « le reste des 60 acteurs » à celle des 11 ; colonne nulle comparée | EC | ✅ une phrase qui compte ses acteurs ne se confronte qu'à une colonne de ce nombre de lignes ; colonne à somme nulle ignorée ; le cas de la cliente (« onze concurrents », 11 parts, 2,7 % contre 0,479 %) reste signalé |

Suspicions et incohérences internes aux prompts (non encore prouvées ou sans
contrôle qui les attrape) : catalogue de figures sans matrice ni chronologie
alors que des prompts les demandent ; « non communiqué » imposé en EC, interdit
par COHERENCE ; marque « EVKHA » dans trois prompts ; notation `MEUR` ;
« points à confirmer par un professionnel » contre `_SYSTEME` ; URL de pages
d'accueil fournies en EM ch 21 ; le prévisionnel du BP (ch 16) et EC ch 03
reçoivent « Ne pas utiliser ce prompt directement » comme seule instruction.

## Relecture indépendante du 14/09/2026 (lot décisions, réponse libre, accents)

Une relecture a trouvé un bloquant et sept points importants, tous vérifiés
par une phrase concrète. Corrigés avant tout commit :

- **Clé JSON accentuée** : la restauration avait écrit `"activités_cles"` dans
  l'exemple du canvas (BP ch. 9), refusé par le schéma → chapitre repayé.
  Revenu en arrière ; test : aucun identifiant ni clé JSON accentué.
- **Tableau « Décisions retenues »** : l'étiquette seule fermait le motif, même
  avec « À définir » dans la case, et la consigne disait « écris que tu ne
  tranches pas » contre la règle STR « tu tranches quand même ». La case
  « Ce qui est retenu » juge désormais ; la consigne est alignée.
- **Formes verbales** : « Nous n'excluons aucun canal », « Aucun réseau n'est
  encore exclu », « les concurrents publient une vidéo par semaine »
  passaient. Locution et forme verbale sont séparées ; la forme verbale doit
  décider (ni négation près du verbe, ni tiers dans la phrase), et les
  plateformes nommées (Facebook, Instagram…) sont des canaux. Word réels :
  23 → 7 motifs, les 7 restants vrais.
- **Réponse libre (apport)** : un montant de la réponse n'est plus l'apport
  pour autant (8 000 € d'enveloppe, 1 800 € de rémunération) ; « j'apporte »,
  « économies », « épargne » sont reconnus ; « investis » dans une phrase de
  prêt ne porte plus l'apport.
- **Agrégats** : une ligne « Total » ne compte plus comme une part (elle
  cachait de nouveau le cas de la cliente).
- **Accents** : « est génère », « non références », « a-t-il évolue » corrigés ;
  144 homographes sûrs traités (« liste à puces », « du marché », « 3 à 5 »).
- **Mineurs** : la ligne qui continue une puce ne ferme plus la liste ; une
  légende de tableau contenant `_` reste une légende.

Limite à dire : la migration 0017 ne répare pas les faits déjà tronqués. Un
dossier ancien rejoué garde sa référence amputée ; l'effet ne se verra que sur
un nouveau dossier.

## Mesure après déploiement de `428d3ab` — 14/09/2026, mêmes 37 dossiers

Preuve du déploiement par le comportement (règle du dépôt : un 200 ne prouve rien).

| Contrôle (gate) | Avant | Après |
|---|---|---|
| `desaccord_numerique` | 13 | 0 |
| `troncature_rendu` | 8 | 0 |
| `strategy_…_decision_absente` | 40 | 17 |
| `coherence_chiffree` (BP) | 32 | 20 |
| `agregat_faux` (EC) | 9 | 5 |
| `fourchette_interdite` | 12 | **156** |
| `reference_client_illisible` (BP) | 1 | 4 |

**`fourchette_interdite` 12 → 156**, lu dans les Word : la plupart sont VRAIS.
L'ancien détecteur ne voyait pas « à ». « Interventions de 60 à 75 € de
l'heure » efface les trois prix du brief (60 € à distance, 65 € en atelier,
75 € à domicile), « trois paliers de 12 à 29 € » efface le 19 €. Une classe
était fausse : deux valeurs RELIÉES (« le saut de 19 € à 29 € », « basculé
de 19 à 29 € », « l'écart entre 19 et 29 € »). Correctif : ces formes ne sont
plus des plages ; « une hausse de 3 à 5 % » en reste une. À la source, la
consigne des livrables BP/EC/STR interdit désormais de résumer des prix par
variante en « de X à Y ».

`reference_client_illisible` 1 → 4 : attendu. Les faits de ces anciens
dossiers restent tronqués à 500 signes (la migration ne les répare pas), et
une réponse libre qui ne donne pas l'apport est désormais dite illisible au
lieu d'accuser le document.

Après déploiement de `88fc431` : `fourchette_interdite` BP 67 → 66, STR 65 → 62,
EC 24 inchangé. La classe « valeurs reliées » était petite ; les ~150 motifs
restants sont de vraies plages dans des documents anciens. Leur correctif est
à la source (consigne des prix par variante) et ne se prouvera que sur le
prochain dossier réel.

## Figures des stratégies — 14/09/2026

Mesure : 188 figures perdues sur les 12 stratégies (6 obtenues pour 29
demandées sur `a678b10a`). La mesure dit désormais, par figure perdue, ses
données, leurs unités et la raison de l'échec de la réparation.

Ce n'étaient pas des erreurs de réparation. Le modèle demandait des figures
sur des données qui ne se tracent pas ensemble : 65 entonnoirs sur
[abonnés, chiffre d'affaires visé], 22 frises sans date, 8 radars et 7 jauges
sans grille de notes. Deux contradictions en amont :

1. **Le plancher de 17 figures** (exigence de la cliente, 06/08) face à un
   référentiel STR fermé à 13 données, une par notion : trois ou quatre figures
   justes au plus. → Le référentiel accueille les SÉRIES que le brief liste
   (prix par formule, tarif par prestation, CA par activité, clients par
   segment, charges par poste, CA visé année par année), facultatives,
   déclarées, jamais inventées. Socle Zenitek type : 3 figures → 6, chacune
   dans la forme de ce qu'elle est (trajectoire en barres/courbes, composantes
   d'un total en anneau, prix comparés en barres). Le catalogue ne propose plus
   de parts pour un regroupement sans total (« CA + panier » en camembert).
2. **Le radar obligatoire du chapitre 3 STR** : aucune grille de notation dans
   le socle d'une stratégie, donc jamais dessinable. → Tableau de positionnement
   noté ; test de classe : aucun prompt ne demande radar ou jauges si le socle
   de son livrable n'a pas de grille.

Limite : les socles existants n'ont pas ces séries ; l'effet se verra sur le
prochain dossier de stratégie. Le plancher de 17 reste hors d'atteinte pour un
projet dont le brief ne liste presque aucun chiffre — c'est à dire à la
cliente, pas à contourner.

Mesuré après déploiement de `488c8ee` (catalogue des figures justes que le
socle de chaque dossier permet, contre les figures demandées par le modèle) :

| Livrable | Catalogue par dossier | Demandées (moyenne) |
|---|---|---|
| Stratégie | 2 (0 à 3) | 30 |
| Business plan | 4 à 12 | 39 |
| Étude concurrentielle | 1 à 5 | 17 |
| Étude de marché | 3 à 6 | 19 |

Le catalogue ne compte que les groupes de valeurs scalaires : l'étude de marché
dessine bien plus (séries temporelles, grilles), il la sous-estime. Pour la
stratégie il est juste : deux figures possibles, trente demandées — l'écart
que les séries du brief doivent combler.

## Chiffres hors socle — 14/09/2026, après-midi

La mesure rend désormais chaque motif avec sa phrase (757 au départ de l'étape).
Classes fausses trouvées en les lisant, chacune corrigée, testée, déployée et
re-mesurée :

| Classe | Correctif | Effet mesuré |
|---|---|---|
| Champs STRUCTURÉS du brief jamais lus (`INVESTISSEMENT_TOTAL : 180 000 euros`) | montants à unité et pourcentages de tous les champs | BP 305 → 270, STR 32 → 21 |
| Cellule de tableau jugée seule, sous un en-tête « CA estimé » | la cellule se lit « en-tête : ligne » ; règles de la prose inchangées | EC 382 → 211, BP 270 → 243 |
| Garde « taille de marché » déclenchée par le commentaire d'une autre colonne ; part calculée dans sa ligne (200 000 / 850 M€) ; URL et article de loi comme sources | portée = en-tête + libellé + cellule jugée ; part exigeant un en-tête de part et un rapport exact | EC 211 → 153, BP 243 → 222 |

Bilan sur les mêmes 37 dossiers depuis la mesure de référence du matin :
**756 → 424** (BP 294 → 222, EC 388 → 153, EM 39 → 30, STR 35 → 19).

Restent surtout des vrais motifs : croissances de concurrents sans source
(« +16 % »), fourchettes de CA estimé, prix unitaires sans base (« baguette à
1,09 € »), et des opérandes de calculs posés dont l'origine est plus haut dans
le document.

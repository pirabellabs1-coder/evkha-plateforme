<!--
Prompt du chapitre 2 — Marché national, local et marché accessible
Clé historique : em.02.marche_national_local

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

CHAPITRE 2 — Marché national, local et marche accessible (manuel §6, p. 8).
Objectif : mesurer le terrain réel d'implantation et transformer la vue macro en potentiel accessible. Le pays cible est extrait de BRIEF_CLIENT.PAYS, la zone de BRIEF_CLIENT.ZONE.

Questions auxquelles ce chapitre doit répondre :
- Quelle est la taille du marché dans le pays, la région et la zone d'implantation réelle ?
- La population, le pouvoir d'achat, les usages, les flux et la densité locale créent-ils une demande suffisante ?
- Quelle part du marché total correspond réellement a l'offre, a la cible et a la zone du projet ?
- Quel niveau de marché le projet peut-il raisonnablement atteindre en année 1 puis en année 3 ?
- Quelles hypothèses expliquent le marché total, le marché accessible et le chiffre d'affaires visé, et lesquelles sont les plus sensibles ?

Contenu obligatoire, dans cet ordre :
1. Marche NATIONAL : taille et dynamique (valeur, volume, TCAC national), acteurs structurants sans benchmark concurrentiel detaille, maturité et structure (concentration, distribution), specificites nationales utiles (réglementation, habitudes de consommation), projection nationale lorsque défendable.
2. Marche LOCAL sur la zone cible : démographie, revenus, emploi, flux, usages, densité et demande ; projection locale lorsque défendable, avec estimation argumentee si les données directes manquent.
3. Marche ACCESSIBLE : le marché total, estimé du haut vers le bas ; le marché accessible, filtré par zone, cible et offre ; le chiffre d'affaires visé, calculé à partir de l'activité réelle du projet, année 1 ET année 3.
Ne répète pas les chiffres mondiaux et continentaux du {{ renvoi_marche_mondial_europeen }} : tu les reprends comme point de départ, tu ne les re-estimes pas.

DISTINCTION CRITIQUE mondial / continental (erreur fatale de cohérence) :
Le bloc DONNÉES DE RÉFÉRENCE contient DEUX valeurs séparées et différentes :
  - `marche_mondial_taille` = taille totale du marché mondial (toutes géographies, toutes technologies pertinentes au projet)
  - `marche_continental_taille` = part de ce marché a l'échelle du continent pertinent (ex. Europe IA strict pour un projet français)
Ces deux valeurs sont différentes. Si tu ouvres ce chapitre en rappelant la taille du marché mondial établie au {{ renvoi_marche_mondial_europeen }}, cette taille doit être EXACTEMENT `marche_mondial_taille`, jamais `marche_continental_taille`. Confondre les deux dans la phrase d'ouverture propage l'erreur dans tous les chapitres suivants qui s'appuient sur ce chapitre comme référence.

RÈGLES DE CALCUL DU marché ACCESSIBLE (non negociables) :
- Écris le calcul, pas seulement le résultat. Chaque étape nomme ses variables et leur valeur : population de la zone, taux de pénétration retenu, panier ou ticket moyen, fréquence annuelle, part de capture visee. Un lecteur doit pouvoir refaire le calcul et retrouver ton chiffre.
- Un seul marché total, un seul marché accessible, un seul chiffre d'affaires visé par année. Si tu donnes une fourchette, elle sert partout ensuite a l'identique.
- L'ordre marché total > marché accessible > chiffre d'affaires visé doit être vrai en euros comparés. Vérifie-le avant d'écrire : convertis tout dans la même unité.
- Le chiffre d'affaires visé en année 1 dépasse rarement quelques pour cent du marché accessible. Si ton calcul donne davantage, c'est que le marché accessible est sous-estimé ou que le chiffre d'affaires visé est irréaliste : refais le calcul. Ne justifie JAMAIS une part élevée par un argument rédactionnel.
- Ces trois valeurs sont réutilisées telles quelles au {{ renvoi_rentabilite_viabilite }} et au {{ renvoi_graphiques_tableaux }} (manuel p. 6). Elles doivent être justes ici, elles ne seront plus recalculées.
- Quand un outil d'exécution de code est a ta disposition, pose ces calculs dedans au lieu de les faire de tête : l'ordre des trois niveaux de marché, les conversions d'unités et la montée en charge mensuelle sont des enchainements ou une erreur d'arrondi se propage jusqu'au {{ renvoi_rentabilite_viabilite }} et au {{ renvoi_graphiques_tableaux }}.
- Le livrable montre le calcul en langage MÉTIER : variables, valeurs, formule, hypothèses et sources, comme l'exige la colonne « Formule et sources » du manuel p. 6. Il ne montre RIEN de la technique : ni code, ni sortie de console, ni mention d'un script, d'un outil, d'un calcul « vérifié » ou d'une procédure. Tu écris pour un porteur de projet et son banquier, pas un journal de travail.

[EXEMPLE DE NIVEAU — chiffre d'affaires visé posé variable par variable]
Extrait d'une étude EVKHA notee 8/10, secteur ÉTRANGER au tien (plateforme juridique, France) : ne reprends ni ses chiffres, ni son secteur, ni ses variables. Reprends sa MÉCANIQUE.
« Le modèle distingue sept variables. Le nombre d'avocats actifs correspond a la part des avocats inscrits qui utilisent effectivement la plateforme, et non au nombre brut d'inscriptions mis en avant dans les objectifs du porteur de projet. Le nombre de consultations réservées par mois et par avocat actif mesure l'intensité d'usage une fois l'avocat engage. [...] Le taux d'annulation ou de report retire du calcul les rendez-vous reserves mais non honores. [...] Le revenu mensuel moyen par avocat actif résulte du calcul : (consultations x (1 - taux d'annulation) x frais de service net) + (part abonnee x abonnement). »
MÉCANIQUE A IMITER, point par point :
1. ANNONCE le nombre de variables de ton modèle avant de les derouler.
2. DÉFINIS chaque variable en une phrase, en la distinguant de la donnée voisine avec laquelle on la confondrait (ici : avocats ACTIFS et non avocats INSCRITS — l'écart entre les deux est la variable la plus determinante du modèle).
3. POSE la formule en clair, avec le signe des opérations, pour que le porteur de projet puisse la refaire avec ses propres hypothèses.
4. DEDUIS les pertes réelles (annulations, défauts de paiement, commissions du prestataire) au lieu de raisonner sur un brut théorique.
5. APPLIQUE une montée en charge progressive, pas un effectif constant sur l'année : les clients arrivent au fil des mois.
6. DÉSIGNE la variable la plus sensible du modèle et dis en une phrase ce qui change si elle bouge.
Un chiffre d'affaires visé qui ne montre pas ses variables est un chiffre que personne ne peut discuter, donc un chiffre que le porteur de projet ne defendra pas devant son banquier.

LES TROIS NIVEAUX DE MARCHÉ, EN MOTS SIMPLES. Le cahier des charges impose TAM, SAM et SOM dans ce chapitre, avec une explication pour un porteur de projet novice. Présente-les UNE fois, chacun avec son nom simple, puis n'emploie plus que les noms simples, ici comme dans le reste de l'étude :
- le TAM, « le marché total » : tout ce qui se vend dans cette famille de produits ou de services ;
- le SAM, « le marché accessible » : la part qui correspond à l'offre, à la cible et à la zone du projet ;
- le SOM, « le chiffre d'affaires visé » : ce qu'une entreprise comme celle-ci peut réellement réaliser en année 1 puis en année 3.

DU MARCHÉ ACCESSIBLE AU CHIFFRE D'AFFAIRES VISÉ — paragraphe obligatoire (c'est ce que le CHECK 1 vérifie en priorité) :
Immédiatement après avoir annoncé le chiffre d'affaires visé en année 1, ouvre une sous-section intitulée « Du marché accessible à votre chiffre d'affaires » (un sous-titre, jamais des astérisques ni du gras dans le texte), qui contient, en phrases simples :
1. Le raisonnement : chiffre d'affaires visé = marché accessible × part de ce marché que le projet peut prendre.
2. Les valeurs : année 1 = [marché accessible en euros] × [part en %] = [chiffre d'affaires en euros].
3. Pourquoi cette part est réaliste, en une phrase concrète (le temps disponible, le nombre de clients qu'une personne peut servir…).
4. Le même raisonnement pour l'année 3.
5. La vérification, sur une seule ligne et en euros : marché total > marché accessible > chiffre d'affaires de l'année 3 > chiffre d'affaires de l'année 1.
Ce paragraphe est non négociable : sans lui, le chapitre est rejeté à la relecture des fondations du marché.

Visuel utile (manuel) : graphique national/local + schéma des trois niveaux de marché. En fin de chapitre, demande UN graphique en barres montrant la répartition ou la dynamique du marché local, en citant des identifiants des données de référence de même nature.
Remplace Segment A/B/C et XX par les vraies données établies dans l'analyse.

Lecture stratégique attendue : Dire si la zone est pertinente, quelle part du marché est réellement accessible et quelles hypothèses doivent être testées en priorité.

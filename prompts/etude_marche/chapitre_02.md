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

CHAPITRE 2 — Marche national, local et marche accessible (manuel §6, p. 8).
Objectif : mesurer le terrain reel d'implantation et transformer la vue macro en potentiel accessible. Le pays cible est extrait de BRIEF_CLIENT.PAYS, la zone de BRIEF_CLIENT.ZONE.

Questions auxquelles ce chapitre doit repondre :
- Quelle est la taille du marche dans le pays, la region et la zone d'implantation reelle ?
- La population, le pouvoir d'achat, les usages, les flux et la densite locale creent-ils une demande suffisante ?
- Quelle part du marche total correspond reellement a l'offre, a la cible et a la zone du projet ?
- Quel niveau de marche le projet peut-il raisonnablement atteindre en annee 1 puis en annee 3 ?
- Quelles hypotheses expliquent le TAM, le SAM et le SOM, et lesquelles sont les plus sensibles ?

Contenu obligatoire, dans cet ordre :
1. Marche NATIONAL : taille et dynamique (valeur, volume, TCAC national), acteurs structurants sans benchmark concurrentiel detaille, maturite et structure (concentration, distribution), specificites nationales utiles (reglementation, habitudes de consommation), projection nationale lorsque defendable.
2. Marche LOCAL sur la zone cible : demographie, revenus, emploi, flux, usages, densite et demande ; projection locale lorsque defendable, avec estimation argumentee si les donnees directes manquent.
3. Marche ACCESSIBLE : TAM top-down, SAM filtre par zone/cible/offre, SOM bottom-up annee 1 ET annee 3.
Ne repete pas les chiffres mondiaux et continentaux du chapitre 1 : tu les reprends comme point de depart, tu ne les re-estimes pas.

DISTINCTION CRITIQUE mondial / continental (erreur fatale de coherence) :
Le bloc SOCLE VERROUILLE contient DEUX valeurs separees et differentes :
  - `marche_mondial_taille` = taille totale du marche mondial (toutes geographies, toutes technologies pertinentes au projet)
  - `marche_continental_taille` = part de ce marche a l'echelle du continent pertinent (ex. Europe IA strict pour un projet francais)
Ces deux valeurs sont differentes. Si tu ouvres ce chapitre avec une phrase du type 'Le chapitre 1 a etabli que le marche mondial represente X', X doit etre EXACTEMENT `marche_mondial_taille`, jamais `marche_continental_taille`. Confondre les deux dans la phrase d'ouverture propage l'erreur dans tous les chapitres suivants qui s'appuient sur ce chapitre comme reference.

REGLES DE CALCUL DU MARCHE ACCESSIBLE (non negociables) :
- Ecris le calcul, pas seulement le resultat. Chaque etape nomme ses variables et leur valeur : population de la zone, taux de penetration retenu, panier ou ticket moyen, frequence annuelle, part de capture visee. Un lecteur doit pouvoir refaire le calcul et retrouver ton chiffre.
- Un seul TAM, un seul SAM, un seul SOM par annee. Si tu donnes une fourchette, elle sert partout ensuite a l'identique.
- L'emboitement TAM > SAM > SOM doit etre vrai en euros compares. Verifie-le avant d'ecrire : convertis tout dans la meme unite.
- Le SOM annee 1 depasse rarement quelques pour cent du SAM. Si ton calcul donne davantage, c'est que le SAM est sous-estime ou que le SOM est irrealiste : refais le calcul. Ne justifie JAMAIS un taux de capture eleve par un argument redactionnel.
- Ces trois valeurs sont reutilisees telles quelles aux chapitres 14 et 15 (manuel p. 6). Elles doivent etre justes ici, elles ne seront plus recalculees.
- Quand un outil d'execution de code est a ta disposition, pose ces calculs dedans au lieu de les faire de tete : l'emboitement TAM > SAM > SOM, les conversions d'unites et la montee en charge mensuelle sont des enchainements ou une erreur d'arrondi se propage jusqu'aux chapitres 14 et 15.
- Le livrable montre le calcul en langage METIER : variables, valeurs, formule, hypotheses et sources, comme l'exige la colonne « Formule et sources » du manuel p. 6. Il ne montre RIEN de la technique : ni code, ni sortie de console, ni mention d'un script, d'un outil, d'un calcul « verifie » ou d'une procedure. Tu ecris pour un porteur de projet et son banquier, pas un journal de travail.

[EXEMPLE DE NIVEAU — SOM pose variable par variable]
Extrait d'une etude EVKHA notee 8/10, secteur ETRANGER au tien (plateforme juridique, France) : ne reprends ni ses chiffres, ni son secteur, ni ses variables. Reprends sa MECANIQUE.
« Le modele distingue sept variables. Le nombre d'avocats actifs correspond a la part des avocats inscrits qui utilisent effectivement la plateforme, et non au nombre brut d'inscriptions mis en avant dans les objectifs du porteur de projet. Le nombre de consultations reservees par mois et par avocat actif mesure l'intensite d'usage une fois l'avocat engage. [...] Le taux d'annulation ou de report retire du calcul les rendez-vous reserves mais non honores. [...] Le revenu mensuel moyen par avocat actif resulte du calcul : (consultations x (1 - taux d'annulation) x frais de service net) + (part abonnee x abonnement). »
MECANIQUE A IMITER, point par point :
1. ANNONCE le nombre de variables de ton modele avant de les derouler.
2. DEFINIS chaque variable en une phrase, en la distinguant de la donnee voisine avec laquelle on la confondrait (ici : avocats ACTIFS et non avocats INSCRITS — l'ecart entre les deux est la variable la plus determinante du modele).
3. POSE la formule en clair, avec le signe des operations, pour que le porteur de projet puisse la refaire avec ses propres hypotheses.
4. DEDUIS les pertes reelles (annulations, defauts de paiement, commissions du prestataire) au lieu de raisonner sur un brut theorique.
5. APPLIQUE une montee en charge progressive, pas un effectif constant sur l'annee : les clients arrivent au fil des mois.
6. DESIGNE la variable la plus sensible du modele et dis en une phrase ce qui change si elle bouge.
Un SOM qui ne montre pas ses variables est un chiffre que personne ne peut discuter, donc un chiffre que le porteur de projet ne defendra pas devant son banquier.

DERIVATION SAM vers SOM — paragraphe obligatoire (c'est ce que le CHECK 1 verifie en priorite) :
Immediatement apres avoir annonce le SOM An1, insere un paragraphe intitule en gras '**Formule et derivation SOM depuis le SAM**' contenant :
1. La formule litterale : SOM = SAM × taux de capture
2. Les valeurs numeriques completees : SOM An1 = [SAM en euros] × [taux]% = [SOM en euros]
3. La justification du taux de capture retenu (une phrase)
4. La meme derivation pour le SOM An3
5. La verification de l'emboitement : TAM > SAM > SOM An3 > SOM An1 en euros sur une seule ligne
Ce paragraphe est non-negociable : sans lui, le chapitre est rejete par le CHECK 1 (bloc A — Fondations du marche).

Visuel utile (manuel) : graphique national/local + schema TAM/SAM/SOM. En fin de chapitre, genere UN graphique HTML en barres montrant la repartition ou la dynamique du marche local par segment, en utilisant ce pattern exact (adapte valeurs et etiquettes au contexte reel) :
<h3 style="font-size:13pt;margin:4mm 0 2mm">Repartition du marche local — segments cles</h3>
<table style="border-collapse:collapse;width:100%;margin:3mm 0;font-size:9pt">
<tr><td style="padding:1.5mm 3mm;border-bottom:0.5pt solid #EFEAD8;width:30%">Segment A</td><td style="padding:1.5mm 2mm;width:60%"><div style="background:#C9A227;height:5mm;width:72%;display:inline-block"></div></td><td style="padding:1.5mm 2mm;font-weight:bold;width:10%">XX %</td></tr>
<tr><td style="padding:1.5mm 3mm;border-bottom:0.5pt solid #EFEAD8">Segment B</td><td style="padding:1.5mm 2mm"><div style="background:#C9A227;height:5mm;width:50%;display:inline-block"></div></td><td style="padding:1.5mm 2mm;font-weight:bold">XX %</td></tr>
<tr><td style="padding:1.5mm 3mm">Segment C</td><td style="padding:1.5mm 2mm"><div style="background:#1A1A1A;height:5mm;width:28%;display:inline-block"></div></td><td style="padding:1.5mm 2mm;font-weight:bold">XX %</td></tr>
</table>
<p style="font-style:italic;font-size:8.5pt;color:#5A5A5A">Source : [cite ta source]. Estimations argumentees sur la base des donnees disponibles.</p>
Remplace Segment A/B/C et XX par les vraies donnees etablies dans l'analyse.

Lecture strategique attendue : Dire si la zone est pertinente, quelle part du marche est reellement accessible et quelles hypotheses doivent etre testees en priorite.

<!--
Prompt du chapitre 15 — Tableau de bord visuel du marché
Clé historique : em.15.graphiques_tableaux

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

CHAPITRE 15 — Tableau de bord visuel du marche (manuel §6, p. 15).
Objectif : consolider les visuels les plus utiles sans creer de nouvelles donnees.

Questions auxquelles ce chapitre doit repondre :
- Quels visuels permettent de comprendre immediatement les relations les plus importantes du marche ?
- Le tableau de bord couvre-t-il au minimum la taille, la croissance, le marche accessible, la cible ou les risques ?
- Chaque graphique possede-t-il un titre clair, une periode, une unite, une source courte et une lecture strategique ?
- Les visuels reprennent-ils strictement les chiffres-fondations sans creer de nouvelles donnees ?

Contenu obligatoire :
- 3 a 5 visuels maximum selectionnes selon le projet.
- Evolution du marche, TAM/SAM/SOM, cible, risque ou geographie selon pertinence.
- Donnees appelees directement depuis la fiche projet enrichie et les chapitres precedents. Aucune nouvelle valeur introduite.
- Titre, unite, periode, legende et source courte pour chaque visuel.
- Commentaire d'une a trois phrases par visuel.

Chaque visuel se demande en figure du catalogue (barres, camembert, courbes...), en citant des identifiants du socle de meme nature — jamais de valeurs en clair dans la figure, jamais de tableau mis en forme a la main.
Pour chaque graphique : titre H3, tableau barres avec valeurs reelles, legende courte sous le tableau en italique. Produis 3 a 5 graphiques (manuel §6, p. 15 : 3-5 visuels maximum) selectionnes selon le projet, en priorite parmi : (1) evolution du marche 2021-2026, (2) repartition CA cible par segment, (3) croissance projetee 2026-2030, (4) repartition clientele cible, (5) comparaison positionnement prix concurrents si disponible. Utilise les donnees chiffrees reelles etablies dans les chapitres precedents. Couleur principale des barres : #C9A227 (or EVKHA). Barres secondaires : #1A1A1A.

CONTRAINTE ABSOLUE — coherence chiffres-fondations pour ce chapitre :
Toutes les valeurs de taille de marche et de TCAC dans les graphiques DOIVENT correspondre exactement aux valeurs du bloc SOCLE VERROUILLE. Distinction obligatoire : `marche_mondial_taille` (marche total mondial) et `marche_continental_taille` (part continentale) sont deux chiffres DIFFERENTS — ne les confonds pas dans les titres ou legendes des graphiques.

Lecture strategique attendue : Faire de chaque visuel un outil de decision accompagne d'une courte interpretation, pas un simple element decoratif.

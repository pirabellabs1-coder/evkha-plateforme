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

CHAPITRE 15 — Tableau de bord visuel du marché (manuel §6, p. 15).
Objectif : consolider les visuels les plus utiles sans créer de nouvelles données.

Questions auxquelles ce chapitre doit répondre :
- Quels visuels permettent de comprendre immédiatement les relations les plus importantes du marché ?
- Le tableau de bord couvre-t-il au minimum la taille, la croissance, le marché accessible, la cible ou les risques ?
- Chaque graphique possède-t-il un titre clair, une période, une unité, une source courte et une lecture stratégique ?
- Les visuels reprennent-ils strictement les chiffres-fondations sans créer de nouvelles données ?

Contenu obligatoire :
- 3 à 5 visuels maximum selectionnes selon le projet.
- Évolution du marché, TAM/SAM/SOM, cible, risque ou géographie selon pertinence.
- Données appelees directement depuis la fiche projet enrichie et les chapitres précédents. Aucune nouvelle valeur introduite.
- Titre, unité, période, légende et source courte pour chaque visuel.
- Commentaire d'une a trois phrases par visuel.

Chaque visuel se demande en figure du catalogue (barres, camembert, courbes...), en citant des identifiants des données de référence de même nature — jamais de valeurs en clair dans la figure, jamais de tableau mis en forme a la main.
Pour chaque graphique : titre H3, tableau barres avec valeurs réelles, légende courte sous le tableau en italique. Produis 3 à 5 graphiques (manuel §6, p. 15 : 3-5 visuels maximum) selectionnes selon le projet, en priorité parmi : (1) évolution du marché 2021-2026, (2) répartition CA cible par segment, (3) croissance projetee 2026-2030, (4) répartition clientèle cible, (5) comparaison positionnement prix concurrents si disponible. Utilise les données chiffrées réelles établies dans les chapitres précédents. Couleur principale des barres : #C9A227 (or EVKHA). Barres secondaires : #1A1A1A.

CONTRAINTE ABSOLUE — cohérence chiffres-fondations pour ce chapitre :
Toutes les valeurs de taille de marché et de TCAC dans les graphiques DOIVENT correspondre exactement aux valeurs du bloc DONNÉES DE RÉFÉRENCE. Distinction obligatoire : `marche_mondial_taille` (marche total mondial) et `marche_continental_taille` (part continentale) sont deux chiffres DIFFÉRENTS — ne les confonds pas dans les titres ou légendes des graphiques.

Lecture stratégique attendue : Faire de chaque visuel un outil de décision accompagne d'une courte interprétation, pas un simple élément décoratif.

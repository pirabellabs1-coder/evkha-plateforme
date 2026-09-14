<!--
Prompt du chapitre 18 — SWOT de synthèse
Clé historique : em.18.swot

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

CHAPITRE 18 — SWOT de synthèse (manuel §6, p. 16).
Objectif : resumer les enseignements établis, sans inventer de nouveaux éléments.

Questions auxquelles ce chapitre doit répondre :
- Quelles forces et faiblesses internes ressortent réellement du projet et de son modèle ?
- Quelles opportunités et menaces externes ont ete établies dans les chapitres précédents ?
- Quels croisements SWOT font apparaître les priorités les plus importantes ?
- Quelles forces permettent de saisir une opportunité et quelles faiblesses aggravent une menace ?
- Quels arbitrages stratégiques decoulent de cette synthèse ?
- Quelles informations essentielles restent invisibles dans les quatre cases de la SWOT ?
- Quels sujets exigent une analyse complémentaire avant de prendre une décision définitive ?

Contenu obligatoire :
- 3 à 5 forces, faiblesses, opportunités et menaces.
- Origine traçable de chaque point dans un chapitre précédent.
- Distinction interne/externe respectee.
- Lecture croisee : forces pour saisir les opportunités, faiblesses face aux menaces.

Commence par 1 paragraphe d'introduction. Puis le SWOT en bloc `tableau` : quatre lignes (forces, faiblesses, opportunités, menaces), chaque cellule 1 à 2 phrases concrètes et chiffrées — les vrais éléments du projet. Ferme sur deux ou trois priorités tirées du CROISEMENT des cases, comme la règle de fond l'exige.
Remplis chaque cellule avec 3 à 5 points réels (manuel §6, p. 16 : 3-5 forces, faiblesses, opportunités et menaces), specifiques au projet, pas génériques. Chaque point indique sa source dans l'étude. Après le tableau, ajoute un paragraphe de lecture croisee : comment les forces compensent les faiblesses, comment les opportunités répondent aux menaces.

CONTRAINTE — chiffres de marché dans ce chapitre :
Quand tu mentionnes une taille de marché dans les opportunités ou menaces, utilise EXACTEMENT les valeurs du bloc DONNÉES DE RÉFÉRENCE. Distinction critique : `marche_mondial_taille` (marche total mondial) et `marche_continental_taille` (part continentale, ex. Europe IA strict) sont deux chiffres différents. Labellise chacun avec son périmètre exact (ex. 'marché européen IA 407 M€', jamais 'marché mondial 407 M€' si 407 M€ est la valeur continentale).

Approfondissement obligatoire (manuel) :
- Conserver une SWOT lisible avec 3 à 5 éléments solides par cadran, tous relies a des preuves déjà presentees.
- Après la matrice, ajouter OBLIGATOIREMENT une section rédigée intitulee « Ce que la SWOT ne dit pas ».
- Cette section traite les dépendances entre facteurs, la chronologie, la capacité réelle d'exécution, les arbitrages de ressources, les hypothèses encore fragiles et les signaux faibles.
- Préciser ce qui ne peut pas être conclu a partir de la seule SWOT : rentabilité, vitesse de conversion, réaction du marché, capacité opérationnelle ou efficacité future des recommandations.
- Terminer par 3 à 5 décisions a approfondir dans le chapitre 19, sans transformer la SWOT en liste de recommandations génériques.

Lecture stratégique attendue : Faire emerger des priorités par croisement des quatre cadrans, puis exposer honnetement ce que la SWOT ne permet pas de conclure.

<!--
Prompt du chapitre 3 — Analyse du positionnement actuel
Clé historique : str.03.positionnement_actuel

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

Analyse du positionnement actuel : quelle place occupe reellement l'entreprise sur son marche, comment est-elle percue, coherence entre image / offre / cible / prix / ambition. Identifie les risques de dilution ou de confusion de positionnement. GRAPHIQUE OBLIGATOIRE : apres l'analyse redigee, insere un bloc ```chart de type 'radar' avec title "Positionnement du projet", labels ["Clarte de l'offre", "Notoriete", "Prix pergu", "Differenciation", "Coherence marque", "Digital"], et une serie {"name": "Aujourd'hui", "values":[...]} avec des scores de 0 a 5 refletant l'etat REEL du business (pas ideal, pas projete). Si tu identifies un positionnement cible clair, ajoute une deuxieme serie {"name": "Cible", "values":[...]}. Le radar donne au dirigeant une lecture immediate des ecarts a combler.

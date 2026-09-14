<!--
Prompt du chapitre 13 — Cartographie des risques externes
Clé historique : em.13.cartographie_risques

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

CHAPITRE 13 — Cartographie des risques externes (manuel §6, p. 14).
Objectif : hierarchiser visuellement les risques externes selon leur probabilité et leur impact.

Questions auxquelles ce chapitre doit répondre :
- Quels risques externes sont assez importants pour figurer dans la cartographie ?
- Pourquoi leur probabilité et leur impact sont-ils positionnes a ce niveau ?
- Quels risques exigent une surveillance immédiate et quels indicateurs permettent de les détecter ?
- La carte reflète-t-elle exactement l'analyse du chapitre 12, sans ajout ni contradiction ?
- Quels risques evoluent rapidement et lesquels sont plus lents mais potentiellement plus graves ?
- Quelles dépendances externes echappent au controle du porteur de projet ?

Contenu obligatoire :
- 6 à 10 risques externes maximum, issus du chapitre 12 et conservant EXACTEMENT les mêmes intitules, catégories et évaluations qu'au chapitre 12.
- Matrice 3 x 3 ou 4 x 4 selon le nombre de risques, avec des définitions precises de chaque niveau de probabilité et d'impact.
- Placement cohérent avec les scores du registre, complete par l'horizon de survenance : immédiat, 12 mois, 2 à 3 ans ou long terme.
- Légende courte, lecture des priorités et indicateurs de surveillance.
- Aucun risque interne ni catégorie nouvelle non analysee au chapitre 12.

Introduction : 2 à 3 paragraphes d'analyse contextuelle des risques macro-environnementaux. Puis demande la figure `matrice_positionnement` : elle se construit seule a partir des risques notes du socle (probabilité x impact). Ne décris pas la matrice — commente ce qu'elle montre : risques critiques, risques a surveiller, parades.
Niveaux de couleur : CRITIQUE = background:#B73E3E / ELEVE = background:#E65100 / MODERE = background:#C9A227 / FAIBLE = background:#2E7D4F. Tous en color:#fff. Identifie 6 à 10 risques réels propres au secteur et a la zone, issus du chapitre 12 et portant les mêmes intitules qu'au chapitre 12 (manuel : 6 à 10 maximum). Termine par une légende courte sous le tableau expliquant la lecture des priorités.

Approfondissement obligatoire (manuel) :
- Faire apparaître les risques a surveillance prioritaire, les indicateurs associes et la fréquence de suivi recommandee.
- Ajouter une courte lecture des interdependances : quels risques pourraient se renforcer mutuellement ?
- Expliquer les limites de la carte : elle hierarchise les risques, mais ne mesure ni leur coût exact ni toutes leurs interactions.

Lecture stratégique attendue : Faire ressortir visuellement les risques externes qui necessitent une surveillance ou une action immédiate, puis expliquer ce que la carte change dans les décisions du porteur.

<!--
Prompt du chapitre 9 — Modèle économique et Business Model Canvas
Clé historique : bp.09.modele_bmc

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

Présente la logique économique globale : comment l'entreprise cree de la valeur, comment elle génère du chiffre d'affaires, structure des coûts principaux, marge brute estimee, point mort. Puis presente le Business Model Canvas en bloc `canvas` — PAS en bloc `tableau`.

Le bloc `canvas` contient un objet `canvas`, et c'est cet OBJET qui porte les
neuf briques :

    {"type": "canvas", "canvas": {"partenaires_cles": [...], "activites_cles": [...]}}

Les neuf champs vont DANS `canvas`, jamais à côté de `type`. Les voici :
`partenaires_cles`,
`activites_cles`, `ressources_cles`, `proposition_valeur`, `relation_client`,
`canaux`, `segments_clientele`, `structure_couts`, `sources_revenus`. Chacun
reçoit une liste de 2 à 4 éléments COURTS — une ligne chacun, pas un
paragraphe : ils s'affichent dans une case, et une phrase longue rend la carte
illisible.

Le rendu les dessine dans la disposition d'origine d'Osterwalder, celle que
tout lecteur de business plan reconnaît : ce que l'entreprise mobilise a
gauche, ce que le client reçoit a droite, l'argent en bas. C'est pour cela que
neuf lignes empilées ne conviennent pas — elles donnent une liste là où le
canvas est une carte, et le lecteur perd la lecture d'un coup d'oeil.

IMPORTANT : le contenu RÉEL du projet, jamais les exemples du modèle. Une
brique que le dossier client ne permet pas de remplir reste VIDE — un modèle
économique sans partenaires clés est une information utile, l'inventer pour
remplir la case ne l'est pas.

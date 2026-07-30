<!--
Prompt du chapitre 9 — Les 12 chiffres clés
Clé historique : em.09.douze_chiffres_cles

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

CHAPITRE 9 — Les 12 chiffres cles (manuel §6, p. 13).
Objectif : selectionner les donnees les plus fortes et reutilisables pour comprendre le marche en quelques minutes.
Contenu obligatoire :
- Exactement 12 chiffres issus du registre valide (fiche projet enrichie et chapitres precedents).
- Diversite : taille, croissance, comportements, frequence, prix, digital, environnement ou reglementation.
- Une explication courte et une consequence pour chaque chiffre.
- Annee, zone, unite et statut observe/estime/projete.
Visuel utile : tuiles chiffrees ou tableau synthetique lisible (manuel §6, p. 13). Les 12 chiffres doivent tous apparaitre dans le chapitre — aucun n'est a supprimer pour un visuel.
CONTRAINTE ABSOLUE — coherence chiffres-fondations : pour chaque chiffre faisant reference a la taille du marche (TAM mondial, continental, national) ou a un TCAC, tu DOIS utiliser EXACTEMENT la valeur presente dans le bloc CHIFFRES_FONDATIONS de ton contexte. Interdiction formelle de citer un chiffre de marche different de ceux du bloc CHIFFRES_FONDATIONS. Distinction critique : `taille_marche_mondial` et `taille_marche_continental` sont deux valeurs DIFFERENTES — ne confonds pas les deux dans les tuiles. Pour le premier chiffre cle (taille du marche), verifie que le libelle de zone ('Mondial', 'Europe', 'France'...) correspond exactement au perimetre reel de la valeur dans CHIFFRES_FONDATIONS. Si CHIFFRES_FONDATIONS contient 'taille_marche_continental = 1,1 Md EUR (2024)', alors ton chiffre cle doit afficher exactement '1,1 Md EUR (2024)', pas '900 M EUR', pas '1,2 Md EUR', pas aucune autre valeur.

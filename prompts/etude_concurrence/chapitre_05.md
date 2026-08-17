<!--
Prompt du chapitre 5 — Matrice de positionnement concurrentiel et zones stratégiques
Clé historique : ec.05.matrice_positionnement

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

Cartographier les 11 concurrents (8 directs, 3 indirects) et le projet sur deux axes strategiques, pour identifier zones saturees, niches disponibles et meilleure zone de differenciation. Il justifie le positionnement recommande au chapitre precedent et sert en pitch deck, dossier bancaire et presentation investisseurs. Grille identique pour directs et indirects, liste figee du chapitre 1.

## Définition des axes stratégiques pertinents
Retiens les deux axes les plus discriminants. Explore plusieurs combinaisons : prix contre qualite percue, innovation contre notoriete, niche ciblee contre marche de masse, ou toute autre combinaison pertinente au secteur. Justifie le choix et son pouvoir discriminant ; ecarte tout axe qui regrouperait tous les acteurs au meme endroit. Le livrable ne montre que les deux axes retenus (X et Y) et leur justification synthetique.

## Génération des données de la matrice
Produis un bloc `tableau` unique des 11 acteurs : nom, type (direct / indirect), position sur l'axe X, position sur l'axe Y, justification courte ; termine par la position recommandee du projet. Aucun chevauchement, projet distinguable ; en cas de chevauchement, repositionne legerement et documente le reajustement. Demande ensuite la matrice en figure `matrice_positionnement`, en citant comme axes DEUX codes de la grille de notation du socle — les deux criteres les plus discriminants. Une matrice decrite en prose, sans bloc `tableau` ni figure, est un echec.

## Interprétation stratégique de la matrice
Redige zones saturees, espaces libres ou sous-exploites, risques de cannibalisation, zone ideale du projet ; justifie chaque constat par la matrice, relie chaque espace libre a une opportunite concrete, alerte sur les zones encombrees.

Traite explicitement : quelles zones sont saturees, quels espaces restent sous-exploites, qui risque de se cannibaliser, quelle zone le projet doit occuper.

Interdits : listes a puces sans analyse, paragraphes generiques, complaisance, denigrement gratuit des concurrents, jargon inutile.

## A retenir
Prends du recul : nomme les consequences futures de chaque zone occupee ou laissee libre et relie la position visee aux decisions de gamme, de cible et d'investissement.

Termine par une recommandation claire de zone a occuper et une transition vers l'estimation des chiffres d'affaires et des parts de marche. Sources en fin de reponse uniquement.

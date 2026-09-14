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

Cartographier les 11 concurrents (8 directs, 3 indirects) et le projet sur deux axes stratégiques, pour identifier zones saturees, niches disponibles et meilleure zone de différenciation. Il justifie le positionnement recommande au chapitre précédent et sert en pitch deck, dossier bancaire et présentation investisseurs. Grille identique pour directs et indirects, liste figee du chapitre 1.

## Définition des axes stratégiques pertinents
Retiens les deux axes les plus discriminants. Explore plusieurs combinaisons : prix contre qualité perçue, innovation contre notoriété, niche ciblee contre marche de masse, ou toute autre combinaison pertinente au secteur. Justifie le choix et son pouvoir discriminant ; ecarte tout axe qui regrouperait tous les acteurs au même endroit. Le livrable ne montre que les deux axes retenus (X et Y) et leur justification synthétique.

## Génération des données de la matrice
Produis un bloc `tableau` unique des 11 acteurs : nom, type (direct / indirect), position sur l'axe X, position sur l'axe Y, justification courte ; termine par la position recommandee du projet. Aucun chevauchement, projet distinguable ; en cas de chevauchement, repositionne légèrement et documente le reajustement. Demande ensuite la matrice en figure `matrice_positionnement`, en citant comme axes DEUX codes de la grille de notation du socle — les deux critères les plus discriminants. Une matrice décrite en prose, sans bloc `tableau` ni figure, est un échec.

## Interprétation stratégique de la matrice
Rédige zones saturees, espaces libres ou sous-exploites, risques de cannibalisation, zone ideale du projet ; justifie chaque constat par la matrice, relie chaque espace libre a une opportunité concrète, alerte sur les zones encombrees.

Traite explicitement : quelles zones sont saturees, quels espaces restent sous-exploites, qui risque de se cannibaliser, quelle zone le projet doit occuper.

Interdits : listes à puces sans analyse, paragraphes génériques, complaisance, denigrement gratuit des concurrents, jargon inutile.

## A retenir
Prends du recul : nomme les conséquences futures de chaque zone occupee ou laissee libre et relie la position visee aux décisions de gamme, de cible et d'investissement.

Termine par une recommandation claire de zone a occuper et une transition vers l'estimation des chiffres d'affaires et des parts de marché. Sources en fin de réponse uniquement.

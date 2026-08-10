<!--
Prompt du chapitre 1 — Identification des concurrents
Clé historique : ec.01.identification

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

Identifie les acteurs structurants du marche et fige la selection de 11 concurrents qui servira de socle a toute l'etude.

## Intégration des concurrents pressentis par le client
Reprends chaque acteur cite par le client (nom, emplacement precis, site web, type percu), evalue sa pertinence strategique et tranche : a conserver, a ecarter, a approfondir. Ne valide et ne rejette aucun nom sans justification.

## Recherche autonome des concurrents directs
Va au-dela de la liste client. Direct = offre comparable, clientele similaire, zone pertinente ou accessible, gamme comparable. Liste large, 12 a 20 acteurs quand le marche le permet : nom, emplacement precis, site web officiel, description de l'offre, positionnement percu. Adapte le perimetre au niveau de geographie concurrentielle retenu. Tableau puis paragraphe d'analyse.

## Recherche autonome des concurrents indirects
Indirect = substitut repondant au meme besoin autrement. Produis 5 a 8 alternatives credibles : nom, emplacement precis, site web officiel, nature de l'alternative, lien de substitution, et dans quel cas un client cible la prefererait. Tableau puis paragraphe.

## Sélection finale 8 + 3
Retiens exactement 8 directs et 3 indirects, soit 11 acteurs, sur ces criteres : influence sur le marche, proximite d'offre, proximite de clientele, presence ou accessibilite sur la zone, visibilite digitale et terrain, intensite concurrentielle, potentiel d'enseignement strategique. Justifie chaque selection et chaque exclusion ; ecarter un nom cite par le client reste factuel, respectueux, argumente. Aucun acteur hors secteur cible.

## Base consolidée concurrents
Bloc `tableau` : nom, type, emplacement precis, structure, positionnement, site web, CA connu avec annee et source ou mention « non publié », methode d'estimation prevue si le CA manque (trafic, volume, prix moyen), niveau de fiabilite (certifie / estime / inconnu). Reprends la BASE CONSOLIDEE CONCURRENTS donnee avec le socle, telle quelle : memes acteurs, memes comptes. Aucun autre format — ni Markdown, ni CSV : tout format de donnees dans un texte arrive brut chez le client.

Traite au passage : qui occupe ce marche, qui concurrence frontalement et qui substitue, ce que la perception du client confirme ou corrige, quels acteurs meritent l'analyse approfondie.

## A retenir
Prends du recul : ce que ce paysage annonce pour le projet, quelles consequences en decoulent, quels acteurs pesent sur les decisions a venir. Termine par une note rappelant que cette liste de 11 est figee et sert de base aux chapitres suivants.

Si une donnee manque, indique ce qui est connu et sa fiabilite : n'invente jamais un site ni une adresse. Interdits : listes a puces sans analyse, paragraphes generiques, jargon inutile, jugement gratuit. Sources uniquement en fin de reponse totale.

<!--
Prompt du chapitre 6 — Estimation des chiffres d'affaires et parts de marché
Clé historique : ec.06.parts_de_marche

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

Chiffrer le poids des 11 concurrents (8 directs, 3 indirects) : chiffres d'affaires ou volumes d'activite, parts de marche locales, positionnement du projet objective. Donnees fiables si elles existent, estimations argumentees sinon, lecture exploitable en business plan et dossier bancaire. Grille identique pour directs et indirects, liste figee du chapitre 1.

## Extraction des chiffres d'affaires connus
Pour chaque acteur : CA publie ou estime, annee, source (site officiel, base professionnelle, presse), fiabilite (certifie / estime / inconnu). Privilegie les sources officielles, distingue CA publies et estimes, signale les particularites de perimetre (groupe contre filiale). CA non public : indique-le, precise qu'il sera estime ensuite, sans inventer de chiffre ici.

## Estimation des CA pour les acteurs non référencés
Estime les acteurs non references sur le volume d'activite observable : points de vente, clients ou prestations annuelles, panier moyen du secteur, frequence d'activite, presence digitale, benchmarks sectoriels. Pour chacun : fourchette basse et haute, hypotheses explicitees, fiabilite, methode. Fourchettes prudentes, coherentes avec la taille de l'acteur, defendables devant un banquier. Complete le tableau precedent et expose la methode.

## Projection des CA sur la période pertinente
Projette les 11 acteurs sur deux points : annee de reference recente (idealement 2024) et annee la plus recente exploitable (idealement debut 2026), a partir des TCAC sectoriels, des dynamiques de l'etude de marche et des evolutions visibles. Tableau : CA de reference, CA actuel, evolution, commentaire court. Distingue croissance, stabilite et perte de vitesse, chaque evolution justifiee.

## Estimation des parts de marché locales
Compare les CA estimes au marche total de la zone, produis un pourcentage par acteur et si possible pour le projet. Precise le perimetre (zone et segment), distingue acteurs dominants, emergents et fragilises. Presente-les comme des estimations, avec fourchette si pertinent et limites de la methode ; tableau de synthese puis interpretation.

Traite explicitement : qui domine, qui emerge, qui perd du terrain, ou se situe le projet en position actuelle ou projetee.

Interdits : chiffre invente sans methode, listes a puces sans analyse, paragraphes generiques, complaisance, jargon inutile, mention de donnees indisponibles — estime et documente.

## A retenir
Prends du recul : traduis ce rapport de forces en consequences futures et relie dominations et fragilisations aux decisions de prix et de conquete.

Termine par une synthese de la domination concurrentielle et une transition vers la conclusion analytique et les graphiques. Sources en fin de reponse.

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

Chiffrer le poids des 11 concurrents (8 directs, 3 indirects) : chiffres d'affaires ou volumes d'activité, parts de marché locales, positionnement du projet objective. Données fiables si elles existent, estimations argumentées sinon, lecture exploitable en business plan et dossier bancaire. Grille identique pour directs et indirects, liste figee du chapitre 1.

## Extraction des chiffres d'affaires connus
Pour chaque acteur : CA publie ou estime, année, source (site officiel, base professionnelle, presse), fiabilité (certifie / estime / inconnu). Privilegie les sources officielles, distingue CA publies et estimes, signale les particularites de périmètre (groupe contre filiale). CA non public : indique-le, précise qu'il sera estime ensuite, sans inventer de chiffre ici.

## Estimation des CA pour les acteurs non référencés
Estime les acteurs non référencés sur le volume d'activité observable : points de vente, clients ou prestations annuelles, panier moyen du secteur, fréquence d'activité, présence digitale, benchmarks sectoriels. Pour chacun : borne basse, borne haute et valeur retenue — en TROIS colonnes distinctes du tableau (borne basse | borne haute | valeur retenue), jamais les deux bornes dans une même cellule —, hypothèses explicitees, fiabilité, méthode. Estimations prudentes, cohérentes avec la taille de l'acteur, défendables devant un banquier. Complete le tableau précédent et expose la méthode.

## Projection des CA sur la période pertinente
Projette les 11 acteurs sur deux points : année de référence récente (idealement 2024) et année la plus récente exploitable (idealement début 2026), a partir des TCAC sectoriels, des dynamiques de l'étude de marché et des évolutions visibles. Tableau : CA de référence estimé, CA actuel estimé, évolution, commentaire court. Distingue croissance, stabilité et perte de vitesse, chaque évolution justifiee.

## Estimation des parts de marché locales
Compare les CA estimes au marché total de la zone, produis un pourcentage par acteur et si possible pour le projet. Précise le périmètre (zone et segment), distingue acteurs dominants, émergents et fragilises. Présente-les comme des estimations — valeur retenue, et bornes seulement si elles l'eclairent — et limites de la méthode ; tableau de synthèse puis interprétation.

Traite explicitement : qui domine, qui emerge, qui perd du terrain, ou se situe le projet en position actuelle ou projetee.

Interdits : chiffre invente sans méthode, listes à puces sans analyse, paragraphes génériques, complaisance, jargon inutile, mention de données indisponibles — estime et documente.

## A retenir
Prends du recul : traduis ce rapport de forces en conséquences futures et relie dominations et fragilisations aux décisions de prix et de conquête.

Termine par une synthèse de la domination concurrentielle et une transition vers la conclusion analytique et les graphiques. Sources en fin de réponse.

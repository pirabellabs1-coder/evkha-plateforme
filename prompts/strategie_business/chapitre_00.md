<!--
Prompt du chapitre 0 — Fiche projet
Clé historique : str.00.fiche_projet

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

Produis la fiche projet strategique complete : la base de reference unique du livrable, le socle de coherence strategique et le point de depart de tous les arbitrages. Tous les chapitres suivants seront rediges en fonction d'elle.

Sources a croiser : reponses du questionnaire, elements libres, notes desorganisees, documents complementaires, precisions ajoutees, elements conversationnels, previsionnels. Les documents fournis sont des elements de contexte et des indicateurs, pas des verites absolues : signale les incoherences entre eux.

REGLE ABSOLUE : un champ que le brief client ne permet pas de renseigner est rendu avec la mention « Non renseigne par le brief ». Jamais supprime en silence, jamais invente, jamais devine.

Quatre blocs obligatoires, dans cet ordre, chacun en tableau Markdown a deux colonnes ouvert par l'entete | Élément | Détail | puis |---|---|. Une ligne par champ, tous les champs presents.

## IDENTITÉ DU PROJET
Nom du projet, Secteur, Pays, Zone, Modèle économique, Positionnement, Clientèle cible, Niveau de gamme, Type de business, Niveau de maturité.

## STRUCTURE BUSINESS
Offres existantes, Verticales, Logique de revenus, Revenus récurrents, Activités principales, Activités secondaires, Dépendance au dirigeant, Niveau de structuration.

## VARIABLES DIRIGEANT
Vision, Objectifs, Ambition, Contraintes, Ressources disponibles, Capacité de développement, Charge actuelle, Niveau de dispersion.

## VARIABLES STRATÉGIQUES
Forces, Fragilités, Risques, Opportunités, Différenciateurs, Problèmes de positionnement, Problèmes d'offre, Problèmes de rentabilité, Problèmes d'organisation, Risques de dispersion, Potentiel scalable.

Valeurs courtes, factuelles, tirees du business reel. Interdits : formulations generiques, jargon inutile, complaisance, survalorisation artificielle du projet, evitement des sujets sensibles.

## QUESTIONS IMPLICITES DU CLIENT
Liste a puces de 5 a 8 vraies questions auxquelles le dirigeant cherche une reponse : business structure, modele soutenable, clients a cibler reellement, activites a arreter, chemin vers la rentabilite, clarte de l'offre, reduction de la charge, scalabilite, sortie du temps contre argent, structuration de la croissance.

## A retenir
Trois a cinq lignes de lecture directionnelle : dependances critiques, risques de dispersion, coherence economique du modele, ecarts reperes entre les donnees d'entree. Relie chaque constat aux arbitrages qu'il commande et aux consequences futures. Aucune puce sans analyse.

Termine par une phrase de synthese posant le point de depart strategique, puis annonce que ces constats sont repris et deployes dans l'Introduction générale.

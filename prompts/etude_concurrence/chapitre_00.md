<!--
Prompt du chapitre 0 — Fiche projet
Clé historique : ec.00.fiche_projet

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

FORMAT STRICT (Bloc 5 Consignes EVKHA) : produis EXACTEMENT un tableau Markdown a 2 colonnes (Label | Valeur), AUCUN texte autour, AUCUNE introduction, AUCUN commentaire. Les 8 lignes obligatoires dans cet ordre exact :
| Élément | Détail |
|---|---|
| Secteur | [valeur] |
| Pays | [valeur] |
| Projet | [description en 1-2 phrases] |
| Zone | [valeur] |
| Positionnement | [synthese 1 phrase] |
| Clientèle cible | [synthese 1 phrase] |
| Modèle économique | [synthese 1 phrase] |
| Éléments à retenir | [3 a 5 points cles separes par ' / '] |
Apres le tableau, saute une ligne et ajoute UNE SEULE section intitulee '## Questions auxquelles cette etude repond' avec une liste a puces de 4 a 5 questions implicites du porteur orientees benchmark concurrentiel (type 'Qui sont les concurrents directs les plus serieux ?'). Rien d'autre.

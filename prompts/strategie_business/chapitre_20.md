<!--
Prompt du chapitre 20 — Sources et méthodologie
Clé historique : str.20.sources

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

Liste les sources utilisees pour construire cette strategie, regroupees par thematique (Donnees marche, Benchmarks sectoriels, Reglementation, Documents client). Reprends en PRIORITE les URLs reelles du bloc SOURCES_WEB du contexte ; n'invente aucune URL absente de ce bloc. Format simple :
## Donnees marche
- Nom - URL si disponible
## Benchmarks sectoriels
- ...
Pas plus de 4-6 sources par thematique. Ajoute un court paragraphe '## Methodologie' (3-4 lignes) precisant la demarche (croisement diagnostic / arbitrages / feuille de route). Rester concis et structure.

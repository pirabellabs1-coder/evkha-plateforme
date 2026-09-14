<!--
Prompt du chapitre 19 — Sources et méthodologie
Clé historique : bp.21.sources

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

Liste les sources utilisées pour construire ce business plan, regroupees par thématique (Données sectorielles, Réglementation, Financements et aides, Concurrence, Documents fournis par le porteur). Reprends en PRIORITÉ les URLs réelles du bloc SOURCES_WEB du contexte ; n'invente aucune URL absente de ce bloc. Format simple :
## Données sectorielles
- Nom - URL si disponible
## Réglementation
- ...
Pas plus de 4-6 sources par thématique. Ajoute un court paragraphe '## Méthodologie' (3-4 lignes) precisant la démarche (période des données, hypothèses financières assumées). Rester concis et structure.

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

Liste les sources utilisees pour construire ce business plan, regroupees par thematique (Donnees sectorielles, Reglementation, Financements et aides, Concurrence, Documents fournis par le porteur). Reprends en PRIORITE les URLs reelles du bloc SOURCES_WEB du contexte ; n'invente aucune URL absente de ce bloc. Format simple :
## Donnees sectorielles
- Nom - URL si disponible
## Reglementation
- ...
Pas plus de 4-6 sources par thematique. Ajoute un court paragraphe '## Methodologie' (3-4 lignes) precisant la demarche (periode des donnees, hypotheses financieres assumees). Rester concis et structure.

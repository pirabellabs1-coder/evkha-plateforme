<!--
Prompt du chapitre 9 — Sources et méthodologie
Clé historique : ec.09.sources

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

Liste les sources reellement utilisees pour cette etude concurrentielle, regroupees par thematique (Concurrents identifies, Donnees de marche, Avis clients, Publications sectorielles). Reprends en PRIORITE les URLs reelles du bloc SOURCES_WEB du contexte ; n'invente aucune URL absente de ce bloc. Format simple :
## Concurrents identifies
- Nom - URL si disponible
## Donnees de marche
- ...
Pas plus de 4-6 sources par thematique. Ajoute un court paragraphe '## Methodologie' (3-4 lignes) expliquant la demarche de benchmark (perimetre, critere de selection des concurrents, periode des avis). Rester concis et structure.

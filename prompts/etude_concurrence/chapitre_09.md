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

Liste les sources réellement utilisées pour cette étude concurrentielle, regroupees par thématique (Concurrents identifies, Données de marché, Avis clients, Publications sectorielles). Reprends en PRIORITÉ les URLs réelles du bloc SOURCES_WEB du contexte ; n'invente aucune URL absente de ce bloc. Format simple :
## Concurrents identifies
- Nom - URL si disponible
## Données de marché
- ...
Pas plus de 4-6 sources par thématique. Ajoute un court paragraphe '## Méthodologie' (3-4 lignes) expliquant la démarche de benchmark (périmètre, critère de sélection des concurrents, période des avis). Rester concis et structure.

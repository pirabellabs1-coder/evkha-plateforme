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

Liste les sources utilisées pour construire ce business plan, regroupees par thématique (Données sectorielles, Réglementation, Financements et aides, Concurrence, Documents fournis par le porteur). Chaque source EXTÉRIEURE porte son adresse web, recopiée telle quelle depuis le bloc des sources web réelles du contexte, en fin de ligne : sans elle, la source n'est pas vérifiable et un banquier ne la retient pas. Une source dont ce bloc ne donne pas l'adresse ne figure PAS dans cette liste — si elle a servi, nomme-la dans la méthodologie comme repère. N'invente jamais une adresse. Les documents du client, eux, n'ont pas d'adresse. Format :
## Données sectorielles
- Organisme — ce que la source étaye — adresse recopiée du bloc
## Réglementation
- ...
Pas plus de 4-6 sources par thématique. Ajoute un court paragraphe '## Méthodologie' (3-4 lignes) precisant la démarche (période des données, hypothèses financières assumées). Rester concis et structure.

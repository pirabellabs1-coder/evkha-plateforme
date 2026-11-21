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

Liste les sources utilisées pour construire cette stratégie, regroupees par thématique (Données marche, Benchmarks sectoriels, Réglementation, Documents client). Chaque source EXTÉRIEURE porte son adresse web, recopiée telle quelle depuis le bloc des sources web réelles du contexte, en fin de ligne : sans elle, la source n'est pas vérifiable et un banquier ne la retient pas. Une source dont ce bloc ne donne pas l'adresse ne figure PAS dans cette liste — si elle a servi, nomme-la dans la méthodologie comme repère. N'invente jamais une adresse. Les documents du client, eux, n'ont pas d'adresse. Format :
## Données marche
- Organisme — ce que la source étaye — adresse recopiée du bloc
## Benchmarks sectoriels
- ...
La liste reprend les sources du bloc « SOURCES CITÉES DANS L'ÉTUDE », toutes et rien qu'elles : n'y ajoute aucune source collectée que le texte ne cite pas, même pour étoffer une thématique — une thématique sans source citée n'apparaît pas. Une source citée dont le bloc des sources web ne donne pas l'adresse se nomme dans la méthodologie, comme repère, avec ce qu'elle étaye. Ajoute un court paragraphe '## Méthodologie' (3-4 lignes) precisant la démarche (croisement diagnostic / arbitrages / feuille de route). Rester concis et structure.

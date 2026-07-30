<!--
Prompt du chapitre 1 — Identification des concurrents
Clé historique : ec.01.identification

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

Identification rigoureuse des concurrents directs (meme offre, meme cible) et indirects (substituts). Le nombre final DOIT toujours etre EXACTEMENT 8 concurrents directs et 3 indirects, ni plus, ni moins. REGLE D'EXCLUSIVITE ABSOLUE : un meme acteur NE PEUT PAS figurer a la fois dans les directs ET les indirects. Si un acteur semble appartenir aux deux categories, classe-le dans celle qui reflete sa principale modalite de concurrence (direct = meme offre ET meme cible ; indirect = substitut ou cible adjacente). Verifie avant de finaliser qu'aucun nom n'apparait dans les deux listes. Si VARIABLES_PROJET.CONCURRENTS propose des noms, ne les traite jamais tous integralement : selectionne parmi eux les 8 directs et les 3 indirects les plus pertinents pour ce projet (proximite d'offre, de cible, d'implantation), meme si la liste en propose davantage (10, 15, 20...). Si cette liste est vide, trop vague ou insuffisante pour atteindre 8 directs + 3 indirects, complete-la toi-meme avec des acteurs reels et plausibles du secteur et de la zone du projet pour atteindre exactement ce nombre, et poursuis l'etude normalement : ne t'arrete jamais et ne reduis jamais le nombre de concurrents traites faute d'indication du client. Pour chacun : nom, emplacement precis, site web. Termine par une base consolidee (type, structure, positionnement, CA connu ou estime + fiabilite).

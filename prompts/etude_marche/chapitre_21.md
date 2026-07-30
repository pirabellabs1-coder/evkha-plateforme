<!--
Prompt du chapitre 21 — Sources et méthodologie
Clé historique : em.21.sources_methodologie

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

CHAPITRE 21 — Sources et methodologie (manuel §6, p. 17).
Objectif : rendre la recherche verifiable et expliquer sobrement les methodes d'estimation.
Contenu obligatoire :
- Liste dedupliquee des sources par famille (Marche, Demographie, Reglementation, Concurrence, Documents client). Pour chaque source : titre, organisme, annee et URL verifiee. Reprends en PRIORITE les URLs reelles du bloc SOURCES_WEB du contexte.
- Courte methodologie : demarche de recherche, croisement de sources, periode des donnees, estimations construites (secteur adjacent, zone geographique proche, indicateur equivalent) et limites de l'etude.
- Mention sobre des calculs EVKHA (TAM/SAM/SOM, scenarios) sans detailler la pipeline technique.
Format :
## Marche
- Nom de la source, organisme, annee - https://...
## Demographie
- ...
## Methodologie
Un a deux paragraphes decrivant la demarche, les croisements et les limites. Pour chaque hypothese chiffree construite faute de source directe, indiquer la methode d'estimation.
Aucun visuel obligatoire. Mise en page bibliographique claire. N'utilise JAMAIS les formules « URL a confirmer », « lien indisponible », « donnees non disponibles » : sans source, ne cite pas la donnee dans le corps du document.
Si le bloc SOURCES_WEB du contexte est vide ou incomplet, utilise les patterns d'URL institutionnelles suivants (qui existent et sont stables) :
- Reglementation UE : https://eur-lex.europa.eu/
- Statistiques europeennes : https://ec.europa.eu/eurostat/
- OCDE donnees : https://data.oecd.org/
- INSEE France : https://www.insee.fr/
- Xerfi etudes sectorielles : https://www.xerfi.com/ (avec titre exact de l'etude si connue, sinon ne pas citer Xerfi)
- Statista : https://www.statista.com/ (avec titre exact de la fiche)
- McKinsey Global Institute : https://www.mckinsey.com/mgi/
Pour les sources sectorielles dont tu ne connais pas l'URL precise, cite uniquement le nom de l'organisme et l'annee sans URL. Ne pas inventer d'URL.

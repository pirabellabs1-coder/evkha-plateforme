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

Questions auxquelles ce chapitre doit repondre :
- Toutes les donnees utilisees peuvent-elles etre reliees a une source reelle et verifiee ?
- Les sources sont-elles suffisamment variees, recentes et adaptees a la zone etudiee ?
- Les chiffres decrivant la situation actuelle privilegient-ils 2024-2026, ou la derniere annee reellement disponible ?
- Les estimations expliquent-elles leur methode, leurs hypotheses, leur fourchette et leurs limites ?
- Les liens sont-ils complets, fonctionnels, dedupliques et regroupes par famille ?
- Les chiffres-fondations et les recommandations majeures reposent-ils sur plusieurs sources croisees plutot que sur une source isolee ?
- La liste finale reflete-t-elle toute la richesse des recherches reellement menees ?

Contenu obligatoire :
- Liste dedupliquee des sources par famille. Le manuel en nomme huit, a diversifier reellement : statistiques publiques, textes et organismes officiels, institutions internationales, federations professionnelles, observatoires, travaux academiques, cabinets reconnus et sources locales fiables.
- Viser 35 a 60 sources distinctes et reellement utiles pour une etude de 55 a 70 pages. En dessous de 35, l'etude n'est pas suffisamment etayee.
- Privilegier les chiffres 2024-2026 pour decrire la situation actuelle, et la derniere annee reellement disponible pour chaque indicateur. Une donnee anterieure a 2022 ne sert que d'historique ou de reference structurelle, jamais de preuve principale lorsqu'une donnee plus recente existe.
- Pour les chiffres-fondations et les affirmations determinantes, croiser au moins deux sources independantes lorsque c'est possible.
- Ne jamais considerer un blog, une page commerciale ou un agregateur comme preuve unique d'un chiffre important.
- Faire apparaitre toutes les sources reellement utilisees, y compris celles qui ont servi a confirmer, nuancer ou construire une estimation. Pour chaque source : titre, organisme, annee et URL verifiee. Reprends en PRIORITE les URLs reelles du bloc SOURCES WEB du contexte.
- Courte methodologie : demarche de recherche, croisement de sources, periode des donnees, estimations construites (secteur adjacent, zone geographique proche, indicateur equivalent) et limites de l'etude.
- Mention sobre des calculs EVKHA (TAM/SAM/SOM, scenarios) sans detailler la pipeline technique.
- Aucune source utilisee absente ; aucune source inutilisee ajoutee.
Format : une section « ## » par famille effectivement mobilisee, parmi les huit du manuel. N'ecris pas une section vide : une famille sans source n'apparait pas.
## Statistiques publiques
- Nom de la source, organisme, annee - https://...
## Organismes officiels et textes reglementaires
- ...
## Institutions internationales
- ...
## Federations professionnelles
- ...
## Observatoires et etudes sectorielles
- ...
## Travaux academiques
- ...
## Cabinets et analystes reconnus
- ...
## Sources locales et documents client
- ...
## Methodologie
Un a deux paragraphes decrivant la demarche, les croisements et les limites. Pour chaque hypothese chiffree construite faute de source directe, indiquer la methode d'estimation.
Aucun visuel obligatoire. Mise en page bibliographique claire. N'utilise JAMAIS les formules « URL a confirmer », « lien indisponible », « donnees non disponibles » : sans source, ne cite pas la donnee dans le corps du document.
Si le bloc SOURCES WEB du contexte est vide ou incomplet, utilise les patterns d'URL institutionnelles suivants (qui existent et sont stables) :
- Reglementation UE : https://eur-lex.europa.eu/
- Statistiques europeennes : https://ec.europa.eu/eurostat/
- OCDE donnees : https://data.oecd.org/
- INSEE France : https://www.insee.fr/
- Xerfi etudes sectorielles : https://www.xerfi.com/ (avec titre exact de l'etude si connue, sinon ne pas citer Xerfi)
- Statista : https://www.statista.com/ (avec titre exact de la fiche)
- McKinsey Global Institute : https://www.mckinsey.com/mgi/
Pour les sources sectorielles dont tu ne connais pas l'URL precise, cite uniquement le nom de l'organisme et l'annee sans URL. Ne pas inventer d'URL.

Lecture strategique attendue : Rendre l'etude pleinement verifiable, montrer la diversite des sources mobilisees et expliquer honnetement les estimations construites par croisement.

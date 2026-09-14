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

CHAPITRE 21 — Sources et méthodologie (manuel §6, p. 17).
Objectif : rendre la recherche vérifiable et expliquer sobrement les méthodes d'estimation.

Questions auxquelles ce chapitre doit répondre :
- Toutes les données utilisées peuvent-elles être reliées a une source réelle et vérifiée ?
- Les sources sont-elles suffisamment variees, récentes et adaptees a la zone étudiée ?
- Les chiffres décrivant la situation actuelle privilégient-ils 2024-2026, ou la dernière année réellement disponible ?
- Les estimations expliquent-elles leur méthode, leurs hypothèses, leur fourchette et leurs limites ?
- Les liens sont-ils complets, fonctionnels, dedupliques et regroupes par famille ?
- Les chiffres-fondations et les recommandations majeures reposent-ils sur plusieurs sources croisees plutôt que sur une source isolee ?
- La liste finale reflète-t-elle toute la richesse des recherches réellement menées ?

Contenu obligatoire :
- Liste dedupliquee des sources par famille. Le manuel en nomme huit, a diversifier réellement : statistiques publiques, textes et organismes officiels, institutions internationales, fédérations professionnelles, observatoires, travaux académiques, cabinets reconnus et sources locales fiables.
- Viser 35 à 60 sources distinctes et réellement utiles pour une étude de 55 à 70 pages. En dessous de 35, l'étude n'est pas suffisamment etayee.
- Privilégier les chiffres 2024-2026 pour décrire la situation actuelle, et la dernière année réellement disponible pour chaque indicateur. Une donnée antérieure a 2022 ne sert que d'historique ou de référence structurelle, jamais de preuve principale lorsqu'une donnée plus récente existe.
- Pour les chiffres-fondations et les affirmations determinantes, croiser au moins deux sources indépendantes lorsque c'est possible.
- Ne jamais considerer un blog, une page commerciale ou un agrégateur comme preuve unique d'un chiffre important.
- Faire apparaître toutes les sources réellement utilisées, y compris celles qui ont servi a confirmer, nuancer ou construire une estimation. Pour chaque source : titre, organisme, année et URL vérifiée. Reprends en PRIORITÉ les URLs réelles du bloc SOURCES WEB du contexte.
- Courte méthodologie : démarche de recherche, croisement de sources, période des données, estimations construites (secteur adjacent, zone géographique proche, indicateur équivalent) et limites de l'étude.
- Mention sobre des calculs EVKHA (TAM/SAM/SOM, scénarios) sans detailler la pipeline technique.
- Aucune source utilisee absente ; aucune source inutilisee ajoutee.
Format : une section « ## » par famille effectivement mobilisee, parmi les huit du manuel. N'écris pas une section vide : une famille sans source n'apparaît pas.
## Statistiques publiques
- Nom de la source, organisme, année - https://...
## Organismes officiels et textes réglementaires
- ...
## Institutions internationales
- ...
## Fédérations professionnelles
- ...
## Observatoires et études sectorielles
- ...
## Travaux académiques
- ...
## Cabinets et analystes reconnus
- ...
## Sources locales et documents client
- ...
## Méthodologie
Un a deux paragraphes décrivant la démarche, les croisements et les limites. Pour chaque hypothèse chiffrée construite faute de source directe, indiquer la méthode d'estimation.
Aucun visuel obligatoire. Mise en page bibliographique claire. N'utilise JAMAIS les formules « URL a confirmer », « lien indisponible », « données non disponibles » : sans source, ne cite pas la donnée dans le corps du document.
Si le bloc SOURCES WEB du contexte est vide ou incomplet, utilise les patterns d'URL institutionnelles suivants (qui existent et sont stables) :
- Réglementation UE : https://eur-lex.europa.eu/
- Statistiques europeennes : https://ec.europa.eu/eurostat/
- OCDE données : https://data.oecd.org/
- INSEE France : https://www.insee.fr/
- Xerfi études sectorielles : https://www.xerfi.com/ (avec titre exact de l'étude si connue, sinon ne pas citer Xerfi)
- Statista : https://www.statista.com/ (avec titre exact de la fiche)
- McKinsey Global Institute : https://www.mckinsey.com/mgi/
Pour les sources sectorielles dont tu ne connais pas l'URL précise, cite uniquement le nom de l'organisme et l'année sans URL. Ne pas inventer d'URL.

Lecture stratégique attendue : Rendre l'étude pleinement vérifiable, montrer la diversite des sources mobilisées et expliquer honnetement les estimations construites par croisement.

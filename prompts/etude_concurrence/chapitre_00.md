<!--
Prompt du chapitre 0 — Fiche projet
Clé historique : ec.00.fiche_projet

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

FICHE PROJET — base de reference unique de l'etude de la concurrence (manuel p. 6-7).
Objectif : transformer le brief client, le questionnaire et les precisions transmises en une fiche exploitable, reinjectee dans tous les chapitres pour garantir la coherence du livrable, la continuite de l'analyse, l'adaptation au projet reel du client, l'absence de reponses generiques et la coherence avec l'etude de marche lorsqu'elle existe.

FORMAT STRICT : produis EXACTEMENT un tableau Markdown a 2 colonnes, AUCUN texte autour, AUCUNE introduction, AUCUN commentaire. Les 10 lignes obligatoires dans cet ordre exact :
| Élément | Détail |
|---|---|
| Secteur | [nom precis du secteur etudie] |
| Pays | [pays principal concerne] |
| Projet | [description claire et synthetique, 1-2 phrases] |
| Zone | [zone geographique etudiee : nationale, regionale, departementale, locale, transfrontaliere, en ligne / digitale, internationale, mixte] |
| Positionnement | [niveau de gamme ou angle strategique : entree de gamme, accessible, premium, haut de gamme, specialise, local, innovant, hybride, B2B, B2C, mixte] |
| Clientèle cible | [typologie principale de clients vises, 1 phrase] |
| Modèle économique | [mode de generation du chiffre d'affaires, 1 phrase] |
| Éléments à retenir | [3 a 5 points cles separes par ' / '] |
| Concurrents pressentis par le client | [pour chaque acteur cite spontanement par le porteur : nom, type percu par le client (direct / indirect), precisions transmises (lien, localisation, ressenti) ; separer les acteurs par ' / '] |
| Niveau de géographie concurrentielle | [une seule valeur parmi : « une concurrence locale uniquement (exemple : un restaurant, un mariage, un service de proximité) », « une concurrence nationale », « une concurrence nationale + internationale », « une concurrence digitale sans frontière »] |

Un champ non renseignable depuis le brief se rend « Non renseigne par le brief ». Ne supprime jamais une ligne. N'invente jamais un concurrent pressenti ni un niveau de geographie.

Apres le tableau, saute une ligne et ajoute la section '## Questions auxquelles cette etude repond' : liste a puces de 4 a 5 questions implicites du porteur orientees benchmark concurrentiel — qui occupe reellement son marche, comment se positionnent ces acteurs, ce que chacun fait bien ou mal, ou se situent les espaces strategiques disponibles, comment le projet peut se differencier durablement, quels leviers concurrentiels actionner des le lancement.

Puis la section '## Lecture strategique' : 3 a 5 lignes redigees. Enonce ce que le niveau de geographie concurrentielle impose a la suite du livrable — cette variable conditionne toute la profondeur de la recherche concurrentielle — et ce que les concurrents pressentis revelent de la connaissance terrain du porteur, en indiquant les consequences pour la recherche a venir. Interdits : listes de points successifs sans analyse, paragraphes vagues ou generiques, complaisance vis-a-vis du projet client, jargon inutile.

Termine par une phrase de transition vers le chapitre Identification des concurrents. Rien d'autre.

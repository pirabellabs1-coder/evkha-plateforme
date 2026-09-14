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

FICHE PROJET — base de référence unique de l'étude de la concurrence (manuel p. 6-7).
Objectif : transformer le brief client, le questionnaire et les precisions transmises en une fiche exploitable, reinjectee dans tous les chapitres pour garantir la cohérence du livrable, la continuité de l'analyse, l'adaptation au projet réel du client, l'absence de réponses génériques et la cohérence avec l'étude de marché lorsqu'elle existe.

FORMAT STRICT : produis EXACTEMENT un tableau Markdown a 2 colonnes, AUCUN texte autour, AUCUNE introduction, AUCUN commentaire. Les 10 lignes obligatoires dans cet ordre exact :
| Élément | Détail |
|---|---|
| Secteur | [nom précis du secteur etudie] |
| Pays | [pays principal concerne] |
| Projet | [description claire et synthétique, 1-2 phrases] |
| Zone | [zone géographique étudiée : nationale, régionale, departementale, locale, transfrontaliere, en ligne / digitale, internationale, mixte] |
| Positionnement | [niveau de gamme ou angle stratégique : entree de gamme, accessible, premium, haut de gamme, specialise, local, innovant, hybride, B2B, B2C, mixte] |
| Clientèle cible | [typologie principale de clients vises, 1 phrase] |
| Modèle économique | [mode de génération du chiffre d'affaires, 1 phrase] |
| Éléments à retenir | [3 à 5 points clés separes par ' / '] |
| Concurrents pressentis par le client | [pour chaque acteur cite spontanement par le porteur : nom, type perçu par le client (direct / indirect), precisions transmises (lien, localisation, ressenti) ; séparer les acteurs par ' / '] |
| Niveau de géographie concurrentielle | [une seule valeur parmi : « une concurrence locale uniquement (exemple : un restaurant, un mariage, un service de proximité) », « une concurrence nationale », « une concurrence nationale + internationale », « une concurrence digitale sans frontière »] |
| Devise | Devise de référence du document, déduite du pays. Si le brief mélange plusieurs monnaies, dis laquelle fait foi et le taux retenu. |
| Lecteur final | A qui le document est destine (porteur seul, banque, investisseur, jury, partenaire) et niveau de langage attendu. Deduis-le du projet si le brief ne le dit pas, et dis que c'est une déduction. |

Un champ non renseignable depuis le brief se rend « Non renseigne par le brief ». Ne supprime jamais une ligne. N'invente jamais un concurrent pressenti ni un niveau de géographie.

Après le tableau, saute une ligne et ajoute la section '## Questions auxquelles cette étude répond' : liste à puces de 4 à 5 questions implicites du porteur orientees benchmark concurrentiel — qui occupe réellement son marché, comment se positionnent ces acteurs, ce que chacun fait bien ou mal, ou se situent les espaces stratégiques disponibles, comment le projet peut se différencier durablement, quels leviers concurrentiels actionner des le lancement.

Puis la section '## Lecture stratégique' : 3 à 5 lignes rédigées. Énonce ce que le niveau de géographie concurrentielle impose a la suite du livrable — cette variable conditionne toute la profondeur de la recherche concurrentielle — et ce que les concurrents pressentis revelent de la connaissance terrain du porteur, en indiquant les conséquences pour la recherche a venir. Interdits : listes de points successifs sans analyse, paragraphes vagues ou génériques, complaisance vis-a-vis du projet client, jargon inutile.


## Points non specifies par le client
Liste a puces de ce que la demande ne précise pas et que tu laisses donc ouvert (budget, délai, forme juridique, financement, capacité de production...). Marque chacun « provisoire ». Écris « Aucun » si la demande ne laisse rien d'ouvert. N'INVENTE JAMAIS la valeur manquante : la signaler EST la réponse attendue, et le relecteur du CHECK INITIAL l'accepte comme telle.

Termine par une phrase de transition vers le chapitre Identification des concurrents. Rien d'autre.

<!--
Prompt du chapitre 0 — Fiche projet
Clé historique : str.00.fiche_projet

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

Produis la fiche projet stratégique. Le document en fait « la base de référence unique du livrable, le socle de cohérence stratégique, et le point de départ de tous les arbitrages » : tous les chapitres suivants seront rédigés en fonction d'elle, et elle y sera reinjectee.

Croise TOUTES les données d'entree : réponses du questionnaire, éléments libres, notes desorganisees, documents complémentaires, precisions ajoutées, éléments conversationnels, previsionnels. Quand deux sources se contredisent, signale l'écart au lieu de trancher en silence.

RÈGLE ABSOLUE : un champ que le brief ne permet pas de renseigner porte la mention « Non renseigne par le brief ». Jamais supprime, jamais devine, jamais invente. Un champ absent se voit et se comble ; un champ invente contamine les vingt chapitres qui s'appuieront dessus.

Quatre tableaux Markdown a deux colonnes, dans cet ordre, chacun précédé de son titre et ouvert par l'entete | Élément | Détail | puis |---|---|. Les 37 lignes sont obligatoires : aucune ne se supprime, même vide.

## Identité du projet
| Nom du projet | [nom commercial ou de travail] |
| Secteur | [activité précise, pas la catégorie large] |
| Pays | [valeur] |
| Zone | [ville, région ou périmètre réel d'activité] |
| Modèle économique | [comment le chiffre d'affaires se génère, 1 phrase] |
| Positionnement | [place revendiquee sur le marché, 1 phrase] |
| Clientèle cible | [typologie principale visee, 1 phrase] |
| Niveau de gamme | [accessible, milieu de gamme, premium, haut de gamme] |
| Type de business | [service, produit, hybride ; B2B, B2C, mixte] |
| Niveau de maturité | [lancement, validation, structuration, croissance, transition] |
| Devise | Devise de référence du document, déduite du pays. Si le brief mélange plusieurs monnaies, dis laquelle fait foi et le taux retenu. |
| Lecteur final | A qui le document est destine (porteur seul, banque, investisseur, jury, partenaire) et niveau de langage attendu. Deduis-le du projet si le brief ne le dit pas, et dis que c'est une déduction. |

## Structure business
| Offres existantes | [ce qui est réellement vendu aujourd'hui] |
| Verticales | [axes ou segments d'activité distincts] |
| Logique de revenus | [d'où vient la marge, quelles activités la portent] |
| Revenus récurrents | [part et nature du récurrent, ou absence] |
| Activités principales | [ce qui occupe l'essentiel du temps et du CA] |
| Activités secondaires | [le reste, y compris ce qui est peu rentable] |
| Dépendance au dirigeant | [ce qui ne tourne pas sans lui] |
| Niveau de structuration | [processus, équipe, outils : ce qui tient, ce qui manque] |

## Variables dirigeant
| Vision | [ce que le dirigeant veut construire] |
| Objectifs | [ce qu'il vise concrètement, avec horizon si donne] |
| Ambition | [niveau de développement recherche] |
| Contraintes | [temps, trésorerie, compétences, personnel, réglementaire] |
| Ressources disponibles | [ce sur quoi il peut réellement s'appuyer] |
| Capacité de développement | [marge de manoeuvre réelle pour engager du nouveau] |
| Charge actuelle | [niveau de saturation opérationnelle] |
| Niveau de dispersion | [nombre de fronts ouverts simultanément] |

## Variables stratégiques
| Forces | [avantages réels et défendables, pas les intentions] |
| Fragilités | [ce qui expose le modèle, nomme franchement] |
| Risques | [ce qui peut faire deraper la trajectoire] |
| Opportunités | [leviers accessibles a court et moyen terme] |
| Différenciateurs | [ce qui distingue vraiment, hors discours] |
| Problèmes de positionnement | [flou, dilution, écart image / ambition] |
| Problèmes d'offre | [lisibilité, cohérence, empilement] |
| Problèmes de rentabilité | [marges, activités energivores, prix] |
| Problèmes d'organisation | [processus, délégation, outils] |
| Risques de dispersion | [ce qui eparpille l'énergie et le capital] |
| Potentiel scalable | [ce qui peut croitre sans croitre le temps dirigeant] |

Valeurs courtes et factuelles, tirées du business réel. Interdits : formulations génériques, jargon, complaisance, survalorisation du projet, evitement des sujets qui fachent. Une fragilité nommée franchement vaut mieux qu'une fragilité maquillee — c'est elle qui commandera les arbitrages.

## Questions auxquelles cette stratégie répond
Liste a puces de 5 à 8 questions : les VRAIES questions que le dirigeant se pose, déduites du brief et non recopiées d'une liste type. Le document en donne des exemples : mon business est-il structure, mon modèle est-il soutenable, quels clients cibler réellement, quelles activités arrêter, comment devenir plus rentable, mon offre est-elle claire, comment réduire ma charge, comment sortir du temps contre argent.


## Points non specifies par le client
Liste a puces de ce que la demande ne précise pas et que tu laisses donc ouvert (budget, délai, forme juridique, financement, capacité de production...). Marque chacun « provisoire ». Écris « Aucun » si la demande ne laisse rien d'ouvert. N'INVENTE JAMAIS la valeur manquante : la signaler EST la réponse attendue, et le relecteur du CHECK INITIAL l'accepte comme telle.

## À retenir
Trois a cinq lignes de lecture directionnelle : dépendances critiques, risques de dispersion, cohérence économique du modèle, écarts releves entre les données d'entree. Relie chaque constat a l'arbitrage qu'il commande. Aucune puce sans analyse.

Termine par une phrase posant le point de départ stratégique, puis annonce que ces constats sont deployes dans l'introduction générale.

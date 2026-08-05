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

Produis la fiche projet strategique. Le document en fait « la base de reference unique du livrable, le socle de coherence strategique, et le point de depart de tous les arbitrages » : tous les chapitres suivants seront rediges en fonction d'elle, et elle y sera reinjectee.

Croise TOUTES les donnees d'entree : reponses du questionnaire, elements libres, notes desorganisees, documents complementaires, precisions ajoutees, elements conversationnels, previsionnels. Quand deux sources se contredisent, signale l'ecart au lieu de trancher en silence.

REGLE ABSOLUE : un champ que le brief ne permet pas de renseigner porte la mention « Non renseigne par le brief ». Jamais supprime, jamais devine, jamais invente. Un champ absent se voit et se comble ; un champ invente contamine les vingt chapitres qui s'appuieront dessus.

Quatre tableaux Markdown a deux colonnes, dans cet ordre, chacun precede de son titre et ouvert par l'entete | Élément | Détail | puis |---|---|. Les 37 lignes sont obligatoires : aucune ne se supprime, meme vide.

## Identité du projet
| Nom du projet | [nom commercial ou de travail] |
| Secteur | [activite precise, pas la categorie large] |
| Pays | [valeur] |
| Zone | [ville, region ou perimetre reel d'activite] |
| Modèle économique | [comment le chiffre d'affaires se genere, 1 phrase] |
| Positionnement | [place revendiquee sur le marche, 1 phrase] |
| Clientèle cible | [typologie principale visee, 1 phrase] |
| Niveau de gamme | [accessible, milieu de gamme, premium, haut de gamme] |
| Type de business | [service, produit, hybride ; B2B, B2C, mixte] |
| Niveau de maturité | [lancement, validation, structuration, croissance, transition] |

## Structure business
| Offres existantes | [ce qui est reellement vendu aujourd'hui] |
| Verticales | [axes ou segments d'activite distincts] |
| Logique de revenus | [d'ou vient la marge, quelles activites la portent] |
| Revenus récurrents | [part et nature du recurrent, ou absence] |
| Activités principales | [ce qui occupe l'essentiel du temps et du CA] |
| Activités secondaires | [le reste, y compris ce qui est peu rentable] |
| Dépendance au dirigeant | [ce qui ne tourne pas sans lui] |
| Niveau de structuration | [processus, equipe, outils : ce qui tient, ce qui manque] |

## Variables dirigeant
| Vision | [ce que le dirigeant veut construire] |
| Objectifs | [ce qu'il vise concretement, avec horizon si donne] |
| Ambition | [niveau de developpement recherche] |
| Contraintes | [temps, tresorerie, competences, personnel, reglementaire] |
| Ressources disponibles | [ce sur quoi il peut reellement s'appuyer] |
| Capacité de développement | [marge de manoeuvre reelle pour engager du nouveau] |
| Charge actuelle | [niveau de saturation operationnelle] |
| Niveau de dispersion | [nombre de fronts ouverts simultanement] |

## Variables stratégiques
| Forces | [avantages reels et defendables, pas les intentions] |
| Fragilités | [ce qui expose le modele, nomme franchement] |
| Risques | [ce qui peut faire deraper la trajectoire] |
| Opportunités | [leviers accessibles a court et moyen terme] |
| Différenciateurs | [ce qui distingue vraiment, hors discours] |
| Problèmes de positionnement | [flou, dilution, ecart image / ambition] |
| Problèmes d'offre | [lisibilite, coherence, empilement] |
| Problèmes de rentabilité | [marges, activites energivores, prix] |
| Problèmes d'organisation | [processus, delegation, outils] |
| Risques de dispersion | [ce qui eparpille l'energie et le capital] |
| Potentiel scalable | [ce qui peut croitre sans croitre le temps dirigeant] |

Valeurs courtes et factuelles, tirees du business reel. Interdits : formulations generiques, jargon, complaisance, survalorisation du projet, evitement des sujets qui fachent. Une fragilite nommee franchement vaut mieux qu'une fragilite maquillee — c'est elle qui commandera les arbitrages.

## Questions auxquelles cette stratégie répond
Liste a puces de 5 a 8 questions : les VRAIES questions que le dirigeant se pose, deduites du brief et non recopiees d'une liste type. Le document en donne des exemples : mon business est-il structure, mon modele est-il soutenable, quels clients cibler reellement, quelles activites arreter, comment devenir plus rentable, mon offre est-elle claire, comment reduire ma charge, comment sortir du temps contre argent.

## À retenir
Trois a cinq lignes de lecture directionnelle : dependances critiques, risques de dispersion, coherence economique du modele, ecarts releves entre les donnees d'entree. Relie chaque constat a l'arbitrage qu'il commande. Aucune puce sans analyse.

Termine par une phrase posant le point de depart strategique, puis annonce que ces constats sont deployes dans l'introduction generale.

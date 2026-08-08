<!--
Prompt du chapitre 0 — Fiche projet
Clé historique : em.00.fiche_projet

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

FICHE PROJET — carte d'identite de l'etude (manuel §2, p. 3).
Objectif : reformuler le brief Tally et les pieces jointes en une fiche claire, qui reste presente pendant toute la production et est enrichie apres chaque CHECK.

FORMAT STRICT : produis EXACTEMENT un tableau Markdown a 2 colonnes, aucun texte autour, aucune introduction, aucun commentaire. Rubriques obligatoires dans cet ordre (manuel §2) :
| Rubrique | Contenu |
|---|---|
| Projet | Nom, activite envisagee, offre, stade d'avancement et objectif du porteur. |
| Marche exact | Secteur principal, sous-secteur, produits ou services reellement concernes. |
| Geographie | Pays, ville ou zone d'implantation, puis continent pertinent. Jamais l'Europe par defaut. |
| Devise | Devise de reference de l'etude, deduite du pays. Si le brief melange plusieurs monnaies, dis laquelle fait foi et le taux retenu. |
| Clientele | B2C, B2B, institutions, cibles deja envisagees, profil et besoins. |
| Positionnement | Niveau de gamme, proposition de valeur, particularites, differenciation envisagee. |
| Modele | Mode de vente, canaux, frequence, revenus attendus et capacites connues. |
| Demandes explicites | Toutes les questions et attentes ecrites par le client, sans en oublier une. |
| Questions implicites | Ce qu'un porteur de projet dans ce domaine doit normalement comprendre avant de se lancer. |
| Contraintes | Budget, delai, reglementation pressentie, ressources, limites, points sensibles. |
| Identite visuelle | Logo fourni, couleurs EVKHA, consignes de marque et format final. |
| Lecteur final | A qui l'etude est destinee (porteur seul, banque, investisseur, jury, partenaire) et niveau de langage attendu. Deduis-le du projet si le brief ne le dit pas, et dis que c'est une deduction. |

Apres le tableau, saute une ligne et ajoute DEUX sections, dans cet ordre, et rien d'autre.

« ## Questions auxquelles cette etude repond » : liste a puces de 4 a 5 questions du porteur (explicites + implicites).

« ## Points non specifies par le client » : liste a puces de ce que la demande ne precise pas et que tu laisses donc ouvert (budget de l'etude, delai, forme juridique, financement, capacite de production...). Marque chacun « provisoire ». Ecris « Aucun » si la demande ne laisse rien d'ouvert. N'INVENTE JAMAIS la valeur manquante : la signaler EST la reponse attendue, et le relecteur du CHECK INITIAL l'accepte comme telle.

Aucune phrase meta du type « Voici la fiche projet ».

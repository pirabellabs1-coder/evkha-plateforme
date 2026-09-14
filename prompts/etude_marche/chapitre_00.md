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

FICHE PROJET — carte d'identité de l'étude (manuel §2, p. 3).
Objectif : reformuler le brief Tally et les pièces jointes en une fiche claire, qui reste presente pendant toute la production et est enrichie après chaque CHECK.

FORMAT STRICT : produis EXACTEMENT un tableau Markdown a 2 colonnes, aucun texte autour, aucune introduction, aucun commentaire. Rubriques obligatoires dans cet ordre (manuel §2) :
| Rubrique | Contenu |
|---|---|
| Projet | Nom, activité envisagee, offre, stade d'avancement et objectif du porteur. |
| Marche exact | Secteur principal, sous-secteur, produits ou services réellement concernes. |
| Géographie | Pays, ville ou zone d'implantation, puis continent pertinent. Jamais l'Europe par défaut. |
| Devise | Devise de référence de l'étude, déduite du pays. Si le brief mélange plusieurs monnaies, dis laquelle fait foi et le taux retenu. |
| Clientèle | B2C, B2B, institutions, cibles déjà envisagees, profil et besoins. |
| Positionnement | Niveau de gamme, proposition de valeur, particularites, différenciation envisagee. |
| Modèle | Mode de vente, canaux, fréquence, revenus attendus et capacités connues. |
| Demandes explicites | Toutes les questions et attentes écrites par le client, sans en oublier une. |
| Questions implicites | Ce qu'un porteur de projet dans ce domaine doit normalement comprendre avant de se lancer. |
| Contraintes | Budget, délai, réglementation pressentie, ressources, limites, points sensibles. |
| Identité visuelle | Logo fourni, couleurs EVKHA, consignes de marque et format final. |
| Lecteur final | A qui l'étude est destinee (porteur seul, banque, investisseur, jury, partenaire) et niveau de langage attendu. Deduis-le du projet si le brief ne le dit pas, et dis que c'est une déduction. |

Après le tableau, saute une ligne et ajoute DEUX sections, dans cet ordre, et rien d'autre.

« ## Questions auxquelles cette étude répond » : liste à puces de 4 à 5 questions du porteur (explicites + implicites).

« ## Points non specifies par le client » : liste à puces de ce que la demande ne précise pas et que tu laisses donc ouvert (budget de l'étude, délai, forme juridique, financement, capacité de production...). Marque chacun « provisoire ». Écris « Aucun » si la demande ne laisse rien d'ouvert. N'INVENTE JAMAIS la valeur manquante : la signaler EST la réponse attendue, et le relecteur du CHECK INITIAL l'accepte comme telle.

Aucune phrase méta du type « Voici la fiche projet ».

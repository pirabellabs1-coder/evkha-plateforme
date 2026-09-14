<!--
Prompt du chapitre 0 — Fiche projet
Clé historique : bp.00.fiche_projet

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

FORMAT STRICT (Bloc 5 Consignes EVKHA) : produis EXACTEMENT un tableau Markdown a 2 colonnes (Label | Valeur), AUCUN texte autour, AUCUNE introduction, AUCUN commentaire. Les 8 lignes obligatoires dans cet ordre exact :
| Élément | Détail |
|---|---|
| Secteur | [valeur] |
| Pays | [valeur] |
| Projet | [description en 1-2 phrases] |
| Zone | [valeur] |
| Positionnement | [synthèse 1 phrase] |
| Clientèle cible | [synthèse 1 phrase] |
| Modèle économique | [synthèse 1 phrase] |
| Éléments à retenir | [3 à 5 points clés separes par ' / '] |
| Devise | Devise de référence du document, déduite du pays. Si le brief mélange plusieurs monnaies, dis laquelle fait foi et le taux retenu. |
| Lecteur final | A qui le document est destine (porteur seul, banque, investisseur, jury, partenaire) et niveau de langage attendu. Deduis-le du projet si le brief ne le dit pas, et dis que c'est une déduction. |
Après le tableau, saute une ligne et ajoute UNE SEULE section intitulee '## Questions auxquelles ce business plan répond' avec une liste à puces de 4 à 5 questions implicites du porteur orientees viabilité et financement (type 'Le projet est-il rentable des l'année 1 ?'). Rien d'autre.

« ## Points non specifies par le client » : liste à puces de ce que la demande ne précise pas et que tu laisses donc ouvert (budget, délai, forme juridique, financement, capacité de production...). Marque chacun « provisoire ». Écris « Aucun » si la demande ne laisse rien d'ouvert. N'INVENTE JAMAIS la valeur manquante : la signaler EST la réponse attendue, et le relecteur du CHECK INITIAL l'accepte comme telle.


<!--
Prompt du chapitre 20 — Annexes
Clé historique : bp.20.annexes

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

29/09/2026 : un statut « traitée » se PROUVE. Business plan ÉCLORE : l'annexe
déclarait « traité » ce que le document ne traitait pas, à partir des seuls
résumés des chapitres, et rien ne contrôle un « traité » faux (diagnostic du
29/09/2026, § 3.10). Le statut calculé viendra plus tard ; en attendant, la
consigne exige le chapitre ET la section, et fait de « partiellement traitée »
le statut du doute.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
  {{ renvoi_<clé> }} : « chapitre N « Titre » », lu dans le plan du livrable
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

Annexes : une réponse explicite à chaque demande spécifique du client, dans un bloc `tableau` — une ligne par demande : la demande, son statut, où elle est traitée, ce qui manque.

Chaque demande reçoit UN statut parmi trois, et chacun se prouve :
- « traitée » : UNIQUEMENT si tu nommes le chapitre ET la section qui y répondent en entier — numéro et intitulé, tels que les résumés des chapitres précédents te les montrent. N'invente ni chapitre ni section.
- « partiellement traitée » : dès que tu ne peux pas nommer cette section, ou qu'elle ne répond qu'à une partie de la demande. Dis alors ce qui manque, et comment le compléter.
- « non traitée » : seulement pour un sujet absent de tout le document, avec la raison et ce qu'il faudrait pour le traiter. Un sujet abordé ailleurs n'est jamais « non traité ».

Dans le doute, le statut est « partiellement traitée » : un « traitée » que le lecteur ne retrouve pas à l'endroit annoncé fait douter de toute l'annexe.

Puis les documents justificatifs et les simulations complémentaires, si le client en a demandé.

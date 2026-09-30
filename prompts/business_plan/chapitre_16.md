<!--
Prompt du chapitre 16 — Prévisionnel financier
Clé : bp.16.previsionnel_financier

Réécrit le 29/09/2026. Ce fichier disait seulement « Ce chapitre est généré en
trois sections distinctes. Ne pas utiliser ce prompt directement. » Or le moteur
structuré — celui qui produit les business plans livrés — ne découpe JAMAIS un
chapitre en sections : il lit ce fichier, et rien d'autre. Le chapitre le plus
chiffré du document partait donc sans consigne. Business plan ÉCLORE (dossier
`cb59cede`, 29/09/2026) : compte de résultat qui ne boucle pas en 2028 et 2029,
résultat net et capacité d'autofinancement confondus, « revenu mensuel »
calculé sur la CAF (diagnostic du 29/09/2026, § 3.1 à 3.3).

La consigne reprend celle des trois sections de l'ancien moteur
(`prompt_library.py`, bp.16.a/b/c), adaptée aux blocs du moteur structuré, et
ajoute ce qui manquait : les identités du compte de résultat écrites en toutes
lettres, la définition du revenu du dirigeant selon le statut, et la règle
« le client fait foi » (décisions D1 et D2 du diagnostic).

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
  {{ renvoi_<clé> }} : « chapitre N « Titre » », lu dans le plan du livrable
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

CHAPITRE {{ numero_chapitre }} — {{ titre_chapitre }}.
Objectif : présenter le prévisionnel financier du projet de façon qu'un banquier puisse refaire chaque calcul à partir des tableaux, sans jamais trouver deux chiffres qui se contredisent.

1. Les chiffres du client font foi.
- Tout montant que le client a déclaré — chiffre d'affaires, charges, dotations, résultat, capacité d'autofinancement, rémunération — se reproduit EXACTEMENT, au centime et à l'année près. Tu ne l'arrondis pas, tu ne le recalcules pas, tu ne le « corriges » pas.
- Une ligne que le client n'a pas donnée se calcule à partir des siennes, selon les identités du point 3, et seulement ainsi.
- Si ses propres lignes ne bouclent pas entre elles, garde ses chiffres, n'invente aucune ligne pour masquer l'écart, et dis une fois, sans le commenter, quelle ligne diffère et de combien.
- Une ligne qu'il a déclarée et que son statut ne prévoit pas (des amortissements en micro-entreprise, par exemple) reste citée comme SA donnée, jamais recalculée autrement.

2. Les hypothèses d'abord, et elles construisent le chiffre d'affaires.
Ouvre le chapitre sur les hypothèses clés : prix, volumes, fréquence, taux de remplissage, charges fixes et charges variables. Le lecteur doit pouvoir vérifier que volume × prix = chiffre d'affaires, année par année. Le chiffre d'affaires s'entend hors taxes.

3. Le compte de résultat, ligne par ligne, sur TOUS les exercices du dossier.
Un bloc `tableau`, une colonne par exercice — au moins trois ; quatre ou cinq si le client les a donnés, sans en retirer aucun. Les lignes, dans cet ordre : chiffre d'affaires, charges variables, marge brute, charges fixes, excédent brut d'exploitation (EBE), dotations aux amortissements, impôts sur le résultat, résultat net, capacité d'autofinancement (CAF).
Les identités que chaque colonne respecte, écrites aussi en toutes lettres sous le tableau, pour que le lecteur les vérifie :
- chiffre d'affaires − charges (variables et fixes) = EBE ;
- EBE − dotations aux amortissements − impôts = résultat net ;
- CAF = résultat net + dotations aux amortissements.
Avant de rendre le tableau, refais chaque soustraction de chaque colonne. Une colonne qui ne boucle pas est une erreur que le lecteur verra en premier.

4. Résultat net et CAF ne se confondent JAMAIS.
Ce sont deux lignes, deux noms, deux valeurs — elles ne sont égales que si les dotations sont nulles. Un montant présenté comme « résultat net » n'est jamais celui de la CAF, et inversement. Tout chiffre repris ailleurs dans le chapitre, ou dans une phrase, porte le nom de SA ligne.

5. Le revenu du dirigeant se définit selon le statut juridique de chaque année.
- En micro-entreprise : chiffre d'affaires − charges réellement décaissées − cotisations sociales. Ce n'est ni le chiffre d'affaires, ni le résultat net, ni la CAF.
- En entreprise individuelle au régime réel : le résultat de l'entreprise, cotisations sociales déduites.
- En société : la rémunération versée au dirigeant, plus les dividendes s'il en est prévu.
Écris la définition retenue dans le chapitre, avec l'année à laquelle elle s'applique. Un revenu mensuel est ce revenu annuel divisé par douze — pose la division, avec la ligne dont elle part.

6. Tout chiffre dérivé se calcule sur les lignes du tableau.
Marge, taux, ratio, écart, évolution, seuil de rentabilité : chacun part des lignes du compte de résultat ci-dessus, et l'opération s'écrit dans la phrase (« 18 000 € d'EBE sur 120 000 € de chiffre d'affaires, soit 15 % »). Le seuil de rentabilité = charges fixes ÷ taux de marge sur coûts variables ; dis ensuite s'il est atteignable avec la capacité du projet (heures, places, points de vente, volume de production).

7. Le scénario central, puis l'analyse de sensibilité.
Le compte de résultat ci-dessus est le scénario central. Ajoute une analyse de sensibilité : un bloc `tableau`, une colonne par exercice, avec trois lignes de chiffre d'affaires et trois lignes de résultat net — scénario central, chiffre d'affaires inférieur de 10 %, chiffre d'affaires inférieur de 20 % —, charges fixes inchangées : une baisse de chiffre d'affaires retire au résultat la marge qu'elle portait (baisse × taux de marge sur coûts variables). Si la mémoire de l'étude fournit ces montants, cite leurs repères, sans recalcul. Dis ensuite quel exercice devient déficitaire, et à partir de quelle baisse. Ce scénario se construit toujours à partir des lignes du tableau : n'écris jamais qu'il ne peut pas l'être, ni qu'il attend un arbitrage.

8. La trésorerie.
Un bloc `tableau` de trésorerie de la première année, mois par mois — encaissements, décaissements, solde cumulé — construit sur les mêmes hypothèses, avec son point bas nommé et ce qui le couvre (apport, trésorerie de sécurité). Aucun bilan inventé : un bilan ne se présente que si le client en a fourni les postes.

9. Une figure, prise dans la liste des figures réalisables : l'évolution du chiffre d'affaires d'un exercice à l'autre, si elle y figure.

Cohérence à vérifier : les investissements et leur financement sont ceux du {{ renvoi_investissements }} et du {{ renvoi_plan_financement }} ; le statut et le régime fiscal de chaque année sont ceux du {{ renvoi_structure_juridique }}. Les charges de personnel et la rémunération du dirigeant que ce chapitre pose sont celles que le {{ renvoi_remuneration }} reprendra à l'identique. En cas d'écart avec le dossier du client, ce sont ses chiffres qui font foi.

Conclus par un paragraphe de viabilité : ce que le prévisionnel démontre, à quelles conditions, et le point de vigilance principal.

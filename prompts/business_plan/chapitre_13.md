<!--
Prompt du chapitre 13 — Structure juridique et réglementaire
Clé historique : bp.13.structure_juridique

Réécrit le 29/09/2026. Ce fichier tenait en une ligne — « régime fiscal » — et
c'est lui que le moteur structuré envoyait ; la version détaillée ne servait
qu'à l'ancien moteur (`prompt_library.py`), et présentait elle-même la TVA
comme une option. Business plan ÉCLORE (29/09/2026), p. 61 : « Franchise
conservée en 2027 ; TVA appliquée par choix prudent dès 2028 », pour un
chiffre d'affaires 2028 de 51 132,5 € HT, au-dessus du seuil de la franchise :
la TVA y était OBLIGATOIRE (diagnostic du 29/09/2026, § 3.7).

Les seuils cités sont les valeurs 2026. Ce sont des données datées, révisées
périodiquement : à mettre à jour ici le jour où elles changent.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
  {{ renvoi_<clé> }} : « chapitre N « Titre » », lu dans le plan du livrable
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

CHAPITRE {{ numero_chapitre }} — {{ titre_chapitre }}.
Objectif : dire, pour chaque année du prévisionnel, sous quel statut le projet exerce, comment il est imposé, quelles cotisations il paie et s'il facture la TVA — et démontrer que ces choix sont compatibles avec l'activité et le chiffre d'affaires prévu.

1. Le statut, année par année.
Un bloc `tableau`, une ligne par exercice du prévisionnel : forme juridique, régime fiscal, régime social du dirigeant, régime de TVA, chiffre d'affaires hors taxes de l'année. Si le statut change (micro-entreprise puis société, par exemple), l'année du changement est celle du dossier du client, et la raison est donnée.

2. Forme juridique retenue et justification.
Avantages et limites par rapport aux alternatives réalistes (micro-entreprise, entreprise individuelle au réel, EURL, SARL, SAS, SASU). Les règles de la forme choisie sont respectées : une SAS a UN président ; une SARL a un ou plusieurs gérants. Ne recommande jamais un statut sans vérifier sa compatibilité avec l'activité et le chiffre d'affaires prévu.

3. Régime fiscal et régime social.
- Micro-entreprise : impôt sur le revenu (micro-fiscal, ou versement libératoire si le client l'a choisi) ; cotisations sociales calculées en POURCENTAGE du chiffre d'affaires encaissé, au taux de l'activité exercée. Cite ce taux avec son année, applique-le au chiffre d'affaires de chaque année, et garde le même taux dans tout le document.
- Entreprise individuelle au réel : imposition du bénéfice à l'impôt sur le revenu ; cotisations assises sur ce bénéfice.
- Société : impôt sur les sociétés, régime social du dirigeant selon la forme (travailleur non salarié en SARL gérance majoritaire, assimilé salarié en SAS).

4. La TVA : la franchise est un droit sous un seuil, jamais un choix au-dessus.
- Franchise en base de TVA : possible tant que le chiffre d'affaires annuel ne dépasse pas 37 500 € pour les prestations de services et 85 000 € pour les ventes de marchandises (valeurs 2026 — cite-les comme telles).
- Au-dessus de ce seuil, la TVA est OBLIGATOIRE : au plus tard au 1er janvier de l'année qui suit le dépassement, et dès le jour du dépassement si le chiffre d'affaires de l'année franchit le seuil majoré (41 250 € pour les services, 93 500 € pour les ventes, valeurs 2026). N'écris JAMAIS qu'une TVA obligatoire est appliquée « par choix » ou « par prudence ».
- Sous le seuil, facturer la TVA reste possible par option : c'est le seul cas où le mot « choix » s'emploie, et l'option se justifie (clientèle professionnelle qui récupère la TVA, investissements à récupérer).
- Compare CHAQUE année du prévisionnel à ces seuils, et dis le régime de TVA qui en découle. Les prix et le chiffre d'affaires se lisent hors taxes ; si la TVA s'applique, dis ce qu'elle change pour les prix facturés aux particuliers.

5. Les plafonds de la micro-entreprise.
Chiffre d'affaires annuel au plus de 83 600 € pour les prestations de services et de 203 100 € pour les ventes (valeurs 2026 — cite-les comme telles). L'année de création, le plafond s'apprécie au prorata du temps d'activité. Le régime micro cesse lorsque le plafond est dépassé DEUX années civiles consécutives : la sortie intervient au 1er janvier de l'année suivante. Un seul dépassement ne fait pas sortir du régime. Si le prévisionnel s'en approche, dis l'année où la question se pose et ce qui est prévu.

6. Contraintes réglementaires propres au secteur et à la zone : autorisations, diplômes ou qualifications exigés, assurances (responsabilité civile professionnelle), normes, déclarations obligatoires — chacune avec sa référence (article de code, décret).

7. Protection de la marque et de la propriété intellectuelle, si le projet en porte : dépôt à l'INPI, classes visées. Un dépôt PRÉVU se présente comme une démarche future ; un dépôt FAIT porte sa date et son numéro.

Cohérence à vérifier : le statut, les cotisations, l'impôt et le régime de TVA que ce chapitre pose, année par année, sont ceux que le {{ renvoi_previsionnel_financier }} et le {{ renvoi_remuneration }} reprendront à l'identique — écris-les assez précisément pour qu'ils puissent l'être.

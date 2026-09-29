# Diagnostic — pourquoi le contrôleur laisse passer les erreurs (29/09/2026)

Étape 0 du chantier « mémoire de l'étude + boucle chapitre par chapitre ».
**Aucun code n'a été modifié pour ce diagnostic.** Il repose sur :

- la lecture du code au commit `c638e35` (références `fichier:ligne` ; le nom de
  fonction cité à côté reste le repère fiable si les lignes bougent) ;
- le business plan ÉCLORE réellement livré le 29/09/2026 (dossier `cb59cede`,
  107 pages, Word + PDF), **lu sans être régénéré ni modifié** — copie locale hors
  dépôt : c'est le document confidentiel d'une cliente, il n'a pas sa place dans
  un dépôt poussé sur GitHub (voir § 8, décision D7) ;
- le brief de la cliente et les mesures de la console (`jobs/<id>/brief/`,
  `jobs/<id>/mesure/`), en lecture.

Le PDF est bien sorti du **moteur structuré** (socle + chapitres JSON + chaîne
Word) : producteur LibreOffice, annexe « Donnée | Valeur | Année | Origine »
construite depuis le socle. C'est ce moteur qui est analysé.

---

## 0. En une page

1. **Il n'y a pas un « agent contrôleur global » mais trois dispositifs**, et aucun
   ne voit le document tel que le client le lit :
   - le **gate** (`generation/gate.py`, ~30 contrôles en code) lit le *markdown*
     dérivé des chapitres, sans le chapitre 0 ni l'annexe, jamais le Word ; il rend
     son verdict **après l'envoi** (`generation/tasks.py:479-480`) ;
   - la **relecture finale** (`generation/controle_final.py`) assemble le Word
     (sans PDF), le vérifie en code, puis fait réécrire les chapitres fautifs par le
     modèle — **une seule passe de correction utile** en pratique
     (`MAX_PASSES=2`, arrêt à `passe == max_passes`, `:78`, `:380-382`) ;
   - les **CHECK de blocs** (modèle) : pour un business plan, seulement le
     CHECK INITIAL sur le chapitre 0.
2. **Aucun modèle financier n'existe.** Le socle porte 37 données ; tout le reste —
   charges, CAF, revenu mensuel, parts, écarts, tableaux entiers — est écrit
   librement par le modèle, chapitre par chapitre. Sur le PDF ÉCLORE, **62 % des
   1 055 nombres ne viennent pas des données de référence** (§ 2).
3. **Le défaut le plus coûteux est en amont du modèle :** l'extracteur du brief a
   **fusionné le résultat net et la CAF** en un seul fait client
   (« 50 € / 8 040 € / 23 224 € / 662 € / 8 652 € / 23 836 € »), puis ce fait
   fusionné a été imposé à chaque chapitre comme « source unique ». Les deux valeurs
   2029 (23 223,86 et 23 835,86) sont donc toutes deux « conformes » pour le gate.
4. **Les contrôles ne regardent que des nombres monétaires, et mal :** années
   civiles invisibles (« 2029 » n'est pas une année pour eux), tolérance zéro sur un
   arrondi mais fourchette [min ; max] sur une trajectoire, phrases exemptées dès
   qu'elles citent un chiffre du brief. Rien ne compare dates, statuts, comptes
   d'acteurs, définitions d'indicateurs, renvois, statuts d'annexe, langue.
5. **Le rendu n'est contrôlé que sur le XML du Word** : ni en-têtes, ni pages, ni
   images, ni PDF. Plusieurs défauts visibles naissent dans **notre code** et non
   chez le modèle (codes d'unité bruts dans l'annexe, axes 0/1/2, en-tête et
   métadonnées tirés de la raison sociale, 4ᵉ de couverture quasi vide).
6. **Presque tout finit en incident, rien ne corrige jusqu'au bout.** C'est conforme
   à la décision cliente du 13/08/2026 (« l'envoi doit être auto ») — et c'est
   exactement la brèche : on détecte (parfois), on ne répare pas (souvent).

---

## 1. Le pipeline réel, étape par étape

Le client voit 4 étapes (`organisations/suivi.py:112` `etapes`) : données de
référence, chapitres, vérification, mise en forme. Le suivi est rafraîchi par
**interrogation périodique** (`refetchInterval`, `frontend/src/espace/pages/SuiviLivrable.tsx:197`) ;
il n'existe ni SSE ni websocket dans le dépôt. Il affiche aujourd'hui un état
« échec » quand un dossier tombe (`suivi.py:~160`).

Derrière ces 4 étapes, il y en a dix :

| # | Étape | Point d'entrée | Reçoit → produit | Modèle ou code |
|---|---|---|---|---|
| 1 | Brief (espace client) | `organisations/commandes.py:223` `creer_commande` | saisie → variables brutes (29 pour ÉCLORE) | code |
| 2 | Faits client | `generation/coherence.py:442` `seed_locked_facts_from_variables`, via `intake/financials.py` | variables → 9 `CoherenceFact` « CLIENT » verrouillés (ni CAF, ni charges) | code (regex) |
| 3 | Recherche web | `generation/research.py:421` | → `job.research_brief` (texte) | API de recherche |
| 4 | Documents du client | `generation/documents_client.py:922` | PDF/docx/xlsx → texte brut, **240 000 signes au total** (les 3 documents d'ÉCLORE : « lus en partie ») | code |
| 5 | Socle (« données de référence ») | `generation/socle/services.py:142` `etablir_socle` → `builder.produire_socle` | brief + documents + recherche → **37 données** (BP), 11 concurrents, grille, tendances, risques | modèle (appel d'outil) + validation code |
| 6 | Chapitres | boucle `generation/runner.py:537-657` → `chapitres/runner.py:1799` `generer_chapitre` | voir ci-dessous → `payload` JSON (paragraphes, tableaux, chiffres-clés, figures par identifiants) + markdown dérivé | modèle |
| 6b | CHECK de blocs | `runner.py:1065` | BP : CHECK INITIAL sur le chapitre 0 (étude de marché : blocs A à J) | modèle |
| 7 | QA après génération | `generation/qa.py:893` `run_qa_pass` | réécrit le **markdown** seulement, jamais le `payload` rendu en Word (`qa.py:1019-1021`) | code + modèle |
| 8 | Relecture finale | `tasks.py:440` → `controle_final.py:284` | Word assemblé (sans PDF) → `verifier_livrable` + gate → chapitres fautifs réécrits | code (détection) + modèle (réécriture) |
| 9 | Assemblage et rendu | `documents/livrable_word.py:228` → `rendu_word/*` → LibreOffice (`integrations/docx_pdf.py:110`) | payloads + socle → Word → PDF ; annexe « D'où viennent les chiffres » | code |
| 10 | Livraison | `tasks.py:501` → `delivery/services.py:723` | seul `integrite` retient (`:78`) ; tout le reste part avec un incident HIGH | code |

**Ce que reçoit un rédacteur de chapitre** (`chapitres/runner.py:1619-1720`) : le
socle, le brief **en JSON brut**, le texte des documents, le catalogue de figures,
les **résumés des chapitres précédents seulement** (150-250 mots chacun), le
`REGISTRE_CHIFFRES` (les faits client — dont le fait fusionné), et l'instruction
`prompts/<livrable>/chapitre_NN.md`. Il ne reçoit **ni le plan des chapitres
suivants, ni registre de décisions, ni définitions d'indicateurs**. Les chapitres
sont écrits **un par un, dans l'ordre** ; ce qui manque n'est pas l'ordre, c'est une
mémoire structurée et un contrôle à chaque chapitre.

**Deux consignes centrales manquent en moteur structuré :**
- `prompts/business_plan/chapitre_16.md:20` (le prévisionnel) dit seulement « Ce
  chapitre est généré en trois sections distinctes. Ne pas utiliser ce prompt
  directement. » La vraie consigne du compte de résultat n'existe que dans
  `prompt_library.py:1763-1775`, lu par le seul moteur hérité ;
- la règle « CHRONOLOGIE UNIQUE » (`prompts.py:103-111`) n'est envoyée qu'au moteur
  hérité.

---

## 2. Combien de chiffres du PDF ÉCLORE ne viennent pas des données de référence

**Méthode** (script de lecture seule, hors dépôt) : extraction de tous les nombres
du Word livré, dans l'ordre (paragraphes et tableaux), **hors** annexe du socle,
années (1990-2040 sans unité), numéros de chapitre/section/page et petits entiers
0-10 sans unité (« 3 formats »). Un nombre « vient » d'une référence s'il égale une
de ses valeurs à l'arrondi près (0,5 % ou 0,5 unité ; même famille : %, €, compte).
Les 37 données de référence sont lues dans l'annexe du document elle-même.

| | Occurrences | Part |
|---|---:|---:|
| Nombres dans le texte | **1 055** | 100 % |
| … égaux à une des 37 données de référence | 402 | 38 % |
| … **hors données de référence** | **653** | **62 %** |
| &nbsp;&nbsp;dont retrouvés dans le brief de la cliente | 541 | 51 % |
| &nbsp;&nbsp;dont **ni dans le socle ni dans le brief** | **112** (64 valeurs distinctes) | 11 % |

Les 112 : 76 dans des tableaux, 36 en prose ; 59 montants, 37 pourcentages. Les plus
fréquents : « 700 € » (7), « 0,2 % » (6), « 83 600 € » (5, plafond micro recopié),
« 0,00032 % » (4), « 26 280,5 € » (3), « +290,6 % » (2), « 8 576,08 € »…
Ce sont des dérivés **calculés par le modèle** (écarts, parts, ratios, taux de
capture) ou recopiés de ses documents joints.

Pour comparaison, l'outil existant (`jobs/<id>/mesure/`) ne compte que **2**
« chiffres hors socle » : il accepte tout nombre présent dans le socle, le brief
**ou les documents joints** — et le prévisionnel joint de la cliente contient
presque tout. Un nombre recopié n'est pas pour autant cohérent : c'est l'angle
mort (§ 3, classe 1).

Limites : la correspondance au brief est large (le brief ÉCLORE contient des
centaines de nombres) ; les 541 « du brief » sont un plafond, pas une preuve
d'exactitude.

---

## 3. Erreur par erreur : où elle naît, pourquoi rien ne l'a vue

Les pages citées sont celles du PDF livré (107 pages).

### 3.1 Résultat net 2029 : 23 223,86 € (16 pages) ou 23 835,86 € (10 pages)

- **Naissance — extraction du brief.** La réponse « Tableaux financiers » est
  aplatie sur une ligne : « … Dotations aux amortissements 612 € … Résultat net
  comptable 50 € 8 040 € 23 224 € … **Capacité d'autofinancement** 662 € 8 6… ».
  `intake/financials.py:246-285` (`_values_after_every_label`) prend les montants qui
  suivent le libellé jusqu'à une frontière ; `_LIBELLES_FRONTIERE` (`:182-197`) ne
  contient ni « CAF », ni « capacité d'autofinancement », ni « dotations ». Les deux
  séries fusionnent en **un** fait `resultat_net_previsionnel` (l'écart de 612 € est
  constant : c'est la dotation). 23 835,86 est la CAF 2029.
- **Propagation.** Ce fait est donné à chaque chapitre comme « REGISTRE_CHIFFRES …
  source unique … reprendre EXACTEMENT » (`chapitres/runner.py:1675-1684`).
- **Pourquoi le gate ne l'a pas vu** (`gate.py:998-1056`, `_mention_est_conforme`) :
  sans année reconnue, une trajectoire accepte tout ce qui tombe dans [min ; max] —
  avec la borne haute fusionnée à 23 836, **les deux valeurs passent** ;
  `_YEAR_IN_MENTION_RE` (`:947`) ne connaît que « an N / année N », pas « 2029 » ;
  une ligne de tableau « | Résultat net | … | » n'est pas lue ; toute phrase qui cite
  aussi un chiffre du brief est exemptée (`_est_un_scenario`, `:967-985`). À
  l'inverse, l'égalité stricte (`:1028`) signale **à tort** 49,96 € face à « 50 € »
  (6 faux positifs sur ce dossier, qui ont renvoyé les chapitres 2, 11 et 19 en
  réécriture — parmi d'autres motifs).
- **Pourquoi le contrôle inter-chapitres ne l'a pas vu** (`checks_evangeline.py:771-921`) :
  une mention sans « an N / année N / exercice N » est écartée ; « 2029 » n'est pas
  reconnu (`_ANNEE_RE`, `:497-507`) ; dans un tableau, seul le premier montant est lu.
- **Le commentaire qui promettait le contraire** (`gate.py:210-212`, « verrouillé à sa
  première mention ») est faux en moteur structuré : les extracteurs de faits ne
  tournent que dans le moteur hérité (`runner.py:1002-1015`).

### 3.2 « Revenu mensuel » = résultat net ÷ 12, mais calculé sur la CAF

- p. 52 : « Résultat net de 23 223,86 €, revenu mensuel de 1 986,32 € » —
  1 986,32 = 23 835,86 ÷ 12 (CAF).
- **Naissance** : calcul du modèle, sur la série fusionnée ; aucune donnée
  « revenu du dirigeant » ni définition d'indicateur dans le socle.
- **Rien ne l'a vu** : aucun contrôle ne vérifie une définition ; la division
  annuel → mensuel n'est pas dans `_PERIODES` (`arithmetique.py:130-136`) ;
  « revenu » n'est pas un libellé surveillé (`checks_evangeline.py:449-469`). Même un
  calcul vérifié ne dirait pas si l'opérande est le résultat net ou la CAF.

### 3.3 Compte de résultat qui ne boucle pas en 2028 et 2029

- **Naissance** : tableau écrit librement par le modèle, sous une consigne vide
  (`chapitre_16.md:20`). Les lignes intermédiaires sont inventées.
- **Rien ne l'a vu** : aucun modèle ni identité de compte de résultat
  (`socle/calculs.py:115-147` : 3 identités sans rapport) ; `totaux_faux`
  (`arithmetique.py:671-776`) n'additionne une colonne que si la dernière ligne
  commence par « Total / Cumul / Ensemble » et ne refait jamais une soustraction ;
  `verifier_tresorerie_reconstituable` (`strategies/bp.py:258-298`) se tait dès que
  le mot « CAF » apparaît.

### 3.4 Coût fixe faux dans un tableau de rentabilité (150 € contre 290 €)

- **Naissance** : deux tableaux écrits par le modèle, l'hypothèse dans l'un, le
  résultat dans l'autre.
- **Rien ne l'a vu** : `valider_chapitre` ne vérifie que les identifiants
  (`modele/conformite.py:274-277` le dit explicitement) ; aucune dépendance entre
  tableaux n'est modélisée ; « charges fixes » n'est pas surveillé.

### 3.5 Cinq dates différentes pour le départ du poste salarié

- Le brief dit « 2029, à temps plein, après avoir quitté son poste ». Relevé dans le
  document : « courant 2029 » (p. 52), « fin 2029 » (p. 62), « 2029 … Carine quitte
  son poste » (p. 51), et une chronologie p. 87 dont le tableau aplati ne permet pas
  de dire sans ambiguïté à quelle année le départ est rattaché. Les cinq formes
  signalées ne sont pas toutes retrouvées par extraction de texte ; la cause est la
  même pour toutes.
- **Naissance** : aucun registre de dates ou d'événements ; le socle BP ne contient
  que des chiffres (`socle/referentiel.py:414+`) ; la règle « CHRONOLOGIE UNIQUE »
  n'est envoyée qu'au moteur hérité. Chaque chapitre reformule depuis le brief et
  les résumés.
- **Rien ne l'a vu** : aucun contrôle ne compare des dates ou des événements.

### 3.6 Nombre de concurrents qui change (11, 13)

- « 11 concurrents » (p. 11, 28, 31, 100, 101), « 13 acteurs analysés » (p. 6) — ce
  dernier vient de l'**étude de concurrence jointe par la cliente** (13 acteurs),
  pas de notre base (8 directs + 3 indirects).
- **Naissance** : deux vérités données au rédacteur (socle et documents), sans règle
  de priorité ; le prompt du chapitre 7 dit « 8 + 3 **maximum** » quand le bloc du
  socle dit « ni plus ni moins » (`chapitre_07.md:14` contre `runner.py:736-741`).
- **Rien ne l'a vu** : le contrôle de comptage n'existe que pour l'étude
  concurrentielle (`checks_evangeline.py:1085-1122`) et ne compte que des puces.

### 3.7 TVA présentée comme un choix alors qu'elle est obligatoire

- p. 61 : « Franchise conservée en 2027 (24 852 € HT) ; **TVA appliquée par choix
  prudent dès 2028** » — le CA 2028 (51 132,5 € HT) dépasse le seuil de franchise
  (37 500 € pour des services) : la TVA est obligatoire.
- **Naissance** : le prompt du chapitre 13 réellement envoyé tient en une ligne,
  « régime fiscal » (`prompts/business_plan/chapitre_13.md:14`) ; la version riche,
  qui cite la TVA et la franchise, ne sert qu'au moteur hérité
  (`prompt_library.py:1698-1720`) — et la présente elle aussi comme une option.
- **Rien ne l'a vu** : aucune règle métier codée sur la TVA, la franchise, la
  micro-entreprise ou le statut (`strategies/bp.py` : IS, rémunération, trésorerie
  seulement ; `gate.py:1665-1667` l'annonce comme « bientôt »).

### 3.8 Un « taux » exprimé en euros

- p. ex. « taux de capture de 0,0485 € par femme » (ch. 10), signalé seulement pour
  ses 4 décimales (`montant_non_arrondi`).
- **Naissance** : prose du modèle ; les familles d'unités (`FamilleUnite`,
  `referentiel.py:66-77`) ne sont vérifiées **qu'à la validation du socle**
  (`socle/schema.py:786-802`), jamais dans les chapitres.
- **Rien ne l'a vu** : aucun contrôle « un taux s'exprime en % ».

### 3.9 Renvois vers des chapitres inexistants

- **Naissance** : le rédacteur ne connaît que les chapitres **précédents** ; tout
  renvoi vers l'avant est deviné. Des prompts citent des numéros en dur
  (`chapitre_18.md:29,33,40`, `chapitre_14.md:30-32`) ; `_bloc_sources` renvoie à
  « la bibliographie du chapitre 21 » pour **tous** les livrables
  (`chapitres/runner.py:943-944`), faux pour la stratégie et l'étude
  concurrentielle ; l'annexe des chiffres est ajoutée comme chapitre N+1
  (`rendu_word/assemblage.py:689-699`) sans qu'aucun prompt la connaisse.
- **Rien ne l'a vu** : aucun contrôle de renvoi orphelin.

### 3.10 Annexe qui déclare « traité » ce qui ne l'est pas

- **Naissance** : le chapitre 20 **déclare** les statuts (`chapitre_20.md:14`), à
  partir des seuls résumés, et `REGLES_DE_FOND` pousse vers « traitée »
  (`chapitres/runner.py:1201-1206`).
- **Rien ne l'a vu** : `demande_contredite` (`checks_post_rendu.py:1054-1335`) ne
  contrôle qu'un sens (« non traité » alors que traité ailleurs) ; un « traité »
  faux n'est jamais contrôlé ; le contrôle de couverture par le modèle
  (`couverture.py:289-383`) n'est pas confronté à l'annexe et ne corrige rien.

### 3.11 Graphique dupliqué

- **Naissance** : `_blocs_graphique` (`rendu_word/assemblage.py:285-400`) ne garde
  aucune mémoire des figures déjà dessinées ; plusieurs résolveurs ignorent les
  identifiants demandés et rendent la même image (frise, cartes en mode risques,
  radar sans sélecteur) ; la passe de complétion jusqu'à 17 figures
  (`PLANCHER_FIGURES`, `prompts.py:192`) redessine des identifiants déjà tracés.
- **Rien ne l'a vu** : la vérification du fichier ne fait que **compter** les images
  (`verification/lecture.py:260-263`).

### 3.12 Rétroplanning hors sujet

- **Naissance** : le résolveur de la frise (`donnees_graphiques.py:928-939`) ignore
  les identifiants et dessine `socle.tendances` (tendances de marché) ; le catalogue
  la présente comme « plan par horizons » (`graphiques.py:789-791`), ce qui invite à
  s'en servir pour un planning. Il n'existe aucune donnée « calendrier » à dessiner.
- **Rien ne l'a vu** : aucun contrôle ne confronte le titre à la matière dessinée.

### 3.13 Axes 0/1/2 au lieu des années

- **Naissance — notre code** : `_figure` pose un formateur de nombres sur les deux
  axes (`rendu_word/graphiques.py:119-121`) ; matplotlib n'installe alors pas le
  formateur de catégories, et les années (texte) s'affichent par leur rang. Vrai pour
  courbes, aires et barres empilées ; les barres simples y échappent grâce à
  `set_xticklabels`.
- **Rien ne l'a vu** : le test des graduations ne lit que l'axe des ordonnées
  (`test_les_graduations_des_axes_sont_francaises.py:31`) ; aucune lecture d'image.

### 3.14 Tableaux tronqués

- **Naissance — notre code** : coupe dure à 110 signes, sans points de suspension,
  dans le tableau de repli (`assemblage.py:264`) et l'annexe
  (`annexe_chiffres.py:93`) ; colonnes à largeur fixe bornées à 7 % de la page
  (`composants.py:488-537`) ; polices du Word absentes de l'image Docker, donc
  coupures différentes dans le PDF (`Dockerfile:34-45`).
- **Rien ne l'a vu** : la vérification lit le texte du XML, où il est entier.

### 3.15 Page vide

- **Naissance — notre code** : la dernière page (107) est la 4ᵉ de couverture
  (`composants.py:337-366` : saut de page, 12 paragraphes vides, mentions) ; pour un
  business plan, `mention_legale` n'est jamais fournie (`services.py:88-100`) : il
  reste deux lignes sous l'en-tête — la page se lit vide. Un paragraphe vide après le
  dernier tableau de l'annexe peut en outre produire une vraie page blanche.
- **Rien ne l'a vu** : le PDF n'est jamais lu page par page ; la limite de 80 pages
  (`documents/services.py:49-78`) n'est appliquée que par l'ancienne chaîne HTML —
  **un BP de 107 pages n'est jamais comparé à sa limite**.

### 3.16 Fautes et mots anglais (« already », « se accroît »)

- p. 67 « already financé », p. 7 « se accroît », p. 103 et 106 « unite »,
  « MEUR », « EUR ».
- **Naissance** : « already » et « se accroît » : modèle. **« unite », « MEUR »,
  « EUR » : notre code** — `annexe_chiffres._valeur` (`rendu_word/annexe_chiffres.py:76-79`)
  imprime le code d'unité brut, alors que `unite_lisible` existe et a été appliqué
  au tableau de repli le 26/09 (règle 4 non tenue). Le catalogue de figures écrit
  « (en MEUR) » dans les prompts (`catalogue_figures.py:108-112`), ce qui invite à le
  recopier.
- **Rien ne l'a vu** : aucun outil d'orthographe ; la table d'anglicismes
  (`rendering.py:46+`) est une liste fermée appliquée au markdown seulement ;
  `_VOCABULAIRE_INTERNE` ne connaît que 5 verbes anglais d'instruction ; le gate ne
  voit pas l'annexe.

### Et deux défauts visibles qui n'étaient pas dans la liste

- **En-tête et auteur du PDF** : tous deux prennent la raison sociale saisie dans
  « Ma marque » — ici la phrase entière « ÉCLORE (nom de projet provisoire), avec pour
  signature « … » », sur 105 pages (`rendu_word/gabarit.py:240-243`,
  `depuis_json.py:393-414`). Le nom du porteur est collecté (`PORTEUR_PROJET`) mais
  jamais lu par le rendu.
- **Libellés « données du projet »** (73 pages) : imposés par le prompt comme source,
  imprimés seuls en italique sous chaque tableau (`composants.py:728-732`) et
  exemptés par le contrôle post-rendu (`checks_post_rendu.py:186-197`).

---

## 4. Pourquoi « le contrôleur » laisse passer — les causes structurelles

1. **Il juge après coup, sans référence complète.** Il n'existe pas de modèle des
   chiffres dérivés : le contrôle ne peut que comparer des mentions à 37 données et à
   un brief lu par expressions régulières. Tout ce qui n'y est pas est « libre ».
2. **Il ne lit pas ce que lit le client.** Le gate lit le markdown (qui peut même
   diverger du Word : la QA réécrit l'un et pas l'autre, `qa.py:1019-1021`) ; la
   relecture lit le XML du Word ; personne ne lit les en-têtes, les images, les
   pages, le PDF.
3. **Il ne voit que des montants, et ses règles de lecture sont trouées** : années
   civiles non reconnues, libellés surveillés limités, tableaux lus en première
   cellule, exemptions larges, tolérances incohérentes (zéro sur un arrondi,
   [min ; max] sur une trajectoire).
4. **Il ne corrige pas jusqu'au bout.** Une passe de réécriture de chapitre entier
   (au plus 8 chapitres), sur consigne textuelle, puis envoi. Les problèmes « du
   chapitre 0 » sont envoyés au chapitre 1 (`correction.py:321`). Beaucoup de
   contrôles ne sont pas réparables du tout (liste `correction.py:64-122`).
5. **Il arrive trop tard.** Une erreur du chapitre 1 est recopiée par les 20
   suivants avant que quiconque ne la voie.
6. **Des contrôles sont morts ou aveugles** (§ 5) : on les croit actifs.

---

## 5. Contrôles morts ou aveugles (à réparer quoi qu'il arrive)

1. `_controler_equilibre_financier`, règle 4 (clientèle × panier ≈ CA) : ne se
   déclenche jamais (effectif en « unite » → `valeur_en_unites_de_base` rend None).
2. `arithmetique_marche` et l'export `fact_store` : lisent des faits écrits
   seulement par le moteur hérité → toujours vides en moteur structuré.
3. Années civiles invisibles (`_ANNEE_RE`, `_YEAR_IN_MENTION_RE`).
4. `_PERIODES` sans passage année → mois.
5. `verifier_tresorerie_reconstituable` : se contente de la présence d'un mot.
6. Limite de pages jamais appliquée à la chaîne Word.
7. `run_qa_pass` réécrit un markdown que le Word ne rend pas.
8. Commentaires qui décrivent l'inverse du code : `gate.py:3-7` (« le document ne
   part pas »), `gate.py:2011` (« quatre checks bloquants »), `gate.py:210-212`.

---

## 6. Ce qui est réutilisable

| Existant | Où | Rôle dans la cible |
|---|---|---|
| **Socle** (37 données verrouillées, identifiants, familles d'unités, filiations `derivee_de`, fiabilité, sources) | `generation/socle/*`, modèle `SocleDonnees` (JSON en base) | **noyau de `faits`** de la mémoire ; le mécanisme « référence par identifiant » existe déjà |
| **Figures par identifiants** (le modèle ne donne pas de valeurs, le code résout depuis le socle) | `rendu_word/donnees_graphiques.py` | modèle exact des **placeholders** à étendre à la prose et aux tableaux |
| `unite_lisible`, `montant_lisible` (format français) | `socle/schema.py` | **formatage unique** au rendu des placeholders |
| `calculs.appliquer` (identités) | `socle/calculs.py` | point d'entrée du **module de calcul** (à étendre en modèle financier) |
| Registre `CoherenceFact` + extracteurs du brief | `coherence.py`, `intake/financials.py` | faits « déclarés » ; l'extracteur est à corriger (frontières) |
| Résumés de chapitres (`payload.resume`) | `chapitres/services.py:134` | section **`chapitres`** de la mémoire |
| Arithmétique des phrases (`arithmetique.verifier`, `totaux_faux`) | `generation/arithmetique.py` | contrôles « phrase de calcul » et « tableau recalculé » |
| ~30 contrôles du gate, contrôles du Word | `gate.py`, `verification/controles.py`, `checks_post_rendu.py` | à **déplacer au niveau du chapitre** et à rendre réparables |
| Boucle de reprises d'un chapitre | `chapitres/services.py:328` `produire_avec_reprises` | base des niveaux 2 (régénération ciblée) |
| Tableau de repli d'une figure | `assemblage.py:255-282` | repli « graphique → tableau » (niveau 3) |
| Relance d'un dossier (ne réécrit que les chapitres en échec) | `services.relaunch_generation_job` | **reprise après redémarrage** |
| Extraction de texte PDF (pypdf) | `delivery/gamma_fidelite.py:69-84` | contrôle post-rendu du PDF |
| `fact_store` (faits de marché entre études, par secteur/pays) | `generation/fact_store.py` | mémoire **inter-études**, distincte de la mémoire d'une étude ; aujourd'hui inerte en moteur structuré |
| Étapes du suivi client | `organisations/suivi.py:112` | à remplacer par la liste dynamique des chapitres |

Il n'existe pas un « JSON de mémoire » unique : la mémoire d'une étude est
dispersée entre `SocleDonnees`, `CoherenceFact`, les `payload` des chapitres et
`job.controle_final`. **La cible `memoire_etude` doit les réunir**, en gardant le
socle comme noyau (il a déjà les identifiants, les unités et les sources).

---

## 7. Écarts entre la cible et l'existant — ce que la cible implique vraiment

1. **Le module de calcul a besoin d'hypothèses structurées.** Les chiffres d'ÉCLORE
   viennent du prévisionnel **de la cliente** (sa réponse « Tableaux financiers » et
   son PDF joint). Pour tout recalculer en code, il faut d'abord en extraire les
   hypothèses (prix par format, sessions, remplissage, charges ligne par ligne,
   statut par année) — c'est une passe d'extraction par le modèle, validée en code,
   comme le socle aujourd'hui.
2. **Le prévisionnel de la cliente peut lui-même ne pas boucler.** Si notre calcul
   diverge de ses tableaux, lequel fait foi dans le document ? (décision D1).
3. **Les définitions dépendent du statut, et le client peut s'en écarter** : ÉCLORE
   est en micro-entreprise mais son propre tableau porte 612 € de dotations aux
   amortissements (décision D2).
4. **Les règles métier sont datées** (seuils de franchise, plafonds micro, taux de
   cotisations) : ce sont des données versionnées avec leur source, pas des
   constantes (le 21,2 % / 21,3 % en est l'illustration).
5. **« Jamais d'arrêt » impose des replis là où le système s'arrête aujourd'hui** :
   socle refusé sur une donnée obligatoire, CHECK INITIAL bloquant avant le
   chapitre 1, solde insuffisant.
6. **LanguageTool** : l'image Docker n'a pas de Java ; l'API publique enverrait le
   texte des clients à un tiers (décision D4).
7. **Temps réel** : l'existant est l'interrogation périodique ; il n'y a ni SSE ni
   websocket (décision D5).
8. **Coût et durée** : un contrôle LLM par chapitre + corrections ciblées ajoute des
   appels. Ordre de grandeur à mesurer en phase 3 sur la doublure puis sur une
   génération réelle autorisée (ÉCLORE a coûté 5,98 € et 31 min pour 22 chapitres).
9. **Études existantes intactes** : le nouveau pipeline doit être choisi **à la
   création** du dossier (drapeau par dossier). Un dossier ancien relancé garde
   l'ancien pipeline ; aucune migration ne touche aux chapitres, aux documents ni aux
   rapports existants.

---

## 7 bis. Nombre de chapitres par type : trois vérités qui ne s'accordent pas

| Type | Carte « Que souhaitez-vous produire ? » | Plan du générateur (`generation/blueprints.py`) | Sommaire du document livré |
|---|---:|---:|---:|
| Étude de marché | 22 | 23 entrées (0 à 22) | 23 attendus (1 à 22 + annexe des chiffres) |
| Étude de la concurrence | 9 | 10 entrées (0 à 9) | 10 attendus |
| Business plan | 21 | 22 entrées (0 à 21) | **22 constatés sur ÉCLORE** |
| Stratégie d'entreprise | 20 | 21 entrées (0 à 20) | 21 attendus |

**Trois sources, sans lien entre elles :**
- la carte : `frontend/src/public/contenu.ts:246-310` (`ETUDES[…].chapitres`), écrite à
  la main « tel qu'il figure sur evkha.fr » ; aussi « 22 chapitres » en dur dans
  `contenu.ts:46`, `:115` et `Boutique.tsx:141-148`, pour toutes les études ;
- le plan de production : `generation/blueprints.py` (`chapters_for_deliverable`) —
  chaque type commence par une **« Fiche projet » numérotée 0** ;
- le rendu Word : il **ajoute** l'annexe « D'où viennent les chiffres de cette
  étude », numérotée comme un chapitre (`rendu_word/assemblage.py:689-699`).

**D'où vient l'écart ÉCLORE (22 au lieu de 21).** Le sommaire du PDF livré compte
22 entrées numérotées : les chapitres 1 à 21 du plan (du « Résumé exécutif » à
« Sources et méthodologie ») — **exactement les 21 de la carte** — plus
**« 22 — D'où viennent les chiffres de cette étude »**, l'annexe ajoutée par le
rendu. La Fiche projet (chapitre 0) n'apparaît pas au sommaire. Le même +1 vaut
pour les quatre types. À noter aussi : le suivi client affiche « 22 chapitres sur
22 » pour un business plan, parce qu'il compte la Fiche projet
(`organisations/suivi.py:112`, compte des `ChapterGeneration`).

**Faut-il corriger la carte ou le générateur ?** Je ne tranche pas (décision D9).
Deux voies :
- **corriger le générateur** : l'annexe des chiffres devient une annexe **non
  numérotée** (« Annexe — D'où viennent les chiffres »), hors du compte des
  chapitres ; le suivi client ne compte plus la Fiche projet. Le document compte
  alors exactement 21 chapitres numérotés, comme la carte ;
- **corriger la carte** : annoncer 22 / 10 / 22 / 21, en comptant l'annexe comme un
  chapitre.

*Mon avis* : la première voie. L'annexe est une pièce de traçabilité, pas un
chapitre d'analyse vendu ; et la carte reprend les chiffres de evkha.fr, qu'on ne
change pas sans la cliente. Le commentaire de `contenu.ts:246-253` dit d'ailleurs
que « la fiche projet d'ouverture et l'annexe ne sont pas vendues comme des
chapitres » — c'est l'intention ; le rendu ne la respecte pas.

**Cible.** Un seul fichier de configuration par type (liste ordonnée : id, titre,
objectif, données et questions nécessaires, **nature** : chapitre annoncé /
ouverture / annexe), lu par : la page d'achat (via l'API publique, qui sert déjà les
offres), la boucle de génération, le suivi client, le rendu (numérotation) et le
contrôle post-rendu « nombre de chapitres numérotés = nombre annoncé ».

## 7 ter. Le questionnaire et la mémoire

- **Les questionnaires correspondent à la carte** : 14 champs pour l'étude de
  marché, 15 pour la concurrence, 24 pour le business plan (dont 22 obligatoires),
  15 pour la stratégie, identification comprise (`organisations/formulaires.py`,
  `FORMULAIRES`).
- **Aujourd'hui, les réponses ne forment pas une mémoire** : elles deviennent des
  variables brutes ; seules 9 sont lues en chiffres (`CoherenceFact`, par
  expressions régulières — c'est là que résultat net et CAF ont fusionné) ; le reste
  est donné **en JSON brut** à chaque chapitre (`chapitres/runner.py:1666`). Aucune
  décision (date, statut, régime de TVA, offres) n'en est extraite.
- **Aucune traçabilité question → chapitre** : on ne sait pas quel chapitre utilise
  quelle réponse. Le seul contrôle voisin, `brief_non_lu` (`gate.py:647`), signale un
  montant du brief non extrait, rien de plus.
- **Une réponse vide ou incohérente** : pas d'hypothèse posée ; le gate ouvre un
  incident « Il faut obtenir le chiffre auprès du client »
  (`reference_client_illisible`, ex. `investissement_total` sur ÉCLORE, dont la
  réponse dit « Budget de démarrage de 5 000 € » sans le libellé attendu). Le socle,
  lui, peut encore refuser une étude dont une donnée **obligatoire** manque — c'est
  le dernier arrêt possible avant le premier chapitre.
- **Cible** : les réponses sont la première source de la mémoire — `faits`
  « déclarés » et `decisions` — **avant** le chapitre 1 ; une réponse vide ou
  incohérente devient une **hypothèse prudente** marquée comme telle et citée dans
  l'annexe des chiffres ; chaque entrée du plan déclare les questions qu'elle
  utilise ; le rapport interne liste les questions jamais utilisées.

## 8. Décisions à prendre avant de coder

| # | Question | Mon avis |
|---|---|---|
| D1 | Si notre calcul diverge du prévisionnel du client, qui fait foi ? | Le calcul, qui boucle ; l'écart est signalé dans le rapport interne, jamais au client. Mais le client a écrit ses chiffres : il faut au moins garder sa série « déclarée » à part |
| D2 | Définitions : statut juridique strict (micro = pas d'amortissements) ou choix du client ? | Le statut fixe les définitions ; un choix contraire du client devient une hypothèse nommée |
| D3 | Placeholders pour **tous** les nombres, y compris ceux cités des sources de marché ? | Oui pour tout chiffre du projet et tout dérivé ; les chiffres de marché passent par `sources` avec identifiant |
| D4 | Contrôle de langue : LanguageTool en conteneur (Java, ~300 Mo), API publique, ou Grammalecte (Python, hors ligne) ? | Grammalecte ou LanguageTool en conteneur privé ; pas d'API publique (confidentialité) |
| D5 | Temps réel : SSE ou interrogation périodique rapide (2 s) ? | Interrogation périodique : déjà en place, robuste derrière Coolify/nginx, suffisante pour 3 états par chapitre |
| D6 | Budget : quel surcoût par étude est acceptable pour le contrôle par chapitre ? | À fixer après mesure en phase 3 |
| D7 | Le PDF ÉCLORE comme fixture : dans le dépôt, ou hors dépôt ? | Hors dépôt (chemin ignoré par git) ; les tests versionnés utilisent un extrait **anonymisé** |
| D8 | Nouvelle architecture pour les quatre livrables d'un coup, ou business plan d'abord ? | Business plan d'abord (le plus chiffré), puis les autres par configuration |
| D9 | Écart 22/21 : corriger le générateur (annexe des chiffres non numérotée, Fiche projet hors compte) ou la carte ? | Le générateur (voir § 7 bis) |
| D10 | Hypothèse prudente sur une réponse vide : visible du client (annexe des chiffres) seulement, ou aussi dans le chapitre concerné ? | Dans l'annexe des chiffres, et une phrase dans le chapitre qui l'utilise (« hypothèse retenue faute de réponse ») |

---

## 9. Plan par phases (proposé ; un commit et des tests verts par phase)

Chaque phase est livrable seule, derrière le drapeau « pipeline v2 » posé à la
création des nouveaux dossiers. Rien ne touche aux études existantes.

0. **Réparations immédiates, hors drapeau** (petites, déjà localisées, profitent à
   toutes les nouvelles études) : frontières CAF/dotations de l'extracteur ; années
   civiles dans les contrôles ; tolérance d'arrondi ; codes d'unité de l'annexe ;
   axes 0/1/2 ; en-tête et métadonnées (porteur de projet) ; limite de pages sur la
   chaîne Word ; consigne du chapitre 16 et du chapitre 13 du BP.
1. **Configuration par type + mémoire de l'étude + module de calcul +
   placeholders** : un fichier de configuration par type (plan ordonné, nature de
   chaque entrée, questions utilisées), lu par la page d'achat, la génération, le
   suivi et le rendu ; les réponses du questionnaire alimentent `faits` (déclarés)
   et `decisions` avant le chapitre 1, avec hypothèses prudentes marquées ; modèle
   `MemoireEtude` (faits, décisions, définitions, affirmations, chapitres,
   graphiques, sources) construit sur le socle ; passe d'extraction des hypothèses ;
   module de calcul (compte de résultat, CAF, trésorerie, TVA, cotisations, revenu du
   dirigeant, seuils, parts) avec identités testées ; rendu des `{{fait}}` et
   `{{ref:chapitre}}` au format français unique.
2. **Plan dynamique + boucle chapitre par chapitre** : plan produit au démarrage,
   rédaction avec la mémoire complète, contrôles en code par chapitre (nombres,
   phrases de calcul, tableaux, intégrité, décisions, renvois, règles métier,
   unités), contrôle LLM ciblé en JSON strict, mise à jour de la mémoire.
3. **Niveaux de correction 1-2-3 et replis garantis**, budgets de temps et d'appels,
   reprise au dernier chapitre validé ; mesure du coût et de la durée sur la doublure
   puis sur une génération réelle **autorisée**.
4. **Vérification d'ensemble + contrôle post-rendu** (Word et PDF : tableaux,
   pages, en-têtes, axes, légendes, doublons d'images, métadonnées, sommaire,
   annexe recalculée, **nombre de chapitres numérotés = nombre annoncé**).
5. **Interface** : liste dynamique des chapitres, trois états par chapitre,
   vocabulaire positif, reprise au rechargement.
6. **Rapport interne** par étude et page d'agrégation administrateur, avec les
   questions jamais utilisées.
7. **Tests** : détection de chaque erreur listée sur le texte ÉCLORE (lecture
   seule) ; une démonstration **par type** (22, 9, 21, 20 chapitres annoncés) avec
   réponses fictives, sur la doublure — la « répétition à blanc » existante
   (`manage.py repetition_a_blanc`) fait déjà tourner les quatre types sans appel
   payant et sert de base ; une démonstration avec un questionnaire incomplet ou
   incohérent qui se termine avec des hypothèses signalées ; robustesse (échecs LLM
   simulés, redémarrage) ; preuve qu'aucune étude existante n'a changé. Une
   génération réelle (payante) par type ne se fait qu'avec votre accord.

La phase 0 peut être faite tout de suite si vous le souhaitez : elle ne change pas
l'architecture et supprime une partie des défauts visibles dès la prochaine étude.

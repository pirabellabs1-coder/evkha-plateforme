# Chantier de fiabilisation — septembre 2026

Demande du client, 13/09/2026 : trois jours d'affilée au moins pour mettre le
système « 100/100 », surtout les prompts et les chiffres. **Aucune génération
réelle n'est autorisée** : chaque correctif se mesure sur le corpus des dossiers
déjà écrits, re-rendus à zéro centime, et sur la doublure.

## Méthode

1. Mesurer le corpus : `GET /api/dashboard/jobs/<id>/mesure/` sur chaque dossier
   terminé (figures, sources, chiffres hors socle, et depuis `dfd90b8` chaque
   anomalie du fichier Word et chaque échec du gate, avec total et exemples).
2. Classer les défauts par fréquence et par gravité, livrable par livrable.
3. Trier les vrais motifs des faux, en retrouvant l'extrait dans le document
   (règle 2). Un contrôle qui accuse à tort est un défaut : le contrôleur final
   réécrit — et fait payer — les chapitres qu'il désigne.
4. Corriger par CLASSE, puis re-mesurer le corpus et comparer.

Limite à dire : un correctif de PROMPT ne se prouve pas sans génération. Il se
vérifie par la doublure et par des tests de classe sur ce qui part au modèle ;
sa preuve sur un vrai document viendra au prochain dossier client.

## Mesure de référence — 13/09/2026, 37 dossiers, code `dfd90b8`

| Classe | BP (7) | EC (11) | STR (12) | EM (7) |
|---|---|---|---|---|
| `chiffres_hors_socle` (fichier Word) | 393 | 409 | 38 | 43 |
| `visuels` (figures abandonnées) | 84 | 56 | 203 | 42 |
| figures dessinées / demandées | 222/270 | 146/181 | 172/360 | 107/134 |
| `densite` | — | 3 | 44 | — |
| `valeur_nulle` | 13 | 5 | 10 | — |
| gate `coherence_chiffree` | 32 | — | — | — |
| gate `check_bloc_non_resolu` | 1 | 1 | — | 88 |
| gate `strategy_…_decision_absente` | — | — | 40 (12/12) | — |
| gate `fourchette_interdite` | 6 | 1 | 5 | — |
| gate `agregat_faux` | — | 9 | — | — |
| gate `brief_non_lu` | — | 1 | 10 | — |
| sources extérieures sans adresse | 15/56 | 54/155 | 22/51 | 21/21 |

## Audit prompts ↔ contrôles — 14/09/2026

Contradictions PROUVÉES par lecture du code (et pour la plupart par exécution
des contrôles sur des phrases). Statut : ✅ corrigé, 🔧 en cours, ⏳ à faire.

| Id | Constat | Livrables | Statut |
|---|---|---|---|
| A1 | EC : fourchette de CA/parts OBLIGATOIRE dans le prompt (`prompts.py` `exception_ca_estime`, EC ch 06), `fourchette_interdite` strict hors EM | EC | ✅ plage admise en EC seulement suivie de sa valeur retenue (cahier des charges ET cliente) ; gate, prompt, CLAUDE.md alignés |
| A2 | Plages produites par les consignes : `_SYSTEME` « entre X et Y », libellé du socle, « 14-16 % → 15 % retenu », `DECISIONS_STRATEGIE` « fourchette ou prix cible », STR ch 17 seuils | BP EC STR | ✅ consignes réécrites sans montrer de plage ; test de classe avec le détecteur du gate sur tout ce qui part au modèle |
| A3 | Détecteur de fourchettes : « de 60 à 65 € » non vu (« à » accentué) ; « An 1 — 120 000 € », « Scénario 2 - 40 % » accusés à tort ; EM jamais contrôlé | tous | ✅ « à » accentué ; « An 1 — », « Scénario 2 - », trajectoires datées (« 120 000 € en 2026 à 180 000 € en 2027 ») écartés ; les vraies plages de prix derrière une étiquette (« l'offre 60 à 65 € ») restent vues — la 1re version les cachait (relecture). EC : valeur retenue dans la MÊME phrase ou trois colonnes de tableau ; croissance/TCAC toujours unique. Consigne de réécriture alignée (elle montrait « X à Y, médiane retenue Z », forme refusée). EM : bornes gardées dans le libellé du socle |
| A4 | `calcul_faux` : « 250 abonnés à 19 € par mois, soit 57 000 € par an » déclaré faux (×12 sur le seul nombre qui précède « par mois ») — la forme que PRIX règles 5-6 demande | BP EC STR | ✅ prix × effectif × période reconnu comme calcul juste ; test sur la forme exacte de PRIX règles 5-6 |
| A5 | `chiffres_hors_socle` punit les calculs que les prompts exigent de montrer ; dérivations coupées à 80 valeurs dont les doublons | tous | ✅ calcul posé, chiffre sourcé, estimation déclarée (hors taille de marché) reconnus ; doublons retirés avant la coupe, brief en tête ; ne fait plus RÉÉCRIRE (trop peu précis). Relecture : une base inventée ne justifie plus le montant qu'on en tire, « estimé à » ne couvre plus une taille de marché, « selon le canal » n'est plus une source, années et petits nombres ne fabriquent plus de calcul. Corpus : 883 → 756 après la 1re étape |
| A6 | Seuil de rentabilité au mois ET à l'année (PRIX règle 6) → `coherence_chiffree` « 16 250 € au ch. 14 ; 195 000 € au ch. 16 » | BP | ⏳ |
| A7 | BP : dirigeant non rémunéré (validé par BP ch 18, « 0 € » interdit) → `remuneration_dirigeant` exige un montant | BP | ⏳ |
| A8 | « Aucun chiffre hors socle » ×135 dans le plan EM, « SOCLE VERROUILLE » dans six prompts EM, « identifiants du socle » dans la règle des figures | EM (BP STR) | ✅ + test de classe sur tout ce qui part au modèle |
| A9 | EC ch 07 demande `barres_verticales`, type inexistant → chapitre refusé par le contrat | EC | ✅ + test : chaque type nommé dans un prompt existe |
| A10 | Chiffre clé sans source (« laisse le champ vide ») rendu sans point final → `sentence_cut` bloquant | EM | ⏳ |
| A11 | Sources : ratio d'URL exigé alors que les prompts disent « URL si disponible, n'invente aucune URL » ; exemption client jugée ligne par ligne | BP EC STR | ⏳ |
| A12 | Tableau de sources reconnu seulement par un en-tête exact « Source(s) »/« Référence(s) » ; « Organisme \| Publication \| Lien » → « vide » | tous | ⏳ |
| A13 | Même source écrite deux fois (« (Eurostat, 2024) » / « (Eurostat 2024) ») → `sources_divergentes` bloquant, sans chapitre routable | tous | ⏳ |
| A14 | STR : structure « à retenir / lecture stratégique » exigée aussi des chapitres Sources, Annexe, fiche projet | STR | ⏳ |
| A15 | STR : décision exigée sous « offre phare / locomotive / à pousser », jamais demandée par le prompt ch 08 ; horizons 30-60-90 j contre 0-3 mois / 3-12 mois / 1-3 ans au ch 17 | STR | ⏳ |
| A16 | EC : décompte des concurrents dépendant de la forme (encadré coupé à six lignes, puces de forces/faiblesses) | EC | ⏳ |
| A17 | STR : « paragraphes développés » dans tous les prompts contre le plafond de densité (médiane 25 mots) | STR | ⏳ |
| A18 | « un segment » + encadré de 3 puces → `desaccord_numerique` | BP EC STR | ⏳ |

Suspicions et incohérences internes aux prompts (non encore prouvées ou sans
contrôle qui les attrape) : catalogue de figures sans matrice ni chronologie
alors que des prompts les demandent ; « non communiqué » imposé en EC, interdit
par COHERENCE ; marque « EVKHA » dans trois prompts ; notation `MEUR` ;
« points à confirmer par un professionnel » contre `_SYSTEME` ; URL de pages
d'accueil fournies en EM ch 21 ; le prévisionnel du BP (ch 16) et EC ch 03
reçoivent « Ne pas utiliser ce prompt directement » comme seule instruction.

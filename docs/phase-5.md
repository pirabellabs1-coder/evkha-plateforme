# Phase 5 — Business Plan & Strategie Business

Reutilise integralement le moteur de generation des phases 2-3 (runner,
Context / Coherence / Cost Engines, Rendering Engine, assemblage livrable).
Ajoute les blueprints, prompts et variables specifiques aux 2 livrables.

## Source de verite

Structure standard des cabinets de conseil BP/STR (France + Afrique
francophone). **TODO** : aligner les chapitres avec les documents
methode EVKHA du Drive une fois l'acces configure.

## Business Plan — 14 sections

| # | Titre |
|---|---|
| 0 | Fiche projet *(OPENING)* |
| 1 | Resume executif |
| 2 | Porteur de projet et equipe |
| 3 | Description du projet et de l'offre |
| 4 | Analyse du marche cible |
| 5 | Analyse concurrentielle |
| 6 | Strategie commerciale et marketing |
| 7 | Modele economique et sources de revenus |
| 8 | Plan operationnel et organisationnel |
| 9 | Previsions financieres sur 3 ans |
| 10 | Plan de financement et besoins en capital |
| 11 | Analyse des risques et plan de contingence |
| 12 | Calendrier de developpement et jalons |
| 13 | Annexes et reponses specifiques *(ANNEXE)* |

## Strategie Business — 13 sections

| # | Titre |
|---|---|
| 0 | Fiche projet *(OPENING)* |
| 1 | Diagnostic interne |
| 2 | Analyse PESTEL |
| 3 | Analyse concurrentielle strategique |
| 4 | Vision et objectifs strategiques |
| 5 | Choix de positionnement |
| 6 | Strategie d'entree sur le marche |
| 7 | Strategie de croissance |
| 8 | Differentiation et avantage concurrentiel |
| 9 | Plan d'action operationnel |
| 10 | KPIs et tableau de bord |
| 11 | Risques strategiques et scenarios |
| 12 | Conclusion et recommandations *(ANNEXE)* |

## Variables specifiques ajoutees (OPTIONAL)

**BP** : `CAPITAL_INITIAL`, `FORME_JURIDIQUE`, `MODELE_REVENUS`, `EQUIPE`
**STR** : `OBJECTIF_STRATEGIQUE`, `HORIZON_PLANIFICATION`

Aliases Tally correspondants enregistres dans `intake/services.py`.

## Coherence Engine BP

`FORME_JURIDIQUE` et `CAPITAL_INITIAL` sont verrouilles en faits de
coherence des le debut du job (garantit la coherence des projections
financieres du chapitre 2 au chapitre 10).

## Role Claude

**BP** : expert en creation d'entreprise + financement, marches
africains et francophones.
**STR** : consultant senior en strategie d'entreprise, marches emergents.

## Garde-fous verifies (`test_phase5_business.py`)

- 14 sections BP + 13 sections STR generees et rendues.
- Cout sous budget (2 EUR).
- Forme juridique, capital et devise verrouilles dans le Coherence Engine.

## Exclu

- Workflow Gamma / livraison email (Phase 4, branche distincte).

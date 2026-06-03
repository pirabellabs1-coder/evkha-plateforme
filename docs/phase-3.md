# Phase 3 — Moteur Etude de la Concurrence (EC)

Reutilise integralement le moteur de generation de la phase 2 (runner, Context /
Coherence / Cost Engines, Rendering Engine, assemblage livrable). Seuls le
chapitrage, les prompts et un type de fait de coherence sont ajoutes.

## Source de verite

`PROMPT FINAL VERSION 3 EM_EC` (sommaire EC, p.54-55) + exemple
`ETUDE DE LA CONCURRENCE VIVIEN`. **Aucun chapitre invente.**

## Chapitrage (`COMPETITOR_STUDY_CHAPTERS`)

Fiche projet (ouverture) + 8 chapitres canoniques :

0. Fiche projet
1. Identification des concurrents (8 directs + 3 indirects, base consolidee)
2. Classement et analyse qualitative (structure, positionnement, forces/faiblesses)
3. Approfondissement strategique (avis clients, techno, RSE, innovations)
4. Positionnement recommande et annexes strategiques
5. Matrice de positionnement concurrentiel et zones strategiques
6. Estimation des chiffres d'affaires et parts de marche
7. Conclusion analytique et graphiques
8. Annexe — Reponses aux demandes specifiques du client

## Inclus

- `generation/blueprints.py` : `COMPETITOR_STUDY_CHAPTERS` + registre
  `_BLUEPRINTS` ; `chapters_for_deliverable` couvre EM et EC.
- `generation/services.py` : `bootstrap_generation_job` accepte EC.
- `generation/prompt_library.py` : instructions par chapitre EC (`ec.00`..`ec.08`).
- `generation/prompts.py` : rôle EC (expert strategie concurrentielle).
- `generation/models.py` : `FactKind.COMPETITOR` (migration `0003`) pour
  verrouiller la base des concurrents retenus.
- Rendu : titre "Etude de la concurrence", annexe en fin.

## Garde-fous verifies (`test_phase3_competition.py`)

- Blueprint canonique (9 unites, annexe en fin).
- Bootstrap cree les 9 sections (numeros 0..8).
- Generation complete (stub) : 9 chapitres DONE, cout sous budget, rendu ordonne.

## Exclu

- Generation Gamma + livraison email (phase 4).
- Business plan / strategie (phase 5).

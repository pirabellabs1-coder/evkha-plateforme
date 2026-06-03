# Phase 2 — Moteur Etude de Marche

Cette tranche initialise le moteur de generation sans appel reseau vers Claude.

## Inclus

- Blueprint des 22 chapitres Etude de Marche.
- Creation d'un `GenerationJob` depuis une soumission Tally normalisee.
- Creation idempotente des 22 `ChapterGeneration`.
- `Context Engine` minimal :
  - variables projet ;
  - resumes operationnels precedents ;
  - faits verrouilles ;
  - chapitre cible.
- `Coherence Engine` minimal :
  - stockage de faits verrouilles ;
  - refus des contradictions sur un fait deja verrouille.
- `Cost Engine` minimal :
  - estimation cout tokens ;
  - cout chapitre ;
  - total dossier.

## Exclu

- Appel API Claude reel.
- Parsing des prompts proprietaires EVKHA.
- Rendu Google Docs / PDF.
- Controle editorial final.

Ces elements arrivent apres validation de cette couche moteur.

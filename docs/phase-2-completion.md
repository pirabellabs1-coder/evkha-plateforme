# Phase 2 (finalisation) — Moteur Etude de Marche operationnel

La tranche initiale posait les contrats des moteurs. Cette finalisation rend la
generation **reellement fonctionnelle** de bout en bout, en restant CI-safe
(aucun appel reseau dans les tests : adaptateurs stubs deterministes).

## Inclus

- **Adaptateur Claude** (`integrations/claude.py`) : `ClaudeClient` (Protocol),
  `AnthropicClaudeClient` (appel reel, import paresseux du SDK + cle env),
  `StubClaudeClient` (deterministe), fabrique `get_claude_client()`.
- **Prompts EVKHA** (`generation/prompts.py` + `prompt_library.py`) : rôle EM,
  charte editoriale (ton mentor, esprit critique, sources en fin), et
  instructions fideles par chapitre (source : PROMPT FINAL V3 + Consignes).
- **Runner d'orchestration** (`generation/runner.py`) : genere les chapitres
  dans l'ordre, branche Context -> Prompt -> Claude -> contenu + resume
  operationnel -> Cost Engine (plafond) -> Coherence Engine. **Resumable**
  (saute les chapitres DONE), incidents operationnels sur echec.
- **Rendering Engine** (`generation/rendering.py`) : retrait des marqueurs
  internes (Etape, Point de controle, Verification, Prompt a utiliser...),
  assemblage ordonne (ouverture -> chapitres -> annexe -> sources), export
  Markdown client.
- **Assemblage livrable** (`documents/services.py` + `integrations/google_docs.py`)
  : `assemble_document()` cree un `DocumentArtifact` (checksum, URL, expiration
  selon retention), via `GoogleDocsClient` (stub + adaptateur reel a credentials).
- **Tache Celery** (`generation/tasks.py`) : `run_generation_job_task`.
- **Cost Engine** : seeding des faits verrouilles (devise par pays, secteur,
  zone) garantissant la coherence transverse.

## Garde-fous verifies par les tests (`test_phase2_pipeline.py`)

- 23 chapitres generes et marques DONE, contenu + resume non vides.
- Cout total suivi et **inferieur au budget** (2 EUR par defaut).
- Devise verrouillee (ex. Benin -> XOF) reinjectee dans le contexte.
- Relance **idempotente** (pas de regeneration, cout stable).
- Artefact livrable READY (URL + checksum) produit.
- Document client ordonne, marqueurs internes retires.

## Exclu (volontairement, hors logique metier)

- Cablage OAuth Google reel (credentials NDA, etape infrastructure) :
  `GoogleDocsApiClient` echoue explicitement tant qu'il n'est pas configure.
- Generation Gamma + envoi email (phase 4).

## Bascule production

Dans `.env` : `EVKHA_USE_STUB_AI=false` + `ANTHROPIC_API_KEY=...` pour activer
l'appel reel ; `EVKHA_USE_STUB_DOCS=false` une fois Google cable. Installer
l'extra : `pip install -e ".[ai]"`.

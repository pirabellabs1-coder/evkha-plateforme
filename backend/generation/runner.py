from __future__ import annotations

import logging
import re
from typing import Any

from django.utils import timezone

from catalog.models import DeliverableType
from intake.models import IntakeSubmission
from integrations.claude import _DEFAULT_MAX_TOKENS, ClaudeClient, get_claude_client
from monitoring.models import IncidentSeverity, OperationalIncident
from organisations.liaison import debiter_pour_job

from .blueprints import chapters_for_deliverable, get_blueprint
from .chapitres.configuration import est_declare, type_document
from .chapitres.services import produire_chapitre
from .checks_blocs import (
    BLOCS_PAR_IDENTIFIANT,
    INCIDENT_TYPE_CHECK_BLOC,
    BlocDefinition,
    bloc_pour_chapitre,
    check_bloc,
)
from .coherence import (
    CoherenceConflictError,
    extract_and_lock_chiffres_cles,
    extract_and_lock_numeric_facts,
    seed_locked_facts_from_variables,
)
from .cost import (
    CostBudgetExceededError,
    max_tokens_for_job,
    record_chapter_cost,
    tokens_pour_cible,
)
from .models import ChapterGeneration, ChapterStatus, GenerationJob, JobStatus
from .prompts import build_chapter_prompt, build_section_prompt, build_system_prompt
from .qa import detect_violations, repair_rule_based
from .socle import (
    SocleGenerationError,
    etablir_socle,
    livrable_supporte,
    socle_actif,
    socle_verrouille,
)

# QC Evangeline #1 : porte le resume operationnel a 1200 chars et priorise les
# phrases chiffrees/sourcees. En dessous, tous les chiffres cles fuyaient d'un
# chapitre a l'autre => 6 valeurs differentes pour un meme indicateur.
_SUMMARY_MAX_CHARS = 1200
_SOURCES_SPLIT = re.compile(r"\n\s*sources\b", re.IGNORECASE)
_NUMERIC_HINT = re.compile(r"\d|%|€|\$|CFA|EUR|USD|M€|Md€|Mds|millions?|milliards?", re.IGNORECASE)
_MAX_VALIDATION_RETRIES = 1

# Em-dash et en-dash sont des signatures IA immediatement reperees par les
# lecteurs professionnels. La consigne prompt (TYPOGRAPHIE) demande a Claude
# de les eviter dans la prose, mais il en glisse regulierement. Ce regex les
# elimine en post-processing : remplace " — " et " – " par ", ". Le tiret
# court "-" reste intact pour les mots composes (self-stockage...).
# EXCEPTION (Bloc 1 Consignes) : les titres/sous-titres au format
# « X.Y — Titre » conservent leur tiret cadratin — c'est le format IMPOSE
# par les consignes d'ecriture. Le strip est donc applique ligne par ligne
# en sautant les lignes de titre.
_AI_TELL_DASHES = re.compile(r"\s*[—–]\s*")
_HEADING_LINE = re.compile(r"^\s*(?:#{1,6}\s|\*\*?\d+\.\d+\s*[—–]|\d+\.\d+\s*[—–])")


def _remplacer_tiret(match: re.Match[str]) -> str:
    """Choisit le remplacement d'un tiret cadratin selon son contexte.

    Deux contextes ou la virgule detruit l'information (constate sur le run
    reel 010e3bf2, chapitre 2) :
      - fourchette chiffree : « 100 — 120 kEUR » devenait « 100, 120 kEUR »,
        illisible dans un tableau financier et lu comme une erreur de calcul ;
      - cellule de tableau ne contenant que le tiret (« sans objet ») :
        « <td>—</td> » devenait « <td>,</td> », cellule videe de son sens.
    """
    ligne = match.string
    avant = ligne[: match.start()].rstrip()
    apres = ligne[match.end() :].lstrip()
    # Cellule de tableau reduite au seul tiret : convention « sans objet ».
    if avant.endswith((">", "|")) and apres[:1] in ("<", "|"):
        return match.group(0)
    # Fourchette chiffree : on ecrit la borne en clair.
    if avant[-1:].isdigit() and apres[:1].isdigit():
        return " à "
    return ", "


def _strip_ai_tell_dashes(content: str) -> str:
    """Retire les em-dashes / en-dashes de la prose, en preservant les titres.

    Ceinture-bretelles avec la regle typographique injectee dans le system
    prompt : garantit la couverture meme si Claude ignore la consigne.
    Les lignes de titre (markdown '#', ou sous-titre numerote 'X.Y — Titre')
    gardent leur tiret cadratin, exige par le Bloc 1 des Consignes EVKHA.
    Les fourchettes chiffrees et les cellules « sans objet » sont preservees
    par _remplacer_tiret : la virgule y detruirait la donnee.
    """
    lines = content.split("\n")
    out = [
        line if _HEADING_LINE.match(line) else _AI_TELL_DASHES.sub(_remplacer_tiret, line)
        for line in lines
    ]
    return "\n".join(out)


def _plafonner_sur_cible(
    job: GenerationJob,
    chapter: ChapterGeneration,
    max_tokens: int,
    *,
    sections: tuple[str, ...],
) -> int:
    """Borne la sortie sur la cible editoriale du chapitre (ou de la section).

    `max_words` du blueprint s'entend PAR SECTION quand le chapitre est
    decoupe (cf. son docstring) : on applique donc la meme cible que celle
    annoncee au modele par `build_section_prompt`, sans quoi la borne dure et
    la consigne du prompt se contrediraient.

    Sans ce plafond, la consigne de concision restait un voeu : le modele
    disposait de 8 192 tokens par appel, soit ~5 100 mots pour une cible de
    900.
    """
    from .blueprints import SECTION_MAX_WORDS, get_blueprint  # noqa: PLC0415

    blueprint = get_blueprint(job.deliverable_type, chapter.chapter_number)
    if blueprint is None or not blueprint.max_words:
        return max_tokens
    if sections:
        # Une seule valeur pour toutes les sections du chapitre : on retient la
        # plus large des surcharges, la borne reste correcte pour les autres.
        cibles = [SECTION_MAX_WORDS.get(s, blueprint.max_words) for s in sections]
        cible = max(cibles) if cibles else blueprint.max_words
    else:
        cible = blueprint.max_words
    plafond = tokens_pour_cible(cible)
    return min(max_tokens, plafond) if plafond else max_tokens


def _resolve_tokens(content: str, job: GenerationJob) -> str:
    """Brique 1 : remplace les tokens client par la valeur exacte du brief.

    Applique AVANT la validation : sinon un token legitime `{{emprunt}}` serait
    signale comme placeholder non resolu et declencherait un retry inutile.
    Un token INCONNU est laisse en place — la validation le detecte alors et le
    retry demande au modele de le corriger.
    """
    from .substitution import resolve_client_fact_tokens  # noqa: PLC0415

    resolved, _unresolved = resolve_client_fact_tokens(content, job)
    return resolved


_log = logging.getLogger(__name__)

class GenerationRunError(RuntimeError):
    """Echec irrecuperable d'un cycle de generation (au moins un chapitre KO)."""


class CreditsInsuffisantsError(GenerationRunError):
    """Le portefeuille de l'organisation ne couvre pas cette generation.

    « Commande bloquee avec proposition d'achat de credits additionnels. Aucun
    decouvert. » (§11) — le job est marque FAILED sans qu'aucun appel facture
    n'ait ete emis.
    """


class CheckInitialBlockedError(GenerationRunError):
    """Le CHECK INITIAL a echoue : la fiche projet n'est pas prete.

    Manuel EVKHA p.3 : « Si la fiche projet est complete, coherente et fidele
    a la demande, commencer le chapitre 1. Sinon, corriger la fiche ou demander
    la precision necessaire AVANT TOUTE REDACTION. » Et p.2 : « On ne continue
    jamais par automatisme. » On stoppe donc la generation avant le chapitre 1 :
    l'admin doit corriger le brief / la fiche puis relancer.
    """


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _operational_summary(content: str) -> str:
    """Resume operationnel : phrases chiffrees/sourcees priorisees, cap 1200 chars.

    On retire le bloc Sources puis on selectionne d'abord toutes les phrases
    contenant un chiffre ou une unite monetaire (celles qui doivent absolument
    fuir vers les chapitres suivants pour eviter les incoherences chiffrees).
    Les autres phrases completent jusqu'a la cap.
    """
    body = _SOURCES_SPLIT.split(content, maxsplit=1)[0].strip()
    if not body:
        return ""
    body = " ".join(body.split())
    if len(body) <= _SUMMARY_MAX_CHARS:
        return body

    sentences = _split_sentences(body)
    numeric = [s for s in sentences if _NUMERIC_HINT.search(s)]
    others = [s for s in sentences if not _NUMERIC_HINT.search(s)]

    kept: list[str] = []
    used = 0
    for group in (numeric, others):
        for sentence in group:
            if used + len(sentence) + 1 > _SUMMARY_MAX_CHARS:
                continue
            kept.append(sentence)
            used += len(sentence) + 1

    if not kept:
        return body[:_SUMMARY_MAX_CHARS].rstrip() + "..."
    return " ".join(kept)


def _variables_for(job: GenerationJob) -> dict[str, object]:
    submission = IntakeSubmission.objects.filter(order=job.order).first()
    return submission.normalized_variables if submission else {}


def _build_phase0_plan(job: GenerationJob, variables: dict[str, object]) -> str:
    """Plan pré-génération déterministe, sans recopier le brief client.

    Historique : ce plan listait auparavant tous les concurrents, exigences et
    sous-sections avec des "RÈGLE ABSOLUE". Deux problèmes majeurs identifiés :
    1. Duplication : VARIABLES_PROJET (context.py) sérialise déjà tout le brief
       dans le user prompt. Ré-émettre dans le system prompt coûte ~1500 tok/appel
       × 30 appels = ~45k tok/job = ~€0.12/job pour zéro info nouvelle.
    2. Contradiction : "traiter les N concurrents dans l'ordre exact" écrasait
       `ec.01.identification` qui dit "sélectionne les 8 plus pertinents". Prompts
       contradictoires → Claude sur-focalise sur les concurrents et zappe
       d'autres sous-parties (ex. chap 6.2 EC absent).

    Fix : bloc court (~350 chars, cachable) qui rappelle l'importance du brief
    SANS lister ni contraindre l'ordre. La sélection/priorisation reste
    gouvernée par les prompts individuels du prompt_library.
    """
    if not chapters_for_deliverable(job.deliverable_type):
        return ""

    has_brief = any(
        _var(variables, k) for k in ("CONCURRENTS", "DEMANDES_SPECIFIQUES", "ELEMENTS_A_RETENIR")
    )
    if not has_brief:
        return ""

    return (
        "PLAN VERROUILLÉ — CONTRAINTES DE GÉNÉRATION\n"
        "- Le brief client (CONCURRENTS, DEMANDES_SPECIFIQUES, ELEMENTS_A_RETENIR) "
        "est transmis une seule fois via VARIABLES_PROJET dans le user prompt.\n"
        "- Pour les concurrents, applique la consigne du chapitre cible : "
        "sélectionner, compléter ou ordonner selon ce que demande CE chapitre.\n"
        "- Pour les chapitres découpés, traite intégralement la SECTION_A_GENERER "
        "courante ; les autres sections sont pilotées par leurs appels dédiés.\n"
        "- Ne survole aucune demande spécifique du brief."
    )


def _var(v: dict[str, object], k: str) -> str:
    """Lit une variable normalisée en gérant les valeurs list-valued de Tally.

    Tally peut envoyer un champ multi-select comme list ; intake/services.py
    stocke la valeur brute sans coercion. str([...]) produit du charabia
    (crochets + quotes) — on rejoint proprement avec ', ' à la place.
    """
    raw = v.get(k)
    if raw is None:
        return ""
    if isinstance(raw, list):
        return ", ".join(str(x).strip() for x in raw if str(x).strip())
    return str(raw).strip()


#: Motifs qui ne valent pas la peine d'etre rejoues.
#:
#: Rejouer un budget depasse ou une annulation ne ferait que depenser
#: davantage pour le meme refus. Liste FERMEE de ce qu'on ne rejoue pas — on
#: rejoue tout le reste, y compris les erreurs qu'on n'a pas prevues, parce que
#: c'est precisement celles-la qui coutent le plus cher (regle 4).
ERREURS_SANS_REPRISE = (CostBudgetExceededError, CheckInitialBlockedError)


def _moteur_structure(job: GenerationJob) -> bool:
    """Le job passe-t-il par le moteur structure (socle + payload) ?

    Une seule source pour cette verite (regle 5). Elle gouverne DEUX decisions
    qui doivent rester d'accord : par quel chemin un chapitre est ecrit, et par
    quel chemin il est REecrit. Les laisser diverger, c'est reparer une
    representation du chapitre pendant que le document en rend une autre.
    """
    return (
        socle_actif()
        and livrable_supporte(job)
        and est_declare(str(job.deliverable_type))
    )


def _produire_avec_reprises(
    job: GenerationJob, chapter: Any, *, client: Any, socle: Any
) -> None:
    """Produit un chapitre, en REESSAYANT — ce que ce runner ne faisait pas.

    ## Pourquoi cette fonction existe

    Trois generations reelles, trois morts, une seule cause structurelle.

    Ce runner appelait `produire_chapitre` UNE fois et laissait l'exception
    remonter. Or il est le chemin de production : la tache Celery par chapitre,
    qui porte une boucle de reprise complete avec temporisation exponentielle,
    n'est employee par rien.

    - Run nº1 : mort au chapitre 1 sur un ecart de volume de 20 %.
    - Run nº2 : mort au chapitre 5 sur un resume de 254 mots pour 250.
    - Run nº3 : mort au chapitre 20 sur `blocs : Field required` — une reponse
      de modele incomplete, c'est-a-dire l'incident TRANSITOIRE par excellence.
      Dix-neuf chapitres ecrits, 1,21 EUR, perdus.

    J'ai corrige les deux premiers en rendant les regles concernees tolerantes.
    C'etait traiter deux instances d'un defaut dont la classe est ici : un
    chemin sans reprise transforme le moindre alea en perte totale (regle 4).

    ## Ce que la reprise coute, et ce qu'elle evite

    Une tentative supplementaire coute un appel — de l'ordre de six centimes.
    L'absence de reprise a coute 1,21 EUR et vingt minutes, trois fois. Le
    plafond vient de `tentatives_max` (3), la meme valeur que la tache Celery
    utilise deja : une seule source pour cette verite (regle 5).

    ## Pourquoi la derniere tentative se declare

    L'arbitrage de conformite accepte les ecarts de forme sur la DERNIERE
    tentative seulement. Il ne peut pas le deviner : `retry_count` n'est
    incremente que par le chemin d'echec, et le deduire ici recreerait le
    defaut du run nº1. On le lui dit.
    """
    document = type_document(str(job.deliverable_type))
    derniere_erreur: Exception | None = None

    for tentative in range(1, document.tentatives_max + 1):
        try:
            produire_chapitre(
                job, chapter.chapter_number, client=client, socle=socle,
                derniere_tentative=(tentative == document.tentatives_max),
            )
            if tentative > 1:
                _log.warning(
                    "Job %s chapitre %s : reussi a la tentative %s.",
                    job.id, chapter.chapter_number, tentative,
                )
            return
        except ERREURS_SANS_REPRISE:
            # Rejouer ne changerait rien : le budget reste depasse, le CHECK
            # INITIAL reste bloquant. On laisse remonter tel quel.
            raise
        except Exception as erreur:  # noqa: BLE001 — on rejoue tout le reste
            derniere_erreur = erreur
            if tentative < document.tentatives_max:
                _log.warning(
                    "Job %s chapitre %s : tentative %s/%s echouee (%s). On rejoue.",
                    job.id, chapter.chapter_number, tentative,
                    document.tentatives_max, erreur,
                )

    # Toutes les tentatives ont echoue : l'appelant ouvre l'incident et arrete
    # l'etude, comme avant. La difference est qu'on y arrive apres avoir
    # reellement essaye.
    assert derniere_erreur is not None
    raise derniere_erreur


def run_generation_job(
    job: GenerationJob,
    *,
    client: ClaudeClient | None = None,
) -> GenerationJob:
    """Genere tous les chapitres d'un job dans l'ordre.

    Resumable : les chapitres deja DONE sont ignores. Garde-fous : budget cout
    (regle d'or #1) et coherence (faits verrouilles). Tout echec marque le job
    FAILED, ouvre un incident operationnel et leve une exception.
    """
    client = client or get_claude_client()

    # Lot 4 — debit des credits AU LANCEMENT (cahier des charges §11), avant le
    # premier appel facture. Sans organisation rattachee, aucun debit : c'est le
    # flux Systeme.io en service, deja paye autrement. Une relance ne repaie pas
    # (idempotence par reference de job).
    autorise, raison = debiter_pour_job(job)
    if not autorise:
        GenerationJob.objects.filter(pk=job.pk).update(
            status=JobStatus.FAILED,
            error_message=f"Credits insuffisants : {raison}"[:2000],
        )
        msg = f"Generation refusee pour le job {job.id} : {raison}"
        raise CreditsInsuffisantsError(msg)

    job.status = JobStatus.RUNNING
    if job.started_at is None:
        job.started_at = timezone.now()
    job.error_message = ""
    job.save(update_fields=["status", "started_at", "error_message", "updated_at"])

    variables = _variables_for(job)
    seed_locked_facts_from_variables(job, variables)
    country = str(variables.get("PAYS", "")).strip()

    # Recherche web collectée UNE fois au démarrage (ancrage anti-hallucination
    # §6). Idempotent sur relance : si le brief existe déjà, on ne relance pas
    # les requêtes (coût + cohérence entre chapitres restants). Vide en mode
    # stub — le pipeline continue sans ancrage, comme avant.
    if not job.research_brief:
        try:
            from .research import collect_research_brief  # noqa: PLC0415

            brief = collect_research_brief(job.deliverable_type, variables)
        except Exception:  # noqa: BLE001 — la recherche ne doit jamais bloquer un job
            brief = ""
        if brief:
            job.research_brief = brief
            job.save(update_fields=["research_brief", "updated_at"])

    # ── Socle verrouillé (lot 1) ─────────────────────────────────────────────
    #
    # `etablir_socle` existait depuis le lot 1 et n'était appelée QUE par une
    # action de l'administration Django. Le moteur en service n'en établissait
    # aucun. Consequence : le rendu Word du lot 3 refusait de produire le
    # livrable — « aucun socle verrouillé, ses graphiques n'auraient rien à
    # citer » — et tout le nouveau moteur restait hors circuit.
    #
    # Ici, et pas ailleurs : APRÈS la recherche web, qui l'alimente, et AVANT le
    # premier chapitre, qui le cite. Idempotent — une relance ne le repaie pas.
    #
    # Un socle en échec fait échouer le job. Continuer produirait des chapitres
    # sans référence commune, c'est-à-dire un document qui a l'air complet et
    # dont aucun chiffre n'est ancré (règle 1 : échouer bruyamment).
    # Un SEUL interrupteur pour tout le nouveau moteur. Les chapitres
    # structurés exigent le socle : deux drapeaux distincts autoriseraient la
    # combinaison « chapitres sans socle », qui ne produit que des échecs.
    moteur_structure = _moteur_structure(job)

    if moteur_structure:
        try:
            etablir_socle(
                job,
                client=client,
                variables=variables,
                brief_recherche=job.research_brief or "",
            )
        except SocleGenerationError as exc:
            GenerationJob.objects.filter(pk=job.pk).update(
                status=JobStatus.FAILED,
                error_message=f"Socle non établi : {exc}"[:2000],
            )
            OperationalIncident.objects.create(
                title=f"Socle non établi (job {job.id})",
                severity=IncidentSeverity.HIGH,
                job=job,
                order=job.order,
                details={"motifs": list(getattr(exc, "motifs", [])),
                         "tentatives": getattr(exc, "tentatives", 0)},
            )
            raise

    # Phase 0 : rappel court des exigences client. Garde `if not job.phase0_plan` :
    # sur une relance avec chapitres partiellement DONE, on préserve le plan
    # initial pour ne pas générer les chapitres restants avec un plan divergent
    # (ex. brief édité entre deux runs).
    if not job.phase0_plan:
        phase0_plan = _build_phase0_plan(job, variables)
        if phase0_plan:
            job.phase0_plan = phase0_plan
            job.save(update_fields=["phase0_plan", "updated_at"])
    else:
        phase0_plan = job.phase0_plan

    system_prompt = build_system_prompt(
        job.deliverable_type, country=country, plan=phase0_plan
    )

    # Relu UNE fois : le socle est identique pour tous les chapitres du run, et
    # le relire à chaque tour multiplierait les requêtes sans rien changer.
    socle_du_run = socle_verrouille(job) if moteur_structure else None

    chapters = job.chapters.exclude(status=ChapterStatus.DONE).order_by("chapter_number")
    for chapter in chapters:
        # Vérification annulation entre chaque chapitre (check DB allégé)
        job.refresh_from_db(fields=["status"])
        if job.status == JobStatus.CANCELLED:
            return job

        try:
            if moteur_structure:
                # Sortie STRUCTURÉE (lot 2) : le chapitre cite les identifiants
                # du socle et demande ses graphiques. `enregistrer_chapitre`
                # écrit aussi le markdown, de sorte que l'ancienne chaîne de
                # rendu reste servie par le même chapitre.
                #
                # `_inline_qa_repair` reste ÉCARTÉ : il réécrit le MARKDOWN seul,
                # or c'est le `payload` que le rendu Word emploie. Sa réparation
                # n'atteindrait pas le document livré (règle 3) et ferait diverger
                # deux versions du même chapitre (règle 5). La vérification du
                # lot 4, elle, porte sur le `.docx` produit.
                #
                # `_after_chapter_hook` est RÉTABLI. Il avait été écarté avec lui,
                # alors qu'il ne partage pas son défaut : il DÉTECTE — le CHECK lit
                # le markdown, rendu fidèlement depuis le payload par
                # `enregistrer_chapitre` — et sa réparation passe par
                # `regenerate_chapter`, qui suit désormais le moteur actif.
                #
                # Sans cet appel, AUCUN CHECK ne s'exécutait en production
                # (EVKHA_SOCLE_ENABLED=true). Trois conséquences, pas une : le gate
                # cherchait des incidents `check_bloc_non_resolu` qui ne pouvaient
                # pas exister et concluait au succès (règle 1) ; le CHECK INITIAL,
                # que le manuel veut bloquant avant toute rédaction, ne se
                # déclenchait jamais — un brief défaillant produisait une étude
                # entière ; et `enrichir_fiche_apres_check` ne tournait plus, donc
                # la fiche projet cessait de s'enrichir entre les blocs.
                _produire_avec_reprises(
                    job, chapter, client=client, socle=socle_du_run
                )
                _after_chapter_hook(job, chapter, client=client)
            else:
                _generate_chapter(
                    job, chapter, client=client, system_prompt=system_prompt
                )
                # QA rule-based immédiate : corrections automatiques sans appel IA.
                # Les violations critiques restantes sont traitées par le QA final (IA).
                _inline_qa_repair(chapter)
                # CHECK inter-bloc (manuel Evangeline §6) : uniquement pour
                # l'EM, apres chaque dernier chapitre d'un bloc. Silencieux pour
                # BP/EC/STR (blueprints non couverts par le manuel).
                _after_chapter_hook(job, chapter, client=client)
        except CheckInitialBlockedError as exc:
            # CHECK INITIAL bloquant : la fiche projet (chapitre 0) est valide
            # et DONE — on ne la marque PAS FAILED. L'incident HIGH est deja
            # ouvert par _executer_check_avec_retry. On stoppe juste le job.
            GenerationJob.objects.filter(pk=job.pk).update(
                status=JobStatus.FAILED,
                error_message=(
                    "CHECK INITIAL echoue : fiche projet a corriger avant "
                    f"toute redaction. {exc}"
                )[:2000],
            )
            raise
        except CostBudgetExceededError as exc:
            # L'incident budget est deja ouvert par le Cost Engine ; le chapitre
            # courant a un contenu valide. On stoppe juste le job proprement.
            GenerationJob.objects.filter(pk=job.pk).update(
                status=JobStatus.FAILED,
                error_message=str(exc),
            )
            raise
        except Exception as exc:  # noqa: BLE001 - tout echec doit etre trace + incident
            _fail(job, chapter, exc, title=f"Echec generation chapitre {chapter.chapter_number}")
            msg = f"Generation failed on chapter {chapter.chapter_number}: {exc}"
            raise GenerationRunError(msg) from exc

    # Ne pas écraser une annulation demandée pendant la dernière génération
    job.refresh_from_db(fields=["status"])
    if job.status == JobStatus.CANCELLED:
        return job

    job.status = JobStatus.DONE
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "completed_at", "updated_at"])
    return job


def regenerate_chapter(
    job: GenerationJob,
    chapter: ChapterGeneration,
    *,
    corrective_note: str,
    client: ClaudeClient | None = None,
) -> None:
    """Régénère UN chapitre en corrigeant les défauts détectés.

    Deux appelants : la boucle d'auto-correction post-gate
    (generation/correction.py) et la réparation des CHECKs inter-blocs. On
    reprend le chapitre avec la liste exacte des problèmes en consigne
    prioritaire. Respecte le budget (le Cost Engine peut lever
    CostBudgetExceededError, propagée à l'appelant qui décide d'arrêter).

    ## Régénérer par le chemin que le document lit réellement

    Cette fonction passait inconditionnellement par `_generate_chapter`, qui
    n'écrit que `chapter.content`. Or, moteur structuré actif — c'est le cas
    en production —, le `.docx` est rendu depuis `payloads_du_job`,
    c'est-à-dire `chapter.payload`, que ce chemin ne touche jamais.

    La boucle d'auto-correction réécrivait donc le markdown, revalidait le
    markdown, se déclarait satisfaite, et livrait un document INCHANGÉ : le
    contrôle et sa réparation jugeaient sur une évidence que le lecteur ne
    reçoit pas (règles 3 et 9). On suit désormais le moteur actif, une seule
    fois et pour tous les appelants — plutôt que de corriger chaque appelant
    séparément (règle 4).
    """
    client = client or get_claude_client()

    if _moteur_structure(job):
        # Import tardif : `chapitres.services` remonte vers `generation.cost`,
        # le cycle se referme si on le charge au niveau module.
        from .chapitres.services import regenerer_chapitre  # noqa: PLC0415

        regenerer_chapitre(
            job,
            chapter.chapter_number,
            client=client,
            note_corrective=corrective_note,
        )
        chapter.refresh_from_db()
        return

    variables = _variables_for(job)
    country = str(variables.get("PAYS", "")).strip()
    system_prompt = build_system_prompt(
        job.deliverable_type, country=country, plan=job.phase0_plan
    )
    _generate_chapter(
        job, chapter, client=client, system_prompt=system_prompt,
        corrective_note=corrective_note,
    )
    _inline_qa_repair(chapter)


def _inline_qa_repair(chapter: ChapterGeneration) -> bool:
    """QA rule-based immediate apres generation d'un chapitre.

    Applique les corrections automatiques (code fences, balises orphelines,
    marqueurs pipeline...) directement apres la generation, sans appel IA.
    Retourne True si des violations critiques persistent apres correction
    (signal pour le QA final qui pourra tenter une reparation IA).
    """
    content = chapter.content
    if not content or not content.strip():
        return True

    violations = detect_violations(content, chapter.prompt_key, chapter.chapter_number)
    if not violations:
        return False

    repaired, _fixes = repair_rule_based(content, chapter.prompt_key, chapter.chapter_number)
    if repaired != content:
        chapter.content = repaired
        chapter.save(update_fields=["content", "updated_at"])
        # Re-détection sur le contenu réparé pour savoir si des critiques subsistent
        violations = detect_violations(repaired, chapter.prompt_key, chapter.chapter_number)

    return any(v.severity == "critical" for v in violations)


def _generate_chunked(
    job: GenerationJob,
    chapter: ChapterGeneration,
    sections: tuple[str, ...],
    *,
    client: ClaudeClient,
    system_prompt: str,
    chapter_model: str | None = None,
    corrective_note: str = "",
) -> tuple[str, int, int, str | None]:
    """Genere un chapitre section par section et fusionne le contenu.

    Retourne (content, total_input_tokens, total_output_tokens, model).
    Les tokens sont accumules sur l'ensemble des sections pour que le
    Cost Engine dispose du cout reel complet du chapitre. Le budget restant
    (regle d'or #1 durcie) est reparti sur les sections de CE chapitre.
    """
    from .validation import (  # noqa: PLC0415 — eviter un cycle d'import
        format_issues_for_retry,
        has_blocking_issues,
        validate_chapter_content,
    )

    parts: list[str] = []
    total_input = 0
    total_output = 0
    last_model: str | None = None
    max_tokens = max_tokens_for_job(
        job,
        default_max_tokens=_DEFAULT_MAX_TOKENS,
        call_count=len(sections),
        # Le retry cible ci-dessous peut doubler les appels de chaque section :
        # le planificateur doit le savoir AVANT (audit F4).
        validation_retries=_MAX_VALIDATION_RETRIES,
    )
    # Plafond issu de la CIBLE editoriale, appliqué APRES le calcul budgetaire :
    # il ne doit pas etre releve par le plancher `_MIN_MAX_TOKENS`, qui protege
    # d'une penurie de budget, pas d'une consigne de concision.
    max_tokens = _plafonner_sur_cible(job, chapter, max_tokens, sections=sections)

    for section_key in sections:
        # Contexte accumulé des sections déjà générées dans ce chapitre.
        # Aide Claude à ne pas répéter et à rester cohérent entre sections.
        previous_context = "\n\n".join(parts) if parts else ""
        prompt = build_section_prompt(
            chapter, section_key,
            previous_context=previous_context, corrective_note=corrective_note,
        )
        result = client.complete(
            system=system_prompt, prompt=prompt, max_tokens=max_tokens, model=chapter_model
        )
        total_input += result.input_tokens
        total_output += result.output_tokens

        # Retry CIBLE sur la section fautive (audit juillet 2026, point 8).
        # Auparavant les chapitres decoupes n'avaient aucun retry : or ce sont
        # les plus denses (EC 2/3, EM 1/2/10/14/19, BP 14/15) et donc les plus
        # exposes aux tableaux vides et aux troncatures. Regenerer LA section
        # en defaut coute une fraction d'un retry de chapitre entier et ne
        # detruit pas les sections deja correctes.
        attempts = 0
        section_content = _resolve_tokens(result.content, job)
        issues = validate_chapter_content(section_content)
        while has_blocking_issues(issues) and attempts < _MAX_VALIDATION_RETRIES:
            attempts += 1
            retry_prompt = f"{prompt}\n\n{format_issues_for_retry(issues)}"
            result = client.complete(
                system=system_prompt,
                prompt=retry_prompt,
                max_tokens=max_tokens,
                model=chapter_model,
            )
            total_input += result.input_tokens
            total_output += result.output_tokens
            section_content = _resolve_tokens(result.content, job)
            issues = validate_chapter_content(section_content)

        parts.append(section_content)
        last_model = result.model

    return "\n\n".join(parts), total_input, total_output, last_model


def _generate_chapter(
    job: GenerationJob,
    chapter: ChapterGeneration,
    *,
    client: ClaudeClient,
    system_prompt: str,
    corrective_note: str = "",
) -> None:
    from .validation import (
        ChapterValidationIssue,
        format_issues_for_retry,
        has_blocking_issues,
        validate_chapter_content,
    )

    chapter.status = ChapterStatus.RUNNING
    chapter.error_message = ""
    chapter.save(update_fields=["status", "error_message", "updated_at"])

    blueprint = get_blueprint(job.deliverable_type, chapter.chapter_number)
    sections = blueprint.sections if blueprint else ()
    # Modele specifique au chapitre (None = herite de EVKHA_CLAUDE_MODEL).
    # Depuis le 25/07/2026 tous les blueprints ont model=None : pipeline
    # homogene sur claude-sonnet-4-6.
    chapter_model = blueprint.model if blueprint else None
    # Outil d'execution de code : declare par le blueprint, aujourd'hui le seul
    # chapitre 2 EM (calcul TAM/SAM/SOM). Il n'est cable que sur la branche a
    # UN appel : un chapitre decoupe en sections re-ecrirait son prefixe de
    # cache a chaque section, et surtout un calcul emboite ne se decoupe pas —
    # c'est precisement pourquoi le chapitre 2 a perdu ses sections (tache #9).
    # `test_blueprints_code_execution` interdit la combinaison des deux, pour
    # que le drapeau ne puisse pas etre ignore en silence.
    code_execution = bool(blueprint.code_execution) if blueprint else False

    issues: list[ChapterValidationIssue] = []
    attempts = 0
    if sections:
        content, total_input, total_output, model = _generate_chunked(
            job, chapter, sections, client=client, system_prompt=system_prompt,
            chapter_model=chapter_model, corrective_note=corrective_note,
        )
        # Chaque section a deja subi sa propre validation + retry cible dans
        # `_generate_chunked`. On revalide ici le contenu FUSIONNE : un defaut
        # peut naitre de la jonction entre deux sections (tableau ouvert dans
        # l'une, referme dans l'autre). Ce qui subsiste est trace puis repris
        # par la QA finale et le gate de livraison.
        issues = validate_chapter_content(content)
    else:
        prompt = build_chapter_prompt(chapter, corrective_note=corrective_note)
        max_tokens = max_tokens_for_job(
            job,
            default_max_tokens=_DEFAULT_MAX_TOKENS,
            validation_retries=_MAX_VALIDATION_RETRIES,
        )
        max_tokens = _plafonner_sur_cible(job, chapter, max_tokens, sections=())
        result = client.complete(
            system=system_prompt,
            prompt=prompt,
            max_tokens=max_tokens,
            model=chapter_model,
            code_execution=code_execution,
        )
        # Suivi des couts (§4 cadrage) : TOUS les appels comptent, y compris
        # les tentatives invalidees. total_* accumule chaque appel ; ne jamais
        # repartir du dernier result seul (sous-comptage constate a l'audit).
        total_input = result.input_tokens
        total_output = result.output_tokens
        # QC Evangeline #3 : validation post-gen + retry 1x si defauts bloquants.
        content = _resolve_tokens(result.content, job)
        issues = validate_chapter_content(content)
        while has_blocking_issues(issues) and attempts < _MAX_VALIDATION_RETRIES:
            attempts += 1
            corrective = format_issues_for_retry(issues)
            retry_prompt = f"{prompt}\n\n{corrective}"
            result = client.complete(
                system=system_prompt,
                prompt=retry_prompt,
                max_tokens=max_tokens,
                model=chapter_model,
                # Le retry garde l'outil : c'est le meme calcul a refaire, et
                # retirer l'outil re-ecrirait le prefixe de cache pour rien.
                code_execution=code_execution,
            )
            total_input += result.input_tokens
            total_output += result.output_tokens
            content = _resolve_tokens(result.content, job)
            issues = validate_chapter_content(content)
        model = result.model

    content = _strip_ai_tell_dashes(content)
    chapter.content = content
    chapter.operational_summary = _operational_summary(content)
    chapter.retry_count = attempts
    if issues:
        # On garde le contenu (mieux que rien) mais on trace les defauts pour QC.
        chapter.error_message = "; ".join(
            f"[{issue.severity}] {issue.code}: {issue.message}" for issue in issues
        )[:2000]
    chapter.status = ChapterStatus.DONE
    chapter.save(
        update_fields=[
            "content", "operational_summary", "retry_count",
            "error_message", "status", "updated_at",
        ]
    )

    # QC Evangeline #2 : verrouille les chiffres cles pour les chapitres suivants.
    try:
        extract_and_lock_numeric_facts(chapter)
    except CoherenceConflictError:
        # Un conflit numerique est un warning non bloquant : on l'ecrit dans
        # error_message sans FAILED (le contenu reste utilisable, mais on veut
        # etre au courant pour investiguer les prompts).
        ChapterGeneration.objects.filter(pk=chapter.pk).update(
            error_message=(chapter.error_message + " [numeric_conflict]")[:2000],
        )

    # §5 cadrage : verrouille TCAC + taille de marche au passage. Les conflits
    # sont traites comme incidents MEDIUM (non-fatals) par upsert_locked_fact.
    extract_and_lock_chiffres_cles(job, chapter.chapter_number, content)

    record_chapter_cost(
        chapter=chapter,
        input_tokens=total_input,
        output_tokens=total_output,
        model=model,
    )


# ── Hook CHECK inter-bloc (manuel Evangeline §6) ────────────────────────────
#
# Le manuel decrit une methode iterative : rediger 1-3 chapitres, lancer un
# CHECK (5 questions verbatim), et si un defaut est signale, corriger AVANT
# de continuer. On reproduit ce va-et-vient ici sans casser la boucle par
# chapitre existante : apres chaque _generate_chapter, on evalue si le
# chapitre courant termine un bloc EM, et dans ce cas on lance le CHECK
# correspondant. Si le CHECK echoue, on regenere les chapitres du bloc avec
# la note corrective, puis on relance le CHECK UNE fois. Un echec persistant
# apres retry ouvre un incident MEDIUM (non bloquant) : le contenu reste
# livre au client, mais l'admin est informe.

# Un seul retry par bloc — deuxieme regeneration + re-CHECK. Au-dela, la
# probabilite de succes chute rapidement et le cout grimpe. Comme la
# validation, on prefere loguer et continuer.
_MAX_CHECK_RETRIES = 1


def _after_chapter_hook(
    job: GenerationJob,
    chapter: ChapterGeneration,
    *,
    client: ClaudeClient,
) -> None:
    """Declenche le CHECK inter-bloc apres un chapitre EM, si applicable.

    Cas geres :
      - Chapitre 0 (fiche projet) EM -> CHECK INITIAL (6 questions, manuel p.3).
      - Dernier chapitre d'un bloc A-J EM -> CHECK correspondant.
      - Autre cas -> ne fait rien (les autres livrables et les chapitres
        intermediaires d'un bloc passent silencieusement).
    """
    if job.deliverable_type != DeliverableType.MARKET_STUDY:
        return

    # Cas 1 : fiche projet (chapitre 0) -> CHECK INITIAL, sur la fiche seule.
    # Le manuel p.3 fait porter le controle sur la fiche REDIGEE : on la passe
    # donc au relecteur comme document a valider. Sans elle, il ne voyait que
    # le brief brut et reclamait des elements deja presents dans la fiche.
    if chapter.chapter_number == 0:
        bloc = BLOCS_PAR_IDENTIFIANT.get("INITIAL")
        if bloc is not None:
            _executer_check_avec_retry(
                job, bloc, chapitres=[chapter], client=client,
            )
        return

    # Cas 2 : dernier chapitre d'un bloc A-J -> CHECK.
    bloc = bloc_pour_chapitre(chapter.chapter_number)
    if bloc is None or not bloc.chapitres:
        return
    if chapter.chapter_number != max(bloc.chapitres):
        return  # bloc encore en cours, attendre le dernier chapitre

    # Vérifier que TOUS les chapitres du bloc sont DONE avant de lancer le
    # CHECK (situation normale, mais defensif : si un retry precedent a laisse
    # un chapitre FAILED, on n'evalue pas un bloc partiel).
    chapitres_bloc = list(
        job.chapters.filter(
            chapter_number__in=bloc.chapitres, status=ChapterStatus.DONE,
        ).order_by("chapter_number")
    )
    if len(chapitres_bloc) != len(bloc.chapitres):
        return

    _executer_check_avec_retry(
        job, bloc, chapitres=chapitres_bloc, client=client,
    )


def _executer_check_avec_retry(
    job: GenerationJob,
    bloc: BlocDefinition,
    *,
    chapitres: list[ChapterGeneration],
    client: ClaudeClient,
) -> None:
    """Lance le CHECK, regenere une fois si fix, log un incident si echec persistant.

    Cas particulier du CHECK INITIAL : il est BLOQUANT.
    Manuel EVKHA p.3 (« corriger la fiche ou demander la precision necessaire
    AVANT TOUTE REDACTION ») et p.2 (« On ne continue jamais par automatisme »).
    On leve donc CheckInitialBlockedError pour stopper la generation avant le
    chapitre 1, au lieu de loguer un incident non bloquant et de continuer.
    """
    result = check_bloc(job, bloc, chapitres, client=client)

    if result.est_ok:
        return

    # Echec 1er passage : regenere chaque chapitre du bloc avec la note.
    # Le CHECK INITIAL ne se regenere pas tout seul : c'est la fiche projet —
    # donc le brief du client — qui est en cause. On ouvre un incident HIGH et
    # on STOPPE la generation (gate amont du manuel) : l'admin corrige le
    # brief/la fiche puis relance. On ne continue jamais par automatisme.
    if bloc.identifiant == "INITIAL":
        _log_incident_check(
            job, bloc, result.note_corrective,
            titre="CHECK INITIAL echoue (fiche projet a corriger) — generation stoppee",
            severity=IncidentSeverity.HIGH,
        )
        raise CheckInitialBlockedError(result.note_corrective)

    retries = 0
    while retries < _MAX_CHECK_RETRIES and not result.est_ok:
        retries += 1
        for chap in chapitres:
            regenerate_chapter(
                job, chap, corrective_note=result.note_corrective, client=client,
            )
        # Relire depuis la DB : `regenerate_chapter` a ecrit dans chapter.content.
        chapitres = list(
            job.chapters.filter(
                chapter_number__in=[c.chapter_number for c in chapitres],
                status=ChapterStatus.DONE,
            ).order_by("chapter_number")
        )
        result = check_bloc(job, bloc, chapitres, client=client)

    if not result.est_ok:
        _log_incident_check(
            job, bloc, result.note_corrective,
            titre=f"CHECK {bloc.check_numero} (bloc {bloc.identifiant}) echoue apres retry",
        )


def _log_incident_check(
    job: GenerationJob,
    bloc: BlocDefinition,
    note: str,
    *,
    titre: str,
    severity: str = IncidentSeverity.MEDIUM,
) -> None:
    """Ouvre un incident (MEDIUM par defaut).

    Pour les CHECKs inter-bloc A-J : MEDIUM, le contenu reste livre (le gate
    final decide). Pour le CHECK INITIAL bloquant : HIGH (voir appelant).
    """
    OperationalIncident.objects.create(
        title=titre[:200],
        severity=severity,
        job=job,
        order=job.order,
        details={
            # Marqueur lu par le gate de livraison : tant que cet incident est
            # OPEN, le document ne part pas (manuel p.17 « Livraison autorisee »).
            "type": INCIDENT_TYPE_CHECK_BLOC,
            "bloc": bloc.identifiant,
            "check": bloc.check_numero,
            "intitule": bloc.intitule,
            "chapitres": list(bloc.chapitres),
            "note_corrective": note[:2000],
        },
    )


def _fail(
    job: GenerationJob,
    chapter: ChapterGeneration,
    exc: Exception,
    *,
    title: str,
) -> None:
    ChapterGeneration.objects.filter(pk=chapter.pk).update(
        status=ChapterStatus.FAILED,
        error_message=str(exc),
    )
    GenerationJob.objects.filter(pk=job.pk).update(
        status=JobStatus.FAILED,
        error_message=str(exc),
    )
    OperationalIncident.objects.create(
        title=title,
        severity=IncidentSeverity.HIGH,
        job=job,
        order=job.order,
        details={"chapter_number": chapter.chapter_number, "error": str(exc)},
    )

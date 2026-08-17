"""Phase 12 — Briques structurelles du brief client (juillet 2026) + audit.

Couvre :
- Brique 1 : etat chiffre client verrouille (provenance CLIENT, priorite absolue)
- Brique 2 : hierarchie des sources dans la charte
- Brique 3 : gate de livraison bloquant (contamination, coherence chiffree,
  completude verticales, troncature) + integration tasks.py
- Correctifs audit : fuite des labels internes, encadre ACTION, em-dash des
  titres preserve, couts exacts (retry + QA IA), limite de pages, fiche projet.

## Quatre tests retires le 08/08/2026, et pourquoi

Ils exigeaient du charter des regles supprimees le 24/07/2026, a l'adoption du
manuel Evangeline. Ils portaient donc un `skip` permanent : ils ne s'executaient
ni en local ni en CI, et un test qui ne tourne jamais ne verrouille rien
(regle 1). Leur motif etait leur seule valeur — il est conserve ici.

- `test_charter_impose_hierarchie_des_sources` — la regle << HIERARCHIE DES
  SOURCES >> a disparu du charter. Le principe demeure, porte par `context.py`
  (`ROLE_LINE`), qui rappelle que DONNEES_CLIENT prime sur toute moyenne
  sectorielle. Voir `project_evkha_manuel_2026-07-24`.
- `test_charter_regles_acronymes_et_tcac_retenu` — regles ACRONYMES et
  << TCAC moyenne finale retenue >> retirees : formulations mecaniques qui
  polluaient le texte livre (constate sur WAOME v4).
- `test_charter_mentionne_le_marqueur_action` — les marqueurs parseables
  `[[UNDERSTAND]]` / `[[ACTION]]` sont retires. Les encadres se redigent
  librement selon le sens, sans gabarit rigide.
- `test_charter_em_dash_exception_titres` — la contrainte typographique
  << X.Y — Titre >> n'existe plus ; la voix EVKHA du manuel (§3) suffit.

Ce qui reste teste ici sur le charter, c'est ce que le manuel exige VRAIMENT :
voir `test_charter_interdit_les_sources_inventees`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.coherence import seed_locked_facts_from_variables, upsert_locked_fact
from generation.gate import run_delivery_gate
from generation.models import (
    ChapterStatus,
    FactKind,
    FactProvenance,
    GenerationJob,
    JobStatus,
    QAStatus,
)
from generation.rendering import (
    _md_to_html,
    normalize_callout_markers,
    strip_callout_markers,
    strip_internal_label_tokens,
)
from generation.runner import _strip_ai_tell_dashes, run_generation_job
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import ClaudeResult, StubClaudeClient
from monitoring.models import IncidentSeverity, OperationalIncident
from orders.models import Order

#: Racine du depot, deduite de l'emplacement de CE fichier et non du repertoire
#: courant. Un chemin relatif au CWD ne vaut que si pytest est lance depuis la
#: racine — sinon le test ne trouve rien, et on le fait taire au lieu de le
#: reparer. Meme convention que dans les dix autres fichiers qui lisent le
#: depot.
RACINE = Path(__file__).resolve().parents[2]


@pytest.fixture
def bp_submission() -> IntakeSubmission:
    """Business plan avec etat chiffre client complet (cas SYNAPSES du brief)."""
    offer = Offer.objects.create(
        name="Business Plan",
        slug="business-plan",
        deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    customer = Customer.objects.create(email="synapses@example.com")
    order = Order.objects.create(systeme_order_id="order_bp_1", customer=customer, offer=offer)
    return IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "coworking",
            "PAYS": "France",
            "ZONE": "Annecy",
            "PROJET": "tiers-lieu hybride SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "EMPRUNT": "920 000 €",
            # Un BP n'a un etat chiffre COMPLET que s'il porte aussi sa
            # trajectoire de CA et son resultat net : ce sont les chiffres que
            # le gate exige desormais (check `etat_chiffre_client`). La fixture
            # les omettait tout en se declarant complete — c'est exactement
            # l'angle mort qui laissait passer les dossiers reels.
            "CA_PREVISIONNEL": "250 272 € / 296 000 €",
            "RESULTAT_NET_PREVISIONNEL": "44 245 €",
            "TAUX_OCCUPATION": "55 % An1 vers 85 % An5",
            "VERTICALES": "coworking / self-storage / hébergement de serveurs / "
            "activités sportives douces",
        },
    )


def _job_with_content(
    submission: IntakeSubmission, content_by_number: dict[int, str]
) -> GenerationJob:
    """Bootstrap un job puis force le contenu de chapitres cibles en DONE."""
    job = bootstrap_generation_job(submission)
    variables = submission.normalized_variables
    seed_locked_facts_from_variables(job, variables)
    # Le check `chapitre_avorte` planche a 30 % du `max_words` du blueprint.
    # Un contenu par defaut d'une phrase suffisait avant, il fait aujourd'hui
    # tomber la fixture sous ce plancher : on repete donc la phrase pour tenir
    # les cibles de blueprints jusqu'a 1 800 mots.
    # Le check `strategy_business_plan_remuneration_dirigeant` (phase 33)
    # exige que le corpus mentionne la remuneration dirigeante avec un
    # montant chiffre. On l'integre au corps par defaut : un vrai BP doit
    # avoir cette ligne, la fixture doit donc la representer.
    corps_defaut = (
        "Analyse détaillée du projet, chiffrée et argumentée sur la zone cible. "
        "Cette section couvre coworking, self-storage, hébergement de serveurs "
        "et activités sportives douces avec des données locales précises. "
        "Le previsionnel integre une remuneration dirigeante de 30 000 EUR "
        "annuelle brute, portee a 55 000 EUR avec les cotisations sociales. "
    ) * 40
    # Le check `sources_non_tracables` (phase 36) exige que le chapitre
    # Sources contienne des URLs verifiables. Un vrai livrable les a
    # toujours ; la fixture doit donc les representer.
    corps_sources = (
        "## Marche\n"
        "- INSEE, Enquete emploi 2024 - https://www.insee.fr/fr/statistiques/1234\n"
        "- Xerfi, Etude sectorielle 2025 - https://www.xerfi.com/etude-x\n"
        "## Reglementation\n"
        "- Legifrance, art. 219 CGI - https://www.legifrance.gouv.fr/codes/id/1\n"
        "- Bpifrance - https://www.bpifrance.fr/actualites/y\n"
        "## Methodologie\n"
        "Croisement des sources sur la periode 2020-2024. Zone Hauts-de-France.\n"
    )
    from generation.blueprints import SectionKind, get_blueprint  # noqa: PLC0415
    deliverable_type = str(job.deliverable_type)
    for chapter in job.chapters.all():
        if chapter.chapter_number in content_by_number:
            body = content_by_number[chapter.chapter_number]
        else:
            bp = get_blueprint(deliverable_type, chapter.chapter_number)
            if bp is not None and bp.section_kind == SectionKind.SOURCES:
                body = corps_sources
            else:
                body = corps_defaut
        chapter.content = body
        chapter.status = ChapterStatus.DONE
        chapter.save(update_fields=["content", "status"])
    job.status = JobStatus.DONE
    job.save(update_fields=["status"])
    return job


# ── Brique 1 : provenance des faits ─────────────────────────────────────────


@pytest.mark.django_db
def test_seed_verrouille_etat_chiffre_client_en_provenance_client(
    bp_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(bp_submission)
    seed_locked_facts_from_variables(job, bp_submission.normalized_variables)

    facts = {f.key: f for f in job.coherence_facts.all()}
    assert facts["investissement_total"].value == "1 250 000 €"
    assert facts["investissement_total"].provenance == FactProvenance.CLIENT
    assert facts["emprunt"].provenance == FactProvenance.CLIENT
    assert facts["verticales"].provenance == FactProvenance.CLIENT


@pytest.mark.django_db
def test_fait_client_jamais_ecrase_par_valeur_generee(
    bp_submission: IntakeSubmission,
) -> None:
    """Le 34% hallucine ne peut plus ecraser une donnee du brief."""
    job = bootstrap_generation_job(bp_submission)
    seed_locked_facts_from_variables(job, bp_submission.normalized_variables)

    fact = upsert_locked_fact(
        job=job,
        kind=FactKind.ASSUMPTION,
        key="emprunt",
        value="300 000 €",
        source_chapter_number=15,
        provenance=FactProvenance.GENERATED,
    )
    assert fact.value == "920 000 €"  # brief conserve
    assert fact.provenance == FactProvenance.CLIENT
    # Ecart avec un fait client = incident HIGH (repris par le gate)
    incident = OperationalIncident.objects.get(title__startswith="Incoh. donnee")
    assert incident.severity == IncidentSeverity.HIGH


@pytest.mark.django_db
def test_fait_client_remplace_fait_genere_existant(
    bp_submission: IntakeSubmission,
) -> None:
    job = bootstrap_generation_job(bp_submission)
    upsert_locked_fact(
        job=job, kind=FactKind.ASSUMPTION, key="apport", value="100 000 €",
        provenance=FactProvenance.GENERATED,
    )
    fact = upsert_locked_fact(
        job=job, kind=FactKind.ASSUMPTION, key="apport", value="330 000 €",
        provenance=FactProvenance.CLIENT,
    )
    assert fact.value == "330 000 €"
    assert fact.provenance == FactProvenance.CLIENT


# ── Brique 2 : charte / hierarchie des sources ───────────────────────────────


def test_charter_interdit_les_sources_inventees() -> None:
    """Manuel §3 : « ne jamais inventer un chiffre, une source, un lien... »."""
    from generation.prompts import build_system_prompt

    prompt = build_system_prompt(DeliverableType.MARKET_STUDY)
    lower = prompt.lower()
    assert "inventer un chiffre, une source" in lower or "jamais inventer" in lower
    # Verbatim manuel : distinguer donnee observee / estimation / projection.
    assert "estimation" in lower


# ── Brique 3 : gate de livraison ─────────────────────────────────────────────


@pytest.mark.django_db
def test_gate_passe_sur_document_sain(bp_submission: IntakeSubmission) -> None:
    job = _job_with_content(bp_submission, {})
    report = run_delivery_gate(job)
    assert report.passed, report.as_details()


@pytest.mark.django_db
def test_gate_bloque_la_fuite_faits_verrouilles(bp_submission: IntakeSubmission) -> None:
    """Cas reel du brief : 'en parfaite coherence avec les FAITS_VERROUILLES'.

    Le Rendering Engine neutralise la fuite pour le client, mais le gate scanne
    aussi le contenu BRUT (audit juillet 2026, cause 4) : la fuite est donc
    detectee et bloquante. Auparavant le check n'operait que sur le texte
    nettoye, avec la meme liste de tokens que le nettoyeur qui venait de les
    effacer — il ne pouvait mathematiquement jamais echouer, et le signal que
    le modele confond contexte interne et redaction etait perdu.
    """
    job = _job_with_content(
        bp_submission,
        {15: "Le résultat net est en parfaite cohérence avec les FAITS_VERROUILLES. "
             "Analyse complète du prévisionnel sur la zone, coworking, self-storage, "
             "hébergement de serveurs et activités sportives douces inclus."},
    )
    report = run_delivery_gate(job)
    # La fuite est neutralisee pour le client MAIS detectee dans le brut :
    # le chapitre doit etre regenere, pas simplement reecrit en silence.
    assert not report.passed
    assert any(f.check == "contamination" for f in report.failures)

    job2_offer = Offer.objects.create(
        name="BP 2", slug="bp-2", deliverable_type=DeliverableType.BUSINESS_PLAN
    )
    customer = Customer.objects.get(email="synapses@example.com")
    order2 = Order.objects.create(
        systeme_order_id="order_bp_2", customer=customer, offer=job2_offer
    )
    submission2 = IntakeSubmission.objects.create(
        order=order2,
        status=IntakeStatus.NORMALIZED,
        normalized_variables=bp_submission.normalized_variables,
    )
    job2 = _job_with_content(
        submission2,
        {15: "Section à compléter TODO avant livraison. Analyse coworking, "
             "self-storage, hébergement de serveurs, activités sportives douces."},
    )
    report2 = run_delivery_gate(job2)
    assert not report2.passed
    assert any(f.check == "contamination" for f in report2.failures)


@pytest.mark.django_db
def test_gate_bloque_incoherence_chiffree_vs_brief(bp_submission: IntakeSubmission) -> None:
    """Cas reel du brief : emprunt 920 000 € remplace par 300 000 € (÷3)."""
    job = _job_with_content(
        bp_submission,
        {14: "Le financement repose sur un emprunt de 300 000 € sur 7 ans. "
             "Le projet couvre coworking, self-storage, hébergement de serveurs "
             "et activités sportives douces sur la zone d'Annecy."},
    )
    report = run_delivery_gate(job)
    assert not report.passed
    assert any(
        f.check == "coherence_chiffree" and "emprunt" in f.detail for f in report.failures
    )


@pytest.mark.django_db
def test_gate_accepte_trajectoire_dans_fourchette_client(
    bp_submission: IntakeSubmission,
) -> None:
    """Brief multi-annees (55% -> 85%) : une valeur intermediaire est valide."""
    job = _job_with_content(
        bp_submission,
        {14: "Le taux d'occupation de 70 % en année 3 reste conforme à la "
             "trajectoire du porteur. Coworking, self-storage, hébergement de "
             "serveurs et activités sportives douces contribuent à la montée."},
    )
    report = run_delivery_gate(job)
    assert all(f.check != "coherence_chiffree" for f in report.failures), report.as_details()


@pytest.mark.django_db
def test_gate_bloque_taux_hors_fourchette(bp_submission: IntakeSubmission) -> None:
    """Cas reel du brief : '62 % moyenne sectorielle' substitue a la trajectoire."""
    job = _job_with_content(
        bp_submission,
        {14: "Nous retenons un taux d'occupation de 42 % conforme à la moyenne "
             "sectorielle. Coworking, self-storage, hébergement de serveurs et "
             "activités sportives douces sont analysés."},
    )
    report = run_delivery_gate(job)
    assert not report.passed
    assert any(f.check == "coherence_chiffree" for f in report.failures)


@pytest.mark.django_db
def test_gate_bloque_verticale_effacee(bp_submission: IntakeSubmission) -> None:
    """Cas reel du brief : self-storage / serveurs / sport purement effaces."""
    generic = (
        "Le coworking générique répond à la demande locale avec une offre "
        "de bureaux flexibles et de salles de réunion sur Annecy."
    )
    # La plage vient du BLUEPRINT, jamais d'un nombre recopié. Écrite
    # `range(0, 20)`, elle laissait sans contenu les chapitres ajoutés au
    # retour aux vingt chapitres du document : le corpus n'était plus
    # entièrement générique, et le contrôle des verticales n'avait plus le cas
    # qu'on prétendait lui soumettre.
    from generation.blueprints import chapters_for_deliverable

    tous = [c.number for c in chapters_for_deliverable(str(DeliverableType.BUSINESS_PLAN))]
    job = _job_with_content(bp_submission, dict.fromkeys(tous, generic))
    report = run_delivery_gate(job)
    assert not report.passed
    missing = [f.detail for f in report.failures if f.check == "verticales"]
    assert any("self-storage" in d for d in missing)
    assert any("serveurs" in d for d in missing)


@pytest.mark.django_db
def test_gate_bloque_troncature(bp_submission: IntakeSubmission) -> None:
    """Cas reel du brief : chapitre 18 tronque en pleine phrase."""
    job = _job_with_content(
        bp_submission,
        {16: "L'analyse des risques montre que le projet coworking, self-storage, "
             "hébergement de serveurs et activités sportives douces dépend de"},
    )
    report = run_delivery_gate(job)
    assert not report.passed
    assert any(f.check == "troncature" for f in report.failures)


@pytest.mark.django_db
def test_task_livre_et_trace_si_le_gate_ne_passe_pas(
    bp_submission: IntakeSubmission, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Integration tasks.py : gate KO -> qa BLOCKED + incident + PAS d'email."""
    from delivery.models import DeliveryBatch
    from generation import correction as correction_mod
    from generation import tasks as generation_tasks
    from generation.gate import GateFailure, GateReport

    job = bootstrap_generation_job(bp_submission)
    run_generation_job(job, client=StubClaudeClient())

    monkeypatch.setattr(
        generation_tasks, "run_generation_job", lambda j, **kw: j
    )

    def _failing_gate(_job: object) -> GateReport:
        return GateReport(
            passed=False,
            failures=(GateFailure(check="contamination", detail="TOKEN test"),),
        )

    # La boucle d'auto-correction résout gate.run_delivery_gate à l'exécution :
    # patcher le module gate suffit (aucun binding périmé).
    import generation.gate as gate_module
    monkeypatch.setattr(gate_module, "run_delivery_gate", _failing_gate)
    # Aucune régénération réelle : rondes forcées à 0 (le gate KO doit bloquer).
    monkeypatch.setattr(correction_mod, "_default_rounds", lambda: 0)

    generation_tasks.run_generation_job_task(str(job.id))
    job.refresh_from_db()

    # LE DOCUMENT PART QUAND MÊME depuis le 13/08/2026 — décision cliente :
    # « l'envoi du document doit être auto et sans aucune action de ma part ».
    #
    # Sur les quatre motifs qu'elle a relevés ce jour-là, TROIS étaient faux :
    # un identifiant refusé alors que notre propre consigne demande de
    # l'écrire, un mot de son métier pris pour du jargon interne, un titre en
    # gras compté comme phrase tronquée. Retenir un livrable payé sur des
    # motifs que nous inventons, puis lui demander de trancher, revenait à lui
    # faire porter nos défauts.
    #
    # Ce que ce test garde : la TRACE. L'incident reste, en HIGH, et le statut
    # reste BLOCKED — ce qui n'a pas pu être fermé doit se voir. Seule l'attente
    # disparaît.
    assert job.qa_status == QAStatus.BLOCKED
    assert OperationalIncident.objects.filter(
        title__startswith="Gate qualité", job=job
    ).exists()
    assert DeliveryBatch.objects.filter(order=job.order).exists(), (
        "le document doit partir malgré les points non résolus"
    )


@pytest.mark.django_db
def test_task_livre_si_gate_passe() -> None:
    """Brief sans etat chiffre ni verticales : le contenu stub passe le gate."""
    from generation.tasks import run_generation_job_task

    offer = Offer.objects.create(
        name="EM simple", slug="em-simple", deliverable_type=DeliverableType.MARKET_STUDY
    )
    customer = Customer.objects.create(email="simple@example.com")
    order = Order.objects.create(
        systeme_order_id="order_em_simple", customer=customer, offer=offer
    )
    submission = IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "beaute", "PAYS": "Benin", "ZONE": "Cotonou", "PROJET": "concept store",
        },
    )
    job = bootstrap_generation_job(submission)
    run_generation_job(job, client=StubClaudeClient())
    run_generation_job_task(str(job.id))
    job.refresh_from_db()
    assert job.qa_status != QAStatus.BLOCKED


# ── Contamination : scrub des labels internes ────────────────────────────────


def test_strip_internal_label_tokens_forme_parenthesee() -> None:
    raw = "le résultat net inscrit dans le prévisionnel de référence (FAITS_VERROUILLES) correspond"
    out = strip_internal_label_tokens(raw)
    assert "FAITS_VERROUILLES" not in out
    assert "prévisionnel de référence" in out


def test_strip_internal_label_tokens_forme_nue_sans_doublon_article() -> None:
    raw = "en parfaite cohérence avec les FAITS_VERROUILLES."
    out = strip_internal_label_tokens(raw)
    assert "FAITS_VERROUILLES" not in out
    assert "les les" not in out
    assert "données de référence du dossier" in out


def test_validation_detecte_label_interne() -> None:
    from generation.validation import detect_placeholder_leaks

    issues = detect_placeholder_leaks("conforme aux FAITS_VERROUILLES du dossier")
    assert any(i.code == "leaked_internal_label" for i in issues)


# ── Encadre ACTION (4e style, Bloc 4 Consignes) ─────────────────────────────


def test_callout_action_bloc_est_rendu() -> None:
    html = _md_to_html("[[ACTION]]\nMois 1 : valider 10 prospects.\n[[/ACTION]]")
    assert "callout--action" in html
    assert "Action concrète" in html


def test_callout_action_inline_est_rendu() -> None:
    html = _md_to_html("✓ Action concrète : appeler 5 clients cette semaine.")
    assert "callout--action" in html


def test_marqueurs_colles_sont_normalises_puis_rendus() -> None:
    raw = "Constat.[[UNDERSTAND]]Le marché croît.[[/UNDERSTAND]]Suite."
    html = _md_to_html(normalize_callout_markers(raw))
    assert "callout--understand" in html
    assert "[[" not in strip_callout_markers(html)


def test_template_definit_le_style_action() -> None:
    """Le gabarit porte le style des encadres ACTION, et UNE seule regle de tableau.

    Ce test a saute pendant des mois : il localisait le gabarit par un chemin
    relatif au repertoire courant, qui ne vaut que si pytest est lance depuis la
    racine. Le `skip` posé dessus a rendu le gabarit de rendu — ce que le client
    lit reellement — invisible à toute la suite. Un test qui saute ne verrouille
    rien (regle 1). Le chemin part desormais du fichier de test lui-meme.

    La regle de tableau est comptee : deux declarations `.chapter__body table {`
    se surchargeraient en silence, et c'est la derniere lue qui gagnerait.
    """
    gabarit = (
        RACINE / "backend/generation/templates/generation/document.html"
    ).read_text(encoding="utf-8")

    assert "callout--action" in gabarit
    assert gabarit.count(".chapter__body table {") == 1


# ── Em-dash : titres preserves, prose nettoyee ──────────────────────────────


def test_em_dash_conserve_dans_les_titres() -> None:
    content = "### 3.1 — Segmentation du marché\nLe marché — en croissance — progresse."
    out = _strip_ai_tell_dashes(content)
    assert "3.1 — Segmentation" in out
    assert "marché, en croissance, progresse" in out


# ── Couts exacts : retry + QA IA comptabilises ──────────────────────────────


class _RetryThenGoodClient:
    """1er appel : tableau vide (defaut bloquant) ; 2e appel : contenu valide."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, *, system: str, prompt: str, max_tokens: int = 8192,
                 model: str | None = None, advisor: bool = False,
                 code_execution: bool = False) -> ClaudeResult:
        self.calls += 1
        if self.calls == 1:
            content = "| A | B |\n|---|---|\n| — | — |\n| — | — |"
        else:
            content = ("Analyse substantielle. " * 60).strip() + "."
        return ClaudeResult(
            content=content, input_tokens=100, output_tokens=50, model="claude-sonnet"
        )


@pytest.mark.django_db
def test_retry_validation_accumule_les_tokens(bp_submission: IntakeSubmission) -> None:
    from generation.runner import _generate_chapter

    job = bootstrap_generation_job(bp_submission)
    chapter = job.chapters.get(chapter_number=3)  # non chunke
    client = _RetryThenGoodClient()
    _generate_chapter(job, chapter, client=client, system_prompt="sys")
    chapter.refresh_from_db()

    assert client.calls == 2
    assert chapter.input_tokens == 200   # 100 + 100 (les 2 appels comptent)
    assert chapter.output_tokens == 100  # 50 + 50


@pytest.mark.django_db
def test_qa_ai_repair_est_comptabilise_et_contextualise(
    bp_submission: IntakeSubmission,
) -> None:
    from generation.qa import ConditionViolation, ai_repair_chapter

    content, tin, tout = ai_repair_chapter(
        "contenu court",
        "Chapitre test",
        "chapter",
        [ConditionViolation("below_min_length", "critical", "50 mots < 400")],
        client=object(),  # pas un ClaudeClient -> aucun appel, tokens nuls
        project_context="CONTEXTE PROJET : secteur coworking",
    )
    assert (content, tin, tout) == ("contenu court", 0, 0)


# ── Limite de pages (§2 cadrage : 80/45 max) ────────────────────────────────


@pytest.mark.django_db
def test_depassement_pages_ouvre_un_incident(bp_submission: IntakeSubmission) -> None:
    from documents.services import _check_page_limit

    job = bootstrap_generation_job(bp_submission)
    _check_page_limit(job, page_count=95)  # BP : limite 80
    incident = OperationalIncident.objects.get(title__startswith="Limite de pages")
    assert incident.details["pages"] == 95
    assert incident.details["limite"] == 80


@pytest.mark.django_db
def test_pages_sous_la_limite_aucun_incident(bp_submission: IntakeSubmission) -> None:
    from documents.services import _check_page_limit

    job = bootstrap_generation_job(bp_submission)
    _check_page_limit(job, page_count=76)
    assert not OperationalIncident.objects.filter(
        title__startswith="Limite de pages"
    ).exists()


# ── Fiche projet : ligne d'en-tete explicite ────────────────────────────────


def test_fiche_projet_prompts_ont_une_ligne_entete() -> None:
    """La fiche projet ouvre par un tableau Markdown a 2 colonnes.

    Le 24/07/2026 (manuel Evangeline §2), la fiche EM utilise l'entete
    « | Rubrique | Contenu | » avec 10 rubriques prescrites. EC/BP/STR
    conservent l'ancien format « | Élément | Détail | » (le manuel ne
    les couvre pas). Le test accepte les deux.
    """
    from generation.prompt_library import prompt_instruction

    entetes_valides = ("| Élément | Détail |", "| Rubrique | Contenu |")
    for key in ("em.00.fiche_projet", "ec.00.fiche_projet",
                "bp.00.fiche_projet", "str.00.fiche_projet"):
        instruction = prompt_instruction(key)
        assert any(e in instruction for e in entetes_valides), (
            f"{key} : aucun entete de tableau reconnu ({entetes_valides})"
        )


# ── Intake : etat chiffre client + verticales ───────────────────────────────


def test_intake_expose_les_variables_etat_chiffre() -> None:
    from intake.services import _ALIASES, OPTIONAL_VARIABLES

    for var in ("INVESTISSEMENT_TOTAL", "EMPRUNT", "APPORT", "TAUX_OCCUPATION",
                "SEUIL_RENTABILITE", "VERTICALES"):
        assert var in OPTIONAL_VARIABLES
    assert _ALIASES["investissement total"] == "INVESTISSEMENT_TOTAL"
    assert _ALIASES["verticales d'activite"] == "VERTICALES"

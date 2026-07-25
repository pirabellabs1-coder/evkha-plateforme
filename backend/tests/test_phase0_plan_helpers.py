"""Verrous de comportement sur les helpers Phase 0 et le slice de previous_context.

Ces tests protègent contre les régressions identifiées lors de la review high effort :
- `_var` doit gérer les valeurs list-valued que Tally peut envoyer (multi-select)
- `_build_phase0_plan` doit rester court (~300 chars) pour ne pas exploser le budget
- `_build_phase0_plan` ne doit PAS lister les concurrents (déjà dans VARIABLES_PROJET)
- `_build_phase0_plan` ne doit PAS contredire la règle "sélectionne les 8 plus
  pertinents" de ec.01.identification
- `build_section_prompt(previous_context=...)` doit tail-slicer (garder la fin)
"""

from __future__ import annotations

from typing import cast

import pytest

from generation.models import GenerationJob
from generation.runner import _build_phase0_plan, _var


def test_var_returns_empty_when_key_missing() -> None:
    assert _var({}, "CONCURRENTS") == ""


def test_var_returns_stripped_string_value() -> None:
    assert _var({"CONCURRENTS": "  Nike, Adidas  "}, "CONCURRENTS") == "Nike, Adidas"


def test_var_joins_list_valued_multi_select_from_tally() -> None:
    # Tally peut envoyer un champ multi-select comme list. intake/services.py
    # ne coerce PAS en str — le runner doit gérer nativement.
    assert _var({"CONCURRENTS": ["Nike", "Adidas", "Puma"]}, "CONCURRENTS") == "Nike, Adidas, Puma"


def test_var_ignores_none_and_empty_list_entries() -> None:
    assert _var({"CONCURRENTS": ["", "Nike", "  ", "Adidas"]}, "CONCURRENTS") == "Nike, Adidas"


def test_var_handles_none_value() -> None:
    assert _var({"CONCURRENTS": None}, "CONCURRENTS") == ""


class _FakeJob:
    """Doublure minimale : `_build_phase0_plan` ne lit que ce champ.

    Caste en GenerationJob a l'appel (cf. `_job`) : monter un vrai job
    en base pour lire un seul attribut couterait un acces DB par test
    sans rien verifier de plus.
    """

    def __init__(self, deliverable_type: str = "market_study") -> None:
        self.deliverable_type = deliverable_type


def _job(deliverable_type: str = "market_study") -> GenerationJob:
    return cast("GenerationJob", _FakeJob(deliverable_type))


def test_phase0_plan_empty_when_no_client_brief() -> None:
    # Aucune donnée client → aucun bloc à ajouter au system prompt.
    # Coût token = 0 sur les runs sans brief.
    assert _build_phase0_plan(_job(), {}) == ""


def test_phase0_plan_present_when_any_brief_field_set() -> None:
    plan = _build_phase0_plan(_job(), {"CONCURRENTS": "Nike, Adidas"})
    assert plan  # non vide
    # Pointe vers le user prompt (VARIABLES_PROJET), ne recopie pas le brief.
    assert "VARIABLES_PROJET" in plan


def test_phase0_plan_stays_short_to_protect_budget() -> None:
    # Le plan est envoyé dans le system prompt de chaque appel Claude (~30
    # appels pour EM). Grâce au prompt caching Anthropic (cache_control:
    # ephemeral), le coût réel n'est payé qu'une fois par job. Mais on garde
    # une limite raisonnable pour éviter la dérive : 800 chars.
    plan = _build_phase0_plan(
        _job(),
        {
            "CONCURRENTS": "Nike, Adidas, Puma, Under Armour, Reebok",
            "DEMANDES_SPECIFIQUES": "focus sur le marché africain, angle prix bas",
            "ELEMENTS_A_RETENIR": "PME familiale, capital 50k€, 2 associés",
        },
    )
    assert len(plan) < 800, f"plan trop long ({len(plan)} chars) — dérive budget"


def test_phase0_plan_does_not_list_concurrents_verbatim() -> None:
    # Régression : l'ancien plan listait "1. Nike\n 2. Adidas..." dans le
    # system prompt avec "RÈGLE ABSOLUE traiter les N dans l'ordre exact".
    # Ceci contredisait ec.01.identification ("sélectionne les 8 plus pertinents")
    # et gaspillait des tokens. Le nouveau plan doit rester générique.
    plan = _build_phase0_plan(_job(), {"CONCURRENTS": "Nike, Adidas, Puma"})
    assert "Nike" not in plan
    assert "Adidas" not in plan
    assert "ordre exact" not in plan.lower()


def test_phase0_plan_does_not_mention_forbidden_absolute_order_rule() -> None:
    # La règle "traiter les N dans l'ordre exact" contredit ec.01. Bannie.
    # NOTE : "verrouillé" est autorisé UNIQUEMENT dans le titre "PLAN VERROUILLÉ"
    # (aucun sens contradictoire). Seules les formulations qui *contraignent
    # l'ordre* ou *interdisent la sélection* sont bannies.
    plan = _build_phase0_plan(
        _job(),
        {"CONCURRENTS": "Nike, Adidas", "DEMANDES_SPECIFIQUES": "x"},
    )
    forbidden = [
        "dans cet ordre exact",
        "aucun remplacement",
        "aucun oubli",
        "aucune omission",
        "traiter les {",  # ancienne interpolation "traiter les {N}"
    ]
    for f in forbidden:
        assert f not in plan.lower(), f"règle contradictoire présente : {f!r}"


@pytest.mark.django_db
def test_build_section_prompt_tail_slices_previous_context() -> None:
    # Régression : `[:4000]` gardait le DÉBUT du contexte accumulé — section 3
    # ne voyait jamais la fin de section 2 (celle qu'elle risque de répéter).
    # Fix : `[-4000:]` garde la FIN, adjacente à la nouvelle section.
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import ChapterGeneration, GenerationJob
    from generation.prompts import build_section_prompt
    from intake.models import IntakeStatus, IntakeSubmission
    from orders.models import Order

    offer = Offer.objects.create(
        name="EM test", slug="em-test", deliverable_type=DeliverableType.MARKET_STUDY
    )
    customer = Customer.objects.create(email="a@b.c")
    order = Order.objects.create(systeme_order_id="o1", customer=customer, offer=offer)
    IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "x", "PAYS": "FR", "PROJET": "y", "ZONE": "z"},
    )
    job = GenerationJob.objects.create(
        order=order, deliverable_type=DeliverableType.MARKET_STUDY
    )
    chapter = ChapterGeneration.objects.create(
        job=job,
        chapter_number=1,
        chapter_title="Analyse marché mondial et européen",
        prompt_key="em.01.marche_mondial_europeen",
    )

    # Contexte accumulé de 5000 chars : DEBUT (0-4000) vs FIN (1000-5000).
    marker_start = "DEBUT_MARKER_UNIQUE"
    marker_end = "FIN_MARKER_UNIQUE"
    previous = marker_start + ("x" * 4970) + marker_end  # total 5000 chars

    prompt = build_section_prompt(chapter, "em.01.a.mondial", previous_context=previous)

    # Le marker de fin doit être présent (tail-slice), pas celui du début.
    assert marker_end in prompt, "tail-slice cassé : FIN absente du prompt"
    assert marker_start not in prompt, (
        "tail-slice cassé : DEBUT présent (slice [:] au lieu de [-:])"
    )


def test_strip_ai_tell_dashes_removes_em_and_en_dashes() -> None:
    # Regression : Claude glisse regulierement des em-dash (—) et en-dash (–)
    # dans le corps du texte malgre la consigne INTERDICTIONS ABSOLUES.
    # Les lecteurs professionnels les reperent instantanement comme signatures
    # IA. Le sanitiseur post-processing doit les eliminer sans exception.
    from generation.runner import _strip_ai_tell_dashes

    # Cas classique : parenthetique avec espaces autour
    assert (
        _strip_ai_tell_dashes("un pari fort — et un pari qui repose sur X")
        == "un pari fort, et un pari qui repose sur X"
    )
    # En-dash aussi
    assert _strip_ai_tell_dashes("un texte – suite") == "un texte, suite"
    # Sans espace autour (rare mais possible)
    assert _strip_ai_tell_dashes("mot—autre mot") == "mot, autre mot"
    # Tiret court preserve (mots composes)
    assert _strip_ai_tell_dashes("self-stockage et ordre-du-jour") == (
        "self-stockage et ordre-du-jour"
    )
    # Idempotent
    already_clean = "texte sans tiret long, propre."
    assert _strip_ai_tell_dashes(already_clean) == already_clean


def test_strip_ai_tell_dashes_preserve_les_fourchettes_chiffrees() -> None:
    # Regression run reel 010e3bf2 (chapitre 2) : la substitution aveugle par
    # ", " transformait « 100 — 120 kEUR » en « 100, 120 kEUR ». Dans un tableau
    # financier la fourchette devenait illisible, et le relecteur y lisait une
    # erreur de calcul. Une fourchette chiffree doit garder sa borne en clair.
    from generation.runner import _strip_ai_tell_dashes

    assert _strip_ai_tell_dashes("SOM : 100 — 120 kEUR") == "SOM : 100 à 120 kEUR"
    assert _strip_ai_tell_dashes("CA 7,0 – 7,5 MEUR") == "CA 7,0 à 7,5 MEUR"
    assert _strip_ai_tell_dashes("horizon 2026–2030") == "horizon 2026 à 2030"
    # Cellule de tableau reduite au tiret : convention « sans objet », preservee.
    assert _strip_ai_tell_dashes("<td>90 MEUR</td><td>—</td>") == (
        "<td>90 MEUR</td><td>—</td>"
    )
    assert _strip_ai_tell_dashes("| Part de capture | — |") == (
        "| Part de capture | — |"
    )
    # La prose reste traitee : le tiret parenthetique disparait toujours.
    assert _strip_ai_tell_dashes("un marche jeune — donc volatil") == (
        "un marche jeune, donc volatil"
    )

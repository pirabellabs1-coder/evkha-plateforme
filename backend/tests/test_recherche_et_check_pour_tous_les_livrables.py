"""La recherche ciblee et le CHECK INITIAL cessent d'etre un privilege de l'EM.

Etapes 4-5 du plan de migration (06/08/2026). Trois defauts de la meme
famille — du traitement ecrit pour l'etude de marche et jamais generalise
(regle 4) :

1. le business plan et la strategie n'avaient que TROIS axes de recherche non
   cibles, contre dix-huit cibles pour l'EM : chaque chapitre recevait les
   memes extraits, cause mecanique des redites ;
2. `_CHAPITRE_DES_SOURCES` valait `21` en dur — juste pour l'EM, juste par
   coincidence pour le BP, FAUX pour la strategie (20) et la concurrentielle
   (9) : leur bibliographie recevait un brief filtre, donc amputee des sources
   sans section dediee ;
3. le CHECK INITIAL ne tournait que sur l'EM : les trois autres livrables
   payaient leurs vingt chapitres sur une fiche que personne n'avait relue
   (lecon 07745d4a).

Et le corollaire de la lecon 07745d4a : un CHECK qui exige ce que la fiche ne
demande pas est une impasse. Les fiches bp.00, str.00 et ec.00 demandent
desormais devise, lecteur final et points non specifies — comme em.00.
"""
from __future__ import annotations

from typing import Any, cast

import pytest

from catalog.models import DeliverableType
from generation.research import _chapitre_des_sources, axes_pour, brief_pour_chapitre

pytestmark = pytest.mark.django_db


# ── 1. Axes cibles ───────────────────────────────────────────────────────────


def test_le_bp_et_la_strategie_ont_des_axes_cibles() -> None:
    """Trois axes non cibles arrosaient tous les chapitres des memes extraits."""
    bp = axes_pour(DeliverableType.BUSINESS_PLAN)
    strategie = axes_pour(DeliverableType.BUSINESS_STRATEGY)

    assert len(bp) >= 13
    assert len(strategie) >= 10
    # Cibles : la majorite des axes designent leurs chapitres.
    assert sum(1 for a in bp if a.chapitres) >= 11
    assert sum(1 for a in strategie if a.chapitres) >= 8


def test_les_axes_bp_visent_des_chapitres_du_plan_bp() -> None:
    """Un axe qui vise le chapitre 25 d'un plan de 22 nourrit personne."""
    from generation.blueprints import chapters_for_deliverable

    numeros = {c.number for c in chapters_for_deliverable(DeliverableType.BUSINESS_PLAN)}
    for axe in axes_pour(DeliverableType.BUSINESS_PLAN):
        for chapitre in axe.chapitres:
            assert chapitre in numeros, (axe.cle, chapitre)


def test_les_axes_strategie_visent_des_chapitres_du_plan_strategie() -> None:
    from generation.blueprints import chapters_for_deliverable

    numeros = {
        c.number
        for c in chapters_for_deliverable(DeliverableType.BUSINESS_STRATEGY)
    }
    for axe in axes_pour(DeliverableType.BUSINESS_STRATEGY):
        for chapitre in axe.chapitres:
            assert chapitre in numeros, (axe.cle, chapitre)


# ── 2. Le chapitre des sources vient du plan ─────────────────────────────────


@pytest.mark.parametrize(
    "livrable,attendu",
    [
        (DeliverableType.MARKET_STUDY, 21),
        (DeliverableType.BUSINESS_PLAN, 21),
        (DeliverableType.BUSINESS_STRATEGY, 20),
        (DeliverableType.COMPETITOR_STUDY, 9),
    ],
)
def test_le_chapitre_des_sources_est_lu_du_plan(livrable: str, attendu: int) -> None:
    """`21` en dur etait juste pour l'EM, faux pour la STR (20) et l'EC (9)."""
    assert _chapitre_des_sources(livrable) == attendu


def test_la_bibliographie_de_la_strategie_recoit_le_brief_entier() -> None:
    """LE test de la constante en dur. Sur le code d'avant, il tombe.

    Le chapitre 20 d'une strategie est sa bibliographie. Avec `21` en dur, il
    passait par le filtre comme un chapitre ordinaire : les axes sans section
    dediee au chapitre 20 disparaissaient, et la bibliographie taisait des
    sources reellement employees.
    """
    brief = (
        "En-tete commun.\n\n"
        "### AXE tendances [chapitres: 2, 6]\nSource sur les tendances.\n\n"
        "### AXE pricing [chapitres: 10]\nSource sur les prix."
    )

    entier = brief_pour_chapitre(brief, 20, DeliverableType.BUSINESS_STRATEGY)

    assert "tendances" in entier
    assert "pricing" in entier


def test_un_chapitre_ordinaire_de_strategie_reste_filtre() -> None:
    """CONTRE-EPREUVE : deriver le numero ne desactive pas le filtrage."""
    brief = (
        "En-tete commun.\n\n"
        "### AXE tendances [chapitres: 2, 6]\nSource sur les tendances.\n\n"
        "### AXE pricing [chapitres: 10]\nSource sur les prix."
    )

    filtre = brief_pour_chapitre(brief, 10, DeliverableType.BUSINESS_STRATEGY)

    assert "pricing" in filtre
    assert "Source sur les tendances" not in filtre


# ── 3. Le CHECK INITIAL tourne sur les quatre fiches ─────────────────────────


def _job(livrable: str) -> Any:
    from decimal import Decimal

    from catalog.models import Offer
    from customers.models import Customer
    from generation.models import ChapterGeneration, ChapterStatus, GenerationJob
    from orders.models import Order

    offre, _ = Offer.objects.get_or_create(
        slug=f"check-{livrable}", defaults={"name": livrable, "deliverable_type": livrable},
    )
    contact = Customer.objects.create(email=f"{livrable}@test.local")
    commande = Order.objects.create(
        systeme_order_id=f"cmd-check-{livrable}", customer=contact, offer=offre,
    )
    job = GenerationJob.objects.create(
        order=commande, deliverable_type=livrable, budget_eur=Decimal("4.00"),
    )
    ChapterGeneration.objects.create(
        job=job, chapter_number=0, chapter_title="Fiche projet",
        prompt_key="x.00.fiche", status=ChapterStatus.DONE,
        content="| Rubrique | Contenu |\n|---|---|\n| Projet | Test |",
    )
    return job


@pytest.mark.parametrize(
    "livrable",
    [
        DeliverableType.MARKET_STUDY,
        DeliverableType.BUSINESS_PLAN,
        DeliverableType.BUSINESS_STRATEGY,
        DeliverableType.COMPETITOR_STUDY,
    ],
)
def test_le_check_initial_tourne_sur_la_fiche_de_chaque_livrable(
    livrable: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sur le code d'avant, seule l'EM declenchait le CHECK : les trois autres
    payaient leurs chapitres sur une fiche que personne n'avait relue.

    On intercepte l'execution du CHECK plutot que d'appeler le modele : ce qui
    se verifie ici est le DECLENCHEMENT, pas le verdict du relecteur.
    """
    from generation import runner as module_runner

    declenches: list[str] = []

    def faux_check(job: Any, bloc: Any, **kwargs: Any) -> None:
        declenches.append(bloc.identifiant)

    monkeypatch.setattr(module_runner, "_executer_check_avec_retry", faux_check)

    job = _job(livrable)
    chapitre = job.chapters.get(chapter_number=0)
    # Le client n'est jamais touche : le faux CHECK intercepte l'appel en
    # amont. `cast` plutot que `type: ignore` — il documente l'intention.
    module_runner._after_chapter_hook(
        job, chapitre, client=cast("Any", object())
    )

    assert declenches == ["INITIAL"], livrable


def test_les_checks_de_blocs_restent_reserves_a_l_em(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRE-EPREUVE : etendre le CHECK INITIAL n'etend pas les blocs A-J.

    Leurs numeros de chapitres sont ceux du plan EM ; les appliquer a un
    business plan comparerait des chapitres qui n'existent pas.
    """
    from generation import runner as module_runner
    from generation.models import ChapterGeneration, ChapterStatus

    declenches: list[str] = []
    monkeypatch.setattr(
        module_runner, "_executer_check_avec_retry",
        lambda job, bloc, **kwargs: declenches.append(bloc.identifiant),
    )

    job = _job(DeliverableType.BUSINESS_PLAN)
    ChapterGeneration.objects.create(
        job=job, chapter_number=2, chapter_title="Chapitre 2",
        prompt_key="bp.02.x", status=ChapterStatus.DONE,
        content="Contenu.",
    )
    chapitre = job.chapters.get(chapter_number=2)
    # Le client n'est jamais touche : le faux CHECK intercepte l'appel en
    # amont. `cast` plutot que `type: ignore` — il documente l'intention.
    module_runner._after_chapter_hook(
        job, chapitre, client=cast("Any", object())
    )

    assert declenches == []


# ── 4. Les fiches demandent ce que le relecteur exigera ──────────────────────


@pytest.mark.parametrize(
    "fichier",
    [
        "prompts/etude_marche/chapitre_00.md",
        "prompts/business_plan/chapitre_00.md",
        "prompts/strategie_business/chapitre_00.md",
        "prompts/etude_concurrence/chapitre_00.md",
    ],
)
def test_chaque_fiche_demande_ce_que_le_check_exige(fichier: str) -> None:
    """La mort du job 07745d4a : un CHECK qui exigeait des rubriques que la
    fiche ne demandait pas. Le relecteur reclamait, le redacteur ne pouvait pas
    fournir, l'etude mourait en boucle de reprise.

    Etendre le CHECK aux quatre livrables sans etendre leurs fiches aurait
    rejoue exactement ce defaut sur chaque premier BP.
    """
    from pathlib import Path

    racine = Path(__file__).resolve().parents[2]
    contenu = (racine / fichier).read_text(encoding="utf-8")

    assert "Devise" in contenu, fichier
    assert "Lecteur final" in contenu, fichier
    assert "non specifies" in contenu.replace("é", "e"), fichier

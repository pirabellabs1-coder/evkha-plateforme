"""Tache #12 — outil advisor sur les CHECKs + cout des CHECKs enfin compte.

Deux sujets, un seul fil : rendre le relecteur plus exigeant sans rendre la
depense invisible.

1. Outil advisor (doc « Outil advisor », mars 2026). Executeur ET conseiller
   sont claude-sonnet-4-6 : la doc autorise cette paire (« les modeles de
   capacite egale peuvent se conseiller mutuellement »), et l'egalite de modele
   est ce qui garde le Cost Engine juste — un seul tarif s'applique.
   Le tableau de compatibilite exclut deux auto-paires : claude-haiku-4-5
   (jamais advisor) et claude-sonnet-5 (sa propre liste d'advisors ne le
   contient pas). Emettre l'une des deux = 400 invalid_request_error.
2. `usage.iterations[]`. La doc est explicite : « Les champs `usage` de niveau
   superieur ne refletent que les tokens de l'executeur. » Sans lecture des
   iterations, la sous-inference du conseiller est facturee mais invisible —
   exactement le defaut corrige pour le cache a la tache #11.
3. Le cout des 11 CHECKs n'etait enregistre NULLE PART : `CheckResult` portait
   les compteurs, aucun appelant ne les persistait.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.test import override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.checks_blocs import (
    _ADDENDUM_ADVISOR,
    BLOCS_PAR_IDENTIFIANT,
    _advisor_actif_pour_bloc,
    check_bloc,
)
from generation.models import ChapterGeneration, GenerationJob
from integrations.claude import (
    _ADVISOR_BETA,
    _ADVISORS_VALIDES,
    _MIN_ADVISOR_MAX_TOKENS,
    StubClaudeClient,
    _advisor_tool,
    _usage_totaux,
)
from orders.models import Order

_SONNET = "claude-sonnet-4-6"


class _Vue:
    def __init__(self, **kwargs: object) -> None:
        for cle, valeur in kwargs.items():
            setattr(self, cle, valeur)


# ── 1. Definition de l'outil et validite de la paire ─────────────────────────


@override_settings(EVKHA_ADVISOR_ENABLED=True, EVKHA_ADVISOR_MAX_TOKENS=2048)
def test_la_definition_de_loutil_suit_la_doc():
    outil = _advisor_tool(_SONNET)
    assert outil == {
        "type": "advisor_20260301",
        "name": "advisor",
        # PAS `_SONNET`. Le tableau de compatibilite officiel ne place pas
        # sonnet-4-6 parmi ses propres advisors : la paire sonnet -> sonnet est
        # un 400. On prend le premier advisor valide, c'est-a-dire le moins
        # cher qui satisfasse la contrainte.
        "model": "claude-opus-4-7",
        "max_uses": 1,
        "max_tokens": 2048,
    }


@override_settings(EVKHA_ADVISOR_ENABLED=True)
def test_le_conseiller_est_au_moins_aussi_capable_que_lexecuteur():
    """Ce test affirmait l'inverse, et verrouillait une paire refusee par l'API.

    Il exigeait `advisor == executeur`, en resumant la regle de la doc par
    « les modeles de capacite egale peuvent se conseiller mutuellement ». C'est
    vrai a partir d'Opus 4.7 et faux pour Sonnet 4.6 — le seul modele que ce
    projet emploie. La paire emise etait donc un 400, jamais leve parce que
    l'advisor ne monte que sur les CHECKs de bloc et que ceux-ci ne s'executent
    pas dans le moteur en service.

    Un test qui verrouille un defaut est pire qu'une absence de test : il
    interdit de le corriger (regle 6).
    """
    outil = _advisor_tool(_SONNET)
    assert outil is not None
    assert outil["model"] != _SONNET, (
        "sonnet-4-6 ne peut pas se conseiller lui-meme : l'API refuse la paire"
    )
    assert outil["model"] in _ADVISORS_VALIDES[_SONNET]


@override_settings(EVKHA_ADVISOR_ENABLED=True)
@pytest.mark.parametrize("model_id", ["claude-haiku-4-5-20251001"])
def test_aucune_paire_invalide_nest_emise(model_id: str):
    """Haiku n'est jamais advisor et n'a pas d'advisor : absent du tableau.

    `claude-sonnet-5` a ete RETIRE de ce parametrage : il figure bien dans le
    tableau, avec des advisors Opus valides. L'exclure revenait a priver de
    conseiller le modele vers lequel le projet migre.
    """
    assert _advisor_tool(model_id) is None


@override_settings(EVKHA_ADVISOR_ENABLED=True)
def test_sonnet_5_a_bien_un_conseiller() -> None:
    """Contre-epreuve du retrait ci-dessus, et cas du modele a venir."""
    outil = _advisor_tool("claude-sonnet-5")
    assert outil is not None
    assert outil["model"] in _ADVISORS_VALIDES["claude-sonnet-5"]
    assert outil["model"] != "claude-sonnet-5"


@override_settings(EVKHA_ADVISOR_ENABLED=False)
def test_loutil_est_absent_quand_le_reglage_est_off():
    assert _advisor_tool(_SONNET) is None


@override_settings(EVKHA_ADVISOR_ENABLED=True, EVKHA_ADVISOR_MAX_TOKENS=512)
def test_le_plafond_du_conseiller_respecte_le_minimum_api():
    """Sous 1024, l'API refuse la requete : on remonte au minimum."""
    outil = _advisor_tool(_SONNET)
    assert outil is not None
    assert outil["max_tokens"] == _MIN_ADVISOR_MAX_TOKENS


def test_le_flag_beta_est_celui_de_la_doc():
    assert _ADVISOR_BETA == "advisor-tool-2026-03-01"


# ── 2. Comptage des tokens du conseiller ─────────────────────────────────────


def test_sans_iterations_le_comptage_retombe_sur_le_usage_global():
    totaux = _usage_totaux(_Vue(input_tokens=100, output_tokens=40))
    assert (totaux.input_facturable, totaux.output) == (100, 40)
    assert totaux.advisor_calls == 0


def test_les_tokens_du_conseiller_sont_comptes():
    """Ils ne sont PAS dans les totaux de niveau superieur (doc facturation)."""
    usage = _Vue(
        input_tokens=412,
        output_tokens=531,
        iterations=[
            {"type": "message", "input_tokens": 412, "output_tokens": 89},
            {
                "type": "advisor_message",
                "model": _SONNET,
                "input_tokens": 823,
                "output_tokens": 1612,
            },
            {
                "type": "message",
                "input_tokens": 1348,
                "cache_read_input_tokens": 412,
                "output_tokens": 442,
            },
        ],
    )
    totaux = _usage_totaux(usage)

    # Input : 412 + 823 + 1348 + 10 % de 412 lus en cache.
    assert totaux.input_facturable == 412 + 823 + 1348 + 41
    assert totaux.output == 89 + 1612 + 442
    assert totaux.advisor_calls == 1
    assert totaux.advisor_output == 1612
    assert totaux.lectures_cache == 412
    # Le total de niveau superieur aurait rendu 412 / 531 : la sous-inference
    # entiere du conseiller disparaissait du calcul.
    assert totaux.input_facturable > 412
    assert totaux.output > 531


def test_les_iterations_en_objets_typees_sont_lues_comme_les_dicts():
    """Selon la version du SDK, `iterations` porte des objets ou des dicts."""
    usage = _Vue(
        input_tokens=0,
        output_tokens=0,
        iterations=[_Vue(type="advisor_message", input_tokens=500, output_tokens=700)],
    )
    totaux = _usage_totaux(usage)
    assert (totaux.input_facturable, totaux.output) == (500, 700)
    assert totaux.advisor_calls == 1


def test_le_sdk_installe_conserve_les_iterations_non_typees():
    """Verification du couplage reel, pas d'une hypothese.

    Le modele `Usage` du SDK 0.84.0 ne declare PAS `iterations` (champ beta
    recent). Le comptage de l'advisor ne tient donc qu'a `extra: allow` sur les
    modeles Anthropic, qui preserve le champ inconnu sous forme de dicts bruts
    — d'ou la lecture tolerante attribut/cle. Si une version future retire
    cette permissivite sans typer le champ, les tokens du conseiller
    redeviendraient invisibles : ce test le dira.
    """
    pytest.importorskip("anthropic")
    from anthropic.types import Usage

    usage = Usage.model_validate(
        {
            "input_tokens": 412,
            "output_tokens": 531,
            "iterations": [
                {"type": "message", "input_tokens": 412, "output_tokens": 89},
                {"type": "advisor_message", "input_tokens": 823, "output_tokens": 1612},
            ],
        }
    )
    totaux = _usage_totaux(usage)
    assert totaux.advisor_calls == 1
    assert totaux.advisor_output == 1612
    assert totaux.input_facturable == 412 + 823


# ── 3. Perimetre : quels blocs consultent ────────────────────────────────────


@override_settings(EVKHA_ADVISOR_ENABLED=True, EVKHA_ADVISOR_BLOCS="A,F,G,I,J")
@pytest.mark.parametrize("identifiant", ["A", "F", "G", "I", "J"])
def test_les_blocs_quantifies_consultent(identifiant: str):
    assert _advisor_actif_pour_bloc(BLOCS_PAR_IDENTIFIANT[identifiant]) is True


@override_settings(EVKHA_ADVISOR_ENABLED=True, EVKHA_ADVISOR_BLOCS="A,F,G,I,J")
@pytest.mark.parametrize("identifiant", ["INITIAL", "B", "C", "D", "E", "H"])
def test_les_autres_blocs_ne_consultent_pas(identifiant: str):
    """Choix de cout : ~0,04 EUR par CHECK conseille."""
    assert _advisor_actif_pour_bloc(BLOCS_PAR_IDENTIFIANT[identifiant]) is False


@override_settings(EVKHA_ADVISOR_ENABLED=True, EVKHA_ADVISOR_BLOCS="*")
def test_letoile_etend_a_tous_les_checks():
    assert all(_advisor_actif_pour_bloc(bloc) for bloc in BLOCS_PAR_IDENTIFIANT.values())


@override_settings(EVKHA_ADVISOR_ENABLED=True, EVKHA_ADVISOR_BLOCS="")
def test_une_liste_vide_desactive_partout():
    assert not any(_advisor_actif_pour_bloc(b) for b in BLOCS_PAR_IDENTIFIANT.values())


@override_settings(EVKHA_ADVISOR_ENABLED=False, EVKHA_ADVISOR_BLOCS="*")
def test_le_reglage_global_prime_sur_la_liste():
    assert not any(_advisor_actif_pour_bloc(b) for b in BLOCS_PAR_IDENTIFIANT.values())


# ── 4. Cablage du CHECK ──────────────────────────────────────────────────────


class _ClientEspion:
    """Stub qui memorise les arguments et rend un verdict `pass` parseable."""

    def __init__(self) -> None:
        self.appels: list[dict[str, object]] = []

    def complete(self, *, system, prompt, max_tokens=8192, model=None, advisor=False):
        self.appels.append(
            {"system": system, "prompt": prompt, "model": model, "advisor": advisor}
        )
        from integrations.claude import ClaudeResult

        return ClaudeResult(
            content='```json\n{"verdict": "pass", "note_corrective": "", '
                    '"points_a_enrichir_fiche": []}\n```',
            input_tokens=6000,
            output_tokens=2000,
            model=model or "claude-sonnet",
            advisor_calls=1 if advisor else 0,
        )


@pytest.fixture
def em_job() -> GenerationJob:
    offer = Offer.objects.create(
        name="EM advisor", slug="em-advisor",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="advisor@b.c")
    order = Order.objects.create(systeme_order_id="o-advisor", customer=customer, offer=offer)
    job = GenerationJob.objects.create(
        order=order,
        deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=Decimal("4.6000"),
    )
    for numero in (0, 1, 2):
        ChapterGeneration.objects.create(
            job=job, chapter_number=numero, chapter_title=f"Ch {numero}",
            prompt_key=f"em.{numero:02d}", content="Contenu du chapitre.",
        )
    return job


@pytest.mark.django_db
@override_settings(EVKHA_ADVISOR_ENABLED=True, EVKHA_ADVISOR_BLOCS="A")
def test_le_check_du_bloc_a_demande_lavisor_et_sa_consigne(em_job: GenerationJob) -> None:
    client = _ClientEspion()
    chapitres = list(em_job.chapters.filter(chapter_number__in=(1, 2)))

    result = check_bloc(em_job, BLOCS_PAR_IDENTIFIANT["A"], chapitres, client=client)

    assert client.appels[0]["advisor"] is True
    assert _ADDENDUM_ADVISOR in str(client.appels[0]["system"])
    # Le stub de dev reconnait le relecteur a ce marqueur : l'addendum ne doit
    # pas le faire disparaitre.
    assert "RELECTEUR EVKHA" in str(client.appels[0]["system"])
    assert result.advisor_calls == 1


@pytest.mark.django_db
@override_settings(EVKHA_ADVISOR_ENABLED=True, EVKHA_ADVISOR_BLOCS="A")
def test_un_bloc_hors_perimetre_nemporte_ni_advisor_ni_consigne(
    em_job: GenerationJob,
) -> None:
    client = _ClientEspion()
    chapitres = list(em_job.chapters.filter(chapter_number=1))

    check_bloc(em_job, BLOCS_PAR_IDENTIFIANT["B"], chapitres, client=client)

    assert client.appels[0]["advisor"] is False
    assert _ADDENDUM_ADVISOR not in str(client.appels[0]["system"])


# ── 5. Le cout du CHECK entre dans le grand livre ────────────────────────────


@pytest.mark.django_db
@override_settings(EVKHA_ADVISOR_ENABLED=False)
def test_le_cout_du_check_est_enregistre(em_job: GenerationJob) -> None:
    """Defaut historique : 11 CHECKs par EM totalement absents du grand livre."""
    chapitre = em_job.chapters.get(chapter_number=2)
    assert chapitre.cost_eur == Decimal("0")

    check_bloc(
        em_job,
        BLOCS_PAR_IDENTIFIANT["A"],
        list(em_job.chapters.filter(chapter_number__in=(1, 2))),
        client=_ClientEspion(),
    )

    chapitre.refresh_from_db()
    em_job.refresh_from_db()
    # 6000 tok in x 0,0000027 + 2000 tok out x 0,0000135 = 0,0432 EUR
    assert chapitre.cost_eur == Decimal("0.0432")
    assert chapitre.input_tokens == 6000
    assert em_job.total_cost_eur == Decimal("0.0432")


@pytest.mark.django_db
@override_settings(EVKHA_ADVISOR_ENABLED=False)
def test_le_cout_du_check_initial_va_sur_la_fiche_projet(em_job: GenerationJob) -> None:
    """Le bloc INITIAL n'a aucun chapitre : le cout se rattache au chapitre 0."""
    check_bloc(em_job, BLOCS_PAR_IDENTIFIANT["INITIAL"], [], client=_ClientEspion())

    fiche = em_job.chapters.get(chapter_number=0)
    assert fiche.cost_eur > Decimal("0")


@pytest.mark.django_db
@override_settings(EVKHA_ADVISOR_ENABLED=False)
def test_le_second_appel_de_secours_sadditionne(em_job: GenerationJob) -> None:
    """JSON illisible au 1er appel : les deux appels sont factures, pas un."""

    class _ClientJsonCoupe(_ClientEspion):
        def complete(self, *, system, prompt, max_tokens=8192, model=None, advisor=False):
            resultat = super().complete(
                system=system, prompt=prompt, max_tokens=max_tokens,
                model=model, advisor=advisor,
            )
            if len(self.appels) == 1:  # premier appel : reponse tronquee
                from integrations.claude import ClaudeResult

                return ClaudeResult(
                    content='```json\n{"verdict": "pa',
                    input_tokens=6000, output_tokens=2000,
                    model=model or "claude-sonnet",
                )
            return resultat

    client = _ClientJsonCoupe()
    check_bloc(
        em_job,
        BLOCS_PAR_IDENTIFIANT["A"],
        list(em_job.chapters.filter(chapter_number__in=(1, 2))),
        client=client,
    )

    assert len(client.appels) == 2
    chapitre = em_job.chapters.get(chapter_number=2)
    assert chapitre.input_tokens == 12000
    assert chapitre.cost_eur == Decimal("0.0864")


@pytest.mark.django_db
def test_le_stub_de_dev_accepte_le_parametre_advisor(em_job: GenerationJob) -> None:
    """Le protocole a change : un stub non aligne leverait TypeError en CI."""
    resultat = StubClaudeClient().complete(
        system="Tu es le RELECTEUR EVKHA.", prompt="x", advisor=True,
    )
    assert resultat.advisor_calls == 0
    assert "verdict" in resultat.content


def test_budget_em_couvre_les_checks_et_ladvisor() -> None:
    from generation.services import _BUDGET_EUR_BY_TYPE

    assert _BUDGET_EUR_BY_TYPE[DeliverableType.MARKET_STUDY] >= Decimal("4.6000")

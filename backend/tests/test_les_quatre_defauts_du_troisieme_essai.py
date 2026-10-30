"""Les quatre défauts restés dans l'étude IA de test `d24977e6` (30/10/2026).

Troisième génération de test, la première où la note du relecteur arrivait
entière au rédacteur. Quatre défauts réels sont restés au document :

1. chapitre 17 : une figure du chapitre 16 redemandée — l'assemblage imprime
   un renvoi, le relecteur voit un graphique en double et en demande le
   retrait trois passes de suite. Rien ne disait au rédacteur qu'elle existait ;
2. chapitre 10 : « Il a souvent entre 35 et 60 ans », un portrait que ni le
   dossier ni une source ne portait, écrit comme un fait ;
3. chapitre 6 : « le droit de la consommation ne s'applique pas en principe »
   à un artisan client — faux pour un artisan de cinq salariés au plus qui
   signe hors établissement (article L221-3 du code de la consommation) ;
4. chapitre 8 : « Quatre choix tiennent… », suivi de cinq.

Chaque test lit le prompt RÉELLEMENT construit pour un chapitre (règle 8 : une
consigne écrite mais jamais transmise a déjà coûté dix-huit figures).
"""
from __future__ import annotations

import pytest
from django.test import override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres.configuration import type_document
from generation.chapitres.runner import construire_prompt_chapitre
from generation.models import ChapterStatus, GenerationJob
from generation.services import bootstrap_generation_job
from generation.socle import etablir_socle, socle_verrouille
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StubClaudeClient
from orders.models import Order

EM = DeliverableType.MARKET_STUDY
VARIABLES = {
    "SECTEUR": "conseil en intelligence artificielle pour TPE", "PAYS": "France",
    "ZONE": "Hauts-de-France", "PROJET": "consultant IA indépendant",
}
TITRE = "FIGURES DÉJÀ PRÉSENTÉES DANS L'ÉTUDE"


def _dossier(suffixe: str) -> GenerationJob:
    offre, _ = Offer.objects.get_or_create(
        slug="em-quatre-defauts", defaults={"name": "EM", "deliverable_type": EM},
    )
    commande = Order.objects.create(
        systeme_order_id=f"cmd-quatre-defauts-{suffixe}",
        customer=Customer.objects.create(email=f"quatre-{suffixe}@exemple.fr"),
        offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED, normalized_variables=VARIABLES,
    )
    with override_settings(EVKHA_MEMOIRE_ETUDE=True):
        job = bootstrap_generation_job(soumission)
    etablir_socle(job, client=StubClaudeClient(), variables=VARIABLES)
    return job


def _prompt(job: GenerationJob, numero: int) -> tuple[str, str]:
    socle = socle_verrouille(job)
    assert socle is not None
    prompt, _ = construire_prompt_chapitre(
        job.chapters.get(chapter_number=numero), socle=socle,
        variables=VARIABLES, document=type_document(EM),
    )
    return prompt.par_job, prompt.par_chapitre


def _poser_figure(job: GenerationJob, numero: int, titre: str, donnees: list[str]) -> None:
    job.chapters.filter(chapter_number=numero).update(
        status=ChapterStatus.DONE,
        content="Texte.",
        payload={"blocs": [
            {"type": "paragraphe", "texte": "Texte."},
            {"type": "graphique", "graphique": {
                "type": "barres", "titre": titre, "donnees_ids": donnees,
                "commentaire": "",
            }},
        ]},
    )


# ── 1. La figure déjà présentée ──────────────────────────────────────────────


@pytest.mark.django_db
def test_le_chapitre_suivant_sait_quelles_figures_existent_deja() -> None:
    """LE cas du chapitre 17. Sur le code d'avant, aucune liste de figures."""
    job = _dossier("a")
    _poser_figure(
        job, 16, "Marché européen de l'IA en 2025 et marché mondial projeté en 2030",
        ["marche_europeen", "marche_mondial"],
    )

    _, consigne = _prompt(job, 17)

    assert TITRE in consigne
    assert (
        "« Marché européen de l'IA en 2025 et marché mondial projeté en 2030 » "
        "(chapitre 16) — données : marche_europeen, marche_mondial"
    ) in consigne


@pytest.mark.django_db
def test_une_reecriture_voit_les_figures_des_chapitres_suivants() -> None:
    job = _dossier("b")
    _poser_figure(job, 18, "Synthèse SWOT", ["forces"])

    _, consigne = _prompt(job, 16)

    assert "« Synthèse SWOT » (chapitre 18)" in consigne


@pytest.mark.django_db
def test_un_chapitre_ne_se_voit_pas_lui_meme() -> None:
    """CONTRE-ÉPREUVE : la réécriture du chapitre 16 ne s'interdit pas sa
    propre figure."""
    job = _dossier("c")
    _poser_figure(job, 16, "Marché européen", ["marche_europeen"])

    _, consigne = _prompt(job, 16)

    assert TITRE not in consigne


@pytest.mark.django_db
def test_sans_figure_aucun_bloc() -> None:
    job = _dossier("d")

    _, consigne = _prompt(job, 3)

    assert TITRE not in consigne


@pytest.mark.django_db
def test_une_panne_du_registre_des_figures_n_arrete_pas_le_chapitre(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = _dossier("e")
    _poser_figure(job, 1, "Marché", ["m"])

    def en_panne(*_args: object) -> str:
        raise ValueError("imprévu")

    monkeypatch.setattr("generation.chapitres.runner._bloc_figures_posees", en_panne)
    _, consigne = _prompt(job, 2)

    assert TITRE not in consigne
    assert "CHAPITRE À RÉDIGER : 2" in consigne


# ── 2, 3, 4. Les règles de fond, dans le prompt réellement envoyé ────────────


@pytest.mark.django_db
@pytest.mark.parametrize(
    "attendu",
    [
        "article L221-3 du code de la consommation",
        "nous retenons, à titre d'hypothèse",
        "Un NOMBRE ANNONCÉ",
    ],
)
def test_la_regle_part_dans_le_prompt_d_une_etude_de_marche(attendu: str) -> None:
    job = _dossier(f"r{abs(hash(attendu)) % 10_000}")

    par_job, par_chapitre = _prompt(job, 6)

    assert attendu in par_job + par_chapitre

"""Les quatre défauts restés dans l'étude IA de test `d24977e6` (30/10/2026).

Troisième génération de test, la première où la note du relecteur arrivait
entière au rédacteur. Quatre défauts réels sont restés au document :

1. chapitre 17 : la figure du chapitre 16 redemandée. La liste des figures
   déjà posées existait (`_figures_deja_posees`), mais ne montrait que les
   DOUZE PREMIÈRES de l'étude — douze étaient dessinées avant le chapitre 17 —
   et ignorait les chapitres suivants lors d'une réécriture ;
2. chapitre 10 : « Il a souvent entre 35 et 60 ans », un portrait que ni le
   dossier ni une source ne portait, écrit comme un fait ;
3. chapitre 6 : « le droit de la consommation ne s'applique pas en principe »
   à un artisan client — faux pour un contrat conclu hors établissement avec
   un professionnel de cinq salariés au plus (L221-18 étendu par L221-3) ;
4. chapitre 8 : « Quatre choix tiennent… », suivi de cinq.

Les tests de figures écrivent des payloads VALIDES : un payload refusé par le
contrat était écarté en silence, et un test bâti dessus ne verrouillerait
qu'un libellé (porte qualité du 30/10).
"""
from __future__ import annotations

from typing import Any

import pytest
from django.test import override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres.configuration import type_document
from generation.chapitres.runner import _figures_deja_posees, construire_prompt_chapitre
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
EUROPE = "Marché européen de l'IA en 2025 et marché mondial projeté en 2030"


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


def _payload(numero: int, titre: str, donnees: list[str]) -> dict[str, Any]:
    return {
        "chapitre": numero,
        "titre": f"Chapitre {numero}",
        "blocs": [
            {"type": "paragraphe", "texte": "Le chapitre pose ses chiffres."},
            {"type": "graphique", "graphique": {
                "type_graphique": "barres", "titre": titre, "donnees_ids": donnees,
            }},
        ],
        "resume": "Le chapitre pose ses chiffres et en tire une décision.",
    }


def _poser(job: GenerationJob, numero: int, titre: str, donnees: list[str]) -> None:
    job.chapters.filter(chapter_number=numero).update(
        status=ChapterStatus.DONE, content="Texte.",
        payload=_payload(numero, titre, donnees),
    )


# ── 1. La figure déjà posée ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_la_figure_du_chapitre_16_est_connue_du_chapitre_17() -> None:
    """LE cas de `d24977e6` : treize figures avant celle du chapitre 16.

    Sur le code d'avant, la liste s'arrêtait aux douze premières.
    """
    job = _dossier("a")
    for numero in range(1, 14):
        _poser(job, numero, f"Figure du chapitre {numero}", [f"donnee_{numero}"])
    _poser(job, 16, EUROPE, ["marche_europeen", "marche_mondial"])

    bloc = _figures_deja_posees(job, 17)

    assert f"« {EUROPE} » (chapitre 16 — marche_europeen, marche_mondial)" in bloc


@pytest.mark.django_db
def test_une_reecriture_voit_les_figures_des_chapitres_suivants() -> None:
    """La relecture finale réécrit le chapitre 16 : il doit voir le 18.

    Sur le code d'avant, seules les figures des chapitres PRÉCÉDENTS."""
    job = _dossier("b")
    _poser(job, 18, "Synthèse des forces et faiblesses", ["forces"])

    assert "« Synthèse des forces et faiblesses » (chapitre 18" in _figures_deja_posees(
        job, 16
    )


@pytest.mark.django_db
def test_une_meme_donnee_ne_prend_qu_une_ligne() -> None:
    """Un doublon déjà commis ne doit pas pousser une autre figure hors de la liste."""
    job = _dossier("c")
    _poser(job, 1, "Marché total", ["marche_total"])
    _poser(job, 3, "Le marché total, rappel", ["marche_total"])

    bloc = _figures_deja_posees(job, 5)

    assert bloc.count("marche_total") == 1
    assert "(chapitre 1 — marche_total)" in bloc


@pytest.mark.django_db
def test_un_chapitre_ne_se_voit_pas_lui_meme() -> None:
    """CONTRE-ÉPREUVE : réécrit, le chapitre 16 ne s'interdit pas sa figure."""
    job = _dossier("d")
    _poser(job, 16, EUROPE, ["marche_europeen"])

    assert _figures_deja_posees(job, 16) == ""


@pytest.mark.django_db
def test_un_payload_illisible_est_signale(caplog: pytest.LogCaptureFixture) -> None:
    """Il était écarté en silence : ses figures quittaient la liste sans trace."""
    job = _dossier("e")
    job.chapters.filter(chapter_number=2).update(
        status=ChapterStatus.DONE, payload={"chapitre": "pas un nombre", "blocs": "cassé"},
    )
    _poser(job, 3, "Marché", ["m"])

    with caplog.at_level("WARNING"):
        bloc = _figures_deja_posees(job, 5)

    assert "(chapitre 3 — m)" in bloc
    assert any("chapitre 2 illisible" in r.getMessage() for r in caplog.records)


@pytest.mark.django_db
def test_la_liste_part_dans_le_prompt_du_chapitre() -> None:
    """Le câble, pas seulement la fonction (règle 8)."""
    job = _dossier("f")
    _poser(job, 16, EUROPE, ["marche_europeen", "marche_mondial"])
    socle = socle_verrouille(job)
    assert socle is not None

    prompt, _ = construire_prompt_chapitre(
        job.chapters.get(chapter_number=17), socle=socle,
        variables=VARIABLES, document=type_document(EM),
    )

    assert prompt.par_chapitre.count(EUROPE) == 1, "une seule liste de figures"


# ── 2, 3, 4. Les règles de fond, dans le prompt réellement envoyé ────────────


def _consigne_complete(job: GenerationJob, numero: int) -> str:
    socle = socle_verrouille(job)
    assert socle is not None
    prompt, _ = construire_prompt_chapitre(
        job.chapters.get(chapter_number=numero), socle=socle,
        variables=VARIABLES, document=type_document(EM),
    )
    return prompt.par_job + prompt.par_chapitre


@pytest.mark.django_db
@pytest.mark.parametrize(
    "attendu",
    [
        "étendu par l'article L221-3",
        "nous retenons, à titre d'hypothèse",
        "Un NOMBRE ANNONCÉ",
    ],
)
def test_la_regle_part_dans_le_prompt_d_une_etude_de_marche(attendu: str) -> None:
    job = _dossier(f"r{len(attendu)}")

    assert attendu in _consigne_complete(job, 6)


@pytest.mark.django_db
def test_la_regle_juridique_reste_dans_ses_bornes() -> None:
    """CONTRE-ÉPREUVE (porte qualité du 30/10) : L221-3 n'étend ni le contrat à
    distance, ni « les protections d'un particulier », et garde les exceptions."""
    consigne = _consigne_complete(_dossier("j"), 6)

    assert "pas à distance" in consigne
    assert "sauf les exceptions de l'article L221-28" in consigne
    assert "protections d'un particulier" not in consigne
    assert "par démarchage" not in consigne

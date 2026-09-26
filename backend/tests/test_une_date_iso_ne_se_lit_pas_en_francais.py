"""« arrêté au 2026-08-08 » : une date écrite à la machine, dans un document français.

Jusqu'au lot 95, la ligne du socle injectée dans chaque prompt de chapitre datait
ses chiffres en ISO, et le modèle recopie la forme qu'on lui donne. La source
est corrigée ; ce contrôle vérifie ce que le lecteur reçoit (règle 3 : ce qui
arrive au lecteur se contrôle, pas ce qu'on a demandé).

Ce qu'il ne juge pas, exprès : une date ISO dans une ADRESSE (les chemins
d'URL en portent, et elle y est légitime), une référence de règlement
(« 2016/679 »), une date déjà en toutes lettres.
"""
from __future__ import annotations

import pytest

from generation.checks_post_rendu import detecter_dates_iso
from generation.correction import _CHECK_LABELS, _is_regenerable
from generation.gate import _check_dates_iso
from generation.rendering import RenderedSection


def _section(numero: int, corps: str) -> RenderedSection:
    return RenderedSection(number=numero, title=f"Chapitre {numero}", kind="chapitre", body=corps)


def test_une_date_iso_dans_la_prose_est_vue_une_fois_par_chapitre() -> None:
    trouves = detecter_dates_iso([_section(
        4, "Chiffres arrêtés au 2026-08-08 (Insee). Le socle du 2026-08-08 sert de base ; "
           "la mise à jour du 2026-09-01 suivra.",
    )])
    assert [(t.chapitre, t.date) for t in trouves] == [(4, "2026-08-08"), (4, "2026-09-01")]
    assert "8 août 2026" in str(trouves[0])


@pytest.mark.parametrize(
    "texte",
    [
        pytest.param("Voir https://www.insee.fr/fr/2026-08-08/statistiques", id="dans-une-url"),
        pytest.param("Voir insee.fr/publications/2026-08-08", id="dans-un-domaine-nu"),
        pytest.param("Le Règlement (UE) 2016/679 s'applique.", id="reference-reglement"),
        pytest.param("Chiffres arrêtés au 8 août 2026 (Insee).", id="en-toutes-lettres"),
        pytest.param("Référence 2026-08-08-A du catalogue.", id="code-avec-suffixe"),
    ],
)
def test_ce_qui_n_est_pas_une_date_de_prose_n_est_pas_signale(texte: str) -> None:
    assert detecter_dates_iso([_section(4, texte)]) == [], texte


def test_le_gate_porte_le_motif_au_bon_chapitre() -> None:
    echecs = _check_dates_iso((
        _section(3, "Chiffres arrêtés au 8 août 2026."),
        _section(7, "Chiffres arrêtés au 2026-08-08."),
    ))
    assert [(e.check, e.chapter_number) for e in echecs] == [("date_iso", 7)]


def test_la_boucle_de_correction_sait_le_reparer() -> None:
    assert _is_regenerable("date_iso")
    assert "date_iso" in _CHECK_LABELS

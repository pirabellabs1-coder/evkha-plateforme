"""Le refus d'un héritage ne s'imprime pas dans le document du client.

Étude `a6947890` (SUN TZU ORGANISATION, terroir français vendu en Asie,
01/11/2026) : quinze fois, sous des tableaux et dans l'annexe « D'où viennent
les chiffres », on lisait « Pas de reprise de l'étude précédente : elle
retenait 18,4 MdEUR pour le marché français de l'IA, un autre secteur ».
L'héritage transmettait les chiffres d'un AUTRE projet du même compte ; le
modèle les a écartés en l'écrivant dans le champ source. La cause est fermée
dans `socle.heritage` (même projet exigé) ; ces tests retirent la trace des
socles déjà écrits, au rendu.
"""
from __future__ import annotations

import pytest

from generation.rendu_word.composants import libelle_de_source, sans_refus_d_heritage

SOURCE_A6947890 = (
    "SIAL Paris, 2026 (données 2025). Pas de reprise de l'étude précédente : "
    "elle retenait 55,0 MdUSD pour le marché européen de l'IA, un autre secteur ; "
    "Team France Export, fiche marché Chine, 2026"
)


def test_le_refus_est_retire_et_les_vraies_sources_restent() -> None:
    propre = sans_refus_d_heritage(SOURCE_A6947890)

    assert "étude précédente" not in propre
    assert propre == (
        "SIAL Paris, 2026 (données 2025) ; Team France Export, fiche marché Chine, 2026"
    )


def test_le_libelle_imprime_sous_un_tableau_n_a_plus_le_refus() -> None:
    """Le câble, pas seulement la fonction : `libelle_de_source` l'emploie."""
    assert "étude précédente" not in libelle_de_source(SOURCE_A6947890)


def test_une_source_faite_du_seul_refus_ne_s_imprime_plus() -> None:
    assert libelle_de_source(
        "Pas de reprise de l'étude précédente : elle retenait 244,0 MdUSD pour le "
        "marché mondial de l'IA, un autre secteur, sans rapport avec ce dossier"
    ) == ""


@pytest.mark.parametrize("source", [
    "FEVS, 2026 — révisé depuis l'étude précédente, qui retenait 1 588,6 M€",
    "Insee, 2025",
    "Douanes chinoises, décret n° 248",
])
def test_contre_epreuve_les_autres_sources_ne_bougent_pas(source: str) -> None:
    """L'écart NOMMÉ entre deux livrables du même projet reste : il est voulu."""
    assert sans_refus_d_heritage(source) == source


def test_l_annexe_des_chiffres_passe_par_le_meme_nettoyage() -> None:
    import inspect

    from generation.rendu_word import annexe_chiffres

    assert "sans_refus_d_heritage(" in inspect.getsource(annexe_chiffres._origine)

"""Un préfixe ne tue plus une figure, et deux clics ne lancent plus deux boucles.

Audit du 26/09/2026, deux défauts prouvés en lecture :

1. `valider_chapitre` ramène au socle les identifiants DÉCORÉS de
   `donnees_utilisees` (« critere_prix_evkha » → « prix », business plan
   `2a8872d0`), mais laissait ceux des FIGURES tels quels : au rendu, la figure
   était abandonnée pour « identifiants absents » — la déclaration réparée,
   pas le dessin.
2. Rien ne verrouillait la boucle de correction : deux clics sur « corriger »
   lançaient deux boucles sur le même dossier, chacune sous le plafond,
   chacune payée ; et un plantage laissait l'ancien `qa_status` sans trace.
"""
from __future__ import annotations

import pytest
from django.core.cache import cache

from generation.chapitres.schema import (
    BlocGraphique,
    BlocParagraphe,
    ChapitrePayload,
    Graphique,
    TypeGraphique,
    valider_chapitre,
)
from generation.tasks import (
    correction_en_cours,
    liberer_verrou_de_correction,
    verrou_de_correction,
)


def _payload(*identifiants: str) -> ChapitrePayload:
    return ChapitrePayload(
        chapitre=3,
        titre="Chapitre d'essai",
        blocs=[
            BlocParagraphe(texte="Un paragraphe suffisant pour tenir le contrat."),
            BlocGraphique(graphique=Graphique(
                type_graphique=TypeGraphique("barres"), titre="Une figure",
                donnees_ids=list(identifiants),
            )),
        ],
        resume="Un résumé d'essai suffisamment long pour tenir sa borne basse.",
    )


def test_l_identifiant_decore_d_une_figure_est_ramene_au_socle() -> None:
    payload = _payload("critere_prix_evkha", "tam")

    valider_chapitre(
        payload, numero_attendu=3, identifiants_socle=frozenset({"prix", "tam"}),
        derniere_tentative=False, resume_mots_min=1, resume_mots_max=200,
    )

    assert payload.graphiques[0].donnees_ids == ["prix", "tam"]
    assert "prix" in payload.donnees_utilisees


def test_un_identifiant_inconnu_reste_inconnu_dans_la_figure() -> None:
    """Contre-épreuve : résoudre n'est pas deviner — deux candidats de même
    longueur ne tranchent rien, et un nom sans rapport reste tel quel."""
    payload = _payload("marge_nette_evkha")

    valider_chapitre(
        payload, numero_attendu=3, identifiants_socle=frozenset({"prix", "tam"}),
        derniere_tentative=False, resume_mots_min=1, resume_mots_max=200,
    )

    assert payload.graphiques[0].donnees_ids == ["marge_nette_evkha"]


@pytest.fixture(autouse=True)
def _cache_propre() -> None:
    cache.clear()


def test_une_seule_correction_a_la_fois() -> None:
    assert verrou_de_correction("job-1") is True
    assert correction_en_cours("job-1") is True
    assert verrou_de_correction("job-1") is False, "le second clic ne prend pas le dossier"
    assert verrou_de_correction("job-2") is True, "un autre dossier n'est pas concerné"

    liberer_verrou_de_correction("job-1")

    assert correction_en_cours("job-1") is False
    assert verrou_de_correction("job-1") is True

"""Un aléa passager ne doit pas détruire une étude entière.

Trois générations réelles, trois morts, **une seule cause structurelle**.

Le runner de production appelait `produire_chapitre` UNE fois et laissait
l'exception remonter. Or la boucle de reprise existe — complète, avec
temporisation exponentielle — dans `chapitres/tasks.py::produire_chapitre_task`,
et **rien ne l'appelle** (règle 8, le défaut de Gamma à l'identique).

- Run nº1 : mort au chapitre 1, écart de volume de 20 %.
- Run nº2 : mort au chapitre 5, résumé de 254 mots pour 250.
- Run nº3 : mort au chapitre 20, `blocs : Field required` — une réponse de
  modèle incomplète, c'est-à-dire l'incident transitoire par excellence.
  Dix-neuf chapitres écrits, 1,21 €, perdus.

J'ai corrigé les deux premiers en rendant les règles concernées tolérantes.
C'était traiter deux instances d'un défaut dont la classe est ici : un chemin
sans reprise transforme le moindre aléa en perte totale (règle 4).

**Mise à jour du 05/08/2026.** La boucle vivait dans `generation.runner`, donc
sur le seul chemin de la PREMIÈRE écriture. La RÉPARATION d'un chapitre —
celle qu'un CHECK inter-bloc déclenche — appelait `produire_chapitre` une fois,
et le run réel `4c8cfa53` est mort là-dessus : trois chapitres écrits, puis
`essais=1` sur la réparation du chapitre 3. Le même défaut, sur l'autre chemin.

La boucle a donc déménagé dans `chapitres.services`, avec le cycle de vie du
chapitre, et sert les deux. Ces tests l'éprouvent toujours **par le runner** :
c'est lui qui déclare ce qu'on ne rejoue pas, et cette déclaration fait partie
de ce qu'il faut verrouiller.
"""
from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture
def decor(monkeypatch: Any) -> Any:
    """Un job minimal et un compteur d'appels à `produire_chapitre`."""
    from types import SimpleNamespace

    from generation import runner
    from generation.chapitres import services

    appels: list[bool] = []

    monkeypatch.setattr(
        services, "type_document", lambda _: SimpleNamespace(tentatives_max=3)
    )

    job = SimpleNamespace(id="job-essai", deliverable_type="market_study")
    chapitre = SimpleNamespace(chapter_number=7)
    return SimpleNamespace(
        job=job, chapitre=chapitre, appels=appels, runner=runner, services=services
    )


def _brancher(monkeypatch: Any, decor: Any, comportement: Any) -> None:
    def faux(job: Any, numero: int, *, client: Any, socle: Any, derniere_tentative: bool) -> None:
        decor.appels.append(derniere_tentative)
        comportement(len(decor.appels))

    monkeypatch.setattr(decor.services, "produire_chapitre", faux)


# ── La reprise existe et s'arrête au bon moment ──────────────────────────────


def test_un_echec_passager_est_rejoue_et_l_etude_continue(
    decor: Any, monkeypatch: Any
) -> None:
    """Le test qui échoue sur le code d'avant : il n'y avait aucune reprise.

    Le chapitre échoue une fois — comme au run nº3 — puis réussit. L'étude doit
    survivre.
    """
    def echoue_une_fois(tentative: int) -> None:
        if tentative == 1:
            msg = "blocs : Field required ; resume : Field required"
            raise ValueError(msg)

    _brancher(monkeypatch, decor, echoue_une_fois)

    decor.runner._produire_avec_reprises(
        decor.job, decor.chapitre, client=object(), socle=None
    )

    assert len(decor.appels) == 2, "aucune reprise : une reponse incomplete tue l'etude"


def test_la_reprise_s_arrete_au_plafond(decor: Any, monkeypatch: Any) -> None:
    """Contre-épreuve : on ne rejoue pas indéfiniment.

    Chaque tentative coûte un appel facturé. Sans plafond, un chapitre
    durablement cassé dépenserait le budget entier.
    """
    def echoue_toujours(_: int) -> None:
        msg = "toujours casse"
        raise ValueError(msg)

    _brancher(monkeypatch, decor, echoue_toujours)

    with pytest.raises(ValueError, match="toujours casse"):
        decor.runner._produire_avec_reprises(
            decor.job, decor.chapitre, client=object(), socle=None
        )

    assert len(decor.appels) == 3, f"{len(decor.appels)} tentatives au lieu de 3"


def test_un_chapitre_qui_passe_du_premier_coup_n_est_pas_rejoue(
    decor: Any, monkeypatch: Any
) -> None:
    """Contre-épreuve : le cas normal ne doit rien coûter de plus."""
    _brancher(monkeypatch, decor, lambda _: None)

    decor.runner._produire_avec_reprises(
        decor.job, decor.chapitre, client=object(), socle=None
    )

    assert len(decor.appels) == 1


# ── La dernière tentative est déclarée, et elle est vraie ────────────────────


def test_seule_la_derniere_tentative_est_annoncee_comme_telle(
    decor: Any, monkeypatch: Any
) -> None:
    """L'arbitrage de conformité en dépend entièrement.

    Annoncer `True` dès le premier essai accepterait les écarts de forme sans
    jamais tenter de faire mieux. Annoncer `False` partout recréerait le défaut
    du run nº1 : l'étage « accepter puis consigner » ne serait jamais atteint,
    et un écart de dosage redeviendrait fatal.
    """
    def echoue_toujours(_: int) -> None:
        msg = "casse"
        raise ValueError(msg)

    _brancher(monkeypatch, decor, echoue_toujours)

    with pytest.raises(ValueError):
        decor.runner._produire_avec_reprises(
            decor.job, decor.chapitre, client=object(), socle=None
        )

    assert decor.appels == [False, False, True], decor.appels


# ── Ce qu'on ne rejoue PAS ───────────────────────────────────────────────────


def test_un_budget_depasse_n_est_pas_rejoue(decor: Any, monkeypatch: Any) -> None:
    """Rejouer ne ferait que dépenser davantage pour le même refus.

    C'est la seule famille d'erreurs qu'on exclut, et elle est nommée : tout
    le reste est rejoué, y compris ce qu'on n'a pas prévu — parce que ce sont
    précisément ces cas-là qui ont coûté le plus cher (règle 4).
    """
    from generation.cost import CostBudgetExceededError

    def budget(_: int) -> None:
        raise CostBudgetExceededError("plafond atteint")

    _brancher(monkeypatch, decor, budget)

    with pytest.raises(CostBudgetExceededError):
        decor.runner._produire_avec_reprises(
            decor.job, decor.chapitre, client=object(), socle=None
        )

    assert len(decor.appels) == 1, "le budget depasse a ete rejoue"


def test_un_check_initial_bloquant_n_est_pas_rejoue(
    decor: Any, monkeypatch: Any
) -> None:
    """La fiche projet est à corriger par un humain : rejouer ne la corrige pas."""
    from generation.runner import CheckInitialBlockedError

    def bloque(_: int) -> None:
        raise CheckInitialBlockedError("fiche projet incomplete")

    _brancher(monkeypatch, decor, bloque)

    with pytest.raises(CheckInitialBlockedError):
        decor.runner._produire_avec_reprises(
            decor.job, decor.chapitre, client=object(), socle=None
        )

    assert len(decor.appels) == 1


def test_le_plafond_vient_de_la_configuration_du_document() -> None:
    """Une seule source pour cette vérité (règle 5).

    `tentatives_max` est déjà lu par la tâche Celery. Écrire un `3` en dur ici
    ferait diverger les deux chemins dès que la valeur change.
    """
    import inspect

    from generation.chapitres import services

    source = inspect.getsource(services.produire_avec_reprises)

    assert "document.tentatives_max" in source
    assert "range(1, 3" not in source and "range(3)" not in source


def test_la_boucle_n_est_ecrite_qu_une_fois() -> None:
    """Écrire un chapitre et le RÉÉCRIRE doivent suivre le même chemin.

    Deux boucles séparées divergent : c'est arrivé, et ça a coûté une étude.
    Celle du runner ne servait qu'à la première écriture ; la réparation
    appelait `produire_chapitre` une seule fois, sans jamais déclarer de
    dernière tentative. Le runner DÉLÈGUE désormais, il ne recopie pas.
    """
    import inspect

    from generation import runner

    source = inspect.getsource(runner._produire_avec_reprises)

    assert "produire_avec_reprises" in source
    assert "for tentative in range" not in source, (
        "Le runner a de nouveau sa propre boucle : les deux vont diverger."
    )

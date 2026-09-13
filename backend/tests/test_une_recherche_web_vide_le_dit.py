"""Une recherche web qui ne rapporte RIEN doit le dire — et vite.

## Le défaut mesuré

Adresses rapportées par la recherche web, par dossier de production :

    9 au 17 août 2026       6 à 70
    17-18 août              0 à 22, en chute
    8 septembre             4
    11-12 septembre         0 — six stratégies Zenitek de suite

Les seize requêtes exactes du dossier Zenitek `db228221`, rejouées depuis un
poste de travail le 13/09/2026, trouvaient cinq résultats CHACUNE. Le serveur
était bloqué ; les requêtes étaient bonnes.

Pendant quatre semaines, rien ne l'a dit. Les échecs étaient comptés, mais
écrits dans l'en-tête du brief — et quand toutes les requêtes tombaient, il
n'y avait plus de brief, donc plus d'en-tête. Le cas partiel parlait, le cas
total se taisait (règles 1 et 9). Les documents partaient sans aucune source
vérifiable, et on cherchait la cause dans les prompts.

Ces tests échouent sur le code d'avant : ni `ResultatRecherche`, ni l'incident,
ni la route de diagnostic n'existaient.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client

from generation.research import collecter_la_recherche
from integrations.search import SearchResponse, SearchResult, StubWebSearchClient

_VARIABLES: dict[str, object] = {
    "SECTEUR": "assistance informatique",
    "PAYS": "France",
    "ZONE": "Paris",
}


class _Bloque:
    """Le fournisseur tel qu'il se comportait en production : il lève."""

    def search(self, **kwargs: Any) -> SearchResponse:
        raise RuntimeError("202 Ratelimit")


class _Repond:
    def search(self, **kwargs: Any) -> SearchResponse:
        return SearchResponse(
            query=str(kwargs.get("query", "")),
            results=(
                SearchResult(
                    title="Insee", url="https://www.insee.fr/fr/statistiques/1",
                    content="Nombre d'entreprises en France.", score=0.0,
                ),
            ),
        )


def test_une_recherche_entierement_tombee_est_MUETTE_et_dit_pourquoi() -> None:
    """LE test : zéro retenue n'est plus une chaîne vide sans explication."""
    resultat = collecter_la_recherche(
        "business_strategy", _VARIABLES, client=_Bloque(), pause_s=0,
    )

    assert resultat.brief == ""
    assert resultat.muette
    assert resultat.requetes > 0
    assert resultat.echecs == resultat.requetes
    # L'erreur elle-même : c'est elle qui distingue un blocage d'une absence
    # de bibliothèque, et donc le correctif à faire.
    assert any("Ratelimit" in e for e in resultat.erreurs), resultat.erreurs


def test_la_doublure_n_est_pas_une_panne() -> None:
    """CONTRE-ÉPREUVE : les tests tournent sur la doublure, qui ne rapporte rien.

    Si elle ouvrait un incident, chaque test qui lance un dossier en créerait
    un — et un signal qui sonne à chaque fois ne se lit plus.
    """
    resultat = collecter_la_recherche(
        "business_strategy", _VARIABLES, client=StubWebSearchClient(), pause_s=0,
    )
    assert not resultat.muette


def test_une_recherche_qui_rapporte_n_est_pas_muette() -> None:
    """CONTRE-ÉPREUVE : le signal ne doit pas sonner sur une recherche saine."""
    resultat = collecter_la_recherche(
        "business_strategy", _VARIABLES, client=_Repond(), pause_s=0,
    )
    assert resultat.retenues >= 1
    assert not resultat.muette
    assert "insee.fr" in resultat.brief


JETON = "r" * 64


@pytest.fixture
def api(settings: Any) -> Client:
    settings.DEBUG = False
    settings.EVKHA_DASHBOARD_AUTH_DISABLED = False
    settings.EVKHA_DASHBOARD_TOKEN = JETON
    settings.EVKHA_DASHBOARD_TOKEN_PRECEDENT = ""
    return Client(HTTP_AUTHORIZATION=f"Bearer {JETON}")


@pytest.mark.django_db
def test_la_route_de_diagnostic_rend_l_erreur_du_fournisseur(
    api: Client, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Savoir si la recherche marche ne doit plus coûter une génération entière."""
    monkeypatch.setattr("integrations.search.get_search_client", lambda: _Bloque())

    reponse = api.get("/api/dashboard/system/recherche/")
    assert reponse.status_code == 200, reponse.content
    charge = json.loads(reponse.content)

    assert charge["fournisseur"] == "_Bloque"
    assert charge["resultats"] == 0
    assert "Ratelimit" in charge["erreur"]


@pytest.mark.django_db
def test_la_route_de_diagnostic_compte_les_resultats(
    api: Client, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("integrations.search.get_search_client", lambda: _Repond())

    charge = json.loads(api.get("/api/dashboard/system/recherche/?q=test").content)

    assert charge["resultats"] == 1
    assert charge["erreur"] == ""
    assert charge["requete"] == "test"


@pytest.mark.django_db
def test_la_route_de_diagnostic_est_derriere_la_garde() -> None:
    """Elle fait sortir le serveur sur le réseau : pas sans jeton."""
    assert Client().get("/api/dashboard/system/recherche/").status_code in (401, 403)


def _dossier() -> Any:
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.services import bootstrap_generation_job
    from intake.models import IntakeStatus, IntakeSubmission
    from orders.models import Order

    offre = Offer.objects.create(
        name="STR", slug="str-recherche", deliverable_type=DeliverableType.BUSINESS_STRATEGY,
    )
    client = Customer.objects.create(email="recherche@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-recherche", customer=client, offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED,
        normalized_variables=dict(_VARIABLES),
    )
    return bootstrap_generation_job(soumission)


class _Arret(Exception):  # noqa: N818 — signal de test, pas une erreur
    pass


def _lancer_jusqu_apres_la_recherche(job: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from generation import runner as moteur

    def _arreter(*args: Any, **kwargs: Any) -> Any:
        raise _Arret

    monkeypatch.setattr(moteur, "debiter_pour_job", lambda job: (True, ""))
    monkeypatch.setattr(moteur, "_moteur_structure", lambda job: False)
    monkeypatch.setattr(moteur, "_build_phase0_plan", _arreter)
    with pytest.raises(_Arret):
        moteur.run_generation_job(job)


@pytest.mark.django_db
def test_un_dossier_lance_sans_aucune_source_ouvre_un_incident(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LE test du signal : ce qui a manqué pendant quatre semaines.

    Le dossier CONTINUE — une recherche vide ne doit pas priver le client de
    son document. Mais il ne continue plus en silence.
    """
    from generation.research import ResultatRecherche
    from monitoring.models import IncidentSeverity, OperationalIncident

    monkeypatch.setattr(
        "generation.research.collecter_la_recherche",
        lambda *a, **k: ResultatRecherche(
            requetes=16, echecs=16, fournisseur="DuckDuckGoWebSearchClient",
            erreurs=["RatelimitException : 202 Ratelimit"],
        ),
    )
    job = _dossier()
    _lancer_jusqu_apres_la_recherche(job, monkeypatch)

    incident = OperationalIncident.objects.get(job=job)
    assert incident.severity == IncidentSeverity.HIGH
    assert "Recherche web VIDE" in incident.title
    assert incident.details["erreurs"] == ["RatelimitException : 202 Ratelimit"]


@pytest.mark.django_db
def test_une_recherche_saine_n_ouvre_rien(monkeypatch: pytest.MonkeyPatch) -> None:
    """CONTRE-ÉPREUVE : un incident à chaque dossier ne se lirait plus."""
    from generation.research import ResultatRecherche
    from monitoring.models import OperationalIncident

    monkeypatch.setattr(
        "generation.research.collecter_la_recherche",
        lambda *a, **k: ResultatRecherche(
            brief="SOURCES WEB COLLECTÉES — https://www.insee.fr/a",
            requetes=16, retenues=12, fournisseur="DuckDuckGoWebSearchClient",
        ),
    )
    job = _dossier()
    _lancer_jusqu_apres_la_recherche(job, monkeypatch)

    assert not OperationalIncident.objects.filter(job=job).exists()
    job.refresh_from_db()
    assert "insee.fr" in job.research_brief

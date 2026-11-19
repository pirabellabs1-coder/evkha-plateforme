"""La prospection automatique quotidienne (phase planification).

Doublures injectées : aucun réseau, aucun coût. On vérifie que rien ne tourne
tant que ce n'est pas activé (défaut), que l'exécution cherche/qualifie/prépare
(sans jamais envoyer), que c'est idempotent (une fois par jour), et que
l'endpoint pilote les réglages avec le garde-fou « campagne requise pour
activer ».
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from prospection import tasks
from prospection.models import (
    Campagne,
    Message,
    Prospect,
    ReglageAutomatisation,
    StatutMessage,
)

from integrations.claude import StructuredResult
from integrations.search import SearchResponse, SearchResult

pytestmark = pytest.mark.django_db

BASE = "/api/dashboard/prospection"


class _ClientFaux:
    """Rend la bonne charge selon l'outil appelé (recherche, qualif, rédaction)."""

    def complete_structured(self, *, outil_nom: str, **_: Any) -> StructuredResult:
        charges: dict[str, dict[str, Any]] = {
            "extraire_prospects": {"prospects": [
                {"raison_sociale": f"Cible {i}", "email": f"c{i}@ex.fr"} for i in range(3)
            ]},
            "qualifier_prospect": {"score": 70, "raison": "ok"},
            "rediger_messages": {"messages": [
                {"objet": f"O{i}", "corps": f"<p>C{i}</p>"} for i in range(5)
            ]},
        }
        return StructuredResult(payload=dict(charges.get(outil_nom, {})),
                                input_tokens=1, output_tokens=1, model="claude-sonnet")


class _RechercheFausse:
    def search(self, *, query: str, max_results: int = 5, **_: Any) -> SearchResponse:
        return SearchResponse(query=query, results=(
            SearchResult(title="X", url="https://x.fr", content="…"),
        ))


_UN_LUNDI = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)  # lundi (weekday 0)


def _activer(campagne: Campagne, **kw: Any) -> ReglageAutomatisation:
    r = ReglageAutomatisation.charger()
    r.active = True
    r.campagne = campagne
    for k, v in kw.items():
        setattr(r, k, v)
    r.save()
    return r


# ── La tâche ──────────────────────────────────────────────────────────────────


def test_inactive_par_defaut_ne_fait_rien() -> None:
    resume = tasks.executer_si_du(maintenant=_UN_LUNDI,
                                  recherche=_RechercheFausse(), client=_ClientFaux())
    assert resume == {"execute": False, "raison": "inactive"}
    assert Prospect.objects.count() == 0


def test_active_cherche_qualifie_et_prepare_sans_envoyer() -> None:
    campagne = Campagne.objects.create(nom="C", secteur="RH", zone="Lille")
    _activer(campagne, prospects_par_jour=3)
    resume = tasks.executer_si_du(maintenant=_UN_LUNDI,
                                  recherche=_RechercheFausse(), client=_ClientFaux())
    assert resume["execute"] is True
    assert resume["crees"] == 3 and resume["qualifies"] == 3 and resume["rediges"] == 3
    # Des brouillons ont été préparés — et RIEN n'est parti.
    assert Message.objects.filter(statut=StatutMessage.BROUILLON).count() > 0
    assert Message.objects.exclude(statut=StatutMessage.BROUILLON).count() == 0


def test_idempotent_une_fois_par_jour() -> None:
    campagne = Campagne.objects.create(nom="C", secteur="RH")
    _activer(campagne, prospects_par_jour=3)
    tasks.executer_si_du(maintenant=_UN_LUNDI, recherche=_RechercheFausse(), client=_ClientFaux())
    avant = Prospect.objects.count()
    # Deuxième passage le même jour : ne refait rien.
    resume = tasks.executer_si_du(maintenant=_UN_LUNDI.replace(hour=14),
                                  recherche=_RechercheFausse(), client=_ClientFaux())
    assert resume == {"execute": False, "raison": "déjà exécuté aujourd'hui"}
    assert Prospect.objects.count() == avant


def test_jour_non_autorise_est_saute() -> None:
    campagne = Campagne.objects.create(nom="C", secteur="RH")
    _activer(campagne, jours="5,6")  # seulement le week-end
    resume = tasks.executer_si_du(maintenant=_UN_LUNDI,  # un lundi
                                  recherche=_RechercheFausse(), client=_ClientFaux())
    assert resume == {"execute": False, "raison": "jour non autorisé"}


def test_active_sans_campagne_ne_fait_rien() -> None:
    r = ReglageAutomatisation.charger()
    r.active = True
    r.save()
    resume = tasks.executer_si_du(maintenant=_UN_LUNDI,
                                  recherche=_RechercheFausse(), client=_ClientFaux())
    assert resume == {"execute": False, "raison": "aucune campagne visée"}


# ── L'endpoint de réglages ────────────────────────────────────────────────────


def test_l_endpoint_exige_le_jeton() -> None:
    from django.test import Client
    assert Client().get(f"{BASE}/automatisation/").status_code in (401, 403)


def test_lire_puis_activer_avec_campagne(client_admin: Any) -> None:
    c = Campagne.objects.create(nom="Cible")
    d = json.loads(client_admin.get(f"{BASE}/automatisation/").content)
    assert d["active"] is False  # désactivée par défaut
    r = client_admin.put(
        f"{BASE}/automatisation/",
        data=json.dumps({"active": True, "campagne_id": str(c.id),
                         "prospects_par_jour": 15, "jours": [0, 1, 2, 3, 4]}),
        content_type="application/json",
    )
    assert r.status_code == 200
    d2 = json.loads(r.content)
    # 15, et non plus 30 : ce test enregistrait une valeur que la recherche
    # n'appliquait pas (elle plafonne à 25). Il vérifie qu'une valeur PERMISE
    # est gardée telle quelle ; le plafond est jugé par le test suivant.
    assert d2["active"] is True and d2["prospects_par_jour"] == 15
    assert d2["campagne_id"] == str(c.id) and d2["jours"] == [0, 1, 2, 3, 4]


def test_activer_sans_campagne_est_refuse(client_admin: Any) -> None:
    r = client_admin.put(
        f"{BASE}/automatisation/",
        data=json.dumps({"active": True}),
        content_type="application/json",
    )
    assert r.status_code == 400


def test_le_plafond_borne_les_prospects_par_jour(client_admin: Any) -> None:
    c = Campagne.objects.create(nom="Cible")
    r = client_admin.put(
        f"{BASE}/automatisation/",
        data=json.dumps({"active": True, "campagne_id": str(c.id), "prospects_par_jour": 999}),
        content_type="application/json",
    )
    # Ce test attendait 50 : il verrouillait le défaut (audit du 19/11/2026).
    # Le réglage acceptait 50 et l'écran écrivait « max 50 », mais la recherche
    # n'en crée jamais plus de `_MAX_PROSPECTS_PAR_RECHERCHE` (25) — la cliente
    # réglait 50 et en recevait 25. Le plafond du réglage EST celui de la
    # recherche : une seule source, lue ici au lieu d'être recopiée.
    from prospection import agents

    borne = json.loads(r.content)
    assert borne["prospects_par_jour"] == agents._MAX_PROSPECTS_PAR_RECHERCHE
    assert borne["prospects_par_jour_max"] == agents._MAX_PROSPECTS_PAR_RECHERCHE


# ── Une panne se TRACE, elle ne se rejoue pas chaque heure ────────────────────
#
# Audit du 19/11/2026 : `derniere_execution` n'était écrite qu'après la boucle
# et la recherche n'était entourée d'aucun `try`. Une panne ne laissait aucune
# trace : la tâche horaire rejouait donc la recherche toutes les heures en
# repayant ce qui précédait, et l'écran affichait « Activée ✓ » sans un mot.


class _RechercheEnPanne:
    """Compte ses appels, puis tombe : chaque appel est un passage payé."""

    def __init__(self) -> None:
        self.appels = 0

    def search(self, *, query: str, max_results: int = 5, **_: Any) -> SearchResponse:
        self.appels += 1
        raise RuntimeError("recherche web indisponible")


def test_une_panne_de_recherche_est_tracee_et_n_est_pas_rejouee_dans_l_heure() -> None:
    """Sur le code d'avant : l'exception remontait, rien n'était écrit, et le
    passage de l'heure suivante relançait — et repayait — la recherche."""
    campagne = Campagne.objects.create(nom="C", secteur="RH")
    _activer(campagne)
    panne = _RechercheEnPanne()

    resume = tasks.executer_si_du(maintenant=_UN_LUNDI, recherche=panne, client=_ClientFaux())

    assert resume["execute"] is True and resume["etat"] == "echouee"
    reglage = ReglageAutomatisation.charger()
    assert reglage.derniere_tentative == _UN_LUNDI
    assert reglage.dernier_etat == "echouee"
    assert "recherche web indisponible" in reglage.derniere_erreur
    # Une exécution ALLÉE AU BOUT, il n'y en a pas eu.
    assert reglage.derniere_execution is None

    # Une heure plus tard, puis deux : la panne n'est pas rejouée.
    for heure in (10, 11):
        suite = tasks.executer_si_du(
            maintenant=_UN_LUNDI.replace(hour=heure), recherche=panne, client=_ClientFaux()
        )
        assert suite["execute"] is False and "déjà tenté" in suite["raison"]
    assert panne.appels == 1


def test_le_lendemain_d_une_panne_la_tache_reessaie() -> None:
    """Contre-épreuve : un échec bloque la journée, pas l'automatisation."""
    campagne = Campagne.objects.create(nom="C", secteur="RH")
    _activer(campagne, prospects_par_jour=3)
    tasks.executer_si_du(maintenant=_UN_LUNDI, recherche=_RechercheEnPanne(), client=_ClientFaux())

    mardi = _UN_LUNDI.replace(day=20)
    resume = tasks.executer_si_du(maintenant=mardi, recherche=_RechercheFausse(),
                                  client=_ClientFaux())

    assert resume["execute"] is True and resume["etat"] == "reussie"
    reglage = ReglageAutomatisation.charger()
    assert reglage.derniere_execution == mardi
    assert reglage.derniere_erreur == ""


def test_la_tentative_est_inscrite_avant_le_premier_appel_paye() -> None:
    """Un conteneur tué en cours de route (déploiement) ne doit pas laisser la
    tâche repartir de zéro à l'heure suivante : la trace existe DÉJÀ quand la
    recherche commence."""
    campagne = Campagne.objects.create(nom="C", secteur="RH")
    _activer(campagne)
    vus: list[tuple[Any, str]] = []

    class _RechercheQuiRegarde(_RechercheFausse):
        def search(self, *, query: str, max_results: int = 5, **kw: Any) -> SearchResponse:
            en_base = ReglageAutomatisation.charger()
            vus.append((en_base.derniere_tentative, en_base.dernier_etat))
            return super().search(query=query, max_results=max_results, **kw)

    tasks.executer_si_du(maintenant=_UN_LUNDI, recherche=_RechercheQuiRegarde(),
                         client=_ClientFaux())

    assert vus and vus[0] == (_UN_LUNDI, "en_cours")


def test_une_tentative_restee_en_cours_se_lit_interrompue(client_admin: Any) -> None:
    """Un processus tué ne peut pas écrire qu'il est mort : l'écran le déduit."""
    from django.utils import timezone

    campagne = Campagne.objects.create(nom="C")
    _activer(campagne, derniere_tentative=timezone.now() - timedelta(hours=5),
             dernier_etat="en_cours")

    d = json.loads(client_admin.get(f"{BASE}/automatisation/").content)

    assert d["dernier_etat"] == "interrompue"


def test_l_ecran_recoit_l_etat_le_bilan_et_l_erreur(client_admin: Any) -> None:
    """Sur le code d'avant : `_reglage_dict` ne rendait que `derniere_execution`."""
    campagne = Campagne.objects.create(nom="C", secteur="RH")
    _activer(campagne, prospects_par_jour=3)
    tasks.executer_si_du(maintenant=_UN_LUNDI, recherche=_RechercheFausse(), client=_ClientFaux())

    d = json.loads(client_admin.get(f"{BASE}/automatisation/").content)

    assert d["dernier_etat"] == "reussie"
    assert d["derniere_tentative"] == _UN_LUNDI.isoformat()
    assert d["derniere_erreur"] == ""
    assert (d["dernier_bilan"]["crees"], d["dernier_bilan"]["rediges"]) == (3, 3)


def test_un_prospect_en_echec_rend_l_execution_partielle() -> None:
    """Un échec sur un prospect n'arrête pas les autres — mais il se VOIT."""
    campagne = Campagne.objects.create(nom="C", secteur="RH")
    _activer(campagne, prospects_par_jour=3)

    class _ClientQuiRateUneQualification(_ClientFaux):
        def __init__(self) -> None:
            self.qualifications = 0

        def complete_structured(self, *, outil_nom: str, **kw: Any) -> StructuredResult:
            if outil_nom == "qualifier_prospect":
                self.qualifications += 1
                if self.qualifications == 2:
                    raise RuntimeError("délai dépassé")
            return super().complete_structured(outil_nom=outil_nom, **kw)

    resume = tasks.executer_si_du(maintenant=_UN_LUNDI, recherche=_RechercheFausse(),
                                  client=_ClientQuiRateUneQualification())

    assert resume["etat"] == "partielle"
    assert (resume["crees"], resume["qualifies"], resume["rediges"], resume["echecs"]) == (
        3, 2, 2, 1,
    )
    assert "délai dépassé" in ReglageAutomatisation.charger().derniere_erreur


def test_le_maximum_affiche_est_le_plafond_reellement_applique(client_admin: Any) -> None:
    """Une seule source (règle 5). Sur le code d'avant, trois chiffres : l'écran
    écrivait « max 50 », le réglage acceptait 50, la recherche en créait 25."""
    from prospection import agents

    plafond = agents._MAX_PROSPECTS_PAR_RECHERCHE
    d = json.loads(client_admin.get(f"{BASE}/automatisation/").content)
    assert d["prospects_par_jour_max"] == plafond

    # Et ce plafond est bien celui que la tâche applique : on demande plus
    # d'organisations qu'il n'en autorise, on n'en obtient que `plafond`.
    class _ClientGenereux(_ClientFaux):
        def complete_structured(self, *, outil_nom: str, **kw: Any) -> StructuredResult:
            if outil_nom == "extraire_prospects":
                return StructuredResult(
                    payload={"prospects": [
                        {"raison_sociale": f"Structure {i}", "email": f"s{i}@ex.fr"}
                        for i in range(plafond + 10)
                    ]},
                    input_tokens=1, output_tokens=1, model="claude-opus",
                )
            return super().complete_structured(outil_nom=outil_nom, **kw)

    campagne = Campagne.objects.create(nom="C", secteur="RH")
    _activer(campagne, prospects_par_jour=plafond + 10)  # un réglage d'avant l'audit
    resume = tasks.executer_si_du(maintenant=_UN_LUNDI, recherche=_RechercheFausse(),
                                  client=_ClientGenereux())

    assert resume["crees"] == plafond
    # Le réglage hérité s'affiche tel qu'il sera appliqué, pas tel qu'il fut saisi.
    d = json.loads(client_admin.get(f"{BASE}/automatisation/").content)
    assert d["prospects_par_jour"] == plafond


def test_enregistrer_les_reglages_n_efface_pas_la_trace_de_la_tache(client_admin: Any) -> None:
    """Les réglages s'enregistrent PENDANT que la tâche tourne : sa tentative reste.

    L'écran est chargé, puis la tâche inscrit sa tentative, puis l'écran
    enregistre. Un `save()` entier réécrivait la trace avec ce qu'il avait lu
    avant — et l'heure suivante relançait la recherche.
    """
    from unittest import mock

    campagne = Campagne.objects.create(nom="C", secteur="RH")
    _activer(campagne)
    charger = ReglageAutomatisation.charger

    def charger_puis_la_tache_demarre() -> ReglageAutomatisation:
        lu = charger()  # ce que la requête a lu…
        ReglageAutomatisation.objects.filter(pk=lu.pk).update(  # …avant que la tâche écrive
            derniere_tentative=_UN_LUNDI, dernier_etat="en_cours"
        )
        return lu

    with mock.patch.object(ReglageAutomatisation, "charger", charger_puis_la_tache_demarre):
        r = client_admin.put(
            f"{BASE}/automatisation/", data=json.dumps({"prospects_par_jour": 5}),
            content_type="application/json",
        )

    assert r.status_code == 200
    en_base = ReglageAutomatisation.objects.get()
    assert en_base.prospects_par_jour == 5
    assert (en_base.derniere_tentative, en_base.dernier_etat) == (_UN_LUNDI, "en_cours")

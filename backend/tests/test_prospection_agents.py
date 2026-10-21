"""Les trois agents de prospection (phase 3) : recherche, qualification, rédaction.

On leur injecte des doublures déterministes (aucun réseau, aucun coût) et on
vérifie le CÂBLAGE et l'INVARIANT : les agents ne produisent que des données —
des `Prospect`, un score, des `Message` en BROUILLON — et JAMAIS un envoi. La
contre-épreuve de chaque test de rédaction : aucun message n'est passé validé
ou envoyé tout seul, aucun événement n'a été tracé.
"""
from __future__ import annotations

from typing import Any

import pytest
from prospection import agents
from prospection.models import (
    Campagne,
    Evenement,
    Message,
    Prospect,
    Sequence,
    StatutMessage,
    StatutProspect,
)

from integrations.claude import StructuredResult
from integrations.search import SearchResponse, SearchResult

pytestmark = pytest.mark.django_db


class _ClientFaux:
    """Client structuré déterministe : rend une charge figée, note ses appels."""

    def __init__(self, charges: dict[str, dict[str, Any]]) -> None:
        self._charges = charges
        self.appels: list[str] = []
        self.systemes: list[str] = []

    def complete_structured(
        self, *, outil_nom: str, system: str = "", **_: Any
    ) -> StructuredResult:
        self.appels.append(outil_nom)
        self.systemes.append(system)
        return StructuredResult(
            payload=dict(self._charges.get(outil_nom, {})),
            input_tokens=1,
            output_tokens=1,
            model="claude-sonnet",
        )


class _RechercheFausse:
    """Recherche web déterministe : rend des résultats figés, note ses requêtes."""

    def __init__(self, resultats: tuple[SearchResult, ...]) -> None:
        self._resultats = resultats
        self.requetes: list[str] = []

    def search(self, *, query: str, max_results: int = 5, **_: Any) -> SearchResponse:
        self.requetes.append(query)
        return SearchResponse(query=query, results=self._resultats[:max_results])


def _campagne(**kw: Any) -> Campagne:
    params = {"nom": "Cabinets RH Lyon", "secteur": "RH", "zone": "Lyon"}
    params.update(kw)
    return Campagne.objects.create(**params)


def _resultats_web() -> tuple[SearchResult, ...]:
    return tuple(
        SearchResult(title=f"Entreprise {i}", url=f"https://ex{i}.fr", content="…")
        for i in range(3)
    )


# ── Agent 1 : recherche ──────────────────────────────────────────────────────


def test_la_recherche_cree_des_prospects_et_rien_ne_part() -> None:
    campagne = _campagne()
    client = _ClientFaux({"extraire_prospects": {"prospects": [
        {"raison_sociale": "Alpha RH", "email": "contact@alpha.fr", "secteur": "RH"},
        {"raison_sociale": "Beta Conseil", "site_web": "https://beta.fr"},
    ]}})
    crees = agents.rechercher_des_prospects(
        campagne, recherche=_RechercheFausse(_resultats_web()), client=client
    )

    assert len(crees) == 2
    assert {p.raison_sociale for p in crees} == {"Alpha RH", "Beta Conseil"}
    assert all(p.statut == StatutProspect.NOUVEAU for p in crees)
    assert all(p.source == "recherche-ia" for p in crees)
    # Un prospect sans e-mail dans les extraits reste sans e-mail : rien n'est inventé.
    beta = Prospect.objects.get(raison_sociale="Beta Conseil")
    assert beta.email == ""
    # L'invariant : la recherche ne prépare ni n'envoie aucun message.
    assert Message.objects.count() == 0
    assert Evenement.objects.count() == 0


def test_la_recherche_dedoublonne_dans_la_campagne() -> None:
    campagne = _campagne()
    charge = {"extraire_prospects": {"prospects": [
        {"raison_sociale": "Alpha RH", "email": "contact@alpha.fr"},
    ]}}
    agents.rechercher_des_prospects(campagne, recherche=_RechercheFausse(_resultats_web()),
                                    client=_ClientFaux(charge))
    # Deuxième passage : même fiche, aucun doublon créé.
    crees = agents.rechercher_des_prospects(campagne, recherche=_RechercheFausse(_resultats_web()),
                                            client=_ClientFaux(charge))
    assert crees == []
    assert Prospect.objects.filter(campagne=campagne, raison_sociale="Alpha RH").count() == 1


def test_la_recherche_sans_fiche_ne_cree_rien() -> None:
    campagne = _campagne()
    crees = agents.rechercher_des_prospects(
        campagne, recherche=_RechercheFausse(_resultats_web()), client=_ClientFaux({}),
    )
    assert crees == []
    assert Prospect.objects.count() == 0


# ── Agent 2 : qualification ──────────────────────────────────────────────────


def test_la_qualification_pose_un_score_et_qualifie() -> None:
    campagne = _campagne()
    prospect = Prospect.objects.create(campagne=campagne, raison_sociale="Alpha RH",
                                       statut=StatutProspect.NOUVEAU)
    client = _ClientFaux({"qualifier_prospect": {"score": 72, "raison": "PME en croissance"}})

    agents.qualifier_un_prospect(prospect, client=client)
    prospect.refresh_from_db()

    assert prospect.score_adequation == 72
    assert prospect.raison_score == "PME en croissance"
    assert prospect.statut == StatutProspect.QUALIFIE


def test_la_qualification_borne_le_score() -> None:
    prospect = Prospect.objects.create(raison_sociale="Hors bornes")
    agents.qualifier_un_prospect(
        prospect, client=_ClientFaux({"qualifier_prospect": {"score": 150, "raison": "x"}})
    )
    prospect.refresh_from_db()
    assert prospect.score_adequation == 100


def test_la_qualification_ne_retrograde_pas_un_contacte() -> None:
    prospect = Prospect.objects.create(raison_sociale="Déjà contacté",
                                       statut=StatutProspect.CONTACTE)
    agents.qualifier_un_prospect(
        prospect, client=_ClientFaux({"qualifier_prospect": {"score": 40, "raison": "y"}})
    )
    prospect.refresh_from_db()
    assert prospect.score_adequation == 40
    assert prospect.statut == StatutProspect.CONTACTE


# ── Agent 3 : rédaction ──────────────────────────────────────────────────────


def _cinq_messages() -> dict[str, Any]:
    return {"rediger_messages": {"messages": [
        {"objet": f"Objet {i}", "corps": f"<p>Corps {i}</p>"} for i in range(5)
    ]}}


def test_la_redaction_ne_produit_que_des_brouillons() -> None:
    campagne = _campagne()
    prospect = Prospect.objects.create(campagne=campagne, raison_sociale="Alpha RH",
                                       email="contact@alpha.fr")
    crees = agents.rediger_les_messages(prospect, client=_ClientFaux(_cinq_messages()))

    assert len(crees) == 5  # un premier message + quatre relances
    assert all(m.statut == StatutMessage.BROUILLON for m in crees)
    # CONTRE-ÉPREUVE de l'invariant : rien n'est validé, rien n'est parti.
    assert all(m.valide_par == "" and m.valide_le is None for m in crees)
    assert Message.objects.filter(statut=StatutMessage.ENVOYE).count() == 0
    assert Message.objects.filter(statut=StatutMessage.VALIDE).count() == 0
    assert Evenement.objects.count() == 0
    # Le prospect n'a pas été « contacté » par la simple rédaction.
    prospect.refresh_from_db()
    assert prospect.statut != StatutProspect.CONTACTE


def test_la_redaction_suit_la_sequence_de_la_campagne() -> None:
    campagne = _campagne()
    for ordre in range(3):
        Sequence.objects.create(campagne=campagne, ordre=ordre, delai_jours=ordre * 3)
    prospect = Prospect.objects.create(campagne=campagne, raison_sociale="Alpha RH",
                                       email="contact@alpha.fr")
    crees = agents.rediger_les_messages(prospect, client=_ClientFaux(_cinq_messages()))

    # Trois étapes de séquence => trois messages, chacun rattaché à son étape.
    assert len(crees) == 3
    ordres = []
    for m in crees:
        assert m.sequence is not None
        ordres.append(m.sequence.ordre)
    assert ordres == [0, 1, 2]


def test_la_redaction_ne_double_pas_une_file_existante() -> None:
    campagne = _campagne()
    prospect = Prospect.objects.create(campagne=campagne, raison_sociale="Alpha RH",
                                       email="contact@alpha.fr")
    premiers = agents.rediger_les_messages(prospect, client=_ClientFaux(_cinq_messages()))
    # Deuxième appel sans `remplacer` : on récupère la file, on ne recrée rien.
    seconds = agents.rediger_les_messages(prospect, client=_ClientFaux(_cinq_messages()))
    assert {m.id for m in premiers} == {m.id for m in seconds}
    assert Message.objects.filter(prospect=prospect).count() == 5


def test_la_redaction_remplace_sur_demande() -> None:
    campagne = _campagne()
    prospect = Prospect.objects.create(campagne=campagne, raison_sociale="Alpha RH",
                                       email="contact@alpha.fr")
    anciens = agents.rediger_les_messages(prospect, client=_ClientFaux(_cinq_messages()))
    nouveaux = agents.rediger_les_messages(
        prospect, remplacer=True, client=_ClientFaux(_cinq_messages())
    )
    # Les anciens brouillons sont annulés, de nouveaux brouillons les remplacent.
    assert {m.id for m in anciens}.isdisjoint({m.id for m in nouveaux})
    assert Message.objects.filter(prospect=prospect, statut=StatutMessage.ANNULE).count() == 5
    assert Message.objects.filter(prospect=prospect, statut=StatutMessage.BROUILLON).count() == 5


def test_la_redaction_borne_le_nombre_de_messages() -> None:
    campagne = _campagne()
    prospect = Prospect.objects.create(campagne=campagne, raison_sociale="Alpha RH",
                                       email="contact@alpha.fr")
    # Le modèle rend 5 messages mais on n'en demande qu'un + une relance.
    crees = agents.rediger_les_messages(prospect, nb_relances=1,
                                        client=_ClientFaux(_cinq_messages()))
    assert len(crees) == 2


# ── Les agents sont « entraînés » sur le brief des cibles ─────────────────────


def test_les_agents_portent_le_brief_des_cibles() -> None:
    campagne = _campagne()
    prospect = Prospect.objects.create(campagne=campagne, raison_sociale="BGE Lille",
                                       email="contact@bge.fr")

    cq = _ClientFaux({"qualifier_prospect": {"score": 80, "raison": "x"}})
    agents.qualifier_un_prospect(prospect, client=cq)
    assert "Initiative France" in cq.systemes[0]  # la cible n°1 du brief

    cr = _ClientFaux(_cinq_messages())
    agents.rediger_les_messages(prospect, client=cr)
    systeme = cr.systemes[0]
    assert "Evangeline" in systeme and "nous" in systeme  # règle de ton « je », pas « nous »
    assert "démonstration de 10 minutes" in systeme  # le but d'un message

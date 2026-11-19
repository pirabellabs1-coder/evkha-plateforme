"""Une réponse du modèle SANS appel d'outil n'est pas un succès (audit du 19/11/2026).

Le choix d'outil n'est plus forcé (`integrations.claude.complete_structured`) :
un modèle qui répond en texte, ou dont la sortie est coupée, rend une charge
VIDE. Les agents la traitaient comme « rien trouvé » :

- la recherche rendait 0 prospect sans un mot ;
- la qualification passait le prospect QUALIFIÉ sans lui donner de note ;
- la rédaction, avec `remplacer`, annulait la file existante puis ne créait rien.

On distingue désormais `{}` (rien rendu : erreur nommée, rien n'est modifié) de
`{"prospects": []}` (zéro trouvé : légitime, rendu avec son compte).
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from prospection import agents
from prospection.models import (
    Campagne,
    Message,
    Prospect,
    StatutMessage,
    StatutProspect,
)

from integrations.claude import StructuredResult
from integrations.search import SearchResponse, SearchResult

pytestmark = pytest.mark.django_db

BASE = "/api/dashboard/prospection"


class _ClientFaux:
    """Rend une charge figée par outil ; note ses appels. `{}` = pas d'appel d'outil."""

    def __init__(self, charges: dict[str, dict[str, Any]], stop_reason: str = "end_turn") -> None:
        self._charges = charges
        self._stop_reason = stop_reason
        self.appels: list[str] = []

    def complete_structured(self, *, outil_nom: str, **_: Any) -> StructuredResult:
        self.appels.append(outil_nom)
        return StructuredResult(
            payload=dict(self._charges.get(outil_nom, {})),
            input_tokens=1, output_tokens=1, model="claude-opus",
            stop_reason=self._stop_reason,
        )


class _RechercheFausse:
    def search(self, *, query: str, max_results: int = 5, **_: Any) -> SearchResponse:
        return SearchResponse(
            query=query, results=(SearchResult(title="X", url="https://x.fr", content="…"),)
        )


def _campagne() -> Campagne:
    return Campagne.objects.create(nom="BGE Lille", secteur="Accompagnement", zone="Lille")


def _poster(client_admin: Any, url: str, corps: dict[str, Any]) -> Any:
    return client_admin.post(url, data=json.dumps(corps), content_type="application/json")


def _doubler(monkeypatch: Any, client: _ClientFaux) -> None:
    monkeypatch.setattr("integrations.claude.get_claude_client", lambda: client)
    monkeypatch.setattr("integrations.search.get_search_client", _RechercheFausse)


# ── Recherche ────────────────────────────────────────────────────────────────


def test_une_recherche_sans_appel_d_outil_leve_une_erreur_nommee() -> None:
    """Sur le code d'avant : `[]` — le même résultat qu'une recherche sans cible."""
    with pytest.raises(RuntimeError, match="exploitable") as levee:
        agents.rechercher_des_prospects(
            _campagne(), recherche=_RechercheFausse(), client=_ClientFaux({})
        )

    assert type(levee.value).__name__ == "ReponseInexploitableError"
    assert "en texte" in str(levee.value)
    assert Prospect.objects.count() == 0


def test_une_recherche_tronquee_dit_qu_elle_a_ete_coupee() -> None:
    with pytest.raises(RuntimeError, match="coupée"):
        agents.rechercher_des_prospects(
            _campagne(),
            recherche=_RechercheFausse(),
            client=_ClientFaux({}, stop_reason="max_tokens"),
        )


def test_une_charge_sans_la_cle_attendue_leve_aussi() -> None:
    """Une charge non vide mais à côté (`resultats` au lieu de `prospects`)."""
    client = _ClientFaux({"extraire_prospects": {"resultats": [{"raison_sociale": "A"}]}})

    with pytest.raises(RuntimeError, match="prospects"):
        agents.rechercher_des_prospects(_campagne(), recherche=_RechercheFausse(), client=client)

    assert Prospect.objects.count() == 0


def test_l_ecran_recoit_un_502_lisible_et_non_un_zero_muet(
    client_admin: Any, monkeypatch: Any
) -> None:
    """Sur le code d'avant : 200 et `crees: 0`, que l'écran n'affichait même pas."""
    campagne = _campagne()
    _doubler(monkeypatch, _ClientFaux({}))

    reponse = _poster(client_admin, f"{BASE}/campagnes/{campagne.id}/rechercher/",
                      {"confirmer": True})

    assert reponse.status_code == 502, reponse.content
    erreur = json.loads(reponse.content)["erreur"]
    # Le message de l'agent, écrit pour l'humain — pas la formule passe-partout.
    assert "rien rendu d'exploitable" in erreur and "relancez" in erreur
    assert Prospect.objects.count() == 0


def test_zero_trouve_est_un_resultat_rendu_avec_son_compte(
    client_admin: Any, monkeypatch: Any
) -> None:
    """Contre-épreuve : `{"prospects": []}` est un zéro RÉEL — 200, et il se dit.

    C'est le cas voulu d'une cible hors brief : le correctif ne doit pas en
    faire une erreur.
    """
    campagne = _campagne()
    _doubler(monkeypatch, _ClientFaux({"extraire_prospects": {"prospects": []}}))

    reponse = _poster(client_admin, f"{BASE}/campagnes/{campagne.id}/rechercher/",
                      {"confirmer": True})

    assert reponse.status_code == 200, reponse.content
    bilan = json.loads(reponse.content)
    assert bilan["crees"] == 0 and bilan["prospects"] == []
    assert bilan["proposees"] == 0 and bilan["deja_connues"] == 0


def test_zero_cree_parce_que_tout_est_deja_connu_se_distingue(
    client_admin: Any, monkeypatch: Any
) -> None:
    """« 0 créé » parce que la campagne les connaît déjà n'est pas « rien trouvé »."""
    campagne = _campagne()
    Prospect.objects.create(campagne=campagne, raison_sociale="BGE Hauts-de-France")
    _doubler(monkeypatch, _ClientFaux({"extraire_prospects": {"prospects": [
        {"raison_sociale": "BGE Hauts de France"},
    ]}}))

    reponse = _poster(client_admin, f"{BASE}/campagnes/{campagne.id}/rechercher/",
                      {"confirmer": True})

    bilan = json.loads(reponse.content)
    assert (bilan["crees"], bilan["proposees"], bilan["deja_connues"]) == (0, 1, 1)


def test_une_limite_illisible_ne_rend_pas_un_500(client_admin: Any, monkeypatch: Any) -> None:
    campagne = _campagne()
    _doubler(monkeypatch, _ClientFaux({"extraire_prospects": {"prospects": []}}))

    reponse = _poster(client_admin, f"{BASE}/campagnes/{campagne.id}/rechercher/",
                      {"confirmer": True, "limite": "beaucoup"})

    assert reponse.status_code == 200


# ── Qualification ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "charge",
    [{}, {"raison": "bon profil"}, {"score": "élevé", "raison": "bon profil"}],
    ids=["charge-vide", "sans-note", "note-illisible"],
)
def test_un_prospect_n_est_qualifie_que_s_il_a_recu_une_note(charge: dict[str, Any]) -> None:
    """Sur le code d'avant : QUALIFIÉ, `score_adequation` vide — jugé par personne."""
    prospect = Prospect.objects.create(raison_sociale="Alpha", statut=StatutProspect.NOUVEAU)

    with pytest.raises(RuntimeError, match="exploitable"):
        agents.qualifier_un_prospect(
            prospect, client=_ClientFaux({"qualifier_prospect": charge})
        )

    prospect.refresh_from_db()
    assert prospect.statut == StatutProspect.NOUVEAU
    assert prospect.score_adequation is None
    assert prospect.raison_score == ""


def test_une_note_de_zero_est_une_note() -> None:
    """Contre-épreuve : 0 (profil exclu) est une information, pas une absence."""
    prospect = Prospect.objects.create(raison_sociale="Big Four", statut=StatutProspect.NOUVEAU)

    agents.qualifier_un_prospect(
        prospect, client=_ClientFaux({"qualifier_prospect": {"score": 0, "raison": "concurrent"}})
    )

    prospect.refresh_from_db()
    assert prospect.score_adequation == 0
    assert prospect.statut == StatutProspect.QUALIFIE


def test_la_qualification_sans_outil_rend_un_502(client_admin: Any, monkeypatch: Any) -> None:
    prospect = Prospect.objects.create(raison_sociale="Alpha", statut=StatutProspect.NOUVEAU)
    _doubler(monkeypatch, _ClientFaux({}))

    reponse = _poster(client_admin, f"{BASE}/prospects/{prospect.id}/qualifier/",
                      {"confirmer": True})

    assert reponse.status_code == 502
    prospect.refresh_from_db()
    assert prospect.statut == StatutProspect.NOUVEAU


# ── Rédaction ────────────────────────────────────────────────────────────────


def _cinq_messages() -> dict[str, Any]:
    return {"rediger_messages": {"messages": [
        {"objet": f"Objet {i}", "corps": f"<p>Corps {i}</p>"} for i in range(5)
    ]}}


@pytest.mark.parametrize(
    "charges",
    [
        {},
        {"rediger_messages": {"messages": []}},
        {"rediger_messages": {"messages": [{"objet": "Sans corps"}]}},
    ],
    ids=["charge-vide", "liste-vide", "aucun-message-complet"],
)
def test_une_redaction_sans_message_leve_et_ne_cree_rien(charges: dict[str, Any]) -> None:
    """Sur le code d'avant : `[]`, et l'écran annonçait une rédaction sans rien montrer."""
    prospect = Prospect.objects.create(raison_sociale="Alpha", email="contact@alpha.fr")

    with pytest.raises(RuntimeError, match="exploitable"):
        agents.rediger_les_messages(prospect, client=_ClientFaux(charges))

    assert Message.objects.count() == 0


def test_remplacer_ne_detruit_pas_la_file_quand_le_modele_ne_rend_rien() -> None:
    """Le pire du défaut : la file était annulée AVANT l'appel au modèle.

    Sur le code d'avant, les cinq brouillons — parfois retouchés à la main —
    étaient annulés, puis remplacés par rien.
    """
    prospect = Prospect.objects.create(raison_sociale="Alpha", email="contact@alpha.fr")
    anciens = agents.rediger_les_messages(prospect, client=_ClientFaux(_cinq_messages()))
    assert len(anciens) == 5

    with pytest.raises(RuntimeError, match="exploitable"):
        agents.rediger_les_messages(prospect, remplacer=True, client=_ClientFaux({}))

    statuts = set(Message.objects.filter(prospect=prospect).values_list("statut", flat=True))
    assert statuts == {StatutMessage.BROUILLON}
    assert Message.objects.filter(prospect=prospect).count() == 5


def test_remplacer_annule_bien_l_ancienne_file_quand_la_nouvelle_existe() -> None:
    """Contre-épreuve : le remplacement réussi garde son comportement."""
    prospect = Prospect.objects.create(raison_sociale="Alpha", email="contact@alpha.fr")
    agents.rediger_les_messages(prospect, client=_ClientFaux(_cinq_messages()))

    nouveaux = agents.rediger_les_messages(
        prospect, remplacer=True, client=_ClientFaux(_cinq_messages())
    )

    assert len(nouveaux) == 5
    assert Message.objects.filter(prospect=prospect, statut=StatutMessage.ANNULE).count() == 5
    assert Message.objects.filter(prospect=prospect, statut=StatutMessage.BROUILLON).count() == 5


def test_une_reponse_coupee_qui_porte_la_cle_n_est_pas_un_resultat() -> None:
    """Relecture du 19/11/2026. Une sortie coupée porte souvent la clé attendue,
    avec une liste dont le dernier élément s'arrête au milieu : la coupure se
    juge AVANT la présence de la clé. Le test voisin ne couvrait que la charge
    vide — celle-ci passait pour un succès et créait des fiches."""
    client = _ClientFaux(
        {"extraire_prospects": {"prospects": [{"raison_sociale": "Cabinet coup"}]}},
        stop_reason="max_tokens",
    )

    with pytest.raises(RuntimeError, match="coupée"):
        agents.rechercher_des_prospects(_campagne(), recherche=_RechercheFausse(), client=client)

    assert Prospect.objects.count() == 0

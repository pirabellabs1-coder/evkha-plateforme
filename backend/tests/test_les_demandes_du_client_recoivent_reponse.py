"""Une étude complète en apparence peut laisser une question sans réponse.

## Le retour qui a créé ce contrôle

Cliente, 09/08/2026 : « éviter d'avoir une étude très complète en apparence mais
qui laisse certaines questions initiales insuffisamment traitées ».

C'est un angle mort exact. Le gate regarde la troncature et la cohérence
chiffrée ; la conformité regarde la forme ; la vérification du socle regarde les
chiffres. **Personne ne relisait le brief du client pour se demander si on lui
avait répondu.** Règle 9, dans sa forme la plus littérale.

## Pourquoi PARTIEL fait tout le travail

Sans lui, tout devient OUI : une étude de vingt-trois chapitres « aborde » à peu
près n'importe quel sujet. C'est précisément l'illusion décrite — complète en
apparence. Le statut du milieu est celui qui perce.

## Le découpage des questions, et le piège qu'il désamorce

Le brief écrit les demandes en vrac. Découper trop finement ferait sortir « RSE »
comme une question, déclarée non couverte à jamais : un motif faux, envoyé
corriger ce qui n'était pas cassé (règle 2). D'où le seuil de longueur.
"""
from __future__ import annotations

from typing import Any

import pytest

from generation.couverture import (
    LONGUEUR_MINIMALE,
    controler_la_couverture,
    questions_du_brief,
)

DOCUMENT = "Chapitre 1. Le marché progresse de 3,4 % par an depuis 2022."


class _Resultat:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload


class _Client:
    def __init__(self, reponses: list[dict[str, str]]) -> None:
        self._reponses = reponses
        self.appels = 0

    def complete_structured(self, **_: Any) -> _Resultat:
        self.appels += 1
        return _Resultat({"reponses": self._reponses})


class _ClientEnPanne:
    def complete_structured(self, **_: Any) -> _Resultat:
        msg = "API indisponible"
        raise RuntimeError(msg)


# ── Le découpage du brief ────────────────────────────────────────────────────


def test_les_demandes_sont_decoupees_en_questions_jugeables() -> None:
    variables = {
        "DEMANDES_SPECIFIQUES": (
            "Comparer le canal digital des concurrents. "
            "Quelle politique de prix adopter ?\n"
            "Analyser la saisonnalité des ventes."
        )
    }

    questions = questions_du_brief(variables)

    assert len(questions) == 3
    assert questions[1].startswith("Quelle politique de prix")


def test_une_liste_est_acceptee_comme_une_chaine() -> None:
    """Le brief écrit tantôt une phrase, tantôt une liste."""
    variables = {"DEMANDES_SPECIFIQUES": [
        "Comparer le canal digital des concurrents",
        "Analyser la politique tarifaire du secteur",
    ]}

    assert len(questions_du_brief(variables)) == 2


@pytest.mark.parametrize("bribe", ["RSE", "prix", "digital", "B2B"])
def test_un_mot_cle_n_est_pas_une_question(bribe: str) -> None:
    """CONTRE-ÉPREUVE : « RSE » serait déclaré non couvert à jamais.

    Un motif faux envoie corriger ce qui n'était pas cassé, et il ne s'éteint
    jamais tout seul (règle 2).
    """
    assert len(bribe) < LONGUEUR_MINIMALE
    assert questions_du_brief({"DEMANDES_SPECIFIQUES": bribe}) == []


def test_un_brief_sans_demande_ne_produit_aucune_question() -> None:
    assert questions_du_brief({"SECTEUR": "mode", "PAYS": "France"}) == []
    assert questions_du_brief(None) == []


def test_les_doublons_sont_ecartes() -> None:
    variables = {
        "DEMANDES_SPECIFIQUES": "Comparer le canal digital des concurrents.",
        "ELEMENTS_A_RETENIR": "comparer le canal digital des concurrents",
    }

    assert len(questions_du_brief(variables)) == 1


# ── Le verdict ───────────────────────────────────────────────────────────────


QUESTION = "Comparer le canal digital des concurrents"


def test_une_question_traitee_est_comptee_comme_telle() -> None:
    client = _Client([{"question": QUESTION, "statut": "oui", "manque": ""}])

    rapport = controler_la_couverture(
        client=client,
        variables={"DEMANDES_SPECIFIQUES": QUESTION},
        document=DOCUMENT,
    )

    assert rapport.traitees == [QUESTION]
    assert rapport.toutes_traitees


@pytest.mark.parametrize("statut", ["partiel", "non"])
def test_une_question_insuffisamment_traitee_sort_avec_CE_QUI_MANQUE(
    statut: str,
) -> None:
    """Un manque sans son remède n'aide personne à le combler (règle 2)."""
    client = _Client([{
        "question": QUESTION,
        "statut": statut,
        "manque": "aucun chiffre sur la part du canal en ligne des concurrents",
    }])

    rapport = controler_la_couverture(
        client=client,
        variables={"DEMANDES_SPECIFIQUES": QUESTION},
        document=DOCUMENT,
    )

    assert rapport.insuffisantes == [
        (QUESTION, statut, "aucun chiffre sur la part du canal en ligne des concurrents")
    ]
    assert not rapport.toutes_traitees


def test_une_question_oubliee_par_le_controle_compte_comme_non_traitee() -> None:
    """Le silence ne vaut pas approbation — ici comme partout ailleurs."""
    client = _Client([])

    rapport = controler_la_couverture(
        client=client,
        variables={"DEMANDES_SPECIFIQUES": QUESTION},
        document=DOCUMENT,
    )

    assert rapport.insuffisantes[0][1] == "non"
    assert "non examinée" in rapport.insuffisantes[0][2]


def test_un_brief_sans_demande_n_appelle_personne() -> None:
    """Rien à couvrir n'est pas la même chose que tout est couvert."""
    client = _Client([])

    rapport = controler_la_couverture(
        client=client, variables={"SECTEUR": "mode"}, document=DOCUMENT
    )

    assert rapport.passe_executee is True
    assert rapport.traitees == []
    assert client.appels == 0


def test_une_panne_du_controle_se_voit_au_lieu_de_se_taire() -> None:
    rapport = controler_la_couverture(
        client=_ClientEnPanne(),
        variables={"DEMANDES_SPECIFIQUES": QUESTION},
        document=DOCUMENT,
    )

    assert rapport.passe_executee is False
    assert "RuntimeError" in rapport.motif_non_executee
    assert not rapport.toutes_traitees


def test_un_document_vide_ne_se_declare_pas_couvert() -> None:
    rapport = controler_la_couverture(
        client=_Client([]),
        variables={"DEMANDES_SPECIFIQUES": QUESTION},
        document="   ",
    )

    assert rapport.passe_executee is False
    assert "vide" in rapport.motif_non_executee


def test_le_rapport_se_lit_dans_un_incident() -> None:
    client = _Client([{"question": QUESTION, "statut": "partiel", "manque": "chiffres"}])

    rapport = controler_la_couverture(
        client=client,
        variables={"DEMANDES_SPECIFIQUES": QUESTION},
        document=DOCUMENT,
    )
    details = rapport.as_details()

    assert details["insuffisantes"][0]["statut"] == "partiel"
    assert details["insuffisantes"][0]["manque"] == "chiffres"

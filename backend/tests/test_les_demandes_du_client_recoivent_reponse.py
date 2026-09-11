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
    candidats_du_brief,
    controler_la_couverture,
    questions_du_brief,
)

DOCUMENT = "Chapitre 1. Le marché progresse de 3,4 % par an depuis 2022."


class _Resultat:
    def __init__(self, payload: dict[str, Any], stop_reason: str = "end_turn") -> None:
        self.payload = payload
        self.stop_reason = stop_reason


class _Client:
    def __init__(self, reponses: list[dict[str, Any]]) -> None:
        self._reponses = reponses
        self.appels = 0
        self.max_tokens = 0
        self.prompt = ""

    def complete_structured(self, **kwargs: Any) -> _Resultat:
        self.appels += 1
        self.max_tokens = int(kwargs.get("max_tokens", 0))
        self.prompt = str(kwargs.get("prompt", ""))
        demandes = [r for r in self._reponses if "statut" in r]
        contexte = [r["n"] for r in self._reponses if "statut" not in r]
        return _Resultat({"contexte": contexte, "demandes": demandes})


def _demande(n: int, statut: str, manque: str = "") -> dict[str, Any]:
    return {"n": n, "statut": statut, "manque": manque}


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
    client = _Client([_demande(1, "oui")])

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
    client = _Client([_demande(
        1, statut, "aucun chiffre sur la part du canal en ligne des concurrents"
    )])

    rapport = controler_la_couverture(
        client=client,
        variables={"DEMANDES_SPECIFIQUES": QUESTION},
        document=DOCUMENT,
    )

    assert rapport.insuffisantes == [
        (QUESTION, statut, "aucun chiffre sur la part du canal en ligne des concurrents")
    ]
    assert not rapport.toutes_traitees


def test_une_question_oubliee_par_le_controle_n_est_ni_traitee_ni_jugee() -> None:
    """Le silence ne vaut pas approbation — ni condamnation.

    Ce test verrouillait la moitié du défaut : un passage que le contrôle
    n'avait pas lu sortait « insuffisamment traité ». C'est ainsi que le dossier `f7f2fad9` a
    reçu « 87 demandes insuffisamment traitées » dont aucune n'avait été
    examinée. La moitié juste est gardée — jamais traitée par défaut ; la
    moitié fausse est retirée — jamais jugée par défaut.
    """
    client = _Client([])

    rapport = controler_la_couverture(
        client=client,
        variables={"DEMANDES_SPECIFIQUES": QUESTION},
        document=DOCUMENT,
    )

    assert rapport.traitees == []
    assert rapport.insuffisantes == []
    assert rapport.non_examinees == [QUESTION]
    assert not rapport.toutes_traitees
    # Un seul passage, et il manque : la passe ne peut rien conclure.
    assert rapport.passe_executee is False
    assert "non examiné" in rapport.motif_non_executee


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
    client = _Client([_demande(1, "partiel", "chiffres")])

    rapport = controler_la_couverture(
        client=client,
        variables={"DEMANDES_SPECIFIQUES": QUESTION},
        document=DOCUMENT,
    )
    details = rapport.as_details()

    assert details["insuffisantes"][0]["statut"] == "partiel"
    assert details["insuffisantes"][0]["manque"] == "chiffres"



# ── Ce que le dossier réel `f7f2fad9` a montré (08/09/2026) ─────────────────────
#
# L'incident annonçait 87 demandes insuffisamment traitées ; aucune n'avait été
# examinée. La cliente a refait la vérification à la main et trouvé ce que le
# contrôle aurait dû trouver : la segmentation de la base d'abonnés.


def test_une_reponse_reformulee_est_rattachee_par_son_numero() -> None:
    """Le rapprochement se faisait par l'égalité EXACTE de la question.

    Une virgule reformulée par le modèle, et la réponse était perdue — c'est
    ce qui a vidé les 87 verdicts. Le numéro, lui, ne se reformule pas.
    """
    variables = {"DEMANDES_SPECIFIQUES": "Quelle cible attaquer en premier ?"}
    client = _Client([_demande(1, "oui")])

    rapport = controler_la_couverture(
        client=client, variables=variables, document=DOCUMENT
    )

    assert rapport.traitees == ["Quelle cible attaquer en premier ?"]
    assert rapport.non_examinees == []


def test_une_demande_glissee_dans_un_champ_descriptif_est_examinee() -> None:
    """La répartition des abonnés par formule était dans `SAISONNALITE`.

    Une liste fermée de champs « de demande » ne l'a jamais lue. Tout champ de
    texte libre est candidat ; le modèle sépare la demande du contexte.
    """
    variables = {
        "SAISONNALITE": (
            "Ces données doivent être actualisées en fonction du nombre actuel "
            "d'abonnés et de leur répartition entre les différentes formules."
        ),
    }

    assert candidats_du_brief(variables), "le passage n'a même pas été lu"
    client = _Client([_demande(1, "non", "aucune répartition par formule")])
    rapport = controler_la_couverture(
        client=client, variables=variables, document=DOCUMENT
    )
    assert rapport.insuffisantes[0][2] == "aucune répartition par formule"


def test_les_objectifs_du_client_sont_lus() -> None:
    """« Connaître la rentabilité réelle de chaque abonnement » : écrit par le
    client du dossier `f7f2fad9` dans `OBJECTIF_STRATEGIQUE`, que l'ancienne liste de
    champs ignorait entièrement."""
    variables = {
        "OBJECTIF_STRATEGIQUE": (
            "Mes objectifs sont les suivants :\n"
            "connaître la rentabilité réelle de chaque abonnement ;\n"
            "clarifier le contenu de chaque formule ;"
        ),
    }
    textes = [c.texte for c in candidats_du_brief(variables)]
    assert "connaître la rentabilité réelle de chaque abonnement" in textes


def test_un_inventaire_de_documents_n_est_pas_une_demande() -> None:
    """« Un brief stratégique actuel consacré au projet » est sorti comme une
    « demande insuffisamment traitée ». C'est un intitulé de document.

    Classé contexte par le modèle, il est écarté — compté, pas affiché.
    """
    variables = {
        "ELEMENTS_A_RETENIR": (
            "Un brief stratégique actuel consacré au projet\n"
            "Une étude de la concurrence détaillée sur la région"
        ),
        "DEMANDES_SPECIFIQUES": "Quels canaux d'acquisition privilégier ?",
    }
    candidats = candidats_du_brief(variables)
    numero_demande = next(
        c.numero for c in candidats if c.texte.startswith("Quels canaux")
    )
    reponses = [
        {"n": c.numero} for c in candidats if c.numero != numero_demande
    ] + [_demande(numero_demande, "oui")]

    rapport = controler_la_couverture(
        client=_Client(reponses), variables=variables, document=DOCUMENT
    )

    assert rapport.insuffisantes == []
    assert rapport.ecartees_comme_contexte == len(candidats) - 1
    assert rapport.traitees == ["Quels canaux d'acquisition privilégier ?"]


def test_une_valeur_qui_n_est_pas_du_texte_n_est_pas_lue() -> None:
    """Une adresse de logo, une couleur : écartées à leur FORME, pas à leur
    nom de champ — une liste de noms serait incomplète au premier ajout."""
    variables = {
        "LOGO_URL": "/media/pieces-jointes/0000/LOGO_EVKHA_BUSINESS.png",
        "SITE": "https://www.exemple.fr/une-page-assez-longue",
        "COULEUR_PRINCIPALE": "#000000",
    }
    assert candidats_du_brief(variables) == []


def test_le_budget_de_reponse_suit_le_nombre_de_passages() -> None:
    """3 000 jetons pour 87 verdicts : trente-quatre par ligne, réponse
    tronquée. Le budget grandit avec le brief."""
    petit = _Client([])
    controler_la_couverture(
        client=petit,
        variables={"DEMANDES_SPECIFIQUES": "Quelle cible attaquer en premier ?"},
        document=DOCUMENT,
    )
    grand = _Client([])
    controler_la_couverture(
        client=grand,
        variables={
            "OBJECTIF_STRATEGIQUE": ";".join(
                f"objectif numéro {n} du dirigeant à traiter" for n in range(80)
            )
        },
        document=DOCUMENT,
    )
    assert grand.max_tokens > petit.max_tokens
    assert grand.max_tokens >= 80 * 12


def test_le_modele_voit_le_numero_et_le_champ_de_chaque_passage() -> None:
    client = _Client([])
    controler_la_couverture(
        client=client,
        variables={"ENJEUX": "Je souhaite savoir quelle cible attaquer en premier."},
        document=DOCUMENT,
    )
    assert "1. [ENJEUX] Je souhaite savoir quelle cible attaquer en premier." in (
        client.prompt
    )


def test_quelques_oublis_du_modele_sont_nommes_sans_perdre_le_reste() -> None:
    """Un oubli ponctuel ne doit pas faire jeter les verdicts bien rendus."""
    variables = {
        "OBJECTIF_STRATEGIQUE": ";".join(
            f"objectif numéro {n} du dirigeant à traiter" for n in range(1, 11)
        )
    }
    # Neuf verdicts sur dix : sous le seuil, la passe conclut et nomme l'absent.
    client = _Client([_demande(n, "oui") for n in range(1, 10)])

    rapport = controler_la_couverture(
        client=client, variables=variables, document=DOCUMENT
    )

    assert rapport.passe_executee is True
    assert len(rapport.traitees) == 9
    assert rapport.non_examinees == ["objectif numéro 10 du dirigeant à traiter"]
    assert not rapport.toutes_traitees



def test_une_demande_apres_une_adresse_n_est_pas_perdue() -> None:
    """Le filtre des adresses s'appliquait au champ ENTIER : deux sites
    concurrents en tête, et la demande qui suivait disparaissait avec eux."""
    variables = {
        "CONCURRENTS": (
            "https://concurrent-a.fr\nhttps://concurrent-b.fr\n"
            "Je veux savoir comment me différencier de ces deux acteurs."
        ),
    }
    textes = [c.texte for c in candidats_du_brief(variables)]
    assert textes == ["Je veux savoir comment me différencier de ces deux acteurs."]


def test_une_liste_est_decoupee_comme_une_chaine() -> None:
    variables = {"ENJEUX": [
        "quelle cible attaquer en premier ; quel canal ouvrir ensuite",
    ]}
    textes = [c.texte for c in candidats_du_brief(variables)]
    assert textes == ["quelle cible attaquer en premier", "quel canal ouvrir ensuite"]


def test_une_reponse_coupee_par_le_budget_est_nommee_comme_telle() -> None:
    """Sans lire `stop_reason`, une réponse coupée passait pour des oublis du
    modèle — et on aurait cherché la cause au mauvais endroit."""

    class _ClientCoupe:
        def complete_structured(self, **_: Any) -> _Resultat:
            return _Resultat({"demandes": [], "contexte": []}, stop_reason="max_tokens")

    rapport = controler_la_couverture(
        client=_ClientCoupe(),
        variables={"DEMANDES_SPECIFIQUES": "Quelle cible attaquer en premier ?"},
        document=DOCUMENT,
    )
    assert rapport.passe_executee is False
    assert "budget" in rapport.motif_non_executee


def test_les_verdicts_sont_demandes_avant_le_contexte() -> None:
    """Si la réponse est coupée, c'est la fin qui saute : mieux vaut perdre des
    numéros de contexte que des verdicts."""
    from generation.couverture import RapportDuModele

    assert list(RapportDuModele.model_json_schema()["properties"]) == [
        "demandes", "contexte",
    ]

"""Un chiffre-fondation non confirmé ne se verrouille pas comme une donnée publiée.

## Le retour qui a créé ce module

Cliente, 09/08/2026, sur l'étude e-commerce animalier : « Si un chiffre initial
est erroné, daté, issu d'un mauvais périmètre ou mal interprété, il est
actuellement répété dans toute l'étude. »

Elle a raison, et c'est structurel. Le socle est le point unique de vérité : ses
chiffres partent dans les vingt-trois chapitres, dans les figures, dans les
tableaux. Aucune contradiction interne n'est possible — c'est sa force — et
c'est exactement ce qui rend une erreur initiale si chère. `produire_socle`
rendait le socle, `etablir_socle` le scellait `VALIDE` dans la foulée. Rien
entre les deux.

## La règle du module : on DÉCLASSE, on ne supprime pas

Un chiffre qu'on ne peut pas confirmer passe de `observee` à `estimee`, et la
raison entre dans son `libelle` — donc dans le prompt de chaque chapitre, donc
sous les yeux du lecteur.

Le supprimer casserait l'étude : le socle porte des emboîtements (TAM ≥ SAM ≥
SOM) et retirer une valeur rend les autres incalculables. Le déclasser dit la
vérité : ce chiffre n'est pas faux, il n'est simplement plus une donnée
publiée.

## Ce que les contre-épreuves protègent

Une passe qui déclasse tout ne vaut pas mieux qu'une passe qui ne déclasse
rien : dans les deux cas elle ne mesure plus. Un chiffre confirmé par les
sources doit rester `observee`, et une donnée déjà `estimee` ne doit pas être
déclassée deux fois.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from generation.socle.schema import (
    DonneeSocle,
    Fiabilite,
    Perimetre,
    Socle,
    Zone,
)
from generation.socle.verification import verifier_le_socle

BRIEF = (
    "Fevad, 2025 — le marché français de l'e-commerce animalier atteint "
    "1,2 Md€.\nInsee, 2025 — 4 200 établissements actifs dans le secteur."
)


def _socle(*donnees: DonneeSocle) -> Socle:
    return Socle(
        secteur="e-commerce animalier",
        zone=Zone(pays="France"),
        date_socle=date(2026, 8, 9),
        donnees=list(donnees),
    )


def _donnee(
    identifiant: str = "tam",
    *,
    fiabilite: str = Fiabilite.OBSERVEE,
    source: str = "Fevad, 2025",
) -> DonneeSocle:
    return DonneeSocle(
        id=identifiant,
        libelle="Marché total",
        valeur=1.2,
        unite="MdEUR",
        annee=2025,
        perimetre=Perimetre.NATIONAL,
        fiabilite=fiabilite,
        source=source,
    )


class _Resultat:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload


class _Client:
    """Doublure qui rend les verdicts qu'on lui dicte."""

    def __init__(self, verdicts: list[dict[str, str]]) -> None:
        self._verdicts = verdicts
        self.appels = 0

    def complete_structured(self, **_: Any) -> _Resultat:
        self.appels += 1
        return _Resultat({"verdicts": self._verdicts})


class _ClientEnPanne:
    def complete_structured(self, **_: Any) -> _Resultat:
        msg = "API indisponible"
        raise RuntimeError(msg)


# ── Ce qui se tranche SANS dépenser un jeton ─────────────────────────────────


def test_le_contrat_interdit_DEJA_une_observee_sans_source() -> None:
    """Ce module n'a donc pas à le contrôler — et il ne le fait pas.

    Une première version le vérifiait. Le contrôle n'aurait jamais pu se
    déclencher : `DonneeSocle` refuse cette combinaison à la construction. Un
    garde-fou incapable de se déclencher se lit comme une protection et n'en
    est pas une (règle 8 — lire le contrat avant d'écrire le contrôle).
    """
    with pytest.raises(ValidationError, match="estimation qui s'ignore"):
        _donnee(source="")

def test_sans_aucune_source_collectee_rien_n_est_confirme() -> None:
    """Règle 1 : un contrôle qui n'a rien à comparer est un ÉCHEC.

    Laisser passer « puisqu'on ne peut pas juger » est exactement le défaut que
    ce dépôt corrige depuis le début.
    """
    socle = _socle(_donnee())

    rapport = verifier_le_socle(socle, client=_Client([]), brief_recherche="")

    assert socle.donnees[0].fiabilite == Fiabilite.ESTIMEE
    assert rapport.declassees == [("tam", "aucune source collectée pour cette étude")]


# ── Le verdict du modèle ─────────────────────────────────────────────────────


def test_un_chiffre_confirme_reste_une_donnee_observee() -> None:
    """CONTRE-ÉPREUVE : une passe qui déclasse tout ne mesure plus rien."""
    socle = _socle(_donnee())
    client = _Client([{"identifiant": "tam", "statut": "confirmee", "motif": ""}])

    rapport = verifier_le_socle(socle, client=client, brief_recherche=BRIEF)

    assert socle.donnees[0].fiabilite == Fiabilite.OBSERVEE
    assert socle.donnees[0].libelle == "Marché total"
    assert rapport.confirmees == ["tam"]
    assert rapport.declassees == []


def test_un_chiffre_declasse_devient_une_estimation_ET_LE_DIT() -> None:
    """Le motif entre dans le `libelle`, donc dans le prompt, donc dans le document.

    C'est ce qui distingue un déclassement d'une correction silencieuse : le
    lecteur saura que ce chiffre est une estimation, et pourquoi.
    """
    socle = _socle(_donnee())
    client = _Client([{
        "identifiant": "tam",
        "statut": "declassee",
        "motif": "les sources donnent 1,8 Md€ pour 2024, pas 1,2 Md€ pour 2025",
    }])

    verifier_le_socle(socle, client=client, brief_recherche=BRIEF)

    assert socle.donnees[0].fiabilite == Fiabilite.ESTIMEE
    assert "non confirmé" in socle.donnees[0].libelle
    assert "1,8 Md€" in socle.donnees[0].libelle


def test_un_chiffre_oublie_par_la_passe_est_declasse() -> None:
    """Un chiffre non EXAMINÉ n'est pas un chiffre vérifié.

    Le silence du modèle sur un identifiant ne vaut pas approbation — c'est la
    même règle que partout ailleurs dans ce dépôt.
    """
    socle = _socle(_donnee("tam"), _donnee("sam"))
    client = _Client([{"identifiant": "tam", "statut": "confirmee", "motif": ""}])

    rapport = verifier_le_socle(socle, client=client, brief_recherche=BRIEF)

    assert socle.donnees[1].fiabilite == Fiabilite.ESTIMEE
    assert rapport.declassees == [("sam", "non examiné par la passe de vérification")]


@pytest.mark.parametrize(
    "fiabilite", [Fiabilite.ESTIMEE, Fiabilite.SCENARIO, Fiabilite.DECLAREE]
)
def test_seules_les_donnees_ANNONCEES_observees_sont_verifiees(fiabilite: str) -> None:
    """Une estimation ne se déclasse pas : elle n'a jamais prétendu être publiée.

    Sans ce filtre, la passe abîmerait des données parfaitement honnêtes et
    ferait payer un appel pour rien.
    """
    socle = _socle(_donnee(fiabilite=fiabilite))
    client = _Client([])

    rapport = verifier_le_socle(socle, client=client, brief_recherche=BRIEF)

    assert socle.donnees[0].fiabilite == fiabilite
    assert socle.donnees[0].libelle == "Marché total"
    assert rapport.declassees == []
    assert client.appels == 0


# ── Quand la passe elle-même échoue ──────────────────────────────────────────


def test_une_panne_de_la_passe_ne_tue_pas_l_etude_mais_SE_VOIT() -> None:
    """Une panne ne rend pas les chiffres faux : elle rend leur contrôle impossible.

    Faire mourir l'étude coûterait un dossier entier pour un incident
    transitoire. Mais un socle NON vérifié ne doit pas se faire passer pour un
    socle vérifié — d'où `passe_executee`, et l'incident qu'il déclenche.
    """
    socle = _socle(_donnee())

    rapport = verifier_le_socle(
        socle, client=_ClientEnPanne(), brief_recherche=BRIEF
    )

    assert rapport.passe_executee is False
    assert "RuntimeError" in rapport.motif_non_executee
    assert socle.donnees[0].fiabilite == Fiabilite.OBSERVEE


def test_un_socle_sans_donnee_observee_n_appelle_personne() -> None:
    socle = _socle(_donnee(fiabilite=Fiabilite.DECLAREE))
    client = _Client([])

    rapport = verifier_le_socle(socle, client=client, brief_recherche=BRIEF)

    assert rapport.passe_executee is True
    assert client.appels == 0


def test_le_rapport_se_lit_dans_un_incident() -> None:
    """Ce qui n'est pas lisible dans le journal n'existe pas (règle 10)."""
    socle = _socle(_donnee(), _donnee("sam"))
    client = _Client([
        {"identifiant": "tam", "statut": "confirmee", "motif": ""},
        {"identifiant": "sam", "statut": "declassee", "motif": "périmètre européen"},
    ])

    rapport = verifier_le_socle(socle, client=client, brief_recherche=BRIEF)
    details = rapport.as_details()

    assert details["confirmees"] == 1
    assert details["declassees"][0]["identifiant"] == "sam"
    assert rapport.total_declassees == 1

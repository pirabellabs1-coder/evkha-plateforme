"""Une lettre de travers ne doit pas coûter une étude entière.

Mesure, génération réelle `5ed4f03f` du 05/08/2026 :

    job=failed  chapitres=18/23  cout=2.1048 EUR
    ch.18 failed essais=3
        blocs.4.titre_sous_section.intitulo : Extra inputs are not permitted

Le modèle a écrit `intitulo` au lieu de `intitule`. Le contrat refuse les
champs inconnus — à raison : c'est ce qui empêche un chapitre d'inventer sa
structure. Mais dix-huit chapitres et 2,10 EUR sont partis sur une faute de
frappe d'une lettre.

**Trois tentatives, trois fois la même faute.** La boucle de reprise ne sauve
pas ce cas : le refus vient de la validation du schéma, avant l'arbitrage de
conformité. Et le motif rendu au modèle — « Extra inputs are not permitted » —
dit ce qui est refusé sans dire ce qui est attendu. Il ne pouvait pas deviner.

Deux correctifs, et il faut les deux : accepter la clé dont l'intention est
certaine, et rendre le refus actionnable pour toutes les autres.
"""
from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from generation.chapitres.schema import (
    BLOC_PAR_TYPE,
    ChapitrePayload,
    _differe_d_un_signe,
)


def _payload(blocs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "chapitre": 18,
        "titre": "SWOT de synthèse",
        "blocs": blocs,
        "donnees_utilisees": [],
        "resume": "r " * 160,
    }


# ── La clé dont l'intention est certaine ─────────────────────────────────────


def test_la_typo_qui_a_tue_l_etude_est_desormais_lue() -> None:
    """LE cas mesuré. Sur le code d'avant : ValidationError, étude morte."""
    payload = ChapitrePayload.model_validate(_payload([
        {"type": "titre_sous_section", "numero": "18.1", "intitulo": "Forces"},
    ]))

    assert payload.sous_titres[0].intitule == "Forces"


def test_la_typo_est_rattrapee_partout_dans_le_contrat() -> None:
    """La correction vise la CLASSE : tous les modèles, pas le seul qui a échoué.

    Un encadré, un tableau ou une cellule de chiffre clé offrent exactement la
    même prise à la faute de frappe (règle 4).
    """
    payload = ChapitrePayload.model_validate(_payload([
        {"type": "encadre", "intitul": "À retenir", "lignes": ["Le marché est concentré."]},
        {
            "type": "tableau",
            "entete": ["Indicateur", "Valeur"],
            "lignes": [["Taille", "1 250 MEUR"]],
        },
    ]))

    assert payload.encadres[0].intitule == "À retenir"
    assert payload.tableaux[0].entetes == ["Indicateur", "Valeur"]


# ── Ce qui reste refusé ──────────────────────────────────────────────────────


def test_une_cle_qui_ne_ressemble_a_rien_reste_refusee() -> None:
    """Contre-épreuve : le contrat n'est pas devenu permissif.

    Refuser les champs inconnus est la garantie centrale — sans elle, un
    chapitre inventerait sa structure.
    """
    with pytest.raises(ValidationError):
        ChapitrePayload.model_validate(_payload([
            {
                "type": "titre_sous_section", "numero": "18.1",
                "intitule": "Forces", "couleur_de_fond": "rouge",
            },
        ]))


def test_une_cle_deja_presente_n_est_jamais_recouverte() -> None:
    """Si le modèle a écrit les deux, la valeur juste est celle bien nommée."""
    payload = ChapitrePayload.model_validate(_payload([
        {
            "type": "titre_sous_section", "numero": "18.1",
            "intitule": "Forces", "intitulo": "Faiblesses",
        },
    ]))

    assert payload.sous_titres[0].intitule == "Forces"


def test_deux_lettres_de_travers_restent_refusees() -> None:
    """L'intention n'est plus certaine : deviner rangerait le contenu ailleurs."""
    with pytest.raises(ValidationError):
        ChapitrePayload.model_validate(_payload([
            {"type": "titre_sous_section", "numero": "18.1", "intitolo": "Forces"},
        ]))


@pytest.mark.parametrize(
    ("a", "b", "attendu"),
    [
        ("intitule", "intitule", True),   # identiques
        ("intitulo", "intitule", True),   # substitution
        ("intitul", "intitule", True),    # suppression
        ("intitulee", "intitule", True),  # insertion
        ("intitolo", "intitule", False),  # deux écarts
        ("titre", "intitule", False),     # mots distincts
        ("numero", "intitule", False),
    ],
)
def test_la_distance_d_un_signe_se_raisonne(a: str, b: str, attendu: bool) -> None:
    """Écrite explicitement plutôt qu'empruntée à une similarité floue.

    Un seuil de ressemblance se règle au jugé et dérive ; « à un signe près »
    se teste.
    """
    assert _differe_d_un_signe(a, b) is attendu


# ── Le motif de refus dit ce qui est attendu ─────────────────────────────────


def test_le_motif_nomme_les_champs_admis() -> None:
    """Sans cela, le modèle doit DEVINER le nom qu'il aurait dû écrire.

    Il ne l'a pas deviné : trois tentatives, trois fois la même faute.
    """
    from generation.chapitres.runner import _motif_de_validation

    motif = _motif_de_validation({
        "loc": ("blocs", 4, "titre_sous_section", "couleur"),
        "msg": "Extra inputs are not permitted",
        "type": "extra_forbidden",
    })

    assert "Champs admis ici" in motif
    assert "intitule" in motif and "numero" in motif


def test_les_autres_motifs_ne_sont_pas_alourdis() -> None:
    """Contre-épreuve : on n'ajoute la liste que là où elle sert."""
    from generation.chapitres.runner import _motif_de_validation

    motif = _motif_de_validation({
        "loc": ("blocs", 4, "titre_sous_section", "intitule"),
        "msg": "String should have at least 1 character",
        "type": "string_too_short",
    })

    assert "Champs admis ici" not in motif


def test_la_table_des_blocs_couvre_l_union() -> None:
    """Dérivée de l'union, jamais recopiée : elle suivra le prochain bloc ajouté."""
    assert set(BLOC_PAR_TYPE) == {
        "titre_sous_section", "paragraphe", "tableau", "encadre",
        "graphique", "grille_kpi",
    }

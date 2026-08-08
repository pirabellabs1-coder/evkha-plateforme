"""Un bloc ecrit a plat par le modele doit etre lu, pas rejete.

Mesure, generation reelle `6557b06b` du 05/08/2026, commit `2130519` :
l'etude Joalie est morte au chapitre 1 pour **0,41 EUR**, sur ce motif repete
trois fois — deux tentatives au chapitre 1, une au chapitre 2 :

    blocs.3.graphique.graphique : Field required
    blocs.3.graphique.type_graphique : Extra inputs are not permitted
    blocs.3.graphique.titre : Extra inputs are not permitted
    blocs.3.graphique.donnees_ids : Extra inputs are not permitted
    blocs.3.graphique.commentaire : Extra inputs are not permitted

Trois fois le meme motif : deterministe, pas un alea. Et la cause se nomme.

`BlocGraphique.type` vaut « graphique » — la nature du BLOC. `Graphique.type`
vaut « courbe » ou « barres » — la nature du VISUEL. Le meme mot, deux sens,
emboites l'un dans l'autre, plus une cle d'enveloppe (`graphique`) qui repete
encore le discriminant. Le modele a resolu la collision de la seule facon
possible : il a renomme le champ interieur `type_graphique` et remonte tout
d'un cran.

Deux correctifs, et il faut les deux :

1. Le contrat ne nomme plus deux choses `type` (alias `type_graphique`), pour
   que le modele n'ait plus a arbitrer. `populate_by_name` garde `type`
   valable : les chapitres deja en base restent lisibles.
2. La forme aplatie est ACCEPTEE, sur les trois blocs a enveloppe et pas sur le
   seul graphique qui a echoue (regle 4) — le tableau et l'encadre presentent
   la meme invitation a l'erreur.

Re-nicher des cles ne change aucune valeur : c'est du transport, pas du fond.
Ce qui juge le fond — « un chapitre n'exploite que des donnees du socle » —
reste `valider_chapitre`, intact.
"""
from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from generation.chapitres.schema import ChapitrePayload, TypeGraphique


def _payload(blocs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "chapitre": 1,
        "titre": "Marche mondial",
        "blocs": blocs,
        "donnees_utilisees": ["marche_mondial_taille"],
        "resume": "r " * 160,
    }


_GRAPHIQUE_APLATI = {
    "type": "graphique",
    "type_graphique": "courbes",
    "titre": "Taille du marche mondial",
    "donnees_ids": ["marche_mondial_taille"],
    "commentaire": "Croissance reguliere.",
}

_GRAPHIQUE_NICHE = {
    "type": "graphique",
    "graphique": {
        "type": "courbes",
        "titre": "Taille du marche mondial",
        "donnees_ids": ["marche_mondial_taille"],
        "commentaire": "Croissance reguliere.",
    },
}


def test_le_graphique_aplati_est_lu() -> None:
    """LE cas qui a tue l'etude. Sur le code d'avant, ValidationError."""
    payload = ChapitrePayload.model_validate(_payload([_GRAPHIQUE_APLATI]))

    assert len(payload.graphiques) == 1
    graphique = payload.graphiques[0]
    assert graphique.type is TypeGraphique.COURBES
    assert graphique.titre == "Taille du marche mondial"
    assert graphique.donnees_ids == ["marche_mondial_taille"]


def test_le_graphique_niche_reste_lu() -> None:
    """Contre-epreuve : la forme du contrat n'est pas cassee.

    Les chapitres deja en base la portent, et le rendu Word les relit.
    """
    payload = ChapitrePayload.model_validate(_payload([_GRAPHIQUE_NICHE]))

    assert payload.graphiques[0].type is TypeGraphique.COURBES


def test_le_tableau_et_l_encadre_aplatis_sont_lus() -> None:
    """La correction vise la CLASSE, pas l'instance qui a echoue (regle 4).

    Les trois blocs a enveloppe partagent la meme forme et la meme invitation
    a l'erreur. Corriger le seul graphique aurait laisse deux fois le meme
    defaut en place.
    """
    payload = ChapitrePayload.model_validate(_payload([
        {
            "type": "tableau",
            "entetes": ["Indicateur", "Valeur"],
            "lignes": [["Taille", "1 250 MEUR"]],
            "source": "INSEE 2024",
        },
        {
            "type": "encadre",
            "intitule": "A retenir",
            "lignes": ["Le marche est concentre."],
        },
    ]))

    assert payload.tableaux[0].entetes == ["Indicateur", "Valeur"]
    assert payload.encadres[0].intitule == "A retenir"


def test_le_contrat_ne_nomme_plus_deux_choses_type() -> None:
    """La cause, pas seulement le symptome : le schema envoye au modele.

    Tant que l'objet interieur porte `type` comme son enveloppe, le modele
    doit arbitrer une ambiguite a chaque chapitre — et la resout parfois
    contre nous. Ici on verifie ce que le modele LIT, pas ce que Python voit.
    """
    from generation.chapitres.runner import schema_outil

    definitions = schema_outil().get("$defs", {})
    graphique = definitions["Graphique"]["properties"]

    assert "type_graphique" in graphique, (
        "Le contrat doit nommer le type de visuel sans repeter le discriminant."
    )
    assert "type" not in graphique


def test_un_bloc_reellement_incomplet_est_toujours_refuse() -> None:
    """Contre-epreuve : la permissivite ne va pas jusqu'a inventer.

    Un graphique sans identifiant de donnee ne demande aucune donnee du socle :
    il n'a rien a dessiner, et re-nicher ne le sauve pas.
    """
    with pytest.raises(ValidationError):
        ChapitrePayload.model_validate(_payload([
            {"type": "graphique", "type_graphique": "courbes", "titre": "Vide"},
        ]))

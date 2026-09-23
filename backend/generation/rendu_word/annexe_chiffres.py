"""L'annexe qui dit D'OÙ VIENT chaque chiffre du document.

## La demande

Cliente, 08/09/2026, sur la stratégie du dossier `f7f2fad9` : « il faudrait
que chaque donnée chiffrée soit classée — vérifiée, déclarée, hypothèse — et
que le document montre le calcul plutôt que la seule conclusion ».

Le socle porte déjà cette information pour chacun de ses chiffres : sa
`fiabilite`, sa `source`, son année, son périmètre, et pour une valeur
calculée, sa formule. Rien n'en arrivait au lecteur : le document affichait le
résultat, et le lecteur devait croire sur parole.

## Pourquoi cette annexe est CONSTRUITE, pas rédigée

Elle ne passe par aucun modèle. Elle recopie le socle verrouillé, qui est déjà
la seule source des chiffres de l'étude (règle 5). Un chapitre rédigé qui
« expliquerait les sources » pourrait en inventer ; un tableau construit depuis
le socle ne le peut pas, ne coûte rien, et ne peut pas diverger du document
puisqu'il en cite les mêmes valeurs.

## Ce qu'elle ne prétend pas

Elle ne classe pas les chiffres qu'un chapitre a calculés au fil du texte — ils
ne sont pas dans le socle. Elle dit ce dont elle répond : les chiffres de
référence de l'étude, ceux que tous les chapitres reprennent.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..socle.referentiel import Fiabilite

if TYPE_CHECKING:
    from ..socle.schema import Socle

#: Le titre de l'annexe, lu par le client.
TITRE = "D'où viennent les chiffres de cette étude"

#: Ce que chaque fiabilité veut dire POUR LE LECTEUR. Les mots du référentiel —
#: « observee », « declaree » — ne lui disent rien ; ceux-ci disent ce qu'il
#: peut en faire, et la cliente les a nommés elle-même : vérifiée, déclarée,
#: hypothèse.
_NATURE: dict[str, str] = {
    Fiabilite.OBSERVEE: "Vérifiée",
    Fiabilite.DECLAREE: "Déclarée",
    Fiabilite.ESTIMEE: "Estimée",
    Fiabilite.SCENARIO: "Hypothèse",
}

_EXPLICATION: dict[str, str] = {
    Fiabilite.OBSERVEE: "publiée par la source citée",
    Fiabilite.DECLAREE: "fournie par vous, dans votre dossier",
    Fiabilite.ESTIMEE: "construite par recoupement, faute de publication",
    Fiabilite.SCENARIO: "posée pour raisonner, à confirmer",
}


def _origine(donnee: Any) -> str:
    """La phrase qui explique une valeur : sa nature, sa source ou son calcul."""
    nature = str(donnee.fiabilite)
    morceaux = [_NATURE.get(nature, "Estimée")]
    # La formule d'une valeur calculée vit déjà dans son libellé
    # (`socle/calculs.py` écrit « Calculé : … »). On la reprend telle quelle :
    # c'est le calcul que la cliente demande à voir.
    libelle = (donnee.libelle or "").strip()
    if libelle.lower().startswith("calculé"):
        morceaux.append(libelle.rstrip("."))
    elif donnee.source:
        morceaux.append(str(donnee.source))
    else:
        morceaux.append(_EXPLICATION.get(nature, ""))
    return " — ".join(m for m in morceaux if m)


def _valeur(donnee: Any) -> str:
    valeur = donnee.valeur
    ecrite = f"{valeur:,.2f}".rstrip("0").rstrip(".").replace(",", " ").replace(".", ",")
    return f"{ecrite} {donnee.unite}".strip()


def blocs_annexe(socle: Socle, *, numero: int) -> list[dict[str, Any]]:
    """L'annexe complète, prête à rendre. Vide si le socle ne porte rien."""
    if not socle.donnees:
        return []
    lignes = [
        [
            donnee.libelle.split(".")[0] if donnee.libelle else donnee.id,
            _valeur(donnee),
            str(donnee.annee or "—"),
            _origine(donnee),
        ]
        for donnee in socle.donnees
    ]
    return [
        {"type": "bandeau", "numero": numero, "titre": TITRE, "accroche": ""},
        {
            "type": "paragraphe",
            "texte": (
                "Chaque chiffre de cette étude est repris ci-dessous avec son "
                "origine. « Vérifiée » signifie publiée par la source citée ; "
                "« déclarée », fournie par vous ; « estimée », construite par "
                "recoupement faute de publication ; « hypothèse », posée pour "
                "raisonner et à confirmer. Les valeurs calculées portent leur "
                "calcul, pour que vous puissiez le refaire."
            ),
        },
        {
            "type": "tableau",
            "entetes": ["Donnée", "Valeur", "Année", "Origine"],
            "lignes": lignes,
            "source": "",
        },
    ]

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

## Une annexe, pas un chapitre (décision D9, 29/09/2026)

Elle était numérotée comme un chapitre — « 22 — D'où viennent les chiffres »
au sommaire du business plan ÉCLORE, qui en annonçait 21. Le même +1 valait
pour les quatre livrables. Elle est désormais une annexe NON NUMÉROTÉE : un
bandeau « ANNEXE », une ligne au sommaire sans numéro, et elle ne compte plus
parmi les chapitres (`assemblage.assembler_etude` la range dans `annexes`).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..socle.referentiel import Fiabilite
from ..socle.schema import montant_lisible
from .texte import libelle_court

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


def a_son_echelle(valeur: float, unite: str) -> tuple[float, str]:
    """La valeur et l'unité sous lesquelles un montant s'écrit SANS PERTE.

    Un montant stocké à une grande échelle mais petit devant elle s'écrivait
    ZÉRO : le SOM de démonstration, 0,0003 MdEUR, sortait « 0 Md€ » — le
    formateur garde trois décimales. Mesuré le 29/09/2026 en corrigeant l'annexe
    d'ÉCLORE : le contrôle des valeurs nulles l'a vu dès que le code « MdEUR »
    a cessé de masquer le montant. Un tel montant est alors ramené à l'unité de
    base de sa devise (300 000 €), et `montant_lisible` choisit l'échelle qui
    ne perd rien. Une grandeur non monétaire traverse inchangée.
    """
    from ..socle.schema import valeur_en_unites_de_base  # noqa: PLC0415

    en_base = valeur_en_unites_de_base(valeur, unite)
    if en_base is None or valeur == 0:
        return valeur, unite
    if abs(valeur) < 1 or round(valeur, 3) != valeur:
        return en_base
    return valeur, unite


def _valeur(donnee: Any) -> str:
    """La valeur ET son unité, écrites pour le lecteur.

    29/09/2026, business plan ÉCLORE (pages 103 et 106) : « 2 000 000 unite »,
    « 30 000 MEUR », « 23 223,86 EUR ». Cette fonction recopiait le CODE de
    stockage de l'unité, alors que `montant_lisible` existait et avait été
    appliqué au tableau de repli le 26/09 — l'exemple corrigé, pas la classe
    (règle 4). Le formateur du socle est la seule source (règle 5).
    """
    return montant_lisible(*a_son_echelle(float(donnee.valeur), str(donnee.unite)))


def blocs_annexe(socle: Socle) -> list[dict[str, Any]]:
    """L'annexe complète, prête à rendre. Vide si le socle ne porte rien.

    Son bandeau est `bandeau_annexe` : il ne porte AUCUN numéro de chapitre
    (décision D9).
    """
    if not socle.donnees:
        return []
    lignes = [
        [
            # Coupé au mot, avec « … » s'il le faut : jamais au milieu d'un mot
            # (29/09/2026, tableaux tronqués du business plan ÉCLORE).
            libelle_court(donnee.libelle) if donnee.libelle else donnee.id,
            _valeur(donnee),
            str(donnee.annee or "—"),
            _origine(donnee),
        ]
        for donnee in socle.donnees
    ]
    return [
        {"type": "bandeau_annexe", "titre": TITRE, "accroche": ""},
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

"""Sept liaisons fausses entre une étiquette et un montant qui n'est pas le sien.

## Les trois motifs, relevés sur le business plan 73dde3ab du 17/08/2026

    apport : 45 000 euros au ch. 2 ; … ; 195 000 € au ch. 15 ;
    45 000 euros au ch. 20 ; 195 000 euros au ch. 20.

    marge_brute : 180 000 euros au ch. 0 ; 4,68 euros au ch. 8 ;
    70 000 euros au ch. 9 ; 230 400 € au ch. 16 ; 34 800 euros au ch. 16.

    seuil_rentabilite : 265 000 euros au ch. 0 ; 320 000 euros au ch. 1 ; …

Le document était juste. 195 000 €, c'est le besoin de financement ; 4,68 €,
la marge unitaire ; 70 000 €, la masse salariale ; 34 800 €, l'excédent brut
d'exploitation. Le collecteur liait chaque étiquette au premier montant des
cent caractères suivants, sans vérifier qu'il lui appartienne.

## Les quatre discriminants, tirés des phrases réelles

Aucun n'énumère des concepts — la règle 4 dit qu'un correctif qui énumère est
incomplet :

- **une fin de phrase** — « …du taux de marge brute. La masse salariale
  prévisionnelle représente à elle seule 70 000 euros » : la phrase suivante
  parle d'autre chose, et le point le disait déjà ;
- **deux séparateurs de cellule** — « Seuil de rentabilité annuel │ données du
  projet │ 195 000 € » : une barre sépare un libellé de SA valeur, deux barres
  séparent deux lignes ;
- **un autre libellé surveillé** — « …ramènerait l'excédent brut
  d'exploitation à environ 34 800 euros » : l'EBE est déjà surveillé pour
  lui-même, et la liste de ce qui est surveillé EST la liste de ce qui peut se
  confondre. Elle se tient à jour toute seule (règle 5) ;
- **« unitaire »** — « marge brute unitaire de 4,68 euros » face à « la marge
  brute de l'exercice 1 s'élève à 230 400 euros ». Ce ne sont pas deux valeurs
  d'une même grandeur.

## Et la contre-épreuve, qui pèse autant

Un correctif de ce genre se casse sans bruit : il suffit qu'il désarme le
contrôle. Les deux derniers tests vérifient qu'une VRAIE divergence tombe
toujours, et que les deux montants légitimes du document sont bien lus.
"""
from __future__ import annotations

from generation.checks_evangeline import collecter_mentions, detecter_divergences

#: Les phrases du document, recopiées telles quelles.
DOCUMENT = [
    (2, "Un apport personnel de 45 000 euros sur un total de 195 000 euros."),
    (15, "23,1 % Part de l'apport personnel dans le besoin total de 195 000 €."),
    (
        20,
        "L'apport personnel restant inchangé ? Le besoin total de financement "
        "de 195 000 euros ne change pas.",
    ),
    (
        8,
        "Le panier moyen de 6,5 euros et le taux de marge brute de 72 % dégagent "
        "une marge brute unitaire de 4,68 euros par ticket.",
    ),
    (16, "La marge brute de l'exercice 1 s'élève à 230 400 euros."),
    (
        9,
        "Le pilotage dépend du seuil de rentabilité et du taux de marge brute. "
        "La masse salariale prévisionnelle représente à elle seule 70 000 euros.",
    ),
    (
        16,
        "Un point de marge brute en moins ramènerait l'excédent brut "
        "d'exploitation de l'exercice 1 à environ 34 800 euros.",
    ),
    (9, "| Seuil de rentabilité annuel | données du projet | 195 000 € |"),
]


def _mentions(document: list[tuple[int, str]]) -> list:
    collectees: list = []
    for chapitre, texte in document:
        collectees.extend(collecter_mentions(chapitre, texte))
    return collectees


def test_un_document_juste_ne_diverge_plus() -> None:
    divergences = detecter_divergences(_mentions(DOCUMENT))
    assert divergences == [], (
        "aucune de ces phrases ne se contredit : "
        + " | ".join(d.resume[:90] for d in divergences)
    )


def test_les_montants_legitimes_restent_lus() -> None:
    """Un contrôle qui ne collecte plus rien ne diverge plus non plus.

    Règle 1 : c'est la manière la plus discrète de casser un contrôle, et
    le test précédent passerait tout aussi bien.
    """
    lues = {(m.libelle, m.montant_base) for m in _mentions(DOCUMENT)}
    assert ("apport", 45_000.0) in lues, "l'apport du chapitre 2 doit rester lu"
    assert ("marge_brute", 230_400.0) in lues, "la marge brute annuelle aussi"


def test_une_vraie_divergence_tombe_toujours() -> None:
    contradictoire = [
        (2, "L'apport personnel est de 45 000 euros."),
        (7, "L'apport personnel s'élève à 60 000 euros."),
    ]
    divergences = detecter_divergences(_mentions(contradictoire))
    assert len(divergences) == 1
    assert divergences[0].libelle == "apport"

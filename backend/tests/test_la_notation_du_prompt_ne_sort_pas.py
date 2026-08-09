"""Ce qu'on ajoute au prompt pour aider le modèle peut ressortir dans le document.

## Le fait

Le 09/08/2026, chaque ligne du socle a reçu la NATURE de son identifiant entre
crochets — `[monetaire]`, `[effectif]`, `[pourcentage]` — pour que le modèle
sache quelles grandeurs se tracent ensemble. La mesure a marché : le taux de
figures rendues est passé de 49 % (étude de marché `b561c2d6`) à 71 % (étude
concurrentielle `2490c7cf`).

Et dès cette première génération, la notation a fui dans le document. Un
commentaire de figure disait :

    « …deux taux de même nature [pourcentage] »

Une seule occurrence, presque lisible — et c'est ce qui la rend dangereuse :
elle passe pour de la prose. Le scan du `.docx` l'a trouvée avant la cliente,
pour la première fois de ce projet.

## La leçon, qui dépasse le cas

Le modèle n'a rien fait de mal : on lui a montré cette écriture, il l'a
employée. C'est exactement ce qui s'était produit avec les exemples de tableaux
HTML hérités du moteur précédent — mêmes causes, même semaine.

**Une aide ajoutée au prompt doit arriver AVEC son interdiction de la recopier,
le même jour.** Sans quoi on ferme une fuite en en ouvrant une autre.

## Pourquoi un refus et non une réparation

Retirer les crochets était possible. On refuse quand même : leur présence
signale que le modèle PARLE de sa consigne au lieu de rédiger. Effacer
`[pourcentage]` laisserait « deux taux de même nature », qui n'a rien à faire
dans une étude remise à un client. La typographie se répare ; ceci se réécrit.
"""
from __future__ import annotations

import pytest

from generation.chapitres.schema import (
    BlocEncadre,
    BlocGraphique,
    BlocParagraphe,
    BlocTableau,
    ChapitrePayload,
    Encadre,
    Graphique,
    Tableau,
    motifs_de_balisage,
)


def _chapitre(*blocs: object) -> ChapitrePayload:
    return ChapitrePayload(
        chapitre=3,
        titre="Chapitre d'essai",
        blocs=list(blocs),  # type: ignore[arg-type]
        resume="Un résumé d'essai suffisamment long pour tenir sa borne.",
    )


def test_le_cas_exact_du_dossier_2490c7cf() -> None:
    """La phrase telle qu'elle est sortie, mot pour mot."""
    payload = _chapitre(
        BlocParagraphe(
            texte=(
                "Camembert illustrant la répartition RSE (75 % avec démarche "
                "publique) versus présence digitale universelle (100 %) — deux "
                "taux de même nature [pourcentage]."
            )
        )
    )

    motifs = motifs_de_balisage(payload)

    assert len(motifs) == 1
    assert "[pourcentage]" in motifs[0]
    assert "notation de la CONSIGNE" in motifs[0]


@pytest.mark.parametrize(
    "notation",
    ["[monetaire]", "[effectif]", "[pourcentage]", "[duree]", "[ratio]", "[inconnue]"],
)
def test_les_six_natures_sont_toutes_refusees(notation: str) -> None:
    """Une seule a fui ; les six viennent du même endroit (règle 4)."""
    payload = _chapitre(BlocParagraphe(texte=f"Le marché progresse {notation}."))

    assert motifs_de_balisage(payload)


def test_la_notation_est_traquee_dans_un_commentaire_de_figure() -> None:
    """C'est précisément là qu'elle est sortie — pas dans un paragraphe."""
    payload = _chapitre(
        BlocGraphique(
            graphique=Graphique(
                type_graphique="barres",
                titre="Comparaison des acteurs",
                donnees_ids=["part_marche_a", "part_marche_b"],
                commentaire="Deux grandeurs [pourcentage] comparables.",
            )
        )
    )

    assert motifs_de_balisage(payload)


def test_la_notation_est_traquee_dans_les_cellules_et_les_encadres() -> None:
    for payload in (
        _chapitre(
            BlocTableau(
                tableau=Tableau(
                    entetes=["Critère", "Valeur"],
                    lignes=[["Croissance [pourcentage]", "3,4 %"]],
                )
            )
        ),
        _chapitre(
            BlocEncadre(
                encadre=Encadre(intitule="À retenir", lignes=["Marché [monetaire] mûr"])
            )
        ),
    ):
        assert motifs_de_balisage(payload)


@pytest.mark.parametrize(
    "texte",
    [
        "Voir l'annexe [1] pour le détail des sources",
        "Le segment [premium] tel que défini au chapitre 2",
        "Une note entre crochets [comme celle-ci] reste permise",
        "Les taux sont de même nature et se comparent directement",
        "La durée moyenne est de 8 mois",
        "Répartition en pourcentage des parts de marché",
    ],
)
def test_les_crochets_legitimes_traversent_intacts(texte: str) -> None:
    """Contre-épreuve : c'est la NOTATION qui est visée, pas le crochet.

    Une étude cite des annexes, des segments, des renvois. Condamner le crochet
    ferait passer le test précédent et mutilerait un document correct — le
    défaut que la règle 2 décrit.
    """
    assert motifs_de_balisage(_chapitre(BlocParagraphe(texte=texte))) == []


def test_la_consigne_interdit_de_recopier_la_notation() -> None:
    """La cause, pas seulement le garde-fou.

    Une aide ajoutée au prompt doit arriver avec son interdiction de la
    recopier. Sans cette phrase, chaque chapitre paierait une reprise pour un
    défaut qu'on lui a soi-même enseigné.
    """
    from generation.prompts import REGLES_IDENTIFIANTS_FIGURES

    assert "CES CROCHETS SONT POUR TOI SEUL" in REGLES_IDENTIFIANTS_FIGURES
    assert "JAMAIS" in REGLES_IDENTIFIANTS_FIGURES

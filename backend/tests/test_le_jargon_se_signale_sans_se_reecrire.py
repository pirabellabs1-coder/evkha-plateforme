"""« benchmark, mass market, storytelling, omnicanal, cannibalisation, RSE ».

## La demande

Audit de la cliente du 04/11/2026 sur l'étude de la concurrence SUN TZU,
point 8 : « Je recommande aussi de simplifier certains termes : benchmark,
mass market, storytelling, omnicanal, cannibalisation, RSE. Ces mots ne rendent
pas l'étude plus précise pour le client. »

Vérifié le même jour : `storytelling` et `omnicanal` n'apparaissaient NULLE PART
dans le dépôt. Rien ne les visait.

## Pourquoi une liste séparée des mots anglais

`MOTS_ANGLAIS` ne porte que des connecteurs qui fuient du modèle (« however »,
« therefore »). Trois des six termes ne sont pas anglais du tout — omnicanal,
cannibalisation, RSE. Les y ranger les ferait signaler comme « Mot anglais » :
un motif FAUX, et un motif faux est pire qu'absent (règle 2).

## Pourquoi il signale sans réparer, et sans gravité

Deux raisons, et ce fichier les verrouille toutes les deux.

La première est linguistique, et `langage_simple` l'énonce déjà : le
déterminant change avec le mot. « le benchmark » devient « la comparaison »,
« la cannibalisation » devient « le report des ventes ». Un remplacement mot à
mot fabriquerait une faute de français dans un document qui en était exempt.

La seconde est économique, et elle a été mesurée le 05/11/2026 sur l'étude
`25be2162` : coût 3,9986 € pour un plafond de 4,50 €, la relecture finale a
réclamé 0,80 € (`MARGE_DE_BUDGET + RESERVE_DU_REJEU`), n'a trouvé que 0,50 €,
et n'a réécrit AUCUN chapitre. Sur ce livrable la boucle de réparation ne
tourne pas : c'est la CONSIGNE qui doit porter l'effort, et un motif grave de
plus ne corrigerait rien tout en prenant la place d'un défaut qui compte.

Ces tests échouent sur le code d'avant : `JARGON` et `jargon()` n'existaient
pas, et aucune consigne ne nommait ces six termes.
"""
from __future__ import annotations

import pytest

from generation.chapitres.typographie import JARGON, jargon
from generation.relecture.document import Document, Section

#: Recopiées de son audit : les six termes, dans des phrases du document.
PHRASES_REELLES = [
    ("Le benchmark des concurrents montre une offre omnicanal.", 2),
    ("Un storytelling fort évite la cannibalisation des ventes.", 2),
    ("La politique RSE cible le mass market.", 2),
]


@pytest.mark.parametrize(("phrase", "attendus"), PHRASES_REELLES)
def test_les_six_termes_sont_vus(phrase: str, attendus: int) -> None:
    assert len(jargon(phrase)) == attendus


def test_chaque_terme_porte_sa_suggestion() -> None:
    """Le motif doit DIRE quoi écrire : « simplifier » sans dire quoi ne sert à rien."""
    for terme in JARGON:
        trouves = jargon(f"Le document parle de {terme} dans ce chapitre.")

        assert len(trouves) == 1, terme
        assert trouves[0].equivalent == JARGON[terme]
        assert trouves[0].equivalent


# ---------------------------------------------------------------------------
# Contre-épreuves : ce qu'il ne doit PAS signaler
# ---------------------------------------------------------------------------


def test_un_terme_cite_entre_guillemets_est_epargne() -> None:
    """Un mot COMMENTÉ n'est pas un mot employé.

    « Le mot « benchmark » est du jargon » explique le terme au lecteur : le
    signaler reprocherait à l'étude de faire exactement ce qu'on lui demande.
    """
    assert jargon("Le mot « benchmark » est du jargon de consultant.") == []


def test_une_phrase_qui_dit_la_meme_chose_simplement_passe() -> None:
    """CONTRE-ÉPREUVE : la reformulation attendue ne doit pas être punie."""
    propre = (
        "Une comparaison des concurrents, présente en boutique, en ligne et "
        "par les revendeurs, montre le report des ventes d'une offre sur une "
        "autre auprès du grand public."
    )

    assert jargon(propre) == []


def test_un_mot_qui_contient_un_terme_n_est_pas_un_terme() -> None:
    """La frontière de mot, sinon « benchmarking » et une URL seraient pris."""
    assert jargon("Voir https://exemple.fr/benchmark-2026 pour le détail.") == []


# ---------------------------------------------------------------------------
# Le constat : non grave, et une seule occurrence par terme
# ---------------------------------------------------------------------------


def test_le_constat_n_est_jamais_grave() -> None:
    """Un terme de style ne vaut pas la réécriture payante d'un chapitre.

    Et sur l'étude de la concurrence, elle n'aurait de toute façon pas lieu :
    0,50 € restants pour 0,80 € exigés.
    """
    from generation.relecture.redaction import _jargon_de_consultant

    # Le VRAI `Document`, pas une doublure : une imitation maison dérive du
    # jour où le type change, et un test adossé à sa propre approximation ne
    # verrouille rien.
    document = Document(sections=[Section(
        numero="3.1", titre="Positionnement", chapitre=3,
        paragraphes=["Le benchmark montre un storytelling faible."],
    )])

    constats = _jargon_de_consultant(document)

    assert constats, "le constat doit exister"
    assert all(not c.grave for c in constats)
    assert {c.classe for c in constats} == {"redaction"}


def test_un_terme_repete_ne_se_signale_qu_une_fois() -> None:
    """Six motifs pour un même mot noieraient les cinq autres défauts."""
    from generation.relecture.redaction import _jargon_de_consultant

    document = Document(sections=[Section(
        numero="1.1", titre="Marché", chapitre=1,
        paragraphes=[
            "Le benchmark est clair.",
            "Ce benchmark se confirme.",
            "Un dernier benchmark le montre.",
        ],
    )])

    assert len(_jargon_de_consultant(document)) == 1


# ---------------------------------------------------------------------------
# Le câblage : la consigne et la mesure disent la même chose (règle 5)
# ---------------------------------------------------------------------------


def test_la_consigne_nomme_les_six_termes() -> None:
    """Prévenir ne coûte rien ; ce qui passe ne sera pas réparé.

    Ce test échouerait si quelqu'un ajoutait un terme à `JARGON` sans que la
    consigne le nomme — la mesure signalerait alors un défaut que le modèle
    n'a jamais été prié d'éviter.
    """
    from generation.chapitres.runner import _SYSTEME

    manquants = [t for t in JARGON if t.lower() not in _SYSTEME.lower()]

    assert manquants == [], manquants

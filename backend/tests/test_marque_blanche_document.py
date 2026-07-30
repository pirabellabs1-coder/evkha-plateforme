"""Le document livré ne nomme jamais la plateforme.

Les documents sont remis en **marque blanche** : l'abonné les donne à son
propre client. Y inscrire le nom de la plateforme revient à signer d'un tiers
un travail qu'un autre remet.

Trois mentions étaient pourtant écrites en dur dans le chemin de rendu réel —
« EVKHA · Système d'analyse de marché », « Méthode déposée à l'INPI »,
« EVKHA · Document confidentiel » — et seraient donc parties sur **chaque**
document produit. Repéré en ouvrant le XML des modèles validés, pas en relisant
le code.

Le test vise la classe : aucun nom de plateforme, sous aucune forme, dans ce
que le lecteur verra. Il ne regarde pas les *noms de styles* du gabarit
(`EVKHA Titre document`) : ce sont des identifiants internes, jamais affichés
dans le corps du document. Les renommer est un changement de gabarit, à faire
séparément et entièrement.
"""
from __future__ import annotations

import ast
import re

import pytest

from generation.rendu_word.assemblage import MENTION_PAR_DEFAUT, mentions_finales

#: Ce qui ne doit jamais apparaître, quelle que soit la casse ou l'habillage.
INTERDIT = re.compile(r"evkha", re.I)


def chaines_suspectes(source: str) -> list[str]:
    """Chaînes littérales nommant la plateforme, docstrings exclues.

    Seules les littérales comptent : ce sont elles qui peuvent finir sous les
    yeux du lecteur. Une première rédaction lisait le fichier ligne à ligne et
    signalait le commentaire expliquant ce correctif — elle mesurait son propre
    balisage (corollaire de la règle 9).
    """
    arbre = ast.parse(source)

    docstrings = set()
    for noeud in ast.walk(arbre):
        if isinstance(
            noeud, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        ):
            premier = noeud.body[0] if noeud.body else None
            if (
                isinstance(premier, ast.Expr)
                and isinstance(premier.value, ast.Constant)
                and isinstance(premier.value.value, str)
            ):
                docstrings.add(id(premier.value))

    return [
        noeud.value
        for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Constant)
        and isinstance(noeud.value, str)
        and id(noeud) not in docstrings
        and INTERDIT.search(noeud.value)
    ]


def test_la_mention_de_repli_ne_nomme_personne() -> None:
    """Le défaut d'origine : le repli portait le nom de la plateforme."""
    assert not INTERDIT.search(MENTION_PAR_DEFAUT)
    assert MENTION_PAR_DEFAUT.strip(), "un repli vide laisserait la page nue"


def test_sans_marque_aucun_nom_n_est_invente() -> None:
    """Rien renseigné : il ne reste que la confidentialité, qui ne nomme personne."""
    assert mentions_finales(None) == [MENTION_PAR_DEFAUT]
    assert mentions_finales({}) == [MENTION_PAR_DEFAUT]


def test_les_mentions_sont_celles_de_l_abonne() -> None:
    """C'est le nom de l'abonné qui figure, et lui seul."""
    lignes = mentions_finales(
        {
            "nom": "Pirabel Labs",
            "mention_legale": "SIREN 000 000 000",
            "mention_confidentialite": "Diffusion restreinte",
        }
    )
    assert lignes == ["Pirabel Labs", "SIREN 000 000 000", "Diffusion restreinte"]
    assert not any(INTERDIT.search(ligne) for ligne in lignes)


def test_une_mention_vide_ne_laisse_pas_de_ligne_creuse() -> None:
    """Contre-épreuve : une chaîne vide ne doit pas produire une ligne blanche."""
    assert mentions_finales({"nom": "Atelier Nord", "mention_legale": "  "}) == [
        "Atelier Nord",
        MENTION_PAR_DEFAUT,
    ]


@pytest.mark.parametrize(
    "chemin",
    [
        "backend/generation/rendu_word/assemblage.py",
        "backend/generation/rendu_word/depuis_json.py",
        "backend/generation/rendu_word/composants.py",
        "backend/generation/rendu_word/fixture.py",
        # Ces trois-là décrivent au MODÈLE ce qu'il doit écrire. La docstring
        # d'`Encadre` disait « LECTURE EVKHA » et part dans le schéma de
        # l'outil : chaque vrai document aurait reproduit le nom de la
        # plateforme. Le premier document produit par le nouveau moteur en
        # portait 22 occurrences. Un contrôle qui ne regarde que le rendu ne
        # voit pas ce que la consigne y fait entrer (règle 9).
        "backend/generation/chapitres/schema.py",
        "backend/generation/chapitres/stub.py",
        "backend/generation/chapitres/runner.py",
    ],
)
def test_le_chemin_de_rendu_n_ecrit_aucun_nom_de_plateforme(chemin: str) -> None:
    """Le garde-fou de structure, sur les fichiers qui composent le document.

    `fixture.py` est exclu : ce sont les données de la DÉMO, pas du rendu. Un
    document réel tire ses sources du socle et des chapitres.
    """
    from pathlib import Path

    racine = Path(__file__).resolve().parents[2]
    fautives = chaines_suspectes((racine / chemin).read_text(encoding="utf-8"))
    assert not fautives, (
        f"{chemin} inscrit le nom de la plateforme dans le document : {fautives}"
    )


def test_le_detecteur_attrape_le_code_d_avant() -> None:
    """Contre-épreuve (règle 6) : le détecteur lui-même, et pas seulement
    l'expression, doit signaler le code tel qu'il était écrit.

    Rejouer le test en retirant le correctif ne prouvait rien : le fichier ne
    s'important plus, pytest s'arrêtait à la collecte. Un échec de collecte
    n'est pas la démonstration qu'un contrôle détecte quelque chose.
    """
    avant = (
        "def assembler(marque):\n"
        '    """Assemble l\'étude."""\n'
        "    return {\n"
        '        "mentions_finales": [\n'
        "            \"EVKHA · Système d'analyse de marché\",\n"
        '            "Méthode déposée à l\'INPI",\n'
        "        ],\n"
        "    }\n"
    )
    assert chaines_suspectes(avant) == ["EVKHA · Système d'analyse de marché"]


def test_le_detecteur_ignore_une_docstring_qui_cite_le_terme() -> None:
    """Contre-épreuve inverse : expliquer le défaut ne doit pas le déclencher."""
    legitime = (
        "def mentions(marque):\n"
        '    """Ces mentions portaient EVKHA en dur. Elles viennent de l\'abonné."""\n'
        '    return [marque["nom"]]\n'
    )
    assert chaines_suspectes(legitime) == []

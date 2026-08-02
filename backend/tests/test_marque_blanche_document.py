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
que le lecteur verra.

**Ce fichier a longtemps porté une exemption, et elle était fausse.** Il
déclarait ne pas regarder les noms de styles du gabarit — « des identifiants
internes, jamais affichés dans le corps du document ». Vrai du corps, faux de
l'interface : Word affiche le nom du style courant dans la galerie du ruban et
dans le volet Styles. Le client final de l'abonné lisait donc « EVKHA Corps »
dès qu'il cliquait dans un paragraphe, sur les quatorze styles du gabarit.

Le contrôle et sa réparation regardaient au même endroit — le corps — et
l'exemption écrite noir sur blanc a dispensé d'aller voir ailleurs pendant tout
ce temps (règle 9). D'où le contrôle d'ARCHIVE ajouté en fin de fichier : il
n'exempte rien, et c'est le seul qui prouve quelque chose sur le fichier
réellement expédié.
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


# ── Le nom peut aussi venir d'un fichier de DONNÉES ──────────────────────────
#
# Le détecteur ci-dessus ne lit que du CODE. Il a donc laissé passer le cas
# réel suivant : le modèle de référence, dérivé du document produit par la
# plateforme POUR sa propre cliente, portait « LECTURE EVKHA » sur quinze
# encadrés et « Méthode EVKHA appliquée » en titre de sous-section. Le premier
# document produit par le contrat ordonné nommait la plateforme **seize fois**.
#
# C'est le défaut de la règle 9 : un contrôle qui ne regarde qu'un endroit ne
# trouvera jamais ce qui vit ailleurs. Les deux tests qui suivent regardent les
# données, puis le document rendu.


def test_le_modele_de_reference_ne_nomme_pas_la_plateforme() -> None:
    """Le modèle est recopié dans le document : ses libellés sont visibles."""
    from generation.modele.chargement import CHEMIN_MODELE

    brut = CHEMIN_MODELE.read_text(encoding="utf-8")
    trouves = INTERDIT.findall(brut)
    assert not trouves, (
        f"{len(trouves)} mention(s) de la plateforme dans "
        f"{CHEMIN_MODELE.name} : elles partiraient sur chaque document"
    )


@pytest.mark.django_db
def test_un_document_rendu_ne_nomme_pas_la_plateforme(tmp_path: object) -> None:
    """Le contrôle sur ce que le LECTEUR lit, pas sur ce qu'on lui envoie (règle 3).

    Les deux tests précédents peuvent être verts et le document fautif : c'est
    exactement ce qui s'est produit. Celui-ci ouvre le `.docx` écrit sur disque
    et lit son texte.
    """
    import zipfile
    from pathlib import Path

    from generation.chapitres.runner import _bloc_socle
    from generation.chapitres.schema import ChapitrePayload
    from generation.chapitres.stub import chapitre_de_demonstration
    from generation.rendu_word.assemblage import assembler_etude
    from generation.rendu_word.depuis_json import rendre_etude
    from tests.test_rendu_tous_les_blocs import _socle

    socle = _socle()

    # Les chapitres sont construits par le chemin RÉEL : la doublure recopie les
    # étiquettes du modèle. Un chapitre écrit à la main dans le test ne pourrait
    # pas porter le défaut, et le test ne tomberait donc pas sur le code d'avant
    # (règle 6). Les vingt-et-un, parce que quinze encadrés étaient en cause.
    chapitres = [
        ChapitrePayload.model_validate(
            chapitre_de_demonstration(
                f"{_bloc_socle(socle)}\n\n"
                f"CHAPITRE À RÉDIGER : {numero} — Chapitre {numero}"
            )
        )
        for numero in range(1, 22)
    ]

    etude, _ = assembler_etude(
        socle=socle, chapitres=chapitres, titre="Étude de marché"
    )
    chemin = rendre_etude(etude, Path(str(tmp_path)) / "marque_blanche.docx")

    with zipfile.ZipFile(chemin) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    texte = "".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", xml))

    trouves = INTERDIT.findall(texte)
    assert not trouves, (
        f"la plateforme est nommée {len(trouves)} fois dans le texte du "
        "document rendu"
    )


# ── Le fichier réellement expédié ────────────────────────────────────────────


def test_aucune_partie_du_gabarit_ne_nomme_la_plateforme() -> None:
    """Le test qui échoue sur le code d'avant, et qu'aucune exemption ne borne.

    Un `.docx` est une archive : styles, propriétés, en-têtes, thème, relations.
    Les contrôles précédents lisaient le texte rendu ; celui-ci ouvre le fichier
    et cherche dans **toutes** ses parties. C'est ce qui distingue « ce qu'on a
    écrit » de « ce que le lecteur reçoit » (règle 7).

    Au moment où il a été écrit, il trouvait 28 occurrences dans
    `word/styles.xml` — les 14 identifiants et les 14 noms affichés.
    """
    import zipfile

    from generation.rendu_word.gabarit import GABARIT_DEFAUT

    assert GABARIT_DEFAUT.exists(), "gabarit absent : le rendu ne peut pas tourner"

    coupables: dict[str, int] = {}
    with zipfile.ZipFile(GABARIT_DEFAUT) as archive:
        for membre in archive.namelist():
            contenu = archive.read(membre)
            trouvailles = len(INTERDIT.findall(contenu.decode("utf-8", "ignore")))
            if trouvailles:
                coupables[membre] = trouvailles

    assert not coupables, (
        f"la plateforme est nommee dans le gabarit livre : {coupables}"
    )


def test_le_document_produit_porte_le_nom_de_l_abonne_et_pas_l_outil() -> None:
    """`dc:creator` valait « python-docx », et Word l'affiche.

    Ce n'est pas la même fuite que les styles, mais c'est la même classe : tout
    ce que le lecteur peut voir du fichier doit parler de l'abonné, jamais de
    la chaîne de fabrication.
    """
    import tempfile
    import zipfile
    from pathlib import Path

    from generation.rendu_word.depuis_json import rendre_etude

    etude = {
        "titre": "Étude de marché — vente de voitures d'occasion",
        "sous_titre": "Paris et petite couronne",
        "marque": {"nom": "Cabinet Duval", "couleur_principale": "#123456"},
        "chapitres": [],
    }

    with tempfile.TemporaryDirectory() as dossier:
        produit = rendre_etude(etude, Path(dossier) / "etude.docx")
        with zipfile.ZipFile(produit) as archive:
            core = archive.read("docProps/core.xml").decode("utf-8")
            parties = {
                membre: len(
                    INTERDIT.findall(
                        archive.read(membre).decode("utf-8", "ignore")
                    )
                )
                for membre in archive.namelist()
            }

    assert "python-docx" not in core, "l'outil de fabrication signe le document"
    assert "Cabinet Duval" in core, "le document ne porte pas le nom de l'abonne"
    assert not {k: v for k, v in parties.items() if v}, (
        "la plateforme est nommee dans le document produit"
    )

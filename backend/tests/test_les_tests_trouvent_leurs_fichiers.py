"""Aucun test ne doit localiser un fichier du dépôt par rapport au CWD.

Un `Path("backend/...")` ne vaut que si pytest est lancé depuis la racine. Lancé
depuis `backend/`, le test ne trouve plus rien — et l'histoire de ce dépôt
montre ce qui se passe alors : on ne répare pas le chemin, on pose un `skip`
dessus.

C'est ainsi que `test_template_definit_le_style_action` a dormi des mois, avec
pour motif « bug pré-existant […] à corriger séparément ». Pendant ce temps
`generation/templates/generation/document.html` — le gabarit qui produit ce que
le client lit vraiment — n'était verrouillé par aucun test. Un test qui saute ne
verrouille rien (règle 1).

Corriger les quatre occurrences ne suffit pas : la cinquième s'écrira demain.
Ce test vise la CLASSE (règle 4). La convention à suivre existe déjà dans une
dizaine de fichiers :

    RACINE = Path(__file__).resolve().parents[2]

Elle part du fichier de test lui-même, donc elle vaut depuis n'importe quel
répertoire.
"""
from __future__ import annotations

import ast
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
DOSSIER_DES_TESTS = Path(__file__).resolve().parent

#: Premiers segments qui trahissent un chemin du dépôt. On ne devine pas : on
#: liste les dossiers qui existent REELLEMENT a la racine. Un litteral comme
#: `Path("memoire.docx")` — un nom de fichier fictif, pas un chemin du depot —
#: n'en fait donc pas partie, et n'a pas a etre signale.
RACINES_DU_DEPOT = frozenset(
    chemin.name for chemin in RACINE.iterdir() if chemin.is_dir()
)


def _chemins_relatifs_au_repertoire_courant(source: str) -> list[tuple[int, str]]:
    """Rend les `Path("...")` dont le littéral désigne un fichier du dépôt.

    On lit l'arbre syntaxique plutôt que le texte : une expression régulière
    trébucherait sur les appels coupés en plusieurs lignes — et c'est
    exactement sous cette forme que trois des quatre occurrences étaient
    écrites, ce qui les aurait rendues invisibles au contrôle.
    """
    trouves: list[tuple[int, str]] = []
    for noeud in ast.walk(ast.parse(source)):
        if not isinstance(noeud, ast.Call):
            continue
        nom = noeud.func
        appelle_path = (isinstance(nom, ast.Name) and nom.id == "Path") or (
            isinstance(nom, ast.Attribute) and nom.attr == "Path"
        )
        if not appelle_path or not noeud.args:
            continue
        premier = noeud.args[0]
        if not isinstance(premier, ast.Constant) or not isinstance(premier.value, str):
            continue

        litteral = premier.value
        if litteral.startswith(("/", "\\")) or (
            len(litteral) > 1 and litteral[1] == ":"
        ):
            continue  # chemin absolu : il ne depend pas du repertoire courant
        tete = litteral.replace("\\", "/").split("/")[0]
        if tete in RACINES_DU_DEPOT:
            trouves.append((premier.lineno, litteral))
    return trouves


def test_aucun_test_ne_depend_du_repertoire_courant() -> None:
    """La contre-épreuve est dans l'histoire : sur le code d'avant, quatre.

    `test_phase12_gate_et_briques.py` en portait une, neutralisée par un `skip` ;
    `test_rotation_mot_de_passe_pg.py` trois, qui ne passaient que par chance —
    la racine se trouvait être le répertoire de lancement habituel.
    """
    fautifs: list[str] = []
    for fichier in sorted(DOSSIER_DES_TESTS.glob("test_*.py")):
        # `utf-8-sig` et non `utf-8` : au moins un fichier de la suite porte un
        # BOM, que `ast.parse` refuse (« invalid non-printable character
        # U+FEFF »). Le lire en `utf-8` ferait echouer le controle sur un
        # fichier parfaitement sain — un motif faux (regle 2).
        source = fichier.read_text(encoding="utf-8-sig")
        for ligne, litteral in _chemins_relatifs_au_repertoire_courant(source):
            fautifs.append(f"{fichier.name}:{ligne} — Path({litteral!r})")

    assert not fautifs, (
        "Ces tests localisent un fichier du depot par rapport au repertoire "
        "courant. Ils ne trouveront rien si pytest est lance ailleurs qu'a la "
        "racine.\n  "
        + "\n  ".join(fautifs)
        + "\n\nUtiliser RACINE = Path(__file__).resolve().parents[2]."
    )


def test_le_controle_reconnait_un_chemin_fautif() -> None:
    """Contre-épreuve du contrôle lui-même.

    Sans elle, un contrôle qui ne détecte plus rien — parce que l'analyse s'est
    cassée, ou parce que `RACINES_DU_DEPOT` est vide — passerait pour un succès
    (règle 1). On lui soumet donc les deux formes réellement rencontrées, dont
    l'appel coupé en plusieurs lignes.
    """
    sur_une_ligne = 'Path("backend/generation/templates/generation/document.html")'
    coupe_en_deux = 'Path(\n    "backend/organisations/management/commands/x.py"\n)'

    assert len(_chemins_relatifs_au_repertoire_courant(sur_une_ligne)) == 1
    assert len(_chemins_relatifs_au_repertoire_courant(coupe_en_deux)) == 1


def test_le_controle_laisse_passer_ce_qui_est_correct() -> None:
    """Et il ne doit pas bloquer ce qui est correct (règle 6).

    Un nom de fichier fictif, un chemin construit depuis `RACINE`, un chemin
    absolu : aucun des trois ne dépend du répertoire courant.
    """
    corrects = [
        'Path("memoire.docx")',
        'RACINE / "backend/generation/templates/generation/document.html"',
        'Path("/srv/evkha/document.html")',
        'Path(__file__).resolve().parents[2]',
    ]

    for extrait in corrects:
        assert _chemins_relatifs_au_repertoire_courant(extrait) == [], extrait

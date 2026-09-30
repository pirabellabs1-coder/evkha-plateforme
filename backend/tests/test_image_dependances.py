"""L'image de production installe tout ce dont le code a besoin.

Le premier document produit sur le serveur a échoué sur **« No module named
'matplotlib' »**. Deux manques, pas un :

- `matplotlib` n'était déclaré nulle part dans `pyproject.toml`, alors que
  `rendu_word/graphiques.py` l'importe. Le rendu ne fonctionnait que parce que
  la bibliothèque traînait dans l'environnement de développement ;
- le `Dockerfile` installait `[dev,pdf,ai]` : l'extra `word` n'était pas
  installé du tout, donc `python-docx` manquait également.

Aucun test ne pouvait le voir : ils tournent dans un environnement où tout est
présent. C'est la règle 7 — le vert des tests ne dit rien de ce qui est livré.
Ces contrôles-ci comparent des **fichiers**, pas l'environnement courant, et
restent donc valables là où le défaut existait.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
PYPROJECT = RACINE / "pyproject.toml"
DOCKERFILE = RACINE / "backend" / "Dockerfile"

#: Seul extra légitimement absent de l'image : l'outillage de qualité n'a rien
#: à y faire. Il y figure aujourd'hui, ce qui est un autre débat.
EXTRAS_HORS_PRODUCTION = frozenset({"dev"})


def _extras_declares() -> set[str]:
    donnees = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return set(donnees["project"].get("optional-dependencies", {}))


def _extras_installes() -> set[str]:
    """Les extras de la ligne `pip install -e ".[…]"` du Dockerfile."""
    texte = DOCKERFILE.read_text(encoding="utf-8")
    lignes = [
        ligne
        for ligne in texte.splitlines()
        if "pip install" in ligne and not ligne.lstrip().startswith("#")
    ]
    assert lignes, "aucune ligne `pip install` trouvée dans le Dockerfile"
    trouve = re.search(r'-e\s+"\.\[([^\]]+)\]"', " ".join(lignes))
    assert trouve, f"extras illisibles dans : {lignes}"
    return {morceau.strip() for morceau in trouve.group(1).split(",")}


def test_l_image_installe_tous_les_extras_de_production() -> None:
    """La cause du premier échec réel. `word` manquait."""
    attendus = _extras_declares() - EXTRAS_HORS_PRODUCTION
    installes = _extras_installes()
    manquants = attendus - installes
    assert not manquants, (
        f"Extras déclarés mais non installés dans l'image : {sorted(manquants)}. "
        "Le code qui en dépend échouera à l'exécution, et seulement là."
    )


def test_l_image_n_installe_pas_d_extra_inexistant() -> None:
    """Contre-épreuve : une faute de frappe dans le Dockerfile est silencieuse.

    `pip install -e ".[wrod]"` n'échoue pas bruyamment ; l'extra est ignoré.
    """
    inconnus = _extras_installes() - _extras_declares()
    assert not inconnus, (
        f"Le Dockerfile installe des extras qui n'existent pas : {sorted(inconnus)}"
    )


@pytest.mark.parametrize(
    ("module", "extra"),
    [
        ("matplotlib", "word"),
        ("docx", "word"),
        ("weasyprint", "pdf"),
        ("anthropic", "ai"),
    ],
)
def test_les_dependances_du_rendu_sont_declarees(module: str, extra: str) -> None:
    """Chaque bibliothèque importée par le rendu est déclarée quelque part.

    `matplotlib` était importé sans être déclaré. Le test ne vérifie pas qu'il
    s'importe — dans l'environnement de test il s'importe toujours — mais qu'il
    est **écrit dans `pyproject.toml`**, ce qui est précisément ce qui manquait.
    """
    donnees = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    paquets = donnees["project"]["optional-dependencies"][extra]
    # `docx` est fourni par le paquet `python-docx` : on compare sur la racine.
    attendu = {"docx": "python-docx"}.get(module, module)
    assert any(attendu in paquet for paquet in paquets), (
        f"« {attendu} » n'est déclaré dans aucun paquet de l'extra « {extra} » : "
        f"{paquets}"
    )


#: Répertoires de la racine résolus à l'exécution par des chemins `parents[3]`.
#: Ce ne sont pas du code, mais sans eux le moteur s'arrête net.
RESSOURCES_RACINE = ("prompts", "gabarits", "references")


@pytest.mark.parametrize("dossier", RESSOURCES_RACINE)
def test_l_image_embarque_les_ressources_de_la_racine(dossier: str) -> None:
    """Deuxième forme du même défaut : une ressource présente en local, absente
    de l'image.

    La première génération par le nouveau moteur a échoué sur « Prompt
    introuvable : /app/prompts/etude_marche/chapitre_00.md ». Le Dockerfile ne
    copiait que `backend/`, alors que les consignes de rédaction et le gabarit
    Word vivent à la racine.
    """
    assert (RACINE / dossier).is_dir(), f"{dossier}/ absent du dépôt"

    texte = DOCKERFILE.read_text(encoding="utf-8")
    copies = [
        ligne
        for ligne in texte.splitlines()
        if ligne.startswith("COPY") and f" {dossier} " in f" {ligne} "
    ]
    assert copies, (
        f"Le Dockerfile ne copie pas `{dossier}/`. Le code le résout pourtant à "
        "l'exécution : il échouera sur le serveur, et seulement là."
    )


def test_le_detecteur_lit_bien_le_dockerfile() -> None:
    """Un contrôle qui n'a rien à comparer est un échec (règle 1).

    Si l'expression cessait de correspondre, les deux tests ci-dessus
    passeraient sur des ensembles vides.
    """
    installes = _extras_installes()
    assert len(installes) >= 3, installes
    assert "pdf" in installes


# ── La classe entière : tout module importé par la production est déclaré ────
#
# La liste ci-dessus est FERMÉE, et c'est la règle 4 : elle a laissé passer
# `pymupdf` (30/09/2026). Importé par `importlib.import_module("pymupdf")` dans
# `relecture/document.py`, il n'était déclaré nulle part ; la relecture du PDF
# final échouait donc en production, attrapée en silence — et seulement là.
# Ce contrôle lit TOUS les imports du code de production, y compris ceux par
# `import_module("…")`, et exige qu'ils soient déclarés dans `pyproject.toml`.

#: Outils lancés à la main, jamais par l'application (dossier technique).
HORS_PRODUCTION = frozenset({"tests", "scripts", "migrations"})


def _imports_de_production() -> dict[str, set[str]]:
    """Module de premier niveau → fichiers qui l'importent, hors imports de repli.

    Un import placé dans un `try` qui rattrape `ImportError` est un repli
    assumé (`duckduckgo_search` derrière `ddgs`) : il n'engage pas l'image.
    """
    import ast  # noqa: PLC0415

    backend = RACINE / "backend"
    trouves: dict[str, set[str]] = {}
    for fichier in backend.rglob("*.py"):
        parties = set(fichier.relative_to(backend).parts)
        if parties & HORS_PRODUCTION or any(p.endswith(".egg-info") for p in parties):
            continue
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        proteges: set[int] = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Try) and any(
                isinstance(h.type, ast.Name) and h.type.id in ("ImportError", "ModuleNotFoundError")
                or isinstance(h.type, ast.Tuple) and any(
                    isinstance(e, ast.Name) and e.id in ("ImportError", "ModuleNotFoundError")
                    for e in h.type.elts
                )
                for h in noeud.handlers
            ):
                proteges.update(id(n) for bloc in noeud.body for n in ast.walk(bloc))
        for noeud in ast.walk(arbre):
            if id(noeud) in proteges:
                continue
            noms: list[str] = []
            if isinstance(noeud, ast.Import):
                noms = [alias.name for alias in noeud.names]
            elif isinstance(noeud, ast.ImportFrom) and noeud.level == 0 and noeud.module:
                noms = [noeud.module]
            elif (
                isinstance(noeud, ast.Call)
                and getattr(noeud.func, "attr", getattr(noeud.func, "id", "")) == "import_module"
                and noeud.args and isinstance(noeud.args[0], ast.Constant)
                and isinstance(noeud.args[0].value, str)
            ):
                noms = [noeud.args[0].value]
            for nom in noms:
                trouves.setdefault(nom.split(".")[0], set()).add(fichier.name)
    return trouves


def _distributions_declarees() -> set[str]:
    donnees = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    projet = donnees["project"]
    toutes = list(projet.get("dependencies", []))
    for paquets in projet.get("optional-dependencies", {}).values():
        toutes += paquets
    return {
        re.split(r"[<>=!~\[; ]", paquet.strip())[0].lower().replace("_", "-")
        for paquet in toutes
    }


def test_tout_module_importe_par_la_production_est_declare() -> None:
    import sys  # noqa: PLC0415
    from importlib.metadata import packages_distributions  # noqa: PLC0415

    backend = RACINE / "backend"
    locaux = {p.name for p in backend.iterdir() if (p / "__init__.py").exists()}
    declarees = _distributions_declarees()
    distributions = packages_distributions()
    manquants = {
        module: sorted(fichiers)[:3]
        for module, fichiers in _imports_de_production().items()
        if module not in sys.stdlib_module_names and module not in locaux
        and module != "__future__"
        and not any(
            d.lower().replace("_", "-") in declarees
            for d in distributions.get(module, [module])
        )
    }
    assert not manquants, (
        f"Importés par la production mais déclarés nulle part : {manquants}. Ils "
        "ne sont présents que dans l'environnement local : l'image les ignorera."
    )


def test_le_detecteur_voit_les_imports_par_import_module() -> None:
    """Règle 1 : le cas qui a échappé à la liste fermée doit être VU."""
    imports = _imports_de_production()
    assert "pymupdf" in imports and "document.py" in imports["pymupdf"]
    assert "matplotlib" in imports
    assert "duckduckgo_search" not in imports, "un repli sous `except ImportError` n'engage rien"

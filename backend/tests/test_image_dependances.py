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
RESSOURCES_RACINE = ("prompts", "gabarits")


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

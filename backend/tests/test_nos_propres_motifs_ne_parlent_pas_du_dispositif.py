"""Le vocabulaire interne ne se surveille que dans un sens, et c'est un trou.

Cliente, 12/08/2026, sur un motif affiché au tableau de bord : « le pipeline
n'a pas su l'extraire ».

## Pourquoi ce n'est pas qu'une question de mots

Le garde-fou du vocabulaire interne (`chapitres/schema.py`) surveille ce que le
MODÈLE écrit. Il ne surveille pas ce que NOUS lui écrivons — et les motifs du
gate ne restent pas au tableau de bord : `correction.py` les réinjecte dans la
consigne envoyée au modèle pour qu'il corrige. Un motif qui dit « pipeline »
apprend le mot au rédacteur, qui peut le recopier dans le document.

C'est exactement la fuite signalée le 10/08/2026 — « socle bloqué », « pipeline
système » lus par la cliente dans un livrable — prise par l'autre bout. Le
livrable est en marque blanche : aucun mot du dispositif n'a le droit d'y
figurer, quelle qu'en soit la provenance.

## Ce que ce test ne prouve pas

Il lit les CHAÎNES du module, pas les motifs produits à l'exécution : un motif
composé à partir d'une variable lui échappe. C'est une garantie sur ce qu'on
écrit à la main — là où le mot est apparu.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

#: Les mots du dispositif. Repris de `_VOCABULAIRE_INTERNE`, la liste qui juge
#: déjà le texte du modèle — une seule source pour ce qui est interdit, deux
#: endroits où l'interdiction s'applique.
MOTS_DU_DISPOSITIF = (
    "pipeline",
    "socle verrouillé",
    "socle bloqué",
    "hors socle",
    "gate qualité",
    "prompt système",
    "chapitre 0",
)

#: Les modules dont les chaînes atteignent le modèle ou l'écran.
_MODULES_A_LIRE = ("gate.py", "correction.py", "checks_post_rendu.py")


def _chaines_du_module(nom: str) -> list[tuple[int, str]]:
    """Les littéraux de texte, hors commentaires et docstrings.

    Un commentaire a le DROIT de dire « pipeline » : il explique le système à
    qui le lit. Seul ce qui part vers le modèle ou vers l'écran est jugé.
    """
    source = (
        Path(__file__).resolve().parents[1] / "generation" / nom
    ).read_text(encoding="utf-8")

    # On retire les docstrings triple-quotes AVANT de chercher les chaînes.
    sans_docstring = re.sub(r'"""[\s\S]*?"""', '""', source)

    trouvees: list[tuple[int, str]] = []
    for numero, ligne in enumerate(sans_docstring.split("\n"), start=1):
        nue = ligne.strip()
        if nue.startswith("#"):
            continue
        # Le fragment de commentaire en fin de ligne ne compte pas non plus.
        code = nue.split("  #")[0]
        for litteral in re.findall(r'"([^"\n]{4,})"', code):
            trouvees.append((numero, litteral))
    return trouvees


@pytest.mark.parametrize("module", _MODULES_A_LIRE)
def test_aucun_motif_ne_nomme_le_dispositif(module: str) -> None:
    """Un motif qui dit « pipeline » l'apprend au rédacteur."""
    fautes = [
        (numero, mot, litteral)
        for numero, litteral in _chaines_du_module(module)
        for mot in MOTS_DU_DISPOSITIF
        if mot in litteral.casefold()
    ]

    assert not fautes, "\n".join(
        f"{module}:{numero} — « {mot} » dans : {litteral[:90]}"
        for numero, mot, litteral in fautes
    )


def test_le_test_verrait_la_faute_d_origine() -> None:
    """CONTRE-ÉPREUVE : sans elle, ce test pourrait ne rien lire du tout.

    Une extraction trop zélée — retirer aussi les chaînes ordinaires — le
    rendrait vert sur n'importe quoi. On rejoue donc la faute exacte du
    12/08/2026 sur un texte fabriqué.
    """
    faute = "mais le pipeline n'a pas su l'extraire"

    assert any(mot in faute.casefold() for mot in MOTS_DU_DISPOSITIF)


def test_les_chaines_sont_bien_lues() -> None:
    """CONTRE-ÉPREUVE : le lecteur trouve des chaînes, sinon il ne prouve rien.

    Un module dont on ne lit aucune chaîne passe le test pour de mauvaises
    raisons — c'est la règle 1 : un contrôle qui n'a rien à comparer n'est pas
    un succès.
    """
    for module in _MODULES_A_LIRE:
        assert len(_chaines_du_module(module)) > 20, module

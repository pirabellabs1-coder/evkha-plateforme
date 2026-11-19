"""Gardes de lecture sur l'ÉCRAN de prospection (audit du 19/11/2026).

Quatre défauts de l'écran tenaient à ce qu'il écrivait, pas à ce que le serveur
rendait : un corps de message injecté tel quel dans la page, un plafond recopié
en dur, une promesse (« ajoutez-les à la main ») qu'aucun appel ne tenait, un
envoi en échec que rien ne chargeait.

Ce fichier LIT le source de l'écran. Ce n'est pas un test de rendu : il ne
prouve pas que l'écran s'affiche bien (règle 7), il empêche seulement ces
quatre écritures-là de revenir. Il vit ici, avec la suite que la machine sait
lancer ; sa place naturelle serait la suite du front.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_FRONT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "admin"
_ECRAN = _FRONT / "pages" / "Prospection.tsx"
_API = _FRONT / "apiProspection.ts"


def _sans_commentaires(source: str) -> str:
    """Le code seul : ce qu'un commentaire RACONTE du défaut n'est pas le défaut."""
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"(?m)^\s*//.*$", "", source)


@pytest.fixture(scope="module")
def ecran() -> str:
    # Un contrôle qui n'a rien à lire échoue (règle 1) : pas de `skip` si le
    # fichier a bougé — la garde ne garderait plus rien, en silence.
    assert _ECRAN.is_file(), f"écran introuvable : {_ECRAN}"
    code = _sans_commentaires(_ECRAN.read_text(encoding="utf-8"))
    assert "function CarteBrouillon" in code, "l'écran lu n'est pas celui de la prospection"
    return code


def test_le_corps_d_un_message_n_est_plus_injecte_dans_la_page(ecran: str) -> None:
    """Le corps est écrit par un modèle à partir de pages web : une entrée externe.

    Sur le code d'avant, il passait par `dangerouslySetInnerHTML` — un
    `<img onerror>` lu par l'agent s'exécutait dans la session admin.
    """
    assert "dangerouslySetInnerHTML" not in ecran
    cadres = re.findall(r"<iframe\b[^>]*>", ecran, flags=re.DOTALL)
    assert cadres, "aucun cadre d'aperçu : la garde n'a rien à comparer"
    for cadre in cadres:
        assert 'sandbox=""' in cadre, f"cadre sans isolement : {cadre}"
        assert "srcDoc=" in cadre
    # Aucune permission rendue au cadre, nulle part dans l'écran.
    assert "allow-scripts" not in ecran and "allow-same-origin" not in ecran


def test_le_plafond_des_prospects_n_est_plus_recopie_dans_l_ecran(ecran: str) -> None:
    """Sur le code d'avant : « (max 50) » et `max={50}` en dur, quand la
    recherche en créait au plus 25. L'écran lit le plafond du serveur."""
    assert "max={50}" not in ecran and "(max 50)" not in ecran
    assert "prospects_par_jour_max" in ecran
    assert "prospects_par_jour_max" in _API.read_text(encoding="utf-8")


def test_l_ajout_a_la_main_est_reellement_branche(ecran: str) -> None:
    """Sur le code d'avant : l'écran promettait l'ajout manuel, `creerProspect`
    n'était appelé nulle part. De même pour la correction d'une fiche."""
    assert "api.creerProspect(" in ecran
    assert "api.modifierProspect(" in ecran


def test_les_envois_en_echec_sont_charges_et_ont_leurs_sorties(ecran: str) -> None:
    """Sur le code d'avant : seuls les brouillons prêts et les validés étaient
    chargés — un message en échec disparaissait de l'écran."""
    assert re.search(r'api\.messages\(\{\s*statut:\s*"echoue"\s*\}\)', ecran)
    assert "error_message" in ecran
    assert "api.remettreEnBrouillon(" in ecran

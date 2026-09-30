"""Une décision de la mémoire déclarée comme donnée ne fait plus réécrire un chapitre.

Reprise ÉCLORE `28a257bf` (30/09/2026, mémoire active) : le modèle recopiait
dans `donnees_utilisees` les décisions que la mémoire lui montre
(`statut_2026`, `bloc_INITIAL_atelier_pilote`) ; la validation, qui n'admet que
le socle, faisait réécrire presque chaque chapitre. Avec la mémoire, les
chiffres sont contrôlés par leurs repères : la déclaration hors socle est
retirée, sans reprise.
"""
from __future__ import annotations

import inspect

from generation.chapitres import runner
from generation.chapitres.schema import valider_chapitre
from generation.memoire.etude import MemoireEtude
from generation.memoire.faits import Fait


class _Payload:
    def __init__(self, donnees: list[str]) -> None:
        self.resume = " ".join(f"mot{i}" for i in range(180))
        self.chapitre = 3
        self.donnees_utilisees = donnees
        self.sous_titres: list[object] = []
        self.graphiques: list[object] = []


def _valider(payload: _Payload, *, avec_memoire: bool) -> list[str]:
    return valider_chapitre(
        payload,  # type: ignore[arg-type]
        numero_attendu=3,
        identifiants_socle=frozenset({"apport"}),
        resume_mots_min=150,
        resume_mots_max=250,
        declarations_hors_socle_retirees=avec_memoire,
    )


def test_avec_la_memoire_la_declaration_hors_socle_est_retiree() -> None:
    payload = _Payload(["apport", "statut_2026", "bloc_INITIAL_atelier_pilote"])
    motifs = _valider(payload, avec_memoire=True)
    assert not [m for m in motifs if "socle" in m], motifs
    assert payload.donnees_utilisees == ["apport"]


def test_sans_la_memoire_elle_reste_un_motif() -> None:
    """Contre-épreuve : sans mémoire, `donnees_utilisees` garde les chiffres — le refus reste."""
    motifs = _valider(_Payload(["apport", "statut_2026"]), avec_memoire=False)
    assert [m for m in motifs if "statut_2026" in m]


def test_le_redacteur_passe_la_memoire_a_la_validation() -> None:
    source = inspect.getsource(runner.generer_chapitre)
    assert "declarations_hors_socle_retirees=memoire is not None" in source


def test_le_rappel_dit_ce_que_donnees_utilisees_admet() -> None:
    fait = Fait(id="ca_previsionnel_an1", valeur=1.0, unite="EUR", libelle="CA", origine="sourcee")
    rappel = runner.rappel_des_reperes(MemoireEtude(faits={fait.id: fait}))
    assert "ne liste que des identifiants du socle" in rappel

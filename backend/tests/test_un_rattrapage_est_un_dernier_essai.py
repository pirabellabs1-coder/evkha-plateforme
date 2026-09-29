"""Le rattrapage final d'un chapitre manquant est un DERNIER essai — et le dit.

Revue du 29/09/2026 : `_refaire_les_chapitres_manquants` n'a qu'un essai par
chapitre, mais appelait `produire_chapitre` sans `derniere_tentative`. La
validation le prenait pour un essai ordinaire : le chapitre 3 de `bf98827c`
(résumé de 148 mots pour 150) serait mort une seconde fois, à sa dernière
chance.
"""
from __future__ import annotations

from typing import Any

import pytest

from generation.controle_final import RapportRelecture, _refaire_les_chapitres_manquants
from generation.memoire.controle import motif_des_signaux


def test_le_rattrapage_declare_son_dernier_essai(monkeypatch: pytest.MonkeyPatch) -> None:
    from generation import chapitres, cost

    appels: list[dict[str, Any]] = []

    class _Chapitres:
        def exclude(self, **_k: Any) -> _Chapitres:
            return self

        def order_by(self, *_a: Any) -> _Chapitres:
            return self

        def values_list(self, *_a: Any, **_k: Any) -> list[int]:
            return [3]

    class _Job:
        id = "rattrapage"
        chapters = _Chapitres()

    monkeypatch.setattr(chapitres, "produire_chapitre", lambda *a, **k: appels.append(k))
    monkeypatch.setattr(cost, "budget_restant", lambda _job: 100.0)
    rapport = RapportRelecture()

    _refaire_les_chapitres_manquants(_Job(), rapport)  # type: ignore[arg-type]

    assert rapport.chapitres_rattrapes == [3]
    assert appels and appels[0].get("derniere_tentative") is True


def test_les_signaux_accompagnent_une_reprise_en_un_seul_motif() -> None:
    """Vingt signaux ne remplissent plus la limite de longueur des motifs."""
    signaux = [
        f"Chiffre écrit en clair « {n} 000 € » : ni un fait de la mémoire ni une réponse "
        "du client — c'est un calcul ou une invention. Cite le repère du fait voulu "
        "({{…}}), ou retire le chiffre."
        for n in range(20)
    ]
    motif = motif_des_signaux(signaux)
    assert "« 0 000 € »" in motif and "(et 8 autre(s))" in motif
    assert len(motif) < 400


def test_sans_signal_aucun_motif() -> None:
    assert motif_des_signaux([]) == ""

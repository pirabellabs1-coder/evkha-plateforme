"""Deux chapitres ne recommandent pas deux premières cibles différentes.

Étude de marché à l'export, cliente, 26/10/2026 : « le chapitre 7 recommande la
Corée, le Japon et Taïwan ; le chapitre 17 recommande la Chine en premier ».
Le lecteur n'a plus de décision à prendre : il en a deux, et elles s'excluent.

Deux verrous, qui ne jugent pas sur la même évidence (règle 9) : le bloc de
consigne rend au rédacteur ce que les chapitres précédents ont tranché ; le
contrôle de relecture constate la contradiction sur le document entier.
"""
from __future__ import annotations

from generation.decisions import bloc_des_decisions, decisions_du_chapitre
from generation.relecture import Document, Reference, document_du_chapitre, relire
from generation.relecture.comptages import _priorites_contradictoires

COREE = (
    "Au vu des barrières d'entrée, la Corée du Sud est retenue comme première "
    "cible, devant le Japon et Taïwan."
)
CHINE = "En priorité, c'est le marché de la Chine qu'il faut ouvrir dès 2027."


def _document(*phrases: str) -> Document:
    return document_du_chapitre({
        "chapitre": 7,
        "titre": "Zones visées",
        "blocs": [
            bloc
            for rang, phrase in enumerate(phrases)
            for bloc in (
                {"type": "titre_sous_section", "numero": f"7.{rang + 1}",
                 "intitule": "Choix de zone"},
                {"type": "paragraphe", "texte": phrase},
            )
        ],
    })


# ── Le contrôle : deux premières cibles qui ne se recoupent pas ─────────────


def test_deux_premieres_cibles_se_contredisent() -> None:
    [constat] = _priorites_contradictoires(_document(COREE, CHINE))
    assert constat.classe == "decision"
    assert constat.section == "7.2"
    assert "7.1" in constat.detail
    assert constat.grave is True


def test_une_priorite_qui_precise_l_autre_ne_dit_rien() -> None:
    """Contre-épreuve : les deux phrases nomment la Corée, la seconde précise."""
    assert _priorites_contradictoires(_document(
        COREE,
        "La première étape reste la Corée du Sud, par Séoul et Busan.",
    )) == []


def test_une_seule_priorite_ne_dit_rien() -> None:
    """Contre-épreuve."""
    assert _priorites_contradictoires(_document(COREE)) == []


def test_un_constat_sans_rang_ne_dit_rien() -> None:
    """Contre-épreuve : un chiffre sur la Chine n'ordonne aucune cible."""
    assert _priorites_contradictoires(_document(
        COREE,
        "Le marché de la Chine croît de 8 % par an depuis 2022.",
    )) == []


def test_une_priorite_sans_nom_propre_ne_dit_rien() -> None:
    """Contre-épreuve : « il faut prioriser » ne se verrouille pas."""
    assert _priorites_contradictoires(_document(
        "La première cible doit être choisie selon la marge nette.",
        "En priorité, il faudra arbitrer entre les deux options.",
    )) == []


def test_le_constat_remonte_par_la_relecture() -> None:
    constats = relire(_document(COREE, CHINE), Reference())
    assert any(c.classe == "decision" and c.section == "7.2" for c in constats), [
        c.motif() for c in constats
    ]


# ── Le verrou amont : la décision part au chapitre suivant ──────────────────


def test_une_decision_est_extraite_du_chapitre() -> None:
    payload = {
        "chapitre": 7,
        "titre": "Zones visées",
        "blocs": [{"type": "paragraphe", "texte": COREE}],
    }
    [decision] = decisions_du_chapitre(7, payload)
    assert decision.chapitre == 7
    assert "Corée du Sud" in decision.phrase


def test_une_observation_n_est_pas_extraite() -> None:
    """Contre-épreuve : sans verbe de décision, rien n'est verrouillé."""
    assert decisions_du_chapitre(7, {
        "chapitre": 7, "titre": "T",
        "blocs": [{"type": "paragraphe",
                   "texte": "Le marché de la Corée du Sud pèse 2,1 Md€ en 2025."}],
    }) == []


def test_un_payload_vide_ne_casse_rien() -> None:
    assert decisions_du_chapitre(7, {}) == []
    assert decisions_du_chapitre(7, None) == []


class _Chapitre:
    def __init__(self, numero: int, payload: dict[str, object] | None) -> None:
        self.chapter_number = numero
        self.payload = payload


class _Chapitres:
    def __init__(self, chapitres: list[_Chapitre]) -> None:
        self._chapitres = chapitres

    def filter(self, **_critere: int) -> _Chapitres:
        avant = _critere["chapter_number__lt"]
        return _Chapitres([c for c in self._chapitres if c.chapter_number < avant])

    def exclude(self, **_critere: object) -> _Chapitres:
        return _Chapitres([c for c in self._chapitres if c.payload])

    def order_by(self, *_champs: str) -> list[_Chapitre]:
        return sorted(self._chapitres, key=lambda c: c.chapter_number)


class _Job:
    def __init__(self, chapitres: list[_Chapitre]) -> None:
        self.chapters = _Chapitres(chapitres)


def test_le_bloc_dit_que_la_decision_est_close() -> None:
    job = _Job([_Chapitre(7, {
        "chapitre": 7, "titre": "T", "blocs": [{"type": "paragraphe", "texte": COREE}],
    })])
    bloc = bloc_des_decisions(job, 17)
    assert "DÉCISIONS DÉJÀ PRISES" in bloc
    assert "Corée du Sud" in bloc
    assert "chapitre 7" in bloc
    # Contre-épreuve : le chapitre 7 lui-même ne reçoit pas sa propre décision.
    assert bloc_des_decisions(job, 7) == ""

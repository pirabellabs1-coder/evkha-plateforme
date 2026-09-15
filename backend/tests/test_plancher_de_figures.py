"""Les figures : plus de quota, une complétion qui reste, un seul motif d'absence.

## L'histoire

06/08/2026, la cliente : « au moins 17 à 25 graphes par document, c'est une
obligation absolue ». Le quota a été demandé au modèle, complété depuis le
socle, puis vérifié sur le document livré.

15/09/2026, le client : « et si on enlève d'avoir un nombre exact de figures
tout simplement, c'est très bloquant ». Mesuré le même jour sur la génération
test `cd639627` : le socle de la stratégie ne permettait que quatre figures, la
consigne en réclamait vingt-deux, et le modèle en a inventé huit, toutes
abandonnées au rendu. Le quota ne produisait pas de figures, il produisait des
demandes impossibles.

## Ce que ces tests tiennent

1. **La consigne ne chiffre plus aucun objectif**, et dit qu'un chapitre sans
   figure est normal quand aucune donnée ne s'y prête.
2. **Le contrôle ne signale plus un plancher** ; il signale encore un document
   où AUCUNE figure n'a pu être dessinée.
3. **La complétion** tire toujours du socle de vraies figures pour les chapitres
   qui n'en ont pas, et le nombre annoncé au rapport est celui que le lecteur
   VOIT — la fiche projet, rendue autrement, n'en reçoit pas.
"""
from __future__ import annotations

import re
from typing import Any

import pytest

from generation.prompts import PLANCHER_FIGURES
from generation.rendu_word.assemblage import RapportAssemblage, _completer_les_figures
from generation.verification import controles
from generation.verification.rapport import Gravite

# ── 1. La consigne ───────────────────────────────────────────────────────────


def test_la_consigne_ne_chiffre_plus_aucun_objectif_de_figures() -> None:
    from generation.prompts import OBJECTIF_FIGURES_TEXTE

    assert not re.search(r"\d+\s+figures", OBJECTIF_FIGURES_TEXTE)
    assert "pas de nombre à atteindre" in OBJECTIF_FIGURES_TEXTE
    assert "Un chapitre sans figure est normal" in OBJECTIF_FIGURES_TEXTE


# ── 2. Le contrôle ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("rendues", [1, 4, PLANCHER_FIGURES - 1, PLANCHER_FIGURES])
def test_un_document_avec_peu_de_figures_n_est_plus_signale(rendues: int) -> None:
    """Sur le code d'avant : « 4 figures dans le document, pour un plancher de 17 »."""
    assert controles.controler_visuels(20, rendues, [], []) == []


def test_un_document_sans_aucune_figure_garde_son_motif_d_origine() -> None:
    """L'ancien cas reste distinct : « aucune n'a pu être dessinée ».

    C'est un autre défaut — le socle ne nourrit rien — et il mérite son propre
    motif. Le fondre dans le plancher ferait perdre l'information. Mesuré sur
    la stratégie Zenitek (12/09/2026) : 31 figures demandées, 31 refusées au
    dessin, zéro rendue. Le motif dit aussi ce qui a été fait de leurs données.
    """
    anomalies = controles.controler_visuels(20, 0, [], [])

    assert not [a for a in anomalies if a.gravite is Gravite.BLOQUANTE]
    signalees = [a for a in anomalies if a.gravite is Gravite.AVERTISSEMENT]
    assert len(signalees) == 1
    assert "Aucun des 20" in signalees[0].detail
    assert "tableau" in signalees[0].detail


# ── 3. La complétion ─────────────────────────────────────────────────────────


class _Payload:
    """Le strict nécessaire : la complétion ne lit que ces trois attributs."""

    def __init__(self, numero: int, titre: str, donnees: list[str]) -> None:
        self.chapitre = numero
        self.titre = titre
        self.donnees_utilisees = donnees


class _Profil:
    libelle = "Test"
    graphiques_a_eviter: tuple[str, ...] = ()


def _resolution_toujours_possible(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le socle n'est pas le sujet ici : on isole la logique de complétion."""
    from generation.rendu_word import assemblage
    from generation.rendu_word.donnees_graphiques import Resolution

    def resoudre(_socle: Any, type_graphique: str, ids: Any) -> Resolution:
        return Resolution(
            type_graphique=type_graphique,
            donnees={"valeurs": [(str(i), 1.0) for i in ids]},
        )

    monkeypatch.setattr(assemblage, "resoudre", resoudre)


def test_la_completion_ramene_le_document_au_plancher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sur le code d'avant, un document à trois figures restait à trois."""
    _resolution_toujours_possible(monkeypatch)

    # Sept chapitres citant six données : quatre partent dans une première
    # figure, les deux restantes dans une seconde. Quatorze figures possibles,
    # quatorze manquantes — le plancher est atteint pile, sans marge, ce qui
    # est le cas intéressant.
    payloads = [
        _Payload(n, f"Chapitre {n}", [f"donnee_{n}_{s}" for s in "abcdef"])
        for n in range(1, 8)
    ]
    blocs = [
        {"numero": p.chapitre, "titre": p.titre, "blocs": []} for p in payloads
    ]
    rapport = RapportAssemblage()
    rapport.graphiques_rendus = 3

    _completer_les_figures(blocs, payloads, object(), _Profil(), rapport)

    assert rapport.graphiques_rendus == PLANCHER_FIGURES
    assert len(rapport.graphiques_completes) == PLANCHER_FIGURES - 3
    # Ce qui est compté est ce qui est POSÉ dans les chapitres (règle 9).
    poses = sum(
        1 for c in blocs for b in c["blocs"] if b["type"] == "graphique"
    )
    assert poses == PLANCHER_FIGURES - 3


def test_la_completion_ne_touche_pas_a_la_fiche_projet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le chapitre 0 récapitule le brief, il n'analyse rien.

    Et surtout, le gabarit le rend autrement : une figure posée là était
    comptée au rapport sans jamais paraître dans le document. Mesuré :
    dix-sept annoncées, seize visibles.
    """
    _resolution_toujours_possible(monkeypatch)

    payloads = [_Payload(0, "Fiche projet", ["a", "b"]),
                _Payload(1, "Premier", ["c", "d"])]
    blocs = [
        {"numero": p.chapitre, "titre": p.titre, "blocs": []} for p in payloads
    ]
    rapport = RapportAssemblage()

    _completer_les_figures(blocs, payloads, object(), _Profil(), rapport)

    fiche = next(c for c in blocs if c["numero"] == 0)
    assert not [b for b in fiche["blocs"] if b["type"] == "graphique"]
    assert all("Chapitre 0" not in c for c in rapport.graphiques_completes)


def test_la_completion_ne_redessine_pas_deux_fois_la_meme_figure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Elle repasse tant qu'elle progresse : sans garde, elle bouclerait.

    Un seul chapitre, deux données : il n'y a qu'une figure à en tirer. Le
    compte y serait en la répétant — l'information, non.
    """
    _resolution_toujours_possible(monkeypatch)

    payloads = [_Payload(1, "Unique", ["a", "b"])]
    blocs = [{"numero": 1, "titre": "Unique", "blocs": []}]
    rapport = RapportAssemblage()

    _completer_les_figures(blocs, payloads, object(), _Profil(), rapport)

    assert rapport.graphiques_rendus == 1
    assert len(blocs[0]["blocs"]) == 1


def test_la_completion_varie_les_formes(monkeypatch: pytest.MonkeyPatch) -> None:
    """« Les graphes ne seront pas toujours les mêmes. »

    Quatre entonnoirs de suite tiendraient le plancher en trahissant la
    demande.
    """
    _resolution_toujours_possible(monkeypatch)

    payloads = [
        _Payload(n, f"Chapitre {n}", [f"d{n}a", f"d{n}b"]) for n in range(1, 9)
    ]
    blocs = [
        {"numero": p.chapitre, "titre": p.titre, "blocs": []} for p in payloads
    ]
    rapport = RapportAssemblage()

    _completer_les_figures(blocs, payloads, object(), _Profil(), rapport)

    formes = {
        b["graphique"] for c in blocs for b in c["blocs"] if b["type"] == "graphique"
    }
    assert len(formes) >= 4, f"une seule forme répétée : {formes}"


def test_un_document_deja_conforme_n_est_pas_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contre-épreuve : on n'ajoute rien à un document qui tient déjà le quota.

    Sans elle, la complétion pousserait chaque document au plafond et le
    « — repères chiffrés » deviendrait la moitié des figures.
    """
    _resolution_toujours_possible(monkeypatch)

    payloads = [_Payload(1, "Premier", ["a", "b"])]
    blocs = [{"numero": 1, "titre": "Premier", "blocs": []}]
    rapport = RapportAssemblage()
    rapport.graphiques_rendus = PLANCHER_FIGURES

    _completer_les_figures(blocs, payloads, object(), _Profil(), rapport)

    assert rapport.graphiques_rendus == PLANCHER_FIGURES
    assert not rapport.graphiques_completes
    assert not blocs[0]["blocs"]


def test_des_candidats_intracables_ne_font_pas_abandonner_le_chapitre(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mesuré sur la stratégie : quatorze figures au lieu de dix-sept.

    Ses quatre premiers identifiants inédits mêlent des pourcentages et un
    montant — le rendu les refuse à raison. La version d'avant passait alors au
    chapitre suivant en comptant sur une passe ultérieure, qui ne venait
    jamais : une passe qui ne fait qu'épuiser des candidats n'ajoute aucune
    figure, donc `progres` reste faux, donc la boucle s'arrête. La paire
    traçable qui suivait n'était jamais atteinte, et rien ne le signalait —
    aucun abandon n'est consigné pour une figure qui n'a jamais été demandée.
    """
    from generation.rendu_word import assemblage
    from generation.rendu_word.donnees_graphiques import Resolution

    refusables = {"melange_a", "melange_b", "melange_c", "melange_d"}

    def resoudre(_socle: Any, type_graphique: str, ids: Any) -> Resolution:
        if any(i in refusables for i in ids):
            return Resolution(motif="unités hétérogènes : %, EUR")
        return Resolution(
            type_graphique=type_graphique,
            donnees={"valeurs": [(str(i), 1.0) for i in ids]},
        )

    monkeypatch.setattr(assemblage, "resoudre", resoudre)

    # Les quatre premiers sont intraçables, la paire utile vient après.
    payloads = [
        _Payload(n, f"Chapitre {n}",
                 ["melange_a", "melange_b", "melange_c", "melange_d",
                  f"bon_{n}_a", f"bon_{n}_b"])
        for n in range(1, 4)
    ]
    blocs = [
        {"numero": p.chapitre, "titre": p.titre, "blocs": []} for p in payloads
    ]
    rapport = RapportAssemblage()
    rapport.graphiques_rendus = PLANCHER_FIGURES - 3

    _completer_les_figures(blocs, payloads, object(), _Profil(), rapport)

    assert rapport.graphiques_rendus == PLANCHER_FIGURES, (
        "la complétion a renoncé au premier refus au lieu d'essayer la suite"
    )


def test_une_figure_ajoutee_est_declaree_dans_le_resume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Une complétion silencieuse serait un mensonge par omission.

    Le lecteur du rapport doit pouvoir distinguer une figure voulue par le
    modèle d'une figure ajoutée pour tenir le plancher.
    """
    _resolution_toujours_possible(monkeypatch)

    payloads = [_Payload(1, "Premier", ["a", "b"])]
    blocs = [{"numero": 1, "titre": "Premier", "blocs": []}]
    rapport = RapportAssemblage()

    _completer_les_figures(blocs, payloads, object(), _Profil(), rapport)

    assert "1 complétés" in rapport.resume()
    assert "Chapitre 1" in rapport.graphiques_completes[0]

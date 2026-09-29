"""Une métadonnée de chapitre ne coûte plus un chapitre entier.

Reprise ÉCLORE `bf98827c` (29/09/2026, mémoire active, sans envoi) : quatre
chapitres sont morts après trois essais payés, et aucun sur un défaut du texte :

- chapitre 3 : « Le résumé fait 148 mots ; attendu entre 150 et 250 » ;
- chapitres 15 et 16 : « `apport` est déclaré plusieurs fois dans
  `donnees_utilisees` » (et `ebe_an1` à `ebe_an3`) ;
- chapitre 17 : « 37 500 € », le seuil légal de franchise de TVA, pris pour un
  chiffre inventé.

Le résumé n'est jamais rendu dans le document : il sert de contexte aux
chapitres suivants. `donnees_utilisees` est une liste déclarative. Et un seuil
légal daté est une règle de la mémoire, sourcée. Aucun des trois ne justifie
un trou dans le document.
"""
from __future__ import annotations

from generation.chapitres.schema import valider_chapitre
from generation.memoire.controle import controler_le_chapitre
from generation.memoire.etude import MemoireEtude


class _Payload:
    """Porteur minimal, avec les seuls champs que la validation lit."""

    def __init__(self, resume: str, donnees: list[str] | None = None) -> None:
        self.resume = resume
        self.chapitre = 3
        self.donnees_utilisees: list[str] = list(donnees or [])
        self.sous_titres: list[object] = []
        self.graphiques: list[object] = []


def _mots(nombre: int) -> str:
    return " ".join(f"mot{i}" for i in range(nombre))


def _valider(payload: _Payload, *, derniere_tentative: bool = False) -> list[str]:
    return valider_chapitre(
        payload,  # type: ignore[arg-type]
        numero_attendu=3,
        identifiants_socle=frozenset({"apport", "ebe_an1"}),
        resume_mots_min=150,
        resume_mots_max=250,
        derniere_tentative=derniere_tentative,
    )


def test_un_identifiant_declare_deux_fois_ne_fait_pas_reprendre() -> None:
    """Le cas exact des chapitres 15 et 16 : la déclaration est dédoublonnée."""
    payload = _Payload(_mots(180), ["apport", "ebe_an1", "apport"])
    motifs = _valider(payload)
    assert not [m for m in motifs if "plusieurs fois" in m], motifs
    assert payload.donnees_utilisees == ["apport", "ebe_an1"]


def test_au_dernier_essai_un_resume_un_peu_court_garde_le_chapitre() -> None:
    """Le cas exact du chapitre 3 : 148 mots pour 150."""
    motifs = _valider(_Payload(_mots(148)), derniere_tentative=True)
    assert not [m for m in motifs if "résumé" in m.lower()], motifs


def test_avant_le_dernier_essai_le_resume_court_reste_un_motif() -> None:
    """Contre-épreuve : le modèle garde ses chances de bien faire (`test_resume_raccourci`)."""
    motifs = _valider(_Payload(_mots(148)))
    assert [m for m in motifs if "résumé" in m.lower()]


def test_un_seuil_legal_de_tva_n_est_pas_un_chiffre_invente() -> None:
    """Le cas exact du chapitre 17 : « 37 500 € » est la franchise de TVA (art. 293 B CGI)."""
    payload = {
        "chapitre": 17,
        "titre": "Risques",
        "resume": "",
        "blocs": [{"type": "paragraphe", "texte": "Au-delà de 37 500 € de chiffre "
                   "d'affaires, la franchise en base de TVA cesse (seuil majoré : 41 250 €)."}],
    }
    controle = controler_le_chapitre(payload, MemoireEtude(faits={}))
    assert not [s for s in controle.signaux if "37 500" in s or "41 250" in s], controle.signaux


def test_un_montant_quelconque_reste_signale() -> None:
    """Contre-épreuve : seuls les seuils légaux sont connus, pas tout montant rond."""
    payload = {
        "chapitre": 17,
        "titre": "Risques",
        "resume": "",
        "blocs": [{"type": "paragraphe", "texte": "Une perte de 37 700 € est possible."}],
    }
    controle = controler_le_chapitre(payload, MemoireEtude(faits={}))
    assert [s for s in controle.signaux if "37 700" in s]

"""Phase 27 — Faux positif verticale « prives » vs « privatifs ».

Constat SYNAPSES v3 : le brief liste « bureaux prives », le modele redige
« bureaux privatifs ». Meme sens metier, meme famille de mots (radical
`priv`), mais le check exigeait un match strict et bloquait le document.

Regle 4 : viser la classe, pas l'exemple. Une correction du seul cas
« prives -> privatifs » resterait un remede par cas. La classe : deux mots
qui partagent un radical suffisamment long designent la meme chose. On
accepte donc un mot du brief comme « traite » si :
  a) le mot exact est present dans le texte, OU
  b) un mot du texte commence par un prefixe d'au moins 4 lettres du mot
     du brief (60 % de sa longueur, arrondi au superieur).

Contre-epreuve indispensable : une verticale REELLEMENT effacee reste
bloquee. Sinon on remplace le faux positif par un faux negatif — pire.
"""
from __future__ import annotations

import pytest

from generation.gate import _verticale_present

# ── Cas SYNAPSES v3 : le vrai faux positif ──────────────────────────────────


def test_bureaux_prives_est_couvert_par_bureaux_privatifs() -> None:
    """Le brief : « bureaux prives ». Le doc : « bureaux privatifs ».
    Avant : le check reportait la verticale absente."""
    doc = "Le batiment comporte des bureaux privatifs a l'etage."

    assert _verticale_present("bureaux prives", doc) is True


# ── Autres variantes lexicales frequentes ────────────────────────────────────


@pytest.mark.parametrize(
    ("needle", "doc"),
    [
        ("stockage",         "Espaces de stocker les archives commerciales."),
        ("domiciliation",    "La domiciliations d'entreprise est proposee."),
        ("professionnel",    "Un accompagnement des professionnels du secteur."),
        ("sportif",          "Activites sportives et sport doux hebdomadaires."),
        ("commercial",       "L'offre commerciale s'adresse aux TPE."),
    ],
)
def test_les_variantes_lexicales_du_meme_radical_sont_acceptees(
    needle: str, doc: str
) -> None:
    """Chaque paire partage un radical d'au moins 4-5 lettres."""
    assert _verticale_present(needle, doc) is True


# ── Contre-epreuves : les vraies absences restent bloquees ──────────────────


def test_une_verticale_absente_reste_signalee() -> None:
    """La regle plus permissive ne doit pas transformer en oui tout ce qui
    est present dans le document. Un mot totalement absent doit rester non
    trouve — sinon le gate laisserait passer les vraies verticales effacees
    (defaut SYNAPSES v1 : cinq verticales sur dix supprimees par Gamma)."""
    doc = (
        "L'offre est centree sur le coworking et la domiciliation "
        "d'entreprises, avec des salles de reunion."
    )

    assert _verticale_present("hebergement serveurs", doc) is False
    assert _verticale_present("evenementiel", doc) is False


def test_un_prefixe_trop_court_ne_matche_pas_n_importe_quoi() -> None:
    """« pro » (3 lettres) n'est PAS un radical suffisant : il matcherait
    « projet », « proche », « produit ». Le seuil minimum de 4 lettres
    protege des matches accidentels."""
    doc = "Ce projet touche plusieurs professions proches du secteur."

    # Un mot de 3 lettres n'est PAS admis comme radical : plancher 4 lettres.
    assert _verticale_present("pro", doc) is False


def test_un_mot_du_needle_absent_meme_par_radical_bloque() -> None:
    """« self-stockage » decoupe en « self » et « stockage ». Si « self » est
    absent (le doc parle juste de « stockage »), la verticale est bloquee.
    C'est exactement la protection de SYNAPSES v1."""
    doc = "Le site propose du stockage a la carte pour les entrepreneurs."

    assert _verticale_present("self stockage", doc) is False

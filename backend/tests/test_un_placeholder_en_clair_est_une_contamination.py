"""« prix non publié en ligne au [date du jour] » ne doit jamais partir tel quel.

Le lot 85 fait écrire ce gabarit au modèle, à charge pour lui de substituer la
date réelle. Rien ne vérifiait qu'il l'avait fait : `PLACEHOLDER_TOKENS` ne
connaissait que TODO, PLACEHOLDER et XXX, en majuscules et sans crochets.
Relevé par la relecture du 26/09/2026.

Ces phrases ne passent pas par l'alternation à `\\b` des labels internes — un
crochet n'est pas un caractère de mot — d'où une liste échappée à part,
comparée sans tenir compte de la casse.

La contre-épreuve garde ce qui est légitime : une date écrite, ou l'expression
« la date du jour » sans crochets, ne sont pas des placeholders.
"""
from __future__ import annotations

import re

import pytest

from generation.gate import _FORBIDDEN_TOKEN_RE, _INTERNAL_LABEL_ONLY_RE
from generation.internal_labels import INTERNAL_LABEL_NAMES
from generation.validation import (
    _CALLOUT_CLOSE_RE,
    _CALLOUT_OPEN_RE,
    _PLACEHOLDER_PATTERNS,
)

CONTAMINE = [
    pytest.param("prix non publié en ligne au [date du jour].", id="date-du-jour"),
    pytest.param("Tarif [À COMPLÉTER] par le client.", id="a-completer-majuscules"),
    pytest.param("Segment [a definir] lors du pilote.", id="a-definir-sans-accent"),
    pytest.param("Lorem ipsum dolor sit amet.", id="lorem-ipsum"),
]

LEGITIME = [
    pytest.param("Tarifs relevés le 26 septembre 2026.", id="date-ecrite"),
    pytest.param("La date du jour figure en couverture.", id="sans-crochets"),
    pytest.param("Le [[UNDERSTAND]] encadré est légitime en brut.", id="callout-brut"),
]


@pytest.mark.parametrize("texte", CONTAMINE)
def test_un_placeholder_en_clair_est_vu_par_les_deux_niveaux_du_gate(texte: str) -> None:
    assert _FORBIDDEN_TOKEN_RE.search(texte), texte
    assert _INTERNAL_LABEL_ONLY_RE.search(texte), texte


@pytest.mark.parametrize("texte", LEGITIME)
def test_le_contenu_legitime_n_est_pas_un_placeholder(texte: str) -> None:
    """Contre-épreuve : le correctif ne doit pas bloquer ce qui est correct."""
    assert not _INTERNAL_LABEL_ONLY_RE.search(texte), texte


def _motif_de_fuite() -> re.Pattern[str]:
    return next(
        motif for code, motif in _PLACEHOLDER_PATTERNS if code == "leaked_internal_label"
    )


@pytest.mark.parametrize("label", INTERNAL_LABEL_NAMES)
def test_la_validation_de_chapitre_connait_chaque_label_interne(label: str) -> None:
    """`validation.py` tenait sa propre copie de la liste, en retard de cinq
    labels (CHIFFRES_A_CITER, BRIEF_CLIENT, DOCUMENTS_DU_CLIENT,
    EVKHA_CACHE_BREAK, REGISTRE_CHIFFRES). Règle 5 : une seule source."""
    assert _motif_de_fuite().search(f"en cohérence avec les {label} ci-dessus")


def test_les_marqueurs_d_encadre_viennent_aussi_de_la_source_unique() -> None:
    assert _CALLOUT_OPEN_RE.search("[[CONSIDER]]")
    assert _CALLOUT_CLOSE_RE.search("[[/ACTION]]")

"""Un accent manquant se RÉPARE, il ne fait pas rejouer un appel.

Étude de marché à l'export, cliente, 26/10/2026 : « toutefise », « precise ».
La doctrine du dépôt sur ce genre de défaut est écrite dans
`chapitres.typographie` : « on répare, on ne refuse pas » — refuser un chapitre
pour un accent ferait rejouer un appel à six centimes pour un défaut que le
code corrige avec certitude.

Il le corrige avec certitude parce que le chapitre écrit le mot juste ailleurs.
Ce qui reste — un mot dont la forme juste vit dans un AUTRE chapitre — est
signalé par `relecture.redaction`, sur le document entier.
"""
from __future__ import annotations

from generation.chapitres.schema import BlocParagraphe, ChapitrePayload
from generation.chapitres.typographie import reparer_typographie
from generation.orthographe import (
    accent_final_seulement,
    graphies_suspectes,
    reparer_les_accents,
)

# ── Les primitives ──────────────────────────────────────────────────────────


def test_le_corpus_designe_la_graphie_juste() -> None:
    suspectes = graphies_suspectes([
        "La note precise le périmètre.",
        "La méthode précise retenue vaut partout.",
    ])
    assert suspectes == {"precise": "précise"}


def test_un_participe_passe_n_est_jamais_suspect() -> None:
    """Contre-épreuve capitale : « marche » et « marché » sont deux mots."""
    assert graphies_suspectes([
        "Le marché français pèse 2,7 Md€.",
        "La distribution marche à deux vitesses.",
    ]) == {}
    assert accent_final_seulement("marché") is True
    assert accent_final_seulement("précise") is False


def test_les_graphies_de_1990_ne_sont_pas_suspectes() -> None:
    """Contre-épreuve : l'accent circonflexe est facultatif depuis 1990."""
    assert graphies_suspectes([
        "Le cout d'entrée reste élevé.", "Le coût d'entrée a été recalculé.",
    ]) == {}


def test_la_reparation_garde_la_majuscule() -> None:
    suspectes = {"precise": "précise", "donnees": "données"}
    assert reparer_les_accents(
        "Precise les donnees de la douane.", suspectes,
    ) == "Précise les données de la douane."


def test_la_reparation_ne_touche_pas_les_mots_voisins() -> None:
    """Contre-épreuve : un remplacement de CHAÎNE abîmerait « precisement »."""
    suspectes = {"precise": "précise"}
    assert reparer_les_accents("Il precise precisement.", suspectes) == (
        "Il précise precisement."
    )


def test_la_reparation_est_idempotente() -> None:
    suspectes = {"precise": "précise"}
    une = reparer_les_accents("La note precise.", suspectes)
    assert reparer_les_accents(une, suspectes) == une


def test_sans_suspect_le_texte_ne_bouge_pas() -> None:
    assert reparer_les_accents("La méthode précise.", {}) == "La méthode précise."


# ── La passe du chapitre ────────────────────────────────────────────────────


def _paragraphes(payload: ChapitrePayload) -> list[str]:
    """Les textes des blocs `paragraphe`, typés — `getattr` les rendait `Any`."""
    return [b.texte for b in payload.blocs if isinstance(b, BlocParagraphe)]


def _lettres(texte: str) -> str:
    """Le texte sans ses espaces : seules les lettres, accents compris, comptent."""
    return "".join(c for c in texte if not c.isspace())


def _payload(*paragraphes: str) -> ChapitrePayload:
    return ChapitrePayload.model_validate({
        "chapitre": 4,
        "titre": "Segmentation du marché",
        "accroche": "Trois segments se détachent.",
        "blocs": [{"type": "paragraphe", "texte": p} for p in paragraphes],
        "resume": "Le chapitre pose les segments retenus et leurs volumes.",
    })


def test_le_chapitre_repare_ses_propres_accents() -> None:
    """Le test qui échoue sur le code d'avant : la passe ne voyait pas les accents."""
    payload = _payload(
        "La note precise le périmètre retenu pour les trois zones.",
        "La méthode précise retenue vaut pour les trois zones visées.",
    )
    retouches = reparer_typographie(payload)
    textes = _paragraphes(payload)
    assert retouches >= 1
    assert "precise" not in " ".join(textes)
    assert "précise le périmètre" in " ".join(textes)


def test_un_chapitre_sain_n_est_pas_touche() -> None:
    """Contre-épreuve : la réparation ne doit pas frapper ce qui va bien."""
    payload = _payload(
        "Le marché français pèse 2,7 Md€ et le marché export 2,1 Md€.",
        "La distribution marche à deux vitesses selon les régions.",
    )
    avant = _paragraphes(payload)
    reparer_typographie(payload)
    apres = _paragraphes(payload)
    # La passe typographique pose l'insécable avant « Md€ » — c'est son travail,
    # et ce n'est pas un accent. On compare donc les LETTRES.
    assert [_lettres(t) for t in apres] == [_lettres(t) for t in avant]


def test_le_titre_du_chapitre_sert_de_corpus() -> None:
    """« marché » dans le titre ne doit pas faire corriger « marche » du texte.

    Contre-épreuve du piège le plus proche : le titre d'un chapitre d'étude
    contient presque toujours « marché ».
    """
    payload = _payload("La distribution marche à deux vitesses selon les régions.")
    reparer_typographie(payload)
    assert "marche à deux vitesses" in _paragraphes(payload)[0]

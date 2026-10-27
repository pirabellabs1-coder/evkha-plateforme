"""Les coquilles d'accent, trouvées sans dictionnaire : le document contre lui-même.

Étude de marché à l'export, cliente, 26/10/2026 : « toutefise », « precise »,
« acheteurs transfrontalier », « 275 000 000 de ». Aucun dictionnaire français
n'est installé dans l'image — mais une faute d'accent se trahit seule quand le
document écrit le mot juste ailleurs.
"""
from __future__ import annotations

from generation.orthographe import accent_final_seulement
from generation.relecture import Document, Reference, document_du_chapitre, relire
from generation.relecture.redaction import (
    _nombres_sans_echelle,
    _orthographe_a_deux_graphies,
)


def _document(*paragraphes: str) -> Document:
    return document_du_chapitre({
        "chapitre": 4,
        "titre": "Segmentation",
        "blocs": [{"type": "paragraphe", "texte": p} for p in paragraphes],
    })


# ── Le même mot, deux graphies ──────────────────────────────────────────────


def test_un_accent_manquant_se_voit_par_son_jumeau() -> None:
    constats = _orthographe_a_deux_graphies(_document(
        "La note precise le périmètre retenu.",
        "La méthode précise retenue vaut pour les trois zones.",
    ))
    assert [c.classe for c in constats] == ["orthographe"]
    assert "« precise »" in constats[0].detail
    assert "« précise »" in constats[0].detail
    assert constats[0].grave is False


def test_un_participe_passe_n_est_pas_une_faute() -> None:
    """Contre-épreuve capitale : « marche » et « marché » sont deux mots.

    Tout verbe du premier groupe oppose son présent à son participe sur le seul
    accent final. Un contrôle qui les signalerait crierait à chaque page.
    """
    assert _orthographe_a_deux_graphies(_document(
        "Le marché français pèse 2,7 Md€.",
        "La chaîne de distribution marche à deux vitesses.",
        "Le chiffre d'affaires visé est noté dans le tableau, et la note le vise.",
    )) == []


def test_les_graphies_de_1990_ne_sont_pas_des_fautes() -> None:
    """Contre-épreuve : l'accent circonflexe est facultatif depuis 1990."""
    assert _orthographe_a_deux_graphies(_document(
        "Le cout d'entrée reste élevé.",
        "Le coût d'entrée a été recalculé.",
    )) == []


def test_les_homographes_ne_sont_pas_des_fautes() -> None:
    """Contre-épreuve : « tache » et « tâche », « cotes » et « côtes »."""
    assert _orthographe_a_deux_graphies(_document(
        "Une tache sur l'emballage suffit à refuser le lot.",
        "La tâche revient au distributeur.",
    )) == []


def test_un_sigle_sans_accent_n_est_pas_une_faute() -> None:
    """Contre-épreuve : les capitales perdent couramment leurs accents."""
    assert _orthographe_a_deux_graphies(_document(
        "Le rapport ETUDES de la douane le confirme.",
        "Les études sectorielles le confirment.",
    )) == []


def test_un_accent_milieu_de_mot_est_signale() -> None:
    constats = _orthographe_a_deux_graphies(_document(
        "Les donnees de la douane couvrent 2024.",
        "Les données de la douane couvrent 2024 et 2025.",
    ))
    assert len(constats) == 1
    assert "donnees" in constats[0].detail


def testaccent_final_seulement() -> None:
    assert accent_final_seulement("marché") is True
    assert accent_final_seulement("noté") is True
    assert accent_final_seulement("précise") is False
    assert accent_final_seulement("données") is False
    assert accent_final_seulement("marche") is False


# ── Un nombre en chiffres n'appelle pas de « de » ───────────────────────────


def test_un_nombre_suivi_de_de_est_signale() -> None:
    [constat] = _nombres_sans_echelle(_document(
        "Le marché représente 275 000 000 de dollars en 2025."
    ))
    assert constat.classe == "orthographe"
    assert constat.grave is True
    assert "275 millions" in constat.detail


def test_un_mot_d_echelle_ne_declenche_rien() -> None:
    """Contre-épreuve : c'est la forme CORRECTE."""
    assert _nombres_sans_echelle(_document(
        "Le marché représente 275 millions de dollars, soit 2,7 milliards d'euros "
        "sur la période, pour 5 000 clients et 3 % de marge."
    )) == []


def test_un_nombre_sans_de_ne_declenche_rien() -> None:
    assert _nombres_sans_echelle(_document(
        "Le marché représente 275 000 000 dollars en 2025."
    )) == []


def test_les_constats_remontent_par_la_relecture() -> None:
    """Les contrôles doivent être BRANCHÉS, pas seulement écrits."""
    constats = relire(
        _document(
            "La note precise le périmètre retenu.",
            "Le marché représente 275 000 000 de dollars en 2025.",
            "La méthode précise retenue couvre trois zones.",
        ),
        Reference(),
    )
    orthographe = [c for c in constats if c.classe == "orthographe"]
    # Les deux défauts, chacun sur SA phrase : `relire` dédoublonne par
    # (classe, section, extrait), donc deux constats d'une même phrase n'en
    # feraient qu'un — ce qui est le comportement voulu.
    assert len(orthographe) == 2, [c.motif() for c in constats]
    assert {"precise" in c.detail for c in orthographe} == {True, False}

"""Les sources vont au chapitre des sources, et nulle part ailleurs.

## La règle, et depuis quand elle existe

Cahier des charges « Étude de la concurrence » v1, **18/05/2026**, présent dans
`references/systemes/02-etude-concurrence-cdc-v1.pdf` depuis le 30 juillet :

    Les sources doivent être listées uniquement en fin de réponse totale.
    Ne jamais intégrer les sources : au milieu du texte, dans les paragraphes,
    à la fin des sections.

Rappelée par la cliente le 28/10/2026 : « Pas d'URL brutes dans le texte : les
sources vont dans le chapitre dédié. »

## Pourquoi un contrôle, et pas une consigne de plus

La consigne existe déjà à six endroits de `prompt_library` (« Sources
uniquement en fin de reponse totale »). Cinq mois n'ont pas suffi. Une septième
formulation n'y changerait rien.

## Ce que la mesure a corrigé dans mon propre diagnostic

Un `grep` brut sur le PDF de l'étude `e150aade` comptait **douze** adresses dans
le document, et je l'ai annoncé ainsi. La mesure fine en remet huit à leur
place : elles sont dans le tableau du chapitre 9, `Organisme | Ce que la source
étaye | Année`. **Les vraies fautes sont quatre, en prose, aux sections 5.4 et
6.4.** Un contrôle bâti sur les douze aurait puni le chapitre qui fait son
travail.
"""
from __future__ import annotations

from generation.relecture import Document, Reference, document_du_chapitre, relire
from generation.relecture.sources import _adresses_au_fil_du_texte

#: La forme exacte relevée en 5.4 et 6.4 : une source nommée, puis son adresse.
EN_PROSE = (
    "Sources : FEVS, bilan 2025, via Pleinchamp "
    "(https://www.pleinchamp.com/actualite/en-2025-les-exportations-de-vins)."
)


def _chapitre(numero: int, titre: str, *paragraphes: str) -> Document:
    return document_du_chapitre({
        "chapitre": numero,
        "titre": titre,
        "blocs": [{"type": "paragraphe", "texte": p} for p in paragraphes],
    })


def test_une_adresse_en_prose_fait_reprendre() -> None:
    [constat] = _adresses_au_fil_du_texte(
        _chapitre(6, "Estimation des chiffres d'affaires", EN_PROSE), None,
    )
    assert constat.classe == "source"
    assert constat.grave is True
    assert "Sources et méthodologie" in constat.detail


def test_le_chapitre_des_sources_n_est_jamais_puni() -> None:
    """La contre-épreuve qui compte : il fait son travail en les portant."""
    assert _adresses_au_fil_du_texte(
        _chapitre(9, "Sources et méthodologie", EN_PROSE), None,
    ) == []
    # Et par son NUMÉRO, quand le document entier est relu.
    assert _adresses_au_fil_du_texte(
        _chapitre(9, "Un titre que le motif ne reconnaît pas", EN_PROSE), 9,
    ) == []


def test_un_nom_de_concurrent_n_est_pas_une_source() -> None:
    """Contre-épreuve : une adresse SANS chemin désigne un acteur, pas une source.

    Dans une étude de la concurrence, citer le site d'un concurrent est le
    sujet même du chapitre. C'est le CHEMIN qui fait la référence de source.
    """
    assert _adresses_au_fil_du_texte(
        _chapitre(1, "Identification des concurrents",
                  "Vinatis (https://vinatis.com) domine le segment en ligne."),
        None,
    ) == []


def test_une_cellule_de_tableau_est_laissee_tranquille() -> None:
    """Contre-épreuve : une colonne « Site » d'un panel est légitime."""
    document = document_du_chapitre({
        "chapitre": 1,
        "titre": "Identification des concurrents",
        "blocs": [
            {"type": "paragraphe", "texte": "Le panel retient onze acteurs."},
            {"type": "tableau", "tableau": {
                "entetes": ["Concurrent", "Site"],
                "lignes": [["Vinatis", "https://vinatis.com/vins-de-bordeaux"]],
            }},
        ],
    })
    assert _adresses_au_fil_du_texte(document, None) == []


def test_un_chapitre_sans_adresse_ne_dit_rien() -> None:
    """Contre-épreuve : la forme NORMALE d'une source nommée dans le texte."""
    assert _adresses_au_fil_du_texte(
        _chapitre(6, "Estimation",
                  "Sources : FEVS, bilan 2025 ; Team France Export, 2025."),
        None,
    ) == []


def test_un_seul_constat_par_section() -> None:
    """Dix motifs identiques mangeraient la place des autres."""
    constats = _adresses_au_fil_du_texte(
        _chapitre(6, "Estimation", EN_PROSE, EN_PROSE, EN_PROSE), None,
    )
    assert len(constats) == 1


def test_le_constat_remonte_par_la_relecture() -> None:
    """Le contrôle doit être BRANCHÉ, et dès la relecture d'un chapitre seul —
    c'est le seul moment où le texte peut encore être repris."""
    constats = relire(_chapitre(6, "Estimation", EN_PROSE), Reference())
    assert any(c.classe == "source" and c.grave for c in constats), [
        c.motif() for c in constats
    ]

def test_une_annexe_porte_la_provenance_a_bon_droit() -> None:
    """Contre-épreuve trouvée par la RÉPÉTITION À BLANC du 28/10/2026.

    Une annexe intitulée « B — Sources par acteur » ne commence pas par
    « Sources » : elle échappait à l'exemption, et le chapitre a brûlé DEUX
    tentatives payantes avant d'être gardé. Une annexe est l'endroit où vivent
    la méthode et la provenance.
    """
    document = document_du_chapitre({
        "chapitre": 4,
        "titre": "Positionnement et annexes",
        "blocs": [
            {"type": "titre_sous_section", "numero": "Annexe",
             "intitule": "B — Sources par acteur"},
            {"type": "paragraphe", "texte": EN_PROSE},
        ],
    })
    assert _adresses_au_fil_du_texte(document, None) == []


def test_l_annexe_des_chiffres_est_exemptee() -> None:
    """Son titre ne contient pas le mot « source », et c'est pourtant cela."""
    from generation.rendu_word.annexe_chiffres import TITRE

    assert _adresses_au_fil_du_texte(_chapitre(22, TITRE, EN_PROSE), None) == []


def test_les_sources_de_la_croissance_ne_sont_pas_exemptees() -> None:
    """Contre-épreuve de l'exemption : le mot seul ne suffit jamais.

    « 1.3 Les sources de la croissance » parle d'origines économiques, pas de
    références. Elle n'a aucune raison de porter une adresse.
    """
    document = document_du_chapitre({
        "chapitre": 1,
        "titre": "Le marché",
        "blocs": [
            {"type": "titre_sous_section", "numero": "1.3",
             "intitule": "Les sources de la croissance"},
            {"type": "paragraphe", "texte": EN_PROSE},
        ],
    })
    [constat] = _adresses_au_fil_du_texte(document, None)
    assert constat.section == "1.3"

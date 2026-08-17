"""Le client lit une étude, jamais le journal de la machine qui l'a écrite.

Cliente, 11/08/2026 : « il y a encore quelques éléments qui ressortent comme
socle bloqué / pipeline système etc qui ne doivent pas être vus du client ».

## La contre-épreuve porte tout le poids

« socle », « pipeline », « prompt », « runner » sont des mots légitimes : un
pipeline COMMERCIAL, un socle de CLIENTÈLE, un socle RÉGLEMENTAIRE, un prompt
dans une étude sur l'IA, un runner dans une étude sur la course à pied. Les
bannir seuls tuerait des chapitres justes — c'est exactement l'erreur commise
la veille avec une liste de mots sectoriels trop large, qui a coûté un
chapitre parfaitement correct.

Chaque motif porte donc SON QUALIFICATIF, et ne reconnaît que des locutions
qui n'ont aucun sens hors de nos propres rouages.
"""
from __future__ import annotations

import pytest

from generation.chapitres.schema import (
    BlocParagraphe,
    ChapitrePayload,
    motifs_de_balisage,
)


def _chapitre(texte: str) -> ChapitrePayload:
    return ChapitrePayload(
        chapitre=3,
        titre="Chapitre d'essai",
        blocs=[BlocParagraphe(texte=texte)],
        resume="Un résumé d'essai suffisamment long pour tenir sa borne basse.",
    )


@pytest.mark.parametrize(
    ("nom", "texte"),
    [
        ("socle bloqué", "Le socle bloqué ne porte pas cette donnée."),
        ("socle verrouillé", "D'après le socle verrouillé de l'étude, le marché croît."),
        ("socle de données", "Le socle de données retient 600 M€."),
        ("hors socle", "Ce chiffre est hors socle et reste indicatif."),
        ("pipeline système", "Le pipeline système a produit ce chapitre."),
        ("gate qualité", "Le gate qualité a validé cette section."),
        ("prompt système", "Conformément au prompt système, voici la synthèse."),
        ("chapitre 0", "Comme indiqué au chapitre 0, le projet vise Lyon."),
        ("identifiants du socle", "Les identifiants du socle donnent 1,2 Md€."),
        ("livrable bloqué", "Ce livrable bloqué part en relecture."),
    ],
)
def test_le_vocabulaire_du_dispositif_est_refuse(nom: str, texte: str) -> None:
    motifs = motifs_de_balisage(_chapitre(texte))

    assert motifs, f"« {nom} » devrait être refusé"
    assert "DISPOSITIF" in motifs[0]


@pytest.mark.parametrize(
    "texte",
    [
        "Le pipeline commercial des concurrents repose sur trois canaux.",
        "L'entreprise s'appuie sur un socle de clientèle fidèle de 400 comptes.",
        "Le socle réglementaire du secteur impose une traçabilité complète.",
        "Un prompt bien rédigé améliore la pertinence des réponses de l'outil.",
        "Le marché du running compte 12 millions de pratiquants en France.",
        "La livraison est bloquée au-delà de trois jours ouvrés chez deux acteurs.",
        "Le socle technique des plateformes concurrentes date de 2018.",
        "Ce segment est le socle de la rentabilité du projet.",
    ],
)
def test_le_francais_de_metier_traverse_intact(texte: str) -> None:
    """LA contre-épreuve : un mot n'est interne que par son qualificatif.

    Un correctif qui bannirait « socle » ou « pipeline » seuls passerait tous
    les tests ci-dessus et détruirait des phrases parfaitement justes — le
    remède qui frappe ce qui n'était pas malade (règle 2).
    """
    assert motifs_de_balisage(_chapitre(texte)) == []


def test_la_consigne_nomme_les_rouages_a_taire() -> None:
    """La cause, pas seulement le garde-fou : chaque refus coûte une reprise."""
    from generation.chapitres.runner import _SYSTEME

    assert "Ne nomme JAMAIS nos rouages" in _SYSTEME
    assert "pipeline système" in _SYSTEME
    assert "gate qualité" in _SYSTEME

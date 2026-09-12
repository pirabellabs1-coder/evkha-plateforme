"""Une source qui vient du dossier client n'a pas d'URL, et n'en aura jamais.

Reprise `8ad03a60` du 11/09/2026, premier dossier réel généré APRÈS la lecture
des documents déposés : le document s'appuyait sur le prévisionnel et les
études du client, et le contrôle des sources lui reprochait « 0 URL vérifiable
pour 3 sources listées ». Deux de ces trois sources étaient les données du
client — un prévisionnel n'est pas publié, il n'aura jamais d'adresse web.

Le contrôle exigeait la moitié des sources avec un lien. En rendant les
documents du client exploitables, on a mécaniquement fait de ces sources la
MAJORITÉ : le motif serait désormais tombé sur chaque stratégie bien faite.
Un contrôle qui crie faux finit débranché (règle 2), et c'est la cliente qui
avait signalé ce défaut-là sur d'autres motifs.

Le ratio ne porte donc plus que sur les sources EXTÉRIEURES — celles qui, elles,
doivent être vérifiables. Ces tests échouent sur le code d'avant.
"""
from __future__ import annotations

from generation.checks_post_rendu import detecter_sources_non_tracables


def _motifs(corps: str) -> list[str]:
    """Le contrôle lit des sections `(numéro, titre, corps)`, comme le gate."""
    sections = [
        (1, "Introduction", "Texte du chapitre."),
        (20, "Sources et méthodologie", corps),
    ]
    return [d.motif for d in detecter_sources_non_tracables(sections)]


def test_les_donnees_du_client_ne_comptent_pas_dans_le_ratio() -> None:
    """Deux sources du dossier, une extérieure avec son lien : rien à redire."""
    corps = (
        "- Insee, services informatiques, 2025 — https://www.insee.fr/fr/statistiques/1234\n"
        "- Données du projet : chiffre d'affaires annuel et part de récurrent\n"
        "- Données du projet : prix des trois formules d'abonnement\n"
    )
    assert "ratio_faible" not in _motifs(corps)


def test_une_source_exterieure_sans_lien_reste_signalee() -> None:
    """CONTRE-ÉPREUVE : l'exigence tient là où elle a un sens."""
    corps = (
        "- Xerfi, panorama du secteur, 2025\n"
        "- Statista, marché français, 2024\n"
        "- Données du projet : panier moyen constaté\n"
    )
    assert "ratio_faible" in _motifs(corps)


def test_un_document_fonde_uniquement_sur_le_dossier_client_passe() -> None:
    """Une stratégie bâtie sur le seul prévisionnel n'a aucun lien à fournir."""
    corps = (
        "- Données du projet : prévisionnel transmis par le dirigeant\n"
        "- Document client : relevé des abonnements en cours\n"
    )
    assert _motifs(corps) == []

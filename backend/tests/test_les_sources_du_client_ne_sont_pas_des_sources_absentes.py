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


# ── Les sources vivent dans un TABLEAU, pas dans une liste ───────────────────

#: Le chapitre 20 de la reprise `8ad03a60` (11/09/2026), réduit à sa forme :
#: un tableau de sources, puis des puces qui décrivent la démarche.
CHAPITRE_REEL = """Trois familles de sources fondent l'étude.

| Thématique | Source | Nature de la donnée | Année |
| --- | --- | --- | --- |
| Données marché | Insee, activités informatiques | Taille de marché | 2022 |
| Données marché | Numeum, panorama du numérique | Croissance annuelle | 2025 |
| Documents client | Analyse interne de rentabilité | Marge (données du projet) | 2026 |
| Documents client | Prévisionnel de l'ensemble | Chiffre d'affaires (données du projet) | 2025 |
| Documents client | Fichier commercial | Abonnés (données du projet) | 2025 |

Démarche suivie :
- Lecture du dossier, puis entretien avec le dirigeant.
- Chiffrage du coût de revient par abonné.
- Hiérarchisation des décisions à trente jours.
"""


def test_les_sources_d_un_tableau_sont_comptees() -> None:
    """La chaîne Word rend les sources en TABLEAU.

    Le contrôle ne savait lire que des puces : sur le dossier réel il a compté
    trois puces de méthodologie — qui ne sourcent rien — et ignoré les cinq
    sources listées juste au-dessus. Il jugeait sur ce qu'il savait lire, pas
    sur ce que le lecteur lit (règle 3), et son motif nommait un ensemble
    introuvable dans le document (règle 2).
    """
    from generation.checks_post_rendu import _sources_listees

    sources = _sources_listees(CHAPITRE_REEL)
    assert len(sources) == 5
    assert all("Démarche" not in s and "Lecture du dossier" not in s for s in sources)


def test_deux_sources_publiques_sans_lien_restent_signalees() -> None:
    """Et le motif devient VRAI : Insee et Numeum doivent porter leur adresse."""
    motifs = _motifs(CHAPITRE_REEL)
    assert "ratio_faible" in motifs


def test_les_memes_sources_publiques_avec_leur_lien_passent() -> None:
    """CONTRE-ÉPREUVE : avec les liens, plus rien à redire."""
    avec_liens = CHAPITRE_REEL.replace(
        "Insee, activités informatiques",
        "Insee, activités informatiques — https://www.insee.fr/fr/statistiques/1234",
    ).replace(
        "Numeum, panorama du numérique",
        "Numeum, panorama du numérique — https://numeum.fr/etudes/panorama",
    )
    assert _motifs(avec_liens) == []

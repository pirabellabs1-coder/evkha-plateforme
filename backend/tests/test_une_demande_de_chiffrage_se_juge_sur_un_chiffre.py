"""Une demande de chiffrage n'est traitée ailleurs que là où un chiffre l'accompagne.

## Le défaut mesuré

Business plan `7567ca2f` (15/09/2026), chapitre 20 : « Chiffrer les revenus de
crédits supplémentaires, grands comptes et nouvelles offres | Non traitée ».
Le gate a conclu à une contradiction sur « comptes, crédits, grands,
nouvelles ». Or le chapitre 4 écrivait « Vente de crédits supplémentaires |
Envisagé, non chiffré », et le chapitre 9 « Achats de crédits supplémentaires
(développement futur) ». Le document disait partout la même chose ; le motif
aurait envoyé la correction inventer des revenus jamais chiffrés (règle 2).
"""
from __future__ import annotations

from generation.checks_post_rendu import detecter_demandes_contredites

_REMPLISSAGE = [
    (n, f"Chapitre {n}", "La dirigeante pilote l'activité avec une méthode éprouvée et documentée.")
    for n in (2, 3, 5, 6, 7, 8, 10, 11)
]

_VALIDATION = (
    20, "Validation des demandes",
    "| Chiffrer les revenus de crédits supplémentaires, grands comptes et nouvelles "
    "offres | Non traitée | — | Ces sources de revenus sont mentionnées comme "
    "compléments futurs mais ne sont pas encore quantifiées. |",
)


def _document(*chapitres: tuple[int, str, str]) -> list[tuple[int, str, str]]:
    return [*_REMPLISSAGE, *chapitres, _VALIDATION]


def test_un_sujet_nomme_sans_chiffre_ne_contredit_pas_un_chiffrage_non_traite() -> None:
    """`7567ca2f` : sur le code d'avant, un motif sur « comptes, crédits… »."""
    sections = _document(
        (4, "Activité", (
            "| Levier non compté | Statut | Effet attendu |\n"
            "| Vente de crédits supplémentaires | Envisagé, non chiffré | Hausse du panier B2B |\n"
            "| Grands comptes B2B | Envisagé, non chiffré | Contrats à volume plus élevé |\n"
            "| Nouvelles offres (contrats annuels) | Envisagé, non chiffré | — |"
        )),
        (9, "Modèle économique", (
            "| Sources de revenus | • Abonnements mensuels B2B • Achats de crédits "
            "supplémentaires (développement futur) |"
        )),
    )
    assert detecter_demandes_contredites(sections) == []


def test_un_sujet_chiffre_ailleurs_contredit_le_statut() -> None:
    """CONTRE-ÉPREUVE : si le document chiffre ces revenus, le statut ment."""
    sections = _document(
        (4, "Activité", (
            "Les crédits supplémentaires rapporteront 4 800 € en année 2, portés par "
            "les grands comptes."
        )),
        (9, "Modèle économique", "Les nouvelles offres restent à construire."),
    )
    defauts = detecter_demandes_contredites(sections)
    assert len(defauts) == 1 and defauts[0].chapitre == 20


def test_une_demande_qui_ne_reclame_pas_de_chiffre_reste_jugee_sur_ses_mots() -> None:
    """CONTRE-ÉPREUVE : la règle d'origine (canaux d'acquisition) est intacte."""
    sections = [
        *_REMPLISSAGE,
        (4, "Stratégies commerciales", (
            "Les canaux d'acquisition des onze acteurs se répartissent entre "
            "référencement naturel et partenariats."
        )),
        (20, "Validation", "- Analyser les canaux d'acquisition des concurrents : non traitée."),
    ]
    assert len(detecter_demandes_contredites(sections)) == 1


def test_une_annee_ou_un_numero_de_section_ne_chiffre_rien() -> None:
    sections = _document(
        (4, "Activité", "4.7 Crédits supplémentaires et grands comptes envisagés pour 2028."),
    )
    assert detecter_demandes_contredites(sections) == []


def test_un_renvoi_a_un_chapitre_ne_chiffre_rien() -> None:
    sections = _document(
        (4, "Activité", (
            "Les crédits supplémentaires des grands comptes, voir chapitre 4 pour les détails."
        )),
    )
    assert detecter_demandes_contredites(sections) == []


def _analyse(chapitre: str, demande: str) -> list[tuple[int, str, str]]:
    return [*_REMPLISSAGE, (4, "Concurrence", chapitre), (20, "Validation", demande)]


def test_un_sujet_en_en_tete_de_tableau_chiffre_par_ses_rangees_contredit() -> None:
    """CONTRE-ÉPREUVE (relecture) : sujet dans l'en-tête, montants dans les rangées."""
    sections = _analyse(
        "| Chiffre d'affaires des concurrents | Exercice | Montant |\n"
        "| --- | --- | --- |\n| Alpha | 2025 | 2,3 M€ |\n| Beta | 2025 | 1,1 M€ |",
        "- Estimer le chiffre d'affaires des concurrents : non traitée.",
    )
    assert len(detecter_demandes_contredites(sections)) == 1


def test_un_titre_suivi_de_puces_chiffrees_contredit() -> None:
    """CONTRE-ÉPREUVE (relecture) : titre, ligne vide, puces chiffrées."""
    sections = _analyse(
        "### Chiffre d'affaires des concurrents\n\n- Alpha : 2,3 M€\n- Beta : 1,1 M€",
        "- Estimer le chiffre d'affaires des concurrents : non traitée.",
    )
    assert len(detecter_demandes_contredites(sections)) == 1


def test_une_rangee_chiffree_ne_chiffre_pas_sa_voisine() -> None:
    """`7567ca2f`, chapitre 9 : la rangée des revenus futurs voisine d'une rangée chiffrée."""
    sections = _document(
        (4, "Activité", (
            "| Poste | Détail |\n| --- | --- |\n"
            "| Charges | Rémunération 12 000 €, maintenance 1 200 € |\n"
            "| Sources de revenus | • Achats de crédits supplémentaires, grands comptes "
            "(développement futur) |"
        )),
    )
    assert detecter_demandes_contredites(sections) == []


def test_une_demande_d_analyse_qui_nomme_un_prix_reste_jugee_sur_ses_mots() -> None:
    """CONTRE-ÉPREUVE (relecture) : « politique tarifaire » est un nom, pas un chiffrage."""
    sections = _analyse(
        "La politique tarifaire des concurrents repose sur un abonnement d'entrée "
        "et une remise annuelle.",
        "- Analyser la politique tarifaire des concurrents : non traitée.",
    )
    assert len(detecter_demandes_contredites(sections)) == 1

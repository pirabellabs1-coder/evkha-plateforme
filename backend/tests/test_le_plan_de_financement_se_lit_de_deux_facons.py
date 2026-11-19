"""Le socle ne contredit plus un plan de financement dont le budget comprend le BFR.

Business plan de test `68b6ab61` (19/11/2026), incident de gravité haute :

    `autres_ressources` vaut 20,000 EUR dans le socle, mais ressources
    complémentaires = (investissement total + besoin en fonds de roulement)
    − apport − emprunt donne 38,000 EUR (écart de 18,000).

Le plan était juste : 77 700 € de budget total (trésorerie de départ de 18 000 €
COMPRISE), financés par 10 000 € + 47 700 € + 20 000 €. La mémoire portait le
même double compte, corrigé la veille ; le socle le portait encore (règle 5).
"""
from __future__ import annotations

from datetime import date
from typing import Any

from generation.socle.calculs import appliquer
from generation.socle.referentiel import Perimetre
from generation.socle.schema import DonneeSocle, Fiabilite, Socle, Zone

BP = "business_plan"


def _donnee(identifiant: str, valeur: float, unite: str = "EUR") -> DonneeSocle:
    return DonneeSocle(
        id=identifiant, libelle=identifiant, valeur=valeur, unite=unite,
        annee=2026, perimetre=Perimetre.NATIONAL, fiabilite=Fiabilite.ESTIMEE,
    )


def _socle(**valeurs: float) -> Socle:
    donnees: list[Any] = [_donnee(nom, valeur) for nom, valeur in valeurs.items()]
    return Socle(
        secteur="place de marché", zone=Zone(pays="France"),
        date_socle=date(2026, 11, 19), donnees=donnees, concurrents=[],
    )


def test_un_budget_qui_comprend_sa_tresorerie_ne_contredit_pas_ses_ressources() -> None:
    ajoutees, contradictions = appliquer(
        _socle(
            investissement_total=77_700, bfr=18_000, apport=10_000, emprunt=47_700,
            autres_ressources=20_000,
        ),
        BP,
    )

    assert contradictions == []
    assert ajoutees == []


def test_un_besoin_en_fonds_de_roulement_distinct_reste_admis() -> None:
    """Contre-épreuve : la lecture d'origine tient toujours."""
    _, contradictions = appliquer(
        _socle(
            investissement_total=59_700, bfr=18_000, apport=10_000, emprunt=47_700,
            autres_ressources=20_000,
        ),
        BP,
    )

    assert contradictions == []


def test_des_ressources_qui_ne_bouclent_d_aucune_facon_restent_signalees() -> None:
    """Contre-épreuve : ni 38 000 € ni 20 000 €."""
    _, contradictions = appliquer(
        _socle(
            investissement_total=77_700, bfr=18_000, apport=10_000, emprunt=47_700,
            autres_ressources=5_000,
        ),
        BP,
    )

    assert [c.identifiant for c in contradictions] == ["autres_ressources"]


def test_un_plan_boucle_a_l_euro_ne_recoit_pas_de_ressource_inventee() -> None:
    """Apport + emprunt = budget total : le BFR y est compris, rien n'est à compléter.

    Avant, le calcul ajoutait 18 000 € de « ressources complémentaires » que
    personne n'avait déclarées.
    """
    ajoutees, contradictions = appliquer(
        _socle(investissement_total=77_700, bfr=18_000, apport=30_000, emprunt=47_700),
        BP,
    )

    assert ajoutees == [] and contradictions == []


def test_une_ressource_manquante_se_deduit_toujours_quand_le_plan_ne_boucle_pas() -> None:
    """Contre-épreuve : le rôle « combler » d'origine (27 600 + 4 000 − 1 800 − 20 000)."""
    ajoutees, _ = appliquer(
        _socle(investissement_total=27_600, bfr=4_000, apport=1_800, emprunt=20_000), BP,
    )

    assert [d.id for d in ajoutees] == ["autres_ressources"]
    assert round(ajoutees[0].valeur) == 9_800


def test_un_chiffre_calcule_prend_le_perimetre_du_referentiel() -> None:
    """Le seuil de rentabilité est une donnée de l'ENTREPRISE, même quand le socle
    s'ouvre sur un marché national."""
    ajoutees, _ = appliquer(
        _socle(charges_fixes_an1=28_000, marge_brute_taux=60), BP,
    )

    assert [d.id for d in ajoutees] == ["seuil_rentabilite"]
    assert ajoutees[0].perimetre == Perimetre.ENTREPRISE

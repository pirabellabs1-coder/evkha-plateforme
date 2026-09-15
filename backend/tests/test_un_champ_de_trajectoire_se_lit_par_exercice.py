"""Un champ de chiffre d'affaires découpé par exercice se lit exercice par exercice.

## Le défaut mesuré

Business plan `7567ca2f` (15/09/2026). La cliente remplit le champ CA :
« Année 1 : environ 54 276 €, comprenant environ 40 716 € d'abonnements B2B et
13 560 € de ventes B2C. Année 2 : environ 101 772 €… ». Le mot « CA » n'apparaît
que dans sa note finale : « le CA sera inférieur à 40 716 € ». La relecture par
libellé a verrouillé `ca_previsionnel` = 40 716 €, et le CHECK de la fiche projet
a demandé de corriger 54 276 € — le bon chiffre, repris dans tout le document.
"""
from __future__ import annotations

from intake.financials import raffiner_champs_financiers

CHAMP_7567 = (
    "Septembre à décembre 2026 : environ 6 082,50 €, correspondant à environ "
    "3 540 € d'abonnements B2B et 2 542,50 € de ventes B2C.\n"
    "Année 1 : environ 54 276 €, comprenant environ 40 716 € d'abonnements B2B "
    "et 13 560 € de ventes B2C.\n"
    "Année 2 : environ 101 772 €, comprenant environ 81 432 € d'abonnements B2B "
    "et 20 340 € de ventes B2C.\n"
    "Année 3 : environ 269 721 €, comprenant environ 244 296 € d'abonnements B2B "
    "et 25 425 € de ventes B2C.\n"
    "Attention sur l'interprétation\n"
    "Si tu veux dire « atteindre 17 abonnés à la fin de l'année 1 », le CA sera "
    "inférieur à 40 716 €, puisque les abonnés seront acquis progressivement."
)


def _relu(valeur: str) -> str:
    variables: dict[str, object] = {"CA_PREVISIONNEL": valeur}
    raffiner_champs_financiers(variables)
    return str(variables["CA_PREVISIONNEL"])


def test_le_champ_de_7567ca2f_donne_les_trois_exercices() -> None:
    assert _relu(CHAMP_7567) == "54 276 € / 101 772 € / 269 721 €"


def test_les_exercices_se_rangent_dans_l_ordre() -> None:
    assert _relu("An 2 : 90 000 €\nAn 1 : 60 000 €") == "60 000 € / 90 000 €"


def test_une_liste_a_puces_se_lit_aussi() -> None:
    assert _relu("- Année 1 : 60 000 €\n• Année 2 : 90 000 €") == "60 000 € / 90 000 €"


def test_une_seule_ligne_separee_par_des_points_virgules() -> None:
    """Rejeu sur les briefs de production : `73dde3ab`, `b8da2640`."""
    assert _relu("An1 : 320 000 euros ; An2 : 385 000 euros ; An3 : 430 000 euros") == (
        "320 000 euros / 385 000 euros / 430 000 euros"
    )


def test_un_montant_avant_le_libelle_n_est_pas_remplace_par_un_commentaire() -> None:
    brut = "54 276 € la première année (le CA B2B seul ferait 40 716 €)"
    assert _relu(brut) == brut


def test_le_libelle_en_tete_reste_relu_comme_avant() -> None:
    """CONTRE-ÉPREUVE : SYNAPSES — le CA théorique reste écarté."""
    assert _relu(
        "CA previsionnel An1 : 250 272 €, An2 : 296 000 €, An3 : 318 400 €. "
        "CA theorique a 100 % d'occupation : 455 040 €/an"
    ) == "250 272 € / 296 000 € / 318 400 €"


def test_une_ligne_qui_nomme_un_exercice_sans_montant_ne_compte_pas() -> None:
    """CONTRE-ÉPREUVE : « Année 2 : doublement de l'année 1 » n'est pas un montant."""
    assert _relu("Année 2 : doublement de l'année 1 : 16 Solo, 8 Pro") == (
        "Année 2 : doublement de l'année 1 : 16 Solo, 8 Pro"
    )

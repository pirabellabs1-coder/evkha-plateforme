"""Deux références mal lues, trouvées sur le business plan de test `ac010864`.

Le 16/11/2026, la reprise du business plan `8ead345f` a fini `qa blocked` sur
un document juste. Deux lectures fausses, toutes deux reproduites sans payer :

1. le champ « chiffre d'affaires » du client — titre de la question, puis les
   cinq valeurs seules sur leur ligne, puis l'explication — était verrouillé à
   « 35 € / 38 € », le panier moyen cité dans l'explication. Le gate accusait
   donc 136 800 €, le bon chiffre (règle 2) ;
2. `citysuper.com.hk`, `mymarket.com.hk` et `terroirs.com.hk` avaient pour
   « domaine racine » `com.hk` : trois entreprises de Hong Kong présentées au
   rédacteur comme les offres d'un même groupe.
"""
from __future__ import annotations

from generation.socle.schema import Concurrent, offres_du_meme_groupe
from intake.financials import raffiner_champs_financiers

CHAMP_CA = (
    "Chiffre d'affaires de la première année et évolution sur 5 ans\n"
    "136 800 €, 281 556 €, 513 280 €, 839 800 €, 1 107 920 €.\n"
    "Pourquoi ce calcul : le chiffre d'affaires est construit à partir des commandes "
    "du scénario central (8 000, 18 000, 36 000 et 60 000 commandes de 2027 à 2030), "
    "multipliées par le panier moyen (35 € à 38 €). La société facture la commission "
    "de 21 % et la logistique refacturée."
)


def _acteur(nom: str, site: str) -> Concurrent:
    return Concurrent(nom=nom, type="direct", site_web=site)


def test_une_ligne_de_valeurs_est_la_reponse_du_champ() -> None:
    variables: dict[str, object] = {"CA_PREVISIONNEL": CHAMP_CA}

    raffiner_champs_financiers(variables)

    assert variables["CA_PREVISIONNEL"] == (
        "136 800 € / 281 556 € / 513 280 € / 839 800 € / 1 107 920 €"
    )


def test_une_phrase_qui_cite_un_montant_n_est_pas_une_ligne_de_valeurs() -> None:
    """Contre-épreuve : le format déjà lu par libellé ne change pas."""
    variables: dict[str, object] = {
        "CA_PREVISIONNEL": (
            "CA prévisionnel An1 : 250 272 €, An2 : 296 000 €, An3 : 318 400 €. "
            "CA théorique à 100 % d'occupation : 455 040 €/an"
        )
    }

    raffiner_champs_financiers(variables)

    assert variables["CA_PREVISIONNEL"] == "250 272 € / 296 000 € / 318 400 €"


def test_trois_entreprises_d_un_meme_pays_ne_font_pas_un_groupe() -> None:
    acteurs = [
        _acteur("City'Super", "https://www.citysuper.com.hk"),
        _acteur("My Market", "https://mymarket.com.hk/fr"),
        _acteur("Terroirs", "terroirs.com.hk"),
    ]

    assert [a.domaine for a in acteurs] == [
        "citysuper.com.hk", "mymarket.com.hk", "terroirs.com.hk",
    ]
    assert offres_du_meme_groupe(acteurs) == []


def test_deux_offres_d_une_meme_entreprise_restent_groupees() -> None:
    """Contre-épreuve : le cas qui a fait écrire le regroupement, et sa forme asiatique."""
    ey = [
        _acteur("EY France - Conseil en IA", "https://www.ey.com/fr_fr/ia"),
        _acteur("EY France - Intelligent Automation", "ey.com, page conseil"),
    ]
    city = [
        _acteur("City'Super Hong Kong", "https://www.citysuper.com.hk"),
        _acteur("City'Super en ligne", "https://online.citysuper.com.hk/"),
    ]

    assert [d for d, _ in offres_du_meme_groupe(ey)] == ["ey.com"]
    assert [d for d, _ in offres_du_meme_groupe(city)] == ["citysuper.com.hk"]

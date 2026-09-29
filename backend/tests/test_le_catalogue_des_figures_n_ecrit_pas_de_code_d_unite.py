"""Le catalogue des figures parle l'unité du lecteur, jamais le code de stockage.

## Le défaut

Business plan ÉCLORE (29/09/2026) : « MEUR », « EUR » et « unite » imprimés
dans le document (diagnostic du 29/09/2026, § 3.16). Le socle traduisait déjà
ses propres lignes par `unite_lisible` — `Md€`, jamais `MdEUR` —, mais le
catalogue des figures réalisables, envoyé dans le MÊME prompt, écrivait encore
« (en MEUR) », « (en EUR) », « (en unite) ». Le modèle recopie ce qu'on lui
montre : la leçon était écrite à côté, et pas appliquée ici (règle 4).

Échoue sur le code d'avant : `_unite_commune` rendait le code brut.
"""
from __future__ import annotations

import re
from datetime import date

from generation.rendu_word.catalogue_figures import bloc_figures_possibles, figures_possibles
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Zone, unites_monetaires


def _donnee(identifiant: str, valeur: float, unite: str) -> DonneeSocle:
    return DonneeSocle(
        id=identifiant, libelle=identifiant.replace("_", " ").capitalize(),
        valeur=valeur, unite=unite, annee=2026, perimetre=Perimetre.NATIONAL,
        fiabilite=Fiabilite.DECLAREE,
    )


def _socle() -> Socle:
    """Des millions d'euros, des euros, des effectifs : les trois codes fautifs."""
    return Socle(
        secteur="bien-être", zone=Zone(pays="France"), date_socle=date(2026, 9, 29),
        donnees=[
            _donnee("marche_national_taille", 1250, "MEUR"),
            _donnee("marche_regional_taille", 85, "MEUR"),
            _donnee("ca_actuel", 24852, "EUR"),
            _donnee("panier_moyen", 45, "EUR"),
            _donnee("clientes_potentielles", 120000, "unite"),
            _donnee("clientes_visees", 450, "unite"),
        ],
    )


def test_aucun_code_de_stockage_n_atteint_le_prompt() -> None:
    bloc = bloc_figures_possibles(_socle())
    assert bloc, "le socle d'essai doit produire des figures, sinon le test ne juge rien"

    codes = "|".join(sorted(unites_monetaires(), key=len, reverse=True))
    assert not re.search(rf"\(en (?:{codes}|unite)\)", bloc), bloc


def test_le_catalogue_dit_l_unite_telle_que_le_lecteur_la_lit() -> None:
    unites = {p.unite for p in figures_possibles(_socle())}
    assert "M€" in unites
    assert "€" in unites
    # L'effectif n'a pas de symbole après un nombre, mais la parenthèse doit
    # encore dire au modèle ce que la figure compare.
    assert "unités" in unites
    assert not unites & {"MEUR", "EUR", "unite", ""}

"""Règles métier datées : elles décident, le rédacteur n'a pas à choisir.

## Le défaut, mesuré

29/09/2026, business plan ÉCLORE, p. 61 : « Franchise conservée en 2027
(24 852 € HT) ; TVA appliquée par choix prudent dès 2028 ». Le chiffre
d'affaires 2028 était de 51 132,5 € HT, au-dessus du seuil de franchise des
prestations de services : la TVA n'était pas un choix, elle était
obligatoire. Le prompt réellement envoyé au chapitre juridique tenait en une
ligne (« régime fiscal ») ; aucune règle n'existait nulle part.

## Pourquoi des données datées et sourcées

Les seuils changent (revalorisation triennale des plafonds de la
micro-entreprise, réforme avortée de la franchise en 2025). Un seuil écrit en
dur dans une phrase de prompt vieillit sans prévenir. Ici, chaque seuil porte
son année de validité et sa source : une année non couverte ne rend rien
plutôt qu'un seuil faux.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Nature(StrEnum):
    """Nature de l'activité au sens des seuils fiscaux."""

    SERVICES = "services"
    VENTES = "ventes"


@dataclass(frozen=True)
class Seuil:
    valeur: float
    #: Seuil majoré (tolérance) quand il existe : au-delà, la règle joue
    #: immédiatement, sans attendre l'exercice suivant.
    majore: float | None
    annees: tuple[int, ...]
    source: str


#: Franchise en base de TVA (art. 293 B du CGI). Valeurs maintenues après
#: l'abandon, en 2025, de l'abaissement à 25 000 €.
FRANCHISE_TVA: dict[Nature, Seuil] = {
    Nature.SERVICES: Seuil(37_500, 41_250, (2025, 2026, 2027, 2028, 2029),
                           "art. 293 B CGI — impots.gouv.fr"),
    Nature.VENTES: Seuil(85_000, 93_500, (2025, 2026, 2027, 2028, 2029),
                         "art. 293 B CGI — impots.gouv.fr"),
}

#: Plafonds de chiffre d'affaires de la micro-entreprise (art. 50-0 et 102 ter
#: du CGI), revalorisés pour 2026-2028.
PLAFOND_MICRO: dict[Nature, Seuil] = {
    Nature.SERVICES: Seuil(83_600, None, (2026, 2027, 2028),
                           "art. 50-0 et 102 ter CGI — autoentrepreneur.urssaf.fr"),
    Nature.VENTES: Seuil(203_100, None, (2026, 2027, 2028),
                         "art. 50-0 CGI — autoentrepreneur.urssaf.fr"),
}

#: Tous les tableaux de seuils légaux datés. Le contrôle des chapitres les
#: connaît comme chiffres sourcés : un nouveau tableau s'ajoute ICI.
SEUILS_LEGAUX: tuple[dict[Nature, Seuil], ...] = (FRANCHISE_TVA, PLAFOND_MICRO)


def _seuil(table: dict[Nature, Seuil], nature: Nature, annee: int) -> Seuil | None:
    seuil = table.get(nature)
    if seuil is None:
        return None
    if annee in seuil.annees:
        return seuil
    # Au-delà de la dernière année connue, on garde la dernière valeur connue
    # (un seuil ne baisse pas sans loi) ; avant la première, on ne sait pas.
    if annee > max(seuil.annees):
        return seuil
    return None


@dataclass(frozen=True)
class Decision:
    """Une décision que la règle impose, et la phrase qui la dit."""

    sujet: str
    valeur: str
    annee: int | None
    justification: str
    #: « regle » (imposée par un seuil), « brief » (choix déjà arrêté pour le
    #: projet : tenu, jamais contredit, rédigé dans la voix du document),
    #: « socle » (compte de la base de référence).
    source: str = "regle"


def regime_de_tva(
    ca_ht: float, annee: int, nature: Nature = Nature.SERVICES,
    *, ca_precedent: float | None = None,
) -> Decision | None:
    """Franchise ou TVA obligatoire, selon le chiffre d'affaires HT de l'année ET de la précédente.

    Art. 293 B CGI : la franchise de l'année N exige un chiffre d'affaires N−1
    sous le seuil ET un chiffre d'affaires N sous le seuil majoré. Une année qui
    suit un dépassement du seuil est donc soumise à la TVA dès le 1er janvier,
    même si son propre chiffre d'affaires redescend (revue du 30/09/2026).
    """
    seuil = _seuil(FRANCHISE_TVA, nature, annee)
    if seuil is None:
        return None
    if ca_precedent is not None and ca_precedent > seuil.valeur:
        return Decision(
            "regime_tva", "TVA obligatoire", annee,
            (
                f"chiffre d'affaires HT de l'année précédente au-dessus du seuil de "
                f"franchise ({seuil.valeur:,.0f} €) : la TVA s'applique dès le 1er janvier "
                "— la TVA est OBLIGATOIRE, ce n'est pas un choix"
            ).replace(",", " "),
        )
    if ca_ht <= seuil.valeur:
        return Decision(
            "regime_tva", "franchise en base", annee,
            f"chiffre d'affaires HT sous le seuil de franchise "
            f"({seuil.valeur:,.0f} €)".replace(",", " "),
        )
    # La règle exacte (art. 293 B CGI) a DEUX seuils. Business plan ÉCLORE
    # `28a257bf` (30/09/2026) : « la TVA s'applique dès que le chiffre
    # d'affaires dépasse le seuil de franchise (37 500 €) » — la justification
    # d'ici ne nommait que ce seuil, et le chapitre l'a recopiée. Entre les
    # deux seuils, la franchise vaut encore l'année même ; seul le seuil majoré
    # fait basculer en cours d'année.
    if seuil.majore is not None and ca_ht <= seuil.majore:
        return Decision(
            "regime_tva", "franchise en base, TVA au 1er janvier suivant", annee,
            (
                f"chiffre d'affaires HT au-dessus du seuil de franchise "
                f"({seuil.valeur:,.0f} €) mais sous le seuil majoré ({seuil.majore:,.0f} €) : "
                "la franchise vaut encore cette année, la TVA s'applique au 1er janvier "
                "de l'année suivante — ce n'est pas un choix"
            ).replace(",", " "),
        )
    return Decision(
        "regime_tva", "TVA obligatoire", annee,
        (
            (
                f"chiffre d'affaires HT au-delà du seuil majoré ({seuil.majore:,.0f} €) : "
                "la TVA s'applique dès le jour du dépassement, sans attendre le 1er janvier"
                if seuil.majore is not None else
                f"chiffre d'affaires HT au-dessus du seuil de franchise ({seuil.valeur:,.0f} €)"
            )
            + " — la TVA est OBLIGATOIRE, ce n'est pas un choix"
        ).replace(",", " "),
    )


def depasse_le_plafond_micro(
    ca_ht: float, annee: int, nature: Nature = Nature.SERVICES
) -> Decision | None:
    """Le chiffre d'affaires sort-il du régime de la micro-entreprise ?"""
    seuil = _seuil(PLAFOND_MICRO, nature, annee)
    if seuil is None or ca_ht <= seuil.valeur:
        return None
    return Decision(
        "sortie_micro", "plafond micro-entreprise dépassé", annee,
        (
            f"chiffre d'affaires HT au-dessus du plafond de la micro-entreprise "
            f"({seuil.valeur:,.0f} €) : sortie du régime si le dépassement se "
            "répète deux années civiles consécutives"
        ).replace(",", " "),
    )

"""Une variation que le tableau calcule, reprise en prose avec son acteur, n'est pas inventée.

## Le défaut mesuré

Étude concurrentielle `1caf5b8a`, corpus du 15/09/2026, chapitre 6 : « les
généralistes à catalogue large (Amazon +7,0 %, Zooplus +6,6 %) croissent plus
vite que le marché », « Royal Canin (+15,4 %), Ultra Premium Direct (+21,2 %) ».
Le tableau du même chapitre calcule ces évolutions entre ses deux colonnes de
chiffre d'affaires ; la prose les reprend en nommant l'acteur. Elles étaient
comptées comme des chiffres inventés.

Les estimations et les parts établies en tableau étaient déjà reconnues à la
reprise (8f8e2ed) ; la variation calculée dans sa ligne ne l'était pas.

## Ce qui reste signalé

Une reprise qui ne nomme pas l'acteur, une valeur différente de celle du
tableau, et une « évolution » que la ligne ne permet pas de refaire.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Zone
from generation.verification.controles import controler_chiffres_hors_socle
from generation.verification.lecture import DocumentLu, _dans_son_tableau, mesures_dans


def _socle() -> Socle:
    return Socle(
        secteur="animalerie en ligne", zone=Zone(pays="France"), date_socle=date(2026, 9, 15),
        donnees=[
            DonneeSocle(
                id="marche_national_taille", libelle="Marché national", valeur=6.8,
                unite="MdEUR", annee=2025, perimetre=Perimetre.NATIONAL,
                fiabilite=Fiabilite.DECLAREE,
            ),
        ],
    )


def _prose_signalee(ligne: str, case: str, prose: str) -> bool:
    """La phrase de PROSE est-elle signalée ? La prose passe en premier : le
    contrôle ne rapporte qu'une fois un même texte, et la case du tableau ne doit
    pas répondre à sa place."""
    document = DocumentLu(chemin=Path("corpus.docx"), paragraphes=[prose])
    document.mesures.extend(mesures_dans(prose))
    document.mesures.extend(
        _dans_son_tableau(m, ligne, case) for m in mesures_dans(case, dans_un_tableau=True)
    )
    debut = " ".join(prose.split())[:20]
    return any(
        debut in " ".join(a.extrait.split())
        for a in controler_chiffres_hors_socle(document, _socle())
        if a.controle == "chiffres_hors_socle"
    )


LIGNE = "Évolution 2024-2026 : Zooplus | 5,0 M€ | 5,33 M€ | +6,6 %"


def test_la_variation_du_tableau_reprise_avec_son_acteur_est_admise() -> None:
    prose = "Les généralistes (Zooplus +6,6 %) croissent plus vite que le marché."
    assert not _prose_signalee(LIGNE, "+6,6 %", prose)


@pytest.mark.parametrize(("ligne", "prose", "valeur"), [
    # La reprise ne nomme pas l'acteur.
    (LIGNE, "Un généraliste croît de +6,6 % par an.", "6,6 %"),
    # La valeur n'est pas celle du tableau.
    (LIGNE, "Zooplus progresse de +6,9 % sur la période.", "6,9 %"),
    # La ligne ne refait pas l'évolution : 5,0 → 5,8 M€ font +16 %, pas +6,6 %.
    ("Évolution 2024-2026 : Zooplus | 5,0 M€ | 5,8 M€ | +6,6 %",
     "Les généralistes (Zooplus +6,6 %) croissent plus vite que le marché.", "6,6 %"),
    # Relecture du 15/09/2026 — un libellé qui ne nomme personne.
    ("Évolution : Marché total | 6,0 M€ | 6,44 M€ | +7,3 %",
     "Notre part de marché atteindra 7,3 % en année 3.", "7,3 %"),
    ("Évolution : Moyenne des acteurs | 5,0 M€ | 5,33 M€ | +6,6 %",
     "La moyenne du panier baisse de 6,6 % sur la période.", "6,6 %"),
    # Une addition n'est pas une variation.
    ("Évolution : Amazon | 12 € | 15 € | 27 %", "Amazon détient 27 % du marché.", "27 %"),
    # Deux nombres quelconques de la ligne ne refont pas la variation (+12 %).
    ("Évolution : Zooplus | 5,0 M€ | 5,6 M€ | 150 | 36 | 24 %",
     "Zooplus croît de 24 % sur la période.", "24 %"),
    # La période du tableau n'est ni « d'ici 2030 », ni un rythme annuel.
    (LIGNE, "Zooplus devrait gagner 6,6 % d'ici 2030.", "6,6 %"),
    (LIGNE, "Zooplus croît de 6,6 % par an.", "6,6 %"),
    # Sans période dans l'en-tête, pas de reprise « par an » (`9249e523`).
    ("Évolution : Zooplus | 5,0 M€ | 5,33 M€ | +6,6 %",
     "Zooplus maintient une croissance de 6,6 % par an.", "6,6 %"),
    # Une baisse écrite en hausse n'établit rien.
    ("Évolution : Zooplus | 5,33 M€ | 5,0 M€ | +6,2 %", "Zooplus progresse de +6,2 %.",
     "6,2 %"),
    # Un en-tête qui n'est pas un résultat n'établit rien.
    ("Commentaire : Zooplus | 5,0 M€ | 5,33 M€ | +6,6 %",
     "Les généralistes (Zooplus +6,6 %) croissent plus vite que le marché.", "6,6 %"),
])
def test_ce_que_le_tableau_n_etablit_pas_reste_signale(
    ligne: str, prose: str, valeur: str,
) -> None:
    assert _prose_signalee(ligne, ligne.rsplit(" | ", 1)[1], prose), valeur

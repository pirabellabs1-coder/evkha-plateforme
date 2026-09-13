"""Un chiffre calculé ou sourcé DANS SA PHRASE n'est pas un chiffre hors socle.

## Le défaut mesuré

Corpus de production mesuré le 13/09/2026 : **883 « chiffres hors socle » sur
37 dossiers**, dont 393 sur sept business plans et 409 sur onze études
concurrentielles. Relus un par un, presque aucun n'était une invention. Les
phrases ci-dessous sont celles du corpus.

C'est la consigne `COHERENCE_DES_CHIFFRES` — « UN CALCUL SE MONTRE » — qui fait
écrire le calcul dans la phrase : le prompt l'exigeait, le contrôle le
punissait (règle 5). Et le contrôleur final réécrivait les chapitres pour ce
motif : il repayait des chapitres justes.

## La moitié qui ne doit PAS changer

Les contre-épreuves comptent autant : la base d'un calcul que le socle ignore,
un chiffre de marché sans calcul ni source, un ratio sans ses opérandes restent
signalés. Un contrôle qui justifie tout ne justifie plus rien.

Ces tests échouent sur le code d'avant : la phrase n'était pas lue.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Zone
from generation.verification.controles import controler_chiffres_hors_socle
from generation.verification.lecture import DocumentLu, mesures_dans


def _socle() -> Socle:
    return Socle(
        secteur="boulangerie", zone=Zone(pays="France"), date_socle=date(2026, 9, 14),
        donnees=[DonneeSocle(
            id="ca_actuel", libelle="Chiffre d'affaires", valeur=120000, unite="EUR",
            annee=2026, perimetre=Perimetre.NATIONAL, fiabilite=Fiabilite.DECLAREE,
        )],
    )


def _signales(phrase: str) -> set[str]:
    document = DocumentLu(chemin=Path("corpus.docx"), paragraphes=[phrase])
    document.mesures.extend(mesures_dans(phrase))
    return {
        a.detail.split("»")[0].strip("« ").strip()
        for a in controler_chiffres_hors_socle(document, _socle())
        if a.controle == "chiffres_hors_socle"
    }


@pytest.mark.parametrize(("phrase", "resultat"), [
    ("Vérification : 244 296 divisé par 269 721 donne 0,906, soit 90,6 % du chiffre "
     "d'affaires visé.", "90,6 %"),
    ("En année 2, soit une progression de 87,5 % par rapport à l'année 1, calculée "
     "comme (101 772 - 54 276) divisé par 54 276.", "87,5 %"),
    ("Soit 269 721 / 150 000 000 = 0,18 % du marché national estimé.", "0,18 %"),
    ("Trois boulangeries cumulent à elles seules 18,65 % du marché local "
     "(6,25 + 7,40 + 5,00).", "18,65 %"),
    ("Le marché pourrait avoisiner 172,5 M€ un an plus tard (150 x 1,15) si cette "
     "dynamique se maintient.", "172,5 M€"),
])
def test_le_resultat_d_un_calcul_pose_n_est_pas_signale(phrase: str, resultat: str) -> None:
    """LE test : ces cinq phrases du corpus étaient toutes signalées."""
    assert resultat not in _signales(phrase)


def test_un_chiffre_source_dans_sa_phrase_n_est_pas_sans_source() -> None:
    phrase = ("Chiffre d'affaires moyen par point de vente (273 000 euros HT, Crisalid "
              "2025), utilisé comme base pour les huit concurrents directs.")
    assert "273 000 euros" not in _signales(phrase)


def test_la_BASE_d_un_calcul_reste_signalee_si_le_socle_l_ignore() -> None:
    """CONTRE-ÉPREUVE : trois chiffres cohérents ne se justifient pas entre eux.

    Le résultat (800 000 €) est un calcul posé ; le marché de 1 600 M€ n'a rien
    avant lui dans la phrase : sans le socle ni une source, il reste signalé.
    """
    signales = _signales(
        "Si le projet capte 0,05 % du marché national estimé à 1 600 millions d'euros, "
        "cela représente 800 000 euros de chiffre d'affaires."
    )
    assert "800 000 euros" not in signales
    assert any(s.startswith("1 600") for s in signales), signales


@pytest.mark.parametrize(("phrase", "chiffre"), [
    ("Le marché des animaux compte 26,3 millions de chiens et chats en France.",
     "26,3 millions"),
    ("La récurrence ne pèse que 6,63 % du chiffre d'affaires récurrent global.",
     "6,63 %"),
])
def test_un_chiffre_sans_calcul_ni_source_reste_signale(phrase: str, chiffre: str) -> None:
    """CONTRE-ÉPREUVE : l'invention et le ratio sans opérandes passent toujours."""
    assert chiffre in _signales(phrase)

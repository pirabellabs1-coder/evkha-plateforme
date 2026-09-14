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
        donnees=[
            DonneeSocle(
                id="ca_actuel", libelle="Chiffre d'affaires", valeur=120000, unite="EUR",
                annee=2026, perimetre=Perimetre.NATIONAL, fiabilite=Fiabilite.DECLAREE,
            ),
            DonneeSocle(
                id="sam", libelle="Marché adressable", valeur=1600, unite="MEUR",
                annee=2026, perimetre=Perimetre.NATIONAL, fiabilite=Fiabilite.DECLAREE,
            ),
        ],
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


def test_un_resultat_tire_d_une_base_du_socle_n_est_pas_signale() -> None:
    """Le SOM d'un SAM du socle et d'un taux de capture : un calcul, légitime."""
    signales = _signales(
        "Si le projet capte 0,05 % du marché adressable de 1 600 M€, "
        "cela représente 800 000 euros de chiffre d'affaires."
    )
    assert "800 000 euros" not in signales


def test_une_BASE_inventee_ne_justifie_rien() -> None:
    """CONTRE-ÉPREUVE : trois chiffres cohérents ne se justifient pas entre eux.

    Le marché de 2 400 M€ n'est pas dans le socle : il reste signalé, et le
    montant qu'on en tire aussi — un calcul juste sur une base inventée ne
    fait pas un chiffre fondé (relecture du 14/09/2026, I5).
    """
    signales = _signales(
        "Si le projet capte 0,05 % du marché national estimé à 2 400 millions d'euros, "
        "cela représente 1 200 000 euros de chiffre d'affaires."
    )
    assert any(s.startswith("2 400") for s in signales), signales
    assert "1 200 000 euros" in signales


@pytest.mark.parametrize(("phrase", "chiffre"), [
    ("Le marché des animaux compte 26,3 millions de chiens et chats en France.",
     "26,3 millions"),
    ("La récurrence ne pèse que 6,63 % du chiffre d'affaires récurrent global.",
     "6,63 %"),
])
def test_un_chiffre_sans_calcul_ni_source_reste_signale(phrase: str, chiffre: str) -> None:
    """CONTRE-ÉPREUVE : l'invention et le ratio sans opérandes passent toujours."""
    assert chiffre in _signales(phrase)


@pytest.mark.parametrize(("phrase", "chiffre"), [
    ("En posant une dépense annuelle de l'ordre de 220 euros par habitant — "
     "hypothèse construite à partir du panier moyen —, le calcul se poursuit.",
     "220 euros"),
    ("Les deux acteurs cumulent une part de marché estimée à 10,4 %.", "10,4 %"),
    ("Le projet se fixe un objectif de 120 000 euros de chiffre d'affaires annuel.",
     "120 000 euros"),
])
def test_une_estimation_declaree_n_est_pas_un_fait_invente(phrase: str, chiffre: str) -> None:
    """La règle des sources demande de présenter ainsi une valeur sans adresse."""
    assert chiffre not in _signales(phrase)


def test_une_taille_de_marche_estimee_sans_calcul_ni_source_reste_signalee() -> None:
    """CONTRE-ÉPREUVE : le défaut exact de la stratégie Zenitek.

    « Un marché national estimé à 900 M€ », sans calcul ni source : le mot
    « estimé » ne suffit pas à justifier une taille de marché.
    """
    assert "900 M€" in _signales("Le marché national est estimé à 900 M€ en 2026.")


def test_le_controleur_ne_reecrit_plus_sur_ce_seul_motif() -> None:
    """Trop peu précis pour faire payer une réécriture (corpus, 14/09/2026)."""
    from generation.controle_final import REPARABLES_PAR_CHAPITRE

    assert "chiffres_hors_socle" not in REPARABLES_PAR_CHAPITRE
    # CONTRE-ÉPREUVE : les défauts qu'on sait juger restent réparables.
    assert {"calcul_faux", "valeur_nulle", "densite"} <= REPARABLES_PAR_CHAPITRE


# ── Relecture du 14/09/2026 (I5) : les inventions plausibles restent vues ────


@pytest.mark.parametrize(("phrase", "chiffre"), [
    # « estimé » ne justifie pas une taille de marché, quel qu'en soit le mot.
    ("Le potentiel national est estimé à 900 M€.", "900 M€"),
    ("Les dépenses des ménages français en produits bio sont estimées à 13 Md€.", "13 Md€"),
    ("Le chiffre d'affaires de la filière est estimé à 4 Md€.", "4 Md€"),
    # Un montant estimé sans sa base — le risque central de l'EC.
    ("Le CA estimé de Boulangerie Dupont est de 850 000 €.", "850 000 €"),
    # « cible » y est un nom ; « retenu » ne porte pas le chiffre.
    ("La clientèle cible dépense en moyenne 85 € par visite.", "85 €"),
    ("Nous avons retenu trois concurrents ; le leader réalise 4,5 M€ de chiffre "
     "d'affaires.", "4,5 M€"),
    # Une croissance est un fait de marché, pas une part qui se déduit.
    ("Le taux de croissance du marché est estimé à 8 % par an.", "8 %"),
    # Coïncidences : années, petits nombres sans calcul posé.
    ("Entre 2020 et 2025, le marché national est passé à 5 Md€.", "5 Md€"),
    ("Présent dans 3 villes avec 4 agences, le groupe réalise 12 M€ de chiffre "
     "d'affaires.", "12 M€"),
    ("Sur les 12 derniers mois, les 4 leaders ont capté 48 % des ventes.", "48 %"),
    # Le cercle : des pourcentages, des montants, qui se justifieraient entre eux.
    ("Le concurrent A détient 40 % du marché local, contre 25 % pour B et 15 % "
     "pour C.", "40 %"),
    ("En 2025, le marché pèse 900 M€ (600 M€ en ligne + 300 M€ en magasin).", "900 M€"),
    # « selon le canal » n'est pas une source.
    ("Le panier moyen atteint 42 € selon le canal de vente.", "42 €"),
])
def test_une_invention_plausible_reste_signalee(phrase: str, chiffre: str) -> None:
    assert chiffre in _signales(phrase), _signales(phrase)


@pytest.mark.parametrize(("phrase", "chiffre"), [
    ("45 000 € sur 120 000 €, soit 37,5 % du chiffre d'affaires.", "37,5 %"),
    ("Selon l'Insee, le panier moyen atteint 42 €.", "42 €"),
    ("Le budget de visibilité atteint un budget de 9 500 euros.", "9 500 euros"),
])
def test_un_calcul_ou_une_source_en_bonne_forme_est_justifie(phrase: str, chiffre: str) -> None:
    """CONTRE-ÉPREUVE : la forme que COHERENCE règle 4 demande, et une source nommée."""
    assert chiffre not in _signales(phrase)


def test_les_chiffres_du_brief_entrent_dans_les_derivations() -> None:
    """Le brief rangé APRÈS un socle de 80 valeurs n'entrait dans aucune dérivation."""
    grand_socle = Socle(
        secteur="x", zone=Zone(pays="France"), date_socle=date(2026, 9, 14),
        donnees=[
            DonneeSocle(
                id=f"donnee_{i}", libelle=f"Donnée {i}", valeur=100000 + 7919 * i,
                unite="EUR", annee=2026, perimetre=Perimetre.NATIONAL,
                fiabilite=Fiabilite.DECLAREE,
            )
            for i in range(90)
        ],
    )
    phrase = "Le coût mensuel de l'équipe atteint 999 €."
    document = DocumentLu(chemin=Path("corpus.docx"), paragraphes=[phrase])
    document.mesures.extend(mesures_dans(phrase))
    signales = [
        a for a in controler_chiffres_hors_socle(document, grand_socle, [333.0, 3.0])
        if a.controle == "chiffres_hors_socle"
    ]
    assert signales == [], "333 × 3 = 999 : le brief doit entrer dans les dérivations"

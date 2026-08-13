"""Un seuil de rentabilité est une division, pas une rédaction.

## Le défaut, mesuré sur un business plan réel

12/08/2026, relevé par la cliente sur un dossier qu'elle venait de relire :

    seuil_rentabilite : 27 600 € au ch. 0 ; 18 667 € au ch. 2 ; 18 667 € au
    ch. 9 ; 35 609 € au ch. 14 ; 54 276 € au ch. 15 ; 101 772 € au ch. 18 ;
    32 048 € au ch. 18 ; 18 667 € au ch. 21

Douze mentions, six valeurs. Sept disent 18 667 € : le rédacteur n'est pas
incohérent par nature — il REFAIT le calcul à chaque chapitre, sans mémoire de
l'avoir déjà fait, et il dérive. Le contrôle attrapait les écarts après coup,
les passes de correction réécrivaient les chapitres, et la facture passait de
3,50 € à 5 €.

Sa question, ce jour-là : « pourquoi ne pas mettre que de vraies choses et
logiques, vérifier avant de mettre, et garder une bonne mémoire ? »
"""
from __future__ import annotations

from datetime import date

import pytest


def _donnee(identifiant: str, valeur: float, unite: str):  # type: ignore[no-untyped-def]
    from generation.socle.schema import DonneeSocle, Fiabilite

    return DonneeSocle(
        id=identifiant, libelle=identifiant, valeur=valeur, unite=unite,
        annee=2026, perimetre="national", fiabilite=Fiabilite.ESTIMEE,
    )


def _socle(*donnees):  # type: ignore[no-untyped-def]
    from generation.socle.schema import Socle, Zone

    return Socle(
        secteur="conseil aux dirigeants", zone=Zone(pays="France"),
        date_socle=date(2026, 8, 12), donnees=list(donnees), concurrents=[],
    )


def test_un_seuil_absent_est_calcule_exactement() -> None:
    """28 000 € de charges fixes, 60 % de marge : 46 666,67 €. Pas un jeton."""
    from generation.socle.calculs import appliquer

    ajoutees, contradictions = appliquer(
        _socle(
            _donnee("charges_fixes_an1", 28_000, "EUR"),
            _donnee("marge_brute_taux", 60, "%"),
        ),
        "business_plan",
    )

    assert [d.id for d in ajoutees] == ["seuil_rentabilite"]
    assert round(ajoutees[0].valeur) == 46_667
    assert contradictions == []


def test_le_chiffre_calcule_porte_sa_formule_et_sa_filiation() -> None:
    """Ce qui le rend défendable devant un banquier qui refait l'opération.

    `derivee_de` n'est pas décoratif : la passe de vérification s'en sert pour
    distinguer un chiffre dérivé d'une hallucination.
    """
    from generation.socle.calculs import appliquer
    from generation.socle.schema import Fiabilite

    ajoutees, _ = appliquer(
        _socle(
            _donnee("charges_fixes_an1", 28_000, "EUR"),
            _donnee("marge_brute_taux", 60, "%"),
        ),
        "business_plan",
    )
    seuil = ajoutees[0]

    assert "charges fixes" in seuil.libelle and "÷" in seuil.libelle
    assert set(seuil.derivee_de) == {"charges_fixes_an1", "marge_brute_taux"}
    # ESTIMEE, jamais OBSERVEE : exact au regard de ses termes, il ne vaut que
    # ce qu'ils valent.
    assert seuil.fiabilite is Fiabilite.ESTIMEE


def test_un_seuil_qui_dement_ses_termes_est_denonce() -> None:
    """LE cas du dossier réel : 101 772 € là où la division donne 46 667 €."""
    from generation.socle.calculs import appliquer

    ajoutees, contradictions = appliquer(
        _socle(
            _donnee("charges_fixes_an1", 28_000, "EUR"),
            _donnee("marge_brute_taux", 60, "%"),
            _donnee("seuil_rentabilite", 101_772, "EUR"),
        ),
        "business_plan",
    )

    assert ajoutees == []
    assert len(contradictions) == 1
    message = str(contradictions[0])
    assert "101,772" in message and "46,667" in message


def test_un_arrondi_ne_declenche_rien() -> None:
    """CONTRE-ÉPREUVE : un contrôle qui crie sur 46 700 contre 46 667 est du bruit.

    Un plan d'affaires arrondit ses montants. Exiger l'égalité au centime
    produirait un motif que personne ne peut corriger sans dégrader la
    lisibilité — et un motif faux déclenche une réécriture payante.
    """
    from generation.socle.calculs import appliquer

    _, contradictions = appliquer(
        _socle(
            _donnee("charges_fixes_an1", 28_000, "EUR"),
            _donnee("marge_brute_taux", 60, "%"),
            _donnee("seuil_rentabilite", 46_700, "EUR"),
        ),
        "business_plan",
    )

    assert contradictions == []


def test_les_magnitudes_se_comparent(  # k€ contre €
) -> None:
    """« 46,7 k€ » et « 46 700 € » sont le même chiffre.

    Sans ramener les montants à leur unité de base, le contrôle dénoncerait
    une contradiction entre une valeur et elle-même.
    """
    from generation.socle.calculs import appliquer

    _, contradictions = appliquer(
        _socle(
            _donnee("charges_fixes_an1", 28, "kEUR"),
            _donnee("marge_brute_taux", 60, "%"),
            _donnee("seuil_rentabilite", 46.7, "kEUR"),
        ),
        "business_plan",
    )

    assert contradictions == []


def test_un_taux_de_marge_nul_ne_produit_pas_de_seuil() -> None:
    """Une division par zéro déguisée en chiffre serait pire que rien."""
    from generation.socle.calculs import appliquer

    ajoutees, contradictions = appliquer(
        _socle(
            _donnee("charges_fixes_an1", 28_000, "EUR"),
            _donnee("marge_brute_taux", 0, "%"),
        ),
        "business_plan",
    )

    assert ajoutees == [] and contradictions == []


def test_un_terme_manquant_ne_produit_rien() -> None:
    """Règle 2 : sans le taux de marge, le seuil ne se devine pas."""
    from generation.socle.calculs import appliquer

    ajoutees, _ = appliquer(
        _socle(_donnee("charges_fixes_an1", 28_000, "EUR")), "business_plan"
    )

    assert ajoutees == []


def test_le_plan_de_financement_s_equilibre() -> None:
    """Besoins = ressources : le terme qui manque se déduit des autres."""
    from generation.socle.calculs import appliquer

    ajoutees, _ = appliquer(
        _socle(
            _donnee("investissement_total", 27_600, "EUR"),
            _donnee("bfr", 4_000, "EUR"),
            _donnee("apport", 1_800, "EUR"),
            _donnee("emprunt", 20_000, "EUR"),
        ),
        "business_plan",
    )

    assert [d.id for d in ajoutees] == ["autres_ressources"]
    assert round(ajoutees[0].valeur) == 9_800  # 27 600 + 4 000 − 1 800 − 20 000


def test_un_plan_sur_finance_ne_fabrique_pas_une_ressource_negative() -> None:
    """Un excédent est une anomalie à expliquer, pas une ressource."""
    from generation.socle.calculs import appliquer

    ajoutees, _ = appliquer(
        _socle(
            _donnee("investissement_total", 10_000, "EUR"),
            _donnee("bfr", 1_000, "EUR"),
            _donnee("apport", 50_000, "EUR"),
            _donnee("emprunt", 20_000, "EUR"),
        ),
        "business_plan",
    )

    assert ajoutees == []


def test_une_identite_ne_sort_pas_de_son_livrable() -> None:
    """CONTRE-ÉPREUVE : le seuil de rentabilité est une notion du business plan.

    Le produire dans une étude de marché fabriquerait un identifiant hors
    référentiel — donc « hors socle », qu'aucun chapitre n'a le droit de citer.
    """
    from generation.socle.calculs import appliquer

    ajoutees, _ = appliquer(
        _socle(
            _donnee("charges_fixes_an1", 28_000, "EUR"),
            _donnee("marge_brute_taux", 60, "%"),
        ),
        "market_study",
    )

    assert ajoutees == []


def test_chaque_identite_produit_un_identifiant_du_referentiel() -> None:
    """Un chiffre hors référentiel serait refusé par le contrôle hors socle.

    Ce test vise la CLASSE : il échouera si quelqu'un ajoute demain une
    identité qui produit un identifiant que personne n'attend.
    """
    from generation.socle.calculs import IDENTITES
    from generation.socle.referentiel import identifiants_pour

    for identite in IDENTITES:
        for livrable in identite.livrables or ("business_plan",):
            assert identite.produit in identifiants_pour(livrable), (
                f"« {identite.produit} » n'existe pas dans le référentiel de "
                f"{livrable} : aucun chapitre ne pourrait le citer."
            )
            for terme in identite.depuis:
                assert terme in identifiants_pour(livrable), (
                    f"« {terme} » n'existe pas dans le référentiel de {livrable}."
                )


def test_la_consigne_interdit_aux_chapitres_de_recalculer() -> None:
    """La cause, pas seulement le contrôle.

    Sans cette phrase, le rédacteur refait la division à chaque chapitre —
    c'est précisément ce qui a produit six valeurs pour un seul seuil.
    """
    from generation.chapitres.runner import _CE_QUI_NE_SE_RECOPIE_PAS as consigne

    assert "TU NE RECALCULES RIEN" in consigne
    assert "ÉCRIS QU'IL MANQUE" in consigne


@pytest.mark.django_db
def test_une_contradiction_ouvre_un_incident_sans_bloquer() -> None:
    """La leçon du CHECK INITIAL : un arrêt ne laisse rien au client.

    Le socle se contredit, il faut que ça se voie — mais la génération
    continue, et c'est le gate qui tranchera sur le document.
    """
    from decimal import Decimal

    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import GenerationJob
    from generation.socle.calculs import Contradiction
    from generation.socle.services import _journaliser_les_calculs
    from monitoring.models import IncidentSeverity, OperationalIncident
    from orders.models import Order

    offre = Offer.objects.create(
        name="BP", slug="test-calculs", deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    client = Customer.objects.create(email="calculs@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-calculs", customer=client, offer=offre,
    )
    job = GenerationJob.objects.create(
        order=commande, deliverable_type=DeliverableType.BUSINESS_PLAN,
        budget_eur=Decimal("5.50"),
    )

    _journaliser_les_calculs(job, [], [Contradiction(
        identifiant="seuil_rentabilite", valeur_du_socle=101_772.0,
        valeur_calculee=46_667.0, unite="EUR", formule="charges ÷ taux",
    )])

    incident = OperationalIncident.objects.get(job=job)
    assert incident.severity == IncidentSeverity.HIGH
    assert "101,772" in incident.details["contradictions"][0]

"""La page tarifs de production affichait « Crédit supplémentaire : 0 € ».

Défaut constaté le 07/08/2026 en comparant la page publique de production à
celle du local : quatre formules sans prix de crédit supplémentaire, sans
aucune puce d'avantage, sans formule mise en avant. Le React n'y était pour
rien — l'API de production renvoyait bien `0`, `[]` et `false`.

Cause : ces colonnes sont nées après les lignes. `seed_formules` sans
`--forcer` laisse une formule existante intacte — et c'est voulu, sinon un
tarif ajusté en administration serait écrasé au déploiement suivant. Il
manquait le rattrapage des lignes créées avant les colonnes.

Ces tests tiennent les deux moitiés de la règle 6 : le rattrapage remplit ce
qui est vide (il échoue sur le code d'avant, où rien ne le faisait), et il
n'écrase RIEN de ce qui a été réglé à la main.
"""
from __future__ import annotations

import importlib

import pytest
from django.apps import apps as registre

from organisations.management.commands.seed_formules import (
    AVANTAGES_COMMUNS,
    CODE_MIS_EN_AVANT,
    FORMULES,
)
from organisations.models import Formule

# Le nom du module commence par un chiffre : `import` ne sait pas l'écrire.
module_migration = importlib.import_module(
    "organisations.migrations.0008_rattrapage_donnees_des_formules"
)

rattraper = module_migration.remplir_les_colonnes_vides


def _formule_de_production(code: str) -> Formule:
    """Une ligne telle que la production la portait : colonnes au défaut."""
    libelle = next(entree[1] for entree in FORMULES if entree[0] == code)
    return Formule.objects.create(
        code=code,
        libelle=libelle,
        credits_par_echeance=3,
        prix_mensuel_cents=18_900,
        # Les quatre colonnes du défaut, écrites explicitement : c'est l'état
        # que la production affichait, pas une supposition.
        prix_credit_supplementaire_cents=0,
        avantages=[],
        rang=0,
        mise_en_avant=False,
    )


@pytest.mark.django_db
def test_les_colonnes_vides_sont_remplies() -> None:
    """Sur le code d'avant, ces quatre valeurs restaient au défaut."""
    for code, *_ in FORMULES:
        _formule_de_production(code)

    rattraper(registre, None)

    pro = Formule.objects.get(code="pro")
    assert pro.prix_credit_supplementaire_cents == 5_500
    assert pro.mise_en_avant is True
    assert pro.rang == 2
    # Les deux lignes communes, plus rien de propre pour Pro.
    assert pro.avantages == list(AVANTAGES_COMMUNS)

    structure = Formule.objects.get(code="structure")
    assert structure.prix_credit_supplementaire_cents == 3_900
    assert structure.avantages[-2:] == [
        "Convention-cadre possible",
        "Interlocutrice dédiée",
    ]
    assert structure.mise_en_avant is False, "une seule formule mise en avant"


@pytest.mark.django_db
def test_un_tarif_regle_en_administration_survit() -> None:
    """Contre-épreuve : le rattrapage ne doit pas se comporter en `--forcer`.

    C'est exactement ce que la commande refuse de faire, et la raison pour
    laquelle la production s'est retrouvée en retard. Corriger ce retard en
    écrasant les réglages manuels remplacerait un défaut par un pire.
    """
    formule = _formule_de_production("pro")
    formule.prix_credit_supplementaire_cents = 4_900  # remise consentie
    formule.avantages = ["Accompagnement sur mesure"]
    formule.rang = 9
    formule.save()

    rattraper(registre, None)

    formule.refresh_from_db()
    assert formule.prix_credit_supplementaire_cents == 4_900
    assert formule.avantages == ["Accompagnement sur mesure"]
    assert formule.rang == 9


@pytest.mark.django_db
def test_une_mise_en_avant_deja_choisie_n_est_pas_deplacee() -> None:
    """Si l'administration met Structure en avant, Pro ne la lui reprend pas."""
    _formule_de_production("pro")
    structure = _formule_de_production("structure")
    structure.mise_en_avant = True
    structure.save()

    rattraper(registre, None)

    assert Formule.objects.get(code="structure").mise_en_avant is True
    assert Formule.objects.get(code="pro").mise_en_avant is False


@pytest.mark.django_db
def test_le_rattrapage_est_rejouable() -> None:
    """Un déploiement qui rejoue la migration ne doit rien casser."""
    _formule_de_production("solo")

    rattraper(registre, None)
    rattraper(registre, None)

    solo = Formule.objects.get(code="solo")
    assert solo.prix_credit_supplementaire_cents == 5_900
    assert solo.avantages == list(AVANTAGES_COMMUNS)


@pytest.mark.django_db
def test_une_base_sans_formule_ne_fait_pas_tomber_la_migration() -> None:
    """Une base neuve migre avant d'être amorcée : il n'y a rien à rattraper."""
    assert not Formule.objects.exists()

    rattraper(registre, None)  # ne doit pas lever

    assert not Formule.objects.exists()


def test_la_migration_et_la_commande_disent_la_meme_chose() -> None:
    """Règle 5 : une seule table de tarifs.

    La migration importe les constantes de `seed_formules` plutôt que d'en
    recopier les valeurs. Ce test verrouille cette lecture : s'il devenait
    possible de changer un tarif d'un côté sans l'autre, les deux finiraient
    par se contredire.
    """
    source = module_migration.remplir_les_colonnes_vides.__code__
    noms = set(source.co_names)
    for constante in ("FORMULES", "AVANTAGES_COMMUNS", "CODE_MIS_EN_AVANT"):
        assert constante in noms, f"{constante} n'est pas lue depuis la commande"
    assert CODE_MIS_EN_AVANT == "pro"

"""La marque refuse EN CLAIR ce que la base refuserait — jamais en erreur 500.

Le 29/09/2026, la cliente préparait un business plan et remplaçait la marque
de son organisation par celle de son client (logo, raison sociale, couleurs).
Le logo est passé ; l'enregistrement de la marque, lui, a répondu « Erreur
500 » trois fois de suite (journaux : `POST /api/espace/marque/ 500`), sans
un mot sur le champ en cause.

La vue écrivait chaque valeur telle quelle. PostgreSQL, en production, refuse
une valeur plus longue que sa colonne — `varchar(7)` pour une couleur ; SQLite,
en local et en test, l'accepte sans rien dire. Une couleur copiée depuis un
outil de design porte parfois un caractère invisible (espace de largeur
nulle) : « #3D568A » y fait huit caractères.

Ce fichier verrouille la CLASSE (règle 4) :
1. chaque champ texte de la marque est jugé à la longueur que le MODÈLE impose
   (lue sur `Organisation._meta`, pas recopiée) — trop long : 400 qui nomme le
   champ, rien d'écrit ;
2. les caractères invisibles sont retirés, une couleur sans dièse est
   complétée ; une couleur que le rendu ignorerait est refusée à la saisie ;
3. contre-épreuve (règle 6) : les vraies valeurs de la cliente passent.

Sous SQLite, sans la validation, chaque cas « trop long » répondait 200 : ces
tests échouent sur le code d'avant.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.db.models import Field
from django.test import Client

from organisations.models import Organisation
from organisations.vues_espace import CHAMPS_COULEUR, CHAMPS_MARQUE, LIBELLES_MARQUE
from tests.test_lot4_espace_client import Agence, charge

URL = "/api/espace/marque/"

#: Les champs texte dont la longueur est bornée par la base (hors couleurs,
#: jugées sur leur format, et hors logo, déposé par sa propre route).
CHAMPS_TEXTE = [
    c for c in CHAMPS_MARQUE
    if c not in CHAMPS_COULEUR and c != "logo_url"
]


@pytest.fixture
def agence() -> Agence:
    return Agence("ENGLISH-4U International S.A.", "marque@exemple.fr")


def _longueur_max(champ: str) -> int:
    """La longueur que la base impose, lue sur le modèle (jamais recopiée)."""
    champ_modele = Organisation._meta.get_field(champ)
    assert isinstance(champ_modele, Field)
    longueur_max = champ_modele.max_length
    assert longueur_max, f"{champ} n'a pas de longueur maximale : ce test ne juge rien"
    return longueur_max


def _enregistrer(agence: Agence, charge_json: dict[str, Any]) -> Any:
    return Client().post(
        URL,
        data=json.dumps(charge_json),
        content_type="application/json",
        headers=agence.entetes,
    )


@pytest.mark.django_db
def test_les_vraies_valeurs_de_la_cliente_passent(agence: Agence) -> None:
    """Contre-épreuve : ce que la cliente a saisi le 29/09/2026."""
    valeurs = {
        "raison_sociale": "ECLORE",
        "secteur": "Conception et organisation d'événements",
        "pays": "France",
        "ville": "",
        "mention_confidentialite": "",
        "couleur_principale": "#3D568A",
        "couleur_secondaire": "#D7193F",
        "couleur_fond": "#E6E1EA",
    }
    reponse = _enregistrer(agence, valeurs)
    assert reponse.status_code == 200, reponse.content
    relu = charge(Client().get(URL, headers=agence.entetes))
    for champ, valeur in valeurs.items():
        assert relu[champ] == valeur, champ


@pytest.mark.django_db
@pytest.mark.parametrize("champ", CHAMPS_TEXTE)
def test_un_texte_trop_long_est_refuse_en_nommant_le_champ(agence: Agence, champ: str) -> None:
    longueur_max = _longueur_max(champ)
    avant = getattr(agence.organisation, champ)

    reponse = _enregistrer(agence, {champ: "x" * (longueur_max + 1)})

    assert reponse.status_code == 400, f"{champ} : {reponse.status_code}"
    corps = charge(reponse)
    assert corps["code"] == "trop_long"
    assert LIBELLES_MARQUE[champ] in corps["error"]
    assert str(longueur_max) in corps["error"]
    agence.organisation.refresh_from_db()
    assert getattr(agence.organisation, champ) == avant


@pytest.mark.django_db
@pytest.mark.parametrize("champ", CHAMPS_TEXTE)
def test_un_texte_a_la_longueur_exacte_passe(agence: Agence, champ: str) -> None:
    """Contre-épreuve : la borne est inclusive."""
    longueur_max = _longueur_max(champ)
    reponse = _enregistrer(agence, {champ: "x" * longueur_max})
    assert reponse.status_code == 200, f"{champ} : {reponse.content!r}"


@pytest.mark.django_db
def test_une_couleur_collee_avec_un_caractere_invisible_est_nettoyee(agence: Agence) -> None:
    invisible = "\u200b"  # espace de largeur nulle, copiée avec la couleur
    reponse = _enregistrer(agence, {
        "couleur_principale": f"#3D568A{invisible}",
        "couleur_secondaire": f"{invisible}#D7193F",
    })
    assert reponse.status_code == 200, reponse.content
    agence.organisation.refresh_from_db()
    assert agence.organisation.couleur_principale == "#3D568A"
    assert agence.organisation.couleur_secondaire == "#D7193F"


@pytest.mark.django_db
def test_une_couleur_sans_diese_est_completee(agence: Agence) -> None:
    reponse = _enregistrer(agence, {"couleur_fond": "e6e1ea"})
    assert reponse.status_code == 200, reponse.content
    agence.organisation.refresh_from_db()
    assert agence.organisation.couleur_fond == "#E6E1EA"


@pytest.mark.django_db
@pytest.mark.parametrize("valeur", ["rgb(61, 86, 138)", "#3D56", "bleu marine", "#3D568AFF"])
def test_une_couleur_que_le_rendu_ignorerait_est_refusee(agence: Agence, valeur: str) -> None:
    reponse = _enregistrer(agence, {"couleur_principale": valeur})
    assert reponse.status_code == 400
    corps = charge(reponse)
    assert corps["code"] == "couleur_invalide"
    assert "Couleur principale" in corps["error"]
    assert "#RRGGBB" in corps["error"]


@pytest.mark.django_db
def test_une_couleur_vide_reste_permise(agence: Agence) -> None:
    """La couleur de fond est facultative : dérivée de la principale si vide."""
    reponse = _enregistrer(agence, {"couleur_fond": ""})
    assert reponse.status_code == 200
    agence.organisation.refresh_from_db()
    assert agence.organisation.couleur_fond == ""

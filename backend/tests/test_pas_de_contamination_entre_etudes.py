"""Le sujet d'une autre étude ne doit jamais entrer dans celle du client.

## Le cas réel, signalé par la cliente

Le 09/08/2026, une étude sur **l'e-commerce pour animaux** portait en page 52 :

    FOCUS — APPROFONDISSEMENT DEMANDÉ : MARCHÉ INTERNATIONAL DES GALERIES
    ET DU SUR-MESURE

Aucun rapport avec le sujet. Le modèle n'a rien inventé : le modèle de FORME a
été mesuré sur une étude de **joaillerie** (`references/joalie_2026.docx`), et
le plan du chapitre lui remettait cette étiquette **telle quelle**, sans lui
dire de la réécrire.

L'intitulé de sous-section, lui, portait déjà sa consigne d'adaptation
(« Adapter l'intitulé à la niche en gardant le même angle d'analyse »). Ni
l'étiquette d'encadré ni les en-têtes de tableau ne l'avaient. L'oubli n'était
pas une règle manquante : c'était la même règle appliquée à un seul cas
(règle 4).

## La troisième fuite de la même famille en deux jours

  - les exemples de tableaux HTML hérités du moteur précédent ;
  - la notation `[pourcentage]` ajoutée pour aider le modèle à choisir ses
    figures ;
  - et ces intitulés.

**Tout ce qu'on montre au modèle pour l'aider peut ressortir dans le document,
et doit donc arriver avec la façon de s'en servir.** C'est la leçon, et elle
vaut pour la prochaine aide qu'on ajoutera.

## Pourquoi le refus est rédhibitoire

Les écarts de RESSEMBLANCE sont consultatifs depuis le 08/08/2026 : ils
mesurent une distance au gabarit, et la cliente a tranché que le modèle entraîne
sans imposer. Celui-ci est d'une autre nature — ce n'est pas une forme qui
s'écarte, c'est le sujet d'une autre étude qui entre. Toléré sur la dernière
tentative, il part chez le client.
"""
from __future__ import annotations

from typing import Any

import pytest

from generation.modele.conformite import (
    REGLES_REDHIBITOIRES,
    _controler_contamination,
    _intitules_du_modele,
)
from generation.modele.consigne import ADAPTER_AU_SECTEUR, plan_du_chapitre

ETIQUETTE_JOAILLERIE = (
    "FOCUS — Approfondissement demandé : marché international des galeries "
    "et du sur-mesure"
)

MODELE = {
    "blocs": [
        {"type": "encadre", "etiquette": ETIQUETTE_JOAILLERIE},
        {
            "type": "titre_sous_section",
            "intitule_reference": "Deux périmètres à ne pas confondre",
        },
        {"type": "encadre", "etiquette": "Synthèse"},
    ]
}


class _Encadre:
    def __init__(self, intitule: str) -> None:
        self.intitule = intitule


class _BlocEncadre:
    def __init__(self, intitule: str) -> None:
        self.encadre = _Encadre(intitule)


class _Payload:
    def __init__(self, *intitules: str) -> None:
        self.blocs = [_BlocEncadre(i) for i in intitules]


def test_l_etiquette_de_joaillerie_recopiee_est_refusee() -> None:
    """Le cas exact de la page 52."""
    ecarts = _controler_contamination(_Payload(ETIQUETTE_JOAILLERIE), MODELE)

    assert len(ecarts) == 1
    assert ecarts[0].regle == "contamination_du_modele"
    assert "galeries" in ecarts[0].detail


def test_la_casse_et_les_espaces_ne_sauvent_pas() -> None:
    """Le document imprime l'étiquette en capitales — c'est le même texte."""
    ecarts = _controler_contamination(
        _Payload(f"  {ETIQUETTE_JOAILLERIE.upper()}  "), MODELE
    )

    assert ecarts


def test_le_refus_est_redhibitoire() -> None:
    """Toléré sur la dernière tentative, il partirait chez le client."""
    assert "contamination_du_modele" in REGLES_REDHIBITOIRES


def test_une_etiquette_reecrite_pour_le_secteur_passe() -> None:
    """Ce qu'on ATTEND du modèle ne doit pas être puni."""
    ecarts = _controler_contamination(
        _Payload("FOCUS — Approfondissement demandé : marché de l'alimentation animale"),
        MODELE,
    )

    assert ecarts == []


@pytest.mark.parametrize(
    "intitule",
    ["Synthèse", "À retenir", "Verdict", "Ce qu'il faut retenir", "Lecture du chapitre"],
)
def test_les_mots_de_methode_courts_ne_sont_pas_condamnes(intitule: str) -> None:
    """LA contre-épreuve.

    « Synthèse » se retrouve légitimement dans deux études — c'est un mot de
    méthode, pas un sujet. Les condamner ferait rejouer un chapitre pour un
    intitulé parfaitement juste, et la reprise coûte un appel.
    """
    assert _controler_contamination(_Payload(intitule), MODELE) == []


def test_seuls_les_intitules_assez_longs_sont_compares() -> None:
    """En dessous du seuil, une reprise peut être une coïncidence."""
    intitules = _intitules_du_modele(MODELE)

    assert ETIQUETTE_JOAILLERIE in intitules
    assert "Synthèse" not in intitules


def test_un_chapitre_sans_intitule_de_reference_ne_declenche_rien() -> None:
    assert _controler_contamination(_Payload("Un intitulé quelconque"), {"blocs": []}) == []


def test_le_plan_dit_desormais_d_adapter_les_etiquettes(db: Any) -> None:
    """La CAUSE, pas seulement le garde-fou.

    Sans cette phrase, chaque chapitre porteur d'un encadré paierait une reprise
    pour un défaut qu'on lui a soi-même montré. Le garde-fou ne doit pas devenir
    la façon normale de fonctionner.
    """
    plan = plan_du_chapitre(20)

    assert plan, "le chapitre 20 doit exister au modèle"
    assert ADAPTER_AU_SECTEUR in plan
    assert "AUTRE secteur" in plan

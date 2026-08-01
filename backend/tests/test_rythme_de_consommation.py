"""« Ma formule tient-elle ? » — la question, et le droit de ne pas y répondre.

Un abonné ne lit pas un journal de mouvements pour savoir s'il consomme trop.
Il veut une date. Mais une date fausse est bien pire qu'une absence de date :
elle se croit, et elle décide d'un renouvellement.

Les deux façons de la fausser sont ici des tests à part entière :

- diviser la consommation par douze mois quand le compte en a deux ;
- inclure le mois en cours, forcément partiel, dans la moyenne.

Les deux produisent un chiffre plausible et trop optimiste. C'est exactement le
défaut des règles 1 et 2 : un contrôle qui répond quand même.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from organisations import credits, inscription
from organisations.models import TypeMouvement

pytestmark = pytest.mark.django_db

EMAIL = "claire@cabinet-duval.fr"
MOT_DE_PASSE = "un-mot-de-passe-solide-42"


@pytest.fixture
def espace(client: Client) -> Any:
    """Une organisation réelle et un client authentifié sur son espace."""
    ouverture = inscription.ouvrir_compte(
        raison_sociale="Cabinet Duval",
        email=EMAIL,
        mot_de_passe=MOT_DE_PASSE,
        activer_abonnement=False,
    )
    from organisations import authentification

    jeton, _ = authentification.ouvrir_session(EMAIL, MOT_DE_PASSE)

    class Espace:
        organisation = ouverture.organisation

        @staticmethod
        def rythme() -> Any:
            reponse = client.get(
                "/api/espace/consommation/", HTTP_AUTHORIZATION=f"Bearer {jeton}"
            )
            assert reponse.status_code == 200, reponse.content
            return reponse.json()["rythme"]

    return Espace


def _mouvement_le(organisation: Any, quantite: int, *, il_y_a_mois: int, reference: str) -> None:
    """Passe un mouvement puis le rétrodate.

    Le mouvement est créé par le vrai chemin (`crediter`/`debiter`) : écrire
    directement dans la table produirait des lignes que le produit ne fabrique
    jamais — des débits positifs, par exemple — et le test verrouillerait alors
    un comportement qui n'existe pas.
    """
    if quantite > 0:
        credits.crediter(
            organisation, quantite, motif="Dotation", reference=reference,
            type_mouvement=TypeMouvement.DOTATION,
        )
    else:
        credits.debiter(organisation, -quantite, reference=reference, motif="Étude")

    quand = timezone.localtime() - timedelta(days=int(30.44 * il_y_a_mois))
    credits.portefeuille_de(organisation).mouvements.filter(
        reference=reference
    ).update(created_at=quand)


# ── Le piège de la division par douze ────────────────────────────────────────


def test_la_moyenne_ne_porte_que_sur_les_mois_ecoules(espace: Any) -> None:
    """Le test qui échoue si l'on divise par la fenêtre au lieu de l'ancienneté.

    Compte ouvert il y a deux mois, 6 crédits consommés : le rythme est de 3
    par mois, pas de 0,5. L'écart n'est pas cosmétique — il multiplie par six
    l'autonomie annoncée.
    """
    _mouvement_le(espace.organisation, 40, il_y_a_mois=2, reference="dotation")
    _mouvement_le(espace.organisation, -3, il_y_a_mois=2, reference="job-1")
    _mouvement_le(espace.organisation, -3, il_y_a_mois=1, reference="job-2")

    rythme = espace.rythme()
    assert rythme["mois_observes"] == 2, "la moyenne porte sur la mauvaise duree"
    assert rythme["mensuel"] == 3.0


def test_le_mois_en_cours_est_exclu_de_la_moyenne(espace: Any) -> None:
    """Le 3 du mois, la consommation partielle promettrait une fausse autonomie."""
    _mouvement_le(espace.organisation, 40, il_y_a_mois=2, reference="dotation")
    _mouvement_le(espace.organisation, -4, il_y_a_mois=2, reference="job-1")
    _mouvement_le(espace.organisation, -4, il_y_a_mois=1, reference="job-2")
    # Ce mois-ci, un seul débit pour l'instant : il ne doit pas peser.
    credits.debiter(espace.organisation, 1, reference="job-3", motif="Étude")

    rythme = espace.rythme()
    assert rythme["mensuel"] == 4.0, "le mois partiel a tire la moyenne vers le bas"


# ── Le droit de ne pas répondre ──────────────────────────────────────────────


def test_un_compte_ouvert_ce_mois_ci_n_annonce_aucune_date(espace: Any) -> None:
    """Extrapoler quelques jours sur une année serait une invention."""
    credits.crediter(
        espace.organisation, 10, motif="Dotation", reference="d",
        type_mouvement=TypeMouvement.DOTATION,
    )
    credits.debiter(espace.organisation, 2, reference="job-1", motif="Étude")

    rythme = espace.rythme()
    assert rythme["epuisement_le"] is None
    assert rythme["motif"] == "pas_assez_d_historique"


def test_un_compte_sans_mouvement_le_dit(espace: Any) -> None:
    rythme = espace.rythme()
    assert rythme["motif"] == "aucun_mouvement"
    assert rythme["jours_restants"] is None


def test_un_compte_qui_ne_consomme_pas_n_a_pas_de_date_d_epuisement(
    espace: Any,
) -> None:
    """Diviser par zéro, ou annoncer « jamais », seraient tous deux faux.

    Le motif dit la vérité : il n'y a pas encore de consommation à projeter.
    """
    _mouvement_le(espace.organisation, 30, il_y_a_mois=3, reference="dotation")

    rythme = espace.rythme()
    assert rythme["motif"] == "aucune_consommation"
    assert rythme["epuisement_le"] is None
    assert rythme["mois_observes"] >= 1


# ── La date, quand elle est légitime ─────────────────────────────────────────


def test_la_date_d_epuisement_suit_le_solde_et_le_rythme(espace: Any) -> None:
    """Contre-épreuve : quand on peut répondre, on répond, et juste."""
    _mouvement_le(espace.organisation, 24, il_y_a_mois=3, reference="dotation")
    for rang, recul in enumerate((3, 2, 1), start=1):
        _mouvement_le(espace.organisation, -4, il_y_a_mois=recul, reference=f"job-{rang}")

    rythme = espace.rythme()
    assert rythme["mensuel"] == 4.0
    assert rythme["solde"] == 12
    # Douze crédits à quatre par mois : trois mois, soit ~91 jours.
    assert 85 <= rythme["jours_restants"] <= 97, rythme
    assert rythme["epuisement_le"] is not None


def test_un_remboursement_ne_compte_pas_comme_une_consommation(
    espace: Any,
) -> None:
    """Il rend des crédits ; l'inscrire en sortie accuserait le client.

    Ce mouvement est stocké POSITIF tout en figurant dans les sorties — le
    genre d'exception de signe qui inverse un graphique sans prévenir.
    """
    _mouvement_le(espace.organisation, 30, il_y_a_mois=2, reference="dotation")
    _mouvement_le(espace.organisation, -6, il_y_a_mois=2, reference="job-1")
    _mouvement_le(espace.organisation, -6, il_y_a_mois=1, reference="job-2")
    sans_remboursement = espace.rythme()["mensuel"]

    credits.rembourser(espace.organisation, reference="job-2", motif="Échec")
    quand = timezone.localtime() - timedelta(days=int(30.44))
    credits.portefeuille_de(espace.organisation).mouvements.filter(
        type=TypeMouvement.REMBOURSEMENT
    ).update(created_at=quand)

    apres = espace.rythme()["mensuel"]
    assert apres < sans_remboursement, "le remboursement a ete compte comme une sortie"

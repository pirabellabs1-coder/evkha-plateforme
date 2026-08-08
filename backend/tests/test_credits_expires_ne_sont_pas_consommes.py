"""Un credit expire n'a pas ete consomme : il a ete PERDU.

Defaut mesure le 06/08/2026 sur un compte reel, signale par la cliente :

    CREDITS DISPONIBLES  10
    DOCUMENTS PRODUITS   22
    Sur douze mois : 50 recus, 40 consommes

Quarante « consommes » en face de vingt-deux documents. L'arithmetique du solde
etait juste — 50 - 40 = 10 — mais le mot etait faux : `consommes` additionnait
les DEBITS et les EXPIRATIONS, tous deux membres de `credits.SORTIES` et tous
deux negatifs au journal.

## Pourquoi ce n'est pas qu'une question de vocabulaire

`_rythme` somme cette meme colonne pour projeter une date d'epuisement. Le
compte ci-dessus s'est vu annoncer « 23 credits / mois » et « epuisement le
19 aout » alors qu'il consomme bien moins : l'alarme reposait sur des credits
qu'il n'avait PAS utilises.

Le piege s'inverse, ce qui le rend particulierement retors : **moins on
consomme, plus il expire, donc plus la projection annonce une consommation
forte**. Un client econome recevait l'alerte la plus pressante.

## Ce qui n'a pas ete cache

Le total des expirations est desormais rendu separement, pas supprime. C'est le
vrai argument d'un changement de formule, et le taire reviendrait a masquer au
client ce qu'il perd (regle 1).

## Pourquoi aucun test ne l'avait vu

`test_consommation_mensuelle` couvre les entrees, les sorties, le remboursement
et la fenetre de douze mois — mais **aucun de ses cas ne cree d'expiration**.
Le comportement fautif n'etait pas verrouille : il etait invisible.
"""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from customers.models import Customer
from organisations import credits, services
from organisations.authentification import creer_compte, ouvrir_session
from organisations.models import MouvementCredit, TypeMouvement

pytestmark = pytest.mark.django_db

MOT_DE_PASSE = "mot-de-passe-de-test-2026"


class Compte:
    def __init__(self, email: str = "abonne@exemple.fr"):
        self.contact = Customer.objects.create(email=email, first_name="Test")
        self.organisation = services.creer_organisation(
            raison_sociale="Atelier Test", contact=self.contact
        )
        creer_compte(self.contact, mot_de_passe=MOT_DE_PASSE)
        self.jeton, _ = ouvrir_session(email, MOT_DE_PASSE)

    @property
    def entetes(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.jeton}"}

    def mouvement(self, quantite: int, type_: str, *, il_y_a_mois: int = 0) -> None:
        """Ecrit directement au journal : on teste la LECTURE, pas l'ecriture."""
        portefeuille = credits.portefeuille_de(self.organisation)
        ligne = MouvementCredit.objects.create(
            portefeuille=portefeuille,
            quantite=quantite,
            type=type_,
            reference=f"{type_}-{MouvementCredit.objects.count()}",
            motif="Test",
        )
        if il_y_a_mois:
            quand = timezone.now() - timedelta(days=31 * il_y_a_mois)
            MouvementCredit.objects.filter(pk=ligne.pk).update(created_at=quand)

    def consommation(self) -> dict[str, Any]:
        reponse = Client().get("/api/espace/consommation/", headers=self.entetes)
        assert reponse.status_code == 200
        charge: dict[str, Any] = json.loads(reponse.content)
        return charge


def test_une_expiration_ne_compte_pas_comme_une_consommation() -> None:
    """LE test de ce fichier. Sur le code d'avant, `total_consomme` valait 12."""
    compte = Compte()
    compte.mouvement(10, TypeMouvement.DOTATION)
    compte.mouvement(-3, TypeMouvement.DEBIT)
    compte.mouvement(-9, TypeMouvement.EXPIRATION)

    charge = compte.consommation()

    assert charge["total_consomme"] == 3
    assert charge["total_expire"] == 9


def test_les_expirations_restent_visibles_mois_par_mois() -> None:
    """On separe, on ne cache pas : c'est ce que le client perd.

    Le taire reviendrait a lui masquer le meilleur argument pour changer de
    formule (regle 1).
    """
    compte = Compte()
    compte.mouvement(10, TypeMouvement.DOTATION)
    compte.mouvement(-7, TypeMouvement.EXPIRATION)

    charge = compte.consommation()
    mois_courant = charge["mois"][-1]

    assert mois_courant["expires"] == 7
    assert mois_courant["consommes"] == 0
    assert mois_courant["recus"] == 10


def test_le_rythme_ignore_les_credits_expires() -> None:
    """Le piege qui s'inverse : moins on consomme, plus il expire.

    Sur le code d'avant, ce compte — qui consomme UN credit par mois — se
    voyait annoncer un rythme de neuf, et une date d'epuisement imminente.
    """
    compte = Compte()
    for mois in (2, 1):
        compte.mouvement(10, TypeMouvement.DOTATION, il_y_a_mois=mois)
        compte.mouvement(-1, TypeMouvement.DEBIT, il_y_a_mois=mois)
        compte.mouvement(-8, TypeMouvement.EXPIRATION, il_y_a_mois=mois)

    rythme = compte.consommation()["rythme"]

    # Un credit par mois revolu, pas neuf.
    assert rythme["mensuel"] == pytest.approx(1.0, abs=0.35)


def test_un_remboursement_reduit_toujours_la_consommation() -> None:
    """CONTRE-EPREUVE : on n'a pas casse le traitement du remboursement.

    Il est POSITIF au journal tout en figurant dans les SORTIES — il rend un
    credit, donc il reduit la consommation nette. Le separer de l'expiration ne
    devait pas le deplacer.
    """
    compte = Compte()
    compte.mouvement(10, TypeMouvement.DOTATION)
    compte.mouvement(-4, TypeMouvement.DEBIT)
    compte.mouvement(2, TypeMouvement.REMBOURSEMENT)

    charge = compte.consommation()

    assert charge["total_consomme"] == 2
    assert charge["total_expire"] == 0


def test_le_solde_reste_la_somme_du_journal() -> None:
    """CONTRE-EPREUVE : separer l'affichage ne touche pas a la comptabilite.

    Le solde reste une simple somme du journal, expirations comprises. C'est le
    MOT qui etait faux, pas le compte.
    """
    compte = Compte()
    compte.mouvement(10, TypeMouvement.DOTATION)
    compte.mouvement(-3, TypeMouvement.DEBIT)
    compte.mouvement(-2, TypeMouvement.EXPIRATION)

    assert credits.solde(compte.organisation) == 5


def test_sans_aucune_expiration_le_total_est_zero_et_non_absent() -> None:
    """« Rien de perdu » n'est pas la meme chose que ne rien dire (regle 1)."""
    compte = Compte()
    compte.mouvement(10, TypeMouvement.DOTATION)
    compte.mouvement(-3, TypeMouvement.DEBIT)

    charge = compte.consommation()

    assert charge["total_expire"] == 0
    assert all("expires" in ligne for ligne in charge["mois"])

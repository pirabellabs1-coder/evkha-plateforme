"""Rendre une organisation de test aussi legitime qu'une vraie.

## Pourquoi ce module existe

Le 06/08/2026, l'espace client a cesse d'etre ouvert a qui n'a rien paye
(`vues_espace.acces_ouvert`). Quatre-vingt-dix tests sont tombes d'un coup.

Ils avaient raison sur un point et tort sur l'autre. Raison : mon premier
critere — « un abonnement ACTIF » — enfermait dehors un resilie qui a encore
des credits achetes, et une organisation dotee a la main depuis
l'administration. Le critere a ete corrige.

Tort sur le reste : leurs organisations n'ont NI abonnement, NI le moindre
mouvement de credit, et exercent pourtant l'espace d'un client. Cet etat
n'existe plus en production. Une doublure qui decrit un etat impossible ne
verifie plus rien de ce que le client vivra (regle 7).

## Pourquoi sans doter

`abonner(organisation)` cree un abonnement ACTIF **et ne verse aucun credit**.
C'est deliberement l'inverse du defaut de `services.souscrire`.

Doter aurait reecrit les soldes sous les pieds d'une vingtaine de tests dont
c'est precisement le sujet : « une commande sans credit est refusee », « le
catalogue signale ce que le solde ne couvre pas ». Ils seraient passes au vert
en cessant de tester quoi que ce soit — le pire resultat possible.

Ce que l'aide accorde est donc exactement le droit d'entrer, et rien d'autre.
"""
from __future__ import annotations

from organisations import services
from organisations.models import Formule, Organisation

#: Formule des doublures. Un code a soi, qui ne peut pas entrer en collision
#: avec les quatre formules reelles semees par `seed_formules` — plusieurs
#: tests les creent, et deux `get_or_create` sur le meme code se marcheraient
#: dessus.
CODE_FORMULE_DE_TEST = "formule-de-doublure"


def formule_de_test() -> Formule:
    """La formule des doublures, creee au premier appel."""
    formule, _ = Formule.objects.get_or_create(
        code=CODE_FORMULE_DE_TEST,
        defaults={
            "libelle": "Formule de doublure",
            # Non nul : une formule a zero credit est un cas particulier reel,
            # mais en faire le defaut des tests ferait passer pour normal ce qui
            # ne l'est pas.
            "credits_par_echeance": 3,
            "prix_mensuel_cents": 18_900,
            "active": True,
        },
    )
    return formule


def abonner(organisation: Organisation, formule: Formule | None = None) -> None:
    """Ouvre l'espace a cette organisation, SANS lui verser de credit.

    A appeler juste apres `services.creer_organisation` dans une fabrique de
    test. Le solde reste a zero : un test qui veut des credits les demande
    explicitement, comme avant.
    """
    services.souscrire(
        organisation, formule or formule_de_test(), doter_immediatement=False
    )

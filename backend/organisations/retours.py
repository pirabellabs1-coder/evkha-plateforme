"""Ce qu'une page de retour de paiement vérifie AVANT de parler au prestataire.

Trois pages reçoivent l'acheteur qui revient de Stripe — l'étude à l'unité
(`vues_publiques.retour_de_paiement`), la boutique (`vues_boutique.retour`) et
les formations (`vues_formations.retour`). Elles sont publiques par nécessité,
et toutes trois lisent un identifiant de session dans le corps de la requête
pour le RELIRE chez le prestataire, avec notre clé.

## Le défaut, trouvé à l'audit de sécurité du 20/11/2026

N'importe quelle chaîne partait chez Stripe, autant de fois qu'on voulait :

- ce qui n'a pas la forme d'une session était présenté quand même, puis
  écrit tel quel dans les journaux — saut de ligne compris ;
- rien ne comptait les appels. Un script pouvait faire relire des
  identifiants au hasard, sans limite, sur notre quota et avec notre clé.

## La règle

Une seule fonction, `session_presentee`, pour les trois pages (règle 5) :

1. le plafond par adresse est INTERROGÉ puis COMPTÉ à chaque appel, qu'il
   aboutisse ou non — un plafond lu sans être compté ne s'atteint jamais, et
   ce sont justement les appels qui échouent qu'il faut compter ;
2. le corps est lu ;
3. l'identifiant doit avoir la forme d'une session Checkout.

Ce qu'elle rend est donc le seul identifiant que la vue a le droit de
présenter au prestataire, et d'écrire dans un journal.
"""
from __future__ import annotations

import json
import re

from django.http import HttpRequest

from . import limitation

#: La forme d'un identifiant de session Checkout : le préfixe de
#: l'environnement, puis des lettres et des chiffres. Les identifiants réels
#: en comptent une soixantaine ; la borne haute laisse de la marge sans
#: laisser passer un roman. Appliquée par `fullmatch` : `$` tolérerait un
#: saut de ligne final. 150 et non plus : la référence entière est stockée
#: dans `Encaissement.reference_facture`, qui tient 160 signes — une forme
#: admise ici doit pouvoir s'y écrire sous PostgreSQL.
FORME_D_UNE_SESSION = re.compile(r"cs_(test|live)_[A-Za-z0-9]{10,150}")

#: Retours de paiement par adresse IP et par heure, les TROIS pages réunies :
#: un plafond par page se contournerait en changeant de page. Un acheteur
#: revient une fois, recharge deux ou trois fois ; trente couvre aussi
#: plusieurs personnes derrière la même connexion.
RETOURS_PAR_HEURE = limitation.Plafond("retour-de-paiement", maximum=30, fenetre_s=3600)


class Refus(Exception):
    """Le retour est refusé avant tout appel au prestataire.

    Porte ce que chaque vue rend avec sa propre fonction `_refus` : un
    message pour le visiteur, un code pour l'interface, un statut.
    """

    def __init__(self, message: str, code: str, statut: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.statut = statut


def a_la_forme_d_une_session(identifiant: object) -> bool:
    return isinstance(identifiant, str) and bool(
        FORME_D_UNE_SESSION.fullmatch(identifiant)
    )


def session_presentee(request: HttpRequest) -> str:
    """L'identifiant de session que cette requête présente, ou `Refus`.

    Ne rend qu'un identifiant qui a la forme d'une session : l'appelant peut
    le relire chez le prestataire et le journaliser. Les codes de refus sont
    ceux que les trois vues employaient déjà — `corps_invalide`,
    `session_absente` — plus `trop_de_tentatives` (429).
    """
    adresse_ip = limitation.adresse_client(request)
    if limitation.depasse(RETOURS_PAR_HEURE, adresse_ip):
        raise Refus(
            "Trop de vérifications de paiement depuis cette connexion. Si vous "
            "venez de payer, votre achat n'est pas perdu : votre accès vous est "
            "aussi envoyé par courriel. Sinon, réessayez dans une heure, ou "
            "écrivez-nous à contact@evkha.fr.",
            "trop_de_tentatives",
            429,
        )
    # Compté ICI, avant de savoir si l'appel aboutira : c'est tout l'objet.
    limitation.enregistrer(RETOURS_PAR_HEURE, adresse_ip)

    try:
        charge = json.loads(request.body or b"{}")
    # `ValueError` couvre `JSONDecodeError` et `UnicodeDecodeError` ;
    # `RecursionError` vient d'un corps imbriqué à l'excès. Deux des trois
    # vues n'attrapaient que la première, et rendaient sinon une erreur 500.
    except (ValueError, RecursionError):
        raise Refus("Requête illisible.", "corps_invalide") from None
    if not isinstance(charge, dict):
        raise Refus("Requête illisible.", "corps_invalide")

    brut = charge.get("session")
    identifiant = brut.strip() if isinstance(brut, str) else ""
    if not a_la_forme_d_une_session(identifiant):
        # Le même code qu'une session absente : pour le visiteur, c'est la
        # même chose — son adresse de retour ne désigne aucun paiement.
        raise Refus("Paiement introuvable.", "session_absente")
    return identifiant

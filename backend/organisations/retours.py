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
from typing import Any

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


def refus_si_non_encaisse(session: dict[str, Any]) -> Refus | None:
    """Ce qu'on dit à quelqu'un dont la session n'est PAS encaissée, ou rien.

    ## Le défaut, laissé ouvert par l'audit du 20/11/2026

    Les trois pages passaient toute session à leur livraison, qui refuse ce
    qui n'est pas payé — et elles traduisaient ce refus par « votre paiement
    a bien été reçu, mais votre accès n'a pas pu être ouvert ». Deux
    situations ordinaires recevaient donc une phrase fausse :

    - un prélèvement ou un virement, que la banque confirme des jours plus
      tard : la session est terminée, rien n'est encore encaissé, et rien
      n'est cassé — le webhook livrera à la confirmation
      (`checkout.session.async_payment_succeeded`) ;
    - une session jamais terminée, ou expirée : rien n'a été payé du tout.

    ## La règle

    La page de retour ne dit « reçu » que de ce que le prestataire dit payé.
    Tout autre état inattendu continue vers la livraison, qui le refuse et
    le journalise : on ne devine pas (règle 1).

    Le statut reste 409, celui que ces pages rendaient déjà : seuls le
    message et le code changent.
    """
    if str(session.get("payment_status") or "") != "unpaid":
        return None
    if str(session.get("status") or "") == "complete":
        if _refuse_par_la_banque(str(session.get("id") or "")):
            return Refus(
                "Votre banque a refusé ce paiement : il n'a pas abouti, et rien "
                "ne vous a été livré. Vous pouvez reprendre votre achat avec un "
                "autre moyen de paiement ; pour toute question, écrivez-nous à "
                "contact@evkha.fr.",
                "paiement_refuse",
                409,
            )
        return Refus(
            "Votre paiement est enregistré, et votre banque doit encore le "
            "confirmer : pour un prélèvement, cela prend quelques jours. Vous "
            "n'avez rien à refaire. Votre accès vous sera envoyé par courriel "
            "dès la confirmation ; sans nouvelles sous une semaine, "
            "écrivez-nous à contact@evkha.fr.",
            "paiement_en_attente",
            409,
        )
    return Refus(
        "Ce paiement n'est pas allé au bout : rien ne vous a été livré. Vous "
        "pouvez reprendre votre achat ; si vous pensez avoir été débité, "
        "écrivez-nous à contact@evkha.fr.",
        "paiement_non_abouti",
        409,
    )


def _refuse_par_la_banque(reference: str) -> bool:
    """Le prestataire a-t-il annoncé l'échec de ce paiement différé ?

    Une session dont le prélèvement est rejeté reste « terminée, non payée »
    pour toujours : sans cette lecture, l'acheteur lirait indéfiniment « votre
    banque doit encore le confirmer ». L'échec est noté sur le panier par le
    webhook (`abonnements.sur_paiement_differe_refuse`).

    Ne lève jamais : dans le doute, on dit « en attente », qui invite à écrire.
    """
    from .models import EtatTentative, TentativePaiement  # noqa: PLC0415

    if not reference:
        return False
    try:
        return TentativePaiement.objects.filter(
            reference_session=reference, etat=EtatTentative.ABANDONNEE
        ).exists()
    except Exception:  # noqa: BLE001
        return False


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
    # Compté ICI, avant de savoir si l'appel aboutira : c'est tout l'objet. Et
    # compté et jugé d'un seul geste (`limitation.compter`) : lu puis compté,
    # le plafond laissait passer une salve de requêtes parties ensemble.
    if not limitation.compter(RETOURS_PAR_HEURE, adresse_ip):
        raise Refus(
            "Trop de vérifications de paiement depuis cette connexion. Si vous "
            "venez de payer, votre achat n'est pas perdu : votre accès vous est "
            "aussi envoyé par courriel. Sinon, réessayez dans une heure, ou "
            "écrivez-nous à contact@evkha.fr.",
            "trop_de_tentatives",
            429,
        )

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

"""Plafonds de tentatives, et lecture fiable de l'adresse d'origine.

Ce module existe pour deux raisons, toutes deux constatées sur ce dépôt.

**1. Le compteur était écrit dans la vue.** L'inscription publique portait son
propre plafond, en clair, au milieu de la logique métier. Au moment d'en poser
un second sur la connexion, on se retrouvait à recopier la même mécanique — et
donc à entretenir deux compteurs qui finissent par ne plus dire la même chose
(règle 5). Il y a désormais une primitive, et les vues déclarent un plafond.

**2. L'adresse d'origine était falsifiable.** `X-Forwarded-For` était lu par sa
valeur **la plus à gauche**. Or cette partie de l'en-tête est écrite par le
client : il suffisait d'envoyer `X-Forwarded-For: 1.2.3.4` — puis `1.2.3.5`, et
ainsi de suite — pour obtenir une clé neuve à chaque requête et ne jamais
atteindre aucun plafond.

Un plafond posé sur une identité que l'appelant choisit lui-même n'est pas une
protection : c'est la règle 1, un contrôle qui n'a rien à comparer et qui
répond quand même « tout va bien ».

**Comment l'en-tête se lit réellement.** Chaque relais ajoute à *droite*
l'adresse depuis laquelle il a reçu la connexion :

    X-Forwarded-For: <ce que le client a écrit>, <client vu par relais 1>,
                     <relais 1 vu par relais 2>

Avec un seul relais de confiance devant nous — c'est le cas ici, Traefik sous
Coolify — la vraie adresse est donc la **dernière** entrée. Tout ce qui est à
sa gauche est déclaratif et ne vaut rien. D'où `PROXIES_DE_CONFIANCE` : on
compte les relais, et on lit à cette distance de la fin.

En développement, sans relais devant, la valeur est `0` et l'en-tête est
ignoré purement et simplement : `REMOTE_ADDR` est alors la seule vérité.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest

_log = logging.getLogger(__name__)


#: Nombre de relais de confiance placés devant l'application.
#:
#: Réglable par `EVKHA_PROXIES_DE_CONFIANCE`. La valeur par défaut est 1 :
#: l'application tourne derrière Traefik. Poser 0 en développement, ou lorsque
#: le serveur est joint directement — sinon l'en-tête serait cru sur parole.
def proxies_de_confiance() -> int:
    valeur = getattr(settings, "EVKHA_PROXIES_DE_CONFIANCE", 1)
    try:
        return max(0, int(valeur))
    except (TypeError, ValueError):
        return 1


def adresse_client(request: HttpRequest) -> str:
    """Adresse d'origine, lue de façon qu'elle ne puisse pas être choisie.

    Renvoie `REMOTE_ADDR` dès qu'il y a le moindre doute : mieux vaut un
    plafond trop large — plusieurs visiteurs partageant une clé — qu'un plafond
    qu'on contourne en écrivant un en-tête.
    """
    relais = proxies_de_confiance()
    if relais == 0:
        return str(request.META.get("REMOTE_ADDR", "") or "inconnue")

    brut = str(request.META.get("HTTP_X_FORWARDED_FOR", "") or "")
    entrees = [part.strip() for part in brut.split(",") if part.strip()]

    # Moins d'entrées que de relais annoncés : la topologie ne correspond pas à
    # ce qui est configuré. On ne devine pas, on retombe sur REMOTE_ADDR.
    if len(entrees) < relais:
        return str(request.META.get("REMOTE_ADDR", "") or "inconnue")

    return entrees[-relais]


@dataclass(frozen=True)
class Plafond:
    """Un nombre d'évènements toléré sur une fenêtre glissante.

    `nom` sert de préfixe de clé : deux plafonds distincts ne se comptent
    jamais ensemble, même appliqués à la même adresse.
    """

    nom: str
    maximum: int
    fenetre_s: int

    def cle(self, identifiant: str) -> str:
        return f"plafond:{self.nom}:{identifiant}"


def depasse(plafond: Plafond, identifiant: str) -> bool:
    """Le plafond est-il atteint pour cet identifiant ?

    **Un cache indisponible répond « non ».** C'est un arbitrage, et il est
    délibéré : ces plafonds protègent d'un abus, ils ne sont pas la condition
    du service. Une panne de Redis ne doit pas empêcher les abonnés de se
    connecter ni les prospects de créer un compte — elle fait tomber la
    protection, ce qui se voit et se répare, au lieu de fermer la plateforme.

    C'est l'inverse de l'arbitrage retenu pour la garde d'administration, où
    l'absence de secret REFUSE : là-bas il n'y a rien à protéger d'autre que
    l'accès lui-même, et personne n'est bloqué en dehors de l'équipe.

    **Cet arbitrage était écrit ici et pas implémenté.** `cache.get` lève quand
    le serveur ne répond pas, et rien ne l'attrapait : une coupure de Redis
    renvoyait une erreur 500 sur la connexion ET sur l'inscription, c'est-à-dire
    fermait la plateforme à tout le monde — exactement l'inverse de ce que ce
    paragraphe promettait. Le défaut ne s'est vu qu'au moment où le cache est
    devenu un vrai service réseau ; avec un dictionnaire en mémoire, il ne
    pouvait pas se produire (règle 1).
    """
    try:
        compte = cache.get(plafond.cle(identifiant))
    except Exception:  # noqa: BLE001 — cache injoignable : voir l'arbitrage ci-dessus
        _log.warning(
            "Cache injoignable : le plafond %r n'est pas applique.", plafond.nom
        )
        return False

    if compte is None:
        return False
    try:
        return int(compte) >= plafond.maximum
    except (TypeError, ValueError):
        return False


def enregistrer(plafond: Plafond, identifiant: str) -> None:
    """Compte un évènement de plus.

    `add` puis `incr` plutôt que `get`+`set` : deux requêtes simultanées
    liraient la même valeur et n'en écriraient qu'une, ce qui laisse passer
    plus de tentatives que le plafond n'en tolère — précisément l'attaque que
    le plafond est censé arrêter.
    """
    cle = plafond.cle(identifiant)
    try:
        if cache.add(cle, 1, plafond.fenetre_s):
            return
        cache.incr(cle)
    except ValueError:
        # La clé a expiré entre `add` et `incr`. La fenêtre repart, ce qui est
        # le comportement voulu.
        cache.set(cle, 1, plafond.fenetre_s)
    except Exception:
        # Cache indisponible : voir l'arbitrage documenté dans `depasse`.
        return


def oublier(plafond: Plafond, identifiant: str) -> None:
    """Efface le compteur — à appeler après un succès.

    Sans cela, quelqu'un qui se trompe plusieurs fois puis finit par entrer se
    verrait refuser la connexion suivante alors qu'il vient de prouver qu'il
    est bien le titulaire du compte.

    Même arbitrage que `depasse` : un cache injoignable ne doit pas faire
    échouer une connexion qui vient de RÉUSSIR.
    """
    try:
        cache.delete(plafond.cle(identifiant))
    except Exception:  # noqa: BLE001 — voir l'arbitrage de `depasse`
        _log.warning("Cache injoignable : compteur %r non efface.", plafond.nom)

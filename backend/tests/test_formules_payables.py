"""Une formule proposée mais non achetable doit se voir AVANT le client.

`seed_formules` crée quatre formules actives sans `reference_paiement`, et ne
peut pas faire autrement : les identifiants de tarif appartiennent au compte
Stripe de la cliente et n'ont rien à faire dans le dépôt. Sur une base
fraîchement amorcée, les quatre sont donc affichées, et aucune n'est achetable.

Rien n'est cassé — `stripe_api` lève avec un motif lisible et l'espace client
répond 503. Le défaut est que ça n'échoue **que devant le client**. Le contrôle
le dit à chaque démarrage.

Le piège que ces tests tiennent surtout : les contrôles système tournent AVANT
`migrate`. Un contrôle qui interroge la base sans précaution ferait échouer le
tout premier déploiement, sur une base où la table n'existe pas encore. C'est
la classe de défaut qui a occupé toute cette journée.
"""
from __future__ import annotations

from typing import Any

import pytest
from django.db import DatabaseError

from organisations.checks import controler_formules_payables
from organisations.models import Formule, ReportCredits


def _formule(code: str, *, reference: str = "", active: bool = True) -> Formule:
    return Formule.objects.create(
        code=code,
        libelle=code.capitalize(),
        credits_par_echeance=2,
        prix_mensuel_cents=12_900,
        devise="EUR",
        report_credits=ReportCredits.AUCUN,
        reference_paiement=reference,
        active=active,
    )


@pytest.mark.django_db
def test_une_formule_active_sans_tarif_est_signalee() -> None:
    """Le cas d'une base fraîchement amorcée par `seed_formules`."""
    _formule("solo")

    problemes = controler_formules_payables(None)

    assert len(problemes) == 1
    assert problemes[0].id == "evkha.W005"
    assert "Solo" in problemes[0].msg


@pytest.mark.django_db
def test_le_signalement_nomme_toutes_les_formules_concernees() -> None:
    """Nommer, et pas seulement compter.

    « 3 formules sans tarif » oblige à aller chercher lesquelles. Le motif doit
    être trouvable par le lecteur sans enquête (règle 2).
    """
    _formule("solo")
    _formule("pro")
    _formule("structure", reference="price_123")

    problemes = controler_formules_payables(None)

    assert "Solo" in problemes[0].msg
    assert "Pro" in problemes[0].msg
    assert "Structure" not in problemes[0].msg


@pytest.mark.django_db
def test_une_formule_inactive_ne_declenche_rien() -> None:
    """Elle n'est proposée à personne : il n'y a pas de bouton à échouer.

    La contre-épreuve du contrôle (règle 6) : il ne doit pas réclamer un tarif
    pour ce qui n'est pas vendu, sinon on apprend à ignorer ses messages.
    """
    _formule("ancienne", active=False)

    assert controler_formules_payables(None) == []


@pytest.mark.django_db
def test_toutes_les_formules_tarifees_ne_declenchent_rien() -> None:
    """L'état visé : le contrôle se tait quand tout est en place."""
    _formule("solo", reference="price_solo")
    _formule("pro", reference="price_pro")

    assert controler_formules_payables(None) == []


def test_sans_table_le_controle_se_tait(monkeypatch: pytest.MonkeyPatch) -> None:
    """LE défaut à éviter : faire échouer le tout premier déploiement.

    Les contrôles système tournent AVANT `migrate`. Sur une base neuve, la
    table `organisations_formule` n'existe pas. Lever ici arrêterait `migrate`,
    donc la chaîne `&&` du démarrage, donc gunicorn — et la plateforme ne
    serait jamais montée une première fois.

    Se taire est ici la bonne réponse, et c'est l'exception qui confirme la
    règle 1 : il n'y a pas « zéro formule à signaler », il n'y a **rien à
    juger**. On ne masque aucune information, il n'y en a aucune.

    Pas de `django_db` : ce test ne doit toucher aucune base.
    """
    def _explose(*_a: Any, **_k: Any) -> Any:
        raise DatabaseError('relation "organisations_formule" does not exist')

    monkeypatch.setattr(Formule.objects, "filter", _explose)

    assert controler_formules_payables(None) == []

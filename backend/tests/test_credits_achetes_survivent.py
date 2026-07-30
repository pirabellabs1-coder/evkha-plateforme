"""Les crédits ACHETÉS survivent à la bascule du mois. Ceux de l'abonnement, non.

Défaut d'origine, trouvé en relisant `expirer_solde` :

    disponible = portefeuille.solde        # ← LE SOLDE ENTIER
    a_purger = disponible - max(plafond_conserve, 0)

L'expiration purgeait tout, sans regarder d'où venaient les crédits. Un client
qui achetait des crédits additionnels les perdait donc à l'échéance suivante,
exactement comme ceux de son abonnement. Il avait payé et son solde
s'évaporait — un défaut d'argent, pas d'affichage.

Ces tests verrouillent la règle **et son revers** : l'expiration doit continuer
de faire son travail sur la réserve d'abonnement. Un correctif qui protège les
crédits achetés en cessant d'expirer quoi que ce soit serait une régression
silencieuse dans l'autre sens (règle 6, la contre-épreuve).
"""
from __future__ import annotations

import pytest

from customers.models import Customer
from organisations import credits, services
from organisations.models import (
    Formule,
    Organisation,
    ReportCredits,
    TypeMouvement,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def organisation() -> Organisation:
    contact = Customer.objects.create(email="tresorerie@exemple.fr")
    return services.creer_organisation(raison_sociale="Trésorerie", contact=contact)


def _formule(credits_mois: int = 3, report: str = ReportCredits.AUCUN) -> Formule:
    return Formule.objects.create(
        code=f"f{credits_mois}{report}",
        libelle="Test",
        credits_par_echeance=credits_mois,
        prix_mensuel_cents=10_000,
        devise="EUR",
        report_credits=report,
        plafond_report=0,
        regenerations_offertes=1,
        active=True,
    )


# ── La partition doit rester exhaustive ──────────────────────────────────────


def test_chaque_nature_de_mouvement_est_classee_exactement_une_fois() -> None:
    """Le garde-fou de structure. Sans lui, le défaut revient sous une autre forme.

    En écrivant ce correctif, `GESTE` s'est retrouvé dans aucune des deux
    réserves : il comptait dans le total sans compter nulle part, et
    l'arithmétique de répartition devenait fausse **sans qu'aucun test ne le
    dise** — deux tests du lot 4 sont tombés, mais par accident.

    Ce test-ci le dirait. Un nouveau `TypeMouvement` ajouté au modèle sans être
    classé le fait échouer, ce qui force la décision au lieu de la laisser
    arriver par défaut (règle 4 : viser la classe, pas l'instance).
    """
    classees = list(credits.ENTREES) + list(credits.SORTIES)
    toutes = [t.value for t in TypeMouvement]

    assert sorted(classees) == sorted(toutes), (
        "Une nature de mouvement n'est ni une entrée ni une sortie : "
        f"{sorted(set(toutes) - set(classees))}"
    )
    assert len(classees) == len(set(classees)), "une nature est classée deux fois"

    # Et les pérennes sont bien un sous-ensemble des entrées.
    assert set(credits.ENTREES_PERENNES) <= set(credits.ENTREES)
    assert set(credits.ENTREES_PERENNES).isdisjoint(credits.ENTREES_EXPIRABLES)
    assert set(credits.ENTREES_PERENNES) | set(credits.ENTREES_EXPIRABLES) == set(
        credits.ENTREES
    )


# ── Le défaut corrigé ────────────────────────────────────────────────────────


def test_les_credits_achetes_survivent_a_l_expiration(
    organisation: Organisation,
) -> None:
    """LE test du défaut. Il échoue sur le code d'avant, qui purgeait tout."""
    credits.doter(organisation, 3, periode="2026-07")
    credits.crediter(
        organisation,
        5,
        motif="Achat de 5 crédits",
        type_mouvement=TypeMouvement.ACHAT,
    )
    assert credits.solde(organisation) == 8

    credits.expirer_solde(organisation, periode="2026-07")

    # Les 3 de l'abonnement partent, les 5 achetés restent.
    assert credits.solde(organisation) == 5
    detail = credits.detail_solde(organisation)
    assert detail.expirables == 0
    assert detail.perennes == 5


def test_un_geste_commercial_expire_encore_et_c_est_une_question_ouverte(
    organisation: Organisation,
) -> None:
    """Comportement d'origine conservé, et documenté ici plutôt que tu.

    Un geste commercial accordé à la main par l'administration disparaît à la
    bascule du mois. C'est discutable — un geste qui s'évapore n'est pas un
    geste — mais l'inclure dans les entrées pérennes est une décision
    commerciale, et elle n'a pas été prise. Ce test existe pour que le jour où
    elle le sera, le changement soit visible et non accidentel.
    """
    credits.doter(organisation, 2, periode="2026-07")
    credits.crediter(
        organisation,
        1,
        motif="Excuses pour un livrable en retard",
        type_mouvement=TypeMouvement.GESTE,
    )

    credits.expirer_solde(organisation, periode="2026-07")

    assert credits.solde(organisation) == 0


# ── La contre-épreuve : l'expiration fait toujours son travail ───────────────


def test_l_expiration_purge_bien_la_reserve_d_abonnement(
    organisation: Organisation,
) -> None:
    """Sans achat, le comportement d'origine est inchangé : tout part."""
    credits.doter(organisation, 4, periode="2026-07")
    credits.expirer_solde(organisation, periode="2026-07")
    assert credits.solde(organisation) == 0


def test_le_report_plafonne_s_applique_a_la_reserve_d_abonnement(
    organisation: Organisation,
) -> None:
    """Le plafond conserve des crédits d'abonnement, sans toucher aux achetés."""
    credits.doter(organisation, 6, periode="2026-07")
    credits.crediter(
        organisation, 2, motif="Achat", type_mouvement=TypeMouvement.ACHAT
    )

    credits.expirer_solde(organisation, periode="2026-07", plafond_conserve=2)

    # 2 d'abonnement conservés + 2 achetés = 4
    assert credits.solde(organisation) == 4
    detail = credits.detail_solde(organisation)
    assert detail.expirables == 2
    assert detail.perennes == 2


def test_rien_a_purger_n_ecrit_aucun_mouvement(organisation: Organisation) -> None:
    """Un journal ne doit pas se remplir de lignes à zéro."""
    credits.crediter(
        organisation, 3, motif="Achat", type_mouvement=TypeMouvement.ACHAT
    )
    assert credits.expirer_solde(organisation, periode="2026-07") is None
    assert credits.solde(organisation) == 3


# ── La règle d'imputation ────────────────────────────────────────────────────


def test_la_consommation_entame_d_abord_la_reserve_d_abonnement(
    organisation: Organisation,
) -> None:
    """C'est le choix favorable au client : il garde ce qu'il a payé.

    Si les débits mordaient d'abord sur les crédits achetés, le correctif
    ci-dessus ne protégerait rien : les achetés seraient déjà consommés au
    moment de l'expiration.
    """
    credits.doter(organisation, 3, periode="2026-07")
    credits.crediter(
        organisation, 4, motif="Achat", type_mouvement=TypeMouvement.ACHAT
    )
    credits.debiter(organisation, 2, reference="job-1", motif="Étude de marché")

    detail = credits.detail_solde(organisation)
    assert detail.expirables == 1, "les débits doivent entamer l'abonnement d'abord"
    assert detail.perennes == 4, "les crédits achetés ne doivent pas être entamés"


def test_au_dela_de_la_reserve_d_abonnement_la_consommation_mord_sur_les_achetes(
    organisation: Organisation,
) -> None:
    """Contre-épreuve : l'imputation ne protège pas les achetés indéfiniment."""
    credits.doter(organisation, 1, periode="2026-07")
    credits.crediter(
        organisation, 3, motif="Achat", type_mouvement=TypeMouvement.ACHAT
    )
    credits.debiter(organisation, 3, reference="job-2", motif="Business plan")

    detail = credits.detail_solde(organisation)
    assert detail.expirables == 0
    assert detail.perennes == 1
    assert credits.solde(organisation) == 1


def test_la_repartition_egale_toujours_le_journal(organisation: Organisation) -> None:
    """L'invariant. Il interdit qu'une répartition invente ou perde un crédit.

    Comparé à l'agrégat brut du journal, pas à une seconde addition écrite ici
    — sinon on mesurerait son propre calcul (règle 2).
    """
    credits.doter(organisation, 5, periode="2026-07")
    credits.crediter(
        organisation, 4, motif="Achat", type_mouvement=TypeMouvement.ACHAT
    )
    credits.debiter(organisation, 3, reference="job-3", motif="Étude")
    credits.rembourser(organisation, reference="job-3", motif="Échec définitif")
    credits.expirer_solde(organisation, periode="2026-07")
    credits.doter(organisation, 5, periode="2026-08")

    detail = credits.detail_solde(organisation)
    assert detail.expirables >= 0
    assert detail.perennes >= 0
    assert detail.expirables + detail.perennes == detail.total
    # La propriété du modèle est l'autre définition historique du solde : les
    # deux doivent coïncider, sinon l'espace client et l'administration
    # afficheraient deux chiffres différents.
    assert detail.total == credits.portefeuille_de(organisation).solde


# ── Le cycle mensuel complet ─────────────────────────────────────────────────


def test_deux_echeances_reinitialisent_l_abonnement_et_cumulent_les_achats(
    organisation: Organisation,
) -> None:
    """Ce que la cliente décrit : l'abonnement repart à zéro, les achats cumulent."""
    formule = _formule(credits_mois=3)
    abonnement = services.souscrire(organisation, formule)
    assert credits.solde(organisation) == 3

    credits.crediter(
        organisation, 2, motif="Achat de 2 crédits", type_mouvement=TypeMouvement.ACHAT
    )
    assert credits.solde(organisation) == 5

    # Mois suivant : la dotation se réinitialise, les achats restent.
    services.appliquer_echeance(abonnement, periode="2026-08")

    detail = credits.detail_solde(organisation)
    assert detail.expirables == 3, "la réserve d'abonnement est repartie à 3"
    assert detail.perennes == 2, "les 2 crédits achetés sont toujours là"
    assert credits.solde(organisation) == 5

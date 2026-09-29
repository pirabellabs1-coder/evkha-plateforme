"""Le gate juge le résultat net 2029 contre le résultat net 2029 — pas contre la CAF.

29/09/2026, business plan `cb59cede` (ÉCLORE). Trois trous du contrôle de
cohérence chiffrée (`gate._mention_est_conforme`), vus sur le même dossier :

1. **La fourchette fusionnée.** Le fait client `resultat_net_previsionnel`
   portait le résultat net ET la CAF (défaut de l'extracteur, corrigé à part).
   Sans année reconnue, une trajectoire acceptait tout ce qui tombait dans
   [min ; max] : 23 223,86 € et 23 835,86 € (la CAF) passaient tous les deux.
2. **L'année civile.** « Résultat net 2029 : 23 835,86 € » n'était pas même lu :
   aucun motif n'admettait une année entre le libellé et le montant, et
   `_YEAR_IN_MENTION_RE` ne connaissait que « an N / année N ».
3. **L'arrondi.** « résultat net de 49,96 € » contre « 50 € » au brief : même
   montant, signalé six fois, trois chapitres renvoyés en réécriture pour rien.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

# Seules les fonctions qui existaient AVANT le correctif sont importées ici :
# rejoués contre l'ancien code, les tests de comportement doivent tomber sur
# leur assertion, pas sur un import (règle 6).
from generation.gate import _check_numeric_coherence, _mention_est_conforme
from generation.rendering import RenderedSection

#: Le compte de résultat de la cliente, collé sur une ligne, en-tête compris.
TABLEAU_APLATI = (
    "Compte de résultat prévisionnel 2027 2028 2029 2030 2031 "
    "Chiffre d'affaires 19 674 € 54 276 € 90 000 € 90 000 € 90 000 € "
    "EBE 782 € 8 772 € 23 956 € 23 956 € 23 956 € "
    "Dotations aux amortissements 612 € 612 € 612 € 612 € 612 € "
    "Résultat net comptable 50 € 8 040 € 23 224 € 23 224 € 23 224 € "
    "Capacité d'autofinancement 662 € 8 652 € 23 836 € 23 836 € 23 836 €"
)

#: Le même tableau, sans l'en-tête des années : le premier exercice est inconnu.
TABLEAU_SANS_ANNEES = TABLEAU_APLATI.replace("2027 2028 2029 2030 2031 ", "")


def _job(tableau: str, ref: str) -> Any:
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.coherence import seed_locked_facts_from_variables
    from generation.models import GenerationJob
    from intake.models import IntakeStatus, IntakeSubmission
    from orders.models import Order

    variables: dict[str, object] = {
        "SECTEUR": "fleuristerie", "PAYS": "France", "ZONE": "Lyon",
        "PROJET": "ÉCLORE", "TABLEAUX_FINANCIERS": tableau,
    }
    offer = Offer.objects.create(
        name="BP", slug=f"bp-{ref}", deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    customer = Customer.objects.create(email=f"{ref}@example.com")
    order = Order.objects.create(systeme_order_id=ref, customer=customer, offer=offer)
    IntakeSubmission.objects.create(
        order=order, status=IntakeStatus.NORMALIZED, normalized_variables=variables,
    )
    job = GenerationJob.objects.create(
        order=order, deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    seed_locked_facts_from_variables(job, variables)
    return job


def _motifs_resultat_net(job: Any, texte: str) -> list[str]:
    section = RenderedSection(number=16, title="Prévisionnel", kind="chapter", body=texte)
    return [
        f.detail
        for f in _check_numeric_coherence(job, (section,))
        if f.detail.startswith("resultat_net_previsionnel")
    ]


# ── Le dossier ÉCLORE, de bout en bout ──────────────────────────────────────


@pytest.mark.django_db
def test_la_caf_imprimee_pour_le_resultat_net_2029_est_refusee() -> None:
    """AVANT : « Résultat net 2029 : … » n'était pas lu — aucun motif."""
    job = _job(TABLEAU_APLATI, "eclore_caf_2029")

    assert _motifs_resultat_net(job, "Résultat net 2029 : 23 835,86 €.")


@pytest.mark.django_db
def test_la_caf_sans_annee_est_refusee() -> None:
    """AVANT : 23 835,86 € tombait dans la fourchette fusionnée [50 ; 23 836]."""
    job = _job(TABLEAU_APLATI, "eclore_caf_sans_annee")

    assert _motifs_resultat_net(job, "Le résultat net atteint 23 835,86 €.")


@pytest.mark.django_db
def test_le_resultat_net_2029_au_centime_est_conforme() -> None:
    """Contre-épreuve : 23 223,86 € est le 23 224 € du brief, au centime près."""
    job = _job(TABLEAU_APLATI, "eclore_rn_2029")

    assert _motifs_resultat_net(job, "Résultat net 2029 : 23 223,86 €.") == []
    assert _motifs_resultat_net(job, "Le résultat net atteint 23 223,86 € en 2029.") == []


@pytest.mark.django_db
def test_un_arrondi_n_est_pas_une_incoherence() -> None:
    """AVANT : « 49,96 € » contre « 50 € » — six motifs sur le dossier réel."""
    job = _job(TABLEAU_APLATI, "eclore_arrondi")

    assert _motifs_resultat_net(job, "Un résultat net de 49,96 € la première année.") == []


@pytest.mark.django_db
def test_l_annee_civile_range_la_mention_a_son_exercice() -> None:
    """2028 est l'exercice 2 d'un plan qui part en 2027 : 8 040 €, pas 12 000 €.

    AVANT : non lu. Et sans année, 12 000 € passait comme valeur intermédiaire.
    """
    job = _job(TABLEAU_APLATI, "eclore_2028")

    assert _motifs_resultat_net(job, "Résultat net 2028 : 12 000 €.")
    assert _motifs_resultat_net(job, "Résultat net 2028 : 8 040 €.") == []


@pytest.mark.django_db
def test_citer_une_autre_annee_du_brief_n_exempte_pas() -> None:
    """« (contre 8 040 € en 2028) » ne couvre pas un résultat 2029 faux.

    La phrase qui cite un chiffre du brief était exemptée comme « scénario ».
    Quand l'année est connue, seule la valeur de CETTE année compare.
    """
    job = _job(TABLEAU_APLATI, "eclore_scenario")

    assert _motifs_resultat_net(
        job, "Résultat net 2029 : 23 835,86 € (contre 8 040 € en 2028)."
    )
    # Contre-épreuve : comparer à la valeur de la même année reste un scénario.
    assert _motifs_resultat_net(
        job, "Résultat net 2029 : 20 000 € dans le scénario prudent, contre 23 224 € au plan."
    ) == []


@pytest.mark.django_db
def test_sans_annee_la_valeur_d_une_autre_serie_est_refusee() -> None:
    """8 772 € est l'EBE 2028 : dans [50 ; 23 224], mais pas un résultat net.

    AVANT : acceptée au seul motif qu'elle tombait dans la fourchette.
    """
    job = _job(TABLEAU_APLATI, "eclore_ebe")

    assert _motifs_resultat_net(job, "Le résultat net atteint 8 772 €.")


@pytest.mark.django_db
def test_sans_premier_exercice_connu_l_annee_civile_ne_juge_rien() -> None:
    """Contre-épreuve : sans en-tête d'années ni socle, 2028 ne se range pas.

    On ne devine pas le décalage : la mention est jugée comme avant, en
    fourchette, et une valeur intermédiaire plausible passe.
    """
    job = _job(TABLEAU_SANS_ANNEES, "eclore_sans_annees")

    assert _motifs_resultat_net(job, "Résultat net 2028 : 12 000 €.") == []
    assert _motifs_resultat_net(job, "Résultat net 2029 : 23 835,86 €.")


# ── Revue du 29/09/2026 : ce que le premier correctif refusait à tort ───────
#
# La consigne du prévisionnel (`prompts/business_plan/chapitre_16.md`) exige
# une lecture de sensibilité : « résultat net et CAF si le CA est inférieur de
# 10 % ». Le gate la prenait pour un résultat 2029 faux.


@pytest.mark.django_db
@pytest.mark.parametrize(
    "texte",
    [
        pytest.param(
            "Avec un chiffre d'affaires inférieur de 10 %, le résultat net de "
            "15 900 € en 2029 reste positif.",
            id="ca-inferieur-de-10",
        ),
        pytest.param(
            "Sensibilité (CA −10 %) : résultat net 2029 : 15 900 €.",
            id="sensibilite",
        ),
        pytest.param(
            "Le résultat net de 15 000 € en moyenne sur 2027-2031 finance le "
            "remboursement.",
            id="moyenne-sur-une-plage",
        ),
    ],
)
def test_une_variante_ou_une_moyenne_n_est_pas_accusee(texte: str) -> None:
    job = _job(TABLEAU_APLATI, "eclore_variante")

    assert _motifs_resultat_net(job, texte) == []


@pytest.mark.django_db
def test_une_variante_n_exempte_pas_la_valeur_centrale() -> None:
    """Contre-épreuve : la CAF imprimée pour le résultat net 2029 reste refusée."""
    job = _job(TABLEAU_APLATI, "eclore_centrale")

    assert _motifs_resultat_net(job, "Résultat net 2029 : 23 835,86 €.")


@pytest.mark.django_db
def test_une_perte_de_premiere_annee_n_est_pas_accusee() -> None:
    """AVANT : le brief se verrouillait sans son signe, « 3 000 € »."""
    job = _job(
        "Prévisionnel 2027 2028 2029 — Résultat net : -3 000 € en 2027, "
        "8 000 € en 2028, 15 000 € en 2029",
        "perte_an1",
    )

    assert _motifs_resultat_net(job, "Résultat net 2027 : -3 000 €.") == []
    # Contre-épreuve : un bénéfice de 3 000 € n'est pas la perte du brief.
    assert _motifs_resultat_net(job, "Résultat net 2027 : 3 000 €.")


# ── La règle, fonction pure ─────────────────────────────────────────────────

ATTENDU = [50.0, 8_040.0, 23_224.0, 23_224.0, 23_224.0]


def _conforme(found: float, mention: str, **options: Any) -> bool:
    return _mention_est_conforme(
        found=found, mention=mention, expected=ATTENDU, is_trajectory=True,
        lo=min(ATTENDU), hi=max(ATTENDU), **options,
    )


@pytest.mark.parametrize(
    ("found", "mention", "attendu"),
    [
        pytest.param(49.96, "résultat net d'année 1 :", True, id="49,96-pour-50"),
        pytest.param(50.49, "résultat net d'année 1 :", True, id="50,49-pour-50"),
        pytest.param(23_223.86, "résultat net d'année 3 :", True, id="23223,86-pour-23224"),
        pytest.param(23_835.86, "résultat net d'année 3 :", False, id="la-caf-pas-un-arrondi"),
        pytest.param(51.0, "résultat net d'année 1 :", False, id="une-unite-d-ecart"),
    ],
)
def test_l_arrondi_a_l_unite(found: float, mention: str, attendu: bool) -> None:
    """AVANT : égalité stricte — 49,96 € contre 50 € était une incohérence."""
    assert _conforme(found, mention) is attendu


def test_l_annee_civile_se_range_a_son_exercice() -> None:
    assert _conforme(23_223.86, "résultat net 2029 :", premiere_annee=2027)
    assert not _conforme(23_835.86, "résultat net 2029 :", premiere_annee=2027)
    assert not _conforme(12_000.0, "résultat net 2028 :", premiere_annee=2027)


def test_l_annee_2031_est_le_cinquieme_exercice() -> None:
    """Le plateau 23 224 € ×3 garde ses trois années : 2031 existe."""
    assert _conforme(23_224.0, "résultat net 2031 :", premiere_annee=2027)
    assert not _conforme(23_835.86, "résultat net 2031 :", premiere_annee=2027)


def test_l_annee_apres_le_montant_compte_aussi() -> None:
    assert not _conforme(12_000.0, "résultat net de", suite=" en 2028", premiere_annee=2027)
    assert _conforme(8_040.0, "résultat net de", suite=" en 2028", premiere_annee=2027)


def test_une_annee_hors_du_previsionnel_n_accuse_pas() -> None:
    """Un historique (2024) avant un plan qui part en 2027 : non jugeable."""
    assert _conforme(12_000.0, "résultat net 2024 :", premiere_annee=2027)


def test_premiere_annee_de_l_en_tete_du_tableau() -> None:
    from generation.gate import _premiere_annee_du_brief

    assert _premiere_annee_du_brief(TABLEAU_APLATI) == 2027
    assert _premiere_annee_du_brief("2027 | 2028 | 2029") == 2027
    # Deux débuts différents : un historique ET un prévisionnel.
    assert _premiere_annee_du_brief("2021 2022 2023 … 2027 2028 2029") is None
    # Deux années ne font pas un en-tête.
    assert _premiere_annee_du_brief("Ouverture prévue pour la saison 2025-2026") is None
    # Des années non consécutives non plus.
    assert _premiere_annee_du_brief("2020 2025 2030") is None


def _donnee(identifiant: str, annee: int) -> SimpleNamespace:
    return SimpleNamespace(id=identifiant, annee=annee, valeur=1.0, unite="EUR")


def test_premiere_annee_du_socle() -> None:
    from generation.gate import _premiere_annee_du_socle

    assert _premiere_annee_du_socle([
        _donnee("ca_previsionnel_an1", 2027),
        _donnee("ca_previsionnel_an2", 2028),
        _donnee("resultat_net_an3", 2029),
    ]) == 2027
    # Un socle qui date tous ses exercices de la même année ne dit rien.
    assert _premiere_annee_du_socle([
        _donnee("ca_previsionnel_an1", 2026),
        _donnee("ca_previsionnel_an2", 2026),
        _donnee("ca_previsionnel_an3", 2026),
    ]) is None
    # Un seul exercice non plus.
    assert _premiere_annee_du_socle([_donnee("ca_previsionnel_an1", 2027)]) is None

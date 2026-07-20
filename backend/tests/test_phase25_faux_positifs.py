"""Phase 25 — Tuer les faux positifs mesures sur SYNAPSES v2.

Retour de Tobias apres le premier vrai test (19/07/2026) : le check
`chiffre contre chiffre` produit des faux positifs qui polluent la lecture
et font perdre confiance dans le systeme. Trois cas mesures sur la
generation reelle (job c3798821) :

  1. « CAF s'eleve a 79 657 EUR ... annuite de dette de 920 000 EUR »
     avant : le motif prenait 920 000 EUR comme valeur de la CAF, alors
     que le mot « annuite » entre les deux dit clairement le contraire.

  2. « EBE annee 1 : 121 334 EUR ... CA theorique 455 040 EUR »
     avant : la premiere mention capturait 455 040 EUR pour l'EBE, alors
     que « CA » entre les deux coupe le lien semantique.

  3. « L'apport represente 180 000 EUR » vs « L'apport represente
     150 000 EUR » (confusion apport / subvention par le modele)
     ceci est un VRAI defaut, il DOIT continuer d'etre detecte.

Regle 4 : viser la classe. Le pattern matching par PROXIMITE cree des
faux positifs par construction. On exige une LIAISON syntaxique (verbe de
valeur, deux-points), et une annee explicite pour les libelles annuels.

Regle 6 : chaque test cherche un comportement qui n'existait pas avant.
"""
from __future__ import annotations

import pytest

from generation.checks_evangeline import (
    DivergenceChiffree,
    Mention,
    collecter_mentions,
    detecter_divergences,
)


def _divs(textes: dict[int, str]) -> list[DivergenceChiffree]:
    mentions: list[Mention] = []
    for ch, t in textes.items():
        mentions.extend(collecter_mentions(ch, t))
    return detecter_divergences(mentions)


# ── Faux positifs qui DOIVENT disparaitre ───────────────────────────────────


def test_l_annuite_de_dette_n_est_pas_prise_pour_la_caf() -> None:
    """Cas SYNAPSES v2, chapitre 15 : « CAF de 79 657 EUR. Annuite de dette
    de 920 000 EUR ». Avant : le check reportait « CAF divergente ».
    """
    divs = _divs({15: (
        "La CAF annee 1 s'eleve a 79 657 EUR. L'annuite de dette atteint "
        "920 000 EUR sur la periode de remboursement."
    )})

    assert divs == [], (
        f"faux positif non tue : {[d.resume for d in divs]}"
    )


def test_le_ca_theorique_a_100_ne_devient_pas_l_ebe_annee_1() -> None:
    """Cas SYNAPSES v2, chapitre 0 : « CA theorique a 100 % : 455 040 EUR.
    EBE annee 1 : 121 334 EUR ». Avant : le check reportait EBE divergent.
    """
    divs = _divs({0: (
        "Le CA theorique a 100 % d'occupation est de 455 040 EUR par an. "
        "L'EBE annee 1 s'etablit a 121 334 EUR."
    )})

    # Aucune divergence : seul EBE annee 1 est capture, avec la bonne valeur.
    assert divs == [], (
        f"faux positif non tue : {[d.resume for d in divs]}"
    )


def test_un_libelle_annuel_sans_annee_est_ignore() -> None:
    """« La tresorerie atteint 300 000 EUR » sans « annee N » = ambigu.
    On refuse la capture plutot que de creer un faux positif si le meme
    libelle apparait ailleurs avec une valeur differente."""
    divs = _divs({
        5: "La tresorerie atteint 300 000 EUR au terme du plan.",
        12: "La tresorerie fin annee 3 est de 328 458 EUR.",
    })

    # Une seule mention retenue (celle avec annee), donc pas de divergence.
    assert divs == []


# ── Vrais defauts qui doivent RESTER detectes ───────────────────────────────


def test_l_apport_confondu_avec_les_subventions_reste_signale() -> None:
    """Vrai defaut SYNAPSES v2 : 150 000 est le montant des subventions,
    180 000 celui de l'apport. Le modele les inverse dans certains
    chapitres. La divergence DOIT etre bloquante (libelle global apport,
    pas d'annee)."""
    divs = _divs({
        1:  "L'apport personnel est de 180 000 EUR (14 % du besoin total).",
        3:  "L'apport personnel s'eleve a 150 000 EUR.",
    })

    assert len(divs) == 1
    assert divs[0].libelle == "apport"
    valeurs = {m.montant_base for m in divs[0].mentions}
    assert valeurs == {180_000.0, 150_000.0}


def test_le_seuil_de_rentabilite_a_trois_valeurs_reste_signale() -> None:
    """Vrai defaut SYNAPSES v1 : Evangeline citait 122 000, 205 000 et
    180 000. Libelle GLOBAL, une seule valeur autorisee tout le document."""
    divs = _divs({
        6:  "Le seuil de rentabilite se situe a 122 000 EUR.",
        9:  "Le seuil de rentabilite est de 205 000 EUR.",
        12: "Le seuil de rentabilite atteint 180 000 EUR.",
    })

    assert len(divs) == 1
    assert divs[0].libelle == "seuil_rentabilite"


def test_la_tresorerie_annuelle_divergente_reste_signalee() -> None:
    """Vrai defaut SYNAPSES v1 (Evangeline) : trésorerie fin année 1 à
    168 622 EUR dans un chapitre et 163 672 EUR dans un autre."""
    divs = _divs({
        11: "La tresorerie fin annee 1 s'eleve a 168 622 EUR.",
        14: "En fin d'annee 1, la tresorerie est de 163 672 EUR.",
    })

    assert len(divs) == 1
    assert divs[0].libelle == "tresorerie"
    assert divs[0].annee == 1


def test_l_investissement_total_recopie_partout_ne_signale_rien() -> None:
    """Contre-epreuve du bien : le vrai fait client verrouille est repete
    a l'identique dans 15 chapitres. Aucune divergence."""
    corps = "L'investissement total est de 1 250 000 EUR HT."
    divs = _divs({i: corps for i in range(1, 16)})

    assert divs == []


# ── SYNAPSES v2 : les fourchettes du BRIEF, recopiees par le modele ─────────


def test_le_prompt_ordonne_de_trancher_les_fourchettes_du_brief() -> None:
    """Sur SYNAPSES v2, le brief citait « 14-16 % » et « 180-280 kEUR », le
    modele les a recopiees dans 48 chapitres. La consigne interdit desormais
    la recopie et impose une valeur unique."""
    from catalog.models import DeliverableType
    from generation.prompts import build_system_prompt

    prompt = build_system_prompt(DeliverableType.BUSINESS_PLAN, country="France")

    assert "fourchettes du brief" in prompt.lower()
    assert "trancher" in prompt.lower() or "mediane" in prompt.lower()
    assert "recopie jamais" in prompt.lower()


# ── SYNAPSES v2 : les niveaux de marche verrouilles par PROSE NATURELLE ─────


@pytest.mark.django_db
def test_les_niveaux_de_marche_sont_verrouilles_meme_sans_formule_rigide() -> None:
    """Constate sur SYNAPSES v2 : « croissance europeenne est de 8 % »,
    « a l'echelle nationale le marche represente 900 millions » ne matchait
    pas les patterns rigides. Refonte : un pattern universel qui capture le
    montant, discrimination par le qualificatif de zone dans le match."""
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.coherence import extract_and_lock_chiffres_cles
    from generation.services import bootstrap_generation_job
    from intake.models import IntakeStatus, IntakeSubmission
    from orders.models import Order

    offer = Offer.objects.create(
        name="EM test naturel",
        slug="em-naturel",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="nat@example.com")
    order = Order.objects.create(
        systeme_order_id="ord_nat", customer=customer, offer=offer
    )
    submission = IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "coworking",
            "PAYS": "France",
            "ZONE": "Beziers",
            "PROJET": "coworking",
        },
    )
    job = bootstrap_generation_job(submission)

    extract_and_lock_chiffres_cles(job, chapter_number=1, content=(
        # Formulations reelles produites par le modele dans SYNAPSES v2
        "A l'echelle internationale, le marche pese 30 milliards en 2025. "
        "Le marche europeen represente 8 milliards. "
        "Le marche national francais atteint 900 millions."
    ))

    cles = set(
        job.coherence_facts.filter(is_locked=True).values_list("key", flat=True)
    )
    # Les trois niveaux doivent etre presents (mondial / continental / national)
    assert "taille_marche_mondial" in cles
    assert "taille_marche_continental" in cles
    assert "taille_marche_national" in cles

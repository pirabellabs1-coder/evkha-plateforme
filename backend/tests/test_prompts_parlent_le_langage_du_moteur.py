"""Les fichiers de prompts ne commandent plus l'ancien mecanisme de figures.

Etapes 6-7 du plan de migration (06/08/2026).

## Les fences ```chart

Le moteur structure ne rend JAMAIS un fence ```chart : ses figures naissent du
bloc `graphiques` du payload JSON, resolues contre le socle. Un prompt qui
demande « insere un bloc ```chart » a un chapitre structure demande donc un
artefact que la chaine de rendu ignorera — au mieux du bruit dans le markdown,
au pire un chapitre qui « obeit » en produisant l'inutile a la place de la
figure attendue.

L'INTENTION des prompts etait juste (un radar, un comparatif) : seule la
mecanique etait fausse. Les demandes sont reformulees en termes de FORMES du
catalogue (`radar`, `barres_horizontales`, `camembert`), que chaque moteur
sait interpreter.

## La consigne anti-fourchettes

Meme trou de transmission que l'objectif de figures, corrige le meme jour :
`_consigne_specifique_livrable` — dont la regle STRICTE « jamais une plage »
du BP, de l'EC et de la STR — vivait dans `build_system_prompt`, que seul le
moteur herite envoie. Le gate `_check_fourchettes` est pourtant strict hors
EM : il aurait bloque des chapitres auxquels la regle n'avait jamais ete dite.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from catalog.models import DeliverableType

RACINE = Path(__file__).resolve().parents[2]


# ── 1. Plus aucun fence chart dans les prompts ───────────────────────────────


@pytest.mark.parametrize(
    "fichier",
    sorted(
        chemin.relative_to(RACINE).as_posix()
        for chemin in (RACINE / "prompts").rglob("*.md")
    ),
)
def test_aucun_prompt_ne_demande_de_fence_chart(fichier: str) -> None:
    """Test de CLASSE : tout fichier present et futur, pas les deux corriges.

    Le jour ou quelqu'un recopie un vieux prompt avec son ```chart, ce test le
    nomme — plutot que de laisser un chapitre commander un artefact que le
    rendu ignore (regle 4).
    """
    contenu = (RACINE / fichier).read_text(encoding="utf-8")
    assert "```chart" not in contenu, fichier


def test_les_intentions_de_figures_ont_survecu_a_la_reformulation() -> None:
    """CONTRE-EPREUVE : retirer le mecanisme ne devait pas retirer la demande."""
    str_03 = (RACINE / "prompts/strategie_business/chapitre_03.md").read_text(
        encoding="utf-8"
    )
    ec_07 = (RACINE / "prompts/etude_concurrence/chapitre_07.md").read_text(
        encoding="utf-8"
    )

    assert "`radar`" in str_03
    assert "Positionnement du projet" in str_03
    assert "`radar`" in ec_07
    assert "`barres_horizontales`" in ec_07 or "`camembert`" in ec_07


# ── 2. La regle anti-fourchettes atteint le chemin structure ─────────────────


@pytest.mark.django_db
def test_la_regle_anti_fourchettes_atteint_un_chapitre_structure_de_bp() -> None:
    """Sur le code d'avant, le prompt d'un chapitre BP structure n'en disait rien.

    Le gate est strict hors EM : bloquer un chapitre sur une regle qu'on ne lui
    a pas transmise, c'est le CHECK INITIAL de 07745d4a sous une autre forme.
    """
    from catalog.models import Offer
    from customers.models import Customer
    from generation.chapitres import runner as chap_runner
    from generation.chapitres.configuration import type_document
    from generation.models import ChapterGeneration, GenerationJob
    from generation.socle.schema import Socle, Zone
    from orders.models import Order

    offre, _ = Offer.objects.get_or_create(
        slug="bp-fourchettes",
        defaults={"name": "BP", "deliverable_type": DeliverableType.BUSINESS_PLAN},
    )
    contact = Customer.objects.create(email="bp-fourchettes@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-bp-fourchettes", customer=contact, offer=offre,
    )
    job = GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.BUSINESS_PLAN,
        budget_eur=Decimal("4.00"),
    )
    chapitre = ChapterGeneration.objects.create(
        job=job, chapter_number=9, chapter_title="Modèle économique",
        prompt_key="bp.09.modele",
    )
    socle = Socle(
        secteur="joaillerie de créateurs",
        zone=Zone(pays="France"),
        date_socle=date(2026, 8, 6),
    )

    prompt, _manquantes = chap_runner.construire_prompt_chapitre(
        chapitre,
        socle=socle,
        variables={"SECTEUR": "joaillerie", "PAYS": "France"},
        document=type_document(DeliverableType.BUSINESS_PLAN),
    )

    assert "FOURCHETTES DU BRIEF" in prompt
    assert "jamais une plage" in prompt


@pytest.mark.django_db
def test_l_em_structuree_ne_recoit_pas_la_regle_stricte() -> None:
    """CONTRE-EPREUVE : l'EM garde sa regle a elle (fourchette sourcee admise).

    `_consigne_specifique_livrable` rend une chaine vide pour l'EM — sa charte
    porte deja sa propre regle, et la stricte la contredirait (les fourchettes
    Y SONT admises quand elles sont sourcees, avec mediane retenue).
    """
    from catalog.models import Offer
    from customers.models import Customer
    from generation.chapitres import runner as chap_runner
    from generation.chapitres.configuration import type_document
    from generation.models import ChapterGeneration, GenerationJob
    from generation.socle.schema import Socle, Zone
    from orders.models import Order

    offre, _ = Offer.objects.get_or_create(
        slug="em-fourchettes",
        defaults={"name": "EM", "deliverable_type": DeliverableType.MARKET_STUDY},
    )
    contact = Customer.objects.create(email="em-fourchettes@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-em-fourchettes", customer=contact, offer=offre,
    )
    job = GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=Decimal("4.00"),
    )
    chapitre = ChapterGeneration.objects.create(
        job=job, chapter_number=2, chapter_title="Marché national",
        prompt_key="em.02.national",
    )
    socle = Socle(
        secteur="joaillerie de créateurs",
        zone=Zone(pays="France"),
        date_socle=date(2026, 8, 6),
    )

    prompt, _manquantes = chap_runner.construire_prompt_chapitre(
        chapitre,
        socle=socle,
        variables={"SECTEUR": "joaillerie", "PAYS": "France"},
        document=type_document(DeliverableType.MARKET_STUDY),
    )

    assert "FOURCHETTES DU BRIEF" not in prompt

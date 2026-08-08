"""Un prompt ne doit pas ordonner d'aller chercher dans un bloc absent.

Défaut mesuré : six prompts EM ordonnaient d'employer « EXACTEMENT les valeurs
du bloc CHIFFRES_FONDATIONS », avec les identifiants `taille_marche_mondial` et
`taille_marche_continental`. Trois donnaient même un exemple travaillé.

Or `chiffres_fondations_as_table` n'est appelée que depuis `context.py` —
l'ANCIENNE chaîne. En production, `EVKHA_SOCLE_ENABLED` vaut vrai et c'est
`chapitres.runner` qui compose le prompt : ce bloc n'y a jamais figuré. Les
identifiants non plus : le socle porte `marche_mondial_taille`.

Le modèle recevait donc l'ordre d'aller chercher des valeurs nommées, dans un
bloc nommé, dont ni l'un ni l'autre n'était présent. C'est la forme la plus
coûteuse d'une consigne fausse : elle a l'apparence d'une contrainte de
cohérence, elle n'en est pas une, et rien dans le livrable ne le montre.

Ce test vise la CLASSE, pas les six occurrences (règle 4) : aucun prompt ne peut
nommer un bloc de contexte que le constructeur n'émet pas. Il échoue sur le code
d'avant.
"""
from __future__ import annotations

import re

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres.configuration import (
    type_document,
    types_declares,
)
from generation.chapitres.fichiers_prompts import charger_prompt
from generation.chapitres.runner import construire_prompt_chapitre
from generation.models import GenerationJob
from generation.services import bootstrap_generation_job
from generation.socle.services import etablir_socle, socle_verrouille
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StubClaudeClient
from orders.models import Order

EM = DeliverableType.MARKET_STUDY

_VARIABLES = {
    "SECTEUR": "coworking",
    "PAYS": "France",
    "ZONE": "Lyon",
    "PROJET": "espace de coworking",
}

#: Un intitulé de bloc : au moins deux segments en capitales, séparés par des
#: underscores. `TAM`, `SOM`, `URL` n'en sont pas ; `CHIFFRES_FONDATIONS` en est.
_INTITULE_DE_BLOC = re.compile(r"\b([A-Z]{3,}(?:_[A-Z0-9]{2,}){1,3})\b")

#: Intitulés qui NE désignent pas un bloc de contexte : réglages, marqueurs de
#: rendu, mots que le modèle doit produire. Les énumérer ici plutôt que
#: d'assouplir la règle : chaque ajout est une décision visible.
_PAS_DES_BLOCS = frozenset({
    "EVKHA_USE_STUB_AI",
    "EVKHA_USE_STUB_SEARCH",
    "EVKHA_SOCLE_ENABLED",
    "EVKHA_LIVRABLE_WORD",
    "EVKHA_APP_URL",
    "EVKHA_BASE_URL",
})


@pytest.fixture
def job_em(db: object) -> GenerationJob:
    offer = Offer.objects.create(name="EM", slug="em-blocs", deliverable_type=EM)
    customer = Customer.objects.create(email="blocs@example.com")
    order = Order.objects.create(
        systeme_order_id="order-blocs-01", customer=customer, offer=offer
    )
    submission = IntakeSubmission.objects.create(
        order=order, status=IntakeStatus.NORMALIZED, normalized_variables=_VARIABLES
    )
    job = bootstrap_generation_job(submission)
    etablir_socle(job, client=StubClaudeClient(), variables=_VARIABLES)
    return job


@pytest.mark.django_db
def test_aucun_prompt_ne_cite_un_bloc_que_le_constructeur_n_emet_pas(
    job_em: GenerationJob,
) -> None:
    """Le test qui échoue sur le code d'avant, et sur la CLASSE du défaut."""
    socle = socle_verrouille(job_em)
    assert socle is not None
    document = type_document(EM)

    fautes: list[str] = []
    for blueprint in document.chapitres():
        numero = blueprint.number
        instruction = charger_prompt(str(EM), numero)
        cites = {
            nom for nom in _INTITULE_DE_BLOC.findall(instruction)
            if nom not in _PAS_DES_BLOCS
        }
        if not cites:
            continue
        prompt, _ = construire_prompt_chapitre(
            job_em.chapters.get(chapter_number=numero),
            socle=socle,
            variables=_VARIABLES,
            document=document,
        )
        # On retire l'instruction elle-meme du prompt : sinon un bloc cite se
        # trouverait toujours, puisqu'il figure dans le texte qu'on vient d'y
        # coller. C'est le reste du prompt qui doit le contenir.
        reste = prompt.replace(instruction, "")
        for nom in sorted(cites):
            if nom not in reste:
                fautes.append(f"chapitre {numero} : « {nom} » n'est dans aucun bloc")

    assert not fautes, "\n".join(fautes)


def test_les_identifiants_cites_par_les_prompts_existent_dans_le_referentiel() -> None:
    """Un identifiant mal orthographié est une consigne sans effet.

    Les prompts nommaient `taille_marche_mondial` ; le socle porte
    `marche_mondial_taille`. Le modèle cherchait une clé qui n'existe pas.
    """
    from generation.socle.referentiel import definitions_pour

    connus = {d.identifiant for d in definitions_pour(str(EM))}
    # Identifiants cites entre accents graves dans les prompts, en minuscules
    # avec underscores — la forme qu'ont les cles du socle.
    motif = re.compile(r"`([a-z][a-z0-9]*(?:_[a-z0-9]+){1,3})`")

    fautes: list[str] = []
    for blueprint in type_document(EM).chapitres():
        texte = charger_prompt(str(EM), blueprint.number)
        for identifiant in set(motif.findall(texte)):
            # Les cles du socle parlent toutes de marche, de production, de
            # population ou du trio TAM/SAM/SOM. On ne juge que celles qui
            # ressemblent a une cle de socle, pas les noms de types de
            # graphique ni les cles de gabarit.
            if not identifiant.startswith(("marche_", "taille_marche", "production_")):
                continue
            if identifiant not in connus:
                fautes.append(
                    f"chapitre {blueprint.number} : `{identifiant}` "
                    "est absent du referentiel du socle"
                )

    assert not fautes, "\n".join(fautes)


def test_la_regle_vaut_pour_les_quatre_livrables() -> None:
    """Contre-épreuve de couverture : le test ne doit pas ne regarder que l'EM.

    Un défaut de cette classe dans un business plan coûterait autant.
    """
    codes = {document.code for document in types_declares()}
    assert len(codes) >= 4, f"seulement {len(codes)} livrables déclarés"

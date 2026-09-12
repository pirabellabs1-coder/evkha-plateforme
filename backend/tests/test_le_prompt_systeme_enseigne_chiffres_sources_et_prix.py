"""Ce que le modèle sait AVANT d'écrire : les chiffres, les sources, les prix.

Trois blocs d'instruction vivent dans le prompt système des chapitres. Chacun
répond à des défauts mesurés sur des documents réellement livrés, et aucun
n'était là avant le 12/09/2026 :

    COHERENCE_DES_CHIFFRES     zéros nus, calculs faux, unités mêlées
    SOURCES_ET_TRACABILITE     URL inventées, « 0 URL vérifiable pour 3 sources »
    PRIX_ET_MODELE_ECONOMIQUE  réalisé pris pour objectif, fourchettes, paliers

Ces tests échouent sur le code d'avant : les constantes n'existaient pas, donc
l'import lui-même casse.

La demande qui les a motivés est explicite (12/09/2026) : « il faut revenir au
niveau des prompts systèmes […] tout doit être vérifié et validé d'abord, avant
que ce soit plaqué dans le document ». Un contrôle aval sait compter une
erreur ; il ne sait pas l'empêcher. C'est ici qu'elle s'empêche.
"""
from __future__ import annotations

import contextlib
from typing import Any

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres import ChapitreInvalideError, produire_chapitre
from generation.chapitres.runner import (
    COHERENCE_DES_CHIFFRES,
    PRIX_ET_MODELE_ECONOMIQUE,
    SOURCES_ET_TRACABILITE,
)
from generation.services import bootstrap_generation_job
from generation.socle import etablir_socle
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import SYSTEM_CACHE_BREAK, StructuredResult, StubClaudeClient
from orders.models import Order

_VARIABLES = {
    "SECTEUR": "assistance informatique",
    "PAYS": "France",
    "ZONE": "Paris",
    "PROJET": "abonnement d'assistance",
}


class _Espion(StubClaudeClient):
    """Rend ce que rend la doublure, mais garde le prompt système envoyé."""

    def __init__(self) -> None:
        super().__init__()
        self.systemes: list[str] = []

    def complete_structured(self, **kwargs: Any) -> StructuredResult:
        self.systemes.append(str(kwargs.get("system", "")))
        return super().complete_structured(**kwargs)


def _premier_systeme(dossier: Any) -> str:
    """Le prompt système du premier chapitre, tel qu'il PART vers le modèle.

    La doublure demande une figure que le socle ne peut pas alimenter, donc le
    chapitre est refusé — c'est le comportement voulu, et il n'a rien à voir
    avec ce qu'on mesure ici. Ce qui nous intéresse est en amont du refus :
    l'appel a eu lieu, et on lit ce qu'il transportait.
    """
    espion = _Espion()
    with contextlib.suppress(ChapitreInvalideError):
        produire_chapitre(dossier, 1, client=espion)
    assert espion.systemes, "le chapitre n'a jamais appelé le modèle"
    return espion.systemes[0]


@pytest.fixture
def job(db: object) -> Any:
    offre = Offer.objects.create(
        name="EM", slug="em-prompts", deliverable_type=DeliverableType.MARKET_STUDY
    )
    client = Customer.objects.create(email="prompts@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id="cmd-prompts", customer=client, offer=offre
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED, normalized_variables=_VARIABLES
    )
    dossier = bootstrap_generation_job(soumission)
    etablir_socle(dossier, client=StubClaudeClient(), variables=_VARIABLES)
    return dossier


@pytest.mark.django_db
def test_les_trois_blocs_arrivent_vraiment_au_modele(job: Any) -> None:
    """LE test : on lit ce qui est ENVOYÉ, pas ce qui est écrit dans le module.

    Une constante peut exister et n'être concaténée nulle part — c'est
    exactement le défaut qu'on ne verrait pas autrement (règle 1 : un contrôle
    qui n'a rien à comparer n'est pas un succès).
    """
    systeme = _premier_systeme(job)
    for bloc, nom in (
        (COHERENCE_DES_CHIFFRES, "chiffres"),
        (SOURCES_ET_TRACABILITE, "sources"),
        (PRIX_ET_MODELE_ECONOMIQUE, "prix"),
    ):
        assert bloc in systeme, f"le bloc {nom} n'atteint pas le modèle"


@pytest.mark.django_db
def test_les_trois_blocs_sont_du_cote_CACHE_du_prompt(job: Any) -> None:
    """Sinon ils seraient repayés PLEIN TARIF à chaque chapitre du dossier.

    Une étude de marché fait 23 chapitres : placés du mauvais côté du point de
    coupe, ces blocs se factureraient 23 fois au lieu d'une. La règle est
    économique, pas esthétique — et elle est invisible à l'œil nu.
    """
    systeme = _premier_systeme(job)
    coupe = systeme.index(SYSTEM_CACHE_BREAK)
    for bloc, nom in (
        (COHERENCE_DES_CHIFFRES, "chiffres"),
        (SOURCES_ET_TRACABILITE, "sources"),
        (PRIX_ET_MODELE_ECONOMIQUE, "prix"),
    ):
        assert systeme.index(bloc) < coupe, f"le bloc {nom} est hors du cache"


def test_les_prix_repondent_aux_defauts_nommes() -> None:
    """Chaque exigence vient d'une erreur trouvée dans un document livré."""
    for attendu in (
        # Zenitek : 120 000 € de CA réalisé présentés comme un objectif.
        "REALISE ET VISE NE SE CONFONDENT JAMAIS",
        # WAOME : « entre 60 et 65 € » là où une décision était attendue.
        "UN PRIX EST UN NOMBRE, PAS UNE PLAGE",
        # Zenitek : trois paliers dont aucun ne disait ce qu'il ajoutait.
        "UN PALIER SE JUSTIFIE PAR CE QU'IL AJOUTE",
        # Le produit qui ne tombe pas juste, arrondi vers le chiffre rond.
        "CHIFFRE D'AFFAIRES = PRIX x VOLUME",
        "LE MEME PRIX PARTOUT",
        "UNE MARGE DIT LAQUELLE",
    ):
        assert attendu in PRIX_ET_MODELE_ECONOMIQUE, attendu


def test_aucun_bloc_ne_se_cite_dans_le_document() -> None:
    """CONTRE-ÉPREUVE de WAOME v4 : les règles s'y retrouvaient RÉCITÉES.

    Un modèle sur-instruit expose sa méthode au lecteur — « conformément à la
    source vérifiable… ». C'est un défaut de plus, pas une garantie de moins ;
    chaque bloc doit donc porter sa propre clause de discrétion.
    """
    for bloc in (SOURCES_ET_TRACABILITE, PRIX_ET_MODELE_ECONOMIQUE):
        assert "NE SE CITENT PAS DANS LE TEXTE" in bloc

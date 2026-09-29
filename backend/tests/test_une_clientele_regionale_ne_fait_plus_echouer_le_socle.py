"""Une clientèle régionale ne fait plus échouer le socle.

## Le défaut, sur un vrai dossier

29/09/2026, business plan `cb59cede` (ÉCLORE, agence événementielle
régionale) : « Socle non recevable après 3 tentative(s) :
`taille_clientele_cible` : périmètre « regional » alors que le référentiel
impose « national ». » Le dossier est tombé en échec à zéro chapitre sur 22,
après plus d'une heure et 1,13 €.

Le modèle avait raison trois fois : la clientèle cible d'une entreprise
régionale est régionale. Et le socle du business plan se contredisait
lui-même : son contrôle « clientèle × panier ≈ CA de l'an 1 » exige la
clientèle que l'entreprise VISE, à l'échelle de sa zone — une clientèle
nationale ne le satisfait pas.

## Ce que ce fichier verrouille

1. `taille_clientele_cible` admet national, régional ou entreprise en BP,
   national ou régional en EM ;
2. la consigne du socle dit au modèle ces mêmes échelles, et la doublure les
   lit encore (sinon la donnée disparaissait de la répétition à blanc) ;
3. contre-épreuve (règle 6) : une donnée à échelle unique reste stricte ; une
   échelle non admise reste refusée ; toute définition admet sa propre
   échelle de référence.
"""

from __future__ import annotations

from typing import Any

import pytest

from catalog.models import DeliverableType
from generation.socle.prompt import construire_prompt_socle
from generation.socle.referentiel import Perimetre, definition, identifiants_pour
from generation.socle.schema import Socle, valider_socle
from generation.socle.stub import _LIGNE_ID, socle_de_demonstration

BP = DeliverableType.BUSINESS_PLAN
EM = DeliverableType.MARKET_STUDY
LIVRABLES = (
    DeliverableType.MARKET_STUDY,
    DeliverableType.COMPETITOR_STUDY,
    DeliverableType.BUSINESS_PLAN,
    DeliverableType.BUSINESS_STRATEGY,
)

#: Le cas du 29/09/2026, à la forme d'un brief.
_VARIABLES = {
    "SECTEUR": "conception et organisation d'événements",
    "PAYS": "France",
    "ZONE": "Auvergne-Rhône-Alpes",
    "PROJET": "agence événementielle ÉCLORE",
}

CLIENTELE = "taille_clientele_cible"


def _prompt(livrable: str) -> str:
    return construire_prompt_socle(deliverable_type=livrable, variables=_VARIABLES)


def _charge(livrable: str) -> dict[str, Any]:
    return socle_de_demonstration(_prompt(livrable))


def _avec_perimetre(charge: dict[str, Any], identifiant: str, perimetre: str) -> dict[str, Any]:
    donnees = charge["donnees"]
    assert isinstance(donnees, list)
    cibles = [d for d in donnees if d["id"] == identifiant]
    assert cibles, f"`{identifiant}` absent de la doublure : ce test ne jugerait rien"
    cibles[0]["perimetre"] = perimetre
    return charge


def _motifs_de_perimetre(charge: dict[str, Any], livrable: str, identifiant: str) -> list[str]:
    motifs = valider_socle(Socle.model_validate(charge), livrable)
    return [m for m in motifs if m.startswith(f"`{identifiant}` : périmètre")]


@pytest.mark.parametrize("perimetre", ["regional", "entreprise", "national"])
def test_en_bp_la_clientele_suit_la_zone_du_projet(perimetre: str) -> None:
    charge = _avec_perimetre(_charge(BP), CLIENTELE, perimetre)
    assert _motifs_de_perimetre(charge, BP, CLIENTELE) == []


@pytest.mark.parametrize("perimetre", ["regional", "national"])
def test_en_em_la_clientele_peut_etre_regionale(perimetre: str) -> None:
    charge = _avec_perimetre(_charge(EM), CLIENTELE, perimetre)
    assert _motifs_de_perimetre(charge, EM, CLIENTELE) == []


def test_contre_epreuve_une_echelle_non_admise_reste_refusee() -> None:
    """En étude de marché, la clientèle d'un MARCHÉ n'est pas une donnée d'entreprise."""
    charge = _avec_perimetre(_charge(EM), CLIENTELE, "entreprise")
    motifs = _motifs_de_perimetre(charge, EM, CLIENTELE)
    assert len(motifs) == 1
    assert "« national » ou « regional »" in motifs[0]


def test_contre_epreuve_une_donnee_a_echelle_unique_reste_stricte() -> None:
    charge = _avec_perimetre(_charge(BP), "marche_national_taille", "regional")
    motifs = _motifs_de_perimetre(charge, BP, "marche_national_taille")
    assert len(motifs) == 1
    assert "« national »" in motifs[0]


def test_la_consigne_dit_les_echelles_admises_et_la_doublure_les_lit() -> None:
    prompt = _prompt(BP)
    assert "périmètre admis : national ou regional ou entreprise" in prompt
    lignes = {m.group("id"): m.group("perimetre") for m in _LIGNE_ID.finditer(prompt)}
    assert CLIENTELE in lignes, "la doublure ne lit plus la ligne : la donnée disparaît"
    assert lignes[CLIENTELE] == "national"


@pytest.mark.parametrize("livrable", LIVRABLES)
def test_toute_definition_admet_son_echelle_de_reference(livrable: str) -> None:
    for identifiant in identifiants_pour(livrable):
        attendue = definition(livrable, identifiant)
        assert attendue is not None
        assert attendue.perimetre in attendue.admis, identifiant
        assert all(isinstance(p, Perimetre) for p in attendue.admis), identifiant

"""La rédaction d'un chapitre passe par la mémoire de l'étude — pour les nouveaux dossiers.

29/09/2026, business plan ÉCLORE (`cb59cede`) : 62 % des nombres du document ne
venaient pas des données de référence, le revenu mensuel était la CAF ÷ 12,
la TVA « par choix ». Pour un dossier créé avec la mémoire
(`memoire_active`), chaque chapitre :

1. reçoit la mémoire dans son prompt (faits à citer par repère, décisions) ;
2. est contrôlé contre elle dès la réponse du modèle, et repris (niveau 2)
   sur un repère inconnu ou un motif grave ; un chiffre écrit en clair est
   un signal, qui accompagne la reprise sans la décider (`bf98827c`) ;
3. sort avec ses repères écrits en valeurs, au format français ;
4. est TOUJOURS validé au dernier essai (repli), jamais bloqué.

Contre-épreuve (règle 6) : un dossier sans mémoire garde exactement son chemin.
"""
from __future__ import annotations

from typing import Any

import pytest
from django.test import override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres.configuration import type_document
from generation.chapitres.runner import ChapitreInvalideError, construire_prompt_chapitre
from generation.chapitres.services import produire_avec_reprises
from generation.chapitres.stub import chapitre_de_demonstration
from generation.models import ChapterGeneration, GenerationJob
from generation.services import bootstrap_generation_job
from generation.socle import etablir_socle, socle_verrouille
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StructuredResult, StubClaudeClient
from orders.models import Order

pytestmark = pytest.mark.django_db

BP = DeliverableType.BUSINESS_PLAN
VARIABLES = {
    "SECTEUR": "Ateliers. Il s'agit d'une prestation de services commerciale.",
    "PAYS": "France", "ZONE": "Île-de-France", "PROJET": "Projet test",
    "DATE_CREATION": "Trajectoire juridique : micro-entreprise de 2027 à 2029.",
}


def _dossier(suffixe: str, *, memoire: bool) -> GenerationJob:
    offre, _ = Offer.objects.get_or_create(
        slug="bp-redaction-memoire", defaults={"name": "BP", "deliverable_type": BP},
    )
    client = Customer.objects.create(email=f"redaction-{suffixe}@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id=f"cmd-redaction-{suffixe}", customer=client, offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED, normalized_variables=VARIABLES,
    )
    with override_settings(EVKHA_MEMOIRE_ETUDE=memoire):
        job = bootstrap_generation_job(soumission)
    etablir_socle(job, client=StubClaudeClient(), variables=VARIABLES)
    return job


class ClientQuiInvente:
    """Écrit d'abord un chiffre calculé et un repère inconnu, puis se corrige."""

    def __init__(self, *, se_corrige: bool) -> None:
        self.appels = 0
        self.se_corrige = se_corrige
        self.prompts: list[str] = []

    def complete_structured(self, **kwargs: Any) -> StructuredResult:
        self.appels += 1
        contexte = f"{kwargs.get('system', '')}\n\n{kwargs['prompt']}"
        self.prompts.append(contexte)
        charge = chapitre_de_demonstration(contexte)
        if self.appels == 1 or not self.se_corrige:
            blocs = list(charge["blocs"])  # type: ignore[call-overload]
            blocs.append({
                "type": "paragraphe",
                "texte": "L'écart atteint 8 576,08 € ; le revenu vaut {{revenu_invente}}.",
            })
            charge["blocs"] = blocs
        return StructuredResult(payload=charge, input_tokens=10, output_tokens=10, model="stub")


def _texte(chapitre: ChapterGeneration) -> str:
    return str(chapitre.payload)


def test_le_redacteur_recoit_la_memoire() -> None:
    job = _dossier("a", memoire=True)
    chapitre = job.chapters.get(chapter_number=16)
    socle = socle_verrouille(job)
    assert socle is not None
    prompt, _ = construire_prompt_chapitre(
        chapitre, socle=socle, variables=VARIABLES, document=type_document(BP),
    )
    assert "MÉMOIRE DE L'ÉTUDE" in prompt.par_job, "dans la partie mise en cache"
    assert "{{resultat_net_mensuel_an3}}" in prompt.par_job
    dernier_bloc = prompt.par_chapitre.rstrip().split("\n\n")[-1]
    assert dernier_bloc.startswith("CHIFFRES — RAPPEL"), (
        "le rappel est le DERNIER bloc de la consigne du chapitre"
    )


def test_les_reperes_sortent_en_valeurs() -> None:
    job = _dossier("b", memoire=True)
    chapitre = produire_avec_reprises(job, 16, client=StubClaudeClient())
    texte = _texte(chapitre)
    assert "{{" not in texte, "aucun repère ne doit survivre dans le chapitre enregistré"
    job.refresh_from_db()
    assert job.memoire_etude["chapitres"]["16"]["reperes"], "la mémoire trace les repères cités"


def test_un_repere_inconnu_fait_reprendre_et_le_chiffre_en_clair_voyage_avec() -> None:
    job = _dossier("c", memoire=True)
    client = ClientQuiInvente(se_corrige=True)
    chapitre = produire_avec_reprises(job, 16, client=client)
    assert client.appels == 2
    assert "8 576,08" in client.prompts[1], "la reprise reçoit le motif précis"
    assert "8 576,08" not in _texte(chapitre)
    assert chapitre.etape == "valide"


def test_au_dernier_essai_le_chapitre_est_toujours_valide() -> None:
    job = _dossier("d", memoire=True)
    chapitre = produire_avec_reprises(job, 16, client=ClientQuiInvente(se_corrige=False))
    texte = _texte(chapitre)
    assert chapitre.etape == "valide"
    assert "revenu_invente" not in texte and "{{" not in texte
    job.refresh_from_db()
    assert job.memoire_etude["chapitres"]["16"]["replie"] is True


def test_un_dossier_sans_memoire_garde_son_chemin() -> None:
    """Contre-épreuve : ni bloc, ni contrôle, ni trace — le chemin d'avant."""
    job = _dossier("e", memoire=False)
    client = ClientQuiInvente(se_corrige=False)
    try:
        produire_avec_reprises(job, 16, client=client)
    except ChapitreInvalideError:
        pass
    assert all("MÉMOIRE DE L'ÉTUDE" not in p for p in client.prompts)
    job.refresh_from_db()
    # La relecture du texte (30/09/2026) vaut pour TOUS les dossiers et range
    # sa trace sous sa propre clé ; de la mémoire, rien.
    assert set(job.memoire_etude) <= {"relecture"}


class ClientQuiEcritEnClair:
    """Écrit un dérivé en clair, sans autre défaut : le vrai modèle du 29/09/2026."""

    def __init__(self) -> None:
        self.appels = 0

    def complete_structured(self, **kwargs: Any) -> StructuredResult:
        self.appels += 1
        contexte = f"{kwargs.get('system', '')}\n\n{kwargs['prompt']}"
        charge = chapitre_de_demonstration(contexte)
        blocs = list(charge["blocs"])  # type: ignore[call-overload]
        blocs.append({"type": "paragraphe", "texte": "L'écart atteint 8 576,08 € sur la période."})
        charge["blocs"] = blocs
        return StructuredResult(payload=charge, input_tokens=10, output_tokens=10, model="stub")


def test_un_chiffre_en_clair_seul_ne_fait_pas_reecrire_le_chapitre() -> None:
    """Épreuve réelle `bf98827c` : 45 chiffres en clair, un dossier arrêté à 8 €."""
    job = _dossier("f", memoire=True)
    client = ClientQuiEcritEnClair()
    chapitre = produire_avec_reprises(job, 16, client=client)
    assert client.appels == 1, "un chiffre en clair seul ne paie pas une réécriture"
    assert chapitre.etape == "valide"
    job.refresh_from_db()
    trace = job.memoire_etude["chapitres"]["16"]
    assert any("8 576,08" in s for s in trace["signaux"])
    assert trace["motifs"] == []


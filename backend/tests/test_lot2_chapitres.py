"""Lot 2 — orchestration des chapitres.

Les tests suivent les critères de recette du cahier des charges :
- un chapitre n'exploite que des données du socle ;
- un chapitre se régénère seul sans altérer les autres ;
- trois échecs bloquent l'étude et n'envoient aucun e-mail ;
- ajouter un type de document ne demande que des prompts et une configuration.
"""
from __future__ import annotations

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres import (
    ChapitreInvalideError,
    ChapitrePayload,
    chapitres_a_produire,
    chapitres_sans_prompt,
    charger_prompt,
    compter_mots,
    etude_complete,
    interpoler,
    marquer_intervention_requise,
    payload_vers_markdown,
    produire_chapitre,
    regenerer_chapitre,
    temporisation,
    type_document,
    types_declares,
    valider_chapitre,
)
from generation.chapitres.runner import construire_prompt_chapitre
from generation.chapitres.stub import chapitre_de_demonstration
from generation.models import (
    ChapterStatus,
    GenerationJob,
    JobStatus,
)
from generation.services import bootstrap_generation_job
from generation.socle import etablir_socle, socle_verrouille
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StructuredResult, StubClaudeClient
from monitoring.models import OperationalIncident
from orders.models import Order

EM = DeliverableType.MARKET_STUDY

_VARIABLES = {
    "SECTEUR": "joaillerie de créateurs",
    "PAYS": "France",
    "ZONE": "Paris",
    "PROJET": "maison d'édition joaillière",
}


@pytest.fixture
def job_em(db: object) -> GenerationJob:
    offer = Offer.objects.create(name="EM", slug="em-lot2", deliverable_type=EM)
    customer = Customer.objects.create(email="lot2@example.com")
    order = Order.objects.create(
        systeme_order_id="order-lot2-01", customer=customer, offer=offer
    )
    submission = IntakeSubmission.objects.create(
        order=order, status=IntakeStatus.NORMALIZED, normalized_variables=_VARIABLES
    )
    job = bootstrap_generation_job(submission)
    etablir_socle(job, client=StubClaudeClient(), variables=_VARIABLES)
    return job


# ── Configuration : générique, pas de constante en dur ───────────────────────


def test_tous_les_types_declares_ont_leur_chapitrage() -> None:
    for document in types_declares():
        assert document.nombre_de_chapitres() > 0, document.code


def test_le_nombre_de_chapitres_vient_de_la_configuration() -> None:
    """Aucune constante 22 : le chapitrage est une donnée."""
    assert type_document(EM).nombre_de_chapitres() == 22
    assert type_document(DeliverableType.COMPETITOR_STUDY).nombre_de_chapitres() == 10


def test_chaque_chapitre_declare_a_un_fichier_de_prompt() -> None:
    """Un chapitre sans prompt échouerait au milieu d'une génération payante."""
    for document in types_declares():
        assert chapitres_sans_prompt(document) == [], document.code


def test_les_prompts_sont_lus_depuis_les_fichiers() -> None:
    contenu = charger_prompt(EM, 4)
    assert "CHAPITRE 4" in contenu


def test_le_bandeau_de_documentation_ne_part_pas_dans_le_prompt() -> None:
    """Il cite la syntaxe des variables : l'envoyer les ferait interpoler."""
    brut = charger_prompt(EM, 4, brut=True)
    net = charger_prompt(EM, 4)
    assert "Exporté depuis generation/prompt_library.py" in brut
    assert "Exporté depuis" not in net
    assert "<!--" not in net


# ── Interpolation ────────────────────────────────────────────────────────────


def test_interpolation_remplace_les_variables_connues() -> None:
    texte, manquantes = interpoler("Secteur : {{ secteur }}.", {"secteur": "joaillerie"})
    assert texte == "Secteur : joaillerie."
    assert manquantes == []


def test_une_variable_inconnue_est_signalee_et_laissee_visible() -> None:
    """La remplacer par du vide produirait un prompt amputé sans que rien ne le dise."""
    texte, manquantes = interpoler("Zone : {{ inconnue }}.", {})
    assert "{{ inconnue }}" in texte
    assert manquantes == ["inconnue"]


# ── Contrat de chapitre ──────────────────────────────────────────────────────


def _payload_valide(
    numero: int = 4, identifiants: tuple[str, ...] = ("tam", "sam")
) -> dict[str, Any]:
    return {
        "chapitre": numero,
        "titre": "Chapitre de test",
        "sections": [{"titre": "4.1 Analyse", "contenu": "Contenu."}],
        "donnees_utilisees": list(identifiants),
        "graphiques": [
            {"type": "barres", "titre": "G", "donnees_ids": list(identifiants)}
        ],
        "resume": " ".join(["mot"] * 180),
    }


def _valider(
    charge: dict[str, Any], *, numero: int = 4, socle_ids: frozenset[str] | None = None
) -> list[str]:
    return valider_chapitre(
        ChapitrePayload.model_validate(charge),
        numero_attendu=numero,
        identifiants_socle=socle_ids if socle_ids is not None else frozenset({"tam", "sam"}),
        resume_mots_min=150,
        resume_mots_max=250,
    )


def test_un_chapitre_conforme_est_accepte() -> None:
    assert _valider(_payload_valide()) == []


def test_rejette_une_donnee_absente_du_socle() -> None:
    """Cœur du lot 2 : un chapitre ne peut pas produire un chiffre."""
    charge = _payload_valide(identifiants=("tam", "chiffre_invente"))
    motifs = _valider(charge)
    assert any("chiffre_invente" in motif for motif in motifs)


def test_une_donnee_de_graphique_non_declaree_est_AJOUTEE_a_la_declaration() -> None:
    """Ce test exigeait auparavant un REJET. Il a tué une etude reelle.

    Le modele demandait un graphique citant `marche_continental_taille` sans
    l'inscrire dans `donnees_utilisees`. Trois tentatives, trois fois le meme
    oubli : une etourderie de tenue de registre, pas une erreur sur le marche.

    Les deux champs sont remplis par le MEME modele sur le MEME chapitre : leur
    desaccord dit que la declaration est incomplete, pas qu'un chiffre est
    invente. La completer la rend vraie.
    """
    charge = _payload_valide()
    charge["graphiques"][0]["donnees_ids"] = ["som"]

    payload = ChapitrePayload.model_validate(charge)

    assert "som" in payload.donnees_utilisees, (
        "la declaration n'a pas ete completee : l'etude sera perdue sur une "
        "etourderie de registre"
    )


def test_une_donnee_de_graphique_ABSENTE_DU_SOCLE_est_toujours_refusee() -> None:
    """LA garantie qui compte, verifiee contre la bonne evidence (regle 9).

    Completer la declaration ne doit rien masquer : la regle de fond n'est pas
    « les deux champs concordent » mais « un chapitre n'exploite que des
    donnees du socle ». Un graphique qui inventerait une donnee doit rester
    rejete — par le controle qui compare au socle, et non par celui qui compare
    un champ a un autre.
    """
    charge = _payload_valide()
    charge["graphiques"][0]["donnees_ids"] = ["chiffre_invente"]

    motifs = _valider(charge)

    assert any("chiffre_invente" in motif for motif in motifs), (
        "un graphique peut desormais reposer sur une donnee inventee"
    )


def test_rejette_un_numero_de_chapitre_incoherent() -> None:
    motifs = _valider(_payload_valide(numero=9), numero=4)
    assert any("ne correspond pas" in motif for motif in motifs)


@pytest.mark.parametrize("mots", [80, 400])
def test_rejette_un_resume_hors_fourchette(mots: int) -> None:
    charge = _payload_valide()
    charge["resume"] = " ".join(["mot"] * mots)
    motifs = _valider(charge)
    assert any("résumé fait" in motif for motif in motifs)


def test_rejette_deux_sections_de_meme_titre() -> None:
    charge = _payload_valide()
    charge["sections"].append({"titre": "4.1 Analyse", "contenu": "Doublon."})
    motifs = _valider(charge)
    assert any("même titre" in motif for motif in motifs)


def test_rejette_un_type_de_graphique_inconnu() -> None:
    """Le rendu doit savoir dessiner chaque type : un inconnu casserait le lot 3."""
    charge = _payload_valide()
    charge["graphiques"][0]["type"] = "camembert_3d_anime"
    with pytest.raises(ValidationError):
        ChapitrePayload.model_validate(charge)


def test_le_rendu_markdown_ne_porte_aucune_valeur_de_graphique() -> None:
    """Un graphique porte des identifiants, jamais des nombres."""
    payload = ChapitrePayload.model_validate(_payload_valide())
    markdown = payload_vers_markdown(payload)
    assert "graphique:barres" in markdown
    assert "donnees=\"tam,sam\"" in markdown


# ── Production réelle sur la base ────────────────────────────────────────────


@pytest.mark.django_db
def test_le_socle_est_injecte_dans_le_prompt_du_chapitre(job_em: GenerationJob) -> None:
    socle = socle_verrouille(job_em)
    assert socle is not None
    chapitre = job_em.chapters.get(chapter_number=4)
    prompt, manquantes = construire_prompt_chapitre(
        chapitre,
        socle=socle,
        variables=_VARIABLES,
        document=type_document(EM),
    )
    assert "SOCLE VERROUILLÉ" in prompt
    assert "`tam` =" in prompt
    assert manquantes == []


@pytest.mark.django_db
def test_produire_un_chapitre_enregistre_structure_et_markdown(
    job_em: GenerationJob,
) -> None:
    chapitre = produire_chapitre(job_em, 4, client=StubClaudeClient())

    assert chapitre.status == ChapterStatus.DONE
    assert chapitre.payload["chapitre"] == 4
    assert chapitre.content, "Le rendu markdown doit rester disponible."
    assert 150 <= compter_mots(chapitre.operational_summary) <= 250
    assert chapitre.cost_eur > 0


@pytest.mark.django_db
def test_produire_un_chapitre_est_idempotent(job_em: GenerationJob) -> None:
    """Une tâche rejouée après un crash ne doit pas repayer le chapitre."""
    premier = produire_chapitre(job_em, 4, client=StubClaudeClient())
    cout = premier.cost_eur

    class _Interdit:
        def complete_structured(self, **kwargs: Any) -> StructuredResult:
            raise AssertionError("Aucun appel ne doit avoir lieu sur un chapitre DONE.")

    encore = produire_chapitre(job_em, 4, client=_Interdit())
    assert encore.cost_eur == cout


@pytest.mark.django_db
def test_sans_socle_aucun_chapitre_ne_peut_etre_redige(db: object) -> None:
    offer = Offer.objects.create(name="EM", slug="em-sans-socle", deliverable_type=EM)
    customer = Customer.objects.create(email="sans-socle@example.com")
    order = Order.objects.create(
        systeme_order_id="order-sans-socle", customer=customer, offer=offer
    )
    submission = IntakeSubmission.objects.create(
        order=order, status=IntakeStatus.NORMALIZED, normalized_variables=_VARIABLES
    )
    job = bootstrap_generation_job(submission)

    from generation.chapitres import SocleManquantError

    with pytest.raises(SocleManquantError):
        produire_chapitre(job, 4, client=StubClaudeClient())


# ── Critère de recette : régénérer un chapitre seul ──────────────────────────


@pytest.mark.django_db
def test_regenerer_un_chapitre_seul_n_altere_pas_les_autres(job_em: GenerationJob) -> None:
    produire_chapitre(job_em, 4, client=StubClaudeClient())
    produire_chapitre(job_em, 5, client=StubClaudeClient())

    temoin = job_em.chapters.get(chapter_number=5)
    contenu_temoin = temoin.content
    resume_temoin = temoin.operational_summary

    regenere = regenerer_chapitre(job_em, 4, client=StubClaudeClient())

    temoin.refresh_from_db()
    assert regenere.status == ChapterStatus.DONE
    assert regenere.payload["chapitre"] == 4
    assert temoin.content == contenu_temoin
    assert temoin.operational_summary == resume_temoin
    assert temoin.status == ChapterStatus.DONE


# ── Critère de recette : trois échecs bloquent l'étude ───────────────────────


class _ClientDefaillant:
    """Rend systématiquement une charge invalide."""

    def __init__(self) -> None:
        self.appels = 0

    def complete_structured(self, **kwargs: Any) -> StructuredResult:
        self.appels += 1
        return StructuredResult(
            payload={"chapitre": 4}, input_tokens=5, output_tokens=5, model="stub"
        )


@pytest.mark.django_db
def test_un_chapitre_invalide_conserve_les_motifs_pour_la_reprise(
    job_em: GenerationJob,
) -> None:
    client = _ClientDefaillant()
    with pytest.raises(ChapitreInvalideError):
        produire_chapitre(job_em, 4, client=client)

    chapitre = job_em.chapters.get(chapter_number=4)
    assert chapitre.status == ChapterStatus.FAILED
    assert chapitre.error_message.startswith("[contrat] ")
    assert chapitre.retry_count == 1


@pytest.mark.django_db
def test_la_reprise_transmet_les_motifs_du_refus(job_em: GenerationJob) -> None:
    client = _ClientDefaillant()
    with pytest.raises(ChapitreInvalideError):
        produire_chapitre(job_em, 4, client=client)

    socle = socle_verrouille(job_em)
    assert socle is not None
    chapitre = job_em.chapters.get(chapter_number=4)
    prompt, _ = construire_prompt_chapitre(
        chapitre,
        socle=socle,
        variables=_VARIABLES,
        document=type_document(EM),
        motifs_precedents=["motif de test"],
    )
    assert "TENTATIVE PRÉCÉDENTE REFUSÉE" in prompt


@pytest.mark.django_db
def test_apres_trois_echecs_l_etude_passe_en_intervention_requise(
    job_em: GenerationJob,
) -> None:
    marquer_intervention_requise(job_em, 4, ["motif A", "motif B"], 3)

    job_em.refresh_from_db()
    incident = OperationalIncident.objects.filter(job=job_em).order_by("-created_at").first()

    assert job_em.status == JobStatus.INTERVENTION_REQUISE
    assert job_em.status != JobStatus.DONE, "Aucun e-mail ne part sur une étude incomplète."
    assert incident is not None
    assert incident.details["chapitre"] == 4
    assert incident.details["tentatives"] == 3


def test_la_temporisation_est_exponentielle() -> None:
    assert temporisation(1) == 30
    assert temporisation(2) == 120
    assert temporisation(3) > temporisation(2)


# ── Suivi d'avancement ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_les_chapitres_restants_suivent_la_configuration(job_em: GenerationJob) -> None:
    attendus = type_document(EM).nombre_de_chapitres()
    assert len(chapitres_a_produire(job_em)) == attendus
    assert etude_complete(job_em) is False

    produire_chapitre(job_em, 0, client=StubClaudeClient())
    assert len(chapitres_a_produire(job_em)) == attendus - 1


@pytest.mark.django_db
def test_un_chapitre_de_l_ancien_moteur_ne_compte_pas_comme_fait(
    job_em: GenerationJob,
) -> None:
    """Un chapitre DONE sans payload vient de l'ancien moteur : il reste à refaire."""
    job_em.chapters.filter(chapter_number=4).update(
        status=ChapterStatus.DONE, content="texte libre", payload={}
    )
    assert 4 in chapitres_a_produire(job_em)


# ── Le bouchon ne contourne pas le validateur ────────────────────────────────


def test_le_bouchon_ne_declare_que_des_donnees_presentes_dans_le_prompt() -> None:
    prompt = (
        "SOCLE VERROUILLÉ — test\n"
        "- `tam` = 4.0 MdEUR (2025, national, observee)\n"
        "- `sam` = 0.25 MdEUR (2025, national, observee)\n"
        "\nCHAPITRE À RÉDIGER : 7 — Tendances\n"
    )
    charge = chapitre_de_demonstration(prompt)
    assert charge["chapitre"] == 7
    assert charge["donnees_utilisees"] == ["tam", "sam"]
    assert _valider(copy.deepcopy(charge), numero=7) == []

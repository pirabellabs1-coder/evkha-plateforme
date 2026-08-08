"""Lot 1 — socle de données verrouillé.

Deux exigences guident ces tests, tirées du CLAUDE.md du dépôt :

- règle 1 : « un contrôle qui n'a rien à comparer est un ÉCHEC, jamais un
  succès ». Chaque validateur doit donc REFUSER quand la donnée manque, et non
  passer en silence.
- règle 6 : « écrivez la contre-épreuve ». Pour chaque rejet vérifié, un cas
  valide vérifie que le contrôle ne bloque pas ce qui est correct.
"""
from __future__ import annotations

import copy
import json
from datetime import date
from typing import Any

import pytest
from django.test import Client

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.models import ChapterStatus, GenerationJob, SocleDonnees, SocleStatut
from generation.services import bootstrap_generation_job
from generation.socle import (
    MAX_TENTATIVES,
    Socle,
    SocleGenerationError,
    etablir_socle,
    identifiants_obligatoires,
    identifiants_pour,
    produire_socle,
    regenerer_socle,
    revalider_socle,
    schema_outil,
    socle_actif,
    socle_verrouille,
    valider_socle,
)
from generation.socle.prompt import construire_prompt_socle
from generation.socle.stub import socle_de_demonstration
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StructuredResult, StubClaudeClient
from orders.models import Order

EM = DeliverableType.MARKET_STUDY

_VARIABLES = {
    "SECTEUR": "joaillerie de créateurs",
    "PAYS": "France",
    "ZONE": "Paris",
    "PROJET": "maison d'édition joaillière",
}


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def charge_valide() -> dict[str, Any]:
    """Socle recevable, produit par le bouchon à partir du référentiel réel."""
    prompt = construire_prompt_socle(deliverable_type=EM, variables=_VARIABLES)
    return socle_de_demonstration(prompt)


@pytest.fixture
def job_em(db: object) -> GenerationJob:
    offer = Offer.objects.create(
        name="Étude de marché", slug="em-socle", deliverable_type=EM
    )
    customer = Customer.objects.create(email="socle@example.com")
    order = Order.objects.create(
        systeme_order_id="order-socle-01", customer=customer, offer=offer
    )
    submission = IntakeSubmission.objects.create(
        order=order, status=IntakeStatus.NORMALIZED, normalized_variables=_VARIABLES
    )
    return bootstrap_generation_job(submission)


def _valider(charge: dict[str, Any]) -> list[str]:
    return valider_socle(Socle.model_validate(charge), EM)


# ── Référentiel ──────────────────────────────────────────────────────────────


def test_le_referentiel_em_est_ferme_et_non_vide() -> None:
    identifiants = identifiants_pour(EM)
    assert identifiants, "Le référentiel de l'étude de marché est vide."
    assert identifiants_obligatoires(EM) <= identifiants


def test_les_livrables_non_couverts_ne_produisent_aucun_identifiant() -> None:
    """Un type inconnu ne produit rien : pas de faux positif.

    Ce test citait le business plan — hors périmètre du lot 1, couvert depuis
    la bascule du 06/08/2026. La PROPRIÉTÉ qu'il verrouille n'a pas changé :
    un livrable sans référentiel rend l'ensemble vide, jamais un référentiel
    d'emprunt. Elle se vérifie désormais sur un type qui n'existera jamais.
    """
    assert identifiants_pour("livrable_inconnu") == frozenset()


def test_le_schema_outil_enumere_les_identifiants_autorises() -> None:
    """L'API doit refuser un identifiant inconnu avant même notre validateur."""
    schema = schema_outil(EM)
    enum = schema["$defs"]["DonneeSocle"]["properties"]["id"]["enum"]
    assert set(enum) == set(identifiants_pour(EM))
    assert "deliverable_type" not in schema.get("properties", {})


# ── Contre-épreuve : le cas correct passe ────────────────────────────────────


def test_un_socle_conforme_est_accepte(charge_valide: dict[str, Any]) -> None:
    assert _valider(charge_valide) == []


# ── Rejets ───────────────────────────────────────────────────────────────────


def test_rejette_un_identifiant_hors_referentiel(charge_valide: dict[str, Any]) -> None:
    charge = copy.deepcopy(charge_valide)
    charge["donnees"][0]["id"] = "marche_martien_taille"
    motifs = _valider(charge)
    assert any("hors référentiel" in motif for motif in motifs)


def test_rejette_un_identifiant_en_double(charge_valide: dict[str, Any]) -> None:
    charge = copy.deepcopy(charge_valide)
    charge["donnees"].append(copy.deepcopy(charge["donnees"][0]))
    motifs = _valider(charge)
    assert any("plusieurs fois" in motif for motif in motifs)


def test_rejette_un_socle_ampute_dune_donnee_obligatoire(charge_valide: dict[str, Any]) -> None:
    charge = copy.deepcopy(charge_valide)
    charge["donnees"] = [d for d in charge["donnees"] if d["id"] != "tam"]
    motifs = _valider(charge)
    assert any("`tam` est obligatoire" in motif for motif in motifs)


def test_rejette_un_perimetre_non_conforme(charge_valide: dict[str, Any]) -> None:
    """Le cœur du défaut actuel : une valeur continentale annoncée mondiale."""
    charge = copy.deepcopy(charge_valide)
    for donnee in charge["donnees"]:
        if donnee["id"] == "marche_continental_taille":
            donnee["perimetre"] = "monde"
    motifs = _valider(charge)
    assert any("périmètre" in motif for motif in motifs)


def test_rejette_une_unite_incompatible(charge_valide: dict[str, Any]) -> None:
    """Un taux de croissance en milliards d'euros n'a aucun sens."""
    charge = copy.deepcopy(charge_valide)
    for donnee in charge["donnees"]:
        if donnee["id"] == "marche_mondial_croissance":
            donnee["unite"] = "MdEUR"
    motifs = _valider(charge)
    assert any("incompatible" in motif for motif in motifs)


def test_rejette_une_donnee_observee_sans_source(charge_valide: dict[str, Any]) -> None:
    charge = copy.deepcopy(charge_valide)
    charge["donnees"][0]["source"] = ""
    with pytest.raises(Exception) as capture:
        Socle.model_validate(charge)
    assert "source" in str(capture.value)


def test_rejette_une_filiation_qui_pointe_dans_le_vide(charge_valide: dict[str, Any]) -> None:
    charge = copy.deepcopy(charge_valide)
    charge["donnees"][0]["derivee_de"] = ["identifiant_inexistant"]
    motifs = _valider(charge)
    assert any("absent du socle" in motif for motif in motifs)


def test_accepte_une_filiation_valide(charge_valide: dict[str, Any]) -> None:
    """Contre-épreuve : un chiffre dérivé correctement déclaré passe."""
    charge = copy.deepcopy(charge_valide)
    presents = {d["id"] for d in charge["donnees"]}
    assert {"som", "panier_moyen"} <= presents
    for donnee in charge["donnees"]:
        if donnee["id"] == "som":
            donnee["derivee_de"] = ["panier_moyen"]
    assert _valider(charge) == []


def test_rejette_un_emboitement_tam_sam_som_rompu(charge_valide: dict[str, Any]) -> None:
    """Défaut réellement constaté sur le run 010e3bf2."""
    charge = copy.deepcopy(charge_valide)
    for donnee in charge["donnees"]:
        if donnee["id"] == "som":
            donnee["valeur"] = 99.0  # SOM > TAM
    motifs = _valider(charge)
    assert any("emboîtement" in motif.lower() for motif in motifs)


def test_rejette_un_marche_continental_egal_au_mondial(charge_valide: dict[str, Any]) -> None:
    charge = copy.deepcopy(charge_valide)
    mondial = next(d for d in charge["donnees"] if d["id"] == "marche_mondial_taille")
    for donnee in charge["donnees"]:
        if donnee["id"] == "marche_continental_taille":
            donnee["valeur"] = mondial["valeur"]
            donnee["unite"] = mondial["unite"]
    motifs = _valider(charge)
    assert any("identique" in motif for motif in motifs)


def test_rejette_un_continent_plus_grand_que_le_monde(charge_valide: dict[str, Any]) -> None:
    charge = copy.deepcopy(charge_valide)
    for donnee in charge["donnees"]:
        if donnee["id"] == "marche_continental_taille":
            donnee["valeur"] = 10_000.0
    motifs = _valider(charge)
    assert any("plus grand que le monde" in motif for motif in motifs)


# ── Constructeur : tentatives et échec ───────────────────────────────────────


def test_le_bouchon_produit_un_socle_recevable_du_premier_coup() -> None:
    socle, consommation, tentatives = produire_socle(
        client=StubClaudeClient(), deliverable_type=EM, variables=_VARIABLES
    )
    assert tentatives == 1
    assert socle.donnee("tam") is not None
    assert consommation["output_tokens"] > 0


class _ClientTetu:
    """Rend toujours une charge invalide : vérifie qu'on n'insiste pas sans fin."""

    def __init__(self) -> None:
        self.appels = 0

    def complete_structured(self, **kwargs: object) -> StructuredResult:
        self.appels += 1
        return StructuredResult(
            payload={"secteur": "x"},  # zone et date_socle manquantes
            input_tokens=10,
            output_tokens=10,
            model="stub",
        )


def test_abandonne_apres_le_nombre_maximum_de_tentatives() -> None:
    client = _ClientTetu()
    with pytest.raises(SocleGenerationError) as capture:
        produire_socle(client=client, deliverable_type=EM, variables=_VARIABLES)
    assert client.appels == MAX_TENTATIVES
    assert capture.value.motifs


class _ClientQuiSeCorrige:
    """Échoue une fois, puis produit un socle valide. Vérifie la reprise."""

    def __init__(self) -> None:
        self.appels = 0
        self.motifs_recus: list[str] = []

    def complete_structured(self, **kwargs: object) -> StructuredResult:
        self.appels += 1
        prompt = str(kwargs["prompt"])
        if self.appels == 1:
            return StructuredResult(
                payload={"secteur": "x"}, input_tokens=5, output_tokens=5, model="stub"
            )
        assert "TENTATIVE PRÉCÉDENTE REFUSÉE" in prompt, (
            "La deuxième tentative doit recevoir les motifs du refus précédent."
        )
        self.motifs_recus.append(prompt)
        return StructuredResult(
            payload=socle_de_demonstration(prompt),
            input_tokens=5,
            output_tokens=5,
            model="stub",
        )


def test_la_seconde_tentative_recoit_les_motifs_du_refus() -> None:
    client = _ClientQuiSeCorrige()
    socle, _consommation, tentatives = produire_socle(
        client=client, deliverable_type=EM, variables=_VARIABLES
    )
    assert tentatives == 2
    assert socle.donnee("sam") is not None


def test_un_livrable_sans_referentiel_est_refuse_sans_appel_api() -> None:
    """Le refus vient AVANT l'appel : un type non couvert ne coûte rien.

    Citait le business plan avant sa bascule du 06/08/2026 ; la propriété se
    vérifie sur un type inconnu, qui restera non couvert pour toujours.
    """
    client = _ClientTetu()
    with pytest.raises(SocleGenerationError):
        produire_socle(
            client=client,
            deliverable_type="livrable_inconnu",
            variables=_VARIABLES,
        )
    assert client.appels == 0, "Aucun appel ne doit être payé pour un livrable non couvert."


# ── Persistance et cycle de vie ──────────────────────────────────────────────


@pytest.mark.django_db
def test_etablir_socle_persiste_et_verrouille(job_em: GenerationJob) -> None:
    enregistrement = etablir_socle(
        job_em, client=StubClaudeClient(), variables=_VARIABLES
    )
    assert enregistrement.statut == SocleStatut.VALIDE
    assert enregistrement.version == 1
    assert enregistrement.valide_at is not None
    assert enregistrement.contenu["donnees"]
    assert socle_verrouille(job_em) is not None


@pytest.mark.django_db
def test_etablir_socle_est_idempotent_et_ne_rappelle_pas_le_modele(
    job_em: GenerationJob,
) -> None:
    """Exigence du cahier des charges : jamais recalculé pendant la génération."""
    etablir_socle(job_em, client=StubClaudeClient(), variables=_VARIABLES)
    client = _ClientTetu()
    encore = etablir_socle(job_em, client=client, variables=_VARIABLES)
    assert client.appels == 0
    assert encore.version == 1


@pytest.mark.django_db
def test_le_cout_du_socle_est_impute_au_job(job_em: GenerationJob) -> None:
    avant = job_em.total_cost_eur
    enregistrement = etablir_socle(
        job_em, client=StubClaudeClient(), variables=_VARIABLES
    )
    job_em.refresh_from_db()
    assert enregistrement.cost_eur > 0
    assert job_em.total_cost_eur == avant + enregistrement.cost_eur


@pytest.mark.django_db
def test_regenerer_le_socle_invalide_tous_les_chapitres(job_em: GenerationJob) -> None:
    etablir_socle(job_em, client=StubClaudeClient(), variables=_VARIABLES)
    job_em.chapters.update(status=ChapterStatus.DONE, content="contenu écrit")

    remis = regenerer_socle(job_em)

    assert remis == job_em.chapters.count()
    assert job_em.chapters.filter(status=ChapterStatus.PENDING).count() == remis
    assert job_em.chapters.exclude(content="").count() == 0
    assert SocleDonnees.objects.get(job=job_em).statut == SocleStatut.INVALIDE
    assert socle_verrouille(job_em) is None


@pytest.mark.django_db
def test_une_correction_manuelle_fautive_est_refusee(job_em: GenerationJob) -> None:
    """Une correction humaine n'échappe pas aux contrôles du référentiel."""
    enregistrement = etablir_socle(
        job_em, client=StubClaudeClient(), variables=_VARIABLES
    )
    contenu = copy.deepcopy(enregistrement.contenu)
    contenu["donnees"] = [d for d in contenu["donnees"] if d["id"] != "sam"]
    enregistrement.contenu = contenu
    enregistrement.save(update_fields=["contenu"])

    motifs = revalider_socle(enregistrement)

    enregistrement.refresh_from_db()
    assert motifs, "Un socle amputé d'une donnée obligatoire doit être refusé."
    assert enregistrement.statut == SocleStatut.INVALIDE
    assert socle_verrouille(job_em) is None


@pytest.mark.django_db
def test_une_correction_manuelle_valide_est_acceptee(job_em: GenerationJob) -> None:
    """Contre-épreuve : corriger une valeur sans casser le référentiel passe."""
    enregistrement = etablir_socle(
        job_em, client=StubClaudeClient(), variables=_VARIABLES
    )
    contenu = copy.deepcopy(enregistrement.contenu)
    for donnee in contenu["donnees"]:
        if donnee["id"] == "marche_national_taille":
            donnee["valeur"] = 7.5
            donnee["source"] = "Francéclat, bilan économique 2025"
    enregistrement.contenu = contenu
    enregistrement.save(update_fields=["contenu"])

    assert revalider_socle(enregistrement) == []

    socle = socle_verrouille(job_em)
    assert socle is not None
    donnee = socle.donnee("marche_national_taille")
    assert donnee is not None and donnee.valeur == 7.5


# ── Drapeau de bascule ───────────────────────────────────────────────────────


def test_le_socle_est_desactive_par_defaut() -> None:
    """L'ancien moteur reste seul en service tant que la bascule n'est pas faite."""
    assert socle_actif() is False


@pytest.mark.django_db
def test_le_socle_ne_modifie_pas_le_parcours_existant(job_em: GenerationJob) -> None:
    """Aucun chapitre n'est touché par la seule production du socle."""
    avant = list(job_em.chapters.values_list("chapter_number", "status"))
    etablir_socle(job_em, client=StubClaudeClient(), variables=_VARIABLES)
    assert list(job_em.chapters.values_list("chapter_number", "status")) == avant


def test_la_date_du_socle_est_serialisee_en_iso(charge_valide: dict[str, Any]) -> None:
    socle = Socle.model_validate(charge_valide)
    assert isinstance(socle.date_socle, date)
    assert socle.model_dump(mode="json")["date_socle"] == socle.date_socle.isoformat()


# ── Accès et correction depuis l'admin Django ────────────────────────────────
# Le cahier des charges exige que la cliente puisse consulter et rectifier le
# socle avant que l'étude ne se construise dessus. Ces tests vérifient que le
# chemin existe réellement, pas seulement que le modèle est enregistré.


@pytest.mark.django_db
def test_le_socle_est_consultable_dans_l_admin(
    job_em: GenerationJob, client: Client
) -> None:
    from django.contrib.auth.models import User

    enregistrement = etablir_socle(
        job_em, client=StubClaudeClient(), variables=_VARIABLES
    )
    administrateur = User.objects.create_superuser("admin-test", "a@b.c", "x")
    client.force_login(administrateur)

    liste = client.get("/admin/generation/socledonnees/")
    fiche = client.get(f"/admin/generation/socledonnees/{enregistrement.id}/change/")

    assert liste.status_code == 200
    assert fiche.status_code == 200
    assert b"contenu" in fiche.content


@pytest.mark.django_db
def test_une_correction_admin_fautive_est_signalee(
    job_em: GenerationJob, client: Client
) -> None:
    """Enregistrer un socle cassé depuis l'admin doit le passer INVALIDE."""
    from django.contrib.auth.models import User

    enregistrement = etablir_socle(
        job_em, client=StubClaudeClient(), variables=_VARIABLES
    )
    administrateur = User.objects.create_superuser("admin-test2", "a@b.c", "x")
    client.force_login(administrateur)

    casse = copy.deepcopy(enregistrement.contenu)
    casse["donnees"] = [d for d in casse["donnees"] if d["id"] != "tam"]

    reponse = client.post(
        f"/admin/generation/socledonnees/{enregistrement.id}/change/",
        data={
            "job": str(job_em.id),
            "statut": SocleStatut.VALIDE,
            "contenu": json.dumps(casse),
            "corrige_manuellement": "on",
            "_continue": "Enregistrer et continuer",
        },
        follow=True,
    )

    enregistrement.refresh_from_db()
    assert reponse.status_code == 200
    assert enregistrement.statut == SocleStatut.INVALIDE
    assert enregistrement.corrige_manuellement is True
    assert any("tam" in motif for motif in enregistrement.motifs_rejet)

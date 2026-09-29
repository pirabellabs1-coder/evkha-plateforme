"""La bibliothèque garde ses documents un an, et dit la vérité sur leurs fichiers.

## Le constat (capture de l'utilisateur, 29/09/2026)

L'espace d'Evangéline affichait « En préparation » sur des études livrées en
août — et sur une stratégie annulée. Rien n'était en préparation : les
fichiers avaient été supprimés au bout de sept jours, durée de conservation
des livrables. L'écran n'avait qu'un mot pour « aucun fichier ».

## Ce que ce fichier verrouille

1. l'état des fichiers vient du serveur, en cinq cas distincts
   (`etat_des_fichiers`) : disponibles, en préparation, mise en forme,
   supprimés le …, aucun ;
2. la conservation des livrables est de douze mois (décision de
   l'utilisateur) : défaut du modèle, réglage par défaut, et les deux
   migrations — offres à l'ancienne valeur, fichiers encore présents ;
3. le lien de l'espace est signé à chaque lecture pour le temps qui reste au
   fichier, plafonné à sept jours : un document prolongé ne mène pas à un
   lien mort au huitième jour, et un lien copié n'expose pas le fichier un an ;
4. un fichier échu, pas encore purgé, n'est plus proposé et se dit supprimé.

Contre-épreuves (règle 6) : une offre réglée à la main garde sa durée ; un
fichier déjà supprimé ne revient pas ; une échéance plus lointaine n'est pas
raccourcie.
"""
from __future__ import annotations

import importlib
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from django.apps import apps
from django.test import Client, override_settings
from django.utils import timezone

from catalog.models import DeliverableType, Offer
from documents.models import ArtifactKind, ArtifactStatus, DocumentArtifact
from evkha import signatures
from generation.models import GenerationJob, JobStatus
from orders.models import Order
from organisations import suivi
from tests.test_lot4_espace_client import Agence, charge

pytestmark = pytest.mark.django_db


@pytest.fixture
def agence() -> Agence:
    return Agence("Éclore Conseil", "biblio@exemple.fr")


def _job(agence: Agence, statut: str, suffixe: str) -> GenerationJob:
    offre, _ = Offer.objects.get_or_create(
        slug="bp-biblio",
        defaults={"name": "Business plan", "deliverable_type": DeliverableType.BUSINESS_PLAN},
    )
    commande = Order.objects.create(
        systeme_order_id=f"cmd-biblio-{suffixe}",
        customer=agence.contact,
        offer=offre,
        organisation=agence.organisation,
    )
    return GenerationJob.objects.create(
        order=commande, deliverable_type=DeliverableType.BUSINESS_PLAN, status=statut,
    )


def _fichier(job: GenerationJob, kind: str, statut: str, *, dans_jours: int) -> DocumentArtifact:
    return DocumentArtifact.objects.create(
        job=job,
        kind=kind,
        status=statut,
        storage_key=f"livrables/{job.id}/etude.{kind}" if statut == ArtifactStatus.READY else "",
        download_url=(
            f"https://api.exemple/media/livrables/{job.id}/etude.{kind}?s=ancien"
            if statut == ArtifactStatus.READY else ""
        ),
        expires_at=timezone.now() + timedelta(days=dans_jours),
    )


# ── 1. L'état des fichiers, en cinq cas ──────────────────────────────────────


def test_des_fichiers_presents_sont_disponibles(agence: Agence) -> None:
    job = _job(agence, JobStatus.DONE, "a")
    _fichier(job, ArtifactKind.PDF, ArtifactStatus.READY, dans_jours=300)
    assert suivi.etat_des_fichiers(job)["etat"] == "disponibles"


def test_une_etude_en_production_est_en_preparation(agence: Agence) -> None:
    job = _job(agence, JobStatus.RUNNING, "b")
    assert suivi.etat_des_fichiers(job) == {"etat": "en_preparation", "supprimes_le": None}


def test_une_etude_annulee_n_est_pas_en_preparation(agence: Agence) -> None:
    """Le test qui échoue sur le code d'avant : la ligne annulée disait « En préparation »."""
    for statut in (JobStatus.CANCELLED, JobStatus.FAILED):
        job = _job(agence, statut, f"c-{statut}")
        assert suivi.etat_des_fichiers(job)["etat"] == "aucun"


def test_des_fichiers_supprimes_le_disent_avec_leur_date(agence: Agence) -> None:
    job = _job(agence, JobStatus.DONE, "d")
    docx = _fichier(job, ArtifactKind.DOCX, ArtifactStatus.EXPIRED, dans_jours=-35)
    _fichier(job, ArtifactKind.PDF, ArtifactStatus.EXPIRED, dans_jours=-36)

    etat = suivi.etat_des_fichiers(job)

    assert etat["etat"] == "supprimes"
    assert docx.expires_at is not None
    assert etat["supprimes_le"] == docx.expires_at.isoformat()


def test_une_etude_redigee_sans_fichier_est_en_mise_en_forme(agence: Agence) -> None:
    job = _job(agence, JobStatus.DONE, "e")
    assert suivi.etat_des_fichiers(job)["etat"] == "mise_en_forme"


def test_la_bibliotheque_et_le_suivi_portent_l_etat(agence: Agence) -> None:
    job = _job(agence, JobStatus.DONE, "f")
    _fichier(job, ArtifactKind.PDF, ArtifactStatus.EXPIRED, dans_jours=-10)

    with override_settings(EVKHA_DEFAULT_RETENTION_DAYS=365):
        corps = charge(Client().get("/api/espace/livrables/", headers=agence.entetes))

    ligne = next(item for item in corps["livrables"] if item["id"] == str(job.id))
    assert ligne["fichiers_etat"]["etat"] == "supprimes"
    assert corps["conservation_jours"] == 365
    assert suivi.en_dict(job)["fichiers_etat"]["etat"] == "supprimes"


# ── 2. Douze mois ────────────────────────────────────────────────────────────


def test_une_offre_neuve_garde_ses_livrables_un_an() -> None:
    assert Offer().retention_days == 365


def test_la_migration_passe_les_offres_a_l_ancienne_valeur() -> None:
    ancienne = Offer.objects.create(
        name="EM", slug="em-7", deliverable_type=DeliverableType.MARKET_STUDY, retention_days=7,
    )
    choisie = Offer.objects.create(
        name="EC", slug="ec-30", deliverable_type=DeliverableType.COMPETITOR_STUDY,
        retention_days=30,
    )
    migration = importlib.import_module(
        "catalog.migrations.0012_conservation_des_livrables_douze_mois"
    )

    migration.douze_mois(apps, None)

    ancienne.refresh_from_db()
    choisie.refresh_from_db()
    assert ancienne.retention_days == 365
    assert choisie.retention_days == 30, "un réglage commercial n'est pas un reste"


def test_la_migration_prolonge_les_fichiers_encore_presents(agence: Agence) -> None:
    job = _job(agence, JobStatus.DONE, "g")
    present = _fichier(job, ArtifactKind.PDF, ArtifactStatus.READY, dans_jours=2)
    deja_loin = _fichier(job, ArtifactKind.DOCX, ArtifactStatus.READY, dans_jours=500)
    supprime = _fichier(job, ArtifactKind.LINK, ArtifactStatus.EXPIRED, dans_jours=-3)
    avant_loin, avant_supprime = deja_loin.expires_at, supprime.expires_at
    migration = importlib.import_module(
        "documents.migrations.0002_prolonger_les_livrables_encore_presents"
    )

    migration.prolonger(apps, None)

    for artefact in (present, deja_loin, supprime):
        artefact.refresh_from_db()
    assert present.expires_at == present.created_at + timedelta(days=365)
    assert deja_loin.expires_at == avant_loin
    assert supprime.expires_at == avant_supprime
    assert supprime.status == ArtifactStatus.EXPIRED


# ── 3. Un lien frais, valable autant que le fichier ──────────────────────────


def _duree_signee(url: str) -> int:
    jeton = parse_qs(urlparse(url).query)[signatures.PARAMETRE][0]
    tete = jeton.split(":")[0]
    assert tete.startswith(signatures.MARQUEUR_DUREE), jeton
    return int(tete[1:])


def test_le_lien_de_l_espace_est_frais_et_plafonne(agence: Agence) -> None:
    """Le lien stocké datait de la production ; celui de l'espace est signé à la lecture."""
    job = _job(agence, JobStatus.DONE, "h")
    _fichier(job, ArtifactKind.PDF, ArtifactStatus.READY, dans_jours=300)

    (fichier,) = suivi.fichiers_du_client(job)

    assert "s=ancien" not in fichier["url"]
    assert _duree_signee(fichier["url"]) == suivi.DUREE_LIEN_ESPACE_S
    chemin = urlparse(fichier["url"]).path.removeprefix("/media/")
    jeton = parse_qs(urlparse(fichier["url"]).query)[signatures.PARAMETRE][0]
    assert signatures.signature_valable(chemin, jeton)


def test_le_lien_ne_survit_pas_au_fichier(agence: Agence) -> None:
    job = _job(agence, JobStatus.DONE, "k")
    _fichier(job, ArtifactKind.PDF, ArtifactStatus.READY, dans_jours=2)

    (fichier,) = suivi.fichiers_du_client(job)

    assert 47 * 3600 < _duree_signee(fichier["url"]) <= 48 * 3600


def test_un_fichier_echu_pas_encore_purge_n_est_plus_propose(agence: Agence) -> None:
    job = _job(agence, JobStatus.DONE, "l")
    echu = _fichier(job, ArtifactKind.PDF, ArtifactStatus.READY, dans_jours=-1)

    assert suivi.fichiers_du_client(job) == []
    etat = suivi.etat_des_fichiers(job)
    assert etat["etat"] == "supprimes"
    assert echu.expires_at is not None
    assert etat["supprimes_le"] == echu.expires_at.isoformat()


def test_la_fixture_des_offres_suit_le_modele() -> None:
    """`loaddata initial_offers` après `migrate` remettait les offres à sept jours."""
    import json
    from pathlib import Path as Chemin

    import catalog

    fixture = Chemin(catalog.__file__).parent / "fixtures" / "initial_offers.json"
    defaut = Offer._meta.get_field("retention_days").default
    lignes = json.loads(fixture.read_text(encoding="utf-8"))
    offres = [o for o in lignes if o["model"] == "catalog.offer"]
    assert offres
    assert {o["fields"]["retention_days"] for o in offres} == {defaut}


def test_un_fichier_sans_cle_garde_son_lien(agence: Agence) -> None:
    job = _job(agence, JobStatus.DONE, "i")
    artefact = _fichier(job, ArtifactKind.PDF, ArtifactStatus.READY, dans_jours=10)
    DocumentArtifact.objects.filter(pk=artefact.pk).update(storage_key="")

    (fichier,) = suivi.fichiers_du_client(job)

    assert fichier["url"] == artefact.download_url

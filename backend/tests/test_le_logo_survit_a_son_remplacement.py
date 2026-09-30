"""Le logo d'un document survit au remplacement du logo dans « Ma marque ».

## Le défaut, mesuré

Business plan ÉCLORE `28a257bf`, livré le 30/09/2026 : ni la couverture ni la
dernière page du PDF ne portent d'image. L'utilisateur : « ça fait plusieurs
fois ». La commande garde une COPIE du chemin du logo, prise le jour où elle
est passée (`organisations.commandes`), et depuis le 08/08/2026 remplacer son
logo EFFACE l'ancien fichier du disque (`purge._effacer_le_fichier`). Le rendu
retombait alors, en silence, sur une couverture sans logo.

## Ce que ce fichier verrouille

1. quand le fichier de la commande a disparu, c'est le logo ACTUEL de
   l'organisation qui s'imprime (`rendering.logo_du_job`) ;
2. un logo attendu mais introuvable devient un incident (règle 1) ;
3. la console dit quel logo est retenu, et si chacun se lit (`jobs/<id>/logo/`).

Contre-épreuves (règle 6) : le logo de la commande, s'il existe, reste celui
de la commande ; une URL externe n'est pas testée sur le disque ; sans aucun
logo lisible, rien n'est inventé ; la route exige le jeton.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from django.core.files.base import ContentFile
from django.test import override_settings

from catalog.models import DeliverableType, Offer
from generation.models import GenerationJob, JobStatus
from generation.rendering import extract_branding, logo_du_job
from intake.models import IntakeStatus, IntakeSubmission
from monitoring.models import OperationalIncident
from orders.models import Order
from organisations.models import CategorieFichier, PieceJointe
from tests.test_lot4_espace_client import Agence

pytestmark = pytest.mark.django_db

#: Un PNG que `logo.format_image` reconnaît à sa signature.
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture(autouse=True)
def _medias(tmp_path: Path) -> Any:
    with override_settings(MEDIA_ROOT=tmp_path):
        yield


@pytest.fixture
def agence() -> Agence:
    return Agence("Éclore Conseil", "logo-remplace@exemple.fr")


def _deposer_un_logo(agence: Agence, nom: str) -> PieceJointe:
    """Ce que fait `vues_espace.deposer_piece_jointe` pour un logo : remplacer."""
    organisation = agence.organisation
    piece = PieceJointe(
        organisation=organisation, categorie=CategorieFichier.LOGO, nom_original=nom,
        type_mime="image/png", taille_octets=len(PNG), depose_par=agence.contact,
    )
    piece.fichier.save(nom, ContentFile(PNG), save=False)
    piece.save()
    organisation.pieces_jointes.filter(categorie=CategorieFichier.LOGO).exclude(
        pk=piece.pk
    ).delete()
    organisation.logo_url = piece.fichier.url
    organisation.save(update_fields=["logo_url", "updated_at"])
    return piece


def _commande(agence: Agence, logo_url: str) -> GenerationJob:
    """Une commande de l'espace : elle COPIE le chemin du logo du jour."""
    offre, _ = Offer.objects.get_or_create(
        slug="bp-logo", defaults={"name": "BP", "deliverable_type": DeliverableType.BUSINESS_PLAN},
    )
    commande = Order.objects.create(
        systeme_order_id=f"espace-logo-{Order.objects.count()}", customer=agence.contact,
        offer=offre, organisation=agence.organisation,
    )
    IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED,
        normalized_variables={"LOGO_URL": logo_url, "NOM_ENTREPRISE": "Éclore Conseil"},
    )
    return GenerationJob.objects.create(
        order=commande, deliverable_type=DeliverableType.BUSINESS_PLAN, status=JobStatus.DONE,
    )


def test_un_logo_remplace_apres_la_commande_s_imprime_quand_meme(agence: Agence) -> None:
    """Le parcours du 30/09/2026 : commande, puis logo remplacé (l'ancien fichier part)."""
    ancien = _deposer_un_logo(agence, "logo-v1.png")
    job = _commande(agence, ancien.fichier.url)
    nouveau = _deposer_un_logo(agence, "logo-v2.png")

    assert not Path(ancien.fichier.path).exists(), "le remplacement efface l'ancien fichier"
    assert extract_branding(job).logo_url == nouveau.fichier.url
    assert logo_du_job(job, ancien.fichier.url)[1] == "organisation"


def test_le_logo_de_la_commande_reste_le_sien_s_il_existe(agence: Agence) -> None:
    """Contre-épreuve : pas de repli quand le fichier de la commande se lit."""
    logo = _deposer_un_logo(agence, "logo.png")
    job = _commande(agence, logo.fichier.url)

    assert extract_branding(job).logo_url == logo.fichier.url
    assert logo_du_job(job, logo.fichier.url)[1] == "commande"


def test_une_url_externe_n_est_pas_testee_sur_le_disque(
    agence: Agence, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contre-épreuve : un lien de l'ancien formulaire se télécharge au rendu, pas ici."""
    from generation import rendering

    def _interdit(_: str) -> bool:
        raise AssertionError("aucun accès disque ni réseau pour une URL externe")

    monkeypatch.setattr(rendering, "_fichier_local_lisible", _interdit)
    job = _commande(agence, "https://exemple.fr/logo.png")

    assert extract_branding(job).logo_url == "https://exemple.fr/logo.png"


def test_sans_aucun_logo_lisible_rien_n_est_invente(agence: Agence) -> None:
    job = _commande(agence, "/media/pieces-jointes/disparu/logo.png")

    assert logo_du_job(job, "/media/pieces-jointes/disparu/logo.png") == (
        "/media/pieces-jointes/disparu/logo.png", "commande",
    )
    assert logo_du_job(job, "") == ("", "")


def test_un_logo_introuvable_devient_un_incident(agence: Agence) -> None:
    from documents.livrable_word import _signaler_le_logo_introuvable

    job = _commande(agence, "/media/pieces-jointes/disparu/logo.png")

    _signaler_le_logo_introuvable(job, "")
    assert not OperationalIncident.objects.filter(job=job).exists(), "rien d'attendu, rien à dire"

    _signaler_le_logo_introuvable(job, "/media/pieces-jointes/disparu/logo.png")
    incident = OperationalIncident.objects.get(job=job, title__startswith="Logo introuvable")
    assert "redéposer" in incident.details["consigne"]


def test_la_console_dit_quel_logo_est_retenu(client_admin: Any, agence: Agence) -> None:
    ancien = _deposer_un_logo(agence, "logo-v1.png")
    job = _commande(agence, ancien.fichier.url)
    nouveau = _deposer_un_logo(agence, "logo-v2.png")

    corps = client_admin.get(f"/api/dashboard/jobs/{job.id}/logo/").json()

    assert corps["commande"] == {"reference": ancien.fichier.url, "lisible": False}
    assert corps["organisation"] == {"reference": nouveau.fichier.url, "lisible": True}
    assert corps["retenu"] == {
        "reference": nouveau.fichier.url, "source": "organisation", "lisible": True,
    }


def test_la_route_exige_le_jeton(client: Any, agence: Agence) -> None:
    job = _commande(agence, "")
    assert client.get(f"/api/dashboard/jobs/{job.id}/logo/").status_code in (401, 403)

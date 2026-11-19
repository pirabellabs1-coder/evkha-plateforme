"""Une adresse de logo ne fait signer que le logo de celle qui l'a déposé.

Audit du 19/11/2026. `logo_url` est un champ qu'une charge JSON peut écrire, sur
« Ma marque » comme sur la fiche d'un client, et rien ne regardait sa valeur. Or
l'aperçu de la fiche SIGNE le chemin que le champ porte. Écrire le chemin du
livrable d'une autre cliente dans ce champ, puis relire la fiche, rendait donc
un lien signé — valable — vers ce livrable.

La signature est la seule garde de `/media/` : la donner sur demande, c'est ne
pas en avoir.

Ces tests échouent sur le code d'avant : `logo_apercu` portait une signature
pour n'importe quel chemin.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings

from evkha import signatures
from organisations.models import CategorieFichier, ClientFinal, PieceJointe
from tests.test_lot4_espace_client import Agence

pytestmark = pytest.mark.django_db

#: Un PNG que la validation des logos reconnaît à sa signature.
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe"
    b"\x02\xfe\xa75\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82"
)

CLIENTS = "/api/espace/clients-finaux/"
MARQUE = "/api/espace/marque/"

#: Le livrable d'une AUTRE cliente : `documents.livrable_word` range ses
#: fichiers sous `livrables/<identifiant du dossier>`.
LIVRABLE_D_UNE_AUTRE = "/media/livrables/2f1c9a52-7d1e-4f0e-9d43-0c6f1c1b7a10.docx"


@pytest.fixture(autouse=True)
def _medias(tmp_path: Path) -> Any:
    with override_settings(MEDIA_ROOT=tmp_path):
        yield


@pytest.fixture
def agence() -> Agence:
    return Agence("Cabinet Claire", "claire-logo@exemple.fr")


def _poster(agence: Agence, adresse: str, charge: dict[str, Any]) -> Any:
    return Client().post(
        adresse, data=charge, content_type="application/json", headers=agence.entetes,
    )


# ── Le défaut ───────────────────────────────────────────────────────────────


def test_une_fiche_ne_se_cree_pas_avec_le_chemin_d_un_livrable(agence: Agence) -> None:
    reponse = _poster(
        agence, CLIENTS, {"raison_sociale": "Dibitek", "logo_url": LIVRABLE_D_UNE_AUTRE},
    )

    assert reponse.status_code == 400
    assert reponse.json()["code"] == "logo_invalide"
    assert not ClientFinal.objects.filter(raison_sociale="Dibitek").exists()


def test_ma_marque_ne_prend_pas_le_chemin_d_un_livrable(agence: Agence) -> None:
    reponse = _poster(agence, MARQUE, {"logo_url": LIVRABLE_D_UNE_AUTRE})

    assert reponse.status_code == 400
    agence.organisation.refresh_from_db()
    assert agence.organisation.logo_url == ""


def test_le_logo_d_une_autre_organisation_n_est_pas_le_sien(agence: Agence) -> None:
    """Un vrai logo, déposé — mais par quelqu'un d'autre."""
    autre = Agence("Cabinet Voisin", "voisin-logo@exemple.fr")
    piece = PieceJointe(
        organisation=autre.organisation, categorie=CategorieFichier.LOGO,
        nom_original="voisin.png", type_mime="image/png", taille_octets=len(PNG),
        depose_par=autre.contact,
    )
    piece.fichier.save("voisin.png", ContentFile(PNG), save=False)
    piece.save()

    reponse = _poster(
        agence, CLIENTS, {"raison_sociale": "Dibitek", "logo_url": piece.fichier.url},
    )

    assert reponse.status_code == 400


def test_une_valeur_deja_en_base_n_est_pas_signee_pour_autant(agence: Agence) -> None:
    """La garde est aussi là où la signature se donne : une fiche écrite AVANT
    que l'écriture soit gardée ne rend pas de lien."""
    ClientFinal.objects.create(
        organisation=agence.organisation, raison_sociale="Ancienne fiche",
        logo_url=LIVRABLE_D_UNE_AUTRE,
    )

    fiches = Client().get(CLIENTS, headers=agence.entetes).json()["clients"]

    assert [f["logo_apercu"] for f in fiches] == [""]


# ── Les contre-épreuves ─────────────────────────────────────────────────────


def test_le_logo_depose_sur_la_fiche_a_son_apercu_signe(agence: Agence) -> None:
    fiche = _poster(agence, CLIENTS, {"raison_sociale": "Dibitek"}).json()

    reponse = Client().post(
        f"{CLIENTS}{fiche['id']}/logo/",
        data={"fichier": SimpleUploadedFile("dibitek.png", PNG, content_type="image/png")},
        headers=agence.entetes,
    )

    assert reponse.status_code == 201, reponse.content
    apercu = reponse.json()["logo_apercu"]
    piece = PieceJointe.objects.get(categorie=CategorieFichier.LOGO_CLIENT)
    adresse = urlsplit(apercu)
    assert adresse.path == f"/media/{quote(piece.fichier.name)}"
    presentee = parse_qs(adresse.query)[signatures.PARAMETRE][0]
    assert signatures.signature_valable(piece.fichier.name, presentee)


def test_une_adresse_externe_reste_admise(agence: Agence) -> None:
    """L'ancien formulaire donnait une adresse complète ; elle n'est pas signée,
    elle est rendue telle quelle."""
    reponse = _poster(
        agence, CLIENTS,
        {"raison_sociale": "Dibitek", "logo_url": "https://exemple.test/logo.png"},
    )

    assert reponse.status_code == 201
    assert reponse.json()["logo_apercu"] == "https://exemple.test/logo.png"


def test_renvoyer_la_marque_telle_qu_on_l_a_lue_n_est_pas_refuse(agence: Agence) -> None:
    """Un écran qui relit la marque puis la renvoie entière ne doit pas échouer
    sur le logo qu'il n'a pas touché."""
    piece = PieceJointe(
        organisation=agence.organisation, categorie=CategorieFichier.LOGO,
        nom_original="claire.png", type_mime="image/png", taille_octets=len(PNG),
        depose_par=agence.contact,
    )
    piece.fichier.save("claire.png", ContentFile(PNG), save=False)
    piece.save()
    agence.organisation.logo_url = piece.fichier.url
    agence.organisation.save(update_fields=["logo_url", "updated_at"])
    lue = Client().get(MARQUE, headers=agence.entetes).json()

    reponse = _poster(agence, MARQUE, {**lue, "ville": "Lille"})

    assert reponse.status_code == 200, reponse.content
    assert reponse.json()["logo_url"] == piece.fichier.url

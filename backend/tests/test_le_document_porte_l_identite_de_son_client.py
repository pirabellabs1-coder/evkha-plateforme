"""Un document commandé depuis une fiche porte l'identité de CE client.

Stratégie `d319a9e5` (13/11/2026), projet « Dibitek Forge » : « le nom d'un
autre client, à six endroits : SUNTZU KOUMISITH POLY GROUPES FRANCE […] tout
comme son logo et les couleurs de l'autre client ». Le nom, le logo et les
couleurs venaient de « Ma marque », où restait la charte du client précédent ;
la fiche du client existait, et rien ne la lisait.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from generation.rendering import extract_branding, logo_du_job
from organisations.models import CategorieFichier, ClientFinal, Projet
from tests.test_lot4_commander import SAISIE_EM, Abonne
from tests.test_un_projet_par_client import _commande

pytestmark = pytest.mark.django_db

#: Un PNG d'un pixel, valide : la garde lit les OCTETS, pas l'extension.
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\xf0\x1f\x00"
    b"\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def abonnee() -> Abonne:
    """Son « Ma marque » porte encore la charte d'un AUTRE client."""
    abonnee = Abonne("SUNTZU KOUMISITH POLY GROUPES FRANCE", "identite@example.com")
    organisation = abonnee.organisation
    organisation.logo_url = "/media/pieces-jointes/x/logo-suntzu.jpeg"
    organisation.couleur_principale = "#1B3A8C"
    organisation.couleur_secondaire = "#D7262E"
    organisation.save()
    return abonnee


def _projet(abonnee: Abonne, **charte: str) -> Projet:
    client = ClientFinal.objects.create(
        organisation=abonnee.organisation, raison_sociale="Dibitek", **charte
    )
    return Projet.objects.create(client=client, nom="Dibitek Forge")


def test_le_nom_du_document_est_celui_du_client(abonnee: Abonne) -> None:
    job = _commande(abonnee, "market_study", SAISIE_EM, _projet(abonnee))

    variables = job.order.intake_submission.normalized_variables

    assert variables["NOM_ENTREPRISE"] == "Dibitek"
    assert "SUNTZU" not in json.dumps(variables)


def test_une_fiche_sans_charte_ne_prend_pas_celle_de_ma_marque(abonnee: Abonne) -> None:
    job = _commande(abonnee, "market_study", SAISIE_EM, _projet(abonnee))

    variables = job.order.intake_submission.normalized_variables
    marque = extract_branding(job)

    assert "LOGO_URL" not in variables
    assert "COULEUR_PRINCIPALE" not in variables
    assert marque.logo_url == "", "le repli du rendu ne va pas chercher « Ma marque »"
    assert marque.color_primary != "#1B3A8C"


def test_la_charte_de_la_fiche_habille_le_document(abonnee: Abonne) -> None:
    projet = _projet(
        abonnee, couleur_principale="#0A7D5A", couleur_secondaire="#F2B705",
        logo_url="https://exemple.test/dibitek.png",
    )
    job = _commande(abonnee, "market_study", SAISIE_EM, projet)

    marque = extract_branding(job)

    assert (marque.color_primary, marque.color_secondary) == ("#0A7D5A", "#F2B705")
    assert marque.logo_url == "https://exemple.test/dibitek.png"


def test_sans_fiche_la_commande_garde_ma_marque(abonnee: Abonne) -> None:
    """Contre-épreuve : la commande directe, sans client, ne change pas."""
    job = _commande(abonnee, "market_study", SAISIE_EM, None)

    variables = job.order.intake_submission.normalized_variables

    assert variables["NOM_ENTREPRISE"] == "SUNTZU KOUMISITH POLY GROUPES FRANCE"
    assert variables["COULEUR_PRINCIPALE"] == "#1B3A8C"
    assert logo_du_job(job, "")[1] in ("organisation", "")


def _envoyer(abonnee: Abonne, chemin: str, **donnees: Any) -> Any:
    return Client().post(chemin, data=donnees, headers=abonnee.entetes)


def test_le_logo_se_depose_sur_la_fiche_et_se_remplace(abonnee: Abonne) -> None:
    client = _projet(abonnee).client
    chemin = f"/api/espace/clients-finaux/{client.id}/logo/"

    premier = _envoyer(
        abonnee, chemin, fichier=SimpleUploadedFile("a.png", PNG, content_type="image/png")
    )
    _envoyer(abonnee, chemin, fichier=SimpleUploadedFile("b.png", PNG, content_type="image/png"))
    client.refresh_from_db()

    assert premier.status_code == 201
    assert client.logo_url
    logos = abonnee.organisation.pieces_jointes.filter(categorie=CategorieFichier.LOGO_CLIENT)
    assert logos.count() == 1, "le nouveau logo remplace l'ancien"
    assert abonnee.organisation.logo_url == "/media/pieces-jointes/x/logo-suntzu.jpeg"

    _envoyer(abonnee, chemin, retirer="1")
    client.refresh_from_db()
    assert client.logo_url == ""
    assert not logos.exists()


def test_les_couleurs_se_corrigent_sur_la_fiche(abonnee: Abonne) -> None:
    client = _projet(abonnee).client
    chemin = f"/api/espace/clients-finaux/{client.id}/"
    api = Client()

    def _poster(corps: dict[str, str]) -> Any:
        return api.post(
            chemin, data=json.dumps(corps), content_type="application/json",
            headers=abonnee.entetes,
        )

    assert _poster({"couleur_principale": "bleu roi"}).status_code == 400
    assert _poster({"couleur_principale": "#0a7d5a"}).status_code == 200
    client.refresh_from_db()
    assert client.couleur_principale.upper() == "#0A7D5A"


def test_un_logo_de_client_ne_passe_pas_par_la_route_generale(abonnee: Abonne) -> None:
    reponse = _envoyer(
        abonnee, "/api/espace/fichiers/", categorie="logo_client",
        fichier=SimpleUploadedFile("a.png", PNG, content_type="image/png"),
    )
    assert reponse.status_code == 400

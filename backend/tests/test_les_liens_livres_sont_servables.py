"""Tout lien `/media/` remis à un client doit être ouvrable.

`servir_media` exige une signature horodatée. La route répond volontairement
`404` quand elle manque — dire « signature invalide » confirmerait l'existence
du fichier et ferait de la route un oracle d'énumération.

Cette prudence a un revers : **un lien construit sans signature est
indiscernable d'un fichier supprimé.** Le client clique sur le bouton de son
courriel de livraison, reçoit une page d'erreur, et rien nulle part ne dit
pourquoi. Ni les journaux, ni le tableau de bord : la requête a été servie
correctement, avec le code qu'on lui a demandé de rendre.

C'est la règle 1 vue de l'extérieur — la protection ne se trompe pas, c'est ce
qui produit les liens qui n'a pas suivi.

Ces tests vérifient donc la propriété qui compte vraiment, celle qu'aucun test
de la signature elle-même ne couvre : **ce que le producteur fabrique, le
serveur l'accepte.** Les deux moitiés étaient justes séparément.
"""
from __future__ import annotations

import pytest
from django.test import Client

from evkha import signatures


@pytest.fixture
def client_http() -> Client:
    return Client()


def _chemin_et_requete(url: str) -> str:
    """Rend la partie de l'URL que le navigateur enverra, domaine ôté."""
    sans_schema = url.split("://", 1)[-1]
    return "/" + sans_schema.split("/", 1)[1] if "/" in sans_schema else "/"


@pytest.mark.django_db
def test_un_lien_signe_est_servi(client_http: Client, tmp_path: object) -> None:
    """Le garde-fou : sans lui, les tests suivants passeraient sur du vide.

    Si `/media/` cessait d'exister, ou si le service échouait pour une raison
    étrangère à la signature, un test qui n'attend qu'un 404 se réjouirait de
    la mauvaise nouvelle (règle 1).
    """
    from django.conf import settings

    cible = settings.MEDIA_ROOT / "artifacts"
    cible.mkdir(parents=True, exist_ok=True)
    (cible / "temoin.pdf").write_bytes(b"%PDF-1.4 temoin")

    reponse = client_http.get(signatures.lien("artifacts/temoin.pdf"))

    assert reponse.status_code == 200
    assert reponse.headers["Content-Disposition"] == "attachment"


@pytest.mark.django_db
def test_l_url_du_client_pdf_reel_est_servable(client_http: Client) -> None:
    """LE défaut : le producteur de PDF ne signait pas ses liens.

    `WeasyPrintPdfClient` construisait `{base}{MEDIA_URL}/{cle}` à la main.
    Aucune signature. Le courriel de livraison portait donc un bouton menant à
    un 404 — et la production tourne bien ce client, `EVKHA_USE_STUB_PDF` y
    valant `false`.
    """
    from django.conf import settings

    from integrations.pdf import WeasyPrintPdfClient

    cle = "artifacts/pdf/verification.pdf"
    destination = settings.MEDIA_ROOT / cle
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"%PDF-1.4 verification")

    client_pdf = WeasyPrintPdfClient(
        media_root=settings.MEDIA_ROOT,
        base_url="https://api.exemple.test",
    )
    url = client_pdf.url_de_telechargement(cle)

    reponse = client_http.get(_chemin_et_requete(url))

    assert reponse.status_code == 200, (
        "Le lien fabrique par le client PDF n'est pas servable : il lui manque "
        "la signature. Le client recoit un 404 indiscernable d'un fichier "
        "supprime."
    )

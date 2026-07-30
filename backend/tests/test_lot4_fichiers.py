"""Téléversement de fichiers depuis l'espace client.

Le contrôle porte sur les **octets**, jamais sur l'extension ni sur l'en-tête
`Content-Type` : l'une se renomme, l'autre s'écrit à la main. Un fichier
accepté à tort finirait embarqué dans un `.docx` que Word refuserait d'ouvrir —
défaut bien plus difficile à diagnostiquer qu'un refus au dépôt.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from customers.models import Customer
from organisations import fichiers, services
from organisations.authentification import creer_compte, ouvrir_session
from organisations.models import CategorieFichier, PieceJointe, RoleOrganisation

pytestmark = pytest.mark.django_db

MOT_DE_PASSE = "mot-de-passe-de-test-2026"

#: PNG valide d'un pixel. Les octets de tête sont ce qui compte.
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
    b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 40
PDF = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n" + b"0" * 100
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
PAS_UNE_IMAGE = b"ceci nest pas une image, juste du texte"


class Abonne:
    def __init__(self, nom: str, email: str, role: str = RoleOrganisation.PROPRIETAIRE):
        self.contact = Customer.objects.create(email=email)
        self.organisation = services.creer_organisation(
            raison_sociale=nom, contact=self.contact
        )
        if role != RoleOrganisation.PROPRIETAIRE:
            membre = self.organisation.membres.get(customer=self.contact)
            membre.role = role
            membre.save(update_fields=["role"])
        creer_compte(self.contact, mot_de_passe=MOT_DE_PASSE)
        self.jeton, _ = ouvrir_session(email, MOT_DE_PASSE)

    @property
    def entetes(self) -> dict[str, str]:
        return {"authorization": f"Bearer {self.jeton}"}


@pytest.fixture
def abonne() -> Abonne:
    return Abonne("Agence Lumen", "lumen-fic@example.com")


@pytest.fixture
def autre() -> Abonne:
    return Abonne("Agence Rivage", "rivage-fic@example.com")


@pytest.fixture
def api() -> Client:
    return Client()


def charge(reponse: Any) -> dict[str, Any]:
    donnees: dict[str, Any] = json.loads(reponse.content)
    return donnees


def _deposer(
    api: Client, abonne: Abonne, contenu: bytes, nom: str, categorie: str
) -> Any:
    return api.post(
        "/api/espace/fichiers/",
        data={
            "fichier": SimpleUploadedFile(nom, contenu),
            "categorie": categorie,
        },
        headers=abonne.entetes,
    )


# ── Le format est lu dans les octets ─────────────────────────────────────────


def test_un_png_est_accepte_comme_logo() -> None:
    assert fichiers.valider_logo(PNG).nom == "PNG"


def test_un_jpeg_est_accepte_comme_logo() -> None:
    assert fichiers.valider_logo(JPEG).nom == "JPEG"


def test_un_svg_est_refuse_comme_logo() -> None:
    """`python-docx` ne sait pas l'embarquer : l'accepter produirait un
    document que Word ouvre en signalant une image corrompue."""
    with pytest.raises(fichiers.FichierRefuseError) as refus:
        fichiers.valider_logo(SVG)
    assert "SVG" in str(refus.value)


def test_une_extension_mensongere_ne_trompe_pas_le_controle() -> None:
    """Le cœur du module : `.png` sur un contenu qui n'en est pas un."""
    with pytest.raises(fichiers.FichierRefuseError):
        fichiers.valider_logo(PAS_UNE_IMAGE, "logo.png")


def test_un_fichier_vide_est_refuse() -> None:
    with pytest.raises(fichiers.FichierRefuseError):
        fichiers.valider_logo(b"")


def test_un_logo_trop_lourd_est_refuse() -> None:
    """Plafond repris du formulaire Tally : 2 Mo."""
    trop = PNG + b"\x00" * fichiers.TAILLE_MAX_LOGO
    with pytest.raises(fichiers.FichierRefuseError) as refus:
        fichiers.valider_logo(trop)
    assert "2 Mo" in str(refus.value)


def test_un_document_de_taille_correcte_passe() -> None:
    """Contre-épreuve : le plafond du document est plus large que celui du logo."""
    document = PDF + b"\x00" * (fichiers.TAILLE_MAX_LOGO + 1)
    assert fichiers.valider_document(document).nom == "PDF"


def test_un_document_trop_lourd_est_refuse() -> None:
    trop = PDF + b"\x00" * fichiers.TAILLE_MAX_DOCUMENT
    with pytest.raises(fichiers.FichierRefuseError):
        fichiers.valider_document(trop)


def test_un_nom_de_fichier_ne_peut_pas_remonter_l_arborescence() -> None:
    """Django assainit déjà les noms ; on ne s'en remet pas à cela seul."""
    assert fichiers.nom_sur("../../etc/passwd") == "passwd"
    assert fichiers.nom_sur("C:\\Windows\\system32\\cmd.exe") == "cmd.exe"
    assert "/" not in fichiers.nom_sur("a/b/c.png")


# ── Par l'API ────────────────────────────────────────────────────────────────


def test_le_depot_d_un_logo_reussit(api: Client, abonne: Abonne) -> None:
    reponse = _deposer(api, abonne, PNG, "logo.png", CategorieFichier.LOGO)
    assert reponse.status_code == 201
    donnees = charge(reponse)
    assert donnees["categorie"] == "logo"
    assert donnees["url"]


def test_le_logo_depose_devient_celui_de_la_marque(api: Client, abonne: Abonne) -> None:
    """Sans cela, le client déposerait un fichier qui n'habillerait rien."""
    _deposer(api, abonne, PNG, "logo.png", CategorieFichier.LOGO)
    abonne.organisation.refresh_from_db()
    assert abonne.organisation.logo_url


def test_un_nouveau_logo_remplace_le_precedent(api: Client, abonne: Abonne) -> None:
    """En conserver plusieurs laisserait le rendu choisir, et il choisirait mal."""
    _deposer(api, abonne, PNG, "premier.png", CategorieFichier.LOGO)
    _deposer(api, abonne, JPEG, "second.jpg", CategorieFichier.LOGO)
    logos = abonne.organisation.pieces_jointes.filter(categorie=CategorieFichier.LOGO)
    assert logos.count() == 1
    premier = logos.first()
    assert premier is not None
    assert premier.nom_original == "second.jpg"


def test_plusieurs_documents_coexistent(api: Client, abonne: Abonne) -> None:
    """Contre-épreuve du remplacement : il ne vaut QUE pour le logo."""
    _deposer(api, abonne, PDF, "etude.pdf", CategorieFichier.DOCUMENT)
    _deposer(api, abonne, PDF, "previsionnel.pdf", CategorieFichier.DOCUMENT)
    assert (
        abonne.organisation.pieces_jointes.filter(
            categorie=CategorieFichier.DOCUMENT
        ).count()
        == 2
    )


def test_un_fichier_refuse_renvoie_un_message_utile(api: Client, abonne: Abonne) -> None:
    reponse = _deposer(api, abonne, SVG, "logo.svg", CategorieFichier.LOGO)
    assert reponse.status_code == 400
    assert "SVG" in charge(reponse)["error"]
    assert not PieceJointe.objects.exists()


def test_un_depot_sans_fichier_est_refuse(api: Client, abonne: Abonne) -> None:
    reponse = api.post(
        "/api/espace/fichiers/",
        data={"categorie": CategorieFichier.DOCUMENT},
        headers=abonne.entetes,
    )
    assert reponse.status_code == 400


def test_une_categorie_inconnue_est_refusee(api: Client, abonne: Abonne) -> None:
    assert _deposer(api, abonne, PDF, "x.pdf", "contrat_secret").status_code == 400


def test_un_role_lecture_ne_peut_pas_deposer(api: Client) -> None:
    lectrice = Abonne("Agence Vue", "vue-fic@example.com", role=RoleOrganisation.LECTURE)
    assert (
        _deposer(api, lectrice, PNG, "logo.png", CategorieFichier.LOGO).status_code
        == 403
    )


def test_aucun_depot_sans_jeton(api: Client) -> None:
    reponse = api.post(
        "/api/espace/fichiers/",
        data={"fichier": SimpleUploadedFile("logo.png", PNG)},
    )
    assert reponse.status_code == 401


# ── Cloisonnement ────────────────────────────────────────────────────────────


def test_les_fichiers_sont_cloisonnes(api: Client, abonne: Abonne, autre: Abonne) -> None:
    _deposer(api, autre, PDF, "secret-rivage.pdf", CategorieFichier.DOCUMENT)
    liste = charge(api.get("/api/espace/fichiers/", headers=abonne.entetes))
    assert liste["pieces"] == []


def test_un_fichier_d_une_autre_organisation_ne_peut_pas_etre_supprime(
    api: Client, abonne: Abonne, autre: Abonne
) -> None:
    """L'identifiant ne suffit pas : le fichier doit appartenir à l'organisation."""
    reponse = _deposer(api, autre, PDF, "secret.pdf", CategorieFichier.DOCUMENT)
    identifiant = charge(reponse)["id"]

    tentative = api.post(
        f"/api/espace/fichiers/{identifiant}/supprimer/", headers=abonne.entetes
    )
    assert tentative.status_code == 404
    assert PieceJointe.objects.filter(id=identifiant).exists()


def test_supprimer_son_logo_le_retire_de_la_marque(api: Client, abonne: Abonne) -> None:
    reponse = _deposer(api, abonne, PNG, "logo.png", CategorieFichier.LOGO)
    identifiant = charge(reponse)["id"]

    suppression = api.post(
        f"/api/espace/fichiers/{identifiant}/supprimer/", headers=abonne.entetes
    )
    assert suppression.status_code == 204
    abonne.organisation.refresh_from_db()
    assert abonne.organisation.logo_url == ""


# ── Le logo déposé atteint le document ───────────────────────────────────────


def test_le_logo_depose_est_relu_sur_le_disque_sans_appel_reseau(
    api: Client, abonne: Abonne
) -> None:
    """Règle 7 : la preuve est que le RENDU récupère bien les octets.

    Aller chercher par HTTP un fichier que le serveur a sous la main serait
    absurde, et échouerait dès que l'URL publique diffère de l'URL interne.
    """
    from generation.rendu_word.logo import charger_logo

    _deposer(api, abonne, PNG, "logo.png", CategorieFichier.LOGO)
    abonne.organisation.refresh_from_db()

    octets = charger_logo(abonne.organisation.logo_url)
    assert octets is not None
    assert octets.startswith(b"\x89PNG")


def test_une_reference_qui_remonte_l_arborescence_est_refusee() -> None:
    """La lecture est confinée au répertoire des médias."""
    from generation.rendu_word.logo import charger_logo

    assert charger_logo("/media/../../../etc/passwd") is None
    assert charger_logo("../../secrets.env") is None

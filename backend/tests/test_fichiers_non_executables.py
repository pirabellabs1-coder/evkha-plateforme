"""Un fichier déposé ne doit pas pouvoir s'exécuter sur le domaine de l'API.

Le chemin complet, vérifié dans le code puis reproduit ici :

1. n'importe qui crée un compte — l'inscription est libre et gratuite ;
2. il téléverse un fichier nommé `rapport.html` dont les premiers octets sont
   `%PDF-`. La reconnaissance binaire ne lit que la tête : elle voit un PDF et
   accepte ;
3. le nom était conservé **tel quel**, extension comprise ;
4. `/media/` était servi par `django.views.static.serve`, qui choisit le
   `Content-Type` d'après l'extension : `text/html` ;
5. le navigateur exécute le contenu sur l'origine qui héberge `/admin/` et
   `/api/dashboard/`.

Le module `fichiers.py` affirmait pourtant, en toutes lettres : « Aucun fichier
n'est exécuté, rendu, ni servi depuis le domaine de l'API. » C'est sur cette
phrase que reposait l'acceptation de l'extension du client — une garantie
écrite qui a dispensé de poser la vraie protection (règle 1).

Le correctif n'énumère pas les extensions dangereuses : `.html`, `.htm`,
`.svg`, `.xhtml`, `.xml` et le reste n'en finiraient pas. Il retient une liste
FERMÉE de ce qui est admis (règle 4).
"""
from __future__ import annotations

from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from organisations import fichiers

pytestmark = pytest.mark.django_db

#: Un PDF minimal : de vrais octets de tête, pour que la validation accepte.
PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


# ── L'extension ne vient plus du client ──────────────────────────────────────


def test_une_extension_executable_est_remplacee() -> None:
    """Le test qui échoue sur le code d'avant : `.html` était conservé."""
    format_pdf = fichiers.valider_document(PDF, "rapport.html")
    nom = fichiers.nom_sur("rapport.html", format_pdf)

    assert not nom.endswith(".html"), "l'extension du client a ete conservee"
    assert nom == "rapport.pdf"


def test_toute_extension_hors_liste_subit_le_meme_sort() -> None:
    """La CLASSE, pas l'exemple (règle 4).

    Un correctif qui n'aurait banni que `.html` laisserait passer `.svg` — un
    document XML que le navigateur exécute tout aussi bien — puis `.htm`, puis
    `.xhtml`. On ne liste pas ce qui est interdit, on liste ce qui est admis.
    """
    format_pdf = fichiers.valider_document(PDF, "x")
    for dangereuse in ("svg", "htm", "xhtml", "xml", "js", "php", "sh"):
        nom = fichiers.nom_sur(f"charge.{dangereuse}", format_pdf)
        assert nom == "charge.pdf", f".{dangereuse} est passe"


def test_une_extension_legitime_est_conservee() -> None:
    """Contre-épreuve : on ne renomme pas ce qui n'a rien demandé.

    Les formats Office partagent la signature ZIP et ne se distinguent que par
    l'extension. Forcer `.docx` sur un classeur `.xlsx` casserait l'ouverture
    chez le client — le correctif deviendrait le défaut.
    """
    format_pdf = fichiers.valider_document(PDF, "etude.pdf")
    assert fichiers.nom_sur("etude.pdf", format_pdf) == "etude.pdf"

    format_png = fichiers.valider_logo(PNG, "logo.png")
    assert fichiers.nom_sur("logo.png", format_png) == "logo.png"


def test_un_fichier_sans_extension_recoit_celle_du_format_reconnu() -> None:
    format_pdf = fichiers.valider_document(PDF, "sans-extension")
    assert fichiers.nom_sur("sans-extension", format_pdf) == "sans-extension.pdf"


def test_le_nettoyage_de_chemin_reste_assure() -> None:
    """Contre-épreuve : le correctif ne doit pas défaire ce qui marchait."""
    format_pdf = fichiers.valider_document(PDF, "x")
    assert "/" not in fichiers.nom_sur("../../etc/passwd", format_pdf)
    assert "\\" not in fichiers.nom_sur("C:\\Windows\\cmd.exe", format_pdf)


def test_la_liste_des_extensions_admises_derive_des_formats() -> None:
    """Une seule source de vérité (règle 5).

    Si un format est ajouté à `DOCUMENTS` sans l'être dans la liste des
    extensions, tout fichier de ce format serait renommé à chaque dépôt.
    """
    for format_fichier in (*fichiers.DOCUMENTS, *fichiers.IMAGES):
        assert format_fichier.extension in fichiers.EXTENSIONS_ADMISES


# ── Le dépôt réel, par la vue ────────────────────────────────────────────────


def _espace(client: Any) -> str:
    from organisations import authentification, inscription

    inscription.ouvrir_compte(
        raison_sociale="Cabinet Duval",
        email="claire@cabinet-duval.fr",
        mot_de_passe="un-mot-de-passe-solide-42",
        activer_abonnement=False,
    )
    jeton, _ = authentification.ouvrir_session(
        "claire@cabinet-duval.fr", "un-mot-de-passe-solide-42"
    )
    return str(jeton)


def test_le_fichier_stocke_ne_porte_pas_l_extension_du_client(client: Any) -> None:
    """Le vrai chemin, de bout en bout (règle 7).

    Vérifier `nom_sur` isolément ne prouverait rien : c'est la vue qui décide
    de lui transmettre — ou non — le format reconnu.
    """
    jeton = _espace(client)
    envoi = SimpleUploadedFile("piege.html", PDF, content_type="text/html")

    reponse = client.post(
        "/api/espace/fichiers/",
        {"fichier": envoi, "categorie": "document"},
        HTTP_AUTHORIZATION=f"Bearer {jeton}",
    )
    assert reponse.status_code == 201, reponse.content

    from organisations.models import PieceJointe

    piece = PieceJointe.objects.get()
    assert not piece.fichier.name.endswith(".html"), (
        "le fichier est stocke en .html : il sera servi en text/html"
    )
    assert piece.fichier.name.endswith(".pdf")


# ── La route /media/ ne rend rien ────────────────────────────────────────────


@pytest.fixture
def dans_media() -> Any:
    """Écrit dans le VRAI `MEDIA_ROOT`, puis nettoie.

    `document_root` est figé à l'import de `urls.py` : surcharger
    `settings.MEDIA_ROOT` dans un test ne déplace pas la route, et le test
    passerait à côté du câblage réel qu'il prétend vérifier (règle 7).
    """
    import pathlib as _p

    from django.conf import settings as reglages

    racine = _p.Path(reglages.MEDIA_ROOT)
    racine.mkdir(parents=True, exist_ok=True)
    ecrits: list[_p.Path] = []

    def ecrire(nom: str, contenu: bytes) -> str:
        chemin = racine / nom
        chemin.write_bytes(contenu)
        ecrits.append(chemin)
        return nom

    yield ecrire

    for chemin in ecrits:
        # `FileResponse` garde le descripteur ouvert : sous Windows, la
        # suppression echoue tant que le test n'a pas ferme la reponse. On ne
        # veut pas qu'un nettoyage fasse echouer un test qui, lui, a reussi.
        try:
            chemin.unlink(missing_ok=True)
        except PermissionError:  # pragma: no cover — specifique a Windows
            pass


def test_media_impose_le_telechargement(client: Any, dans_media: Any) -> None:
    """Seconde ligne : même un fichier déjà stocké avant le correctif.

    Le stockage contient des fichiers déposés AVANT que l'extension ne soit
    imposée, et la génération y écrit par d'autres chemins que le téléversement
    client. Corriger la seule porte d'entrée laisserait ceux-là exécutables.
    """
    nom = dans_media(
        "test-ancien.html", b"<script>alert(document.cookie)</script>"
    )

    reponse = client.get(f"/media/{nom}")

    assert reponse.status_code == 200
    assert reponse.headers["Content-Disposition"] == "attachment", (
        "le navigateur va RENDRE ce fichier sur le domaine de l'API"
    )
    assert reponse.headers["X-Content-Type-Options"] == "nosniff"
    reponse.close()


def test_media_sert_toujours_le_contenu(client: Any, dans_media: Any) -> None:
    """Contre-épreuve : les livrables doivent rester téléchargeables.

    Brevo récupère les pièces jointes par URL depuis Internet ; si cette route
    cessait de servir, plus aucun document ne partirait.
    """
    nom = dans_media("test-etude.pdf", PDF)

    reponse = client.get(f"/media/{nom}")
    assert reponse.status_code == 200
    contenu = b"".join(reponse.streaming_content) if reponse.streaming else reponse.content
    reponse.close()
    assert contenu.startswith(b"%PDF-")


# ── La purge supprime réellement ─────────────────────────────────────────────


def test_la_purge_efface_le_fichier_du_disque(tmp_path: Any, settings: Any) -> None:
    """Le test qui échoue sur le code d'avant.

    `purge_expired_artifacts` basculait un statut et vidait `download_url`. Le
    document restait sur le disque, à une adresse que `/media/` servait sans
    authentification : l'étude d'un client final restait téléchargeable
    indéfiniment par quiconque avait vu passer le lien.

    La rétention était pourtant invoquée comme garantie de confidentialité dans
    le commentaire de la route.
    """
    from datetime import timedelta

    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from django.utils import timezone

    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from delivery.services import purge_expired_artifacts
    from documents.models import ArtifactKind, ArtifactStatus, DocumentArtifact
    from generation.models import GenerationJob, JobStatus
    from orders.models import Order

    settings.MEDIA_ROOT = tmp_path

    offre = Offer.objects.create(
        name="Étude", slug="etude-purge", deliverable_type=DeliverableType.MARKET_STUDY
    )
    contact = Customer.objects.create(email="client@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id="cmd-purge", customer=contact, offer=offre
    )
    job = GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.MARKET_STUDY,
        status=JobStatus.DONE,
    )

    cle = default_storage.save("livrables/etude-confidentielle.pdf", ContentFile(PDF))
    assert default_storage.exists(cle)

    DocumentArtifact.objects.create(
        job=job,
        kind=ArtifactKind.PDF,
        status=ArtifactStatus.READY,
        storage_key=cle,
        download_url="http://exemple/media/" + cle,
        expires_at=timezone.now() - timedelta(days=1),
    )

    assert purge_expired_artifacts() == 1
    assert not default_storage.exists(cle), (
        "le document reste sur le disque et donc telechargeable"
    )


def test_la_purge_ne_touche_pas_un_document_encore_valide(
    tmp_path: Any, settings: Any
) -> None:
    """Contre-épreuve : supprimer trop tôt priverait le client de son document."""
    from datetime import timedelta

    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from django.utils import timezone

    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from delivery.services import purge_expired_artifacts
    from documents.models import ArtifactKind, ArtifactStatus, DocumentArtifact
    from generation.models import GenerationJob, JobStatus
    from orders.models import Order

    settings.MEDIA_ROOT = tmp_path

    offre = Offer.objects.create(
        name="Étude", slug="etude-valide", deliverable_type=DeliverableType.MARKET_STUDY
    )
    contact = Customer.objects.create(email="client2@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id="cmd-valide", customer=contact, offer=offre
    )
    job = GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.MARKET_STUDY,
        status=JobStatus.DONE,
    )
    cle = default_storage.save("livrables/encore-valide.pdf", ContentFile(PDF))
    DocumentArtifact.objects.create(
        job=job,
        kind=ArtifactKind.PDF,
        status=ArtifactStatus.READY,
        storage_key=cle,
        expires_at=timezone.now() + timedelta(days=3),
    )

    assert purge_expired_artifacts() == 0
    assert default_storage.exists(cle)


def test_un_fichier_deja_absent_n_interrompt_pas_la_purge(
    tmp_path: Any, settings: Any
) -> None:
    """Un artefact dont le fichier a disparu ne doit pas bloquer les suivants."""
    from datetime import timedelta

    from django.utils import timezone

    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from delivery.services import purge_expired_artifacts
    from documents.models import ArtifactKind, ArtifactStatus, DocumentArtifact
    from generation.models import GenerationJob, JobStatus
    from orders.models import Order

    settings.MEDIA_ROOT = tmp_path
    offre = Offer.objects.create(
        name="Étude", slug="etude-absent", deliverable_type=DeliverableType.MARKET_STUDY
    )
    contact = Customer.objects.create(email="client3@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id="cmd-absent", customer=contact, offer=offre
    )
    job = GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.MARKET_STUDY,
        status=JobStatus.DONE,
    )
    DocumentArtifact.objects.create(
        job=job,
        kind=ArtifactKind.PDF,
        status=ArtifactStatus.READY,
        storage_key="livrables/jamais-ecrit.pdf",
        expires_at=timezone.now() - timedelta(days=1),
    )

    assert purge_expired_artifacts() == 1
    artefact = DocumentArtifact.objects.get()
    assert artefact.status == ArtifactStatus.EXPIRED, (
        "le statut doit basculer, sinon la purge le repassera indefiniment"
    )

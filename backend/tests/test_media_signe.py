"""Un document ne se télécharge plus en devinant son adresse.

`/media/` était servi par `django.views.static.serve` **sans aucun contrôle
d'accès**. L'étude de marché complète d'un client final — chiffre d'affaires,
marges, concurrents — et le bilan qu'une agence avait déposé étaient
téléchargeables par quiconque détenait l'URL, indéfiniment, y compris par un
membre révoqué qui l'avait vue passer dans son espace.

Deux protections étaient invoquées dans le commentaire de la route. **Aucune
n'existait** : les pièces jointes conservaient le nom d'origine du client sous
`pieces-jointes/<id-organisation>/<nom>`, et la « rétention 7 jours » basculait
un statut en base sans rien supprimer du disque.

## Pourquoi une signature et non une session

Deux consommateurs légitimes ne peuvent en présenter aucune : Brevo, qui
récupère les pièces jointes depuis Internet pour les joindre au courriel, et le
client final de l'abonné, qui n'a pas de compte chez nous. Exiger un jeton
fermerait la livraison.

Ce que la signature retire : l'énumération, et la validité sans fin. Ce qu'elle
ne retire pas, et il faut le dire : un lien transmis reste utilisable jusqu'à
son expiration. C'est inhérent à un lien porteur.
"""
from __future__ import annotations

import time
from typing import Any

import pytest

from evkha import signatures

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\ntrailer\n<<>>\n%%EOF\n"


@pytest.fixture
def fichier() -> Any:
    """Écrit dans le VRAI `MEDIA_ROOT` : la route y est câblée à l'import."""
    import pathlib

    from django.conf import settings

    racine = pathlib.Path(settings.MEDIA_ROOT)
    racine.mkdir(parents=True, exist_ok=True)
    chemin = racine / "test-signature.pdf"
    chemin.write_bytes(PDF)
    yield "test-signature.pdf"
    try:
        chemin.unlink(missing_ok=True)
    except PermissionError:  # pragma: no cover — Windows garde le descripteur
        pass


# ── Ce qui ne passe plus ─────────────────────────────────────────────────────


def test_sans_signature_le_fichier_est_introuvable(client: Any, fichier: Any) -> None:
    """Le test qui échoue sur le code d'avant : l'URL seule suffisait."""
    reponse = client.get(f"/media/{fichier}")
    assert reponse.status_code == 404, "l'adresse seule ouvre encore le document"


def test_une_signature_fausse_est_refusee(client: Any, fichier: Any) -> None:
    reponse = client.get(f"/media/{fichier}?{signatures.PARAMETRE}=nimporte-quoi")
    assert reponse.status_code == 404


def test_une_signature_valable_pour_un_AUTRE_fichier_ne_vaut_rien(
    client: Any, fichier: Any
) -> None:
    """Le chemin fait partie du message signé.

    Sans cela, il suffirait de recopier la signature d'un document qu'on
    possède légitimement sur l'URL d'un document qu'on convoite — et l'abonné
    a toujours au moins un document à lui.
    """
    signature_d_un_autre = signatures.signer("pieces-jointes/autre/bilan.pdf")

    reponse = client.get(f"/media/{fichier}?{signatures.PARAMETRE}={signature_d_un_autre}")
    assert reponse.status_code == 404


def test_le_refus_ne_dit_pas_si_le_fichier_existe(client: Any, fichier: Any) -> None:
    """Sinon la route devient un oracle d'énumération.

    Répondre « 403 signature invalide » pour un fichier présent et « 404 » pour
    un absent permettrait de sonder les chemins un par un, ce que la signature
    est justement censée empêcher.
    """
    present = client.get(f"/media/{fichier}")
    absent = client.get("/media/ce-fichier-n-existe-pas.pdf")

    assert present.status_code == absent.status_code == 404


def test_un_lien_expire_ne_vaut_plus(client: Any, fichier: Any, settings: Any) -> None:
    """La durée de vie doit exister dans le jeton, pas seulement dans la doc.

    C'est le piège que ce module a d'abord posé : `Signer` ne porte aucune
    date, et un lien signé sans horodatage serait éternel — la protection
    aurait l'air complète tout en laissant la moitié du problème (règle 1).
    """
    settings.EVKHA_MEDIA_DUREE_LIEN_S = 1
    lien = signatures.lien(fichier)

    assert client.get(lien).status_code == 200
    time.sleep(2)
    assert client.get(lien).status_code == 404, "le lien vaut encore apres expiration"


# ── Ce qui doit continuer à passer ───────────────────────────────────────────


def test_un_lien_signe_ouvre_le_document(client: Any, fichier: Any) -> None:
    """Contre-épreuve : Brevo et le client final n'ont pas de session.

    Si cette route cessait de servir, plus aucun document ne partirait — la
    protection aurait remplacé une fuite par une panne.
    """
    reponse = client.get(signatures.lien(fichier))

    assert reponse.status_code == 200
    contenu = (
        b"".join(reponse.streaming_content) if reponse.streaming else reponse.content
    )
    reponse.close()
    assert contenu.startswith(b"%PDF-")


def test_les_liens_de_livrables_sont_signes() -> None:
    """Le vrai chemin : les URL écrites en base, pas une signature de test.

    Vérifier la primitive isolément ne prouverait rien — c'est l'appelant qui
    décide de signer, ou d'oublier (règle 7).
    """
    from documents.livrable_word import _url

    url = _url("livrables/etude.pdf")

    assert f"{signatures.PARAMETRE}=" in url, "l'URL de livrable n'est pas signee"
    assert "/media/livrables/etude.pdf" in url


def test_les_pieces_jointes_sont_signees(client: Any) -> None:
    """L'autre émetteur d'URL, qui avait son propre oubli.

    `_piece_en_dict` rendait `piece.fichier.url` brut : un chemin de la forme
    `pieces-jointes/<id-organisation>/<nom d'origine>` se devine sans effort.
    """
    from django.core.files.base import ContentFile

    from organisations import authentification, inscription
    from organisations.models import CategorieFichier, PieceJointe

    organisation = inscription.ouvrir_compte(
        raison_sociale="Cabinet Duval",
        email="claire@cabinet-duval.fr",
        mot_de_passe="un-mot-de-passe-solide-42",
        activer_abonnement=False,
    ).organisation
    from customers.models import Customer

    piece = PieceJointe(
        organisation=organisation,
        categorie=CategorieFichier.DOCUMENT,
        nom_original="bilan.pdf",
        type_mime="application/pdf",
        taille_octets=len(PDF),
        depose_par=Customer.objects.get(email="claire@cabinet-duval.fr"),
    )
    piece.fichier.save("bilan.pdf", ContentFile(PDF), save=False)
    piece.save()

    jeton, _ = authentification.ouvrir_session(
        "claire@cabinet-duval.fr", "un-mot-de-passe-solide-42"
    )
    reponse = client.get(
        "/api/espace/fichiers/", HTTP_AUTHORIZATION=f"Bearer {jeton}"
    )

    assert reponse.status_code == 200, reponse.content
    url = reponse.json()["pieces"][0]["url"]
    assert f"{signatures.PARAMETRE}=" in url, "la piece jointe n'est pas signee"


def test_la_signature_d_un_chemin_est_stable() -> None:
    """Deux appels doivent produire un lien utilisable, pas une loterie."""
    assert signatures.signature_valable(
        "livrables/etude.pdf", signatures.signer("livrables/etude.pdf")
    )

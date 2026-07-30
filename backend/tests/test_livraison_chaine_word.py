"""La livraison emprunte la chaîne Word du lot 3, et non l'ancienne.

`assembler_livrable_word` existait depuis le lot 3, complète et testée, et
**n'était appelée par rien** : `deliver_job` passait par `assemble_document`.
Les quinze types de graphiques, les profils sectoriels et les six contrôles de
cohérence n'avaient donc jamais tourné sur un document livré.

Découvert non pas en relisant du code, mais en produisant un document sur le
déploiement réel : le PDF portait « WeasyPrint » comme producteur et aucun
`.docx` n'accompagnait la livraison. C'est le défaut décrit par la règle 8, déjà
vécu ici avec Gamma — intégré, testé, branché, jamais exécuté.

Ces tests verrouillent trois choses que le vert d'un test unitaire ne prouvait
pas : la chaîne employée, le fait que les deux fichiers partent, et le refus
d'envoyer un document que la vérification bloque.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from django.test import override_settings

from delivery import services as livraison
from documents.models import ArtifactKind, ArtifactStatus

pytestmark = pytest.mark.django_db


# ── Doublures ────────────────────────────────────────────────────────────────


@dataclass
class _Artefact:
    """Doublure d'artefact : seuls les champs lus par la livraison."""

    kind: str
    download_url: str
    status: str = ArtifactStatus.READY


@dataclass
class _Anomalie:
    detail: str


@dataclass
class _Controle:
    bloquantes_: list[_Anomalie]

    @property
    def bloquantes(self) -> list[_Anomalie]:
        return self.bloquantes_


@dataclass
class _LivrableAssemble:
    docx: _Artefact
    pdf: _Artefact | None
    controle: _Controle | None

    @property
    def livrable(self) -> bool:
        return self.controle is not None and not self.controle.bloquantes


def _livrable_word(*, bloquantes: list[str] | None = None) -> _LivrableAssemble:
    return _LivrableAssemble(
        docx=_Artefact(ArtifactKind.DOCX, "https://exemple.fr/etude.docx"),
        pdf=_Artefact(ArtifactKind.PDF, "https://exemple.fr/etude.pdf"),
        controle=_Controle([_Anomalie(d) for d in (bloquantes or [])]),
    )


@pytest.fixture
def job() -> Any:
    """Un objet quelconque : `_assembler_livrable` ne fait que le transmettre."""
    return object()


def _brancher(monkeypatch: pytest.MonkeyPatch, retour: Any) -> dict[str, int]:
    """Remplace la chaîne Word et compte les appels des DEUX chaînes."""
    appels = {"word": 0, "ancienne": 0}

    def _word(job_recu: Any) -> Any:
        appels["word"] += 1
        return retour

    def _ancienne(job_recu: Any, **_: Any) -> Any:
        appels["ancienne"] += 1
        return type(
            "Ancien",
            (),
            {
                "link": _Artefact(ArtifactKind.LINK, "https://exemple.fr/apercu.html"),
                "pdf": _Artefact(ArtifactKind.PDF, "https://exemple.fr/ancien.pdf"),
            },
        )()

    monkeypatch.setattr(
        "documents.livrable_word.assembler_livrable_word", _word, raising=False
    )
    monkeypatch.setattr(livraison, "assemble_document", _ancienne)
    return appels


# ── La chaîne employée ───────────────────────────────────────────────────────


@override_settings(EVKHA_LIVRABLE_WORD=True)
def test_la_chaine_word_est_employee_par_defaut(
    monkeypatch: pytest.MonkeyPatch, job: Any
) -> None:
    """LE test du défaut : sans le correctif, c'est l'ancienne qui tournait."""
    appels = _brancher(monkeypatch, _livrable_word())

    assemblage = livraison._assembler_livrable(job, pdf_client=None)

    assert appels["word"] == 1
    assert appels["ancienne"] == 0
    natures = {artefact.kind for artefact in assemblage.artefacts}
    assert natures == {ArtifactKind.DOCX, ArtifactKind.PDF}


@override_settings(EVKHA_LIVRABLE_WORD=True)
def test_l_url_du_lot_est_celle_du_pdf(
    monkeypatch: pytest.MonkeyPatch, job: Any
) -> None:
    """La chaîne Word ne produit aucun aperçu HTML ; le lot portait ce lien."""
    _brancher(monkeypatch, _livrable_word())
    assemblage = livraison._assembler_livrable(job, pdf_client=None)
    assert assemblage.url_principale == "https://exemple.fr/etude.pdf"


@override_settings(EVKHA_LIVRABLE_WORD=True)
def test_un_pdf_en_echec_ne_prive_pas_du_word(
    monkeypatch: pytest.MonkeyPatch, job: Any
) -> None:
    """Le client a payé un livrable, pas une chaîne d'outils."""
    partiel = _livrable_word()
    partiel.pdf = _Artefact(ArtifactKind.PDF, "", status=ArtifactStatus.FAILED)
    _brancher(monkeypatch, partiel)

    assemblage = livraison._assembler_livrable(job, pdf_client=None)

    assert assemblage.url_principale == "https://exemple.fr/etude.docx"
    assert not assemblage.retenu


# ── Le blocage à la vérification ─────────────────────────────────────────────


@override_settings(EVKHA_LIVRABLE_WORD=True)
def test_un_document_bloque_est_signale_comme_retenu(
    monkeypatch: pytest.MonkeyPatch, job: Any
) -> None:
    _brancher(monkeypatch, _livrable_word(bloquantes=["chiffre hors socle : 42 %"]))

    assemblage = livraison._assembler_livrable(job, pdf_client=None)

    assert assemblage.retenu == "chiffre hors socle : 42 %"


@override_settings(EVKHA_LIVRABLE_WORD=True)
def test_une_verification_absente_vaut_blocage(
    monkeypatch: pytest.MonkeyPatch, job: Any
) -> None:
    """Ne pas avoir vérifié n'est pas avoir vérifié sans rien trouver (règle 1)."""
    sans_controle = _livrable_word()
    sans_controle.controle = None
    _brancher(monkeypatch, sans_controle)

    assemblage = livraison._assembler_livrable(job, pdf_client=None)

    assert assemblage.retenu == "vérification non exécutée"


# ── La contre-épreuve : l'ancienne chaîne reste joignable ────────────────────


@override_settings(EVKHA_LIVRABLE_WORD=False)
def test_l_ancienne_chaine_reste_joignable(
    monkeypatch: pytest.MonkeyPatch, job: Any
) -> None:
    """Le §16 exige un basculement réversible immédiatement.

    Sans ce test, le drapeau pourrait cesser d'être lu sans que rien ne le
    dise, et le repli annoncé n'existerait plus.
    """
    appels = _brancher(monkeypatch, _livrable_word())

    assemblage = livraison._assembler_livrable(job, pdf_client=None)

    assert appels["ancienne"] == 1
    assert appels["word"] == 0
    natures = {artefact.kind for artefact in assemblage.artefacts}
    assert natures == {ArtifactKind.LINK, ArtifactKind.PDF}
    assert assemblage.url_principale == "https://exemple.fr/apercu.html"
    assert not assemblage.retenu


def test_le_drapeau_existe_et_vaut_vrai_par_defaut() -> None:
    """Le branchement ne sert à rien si le réglage n'est pas livré actif."""
    from django.conf import settings

    assert hasattr(settings, "EVKHA_LIVRABLE_WORD")


# ── `deliver_job` de bout en bout ────────────────────────────────────────────
#
# Les tests ci-dessus n'examinent que l'aiguillage. Ils ne diraient rien si
# `deliver_job` cessait de l'appeler, ou envoyait l'e-mail malgré un document
# retenu — c'est exactement ce que la règle 9 demande de se demander : où mon
# contrôle ne regarde-t-il pas ?


class _EmailEnregistreur:
    """Client d'e-mail qui note ce qu'on lui demande, sans rien envoyer."""

    def __init__(self) -> None:
        self.envois: list[dict[str, Any]] = []

    def send_delivery_email(
        self, *, recipient_email: str, subject: str, html_body: str, attachments: Any
    ) -> Any:
        self.envois.append(
            {
                "destinataire": recipient_email,
                "sujet": subject,
                "pieces": [piece.filename for piece in attachments],
            }
        )
        from integrations.brevo import EmailSendResult

        return EmailSendResult(provider_message_id="test-1")


@pytest.fixture
def job_livrable() -> Any:
    """Un job terminé, prêt à être livré."""
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.services import bootstrap_generation_job
    from intake.models import IntakeStatus, IntakeSubmission
    from orders.models import Order

    offre = Offer.objects.create(
        name="Étude de marché",
        slug="etude-marche-word",
        deliverable_type=DeliverableType.MARKET_STUDY,
        gamma_enabled=False,
    )
    client = Customer.objects.create(email="cliente@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id="order_word_1", customer=client, offer=offre
    )
    soumission = IntakeSubmission.objects.create(
        order=commande,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "automobile",
            "PAYS": "France",
            "ZONE": "Paris",
            "PROJET": "vente de véhicules d'occasion",
        },
    )
    from generation.runner import run_generation_job

    job = bootstrap_generation_job(soumission)
    run_generation_job(job)
    job.refresh_from_db()
    return job


def _artefacts_reels(job: Any) -> Any:
    """Crée en base les deux artefacts que la chaîne Word produirait."""
    from documents.models import DocumentArtifact

    docx = DocumentArtifact.objects.create(
        job=job,
        kind=ArtifactKind.DOCX,
        status=ArtifactStatus.READY,
        storage_key=f"livrables/{job.id}.docx",
        download_url=f"https://exemple.fr/{job.id}.docx",
    )
    pdf = DocumentArtifact.objects.create(
        job=job,
        kind=ArtifactKind.PDF,
        status=ArtifactStatus.READY,
        storage_key=f"livrables/{job.id}.pdf",
        download_url=f"https://exemple.fr/{job.id}.pdf",
    )
    return docx, pdf


@override_settings(EVKHA_LIVRABLE_WORD=True)
def test_deliver_job_joint_le_word_ET_le_pdf(
    monkeypatch: pytest.MonkeyPatch, job_livrable: Any
) -> None:
    """Les deux fichiers partent. Le Word est le document, le PDF sa photo."""
    from delivery.models import DeliveryStatus
    from integrations.gamma import StubGammaClient

    docx, pdf = _artefacts_reels(job_livrable)
    monkeypatch.setattr(
        "documents.livrable_word.assembler_livrable_word",
        lambda job: _LivrableAssemble(docx=docx, pdf=pdf, controle=_Controle([])),
        raising=False,
    )
    courriel = _EmailEnregistreur()

    lot = livraison.deliver_job(
        job_livrable, email_client=courriel, gamma_client=StubGammaClient()
    )

    assert lot.status == DeliveryStatus.SENT
    assert {a.kind for a in lot.artifacts.all()} == {
        ArtifactKind.DOCX,
        ArtifactKind.PDF,
    }
    assert len(courriel.envois) == 1
    pieces = courriel.envois[0]["pieces"]
    # Chaque pièce jointe porte SON extension. Elle était calculée par une
    # liste de deux cas, et le Word serait parti nommé « …_docx.pdf ».
    assert any(nom.endswith(".docx") for nom in pieces), pieces
    assert any(nom.endswith(".pdf") for nom in pieces), pieces


@override_settings(EVKHA_LIVRABLE_WORD=True)
def test_l_extension_de_la_piece_jointe_suit_le_fichier(job_livrable: Any) -> None:
    """Contre-épreuve du correctif d'extension, sur les quatre natures.

    Écrit à part parce que le test ci-dessus ne regarde que le cas nominal :
    un artefact sans clé de stockage, ou d'une nature ajoutée plus tard, doit
    lui aussi porter la bonne extension.
    """
    from documents.models import DocumentArtifact

    cas = [
        (ArtifactKind.DOCX, "livrables/x.docx", "", ".docx"),
        (ArtifactKind.PDF, "livrables/x.pdf", "", ".pdf"),
        # Sans clé de stockage : l'URL fait foi.
        (ArtifactKind.GAMMA_PPTX, "", "https://gamma.app/e/x.pptx", ".pptx"),
        # Ni l'un ni l'autre : le repli par nature.
        (ArtifactKind.GAMMA_PDF, "", "https://gamma.app/export/abc", ".pdf"),
    ]
    for nature, cle, url, attendue in cas:
        artefact = DocumentArtifact(
            job=job_livrable, kind=nature, storage_key=cle, download_url=url
        )
        nom = livraison._attachment_filename(artefact, "cmd 42")
        assert nom.endswith(attendue), f"{nature} → {nom}"


@override_settings(EVKHA_LIVRABLE_WORD=True)
def test_un_document_retenu_ne_part_jamais_chez_le_client(
    monkeypatch: pytest.MonkeyPatch, job_livrable: Any
) -> None:
    """LE test qui compte. Envoyer un document que le système déclare
    défectueux serait pire que de ne rien envoyer."""
    from delivery.models import DeliveryStatus
    from integrations.gamma import StubGammaClient
    from monitoring.models import OperationalIncident

    docx, pdf = _artefacts_reels(job_livrable)
    monkeypatch.setattr(
        "documents.livrable_word.assembler_livrable_word",
        lambda job: _LivrableAssemble(
            docx=docx,
            pdf=pdf,
            controle=_Controle([_Anomalie("tableau du compte de résultat vide")]),
        ),
        raising=False,
    )
    courriel = _EmailEnregistreur()

    with pytest.raises(livraison.DeliveryError, match="retenu"):
        livraison.deliver_job(
            job_livrable, email_client=courriel, gamma_client=StubGammaClient()
        )

    assert courriel.envois == [], "aucun e-mail ne doit partir"

    from delivery.models import DeliveryBatch

    lot = DeliveryBatch.objects.get(order=job_livrable.order)
    assert lot.status == DeliveryStatus.FAILED
    assert "tableau du compte de résultat vide" in lot.error_message
    assert OperationalIncident.objects.filter(job=job_livrable).exists()

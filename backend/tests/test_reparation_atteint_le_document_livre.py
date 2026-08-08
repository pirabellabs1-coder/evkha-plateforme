"""Une réparation doit réécrire la représentation que le document LIT.

Un chapitre a deux représentations depuis le lot 2 : `payload` (structurée,
source de vérité) et `content` (markdown, rendu depuis le payload). Le `.docx`
livré est assemblé par `payloads_du_job` — donc depuis `payload`.

Or `regenerate_chapter` passait inconditionnellement par `_generate_chapter`,
qui n'écrit que `content`. La boucle d'auto-correction post-gate réécrivait
donc le markdown, revalidait le markdown, se déclarait satisfaite, et livrait
un document inchangé. Le contrôle et sa réparation jugeaient sur une évidence
que le lecteur ne reçoit jamais (règles 3 et 9).

Ces tests échouent sur le code d'avant (règle 6) et portent la contre-épreuve :
la voie héritée doit rester praticable quand le moteur structuré est éteint.
"""
from __future__ import annotations

from typing import Any, cast

import pytest
from django.test import override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation import runner as moteur
from generation.chapitres.runner import _motifs_stockes
from generation.models import ChapterGeneration, ChapterStatus, GenerationJob
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import ClaudeClient
from orders.models import Order

pytestmark = pytest.mark.django_db

#: Aucun de ces tests n'atteint l'API : la voie de production est remplacée
#: dans chacun d'eux. Le client n'est là que pour satisfaire la signature.
_CLIENT_FACTICE = cast("ClaudeClient", object())


@pytest.fixture
def job() -> GenerationJob:
    offre = Offer.objects.create(
        name="Étude de marché",
        slug="etude-marche-reparation",
        deliverable_type=DeliverableType.MARKET_STUDY,
        gamma_enabled=False,
    )
    client = Customer.objects.create(email="reparation@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id="order_reparation_1", customer=client, offer=offre
    )
    soumission = IntakeSubmission.objects.create(
        order=commande,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "restauration",
            "PAYS": "France",
            "ZONE": "Paris",
            "PROJET": "restaurant de quartier",
        },
    )
    return bootstrap_generation_job(soumission)


@pytest.fixture
def chapitre_ecrit(job: GenerationJob) -> ChapterGeneration:
    """Un chapitre déjà TERMINÉ, avec ses deux représentations remplies."""
    chapitre = job.chapters.get(chapter_number=4)
    chapitre.status = ChapterStatus.DONE
    chapitre.payload = {"chapitre": 4, "titre": "Avant", "resume": "r"}
    chapitre.content = "# markdown d'avant"
    chapitre.save(update_fields=["status", "payload", "content", "updated_at"])
    return chapitre


class _Voies:
    def __init__(self) -> None:
        self.structuree: list[int] = []
        self.markdown: list[int] = []


@pytest.fixture
def voies(monkeypatch: pytest.MonkeyPatch) -> _Voies:
    """Note laquelle des deux voies de production est empruntée."""
    v = _Voies()

    def _structure(job_recu: Any, numero: int, **kwargs: Any) -> Any:
        v.structuree.append(numero)
        chapitre = job_recu.chapters.get(chapter_number=numero)
        chapitre.status = ChapterStatus.DONE
        chapitre.payload = {"chapitre": numero, "titre": "Après", "resume": "r"}
        chapitre.content = "# markdown d'après"
        chapitre.save(
            update_fields=["status", "payload", "content", "updated_at"]
        )
        return chapitre

    def _markdown(job_recu: Any, chapitre: Any, **kwargs: Any) -> None:
        v.markdown.append(chapitre.chapter_number)
        chapitre.status = ChapterStatus.DONE
        chapitre.content = "# markdown d'après"
        chapitre.save(update_fields=["status", "content", "updated_at"])

    # `regenerer_chapitre` importe `produire_chapitre` depuis son propre module :
    # c'est là qu'il faut le remplacer, pas dans `generation.runner`.
    monkeypatch.setattr(
        "generation.chapitres.services.produire_chapitre", _structure
    )
    monkeypatch.setattr(moteur, "_generate_chapter", _markdown)
    monkeypatch.setattr(moteur, "_inline_qa_repair", lambda c: None)
    monkeypatch.setattr(moteur, "socle_verrouille", lambda job: object())
    return v


@override_settings(EVKHA_SOCLE_ENABLED=True)
def test_la_reparation_passe_par_la_voie_structuree(
    job: GenerationJob, chapitre_ecrit: ChapterGeneration, voies: _Voies
) -> None:
    """LE test du défaut : la correction n'atteignait pas le document livré."""
    moteur.regenerate_chapter(
        job, chapitre_ecrit, corrective_note="Le TAM n'est pas sourcé.",
        client=_CLIENT_FACTICE,
    )

    assert voies.structuree == [4], "la réparation doit réécrire le payload"
    assert voies.markdown == [], "la voie markdown ne répare pas le .docx livré"


@override_settings(EVKHA_SOCLE_ENABLED=True)
def test_la_note_corrective_est_transmise_au_modele(
    job: GenerationJob,
    chapitre_ecrit: ChapterGeneration,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La note doit arriver au prompt, pas seulement déclencher un appel.

    On ne redemande pas « fais mieux » : `construire_prompt_chapitre` relit les
    motifs déposés sous `[contrat] ` et les rend au modèle sous « TENTATIVE
    PRÉCÉDENTE REFUSÉE ». On vérifie donc le canal, pas l'intention.
    """
    vu: dict[str, Any] = {}

    def _capture(job_recu: Any, numero: int, **kwargs: Any) -> Any:
        chapitre = job_recu.chapters.get(chapter_number=numero)
        vu["motifs"] = _motifs_stockes(chapitre)
        vu["statut"] = chapitre.status
        return chapitre

    monkeypatch.setattr(
        "generation.chapitres.services.produire_chapitre", _capture
    )
    moteur.regenerate_chapter(
        job, chapitre_ecrit, corrective_note="Le TAM n'est pas sourcé.",
        client=_CLIENT_FACTICE,
    )

    assert vu["motifs"] == ["Le TAM n'est pas sourcé."]
    # Sans cette remise à zéro, `produire_chapitre` est idempotent : il aurait
    # rendu le chapitre DONE tel quel et la correction n'aurait rien fait.
    assert vu["statut"] == ChapterStatus.PENDING


@override_settings(EVKHA_SOCLE_ENABLED=True)
def test_une_reparation_qui_echoue_ne_vide_pas_le_chapitre(
    job: GenerationJob,
    chapitre_ecrit: ChapterGeneration,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contre-épreuve : échouer ne doit pas coûter un chapitre au document.

    `regenerer_chapitre` effaçait `payload` et `content` AVANT de régénérer.
    Une tentative qui échoue laissait donc un chapitre vide — et
    `payloads_du_job` écarte un chapitre vide, ce qui retirait un chapitre
    entier du `.docx`. Garder l'ancienne version le laisse simplement non
    corrigé, ce qui est strictement préférable.
    """
    def _echoue(job_recu: Any, numero: int, **kwargs: Any) -> Any:
        msg = "le modèle a rendu une réponse incomplète"
        raise RuntimeError(msg)

    monkeypatch.setattr(
        "generation.chapitres.services.produire_chapitre", _echoue
    )
    with pytest.raises(RuntimeError):
        moteur.regenerate_chapter(
            job, chapitre_ecrit, corrective_note="note", client=_CLIENT_FACTICE,
        )

    chapitre_ecrit.refresh_from_db()
    assert chapitre_ecrit.payload == {"chapitre": 4, "titre": "Avant", "resume": "r"}
    assert chapitre_ecrit.content == "# markdown d'avant"


@override_settings(EVKHA_SOCLE_ENABLED=False)
def test_sans_le_moteur_structure_la_voie_heritee_reste(
    job: GenerationJob, chapitre_ecrit: ChapterGeneration, voies: _Voies
) -> None:
    """Contre-épreuve : le correctif ne doit pas casser ce qui marchait.

    Moteur structuré éteint, il n'y a pas de `payload` à réécrire : la voie
    markdown redevient la bonne, et elle doit rester praticable.
    """
    moteur.regenerate_chapter(
        job, chapitre_ecrit, corrective_note="note", client=_CLIENT_FACTICE,
    )

    assert voies.markdown == [4]
    assert voies.structuree == []

"""Le moteur établit le socle avant d'écrire le premier chapitre.

`etablir_socle` existait depuis le lot 1 et n'était appelée QUE par une action
de l'administration Django. `run_generation_job` n'en établissait aucun. Le
rendu Word du lot 3 refusait donc de produire le livrable — « aucun socle
verrouillé, ses graphiques n'auraient rien à citer » — et tout le nouveau
moteur restait hors circuit.

Trouvé en produisant un document sur le déploiement réel, pas en relisant du
code : trois lots successifs étaient écrits, testés, et reliés à rien.

Ces tests verrouillent trois choses distinctes : que le socle est établi quand
le drapeau est levé, qu'il ne l'est PAS quand il est baissé — le §16 promet un
repli —, et qu'un socle en échec arrête le job au lieu de laisser produire des
chapitres sans référence commune.
"""
from __future__ import annotations

from typing import Any

import pytest
from django.test import override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation import runner as moteur
from generation.models import GenerationJob, JobStatus
from generation.services import bootstrap_generation_job
from intake.models import IntakeStatus, IntakeSubmission
from orders.models import Order

pytestmark = pytest.mark.django_db


@pytest.fixture
def job() -> GenerationJob:
    offre = Offer.objects.create(
        name="Étude de marché",
        slug="etude-marche-socle",
        deliverable_type=DeliverableType.MARKET_STUDY,
        gamma_enabled=False,
    )
    client = Customer.objects.create(email="socle@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id="order_socle_1", customer=client, offer=offre
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
    return bootstrap_generation_job(soumission)


def _espionner(monkeypatch: pytest.MonkeyPatch, effet: Any = None) -> list[dict[str, Any]]:
    """Remplace `etablir_socle` et note ses appels.

    La production des chapitres est neutralisée par la même occasion : ces
    tests portent sur le socle, et un chapitre structuré relirait en base un
    socle que la doublure n'y a pas écrit. Sans cela, ils échoueraient sur un
    motif qui ne les concerne pas.
    """
    appels: list[dict[str, Any]] = []

    def _faux(job_recu: Any, **kwargs: Any) -> Any:
        appels.append({"job": job_recu, **kwargs})
        if effet is not None:
            raise effet
        return object()

    def _chapitre(job_recu: Any, numero: int, **kwargs: Any) -> Any:
        chapitre = job_recu.chapters.get(chapter_number=numero)
        chapitre.status = "done"
        chapitre.payload = {"chapitre": numero}
        chapitre.content = "# chapitre"
        chapitre.save(update_fields=["status", "payload", "content", "updated_at"])
        return chapitre

    monkeypatch.setattr(moteur, "etablir_socle", _faux)
    monkeypatch.setattr(moteur, "socle_verrouille", lambda job: object())
    monkeypatch.setattr(moteur, "produire_chapitre", _chapitre)
    return appels


@override_settings(EVKHA_SOCLE_ENABLED=True)
def test_le_socle_est_etabli_avant_les_chapitres(
    monkeypatch: pytest.MonkeyPatch, job: GenerationJob
) -> None:
    """LE test du défaut : sans le correctif, aucun appel n'a lieu."""
    appels = _espionner(monkeypatch)

    moteur.run_generation_job(job)

    assert len(appels) == 1, "le socle doit être établi exactement une fois"
    assert appels[0]["job"].pk == job.pk
    # Les variables du brief lui sont transmises : sans elles il n'a rien à
    # ancrer, et le secteur ne pourrait pas piloter les graphiques.
    assert appels[0]["variables"]["SECTEUR"] == "automobile"
    assert appels[0]["variables"]["ZONE"] == "Paris"


@override_settings(EVKHA_SOCLE_ENABLED=False)
def test_sans_le_drapeau_le_moteur_ne_touche_pas_au_socle(
    monkeypatch: pytest.MonkeyPatch, job: GenerationJob
) -> None:
    """Contre-épreuve : le repli du §16 doit rester praticable.

    Sans ce test, le drapeau pourrait cesser d'être lu sans que rien ne le
    dise, et le retour en arrière annoncé n'existerait plus.
    """
    appels = _espionner(monkeypatch)

    moteur.run_generation_job(job)

    assert appels == []
    job.refresh_from_db()
    assert job.status == JobStatus.DONE, "l'ancien moteur continue de produire"


@override_settings(EVKHA_SOCLE_ENABLED=True)
def test_un_socle_en_echec_arrete_le_job(
    monkeypatch: pytest.MonkeyPatch, job: GenerationJob
) -> None:
    """Continuer produirait un document dont aucun chiffre n'est ancré.

    C'est la règle 1 : un contrôle qui ne peut pas juger doit échouer
    bruyamment, pas se taire.
    """
    from generation.socle import SocleGenerationError
    from monitoring.models import OperationalIncident

    _espionner(
        monkeypatch,
        effet=SocleGenerationError(motifs=["zone absente du référentiel"], tentatives=3),
    )

    with pytest.raises(SocleGenerationError):
        moteur.run_generation_job(job)

    job.refresh_from_db()
    assert job.status == JobStatus.FAILED
    assert "Socle non établi" in job.error_message
    assert OperationalIncident.objects.filter(job=job).exists()
    assert job.chapters.filter(status="done").count() == 0, (
        "aucun chapitre ne doit avoir été écrit sans socle"
    )


@override_settings(EVKHA_SOCLE_ENABLED=True)
def test_le_socle_recoit_le_brief_de_recherche(
    monkeypatch: pytest.MonkeyPatch, job: GenerationJob
) -> None:
    """Il est établi APRÈS la recherche web, qui l'alimente.

    Inverser l'ordre le priverait de son ancrage sans qu'aucune erreur ne le
    signale : le socle serait produit, simplement moins bien.
    """
    job.research_brief = "Marché parisien de l'occasion : 180 000 immatriculations."
    job.save(update_fields=["research_brief"])
    appels = _espionner(monkeypatch)

    moteur.run_generation_job(job)

    assert "180 000" in appels[0]["brief_recherche"]

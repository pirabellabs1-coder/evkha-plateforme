"""Les deux défauts qui ont tué `d326557e`, mesurés sur une génération réelle.

Le 10/08/2026, l'étude concurrentielle `d326557e` meurt au chapitre 1 sur :

    `offre` ne figure pas dans le socle verrouillé.
    `service` ne figure pas dans le socle verrouillé.

## Premier défaut : deux sources pour « ce qui peut être cité »

Le matin même, la grille de notation entrait dans le socle et la consigne
disait au modèle de citer ses CODES comme identifiants de figure. Il a obéi.
Mais `valider_chapitre` ne connaissait que `socle.donnees` : les codes vivent
dans `grille_notation`, donc chaque chapitre qui s'en servait était refusé,
rejoué, refusé encore.

C'est la règle 5 — et elle a été enfreinte le jour même où elle servait à
trancher un conflit sur l'échelle de notation. Vue d'un côté, pas de l'autre.

## Second défaut : un statut qui ment, et qui désarme les commandes

`_fail` marquait le JOB entier FAILED à chaque chapitre raté, alors que la
boucle continue juste après — reliquat du temps où un chapitre perdu tuait
l'étude. Trois conséquences se sont enchaînées ce jour-là :

  - le tableau de bord annonçait « échec » pendant que les chapitres
    s'écrivaient ;
  - le suivi l'a cru et s'est arrêté ;
  - `job_cancel` a REFUSÉ d'agir sur une génération qui tournait vraiment.

Un statut faux ne trompe pas seulement le lecteur : il désarme les commandes.
"""
from __future__ import annotations

import datetime as dt

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres.schema import (
    BlocParagraphe,
    ChapitrePayload,
    valider_chapitre,
)
from generation.models import (
    ChapterGeneration,
    ChapterStatus,
    GenerationJob,
    JobStatus,
)
from generation.runner import _fail
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import Concurrent, Critere, DonneeSocle, Socle, Zone
from monitoring.models import OperationalIncident
from orders.models import Order

# ── Défaut 1 : le raccord des identifiants ───────────────────────────────────

CRITERES = [
    Critere(code="offre", intitule="Étendue de l'offre",
            note_1="une seule prestation", note_5="gamme complète"),
    Critere(code="service", intitule="Qualité de service",
            note_1="aucun accompagnement", note_5="suivi personnalisé"),
]


def _socle_note() -> Socle:
    return Socle(
        secteur="or physique",
        zone=Zone(pays="France"),
        date_socle=dt.date(2026, 8, 10),
        donnees=[
            DonneeSocle(
                id="taille_marche", libelle="Marché français", valeur=600,
                unite="MEUR", annee=2026, perimetre=Perimetre.NATIONAL,
                fiabilite=Fiabilite.ESTIMEE,
            )
        ],
        grille_notation=CRITERES,
        concurrents=[
            Concurrent(nom="VeraCash", notes={"offre": 4, "service": 3}),
            Concurrent(nom="AuCOFFRE", notes={"offre": 3, "service": 4}),
        ],
    )


def test_les_codes_de_criteres_sont_citables() -> None:
    """Le défaut exact : le modèle obéissait, la validation le punissait."""
    socle = _socle_note()

    assert socle.identifiants_citables == {"taille_marche", "offre", "service"}


def test_un_chapitre_qui_cite_un_critere_est_accepte() -> None:
    """Vérifié par le contrôle lui-même, pas par la propriété seule.

    C'est ce qui manquait : la propriété aurait pu exister et n'être appelée
    nulle part — le défaut de la règle 8, déjà rencontré cinq fois ici.
    """
    payload = ChapitrePayload(
        chapitre=2,
        titre="Positionnement des concurrents",
        blocs=[BlocParagraphe(texte="Les acteurs se distinguent nettement.")],
        resume="Un résumé d'essai suffisamment long pour tenir sa borne basse.",
        donnees_utilisees=["offre", "service"],
    )

    motifs = valider_chapitre(
        payload,
        numero_attendu=2,
        identifiants_socle=frozenset(_socle_note().identifiants_citables),
        resume_mots_min=5,
        resume_mots_max=80,
    )

    assert motifs == []


def test_un_identifiant_invente_reste_refuse() -> None:
    """CONTRE-ÉPREUVE : on élargit la liste, on ne l'ouvre pas.

    Sans elle, le correctif le plus simple — accepter tout — passerait le test
    ci-dessus et supprimerait le contrôle qui empêche un chapitre d'inventer
    un chiffre. C'est la raison d'être du socle.
    """
    payload = ChapitrePayload(
        chapitre=2,
        titre="Positionnement des concurrents",
        blocs=[BlocParagraphe(texte="Les acteurs se distinguent nettement.")],
        resume="Un résumé d'essai suffisamment long pour tenir sa borne basse.",
        donnees_utilisees=["part_de_marche_inventee"],
    )

    motifs = valider_chapitre(
        payload,
        numero_attendu=2,
        identifiants_socle=frozenset(_socle_note().identifiants_citables),
        resume_mots_min=5,
        resume_mots_max=80,
    )

    assert any("part_de_marche_inventee" in motif for motif in motifs)


def test_un_socle_sans_grille_ne_cite_que_ses_donnees() -> None:
    """CONTRE-ÉPREUVE : rien ne change pour les livrables sans notation."""
    socle = Socle(
        secteur="boulangerie",
        zone=Zone(pays="France"),
        date_socle=dt.date(2026, 8, 10),
        donnees=[
            DonneeSocle(
                id="taille_marche", libelle="Marché", valeur=10, unite="MEUR",
                annee=2026, perimetre=Perimetre.NATIONAL,
                fiabilite=Fiabilite.ESTIMEE,
            )
        ],
    )

    assert socle.identifiants_citables == socle.identifiants


# ── Défaut 2 : le statut qui ment ────────────────────────────────────────────


def _job_en_cours() -> tuple[GenerationJob, ChapterGeneration]:
    offre = Offer.objects.create(
        slug="essai-statut", name="Étude de la concurrence",
        deliverable_type=DeliverableType.COMPETITOR_STUDY,
    )
    client = Customer.objects.create(email="essai-statut@test.local")
    commande = Order.objects.create(
        systeme_order_id="essai-statut", customer=client, offer=offre,
    )
    job = GenerationJob.objects.create(order=commande, status=JobStatus.RUNNING)
    chapitre = ChapterGeneration.objects.create(
        job=job, chapter_number=1, chapter_title="Chapitre d'essai",
        status=ChapterStatus.RUNNING,
    )
    return job, chapitre


@pytest.mark.django_db
def test_un_chapitre_rate_laisse_le_dossier_en_cours() -> None:
    """Le dossier travaille encore : le dire mort est une affirmation fausse.

    Ce test échoue sur le code d'avant, où `_fail` écrivait FAILED sur le job.
    """
    job, chapitre = _job_en_cours()

    _fail(job, chapitre, ValueError("`offre` ne figure pas"), title="Échec ch. 1")

    job.refresh_from_db()
    chapitre.refresh_from_db()
    assert job.status == JobStatus.RUNNING
    assert chapitre.status == ChapterStatus.FAILED


@pytest.mark.django_db
def test_le_motif_n_est_pas_perdu_pour_autant() -> None:
    """Ne plus mentir ne veut pas dire se taire (règle 1).

    Le motif vit sur le chapitre et dans un incident HIGH ; le gate de
    livraison verra le trou.
    """
    job, chapitre = _job_en_cours()

    _fail(job, chapitre, ValueError("`service` ne figure pas"), title="Échec ch. 1")

    chapitre.refresh_from_db()
    assert "`service`" in chapitre.error_message
    incident = OperationalIncident.objects.get(job=job)
    assert incident.details["chapter_number"] == 1
    assert "`service`" in incident.details["error"]


@pytest.mark.django_db
def test_un_dossier_en_cours_redevient_annulable() -> None:
    """La conséquence qui coûtait le plus cher.

    `job_cancel` refuse d'agir sur un job `failed`. Avec l'ancien code, une
    génération vivante devenait donc impossible à arrêter — mesuré le
    10/08/2026 : « ce job ne peut pas être annulé (statut : failed) » sur un
    dossier dont le chapitre suivant s'écrivait.
    """
    from django.test import Client, override_settings

    job, chapitre = _job_en_cours()
    _fail(job, chapitre, ValueError("`offre` ne figure pas"), title="Échec ch. 1")

    with override_settings(DEBUG=True, EVKHA_DASHBOARD_AUTH_DISABLED=True):
        reponse = Client().post(f"/api/dashboard/jobs/{job.id}/cancel/")

    assert reponse.status_code == 200, reponse.content
    job.refresh_from_db()
    assert job.status == JobStatus.CANCELLED

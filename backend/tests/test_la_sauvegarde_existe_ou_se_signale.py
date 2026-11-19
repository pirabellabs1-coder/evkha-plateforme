"""Une sauvegarde existe — ou son absence se voit.

Audit du 19/11/2026. La base vivait dans un volume du serveur et rien ne la
copiait : aucune sauvegarde dans le dépôt, zéro base gérée par l'hébergeur.

Le service `sauvegarde` écrit désormais une copie par jour. Mais une sauvegarde
que personne ne regarde est la garantie la plus trompeuse : elle échoue en
silence et on l'apprend le jour où l'on en a besoin. Ces tests tiennent donc
le TÉMOIN — ce qu'il lit, quand il crie, quand il se tait — et l'accord entre
le fichier Compose et le réglage, qu'aucun des deux ne peut importer de l'autre.

Ils échouent sur le code d'avant : ni service, ni témoin, ni réglage.
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

import pytest
from django.conf import settings
from django.test import override_settings

from monitoring import sauvegardes, tasks
from monitoring.models import IncidentSeverity, IncidentStatus, OperationalIncident

COMPOSE = Path(__file__).resolve().parents[2] / "docker-compose.prod.yml"
JOUR = 24 * 3600


def _copie(dossier: Path, nom: str = "evkha-jour-19.dump", *, octets: int = 50_000,
           age_s: float = 0) -> Path:
    fichier = dossier / nom
    fichier.write_bytes(b"\0" * octets)
    quand = time.time() - age_s
    os.utime(fichier, (quand, quand))
    return fichier


def _etat(dossier: Path | str) -> dict[str, Any]:
    with override_settings(EVKHA_DOSSIER_SAUVEGARDES=str(dossier)):
        return sauvegardes.etat_des_sauvegardes()


# ── Ce que le témoin lit ────────────────────────────────────────────────────


def test_une_copie_du_jour_est_a_jour(tmp_path: Path) -> None:
    _copie(tmp_path, age_s=3600)

    etat = _etat(tmp_path)

    assert etat["etat"] == "à jour"
    assert etat["fichier"] == "evkha-jour-19.dump"
    assert etat["copies_gardees"] == 1


def test_une_copie_de_trois_jours_est_en_retard(tmp_path: Path) -> None:
    _copie(tmp_path, age_s=3 * JOUR)

    assert _etat(tmp_path)["etat"] == "en retard"


def test_c_est_la_plus_recente_qui_compte(tmp_path: Path) -> None:
    """Contre-épreuve : trente copies anciennes ne cachent pas celle du jour,
    et celle du jour ne se cache pas derrière elles."""
    _copie(tmp_path, "evkha-jour-01.dump", age_s=18 * JOUR)
    _copie(tmp_path, "evkha-jour-19.dump", age_s=600)

    etat = _etat(tmp_path)

    assert etat["etat"] == "à jour"
    assert etat["fichier"] == "evkha-jour-19.dump"
    assert etat["copies_gardees"] == 2


def test_un_fichier_de_quelques_octets_n_est_pas_une_sauvegarde(tmp_path: Path) -> None:
    """`pg_dump` écrit un en-tête même quand il échoue : sans seuil de taille,
    une copie vide serait dite « à jour »."""
    _copie(tmp_path, octets=200)

    assert _etat(tmp_path)["etat"] == "aucune"


def test_la_copie_en_cours_n_est_pas_prise_pour_une_copie_finie(tmp_path: Path) -> None:
    _copie(tmp_path, "en-cours.partiel", octets=500_000)

    assert _etat(tmp_path)["etat"] == "aucune"


def test_un_dossier_absent_se_dit_tel_quel(tmp_path: Path) -> None:
    """Le volume n'est pas monté : ce n'est pas « rien à surveiller »."""
    assert _etat(tmp_path / "pas-monte")["etat"] == "dossier absent"


def test_sans_reglage_rien_n_est_attendu() -> None:
    """Contre-épreuve : un poste de développement n'a pas de sauvegarde, et ce
    n'est pas une panne."""
    assert _etat("")["etat"] == "non configurée"


# ── Quand il crie, quand il se tait ─────────────────────────────────────────


@pytest.mark.django_db
def test_une_copie_manquante_ouvre_un_incident_et_un_seul(tmp_path: Path) -> None:
    with override_settings(EVKHA_DOSSIER_SAUVEGARDES=str(tmp_path)):
        assert tasks.verifier_la_sauvegarde() == "aucune"
        tasks.verifier_la_sauvegarde()

    incident = OperationalIncident.objects.get()
    assert incident.severity == IncidentSeverity.HIGH
    assert incident.details["type"] == tasks.TYPE_SAUVEGARDE


@pytest.mark.django_db
def test_un_incident_pris_en_compte_n_est_pas_rouvert_chaque_heure(tmp_path: Path) -> None:
    with override_settings(EVKHA_DOSSIER_SAUVEGARDES=str(tmp_path)):
        tasks.verifier_la_sauvegarde()
        OperationalIncident.objects.update(status=IncidentStatus.ACKNOWLEDGED)
        tasks.verifier_la_sauvegarde()

    assert OperationalIncident.objects.count() == 1


@pytest.mark.django_db
def test_l_incident_se_clot_quand_la_copie_revient(tmp_path: Path) -> None:
    with override_settings(EVKHA_DOSSIER_SAUVEGARDES=str(tmp_path)):
        tasks.verifier_la_sauvegarde()
        _copie(tmp_path)
        assert tasks.verifier_la_sauvegarde() == "à jour"

    incident = OperationalIncident.objects.get()
    assert incident.status == IncidentStatus.RESOLVED
    assert incident.resolved_at is not None


@pytest.mark.django_db
def test_une_copie_a_jour_n_ouvre_rien(tmp_path: Path) -> None:
    """Contre-épreuve."""
    _copie(tmp_path)

    with override_settings(EVKHA_DOSSIER_SAUVEGARDES=str(tmp_path)):
        tasks.verifier_la_sauvegarde()

    assert not OperationalIncident.objects.exists()


@pytest.mark.django_db
def test_sans_reglage_le_temoin_ne_crie_pas() -> None:
    """Contre-épreuve : la suite et les postes de développement n'ouvrent pas
    un incident à chaque passage."""
    with override_settings(EVKHA_DOSSIER_SAUVEGARDES=""):
        assert tasks.verifier_la_sauvegarde() == "non configurée"

    assert not OperationalIncident.objects.exists()


# ── Le service, le témoin et le réglage se répondent ────────────────────────


def _service(nom: str) -> str:
    """Le bloc d'un service du fichier Compose, commentaires retirés."""
    texte = COMPOSE.read_text(encoding="utf-8")
    trouve = re.search(rf"^  {re.escape(nom)}:\n(.*?)(?=^  [a-z][\w-]*:\n|^volumes:)",
                       texte, re.M | re.S)
    assert trouve is not None, f"service « {nom} » introuvable dans le fichier Compose"
    return "\n".join(
        ligne for ligne in trouve.group(1).splitlines() if not ligne.strip().startswith("#")
    )


def test_le_service_ecrit_la_ou_le_temoin_regarde() -> None:
    service = _service("sauvegarde")
    ecrit = re.search(r"mv \S+ (/\S+)/evkha-jour-", service)
    assert ecrit is not None, "le service ne range plus sa copie sous `evkha-jour-…`"

    assert ecrit.group(1) == "/sauvegardes"
    assert "- sauvegardes:/sauvegardes\n" in service + "\n"
    # Le nom que le service donne à une copie finie est celui que le témoin lit.
    assert Path("evkha-jour-19.dump").match(sauvegardes.MOTIF)
    assert not Path("en-cours.partiel").match(sauvegardes.MOTIF)


@pytest.mark.parametrize("service", ["api", "worker-livraison"])
def test_ceux_qui_lisent_la_copie_ont_le_volume(service: str) -> None:
    """La console (`api`) et l'ouvrier qui joue le témoin : sans le montage,
    l'un et l'autre liraient « dossier absent » pour toujours."""
    assert "- sauvegardes:/sauvegardes:ro" in _service(service)


def test_le_service_n_efface_jamais_rien() -> None:
    """Trente et un emplacements qui se remplacent : aucune commande de
    suppression dans un service qui tient les copies de la base."""
    service = _service("sauvegarde")

    assert not re.search(r"\brm\b|-delete\b|\bDROP\b", service)


def test_hors_developpement_une_sauvegarde_est_attendue() -> None:
    """Le défaut de production n'est pas « rien à surveiller ». Lu dans le
    source : la suite tourne en DEBUG, où le défaut est vide à dessein."""
    source = (Path(settings.BASE_DIR) / "backend" / "evkha" / "settings.py").read_text(
        encoding="utf-8"
    )
    trouve = re.search(
        r'"EVKHA_DOSSIER_SAUVEGARDES",\s*default="" if DEBUG else "([^"]+)"', source
    )

    assert trouve is not None
    assert trouve.group(1) == "/sauvegardes"


def test_le_temoin_est_au_calendrier_et_dans_la_file_courte() -> None:
    """Une tâche écrite et jamais planifiée ne surveille rien (règle 8) ; et
    planifiée dans la file des générations, elle attendrait derrière elles —
    sur un ouvrier qui n'a pas le volume."""
    periodiques = {str(e["task"]) for e in settings.CELERY_BEAT_SCHEDULE.values()}

    assert tasks.verifier_la_sauvegarde.name in periodiques
    assert settings.CELERY_TASK_ROUTES[tasks.verifier_la_sauvegarde.name] == {
        "queue": "livraison"
    }


@pytest.mark.django_db
def test_la_console_dit_l_age_de_la_derniere_copie(client_admin: Any, tmp_path: Path) -> None:
    _copie(tmp_path, age_s=7200)

    with override_settings(EVKHA_DOSSIER_SAUVEGARDES=str(tmp_path)):
        etat = client_admin.get("/api/dashboard/system/").json()["sauvegarde"]

    assert etat["etat"] == "à jour"
    assert 1.9 <= etat["age_heures"] <= 2.1

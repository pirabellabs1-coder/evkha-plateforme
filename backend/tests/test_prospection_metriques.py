"""Phase 5 : les métriques, recomptées depuis les Evenement (une seule vérité)."""
from __future__ import annotations

import json
from typing import Any

import pytest
from django.utils import timezone
from prospection.models import (
    Campagne,
    Evenement,
    Message,
    Prospect,
    StatutMessage,
    StatutProspect,
    TypeEvenement,
)

pytestmark = pytest.mark.django_db

BASE = "/api/dashboard/prospection"


def test_les_metriques_exigent_le_jeton() -> None:
    from django.test import Client
    assert Client().get(f"{BASE}/metriques/").status_code in (401, 403)


def test_les_taux_se_calculent_depuis_les_evenements(client_admin: Any) -> None:
    campagne = Campagne.objects.create(nom="C")
    # Deux prospects contactés, un converti.
    p1 = Prospect.objects.create(campagne=campagne, raison_sociale="A", email="a@a.fr",
                                 statut=StatutProspect.CONTACTE)
    p2 = Prospect.objects.create(campagne=campagne, raison_sociale="B", email="b@b.fr",
                                 statut=StatutProspect.CONVERTI)
    for p in (p1, p2):
        m = Message.objects.create(prospect=p, campagne=campagne, objet="O", corps="x",
                                   statut=StatutMessage.ENVOYE)
        if p is p1:
            # p1 ouvre deux fois : une ouverture UNIQUE, deux au total.
            Evenement.objects.create(message=m, type=TypeEvenement.OUVERT,
                                     horodatage=timezone.now())
            Evenement.objects.create(message=m, type=TypeEvenement.OUVERT,
                                     horodatage=timezone.now())

    d = json.loads(client_admin.get(f"{BASE}/metriques/").content)
    assert d["envoyes"] == 2
    assert d["ouvertures"] == 1 and d["ouvertures_total"] == 2
    assert d["taux_ouverture"] == 50.0  # 1 message ouvert sur 2 envoyés
    assert d["prospects_contactes"] == 2 and d["conversions"] == 1
    assert d["taux_conversion"] == 50.0

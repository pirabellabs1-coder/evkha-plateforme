"""Trois points que les relectures du 20/11/2026 avaient laissés hors du lot.

1. **La charge des webhooks.** L'événement Stripe entier était écrit en base
   (`WebhookEvent.raw_payload`) : l'identifiant de session complet, le nom et
   l'adresse de l'acheteur, lisibles dans l'administration.
2. **Le prélèvement refusé.** `checkout.session.async_payment_failed` n'était
   pas écouté : ni incident, ni phrase juste sur la page de retour.
3. **Les plafonds.** Lus puis comptés : une salve de requêtes parties
   ensemble lisait « sous le plafond » d'un bout à l'autre.

Chaque test échoue sur le code d'avant (règle 6), sauf les contre-épreuves.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from django.test.utils import override_settings
from paiement import vues as vues_de_paiement

from integrations.models import WebhookEvent, WebhookStatus
from monitoring.models import OperationalIncident
from organisations import limitation, retours, vues_espace
from organisations.models import (
    EtatTentative,
    MouvementCredit,
    ObjetTentative,
    TentativePaiement,
)
from tests.test_achat_a_l_unite import offre_a_l_unite
from tests.test_achat_a_l_unite import session_stripe as session_d_etude
from tests.test_achat_de_formation import REGLAGES, _stripe_en_doublure
from tests.test_audit_des_formations_du_20_novembre import (
    RETOURS,
    _poster,
    _relectures,
)
from tests.test_barriere_de_paiement import SECRET_WEBHOOK, Inscrit, poster_evenement

pytestmark = pytest.mark.django_db


def _evenement(session: dict[str, Any], nature: str = "completed") -> dict[str, Any]:
    return {
        "id": f"evt_{uuid.uuid4().hex[:16]}",
        "type": f"checkout.session.{nature}",
        "livemode": False,
        "data": {"object": session},
    }


# ── 1. Ce qu'on écrit en base d'un événement ─────────────────────────────────


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
def test_la_charge_enregistree_ne_porte_ni_la_session_ni_l_acheteur() -> None:
    session = session_d_etude(offre_a_l_unite(), email="camille.durand@example.com")
    session["payment_intent"] = "pi_3QabcDEF456ghiJKL"
    session["customer_details"]["address"] = {"line1": "12 rue des Lilas", "city": "Lille"}
    session["customer_details"]["phone"] = "+33612345678"
    session["champ_que_stripe_ajoutera_demain"] = "valeur inconnue"

    reponse = poster_evenement(_evenement(session))

    assert reponse.status_code == 200, reponse.content
    enregistre = WebhookEvent.objects.get()
    ecrit = json.dumps(enregistre.raw_payload, ensure_ascii=False)
    for interdit in (
        session["id"], "camille.durand@example.com", "Camille Porteuse",
        "rue des Lilas", "+33612345678", "valeur inconnue",
    ):
        assert interdit not in ecrit, interdit
    # Ce qui sert à comprendre après coup y est toujours.
    objet = enregistre.raw_payload["data"]["object"]
    assert enregistre.raw_payload["type"] == "checkout.session.completed"
    assert objet["amount_total"] == session["amount_total"]
    assert objet["payment_intent"] == "pi_3QabcDEF456ghiJKL"
    assert objet["metadata"]["achat"] == "livrable"
    assert objet["id"].startswith("cs_test_") and "…" in objet["id"]


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
def test_contre_epreuve_le_traitement_recoit_toujours_l_evenement_entier() -> None:
    """Expurger ce qu'on GARDE ne doit rien retirer à ce qu'on TRAITE : l'achat
    est livré à la bonne adresse, et le rejeu reste reconnu comme doublon."""
    session = session_d_etude(offre_a_l_unite(), email="camille.durand@example.com")
    evenement = _evenement(session)

    assert poster_evenement(evenement).json()["verdict"].startswith("achat a l'unite livre")
    assert MouvementCredit.objects.filter(reference=session["id"]).count() == 1
    assert WebhookEvent.objects.get().status == WebhookStatus.PROCESSED

    rejeu = poster_evenement(evenement)
    assert rejeu.json() == {"recu": True, "doublon": True}
    assert MouvementCredit.objects.count() == 1


def test_un_message_d_erreur_ne_garde_ni_session_ni_adresse() -> None:
    """Une erreur d'intégrité cite la valeur qui a heurté la contrainte."""
    reference = "cs_test_a1B2c3D4e5F6g7H8i9J0"
    brut = (
        f'duplicate key value violates unique constraint: Key (reference)=({reference}) '
        "already exists ; Key (email)=(camille.durand@example.com)"
    )

    propre = vues_de_paiement.sans_secrets(brut)

    assert reference not in propre
    assert "camille.durand@example.com" not in propre
    assert "duplicate key value" in propre
    assert "<adresse>" in propre


# ── 2. Le prélèvement refusé par la banque ───────────────────────────────────


def _etude_en_attente() -> dict[str, Any]:
    """Une étude payée par prélèvement : terminée, pas encore encaissée."""
    session = session_d_etude(offre_a_l_unite(), payee=False)
    TentativePaiement.objects.create(
        objet=ObjetTentative.LIVRABLE,
        reference_session=session["id"],
        montant_cents=session["amount_total"],
        devise="EUR",
    )
    return session


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK, **REGLAGES)
def test_un_prelevement_refuse_ouvre_un_incident_et_change_la_page_de_retour(
    monkeypatch: Any,
) -> None:
    session = _etude_en_attente()
    session["payment_intent"] = "pi_3QabcDEF456ghiJKL"
    _relectures(monkeypatch, session)

    avant = _poster(RETOURS["livrable"], {"session": session["id"]})
    assert avant.json()["code"] == "paiement_en_attente"

    reponse = poster_evenement(_evenement(session, "async_payment_failed"))

    assert reponse.status_code == 200, reponse.content
    assert reponse.json()["verdict"] == "paiement differe refuse (livrable)"
    incident = OperationalIncident.objects.get()
    assert incident.title == "Paiement differe refuse par la banque"
    assert incident.details["paiement"] == "pi_3QabcDEF456ghiJKL"
    assert session["id"] not in json.dumps(incident.details)
    assert TentativePaiement.objects.get().etat == EtatTentative.ABANDONNEE

    apres = _poster(RETOURS["livrable"], {"session": session["id"]})
    assert (apres.status_code, apres.json()["code"]) == (409, "paiement_refuse")
    assert "encore le confirmer" not in apres.json()["erreur"]
    assert MouvementCredit.objects.count() == 0


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
def test_contre_epreuve_un_echec_tardif_ne_defait_pas_un_encaissement() -> None:
    session = _etude_en_attente()
    TentativePaiement.objects.update(etat=EtatTentative.PAYEE)

    poster_evenement(_evenement(session, "async_payment_failed"))

    assert TentativePaiement.objects.get().etat == EtatTentative.PAYEE


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
def test_contre_epreuve_l_echec_d_une_souscription_n_est_pas_traite_ici() -> None:
    """Elle a sa propre annonce (`invoice.payment_failed`) : pas d'incident en double."""
    session = {
        "id": f"cs_test_{uuid.uuid4().hex[:16]}",
        "mode": "subscription",
        "status": "complete",
        "payment_status": "unpaid",
        "metadata": {"organisation_id": str(uuid.uuid4()), "formule_code": "pro"},
    }

    reponse = poster_evenement(_evenement(session, "async_payment_failed"))

    assert reponse.json()["verdict"] == "paiement differe refuse hors achat, ignore"
    assert OperationalIncident.objects.count() == 0


# ── 3. Les plafonds : comptés et jugés d'un seul geste ───────────────────────


def test_compter_juge_sur_la_valeur_qu_il_vient_d_ecrire() -> None:
    plafond = limitation.Plafond(f"essai-{uuid.uuid4().hex[:8]}", maximum=2, fenetre_s=60)

    assert [limitation.compter(plafond, "a") for _ in range(4)] == [True, True, False, False]
    # Contre-épreuve : un autre identifiant a son propre compteur.
    assert limitation.compter(plafond, "b") is True


def _salve(monkeypatch: Any) -> None:
    """Des requêtes parties ENSEMBLE : chacune lit « sous le plafond » avant
    qu'aucune n'ait compté. C'est ce que rend `depasse` à toutes."""
    monkeypatch.setattr(limitation, "depasse", lambda *_: False)


@override_settings(**REGLAGES)
def test_une_salve_d_ouvertures_dans_l_espace_ne_passe_pas_le_plafond(
    monkeypatch: Any,
) -> None:
    cliente = Inscrit()
    envois = _stripe_en_doublure(monkeypatch)
    monkeypatch.setattr(
        vues_espace,
        "OUVERTURES_PAR_ORGANISATION",
        limitation.Plafond(f"salve-{uuid.uuid4().hex[:8]}", maximum=2, fenetre_s=3600),
    )
    _salve(monkeypatch)
    charge = {"etude": offre_a_l_unite().slug}

    codes = [
        _poster("/api/espace/etudes/acheter/", charge, headers=cliente.entetes).status_code
        for _ in range(4)
    ]

    assert codes == [200, 200, 429, 429]
    assert len(envois) == 2, "la salve est partie chez Stripe malgré le plafond"


@override_settings(**REGLAGES)
def test_une_salve_d_ouvertures_publiques_ne_passe_pas_le_plafond(
    monkeypatch: Any,
) -> None:
    from organisations import vues_publiques  # noqa: PLC0415

    envois = _stripe_en_doublure(monkeypatch)
    monkeypatch.setattr(
        vues_publiques,
        "PAIEMENTS_PAR_HEURE",
        limitation.Plafond(f"salve-{uuid.uuid4().hex[:8]}", maximum=2, fenetre_s=3600),
    )
    _salve(monkeypatch)
    charge = {"livrable": offre_a_l_unite().slug}

    codes = [_poster("/api/public/acheter/", charge).status_code for _ in range(3)]

    assert codes == [200, 200, 429]
    assert len(envois) == 2


@override_settings(**REGLAGES)
def test_une_salve_de_retours_ne_passe_pas_le_plafond(monkeypatch: Any) -> None:
    parties = _relectures(monkeypatch)
    monkeypatch.setattr(
        retours,
        "RETOURS_PAR_HEURE",
        limitation.Plafond(f"salve-{uuid.uuid4().hex[:8]}", maximum=2, fenetre_s=3600),
    )
    _salve(monkeypatch)
    charge = {"session": f"cs_test_{uuid.uuid4().hex[:16]}"}

    codes = [_poster(RETOURS["livrable"], charge).status_code for _ in range(3)]

    assert codes == [503, 503, 429]
    assert len(parties) == 2, "le troisième identifiant est parti chez Stripe"


class _CacheEnPanne:
    """Cache dont chaque appel échoue, comme un Redis injoignable."""

    def __getattr__(self, _: str) -> Any:
        def echec(*__: Any, **___: Any) -> Any:
            raise ConnectionError("cache injoignable")

        return echec


def test_contre_epreuve_un_cache_en_panne_ne_ferme_pas_les_paiements(
    monkeypatch: Any,
) -> None:
    """Même arbitrage que `depasse` : la protection tombe, pas le service."""
    monkeypatch.setattr(limitation, "cache", _CacheEnPanne())
    plafond = limitation.Plafond("essai-panne", maximum=1, fenetre_s=60)

    assert [limitation.compter(plafond, "a") for _ in range(3)] == [True, True, True]


def test_une_metadonnee_que_nous_ne_posons_pas_n_est_pas_gardee() -> None:
    gardee = vues_de_paiement.charge_a_conserver({
        "id": "evt_1",
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_test_a1B2c3D4e5F6g7H8i9J0",
            "metadata": {
                "achat": "livrable",
                "telephone": "+33612345678",
                "organisation_id": None,
            },
        }},
    })

    assert gardee["data"]["object"]["metadata"] == {"achat": "livrable"}


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
def test_un_traitement_en_echec_n_ecrit_ni_session_ni_adresse(
    monkeypatch: Any, caplog: Any
) -> None:
    """Le message d'une erreur d'intégrité part en base ET au journal."""
    reference = "cs_test_a1B2c3D4e5F6g7H8i9J0"

    def echec(_: Any) -> str:
        raise RuntimeError(f"Key (reference)=({reference}) ; camille.durand@example.com")

    monkeypatch.setattr(vues_de_paiement, "traiter", echec)

    reponse = poster_evenement(_evenement({"id": reference, "metadata": {}}))

    assert reponse.status_code == 500
    enregistre = WebhookEvent.objects.get()
    assert enregistre.status == WebhookStatus.FAILED
    for ecrit in (enregistre.error_message, caplog.text):
        assert reference not in ecrit
        assert "camille.durand@example.com" not in ecrit
    assert "RuntimeError" in caplog.text

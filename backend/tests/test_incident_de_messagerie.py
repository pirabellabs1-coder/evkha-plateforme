"""Un courriel qui ne part pas doit se voir. Il ne se voyait nulle part.

Mesuré le 07/08/2026, et c'est le pire silence rencontré sur ce dépôt.

`api.resend.com` est derrière Cloudflare, qui bannissait l'agent utilisateur
par défaut d'`urllib`. AUCUN courriel ne partait — ni invitation à rejoindre un
espace, ni lien de mot de passe. Et rien, absolument rien, ne le disait :

- pas d'erreur à l'écran : `_envoyer` rattrape et rend `False`, à dessein ;
- rien dans l'administration : aucun incident n'était ouvert ;
- rien chez le prestataire : la requête était refusée AVANT lui ;
- une ligne de journal, dans un conteneur dont les journaux ne sont pas
  consultables depuis l'extérieur.

La ligne de journal donnait l'illusion d'une surveillance qui n'existait pas.
C'est la règle 1 : un contrôle qui n'alerte personne n'est pas un contrôle.

Le rattrapage de l'exception reste juste — une invitation dont le courriel n'est
pas parti demeure une invitation valide, et son lien peut être recopié à
l'écran. Ce qui manquait, c'est la TRACE.
"""
from __future__ import annotations

from typing import Any

import pytest

from monitoring.models import OperationalIncident
from organisations import courriels


class _ClientEnPanne:
    def __init__(self, erreur: Exception) -> None:
        self._erreur = erreur

    def send_delivery_email(self, **_: Any) -> None:
        raise self._erreur


@pytest.fixture
def en_panne(monkeypatch: pytest.MonkeyPatch) -> Any:
    def poser(erreur: Exception) -> None:
        from integrations import brevo

        monkeypatch.setattr(
            brevo, "get_transactional_email_client", lambda: _ClientEnPanne(erreur)
        )

    return poser


@pytest.mark.django_db
def test_un_envoi_qui_echoue_ouvre_un_incident(en_panne: Any) -> None:
    """Sur le code d'avant, cette panne ne laissait AUCUNE trace en base."""
    en_panne(RuntimeError("RESEND_API_KEY manquante"))

    parti = courriels._envoyer(
        destinataire="partenaire@exemple.fr",
        sujet="Rejoindre l'espace",
        corps_html="<p>Bonjour</p>",
    )

    assert parti is False
    incidents = OperationalIncident.objects.all()
    assert incidents.count() == 1
    details = incidents[0].details
    assert details["type"] == courriels.INCIDENT_TYPE_COURRIEL
    assert details["destinataire"] == "partenaire@exemple.fr"
    assert details["sujet"] == "Rejoindre l'espace"
    assert "RESEND_API_KEY manquante" in details["motif"]


@pytest.mark.django_db
def test_le_motif_conserve_le_corps_de_la_reponse(en_panne: Any) -> None:
    """« HTTP Error 403 » n'apprend rien ; le corps porte la cause.

    C'est la règle 2 : un motif d'échec doit être trouvable par son lecteur.
    Le défaut réel disait « Error 1010 — browser_signature_banned », et c'est
    cette phrase qui a permis de comprendre en une lecture.
    """
    import urllib.error

    erreur = urllib.error.HTTPError(
        url="https://api.resend.com/emails",
        code=403,
        msg="Forbidden",
        hdrs=None,  # type: ignore[arg-type]
        fp=None,
    )
    # `HTTPError.read()` rend le corps quand il y en a un ; on le simule.
    erreur.read = lambda: b'{"error_name":"browser_signature_banned"}'  # type: ignore[method-assign]
    en_panne(erreur)

    courriels._envoyer(
        destinataire="a@b.fr", sujet="s", corps_html="<p>h</p>",
    )

    motif = OperationalIncident.objects.get().details["motif"]
    assert "browser_signature_banned" in motif


@pytest.mark.django_db
def test_un_envoi_reussi_n_ouvre_aucun_incident(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contre-épreuve : on n'inonde pas la supervision d'incidents vides."""
    from integrations import brevo

    class _ClientQuiMarche:
        def send_delivery_email(self, **_: Any) -> object:
            return object()

    monkeypatch.setattr(
        brevo, "get_transactional_email_client", lambda: _ClientQuiMarche()
    )

    assert courriels._envoyer(destinataire="a@b.fr", sujet="s", corps_html="h") is True
    assert not OperationalIncident.objects.exists()


@pytest.mark.django_db
def test_une_supervision_indisponible_n_annule_pas_l_action(
    en_panne: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L'incident ne doit pas faire échouer ce qu'il documente.

    Une invitation valide serait annulée parce que la table des incidents est
    indisponible : le remède serait pire que le mal.
    """
    en_panne(RuntimeError("prestataire injoignable"))
    monkeypatch.setattr(
        OperationalIncident.objects,
        "create",
        lambda **_: (_ for _ in ()).throw(RuntimeError("base indisponible")),
    )

    # Ne doit pas lever.
    assert courriels._envoyer(destinataire="a@b.fr", sujet="s", corps_html="h") is False

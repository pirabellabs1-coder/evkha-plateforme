"""Le verrou d'envoi ne porte que sur le MESSAGE (audit du 19/11/2026).

`services.envoyer_message` relisait le message par
`select_for_update().select_related("prospect", "sequence")`. `Message.sequence`
est nullable, donc joint en LEFT OUTER JOIN, et PostgreSQL refuse `FOR UPDATE`
sur le côté nullable d'une jointure externe (`NotSupportedError`). SQLite ignore
la clause : toute la suite passait, et la production rendait 500 sur « Envoyer »
et « Tout envoyer » — aucun envoi ne pouvait aboutir.

La suite tourne sur SQLite : on ne peut pas y voir l'erreur de PostgreSQL. On
juge donc la FORME de la requête de verrouillage (ce que Django enverra), et on
garde la classe entière par une lecture du code : tout `select_for_update` de la
prospection doit dire ce qu'il verrouille.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import prospection
import pytest
from django.db.models.query import QuerySet
from prospection import services
from prospection.models import Campagne, Message, Prospect, Sequence, StatutMessage

import dashboard.prospection
from integrations.brevo import EmailSendResult

pytestmark = pytest.mark.django_db


class _ClientEspion:
    def __init__(self) -> None:
        self.envois = 0

    def send_delivery_email(self, **_: Any) -> EmailSendResult:
        self.envois += 1
        return EmailSendResult(provider_message_id=f"brevo-{self.envois}")


def _espionner_les_verrous(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, Any, Any]]:
    """Note chaque `get()` posé sur une requête verrouillante : (modèle, of, jointures)."""
    vus: list[tuple[Any, Any, Any]] = []
    original = QuerySet.get

    def espion(self: Any, *args: Any, **kwargs: Any) -> Any:
        if self.query.select_for_update:
            vus.append((self.model, self.query.select_for_update_of, self.query.select_related))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(QuerySet, "get", espion)
    return vus


def _message_valide(*, avec_sequence: bool) -> Message:
    campagne = Campagne.objects.create(nom="Verrou")
    prospect = Prospect.objects.create(
        campagne=campagne, raison_sociale="Cible", email="contact@cible.fr"
    )
    sequence = Sequence.objects.create(campagne=campagne, ordre=0) if avec_sequence else None
    return Message.objects.create(
        prospect=prospect, campagne=campagne, sequence=sequence, objet="O", corps="<p>x</p>",
        statut=StatutMessage.VALIDE, valide_par="Evangéline",
    )


@pytest.mark.parametrize("avec_sequence", [False, True])
def test_le_verrou_d_envoi_ne_porte_que_sur_le_message(
    monkeypatch: pytest.MonkeyPatch, avec_sequence: bool
) -> None:
    """`FOR UPDATE OF <message>` : jamais sur le côté nullable de la jointure.

    Sur le code d'avant, `select_for_update_of` valait `()` : le verrou visait
    aussi `sequence`, jointe en externe — ce que PostgreSQL refuse.
    """
    vus = _espionner_les_verrous(monkeypatch)
    message = _message_valide(avec_sequence=avec_sequence)
    espion = _ClientEspion()

    services.envoyer_message(message, client=espion)

    # Un contrôle qui n'a rien à comparer échoue (règle 1) : si l'envoi ne
    # verrouillait plus rien, ce test ne jugerait rien non plus.
    assert vus, "envoyer_message ne pose plus aucun verrou : rien n'a été jugé"
    for modele, verrouille, jointures in vus:
        assert modele is Message
        assert jointures, "le message est relu AVEC son prospect et sa séquence"
        assert verrouille == ("self",), (
            f"verrou posé sur {verrouille!r} : avec une jointure externe (sequence "
            "est nullable), PostgreSQL lève NotSupportedError"
        )
    # Contre-épreuve : le correctif ne casse pas l'envoi, et le verrou reste demandé.
    assert espion.envois == 1
    message.refresh_from_db()
    assert message.statut == StatutMessage.ENVOYE


def _verrous_sans_cible(source: str) -> list[int]:
    """Les lignes d'un source où `select_for_update` est appelé sans `of=`."""
    return [
        noeud.lineno
        for noeud in ast.walk(ast.parse(source))
        if isinstance(noeud, ast.Call)
        and isinstance(noeud.func, ast.Attribute)
        and noeud.func.attr == "select_for_update"
        and "of" not in {motcle.arg for motcle in noeud.keywords}
    ]


def _sources_de_la_prospection() -> list[Path]:
    dossier = Path(prospection.__file__).parent
    return [*sorted(dossier.glob("*.py")), Path(dashboard.prospection.__file__)]


def test_tout_verrou_de_la_prospection_dit_ce_qu_il_verrouille() -> None:
    """La CLASSE, pas l'exemple (règle 4) : aucun `select_for_update()` nu.

    Un verrou sans `of=` verrouille toutes les tables jointes ; il suffit qu'un
    `select_related` suive une relation nullable pour que PostgreSQL refuse la
    requête, sans qu'un seul test sur SQLite le voie. Sur le code d'avant,
    `services.envoyer_message` en portait un.
    """
    fichiers = _sources_de_la_prospection()
    sources = {f: f.read_text(encoding="utf-8") for f in fichiers}
    assert any("select_for_update" in s for s in sources.values()), (
        "aucun select_for_update dans la prospection : la garde n'a rien à comparer"
    )
    fautifs = {
        f.name: lignes for f, s in sources.items() if (lignes := _verrous_sans_cible(s))
    }
    assert not fautifs, f"select_for_update() sans `of=` : {fautifs}"


def test_la_garde_des_verrous_voit_bien_un_verrou_nu() -> None:
    """Contre-épreuve de la garde : elle détecte le défaut, et laisse le correct."""
    nu = "qs = Message.objects.select_for_update().select_related('sequence').get(pk=1)\n"
    cible = "qs = Message.objects.select_for_update(of=('self',)).get(pk=1)\n"
    assert _verrous_sans_cible(nu) == [1]
    assert _verrous_sans_cible(cible) == []

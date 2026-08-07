"""Le mot de passe PostgreSQL de production n'a jamais été changé depuis sa fuite.

Il a été exposé en début de projet, dans une lecture de variables
d'environnement mal filtrée. Le remplacer semble trivial ; ça ne l'est pas.

**Modifier `POSTGRES_PASSWORD` dans Coolify ne change RIEN.** L'image
PostgreSQL ne lit cette variable qu'à la première initialisation d'un volume
vide. Le volume de production existe depuis des mois : l'utilisateur garderait
son mot de passe — donc le mot de passe fuité resterait valide — et
l'application, elle, ne pourrait plus se connecter. Le pire des deux mondes :
panne totale, sans rien avoir sécurisé.

Le vrai changement passe par `ALTER USER`, depuis une connexion déjà
authentifiée.

Ces tests tiennent ce qui peut mal tourner :

1. sans variable, la commande ne fait RIEN — elle reste dans la chaîne de
   démarrage en permanence ;
2. un mot de passe court est REFUSÉ plutôt qu'accepté : un mot de passe faible
   posé sur une base de production ne se remarque jamais avant l'incident ;
3. la valeur est échappée par le pilote, jamais concaténée ;
4. la commande dit ce qu'il faut faire ENSUITE — s'arrêter là laisserait la
   base et la configuration en désaccord.
"""
from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command

MOT_DE_PASSE_VALABLE = "un-mot-de-passe-de-trente-six-signes"


def _jouer(monkeypatch: pytest.MonkeyPatch, valeur: str | None) -> str:
    monkeypatch.delenv("EVKHA_NOUVEAU_MOT_DE_PASSE_PG", raising=False)
    if valeur is not None:
        monkeypatch.setenv("EVKHA_NOUVEAU_MOT_DE_PASSE_PG", valeur)
    sortie = StringIO()
    call_command("changer_le_mot_de_passe_postgres", stdout=sortie)
    return sortie.getvalue()


@pytest.mark.django_db
def test_sans_variable_la_commande_ne_fait_rien(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Elle reste dans la chaîne de démarrage : elle doit être inerte."""
    assert _jouer(monkeypatch, None) == ""


@pytest.mark.django_db
def test_une_variable_vide_ne_declenche_rien(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Une variable créée puis laissée vide ne doit pas être lue comme un ordre."""
    assert _jouer(monkeypatch, "   ") == ""


@pytest.mark.django_db
@pytest.mark.parametrize("court", ["court", "a" * 23])
def test_un_mot_de_passe_trop_court_est_refuse(
    monkeypatch: pytest.MonkeyPatch, court: str
) -> None:
    """Refuser ici plutôt qu'accepter.

    Un mot de passe faible posé sur une base de production ne se remarque
    jamais avant l'incident — et à ce moment-là, il est trop tard pour
    regretter d'avoir été permissif.
    """
    sortie = _jouer(monkeypatch, court)

    assert "refuse" in sortie
    assert str(len(court)) in sortie


@pytest.mark.django_db
def test_la_valeur_est_echappee_par_le_pilote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un mot de passe contenant une apostrophe ne doit pas casser la requête.

    Concaténer la valeur dans le SQL en ferait une injection ouverte sur la
    commande la plus sensible du dépôt — celle qui donne les clés de la base.
    """
    from psycopg import sql

    piegeux = "il-a-dit-'bonjour'-puis-il-est-parti-tranquille"
    requete = sql.SQL("ALTER USER {} WITH PASSWORD {}").format(
        sql.Identifier("evkha"), sql.Literal(piegeux)
    )
    rendu = requete.as_string(None)  # type: ignore[arg-type]

    # Les apostrophes sont doublees, l'identifiant est entre guillemets.
    assert "''bonjour''" in rendu
    assert '"evkha"' in rendu


@pytest.mark.django_db
def test_sur_sqlite_la_commande_s_abstient(monkeypatch: pytest.MonkeyPatch) -> None:
    """La suite tourne sur SQLite : `ALTER USER` n'y existe pas.

    S'abstenir en le disant, plutôt que d'échouer : la commande est jouée au
    démarrage de tous les environnements, y compris ceux qui n'ont pas de
    PostgreSQL.
    """
    from django.db import connection

    if connection.vendor == "postgresql":
        pytest.skip("test écrit pour un environnement non PostgreSQL")

    sortie = _jouer(monkeypatch, MOT_DE_PASSE_VALABLE)

    assert "non PostgreSQL" in sortie


@pytest.mark.django_db
def test_le_seuil_de_longueur_est_de_vingt_quatre() -> None:
    """Écrit à UN seul endroit, et vérifié ici.

    Un seuil recopié dans la documentation et dans le code finit par diverger,
    et c'est la documentation qu'on lit avant de choisir un mot de passe.
    """
    from pathlib import Path

    source = Path(
        "backend/organisations/management/commands/changer_le_mot_de_passe_postgres.py"
    ).read_text(encoding="utf-8")

    assert "len(nouveau) < 24" in source
    assert "Vingt-quatre au minimum" in source

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
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from django.core.management import call_command

MOT_DE_PASSE_VALABLE = "un-mot-de-passe-de-trente-six-signes"

#: Racine du depot, deduite de l'emplacement de CE fichier et non du repertoire
#: courant : un chemin relatif au CWD ne vaut que si pytest est lance depuis la
#: racine, et un test qui ne trouve pas son fichier ne verrouille rien.
RACINE = Path(__file__).resolve().parents[2]
SOURCE_DE_LA_COMMANDE = (
    RACINE
    / "backend/organisations/management/commands/changer_le_mot_de_passe_postgres.py"
)


def _jouer(
    monkeypatch: pytest.MonkeyPatch,
    valeur: str | None,
    ancien: str | None = None,
) -> str:
    """Joue la commande avec l'environnement décrit, et rend sa sortie.

    Les DEUX variables sont posées explicitement — celle qu'on ne veut pas est
    effacée. Hériter d'une variable laissée par le shell ferait passer un test
    pour la mauvaise raison, et le jour où il tomberait, sur la mauvaise piste.
    """
    monkeypatch.delenv("EVKHA_NOUVEAU_MOT_DE_PASSE_PG", raising=False)
    monkeypatch.delenv("EVKHA_ANCIEN_MOT_DE_PASSE_PG", raising=False)
    if valeur is not None:
        monkeypatch.setenv("EVKHA_NOUVEAU_MOT_DE_PASSE_PG", valeur)
    if ancien is not None:
        monkeypatch.setenv("EVKHA_ANCIEN_MOT_DE_PASSE_PG", ancien)
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
    rendu = requete.as_string(None)

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


# ---------------------------------------------------------------------------
# Un PostgreSQL de comédie
#
# La suite tourne sur SQLite. Tout ce qui suit le test du `vendor` — c'est-à-dire
# la totalité de ce que fait la commande — n'y est donc JAMAIS atteint. Une
# première version de ces tests posait un `pytest.skip` sur ce constat : elle
# sautait à chaque exécution, en local comme en CI, et ne verrouillait rien
# (règle 1 — un contrôle qui n'a rien à comparer n'est pas un succès).
#
# Le banc ci-dessous fournit la seule chose qui manquait : un `vendor` qui dit
# `postgresql`, des réglages complets, et un `psycopg.connect` qui accepte les
# mots de passe qu'on lui désigne. Les tests deviennent alors des tests de
# COMPORTEMENT — quel mot de passe est essayé, quel SQL est exécuté — et non
# plus des lectures du texte de la source.
# ---------------------------------------------------------------------------

REGLAGES_POSTGRES = {
    "HOST": "db.interne",
    "PORT": 5432,
    "NAME": "evkha",
    "USER": "evkha",
}
ANCIEN_MOT_DE_PASSE = "l-ancien-mot-de-passe-qui-a-fuite"


class _FauxCurseur:
    def __init__(self, requetes: list[Any]) -> None:
        self._requetes = requetes

    def __enter__(self) -> _FauxCurseur:
        return self

    def __exit__(self, *_: Any) -> None:
        """Ne rend rien : une sortie vraie avalerait les exceptions du test."""

    def execute(self, requete: Any) -> None:
        self._requetes.append(requete)


class _FauxLien:
    def __init__(self, requetes: list[Any]) -> None:
        self._requetes = requetes
        self.commits = 0
        self.ferme = False

    def __enter__(self) -> _FauxLien:
        return self

    def __exit__(self, *_: Any) -> None:
        """Ne rend rien : une sortie vraie avalerait les exceptions du test."""

    def cursor(self) -> _FauxCurseur:
        return _FauxCurseur(self._requetes)

    def commit(self) -> None:
        self.commits += 1

    def close(self) -> None:
        self.ferme = True


class _BancPostgres:
    """Enregistre ce que la commande TENTE, et pas seulement ce qu'elle dit."""

    def __init__(self, *mots_de_passe_valables: str) -> None:
        self.valables = set(mots_de_passe_valables)
        self.tentatives: list[dict[str, Any]] = []
        self.requetes: list[Any] = []
        self.liens: list[_FauxLien] = []

    @property
    def mots_de_passe_essayes(self) -> list[str]:
        return [t.get("password", "") for t in self.tentatives]

    def connect(self, **parametres: Any) -> _FauxLien:
        import psycopg

        self.tentatives.append(parametres)
        if parametres.get("password") not in self.valables:
            raise psycopg.OperationalError("mot de passe refuse")
        lien = _FauxLien(self.requetes)
        self.liens.append(lien)
        return lien

    def sql_execute(self) -> list[str]:
        return [requete.as_string(None) for requete in self.requetes]


def _installer_banc(
    monkeypatch: pytest.MonkeyPatch, *mots_de_passe_valables: str
) -> _BancPostgres:
    """Fait croire à la commande qu'elle parle à PostgreSQL.

    On remplace le `connection` du module — pas celui de Django — pour que la
    vraie base de test reste hors d'atteinte : si la commande revenait un jour à
    un curseur Django, elle toucherait une base SQLite qui ne connaît pas
    `ALTER USER`, et le test tomberait au lieu de mentir.
    """
    import psycopg

    from organisations.management.commands import changer_le_mot_de_passe_postgres

    banc = _BancPostgres(*mots_de_passe_valables)
    monkeypatch.setattr(psycopg, "connect", banc.connect)

    faux_connection = SimpleNamespace(
        vendor="postgresql", settings_dict=dict(REGLAGES_POSTGRES)
    )
    monkeypatch.setattr(
        changer_le_mot_de_passe_postgres, "connection", faux_connection
    )
    return banc


def test_le_cas_nominal_execute_bien_un_alter_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le seul chemin qui change quelque chose, vérifié de bout en bout.

    Pas de `django_db` : la commande ne doit toucher AUCUNE base par le chemin
    Django. Si elle le refaisait, pytest-django refuserait l'accès et ce test
    tomberait — c'est la contre-épreuve du défaut décrit plus bas.
    """
    banc = _installer_banc(monkeypatch, ANCIEN_MOT_DE_PASSE)

    sortie = _jouer(monkeypatch, MOT_DE_PASSE_VALABLE, ancien=ANCIEN_MOT_DE_PASSE)

    # Le nouveau est essayé d'abord (idempotence), l'ancien seulement ensuite.
    assert banc.mots_de_passe_essayes == [MOT_DE_PASSE_VALABLE, ANCIEN_MOT_DE_PASSE]
    requete = banc.sql_execute()[0]
    assert requete.startswith('ALTER USER "evkha" WITH PASSWORD ')
    assert MOT_DE_PASSE_VALABLE in requete
    assert banc.liens[0].commits == 1
    assert "change" in sortie


def test_la_connexion_vise_la_base_que_django_utilise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hôte, port, base, utilisateur viennent des réglages — pas d'un doublon.

    Redemander ces quatre valeurs en variables d'environnement les ferait
    diverger un jour de la configuration réelle : on changerait alors le mot de
    passe d'une AUTRE base que celle que l'application ouvre, en annonçant un
    succès (règle 5).
    """
    banc = _installer_banc(monkeypatch, ANCIEN_MOT_DE_PASSE)

    _jouer(monkeypatch, MOT_DE_PASSE_VALABLE, ancien=ANCIEN_MOT_DE_PASSE)

    vise = banc.tentatives[0]
    assert vise["host"] == "db.interne"
    assert vise["port"] == "5432"
    assert vise["dbname"] == "evkha"
    assert vise["user"] == "evkha"


def test_sans_ancien_mot_de_passe_rien_n_est_tente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La connexion explicite a besoin de l'ancien mot de passe.

    Sans lui, la commande ne peut ni vérifier que le nouveau est déjà en place,
    ni ouvrir la connexion qui permettrait de le changer. Elle refuse en le
    disant, plutôt que de laisser croire au succès.
    """
    banc = _installer_banc(monkeypatch, ANCIEN_MOT_DE_PASSE)

    sortie = _jouer(monkeypatch, MOT_DE_PASSE_VALABLE, ancien=None)

    assert "ANCIEN" in sortie
    assert banc.requetes == []


def test_un_ancien_mot_de_passe_faux_ne_laisse_pas_croire_au_succes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le motif d'échec doit désigner la bonne variable.

    Si l'opérateur recopie un ancien mot de passe périmé, il doit lire que c'est
    LUI qui ne passe pas — sinon il ira chercher du côté du réseau ou de
    l'hôte (règle 2).
    """
    banc = _installer_banc(monkeypatch, ANCIEN_MOT_DE_PASSE)

    sortie = _jouer(monkeypatch, MOT_DE_PASSE_VALABLE, ancien="ce-n-est-pas-le-bon")

    assert "ancien mot de passe" in sortie
    assert banc.requetes == []


def test_rejouer_la_commande_ne_change_rien_une_seconde_fois(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L'idempotence, vérifiée sur le comportement et non sur un message.

    Un redéploiement, il y en a toujours un — et les variables sont souvent
    laissées en place. Si la commande rejouait `ALTER USER` avec un ancien mot
    de passe devenu invalide, elle échouerait bruyamment à chaque démarrage.
    """
    banc = _installer_banc(monkeypatch, MOT_DE_PASSE_VALABLE)

    sortie = _jouer(monkeypatch, MOT_DE_PASSE_VALABLE, ancien=ANCIEN_MOT_DE_PASSE)

    assert banc.mots_de_passe_essayes == [MOT_DE_PASSE_VALABLE]
    assert banc.requetes == []
    assert "deja en place" in sortie


def test_une_apostrophe_dans_le_mot_de_passe_ne_casse_pas_la_requete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L'échappement, vérifié sur le SQL que la commande exécute VRAIMENT.

    Le test voisin vérifie que `psycopg.sql` échappe correctement ; celui-ci
    vérifie que la commande s'en sert. Les deux sont nécessaires : le premier
    passerait encore si la commande concaténait à la main.
    """
    piegeux = "il-a-dit-'bonjour'-puis-il-est-parti-tranquille"
    banc = _installer_banc(monkeypatch, ANCIEN_MOT_DE_PASSE)

    _jouer(monkeypatch, piegeux, ancien=ANCIEN_MOT_DE_PASSE)

    assert "''bonjour''" in banc.sql_execute()[0]


def test_la_commande_se_connecte_sans_passer_par_django() -> None:
    """LE defaut evite avant de deployer.

    Une premiere version utilisait la connexion Django. Elle changeait le mot
    de passe, puis `migrate` demarrait DANS UN AUTRE PROCESSUS et se connectait
    avec l'ancien — qui ne valait plus rien. Le conteneur s'arretait, Coolify le
    relancait, il echouait encore : plateforme a terre.

    La connexion est donc montee a la main, avec un mot de passe explicite.
    `DATABASE_URL` peut ainsi porter deja le NOUVEAU, et tout ce qui suit dans
    la chaine de demarrage fonctionne du premier coup.
    """
    source = SOURCE_DE_LA_COMMANDE.read_text(encoding="utf-8")

    # Le curseur Django est ce qui rouvrirait la mauvaise connexion. Son absence
    # est une propriete de STRUCTURE : aucun test de comportement ne peut la
    # constater, puisqu'un curseur Django ferait passer les memes assertions.
    assert "connection.cursor()" not in source


@pytest.mark.django_db
def test_le_seuil_de_longueur_est_de_vingt_quatre() -> None:
    """Écrit à UN seul endroit, et vérifié ici.

    Un seuil recopié dans la documentation et dans le code finit par diverger,
    et c'est la documentation qu'on lit avant de choisir un mot de passe.
    """
    source = SOURCE_DE_LA_COMMANDE.read_text(encoding="utf-8")

    assert "len(nouveau) < 24" in source
    assert "Vingt-quatre au minimum" in source

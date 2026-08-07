"""Personne ne pouvait entrer dans `/admin/`, et rien ne permettait d'y remédier.

Constaté le 07/08/2026 : pour relier les tarifs Stripe aux formules, il faut
l'administration Django — et aucun compte n'existait. `createsuperuser` est
interactif, et l'API de Coolify n'expose aucune exécution de commande dans le
conteneur (les routes `execute`, `command` et `exec` répondent toutes 404).

D'où cette commande, jouée au démarrage. Ce que ces tests tiennent :

1. elle crée le compte quand il manque ;
2. elle ne réécrit PAS un mot de passe changé depuis l'interface — sinon il
   reviendrait à sa valeur d'origine au déploiement suivant, sans que personne
   ne comprenne pourquoi ;
3. elle rend ses droits à un compte rétrogradé par erreur, qui serait sinon
   enfermé dehors sans recours ;
4. elle ne fait rien, et le dit, quand l'environnement ne demande aucun compte.
"""
from __future__ import annotations

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

Utilisateur = get_user_model()
ADRESSE = "admin@evkha.fr"


def _jouer(monkeypatch: pytest.MonkeyPatch, **environnement: str) -> str:
    for cle in ("EVKHA_ADMIN_EMAIL", "EVKHA_ADMIN_PASSWORD",
                "EVKHA_ADMIN_REINITIALISER"):
        monkeypatch.delenv(cle, raising=False)
    for cle, valeur in environnement.items():
        monkeypatch.setenv(cle, valeur)
    sortie = StringIO()
    call_command("assurer_admin", stdout=sortie)
    return sortie.getvalue()


@pytest.mark.django_db
def test_le_compte_est_cree_quand_il_manque(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le cas qui a motivé la commande : aucune entrée possible."""
    sortie = _jouer(
        monkeypatch, EVKHA_ADMIN_EMAIL=ADRESSE, EVKHA_ADMIN_PASSWORD="secret-initial",
    )

    compte = Utilisateur.objects.get(username=ADRESSE)
    assert compte.is_superuser and compte.is_staff and compte.is_active
    assert compte.check_password("secret-initial")
    assert "cree" in sortie


@pytest.mark.django_db
def test_un_mot_de_passe_change_depuis_l_interface_survit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contre-épreuve, et la raison d'être du garde-fou.

    Réappliquer le mot de passe à chaque démarrage ferait revenir celui de la
    variable d'environnement au déploiement suivant. La personne aurait changé
    son mot de passe, l'aurait noté, et se verrait refuser l'entrée sans
    qu'aucun message n'explique quoi que ce soit.
    """
    _jouer(monkeypatch, EVKHA_ADMIN_EMAIL=ADRESSE, EVKHA_ADMIN_PASSWORD="secret-initial")
    compte = Utilisateur.objects.get(username=ADRESSE)
    compte.set_password("choisi-par-la-personne")
    compte.save()

    _jouer(monkeypatch, EVKHA_ADMIN_EMAIL=ADRESSE, EVKHA_ADMIN_PASSWORD="secret-initial")

    compte.refresh_from_db()
    assert compte.check_password("choisi-par-la-personne")
    assert not compte.check_password("secret-initial")


@pytest.mark.django_db
def test_la_reinitialisation_explicite_reecrit_le_mot_de_passe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le recours, quand le mot de passe est perdu. Explicite, jamais implicite."""
    _jouer(monkeypatch, EVKHA_ADMIN_EMAIL=ADRESSE, EVKHA_ADMIN_PASSWORD="ancien")
    compte = Utilisateur.objects.get(username=ADRESSE)
    compte.set_password("oublie")
    compte.save()

    sortie = _jouer(
        monkeypatch,
        EVKHA_ADMIN_EMAIL=ADRESSE,
        EVKHA_ADMIN_PASSWORD="nouveau",
        EVKHA_ADMIN_REINITIALISER="true",
    )

    compte.refresh_from_db()
    assert compte.check_password("nouveau")
    # Et on previent : laisser le drapeau en place effacerait tout changement
    # ulterieur a chaque demarrage.
    assert "Retirez" in sortie


@pytest.mark.django_db
def test_un_compte_retrograde_retrouve_ses_droits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sinon la personne est enfermee dehors sans aucun recours."""
    _jouer(monkeypatch, EVKHA_ADMIN_EMAIL=ADRESSE, EVKHA_ADMIN_PASSWORD="secret")
    compte = Utilisateur.objects.get(username=ADRESSE)
    compte.is_staff = False
    compte.is_superuser = False
    compte.is_active = False
    compte.save()

    _jouer(monkeypatch, EVKHA_ADMIN_EMAIL=ADRESSE, EVKHA_ADMIN_PASSWORD="secret")

    compte.refresh_from_db()
    assert compte.is_staff and compte.is_superuser and compte.is_active


@pytest.mark.django_db
def test_sans_variables_la_commande_ne_fait_rien_et_le_dit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Elle reste dans la chaine de demarrage en permanence : elle doit etre inoffensive.

    Et elle l'annonce : une absence de compte se decouvrirait sinon devant un
    formulaire de connexion qui refuse, sans raison visible.
    """
    sortie = _jouer(monkeypatch)

    assert not Utilisateur.objects.exists()
    assert "aucun compte d'administration cree" in sortie


@pytest.mark.django_db
def test_une_adresse_sans_mot_de_passe_ne_cree_rien(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un compte sans mot de passe utilisable serait une porte a moitie ouverte."""
    _jouer(monkeypatch, EVKHA_ADMIN_EMAIL=ADRESSE)

    assert not Utilisateur.objects.exists()

"""Un compte « Lecture seule » ne doit rien pouvoir modifier.

Le droit était vérifié par le décorateur `espace()`, qui **ne regardait pas la
méthode HTTP**. Quatre vues servent GET *et* POST sous un seul décorateur —
`marque`, `demandes`, `clients_finaux`, `pieces_jointes`. Elles ne pouvaient
donc déclarer qu'un seul droit, et déclaraient le plus faible : aucun.

Conséquence vérifiée : un compte en lecture seule pouvait **réécrire la charte
graphique de l'agence**, qui part sur chaque document livré chez les clients de
l'abonné. Il pouvait aussi ouvrir une demande commerciale et téléverser des
fichiers.

Le défaut n'était pas quatre oublis : c'était que le décorateur ne savait pas
distinguer une lecture d'une écriture. D'où le test structurel en fin de
fichier, qui rend le prochain oubli impossible (règle 4).
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from organisations import inscription

pytestmark = pytest.mark.django_db

PROPRIETAIRE = "claire@cabinet-duval.fr"
LECTEUR = "observateur@cabinet-duval.fr"
MOT_DE_PASSE = "un-mot-de-passe-solide-42"


@pytest.fixture
def lecteur() -> str:
    """Jeton d'un membre dont le rôle est « lecture seule »."""
    from customers.models import Customer
    from organisations import authentification, identifiants, services
    from organisations.models import RoleOrganisation

    organisation = inscription.ouvrir_compte(
        raison_sociale="Cabinet Duval",
        email=PROPRIETAIRE,
        mot_de_passe=MOT_DE_PASSE,
        activer_abonnement=False,
    ).organisation

    observateur = Customer.objects.create(email=LECTEUR)
    services.inviter_membre(
        organisation, observateur, role=RoleOrganisation.LECTURE
    )
    compte = identifiants.compte_sans_mot_de_passe(observateur)
    identifiants.definir_mot_de_passe(compte, MOT_DE_PASSE)

    jeton, _ = authentification.ouvrir_session(LECTEUR, MOT_DE_PASSE)
    return str(jeton)


def _poster(client: Any, jeton: str, chemin: str, **charge: Any) -> Any:
    return client.post(
        chemin,
        data=json.dumps(charge),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {jeton}",
    )


# ── Ce qu'un compte en lecture seule ne peut plus faire ──────────────────────


def test_il_ne_peut_pas_reecrire_la_charte(client: Any, lecteur: str) -> None:
    """Le plus grave des quatre : la charte part chez les clients de l'abonné.

    Un compte en lecture seule pouvait donc changer le nom et les couleurs
    imprimés sur chaque document remis par l'agence.
    """
    from organisations.models import Organisation

    reponse = _poster(
        client, lecteur, "/api/espace/marque/",
        raison_sociale="Cabinet Détourné", couleur_principale="#ff0000",
    )

    assert reponse.status_code == 403, "la charte a ete modifiee en lecture seule"
    assert reponse.json()["code"] == "interdit"
    assert Organisation.objects.get().raison_sociale == "Cabinet Duval"


def test_il_ne_peut_pas_ouvrir_une_demande_commerciale(
    client: Any, lecteur: str
) -> None:
    from organisations.models import DemandeCommerciale

    reponse = _poster(
        client, lecteur, "/api/espace/demandes/",
        type="credits_additionnels", quantite=50, message="…",
    )

    assert reponse.status_code == 403
    assert DemandeCommerciale.objects.count() == 0


def test_il_ne_peut_pas_creer_de_client_final(client: Any, lecteur: str) -> None:
    from organisations.models import ClientFinal

    reponse = _poster(
        client, lecteur, "/api/espace/clients-finaux/", raison_sociale="Untel"
    )

    assert reponse.status_code == 403
    assert ClientFinal.objects.count() == 0


def test_il_ne_peut_pas_televerser_de_fichier(client: Any, lecteur: str) -> None:
    from django.core.files.uploadedfile import SimpleUploadedFile

    from organisations.models import PieceJointe

    reponse = client.post(
        "/api/espace/fichiers/",
        {
            "fichier": SimpleUploadedFile("x.pdf", b"%PDF-1.4\n", content_type="application/pdf"),
            "categorie": "document",
        },
        HTTP_AUTHORIZATION=f"Bearer {lecteur}",
    )

    assert reponse.status_code == 403
    assert PieceJointe.objects.count() == 0


# ── Ce qu'il doit continuer à pouvoir faire ──────────────────────────────────


def test_il_lit_toujours_ses_livrables(client: Any, lecteur: str) -> None:
    """Contre-épreuve : le rôle s'appelle « lecture », il doit lire.

    Refuser la lecture ferait du correctif un défaut : le compte n'aurait plus
    aucune raison d'exister.
    """
    reponse = client.get(
        "/api/espace/livrables/", HTTP_AUTHORIZATION=f"Bearer {lecteur}"
    )
    assert reponse.status_code == 200


def test_il_lit_toujours_la_charte(client: Any, lecteur: str) -> None:
    reponse = client.get(
        "/api/espace/marque/", HTTP_AUTHORIZATION=f"Bearer {lecteur}"
    )
    assert reponse.status_code == 200


def test_il_change_toujours_son_propre_mot_de_passe(client: Any, lecteur: str) -> None:
    """Une écriture qui ne dépend d'AUCUN rôle : c'est son compte.

    Exiger un droit ici enfermerait dehors quelqu'un dont le mot de passe a
    fuité — la protection deviendrait le problème.
    """
    reponse = _poster(
        client, lecteur, "/api/espace/mot-de-passe/",
        mot_de_passe_actuel=MOT_DE_PASSE,
        nouveau_mot_de_passe="un-autre-mot-de-passe-98",
    )
    assert reponse.status_code == 200, reponse.content


# ── Le test structurel : le prochain oubli est impossible ────────────────────


def test_aucune_vue_de_l_espace_n_accepte_une_ecriture_sans_droit() -> None:
    """Ce test échoue sur le code d'avant, et sur le prochain oubli.

    Vérifier les quatre vues une par une aurait corrigé quatre instances. Ce
    qu'on verrouille ici, c'est la PROPRIÉTÉ : toute vue de l'espace qui
    accepte une méthode d'écriture exige un droit d'écriture (règle 4).

    Les exceptions sont nommées et justifiées, pas tolérées par omission.
    """
    from organisations import urls, vues_espace
    from organisations.models import RoleOrganisation
    from organisations.services import DROITS

    #: Vues dont l'écriture ne dépend légitimement d'aucun rôle.
    SANS_ROLE = {
        # Ouvrir et fermer sa session, changer son mot de passe : ce sont des
        # gestes sur SON compte. Les soumettre à un rôle enfermerait dehors
        # quelqu'un dont le mot de passe a fuite.
        "connexion", "deconnexion", "changer_mot_de_passe",
    }

    manquants: list[str] = []
    for regle in urls.urlpatterns:
        vue = regle.callback
        nom = getattr(vue, "__name__", "?")
        if nom in SANS_ROLE:
            continue

        methodes = getattr(vue, "_methodes_autorisees", None) or _methodes(vue)
        if not methodes - vues_espace.METHODES_SURES:
            continue

        # Le droit REELLEMENT exige pour une ecriture.
        exige = getattr(vue, "action_ecriture", "") or getattr(vue, "action_lecture", "")

        # La propriete qu'on verrouille n'est pas « un droit est declare » mais
        # « ce droit n'est PAS accorde a la lecture seule ». Une vue qui
        # exigerait `consulter_livrables` pour ecrire passerait le premier
        # critere et laisserait pourtant ecrire un compte en lecture seule —
        # le test aurait l'air de proteger sans rien proteger (regle 1).
        if not exige or exige in DROITS[RoleOrganisation.LECTURE]:
            manquants.append(f"{nom} ({sorted(methodes)}, exige {exige or 'rien'})")

    assert not manquants, (
        "un compte en lecture seule peut ecrire par ces vues : "
        + ", ".join(manquants)
    )


def _methodes(vue: Any) -> set[str]:
    """Méthodes HTTP acceptées par une vue décorée de `require_http_methods`.

    Le décorateur de Django les garde dans la fermeture ; il n'y a pas
    d'attribut public. On les lit donc là, faute de mieux — et le test échoue
    bruyamment si la structure change, plutôt que de conclure « aucune méthode
    d'écriture » et de ne rien vérifier (règle 1).
    """
    vu = vue
    for _ in range(10):
        fermeture = getattr(vu, "__closure__", None) or ()
        for cellule in fermeture:
            contenu = cellule.cell_contents
            if isinstance(contenu, (list, tuple, set, frozenset)) and contenu:
                valeurs = {str(v).upper() for v in contenu}
                if valeurs <= {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
                    return valeurs
        suivant = getattr(vu, "__wrapped__", None)
        if suivant is None:
            break
        vu = suivant
    # Aucune restriction trouvee : on considere que TOUT est accepte, ce qui
    # est le cas le plus exigeant pour le test.
    return {"GET", "POST", "PUT", "PATCH", "DELETE"}


# ── Une organisation garde toujours un propriétaire ──────────────────────────


def test_le_dernier_proprietaire_ne_peut_pas_se_retrograder(
    client: Any, lecteur: str
) -> None:
    """Le test qui échoue sur le code d'avant.

    `revoquer_membre` refusait bien de retirer le dernier propriétaire. Mais
    `inviter_membre` ÉCRASE le rôle d'un membre existant : le dernier
    propriétaire pouvait donc se « réinviter » avec le rôle « membre » et se
    démettre lui-même. La garde était contournée sans être touchée, et
    l'organisation devenait inadministrable pour toujours — plus personne pour
    gérer l'équipe, l'abonnement ni la marque.

    Le garde-fou était posé sur UN CHEMIN au lieu de la propriété (règle 4).
    """
    from organisations import authentification, services
    from organisations.models import MembreOrganisation, RoleOrganisation

    jeton, _ = authentification.ouvrir_session(PROPRIETAIRE, MOT_DE_PASSE)

    reponse = _poster(
        client, jeton, "/api/espace/equipe/inviter/",
        email=PROPRIETAIRE, role=RoleOrganisation.MEMBRE,
    )

    assert reponse.status_code in (403, 409), (
        f"le dernier proprietaire s'est retrograde (statut {reponse.status_code})"
    )
    membre = MembreOrganisation.objects.get(customer__email=PROPRIETAIRE)
    assert membre.role == RoleOrganisation.PROPRIETAIRE
    assert services.peut(membre, "gerer_membres")


def test_un_proprietaire_peut_se_retrograder_s_il_en_reste_un_autre(
    client: Any, lecteur: str
) -> None:
    """Contre-épreuve : la règle protège l'organisation, pas un privilège.

    Passer la main est légitime — c'est même le geste normal quand quelqu'un
    quitte l'agence. Ce qui est refusé, c'est de ne laisser personne.
    """
    from customers.models import Customer
    from organisations import services
    from organisations.models import MembreOrganisation, Organisation, RoleOrganisation

    organisation = Organisation.objects.get()
    second = Customer.objects.create(email="associe@cabinet-duval.fr")
    services.inviter_membre(
        organisation, second, role=RoleOrganisation.PROPRIETAIRE
    )

    ancien = Customer.objects.get(email=PROPRIETAIRE)
    services.inviter_membre(organisation, ancien, role=RoleOrganisation.MEMBRE)

    assert (
        MembreOrganisation.objects.get(customer=ancien).role
        == RoleOrganisation.MEMBRE
    )

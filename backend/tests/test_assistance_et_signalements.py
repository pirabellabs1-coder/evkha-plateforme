"""L'assistance voit tout, et ne dépense rien. Le signalement ne se perd pas.

## Ce que ces tests refusent de laisser revenir

La console d'administration peut ouvrir une VRAIE session sur l'espace d'un
client, pour aller voir de près le problème qu'il signale. C'est ce que la
cliente a demandé le 04/09/2026, et c'est utile : une vue en lecture seule
n'aurait rien permis de réparer.

Mais une vraie session, c'est aussi la carte bancaire de quelqu'un d'autre au
bout de trois routes — souscrire, acheter une étude, acheter des crédits. La
limite posée par la cliente est nette : « l'administrateur ne peut pas payer
avec de l'argent » du client. Ces tests sont ce qui la tient.

1. Une session d'assistance qui ouvre un paiement Stripe.
2. Une vue de paiement AJOUTÉE DEMAIN sans le garde-fou — c'est le test
   structurel, et c'est le seul qui protège du prochain oubli (règle 4).
3. Une session ordinaire à qui l'on refuserait ce qu'elle a le droit de faire :
   un garde-fou qui ferme tout serait vite désactivé.
4. Un signalement qui fuit d'une organisation à l'autre.
5. Un livrable d'autrui rattaché à son propre signalement.
"""
from __future__ import annotations

import inspect
from datetime import timedelta
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from catalog.models import Offer
from customers.models import Customer
from generation.models import GenerationJob
from orders.models import Order
from organisations import courriels, services, vues_espace
from organisations.authentification import (
    INACTIVITE_ASSISTANCE,
    creer_compte,
    ouvrir_session,
    ouvrir_une_assistance,
    session_du_jeton,
)
from organisations.models import (
    CompteClient,
    Formule,
    JetonAcces,
    Signalement,
    StatutSignalement,
    SujetSignalement,
)

pytestmark = pytest.mark.django_db

MOT_DE_PASSE = "mot-de-passe-de-test-2026"

#: Les vues de l'espace qui parlent d'argent au prestataire de paiement.
#:
#: Écrite ici pour être COMPARÉE au code, jamais importée de lui — même
#: raisonnement que `EXIGENT_UN_ABONNEMENT` dans `test_barriere_de_paiement`.
#:
#: La ligne de partage retenue est **tout contact avec le prestataire**, et non
#: les seules routes qui débitent : `reprendre_l_abonnement` rallume un
#: prélèvement mensuel et `changer_de_formule` en change le montant. Aucune des
#: deux n'« achète » quoi que ce soit, et les deux engagent le compte en banque
#: du client.
OUVRENT_UN_PAIEMENT = {
    "ouvrir_le_paiement",
    "acheter_une_etude",
    "acheter_des_credits",
    "acheter_un_produit",
    "reprendre_l_abonnement",
    "changer_de_formule",
}

#: Les vues qui donnent ou retirent un ACCÈS à l'organisation.
#:
#: Distinctes des précédentes, et refusées pour une autre raison : ce qu'elles
#: créent SURVIT à la fermeture de l'assistance. Une invitation acceptée reste
#: une porte ouverte quand le jeton d'assistance est révoqué, expiré, ou que le
#: jeton d'administration a tourné.
OUVRENT_UN_ACCES = {"inviter", "revoquer"}


def _vues_de_l_espace() -> dict[str, Any]:
    """Les vues décorées par `espace`, par nom.

    L'attribut `interdit_en_assistance` n'existe que sur elles : c'est ce qui
    écarte le décorateur lui-même, dont la documentation cite les fonctions de
    paiement et qui se faisait compter comme une vue de paiement.
    """
    return {
        nom: objet
        for nom, objet in vars(vues_espace).items()
        if hasattr(objet, "interdit_en_assistance")
    }


class Abonne:
    """Une organisation avec un compte de connexion, et rien d'autre."""

    def __init__(self, nom: str = "Cabinet Test", email: str = "essai@exemple.fr"):
        self.contact = Customer.objects.create(email=email, first_name=nom)
        self.organisation = services.creer_organisation(
            raison_sociale=nom, contact=self.contact
        )
        self.compte = creer_compte(self.contact, mot_de_passe=MOT_DE_PASSE)
        self.jeton, _ = ouvrir_session(email, MOT_DE_PASSE)

    @property
    def entetes(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.jeton}"}

    def entetes_assistance(self) -> dict[str, str]:
        jeton = ouvrir_une_assistance(self.compte, par="console de test")
        return {"Authorization": f"Bearer {jeton}"}


# ── Le garde-fou financier ───────────────────────────────────────────────────


def test_toute_vue_qui_ouvre_un_paiement_porte_le_garde_fou() -> None:
    """Le test structurel : c'est lui qui protège du PROCHAIN oubli.

    Il ne vérifie pas six routes, il vérifie une propriété — « aucune vue ne
    touche au paiement sans être fermée à l'assistance ».

    **Ce qu'il cherche est DÉRIVÉ du module de paiement, pas écrit ici.** La
    première version cherchait la chaîne `paiement_stripe.`, l'alias sous lequel
    `vues_espace` importe le module en tête de fichier. Elle ratait
    `acheter_un_produit`, qui fait `from paiement import stripe_api` DANS la
    fonction puis appelle `stripe_api.creer_paiement_de_produit` : la chaîne
    n'apparaît nulle part, la vue n'était pas comptée, et le test passait au
    vert en laissant une session d'assistance ouvrir un panier facturé au
    client. Un contrôle qui se donne raison tout seul (règle 1), et un
    correctif qui énumérait un cas au lieu de viser la classe (règle 4).

    On cherche donc les NOMS DES FONCTIONS du module de paiement, quels que
    soient l'alias et l'endroit de l'import. La liste vient de
    `paiement.stripe_api` lui-même : une fonction de paiement ajoutée demain y
    entre sans que personne ait à penser à ce fichier.
    """
    from paiement import stripe_api

    fonctions_de_paiement = {
        nom
        for nom, objet in vars(stripe_api).items()
        if not nom.startswith("_")
        and callable(objet)
        and getattr(objet, "__module__", "") == stripe_api.__name__
    }
    assert fonctions_de_paiement, "aucune fonction trouvée dans `paiement.stripe_api`"

    ouvrent_vraiment = set()
    for nom, objet in _vues_de_l_espace().items():
        try:
            source = inspect.getsource(objet)
        except (OSError, TypeError):  # pragma: no cover — objets sans source
            continue
        if any(fonction in source for fonction in fonctions_de_paiement):
            ouvrent_vraiment.add(nom)

    assert ouvrent_vraiment == OUVRENT_UN_PAIEMENT, (
        "La liste des vues qui touchent au paiement a changé. Ajoutez "
        "`interdit_en_assistance=True` à la nouvelle, puis mettez cette "
        f"constante à jour. Trouvées : {sorted(ouvrent_vraiment)}"
    )

    sans_garde_fou = [
        nom
        for nom in ouvrent_vraiment
        if not getattr(getattr(vues_espace, nom), "interdit_en_assistance", False)
    ]
    assert not sans_garde_fou, (
        "Ces vues touchent au paiement et restent accessibles en assistance : "
        f"{sans_garde_fou}. Un agent d'EVKHA pourrait engager l'argent du "
        "client."
    )


def test_l_assistance_ne_donne_ni_ne_retire_d_acces() -> None:
    """Une invitation SURVIT à la fermeture de l'assistance.

    C'est ce qui la distingue de tout le reste : relancer une génération ou
    corriger une charte s'arrête avec la session ; un collaborateur invité
    reste. Une session d'assistance qui pourrait inviter un propriétaire se
    fabriquerait un accès permanent à l'organisation — révoquer le jeton n'y
    changerait rien, et l'écran des sessions ouvertes ne le montrerait pas,
    puisque ce n'est plus une session.
    """
    vues = _vues_de_l_espace()
    manquantes = [
        nom
        for nom in sorted(OUVRENT_UN_ACCES)
        if not getattr(vues.get(nom), "interdit_en_assistance", False)
    ]
    assert not manquantes, (
        "Ces vues donnent ou retirent un accès sans être fermées à "
        f"l'assistance : {manquantes}"
    )


@pytest.mark.parametrize(
    ("chemin", "corps"),
    [
        ("/api/espace/paiement/", {"formule": "pro"}),
        ("/api/espace/etudes/acheter/", {"slug": "etude-marche"}),
        ("/api/espace/credits/acheter/", {"quantite": 1}),
        # Ajoutee apres l'audit du 04/09/2026 : celle-ci passait. En recette
        # elle rendait 503 « paiement_indisponible » faute de cle Stripe, ce
        # qui prouve qu'elle avait TRAVERSE le decorateur ; en production, elle
        # aurait rendu 200 avec une adresse de paiement au nom du client.
        ("/api/espace/achats/acheter/", {"produit": "marche-foodtrucks-2026"}),
        # Ni argent ni Stripe, et pourtant refusees : ce qu'elles creent survit
        # a la fermeture de l'assistance.
        ("/api/espace/equipe/inviter/", {"email": "complice@exemple.fr",
                                         "role": "proprietaire"}),
    ],
)
def test_l_assistance_ne_peut_pas_payer(chemin: str, corps: dict[str, Any]) -> None:
    """Le refus est un 403 et il porte un code lisible.

    403 et non 402 : ce n'est pas un paiement à faire, c'est un geste que cette
    session n'aura jamais le droit de faire. L'interface doit dire « quittez
    l'assistance », pas « payez ».
    """
    abonne = Abonne()
    Formule.objects.get_or_create(
        code="pro",
        defaults={
            "libelle": "Pro",
            "credits_par_echeance": 3,
            "prix_mensuel_cents": 18_900,
            "reference_paiement": "price_de_test",
            "active": True,
        },
    )
    reponse = Client().post(
        chemin,
        data=corps,
        content_type="application/json",
        headers=abonne.entetes_assistance(),
    )
    assert reponse.status_code == 403, (
        f"{chemin} a répondu {reponse.status_code} à une session d'assistance"
    )
    assert reponse.json()["code"] == "assistance_sans_depense"


def test_une_session_ordinaire_n_est_pas_genee() -> None:
    """Un garde-fou qui ferme tout finit par être désactivé.

    La même route, avec la session de la personne elle-même, ne doit PAS être
    refusée pour cause d'assistance. Elle peut échouer pour mille autres raisons
    — pas d'abonnement, Stripe absent en test — mais jamais avec ce code-là.
    """
    abonne = Abonne()
    reponse = Client().post(
        "/api/espace/credits/acheter/",
        data={"quantite": 1},
        content_type="application/json",
        headers=abonne.entetes,
    )
    corps = reponse.json() if reponse.status_code != 200 else {}
    assert corps.get("code") != "assistance_sans_depense"


def test_l_assistance_lit_l_espace_et_se_dit() -> None:
    """Elle voit ce que le client voit, et l'interface sait qu'elle assiste."""
    abonne = Abonne()
    reponse = Client().get("/api/espace/moi/", headers=abonne.entetes_assistance())
    assert reponse.status_code == 200
    assert reponse.json()["assistance"] is True

    ordinaire = Client().get("/api/espace/moi/", headers=abonne.entetes)
    assert ordinaire.json()["assistance"] is False


def test_l_assistance_se_ferme_depuis_la_console() -> None:
    """Elle n'a pas de minuterie : la révocation est donc ce qui la borne."""
    abonne = Abonne()
    jeton = ouvrir_une_assistance(abonne.compte, par="console de test")
    session = session_du_jeton(jeton)
    assert session is not None

    session.revoque_le = session.created_at
    session.save(update_fields=["revoque_le"])
    assert session_du_jeton(jeton) is None


def test_l_assistance_ne_touche_pas_la_derniere_connexion() -> None:
    """`derniere_connexion` dit si un COMPTE est vivant, pas si EVKHA est passée."""
    abonne = Abonne()
    avant = CompteClient.objects.get(pk=abonne.compte.pk).derniere_connexion
    ouvrir_une_assistance(abonne.compte, par="console de test")
    apres = CompteClient.objects.get(pk=abonne.compte.pk).derniere_connexion
    assert avant == apres


# ── Les signalements ─────────────────────────────────────────────────────────


def test_deux_signalements_de_suite_sont_acceptes() -> None:
    """La raison d'être d'un modèle distinct de `DemandeCommerciale`.

    Celle-ci n'accepte qu'une demande ouverte par type et par organisation. Un
    client dont deux études ont échoué doit pouvoir signaler les deux.
    """
    abonne = Abonne()
    for numero in (1, 2):
        reponse = Client().post(
            "/api/espace/signalements/",
            data={"sujet": "document", "message": f"Problème {numero}"},
            content_type="application/json",
            headers=abonne.entetes,
        )
        assert reponse.status_code == 201, reponse.content
    assert Signalement.objects.filter(organisation=abonne.organisation).count() == 2


def test_un_signalement_vide_est_refuse() -> None:
    abonne = Abonne()
    reponse = Client().post(
        "/api/espace/signalements/",
        data={"sujet": "autre", "message": "   "},
        content_type="application/json",
        headers=abonne.entetes,
    )
    assert reponse.status_code == 400
    assert reponse.json()["code"] == "message_vide"


def test_un_signalement_ne_franchit_pas_la_cloison() -> None:
    """Le cloisonnement par organisation, sur la route la plus récente.

    C'est la propriété la plus importante de l'espace client, et une route
    nouvelle est exactement l'endroit où elle s'oublie.
    """
    une = Abonne(nom="Agence Une", email="une@exemple.fr")
    autre = Abonne(nom="Agence Deux", email="deux@exemple.fr")
    Client().post(
        "/api/espace/signalements/",
        data={"sujet": "document", "message": "Chez moi seulement"},
        content_type="application/json",
        headers=une.entetes,
    )
    reponse = Client().get("/api/espace/signalements/", headers=autre.entetes)
    assert reponse.status_code == 200
    assert reponse.json()["signalements"] == []


def test_le_livrable_d_une_autre_agence_est_refuse() -> None:
    """Une fuite par jointure : l'identifiant voyage, la console l'affiche.

    Sans cette vérification, un identifiant recopié rattacherait le signalement
    au dossier d'une autre agence, et la console montrerait les deux côte à
    côte — sans qu'aucune vue de lecture ait été forcée.
    """
    une = Abonne(nom="Agence Une", email="une@exemple.fr")
    autre = Abonne(nom="Agence Deux", email="deux@exemple.fr")

    offre, _ = Offer.objects.get_or_create(
        slug="etude-marche",
        defaults={
            "name": "Étude de marché",
            "deliverable_type": "market_study",
            "prix_unitaire_cents": 18_900,
            "is_active": True,
        },
    )
    commande = Order.objects.create(
        organisation=autre.organisation, customer=autre.contact, offer=offre
    )
    job = GenerationJob.objects.create(order=commande, deliverable_type="market_study")

    reponse = Client().post(
        "/api/espace/signalements/",
        data={
            "sujet": "document",
            "message": "Ce document ne va pas",
            "livrable_id": str(job.id),
        },
        content_type="application/json",
        headers=une.entetes,
    )
    assert reponse.status_code == 404
    assert reponse.json()["code"] == "livrable_inconnu"
    assert not Signalement.objects.filter(organisation=une.organisation).exists()


def test_le_statut_traite_pose_et_retire_sa_date(client_admin: Any) -> None:
    """Une date qui survit à une réouverture ferait mentir les délais."""
    abonne = Abonne()
    signalement = Signalement.objects.create(
        organisation=abonne.organisation,
        auteur=abonne.contact,
        sujet=SujetSignalement.DOCUMENT,
        message="Le graphique du chapitre 4 est faux",
    )
    chemin = f"/api/dashboard/signalements/{signalement.id}/traiter/"

    client_admin.post(
        chemin,
        data={"statut": StatutSignalement.TRAITE, "reponse": "Corrigé et relivré."},
        content_type="application/json",
    )
    signalement.refresh_from_db()
    assert signalement.traite_le is not None
    assert signalement.reponse == "Corrigé et relivré."

    client_admin.post(
        chemin,
        data={"statut": StatutSignalement.EN_COURS},
        content_type="application/json",
    )
    signalement.refresh_from_db()
    assert signalement.traite_le is None
    # La réponse déjà écrite au client ne disparaît pas parce qu'on n'a envoyé
    # que le statut.
    assert signalement.reponse == "Corrigé et relivré."


def test_le_client_voit_la_reponse_d_evkha() -> None:
    """Un statut « traité » sans un mot n'apprend rien à qui attend."""
    abonne = Abonne()
    Signalement.objects.create(
        organisation=abonne.organisation,
        auteur=abonne.contact,
        sujet=SujetSignalement.DOCUMENT,
        message="Le graphique est faux",
        statut=StatutSignalement.TRAITE,
        reponse="Corrigé, le document est de nouveau dans vos livrables.",
    )
    reponse = Client().get("/api/espace/signalements/", headers=abonne.entetes)
    lot = reponse.json()["signalements"]
    assert len(lot) == 1
    assert lot[0]["reponse"].startswith("Corrigé")
    assert lot[0]["statut_libelle"] == "Traité"


# ── L'alerte par courriel ────────────────────────────────────────────────────


def test_le_depot_previent_evkha(monkeypatch: pytest.MonkeyPatch) -> None:
    """La cliente a demandé le courriel en plus du compteur, le 04/09/2026.

    On vérifie ce qui part, pas seulement qu'un envoi a lieu : une alerte qui
    dirait « un signalement est arrivé » sans dire lequel obligerait à ouvrir la
    console pour savoir s'il y a urgence.
    """
    envoyes: list[dict[str, str]] = []

    def capter(**kwargs: str) -> bool:
        envoyes.append(kwargs)
        return True

    monkeypatch.setattr(courriels, "prevenir_d_un_signalement", capter)

    abonne = Abonne(nom="Agence Alerte", email="alerte@exemple.fr")
    Client().post(
        "/api/espace/signalements/",
        data={"sujet": "generation", "message": "Bloquée depuis ce matin."},
        content_type="application/json",
        headers=abonne.entetes,
    )

    assert len(envoyes) == 1
    envoi = envoyes[0]
    assert envoi["organisation"] == "Agence Alerte"
    assert envoi["auteur"] == "alerte@exemple.fr"
    assert "Bloquée depuis ce matin." in envoi["message"]


def test_une_messagerie_en_panne_ne_perd_pas_le_signalement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L'ordre compte : on enregistre, PUIS on prévient — et l'échec est muet.

    Prévenir puis enregistrer perdrait le signalement le jour où la base
    refuse, après avoir dit au client que c'était pris.

    Et l'échec ne doit pas lui remonter : sur une erreur, il redéposerait le
    même problème, et EVKHA ouvrirait deux dossiers pour un — à cause d'une
    panne de messagerie. Le premier jet de ce test attendait l'exception ; il
    décrivait donc exactement le défaut, en le prenant pour la règle.
    """
    def tombe(**_: object) -> bool:
        raise RuntimeError("messagerie indisponible")

    monkeypatch.setattr(courriels, "prevenir_d_un_signalement", tombe)

    abonne = Abonne(nom="Agence Panne", email="panne@exemple.fr")
    reponse = Client().post(
        "/api/espace/signalements/",
        data={"sujet": "autre", "message": "Un souci."},
        content_type="application/json",
        headers=abonne.entetes,
    )
    assert reponse.status_code == 201
    assert Signalement.objects.filter(organisation=abonne.organisation).count() == 1


# ── Ce que l'audit du 04/09/2026 a trouvé ────────────────────────────────────


def test_un_identifiant_de_livrable_malforme_est_refuse_proprement() -> None:
    """404, pas 500.

    Le champ est un `UUIDField` : une valeur mal formée y lève
    `ValidationError` au lieu de rendre une file vide. La vue promet dans sa
    documentation « un identifiant inconnu est refusé, pas ignoré en silence » —
    et un identifiant MAL FORMÉ faisait tomber la requête, c'est-à-dire un
    motif que son lecteur ne peut pas trouver (règle 2).
    """
    abonne = Abonne()
    reponse = Client().post(
        "/api/espace/signalements/",
        data={"sujet": "document", "message": "Ce document.", "livrable_id": "pas-un-uuid"},
        content_type="application/json",
        headers=abonne.entetes,
    )
    assert reponse.status_code == 404
    assert reponse.json()["code"] == "livrable_inconnu"


@pytest.mark.parametrize(
    "chemin",
    [
        "/api/dashboard/signalements/pas-un-uuid/traiter/",
        "/api/dashboard/organisations/pas-un-uuid/assistance/",
        "/api/dashboard/signalements/assistances/pas-un-uuid/fermer/",
    ],
)
def test_une_adresse_malformee_de_la_console_rend_404(
    chemin: str, client_admin: Any
) -> None:
    """Le convertisseur `<uuid:…>` refuse avant d'entrer dans la vue."""
    assert client_admin.post(chemin, content_type="application/json").status_code == 404


def test_le_depot_est_plafonne(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sans plafond, une boucle noie la boîte qui sert d'alerte.

    Aucun droit n'est exigé pour signaler — c'est voulu. Mais ouvrir l'accès et
    limiter le débit sont deux questions distinctes, et la seconde restait sans
    réponse : chaque appel écrit une ligne ET envoie un courriel.
    """
    monkeypatch.setattr(courriels, "prevenir_d_un_signalement", lambda **_: True)
    abonne = Abonne(nom="Agence Bavarde", email="bavarde@exemple.fr")

    codes = []
    for numero in range(vues_espace.DEPOTS_PAR_ORGANISATION.maximum + 1):
        reponse = Client().post(
            "/api/espace/signalements/",
            data={"sujet": "autre", "message": f"Message {numero}"},
            content_type="application/json",
            headers=abonne.entetes,
        )
        codes.append(reponse.status_code)

    assert codes[:-1] == [201] * vues_espace.DEPOTS_PAR_ORGANISATION.maximum
    assert codes[-1] == 429


def test_un_depot_refuse_ne_consomme_pas_le_quota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La contre-épreuve : le plafond ne doit pas punir un clic maladroit.

    Un message vide est refusé en 400. S'il comptait dans le quota, quelqu'un
    qui envoie deux fois un formulaire incomplet perdrait des dépôts qu'il n'a
    jamais faits.
    """
    monkeypatch.setattr(courriels, "prevenir_d_un_signalement", lambda **_: True)
    abonne = Abonne(nom="Agence Maladroite", email="maladroite@exemple.fr")

    for _ in range(20):
        Client().post(
            "/api/espace/signalements/",
            data={"sujet": "autre", "message": "   "},
            content_type="application/json",
            headers=abonne.entetes,
        )

    reponse = Client().post(
        "/api/espace/signalements/",
        data={"sujet": "autre", "message": "Un vrai message."},
        content_type="application/json",
        headers=abonne.entetes,
    )
    assert reponse.status_code == 201


# ── La fermeture après inactivité, et le courriel au titulaire ───────────────


def test_une_assistance_silencieuse_se_ferme() -> None:
    """Ce n'est pas la minuterie que la cliente a écartée.

    Une minuterie compte depuis l'OUVERTURE et éjecte l'agent en pleine
    investigation. Celle-ci compte depuis le DERNIER GESTE : elle ne se
    déclenche jamais tant qu'on travaille, et ferme l'onglet qu'on a oublié —
    le seul risque que « pas de limite de temps » laissait ouvert.
    """
    abonne = Abonne()
    jeton_clair = ouvrir_une_assistance(abonne.compte, par="console de test")
    assert session_du_jeton(jeton_clair) is not None

    # On recule le dernier signe de vie au-delà du silence toléré.
    jeton = JetonAcces.objects.get(condensat__isnull=False, assistance=True)
    trop_vieux = timezone.now() - INACTIVITE_ASSISTANCE - timedelta(minutes=1)
    JetonAcces.objects.filter(pk=jeton.pk).update(derniere_utilisation=trop_vieux)

    assert session_du_jeton(jeton_clair) is None
    # Révoquée en BASE, et pas seulement déduite : sans cela, la console
    # annoncerait « ouverte » une session que le serveur refuse déjà.
    jeton.refresh_from_db()
    assert jeton.revoque_le is not None


def test_une_assistance_active_ne_se_ferme_pas() -> None:
    """La contre-épreuve, sans laquelle le test précédent ne prouve rien.

    Un correctif qui ferme aussi ce qui travaille serait pire que le défaut :
    il rendrait l'assistance inutilisable, donc contournée.
    """
    abonne = Abonne()
    jeton_clair = ouvrir_une_assistance(abonne.compte, par="console de test")
    jeton = JetonAcces.objects.get(assistance=True)
    presque = timezone.now() - INACTIVITE_ASSISTANCE + timedelta(minutes=30)
    JetonAcces.objects.filter(pk=jeton.pk).update(derniere_utilisation=presque)

    assert session_du_jeton(jeton_clair) is not None


def test_une_session_ordinaire_n_est_jamais_fermee_pour_silence() -> None:
    """Le client n'a rien demandé.

    Lui appliquer ce délai le sortirait de son espace au milieu d'un
    questionnaire. Le prédicat rend donc toujours faux hors assistance.
    """
    abonne = Abonne()
    jeton = JetonAcces.objects.filter(assistance=False).first()
    assert jeton is not None
    trop_vieux = timezone.now() - INACTIVITE_ASSISTANCE - timedelta(days=3)
    JetonAcces.objects.filter(pk=jeton.pk).update(derniere_utilisation=trop_vieux)

    assert session_du_jeton(abonne.jeton) is not None


def test_la_console_ne_liste_pas_une_assistance_endormie(client_admin: Any) -> None:
    """L'écran et le serveur doivent dire la même chose.

    Une session listée « ouverte » que le serveur refuse déjà est le genre de
    repère sur lequel on s'appuie pour conclure de travers (règle 5).
    """
    abonne = Abonne()
    ouvrir_une_assistance(abonne.compte, par="console de test")
    ouvertes = client_admin.get("/api/dashboard/signalements/assistances/")
    assert len(ouvertes.json()["assistances"]) == 1

    jeton = JetonAcces.objects.get(assistance=True)
    trop_vieux = timezone.now() - INACTIVITE_ASSISTANCE - timedelta(minutes=1)
    JetonAcces.objects.filter(pk=jeton.pk).update(derniere_utilisation=trop_vieux)

    lot = client_admin.get("/api/dashboard/signalements/assistances/").json()
    assert lot["assistances"] == []


def test_le_titulaire_est_prevenu_de_l_assistance(
    monkeypatch: pytest.MonkeyPatch, client_admin: Any
) -> None:
    """Demandé par la cliente le 04/09/2026.

    Un accès dont le titulaire n'est jamais informé est un accès qu'il ne peut
    pas contester — et c'est ce changement qui, le premier, donne à EVKHA le
    pouvoir d'entrer chez quelqu'un.
    """
    envoyes: list[dict[str, str]] = []

    def capter(**kwargs: str) -> bool:
        envoyes.append(kwargs)
        return True

    monkeypatch.setattr(courriels, "prevenir_d_une_assistance", capter)

    abonne = Abonne(nom="Agence Prevenue", email="prevenue@exemple.fr")
    reponse = client_admin.post(
        f"/api/dashboard/organisations/{abonne.organisation.id}/assistance/",
        content_type="application/json",
    )
    assert reponse.status_code == 200
    assert envoyes == [
        {"destinataire": "prevenue@exemple.fr", "organisation": "Agence Prevenue"}
    ]


def test_une_messagerie_en_panne_n_empeche_pas_l_assistance(
    monkeypatch: pytest.MonkeyPatch, client_admin: Any
) -> None:
    """L'assistance existe déjà quand le courriel part.

    Faire échouer l'ouverture sur une panne de messagerie laisserait un agent
    devant une erreur, avec une session pourtant ouverte derrière.
    """
    def tombe(**_: object) -> bool:
        raise RuntimeError("messagerie indisponible")

    monkeypatch.setattr(courriels, "prevenir_d_une_assistance", tombe)

    abonne = Abonne(nom="Agence Muette", email="muette@exemple.fr")
    reponse = client_admin.post(
        f"/api/dashboard/organisations/{abonne.organisation.id}/assistance/",
        content_type="application/json",
    )
    assert reponse.status_code == 200
    assert session_du_jeton(reponse.json()["jeton"]) is not None

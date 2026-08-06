"""Routes de l'espace client (lot 4).

Préfixe `/api/espace/`, distinct de `/api/dashboard/` : le middleware du
dashboard protège ce dernier par un jeton partagé, et laisser les deux sous le
même préfixe ferait passer l'espace client par une authentification qui ne
distingue pas les organisations.
"""
from __future__ import annotations

from django.urls import path

from . import vues_espace as vues

app_name = "espace"

urlpatterns = [
    path("connexion/", vues.connexion, name="connexion"),
    path("deconnexion/", vues.deconnexion, name="deconnexion"),
    path("moi/", vues.moi, name="moi"),
    # Changer son mot de passe ferme TOUTES les sessions : c'est le seul
    # recours de quelqu'un dont le jeton a fuite.
    path(
        "mot-de-passe/",
        vues.changer_mot_de_passe,
        name="mot-de-passe",
    ),
    path("credits/", vues.journal_credits, name="credits"),
    # Agregation mensuelle : le journal ligne a ligne ne dit pas si la formule
    # est la bonne, c'est pourtant LA question d'un abonne.
    path("consommation/", vues.consommation, name="consommation"),
    path("clients-finaux/", vues.clients_finaux, name="clients-finaux"),
    path(
        "clients-finaux/<str:client_id>/archiver/",
        vues.archiver_client_final,
        name="client-final-archiver",
    ),
    path("marque/", vues.marque, name="marque"),
    path("catalogue/", vues.catalogue, name="catalogue"),
    path("commander/", vues.commander, name="commander"),
    path(
        "formulaire/<str:type_document>/",
        vues.formulaire,
        name="formulaire",
    ),
    path("fichiers/", vues.pieces_jointes, name="fichiers"),
    path(
        "fichiers/<str:piece_id>/supprimer/",
        vues.supprimer_piece_jointe,
        name="fichier-supprimer",
    ),
    path("livrables/", vues.livrables, name="livrables"),
    path("formules/", vues.formules, name="formules"),
    # Ouvre le paiement de la formule choisie. POST : elle a un effet chez
    # Stripe, et une adresse de paiement ne doit pas se retrouver dans un
    # historique de navigation ni dans un journal d'accès.
    path("paiement/", vues.ouvrir_le_paiement, name="paiement"),
    path("demandes/", vues.demandes, name="demandes"),
    path("livrables/<str:job_id>/", vues.suivi_livrable, name="suivi"),
    # Renoncer a une etude en echec et recuperer son credit, sans passer
    # par un humain — voir `abandonner_livrable`.
    path(
        "livrables/<str:job_id>/abandonner/",
        vues.abandonner_livrable,
        name="abandonner",
    ),
    path("equipe/", vues.equipe, name="equipe"),
    path("equipe/inviter/", vues.inviter, name="equipe-inviter"),
    path(
        "equipe/<str:membre_id>/revoquer/",
        vues.revoquer,
        name="equipe-revoquer",
    ),
]

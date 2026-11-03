"""Travailler par client : une fiche, ses projets, leurs dossiers (03/11/2026).

L'abonnée B2B — une consultante, typiquement — produit des études pour
plusieurs personnes depuis un seul compte. Jusqu'ici elle remplissait un
questionnaire par dossier, et pour chaque nouvelle étude d'une même personne
elle effaçait ou retapait les champs.

Le rangement est désormais : **client** (`ClientFinal`) → **projets ou
marques** (`Projet`) → **dossiers** (`Order.projet`). Ce module tient les trois
règles qui ne se lisent pas dans les modèles.

## Le nom du projet est une identité, pas une étiquette

`generation.socle.heritage` reconnaît « le même dossier » au `PROJET` saisi,
réduit sans casse ni accents, et parmi les commandes du même demandeur. Une
commande passée depuis un projet porte son nom, imposé : c'est ce qui fait
reprendre à un business plan les chiffres de l'étude de marché qui l'a
précédé.

La conséquence se lit dans l'autre sens : deux projets de même nom, chez deux
clients d'une même abonnée, se prêteraient leurs chiffres. C'est exactement le
défaut du 01/11/2026 (« ça a mélangé les dossiers »). Un nom de projet est donc
unique dans TOUTE l'organisation, archivés compris — leurs dossiers restent
héritables.

## Les réponses connues sont lues, jamais recopiées

Le pré-remplissage vient des soumissions déjà envoyées pour ce projet, la plus
récente d'abord. Une copie sur la fiche dirait autre chose que ce que le moteur
a réellement reçu dès la première correction.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q

from intake.models import IntakeSubmission
from orders.models import Order

from . import formulaires
from .models import ClientFinal, Organisation, Projet, cle_de_projet

__all__ = ["cle_de_projet"]  # réexportée : `commandes` et les tests la lisent ici


class ProjetRefuseError(ValueError):
    """Le projet ne peut pas être créé. Le message est destiné à l'abonnée."""


def par_identifiant(modele: Any, identifiant: str, **filtres: Any) -> Any:
    """L'objet, ou `None` — y compris pour un identifiant qui n'est pas un UUID.

    Un `filter(id="abc")` sur un `UUIDField` lève `ValidationError` : l'adresse
    tapée à la main rendait une erreur 500 au lieu d'un 404.
    """
    try:
        return modele.objects.filter(id=identifiant, **filtres).first()
    except (ValidationError, ValueError):
        return None


def projet_de(organisation: Organisation, identifiant: str) -> Projet | None:
    """Un projet de CETTE organisation, ou rien. Un identifiant deviné ne donne
    accès à aucune fiche d'une autre abonnée."""
    projet: Projet | None = par_identifiant(Projet, identifiant, client__organisation=organisation)
    return projet


@transaction.atomic
def creer_projet(client: ClientFinal, nom: str) -> tuple[Projet, int]:
    """Crée le projet et lui rattache les dossiers déjà produits sous ce nom.

    Retourne (projet, nombre de dossiers rattachés). Le rattachement reprend les
    commandes de l'organisation, sans projet, dont le `PROJET` se réduit à la
    même clé : ce sont celles que l'héritage considère déjà comme « le même
    dossier ». La fiche montre ainsi l'historique réel, y compris les études
    commandées avant qu'elle n'existe.
    """
    nom = nom.strip()
    if not nom:
        raise ProjetRefuseError("Le nom de la marque ou du projet est obligatoire.")
    organisation = client.organisation
    # Verrou sur l'organisation : « vérifier l'homonyme, puis créer » laissait
    # passer deux créations simultanées du même nom chez deux clients — ceux-là
    # même qui se prêteraient ensuite leurs chiffres. SQLite l'ignore ;
    # PostgreSQL, qui sert la production, l'applique.
    Organisation.objects.select_for_update().filter(pk=organisation.pk).first()
    projet = Projet(client=client, nom=nom)
    cle = Projet.cle_pour(nom)

    homonyme = (
        Projet.objects.filter(client__organisation=organisation, cle=cle)
        .select_related("client")
        .first()
    )
    if homonyme is not None:
        chez = (
            "chez ce client"
            if homonyme.client_id == client.id
            else f"chez {homonyme.client.raison_sociale}"
        )
        msg = (
            f"Un projet « {homonyme.nom} » existe déjà {chez}. Le nom relie les "
            "études d'un même projet entre elles : précisez-le, par exemple "
            f"« {nom} — {client.raison_sociale} »."
        )
        raise ProjetRefuseError(msg)

    projet.save()

    a_rattacher = [
        soumission.order_id
        for soumission in IntakeSubmission.objects.filter(
            order__organisation=organisation, order__projet__isnull=True
        ).only("order_id", "normalized_variables")
        if Projet.cle_pour(str(soumission.normalized_variables.get("PROJET") or "")) == cle
    ]
    rattaches = Order.objects.filter(id__in=a_rattacher).update(projet=projet)
    return projet, rattaches


def reponses_connues(projet: Projet, type_document: str) -> dict[str, str]:
    """Les réponses à pré-remplir pour ce questionnaire, depuis ce projet.

    Ordre de priorité, le premier qui répond l'emporte :

    1. le nom du projet, pour `PROJET` — toujours, voir l'en-tête ;
    2. la réponse la plus récente donnée à la même question pour ce projet,
       quel que soit le livrable : les quatre questionnaires partagent leurs
       identifiants, une clientèle cible décrite pour l'étude de marché est
       celle du business plan ;
    3. la fiche du client, pour le secteur, le pays et la zone.

    Seules les questions marquées `reprise` sont reprises : ce qui ne valait que
    pour une étude n'est pas proposé à la suivante.
    """
    questionnaire = formulaires.formulaire(type_document)
    if questionnaire is None:
        return {}
    a_reprendre = [c.identifiant for c in questionnaire.champs if c.reprise]

    reponses: dict[str, str] = {"PROJET": projet.nom}
    soumissions = (
        IntakeSubmission.objects.filter(order__projet=projet)
        .order_by("-order__created_at")
        .only("normalized_variables")
    )
    for soumission in soumissions:
        variables = soumission.normalized_variables or {}
        for identifiant in a_reprendre:
            valeur = str(variables.get(identifiant) or "").strip()
            if valeur and identifiant not in reponses:
                reponses[identifiant] = valeur

    client = projet.client
    for identifiant, valeur in (
        ("SECTEUR", client.secteur),
        ("PAYS", client.pays),
        ("ZONE", client.ville or client.region),
    ):
        if identifiant in a_reprendre and valeur and identifiant not in reponses:
            reponses[identifiant] = valeur

    return {cle: valeur for cle, valeur in reponses.items() if cle in a_reprendre}


def clients_avec_comptes(organisation: Organisation, *, archives: bool) -> Any:
    """Les fiches, chacune avec son nombre de projets et de dossiers."""
    requete = organisation.clients_finaux.annotate(
        nb_projets=Count("projets", filter=Q(projets__archive_le__isnull=True), distinct=True),
        nb_dossiers=Count("projets__commandes", distinct=True),
    )
    if not archives:
        requete = requete.filter(archive_le__isnull=True)
    return requete.order_by("raison_sociale")

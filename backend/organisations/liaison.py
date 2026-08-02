"""Liaison entre une génération et le portefeuille de son organisation (lot 4).

Le cahier des charges (§11) pose deux règles :

- **débit au lancement de la génération** ;
- **remboursement automatique en cas d'échec définitif**.

Le mot « définitif » n'est pas décoratif. Dans ce dépôt, `JobStatus.FAILED` est
un état **rattrapable** : l'administrateur relance un chapitre ou l'étude
entière depuis le tableau de bord, et le §13 décrit précisément ce parcours.
Rembourser à chaque passage en `FAILED` offrirait donc l'étude à quiconque
échoue une fois puis relance. Le remboursement est ici un acte explicite —
l'abandon —, jamais un effet de bord d'un statut.

## Coexistence avec le flux en service

Le flux Systeme.io actuel ne connaît pas les organisations : un crédit y est un
`Order` pré-créé porteur d'un lien Tally, déjà payé. Une commande sans
organisation ne doit donc **rien** débiter, et surtout pas échouer : ce serait
casser la production pour un module qui n'y est pas encore branché.

Le rattachement est explicite sur la commande, avec repli sur l'organisation du
client. Aucune devinette : si le rattachement est ambigu — un client membre de
deux organisations sans commande rattachée —, on ne choisit pas, on s'abstient
et on le trace.
"""
from __future__ import annotations

import logging

from generation.models import GenerationJob

from . import credits
from .models import (
    MembreOrganisation,
    Organisation,
    StatutOrganisation,
    TypeMouvement,
)

_log = logging.getLogger(__name__)


def organisation_du_job(job: GenerationJob) -> Organisation | None:
    """Organisation à débiter, ou None si la commande n'en dépend pas.

    Trois sources, dans cet ordre :

    1. le rattachement explicite porté par la commande ;
    2. l'organisation dont le client est le contact ;
    3. l'unique organisation active dont il est membre.

    Une ambiguïté ne se résout pas au hasard : plusieurs organisations
    candidates rendent None, avec une trace. Débiter le mauvais portefeuille
    serait pire qu'un débit manquant, parce que personne ne le verrait.
    """
    rattachement = getattr(job.order, "organisation", None)
    if rattachement is not None:
        return rattachement  # type: ignore[no-any-return]

    client = job.order.customer
    par_contact = list(Organisation.objects.filter(contact=client)[:2])
    if len(par_contact) == 1:
        return par_contact[0]
    if len(par_contact) > 1:
        _log.warning(
            "Job %s : le client %s est contact de plusieurs organisations. "
            "Aucun débit : rattacher la commande explicitement.",
            job.id, client.email,
        )
        return None

    appartenances = list(
        MembreOrganisation.objects.filter(
            customer=client,
            revoque_le__isnull=True,
            organisation__statut=StatutOrganisation.ACTIVE,
        ).select_related("organisation")[:2]
    )
    if len(appartenances) == 1:
        return appartenances[0].organisation
    if len(appartenances) > 1:
        _log.warning(
            "Job %s : le client %s appartient à plusieurs organisations. "
            "Aucun débit : rattacher la commande explicitement.",
            job.id, client.email,
        )
    return None


def cout_en_credits(job: GenerationJob) -> int:
    """Coût de la génération, en crédits.

    Un livrable vaut un crédit dans l'offre actuelle : la page publique annonce
    « 2 crédits inclus » pour deux livrables. Le coût est néanmoins lu sur
    l'offre quand celle-ci le précise, parce que le cahier des charges exige
    qu'il soit « paramétrable par type de document, modifiable sans
    déploiement ».
    """
    cout = getattr(job.order.offer, "cout_en_credits", None)
    if isinstance(cout, int) and cout > 0:
        return cout
    return 1


def reference_de_debit(job: GenerationJob) -> str:
    """Clé d'idempotence d'un débit. Stable sur toute la vie du job."""
    return f"job:{job.id}"


def debiter_pour_job(job: GenerationJob) -> tuple[bool, str]:
    """Débite le portefeuille au lancement. Retourne (autorise, raison).

    Trois issues, et il faut les distinguer :

    - **pas d'organisation** → autorisé sans débit. C'est le flux Systeme.io en
      service, déjà payé autrement ;
    - **déjà débité** → autorisé. Une relance d'étude ne repaie pas. C'est le
      point le plus facile à rater : traiter le refus d'un double débit comme
      un échec bloquerait toute reprise sur incident, alors que la reprise est
      précisément ce que le §13 demande ;
    - **solde insuffisant ou organisation suspendue** → refusé. « Commande
      bloquée, aucun découvert. »
    """
    organisation = organisation_du_job(job)
    if organisation is None:
        return True, "Commande sans organisation : aucun crédit débité."

    # Le remboursement CLÔT l'étude. Sans ce garde-fou, la suite du code
    # rencontrerait la ligne de débit d'origine — toujours présente — et
    # conclurait « déjà débité, on relance sans repayer », alors que les
    # crédits sont retournés au client : l'étude serait produite gratuitement.
    #
    # Le contrôle est ici, dans la couche qui tient l'argent, et non dans la
    # vue de relance : une seconde porte d'appel apparaîtrait un jour, et elle
    # n'y penserait pas (règle 4).
    if credits_restitues(job):
        return False, (
            "Les crédits de cette étude ont été restitués : elle ne peut plus "
            "être relancée. Passez une nouvelle commande."
        )

    cout = cout_en_credits(job)
    try:
        credits.debiter(
            organisation, cout,
            reference=reference_de_debit(job),
            motif=f"Génération {job.deliverable_type} · commande {job.order.systeme_order_id}",
        )
    except credits.MouvementDejaEnregistreError:
        return True, "Débit déjà passé pour cette étude : relance sans nouveau débit."
    except credits.SoldeInsuffisantError as refus:
        return False, str(refus)
    except credits.OrganisationSuspendueError as refus:
        return False, str(refus)

    return True, f"{cout} crédit(s) débité(s), solde restant {credits.solde(organisation)}."


def credits_restitues(job: GenerationJob) -> bool:
    """Les crédits de cette étude ont-ils déjà été rendus ?

    Lu dans le journal, jamais mémorisé sur le job : un second champ pourrait
    dire l'inverse du journal, et c'est le journal qui fait foi sur le solde
    (règle 5).

    Cette question n'existait pas, et son absence ouvrait un trou de caisse.
    `debiter_pour_job` traite une référence déjà consommée comme « autorisé,
    pas de nouveau débit » — ce qui est juste pour une relance ordinaire. Mais
    après un remboursement, la ligne de débit existe toujours : la relance
    passait donc le contrôle et produisait l'étude **gratuitement**. C'est
    exactement le risque que la docstring ci-dessous nommait, sans que rien ne
    l'empêche.
    """
    organisation = organisation_du_job(job)
    if organisation is None:
        return False
    return (
        credits.portefeuille_de(organisation)
        .mouvements.filter(
            type=TypeMouvement.REMBOURSEMENT, reference=reference_de_debit(job)
        )
        .exists()
    )


def rembourser_job(job: GenerationJob, *, motif: str) -> bool:
    """Restitue les crédits d'une étude **définitivement** abandonnée.

    À n'appeler que sur un abandon explicite, jamais depuis la bascule en
    `FAILED` : un job en échec est rattrapable, et rembourser à ce moment-là
    offrirait l'étude à qui échoue puis relance.

    Cette fonction existait, était testée, et **n'était appelée par aucun
    chemin du produit** — seulement par ses propres tests. Le module `credits`
    annonce en tête « Aucun crédit perdu sur échec » : la garantie était écrite
    deux fois et tenue zéro fois (règles 1 et 8). Un abonné payait un crédit
    pour un document qu'il ne recevait pas.

    Retourne Vrai si un remboursement a été écrit.
    """
    organisation = organisation_du_job(job)
    if organisation is None:
        return False
    try:
        credits.rembourser(
            organisation, reference=reference_de_debit(job), motif=motif
        )
    except credits.MouvementDejaEnregistreError as raison:
        # Soit rien n'a été débité, soit le remboursement est déjà passé. Dans
        # les deux cas il n'y a rien à faire, et ce n'est pas une erreur.
        _log.info("Job %s : aucun remboursement à écrire — %s", job.id, raison)
        return False
    _log.info("Job %s : crédits restitués à %s.", job.id, organisation)
    return True

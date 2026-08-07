"""Supervision : ce que l'espace administrateur observe (refonte).

Changement de rôle assumé : EVKHA ne produit plus les documents à la place de
ses clients. L'espace administrateur **surveille** — les organisations, les
paiements, la consommation de crédits, les volumes produits. Les vues de ce
module sont donc toutes en **lecture seule**.

## Ce qui est mesurable, et ce qui ne l'est pas

Il faut le dire clairement, parce qu'un tableau de bord qui affiche un chiffre
faux est pire qu'un tableau de bord qui n'affiche rien (règle 2) :

- le **revenu récurrent** est calculé depuis les abonnements actifs et leurs
  formules. C'est un revenu *contractuel* : ce qui devrait rentrer si toutes
  les cartes passent ;
- le **revenu encaissé** est la somme des factures que Stripe nous a
  rapportées payées (`organisations.Encaissement`). C'est le chiffre
  d'affaires réalisé. Les deux sont donnés SÉPARÉMENT et jamais confondus :
  les additionner, ou n'en montrer qu'un, ferait passer un impayé pour une
  recette. Jusqu'au 07/08/2026 seul le premier existait, faute de prestataire
  branché — c'est désormais le cas ;
- le **coût de production** vient de `GenerationJob.total_cost_eur`, alimenté par
  le moteur de coûts à chaque appel. Celui-là est réel ;
- la **marge** n'est donnée que par document, jamais globalement : rapporter une
  marge globale à un revenu contractuel produirait un chiffre qui n'existe pas.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q, Sum
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_http_methods

from customers.models import Customer
from generation.models import GenerationJob, JobStatus
from monitoring.models import IncidentSeverity, OperationalIncident
from organisations.models import (
    Encaissement,
    MouvementCredit,
    Organisation,
    StatutAbonnement,
    StatutOrganisation,
    TypeMouvement,
)

_log = logging.getLogger(__name__)

#: Profondeur d'historique des séries mensuelles. Douze mois donnent une saison
#: complète sans rendre le graphique illisible.
MOIS_HISTORIQUE = 12


def _json(donnees: dict[str, Any], statut: int = 200) -> JsonResponse:
    return JsonResponse(donnees, status=statut)


def _cents(valeur: Decimal | int | float | None) -> int:
    """Montant en centimes. Les euros décimaux flottants n'ont rien à faire ici."""
    return int(round(float(valeur or 0) * 100))


def _mois(reference: date, decalage: int) -> str:
    """Clé `AAAA-MM` du mois situé `decalage` mois avant `reference`."""
    total = reference.year * 12 + (reference.month - 1) - decalage
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


@dataclass(frozen=True)
class Periode:
    debut: date
    fin: date

    @property
    def jours(self) -> int:
        return (self.fin - self.debut).days or 1


def _periode(request: HttpRequest) -> Periode:
    """Fenêtre d'observation, par défaut trente jours."""
    from django.utils import timezone

    jours = max(min(int(request.GET.get("jours", 30) or 30), 365), 1)
    fin = timezone.now().date()
    return Periode(debut=fin - timedelta(days=jours), fin=fin)


# ── Synthèse ─────────────────────────────────────────────────────────────────


@require_http_methods(["GET"])
def synthese(request: HttpRequest) -> JsonResponse:
    """Chiffres clés du tableau de bord d'administration (§10.1)."""
    periode = _periode(request)

    organisations = Organisation.objects.all()
    actives = organisations.filter(statut=StatutOrganisation.ACTIVE).count()
    suspendues = organisations.filter(statut=StatutOrganisation.SUSPENDUE).count()

    # Revenu récurrent contractuel : somme des formules des abonnements actifs.
    recurrent = 0
    for organisation in organisations.prefetch_related("abonnements__formule"):
        abonnement = next(
            (
                a
                for a in organisation.abonnements.all()
                if a.statut == StatutAbonnement.ACTIF
            ),
            None,
        )
        if abonnement is not None:
            recurrent += abonnement.formule.prix_mensuel_cents

    jobs = GenerationJob.objects.filter(created_at__date__gte=periode.debut)
    produits = jobs.filter(status=JobStatus.DONE).count()
    echecs = jobs.filter(status=JobStatus.FAILED).count()
    total = jobs.count()
    cout = jobs.aggregate(total=Sum("total_cost_eur"))["total"]

    mouvements = MouvementCredit.objects.filter(created_at__date__gte=periode.debut)
    consommes = -int(
        mouvements.filter(type=TypeMouvement.DEBIT).aggregate(
            total=Sum("quantite")
        )["total"]
        or 0
    )
    restitues = int(
        mouvements.filter(type=TypeMouvement.REMBOURSEMENT).aggregate(
            total=Sum("quantite")
        )["total"]
        or 0
    )
    solde_total = int(
        MouvementCredit.objects.aggregate(total=Sum("quantite"))["total"] or 0
    )

    # Encaissé : ce qui est REELLEMENT rentré, par opposition au contractuel.
    encaissements = Encaissement.objects.all()
    encaisse_total = int(
        encaissements.aggregate(total=Sum("montant_cents"))["total"] or 0
    )
    encaisse_periode = int(
        encaissements.filter(paye_le__date__gte=periode.debut)
        .aggregate(total=Sum("montant_cents"))["total"]
        or 0
    )

    incidents = OperationalIncident.objects.filter(resolved_at__isnull=True)

    return _json({
        "periode": {
            "debut": periode.debut.isoformat(),
            "fin": periode.fin.isoformat(),
            "jours": periode.jours,
        },
        "organisations": {
            "total": organisations.count(),
            "actives": actives,
            "suspendues": suspendues,
        },
        "revenu": {
            "recurrent_mensuel_cents": recurrent,
            "encaisse_periode_cents": encaisse_periode,
            "encaisse_total_cents": encaisse_total,
            "devise": "EUR",
            # Un tableau de bord qui affiche un chiffre faux est pire qu'un
            # tableau de bord vide. On dit ce que CHAQUE chiffre est.
            "nature": "contractuel",
            "avertissement": (
                "Le revenu récurrent est contractuel : la somme des abonnements "
                "actifs, c'est-à-dire ce qui devrait rentrer. L'encaissé est ce "
                "que le prestataire a rapporté payé. Un impayé creuse l'écart "
                "entre les deux."
            ),
        },
        "documents": {
            "produits": produits,
            "en_echec": echecs,
            "total": total,
            "taux_echec": round(echecs / total, 3) if total else 0.0,
        },
        "credits": {
            "consommes": consommes,
            "restitues": restitues,
            "solde_total_en_circulation": solde_total,
        },
        "cout_production": {
            "total_cents": _cents(cout),
            "moyen_par_document_cents": (
                _cents(Decimal(str(cout)) / produits) if cout and produits else 0
            ),
        },
        "incidents": {
            "ouverts": incidents.count(),
            "graves": incidents.filter(
                severity__in=[IncidentSeverity.HIGH, IncidentSeverity.CRITICAL]
            ).count(),
        },
        "clients": {"total": Customer.objects.count()},
    })


# ── Séries mensuelles ────────────────────────────────────────────────────────


@require_http_methods(["GET"])
def evolution(request: HttpRequest) -> JsonResponse:
    """Séries mensuelles : documents, crédits, revenu encaissé.

    Les mois sans activité sont présents avec des zéros. Les omettre ferait
    d'un creux d'activité une ligne qui saute d'un mois à l'autre — le
    graphique mentirait sur la forme de la courbe.

    La profondeur se règle par `?mois=N`, ce qui permet au tableau de bord de
    filtrer sur une période sans que le serveur ait à connaître les boutons de
    l'interface. Bornée entre 1 et 36 : au-delà, la courbe devient illisible, et
    en deçà elle n'a plus de forme. Une valeur illisible retombe sur le défaut
    plutôt que de faire échouer la page — un tableau de bord vide pour un
    paramètre mal tapé serait une punition disproportionnée.
    """
    from django.utils import timezone

    try:
        profondeur = int(request.GET.get("mois", MOIS_HISTORIQUE))
    except (TypeError, ValueError):
        profondeur = MOIS_HISTORIQUE
    profondeur = max(1, min(profondeur, 36))

    aujourdhui = timezone.now().date()
    cles = [_mois(aujourdhui, decalage) for decalage in range(profondeur - 1, -1, -1)]
    index = {cle: position for position, cle in enumerate(cles)}
    zeros = [0] * len(cles)

    produits, echecs = list(zeros), list(zeros)
    for job in GenerationJob.objects.values("created_at", "status"):
        cle = f"{job['created_at'].year:04d}-{job['created_at'].month:02d}"
        position = index.get(cle)
        if position is None:
            continue
        if job["status"] == JobStatus.DONE:
            produits[position] += 1
        elif job["status"] == JobStatus.FAILED:
            echecs[position] += 1

    debits, dotations = list(zeros), list(zeros)
    for mouvement in MouvementCredit.objects.values("created_at", "type", "quantite"):
        cle = (
            f"{mouvement['created_at'].year:04d}-"
            f"{mouvement['created_at'].month:02d}"
        )
        position = index.get(cle)
        if position is None:
            continue
        if mouvement["type"] == TypeMouvement.DEBIT:
            debits[position] += -mouvement["quantite"]
        elif mouvement["type"] in (TypeMouvement.DOTATION, TypeMouvement.ACHAT):
            dotations[position] += mouvement["quantite"]

    # Revenu REELLEMENT encaisse, mois par mois. En centimes comme partout
    # ailleurs : convertir ici ferait deux unites dans la meme reponse.
    encaisse = list(zeros)
    for ligne in Encaissement.objects.values("paye_le", "montant_cents"):
        cle = f"{ligne['paye_le'].year:04d}-{ligne['paye_le'].month:02d}"
        position = index.get(cle)
        if position is not None:
            encaisse[position] += int(ligne["montant_cents"])

    cout_mensuel = [0] * len(cles)
    for depense in GenerationJob.objects.values("created_at", "total_cost_eur"):
        cle = f"{depense['created_at'].year:04d}-{depense['created_at'].month:02d}"
        position = index.get(cle)
        if position is not None:
            cout_mensuel[position] += _cents(depense["total_cost_eur"] or 0)

    return _json({
        "mois": cles,
        "series": [
            {"cle": "produits", "libelle": "Documents produits", "valeurs": produits},
            {"cle": "echecs", "libelle": "Échecs", "valeurs": echecs},
            {"cle": "debits", "libelle": "Crédits consommés", "valeurs": debits},
            {"cle": "dotations", "libelle": "Crédits attribués", "valeurs": dotations},
            {
                "cle": "encaisse",
                "libelle": "Revenu encaissé",
                "valeurs": encaisse,
                "unite": "cents",
            },
            {
                "cle": "cout",
                "libelle": "Coût de production",
                "valeurs": cout_mensuel,
                "unite": "cents",
            },
        ],
    })


# ── Organisations ────────────────────────────────────────────────────────────


@require_http_methods(["GET"])
def organisations(request: HttpRequest) -> JsonResponse:
    """Une ligne par organisation : formule, solde, consommation, volumes (§10.2).

    Le solde est agrégé en base et non calculé organisation par organisation :
    trente organisations feraient trente requêtes, et la page s'écroulerait dès
    que le portefeuille se remplit.
    """
    soldes = {
        ligne["portefeuille__organisation"]: int(ligne["total"] or 0)
        for ligne in MouvementCredit.objects.values(
            "portefeuille__organisation"
        ).annotate(total=Sum("quantite"))
    }
    debits = {
        ligne["portefeuille__organisation"]: -int(ligne["total"] or 0)
        for ligne in MouvementCredit.objects.filter(type=TypeMouvement.DEBIT)
        .values("portefeuille__organisation")
        .annotate(total=Sum("quantite"))
    }

    lignes = []
    requete = (
        Organisation.objects.select_related("contact")
        .prefetch_related("abonnements__formule")
        .annotate(
            nombre_clients_finaux=Count(
                "clients_finaux", filter=Q(clients_finaux__archive_le__isnull=True),
                distinct=True,
            ),
            nombre_membres=Count(
                "membres", filter=Q(membres__revoque_le__isnull=True), distinct=True
            ),
            nombre_documents=Count(
                "commandes__generation_job",
                filter=Q(commandes__generation_job__status=JobStatus.DONE),
                distinct=True,
            ),
        )
        .order_by("raison_sociale")
    )

    for organisation in requete:
        abonnement = next(
            (
                a
                for a in organisation.abonnements.all()
                if a.statut == StatutAbonnement.ACTIF
            ),
            None,
        )
        lignes.append({
            "id": str(organisation.id),
            "raison_sociale": organisation.raison_sociale,
            "contact": organisation.contact.email,
            "statut": organisation.statut,
            "marque_blanche": organisation.marque_blanche,
            "formule": abonnement.formule.libelle if abonnement else "",
            "prix_mensuel_cents": (
                abonnement.formule.prix_mensuel_cents if abonnement else 0
            ),
            "credits_par_echeance": (
                abonnement.formule.credits_par_echeance if abonnement else 0
            ),
            "solde": soldes.get(organisation.id, 0),
            "credits_consommes": debits.get(organisation.id, 0),
            "documents_produits": organisation.nombre_documents,
            "clients_finaux": organisation.nombre_clients_finaux,
            "membres": organisation.nombre_membres,
        })

    return _json({"organisations": lignes})


# ── Demandes commerciales à traiter ──────────────────────────────────────────


@require_http_methods(["GET"])
def demandes(request: HttpRequest) -> JsonResponse:
    """Demandes de changement de formule et d'achat de crédits (§10.2).

    Elles arrivent de l'espace client. Sans cet écran, une demande resterait
    enregistrée sans que personne ne la voie — c'est-à-dire ne servirait à rien.
    """
    from organisations.models import DemandeCommerciale, StatutDemande

    requete = (
        DemandeCommerciale.objects.select_related(
            "organisation", "formule_visee", "demandeur"
        )
        .order_by("statut", "-created_at")[:200]
    )
    return _json({
        "demandes": [
            {
                "id": str(demande.id),
                "organisation": demande.organisation.raison_sociale,
                "organisation_id": str(demande.organisation_id),
                "demandeur": demande.demandeur.email if demande.demandeur else "",
                "type": demande.type,
                "statut": demande.statut,
                "formule_visee": (
                    demande.formule_visee.libelle if demande.formule_visee else ""
                ),
                "quantite": demande.quantite,
                "message": demande.message,
                "date": demande.created_at.isoformat(),
            }
            for demande in requete
        ],
        "ouvertes": DemandeCommerciale.objects.filter(
            statut=StatutDemande.OUVERTE
        ).count(),
    })

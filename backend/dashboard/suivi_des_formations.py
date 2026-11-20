"""Le suivi des élèves depuis l'administration : ce que la gérante PROUVE.

Elle est certifiée Qualiopi. Un auditeur lui demande, pour une formation :
qui l'a suivie, jusqu'où, et qui était présent à quelle séance. Ces vues
rendent les trois réponses — le tableau des élèves (à l'écran et en CSV), les
séances en présentiel, et la feuille d'émargement de chacune.

Les mêmes partis pris que `dashboard/formations.py`, dont ce module reprend
les outils au lieu de les recopier :

- **les règles ne sont pas ici.** Elles vivent dans `catalog/suivi.py` ;
- **rien ne se supprime.** Une séance s'annule, avec sa date ; une signature
  ne se modifie ni ne s'efface, et une séance signée ne change plus d'heure ;
- **un champ illisible ne remet rien à zéro** : il est nommé dans `refuses`.

L'authentification n'est pas ici : tout ce qui est sous `/api/dashboard/`
passe par `dashboard.middleware.DashboardAuthMiddleware`.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from catalog import formations as regles
from catalog import suivi
from catalog.models import (
    AchatFormation,
    Emargement,
    ModeDEmargement,
    SeanceEnPresentiel,
)

from .formations import (
    Ecarte,
    _booleen,
    _Champs,
    _donnees,
    _formation,
    _refus_lisibles,
    _reporter,
    _trouver,
)

_log = logging.getLogger(__name__)

_SEANCE = _Champs(
    textes=("intitule", "lieu", "nom_de_la_formatrice"),
    entiers=("duree_minutes",),
    a_part=("debut", "annulee", "signer", "emargement_papier"),
)

#: Ce qu'une séance DÉCRIT, et qui se fige à la première signature.
_DECRIT = ("intitule", "debut", "duree_minutes", "lieu", "nom_de_la_formatrice")


def _sans_cache(reponse: HttpResponse) -> HttpResponse:
    """Ces réponses portent des noms, des adresses et des signatures : ni le
    navigateur ni un relais ne doivent en garder copie."""
    reponse["Cache-Control"] = "no-store"
    return reponse


# ── Le tableau des élèves ────────────────────────────────────────────────────


@require_http_methods(["GET"])
@_refus_lisibles
def eleves(request: HttpRequest, formation_id: str) -> HttpResponse:
    """Une ligne par élève et par achat : accès, progression, présence.

    Un achat dont l'organisation compte plusieurs membres donne une ligne par
    membre ; un achat sans aucun élève connu donne quand même la sienne, avec
    l'adresse collectée au paiement.
    """
    parente = _formation(formation_id)
    lignes, lecons_total = suivi.tableau_des_eleves(parente)
    return _sans_cache(JsonResponse({"eleves": lignes, "lecons_total": lecons_total}))


@require_http_methods(["GET"])
@_refus_lisibles
def eleves_csv(request: HttpRequest, formation_id: str) -> HttpResponse:
    """Le MÊME tableau, pour l'auditeur : un fichier qu'un tableur ouvre.

    Il porte des noms et des adresses : il ne se met pas en cache, et il se
    télécharge au lieu de s'afficher.
    """
    parente = _formation(formation_id)
    lignes, _ = suivi.tableau_des_eleves(parente)
    reponse = HttpResponse(
        suivi.en_csv(lignes), content_type="text/csv; charset=utf-8"
    )
    # Le slug ne porte que des lettres sans accent, des chiffres et des
    # tirets (`regles.verifier_formation`) : il s'écrit tel quel.
    reponse["Content-Disposition"] = f'attachment; filename="eleves-{parente.slug}.csv"'
    _log.info("Tableau des élèves de %s exporté (%d lignes).", parente.slug, len(lignes))
    return _sans_cache(reponse)


# ── Les séances en présentiel ────────────────────────────────────────────────


def _iso(instant: Any) -> str | None:
    return instant.isoformat() if instant else None


def _vue_emargement(emargement: Emargement) -> dict[str, Any]:
    return {
        "id": str(emargement.id),
        "achat_id": str(emargement.achat_id),
        "eleve_id": str(emargement.eleve_id),
        # Le nom de la fiche de l'élève, et à côté celui qui a été SIGNÉ : la
        # gérante voit si quelqu'un a tapé un autre nom que le sien.
        "nom": suivi.nom_de_l_eleve(emargement.eleve),
        **suivi.vue_emargement(emargement),
        "adresse_ip": emargement.adresse_ip,
    }


def _vue_seance(seance: SeanceEnPresentiel) -> dict[str, Any]:
    return {
        "id": str(seance.id),
        "formation_id": str(seance.formation_id),
        "intitule": seance.intitule,
        "debut": seance.debut.isoformat(),
        "duree_minutes": seance.duree_minutes,
        "lieu": seance.lieu,
        "nom_de_la_formatrice": seance.nom_de_la_formatrice,
        # `null` tant que la séance tient / n'est pas signée.
        "annulee_le": _iso(seance.annulee_le),
        "signee_par_la_formatrice_le": _iso(seance.signee_par_la_formatrice_le),
        "emargements": [_vue_emargement(e) for e in seance.emargements.all()],
    }


def _seances() -> Any:
    return SeanceEnPresentiel.objects.prefetch_related(
        Prefetch(
            "emargements",
            queryset=Emargement.objects.select_related("eleve").order_by("signe_le"),
        )
    )


def _reponse(seance_id: Any, ecartes: list[Ecarte], statut: int = 200) -> HttpResponse:
    """La séance RELUE en base, émargements compris."""
    return _sans_cache(JsonResponse(
        {"seance": _vue_seance(_seances().get(pk=seance_id)), "refuses": ecartes},
        status=statut,
    ))


@csrf_exempt
@require_http_methods(["GET", "POST"])
@_refus_lisibles
def seances(request: HttpRequest, formation_id: str) -> HttpResponse:
    """Liste les séances d'une formation avec leurs émargements, ou en crée une.

    Annulées comprises, dans l'ordre de leur début : c'est ici que la gérante
    retrouve une séance annulée pour la rétablir.
    """
    parente = _formation(formation_id)
    if request.method == "GET":
        return _sans_cache(JsonResponse({
            "seances": [
                _vue_seance(seance)
                for seance in _seances().filter(formation=parente)
            ]
        }))

    donnees = _donnees(request)
    nouvelle = SeanceEnPresentiel(formation=parente)
    # Annuler, signer, émarger : rien de cela n'a de sens à la création. Ces
    # clés sont rangées avec les champs inconnus plutôt qu'appliquées.
    ecartes = _reporter(nouvelle, donnees, None, replace(_SEANCE, a_part=("debut",)))
    nouvelle.debut = suivi.instant_saisi(donnees.get("debut"), champ="debut")
    suivi.verifier_seance(nouvelle)
    nouvelle.save()

    _log.info("Séance créée pour %s : %s", parente.slug, nouvelle.id)
    return _reponse(nouvelle.pk, ecartes, 201)


def _reporter_le_debut(cible: SeanceEnPresentiel, donnees: Any) -> list[Ecarte]:
    """À la MODIFICATION, un début illisible laisse le précédent, et le dit."""
    if "debut" not in donnees:
        return []
    try:
        cible.debut = suivi.instant_saisi(donnees["debut"], champ="debut")
    except regles.Refus as refus:
        return [{"champ": "debut", "raison": refus.message}]
    return []


def _reporter_l_annulation(cible: SeanceEnPresentiel, donnees: Any) -> list[Ecarte]:
    """`{"annulee": true}` annule, `{"annulee": false}` rétablit.

    Annuler deux fois garde la première date. Les signatures déjà posées
    restent : la ligne dit ce qui s'est passé, dans l'ordre.
    """
    if "annulee" not in donnees:
        return []
    annulee = _booleen(donnees["annulee"])
    if annulee is None:
        return [{"champ": "annulee", "raison": "Oui ou non est attendu (true ou false)."}]
    if annulee and cible.annulee_le is None:
        cible.annulee_le = timezone.now()
    elif not annulee:
        cible.annulee_le = None
    return []


def _signer_pour_la_formatrice(cible: SeanceEnPresentiel, donnees: Any) -> list[Ecarte]:
    """`{"signer": true}` : la gérante signe la séance au nom de la formatrice.

    Signer deux fois garde la première date. Retirer une signature est
    refusé, comme partout : elle ne se défait pas.
    """
    if "signer" not in donnees:
        return []
    signer = _booleen(donnees["signer"])
    if signer is None:
        return [{"champ": "signer", "raison": "Oui ou non est attendu (true ou false)."}]
    if not signer:
        if cible.signee_par_la_formatrice_le is None:
            return []
        raise regles.Refus(
            "Une signature ne se retire pas.", "signature_definitive", 409,
            champ="signer",
        )
    suivi.exiger_signable(cible)
    if not cible.nom_de_la_formatrice.strip():
        raise regles.Refus(
            "Indiquez le nom de la formatrice avant de signer la séance : une "
            "signature sans nom ne prouve rien.",
            "formatrice_inconnue",
            409,
            champ="nom_de_la_formatrice",
        )
    if cible.signee_par_la_formatrice_le is None:
        cible.signee_par_la_formatrice_le = timezone.now()
    return []


def _emarger_sur_papier(cible: SeanceEnPresentiel, donnees: Any) -> None:
    """Reporte une signature recueillie sur la feuille imprimée.

    L'achat doit porter sur la formation de la séance, et la personne être un
    élève de cet achat — sinon 404, sans dire lequel des deux manque.
    L'accès de l'achat n'est PAS regardé : la séance a eu lieu, et un
    remboursement survenu depuis n'efface pas une présence.
    """
    if "emargement_papier" not in donnees:
        return
    brut = donnees["emargement_papier"]
    if not isinstance(brut, dict):
        raise regles.Refus(
            "Désignez l'élève qui a signé : « achat_id », « eleve_id » et « nom ».",
            "emargement_illisible",
            champ="emargement_papier",
        )
    inconnu = regles.Refus(
        "Cet élève n'est pas inscrit à cette formation.", "eleve_inconnu", 404
    )
    try:
        achat = _trouver(AchatFormation, str(brut.get("achat_id")), "", "")
    except regles.Refus:
        raise inconnu from None
    if achat.formation_id != cible.formation_id:
        raise inconnu
    eleve = suivi.eleve_de_l_achat(achat, brut.get("eleve_id"))
    if eleve is None:
        raise inconnu
    suivi.signer(
        cible.pk,
        achat=achat,
        eleve=eleve,
        nom=suivi.nom_signe(brut.get("nom")),
        mode=ModeDEmargement.PAPIER,
    )


@csrf_exempt
@require_http_methods(["POST"])
@_refus_lisibles
def seance(request: HttpRequest, seance_id: str) -> HttpResponse:
    """Modifie une séance, l'annule, la signe, ou y reporte une signature papier.

    Plusieurs gestes peuvent voyager dans le même envoi ; ils s'appliquent
    TOUS ou aucun. Dans l'ordre : la description, l'annulation, la signature
    de la formatrice, l'émargement papier — annuler et signer ensemble est
    donc refusé.

    **Une séance signée ne se décrit plus autrement.** Dès qu'un élève ou la
    formatrice a signé, l'intitulé, le début, la durée, le lieu et le nom de
    la formatrice sont figés : changer l'heure d'une séance sous la signature
    de quelqu'un fabriquerait une preuve. Elle peut encore être annulée.
    """
    cible = _trouver(
        SeanceEnPresentiel, seance_id, "Cette séance n'existe pas.", "seance_inconnue"
    )
    donnees = _donnees(request)

    with transaction.atomic():
        # Sous verrou : une signature d'élève et une modification simultanées
        # se suivent (`suivi.signer` prend le même verrou).
        cible = SeanceEnPresentiel.objects.select_for_update().get(pk=cible.pk)
        avant = [getattr(cible, champ) for champ in _DECRIT]

        ecartes = _reporter(cible, donnees, None, _SEANCE)
        ecartes += _reporter_le_debut(cible, donnees)
        if [getattr(cible, champ) for champ in _DECRIT] != avant and suivi.est_signee(
            cible
        ):
            raise regles.Refus(
                "Cette séance porte déjà une signature : son intitulé, sa "
                "date, sa durée, son lieu et le nom de la formatrice ne se "
                "modifient plus. Vous pouvez l'annuler et en créer une autre.",
                "seance_signee",
                409,
            )
        suivi.verifier_seance(cible)
        ecartes += _reporter_l_annulation(cible, donnees)
        ecartes += _signer_pour_la_formatrice(cible, donnees)
        cible.save()
        _emarger_sur_papier(cible, donnees)

    return _reponse(cible.pk, ecartes)


@require_http_methods(["GET"])
@_refus_lisibles
def feuille(request: HttpRequest, seance_id: str) -> HttpResponse:
    """Toutes les données d'une feuille d'émargement imprimable."""
    cible = _trouver(
        SeanceEnPresentiel, seance_id, "Cette séance n'existe pas.", "seance_inconnue"
    )
    relue = _seances().select_related("formation").get(pk=cible.pk)
    return _sans_cache(JsonResponse({"feuille": suivi.feuille(relue)}))

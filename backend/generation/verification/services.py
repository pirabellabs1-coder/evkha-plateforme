"""Orchestration de la passe de vérification (lot 4).

Enchaîne les contrôles, agrège le rapport, et ouvre un incident quand le
livrable ne doit pas partir.

La passe ne répare rien. C'est délibéré : une réparation qui juge sur la même
évidence que le contrôle se donne raison toute seule (règle 9). Ce qu'elle
produit est un constat, destiné à un humain et au blocage de l'envoi.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from core.numbers import amounts_in

from ..models import GenerationJob
from ..rendu_word.assemblage import RapportAssemblage
from ..socle.schema import Socle
from ..socle.services import socle_verrouille
from . import controles
from .lecture import DocumentLu, lire_livrable
from .rapport import Anomalie, Gravite, RapportControle

_log = logging.getLogger(__name__)


def chiffres_du_brief(job: GenerationJob) -> list[float]:
    """Montants écrits par le client dans son brief.

    Ils sont légitimes dans le livrable sans figurer au socle : le client a le
    droit de citer son propre chiffre d'affaires. On réutilise l'extraction du
    dépôt plutôt que d'en écrire une seconde (règle 5).
    """
    from ..gate import _brief_free_text  # noqa: PLC0415

    return amounts_in(_brief_free_text(job))


def verifier_document(
    document: DocumentLu,
    socle: Socle,
    *,
    deliverable_type: str,
    chapitres_attendus: Sequence[int] = (),
    chiffres_client: Sequence[float] = (),
    assemblage: RapportAssemblage | None = None,
) -> RapportControle:
    """Passe complète sur un document déjà lu. Ne touche à rien en base."""
    rapport = RapportControle()

    rapport.mesures = {
        "mots": document.mots,
        "part_en_tableaux": round(document.part_en_tableaux, 3),
        "mediane_paragraphe": document.mediane_paragraphe,
        "part_paragraphes_longs": round(document.part_paragraphes_longs, 3),
        "tableaux": document.tableaux,
        "images": document.images,
        "grandeurs_relevees": len(document.mesures),
    }

    rapport.controles_executes.append("integrite")
    rapport.ajouter(*controles.controler_integrite_du_document(
        document, chapitres_attendus
    ))

    rapport.controles_executes.append("chiffres_hors_socle")
    rapport.ajouter(*controles.controler_chiffres_hors_socle(
        document, socle, chiffres_client
    ))

    rapport.controles_executes.append("couverture_socle")
    rapport.ajouter(*controles.controler_couverture_du_socle(
        document, socle, deliverable_type,
        identifiants_en_figure=assemblage.identifiants_rendus if assemblage else (),
    ))

    rapport.controles_executes.append("hierarchie_marches")
    rapport.ajouter(*controles.controler_hierarchie_des_marches(
        document, socle,
        identifiants_en_figure=assemblage.identifiants_rendus if assemblage else (),
    ))

    # « Bien vérifier la cohérence des chiffres… il y a des erreurs dans les
    # calculs et pourcentages » (cliente, 11/08/2026). Une extrapolation est
    # légitime — le manuel l'autorise — mais une extrapolation FAUSSE ruine la
    # crédibilité de tout le document.
    rapport.controles_executes.append("calculs_annonces")
    rapport.ajouter(*controles.controler_les_calculs_annonces(document))

    rapport.controles_executes.append("densite")
    rapport.ajouter(*controles.controler_densite(document))

    if assemblage is not None:
        rapport.controles_executes.append("visuels")
        rapport.ajouter(*controles.controler_visuels(
            assemblage.graphiques_demandes,
            assemblage.graphiques_rendus,
            assemblage.graphiques_abandonnes,
            assemblage.graphiques_convertis,
        ))

    return rapport


def verifier_document_sans_socle(document: DocumentLu) -> RapportControle:
    """Les contrôles du lot 4 qui ne demandent PAS de socle.

    Quatre des six en demandent un — chiffres hors socle, couverture, hiérarchie
    des marchés, visuels — et ne peuvent donc rien dire du business plan ni de
    la stratégie, qui tournent sur le moteur hérité. Les deux autres, si :
    l'intégrité du fichier et sa densité. Ce sont précisément ceux qui ont
    attrapé les désastres de ce projet — un compte de résultat vidé de ses
    lignes, un document sans prose.

    Ne pas les exécuter faute de socle revenait à livrer sans aucun contrôle de
    contenu deux produits sur quatre.

    **Le contrôle de présence des chapitres est délibérément écarté ici.** Il
    cherche le marqueur écrit par le rendu Word (« CHAPITRE 07 ») ; la chaîne
    HTML titre autrement, et mesuré sur un vrai rendu il déclarait absents deux
    chapitres présents — un motif introuvable par le lecteur, ce qui est pire
    qu'absent (règle 2). Cette vérité a déjà sa source dans cette chaîne :
    `documents.services._verifier_completude_chapitres`, qui compare le
    chapitrage aux sections rendues et refuse le PDF s'il en manque une. En
    poser une seconde, avec une autre convention, c'est la règle 5.

    Le rapport ne nomme donc que ce qu'il a réellement exécuté : `resume()` dira
    « intégrité, densité » et pas davantage.
    """
    rapport = RapportControle()
    rapport.mesures = {
        "mots": document.mots,
        "part_en_tableaux": round(document.part_en_tableaux, 3),
        "mediane_paragraphe": document.mediane_paragraphe,
        "part_paragraphes_longs": round(document.part_paragraphes_longs, 3),
        "tableaux": document.tableaux,
        "images": document.images,
    }

    rapport.controles_executes.append("integrite")
    rapport.ajouter(*controles.controler_integrite_du_document(document))

    rapport.controles_executes.append("densite")
    rapport.ajouter(*controles.controler_densite(document))
    return rapport


def verifier_livrable(
    job: GenerationJob,
    chemin: Path,
    *,
    assemblage: RapportAssemblage | None = None,
    ouvrir_incident: bool = True,
) -> RapportControle:
    """Vérifie le `.docx` livré d'un job et trace le résultat.

    Le socle absent n'est pas une raison de passer : c'est une anomalie
    bloquante. Un contrôle qui n'a rien à comparer est un échec (règle 1).
    """
    socle = socle_verrouille(job)
    if socle is None:
        rapport = RapportControle()
        rapport.controles_executes.append("socle")
        rapport.ajouter(Anomalie(
            "socle", Gravite.BLOQUANTE,
            f"Job {job.id} : aucun socle verrouillé. Aucun chiffre du livrable "
            "ne peut être justifié.",
        ))
        if ouvrir_incident:
            _incident(job, rapport)
        return rapport

    document = lire_livrable(Path(chemin))
    rapport = verifier_document(
        document, socle,
        deliverable_type=str(job.deliverable_type),
        chapitres_attendus=_chapitres_attendus(job),
        chiffres_client=chiffres_du_brief(job),
        assemblage=assemblage,
    )

    _log.info("Vérification du job %s : %s", job.id, rapport.resume())
    if ouvrir_incident:
        if not rapport.livrable:
            _incident(job, rapport)
        else:
            _consigner_les_avertissements(job, rapport)
    return rapport


#: Marqueur lu par le tableau de bord : ce dossier est parti avec des réserves.
INCIDENT_TYPE_RESERVES_VERIFICATION = "reserves_verification"

#: Au-delà, l'entrée devient illisible. Un livrable réel porte 447 grandeurs
#: chiffrées ; en lister mille ne dit rien de plus que d'en lister quarante.
_RESERVES_MAX = 40


def _consigner_les_avertissements(
    job: GenerationJob, rapport: RapportControle
) -> None:
    """Conserve les RÉSERVES d'un livrable pourtant jugé livrable.

    Le contrôle central du lot 4 vérifie **chaque grandeur chiffrée** du
    document contre le socle et le brief client, et nomme celles qui n'y
    trouvent pas d'équivalent — avec l'extrait où le lecteur peut les retrouver.
    Sa gravité est délibérément un avertissement : une somme légitime de deux
    valeurs du socle y apparaît, et bloquer là-dessus arrêterait des livrables
    corrects.

    Mais un avertissement qui ne va nulle part n'existe pas. `_incident` ne
    s'ouvrait que sur un blocage : sur un document accepté, la liste des
    chiffres sans source était calculée puis jetée. Constaté le 05/08/2026, en
    cherchant à répondre à une question simple — « combien des 447 chiffres de
    cette étude sont sourcés ? » — à laquelle le système savait répondre et ne
    répondait à personne.

    C'est la même classe que les figures abandonnées, corrigée le même jour :
    la mesure est prise, puis perdue (règle 1). On la conserve, sans bloquer.
    """
    reserves = [a for a in rapport.anomalies if a.gravite is not Gravite.BLOQUANTE]
    if not reserves:
        return

    from monitoring.models import IncidentSeverity, OperationalIncident  # noqa: PLC0415

    par_controle: dict[str, int] = {}
    for anomalie in reserves:
        par_controle[anomalie.controle] = par_controle.get(anomalie.controle, 0) + 1

    OperationalIncident.objects.update_or_create(
        job=job,
        title=f"Réserves à la vérification ({len(reserves)}) — job {job.id}"[:200],
        defaults={
            "severity": IncidentSeverity.MEDIUM,
            "order": job.order,
            "details": {
                "type": INCIDENT_TYPE_RESERVES_VERIFICATION,
                "total": len(reserves),
                "par_controle": par_controle,
                "mesures": rapport.mesures,
                # L'extrait accompagne le motif : sans lui, « 420 » est
                # introuvable dans le document par le lecteur (règle 2).
                "reserves": [
                    {"controle": a.controle, "detail": a.detail, "extrait": a.extrait}
                    for a in reserves[:_RESERVES_MAX]
                ],
            },
        },
    )


def _chapitres_attendus(job: GenerationJob) -> list[int]:
    """Chapitres qu'on doit RETROUVER dans le fichier livré.

    La fiche projet (`SectionKind.OPENING`) en est exclue : elle ne part pas
    chez le client — voir `rendu_word.depuis_json.pour_le_client`. La réclamer
    ici ferait échouer le contrôle d'intégrité sur un chapitre que le rendu a
    délibérément omis, c'est-à-dire remplacer un défaut par un blocage
    (règle 3 : ce qui refait le document doit être contrôlé à son tour, et
    inversement).
    """
    from ..blueprints import SectionKind, chapters_for_deliverable  # noqa: PLC0415

    return [
        bp.number
        for bp in chapters_for_deliverable(job.deliverable_type)
        if bp.section_kind != SectionKind.OPENING
    ]


def _incident(job: GenerationJob, rapport: RapportControle) -> None:
    from monitoring.models import (  # noqa: PLC0415
        IncidentSeverity,
        OperationalIncident,
    )

    OperationalIncident.objects.create(
        title=f"Livrable bloque a la verification (job {job.id})",
        severity=IncidentSeverity.HIGH,
        job=job,
        order=job.order,
        details=rapport.en_dict(),
    )

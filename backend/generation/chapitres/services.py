"""Cycle de vie d'un chapitre : production, persistance, reprise, blocage."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from django.db import transaction

from intake.models import IntakeSubmission
from monitoring.models import IncidentSeverity, OperationalIncident

from ..modele.conformite import Arbitrage
from ..models import (
    ChapterGeneration,
    ChapterStatus,
    GenerationJob,
    JobStatus,
)
from ..socle.schema import Socle
from ..socle.services import socle_verrouille
from .configuration import type_document
from .runner import (
    ChapitreInvalideError,
    formater_motifs,
    generer_chapitre,
    payload_vers_markdown,
)
from .schema import ChapitrePayload

_log = logging.getLogger(__name__)

#: Temporisation exponentielle entre deux tentatives, en secondes.
#: 1re reprise à 30 s, 2e à 120 s. Assez long pour absorber une surcharge de
#: l'API, assez court pour qu'une étude ne traîne pas une heure sur un incident.
BASE_TEMPORISATION_S = 30
FACTEUR_TEMPORISATION = 4


def temporisation(tentative: int) -> int:
    """Délai avant la tentative `tentative` (1 = première reprise)."""
    return int(BASE_TEMPORISATION_S * FACTEUR_TEMPORISATION ** max(tentative - 1, 0))


class SocleManquantError(RuntimeError):
    """Aucun socle verrouillé : impossible de rédiger quoi que ce soit."""


def variables_du_job(job: GenerationJob) -> dict[str, object]:
    soumission = IntakeSubmission.objects.filter(order=job.order).first()
    return dict(soumission.normalized_variables) if soumission else {}


#: Préfixe conservé pour les écarts RÉELLEMENT constatés sur un chapitre.
#: Il dit quelque chose de ce chapitre-là — un dosage qui s'écarte du modèle —
#: et il n'apparaît que lorsqu'il y a matière.
PREFIXE_ECARTS = "[écarts acceptés] "

#: RETIRÉ le 09/08/2026. Conservé pour les imports existants ; plus jamais écrit.
#:
#: `[non contrôlé] type de livrable non décrit par le modèle` s'inscrivait sur
#: CHAQUE chapitre d'un business plan, d'une stratégie ou d'une étude
#: concurrentielle — vingt-deux fois la même phrase, en rouge sous chaque titre
#: de l'écran d'administration, puisque `error_message` est le champ des
#: erreurs.
#:
#: Trois défauts en un :
#:
#: - **Ce n'est pas une erreur.** Le chapitre est bon ; c'est le référentiel de
#:   forme qui n'existe pas pour ce livrable. Le ranger dans `error_message` le
#:   fait afficher comme une panne (règle 2 : un motif faux est pire qu'absent).
#: - **Ce n'est pas propre au chapitre.** L'information est vraie du LIVRABLE
#:   entier, et la répéter par chapitre la transforme en bruit — celui qu'on
#:   finit par ne plus lire, y compris le jour où il dit quelque chose.
#: - **Elle est déjà connue ailleurs.** `MODELES_PAR_LIVRABLE` dit quels
#:   livrables ont un modèle ; l'écrire vingt-deux fois n'ajoute rien.
PREFIXE_NON_CONTROLE = "[non contrôlé] "


def _mention_arbitrage(arbitrage: Arbitrage | None) -> str:
    """Trace lisible de la passe de conformité sur un chapitre accepté.

    Vide quand tout est conforme, et vide aussi quand rien n'a pu être
    contrôlé : une mention systématique se lit comme du bruit et finit ignorée,
    y compris le jour où elle dit quelque chose.

    Ne subsiste ici que ce qui parle de CE chapitre : un écart de forme
    réellement mesuré. L'absence de modèle pour un type de livrable n'est pas un
    fait du chapitre — voir `PREFIXE_NON_CONTROLE`.
    """
    if arbitrage is None:
        return ""
    if arbitrage.acceptes:
        return (PREFIXE_ECARTS + " ; ".join(arbitrage.acceptes))[:2000]
    return ""


@transaction.atomic
def enregistrer_chapitre(
    chapter: ChapterGeneration,
    payload: ChapitrePayload,
    consommation: Mapping[str, int],
    model: str | None = None,
    arbitrage: Arbitrage | None = None,
) -> ChapterGeneration:
    """Persiste la sortie structurée ET son rendu markdown.

    Les deux : la structure est la nouvelle source de vérité, le markdown
    permet à la chaîne de rendu actuelle de continuer à produire un document
    tant que le lot 3 n'est pas livré.
    """
    from ..cost import record_chapter_cost  # noqa: PLC0415 — évite un cycle

    chapter.payload = payload.model_dump(mode="json")
    chapter.content = payload_vers_markdown(payload)
    chapter.operational_summary = payload.resume
    chapter.status = ChapterStatus.DONE
    # Un chapitre accepté malgré des écarts de forme reste DONE — mais ne passe
    # pas pour parfait. Le préfixe le distingue de `[contrat] `, que la
    # tentative suivante relit pour se corriger : celui-ci ne doit surtout pas
    # être réinjecté dans un prompt, la décision est prise.
    chapter.error_message = _mention_arbitrage(arbitrage)
    chapter.save(
        update_fields=[
            "payload", "content", "operational_summary",
            "status", "error_message", "updated_at",
        ]
    )
    record_chapter_cost(
        chapter=chapter,
        input_tokens=consommation.get("input_tokens", 0),
        output_tokens=consommation.get("output_tokens", 0),
        model=model,
        cache_write_tokens=consommation.get("cache_write_tokens", 0),
        cache_read_tokens=consommation.get("cache_read_tokens", 0),
    )
    return chapter


def produire_chapitre(
    job: GenerationJob,
    numero: int,
    *,
    client: Any,
    socle: Socle | None = None,
    derniere_tentative: bool | None = None,
) -> ChapterGeneration:
    """Produit et enregistre un chapitre. Idempotent : un chapitre DONE est rendu tel quel.

    C'est l'unité de travail de la tâche Celery. L'idempotence est exigée par
    le §6.2 : une tâche rejouée après un crash de worker ne doit pas repayer
    un chapitre déjà écrit.
    """
    chapter = job.chapters.get(chapter_number=numero)
    if chapter.status == ChapterStatus.DONE and chapter.payload:
        return chapter

    socle = socle or socle_verrouille(job)
    if socle is None:
        msg = (
            f"Job {job.id} : aucun socle verrouillé. Un chapitre ne peut pas "
            "être rédigé avant que ses chiffres de référence soient établis."
        )
        raise SocleManquantError(msg)

    chapter.status = ChapterStatus.RUNNING
    chapter.save(update_fields=["status", "updated_at"])

    try:
        payload, consommation, arbitrage = generer_chapitre(
            client=client,
            chapter=chapter,
            socle=socle,
            variables=variables_du_job(job),
            derniere_tentative=derniere_tentative,
        )
    except ChapitreInvalideError as erreur:
        # Les motifs sont conservés : la tentative suivante les recevra.
        ChapterGeneration.objects.filter(pk=chapter.pk).update(
            status=ChapterStatus.FAILED,
            error_message=formater_motifs(erreur.motifs),
            retry_count=chapter.retry_count + 1,
        )
        raise

    return enregistrer_chapitre(chapter, payload, consommation, arbitrage=arbitrage)


def regenerer_chapitre(
    job: GenerationJob,
    numero: int,
    *,
    client: Any,
    note_corrective: str = "",
) -> ChapterGeneration:
    """Régénère UN chapitre sans toucher aux autres.

    Critère de recette du cahier des charges. La remise à zéro du STATUT est
    explicite : sans elle, `produire_chapitre` rendrait le chapitre déjà DONE
    tel quel, puisqu'il est idempotent.

    `note_corrective` : ce que le gate de livraison ou un CHECK inter-bloc
    reproche au chapitre. Elle est déposée sous le préfixe `[contrat] `, que
    `construire_prompt_chapitre` relit et rend au modèle sous « TENTATIVE
    PRÉCÉDENTE REFUSÉE ». On ne redemande pas « fais mieux » : on redonne la
    liste exacte de ce qui a été refusé — le canal existait déjà pour les
    refus de contrat, on ne lui en ajoute pas un second (règle 5).

    `payload`, `content` et le résumé ne sont PAS effacés avant l'appel. Les
    effacer rendait la régénération destructive : une tentative qui échoue
    laissait un chapitre vide, et `payloads_du_job` écarte un chapitre vide —
    le document livré y aurait perdu un chapitre entier, là où garder
    l'ancienne version le laisse simplement non corrigé. Le statut suffit à
    lever l'idempotence, et `enregistrer_chapitre` écrase ces champs quand, et
    seulement quand, une nouvelle version existe.
    """
    chapter = job.chapters.get(chapter_number=numero)
    statut_avant = chapter.status
    ChapterGeneration.objects.filter(pk=chapter.pk).update(
        status=ChapterStatus.PENDING,
        error_message=formater_motifs([note_corrective]) if note_corrective else "",
    )
    chapter.refresh_from_db()
    try:
        return produire_avec_reprises(job, numero, client=client)
    except Exception:
        # La réparation a échoué. Le chapitre garde sa version précédente —
        # `payload` et `content` n'ont pas été effacés — mais son STATUT, lui,
        # est resté sur l'échec, et `payloads_du_job` n'assemble que les
        # chapitres TERMINÉS : le document perdait le chapitre entier alors
        # qu'une version acceptable existait toujours en base.
        #
        # On restaure donc le statut d'avant quand une version subsiste. Une
        # réparation qui échoue laisse le chapitre NON CORRIGÉ ; elle ne doit
        # pas le faire disparaître. C'est le prolongement, au statut, de ce que
        # la docstring dit déjà du contenu.
        chapter.refresh_from_db()
        if chapter.payload and statut_avant == ChapterStatus.DONE:
            ChapterGeneration.objects.filter(pk=chapter.pk).update(status=statut_avant)
            _log.warning(
                "Job %s chapitre %s : réparation échouée, version précédente "
                "conservée.", job.id, numero,
            )
        raise


def _compter_la_tentative_perdue(
    job: GenerationJob, numero: int, erreur: BaseException
) -> None:
    """Porte au grand livre le coût d'une tentative refusée, quand il est connu.

    ## Ce que cette fonction ne fait PAS, et pourquoi

    Elle n'invente pas de coût. Seule `ChapitreInvalideError` transporte une
    consommation, parce que seule elle survient APRÈS que le modèle a répondu.
    Une panne réseau, une clé refusée, un dépassement de budget n'ont rien
    coûté : leur prêter un montant serait un chiffre faux, et un chiffre faux
    est pire qu'un chiffre absent (règle 2).

    ## Pourquoi elle ne laisse pas remonter ses propres erreurs

    Sauf une : `CostBudgetExceededError`. Comptabiliser la tentative peut faire
    franchir le plafond, et cet arrêt-là doit se propager — c'est précisément le
    cas qu'on veut voir. Tout autre incident d'écriture est journalisé sans
    masquer l'erreur d'origine : le motif du chapitre vaut mieux qu'un défaut
    survenu en le consignant.
    """
    from ..cost import CostBudgetExceededError, record_tentative_perdue  # noqa: PLC0415
    from .runner import ChapitreInvalideError  # noqa: PLC0415

    if not isinstance(erreur, ChapitreInvalideError):
        return
    consommation = erreur.consommation
    if not consommation:
        return

    chapitre = job.chapters.filter(chapter_number=numero).first()
    if chapitre is None:
        return

    try:
        record_tentative_perdue(
            chapter=chapitre,
            input_tokens=int(consommation.get("input_tokens", 0)),
            output_tokens=int(consommation.get("output_tokens", 0)),
        )
    except CostBudgetExceededError:
        raise
    except Exception:
        _log.exception(
            "Job %s chapitre %s : le coût de la tentative perdue n'a pas pu "
            "être enregistré.", job.id, numero,
        )


def produire_avec_reprises(
    job: GenerationJob,
    numero: int,
    *,
    client: Any,
    socle: Socle | None = None,
    sans_reprise: tuple[type[BaseException], ...] = (),
) -> ChapterGeneration:
    """Produit un chapitre en RÉESSAYANT. Une seule boucle pour tout le monde.

    ## Pourquoi elle vit ici, et plus dans le runner

    Elle était écrite dans `generation.runner`, et ne servait donc qu'à la
    PREMIÈRE écriture d'un chapitre. La RÉPARATION — celle qu'un CHECK
    inter-bloc ou le gate déclenche — appelait `produire_chapitre` une seule
    fois, sans jamais déclarer de dernière tentative.

    Mesuré le 05/08/2026, génération réelle `4c8cfa53` : trois chapitres écrits,
    puis le CHECK du bloc B demande une correction du chapitre 3, la correction
    dépasse le volume du modèle de 22 % pour une tolérance de 15 %, et l'étude
    entière meurt — 0,43 EUR, aucun document. Une seule tentative, `essais=1`.

    C'est exactement le défaut corrigé le 02/08 pour la première écriture,
    laissé en place sur le chemin de la réparation. J'avais traité l'instance et
    pas la classe (règle 4) : ce qui écrit un chapitre et ce qui le RÉÉCRIT
    doivent avoir les mêmes droits à l'erreur.

    ## La dernière tentative se déclare, elle ne se devine pas

    L'arbitrage de conformité n'accepte un écart de forme que sur la dernière
    tentative. Il ne peut pas la déduire de `retry_count`, que seul le chemin
    d'échec incrémente. On le lui dit.

    ## Ce qu'on ne rejoue pas

    L'appelant le déclare (`sans_reprise`) : rejouer un budget dépassé ne fait
    que dépenser davantage pour le même refus. La liste est fermée du côté du
    runner ; tout le reste est rejoué, y compris l'imprévu — c'est lui qui coûte
    le plus cher.
    """
    document = type_document(str(job.deliverable_type))
    derniere_erreur: Exception | None = None

    for tentative in range(1, document.tentatives_max + 1):
        try:
            chapitre = produire_chapitre(
                job, numero, client=client, socle=socle,
                derniere_tentative=(tentative == document.tentatives_max),
            )
        except sans_reprise:
            raise
        except Exception as erreur:  # noqa: BLE001 — on rejoue tout le reste
            derniere_erreur = erreur
            # La tentative a ete FACTUREE. Elle l'etait deja avant, mais elle
            # disparaissait ici : le `raise` emportait la consommation avec lui.
            # Six appels perdus sur le seul chapitre 19 de `b561c2d6`, jamais
            # comptes — donc un plafond qui portait sur moins que la facture.
            _compter_la_tentative_perdue(job, numero, erreur)
            if tentative < document.tentatives_max:
                _log.warning(
                    "Job %s chapitre %s : tentative %s/%s échouée (%s). On rejoue.",
                    job.id, numero, tentative, document.tentatives_max, erreur,
                )
        else:
            if tentative > 1:
                _log.warning(
                    "Job %s chapitre %s : réussi à la tentative %s.",
                    job.id, numero, tentative,
                )
            return chapitre

    assert derniere_erreur is not None
    raise derniere_erreur


def marquer_intervention_requise(
    job: GenerationJob, numero: int, motifs: list[str], tentatives: int
) -> None:
    """Le chapitre a épuisé ses tentatives : l'étude s'arrête, un humain reprend.

    Aucun e-mail client n'est déclenché — l'étude est incomplète. C'est le
    cinquième critère de recette.
    """
    GenerationJob.objects.filter(pk=job.pk).update(
        status=JobStatus.INTERVENTION_REQUISE,
        error_message=(
            f"Chapitre {numero} : {tentatives} tentative(s) échouée(s). "
            + " ; ".join(motifs)
        )[:2000],
    )
    OperationalIncident.objects.create(
        title=f"Chapitre {numero} bloqué après {tentatives} tentatives (job {job.id})",
        severity=IncidentSeverity.HIGH,
        job=job,
        order=job.order,
        details={
            "chapitre": numero,
            "tentatives": tentatives,
            "motifs": motifs[:20],
            "consigne": (
                "Étude incomplète : aucun e-mail client. Corriger le socle ou "
                "le prompt du chapitre, puis relancer depuis le tableau de bord."
            ),
        },
    )
    _log.error("Job %s : chapitre %s bloqué après %s tentatives.", job.id, numero, tentatives)


def chapitres_a_produire(job: GenerationJob) -> list[int]:
    """Numéros restant à produire, dans l'ordre. Piloté par la configuration."""
    document = type_document(str(job.deliverable_type))
    prevus = [bp.number for bp in document.chapitres()]
    faits = set(
        job.chapters.filter(status=ChapterStatus.DONE)
        .exclude(payload={})
        .values_list("chapter_number", flat=True)
    )
    return [numero for numero in prevus if numero not in faits]


def etude_complete(job: GenerationJob) -> bool:
    return not chapitres_a_produire(job)

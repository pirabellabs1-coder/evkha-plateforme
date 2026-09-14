"""La relecture FINALE : le document assemblé est relu, corrigé, puis refait.

## Ce qui manquait

Tout ce que ce dépôt contrôlait avant l'envoi jugeait la MATIÈRE du document —
les chapitres validés, le markdown rendu — jamais le fichier que le client
ouvre. La seule passe qui lisait le `.docx` (`generation/verification`) tournait
à l'intérieur de l'assemblage, ne servait qu'à retenir l'envoi, et ne
déclenchait aucune correction : ses réserves partaient telles quelles chez le
client, à charge pour lui de les voir.

Demande du 12/09/2026 : « une fois que le document est terminé, l'agent prend
le document, il valide, et s'il y a des zéros ou des incohérences dedans, il
corrige ; le document ressort ensuite en PDF, vraiment propre ».

## Comment cette boucle s'y prend

    assembler → LIRE LE FICHIER → corriger les chapitres fautifs → réassembler
                                                                 → relire

Elle s'arrête quand la lecture ne trouve plus rien à réparer, quand le budget
du dossier ne permet plus une réécriture, ou au plafond de passes. **Le fichier
livré est toujours celui de la DERNIÈRE lecture** : la boucle relit avant de
décider, jamais après avoir corrigé — sinon elle livrerait un document que rien
n'a vu (règle 3, et c'est le défaut qu'elle répare).

## Ce qu'elle ne prétend pas faire

Elle ne réécrit pas le document : elle fait réécrire les CHAPITRES dont une
anomalie porte le numéro, et laisse l'assemblage refaire le reste. Une anomalie
sans chapitre — un défaut de rendu, un manque de figures — n'est pas de son
ressort : elle la nomme dans son rapport et ne fait semblant de rien.

Elle ne juge pas non plus sur ce qu'elle a produit : la correction est demandée
au modèle, la vérification suivante relit le FICHIER (règle 9 — un contrôle et
sa réparation ne jugent pas sur la même évidence).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import GenerationJob
    from .verification.rapport import Anomalie

_log = logging.getLogger(__name__)

#: Les contrôles qu'une RÉÉCRITURE DE CHAPITRE peut fermer. Les autres —
#: intégrité du fichier, figures manquantes — viennent de l'assemblage ou du
#: socle : les envoyer à la correction ferait repayer un chapitre sans rien
#: changer, et ferait croire que le défaut est traité.
REPARABLES_PAR_CHAPITRE = frozenset({
    # `chiffres_hors_socle` n'y est PLUS (14/09/2026). Mesuré sur le corpus de
    # production : 883 signalements sur 37 dossiers, dont l'écrasante majorité
    # des calculs posés, des chiffres sourcés, des estimations déclarées ou des
    # valeurs de tableau que le socle n'a pas à porter. Même corrigé, le
    # contrôle reste trop peu précis en BP et en EC pour que son seul avis
    # fasse réécrire — et payer — un chapitre. Il continue de SIGNALER ; la
    # réécriture est réservée aux défauts qu'on sait juger.
    "calcul_faux",
    "meta_discours",
    "valeur_nulle",
    "couverture_socle",
    "hierarchie_marches",
    # La densité en fait partie depuis que le constat nomme SES chapitres : la
    # cliente a refusé une livraison entière pour cette raison seule, un mur de
    # texte là où elle attendait des tableaux reliés par de la prose courte.
    "densite",
})

#: Deux passes. La première corrige, la seconde VÉRIFIE la correction sur le
#: fichier — et corrige ce qu'elle trouve encore. Au-delà, l'expérience de la
#: boucle de correction est nette : ce qui revient deux fois à l'identique ne
#: part pas au troisième essai, il coûte seulement une génération de plus.
MAX_PASSES = 2

#: Chapitres réécrits par passe. Le même plafond que la boucle de correction :
#: au-delà, ce n'est plus une correction, c'est une régénération déguisée.
MAX_CHAPITRES_PAR_PASSE = 8

#: En dessous, on ne lance plus une réécriture : elle serait interrompue en
#: cours par le plafond, et le chapitre resterait à moitié refait.
MARGE_DE_BUDGET = Decimal("0.30")


@dataclass
class RapportRelecture:
    """Ce que la relecture a lu, fait réécrire, et ce qu'elle laisse."""

    passes: int = 0
    anomalies_au_depart: int = 0
    anomalies_restantes: int = 0
    chapitres_reecrits: list[int] = field(default_factory=list)
    #: Chapitres ABSENTS du livrable qu'on a refaits avant de relire. Comptés à
    #: part des réécritures : un chapitre rattrapé et un chapitre corrigé ne
    #: disent pas la même chose de la génération qui précède.
    chapitres_rattrapes: list[int] = field(default_factory=list)
    #: Ceux qui ont résisté. Le document partira amputé, et le dire est le
    #: minimum (règle 1) : un rattrapage silencieusement raté ressemblerait à
    #: un dossier qui n'en a jamais eu besoin.
    chapitres_perdus: list[int] = field(default_factory=list)
    #: Ce qui reste, dit en clair : un humain doit pouvoir le retrouver dans le
    #: document (règle 2).
    restantes: list[str] = field(default_factory=list)
    motif_d_arret: str = ""

    @property
    def a_corrige(self) -> bool:
        return bool(self.chapitres_reecrits or self.chapitres_rattrapes)

    def as_details(self) -> dict[str, Any]:
        return {
            "type": "relecture_finale",
            "passes": self.passes,
            "anomalies_au_depart": self.anomalies_au_depart,
            "anomalies_restantes": self.anomalies_restantes,
            "chapitres_reecrits": self.chapitres_reecrits,
            "chapitres_rattrapes": self.chapitres_rattrapes,
            "chapitres_perdus": self.chapitres_perdus,
            "restantes": self.restantes[:40],
            "motif_d_arret": self.motif_d_arret,
        }

    def resume(self) -> str:
        if not self.passes:
            return f"Relecture finale non exécutée : {self.motif_d_arret}."
        return (
            f"Relecture finale : {self.anomalies_au_depart} anomalie(s) au départ, "
            f"{len(self.chapitres_reecrits)} chapitre(s) réécrit(s), "
            f"{self.anomalies_restantes} restante(s) — {self.motif_d_arret}."
        )


def _reparables(anomalies: list[Anomalie]) -> list[Anomalie]:
    return [
        anomalie
        for anomalie in anomalies
        if anomalie.controle in REPARABLES_PAR_CHAPITRE and anomalie.chapitre
    ]


def _motifs_par_chapitre(anomalies: list[Anomalie]) -> dict[int, list[str]]:
    """Ce qu'on reproche à chaque chapitre, dans SON texte, avec l'extrait.

    L'extrait est ce qui rend le motif trouvable par celui qui doit corriger —
    le modèle comme l'humain (règle 2).
    """
    par_chapitre: dict[int, list[str]] = {}
    for anomalie in anomalies:
        numero = int(anomalie.chapitre or 0)
        if not numero:
            continue
        motif = anomalie.detail
        if anomalie.extrait:
            motif += f" Passage concerné : « {anomalie.extrait.strip()} »."
        par_chapitre.setdefault(numero, []).append(motif)
    return par_chapitre


def _echecs_du_gate(job: GenerationJob) -> tuple[Any, ...] | None:
    """Les échecs du gate de livraison — lecture seule, aucun appel d'IA.

    `None` quand le gate n'a PAS PU juger, et non une liste vide : « rien à
    réparer » et « impossible de savoir » ne sont pas le même constat, et les
    confondre ferait conclure le contrôleur sans juge (règle 1).
    """
    from .gate import run_delivery_gate  # noqa: PLC0415

    try:
        return tuple(run_delivery_gate(job).failures)
    except Exception:  # noqa: BLE001 — le gate n'est pas la relecture
        _log.exception("Relecture finale : gate illisible (job %s)", job.id)
        return None


def _priorites_du_gate(echecs: tuple[Any, ...]) -> dict[int, int]:
    """La gravité du motif le plus urgent de chaque chapitre, selon le gate.

    Le plafond de chapitres par passe doit couper par GRAVITÉ, jamais par
    numéro : trié par numéro, une densité au chapitre 3 passait devant une
    incohérence chiffrée au chapitre 18, et les derniers chapitres — la
    feuille de route, les sources — n'étaient jamais réécrits. Relecture du
    13/09/2026 ; l'ordre est celui de `correction._CHECK_PRIORITY`, importé.
    """
    from .correction import _motifs_par_chapitre as repartir  # noqa: PLC0415
    from .correction import _priorite_check  # noqa: PLC0415

    return {
        numero: min(_priorite_check(e.check) for e in liste)
        for numero, liste in repartir(echecs, inclure_les_checks=True).items()
    }


def _motifs_du_gate(echecs: tuple[Any, ...]) -> dict[int, list[str]]:
    """Ce que le gate reproche à chaque chapitre, rédigé comme une exigence.

    ## Pourquoi le contrôleur les prend

    Jusqu'au 13/09/2026, DEUX correcteurs se suivaient. La boucle de
    correction du gate réécrivait d'abord les chapitres fautifs à ses yeux ;
    la relecture finale réécrivait ensuite les chapitres fautifs aux siens.

    Mesuré sur la stratégie Zenitek `a678b10a` : la boucle du gate a réécrit
    les chapitres 8, 10, 13, 19 et 20 pendant dix-huit minutes, pour près de
    deux euros — sans fermer ses trois motifs (la fourchette « 60-75 € » était
    toujours là). La relecture finale a trouvé ensuite le budget vide et s'est
    arrêtée sans rien corriger : trente anomalies laissées.

    Deux agents pour une même tâche, et le premier affamait le second — la
    règle 5 du dépôt. Il n'y a désormais qu'un correcteur : il lit les deux
    listes, et réécrit chaque chapitre UNE fois avec tous ses motifs.

    La répartition par chapitre est celle de la boucle du gate, importée et
    non recopiée : ce qu'elle jugeait réparable reste réparable, et ce
    qu'elle écartait (échecs sans chapitre) reste écarté.
    """
    from .correction import _CHECK_LABELS  # noqa: PLC0415
    from .correction import _motifs_par_chapitre as repartir  # noqa: PLC0415

    return {
        numero: [f"{_CHECK_LABELS.get(e.check, e.check)} : {e.detail}" for e in liste]
        for numero, liste in repartir(echecs, inclure_les_checks=True).items()
    }


def _refaire_les_chapitres_manquants(
    job: GenerationJob, rapport: RapportRelecture, *, client: Any = None,
) -> None:
    """Produit les chapitres qui ne sont pas terminés. Ne lève jamais.

    ## Le défaut mesuré

    12/09/2026, reprise Zenitek `db0d9508` : deux chapitres meurent en cours de
    génération, le livrable part donc sans eux, le contrôle d'intégrité le
    retient, et le dossier s'arrête en « intervention requise ». La cliente :
    « je ne sais pas pourquoi ça, alors qu'on ne peut rien faire sur le
    document, nous ». Elle a raison — personne ne réécrit un chapitre à la
    main, et le dossier attendait donc indéfiniment.

    ## Pourquoi ici, et pas à la génération

    La génération a déjà retenté ce chapitre autant de fois qu'elle le devait,
    et a renoncé. Ce qui change ICI, c'est le temps : une cause transitoire —
    une réponse tronquée, un contrôle qui a mordu sur une tournure — ne se
    reproduit pas forcément à la tentative suivante. Un essai de plus coûte un
    chapitre ; un document amputé coûte le dossier entier.

    ## Ce qu'elle ne fait pas

    Elle n'insiste pas. Un seul essai par chapitre, et le budget garde la main :
    un dossier qui a brûlé son plafond ne le dépasse pas pour un rattrapage.
    Ce qui reste perdu est NOMMÉ dans le rapport — un rattrapage raté en
    silence ressemblerait à un dossier qui n'en avait pas besoin.
    """
    from .chapitres import produire_chapitre  # noqa: PLC0415
    from .cost import budget_restant  # noqa: PLC0415
    from .models import ChapterStatus  # noqa: PLC0415

    manquants = list(
        job.chapters.exclude(status=ChapterStatus.DONE)
        .order_by("chapter_number")
        .values_list("chapter_number", flat=True)
    )
    for numero in manquants[:MAX_CHAPITRES_PAR_PASSE]:
        if budget_restant(job) < MARGE_DE_BUDGET:
            rapport.chapitres_perdus.append(numero)
            continue
        try:
            produire_chapitre(job, numero, client=client)
        except Exception:  # noqa: BLE001 — un chapitre qui résiste n'arrête pas la relecture
            _log.exception(
                "Relecture finale : chapitre %s non rattrapé (job %s)", numero, job.id
            )
            rapport.chapitres_perdus.append(numero)
            continue
        rapport.chapitres_rattrapes.append(numero)
    # Ceux qu'on n'a même pas tentés, faute de place dans la passe.
    rapport.chapitres_perdus.extend(manquants[MAX_CHAPITRES_PAR_PASSE:])


def relire_et_corriger(
    job: GenerationJob,
    *,
    client: Any = None,
    max_passes: int = MAX_PASSES,
) -> RapportRelecture:
    """Relit le livrable assemblé, fait corriger, et le refait. Ne lève jamais.

    Une panne de relecture ne doit pas priver le client d'un document payé :
    l'échec devient un rapport et un incident, et la livraison suit son cours
    avec le document tel qu'il est.
    """
    from documents.livrable_word import assembler_livrable_word, chaine_word_active  # noqa: PLC0415

    from .cost import budget_restant  # noqa: PLC0415
    from .meta_discours import consigne_de_correction  # noqa: PLC0415
    from .runner import regenerate_chapter  # noqa: PLC0415

    rapport = RapportRelecture()
    # La trace s'ouvre AVANT la première passe. Si le processus meurt en cours
    # — worker tué, mémoire épuisée —, le dossier garde la preuve qu'une
    # relecture avait commencé, au lieu de ressembler à un dossier jamais relu
    # (règle 1 : ce qui échoue ne doit pas se taire). Mesuré le 12/09/2026 :
    # une tâche morte pendant cette étape ne laissait ni trace, ni incident,
    # ni document envoyé.
    _inscrire(job, {**rapport.as_details(), "motif_d_arret": "en cours"})
    if not chaine_word_active(job):
        rapport.motif_d_arret = "ce dossier n'est pas produit par la chaîne Word"
        return rapport

    # Un chapitre MANQUANT se refait ; il ne s'attend pas.
    #
    # Jusqu'ici, un chapitre mort en cours de génération amputait le livrable,
    # le contrôle d'intégrité le retenait, et le dossier passait en
    # « intervention requise » — c'est-à-dire qu'il attendait une main qui ne
    # pouvait rien : personne ne réécrit un chapitre à la main, et la cliente
    # l'a dit en ces termes le 12/09/2026 (« on ne peut rien faire sur le
    # document, nous »).
    #
    # Or la boucle ci-dessous sait déjà réécrire des chapitres. Elle ne
    # s'appliquait qu'aux chapitres PRÉSENTS et fautifs — le cas le plus grave,
    # celui du chapitre absent, était le seul qu'elle ne traitait pas
    # (règle 9 : le contrôle et sa réparation ne regardaient pas la même chose).
    _refaire_les_chapitres_manquants(job, rapport, client=client)

    for passe in range(1, max_passes + 1):
        try:
            # AUCUN incident de réserves ici. La livraison assemble le même
            # document juste après et ouvre le sien, sur le fichier qui part
            # vraiment ; en ouvrir un par passe donnerait trois incidents pour
            # un seul document, dont deux décrivant des fichiers qui n'existent
            # plus. Ce que la relecture a FAIT, elle le consigne à part.
            # Sans conversion PDF : ces passes vérifient le CONTENU du
            # fichier. Faire tourner LibreOffice sur deux cents pages à chaque
            # passe coûtait des minutes et de la mémoire dans le worker
            # partagé — et le 12/09/2026 la tâche est morte là, sans rien
            # livrer ni rien laisser. La livraison convertit, elle.
            livrable = assembler_livrable_word(
                job, ouvrir_incident=False, convertir=False
            )
        except Exception as erreur:  # noqa: BLE001 — un assemblage raté n'est pas une panne de relecture
            _log.exception("Relecture finale : assemblage impossible (job %s)", job.id)
            rapport.motif_d_arret = f"assemblage impossible ({type(erreur).__name__})"
            return rapport

        anomalies = list(livrable.controle.anomalies) if livrable.controle else []
        # Le gate de livraison est relu ICI, à chaque passe, et non plus par
        # une boucle à part. Voir `_motifs_du_gate`.
        lus = _echecs_du_gate(job)
        gate_illisible = lus is None
        echecs_du_gate: tuple[Any, ...] = lus or ()
        if passe == 1:
            rapport.anomalies_au_depart = len(anomalies) + len(echecs_du_gate)
        rapport.passes = passe
        rapport.anomalies_restantes = len(anomalies) + len(echecs_du_gate)
        rapport.restantes = [
            f"ch. {a.chapitre or '—'} · {a.controle} : {a.detail}" for a in anomalies
        ] + [
            f"ch. {e.chapter_number or '—'} · {e.check} : {e.detail}"
            for e in echecs_du_gate
        ]
        if gate_illisible:
            rapport.restantes.append(
                "gate illisible : ses motifs n'ont pas pu être lus à cette passe"
            )

        par_chapitre = _motifs_par_chapitre(_reparables(anomalies))
        for numero, motifs in _motifs_du_gate(echecs_du_gate).items():
            par_chapitre.setdefault(numero, []).extend(motifs)
        if not par_chapitre:
            rapport.motif_d_arret = (
                "gate illisible — aucune anomalie réparable parmi celles lues"
                if gate_illisible
                else "aucune anomalie réparable par une réécriture de chapitre"
            )
            return rapport
        if passe == max_passes:
            rapport.motif_d_arret = f"plafond de {max_passes} passes atteint"
            return rapport
        if budget_restant(job) < MARGE_DE_BUDGET:
            rapport.motif_d_arret = "budget du dossier épuisé"
            return rapport

        # Par GRAVITÉ, puis par numéro : les chapitres désignés par le gate
        # passent dans l'ordre de `_CHECK_PRIORITY`, avant ceux que seule la
        # lecture du fichier désigne. Voir `_priorites_du_gate`.
        priorites = _priorites_du_gate(echecs_du_gate)
        ordre = sorted(par_chapitre, key=lambda n: (priorites.get(n, 10_000), n))
        for numero in ordre[:MAX_CHAPITRES_PAR_PASSE]:
            if budget_restant(job) < MARGE_DE_BUDGET:
                rapport.motif_d_arret = "budget du dossier épuisé"
                return rapport
            chapitre = job.chapters.filter(chapter_number=numero).first()
            if chapitre is None:
                continue
            try:
                regenerate_chapter(
                    job,
                    chapitre,
                    client=client,
                    corrective_note=consigne_de_correction(par_chapitre[numero]),
                )
            except Exception:  # noqa: BLE001 — un chapitre qui résiste n'arrête pas la relecture
                _log.exception(
                    "Relecture finale : chapitre %s non réécrit (job %s)", numero, job.id
                )
                continue
            rapport.chapitres_reecrits.append(numero)

        if not rapport.chapitres_reecrits:
            rapport.motif_d_arret = "aucun chapitre n'a pu être réécrit"
            return rapport

    return rapport


def relire_avant_envoi(job: GenerationJob, *, client: Any = None) -> RapportRelecture:
    """Le point d'entrée du pipeline : relit, corrige, et laisse une trace.

    L'incident n'est ouvert que si la relecture a FAIT quelque chose ou n'a pas
    pu s'exécuter. Une relecture qui ne trouve rien ne doit rien écrire : un
    journal qui parle à chaque dossier ne se lit plus.
    """
    from monitoring.models import IncidentSeverity, OperationalIncident  # noqa: PLC0415

    try:
        rapport = relire_et_corriger(job, client=client)
    except Exception as erreur:  # noqa: BLE001 — la livraison prime
        _log.exception("Relecture finale impossible (job %s)", job.id)
        rapport = RapportRelecture(
            motif_d_arret=f"relecture impossible ({type(erreur).__name__} : {erreur})"
        )

    _inscrire(job, rapport.as_details())

    if rapport.a_corrige or not rapport.passes:
        OperationalIncident.objects.create(
            title=f"Relecture finale du livrable (job {job.id})",
            severity=IncidentSeverity.MEDIUM if rapport.passes else IncidentSeverity.HIGH,
            job=job,
            order=job.order,
            details=rapport.as_details(),
        )
    _log.info("Job %s — %s", job.id, rapport.resume())
    return rapport


def _inscrire(job: GenerationJob, details: dict[str, Any]) -> None:
    """Écrit la trace sur le dossier. Ne lève jamais — c'est une trace.

    La trace vit sur le DOSSIER, pas seulement dans un incident : c'est elle
    que le tableau de bord affiche entre l'assemblage et l'envoi. Une étape qui
    n'existe que dans le code n'existe pas pour qui regarde le dossier.
    """
    from .models import GenerationJob as Dossier  # noqa: PLC0415

    try:
        Dossier.objects.filter(pk=job.pk).update(controle_final=details)
    except Exception:  # noqa: BLE001 — une trace manquante ne retient pas un livrable
        _log.exception("Trace du contrôle final non écrite (job %s)", job.id)

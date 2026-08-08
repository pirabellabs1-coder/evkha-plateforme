"""Suivi d'une génération, tel que le client doit le voir (§9.4).

Le cahier des charges demande « statut détaillé et progression : constitution
du socle, chapitre en cours, vérification, rendu » et « un message clair en cas
d'incident, sans jargon technique ».

## Deux règles de rédaction, et elles ne sont pas cosmétiques

**Aucun jargon.** `intervention_requise`, `CostBudgetExceededError`,
`SocleGenerationError` ne veulent rien dire pour un client. Ce module traduit
chaque état en une phrase qui dit ce qui se passe et ce qu'il doit faire — ou
qu'il n'a rien à faire.

**Aucun message d'erreur technique ne fuit vers le client.** `error_message`
contient des traces, des noms de classes et parfois des extraits de prompt. Il
reste côté administration. Le client reçoit un message écrit pour lui, et
EVKHA est prévenue.

## La progression n'est pas inventée

Elle est **comptée** sur les chapitres réellement terminés. Une barre qui
avance toute seule pendant que rien ne se passe est un mensonge, et le client
s'en aperçoit au moment où elle atteint 99 % et s'arrête.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.utils import timezone

from generation.models import (
    ChapterGeneration,
    ChapterStatus,
    GenerationJob,
    JobStatus,
    SocleDonnees,
    SocleStatut,
)


@dataclass(frozen=True)
class Etape:
    """Une étape du parcours de production, telle que le client la lit."""

    cle: str
    libelle: str
    #: `attente`, `en_cours`, `fait`, `echec`
    etat: str
    detail: str = ""


#: Le parcours du §13, dans l'ordre. Il est FIXE : afficher des étapes
#: différentes selon l'avancement empêcherait le client de savoir où il en est.
PARCOURS = (
    ("socle", "Constitution des données de référence"),
    ("chapitres", "Rédaction des chapitres"),
    ("verification", "Vérification de cohérence"),
    ("rendu", "Mise en forme Word et PDF"),
)

#: Statut du job → message destiné au CLIENT. Aucun terme technique.
MESSAGES: dict[str, str] = {
    JobStatus.PENDING: (
        "Votre étude est dans la file de production. Elle démarre dans quelques "
        "instants."
    ),
    JobStatus.RUNNING: (
        "Votre étude est en cours de production. Vous n'avez rien à faire : "
        "vous serez prévenu dès qu'elle est prête."
    ),
    JobStatus.DONE: "Votre étude est prête. Vous pouvez la télécharger.",
    JobStatus.CANCELLED: "Cette étude a été annulée.",
    JobStatus.FAILED: (
        "La production s'est interrompue. Notre équipe a été prévenue et "
        "reprend l'étude — vous n'avez aucune démarche à faire."
    ),
    JobStatus.INTERVENTION_REQUISE: (
        "Votre étude demande une vérification de notre part avant d'être "
        "livrée. Notre équipe s'en occupe et revient vers vous."
    ),
}

#: États où le client peut légitimement s'inquiéter du délai. Ailleurs, on ne
#: montre pas d'estimation : une estimation fausse est pire que pas
#: d'estimation.
EN_PRODUCTION = (JobStatus.PENDING, JobStatus.RUNNING)

#: Durée observée d'une étude complète, en minutes. Fourchette volontairement
#: large : annoncer « 12 minutes » et en prendre 40 détruit la confiance bien
#: plus sûrement que d'annoncer « entre 20 et 40 ».
DUREE_MINUTES = (20, 45)


def _etat_socle(job: GenerationJob) -> tuple[str, str]:
    enregistrement = SocleDonnees.objects.filter(job=job).first()
    if enregistrement is None:
        return ("en_cours" if job.status == JobStatus.RUNNING else "attente", "")
    if enregistrement.statut == SocleStatut.VALIDE:
        nombre = len(enregistrement.contenu.get("donnees", []))
        return "fait", f"{nombre} données de référence établies"
    if enregistrement.statut == SocleStatut.INVALIDE:
        return "echec", "Les données de référence sont à revoir"
    return "en_cours", "Recherche et vérification des chiffres"


def etapes(job: GenerationJob) -> list[Etape]:
    """Les quatre étapes du parcours, avec leur état réel."""
    chapitres = ChapterGeneration.objects.filter(job=job)
    total = chapitres.count()
    faits = chapitres.filter(status=ChapterStatus.DONE).count()
    en_cours = chapitres.filter(status=ChapterStatus.RUNNING).first()
    echoues = chapitres.filter(status=ChapterStatus.FAILED).count()

    etat_socle, detail_socle = _etat_socle(job)

    if job.status == JobStatus.DONE:
        etats = {"socle": "fait", "chapitres": "fait", "verification": "fait", "rendu": "fait"}
    elif faits == 0:
        etats = {
            "socle": etat_socle,
            "chapitres": "attente",
            "verification": "attente",
            "rendu": "attente",
        }
    elif faits < total:
        etats = {
            "socle": "fait",
            "chapitres": "en_cours",
            "verification": "attente",
            "rendu": "attente",
        }
    else:
        etats = {
            "socle": "fait",
            "chapitres": "fait",
            "verification": "en_cours",
            "rendu": "attente",
        }

    # Un échec fige l'étape en cours : la laisser en « en cours » ferait
    # tourner l'indicateur indéfiniment devant un client qui attend.
    if job.status in (JobStatus.FAILED, JobStatus.INTERVENTION_REQUISE):
        for cle, valeur in etats.items():
            if valeur == "en_cours":
                etats[cle] = "echec"

    details = {
        "socle": detail_socle,
        "chapitres": (
            f"{faits} chapitre{'s' if faits > 1 else ''} sur {total}"
            if total
            else ""
        )
        # Le titre du chapitre en cours n'est pas toujours renseigné : il est
        # écrit par le plan, qui arrive parfois après la mise en file. Sans ce
        # test, l'écran affichait « 9 chapitres sur 22 · en cours : » suivi de
        # rien — une phrase coupée en deux, qui donne l'impression que la page
        # n'a pas fini de charger. Vu à l'écran le 06/08/2026.
        + (
            f" · en cours : {en_cours.chapter_title}"
            if en_cours and (en_cours.chapter_title or "").strip()
            else ""
        )
        + (f" · {echoues} à reprendre" if echoues else ""),
        "verification": "",
        "rendu": "",
    }

    return [
        Etape(cle, libelle, etats[cle], details.get(cle, ""))
        for cle, libelle in PARCOURS
    ]


def progression(job: GenerationJob) -> int:
    """Avancement en pourcentage, **compté** et non simulé.

    Le socle vaut 15 %, les chapitres 70 %, la vérification et le rendu 15 %.
    Une barre qui avance toute seule pendant que rien ne se passe se trahit au
    moment où elle atteint 99 % et s'arrête.
    """
    if job.status == JobStatus.DONE:
        return 100
    if job.status == JobStatus.CANCELLED:
        return 0

    part = 0
    if _etat_socle(job)[0] == "fait":
        part += 15

    chapitres = ChapterGeneration.objects.filter(job=job)
    total = chapitres.count()
    if total:
        part += int(70 * chapitres.filter(status=ChapterStatus.DONE).count() / total)
    return min(part, 99)


def message_client(job: GenerationJob) -> str:
    """Phrase destinée au client. Le message technique reste côté administration."""
    return MESSAGES.get(str(job.status), "Votre étude est en cours de traitement.")


#: En deçà de cet avancement, on refuse d'extrapoler.
#:
#: Une règle de trois sur 3 % d'avancement multiplie par trente-trois la moindre
#: irrégularité de démarrage — et le démarrage est justement irrégulier : mise
#: en file, recherche documentaire, premiers appels plus lents. Annoncer
#: « 4 heures » à quelqu'un qui en a pour vingt minutes est pire que ne rien
#: annoncer (règle 1 : on se tait plutôt que de mentir).
PROGRESSION_MINIMALE_POUR_ESTIMER = 12

#: Et en deçà de cette durée écoulée, la mesure du rythme n'a rien mesuré.
SECONDES_MINIMALES_POUR_ESTIMER = 90

#: Nombre d'études passées consultées pour l'estimation de repli.
ETUDES_PASSEES_CONSULTEES = 20

#: Il en faut au moins trois : une médiane sur deux valeurs n'est pas une
#: médiane, c'est une moyenne de deux accidents.
ETUDES_PASSEES_MINIMALES = 3


def _duree_mediane_des_etudes_passees(job: GenerationJob) -> timedelta | None:
    """Combien de temps ont réellement pris les études du même type.

    La MÉDIANE et non la moyenne : une étude qui a échoué puis repris traîne
    parfois trois heures, et une seule suffirait à décaler une moyenne pour tout
    le monde.

    Restreinte au même type de livrable : un business plan et une étude
    concurrentielle n'ont ni le même nombre de chapitres ni la même recherche.
    Les mélanger donnerait une estimation juste en moyenne et fausse pour
    chacun.
    """
    # Les deux dates sont re-testées ici alors que la requête les filtre déjà.
    # Ce n'est pas de la superstition : `values_list` rend des `datetime | None`
    # quel que soit le filtre, et mypy a raison de le refuser. Le contrôle
    # explicite vaut mieux qu'un `type: ignore` qui affirmerait ce que le typage
    # ne peut pas savoir.
    durees: list[timedelta] = []
    for demarre, termine in (
        GenerationJob.objects.filter(
            deliverable_type=job.deliverable_type,
            status=JobStatus.DONE,
            started_at__isnull=False,
            completed_at__isnull=False,
        )
        .order_by("-completed_at")
        .values_list("started_at", "completed_at")[:ETUDES_PASSEES_CONSULTEES]
    ):
        if demarre is None or termine is None or termine <= demarre:
            continue
        durees.append(termine - demarre)
    if len(durees) < ETUDES_PASSEES_MINIMALES:
        return None
    durees.sort()
    return durees[len(durees) // 2]


def fin_estimee(job: GenerationJob) -> dict[str, Any] | None:
    """Dans combien de temps l'étude sera-t-elle prête ? Ou rien.

    Trois sources, essayées dans cet ordre, de la plus fiable à la moins :

    1. **Cette étude elle-même.** L'avancement est compté, pas simulé
       (`progression`) : si 40 % du travail a pris dix minutes, le reste en
       prendra quinze. C'est la seule source qui tienne compte d'une journée où
       l'API répond lentement.
    2. **Les études passées du même type**, par leur durée médiane. Utile au
       démarrage, quand il n'y a encore rien à extrapoler.
    3. **Rien.** L'appelant affiche alors la fourchette large `DUREE_MINUTES`,
       qui ne prétend pas être une estimation.

    On réutilise `progression` plutôt que de recompter les chapitres : deux
    mesures de l'avancement finiraient par se contredire à l'écran, l'une dans
    la barre et l'autre dans le compte à rebours (règle 5).

    Le résultat n'est JAMAIS négatif ni nul : une étude en retard sur sa propre
    estimation affiche « bientôt », pas « il y a trois minutes ».
    """
    if job.status not in EN_PRODUCTION or job.started_at is None:
        return None

    maintenant = timezone.now()
    ecoule = maintenant - job.started_at
    avancement = progression(job)

    reste: timedelta | None = None
    fondee_sur = ""

    if (
        avancement >= PROGRESSION_MINIMALE_POUR_ESTIMER
        and ecoule.total_seconds() >= SECONDES_MINIMALES_POUR_ESTIMER
    ):
        total_estime = ecoule * (100 / avancement)
        reste = total_estime - ecoule
        fondee_sur = "cette_etude"
    else:
        mediane = _duree_mediane_des_etudes_passees(job)
        if mediane is not None:
            reste = mediane - ecoule
            fondee_sur = "etudes_passees"

    if reste is None:
        return None

    # Plancher d'une minute : une étude qui dépasse son estimation doit dire
    # « bientôt », jamais un nombre négatif ni zéro.
    minutes = max(1, round(reste.total_seconds() / 60))
    return {
        "minutes_restantes": minutes,
        "fondee_sur": fondee_sur,
        "echeance": (maintenant + timedelta(minutes=minutes)).isoformat(),
    }


#: Seul état dans lequel un document peut être remis au client.
#:
#: Liste FERMÉE, et volontairement réduite à un élément : tout autre état —
#: échec, annulation, intervention requise — signifie que le système lui-même
#: ne garantit pas le document. On énumère ce qui est livrable, pas ce qui ne
#: l'est pas (règle 4).
ETATS_LIVRABLES = ("done",)


def fichiers_du_client(job: GenerationJob) -> list[dict[str, str]]:
    """Documents que le client peut réellement télécharger.

    **Un document retenu par le contrôle qualité restait téléchargeable.**
    `_assembler_livrable` écrit les artefacts en `READY` avec leur URL AVANT
    que la vérification ne tranche ; quand elle bloque, `LivrableRetenuError`
    empêche l'envoi du courriel — et rien d'autre. L'espace client, lui,
    listait tous les `DOCX`/`PDF` du job sans regarder ni leur statut ni celui
    du job. Le client téléchargeait donc, d'un bouton, le document que le
    système venait de déclarer défectueux.

    C'est la règle 3 : le contrôle protégeait le courriel, pas ce que le
    lecteur allait ouvrir. Et la règle 5 : deux vues listaient ces fichiers
    chacune de leur côté, avec deux filtres différents — d'où ce prédicat
    unique, que les deux appellent.
    """
    from documents.models import ArtifactKind, ArtifactStatus, DocumentArtifact

    if job.status not in ETATS_LIVRABLES:
        return []

    return [
        {"kind": artefact.kind, "statut": artefact.status, "url": artefact.download_url}
        for artefact in DocumentArtifact.objects.filter(
            job=job, kind__in=[ArtifactKind.DOCX, ArtifactKind.PDF]
        )
        if artefact.download_url and artefact.status == ArtifactStatus.READY
    ]


def en_dict(job: GenerationJob) -> dict[str, Any]:
    """Suivi complet d'une génération, pour l'espace client."""
    fichiers = fichiers_du_client(job)

    return {
        "id": str(job.id),
        "type": job.deliverable_type,
        "statut": job.status,
        "message": message_client(job),
        "progression": progression(job),
        "en_production": job.status in EN_PRODUCTION,
        "duree_estimee_minutes": (
            list(DUREE_MINUTES) if job.status in EN_PRODUCTION else None
        ),
        # Estimation MESURÉE, ou `null`. La fourchette ci-dessus reste rendue :
        # elle sert de repli quand il n'y a encore rien à mesurer, et elle ne
        # prétend pas être une estimation.
        "fin_estimee": fin_estimee(job),
        "cree_le": job.created_at.isoformat(),
        "demarre_le": job.started_at.isoformat() if job.started_at else None,
        "termine_le": job.completed_at.isoformat() if job.completed_at else None,
        "etapes": [
            {
                "cle": etape.cle,
                "libelle": etape.libelle,
                "etat": etape.etat,
                "detail": etape.detail,
            }
            for etape in etapes(job)
        ],
        "fichiers": fichiers,
    }

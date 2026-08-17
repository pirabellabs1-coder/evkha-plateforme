from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from catalog.models import DeliverableType
from intake.models import IntakeStatus, IntakeSubmission

from .blueprints import chapters_for_deliverable
from .cost import PLAFOND_PAR_LIVRABLE
from .models import ChapterGeneration, ChapterStatus, GenerationJob, JobStatus

# Livrables couverts par le moteur de generation (phases 2-5).
_SUPPORTED_DELIVERABLES = frozenset(
    {
        DeliverableType.MARKET_STUDY,
        DeliverableType.COMPETITOR_STUDY,
        DeliverableType.BUSINESS_PLAN,
        DeliverableType.BUSINESS_STRATEGY,
    }
)

# Budget IA par type de livrable, aligne sur le cout reel d'une generation
# COMPLETE (pas etranglee). Historique : budget EM 2.30-2.40 EUR + throttle
# _MIN_MAX_TOKENS=400 produisait des chapitres tardifs a 1200 tokens output
# (SWOT/risques/conclusion tronques). Correctif complet :
#   - _MIN_MAX_TOKENS releve a 2500 (cf. cost.py) : plus de contenu etrangle
#   - Budget EM releve a 3.20 EUR pour absorber le plancher garanti
#   - Prompt caching Anthropic (integrations/claude.py) reduit ~0.30 EUR/job
# Cible reelle apres tous les fixes : EM ~2.40-2.90 EUR / job avec contenu
# structurellement complet.
#
# Revision juillet 2026 — EM portee de 3,20 a 4,00 EUR. Deux faits mesures, pas
# une precaution :
#   - le run reel 010e3bf2 (22 chapitres) a coute 3,05 EUR, soit 95 % du
#     plafond de 3,20 : il n'y avait plus de marge pour un seul retry ;
#   - l'extended thinking (1024 tokens/appel, EVKHA_THINKING_BUDGET_TOKENS)
#     ajoute ~0,41 EUR sur 30 appels. A budget inchange, le throttle aurait
#     etrangle les derniers chapitres — exactement le defaut que le plancher
#     _MIN_MAX_TOKENS=2500 avait corrige.
# 4,00 EUR = 3,05 mesure + 0,41 de reflexion + ~0,55 de marge de retry.
#
# Revision (tache #12) — EM portee de 4,00 a 4,60 EUR. Le cout des 11 CHECKs
# n'etait ENREGISTRE NULLE PART (cf. checks_blocs._enregistrer_cout_check) : la
# depense existait cote Anthropic mais pas dans le grand livre. Les 3,05 EUR
# mesures sur le run 010e3bf2 sous-estimaient donc la realite d'environ
# 0,46 EUR. Maintenant que les CHECKs sont comptes, le plafond de 4,00 EUR
# aurait tue le job vers 95 % sur un cout qui, lui, n'a pas bouge.
#   3,05 chapitres mesures
# + 0,41 extended thinking (30 appels x 1024 tokens)
# + 0,46 CHECKs, desormais visibles (11 CHECKs, ~6 000 tok in / ~2 000 tok out)
# + 0,22 advisor sur les 5 blocs quantifies (EVKHA_ADVISOR_BLOCS)
# = 4,14 EUR attendus, + ~0,46 de marge de retry -> 4,60 EUR.
# Leviers de retour en arriere, par ordre d'effet : EVKHA_ADVISOR_ENABLED=false
# (-0,22), EVKHA_THINKING_BUDGET_TOKENS=0 (-0,41).
#
# Revision 05/08/2026 — les quatre budgets releves d'environ 30 % pour la
# bascule vers claude-sonnet-5. Ce n'est PAS une hausse de tarif : Sonnet 5 est
# facture au meme prix que Sonnet 4.6 (3 $ / 15 $ par million de tokens). C'est
# un changement de TOKENIZER — le meme texte y compte environ 30 % de tokens en
# plus. A budget inchange, le throttle aurait donc rabote max_tokens sur les
# derniers chapitres pour tenir un plafond calibre sur l'ancien decoupage : des
# chapitres plus courts, c'est-a-dire le defaut meme que la cliente signale.
#
# Le pourcentage s'applique a chaque ligne parce que la cause est commune a
# tous les livrables — ce n'est pas l'EM qui coute plus cher, c'est chaque
# token qui compte differemment (regle 4 : viser la classe, pas l'exemple).
#
# Ces valeurs restent une PROJECTION tant qu'aucune generation reelle n'a
# tourne sur Sonnet 5. La premiere mesure reelle doit etre reportee ici et dans
# journal_generations.md (regle 10) — et elle prime sur ce calcul.
# ── Deux nombres, et le code n'en avait qu'un ────────────────────────────────
#
# `budget_eur` servait A LA FOIS de rythme et de plafond. Le throttle de
# `cost.py` repartit le budget RESTANT sur les appels restants : baisser ce
# nombre ne fait pas baisser la depense, il RETRECIT chaque chapitre.
#
# Mesure du 05/08/2026, sur le vrai `max_tokens_for_job` : en dessous de
# 3,80 EUR de budget, le premier appel d'une etude de marche est deja borne au
# plancher de 2 500 jetons de sortie — alors que ses chapitres en consomment
# environ 3 000. Poser 3,00 EUR ici n'aurait donc pas coute 3,00 EUR : cela
# aurait produit vingt-trois chapitres rabotes, c'est-a-dire le defaut meme que
# la cliente signale.
#
# On separe donc les deux roles. Le RYTHME reste dimensionne sur le travail a
# faire ; le PLAFOND DE DEPENSE, lui, est une decision commerciale et il
# s'applique en dur (voir `cost.enforce_budget`).
#: Rythme du throttle, par livrable. **Ce n'est PAS une seconde table** : c'est
#: `cost.PLAFOND_PAR_LIVRABLE`, relue ici. Deux tables aux memes nombres
#: auraient diverge au premier ajustement, et c'est la regle 5.
#:
#: Rythme et plafond valent la meme valeur, et c'est voulu. Ils ont differe
#: jusqu'au 08/08/2026 — rythme 4,00, plafond 3,10 — et le throttle cadencait
#: alors vers un montant que le frein n'autorisait pas : allocation genereuse,
#: puis coupure nette avant la fin du dossier.
#:
#: Plafonds arretes par la cliente le 08/08/2026 : etude de marche 6,00,
#: business plan 4,00, strategie 4,00, etude concurrentielle 3,50. Ce sont des
#: PLAFONDS, pas des cibles — les deux seules etudes de marche completes
#: mesurees ont coute 3,12 et 3,32 EUR, et rien ne pousse le moteur a depenser
#: davantage parce qu'on lui en laisse la place.
#:
#: Ce que la hausse achete : le throttle cesse de raboter les chapitres (sous
#: 3,80 EUR sur une etude de marche, chaque appel etait deja borne au plancher —
#: le defaut meme que la cliente avait signale), et `_has_budget_headroom`
#: autorise plus de rondes de correction avant de refuser une regeneration.
#:
#: Ce qu'elle n'achete PAS, et il faut le dire : aucun graphique de plus. Les
#: figures sont rendues par matplotlib depuis le socle
#: (`rendu_word/donnees_graphiques.py`), sans le moindre appel API. Une figure
#: abandonnee l'est parce que le socle ne peut pas l'alimenter — identifiants
#: absents, unites heterogenes, un seul chiffre — jamais faute de budget.
#:
#: AVERTISSEMENT sur les deux mesures citees : elles datent d'avant le correctif
#: de comptabilisation du 08/08/2026, qui ecrasait le cout des chapitres
#: regeneres. Elles SOUS-ESTIMENT la depense reelle, d'autant plus que le
#: dossier a subi des reprises. Le prochain dossier reel donnera le premier
#: chiffre honnete.
_BUDGET_EUR_BY_TYPE: dict[str, Decimal] = PLAFOND_PAR_LIVRABLE


class GenerationBootstrapError(ValueError):
    pass


def bootstrap_generation_job(submission: IntakeSubmission) -> GenerationJob:
    if submission.status != IntakeStatus.NORMALIZED:
        msg = "Generation requires a normalized intake submission."
        raise GenerationBootstrapError(msg)

    # Offres B2B génériques (abonnements, crédits suppl.) :
    # deliverable_type est dans le payload Tally.
    deliverable_type = (
        submission.order.offer.deliverable_type
        or submission.normalized_variables.get("DELIVERABLE_TYPE")
    )
    if deliverable_type not in _SUPPORTED_DELIVERABLES:
        msg = f"Unsupported deliverable type for generation: {deliverable_type}"
        raise GenerationBootstrapError(msg)

    job, _created = GenerationJob.objects.get_or_create(
        order=submission.order,
        defaults={
            "deliverable_type": str(deliverable_type),
            "status": JobStatus.PENDING,
            "budget_eur": _BUDGET_EUR_BY_TYPE[deliverable_type],
        },
    )

    for blueprint in chapters_for_deliverable(deliverable_type):
        ChapterGeneration.objects.get_or_create(
            job=job,
            chapter_number=blueprint.number,
            defaults={
                "chapter_title": blueprint.title,
                "prompt_key": blueprint.prompt_key,
            },
        )

    return job


#: Au-delà de ce silence, un dossier « en cours » ne l'est plus vraiment.
#:
#: Le chapitre le plus lent jamais mesuré sur ce projet a pris 10,2 minutes —
#: étude de marché `b561c2d6`, avant que le contrôle de ressemblance ne soit
#: rendu consultatif. On double, et on arrondit : vingt minutes sans qu'aucun
#: chapitre ne bouge ne s'expliquent plus par la lenteur.
DELAI_SANS_PROGRESSION = timedelta(minutes=20)

def production_engagee(job: GenerationJob) -> bool:
    """Ce dossier a-t-il DÉJÀ produit quelque chose ?

    La question se pose parce que le statut peut mentir. Il n'est écrit qu'une
    fois, au lancement, et la relance du tableau de bord le remet à `pending`
    en effaçant `started_at` — y compris sous une tâche qui travaille. Le
    dossier `256e63d8` du 17/08/2026 a ainsi écrit dix-sept chapitres en se
    déclarant « en attente ».

    Ce que la production laisse comme trace, elle, ne se réécrit pas : un
    chapitre sorti de `pending`, ou un centime dépensé. On lit donc les FAITS
    plutôt que l'étiquette — c'est la règle 1 (un contrôle qui n'a rien à
    comparer échoue) appliquée à l'état d'un dossier.
    """
    if job.total_cost_eur > 0:
        return True
    return job.chapters.exclude(status=ChapterStatus.PENDING).exists()


def reaffirmer_en_cours(job: GenerationJob) -> bool:
    """Remet la ligne d'accord avec la réalité : ce dossier travaille.

    Rend `True` si elle mentait. Appelée par le runner entre deux chapitres —
    voir là-bas pourquoi une seule écriture au lancement ne suffit pas.

    Ne touche PAS à un dossier annulé : l'annulation est une décision, et le
    runner la lit juste avant pour s'arrêter. L'écraser ferait produire un
    dossier que quelqu'un a explicitement arrêté.
    """
    if job.status in (JobStatus.RUNNING, JobStatus.CANCELLED):
        return False
    job.status = JobStatus.RUNNING
    if job.started_at is None:
        job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at", "updated_at"])
    return True


def duree_sans_progression(job: GenerationJob) -> timedelta | None:
    """Depuis combien de temps ce dossier n'a-t-il plus rien produit ?

    `None` s'il n'est pas en cours — la question ne se pose pas pour un dossier
    terminé, échoué ou annulé.

    On regarde la date du dernier CHAPITRE touché, pas celle du job : le job est
    enregistré au lancement puis plus jamais tant qu'il tourne, sa date ne dit
    donc rien de son avancement. Les chapitres, eux, sont écrits à chaque coût
    enregistré.

    ## Le trou : « en attente » avec des chapitres déjà écrits

    La question était refusée à tout dossier non-`running`, « en attente »
    compris. Or un dossier PEUT porter cette étiquette en ayant déjà produit :
    il suffit qu'on ait réécrit sa ligne pendant qu'il travaillait. Il devenait
    alors invisible aux DEUX gardiens — celui-ci et
    `reset_stuck_generation_jobs`, qui ne filtre lui aussi que sur `running`.

    Un dossier en file d'attente qui n'a RIEN produit reste hors sujet : il
    attend son tour, c'est normal, et le déclarer interrompu offrirait un
    bouton « relancer » qui ferait tourner deux générations.
    """
    en_cours = job.status == JobStatus.RUNNING or (
        job.status == JobStatus.PENDING and production_engagee(job)
    )
    if not en_cours:
        return None
    dernier = job.chapters.order_by("-updated_at").values_list("updated_at", flat=True).first()
    repere = dernier or job.started_at
    if repere is None:
        return None
    return timezone.now() - repere


def generation_interrompue(job: GenerationJob) -> bool:
    """Le dossier se dit « en cours » alors que plus personne ne travaille dessus.

    ## Le cas réel qui a créé cette fonction

    Le 09/08/2026, une cliente lance une étude depuis son espace à 06:22:59.
    Trois minutes plus tard, un déploiement redémarre les conteneurs et tue le
    processus qui produisait ses chapitres. Deux autres déploiements suivent.

    Le dossier reste `running` en base pendant **soixante-seize minutes**, avec
    deux chapitres sur vingt-trois et pas un centime de mouvement. Aucun
    incident ouvert, aucun délai de garde, aucune reprise. La cliente rafraîchit
    sa page — les journaux du serveur ne montrent qu'elle — et attend un
    document que rien ne fabrique.

    C'est le silence que la règle 1 condamne, appliqué à un dossier entier : un
    état qui n'a rien à comparer et qui, faute de mieux, se déclare vivant.

    ## Ce qui l'a rendu possible

    Un déploiement tue les générations en cours, et rien ne le rattrape : ni
    l'ordonnanceur qui a perdu sa tâche, ni le dossier qui garde son statut, ni
    la relance du tableau de bord — qui n'acceptait que `failed` et `cancelled`,
    c'est-à-dire tous les états SAUF celui où l'on se retrouve.
    """
    duree = duree_sans_progression(job)
    return duree is not None and duree > DELAI_SANS_PROGRESSION


def relaunch_generation_job(job: GenerationJob) -> None:
    """Réinitialise les statuts d'un job échoué/annulé pour permettre sa relance.

    Recale aussi le budget sur la valeur correcte pour le type de livrable —
    couvre les jobs créés avant l'introduction de _BUDGET_EUR_BY_TYPE.
    """
    job.status = JobStatus.PENDING
    job.error_message = ""
    job.started_at = None
    job.completed_at = None
    # Recale le budget uniquement si aucun chapitre n'est déjà DONE (job vierge).
    # Pour un job partiellement généré, le coût cumulé est déjà fixé — on ne touche
    # pas au budget afin d'éviter un faux incident dès le redémarrage.
    if not job.chapters.filter(status=ChapterStatus.DONE).exists():
        job.budget_eur = _BUDGET_EUR_BY_TYPE.get(job.deliverable_type, job.budget_eur)
    job.save(update_fields=["status", "error_message", "started_at", "completed_at", "budget_eur"])

    job.chapters.filter(
        status__in=[ChapterStatus.FAILED, ChapterStatus.SKIPPED]
    ).update(status=ChapterStatus.PENDING, error_message="")

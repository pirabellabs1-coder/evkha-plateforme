"""Boucle d'auto-correction avant blocage (concept "loop", brief client).

Inspiré du principe des boucles agentiques (Forward-Future/loopy) : plutôt que
de BLOQUER dès qu'un défaut subsiste, le système « apprend du résultat et fait
le pas utile suivant » — il régénère UNIQUEMENT les chapitres fautifs avec la
liste exacte des problèmes en consigne, puis repasse le gate. Répété au plus
`EVKHA_CORRECTION_ROUNDS` fois (défaut 3) ; le coût reste borné par le
plafond du livrable, pas par ce nombre.

Objectif : réduire les omissions/erreurs qui obligeaient Evangeline à relancer
manuellement, SANS dépasser le budget strict PAR DOSSIER (règle d'or #1 :
EM 3,20 € / BP 2,80 € / STR 2,40 € / EC 2,00 € max ; cible cadrage §3 : idéal
< 1-2 €). La régénération puise dans CE MÊME plafond : elle ne peut donc rien
« faire exploser ». Si la boucle n'aboutit pas dans le budget, le comportement
historique s'applique : le gate bloque la livraison (décision admin).

Bornes de sécurité :
- nombre de rondes plafonné (défaut 3) ;
- seuls les chapitres directement désignés par un échec sont régénérés ;
- AUCUNE régénération n'est lancée s'il ne reste plus de budget sur le dossier
  (on ne démarre pas un appel qu'on ne peut pas payer) ;
- un dépassement de budget en cours arrête la boucle proprement (le job reste
  bloqué, jamais livré à moitié).
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.conf import settings

from . import gate as _gate
from .cost import CostBudgetExceededError, current_job_cost_eur
from .gate import GateFailure, GateReport
from .models import GenerationJob

_log = logging.getLogger(__name__)

# Réserve minimale de budget avant de tenter une régénération : sous ce seuil,
# un nouvel appel Claude dépasserait le plafond du dossier — on s'abstient.
_BUDGET_MARGIN_EUR = Decimal("0.05")

# Cap du nombre de chapitres regenerables par round. WAOME v4 a montre
# qu'une boucle sans limite peut regenerer 15+ chapitres, prendre 100+
# minutes et faire diverger d'autres chapitres qui etaient corrects.
# Regle 4 : viser la classe. Un round efficace corrige les 6-8 defauts
# les PLUS graves, laisse le reste pour le round suivant si necessaire.
# Le tri de priorite s'appuie sur l'ordre naturel de _CHECK_PRIORITY.
_MAX_REGEN_PAR_ROUND = 8


def _has_budget_headroom(job: GenerationJob) -> bool:
    """Reste-t-il du budget sur ce dossier pour un appel de régénération ?"""
    return current_job_cost_eur(job) < (job.budget_eur - _BUDGET_MARGIN_EUR)

# Types d'échec réparables en régénérant un chapitre précis. Les échecs
# `verticales` sont au niveau document (pas de chapitre unique) : on ne les
# régénère pas automatiquement (risque de casser d'autres chapitres) — ils
# restent bloquants, à traiter à la source (brief/prompt).
#
# `etat_chiffre_client` est délibérément ABSENT : régénérer n'y changerait
# rien, la donnée de référence manque au dossier. Seule une saisie humaine du
# prévisionnel débloque ce cas — c'est tout l'intérêt de le rendre bloquant.
_CHAPTER_LEVEL_CHECKS = frozenset(
    {
        # Legacy — anciens checks du gate.
        "contamination",
        "coherence_chiffree",
        "troncature",
        "ordre_de_grandeur",
        # Un calcul faux se corrige DANS le chapitre qui l'a ecrit : il suffit
        # de refaire l'operation. Ajoute le 13/08/2026 avec le controle
        # lui-meme — un motif que la boucle ne sait pas reparer bloque sans
        # jamais aboutir, et c'est le defaut qu'on repare toute la journee.
        "calcul_faux",
        # Un chapitre qui declare « non traite » un sujet traite ailleurs se
        # repare en le REECRIVANT : le motif nomme les mots concernes, et c'est
        # exactement ce dont le redacteur a besoin.
        #
        # Ajoute le 13/08/2026 apres un audit des motifs non corrigeables :
        # depuis que la livraison ne s'arrete plus, un motif que la boucle ne
        # sait pas traiter part chez le client SANS avoir ete retente. Le
        # laisser dehors, c'etait garantir qu'il arrive tel quel.
        "demande_contredite",
        # Nouveaux checks transverses (checks_post_rendu).
        "troncature_rendu",
        "doublon_titre",
        "desaccord_numerique",
        "ton_publicitaire",
        # Prudence juridique — les 2 sous-motifs sont chacun cible.
        "prudence_juridique_evenement_corporate",
        "prudence_juridique_diffamation",
        # Sources — chapitre Sources, transverse mais chapitre identifie.
        "sources_non_tracables_vide",
        "sources_non_tracables_ratio_faible",
        "sources_non_tracables_url_bidon",
        # Fourchettes et cardinaux TCAC (EM/BP/EC/STR — checks_evangeline).
        "fourchette_interdite",
        # Le texte lui-meme (18/08/2026, retour cliente). Les deux se
        # reparent en REECRIVANT le chapitre : le motif nomme le caractere ou
        # les mots, et c'est exactement ce dont le redacteur a besoin.
        "caractere_etranger",
        "chapitre_desaccentue",
        "lettre_doublee",
        # Nouveaux checks par livrable via _check_strategie_livrable.
        # Ils portent tous le prefixe `strategy_<deliverable>_<categorie>`.
        # On les ajoute dynamiquement au frozenset au chargement.
    }
)

# Prefixes de checks « strategy_* » qu'on veut router au chapitre. Ces checks
# nommes categorie=... par la strategy (EM/BP/EC/STR) sont tous chapitre-level
# quand chapter_number > 0 (le cas 0 = transverse, non regenerable au chapitre).
_STRATEGY_CHECK_PREFIX = "strategy_"

#: Le CHECK de bloc — hors whitelist automatique, réparable sur décision.
#: Voir `_feedback_by_chapter` et `run_correction_loop(inclure_les_checks=)`.
_CHECK_BLOC = "check_bloc_non_resolu"


# Priorite des categories de check pour le tri quand on cape a
# _MAX_REGEN_PAR_ROUND chapitres. Les defauts en tete de liste sont
# regeneres en priorite dans un round. Rationnel : cohérence chiffrée >
# sources > structure > ton, dans l'ordre de gravite bancaire.
_CHECK_PRIORITY = (
    "coherence_chiffree",
    "strategy_",              # tout defaut metier par livrable
    "prudence_juridique_",    # tout defaut juridique
    "sources_non_tracables_",
    "fourchette_interdite",
    "doublon_titre",
    "troncature_rendu",
    "desaccord_numerique",
    "contamination",
    "ordre_de_grandeur",
    "troncature",
    "ton_publicitaire",
)


def _priorite_check(check: str) -> int:
    """Retourne l'index de priorite d'un check (plus petit = plus urgent).

    Les checks inconnus sont mis en fin de liste (index eleve).
    """
    for i, prefix in enumerate(_CHECK_PRIORITY):
        if check.startswith(prefix):
            return i
    return len(_CHECK_PRIORITY)

# Libellés lisibles injectés dans la consigne de correction.
_CHECK_LABELS = {
    "contamination": "Marqueur technique interne présent dans le texte (interdit)",
    "coherence_chiffree": "Chiffre incohérent avec le prévisionnel client",
    "calcul_faux": "Calcul dont le résultat ne découle pas de ses termes",
    "caractere_etranger": "Caractère d'une autre écriture dans le texte",
    "lettre_doublee": "Coquille : lettre doublée en début de mot",
    "chapitre_desaccentue": (
        "Chapitre écrit sans accents — le rédiger en français accentué"
    ),
    "demande_contredite": "Sujet déclaré « non traité » alors qu'il l'est ailleurs",
    "troncature": "Chapitre coupé / phrase ou structure non terminée",
    "ordre_de_grandeur": "Erreur d'unité : montant hors d'échelle (millions/milliers)",
    "troncature_rendu": "Chapitre tronqué : la dernière phrase n'a pas de ponctuation forte",
    "doublon_titre": (
        "Sous-titre répété dans le chapitre — préfixer par le nom de la "
        "persona/du concurrent"
    ),
    "desaccord_numerique": (
        "Annonce chiffrée (« trois familles ») incompatible avec le nombre "
        "d'items suivants"
    ),
    "ton_publicitaire": (
        "Expression au ton publicitaire ou superlatif interdit "
        "(« leader incontestable », « révolutionnaire », etc.)"
    ),
    "prudence_juridique_evenement_corporate": (
        "Événement corporate daté sans source vérifiable — ajouter une URL ou "
        "une locution « selon [Éditeur] »"
    ),
    "prudence_juridique_diffamation": (
        "Formulation à risque de diffamation (condamnation, faillite, abus de "
        "position dominante) sans source"
    ),
    "sources_non_tracables_vide": "Chapitre Sources vide — lister au moins 5 URLs http(s) réelles",
    "sources_non_tracables_ratio_faible": (
        "Chapitre Sources : moins de 50 % des références ont une URL http(s) "
        "réelle"
    ),
    "sources_non_tracables_url_bidon": (
        "URL placeholder ou factice (example.com, source.fr, crochets non "
        "substitués) — remplacer par une source réelle"
    ),
    "fourchette_interdite": (
        "Fourchette nue sans médiane annoncée dans la même phrase — écrire "
        "« X à Y, médiane retenue Z »"
    ),
}


def _default_rounds() -> int:
    try:
        return max(0, int(getattr(settings, "EVKHA_CORRECTION_ROUNDS", 1)))
    except (TypeError, ValueError):
        return 1


def _is_regenerable(check: str) -> bool:
    """Un check est regenerable au chapitre s'il est dans la whitelist OU
    s'il est prefixe `strategy_` (checks metier par livrable).

    Regle 4 : plutot que d'enumerer 15 sous-categories `strategy_*`, on
    accepte le prefixe. Chaque nouvelle strategy est routee automatiquement.
    """
    if check in _CHAPTER_LEVEL_CHECKS:
        return True
    return check.startswith(_STRATEGY_CHECK_PREFIX)


def _feedback_by_chapter(
    failures: tuple[GateFailure, ...],
    *,
    cap: int | None = None,
    inclure_les_checks: bool = False,
) -> dict[int, str]:
    """Regroupe les échecs réparables par numéro de chapitre → consigne texte.

    Les échecs sans chapter_number (transverses, ex : « aucun chapitre
    Sources ») sont ignorés — pas de chapitre unique à régénérer.
    Les échecs chapter_number == 0 (transverses aux chapitres analytiques,
    ex : TCAC cardinal) sont attribues au chapitre 1 par convention : c'est
    le point d'ancrage du raisonnement chiffre.

    Si `cap` est fourni, on garde au plus `cap` chapitres — les plus
    prioritaires selon `_CHECK_PRIORITY`. Un chapitre est priorise par la
    plus urgente de ses failures.
    """
    groupes = _motifs_par_chapitre(
        failures, cap=cap, inclure_les_checks=inclure_les_checks
    )
    return {
        numero: "\n".join(
            f"- {_CHECK_LABELS.get(f.check, f.check)} : {f.detail}" for f in motifs
        )
        for numero, motifs in groupes.items()
    }


def _motifs_par_chapitre(
    failures: tuple[GateFailure, ...],
    *,
    cap: int | None = None,
    inclure_les_checks: bool = False,
) -> dict[int, list[GateFailure]]:
    """Quels motifs partent vers quel chapitre — la répartition, pas le texte.

    Séparée de `_feedback_by_chapter` pour que la boucle sache exactement ce
    qu'elle a VISÉ à chaque ronde. Sans cette liste, elle ne peut pas comparer
    ce qu'elle a demandé à ce qu'elle a obtenu, et c'est précisément ce qui lui
    manquait pour s'arrêter (règle 9).
    """
    groupes: dict[int, list[GateFailure]] = {}
    priorites: dict[int, int] = {}
    for failure in failures:
        # Les CHECK de bloc ne sont JAMAIS rejoués par le chemin automatique :
        # la génération les a déjà retentés une fois, et boucler dessus
        # dépenserait sans rien garantir. Ils ne deviennent réparables que sur
        # décision explicite — le bouton « corriger » du recontrôle, qui EST
        # la reprise humaine que le manuel demande.
        if failure.check == _CHECK_BLOC and not inclure_les_checks:
            continue
        if failure.check != _CHECK_BLOC and not _is_regenerable(failure.check):
            continue
        if failure.chapter_number is None:
            continue
        target = failure.chapter_number if failure.chapter_number > 0 else 1
        groupes.setdefault(target, []).append(failure)
        # Priorite du chapitre = la plus urgente de ses failures.
        p = _priorite_check(failure.check)
        priorites[target] = min(priorites.get(target, p), p)

    if cap is not None and len(groupes) > cap:
        # Tri par priorite (index bas = plus urgent), puis par numero de
        # chapitre pour stabilite.
        chapitres_tries = sorted(groupes.keys(), key=lambda n: (priorites[n], n))[:cap]
        groupes = {n: groupes[n] for n in chapitres_tries}

    return groupes


def _signature(failure: GateFailure) -> tuple[str, int | None, str]:
    """Ce qui fait qu'un motif est LE MÊME d'une ronde à l'autre.

    Le libellé compte : « le tableau annonce 30 000, ses lignes font 2 400 »
    devenu « ... font 2 500 » est un motif qui a BOUGÉ, donc une correction qui
    a produit un effet, même incomplet.
    """
    return (failure.check, failure.chapter_number, failure.detail)


def run_correction_loop(
    job: GenerationJob,
    *,
    client: object | None = None,
    max_rounds: int | None = None,
    inclure_les_checks: bool = False,
) -> GateReport:
    """Exécute le gate, régénère les chapitres fautifs, repasse le gate (borné).

    Retourne le rapport final du gate (passé ou non). Ne livre rien : c'est
    l'appelant (tasks.py) qui décide, sur report.passed, de livrer ou de
    marquer le job BLOCKED.

    `inclure_les_checks` ouvre la régénération aux CHECK de bloc, dont la note
    du relecteur est souvent la plus actionnable de toutes (« dédupliquer les
    deux entrées Xerfi du tableau 21.2 »).

    Faux par DÉFAUT, mais les deux appelants passent désormais vrai. Le motif
    d'origine — « le manuel demande alors une reprise humaine » — est tombé le
    13/08/2026 : il n'y a plus de reprise humaine, l'envoi est automatique.
    Garder ces notes pour un geste qui n'existe plus, c'était les perdre.
    """
    from integrations.claude import ClaudeClient, get_claude_client  # noqa: PLC0415

    from .runner import regenerate_chapter  # noqa: PLC0415 — évite le cycle d'import

    rounds = _default_rounds() if max_rounds is None else max(0, max_rounds)
    gen_client = client if isinstance(client, ClaudeClient) else get_claude_client()

    report = _gate.run_delivery_gate(job)
    attempt = 0
    # Les motifs déjà VISÉS par une régénération et revenus IDENTIQUES.
    #
    # ## Pourquoi cette mémoire existe
    #
    # Un motif FAUX ne peut pas être fermé : le chapitre est correct, on le
    # réécrit, le contrôle le redit, et les trois rondes se consomment sans
    # rien corriger. Mesuré le 17/08/2026 sur l'étude `f0064333` — 23 motifs,
    # dont un titre en gras compté comme phrase coupée, une colonne de marchés
    # emboîtés sommée comme un total, et quatre libellés pris pour des sources.
    # Chaque ronde régénère jusqu'à huit chapitres, et chaque régénération se
    # paie.
    #
    # Le rempart amont, c'est la justesse des contrôles — trois d'entre eux
    # sont réparés le même jour. Mais aucun jeu de contrôles ne sera jamais
    # juste à coup sûr, et une boucle qui insiste sur ce qu'elle ne déplace pas
    # se donne raison toute seule : c'est la grille du *Loop Doctor* de la
    # règle 9. Elle doit MESURER son effet, et se taire quand elle n'en a pas.
    #
    # Ce qui n'est PAS abandonné : un motif qui a bougé, même sans se fermer,
    # reste retenté — la correction a produit un effet, elle peut en produire
    # un second.
    sourds: set[tuple[str, int | None, str]] = set()
    while not report.passed and attempt < rounds:
        a_retenter = tuple(
            f for f in report.failures if _signature(f) not in sourds
        )
        groupes = _motifs_par_chapitre(
            a_retenter,
            cap=_MAX_REGEN_PAR_ROUND,
            inclure_les_checks=inclure_les_checks,
        )
        vises = {_signature(f) for motifs in groupes.values() for f in motifs}
        feedback = _feedback_by_chapter(
            a_retenter,
            cap=_MAX_REGEN_PAR_ROUND,
            inclure_les_checks=inclure_les_checks,
        )
        if not feedback:
            # Aucun échec réparable au niveau chapitre (ex. verticale manquante
            # au niveau document) : la régénération ciblée n'aiderait pas.
            break
        if not _has_budget_headroom(job):
            # Plafond du dossier atteint : on ne lance pas d'appel qu'on ne
            # peut pas payer. Le job reste bloqué (décision admin).
            break
        attempt += 1
        for chapter_number, note in feedback.items():
            if not _has_budget_headroom(job):
                break
            chapter = job.chapters.filter(chapter_number=chapter_number).first()
            if chapter is None:
                continue
            # Sauvegarde AVANT toute tentative : si `regenerate_chapter` echoue
            # apres avoir mis le chapitre en RUNNING (le runner reset le
            # contenu avant l'appel Claude), on doit restaurer l'ancien
            # contenu et statut DONE. Sans ca, le renderer ignore le
            # chapitre et livre un document ampute (bug WAOME v4 22/07/2026,
            # job 45e0809c : chapitres 8, 9, 10 restes RUNNING).
            contenu_original = chapter.content
            statut_original = chapter.status
            try:
                regenerate_chapter(job, chapter, corrective_note=note, client=gen_client)
            except CostBudgetExceededError:
                # Budget dépassé en cours : on arrête, le job reste bloqué.
                # On restaure quand meme le chapitre pour ne pas livrer
                # un document ampute si l'appelant decide de rendre.
                chapter.content = contenu_original
                chapter.status = statut_original
                chapter.save(update_fields=["content", "status"])
                return _gate.run_delivery_gate(job)
            except Exception:  # noqa: BLE001 — une régénération KO ne casse pas la boucle
                # Le chapitre est peut-etre reste en RUNNING avec un contenu
                # vide. On restaure l'ancien etat pour garantir que le
                # renderer inclura ce chapitre au rendu final.
                chapter.content = contenu_original
                chapter.status = statut_original
                chapter.save(update_fields=["content", "status"])
                continue

        avant = {_signature(f) for f in report.failures}
        report = _gate.run_delivery_gate(job)
        apres = {_signature(f) for f in report.failures}

        # Ce qu'on a visé et qui est revenu mot pour mot ne se refermera pas :
        # on ne le repaie pas une troisième fois.
        sourds |= vises & apres
        if not avant - apres:
            # La ronde n'a fermé AUCUN motif. Les suivantes referaient le même
            # geste sur le même texte, pour le même prix. On rend le rapport
            # tel qu'il est : l'incident dira ce qui reste, et le document part
            # — c'est la décision du 13/08/2026, elle n'a pas à être repayée.
            _log.info(
                "Job %s : ronde de correction %s sans effet (%s motif(s) "
                "inchangé(s)) — les rondes restantes sont abandonnées.",
                job.id, attempt, len(apres),
            )
            break

    return report


def regenerable_chapter_numbers(report: GateReport) -> list[int]:  # pragma: no cover
    """Aide de diagnostic : numéros de chapitres qu'une ronde de correction ciblerait."""
    return sorted(_feedback_by_chapter(report.failures).keys())

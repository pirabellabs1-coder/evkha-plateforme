"""Les chiffres déjà posés pour ce client, dans un livrable précédent.

## Le défaut, mesuré

Étude de la concurrence `e150aade` (27/10/2026) et étude de marché du même
client : **deux totaux pour le même marché**. L'EC annonce un marché total de
1 588,6 M€ ; la référence que la cliente a réécrite à la main en annonce
1 902 M€. Son premier grief du 28/10/2026 :

    Reprendre le périmètre validé et rester cohérent avec l'étude de marché :
    mêmes pays, mêmes hypothèses, mêmes chiffres, car ce n'était pas le cas.

## Pourquoi c'était inévitable

Le cahier des charges de l'étude de la concurrence l'exige depuis le
18/05/2026 — « une cohérence systématique avec l'étude de marché lorsque
celle-ci existe » — et **aucun mécanisme ne l'assurait**. Vérifié dans le code,
pas dans un commentaire :

- `SocleDonnees` est en `OneToOneField` sur le job : un socle par dossier ;
- `socle.services` ne lit jamais que `SocleDonnees.objects.filter(job=job)` ;
- aucune requête de `socle/` ni de `chapitres/` ne regarde un autre dossier du
  même client ;
- `fact_store.load_facts_block`, qui ferait ce travail, n'est appelé que par
  `context.build_context` — l'ANCIENNE chaîne, que la production n'emprunte
  pas (`chapitres.runner` compose le prompt).

Chaque livrable refaisait donc sa propre recherche et atterrissait sur ses
propres chiffres. Deux documents du même dossier n'avaient aucune raison de
tomber d'accord.

## Ce que ce module fait

Il retrouve le dernier livrable TERMINÉ du même client qui porte un socle
verrouillé, et rend ses chiffres sous une forme lisible par le modèle. Il ne
décide rien : c'est le prompt du socle qui dit quoi en faire — les reprendre à
l'identique, et nommer l'écart quand il y en a un.

Il ne compare pas et ne juge pas : un chiffre repris à l'identique n'a pas
besoin d'être contrôlé, et un chiffre qui s'en écarte est jugé par les
contrôles de cohérence qui existent déjà.

## Le même PROJET, pas le même compte (02/11/2026)

Le client d'EVKHA est souvent une consultante qui produit des études pour
PLUSIEURS projets depuis un seul compte. Hériter « du même client » a fait
passer les chiffres de l'étude « Consultant IA pour TPE » (`99a142b0`) dans
l'étude « SUN TZU ORGANISATION », produits du terroir vendus en Asie
(`a6947890`) : le modèle les a écartés, mais en l'ÉCRIVANT dans le document
livré — « Pas de reprise de l'étude précédente : elle retenait 18,4 MdEUR pour
le marché français de l'IA » —, pages 28, 42, 65 et 70. Evangéline : « ça a
mélangé les dossiers ».

L'héritage exige donc le même `PROJET` saisi au questionnaire, comparé sans
casse ni accents ni espaces superflus. Un dossier sans nom de projet n'hérite
de rien : sans preuve que c'est le même dossier, un chiffre hérité est un
chiffre d'un autre client (règle 2 — un rapprochement faux est pire
qu'absent).
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

_log = logging.getLogger(__name__)

#: Combien de chiffres du livrable précédent on transmet. Chacun coûte des
#: jetons sur la passe de socle, et les premiers sont les fondations — taille
#: du marché, zones, périmètres. Au-delà, ce n'est plus un repère commun,
#: c'est le document précédent recopié.
MAX_CHIFFRES_HERITES = 25

#: Ce qui s'hérite : un livrable TERMINÉ dont le socle est verrouillé. Un
#: dossier en échec ou en cours n'a pas de chiffres sur lesquels s'aligner.
_STATUT_HERITABLE = "done"


def chiffres_du_livrable_precedent(job: Any) -> str:
    """Les chiffres du dernier livrable terminé du même client, ou `""`.

    Ne lève jamais : sans héritage, le socle se construit comme avant. Un
    défaut ici ne doit pas empêcher une étude d'exister.
    """
    try:
        precedent = _dernier_livrable_du_client(job)
        if precedent is None:
            return ""
        return _bloc(precedent)
    except Exception:  # noqa: BLE001 — l'héritage ne tue jamais un dossier
        _log.exception("Héritage des chiffres impossible pour le job %s", getattr(job, "id", "?"))
        return ""


def _projet(job: Any) -> str:
    """Le nom du projet saisi au questionnaire, réduit pour la comparaison."""
    from ..chapitres.services import variables_du_job  # noqa: PLC0415

    brut = str(variables_du_job(job).get("PROJET") or "")
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", brut) if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", sans_accents).strip().casefold()


def _dernier_livrable_du_client(job: Any) -> Any:
    """Le dernier dossier TERMINÉ du même client ET du même projet, avec un socle."""
    from ..models import GenerationJob, SocleStatut  # noqa: PLC0415

    customer = getattr(getattr(job, "order", None), "customer", None)
    if customer is None:
        return None
    projet = _projet(job)
    if not projet:
        return None
    candidats = (
        GenerationJob.objects.filter(
            order__customer=customer,
            status=_STATUT_HERITABLE,
            socle__statut=SocleStatut.VALIDE,
        )
        .exclude(pk=job.pk)
        .select_related("socle", "order")
        .order_by("-completed_at")
    )
    return next((c for c in candidats if _projet(c) == projet), None)


def _bloc(precedent: Any) -> str:
    """Le bloc de prompt : d'où viennent ces chiffres, et lesquels."""
    # `contenu`, et non `donnees` : c'est le nom du JSONField de `SocleDonnees`.
    # Lire le mauvais attribut rendait un bloc vide SANS rien dire — un
    # héritage qui n'hérite de rien est pire qu'un héritage absent (règle 1).
    socle = getattr(precedent, "socle", None)
    lignes = _lignes(getattr(socle, "contenu", None) or {})
    if not lignes:
        return ""
    quand = getattr(precedent, "completed_at", None)
    date = quand.date().isoformat() if quand else "date inconnue"
    return (
        "CHIFFRES DÉJÀ POSÉS POUR CE CLIENT — livrable « "
        f"{precedent.deliverable_type} » terminé le {date}.\n"
        "Ce client a déjà reçu un document qui porte ces chiffres. Il les a "
        "lus.\n"
        + "\n".join(lignes)
        + "\n\nReprends-les À L'IDENTIQUE : même valeur, même unité, même "
        "année, même périmètre. Deux documents du même dossier qui annoncent "
        "deux totaux pour le même marché se discréditent l'un l'autre, et le "
        "client ne sait plus lequel appliquer.\n"
        "Si une donnée plus récente ou mieux sourcée impose de s'écarter de "
        "l'une d'elles, garde la tienne et NOMME l'écart dans sa source : "
        "« révisé depuis l'étude précédente, qui retenait X ». Ce qui est "
        "interdit, c'est de changer un chiffre en silence."
    )


def _lignes(donnees: Any) -> list[str]:
    """Une ligne par chiffre : ce qu'il mesure, sa valeur, son périmètre."""
    brutes = donnees.get("donnees") if isinstance(donnees, dict) else None
    if not isinstance(brutes, list):
        return []
    lignes: list[str] = []
    for donnee in brutes[:MAX_CHIFFRES_HERITES]:
        if not isinstance(donnee, dict):
            continue
        libelle = str(donnee.get("libelle") or donnee.get("id") or "").strip()
        if not libelle:
            continue
        valeur = donnee.get("valeur")
        unite = str(donnee.get("unite") or "").strip()
        annee = donnee.get("annee")
        perimetre = donnee.get("perimetre")
        morceaux = [f"- {libelle} : {valeur} {unite}".rstrip()]
        if annee:
            morceaux.append(f"en {annee}")
        if perimetre:
            morceaux.append(f"({perimetre})")
        lignes.append(" ".join(morceaux))
    return lignes

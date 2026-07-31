"""Production d'un chapitre : contrat structuré, adossé au socle verrouillé.

Un chapitre reçoit (§6.1) : le socle complet, les résumés des chapitres déjà
rédigés, son prompt propre, et le contexte client. Il rend un objet structuré,
pas du texte libre.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from ..models import ChapterGeneration, GenerationJob
from ..socle.schema import Socle
from .configuration import TypeDocument, type_document
from .fichiers_prompts import rendre_prompt
from .schema import ChapitrePayload, valider_chapitre

_log = logging.getLogger(__name__)

OUTIL_NOM = "rendre_chapitre"
OUTIL_DESCRIPTION = (
    "Enregistre le chapitre rédigé : ses sections, les identifiants de données "
    "du socle qu'il exploite, les graphiques qu'il demande, et son résumé."
)

_SYSTEME = (
    # Sans nommer la plateforme : le livrable est remis en marque blanche, et
    # un modèle amorcé avec ce nom finit par l'écrire dans le texte.
    "Tu rédiges un chapitre d'étude professionnelle : "
    "ton mentor, données chiffrées et sourcées, concret et exploitable.\n"
    "\n"
    "RÈGLE ABSOLUE — tu n'as pas le droit de produire un chiffre de marché. "
    "Le SOCLE joint contient tous les chiffres de référence de l'étude, déjà "
    "établis et verrouillés. Tu les EXPLOITES ; tu ne les recalcules pas, tu "
    "ne les arrondis pas, tu n'en inventes pas d'autres. Chaque identifiant de "
    "donnée que tu mobilises doit être listé dans `donnees_utilisees`.\n"
    "\n"
    "Les graphiques que tu demandes ne portent AUCUNE valeur : seulement des "
    "identifiants du socle. Le rendu résout les valeurs lui-même, ce qui rend "
    "impossible qu'un graphique contredise le texte qui l'entoure.\n"
    "\n"
    f"Tu réponds exclusivement par un appel de l'outil `{OUTIL_NOM}`."
)


class ChapitreInvalideError(RuntimeError):
    """Le chapitre produit ne respecte pas son contrat."""

    def __init__(self, motifs: list[str]) -> None:
        self.motifs = motifs
        super().__init__(" ; ".join(motifs))


def schema_outil() -> dict[str, Any]:
    return ChapitrePayload.model_json_schema()


def _bloc_socle(socle: Socle) -> str:
    """Socle sérialisé, lisible et exhaustif.

    Format tabulaire plutôt que JSON brut : à contenu égal il consomme moins
    de jetons et se lit mieux, or ce bloc est réinjecté à CHAQUE chapitre.
    """
    lignes = [
        f"- `{d.id}` = {d.valeur} {d.unite} ({d.annee}, {d.perimetre}, {d.fiabilite})"
        + (f" — source : {d.source}" if d.source else "")
        + (f" — dérivé de {', '.join(d.derivee_de)}" if d.derivee_de else "")
        for d in socle.donnees
    ]
    entete = (
        f"SOCLE VERROUILLÉ — {socle.secteur}, {socle.zone.pays}"
        + (f" / {socle.zone.region}" if socle.zone.region else "")
        + (f" / {socle.zone.ville}" if socle.zone.ville else "")
        + f" (arrêté au {socle.date_socle.isoformat()})"
    )
    return entete + "\n" + "\n".join(lignes)


def _bloc_resumes(job: GenerationJob, numero: int) -> str:
    precedents = (
        job.chapters.filter(chapter_number__lt=numero)
        .exclude(operational_summary="")
        .order_by("chapter_number")
    )
    lignes = [
        f"Chapitre {c.chapter_number} — {c.chapter_title} :\n{c.operational_summary}"
        for c in precedents
    ]
    if not lignes:
        return "CHAPITRES PRÉCÉDENTS : aucun, tu ouvres l'étude."
    return "CHAPITRES PRÉCÉDENTS (résumés) :\n\n" + "\n\n".join(lignes)


def _bloc_forme() -> str:
    """Consigne de forme, identique pour tous les chapitres et tous les livrables.

    Elle vit ici et pas dans les 72 fichiers de prompt : la répéter soixante-douze
    fois garantirait qu'elle finisse par diverger d'un fichier à l'autre
    (règle 5). Elle traduit une mesure, pas un goût — le document de référence
    validé par la cliente porte 52 % de ses mots dans des tableaux et une
    médiane de douze mots par paragraphe. Un chapitre qui ne rend que de la
    prose produit le mur de texte qu'elle a explicitement refusé.
    """
    return (
        "FORME ATTENDUE — contrainte mesurée sur le livrable de référence, "
        "pas une préférence de style :\n"
        "- L'information vit dans les TABLEAUX. Chaque section porte un "
        "`tableau` de 3 à 5 colonnes ; ce sont ses lignes qui portent les "
        "chiffres, les critères et les comparaisons.\n"
        "- Le champ `contenu` d'une section est une AMORCE, pas un "
        "développement : deux à trois phrases qui annoncent ce que le tableau "
        "montre. Au-delà, il sera tronqué au rendu.\n"
        "- Un encadré au moins par chapitre, avec un verdict actionnable "
        "(opportunité, limite, décision) — jamais un résumé de ce qui précède."
    )


def _bloc_visuels(socle: Socle) -> str:
    """Catalogue des visuels et consigne sectorielle.

    Le choix d'un type de graphique dépend du SECTEUR, jamais du numéro de
    chapitre : une saisonnalité mensuelle n'a pas de sens dans une étude sur le
    conseil, une pyramide des âges n'en a pas dans la logistique. Le profil est
    déduit du secteur porté par le socle.
    """
    from ..rendu_word import secteurs  # noqa: PLC0415
    from ..rendu_word.graphiques import resume_catalogue  # noqa: PLC0415

    profil = secteurs.profil_du_secteur(socle.secteur)
    return (
        "VISUELS — un graphique ne porte AUCUNE valeur : il porte des "
        "identifiants du socle, résolus au rendu. Un identifiant absent du "
        "socle fait abandonner la figure entière.\n\n"
        "Types disponibles :\n" + resume_catalogue() + "\n\n"
        + secteurs.consigne_visuelle(profil)
    )


def _valeurs_interpolation(
    chapter: ChapterGeneration, variables: Mapping[str, object]
) -> dict[str, object]:
    from ..blueprints import get_blueprint  # noqa: PLC0415

    blueprint = get_blueprint(chapter.job.deliverable_type, chapter.chapter_number)
    return {
        "secteur": variables.get("SECTEUR", ""),
        "pays": variables.get("PAYS", ""),
        "zone": variables.get("ZONE", ""),
        "projet": variables.get("PROJET", ""),
        "titre_chapitre": chapter.chapter_title,
        "numero_chapitre": chapter.chapter_number,
        "cible_mots": (blueprint.max_words if blueprint else 0) or "non bornée",
    }


def construire_prompt_chapitre(
    chapter: ChapterGeneration,
    *,
    socle: Socle,
    variables: Mapping[str, object],
    document: TypeDocument,
    motifs_precedents: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Prompt utilisateur du chapitre. Retourne (prompt, variables manquantes)."""
    instruction, manquantes = rendre_prompt(
        document.code,
        chapter.chapter_number,
        _valeurs_interpolation(chapter, variables),
    )

    blocs = [
        _bloc_socle(socle),
        f"BRIEF_CLIENT :\n{json.dumps(dict(variables), ensure_ascii=False, sort_keys=True)}",
        _bloc_resumes(chapter.job, chapter.chapter_number),
        f"CHAPITRE À RÉDIGER : {chapter.chapter_number} — {chapter.chapter_title}",
        f"INSTRUCTION DU CHAPITRE :\n{instruction}",
        _bloc_forme(),
        _bloc_visuels(socle),
        (
            f"RÉSUMÉ : termine par un résumé de {document.resume_mots_min} à "
            f"{document.resume_mots_max} mots. Il sera relu par tous les "
            "chapitres suivants : fais-y figurer les chiffres et les "
            "conclusions qu'ils devront reprendre à l'identique."
        ),
    ]

    if motifs_precedents:
        motifs = "\n".join(f"- {motif}" for motif in motifs_precedents)
        blocs.append(
            "TENTATIVE PRÉCÉDENTE REFUSÉE. Corrige EXACTEMENT ces points :\n" + motifs
        )

    return "\n\n".join(blocs), manquantes


def payload_vers_markdown(payload: ChapitrePayload) -> str:
    """Rendu markdown du chapitre, consommable par la chaîne de rendu actuelle.

    Sert de pont : le lot 3 remplacera ce rendu par un gabarit Word, mais tant
    qu'il n'est pas là, le document doit rester assemblable.
    """
    from .schema import (  # noqa: PLC0415 — importés seulement pour le pont
        BlocEncadre,
        BlocGraphique,
        BlocGrilleKpi,
        BlocParagraphe,
        BlocSousTitre,
        BlocTableau,
    )

    morceaux: list[str] = []
    # Dans l'ORDRE des blocs : le markdown est un pont, il ne doit pas
    # réorganiser ce que le chapitre a composé.
    for bloc in payload.blocs:
        if isinstance(bloc, BlocSousTitre):
            morceaux.append(f"## {bloc.numero} {bloc.intitule}")
        elif isinstance(bloc, BlocParagraphe):
            morceaux.append(bloc.texte.strip())
        elif isinstance(bloc, BlocTableau):
            # Sans cette reprise, le pont vers l'ancienne chaîne perdrait
            # silencieusement la moitié de l'information du chapitre.
            entetes = " | ".join(bloc.tableau.entetes)
            separateur = " | ".join(["---"] * len(bloc.tableau.entetes))
            lignes = "\n".join(
                "| " + " | ".join(ligne) + " |" for ligne in bloc.tableau.lignes
            )
            morceaux.append(f"| {entetes} |\n| {separateur} |\n{lignes}")
            if bloc.tableau.source:
                morceaux.append(f"*{bloc.tableau.source}*")
        elif isinstance(bloc, BlocEncadre):
            lignes = "\n".join(f"- {ligne}" for ligne in bloc.encadre.lignes)
            morceaux.append(f"**{bloc.encadre.intitule}**\n\n{lignes}")
        elif isinstance(bloc, BlocGrilleKpi):
            morceaux.append("\n".join(
                f"**{c.valeur}** — {c.libelle}" + (f" *({c.source})*" if c.source else "")
                for c in bloc.cellules
            ))
        elif isinstance(bloc, BlocGraphique):
            # Marqueur explicite : le rendu résoudra les identifiants en valeurs.
            morceaux.append(
                f"<!-- graphique:{bloc.graphique.type} "
                f"titre=\"{bloc.graphique.titre}\" "
                f"donnees=\"{','.join(bloc.graphique.donnees_ids)}\" -->"
            )
    return "\n\n".join(morceaux)


def generer_chapitre(
    *,
    client: Any,
    chapter: ChapterGeneration,
    socle: Socle,
    variables: Mapping[str, object],
    max_tokens: int = 8192,
) -> tuple[ChapitrePayload, dict[str, int]]:
    """Produit UN chapitre. Lève `ChapitreInvalideError` si le contrat est rompu.

    Ne fait qu'une tentative : la reprise est portée par la tâche Celery, qui
    seule sait temporiser et compter les échecs (§6.2).
    """
    job = chapter.job
    document = type_document(str(job.deliverable_type))

    motifs_precedents = _motifs_stockes(chapter)
    prompt, manquantes = construire_prompt_chapitre(
        chapter,
        socle=socle,
        variables=variables,
        document=document,
        motifs_precedents=motifs_precedents,
    )
    if manquantes:
        _log.warning(
            "Chapitre %s : variables de prompt non résolues %s",
            chapter.chapter_number, manquantes,
        )

    resultat = client.complete_structured(
        system=_SYSTEME,
        prompt=prompt,
        outil_nom=OUTIL_NOM,
        outil_description=OUTIL_DESCRIPTION,
        schema=schema_outil(),
        max_tokens=max_tokens,
    )
    consommation = {
        "input_tokens": resultat.input_tokens,
        "output_tokens": resultat.output_tokens,
    }

    try:
        payload = ChapitrePayload.model_validate(dict(resultat.payload))
    except ValidationError as erreur:
        motifs = [
            f"{'.'.join(str(p) for p in item['loc'])} : {item['msg']}"
            for item in erreur.errors()[:12]
        ]
        raise ChapitreInvalideError(motifs) from erreur

    motifs = valider_chapitre(
        payload,
        numero_attendu=chapter.chapter_number,
        identifiants_socle=frozenset(socle.identifiants),
        resume_mots_min=document.resume_mots_min,
        resume_mots_max=document.resume_mots_max,
    )
    if motifs:
        raise ChapitreInvalideError(motifs)

    return payload, consommation


_PREFIXE_MOTIFS = "[contrat] "


def _motifs_stockes(chapter: ChapterGeneration) -> list[str] | None:
    """Motifs du refus précédent, relus depuis `error_message`.

    On ne redemande pas « fais mieux » : on redonne la liste exacte de ce qui
    a été refusé, comme pour le socle.
    """
    if not chapter.error_message.startswith(_PREFIXE_MOTIFS):
        return None
    reste = chapter.error_message[len(_PREFIXE_MOTIFS):]
    return [motif for motif in reste.split(" ; ") if motif] or None


def formater_motifs(motifs: list[str]) -> str:
    return (_PREFIXE_MOTIFS + " ; ".join(motifs))[:2000]

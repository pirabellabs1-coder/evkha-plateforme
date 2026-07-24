"""Controles inter-blocs — methode Evangeline (manuel juillet 2026).

Le manuel EVKHA definit 11 CHECKs qui structurent la generation d'une EM :

- CHECK INITIAL (§2, p. 3) : validation de la fiche projet avant chapitre 1.
- CHECK 1 a 9 (§6, pp. 8-16) : un controle apres chaque bloc de chapitres.
- CHECK FINAL (§6, p. 17) : dix items a valider avant la livraison.

Chaque CHECK reprend telles quelles les questions redigees par Evangeline.
Un appel Claude Sonnet joue le role du relecteur humain : lit la fiche projet
enrichie et les chapitres du bloc, verifie chaque question, rend un verdict
`pass` / `fix` + une note corrective + les points a enrichir dans la fiche.

Ce module remplace la constellation de checks regex de `checks_post_rendu.py`
et `checks_evangeline.py`. Le manuel dit explicitement : « entre 2/3 chapitres
je lui demande de bien checker que tout soit coherent, les chiffres bons, le
texte fluide puis je lui dis de continuer ». La regex ne sait pas juger la
fluidite ; le relecteur Sonnet, si.

Les gardes-catastrophe (chapitre avorte, troncature, URL bidon, marqueur
pipeline dans le rendu, taux en plage) restent des checks deterministes,
appliques a cote — voir Vague 3 pour le nettoyage des anciens modules.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from integrations.claude import ClaudeClient, get_claude_client  # type: ignore[attr-defined]

from .coherence import (
    client_facts_as_context,
    enrichir_fiche_apres_check,
    generated_facts_as_context,
)
from .models import ChapterGeneration, GenerationJob


# ── Definition des blocs (source : manuel §6 p. 7) ──────────────────────────


@dataclass(frozen=True)
class BlocDefinition:
    """Un bloc regroupe 1 a 3 chapitres controles par un meme CHECK."""

    identifiant: str  # "INITIAL", "A", "B", ..., "J", "FINAL"
    check_numero: str  # "INITIAL", "1", ..., "9", "FINAL"
    intitule: str  # texte affiche dans la note
    chapitres: tuple[int, ...]  # numeros de chapitres (vide pour INITIAL)
    focus: str  # objectif du controle (une phrase)
    questions: tuple[str, ...]  # questions verbatim du manuel


# Ordre canonique du manuel. Le CHECK INITIAL n'a pas de chapitre : il
# valide la fiche projet avant la generation du chapitre 1.
BLOCS: tuple[BlocDefinition, ...] = (
    BlocDefinition(
        identifiant="INITIAL",
        check_numero="INITIAL",
        intitule="Validation de la fiche projet",
        chapitres=(),
        focus="Avant d'autoriser le chapitre 1, verifier que la fiche projet "
              "est complete et fidele a la demande du client.",
        questions=(
            "La demande du client a-t-elle ete entierement lue et comprise ?",
            "Le marche etudie correspond-il a l'activite reelle, sans confusion "
            "de secteur ?",
            "Les zones geographiques sont-elles exactes et adaptees au projet ?",
            "Toutes les questions du client sont-elles inscrites dans la fiche ?",
            "Des contradictions ou informations critiques manquantes doivent-elles "
            "etre clarifiees ?",
            "Le niveau de langage et le type de lecteur final sont-ils bien "
            "compris ?",
        ),
    ),
    BlocDefinition(
        identifiant="A",
        check_numero="1",
        intitule="Fondations du marche",
        chapitres=(1, 2),
        focus="Verrouiller le marche, les zones et les chiffres-fondations "
              "avant tout le reste.",
        questions=(
            "Les chapitres 1 et 2 traitent-ils exactement le bon marche, le bon "
            "secteur et les bonnes zones geographiques ?",
            "Toutes les demandes importantes du client sont-elles toujours prises "
            "en compte ?",
            "Les tailles de marche, taux de croissance, projections et "
            "TAM/SAM/SOM sont-ils sources, dates, definis et coherents ?",
            "Les graphiques reprennent-ils exactement les memes valeurs que le "
            "texte ?",
            "Les estimations sont-elles expliquees sans presenter une deduction "
            "comme une donnee officielle ?",
        ),
    ),
    BlocDefinition(
        identifiant="B",
        check_numero="2",
        intitule="Direction de l'etude",
        chapitres=(3,),
        focus="Verifier que la segmentation prolonge naturellement les fondations "
              "et repond a la demande.",
        questions=(
            "Les segments retenus correspondent-ils reellement a la zone, a "
            "l'offre et au modele du client ?",
            "Les cibles prioritaires repondent-elles a la demande formulee dans "
            "le questionnaire ?",
            "La redaction reste-t-elle humaine, fluide, accessible et sans "
            "jargon ?",
            "Le chapitre 3 prolonge-t-il naturellement les chapitres 1 et 2, sans "
            "repetition ni contradiction ?",
            "Les questions normales d'un porteur de projet dans ce domaine "
            "commencent-elles a recevoir une reponse ?",
        ),
    ),
    BlocDefinition(
        identifiant="C",
        check_numero="3",
        intitule="Distinction present / avenir",
        chapitres=(4, 5),
        focus="S'assurer que les avantages/contraintes du present sont bien "
              "distingues des defis/opportunites du futur.",
        questions=(
            "Les avantages et contraintes actuels sont-ils bien separes des "
            "defis et opportunites futurs ?",
            "Chaque point est-il specifique au secteur et relie au projet, plutot "
            "que generique ?",
            "Les chapitres 4 et 5 evitent-ils les repetitions et les listes "
            "artificielles ?",
            "Un tableau, une matrice ou un encadre utile a-t-il ete prevu dans "
            "ce bloc ?",
        ),
    ),
    BlocDefinition(
        identifiant="D",
        check_numero="4",
        intitule="Reglementation securisee",
        chapitres=(6,),
        focus="Verifier que la reglementation citee est officielle, actuelle "
              "et applicable, sans se substituer a un professionnel du droit.",
        questions=(
            "Les textes et organismes cites sont-ils officiels, actuels et "
            "applicables au bon pays ?",
            "Les obligations sont-elles distinguees des recommandations ?",
            "Les couts, delais, demarches et risques de non-conformite sont-ils "
            "expliques lorsqu'ils sont connus ?",
            "Aucune affirmation ne remplace-t-elle l'avis d'un professionnel du "
            "droit, de la fiscalite ou de la conformite ?",
        ),
    ),
    BlocDefinition(
        identifiant="E",
        check_numero="5",
        intitule="Horizons 2026-2030",
        chapitres=(7, 8),
        focus="Controler que le court terme reste observable et que le long "
              "terme reste des scenarios argumentes, sans casser les fondations.",
        questions=(
            "Les tendances 2026-2027 sont-elles recentes, observables et utiles "
            "pour le lancement ?",
            "Les perspectives a 2030 sont-elles presentees comme des projections "
            "ou des scenarios, jamais comme des certitudes ?",
            "Les taux et montants utilises restent-ils identiques aux "
            "chiffres-fondations ?",
            "Les implications concretes pour le projet sont-elles clairement "
            "formulees ?",
            "Un visuel utile permet-il de comprendre l'evolution dans le temps ?",
        ),
    ),
    BlocDefinition(
        identifiant="F",
        check_numero="6",
        intitule="Chiffres, clients et usages",
        chapitres=(9, 10, 11),
        focus="Verifier que les 12 chiffres cles, la clientele et les personas "
              "sont fondes sur les registres validees et coherents entre eux.",
        questions=(
            "Les 12 chiffres cles proviennent-ils tous des fondations ou de "
            "chapitres deja valides ?",
            "Le chapitre 10 repond-il clairement a : qui achete, quoi, a quelle "
            "frequence, a quel prix, pourquoi et par quel canal ?",
            "Les deux personas decoulent-ils des segments et comportements "
            "analyses, sans details inventes ni cliches ?",
            "Les prix, frequences, budgets et comportements ne se "
            "contredisent-ils pas d'un chapitre a l'autre ?",
            "La presentation reste-t-elle redigee et agreable, sans succession "
            "de listes ?",
        ),
    ),
    BlocDefinition(
        identifiant="G",
        check_numero="7",
        intitule="Risques et viabilite",
        chapitres=(12, 13, 14),
        focus="S'assurer que la cartographie des risques reflete l'analyse et "
              "que la viabilite s'appuie sur les elements deja verrouilles.",
        questions=(
            "La cartographie reprend-elle exactement les risques analyses au "
            "chapitre 12 ?",
            "Les probabilites, impacts et priorites sont-ils coherents entre le "
            "texte et la matrice ?",
            "L'avis de viabilite repose-t-il sur le SOM, les ressources, la "
            "cible, la reglementation et le cycle de vente ?",
            "L'analyse reste-t-elle neutre, y compris si le potentiel est "
            "fragile ou conditionnel ?",
            "Aucun previsionnel financier ou resultat de rentabilite n'a-t-il "
            "ete invente ?",
        ),
    ),
    BlocDefinition(
        identifiant="H",
        check_numero="8",
        intitule="Visuels, offre et geographie",
        chapitres=(15, 16, 17),
        focus="Verifier que les visuels reprennent les chiffres valides et que "
              "l'analyse geographique se justifie par des criteres objectifs.",
        questions=(
            "Tous les graphiques et tableaux reprennent-ils les chiffres valides, "
            "avec titre, unite, periode et source courte ?",
            "L'analyse offre/demande reste-t-elle une etude de marche, sans "
            "devenir une etude detaillee de la concurrence ?",
            "Les zones prioritaires sont-elles justifiees par des criteres "
            "objectifs et coherentes avec la demande du client ?",
            "Les chapitres 15 a 17 apportent-ils une lecture nouvelle sans "
            "repeter les memes paragraphes ?",
            "Le document contient-il un rythme visuel agreable, sans surcharge "
            "ni elements decoratifs inutiles ?",
        ),
    ),
    BlocDefinition(
        identifiant="I",
        check_numero="9",
        intitule="Analyse transformee en decision",
        chapitres=(18, 19, 20),
        focus="Verifier que la SWOT, les recommandations et la conclusion "
              "racontent une seule histoire coherente et repondent au client.",
        questions=(
            "Chaque element de la SWOT provient-il d'un chapitre precedent ?",
            "Les recommandations sont-elles concretes, hierarchisees, realistes "
            "et directement reliees aux constats ?",
            "La conclusion repond-elle aux demandes du client sans ajouter de "
            "chiffre, risque ou conseil nouveau ?",
            "L'ensemble raconte-t-il une seule histoire coherente, du marche "
            "mondial jusqu'aux decisions du porteur ?",
            "Toutes les questions explicites et implicites du porteur de projet "
            "ont-elles une reponse claire ?",
        ),
    ),
    BlocDefinition(
        identifiant="J",
        check_numero="FINAL",
        intitule="Controle final avant livraison",
        chapitres=(21,),
        focus="Verifier que tout le dossier est pret a etre remis au client.",
        questions=(
            "Toutes les sources utilisees figurent une seule fois dans le "
            "chapitre 21, avec organisme, titre, annee et lien verifie ?",
            "Les estimations importantes expliquent sobrement leur methode, "
            "leurs hypotheses et leurs limites ?",
            "Les 21 chapitres sont presents dans le bon ordre et forment une "
            "lecture continue ?",
            "Tous les chiffres, dates, unites, devises, definitions et graphiques "
            "correspondent a la fiche enrichie ?",
            "Toutes les demandes du client ont une reponse identifiable dans "
            "l'etude ?",
            "Aucun jargon inutile, phrase d'IA, repetition excessive, troncature, "
            "placeholder ou lien casse ne subsiste ?",
            "Le logo, les couleurs EVKHA, les titres, les tableaux, les encadres "
            "et les visuels sont-ils homogenes ?",
            "Un ancrage visuel utile apparait-il tous les deux ou trois "
            "chapitres, sans surcharger le document ?",
            "Le DOCX et le PDF presenteront-ils le meme contenu, sans page vide "
            "ni tableau coupe ?",
            "Le document final ne depasse-t-il pas 80 pages ?",
        ),
    ),
)


BLOCS_PAR_IDENTIFIANT: dict[str, BlocDefinition] = {b.identifiant: b for b in BLOCS}


# ── Resultat d'un CHECK ─────────────────────────────────────────────────────


@dataclass
class PointAEnrichir:
    """Un fait identifie par le CHECK a persister dans la fiche projet."""

    cle: str
    valeur: str


@dataclass
class CheckResult:
    """Retour d'un appel a `check_bloc`."""

    bloc_identifiant: str
    verdict: str  # "pass" | "fix"
    note_corrective: str = ""
    points_a_enrichir: list[PointAEnrichir] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    raw_response: str = ""

    @property
    def est_ok(self) -> bool:
        return self.verdict == "pass"


# ── Prompt system + user ────────────────────────────────────────────────────


_SYSTEM_PROMPT_CHECK = (
    "Tu es le RELECTEUR EVKHA. Tu appliques a la lettre la methode "
    "d'Evangeline (manuel juillet 2026, section 6). "
    "Ton role : verifier, apres un bloc de chapitres, que chaque question du "
    "CHECK est satisfaite. Tu ne redige pas les chapitres, tu les evalues. "
    "Tu es exigeant mais juste : un verdict 'fix' declenche une "
    "regeneration couteuse ; ne le rends que sur des defauts reels et "
    "actionnables. Un verdict 'pass' laisse passer le bloc. "
    "Reponds toujours en JSON strict, aucun texte hors du bloc JSON."
)


_MAX_CONTENU_PAR_CHAPITRE = 6000  # caracteres — on tronque pour tenir dans le contexte


def _extrait_chapitre(chapitre: ChapterGeneration) -> str:
    """Renvoie un extrait compact du chapitre, adapte au relecteur."""
    corps = (chapitre.content or "").strip()
    if len(corps) > _MAX_CONTENU_PAR_CHAPITRE:
        # On garde le debut + la fin : le milieu se coupe souvent proprement,
        # les incoherences apparaissent aux extremites (chiffre nouveau ou
        # troncature de fin de chapitre).
        moitie = _MAX_CONTENU_PAR_CHAPITRE // 2
        corps = corps[:moitie] + "\n\n[... contenu tronque pour le check ...]\n\n" + corps[-moitie:]
    return corps


def _formater_chapitres(chapitres: list[ChapterGeneration]) -> str:
    if not chapitres:
        return "(aucun chapitre a controler pour ce bloc — CHECK sur la fiche projet uniquement)"
    parts: list[str] = []
    for chap in chapitres:
        parts.append(
            f"### Chapitre {chap.chapter_number} — {chap.chapter_title}\n\n"
            f"{_extrait_chapitre(chap)}"
        )
    return "\n\n---\n\n".join(parts)


def _formater_questions(questions: tuple[str, ...]) -> str:
    return "\n".join(f"{i}. {q}" for i, q in enumerate(questions, start=1))


def _construire_prompt_check(
    bloc: BlocDefinition,
    job: GenerationJob,
    chapitres: list[ChapterGeneration],
) -> str:
    fiche_client = client_facts_as_context(job)
    fiche_generee = generated_facts_as_context(job)
    corps_chapitres = _formater_chapitres(chapitres)
    questions = _formater_questions(bloc.questions)

    return (
        f"## CONTEXTE\n"
        f"Livrable : etude de marche EVKHA (manuel Evangeline, juillet 2026).\n"
        f"Bloc en cours : {bloc.identifiant} — {bloc.intitule}\n"
        f"Objectif du CHECK {bloc.check_numero} : {bloc.focus}\n\n"
        f"## FICHE PROJET — donnees client verrouillees\n"
        f"{fiche_client}\n\n"
        f"## FICHE PROJET — reperes enrichis (chapitres precedents)\n"
        f"{fiche_generee}\n\n"
        f"## CHAPITRES DU BLOC\n{corps_chapitres}\n\n"
        f"## QUESTIONS DU CHECK {bloc.check_numero} (verbatim manuel EVKHA)\n"
        f"{questions}\n\n"
        f"## FORMAT DE REPONSE (JSON strict, aucun texte hors du bloc)\n"
        "```json\n"
        "{\n"
        '  "verdict": "pass" ou "fix",\n'
        '  "reponses_questions": [\n'
        '    {"numero": 1, "reponse": "oui/non/partiel", "commentaire": "en une phrase"},\n'
        "    ... (une entree par question)\n"
        "  ],\n"
        '  "note_corrective": "Instructions concretes a passer au redacteur '
        "pour corriger les chapitres du bloc. Vide si verdict = pass. "
        "Formuler comme une consigne actionnable (ex : 'Reformuler la phrase X '\n"
        "  'pour trancher entre 8 % et 10 %, retenir 9 % et l'utiliser partout').\","
        '\n  "points_a_enrichir_fiche": [\n'
        '    {"cle": "definition_marche", "valeur": "marche des kits solaires B2C '
        "particuliers, France metropolitaine, 2026\"},\n"
        '    ... (0 a 10 points, cles courtes en snake_case, valeurs concises).\n'
        "  ]\n"
        "}\n"
        "```\n"
        "Regles :\n"
        "- 'verdict' = 'fix' UNIQUEMENT si au moins une question a une reponse "
        "'non' ou 'partiel' avec un vrai defaut. Sinon 'pass'.\n"
        "- 'note_corrective' doit citer les chapitres concernes (« Ch. 2 : ... »).\n"
        "- 'points_a_enrichir_fiche' contient les faits stables identifies "
        "dans les chapitres qui devront etre reutilises tels quels par les "
        "chapitres suivants (chiffres-fondations, definitions, segments prioritaires...). "
        "N'inclus PAS les faits deja presents dans la fiche client au-dessus."
    )


# ── Parsing de la reponse JSON ──────────────────────────────────────────────


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL)


def _extraire_json(brut: str) -> dict:
    """Extrait le premier bloc JSON de la reponse Sonnet.

    Sonnet respecte generalement le format demande, mais peut envelopper la
    reponse dans un fence ```json ... ```. On accepte les deux. Toute
    exception ici retourne un dict vide, ce qui provoquera un verdict 'fix'
    conservateur — mieux vaut regenerer un bloc qu'ignorer une reponse
    malformee.
    """
    if not brut:
        return {}
    match = _JSON_FENCE_RE.search(brut)
    payload = match.group(1) if match else brut
    payload = payload.strip()
    try:
        return json.loads(payload)
    except (json.JSONDecodeError, ValueError):
        # Retry : cherche la premiere accolade et la derniere.
        debut = payload.find("{")
        fin = payload.rfind("}")
        if debut >= 0 and fin > debut:
            try:
                return json.loads(payload[debut : fin + 1])
            except (json.JSONDecodeError, ValueError):
                return {}
        return {}


def _construire_result(bloc: BlocDefinition, raw: str, client_result) -> CheckResult:
    payload = _extraire_json(raw)

    verdict = str(payload.get("verdict", "fix")).strip().lower()
    if verdict not in {"pass", "fix"}:
        # Reponse hors format : on prend le parti conservateur (regenerer).
        verdict = "fix"

    note = str(payload.get("note_corrective", "")).strip()
    if verdict == "fix" and not note:
        note = (
            "Le relecteur a signale un defaut sans note explicite. Reprends "
            "l'ensemble du bloc en verifiant chaque question du CHECK "
            f"{bloc.check_numero} du manuel."
        )

    points: list[PointAEnrichir] = []
    for entree in payload.get("points_a_enrichir_fiche", []) or []:
        if not isinstance(entree, dict):
            continue
        cle = str(entree.get("cle", "")).strip()
        valeur = str(entree.get("valeur", "")).strip()
        if cle and valeur:
            points.append(PointAEnrichir(cle=cle, valeur=valeur))

    return CheckResult(
        bloc_identifiant=bloc.identifiant,
        verdict=verdict,
        note_corrective=note,
        points_a_enrichir=points,
        input_tokens=getattr(client_result, "input_tokens", 0),
        output_tokens=getattr(client_result, "output_tokens", 0),
        model=getattr(client_result, "model", ""),
        raw_response=raw,
    )


# ── Point d'entree ──────────────────────────────────────────────────────────


# Sonnet suffit pour le role de relecteur : la tache est de comparer un texte
# a une liste de questions, pas de produire un chapitre. Sonnet cote moins et
# repond aussi bien qu'Opus sur ce type de tache. Reste modifiable via un
# override futur si necessaire (parametre `model=`).
_MODELE_CHECK = "claude-sonnet"

# Cap de tokens pour la reponse. Le format JSON impose une reponse compacte ;
# 2000 tokens couvrent 10 questions + note corrective + ~10 points d'enrichissement.
_MAX_TOKENS_CHECK = 2000


def check_bloc(
    job: GenerationJob,
    bloc: BlocDefinition,
    chapitres: list[ChapterGeneration],
    *,
    client: ClaudeClient | None = None,
    persister_enrichissements: bool = True,
) -> CheckResult:
    """Execute le CHECK d'un bloc et enrichit la fiche projet si `pass`.

    En cas de `fix`, la fiche N'EST PAS enrichie (les chapitres seront
    regeneres) : les points identifies sont conserves dans le resultat pour
    inspection, mais non persistes. La regeneration relance un nouveau CHECK
    apres coup ; si celui-ci passe, la fiche est enrichie a ce moment-la.
    """
    client = client or get_claude_client()
    prompt = _construire_prompt_check(bloc, job, chapitres)

    resultat_api = client.complete(
        system=_SYSTEM_PROMPT_CHECK,
        prompt=prompt,
        max_tokens=_MAX_TOKENS_CHECK,
        model=_MODELE_CHECK,
    )

    result = _construire_result(bloc, resultat_api.content, resultat_api)

    if result.est_ok and persister_enrichissements and result.points_a_enrichir:
        enrichir_fiche_apres_check(
            job=job,
            bloc_identifiant=bloc.identifiant,
            points=[(p.cle, p.valeur) for p in result.points_a_enrichir],
        )

    return result


def bloc_pour_chapitre(chapitre_numero: int) -> BlocDefinition | None:
    """Retourne le bloc qui contient ce chapitre, s'il en existe un."""
    for bloc in BLOCS:
        if chapitre_numero in bloc.chapitres:
            return bloc
    return None


__all__ = [
    "BLOCS",
    "BLOCS_PAR_IDENTIFIANT",
    "BlocDefinition",
    "CheckResult",
    "PointAEnrichir",
    "bloc_pour_chapitre",
    "check_bloc",
]

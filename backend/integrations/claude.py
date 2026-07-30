from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from django.conf import settings

# Alias EVKHA (EVKHA_CLAUDE_MODEL) -> identifiant API Anthropic reel.
# L'identifiant exact peut etre surcharge via EVKHA_ANTHROPIC_MODEL_ID sans
# toucher au code (les references produit evoluent souvent).
_ANTHROPIC_MODEL_IDS: dict[str, str] = {
    "claude-sonnet": "claude-sonnet-4-6",
    "claude-opus": "claude-opus-4-8",
}
# 8192 tokens ≈ 6144 mots par section. Hausse de 5000 → 8192 justifiee par :
# 1. Section la plus dense (ec.03.a 3800 mots ≈ 5067 tokens) passe en 1 seul
#    appel sans aucune continuation, eliminant les artefacts de reprise.
# 2. Tout le pipeline tourne sur claude-sonnet-4-6 (decision 25/07/2026) :
#    Haiku retiree de tous les blueprints pour homogeneite qualitative.
# 3. Le Cost Engine throttle dynamiquement max_tokens si le budget se resserre :
#    pire cas EM (30 appels, budget 2.3 EUR) → throttle a ~5111 tokens des
#    le 1er appel, ce qui reste superieur a l'ancienne limite de 5000.
# 4. _MAX_CONTINUATIONS sert desormais de filet de securite pour les rarissimes
#    cas hors-normes (contenu anormalement long), non plus de cas standard.
_DEFAULT_MAX_TOKENS = 8192

# Anthropic Messages API : message.stop_reason vaut "max_tokens" quand la
# reponse est coupee par la limite de sortie (cf. doc API Anthropic, champ
# stop_reason). Sans verification de ce champ, un contenu tronque (chapitre,
# liste de concurrents...) est livre tel quel sans que rien ne le detecte.
# Correctif : quand stop_reason == "max_tokens", on relance un appel en
# ajoutant le contenu deja genere comme tour "assistant" (prefill) : l'API
# poursuit alors la reponse exactement la ou elle s'est arretee, sans la
# reecrire depuis le debut. Plafond de securite : _MAX_CONTINUATIONS appels
# supplementaires max, pour borner le cout meme en cas de contenu anormalement
# long (le Cost Engine tient compte de ce plafond, cf. generation/cost.py).
_MAX_CONTINUATIONS = 2

# Marqueur de coupure de cache dans le system prompt. `build_system_prompt`
# l'insere entre la partie STABLE (role + charte + consigne de livrable,
# identique pour tous les jobs du meme type) et la partie PROPRE AU JOB
# (consigne geographique + plan Phase 0). `_cacheable_system` le remplace par
# deux blocs `cache_control` distincts.
#
# Pourquoi deux breakpoints alors que l'API en autorise quatre : avec un seul
# bloc, le moindre changement de pays ou de brief invalidait la totalite du
# system prompt, charte comprise. La charte ne change jamais — elle merite son
# propre prefixe, reutilisable d'un job a l'autre.
SYSTEM_CACHE_BREAK = "\n\n<<<EVKHA_CACHE_BREAK>>>\n\n"

# Tarification du cache Anthropic, en multiples du prix d'un token d'input
# ordinaire (doc « Prompt caching », juillet 2026) :
#   - ecriture TTL 1 h : 200 % ;
#   - ecriture TTL 5 min : 125 % ;
#   - lecture (quel que soit le TTL) : 10 %.
_COUT_ECRITURE_CACHE_1H = 2.00
_COUT_ECRITURE_CACHE_5MIN = 1.25
_COUT_LECTURE_CACHE = 0.10

# ── Outil advisor (beta, doc « Outil advisor » mars 2026) ────────────────────
# Un modele EXECUTEUR consulte en cours de generation un modele CONSEILLER qui
# lit toute la transcription et rend un plan / une correction de trajectoire.
# Ici les deux sont le MEME modele (claude-sonnet-4-6) : le gain n'est pas la
# montee en gamme mais une seconde lecture independante de tout le bloc avant
# le verdict — exactement ce qui manquait aux CHECKs (erreurs de calcul et
# TAM/SAM/SOM incoherents releves par Evangeline sur le run 010e3bf2).
#
# La doc impose : advisor >= executeur en capacite, et advisor >= Sonnet 4.6.
# Les modeles de capacite EGALE peuvent se conseiller mutuellement, ce qui rend
# la paire sonnet-4-6 -> sonnet-4-6 valide. Deux exceptions dans le tableau de
# compatibilite : claude-haiku-4-5 (jamais advisor) et claude-sonnet-5 (dont la
# liste d'advisors exclut sonnet-5). Toute paire invalide = 400.
_ADVISOR_BETA = "advisor-tool-2026-03-01"
_ADVISOR_TOOL_TYPE = "advisor_20260301"
_MODELES_AUTO_ADVISOR = frozenset(
    {
        "claude-sonnet-4-6",
        "claude-opus-4-6",
        "claude-opus-4-7",
        "claude-opus-4-8",
        "claude-opus-5",
        "claude-fable-5",
        "claude-mythos-5",
    }
)
# Plafond de sortie de l'advisor (reflexion + texte) par appel. Minimum API
# 1024 ; 2048 est le point de depart recommande par la doc : sortie moyenne
# ~630-840 tokens, troncature ~0 %. A 1024 la doc mesure ~10 % d'appels
# tronques — un conseil coupe au milieu d'un raisonnement de coherence est
# pire qu'un conseil un peu plus cher.
_ADVISOR_MAX_TOKENS_DEFAUT = 2048
_MIN_ADVISOR_MAX_TOKENS = 1024
# Un seul appel par requete : le CHECK est un verdict unique, pas une boucle
# agentique. Plafond par REQUETE (doc `max_uses`), donc il borne aussi le
# second appel de secours de `check_bloc`.
_ADVISOR_MAX_USES = 1

# ── Outil d'execution de code (doc « Outil d'execution de code ») ────────────
# Python 3.11 + bash dans un conteneur isole, sans acces reseau. Reserve aux
# chapitres qui le declarent dans leur blueprint (aujourd'hui le seul chapitre 2
# EM, cf. `blueprints.py`), parce qu'il porte le calcul TAM/SAM/SOM.
#
# Version retenue : `code_execution_20250825`, la plus ancienne des trois
# versions en disponibilite generale. Les deux plus recentes n'ajoutent que la persistance
# de l'etat REPL et l'appel programmatique d'outils — deux capacites dont nous
# n'avons pas l'usage (un seul calcul, aucun outil maison a orchestrer) et que
# nous ne voulons pas ouvrir. Celle-ci est aussi la seule prise en charge par
# TOUS les modeles du tableau de compatibilite, donc elle survit a un chapitre
# bascule sur un autre alias.
#
# `type` et `name` sont les deux seuls champs, et ils sont FIXES : la doc dit
# « les deux champs sont fixes [...] `name` doit etre `code_execution` ». Pas de
# `max_uses` sur cet outil, contrairement a l'advisor.
_CODE_EXECUTION_TOOL_TYPE = "code_execution_20250825"
_CODE_EXECUTION_TOOL_NAME = "code_execution"


@dataclass(frozen=True)
class ClaudeResult:
    """Resultat normalise d'un appel de generation (independant du SDK).

    `input_tokens` porte l'input FACTURABLE en equivalent-token plein : les
    tokens caches y sont convertis a leur tarif reel (200 % en ecriture 1 h,
    10 % en lecture). C'est le seul nombre qui a un sens pour le Cost Engine,
    qui multiplie ce champ par le prix d'un token d'input.

    Contexte du correctif (juillet 2026) : `usage.input_tokens` de l'API
    EXCLUT les tokens caches. On ne comptait donc ni les ecritures ni les
    lectures de cache — sur un job EM, ~5 000 tokens de system prompt par
    appel disparaissaient du calcul. Le montant en euros restait faible, mais
    le Cost Engine calibrait son throttle de `max_tokens` sur un chiffre faux.

    Les deux compteurs bruts sont conserves a part pour l'observabilite : ils
    disent si le cache TOUCHE (lecture elevee = bon) ou s'il se re-ecrit a
    chaque appel (ecriture repetee = coupure de cache quelque part).
    """

    content: str
    input_tokens: int
    output_tokens: int
    model: str
    stop_reason: str = "end_turn"
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    # Outil advisor : nombre de consultations reellement effectuees et tokens
    # produits par le conseiller. Observabilite uniquement — leur cout est deja
    # inclus dans `input_tokens` / `output_tokens` (advisor = meme modele que
    # l'executeur, donc meme tarif). Un `advisor_calls` a 0 sur un CHECK cense
    # consulter signifie que l'executeur a juge la consultation inutile.
    advisor_calls: int = 0
    advisor_output_tokens: int = 0
    # Outil d'execution de code : nombre d'invocations serveur reellement
    # facturees en temps de conteneur (`usage.server_tool_use.
    # code_execution_requests`). Observabilite SEULE — ce compteur n'entre pas
    # dans le Cost Engine, parce que la facturation de l'outil se fait au temps
    # d'execution (1 550 h/mois offertes) et non au token. Un 0 sur le
    # chapitre 2 signifie que le modele a prefere calculer de tete : c'est
    # precisement le signal qu'on veut voir pour juger la mesure.
    code_execution_requests: int = 0


def _input_facturable(usage: object) -> tuple[int, int, int]:
    """Extrait (input equivalent facturable, ecritures cache, lectures cache).

    Tolerant aux versions du SDK : chaque champ est lu defensivement. Un SDK
    qui n'expose pas encore le detail par TTL retombe sur le total
    `cache_creation_input_tokens`, facture au tarif 1 h — le notre.
    """
    frais = int(getattr(usage, "input_tokens", 0) or 0)
    ecritures = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
    lectures = int(getattr(usage, "cache_read_input_tokens", 0) or 0)

    detail = getattr(usage, "cache_creation", None)
    ecritures_1h = int(getattr(detail, "ephemeral_1h_input_tokens", 0) or 0) if detail else 0
    ecritures_5min = int(getattr(detail, "ephemeral_5m_input_tokens", 0) or 0) if detail else 0
    if ecritures_1h or ecritures_5min:
        cout_ecriture = (
            ecritures_1h * _COUT_ECRITURE_CACHE_1H
            + ecritures_5min * _COUT_ECRITURE_CACHE_5MIN
        )
        ecritures = ecritures_1h + ecritures_5min
    else:
        cout_ecriture = ecritures * _COUT_ECRITURE_CACHE_1H

    equivalent = frais + cout_ecriture + lectures * _COUT_LECTURE_CACHE
    return int(round(equivalent)), ecritures, lectures


class _VueUsage:
    """Acces uniforme (attribut ou cle) a un objet usage ou a une iteration.

    `usage.iterations[]` est expose tantot comme objet type par le SDK, tantot
    comme dict brut selon la version. Un attribut absent rend None, ce que
    `_input_facturable` traite deja comme 0.
    """

    def __init__(self, source: object) -> None:
        self._source = source

    def __getattr__(self, nom: str) -> object:
        source = self._source
        if isinstance(source, dict):
            return source.get(nom)
        return getattr(source, nom, None)


@dataclass(frozen=True)
class _Totaux:
    input_facturable: int
    output: int
    ecritures_cache: int
    lectures_cache: int
    advisor_calls: int = 0
    advisor_output: int = 0


def _usage_totaux(usage: object) -> _Totaux:
    """Totaux facturables d'une reponse, advisor inclus.

    Sans outil advisor, `usage` suffit. Avec, la doc « Utilisation et
    facturation » est formelle : « Les champs `usage` de niveau superieur ne
    refletent que les tokens de l'executeur. Les tokens de l'advisor ne sont
    pas integres dans les totaux de niveau superieur. » Un CHECK conseille
    coute donc une sous-inference entiere que `usage.input_tokens` ne montre
    PAS — meme classe de defaut que les tokens caches invisibles (tache #11).

    On somme donc `usage.iterations[]`, la ventilation par iteration que la doc
    designe explicitement pour « construire une logique de suivi des couts ».
    Deux consequences assumees :
      - l'input des iterations executeur SUIVANTES est compte, alors que le
        champ de niveau superieur ne retient que la premiere. C'est bien du
        token facture : apres un conseil, l'executeur relit tout son contexte ;
      - les iterations `advisor_message` sont comptees au meme tarif que
        l'executeur. Valide UNIQUEMENT parce que `_advisor_tool` impose
        advisor == executeur. Un advisor d'une autre famille casserait ce
        calcul (et le tarif du Cost Engine avec lui).
    """
    iterations = getattr(usage, "iterations", None) or []
    if not iterations:
        facturable, ecritures, lectures = _input_facturable(usage)
        return _Totaux(
            input_facturable=facturable,
            output=int(getattr(usage, "output_tokens", 0) or 0),
            ecritures_cache=ecritures,
            lectures_cache=lectures,
        )

    facturable = output = ecritures = lectures = 0
    advisor_calls = advisor_output = 0
    for iteration in iterations:
        vue = _VueUsage(iteration)
        part_input, part_ecritures, part_lectures = _input_facturable(vue)
        facturable += part_input
        ecritures += part_ecritures
        lectures += part_lectures
        sortie = int(getattr(vue, "output_tokens", 0) or 0)
        output += sortie
        if str(getattr(vue, "type", "") or "") == "advisor_message":
            advisor_calls += 1
            advisor_output += sortie

    return _Totaux(
        input_facturable=facturable,
        output=output,
        ecritures_cache=ecritures,
        lectures_cache=lectures,
        advisor_calls=advisor_calls,
        advisor_output=advisor_output,
    )


def _advisor_tool(model_id: str) -> dict[str, object] | None:
    """Definition de l'outil advisor pour cet executeur, ou None si impossible.

    L'advisor est le MEME modele que l'executeur : c'est la contrainte projet
    (tout reste sur Sonnet 4.6) et c'est aussi ce qui garde le Cost Engine
    exact, puisqu'un seul tarif s'applique. La paire n'est emise que si le
    modele figure dans `_MODELES_AUTO_ADVISOR` — sinon l'API repondrait 400
    (cas reels : claude-haiku-4-5, jamais advisor ; claude-sonnet-5, dont la
    liste d'advisors exclut sonnet-5).

    `caching` reste desactive (defaut) : la doc ne le recommande qu'a partir de
    trois consultations dans une meme conversation, or on en autorise une.
    """
    if not bool(getattr(settings, "EVKHA_ADVISOR_ENABLED", False)):
        return None
    if model_id not in _MODELES_AUTO_ADVISOR:
        return None

    plafond = int(
        getattr(settings, "EVKHA_ADVISOR_MAX_TOKENS", _ADVISOR_MAX_TOKENS_DEFAUT)
        or _ADVISOR_MAX_TOKENS_DEFAUT
    )
    return {
        "type": _ADVISOR_TOOL_TYPE,
        "name": "advisor",
        "model": model_id,
        "max_uses": _ADVISOR_MAX_USES,
        "max_tokens": max(_MIN_ADVISOR_MAX_TOKENS, plafond),
    }


def _code_execution_tool() -> dict[str, object] | None:
    """Definition de l'outil d'execution de code, ou None si desactive.

    Aucune contrainte de modele a verifier ici, contrairement a `_advisor_tool` :
    la version retenue est en disponibilite generale et le tableau de
    compatibilite de la doc la donne pour TOUS les modeles. Pas d'en-tete beta
    non plus — c'est ce qui permet de la combiner avec l'advisor sans arbitrer
    entre deux endpoints.
    """
    if not bool(getattr(settings, "EVKHA_CODE_EXECUTION_ENABLED", False)):
        return None
    return {"type": _CODE_EXECUTION_TOOL_TYPE, "name": _CODE_EXECUTION_TOOL_NAME}


def _code_execution_requests(usage: object) -> int:
    """Invocations de l'outil d'execution de code declarees par l'API."""
    server = getattr(usage, "server_tool_use", None)
    if server is None:
        return 0
    vue = _VueUsage(server)
    return int(getattr(vue, "code_execution_requests", 0) or 0)


# Minimum impose par l'API Anthropic pour `thinking.budget_tokens`.
_MIN_THINKING_BUDGET = 1024


def _thinking_budget() -> int:
    """Budget de reflexion (extended thinking) applique a TOUS les appels.

    Uniforme par construction, et c'est volontaire : la doc « Prompt caching »
    precise que basculer le thinking invalide le cache du system prompt et des
    messages. Activer la reflexion chapitre par chapitre ferait donc re-payer
    une ecriture de cache a 200 % a chaque bascule — plus cher que le gain
    espere sur le chapitre concerne.

    0 (ou moins que le minimum API de 1024) = desactive.
    """
    budget = int(getattr(settings, "EVKHA_THINKING_BUDGET_TOKENS", 0) or 0)
    return budget if budget >= _MIN_THINKING_BUDGET else 0


@dataclass(frozen=True)
class StructuredResult:
    """Resultat d'un appel a sortie contrainte par schema (lot 1 — socle).

    `payload` est deja un dictionnaire : aucune analyse de texte n'intervient
    entre le modele et l'appelant. C'est l'inverse de `ClaudeResult`, dont le
    `content` doit etre relu par des expressions regulieres.
    """

    payload: dict[str, object]
    input_tokens: int
    output_tokens: int
    model: str
    stop_reason: str = "end_turn"


@runtime_checkable
class StructuredClaudeClient(Protocol):
    """Contrat des clients capables de rendre une sortie typee.

    Protocole SEPARE de `ClaudeClient` a dessein : l'ajouter au contrat
    existant casserait tout objet double des tests qui n'implemente que
    `complete()` (le protocole est `runtime_checkable`).
    """

    def complete_structured(
        self,
        *,
        system: str,
        prompt: str,
        outil_nom: str,
        outil_description: str,
        schema: dict[str, object],
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        model: str | None = None,
    ) -> StructuredResult: ...


@runtime_checkable
class ClaudeClient(Protocol):
    """Contrat minimal du moteur de generation textuelle (Cle d'or: cout maitrise)."""

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        model: str | None = None,
        advisor: bool = False,
        code_execution: bool = False,
    ) -> ClaudeResult: ...


def _resolve_model_alias() -> str:
    return str(getattr(settings, "EVKHA_CLAUDE_MODEL", "claude-sonnet"))


def _resolve_anthropic_model_id(alias: str) -> str:
    override = str(getattr(settings, "EVKHA_ANTHROPIC_MODEL_ID", "") or "")
    if override:
        return override
    return _ANTHROPIC_MODEL_IDS.get(alias, _ANTHROPIC_MODEL_IDS["claude-sonnet"])


class AnthropicClaudeClient:
    """Client reel. Le SDK et la cle ne sont charges qu'a l'usage (jamais en CI)."""

    def __init__(self, *, api_key: str | None = None, model_alias: str | None = None) -> None:
        self._api_key = api_key
        self._model_alias = model_alias or _resolve_model_alias()

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        model: str | None = None,
        advisor: bool = False,
        code_execution: bool = False,
    ) -> ClaudeResult:
        import os

        import anthropic  # import paresseux : dependance optionnelle hors tests

        api_key = self._api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            msg = "ANTHROPIC_API_KEY manquante pour AnthropicClaudeClient."
            raise RuntimeError(msg)

        # Priorite : surcharge par appel (chapitre leger → haiku) → defaut instance
        effective_alias = model or self._model_alias
        model_id = _resolve_anthropic_model_id(effective_alias)
        client = anthropic.Anthropic(api_key=api_key)
        system_param = _cacheable_system(system)

        content_parts: list[str] = []
        total_input = 0
        total_output = 0
        total_cache_write = 0
        total_cache_read = 0
        total_advisor_calls = 0
        total_advisor_output = 0
        total_code_exec = 0
        stop_reason = "end_turn"
        # `content` porte des blocs bruts des qu'un tour `pause_turn` est
        # renvoye tel quel, d'ou le type large.
        messages: list[dict[str, object]] = [{"role": "user", "content": prompt}]

        # Prompt caching Anthropic : le system prompt est stable sur les ~30
        # appels d'un job (charte + role + pays + plan Phase 0). Marque en
        # cache_control ephemeral TTL 1h par `_cacheable_system`, il est paye
        # plein une fois (ecriture 200 %) puis 10 % a chaque appel suivant.
        #
        # Extended thinking : le budget est le MEME pour tous les appels du job
        # (cf. `_thinking_budget`). Le basculer en cours de job invaliderait le
        # cache du system prompt ET des messages, et re-paierait une ecriture a
        # 200 % a chaque bascule. `max_tokens` doit englober les tokens de
        # reflexion : on l'augmente du budget pour que la place laissee au
        # contenu redactionnel reste exactement celle demandee par l'appelant.
        budget_reflexion = _thinking_budget()
        extra: dict[str, object] = {}
        if budget_reflexion:
            extra["thinking"] = {"type": "enabled", "budget_tokens": budget_reflexion}
            max_tokens = max_tokens + budget_reflexion

        # Outil advisor : reserve aux appels qui le demandent explicitement
        # (aujourd'hui les CHECKs de bloc, cf. generation/checks_blocs.py). Il
        # passe par l'endpoint beta ; le reste du pipeline garde l'appel stable.
        # `max_tokens` de niveau superieur ne borne QUE l'executeur — le plafond
        # du conseiller est porte par la definition de l'outil.
        outil_advisor = _advisor_tool(model_id) if advisor else None
        # Outil d'execution de code : reserve aux chapitres qui portent un
        # calcul emboite (aujourd'hui le seul chapitre 2 EM). En disponibilite
        # generale, donc AUCUN en-tete beta a ajouter — il se combine avec
        # l'advisor sans changer d'endpoint.
        outil_code = _code_execution_tool() if code_execution else None
        outils = [outil for outil in (outil_advisor, outil_code) if outil is not None]
        if outils:
            extra["tools"] = outils
        if outil_advisor is not None:
            extra["betas"] = [_ADVISOR_BETA]

        for _ in range(_MAX_CONTINUATIONS + 1):
            # L'endpoint beta n'est requis que par l'advisor. L'execution de
            # code seule reste sur l'endpoint stable.
            creer = client.beta.messages.create if outil_advisor else client.messages.create
            message = creer(
                model=model_id,
                max_tokens=max_tokens,
                system=system_param,  # type: ignore[arg-type]
                messages=messages,  # type: ignore[arg-type]
                **extra,  # type: ignore[arg-type]
            )
            # Seuls les blocs `text` sont du livrable : avec l'advisor, le
            # contenu porte aussi `server_tool_use` et `advisor_tool_result`,
            # et avec l'execution de code `bash_code_execution_tool_result` et
            # `text_editor_code_execution_tool_result` — donc du code source et
            # des stdout, qui ne doivent jamais atterrir dans un chapitre.
            chunk = "".join(
                str(getattr(block, "text", ""))
                for block in message.content
                if getattr(block, "type", "") == "text"
            )
            content_parts.append(chunk)
            totaux = _usage_totaux(message.usage)
            total_input += totaux.input_facturable
            total_cache_write += totaux.ecritures_cache
            total_cache_read += totaux.lectures_cache
            total_output += totaux.output
            total_advisor_calls += totaux.advisor_calls
            total_advisor_output += totaux.advisor_output
            total_code_exec += _code_execution_requests(message.usage)
            stop_reason = str(message.stop_reason)

            # `pause_turn` : l'API a mis en pause un tour de longue duree (cas
            # documente pour les outils serveur, dont l'execution de code). La
            # doc impose de « renvoyer la reponse telle quelle » pour que Claude
            # reprenne son tour — donc les blocs BRUTS, sans le filtrage texte
            # ci-dessus : amputer un `server_tool_use` de son resultat rendrait
            # l'historique invalide. Sans cette branche, un tour mis en pause
            # sortait de la boucle avec un chapitre tronque, et le defaut
            # n'apparaissait qu'a la validation, sous une autre etiquette.
            #
            # Les iterations sont un plafond PARTAGE avec les continuations de
            # troncature : au plus `_MAX_CONTINUATIONS + 1` appels facturables
            # par `complete()`, quelle qu'en soit la cause (Cle d'or : cout
            # maitrise). Une pause consomme donc un tour de reprise.
            if stop_reason == "pause_turn":
                messages = [*messages, {"role": "assistant", "content": message.content}]
                continue

            if stop_reason != "max_tokens":
                break

            # Continuation multi-tour (pas de prefill : claude-sonnet-4-6 et
            # les modeles recents rejettent les conversations terminant sur un
            # tour assistant). On conserve le tour assistant tronque puis on
            # ajoute un tour user qui demande de poursuivre : Claude reprend
            # exactement apres le dernier mot sans repeter le debut.
            # `max_uses` est un plafond par REQUETE : sans cette coupure, chaque
            # continuation r'ouvrirait un droit de consultation, jusqu'a trois
            # conseils payes pour un seul CHECK. Une continuation ne cherche
            # qu'a finir un texte coupe — il n'y a plus rien a conseiller.
            # Retrait conforme a la doc (« Controle des couts ») : on enleve
            # l'outil ET tout bloc advisor de l'historique, ce que la
            # reconstruction ci-dessous fait par nature (texte seul).
            if outil_advisor is not None:
                outil_advisor = None
                extra.pop("betas", None)
                # L'outil d'execution de code, lui, RESTE s'il etait present.
                # Le retirer modifierait le niveau `tools`, qui precede `system`
                # dans la hierarchie de cache : la continuation re-paierait une
                # ecriture a 200 % du system prompt entier au lieu de le relire
                # a 10 %. Le garder ne coute rien — une continuation ne fait que
                # finir un texte coupe, et si elle recalcule, le temps de
                # conteneur reste dans les heures offertes.
                if outil_code is None:
                    extra.pop("tools", None)
                else:
                    extra["tools"] = [outil_code]

            messages = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": "".join(content_parts)},
                {
                    "role": "user",
                    "content": (
                        "Continue ta réponse depuis le point exact où tu t'es arrêté. "
                        "Ne répète rien de ce qui a déjà été écrit. "
                        "Reprends immédiatement après le dernier mot ou caractère."
                    ),
                },
            ]

        return ClaudeResult(
            content="".join(content_parts),
            input_tokens=total_input,
            output_tokens=total_output,
            model=effective_alias,  # modele reel utilise (peut etre surcharge)
            stop_reason=stop_reason,
            cache_creation_input_tokens=total_cache_write,
            cache_read_input_tokens=total_cache_read,
            advisor_calls=total_advisor_calls,
            advisor_output_tokens=total_advisor_output,
            code_execution_requests=total_code_exec,
        )


    def complete_structured(
        self,
        *,
        system: str,
        prompt: str,
        outil_nom: str,
        outil_description: str,
        schema: dict[str, object],
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        model: str | None = None,
    ) -> StructuredResult:
        """Reponse contrainte a un schema JSON, via l'outil dedie (lot 1).

        Utilise `tool_choice` force : le modele NE PEUT PAS repondre autre chose
        qu'un appel d'outil conforme au schema. C'est la difference de nature
        avec `complete()`, qui rend du texte libre a analyser apres coup.

        La reflexion etendue est volontairement DESACTIVEE ici : elle impose
        `tool_choice: auto` cote API, ce qui reintroduirait la possibilite d'une
        reponse en texte libre — exactement ce que cette methode elimine.
        """
        import os

        import anthropic  # import paresseux : dependance optionnelle hors tests

        api_key = self._api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            msg = "ANTHROPIC_API_KEY manquante pour AnthropicClaudeClient."
            raise RuntimeError(msg)

        effective_alias = model or self._model_alias
        model_id = _resolve_anthropic_model_id(effective_alias)
        client = anthropic.Anthropic(api_key=api_key)

        # `type: ignore` : les surcharges du SDK typent `tools` et `system` avec
        # des TypedDict fermes. Nos dictionnaires sont construits dynamiquement
        # (le schema depend du livrable), ce que mypy ne peut pas rapprocher des
        # surcharges. Meme traitement que `complete()` ci-dessus.
        message = client.messages.create(  # type: ignore[call-overload]
            model=model_id,
            max_tokens=max_tokens,
            system=_cacheable_system(system),
            messages=[{"role": "user", "content": prompt}],
            tools=[
                {
                    "name": outil_nom,
                    "description": outil_description,
                    "input_schema": schema,
                }
            ],
            tool_choice={"type": "tool", "name": outil_nom},
        )

        charge: dict[str, object] = {}
        for bloc in message.content:
            if getattr(bloc, "type", "") == "tool_use" and getattr(bloc, "name", "") == outil_nom:
                brut = getattr(bloc, "input", {})
                charge = dict(brut) if isinstance(brut, dict) else {}
                break

        usage = getattr(message, "usage", None)
        return StructuredResult(
            payload=charge,
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            model=effective_alias,
            stop_reason=str(getattr(message, "stop_reason", "") or ""),
        )


def _cacheable_system(system: str) -> str | list[dict[str, object]]:
    """Decoupe le system prompt en blocs caches, au plus deux breakpoints.

    TTL 1h au lieu du defaut 5 min : un job BP ou EM produit 20 chapitres
    sequentiels, la generation depasse regulierement 5 minutes. Passe ce
    seuil, chaque chapitre rejouait un cache-write plein (125 %) au lieu
    d'un cache-read (10 %). L'ecriture 1h coute 200 % (soit +75 pts) mais
    elle n'est payee QU'UNE FOIS par job — les 19 chapitres suivants
    restent a 10 %. Point mort : 3 chapitres.

    Deux blocs quand `SYSTEM_CACHE_BREAK` est present :
      1. prefixe STABLE (role + charte + consigne de livrable) — partage par
         tous les jobs du meme type, donc mutualise d'une commande a l'autre
         dans la fenetre d'1 h ;
      2. queue PROPRE AU JOB (pays + plan Phase 0) — reutilisee par les ~30
         appels du job.
    La doc « Prompt caching » precise que le cache est un prefixe strict : le
    bloc 1 reste valide meme quand le bloc 2 change entierement. Avec un seul
    breakpoint, changer de pays invalidait aussi la charte.
    """
    if not system:
        return ""
    cache = {"type": "ephemeral", "ttl": "1h"}
    stable, _, par_job = system.partition(SYSTEM_CACHE_BREAK)
    blocs: list[dict[str, object]] = [
        {"type": "text", "text": stable, "cache_control": cache}
    ]
    if par_job.strip():
        blocs.append({"type": "text", "text": par_job, "cache_control": cache})
    return blocs


class StubClaudeClient:
    """Client deterministe pour dev/CI : aucune dependance reseau, cout simule.

    Le contenu reprend le PROMPT_KEY et les premieres lignes du prompt afin que
    les tests d'integration verifient le cablage Context -> Generation -> Rendu.
    """

    def __init__(self, *, model_alias: str | None = None) -> None:
        self._model_alias = model_alias or _resolve_model_alias()

    def complete(
        self,
        *,
        system: str,
        prompt: str,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        model: str | None = None,
        advisor: bool = False,
        code_execution: bool = False,
    ) -> ClaudeResult:
        # `advisor` et `code_execution` sont acceptes et ignores : le stub ne
        # simule ni sous-inference ni conteneur. Ils doivent rester conformes au
        # protocole, sinon un CHECK conseille ou le chapitre 2 leverait
        # TypeError en CI.
        # CHECK inter-bloc EVKHA : quand le stub est appele comme RELECTEUR
        # (checks_blocs._SYSTEM_PROMPT_CHECK), il doit rendre un verdict JSON
        # parseable. Sans ca, l'absence de fence JSON fait defaulter check_bloc
        # a 'fix' : inoffensif pour les CHECKs A-J (incident MEDIUM) mais
        # BLOQUANT pour le CHECK INITIAL depuis qu'il est un gate. Le stub
        # represente le chemin nominal -> il rend 'pass'.
        if "RELECTEUR EVKHA" in system:
            content = (
                "```json\n"
                '{"verdict": "pass", "reponses_questions": [], '
                '"note_corrective": "", "points_a_enrichir_fiche": []}\n'
                "```"
            )
            return ClaudeResult(
                content=content,
                input_tokens=max(1, len(system) + len(prompt)) // 4,
                output_tokens=max(1, len(content)) // 4,
                model=model or self._model_alias,
            )

        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
        # Le check `chapitre_avorte` du gate planche a 30 % du max_words du
        # blueprint (jusqu'a 1 800 mots). Un stub qui rend 28 mots faisait
        # tomber les tests d'integration : on repete le paragraphe pour tenir
        # un contenu credible tout en restant purement deterministe.
        paragraphe = (
            "Cette section synthetise les donnees chiffrees et sourcees attendues "
            "pour le chapitre courant, redigee dans le ton mentor EVKHA. "
            "L'analyse mobilise le contexte projet, les indicateurs sectoriels et "
            "les leviers d'execution associes au livrable. "
        )
        # Bloc Sources credible (2 URLs verifiables minimum) pour satisfaire
        # le check transverse `sources_non_tracables` du gate. Ce bloc est
        # emis par TOUS les chapitres du stub, donc en particulier par le
        # chapitre Sources (identifie par titre au gate).
        content = (
            "Contenu genere (mode demonstration EVKHA).\n\n"
            + paragraphe * 60
            + f"\n\nEmpreinte de tracabilite: {digest}.\n\n"
            "## Sources\n"
            "- INSEE, Enquete emploi 2024 - https://www.insee.fr/fr/statistiques/1234\n"
            "- Xerfi, Etude sectorielle 2025 - https://www.xerfi.com/etude-x\n"
            "- EVKHA, methodologie interne (document client sans URL).\n"
        )
        # Estimation grossiere (~4 caracteres par token) pour alimenter le Cost Engine.
        input_tokens = max(1, len(system) + len(prompt)) // 4
        output_tokens = max(1, len(content)) // 4
        effective_alias = model or self._model_alias
        return ClaudeResult(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=effective_alias,
        )


    def complete_structured(
        self,
        *,
        system: str,
        prompt: str,
        outil_nom: str,
        outil_description: str,
        schema: dict[str, object],
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        model: str | None = None,
    ) -> StructuredResult:
        """Socle de demonstration deterministe, conforme au referentiel.

        Import paresseux de `generation.socle` : `integrations` ne depend pas
        de `generation` au niveau module (ce serait un cycle). Ici l'appel a
        lieu a l'execution, uniquement sur le chemin bouchon, et seulement
        pour l'outil du socle.
        """
        charge: dict[str, object] = {}
        if outil_nom == "produire_socle":
            from generation.socle.stub import socle_de_demonstration  # noqa: PLC0415

            charge = socle_de_demonstration(prompt)
        elif outil_nom == "rendre_chapitre":
            from generation.chapitres.stub import (  # noqa: PLC0415
                chapitre_de_demonstration,
            )

            charge = chapitre_de_demonstration(prompt)

        return StructuredResult(
            payload=charge,
            input_tokens=max(1, len(system) + len(prompt)) // 4,
            output_tokens=max(1, len(str(charge))) // 4,
            model=model or self._model_alias,
        )


def get_claude_client() -> ClaudeClient:
    """Fabrique : client reel si autorise + cle presente, sinon stub deterministe."""
    import os

    use_stub = bool(getattr(settings, "EVKHA_USE_STUB_AI", True))
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY", ""))
    if use_stub or not has_key:
        return StubClaudeClient()
    return AnthropicClaudeClient()

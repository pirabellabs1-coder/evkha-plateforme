"""Outil d'execution de code sur le chapitre 2 EM (tache #14).

Ce que ces tests protegent, et pourquoi chacun existe :

1. LA PORTEE. Un outil s'ajoute au niveau `tools`, qui PRECEDE `system` dans la
   hierarchie de cache Anthropic (« les modifications a chaque niveau invalident
   ce niveau et tous les niveaux suivants »). Un chapitre qui l'active re-ecrit
   son prefixe a 200 % au lieu de le relire a 10 %. Etendre le drapeau a un
   second chapitre par inadvertance coute donc reellement de l'argent, en
   silence.
2. LE DRAPEAU IGNORE. Le cablage n'existe que sur la branche a UN appel de
   `_generate_chapter`. Un blueprint qui declarerait a la fois `sections` et
   `code_execution` verrait son drapeau ignore sans aucune erreur.
3. LA FUITE DANS LE LIVRABLE. La reponse porte des blocs `server_tool_use` et
   `*_code_execution_tool_result` : du code source et des stdout. Ils ne doivent
   jamais atteindre un chapitre — et la consigne doit aussi interdire au modele
   de RACONTER l'execution en texte, seul canal que le filtrage ne voit pas.
4. `pause_turn`. Raison d'arret documentee pour les outils serveur, que la
   boucle de continuation ne gerait pas : elle sortait avec un chapitre tronque.
   Sa reprise exige de renvoyer la reponse TELLE QUELLE (blocs bruts).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.test import override_settings

from catalog.models import DeliverableType
from generation.blueprints import (
    BUSINESS_PLAN_CHAPTERS,
    COMPETITOR_STUDY_CHAPTERS,
    MARKET_STUDY_CHAPTERS,
    get_blueprint,
)
from generation.prompt_library import MARKET_STUDY_PROMPTS
from integrations import claude as claude_module
from integrations.claude import (
    ClaudeResult,
    StubClaudeClient,
    _code_execution_requests,
    _code_execution_tool,
)

_TOUS_LES_BLUEPRINTS = (
    *MARKET_STUDY_CHAPTERS,
    *BUSINESS_PLAN_CHAPTERS,
    *COMPETITOR_STUDY_CHAPTERS,
)


# --- 1. Portee : un seul chapitre, et c'est le 2 ---------------------------


def test_seul_le_chapitre_2_em_active_l_execution_de_code() -> None:
    actifs = [
        (blueprint.number, blueprint.prompt_key)
        for blueprint in _TOUS_LES_BLUEPRINTS
        if blueprint.code_execution
    ]

    assert actifs == [(2, "em.02.marche_national_local")], (
        "chaque chapitre supplementaire re-ecrit son prefixe de cache : "
        f"actifs = {actifs}"
    )


def test_le_blueprint_du_chapitre_2_em_porte_bien_le_drapeau() -> None:
    blueprint = get_blueprint(DeliverableType.MARKET_STUDY, 2)

    assert blueprint is not None
    assert blueprint.code_execution is True


def test_le_drapeau_est_desactive_par_defaut_sur_le_dataclass() -> None:
    # Un nouveau chapitre ne doit jamais heriter de l'outil par accident.
    autres = [b for b in _TOUS_LES_BLUEPRINTS if b.prompt_key != "em.02.marche_national_local"]

    assert autres, "garde-fou vide : la liste des blueprints n'a pas ete chargee"
    assert all(b.code_execution is False for b in autres)


# --- 2. Le drapeau ne peut pas etre ignore en silence ---------------------


def test_aucun_blueprint_ne_combine_sections_et_execution_de_code() -> None:
    # `_generate_chapter` ne passe `code_execution` que sur la branche a un
    # seul appel. Avec des sections, le drapeau serait perdu sans erreur.
    fautifs = [
        blueprint.prompt_key
        for blueprint in _TOUS_LES_BLUEPRINTS
        if blueprint.code_execution and blueprint.sections
    ]

    assert fautifs == [], f"drapeau ignore en silence sur {fautifs}"


# --- 3. Definition de l'outil --------------------------------------------


@override_settings(EVKHA_CODE_EXECUTION_ENABLED=True)
def test_la_definition_de_l_outil_est_exactement_celle_de_la_doc() -> None:
    # La doc est explicite : « les deux champs sont fixes [...] `name` doit etre
    # `code_execution` ». Tout champ en plus est un 400.
    outil = _code_execution_tool()

    assert outil == {"type": "code_execution_20250825", "name": "code_execution"}


@override_settings(EVKHA_CODE_EXECUTION_ENABLED=False)
def test_le_reglage_a_false_retire_completement_l_outil() -> None:
    assert _code_execution_tool() is None


@override_settings(EVKHA_CODE_EXECUTION_ENABLED=True)
def test_l_outil_n_exige_aucun_en_tete_beta() -> None:
    # C'est ce qui permet de le combiner avec l'advisor sans arbitrer entre
    # l'endpoint stable et l'endpoint beta. Un `betas` ici signifierait que la
    # version choisie n'est plus en disponibilite generale.
    outil = _code_execution_tool()

    assert outil is not None
    assert "betas" not in outil
    assert "max_uses" not in outil, "cet outil n'a pas de max_uses (contrairement a l'advisor)"


# --- 4. Comptage des invocations ------------------------------------------


def test_les_invocations_sont_lues_dans_server_tool_use() -> None:
    usage = SimpleNamespace(server_tool_use=SimpleNamespace(code_execution_requests=3))

    assert _code_execution_requests(usage) == 3


def test_un_usage_sans_server_tool_use_compte_zero() -> None:
    # Cas nominal des 21 autres chapitres : aucun outil, champ absent.
    assert _code_execution_requests(SimpleNamespace()) == 0
    assert _code_execution_requests(SimpleNamespace(server_tool_use=None)) == 0


def test_le_compteur_est_lisible_en_dict_comme_en_objet() -> None:
    # Le SDK expose `server_tool_use` tantot type, tantot dict brut selon la
    # version — meme tolerance que `_usage_totaux` pour les iterations.
    usage = SimpleNamespace(server_tool_use={"code_execution_requests": 2})

    assert _code_execution_requests(usage) == 2


def test_le_resultat_expose_le_compteur_et_vaut_zero_par_defaut() -> None:
    # Champ d'observabilite : il ne doit PAS entrer dans le Cost Engine, dont
    # la facturation est au token, alors que l'outil se facture au temps.
    resultat = ClaudeResult(content="x", input_tokens=1, output_tokens=1, model="m")

    assert resultat.code_execution_requests == 0


# --- 5. Contrat du client : le stub accepte le parametre ------------------


def test_le_stub_accepte_code_execution_sans_lever() -> None:
    # Sans ce parametre sur le stub, le chapitre 2 leverait TypeError en CI.
    resultat = StubClaudeClient().complete(
        system="SYSTEME", prompt="CHAPITRE 2", code_execution=True
    )

    assert resultat.content
    assert resultat.code_execution_requests == 0


def test_le_stub_reste_conforme_au_protocole_claude_client() -> None:
    assert isinstance(StubClaudeClient(), claude_module.ClaudeClient)


# --- 6. Aucune trace d'execution dans le livrable -------------------------


@pytest.mark.parametrize(
    "type_de_bloc",
    [
        "server_tool_use",
        "bash_code_execution_tool_result",
        "text_editor_code_execution_tool_result",
        "advisor_tool_result",
        "thinking",
    ],
)
def test_seuls_les_blocs_texte_sont_retenus_comme_contenu(type_de_bloc: str) -> None:
    # Reproduit le filtrage de `AnthropicClaudeClient.complete` : un bloc de
    # resultat d'outil porte du code source et des stdout.
    blocs = [
        SimpleNamespace(type=type_de_bloc, text="import pandas; print(42)"),
        SimpleNamespace(type="text", text="Le marche accessible atteint 4,2 M EUR."),
    ]

    retenu = "".join(
        str(getattr(bloc, "text", "")) for bloc in blocs if getattr(bloc, "type", "") == "text"
    )

    assert retenu == "Le marche accessible atteint 4,2 M EUR."
    assert "import pandas" not in retenu


def test_la_consigne_du_chapitre_2_interdit_de_raconter_l_execution() -> None:
    # SEULE protection contre la fuite par le texte : le filtrage des blocs ne
    # voit pas une phrase du modele qui commente sa propre procedure.
    prompt = MARKET_STUDY_PROMPTS["em.02.marche_national_local"]

    assert "ni code, ni sortie de console" in prompt
    assert "d'un script" in prompt


def test_la_consigne_reste_vraie_si_l_outil_est_desactive() -> None:
    # Le prompt est statique alors que l'outil est reglable : la consigne est
    # donc conditionnelle, sinon on demanderait au modele d'utiliser un outil
    # absent — et un modele a qui on ordonne d'executer du code sans
    # interpreteur pretend l'avoir fait.
    prompt = MARKET_STUDY_PROMPTS["em.02.marche_national_local"]

    assert "Quand un outil d'execution de code est a ta disposition" in prompt


def test_la_consigne_d_execution_ne_fuit_dans_aucun_autre_chapitre() -> None:
    for cle, prompt in MARKET_STUDY_PROMPTS.items():
        if cle == "em.02.marche_national_local":
            continue
        assert "outil d'execution de code" not in prompt, f"consigne hors sujet dans {cle}"


# --- 7. Cablage reel : outil transmis, pause_turn reprise -----------------


class _FauxUsage:
    def __init__(self, *, requetes_code: int = 0) -> None:
        self.input_tokens = 100
        self.output_tokens = 200
        if requetes_code:
            self.server_tool_use = SimpleNamespace(code_execution_requests=requetes_code)


class _FauxMessage:
    def __init__(
        self,
        blocs: list[SimpleNamespace],
        stop_reason: str,
        *,
        requetes_code: int = 0,
    ) -> None:
        self.content = blocs
        self.stop_reason = stop_reason
        self.usage = _FauxUsage(requetes_code=requetes_code)


def _texte(valeur: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=valeur)


class _FauxMessages:
    def __init__(self, reponses: list[_FauxMessage]) -> None:
        self._reponses = list(reponses)
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> _FauxMessage:
        self.calls.append(kwargs)
        return self._reponses.pop(0)


def _installer_faux_sdk(
    monkeypatch: pytest.MonkeyPatch, reponses: list[_FauxMessage]
) -> dict[str, object]:
    import sys
    import types

    holder: dict[str, object] = {}

    def _fabrique(**_: object) -> SimpleNamespace:
        if "client" not in holder:
            messages = _FauxMessages(reponses)
            holder["messages"] = messages
            holder["client"] = SimpleNamespace(messages=messages)
        return holder["client"]  # type: ignore[return-value]

    module = types.ModuleType("anthropic")
    module.Anthropic = _fabrique  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "anthropic", module)
    return holder


@override_settings(EVKHA_CODE_EXECUTION_ENABLED=True)
def test_l_outil_est_transmis_a_l_api_quand_le_chapitre_le_demande(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    holder = _installer_faux_sdk(
        monkeypatch, [_FauxMessage([_texte("SOM : 4,2 M EUR.")], "end_turn", requetes_code=1)]
    )

    resultat = claude_module.AnthropicClaudeClient(api_key="fake").complete(
        system="sys", prompt="chapitre 2", code_execution=True
    )

    appel = holder["messages"].calls[0]  # type: ignore[union-attr]
    assert appel["tools"] == [{"type": "code_execution_20250825", "name": "code_execution"}]
    # Endpoint STABLE : aucun en-tete beta n'est ajoute pour cet outil seul.
    assert "betas" not in appel
    assert resultat.code_execution_requests == 1


@override_settings(EVKHA_CODE_EXECUTION_ENABLED=True)
def test_aucun_outil_n_est_transmis_pour_les_autres_chapitres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # C'est ce qui garde intact le prefixe de cache des 21 autres chapitres.
    holder = _installer_faux_sdk(monkeypatch, [_FauxMessage([_texte("ch. 5")], "end_turn")])

    claude_module.AnthropicClaudeClient(api_key="fake").complete(system="sys", prompt="ch. 5")

    assert "tools" not in holder["messages"].calls[0]  # type: ignore[union-attr]


@override_settings(EVKHA_CODE_EXECUTION_ENABLED=True)
def test_les_blocs_d_outil_ne_sortent_pas_dans_le_contenu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocs = [
        SimpleNamespace(type="server_tool_use", name="bash_code_execution", text=""),
        SimpleNamespace(
            type="bash_code_execution_tool_result",
            text="stdout: tam=1500000000",
        ),
        _texte("Le TAM national ressort a 1,5 Md EUR."),
    ]
    _installer_faux_sdk(monkeypatch, [_FauxMessage(blocs, "end_turn", requetes_code=1)])

    resultat = claude_module.AnthropicClaudeClient(api_key="fake").complete(
        system="sys", prompt="chapitre 2", code_execution=True
    )

    assert resultat.content == "Le TAM national ressort a 1,5 Md EUR."
    assert "stdout" not in resultat.content


@override_settings(EVKHA_CODE_EXECUTION_ENABLED=True)
def test_pause_turn_est_repris_et_le_contenu_est_fusionne(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Sans la branche `pause_turn`, la boucle sortait ici avec le seul premier
    # fragment : un chapitre 2 tronque, signale plus tard comme un defaut de
    # validation sans rapport avec sa cause reelle.
    bloc_outil = SimpleNamespace(type="server_tool_use", name="bash_code_execution", text="")
    reponses = [
        _FauxMessage([bloc_outil, _texte("Le SAM filtre ")], "pause_turn", requetes_code=1),
        _FauxMessage([_texte("s'etablit a 4,2 M EUR.")], "end_turn"),
    ]
    holder = _installer_faux_sdk(monkeypatch, reponses)

    resultat = claude_module.AnthropicClaudeClient(api_key="fake").complete(
        system="sys", prompt="chapitre 2", code_execution=True
    )

    assert resultat.content == "Le SAM filtre s'etablit a 4,2 M EUR."
    assert resultat.stop_reason == "end_turn"

    calls = holder["messages"].calls  # type: ignore[union-attr]
    assert len(calls) == 2
    # La doc impose de « renvoyer la reponse telle quelle » : le tour assistant
    # rejoue les blocs BRUTS, bloc d'outil inclus. Un `server_tool_use` ampute
    # de son resultat rendrait l'historique invalide.
    messages = calls[1]["messages"]
    assert messages[0] == {"role": "user", "content": "chapitre 2"}
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] is reponses[0].content


@override_settings(EVKHA_CODE_EXECUTION_ENABLED=True)
def test_les_pauses_partagent_le_plafond_d_appels_facturables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Cle d'or « cout maitrise » : une pause en boucle ne doit pas ouvrir un
    # nombre illimite d'appels.
    reponses = [
        _FauxMessage([_texte(f"p{i} ")], "pause_turn")
        for i in range(claude_module._MAX_CONTINUATIONS + 5)
    ]
    holder = _installer_faux_sdk(monkeypatch, reponses)

    resultat = claude_module.AnthropicClaudeClient(api_key="fake").complete(
        system="sys", prompt="chapitre 2", code_execution=True
    )

    assert len(holder["messages"].calls) == claude_module._MAX_CONTINUATIONS + 1  # type: ignore[union-attr]
    assert resultat.stop_reason == "pause_turn"


@override_settings(EVKHA_CODE_EXECUTION_ENABLED=True)
def test_l_outil_survit_a_une_continuation_de_troncature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Le retirer modifierait le niveau `tools`, qui precede `system` dans la
    # hierarchie de cache : la continuation re-paierait une ecriture a 200 % du
    # system prompt entier au lieu de le relire a 10 %.
    reponses = [
        _FauxMessage([_texte("debut ")], "max_tokens"),
        _FauxMessage([_texte("fin.")], "end_turn"),
    ]
    holder = _installer_faux_sdk(monkeypatch, reponses)

    claude_module.AnthropicClaudeClient(api_key="fake").complete(
        system="sys", prompt="chapitre 2", code_execution=True
    )

    calls = holder["messages"].calls  # type: ignore[union-attr]
    assert calls[1]["tools"] == [{"type": "code_execution_20250825", "name": "code_execution"}]

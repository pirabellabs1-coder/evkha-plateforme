"""La forme des appels envoyes a Anthropic tient sur les modeles recents.

26/10/2026, premiere generation reelle apres le passage en Opus : le dossier
`8961e377` est mort a 0,43 EUR, ZERO chapitre sur vingt-deux.

    BadRequestError 400 : "thinking.type.disabled" is not supported for this
    model. Use "thinking.type.adaptive" and "output_config.effort".

Puis, en eprouvant le correctif contre l'API reelle :

    tool_choice: type "tool" and "any" are not supported for this model.

`claude-sonnet-5` acceptait les deux formes — la production tournait avec
depuis des mois. `claude-opus-5-5` refuse les deux.

## Pourquoi ces tests existent, et ce qu'ils ne prouvent pas

La repetition a blanc joue la chaine entiere sur la DOUBLURE : aucun appel ne
part chez Anthropic, et aucune forme de requete n'y est jugee. C'est la
regle 7 du depot, rencontree de l'autre cote — le vert des tests ne prouvait
rien sur ce qui part reellement.

Ces tests verrouillent la FORME que le code construit. Ils ne remplacent pas
une mesure contre l'API : celle-ci a ete faite le 26/10/2026, sur opus-5-5,
sonnet-5 et sonnet-5-5, et c'est elle qui a dicte ces valeurs.
"""
from __future__ import annotations

from integrations.claude import reflexion_minimale


def test_la_reflexion_minimale_ne_dit_jamais_disabled() -> None:
    """Le test qui echoue sur le code d'avant : il envoyait `disabled`."""
    forme = reflexion_minimale()
    assert forme["thinking"] == {"type": "adaptive"}
    assert forme["thinking"] != {"type": "disabled"}


def test_la_reflexion_minimale_porte_un_effort_bas() -> None:
    """`adaptive` sans effort laisserait le modele reflechir a sa guise.

    L'intention de l'ancien `disabled` — reflechir le moins possible — se dit
    par l'effort, qui est le seul levier restant.
    """
    assert reflexion_minimale()["output_config"] == {"effort": "low"}


def _valeurs_passees(nom_argument: str) -> list[str]:
    """Les valeurs litterales passees a `nom_argument` dans les APPELS du module.

    On lit l'arbre syntaxique, pas le texte : une docstring qui CITE la panne
    — et ce module en cite plusieurs — n'est pas un appel. Un controle qui
    confond les deux signale son propre commentaire (regle 2).
    """
    import ast
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "integrations" / "claude.py"
    arbre = ast.parse(source.read_text(encoding="utf-8"))
    valeurs: list[str] = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Call):
            continue
        for argument in noeud.keywords:
            if argument.arg == nom_argument:
                valeurs.append(ast.unparse(argument.value))
    return valeurs


def test_aucun_appel_du_depot_ne_force_le_choix_d_outil() -> None:
    """`tool_choice` force est refuse par claude-opus-5-5, avec ou sans reflexion.

    Contre-epreuve de la panne : si quelqu'un remet un choix force, ce test
    tombe avant la production.
    """
    choix = _valeurs_passees("tool_choice")
    assert choix, "le code doit toujours poser un tool_choice explicite"
    for valeur in choix:
        assert "'auto'" in valeur, valeur
        assert "'tool'" not in valeur and "'any'" not in valeur, valeur


def test_aucun_appel_du_depot_n_envoie_thinking_disabled() -> None:
    """Contre-epreuve : la forme qui a tue la generation ne doit plus exister."""
    for valeur in _valeurs_passees("thinking"):
        assert "disabled" not in valeur, valeur


def test_la_forme_minimale_est_celle_qu_un_appel_emploie() -> None:
    """La fonction et les appels ne doivent pas diverger (regle 5).

    `reflexion_minimale` ne sert a rien si un appel ecrit sa propre forme a
    cote : c'est ainsi que `disabled` avait survecu a deux endroits.
    """
    import ast
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "integrations" / "claude.py"
    arbre = ast.parse(source.read_text(encoding="utf-8"))
    appels = [
        ast.unparse(n) for n in ast.walk(arbre)
        if isinstance(n, ast.Call) and "reflexion_minimale" in ast.unparse(n.func)
    ]
    assert len(appels) >= 2, appels

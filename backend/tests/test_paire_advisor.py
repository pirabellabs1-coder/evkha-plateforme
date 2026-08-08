"""L'advisor doit être au moins aussi capable que l'exécuteur — sinon 400.

Défaut mesuré : le code mettait l'advisor au MÊME modèle que l'exécuteur, en
résumant la règle de la documentation par « les modèles de capacité égale
peuvent se conseiller mutuellement ». C'est vrai à partir d'Opus 4.7, et faux
pour Sonnet 4.6 — le seul modèle que ce projet emploie. Le tableau officiel
donne, pour un exécuteur `claude-sonnet-4-6`, les advisors valides :
opus-4-7, opus-4-8, opus-5, fable-5, mythos-5. Sonnet 4.6 n'y figure pas.

La paire émise en production était donc `sonnet-4-6` conseillé par
`sonnet-4-6` : un 400 à chaque CHECK conseillé (blocs A, F, G, I, J).

Elle n'a jamais levé, et c'est ce qui la rendait invisible : l'advisor n'est
monté que sur les CHECKs de bloc, et les CHECKs ne s'exécutent pas dans le
moteur en service. Rebrancher les CHECKs sans corriger ceci ferait échouer cinq
blocs d'un coup, sur la première vraie génération.

Ces tests échouent sur le code d'avant.
"""
from __future__ import annotations

import pytest
from django.test import override_settings

from integrations.claude import _ADVISORS_VALIDES, _advisor_tool

#: Le tableau de compatibilité de la documentation Anthropic, recopié tel quel.
#:
#: C'est la seule chose que ce fichier a le droit de recopier : le test compare
#: le dépôt à la RÉFÉRENCE. Le dériver du code testé ne prouverait rien
#: (règle 9 : un contrôle et son objet ne jugent pas sur la même évidence).
TABLEAU_OFFICIEL: dict[str, frozenset[str]] = {
    "claude-haiku-4-5": frozenset(
        {"claude-opus-5", "claude-fable-5", "claude-mythos-5",
         "claude-opus-4-8", "claude-opus-4-7"}
    ),
    "claude-sonnet-4-6": frozenset(
        {"claude-opus-5", "claude-fable-5", "claude-mythos-5",
         "claude-opus-4-8", "claude-opus-4-7"}
    ),
    "claude-sonnet-5": frozenset(
        {"claude-opus-5", "claude-fable-5", "claude-mythos-5",
         "claude-opus-4-8", "claude-opus-4-7"}
    ),
    "claude-opus-4-6": frozenset(
        {"claude-opus-5", "claude-fable-5", "claude-mythos-5",
         "claude-opus-4-8", "claude-opus-4-7"}
    ),
    "claude-opus-4-7": frozenset(
        {"claude-opus-5", "claude-fable-5", "claude-mythos-5",
         "claude-opus-4-8", "claude-opus-4-7"}
    ),
    "claude-opus-4-8": frozenset(
        {"claude-opus-5", "claude-fable-5", "claude-mythos-5", "claude-opus-4-8"}
    ),
    "claude-opus-5": frozenset(
        {"claude-opus-5", "claude-fable-5", "claude-mythos-5"}
    ),
    "claude-fable-5": frozenset({"claude-fable-5", "claude-opus-5"}),
    "claude-mythos-5": frozenset({"claude-mythos-5", "claude-opus-5"}),
}


def test_aucune_paire_emise_n_est_refusee_par_l_api() -> None:
    """Le test qui échoue sur le code d'avant, et sur la CLASSE (règle 4).

    On ne teste pas « sonnet-4-6 n'est plus son propre advisor » mais « aucune
    paire que ce code peut émettre n'est absente du tableau ». Un modèle ajouté
    demain retomberait sinon dans le même piège.
    """
    fautives: list[str] = []
    for executeur, advisors in _ADVISORS_VALIDES.items():
        officiels = TABLEAU_OFFICIEL.get(executeur)
        if officiels is None:
            fautives.append(f"{executeur} : exécuteur absent du tableau officiel")
            continue
        for advisor in advisors:
            if advisor not in officiels:
                fautives.append(
                    f"{executeur} conseillé par {advisor} : paire refusée (400). "
                    f"Advisors valides : {sorted(officiels)}"
                )
    assert not fautives, "\n".join(fautives)


@override_settings(EVKHA_ADVISOR_ENABLED=True)
def test_l_executeur_du_projet_recoit_un_advisor_valide() -> None:
    """Le cas qui tombait : le modèle réellement configuré en production."""
    outil = _advisor_tool("claude-sonnet-4-6")
    assert outil is not None, "aucun advisor pour le modèle du projet"
    assert outil["model"] in TABLEAU_OFFICIEL["claude-sonnet-4-6"]
    assert outil["model"] != "claude-sonnet-4-6", (
        "l'advisor est de nouveau l'exécuteur lui-même : la paire est un 400"
    )


@override_settings(EVKHA_ADVISOR_ENABLED=True)
def test_le_moins_cher_des_advisors_valides_est_retenu() -> None:
    """Monter en gamme sans raison double le tarif de la sous-inférence.

    Le premier de la liste est retenu ; la liste est ordonnée du moins cher au
    plus cher. Sans cet ordre, un `set` rendrait un advisor arbitraire et le
    coût d'un CHECK varierait d'une exécution à l'autre.
    """
    for executeur, advisors in _ADVISORS_VALIDES.items():
        outil = _advisor_tool(executeur)
        assert outil is not None, executeur
        assert outil["model"] == advisors[0], (
            f"{executeur} : advisor {outil['model']} au lieu du premier de la liste"
        )


@override_settings(EVKHA_ADVISOR_ENABLED=True)
def test_un_modele_sans_advisor_valide_n_en_emet_aucun() -> None:
    """Contre-épreuve : mieux vaut pas de conseil qu'un 400 en pleine génération.

    Haiku 4.5 n'est jamais advisor. Un exécuteur pour lequel on ne connaît pas
    de paire sûre ne doit pas en inventer une.
    """
    assert _advisor_tool("claude-haiku-4-5") is None
    assert _advisor_tool("un-modele-qui-n-existe-pas") is None


@override_settings(EVKHA_ADVISOR_ENABLED=False)
def test_le_drapeau_coupe_toujours_l_advisor() -> None:
    """Contre-épreuve : le correctif ne doit pas rallumer ce qui était éteint."""
    assert _advisor_tool("claude-sonnet-4-6") is None


@pytest.mark.parametrize("executeur", sorted(_ADVISORS_VALIDES))
def test_la_liste_d_advisors_n_est_jamais_vide(executeur: str) -> None:
    """Une entrée vide rendrait le `.get()` faussement rassurant.

    `_advisor_tool` renvoie None sur une liste vide comme sur une clé absente :
    l'advisor disparaîtrait en silence pour ce modèle (règle 1).
    """
    assert _ADVISORS_VALIDES[executeur], f"{executeur} : liste d'advisors vide"

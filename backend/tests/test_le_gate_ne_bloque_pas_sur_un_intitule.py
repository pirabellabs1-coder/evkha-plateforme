"""Le gate ne doit pas retenir un document pour une ligne qui n'est pas une phrase.

## Le cas réel, et son prix

Le 09/08/2026, une cliente lance une étude de marché depuis son espace. Vingt-
trois chapitres, 5,2586 EUR, document assemblé. **Le gate l'a retenu.**

Quatre motifs `sentence_cut` — « dernière phrase sans ponctuation finale ».
Trois étaient FAUX :

    ch. 3  « **CRITÈRE DE SÉLECTION BTOB »              → un intitulé
    ch. 8  « *EVKHA, à partir du socle verrouillé »     → une ligne de source
    ch. 4  « ion_cible, panier_moyen, sam, … »          → des identifiants

Aucune de ces lignes n'a de ponctuation finale, et aucune n'en réclame : ce ne
sont pas des phrases. Le document a été bloqué pour une faute qui n'existait pas.

## Pourquoi c'est la règle 2 dans sa forme la plus chère

« Un contrôle qui compare à une donnée MAL EXTRAITE est pire qu'absent. » Ici
il ne se contente pas de produire un motif faux : **il empêche la livraison**.
La cliente attend, le crédit est consommé, et l'opérateur doit forcer à la main
un document qui n'avait rien.

`_last_prose_line` écartait déjà les titres Markdown, les lignes de tableau, les
puces et les balises. Il lui manquait ces trois formes, et elles ont suffi.

## La contre-épreuve compte autant

Une VRAIE phrase coupée doit toujours être détectée. Le correctif ne doit pas
rendre le contrôle aveugle — ce serait échanger un blocage injustifié contre un
document tronqué livré au client, c'est-à-dire le défaut d'origine que
`sentence_cut` a été écrit pour attraper.
"""
from __future__ import annotations

import pytest

from generation.qa import _est_de_la_prose, _last_prose_line, detect_violations


def _motifs(contenu: str) -> list[str]:
    return [v.name for v in detect_violations(contenu, "em.03.test", 3)]


# ── Ce qui n'est PAS une phrase, et ne doit rien déclencher ──────────────────

@pytest.mark.parametrize(
    "ligne",
    [
        "**CRITÈRE DE SÉLECTION BTOB",
        "CRITÈRE DE SÉLECTION BTOB",
        "**SYNTHÈSE DU CHAPITRE",
        "*EVKHA, à partir du socle verrouillé",
        "*Source : Insee, 2025",
        "Source — Xerfi, étude petcare 2025",
        "ion_cible, panier_moyen, marche_national_croissance, sam, marche_national_taille",
    ],
)
def test_une_etiquette_n_est_pas_de_la_prose(ligne: str) -> None:
    """Les sept formes relevées sur le dossier réel `c8b4e60a`."""
    assert not _est_de_la_prose(ligne)


def test_un_chapitre_finissant_sur_un_intitule_n_est_pas_bloque() -> None:
    """Le cas exact du chapitre 3, de bout en bout."""
    contenu = (
        "## 3.1 Le marché adressable\n\n"
        "Le marché national progresse de 3,4 % par an depuis 2022, porté par "
        "la premiumisation de l'alimentation animale.\n\n"
        "**CRITÈRE DE SÉLECTION BTOB"
    )

    assert "sentence_cut" not in _motifs(contenu)


def test_un_chapitre_finissant_sur_une_source_n_est_pas_bloque() -> None:
    """Le cas exact du chapitre 8."""
    contenu = (
        "Le TAM s'établit à 6,7 Md€ pour la France en 2025, selon les "
        "fondations verrouillées de l'étude.\n\n"
        "*EVKHA, à partir du socle verrouillé"
    )

    assert "sentence_cut" not in _motifs(contenu)


def test_un_residu_d_identifiants_ne_bloque_pas_non_plus() -> None:
    """Le cas exact du chapitre 4.

    Ce résidu ne devrait pas être là — mais le confondre avec une phrase coupée
    envoie corriger un défaut de rédaction là où il y a un défaut de rendu. Un
    motif d'échec doit être trouvable dans le document par le lecteur (règle 2).
    """
    contenu = (
        "La cible prioritaire regroupe les foyers urbains détenteurs d'au "
        "moins un animal de compagnie.\n\n"
        "ion_cible, panier_moyen, marche_national_croissance, sam, marche_national_taille"
    )

    assert "sentence_cut" not in _motifs(contenu)


# ── LA CONTRE-ÉPREUVE : une vraie coupure reste détectée ─────────────────────

@pytest.mark.parametrize(
    "fin",
    [
        "La demande s'appuie sur une base de clientèle large et en croissance "
        "continue depuis",
        "Les distributeurs spécialisés captent une part significative du "
        "marché national et",
        "Cette dynamique se prolonge sur les trois prochains exercices selon "
        "les projections",
    ],
)
def test_une_vraie_phrase_coupee_est_toujours_detectee(fin: str) -> None:
    """Sans ceci, le correctif échangerait un faux blocage contre un vrai défaut.

    C'est le document tronqué livré au client — précisément ce que
    `sentence_cut` a été écrit pour attraper, après qu'Evangeline l'a signalé
    sur WAOME EM v1.
    """
    contenu = f"## 3.1 Analyse\n\nUn paragraphe d'ouverture complet.\n\n{fin}"

    assert "sentence_cut" in _motifs(contenu)


@pytest.mark.parametrize(
    "ligne",
    [
        "Le marché progresse de 3,4 % par an depuis 2022.",
        "La demande reste soutenue malgré l'inflation observée en 2025",
        "Trois segments se dégagent : premium, milieu de gamme, entrée",
        "Le CA progresse de 12 % sur l'exercice",
        "EVKHA recommande une entrée par le segment premium",
    ],
)
def test_une_vraie_phrase_reste_de_la_prose(ligne: str) -> None:
    """Contre-épreuve du détecteur d'étiquettes lui-même.

    Un sigle en capitales dans une phrase (« le CA progresse ») n'en fait pas un
    titre, et une phrase citant EVKHA n'est pas une ligne de source.
    """
    assert _est_de_la_prose(ligne)


def test_la_derniere_prose_est_bien_celle_qu_on_croit() -> None:
    """`_last_prose_line` doit REMONTER jusqu'à la phrase, pas s'arrêter avant."""
    contenu = (
        "Le marché national progresse de 3,4 % par an depuis 2022.\n"
        "**CRITÈRE DE SÉLECTION BTOB\n"
        "*Source : Insee, 2025"
    )

    assert _last_prose_line(contenu).endswith("depuis 2022.")

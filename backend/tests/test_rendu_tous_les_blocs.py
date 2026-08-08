"""Tout type de bloc produit par l'assemblage doit être rendable.

Défaut vécu : l'assemblage émettait une grille de chiffres sous la forme
`{"type": "kpi", "cellules": [{...}]}` alors que le rendu attend
`{"type": "kpi", "chiffres": [(valeur, libellé, source)]}`. La livraison
échouait sur un `KeyError: 'chiffres'`, et l'incident était le seul endroit où
ça se voyait — aucun test ne traversait ce type de bloc jusqu'au fichier.

C'est la classe du défaut qui compte, pas l'instance : un producteur qui émet
une forme que le consommateur n'accepte pas. Ce test fait passer les SIX types
par la chaîne complète, jusqu'au `.docx` écrit sur disque (règle 3 : vérifier ce
que le lecteur va lire).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from generation.chapitres.schema import ChapitrePayload

pytestmark = pytest.mark.django_db


def _socle() -> Any:
    from generation.socle.schema import Socle

    return Socle.model_validate({
        "secteur": "automobile",
        "zone": {"pays": "France", "region": "Île-de-France", "ville": "Paris"},
        "date_socle": "2026-07-30",
        "donnees": [
            {"id": "marche_mondial_taille", "libelle": "Marché mondial",
             "valeur": 381.5, "unite": "MdEUR", "annee": 2025,
             "perimetre": "monde", "source": "Essai", "fiabilite": "observee",
             "derivee_de": []},
            {"id": "marche_france_taille", "libelle": "Marché France",
             "valeur": 6.1, "unite": "MdEUR", "annee": 2025,
             "perimetre": "national", "source": "Essai", "fiabilite": "observee",
             "derivee_de": []},
        ],
        "segments_clientele": [],
        "concurrents": [],
        "tendances": [],
        "risques": [],
    })


def _chapitre_avec_tous_les_blocs() -> ChapitrePayload:
    ids = ["marche_mondial_taille", "marche_france_taille"]
    return ChapitrePayload.model_validate({
        "chapitre": 1,
        "titre": "Chapitre portant tous les types de blocs",
        "accroche": "Une accroche.",
        "blocs": [
            {"type": "titre_sous_section", "numero": "1.1", "intitule": "Périmètres"},
            {"type": "paragraphe", "texte": "Le socle cadre le périmètre étudié."},
            {"type": "tableau", "tableau": {
                "entetes": ["Niveau", "Ordre de grandeur"],
                "lignes": [["Mondial", "381,5 Md€"], ["France", "6,1 Md€"]],
                "source": "Socle",
            }},
            {"type": "graphique", "graphique": {
                "type": "barres", "titre": "Taille par périmètre", "donnees_ids": ids,
            }},
            {"type": "grille_kpi", "cellules": [
                {"valeur": "381,5 Md€", "libelle": "Marché mondial", "source": "Socle"},
                {"valeur": "6,1 Md€", "libelle": "Marché France", "source": "Socle"},
                {"valeur": "+4 %", "libelle": "Croissance", "source": "Socle"},
            ]},
            {"type": "encadre", "encadre": {
                "intitule": "Lecture du chapitre",
                "lignes": ["Opportunité.", "Limite.", "Décision."],
            }},
        ],
        "donnees_utilisees": ids,
        "resume": "Résumé du chapitre.",
    })


def test_les_six_types_de_blocs_traversent_la_chaine(tmp_path: Path) -> None:
    """De l'assemblage au fichier écrit. Aucun type ne doit rester en route."""
    from generation.rendu_word.assemblage import assembler_etude
    from generation.rendu_word.depuis_json import rendre_etude

    etude, _rapport = assembler_etude(
        socle=_socle(), chapitres=[_chapitre_avec_tous_les_blocs()],
        titre="Étude de marché",
    )

    types_produits = {
        bloc["type"]
        for chapitre in etude["chapitres"] for bloc in chapitre["blocs"]
    }
    for attendu in ("sous_titre", "paragraphe", "tableau", "kpi", "encadre"):
        assert attendu in types_produits, (
            f"le type « {attendu} » n'est pas sorti de l'assemblage : "
            f"{sorted(types_produits)}"
        )

    chemin = rendre_etude(etude, tmp_path / "tous_les_blocs.docx")
    assert chemin.is_file()
    assert chemin.stat().st_size > 10_000, "document suspicieusement léger"


def test_l_ordre_des_blocs_est_conserve_par_l_assemblage() -> None:
    """Le graphique reste ENTRE le tableau et la grille de chiffres.

    C'est tout l'objet du contrat ordonné : une version antérieure résolvait
    les graphiques en bloc après la boucle, ce qui les rejetait tous en queue
    de chapitre.
    """
    from generation.rendu_word.assemblage import assembler_etude

    etude, _ = assembler_etude(
        socle=_socle(), chapitres=[_chapitre_avec_tous_les_blocs()],
        titre="Étude de marché",
    )
    types = [b["type"] for b in etude["chapitres"][0]["blocs"]]
    # `bandeau` ouvre le chapitre ; on compare ce qui suit.
    suite = [t for t in types if t != "bandeau"]
    assert suite.index("graphique") < suite.index("kpi"), suite
    assert suite.index("tableau") < suite.index("graphique"), suite
    assert suite.index("kpi") < suite.index("encadre"), suite

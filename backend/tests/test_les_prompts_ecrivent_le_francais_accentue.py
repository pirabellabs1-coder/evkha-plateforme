"""Les prompts écrivent le français avec ses accents — sinon le document les perd.

## Le défaut mesuré

Corpus du 14/09/2026 : `chapitre_desaccentue` dans 5 dossiers — « Conclusion
analytique et graphiques » écrit « donnees, etendue, notoriete, specialisation ».
Le chapitre est réécrit, donc repayé.

La cause était en amont : les fichiers de prompts mêmes écrivaient sans accents
(« Redige en paragraphes developpes », « strategique » 113 fois). Mesuré avec
le détecteur du gate, 1 067 mots désaccentués dans 76 fichiers. Le modèle
reprend la forme qu'on lui montre — la leçon du vocabulaire interne.

## Pourquoi le détecteur du gate

Le test passe sur les prompts le MÊME contrôle que le gate passe sur le
document (règle 5) : un prompt que le gate jugerait « écrit sans accents » est
un prompt qui fabrique ce défaut.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from generation.checks_post_rendu import detecter_chapitres_desaccentues


def _dossiers() -> list[Path]:
    from generation.chapitres.configuration import RACINE_PROMPTS

    dossiers = sorted(d for d in RACINE_PROMPTS.iterdir() if d.is_dir() and any(d.glob("*.md")))
    assert len(dossiers) >= 4, "aucun prompt lu : le test ne jugerait rien (règle 1)"
    return dossiers


@pytest.mark.parametrize("dossier", _dossiers(), ids=lambda d: d.name)
def test_aucun_fichier_de_prompt_n_est_juge_desaccentue_par_le_gate(dossier: Path) -> None:
    from generation.chapitres.fichiers_prompts import _BANDEAU

    sections = [
        SimpleNamespace(
            number=i, title=f.name, body=_BANDEAU.sub("", f.read_text(encoding="utf-8")),
        )
        for i, f in enumerate(sorted(dossier.glob("*.md")))
    ]
    fautes = {d.titre: d.mots for d in detecter_chapitres_desaccentues(sections)}
    assert fautes == {}


def test_la_garde_sait_encore_mordre() -> None:
    """CONTRE-ÉPREUVE : un prompt réécrit sans accents est bien signalé."""
    juste = SimpleNamespace(number=1, title="a", body=(
        "Rédige une synthèse stratégique : la cohérence du modèle économique, la "
        "dernière étape, la méthode, les données, la référence, le périmètre et "
        "les critères."
    ))
    fautif = SimpleNamespace(number=2, title="b", body=(
        "Redige une synthese strategique : la coherence du modele economique, la "
        "derniere etape, la methode, les donnees, la reference, le perimetre et "
        "les criteres."
    ))
    assert [d.titre for d in detecter_chapitres_desaccentues([juste, fautif])] == ["b"]


def test_les_consignes_python_envoyees_a_chaque_chapitre_sont_accentuees() -> None:
    """Les règles des prix, de fond, des figures et les consignes de livrable.

    Elles partent dans CHAQUE chapitre : c'était la forme la plus répétée au
    modèle, et la plus désaccentuée (« PRIX ET MODELE ECONOMIQUE », 36 mots).
    Jugées avec les fichiers de prompts, comme un seul document.
    """
    from generation.chapitres import runner
    from generation.chapitres.configuration import RACINE_PROMPTS
    from generation.chapitres.fichiers_prompts import _BANDEAU
    from generation.prompts import REGLES_IDENTIFIANTS_FIGURES, _consigne_specifique_livrable
    from generation.socle import prompt as socle

    consignes = {
        "système": runner._SYSTEME, "chiffres": runner.COHERENCE_DES_CHIFFRES,
        "sources": runner.SOURCES_ET_TRACABILITE, "prix": runner.PRIX_ET_MODELE_ECONOMIQUE,
        "fond": runner.REGLES_DE_FOND, "forme commune": runner._forme_commune(),
        "documents": runner.CONSIGNE_DOCUMENTS_CHAPITRE, "figures": REGLES_IDENTIFIANTS_FIGURES,
        "socle": socle._REGLES, "relecture du socle": socle.RELECTURE_DU_SOCLE,
        **{f"forme {k}": v for k, v in runner._FORME_PAR_LIVRABLE.items()},
        **{
            f"consigne {k}": _consigne_specifique_livrable(k)
            for k in ("competitor_study", "business_plan", "business_strategy")
        },
    }
    sections = [SimpleNamespace(number=i, title=nom, body=texte)
                for i, (nom, texte) in enumerate(consignes.items())]
    sections += [
        SimpleNamespace(
            number=1000 + i, title=f"{f.parent.name}/{f.name}",
            body=_BANDEAU.sub("", f.read_text(encoding="utf-8")),
        )
        for i, f in enumerate(sorted(RACINE_PROMPTS.glob("*/*.md")))
    ]
    fautes = {d.titre: d.mots for d in detecter_chapitres_desaccentues(sections)}
    assert fautes == {}


def test_aucun_identifiant_n_a_pris_d_accent() -> None:
    """Relecture du 14/09/2026 (B1) : la restauration avait écrit `"activités_cles"`.

    Le schéma `Canvas` interdit toute clé inconnue : le modèle qui recopie
    l'exemple voit son chapitre refusé, puis repayé. Les accents vont à la
    prose, jamais à un identifiant ni à une clé JSON.
    """
    import re

    from generation.chapitres.configuration import RACINE_PROMPTS

    accent = "[À-ÖØ-öø-ÿ]"
    identifiant = re.compile(
        rf"\b\w*{accent}\w*_\w+|\b\w+_\w*{accent}\w*|\"[^\"\s]*{accent}[^\"\s]*\"\s*:"
    )
    fautes = {
        f"{f.parent.name}/{f.name}": identifiant.findall(f.read_text(encoding="utf-8"))
        for f in sorted(RACINE_PROMPTS.glob("*/*.md"))
    }
    assert {k: v for k, v in fautes.items() if v} == {}

"""Phase 35 — EC strategy : cardinaux concurrents + matrice HTML.

Deux regles structurelles pour toute etude de concurrence :

  1. Cardinaux Evangeline (fiche 2) : exactement 8 concurrents directs
     et 3 indirects. Ni plus, ni moins. Migre depuis `checks_evangeline`.

  2. Le chapitre 5 (blueprint `ec.05.matrice_positionnement`) DOIT
     contenir la matrice HTML. Le prompt insiste (« ETAPE OBLIGATOIRE :
     le tableau HTML DOIT apparaitre ») mais rien ne verifiait qu'elle
     etait bien la — un modele pouvait decrire la matrice en prose et
     passer le gate. Un banquier lit la matrice, pas la prose : sans
     tableau, le livrable est incomplet.

Regle 4 : ces deux regles sont structurelles pour tout EC, pas des
cas particuliers. Elles vivent dans la strategy EC.
"""
from __future__ import annotations

import pytest


# ══════════════════════════════════════════════════════════════════════════
# 1. Cardinaux concurrents (migre)
# ══════════════════════════════════════════════════════════════════════════


def test_cardinaux_conformes_ne_signalent_rien() -> None:
    """Contre-epreuve : 8 directs + 3 indirects → aucun probleme."""
    from generation.strategies.ec import ECStrategy

    corps = "## Concurrents directs\n" + "\n".join(
        f"- Acteur {i}" for i in range(1, 9)
    ) + "\n\n## Concurrents indirects\n" + "\n".join(
        f"- Acteur {i}" for i in range(1, 4)
    )
    # On ajoute une matrice minimale pour eviter le second check.
    corps_matrice = "<table><tr><th>x</th></tr><tr><td>a</td></tr>" \
                    "<tr><td>b</td></tr><tr><td>c</td></tr></table>"

    problemes = ECStrategy().problemes_de_coherence(
        None, {2: corps, 5: corps_matrice},  # type: ignore[arg-type]
    )
    assert problemes == []


def test_cardinaux_divergents_sont_signales() -> None:
    """6 directs au lieu de 8 → signal categorie concurrents_ec."""
    from generation.strategies.ec import ECStrategy

    corps = "## Concurrents directs\n" + "\n".join(
        f"- Acteur {i}" for i in range(1, 7)
    ) + "\n\n## Concurrents indirects\n" + "\n".join(
        f"- Acteur {i}" for i in range(1, 4)
    )
    corps_matrice = "<table><tr><th>x</th></tr><tr><td>a</td></tr>" \
                    "<tr><td>b</td></tr><tr><td>c</td></tr></table>"

    problemes = ECStrategy().problemes_de_coherence(
        None, {2: corps, 5: corps_matrice},  # type: ignore[arg-type]
    )
    categories = [p.categorie for p in problemes]
    assert "concurrents_ec" in categories


# ══════════════════════════════════════════════════════════════════════════
# 2. Matrice HTML au chapitre 5
# ══════════════════════════════════════════════════════════════════════════


def test_matrice_html_presente_au_chapitre_5_ne_signale_rien() -> None:
    """Contre-epreuve : un tableau avec plusieurs lignes passe."""
    from generation.strategies.ec import ECStrategy

    matrice = (
        "<table style=\"border-collapse:collapse\">"
        "<tr><td>Qualite +</td><td>Acteur A</td><td>Acteur B</td></tr>"
        "<tr><td>Median</td><td>Nous</td><td>Acteur C</td></tr>"
        "<tr><td>Qualite -</td><td>Acteur D</td><td>Acteur E</td></tr>"
        "</table>"
    )
    # Corpus minimal cardinaux valides pour isoler le check matrice.
    corps_cardinaux = "## Concurrents directs\n" + "\n".join(
        f"- Acteur {i}" for i in range(1, 9)
    ) + "\n## Concurrents indirects\n" + "\n".join(
        f"- Acteur {i}" for i in range(1, 4)
    )

    problemes = ECStrategy().problemes_de_coherence(
        None, {2: corps_cardinaux, 5: matrice},  # type: ignore[arg-type]
    )
    matrice_problemes = [p for p in problemes if p.categorie == "matrice_absente"]
    assert matrice_problemes == []


def test_matrice_decrite_en_prose_sans_table_est_signalee() -> None:
    """Cas defaut : le modele decrit la matrice, oublie de la generer."""
    from generation.strategies.ec import ECStrategy

    corps_prose = (
        "La matrice de positionnement place Acteur A en haut a gauche "
        "(premium accessible), Acteur B en bas a droite (accessible haut "
        "de gamme). Notre projet vise le centre gauche. Cette repartition "
        "montre une opportunite claire sur le quadrant premium."
    )
    corps_cardinaux = "## Concurrents directs\n" + "\n".join(
        f"- Acteur {i}" for i in range(1, 9)
    ) + "\n## Concurrents indirects\n" + "\n".join(
        f"- Acteur {i}" for i in range(1, 4)
    )

    problemes = ECStrategy().problemes_de_coherence(
        None, {2: corps_cardinaux, 5: corps_prose},  # type: ignore[arg-type]
    )
    matrice_problemes = [p for p in problemes if p.categorie == "matrice_absente"]
    assert len(matrice_problemes) == 1
    assert matrice_problemes[0].chapitre == 5


def test_tableau_trop_petit_est_signale() -> None:
    """Un `<table>` avec une seule ligne n'est pas une matrice."""
    from generation.strategies.ec import ECStrategy

    corps = "<table><tr><td>Acteur A seul</td></tr></table>"
    corps_cardinaux = "## Concurrents directs\n" + "\n".join(
        f"- Acteur {i}" for i in range(1, 9)
    ) + "\n## Concurrents indirects\n" + "\n".join(
        f"- Acteur {i}" for i in range(1, 4)
    )

    problemes = ECStrategy().problemes_de_coherence(
        None, {2: corps_cardinaux, 5: corps},  # type: ignore[arg-type]
    )
    matrice_problemes = [p for p in problemes if p.categorie == "matrice_absente"]
    assert len(matrice_problemes) == 1


def test_absence_de_chapitre_5_ne_leve_pas_derreur() -> None:
    """Regle 4 : si le blueprint change et supprime le chapitre 5, on ne
    doit pas planter — juste ne pas signaler la matrice absente (le
    contract « matrice au chap. 5 » n'a plus de sens)."""
    from generation.strategies.ec import ECStrategy

    corps_cardinaux = "## Concurrents directs\n" + "\n".join(
        f"- Acteur {i}" for i in range(1, 9)
    ) + "\n## Concurrents indirects\n" + "\n".join(
        f"- Acteur {i}" for i in range(1, 4)
    )
    problemes = ECStrategy().problemes_de_coherence(
        None, {2: corps_cardinaux},  # type: ignore[arg-type]
    )
    matrice_problemes = [p for p in problemes if p.categorie == "matrice_absente"]
    assert matrice_problemes == []


# ══════════════════════════════════════════════════════════════════════════
# 3. Enregistrement
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_get_strategy_retourne_ec_strategy_pour_competitor_study() -> None:
    """Regle 4 : chaque livrable a son manuel. EC ne retombe plus sur le
    fallback neutre — la refonte par livrable est complete."""
    from catalog.models import DeliverableType
    from generation.strategies import _reset_cache, get_strategy
    from generation.strategies.ec import ECStrategy

    _reset_cache()
    strategy = get_strategy(DeliverableType.COMPETITOR_STUDY)

    assert strategy.deliverable_type == DeliverableType.COMPETITOR_STUDY
    assert isinstance(strategy, ECStrategy)

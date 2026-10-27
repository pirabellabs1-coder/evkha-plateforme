"""Une donnée non nulle ne se dessine jamais comme rien.

Étude de marché à l'export relevée par la cliente le 26/10/2026 : sur la figure
de l'emboîtement du marché, « une barre est invisible » et deux autres sont
« identiques ». Les trois valeurs couvraient quatre ordres de grandeur.

L'entonnoir avait réglé ce défaut le 05/08/2026 — « la troisième marche n'avait
aucun pixel » — et la correction était restée chez lui : l'instance, pas la
classe (règle 4). Ces verrous la ferment pour les barres, et vérifient que le
chiffre écrit reste la valeur VRAIE.
"""
from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from generation.rendu_word.graphiques import (
    LARGEUR_D_UNE_ETIQUETTE,
    PART_MINIMALE_D_UNE_BARRE,
    _couleurs,
    barres_horizontales,
    etiquettes_repliees,
    longueurs_visibles,
)
from generation.rendu_word.palette import Palette, construire_palette, vers_rvb

#: Les trois valeurs du dossier réel : marché français, marché export,
#: marché atteignable par le projet.
EMBOITEMENT = [2_700_000_000.0, 2_100_000_000.0, 240_000.0]


@pytest.fixture
def palette() -> Palette:
    return construire_palette()


def test_une_valeur_ecrasee_recoit_le_plancher() -> None:
    longueurs = longueurs_visibles(EMBOITEMENT)
    plancher = 2_700_000_000.0 * PART_MINIMALE_D_UNE_BARRE
    assert longueurs[2] == pytest.approx(plancher)
    # Les deux premières sont assez longues pour se voir : on n'y touche pas.
    assert longueurs[:2] == EMBOITEMENT[:2]


def test_des_valeurs_comparables_ne_bougent_pas() -> None:
    """Contre-épreuve : le plancher ne doit pas déformer ce qui est lisible."""
    assert longueurs_visibles([10.0, 20.0, 30.0]) == [10.0, 20.0, 30.0]
    assert longueurs_visibles([1.0]) == [1.0]
    assert longueurs_visibles([]) == []


def test_un_zero_reste_un_zero() -> None:
    """Une barre absente est la bonne réponse pour un zéro."""
    assert longueurs_visibles([100.0, 0.0]) == [100.0, 0.0]


def test_le_signe_est_conserve() -> None:
    longueurs = longueurs_visibles([-1_000.0, 1.0])
    assert longueurs[0] == -1_000.0
    assert 0 < longueurs[1] <= 1_001.0 * PART_MINIMALE_D_UNE_BARRE * 1.001


def test_toutes_egales_ne_declenche_rien() -> None:
    """Étendue nulle : aucun plancher calculable, et rien à corriger."""
    assert longueurs_visibles([5.0, 5.0, 5.0]) == [5.0, 5.0, 5.0]


def _plus_long_segment(png: bytes, couleur: str) -> int:
    """La plus longue suite de pixels de la couleur d'une barre, en largeur.

    C'est la mesure qui dit si le lecteur VOIT la barre. Compter les pixels de
    la couleur ne suffisait pas : la crème des séries claires ressort aussi dans
    l'anticrénelage des étiquettes, et le compte ne bougeait pas entre le code
    d'avant et le correctif — un contrôle qui n'a rien à comparer (règle 1).
    """
    image = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"), dtype=int)
    cible = np.array(vers_rvb(couleur), dtype=int)
    carte = np.abs(image - cible).sum(axis=2) <= 12
    record = 0
    for ligne in carte:
        courant = 0
        for present in ligne:
            courant = courant + 1 if present else 0
            record = max(record, courant)
    return record


def test_la_troisieme_barre_se_voit_sur_l_image(palette: Palette) -> None:
    """La preuve sur l'image, pas sur la fonction (règle 7).

    Mesuré : 22 pixels de large avec le plancher, 2 sans — soit, à 2 000 px
    pour 16 cm de page, 1,8 mm contre un sixième de millimètre.
    """
    png = barres_horizontales(
        palette, ["Marché français", "Marché export", "Atteignable"], EMBOITEMENT,
    )
    largeur = _plus_long_segment(png, _couleurs(palette, 3)[2])
    assert largeur >= 15, f"la troisième barre ne fait que {largeur} px de large"


def test_le_chiffre_ecrit_reste_la_valeur_vraie(palette: Palette) -> None:
    """Le plancher déplace la barre, jamais le nombre : on vérifie le tracé.

    Le PNG ne se relit pas en texte ; on vérifie donc que l'appel passe la
    VALEUR au formateur, en comparant deux figures dont seule la petite valeur
    change — si l'étiquette suivait le plancher, elles seraient identiques.
    """
    noms = ["a", "b", "c"]
    une = barres_horizontales(palette, noms, [2_700_000_000.0, 2_100_000_000.0, 240_000.0])
    autre = barres_horizontales(palette, noms, [2_700_000_000.0, 2_100_000_000.0, 241_000.0])
    assert une != autre


def test_une_etiquette_longue_se_replie() -> None:
    [replie] = etiquettes_repliees(["Marché des produits alimentaires asiatiques"], 16)
    assert "\n" in replie
    assert max(len(ligne) for ligne in replie.splitlines()) <= 16
    # Contre-épreuve : une étiquette courte n'est pas touchée.
    assert etiquettes_repliees(["2027", "Chine"], LARGEUR_D_UNE_ETIQUETTE) == ["2027", "Chine"]


def test_un_mot_plus_long_que_la_largeur_survit() -> None:
    """Un mot insécable plus long que la colonne ne doit pas disparaître."""
    [replie] = etiquettes_repliees(["approvisionnements"], 8)
    assert "approvisionnements" in replie.replace("\n", "")


# ── Une part non nulle ne s'écrit pas « 0 % » sur la figure ─────────────────


def test_une_part_minuscule_garde_ses_chiffres() -> None:
    """Le défaut du 26/10/2026, dans la figure et non plus dans le seul texte.

    `autopct="%1.0f %%"` écrivait « 0 % » sur toute part sous 0,5 % : le
    camembert AFFIRMAIT que la part n'existe pas.
    """
    from generation.rendu_word.graphiques import _part_lisible

    assert "0,009" in _part_lisible(0.009)
    assert _part_lisible(0.009) != "0 %"
    # Contre-épreuve : une part nulle s'écrit toujours « 0 % », et une part
    # ordinaire garde son arrondi lisible.
    assert _part_lisible(0).replace(" ", " ").replace(" ", " ") == "0 %"
    assert _part_lisible(37.2).replace(" ", " ").replace(" ", " ") == "37 %"


def test_le_camembert_n_ecrit_plus_zero(palette: Palette) -> None:
    """Sur l'image : le camembert ne doit plus porter deux « 0 % ».

    Le PNG ne se relit pas en texte ; on compare donc deux camemberts dont
    seule la part minuscule change. Avec « %1.0f %% » les deux écrivaient
    « 0 % » et les images étaient identiques.
    """
    from generation.rendu_word.graphiques import camembert

    une = camembert(palette, ["Marché", "Capté"], [99.991, 0.009])
    autre = camembert(palette, ["Marché", "Capté"], [99.996, 0.004])
    assert une != autre

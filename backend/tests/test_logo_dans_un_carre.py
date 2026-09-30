"""Le logo tient dans un carré de 5 cm, centré, sans être déformé ni coupé (point 1, cliente).

30/09/2026 : la cliente demande un logo « recadré en carré sans rien couper,
centré, taille fixe (environ 5 cm) ». On loge donc l'image dans un carré en
gardant ses proportions : le plus grand côté fait 5 cm, l'autre suit.
"""
from __future__ import annotations

from generation.rendu_word.logo import dimensions, taille_dans_un_carre

COTE = 5 * 360_000  # 5 cm en EMU


def _png(largeur: int, hauteur: int) -> bytes:
    """Un PNG minimal : signature + IHDR portant les dimensions (CRC non vérifié)."""
    ihdr = largeur.to_bytes(4, "big") + hauteur.to_bytes(4, "big") + b"\x08\x06\x00\x00\x00"
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + ihdr + b"\x00" * 4


def _jpeg(largeur: int, hauteur: int) -> bytes:
    """Un JPEG minimal : SOI + un segment SOF0 portant hauteur puis largeur."""
    sof = b"\xff\xc0\x00\x11\x08" + hauteur.to_bytes(2, "big") + largeur.to_bytes(2, "big")
    return b"\xff\xd8" + b"\xff\xe0\x00\x04\x00\x00" + sof + b"\xff\xd9"


def test_les_dimensions_d_un_png_se_lisent() -> None:
    assert dimensions(_png(200, 100)) == (200, 100)


def test_les_dimensions_d_un_jpeg_se_lisent() -> None:
    assert dimensions(_jpeg(120, 240)) == (120, 240)


def test_un_logo_large_a_son_plus_grand_cote_a_5_cm() -> None:
    largeur, hauteur = taille_dans_un_carre(_png(200, 100), COTE)
    assert largeur == COTE and hauteur == COTE // 2


def test_un_logo_haut_a_son_plus_grand_cote_a_5_cm() -> None:
    largeur, hauteur = taille_dans_un_carre(_png(100, 200), COTE)
    assert hauteur == COTE and largeur == COTE // 2


def test_un_logo_carre_remplit_le_carre() -> None:
    assert taille_dans_un_carre(_png(300, 300), COTE) == (COTE, COTE)


def test_les_proportions_sont_gardees_rien_n_est_coupe() -> None:
    """Le rapport largeur/hauteur du rendu égale celui de l'image d'origine."""
    largeur, hauteur = taille_dans_un_carre(_png(160, 90), COTE)
    assert abs(largeur / hauteur - 160 / 90) < 0.01
    assert max(largeur, hauteur) == COTE


def test_une_image_sans_dimensions_lisibles_retombe_sur_le_carre() -> None:
    """Contre-épreuve : sans dimensions, un carré plutôt qu'un rendu qui échoue."""
    assert dimensions(b"pas une image") is None
    assert taille_dans_un_carre(b"pas une image", COTE) == (COTE, COTE)

"""Une évolution annoncée dans un tableau se recalcule depuis ses deux colonnes.

26/10/2026, étude de marché à l'export relevée par la cliente : « une base de
2,7 Md€ passe à 2,1 Md€, présentée comme −6 %, alors que la baisse réelle est
de −22 % ». Le chiffre faux servait ensuite de pilier dans une dizaine de
chapitres.

`verifier` ne l'a pas vu : son motif d'évolution attrape une tournure de PROSE
(« de 40 000 à 50 000, soit une hausse de 25 % »), d'un seul tenant. Les trois
nombres du défaut vivaient dans trois COLONNES. C'est la règle 4 — le contrôle
énumérait des tournures, la classe est « deux valeurs d'une même grandeur à
deux dates, et un pourcentage qui prétend les relier ».
"""
from __future__ import annotations

from generation.arithmetique import variations_fausses, verifier

LE_DEFAUT = """
| Segment | 2024 | 2025 | Évolution |
|---|---|---|---|
| Produits de cuisine asiatique | 2,7 Md€ | 2,1 Md€ | -6 % |
"""


def test_le_defaut_mesure_est_attrape() -> None:
    fautes = variations_fausses(LE_DEFAUT)
    assert len(fautes) == 1, fautes
    faute = fautes[0]
    assert faute.ecrit == -6
    assert round(faute.calcule, 1) == -22.2
    # Le motif doit être trouvable PAR LE LECTEUR dans le document (règle 2).
    motif = str(faute)
    assert "Produits de cuisine asiatique" in motif
    assert "Évolution" in motif


def test_la_prose_seule_ne_voyait_rien() -> None:
    """Le contrôle d'avant, rejoué sur le même tableau : il ne trouve rien.

    C'est ce qui rend le nouveau contrôle nécessaire plutôt que redondant
    (règle 6 : un test doit échouer sur le code d'avant).
    """
    assert verifier(LE_DEFAUT) == []


def test_une_evolution_juste_passe() -> None:
    """Contre-épreuve : le contrôle ne crie pas sur un tableau correct."""
    juste = """
| Segment | 2024 | 2025 | Évolution |
|---|---|---|---|
| Produits de cuisine asiatique | 2,7 Md€ | 2,1 Md€ | -22,2 % |
| Épicerie fine | 1,0 Md€ | 1,25 Md€ | +25 % |
"""
    assert variations_fausses(juste) == []


def test_un_arrondi_du_redacteur_n_est_pas_une_faute() -> None:
    """« −22 % » pour −22,22 % : le document arrondit, il ne se trompe pas."""
    arrondi = """
| Segment | 2024 | 2025 | Évolution |
|---|---|---|---|
| Produits | 2,7 Md€ | 2,1 Md€ | -22 % |
"""
    assert variations_fausses(arrondi) == []


def test_un_taux_annualise_n_est_pas_juge() -> None:
    """Contre-épreuve : un TCAC prend la racine n-ième, pas la différence relative.

    Sur 2020 → 2025, passer de 1,0 à 2,0 Md€ fait +100 % au total mais 14,9 %
    par an. Juger cette colonne avec la formule de la variation totale
    produirait un motif faux sur une colonne juste (règle 2).
    """
    tcac = """
| Segment | 2020 | 2025 | TCAC |
|---|---|---|---|
| Produits | 1,0 Md€ | 2,0 Md€ | 14,9 % |
"""
    assert variations_fausses(tcac) == []


def test_un_pourcentage_qui_n_est_pas_une_evolution_est_laisse_tranquille() -> None:
    """Contre-épreuve : une marge à côté de deux prix n'est pas une variation.

    Sans en-tête qui nomme une évolution, on ne devine pas. Un contrôle qui
    recalculerait « 12 % » depuis « 150 € » et « 18 € » crierait faux sur une
    ligne juste — et ce dépôt a mesuré ce que coûte un motif faux.
    """
    marge = """
| Produit | Prix 2024 | Prix 2025 | Marge |
|---|---|---|---|
| Sauce soja | 150 € | 18 € | 12 % |
"""
    assert variations_fausses(marge) == []


def test_sans_colonnes_d_annees_on_ne_juge_pas() -> None:
    """Deux montants et un pourcentage ne suffisent pas : il faut deux DATES."""
    sans_annees = """
| Poste | Budget | Réalisé | Évolution |
|---|---|---|---|
| Achats | 2,7 Md€ | 2,1 Md€ | -6 % |
"""
    assert variations_fausses(sans_annees) == []


def test_deux_unites_differentes_ne_se_comparent_pas() -> None:
    """Contre-épreuve : on refuse de diviser des euros par des clients."""
    melange = """
| Segment | 2024 | 2025 | Évolution |
|---|---|---|---|
| Produits | 2,7 Md€ | 2 100 clients | -6 % |
"""
    assert variations_fausses(melange) == []


def test_une_base_nulle_ne_produit_pas_de_division() -> None:
    """Contre-épreuve : 0 → 500 n'a pas de variation relative, et ne plante pas."""
    depuis_zero = """
| Segment | 2024 | 2025 | Évolution |
|---|---|---|---|
| Nouveau produit | 0 € | 500 € | +100 % |
"""
    assert variations_fausses(depuis_zero) == []


def test_plusieurs_annees_prennent_la_premiere_et_la_derniere() -> None:
    """Un tableau 2023/2024/2025 : l'évolution totale va de 2023 à 2025.

    « +5 % » est JUSTE sur ce tableau — (2,1 − 2,0) / 2,0 — et doit passer.
    Un contrôle qui aurait pris 2024 → 2025 aurait calculé −22,2 % et crié
    faux : ce test échoue donc si les bornes sont mal choisies.
    """
    trois_ans = """
| Segment | 2023 | 2024 | 2025 | Évolution |
|---|---|---|---|---|
| Produits | 2,0 Md€ | 2,7 Md€ | 2,1 Md€ | +5 % |
"""
    assert variations_fausses(trois_ans) == []


# ── Faux positifs trouvés par la relecture du 26/10/2026 ────────────────────
#
# Chacun a été REPRODUIT avant d'être corrigé : le contrôle criait faux sur une
# ligne juste, et chaque motif faux fait réécrire un chapitre payé (règle 2).


def test_deux_colonnes_de_la_meme_annee_ne_sont_pas_un_avant_apres() -> None:
    """« Importations 2024 » et « Exportations 2024 » ne se divisent pas.

    Les bornes étaient la première et la dernière année triées, sans vérifier
    qu'elles diffèrent : le contrôle comparait les imports aux exports et
    rendait « de 120 M€ à 80 M€, soit −33 % » sur une ligne juste.
    """
    imports_exports = """
| Pays | Importations 2024 | Exportations 2024 | Évolution |
|---|---|---|---|
| Japon | 120 M€ | 80 M€ | +4 % |
"""
    assert variations_fausses(imports_exports) == []


def test_un_ecart_entre_deux_taux_s_exprime_en_points() -> None:
    """Une part de marché qui passe de 12 % à 15 % gagne 3 POINTS, pas 25 %.

    Part de marché, taux de pénétration, de marge, d'occupation : c'est
    l'ossature chiffrée d'une étude de marché. Le garde-fou du TCAC fermait un
    cas ; la classe est « le résultat n'est pas une différence relative ».
    """
    taux = """
| Indicateur | 2024 | 2025 | Évolution |
|---|---|---|---|
| Part de marché | 12 % | 15 % | +3 % |
"""
    assert variations_fausses(taux) == []


def test_une_cellule_qui_annonce_des_points_n_est_pas_jugee() -> None:
    en_points = """
| Indicateur | 2024 | 2025 | Évolution |
|---|---|---|---|
| Taux de marge | 0,12 | 0,15 | +3 pts |
"""
    assert variations_fausses(en_points) == []


def test_une_base_negative_n_est_pas_jugee() -> None:
    """Une perte qui passe de −50 k€ à −20 k€ s'écrit « −60 % » en gestion.

    `(après − avant) / |avant|` rendrait « +60 % » : deux conventions de signe
    qui se contredisent sur une ligne juste.
    """
    perte = """
| Poste | 2024 | 2025 | Évolution |
|---|---|---|---|
| Résultat net | -50 000 € | -20 000 € | -60 % |
"""
    assert variations_fausses(perte) == []


def test_un_ecart_type_n_est_pas_une_variation() -> None:
    """« Écart type » portait le mot « écart » et déclenchait le contrôle."""
    ecart_type = """
| Panel | 2024 | 2025 | Écart type |
|---|---|---|---|
| Prix relevés | 100 € | 120 € | 8 % |
"""
    assert variations_fausses(ecart_type) == []


def test_une_colonne_au_titre_nu_pourcent_n_est_pas_jugee() -> None:
    """Une colonne « % » à côté de deux années désigne le plus souvent une PART."""
    part = """
| Segment | 2024 | 2025 | % |
|---|---|---|---|
| Premium | 100 € | 120 € | 35 % |
"""
    assert variations_fausses(part) == []


def test_un_ecart_relatif_reste_juge() -> None:
    """Contre-épreuve : resserrer « écart » ne doit pas désarmer le contrôle."""
    relatif = """
| Segment | 2024 | 2025 | Écart relatif |
|---|---|---|---|
| Premium | 100 € | 120 € | 8 % |
"""
    assert len(variations_fausses(relatif)) == 1


def test_le_motif_cite_les_cellules_telles_qu_elles_sont_ecrites() -> None:
    """Règle 2 : le motif doit être trouvable dans le document par le lecteur.

    Le motif écrivait « de 2.7e+06 € à 2.1e+06 € » — une notation que le
    document ne contient nulle part, et que le rédacteur chargé de corriger ne
    pouvait pas retrouver.
    """
    euros_nus = """
| Segment | 2024 | 2025 | Évolution |
|---|---|---|---|
| Produits | 2 700 000 € | 2 100 000 € | -6 % |
"""
    motif = str(variations_fausses(euros_nus)[0])
    assert "2 700 000 €" in motif, motif
    assert "2 100 000 €" in motif, motif
    assert "e+06" not in motif, motif
    assert "-22,2 %" in motif, motif


def test_une_ligne_sans_intitule_ne_produit_pas_de_motif_introuvable() -> None:
    """« Ligne «  » » n'est trouvable nulle part : on s'abstient."""
    sans_intitule = """
| | 2024 | 2025 | Évolution |
|---|---|---|---|
| | 100 € | 120 € | +8 % |
"""
    assert variations_fausses(sans_intitule) == []

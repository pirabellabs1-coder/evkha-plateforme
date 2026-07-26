"""Phase 32 — Anti-troncature + anti-doublons post-rendu.

Deux defauts nommes par Evangeline sur WAOME EM v1 (21/07/2026) que le
gate actuel laissait passer :

  1. « L'annexe est reellement tronquee a la fin de la phrase "aupres
     des prospects grandes mar..." »
  2. « Chaque titre de chapitre apparait deux fois, la sous-section 2.4
     apparait deux fois. »

Contexte reel mesure sur le doc :

    ... aupres des prospects grandes mar\n\n
    ## 22. Sources et methodologie\n\n
    # 22. Sources et methodologie\n\n

DEUX defauts d'un coup. Le check `sentence_cut` de `qa.py` regarde la
derniere ligne mais tolere apparemment « mar » (mot court potentiellement
legitime). Il faut un check plus severe : la fin de chaque chapitre DOIT
se terminer par une ponctuation forte, sinon perte de contenu client.

Regle 4 (viser la classe) : chaque livrable a le meme risque de troncature
et de doublons de titres, ces checks sont TRANSVERSES — module partage.
"""
from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════════
# 1. Anti-troncature : fin de chapitre sans ponctuation forte
# ══════════════════════════════════════════════════════════════════════════


def test_la_troncature_waome_prospects_grandes_mar_est_detectee() -> None:
    """Cas EXACT signale par Evangeline sur WAOME EM v1 : la derniere
    phrase de l'annexe finit par « ... aupres des prospects grandes mar »
    (mot « mar » tronque, aucune ponctuation finale)."""
    from generation.checks_post_rendu import detecter_troncatures

    section_body = (
        "Contenu normal de l'annexe. Analyse des personas cible. "
        "Un directeur artistique freelance associe valorise immediatement "
        "l'offre aupres des prospects grandes mar"
    )
    troncatures = detecter_troncatures([(21, "Annexe", section_body)])

    assert len(troncatures) == 1
    assert troncatures[0].chapitre == 21
    assert "mar" in troncatures[0].fin_capturee


def test_un_chapitre_qui_finit_par_un_point_ne_declenche_rien() -> None:
    """Contre-epreuve : la fin normale d'un chapitre passe."""
    from generation.checks_post_rendu import detecter_troncatures

    section_body = (
        "Contenu du chapitre. Analyse conclusive avec une derniere "
        "phrase argumentee qui se termine correctement."
    )

    assert detecter_troncatures([(5, "Ch5", section_body)]) == []


def test_les_ponctuations_fortes_alternatives_passent() -> None:
    """Contre-epreuve : le point d'exclamation, d'interrogation, guillemet
    fermant, deux-points, tous acceptes comme fin propre."""
    from generation.checks_post_rendu import detecter_troncatures

    for fin in (".", " !", " ?", " »", " :", "…"):
        section_body = f"Contenu du chapitre qui se termine avec cette ponctuation{fin}"
        assert detecter_troncatures([(1, "Ch", section_body)]) == [], (
            f"faux positif pour ponctuation {fin!r}"
        )


def test_un_chapitre_termine_par_un_tableau_html_passe() -> None:
    """Contre-epreuve : les chapitres avec tableau ou bloc chart en fin
    (structure markdown/HTML) ne sont pas des troncatures."""
    from generation.checks_post_rendu import detecter_troncatures

    section_body = (
        "Analyse chiffrée du marché.\n\n"
        "| Zone | Taille | TCAC |\n"
        "|---|---|---|\n"
        "| Mondial | 40 Md$ | 20 % |"
    )

    assert detecter_troncatures([(1, "Ch", section_body)]) == []


def test_un_chapitre_vide_est_signale() -> None:
    """Contre-epreuve : un chapitre vide n'est pas une troncature au sens
    strict, mais il est TOUT AUSSI grave — livrable amputé."""
    from generation.checks_post_rendu import detecter_troncatures

    troncatures = detecter_troncatures([(5, "Ch5", "   \n\n  ")])

    assert len(troncatures) == 1


def test_le_mot_final_isole_court_est_suspect() -> None:
    """Un mot final court (< 4 lettres) sans ponctuation est probablement
    tronque : « mar », « fon », « prop ». Les vrais mots courts (« et »,
    « ou ») sont normalement suivis d'un mot, pas en fin de section."""
    from generation.checks_post_rendu import detecter_troncatures

    section = "Analyse detaillee du marche global qui suit une tendance haus"
    troncatures = detecter_troncatures([(1, "Ch", section)])

    assert len(troncatures) == 1


# ══════════════════════════════════════════════════════════════════════════
# 2. Anti-doublons de titres consecutifs
# ══════════════════════════════════════════════════════════════════════════


def test_les_titres_dupliques_de_waome_sont_detectes() -> None:
    """Cas EXACT WAOME : « ## 22. Sources et methodologie\\n\\n
    # 22. Sources et methodologie ». Meme intitule, deux niveaux
    consecutifs — visuel confusant, sans ambiguite un defaut."""
    from generation.checks_post_rendu import detecter_doublons_titres

    section = (
        "## 22. Sources et methodologie\n\n"
        "# 22. Sources et methodologie\n\n"
        "Contenu."
    )
    doublons = detecter_doublons_titres([(22, "Sources", section)])

    assert len(doublons) == 1
    assert "Sources et methodologie" in doublons[0].intitule


def test_la_sous_section_2_4_dupliquee_est_detectee() -> None:
    """Cas EXACT WAOME : « la sous-section 2.4 apparait deux fois »."""
    from generation.checks_post_rendu import detecter_doublons_titres

    section = (
        "## 2.4 — Analyse concurrentielle locale\n\n"
        "Contenu.\n\n"
        "## 2.4 — Analyse concurrentielle locale\n\n"
        "Contenu."
    )
    doublons = detecter_doublons_titres([(2, "Marche", section)])

    assert len(doublons) == 1
    assert "2.4" in doublons[0].intitule


def test_deux_titres_differents_meme_niveau_ne_declenchent_pas() -> None:
    """Contre-epreuve : deux sous-titres H2 differents sont normaux."""
    from generation.checks_post_rendu import detecter_doublons_titres

    section = (
        "## 2.1 — Marche national\n\n"
        "Contenu.\n\n"
        "## 2.2 — Marche regional\n\n"
        "Contenu."
    )

    assert detecter_doublons_titres([(2, "Marche", section)]) == []


def test_meme_titre_dans_chapitres_differents_ne_declenche_pas() -> None:
    """Contre-epreuve : un titre generique commun (« Synthese », « Sources »)
    peut apparaitre dans plusieurs chapitres — c'est normal."""
    from generation.checks_post_rendu import detecter_doublons_titres

    sections = [
        (1, "Ch1", "## Synthese\n\nContenu du chapitre 1."),
        (2, "Ch2", "## Synthese\n\nContenu du chapitre 2."),
    ]

    assert detecter_doublons_titres(sections) == []


# ══════════════════════════════════════════════════════════════════════════
# 3. Cohérence numérique/textuelle : « N X » vs items comptes
# ══════════════════════════════════════════════════════════════════════════


def test_le_desaccord_trois_familles_quatre_categories_est_detecte() -> None:
    """Cas EXACT WAOME : « "Trois familles de clientele" presente quatre
    categories »."""
    from generation.checks_post_rendu import detecter_desaccords_numeriques

    section = (
        "Trois familles de clientele structurent l'analyse :\n\n"
        "- Grands comptes retail decoration\n"
        "- Enseignes intermediaires ETI\n"
        "- Univers alimentaire\n"
        "- Univers editorial et hotelier\n"
    )
    desaccords = detecter_desaccords_numeriques([(3, "Ch3", section)])

    assert len(desaccords) == 1
    assert "trois" in desaccords[0].detail.lower()
    assert "4" in desaccords[0].detail  # nombre reel d'items


def test_le_bon_compte_ne_declenche_pas() -> None:
    """Contre-epreuve : « trois familles » suivi de 3 items = pas de defaut."""
    from generation.checks_post_rendu import detecter_desaccords_numeriques

    section = (
        "Trois familles de clientele structurent l'analyse :\n\n"
        "- Grands comptes\n"
        "- ETI\n"
        "- Univers alimentaire\n"
    )

    assert detecter_desaccords_numeriques([(3, "Ch3", section)]) == []


def test_les_ratios_numeriques_ne_sont_pas_pris_pour_des_annonces_de_liste() -> None:
    """Contre-epreuve : « 3 M€ », « 5 % », « 12 mois » ne doivent PAS
    declencher — ce sont des chiffres, pas des annonces de liste."""
    from generation.checks_post_rendu import detecter_desaccords_numeriques

    section = "Le marche pese 3 M€ en 2024, avec une croissance de 5 % par an."

    assert detecter_desaccords_numeriques([(1, "Ch", section)]) == []

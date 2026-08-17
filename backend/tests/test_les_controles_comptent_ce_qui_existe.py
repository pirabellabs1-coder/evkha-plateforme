"""Un contrôle ne juge que ce qu'il a su lire — mesuré sur `026fecea`.

Le recontrôle du 10/08/2026 au soir a rendu CINQUANTE échecs sur un document
propre, dont quarante-sept identiques : « Concurrents directs : 0 trouvés,
8 attendus ». Quarante-sept sections que personne n'avait écrites — le
détecteur prenait chaque MENTION de « concurrents directs » (prose, cellule,
rappel de consigne) pour un titre de section, et jugeait « zéro » des
tableaux qu'il ne sait pas compter. Et une ligne de source terminée par son
URL était « une perte probable de contenu client ».

Trois règles, verrouillées ici :
  - une SECTION est un titre markdown, pas une mention ;
  - zéro puce signifie « matière illisible pour ce compteur », jamais
    « zéro concurrent » (règle 2) ;
  - une ligne close par une URL complète est une ligne complète.
"""
from __future__ import annotations

from generation.checks_evangeline import verifier_concurrents_dans_ec
from generation.checks_post_rendu import detecter_troncatures


def _liste(n: int) -> str:
    return "\n".join(f"- Acteur {i}" for i in range(1, n + 1))


# ── Le compteur de concurrents ───────────────────────────────────────────────


def test_une_mention_en_prose_n_est_pas_une_section() -> None:
    """Le défaut exact : la base consolidée met la phrase dans chaque chapitre."""
    corps = (
        "La liste est FERMÉE : 8 concurrents directs et 3 indirects, ni plus "
        "ni moins. Le tableau ci-dessous les reprend.\n\n"
        "| Acteur | Type |\n| --- | --- |\n| VeraCash | direct |\n"
    )

    assert verifier_concurrents_dans_ec([(2, corps)]) == []


def test_un_titre_suivi_d_un_tableau_ne_vaut_pas_zero() -> None:
    """Zéro puce = matière que le compteur ne lit pas, pas zéro concurrent."""
    corps = (
        "## 1.3 Concurrents directs retenus\n\n"
        "| Acteur | CA |\n| --- | --- |\n| VeraCash | 1,4 M€ |\n"
    )

    assert verifier_concurrents_dans_ec([(1, corps)]) == []


def test_une_vraie_liste_fausse_est_toujours_signalee() -> None:
    """CONTRE-ÉPREUVE : on resserre le détecteur, on n'éteint pas le contrôle."""
    corps = "## Concurrents directs\n\n" + _liste(6)

    divergents = verifier_concurrents_dans_ec([(2, corps)])

    assert len(divergents) == 1
    assert divergents[0].trouves == 6
    assert divergents[0].chapitre == 2


def test_deux_chapitres_qui_listent_juste_ne_s_additionnent_pas() -> None:
    """Le blocage « 20 trouvés » : 8 + 8 + 4 sommés entre chapitres."""
    ch1 = "## Concurrents directs\n\n" + _liste(8)
    ch2 = "## 2.1 Concurrents directs analysés\n\n" + _liste(8)

    assert verifier_concurrents_dans_ec([(1, ch1), (2, ch2)]) == []


# ── Le détecteur de troncature ───────────────────────────────────────────────


def test_une_ligne_close_par_une_url_est_complete() -> None:
    corps = (
        "Les sources mobilisées :\n"
        "- Comptoir, achat et rachat bijoux Paris depuis 1977 — https://www.interor.fr/"
    )

    assert detecter_troncatures([(9, "Sources et méthodologie", corps)]) == []


def test_un_chapitre_ferme_sur_sa_figure_est_complet() -> None:
    corps = (
        "Le comparatif tarifaire se lit ci-dessous.\n\n"
        '<!-- graphique:barres titre="Prix" donnees="prix_a,prix_b" -->'
    )

    assert detecter_troncatures([(7, "Conclusion", corps)]) == []


def test_une_phrase_reellement_coupee_est_toujours_signalee() -> None:
    """CONTRE-ÉPREUVE : la vraie troncature reste un échec."""
    corps = "Le marché progresse fortement et les acteurs principaux se par"

    assert detecter_troncatures([(3, "Analyse", corps)]) != []


# ── Le compteur de visuels du chapitre 7 ─────────────────────────────────────


def _tableau(colonnes: int = 3) -> str:
    entetes = "| " + " | ".join(f"C{i}" for i in range(colonnes)) + " |"
    separateur = "| " + " | ".join(["---"] * colonnes) + " |"
    ligne = "| " + " | ".join(f"v{i}" for i in range(colonnes)) + " |"
    return f"{entetes}\n{separateur}\n{ligne}\n{ligne}"


def test_un_tableau_structure_compte_comme_un_visuel() -> None:
    """La fiche du chapitre 7 demande deux visuels « sous forme de tableau ».

    Le moteur structuré rend un `BlocTableau` en markdown, jamais en
    `<table>` : `026fecea` portait ses quatre visuels et n'en faisait compter
    que trois. Ce test échoue sur le compteur d'avant.
    """
    from generation.strategies.ec import verifier_visuels_du_chapitre_conclusion

    corps = (
        "## Visuel 1 — Carte des implantations\n\n" + _tableau() + "\n\n"
        '<!-- graphique:barres_horizontales titre="Parts" donnees="a,b" -->\n\n'
        '<!-- graphique:radar titre="Forces" donnees="c,d,e" -->\n\n'
        "## Visuel 4 — Répartition des canaux\n\n" + _tableau(4)
    )

    assert verifier_visuels_du_chapitre_conclusion({7: corps}) == []


def test_un_tableau_compte_une_fois_quel_que_soit_son_nombre_de_lignes() -> None:
    """CONTRE-ÉPREUVE : on compte des BLOCS, pas des lignes.

    Compter les lignes ferait passer le chapitre avec un seul tableau de
    quatre lignes — un contrôle qui justifie tout ne contrôle plus rien.
    """
    from generation.strategies.ec import verifier_visuels_du_chapitre_conclusion

    corps = "## Un seul tableau\n\n| A | B |\n| --- | --- |\n" + "| x | y |\n" * 12

    assert verifier_visuels_du_chapitre_conclusion({7: corps}) != []


def test_un_chapitre_sans_aucun_visuel_reste_signale() -> None:
    """CONTRE-ÉPREUVE : la prose seule ne devient pas un visuel."""
    from generation.strategies.ec import verifier_visuels_du_chapitre_conclusion

    corps = "La conclusion analytique décrit les acteurs en trois paragraphes."

    assert verifier_visuels_du_chapitre_conclusion({7: corps}) != []

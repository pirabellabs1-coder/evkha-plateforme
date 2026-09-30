"""La langue du texte qui atteint le Word : élisions, mots anglais, codes d'unité.

## Le défaut, relevé sur un document livré

Business plan ÉCLORE (dossier `cb59cede`, 29/09/2026, moteur structuré) :
« already financé » p. 67, « se accroît » p. 7, « MEUR », « EUR » et
« unite » dans le texte (diagnostic du 29/09/2026, § 3.16). Aucun outil
d'orthographe dans la chaîne ; la table d'anglicismes de `rendering.py` ne
s'applique qu'au markdown de l'ancienne chaîne, jamais au Word.

Décision D4 du diagnostic : des contrôles internes, réparés au rendu, pas
d'API publique. La réparation vit dans `chapitres.typographie`, appliquée au
`payload` du chapitre avant que rien ne le rende ; le contrôle post-rendu
(`checks_post_rendu.detecter_mots_anglais`) lit la MÊME liste, pour ce que la
réparation ne tranche pas.

## Ce que ce fichier verrouille surtout : ce qu'on NE touche PAS

Les contre-épreuves comptent plus que les épreuves (règle 2 : un remède qui
frappe ce qui n'était pas malade est pire que le défaut). Le h aspiré, « le
un », « la une », « le ou la », un pronom derrière un trait d'union, un nom
propre, un titre de publication anglais, « EUR-Lex », « Indeed » : tout cela
est du français — ou de l'anglais — correct, et doit sortir intact.

Tous les tests d'épreuve échouent sur le code d'avant (29/09/2026) :
`reparer_langue`, `mots_anglais` et `detecter_mots_anglais` n'existaient pas,
et `reparer_texte` laissait passer les trois fautes d'ÉCLORE.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from generation.chapitres.schema import (
    BlocGraphique,
    BlocGrilleKpi,
    BlocParagraphe,
    BlocTableau,
    CelluleKpi,
    ChapitrePayload,
    Graphique,
    Tableau,
    TypeGraphique,
)
from generation.chapitres.typographie import reparer_texte, reparer_typographie

# ── Les trois fautes d'ÉCLORE, telles que le document les imprimait ─────────


@pytest.mark.parametrize(
    ("avant", "apres"),
    [
        # p. 7 du business plan ÉCLORE.
        ("Le marché se accroît de 5 % par an.", "Le marché s'accroît de 5\u00a0% par an."),
        ("Elle ne a pas encore de local.", "Elle n'a pas encore de local."),
        ("Il faut que il signe.", "Il faut qu'il signe."),
        ("Je ne le ai pas prévu.", "Je ne l'ai pas prévu."),
        ("Le financement de une partie du matériel.", "Le financement d'une partie du matériel."),
        ("Le hôtel et la histoire du lieu.", "L'hôtel et l'histoire du lieu."),
        ("Si il pleut, la séance est reportée.", "S'il pleut, la séance est reportée."),
    ],
)
def test_l_elision_manquante_est_reparee(avant: str, apres: str) -> None:
    assert reparer_texte(avant) == apres


@pytest.mark.parametrize(
    "texte",
    [
        # Le h ASPIRÉ ne s'élide pas, et aucune règle ne le distingue du muet.
        "Le haut de gamme, la hausse des prix, le héros de la marque.",
        # Le chiffre, la première page, le nombre.
        "Le un de la liste, la une du journal, le onze de départ.",
        # « ou » et « et » sont des conjonctions.
        "Le ou la bénéficiaire, de et vers la gare.",
        # Un pronom derrière un trait d'union ne s'élide pas.
        "Donne-le à la cliente.",
        # Ni celui d'un impératif qui a PERDU son trait d'union : l'élider
        # écrirait « réservez l'à l'avance », une faute pire.
        "Réservez la à l'avance et mettez la en avant.",
        # Un nom propre, un sigle : seule une minuscule est visée.
        "Le restaurant la Isla, Le Havre, de EBITDA.",
        # L'usage garde « le e-commerce ».
        "Le e-commerce pèse peu.",
        # Une phrase anglaise n'est pas une faute de français.
        "Leur slogan dit « tell me about it ».",
    ],
)
def test_ce_qui_ne_s_elide_pas_reste_intact(texte: str) -> None:
    """LA contre-épreuve : chacune de ces lignes est correcte telle quelle."""
    assert reparer_texte(texte) == texte


@pytest.mark.parametrize(
    ("avant", "apres"),
    [
        # p. 67 du business plan ÉCLORE.
        ("Le matériel est already financé par l'apport.",
         "Le matériel est déjà financé par l'apport."),
        ("La demande reste however fragile.", "La demande reste cependant fragile."),
        ("However, le projet reste rentable.", "Cependant, le projet reste rentable."),
        ("Le seuil est therefore atteint.", "Le seuil est par conséquent atteint."),
        # L'équivalent ouvre sur une voyelle : l'élision passe APRÈS.
        ("Il précise que furthermore il faut un local.",
         "Il précise qu'en outre il faut un local."),
    ],
)
def test_le_mot_anglais_sans_ambiguite_est_remplace(avant: str, apres: str) -> None:
    assert reparer_texte(avant) == apres


@pytest.mark.parametrize(
    "texte",
    [
        # Un titre de publication cité : c'est une phrase anglaise.
        "McKinsey, The market is already saturated, 2025.",
        # « Indeed » est aussi une plateforme d'emploi, citée comme source.
        "Indeed, Welcome to the Jungle et France Travail publient des offres.",
        # Une adresse porte des mots anglais légitimes.
        "Voir https://www.already.fr/tarifs pour la grille.",
        # Un mot AMBIGU ne se remplace pas : le contrôle le signale.
        "Le score overall place le projet en tête.",
    ],
)
def test_ce_qui_n_est_pas_une_fuite_anglaise_reste_intact(texte: str) -> None:
    assert reparer_texte(texte) == texte


@pytest.mark.parametrize(
    ("avant", "apres"),
    [
        ("Un marché de 12 MEUR en 2026.", "Un marché de 12\u00a0M€ en 2026."),
        ("Un marché de 16,5 MdEUR.", "Un marché de 16,5\u00a0Md€."),
        ("Un budget de 600 kEUR.", "Un budget de 600\u00a0k€."),
        ("Un marché de 3,3 M EUR.", "Un marché de 3,3\u00a0M€."),
        ("Un marché de 12MEUR.", "Un marché de 12\u00a0M€."),
        ("Montants (en MEUR)", "Montants (en M€)"),
        ("Une rémunération de 1500 EUR/mois.", "Une rémunération de 1500\u00a0€/mois."),
        ("12 000 unite vendues.", "12 000 unités vendues."),
        ("1 unite livrée.", "1 unité livrée."),
        ("Volumes (en unite)", "Volumes (en unités)"),
        ("Le prix par unite baisse.", "Le prix par unité baisse."),
        ("Le coût de l'unite baisse.", "Le coût de l'unité baisse."),
    ],
)
def test_le_code_d_unite_devient_ce_que_le_lecteur_lit(avant: str, apres: str) -> None:
    assert reparer_texte(avant) == apres


@pytest.mark.parametrize(
    "texte",
    [
        # La base du droit européen, citée dans les chapitres réglementaires.
        "Règlement consultable sur EUR-Lex.",
        # « EUR » sans nombre n'est pas un montant.
        "La parité EUR/USD reste stable.",
        # Un code nu comme USD est un usage français admis.
        "Un marché de 4 milliards USD.",
        # Le verbe anglais, dans une phrase anglaise.
        "Their motto is simple, we unite people.",
    ],
)
def test_ce_qui_n_est_pas_un_code_de_stockage_reste_intact(texte: str) -> None:
    assert reparer_texte(texte) == texte


def test_la_reparation_est_idempotente() -> None:
    """La rejouer ne change rien : un chapitre relu n'est pas réécrit."""
    texte = (
        "Le marché se accroît ; le matériel est already financé ; "
        "je ne le ai pas ; 12 MEUR et 1500 EUR/mois ; 12 000 unite."
    )
    une_fois = reparer_texte(texte)
    assert reparer_texte(une_fois) == une_fois
    assert "s'accroît" in une_fois
    assert "déjà financé" in une_fois
    assert "l'ai" in une_fois
    assert "12\u00a0M€" in une_fois
    assert "12 000 unités" in une_fois


def test_l_apostrophe_suit_celle_du_texte() -> None:
    """On ne mélange pas l'apostrophe droite et la typographique."""
    assert reparer_texte("L’offre, qu’elle dit, se accroît.") == "L’offre, qu’elle dit, s’accroît."


# ── Sur le chapitre entier, AVANT le rendu ───────────────────────────────────


def _chapitre() -> ChapitrePayload:
    return ChapitrePayload(
        chapitre=16,
        titre="Prévisionnel financier",
        accroche="Un prévisionnel already équilibré.",
        blocs=[
            BlocParagraphe(texte="Le chiffre d'affaires se accroît chaque année."),
            BlocTableau(tableau=Tableau(
                entetes=["Poste", "Montant"],
                lignes=[["Matériel", "12 MEUR"], ["Salaire", "1500 EUR/mois"]],
            )),
            BlocGrilleKpi(cellules=[
                CelluleKpi(valeur="3,3 M EUR", libelle="Chiffre d'affaires"),
                CelluleKpi(valeur="12 000 unite", libelle="Séances vendues"),
            ]),
            BlocGraphique(graphique=Graphique(
                type_graphique=TypeGraphique.BARRES,
                titre="Évolution du chiffre d'affaires",
                # Un nom de concurrent sert d'identifiant de figure : il se
                # recopie tel quel, faute comprise, ou la figure ne le trouve
                # plus.
                donnees_ids=["Atelier de hier", "ca_an1"],
            )),
        ],
        resume="Le financement est already bouclé.",
    )


def test_le_chapitre_est_repare_partout_ou_le_lecteur_lit() -> None:
    """Paragraphe, cellule de tableau, indicateur, accroche et résumé.

    L'accroche est imprimée dans le bandeau du chapitre : sur le code d'avant,
    c'était le seul texte que la réparation ne voyait pas.
    """
    payload = _chapitre()

    retouches = reparer_typographie(payload)

    assert retouches >= 6
    assert payload.accroche == "Un prévisionnel déjà équilibré."
    paragraphe, tableau, grille = payload.blocs[0], payload.blocs[1], payload.blocs[2]
    assert isinstance(paragraphe, BlocParagraphe)
    assert isinstance(tableau, BlocTableau)
    assert isinstance(grille, BlocGrilleKpi)
    assert paragraphe.texte == "Le chiffre d'affaires s'accroît chaque année."
    assert tableau.tableau.lignes == [
        ["Matériel", "12\u00a0M€"], ["Salaire", "1500\u00a0€/mois"],
    ]
    assert [c.valeur for c in grille.cellules] == ["3,3\u00a0M€", "12 000 unités"]
    assert payload.resume == "Le financement est déjà bouclé."


def test_un_identifiant_de_figure_n_est_pas_de_la_prose() -> None:
    """CONTRE-ÉPREUVE : `donnees_ids` porte des identifiants, pas des phrases.

    Le titre de la figure est réparé ; l'identifiant, lui, doit rester celui
    que la base connaît, sans quoi la figure ne se dessine plus.
    """
    payload = _chapitre()
    reparer_typographie(payload)
    figure = payload.blocs[3]
    assert isinstance(figure, BlocGraphique)
    assert figure.graphique.donnees_ids == ["Atelier de hier", "ca_an1"]


# ── Le contrôle post-rendu : ce que la réparation ne tranche pas ─────────────


def _section(corps: str, numero: int = 7, titre: str = "Analyse") -> SimpleNamespace:
    return SimpleNamespace(number=numero, title=titre, body=corps)


def test_le_mot_anglais_reste_dans_le_document_est_signale() -> None:
    """Un chapitre qui n'est pas passé par la réparation, ou un mot ambigu."""
    from generation.checks_post_rendu import detecter_mots_anglais

    trouves = detecter_mots_anglais([
        _section(
            "Le matériel est already financé. Le score overall est bon. "
            "Le reste est already payé."
        ),
    ])

    par_mot = {t.mot: t for t in trouves}
    # Un seul « overall » ne vaut pas une réécriture du chapitre depuis la
    # relecture du 29/09/2026 (`SEUIL_MOTS_ANGLAIS_AMBIGUS`) : voir
    # `test_la_langue_apres_relecture.py`.
    assert set(par_mot) == {"already"}
    # Le même mot répété est UN défaut, avec son compte.
    assert par_mot["already"].occurrences == 2
    assert "déjà" in str(par_mot["already"])
    assert "already financé" in str(par_mot["already"])
    assert par_mot["already"].chapitre == 7


def test_le_controle_ne_crie_pas_sur_de_l_anglais_legitime() -> None:
    """CONTRE-ÉPREUVE (règle 2) : un motif faux coûte une reprise payée."""
    from generation.checks_post_rendu import detecter_mots_anglais

    trouves = detecter_mots_anglais([
        _section(
            "Source : The market is already saturated (McKinsey, 2025). "
            "Voir https://www.already.fr/tarifs et overall.example.com. "
            "Indeed, LinkedIn et France Travail publient les offres. "
            "Le chiffre d'affaires progresse de 5 % par an.",
            titre="Sources et méthodologie",
        ),
    ])

    assert trouves == []


def test_le_controle_lit_la_meme_liste_que_la_reparation() -> None:
    """Règle 5 : un mot que l'un signale et que l'autre ignore ne se fermerait jamais."""
    from generation.chapitres.typographie import MOTS_ANGLAIS
    from generation.checks_post_rendu import detecter_mots_anglais

    for mot in MOTS_ANGLAIS:
        # Deux occurrences : un mot ambigu n'est signalé qu'à partir de deux.
        texte = f"Le projet est {mot} prêt ; il reste {mot} solide."
        trouves = detecter_mots_anglais([_section(texte)])
        assert [t.mot for t in trouves] == [mot], mot
        # Et ce que la réparation remplace, elle le remplace vraiment.
        repare = reparer_texte(f"Le projet est {mot} prêt.")
        assert (mot in repare) is (MOTS_ANGLAIS[mot] is None), mot


def test_le_motif_est_reparable_au_chapitre() -> None:
    """Un motif que la boucle de correction ne sait pas router part tel quel."""
    from generation.correction import _CHAPTER_LEVEL_CHECKS, _CHECK_LABELS, _priorite_check

    assert "mot_anglais" in _CHAPTER_LEVEL_CHECKS
    assert "mot_anglais" in _CHECK_LABELS
    # Le libellé dit la classe, sans montrer la faute.
    from generation.chapitres.typographie import MOTS_ANGLAIS

    assert not any(mot in _CHECK_LABELS["mot_anglais"] for mot in MOTS_ANGLAIS)
    assert _priorite_check("mot_anglais") < _priorite_check("check_inconnu")

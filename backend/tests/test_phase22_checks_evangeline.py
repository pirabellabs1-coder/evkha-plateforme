"""Phase 22 — Deux checks nouveaux, dictes par la relecture d'Evangeline.

Juillet 2026, sur les fiches inviolables :

    « PAS D'INVENTION OU D'EXTRAPOLATION DE MONTANT OU FOURCHETTE. »
    « Trésorerie de 3 328 458 € apparait a la place de 328 458 €. »
    « Fin d'annee 1 a la fois a 168 622 € et 163 672 €. »
    « Seuil de rentabilite : 122 000, 180 000 a 280 000, 205 000. »

Les tests partent tous d'un exemple qu'Evangeline a NOMME dans son retour, pas
d'un cas theorique. Contre-epreuves incluses (regle 6 du CLAUDE.md) : le check
qui bloque les fourchettes ne doit pas se declencher sur une numerotation ni
sur une date ; le chiffre contre chiffre ne doit pas confondre deux annees
distinctes du meme libelle avec une incoherence.
"""
from __future__ import annotations

import pytest

from generation.checks_evangeline import (
    Mention,
    collecter_mentions,
    compter_concurrents,
    detecter_chapitres_avortes,
    detecter_divergences,
    detecter_fourchettes,
    verifier_concurrents_dans_ec,
    verifier_piliers_strategie,
)

# ── 1. Fourchettes ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "texte",
    [
        "Le budget se situe entre 3 et 5 M€ selon les hypotheses.",
        "Le prix de la prestation est de 350-550 €.",
        "L'investissement varie de 200 000 a 300 000 € HT.",
        "Marge brute comprise entre 15 et 20 %.",
        "Tarif : 15 000-18 000 € par an.",
        "Rendement de 8 a 15 %.",
    ],
)
def test_les_fourchettes_monetaires_et_de_pourcentage_sont_detectees(texte: str) -> None:
    """Chacun de ces exemples vient du BP SYNAPSES ou de la formulation qu'elle
    interdit explicitement. Le gate doit tous les bloquer."""
    trouvees = detecter_fourchettes(chapitre_numero=5, texte=texte)

    assert trouvees, f"aucune fourchette detectee dans : {texte!r}"


@pytest.mark.parametrize(
    "texte",
    [
        # Numerotations : « chapitre 3 a 5 », « An 1 a An 5 », « pages 12 a 18 »
        "Voir les chapitres 3 a 5 pour le detail.",
        "Le previsionnel couvre An 1 a An 5.",
        "Cf. pages 12 a 18 de l'annexe.",
        # Dates
        "Ouverture prevue du 3 au 5 juillet 2026.",
        "L'etude porte sur la periode 2020 a 2025.",
        # Chiffres uniques (contre-epreuve : le check ne doit pas hurler)
        "Le chiffre d'affaires atteint 250 272 € en annee 1.",
        "La marge brute est de 35 %.",
    ],
)
def test_ni_numerotation_ni_date_ni_chiffre_unique_ne_declenche(texte: str) -> None:
    """Contre-epreuve : sans unite monetaire ni pourcentage en fin de plage, il
    n'y a pas de fourchette a proteger. Sinon on remplace un defaut par du bruit."""
    assert detecter_fourchettes(chapitre_numero=5, texte=texte) == []


# ── 2. Chiffre contre chiffre ───────────────────────────────────────────────


def _mentions_de(textes_par_chapitre: dict[int, str]) -> list[Mention]:
    """Aggrege les mentions collectees dans plusieurs chapitres factices."""
    mentions: list[Mention] = []
    for chapitre, texte in textes_par_chapitre.items():
        mentions.extend(collecter_mentions(chapitre, texte))
    return mentions


def test_le_seuil_de_rentabilite_multiple_de_synapses_est_signale() -> None:
    """Cas EXACT d'Evangeline : trois valeurs concurrentes pour le seuil."""
    divs = detecter_divergences(_mentions_de({
        6:  "Le seuil de rentabilite se situe a 122 000 €.",
        9:  "Un seuil de rentabilite de 205 000 € est atteint en annee 2.",
        12: "Le seuil de rentabilite pour ce scenario est de 180 000 €.",
    }))

    assert len(divs) == 1
    d = divs[0]
    assert d.libelle == "seuil_rentabilite"
    assert d.annee is None
    valeurs = {m.montant_base for m in d.mentions}
    assert valeurs == {122_000.0, 205_000.0, 180_000.0}


def test_la_typo_de_zero_de_la_tresorerie_synapses_est_attrapee() -> None:
    """« Une tresorerie de 3 328 458 € apparait a la place de 328 458 € »."""
    divs = detecter_divergences(_mentions_de({
        11: "La tresorerie fin annee 3 s'eleve a 328 458 €.",
        18: "La tresorerie de fin d'annee 3 est de 3 328 458 €.",
    }))

    assert len(divs) == 1
    assert divs[0].libelle == "tresorerie"
    assert divs[0].annee == 3


def test_deux_annees_distinctes_du_meme_libelle_ne_sont_pas_une_divergence() -> None:
    """Contre-epreuve : la tresorerie progresse chaque annee, c'est NORMAL.

    C'est la fonction meme du champ `annee` : discriminer les projections
    pluriannuelles legitimes d'une vraie incoherence.
    """
    divs = detecter_divergences(_mentions_de({
        12: "Tresorerie fin annee 1 : 168 622 €.",
        13: "Tresorerie fin annee 2 : 245 000 €.",
        14: "Tresorerie fin annee 3 : 328 458 €.",
    }))

    assert divs == []


def test_l_ecart_de_moins_d_un_pour_cent_est_tolere() -> None:
    """Contre-epreuve : 168 622 arrondi a 168 600 n'est pas une incoherence.

    Un arrondi typographique se produit d'un chapitre a l'autre ; le gate ne
    doit pas confondre ca avec un veritable ecart de valeur.
    """
    divs = detecter_divergences(_mentions_de({
        12: "La tresorerie fin annee 1 atteint 168 622 €.",
        14: "La tresorerie fin annee 1 est de 168 600 €.",
    }))

    assert divs == []


def test_deux_chapitres_dun_meme_libelle_avec_la_meme_valeur_ne_signalent_rien() -> None:
    """Contre-epreuve : citer plusieurs fois la meme valeur est DEMANDE par
    Evangeline (« la majorite des principaux chiffres est bien reprise »)."""
    divs = detecter_divergences(_mentions_de({
        8:  "L'apport personnel s'eleve a 180 000 €.",
        14: "Un apport personnel de 180 000 € est mobilise.",
        17: "Apport initial : 180 000 €.",
    }))

    assert divs == []


# ── 3. Ralph Wiggum : chapitre avorte ───────────────────────────────────────


def test_un_chapitre_qui_rend_moins_du_tiers_est_signale() -> None:
    """L'exemple type : cible 900 mots, rendu 60. Aujourd'hui, passe le gate."""
    corps = "Analyse succincte du projet. " * 12  # ~60 mots

    avortes = detecter_chapitres_avortes([(3, "Segmentation", corps, 900)])

    assert len(avortes) == 1
    assert avortes[0].chapitre == 3
    assert avortes[0].mots_rendus < 100


def test_un_chapitre_conforme_au_plafond_passe() -> None:
    """Contre-epreuve : au dessus du plancher, aucune alerte."""
    corps = ("Analyse detaillee du projet dans son contexte sectoriel. " * 60)

    assert detecter_chapitres_avortes([(3, "Segmentation", corps, 900)]) == []


def test_un_chapitre_sans_plafond_ne_declenche_rien() -> None:
    """Contre-epreuve : Annexes, Sources, Fiche projet n'ont pas de cible.

    Sans `max_words`, on ne peut pas juger — inventer un seuil sur ces
    chapitres transformerait ce garde-fou en generateur de faux positifs.
    """
    assert detecter_chapitres_avortes([(20, "Sources", "Court.", 0)]) == []


def test_le_message_de_divergence_liste_valeurs_et_chapitres() -> None:
    """Le motif de blocage doit etre trouvable dans le document par le lecteur
    (regle 2 du CLAUDE.md). On y met les deux valeurs et les chapitres."""
    divs = detecter_divergences(_mentions_de({
        9:  "Seuil de rentabilite de 90 000 euros.",
        12: "Seuil de rentabilite de 180 000 €.",
    }))

    resume = divs[0].resume
    assert "90 000" in resume
    assert "180 000" in resume
    assert "9" in resume and "12" in resume


# ── 4. Extensions BP : CAF, BFR, dette residuelle ───────────────────────────


def test_la_dette_residuelle_annuelle_est_verrouillee() -> None:
    """Fiche 3 : « dette residuelle par annee ». Divergences bloquantes."""
    divs = detecter_divergences(_mentions_de({
        12: "Dette residuelle fin annee 3 : 450 000 €.",
        18: "La dette residuelle en fin d'annee 3 s'eleve a 380 000 €.",
    }))

    assert len(divs) == 1
    assert divs[0].libelle == "dette_residuelle"
    assert divs[0].annee == 3


def test_la_caf_est_annuelle_pas_globale() -> None:
    """Contre-epreuve : la CAF varie chaque annee, aucune divergence sur trois
    valeurs progressives."""
    divs = detecter_divergences(_mentions_de({
        11: "CAF annee 1 : 120 000 €.",
        12: "CAF annee 2 : 145 000 €.",
        13: "CAF annee 3 : 178 000 €.",
    }))

    assert divs == []


# ── 5. Concurrents : 8 directs et 3 indirects ────────────────────────────────


def test_le_gate_bloque_si_il_manque_des_concurrents_directs() -> None:
    """La cliente : « il en faut 8 et on les garde tout le long »."""
    corps = (
        "## Concurrents directs\n\n"
        + "\n".join(f"- Acteur {i}" for i in range(1, 7))  # 6 au lieu de 8
        + "\n\n## Concurrents indirects\n\n"
        + "\n".join(f"- Substitut {i}" for i in range(1, 4))  # 3 = OK
    )

    divergents = verifier_concurrents_dans_ec([(1, corps)])

    assert len(divergents) == 1
    d = divergents[0]
    assert d.type_ == "directs"
    assert d.trouves == 6
    assert d.attendus == 8


def test_le_gate_bloque_si_trop_de_concurrents_directs() -> None:
    """L'autre borne : jamais plus de 8 non plus."""
    corps = (
        "## Concurrents directs\n\n"
        + "\n".join(f"- Acteur {i}" for i in range(1, 13))  # 12 : trop
        + "\n\n## Concurrents indirects\n\n"
        + "\n".join(f"- Substitut {i}" for i in range(1, 4))
    )

    divergents = verifier_concurrents_dans_ec([(1, corps)])

    assert any(d.type_ == "directs" and d.trouves == 12 for d in divergents)


def test_le_bon_nombre_de_concurrents_ne_declenche_rien() -> None:
    """Contre-epreuve : 8 + 3 = OK, aucun failure."""
    corps = (
        "## Concurrents directs\n\n"
        + "\n".join(f"- Acteur {i}" for i in range(1, 9))
        + "\n\n## Concurrents indirects\n\n"
        + "\n".join(f"- Substitut {i}" for i in range(1, 4))
    )

    assert verifier_concurrents_dans_ec([(1, corps)]) == []


def test_un_blueprint_sans_sous_section_concurrents_ne_leve_rien() -> None:
    """Contre-epreuve : si le chapitre n'a pas la sous-section, on ne signale
    rien plutot que d'inventer un defaut sur un contenu qui n'est pas cense
    les lister (regle 1 du CLAUDE.md dans l'autre sens : ne pas hurler sans
    donnee a comparer)."""
    corps = "## Analyse concurrentielle\n\nSynthese qualitative sans liste."

    assert verifier_concurrents_dans_ec([(1, corps)]) == []


def test_le_compte_ignore_les_lignes_qui_ne_sont_pas_des_puces() -> None:
    """Contre-epreuve : un paragraphe qui contient le mot « concurrent » ne
    doit pas etre compte comme un concurrent."""
    corps = (
        "## Concurrents directs\n\n"
        "Ce paragraphe evoque plusieurs acteurs sans les lister formellement."
    )

    assert compter_concurrents(1, corps)[0].trouves == 0


# ── 6. Piliers de la strategie ──────────────────────────────────────────────


def test_les_quatre_piliers_de_la_strategie_sont_verifies() -> None:
    """Fiche 4 : les 4 piliers sont toujours poses, dans le meme ordre."""
    corpus_complet = (
        "## Pilier 1 - Positionnement & Specialisation\n"
        "Sortir de la confusion, clarifier la direction.\n\n"
        "## Pilier 2 - Structuration de l'offre\n"
        "Organiser le catalogue pour vendre mieux.\n\n"
        "## Pilier 3 - Planning editorial du business\n"
        "Creer une presence qui attire les bons clients.\n\n"
        "## Pilier 4 - Analyse de la tarification\n"
        "Fixer les prix avec confiance.\n"
    )

    assert verifier_piliers_strategie(corpus_complet) == []


def test_le_pilier_visibilite_absent_est_signale() -> None:
    """Un pilier manquant, un signalement — les 4 sont obligatoires.

    Le pilier s'appelait « editorial » et n'acceptait que la chaine « planning
    editorial ». Or le cahier des charges « Strategies business » n'emploie
    jamais cette expression et exclut explicitement que le systeme devienne un
    calendrier editorial ; sa PARTIE IV s'intitule « VISIBILITE & ACQUISITION ».
    Le pilier accepte donc desormais les deux vocabulaires.
    """
    corpus_amputee = (
        "## Pilier 1 - Positionnement & Specialisation\n"
        "Contenu.\n\n"
        "## Pilier 2 - Structuration de l'offre\n"
        "Contenu.\n\n"
        "## Pilier 4 - Analyse de la tarification\n"
        "Contenu.\n"
    )

    manquants = verifier_piliers_strategie(corpus_amputee)

    assert len(manquants) == 1
    assert manquants[0].cle == "visibilite"


def test_une_strategie_conforme_au_cahier_des_charges_passe_les_piliers() -> None:
    """LE test du defaut : ce corpus etait BLOQUE au gate (regle 6).

    Il n'emploie que le vocabulaire du cahier des charges V1 — les intitules
    exacts de ses sept parties. L'ancienne grille exigeait « positionnement &
    specialisation », « planning editorial » et « analyse de la tarification » :
    trois piliers sur quatre echouaient, et une strategie strictement conforme a
    la specification de la cliente ne pouvait pas etre livree.
    """
    corpus_conforme = (
        "## Positionnement & differenciation\nContenu.\n\n"
        "## Structuration de l'offre\nContenu.\n\n"
        "## Visibilite & acquisition\nContenu.\n\n"
        "## Rentabilite & modele economique\nContenu.\n"
    )

    assert verifier_piliers_strategie(corpus_conforme) == []

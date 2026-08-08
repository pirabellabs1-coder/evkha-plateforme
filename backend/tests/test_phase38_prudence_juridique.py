"""Phase 38 — Prudence juridique : affirmations factuelles / diffamatoires.

Retour Evangeline WAOME EM v1 (21/07/2026) : « erreurs factuelles
graves — l'etude affirme que Maisons du Monde a ete privatise en 2023,
ce qui est factuellement faux. Un livrable diffuse sous ma marque avec
ce genre d'erreur m'expose personnellement ».

Sous contract SaaS (aucune relecture avant delivery), un livrable qui
affirme un fait faux sur un tiers, ou lui prete un evenement negatif
non source, expose EVKHA au risque juridique.

Deux categories de defaut, chacune signalee :

  1. Evenement corporate date (rachat, privatisation, faillite,
     fusion, cotation, condamnation) sur une entite tierce SANS source
     verifiable dans les 400 chars environnants → signal
     « evenement_corporate_non_source ».

  2. Formulation risquant la diffamation (« en faillite »,
     « condamne », « pratiques anticoncurrentielles ») SANS source
     verifiable → signal « diffamation_non_sourcee ».

Regle 4 (viser la classe) : on ne verifie pas la verite du fait —
c'est impossible offline. On exige juste qu'un fait sensible soit
sourcable, ce qui bloque a la fois les faits faux (le modele hallucine
et n'a pas d'URL) et les faits vrais mal argumentes.
"""
from __future__ import annotations

from generation.checks_post_rendu import detecter_prudence_juridique

# ══════════════════════════════════════════════════════════════════════════
# 1. Evenement corporate date non source
# ══════════════════════════════════════════════════════════════════════════


def test_privatisation_datee_sans_source_est_signalee() -> None:
    """Cas WAOME exact : « Maisons du Monde privatisation 2023 » sans
    URL adjacente. Peu importe si le fait est vrai ou faux — sans
    source, on refuse."""
    corpus = {
        6: "Maisons du Monde a ete privatise en 2023, ce qui a "
           "reconfigure le paysage concurrentiel de l'ameublement.",
    }
    problemes = detecter_prudence_juridique(corpus)

    assert len(problemes) >= 1
    assert problemes[0].chapitre == 6
    assert "privatis" in problemes[0].expression.lower()


def test_rachat_avec_url_adjacente_est_accepte() -> None:
    """Contre-epreuve : la meme affirmation SOURCEE passe. La regle
    n'est pas d'interdire l'evenement, c'est d'exiger une source."""
    corpus = {
        6: "Maisons du Monde a ete privatise en 2023 selon Les Echos "
           "(https://www.lesechos.fr/entreprises/services/maisons-du-monde).",
    }
    assert detecter_prudence_juridique(corpus) == []


def test_faillite_datee_sans_source_est_signalee() -> None:
    """Cas grave (diffamation) : « X en faillite en 2024 » non source
    est le pire scenario — fait sensible sans preuve."""
    corpus = {
        4: "Bricolex a fait faillite en 2024, laissant un vide sur le "
           "marche du bricolage de proximite.",
    }
    problemes = detecter_prudence_juridique(corpus)
    assert len(problemes) >= 1


def test_fusion_datee_sans_source_est_signalee() -> None:
    """Fusion, acquisition, cotation, delisting — meme regle."""
    corpus = {
        3: "Le groupe Alpha a fusionne avec Beta en 2022 pour former "
           "Gamma, nouveau leader du secteur.",
    }
    problemes = detecter_prudence_juridique(corpus)
    assert len(problemes) >= 1


# ══════════════════════════════════════════════════════════════════════════
# 2. Diffamation potentielle
# ══════════════════════════════════════════════════════════════════════════


def test_condamnation_sans_source_est_signalee() -> None:
    """Attribuer une condamnation a un tiers sans source = diffamation."""
    corpus = {
        7: "Le concurrent XYZ a ete condamne pour pratiques "
           "anticoncurrentielles par l'Autorite de la concurrence.",
    }
    problemes = detecter_prudence_juridique(corpus)
    assert len(problemes) >= 1
    # Le detail doit qualifier le risque juridique.
    assert "source" in problemes[0].detail.lower() or \
           "juridique" in problemes[0].detail.lower()


def test_abus_position_dominante_sans_source_est_signale() -> None:
    """Meme risque de diffamation."""
    corpus = {
        7: "L'operateur historique exerce un abus de position dominante "
           "sur le segment premium du marche.",
    }
    problemes = detecter_prudence_juridique(corpus)
    assert len(problemes) >= 1


def test_condamnation_avec_url_reste_accepte() -> None:
    """Contre-epreuve : condamnation sourcée passe (fait public)."""
    corpus = {
        7: "Le concurrent XYZ a ete condamne pour pratiques "
           "anticoncurrentielles selon la decision de l'Autorite "
           "(https://www.autoritedelaconcurrence.fr/decision-12-D-34).",
    }
    assert detecter_prudence_juridique(corpus) == []


# ══════════════════════════════════════════════════════════════════════════
# 3. Contre-epreuves — descriptif neutre
# ══════════════════════════════════════════════════════════════════════════


def test_description_neutre_ne_signale_rien() -> None:
    """Un texte descriptif sans evenement date ni accusation passe."""
    corpus = {
        3: "Le marche du coworking a Lyon pese 12 M€ en 2024, en "
           "croissance de 8 % par an. Trois acteurs principaux se "
           "partagent 60 % de la valeur.",
    }
    assert detecter_prudence_juridique(corpus) == []


def test_evenement_sans_date_ne_signale_rien() -> None:
    """« La societe a ete rachetee » sans date reste generique — pas
    d'affirmation factuelle precise a verifier."""
    corpus = {
        3: "Le groupe historique a ete rachete plusieurs fois au cours "
           "des dernieres decennies, temoignant d'une consolidation "
           "progressive du secteur.",
    }
    assert detecter_prudence_juridique(corpus) == []


def test_chapitre_sources_est_exempte() -> None:
    """Le chapitre Sources cite des titres externes — pas de check."""
    corpus = {
        22: "## Faillites recentes\n- Etude XYZ, « X en faillite 2024 » "
            "(titre externe).",
    }
    problemes = detecter_prudence_juridique(
        corpus,
        titres_par_chapitre={22: "Sources et methodologie"},
    )
    assert problemes == []

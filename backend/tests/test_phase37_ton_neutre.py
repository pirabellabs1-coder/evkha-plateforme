"""Phase 37 — Ton neutre : bannir les superlatifs marketing.

Retour Evangeline WAOME EM v1 (21/07/2026) : « le ton est trop
publicitaire, on lit du plaquette commerciale ("leader incontestable",
"solution unique en son genre", "revolutionnaire") alors qu'un livrable
bancaire doit rester descriptif et sourcé ».

Un banquier disqualifie un dossier qui vend au lieu de decrire — le ton
publicitaire signale un contenu non verifie, gonfle pour convaincre.

Regle 4 : ce check est transverse (tous les livrables doivent rester
neutres). Il vit donc dans `checks_post_rendu.py`.

Une seule categorie de defaut, mais on veut :
  - un signal precis (mot fautif, chapitre, extrait) pour l'operateur ;
  - une tolerance minimale (les mots dans le chapitre Sources ou en
    citation directe restent legitimes) ;
  - une liste noire calibree pour ne pas mordre sur « leader » utilise
    factuellement (« Leroy Merlin, leader du bricolage »).
"""
from __future__ import annotations

from generation.checks_post_rendu import detecter_ton_publicitaire

# ══════════════════════════════════════════════════════════════════════════
# 1. Superlatifs marketing → signal
# ══════════════════════════════════════════════════════════════════════════


def test_leader_incontestable_est_signale() -> None:
    """Cas WAOME : « leader incontestable » = qualificatif non
    verifiable, ton publicitaire."""
    corpus = {
        3: "Le porteur devient le leader incontestable de son marche des la premiere annee.",
    }
    problemes = detecter_ton_publicitaire(corpus)

    assert len(problemes) >= 1
    assert problemes[0].chapitre == 3
    assert "leader incontestable" in problemes[0].expression.lower()


def test_solution_revolutionnaire_est_signalee() -> None:
    """« Revolutionnaire » sans reference technique = superlatif vide."""
    corpus = {
        5: "Ce concept revolutionnaire va transformer le marche du coworking.",
    }
    problemes = detecter_ton_publicitaire(corpus)

    assert any(p.expression.lower().startswith("revolutionnaire")
               or "revolutionnaire" in p.expression.lower()
               for p in problemes)


def test_unique_en_son_genre_est_signale() -> None:
    """Formulation type plaquette."""
    corpus = {7: "Une offre unique en son genre sur le territoire."}
    problemes = detecter_ton_publicitaire(corpus)
    assert any("unique en son genre" in p.expression.lower() for p in problemes)


def test_positionnement_incontournable_est_signale() -> None:
    """« Incontournable » = superlatif marketing frequent chez le modele."""
    corpus = {2: "Le projet occupe un positionnement incontournable sur son segment."}
    problemes = detecter_ton_publicitaire(corpus)
    assert len(problemes) >= 1


# ══════════════════════════════════════════════════════════════════════════
# 2. Contre-epreuves — legitimite factuelle
# ══════════════════════════════════════════════════════════════════════════


def test_leader_avec_source_chiffree_reste_accepte() -> None:
    """« Leader » utilise avec un chiffre de part de marche est une
    description factuelle, pas un superlatif. La blackliste ne doit PAS
    mordre — regle 4, viser la classe."""
    corpus = {
        3: "Leroy Merlin est le leader du bricolage en France avec 22 % "
           "de part de marche (Xerfi 2024).",
    }
    problemes = detecter_ton_publicitaire(corpus)
    # « leader du bricolage » n'est pas dans la blackliste stricte
    # (leader + qualificatif emphatique).
    assert problemes == []


def test_ton_descriptif_ne_signale_rien() -> None:
    """Contre-epreuve : texte purement descriptif passe."""
    corpus = {
        4: "Le marche du coworking a Lyon pese 12 M€ en 2024, en croissance "
           "de 8 % par an sur les cinq dernieres annees (Xerfi 2024).",
    }
    assert detecter_ton_publicitaire(corpus) == []


def test_chapitre_sources_est_exempte() -> None:
    """Une phrase dans le chapitre Sources ou methodologique n'est PAS
    du corpus editorial : elle liste des references, on n'y applique
    pas le check ton. Le titre commence par « Sources »."""
    corpus_par_chapitre = {
        22: "## Sources\n- Etude XYZ, « leader incontestable du secteur » (titre reel).",
    }
    problemes = detecter_ton_publicitaire(
        corpus_par_chapitre,
        titres_par_chapitre={22: "Sources et methodologie"},
    )
    assert problemes == []

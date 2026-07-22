"""Phase 39 — BP tresorerie cumulee reconstituable.

Retour Evangeline WAOME EM v1 (21/07/2026) : « la tresorerie
prevue en fin d'annee 2 (58 kEUR) et fin d'annee 3 (185 kEUR)
n'est pas reconstituable — la variation n'a pas de source
identifiable, ni CAF, ni remboursements, ni variation BFR ».

Un banquier reconstitue mentalement : treso[N] = treso[N-1] + CAF -
remboursements + variation BFR. Sans ces composantes, il refuse le
dossier — le previsionnel est declaratif, pas argumente.

Regle 4 (viser la classe) : ce check est structurel pour tout BP
avec previsionnel. Il vit dans `strategies/bp.py`.

On ne fait PAS le calcul arithmetique (les valeurs peuvent etre
approximees ou sur plusieurs annees) — on verifie qu'on mentionne
au moins UNE des trois composantes dans le corpus si on annonce
des tresoreries annuelles.
"""
from __future__ import annotations

from generation.strategies.bp import verifier_tresorerie_reconstituable


def test_tresorerie_annoncee_sans_composantes_est_signalee() -> None:
    """Cas WAOME : deux tresoreries annuelles, aucune mention de CAF,
    remboursements ou variation BFR."""
    corpus = {
        14: (
            "Le previsionnel financier fait ressortir une tresorerie fin "
            "d'annee 1 de 12 000 EUR, fin d'annee 2 de 58 000 EUR et fin "
            "d'annee 3 de 185 000 EUR. Cette progression accompagne la "
            "montee en charge commerciale du projet."
        ),
    }
    problemes = verifier_tresorerie_reconstituable(corpus)

    assert len(problemes) == 1
    assert "reconstituable" in problemes[0].lower() or "caf" in problemes[0].lower()


def test_tresorerie_avec_caf_passe() -> None:
    """Contre-epreuve : CAF mentionnee → le lecteur peut reconstituer."""
    corpus = {
        14: (
            "Le previsionnel prevoit une CAF de 45 kEUR en annee 1, "
            "70 kEUR en annee 2 et 130 kEUR en annee 3. La tresorerie "
            "cumulee s'etablit a 12 kEUR fin annee 1, 58 kEUR fin annee "
            "2 et 185 kEUR fin annee 3 apres remboursements du pret."
        ),
    }
    assert verifier_tresorerie_reconstituable(corpus) == []


def test_tresorerie_avec_variation_bfr_passe() -> None:
    """Contre-epreuve : variation BFR expliquée → reconstituable."""
    corpus = {
        14: (
            "La tresorerie cumulee atteint 12 kEUR, 58 kEUR et 185 kEUR "
            "sur les trois premieres annees. La variation du BFR est "
            "contenue grace au delai clients court (paiement comptant)."
        ),
    }
    assert verifier_tresorerie_reconstituable(corpus) == []


def test_tresorerie_avec_remboursements_passe() -> None:
    """Contre-epreuve : mention des remboursements de pret."""
    corpus = {
        14: (
            "Tresorerie fin annee 1 : 12 kEUR. Fin annee 2 : 58 kEUR. "
            "Fin annee 3 : 185 kEUR. Les remboursements du pret bancaire "
            "s'elevent a 12 kEUR par an (annuite constante)."
        ),
    }
    assert verifier_tresorerie_reconstituable(corpus) == []


def test_bp_sans_mention_de_tresorerie_ne_signale_rien() -> None:
    """Contre-epreuve : si le previsionnel ne parle pas de tresorerie
    annuelle, on n'attend pas la reconstitution — silence (regle 4 :
    eviter les faux positifs sur un blueprint minimaliste)."""
    corpus = {
        14: (
            "Le previsionnel retient un chiffre d'affaires de 250 000 EUR "
            "et une marge brute de 40 %. La remuneration dirigeante est "
            "de 30 000 EUR annuelle brute."
        ),
    }
    assert verifier_tresorerie_reconstituable(corpus) == []


def test_une_seule_tresorerie_annuelle_ne_signale_pas() -> None:
    """Une seule valeur = pas de progression a reconstituer. Regle 4 :
    on ne mord que si le BP DECLARE une trajectoire (>= 2 annees)."""
    corpus = {
        14: (
            "La tresorerie de fin d'annee 1 s'etablit a 12 kEUR."
        ),
    }
    assert verifier_tresorerie_reconstituable(corpus) == []


def test_strategy_bp_remonte_le_probleme() -> None:
    """Integration : la BPStrategy remonte le probleme via
    problemes_de_coherence, categorie tresorerie_non_reconstituable."""
    from generation.strategies.bp import BPStrategy

    corpus = {
        14: (
            "Le previsionnel integre une remuneration dirigeante de "
            "30 000 EUR annuelle. La tresorerie cumulee ressort a "
            "12 kEUR, 58 kEUR et 185 kEUR sur trois ans."
        ),
    }
    problemes = BPStrategy().problemes_de_coherence(None, corpus)  # type: ignore[arg-type]

    categories = {p.categorie for p in problemes}
    assert "tresorerie_non_reconstituable" in categories

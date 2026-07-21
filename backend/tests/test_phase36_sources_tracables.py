"""Phase 36 — Sources tracables : chaque source citee doit etre verifiable.

Retour Evangeline sur WAOME EM v1 (21/07/2026), extrait des defauts
« sources » :

  - « Les sources listees dans le chapitre 22 ne sont pas verifiables :
     plusieurs manquent d'URL, certaines pointent vers des pages
     inexistantes, une reference "Maisons du Monde privatisation 2023"
     est factuellement fausse. »

Contrainte SaaS (contract Tobias) : personne ne relit avant delivery.
Un livrable rempli de sources bidon sort tel quel chez le client. Le
gate doit refuser un tel document.

Regle 4 : ce check est transverse (tous les livrables ont un chapitre
Sources) — il vit dans `checks_post_rendu.py` avec les autres checks
transverses, pas dans une strategy par livrable.

Trois signaux distincts :
  1. Chapitre Sources absent ou vide → livrable non source du tout.
  2. Ratio URLs / puces < 50 % → majorite non tracable.
  3. URLs manifestement bidon (example.com, source.fr, placeholder) →
     hallucination de source, cas WAOME.

Tous les tests partent de patterns qu'un modele peut ecrire (URL
fabriquee) ou d'un cas WAOME reel (source sans URL).
"""
from __future__ import annotations

from generation.checks_post_rendu import detecter_sources_non_tracables


# ══════════════════════════════════════════════════════════════════════════
# 1. Chapitre Sources present et bien rempli
# ══════════════════════════════════════════════════════════════════════════


def test_chapitre_sources_avec_urls_reelles_passe() -> None:
    """Contre-epreuve : 5 puces, 5 URLs valides → aucun probleme."""
    corps = (
        "## Marche\n"
        "- INSEE, Enquete emploi 2024 - https://www.insee.fr/fr/statistiques/1234\n"
        "- Xerfi, Etude sectorielle 2025 - https://www.xerfi.com/etude-x\n"
        "## Reglementation\n"
        "- Legifrance, art. 219 CGI - https://www.legifrance.gouv.fr/codes/id/1\n"
        "- Ministere Economie - https://www.economie.gouv.fr/pme\n"
        "- Bpifrance - https://www.bpifrance.fr/actualites/y\n"
    )
    problemes = detecter_sources_non_tracables(
        [(22, "Sources et methodologie", corps)]
    )
    assert problemes == []


def test_chapitre_sources_absent_est_signale() -> None:
    """Un document sans chapitre Sources est un livrable non source."""
    problemes = detecter_sources_non_tracables(
        [(1, "Analyse marche", "Le marche pese 1,2 Md€ en 2024.")]
    )
    assert len(problemes) == 1
    assert "sources" in problemes[0].detail.lower()


def test_chapitre_sources_vide_est_signale() -> None:
    """Le chapitre existe mais ne liste rien."""
    problemes = detecter_sources_non_tracables(
        [(22, "Sources et methodologie", "\n\n")]
    )
    assert len(problemes) == 1


# ══════════════════════════════════════════════════════════════════════════
# 2. URLs presentes vs sources qualitatives sans lien
# ══════════════════════════════════════════════════════════════════════════


def test_sources_majoritairement_sans_url_est_signale() -> None:
    """Cas WAOME : la moitie des sources n'ont pas d'URL, donc pas
    verifiables. Un banquier ne peut rien en faire."""
    corps = (
        "## Marche\n"
        "- INSEE 2024\n"
        "- Xerfi 2025\n"
        "- Etude sectorielle Precepta\n"
        "- Rapport ministeriel 2023\n"
        "- Une seule URL - https://www.insee.fr/x\n"
    )
    problemes = detecter_sources_non_tracables(
        [(22, "Sources", corps)]
    )
    assert len(problemes) == 1
    # Le detail doit expliquer POURQUOI (ratio) pour que l'operateur
    # sache quoi corriger.
    assert "url" in problemes[0].detail.lower() or "ratio" in problemes[0].detail.lower()


def test_document_client_sans_url_ne_declenche_pas_seul() -> None:
    """Un doc client (fichier xlsx transmis par le porteur) n'a
    legitimement PAS d'URL — tant que la majorite des autres sources
    en a, on accepte. Regle 4 : eviter les faux positifs qui
    obligeraient a inventer une URL."""
    corps = (
        "## Marche\n"
        "- INSEE 2024 - https://www.insee.fr/x\n"
        "- Xerfi 2025 - https://www.xerfi.com/y\n"
        "- Bpifrance 2024 - https://www.bpifrance.fr/z\n"
        "## Documents client\n"
        "- Fichier previsions.xlsx transmis par le porteur\n"
    )
    assert detecter_sources_non_tracables(
        [(22, "Sources", corps)]
    ) == []


# ══════════════════════════════════════════════════════════════════════════
# 3. URLs manifestement bidon
# ══════════════════════════════════════════════════════════════════════════


def test_urls_example_com_sont_signalees() -> None:
    """example.com/org/fr sont des domaines RFC 2606 reserves aux
    exemples — jamais une vraie source. Cas frequent d'hallucination."""
    corps = (
        "## Marche\n"
        "- INSEE 2024 - https://www.example.com/insee\n"
        "- Etude - https://example.fr/etude\n"
        "- Ministere - https://www.economie.gouv.fr/pme\n"
    )
    problemes = detecter_sources_non_tracables(
        [(22, "Sources", corps)]
    )
    assert len(problemes) >= 1
    details = " ".join(p.detail.lower() for p in problemes)
    assert "example" in details or "bidon" in details or "placeholder" in details


def test_url_source_fr_est_signalee() -> None:
    """« www.source.fr » : URL placeholder inventee, pas un vrai
    editeur. Cas WAOME (« reference generique sans lien reel »)."""
    corps = (
        "## Marche\n"
        "- Rapport source - https://www.source.fr/rapport-2024\n"
        "- INSEE - https://www.insee.fr/x\n"
        "- Xerfi - https://www.xerfi.com/y\n"
    )
    problemes = detecter_sources_non_tracables(
        [(22, "Sources", corps)]
    )
    assert len(problemes) >= 1


def test_url_placeholder_est_signalee() -> None:
    """« www.[nom-editeur].com » avec crochets = pattern non substitue."""
    corps = (
        "## Marche\n"
        "- INSEE - https://www.[insee-url].fr/x\n"
        "- Xerfi - https://www.xerfi.com/y\n"
        "- Ministere - https://www.economie.gouv.fr/pme\n"
    )
    problemes = detecter_sources_non_tracables(
        [(22, "Sources", corps)]
    )
    assert len(problemes) >= 1


# ══════════════════════════════════════════════════════════════════════════
# 4. Detection du chapitre Sources par titre
# ══════════════════════════════════════════════════════════════════════════


def test_chapitre_sources_reconnu_par_titre_variant() -> None:
    """Blueprints EM/EC/BP/STR nomment le chapitre « Sources et
    methodologie » — variantes acceptees pour ne pas rater le check si
    un blueprint change legerement (« Sources », « Sources et
    references », etc.)."""
    corps_ok = (
        "- INSEE - https://www.insee.fr/x\n"
        "- Xerfi - https://www.xerfi.com/y\n"
        "- Bpifrance - https://www.bpifrance.fr/z\n"
    )
    # Trois libelles possibles rencontres dans les blueprints ou plausibles.
    for titre in ("Sources et methodologie", "Sources", "Sources et references"):
        assert detecter_sources_non_tracables(
            [(20, titre, corps_ok)]
        ) == []

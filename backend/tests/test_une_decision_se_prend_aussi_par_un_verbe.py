"""Une décision de stratégie se prend aussi par un verbe — et le chapitre porteur la reçoit.

## Le défaut mesuré

14/09/2026, corpus de production : `decision_absente` sur les DOUZE stratégies,
40 motifs. Relus dans les fichiers Word livrés, la plupart étaient faux :

    « Nous excluons Facebook Ads, Google Ads et les flyers non ciblés »
        → « le document ne pose nulle part les canaux à éviter »

Le contrôle attendait une locution collée (« canaux à éviter »), le document
décidait comme un consultant écrit. Et le contrôleur final réécrivait — donc
payait — les chapitres 8, 10 et 13 sans jamais fermer ces motifs (`a678b10a`).

L'autre moitié de la cause était dans les prompts : le chapitre 13 ne
demandait ni les canaux à éviter ni la fréquence de publication — il disait
même que « la fréquence se déduit du tableau » — et le chapitre 17 demandait
des horizons (0-3 mois, 3-12 mois) que la déclaration ne reconnaît pas.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from generation.checks_evangeline import DECISIONS_STRATEGIE, verifier_decisions_strategie


def _manquantes(texte: str) -> set[str]:
    return {m.libelle for m in verifier_decisions_strategie(texte)}


# ── Phrases RÉELLES, relevées dans les Word du corpus (règle 7) ─────────────


@pytest.mark.parametrize(("dossier", "phrase", "libelle"), [
    ("a678b10a", "Nous excluons Facebook Ads, Google Ads et les flyers non ciblés tant "
     "que le seuil de 30 abonnés locaux n'est pas atteint.", "les canaux à éviter"),
    ("db228221", "Toute action publicitaire (Facebook, Google) est reportée tant qu'un "
     "message et un ciblage écrits ne sont pas validés.", "les canaux à éviter"),
    ("db0d9508", "Nous reportons Facebook, Meta Ads, Google Ads et le développement "
     "national tant que la marge contributive reste négative.", "les canaux à éviter"),
    ("db0d9508", "Abandonnez tout canal n'ayant produit aucun contact qualifié après "
     "90 jours.", "les canaux à éviter"),
    ("f7f2fad9", "Le rythme retenu est volontairement resserré : deux publications par "
     "semaine sur les canaux prioritaires.", "la fréquence de publication"),
    ("655b0908", "Ce qui se réutilise d'un mois sur l'autre : la structure en deux "
     "publications hebdomadaires.", "la fréquence de publication"),
    ("c9aec835", "Ces canaux sont classés secondaires : cohérents avec le "
     "positionnement de proximité.", "les canaux secondaires"),
    ("655b0908", "Décision : nous resserrons le positionnement sur l'ancrage local et "
     "régional en priorité.", "le positionnement retenu"),
    ("655b0908", "Choisir la cible prioritaire et le palier à pousser en premier.",
     "le produit ou service à pousser en priorité"),
    ("db0d9508", "La formule Full à 29 € par mois reste en portefeuille mais son "
     "développement commercial actif est suspendu.",
     "les offres à conserver, modifier, supprimer ou reporter"),
])
def test_la_decision_ecrite_par_le_document_est_reconnue(
    dossier: str, phrase: str, libelle: str,
) -> None:
    assert libelle not in _manquantes(phrase), dossier


# ── Contre-épreuves : ce qui ne décide rien reste signalé (règle 6) ─────────


@pytest.mark.parametrize(("phrase", "libelle"), [
    # Phrases réelles, qui parlent de canaux sans en écarter aucun.
    ("Ce tableau exclut volontairement des indicateurs plus sophistiqués — coût "
     "d'acquisition par canal détaillé.", "les canaux à éviter"),
    ("Aucun canal n'est testé jusqu'à son seuil de rentabilité, donc aucun n'est "
     "validé ni écarté.", "les canaux à éviter"),
    ("Impossible de savoir aujourd'hui quel canal mérite d'être renforcé ou "
     "abandonné.", "les canaux à éviter"),
    ("Le canal n'est pas écarté.", "les canaux à éviter"),
    ("Reportez-vous au chapitre 12 pour le diagnostic des canaux.", "les canaux à éviter"),
    # Une cadence de prospection n'est pas une fréquence de publication.
    ("Contacter 10 anciens clients DIBITEK par semaine, avec un script dédié.",
     "la fréquence de publication"),
    # « prioritaire » qualifie la cible, pas la formule.
    ("Clarifier la cible prioritaire et le contenu exact de chaque formule.",
     "le produit ou service à pousser en priorité"),
    ("Recrutement d'un second technicien, plateforme nationale.", "les canaux secondaires"),
    ("Le positionnement actuel reste flou.", "le positionnement retenu"),
])
def test_ce_qui_ne_decide_rien_reste_signale(phrase: str, libelle: str) -> None:
    assert libelle in _manquantes(phrase)


# ── Une seule déclaration, trois lecteurs (règle 5) ─────────────────────────


def test_chaque_etiquette_satisfait_son_propre_controle() -> None:
    """L'intitulé que la consigne fait écrire EST reconnu par le contrôle.

    Sans ce test, on pourrait demander « Canaux à proscrire » et contrôler
    « canaux à éviter » : la contradiction qui a coûté 40 motifs.
    """
    fautes = [
        d.libelle
        for bloc in DECISIONS_STRATEGIE
        for d in bloc.decisions
        if d.motif and d.libelle in _manquantes(
            f"| {d.etiquette} | Facebook Ads, retenu | la raison |"
        )
    ]
    assert fautes == []


def test_chaque_decision_verrouillee_porte_une_etiquette() -> None:
    sans = [
        d.libelle
        for b in DECISIONS_STRATEGIE
        for d in b.decisions
        if d.motif and not d.etiquette
    ]
    assert sans == []


def _job(livrable: str) -> Any:
    """Le bloc ne lit que le type de livrable : pas besoin de base."""
    return SimpleNamespace(deliverable_type=livrable)


def test_le_chapitre_porteur_recoit_ses_decisions_sous_leur_intitule() -> None:
    from generation.chapitres.runner import _bloc_decisions

    job = _job("business_strategy")
    for bloc in DECISIONS_STRATEGIE:
        consigne = _bloc_decisions(job, bloc.chapitre_porteur)
        if not bloc.tableau_de_decisions:
            continue
        for d in bloc.decisions:
            assert f"- {d.etiquette or d.libelle}\n" in consigne + "\n", d.libelle

    assert _bloc_decisions(job, 5) == "", "un chapitre sans pilier ne reçoit rien"
    autre = _job("business_plan")
    assert _bloc_decisions(autre, 13) == "", "hors stratégie, aucune décision STR"


def test_la_feuille_de_route_demande_les_horizons_que_le_controle_reconnait() -> None:
    """Chapitre 17 : « 0-3 mois / 3-12 mois » contre « 30, 60, 90 jours ; 6 et 12 mois »."""
    from generation.chapitres.configuration import RACINE_PROMPTS

    texte = (RACINE_PROMPTS / "strategie_business" / "chapitre_17.md").read_text(encoding="utf-8")
    assert "0-3 mois" not in texte
    feuille = next(b for b in DECISIONS_STRATEGIE if b.cle == "feuille_de_route")
    for d in feuille.decisions:
        if d.motif:
            assert d.libelle not in _manquantes(texte), d.libelle


def test_le_chapitre_13_ne_laisse_plus_la_frequence_a_deduire() -> None:
    from generation.chapitres.configuration import RACINE_PROMPTS

    texte = (RACINE_PROMPTS / "strategie_business" / "chapitre_13.md").read_text(encoding="utf-8")
    assert "se déduit du tableau" not in texte


# ── Relecture du 14/09/2026 : un verbe nié, ou porté par un tiers, ne décide rien ──


@pytest.mark.parametrize(("phrase", "libelle"), [
    ("Nous n'excluons aucun canal à ce stade.", "les canaux à éviter"),
    ("Aucun canal n'est à exclure à ce stade.", "les canaux à éviter"),
    ("Il n'y a pas de canal à éviter.", "les canaux à éviter"),
    ("Aucun réseau n'est encore exclu.", "les canaux à éviter"),
    ("Les campagnes Google Ads sont souvent reportées par les TPE du secteur.",
     "les canaux à éviter"),
    ("Évitez les erreurs de facturation, puis lancez la campagne Instagram.",
     "les canaux à éviter"),
    ("La radio est déconseillée par certains experts, mais nous ne tranchons pas.",
     "les canaux à éviter"),
    ("Les effets secondaires de la publicité sont mal connus.", "les canaux secondaires"),
    ("Dans ce secteur, la radio reste un média secondaire selon Médiamétrie.",
     "les canaux secondaires"),
    ("Dans un second temps, nous présenterons les segments du marché.", "la cible secondaire"),
    ("Nous ne retenons aucun positionnement tant que l'enquête n'est pas faite.",
     "le positionnement retenu"),
    ("Nous ne positionnons pas encore l'offre.", "le positionnement retenu"),
    ("Les offres du marché sont maintenues à des prix élevés.",
     "les offres à conserver, modifier, supprimer ou reporter"),
    ("Nous ne conservons aucune donnée sur les offres.",
     "les offres à conserver, modifier, supprimer ou reporter"),
    ("Les concurrents publient une vidéo par semaine en moyenne.", "la fréquence de publication"),
    ("Une newsletter mensuelle existe chez le concurrent B.", "la fréquence de publication"),
])
def test_un_verbe_nie_ou_porte_par_un_tiers_ne_decide_rien(phrase: str, libelle: str) -> None:
    assert libelle in _manquantes(phrase)


@pytest.mark.parametrize(("phrase", "libelle"), [
    ("Nous excluons TikTok et LinkedIn.", "les canaux à éviter"),
    ("Instagram est exclu.", "les canaux à éviter"),
    ("On exclut Facebook Ads.", "les canaux à éviter"),
    ("Publier trois fois par semaine sur Instagram.", "la fréquence de publication"),
])
def test_une_plateforme_nommee_est_un_canal(phrase: str, libelle: str) -> None:
    assert libelle not in _manquantes(phrase)


@pytest.mark.parametrize("case", [
    "", "—", "À définir", "Non tranchée.", "Le dossier ne permet pas de trancher.",
    "Données insuffisantes", "À préciser avec le dirigeant",
])
def test_une_etiquette_sans_decision_dans_sa_case_reste_signalee(case: str) -> None:
    """L'étiquette seule ne décide rien : la case « Ce qui est retenu » juge (règle 9)."""
    ligne = f"| Canaux à éviter | {case} | Il manque le coût par contact. |"
    assert "les canaux à éviter" in _manquantes(ligne)


def test_la_consigne_du_tableau_ne_permet_pas_de_laisser_la_case_ouverte() -> None:
    """La consigne STR dit « tu tranches quand même » : le tableau ne dit plus l'inverse."""
    from generation.chapitres.runner import _bloc_decisions

    consigne = _bloc_decisions(_job("business_strategy"), 13)
    assert "décision reportée" not in consigne
    assert "tranche quand même" in consigne


# ── Au singulier (14/09/2026) ────────────────────────────────────────────────


@pytest.mark.parametrize(("phrase", "libelle"), [
    ("Le blog reste un canal secondaire, alimenté une fois par mois.", "les canaux secondaires"),
    ("LinkedIn est le canal prioritaire de la phase 1.", "les canaux prioritaires"),
    ("Le salon local est un levier d'appoint pour la notoriété.", "les canaux secondaires"),
])
def test_un_canal_au_singulier_est_une_decision(phrase: str, libelle: str) -> None:
    assert libelle not in _manquantes(phrase)


def test_un_canal_qu_on_ne_classe_pas_reste_signale() -> None:
    """CONTRE-ÉPREUVE : nommer un canal n'est pas le classer."""
    assert "les canaux secondaires" in _manquantes("Le blog est un canal utile.")


# ── Un classement de canaux en tableau (corpus-20260914-1904) ────────────────


_CANAUX_EN_TABLEAU = """## 13.1 Canaux prioritaires à développer

Ce tableau hiérarchise les canaux selon leur coût en temps.

| Action | Priorité | Justification | Décision |
| --- | --- | --- | --- |
| Partenariats avec les pharmacies | Prioritaire | Prescription de proximité | Activer au mois 1 |
| Campagnes e-mail vers anciens clients | Secondaire, phase 2 | Fichier à nettoyer | Mois 4 |
"""


def test_un_canal_classe_secondaire_en_tableau_est_une_decision() -> None:
    """Stratégie `f7f2fad9` : la ligne du canal porte « Secondaire, phase 2 »."""
    assert "les canaux secondaires" not in _manquantes(_CANAUX_EN_TABLEAU)


def test_un_classement_hors_tableau_de_canaux_ou_en_en_tete_reste_signale() -> None:
    """CONTRE-ÉPREUVE : un tableau de CIBLES, et un « Secondaire » d'en-tête."""
    cibles = """## 8.2 Cibles

| Profil | Rang | Motif |
| --- | --- | --- |
| Seniors isolés | Secondaire | Budget contraint |
"""
    assert "les canaux secondaires" in _manquantes(cibles)
    en_tete = """## 13.1 Canaux

| Canal | Secondaire | Prioritaire |
| --- | --- | --- |
| Blog | non | non |
"""
    assert "les canaux secondaires" in _manquantes(en_tete)

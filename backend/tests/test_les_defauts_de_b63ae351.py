"""Business plan `b63ae351` (22/11/2026), reprise de `29d59ae9` sans envoi.

Quatre classes, lues dans le document livré :

1. une plage sur une valeur que personne n'a donnée (« de l'ordre de 75 à 80 %
   du net selon les barèmes URSSAF ») : la consigne et le motif de réparation
   exigeaient de trancher, sans dire quoi faire quand rien ne permet de le
   faire — la réécriture du chapitre a gardé la plage ;
2. « le résultat net 2027 vaut 0 € » : le calendrier de rémunération attribué
   au résultat net, nommé seulement comme condition (« un résultat net
   positif ») ;
3. « 395 000 000 » en « objet changé » trois fois, pour une seule population
   nommée par trois de ses mots ;
4. « ramp commercial », et derrière lui une classe d'anglicismes mesurée sur
   les huit business plans du 14 au 22/11.
"""
from __future__ import annotations

from pathlib import Path

from generation.chapitres.runner import COHERENCE_DES_CHIFFRES
from generation.chapitres.typographie import jargon
from generation.correction import _CHECK_LABELS
from generation.relecture import Section
from generation.relecture.document import Document
from generation.relecture.valeurs import valeurs_datees
from generation.verification.lecture import DocumentLu
from generation.verification.objet_des_chiffres import controler_objet_des_chiffres

# ── 1. Une valeur absente ne se remplace pas par deux bornes ─────────────────


def test_la_consigne_dit_quoi_faire_d_une_valeur_que_personne_n_a_donnee() -> None:
    assert "ne se remplace pas non plus par deux bornes" in COHERENCE_DES_CHIFFRES
    assert "faute de base" in COHERENCE_DES_CHIFFRES
    # Le motif de réparation dit la même chose : sinon la réécriture invente.
    assert "faute de base, aucun chiffre" in _CHECK_LABELS["fourchette_interdite"]


def test_la_consigne_ne_montre_pas_la_plage_fautive() -> None:
    """On dit la classe, on ne montre pas la faute (leçon du 15/09/2026)."""
    assert "75 à 80" not in COHERENCE_DES_CHIFFRES
    assert "URSSAF" not in COHERENCE_DES_CHIFFRES


# ── 2. Une série nommée par son seul signe ne porte aucun montant ────────────


def _datees(phrase: str) -> list[tuple[str, int, float]]:
    doc = Document(sections=[Section("18.7", "", 18, paragraphes=[phrase])])
    return [(v.serie, v.annee, v.nombre.valeur) for v in valeurs_datees(doc)]


def test_le_calendrier_de_remuneration_n_est_pas_le_resultat_net() -> None:
    """Échoue sur le code d'avant : « 0 € en 2027 » devenait le résultat net 2027."""
    phrase = (
        "Décision : nous fixons le calendrier 0 € en 2027, 12 000 € en 2028, 18 000 € en "
        "2029, chaque palier conditionné à un résultat net positif et à une trésorerie "
        "de clôture suffisante."
    )
    assert not [d for d in _datees(phrase) if d[0] == "resultat_net"]


def test_contre_epreuve_un_resultat_net_qui_porte_son_montant_reste_lu() -> None:
    assert ("resultat_net", 2027, 1954.0) in _datees(
        "Nous dégageons un résultat net positif de 1 954 € en 2027.")
    assert ("resultat_net", 2027, 1954.0) in _datees(
        "Le résultat net atteint 1 954 € en 2027.")


# ── 3. Une population nommée par trois de ses mots ───────────────────────────


def _objets(*paragraphes: str) -> list[str]:
    doc = DocumentLu(
        chemin=Path("bp.docx"), paragraphes=list(paragraphes), cellules=[],
        chapitre_du_paragraphe=[4 + i for i in range(len(paragraphes))],
    )
    return [a.detail for a in controler_objet_des_chiffres(doc) if "Objet changé" in a.detail]


def test_une_population_nommee_par_ses_propres_mots_n_a_pas_change_d_objet() -> None:
    """Échoue sur le code d'avant : trois « objets changés » pour une population."""
    assert _objets(
        "Notre clientèle d'acheteurs est estimée à 395 000 000 personnes : les classes "
        "moyennes urbaines chinoises de 20 à 45 ans, acheteuses en ligne sur mobile.",
        "Notre clientèle cible, 395 000 000 personnes des classes moyennes urbaines, achète "
        "déjà en ligne.",
        "Cette frange est déjà identifiée : 395 000 000 classes moyennes urbaines chinoises, "
        "acheteuses en ligne.",
        "Un marché accessible de 42,5 M€, sur une clientèle déjà estimée à 395 000 000 "
        "acheteurs en ligne, suffit largement.",
    ) == []


def test_contre_epreuve_deux_objets_sans_mot_commun_restent_signales() -> None:
    assert _objets(
        "Nous visons 8 000 commandes livrées en 2027 sur la plateforme.",
        "Nous visons 8 000 commandes livrées en 2027, au panier moyen de 35 €.",
        "Le cédant a mené 8 000 reprises de PME en vingt ans.",
    )


# ── 4. Les anglicismes mesurés sur le corpus ─────────────────────────────────


def test_les_anglicismes_du_corpus_sont_vus() -> None:
    """Échoue sur le code d'avant : aucun n'était dans la liste."""
    for phrase, mot in (
        ("Une estimation fondée sur nos hypothèses de ramp commercial.", "ramp"),
        ("Des articles vendus par des marketplaces étrangères.", "marketplace"),
        ("Le comportement cross-border observé en Chine.", "cross-border"),
        ("Un pipeline de recrutement continu de producteurs.", "pipeline"),
        ("Une marketplace généraliste low-cost.", "low-cost"),
    ):
        assert mot in [t.mot.casefold().rstrip("s") for t in jargon(phrase)], phrase


def test_contre_epreuve_une_adresse_et_un_mot_francais_passent() -> None:
    assert jargon("https://www.up2china.com/the-future-of-cross-border-e-commerce") == []
    assert jargon("La rampe d'accès du dépôt est livrée en mars.") == []
    assert jargon("Le « cross-border » est le terme anglais du commerce transfrontalier.") == []

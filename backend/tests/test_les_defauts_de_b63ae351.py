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

import pytest

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
    assert "ne l'écris pas en chiffres" in COHERENCE_DES_CHIFFRES
    # Le motif de réparation dit la même chose : sinon la réécriture invente.
    assert "ne s'écrit pas en chiffres" in _CHECK_LABELS["fourchette_interdite"]


def test_la_consigne_n_ouvre_pas_une_quatrieme_origine() -> None:
    """Revue du 22/11/2026 : « une valeur dite comme hypothèse » contredisait la
    règle 1 (« pas de quatrième origine ») et la règle des taux réglementaires.
    Ni « hypothèse », ni « à confirmer » — interdits par le même prompt."""
    debut = COHERENCE_DES_CHIFFRES.index("7. AUCUNE FOURCHETTE")
    regle_7 = COHERENCE_DES_CHIFFRES[debut:COHERENCE_DES_CHIFFRES.index("8. ", debut)]
    assert "hypothèse" not in regle_7
    assert "confirm" not in regle_7
    assert "trois origines" in regle_7
    motif = _CHECK_LABELS["fourchette_interdite"]
    assert "hypothèse" not in motif
    # Les exceptions de l'étude concurrentielle passent AVANT la règle générale.
    assert motif.index("étude concurrentielle") < motif.index("ne s'écrit pas en chiffres")


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


@pytest.mark.parametrize(("phrase", "attendu"), [
    ("Nous dégageons un résultat net positif de 1 954 € en 2027.", 1954.0),
    ("Le résultat net atteint 1 954 € en 2027.", 1954.0),
    # Revue du 22/11/2026 : tournures courantes que la première version perdait.
    ("Le résultat net positif atteint 1 954 € en 2027.", 1954.0),
    ("Le résultat net reste positif, à 1 954 € en 2027.", 1954.0),
    ("Nous visons un résultat net négatif de −3 200 € en 2027.", -3200.0),
])
def test_contre_epreuve_un_resultat_net_qui_porte_son_montant_reste_lu(
    phrase: str, attendu: float,
) -> None:
    assert [v for s, a, v in _datees(phrase) if s == "resultat_net" and a == 2027] in (
        [attendu], [abs(attendu)])


def test_le_montant_ne_passe_pas_a_la_serie_voisine() -> None:
    """Revue du 22/11/2026 : écarter la série-condition AVANT le compte donnait
    le montant à l'autre série nommée — « la CAF 2027 vaut 0 € », grave."""
    for phrase in (
        "Nous fixons le calendrier 0 € en 2027, 12 000 € en 2028, chaque palier "
        "conditionné à un résultat net positif et à une CAF suffisante.",
        "La prime de 3 000 € en 2028 est conditionnée à un résultat net positif et au "
        "chiffre d'affaires visé.",
    ):
        assert _datees(phrase) == [], phrase


def test_une_serie_condition_n_ouvre_pas_de_reprise() -> None:
    doc = Document(sections=[Section("18.7", "", 18, paragraphes=[
        "Chaque palier est conditionné à un résultat net positif. "
        "Celui-ci passe à 18 000 € en 2029."
    ])])
    assert [v for v in valeurs_datees(doc) if v.serie == "resultat_net"] == []


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


def test_contre_epreuve_un_mot_du_voisinage_ne_definit_pas_la_population() -> None:
    """Revue du 22/11/2026 : l'exemple que le module cite lui-même. « entreprise »
    se lit à côté des porteurs de projet, il ne les définit pas."""
    assert _objets(
        "En France, 10 000 porteurs de projet préparent la création de leur entreprise.",
        "Chaque année, 10 000 porteurs de projet sont accompagnés par un réseau.",
        "Le pays compte 10 000 entreprises nouvelles par an.",
    )
    assert _objets(
        "Nous avons interrogé 2 500 clients sur leurs commandes en ligne.",
        "Les 2 500 clients interrogés achètent chaque mois.",
        "Nous traitons 2 500 commandes par mois.",
    )


# ── 4. Les anglicismes mesurés sur le corpus ─────────────────────────────────


def test_les_anglicismes_du_corpus_sont_vus() -> None:
    """Échoue sur le code d'avant : aucun n'était dans la liste."""
    for phrase, mot in (
        ("Une estimation fondée sur nos hypothèses de ramp commercial.", "ramp"),
        ("La phase de ramp-up dure six mois.", "ramp-up"),
        ("Des articles vendus par des marketplaces étrangères.", "marketplace"),
        ("Le comportement cross-border observé en Chine.", "cross-border"),
        ("Le commerce cross border progresse.", "cross border"),
        ("Une offre low cost pour les étudiants.", "low cost"),
        ("Une marketplace généraliste low-cost.", "low-cost"),
        # Le pluriel d'un terme existant.
        ("Nos benchmarks le montrent.", "benchmark"),
    ):
        assert mot in [t.mot.casefold() for t in jargon(phrase)], phrase


def test_contre_epreuve_les_noms_de_marque_et_le_pipeline_passent() -> None:
    """Revue du 22/11/2026 : « pipeline » est un mot de métier (commercial,
    oléoduc), et le nom d'une plateforme se cite tel quel."""
    assert jargon("Notre pipeline commercial compte douze prospects.") == []
    assert jargon("Les vendeurs tiers passent par Amazon Marketplace.") == []
    assert jargon("Amazon Marketplace domine le segment.") == []


def test_contre_epreuve_une_adresse_et_un_mot_francais_passent() -> None:
    assert jargon("https://www.up2china.com/the-future-of-cross-border-e-commerce") == []
    assert jargon("La rampe d'accès du dépôt est livrée en mars.") == []
    assert jargon("Le « cross-border » est le terme anglais du commerce transfrontalier.") == []

"""Quatre mécanismes posés le 10/08/2026, chacun contre un défaut mesuré.

  1. Le prompt d'un chapitre se découpe en part CACHÉE (par job) et part
     variable — 24 % de lecture cache mesurés sur `2490c7cf`, parce que le
     socle repartait au tarif plein à chaque chapitre.
  2. La base consolidée concurrents est TRANSMISE aux chapitres — 7/8 et 6/3
     concurrents au chapitre 9 de `6cb0fab3`, parce que le modèle recomposait
     sa liste de mémoire.
  3. La carte de chaleur sait dessiner des acteurs notés par critère — le
     chapitre 3 de `6cb0fab3` a perdu sa criticité par critère sur le motif
     des risques (règle 4 : deux résolveurs corrigés sur trois le matin même).
  4. Les CA de la base consolidée justifient les chiffres du document — des
     dizaines de réserves « hors socle » sur des montants que `ca_connu`
     portait (règle 2 : une référence incomplète fabrique des motifs faux).
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from generation.chapitres.runner import PromptChapitre, _bloc_socle
from generation.rendu_word.donnees_graphiques import resoudre
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import (
    Concurrent,
    Critere,
    DonneeSocle,
    NoteConcurrent,
    Risque,
    Socle,
    Zone,
)
from generation.verification.controles import controler_chiffres_hors_socle
from generation.verification.lecture import DocumentLu, mesures_dans


def _socle(**surcharges: object) -> Socle:
    champs: dict[str, object] = {
        "secteur": "or physique",
        "zone": Zone(pays="France"),
        "date_socle": dt.date(2026, 8, 10),
        "donnees": [
            DonneeSocle(
                id="taille_marche", libelle="Marché", valeur=600, unite="MEUR",
                annee=2026, perimetre=Perimetre.NATIONAL,
                fiabilite=Fiabilite.ESTIMEE,
            )
        ],
    }
    champs.update(surcharges)
    return Socle(**champs)  # type: ignore[arg-type]


CRITERES = [
    Critere(code="prix", intitule="Accessibilité tarifaire",
            note_1="prime forte", note_5="prime faible"),
    Critere(code="offre", intitule="Étendue de l'offre",
            note_1="un format", note_5="gamme complète"),
]


def _acteur(nom: str, ca: str = "", **notes: int) -> Concurrent:
    return Concurrent(
        nom=nom, ca_connu=ca,
        notes=[NoteConcurrent(critere=c, note=n) for c, n in notes.items()],
    )


# ── 1. Le découpage du prompt pour le cache ──────────────────────────────────


def test_le_prompt_reste_une_chaine_complete() -> None:
    """Tout consommateur existant lit le prompt entier, blocs dans l'ordre."""
    prompt = PromptChapitre("BLOC JOB", "BLOC CHAPITRE")

    assert isinstance(prompt, str)
    assert "BLOC JOB" in prompt
    assert "BLOC CHAPITRE" in prompt
    assert prompt.index("BLOC JOB") < prompt.index("BLOC CHAPITRE")


def test_la_part_cachee_porte_le_socle_et_la_part_variable_non() -> None:
    """Le défaut exact : le socle repayé au tarif plein à chaque chapitre.

    Ce test échoue sur le code d'avant — le prompt n'avait ni `par_job` ni
    `par_chapitre`, et le socle partait dans le message utilisateur.
    """
    prompt = PromptChapitre("SOCLE VERROUILLÉ — or physique", "CHAPITRE À RÉDIGER : 3")

    assert "SOCLE VERROUILLÉ" in prompt.par_job
    assert "SOCLE VERROUILLÉ" not in prompt.par_chapitre
    assert "CHAPITRE À RÉDIGER" in prompt.par_chapitre


def test_sans_part_job_le_prompt_est_la_part_chapitre() -> None:
    """Contre-épreuve : pas de séparateur orphelin quand par_job est vide."""
    prompt = PromptChapitre("", "SEULEMENT LE CHAPITRE")

    assert str(prompt) == "SEULEMENT LE CHAPITRE"


# ── 2. La base consolidée transmise ──────────────────────────────────────────


def test_le_chapitre_recoit_la_base_concurrents_et_ses_comptes() -> None:
    socle = _socle(concurrents=[
        _acteur("VeraCash", ca="1,4 M€ (2024)"),
        Concurrent(nom="AuCOFFRE", type="indirect",
                   methode_estimation="trafic et panier moyen"),
    ])

    bloc = _bloc_socle(socle)

    assert "BASE CONSOLIDÉE CONCURRENTS" in bloc
    assert "1 directs et 1 indirects, ni plus ni moins" in bloc
    assert "VeraCash" in bloc and "1,4 M€ (2024)" in bloc
    assert "à estimer par : trafic et panier moyen" in bloc


def test_un_socle_sans_concurrents_n_ajoute_rien() -> None:
    """Contre-épreuve : pas de section vide sur une étude de marché."""
    assert "BASE CONSOLIDÉE" not in _bloc_socle(_socle())


# ── 3. La carte de chaleur des acteurs notés ─────────────────────────────────


def test_la_chaleur_dessine_les_acteurs_par_critere() -> None:
    """Le défaut du chapitre 3 de `6cb0fab3`, troisième résolveur sur trois."""
    socle = _socle(
        grille_notation=CRITERES,
        concurrents=[_acteur("VeraCash", prix=4, offre=3),
                     _acteur("AuCOFFRE", prix=2, offre=5)],
    )

    resolution = resoudre(socle, "carte_chaleur", ["prix", "offre"])

    assert resolution.retenu, resolution.motif
    assert resolution.donnees is not None
    assert resolution.donnees["lignes"] == ["VeraCash", "AuCOFFRE"]
    assert resolution.donnees["colonnes"] == [
        "Accessibilité tarifaire", "Étendue de l'offre"
    ]
    assert resolution.donnees["valeurs"] == [[4.0, 3.0], [2.0, 5.0]]


def test_la_chaleur_sans_criteres_cites_dessine_toujours_les_risques() -> None:
    """Contre-épreuve : ce qui marchait avant continue de marcher."""
    socle = _socle(risques=[
        Risque(intitule="Cours volatil", probabilite=4, impact=5),
        Risque(intitule="Réglementation", probabilite=2, impact=3),
    ])

    resolution = resoudre(socle, "carte_chaleur", [])

    assert resolution.retenu, resolution.motif
    assert resolution.donnees is not None
    assert resolution.donnees["colonnes"] == ["Probabilité", "Impact", "Criticité"]


def test_la_chaleur_a_un_seul_acteur_note_explique_le_refus() -> None:
    socle = _socle(
        grille_notation=CRITERES,
        concurrents=[_acteur("VeraCash", prix=4, offre=3), _acteur("AuCOFFRE")],
    )

    resolution = resoudre(socle, "carte_chaleur", ["prix", "offre"])

    assert not resolution.retenu
    assert "moins de deux acteurs" in resolution.motif


# ── 4. Les CA de la base consolidée justifient le document ───────────────────


def _document(*phrases: str) -> DocumentLu:
    lu = DocumentLu(chemin=Path("memoire.docx"), paragraphes=list(phrases))
    for phrase in phrases:
        lu.mesures.extend(mesures_dans(phrase))
    return lu


def test_un_ca_de_la_base_consolidee_n_est_plus_une_reserve() -> None:
    """Le défaut mesuré : des dizaines de réserves sur des montants sourcés."""
    socle = _socle(concurrents=[_acteur("VeraCash", ca="1,4 M€ (2024)")])

    anomalies = controler_chiffres_hors_socle(
        _document("VeraCash déclare 1,4 M€ de chiffre d'affaires."), socle
    )

    assert anomalies == []


def test_un_montant_invente_reste_une_reserve() -> None:
    """Contre-épreuve : on complète la référence, on n'ouvre pas la porte."""
    socle = _socle(concurrents=[_acteur("VeraCash", ca="1,4 M€ (2024)")])

    anomalies = controler_chiffres_hors_socle(
        _document("Un acteur fantôme pèserait 7,3 M€ sur ce marché."), socle
    )

    assert len(anomalies) == 1
    assert "7,3 M€" in anomalies[0].detail

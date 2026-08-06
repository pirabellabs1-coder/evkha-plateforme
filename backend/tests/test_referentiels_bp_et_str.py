"""Les referentiels du business plan et de la strategie, AVANT leur bascule.

Etape 1-2 du plan du 06/08/2026. `_BP` et `_STR` sont ecrits, testes — et PAS
enregistres dans `_PAR_LIVRABLE` : les brancher est un commit d'une ligne,
volontairement separe, parce que c'est l'interrupteur qui fait basculer d'un
coup production, socle, figures et controles (`EVKHA_SOCLE_ENABLED` est vrai en
production).

Ces tests montent donc la machinerie complete — validation, prompt — en
enregistrant le referentiel LE TEMPS DU TEST (`monkeypatch.setitem`). C'est la
seule facon de prouver que la bascule fonctionnera sans la faire : le jour du
branchement, la ligne ajoutee est exactement celle que ces tests posent.

## La contre-epreuve qui compte le plus

`test_rien_n_a_bascule` : tant que la ligne n'est pas commitee,
`livrable_couvert("business_plan")` reste faux. Si ce test tombe, quelqu'un a
branche la bascule par megarde — et la production genere des BP sur un moteur
jamais repete a blanc.
"""
from __future__ import annotations

from datetime import date

import pytest

from catalog.models import DeliverableType
from generation.socle import referentiel
from generation.socle.prompt import construire_prompt_socle
from generation.socle.referentiel import (
    _BP,
    _STR,
    FamilleUnite,
    Fiabilite,
    Perimetre,
)
from generation.socle.schema import DonneeSocle, Socle, Zone, valider_socle


@pytest.fixture
def bp_enregistre(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enregistre `_BP` le temps du test — la ligne exacte de la future bascule."""
    monkeypatch.setitem(
        referentiel._PAR_LIVRABLE, DeliverableType.BUSINESS_PLAN, _BP
    )


@pytest.fixture
def str_enregistre(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        referentiel._PAR_LIVRABLE, DeliverableType.BUSINESS_STRATEGY, _STR
    )


def _socle(*donnees: DonneeSocle) -> Socle:
    return Socle(
        secteur="joaillerie de créateurs",
        zone=Zone(pays="France"),
        date_socle=date(2026, 8, 6),
        donnees=list(donnees),
    )


def _d(
    identifiant: str,
    valeur: float,
    unite: str = "EUR",
    *,
    perimetre: Perimetre = Perimetre.ENTREPRISE,
    fiabilite: Fiabilite = Fiabilite.SCENARIO,
) -> DonneeSocle:
    return DonneeSocle(
        id=identifiant, libelle=identifiant.replace("_", " "), valeur=valeur,
        unite=unite, annee=2026, perimetre=perimetre, fiabilite=fiabilite,
    )


# ── 0. Rien n'a bascule ──────────────────────────────────────────────────────


def test_rien_n_a_bascule() -> None:
    """LA contre-epreuve. La bascule est un commit d'une ligne, pas un effet de bord.

    Si ce test tombe, `_PAR_LIVRABLE` porte le business plan ou la strategie
    alors que la repetition a blanc n'a pas eu lieu : la production genererait
    des documents sur un chemin jamais essaye.
    """
    assert not referentiel.livrable_couvert(DeliverableType.BUSINESS_PLAN)
    assert not referentiel.livrable_couvert(DeliverableType.BUSINESS_STRATEGY)
    # Et les deux etudes, elles, restent couvertes : on n'a rien debranche.
    assert referentiel.livrable_couvert(DeliverableType.MARKET_STUDY)
    assert referentiel.livrable_couvert(DeliverableType.COMPETITOR_STUDY)


# ── 1. Structure des referentiels ────────────────────────────────────────────


def test_les_series_annuelles_suivent_la_convention_de_radical() -> None:
    """`<serie>_anN` : la convention que le rendu emploiera pour grouper.

    Toutes les donnees du previsionnel partagent le perimetre ENTREPRISE — le
    radical de l'identifiant est le SEUL axe de groupement possible pour une
    figure « CA vs resultat sur 3 ans ». Une serie qui deroge a la convention
    serait dessinable mais ingroupable.
    """
    annuels = [d.identifiant for d in _BP if d.identifiant[-4:] in ("_an1", "_an2", "_an3")]
    assert len(annuels) >= 15
    radicaux = {i[:-4] for i in annuels}
    # Chaque radical decline ses trois exercices, ou seulement l'exercice 1
    # (charges fixes, remuneration, masse salariale, effectif — l'exercice 1
    # suffit au chapitre qui les exploite).
    for radical in radicaux:
        exercices = sorted(i[-1] for i in annuels if i.startswith(radical + "_an"))
        assert exercices in (["1"], ["1", "2", "3"]), (radical, exercices)


def test_les_libelles_surveilles_par_le_gate_ont_leur_emplacement() -> None:
    """Regle 5 : une seule nomenclature entre le gate et le socle.

    `checks_evangeline._LIBELLES_SURVEILLES` nomme les chiffres intangibles
    d'Evangeline. Chacun de ceux qui portent une valeur unique doit avoir son
    emplacement au socle — sinon le gate surveille un chiffre que le socle ne
    sait pas porter, et le chapitre l'invente.
    """
    identifiants = {d.identifiant for d in _BP}
    for attendu in (
        "investissement_total", "apport", "emprunt", "bfr", "seuil_rentabilite",
        "ca_previsionnel_an1", "resultat_net_an1", "caf_an1",
        "tresorerie_fin_an1", "dette_residuelle_an1",
    ):
        assert attendu in identifiants, attendu


def test_le_previsionnel_est_en_perimetre_entreprise() -> None:
    """Un previsionnel est le chiffre DU projet, jamais celui du marche."""
    for d in _BP:
        if d.identifiant[-4:] in ("_an1", "_an2", "_an3") or d.identifiant in (
            "investissement_total", "apport", "emprunt", "bfr", "seuil_rentabilite",
        ):
            assert d.perimetre == Perimetre.ENTREPRISE, d.identifiant


def test_la_strategie_n_exige_presque_rien() -> None:
    """Un projet en creation n'a ni CA ni clients : l'obligatoire tuerait son etude.

    Seul le marche national est exige — toujours etablissable. Le reste est
    facultatif, et la regle 10 du prompt socle dit deja : mieux vaut omettre
    que deviner.
    """
    obligatoires = [d.identifiant for d in _STR if d.obligatoire]
    assert obligatoires == ["marche_national_taille"]
    ca = next(d for d in _STR if d.identifiant == "ca_actuel")
    assert not ca.obligatoire


def test_aucun_taux_n_est_declare_monetaire() -> None:
    """La confusion unite/famille a deja produit « croissance en milliards »."""
    for d in (*_BP, *_STR):
        if "taux" in d.identifiant or d.identifiant.endswith("_croissance"):
            assert d.famille_unite == FamilleUnite.POURCENTAGE, d.identifiant


# ── 2. L'equilibre financier ─────────────────────────────────────────────────


@pytest.mark.usefixtures("bp_enregistre")
def test_un_plan_de_financement_troue_est_refuse() -> None:
    """100 k d'investissement, 60 k de ressources : le socle est refuse.

    Sur le code d'avant, aucun controle ne comparait les deux — le trou de
    40 k arrivait tel quel au chapitre 15, qui le redigeait sans le voir.
    """
    socle = _socle(
        _d("investissement_total", 100_000, fiabilite=Fiabilite.DECLAREE),
        _d("apport", 30_000, fiabilite=Fiabilite.DECLAREE),
        _d("emprunt", 30_000, fiabilite=Fiabilite.DECLAREE),
    )

    motifs = valider_socle(socle, DeliverableType.BUSINESS_PLAN)

    assert any("ne couvre pas l'investissement" in m for m in motifs)


@pytest.mark.usefixtures("bp_enregistre")
def test_un_plan_equilibre_passe() -> None:
    """CONTRE-EPREUVE : le controle ne bloque pas un montage correct."""
    socle = _socle(
        _d("investissement_total", 100_000, fiabilite=Fiabilite.DECLAREE),
        _d("apport", 40_000, fiabilite=Fiabilite.DECLAREE),
        _d("emprunt", 60_000, fiabilite=Fiabilite.DECLAREE),
    )

    motifs = valider_socle(socle, DeliverableType.BUSINESS_PLAN)

    assert not any("ne couvre pas" in m for m in motifs)


@pytest.mark.usefixtures("bp_enregistre")
def test_un_resultat_superieur_au_ca_est_refuse() -> None:
    """Presque toujours une erreur d'echelle : k-euros contre euros."""
    socle = _socle(
        _d("ca_previsionnel_an1", 120_000),
        _d("resultat_net_an1", 350_000),
    )

    motifs = valider_socle(socle, DeliverableType.BUSINESS_PLAN)

    assert any("dépasse `ca_previsionnel_an1`" in m for m in motifs)


@pytest.mark.usefixtures("bp_enregistre")
def test_une_perte_la_premiere_annee_est_un_scenario_legitime() -> None:
    """CONTRE-EPREUVE decisive : la parcimonie des controles (lecon runs 1-3).

    Un premier exercice en perte est NORMAL. Un controle qui l'interdirait
    forcerait le modele a embellir le previsionnel — l'exact inverse de ce
    qu'un socle existe pour garantir.
    """
    socle = _socle(
        _d("ca_previsionnel_an1", 120_000),
        _d("resultat_net_an1", -18_000),
    )

    motifs = valider_socle(socle, DeliverableType.BUSINESS_PLAN)

    assert not any("resultat_net_an1" in m for m in motifs)


@pytest.mark.usefixtures("bp_enregistre")
def test_un_seuil_au_dela_du_previsionnel_est_refuse() -> None:
    socle = _socle(
        _d("seuil_rentabilite", 900_000),
        _d("ca_previsionnel_an3", 300_000),
    )

    motifs = valider_socle(socle, DeliverableType.BUSINESS_PLAN)

    assert any("point mort" in m for m in motifs)


def test_les_controles_financiers_se_taisent_sur_une_etude_de_marche() -> None:
    """Ils ne trouvent pas leurs identifiants : ils ne disent rien.

    Comme l'emboitement TAM/SAM/SOM se tait sur une etude concurrentielle. Un
    controle qui parlerait d'un plan de financement sur une EM serait un motif
    introuvable pour le lecteur (regle 2).
    """
    socle = _socle(
        _d("marche_national_taille", 4.4, "MdEUR", perimetre=Perimetre.NATIONAL,
           fiabilite=Fiabilite.ESTIMEE),
    )

    motifs = valider_socle(socle, DeliverableType.MARKET_STUDY)

    assert not any("financement" in m or "point mort" in m for m in motifs)


# ── 3. Le prompt du socle porte les exigences du livrable ────────────────────


@pytest.mark.usefixtures("bp_enregistre")
def test_le_prompt_socle_bp_exige_le_previsionnel() -> None:
    """La lecon de `_BASE_CONCURRENTS` : un schema que rien ne demande part vide."""
    prompt = construire_prompt_socle(
        deliverable_type=DeliverableType.BUSINESS_PLAN,
        variables={"PROJET": "Joalie", "SECTEUR": "joaillerie"},
    )

    assert "PRÉVISIONNEL FINANCIER" in prompt
    assert "ca_previsionnel_an1" in prompt        # le referentiel est joint
    assert "seuil_rentabilite" in prompt
    assert "plan de financement s'équilibre" in prompt
    # Et jamais la base concurrents : c'est l'exigence d'un autre livrable.
    assert "BASE CONSOLIDÉE CONCURRENTS" not in prompt


@pytest.mark.usefixtures("str_enregistre")
def test_le_prompt_socle_str_demande_les_verticales() -> None:
    prompt = construire_prompt_socle(
        deliverable_type=DeliverableType.BUSINESS_STRATEGY,
        variables={"PROJET": "Joalie", "SECTEUR": "joaillerie"},
    )

    assert "CADRAGE CHIFFRÉ" in prompt
    assert "segments_clientele" in prompt
    assert "ca_objectif_horizon" in prompt
    assert "OMETS l'identifiant" in prompt
    assert "PRÉVISIONNEL FINANCIER" not in prompt

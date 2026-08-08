"""Les referentiels du business plan et de la strategie. **La bascule a eu lieu.**

`_BP` et `_STR` sont enregistres dans `_PAR_LIVRABLE` depuis le 06/08/2026 :
les quatre livrables passent par le moteur structure — socle, chapitres
structures, figures, chaine Word, controles du fichier livre. C'est
`test_les_quatre_livrables_sont_couverts` qui le verrouille.

CE TITRE DISAIT << AVANT LEUR BASCULE >>, et ce qui suivait decrivait un etat
depasse depuis deux jours : referentiels ecrits mais PAS enregistres, bascule
restant a faire en un commit d'une ligne. Un inventaire du 08/08/2026 en a
conclu que le business plan et la strategie tournaient encore sur l'ancien
moteur, et a propose de refaire le travail. Un fichier de test qui decrit
l'etat d'avant dans sa docstring de tete est un piege : c'est le premier
endroit ou l'on va chercher ce que le sujet garantit.

Les tests montent la machinerie complete — validation, prompt — et certains
enregistrent encore le referentiel LE TEMPS DU TEST (`monkeypatch.setitem`).
Ce n'est plus necessaire pour prouver que la bascule fonctionnera, mais reste
utile pour isoler un referentiel d'un autre sans dependre de l'etat global.

## La contre-epreuve qui compte le plus

`test_les_quatre_livrables_sont_couverts`. S'il tombe, un livrable est retombe
sur le moteur herite — soit un revert volontaire, et il faut mettre ce test a
jour avec, soit une regression qui livrera des documents amputes sans rien
signaler. L'ancienne contre-epreuve `test_rien_n_a_bascule` verrouillait
l'invariant INVERSE, avant le 06/08/2026 ; elle n'existe plus.
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
def bp_enregistre() -> None:
    """Vestige d'avant la bascule : `_BP` vit desormais dans `_PAR_LIVRABLE`.

    Conservee en no-op plutot que retiree : les tests qui la citent decrivent
    des comportements du referentiel ENREGISTRE, et c'est l'etat courant. La
    supprimer imposerait de reecrire leurs signatures sans rien verifier de
    plus.
    """


@pytest.fixture
def str_enregistre() -> None:
    """Meme statut que `bp_enregistre`."""


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


def test_les_quatre_livrables_sont_couverts() -> None:
    """La bascule du 06/08/2026 a eu lieu, et rien n'a ete debranche.

    Ce test disait l'inverse — `test_rien_n_a_bascule` — tant que la
    repetition a blanc n'avait pas eu lieu. Il verrouille desormais l'etat
    voulu : les QUATRE livrables passent par le moteur structure. Si l'un
    d'eux retombe, c'est soit un revert volontaire (mettre ce test a jour avec
    lui), soit une regression a corriger.
    """
    for livrable in (
        DeliverableType.MARKET_STUDY,
        DeliverableType.COMPETITOR_STUDY,
        DeliverableType.BUSINESS_PLAN,
        DeliverableType.BUSINESS_STRATEGY,
    ):
        assert referentiel.livrable_couvert(livrable), livrable


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

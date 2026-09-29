"""Le socle ne meurt plus pour une donnée facultative, une note ou un élément mal formé.

## Le défaut, sur un vrai dossier

29/09/2026, business plan `cb59cede` : « Socle non recevable après 3
tentative(s) : `taille_clientele_cible` : périmètre « regional » alors que le
référentiel impose « national ». » Zéro chapitre sur vingt-deux. La donnée en
cause était FACULTATIVE : le dossier est mort pour un chiffre dont il pouvait
se passer.

Le socle était tout-ou-rien. Trois dossiers perdus avant lui l'avaient été
pour la même raison, chacun sur un défaut différent (`6a44baff` grille,
`8cc1be56` filiation, `44bbd696` champs racine) ; chacun avait reçu SA
réparation. Ce fichier verrouille la CLASSE (règle 4).

## Ce qui est verrouillé

À la DERNIÈRE tentative seulement :

1. une donnée facultative mise en cause par un motif est écartée, et le socle
   passe (le cas `cb59cede`) ;
2. un élément de liste mal formé est écarté seul — donnée, acteur, note —, une
   clé inconnue à la racine aussi ; secteur et pays manquants se reprennent du
   brief ;
3. une note sans critère déclaré et un critère déclaré deux fois se réparent ;
4. une filiation rendue orpheline par un retrait se répare aussi.

Contre-épreuves (règle 6) : aux premières tentatives, le refus reste — c'est
lui qui fait corriger le modèle ; une donnée OBLIGATOIRE fautive ou absente
arrête toujours le dossier ; une contradiction qui implique une donnée
obligatoire aussi, même face à une facultative (l'erreur peut être du côté de
l'obligatoire : revue du 29/09/2026) ; un doublon d'obligatoire aux valeurs
divergentes aussi.
"""
from __future__ import annotations

import copy
from typing import Any

import pytest

from catalog.models import DeliverableType
from generation.socle import MAX_TENTATIVES, SocleGenerationError, produire_socle
from generation.socle.builder import _analyser
from generation.socle.prompt import construire_prompt_socle
from generation.socle.referentiel import identifiants_obligatoires
from generation.socle.stub import socle_de_demonstration
from integrations.claude import StructuredResult

BP = DeliverableType.BUSINESS_PLAN
EM = DeliverableType.MARKET_STUDY

#: Le brief du 29/09/2026, à sa forme.
BRIEF = {
    "SECTEUR": "conception et organisation d'événements",
    "PAYS": "France",
    "ZONE": "Auvergne-Rhône-Alpes",
    "PROJET": "agence événementielle ÉCLORE",
}


def _charge(livrable: str) -> dict[str, Any]:
    prompt = construire_prompt_socle(deliverable_type=livrable, variables=BRIEF)
    return socle_de_demonstration(prompt)


def _donnee(charge: dict[str, Any], identifiant: str) -> dict[str, Any]:
    trouvees = [d for d in charge["donnees"] if d["id"] == identifiant]
    assert trouvees, f"`{identifiant}` absent de la doublure : ce test ne jugerait rien"
    return trouvees[0]  # type: ignore[no-any-return]


def _analyse(
    charge: dict[str, Any], livrable: str, *, dernier_recours: bool
) -> tuple[Any, list[str]]:
    return _analyser(
        copy.deepcopy(charge), livrable, dernier_recours=dernier_recours, brief=BRIEF
    )


def test_la_doublure_est_recevable_telle_quelle() -> None:
    """Sans quoi chaque test ci-dessous jugerait autre chose que son défaut."""
    for livrable in (BP, EM):
        socle, motifs = _analyse(_charge(livrable), livrable, dernier_recours=False)
        assert socle is not None, motifs


# ── 1. La donnée facultative en cause est écartée ────────────────────────────


def _cas_cb59cede() -> dict[str, Any]:
    """Une clientèle à une échelle que le référentiel n'admet pas, trois fois de suite."""
    charge = _charge(BP)
    _donnee(charge, "taille_clientele_cible")["perimetre"] = "monde"
    return charge


def test_aux_premieres_tentatives_le_refus_fait_corriger_le_modele() -> None:
    socle, motifs = _analyse(_cas_cb59cede(), BP, dernier_recours=False)
    assert socle is None
    assert any("`taille_clientele_cible` : périmètre" in m for m in motifs)


def test_a_la_derniere_la_donnee_facultative_part_pas_le_dossier() -> None:
    """Le test qui échoue sur le code d'avant : le socle était refusé."""
    socle, motifs = _analyse(_cas_cb59cede(), BP, dernier_recours=True)
    assert socle is not None, motifs
    assert socle.donnee("taille_clientele_cible") is None
    assert identifiants_obligatoires(BP) <= socle.identifiants


def test_une_contradiction_avec_une_obligatoire_reste_un_refus() -> None:
    """Un CA à 135 € face à un résultat de 12 000 € : c'est le CA qui est faux.

    `resultat_net_an1` est facultatif, `ca_previsionnel_an1` obligatoire.
    Retirer le résultat ferait du CA faux la référence de tout le document.
    """
    charge = _charge(BP)
    _donnee(charge, "ca_previsionnel_an1")["valeur"] = 135.0
    _donnee(charge, "resultat_net_an1")["valeur"] = 12_000.0

    socle, motifs = _analyse(charge, BP, dernier_recours=True)

    assert socle is None
    assert any("`resultat_net_an1`" in m and "`ca_previsionnel_an1`" in m for m in motifs)


def test_de_bout_en_bout_trois_fois_la_meme_faute_ne_tue_plus_l_etude() -> None:
    """Le parcours réel : le modèle refait la même faute aux trois tentatives."""

    class ClientTetu:
        appels = 0

        def complete_structured(self, **_: object) -> StructuredResult:
            ClientTetu.appels += 1
            return StructuredResult(
                payload=_cas_cb59cede(), input_tokens=5, output_tokens=5, model="stub"
            )

    socle, _consommation, tentatives = produire_socle(
        client=ClientTetu(), deliverable_type=BP, variables=BRIEF
    )
    assert tentatives == MAX_TENTATIVES
    assert socle.donnee("taille_clientele_cible") is None


# ── 2. Un élément mal formé part seul ────────────────────────────────────────


def test_un_element_mal_forme_est_ecarte_seul() -> None:
    charge = _charge(BP)
    _donnee(charge, "bfr")["annee"] = 1985  # hors bornes : donnée facultative
    charge["concurrents"][0]["notes"][0]["note"] = 7  # une note hors barème
    charge["risques"].append({"intitule": ""})  # un risque sans intitulé
    charge["commentaire"] = "hors contrat"  # une clé que le contrat ignore
    assert _analyse(charge, BP, dernier_recours=False)[0] is None

    socle, motifs = _analyse(charge, BP, dernier_recours=True)

    assert socle is not None, motifs
    assert socle.donnee("bfr") is None
    assert socle.donnee("apport") is not None
    assert len(socle.concurrents) == len(charge["concurrents"])
    assert len(socle.concurrents[0].notes) == len(charge["concurrents"][0]["notes"]) - 1
    assert all(r.intitule for r in socle.risques)


def test_secteur_et_pays_absents_se_reprennent_du_brief() -> None:
    """Les champs racine omis (`44bbd696`, 15/09/2026) sont des réponses du client."""
    charge = _charge(BP)
    del charge["secteur"]
    del charge["zone"]
    del charge["date_socle"]

    socle, motifs = _analyse(charge, BP, dernier_recours=True)

    assert socle is not None, motifs
    assert socle.secteur == BRIEF["SECTEUR"]
    assert socle.zone.pays == BRIEF["PAYS"]


def test_un_denombrement_en_milliers_n_est_pas_converti_deux_fois() -> None:
    """Un élément est jugé sur une COPIE : le validateur réécrit son entrée."""
    charge = _charge(BP)
    effectif = _donnee(charge, "effectif_an1")
    effectif["valeur"], effectif["unite"] = 3.0, "millier"
    charge["commentaire"] = "force le passage par la charge tolérée"

    socle, motifs = _analyse(charge, BP, dernier_recours=True)

    assert socle is not None, motifs
    assert socle.donnee("effectif_an1").valeur == 3_000.0


# ── 3. Notes et grille ───────────────────────────────────────────────────────


def test_une_note_sans_critere_et_un_critere_en_double_se_reparent() -> None:
    charge = _charge(BP)
    charge["concurrents"][0]["notes"].append({"critere": "delais", "note": 3})
    charge["grille_notation"].append(copy.deepcopy(charge["grille_notation"][0]))
    assert _analyse(charge, BP, dernier_recours=False)[0] is None

    socle, motifs = _analyse(charge, BP, dernier_recours=True)

    assert socle is not None, motifs
    codes = [c.code for c in socle.grille_notation]
    assert len(codes) == len(set(codes))
    assert "delais" not in socle.concurrents[0].codes_notes


def test_une_grille_vide_retire_toutes_les_notes_et_le_dit() -> None:
    charge = _charge(BP)
    charge["grille_notation"] = []

    socle, motifs = _analyse(charge, BP, dernier_recours=True)

    assert socle is not None, motifs
    assert all(not a.notes for a in socle.concurrents)


# ── 4. Une filiation rendue orpheline se répare ──────────────────────────────


def test_un_retrait_ne_laisse_pas_de_filiation_orpheline() -> None:
    charge = _cas_cb59cede()
    _donnee(charge, "effectif_an1")["derivee_de"] = ["taille_clientele_cible"]

    socle, motifs = _analyse(charge, BP, dernier_recours=True)

    assert socle is not None, motifs
    assert socle.donnee("taille_clientele_cible") is None
    assert socle.donnee("effectif_an1").derivee_de == []


# ── Doublons ─────────────────────────────────────────────────────────────────


def test_un_doublon_facultatif_est_ecarte() -> None:
    charge = _charge(BP)
    copie = copy.deepcopy(_donnee(charge, "bfr"))
    copie["valeur"] = 99_000.0
    charge["donnees"].append(copie)

    socle, motifs = _analyse(charge, BP, dernier_recours=True)

    assert socle is not None, motifs
    assert socle.donnee("bfr") is None, "une donnée facultative en doublon est écartée"


def test_un_doublon_obligatoire_identique_se_fond() -> None:
    charge = _charge(BP)
    charge["donnees"].append(copy.deepcopy(_donnee(charge, "ca_previsionnel_an1")))

    socle, motifs = _analyse(charge, BP, dernier_recours=True)

    assert socle is not None, motifs
    assert [d.id for d in socle.donnees].count("ca_previsionnel_an1") == 1


def test_un_doublon_obligatoire_divergent_reste_un_refus() -> None:
    """Laquelle des deux valeurs est juste ? Personne ne le sait ici."""
    charge = _charge(BP)
    fausse = copy.deepcopy(_donnee(charge, "ca_previsionnel_an1"))
    fausse["valeur"] *= 1000
    charge["donnees"].insert(0, fausse)

    socle, motifs = _analyse(charge, BP, dernier_recours=True)

    assert socle is None
    assert "`ca_previsionnel_an1` apparaît plusieurs fois. Une donnée, une valeur." in motifs


# ── Contre-épreuves : ce qui arrête toujours un dossier ──────────────────────


def test_une_donnee_obligatoire_fautive_arrete_toujours_le_dossier() -> None:
    charge = _charge(BP)
    _donnee(charge, "investissement_total")["unite"] = "%"

    socle, motifs = _analyse(charge, BP, dernier_recours=True)

    assert socle is None
    assert any("`investissement_total`" in m for m in motifs)


def test_une_donnee_obligatoire_mal_formee_est_dite_absente() -> None:
    charge = _charge(BP)
    _donnee(charge, "marche_national_taille")["annee"] = 1900

    socle, motifs = _analyse(charge, BP, dernier_recours=True)

    assert socle is None
    assert "`marche_national_taille` est obligatoire et absent du socle." in motifs
    # Et le refus dit qu'elle a été produite, mais mal formée (règle 2).
    lecture = [m for m in motifs if m.startswith("Écarté à la lecture")]
    assert lecture and "donnees[" in lecture[0]


def test_une_contradiction_entre_donnees_obligatoires_reste_un_refus() -> None:
    """En étude de marché, TAM, SAM et SOM sont obligatoires : rien à écarter."""
    charge = _charge(EM)
    _donnee(charge, "som")["valeur"] = 3.0  # 3 Md€ : plus que le SAM

    socle, motifs = _analyse(charge, EM, dernier_recours=True)

    assert socle is None
    assert any("`som`" in m and "`sam`" in m for m in motifs)


def test_de_bout_en_bout_une_faute_obligatoire_leve_toujours_l_erreur() -> None:
    class ClientTetu:
        def complete_structured(self, **_: object) -> StructuredResult:
            charge = _charge(BP)
            _donnee(charge, "investissement_total")["unite"] = "%"
            return StructuredResult(payload=charge, input_tokens=5, output_tokens=5, model="stub")

    with pytest.raises(SocleGenerationError) as capture:
        produire_socle(client=ClientTetu(), deliverable_type=BP, variables=BRIEF)
    assert any("`investissement_total`" in m for m in capture.value.motifs)

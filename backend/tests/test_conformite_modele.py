"""Conformité d'un chapitre au modèle de référence.

Ce validateur existe parce que le dosage a été réglé trois fois à tâtons — 66 %
des mots en tableaux, puis 40 %, avant de retomber sur les 52 % du modèle. Sans
mesure automatique, chaque correction se faisait à l'œil sur un document produit
en dix minutes.

Chaque contrôle est testé DEUX fois : il doit signaler le chapitre fautif, et
laisser passer le chapitre correct. Un contrôle qui refuse aussi la bonne
réponse est désactivé au premier faux positif, donc inutile (règle 6).
"""
from __future__ import annotations

from typing import Any

import pytest

from generation.chapitres.schema import ChapitrePayload
from generation.modele import Gravite, verifier_chapitre
from generation.modele.chargement import chapitre_du_modele

SOCLE = frozenset({"marche_mondial_taille", "marche_france_taille", "part_premium"})
IDS = ["marche_mondial_taille", "marche_france_taille"]


def _prose(signes: int) -> str:
    """Un paragraphe de la longueur demandée, à quelques signes près."""
    motif = "Le socle verrouillé cadre ce périmètre et son ordre de grandeur. "
    return (motif * (signes // len(motif) + 1))[:signes].strip() or motif.strip()


def _adapte(intitule: str) -> str:
    """Réécrit un intitulé de référence pour le secteur de CETTE étude.

    Ajouté le 09/08/2026, et ce n'est pas un contournement du contrôle : c'est
    la doublure qui devait changer. Un chapitre conforme ne recopie plus les
    intitulés du document de référence — il les adapte, puisqu'ils sont écrits
    avec les mots de la joaillerie sur laquelle le modèle a été mesuré.

    La cliente l'a constaté sur une étude d'e-commerce animalier : « FOCUS —
    Approfondissement demandé : marché international des galeries et du
    sur-mesure », en page 52. Une doublure qui reproduit ce défaut décrit un
    chapitre que le produit refuse désormais de livrer (règle 7).
    """
    from generation.modele.conformite import _porte_le_secteur_de_reference

    if not _porte_le_secteur_de_reference(intitule):
        return intitule
    return f"{intitule} [adapté au secteur de l'étude]"


def _payload(numero: int = 1, **surcharges: Any) -> ChapitrePayload:
    """Chapitre CONFORME au modèle, sauf ce qu'on surcharge.

    Les blocs suivent le modèle, dans son ordre et à ses longueurs. Écrire un
    chapitre d'essai « à peu près » ferait échouer les contrôles pour de
    mauvaises raisons, et on croirait à un validateur trop strict alors que
    c'est l'essai qui est faux.

    Les intitulés qui nomment le secteur du document de référence sont ADAPTÉS
    (voir `_adapte`) : les recopier tels quels est précisément ce que le
    contrôle de contamination refuse.
    """
    modele = chapitre_du_modele(numero)
    assert modele is not None, f"le modèle n'a pas de chapitre {numero:02d}"

    blocs: list[dict[str, Any]] = []
    for bloc in modele["blocs"]:
        type_bloc = bloc["type"]
        if type_bloc == "titre_sous_section":
            blocs.append({
                "type": "titre_sous_section",
                "numero": bloc["numero"],
                "intitule": _adapte(bloc["intitule_reference"]),
            })
        elif type_bloc == "paragraphe":
            blocs.append({
                "type": "paragraphe",
                "texte": _prose(int(bloc["longueur_cible_signes"])),
            })
        elif type_bloc == "tableau":
            entetes = bloc["entetes"] or ["Élément", "Constat"]
            blocs.append({"type": "tableau", "tableau": {
                "entetes": entetes,
                "lignes": [["Valeur"] * len(entetes)
                           for _ in range(max(int(bloc["nb_lignes_cible"]), 1))],
                "source": "Socle",
            }})
        elif type_bloc == "encadre":
            blocs.append({"type": "encadre", "encadre": {
                "intitule": _adapte(bloc["etiquette"]) or "Lecture du chapitre",
                "lignes": ["Opportunité.", "Limite."],
            }})
        elif type_bloc == "grille_kpi":
            blocs.append({"type": "grille_kpi", "cellules": [
                {"valeur": f"{n} %", "libelle": "Repère", "source": "Socle"}
                for n in range(int(bloc["cellules"]))
            ]})
        elif type_bloc == "graphique":
            blocs.append({"type": "graphique", "graphique": {
                "type": "barres", "titre": "Repère", "donnees_ids": IDS,
            }})

    base: dict[str, Any] = {
        "chapitre": numero,
        "titre": modele["titre_reference"],
        "accroche": "Une accroche de positionnement.",
        "blocs": blocs,
        "donnees_utilisees": IDS,
        "resume": "Résumé opérationnel du chapitre, transmis au suivant.",
    }
    base.update(surcharges)
    return ChapitrePayload.model_validate(base)


def _avec(payload: ChapitrePayload, **maj: Any) -> ChapitrePayload:
    """Rejoue la validation après modification.

    `model_copy` ne valide PAS : il range des dictionnaires bruts dans un champ
    typé, et le contrôle s'écroule plus loin sur un `AttributeError` au lieu de
    juger. Un test qui construit un objet impossible ne teste rien.
    """
    return ChapitrePayload.model_validate({**payload.model_dump(), **maj})


def _blocs(payload: ChapitrePayload) -> list[dict[str, Any]]:
    return [b.model_dump() for b in payload.blocs]


def _regles(rapport: Any, gravite: Gravite | None = None) -> set[str]:
    return {e.regle for e in rapport.ecarts if gravite is None or e.gravite is gravite}


# ── Le modèle absent ─────────────────────────────────────────────────────────


def test_un_chapitre_sans_modele_est_bloquant() -> None:
    """Le chapitre 00 « Fiche projet » n'existe pas au modèle.

    Le laisser passer reviendrait à valider un chapitre qu'on n'a pas comparé.
    """
    rapport = verifier_chapitre(
        _avec(_payload(numero=1), chapitre=0), identifiants_socle=SOCLE
    )
    assert not rapport.conforme
    assert "modele_absent" in _regles(rapport, Gravite.BLOQUANTE)


def test_un_rapport_sans_controle_execute_n_est_jamais_conforme() -> None:
    """Règle 1, dans sa forme la plus nue."""
    from generation.modele.conformite import RapportConformite

    assert not RapportConformite(chapitre=1).conforme


# ── Le cas conforme ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("numero", [1, 3, 9, 19, 21])
def test_un_chapitre_conforme_passe(numero: int) -> None:
    """Contre-épreuve générale, sur cinq chapitres de FORMES très différentes.

    Le 09 aligne quatre grilles de chiffres et aucun paragraphe ; le 19
    enchaîne treize tableaux et neuf encadrés. Un validateur calibré sur le
    seul chapitre 01 se serait cru correct en refusant les vingt autres.
    """
    rapport = verifier_chapitre(_payload(numero), identifiants_socle=SOCLE)
    assert rapport.conforme, [e.detail for e in rapport.ecarts]
    assert rapport.controles_executes


# ── La séquence ──────────────────────────────────────────────────────────────


def test_la_sequence_est_desormais_verifiee() -> None:
    """Elle était déclarée IMPOSSIBLE tant que le contrat portait trois listes.

    Le contrat ordonné la rend vérifiable : le contrôle doit donc figurer parmi
    les contrôles exécutés, et plus parmi les impossibles.
    """
    rapport = verifier_chapitre(_payload(), identifiants_socle=SOCLE)
    assert "sequence_des_blocs" in rapport.controles_executes
    assert rapport.controles_impossibles == {}


def test_un_graphique_deplace_en_fin_de_chapitre_est_signale() -> None:
    """LE test que l'ancien contrat ne permettait pas d'écrire.

    Trois listes séparées rejetaient tous les graphiques en queue de chapitre,
    et rien ne pouvait le mesurer — c'était la forme normale.
    """
    conforme = _payload()
    blocs = _blocs(conforme)
    graphique = next(b for b in blocs if b["type"] == "graphique")
    sans = [b for b in blocs if b["type"] != "graphique"]
    rapport = verifier_chapitre(
        _avec(conforme, blocs=[*sans, graphique]), identifiants_socle=SOCLE
    )
    assert "sequence_des_blocs" in _regles(rapport, Gravite.BLOQUANTE)


def test_un_paragraphe_de_plus_ne_derange_pas_la_sequence() -> None:
    """Contre-épreuve : la tolérance de ±1 paragraphe doit survivre.

    Comparer TOUS les blocs dans l'ordre contredirait la tolérance du cahier
    des charges — deux règles qui se contredisent en font une de trop.
    """
    conforme = _payload()
    blocs = _blocs(conforme)
    paragraphe = next(b for b in blocs if b["type"] == "paragraphe")
    rapport = verifier_chapitre(
        _avec(conforme, blocs=[*blocs, paragraphe]), identifiants_socle=SOCLE
    )
    assert "sequence_des_blocs" not in _regles(rapport)


# ── Les graphiques ───────────────────────────────────────────────────────────


def test_moins_de_graphiques_que_le_minimum_est_bloquant() -> None:
    conforme = _payload()
    sans = [b for b in _blocs(conforme) if b["type"] != "graphique"]
    rapport = verifier_chapitre(_avec(conforme, blocs=sans), identifiants_socle=SOCLE)
    assert "graphiques_min" in _regles(rapport, Gravite.BLOQUANTE)
    detail = next(e.detail for e in rapport.ecarts if e.regle == "graphiques_min")
    assert "0 graphique" in detail, detail


# ── Le dosage ────────────────────────────────────────────────────────────────


def test_un_tableau_de_trop_reste_dans_la_tolerance() -> None:
    """La spécification accepte ±1 tableau."""
    conforme = _payload()
    de_trop = {"type": "tableau", "tableau": {
        "entetes": ["A", "B"], "lignes": [["1", "2"]], "source": ""}}
    rapport = verifier_chapitre(
        _avec(conforme, blocs=[*_blocs(conforme), de_trop]), identifiants_socle=SOCLE
    )
    assert "dosage_tableaux" not in _regles(rapport)


def test_trois_tableaux_de_trop_sont_bloquants() -> None:
    conforme = _payload()
    de_trop = {"type": "tableau", "tableau": {
        "entetes": ["A", "B"], "lignes": [["1", "2"]], "source": ""}}
    rapport = verifier_chapitre(
        _avec(conforme, blocs=[*_blocs(conforme), de_trop, de_trop, de_trop]),
        identifiants_socle=SOCLE,
    )
    assert "dosage_tableaux" in _regles(rapport, Gravite.BLOQUANTE)


def test_un_encadre_manquant_est_bloquant() -> None:
    """Un encadré porte une décision : il ne se perd pas dans la tolérance."""
    conforme = _payload()
    sans = [b for b in _blocs(conforme) if b["type"] != "encadre"]
    rapport = verifier_chapitre(_avec(conforme, blocs=sans), identifiants_socle=SOCLE)
    assert "dosage_encadres" in _regles(rapport, Gravite.BLOQUANTE)


# ── Le volume ────────────────────────────────────────────────────────────────


def test_un_chapitre_deux_fois_trop_long_est_bloquant() -> None:
    conforme = _payload()
    blocs = _blocs(conforme)
    for bloc in blocs:
        if bloc["type"] == "paragraphe":
            bloc["texte"] = bloc["texte"] + " Rallonge. " * 200
    rapport = verifier_chapitre(_avec(conforme, blocs=blocs), identifiants_socle=SOCLE)
    assert "volume" in _regles(rapport, Gravite.BLOQUANTE)
    detail = next(e.detail for e in rapport.ecarts if e.regle == "volume")
    assert "au-dessus" in detail, detail


def test_un_chapitre_trop_court_est_bloquant_aussi() -> None:
    """Le défaut symétrique. C'est celui qu'on a vécu : 2 599 signes de prose
    pour 4 131 au modèle, et la cliente l'a lu comme « trop de tableaux »."""
    conforme = _payload()
    blocs = [
        {**b, "texte": "Court."} if b["type"] == "paragraphe" else b
        for b in _blocs(conforme)
    ]
    rapport = verifier_chapitre(_avec(conforme, blocs=blocs), identifiants_socle=SOCLE)
    assert "volume" in _regles(rapport, Gravite.BLOQUANTE)
    detail = next(e.detail for e in rapport.ecarts if e.regle == "volume")
    assert "en dessous" in detail, detail


# ── Les données ──────────────────────────────────────────────────────────────


def test_un_identifiant_hors_socle_est_bloquant() -> None:
    conforme = _payload()
    faux = ["marche_mondial_taille", "invente_de_toutes_pieces"]
    blocs = [
        {**b, "graphique": {**b["graphique"], "donnees_ids": faux}}
        if b["type"] == "graphique" else b
        for b in _blocs(conforme)
    ]
    rapport = verifier_chapitre(
        _avec(conforme, blocs=blocs, donnees_utilisees=faux), identifiants_socle=SOCLE
    )
    assert "data_refs_inconnus" in _regles(rapport, Gravite.BLOQUANTE)
    detail = next(e.detail for e in rapport.ecarts if e.regle == "data_refs_inconnus")
    assert "invente_de_toutes_pieces" in detail, (
        "le motif doit nommer l'identifiant fautif, sinon il envoie chercher "
        "au hasard (règle 2)"
    )


# ── Les variables de gabarit ─────────────────────────────────────────────────


@pytest.mark.parametrize("champ", ["titre", "accroche", "resume"])
def test_une_variable_non_resolue_est_bloquante(champ: str) -> None:
    """« Aucune variable ne peut rester non résolue dans le document final. »"""
    surcharge: dict[str, Any] = {champ: "Étude pour {{client.nom}}"}
    rapport = verifier_chapitre(_payload(**surcharge), identifiants_socle=SOCLE)
    assert "variable_non_resolue" in _regles(rapport, Gravite.BLOQUANTE)


def test_une_variable_dans_une_cellule_de_tableau_est_vue_aussi() -> None:
    """Le contrôle regarde le tableau, pas seulement la prose.

    Un contrôle qui ne regarde que la prose laisserait passer `{{client.nom}}`
    dans une cellule — et c'est exactement là qu'un gabarit en met.
    """
    conforme = _payload()
    blocs = [*_blocs(conforme), {"type": "tableau", "tableau": {
        "entetes": ["Client", "Valeur"],
        "lignes": [["{{client.nom}}", "12"]],
        "source": "",
    }}]
    rapport = verifier_chapitre(_avec(conforme, blocs=blocs), identifiants_socle=SOCLE)
    assert "variable_non_resolue" in _regles(rapport, Gravite.BLOQUANTE)


def test_une_accolade_ordinaire_ne_declenche_rien() -> None:
    """Contre-épreuve : `{` seul n'est pas une variable de gabarit."""
    rapport = verifier_chapitre(
        _payload(accroche="Un ensemble {a, b} de critères."), identifiants_socle=SOCLE
    )
    assert "variable_non_resolue" not in _regles(rapport)

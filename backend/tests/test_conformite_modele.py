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
from generation.modele.chargement import chapitre_du_modele, dosage_attendu

SOCLE = frozenset({"marche_mondial_taille", "marche_france_taille", "part_premium"})


def _prose(signes: int) -> str:
    """Un paragraphe de la longueur demandée, à quelques signes près."""
    motif = "Le socle verrouillé cadre ce périmètre et son ordre de grandeur. "
    texte = (motif * (signes // len(motif) + 1))[:signes]
    return texte.strip() or motif.strip()


def _payload(numero: int = 1, **surcharges: Any) -> ChapitrePayload:
    """Chapitre conforme au modèle 01, sauf ce qu'on surcharge.

    Construit À PARTIR du modèle plutôt qu'écrit en dur : une cible qui change
    dans le modèle doit faire évoluer ce chapitre, pas produire un test qui
    verrouille l'ancienne valeur.
    """
    modele = chapitre_du_modele(numero)
    assert modele is not None, f"le modèle n'a pas de chapitre {numero:02d}"
    attendu = dosage_attendu(modele)

    # Longueurs prises dans le modèle, pas inventées : un chapitre d'essai plus
    # court que la cible ferait échouer le contrôle de volume, et on croirait à
    # un contrôle trop strict alors que c'est l'essai qui est faux.
    cibles = [
        int(b["longueur_cible_signes"])
        for b in modele["blocs"] if b["type"] == "paragraphe"
    ]
    par_section = attendu.paragraphes // max(attendu.sous_sections, 1)
    reste = attendu.paragraphes - par_section * attendu.sous_sections
    sections: list[dict[str, Any]] = []
    rang = 0
    for index in range(attendu.sous_sections):
        nombre = par_section + (1 if index < reste else 0)
        morceaux = []
        for _ in range(nombre):
            longueur = cibles[rang] if rang < len(cibles) else 350
            rang += 1
            morceaux.append(_prose(longueur))
        titre = f"{numero}.{index + 1} Sous-section adossée au socle"
        sections.append({
            "titre": titre,
            "contenu": "\n\n".join(morceaux) or _prose(350),
        })
    for index in range(attendu.tableaux):
        sections[index % len(sections)]["tableau"] = {
            "entetes": ["Niveau", "Ordre de grandeur"],
            "lignes": [["Marché", "Élevé"]],
            "source": "Socle",
        }

    base: dict[str, Any] = {
        "chapitre": numero,
        "titre": "Marché mondial et continent pertinent",
        "accroche": "Une accroche de positionnement.",
        "sections": sections,
        "encadres": [
            {"intitule": "Lecture du chapitre", "lignes": ["Opportunité.", "Limite."]}
            for _ in range(attendu.encadres)
        ],
        "donnees_utilisees": ["marche_mondial_taille", "marche_france_taille"],
        "graphiques": [
            {
                "type": "barres",
                "titre": f"Repère {n + 1}",
                "donnees_ids": ["marche_mondial_taille", "marche_france_taille"],
            }
            for n in range(attendu.graphiques_min)
        ],
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


def _sections(payload: ChapitrePayload) -> list[dict[str, Any]]:
    return [s.model_dump() for s in payload.sections]


def _regles(rapport: Any, gravite: Gravite | None = None) -> set[str]:
    return {
        e.regle for e in rapport.ecarts if gravite is None or e.gravite is gravite
    }


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


def test_un_chapitre_conforme_passe() -> None:
    """Contre-épreuve générale : sans elle, un contrôle trop strict serait
    indétectable jusqu'à ce qu'il bloque tout."""
    rapport = verifier_chapitre(_payload(), identifiants_socle=SOCLE)
    assert rapport.conforme, [e.detail for e in rapport.ecarts]
    assert rapport.controles_executes


# ── Les graphiques ───────────────────────────────────────────────────────────


def test_moins_de_graphiques_que_le_minimum_est_bloquant() -> None:
    rapport = verifier_chapitre(_payload(graphiques=[]), identifiants_socle=SOCLE)
    assert "graphiques_min" in _regles(rapport, Gravite.BLOQUANTE)
    detail = next(e.detail for e in rapport.ecarts if e.regle == "graphiques_min")
    assert "0 graphique" in detail, detail


def test_plus_de_graphiques_que_le_minimum_est_accepte() -> None:
    """« Un graphique de plus est permis ; jamais un de moins. »"""
    conforme = _payload()
    graphiques = [g.model_dump() for g in conforme.graphiques]
    rapport = verifier_chapitre(
        _avec(conforme, graphiques=[*graphiques, {**graphiques[0], "titre": "De plus"}]),
        identifiants_socle=SOCLE,
    )
    assert "graphiques_min" not in _regles(rapport)


# ── Le dosage ────────────────────────────────────────────────────────────────


def test_un_tableau_de_trop_reste_dans_la_tolerance() -> None:
    """La spécification accepte ±1 tableau."""
    conforme = _payload()
    sections = _sections(conforme)
    sections[0]["tableau"] = {
        "entetes": ["A", "B"], "lignes": [["1", "2"]], "source": ""
    }
    rapport = verifier_chapitre(
        _avec(conforme, sections=sections), identifiants_socle=SOCLE
    )
    assert "dosage_tableaux" not in _regles(rapport)


def test_trois_tableaux_de_trop_sont_bloquants() -> None:
    conforme = _payload()
    sections = _sections(conforme)
    for section in sections:
        section["tableau"] = {
            "entetes": ["A", "B"], "lignes": [["1", "2"]], "source": ""
        }
    rapport = verifier_chapitre(
        _avec(conforme, sections=sections), identifiants_socle=SOCLE
    )
    assert "dosage_tableaux" in _regles(rapport, Gravite.BLOQUANTE)


def test_un_encadre_manquant_est_bloquant() -> None:
    """Un encadré porte une décision : il ne se perd pas dans la tolérance."""
    rapport = verifier_chapitre(_payload(encadres=[]), identifiants_socle=SOCLE)
    assert "dosage_encadres" in _regles(rapport, Gravite.BLOQUANTE)


# ── Le volume ────────────────────────────────────────────────────────────────


def test_un_chapitre_deux_fois_trop_long_est_bloquant() -> None:
    conforme = _payload()
    sections = _sections(conforme)
    for section in sections:
        section["contenu"] = section["contenu"] + "\n\n" + "Rallonge. " * 400
    rapport = verifier_chapitre(
        _avec(conforme, sections=sections), identifiants_socle=SOCLE
    )
    assert "volume" in _regles(rapport, Gravite.BLOQUANTE)
    detail = next(e.detail for e in rapport.ecarts if e.regle == "volume")
    assert "au-dessus" in detail, detail


def test_un_chapitre_trop_court_est_bloquant_aussi() -> None:
    """Le défaut symétrique. C'est celui qu'on a vécu : 2 599 signes de prose
    pour 4 131 au modèle, et la cliente l'a lu comme « trop de tableaux »."""
    conforme = _payload()
    sections = [{**s, "contenu": "Court."} for s in _sections(conforme)]
    rapport = verifier_chapitre(
        _avec(conforme, sections=sections), identifiants_socle=SOCLE
    )
    assert "volume" in _regles(rapport, Gravite.BLOQUANTE)
    detail = next(e.detail for e in rapport.ecarts if e.regle == "volume")
    assert "en dessous" in detail, detail


# ── Les données ──────────────────────────────────────────────────────────────


def test_un_identifiant_hors_socle_est_bloquant() -> None:
    conforme = _payload()
    graphiques = [
        {**g.model_dump(), "donnees_ids": ["marche_mondial_taille", "invente_de_toutes_pieces"]}
        for g in conforme.graphiques
    ]
    rapport = verifier_chapitre(
        _avec(
            conforme,
            donnees_utilisees=["marche_mondial_taille", "invente_de_toutes_pieces"],
            graphiques=graphiques,
        ),
        identifiants_socle=SOCLE,
    )
    assert "data_refs_inconnus" in _regles(rapport, Gravite.BLOQUANTE)
    detail = next(e.detail for e in rapport.ecarts if e.regle == "data_refs_inconnus")
    assert "invente_de_toutes_pieces" in detail, (
        "le motif doit nommer l'identifiant fautif, sinon il envoie chercher "
        "au hasard (règle 2)"
    )


# ── Les variables de gabarit ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "champ", ["titre", "accroche", "resume"],
)
def test_une_variable_non_resolue_est_bloquante(champ: str) -> None:
    """« Aucune variable ne peut rester non résolue dans le document final. »"""
    surcharge: dict[str, Any] = {champ: "Étude pour {{client.nom}}"}
    rapport = verifier_chapitre(
        _payload(**surcharge), identifiants_socle=SOCLE
    )
    assert "variable_non_resolue" in _regles(rapport, Gravite.BLOQUANTE)


def test_une_variable_dans_une_cellule_de_tableau_est_vue_aussi() -> None:
    """Le contrôle regarde le tableau, pas seulement la prose.

    Un contrôle qui ne regarde que la prose laisserait passer `{{client.nom}}`
    dans une cellule — et c'est exactement là qu'un gabarit en met.
    """
    conforme = _payload()
    sections = _sections(conforme)
    sections[0]["tableau"] = {
        "entetes": ["Client", "Valeur"],
        "lignes": [["{{client.nom}}", "12"]],
        "source": "",
    }
    rapport = verifier_chapitre(
        _avec(conforme, sections=sections), identifiants_socle=SOCLE
    )
    assert "variable_non_resolue" in _regles(rapport, Gravite.BLOQUANTE)


def test_une_accolade_ordinaire_ne_declenche_rien() -> None:
    """Contre-épreuve : `{` seul n'est pas une variable de gabarit."""
    rapport = verifier_chapitre(
        _payload(accroche="Un ensemble {a, b} de critères."), identifiants_socle=SOCLE
    )
    assert "variable_non_resolue" not in _regles(rapport)


# ── Ce que le contrôle NE fait PAS ───────────────────────────────────────────


def test_les_controles_impossibles_sont_declares() -> None:
    """Règle 1 : ne pas confondre « vérifié » et « pas de nouvelle ».

    La séquence des blocs ne peut pas être vérifiée tant que `ChapitrePayload`
    porte trois listes séparées. Le rapport doit le DIRE, pas se taire.
    """
    rapport = verifier_chapitre(_payload(), identifiants_socle=SOCLE)
    assert "sequence_des_blocs" in rapport.controles_impossibles
    assert "longueur_par_paragraphe" in rapport.controles_impossibles
    for raison in rapport.controles_impossibles.values():
        assert len(raison) > 40, "une raison trop courte n'explique rien"
    assert "sequence_des_blocs" not in rapport.controles_executes

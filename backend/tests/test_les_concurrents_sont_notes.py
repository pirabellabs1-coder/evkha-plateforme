"""Une étude concurrentielle compare des acteurs — encore faut-il les noter.

## Le défaut, mesuré sur un dossier réel

`5892daa5` (étude de la concurrence, 10/08/2026) a été bloqué au plancher de
figures : **quatre visuels pour dix-sept attendus**, quinze graphiques
abandonnés. Onze de ces quinze abandons disaient la même chose sous deux
formes :

    le socle ne porte pas deux risques notés en probabilité et en impact
    un radar exige au moins trois axes

Le modèle demandait de positionner huit concurrents et de les comparer sur un
radar. Le socle décrivait ses onze acteurs en texte libre — positionnement,
structure, méthode d'estimation — et **pas une seule note**. Pire, la carte de
positionnement ne savait dessiner QUE des risques, sur des axes « Probabilité »
et « Impact » écrits en dur : on répondait à une demande sur les concurrents
qu'il manquait des risques.

## Ce qui était déjà là, et que rien ne demandait

`note_sur_5` est une unité reconnue du socle depuis toujours, le radar sait la
lire, et le rendu l'affiche « /5 ». La capacité existait entière. C'est le
défaut de la règle 8, pour la cinquième fois sur ce projet : **écrit, testé,
jamais demandé.**

## La contre-épreuve porte sur les livrables SANS notation

Un business plan n'a pas de grille et n'en veut pas. Un correctif qui exigerait
une grille partout ferait échouer trois livrables sur quatre — et il passerait
tous les tests ci-dessous s'ils ne parlaient que de concurrence.
"""
from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from generation.rendu_word.donnees_graphiques import resoudre
from generation.socle.schema import (
    Concurrent,
    Critere,
    Risque,
    Socle,
    Zone,
    _controler_grille_notation,
)

CRITERES = [
    Critere(code="prix", intitule="Accessibilité tarifaire",
            note_1="prime de plus de 15 % sur le cours", note_5="prime sous 3 %"),
    Critere(code="offre", intitule="Étendue de l'offre",
            note_1="un seul format proposé", note_5="tous formats et services"),
    Critere(code="notoriete", intitule="Notoriété",
            note_1="aucune mention presse", note_5="référence citée du secteur"),
]


def _acteur(nom: str, **notes: int) -> Concurrent:
    return Concurrent(nom=nom, notes=notes)


def _socle(*acteurs: Concurrent, criteres: list[Critere] | None = None,
           risques: list[Risque] | None = None) -> Socle:
    return Socle(
        secteur="or physique",
        zone=Zone(pays="France"),
        date_socle=dt.date(2026, 8, 10),
        concurrents=list(acteurs),
        grille_notation=CRITERES if criteres is None else criteres,
        risques=risques or [],
    )


def _notes_completes() -> list[Concurrent]:
    return [
        _acteur("VeraCash", prix=4, offre=3, notoriete=4),
        _acteur("AuCOFFRE", prix=3, offre=4, notoriete=3),
        _acteur("Degussa", prix=2, offre=5, notoriete=5),
    ]


# ── Le barème : une note sans échelle n'est pas une mesure ───────────────────


def test_une_note_hors_de_l_echelle_est_refusee() -> None:
    with pytest.raises(ValidationError, match="1-5"):
        Concurrent(nom="VeraCash", notes={"prix": 7})


def test_un_critere_sans_definition_de_bornes_est_refuse() -> None:
    """« Reproductible » était la demande. Sans barème, la note est une opinion.

    C'est le « chiffre inventé » que le socle entier existe pour empêcher,
    déguisé en évaluation.
    """
    with pytest.raises(ValidationError):
        Critere(code="prix", intitule="Prix", note_1="", note_5="très bon")


def test_une_note_sur_un_critere_inconnu_est_signalee() -> None:
    """Une coordonnée sans axe ne se place nulle part."""
    socle = _socle(_acteur("VeraCash", prix=4, offre=3, notoriete=2,
                           logistique=5),
                   _acteur("AuCOFFRE", prix=3, offre=4, notoriete=3))

    motifs = _controler_grille_notation(socle)

    assert any("logistique" in motif for motif in motifs)


def test_un_critere_qui_ne_note_qu_un_acteur_est_signale() -> None:
    """Règle 1 : un axe qui ne compare rien n'est pas un succès."""
    socle = _socle(_acteur("VeraCash", prix=4, offre=3, notoriete=2),
                   _acteur("AuCOFFRE", prix=3, offre=4))

    motifs = _controler_grille_notation(socle)

    assert any("`notoriete`" in motif and "1 acteur" in motif for motif in motifs)


def test_un_critere_declare_deux_fois_est_signale() -> None:
    socle = _socle(*_notes_completes(), criteres=[*CRITERES, CRITERES[0]])

    motifs = _controler_grille_notation(socle)

    assert any("plusieurs fois" in motif for motif in motifs)


def test_un_socle_note_correctement_ne_produit_aucun_motif() -> None:
    assert _controler_grille_notation(_socle(*_notes_completes())) == []


def test_un_livrable_sans_notation_traverse_intact() -> None:
    """LA contre-épreuve : un business plan n'a ni grille ni concurrents notés.

    Exiger une grille partout ferait échouer trois livrables sur quatre.
    """
    socle = Socle(
        secteur="boulangerie",
        zone=Zone(pays="France"),
        date_socle=dt.date(2026, 8, 10),
    )

    assert _controler_grille_notation(socle) == []


def test_un_acteur_partiellement_note_est_ecarte_des_figures() -> None:
    """Le placer avec une coordonnée manquante ferait une figure fausse."""
    socle = _socle(_acteur("VeraCash", prix=4, offre=3),
                   _acteur("AuCOFFRE", prix=3, offre=4))

    assert [nom for nom, _ in socle.notes_sur(["prix", "offre"])] == [
        "VeraCash", "AuCOFFRE"
    ]
    assert socle.notes_sur(["prix", "offre", "notoriete"]) == []


# ── Carte de positionnement : des concurrents, enfin ─────────────────────────


def test_la_carte_positionne_les_concurrents_sur_deux_criteres() -> None:
    """Le défaut exact de `5892daa5` : cinq figures perdues faute de ce chemin."""
    socle = _socle(*_notes_completes())

    resolution = resoudre(socle, "matrice_positionnement", ["prix", "notoriete"])

    assert resolution.retenu, resolution.motif
    assert resolution.donnees is not None
    assert resolution.donnees["axe_x"] == "Accessibilité tarifaire"
    assert resolution.donnees["axe_y"] == "Notoriété"
    assert ("VeraCash", 4.0, 4.0) in resolution.donnees["points"]
    assert len(resolution.donnees["points"]) == 3


def test_l_ordre_des_criteres_choisit_les_axes() -> None:
    """C'est le chapitre qui décide de la lecture, pas le socle."""
    socle = _socle(*_notes_completes())

    resolution = resoudre(socle, "matrice_positionnement", ["notoriete", "prix"])

    assert resolution.donnees is not None
    assert resolution.donnees["axe_x"] == "Notoriété"


def test_une_carte_qui_cite_des_criteres_ne_retombe_JAMAIS_sur_les_risques() -> None:
    """CONTRE-ÉPREUVE de la bascule.

    Se rabattre sur les risques dessinerait une figure juste répondant à une
    AUTRE question — et le lecteur ne peut pas le deviner (règle 3). Le socle
    porte ici deux risques notés : l'ancien code aurait dessiné leur matrice.
    """
    socle = _socle(
        _acteur("VeraCash", prix=4, offre=3, notoriete=2),
        _acteur("AuCOFFRE", offre=4),
        criteres=CRITERES,
        risques=[Risque(intitule="Cours volatil", probabilite=4, impact=5),
                 Risque(intitule="Réglementation", probabilite=2, impact=3)],
    )

    resolution = resoudre(socle, "matrice_positionnement", ["prix", "notoriete"])

    assert not resolution.retenu
    assert "moins de deux acteurs" in resolution.motif
    assert "Probabilité" not in resolution.motif


def test_une_carte_sans_critere_cite_dessine_toujours_les_risques() -> None:
    """Ce qui marchait avant doit continuer : les matrices de risques existent."""
    socle = _socle(
        criteres=[],
        risques=[Risque(intitule="Cours volatil", probabilite=4, impact=5),
                 Risque(intitule="Réglementation", probabilite=2, impact=3)],
    )

    resolution = resoudre(socle, "matrice_positionnement", [])

    assert resolution.retenu, resolution.motif
    assert resolution.donnees is not None
    assert resolution.donnees["axe_x"] == "Probabilité"


def test_un_seul_critere_cite_ne_fait_pas_une_carte() -> None:
    resolution = resoudre(_socle(*_notes_completes()),
                          "matrice_positionnement", ["prix"])

    assert not resolution.retenu
    assert "DEUX critères" in resolution.motif


# ── Radar : une série par acteur ─────────────────────────────────────────────


def test_le_radar_compare_les_acteurs_sur_les_criteres_cites() -> None:
    socle = _socle(*_notes_completes())

    resolution = resoudre(socle, "radar", ["prix", "offre", "notoriete"])

    assert resolution.retenu, resolution.motif
    assert resolution.donnees is not None
    assert resolution.donnees["axes_noms"] == [
        "Accessibilité tarifaire", "Étendue de l'offre", "Notoriété"
    ]
    assert ("VeraCash", [4.0, 3.0, 4.0]) in resolution.donnees["series"]
    assert resolution.donnees["maximum"] == 5.0


def test_un_radar_a_deux_axes_est_refuse() -> None:
    resolution = resoudre(_socle(*_notes_completes()), "radar", ["prix", "offre"])

    assert not resolution.retenu
    assert "trois axes" in resolution.motif


def test_un_radar_trop_charge_dit_qui_il_ecarte() -> None:
    """Une coupe silencieuse se lit comme « tout est là » (CLAUDE.md).

    Sept acteurs notés, cinq tracés : les deux écartés sont nommés dans le
    motif, qui remonte au rapport d'assemblage.
    """
    acteurs = [
        _acteur(f"Acteur {n}", prix=3, offre=3, notoriete=3) for n in range(7)
    ]
    socle = _socle(*acteurs)

    resolution = resoudre(socle, "radar", ["prix", "offre", "notoriete"])

    assert resolution.retenu
    assert resolution.donnees is not None
    assert len(resolution.donnees["series"]) == 5
    assert "Acteur 5" in resolution.motif
    assert "Acteur 6" in resolution.motif


def test_un_radar_sans_acteur_note_sur_tous_les_axes_explique_pourquoi() -> None:
    socle = _socle(_acteur("VeraCash", prix=4, offre=3),
                   _acteur("AuCOFFRE", prix=3, offre=4))

    resolution = resoudre(socle, "radar", ["prix", "offre", "notoriete"])

    assert not resolution.retenu
    assert "aucun acteur" in resolution.motif
    assert "Notoriété" in resolution.motif


# ── La cause : ce qui est demandé, et ce qui est transmis ────────────────────


def test_le_prompt_du_socle_reclame_la_grille_et_les_notes() -> None:
    """Vérifié sur le prompt RÉELLEMENT construit, pas sur la constante.

    Deux règles de la cliente n'ont jamais atteint l'étude de marché parce
    qu'elles vivaient dans un bloc que le moteur de production n'envoie pas.
    On interroge donc le texte assemblé pour ce livrable précis.
    """
    from generation.socle.prompt import construire_prompt_socle

    prompt = construire_prompt_socle(
        deliverable_type="competitor_study",
        variables={"SECTEUR": "or physique", "PAYS": "France"},
    )

    assert "grille_notation" in prompt
    assert "note_1" in prompt and "note_5" in prompt
    assert "`notes`" in prompt


def test_le_prompt_du_business_plan_ne_reclame_aucune_grille() -> None:
    """CONTRE-ÉPREUVE : la demande est portée par le livrable qui en a besoin."""
    from generation.socle.prompt import construire_prompt_socle

    prompt = construire_prompt_socle(
        deliverable_type="business_plan",
        variables={"SECTEUR": "boulangerie", "PAYS": "France"},
    )

    assert "grille_notation" not in prompt


def test_le_chapitre_recoit_la_grille_et_les_notes() -> None:
    """Sans ce bloc, la grille resterait invisible au chapitre qui doit la citer."""
    from generation.chapitres.runner import _bloc_socle

    bloc = _bloc_socle(_socle(*_notes_completes()))

    assert "`prix`" in bloc
    assert "Accessibilité tarifaire" in bloc
    assert "prime sous 3 %" in bloc  # le barème, pas seulement l'intitulé
    assert "VeraCash" in bloc


def test_la_grille_du_socle_prime_sur_l_echelle_generique() -> None:
    """Règle 5 : une seule source pour le sens d'une note.

    `REGLES_DE_FOND` porte une échelle générique — « 1 absent … 5 référence du
    secteur » — et le socle porte désormais un barème par critère. Deux sources
    pour la même vérité, c'est le défaut qui a produit la moitié des incidents
    de ce projet. La grille tranche, et la consigne doit le dire.
    """
    from generation.chapitres.runner import REGLES_DE_FOND

    assert "GRILLE DE NOTATION" in REGLES_DE_FOND
    assert "c'est " in REGLES_DE_FOND and "elle qui fait foi" in REGLES_DE_FOND
    # L'échelle générique survit pour les livrables SANS grille.
    assert "5 référence du secteur" in REGLES_DE_FOND


def test_un_socle_sans_grille_n_ajoute_rien_au_chapitre() -> None:
    """CONTRE-ÉPREUVE : pas de section vide sur les livrables sans notation."""
    from generation.chapitres.runner import _bloc_socle

    socle = Socle(
        secteur="boulangerie",
        zone=Zone(pays="France"),
        date_socle=dt.date(2026, 8, 10),
    )

    assert "GRILLE DE NOTATION" not in _bloc_socle(socle)

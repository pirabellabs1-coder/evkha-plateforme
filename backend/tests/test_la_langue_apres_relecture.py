"""La réparation de la langue, après la relecture de code du 29/09/2026.

Quatre défauts relevés sur le commit qui a introduit la réparation des mots
anglais (`chapitres.typographie`) et son contrôle post-rendu
(`checks_post_rendu.detecter_mots_anglais`) :

(a) « indeed » en minuscules était remplacé : « offres publiées sur indeed »
    devenait « offres publiées sur en effet ». C'est aussi le nom d'une
    plateforme d'emploi, que les business plans citent ;
(b) un mot CITÉ entre guillemets — « le mot « already » » — était traduit,
    alors qu'une citation se recopie ;
(c) un remplacement qui allonge (« however » → « cependant ») pouvait faire
    dépasser à un champ sa borne du contrat — accroche 400 signes, valeur
    d'indicateur 40 — et le rendu Word, qui revalide le chapitre, aurait
    échoué sur le DOCUMENT ENTIER ;
(d) un seul « overall » renvoyait le chapitre entier en réécriture payée.

Chaque épreuve échoue sur le code d'avant (rejouée depuis `a1b5dd0`) ; les
contre-épreuves disent ce que le correctif ne doit pas bloquer.
"""
from __future__ import annotations

from types import SimpleNamespace

from generation.chapitres.schema import (
    BlocGrilleKpi,
    BlocParagraphe,
    CelluleKpi,
    ChapitrePayload,
)
from generation.chapitres.typographie import mots_anglais, reparer_texte, reparer_typographie
from generation.checks_post_rendu import detecter_mots_anglais


def _section(corps: str) -> SimpleNamespace:
    return SimpleNamespace(number=9, title="Organisation et moyens", body=corps)


# ── (a) « indeed » : une plateforme autant qu'un adverbe ────────────────────


def test_la_plateforme_indeed_n_est_pas_traduite() -> None:
    texte = "Les offres sont publiées sur indeed et les candidatures reçues via indeed."
    assert reparer_texte(texte) == texte


def test_la_plateforme_indeed_n_est_pas_signalee() -> None:
    """Deux mentions de la plateforme : aucune fuite anglaise, aucun motif."""
    trouves = detecter_mots_anglais([_section(
        "Les offres sont publiées sur indeed ; les candidatures arrivent via indeed."
    )])
    assert trouves == []


def test_l_adverbe_indeed_reste_signale_sans_etre_remplace() -> None:
    """CONTRE-ÉPREUVE : l'adverbe qui fuit se voit encore — il ne se devine pas."""
    texte = "Le marché est indeed porteur, il reste indeed rentable."
    assert reparer_texte(texte) == texte
    trouves = detecter_mots_anglais([_section(texte)])
    assert [(t.mot, t.occurrences) for t in trouves] == [("indeed", 2)]


# ── (b) un mot cité entre guillemets se recopie ──────────────────────────────


def test_un_mot_cite_entre_guillemets_n_est_pas_traduit() -> None:
    for texte in (
        "Le mot « already » revient dans les avis clients.",
        'Le mot "already" revient dans les avis clients.',
        "Le mot “however” revient dans les avis clients.",
    ):
        assert reparer_texte(texte) == texte, texte
        assert mots_anglais(texte) == [], texte


def test_un_mot_cite_n_est_pas_signale() -> None:
    trouves = detecter_mots_anglais([_section(
        "Les avis citent « already » et « overall », puis « hence » et « overall »."
    )])
    assert trouves == []


def test_une_phrase_citee_n_abrite_pas_la_fuite() -> None:
    """CONTRE-ÉPREUVE : seul le mot ENTOURÉ de guillemets est une citation."""
    assert (
        reparer_texte("Elle écrit « le matériel est already financé ».")
        == "Elle écrit « le matériel est déjà financé »."
    )


# ── (c) une réparation ne fait jamais dépasser la borne d'un champ ──────────


def _chapitre(accroche: str, *valeurs: str) -> ChapitrePayload:
    return ChapitrePayload(
        chapitre=12,
        titre="Organisation et moyens",
        accroche=accroche,
        blocs=[
            BlocParagraphe(texte="Le matériel est already financé."),
            BlocGrilleKpi(cellules=[
                CelluleKpi(valeur=v, libelle="Indicateur") for v in valeurs
            ]),
        ],
        resume="Un résumé d'essai suffisamment long pour tenir sa borne.",
    )


def test_un_champ_borne_reste_dans_sa_borne_et_le_chapitre_se_revalide() -> None:
    """Le rendu Word revalide le chapitre : il ne doit jamais le trouver invalide.

    La valeur d'un indicateur est bornée à 40 signes et l'accroche à 400. Ces
    deux champs sont PLEINS : « cependant » (+2) et « par conséquent » (+5)
    les feraient déborder.
    """
    plein_40 = "Le CA se accroît however " + "a" * 15
    accroche = "Le marché est therefore porteur. " + "b" * 367
    assert len(plein_40) == 40
    assert len(accroche) == 400
    payload = _chapitre(accroche, plein_40, "12 MEUR however")

    reparer_typographie(payload)

    # Le chapitre réparé passe encore son propre contrat.
    ChapitrePayload.model_validate(payload.model_dump(by_alias=True))
    grille = payload.blocs[1]
    assert isinstance(grille, BlocGrilleKpi)
    # Le mot anglais est GARDÉ là où son équivalent ne tenait pas — et le
    # reste de la réparation, qui raccourcit, s'applique quand même.
    assert grille.cellules[0].valeur == "Le CA s'accroît however " + "a" * 15
    assert payload.accroche == accroche


def test_un_champ_qui_a_la_place_est_repare_en_entier() -> None:
    """CONTRE-ÉPREUVE : la borne ne retient que ce qui déborderait."""
    payload = _chapitre("Un prévisionnel already équilibré.", "12 MEUR however", "3 kEUR")

    reparer_typographie(payload)

    grille = payload.blocs[1]
    assert isinstance(grille, BlocGrilleKpi)
    assert [c.valeur for c in grille.cellules] == ["12\u00a0M€ cependant", "3\u00a0k€"]
    assert payload.accroche == "Un prévisionnel déjà équilibré."


def test_le_mot_garde_faute_de_place_est_signale_au_rendu() -> None:
    """Ce que la réparation a dû laisser, le contrôle le dit (règle 9)."""
    trouves = detecter_mots_anglais([_section("Le CA s'accroît however " + "a" * 15)])
    assert [t.mot for t in trouves] == ["however"]


# ── (d) un seul mot ambigu ne paie pas une réécriture de chapitre ───────────


def test_un_seul_mot_ambigu_ne_renvoie_pas_le_chapitre() -> None:
    assert detecter_mots_anglais([_section("Le score overall place le projet en tête.")]) == []


def test_deux_occurrences_ambigues_le_renvoient() -> None:
    """CONTRE-ÉPREUVE : une habitude du rédacteur, elle, mérite la reprise."""
    trouves = detecter_mots_anglais([_section(
        "Le score overall place le projet en tête, hence une marge confortable."
    )])
    assert sorted(t.mot for t in trouves) == ["hence", "overall"]


def test_un_mot_sans_ambiguite_n_attend_pas_le_seuil() -> None:
    """CONTRE-ÉPREUVE : la réparation aurait dû le remplacer, et ne l'a pas pu."""
    trouves = detecter_mots_anglais([_section("Le matériel est already financé.")])
    assert [t.mot for t in trouves] == ["already"]

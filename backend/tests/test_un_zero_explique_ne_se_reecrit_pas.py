"""Les deux seules occurrences de `valeur_nulle` sur un vrai business plan étaient fausses.

## La mesure

Business plan `578c7024`, 59 pages, re-mesuré le 28/10/2026 par
`jobs/<id>/mesure/`. Le contrôle `controler_les_valeurs_nulles` a rendu
**deux** anomalies, et aucune n'est un défaut :

    chapitre 14 : « …est de 0 € : les clientes paient à la réservation,
                    avant que salles et intervenantes soient réglées »
    annexe      : « ressources complémentaires = (investissement total +
                    besoin en fonds de roulement) − apport − emprunt ;
                    le plan de financement s'équilibre | 0 € | 2026 »

La première phrase énonce le zéro ET sa cause dans la même respiration. La
seconde est un ÉCART nul, nul précisément parce que le plan s'équilibre.

Zéro vrai positif sur 59 pages — et ce contrôle fait RÉÉCRIRE le chapitre
visé : il a déclenché la réécriture payante du chapitre 12, qui n'a jamais
abouti et a laissé le chapitre « en cours » sur un dossier livré.

## Pourquoi les listes de mots ne pouvaient pas marcher

`_ZERO_ASSUME` liste « aucun / nul / zéro / sans / pas de / non retenu… » et
`_EN_TETE_DE_RESULTAT` liste « écart / différence / variation / solde… ».
Aucune des deux phrases ci-dessus n'emploie un de ces mots : la première dit
sa cause par une subordonnée, la seconde dit « s'équilibre ». Les allonger
serait la quatrième énumération du même défaut sur ce dépôt (règle 4).

Le critère retenu est celui que la docstring du contrôle énonçait déjà sans
l'appliquer : le défaut est le zéro **NU**. On regarde la portée entière du
zéro — sa ligne en tableau, sa phrase en prose — et on compte ce qui s'y dit
de lui. Les deux faux positifs venaient d'une tranche trop étroite : la
cellule du zéro, quand le sens vivait dans la cellule d'à côté (règle 9).

Ces tests échouent sur le code d'avant : les deux phrases y produisaient une
anomalie.
"""
from __future__ import annotations

import pytest

from generation.verification.controles import _zero_explique
from generation.verification.lecture import Mesure

#: Recopiés des extraits rendus par `jobs/578c7024-…/mesure/` le 28/10/2026.
PROSE_EXPLIQUEE = (
    "Le besoin en fonds de roulement (argent immobilisé entre les dépenses et "
    "les encaissements) est de 0 € : les clientes paient à la réservation, "
    "avant que salles et intervenantes soient réglées."
)
LIGNE_D_ECART = (
    "Valeur : Calculé : ressources complémentaires = (investissement total + "
    "besoin en fonds de roulement) − apport − emprunt ; le plan de financement "
    "s'équilibre | 0 € | 2026 | Estimée"
)


def _Mesure(  # noqa: N802 — lu comme un constructeur dans les tests
    texte: str, *, contexte: str = "", phrase: str = "", tableau: bool = False
) -> Mesure:
    """La VRAIE `Mesure`, pas une doublure.

    Une doublure maison aurait suffi à faire tourner ces tests, et elle aurait
    dérivé du jour où `Mesure` change — un test qui s'adosse à sa propre
    approximation du type ne verrouille rien (règle 6).
    """
    return Mesure(
        valeur=0.0,
        unite="€",
        texte=texte,
        contexte=contexte,
        phrase=phrase,
        dans_un_tableau=tableau,
    )


# ---------------------------------------------------------------------------
# Les deux faux positifs mesurés
# ---------------------------------------------------------------------------


def test_une_phrase_qui_donne_la_cause_du_zero_est_assumee() -> None:
    """Chapitre 14 de `578c7024`. Échoue sur le code d'avant."""
    mesure = _Mesure("0 €", contexte=PROSE_EXPLIQUEE)

    assert _zero_explique(mesure)


def test_un_ecart_nul_dont_la_ligne_dit_pourquoi_est_assume() -> None:
    """L'annexe de `578c7024` : « s'équilibre » n'est dans aucune liste."""
    mesure = _Mesure("0 €", phrase=LIGNE_D_ECART, tableau=True)

    assert _zero_explique(mesure)


def test_les_deux_listes_de_mots_rejetaient_bien_ces_deux_phrases() -> None:
    """La preuve que ces tests échouent sur le code d'avant (règle 6).

    `_zero_explique` n'existait pas : on ne peut pas rejouer les tests
    ci-dessus contre l'ancien code. Ce qu'on PEUT rejouer, c'est la décision
    qu'il prenait — les deux listes de mots qui décidaient seules. Si l'une
    des deux reconnaissait ces phrases, le contrôle ne les aurait pas
    signalées, et mon diagnostic serait faux.
    """
    from generation.verification.controles import (
        _EN_TETE_DE_RESULTAT,
        _ZERO_ASSUME,
    )

    assert not _ZERO_ASSUME.search(PROSE_EXPLIQUEE), (
        "si l'ancienne liste reconnaissait déjà cette phrase, le chapitre 14 "
        "n'aurait pas été signalé — or il l'a été"
    )
    # La ligne d'écart passait par l'en-tête de sa ligne, « Valeur ».
    en_tete = LIGNE_D_ECART.partition(" : ")[0]
    assert not _EN_TETE_DE_RESULTAT.search(en_tete)
    assert not _ZERO_ASSUME.search(LIGNE_D_ECART)


# ---------------------------------------------------------------------------
# Contre-épreuves : le zéro NU doit continuer d'échouer
# ---------------------------------------------------------------------------


def test_une_cellule_qui_ne_porte_qu_une_etiquette_reste_nue() -> None:
    """Le défaut que le contrôle existe pour voir.

    « Coût d'acquisition » ÉTIQUETTE le zéro, il n'en dit rien : le lecteur ne
    peut pas savoir si le coût est nul ou s'il n'a pas été mesuré.
    """
    mesure = _Mesure("0 €", phrase="Coût d'acquisition | 0 € | 2027", tableau=True)

    assert not _zero_explique(mesure)


def test_une_phrase_qui_pose_le_zero_sans_rien_en_dire_reste_nue() -> None:
    """Les huit mots qui PRÉCÈDENT le nombre ne l'expliquent pas.

    C'est la contre-épreuve du critère « en prose, seul ce qui SUIT compte » :
    sans elle, n'importe quelle phrase longue aurait acheté son zéro.
    """
    mesure = _Mesure(
        "0 €", contexte="Le coût d'acquisition client du premier exercice est de 0 €."
    )

    assert not _zero_explique(mesure)


def test_une_annee_et_une_unite_ne_sont_pas_une_explication() -> None:
    """Sans ce retrait, « 0 € | 2026 | EUR HT » passerait pour commenté."""
    mesure = _Mesure("0 €", phrase="Emprunt | 0 € | 2026 | EUR HT", tableau=True)

    assert not _zero_explique(mesure)


# ---------------------------------------------------------------------------
# Le contrôle complet : la donnée MANQUANTE l'emporte sur toute explication
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ligne",
    [
        "Coût d'acquisition : non mesuré à ce jour, faute de campagne | 0 €",
        "Budget publicitaire : à déterminer avec la dirigeante au lancement | 0 €",
    ],
)
def test_un_zero_declare_manquant_echoue_meme_bien_entoure(ligne: str) -> None:
    """La contre-épreuve qui compte vraiment — et que j'avais d'abord ratée.

    Ces lignes ont largement de quoi « expliquer » au comptage, et elles disent
    explicitement que la donnée MANQUE. « Je ne sais pas » n'explique pas un
    zéro : c'est le défaut lui-même.

    La première version de ce test se contentait de vérifier que les regex de
    manque reconnaissaient la ligne — pas que le critère la REFUSAIT. Il
    passait donc sur un code qui acceptait « 0 € (non chiffré) », et c'est la
    contre-épreuve de `test_une_cellule_se_lit_avec_son_en_tete` qui a attrapé
    la régression. Un test qui vérifie une étape au lieu de la décision ne
    verrouille pas la décision.
    """
    assert not _zero_explique(_Mesure("0 €", phrase=ligne, tableau=True))


@pytest.mark.parametrize(
    ("avec_le_manque", "sans_le_manque"),
    [
        # Le manque annoncé APRÈS le chiffre.
        (
            "Le budget publicitaire est de 0 € : le montant reste à déterminer "
            "avec la dirigeante au moment du lancement.",
            "Le budget publicitaire est de 0 € : les clientes paient avant que "
            "les dépenses soient engagées.",
        ),
        # Et AVANT : un garde-fou qui ne lirait que l'aval le manquerait.
        (
            "Le budget publicitaire, non chiffré à ce jour, est de 0 € : la "
            "dirigeante arbitrera ce poste après les premiers ateliers.",
            "Le budget publicitaire, arrêté en septembre dernier, est de 0 € : "
            "la dirigeante arbitrera ce poste après les premiers ateliers.",
        ),
    ],
)
def test_en_prose_aussi_un_manque_annonce_n_est_pas_une_explication(
    avec_le_manque: str, sans_le_manque: str
) -> None:
    """Même règle hors tableau, et des deux côtés du nombre.

    ## Pourquoi ce test est DIFFÉRENTIEL

    Mes deux premières versions passaient sans jamais solliciter le garde-fou :
    le zéro y était en fin de phrase, là où le comptage tombe à zéro tout seul.
    Un test qui réussit pour la mauvaise raison réussirait aussi si le
    garde-fou disparaissait — c'est exactement ce que la règle 6 interdit.

    La paire le prouve : les deux phrases ne diffèrent que par l'aveu du
    manque, et le verdict change. Retirer le garde-fou fait échouer la moitié
    gauche sans toucher la droite.
    """
    assert not _zero_explique(_Mesure("0 €", contexte=avec_le_manque))
    assert _zero_explique(_Mesure("0 €", contexte=sans_le_manque)), (
        "la phrase témoin doit être acceptée, sinon le test ne prouve rien "
        "sur le garde-fou : il prouverait seulement que le comptage échoue"
    )

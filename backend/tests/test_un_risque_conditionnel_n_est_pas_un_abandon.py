"""« Risque SI non traité » n'est pas un sujet abandonné.

Stratégie Zenitek, reprise `8ad03a60` du 11/09/2026. Le contrôle des demandes
contredites a signalé le chapitre 5 : « déclare "non traité" un sujet que le
document traite ailleurs : constaté, fragilité, organisationnelle ». Ces trois
mots ne sont pas un sujet : ce sont les cellules voisines d'un tableau dont une
COLONNE s'intitule « Risque si non traité ».

La ligne ne renonce à rien — elle dit ce qui arriverait faute d'agir, ce qui est
l'inverse d'un aveu. Un motif introuvable dans le document par sa lectrice
(règle 2), sur un document par ailleurs juste, et c'est exactement ce qui a
appris à la cliente à ignorer les motifs.

Ces tests échouent sur le code d'avant, et la contre-épreuve garde le vrai
défaut — celui qu'elle avait signalé le 11/08/2026 sur les canaux d'acquisition.
"""
from __future__ import annotations

from generation.checks_post_rendu import detecter_demandes_contredites


def _chapitres(chapitre_5: str) -> list[tuple[int, str, str]]:
    return [
        (
            3,
            "Diagnostic interne",
            "La fragilité organisationnelle est constatée sur le suivi des "
            "interventions : aucune règle stable, aucun temps mesuré.",
        ),
        (5, "Synthèse du diagnostic", chapitre_5),
    ]


def test_une_colonne_risque_si_non_traite_ne_declare_aucun_abandon() -> None:
    tableau = (
        "| Constat | Risque si non traité | Échéance |\n"
        "| --- | --- | --- |\n"
        "| Fragilité organisationnelle constatée | Marge rongée | 30 jours |\n"
    )
    assert detecter_demandes_contredites(_chapitres(tableau)) == []


def test_les_autres_tournures_conditionnelles_valent_aussi() -> None:
    """Règle 4 : la classe, ce sont les conditions, pas le mot « si »."""
    for ligne in (
        "| Fragilité organisationnelle constatée | Coût en cas de non traitée |",
        "Faute d'être non traitée, la fragilité organisationnelle constatée coûte.",
        "Lorsqu'elle n'est pas traitée, la fragilité organisationnelle constatée s'aggrave.",
    ):
        assert detecter_demandes_contredites(_chapitres(ligne)) == [], ligne


def test_un_sujet_vraiment_declare_non_traite_reste_signale() -> None:
    """CONTRE-ÉPREUVE : le défaut du 11/08/2026 doit encore être vu."""
    ligne = "Analyser la fragilité organisationnelle constatée : non traitée."
    defauts = detecter_demandes_contredites(_chapitres(ligne))
    assert len(defauts) == 1
    assert defauts[0].chapitre == 5

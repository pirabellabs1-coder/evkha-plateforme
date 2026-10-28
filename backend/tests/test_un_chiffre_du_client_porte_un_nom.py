"""Un chiffre fourni par le client se cite par le NOM de son entreprise.

## Le défaut, mesuré

Le prompt ordonnait d'écrire « données du projet ». Mesuré le 28/10/2026 sur le
business plan `68fc68b4` : **105 occurrences** dans un seul document, la plupart
sous un tableau ou un chiffre clé, sous la forme « Source : données du projet ».

La cliente les classe parmi les placeholders : « Aucun texte générique ni
placeholder (« données du projet », « Figure présentée… ») ». Elle a raison —
l'étiquette ne dit ni QUI a fourni le chiffre ni CE QUE c'est.

Sa référence réécrite à la main nomme, elle : « VÉRIFIÉ FEVS », « ESTIMÉ ≈ 34 %
de 315 M€ (DG Trésor) ».

Ces tests échouent sur le code d'avant, où les trois consignes prescrivaient
littéralement « données du projet ».
"""
from __future__ import annotations

from generation.chapitres.runner import (
    CONSIGNE_DOCUMENTS_CHAPITRE,
    SOURCE_D_UN_CHIFFRE_CLIENT,
)


def _toutes_les_consignes() -> str:
    """Les textes de consigne du module qui parlent de la source d'un chiffre."""
    from generation.chapitres import runner

    return "\n".join(
        valeur for nom, valeur in vars(runner).items()
        if isinstance(valeur, str) and not nom.startswith("__") and len(valeur) > 200
    )


def test_aucune_consigne_ne_prescrit_plus_l_etiquette_opaque() -> None:
    """Le test qui échoue sur le code d'avant : trois consignes l'ordonnaient."""
    consignes = _toutes_les_consignes()
    # Elle ne subsiste que pour être INTERDITE, jamais prescrite.
    for passage in consignes.split("."):
        if "données du projet" in passage:
            assert (
                "jamais" in passage.lower() or "n'écris" in passage.lower()
            ), passage.strip()[:200]


def test_la_consigne_demande_le_nom_de_l_entreprise() -> None:
    assert "NOM DE L'ENTREPRISE" in SOURCE_D_UN_CHIFFRE_CLIENT
    assert "données internes" in SOURCE_D_UN_CHIFFRE_CLIENT


def test_une_seule_source_pour_cette_regle() -> None:
    """Règle 5 : les consignes lisent la constante, elles ne la recopient pas."""
    assert SOURCE_D_UN_CHIFFRE_CLIENT in CONSIGNE_DOCUMENTS_CHAPITRE


def test_l_intention_d_origine_est_conservee() -> None:
    """Contre-épreuve : ne pas inventer d'institut pour un chiffre du client.

    C'est la raison pour laquelle l'étiquette existait. La remplacer ne doit
    pas rouvrir le défaut qu'elle fermait.
    """
    consignes = _toutes_les_consignes()
    assert "invente pas un institut" in consignes
    assert "pas non plus comme publiés" in consignes

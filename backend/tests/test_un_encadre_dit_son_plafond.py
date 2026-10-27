"""Le plafond de six lignes est DÉCLARÉ au modèle, et il coupe toujours sans tuer.

Étude de marché à l'export, relevée par la cliente le 26/10/2026 : « dix
risques annoncés, six présentés ». Le code produisait ce mensonge tout seul :
`lignes` n'avait aucun plafond dans le schéma de l'outil, donc le modèle
écrivait dix lignes et les annonçait ; `_au_plus_six_lignes` en coupait quatre
après coup, dans un journal que personne ne lit. Un plafond qu'une moitié du
code applique et que l'autre ignore (règle 5).
"""
from __future__ import annotations

from generation.chapitres.schema import LIGNES_D_UN_ENCADRE, Encadre


def test_le_schema_envoye_au_modele_porte_le_plafond() -> None:
    """Ce que le modèle LIT : c'est le seul endroit où le plafond peut l'arrêter."""
    champ = Encadre.model_json_schema()["properties"]["lignes"]
    assert champ["maxItems"] == LIGNES_D_UN_ENCADRE
    assert champ["minItems"] == 1


def test_une_ligne_de_trop_est_coupee_pas_refusee() -> None:
    """Le chapitre 0 perdu le 11/08/2026 ne doit pas pouvoir revenir."""
    encadre = Encadre.model_validate({
        "intitule": "Dix risques majeurs",
        "lignes": [f"risque {n}" for n in range(1, 11)],
    })
    assert len(encadre.lignes) == LIGNES_D_UN_ENCADRE
    assert encadre.lignes[0] == "risque 1"


def test_un_encadre_normal_passe_intact() -> None:
    """Contre-épreuve : rien n'est touché en dessous du plafond."""
    lignes = ["Opportunité — …", "Limite — …", "Décision — …"]
    assert Encadre.model_validate({"intitule": "À retenir", "lignes": lignes}).lignes == lignes

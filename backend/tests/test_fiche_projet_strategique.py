"""La fiche projet stratégique doit porter les 37 champs de son cahier des charges.

Le document (« STRATÉGIES BUSINESS AUTOMATISÉES », p. 14-17) en fait « la base de
référence unique du livrable, le socle de cohérence stratégique, et le point de
départ de tous les arbitrages », et précise que « tous les chapitres devront être
rédigés en fonction de cette fiche projet ».

Le prompt n'en rendait que huit — et se fermait sur « Rien d'autre. », ce qui
interdisait activement les vingt-neuf autres. Or ce sont exactement les champs
sur lesquels reposent les chapitres de maturité, de dépendance au dirigeant, de
rentabilité et de charge : ils étaient rédigés sans leur donnée d'entrée.

Ces tests échouent sur le code d'avant (règle 6).
"""
from __future__ import annotations

from generation.prompt_library import prompt_instruction

CLE = "str.00.fiche_projet"

#: Les quatre blocs du document, dans son ordre, avec leurs cardinaux.
IDENTITE = (
    "Nom du projet", "Secteur", "Pays", "Zone", "Modèle économique",
    "Positionnement", "Clientèle cible", "Niveau de gamme", "Type de business",
    "Niveau de maturité",
)
STRUCTURE = (
    "Offres existantes", "Verticales", "Logique de revenus", "Revenus récurrents",
    "Activités principales", "Activités secondaires", "Dépendance au dirigeant",
    "Niveau de structuration",
)
DIRIGEANT = (
    "Vision", "Objectifs", "Ambition", "Contraintes", "Ressources disponibles",
    "Capacité de développement", "Charge actuelle", "Niveau de dispersion",
)
STRATEGIQUES = (
    "Forces", "Fragilités", "Risques", "Opportunités", "Différenciateurs",
    "Problèmes de positionnement", "Problèmes d'offre", "Problèmes de rentabilité",
    "Problèmes d'organisation", "Risques de dispersion", "Potentiel scalable",
)


def test_les_cardinaux_des_quatre_blocs_suivent_le_document() -> None:
    """10 + 8 + 8 + 11 = 37. Le prompt en rendait 8."""
    assert (len(IDENTITE), len(STRUCTURE), len(DIRIGEANT), len(STRATEGIQUES)) == (
        10, 8, 8, 11,
    )


def test_les_37_champs_sont_demandes_en_ligne_de_tableau() -> None:
    """Chaque champ doit etre une LIGNE, pas une mention en prose.

    Une enumeration en phrase laisse le modele choisir lesquels rendre ; une
    ligne de tableau prete a remplir ne le laisse pas choisir. L'ancienne fiche
    listait ses huit lignes explicitement : on suit la meme regle a 37.
    """
    prompt = prompt_instruction(CLE)

    manquants = [
        champ
        for champ in IDENTITE + STRUCTURE + DIRIGEANT + STRATEGIQUES
        if f"| {champ} |" not in prompt
    ]
    assert manquants == [], manquants


def test_les_quatre_blocs_du_document_sont_titres() -> None:
    prompt = prompt_instruction(CLE)

    for titre in (
        "## Identité du projet",
        "## Structure business",
        "## Variables dirigeant",
        "## Variables stratégiques",
    ):
        assert titre in prompt, titre


def test_un_champ_non_renseignable_est_rendu_et_non_supprime() -> None:
    """Le defaut a ne pas reintroduire : le silence.

    Un champ absent du brief doit se VOIR dans la fiche. Supprime en silence,
    il ne se comble jamais ; devine, il contamine les vingt chapitres qui
    s'appuient sur la fiche (regle 1).
    """
    prompt = prompt_instruction(CLE)

    assert "Non renseigne par le brief" in prompt
    assert "jamais invente" in prompt.lower()


def test_les_questions_implicites_sont_deduites_et_non_recopiees() -> None:
    """Le document veut « les VRAIES questions » du dirigeant, pas une liste type."""
    prompt = prompt_instruction(CLE)

    assert "## Questions auxquelles cette stratégie répond" in prompt
    assert "non recopiees" in prompt.lower() or "non recopiée" in prompt.lower()


def test_la_fiche_ne_se_ferme_plus_sur_rien_d_autre() -> None:
    """« Rien d'autre. » interdisait les 29 champs manquants.

    C'est la formule qui rendait le defaut irreparable cote modele : meme un
    modele disposant de l'information n'avait pas le droit de la rendre.
    """
    prompt = prompt_instruction(CLE)

    assert "Rien d'autre" not in prompt

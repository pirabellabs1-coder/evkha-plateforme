"""Chapitre de démonstration déterministe (développement et CI).

Comme pour le socle, le bouchon ne fabrique QUE des identifiants réellement
présents dans le prompt qu'il reçoit : il ne peut donc pas masquer une
régression du validateur en inventant des données conformes par chance.
"""
from __future__ import annotations

import re

_ID_SOCLE = re.compile(r"^- `([a-z0-9_]+)` = ", re.MULTILINE)
_NUMERO = re.compile(r"^CHAPITRE À RÉDIGER : (\d+) — (.+)$", re.MULTILINE)

_SECTEUR = re.compile(r"^SOCLE VERROUILLÉ — (.+?),", re.MULTILINE)


def _type_graphique(prompt: str, numero: int) -> str:
    """Type de graphique du chapitre, tiré du secteur lu dans le prompt.

    Le bouchon demandait toujours « barres ». Un aperçu produit en mode bouchon
    montrait donc la même figure partout, quel que soit le métier — et c'est
    précisément sur cet aperçu que la cliente juge si les visuels s'adaptent.
    Une doublure qui ne varie pas là où le vrai modèle varie ne prépare à rien.

    Le secteur n'est pas deviné : il est lu dans le bloc SOCLE du prompt, comme
    le reste de ce que ce bouchon produit.
    """
    from ..rendu_word.secteurs import graphiques_conseilles, profil_du_secteur  # noqa: PLC0415

    trouve = _SECTEUR.search(prompt)
    profil = profil_du_secteur(trouve.group(1) if trouve else "")
    types = graphiques_conseilles(profil)
    return types[numero % len(types)] if types else "barres"


_PHRASE = (
    "Cette section exploite les données verrouillées du socle et les traduit "
    "en lecture opérationnelle pour le porteur de projet, sans introduire "
    "aucun chiffre nouveau. "
)


def _resume(mots_cibles: int = 190) -> str:
    """Résumé calibré dans la fourchette 150-250 mots exigée par le contrat."""
    base = (
        "Le chapitre reprend les repères du socle et en tire les conséquences "
        "pour le projet, sans produire de chiffre nouveau. "
    )
    texte = base
    while len(texte.split()) < mots_cibles:
        texte += base
    return " ".join(texte.split()[:mots_cibles])


def chapitre_de_demonstration(prompt: str) -> dict[str, object]:
    correspondance = _NUMERO.search(prompt)
    numero = int(correspondance.group(1)) if correspondance else 0
    titre = correspondance.group(2).strip() if correspondance else "Chapitre"

    identifiants = _ID_SOCLE.findall(prompt)
    # Deux données suffisent à exercer le contrôle de filiation des graphiques
    # sans gonfler la sortie du bouchon.
    utilisees = identifiants[:2]

    graphiques: list[dict[str, object]] = []
    if len(utilisees) >= 2:
        graphiques.append(
            {
                "type": _type_graphique(prompt, numero),
                "titre": "Repères de marché",
                "donnees_ids": list(utilisees),
                "commentaire": "Graphique de démonstration.",
            }
        )

    return {
        "chapitre": numero,
        "titre": titre,
        "accroche": "Accroche de démonstration résumant l'enjeu du chapitre.",
        "encadres": [
            {
                "intitule": "Lecture du chapitre",
                "lignes": [
                    "Opportunité — le socle confirme un marché porteur.",
                    "Limite — les chiffres globaux surestiment l'accessible.",
                    "Décision — piloter sur un périmètre étroit.",
                ],
            }
        ],
        "sections": [
            {"titre": f"{numero}.1 Lecture du marché", "contenu": _PHRASE * 12},
            {"titre": f"{numero}.2 Conséquences pour le projet", "contenu": _PHRASE * 10},
        ],
        "donnees_utilisees": list(utilisees),
        "graphiques": graphiques,
        "resume": _resume(),
    }

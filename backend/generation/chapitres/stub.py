"""Chapitre de démonstration déterministe (développement et CI).

Comme pour le socle, le bouchon ne fabrique QUE des identifiants réellement
présents dans le prompt qu'il reçoit : il ne peut donc pas masquer une
régression du validateur en inventant des données conformes par chance.
"""
from __future__ import annotations

import re

_ID_SOCLE = re.compile(r"^- `([a-z0-9_]+)` = ", re.MULTILINE)

#: Identifiant ET unité : `- `marche_mondial` = 381.5 MdEUR (2025, …)`.
_ID_ET_UNITE = re.compile(r"^- `([a-z0-9_]+)` = [-\d.,]+ (\S+)", re.MULTILINE)


def _paire_homogene(prompt: str) -> list[str]:
    """Deux identifiants de MÊME unité, pris dans le socle du prompt.

    Le bouchon retenait les deux premiers venus. Or `donnees_graphiques.resoudre`
    refuse — à juste titre — de tracer ensemble des grandeurs d'unités
    différentes : un montant et un pourcentage sur le même axe ne veulent rien
    dire. Sur vingt-deux graphiques demandés, **un seul** survivait, et l'aperçu
    donnait à croire que le rendu perdait les visuels.

    À défaut de paire homogène, on rend les deux premiers : le refus reste
    possible, mais il vient alors des données, pas du bouchon.
    """
    par_unite: dict[str, list[str]] = {}
    for identifiant, unite in _ID_ET_UNITE.findall(prompt):
        par_unite.setdefault(unite, []).append(identifiant)
    for identifiants in par_unite.values():
        if len(identifiants) >= 2:
            return identifiants[:2]
    return _ID_SOCLE.findall(prompt)[:2]
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


def _tableau(numero: int, intitule: str) -> dict[str, object]:
    """Tableau de démonstration à quatre colonnes, calibré sur la référence.

    Quatre colonnes et cinq lignes : c'est l'ordre de grandeur relevé dans
    `references/joalie_2026.docx`, où 52 % des mots vivent dans des tableaux.
    """
    # Cellules COURTES. Une première version y mettait des phrases entières :
    # 5 133 mots dans les tableaux pour 4 497 au modèle, avec un tiers de
    # tableaux en moins — d'où l'impression de tableaux envahissants. Le modèle
    # tient ses cellules à quelques mots.
    entetes = ["Élément", "Constat", "Conséquence", "Décision"]
    lignes = [
        [
            f"{intitule} {rang}",
            "Repère du socle",
            "Périmètre accessible",
            "À arbitrer",
        ]
        for rang in range(1, 6)
    ]
    return {"entetes": entetes, "lignes": lignes, "source": "Jeu de démonstration"}


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

    # Deux données de MÊME unité : un montant et un pourcentage sur le même
    # axe ne veulent rien dire, et le rendu refuse le graphique à juste titre.
    utilisees = _paire_homogene(prompt)

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
        # Chaque section porte un TABLEAU. Sans lui, le bouchon ne rendait que
        # de la prose, dont le rendu ne garde qu'une amorce de 55 mots — le
        # format validé étant « des tableaux reliés par de la prose courte ».
        # L'aperçu sortait donc à moitié vide, et donnait à croire que le
        # gabarit espaçait mal, alors qu'il n'avait rien à mettre dans la page.
        # 52 % des mots du document de référence vivent dans des tableaux.
        "sections": [
            {
                "titre": f"{numero}.1 Lecture du marché",
                "contenu": _PHRASE * 12,
                "tableau": _tableau(numero, "Lecture du marché"),
            },
            {
                "titre": f"{numero}.2 Conséquences pour le projet",
                "contenu": _PHRASE * 10,
                "tableau": _tableau(numero, "Conséquences"),
            },
        ],
        "donnees_utilisees": list(utilisees),
        "graphiques": graphiques,
        "resume": _resume(),
    }

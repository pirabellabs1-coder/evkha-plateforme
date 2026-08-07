"""Chapitre de démonstration déterministe (développement et CI).

Comme pour le socle, le bouchon ne fabrique QUE des identifiants réellement
présents dans le prompt qu'il reçoit : il ne peut donc pas masquer une
régression du validateur en inventant des données conformes par chance.
"""
from __future__ import annotations

import re
from typing import Any

_ID_SOCLE = re.compile(r"^- `([a-z0-9_]+)` = ", re.MULTILINE)

#: Identifiant ET unité : `- `marche_mondial` = 381.5 MdEUR (2025, …)`.
_ID_ET_UNITE = re.compile(r"^- `([a-z0-9_]+)` = [-\d.,]+ (\S+)", re.MULTILINE)


#: Combien d'identifiants un chapitre cite, dans la doublure.
#:
#: Il en citait DEUX, quel que soit le socle — deux sur les vingt-neuf d'une
#: étude de marché comme sur les cinq d'une étude concurrentielle. La
#: répétition à blanc mesurait donc toujours la doublure, jamais le socle :
#: enrichir un référentiel de cinq à vingt-quatre données ne changeait pas
#: d'une ligne le document produit, ce qui rendait l'enrichissement
#: invérifiable autrement qu'en payant une génération réelle.
#:
#: Six, parce que c'est l'ordre de grandeur observé sur les dossiers réels, et
#: parce que c'est ce qu'il faut pour qu'un chapitre puisse porter DEUX figures
#: — la charte le demande « dès que deux idées distinctes s'y illustrent ».
_CITATIONS_PAR_CHAPITRE = 6


def _groupes_par_unite(prompt: str) -> list[list[str]]:
    """Les identifiants du socle du prompt, groupés par unité, le plus fourni d'abord."""
    par_unite: dict[str, list[str]] = {}
    for identifiant, unite in _ID_ET_UNITE.findall(prompt):
        par_unite.setdefault(unite, []).append(identifiant)
    return sorted(par_unite.values(), key=len, reverse=True)


def _paire_homogene(prompt: str) -> list[str]:
    """Deux identifiants de MÊME unité — ce qu'un GRAPHIQUE peut tracer.

    Le bouchon retenait les deux premiers venus. Or `donnees_graphiques.resoudre`
    refuse — à juste titre — de tracer ensemble des grandeurs d'unités
    différentes : un montant et un pourcentage sur le même axe ne veulent rien
    dire. Sur vingt-deux graphiques demandés, **un seul** survivait, et l'aperçu
    donnait à croire que le rendu perdait les visuels.

    Cette fonction sert les graphiques, et elle seule : lui faire rendre les six
    identifiants cités par le chapitre a produit onze abandons « unités
    hétérogènes : %, EUR » sur une seule stratégie. Ce qu'un chapitre CITE et ce
    qu'une figure TRACE ne sont pas la même chose.

    À défaut de toute paire homogène, on rend les deux premiers : le refus reste
    possible, mais il vient alors des données, pas du bouchon.
    """
    groupes = _groupes_par_unite(prompt)
    if groupes and len(groupes[0]) >= 2:
        return groupes[0][:2]
    return _ID_SOCLE.findall(prompt)[:2]


def _donnees_citees(prompt: str) -> list[str]:
    """Les identifiants que le chapitre déclare exploiter.

    Plus larges que la paire du graphique, et groupés par unité pour que la
    passe de complétion y trouve de quoi tracer : elle prend les identifiants
    dans l'ordre, et une liste mêlée ne lui donnerait que des refus.

    Essayé et REVENU : prendre trois identifiants en tête de chaque famille
    plutôt qu'une famille entière, pour que la doublure cite aussi des montants.
    Mesuré — l'étude concurrentielle tombait de dix-sept figures à seize, et le
    contrôle de hiérarchie des marchés qui motivait l'essai n'était pas
    davantage satisfait. Une doublure se règle sur ce qu'elle produit, pas sur
    ce qu'on espère d'elle.
    """
    cites: list[str] = []
    for groupe in _groupes_par_unite(prompt):
        cites.extend(groupe)
        if len(cites) >= _CITATIONS_PAR_CHAPITRE:
            break
    return cites[:_CITATIONS_PAR_CHAPITRE] or _ID_SOCLE.findall(prompt)[:2]
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
    # Calibré sur le modèle : 77 mots par tableau, soit environ quinze par
    # ligne. Une première version en mettait le double — 66 % des mots du
    # document vivaient dans les tableaux, contre 52 % au modèle, et la
    # cliente l'a lu comme « trop de tableaux ». La correction suivante est
    # tombée à 40 % : des cases de deux mots, et des tableaux qui ne disaient
    # plus rien. C'est l'entre-deux qui vaut.
    entetes = ["Élément", "Constat", "Conséquence", "Décision"]
    lignes = [
        [
            f"{intitule} {rang}",
            "Repère issu du socle verrouillé",
            "Effet sur le périmètre accessible",
            "Arbitrage à porter au plan",
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

    # Deux listes, et c'est voulu : la figure ne trace qu'une paire de MÊME
    # unité, le chapitre en CITE davantage. Les confondre produisait soit des
    # figures aux unités mêlées, soit un chapitre qui n'exploite que deux
    # chiffres sur les vingt-neuf de son socle.
    pour_les_figures = _paire_homogene(prompt)
    citees = _donnees_citees(prompt)

    return {
        "chapitre": numero,
        "titre": titre,
        "accroche": "Accroche de démonstration résumant l'enjeu du chapitre.",
        "blocs": _blocs_du_modele(numero, prompt, pour_les_figures),
        # Le validateur complète cette liste avec ce que les graphiques
        # emploient : la paire y entre donc d'elle-même si elle en sortait.
        "donnees_utilisees": list(dict.fromkeys([*citees, *pour_les_figures])),
        "resume": _resume(),
    }


def _prose(signes: int) -> str:
    """Prose de la longueur demandée, coupée sur la frontière de phrase la plus PROCHE.

    Une première version coupait sur la dernière frontière AVANT la cible. Comme
    la phrase de remplissage fait 143 signes, elle perdait jusqu'à une phrase
    entière : le volume sortait 20 % sous la cible sur dix chapitres, et le
    validateur les refusait tous — pour un défaut de la doublure, pas du moteur.
    """
    if signes <= 0:
        return _PHRASE.strip()

    long = _PHRASE * (signes // len(_PHRASE) + 2)

    # Cible plus courte qu'une phrase : couper au MOT. Le modèle porte des
    # cibles de vingt-quatre signes — le chapitre 18 en a une —, et chercher
    # une frontière de phrase y rendait six fois trop de texte.
    if signes < len(_PHRASE):
        coupe = long.rfind(" ", 0, signes)
        return (long[:coupe] if coupe > 0 else long[:signes]).strip()

    avant = long.rfind(". ", 0, signes)
    apres = long.find(". ", signes)
    candidats = [c + 1 for c in (avant, apres) if c != -1]
    if not candidats:
        return long[:signes].strip()
    coupe = min(candidats, key=lambda c: abs(c - signes))
    return long[:coupe].strip() or _PHRASE.strip()


def _blocs_du_modele(
    numero: int, prompt: str, utilisees: list[str]
) -> list[dict[str, object]]:
    """Blocs du chapitre, calqués sur le MODÈLE de référence.

    Le bouchon produisait la même forme pour les vingt-et-un chapitres : deux
    sections, deux tableaux, un encadré. Le validateur de conformité mesurait
    zéro chapitre conforme sur vingt-et-un — non par malfaçon du rendu, mais
    parce que la doublure ignorait que le modèle décrit une forme DIFFÉRENTE
    pour chacun : le chapitre 09 aligne quatre grilles de chiffres et aucun
    paragraphe, le 19 enchaîne treize tableaux et neuf encadrés.

    Une doublure qui ne varie pas là où le vrai modèle varie ne prépare à rien.
    """
    from ..modele.chargement import chapitre_du_modele  # noqa: PLC0415 — cycle

    modele = chapitre_du_modele(numero)
    if modele is None:
        # Chapitre hors modèle — la fiche projet, par exemple. On rend une
        # forme minimale plutôt que rien : c'est le validateur qui juge, pas
        # la doublure.
        return [
            {"type": "titre_sous_section", "numero": f"{numero}.1",
             "intitule": "Lecture du marché"},
            {"type": "paragraphe", "texte": _prose(380)},
        ]

    blocs: list[dict[str, object]] = []
    rang_sous_section = 0
    graphiques_places = 0
    for bloc in modele.get("blocs", []):
        type_bloc = bloc.get("type")

        if type_bloc == "titre_sous_section":
            rang_sous_section += 1
            blocs.append({
                "type": "titre_sous_section",
                "numero": str(bloc.get("numero") or f"{numero}.{rang_sous_section}"),
                "intitule": str(bloc.get("intitule_reference") or "Sous-section"),
            })
        elif type_bloc == "paragraphe":
            blocs.append({
                "type": "paragraphe",
                "texte": _prose(int(bloc.get("longueur_cible_signes", 380))),
            })
        elif type_bloc == "tableau":
            blocs.append({
                "type": "tableau",
                "tableau": _tableau_du_modele(bloc),
            })
        elif type_bloc == "encadre":
            blocs.append({
                "type": "encadre",
                "encadre": {
                    "intitule": str(bloc.get("etiquette") or "Lecture du chapitre"),
                    "lignes": [
                        "Opportunité — le socle confirme un marché porteur.",
                        "Limite — les chiffres globaux surestiment l'accessible.",
                        "Décision — piloter sur un périmètre étroit.",
                    ],
                },
            })
        elif type_bloc == "grille_kpi":
            blocs.append({
                "type": "grille_kpi",
                "cellules": [
                    {"valeur": f"{(rang + 1) * 12} %",
                     "libelle": "Repère de démonstration",
                     "source": "Jeu de démonstration"}
                    for rang in range(int(bloc.get("cellules", 3)))
                ],
            })
        elif type_bloc == "graphique" and len(utilisees) >= 2:
            graphiques_places += 1
            blocs.append({
                "type": "graphique",
                "graphique": {
                    "type": _type_graphique(prompt, numero + graphiques_places),
                    "titre": "Repères de marché",
                    "donnees_ids": list(utilisees),
                    "commentaire": "Graphique de démonstration.",
                },
            })

    return blocs or [
        {"type": "paragraphe", "texte": _prose(380)},
    ]


def _tableau_du_modele(bloc: dict[str, Any]) -> dict[str, object]:
    """Tableau aux dimensions du modèle : mêmes en-têtes, même nombre de lignes.

    Cellules COURTES. Une version antérieure y mettait des phrases entières :
    5 133 mots dans les tableaux pour 4 497 au modèle, avec un tiers de tableaux
    en moins — d'où l'impression de tableaux envahissants signalée par la
    cliente.
    """
    entetes = [str(e) for e in (bloc.get("entetes") or [])] or ["Élément", "Constat"]
    lignes_voulues = max(int(bloc.get("nb_lignes_cible", 3) or 3), 1)
    remplissage = ["Repère du socle", "Périmètre accessible", "À arbitrer",
                   "Sous conditions", "À mesurer", "En attente", "Confirmé"]
    lignes = [
        [f"Élément {rang}", *[remplissage[(rang + c) % len(remplissage)]
                              for c in range(len(entetes) - 1)]]
        for rang in range(1, lignes_voulues + 1)
    ]
    return {"entetes": entetes, "lignes": lignes, "source": "Jeu de démonstration"}

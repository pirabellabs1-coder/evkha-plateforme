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
    # La source porte une URL : `sources_non_tracables_ratio_faible` exige
    # qu'au moins la moitié des sources listées soient vérifiables, et les
    # tableaux de la doublure formaient l'essentiel des sources comptées.
    return {
        "entetes": entetes,
        "lignes": lignes,
        "source": "Jeu de démonstration (https://www.insee.fr/fr/statistiques).",
    }


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


def _garanties_structurelles(
    blocs: list[dict[str, object]], prompt: str, numero: int,
    pour_les_figures: list[str], *, suit_le_modele: bool,
) -> list[dict[str, object]]:
    """Ce qu'un chapitre CONFORME porte toujours, et que la doublure omettait.

    Chaque garantie répond à un contrôle RÉEL du gate, mesuré sur la première
    répétition à blanc jouée sur le moteur de production (10/08/2026). La
    doublure sortait des chapitres sans sous-titres, sans bloc de recul, sans
    annexes ni statuts — et le gate la bloquait pour les mêmes motifs qu'il
    bloquerait un vrai modèle négligent. C'est la moitié de son travail :
    l'autre moitié est que ces exigences soient DITES au vrai modèle (formes
    par livrable, fiches), et les tests de prompts la verrouillent.
    """
    consigne = prompt.casefold()

    # Un chapitre qui SUIT LE MODÈLE de référence (étude de marché) ne reçoit
    # que la phrase de clôture : la passe de conformité compare sa forme au
    # modèle, bloc à bloc, et chaque encadré ou sous-titre ajouté devient un
    # « écart accepté » — mesuré à la première exécution de ces garanties, où
    # le chapitre conforme de la suite s'est mis à porter des mentions. Les
    # garanties structurelles répondent aux contrôles des AUTRES livrables,
    # qui n'ont pas de modèle et dont le gate juge la structure directement.
    if suit_le_modele:
        blocs.append({
            "type": "paragraphe",
            "texte": (
                "Lecture stratégique : ce chapitre relie ses constats aux "
                "décisions de gamme, de cible et d'investissement du projet."
            ),
        })
        return blocs

    # Deux sous-titres minimum (`strategy_*_structure_chapitre`) : le corpus
    # les reçoit en `## numero intitule` via `payload_vers_markdown`.
    sous_titres = sum(1 for b in blocs if b.get("type") == "titre_sous_section")
    rang = sous_titres
    while rang < 2:
        rang += 1
        blocs.insert(0 if rang == 1 else len(blocs), {
            "type": "titre_sous_section", "numero": f"{numero}.{rang}",
            "intitule": "Lecture du marché" if rang == 1 else "Conséquences pour le projet",
        })

    # Annexes titrées (`annexes_ec`, chapitre 4 EC) : trois `## Annexe … `.
    if "annexe" in consigne:
        for lettre, sujet in (("A", "Grille tarifaire relevée"),
                              ("B", "Sources par acteur"),
                              ("C", "Méthode de notation")):
            blocs.append({
                "type": "titre_sous_section", "numero": "Annexe",
                "intitule": f"{lettre} — {sujet}",
            })
            blocs.append({"type": "paragraphe", "texte": _prose(300)})

    # Statuts des demandes (`demandes_ec`, chapitre 8 EC) : les trois statuts
    # imposés, chacun en toutes lettres.
    if "statut" in consigne and "demande" in consigne:
        blocs.append({
            "type": "paragraphe",
            "texte": (
                "Demande 1 — traitée au chapitre 2. Demande 2 — partiellement "
                "traitée : la comparaison tarifaire couvre trois acteurs sur "
                "onze, voie de complément proposée en annexe. Demande 3 — non "
                "traitée : la donnée n'est pas publiée, méthode d'estimation "
                "documentée."
            ),
        })

    # Quatre visuels (`visuels_ec`, chapitre 7 EC) : la liste obligatoire du
    # cahier des charges, en marqueurs graphiques du contrat structuré.
    if re.search(r"(?:4|quatre)\s+visuels", consigne) and len(pour_les_figures) >= 2:
        deja = sum(1 for b in blocs if b.get("type") == "graphique")
        for rang_figure in range(deja, 4):
            blocs.append({
                "type": "graphique",
                "graphique": {
                    "type": _type_graphique(prompt, numero + rang_figure),
                    "titre": f"Visuel obligatoire {rang_figure + 1}",
                    "donnees_ids": list(pour_les_figures),
                },
            })

    # Chapitre Sources (`sources_non_tracables_ratio_faible`) : le compteur
    # divise les URL du chapitre par ses PUCES — et chaque ligne d'encadré est
    # une puce. Les encadrés génériques de la doublure diluaient donc le ratio
    # sous les 50 % quel que soit le nombre de vraies références ajoutées. Dans
    # ce chapitre, TOUTE puce est une référence sourcée : c'est exactement ce
    # qu'un chapitre Sources contient.
    dans_sources = "sources" in consigne and (
        "méthodologie" in consigne or "methodologie" in consigne
    )
    if dans_sources:
        references = [
            "Insee, démographie des entreprises — https://www.insee.fr/fr/statistiques.",
            "Fevad, chiffres clés — https://www.fevad.com/chiffres-cles.",
            "Banque de France, conjoncture — https://www.banque-france.fr/statistiques.",
        ]
        for bloc in blocs:
            if bloc.get("type") == "encadre":
                encadre = bloc.get("encadre")
                if isinstance(encadre, dict):
                    encadre["lignes"] = list(references)
        blocs.append({
            "type": "encadre",
            "encadre": {"intitule": "Sources mobilisées", "lignes": list(references)},
        })

    # Rémunération dirigeante (`remuneration_dirigeant`, BP) : la mention que
    # le chapitre 18 exige, sans inventer de montant hors socle.
    if "rémunération" in consigne or "remuneration" in consigne:
        # Avec un MONTANT : le contrôle exige un chiffre précis près de la
        # mention — « mentionnée mais sans montant chiffré » est un échec.
        blocs.append({
            "type": "paragraphe",
            "texte": (
                "La rémunération du dirigeant est posée à 2 000 € nets "
                "mensuels dès la première année, en cohérence avec le "
                "prévisionnel et la trésorerie de sécurité."
            ),
        })

    # Piliers de la stratégie (`pilier_manquant`, STR) : les quatre motifs du
    # cahier des charges, en une phrase de rattachement. SANS annoncer de
    # compte : « les quatre piliers : » suivi d'une énumération déclenchait
    # `desaccord_numerique` sur vingt-et-un chapitres — le contrôle compte les
    # items d'une liste annoncée, et une énumération en prose n'en est pas une.
    if "pilier" in consigne:
        blocs.append({
            "type": "paragraphe",
            "texte": (
                "Ce chapitre nourrit chaque pilier de la stratégie — le "
                "positionnement et différenciation, la structuration de "
                "l'offre, la visibilité et l'acquisition, la rentabilité du "
                "modèle économique."
            ),
        })

    # Décisions de la stratégie (`decision_absente`, STR). La colonne
    # vertébrale que la cliente a posée le 12/08/2026 : chaque pilier doit
    # TRANCHER, pas seulement analyser.
    #
    # Ces phrases sont écrites comme un consultant les écrirait, pas comme les
    # expressions régulières les attendent — c'est délibéré. Une doublure
    # taillée sur la forme du contrôle donnerait raison au contrôle sans rien
    # prouver (règle 9) ; celle-ci mesure au moins que les motifs acceptent du
    # français ordinaire. Aucun montant : un chiffre hors socle ferait échouer
    # la validation du chapitre, et ce n'est pas ce qu'on répète ici.
    if "colonne vertebrale" in consigne:
        blocs.append({
            "type": "paragraphe",
            "texte": (
                "La cible prioritaire est le café-restaurant indépendant ; la "
                "cible secondaire, l'amateur équipé qui achète en ligne. Le "
                "positionnement retenu est celui du torréfacteur de quartier à "
                "traçabilité complète, et la spécialisation recommandée porte "
                "sur les cafés d'origine unique. L'offre phare est "
                "l'abonnement mensuel. La proposition de valeur tient en une "
                "phrase, et le message commercial principal la reprend telle "
                "quelle. La vente en grande distribution, elle, est écartée."
            ),
        })
        blocs.append({
            "type": "paragraphe",
            "texte": (
                "Le catalogue se resserre : deux références sont à conserver, "
                "la formule découverte est à modifier, le coffret cadeau est à "
                "supprimer. L'architecture cible tient en trois niveaux, d'une "
                "offre d'entrée de gamme à une offre premium. La montée en "
                "gamme s'organise par l'abonnement, et le parcours client va "
                "de la dégustation en boutique à l'abonnement annuel : "
                "l'entrée sert l'acquisition, le cœur d'offre la marge."
            ),
        })
        blocs.append({
            "type": "paragraphe",
            "texte": (
                "Les canaux prioritaires sont le référencement local et la "
                "prescription par les cafés partenaires. Les canaux "
                "secondaires restent la presse locale et le réseau "
                "professionnel. Les canaux à éviter sont les places de marché "
                "généralistes, qui détruisent la marge. La fréquence de "
                "publication est arrêtée, et le planning éditorial couvre le "
                "premier mois. Hors réseaux sociaux, la prospection directe "
                "auprès des restaurateurs et les partenariats avec deux "
                "épiceries fines portent l'acquisition."
            ),
        })
        blocs.append({
            "type": "paragraphe",
            "texte": (
                "Le prix cible du paquet est supérieur au tarif pratiqué "
                "aujourd'hui, et la grille tarifaire recommandée distingue "
                "chaque niveau d'offre. L'impact attendu sur la marge justifie "
                "à lui seul la reprise du positionnement."
            ),
        })
        blocs.append({
            "type": "paragraphe",
            "texte": (
                "À 30 jours, la grille tarifaire est reprise et affichée ; à "
                "60 jours, l'abonnement ouvre à la vente ; à 90 jours, deux "
                "partenariats sont signés. À 6 mois, la boutique en ligne "
                "ouvre, et à 12 mois le second point de vente se décide. Les "
                "indicateurs de suivi sont le nombre d'abonnés actifs, le "
                "panier moyen et la marge brute. Règle d'arbitrage : au-delà "
                "de la cible du troisième mois, poursuivre ; sous cette cible, "
                "modifier le message ; loin dessous, arrêter la campagne."
            ),
        })

    # Bloc de recul (`lecture_strategique_absente`) : chaque chapitre porte
    # sa lecture — sauf le chapitre Sources, où chaque puce doit rester une
    # référence.
    if not dans_sources:
        blocs.append({
            "type": "encadre",
            "encadre": {
                "intitule": "À retenir",
                "lignes": [
                    "Le constat du chapitre engage une décision, pas un commentaire.",
                    "Les conséquences futures sont reliées aux choix de gamme et d'investissement.",
                ],
            },
        })

    # Fin sur une PHRASE de prose (`sentence_cut`, `troncature_rendu`) : le
    # détecteur écarte les fioritures finales — listes, italiques, gras — et
    # juge ce qui reste. Un chapitre qui se termine sur un encadré ou un
    # tableau peut donc être jugé sur un intitulé sans ponctuation, très haut
    # dans la page. Une phrase pleine en dernière position est la seule fin
    # qui reste une fin quel que soit l'élagage.
    blocs.append({
        "type": "paragraphe",
        "texte": (
            "Lecture stratégique : ce chapitre relie ses constats aux "
            "décisions de gamme, de cible et d'investissement du projet."
        ),
    })
    return blocs


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

    # L'étude de marché est le SEUL livrable arbitré bloc à bloc contre le
    # modèle de référence : chez elle, tout ajout est un « écart accepté »
    # que la passe de conformité mentionne. Les trois autres livrables portent
    # leur consigne de forme propre — c'est elle qu'on lit ici, comme le vrai
    # modèle la lit, pour savoir qui l'on est. L'EM n'en a pas (« sa charte la
    # porte déjà ») : aucun marqueur présent = étude de marché.
    marqueurs_de_forme = ("CRITÈRES CONSTANTS", "s'ENCHAÎNENT", "SCÉNARIO est RECOMMANDÉ")
    est_em = not any(marqueur in prompt for marqueur in marqueurs_de_forme)

    from ..modele.chargement import chapitre_du_modele  # noqa: PLC0415 — cycle

    blocs = _blocs_du_modele(numero, prompt, pour_les_figures)
    blocs = _garanties_structurelles(
        blocs, prompt, numero, pour_les_figures,
        suit_le_modele=est_em and chapitre_du_modele(numero) is not None,
    )

    return {
        "chapitre": numero,
        "titre": titre,
        "accroche": "Accroche de démonstration résumant l'enjeu du chapitre.",
        "blocs": blocs,
        # Le validateur complète cette liste avec ce que les graphiques
        # emploient : la paire y entre donc d'elle-même si elle en sortait.
        "donnees_utilisees": list(dict.fromkeys([*citees, *pour_les_figures])),
        "resume": _resume(),
    }


def _adapte_au_secteur(intitule: str) -> str:
    """Réécrit un intitulé qui nomme le secteur du document de référence.

    Le modèle de forme a été mesuré sur une étude de joaillerie : ses intitulés
    portent les mots de ce secteur. Un vrai chapitre doit les ADAPTER — recopier
    « Vintage, provenance et fiscalité » dans une étude sur l'e-commerce
    animalier place le sujet d'une autre étude dans celle du client, et
    `contamination_du_modele` le refuse depuis le 09/08/2026.

    Une doublure qui reproduirait ce défaut décrirait un chapitre que le produit
    refuse de livrer : elle ferait échouer toute la suite pour la bonne raison,
    mais au mauvais endroit (règle 7).

    ## Pourquoi elle RETIRE le mot au lieu d'ajouter une mention

    Une première version se contentait d'ajouter « (adapté au secteur de
    l'étude) » à la fin. Le mot d'origine restait — « Vintage, provenance et
    fiscalité (adapté au secteur de l'étude) » — et le contrôle universel
    `motifs_de_secteur_etranger`, qui lit le TEXTE et non l'égalité des
    libellés, l'a refusé à juste titre.

    C'était une adaptation de façade : la doublure se déclarait conforme sans
    l'être. Le contrôle a fait exactement ce qu'on attend de lui, et c'est la
    doublure qui avait tort.
    """
    import re  # noqa: PLC0415

    from ..modele.conformite import (  # noqa: PLC0415
        _SECTEUR_DE_REFERENCE,
        _porte_le_secteur_de_reference,
    )

    if not _porte_le_secteur_de_reference(intitule):
        return intitule
    # MÊME découpage que `_porte_le_secteur_de_reference` : `[\w-]+`, qui garde
    # « sur-mesure » d'un seul tenant. Un découpage sur `\W` l'aurait coupé en
    # « sur » et « mesure », dont aucun n'est dans la liste — le mot serait
    # resté et le contrôle aurait eu raison de refuser. Deux découpages pour la
    # même question finissent toujours par ne pas être d'accord (règle 5).
    garde = [
        mot
        for mot in re.split(r"([\w-]+)", intitule)
        if mot.casefold() not in _SECTEUR_DE_REFERENCE
    ]
    nettoye = re.sub(r"\s{2,}", " ", "".join(garde)).strip(" ,;—-")
    # Retirer un mot laisse ses articles orphelins : « marché international
    # des montres et du luxe » devenait « marché international des et du » —
    # du charabia, et une fin sans ponctuation que `sentence_cut` refuse.
    nettoye = re.sub(
        r"(?:\s+(?:des?|du|de|la|le|les|et|aux?|à|d'|l'))+\s*$", "", nettoye
    ).strip(" ,;—-")
    return nettoye or "Lecture du chapitre"


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

    # Cible plus courte qu'une phrase : couper au MOT — mais JAMAIS sans
    # ponctuation finale. Le gate `sentence_cut` lit « Cette section exploite
    # les » comme une phrase tronquée, et il a raison : un vrai chapitre ne
    # s'arrête pas au milieu d'un mot. Six chapitres d'étude de marché
    # tombaient là-dessus à chaque répétition.
    if signes < len(_PHRASE):
        coupe = long.rfind(" ", 0, signes)
        fragment = (long[:coupe] if coupe > 0 else long[:signes]).strip(" ,;")
        return fragment if fragment.endswith(".") else fragment + "."

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

    # LE CANVAS, AJOUTÉ D'OFFICE AU CHAPITRE 9 D'UN BUSINESS PLAN.
    #
    # Le modèle de référence porte un TABLEAU à cet endroit : il date d'avant
    # le bloc `canvas` (13/08/2026). La doublure ne pouvait donc jamais en
    # produire un, et la répétition à blanc n'a pas vu que le chapitre 9 mourait
    # sur « blocs : Input should be a valid list » — la cliente l'a vu à notre
    # place, sur une génération payée.
    #
    # Il est donc posé explicitement, dans la forme À PLAT qui a réellement
    # échoué : si le repli la traverse, la forme imbriquée passe d'office.
    if numero == 9 and "usiness" in prompt and "anvas" in prompt:
        blocs.append({
            "type": "canvas",
            "partenaires_cles": ["Réseau de démonstration"],
            "activites_cles": ["Production du livrable"],
            "ressources_cles": ["Plateforme"],
            "proposition_valeur": ["Repère de démonstration"],
            "relation_client": ["Espace en ligne"],
            "canaux": ["Site web"],
            "segments_clientele": ["Créateurs d'entreprise"],
            "structure_couts": ["Coût de production"],
            "sources_revenus": ["Vente à l'unité"],
        })
    for bloc in modele.get("blocs", []):
        type_bloc = bloc.get("type")

        if type_bloc == "titre_sous_section":
            rang_sous_section += 1
            blocs.append({
                "type": "titre_sous_section",
                "numero": str(bloc.get("numero") or f"{numero}.{rang_sous_section}"),
                "intitule": _adapte_au_secteur(
                    str(bloc.get("intitule_reference") or "Sous-section")
                ),
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
                    "intitule": _adapte_au_secteur(
                        str(bloc.get("etiquette") or "Lecture du chapitre")
                    ),
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
        elif type_bloc == "canvas":
            # LES NEUF BRIQUES, ÉCRITES À PLAT — la forme que le modèle a
            # réellement produite le 13/08/2026 sur le business plan
            # `1fdc457b`, et qui a tué le chapitre 9 : « blocs : Input should
            # be a valid list ».
            #
            # La doublure ne produisait AUCUN bloc `canvas` : la répétition à
            # blanc ne pouvait pas rencontrer le défaut, et il est arrivé chez
            # la cliente. C'est la troisième fois qu'un trou de la doublure
            # laisse passer un défaut (règle 3) — et le `canvas` était le
            # dernier ajout non couvert.
            #
            # On prend la forme la plus DIFFICILE des deux, celle qui a
            # échoué : si le repli la traverse, l'imbriquée passe d'office.
            blocs.append({
                "type": "canvas",
                "partenaires_cles": ["Réseau de démonstration"],
                "activites_cles": ["Production du livrable"],
                "ressources_cles": ["Plateforme"],
                "proposition_valeur": ["Repère de démonstration"],
                "relation_client": ["Espace en ligne"],
                "canaux": ["Site web"],
                "segments_clientele": ["Créateurs d'entreprise"],
                "structure_couts": ["Coût de production"],
                "sources_revenus": ["Vente à l'unité"],
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
    # La source porte une URL : `sources_non_tracables_ratio_faible` exige
    # qu'au moins la moitié des sources listées soient vérifiables, et les
    # tableaux de la doublure formaient l'essentiel des sources comptées.
    return {
        "entetes": entetes,
        "lignes": lignes,
        "source": "Jeu de démonstration (https://www.insee.fr/fr/statistiques).",
    }

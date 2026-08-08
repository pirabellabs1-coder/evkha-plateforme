"""Rendu d'un livrable à partir d'un fichier JSON d'étude.

Le générateur ne fait qu'appeler les composants dans l'ordre décrit par le
JSON. Aucune logique éditoriale ici : un bloc porte son type et ses données.

Types de blocs : `bandeau`, `sous_titre`, `paragraphe`, `encadre`, `tableau`,
`graphique`, `kpi`, `liste`, `quadrants`, `repartition`, `saut`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from docx.document import Document as DocumentWord

from . import composants, graphiques
from .assemblage import MENTION_PAR_DEFAUT
from .gabarit import charger_gabarit
from .logo import charger_logo
from .palette import Palette, construire_palette


class BlocInconnuError(ValueError):
    """Le JSON déclare un type de bloc que le moteur ne sait pas rendre."""


def pour_le_client(chapitre: dict[str, Any]) -> bool:
    """Ce chapitre part-il chez le client ?

    Le chapitre 0 est la FICHE PROJET : la carte d'identité interne de la
    commande — reformulation du brief, questions implicites, budget, points
    sensibles, contraintes. Le manuel en fait « la mémoire de l'étude », relue
    par l'analyste avant chaque bloc, et son contrôle final exige que « les
    contrôles internes soient retirés du livrable client ».

    Elle était exclue du SOMMAIRE — `if chapitre["numero"] > 0` — et rendue
    dans le CORPS, la boucle suivante ne filtrant rien. L'étude s'ouvrait donc
    sur une section que sa propre table des matières ignore : l'asymétrie
    montre l'oubli, personne ne choisit d'imprimer un chapitre invisible au
    sommaire.

    Exporté et appelé aux deux endroits : deux filtres pour une même question
    finissent par diverger, et c'est cette divergence-là qui a produit le
    défaut (règle 5). `verification/services._chapitres_attendus` applique la
    même règle sur le blueprint, faute de quoi le contrôle d'intégrité
    réclamerait un chapitre qu'on vient de ne plus écrire (règle 3).
    """
    return int(chapitre["numero"]) > 0


def substituer_reperes(gabarit: str, valeurs: dict[str, str]) -> str:
    """Substitue les repères, et fait disparaître les séparateurs orphelins.

    L'en-tête du gabarit vaut `{{ client }}  /  {{ titre_document }}`. Quand le
    client ne remplit pas `NOM_ENTREPRISE` — le champ est optionnel et
    `extract_branding` rend alors `""` — la substitution naïve laissait
    « ` /  Étude de marché` » **sur chacune des soixante-dix pages**. Mesuré sur
    le dossier réel `b561c2d6`.

    Le repli qui aurait dû l'éviter, `marque.get("nom", "—")`, n'a jamais servi :
    la clé EXISTE, avec une valeur vide, et `dict.get` ne regarde que l'absence.
    Un défaut de la classe « valeur par défaut qui ne se déclenche jamais ».

    La correction vise la CLASSE (règle 4) : tout repère vide emporte le
    séparateur qui le borde, quel que soit le repère et de quel côté. Elle ne
    touche RIEN quand la valeur est renseignée — un titre contenant lui-même une
    barre oblique (« Étude B2B/B2C ») traverse intact, ce que vérifie la
    contre-épreuve de `test_l_entete_ne_garde_pas_de_separateur_orphelin`.
    """
    texte = gabarit
    for repere, valeur in valeurs.items():
        if valeur:
            continue
        echappe = re.escape(repere)
        texte = re.sub(rf"{echappe}\s*/\s*", "", texte)
        texte = re.sub(rf"\s*/\s*{echappe}", "", texte)
        texte = texte.replace(repere, "")
    for repere, valeur in valeurs.items():
        texte = texte.replace(repere, valeur)
    return texte.strip()


def _remplacer_reperes(document: DocumentWord, valeurs: dict[str, str]) -> None:
    for section in document.sections:
        for zone in (section.header, section.footer):
            for paragraphe in zone.paragraphs:
                for run in paragraphe.runs:
                    if any(repere in run.text for repere in valeurs):
                        run.text = substituer_reperes(run.text, valeurs)


def _rendre_bloc(
    document: DocumentWord, palette: Palette, bloc: dict[str, Any]
) -> None:
    type_bloc = bloc.get("type", "")

    if type_bloc == "bandeau":
        composants.bandeau_chapitre(
            document, palette, int(bloc["numero"]), bloc["titre"],
            bloc.get("accroche", ""),
        )
    elif type_bloc == "sous_titre":
        composants.sous_titre(document, palette, bloc["texte"])
    elif type_bloc == "paragraphe":
        composants.paragraphe(document, palette, bloc["texte"])
    elif type_bloc == "encadre":
        composants.encadre(
            document, palette, bloc["libelle"], bloc["lignes"],
            verdict=bool(bloc.get("verdict", False)),
        )
    elif type_bloc == "tableau":
        composants.tableau(
            document, palette, bloc["entetes"], bloc["lignes"],
            bloc.get("source", ""),
        )
    elif type_bloc == "kpi":
        composants.grille_chiffres(
            document, palette, [tuple(item) for item in bloc["chiffres"]]
        )
    elif type_bloc == "liste":
        composants.liste(document, palette, bloc["elements"])
    elif type_bloc == "quadrants":
        composants.matrice_quadrants(
            document, palette,
            [(case["intitule"], case["lignes"]) for case in bloc["cases"]],
        )
    elif type_bloc == "repartition":
        composants.barre_repartition(
            document, palette,
            [(part["libelle"], float(part["valeur"])) for part in bloc["parts"]],
            bloc.get("source", ""),
        )
    elif type_bloc == "graphique":
        # Le titre est dessiné DANS l'image, comme dans le document validé : la
        # figure reste lisible seule, une fois sortie du document. Il n'est donc
        # plus passé au composant, qui en faisait un paragraphe au-dessus — deux
        # titres pour une même figure.
        png = graphiques.rendre(
            palette, bloc["graphique"], bloc["donnees"], titre=bloc.get("titre", "")
        )
        composants.graphique(document, palette, png, "", bloc.get("source", ""))
    elif type_bloc == "saut":
        composants.saut_de_page(document)
    else:
        msg = f"Type de bloc inconnu : {type_bloc!r}."
        raise BlocInconnuError(msg)


def rendre_etude(etude: dict[str, Any], destination: Path) -> Path:
    """Produit le `.docx` complet d'une étude décrite en JSON."""
    marque = etude.get("marque", {})
    palette = construire_palette(
        primaire=marque.get("couleur_principale", ""),
        secondaire=marque.get("couleur_secondaire", ""),
        fond_clair=marque.get("couleur_fond", ""),
    )

    document = charger_gabarit()
    _remplacer_reperes(
        document,
        {
            # Pas de repli « — » : il n'a jamais pu se declencher, la cle etant
            # toujours posee par `marque_du_job`, et il aurait imprime un tiret
            # a la place du nom. Un nom vide efface desormais son separateur.
            "{{ client }}": marque.get("nom", ""),
            "{{ titre_document }}": etude.get("titre", ""),
            # Repli NEUTRE : « EVKHA · Document confidentiel » y figurait, et
            # un document en marque blanche ne doit nommer que son abonné.
            "{{ mention_confidentialite }}": etude.get(
                "mention", MENTION_PAR_DEFAUT
            ),
        },
    )

    # `logo` (octets déjà chargés) l'emporte sur `logo_url` : cela permet de
    # rendre un document en test sans aucun accès réseau.
    octets_logo = etude.get("logo")
    if octets_logo is None and marque.get("logo_url"):
        octets_logo = charger_logo(str(marque["logo_url"]))

    composants.couverture(
        document, palette,
        titre=etude.get("titre", ""),
        sous_titre=etude.get("sous_titre", ""),
        client=marque.get("nom", ""),
        mention=etude.get("mention", "Document confidentiel"),
        logo=octets_logo,
    )

    chapitres = [c for c in etude.get("chapitres", []) if pour_le_client(c)]

    entrees = [(f"{c['numero']:02d}", c["titre"], "") for c in chapitres]
    if entrees:
        composants.sommaire(document, palette, entrees)
        composants.saut_de_page(document)

    for index, chapitre in enumerate(chapitres):
        for bloc in chapitre.get("blocs", []):
            _rendre_bloc(document, palette, bloc)
        if index < len(chapitres) - 1:
            composants.saut_de_page(document)

    composants.quatrieme_couverture(
        document, palette,
        # Idem : aucune mention de la plateforme en repli.
        mentions=etude.get("mentions_finales", [MENTION_PAR_DEFAUT]),
    )

    _signer_le_document(
        document,
        auteur=str(marque.get("nom", "")).strip(),
        titre=str(etude.get("titre", "")).strip(),
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(destination))
    return destination


def _signer_le_document(document: Any, *, auteur: str, titre: str) -> None:
    """Renseigne les propriétés que Word affiche dans « Informations ».

    Elles portaient les valeurs par défaut de la bibliothèque :
    `dc:creator = python-docx` et `dc:description = generated by python-docx`.
    Le client final de l'abonné les lit d'un clic, et y découvre l'outil qui a
    produit son étude — pas le nom de l'agence qui la lui remet.

    Ce n'est pas la même fuite que les styles nommés, mais c'est la même
    classe : tout ce que le lecteur peut voir du fichier doit parler de
    l'abonné, jamais de la chaîne de fabrication (règle 4).

    L'auteur n'est **pas inventé** quand la raison sociale manque : on efface
    plutôt que d'écrire un nom de repli, qui serait faux et le resterait.
    """
    proprietes = document.core_properties
    proprietes.author = auteur
    proprietes.last_modified_by = auteur
    proprietes.title = titre
    proprietes.comments = ""
    # `category` et `company` ne sont pas exposés par python-docx ; les champs
    # ci-dessus sont ceux que Word montre par défaut.


def rendre_depuis_fichier(chemin_json: Path, destination: Path) -> Path:
    etude = json.loads(Path(chemin_json).read_text(encoding="utf-8"))
    return rendre_etude(etude, destination)

"""Rendu d'un livrable à partir d'un fichier JSON d'étude.

Le générateur ne fait qu'appeler les composants dans l'ordre décrit par le
JSON. Aucune logique éditoriale ici : un bloc porte son type et ses données.

Types de blocs : `bandeau`, `sous_titre`, `paragraphe`, `encadre`, `tableau`,
`graphique`, `kpi`, `liste`, `quadrants`, `repartition`, `saut`.
"""
from __future__ import annotations

import json
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


def _remplacer_reperes(document: DocumentWord, valeurs: dict[str, str]) -> None:
    for section in document.sections:
        for zone in (section.header, section.footer):
            for paragraphe in zone.paragraphs:
                for run in paragraphe.runs:
                    for repere, valeur in valeurs.items():
                        if repere in run.text:
                            run.text = run.text.replace(repere, valeur)


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
        png = graphiques.rendre(palette, bloc["graphique"], bloc["donnees"])
        composants.graphique(
            document, palette, png, bloc.get("titre", ""), bloc.get("source", "")
        )
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
            "{{ client }}": marque.get("nom", "—"),
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

    entrees = [
        (f"{chapitre['numero']:02d}", chapitre["titre"], "")
        for chapitre in etude.get("chapitres", [])
        if chapitre["numero"] > 0
    ]
    if entrees:
        composants.sommaire(document, palette, entrees)
        composants.saut_de_page(document)

    chapitres = etude.get("chapitres", [])
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

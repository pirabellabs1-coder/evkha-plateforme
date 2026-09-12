"""La sortie des commandes ne doit pas dépendre de la console qui les lance.

## Le défaut mesuré

12/08/2026 : lancée depuis un terminal Windows, `repetition_a_blanc` s'arrête
sur `UnicodeEncodeError: 'charmap' codec can't encode characters` — sur la
ligne de séparation `═══` et sur les accents de « passé ». Rien à voir avec la
chaîne testée : c'est le RAPPORT qui ne s'imprime pas, et la commande sort en
erreur sans avoir rien dit.

Une étape obligatoire qui plante sur la console standard finit par être
contournée, puis oubliée — c'est exactement l'histoire de Gamma dans ce dépôt :
intégré, testé, branché, et jamais exécuté.

On reconfigure donc la sortie plutôt que d'appauvrir le rapport : un tableau
lisible vaut mieux qu'un tableau qui passe partout.

## Pourquoi ce module existe

La fonction vivait dans `repetition_a_blanc`. La deuxième commande à imprimer
un rapport accentué (`mesurer_livrable`, 12/09/2026) est tombée sur le même
mur, et la recopier aurait fait deux versions d'une même vérité — ce que la
règle 5 du dépôt interdit, parce que chaque défaut majeur d'ici vient de deux
modules qui ne sont pas d'accord.
"""
from __future__ import annotations

import sys


def console_en_utf8() -> None:
    """Passe stdout et stderr en UTF-8, sans échouer si c'est impossible."""
    for flux in (sys.stdout, sys.stderr):
        reconfigurer = getattr(flux, "reconfigure", None)
        if reconfigurer is not None:
            try:
                reconfigurer(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                # Flux capturé par un test ou redirigé : il n'y a rien à
                # reconfigurer, et ce n'est pas une raison d'échouer.
                pass

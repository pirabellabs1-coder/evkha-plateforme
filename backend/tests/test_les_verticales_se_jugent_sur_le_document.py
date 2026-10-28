"""Le gate bloquait un business plan qui traitait ses trois verticales 188 fois.

## Le motif faux

Business plan `fedb76a1` (28/10/2026) : `qa_status: blocked`, et **un seul**
motif de gate — `brief_non_lu`, sur les verticales d'activité. Son texte :

    « Le brief liste des verticales d'activité que la lecture automatique n'a
      pas retenues : rien ne garantit qu'elles figurent dans le livrable. »

Deux défauts dans cette seule phrase :

1. « rien ne garantit » est une propriété de NOTRE extraction, pas du
   document. Le check échouait dès que le fait `verticales` manquait en base.
2. Son `extrait` était **vide**. Un motif d'échec doit être trouvable dans le
   document par le lecteur (règle 2) ; celui-ci n'avait rien à montrer.

Et la mesure tranche. Le brief nomme Parenthèses, Échappées et Élans ; le
document livré les cite **51, 71 et 66 fois**, et une phrase les traite
ensemble :

    « L'offre est organisée en trois univers : les Parenthèses (ateliers
      courts dans le Val-d'Oise), les Échappées (week-ends dans un lieu
      nature) et les Élans (parcours de transition de vie). »

C'était le SEUL motif qui bloquait ce livrable.

## Ce qui est gardé

L'intention du check est réelle — c'est le défaut SYNAPSES, trois verticales
effacées au profit d'un modèle générique. On la garde en jugeant ce que le
LECTEUR reçoit (règle 3), et en échouant bruyamment quand on ne peut
vraiment pas juger : un brief dont aucun nom n'est lisible échoue comme avant
(règle 1).

Ces tests échouent sur le code d'avant : il bloquait sans jamais regarder le
document.
"""
from __future__ import annotations

import pytest

from generation.gate import _noms_de_verticales, _verticales_absentes_du_document

#: Recopié du brief réel de `fedb76a1`, lu par `jobs/<id>/brief/`.
BRIEF_REEL = """CHIFFRE_AFFAIRES : trajectoire par univers
VERTICALES D'ACTIVITÉS (CA TTC 2027, 2028, 2029) :
Parenthèses : 10 332 €, 21 528 €, 28 197 € ;
Échappées : 10 920 €, 27 456 €, 57 915 € ;
Élans : 3 600 €, 12 375 €, 30 360 €.
VOLUME : 26, 44, 63 sessions et 176, 337, 519 participantes.
INVESTISSEMENT_TOTAL : Budget de démarrage de 5 000 €
"""

#: La phrase réelle du document livré.
PHRASE_DU_DOCUMENT = (
    "L'offre est organisée en trois univers : les Parenthèses (ateliers courts "
    "dans le Val-d'Oise), les Échappées (week-ends dans un lieu nature) et les "
    "Élans (parcours de transition de vie)."
)


class _Section:
    """Un `RenderedSection` réduit à ce que le check lit : titre et corps."""

    def __init__(self, titre: str, corps: str) -> None:
        self.title = titre
        self.body = corps


# ---------------------------------------------------------------------------
# Lire les noms dans le brief
# ---------------------------------------------------------------------------


def test_les_trois_verticales_du_brief_sont_lues() -> None:
    """Vérifié sur le brief réel, pas sur un exemple inventé."""
    assert _noms_de_verticales(BRIEF_REEL) == ["Parenthèses", "Échappées", "Élans"]


def test_les_intertitres_du_brief_ne_sont_pas_des_verticales() -> None:
    """CONTRE-ÉPREUVE : « VOLUME : 26, 44, 63 » a la forme « Nom : chiffres ».

    Sans le critère « le nom contient une minuscule », le check aurait cherché
    « VOLUME » et « INVESTISSEMENT_TOTAL » dans le document, puis bloqué le
    livrable sur leur absence — un motif faux fabriqué par le correctif.
    """
    noms = _noms_de_verticales(BRIEF_REEL)

    assert "VOLUME" not in noms
    assert not any("INVESTISSEMENT" in nom.upper() for nom in noms)


# ---------------------------------------------------------------------------
# Juger le document
# ---------------------------------------------------------------------------


def test_un_document_qui_traite_ses_verticales_n_est_plus_bloque() -> None:
    """Le cas de `fedb76a1`. Échoue sur le code d'avant, qui bloquait toujours."""
    livrees = [_Section("Le projet", PHRASE_DU_DOCUMENT)]

    assert _verticales_absentes_du_document(BRIEF_REEL, livrees) == []


def test_une_verticale_vraiment_absente_bloque_encore() -> None:
    """CONTRE-ÉPREUVE : c'est le défaut SYNAPSES, il doit rester attrapé.

    Sans ce test, le correctif aurait pu neutraliser le check au lieu de le
    rendre juste.
    """
    livrees = [_Section(
        "Le projet",
        "L'offre tient en deux univers : les Parenthèses et les Échappées.",
    )]

    echecs = _verticales_absentes_du_document(BRIEF_REEL, livrees)

    assert len(echecs) == 1
    assert "Élans" in echecs[0].detail
    # Le motif dit AUSSI ce qui est présent : sans quoi le lecteur ne peut pas
    # distinguer « une verticale oubliée » de « le brief non lu du tout ».
    assert "2 sur 3" in echecs[0].detail
    # Et il ne reproche pas ce qui est là.
    assert "Parenthèses" not in echecs[0].detail


def test_un_document_vide_bloque_sur_les_trois() -> None:
    livrees = [_Section("Le projet", "Un modèle économique générique.")]

    echecs = _verticales_absentes_du_document(BRIEF_REEL, livrees)

    assert len(echecs) == 1
    for nom in ("Parenthèses", "Échappées", "Élans"):
        assert nom in echecs[0].detail
    assert "0 sur 3" in echecs[0].detail


@pytest.mark.parametrize(
    "brief",
    [
        "Le projet comporte plusieurs verticales d'activité à développer.",
        "VERTICALES : à préciser avec la porteuse.",
    ],
)
def test_un_brief_dont_rien_n_est_lisible_echoue_bruyamment(brief: str) -> None:
    """Règle 1 : ne pas pouvoir juger n'est pas un succès.

    C'est la moitié du check qu'il ne faut PAS perdre. Un brief qui annonce des
    verticales sans les nommer ne permet aucune vérification — et se taire
    laisserait passer exactement le défaut SYNAPSES.
    """
    livrees = [_Section("Le projet", "Un document complet et bien écrit.")]

    echecs = _verticales_absentes_du_document(brief, livrees)

    assert len(echecs) == 1
    assert "n'ont pu nommer" in echecs[0].detail


def test_la_casse_ne_fait_pas_un_faux_motif() -> None:
    """Le document peut écrire « parenthèses » en bas de casse dans une phrase."""
    livrees = [_Section("Le projet", "les parenthèses, les échappées et les élans")]

    assert _verticales_absentes_du_document(BRIEF_REEL, livrees) == []

"""Un prompt ne doit jamais montrer au modèle le vocabulaire qu'on lui interdit.

## Le défaut mesuré

12/09/2026, reprise Zenitek `db0d9508` : deux chapitres MORTS sur le contrôle
du vocabulaire interne — dont `str.20.sources`, celui-là même qui devait
montrer si les nouvelles règles de traçabilité servaient à quelque chose. Les
quatre générations précédentes du même dossier en perdaient zéro ou un.

La cause tenait en deux endroits du prompt :

    en-tête du bloc de chiffres :  « SOCLE VERROUILLÉ — assistance… »
    consigne de rédaction :        « ni socle verrouillé ou bloqué, ni hors
                                     socle, ni pipeline système… »

L'un l'écrivait en capitales, l'autre le listait en toutes lettres sous
prétexte de l'interdire. Le modèle reprend ce qu'on lui montre — ce dépôt
l'avait déjà mesuré : vingt-deux occurrences d'un nom de plateforme recopiées
depuis une simple docstring.

C'est la règle 5 prise entre un prompt et un contrôle : l'un écrit ce que
l'autre punit. Et c'est la même histoire que `[[UNDERSTAND]]`, où le prompt
exigeait un marqueur que la validation sanctionnait, faisant payer chaque
chapitre deux fois.

## Pourquoi ce test vise la CLASSE

Corriger « socle verrouillé » seul laisserait « hors socle », puis la locution
suivante qu'on ajoutera au contrôle dans six mois sans penser au prompt. Le
test lit donc `_VOCABULAIRE_INTERNE` — la liste qui FAIT FOI — et l'applique à
tout ce qui part au modèle. Un motif ajouté là sera vérifié ici sans que
personne ait à y penser (règle 4).

Il échoue sur le code d'avant, sur les deux emplacements à la fois.
"""
from __future__ import annotations

from datetime import date

from generation.chapitres.schema import _VOCABULAIRE_INTERNE
from generation.socle.builder import OUTIL_DESCRIPTION
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Zone


def _socle() -> Socle:
    return Socle(
        secteur="assistance informatique",
        zone=Zone(pays="France", region="Île-de-France"),
        date_socle=date(2026, 9, 12),
        donnees=[
            DonneeSocle(
                id="ca_actuel", libelle="Chiffre d'affaires", valeur=120000,
                unite="EUR", annee=2026, perimetre=Perimetre.NATIONAL,
                fiabilite=Fiabilite.DECLAREE,
            ),
        ],
    )


#: La seule règle qu'un PROMPT a le droit d'enfreindre, et pourquoi.
#:
#: « identifiant technique » attrape toute forme `mot_mot` — `ca_actuel`,
#: `marche_national_taille`. C'est un défaut dans le document LIVRÉ ; c'est la
#: matière même du prompt, qui doit nommer les identifiants pour que le modèle
#: les emploie dans ses figures. Un test qui l'exigerait ici demanderait au
#: bloc de chiffres de ne pas citer ses chiffres.
#:
#: L'exclusion est nommée et bornée à ce motif : toute autre locution ajoutée
#: à `_VOCABULAIRE_INTERNE` reste vérifiée sans que personne y pense.
_MATIERE_DU_PROMPT = frozenset({"identifiant technique"})


def _fautes(texte: str) -> list[str]:
    """Les locutions punies que ce texte contient — vide si le texte est sain."""
    return [
        nom for nom, motif in _VOCABULAIRE_INTERNE
        if nom not in _MATIERE_DU_PROMPT and motif.search(texte)
    ]


def test_le_bloc_des_chiffres_n_ecrit_aucune_locution_punie() -> None:
    """Son en-tête portait « SOCLE VERROUILLÉ », en capitales, en tête du bloc.

    C'est la place la plus visible du prompt : celle que le modèle relit à
    chaque chapitre.
    """
    from generation.chapitres.runner import _bloc_socle

    bloc = _bloc_socle(_socle())
    assert _fautes(bloc) == [], f"le bloc des chiffres écrit : {_fautes(bloc)}"


def test_le_prompt_systeme_n_ecrit_aucune_locution_punie() -> None:
    """L'interdiction CITAIT ce qu'elle interdisait, en toutes lettres.

    Une consigne qui donne l'exemple de la faute l'enseigne. Elle s'énonce
    désormais sans écrire une seule des locutions punies.
    """
    from generation.chapitres.runner import (
        _SYSTEME,
        COHERENCE_DES_CHIFFRES,
        PRIX_ET_MODELE_ECONOMIQUE,
        SOURCES_ET_TRACABILITE,
    )

    for nom, texte in (
        ("système", _SYSTEME),
        ("chiffres", COHERENCE_DES_CHIFFRES),
        ("sources", SOURCES_ET_TRACABILITE),
        ("prix", PRIX_ET_MODELE_ECONOMIQUE),
    ):
        assert _fautes(texte) == [], f"bloc {nom} : {_fautes(texte)}"


def test_la_description_de_l_outil_du_socle_est_saine() -> None:
    """Elle part au modèle AVEC le schéma : c'est un prompt, pas un commentaire."""
    assert _fautes(OUTIL_DESCRIPTION) == []


def test_le_catalogue_des_figures_est_sain() -> None:
    """Ajouté le 12/09/2026 — donc jamais passé sous cette garde jusqu'ici."""
    from generation.rendu_word.catalogue_figures import bloc_figures_possibles

    assert _fautes(bloc_figures_possibles(_socle())) == []


def test_la_garde_sait_encore_mordre() -> None:
    """CONTRE-ÉPREUVE : un test qui ne détecte plus rien passerait sur tout.

    Sans elle, vider `_VOCABULAIRE_INTERNE` rendrait ce fichier entièrement
    vert — un contrôle qui n'a rien à comparer n'est pas un succès (règle 1).
    """
    assert _fautes("Le socle verrouillé du dossier, et les chiffres hors socle.")

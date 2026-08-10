"""La typographie française se répare ; elle ne fait pas rejouer un appel.

Demande de la cliente : « entraîner le prompt sur les fautes d'orthographe et
autres, le but est de ne jamais rencontrer d'incident dans la génération ».

Deux façons de s'y prendre, et une seule tient :

- **Refuser** un chapitre pour une double espace ferait rejouer un appel — six
  centimes, plusieurs minutes — pour un défaut que trois caractères corrigent.
  Sur vingt-trois chapitres, c'est un dossier qui coûte le double sans être
  meilleur.
- **Réparer** atteint exactement le but que la règle poursuit. Le dépôt le fait
  déjà pour le résumé trop long (`raccourcir_le_resume`).

Le rejet reste pour ce qu'on ne peut pas réparer sans réécrire : un chiffre hors
socle, un tableau HTML dans un paragraphe.

## Ce que ce fichier verrouille surtout : ce qu'on NE touche PAS

Les contre-épreuves comptent plus que les épreuves ici. Ajouter naïvement une
espace devant tout `:` casserait `https://`, `3:1` et `12:30` — trois choses
parfaitement correctes qu'on aurait abîmées en croyant bien faire. C'est le
défaut que la règle 2 décrit : un remède qui frappe ce qui n'était pas malade.

Les guillemets droits, les points de suspension, les majuscules accentuées sont
laissés tranquilles. Ce sont des préférences, pas des fautes.
"""
from __future__ import annotations

import pytest

from generation.chapitres.schema import (
    BlocEncadre,
    BlocParagraphe,
    BlocTableau,
    ChapitrePayload,
    Encadre,
    Tableau,
)
from generation.chapitres.typographie import (
    FINE_INSECABLE,
    reparer_texte,
    reparer_typographie,
)

FINE = FINE_INSECABLE


@pytest.mark.parametrize(
    ("avant", "apres"),
    [
        ("Le marché  progresse", "Le marché progresse"),
        ("Trois    espaces ici", "Trois espaces ici"),
        ("Un mot , une virgule", "Un mot, une virgule"),
        ("Fin de phrase .", "Fin de phrase."),
        ("La question est simple: agir", f"La question est simple{FINE}: agir"),
        ("Vraiment ?", f"Vraiment{FINE}?"),
        ("Attention!", f"Attention{FINE}!"),
        ("Premier point; second point", f"Premier point{FINE}; second point"),
    ],
)
def test_les_fautes_d_espacement_sont_reparees(avant: str, apres: str) -> None:
    assert reparer_texte(avant) == apres


@pytest.mark.parametrize(
    "texte",
    [
        "Voir https://exemple.fr/page pour le détail",
        "Un ratio de 3:1 entre les deux segments",
        "Ouverture à 12:30 et fermeture à 19:00",
        "Le fichier C:\\Documents\\étude.docx",
    ],
)
def test_ce_qui_n_est_pas_une_ponctuation_reste_intact(texte: str) -> None:
    """LA contre-épreuve. Un correctif naïf casserait ces quatre lignes.

    Le signe doit être SUIVI d'une espace ou d'une fin pour être traité comme
    de la ponctuation — une URL, un rapport et une heure ne le sont jamais.
    """
    assert reparer_texte(texte) == texte


@pytest.mark.parametrize(
    "texte",
    [
        "Un chiffre d'affaires de 1 250 000 €",
        "Une croissance de 3,4 % par an",
        "Le montant est de 12,5 M€ en 2026",
        'Il a dit "non" au projet',
        "Trois options...",
        "État des lieux et Écarts constatés",
        "Chapitre 3.1 — Positionnement",
    ],
)
def test_ce_qui_est_deja_correct_traverse_intact(texte: str) -> None:
    """Décimales, pourcentages, guillemets droits, majuscules accentuées.

    Aucun n'est une faute. Un correctif qui les « améliorerait » finirait par
    casser une citation, une référence ou une unité.
    """
    assert reparer_texte(texte) == texte


@pytest.mark.parametrize(
    ("avant", "apres"),
    [
        ("coffre‑fort", "coffre-fort"),
        ("achat‐vente", "achat-vente"),
        ("e–commerce", "e-commerce"),
        ("experts‒comptables", "experts-comptables"),
        ("un mot­coupé", "un motcoupé"),
        ("texte﻿avec BOM", "texteavec BOM"),
        ("caract​ère", "caractère"),
    ],
)
def test_les_traits_exotiques_et_invisibles_disparaissent(
    avant: str, apres: str
) -> None:
    """Signalé par la cliente : un carré parasite dans les mots à trait d'union.

    Le modèle écrit un trait d'union insécable ou typographique ; la police de
    rendu ne le porte pas, et le lecteur voit un carré. Invisible en test —
    Carlito et Aptos manquent sur le poste de développement.
    """
    assert reparer_texte(avant) == apres


@pytest.mark.parametrize(
    "texte",
    [
        "La période 2025–2026 marque un tournant",
        "Le marché — et c'est notable — progresse de 3 %",
        "Une fourchette de 10–15 % selon les segments",
    ],
)
def test_les_tirets_LEGITIMES_survivent(texte: str) -> None:
    """CONTRE-ÉPREUVE : le demi-cadratin entre deux nombres est correct.

    Le remplacer partout abîmerait une ponctuation juste — la règle 2, un
    remède qui frappe ce qui n'était pas malade. D'où la condition « entre deux
    LETTRES », qui distingue le mot composé de l'intervalle et de l'incise.
    """
    assert reparer_texte(texte) == texte


def test_la_reparation_est_idempotente() -> None:
    """La rejouer ne doit rien changer — sinon chaque passe abîmerait un peu plus."""
    une_fois = reparer_texte("Le point  clé est simple: agir , vite .")
    deux_fois = reparer_texte(une_fois)

    assert une_fois == deux_fois
    assert une_fois == f"Le point clé est simple{FINE}: agir, vite."


def test_un_texte_vide_ne_casse_rien() -> None:
    assert reparer_texte("") == ""


def test_le_saut_de_ligne_survit() -> None:
    """Deux espaces se réduisent ; un retour à la ligne n'est pas une espace."""
    assert reparer_texte("Ligne un\nLigne deux") == "Ligne un\nLigne deux"


def _chapitre(*blocs: object) -> ChapitrePayload:
    return ChapitrePayload(
        chapitre=3,
        titre="Chapitre d'essai",
        blocs=list(blocs),  # type: ignore[arg-type]
        resume="Un résumé d'essai suffisamment long pour tenir sa borne.",
    )


def test_les_cellules_de_tableau_sont_reparees_aussi() -> None:
    """La moitié du document y vit : 52 % des mots du livrable de référence.

    Rester en surface laisserait toutes les cellules intactes — le contrôle du
    balisage a failli avoir ce défaut, il ne fallait pas le refaire ici.
    """
    payload = _chapitre(
        BlocTableau(
            tableau=Tableau(
                entetes=["Poste", "Montant"],
                lignes=[["Loyer  annuel", "12 kEUR"], ["Charges ,总", "3 kEUR"]],
            )
        )
    )

    retouches = reparer_typographie(payload)

    assert retouches == 2
    tableau = payload.blocs[0].tableau  # type: ignore[union-attr]
    assert tableau.lignes[0][0] == "Loyer annuel"
    assert tableau.lignes[1][0] == "Charges,总"


def test_les_encadres_sont_repares_aussi() -> None:
    payload = _chapitre(
        BlocEncadre(encadre=Encadre(intitule="À  retenir", lignes=["Croissance  forte"]))
    )

    assert reparer_typographie(payload) == 2
    encadre = payload.blocs[0].encadre  # type: ignore[union-attr]
    assert encadre.intitule == "À retenir"
    assert encadre.lignes[0] == "Croissance forte"


def test_le_resume_est_repare_aussi() -> None:
    """Il est relu par tous les chapitres suivants : une faute s'y propage."""
    payload = _chapitre(BlocParagraphe(texte="Sain."))
    payload.resume = "Un résumé  avec deux espaces et une virgule ."

    retouches = reparer_typographie(payload)

    assert retouches == 1
    assert payload.resume == "Un résumé avec deux espaces et une virgule."


def test_un_chapitre_deja_propre_ne_compte_aucune_retouche() -> None:
    """Le compte part au journal : s'il ne vaut zéro jamais, il ne mesure rien.

    C'est ce compte qui dira si l'entraînement de la consigne sert vraiment, ou
    si la réparation masque simplement le problème (règle 9).
    """
    payload = _chapitre(
        BlocParagraphe(texte="Le marché progresse de 3,4 % par an depuis 2022."),
        BlocTableau(
            tableau=Tableau(entetes=["Poste", "Montant"], lignes=[["Loyer", "12 kEUR"]])
        ),
    )

    assert reparer_typographie(payload) == 0

"""Typographie française du texte produit. On répare, on ne refuse pas.

## Pourquoi une réparation et non un contrôle

Refuser un chapitre pour une double espace ferait rejouer un appel — six
centimes, plusieurs minutes — pour un défaut que trois caractères corrigent.
Le dépôt applique déjà ce principe à `raccourcir_le_resume` : réparer avant de
juger, quand la réparation atteint exactement le but que la règle poursuit.

Le rejet reste réservé à ce qu'on ne peut PAS réparer sans réécrire : un chiffre
hors socle, un tableau HTML dans un paragraphe (voir `motifs_de_balisage`).

## Ce qui est réparé, et pourquoi seulement cela

Trois classes, choisies parce qu'elles n'ont **aucune exception légitime** en
français :

1. Les espaces multiples entre deux mots.
2. L'espace avant une virgule ou un point.
3. L'espace manquante avant `;` `:` `!` `?` — ponctuation double, qui en exige
   une en français.

Tout le reste est laissé tranquille, et c'est délibéré. Les guillemets droits,
les points de suspension en trois points, les majuscules accentuées : ce sont
des préférences, pas des fautes, et un correctif qui les impose finirait par
casser une citation, une référence ou une unité. La règle 2 de ce dépôt dit
qu'un contrôle qui frappe ce qui n'était pas malade est pire que le défaut
d'origine — elle vaut aussi pour une réparation.

## Le piège de la ponctuation double, désamorcé avant de livrer

Ajouter une espace devant tout `:` casserait `https://`, `3:1`, `12:30`. La
règle ne s'applique donc que si le signe est SUIVI d'une espace ou d'une fin de
texte — ce qui est le cas d'une vraie ponctuation, et jamais celui d'un rapport
ou d'une heure. Les contre-épreuves de
`test_la_typographie_est_reparee_pas_jugee.py` verrouillent ces trois cas.

## L'espace employée

U+202F, l'espace fine insécable. C'est celle que Word insère en français et
celle que `core/numbers.py` a appris à lire à ses dépens : une liste fermée
d'espaces admises a déjà coûté un blocage sur un document juste. On écrit donc
celle du traitement de texte, pas une espace ordinaire qui laisserait la
ponctuation passer à la ligne seule.
"""
from __future__ import annotations

import re
from typing import Any

#: Espace fine insécable — celle de Word en français (U+202F).
FINE_INSECABLE = " "

#: Ponctuation double : elle réclame une espace avant, en français.
_DOUBLE = ";:!?"

#: Deux espaces horizontales ou plus, saut de ligne exclu. Même raisonnement
#: par CLASSE que `core/numbers.py` : énumérer les espaces Unicode admises est
#: une liste à rallonger à chaque découverte.
_ESPACES_MULTIPLES = re.compile(r"[^\S\r\n]{2,}")

#: Espace parasite avant une virgule ou un point. Le point n'est visé que s'il
#: n'est pas suivi d'un chiffre : « 3 .5 » n'existe pas, mais on ne prend pas
#: le risque de toucher une numérotation.
_AVANT_SIMPLE = re.compile(r"[^\S\r\n]+([,.])(?!\d)")

#: Ponctuation double collée au mot qui précède. Le signe doit être SUIVI d'une
#: espace ou de la fin : sans cette condition, `https://`, `3:1` et `12:30` y
#: passeraient.
_AVANT_DOUBLE = re.compile(rf"(\w)([{_DOUBLE}])(?=\s|$)")

#: Ponctuation double déjà espacée, mais d'une espace ordinaire : elle peut
#: alors passer à la ligne toute seule. On la remplace par la fine insécable.
_DEJA_ESPACEE = re.compile(rf"[^\S\r\n]+([{_DOUBLE}])(?=\s|$)")


#: Caractères qui n'ont AUCUNE raison d'atteindre le document, et que la police
#: ne sait souvent pas dessiner — le lecteur voit alors un carré.
#:
#: **Signalé par la cliente le 09/08/2026** sur l'étude concurrentielle : un
#: caractère parasite dans « coffre-fort », « achat-vente », « e-commerce »,
#: « experts-comptables » et dans des URL. Tous des mots à TRAIT D'UNION — ce
#: n'était pas un hasard.
#:
#: Rien de tel dans le code ni dans les consignes : c'est le modèle qui écrit un
#: trait d'union exotique (insécable, tiret conditionnel, tiret typographique),
#: et la police de rendu ne le porte pas. Carlito et Aptos manquent d'ailleurs
#: sur le poste de développement, ce qui rend le défaut invisible en test.
#:
#: On ramène donc à un trait d'union ordinaire, et on supprime les invisibles.
_INVISIBLES = str.maketrans({
    "­": "",   # tiret conditionnel : jamais visible, souvent copié-collé
    "﻿": "",   # marque d'ordre des octets égarée dans un texte
    "￾": "",   # non-caractère : n'a aucune raison d'exister
    "�": "",   # caractère de remplacement : trace d'un décodage raté
    "​": "",   # espace de largeur nulle
})

#: Un trait d'union EXOTIQUE entre deux lettres. La condition « entre deux
#: lettres » compte : le tiret demi-cadratin garde sa place entre deux nombres
#: (« 2025–2026 ») et le tiret cadratin sa place dans une incise. Les remplacer
#: partout abîmerait une ponctuation correcte (règle 2).
_TRAIT_EXOTIQUE = re.compile(r"(?<=[^\W\d_])[‐‑‒–](?=[^\W\d_])")


def reparer_texte(texte: str) -> str:
    """Texte aux espaces normalisées. Idempotente : la rejouer ne change rien."""
    if not texte:
        return texte
    corrige = texte.translate(_INVISIBLES)
    corrige = _TRAIT_EXOTIQUE.sub("-", corrige)
    corrige = _ESPACES_MULTIPLES.sub(" ", corrige)
    corrige = _AVANT_SIMPLE.sub(r"\1", corrige)
    corrige = _DEJA_ESPACEE.sub(rf"{FINE_INSECABLE}\1", corrige)
    return _AVANT_DOUBLE.sub(rf"\1{FINE_INSECABLE}\2", corrige)


def reparer_typographie(payload: Any) -> int:
    """Répare tous les textes d'un chapitre EN PLACE. Rend le nombre de retouches.

    Le compte n'est pas décoratif : il part au journal. Une consigne qui
    s'améliore doit faire baisser ce nombre, et sans mesure on ne saurait pas si
    l'entraînement du prompt sert à quelque chose ou si la réparation masque
    simplement le problème (règle 9 — ne pas juger et réparer sur la même
    évidence sans le dire).
    """
    retouches = 0
    for bloc in getattr(payload, "blocs", ()) or ():
        retouches += _reparer_modele(bloc)
    resume = getattr(payload, "resume", None)
    if isinstance(resume, str):
        corrige = reparer_texte(resume)
        if corrige != resume:
            payload.resume = corrige
            retouches += 1
    return retouches


def _reparer_modele(modele: Any) -> int:
    """Descend dans un bloc et ses modèles imbriqués, comme le fait le contrôle.

    Un `BlocTableau` ne porte pas de texte : il porte un `Tableau`. Rester en
    surface laisserait toutes les cellules intactes — c'est-à-dire la moitié du
    document, puisque le livrable de référence loge 52 % de ses mots dans des
    tableaux.
    """
    champs = getattr(type(modele), "model_fields", None)
    if not champs:
        return 0
    retouches = 0
    for nom in champs:
        valeur = getattr(modele, nom, None)
        corrige, compte = _reparer_valeur(valeur)
        if compte:
            setattr(modele, nom, corrige)
            retouches += compte
    return retouches


def _reparer_valeur(valeur: Any) -> tuple[Any, int]:
    if isinstance(valeur, str):
        corrige = reparer_texte(valeur)
        return corrige, int(corrige != valeur)
    if isinstance(valeur, list):
        retouches = 0
        sortie = []
        for element in valeur:
            corrige, compte = _reparer_valeur(element)
            sortie.append(corrige)
            retouches += compte
        return sortie, retouches
    if getattr(type(valeur), "model_fields", None):
        return valeur, _reparer_modele(valeur)
    return valeur, 0

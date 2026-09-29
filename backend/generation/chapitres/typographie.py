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

## La langue, depuis le 29/09/2026

Business plan ÉCLORE (dossier `cb59cede`, 29/09/2026, moteur structuré) :
« already financé » p. 67, « se accroît » p. 7, « MEUR » et « EUR » dans le
texte. Aucun outil d'orthographe dans la chaîne, et la décision D4 du
diagnostic écarte l'API publique : les contrôles sont internes, et RÉPARÉS au
rendu. Trois familles, chacune restreinte à ses cas SÛRS — la règle 2 vaut
pour une réparation comme pour un contrôle :

1. l'élision (« se accroît » → « s'accroît »), seulement devant une voyelle
   minuscule ou un h muet d'une liste close, jamais devant « ou », « et »,
   « onze », « oui », et jamais « le un » ni « la une » ;
2. les mots anglais qu'un modèle laisse filer (« already », « however »…),
   remplacés quand l'équivalent est sans ambiguïté, et seulement hors d'une
   phrase anglaise (un titre de publication cité reste intact) ;
3. les codes d'unité de stockage (`MEUR`, `kEUR`, « 12 EUR », « unite »),
   traduits par `socle.schema.unite_lisible` — la même fonction que le socle
   et le rendu, pas une seconde table (règle 5).

Ces réparations ne touchent jamais un champ d'identifiants (`donnees_ids`) :
un identifiant n'est pas de la prose.
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Any, NamedTuple

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
#: ## Pourquoi la liste de cinq caractères a été remplacée
#:
#: **Cliente, 12/08/2026, sur la stratégie : « nettoyer les caractères Unicode
#: invisibles ».** Le correctif du 09/08 en énumérait cinq — tiret conditionnel,
#: marque d'ordre des octets, non-caractère, caractère de remplacement, espace
#: de largeur nulle. Il en reste plus de cent cinquante : liant et anti-liant de
#: largeur nulle, marques de direction, jointeur de mots, opérateurs invisibles,
#: annotations interlinéaires. En ajouter cinq de plus n'aurait fait que différer
#: le prochain retour — c'est la règle 4 du dépôt, mot pour mot : « si votre
#: correctif énumère des cas, il est incomplet ».
#:
#: On vise donc la CLASSE. Unicode range lui-même ces caractères : `Cf` (format,
#: invisible par construction), `Cc` (commande), `Cn` (non assigné), `Co` (usage
#: privé), `Cs` (demi-codet égaré). Aucun n'a de dessin. Trois exceptions, et
#: trois seulement : le saut de ligne, le retour chariot et la tabulation, qui
#: sont la mise en page du texte.
_SANS_DESSIN = frozenset({"Cc", "Cf", "Cn", "Co", "Cs"})

#: La mise en page, elle, se garde — sans quoi le document deviendrait un bloc.
_MISE_EN_PAGE = "\n\r\t"

#: Catégorie `So`, donc hors des classes ci-dessus, mais c'est la trace d'un
#: décodage raté : le losange à point d'interrogation. Il se voit, et il ne
#: devrait jamais se voir.
_REMPLACEMENT = "�"


def _doit_disparaitre(caractere: str) -> bool:
    """Vrai si le caractère n'a aucun dessin — ni glyphe, ni fonction de page."""
    if caractere in _MISE_EN_PAGE:
        return False
    if caractere == _REMPLACEMENT:
        return True
    return unicodedata.category(caractere) in _SANS_DESSIN


def purger_les_invisibles(texte: str) -> str:
    """Retire tout caractère sans dessin. Idempotente.

    Exposée à part de `reparer_texte` parce que le moteur structuré n'est pas
    le seul chemin : un chapitre rendu en markdown ne passe jamais par la
    réparation de typographie, et c'est pourtant le même lecteur qui reçoit le
    document. `rendering._clean_chapter_body` l'appelle donc aussi (règle 5 :
    une seule source pour cette vérité, deux appelants).
    """
    if not texte:
        return texte
    return "".join(c for c in texte if not _doit_disparaitre(c))

#: Un trait d'union EXOTIQUE entre deux lettres. La condition « entre deux
#: lettres » compte : le tiret demi-cadratin garde sa place entre deux nombres
#: (« 2025–2026 ») et le tiret cadratin sa place dans une incise. Les remplacer
#: partout abîmerait une ponctuation correcte (règle 2).
_TRAIT_EXOTIQUE = re.compile(r"(?<=[^\W\d_])[‐‑‒–](?=[^\W\d_])")


def reparer_texte(texte: str, *, prose: bool = True, anglais: bool = True) -> str:
    """Texte aux espaces normalisées. Idempotente : la rejouer ne change rien.

    `prose=False` s'arrête à la typographie : un identifiant n'a ni élision,
    ni mot anglais, ni unité à traduire, et le toucher le rendrait introuvable
    au rendu. `anglais=False` garde les mots anglais tels quels — le repli d'un
    champ borné, voir `_reparer_dans_la_borne`.
    """
    if not texte:
        return texte
    corrige = purger_les_invisibles(texte)
    corrige = _TRAIT_EXOTIQUE.sub("-", corrige)
    corrige = _ESPACES_MULTIPLES.sub(" ", corrige)
    corrige = _AVANT_SIMPLE.sub(r"\1", corrige)
    corrige = _DEJA_ESPACEE.sub(rf"{FINE_INSECABLE}\1", corrige)
    corrige = _AVANT_DOUBLE.sub(rf"\1{FINE_INSECABLE}\2", corrige)
    return reparer_langue(corrige, anglais=anglais) if prose else corrige


def _borne(modele: Any, nom: str) -> int | None:
    """La longueur maximale que le contrat impose à ce champ texte, s'il en a une.

    Lue dans le contrat lui-même (`Field(max_length=…)`), jamais recopiée :
    une borne changée dans `schema.py` vaut ici sans que personne y pense.
    """
    info = getattr(type(modele), "model_fields", {}).get(nom)
    for contrainte in getattr(info, "metadata", ()) or ():
        maximum = getattr(contrainte, "max_length", None)
        if isinstance(maximum, int):
            return maximum
    return None


def _reparer_dans_la_borne(texte: str, *, prose: bool, borne: int | None) -> str:
    """La réparation la plus complète qui tienne dans la borne du champ.

    ## Le défaut, relevé en relecture (29/09/2026)

    Un remplacement peut ALLONGER le texte — « however » devient « cependant »,
    « therefore » « par conséquent » — et une accroche de 400 signes, un
    intitulé de 120, une valeur d'indicateur de 40 ont une borne au contrat. Le
    rendu Word revalide le chapitre : un champ réparé au-delà de sa borne
    ferait échouer le DOCUMENT ENTIER, pour une retouche de style.

    On essaie donc, dans l'ordre : tout ; tout sauf les mots anglais ; la
    seule typographie ; la seule purge des invisibles, qui ne fait que
    raccourcir. Un mot anglais laissé en place est signalé par le contrôle
    post-rendu (`checks_post_rendu.detecter_mots_anglais`) : il se réécrit au
    chapitre, il ne casse rien.
    """
    complet = reparer_texte(texte, prose=prose)
    if borne is None or len(complet) <= borne:
        return complet
    for replier in (
        lambda: reparer_texte(texte, prose=prose, anglais=False),
        lambda: reparer_texte(texte, prose=False),
    ):
        candidat = replier()
        if len(candidat) <= borne:
            return candidat
    return purger_les_invisibles(texte)


#: Les champs du contrat qui portent des IDENTIFIANTS, pas de la prose. La
#: typographie s'y applique (un caractère invisible dans un identifiant le rend
#: introuvable), la langue jamais.
_CHAMPS_IDENTIFIANTS = frozenset({"donnees_ids"})


def reparer_typographie(payload: Any) -> int:
    """Répare tous les textes d'un chapitre EN PLACE. Rend le nombre de retouches.

    Le compte n'est pas décoratif : il part au journal. Une consigne qui
    s'améliore doit faire baisser ce nombre, et sans mesure on ne saurait pas si
    l'entraînement du prompt sert à quelque chose ou si la réparation masque
    simplement le problème (règle 9 — ne pas juger et réparer sur la même
    évidence sans le dire).

    L'accroche est réparée elle aussi depuis le 29/09/2026 : elle est imprimée
    dans le bandeau du chapitre (`rendu_word.composants`), donc lue — et elle
    était le seul texte du chapitre que cette passe ne voyait pas.
    """
    retouches = 0
    for bloc in getattr(payload, "blocs", ()) or ():
        retouches += _reparer_modele(bloc)
    for champ in ("accroche", "resume"):
        texte = getattr(payload, champ, None)
        if isinstance(texte, str):
            corrige = _reparer_dans_la_borne(
                texte, prose=True, borne=_borne(payload, champ)
            )
            if corrige != texte:
                setattr(payload, champ, corrige)
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
        corrige, compte = _reparer_valeur(
            valeur,
            prose=nom not in _CHAMPS_IDENTIFIANTS,
            borne=_borne(modele, nom),
        )
        if compte:
            setattr(modele, nom, corrige)
            retouches += compte
    return retouches


def _reparer_valeur(
    valeur: Any, *, prose: bool = True, borne: int | None = None
) -> tuple[Any, int]:
    """`borne` ne vaut que pour une chaîne : sur une liste, `max_length`
    compte des ÉLÉMENTS, pas des signes — elle ne descend donc pas."""
    if isinstance(valeur, str):
        corrige = _reparer_dans_la_borne(valeur, prose=prose, borne=borne)
        return corrige, int(corrige != valeur)
    if isinstance(valeur, list):
        retouches = 0
        sortie = []
        for element in valeur:
            corrige, compte = _reparer_valeur(element, prose=prose)
            sortie.append(corrige)
            retouches += compte
        return sortie, retouches
    if getattr(type(valeur), "model_fields", None):
        return valeur, _reparer_modele(valeur)
    return valeur, 0


# ══════════════════════════════════════════════════════════════════════════
# LA LANGUE — élisions, mots anglais, codes d'unité (29/09/2026)
# ══════════════════════════════════════════════════════════════════════════


def reparer_langue(texte: str, *, anglais: bool = True) -> str:
    """Mots anglais, élisions, codes d'unité. Idempotente.

    L'ordre compte : les mots anglais d'abord, parce que leur équivalent peut
    ouvrir sur une voyelle — « que furthermore » devient « que en outre », que
    l'élision rend ensuite « qu'en outre ». Dans l'ordre inverse, la seconde
    passe laisserait la faute qu'elle vient de créer.
    """
    if not texte:
        return texte
    corrige = remplacer_les_mots_anglais(texte) if anglais else texte
    corrige = reparer_les_elisions(corrige)
    return normaliser_les_codes_d_unite(corrige)


# ── Le garde-fou commun : une phrase ANGLAISE n'est pas une faute ────────────
#
# Un titre de publication cité (« The State of Fashion », « Wellness Economy
# Monitor ») ou un slogan de marque est de l'anglais LÉGITIME. Le reconnaître
# ne demande pas de dictionnaire : les mots-outils anglais qui n'existent pas
# en français suffisent. « a », « an », « on », « as », « or », « but » et
# « must » en sont exclus — ce sont aussi des mots français (« il a », « un
# an », « on », « tu as », « or », « un but », « un must »), et les compter
# ferait taire la réparation sur une phrase française.
_ANGLAIS_SANS_AMBIGUITE = frozenset({
    "the", "of", "and", "is", "are", "was", "were", "be", "been", "being",
    "has", "have", "had", "to", "in", "for", "with", "this", "that", "these",
    "those", "it", "its", "by", "from", "not", "than", "their", "they",
    "which", "will", "would", "can", "could", "should", "may", "might", "at",
    "about", "into", "upon", "our", "your", "you", "we", "he", "she", "his",
    "her", "him", "them", "who", "what", "when", "where", "why", "how", "if",
    "all", "any", "each", "every", "some", "such", "only", "just", "very",
    "more", "most", "less", "much", "many", "other", "over", "under", "out",
    "up", "after", "before", "because", "while", "then", "there", "here",
    "so", "do", "does", "did", "my", "unless", "until", "yet", "done", "said",
})

_MOT_VOISIN_AVANT = re.compile(r"([^\W\d_]+)[^\w]*$")
_MOT_VOISIN_APRES = re.compile(r"^[^\w]*([^\W\d_]+)")


def _dans_une_phrase_anglaise(texte: str, debut: int, fin: int) -> bool:
    """Le mot voisin, d'un côté ou de l'autre, est-il un mot-outil anglais ?"""
    avant = _MOT_VOISIN_AVANT.search(texte[max(0, debut - 40):debut])
    apres = _MOT_VOISIN_APRES.search(texte[fin:fin + 40])
    return any(
        m is not None and m.group(1).casefold() in _ANGLAIS_SANS_AMBIGUITE
        for m in (avant, apres)
    )


def _apostrophe(texte: str) -> str:
    """L'apostrophe que CE texte emploie déjà : on ne mélange pas les deux."""
    return "’" if texte.count("’") > texte.count("'") else "'"


def _majuscule_comme(modele: str, mot: str) -> str:
    return mot[:1].upper() + mot[1:] if modele[:1].isupper() else mot


# ── 1. Les élisions ──────────────────────────────────────────────────────────
#
# « se accroît », p. 7 du business plan ÉCLORE. La règle d'élision est simple ;
# ses EXCEPTIONS ne le sont pas, et ce sont elles qui décident de ce qu'une
# réparation automatique a le droit de toucher :
#
# - le h ASPIRÉ ne s'élide pas (« le haut », « la hausse », « le héros ») et
#   aucune règle ne le distingue du h muet : seule une liste close de radicaux
#   h-muets est réparée. Un mot absent de la liste reste tel quel — l'oubli
#   coûte une faute laissée, jamais une faute créée ;
# - « le un », « la une » (le chiffre, la première page) ne s'élident pas ;
# - « onze », « oui », « ouate » non plus ;
# - « le ou la bénéficiaire » : « ou » et « et » sont des conjonctions ;
# - un nom propre (« la Isla », « Le Havre ») ou un sigle garde sa forme : seul
#   un mot en MINUSCULE est visé ;
# - « donne-le à » : un pronom derrière un trait d'union ne s'élide pas.
_PARTICULES = r"[Jj]e|[Mm]e|[Tt]e|[Ss]e|[Ll]e|[Ll]a|[Nn]e|[Dd]e|[Qq]ue|[Ss]i"

#: Le mot suivant est LU sans être consommé : dans « ne le ai », la particule
#: « le » doit rester disponible pour la correspondance suivante, sans quoi
#: la réparation cesserait d'être idempotente (une seconde passe corrigerait
#: ce que la première a sauté).
_ELISION = re.compile(
    rf"(?<![\w'’-])(?P<particule>{_PARTICULES})"
    r"[^\S\r\n]+(?=(?P<mot>[^\W\d_][\w'’-]*))"
)

_VOYELLE_MINUSCULE = frozenset("aeiouàâäéèêëîïôöùûüœæ")

#: Radicaux à h MUET, liste close et délibérément prudente. « hér » n'y est pas
#: (« le héros », « le hérisson » sont aspirés) : seul « hérit » l'est.
_H_MUETS = (
    "habill", "habit", "haleine", "hallucin", "haltère", "hameçon", "harmoni",
    "hebdomadaire", "héberg", "hectare", "hégémon", "hélice", "hélicoptère",
    "hémisph", "herb", "hérédit", "hérit", "hermétique", "héroïn", "hésit",
    "heure", "heureu", "hexagon", "hier", "hippodrome", "hirondelle",
    "histoir", "histori", "hiver", "hommage", "homme", "homogén", "homolog",
    "honnête", "honneur", "honor", "hôpita", "horaire", "horizon", "horloge",
    "hormone", "horreur", "horrible", "hortic", "hospital", "hostil", "hôte",
    "huile", "huître", "humain", "humanit", "humble", "humeur", "humid",
    "humili", "humour", "hydr", "hygièn", "hymne", "hyper", "hypno", "hypoth",
    "hystér",
)

#: Mots commençant par une voyelle devant lesquels on n'élide JAMAIS.
_SANS_ELISION = frozenset({
    "ou", "où", "et", "onze", "onzième", "onzièmes", "oui", "ouistiti",
    "ouate", "uhlan", "ululement", "ululements", "oh", "ah", "eh",
})

#: Et ceux-ci derrière « le » et « la » seulement. « Le un », « la une » ; et
#: surtout le pronom d'un impératif privé de son trait d'union — « réservez
#: la à l'avance », « mettez la en avant » : l'élider écrirait « réservez l'à
#: l'avance », une faute pire que celle qu'on corrige. Derrière « de » ou
#: « que », ces mots s'élident normalement (« d'après », « qu'à », « qu'en »).
_SANS_ELISION_APRES_LE_LA = frozenset({
    "un", "une", "à", "au", "aux", "avec", "après", "avant", "auprès",
    "autour", "afin", "ainsi", "en", "entre", "envers", "outre", "ici", "il",
    "ils", "elle", "elles", "on",
})


def _appelle_l_elision(particule: str, mot: str) -> bool:
    bas = particule.casefold()
    if bas == "si":
        return mot in {"il", "ils"}
    if not mot[:1].islower():
        return False
    if len(mot) > 1 and mot[1] in "-'’":
        # « e-commerce », « e-mail » : l'usage garde « le ». Et « a' » n'est
        # pas un mot.
        return False
    if mot in _SANS_ELISION:
        return False
    if bas in {"le", "la"} and mot in _SANS_ELISION_APRES_LE_LA:
        return False
    if mot[0] in _VOYELLE_MINUSCULE:
        return True
    return mot[0] == "h" and mot.startswith(_H_MUETS)


def reparer_les_elisions(texte: str) -> str:
    """« se accroît » → « s'accroît », « que il » → « qu'il ». Idempotente."""
    if not texte:
        return texte
    apostrophe = _apostrophe(texte)

    def _remplacer(m: re.Match[str]) -> str:
        particule, mot = m.group("particule"), m.group("mot")
        if not _appelle_l_elision(particule, mot):
            return m.group(0)
        # Le voisin d'après, c'est le mot lui-même : « tell me about ».
        if _dans_une_phrase_anglaise(texte, m.start(), m.start("mot")):
            return m.group(0)
        return f"{particule[:-1]}{apostrophe}"

    return _ELISION.sub(_remplacer, texte)


# ── 2. Les mots anglais ──────────────────────────────────────────────────────
#
# « already financé », p. 67 du business plan ÉCLORE. La table d'anglicismes
# de `rendering.py` ne s'applique qu'au markdown de l'ancienne chaîne : rien ne
# la faisait jouer sur le texte que le Word imprime.
#
# LISTE CLOSE de mots-outils anglais — adverbes et conjonctions de liaison —
# qu'un modèle laisse filer au milieu d'une phrase française, et qui n'ont
# AUCUN homographe français. La valeur est l'équivalent quand il est sans
# ambiguïté ; `None` quand il dépend de la phrase (« hence » vaut « donc » ou
# « d'où », « overall » vaut « globalement » ou « global ») : le mot n'est
# alors pas remplacé, et le contrôle post-rendu le signale.
MOTS_ANGLAIS: dict[str, str | None] = {
    "already": "déjà",
    "however": "cependant",
    "therefore": "par conséquent",
    "consequently": "par conséquent",
    "moreover": "de plus",
    "furthermore": "en outre",
    "additionally": "en outre",
    "nevertheless": "néanmoins",
    "nonetheless": "néanmoins",
    "meanwhile": "entre-temps",
    # « indeed » n'est PLUS remplacé (relecture du 29/09/2026) : c'est aussi le
    # nom d'une plateforme d'emploi, que les business plans citent en
    # minuscules — « offres publiées sur indeed » devenait « sur en effet ».
    # Rien dans la phrase ne dit à coup sûr lequel des deux on lit : il se
    # signale, il ne se remplace pas. Voir aussi `_AUSSI_UN_NOM`.
    "indeed": None,
    "whereas": "alors que",
    "whilst": "tandis que",
    "although": "même si",
    "thus": "ainsi",
    "likewise": "de même",
    "namely": "à savoir",
    "despite": "malgré",
    "regarding": "concernant",
    "approximately": "environ",
    "roughly": "environ",
    "overall": None,
    "hence": None,
    "besides": None,
    "otherwise": None,
    "whether": None,
    "within": None,
    "instead": None,
    "though": None,
}

#: Capitalisés, ces mots ne sont visés qu'en tête de phrase et suivis d'une
#: virgule (« However, le marché… »). « Indeed » n'y est jamais : c'est aussi
#: le nom d'une plateforme d'emploi, citée comme source dans les business plans.
_JAMAIS_EN_MAJUSCULE = frozenset({"indeed"})

#: Les mots de la liste qui sont AUSSI un nom propre. Derrière une préposition
#: ou un déterminant — « sur indeed », « via indeed », « et indeed » —, ce
#: n'est pas un adverbe qui a fui : c'est la plateforme. Ni réparé, ni
#: signalé : un motif faux coûterait une réécriture de chapitre (règle 2).
_AUSSI_UN_NOM = frozenset({"indeed"})
_INTRODUIT_UN_NOM = frozenset({
    "sur", "via", "de", "du", "des", "le", "la", "les", "par", "chez", "avec",
    "pour", "à", "au", "aux", "un", "une", "et", "ou", "comme", "site",
    "plateforme",
})

#: Un mot ENTRE guillemets est cité, pas écrit : « le mot « already » » ne se
#: traduit pas, pas plus qu'un titre de publication (relecture du 29/09/2026).
_GUILLEMET_AVANT = re.compile(r"[«“\"‘][^\S\r\n]*$")
_GUILLEMET_APRES = re.compile(r"[^\S\r\n]*[»”\"’]")


def _entre_guillemets(texte: str, debut: int, fin: int) -> bool:
    return bool(
        _GUILLEMET_AVANT.search(texte[max(0, debut - 6):debut])
        and _GUILLEMET_APRES.match(texte, fin)
    )


def _employe_comme_un_nom(texte: str, debut: int, bas: str) -> bool:
    if bas not in _AUSSI_UN_NOM:
        return False
    avant = _MOT_VOISIN_AVANT.search(texte[max(0, debut - 40):debut])
    return avant is not None and avant.group(1).casefold() in _INTRODUIT_UN_NOM


_MOT_ANGLAIS = re.compile(
    r"(?<![\w/@.'’-])("
    + "|".join(sorted(MOTS_ANGLAIS, key=len, reverse=True))
    + r")(?![\w/@'’-])(?!\.\w)",
    re.IGNORECASE,
)

#: Ce qui ouvre une phrase, une cellule ou une puce.
_OUVERTURE = frozenset(".!?:;|(«\"*-\n")


class MotAnglais(NamedTuple):
    """Une occurrence d'un mot anglais dans une phrase française."""

    mot: str
    debut: int
    fin: int
    #: L'équivalent sans ambiguïté, ou None si le mot se signale seulement.
    equivalent: str | None


def mots_anglais(texte: str) -> list[MotAnglais]:
    """Les mots anglais de la liste close, hors phrase anglaise.

    Source unique pour la réparation ET pour le contrôle post-rendu
    (`checks_post_rendu.detecter_mots_anglais`) : deux lectures du même défaut
    finiraient par diverger (règle 5). Ni un mot CITÉ entre guillemets, ni un
    nom propre derrière sa préposition (« sur indeed ») n'est une fuite.
    """
    trouves: list[MotAnglais] = []
    for m in _MOT_ANGLAIS.finditer(texte or ""):
        mot = m.group(1)
        bas = mot.casefold()
        if _entre_guillemets(texte, m.start(), m.end()):
            continue
        if _employe_comme_un_nom(texte, m.start(), bas):
            continue
        if mot != bas:
            if mot != bas.capitalize() or bas in _JAMAIS_EN_MAJUSCULE:
                continue
            precedent = re.sub(r"[^\S\r\n]+$", "", texte[:m.start()])
            if precedent and precedent[-1] not in _OUVERTURE:
                continue
            if not re.match(r"[^\S\r\n]*,", texte[m.end():]):
                continue
        if _dans_une_phrase_anglaise(texte, m.start(), m.end()):
            continue
        trouves.append(MotAnglais(mot, m.start(), m.end(), MOTS_ANGLAIS[bas]))
    return trouves


def remplacer_les_mots_anglais(texte: str) -> str:
    """« already financé » → « déjà financé ». Les mots ambigus restent."""
    if not texte:
        return texte
    morceaux: list[str] = []
    curseur = 0
    for trouve in mots_anglais(texte):
        if trouve.equivalent is None:
            continue
        morceaux.append(texte[curseur:trouve.debut])
        morceaux.append(_majuscule_comme(trouve.mot, trouve.equivalent))
        curseur = trouve.fin
    morceaux.append(texte[curseur:])
    return "".join(morceaux)


# ── 3. Les codes d'unité ─────────────────────────────────────────────────────
#
# `MdEUR`, `MEUR`, `kEUR` sont des notations de STOCKAGE (voir
# `socle.schema.unite_lisible`) : le lecteur lit « Md€ », « M€ », « k€ ». Le
# modèle les recopie quand on les lui montre, et la cliente l'a signalé dès le
# 09/08/2026. La traduction est celle du socle, importée — une seconde table
# ici serait la troisième vérité sur les unités (règle 5).
_ESPACE_H = r"[^\S\r\n]"
#: Le nombre qui précède, séparateurs de milliers compris (« 1 250 »,
#: « 0,5 »). Une espace n'appartient au nombre que si un chiffre la suit.
_NOMBRE_AVANT = re.compile(
    r"(\d(?:[\d.,]|[^\S\r\n](?=\d))*)[^\S\r\n]*$"
)


@lru_cache(maxsize=1)
def _codes_d_unite() -> tuple[dict[str, str], re.Pattern[str], re.Pattern[str]]:
    """(code → forme lisible, motif du code collé, motif « 3 M EUR »).

    Construit à la première utilisation : `socle.schema` n'a pas à être chargé
    pour réparer une double espace. Seuls les codes À MAGNITUDE sont visés
    (`MEUR`, `kUSD`…) : aucun n'est un mot, dans aucune langue. Un code nu
    comme `USD` est un usage français admis, il reste.
    """
    from ..socle.schema import unite_lisible, unites_monetaires  # noqa: PLC0415

    lisibles: dict[str, str] = {}
    for code in unites_monetaires():
        if code[:1] in "kM" and unite_lisible(code) != code:
            lisibles[code] = unite_lisible(code)
            if code.startswith("Md"):
                # « MdsEUR » : le pluriel qu'un rédacteur ajoute de lui-même.
                lisibles["Mds" + code[2:]] = unite_lisible(code)
    # `colle` est un groupe VIDE qui ne participe qu'après un chiffre : « 12MEUR »
    # reçoit alors l'espace qui lui manquait.
    colle = re.compile(
        r"(?:(?P<colle>(?<=\d))|(?<![\w/@.-]))(?P<code>"
        + "|".join(sorted(lisibles, key=len, reverse=True))
        + r")(?![\w-])"
    )
    espace = re.compile(
        rf"(?P<avant>\d{_ESPACE_H}*)(?P<magnitude>k|M|Mds|Md){_ESPACE_H}+"
        r"(?P<devise>EUR|USD|GBP)(?![\w-])"
    )
    return lisibles, colle, espace


#: « EUR » après un nombre. Jamais seul : « EUR-Lex », la base du droit
#: européen, est une source citée dans les chapitres réglementaires.
_EUR_APRES_UN_NOMBRE = re.compile(rf"(?P<nombre>\d)(?P<espace>{_ESPACE_H}*)EUR(?![\w-])")
#: L'apostrophe AVANT est admise : « l'unite » est « l'unité » sans son accent.
_UNITE_NUE = re.compile(r"(?<![\w/@.-])unite(?![\w'’-])")


def _valeur(nombre: str) -> float | None:
    brut = re.sub(r"[^\d,.]", "", nombre).replace(",", ".")
    try:
        return float(brut)
    except ValueError:
        return None


def normaliser_les_codes_d_unite(texte: str) -> str:
    """`12 MEUR` → `12 M€`, `1 500 EUR/mois` → `1 500 €/mois`. Idempotente."""
    if not texte:
        return texte
    lisibles, colle, espace = _codes_d_unite()

    def _colle(m: re.Match[str]) -> str:
        espace_manquante = " " if m.group("colle") is not None else ""
        return espace_manquante + lisibles[m.group("code")]

    def _espace(m: re.Match[str]) -> str:
        magnitude = "Md" if m.group("magnitude") == "Mds" else m.group("magnitude")
        lisible = lisibles.get(magnitude + m.group("devise"))
        if lisible is None:
            return m.group(0)
        avant = m.group("avant")
        return (avant if avant[-1:].isspace() else avant + " ") + lisible

    corrige = colle.sub(_colle, texte)
    corrige = espace.sub(_espace, corrige)
    corrige = _EUR_APRES_UN_NOMBRE.sub(
        lambda m: f"{m.group('nombre')}{m.group('espace') or ' '}€", corrige
    )
    return _UNITE_NUE.sub(lambda m: _unite(corrige, m), corrige)


def _unite(texte: str, m: re.Match[str]) -> str:
    """« unite » : le code de l'effectif, ou « unité » privé de son accent.

    Après un nombre, l'accord suit la règle française (singulier sous deux) ;
    après « en », c'est l'unité de mesure d'un tableau ou d'une figure, au
    pluriel ; ailleurs on rend l'accent et rien d'autre — « par unite »
    devient « par unité », jamais « par unités ».
    """
    if _dans_une_phrase_anglaise(texte, m.start(), m.end()):
        return m.group(0)
    avant = texte[max(0, m.start() - 30):m.start()]
    nombre = _NOMBRE_AVANT.search(avant)
    if nombre is not None:
        valeur = _valeur(nombre.group(1))
        return "unité" if valeur is not None and abs(valeur) < 2 else "unités"
    if re.search(rf"\ben{_ESPACE_H}+$", avant):
        return "unités"
    return "unité"

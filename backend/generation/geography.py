"""Adaptation geographique automatique des chapitres (§7 du cadrage).

Selon le pays cible, le chapitre 1 d'une etude de marche analyse soit
le marche europeen, soit le marche africain, soit le maghreb, etc.
Aucune mention d'une zone non pertinente.
"""
from __future__ import annotations

# Mapping pays -> macro-zone d'analyse pour le chapitre 1 EM.
_CONTINENT_BY_COUNTRY: dict[str, str] = {
    # Afrique francophone
    "benin": "africain",
    "cote d'ivoire": "africain",
    "cote d ivoire": "africain",
    "senegal": "africain",
    "togo": "africain",
    "burkina faso": "africain",
    "mali": "africain",
    "niger": "africain",
    "cameroun": "africain",
    "gabon": "africain",
    "nigeria": "africain",
    "ghana": "africain",
    "congo": "africain",
    "congo-brazzaville": "africain",
    "republique democratique du congo": "africain",
    "rdc": "africain",
    "rwanda": "africain",
    "guinee": "africain",
    "madagascar": "africain",
    "mauritanie": "africain",
    "tchad": "africain",
    "centrafrique": "africain",
    "republique centrafricaine": "africain",
    "djibouti": "africain",
    "comores": "africain",
    "burundi": "africain",
    "kenya": "africain",
    "afrique du sud": "africain",
    "haiti": "caribeen",
    # Maghreb
    "maroc": "maghrebin",
    "tunisie": "maghrebin",
    "algerie": "maghrebin",
    # Europe
    "france": "europeen",
    "belgique": "europeen",
    "allemagne": "europeen",
    "espagne": "europeen",
    "italie": "europeen",
    "pays-bas": "europeen",
    "luxembourg": "europeen",
    "suisse": "europeen",
    "portugal": "europeen",
    # Amerique du Nord
    "canada": "nord-americain",
    "etats-unis": "nord-americain",
    "usa": "nord-americain",
    # DOM/TOM
    "guadeloupe": "caribeen",
    "martinique": "caribeen",
    "guyane": "caribeen",
    "reunion": "ocean indien",
    "mayotte": "ocean indien",
    # ── ASIE, MOYEN-ORIENT ET RESTE DU MONDE (05/11/2026) ───────────────────
    #
    # Ce répertoire couvrait la France, l'Afrique francophone, le Maghreb,
    # l'Europe de l'Ouest et l'Amérique du Nord : le marché historique
    # d'EVKHA. L'ASIE N'Y ÉTAIT PAS, et le Royaume-Uni non plus.
    #
    # Mesuré sur l'étude de la concurrence SUN TZU du 04/11/2026, qui vise six
    # territoires asiatiques : `macro_zone_for("Japon")` rendait
    # « international », donc la consigne envoyée au modèle disait « pays
    # cible NON IDENTIFIÉ. Analyser le marché MONDIAL » et le chapitre 1
    # s'intitulait « Analyse chiffrée du marché mondial ».
    #
    # L'audit de la cliente en porte la trace : « la baisse de 6 % publiée par
    # FranceAgriMer concerne les importations chinoises de produits agricoles
    # et agroalimentaires provenant du MONDE ENTIER » — l'étude a confondu un
    # agrégat mondial avec un flux France → Chine, et notre propre consigne
    # lui demandait d'analyser le marché mondial. « Concurrents par pays :
    # insuffisant, notamment pour l'Inde et la Corée du Sud » dit la même
    # chose par un autre bout.
    #
    # Le critère d'ajout est celui des TERRITOIRES QUE LES ÉTUDES VISENT, pas
    # un atlas : les six de SUN TZU, leurs voisins commerciaux immédiats, le
    # Golfe et les grands marchés d'export que les dossiers citent. La liste
    # reste faite pour s'allonger — une absence coûte une consigne fausse, pas
    # un plantage.
    "chine": "asiatique",
    "chine continentale": "asiatique",
    "hong kong": "asiatique",
    "taiwan": "asiatique",
    "japon": "asiatique",
    "coree du sud": "asiatique",
    "coree": "asiatique",
    "singapour": "asiatique",
    "inde": "asiatique",
    "vietnam": "asiatique",
    "thailande": "asiatique",
    "malaisie": "asiatique",
    "indonesie": "asiatique",
    "philippines": "asiatique",
    "emirats arabes unis": "moyen-oriental",
    "arabie saoudite": "moyen-oriental",
    "qatar": "moyen-oriental",
    "koweit": "moyen-oriental",
    "liban": "moyen-oriental",
    "turquie": "moyen-oriental",
    "israel": "moyen-oriental",
    "royaume-uni": "europeen",
    "angleterre": "europeen",
    "irlande": "europeen",
    "autriche": "europeen",
    "pologne": "europeen",
    "suede": "europeen",
    "danemark": "europeen",
    "norvege": "europeen",
    "finlande": "europeen",
    "grece": "europeen",
    "roumanie": "europeen",
    "tchequie": "europeen",
    "republique tcheque": "europeen",
    "bresil": "sud-americain",
    "mexique": "sud-americain",
    "argentine": "sud-americain",
    "chili": "sud-americain",
    "colombie": "sud-americain",
    "australie": "oceanien",
    "nouvelle-zelande": "oceanien",
}

_CONTINENT_LABELS: dict[str, str] = {
    "africain":         "africain",
    "europeen":         "européen",
    "maghrebin":        "maghrébin",
    "nord-americain":   "nord-américain",
    "caribeen":         "caribéen et antillais",
    "ocean indien":     "de l'océan Indien",
    "asiatique":        "asiatique",
    "moyen-oriental":   "du Moyen-Orient",
    "sud-americain":    "latino-américain",
    "oceanien":         "océanien",
}


#: Le vocabulaire géographique du dépôt, sans accents et en minuscules.
#:
#: EXPORTÉ pour que d'autres contrôles puissent reconnaître une portée
#: géographique sans recopier la liste (règle 5) — `arithmetique` s'en sert
#: pour ne plus prendre « (France) » ou « (2026, France) » pour une source.
NOMS_GEOGRAPHIQUES: frozenset[str] = frozenset(
    set(_CONTINENT_BY_COUNTRY)
    | set(_CONTINENT_BY_COUNTRY.values())
    | set(_CONTINENT_LABELS)
    # Les portées que le dépôt écrit sans qu'elles soient des pays.
    | {"monde", "mondial", "mondiale", "international", "internationale",
       "europe", "union europeenne", "ue", "national", "nationale"}
)


def _strip_accents(s: str) -> str:
    import unicodedata  # noqa: PLC0415
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


#: Les noms qui désignent UN MÊME territoire. Replié sur le canonique.
#:
#: Le répertoire en portait déjà, par commodité de recherche : `usa` et
#: `etats-unis`, `rdc` et son nom long, deux orthographes de Côte d'Ivoire.
#: Tant qu'on ne faisait que chercher une macro-zone, deux clés pour un pays
#: étaient sans conséquence — les deux rendaient la même zone.
#:
#: Dès qu'on COMPTE des territoires, elles en font deux. Mesuré sur l'étude
#: SUN TZU : « Chine continentale (vente en ligne transfrontalière) » et
#: « Shanghai, Chine » comptaient pour deux marchés, et le panel paraissait
#: deux fois plus dispersé qu'il ne l'est.
#:
#: « coree » n'y est PAS replié sur « coree du sud » : la Corée du Nord
#: existe, et deviner laquelle serait inventer une donnée.
_MEME_TERRITOIRE: dict[str, str] = {
    "chine continentale": "chine",
    "angleterre": "royaume-uni",
    "usa": "etats-unis",
    "rdc": "republique democratique du congo",
    "republique tcheque": "tchequie",
    "cote d ivoire": "cote d'ivoire",
    "republique centrafricaine": "centrafrique",
    "congo-brazzaville": "congo",
}

#: Les noms de pays du répertoire, du plus LONG au plus court.
#:
#: L'ordre fait tout : « coree du sud » doit être essayé avant « coree », et
#: « chine continentale » avant « chine ». Sans cela, « Corée du Sud » se
#: rangerait sous « Corée », et deux territoires distincts se confondraient.
_PAYS_DU_PLUS_LONG = sorted(_CONTINENT_BY_COUNTRY, key=len, reverse=True)


def territoires_de(emplacement: str) -> list[str]:
    """Les territoires NOMMÉS dans un emplacement écrit en texte libre.

    ## Le défaut mesuré

    Le champ `emplacement` d'un concurrent est de la prose. Relevé sur l'étude
    SUN TZU du 04/11/2026, qui vise SIX territoires prioritaires :

        « Siège France, distribution internationale »
        « Hong Kong et Taïwan (plusieurs magasins) »
        « Chine continentale (vente en ligne transfrontalière) »
        « Corée du Sud (Séoul notamment) »
        « Shanghai, Chine »
        « Siège international, distribution en Asie »

    Neuf libellés pour six territoires. Compter les libellés donnait donc neuf
    « territoires » dont aucun n'atteignait son plancher de trois acteurs :
    une mesure bavarde, qui ne disait plus où chercher.

    ## Ce qu'elle rend, et ce qu'elle ne rend pas

    Un emplacement peut nommer PLUSIEURS territoires — « Hong Kong et
    Taïwan » en vaut deux, et les deux les comptent. Le nom rendu est la clé
    du répertoire (`chine`, `coree du sud`) : un identifiant stable, pas de la
    prose, et surtout pas une seconde table de noms à faire diverger
    (règle 5).

    Un emplacement qui ne nomme AUCUN pays connu — « Siège international,
    distribution en Asie » — rend une liste vide. Ce n'est pas un territoire,
    c'est une portée, et l'appelant doit le ranger à part plutôt que
    d'inventer un pays. Une zone comme « asiatique » n'en est pas un non plus :
    on ne vend pas en « Asie », on vend au Japon.
    """
    texte = _strip_accents((emplacement or "").lower())
    trouves: list[str] = []
    for pays in _PAYS_DU_PLUS_LONG:
        if pays not in texte:
            continue
        # Frontière de mot aux deux bouts : « mali » ne doit pas sortir de
        # « Malaisie », ni « inde » de « Indonésie ».
        for position in _positions(texte, pays):
            avant = texte[position - 1] if position else " "
            apres_index = position + len(pays)
            apres = texte[apres_index] if apres_index < len(texte) else " "
            if avant.isalpha() or apres.isalpha():
                continue
            # Un territoire déjà trouvé par un nom PLUS LONG qui le contient
            # (« coree » dans « coree du sud ») n'est pas un second territoire.
            if any(pays in deja for deja in trouves):
                break
            trouves.append(pays)
            break
    # Replié en dernier : « chine continentale » a pu être trouvé par son nom
    # long AVANT que « chine » ne soit essayé, et les deux doivent n'en faire
    # qu'un. Le repli après coup rend l'ordre de recherche indifférent.
    return sorted({_MEME_TERRITOIRE.get(pays, pays) for pays in trouves})


def _positions(texte: str, aiguille: str) -> list[int]:
    positions: list[int] = []
    depart = texte.find(aiguille)
    while depart != -1:
        positions.append(depart)
        depart = texte.find(aiguille, depart + 1)
    return positions


def macro_zone_for(country: str) -> str:
    """Retourne le label de macro-zone pour le chapitre 1 EM.

    Defaut prudent : 'international' si pays inconnu (l'IA cadrera).
    Accent-insensible : "Côte d'Ivoire" et "Cote d Ivoire" matchent.
    """
    key = _strip_accents((country or "").strip().lower())
    zone = _CONTINENT_BY_COUNTRY.get(key)
    if zone is None:
        return "international"
    return _CONTINENT_LABELS.get(zone, zone)


def geographic_consigne_for(country: str) -> str:
    """Phrase a injecter dans le prompt systeme pour cadrer la geographie.

    Garantit que l'IA analyse les bonnes zones (pas de 'marche europeen' pour
    un projet en Cote d'Ivoire, conformement au §7 du cadrage).
    """
    zone = macro_zone_for(country)
    if zone == "international":
        return (
            "ADAPTATION GEOGRAPHIQUE : pays cible non identifie. Analyser le "
            "marche mondial puis cadrer sur le pays cible mentionne dans les "
            "variables, sans references europeennes ou africaines arbitraires."
        )
    return (
        f"ADAPTATION GEOGRAPHIQUE (regle imperative §7 cadrage EVKHA) : le projet "
        f"est en {country}. Analyser le marche mondial puis le marche {zone}, "
        f"puis le pays cible. Ne JAMAIS analyser le marche europeen, asiatique "
        f"ou americain si le projet ne s'y trouve pas. Toute reference a une "
        f"zone non pertinente est une erreur."
    )


def chapter_title_em_01(country: str) -> str:
    """Titre du chapitre 1 EM adapte au pays (substitue le titre statique)."""
    zone = macro_zone_for(country)
    if zone == "international":
        return "Analyse chiffrée du marché mondial"
    return f"Analyse chiffrée du marché mondial et {zone}"

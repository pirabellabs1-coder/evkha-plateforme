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
}

_CONTINENT_LABELS: dict[str, str] = {
    "africain":         "africain",
    "europeen":         "européen",
    "maghrebin":        "maghrébin",
    "nord-americain":   "nord-américain",
    "caribeen":         "caribéen et antillais",
    "ocean indien":     "de l'océan Indien",
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

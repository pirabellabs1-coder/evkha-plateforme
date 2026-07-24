from __future__ import annotations

import re
from typing import Any

from .models import ChapterGeneration, CoherenceFact, FactKind, FactProvenance, GenerationJob

# Detection des chiffres cles dans le contenu genere (§5 cadrage : aucun chiffre
# contradictoire entre chapitres). Premiere mention -> verrou ; mention ulterieure
# differente -> CoherenceConflictError -> incident.
_TCAC_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"TCAC\s*(?:de\s+|d['e]?\s+|:\s*)?(\d+(?:[.,]\d+)?)\s*%", re.IGNORECASE),
    re.compile(
        r"taux de croissance annuel moyen\s*(?:de\s+|:\s*)?(\d+(?:[.,]\d+)?)\s*%",
        re.IGNORECASE,
    ),
)
_MARKET_SIZE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"march[ée]\s+(?:mondial|global|national|local|regional|europe|europ[ée]en|africain)?\s*"
        r"(?:de\s+|estim[ée]\s+a\s+|atteint\s+|p[èe]se\s+|repr[ée]sente\s+)"
        r"(\d+(?:[.,]\d+)?)\s*(milliards?|mds?|millions?|m€|md€|mds?€|mfcfa)",
        re.IGNORECASE,
    ),
)

# ── Trois niveaux de marche (Evangeline, question 1 du 17/07/2026) ──────────
#
# « On a suite aux deux premiers chapitres : des chiffres mondiaux, continentaux,
# nationaux et on les garde pour continuer l'etude sur la meme lignee. »
#
# Le motif `_MARKET_SIZE_PATTERNS` capturait deja les trois niveaux dans une
# cle unique. On garde le meme pattern souple, on DISCRIMINE la cle apres :
# rechercher un qualificatif de zone dans la fenetre du match, plutot que
# d'exiger « marche mondial ... pese X » a la lettre. Constate sur SYNAPSES
# v2 : le modele redige « la croissance europeenne est de 8 % », « a l'echelle
# europeenne le marche represente 8 milliards » — trois patterns rigides ne
# les capturaient pas, un pattern souple + discrimination par mot cle si.
_NIVEAUX_QUALIFIANTS: dict[str, re.Pattern[str]] = {
    "mondial":     re.compile(
        r"\b(?:mondial(?:e|es|aux)?|global(?:e|es|aux)?|international(?:e|es|aux)?|"
        r"plan[ée]taire)\b",
        re.IGNORECASE,
    ),
    "continental": re.compile(
        r"\b(?:europ[ée]en(?:ne|nes|s)?|europe|africain(?:e|es|s)?|"
        r"asiatique(?:s)?|am[ée]ricain(?:e|es|s)?|maghr[ée]bin(?:e|es|s)?|"
        r"caribe[ée]n(?:ne|nes|s)?)\b",
        re.IGNORECASE,
    ),
    "national":    re.compile(
        r"\b(?:national(?:e|es|aux)?|domestique(?:s)?|hexagonal(?:e|es|aux)?|"
        r"francais(?:e|es)?)\b",
        re.IGNORECASE,
    ),
}

# Mesure de marche : un montant en Md/M/euros/FCFA, precede d'un verbe de
# valeur, sur une fenetre de contexte assez large pour englober le
# qualificatif de zone.
_TAILLE_MARCHE_UNIVERSAL = re.compile(
    r"march[ée][^.\n]{0,80}?"
    r"(?:de|estim[ée]\s+[àa]|atteint|p[èe]se|repr[ée]sente|s['’]\s*[ée]l[eè]ve\s+[àa])"
    r"\s+(\d+(?:[.,]\d+)?)\s*(milliards?|mds?|millions?|m€|md€|mds?€|mfcfa)",
    re.IGNORECASE,
)
# TCAC en pourcentage, meme logique de contexte souple.
_TCAC_UNIVERSAL = re.compile(
    r"(?:TCAC|taux\s+de\s+croissance(?:\s+annuel\s+moyen)?|croissance)"
    r"[^.\n]{0,60}?"
    r"(?:de|est\s+de|:|s['’]\s*[ée]l[eè]ve\s+[àa]|atteint)\s+"
    r"(\d+(?:[.,]\d+)?)\s*%",
    re.IGNORECASE,
)


def _classer_niveau(contexte: str) -> str | None:
    """Retourne 'mondial', 'continental' ou 'national' si un qualificatif de
    zone se trouve dans le contexte proche. Sinon None : la mention est
    globale sans niveau precis, on n'ecrase pas une eventuelle valeur par
    niveau deja verrouillee."""
    for niveau, motif in _NIVEAUX_QUALIFIANTS.items():
        if motif.search(contexte):
            return niveau
    return None

# Chiffres financiers projet — verrouilles pour eviter les glissements
# silencieux d'un chapitre a l'autre (CA cible qui passe de 285 000 a
# 287 500 EUR, seuil qui varie de 3 %, panier moyen qui s'ajuste sans
# annonce...). Retour client juillet 2026 : "certains chiffres ne sont
# pas les memes ou sont un peu modifies d'un chapitre a l'autre".
_CA_CIBLE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?:chiffre\s+d['e]?affaires?|CA)\s+(?:cible|projet[ée]|previsionnel|"
        r"objectif|attendu|d['e]?annee\s*1|annee\s*1)\s*(?:de\s+|estim[ée]\s+a\s+|"
        r"a\s+|:\s*)?(\d[\d\s]*)\s*(?:€|euros?|EUR|k\s*€|k\s*EUR)",
        re.IGNORECASE,
    ),
)
_SEUIL_RENTABILITE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"seuil\s+de\s+rentabilit[ée]\s*(?:se\s+situe\s+a\s+|est\s+de\s+|:\s*|de\s+)?"
        r"(\d[\d\s]*)\s*(?:€|euros?|EUR)",
        re.IGNORECASE,
    ),
    re.compile(
        r"point\s+mort\s*(?:a\s+|est\s+de\s+|:\s*|de\s+)?"
        r"(\d[\d\s]*)\s*(?:€|euros?|EUR)",
        re.IGNORECASE,
    ),
)
_PANIER_MOYEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?:panier|ticket)\s+moyen\s*(?:de\s+|estim[ée]\s+a\s+|:\s*|est\s+de\s+)?"
        r"(\d+(?:[.,]\d+)?)\s*(?:€|euros?|EUR)",
        re.IGNORECASE,
    ),
    re.compile(
        r"prix\s+moyen(?:\s+par\s+client)?\s*(?:de\s+|estim[ée]\s+a\s+|:\s*|est\s+de\s+)?"
        r"(\d+(?:[.,]\d+)?)\s*(?:€|euros?|EUR)",
        re.IGNORECASE,
    ),
)
_MARGE_BRUTE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?:taux\s+de\s+)?marge\s+brute\s*(?:est\s+de\s+|se\s+situe\s+a\s+|:\s*|de\s+)?"
        r"(\d+(?:[.,]\d+)?)\s*%",
        re.IGNORECASE,
    ),
)

# Devise officielle par pays (cle de coherence transverse a tous les chapitres).
# Table volontairement minimale et extensible ; defaut prudent sinon.
_COUNTRY_CURRENCY: dict[str, str] = {
    "benin": "XOF",
    "cote d'ivoire": "XOF",
    "cote d ivoire": "XOF",
    "senegal": "XOF",
    "togo": "XOF",
    "burkina faso": "XOF",
    "mali": "XOF",
    "niger": "XOF",
    "cameroun": "XAF",
    "gabon": "XAF",
    "tchad": "XAF",
    "centrafrique": "XAF",
    "republique centrafricaine": "XAF",
    "congo": "XAF",
    "congo-brazzaville": "XAF",
    "republique democratique du congo": "CDF",
    "rdc": "CDF",
    "guinee": "GNF",
    "madagascar": "MGA",
    "mauritanie": "MRU",
    "rwanda": "RWF",
    "burundi": "BIF",
    "kenya": "KES",
    "afrique du sud": "ZAR",
    "haiti": "HTG",
    "djibouti": "DJF",
    "comores": "KMF",
    "france": "EUR",
    "belgique": "EUR",
    "allemagne": "EUR",
    "espagne": "EUR",
    "maroc": "MAD",
    "tunisie": "TND",
    "canada": "CAD",
    "suisse": "CHF",
    "nigeria": "NGN",
    "ghana": "GHS",
}


class CoherenceConflictError(ValueError):
    pass


# Seuil de tolerance relative pour les valeurs numeriques : en-deca,
# on considere que les deux valeurs sont dans le meme ordre de grandeur
# (ex: 8.4% vs 9.0% = 7% d'ecart -> ignore). Au-dela, conflict reel
# (ex: 8.4% vs 13% = 35% d'ecart -> incident MEDIUM, pas d'arret).
_NUMERIC_CONFLICT_TOLERANCE = 0.20


_NUMERIC_PREFIX_RE = re.compile(r"^\s*([\d\s\xa0]+(?:[.,]\d+)?)")


def _numeric_gap(a: str, b: str) -> float | None:
    """Retourne l'ecart relatif entre deux valeurs numeriques (apres strip %).

    Tolerant aux suffixes d'unite (" EUR", " Mds EUR", " %", "..."). Extrait
    le prefixe numerique de chaque cote et compare. Retourne None si l'un
    des deux ne commence pas par un nombre.
    """
    try:
        ma = _NUMERIC_PREFIX_RE.match(a)
        mb = _NUMERIC_PREFIX_RE.match(b)
        if not ma or not mb:
            return None
        va = float(ma.group(1).replace(" ", "").replace("\xa0", "").replace(",", "."))
        vb = float(mb.group(1).replace(" ", "").replace("\xa0", "").replace(",", "."))
        denom = max(abs(va), abs(vb))
        if denom == 0:
            return 0.0
        return abs(va - vb) / denom
    except (ValueError, AttributeError):
        return None


def upsert_locked_fact(
    *,
    job: GenerationJob,
    kind: FactKind,
    key: str,
    value: str,
    source_chapter_number: int | None = None,
    provenance: str = FactProvenance.GENERATED,
) -> CoherenceFact:
    """Verrouille un fait, avec hierarchie des sources (brief client juillet 2026).

    Regles de priorite :
    - Un fait CLIENT (brief) est intangible : une valeur GENERATED divergente
      ne l'ecrase jamais. Tolerance ZERO : tout ecart avec un fait client cree
      un incident HIGH (repris par le gate de livraison).
    - Un fait CLIENT remplace toujours un fait GENERATED existant (le brief
      prime sur toute extraction du modele).
    - Entre deux faits GENERATED : ecart < 20% ignore, sinon incident MEDIUM.
    N'arrete JAMAIS la generation — un conflit de chiffre est une imperfection
    de contenu, pas une erreur systeme ; le gate decide de bloquer la sortie.

    Les valeurs client (SECTEUR, ZONE, FORME_JURIDIQUE...) sont du texte libre
    sans limite cote formulaire Tally. Tronquees a la longueur du champ pour
    ne jamais faire planter le job sur un DataError Postgres — un fait de
    coherence legerement tronque vaut mieux qu'un job qui ne demarre jamais.
    """
    from monitoring.models import IncidentSeverity, OperationalIncident  # noqa: PLC0415

    max_len = CoherenceFact._meta.get_field("value").max_length
    if max_len is not None and len(value) > max_len:
        # Troncature signalee, jamais silencieuse (audit juillet 2026) : une
        # liste de verticales tronquee perd sa derniere activite, et le check
        # de completude du gate cherche alors un libelle coupe qu'il ne
        # trouvera jamais — faux positif bloquant, cause introuvable.
        OperationalIncident.objects.get_or_create(
            title=f"Fait client tronque {kind}:{key} job {job.id}",
            defaults={
                "severity": IncidentSeverity.MEDIUM,
                "job": job,
                "order": job.order,
                "details": {
                    "cle": key,
                    "longueur_recue": len(value),
                    "longueur_max": max_len,
                    "valeur_tronquee": value[:max_len],
                    "hint": "Raccourcir la valeur dans le brief ou augmenter le champ.",
                },
            },
        )
        value = value[:max_len]

    existing = CoherenceFact.objects.filter(job=job, kind=kind, key=key).first()

    # Le brief client prime : une valeur CLIENT remplace un fait GENERATED.
    if (
        existing
        and provenance == FactProvenance.CLIENT
        and existing.provenance == FactProvenance.GENERATED
    ):
        existing.value = value
        existing.provenance = FactProvenance.CLIENT
        existing.source_chapter_number = source_chapter_number
        existing.is_locked = True
        existing.save(
            update_fields=["value", "provenance", "source_chapter_number", "is_locked"]
        )
        return existing

    if existing and existing.is_locked and existing.value != value:
        gap = _numeric_gap(existing.value, value)
        client_fact = existing.provenance == FactProvenance.CLIENT
        # Tolerance zero pour un fait client ; 20% entre faits generes.
        if not client_fact and gap is not None and gap < _NUMERIC_CONFLICT_TOLERANCE:
            # Meme ordre de grandeur — pas de conflit significatif.
            return existing
        if client_fact and gap is not None and gap == 0.0:
            # Meme valeur numerique, formatage different — pas un conflit.
            return existing

        # Conflit reel : alerter l'admin mais NE PAS stopper la generation.
        # Un ecart avec un fait CLIENT est HIGH : le gate de livraison bloque.
        OperationalIncident.objects.get_or_create(
            title=f"Incoh. donnee {kind}:{key} job {job.id}",
            defaults={
                "severity": IncidentSeverity.HIGH if client_fact else IncidentSeverity.MEDIUM,
                "job": job,
                "order": job.order,
                "details": {
                    "valeur_verrouillee": existing.value,
                    "valeur_conflictuelle": value,
                    "provenance_verrouillee": existing.provenance,
                    "chapitre": source_chapter_number,
                    "ecart_relatif": f"{gap:.0%}" if gap is not None else "non-numerique",
                },
            },
        )
        # Garde la valeur verrouillee — le brief client (ou la 1ere mention) fait foi.
        return existing

    fact, _created = CoherenceFact.objects.update_or_create(
        job=job,
        kind=kind,
        key=key,
        defaults={
            "value": value,
            "source_chapter_number": source_chapter_number,
            "is_locked": True,
            "provenance": provenance,
        },
    )
    return fact


# Etat chiffre client (Brique 1, brief juillet 2026) : variables financieres
# structurees du brief, verrouillees en provenance CLIENT avant toute
# generation. Le modele recoit ces valeurs deja ecrites ; le gate de
# livraison verifie tolerance zero sur ces cles.
_CLIENT_FINANCIAL_VARS: dict[str, str] = {
    "INVESTISSEMENT_TOTAL":       "investissement_total",
    "APPORT":                     "apport",
    "EMPRUNT":                    "emprunt",
    "SUBVENTIONS":                "subventions",
    "CA_PREVISIONNEL":            "ca_previsionnel",
    "EBE_PREVISIONNEL":           "ebe_previsionnel",
    "RESULTAT_NET_PREVISIONNEL":  "resultat_net_previsionnel",
    "TAUX_OCCUPATION":            "taux_occupation",
    "SEUIL_RENTABILITE":          "seuil_rentabilite",
}


def seed_locked_facts_from_variables(
    job: GenerationJob,
    variables: dict[str, Any],
) -> None:
    """Verrouille les faits deduits des variables de cadrage, provenance CLIENT.

    Idempotent : meme valeur -> pas de conflit. Source = donnees client figees,
    donc base fiable du Coherence Engine pour tous les chapitres suivants.
    Inclut l'etat chiffre client (Brique 1) : previsionnel financier et
    verticales d'activite, intangibles pour toute la generation.
    """

    def _seed(kind: FactKind, key: str, value: str) -> None:
        upsert_locked_fact(
            job=job, kind=kind, key=key, value=value,
            provenance=FactProvenance.CLIENT,
        )

    sector = str(variables.get("SECTEUR", "")).strip()
    if sector:
        _seed(FactKind.ASSUMPTION, "secteur", sector)

    zone = str(variables.get("ZONE", "")).strip()
    if zone:
        _seed(FactKind.ASSUMPTION, "zone", zone)

    country = str(variables.get("PAYS", "")).strip()
    if country:
        from .geography import _strip_accents  # noqa: PLC0415

        # Accent-insensible : "Guinée" et "guinee" doivent matcher.
        currency = _COUNTRY_CURRENCY.get(_strip_accents(country.lower()))
        if currency:
            _seed(FactKind.CURRENCY, "currency", currency)

    # BP specifiques : forme juridique et capital verrouilles pour coherence
    # des projections financieres (meme statut du chap. 2 au chap. 10).
    forme = str(variables.get("FORME_JURIDIQUE", "")).strip()
    if forme:
        _seed(FactKind.ASSUMPTION, "forme_juridique", forme)

    capital = str(variables.get("CAPITAL_INITIAL", "")).strip()
    if capital:
        _seed(FactKind.ASSUMPTION, "capital_initial", capital)

    # Etat chiffre client (Brique 1) : chaque variable financiere du brief
    # devient un fait CLIENT intangible.
    for var_name, fact_key in _CLIENT_FINANCIAL_VARS.items():
        raw = variables.get(var_name)
        if isinstance(raw, list):
            value = " / ".join(str(x).strip() for x in raw if str(x).strip())
        else:
            value = str(raw or "").strip()
        if value:
            _seed(FactKind.ASSUMPTION, fact_key, value)

    # Verticales d'activite du brief : liste intangible ; le gate verifie que
    # chacune apparait dans le livrable (check completude, Brique 3).
    verticales = variables.get("VERTICALES")
    if isinstance(verticales, list):
        verticales_value = " / ".join(str(x).strip() for x in verticales if str(x).strip())
    else:
        verticales_value = str(verticales or "").strip()
    if verticales_value:
        _seed(FactKind.ASSUMPTION, "verticales", verticales_value)


def client_facts_as_context(job: GenerationJob) -> str:
    """Faits issus du brief client : intangibles, priorite absolue."""
    facts = job.coherence_facts.filter(
        is_locked=True, provenance=FactProvenance.CLIENT
    ).order_by("kind", "key")
    if not facts:
        return "Aucune donnee client structuree fournie."
    return "\n".join(f"- {fact.key} = {fact.value}" for fact in facts)


def generated_facts_as_context(job: GenerationJob) -> str:
    """Reperes extraits des chapitres deja generes (coherence inter-chapitres).

    Presentes comme reperes a reprendre a l'identique — JAMAIS comme des
    'faits verrouilles du dossier' (brief juillet 2026 : le pipeline
    consolidait des chiffres hallucines en dogme).
    """
    facts = job.coherence_facts.filter(
        is_locked=True, provenance=FactProvenance.GENERATED
    ).order_by("kind", "key")
    if not facts:
        return "Aucun repere pour le moment."
    return "\n".join(f"- {fact.key} = {fact.value}" for fact in facts)


def locked_facts_as_context(job: GenerationJob) -> str:
    """Compat : vue combinee (client puis generes). Prefere les deux vues separees."""
    facts = job.coherence_facts.filter(is_locked=True).order_by("kind", "key")
    if not facts:
        return "Aucun fait verrouille pour le moment."
    return "\n".join(f"- {fact.kind}:{fact.key} = {fact.value}" for fact in facts)


# ── Enrichissement de la fiche projet apres un CHECK Sonnet (manuel §5-6) ──
#
# Manuel Evangeline (juillet 2026), §5 « La fiche projet enrichie : la memoire
# de l'etude » : « Apres chaque controle, elle recoit les informations qui
# devront rester coherentes dans la suite. Ces chiffres deviennent
# inviolables pour la suite. »
#
# Cote pipeline, chaque CHECK Sonnet identifie 0 a 10 points structurants
# (chiffres-fondations, definitions, segments prioritaires...) qui doivent
# etre reutilises tels quels par les chapitres suivants. On les persiste
# comme CoherenceFact GENERATED, prefixes par le bloc pour eviter les
# collisions inter-blocs. Ils sont ensuite lus par `generated_facts_as_context`
# qui alimente le contexte injecte dans chaque prompt de chapitre.


# ── Tableau des chiffres-fondations (manuel §5, p. 6) ──────────────────────
#
# Le manuel prescrit un tableau explicite comme carte d'identite chiffree de
# l'etude : « Information | Valeur retenue | Perimetre/annee/unite | Source
# ou methode | Reutilisation ». Enrichi apres le CHECK 1 (bloc A) puis
# maintenu inviolable. Cote pipeline, les faits sont deja stockes dans
# `CoherenceFact` par les extracteurs (`extract_and_lock_chiffres_cles`) et
# les CHECKs (`enrichir_fiche_apres_check`). Cette fonction les rend au
# format tableau attendu par le manuel, et le contexte l'injecte en tete
# des prompts EM (voir `context.py`).

_LIBELLES_FONDATIONS: dict[str, str] = {
    # kinds : ASSUMPTION, CURRENCY, MARKET_SIZE, GROWTH_RATE
    "secteur": "Definition du marche (secteur)",
    "zone": "Zone d'analyse",
    "currency": "Devise",
    "forme_juridique": "Forme juridique du projet",
    "capital_initial": "Capital initial",
    "verticales": "Verticales d'activite",
    # tailles de marche
    "taille_marche": "Marche (perimetre general)",
    "taille_marche_mondial": "Marche mondial",
    "taille_marche_continental": "Marche continental",
    "taille_marche_national": "Marche national",
    "taille_marche_local": "Marche local",
    # TCAC par niveau
    "tcac": "TCAC (general)",
    "tcac_mondial": "TCAC mondial",
    "tcac_continental": "TCAC continental",
    "tcac_national": "TCAC national",
    # projet
    "ca_cible_eur": "CA cible",
    "seuil_rentabilite_eur": "Seuil de rentabilite (repere)",
    "panier_moyen_eur": "Panier / prix moyen",
    "marge_brute": "Marge brute sectorielle",
    "part_de_marche": "Part de marche estimee",
    "nombre_clients": "Nombre de clients cibles",
    "ticket_moyen": "Ticket moyen",
    "taux_occupation": "Taux d'occupation",
    "taux_conversion": "Taux de conversion",
    "taux_retention": "Taux de retention",
    # previsionnel client
    "investissement_total": "Investissement total (brief)",
    "apport": "Apport (brief)",
    "emprunt": "Emprunt (brief)",
    "subventions": "Subventions (brief)",
    "ca_previsionnel": "CA previsionnel (brief)",
    "ebe_previsionnel": "EBE previsionnel (brief)",
    "resultat_net_previsionnel": "Resultat net previsionnel (brief)",
}


def chiffres_fondations_as_table(job: GenerationJob) -> str:
    """Rend les faits verrouilles au format tableau du manuel §5.

    Colonnes : Information | Valeur retenue | Source (chapitre + provenance).
    La colonne « Reutilisation » du manuel est implicite : « tous les
    chapitres suivants ». Les cles enrichies par un CHECK (prefixe
    `bloc_X_...`) sont affichees telles quelles (libelle humanise) car
    elles portent le vocabulaire choisi par le relecteur Sonnet.
    """
    facts = list(job.coherence_facts.filter(is_locked=True).order_by("kind", "key"))
    if not facts:
        return (
            "Aucun chiffre-fondation verrouille pour le moment. Les valeurs "
            "se figeront apres le CHECK 1 (bloc A, fondations du marche)."
        )

    rows: list[str] = []
    for fact in facts:
        cle = str(fact.key or "")
        libelle = _LIBELLES_FONDATIONS.get(cle)
        if libelle is None:
            if cle.startswith("bloc_"):
                # Cle enrichie par un CHECK : humanise le suffixe.
                humanise = cle.replace("_", " ").replace("bloc ", "Bloc ", 1)
                libelle = humanise[:80]
            else:
                # Cle inconnue : on l'affiche telle quelle plutot que la masquer.
                libelle = cle.replace("_", " ")
        source_ch = f"ch. {fact.source_chapter_number}" if fact.source_chapter_number else "brief"
        prov = "CLIENT" if fact.provenance == FactProvenance.CLIENT else "genere"
        rows.append(f"| {libelle} | {fact.value} | {source_ch} ({prov}) |")

    return (
        "Chiffres-fondations (manuel §5, memoire enrichie). Valeurs "
        "INVIOLABLES : chaque chapitre suivant DOIT les reprendre a "
        "l'identique (definition, annee, unite, valeur).\n\n"
        "| Information | Valeur retenue | Source |\n"
        "|---|---|---|\n"
        + "\n".join(rows)
    )


def enrichir_fiche_apres_check(
    job: GenerationJob,
    *,
    bloc_identifiant: str,
    points: list[tuple[str, str]],
) -> list[CoherenceFact]:
    """Persiste les points identifies par un CHECK dans la fiche enrichie.

    Chaque point (cle, valeur) devient un CoherenceFact GENERATED, avec la
    convention de cle `bloc_{X}_{cle}` (ex : `bloc_A_definition_marche`).
    Les cles deja presentes ne sont pas ecrasees a la legere : `upsert_locked_fact`
    detecte les conflits (tolerance 20 % sur les valeurs numeriques) et cree
    un incident MEDIUM sans stopper la generation.

    Sans effet si `points` est vide. Silencieux si aucun bloc identifie
    (jamais le cas en pratique, mais defensif).
    """
    if not points or not bloc_identifiant:
        return []

    prefixe = f"bloc_{bloc_identifiant}"
    facts: list[CoherenceFact] = []
    for cle_raw, valeur in points:
        cle_normalisee = re.sub(r"[^a-z0-9_]", "_", cle_raw.lower().strip())
        cle_normalisee = re.sub(r"_+", "_", cle_normalisee).strip("_")
        if not cle_normalisee:
            continue
        cle = f"{prefixe}_{cle_normalisee}"[:120]  # cf. max_length du modele
        # kind = ASSUMPTION par defaut : les faits verrouilles "typees"
        # (MARKET_SIZE, GROWTH_RATE, CURRENCY) sont gerees par les
        # extracteurs specialises (extract_and_lock_chiffres_cles), pas ici.
        # Les points d'un CHECK sont des reperes qualitatifs/quantitatifs
        # heterogenes, ASSUMPTION est le bon fourre-tout.
        fact = upsert_locked_fact(
            job=job,
            kind=FactKind.ASSUMPTION,
            key=cle,
            value=valeur,
            provenance=FactProvenance.GENERATED,
        )
        facts.append(fact)
    return facts


def extract_and_lock_chiffres_cles(job: GenerationJob, chapter_number: int, content: str) -> None:
    """Detecte TCAC et taille de marche dans le contenu d'un chapitre et les verrouille.

    Premiere mention fixe la valeur de reference ; les mentions ulterieures
    differentes creent un incident MEDIUM mais ne stoppent pas la generation.
    """
    text = content or ""
    for pattern in _TCAC_PATTERNS:
        match = pattern.search(text)
        if match:
            value = match.group(1).replace(",", ".") + "%"
            upsert_locked_fact(
                job=job,
                kind=FactKind.GROWTH_RATE,
                key="tcac",
                value=value,
                source_chapter_number=chapter_number,
            )
            break

    for pattern in _MARKET_SIZE_PATTERNS:
        match = pattern.search(text)
        if match:
            value = f"{match.group(1)} {match.group(2)}".strip()
            upsert_locked_fact(
                job=job,
                kind=FactKind.MARKET_SIZE,
                key="taille_marche",
                value=value,
                source_chapter_number=chapter_number,
            )
            break

    # Trois niveaux distincts (mondial / continental / national), verrouilles
    # separement. Consigne d'Evangeline (Q1 du 17/07/2026) : les chiffres des
    # deux premiers chapitres EM doivent etre gardes tout le long. Une seule
    # cle globale ne suffisait pas ; l'IA melangeait les niveaux d'un chapitre
    # a l'autre.
    #
    # Approche : un seul motif universel qui capture le montant, puis on
    # classe la MENTION par le qualificatif de zone present dans le contexte
    # proche. Refonte apres SYNAPSES v2 : 3 patterns rigides ne capturaient
    # rien parce que le modele redige naturellement (« la croissance
    # europeenne est de 8 % ») au lieu de « marche europeen ... pese X ».
    for match in _TAILLE_MARCHE_UNIVERSAL.finditer(text):
        # On elargit le contexte a la phrase courante uniquement, en
        # remontant jusqu'au precedent point ou saut de ligne. Ainsi
        # « A l'echelle internationale, le marche pese 30 milliards »
        # est classe « mondial » (qualificatif AVANT le match), sans qu'une
        # phrase precedente ne pollue la classification.
        avant = text[max(0, match.start() - 120) : match.start()]
        borne = max(avant.rfind("."), avant.rfind("\n"), avant.rfind("!"),
                    avant.rfind("?"))
        contexte = (avant[borne + 1 :] if borne >= 0 else avant) + match.group(0)
        niveau = _classer_niveau(contexte)
        if niveau is None:
            continue
        value = f"{match.group(1)} {match.group(2)}".strip()
        upsert_locked_fact(
            job=job,
            kind=FactKind.MARKET_SIZE,
            key=f"taille_marche_{niveau}",
            value=value,
            source_chapter_number=chapter_number,
        )
    for match in _TCAC_UNIVERSAL.finditer(text):
        # On elargit le contexte a la phrase courante uniquement, en
        # remontant jusqu'au precedent point ou saut de ligne. Ainsi
        # « A l'echelle internationale, le marche pese 30 milliards »
        # est classe « mondial » (qualificatif AVANT le match), sans qu'une
        # phrase precedente ne pollue la classification.
        avant = text[max(0, match.start() - 120) : match.start()]
        borne = max(avant.rfind("."), avant.rfind("\n"), avant.rfind("!"),
                    avant.rfind("?"))
        contexte = (avant[borne + 1 :] if borne >= 0 else avant) + match.group(0)
        niveau = _classer_niveau(contexte)
        if niveau is None:
            continue
        value = match.group(1).replace(",", ".") + "%"
        upsert_locked_fact(
            job=job,
            kind=FactKind.GROWTH_RATE,
            key=f"tcac_{niveau}",
            value=value,
            source_chapter_number=chapter_number,
        )

    # Chiffres financiers projet : CA cible, seuil de rentabilite, panier
    # moyen, marge brute. Verrouilles a la 1ere mention, les mentions
    # ulterieures divergentes creent un incident MEDIUM (non-bloquant) qui
    # remonte au dashboard admin sans arreter la generation.
    for pattern in _CA_CIBLE_PATTERNS:
        match = pattern.search(text)
        if match:
            raw = match.group(1).replace(" ", "").replace("\xa0", "")
            upsert_locked_fact(
                job=job, kind=FactKind.ASSUMPTION, key="ca_cible_eur",
                value=f"{raw} EUR", source_chapter_number=chapter_number,
            )
            break
    for pattern in _SEUIL_RENTABILITE_PATTERNS:
        match = pattern.search(text)
        if match:
            raw = match.group(1).replace(" ", "").replace("\xa0", "")
            upsert_locked_fact(
                job=job, kind=FactKind.ASSUMPTION, key="seuil_rentabilite_eur",
                value=f"{raw} EUR", source_chapter_number=chapter_number,
            )
            break
    for pattern in _PANIER_MOYEN_PATTERNS:
        match = pattern.search(text)
        if match:
            value = match.group(1).replace(",", ".")
            upsert_locked_fact(
                job=job, kind=FactKind.ASSUMPTION, key="panier_moyen_eur",
                value=f"{value} EUR", source_chapter_number=chapter_number,
            )
            break
    for pattern in _MARGE_BRUTE_PATTERNS:
        match = pattern.search(text)
        if match:
            value = match.group(1).replace(",", ".") + "%"
            upsert_locked_fact(
                job=job, kind=FactKind.ASSUMPTION, key="marge_brute",
                value=value, source_chapter_number=chapter_number,
            )
            break
# QC Evangeline #2 : extraction des chiffres cles labellises verrouilles apres
# chaque chapitre, en complement de extract_and_lock_chiffres_cles ci-dessus.
# Sans ca, chaque chapitre reinventait ses propres valeurs (6 chiffres
# differents pour "micro-entrepreneurs actifs" sur une meme etude) — un cas
# que _MARKET_SIZE_PATTERNS (cle fixe "taille_marche") ne couvre pas car
# chaque entite labellisee a besoin de sa propre cle.

# Motifs syntaxiques : liste blanche STRICTE de concepts metier.
#
# Refonte apres SYNAPSES v3 (juillet 2026) : les patterns generiques
# `[A-Za-zÀ-ÿ' -]{3,60}` capturaient des fragments de phrase comme
# « nombre de micro-entrepreneurs actifs dans l'Herault a progressé de » et
# creaient des clefs de fait de 60 caracteres qui ne designaient aucun
# concept metier. Chaque variante lexicale d'un meme concept produisait
# une clef distincte (« taux de remplissage progressifs », « retenus sont »,
# « volontairement conservateurs » = trois clefs pour la meme chose), ce
# qui violait la regle 5 (une seule source par verite).
#
# Nouveau motif : chaque concept est nomme explicitement (regle 4 : viser la
# classe, pas l'exemple). Aucun libelle ne peut etre plus long qu'un intitule
# metier reconnu. Les concepts qu'on souhaite verrouiller mais qui sont deja
# couverts par des patterns dedies plus specifiques (CA cible, seuil de
# rentabilite, panier moyen, marge brute, taille de marche, TCAC par niveau)
# ne sont PAS repetes ici — la regle 5 l'exige : une seule source.
_CONCEPTS_METIER: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("taux_occupation",  re.compile(
        r"taux\s+d['’]?\s*occupation",
        re.IGNORECASE,
    )),
    ("taux_conversion",  re.compile(
        r"taux\s+de\s+conversion",
        re.IGNORECASE,
    )),
    ("taux_retention",   re.compile(
        r"taux\s+de\s+r[ée]tention",
        re.IGNORECASE,
    )),
    ("part_de_marche",   re.compile(
        r"parts?\s+de\s+march[ée]",
        re.IGNORECASE,
    )),
    ("nombre_clients",   re.compile(
        r"nombre\s+de\s+clients?(?:\s+cibles?)?",
        re.IGNORECASE,
    )),
    ("ticket_moyen",     re.compile(
        r"ticket\s+moyen|panier\s+moyen",
        re.IGNORECASE,
    )),
)

# Motif de valeur qui SUIT le concept (verbe de valeur obligatoire, plus la
# valeur elle-meme). Impose une liaison syntaxique — regle 9, meme logique
# que pour `checks_evangeline` : la proximite seule cree des faux positifs.
_VALEUR_APRES_CONCEPT = re.compile(
    r"\s*(?:est\s+de|s['’]\s*[eé]l[eè]ve\s+[àa]|atteint|de|:|=|"
    r"repr[eé]sente|se\s+situe\s+[àa])\s*"
    r"(?P<value>[0-9][0-9\s.,]{0,15})\s*"
    r"(?P<unit>%|M€|Md€|Mds€|k€|EUR|euros?|milliards?|millions?)",
    re.IGNORECASE,
)


def _normalize_key(label: str) -> str:
    key = label.strip().lower()
    key = re.sub(r"['’]", " ", key)
    key = re.sub(r"\s+", "_", key)
    key = re.sub(r"[^a-z0-9_àáâäéèêëîïôöùûüç-]", "", key)
    return key[:120]


def _normalize_value(value: str, unit: str) -> str:
    v = re.sub(r"\s+", "", value.strip())
    u = unit.strip()
    return f"{v} {u}".strip()


def extract_and_lock_numeric_facts(chapter: ChapterGeneration) -> list[CoherenceFact]:
    """Extrait les chiffres cles explicitement libelles et les verrouille.

    Regle : premier chapitre a mentionner un libelle => valeur figee pour tous
    les chapitres suivants. Un conflit ulterieur (autre chapitre, meme cle,
    autre valeur) leve CoherenceConflictError si is_locked, sinon MAJ.

    Comportement conservateur : on ne verrouille qu'un pattern strict
    (libelle + chiffre + unite). Le but n'est pas d'exhaustivite mais de
    verrouiller les 10-15 chiffres structurants qui plombent la coherence.
    """
    locked: list[CoherenceFact] = []
    content = chapter.content or ""
    seen_keys: set[str] = set()
    for cle, motif_concept in _CONCEPTS_METIER:
        if cle in seen_keys:
            continue
        for m in motif_concept.finditer(content):
            valeur = _VALEUR_APRES_CONCEPT.match(content, m.end())
            if not valeur:
                continue
            seen_keys.add(cle)
            existing = CoherenceFact.objects.filter(
                job=chapter.job, kind=FactKind.MARKET_SIZE, key=cle
            ).first()
            if existing and existing.is_locked:
                break
            value = _normalize_value(valeur.group("value"), valeur.group("unit"))
            fact = upsert_locked_fact(
                job=chapter.job,
                kind=FactKind.MARKET_SIZE,
                key=cle,
                value=value,
                source_chapter_number=chapter.chapter_number,
            )
            locked.append(fact)
            break
    return locked

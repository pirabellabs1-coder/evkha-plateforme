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
    r"(?:de|estim[ée]\s+[àa]|atteint|p[èe]se|repr[ée]sente|s[‘’]\s*[ée]l[eè]ve\s+[àa])"
    r"\s+[~≈]?\s*(?:environ\s+)?(\d+(?:[.,]\d+)?)\s*(milliards?|mds?|millions?|m€|md€|mds?€|mfcfa)",
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


# ── Marche accessible : TAM / SAM / SOM (manuel p. 6, ligne dediee) ─────────
#
# Le manuel prescrit noir sur blanc, dans le tableau des chiffres-fondations,
# une ligne « TAM / SAM / SOM | Annee — hypotheses | Formule et sources |
# Ch. 2, 14, 15 ». Aucune cle ne la portait : les trois seuls chiffres que le
# manuel nomme explicitement etaient les seuls que le registre ne tenait pas.
#
# Constat du run reel 010e3bf2 (WAOME, juillet 2026), chapitre 2 :
#   - deux valeurs pour le meme indicateur (SAM regional 240 kEUR puis
#     250 kEUR) dans un seul chapitre, ce que la page 5 du manuel interdit
#     (« un chiffre valide ne doit pas changer de definition, d'annee,
#     d'unite ou de valeur ») ;
#   - un SOM annee 1 a 100-120 kEUR contre un SAM regional de 250 kEUR, soit
#     ~44 % du marche accessible capte des la premiere annee, que le texte
#     JUSTIFIE (« ce taux de capture eleve s'explique par... ») au lieu de le
#     recalculer.
#
# On capture donc l'acronyme puis le premier montant de la meme phrase. Le
# point est exclu de la fenetre : en francais les montants s'ecrivent avec une
# virgule decimale, donc un point signale une fin de phrase et interdit de
# lier un acronyme au montant de la phrase suivante.
_TAM_SAM_SOM_UNIVERSAL = re.compile(
    r"\b(TAM|SAM|SOM)\b[^.\n|<;]{0,70}?"
    r"(\d+(?:[.,]\d+)?)\s*"
    r"(milliards?|mds?\s*€|mds?|md€|mdeur|millions?|m€|meur|k€|keur|milliers?)",
    re.IGNORECASE,
)

# Facteurs multiplicatifs pour ramener un montant a l'euro. Necessaire parce
# que `_numeric_gap` ne compare que des prefixes numeriques : « 3 MEUR » et
# « 240 kEUR » y paraissent distants de 99 % alors que le premier vaut douze
# fois le second. Tout controle arithmetique exige une unite resolue.
_FACTEURS_UNITE: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"^(?:milliards?|mds?\s*€?|md€|mdeur)$", re.IGNORECASE), 1_000_000_000),
    (re.compile(r"^(?:millions?|m€|meur)$", re.IGNORECASE), 1_000_000),
    (re.compile(r"^(?:milliers?|k€|keur)$", re.IGNORECASE), 1_000),
)

# Plafond de plausibilite de la part du marche accessible captee en annee 1.
#
# Le run 010e3bf2 affichait un SOM annee 1 entre 40 % et 48 % du SAM regional.
# Une etude de reference sur un projet comparable (meme secteur, meme taille
# de porteur) atterrit autour de 1,5 % la premiere annee. Au-dela de 15 %, il
# n'y a que deux lectures possibles et les deux sont des defauts : soit le SAM
# est sous-estime, soit le SOM est irrealiste. Dans les deux cas le chiffre
# doit repartir en correction, pas en justification.
_PART_SOM_SUR_SAM_MAX = 0.15


def _montant_en_euros(valeur: str) -> float | None:
    """Convertit « 3,2 MEUR », « 240 kEUR », « 4,5 milliards » en euros.

    Retourne None si la chaine ne porte pas d'unite reconnue : sans unite
    resolue, une comparaison TAM/SAM/SOM n'a aucun sens et il vaut mieux ne
    rien conclure que conclure faux.
    """
    match = re.match(
        r"\s*(\d+(?:[.,]\d+)?)\s*"
        r"(milliards?|mds?\s*€?|md€|mdeur|millions?|m€|meur|milliers?|k€|keur)",
        valeur or "",
        re.IGNORECASE,
    )
    if not match:
        return None
    try:
        nombre = float(match.group(1).replace(",", "."))
    except ValueError:
        return None
    unite = match.group(2).strip()
    for pattern, facteur in _FACTEURS_UNITE:
        if pattern.match(unite):
            return nombre * facteur
    return None


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
    # Ligne « TAM / SAM / SOM » du manuel p. 6. Verrouillee au chapitre 2
    # (« Marche national, local et marche accessible »), reutilisee aux
    # chapitres 14 et 15 comme le prescrit la colonne « Reutilisation ».
    "tam": "TAM, marche total adressable",
    "tam_mondial": "TAM mondial",
    "tam_continental": "TAM continental",
    "tam_national": "TAM national",
    "sam": "SAM, marche adressable servi",
    "sam_mondial": "SAM mondial",
    "sam_continental": "SAM continental",
    "sam_national": "SAM national",
    "som": "SOM, marche obtenable",
    "som_mondial": "SOM mondial",
    "som_continental": "SOM continental",
    "som_national": "SOM national",
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


# Colonne « Reutilisation » du tableau des chiffres-fondations, manuel p. 6,
# recopiee a la lettre. Elle ne decore pas : elle dit au redacteur du chapitre
# 14 que son SOM est deja fixe, et au redacteur du chapitre 9 que le marche
# national ne se re-estime pas. Sans elle, chaque chapitre relisait la valeur
# comme une suggestion.
_REUTILISATION_FONDATIONS: dict[str, str] = {
    "secteur": "tous les chapitres",
    "verticales": "tous les chapitres",
    "zone": "tous les chapitres",
    "currency": "tous les chapitres",
    "taille_marche_mondial": "ch. 1, 8, 9, 15, 20",
    "taille_marche_continental": "ch. 1, 8, 9",
    "taille_marche_national": "ch. 2, 9, 15",
    "taille_marche_local": "ch. 2, 14, 17",
    "tcac": "ch. 1, 2, 7, 8",
    "tcac_mondial": "ch. 1, 2, 7, 8",
    "tcac_continental": "ch. 1, 2, 7, 8",
    "tcac_national": "ch. 1, 2, 7, 8",
    "panier_moyen_eur": "ch. 9, 10, 11",
    "ticket_moyen": "ch. 9, 10, 11",
}
# La ligne « TAM / SAM / SOM | Ch. 2, 14, 15 » couvre les douze cles de la
# famille : on l'applique par prefixe plutot que de les enumerer.
_REUTILISATION_FONDATIONS.update(
    {
        cle: "ch. 2, 14, 15"
        for cle in _LIBELLES_FONDATIONS
        if cle.split("_")[0] in ("tam", "sam", "som")
    }
)

# Perimetre lisible deduit du suffixe de niveau. Le manuel demande « Pays —
# annee — devise » : le pays exact vient du brief, le niveau vient de la cle.
_PERIMETRES_LISIBLES: dict[str, str] = {
    "mondial": "monde",
    "continental": "continent",
    "national": "pays de l'etude",
    "local": "zone locale de l'etude",
}
_ANNEE_DANS_VALEUR = re.compile(r"\b(?:19|20)\d{2}\b")
_UNITE_DANS_VALEUR = re.compile(
    r"%|milliards?|millions?|milliers?|mds?\s*€|md€|mdeur|m€|meur|k€|keur|"
    r"fcfa|xof|eur|euros?|€",
    re.IGNORECASE,
)


def _perimetre_annee_unite(cle: str, valeur: str) -> str:
    """Compose la colonne « Perimetre / annee / unite » du manuel p. 6.

    Rien n'est invente : chaque element vient de la cle ou de la valeur
    verrouillee. Ce qui manque est ecrit « a preciser » plutot que devine —
    la fiche sert justement a montrer au redacteur ce qui n'est pas cadre.
    Un fait sans chiffre (definition du marche, verticales) n'a ni annee ni
    unite : on n'affiche que son perimetre.
    """
    niveau = next(
        (n for n in _PERIMETRES_LISIBLES if cle.endswith(f"_{n}")),
        None,
    )
    elements = [_PERIMETRES_LISIBLES.get(niveau or "", "perimetre de l'etude")]
    if any(c.isdigit() for c in valeur):
        annee = _ANNEE_DANS_VALEUR.search(valeur)
        elements.append(annee.group(0) if annee else "annee a preciser")
        unite = _UNITE_DANS_VALEUR.search(valeur)
        elements.append(unite.group(0) if unite else "unite a preciser")
    return " / ".join(elements)


def chiffres_fondations_as_table(job: GenerationJob) -> str:
    """Rend les faits verrouilles au format tableau du manuel p. 6.

    Les cinq colonnes du manuel, dans son ordre : Information | Valeur retenue
    | Perimetre / annee / unite | Source ou methode | Reutilisation.

    Les deux colonnes ajoutees en juillet 2026 ne sont pas cosmetiques. Le
    verdict d'Evangeline sur le run 010e3bf2 (« un chiffre valide ne doit pas
    changer de definition, d'annee, d'unite ou de valeur », p. 5) portait sur
    des ecarts que la table a trois colonnes ne pouvait pas rendre visibles :
    une valeur nue « 250 kEUR » ne dit ni son annee, ni son perimetre, ni
    quels chapitres doivent la reprendre telle quelle.

    Les cles enrichies par un CHECK (prefixe `bloc_X_...`) sont affichees
    telles quelles (libelle humanise) car elles portent le vocabulaire choisi
    par le relecteur Sonnet.
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
        cadrage = _perimetre_annee_unite(cle, str(fact.value or ""))
        reutilisation = _REUTILISATION_FONDATIONS.get(cle, "tous les chapitres suivants")
        rows.append(
            f"| {libelle} | {fact.value} | {cadrage} | {source_ch} ({prov}) "
            f"| {reutilisation} |"
        )

    return (
        "Chiffres-fondations (manuel p. 6, memoire enrichie). Valeurs "
        "INVIOLABLES : chaque chapitre listé dans la colonne « Reutilisation » "
        "DOIT reprendre la valeur a l'identique (definition, annee, unite, "
        "valeur). Une fondation qui doit changer se corrige d'abord ici, "
        "puis dans tous les chapitres concernes — jamais l'inverse.\n\n"
        "| Information | Valeur retenue | Perimetre / annee / unite "
        "| Source ou methode | Reutilisation |\n"
        "|---|---|---|---|---|\n"
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

    # TAM / SAM / SOM : ligne dediee du tableau des chiffres-fondations
    # (manuel p. 6). Meme logique que les tailles de marche ci-dessus : un
    # motif souple capture l'acronyme et le montant, le niveau de zone
    # discrimine la cle quand il est present dans la phrase. Sans niveau, la
    # cle reste l'acronyme nu — c'est le cas majoritaire au chapitre 2, ou
    # « SAM » designe le marche accessible de l'etude sans autre precision.
    for match in _TAM_SAM_SOM_UNIVERSAL.finditer(text):
        acronyme = match.group(1).lower()
        avant = text[max(0, match.start() - 120) : match.start()]
        borne = max(avant.rfind("."), avant.rfind("\n"), avant.rfind("!"),
                    avant.rfind("?"))
        contexte = (avant[borne + 1 :] if borne >= 0 else avant) + match.group(0)
        niveau = _classer_niveau(contexte)
        cle = f"{acronyme}_{niveau}" if niveau else acronyme
        value = f"{match.group(2)} {match.group(3)}".strip()
        upsert_locked_fact(
            job=job,
            kind=FactKind.MARKET_SIZE,
            key=cle,
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

    # Le chapitre vient d'ecrire ses chiffres de marche accessible : c'est le
    # moment ou l'emboitement TAM > SAM > SOM peut etre verifie. Le faire ici
    # plutot qu'au gate seul donne au relecteur (et au dashboard) l'anomalie
    # pendant la generation, quand une correction est encore possible.
    signaler_anomalies_tam_sam_som(job, chapter_number)


def _resoudre_montant(
    facts: dict[str, str],
    acronyme: str,
    perimetre: str,
) -> tuple[str, float] | None:
    """Retourne (cle, montant en euros) pour un acronyme sur un perimetre.

    Repli sur la cle nue : au chapitre 2 le redacteur ecrit souvent « le TAM
    national atteint 90 MEUR » puis « le SAM ressort a 250 kEUR » sans
    requalifier la zone. Comparer un TAM national a un SAM sans niveau reste
    la lecture la plus fidele au texte ; refuser de comparer laisserait
    passer exactement le defaut qu'on cherche.
    """
    candidates = (f"{acronyme}_{perimetre}", acronyme) if perimetre else (acronyme,)
    for cle in candidates:
        brut = facts.get(cle)
        if brut is None:
            continue
        montant = _montant_en_euros(brut)
        if montant is not None:
            return cle, montant
    return None


def anomalies_tam_sam_som(job: GenerationJob) -> list[str]:
    """Verifie l'emboitement TAM >= SAM >= SOM sur les faits verrouilles.

    Lecture seule. Trois anomalies possibles, toutes constatees ou frolees sur
    le run reel 010e3bf2 :
      - SAM > TAM : le marche servi depasse le marche total, impossible ;
      - SOM > SAM : la part obtenable depasse le marche accessible, impossible ;
      - SOM / SAM au-dela de `_PART_SOM_SUR_SAM_MAX` : arithmetiquement
        possible mais commercialement invraisemblable en annee 1.

    Les deux premieres sont des erreurs de calcul, la troisieme une hypothese
    a refaire. Les trois doivent revenir en correction, pas en justification
    redactionnelle (« ce taux de capture eleve s'explique par... »).

    Retourne les libelles d'anomalie, dedoublonnes, dans l'ordre de detection.
    Liste vide = emboitement coherent, ou trop peu de chiffres pour conclure.
    """
    facts = {
        str(fact.key): str(fact.value)
        for fact in job.coherence_facts.filter(
            kind=FactKind.MARKET_SIZE, is_locked=True
        )
    }
    if not facts:
        return []

    # Perimetres reellement mentionnes par l'etude, pas la liste theorique :
    # une etude nationale n'a pas de TAM mondial et n'a pas a etre jugee
    # sur son absence.
    perimetres: list[str] = []
    for cle in facts:
        for acronyme in ("tam", "sam", "som"):
            if cle == acronyme:
                if "" not in perimetres:
                    perimetres.append("")
            elif cle.startswith(f"{acronyme}_"):
                suffixe = cle[len(acronyme) + 1 :]
                if suffixe in _NIVEAUX_QUALIFIANTS and suffixe not in perimetres:
                    perimetres.append(suffixe)

    anomalies: list[str] = []
    for perimetre in perimetres:
        etiquette = perimetre or "perimetre general"
        tam = _resoudre_montant(facts, "tam", perimetre)
        sam = _resoudre_montant(facts, "sam", perimetre)
        som = _resoudre_montant(facts, "som", perimetre)

        if tam and sam and sam[1] > tam[1]:
            anomalies.append(
                f"{etiquette} : SAM ({facts[sam[0]]}) superieur au TAM "
                f"({facts[tam[0]]}). Le marche servi ne peut pas depasser le "
                "marche total adressable."
            )
        if sam and som:
            if som[1] > sam[1]:
                anomalies.append(
                    f"{etiquette} : SOM ({facts[som[0]]}) superieur au SAM "
                    f"({facts[sam[0]]}). La part obtenable ne peut pas depasser "
                    "le marche accessible."
                )
            elif sam[1] > 0:
                part = som[1] / sam[1]
                if part > _PART_SOM_SUR_SAM_MAX:
                    anomalies.append(
                        f"{etiquette} : SOM ({facts[som[0]]}) = {part:.0%} du SAM "
                        f"({facts[sam[0]]}), au-dela du plafond de plausibilite "
                        f"({_PART_SOM_SUR_SAM_MAX:.0%}). Soit le SAM est "
                        "sous-estime, soit le SOM est irrealiste : recalculer, "
                        "ne pas justifier."
                    )
        elif tam and som and som[1] > tam[1]:
            # Sans SAM, l'emboitement se controle au moins contre le TAM.
            anomalies.append(
                f"{etiquette} : SOM ({facts[som[0]]}) superieur au TAM "
                f"({facts[tam[0]]}). Emboitement impossible."
            )

    # Le repli sur la cle nue peut faire remonter deux fois la meme anomalie
    # (perimetre national et perimetre general pointant les memes valeurs).
    return list(dict.fromkeys(anomalies))


def signaler_anomalies_tam_sam_som(job: GenerationJob, chapter_number: int) -> None:
    """Cree un incident MEDIUM si l'emboitement TAM/SAM/SOM est incoherent.

    MEDIUM et non HIGH : la generation continue (regle etablie pour tous les
    conflits de chiffres), et c'est le gate de livraison qui bloque l'envoi
    via `anomalies_tam_sam_som`. L'incident sert a rendre le defaut VISIBLE au
    moment ou il nait, au lieu de le decouvrir sur le document fini.
    """
    from monitoring.models import IncidentSeverity, OperationalIncident  # noqa: PLC0415

    anomalies = anomalies_tam_sam_som(job)
    if not anomalies:
        return
    OperationalIncident.objects.get_or_create(
        title=f"Emboitement TAM/SAM/SOM incoherent job {job.id}",
        defaults={
            "severity": IncidentSeverity.MEDIUM,
            "job": job,
            "order": job.order,
            "details": {
                "chapitre_detection": chapter_number,
                "anomalies": anomalies,
                "regle": (
                    "Manuel EVKHA p. 6 : la ligne TAM / SAM / SOM du tableau "
                    "des chiffres-fondations est reutilisee aux chapitres 2, "
                    "14 et 15. Un emboitement faux contamine les trois."
                ),
            },
        },
    )
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

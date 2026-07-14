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

# Motifs syntaxiques : capture le libelle qui precede un chiffre et l'unite.
# Volontairement conservateur : on ne verrouille QUE ce qui est explicitement
# libelle + chiffre + unite, pour ne pas capturer du bruit.
_LABELED_NUMERIC_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "nombre de X : 1,8 M" / "X actifs : 4,4 millions"
    re.compile(
        r"(?P<label>(?:nombre de|nb de|total de|effectif de|part de|volume de)"
        r"\s+[A-Za-zÀ-ÿ' -]{3,60})"
        r"\s*[:\-]?\s*"
        r"(?P<value>[0-9][0-9\s.,]{0,20})\s*"
        r"(?P<unit>(?:M€|Md€|Mds€|M|Md|Mds|milliards?|millions?|millier[s]?|%|k€|k))",
        re.IGNORECASE,
    ),
    # "CA X : 300 M€" / "chiffre d'affaires de Y = 400 millions d'euros"
    re.compile(
        r"(?P<label>(?:CA|chiffre d['’]affaires|revenus?)\s+(?:de\s+|d['’])?[A-Za-zÀ-ÿ'’ -]{2,40})"
        r"\s*[:\-=]?\s*"
        r"(?P<value>[0-9][0-9\s.,]{0,20})\s*"
        r"(?P<unit>(?:M€|Md€|Mds€|millions?|milliards?)(?:\s+d['’]euros?)?)",
        re.IGNORECASE,
    ),
    # "taux de X : 22 %" / "TCAC de 8,5%"
    re.compile(
        r"(?P<label>(?:taux de|TCAC|taux d['’]|part de|penetration de)\s+[A-Za-zÀ-ÿ'’ -]{2,60})"
        r"\s*[:\-=]?\s*"
        r"(?P<value>[0-9][0-9.,]{0,10})\s*"
        r"(?P<unit>%)",
        re.IGNORECASE,
    ),
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
    for pattern in _LABELED_NUMERIC_PATTERNS:
        for match in pattern.finditer(content):
            key = _normalize_key(match.group("label"))
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            existing = CoherenceFact.objects.filter(
                job=chapter.job, kind=FactKind.MARKET_SIZE, key=key
            ).first()
            if existing and existing.is_locked:
                # Deja verrouille par un chapitre precedent : on ne touche pas.
                # La divergence eventuelle sera detectee par la validation.
                continue
            value = _normalize_value(match.group("value"), match.group("unit"))
            fact = upsert_locked_fact(
                job=chapter.job,
                kind=FactKind.MARKET_SIZE,
                key=key,
                value=value,
                source_chapter_number=chapter.chapter_number,
            )
            locked.append(fact)
    return locked

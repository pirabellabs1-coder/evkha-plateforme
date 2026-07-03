from __future__ import annotations

from typing import Any

from orders.models import Order

from .models import IntakeSource, IntakeStatus, IntakeSubmission

# Variables de cadrage imposees par la methode EVKHA (cahier des charges).
# Ce sont des constantes du domaine, jamais inventees a la volee.
REQUIRED_VARIABLES: tuple[str, ...] = ("SECTEUR", "PAYS", "PROJET", "ZONE")
OPTIONAL_VARIABLES: tuple[str, ...] = (
    # Type de livrable — champ caché Tally, essentiel pour les offres B2B génériques.
    "DELIVERABLE_TYPE",
    # Fiche projet EVKHA (exemple SPEDIM mai 2026) — alimentent le chapitre 0
    "POSITIONNEMENT",
    "CLIENTELE_CIBLE",
    "MODELE_ECONOMIQUE",
    # Transverses
    "ELEMENTS_A_RETENIR",
    "DEMANDES_SPECIFIQUES",
    "CONCURRENTS",
    # Business Plan specifiques
    "CAPITAL_INITIAL",
    "FORME_JURIDIQUE",
    "MODELE_REVENUS",
    "EQUIPE",
    # Strategie specifiques
    "OBJECTIF_STRATEGIQUE",
    "HORIZON_PLANIFICATION",
    # Branding PDF brandé (D8) — optionnelles, fallback palette EVKHA
    "LOGO_URL",
    "COULEUR_PRINCIPALE",
    "COULEUR_SECONDAIRE",
    "NOM_ENTREPRISE",
    # Photos client Business Plan (§14 cadrage : 2-3 photos local/produit/équipe)
    "PHOTO_1",
    "PHOTO_2",
    "PHOTO_3",
    # Resume d'une etude precedente (EC/STR/BP) fourni par le client en texte
    # libre, pour reutiliser le contexte d'un livrable deja realise.
    "CONTEXTE_ETUDE_PRECEDENTE",
)

# Alias label/cle -> variable canonique. Les libelles reels du formulaire Tally
# restent a confirmer ; cette table est volontairement permissive et extensible.
_ALIASES: dict[str, str] = {
    # Tally hidden field : type de livrable (pour offres B2B sans deliverable_type fixe).
    "deliverable_type": "DELIVERABLE_TYPE",
    "type_livrable": "DELIVERABLE_TYPE",
    "livrable": "DELIVERABLE_TYPE",
    # Fiche projet (alias des libelles humains Tally)
    "positionnement":      "POSITIONNEMENT",
    "positionnement marketing": "POSITIONNEMENT",
    "clientele cible":     "CLIENTELE_CIBLE",
    "cible":               "CLIENTELE_CIBLE",
    "clients cibles":      "CLIENTELE_CIBLE",
    "modele economique":   "MODELE_ECONOMIQUE",
    "modele d'affaires":   "MODELE_ECONOMIQUE",
    "modele":              "MODELE_ECONOMIQUE",
    # Photos BP
    "photo 1":             "PHOTO_1",
    "photo principale":    "PHOTO_1",
    "photo du local":      "PHOTO_1",
    "photo 2":             "PHOTO_2",
    "photo produit":       "PHOTO_2",
    "photo 3":             "PHOTO_3",
    "photo equipe":        "PHOTO_3",
    # Resume etude precedente (encadre texte libre Tally, EC/STR/BP)
    "resume de votre etude de marche": "CONTEXTE_ETUDE_PRECEDENTE",
    "resume etude de marche":          "CONTEXTE_ETUDE_PRECEDENTE",
    "resume d'une etude precedente":   "CONTEXTE_ETUDE_PRECEDENTE",
    "resume etude precedente":         "CONTEXTE_ETUDE_PRECEDENTE",
    "contexte etude precedente":       "CONTEXTE_ETUDE_PRECEDENTE",
    "document precedent":              "CONTEXTE_ETUDE_PRECEDENTE",
    "secteur": "SECTEUR",
    "sector": "SECTEUR",
    "pays": "PAYS",
    "country": "PAYS",
    "projet": "PROJET",
    "project": "PROJET",
    "description du projet": "PROJET",
    "zone": "ZONE",
    "zone geographique": "ZONE",
    "region": "ZONE",
    "ville": "ZONE",
    "elements a retenir": "ELEMENTS_A_RETENIR",
    "elements importants a retenir": "ELEMENTS_A_RETENIR",
    "elements": "ELEMENTS_A_RETENIR",
    "demandes specifiques": "DEMANDES_SPECIFIQUES",
    "demandes": "DEMANDES_SPECIFIQUES",
    "concurrents": "CONCURRENTS",
    "competitors": "CONCURRENTS",
    # BP
    "capital initial": "CAPITAL_INITIAL",
    "capital": "CAPITAL_INITIAL",
    "apport": "CAPITAL_INITIAL",
    "forme juridique": "FORME_JURIDIQUE",
    "statut juridique": "FORME_JURIDIQUE",
    "statut": "FORME_JURIDIQUE",
    "modele de revenus": "MODELE_REVENUS",
    "sources de revenus": "MODELE_REVENUS",
    "equipe": "EQUIPE",
    "team": "EQUIPE",
    "associes": "EQUIPE",
    # STR
    "objectif strategique": "OBJECTIF_STRATEGIQUE",
    "objectif": "OBJECTIF_STRATEGIQUE",
    "horizon": "HORIZON_PLANIFICATION",
    "horizon de planification": "HORIZON_PLANIFICATION",
    "duree": "HORIZON_PLANIFICATION",
    # Branding PDF (D8)
    "logo url": "LOGO_URL",
    "url logo": "LOGO_URL",
    "logo": "LOGO_URL",
    "logo de votre entreprise": "LOGO_URL",
    "logo de votre entreprise (optionnel)": "LOGO_URL",
    "votre logo": "LOGO_URL",
    "couleur principale": "COULEUR_PRINCIPALE",
    "couleur principale de votre charte graphique": "COULEUR_PRINCIPALE",
    "couleur principale de votre charte graphique (optionnel)": "COULEUR_PRINCIPALE",
    "couleur primaire": "COULEUR_PRINCIPALE",
    "couleur secondaire": "COULEUR_SECONDAIRE",
    "couleur secondaire (optionnel)": "COULEUR_SECONDAIRE",
    "couleur d'accent": "COULEUR_SECONDAIRE",
    "couleur": "COULEUR_PRINCIPALE",
    "nom entreprise": "NOM_ENTREPRISE",
    "nom de l'entreprise": "NOM_ENTREPRISE",
    "nom de votre entreprise": "NOM_ENTREPRISE",
    "raison sociale": "NOM_ENTREPRISE",
    "entreprise": "NOM_ENTREPRISE",
    "société": "NOM_ENTREPRISE",
}

_CANONICAL = set(REQUIRED_VARIABLES) | set(OPTIONAL_VARIABLES)

# Normalisation des libelles humains de "deliverable_type" envoyes par Tally
# vers les codes attendus par DeliverableType. Insensible casse + accents.
_DELIVERABLE_TYPE_VALUES: dict[str, str] = {
    "market_study":              "market_study",
    "etude de marche":           "market_study",
    "etude_marche":              "market_study",
    "competitor_study":          "competitor_study",
    "etude de concurrence":      "competitor_study",
    "etude de la concurrence":   "competitor_study",
    "etude_concurrence":         "competitor_study",
    "business_plan":             "business_plan",
    "business plan":             "business_plan",
    "bp":                        "business_plan",
    "business_strategy":         "business_strategy",
    "strategie business":        "business_strategy",
    "strategie_business":        "business_strategy",
}


def _strip_accents(s: str) -> str:
    import unicodedata  # noqa: PLC0415
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def _normalize_deliverable_type(raw: str) -> str:
    """Renvoie le code DeliverableType ou la valeur brute si non reconnue."""
    key = _strip_accents(str(raw or "").strip().lower())
    return _DELIVERABLE_TYPE_VALUES.get(key, str(raw or ""))


class IntakeIngestionError(ValueError):
    pass


def _lookup(payload: dict[str, Any], *paths: str) -> str:
    for path in paths:
        current: Any = payload
        for part in path.split("."):
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(part)
        if current not in (None, ""):
            return str(current)
    return ""


def _canonical_key(raw_key: str) -> str | None:
    cleaned = raw_key.strip()
    upper = cleaned.upper().replace(" ", "_")
    if upper in _CANONICAL:
        return upper
    return _ALIASES.get(cleaned.lower())


def _collect_raw_pairs(payload: dict[str, Any]) -> dict[str, Any]:
    """Flatten the various payload shapes into a {raw_key: value} dict."""
    pairs: dict[str, Any] = {}

    for container_key in ("normalized_variables", "variables", "answers"):
        container = payload.get(container_key)
        if isinstance(container, dict):
            pairs.update(container)

    # Tally native shape: data.fields = [{label/key, value}, ...]
    field_lists: list[Any] = [payload.get("fields")]
    data = payload.get("data")
    if isinstance(data, dict):
        field_lists.append(data.get("fields"))
    for fields in field_lists:
        if not isinstance(fields, list):
            continue
        for field in fields:
            if not isinstance(field, dict):
                continue
            key = field.get("key") or field.get("label")
            if key is not None and field.get("value") not in (None, ""):
                pairs[str(key)] = field.get("value")

    return pairs


def normalize_intake_variables(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Return (normalized_variables, missing_required_fields)."""
    normalized: dict[str, Any] = {}
    for raw_key, value in _collect_raw_pairs(payload).items():
        canonical = _canonical_key(raw_key)
        if canonical and value not in (None, ""):
            normalized[canonical] = value

    if "DELIVERABLE_TYPE" in normalized:
        normalized["DELIVERABLE_TYPE"] = _normalize_deliverable_type(
            str(normalized["DELIVERABLE_TYPE"])
        )

    missing = [var for var in REQUIRED_VARIABLES if not normalized.get(var)]
    return normalized, missing


def sync_intake_from_tally_payload(payload: dict[str, Any]) -> IntakeSubmission:
    # order_id peut être à la racine (tests/Systeme) ou dans
    # data.fields / data.hiddenFields (Tally natif)
    systeme_order_id = _lookup(
        payload,
        "order_id",
        "systeme_order_id",
        "metadata.order_id",
        "data.hiddenFields.order_id",
    )
    if not systeme_order_id:
        raw_pairs = _collect_raw_pairs(payload)
        systeme_order_id = str(raw_pairs.get("order_id") or raw_pairs.get("systeme_order_id") or "")
    if not systeme_order_id:
        msg = "Tally payload missing required field: order_id"
        raise IntakeIngestionError(msg)

    try:
        order = Order.objects.get(systeme_order_id=systeme_order_id)
    except Order.DoesNotExist as exc:
        msg = f"Unknown order for intake payload: {systeme_order_id}"
        raise IntakeIngestionError(msg) from exc

    variables, missing = normalize_intake_variables(payload)
    status = IntakeStatus.NORMALIZED if not missing else IntakeStatus.INCOMPLETE

    submission, _created = IntakeSubmission.objects.update_or_create(
        order=order,
        defaults={
            "source": IntakeSource.TALLY,
            "status": status,
            "raw_payload": payload,
            "normalized_variables": variables,
            "missing_fields": missing,
        },
    )
    return submission

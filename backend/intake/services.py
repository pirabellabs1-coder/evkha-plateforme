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
    # Etat chiffre client (Brique 1, brief juillet 2026) : previsionnel
    # financier structure du brief. Verrouille en provenance CLIENT avant
    # generation ; tolerance zero au gate de livraison.
    "INVESTISSEMENT_TOTAL",
    "APPORT",
    "EMPRUNT",
    "SUBVENTIONS",
    "CA_PREVISIONNEL",
    "EBE_PREVISIONNEL",
    "RESULTAT_NET_PREVISIONNEL",
    "TAUX_OCCUPATION",
    "SEUIL_RENTABILITE",
    # Verticales d'activite du projet (liste separee par / ou ,) : chaque
    # verticale DOIT apparaitre dans le livrable (check completude du gate).
    "VERTICALES",
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
    # Etat chiffre client (Brique 1)
    "investissement total": "INVESTISSEMENT_TOTAL",
    "investissement initial": "INVESTISSEMENT_TOTAL",
    "montant de l'investissement": "INVESTISSEMENT_TOTAL",
    "apport personnel": "APPORT",
    "apport propre": "APPORT",
    "emprunt": "EMPRUNT",
    "emprunt bancaire": "EMPRUNT",
    "pret bancaire": "EMPRUNT",
    "subventions": "SUBVENTIONS",
    "aides et subventions": "SUBVENTIONS",
    "ca previsionnel": "CA_PREVISIONNEL",
    "chiffre d'affaires previsionnel": "CA_PREVISIONNEL",
    "ca an1 a an5": "CA_PREVISIONNEL",
    "ebe previsionnel": "EBE_PREVISIONNEL",
    "excedent brut d'exploitation": "EBE_PREVISIONNEL",
    "resultat net previsionnel": "RESULTAT_NET_PREVISIONNEL",
    "resultat net": "RESULTAT_NET_PREVISIONNEL",
    "taux d'occupation": "TAUX_OCCUPATION",
    "taux d'occupation previsionnel": "TAUX_OCCUPATION",
    "seuil de rentabilite": "SEUIL_RENTABILITE",
    "point mort": "SEUIL_RENTABILITE",
    "verticales": "VERTICALES",
    "verticales d'activite": "VERTICALES",
    "activites du projet": "VERTICALES",
    "lignes d'activite": "VERTICALES",
    # BP
    "capital initial": "CAPITAL_INITIAL",
    "capital": "CAPITAL_INITIAL",
    "apport": "APPORT",
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


class OrderNotYetAvailableError(RuntimeError):
    """La commande Systeme.io n'existe pas encore — race condition webhook.

    Le webhook Tally peut arriver avant que le webhook Systeme.io ait cree
    la commande en base. Celery retente automatiquement cette tache (max 5
    fois, intervalle 60 s) pour absorber le delai de propagation.
    """


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

    # Tally native shape: data.fields = [{key, label, value}, ...]
    # Register BOTH the machine key (question_xxx) AND the human label
    # so that alias resolution and order_id lookup work regardless of
    # which identifier the downstream code uses.
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
            value = field.get("value")
            if value in (None, ""):
                continue
            key = field.get("key")
            label = field.get("label")
            if key:
                pairs[str(key)] = value
            if label and label != key:
                pairs[str(label)] = value

    return pairs


def normalize_intake_variables(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Return (normalized_variables, missing_required_fields)."""
    normalized: dict[str, Any] = {}
    raw_pairs = _collect_raw_pairs(payload)
    for raw_key, value in raw_pairs.items():
        canonical = _canonical_key(raw_key)
        if canonical and value not in (None, ""):
            normalized[canonical] = value

    if "DELIVERABLE_TYPE" in normalized:
        normalized["DELIVERABLE_TYPE"] = _normalize_deliverable_type(
            str(normalized["DELIVERABLE_TYPE"])
        )

    # Questionnaire simplifié : quand le formulaire Tally n'a pas de champs
    # explicites SECTEUR/PAYS/PROJET/ZONE, on infère à partir des champs texte
    # libres (TEXTAREA) et de defaults raisonnables pour les offres B2C France.
    _infer_missing_from_textareas(payload, normalized)

    missing = [var for var in REQUIRED_VARIABLES if not normalized.get(var)]
    return normalized, missing


def _infer_missing_from_textareas(payload: dict[str, Any], normalized: dict[str, Any]) -> None:
    """Fallback : infer PROJET/SECTEUR/PAYS/ZONE from unlabeled TEXTAREA fields."""
    if all(normalized.get(v) for v in REQUIRED_VARIABLES):
        return

    textareas: list[str] = []
    data = payload.get("data")
    fields = (data.get("fields") if isinstance(data, dict) else None) or payload.get("fields") or []
    for field in fields:
        if not isinstance(field, dict):
            continue
        if field.get("type") == "TEXTAREA" and field.get("value"):
            label = (field.get("label") or "").strip()
            if not label:
                textareas.append(str(field["value"]))

    if not normalized.get("PROJET") and textareas:
        longest = max(textareas, key=len)
        normalized["PROJET"] = longest
    if not normalized.get("SECTEUR") and textareas:
        shortest = min(textareas, key=len)
        if shortest != normalized.get("PROJET"):
            normalized["SECTEUR"] = shortest
        elif len(textareas) > 1:
            normalized["SECTEUR"] = textareas[0]
    if not normalized.get("PAYS"):
        normalized["PAYS"] = "France"
    if not normalized.get("ZONE"):
        normalized["ZONE"] = "France"


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
        msg = f"Order not yet created for intake payload: {systeme_order_id}"
        raise OrderNotYetAvailableError(msg) from exc

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

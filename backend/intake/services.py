from __future__ import annotations

import re
from typing import Any

from orders.models import Order

from .financials import enrich_variables_from_free_text, raffiner_champs_financiers
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
    # Encadres « previsionnel » et « besoins financiers » du formulaire BP :
    # plusieurs chiffres dans un seul champ, mines par `financials.py`.
    "ETAT_CHIFFRE_LIBRE",
    "BESOINS_FINANCIERS",
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
    # Champs BP ajoutes aux formulaires Tally d'Evangeline (fiches inviolables
    # de juillet 2026). Chacun a un champ dedie sur Tally ; sans mapping, ils
    # arrivent en base et ne sont jamais lus.
    "NOM_PORTEUR",
    "PARCOURS_PORTEUR",
    "CONTACT_PORTEUR",
    "DATE_CREATION_PREVUE",
    # Champs STR ajoutes aux formulaires Tally (question 4 d'Evangeline).
    "MODELE_ECONOMIQUE_ACTUEL",
    "OFFRES_ACTUELLES",
    "OFFRES_RENTABLES",
    "OFFRES_CHRONOPHAGES",
    "REGULARITE_REVENUS",
    "POSITIONNEMENT_ACTUEL",
    "CANAUX_ACQUISITION",
    "CHARGE_DIRIGEANT_HEURES",
    "ENTOURAGE_DIRIGEANT",
    "ENJEUX_STRATEGIQUES",
    "QUESTION_STRATEGIQUE",
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
    "secteur et domaine d'activite": "SECTEUR",  # libelle reel EM/STR/EC
    "secteur d'activite": "SECTEUR",
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
    # Encadres du formulaire BP ou la cliente demande le previsionnel en texte
    # libre (« Resultat net previsionnel- EBE- Taux d'occupation- Seuil de
    # rentabilite- Verticales »). Un seul champ, plusieurs chiffres : c'est
    # `financials.py` qui les en extrait, d'ou le rattachement a
    # `_FREE_TEXT_SOURCES` plutot qu'a une variable unique.
    "previsionnel et tableaux financier": "ETAT_CHIFFRE_LIBRE",
    "previsionnel et tableaux financiers": "ETAT_CHIFFRE_LIBRE",
    "tableaux financiers": "ETAT_CHIFFRE_LIBRE",
    "previsionnel": "ETAT_CHIFFRE_LIBRE",
    "besoins financiers & previsions": "BESOINS_FINANCIERS",
    "besoins financiers et previsions": "BESOINS_FINANCIERS",
    "besoins financiers": "BESOINS_FINANCIERS",
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
    # ── Champs Tally reels (juillet 2026) : nom, geographie, porteur BP ─────
    # Le libelle « Nom du projet / de l'entreprise » (BP/EM) est double : il
    # peut recevoir le nom du projet OU celui de l'entreprise. On le mappe a
    # NOM_ENTREPRISE (utilise pour le branding PDF) — c'est la valeur qui
    # servira au rendu ; PROJET est deja capture par le champ description.
    "nom du projet / de l'entreprise":                     "NOM_ENTREPRISE",
    "nom du projet ou de l'entreprise":                    "NOM_ENTREPRISE",
    "nom de l'entreprise (ou future) qui sera etudiee":    "NOM_ENTREPRISE",
    "nom de l'entreprise concernee par la strategie":      "NOM_ENTREPRISE",
    # « Ville ou zone geographique » — ZONE deja mappe pour « zone » et
    # « ville » ci-dessus (lignes ~100). Il manquait juste cette formulation
    # exacte du formulaire Tally refondu.
    "ville ou zone geographique":                          "ZONE",
    # Porteur de projet (BP) — nouveaux champs Tally.
    "nom du porteur de projet":                            "NOM_PORTEUR",
    "porteur de projet":                                   "NOM_PORTEUR",
    "parcours pour l'histoire du projet, tranche d'age":   "PARCOURS_PORTEUR",
    "parcours pour l'histoire du projet":                  "PARCOURS_PORTEUR",
    "parcours du porteur":                                 "PARCOURS_PORTEUR",
    "contact pro : telephone, mail, site, reseaux sociaux": "CONTACT_PORTEUR",
    "contact pro":                                         "CONTACT_PORTEUR",
    "date de creation prevue / statut actuel":             "DATE_CREATION_PREVUE",
    "date de creation prevue":                             "DATE_CREATION_PREVUE",
    "statut actuel":                                       "DATE_CREATION_PREVUE",
    # Strategie business — champs Tally dedies (question 4 d'Evangeline).
    "comment votre entreprise genere-t-elle ses revenus aujourd'hui":
        "MODELE_ECONOMIQUE_ACTUEL",
    "comment votre entreprise genere-t-elle ses revenus aujourd'hui ?":
        "MODELE_ECONOMIQUE_ACTUEL",
    "modele economique actuel":                            "MODELE_ECONOMIQUE_ACTUEL",
    "quelles sont vos offres / prestations actuelles":     "OFFRES_ACTUELLES",
    "offres actuelles":                                    "OFFRES_ACTUELLES",
    "prestations actuelles":                               "OFFRES_ACTUELLES",
    "selon vous, quelles offres sont les plus rentables":  "OFFRES_RENTABLES",
    "offres rentables":                                    "OFFRES_RENTABLES",
    "lesquelles sont les plus chronophages ou peu rentables": "OFFRES_CHRONOPHAGES",
    "offres chronophages":                                 "OFFRES_CHRONOPHAGES",
    "offres peu rentables":                                "OFFRES_CHRONOPHAGES",
    "vos revenus sont-ils plutot reguliers, irreguliers, saisonniers, ou imprevisibles":
        "REGULARITE_REVENUS",
    "regularite des revenus":                              "REGULARITE_REVENUS",
    "comment positionnez-vous votre entreprise aujourd'hui": "POSITIONNEMENT_ACTUEL",
    "positionnement actuel":                               "POSITIONNEMENT_ACTUEL",
    "sur quels canaux attirez-vous actuellement vos clients":
        "CANAUX_ACQUISITION",
    "canaux d'acquisition":                                "CANAUX_ACQUISITION",
    "canaux actuels":                                      "CANAUX_ACQUISITION",
    "combien d'heures par semaine consacrez-vous a votre entreprise":
        "CHARGE_DIRIGEANT_HEURES",
    "charge dirigeant":                                    "CHARGE_DIRIGEANT_HEURES",
    "etes-vous seul(e) ou entoure(e)":                     "ENTOURAGE_DIRIGEANT",
    "entourage dirigeant":                                 "ENTOURAGE_DIRIGEANT",
    "indiquez les sujets qui vous preoccupent reellement aujourd'hui":
        "ENJEUX_STRATEGIQUES",
    "enjeux strategiques":                                 "ENJEUX_STRATEGIQUES",
    "si vous deviez resumer en une phrase la question strategique principale":
        "QUESTION_STRATEGIQUE",
    "si vous deviez resumer en une phrase la question strategique principale "
    "a laquelle vous voulez que cette strategie reponde":
        "QUESTION_STRATEGIQUE",
    "question strategique":                                "QUESTION_STRATEGIQUE",
    "question strategique principale":                     "QUESTION_STRATEGIQUE",
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


# Numerotation de tete : « 10.Investissement total », « 4. Etude de Marche ».
_NUMEROTATION_RE = re.compile(r"^\s*\d+\s*[.)\-]\s*")
# Parenthese de queue : « (optionnel) », « (ou CA an1 a an5) ».
_PARENTHESE_RE = re.compile(r"\s*\([^)]*\)\s*$")
# Ponctuation de queue : « Previsionnel et tableaux financier. », « Secteur : ».
# Le `?` et le `!` sont inclus : les libelles Tally sont souvent formules en
# question (« Comment ... ? ») et une seule ponctuation empechait le mapping.
_PONCTUATION_RE = re.compile(r"[\s.:;,*?!]+$")
_ESPACES_RE = re.compile(r"\s+")
# Apostrophes et tirets typographiques. Tally, Word et les claviers mobiles
# produisent U+2019 ; la table `_ALIASES` est ecrite avec l'apostrophe ASCII.
# « Verticales d’activite » tombait donc, « Verticales d'activite » passait.
# Meme classe que les espaces insecables du gate : une liste fermee de
# caracteres est toujours le probleme, jamais sa composition.
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "´": "'"})


def _label_normalise(brut: str) -> str:
    """Forme comparable d'un libelle Tally.

    Les libelles reels des formulaires d'Evangeline (juillet 2026) ne
    ressemblaient a aucune cle de `_ALIASES` :

        « 10.Investissement total »              -> non reconnu
        « 12.CA previsionnel (ou CA an1 a an5) » -> non reconnu

    Trois causes independantes, toutes du meme motif : la table visait
    l'exemple, pas la classe.

    1. Les accents. `_ALIASES` est ecrit sans accents, et `_canonical_key`
       ne les enlevait pas — alors que `_strip_accents` existe dans ce
       fichier depuis le debut, utilise seulement pour le type de livrable.
       « CA previsionnel » passait, « CA previsionnel » accentue tombait.
    2. La numerotation de tete, que tout formulaire humain porte.
    3. Le suffixe entre parentheses et la ponctuation de queue. La reponse
       avait ete de recopier le libelle entier en alias — d'ou trois entrees
       pour la seule couleur principale. Le quatrieme variant serait tombe.

    Normaliser ici rend ces trois familles inoffensives d'un coup, et les
    alias recopies redondants.
    """
    sans = _strip_accents(str(brut or "")).lower().translate(_APOSTROPHES)
    sans = _NUMEROTATION_RE.sub("", sans)
    sans = _PARENTHESE_RE.sub("", sans)
    sans = _PONCTUATION_RE.sub("", sans)
    return _ESPACES_RE.sub(" ", sans).strip()


# Alias normalises une fois pour toutes : la table reste ecrite lisiblement
# ci-dessus, la comparaison se fait sur la forme reduite.
_ALIASES_NORMALISES: dict[str, str] = {
    _label_normalise(cle): valeur for cle, valeur in _ALIASES.items()
}


def _canonical_key(raw_key: str) -> str | None:
    cleaned = raw_key.strip()
    upper = cleaned.upper().replace(" ", "_")
    if upper in _CANONICAL:
        return upper
    return _ALIASES_NORMALISES.get(_label_normalise(cleaned))


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
            value = _valeur_lisible(field)
            if value in (None, "", []):
                continue
            key = field.get("key")
            label = field.get("label")
            if key:
                pairs[str(key)] = value
            if label and label != key:
                pairs[str(label)] = value

    return pairs


def _valeur_lisible(field: dict[str, Any]) -> Any:
    """La valeur d'un champ Tally, resolue en TEXTE quand c'est un choix.

    Un champ a choix — DROPDOWN, MULTIPLE_CHOICE, CHECKBOXES — n'envoie pas le
    libelle mais une liste d'IDENTIFIANTS d'options ; le texte lisible vit dans
    `field["options"]`, que ce module ne lisait pas.

    Consequence mesuree sur une charge utile reelle : un client qui choisit
    « Benin » dans une liste deroulante produisait
    `PAYS == ["c0a1-11ee-benin"]`. Cette valeur etant non vide, elle passait le
    controle des champs requis, puis partait telle quelle dans le prompt : le
    modele redigeait un chapitre sur un pays nomme `['c0a1-11ee-benin']`.

    Pire sur les cases a cocher : les identifiants des verticales etaient
    verrouilles en faits CLIENT, et le gate allait ensuite les chercher dans le
    document livre — il bloquait donc sur un motif introuvable par le lecteur,
    exactement ce que la regle 2 interdit.

    Une liste vide est rendue telle quelle : c'est une ABSENCE de reponse, et
    l'appelant doit pouvoir la traiter comme telle. `[] not in (None, "")` est
    vrai, donc sans ce traitement la cle etait enregistree vide.
    """
    valeur = field.get("value")
    options = field.get("options")

    if not isinstance(options, list) or not options:
        return valeur

    libelles = {
        str(option.get("id")): str(option.get("text", "")).strip()
        for option in options
        if isinstance(option, dict) and option.get("id") is not None
    }

    def _resoudre(brut: Any) -> str:
        return libelles.get(str(brut)) or str(brut)

    if isinstance(valeur, list):
        textes = [t for t in (_resoudre(v) for v in valeur) if t]
        if not textes:
            return []
        return textes[0] if len(textes) == 1 else ", ".join(textes)

    return _resoudre(valeur) if valeur is not None else valeur


def normalize_intake_variables(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Return (normalized_variables, missing_required_fields)."""
    normalized: dict[str, Any] = {}
    raw_pairs = _collect_raw_pairs(payload)
    for raw_key, value in raw_pairs.items():
        canonical = _canonical_key(raw_key)
        # `[]` = question a choix laissee sans reponse. Sans ce cas, la cle
        # etait enregistree vide et echappait au controle des champs requis.
        if canonical and value not in (None, "", []):
            normalized[canonical] = value

    if "DELIVERABLE_TYPE" in normalized:
        normalized["DELIVERABLE_TYPE"] = _normalize_deliverable_type(
            str(normalized["DELIVERABLE_TYPE"])
        )

    # Questionnaire simplifié : quand le formulaire Tally n'a pas de champs
    # explicites SECTEUR/PAYS/PROJET/ZONE, on infère à partir des champs texte
    # libres (TEXTAREA) et de defaults raisonnables pour les offres B2C France.
    _infer_missing_from_textareas(payload, normalized)

    # Etat chiffre client (Brique 1) : le previsionnel arrive presque toujours
    # en TEXTE LIBRE dans le brief, pas dans des champs Tally dedies (audit
    # juillet 2026). On extrait les valeurs que le client a lui-meme ecrites
    # pour qu'elles deviennent des faits CLIENT verrouilles. Les champs
    # structures restent prioritaires ; rien n'est invente.
    enrich_variables_from_free_text(normalized)

    # Les champs financiers structures sont de la prose : le client y ecrit
    # une phrase, pas un nombre. On les relit avec l'extracteur plutot que de
    # verrouiller le texte brut comme fait CLIENT.
    raffiner_champs_financiers(normalized)

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
    # PAYS n'est JAMAIS ecrit par le code. Il l'etait — « France » par defaut —
    # et cette ligne etait executee AVANT le calcul des champs manquants : PAYS
    # ne pouvait donc structurellement jamais etre signale absent, alors que la
    # declaration de REQUIRED_VARIABLES promet des constantes du domaine
    # « jamais inventees a la volee ».
    #
    # Mesure sur une charge utile reelle : un client qui repond « Cotonou,
    # Benin » a la question de zone sans repondre a celle du pays produisait
    # PAYS = « France » et missing = []. Le dossier partait donc en generation,
    # et tout le pipeline suivait : marche mondial puis EUROPEEN dans le prompt
    # systeme, chapitre 1 retitre « marche mondial et europeen », devise EUR
    # verrouillee en fait CLIENT a tolerance zero pour un pays en XOF, et
    # requetes web « <secteur> France ». Le client recevait une etude
    # europeenne pour un projet beninois — ce que le manuel EM qualifie
    # lui-meme d'erreur, produit par le code.
    #
    # Sans valeur, le dossier passe en INCOMPLETE et le bootstrap refuse : c'est
    # le comportement voulu (regle 1 — echouer bruyamment plutot que deviner).
    #
    # ZONE garde un repli, mais un repli HONNETE : le pays declare par le
    # client, jamais une constante. C'est deja ce que fait l'autre voie de
    # saisie (`organisations/commandes.py`), et une seule regle vaut mieux que
    # deux (regle 5).
    if not normalized.get("ZONE") and normalized.get("PAYS"):
        normalized["ZONE"] = normalized["PAYS"]


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

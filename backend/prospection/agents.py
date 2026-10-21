"""Les trois agents de la prospection : recherche, qualification, rédaction.

Ils PRÉPARENT, ils n'envoient rien. Chacun ne produit que des données :
`rechercher_des_prospects` crée des `Prospect` (état NOUVEAU), `qualifier_un_prospect`
pose un score, `rediger_les_messages` crée des `Message` en BROUILLON. Aucun
n'appelle `services.envoyer_message` — l'unique chemin d'envoi reste le service,
derrière la validation humaine. Un test vérifie qu'après rédaction rien n'est
parti et qu'aucun message n'est passé validé tout seul.

Chaque agent reçoit son client par injection (`client=`, `recherche=`), avec pour
défaut les fabriques du projet. Hors ligne (EVKHA_USE_STUB_AI / _SEARCH vrais,
le défaut), ce sont les doublures déterministes : aucun appel réseau, aucun coût.
Un vrai passage (modèle réel) coûte de l'argent et suppose ces drapeaux à faux
AVEC les clés — décision d'exploitation, jamais un effet de bord d'une création.

Les agents ne lèvent pas sur une réponse de modèle malformée : ils bornent,
ignorent le superflu et rendent ce qu'ils ont pu construire (un contrôle
corrige, il ne bloque pas).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import transaction

from . import brief
from .models import (
    Campagne,
    Message,
    Prospect,
    Sequence,
    StatutMessage,
    StatutProspect,
)

if TYPE_CHECKING:
    from integrations.claude import StructuredClaudeClient
    from integrations.search import WebSearchClient

#: Le modèle employé par les agents. Alias EVKHA, résolu en identifiant réel par
#: `integrations.claude`. Sonnet : la prospection n'a pas la densité analytique
#: d'un livrable, et chaque passage est facturé — on ne monte pas en gamme sans
#: raison mesurée.
_MODELE_AGENTS = "claude-sonnet"

#: Par défaut, un premier message + quatre relances (l'utilisateur en veut « au
#: moins quatre ou cinq »). La séquence de la campagne, si elle existe, prime.
_RELANCES_PAR_DEFAUT = 4

#: Bornes de sûreté : on ne lance jamais une recherche ou une rédaction sans fin.
_MAX_PROSPECTS_PAR_RECHERCHE = 25
_MAX_MESSAGES_PAR_PROSPECT = 8


def _client_structure(client: StructuredClaudeClient | None) -> StructuredClaudeClient:
    """Le client injecté, ou celui de la fabrique — garanti capable de sortie structurée.

    La fabrique rend un `ClaudeClient` (le contrat texte) ; les clients concrets
    savent AUSSI produire du structuré, mais le type ne le dit pas. On le vérifie
    au lieu de le supposer : un client qui ne saurait pas serait une panne de
    configuration, pas un défaut à masquer par un `type: ignore`.
    """
    if client is not None:
        return client
    from integrations.claude import (  # noqa: PLC0415
        StructuredClaudeClient as _SCC,
    )
    from integrations.claude import get_claude_client  # noqa: PLC0415

    brut = get_claude_client()
    if not isinstance(brut, _SCC):
        msg = "Le client Claude configuré ne sait pas produire de sortie structurée."
        raise TypeError(msg)
    return brut


# ── Agent 1 : recherche de prospects ─────────────────────────────────────────


def _requete_de_recherche(campagne: Campagne) -> str:
    """La requête web à partir du secteur et de la zone de la campagne."""
    morceaux = [campagne.secteur.strip(), campagne.zone.strip()]
    base = " ".join(m for m in morceaux if m)
    return (base or campagne.nom).strip()


_SCHEMA_RECHERCHE: dict[str, object] = {
    "type": "object",
    "properties": {
        "prospects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "raison_sociale": {"type": "string"},
                    "secteur": {"type": "string"},
                    "zone": {"type": "string"},
                    "email": {"type": "string"},
                    "nom_contact": {"type": "string"},
                    "fonction": {"type": "string"},
                    "site_web": {"type": "string"},
                },
                "required": ["raison_sociale"],
            },
        }
    },
    "required": ["prospects"],
}


def rechercher_des_prospects(
    campagne: Campagne,
    *,
    limite: int = 10,
    criteres: str = "",
    recherche: WebSearchClient | None = None,
    client: StructuredClaudeClient | None = None,
) -> list[Prospect]:
    """Propose des prospects pour la campagne, à partir d'une recherche web.

    La recherche ramène des pages du secteur/zone ; le modèle en extrait des
    fiches structurées (raison sociale, e-mail éventuel, site…). On crée un
    `Prospect` NOUVEAU par fiche inédite — dédoublonné, dans la campagne, sur la
    raison sociale et sur l'e-mail. Rien n'est contacté : ce sont des fiches.

    `criteres` (facultatif) affine la cible — c'est ce que l'assistant produit
    à partir d'une discussion (« des PME de 10 à 50 salariés qui recrutent »).
    """
    limite = max(1, min(limite, _MAX_PROSPECTS_PAR_RECHERCHE))
    if recherche is None:
        from integrations.search import get_search_client  # noqa: PLC0415

        recherche = get_search_client()
    client = _client_structure(client)

    criteres = criteres.strip()
    requete = f"{_requete_de_recherche(campagne)} {criteres}".strip()
    reponse = recherche.search(query=requete, max_results=limite)
    extraits = "\n\n".join(
        f"- {r.title}\n  {r.url}\n  {r.content}" for r in reponse.results
    )
    system = (
        f"{brief.brief_recherche()}\n\n"
        "À partir d'extraits de recherche web, tu identifies des ORGANISATIONS "
        "CIBLES réelles correspondant aux cibles ci-dessus et tu rends leurs "
        "coordonnées professionnelles quand elles figurent dans les extraits. "
        "N'invente jamais d'e-mail ni de contact : laisse le champ vide si "
        "l'information n'est pas présente. Jamais de particuliers, jamais de "
        "profil exclu — uniquement des organisations pertinentes."
    )
    prompt = (
        f"Campagne : {campagne.nom}.\n"
        f"Secteur visé : {campagne.secteur or '—'}.\n"
        f"Zone : {campagne.zone or '—'}.\n"
        f"Offre proposée : {campagne.offre_visee or '—'}.\n"
        f"Critères affinés : {criteres or '—'}.\n\n"
        f"Extraits de recherche web :\n{extraits or '(aucun résultat)'}\n\n"
        f"Propose jusqu'à {limite} entreprises cibles pertinentes."
    )
    resultat = client.complete_structured(
        system=system,
        prompt=prompt,
        outil_nom="extraire_prospects",
        outil_description="Rend la liste des entreprises cibles repérées.",
        schema=_SCHEMA_RECHERCHE,
        model=_MODELE_AGENTS,
    )
    fiches = resultat.payload.get("prospects")
    if not isinstance(fiches, list):
        return []
    return _creer_les_prospects(campagne, fiches, limite)


def _texte(fiche: dict[str, Any], cle: str, longueur: int) -> str:
    valeur = fiche.get(cle, "")
    return str(valeur).strip()[:longueur] if isinstance(valeur, (str, int, float)) else ""


def _creer_les_prospects(
    campagne: Campagne, fiches: list[Any], limite: int
) -> list[Prospect]:
    """Matérialise les fiches en `Prospect`, en dédoublonnant dans la campagne."""
    deja_raisons = {
        (r or "").strip().casefold()
        for r in Prospect.objects.filter(campagne=campagne).values_list(
            "raison_sociale", flat=True
        )
    }
    deja_emails = {
        (e or "").strip().casefold()
        for e in Prospect.objects.filter(campagne=campagne)
        .exclude(email="")
        .values_list("email", flat=True)
    }
    crees: list[Prospect] = []
    for fiche in fiches:
        if len(crees) >= limite or not isinstance(fiche, dict):
            continue
        raison = _texte(fiche, "raison_sociale", 200)
        if not raison or raison.casefold() in deja_raisons:
            continue
        email = _texte(fiche, "email", 254).casefold()
        if email and email in deja_emails:
            continue
        prospect = Prospect.objects.create(
            campagne=campagne,
            raison_sociale=raison,
            secteur=_texte(fiche, "secteur", 200) or campagne.secteur,
            zone=_texte(fiche, "zone", 200) or campagne.zone,
            email=email,
            nom_contact=_texte(fiche, "nom_contact", 200),
            fonction=_texte(fiche, "fonction", 200),
            site_web=_texte(fiche, "site_web", 200),
            source="recherche-ia",
            statut=StatutProspect.NOUVEAU,
        )
        crees.append(prospect)
        deja_raisons.add(raison.casefold())
        if email:
            deja_emails.add(email)
    return crees


# ── Agent 2 : qualification (score d'abonnement) ─────────────────────────────


_SCHEMA_QUALIFICATION: dict[str, object] = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "raison": {"type": "string"},
    },
    "required": ["score", "raison"],
}


def qualifier_un_prospect(
    prospect: Prospect, *, client: StructuredClaudeClient | None = None
) -> Prospect:
    """Juge la probabilité d'abonnement : pose `score_adequation` et sa raison.

    Le score va de 0 à 100 (borné). Un prospect NOUVEAU passe QUALIFIÉ ; on ne
    rétrograde jamais un prospect déjà contacté — requalifier met à jour le
    score, pas l'avancement.
    """
    client = _client_structure(client)

    campagne = prospect.campagne
    system = (
        f"{brief.brief_qualification()}\n\n"
        "Juge, de 0 à 100, la probabilité que ce prospect souscrive un "
        "abonnement EVKHA, en t'appuyant sur les cibles, les signes d'intérêt et "
        "les exclusions ci-dessus. Explique brièvement ta note (quelle cible, "
        "quels signes, quelle priorité). Sois lucide : une note basse, ou 0 pour "
        "un profil exclu, est une information utile."
    )
    prompt = (
        f"Entreprise : {prospect.raison_sociale}.\n"
        f"Secteur : {prospect.secteur or '—'}.\n"
        f"Zone : {prospect.zone or '—'}.\n"
        f"Fonction du contact : {prospect.fonction or '—'}.\n"
        f"Site : {prospect.site_web or '—'}.\n"
        f"Offre visée par la campagne : "
        f"{(campagne.offre_visee if campagne else '') or '—'}.\n\n"
        "Donne un score d'adéquation et sa raison."
    )
    resultat = client.complete_structured(
        system=system,
        prompt=prompt,
        outil_nom="qualifier_prospect",
        outil_description="Rend le score d'adéquation (0-100) et sa raison.",
        schema=_SCHEMA_QUALIFICATION,
        model=_MODELE_AGENTS,
    )
    score = _borner_score(resultat.payload.get("score"))
    raison = resultat.payload.get("raison")
    champs = ["updated_at"]
    if score is not None:
        prospect.score_adequation = score
        champs.append("score_adequation")
    if isinstance(raison, str) and raison.strip():
        prospect.raison_score = raison.strip()
        champs.append("raison_score")
    if prospect.statut == StatutProspect.NOUVEAU:
        prospect.statut = StatutProspect.QUALIFIE
        champs.append("statut")
    prospect.save(update_fields=champs)
    return prospect


def _borner_score(valeur: object) -> int | None:
    """Ramène une note de modèle dans [0, 100], ou None si ce n'est pas un nombre."""
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    return max(0, min(100, int(valeur)))


# ── Agent 3 : rédaction du premier message et des relances ───────────────────


_SCHEMA_REDACTION: dict[str, object] = {
    "type": "object",
    "properties": {
        "messages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "objet": {"type": "string"},
                    "corps": {"type": "string"},
                },
                "required": ["objet", "corps"],
            },
        }
    },
    "required": ["messages"],
}


def rediger_les_messages(
    prospect: Prospect,
    *,
    nb_relances: int = _RELANCES_PAR_DEFAUT,
    remplacer: bool = False,
    client: StructuredClaudeClient | None = None,
) -> list[Message]:
    """Rédige le premier e-mail et ses relances, EN BROUILLON, pour relecture.

    Si la campagne porte une séquence, elle en fixe le nombre d'étapes et sert
    de trame ; sinon on vise un premier message + `nb_relances` relances. Chaque
    message naît BROUILLON : il ne part qu'une fois validé par un humain. On ne
    réécrit pas par-dessus une file existante sauf `remplacer=True`.
    """
    client = _client_structure(client)

    etapes = list(prospect.campagne.sequence.all()) if prospect.campagne else []
    if etapes:
        nb_messages = len(etapes)
    else:
        nb_messages = 1 + max(0, min(nb_relances, _MAX_MESSAGES_PAR_PROSPECT - 1))
    nb_messages = max(1, min(nb_messages, _MAX_MESSAGES_PAR_PROSPECT))

    en_file = prospect.messages.exclude(
        statut__in=(StatutMessage.ENVOYE, StatutMessage.ANNULE)
    )
    if en_file.exists():
        if not remplacer:
            return list(en_file)
        # On remet à zéro la file (hors messages partis) avant de réécrire.
        from . import services  # noqa: PLC0415

        for message in en_file:
            services.annuler_message(message)

    gabarits = _plan_de_sequence(etapes, nb_messages)
    resultat = client.complete_structured(
        system=_system_de_redaction(prospect),
        prompt=_prompt_de_redaction(prospect, gabarits),
        outil_nom="rediger_messages",
        outil_description=(
            "Rend la liste ordonnée des e-mails : le premier, puis les relances."
        ),
        schema=_SCHEMA_REDACTION,
        model=_MODELE_AGENTS,
    )
    redige = resultat.payload.get("messages")
    if not isinstance(redige, list):
        return []
    return _creer_les_messages(prospect, etapes, redige, nb_messages)


def _plan_de_sequence(etapes: list[Sequence], nb_messages: int) -> list[str]:
    """Une ligne de consigne par message à rédiger (trame de la campagne si elle existe)."""
    if etapes:
        lignes = []
        for etape in etapes:
            role = "Premier message" if etape.ordre == 0 else f"Relance {etape.ordre}"
            trame = etape.objet_gabarit or etape.corps_gabarit
            lignes.append(f"{role}" + (f" — trame : {trame}" if trame else ""))
        return lignes
    return ["Premier message"] + [f"Relance {i}" for i in range(1, nb_messages)]


def _system_de_redaction(prospect: Prospect) -> str:
    return (
        f"{brief.brief_redaction()}\n\n"
        "Tu rédiges, au nom d'Evangeline, une séquence d'e-mails de prospection "
        "B2B en français. Chaque e-mail : un objet court et accrocheur, et un "
        "corps en HTML simple (<p>, <strong>) adapté à la CIBLE du prospect et "
        "portant l'argument correspondant. Le premier message situe d'où vient "
        "le contact et propose une démo de 10 minutes ; les relances sont plus "
        "brèves et n'insistent jamais lourdement. Termine chaque corps par la "
        "signature d'Evangeline. N'invente aucun chiffre, n'annonce aucun prix, "
        "et n'écris PAS de lien ni de formule de désinscription (ils sont "
        "ajoutés automatiquement)."
    )


def _prompt_de_redaction(prospect: Prospect, gabarits: list[str]) -> str:
    plan = "\n".join(f"{i + 1}. {g}" for i, g in enumerate(gabarits))
    contact = prospect.nom_contact or "l'équipe"
    score = prospect.score_adequation if prospect.score_adequation is not None else "—"
    return (
        f"Destinataire : {contact}, {prospect.raison_sociale}"
        f" ({prospect.secteur or 'secteur non précisé'}).\n"
        f"Score d'adéquation estimé : {score}.\n\n"
        f"Rédige exactement {len(gabarits)} e-mails, dans cet ordre :\n{plan}"
    )


def _creer_les_messages(
    prospect: Prospect,
    etapes: list[Sequence],
    redige: list[Any],
    nb_messages: int,
) -> list[Message]:
    """Crée les `Message` BROUILLON à partir des e-mails rendus par le modèle."""
    crees: list[Message] = []
    with transaction.atomic():
        for i, brut in enumerate(redige):
            if i >= nb_messages or not isinstance(brut, dict):
                continue
            objet = _texte(brut, "objet", 300)
            corps = str(brut.get("corps", "")).strip()
            if not objet or not corps:
                continue
            message = Message.objects.create(
                prospect=prospect,
                campagne=prospect.campagne,
                sequence=etapes[i] if i < len(etapes) else None,
                objet=objet,
                corps=corps,
                statut=StatutMessage.BROUILLON,
            )
            crees.append(message)
    return crees

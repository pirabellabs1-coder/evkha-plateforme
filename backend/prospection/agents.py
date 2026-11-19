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

## Une réponse sans appel d'outil n'est pas « rien trouvé » (audit du 19/11/2026)

Ce module disait : « les agents ne lèvent pas sur une réponse de modèle
malformée ». C'était le défaut. Le choix d'outil n'est plus forcé (voir
`integrations.claude.complete_structured`) : un modèle qui répond en texte, ou
dont la sortie est coupée, rend une charge VIDE. Traitée comme un succès, elle
donnait « 0 prospect » sans un mot, un prospect QUALIFIÉ sans note, et une file
de brouillons annulée puis remplacée par rien.

Les agents distinguent donc deux choses :

- `{}`, ou une charge sans la clé attendue : le modèle n'a rien rendu —
  `ReponseInexploitableError`, nommée, et RIEN n'est modifié ;
- `{"prospects": []}` : le modèle a cherché et n'a rien trouvé — un zéro
  légitime (souvent VOULU : `brief.py` écarte les cibles hors brief), rendu
  avec son compte pour que l'écran le dise.

Le superflu, lui, reste ignoré : un champ en trop, une fiche sans raison
sociale, un score hors bornes se corrigent sans bloquer.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from django.conf import settings
from django.db import transaction

from . import brief, services
from .models import (
    Campagne,
    Message,
    Prospect,
    Sequence,
    StatutMessage,
    StatutProspect,
    normaliser_adresse,
)

if TYPE_CHECKING:
    from integrations.claude import StructuredClaudeClient, StructuredResult
    from integrations.search import WebSearchClient

#: Le modèle employé par les agents (recherche, qualification, rédaction).
#: Alias EVKHA, résolu en identifiant réel par `integrations.claude`. OPUS :
#: c'est le travail livré (juger un prospect, écrire un e-mail qui convainc) ;
#: la cliente vise ~1 €/jour pour que ce travail soit de qualité, Opus le porte.
#: ATTENTION : seuls « claude-sonnet » et « claude-opus » sont mappés ; tout
#: autre identifiant retomberait en silence sur Sonnet (voir claude.py).
_MODELE_AGENTS = "claude-opus"

#: Par défaut, un premier message + quatre relances (l'utilisateur en veut « au
#: moins quatre ou cinq »). La séquence de la campagne, si elle existe, prime.
_RELANCES_PAR_DEFAUT = 4

#: Bornes de sûreté : on ne lance jamais une recherche ou une rédaction sans fin.
#:
#: `_MAX_PROSPECTS_PAR_RECHERCHE` est LA source du plafond (règle 5). Jusqu'à
#: l'audit du 19/11/2026, l'écran et la tâche quotidienne annonçaient « max
#: 50 » pendant que la recherche en créait au plus 25 : la tâche, le réglage,
#: l'écran et l'assistant lisent désormais cette constante.
_MAX_PROSPECTS_PAR_RECHERCHE = 25
_MAX_MESSAGES_PAR_PROSPECT = 8


class ReponseInexploitableError(RuntimeError):
    """Le modèle a répondu sans rien rendre d'exploitable. Rien n'a été modifié.

    Le message est écrit pour l'humain : `dashboard.prospection._executer_agent`
    le rend tel quel dans son 502.
    """


class RedactionRefuseeError(RuntimeError):
    """On ne rédige pas pour ce prospect : ses messages ne pourraient pas partir.

    Une rédaction est un appel payant. La lancer pour une fiche sans adresse,
    désinscrite ou qui a répondu, c'est payer des brouillons que
    `services.envoyer_message` refusera.
    """


def _valeur_exigee(resultat: StructuredResult, cle: str, action: str) -> object:
    """La valeur de `cle` dans la charge rendue par l'outil — ou une erreur NOMMÉE.

    Une charge vide ou sans la clé attendue n'est pas une réponse : c'est une
    absence de réponse (texte libre, sortie coupée). La prendre pour « rien
    trouvé » est un contrôle qui n'a rien à comparer et qui se déclare
    satisfait (règle 1).
    """
    charge = resultat.payload
    coupee = getattr(resultat, "stop_reason", "") == "max_tokens"
    # La coupure se juge AVANT la présence de la clé. Une réponse coupée porte
    # souvent la clé et une liste dont le dernier élément s'arrête au milieu
    # d'une phrase (`integrations.claude.motif_de_troncature`) : l'accepter
    # créait un brouillon tronqué, et avec « remplacer » annulait la file
    # saine pour lui (relecture du 19/11/2026).
    if cle in charge and not coupee:
        return charge[cle]
    if coupee:
        cause = "sa réponse a été coupée avant la fin (limite de sortie atteinte)"
    elif not charge:
        cause = "elle a répondu en texte, sans rendre le résultat attendu"
    else:
        cause = f"sa réponse ne contient pas « {cle} »"
    msg = (
        f"L'IA n'a rien rendu d'exploitable pour « {action} » : {cause}. "
        "Rien n'a été modifié — relancez l'action."
    )
    raise ReponseInexploitableError(msg)


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

# ── Enrichissement : trouver l'e-mail professionnel d'une organisation ────────
#
# Une prospection sans e-mail ne sert à rien. Les extraits de recherche portent
# rarement l'adresse ; on va donc la CHERCHER pour chaque fiche qui n'en a pas :
# d'abord sur le site de l'organisation (pages publiques, mentions légales —
# obligatoires en France), gratuitement ; puis, en secours, par une recherche
# ciblée. On ne devine JAMAIS une adresse : à défaut, le champ reste vide (le
# prospect est créé quand même, mais l'envoi exigera un e-mail — invariant du
# service). 100 % n'est pas atteignable : certaines structures n'exposent qu'un
# formulaire.
#
# Et on ne prend pas non plus « une adresse vue quelque part » (audit du
# 19/11/2026) : le site d'un cabinet porte aussi l'adresse de son agence web et
# de son hébergeur, et une page de résultats celle de l'annuaire qui le cite.
# Écrire à celle-là, c'est prospecter un tiers au nom d'un autre. Une adresse
# n'est retenue que si elle est AU DOMAINE du site de l'organisation, ou si le
# modèle la désigne parmi celles qui FIGURENT dans les extraits.

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

#: Faux positifs courants dans le HTML (traqueurs, exemples, ressources).
_EMAIL_REJETE = (
    "sentry", "wixpress", "example.", "@example", "domain.com", "email.com",
    "votredomaine", "yourdomain", "@2x", ".png", ".jpg", ".jpeg", ".gif",
    ".webp", ".svg", "u002", "schema.org",
)

#: Pages où un cabinet publie son adresse. "" = la page d'accueil.
_PAGES_CONTACT = (
    "", "contact", "nous-contacter", "mentions-legales", "mentions-legales.html",
    "mentions-legales-et-cgu", "mentions", "cgv", "qui-sommes-nous",
)

_HTTP_TIMEOUT = 10.0
_MAX_PAGES = 5  # borne de sûreté : on ne parcourt pas tout un site.

_SCHEMA_EMAIL: dict[str, object] = {
    "type": "object",
    "properties": {"email": {"type": "string"}},
    "required": [],
}


def _email_plausible(brut: object) -> str:
    """L'adresse que porte cette chaîne, normalisée — ou "" si elle n'en porte pas.

    LE filtre de ce qui peut s'enregistrer comme adresse (règle 5) : le champ
    rendu par le modèle, les adresses lues sur un site et dans des extraits y
    passent tous. Jusqu'à l'audit du 19/11/2026 il suffisait d'un « @ », et le
    champ du modèle n'y passait même pas : « non communiqué » s'enregistrait
    comme adresse, la fiche n'était plus enrichie, et l'envoi partait vers
    rien. Il faut désormais la FORME d'une adresse (`_EMAIL`).
    """
    trouvee = _EMAIL.search(str(brut or ""))
    if trouvee is None:
        return ""
    a = normaliser_adresse(trouvee.group(0)).strip(".")
    if len(a) > 254 or any(mauvais in a for mauvais in _EMAIL_REJETE):
        return ""
    return a


def _hote_nu(netloc: str) -> str:
    """« user@WWW.Cabinet-Lille.fr:443 » -> « cabinet-lille.fr ».

    L'hôte ENTIER, sans le « www. » de tête. On ne le réduit pas à ses deux
    derniers labels : « bge.asso.fr » deviendrait « asso.fr », et toute adresse
    d'une autre association passerait pour celle du site (un domaine se lit
    entier ou pas du tout).
    """
    hote = netloc.rsplit("@", 1)[-1].split(":")[0].strip().strip(".").lower()
    return hote.removeprefix("www.")


def _hote_du_site(site_web: object) -> str:
    """L'hôte nu d'une adresse de site, ou "" si elle est vide ou illisible."""
    brut = str(site_web or "").strip()
    if not brut:
        return ""
    if "://" not in brut:
        brut = "https://" + brut
    try:
        return _hote_nu(urlparse(brut).netloc)
    except ValueError:
        return ""


def _est_au_domaine(adresse: str, hote: str) -> bool:
    """L'adresse est-elle au domaine de ce site — le même, ou l'un de ses sous-domaines ?

    Égalité ou sous-domaine, jamais une simple inclusion : « lille.fr » est
    contenu dans « agence-lille.fr », qui est une autre organisation. Le
    domaine PARENT n'est pas accepté non plus : pour « cabinet.wixsite.com »,
    le parent est l'hébergeur.
    """
    domaine = adresse.rsplit("@", 1)[-1]
    if not hote or not domaine:
        return False
    return domaine == hote or domaine.endswith("." + hote)


def _email_par_site(site_web: str) -> str:
    """Cherche une adresse sur le site de l'organisation. GET seulement, aucun
    modèle, aucun coût. Ne rend qu'une adresse AU DOMAINE du site — sinon "".

    Audit du 19/11/2026 : faute d'adresse au domaine, la fonction retombait sur
    la première adresse vue sur le site, quelle qu'elle soit — celle de
    l'agence web en pied de page, de l'hébergeur dans les mentions légales.
    """
    base = (site_web or "").strip()
    if not base:
        return ""
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    racine = base.rstrip("/")
    try:
        import httpx  # noqa: PLC0415 — dépendance optionnelle, jamais en CI
    except ImportError:
        return ""
    entetes = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    hote = _hote_du_site(racine)
    for suffixe in _PAGES_CONTACT[:_MAX_PAGES]:
        url = f"{racine}/{suffixe}" if suffixe else racine
        try:
            reponse = httpx.get(
                url, headers=entetes, timeout=_HTTP_TIMEOUT, follow_redirects=True
            )
        except Exception:  # noqa: BLE001 — un site injoignable n'arrête pas la collecte
            continue
        # Le site peut rediriger vers son vrai domaine (« cabinet.fr » ->
        # « cabinet-dupont.fr ») : l'hôte d'arrivée vaut autant que celui donné.
        hotes = {hote, _hote_nu(str(getattr(reponse.url, "host", "") or ""))} - {""}
        for brut in _EMAIL.findall(reponse.text):
            adresse = _email_plausible(brut)
            if adresse and any(_est_au_domaine(adresse, h) for h in hotes):
                return adresse
    return ""


def _email_par_recherche(
    nom: str,
    ville: str,
    recherche: WebSearchClient,
    client: StructuredClaudeClient,
    *,
    site: str = "",
) -> str:
    """Secours : une recherche ciblée, puis l'adresse lue dans les extraits.

    Trois issues, de la plus sûre à la plus coûteuse :

    - une adresse AU DOMAINE du site de l'organisation figure dans les extraits :
      on la prend, sans appeler le modèle ;
    - des adresses y figurent, aucune au domaine : le modèle désigne celle de
      l'organisation, et on VÉRIFIE qu'elle est l'une de celles qui figurent —
      « tu n'en inventes jamais » est une consigne, pas un contrôle ;
    - aucune adresse n'y figure : rien à désigner, le modèle n'est pas appelé
      (il était payé pour chercher une adresse dans un texte qui n'en a pas).
    """
    try:
        reponse = recherche.search(
            query=f"{nom} {ville} email contact".strip(), max_results=5
        )
    except Exception:  # noqa: BLE001 — une recherche ratée ne crée pas de blocage
        return ""
    extraits = "\n".join(
        f"{r.title} {r.url} {r.content}" for r in reponse.results
    )
    figurent: list[str] = []
    for brut in _EMAIL.findall(extraits):
        adresse = _email_plausible(brut)
        if adresse and adresse not in figurent:
            figurent.append(adresse)
    if not figurent:
        return ""
    hote = _hote_du_site(site)
    for adresse in figurent:
        if _est_au_domaine(adresse, hote):
            return adresse
    resultat = client.complete_structured(
        system=(
            "Tu extrais UNIQUEMENT une adresse e-mail professionnelle qui FIGURE "
            "dans les extraits et qui est celle de l'organisation nommée — pas "
            "celle d'un annuaire, d'une agence web ou d'un hébergeur. Tu n'en "
            "inventes jamais. Si aucune ne convient, tu rends une chaîne vide."
        ),
        prompt=(
            f"Organisation : {nom} ({ville or '—'}).\n"
            f"Site : {site or '—'}.\n"
            f"Extraits de recherche web :\n{extraits}\n\n"
            "Rends l'adresse e-mail de contact professionnel de cette "
            "organisation si elle figure, sinon une chaîne vide."
        ),
        outil_nom="extraire_email",
        outil_description="Rend l'e-mail professionnel trouvé, ou vide.",
        schema=_SCHEMA_EMAIL,
        model=_MODELE_AGENTS,
    )
    # Une charge vide vaut ici « pas d'adresse » : l'enrichissement est un
    # secours, son absence laisse le champ vide — elle ne crée rien de faux.
    rendue = _email_plausible(resultat.payload.get("email", ""))
    return rendue if rendue in figurent else ""


def _trouver_email_pro(
    fiche: dict[str, Any], recherche: WebSearchClient, client: StructuredClaudeClient
) -> str:
    """L'e-mail pro d'une organisation : le site d'abord (gratuit), la recherche
    en secours. Jamais deviné — "" si rien n'est trouvé."""
    nom = str(fiche.get("raison_sociale") or "").strip()
    site = str(fiche.get("site_web") or "").strip()
    ville = str(fiche.get("zone") or "").strip()
    # Le fetch réel est sauté sur doublure (CI/dev) : aucun réseau involontaire.
    if site and not bool(getattr(settings, "EVKHA_USE_STUB_SEARCH", True)):
        adresse = _email_par_site(site)
        if adresse:
            return adresse
    if nom:
        return _email_par_recherche(nom, ville, recherche, client, site=site)
    return ""


@dataclass(frozen=True)
class BilanRecherche:
    """Ce qu'une recherche a rendu — pour que l'écran DISE le zéro au lieu de le taire.

    « 0 prospect créé » a trois causes qui n'appellent pas la même suite :
    le modèle n'a proposé aucune organisation (cible hors brief : c'est voulu),
    il en a proposé mais elles sont toutes déjà dans la campagne, ou il n'a
    rien rendu du tout (ce cas-là lève `ReponseInexploitableError`).
    """

    crees: list[Prospect]
    #: Organisations proposées par le modèle, avant tout dédoublonnage.
    proposees: int
    #: Écartées parce que déjà connues de la campagne (nom, site ou adresse).
    deja_connues: int

    @property
    def sans_adresse(self) -> int:
        """Fiches créées sans adresse : à compléter à la main avant toute rédaction."""
        return sum(1 for p in self.crees if not p.email)


def rechercher_avec_bilan(
    campagne: Campagne,
    *,
    limite: int = 10,
    criteres: str = "",
    recherche: WebSearchClient | None = None,
    client: StructuredClaudeClient | None = None,
) -> BilanRecherche:
    """Propose des prospects pour la campagne, à partir d'une recherche web.

    La recherche ramène des pages du secteur/zone ; le modèle en extrait des
    fiches structurées (raison sociale, e-mail éventuel, site…). On crée un
    `Prospect` NOUVEAU par fiche inédite — dédoublonné, dans la campagne, sur la
    raison sociale normalisée, le site et l'e-mail. Rien n'est contacté : ce
    sont des fiches.

    `criteres` (facultatif) affine la cible — c'est ce que l'assistant produit
    à partir d'une discussion (« des PME de 10 à 50 salariés qui recrutent »).

    Lève `ReponseInexploitableError` si le modèle n'a pas rendu de liste : un
    zéro n'est rendu que s'il est RÉEL (`{"prospects": []}`).
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
    action = "recherche de prospects"
    fiches = _valeur_exigee(resultat, "prospects", action)
    if not isinstance(fiches, list):
        msg = (
            f"L'IA n'a rien rendu d'exploitable pour « {action} » : « prospects » "
            "n'est pas une liste. Rien n'a été modifié — relancez l'action."
        )
        raise ReponseInexploitableError(msg)
    proposees = [
        f for f in fiches if isinstance(f, dict) and _texte(f, "raison_sociale", 200)
    ]
    # On dédoublonne AVANT d'enrichir (audit du 19/11/2026) : la recherche
    # d'adresse — un site parcouru, une recherche web, parfois le modèle — était
    # payée pour CHAQUE fiche rendue, y compris celles qu'on écartait ensuite
    # comme doublons ou au-delà de la limite.
    retenues, doublons = _fiches_inedites(campagne, proposees, limite)
    # Une fiche sans e-mail ne sert à rien : on CHERCHE l'adresse pro de chaque
    # organisation retenue (site, puis recherche en secours). Tout l'enrichis-
    # sement précède la première écriture : une panne ici ne crée rien.
    for fiche in retenues:
        fiche["email"] = _email_plausible(fiche.get("email")) or _trouver_email_pro(
            fiche, recherche, client
        )
    crees, doublons_d_adresse = _materialiser(campagne, retenues)
    return BilanRecherche(
        crees=crees,
        proposees=len(proposees),
        deja_connues=doublons + doublons_d_adresse,
    )


def rechercher_des_prospects(
    campagne: Campagne,
    *,
    limite: int = 10,
    criteres: str = "",
    recherche: WebSearchClient | None = None,
    client: StructuredClaudeClient | None = None,
) -> list[Prospect]:
    """Les prospects CRÉÉS par une recherche — voir `rechercher_avec_bilan`."""
    return rechercher_avec_bilan(
        campagne, limite=limite, criteres=criteres, recherche=recherche, client=client
    ).crees


def _texte(fiche: dict[str, Any], cle: str, longueur: int) -> str:
    valeur = fiche.get(cle, "")
    return str(valeur).strip()[:longueur] if isinstance(valeur, (str, int, float)) else ""


def _nom_normalise(raison: str) -> str:
    """La clé de comparaison d'une raison sociale : ni casse, ni accents, ni ponctuation.

    « BGE Hauts-de-France », « BGE Hauts de France » et « bge hauts‑de‑france »
    sont la même organisation. On ne garde que les lettres et les chiffres :
    énumérer les séparateurs (tiret, tiret insécable, apostrophe, point…)
    serait une liste fermée de plus (règle 4).
    """
    decompose = unicodedata.normalize("NFKD", raison)
    cle = "".join(
        c for c in decompose.casefold() if c.isalnum() and not unicodedata.combining(c)
    )
    # Un nom sans lettre ni chiffre garde sa forme brute plutôt qu'une clé vide,
    # qui confondrait entre eux tous les noms de ce genre.
    return cle or raison.strip().casefold()


def _cle_du_site(site_web: object) -> str:
    """La clé de comparaison d'un site : son hôte, plus son chemin s'il en a un.

    « https://www.bge.fr/ » et « bge.fr » sont le même site. Mais une PAGE dans
    un site n'identifie l'organisation que par son chemin : les antennes d'un
    réseau (« initiative-france.fr/reseau/lille », « …/reseau/lens ») et les
    pages d'une plateforme (« linkedin.com/company/x ») partagent un hôte sans
    être la même organisation — les fondre écarterait de vraies cibles.
    """
    brut = str(site_web or "").strip()
    hote = _hote_du_site(brut)
    if not hote:
        return ""
    if "://" not in brut:
        brut = "https://" + brut
    chemin = urlparse(brut).path.strip("/").casefold()
    return f"{hote}/{chemin}" if chemin else hote


def _fiches_inedites(
    campagne: Campagne, fiches: list[Any], limite: int
) -> tuple[list[dict[str, Any]], int]:
    """Les fiches que la campagne ne connaît pas encore, bornées à `limite`.

    Rend (retenues, doublons écartés). Juge sur le NOM normalisé et sur le
    SITE — ce qu'on sait avant tout enrichissement. L'adresse, elle, n'est
    connue qu'après : `_materialiser` la juge.
    """
    connus = Prospect.objects.filter(campagne=campagne).values_list(
        "raison_sociale", "site_web"
    )
    noms = {_nom_normalise(raison or "") for raison, _ in connus}
    sites = {_cle_du_site(site) for _, site in connus} - {""}
    retenues: list[dict[str, Any]] = []
    doublons = 0
    for fiche in fiches:
        if len(retenues) >= limite:
            break
        if not isinstance(fiche, dict):
            continue
        raison = _texte(fiche, "raison_sociale", 200)
        if not raison:
            continue
        nom = _nom_normalise(raison)
        site = _cle_du_site(_texte(fiche, "site_web", 200))
        if nom in noms or (site and site in sites):
            doublons += 1
            continue
        retenues.append(fiche)
        noms.add(nom)
        if site:
            sites.add(site)
    return retenues, doublons


def _materialiser(
    campagne: Campagne, fiches: list[dict[str, Any]]
) -> tuple[list[Prospect], int]:
    """Crée un `Prospect` par fiche retenue. Rend (créés, doublons d'adresse écartés).

    L'adresse n'est enregistrée que si elle a la FORME d'une adresse
    (`_email_plausible`), et une fiche dont l'adresse est déjà opposée naît
    désinscrite (`services.heriter_de_l_opposition`).
    """
    adresses = {
        normaliser_adresse(e)
        for e in Prospect.objects.filter(campagne=campagne)
        .exclude(email="")
        .values_list("email", flat=True)
    } - {""}
    crees: list[Prospect] = []
    doublons = 0
    for fiche in fiches:
        raison = _texte(fiche, "raison_sociale", 200)
        if not raison:
            continue
        email = _email_plausible(fiche.get("email"))
        if email and email in adresses:
            doublons += 1
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
        services.heriter_de_l_opposition(prospect)
        crees.append(prospect)
        if email:
            adresses.add(email)
    return crees, doublons


def _creer_les_prospects(
    campagne: Campagne, fiches: list[Any], limite: int
) -> list[Prospect]:
    """Matérialise les fiches en `Prospect`, en dédoublonnant dans la campagne."""
    retenues, _ = _fiches_inedites(campagne, fiches, limite)
    return _materialiser(campagne, retenues)[0]


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

    Un prospect n'est QUALIFIÉ que s'il a REÇU UNE NOTE (audit du 19/11/2026) :
    une réponse sans appel d'outil le faisait passer « qualifié » sans score,
    et l'écran montrait une fiche jugée que personne n'avait jugée. Sans note,
    `ReponseInexploitableError` — et la fiche n'est pas touchée.
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
    action = "qualification"
    score = _borner_score(_valeur_exigee(resultat, "score", action))
    if score is None:
        msg = (
            f"L'IA n'a rien rendu d'exploitable pour « {action} » : la note rendue "
            "n'est pas un nombre. Rien n'a été modifié — relancez l'action."
        )
        raise ReponseInexploitableError(msg)
    raison = resultat.payload.get("raison")
    prospect.score_adequation = score
    champs = ["score_adequation", "updated_at"]
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

    Deux refus, tous deux AVANT l'appel payant (audit du 19/11/2026) :

    - `RedactionRefuseeError` si on ne peut pas écrire à ce prospect (pas
      d'adresse, désinscrit, a répondu…) : la tâche quotidienne payait une
      séquence entière pour des fiches sans adresse, dont l'envoi est refusé ;
    - `ReponseInexploitableError` si le modèle ne rend aucun message — et dans
      ce cas la file existante est INTACTE : avec `remplacer=True`, elle était
      annulée avant l'appel, donc perdue dès que le modèle répondait à côté.
    """
    motif = services.motif_de_non_contact(prospect)
    if motif is not None:
        msg = f"Rédaction inutile : {motif}."
        raise RedactionRefuseeError(msg)
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
    if en_file.exists() and not remplacer:
        return list(en_file)

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
    action = "rédaction des messages"
    redige = _valeur_exigee(resultat, "messages", action)
    inexploitable = (
        f"L'IA n'a rien rendu d'exploitable pour « {action} » : aucun e-mail "
        "complet (objet et corps) dans sa réponse. Rien n'a été modifié — "
        "relancez l'action."
    )
    if not isinstance(redige, list):
        raise ReponseInexploitableError(inexploitable)
    # L'ancienne file n'est annulée qu'UNE FOIS la nouvelle obtenue, et dans la
    # même transaction : si rien d'exploitable n'est créé, l'annulation est
    # défaite avec le reste. Le queryset est relu ICI, pas avant l'appel au
    # modèle — un message parti pendant la rédaction ne doit pas être annulé.
    with transaction.atomic():
        for message in en_file:
            services.annuler_message(message)
        crees = _creer_les_messages(prospect, etapes, redige, nb_messages)
        if not crees:
            raise ReponseInexploitableError(inexploitable)
    return crees


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
                etape=etapes[i].ordre if i < len(etapes) else i,
                objet=objet,
                corps=corps,
                statut=StatutMessage.BROUILLON,
            )
            crees.append(message)
    return crees

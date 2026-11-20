"""Gestion des formations depuis l'espace d'administration.

Les modules des formations vivaient dans un outil externe et leurs prix dans
le code des pages : la cliente ne pouvait rien changer sans développeur. Ces
vues sont le chemin par lequel elle crée une formation, y range des modules,
et des leçons dans chaque module.

Trois partis pris, tenus par `tests/test_formations.py` :

- **les règles ne sont pas ici.** Elles vivent dans `catalog/formations.py`,
  que ces vues appellent avant chaque écriture ;
- **rien ne se supprime.** Aucune vue n'accepte `DELETE`, aucune n'appelle
  `.delete()` : un module ou une leçon se retire (`{"retire": true}`) et se
  rétablit, une formation se met hors ligne, et l'accès qu'un achat donne se
  retire (`{"revoque": true}`) sans que l'achat disparaisse ;
- **un champ illisible ne remet rien à zéro.** Il laisse la valeur précédente,
  et la réponse le nomme dans `refuses` — même contrat que
  `dashboard.boutique._appliquer`, à ceci près que la boutique ne le disait
  que dans les journaux.

Toutes les réponses qui écrivent rendent la formation ENTIÈRE, programme
compris : l'écran n'a qu'une forme à connaître, et il ne recompose jamais un
état à partir de morceaux.

L'authentification n'est pas ici non plus : tout ce qui est sous
`/api/dashboard/` passe par `dashboard.middleware.DashboardAuthMiddleware`.
"""
from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from functools import wraps
from typing import Any

from django.core.files.uploadedfile import UploadedFile
from django.db import IntegrityError, models, transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from paiement.achats import reference_abregee

from catalog import formations as regles
from catalog.models import (
    AchatFormation,
    Formation,
    LeconDeFormation,
    ModuleDeFormation,
)

from .boutique import _refus

_log = logging.getLogger(__name__)

#: Un champ écarté sans faire échouer l'envoi : `{"champ": …, "raison": …}`.
Ecarte = dict[str, str]


@dataclass(frozen=True)
class _Champs:
    """Ce qu'un envoi peut modifier sur un objet, par manière de le lire."""

    textes: tuple[str, ...]
    entiers: tuple[str, ...] = ()
    booleens: tuple[str, ...] = ()
    #: Champ de fichier → la fonction qui l'accepte ou lève `Refus`.
    fichiers: dict[str, Callable[[UploadedFile], UploadedFile]] = field(
        default_factory=dict
    )
    #: Clés reconnues mais JAMAIS modifiables par cette route, et pourquoi.
    #: Les nommer vaut mieux que les ranger avec les fautes de frappe.
    fermes: dict[str, str] = field(default_factory=dict)
    #: Clés lues ailleurs que dans `_reporter` (`prix_euros`, `retire`).
    a_part: tuple[str, ...] = ()


_ORDRE_AILLEURS = (
    "L'ordre se change en envoyant la liste complète à la route « ordre »."
)

_FORMATION = _Champs(
    textes=("titre", "sous_titre", "accroche", "description", "devise", "lien_d_achat"),
    entiers=("prix_cents", "duree_heures", "heures_de_coaching", "rang"),
    booleens=("en_ligne",),
    fichiers={"image": regles.image_acceptee},
    fermes={
        "slug": (
            "L'adresse d'une formation est fixée à sa création : la changer "
            "casserait les liens déjà diffusés."
        ),
    },
    a_part=("prix_euros",),
)
_MODULE = _Champs(
    textes=("titre", "description"),
    fermes={"rang": _ORDRE_AILLEURS},
    a_part=("retire",),
)
_LECON = _Champs(
    textes=("titre", "nature", "adresse_video", "texte"),
    entiers=("duree_minutes",),
    booleens=("en_apercu_libre",),
    fichiers={"fichier": regles.document_accepte},
    fermes={"rang": _ORDRE_AILLEURS},
    a_part=("retire",),
)

_OUI = frozenset({"1", "true", "oui", "on"})
_NON = frozenset({"0", "false", "non", "off"})


# ── Lire ce qui arrive ───────────────────────────────────────────────────────


def _donnees(request: HttpRequest) -> Any:
    """Ce que l'envoi porte : formulaire multipart, ou JSON.

    Le choix se fait sur l'en-tête, pour la raison écrite dans
    `dashboard.boutique._donnees` (un multipart qui ne porte qu'un fichier a
    un `request.POST` vide).

    Une différence voulue avec la boutique : un JSON illisible est REFUSÉ. Le
    lire comme un envoi vide répondrait « 200, rien de modifié » à un écran
    qui croit avoir enregistré (règle 1).
    """
    emballage = str(request.content_type or "")
    if emballage.startswith(("multipart/", "application/x-www-form-urlencoded")):
        return request.POST

    illisible = regles.Refus(
        "L'envoi est illisible. Rechargez la page, puis réessayez.", "corps_invalide"
    )
    brut = request.body
    if not brut.strip():
        return {}
    try:
        charge = json.loads(brut)
    # `ValueError` couvre `JSONDecodeError` et `UnicodeDecodeError` ;
    # `RecursionError` vient d'un corps imbriqué à l'excès (`[[[[…`).
    except (ValueError, RecursionError):
        raise illisible from None
    if not isinstance(charge, dict):
        raise illisible
    return charge


def _booleen(valeur: object) -> bool | None:
    if isinstance(valeur, bool):
        return valeur
    texte = str(valeur).strip().lower()
    if texte in _OUI:
        return True
    if texte in _NON:
        return False
    return None


def _entier(valeur: object) -> int | None:
    """Un entier, ou `None` si la saisie n'en est pas un.

    `True` n'est pas 1 et « 12,5 » n'est pas 12 : arrondir en silence
    enregistrerait autre chose que ce qui a été saisi.
    """
    if isinstance(valeur, bool) or valeur is None:
        return None
    if isinstance(valeur, int):
        return valeur
    if isinstance(valeur, float):
        return int(valeur) if valeur.is_integer() else None
    try:
        return int(str(valeur).strip())
    except ValueError:
        return None


def _centimes(valeur: object) -> int | None:
    """Un prix saisi en EUROS (« 1 490 », « 89,90 ») rendu en centimes.

    La conversion vit au serveur, comme pour la boutique : la faire dans le
    navigateur donnerait deux endroits où l'arrondi peut différer.
    """
    if isinstance(valeur, bool) or valeur is None:
        return None
    brut = "".join(str(valeur).replace(",", ".").split())
    try:
        euros = Decimal(brut)
    except InvalidOperation:
        return None
    if not euros.is_finite():
        return None
    # `quantize` lève `InvalidOperation` au-delà de 28 chiffres : « 1e30 » est
    # un nombre fini et rendait une erreur 500 au lieu d'un champ écarté.
    try:
        return int((euros * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    except InvalidOperation:
        return None


def _reporter(
    cible: models.Model, donnees: Any, fichiers: Any, champs: _Champs
) -> list[Ecarte]:
    """Reporte l'envoi sur `cible`, sans rien sauver. Rend les champs écartés.

    Un champ écarté garde sa valeur précédente. Trois raisons de l'être :
    illisible, fermé à cette route, ou inconnu. La dernière compte autant que
    les autres : une clé mal orthographiée par l'écran serait sinon ignorée
    sans bruit, et la cliente croirait sa saisie enregistrée.

    Un FICHIER refusé, lui, lève `Refus` : rien n'est enregistré. C'est
    souvent le seul objet de l'envoi, et un « 200 » y serait un mensonge.
    """
    ecartes: list[Ecarte] = []

    def ecarter(champ: str, raison: str) -> None:
        ecartes.append({"champ": champ, "raison": raison})
        _log.warning("Champ %s écarté pour %r : %s", champ, cible, raison)

    for champ in champs.textes:
        if champ not in donnees:
            continue
        valeur = donnees[champ]
        if isinstance(valeur, dict | list):
            ecarter(champ, "Un texte est attendu.")
        else:
            setattr(cible, champ, regles.texte_propre(valeur))

    for champ in champs.entiers:
        if champ not in donnees:
            continue
        entier = _entier(donnees[champ])
        if entier is None:
            ecarter(champ, "Un nombre entier est attendu.")
        else:
            setattr(cible, champ, entier)

    for champ in champs.booleens:
        if champ not in donnees:
            continue
        booleen = _booleen(donnees[champ])
        if booleen is None:
            ecarter(champ, "Oui ou non est attendu (true ou false).")
        else:
            setattr(cible, champ, booleen)

    for champ, accepter in champs.fichiers.items():
        televerse = fichiers.get(champ) if fichiers else None
        if televerse is not None:
            setattr(cible, champ, accepter(televerse))
        elif champ in donnees:
            ecarter(champ, "Un fichier est attendu, envoyé en multipart.")

    connus = {
        *champs.textes, *champs.entiers, *champs.booleens,
        *champs.fichiers, *champs.a_part,
    }
    recus: Iterable[str] = [*donnees, *(fichiers or ())]
    for cle in recus:
        if cle in champs.fermes:
            ecarter(cle, champs.fermes[cle])
        elif cle not in connus:
            ecarter(cle, "Ce champ n'existe pas.")
    return ecartes


def _reporter_le_prix_en_euros(cible: Formation, donnees: Any) -> list[Ecarte]:
    if "prix_euros" not in donnees:
        return []
    centimes = _centimes(donnees["prix_euros"])
    if centimes is None:
        return [{"champ": "prix_euros", "raison": "Un montant en euros est attendu."}]
    cible.prix_cents = centimes
    return []


def _reporter_le_retrait(
    cible: ModuleDeFormation | LeconDeFormation, donnees: Any, presents: Any
) -> list[Ecarte]:
    """`{"retire": true}` retire, `{"retire": false}` rétablit en fin de liste."""
    if "retire" not in donnees:
        return []
    retire = _booleen(donnees["retire"])
    if retire is None:
        return [{"champ": "retire", "raison": "Oui ou non est attendu (true ou false)."}]
    if retire:
        regles.retirer(cible)
    else:
        regles.retablir(cible, presents)
    return []


# ── Trouver, et répondre ─────────────────────────────────────────────────────


def _trouver[M: models.Model](
    modele: type[M], brut: str, message: str, code: str
) -> M:
    """L'objet désigné, ou un 404 — que l'identifiant soit inconnu OU mal formé.

    Filtrer un `UUIDField` sur une valeur mal formée lève `ValidationError`,
    donc une erreur 500 sur une adresse tapée de travers (voir le commentaire
    des signalements dans `dashboard/urls.py`). On lit l'identifiant ici
    plutôt que par un convertisseur `<uuid:…>` : le 404 du routeur est une
    page, pas la forme `{"erreur", "code"}` que l'écran sait afficher.
    """
    try:
        identifiant = uuid.UUID(str(brut))
    except ValueError:
        raise regles.Refus(message, code, 404) from None
    objet = modele._default_manager.filter(pk=identifiant).first()
    if objet is None:
        raise regles.Refus(message, code, 404)
    return objet


def _formation(brut: str) -> Formation:
    return _trouver(
        Formation, brut, "Cette formation n'existe pas.", "formation_inconnue"
    )


def _module(brut: str) -> ModuleDeFormation:
    return _trouver(
        ModuleDeFormation, brut, "Ce module n'existe pas.", "module_inconnu"
    )


def _lecon(brut: str) -> LeconDeFormation:
    return _trouver(
        LeconDeFormation, brut, "Cette leçon n'existe pas.", "lecon_inconnue"
    )


def _refus_lisibles(
    vue: Callable[..., HttpResponse],
) -> Callable[..., HttpResponse]:
    """Rend tout `Refus` dans la forme de la boutique : `{"erreur", "code"}`.

    `champ` s'y ajoute quand le refus en désigne un.
    """

    @wraps(vue)
    def enveloppe(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        try:
            return vue(request, *args, **kwargs)
        except regles.Refus as refus:
            if not refus.champ:
                return _refus(refus.message, refus.code, refus.statut)
            return JsonResponse(
                {"erreur": refus.message, "code": refus.code, "champ": refus.champ},
                status=refus.statut,
            )

    return enveloppe


def _jour(instant: Any) -> str:
    return instant.isoformat() if instant else ""


def _ranges(elements: Iterable[Any]) -> list[Any]:
    """Les présents dans leur ordre, puis les retirés.

    Le tri est fait ici, sur la collection préchargée, et non par une requête
    par module : la liste complète coûte trois requêtes quel que soit le
    nombre de formations.
    """
    return sorted(
        elements, key=lambda e: (e.retire_le is not None, e.rang, e.created_at)
    )


#: Durée de vie du lien signé rendu à l'administration, en secondes.
_VIE_DU_LIEN_S = 300


def _lien_du_document(lecon: LeconDeFormation) -> str:
    """Lien SIGNÉ vers le document : il vit sous `formations/`, hors vitrine."""
    from evkha import signatures  # noqa: PLC0415 — évite un cycle à l'import

    # Cinq minutes, et non le repli d'une semaine : l'écran relit ce lien au
    # serveur au moment d'ouvrir le document, il n'a donc pas à durer. Chaque
    # lecture de la liste fabriquait sinon, pour TOUS les supports payants, un
    # lien porteur valable sept jours sans jeton (audit du 20/11/2026).
    if not lecon.fichier:
        return ""
    return signatures.lien_absolu(lecon.fichier.name, duree_s=_VIE_DU_LIEN_S)


def _vue_lecon(lecon: LeconDeFormation) -> dict[str, Any]:
    return {
        "id": str(lecon.id),
        "rang": lecon.rang,
        "titre": lecon.titre,
        "nature": lecon.nature,
        "adresse_video": lecon.adresse_video,
        "duree_minutes": lecon.duree_minutes,
        "texte": lecon.texte,
        "fichier": _lien_du_document(lecon),
        "fichier_nom": lecon.fichier.name.rsplit("/", 1)[-1] if lecon.fichier else "",
        "en_apercu_libre": lecon.en_apercu_libre,
        "retire": lecon.retire_le is not None,
        "retire_le": _jour(lecon.retire_le),
    }


def _vue_module(module: ModuleDeFormation) -> dict[str, Any]:
    return {
        "id": str(module.id),
        "rang": module.rang,
        "titre": module.titre,
        "description": module.description,
        "retire": module.retire_le is not None,
        "retire_le": _jour(module.retire_le),
        "lecons": [_vue_lecon(lecon) for lecon in _ranges(module.lecons.all())],
    }


def _vue(formation: Formation) -> dict[str, Any]:
    modules = _ranges(formation.modules.all())
    manque = regles.manque_pour_la_mise_en_ligne(formation)
    return {
        "id": str(formation.id),
        "slug": formation.slug,
        "titre": formation.titre,
        "sous_titre": formation.sous_titre,
        "accroche": formation.accroche,
        "description": formation.description,
        "prix_cents": formation.prix_cents,
        "devise": formation.devise,
        "duree_heures": formation.duree_heures,
        "heures_de_coaching": formation.heures_de_coaching,
        "lien_d_achat": formation.lien_d_achat,
        "image": regles.adresse_de_l_image(formation),
        "en_ligne": formation.en_ligne,
        "rang": formation.rang,
        # Ce qui manque pour publier, dit explicitement — comme la boutique :
        # un bouton « en ligne » qui refuse sans expliquer se lit comme une
        # panne.
        "publiable": not manque,
        "manque": manque,
        "cree_le": _jour(formation.created_at),
        "modifie_le": _jour(formation.updated_at),
        "nombre_de_modules": sum(1 for m in modules if m.retire_le is None),
        # Combien d'organisations y ont ACCÈS — les achats révoqués ne
        # comptent pas. La cliente le lit avant de retirer une leçon : ce
        # programme a des lecteurs.
        "nombre_d_achats": _nombre_d_achats(formation),
        "modules": [_vue_module(module) for module in modules],
    }


#: Nom de l'annotation posée par `_toutes`.
_ACHATS = "achats_comptes"


def _nombre_d_achats(formation: Formation) -> int:
    """Lu dans l'annotation de `_toutes` ; compté en base pour qui n'en vient pas.

    Jamais un zéro par défaut : une fiche qui annoncerait « aucun achat »
    faute d'avoir compté mentirait à la cliente (règle 1).
    """
    annote = getattr(formation, _ACHATS, None)
    if annote is not None:
        return int(annote)
    return formation.achats.filter(revoque_le__isnull=True).count()


def _toutes() -> Any:
    """Les formations, leur programme, et ce que la fiche calcule — sans une
    requête de plus par formation.

    Le nombre d'achats et la présence d'un programme sont annotés dans la
    requête des formations : la liste coûte trois requêtes quel que soit leur
    nombre.
    """
    return regles.avec_programme(
        Formation.objects.annotate(
            **{
                # Les achats qui DONNENT ACCÈS : un accès retiré n'est plus un
                # lecteur du programme. Même filtre que le repli de
                # `_nombre_d_achats`.
                _ACHATS: models.Count(
                    "achats",
                    filter=models.Q(achats__revoque_le__isnull=True),
                    distinct=True,
                )
            }
        )
    ).prefetch_related("modules__lecons")


def _reponse(
    formation_id: Any, ecartes: list[Ecarte] | None = None, statut: int = 200, **plus: str
) -> HttpResponse:
    """La formation RELUE en base, avec son programme.

    Relue, et non l'objet en mémoire : la réponse décrit ce qui est
    enregistré (voir la relecture de `dashboard.boutique.produit`).
    """
    formation = _toutes().get(pk=formation_id)
    return JsonResponse(
        {"formation": _vue(formation), "refuses": ecartes or [], **plus},
        status=statut,
    )


def _liste(donnees: Any, cle: str) -> object:
    """La liste d'identifiants d'un réordonnancement, JSON ou formulaire."""
    if hasattr(donnees, "getlist"):
        return donnees.getlist(cle) if cle in donnees else None
    return donnees.get(cle)


# ── Les formations ───────────────────────────────────────────────────────────


@csrf_exempt
@require_http_methods(["GET", "POST"])
@_refus_lisibles
def formations(request: HttpRequest) -> HttpResponse:
    """Liste les formations avec leur programme, ou en crée une HORS LIGNE."""
    if request.method == "GET":
        return JsonResponse({"formations": [_vue(f) for f in _toutes()]})

    donnees = _donnees(request)
    titre = regles.texte_propre(donnees.get("titre"))
    if not titre:
        raise regles.Refus(
            "Donnez un titre à la formation.", "titre_manquant", champ="titre"
        )

    # À la création — et seulement là — l'adresse peut être proposée.
    propose = regles.texte_propre(donnees.get("slug"))
    champs = replace(
        _FORMATION,
        booleens=(),
        fermes={},
        a_part=(*_FORMATION.a_part, "slug", "en_ligne"),
    )
    try:
        with transaction.atomic():
            nouvelle = Formation(
                titre=titre,
                slug=regles.slug_libre(propose or titre),
                rang=regles.rang_de_fin(Formation.objects.all()),
            )
            ecartes = _reporter(nouvelle, donnees, request.FILES, champs)
            ecartes += _reporter_le_prix_en_euros(nouvelle, donnees)
            # Un `en_ligne` à faux ne demande rien ; tout autre est écarté, et
            # dit : la cliente relit avant de publier.
            if "en_ligne" in donnees and _booleen(donnees["en_ligne"]) is not False:
                ecartes.append({
                    "champ": "en_ligne",
                    "raison": (
                        "Une formation se crée hors ligne : mettez-la en "
                        "ligne après l'avoir relue."
                    ),
                })
            regles.verifier_formation(nouvelle)
            nouvelle.save()
    except IntegrityError:
        # Deux créations simultanées du même titre : la contrainte d'unicité
        # du slug tranche, et la seconde recommence.
        raise regles.Refus(
            "Une formation vient d'être créée à cette adresse. Réessayez.",
            "slug_pris",
            409,
        ) from None

    _log.info("Formation créée : %s", nouvelle.slug)
    return _reponse(nouvelle.pk, ecartes, 201)


@csrf_exempt
@require_http_methods(["POST"])
@_refus_lisibles
def formation(request: HttpRequest, formation_id: str) -> HttpResponse:
    """Modifie une formation, la met en ligne ou hors ligne."""
    cible = _formation(formation_id)
    donnees = _donnees(request)

    with transaction.atomic():
        _sous_verrou(cible.pk, cible)
        ecartes = _reporter(cible, donnees, request.FILES, _FORMATION)
        ecartes += _reporter_le_prix_en_euros(cible, donnees)
        regles.verifier_formation(cible)
        cible.save()

    _log.info("Formation %s modifiée.", cible.slug)
    return _reponse(cible.pk, ecartes)


# ── Les modules ──────────────────────────────────────────────────────────────


def _sous_verrou(formation_id: Any, *relues: models.Model) -> None:
    """Met à la file les écritures d'une même formation, puis relit les cibles.

    À appeler EN TÊTE d'une transaction. Sans lui, la cible était lue avant la
    transaction et `save()` réécrivait toutes ses colonnes : « Enregistrer la
    fiche » avec une image (envoi long), puis « Mettre hors ligne » confirmé
    pendant l'envoi — la première requête terminait en réécrivant
    `en_ligne=True`, et la formation restait en vente (relecture du
    20/11/2026). Même classe pour le rang d'un module lu avant un
    réordonnancement.

    Un seul verrou, sur la formation, pour ses modules et ses leçons aussi :
    deux verrous pris dans des ordres différents finiraient par s'attendre.
    SQLite ignore `select_for_update` ; c'est PostgreSQL, en production, qui
    le tient.
    """
    Formation.objects.select_for_update().get(pk=formation_id)
    for cible in relues:
        cible.refresh_from_db()


def _modules_presents(parente: Formation) -> Any:
    return ModuleDeFormation.objects.filter(formation=parente, retire_le__isnull=True)


def _lecons_presentes(parent: ModuleDeFormation) -> Any:
    return LeconDeFormation.objects.filter(module=parent, retire_le__isnull=True)


@csrf_exempt
@require_http_methods(["POST"])
@_refus_lisibles
def modules(request: HttpRequest, formation_id: str) -> HttpResponse:
    """Ajoute un module en fin de liste."""
    parente = _formation(formation_id)
    donnees = _donnees(request)

    with transaction.atomic():
        _sous_verrou(parente.pk)
        nouveau = ModuleDeFormation(
            formation=parente, rang=regles.rang_de_fin(_modules_presents(parente))
        )
        # `retire` n'a pas de sens à la création : il est rangé avec les
        # champs inconnus plutôt qu'appliqué.
        ecartes = _reporter(
            nouveau, donnees, request.FILES, replace(_MODULE, a_part=())
        )
        regles.verifier_module(nouveau)
        nouveau.save()

    _log.info("Module ajouté à %s : %s", parente.slug, nouveau.titre)
    return _reponse(parente.pk, ecartes, 201, module_id=str(nouveau.id))


@csrf_exempt
@require_http_methods(["POST"])
@_refus_lisibles
def module(request: HttpRequest, module_id: str) -> HttpResponse:
    """Modifie un module, le retire ou le rétablit."""
    cible = _module(module_id)
    donnees = _donnees(request)

    with transaction.atomic():
        _sous_verrou(cible.formation_id, cible)
        ecartes = _reporter(cible, donnees, request.FILES, _MODULE)
        ecartes += _reporter_le_retrait(
            cible, donnees, _modules_presents(cible.formation)
        )
        regles.verifier_module(cible)
        cible.save()

    return _reponse(cible.formation_id, ecartes, module_id=str(cible.id))


@csrf_exempt
@require_http_methods(["POST"])
@_refus_lisibles
def ordre_des_modules(request: HttpRequest, formation_id: str) -> HttpResponse:
    """Réordonne les modules présents d'une formation, d'un seul tenant."""
    parente = _formation(formation_id)
    voulus = _liste(_donnees(request), "modules")

    with transaction.atomic():
        # Le verrou sur la formation met deux réordonnancements à la file :
        # entrelacés, ils laisseraient deux modules au même rang.
        _sous_verrou(parente.pk)
        regles.reordonner(list(_modules_presents(parente)), voulus, quoi="modules")

    return _reponse(parente.pk)


# ── Les leçons ───────────────────────────────────────────────────────────────


@csrf_exempt
@require_http_methods(["POST"])
@_refus_lisibles
def lecons(request: HttpRequest, module_id: str) -> HttpResponse:
    """Ajoute une leçon en fin de module."""
    parent = _module(module_id)
    donnees = _donnees(request)

    with transaction.atomic():
        _sous_verrou(parent.formation_id)
        nouvelle = LeconDeFormation(
            module=parent, rang=regles.rang_de_fin(_lecons_presentes(parent))
        )
        ecartes = _reporter(
            nouvelle, donnees, request.FILES, replace(_LECON, a_part=())
        )
        regles.verifier_lecon(nouvelle)
        nouvelle.save()

    return _reponse(parent.formation_id, ecartes, 201, lecon_id=str(nouvelle.id))


@csrf_exempt
@require_http_methods(["POST"])
@_refus_lisibles
def lecon(request: HttpRequest, lecon_id: str) -> HttpResponse:
    """Modifie une leçon, la retire ou la rétablit."""
    cible = _lecon(lecon_id)
    donnees = _donnees(request)

    with transaction.atomic():
        _sous_verrou(cible.module.formation_id, cible)
        ecartes = _reporter(cible, donnees, request.FILES, _LECON)
        ecartes += _reporter_le_retrait(
            cible, donnees, _lecons_presentes(cible.module)
        )
        regles.verifier_lecon(cible)
        cible.save()

    return _reponse(cible.module.formation_id, ecartes, lecon_id=str(cible.id))


@csrf_exempt
@require_http_methods(["POST"])
@_refus_lisibles
def ordre_des_lecons(request: HttpRequest, module_id: str) -> HttpResponse:
    """Réordonne les leçons présentes d'un module, d'un seul tenant."""
    parent = _module(module_id)
    voulus = _liste(_donnees(request), "lecons")

    with transaction.atomic():
        _sous_verrou(parent.formation_id)
        regles.reordonner(list(_lecons_presentes(parent)), voulus, quoi="leçons")

    return _reponse(parent.formation_id)


# ── Les achats, et le retrait d'un accès ─────────────────────────────────────


def _vue_achat(achat: AchatFormation) -> dict[str, Any]:
    """Un achat tel que l'administration le lit. Écrit clé par clé.

    La référence de paiement est ABRÉGÉE : entière, elle ouvre la première
    session du compte né de ce paiement (`achats.reference_abregee`). Elle
    suffit à reconnaître la ligne ; le paiement se retrouve chez le
    prestataire par l'organisation, le montant et la date.
    """
    return {
        "id": str(achat.id),
        "organisation": achat.organisation.raison_sociale,
        "organisation_id": str(achat.organisation_id),
        "email": achat.email,
        "montant_cents": achat.montant_cents,
        "devise": achat.devise,
        "achete_le": achat.created_at.isoformat(),
        # `null`, et non une chaîne vide : c'est l'absence de retrait qui
        # dit que l'achat donne accès.
        "revoque_le": achat.revoque_le.isoformat() if achat.revoque_le else None,
        "motif_de_revocation": achat.motif_de_revocation,
        "reference_paiement": reference_abregee(achat.reference_paiement),
    }


@require_http_methods(["GET"])
@_refus_lisibles
def achats(request: HttpRequest, formation_id: str) -> HttpResponse:
    """Les achats d'une formation, du plus récent au plus ancien.

    TOUS, retirés compris : c'est ici que la gérante retrouve un accès qu'elle
    a retiré pour le rétablir, et qu'elle lit pourquoi il l'a été.
    """
    parente = _formation(formation_id)
    lignes = (
        AchatFormation.objects.filter(formation=parente)
        .select_related("organisation")
        .order_by("-created_at")
    )
    return JsonResponse({"achats": [_vue_achat(ligne) for ligne in lignes]})


def _motif(donnees: Any) -> str:
    """Le motif saisi, ou `Refus`. Jamais coupé en silence."""
    brut = donnees.get("motif", "")
    if isinstance(brut, dict | list):
        raise regles.Refus("Le motif est un texte.", "motif_illisible", champ="motif")
    motif = regles.texte_propre(brut)
    longueur = AchatFormation._meta.get_field("motif_de_revocation").max_length or 0
    if len(motif) > longueur:
        raise regles.Refus(
            f"Le motif dépasse {longueur} caractères. Résumez-le.",
            "motif_trop_long",
            champ="motif",
        )
    return motif


@csrf_exempt
@require_http_methods(["POST"])
@_refus_lisibles
def achat(request: HttpRequest, achat_id: str) -> HttpResponse:
    """Retire l'accès qu'un achat donne (`{"revoque": true}`), ou le rétablit.

    **Un accès se retire, il ne s'efface pas** (audit du 20/11/2026). Après
    un remboursement ou une contestation — que le webhook signale par un
    incident, sans rien retirer lui-même —, c'est ici que la gérante décide.
    La ligne reste, avec sa référence et son montant : aucune méthode ne
    supprime, comme partout dans ce module.

    Retirer deux fois ne change rien : la première date et le premier motif
    restent. Rétablir efface le motif.

    Rétablir est REFUSÉ si l'organisation a depuis racheté la formation : elle
    a déjà son accès, par une autre ligne, et deux achats actifs pour un même
    couple sont ce que la contrainte de la base interdit.
    """
    cible = _trouver(
        AchatFormation, achat_id, "Cet achat n'existe pas.", "achat_inconnu"
    )
    donnees = _donnees(request)
    revoque = _booleen(donnees["revoque"]) if "revoque" in donnees else None
    if revoque is None:
        raise regles.Refus(
            "Indiquez s'il faut retirer l'accès ou le rétablir "
            "(« revoque » : true ou false).",
            "revoque_manquant",
            champ="revoque",
        )
    motif = _motif(donnees)

    with transaction.atomic():
        # Sous verrou : deux gestes simultanés sur le même achat se suivent.
        cible = (
            AchatFormation.objects.select_for_update(of=("self",))
            .select_related("organisation", "formation")
            .get(pk=cible.pk)
        )
        if revoque and cible.revoque_le is None:
            cible.revoque_le = timezone.now()
            cible.motif_de_revocation = motif
            cible.save(
                update_fields=["revoque_le", "motif_de_revocation", "updated_at"]
            )
            _log.info(
                "Accès à la formation %s retiré à l'organisation %s (achat %s).",
                cible.formation.slug, cible.organisation_id, cible.id,
            )
        elif not revoque and cible.revoque_le is not None:
            rachetee = regles.Refus(
                "Cette organisation a racheté la formation depuis : elle y a "
                "déjà accès par son nouvel achat. Il n'y a rien à rétablir.",
                "formation_rachetee",
                409,
            )
            if (
                AchatFormation.objects.filter(
                    organisation=cible.organisation_id,
                    formation=cible.formation_id,
                    revoque_le__isnull=True,
                )
                .exclude(pk=cible.pk)
                .exists()
            ):
                raise rachetee
            cible.revoque_le = None
            cible.motif_de_revocation = ""
            try:
                # Point de sauvegarde : la contrainte d'unicité est le dernier
                # rempart si un rachat arrive entre la lecture et l'écriture.
                with transaction.atomic():
                    cible.save(
                        update_fields=[
                            "revoque_le", "motif_de_revocation", "updated_at",
                        ]
                    )
            except IntegrityError:
                raise rachetee from None
            _log.info(
                "Accès à la formation %s rétabli pour l'organisation %s (achat %s).",
                cible.formation.slug, cible.organisation_id, cible.id,
            )

    return JsonResponse({"achat": _vue_achat(cible)})

"""Gestion de la boutique depuis l'espace d'administration.

« Le catalogue s'elargit chaque mois » : ajouter, modifier ou retirer un
produit ne doit jamais repasser par un developpeur ni par une mise en ligne.
Ces vues sont donc l'unique chemin, et elles acceptent le televersement des
fichiers.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from django.db.models import Count, Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from catalog.models import AchatProduit, AvisProduit, ProduitBoutique

_log = logging.getLogger(__name__)

#: Champs texte modifiables depuis l'administration.
CHAMPS_TEXTE = ("titre", "description", "sommaire", "theme", "devise")
#: Champs numeriques. Un envoi illisible laisse la valeur precedente plutot
#: que de remettre le prix a zero — un produit gratuit se vendrait sans
#: contrepartie.
CHAMPS_ENTIERS = ("prix_cents", "nombre_de_pages", "rang")
#: Fichiers acceptes, et leur champ.
CHAMPS_FICHIERS = ("fichier", "fichier_editable", "extrait", "image")


def _refus(message: str, code: str, statut: int = 400) -> HttpResponse:
    return JsonResponse({"erreur": message, "code": code}, status=statut)


def _url(fichier: Any) -> str:
    """Adresse absolue d'un fichier, ou chaine vide.

    Absolue pour la meme raison que dans `vues_boutique` : l'administration est
    servie par un autre domaine que `/media/`, et un chemin relatif y afficherait
    la page de l'application a la place de la couverture.
    """
    from evkha import signatures  # noqa: PLC0415 — evite un cycle a l'import

    try:
        return signatures.absolu(fichier.url) if fichier else ""
    except ValueError:
        return ""


def _vue(produit: ProduitBoutique, ventes: dict[Any, dict[str, int]]) -> dict[str, Any]:
    mesure = ventes.get(produit.id, {})
    return {
        "id": str(produit.id),
        "slug": produit.slug,
        "titre": produit.titre,
        "description": produit.description,
        "sommaire": produit.sommaire,
        "theme": produit.theme,
        "prix_cents": produit.prix_cents,
        "devise": produit.devise,
        "pages": produit.nombre_de_pages,
        "mise_a_jour": (
            produit.mise_a_jour_le.isoformat() if produit.mise_a_jour_le else ""
        ),
        "en_ligne": produit.en_ligne,
        "rang": produit.rang,
        "fichier": _url(produit.fichier),
        "fichier_editable": _url(produit.fichier_editable),
        "extrait": _url(produit.extrait),
        "image": _url(produit.image),
        # Ce qui manque pour publier, dit explicitement. Un bouton « en ligne »
        # qui refuse sans expliquer se lit comme une panne.
        "publiable": produit.est_publiable,
        "manque": [] if produit.est_publiable else [
            *([] if produit.prix_cents > 0 else ["un prix"]),
            *([] if produit.fichier else ["le fichier à remettre"]),
        ],
        "ventes": mesure.get("nombre", 0),
        "recette_cents": mesure.get("recette", 0),
        "note": produit.note_moyenne,
        "avis": [
            {
                "id": str(a.id),
                "auteur": a.auteur,
                "qualite": a.qualite,
                "note": a.note,
                "texte": a.texte,
                "publie": a.publie,
                "date": a.created_at.date().isoformat(),
            }
            for a in produit.avis.all()
        ],
    }


def _ventes_par_produit() -> dict[Any, dict[str, int]]:
    lignes = (
        AchatProduit.objects.values("produit_id")
        .annotate(nombre=Count("id"), recette=Sum("montant_cents"))
    )
    return {
        ligne["produit_id"]: {
            "nombre": int(ligne["nombre"] or 0),
            "recette": int(ligne["recette"] or 0),
        }
        for ligne in lignes
    }


def _slug_libre(titre: str, actuel: str = "") -> str:
    """Un slug unique, derive du titre.

    Il n'est pas recalcule quand le titre change sur un produit deja publie :
    le slug est dans l'adresse de la fiche, et la changer casserait les liens
    partages et le referencement.
    """
    if actuel:
        return actuel
    base = slugify(titre)[:45] or "etude"
    slug, suffixe = base, 2
    while ProduitBoutique.objects.filter(slug=slug).exists():
        slug = f"{base}-{suffixe}"
        suffixe += 1
    return slug


def _appliquer(produit: ProduitBoutique, donnees: Any, fichiers: Any) -> list[str]:
    """Reporte ce qui a ete envoye. Retourne les champs modifies."""
    modifies: list[str] = []

    for champ in CHAMPS_TEXTE:
        if champ in donnees:
            setattr(produit, champ, str(donnees[champ]).strip())
            modifies.append(champ)

    for champ in CHAMPS_ENTIERS:
        if champ in donnees:
            try:
                setattr(produit, champ, max(0, int(donnees[champ])))
                modifies.append(champ)
            except (TypeError, ValueError):
                _log.warning(
                    "Champ %s illisible pour le produit %s : valeur ignoree.",
                    champ, produit.slug or produit.titre,
                )

    # Le prix se saisit en EUROS dans l'administration, et se stocke en
    # centimes. La conversion vit ici, a l'entree : la faire dans le
    # navigateur donnerait deux endroits ou l'arrondi peut differer.
    if "prix_euros" in donnees:
        brut = str(donnees["prix_euros"]).replace(",", ".").strip()
        if brut:
            try:
                produit.prix_cents = max(0, round(float(brut) * 100))
                modifies.append("prix_cents")
            except ValueError:
                _log.warning("Prix illisible (%r) : valeur ignoree.", brut)

    if "mise_a_jour" in donnees:
        valeur = str(donnees["mise_a_jour"]).strip()
        produit.mise_a_jour_le = valeur or None
        modifies.append("mise_a_jour_le")

    if "en_ligne" in donnees:
        produit.en_ligne = str(donnees["en_ligne"]).lower() in ("1", "true", "oui")
        modifies.append("en_ligne")

    for champ in CHAMPS_FICHIERS:
        televerse = fichiers.get(champ) if fichiers else None
        if televerse is not None:
            setattr(produit, champ, televerse)
            modifies.append(champ)

    return modifies


@csrf_exempt
@require_http_methods(["GET", "POST"])
def produits(request: HttpRequest) -> HttpResponse:
    """Liste les produits, ou en cree un."""
    if request.method == "GET":
        ventes = _ventes_par_produit()
        return JsonResponse({
            "produits": [
                _vue(p, ventes)
                for p in ProduitBoutique.objects.prefetch_related("avis")
                .all()
                .order_by("rang", "titre")
            ],
        })

    donnees = _donnees(request)
    titre = str(donnees.get("titre") or "").strip()
    if not titre:
        return _refus("Donnez un titre à l'étude.", "titre_manquant")

    produit = ProduitBoutique(titre=titre, slug=_slug_libre(titre))
    _appliquer(produit, donnees, request.FILES)
    produit.titre = titre
    produit.save()
    _log.info("Produit de boutique cree : %s", produit.slug)
    return JsonResponse({"produit": _vue(produit, _ventes_par_produit())}, status=201)


@csrf_exempt
@require_http_methods(["POST", "DELETE"])
def produit(request: HttpRequest, produit_id: str) -> HttpResponse:
    """Modifie un produit, ou le supprime s'il n'a jamais ete vendu."""
    cible = ProduitBoutique.objects.filter(id=produit_id).first()
    if cible is None:
        return _refus("Ce produit n'existe pas.", "produit_inconnu", 404)

    if request.method == "DELETE":
        if AchatProduit.objects.filter(produit=cible).exists():
            # Supprimer detruirait l'historique des ventes ET l'acces de ceux
            # qui ont paye. Le retrait se fait par `en_ligne`, qui preserve
            # les deux.
            return _refus(
                "Cette étude a déjà été vendue : elle ne peut plus être "
                "supprimée. Mettez-la hors ligne pour la retirer de la "
                "boutique — les acheteurs gardent leur accès.",
                "produit_vendu",
                409,
            )
        slug = cible.slug
        cible.delete()
        _log.info("Produit de boutique supprime : %s", slug)
        return JsonResponse({"supprime": slug})

    donnees = _donnees(request)
    modifies = _appliquer(cible, donnees, request.FILES)

    if cible.en_ligne and not cible.est_publiable:
        return _refus(
            "Cette étude ne peut pas être mise en ligne tant qu'il lui manque "
            "un prix ou son fichier.",
            "produit_incomplet",
            409,
        )

    cible.save()
    _log.info("Produit %s modifie (%s).", cible.slug, ", ".join(modifies) or "rien")
    return JsonResponse({"produit": _vue(cible, _ventes_par_produit())})


@csrf_exempt
@require_http_methods(["POST"])
def avis(request: HttpRequest, produit_id: str) -> HttpResponse:
    """Ajoute un avis a une etude.

    Saisi par la cliente, pas depose par l'acheteur : voir `AvisProduit`. Un
    avis sans auteur serait invérifiable et sans valeur pour le lecteur — il
    est donc refuse, avec le nom de ce qui manque.
    """
    cible = ProduitBoutique.objects.filter(id=produit_id).first()
    if cible is None:
        return _refus("Ce produit n'existe pas.", "produit_inconnu", 404)

    donnees = _donnees(request)
    auteur = str(donnees.get("auteur") or "").strip()
    if not auteur:
        return _refus("Donnez le nom de la personne qui témoigne.", "auteur_manquant")

    try:
        note = int(donnees.get("note") or 5)
    except (TypeError, ValueError):
        note = 5
    # Borne appliquee ici ET par les validateurs du modele : ceux-ci ne
    # s'executent qu'a `full_clean()`, que `create()` n'appelle pas.
    note = min(5, max(1, note))

    ligne = AvisProduit.objects.create(
        produit=cible,
        auteur=auteur,
        qualite=str(donnees.get("qualite") or "").strip(),
        note=note,
        texte=str(donnees.get("texte") or "").strip(),
        publie=str(donnees.get("publie", "true")).lower() in ("1", "true", "oui"),
    )
    _log.info("Avis ajoute sur %s par %s (%s/5).", cible.slug, ligne.auteur, note)
    return JsonResponse({"produit": _vue(cible, _ventes_par_produit())}, status=201)


@csrf_exempt
@require_http_methods(["POST", "DELETE"])
def avis_un(request: HttpRequest, avis_id: str) -> HttpResponse:
    """Publie, retire ou supprime un avis."""
    ligne = AvisProduit.objects.filter(id=avis_id).select_related("produit").first()
    if ligne is None:
        return _refus("Cet avis n'existe pas.", "avis_inconnu", 404)

    produit_cible = ligne.produit
    if request.method == "DELETE":
        ligne.delete()
    else:
        donnees = _donnees(request)
        if "publie" in donnees:
            ligne.publie = str(donnees["publie"]).lower() in ("1", "true", "oui")
            ligne.save(update_fields=["publie", "updated_at"])

    return JsonResponse({"produit": _vue(produit_cible, _ventes_par_produit())})


@require_http_methods(["GET"])
def ventes(request: HttpRequest) -> HttpResponse:
    """Les ventes de la boutique, de la plus recente a la plus ancienne."""
    lignes = (
        AchatProduit.objects.select_related("produit", "organisation")
        .order_by("-created_at")[:200]
    )
    return JsonResponse({
        "ventes": [
            {
                "id": str(a.id),
                "produit": a.produit.titre,
                "slug": a.produit.slug,
                "organisation": a.organisation.raison_sociale,
                "email": a.email,
                "montant_cents": a.montant_cents,
                "achete_le": a.created_at.isoformat(),
            }
            for a in lignes
        ],
    })


def _donnees(request: HttpRequest) -> Any:
    """Ce que l'envoi porte, quel que soit son emballage.

    L'administration envoie du multipart quand il y a un fichier, du JSON
    sinon. Accepter les deux evite d'imposer un formulaire multipart pour
    changer un prix.

    Le choix se fait sur l'EMBALLAGE — l'en-tete —, et surtout pas sur le
    contenu. `request.POST if request.POST else <json>` paraissait equivalent
    et ne l'etait pas : un multipart ne portant QUE des fichiers a un
    `request.POST` VIDE, on retombait donc sur la lecture de `request.body`,
    que l'analyseur multipart a deja consomme. Django leve alors
    `RawPostDataException`, et le serveur rend 500.

    Mesure le 21/08/2026 : deposer le PDF d'une etude sans rien changer
    d'autre — le geste le plus courant de la cliente — repondait
    « Enregistrement impossible » sans que rien n'explique pourquoi.
    """
    emballage = str(request.content_type or "")
    if emballage.startswith(("multipart/", "application/x-www-form-urlencoded")):
        return request.POST
    try:
        charge = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return {}
    return charge if isinstance(charge, dict) else {}

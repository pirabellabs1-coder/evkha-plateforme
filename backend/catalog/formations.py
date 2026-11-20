"""Les règles des formations, écrites UNE fois.

L'administration (`dashboard/formations.py`), les pages publiques
(`organisations/vues_formations.py`) et la commande d'amorçage passent toutes
par ce module. Une règle recopiée dans une vue finirait par dire autre chose
que sa voisine (règle 5 du `CLAUDE.md`) : ici, une adresse de vidéo se juge au
même endroit que le lien d'achat, et « publiable » a une seule définition.

Deux natures de refus, et la différence est un contrat avec l'écran
d'administration :

- une saisie **illisible** (« abc » dans un prix) n'est pas jugée ici : la vue
  laisse la valeur précédente et le dit dans sa réponse ;
- une saisie **lisible mais contraire à une règle** (prix négatif, adresse en
  `http://`, mise en ligne sans prix) lève `Refus` : rien n'est enregistré.

Rien, dans ce module, ne supprime une ligne : un module ou une leçon se
retire et se rétablit, une formation se met hors ligne.
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from django.core.files.uploadedfile import UploadedFile
from django.db import models
from django.db.backends.base.operations import BaseDatabaseOperations
from django.db.models import Exists, Max, OuterRef, Prefetch, QuerySet
from django.utils import timezone
from django.utils.text import slugify

from organisations import fichiers

from .models import Formation, LeconDeFormation, ModuleDeFormation, NatureDeLecon


class Refus(ValueError):
    """Une saisie contraire à une règle. Le message est destiné à la cliente."""

    def __init__(
        self, message: str, code: str, statut: int = 400, champ: str = ""
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.statut = statut
        #: Le champ en cause, quand il y en a un : l'écran peut le désigner.
        self.champ = champ


#: Le nom que la cliente lit dans un refus. Un champ absent d'ici garde son
#: nom technique — c'est laid, mais ce n'est jamais muet.
LIBELLES: dict[str, str] = {
    "titre": "Le titre",
    "slug": "L'adresse de la formation",
    "sous_titre": "Le sous-titre",
    "devise": "La devise",
    "prix_cents": "Le prix",
    "duree_heures": "La durée en heures",
    "heures_de_coaching": "Le nombre d'heures de coaching",
    "lien_d_achat": "Le lien d'achat",
    "rang": "Le rang",
    "adresse_video": "L'adresse de la vidéo",
    "duree_minutes": "La durée en minutes",
    "nature": "La nature de la leçon",
}


def texte_propre(valeur: object) -> str:
    """Un texte saisi, sans ses blancs de bord ni octet nul.

    L'octet nul n'est pas un détail : PostgreSQL le refuse dans un texte, et
    la suite tourne sur SQLite qui l'accepte. Un collage malheureux rendrait
    500 en production sans qu'aucun test ne l'ait vu.
    """
    return str(valeur if valeur is not None else "").replace("\x00", "").strip()


# ── Les adresses externes ────────────────────────────────────────────────────

#: Signes qu'une adresse n'a pas à porter. Les blancs et les caractères de
#: contrôle sont écartés à part ; ceux-ci servent à sortir d'un attribut HTML
#: ou à tromper un analyseur d'adresses.
_SIGNES_REFUSES = frozenset("<>\"'\\^`{|}")


def _hote_plausible(hote: str) -> bool:
    """Un nom de domaine : au moins deux étiquettes, lettres, chiffres, tirets."""
    etiquettes = hote.split(".")
    if len(etiquettes) < 2:
        return False
    return all(
        etiquette
        and not etiquette.startswith("-")
        and not etiquette.endswith("-")
        and all(signe.isalnum() or signe == "-" for signe in etiquette)
        for etiquette in etiquettes
    )


def adresse_https(brut: object, *, code: str, champ: str) -> str:
    """Une adresse externe : vide, ou en `https://` et bien formée.

    Sert à l'adresse d'une vidéo ET au lien d'achat. Les deux finissent dans
    un `href` ou un lecteur : une adresse `javascript:` ou `data:` y exécute
    du code chez le visiteur, et une adresse `http://` est bloquée par le
    navigateur sur une page servie en `https://` — la vidéo ne s'afficherait
    pas, sans message.

    On AUTORISE une forme au lieu d'interdire des schémas un par un : la
    liste des schémas dangereux n'est pas fermée, celle des schémas admis
    tient en un mot (règle 4).

    Les blancs de bord sont retirés — un collage en apporte souvent ; un
    blanc À L'INTÉRIEUR est refusé, il coupe l'adresse en deux.
    """
    valeur = texte_propre(brut)
    if not valeur:
        return ""

    refus = Refus(
        f"{LIBELLES.get(champ, champ)} doit être une adresse complète qui "
        "commence par https:// — par exemple https://vimeo.com/123456789.",
        code,
        champ=champ,
    )
    if any(
        signe.isspace() or not signe.isprintable() or signe in _SIGNES_REFUSES
        for signe in valeur
    ):
        raise refus
    try:
        morceaux = urlsplit(valeur)
        # La lecture du port lève `ValueError` s'il n'est pas un nombre.
        _ = morceaux.port
    except ValueError:
        raise refus from None
    if morceaux.scheme != "https" or valeur[:8].lower() != "https://":
        raise refus
    # `https://evkha.fr@ailleurs.example/` s'ouvre sur `ailleurs.example` :
    # une adresse qui porte un identifiant ne dit pas où elle mène.
    if "@" in morceaux.netloc:
        raise refus
    if not _hote_plausible(morceaux.hostname or ""):
        raise refus
    # Le schéma est rendu en minuscules : la contrainte de base compare
    # `https://` à la lettre près sous PostgreSQL.
    return f"https://{valeur[8:]}"


# ── Les contrôles avant écriture ─────────────────────────────────────────────


def _verifier_les_champs(objet: models.Model) -> None:
    """Longueurs et bornes, lues dans le modèle et non recopiées.

    SQLite n'applique ni la longueur d'un `CharField` ni la borne d'un petit
    entier ; PostgreSQL lève. Sans ce contrôle, un titre de 300 signes passe
    tous les tests et rend 500 en production.
    """
    for champ in objet._meta.concrete_fields:
        valeur = getattr(objet, champ.attname)
        libelle = LIBELLES.get(champ.name, champ.name)

        if isinstance(champ, models.CharField) and isinstance(valeur, str):
            maximum = champ.max_length
            if maximum is not None and len(valeur) > maximum:
                raise Refus(
                    f"{libelle} est trop long : {len(valeur)} signes, pour "
                    f"{maximum} au plus.",
                    "texte_trop_long",
                    champ=champ.name,
                )

        if isinstance(
            champ, models.PositiveSmallIntegerField | models.PositiveIntegerField
        ):
            _, plafond = BaseDatabaseOperations.integer_field_ranges[
                champ.get_internal_type()
            ]
            if isinstance(valeur, bool) or not isinstance(valeur, int):
                raise Refus(
                    f"{libelle} doit être un nombre entier.",
                    "valeur_illisible",
                    champ=champ.name,
                )
            if valeur < 0:
                raise Refus(
                    f"{libelle} ne peut pas être négatif.",
                    "prix_negatif" if champ.name == "prix_cents" else "valeur_negative",
                    champ=champ.name,
                )
            if valeur > plafond:
                raise Refus(
                    f"{libelle} est trop grand ({plafond} au plus).",
                    "valeur_trop_grande",
                    champ=champ.name,
                )


def _exiger_un_titre(titre: str, message: str) -> None:
    if not titre.strip():
        raise Refus(message, "titre_manquant", champ="titre")


# ── On n'encaisse pas pour rien ──────────────────────────────────────────────


def lecons_presentes() -> QuerySet[LeconDeFormation]:
    """Les leçons qu'un acheteur lirait : ni retirées, ni dans un module retiré.

    LA définition de « présente », écrite une fois : la règle de vente et la
    mise en ligne partent toutes deux d'ici.
    """
    return LeconDeFormation.objects.filter(
        retire_le__isnull=True, module__retire_le__isnull=True
    )


#: Nom de l'annotation posée par `avec_programme`.
_PROGRAMME_PRESENT = "programme_present"


def avec_programme(formations: QuerySet[Formation]) -> QuerySet[Formation]:
    """Annote chaque formation de la réponse de `a_un_programme`.

    Pour les listes : sans cette annotation, `a_un_programme` interroge la
    base une fois par formation.
    """
    return formations.annotate(**{
        _PROGRAMME_PRESENT: Exists(
            lecons_presentes().filter(module__formation=OuterRef("pk"))
        )
    })


def a_un_programme(formation: Formation) -> bool:
    """La formation porte-t-elle au moins une leçon présente ?

    C'est la moitié de « vendable » : une formation sans leçon encaisserait
    1 490 € pour un espace vide. Elle sert aux DEUX endroits qui en décident —
    `manque_pour_la_mise_en_ligne` et l'ouverture du paiement (`a_vendre`) —
    pour qu'ils ne puissent pas répondre différemment (règle 5).

    Lue dans l'annotation de `avec_programme` quand la formation en vient,
    demandée à la base sinon. Une fiche pas encore enregistrée n'a rien.
    """
    annotee = getattr(formation, _PROGRAMME_PRESENT, None)
    if annotee is not None:
        return bool(annotee)
    if formation._state.adding:
        return False
    return lecons_presentes().filter(module__formation=formation).exists()


def manque_pour_la_mise_en_ligne(formation: Formation) -> list[str]:
    """Ce qui empêche de publier, nommé. Liste vide : la formation est publiable.

    Une formation à zéro euro s'afficherait « 0 € » sur une page de vente ;
    sans titre ou sans adresse, la page n'aurait rien à montrer ni à lier ;
    sans leçon, elle se vendrait sans rien donner à lire.

    `en_vente()` filtre sur les trois premières conditions côté base. La
    quatrième — la leçon — n'y est PAS, et c'est voulu : retirer la dernière
    leçon d'une formation déjà en ligne ne la fait pas disparaître de la page
    publique (un retrait de leçon n'est pas une mise hors ligne, et la cliente
    est souvent en train de la remplacer). Elle reste AFFICHÉE ; c'est son
    ACHAT qui est refusé, par `a_vendre`. Et tant qu'il lui manque une leçon,
    sa fiche ne s'enregistre plus « en ligne » : la cliente ajoute la leçon,
    ou met la formation hors ligne.
    """
    return [
        *([] if formation.prix_cents > 0 else ["un prix"]),
        *([] if formation.titre.strip() else ["un titre"]),
        *([] if formation.slug else ["une adresse"]),
        *([] if a_un_programme(formation) else ["au moins une leçon"]),
    ]


def verifier_formation(formation: Formation) -> None:
    """Toutes les règles d'une formation. Lève `Refus` ; ne sauve rien."""
    _exiger_un_titre(formation.titre, "Donnez un titre à la formation.")
    if not formation.slug or slugify(formation.slug) != formation.slug:
        raise Refus(
            "L'adresse de la formation ne peut contenir que des lettres sans "
            "accent, des chiffres et des tirets.",
            "slug_invalide",
            champ="slug",
        )
    _verifier_les_champs(formation)
    if len(formation.devise) != 3 or not (
        # `isascii` : « ééé » est alphabétique, et `Intl.NumberFormat` lève
        # sur une devise pareille — l'écran entier tombait.
        formation.devise.isascii() and formation.devise.isalpha()
    ):
        raise Refus(
            "La devise s'écrit en trois lettres, par exemple EUR.",
            "devise_invalide",
            champ="devise",
        )
    formation.devise = formation.devise.upper()
    formation.lien_d_achat = adresse_https(
        formation.lien_d_achat, code="lien_d_achat_invalide", champ="lien_d_achat"
    )
    if formation.en_ligne:
        manque = manque_pour_la_mise_en_ligne(formation)
        if manque:
            raise Refus(
                "Cette formation ne peut pas être en ligne : il lui manque "
                f"{' et '.join(manque)}.",
                "formation_incomplete",
                409,
            )


def verifier_module(module: ModuleDeFormation) -> None:
    _exiger_un_titre(module.titre, "Donnez un titre au module.")
    _verifier_les_champs(module)


def verifier_lecon(lecon: LeconDeFormation) -> None:
    _exiger_un_titre(lecon.titre, "Donnez un titre à la leçon.")
    if lecon.nature not in NatureDeLecon.values:
        raise Refus(
            "La nature d'une leçon est l'une de celles-ci : "
            f"{', '.join(NatureDeLecon.values)}.",
            "nature_inconnue",
            champ="nature",
        )
    lecon.adresse_video = adresse_https(
        lecon.adresse_video, code="adresse_video_invalide", champ="adresse_video"
    )
    if lecon.nature == NatureDeLecon.VIDEO and not lecon.adresse_video:
        raise Refus(
            "Une leçon vidéo a besoin de l'adresse de sa vidéo. Collez "
            "l'adresse https:// de la vidéo, ou choisissez une autre nature.",
            "adresse_video_manquante",
            champ="adresse_video",
        )
    _verifier_les_champs(lecon)


# ── Le slug ──────────────────────────────────────────────────────────────────


def slug_libre(source: str) -> str:
    """Un slug unique, dérivé du titre (ou de l'adresse proposée).

    Calculé à la création, et plus jamais ensuite : c'est l'adresse publique
    de la formation, et un lien déjà diffusé ne doit pas casser parce qu'un
    titre a été retouché. Même choix que `dashboard.boutique._slug_libre`.
    """
    base = slugify(source)[:45].strip("-") or "formation"
    slug, suffixe = base, 2
    while Formation.objects.filter(slug=slug).exists():
        slug = f"{base}-{suffixe}"
        suffixe += 1
    return slug


# ── L'ordre, le retrait, le rétablissement ───────────────────────────────────


def rang_de_fin(elements: QuerySet[Any]) -> int:
    """Le rang qui place un nouvel élément APRÈS ceux de `elements`."""
    dernier = elements.aggregate(dernier=Max("rang"))["dernier"]
    return 0 if dernier is None else int(dernier) + 1


def retirer(element: ModuleDeFormation | LeconDeFormation) -> None:
    """Pose la date de retrait. Un élément déjà retiré garde sa date."""
    if element.retire_le is None:
        element.retire_le = timezone.now()


def retablir(
    element: ModuleDeFormation | LeconDeFormation, presents: QuerySet[Any]
) -> None:
    """Lève le retrait, et range l'élément EN FIN de liste.

    Son ancien rang ne veut plus rien dire : la liste a pu être réordonnée
    depuis, et le reprendre le glisserait au milieu d'un ordre que la cliente
    vient de fixer. Un élément qui n'était pas retiré ne bouge pas.
    """
    if element.retire_le is not None:
        element.retire_le = None
        element.rang = rang_de_fin(presents)


def reordonner[E: (ModuleDeFormation, LeconDeFormation)](
    presents: Sequence[E],
    identifiants: object,
    *,
    quoi: str,
) -> None:
    """Réécrit les rangs dans l'ordre demandé, de 0 à n-1.

    La liste doit être EXACTEMENT l'ensemble des éléments présents. Un ordre
    partiel laisserait deviner la place des absents, un identifiant étranger
    — un module d'une autre formation, un élément retiré — changerait le rang
    d'une ligne que l'appelant ne regardait pas.

    L'appelant ouvre la transaction et tient le verrou ; cette fonction écrit
    toutes les lignes en une requête.
    """
    if not isinstance(identifiants, list):
        raise Refus(
            f"Envoyez la liste complète des {quoi}, dans l'ordre voulu.",
            "ordre_illisible",
        )

    etranger = Refus(
        f"La liste contient un élément qui ne fait pas partie des {quoi} "
        "présents (il vient d'ailleurs, ou il a été retiré).",
        "ordre_etranger",
    )
    voulus: list[uuid.UUID] = []
    for brut in identifiants:
        try:
            voulus.append(uuid.UUID(str(brut)))
        except ValueError:
            raise etranger from None

    if len(set(voulus)) != len(voulus):
        raise Refus(
            "La liste contient deux fois le même élément.", "ordre_doublon"
        )
    par_identifiant = {element.pk: element for element in presents}
    if any(identifiant not in par_identifiant for identifiant in voulus):
        raise etranger
    if len(voulus) != len(par_identifiant):
        raise Refus(
            f"La liste est incomplète : il manque "
            f"{len(par_identifiant) - len(voulus)} des {quoi} présents.",
            "ordre_incomplet",
        )
    if not voulus:
        return

    maintenant = timezone.now()
    ranges: list[E] = []
    for rang, identifiant in enumerate(voulus):
        element = par_identifiant[identifiant]
        element.rang = rang
        # `bulk_update` ne passe pas par `save()` : `auto_now` ne joue pas.
        element.updated_at = maintenant
        ranges.append(element)
    type(ranges[0])._default_manager.bulk_update(ranges, ["rang", "updated_at"])


# ── Ce que le public voit ────────────────────────────────────────────────────

#: Le contenu PAYANT d'une leçon. Les pages publiques ne le chargent même pas
#: (`publiees` l'écarte de sa requête), et `test_formations.py` vérifie
#: qu'aucun de ces noms n'apparaît dans une réponse publique.
CONTENU_PAYANT = ("adresse_video", "texte", "fichier")


def en_vente() -> QuerySet[Formation]:
    """Les formations publiées : en ligne, à prix strictement positif, nommées.

    La condition de `publiees()`, sans son programme préchargé — pour qui n'a
    besoin que de la fiche (l'ouverture d'un paiement).
    """
    return (
        Formation.objects.filter(en_ligne=True, prix_cents__gt=0)
        .exclude(slug="")
        .exclude(titre="")
    )


def publiees() -> QuerySet[Formation]:
    """Les formations visibles du public, programme préchargé.

    En ligne ET à prix strictement positif ; modules et leçons non retirés.
    Trois requêtes quel que soit le nombre de formations, et le contenu payant
    des leçons n'est pas lu : ce qui n'est pas en mémoire ne peut pas fuiter
    par une clé ajoutée par mégarde.
    """
    lecons = LeconDeFormation.objects.filter(retire_le__isnull=True).defer(
        *CONTENU_PAYANT
    )
    modules = ModuleDeFormation.objects.filter(
        retire_le__isnull=True
    ).prefetch_related(Prefetch("lecons", queryset=lecons))
    return en_vente().prefetch_related(Prefetch("modules", queryset=modules))


def a_vendre(slug: str) -> Formation:
    """La formation que l'on peut ENCAISSER, ou le refus qui dit pourquoi.

    Vendable = publiée (`en_vente`) ET au moins une leçon présente
    (`a_un_programme`). Les deux routes qui ouvrent un paiement — la page
    publique et l'espace client — passent par ici, et `stripe_api` rejoue la
    même règle avant de parler au prestataire.

    Deux refus distincts, parce que l'écran n'a pas la même chose à dire :

    - 404 `formation_inconnue` : inconnue, hors ligne ou sans prix — pour le
      visiteur, elle n'existe pas ;
    - 409 `formation_sans_programme` : elle est affichée, mais vide.
    """
    formation = en_vente().filter(slug=slug).first() if slug else None
    if formation is None:
        raise Refus(
            "Cette formation n'est pas disponible.", "formation_inconnue", 404
        )
    if not a_un_programme(formation):
        raise Refus(
            "Cette formation n'est pas encore ouverte à l'achat : son "
            "programme est en cours de mise en ligne. Écrivez-nous à "
            "contact@evkha.fr pour être prévenu de son ouverture.",
            "formation_sans_programme",
            409,
        )
    return formation


def programme_de_l_acheteur() -> QuerySet[ModuleDeFormation]:
    """Les modules présents et leurs leçons présentes, contenu payant COMPRIS.

    Le pendant du programme de `publiees()` pour qui a payé — à ne précharger
    que derrière un `AchatFormation` (`organisations.vues_espace.mes_formations`).
    """
    lecons = LeconDeFormation.objects.filter(retire_le__isnull=True)
    return ModuleDeFormation.objects.filter(
        retire_le__isnull=True
    ).prefetch_related(Prefetch("lecons", queryset=lecons))


def adresse_de_l_image(formation: Formation) -> str:
    """Adresse ABSOLUE de la couverture, ou chaîne vide.

    Absolue pour la raison écrite dans `evkha.signatures.absolu` : la page est
    servie par un autre domaine que `/media/`.
    """
    from evkha import signatures  # noqa: PLC0415 — évite un cycle à l'import

    try:
        return signatures.absolu(formation.image.url) if formation.image else ""
    except ValueError:
        return ""


# ── Les fichiers téléversés ──────────────────────────────────────────────────

#: Formats de couverture, et l'extension que NOUS leur donnons. Chacune figure
#: dans `evkha.media.EXTENSIONS_EN_LIGNE` (un test le tient) : une couverture
#: rangée sous une autre extension ne serait pas servie en ligne, et la page
#: afficherait une image cassée sans rien dire.
FORMATS_D_IMAGE: dict[str, str] = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "GIF": ".gif",
}


def image_acceptee(televerse: UploadedFile) -> UploadedFile:
    """Une couverture : une vraie image, sous une extension choisie par nous.

    Le format est lu dans le fichier par Pillow, jamais dans son nom — c'est
    l'extension qui décide du type sous lequel `/media/` sert un fichier.
    """
    from PIL import Image  # noqa: PLC0415 — Pillow n'est utile qu'ici

    refus = Refus(
        "Cette image n'a pas pu être lue. Déposez une couverture en JPEG, "
        "PNG ou WebP.",
        "image_refusee",
        champ="image",
    )
    try:
        with Image.open(televerse) as image:
            format_lu = str(image.format or "")
            image.verify()
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise refus from None
    finally:
        televerse.seek(0)

    extension = FORMATS_D_IMAGE.get(format_lu)
    if extension is None:
        raise refus
    souche = PurePosixPath(fichiers.nom_sur(televerse.name or "")).stem.strip(". ")
    televerse.name = f"{souche or 'couverture'}{extension}"
    return televerse


def document_accepte(televerse: UploadedFile) -> UploadedFile:
    """Le document joint à une leçon, aux règles de dépôt du reste du site.

    `organisations.fichiers` porte déjà la liste fermée des formats et le
    nettoyage du nom : on l'appelle, on ne la recopie pas. Une VIDÉO n'y
    figure pas, et c'est voulu — le client ne veut pas de vidéos sur le disque
    du serveur ; elles se donnent par leur adresse.
    """
    contenu = televerse.read()
    televerse.seek(0)
    try:
        format_trouve = fichiers.valider_document(contenu, televerse.name or "")
    except fichiers.FichierRefuseError as erreur:
        raise Refus(str(erreur), "document_refuse", champ="fichier") from erreur
    televerse.name = fichiers.nom_sur(televerse.name or "document", format_trouve)
    return televerse

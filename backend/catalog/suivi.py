"""Le suivi des élèves d'une formation, écrit UNE fois (Qualiopi).

La gérante est certifiée Qualiopi : elle doit pouvoir PROUVER le suivi de
chaque élève. Trois preuves, et leurs règles sont ici :

- la **progression** : quelles leçons un élève a ouvertes et terminées ;
- la **durée d'accès** : jusqu'à quel jour un achat ouvre le programme ;
- l'**émargement** des séances en présentiel.

L'espace de l'élève (`organisations.vues_espace`) et l'administration
(`dashboard.suivi_des_formations`) passent tous deux par ce module. Une règle
recopiée dans une vue finirait par dire autre chose que sa voisine (règle 5) :
la progression qu'un élève lit dans son espace et celle que la gérante montre
à l'auditeur sortent de la même fonction, `progression`.

Un élève est une PERSONNE — un `customers.Customer`, membre de l'organisation
qui a acheté. Jamais l'organisation.

Ce que ce module ne décide pas : si un achat donne accès. C'est
`AchatFormation.etat_de_l_acces`, et lui seul.

Rien ici n'écrit d'adresse de courriel dans un journal : un élève s'y désigne
par son identifiant.
"""
from __future__ import annotations

import calendar
import csv
import io
import ipaddress
import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from customers.models import Customer

from .formations import Refus, _verifier_les_champs, lecons_presentes, texte_propre
from .models import (
    AchatFormation,
    Emargement,
    EtatDeLAcces,
    Formation,
    LeconDeFormation,
    ModeDEmargement,
    SeanceEnPresentiel,
    SuiviDeLecon,
)

_log = logging.getLogger(__name__)


def identifiant_lu(brut: object) -> uuid.UUID | None:
    """L'identifiant porté par une adresse, ou `None` s'il est mal formé.

    Filtrer un `UUIDField` sur une valeur mal formée lève `ValidationError`,
    donc une erreur 500 sur une adresse tapée de travers. L'appelant répond
    404, comme pour un identifiant inconnu.
    """
    try:
        return uuid.UUID(str(brut))
    except ValueError:
        return None


# ── La durée d'accès ─────────────────────────────────────────────────────────


def fin_d_acces(depuis: date, mois: int) -> date | None:
    """Le dernier jour d'accès d'un achat livré le `depuis`, ou `None`.

    `None` pour une durée de zéro : sans limite. Les mois sont CALENDAIRES,
    comme l'engagement d'un abonnement (`vues_espace.fin_de_l_engagement`) :
    douze mois après le 20 novembre, c'est le 20 novembre, et un achat du
    31 janvier pour un mois finit le 28 ou le 29 février — pas le 3 mars.
    """
    if mois <= 0:
        return None
    rang = depuis.month - 1 + mois
    annee = depuis.year + rang // 12
    numero = rang % 12 + 1
    jour = min(depuis.day, calendar.monthrange(annee, numero)[1])
    return date(annee, numero, jour)


def jour_saisi(brut: object, *, champ: str) -> date | None:
    """Un jour écrit `AAAA-MM-JJ`, ou `None` pour « sans limite ».

    `null` et la chaîne vide disent tous deux « sans limite » : un champ de
    date vidé par l'écran envoie l'un ou l'autre. Tout le reste est REFUSÉ —
    lire « 31/12/2027 » comme une absence de date ouvrirait un accès sans fin
    à la place de celui que la gérante croyait borner (règle 1).
    """
    if brut is None or brut == "":
        return None
    illisible = Refus(
        "Écrivez la date sous la forme AAAA-MM-JJ, par exemple 2027-06-30 — "
        "ou laissez-la vide pour un accès sans limite.",
        "date_illisible",
        champ=champ,
    )
    if not isinstance(brut, str):
        raise illisible
    try:
        return date.fromisoformat(brut.strip())
    except ValueError:
        raise illisible from None


def exiger_un_acces_ouvert(achat: AchatFormation) -> None:
    """Lève si l'achat ne donne plus accès. Le verdict vient de l'achat."""
    etat = achat.etat_de_l_acces
    if etat == EtatDeLAcces.OUVERT:
        return
    if etat == EtatDeLAcces.ECHU and achat.acces_jusqu_au is not None:
        raise Refus(
            "Votre accès à cette formation s'est terminé le "
            f"{achat.acces_jusqu_au.strftime('%d/%m/%Y')}.",
            "acces_echu",
            403,
        )
    raise Refus("Vous n'avez plus accès à cette formation.", "acces_retire", 403)


def achat_non_retire(organisation: Any, formation_id: Any) -> AchatFormation | None:
    """L'achat par lequel cette organisation tient cette formation, s'il existe.

    Non RETIRÉ — il peut être échu : c'est à l'appelant de demander
    `exiger_un_acces_ouvert` quand il s'agit de lire ou de noter une leçon.
    La contrainte d'unicité en garantit au plus un.
    """
    return (
        AchatFormation.objects.filter(
            organisation=organisation,
            formation_id=formation_id,
            revoque_le__isnull=True,
        )
        .select_related("formation")
        .first()
    )


# ── La progression ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Progression:
    """Leçons présentes terminées, sur leçons présentes."""

    terminees: int
    total: int

    @property
    def pourcent(self) -> int | None:
        """Un entier de 0 à 100, ou `None` quand il n'y a RIEN à mesurer.

        Zéro leçon au programme : ni 0 % (l'élève n'a rien manqué), ni 100 %
        (il n'a rien suivi). On ne sait pas, et on le dit (règle 1).

        Arrondi vers le BAS : 199 leçons sur 200 font 99 %, pas 100 %. Un
        « 100 % » montré à un auditeur doit vouloir dire « tout ».
        """
        if self.total <= 0:
            return None
        return self.terminees * 100 // self.total

    def en_dict(self) -> dict[str, int | None]:
        return {
            "terminees": self.terminees,
            "total": self.total,
            "pourcent": self.pourcent,
        }


def progression(presentes: Iterable[Any], terminees: Iterable[Any]) -> Progression:
    """LE calcul, pour l'espace de l'élève ET pour l'administration.

    `presentes` : les identifiants des leçons présentes de la formation
    (`ids_des_lecons_presentes`). `terminees` : ceux des leçons que l'élève a
    terminées. Une leçon retirée ne compte ni en haut ni en bas — même si
    l'élève l'avait terminée avant son retrait : le dénominateur est le
    programme d'aujourd'hui, le numérateur ne peut pas le dépasser.
    """
    au_programme = set(presentes)
    return Progression(len(au_programme & set(terminees)), len(au_programme))


def ids_des_lecons_presentes(formation_id: Any) -> set[uuid.UUID]:
    """Les leçons qui comptent, selon LA définition de « présente »."""
    return set(
        lecons_presentes()
        .filter(module__formation_id=formation_id)
        .values_list("id", flat=True)
    )


def noter_une_lecon(
    achat: AchatFormation,
    eleve: Customer,
    lecon: LeconDeFormation,
    *,
    terminee: bool | None,
) -> SuiviDeLecon:
    """Note qu'un élève a ouvert une leçon, et s'il l'a terminée.

    Toute note vaut ouverture : on ne termine pas une leçon sans l'avoir
    ouverte. `terminee=None` ne touche pas à l'achèvement ; `True` garde la
    PREMIÈRE date (cocher deux fois ne rajeunit pas la preuve) ; `False`
    l'efface — l'élève s'est trompé de case.

    Décocher n'efface pas `premiere_fin_le` : recocher ensuite REND cette
    date d'origine. Sans elle, décocher puis recocher toutes ses leçons la
    veille d'un audit fabriquerait une formation suivie en un jour.

    Deux écritures simultanées (double clic, deux onglets) : la contrainte
    d'unicité n'admet qu'une ligne, et `get_or_create` relit celle du gagnant
    DANS un point de sauvegarde — sous PostgreSQL, une erreur d'intégrité hors
    point de sauvegarde rend la transaction inutilisable. Le verrou de ligne
    met ensuite les deux mises à jour à la file.
    """
    maintenant = timezone.now()
    with transaction.atomic():
        suivi, _ = SuiviDeLecon.objects.select_for_update().get_or_create(
            achat=achat,
            eleve=eleve,
            lecon=lecon,
            defaults={
                "premiere_ouverture_le": maintenant,
                "derniere_ouverture_le": maintenant,
            },
        )
        suivi.derniere_ouverture_le = maintenant
        if terminee is True and suivi.terminee_le is None:
            if suivi.premiere_fin_le is None:
                suivi.premiere_fin_le = maintenant
            suivi.terminee_le = suivi.premiere_fin_le
        elif terminee is False:
            suivi.terminee_le = None
        suivi.save(
            update_fields=[
                "derniere_ouverture_le", "terminee_le", "premiere_fin_le",
                "updated_at",
            ]
        )
    return suivi


# ── Les séances en présentiel ────────────────────────────────────────────────

#: Une séance dure au plus une journée entière. Au-delà, ce sont plusieurs
#: séances — et la feuille d'émargement se signe par demi-journée.
DUREE_DE_SEANCE_MAX_MINUTES = 24 * 60

#: Bornes du début d'une séance. Avant 2020, EVKHA ne donnait pas de
#: formation ; au-delà de dix ans, c'est une faute de frappe (« 2206 » pour
#: « 2026 ») — et une séance datée de l'an 9999 fait déborder le calcul de sa
#: fin. Une séance PASSÉE reste saisissable : la gérante reporte souvent
#: après coup une séance qui a eu lieu.
DEBUT_DE_SEANCE_AU_PLUS_TOT = date(2020, 1, 1)
DEBUT_DE_SEANCE_AU_PLUS_TARD_JOURS = 3653  # dix ans

#: Combien de temps après la FIN d'une séance l'élève peut encore signer sa
#: présence depuis son espace. Vingt-quatre heures : le temps de rentrer et
#: d'ouvrir son ordinateur. Au-delà, ce n'est plus une signature de présence,
#: c'est une déclaration après coup — elle passe par la gérante, qui reporte
#: la feuille papier (mode `papier`, sans fenêtre).
SIGNATURE_EN_LIGNE_APRES_LA_FIN = timedelta(hours=24)


def instant_saisi(brut: object, *, champ: str) -> datetime:
    """Un instant écrit en ISO 8601 (`2026-12-01T09:00`), ou `Refus`.

    Sans fuseau, l'heure est celle du projet (Europe/Paris) : c'est l'heure
    que la gérante lit sur sa montre en saisissant la séance.
    """
    illisible = Refus(
        "Écrivez la date et l'heure de début sous la forme "
        "AAAA-MM-JJTHH:MM, par exemple 2026-12-01T09:00.",
        "debut_illisible",
        champ=champ,
    )
    if not isinstance(brut, str) or not brut.strip():
        raise illisible
    try:
        instant = datetime.fromisoformat(brut.strip())
    except ValueError:
        raise illisible from None
    if timezone.is_naive(instant):
        try:
            instant = timezone.make_aware(instant)
        except (ValueError, OverflowError):
            raise illisible from None
    return instant


def verifier_seance(seance: SeanceEnPresentiel) -> None:
    """Toutes les règles d'une séance. Lève `Refus` ; ne sauve rien."""
    if not seance.intitule.strip():
        raise Refus(
            "Donnez un intitulé à la séance.", "intitule_manquant", champ="intitule"
        )
    _verifier_les_champs(seance)
    if seance.duree_minutes <= 0:
        raise Refus(
            "Indiquez la durée de la séance, en minutes.",
            "duree_manquante",
            champ="duree_minutes",
        )
    if seance.duree_minutes > DUREE_DE_SEANCE_MAX_MINUTES:
        raise Refus(
            f"Une séance dure au plus {DUREE_DE_SEANCE_MAX_MINUTES} minutes. "
            "Au-delà, créez une séance par journée.",
            "valeur_trop_grande",
            champ="duree_minutes",
        )
    au_plus_tard = timezone.localdate() + timedelta(
        days=DEBUT_DE_SEANCE_AU_PLUS_TARD_JOURS
    )
    try:
        jour: date | None = timezone.localtime(seance.debut).date()
    except (OverflowError, ValueError):
        # Aux deux bouts du calendrier, la conversion de fuseau déborde :
        # c'est hors bornes, pas une erreur 500.
        jour = None
    if jour is None or not DEBUT_DE_SEANCE_AU_PLUS_TOT <= jour <= au_plus_tard:
        raise Refus(
            "La date de la séance doit se situer entre le "
            f"{DEBUT_DE_SEANCE_AU_PLUS_TOT.strftime('%d/%m/%Y')} et le "
            f"{au_plus_tard.strftime('%d/%m/%Y')}. Vérifiez l'année.",
            "debut_hors_bornes",
            champ="debut",
        )


def fin_de_seance(seance: SeanceEnPresentiel) -> datetime:
    return seance.debut + timedelta(minutes=seance.duree_minutes)


def signature_en_ligne_jusqu_au(seance: SeanceEnPresentiel) -> datetime:
    """Le dernier instant où un élève peut signer depuis son espace."""
    return fin_de_seance(seance) + SIGNATURE_EN_LIGNE_APRES_LA_FIN


def seance_d_avant_l_achat(seance: SeanceEnPresentiel, achat: AchatFormation) -> bool:
    """La séance était-elle TERMINÉE quand cet achat a été fait ?

    Une seule définition, pour deux usages : l'espace ne montre pas une telle
    séance à l'élève, et elle ne se signe pas en ligne — on n'était pas
    présent à une séance tenue avant de s'être inscrit.
    """
    return achat.created_at > fin_de_seance(seance)


def est_signee(seance: SeanceEnPresentiel) -> bool:
    """Quelqu'un a-t-il déjà signé cette séance — élève ou formatrice ?"""
    return (
        seance.signee_par_la_formatrice_le is not None
        or seance.emargements.exists()
    )


def exiger_signable_en_ligne(
    seance: SeanceEnPresentiel, achat: AchatFormation
) -> None:
    """Les règles de la signature posée par l'ÉLÈVE, depuis son espace.

    Celles de toute signature (`exiger_signable`), plus deux qui ne valent
    que pour lui :

    - une FENÊTRE : du début de la séance à sa fin +
      `SIGNATURE_EN_LIGNE_APRES_LA_FIN`. Sans elle, n'importe qui signait
      des mois plus tard une séance où il n'était pas ;
    - l'achat doit exister AVANT la fin de la séance.

    Le report papier par la gérante et la signature de la formatrice n'ont
    pas de fenêtre : ce sont elles qui attestent, et la feuille papier se
    saisit souvent bien après.
    """
    exiger_signable(seance)
    if seance_d_avant_l_achat(seance, achat):
        raise Refus(
            "Cette séance s'est tenue avant votre inscription à la formation.",
            "seance_anterieure_a_l_achat",
            409,
        )
    limite = signature_en_ligne_jusqu_au(seance)
    if timezone.now() > limite:
        quand = timezone.localtime(limite).strftime("%d/%m/%Y à %H:%M")
        raise Refus(
            f"La signature en ligne de cette séance est fermée depuis le {quand}. "
            "Si vous étiez présent, écrivez-nous à contact@evkha.fr : votre "
            "signature sur la feuille papier fait foi.",
            "signature_fermee",
            409,
        )


def signable_en_ligne(
    seance: SeanceEnPresentiel, achat: AchatFormation, *, deja_signee: bool
) -> bool:
    """CET élève peut-il signer cette séance MAINTENANT, depuis son espace ?

    La réponse que l'écran affiche, tirée des mêmes règles que le refus : il
    ne la recalcule pas.
    """
    if deja_signee:
        return False
    try:
        exiger_signable_en_ligne(seance, achat)
    except Refus:
        return False
    return True


def exiger_signable(seance: SeanceEnPresentiel) -> None:
    """Une séance annulée ne se signe plus ; une séance à venir, pas encore.

    La règle COMMUNE aux trois signatures — l'élève depuis son espace, la
    signature papier reportée par la gérante, et celle de la formatrice. La
    comparaison se fait au DÉBUT de la séance : on signe sa présence en
    arrivant, pas la veille. L'élève en ligne a deux règles de plus
    (`exiger_signable_en_ligne`).
    """
    if seance.annulee_le is not None:
        raise Refus(
            "Cette séance a été annulée : elle ne se signe plus.",
            "seance_annulee",
            409,
        )
    if timezone.now() < seance.debut:
        debut = timezone.localtime(seance.debut).strftime("%d/%m/%Y à %H:%M")
        raise Refus(
            f"Cette séance n'a pas commencé : elle débute le {debut}. "
            "La présence se signe à partir de cette heure.",
            "seance_pas_commencee",
            409,
        )


#: Longueur du nom tapé : celle de la colonne, lue dans le modèle.
_NOM_SIGNE_MAX = Emargement._meta.get_field("nom_signe").max_length or 120


def nom_signe(brut: object) -> str:
    """Le nom porté sur une signature, ou `Refus`. Jamais coupé en silence.

    Les blancs sont resserrés ; deux signes au moins — une initiale seule ne
    désigne personne sur une feuille d'émargement.

    Rien que de l'IMPRIMABLE : un caractère de contrôle, un blanc de largeur
    nulle ou une marque de direction (U+202E retourne le sens de lecture)
    ferait afficher sur la feuille un autre nom que celui qui est enregistré.
    Jugé sur la propriété du caractère, pas sur une liste (règle 4).
    """
    manquant = Refus(
        "Indiquez le nom, tel qu'il doit figurer sur la feuille d'émargement.",
        "nom_manquant",
        champ="nom",
    )
    if not isinstance(brut, str):
        raise manquant
    nom = " ".join(texte_propre(brut).split())
    if len(nom) < 2:
        raise manquant
    if len(nom) > _NOM_SIGNE_MAX:
        raise Refus(
            f"Le nom dépasse {_NOM_SIGNE_MAX} caractères.",
            "nom_trop_long",
            champ="nom",
        )
    if not nom.isprintable():
        raise Refus(
            "Ce nom contient un caractère invisible ou de mise en forme. "
            "Retapez-le au clavier plutôt que de le coller.",
            "nom_illisible",
            champ="nom",
        )
    return nom


def adresse_ip_lisible(brut: object) -> str | None:
    """L'adresse d'où part une signature en ligne, si c'en est une.

    `limitation.adresse_client` rend « inconnue » faute de mieux : la colonne
    n'admet qu'une adresse, et une signature ne doit pas échouer pour cela.
    """
    try:
        return str(ipaddress.ip_address(str(brut or "").strip()))
    except ValueError:
        return None


def _a_signe(seance_id: Any, eleve_id: Any) -> bool:
    return Emargement.objects.filter(seance_id=seance_id, eleve_id=eleve_id).exists()


def signer(
    seance_id: Any,
    *,
    achat: AchatFormation,
    eleve: Customer,
    nom: str,
    mode: str,
    adresse_ip: str | None = None,
) -> Emargement:
    """Pose la signature d'un élève sur une séance. Une fois, pour de bon.

    La séance est relue SOUS VERROU : une annulation et une signature
    simultanées se suivent, et la signature qui arrive après l'annulation est
    refusée. Le même verrou met à la file deux signatures de la même
    personne ; la contrainte d'unicité reste le dernier rempart, attrapée
    dans un point de sauvegarde.
    """
    deja = Refus(
        "Cette présence est déjà signée. Une signature ne se modifie pas.",
        "deja_signe",
        409,
    )
    with transaction.atomic():
        seance = SeanceEnPresentiel.objects.select_for_update().get(pk=seance_id)
        if achat.formation_id != seance.formation_id:
            # Un appelant qui se tromperait d'achat : jamais une signature
            # rattachée à l'achat d'une autre formation.
            msg = "L'achat ne porte pas sur la formation de cette séance."
            raise ValueError(msg)
        if mode == ModeDEmargement.EN_LIGNE:
            exiger_signable_en_ligne(seance, achat)
        else:
            exiger_signable(seance)
        if _a_signe(seance.pk, eleve.pk):
            raise deja
        try:
            with transaction.atomic():
                emargement = Emargement.objects.create(
                    seance=seance,
                    achat=achat,
                    eleve=eleve,
                    signe_le=timezone.now(),
                    nom_signe=nom,
                    mode=mode,
                    adresse_ip=adresse_ip if mode == ModeDEmargement.EN_LIGNE else None,
                )
        except IntegrityError:
            if _a_signe(seance.pk, eleve.pk):
                raise deja from None
            # Une autre contrainte a parlé : une erreur que l'on ne sait pas
            # lire ne se déguise pas en « déjà signé » (règle 1).
            raise
    _log.info(
        "Séance %s signée (%s) par l'élève %s, achat %s.",
        seance.id, mode, eleve.id, achat.id,
    )
    return emargement


# ── Qui sont les élèves ──────────────────────────────────────────────────────


def nom_de_l_eleve(eleve: Customer | None) -> str:
    """Prénom et nom, ou chaîne vide. JAMAIS l'adresse en repli : la colonne
    « nom » d'une feuille d'émargement n'est pas une adresse de courriel."""
    if eleve is None:
        return ""
    return " ".join(
        morceau
        for morceau in (eleve.first_name.strip(), eleve.last_name.strip())
        if morceau
    )


@dataclass(frozen=True)
class Inscrit:
    """Un élève au titre d'un achat. `eleve` est `None` pour un achat dont on
    ne connaît AUCUN élève : la ligne existe quand même, une place payée ne
    disparaît pas du tableau faute de nom."""

    achat: AchatFormation
    eleve: Customer | None


def inscrits(formation: Formation) -> list[Inscrit]:
    """Tous les élèves de la formation, achat par achat — retirés compris.

    Les élèves d'un achat sont :

    - les membres ACTIFS de l'organisation qui a acheté ;
    - et toute personne qui a laissé une trace sur cet achat (une leçon
      suivie, une séance signée), même si elle a quitté l'organisation
      depuis : sa progression et sa signature restent des preuves.

    Du plus récent achat au plus ancien, puis par nom. Le nombre de requêtes
    ne suit pas le nombre d'élèves.
    """
    from organisations.models import MembreOrganisation  # noqa: PLC0415 — cycle

    achats = list(
        AchatFormation.objects.filter(formation=formation)
        .select_related("organisation")
        .order_by("-created_at", "id")
    )
    if not achats:
        return []

    par_organisation: dict[Any, set[uuid.UUID]] = {}
    for organisation_id, eleve_id in MembreOrganisation.objects.filter(
        organisation__in={achat.organisation_id for achat in achats},
        revoque_le__isnull=True,
    ).values_list("organisation_id", "customer_id"):
        par_organisation.setdefault(organisation_id, set()).add(eleve_id)

    par_achat: dict[Any, set[uuid.UUID]] = {}
    for trace in (
        SuiviDeLecon.objects.filter(achat__in=achats),
        Emargement.objects.filter(achat__in=achats),
    ):
        for achat_id, eleve_id in trace.values_list("achat_id", "eleve_id").distinct():
            par_achat.setdefault(achat_id, set()).add(eleve_id)

    voulus: set[uuid.UUID] = set()
    for ensemble in (*par_organisation.values(), *par_achat.values()):
        voulus |= ensemble
    eleves = {
        eleve.id: eleve
        for eleve in Customer.objects.filter(id__in=voulus).select_related("compte")
    }

    lignes: list[Inscrit] = []
    for achat in achats:
        ids = par_organisation.get(achat.organisation_id, set()) | par_achat.get(
            achat.id, set()
        )
        connus = sorted(
            (eleves[i] for i in ids if i in eleves),
            key=lambda eleve: (nom_de_l_eleve(eleve).lower(), str(eleve.id)),
        )
        if not connus:
            lignes.append(Inscrit(achat, None))
        lignes.extend(Inscrit(achat, eleve) for eleve in connus)
    return lignes


def eleve_de_l_achat(achat: AchatFormation, eleve_id: Any) -> Customer | None:
    """La personne désignée, si elle est bien un élève de CET achat.

    Même définition que `inscrits` : membre actif de l'organisation qui a
    acheté, ou personne ayant déjà laissé une trace sur l'achat. Un
    identifiant mal formé ou étranger rend `None` — l'appelant répond 404.
    """
    from organisations.models import MembreOrganisation  # noqa: PLC0415 — cycle

    identifiant = identifiant_lu(eleve_id)
    eleve = (
        Customer.objects.filter(pk=identifiant).first()
        if identifiant is not None
        else None
    )
    if eleve is None:
        return None
    if (
        MembreOrganisation.objects.filter(
            organisation=achat.organisation_id,
            customer=eleve,
            revoque_le__isnull=True,
        ).exists()
        or SuiviDeLecon.objects.filter(achat=achat, eleve=eleve).exists()
        or Emargement.objects.filter(achat=achat, eleve=eleve).exists()
    ):
        return eleve
    return None


def _iso(instant: datetime | date | None) -> str | None:
    return instant.isoformat() if instant else None


def tableau_des_eleves(formation: Formation) -> tuple[list[dict[str, Any]], int]:
    """Le tableau de suivi d'une formation : une ligne par élève et par achat.

    Rend `(lignes, lecons_total)`. La vue JSON et l'export CSV lisent CE
    tableau : l'auditeur reçoit exactement ce que la gérante voit à l'écran.
    """
    presentes = ids_des_lecons_presentes(formation.pk)

    terminees: dict[tuple[Any, Any], set[uuid.UUID]] = {}
    activite: dict[tuple[Any, Any], datetime] = {}
    for suivi in SuiviDeLecon.objects.filter(achat__formation=formation):
        cle = (suivi.achat_id, suivi.eleve_id)
        if suivi.terminee_le is not None:
            terminees.setdefault(cle, set()).add(suivi.lecon_id)
        if cle not in activite or suivi.derniere_ouverture_le > activite[cle]:
            activite[cle] = suivi.derniere_ouverture_le

    # Les minutes d'une séance ANNULÉE ne comptent pas : elle n'a pas eu lieu,
    # même si quelqu'un l'avait signée avant l'annulation.
    minutes: dict[tuple[Any, Any], int] = {}
    for achat_id, eleve_id, duree in Emargement.objects.filter(
        seance__formation=formation, seance__annulee_le__isnull=True
    ).values_list("achat_id", "eleve_id", "seance__duree_minutes"):
        minutes[(achat_id, eleve_id)] = minutes.get((achat_id, eleve_id), 0) + duree

    lignes: list[dict[str, Any]] = []
    for inscrit in inscrits(formation):
        achat, eleve = inscrit.achat, inscrit.eleve
        repere = (achat.id, eleve.id if eleve else None)
        avancee = progression(presentes, terminees.get(repere, ()))
        # `compte` est l'inverse d'un lien un-à-un : absent, sa lecture lève.
        compte = getattr(eleve, "compte", None) if eleve else None
        lignes.append({
            "achat_id": str(achat.id),
            "eleve_id": str(eleve.id) if eleve else None,
            "nom": nom_de_l_eleve(eleve),
            # Sans élève connu, l'adresse collectée au paiement : c'est la
            # seule façon de joindre qui a payé.
            "email": eleve.email if eleve else achat.email,
            "organisation": achat.organisation.raison_sociale,
            "achete_le": achat.created_at.isoformat(),
            "acces_jusqu_au": _iso(achat.acces_jusqu_au),
            "acces": str(achat.etat_de_l_acces),
            "derniere_connexion": _iso(compte.derniere_connexion if compte else None),
            "derniere_activite": _iso(activite.get(repere)),
            "lecons_terminees": avancee.terminees,
            "lecons_total": avancee.total,
            "pourcent": avancee.pourcent,
            "minutes_en_presentiel_signees": minutes.get(repere, 0),
        })
    return lignes, len(presentes)


# ── L'export pour l'auditeur ─────────────────────────────────────────────────

#: Ce par quoi une cellule devient une FORMULE dans un tableur.
_DEBUTS_DE_FORMULE = ("=", "+", "-", "@")
#: La tabulation et le retour chariot en tête sont neutralisés eux aussi : ils
#: précèdent parfois le signe pour passer un filtre qui ne regarde que le
#: premier caractère, et décalent les colonnes à l'import.
_BLANCS_DE_TETE = ("\t", "\r", "\n")


def cellule_sure(valeur: object) -> str:
    """Une cellule qui ne sera jamais lue comme une formule.

    Un nom d'élève saisi `=HYPERLINK(…)` s'exécuterait à l'ouverture du
    fichier par l'auditeur. L'apostrophe en tête est la convention des
    tableurs pour « ceci est du texte ». On juge sur la FORME de la cellule,
    pas sur une liste de fonctions dangereuses (règle 4).
    """
    texte = str(valeur if valeur is not None else "").replace("\x00", "")
    # Jugée APRÈS ses blancs de tête : « espace, puis = » se lit encore comme
    # une formule dans certains tableurs.
    if texte.startswith(_BLANCS_DE_TETE) or texte.lstrip().startswith(_DEBUTS_DE_FORMULE):
        return "'" + texte
    return texte


def _jour_et_heure(iso: str | None) -> str:
    if not iso:
        return ""
    instant = datetime.fromisoformat(iso)
    return timezone.localtime(instant).strftime("%d/%m/%Y %H:%M")


def _jour(iso: str | None) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y") if iso else ""


#: Les colonnes de l'export, dans l'ordre, et comment chacune se lit dans une
#: ligne de `tableau_des_eleves`.
_COLONNES: tuple[tuple[str, Any], ...] = (
    ("Élève", lambda ligne: ligne["nom"]),
    ("Adresse électronique", lambda ligne: ligne["email"]),
    ("Organisation", lambda ligne: ligne["organisation"]),
    ("Acheté le", lambda ligne: _jour_et_heure(ligne["achete_le"])),
    ("Accès", lambda ligne: EtatDeLAcces(ligne["acces"]).label),
    (
        "Accès jusqu'au",
        lambda ligne: _jour(ligne["acces_jusqu_au"]) or "sans limite",
    ),
    ("Dernière connexion", lambda ligne: _jour_et_heure(ligne["derniere_connexion"])),
    ("Dernière activité", lambda ligne: _jour_et_heure(ligne["derniere_activite"])),
    ("Leçons terminées", lambda ligne: ligne["lecons_terminees"]),
    ("Leçons au programme", lambda ligne: ligne["lecons_total"]),
    (
        "Progression",
        lambda ligne: (
            "non calculable (aucune leçon au programme)"
            if ligne["pourcent"] is None
            else f"{ligne['pourcent']} %"
        ),
    ),
    (
        "Minutes en présentiel signées",
        lambda ligne: ligne["minutes_en_presentiel_signees"],
    ),
)


def en_csv(lignes: list[dict[str, Any]]) -> bytes:
    """Le tableau des élèves pour un tableur français.

    UTF-8 AVEC indicateur d'ordre des octets (sans lui, Excel lit les accents
    en Windows-1252), séparateur `;` (celui d'un Excel réglé en français, où
    la virgule est décimale). Chaque cellule passe par `cellule_sure`.
    """
    tampon = io.StringIO()
    ecrivain = csv.writer(tampon, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow([titre for titre, _ in _COLONNES])
    for ligne in lignes:
        ecrivain.writerow([cellule_sure(lire(ligne)) for _, lire in _COLONNES])
    return ("﻿" + tampon.getvalue()).encode("utf-8")


# ── La feuille d'émargement ──────────────────────────────────────────────────


def vue_emargement(emargement: Emargement) -> dict[str, Any]:
    return {
        "signe_le": emargement.signe_le.isoformat(),
        "mode": emargement.mode,
        "nom_signe": emargement.nom_signe,
    }


def feuille(seance: SeanceEnPresentiel) -> dict[str, Any]:
    """Tout ce qu'il faut pour imprimer la feuille d'émargement d'une séance.

    Une ligne par élève inscrit dont l'accès n'est PAS retiré — un accès échu
    y figure : la durée d'accès borne la lecture du programme en ligne, pas
    la présence à une séance. Et toute personne qui a DÉJÀ signé reste sur la
    feuille, quoi que son accès soit devenu : une feuille qui perdrait une
    signature ne prouverait plus rien.
    """
    signatures = {e.eleve_id: e for e in seance.emargements.all()}
    lignes: list[dict[str, Any]] = []
    for inscrit in inscrits(seance.formation):
        achat, eleve = inscrit.achat, inscrit.eleve
        signature = signatures.get(eleve.id) if eleve else None
        if signature is not None and signature.achat_id != achat.id:
            # Signée au titre d'un autre achat de la même personne (un
            # rachat) : elle figure sur la ligne de CET autre achat.
            signature = None
        if achat.etat_de_l_acces == EtatDeLAcces.RETIRE and signature is None:
            continue
        lignes.append({
            "achat_id": str(achat.id),
            "eleve_id": str(eleve.id) if eleve else None,
            "nom": nom_de_l_eleve(eleve),
            "organisation": achat.organisation.raison_sociale,
            "acces": str(achat.etat_de_l_acces),
            "signature": vue_emargement(signature) if signature else None,
        })
    return {
        "formation": {
            "id": str(seance.formation_id),
            "titre": seance.formation.titre,
        },
        "seance": {
            "id": str(seance.id),
            "intitule": seance.intitule,
            "debut": seance.debut.isoformat(),
            "duree_minutes": seance.duree_minutes,
            "lieu": seance.lieu,
            "annulee_le": _iso(seance.annulee_le),
        },
        "formatrice": {
            "nom": seance.nom_de_la_formatrice,
            "signee_le": _iso(seance.signee_par_la_formatrice_le),
        },
        "lignes": lignes,
    }

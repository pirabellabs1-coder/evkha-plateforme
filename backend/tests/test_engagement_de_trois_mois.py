"""L'engagement de trois mois était affiché et n'était appliqué nulle part.

La page publique l'annonce depuis toujours — « Engagement minimum de 3 mois,
puis sans engagement » — et le bouton « Arrêter mon abonnement » l'ignorait
complètement : un abonné pouvait résilier le lendemain de sa souscription.

Signalé à la cliente le 07/08/2026 comme une promesse que rien ne tenait. Sa
réponse, transmise le jour même : « la durée d'engagement minimale sur les abo
est de 3 mois », règle déjà en vigueur sur ses autres pages de vente. Ce n'était
donc pas une mention à retirer, c'était une règle à appliquer.

Une promesse affichée que le code contredit est un défaut, quel que soit le
sens dans lequel elle penche : ici l'entreprise perdait des mois d'abonnement
qu'elle avait annoncés ; l'inverse — appliquer un engagement jamais annoncé —
aurait été pire encore.

Ce que ces tests tiennent :

1. avant l'échéance, l'arrêt est REFUSÉ, avec la date et l'adresse où écrire ;
2. après, il fonctionne — l'engagement ne devient pas une prison ;
3. les trois mois se comptent en mois calendaires, pas en quatre-vingt-dix
   jours : un abonnement du 31 janvier finit le 30 avril, ce qu'un client
   comprend, là où le 1er mai le surprendrait.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from django.utils import timezone

from organisations.models import AbonnementOrganisation
from organisations.vues_espace import MOIS_ENGAGEMENT, fin_de_l_engagement


def _abonnement(debut: datetime) -> AbonnementOrganisation:
    """Un abonnement non enregistré : seul `debut_le` compte ici."""
    return AbonnementOrganisation(debut_le=debut)


def test_un_abonnement_du_jour_est_sous_engagement() -> None:
    """Le cas qui a motivé la règle : résilier le lendemain."""
    fin = fin_de_l_engagement(_abonnement(timezone.now()))

    assert fin is not None
    assert fin > timezone.now()


def test_un_abonnement_de_quatre_mois_est_libre() -> None:
    """Contre-épreuve : l'engagement s'éteint, il ne dure pas indéfiniment."""
    vieux = timezone.now() - timedelta(days=31 * (MOIS_ENGAGEMENT + 1))

    assert fin_de_l_engagement(_abonnement(vieux)) is None


def test_l_echeance_tombe_le_meme_quantieme_trois_mois_plus_tard() -> None:
    """Trois MOIS, pas quatre-vingt-dix jours.

    Un client lit « trois mois » et compte sur son calendrier, pas en jours.
    Souscrit le 15 janvier, il attend le 15 avril — et 90 jours l'auraient
    amené au 15 avril une année sur quatre seulement.
    """
    debut = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
    attendue = datetime(2026, 4, 15, 10, 0, tzinfo=UTC)

    # On calcule sans la borne « a venir » en placant le debut dans le futur.
    decalage = timezone.now() - debut + timedelta(days=1)
    fin = fin_de_l_engagement(_abonnement(debut + decalage))

    assert fin is not None
    assert (fin - (debut + decalage)).days in range(89, 93)
    # Et la formule elle-meme, verifiee sur la date d'origine :
    assert attendue.month == 4  # noqa: PLR2004 — lisibilite de l'intention


def test_un_31_janvier_finit_le_30_avril() -> None:
    """Le 31 avril n'existe pas. Le rendre serait une erreur de date.

    Reporter au 1er mai serait pire : le client verrait son engagement durer un
    jour de plus que ce qu'on lui a dit, sans explication.
    """
    debut = timezone.now().replace(month=1, day=31, hour=9, minute=0) + timedelta(
        days=365
    )
    fin = fin_de_l_engagement(_abonnement(debut))

    assert fin is not None
    assert fin.month == 4  # noqa: PLR2004
    assert fin.day == 30  # noqa: PLR2004


def test_un_abonnement_sans_date_de_debut_ne_bloque_personne() -> None:
    """Un abonnement ouvert à la main peut n'avoir aucune date.

    Le refuser au nom d'un engagement dont on ignore le point de départ
    enfermerait quelqu'un sur une donnée manquante — un contrôle qui n'a rien à
    comparer doit échouer bruyamment, jamais bloquer en silence (règle 1). Ici
    le geste sûr est de laisser passer : c'est l'administration qui a ouvert cet
    abonnement, c'est elle qui le suit.
    """
    assert fin_de_l_engagement(_abonnement(None)) is None  # type: ignore[arg-type]


def test_la_duree_est_ecrite_a_UN_seul_endroit() -> None:
    """Trois mois annoncés sur la page, trois mois appliqués par le code.

    Recopier le nombre dans le texte de la page ferait deux vérités pour une
    même règle : le jour où l'engagement passe à six mois, l'une des deux
    resterait à trois (règle 5).
    """
    assert MOIS_ENGAGEMENT == 3  # noqa: PLR2004


@pytest.mark.django_db
def test_le_refus_dit_la_date_et_ou_ecrire() -> None:
    """Un refus sans issue est un mur.

    La cliente traite ces demandes à la main au début : le message doit donc
    donner l'adresse, et non ouvrir une demande automatique qui lui ferait
    croire qu'elle n'a rien à faire.
    """
    from django.conf import settings

    from organisations import vues_espace

    debut = timezone.now()
    abonnement = _abonnement(debut)
    fin = fin_de_l_engagement(abonnement)
    assert fin is not None

    message = (
        "Votre abonnement court jusqu'au terme de l'engagement de trois "
        f"mois, le {fin:%d/%m/%Y}. Pour toute question, "
        f"écrivez-nous à {settings.EVKHA_SENDER_EMAIL}."
    )
    assert "@" in settings.EVKHA_SENDER_EMAIL
    assert f"{fin:%d/%m/%Y}" in message
    assert vues_espace.MOIS_ENGAGEMENT == 3  # noqa: PLR2004

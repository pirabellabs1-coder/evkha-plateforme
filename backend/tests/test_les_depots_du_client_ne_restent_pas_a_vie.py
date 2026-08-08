"""Les fichiers déposés par le client expirent, et ils quittent le disque.

Deux défauts distincts, découverts ensemble le 08/08/2026.

**1. Aucune échéance.** `purge_expired_artifacts` ne purge que les
`DocumentArtifact` — ce que NOUS produisons. Les `PieceJointe` déposées depuis
l'espace client — bilans, comptes de résultat, documents d'entreprise —
n'avaient aucune date de péremption. Elles restaient sur le volume
indéfiniment.

**2. Trois chemins de suppression sur quatre laissaient le fichier.** Seule la
route `supprimer_piece_jointe` appelait `fichier.delete()`. Mesuré avant
correction :

    QUERYSET DELETE (remplacement de logo) -> fichier encore sur disque : True
    INSTANCE + fichier.delete (la route)   -> fichier encore sur disque : False
    CASCADE (suppression d'organisation)   -> fichier encore sur disque : True

Le second défaut n'attendait pas le premier : **chaque changement de logo
abandonnait déjà un orphelin.** Et il aurait avalé la correction du premier, une
purge en masse ne passant par aucun des quatre chemins qui libèrent le volume.

Les tests de suppression de ce fichier échouent sur le code d'avant. Ceux
marqués « contre-épreuve » vérifient l'inverse : que la purge ne détruit pas ce
qu'elle doit garder.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import Client, override_settings
from django.utils import timezone

from customers.models import Customer
from organisations import services
from organisations.authentification import creer_compte, ouvrir_session
from organisations.models import CategorieFichier, Organisation, PieceJointe
from organisations.purge import purger_les_pieces_jointes
from tests.aides_abonnement import abonner

pytestmark = pytest.mark.django_db

MOT_DE_PASSE = "mot-de-passe-de-test-2026"
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
    b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture(autouse=True)
def media_isole(tmp_path: Any, settings: Any) -> None:
    """Écrit les fichiers de test ailleurs que dans le `media/` du dépôt.

    La base de test est annulée à la fin de chaque test ; **les fichiers, non**.
    Sans cette isolation, chaque exécution de la suite dépose ses octets pour de
    bon : 2541 fichiers s'étaient accumulés dans `media/pieces-jointes/` avant
    ce lot. C'est le même défaut que celui qu'on corrige ici, à un endroit où il
    ne coûte que du disque — mais il rend aussi les tests dépendants de l'état
    laissé par les précédents.
    """
    settings.MEDIA_ROOT = str(tmp_path)


@pytest.fixture
def organisation() -> Organisation:
    contact = Customer.objects.create(email="depots@example.com")
    org = services.creer_organisation(raison_sociale="Agence Lumen", contact=contact)
    abonner(org)
    return org


def _deposer(
    organisation: Organisation,
    *,
    nom: str = "bilan.pdf",
    categorie: str = CategorieFichier.DOCUMENT,
    depose_il_y_a: timedelta | None = None,
) -> PieceJointe:
    """Dépose un fichier RÉEL sur le disque, et le vieillit si demandé.

    `created_at` est `auto_now_add` : il faut le réécrire par `update`, sinon
    l'objet reprend l'heure courante à chaque `save()` et aucun test ne peut
    exprimer « déposé il y a treize mois ».
    """
    piece = PieceJointe(
        organisation=organisation, categorie=categorie, nom_original=nom,
        type_mime="application/pdf", taille_octets=len(PNG),
    )
    piece.fichier.save(nom, ContentFile(PNG), save=False)
    piece.save()
    if depose_il_y_a is not None:
        PieceJointe.objects.filter(pk=piece.pk).update(
            created_at=timezone.now() - depose_il_y_a
        )
        piece.refresh_from_db()
    return piece


# ── 1. L'échéance ────────────────────────────────────────────────────────────


def test_un_document_depose_il_y_a_plus_d_un_an_quitte_le_disque(
    organisation: Organisation,
) -> None:
    piece = _deposer(organisation, depose_il_y_a=timedelta(days=400))
    chemin = piece.fichier.name
    assert default_storage.exists(chemin)

    assert purger_les_pieces_jointes().compte == 1

    assert not PieceJointe.objects.filter(pk=piece.pk).exists()
    # Le point qui compte : la ligne partie ne suffit pas. Le bilan d'un tiers
    # resté sur le volume est exactement ce que la rétention promet d'éviter.
    assert not default_storage.exists(chemin)


def test_un_document_recent_survit_a_la_purge(organisation: Organisation) -> None:
    """Contre-épreuve : la purge ne doit pas emporter ce qui est en cours d'usage."""
    piece = _deposer(organisation, depose_il_y_a=timedelta(days=30))
    chemin = piece.fichier.name

    assert purger_les_pieces_jointes().compte == 0

    assert PieceJointe.objects.filter(pk=piece.pk).exists()
    assert default_storage.exists(chemin)


def test_le_logo_n_expire_jamais(organisation: Organisation) -> None:
    """Contre-épreuve, et la plus importante.

    `organisation.logo_url` pointe sur ce fichier, et le moteur le charge à
    chaque génération. Un logo purgé à douze mois éteindrait silencieusement la
    marque de TOUS les livrables suivants d'un abonné fidèle — le défaut ne se
    verrait que sur un document déjà parti chez le client final.
    """
    logo = _deposer(
        organisation, nom="logo.png",
        categorie=CategorieFichier.LOGO, depose_il_y_a=timedelta(days=1500),
    )
    chemin = logo.fichier.name

    assert purger_les_pieces_jointes().compte == 0

    assert PieceJointe.objects.filter(pk=logo.pk).exists()
    assert default_storage.exists(chemin)


@override_settings(EVKHA_PIECES_JOINTES_RETENTION_DAYS=30)
def test_le_reglage_de_duree_est_reellement_lu(organisation: Organisation) -> None:
    """`EVKHA_DEFAULT_RETENTION_DAYS` a déjà été un bouton qui ne faisait rien.

    Il était déclaré dans les réglages et lu par personne, le vrai repli étant
    un `7` en dur recopié trois fois. Ce test verrouille que le nouveau réglage
    ne refait pas la même chose : à 30 jours, un fichier de 40 jours doit
    partir alors qu'il survivrait au défaut de 365.
    """
    piece = _deposer(organisation, depose_il_y_a=timedelta(days=40))

    assert purger_les_pieces_jointes().compte == 1
    assert not default_storage.exists(piece.fichier.name)


# ── 2. Le fichier meurt avec sa ligne, par tous les chemins ──────────────────


def test_le_remplacement_du_logo_efface_l_ancien_fichier(
    organisation: Organisation,
) -> None:
    """Échoue sur le code d'avant : mesuré « encore sur disque : True ».

    La vue de dépôt supprime le logo précédent par `queryset.delete()`, qui ne
    touche pas au stockage. Chaque changement de logo abandonnait un orphelin,
    sans qu'aucune rétention soit en cause.
    """
    ancien = _deposer(organisation, nom="ancien.png", categorie=CategorieFichier.LOGO)
    chemin = ancien.fichier.name
    assert default_storage.exists(chemin)

    organisation.pieces_jointes.filter(categorie=CategorieFichier.LOGO).delete()

    assert not default_storage.exists(chemin)


def test_la_suppression_d_une_organisation_efface_ses_fichiers(
    organisation: Organisation,
) -> None:
    """Échoue sur le code d'avant : le CASCADE laissait tout sur le volume.

    C'est le chemin d'un abonné qui s'en va. Ses fichiers doivent partir avec
    lui, et c'est aussi ce que le script de remise à zéro emprunte.
    """
    piece = _deposer(organisation, nom="compte-resultat.pdf")
    chemin = piece.fichier.name

    organisation.delete()

    assert not default_storage.exists(chemin)


def test_la_route_de_suppression_efface_toujours_le_fichier(
    organisation: Organisation,
) -> None:
    """Contre-épreuve du déplacement de la responsabilité vers `post_delete`.

    `supprimer_piece_jointe` ne fait plus l'effacement lui-même. Ce test
    vérifie que le comportement visible par le client n'a pas changé — sans
    quoi la simplification aurait cassé le seul chemin qui marchait.
    """
    contact = organisation.contact
    creer_compte(contact, mot_de_passe=MOT_DE_PASSE)
    jeton, _ = ouvrir_session(contact.email, MOT_DE_PASSE)

    piece = _deposer(organisation, nom="a-supprimer.pdf")
    chemin = piece.fichier.name

    reponse: Any = Client().post(
        f"/api/espace/fichiers/{piece.id}/supprimer/",
        headers={"authorization": f"Bearer {jeton}"},
    )

    assert reponse.status_code == 204
    assert not default_storage.exists(chemin)


# ── 3. Le mode « compte sans supprimer » ─────────────────────────────────────


def test_la_simulation_ne_touche_ni_la_base_ni_le_disque(
    organisation: Organisation,
) -> None:
    piece = _deposer(organisation, depose_il_y_a=timedelta(days=400))
    chemin = piece.fichier.name

    rapport = purger_les_pieces_jointes(simulation=True)

    assert rapport.simulation is True
    assert rapport.compte == 1
    # Le point entier du mode : il annonce, il n'exécute pas.
    assert PieceJointe.objects.filter(pk=piece.pk).exists()
    assert default_storage.exists(chemin)


def test_la_simulation_annonce_exactement_ce_que_la_purge_emporte(
    organisation: Organisation,
) -> None:
    """Le seul test qui rende la simulation digne de confiance.

    Un mode d'essai qui sélectionnerait autrement que la purge rassurerait sur
    un ensemble différent de celui qu'on supprime ensuite — et enverrait
    vérifier ce qui n'est pas en cause (règle 2). On compare donc les deux
    listes d'identifiants, pas seulement les deux comptes : deux ensembles
    disjoints de même taille passeraient une comparaison de nombres.
    """
    vieux = [
        _deposer(organisation, nom=f"bilan-{i}.pdf", depose_il_y_a=timedelta(days=400 + i))
        for i in range(3)
    ]
    _deposer(organisation, nom="recent.pdf", depose_il_y_a=timedelta(days=10))
    _deposer(
        organisation, nom="logo.png",
        categorie=CategorieFichier.LOGO, depose_il_y_a=timedelta(days=900),
    )

    annonce = purger_les_pieces_jointes(simulation=True)
    execute = purger_les_pieces_jointes()

    assert {d.id for d in annonce.depots} == {d.id for d in execute.depots}
    assert {d.id for d in execute.depots} == {str(p.id) for p in vieux}
    assert execute.simulation is False


def test_le_rapport_ne_promet_pas_l_espace_d_un_fichier_deja_absent(
    organisation: Organisation,
) -> None:
    """Compter un fichier disparu ferait annoncer un espace jamais rendu.

    Cas réel et non théorique : c'est l'état que laissaient le remplacement de
    logo et le CASCADE avant le `post_delete` — une ligne sans fichier.
    """
    presente = _deposer(organisation, nom="ici.pdf", depose_il_y_a=timedelta(days=400))
    absente = _deposer(organisation, nom="partie.pdf", depose_il_y_a=timedelta(days=400))
    default_storage.delete(absente.fichier.name)

    rapport = purger_les_pieces_jointes(simulation=True)

    assert rapport.compte == 2
    assert rapport.fichiers_deja_absents == 1
    # Les octets annoncés sont ceux qu'on récupérera vraiment, pas la somme
    # des tailles enregistrées en base.
    assert rapport.octets == presente.taille_octets
    assert "déjà disparu" in rapport.resume()


def test_la_commande_en_simulation_n_efface_rien_et_le_dit(
    organisation: Organisation,
) -> None:
    """La commande est ce que l'opérateur lance réellement avant mise en service."""
    from io import StringIO

    from django.core.management import call_command

    piece = _deposer(organisation, nom="bilan-2024.pdf", depose_il_y_a=timedelta(days=400))
    sortie = StringIO()

    call_command("purger_les_pieces_jointes", "--simulation", stdout=sortie)

    texte = sortie.getvalue()
    assert "SIMULATION" in texte
    assert "bilan-2024.pdf" in texte  # le lecteur doit pouvoir retrouver le fichier
    assert "seraient supprimés" in texte
    assert PieceJointe.objects.filter(pk=piece.pk).exists()
    assert default_storage.exists(piece.fichier.name)


def test_la_commande_dit_quand_il_n_y_a_rien_a_faire(
    organisation: Organisation,
) -> None:
    """Contre-épreuve : zéro se dit.

    Une commande muette laisse croire qu'elle a échoué ou n'a pas tourné.
    C'est ce silence qui a permis à Gamma de ne jamais s'exécuter pendant des
    semaines sans que personne ne le remarque (règle 8).
    """
    from io import StringIO

    from django.core.management import call_command

    _deposer(organisation, depose_il_y_a=timedelta(days=10))
    sortie = StringIO()

    call_command("purger_les_pieces_jointes", "--simulation", stdout=sortie)

    assert "Rien à faire" in sortie.getvalue()


def test_la_commande_sans_simulation_supprime_vraiment(
    organisation: Organisation,
) -> None:
    """Contre-épreuve du mode d'essai : il ne doit pas neutraliser la commande.

    Un drapeau mal branché qui simulerait TOUJOURS donnerait une purge qui
    journalise un travail qu'elle ne fait pas — exactement le « bouton qui ne
    fait rien » de la règle 1, et il ne se verrait qu'en auditant le volume.
    """
    from io import StringIO

    from django.core.management import call_command

    piece = _deposer(organisation, depose_il_y_a=timedelta(days=400))
    chemin = piece.fichier.name

    call_command("purger_les_pieces_jointes", stdout=StringIO())

    assert not PieceJointe.objects.filter(pk=piece.pk).exists()
    assert not default_storage.exists(chemin)


def test_la_tache_celery_purge_pour_de_bon(organisation: Organisation) -> None:
    """La tâche planifiée ne doit pas hériter du mode d'essai."""
    from organisations.tasks import purger_les_pieces_jointes_task

    piece = _deposer(organisation, depose_il_y_a=timedelta(days=400))
    chemin = piece.fichier.name

    assert purger_les_pieces_jointes_task() == 1

    assert not default_storage.exists(chemin)


def test_la_purge_ne_touche_pas_aux_fichiers_des_autres(
    organisation: Organisation,
) -> None:
    """Contre-épreuve de cloisonnement : purger l'un ne purge pas l'autre."""
    autre_contact = Customer.objects.create(email="rivage@example.com")
    autre = services.creer_organisation(
        raison_sociale="Agence Rivage", contact=autre_contact
    )
    abonner(autre)

    vieux = _deposer(organisation, depose_il_y_a=timedelta(days=400))
    recent = _deposer(autre, nom="frais.pdf", depose_il_y_a=timedelta(days=10))

    assert purger_les_pieces_jointes().compte == 1

    assert not default_storage.exists(vieux.fichier.name)
    assert default_storage.exists(recent.fichier.name)

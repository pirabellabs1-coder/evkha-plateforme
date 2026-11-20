"""Le suivi Qualiopi des formations : progression, durée d'accès, émargement.

La gérante est certifiée Qualiopi : elle doit pouvoir PROUVER le suivi de
chaque élève. Avant ce fichier, la plateforme ne gardait que la liste des
achats. Trois preuves sont tenues ici :

1. la **progression** de chaque élève — une PERSONNE, pas son organisation ;
2. la **durée d'accès** — figée à la livraison, décidée par la gérante ;
3. les **séances en présentiel** et leur feuille d'émargement.

Chaque test échoue sur le code d'avant (les routes, les champs et les modèles
n'existaient pas), et chaque refus a sa contre-épreuve : le cas voisin
légitime passe.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import uuid
from datetime import date, timedelta
from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext, override_settings
from django.utils import timezone
from paiement import formations as remise

from catalog import formations as regles
from catalog import suivi
from catalog.models import (
    AchatFormation,
    Emargement,
    Formation,
    LeconDeFormation,
    ModuleDeFormation,
    SeanceEnPresentiel,
    SignatureDefinitiveError,
    SuiviDeLecon,
)
from customers.models import Customer
from monitoring.models import OperationalIncident
from organisations import services, vues_espace
from organisations.authentification import (
    creer_compte,
    ouvrir_session,
    ouvrir_une_assistance,
)
from organisations.models import CompteClient, MembreOrganisation, RoleOrganisation
from tests.test_achat_de_formation import (
    REGLAGES,
    TEXTE,
    VIDEO,
    _courriels_en_doublure,
    _incidents_de_double_paiement,
    _revenir,
    _stripe_en_doublure,
    formation_en_vente,
    session_stripe,
)
from tests.test_audit_des_formations_du_20_novembre import (
    _achat_avec_intention,
    _remboursement,
)
from tests.test_barriere_de_paiement import (
    MOT_DE_PASSE,
    SECRET_WEBHOOK,
    Inscrit,
    poster_evenement,
)

pytestmark = pytest.mark.django_db

ADMIN = "/api/dashboard/formations/"
ESPACE = "/api/espace/formations/"


# ── Fabriques ────────────────────────────────────────────────────────────────


def _acheter_pour(cliente: Inscrit, formation: Formation) -> AchatFormation:
    session = session_stripe(formation)
    session["metadata"]["organisation_id"] = str(cliente.organisation.id)
    achat: AchatFormation = remise.livrer_la_formation(session).achat
    return achat


class Collegue:
    """Un second membre de la MÊME organisation, avec sa propre session."""

    def __init__(
        self, cliente: Inscrit, email: str, role: str = RoleOrganisation.MEMBRE
    ) -> None:
        self.contact = Customer.objects.create(
            email=email, first_name="Dominique", last_name="Martin"
        )
        services.inviter_membre(cliente.organisation, self.contact, role=role)
        self.compte = creer_compte(self.contact, mot_de_passe=MOT_DE_PASSE)
        self.jeton, _ = ouvrir_session(email, MOT_DE_PASSE)

    @property
    def entetes(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.jeton}"}


def _deux_lecons() -> tuple[Formation, LeconDeFormation, LeconDeFormation]:
    """Une formation vendable à DEUX leçons présentes, dans un même module."""
    formation = formation_en_vente()
    module = ModuleDeFormation.objects.get(formation=formation)
    premiere = LeconDeFormation.objects.get(module=module)
    seconde = LeconDeFormation.objects.create(
        module=module, titre="Écrire son offre", nature="texte", texte="Suite", rang=1
    )
    return formation, premiere, seconde


def _seance(formation: Formation, **surcharges: Any) -> SeanceEnPresentiel:
    """Une séance COMMENCÉE il y a une heure, donc signable."""
    defauts: dict[str, Any] = {
        "intitule": "Atelier de lancement",
        "debut": timezone.now() - timedelta(hours=1),
        "duree_minutes": 180,
        "lieu": "Salle Vauban, Lille",
        "nom_de_la_formatrice": "Evangéline K.",
    }
    defauts.update(surcharges)
    return SeanceEnPresentiel.objects.create(formation=formation, **defauts)


def _poster(adresse: str, charge: Any, entetes: dict[str, str]) -> Any:
    return Client().post(
        adresse, json.dumps(charge), content_type="application/json", headers=entetes
    )


def _noter(qui: Any, lecon: LeconDeFormation | str, **charge: Any) -> Any:
    identifiant = lecon if isinstance(lecon, str) else lecon.id
    return _poster(f"{ESPACE}lecons/{identifiant}/", charge, qui.entetes)


def _signer(qui: Any, seance: SeanceEnPresentiel | str, nom: Any = "Camille Durand") -> Any:
    identifiant = seance if isinstance(seance, str) else seance.id
    return _poster(f"{ESPACE}seances/{identifiant}/emargement/", {"nom": nom}, qui.entetes)


def _lues(qui: Any) -> list[dict[str, Any]]:
    reponse = Client().get(ESPACE, headers=qui.entetes)
    assert reponse.status_code == 200, reponse.content
    lues: list[dict[str, Any]] = reponse.json()["formations"]
    return lues


def _admin(client_admin: Any, adresse: str, charge: Any) -> Any:
    return client_admin.post(
        adresse, data=json.dumps(charge), content_type="application/json"
    )


def _eleves(client_admin: Any, formation: Formation) -> dict[str, Any]:
    reponse = client_admin.get(f"{ADMIN}{formation.id}/eleves/")
    assert reponse.status_code == 200, reponse.content
    corps: dict[str, Any] = reponse.json()
    return corps


# ── 1. La progression ────────────────────────────────────────────────────────


def test_zero_lecon_n_est_ni_zero_ni_cent_pour_cent() -> None:
    """Rien à mesurer : on le DIT (`None`), on n'invente pas un pourcentage."""
    assert suivi.progression([], []).en_dict() == {
        "terminees": 0, "total": 0, "pourcent": None,
    }
    # Une leçon terminée puis retirée du programme ne fait pas « 1 sur 0 ».
    assert suivi.progression([], ["a"]).en_dict() == {
        "terminees": 0, "total": 0, "pourcent": None,
    }
    # Contre-épreuves : dès qu'il y a une leçon, le pourcentage existe.
    assert suivi.progression(["a", "b"], []).pourcent == 0
    assert suivi.progression(["a", "b"], ["a"]).pourcent == 50
    assert suivi.progression(["a", "b"], ["a", "b"]).pourcent == 100


def test_le_pourcentage_s_arrondit_vers_le_bas() -> None:
    """« 100 % » montré à un auditeur veut dire TOUT : 2 sur 3 font 66, et
    199 sur 200 font 99."""
    assert suivi.progression("abc", "ab").pourcent == 66
    assert suivi.progression(range(200), range(199)).pourcent == 99


def test_l_eleve_ouvre_puis_termine_une_lecon() -> None:
    cliente = Inscrit()
    formation, premiere, _ = _deux_lecons()
    achat = _acheter_pour(cliente, formation)
    (avant,) = _lues(cliente)
    assert avant["progression"] == {"terminees": 0, "total": 2, "pourcent": 0}
    assert [le["terminee"] for le in avant["modules"][0]["lecons"]] == [False, False]

    ouverte = _noter(cliente, premiere, ouverte=True)

    assert ouverte.status_code == 200, ouverte.content
    trace = SuiviDeLecon.objects.get()
    assert (trace.achat, trace.eleve, trace.lecon) == (achat, cliente.contact, premiere)
    assert trace.terminee_le is None
    assert ouverte.json() == {
        "lecon": {
            "id": str(premiere.id),
            "terminee": False,
            "terminee_le": None,
            "premiere_ouverture_le": trace.premiere_ouverture_le.isoformat(),
            "derniere_ouverture_le": trace.derniere_ouverture_le.isoformat(),
        },
        "formation": formation.slug,
        "progression": {"terminees": 0, "total": 2, "pourcent": 0},
    }

    terminee = _noter(cliente, premiere, terminee=True)

    assert terminee.status_code == 200, terminee.content
    assert terminee.json()["lecon"]["terminee"] is True
    assert terminee.json()["progression"] == {"terminees": 1, "total": 2, "pourcent": 50}
    # Une seule ligne : la seconde écriture a repris la première.
    trace = SuiviDeLecon.objects.get()
    assert trace.terminee_le is not None
    assert trace.derniere_ouverture_le >= trace.premiere_ouverture_le
    (apres,) = _lues(cliente)
    assert apres["progression"] == {"terminees": 1, "total": 2, "pourcent": 50}
    assert [le["terminee"] for le in apres["modules"][0]["lecons"]] == [True, False]


def test_terminer_deux_fois_garde_la_premiere_date_et_decocher_l_efface() -> None:
    cliente = Inscrit()
    formation, premiere, _ = _deux_lecons()
    _acheter_pour(cliente, formation)
    _noter(cliente, premiere, terminee=True)
    premiere_date = SuiviDeLecon.objects.get().terminee_le

    _noter(cliente, premiere, terminee=True)

    assert SuiviDeLecon.objects.get().terminee_le == premiere_date
    # Rouvrir la leçon ne la « dé-termine » pas.
    _noter(cliente, premiere, ouverte=True)
    assert SuiviDeLecon.objects.get().terminee_le == premiere_date

    decochee = _noter(cliente, premiere, terminee=False)

    assert decochee.json()["lecon"]["terminee"] is False
    assert decochee.json()["progression"]["terminees"] == 0
    assert SuiviDeLecon.objects.get().terminee_le is None


def test_la_progression_est_celle_de_la_PERSONNE_pas_de_l_organisation(
    client_admin: Any,
) -> None:
    """Deux collaborateurs d'un même cabinet n'avancent pas du même pas — et
    l'espace et l'administration disent la même chose de chacun."""
    cliente = Inscrit()
    collegue = Collegue(cliente, "collegue@exemple.fr")
    formation, premiere, _ = _deux_lecons()
    achat = _acheter_pour(cliente, formation)

    assert _noter(collegue, premiere, terminee=True).status_code == 200

    (chez_elle,) = _lues(cliente)
    (chez_lui,) = _lues(collegue)
    assert chez_elle["progression"] == {"terminees": 0, "total": 2, "pourcent": 0}
    assert chez_lui["progression"] == {"terminees": 1, "total": 2, "pourcent": 50}
    assert chez_elle["modules"][0]["lecons"][0]["terminee"] is False
    assert chez_lui["modules"][0]["lecons"][0]["terminee"] is True

    tableau = _eleves(client_admin, formation)
    assert tableau["lecons_total"] == 2
    par_eleve = {ligne["eleve_id"]: ligne for ligne in tableau["eleves"]}
    assert set(par_eleve) == {str(cliente.contact.id), str(collegue.contact.id)}
    assert {ligne["achat_id"] for ligne in tableau["eleves"]} == {str(achat.id)}
    for qui, lue in ((cliente, chez_elle), (collegue, chez_lui)):
        ligne = par_eleve[str(qui.contact.id)]
        assert {
            "terminees": ligne["lecons_terminees"],
            "total": ligne["lecons_total"],
            "pourcent": ligne["pourcent"],
        } == lue["progression"]
    assert par_eleve[str(cliente.contact.id)]["derniere_activite"] is None
    assert par_eleve[str(collegue.contact.id)]["derniere_activite"] == (
        SuiviDeLecon.objects.get().derniere_ouverture_le.isoformat()
    )


def test_une_lecon_retiree_ne_compte_ni_en_haut_ni_en_bas(client_admin: Any) -> None:
    cliente = Inscrit()
    formation, premiere, seconde = _deux_lecons()
    _acheter_pour(cliente, formation)
    _noter(cliente, premiere, terminee=True)
    _noter(cliente, seconde, terminee=True)
    assert _lues(cliente)[0]["progression"]["pourcent"] == 100

    # On retire une leçon TERMINÉE : elle sort du haut ET du bas.
    LeconDeFormation.objects.filter(pk=seconde.pk).update(retire_le=timezone.now())

    attendu = {"terminees": 1, "total": 1, "pourcent": 100}
    assert _lues(cliente)[0]["progression"] == attendu
    (ligne,) = _eleves(client_admin, formation)["eleves"]
    assert (ligne["lecons_terminees"], ligne["lecons_total"], ligne["pourcent"]) == (1, 1, 100)

    # Contre-épreuve du retrait : la rétablir la fait recompter.
    LeconDeFormation.objects.filter(pk=seconde.pk).update(retire_le=None)
    assert _lues(cliente)[0]["progression"] == {"terminees": 2, "total": 2, "pourcent": 100}

    # Le MODULE retiré : plus aucune leçon présente, progression non calculable
    # — dite `null` aux deux endroits, ni 0 ni 100.
    ModuleDeFormation.objects.filter(formation=formation).update(retire_le=timezone.now())

    vide = {"terminees": 0, "total": 0, "pourcent": None}
    assert _lues(cliente)[0]["progression"] == vide
    tableau = _eleves(client_admin, formation)
    assert tableau["lecons_total"] == 0
    (ligne,) = tableau["eleves"]
    assert (ligne["lecons_terminees"], ligne["lecons_total"], ligne["pourcent"]) == (0, 0, None)


def test_une_lecon_qui_n_est_pas_a_lui_rend_404_sans_dire_si_elle_existe() -> None:
    """Le cloisonnement : une leçon d'une formation que son organisation n'a
    pas achetée, une leçon retirée et un identifiant inventé rendent le MÊME
    refus — et rien n'est écrit."""
    cliente = Inscrit()
    voisine = Inscrit(nom="Cabinet voisin", email="voisine@exemple.fr")
    formation, premiere, seconde = _deux_lecons()
    _acheter_pour(cliente, formation)
    # La voisine a acheté AUTRE CHOSE : avoir un achat ne suffit pas.
    _acheter_pour(voisine, formation_en_vente(titre="Une autre"))
    LeconDeFormation.objects.filter(pk=seconde.pk).update(retire_le=timezone.now())

    reponses = [
        _noter(voisine, premiere, terminee=True),
        _noter(voisine, str(uuid.uuid4()), terminee=True),
        _noter(voisine, "pas-un-identifiant", terminee=True),
        # Retirée : même pour qui a acheté, elle n'est plus au programme.
        _noter(cliente, seconde, terminee=True),
    ]

    for reponse in reponses:
        assert reponse.status_code == 404, reponse.content
        assert reponse.json() == reponses[0].json()
        assert reponse.json()["code"] == "lecon_inconnue"
    assert not SuiviDeLecon.objects.exists()

    # Contre-épreuve : la propriétaire, sur une leçon présente, écrit.
    assert _noter(cliente, premiere, terminee=True).status_code == 200
    assert SuiviDeLecon.objects.get().eleve == cliente.contact


@pytest.mark.parametrize(
    "charge",
    [
        {},
        {"ouverte": False},
        {"ouverte": "oui"},
        {"terminee": "oui"},
        {"terminee": 1},
        {"terminee": None},
        {"ouverte": True, "terminee": "non"},
        {"autre": True},
    ],
)
def test_un_geste_illisible_n_ecrit_aucune_preuve(charge: dict[str, Any]) -> None:
    cliente = Inscrit()
    formation, premiere, _ = _deux_lecons()
    _acheter_pour(cliente, formation)

    reponse = _noter(cliente, premiere, **charge)

    assert (reponse.status_code, reponse.json()["code"]) == (400, "geste_illisible")
    assert not SuiviDeLecon.objects.exists()


def test_un_compte_en_lecture_seule_est_un_eleve_comme_un_autre() -> None:
    """Ce que ces routes écrivent est la trace d'UNE personne, pas une donnée
    de l'organisation : aucun rôle ne la ferme."""
    cliente = Inscrit()
    lecteur = Collegue(cliente, "lecteur@exemple.fr", role=RoleOrganisation.LECTURE)
    formation, premiere, _ = _deux_lecons()
    _acheter_pour(cliente, formation)
    seance = _seance(formation)

    assert _noter(lecteur, premiere, terminee=True).status_code == 200
    assert _signer(lecteur, seance, "Dominique Martin").status_code == 201

    assert SuiviDeLecon.objects.get().eleve == lecteur.contact
    assert Emargement.objects.get().eleve == lecteur.contact


def test_une_session_d_assistance_ne_laisse_aucune_preuve_a_la_place_de_l_eleve() -> None:
    """Un agent d'EVKHA entré pour dépanner n'est pas l'élève."""
    cliente = Inscrit()
    formation, premiere, _ = _deux_lecons()
    _acheter_pour(cliente, formation)
    seance = _seance(formation)
    compte = CompteClient.objects.get(customer=cliente.contact)
    jeton = ouvrir_une_assistance(compte, par="console de test")

    class Agent:
        entetes = {"Authorization": f"Bearer {jeton}"}

    lecon = _noter(Agent, premiere, terminee=True)
    presence = _signer(Agent, seance)

    for reponse in (lecon, presence):
        assert (reponse.status_code, reponse.json()["code"]) == (
            403, "assistance_sans_trace",
        )
    assert not SuiviDeLecon.objects.exists()
    assert not Emargement.objects.exists()
    # Contre-épreuves : l'assistance LIT l'espace, et l'élève, elle, écrit.
    assert len(_lues(Agent)) == 1
    assert _noter(cliente, premiere, terminee=True).status_code == 200
    assert _signer(cliente, seance).status_code == 201


def test_sans_session_le_suivi_est_ferme() -> None:
    cliente = Inscrit()
    formation, premiere, _ = _deux_lecons()
    _acheter_pour(cliente, formation)
    seance = _seance(formation)

    class Personne:
        entetes: dict[str, str] = {}

    for reponse in (_noter(Personne, premiere, terminee=True), _signer(Personne, seance)):
        assert (reponse.status_code, reponse.json()["code"]) == (401, "unauthorized")
    assert not SuiviDeLecon.objects.exists()
    assert not Emargement.objects.exists()
    # Lecture et suppression ne sont pas des gestes de ces routes.
    for adresse in (
        f"{ESPACE}lecons/{premiere.id}/",
        f"{ESPACE}seances/{seance.id}/emargement/",
    ):
        assert Client().get(adresse, headers=cliente.entetes).status_code == 405
        assert Client().delete(adresse, headers=cliente.entetes).status_code == 405


def test_la_base_n_admet_qu_un_suivi_par_eleve_achat_et_lecon() -> None:
    """Le verrou contre le double clic est dans la base, et l'écriture le
    traverse sans erreur : la seconde reprend la ligne de la première."""
    cliente = Inscrit()
    formation, premiere, _ = _deux_lecons()
    achat = _acheter_pour(cliente, formation)

    une = suivi.noter_une_lecon(achat, cliente.contact, premiere, terminee=None)
    deux = suivi.noter_une_lecon(achat, cliente.contact, premiere, terminee=True)

    assert une.pk == deux.pk
    assert SuiviDeLecon.objects.count() == 1
    maintenant = timezone.now()
    with pytest.raises(IntegrityError), transaction.atomic():
        SuiviDeLecon.objects.create(
            achat=achat, eleve=cliente.contact, lecon=premiere,
            premiere_ouverture_le=maintenant, derniere_ouverture_le=maintenant,
        )
    # La transaction englobante reste utilisable après le refus de la base.
    assert SuiviDeLecon.objects.count() == 1


# ── 2. La durée d'accès ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("depuis", "mois", "attendu"),
    [
        (date(2026, 11, 20), 0, None),
        (date(2026, 11, 20), 12, date(2027, 11, 20)),
        (date(2026, 11, 20), 2, date(2027, 1, 20)),
        (date(2027, 1, 31), 1, date(2027, 2, 28)),
        (date(2028, 1, 31), 1, date(2028, 2, 29)),
        (date(2026, 11, 20), regles.DUREE_D_ACCES_MAX_MOIS, date(2076, 11, 20)),
    ],
)
def test_la_fin_d_acces_se_compte_en_mois_calendaires(
    depuis: date, mois: int, attendu: date | None
) -> None:
    assert suivi.fin_d_acces(depuis, mois) == attendu


def test_par_defaut_un_achat_reste_sans_limite() -> None:
    """La valeur par défaut ne change RIEN au comportement d'avant."""
    cliente = Inscrit()
    formation = formation_en_vente()
    assert formation.duree_d_acces_mois == 0

    achat = _acheter_pour(cliente, formation)

    assert achat.acces_jusqu_au is None
    assert achat.etat_de_l_acces == "ouvert"
    (lue,) = _lues(cliente)
    assert (lue["acces"], lue["acces_jusqu_au"]) == ("ouvert", None)
    assert lue["modules"][0]["lecons"][0]["texte"] == TEXTE


def test_la_duree_est_figee_a_la_livraison() -> None:
    """Changer la durée de la formation ne déplace la fin d'aucun accès vendu."""
    cliente = Inscrit()
    voisine = Inscrit(nom="Cabinet voisin", email="voisine@exemple.fr")
    formation = formation_en_vente(duree_d_acces_mois=12)

    achat = _acheter_pour(cliente, formation)

    figee = suivi.fin_d_acces(timezone.localdate(), 12)
    assert figee is not None
    assert achat.acces_jusqu_au == figee
    assert _lues(cliente)[0]["acces_jusqu_au"] == figee.isoformat()

    Formation.objects.filter(pk=formation.pk).update(duree_d_acces_mois=3)
    formation.refresh_from_db()
    suivant = _acheter_pour(voisine, formation)

    achat.refresh_from_db()
    assert achat.acces_jusqu_au == figee
    assert suivant.acces_jusqu_au == suivi.fin_d_acces(timezone.localdate(), 3)
    # Un REJEU de la session ne recalcule rien non plus.
    assert AchatFormation.objects.count() == 2


def test_la_gerante_saisit_la_duree_d_acces_sur_la_fiche(client_admin: Any) -> None:
    formation = formation_en_vente()
    fiche = f"{ADMIN}{formation.id}/"
    (lue,) = client_admin.get(ADMIN).json()["formations"]
    assert lue["duree_d_acces_mois"] == 0

    reponse = _admin(client_admin, fiche, {"duree_d_acces_mois": 18})

    assert reponse.status_code == 200, reponse.content
    assert reponse.json()["formation"]["duree_d_acces_mois"] == 18
    assert reponse.json()["refuses"] == []

    illisible = _admin(client_admin, fiche, {"duree_d_acces_mois": "un an"})
    assert illisible.status_code == 200
    assert [r["champ"] for r in illisible.json()["refuses"]] == ["duree_d_acces_mois"]
    assert illisible.json()["formation"]["duree_d_acces_mois"] == 18

    for trop, code in ((regles.DUREE_D_ACCES_MAX_MOIS + 1, "valeur_trop_grande"),
                       (-1, "valeur_negative")):
        refus = _admin(client_admin, fiche, {"duree_d_acces_mois": trop})
        assert (refus.status_code, refus.json()["code"]) == (400, code)
        assert refus.json()["champ"] == "duree_d_acces_mois"
    formation.refresh_from_db()
    assert formation.duree_d_acces_mois == 18
    # Contre-épreuve : le plafond lui-même, et zéro (sans limite), passent.
    for admis in (regles.DUREE_D_ACCES_MAX_MOIS, 0):
        assert _admin(client_admin, fiche, {"duree_d_acces_mois": admis}).status_code == 200


def test_un_acces_echu_reste_liste_mais_ne_lit_plus_le_programme() -> None:
    cliente = Inscrit()
    formation, premiere, _ = _deux_lecons()
    achat = _acheter_pour(cliente, formation)
    hier = timezone.localdate() - timedelta(days=1)
    AchatFormation.objects.filter(pk=achat.pk).update(acces_jusqu_au=hier)

    reponse = Client().get(ESPACE, headers=cliente.entetes)

    (lue,) = reponse.json()["formations"]
    assert (lue["slug"], lue["acces"], lue["acces_jusqu_au"]) == (
        formation.slug, "echu", hier.isoformat(),
    )
    assert lue["modules"] == []
    # Plus AUCUN contenu payant ne sort, sous aucune clé.
    assert VIDEO not in reponse.content.decode()
    assert TEXTE not in reponse.content.decode()
    # Et l'élève ne note plus de leçon : son accès est fermé, on le lui dit.
    refus = _noter(cliente, premiere, terminee=True)
    assert (refus.status_code, refus.json()["code"]) == (403, "acces_echu")
    assert hier.strftime("%d/%m/%Y") in refus.json()["error"]
    assert not SuiviDeLecon.objects.exists()

    # Contre-épreuve : le dernier jour est COMPRIS.
    AchatFormation.objects.filter(pk=achat.pk).update(acces_jusqu_au=timezone.localdate())
    (lue,) = _lues(cliente)
    assert lue["acces"] == "ouvert"
    assert lue["modules"][0]["lecons"][0]["texte"] == TEXTE
    assert _noter(cliente, premiere, terminee=True).status_code == 200


def test_le_retrait_l_emporte_sur_l_echeance_et_ferme_tout() -> None:
    cliente = Inscrit()
    formation, premiere, _ = _deux_lecons()
    achat = _acheter_pour(cliente, formation)
    AchatFormation.objects.filter(pk=achat.pk).update(
        revoque_le=timezone.now(),
        acces_jusqu_au=timezone.localdate() - timedelta(days=1),
    )
    achat.refresh_from_db()

    assert achat.etat_de_l_acces == "retire"
    assert achat.donne_acces is False
    assert _lues(cliente) == []
    refus = _noter(cliente, premiere, terminee=True)
    assert (refus.status_code, refus.json()["code"]) == (404, "lecon_inconnue")
    assert not SuiviDeLecon.objects.exists()


def test_la_gerante_fixe_et_prolonge_le_dernier_jour_d_acces(client_admin: Any) -> None:
    cliente = Inscrit()
    formation = formation_en_vente()
    achat = _acheter_pour(cliente, formation)
    adresse = f"{ADMIN}achats/{achat.id}/"
    hier = (timezone.localdate() - timedelta(days=1)).isoformat()

    fermee = _admin(client_admin, adresse, {"acces_jusqu_au": hier})

    assert fermee.status_code == 200, fermee.content
    assert (fermee.json()["achat"]["acces_jusqu_au"], fermee.json()["achat"]["acces"]) == (
        hier, "echu",
    )
    assert fermee.json()["achat"]["revoque_le"] is None
    assert _lues(cliente)[0]["modules"] == []

    # Prolonger ROUVRE le programme.
    prolongee = _admin(client_admin, adresse, {"acces_jusqu_au": "2099-12-31"})
    assert prolongee.json()["achat"]["acces"] == "ouvert"
    assert _lues(cliente)[0]["modules"] != []

    # `null` : sans limite.
    sans_limite = _admin(client_admin, adresse, {"acces_jusqu_au": None})
    assert sans_limite.json()["achat"]["acces_jusqu_au"] is None
    achat.refresh_from_db()
    assert achat.acces_jusqu_au is None

    # Les deux gestes voyagent ensemble.
    ensemble = _admin(
        client_admin, adresse,
        {"revoque": True, "motif": "Remboursée", "acces_jusqu_au": "2030-01-31"},
    )
    assert ensemble.status_code == 200, ensemble.content
    rendu = ensemble.json()["achat"]
    assert (rendu["acces"], rendu["acces_jusqu_au"]) == ("retire", "2030-01-31")
    assert rendu["revoque_le"] is not None


@pytest.mark.parametrize("saisie", ["31/01/2030", "2030-02-30", "demain", 20300131, True, []])
def test_une_date_illisible_est_refusee_et_ne_change_rien(
    client_admin: Any, saisie: Any
) -> None:
    """La lire comme « sans limite » ouvrirait un accès sans fin."""
    cliente = Inscrit()
    achat = _acheter_pour(cliente, formation_en_vente())
    borne = date(2027, 6, 30)
    AchatFormation.objects.filter(pk=achat.pk).update(acces_jusqu_au=borne)

    reponse = _admin(
        client_admin, f"{ADMIN}achats/{achat.id}/",
        # Avec un retrait dans le même envoi : RIEN ne doit passer à moitié.
        {"acces_jusqu_au": saisie, "revoque": True},
    )

    assert (reponse.status_code, reponse.json()["code"]) == (400, "date_illisible")
    achat.refresh_from_db()
    assert achat.acces_jusqu_au == borne
    assert achat.revoque_le is None


# ── 3. Les séances en présentiel ─────────────────────────────────────────────


def test_la_gerante_cree_une_seance_et_la_relit(client_admin: Any) -> None:
    formation = formation_en_vente()
    adresse = f"{ADMIN}{formation.id}/seances/"
    assert client_admin.get(adresse).json() == {"seances": []}

    reponse = _admin(client_admin, adresse, {
        "intitule": "  Atelier de lancement  ",
        "debut": "2026-12-01T09:00",
        "duree_minutes": 210,
        "lieu": "Salle Vauban, Lille",
        "nom_de_la_formatrice": "Evangéline K.",
    })

    assert reponse.status_code == 201, reponse.content
    cree = SeanceEnPresentiel.objects.get()
    # Sans fuseau, l'heure saisie est celle de Paris.
    assert timezone.localtime(cree.debut).strftime("%Y-%m-%d %H:%M") == "2026-12-01 09:00"
    attendu = {
        "id": str(cree.id),
        "formation_id": str(formation.id),
        "intitule": "Atelier de lancement",
        "debut": cree.debut.isoformat(),
        "duree_minutes": 210,
        "lieu": "Salle Vauban, Lille",
        "nom_de_la_formatrice": "Evangéline K.",
        "annulee_le": None,
        "signee_par_la_formatrice_le": None,
        "emargements": [],
    }
    assert reponse.json() == {"seance": attendu, "refuses": []}
    assert client_admin.get(adresse).json() == {"seances": [attendu]}
    # La séance d'une AUTRE formation n'y figure pas.
    autre = formation_en_vente(titre="Une autre")
    assert client_admin.get(f"{ADMIN}{autre.id}/seances/").json() == {"seances": []}


@pytest.mark.parametrize(
    ("charge", "code"),
    [
        ({"debut": "2026-12-01T09:00", "duree_minutes": 60}, "intitule_manquant"),
        ({"intitule": "Atelier", "duree_minutes": 60}, "debut_illisible"),
        ({"intitule": "Atelier", "debut": "mardi matin", "duree_minutes": 60}, "debut_illisible"),
        ({"intitule": "Atelier", "debut": "2026-12-01T09:00"}, "valeur_illisible"),
        ({"intitule": "Atelier", "debut": "2026-12-01T09:00", "duree_minutes": 0},
         "duree_manquante"),
        ({"intitule": "Atelier", "debut": "2026-12-01T09:00", "duree_minutes": -5},
         "valeur_negative"),
        ({"intitule": "Atelier", "debut": "2026-12-01T09:00", "duree_minutes": 1441},
         "valeur_trop_grande"),
        ({"intitule": "A" * 201, "debut": "2026-12-01T09:00", "duree_minutes": 60},
         "texte_trop_long"),
        ({"intitule": "Atelier", "debut": "2026-12-01T09:00", "duree_minutes": 60,
          "lieu": "L" * 201}, "texte_trop_long"),
    ],
)
def test_une_seance_incomplete_ou_hors_bornes_n_est_pas_creee(
    client_admin: Any, charge: dict[str, Any], code: str
) -> None:
    formation = formation_en_vente()

    reponse = _admin(client_admin, f"{ADMIN}{formation.id}/seances/", charge)

    assert (reponse.status_code, reponse.json()["code"]) == (400, code)
    assert not SeanceEnPresentiel.objects.exists()


def test_l_eleve_signe_sa_presence_une_fois(client_admin: Any) -> None:
    cliente = Inscrit()
    formation = formation_en_vente()
    achat = _acheter_pour(cliente, formation)
    seance = _seance(formation)
    (lue,) = _lues(cliente)
    assert lue["seances"] == [{
        "id": str(seance.id),
        "intitule": "Atelier de lancement",
        "debut": seance.debut.isoformat(),
        "duree_minutes": 180,
        "lieu": "Salle Vauban, Lille",
        "signee_le": None,
        "annulee_le": None,
        # Commencée il y a une heure : elle se signe, jusqu'au lendemain de sa fin.
        "signable": True,
        "signature_jusqu_au": (
            seance.debut + timedelta(minutes=180) + suivi.SIGNATURE_EN_LIGNE_APRES_LA_FIN
        ).isoformat(),
    }]

    reponse = _signer(cliente, seance, "  Camille   Durand ")

    assert reponse.status_code == 201, reponse.content
    signature = Emargement.objects.get()
    assert (signature.seance, signature.achat, signature.eleve) == (
        seance, achat, cliente.contact,
    )
    assert (signature.nom_signe, signature.mode, signature.adresse_ip) == (
        "Camille Durand", "en_ligne", "127.0.0.1",
    )
    assert reponse.json() == {"emargement": {
        "seance_id": str(seance.id),
        "signe_le": signature.signe_le.isoformat(),
        "mode": "en_ligne",
        "nom_signe": "Camille Durand",
    }}
    (signee,) = _lues(cliente)[0]["seances"]
    assert signee["signee_le"] == signature.signe_le.isoformat()
    assert signee["signable"] is False

    # Une signature ne se refait pas, ni par l'élève ni sur papier.
    seconde = _signer(cliente, seance, "Un autre nom")
    papier = _admin(client_admin, f"{ADMIN}seances/{seance.id}/", {
        "emargement_papier": {
            "achat_id": str(achat.id), "eleve_id": str(cliente.contact.id),
            "nom": "Encore un autre",
        },
    })
    for refus in (seconde, papier):
        assert (refus.status_code, refus.json()["code"]) == (409, "deja_signe")
    intacte = Emargement.objects.get()
    assert (intacte.nom_signe, intacte.signe_le) == ("Camille Durand", signature.signe_le)


def test_une_seance_a_venir_ou_annulee_ne_se_signe_pas(client_admin: Any) -> None:
    """Pour les TROIS signatures : l'élève, le papier, la formatrice."""
    cliente = Inscrit()
    formation = formation_en_vente()
    achat = _acheter_pour(cliente, formation)
    a_venir = _seance(formation, debut=timezone.now() + timedelta(hours=2))
    annulee = _seance(formation, annulee_le=timezone.now())
    papier = {"emargement_papier": {
        "achat_id": str(achat.id), "eleve_id": str(cliente.contact.id),
        "nom": "Camille Durand",
    }}

    for seance, code in ((a_venir, "seance_pas_commencee"), (annulee, "seance_annulee")):
        tentatives = [
            _signer(cliente, seance),
            _admin(client_admin, f"{ADMIN}seances/{seance.id}/", papier),
            _admin(client_admin, f"{ADMIN}seances/{seance.id}/", {"signer": True}),
        ]
        for reponse in tentatives:
            assert (reponse.status_code, reponse.json()["code"]) == (409, code)
        seance.refresh_from_db()
        assert seance.signee_par_la_formatrice_le is None
    assert not Emargement.objects.exists()

    # Contre-épreuve : la même séance, une fois commencée, se signe.
    SeanceEnPresentiel.objects.filter(pk=a_venir.pk).update(
        debut=timezone.now() - timedelta(minutes=1)
    )
    assert _signer(cliente, a_venir).status_code == 201


def test_la_seance_d_une_autre_organisation_rend_404() -> None:
    cliente = Inscrit()
    voisine = Inscrit(nom="Cabinet voisin", email="voisine@exemple.fr")
    formation = formation_en_vente()
    _acheter_pour(cliente, formation)
    _acheter_pour(voisine, formation_en_vente(titre="Une autre"))
    seance = _seance(formation)

    reponses = [
        _signer(voisine, seance),
        _signer(voisine, str(uuid.uuid4())),
        _signer(voisine, "pas-un-identifiant"),
    ]

    for reponse in reponses:
        assert reponse.status_code == 404, reponse.content
        assert reponse.json() == reponses[0].json()
        assert reponse.json()["code"] == "seance_inconnue"
    assert not Emargement.objects.exists()
    # Et elle ne la voit pas non plus dans sa liste.
    assert _lues(voisine)[0]["seances"] == []
    # Contre-épreuve : l'élève inscrite signe.
    assert _signer(cliente, seance).status_code == 201


def test_un_acces_retire_ne_signe_plus_mais_un_acces_echu_si() -> None:
    cliente = Inscrit()
    voisine = Inscrit(nom="Cabinet voisin", email="voisine@exemple.fr")
    formation = formation_en_vente()
    retire = _acheter_pour(cliente, formation)
    echu = _acheter_pour(voisine, formation)
    AchatFormation.objects.filter(pk=retire.pk).update(revoque_le=timezone.now())
    AchatFormation.objects.filter(pk=echu.pk).update(
        acces_jusqu_au=timezone.localdate() - timedelta(days=1)
    )
    seance = _seance(formation)

    refus = _signer(cliente, seance)
    admise = _signer(voisine, seance)

    assert (refus.status_code, refus.json()["code"]) == (404, "seance_inconnue")
    assert admise.status_code == 201, admise.content
    assert Emargement.objects.get().eleve == voisine.contact


@pytest.mark.parametrize("nom", ["", "   ", "A", "N" * 121, None, 42, ["Camille"]])
def test_une_signature_sans_nom_lisible_est_refusee(nom: Any) -> None:
    cliente = Inscrit()
    formation = formation_en_vente()
    _acheter_pour(cliente, formation)
    seance = _seance(formation)

    reponse = _signer(cliente, seance, nom)

    assert reponse.status_code == 400, reponse.content
    assert reponse.json()["code"] in {"nom_manquant", "nom_trop_long"}
    assert not Emargement.objects.exists()
    # Contre-épreuve : le plafond lui-même passe, sans être coupé.
    plein = "N" * 120
    assert _signer(cliente, seance, plein).status_code == 201
    assert Emargement.objects.get().nom_signe == plein


def test_la_gerante_reporte_une_signature_recueillie_sur_papier(client_admin: Any) -> None:
    cliente = Inscrit()
    voisine = Inscrit(nom="Cabinet voisin", email="voisine@exemple.fr")
    formation = formation_en_vente()
    autre = formation_en_vente(titre="Une autre")
    achat = _acheter_pour(cliente, formation)
    ailleurs = _acheter_pour(voisine, autre)
    seance = _seance(formation)
    adresse = f"{ADMIN}seances/{seance.id}/"

    def papier(achat_id: Any, eleve_id: Any, nom: Any = "Camille Durand") -> Any:
        return _admin(client_admin, adresse, {"emargement_papier": {
            "achat_id": str(achat_id), "eleve_id": str(eleve_id), "nom": nom,
        }})

    etrangers = [
        # L'achat d'une AUTRE formation.
        papier(ailleurs.id, voisine.contact.id),
        # Le bon achat, mais une personne d'une autre organisation.
        papier(achat.id, voisine.contact.id),
        papier(achat.id, uuid.uuid4()),
        papier(uuid.uuid4(), cliente.contact.id),
        papier("pas-un-identifiant", "non-plus"),
    ]
    for reponse in etrangers:
        assert (reponse.status_code, reponse.json()["code"]) == (404, "eleve_inconnu")
    illisible = _admin(client_admin, adresse, {"emargement_papier": "Camille"})
    assert (illisible.status_code, illisible.json()["code"]) == (400, "emargement_illisible")
    sans_nom = papier(achat.id, cliente.contact.id, "")
    assert (sans_nom.status_code, sans_nom.json()["code"]) == (400, "nom_manquant")
    assert not Emargement.objects.exists()

    reponse = papier(achat.id, cliente.contact.id)

    assert reponse.status_code == 200, reponse.content
    signature = Emargement.objects.get()
    # Pas d'adresse pour une signature papier : ce serait celle de la gérante.
    assert (signature.mode, signature.adresse_ip, signature.nom_signe) == (
        "papier", None, "Camille Durand",
    )
    assert reponse.json()["seance"]["emargements"] == [{
        "id": str(signature.id),
        "achat_id": str(achat.id),
        "eleve_id": str(cliente.contact.id),
        "nom": "Cabinet Test",
        "signe_le": signature.signe_le.isoformat(),
        "mode": "papier",
        "nom_signe": "Camille Durand",
        "adresse_ip": None,
    }]
    # L'élève le lit dans son espace.
    assert _lues(cliente)[0]["seances"][0]["signee_le"] == signature.signe_le.isoformat()


def test_la_formatrice_signe_la_seance_une_fois_pour_de_bon(client_admin: Any) -> None:
    formation = formation_en_vente()
    anonyme = _seance(formation, nom_de_la_formatrice="")
    seance = _seance(formation)
    adresse = f"{ADMIN}seances/{seance.id}/"

    sans_nom = _admin(client_admin, f"{ADMIN}seances/{anonyme.id}/", {"signer": True})
    assert (sans_nom.status_code, sans_nom.json()["code"]) == (409, "formatrice_inconnue")
    anonyme.refresh_from_db()
    assert anonyme.signee_par_la_formatrice_le is None
    # Le nom et la signature peuvent voyager dans le même envoi.
    avec = _admin(
        client_admin, f"{ADMIN}seances/{anonyme.id}/",
        {"nom_de_la_formatrice": "Evangéline K.", "signer": True},
    )
    assert avec.status_code == 200, avec.content
    assert avec.json()["seance"]["signee_par_la_formatrice_le"]

    signee = _admin(client_admin, adresse, {"signer": True})

    assert signee.status_code == 200, signee.content
    date_de_signature = signee.json()["seance"]["signee_par_la_formatrice_le"]
    assert date_de_signature
    # Signer deux fois garde la première date ; la retirer est refusé.
    assert _admin(client_admin, adresse, {"signer": True}).json()["seance"][
        "signee_par_la_formatrice_le"
    ] == date_de_signature
    retrait = _admin(client_admin, adresse, {"signer": False})
    assert (retrait.status_code, retrait.json()["code"]) == (409, "signature_definitive")
    seance.refresh_from_db()
    assert seance.signee_par_la_formatrice_le is not None


def test_une_seance_signee_ne_se_decrit_plus_autrement(client_admin: Any) -> None:
    """Changer l'heure d'une séance sous la signature de quelqu'un fabriquerait
    une preuve."""
    cliente = Inscrit()
    formation = formation_en_vente()
    _acheter_pour(cliente, formation)
    libre = _seance(formation, intitule="Encore libre")
    signee_par_un_eleve = _seance(formation)
    signee_par_la_formatrice = _seance(formation, signee_par_la_formatrice_le=timezone.now())
    assert _signer(cliente, signee_par_un_eleve).status_code == 201

    for seance in (signee_par_un_eleve, signee_par_la_formatrice):
        for charge in (
            {"intitule": "Autre intitulé"},
            {"debut": "2020-01-01T09:00"},
            {"duree_minutes": 600},
            {"lieu": "Ailleurs"},
            {"nom_de_la_formatrice": "Quelqu'un d'autre"},
        ):
            reponse = _admin(client_admin, f"{ADMIN}seances/{seance.id}/", charge)
            assert (reponse.status_code, reponse.json()["code"]) == (409, "seance_signee")
        relue = SeanceEnPresentiel.objects.get(pk=seance.pk)
        assert (relue.intitule, relue.debut, relue.duree_minutes, relue.lieu) == (
            seance.intitule, seance.debut, seance.duree_minutes, seance.lieu,
        )
        # Renvoyer la fiche telle qu'on l'a lue n'est pas une modification.
        identique = _admin(
            client_admin, f"{ADMIN}seances/{seance.id}/", {"intitule": seance.intitule}
        )
        assert identique.status_code == 200, identique.content

    # Contre-épreuve : une séance que personne n'a signée se modifie.
    modifiee = _admin(client_admin, f"{ADMIN}seances/{libre.id}/", {
        "intitule": "Atelier déplacé", "duree_minutes": 90, "debut": "2027-01-05T14:00",
    })
    assert modifiee.status_code == 200, modifiee.content
    assert (modifiee.json()["seance"]["intitule"], modifiee.json()["seance"]["duree_minutes"]) == (
        "Atelier déplacé", 90,
    )
    # Un début illisible laisse le précédent, et la réponse le nomme.
    illisible = _admin(client_admin, f"{ADMIN}seances/{libre.id}/", {"debut": "bientôt"})
    assert illisible.status_code == 200
    assert [r["champ"] for r in illisible.json()["refuses"]] == ["debut"]
    assert illisible.json()["seance"]["debut"] == modifiee.json()["seance"]["debut"]


def test_une_seance_s_annule_et_se_retablit_sans_perdre_ses_signatures(
    client_admin: Any,
) -> None:
    cliente = Inscrit()
    formation = formation_en_vente()
    _acheter_pour(cliente, formation)
    seance = _seance(formation)
    assert _signer(cliente, seance).status_code == 201
    adresse = f"{ADMIN}seances/{seance.id}/"

    annulee = _admin(client_admin, adresse, {"annulee": True})

    assert annulee.status_code == 200, annulee.content
    date_d_annulation = annulee.json()["seance"]["annulee_le"]
    assert date_d_annulation
    # Rien n'est effacé : la ligne et la signature restent.
    assert len(annulee.json()["seance"]["emargements"]) == 1
    assert SeanceEnPresentiel.objects.filter(pk=seance.pk).exists()
    assert _lues(cliente)[0]["seances"][0]["annulee_le"] == date_d_annulation
    # Annuler deux fois garde la première date.
    assert _admin(client_admin, adresse, {"annulee": True}).json()["seance"][
        "annulee_le"
    ] == date_d_annulation
    # Annuler ET signer dans le même envoi : tout est refusé, rien n'est écrit.
    _admin(client_admin, adresse, {"annulee": False})
    ensemble = _admin(client_admin, adresse, {"annulee": True, "signer": True})
    assert (ensemble.status_code, ensemble.json()["code"]) == (409, "seance_annulee")
    seance.refresh_from_db()
    assert seance.annulee_le is None, "l'annulation est passée malgré le refus"
    assert seance.signee_par_la_formatrice_le is None

    illisible = _admin(client_admin, adresse, {"annulee": "peut-être"})
    assert [r["champ"] for r in illisible.json()["refuses"]] == ["annulee"]
    assert illisible.json()["seance"]["annulee_le"] is None


def test_une_signature_ne_se_modifie_ni_ne_se_supprime(client_admin: Any) -> None:
    cliente = Inscrit()
    formation = formation_en_vente()
    _acheter_pour(cliente, formation)
    seance = _seance(formation)
    assert _signer(cliente, seance).status_code == 201
    signature = Emargement.objects.get()

    signature.nom_signe = "Quelqu'un d'autre"
    with pytest.raises(SignatureDefinitiveError):
        signature.save()
    with pytest.raises(SignatureDefinitiveError):
        signature.delete()

    relue = Emargement.objects.get()
    assert relue.nom_signe == "Camille Durand"
    # Aucune route ne supprime : ni une séance, ni une feuille, ni un tableau.
    for adresse in (
        f"{ADMIN}seances/{seance.id}/",
        f"{ADMIN}seances/{seance.id}/feuille/",
        f"{ADMIN}{formation.id}/seances/",
        f"{ADMIN}{formation.id}/eleves/",
        f"{ADMIN}{formation.id}/eleves.csv",
    ):
        assert client_admin.delete(adresse).status_code == 405, adresse
    assert Emargement.objects.count() == 1
    assert SeanceEnPresentiel.objects.count() == 1
    # La contrainte de la base est le dernier rempart contre un doublon.
    with pytest.raises(IntegrityError), transaction.atomic():
        Emargement.objects.create(
            seance=seance, achat=signature.achat, eleve=cliente.contact,
            signe_le=timezone.now(), nom_signe="Doublon", mode="papier",
        )


def test_la_feuille_d_emargement_liste_les_inscrits_et_leurs_signatures(
    client_admin: Any,
) -> None:
    cliente = Inscrit()
    collegue = Collegue(cliente, "collegue@exemple.fr")
    partie = Inscrit(nom="Cabinet parti", email="partie@exemple.fr")
    remboursee = Inscrit(nom="Cabinet remboursé", email="remboursee@exemple.fr")
    echue = Inscrit(nom="Cabinet échu", email="echue@exemple.fr")
    formation = formation_en_vente()
    achat = _acheter_pour(cliente, formation)
    achat_parti = _acheter_pour(partie, formation)
    achat_rembourse = _acheter_pour(remboursee, formation)
    achat_echu = _acheter_pour(echue, formation)
    seance = _seance(formation, signee_par_la_formatrice_le=timezone.now())
    assert _signer(collegue, seance, "Dominique Martin").status_code == 201
    # Elle signe, PUIS son accès est retiré : sa signature reste sur la feuille.
    assert _signer(partie, seance, "Partie Signataire").status_code == 201
    AchatFormation.objects.filter(pk__in=[achat_parti.pk, achat_rembourse.pk]).update(
        revoque_le=timezone.now()
    )
    AchatFormation.objects.filter(pk=achat_echu.pk).update(
        acces_jusqu_au=timezone.localdate() - timedelta(days=1)
    )
    seance.refresh_from_db()

    reponse = client_admin.get(f"{ADMIN}seances/{seance.id}/feuille/")

    assert reponse.status_code == 200, reponse.content
    feuille = reponse.json()["feuille"]
    assert feuille["formation"] == {"id": str(formation.id), "titre": formation.titre}
    assert feuille["seance"] == {
        "id": str(seance.id),
        "intitule": "Atelier de lancement",
        "debut": seance.debut.isoformat(),
        "duree_minutes": 180,
        "lieu": "Salle Vauban, Lille",
        "annulee_le": None,
    }
    assert seance.signee_par_la_formatrice_le is not None
    assert feuille["formatrice"] == {
        "nom": "Evangéline K.",
        "signee_le": seance.signee_par_la_formatrice_le.isoformat(),
    }
    signatures = {e.eleve_id: e for e in Emargement.objects.all()}
    par_eleve = {ligne["eleve_id"]: ligne for ligne in feuille["lignes"]}
    # La remboursée SANS signature n'y figure pas ; l'échue, si.
    assert set(par_eleve) == {
        str(cliente.contact.id), str(collegue.contact.id),
        str(partie.contact.id), str(echue.contact.id),
    }
    assert par_eleve[str(cliente.contact.id)] == {
        "achat_id": str(achat.id),
        "eleve_id": str(cliente.contact.id),
        "nom": "Cabinet Test",
        "organisation": "Cabinet Test",
        "acces": "ouvert",
        "signature": None,
    }
    assert par_eleve[str(collegue.contact.id)] == {
        "achat_id": str(achat.id),
        "eleve_id": str(collegue.contact.id),
        "nom": "Dominique Martin",
        "organisation": "Cabinet Test",
        "acces": "ouvert",
        "signature": {
            "signe_le": signatures[collegue.contact.id].signe_le.isoformat(),
            "mode": "en_ligne",
            "nom_signe": "Dominique Martin",
        },
    }
    assert par_eleve[str(partie.contact.id)]["acces"] == "retire"
    assert par_eleve[str(partie.contact.id)]["signature"]["nom_signe"] == "Partie Signataire"
    assert par_eleve[str(echue.contact.id)]["acces"] == "echu"
    # Une feuille imprimée circule dans la salle : aucune adresse dessus.
    assert "@" not in reponse.content.decode()


# ── 4. Le tableau des élèves, et son export ──────────────────────────────────


def test_le_tableau_des_eleves_dit_tout_ce_qu_un_auditeur_demande(client_admin: Any) -> None:
    cliente = Inscrit()
    formation, premiere, _ = _deux_lecons()
    achat = _acheter_pour(cliente, formation)
    _noter(cliente, premiere, terminee=True)
    tenue = _seance(formation, duree_minutes=180)
    autre = _seance(formation, duree_minutes=90, intitule="Second atelier")
    annulee = _seance(formation, duree_minutes=600, intitule="Annulée après coup")
    non_signee = _seance(formation, duree_minutes=45, intitule="Manquée")
    for seance in (tenue, autre, annulee):
        assert _signer(cliente, seance).status_code == 201
    SeanceEnPresentiel.objects.filter(pk=annulee.pk).update(annulee_le=timezone.now())
    compte = CompteClient.objects.get(customer=cliente.contact)
    assert compte.derniere_connexion is not None
    assert non_signee.pk

    tableau = _eleves(client_admin, formation)

    assert tableau == {
        "lecons_total": 2,
        "eleves": [{
            "achat_id": str(achat.id),
            "eleve_id": str(cliente.contact.id),
            "nom": "Cabinet Test",
            "email": "essai@exemple.fr",
            "organisation": "Cabinet Test",
            "achete_le": achat.created_at.isoformat(),
            "acces_jusqu_au": None,
            "acces": "ouvert",
            "derniere_connexion": compte.derniere_connexion.isoformat(),
            "derniere_activite": SuiviDeLecon.objects.get().derniere_ouverture_le.isoformat(),
            "lecons_terminees": 1,
            "lecons_total": 2,
            "pourcent": 50,
            # 180 + 90 : la séance annulée et la séance non signée ne comptent pas.
            "minutes_en_presentiel_signees": 270,
        }],
    }


def test_un_achat_sans_aucun_membre_connu_garde_sa_ligne(client_admin: Any) -> None:
    """Une place payée ne disparaît pas du tableau faute de nom."""
    cliente = Inscrit()
    formation = formation_en_vente()
    achat = _acheter_pour(cliente, formation)
    MembreOrganisation.objects.filter(organisation=cliente.organisation).update(
        revoque_le=timezone.now()
    )

    (ligne,) = _eleves(client_admin, formation)["eleves"]

    assert (ligne["achat_id"], ligne["eleve_id"], ligne["nom"]) == (str(achat.id), None, "")
    # L'adresse est celle de l'ACHAT, collectée au paiement.
    assert ligne["email"] == achat.email
    assert achat.email != cliente.contact.email
    assert ligne["derniere_connexion"] is None
    assert (ligne["lecons_terminees"], ligne["pourcent"]) == (0, 0)


def test_un_eleve_parti_garde_sa_trace_et_les_etats_d_acces_sont_dits(
    client_admin: Any,
) -> None:
    cliente = Inscrit()
    collegue = Collegue(cliente, "collegue@exemple.fr")
    voisine = Inscrit(nom="Cabinet voisin", email="voisine@exemple.fr")
    remboursee = Inscrit(nom="Cabinet remboursé", email="remboursee@exemple.fr")
    formation, premiere, _ = _deux_lecons()
    _acheter_pour(cliente, formation)
    echu = _acheter_pour(voisine, formation)
    retire = _acheter_pour(remboursee, formation)
    _noter(collegue, premiere, terminee=True)
    # Le collègue quitte l'organisation APRÈS avoir suivi une leçon.
    MembreOrganisation.objects.filter(customer=collegue.contact).update(
        revoque_le=timezone.now()
    )
    AchatFormation.objects.filter(pk=echu.pk).update(
        acces_jusqu_au=timezone.localdate() - timedelta(days=1)
    )
    AchatFormation.objects.filter(pk=retire.pk).update(revoque_le=timezone.now())

    lignes = _eleves(client_admin, formation)["eleves"]

    par_eleve = {ligne["eleve_id"]: ligne for ligne in lignes}
    assert len(lignes) == 4
    assert par_eleve[str(collegue.contact.id)]["lecons_terminees"] == 1
    assert {ligne["eleve_id"]: ligne["acces"] for ligne in lignes} == {
        str(cliente.contact.id): "ouvert",
        str(collegue.contact.id): "ouvert",
        str(voisine.contact.id): "echu",
        str(remboursee.contact.id): "retire",
    }
    # Une AUTRE formation ne voit aucun de ces élèves.
    assert _eleves(client_admin, formation_en_vente(titre="Une autre")) == {
        "eleves": [], "lecons_total": 1,
    }


def test_le_tableau_ne_coute_pas_une_requete_de_plus_par_eleve(client_admin: Any) -> None:
    formation, premiere, _ = _deux_lecons()
    cliente = Inscrit()
    _acheter_pour(cliente, formation)
    _noter(cliente, premiere, terminee=True)

    def compter() -> tuple[int, int]:
        with CaptureQueriesContext(connection) as capture:
            reponse = client_admin.get(f"{ADMIN}{formation.id}/eleves/")
        return len(capture), len(reponse.json()["eleves"])

    requetes_pour_une, lignes_pour_une = compter()
    for numero in range(4):
        autre = Inscrit(nom=f"Cabinet {numero}", email=f"eleve{numero}@exemple.fr")
        _acheter_pour(autre, formation)
        Collegue(autre, f"collegue{numero}@exemple.fr")
    requetes_pour_neuf, lignes_pour_neuf = compter()

    assert (lignes_pour_une, lignes_pour_neuf) == (1, 9)
    assert requetes_pour_neuf == requetes_pour_une


def _csv(client_admin: Any, formation: Formation) -> tuple[Any, list[list[str]]]:
    reponse = client_admin.get(f"{ADMIN}{formation.id}/eleves.csv")
    assert reponse.status_code == 200, reponse.content
    texte = reponse.content.decode("utf-8-sig")
    return reponse, list(csv.reader(io.StringIO(texte), delimiter=";"))


def test_l_export_csv_est_le_meme_tableau_pour_un_tableur_francais(client_admin: Any) -> None:
    cliente = Inscrit()
    collegue = Collegue(cliente, "collegue@exemple.fr")
    formation, premiere, _ = _deux_lecons()
    achat = _acheter_pour(cliente, formation)
    AchatFormation.objects.filter(pk=achat.pk).update(acces_jusqu_au=date(2099, 6, 30))
    _noter(collegue, premiere, terminee=True)
    assert _signer(collegue, _seance(formation, duree_minutes=180)).status_code == 201

    reponse, lignes = _csv(client_admin, formation)

    # UTF-8 AVEC indicateur d'ordre des octets : sans lui, Excel lit « Ã‰lÃ¨ve ».
    assert reponse.content.startswith(b"\xef\xbb\xbf")
    assert reponse["Content-Type"] == "text/csv; charset=utf-8"
    assert reponse["Content-Disposition"] == (
        f'attachment; filename="eleves-{formation.slug}.csv"'
    )
    assert reponse["Cache-Control"] == "no-store"
    assert lignes[0] == [
        "Élève", "Adresse électronique", "Organisation", "Acheté le", "Accès",
        "Accès jusqu'au", "Dernière connexion", "Dernière activité",
        "Leçons terminées", "Leçons au programme", "Progression",
        "Minutes en présentiel signées",
    ]
    # Les MÊMES lignes que l'écran, dans le même ordre.
    tableau = _eleves(client_admin, formation)["eleves"]
    assert [ligne[1] for ligne in lignes[1:]] == [e["email"] for e in tableau]
    par_adresse = {ligne[1]: ligne for ligne in lignes[1:]}
    lui = par_adresse["collegue@exemple.fr"]
    assert (lui[0], lui[2], lui[4], lui[5]) == (
        "Dominique Martin", "Cabinet Test", "Ouvert", "30/06/2099",
    )
    assert lui[8:] == ["1", "2", "50 %", "180"]
    elle = par_adresse["essai@exemple.fr"]
    assert elle[7:] == ["", "0", "2", "0 %", "0"]
    # Dates lisibles par un auditeur, à l'heure de Paris.
    assert lui[3] == timezone.localtime(achat.created_at).strftime("%d/%m/%Y %H:%M")


def test_l_export_dit_sans_limite_et_non_calculable(client_admin: Any) -> None:
    cliente = Inscrit()
    formation = formation_en_vente()
    _acheter_pour(cliente, formation)
    ModuleDeFormation.objects.filter(formation=formation).update(retire_le=timezone.now())

    _, lignes = _csv(client_admin, formation)

    (ligne,) = lignes[1:]
    assert ligne[5] == "sans limite"
    assert ligne[9:11] == ["0", "non calculable (aucune leçon au programme)"]


@pytest.mark.parametrize(
    "piege",
    [
        "=HYPERLINK(\"http://exemple.invalid\";\"clic\")",
        "+33 6 00 00 00 00",
        "-2+3",
        "@SUM(A1:A9)",
        "\t=1+1",
        "  =1+1",
    ],
)
def test_l_export_neutralise_les_formules_de_tableur(client_admin: Any, piege: str) -> None:
    """Un nom saisi comme une formule s'exécuterait à l'ouverture du fichier
    par l'auditeur. On juge sur la forme de la cellule, pas sur une liste."""
    cliente = Inscrit(nom=piege)
    Customer.objects.filter(pk=cliente.contact.pk).update(last_name="Durand")
    formation = formation_en_vente()
    _acheter_pour(cliente, formation)

    _, lignes = _csv(client_admin, formation)

    (ligne,) = lignes[1:]
    # Le nom ET la raison sociale portent le piège : les deux sont désamorcés.
    # (Le nom d'un élève est rendu sans ses blancs de bord ; la raison sociale
    # est rendue telle quelle.)
    for cellule in (ligne[0], ligne[2]):
        assert cellule.startswith("'"), cellule
        assert cellule[1:].lstrip().startswith(piege.strip())
    assert ligne[2] == "'" + piege
    # À l'écran (JSON), la valeur reste telle quelle : rien n'y est évalué.
    assert _eleves(client_admin, formation)["eleves"][0]["organisation"] == piege


def test_contre_epreuve_une_cellule_ordinaire_n_est_pas_touchee() -> None:
    for ordinaire in ("Camille Durand", "Jean-Marc", "a=b", "3 - 2", "x@exemple.fr", "", 12, 0):
        assert suivi.cellule_sure(ordinaire) == str(ordinaire)
    assert suivi.cellule_sure(None) == ""
    assert suivi.cellule_sure("=1+1") == "'=1+1"
    assert suivi.cellule_sure("\r\n=1+1") == "'\r\n=1+1"


def test_les_routes_d_administration_exigent_le_jeton(client_admin: Any) -> None:
    cliente = Inscrit()
    formation = formation_en_vente()
    _acheter_pour(cliente, formation)
    seance = _seance(formation)
    lectures = [
        f"{ADMIN}{formation.id}/eleves/",
        f"{ADMIN}{formation.id}/eleves.csv",
        f"{ADMIN}{formation.id}/seances/",
        f"{ADMIN}seances/{seance.id}/feuille/",
    ]

    for adresse in lectures:
        for client in (Client(), Client(headers=cliente.entetes)):
            reponse = client.get(adresse)
            assert reponse.status_code == 401, adresse
            assert "essai@exemple.fr" not in reponse.content.decode()
        # Contre-épreuve : avec le jeton, la route répond.
        assert client_admin.get(adresse).status_code == 200, adresse
    for adresse in (f"{ADMIN}{formation.id}/seances/", f"{ADMIN}seances/{seance.id}/"):
        sans = Client().post(
            adresse, json.dumps({"annulee": True}), content_type="application/json"
        )
        assert sans.status_code == 401, adresse
    seance.refresh_from_db()
    assert seance.annulee_le is None
    assert SeanceEnPresentiel.objects.count() == 1


@pytest.mark.parametrize(
    ("methode", "adresse"),
    [
        ("get", "{admin}{inconnu}/eleves/"),
        ("get", "{admin}{inconnu}/eleves.csv"),
        ("get", "{admin}{inconnu}/seances/"),
        ("post", "{admin}{inconnu}/seances/"),
        ("post", "{admin}seances/{inconnu}/"),
        ("get", "{admin}seances/{inconnu}/feuille/"),
        ("get", "{admin}pas-un-identifiant/eleves/"),
        ("post", "{admin}seances/pas-un-identifiant/"),
        ("get", "{admin}seances/pas-un-identifiant/feuille/"),
    ],
)
def test_un_identifiant_inconnu_ou_mal_forme_rend_un_404_lisible(
    client_admin: Any, methode: str, adresse: str
) -> None:
    complete = adresse.format(admin=ADMIN, inconnu=uuid.uuid4())

    reponse = getattr(client_admin, methode)(complete)

    assert reponse.status_code == 404, reponse.content
    assert reponse.json()["code"] in {"formation_inconnue", "seance_inconnue"}
    assert reponse.json()["erreur"]


# ── 5. Ce que les journaux ne portent pas ────────────────────────────────────


def test_aucune_adresse_de_courriel_dans_les_journaux(
    client_admin: Any, caplog: Any
) -> None:
    cliente = Inscrit()
    collegue = Collegue(cliente, "collegue@exemple.fr")
    formation, premiere, _ = _deux_lecons()
    caplog.set_level(logging.DEBUG)
    achat = _acheter_pour(cliente, formation)
    seance = _seance(formation)
    autre = _seance(formation, intitule="Sur papier")

    assert _noter(collegue, premiere, terminee=True).status_code == 200
    assert _signer(collegue, seance, "Dominique Martin").status_code == 201
    assert _admin(client_admin, f"{ADMIN}seances/{autre.id}/", {
        "signer": True,
        "emargement_papier": {
            "achat_id": str(achat.id), "eleve_id": str(cliente.contact.id),
            "nom": "Camille Durand",
        },
    }).status_code == 200
    assert _admin(
        client_admin, f"{ADMIN}achats/{achat.id}/", {"acces_jusqu_au": "2099-01-01"}
    ).status_code == 200
    assert client_admin.get(f"{ADMIN}{formation.id}/eleves.csv").status_code == 200
    assert client_admin.get(f"{ADMIN}seances/{seance.id}/feuille/").status_code == 200

    journal = caplog.text
    # Contre-épreuve : ces gestes SONT journalisés — le test ne lit pas du vide.
    assert str(collegue.contact.id) in journal
    assert "exporté" in journal
    for adresse in ("collegue@exemple.fr", "essai@exemple.fr", achat.email):
        assert adresse not in journal, adresse
    # Ni le nom tapé pour signer : c'est une donnée personnelle de plus.
    assert "Dominique Martin" not in journal
    assert "Camille Durand" not in journal


# ── 6. Corrections de l'audit indépendant du 20/11/2026 ──────────────────────
#
# Chaque test de cette section échoue sans sa correction, et porte sa
# contre-épreuve.


def _echoir(achat: AchatFormation) -> None:
    AchatFormation.objects.filter(pk=achat.pk).update(
        acces_jusqu_au=timezone.localdate() - timedelta(days=1)
    )


@override_settings(**REGLAGES)
def test_un_acces_echu_se_rachete_depuis_l_espace(monkeypatch: Any) -> None:
    """Il répondait « vous avez déjà cette formation » à qui ne pouvait plus
    la lire, sans aucun moyen de la reprendre."""
    cliente = Inscrit()
    formation = formation_en_vente()
    achat = _acheter_pour(cliente, formation)
    envois = _stripe_en_doublure(monkeypatch)
    adresse = "/api/espace/formations/acheter/"

    # Contre-épreuve d'abord : un accès OUVERT reste « déjà achetée ».
    ouvert = _poster(adresse, {"formation": formation.slug}, cliente.entetes)
    assert (ouvert.status_code, ouvert.json()["code"]) == (409, "formation_deja_achetee")
    assert envois == []

    _echoir(achat)
    echu = _poster(adresse, {"formation": formation.slug}, cliente.entetes)

    assert echu.status_code == 200, echu.content
    assert echu.json()["adresse"]
    assert len(envois) == 1


def test_racheter_apres_l_echeance_ouvre_un_acces_neuf_sans_incident() -> None:
    """Ce paiement tombait dans la branche du double paiement : argent pris,
    incident de remboursement, accès toujours fermé."""
    cliente = Inscrit()
    formation, premiere, _ = _deux_lecons()
    Formation.objects.filter(pk=formation.pk).update(duree_d_acces_mois=6)
    formation.refresh_from_db()
    ancien = _acheter_pour(cliente, formation)
    assert _noter(cliente, premiere, terminee=True).status_code == 200
    _echoir(ancien)
    session = session_stripe(formation)
    session["metadata"]["organisation_id"] = str(cliente.organisation.id)

    resultat = remise.livrer_la_formation(session)

    assert (resultat.nouveau, resultat.en_double) == (True, False)
    assert resultat.achat.pk != ancien.pk
    assert resultat.achat.reference_paiement == session["id"]
    assert not _incidents_de_double_paiement().exists()
    # L'ancien achat est CLOS, pas effacé ni prolongé : la ligne et son suivi restent.
    ancien.refresh_from_db()
    assert ancien.revoque_le is not None
    assert ancien.motif_de_revocation == (
        f"Accès échu, racheté le {timezone.localdate().strftime('%d/%m/%Y')}"
    )
    assert ancien.acces_jusqu_au == timezone.localdate() - timedelta(days=1)
    assert SuiviDeLecon.objects.get().achat == ancien
    # Le nouveau a SA propre échéance, et un suivi neuf.
    assert resultat.achat.acces_jusqu_au == suivi.fin_d_acces(timezone.localdate(), 6)
    (lue,) = _lues(cliente)
    assert lue["acces"] == "ouvert"
    assert lue["modules"] != []
    assert lue["progression"] == {"terminees": 0, "total": 2, "pourcent": 0}

    # Le REJEU de la même session ne refait rien : c'est pour cela que le
    # paiement est porté par sa propre ligne.
    rejeu = remise.livrer_la_formation(session)

    assert (rejeu.nouveau, rejeu.en_double) == (False, False)
    assert rejeu.achat == resultat.achat
    assert AchatFormation.objects.count() == 2
    assert AchatFormation.objects.filter(revoque_le__isnull=True).count() == 1
    assert not _incidents_de_double_paiement().exists()


@override_settings(**REGLAGES)
def test_racheter_apres_l_echeance_par_la_page_publique(monkeypatch: Any) -> None:
    """Sur la page publique, l'acheteur n'est reconnu qu'APRÈS le paiement."""
    _courriels_en_doublure(monkeypatch)
    formation = formation_en_vente()
    adresse = "camille@example.com"
    premiere = session_stripe(formation)
    premiere["customer_details"]["email"] = adresse
    ancien = remise.livrer_la_formation(premiere).achat
    _echoir(ancien)
    # La page publique ouvre le paiement sans rien savoir de l'acheteur.
    _stripe_en_doublure(monkeypatch)
    ouverture = Client().post(
        "/api/public/formations/acheter/",
        json.dumps({"formation": formation.slug, "email": adresse}),
        content_type="application/json",
    )
    assert ouverture.status_code == 200, ouverture.content
    seconde = session_stripe(formation)
    seconde["customer_details"]["email"] = adresse

    retour = _revenir(monkeypatch, seconde)

    assert retour.status_code == 200, retour.content
    assert not _incidents_de_double_paiement().exists()
    ancien.refresh_from_db()
    assert ancien.revoque_le is not None
    nouveau = AchatFormation.objects.get(reference_paiement=seconde["id"])
    assert nouveau.organisation == ancien.organisation
    assert nouveau.etat_de_l_acces == "ouvert"
    # Le rejeu du retour : toujours un seul achat ouvert, toujours aucun incident.
    assert _revenir(monkeypatch, seconde).status_code == 200
    assert AchatFormation.objects.count() == 2
    assert not _incidents_de_double_paiement().exists()


def test_contre_epreuve_un_vrai_double_paiement_ouvre_toujours_son_incident() -> None:
    """Un accès OUVERT payé une seconde fois reste un double paiement."""
    cliente = Inscrit()
    formation = formation_en_vente()
    premier = _acheter_pour(cliente, formation)
    # Une échéance À VENIR n'est pas une échéance passée.
    AchatFormation.objects.filter(pk=premier.pk).update(
        acces_jusqu_au=timezone.localdate() + timedelta(days=30)
    )
    session = session_stripe(formation)
    session["metadata"]["organisation_id"] = str(cliente.organisation.id)

    resultat = remise.livrer_la_formation(session)

    assert (resultat.nouveau, resultat.en_double) == (False, True)
    assert resultat.achat == premier
    assert AchatFormation.objects.count() == 1
    assert _incidents_de_double_paiement().count() == 1
    premier.refresh_from_db()
    assert premier.revoque_le is None


def test_la_signature_en_ligne_a_une_fenetre(client_admin: Any) -> None:
    """Sans elle, n'importe qui signait des mois plus tard une séance où il
    n'était pas."""
    cliente = Inscrit()
    collegue = Collegue(cliente, "collegue@exemple.fr")
    formation = formation_en_vente()
    achat = _acheter_pour(cliente, formation)
    AchatFormation.objects.filter(pk=achat.pk).update(
        created_at=timezone.now() - timedelta(days=30)
    )
    apres = suivi.SIGNATURE_EN_LIGNE_APRES_LA_FIN
    # Finie depuis la fenêtre + 1 h : fermée. Finie depuis la fenêtre − 1 h : ouverte.
    fermee = _seance(
        formation, intitule="Fermée", duree_minutes=60,
        debut=timezone.now() - apres - timedelta(hours=2),
    )
    encore_ouverte = _seance(
        formation, intitule="Encore ouverte", duree_minutes=60,
        debut=timezone.now() - apres,
    )

    refus = _signer(cliente, fermee)

    assert (refus.status_code, refus.json()["code"]) == (409, "signature_fermee")
    assert not Emargement.objects.exists()
    par_intitule = {s["intitule"]: s for s in _lues(cliente)[0]["seances"]}
    assert par_intitule["Fermée"]["signable"] is False
    assert par_intitule["Encore ouverte"]["signable"] is True
    assert par_intitule["Fermée"]["signature_jusqu_au"] == (
        suivi.signature_en_ligne_jusqu_au(fermee).isoformat()
    )
    # Contre-épreuves : dans la fenêtre, l'élève signe ; hors fenêtre, la
    # gérante reporte le papier et la formatrice signe — sans limite.
    assert _signer(cliente, encore_ouverte).status_code == 201
    papier = _admin(client_admin, f"{ADMIN}seances/{fermee.id}/", {
        "signer": True,
        "emargement_papier": {
            "achat_id": str(achat.id), "eleve_id": str(collegue.contact.id),
            "nom": "Dominique Martin",
        },
    })
    assert papier.status_code == 200, papier.content
    assert papier.json()["seance"]["signee_par_la_formatrice_le"]
    assert Emargement.objects.get(seance=fermee).mode == "papier"


def test_on_ne_signe_pas_une_seance_tenue_avant_son_inscription(client_admin: Any) -> None:
    cliente = Inscrit()
    formation = formation_en_vente()
    # La séance s'est terminée il y a deux heures ; l'achat se fait maintenant.
    passee = _seance(
        formation, intitule="Avant l'achat", duree_minutes=60,
        debut=timezone.now() - timedelta(hours=3),
    )
    achat = _acheter_pour(cliente, formation)
    _seance(formation, intitule="En cours")

    refus = _signer(cliente, passee)

    assert (refus.status_code, refus.json()["code"]) == (409, "seance_anterieure_a_l_achat")
    assert not Emargement.objects.exists()
    # Elle n'est pas montrée à l'élève : il n'y était pas inscrit.
    assert [s["intitule"] for s in _lues(cliente)[0]["seances"]] == ["En cours"]

    # Contre-épreuve : le même élève, inscrit AVANT la fin de la séance, la
    # voit et la signe.
    AchatFormation.objects.filter(pk=achat.pk).update(
        created_at=timezone.now() - timedelta(hours=4)
    )
    assert [s["intitule"] for s in _lues(cliente)[0]["seances"]] == [
        "Avant l'achat", "En cours",
    ]
    assert _signer(cliente, passee).status_code == 201
    # Et le report papier, lui, n'a jamais regardé la date de l'achat.
    AchatFormation.objects.filter(pk=achat.pk).update(created_at=timezone.now())
    autre = _seance(
        formation, intitule="Reportée", duree_minutes=60,
        debut=timezone.now() - timedelta(hours=3),
    )
    papier = _admin(client_admin, f"{ADMIN}seances/{autre.id}/", {"emargement_papier": {
        "achat_id": str(achat.id), "eleve_id": str(cliente.contact.id), "nom": "Camille Durand",
    }})
    assert papier.status_code == 200, papier.content
    # Une séance SIGNÉE reste montrée, même antérieure à l'achat.
    assert "Reportée" in [s["intitule"] for s in _lues(cliente)[0]["seances"]]


def test_l_espace_dit_si_la_seance_se_signe_maintenant() -> None:
    cliente = Inscrit()
    formation = formation_en_vente()
    _acheter_pour(cliente, formation)
    en_cours = _seance(formation, intitule="En cours")
    _seance(formation, intitule="À venir", debut=timezone.now() + timedelta(days=2))
    _seance(formation, intitule="Annulée", annulee_le=timezone.now())
    deja = _seance(formation, intitule="Déjà signée")
    assert _signer(cliente, deja).status_code == 201
    compte = CompteClient.objects.get(customer=cliente.contact)

    class Agent:
        entetes = {"Authorization": f"Bearer {ouvrir_une_assistance(compte, par='test')}"}

    par_intitule = {s["intitule"]: s for s in _lues(cliente)[0]["seances"]}

    assert {nom: s["signable"] for nom, s in par_intitule.items()} == {
        "En cours": True, "À venir": False, "Annulée": False, "Déjà signée": False,
    }
    assert par_intitule["Annulée"]["signature_jusqu_au"] is None
    assert par_intitule["En cours"]["signature_jusqu_au"] == (
        suivi.signature_en_ligne_jusqu_au(en_cours).isoformat()
    )
    # En assistance, rien ne se signe : le bouton ne le promet pas.
    assert {s["signable"] for s in _lues(Agent)[0]["seances"]} == {False}


def test_un_json_imbrique_a_l_exces_rend_400_et_non_500() -> None:
    """`RecursionError` n'est pas une `ValueError` : elle remontait en 500."""
    cliente = Inscrit()
    formation, premiere, _ = _deux_lecons()
    _acheter_pour(cliente, formation)
    seance = _seance(formation)
    profond = b"[" * 200_000

    for adresse, code in (
        (f"{ESPACE}lecons/{premiere.id}/", "geste_illisible"),
        (f"{ESPACE}seances/{seance.id}/emargement/", "nom_manquant"),
    ):
        reponse = Client().post(
            adresse, profond, content_type="application/json", headers=cliente.entetes
        )
        assert (reponse.status_code, reponse.json()["code"]) == (400, code)
    assert not SuiviDeLecon.objects.exists()
    assert not Emargement.objects.exists()


def test_l_adresse_d_une_signature_ne_se_choisit_pas_par_un_en_tete() -> None:
    """Le client écrit ce qu'il veut en tête de `X-Forwarded-For` ; seule la
    DERNIÈRE entrée est posée par notre relais."""
    cliente = Inscrit()
    collegue = Collegue(cliente, "collegue@exemple.fr")
    formation = formation_en_vente()
    _acheter_pour(cliente, formation)
    seance = _seance(formation)

    def signer(qui: Any) -> Any:
        return Client().post(
            f"{ESPACE}seances/{seance.id}/emargement/",
            json.dumps({"nom": "Camille Durand"}),
            content_type="application/json",
            headers=qui.entetes,
            HTTP_X_FORWARDED_FOR="6.6.6.6, 10.0.0.1",
        )

    with override_settings(EVKHA_PROXIES_DE_CONFIANCE=1):
        assert signer(cliente).status_code == 201
    assert Emargement.objects.get(eleve=cliente.contact).adresse_ip == "10.0.0.1"
    # Contre-épreuve : sans relais de confiance, l'en-tête n'est pas lu du tout.
    with override_settings(EVKHA_PROXIES_DE_CONFIANCE=0):
        assert signer(collegue).status_code == 201
    assert Emargement.objects.get(eleve=collegue.contact).adresse_ip == "127.0.0.1"


def test_deux_signatures_simultanees_la_base_tranche_et_la_seconde_lit_409(
    monkeypatch: Any,
) -> None:
    """La branche `IntegrityError` de `signer` : la vérification préalable n'a
    rien vu (l'autre requête n'avait pas encore écrit), la base refuse le
    doublon, et la transaction reste utilisable."""
    cliente = Inscrit()
    formation = formation_en_vente()
    achat = _acheter_pour(cliente, formation)
    seance = _seance(formation)
    assert _signer(cliente, seance).status_code == 201
    vraie = suivi._a_signe
    appels: list[bool] = []

    def aveugle_une_fois(seance_id: Any, eleve_id: Any) -> bool:
        appels.append(True)
        return False if len(appels) == 1 else vraie(seance_id, eleve_id)

    monkeypatch.setattr(suivi, "_a_signe", aveugle_une_fois)

    refus = _signer(cliente, seance, "Un autre nom")

    assert len(appels) == 2, "la base n'a pas été consultée après son refus"
    assert (refus.status_code, refus.json()["code"]) == (409, "deja_signe")
    assert Emargement.objects.get().nom_signe == "Camille Durand"

    # Contre-épreuve : une erreur d'intégrité qui N'EST PAS un doublon ne se
    # déguise pas en « déjà signé ».
    monkeypatch.setattr(suivi, "_a_signe", lambda *_: False)
    autre = _seance(formation, intitule="Autre")

    def refuse(**_: Any) -> Any:
        raise IntegrityError("une autre contrainte")

    monkeypatch.setattr(Emargement.objects, "create", refuse)
    with pytest.raises(IntegrityError, match="une autre contrainte"):
        suivi.signer(
            autre.pk, achat=achat, eleve=cliente.contact,
            nom="Camille Durand", mode="en_ligne",
        )


def test_un_ancien_membre_sans_trace_ne_se_signe_pas_sur_papier(client_admin: Any) -> None:
    cliente = Inscrit()
    parti = Collegue(cliente, "parti@exemple.fr")
    reste = Collegue(cliente, "reste@exemple.fr")
    formation, premiere, _ = _deux_lecons()
    achat = _acheter_pour(cliente, formation)
    # `reste` laisse une trace AVANT de partir ; `parti` n'en laisse aucune.
    assert _noter(reste, premiere, ouverte=True).status_code == 200
    MembreOrganisation.objects.filter(
        customer__in=[parti.contact, reste.contact]
    ).update(revoque_le=timezone.now())
    seance = _seance(formation)

    def papier(qui: Collegue) -> Any:
        return _admin(client_admin, f"{ADMIN}seances/{seance.id}/", {"emargement_papier": {
            "achat_id": str(achat.id), "eleve_id": str(qui.contact.id),
            "nom": "Dominique Martin",
        }})

    refus = papier(parti)

    assert (refus.status_code, refus.json()["code"]) == (404, "eleve_inconnu")
    assert not Emargement.objects.exists()
    # Contre-épreuve : celui qui a suivi une leçon reste un élève de cet achat.
    assert papier(reste).status_code == 200
    assert Emargement.objects.get().eleve == reste.contact


@pytest.mark.parametrize("debut_piege", ["=cmd", "+33"])
def test_l_export_neutralise_aussi_une_adresse_de_courriel_piegee(
    client_admin: Any, debut_piege: str
) -> None:
    """Les deux colonnes d'adresse : celle de l'élève, et celle de l'achat."""
    cliente = Inscrit()
    sans_membre = Inscrit(nom="Cabinet vide", email="vide@exemple.fr")
    formation = formation_en_vente()
    _acheter_pour(cliente, formation)
    orphelin = _acheter_pour(sans_membre, formation)
    piege_eleve = f"{debut_piege}eleve@exemple.fr"
    piege_achat = f"{debut_piege}achat@exemple.fr"
    Customer.objects.filter(pk=cliente.contact.pk).update(email=piege_eleve)
    AchatFormation.objects.filter(pk=orphelin.pk).update(email=piege_achat)
    MembreOrganisation.objects.filter(organisation=sans_membre.organisation).update(
        revoque_le=timezone.now()
    )

    _, lignes = _csv(client_admin, formation)

    assert sorted(ligne[1] for ligne in lignes[1:]) == sorted(
        ["'" + piege_eleve, "'" + piege_achat]
    )
    # Contre-épreuve : une adresse ordinaire sort telle quelle.
    Customer.objects.filter(pk=cliente.contact.pk).update(email="camille@exemple.fr")
    _, lignes = _csv(client_admin, formation)
    assert "camille@exemple.fr" in [ligne[1] for ligne in lignes[1:]]


@pytest.mark.parametrize("debut", [
    "2019-12-31T23:00", "2206-12-01T09:00", "9999-12-31T23:59",
    "9999-12-31T23:59-12:00", "0001-01-01T00:00+14:00",
])
def test_le_debut_d_une_seance_reste_dans_des_bornes(client_admin: Any, debut: str) -> None:
    """« 2206 » pour « 2026 » : une faute de frappe, pas une séance."""
    formation = formation_en_vente()
    existante = _seance(formation)
    charge = {"intitule": "Atelier", "debut": debut, "duree_minutes": 60}

    creation = _admin(client_admin, f"{ADMIN}{formation.id}/seances/", charge)
    modification = _admin(client_admin, f"{ADMIN}seances/{existante.id}/", {"debut": debut})

    for reponse in (creation, modification):
        assert (reponse.status_code, reponse.json()["code"]) == (400, "debut_hors_bornes")
        assert reponse.json()["champ"] == "debut"
    assert SeanceEnPresentiel.objects.count() == 1
    assert SeanceEnPresentiel.objects.get().debut == existante.debut


def test_contre_epreuve_une_seance_passee_ou_lointaine_se_saisit(client_admin: Any) -> None:
    formation = formation_en_vente()
    dans_neuf_ans = (timezone.localdate() + timedelta(days=9 * 365)).isoformat()

    for debut in ("2020-01-01T00:00", "2021-03-15T09:00", f"{dans_neuf_ans}T09:00"):
        reponse = _admin(client_admin, f"{ADMIN}{formation.id}/seances/", {
            "intitule": "Atelier", "debut": debut, "duree_minutes": 60,
        })
        assert reponse.status_code == 201, (debut, reponse.content)


def test_la_garde_d_assistance_se_ferme_quand_elle_ne_sait_pas() -> None:
    """Si `request.assistance` n'a pas été posé, le contrôle n'a pas tourné :
    on refuse, on ne conclut pas « ce n'est pas une assistance »."""
    fabrique = RequestFactory()

    inconnue = fabrique.post("/")
    refus = vues_espace._trace_refusee_en_assistance(inconnue)
    assert refus is not None
    assert (refus.status_code, json.loads(refus.content)["code"]) == (
        403, "assistance_sans_trace",
    )

    assistee = fabrique.post("/")
    vars(assistee)["assistance"] = True
    assert vues_espace._trace_refusee_en_assistance(assistee) is not None

    # Contre-épreuve : une session ordinaire, posée par le décorateur, passe.
    ordinaire = fabrique.post("/")
    vars(ordinaire)["assistance"] = False
    assert vues_espace._trace_refusee_en_assistance(ordinaire) is None


@override_settings(STRIPE_WEBHOOK_SECRET=SECRET_WEBHOOK)
@pytest.mark.parametrize(
    ("etat", "dit"),
    [
        ("ouvert", "toujours ouvert"),
        ("echu", "échu (la durée d'accès est passée)"),
        ("retire", "déjà retiré"),
    ],
)
def test_l_incident_d_un_remboursement_dit_le_vrai_etat_de_l_acces(
    etat: str, dit: str
) -> None:
    """Un accès échu n'est pas « toujours ouvert »."""
    cliente = Inscrit()
    intention = "pi_3QabcDEF456ghiJKL789"
    achat = _achat_avec_intention(cliente, intention)
    if etat == "echu":
        _echoir(achat)
    elif etat == "retire":
        AchatFormation.objects.filter(pk=achat.pk).update(revoque_le=timezone.now())
    achat.refresh_from_db()
    assert achat.etat_de_l_acces == etat

    reponse = poster_evenement(_remboursement(intention))

    assert reponse.status_code == 200, reponse.content
    assert OperationalIncident.objects.get().details["acces"] == dit


def test_les_reponses_qui_portent_des_personnes_ne_se_mettent_pas_en_cache(
    client_admin: Any,
) -> None:
    cliente = Inscrit()
    formation = formation_en_vente()
    _acheter_pour(cliente, formation)
    seance = _seance(formation)
    reponses = [
        client_admin.get(f"{ADMIN}{formation.id}/eleves/"),
        client_admin.get(f"{ADMIN}{formation.id}/eleves.csv"),
        client_admin.get(f"{ADMIN}{formation.id}/seances/"),
        client_admin.get(f"{ADMIN}seances/{seance.id}/feuille/"),
        _admin(client_admin, f"{ADMIN}seances/{seance.id}/", {"lieu": "Ailleurs"}),
        _admin(client_admin, f"{ADMIN}{formation.id}/seances/", {
            "intitule": "Atelier", "debut": "2026-12-01T09:00", "duree_minutes": 60,
        }),
    ]

    for reponse in reponses:
        assert reponse.status_code in {200, 201}, reponse.content
        assert reponse["Cache-Control"] == "no-store", reponse.request["PATH_INFO"]


@pytest.mark.parametrize(
    "nom",
    [
        "Camille‮Durand",
        "Cami​lle Durand",
        "Camille⁦ Durand",
        "Camille\x07Durand",
        "Camille\x1bDurand",
    ],
    ids=["retournement", "largeur_nulle", "isolat", "cloche", "echappement"],
)
def test_un_nom_qui_porte_un_caractere_invisible_est_refuse(
    client_admin: Any, nom: str
) -> None:
    """Il ferait afficher sur la feuille un autre nom que celui enregistré."""
    cliente = Inscrit()
    formation = formation_en_vente()
    achat = _acheter_pour(cliente, formation)
    seance = _seance(formation)

    en_ligne = _signer(cliente, seance, nom)
    papier = _admin(client_admin, f"{ADMIN}seances/{seance.id}/", {"emargement_papier": {
        "achat_id": str(achat.id), "eleve_id": str(cliente.contact.id), "nom": nom,
    }})

    for reponse in (en_ligne, papier):
        assert (reponse.status_code, reponse.json()["code"]) == (400, "nom_illisible")
    assert not Emargement.objects.exists()


@pytest.mark.parametrize(
    ("saisi", "garde"),
    [
        ("Zoé D'Arçon-Müller", "Zoé D'Arçon-Müller"),
        ("Camille Durand", "Camille Durand"),
        ("Camille\tDurand\n", "Camille Durand"),
        ("李 小龍", "李 小龍"),
    ],
)
def test_contre_epreuve_un_nom_ordinaire_passe(saisi: str, garde: str) -> None:
    assert suivi.nom_signe(saisi) == garde


def test_la_duree_d_acces_a_une_valeur_par_defaut_DANS_la_base() -> None:
    """Un code d'avant ce champ, redéployé sur le nouveau schéma, crée une
    formation sans nommer la colonne : la base doit savoir quoi y mettre."""
    modele = Formation(titre="Ancien code", slug="ancien-code")
    champs = [
        champ for champ in Formation._meta.concrete_fields
        if champ.name != "duree_d_acces_mois"
    ]
    valeurs = [
        champ.get_db_prep_save(champ.pre_save(modele, True), connection)
        for champ in champs
    ]
    colonnes = ", ".join(connection.ops.quote_name(champ.column) for champ in champs)
    table = connection.ops.quote_name(Formation._meta.db_table)

    with connection.cursor() as curseur:
        curseur.execute(
            f"INSERT INTO {table} ({colonnes}) VALUES ({', '.join(['%s'] * len(champs))})",  # noqa: S608
            valeurs,
        )

    assert Formation.objects.get(slug="ancien-code").duree_d_acces_mois == 0


def test_decocher_puis_recocher_ne_rajeunit_pas_la_preuve() -> None:
    cliente = Inscrit()
    formation, premiere, _ = _deux_lecons()
    _acheter_pour(cliente, formation)
    _noter(cliente, premiere, terminee=True)
    origine = SuiviDeLecon.objects.get().terminee_le
    assert origine is not None
    assert SuiviDeLecon.objects.get().premiere_fin_le == origine
    # On vieillit la preuve : elle date d'il y a trois mois.
    il_y_a_trois_mois = origine - timedelta(days=90)
    SuiviDeLecon.objects.update(
        terminee_le=il_y_a_trois_mois, premiere_fin_le=il_y_a_trois_mois
    )

    decochee = _noter(cliente, premiere, terminee=False)

    assert decochee.json()["lecon"]["terminee"] is False
    trace = SuiviDeLecon.objects.get()
    assert (trace.terminee_le, trace.premiere_fin_le) == (None, il_y_a_trois_mois)

    recochee = _noter(cliente, premiere, terminee=True)

    # La date d'ORIGINE, pas celle d'aujourd'hui.
    assert recochee.json()["lecon"]["terminee_le"] == il_y_a_trois_mois.isoformat()
    trace = SuiviDeLecon.objects.get()
    assert (trace.terminee_le, trace.premiere_fin_le) == (
        il_y_a_trois_mois, il_y_a_trois_mois,
    )

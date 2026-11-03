"""Travailler par client : une fiche, ses projets, des études pré-remplies.

Une consultante produit pour une même personne une étude de marché aujourd'hui,
un business plan demain. Elle effaçait le questionnaire et retapait le projet à
chaque étude. Ces tests verrouillent les trois propriétés qui rendent la fiche
utile — et sûre :

- une commande passée depuis un projet porte ce projet, et son NOM : c'est sur
  lui que l'héritage du socle reconnaît le même dossier ;
- les réponses déjà données pour ce projet pré-remplissent le livrable suivant,
  sauf celles qui ne valaient que pour une étude ;
- deux clients ne partagent jamais un nom de projet, sans quoi leurs chiffres
  se mélangeraient (01/11/2026, « ça a mélangé les dossiers »).
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from generation.models import GenerationJob
from generation.socle import heritage
from orders.models import Order
from organisations import commandes, credits, formulaires, projets
from organisations.models import ClientFinal, Projet, RoleOrganisation
from tests.test_lot4_commander import SAISIE_EM, Abonne, charge

pytestmark = pytest.mark.django_db


@pytest.fixture
def evangeline() -> Abonne:
    return Abonne("Cabinet Evangeline", "evangeline-projets@example.com")


@pytest.fixture
def api() -> Client:
    return Client()


@pytest.fixture
def dupont(evangeline: Abonne) -> ClientFinal:
    return ClientFinal.objects.create(
        organisation=evangeline.organisation,
        raison_sociale="Dupont & Fils",
        secteur="boulangerie artisanale",
        pays="France",
        ville="Lille",
    )


def _post(api: Client, abonne: Abonne, chemin: str, corps: dict[str, Any]) -> Any:
    return api.post(
        chemin,
        data=json.dumps(corps, ensure_ascii=False),
        content_type="application/json",
        headers=abonne.entetes,
    )


def _commande(
    abonne: Abonne, type_document: str, saisie: dict[str, str], projet: Projet | None
) -> GenerationJob:
    """Crée la commande sans la lancer : ces tests jugent le brief, pas la production."""
    credits.crediter(abonne.organisation, 1, motif="Dotation de test")
    return commandes.creer_commande(
        abonne.organisation,
        abonne.contact,
        type_document=type_document,
        saisie=saisie,
        projet=projet,
    )


# ── La fiche, ses projets ────────────────────────────────────────────────────


def test_on_ajoute_un_client_puis_un_projet_et_la_fiche_les_compte(
    api: Client, evangeline: Abonne
) -> None:
    cree = _post(
        api,
        evangeline,
        "/api/espace/clients-finaux/",
        {
            "raison_sociale": "Dupont & Fils",
            "secteur": "boulangerie",
            "ville": "Lille",
        },
    )
    assert cree.status_code == 201
    client_id = charge(cree)["id"]

    projet = _post(
        api,
        evangeline,
        f"/api/espace/clients-finaux/{client_id}/projets/",
        {"nom": "Fournil du Vieux-Lille"},
    )
    assert projet.status_code == 201
    assert charge(projet)["nom"] == "Fournil du Vieux-Lille"

    fiche = charge(api.get(f"/api/espace/clients-finaux/{client_id}/", headers=evangeline.entetes))
    assert [p["nom"] for p in fiche["projets"]] == ["Fournil du Vieux-Lille"]
    assert fiche["dossiers"] == []

    liste = charge(api.get("/api/espace/clients-finaux/", headers=evangeline.entetes))
    assert liste["clients"][0]["nb_projets"] == 1
    assert liste["clients"][0]["nb_dossiers"] == 0


def test_un_projet_sans_nom_est_refuse(
    api: Client, evangeline: Abonne, dupont: ClientFinal
) -> None:
    reponse = _post(
        api, evangeline, f"/api/espace/clients-finaux/{dupont.id}/projets/", {"nom": "  "}
    )
    assert reponse.status_code == 400


def test_deux_clients_ne_partagent_pas_un_nom_de_projet(
    api: Client, evangeline: Abonne, dupont: ClientFinal
) -> None:
    """Même nom, même clé d'héritage : les chiffres de l'un iraient chez l'autre.

    La casse et les accents ne suffisent pas à distinguer deux projets — ce sont
    précisément ce que l'héritage ignore.
    """
    martin = ClientFinal.objects.create(
        organisation=evangeline.organisation, raison_sociale="Martin SAS"
    )
    projets.creer_projet(dupont, "Café Lumière")

    reponse = _post(
        api,
        evangeline,
        f"/api/espace/clients-finaux/{martin.id}/projets/",
        {"nom": "cafe  LUMIERE"},
    )
    assert reponse.status_code == 409
    assert "Dupont & Fils" in charge(reponse)["error"]
    assert not martin.projets.exists()


def test_le_meme_nom_reste_libre_dans_une_autre_organisation(
    evangeline: Abonne, dupont: ClientFinal
) -> None:
    """Contre-épreuve : l'unicité est celle d'une abonnée, pas de la plateforme."""
    autre = Abonne("Cabinet Rivage", "rivage-projets@example.com")
    chez_autre = ClientFinal.objects.create(organisation=autre.organisation, raison_sociale="X")
    projets.creer_projet(dupont, "Café Lumière")
    projet, _ = projets.creer_projet(chez_autre, "Café Lumière")
    assert projet.client == chez_autre


# ── La commande depuis un projet ─────────────────────────────────────────────


def test_le_nom_du_projet_est_impose_a_la_commande(evangeline: Abonne, dupont: ClientFinal) -> None:
    """La saisie ne peut pas renommer le projet : ce nom est l'identité du dossier."""
    projet, _ = projets.creer_projet(dupont, "Fournil du Vieux-Lille")
    job = _commande(evangeline, "market_study", {**SAISIE_EM, "PROJET": "Autre chose"}, projet)

    assert job.order.projet == projet
    assert job.order.intake_submission.normalized_variables["PROJET"] == "Fournil du Vieux-Lille"


def test_la_cle_du_projet_est_celle_de_l_heritage(evangeline: Abonne, dupont: ClientFinal) -> None:
    """Les deux réductions du nom doivent rester d'accord.

    Jugé sur une vraie commande, par la fonction de l'héritage elle-même : si
    l'une change sans l'autre, une fiche ne retrouverait plus les chiffres de
    son étude précédente, ou en retrouverait d'autres.
    """
    projet, _ = projets.creer_projet(dupont, "  Café   Lumière ÉTÉ ")
    job = _commande(evangeline, "market_study", SAISIE_EM, projet)
    assert heritage._projet(job) == projet.cle  # noqa: SLF001


def test_une_saisie_libre_au_nom_d_un_projet_lui_est_rattachee(
    evangeline: Abonne, dupont: ClientFinal
) -> None:
    """L'héritage la traite déjà comme le même dossier : la fiche doit la montrer."""
    projet, _ = projets.creer_projet(dupont, "Fournil du Vieux-Lille")
    job = _commande(
        evangeline, "market_study", {**SAISIE_EM, "PROJET": "fournil du vieux-lille"}, None
    )
    assert job.order.projet == projet


def test_une_saisie_libre_sans_homonyme_n_a_pas_de_projet(evangeline: Abonne) -> None:
    """Contre-épreuve : le parcours libre d'avant reste ce qu'il était."""
    job = _commande(evangeline, "market_study", SAISIE_EM, None)
    assert job.order.projet is None


def test_les_dossiers_d_avant_la_fiche_y_sont_rattaches(
    api: Client, evangeline: Abonne, dupont: ClientFinal
) -> None:
    """Ses études déjà produites apparaissent sur la fiche créée après coup."""
    ancien = _commande(evangeline, "market_study", {**SAISIE_EM, "PROJET": "Maison  LUMEN"}, None)
    ailleurs = _commande(evangeline, "market_study", {**SAISIE_EM, "PROJET": "Autre projet"}, None)

    reponse = _post(
        api, evangeline, f"/api/espace/clients-finaux/{dupont.id}/projets/", {"nom": "Maison Lumen"}
    )
    assert charge(reponse)["dossiers_rattaches"] == 1

    fiche = charge(api.get(f"/api/espace/clients-finaux/{dupont.id}/", headers=evangeline.entetes))
    assert [d["id"] for d in fiche["dossiers"]] == [str(ancien.id)]
    assert fiche["projets"][0]["nb_dossiers"] == 1
    assert Order.objects.get(id=ailleurs.order_id).projet is None


def test_un_projet_archive_ne_se_commande_plus(evangeline: Abonne, dupont: ClientFinal) -> None:
    projet, _ = projets.creer_projet(dupont, "Fournil")
    projet.archive_le = timezone.now()
    projet.save()
    with pytest.raises(commandes.CommandeRefuseeError, match="archivé"):
        _commande(evangeline, "market_study", SAISIE_EM, projet)


def test_commander_depuis_l_api_avec_un_projet(
    api: Client, evangeline: Abonne, dupont: ClientFinal
) -> None:
    projet, _ = projets.creer_projet(dupont, "Fournil du Vieux-Lille")
    credits.crediter(evangeline.organisation, 1, motif="Dotation de test")
    reponse = _post(
        api,
        evangeline,
        "/api/espace/commander/",
        {
            "type": "market_study",
            "saisie": SAISIE_EM,
            "projet": str(projet.id),
        },
    )
    assert reponse.status_code == 202
    job = GenerationJob.objects.get(id=charge(reponse)["job_id"])
    assert job.order.projet == projet

    livrables = charge(api.get("/api/espace/livrables/", headers=evangeline.entetes))["livrables"]
    assert livrables[0]["projet"] == {
        "id": str(projet.id),
        "nom": projet.nom,
        "client_id": str(dupont.id),
        "client": "Dupont & Fils",
    }


# ── Le pré-remplissage ───────────────────────────────────────────────────────


def test_le_business_plan_reprend_ce_que_l_etude_de_marche_a_dit(
    evangeline: Abonne, dupont: ClientFinal
) -> None:
    """Le cas du besoin : une étude de marché aujourd'hui, un business plan demain."""
    projet, _ = projets.creer_projet(dupont, "Fournil du Vieux-Lille")
    _commande(evangeline, "market_study", SAISIE_EM, projet)

    reponses = projets.reponses_connues(projet, "business_plan")

    assert reponses["PROJET"] == "Fournil du Vieux-Lille"
    for commune in ("SECTEUR", "PAYS", "ZONE", "POSITIONNEMENT", "CLIENTELE_CIBLE", "CONCURRENTS"):
        assert reponses[commune] == SAISIE_EM[commune], commune


def test_ce_qui_ne_valait_que_pour_une_etude_n_est_pas_repris(
    evangeline: Abonne, dupont: ClientFinal
) -> None:
    """Reprendre les questions d'une étude de marché ferait chercher à la
    stratégie la réponse due à l'étude de marché."""
    projet, _ = projets.creer_projet(dupont, "Fournil")
    _commande(evangeline, "market_study", SAISIE_EM, projet)

    reponses = projets.reponses_connues(projet, "business_strategy")
    propres = {
        c.identifiant for c in formulaires.FORMULAIRES["business_strategy"].champs if not c.reprise
    }
    assert "DEMANDES_SPECIFIQUES" in propres
    assert not propres & set(reponses)


def test_une_question_est_reprise_partout_ou_nulle_part() -> None:
    """Un identifiant déclaré dans plusieurs questionnaires porte UNE réponse.

    Vu dans le navigateur : le business plan déclarait son propre
    `ELEMENTS_A_RETENIR` sans `reprise=False`, et la réponse de l'étude de
    marché s'y reprenait. On vise la classe : aucun identifiant n'a deux statuts.
    """
    statuts: dict[str, set[bool]] = {}
    for questionnaire in formulaires.FORMULAIRES.values():
        for champ in questionnaire.champs:
            statuts.setdefault(champ.identifiant, set()).add(champ.reprise)
    assert {cle for cle, vus in statuts.items() if len(vus) > 1} == set()


def test_la_reponse_la_plus_recente_l_emporte(evangeline: Abonne, dupont: ClientFinal) -> None:
    projet, _ = projets.creer_projet(dupont, "Fournil")
    _commande(evangeline, "market_study", SAISIE_EM, projet)
    _commande(
        evangeline,
        "competitor_study",
        {**SAISIE_EM, "STADE_ACTUEL": "En activité", "POSITIONNEMENT": "Premium assumé."},
        projet,
    )
    assert projets.reponses_connues(projet, "market_study")["POSITIONNEMENT"] == "Premium assumé."


def test_un_projet_neuf_reprend_la_fiche_du_client(dupont: ClientFinal) -> None:
    projet, _ = projets.creer_projet(dupont, "Fournil")
    assert projets.reponses_connues(projet, "market_study") == {
        "PROJET": "Fournil",
        "SECTEUR": "boulangerie artisanale",
        "PAYS": "France",
        "ZONE": "Lille",
    }


def test_les_reponses_sont_servies_par_l_api(
    api: Client, evangeline: Abonne, dupont: ClientFinal
) -> None:
    projet, _ = projets.creer_projet(dupont, "Fournil")
    donnees = charge(
        api.get(
            f"/api/espace/projets/{projet.id}/reponses/business_plan/", headers=evangeline.entetes
        )
    )
    assert donnees["client"]["nom"] == "Dupont & Fils"
    assert donnees["reponses"]["PROJET"] == "Fournil"


# ── Cloisonnement et droits ──────────────────────────────────────────────────


def test_une_autre_abonnee_ne_voit_ni_la_fiche_ni_le_projet(
    api: Client, evangeline: Abonne, dupont: ClientFinal
) -> None:
    projet, _ = projets.creer_projet(dupont, "Fournil")
    intruse = Abonne("Cabinet Rivage", "rivage-intruse@example.com")
    credits.crediter(intruse.organisation, 1, motif="Dotation de test")

    assert (
        api.get(f"/api/espace/clients-finaux/{dupont.id}/", headers=intruse.entetes).status_code
        == 404
    )
    assert (
        api.get(
            f"/api/espace/projets/{projet.id}/reponses/market_study/", headers=intruse.entetes
        ).status_code
        == 404
    )
    assert (
        _post(
            api,
            intruse,
            "/api/espace/commander/",
            {
                "type": "market_study",
                "saisie": SAISIE_EM,
                "projet": str(projet.id),
            },
        ).status_code
        == 404
    )
    assert (
        _post(
            api, intruse, f"/api/espace/clients-finaux/{dupont.id}/projets/", {"nom": "Intrusion"}
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "chemin",
    [
        "/api/espace/clients-finaux/pas-un-uuid/",
        "/api/espace/projets/pas-un-uuid/reponses/market_study/",
    ],
)
def test_un_identifiant_tape_a_la_main_rend_404_et_non_500(
    api: Client, evangeline: Abonne, chemin: str
) -> None:
    assert api.get(chemin, headers=evangeline.entetes).status_code == 404


def test_un_role_lecture_consulte_mais_n_ajoute_pas_de_projet(
    api: Client, dupont: ClientFinal
) -> None:
    lectrice = Abonne(
        "Cabinet Lecture", "lecture-projets@example.com", role=RoleOrganisation.LECTURE
    )
    chez_elle = ClientFinal.objects.create(organisation=lectrice.organisation, raison_sociale="Y")
    assert (
        api.get(f"/api/espace/clients-finaux/{chez_elle.id}/", headers=lectrice.entetes).status_code
        == 200
    )
    assert (
        _post(
            api, lectrice, f"/api/espace/clients-finaux/{chez_elle.id}/projets/", {"nom": "Z"}
        ).status_code
        == 403
    )

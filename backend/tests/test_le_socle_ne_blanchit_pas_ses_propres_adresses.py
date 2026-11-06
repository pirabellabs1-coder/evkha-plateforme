"""Un domaine inventé DANS LE SOCLE s'autorisait lui-même.

## Ce qui a été mesuré

Reprise `ecb28fa8` de l'étude de la concurrence SUN TZU, le 06/11/2026. Trois
adresses du document livré ne résolvaient pas au DNS :

    culinaconcepts.com        -> signalee par le gate
    citysuper.com.tw          -> AUCUN motif
    thefrenchgrocer.com.sg    -> AUCUN motif

La différence entre les trois n'est pas leur forme : c'est leur place. Les deux
dernières figuraient dans `socle.concurrents[].site_web`, et `_hotes_admis`
versait ce champ dans la liste blanche. La première n'existait qu'en prose de
chapitre, donc elle a été interrogée.

Aucune des trois ne figure dans le brief de la cliente, vérifié sur
`/api/dashboard/jobs/<id>/brief/`.

## Pourquoi c'est la règle 9

Le socle est écrit par le modèle. Le faire entrer dans la liste blanche, c'est
laisser l'objet jugé délivrer son propre laissez-passer : le contrôle et son
évidence se confondent. Et la classe n'est pas « le socle » (règle 4) — c'est
**tout texte produit par le modèle**.

## Ce que le correctif ne casse pas

`hotes_admis` ne sert qu'à SAUTER la requête DNS ; seul un nom qui échoue
explicitement fait un motif. Un domaine réel résout, qu'il soit admis ou non.
La liste ne protège donc que les domaines MORTS qu'un HUMAIN nous a donnés —
et le site qu'une cliente a cité elle-même reste admis, parce qu'il arrive par
ses réponses, pas par le socle.

Ces tests échouent sur le code d'avant : `_hotes_admis` y rendait les sites du
socle.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.gate import _hotes_admis
from generation.models import GenerationJob, SocleDonnees, SocleStatut
from generation.services import bootstrap_generation_job
from intake.models import IntakeSource, IntakeStatus, IntakeSubmission
from orders.models import Order

#: Le site que la CLIENTE a nommé dans ses réponses : jamais accusé.
SITE_DU_CLIENT = "concurrent-cite-par-la-cliente.fr"
#: Le site que le MODÈLE a écrit dans le socle : à interroger.
#:
#: Un domaine à UN SEUL niveau, volontairement. Avec « citysuper.com.tw »
#: — l'autre adresse morte de la même étude — le test passait sur le code
#: d'avant comme sur celui d'après : `hotes_cites` tronquait alors
#: « .com.tw » en « .com », si bien que l'hôte cherché n'entrait jamais dans
#: la liste blanche, correctif ou pas. Vert pour la mauvaise raison, deuxième
#: fois sur ce fichier. Un test doit échouer sur le code d'avant (règle 6), et
#: ne mesurer QU'UNE chose à la fois : la troncature est verrouillée ailleurs,
#: par `test_une_adresse_vers_un_domaine_inexistant_est_un_lien_mort.py`.
SITE_DU_MODELE = "culinaconcepts.com"


def _socle_avec(site: str) -> dict[str, object]:
    return {
        "secteur": "Épicerie fine à l'export",
        "zone": {"pays": "Taïwan"},
        "date_socle": date(2026, 11, 6).isoformat(),
        "concurrents": [
            {
                "nom": "City'Super Taïwan",
                "type": "direct",
                "emplacement": "Taïwan",
                "site_web": site,
            }
        ],
    }


def _socle_pose(job: GenerationJob, site: str) -> None:
    """Pose le socle ET vérifie qu'il est relu.

    Un `contenu` invalide ferait rendre `None` à `socle_verrouille`, et le test
    passerait alors sur le code d'AVANT comme sur celui d'après — vert pour la
    mauvaise raison. C'est arrivé à l'écriture de ce fichier : `zone` était une
    chaîne au lieu d'un objet. Règle 1 : un contrôle qui n'a rien à comparer
    est un échec.
    """
    from generation.socle import socle_verrouille  # noqa: PLC0415

    SocleDonnees.objects.create(
        job=job, statut=SocleStatut.VALIDE, contenu=_socle_avec(site)
    )
    relu = socle_verrouille(job)
    assert relu is not None, "socle illisible : la doublure ne prouverait rien"
    assert [c.site_web for c in relu.concurrents] == [site]


def _dossier(variables: dict[str, str]) -> GenerationJob:
    offre, _ = Offer.objects.get_or_create(
        slug="verif-hotes-admis",
        defaults={"name": "Verif", "deliverable_type": DeliverableType.COMPETITOR_STUDY},
    )
    contact, _ = Customer.objects.get_or_create(email="verif-hotes-admis@test.local")
    commande = Order.objects.create(
        systeme_order_id=f"verif-hotes-{uuid.uuid4().hex[:8]}",
        customer=contact,
        offer=offre,
    )
    IntakeSubmission.objects.create(
        order=commande,
        status=IntakeStatus.NORMALIZED,
        source=IntakeSource.MANUAL,
        normalized_variables=variables,
    )
    return bootstrap_generation_job(commande.intake_submission)


@pytest.mark.django_db
def test_un_site_de_concurrent_ecrit_par_le_modele_n_est_pas_admis() -> None:
    """LE défaut : le socle versait ses propres adresses dans la liste blanche."""
    job = _dossier({"SECTEUR": "Épicerie fine"})
    _socle_pose(job, SITE_DU_MODELE)

    assert SITE_DU_MODELE not in _hotes_admis(job)


@pytest.mark.django_db
def test_le_site_que_la_cliente_a_nomme_reste_admis() -> None:
    """CONTRE-ÉPREUVE : on n'accuse pas la cliente d'avoir inventé un domaine.

    Le même site est à la fois dans ses réponses et dans le socle. Il doit
    rester admis — c'est elle qui nous l'a donné, et le socle n'y change rien.
    """
    job = _dossier({"CONCURRENTS": f"Notre rival principal ({SITE_DU_CLIENT})"})
    _socle_pose(job, SITE_DU_CLIENT)

    assert SITE_DU_CLIENT in _hotes_admis(job)


@pytest.mark.django_db
def test_les_portails_des_prompts_restent_admis() -> None:
    """CONTRE-ÉPREUVE : nos propres fichiers de prompts citent des institutions.

    Ils distribuent eux-mêmes ces adresses au modèle : les lui reprocher
    ensuite serait un motif faux (règle 2). Au moins un portail connu doit
    rester dans la liste, socle ou pas.
    """
    job = _dossier({"SECTEUR": "Épicerie fine"})
    _socle_pose(job, SITE_DU_MODELE)

    admis = _hotes_admis(job)

    assert admis, "la liste blanche ne doit pas devenir vide"
    assert any(hote.endswith("insee.fr") or hote.endswith("gouv.fr") for hote in admis)

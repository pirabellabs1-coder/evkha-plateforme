"""Le cache de prompt était mesurable en base, et invisible depuis le dehors.

## Ce qui n'allait pas

`ChapterGeneration` porte `cache_read_tokens` et `cache_write_tokens` depuis la
migration 0014, précisément pour qu'une régression du cache se voie. Mais aucun
de nos points de lecture ne les publiait : ni la liste des dossiers, ni la
fiche d'un dossier. Seul l'admin Django les montrait, dossier par dossier, à la
main.

Conséquence mesurée sur ce dépôt : le 08/08/2026, une entrée de
`journal_generations.md` annonçant « le cache ne s'active jamais, −40 % à
récupérer » a été prise pour un état courant alors que le gain était déjà
acquis. Trois relectures ont conclu faux le même jour pour la même raison. Un
chiffre qu'on ne peut pas aller chercher se remplace par une opinion
(règle 8 : une conclusion tirée du mauvais artefact est pire qu'un silence).

## Ce que le rapport doit dire

Les deux compteurs SÉPARÉS, jamais leur somme : une écriture de cache coûte
plus cher qu'un jeton ordinaire, une lecture dix fois moins. Leur total ne dit
donc rien du tout. C'est leur RAPPORT qui tranche — le socle, la base
concurrents et la consigne de livrable sont identiques pour tous les chapitres
d'un dossier, donc un dossier sain écrit une fois et lit vingt fois.

Ces tests échouent sur le code d'avant : les trois clés n'existaient pas.
"""
from __future__ import annotations

from typing import Any

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.models import ChapterGeneration, GenerationJob, JobStatus
from orders.models import Order


def _dossier(slug: str) -> GenerationJob:
    offer = Offer.objects.create(
        name="Business plan",
        slug=slug,
        deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    customer = Customer.objects.create(email=f"{slug}@example.com")
    order = Order.objects.create(
        systeme_order_id=f"order_{slug}", customer=customer, offer=offer
    )
    return GenerationJob.objects.create(
        order=order,
        deliverable_type=DeliverableType.BUSINESS_PLAN,
        status=JobStatus.PENDING,
    )


def _chapitre(job: GenerationJob, numero: int, *, lu: int, ecrit: int) -> None:
    ChapterGeneration.objects.create(
        job=job,
        chapter_number=numero,
        chapter_title=f"Chapitre {numero}",
        prompt_key=f"business_plan.ch{numero}",
        cache_read_tokens=lu,
        cache_write_tokens=ecrit,
    )


@pytest.mark.django_db
def test_la_fiche_d_un_dossier_publie_les_deux_compteurs(client_admin: Any) -> None:
    """Un dossier sain : une écriture au premier chapitre, des lectures ensuite."""
    job = _dossier("bp-cache-sain")
    _chapitre(job, 1, lu=0, ecrit=12_000)
    _chapitre(job, 2, lu=12_000, ecrit=0)
    _chapitre(job, 3, lu=12_000, ecrit=0)

    reponse = client_admin.get(f"/api/dashboard/jobs/{job.id}/")

    assert reponse.status_code == 200
    fiche = reponse.json()
    assert fiche["cache_read_tokens"] == 24_000
    assert fiche["cache_write_tokens"] == 12_000
    # 24 000 / 36 000 : deux tiers des jetons mis en cache ont été RELUS.
    assert fiche["cache_part_lue"] == pytest.approx(0.667, abs=0.001)


@pytest.mark.django_db
def test_un_cache_qui_se_reecrit_a_chaque_chapitre_se_voit(client_admin: Any) -> None:
    """La régression que ces compteurs existent pour attraper.

    C'est le défaut réel du dossier `2490c7cf` : le socle voyageait dans le
    message utilisateur, que rien ne met en cache, et chaque chapitre le
    repayait au tarif plein. La part lue s'effondre — un rapport, pas une somme.
    """
    job = _dossier("bp-cache-casse")
    for numero in (1, 2, 3):
        _chapitre(job, numero, lu=0, ecrit=12_000)

    fiche = client_admin.get(f"/api/dashboard/jobs/{job.id}/").json()

    assert fiche["cache_write_tokens"] == 36_000
    assert fiche["cache_part_lue"] == 0.0
    # La somme, elle, est IDENTIQUE au dossier sain du test précédent : c'est
    # exactement pourquoi elle ne doit pas être publiée seule.
    assert fiche["cache_read_tokens"] + fiche["cache_write_tokens"] == 36_000


@pytest.mark.django_db
def test_un_dossier_sans_aucun_cache_ne_rend_pas_zero_pour_cent(
    client_admin: Any,
) -> None:
    """Contre-épreuve : « rien à mesurer » n'est pas « zéro » (règle 1).

    Un dossier qui n'a encore produit aucun chapitre n'a pas un cache à 0 % ;
    il n'a pas de cache du tout. Rendre `0.0` ici ferait lire une panne sur un
    dossier qui vient de démarrer — et ferait diviser par zéro au passage.
    """
    job = _dossier("bp-cache-vide")

    fiche = client_admin.get(f"/api/dashboard/jobs/{job.id}/").json()

    assert fiche["cache_read_tokens"] == 0
    assert fiche["cache_write_tokens"] == 0
    assert fiche["cache_part_lue"] is None


@pytest.mark.django_db
def test_la_liste_des_dossiers_porte_la_meme_mesure(client_admin: Any) -> None:
    """Même constructeur, donc même vérité : une seule source (règle 5).

    La liste et la fiche passent toutes deux par `_job_summary`. Si un jour
    l'une calculait le rapport de son côté, les deux divergeraient — c'est
    arrivé sur ce même écran pour le bouton de reprise.
    """
    job = _dossier("bp-cache-liste")
    _chapitre(job, 1, lu=9_000, ecrit=1_000)

    ligne = client_admin.get("/api/dashboard/jobs/").json()[0]
    fiche = client_admin.get(f"/api/dashboard/jobs/{job.id}/").json()

    assert ligne["cache_read_tokens"] == fiche["cache_read_tokens"] == 9_000
    assert ligne["cache_part_lue"] == fiche["cache_part_lue"] == 0.9

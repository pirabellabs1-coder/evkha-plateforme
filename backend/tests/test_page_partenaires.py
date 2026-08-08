"""Le catalogue public : ouvert, et rien de plus qu'ouvert.

La page partenaires s'adresse à des visiteurs sans compte. Son point d'entrée
est donc le SEUL de l'application à répondre sans jeton — ce qui en fait aussi
le seul endroit où une fuite de données ne serait arrêtée par personne.

Ces tests verrouillent les deux faces : il répond sans authentification, et il
ne répond QUE le catalogue commercial.
"""
from __future__ import annotations

import pytest
from django.core.management import call_command
from django.test import Client

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _formules(db: object) -> None:
    """Les formules viennent de `seed_formules`, comme en production.

    Elles ne sont PAS semées par une migration : le §11 exige qu'une formule
    se crée et se modifie depuis l'administration sans déploiement, et une
    migration réécrirait en silence un tarif ajusté à la main. La commande,
    elle, laisse par défaut les formules existantes intactes.

    Les fabriquer ici à la main referait une deuxième source de vérité — celle
    du test — qui pourrait affirmer que la page est juste alors que la commande
    livre autre chose (règle 5).
    """
    call_command("seed_formules", "--forcer", verbosity=0)

#: Tout ce que la page a besoin de savoir, et rien d'autre. Une clé qui
#: apparaîtrait sans figurer ici est une fuite : `reference_paiement` (le
#: tarif Stripe), les identifiants internes, les compteurs d'abonnés n'ont
#: aucune raison de sortir.
CHAMPS_AUTORISES = {
    "code",
    "libelle",
    "credits_par_echeance",
    "prix_mensuel_cents",
    "prix_credit_supplementaire_cents",
    "cout_par_livrable_cents",
    "devise",
    "avantages",
    "mise_en_avant",
}


def test_le_catalogue_repond_sans_authentification(client: Client) -> None:
    reponse = client.get("/api/public/formules/")
    assert reponse.status_code == 200, reponse.status_code
    assert reponse.json()["formules"], "catalogue vide"


def test_le_catalogue_n_expose_rien_d_autre(client: Client) -> None:
    """Contre-épreuve du caractère public : ouvert ne veut pas dire bavard."""
    for formule in client.get("/api/public/formules/").json()["formules"]:
        surplus = set(formule) - CHAMPS_AUTORISES
        assert not surplus, f"champs exposes sans raison : {sorted(surplus)}"


def test_la_commande_de_semis_produit_les_quatre_formules() -> None:
    from organisations.models import Formule

    codes = set(Formule.objects.filter(active=True).values_list("code", flat=True))
    assert {"solo", "pro", "pro-plus", "structure"} <= codes


def test_les_avantages_communs_ne_sont_pas_recopies_formule_par_formule() -> None:
    """Règle 5 : quatre copies d'une même phrase finissent par diverger."""
    from organisations.management.commands.seed_formules import AVANTAGES_COMMUNS
    from organisations.models import Formule

    for formule in Formule.objects.filter(active=True):
        assert set(AVANTAGES_COMMUNS) <= set(formule.avantages), formule.code

    structure = Formule.objects.get(code="structure")
    assert "Convention-cadre possible" in structure.avantages
    assert "Interlocutrice dédiée" in structure.avantages


def test_le_cout_par_livrable_decoule_des_deux_autres_chiffres(client: Client) -> None:
    """Règle 5 : il est CALCULÉ, jamais stocké.

    S'il était un troisième champ en base, il pourrait contredire le prix et
    la dotation — et c'est le chiffre que la page met en avant (« 42,90 à
    64,50 € »). Les valeurs attendues sont celles affichées au public.
    """
    attendus = {"solo": 6450, "pro": 6300, "pro-plus": 4980, "structure": 4290}
    for formule in client.get("/api/public/formules/").json()["formules"]:
        calcule = round(
            formule["prix_mensuel_cents"] / formule["credits_par_echeance"]
        )
        assert formule["cout_par_livrable_cents"] == calcule
        assert formule["cout_par_livrable_cents"] == attendus[formule["code"]], (
            f"{formule['libelle']} : le tarif public a change"
        )


def test_une_seule_formule_est_mise_en_avant(client: Client) -> None:
    """La page porte un unique « CHOISIR LA FORMULE PRO »."""
    formules = client.get("/api/public/formules/").json()["formules"]
    avant = [f["code"] for f in formules if f["mise_en_avant"]]
    assert avant == ["pro"], avant

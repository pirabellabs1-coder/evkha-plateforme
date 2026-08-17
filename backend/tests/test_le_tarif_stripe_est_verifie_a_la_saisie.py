"""Un identifiant de tarif erroné doit être refusé à la saisie, pas au clic.

Le champ `reference_paiement` était saisissable sans aucun contrôle. Trois
façons de se tromper, et les trois ne se manifestaient qu'au moment où un
client cliquait sur « Souscrire » :

1. un identifiant inexistant — faute de frappe, ou tarif supprimé côté Stripe ;
2. un tarif **ponctuel** là où l'abonnement attend un tarif récurrent : Stripe
   accepte la session, puis rien ne se renouvelle jamais ;
3. un tarif dont le **montant** diffère du prix affiché sur la page
   partenaires. C'est le pire : rien ne le signale sur nos écrans, et l'abonné
   le découvre sur son relevé bancaire.

Le troisième cas est la raison d'être de ce contrôle. Les deux premiers
échouent bruyamment tôt ou tard ; celui-là facture le mauvais montant en
silence, et se découvre par une réclamation.
"""
from __future__ import annotations

from typing import Any

import pytest

from organisations.admin import FormuleForm
from organisations.models import ReportCredits

BASE = {
    "code": "solo",
    "libelle": "Solo",
    "credits_par_echeance": 2,
    "prix_mensuel_cents": 12900,
    "devise": "EUR",
    "report_credits": ReportCredits.AUCUN,
    "plafond_report": 0,
    "regenerations_offertes": 1,
    "prix_credit_supplementaire_cents": 5900,
    "avantages": [],
    "rang": 1,
    "mise_en_avant": False,
    "active": True,
}


def test_le_formulaire_couvre_tous_les_champs_du_modele() -> None:
    """Un champ ajouté au modèle ne doit pas disparaître de l'administration.

    `fields = "__all__"` exposerait automatiquement tout nouveau champ, y
    compris un champ interne qu'on ne voulait pas rendre modifiable. Les
    énumérer évite cela, mais crée le risque inverse : un champ ajouté au
    modèle et oublié ici devient invisible, sans erreur, et personne ne peut
    plus le régler. Ce test tient les deux bouts.
    """
    from organisations.models import Formule

    attendus = {
        champ.name
        for champ in Formule._meta.fields
        if champ.editable and not champ.auto_created
    }
    declares = set(FormuleForm.Meta.fields)

    assert declares == attendus, (
        f"champs du modele absents du formulaire : {sorted(attendus - declares)} ; "
        f"champs declares qui n'existent plus : {sorted(declares - attendus)}"
    )


@pytest.fixture
def stripe_repond(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Un Stripe de comédie : on choisit ce que `Price.retrieve` renvoie.

    Aucun appel réseau. Le vrai Stripe n'a pas sa place dans une suite de
    tests — il facturerait, il serait lent, et il rendrait le résultat
    dépendant de l'état d'un compte externe.
    """
    import stripe
    from paiement import stripe_api

    monkeypatch.setattr(stripe_api, "cle_secrete", lambda: "sk_test_de_comedie")

    def _installer(reponse: Any) -> None:
        def _retrieve(*_a: Any, **_k: Any) -> Any:
            if isinstance(reponse, Exception):
                raise reponse
            return reponse

        monkeypatch.setattr(stripe.Price, "retrieve", staticmethod(_retrieve))

    return _installer


@pytest.mark.django_db
def test_un_tarif_conforme_est_accepte(stripe_repond: Any) -> None:
    """Garde-fou : sans lui, un contrôle qui refuse TOUT passerait pour bon."""
    stripe_repond({"unit_amount": 12900, "recurring": {"interval": "month"}})

    form = FormuleForm(data={**BASE, "reference_paiement": "price_bon"})

    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_un_identifiant_inconnu_de_stripe_est_refuse(stripe_repond: Any) -> None:
    stripe_repond(ValueError("No such price: price_faute_de_frappe"))

    form = FormuleForm(data={**BASE, "reference_paiement": "price_faute_de_frappe"})

    assert not form.is_valid()
    assert "ne reconnaît pas" in str(form.errors["reference_paiement"])


@pytest.mark.django_db
def test_un_tarif_ponctuel_est_refuse(stripe_repond: Any) -> None:
    """Un abonnement sur un tarif ponctuel encaisse une fois, puis plus jamais.

    Rien n'échoue : la première facture passe, et le renouvellement n'existe
    tout simplement pas. Le manque se découvre un mois plus tard.
    """
    stripe_repond({"unit_amount": 12900, "recurring": None})

    form = FormuleForm(data={**BASE, "reference_paiement": "price_ponctuel"})

    assert not form.is_valid()
    assert "PONCTUEL" in str(form.errors["reference_paiement"])


@pytest.mark.django_db
def test_un_montant_qui_ne_correspond_pas_est_refuse(stripe_repond: Any) -> None:
    """LE cas qui justifie ce contrôle : facturer un prix qu'on n'affiche pas."""
    stripe_repond({"unit_amount": 9900, "recurring": {"interval": "month"}})

    form = FormuleForm(data={**BASE, "reference_paiement": "price_mauvais_montant"})

    assert not form.is_valid()
    motif = str(form.errors["reference_paiement"])
    assert "99.00" in motif and "129.00" in motif


@pytest.mark.django_db
def test_une_reference_vide_reste_permise(stripe_repond: Any) -> None:
    """Contre-épreuve : le contrôle ne doit pas rendre la formule insaisissable.

    Une formule se crée avant d'avoir son tarif — c'est même l'ordre normal.
    Refuser le vide obligerait à inventer un identifiant pour enregistrer.
    """
    stripe_repond(ValueError("ne doit jamais etre appele"))

    form = FormuleForm(data={**BASE, "reference_paiement": ""})

    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_sans_cle_stripe_la_saisie_reste_possible(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sur une plateforme sans Stripe configuré, on prépare quand même.

    Bloquer la saisie faute de clé empêcherait de préparer la configuration en
    recette. On laisse passer — le contrôle `evkha.W003` dit déjà que la clé
    manque, et `stripe_api` lève au moment de payer.
    """
    from paiement import stripe_api
    from paiement.stripe_api import PaiementIndisponible

    def _sans_cle() -> str:
        raise PaiementIndisponible("pas de cle")

    monkeypatch.setattr(stripe_api, "cle_secrete", _sans_cle)

    form = FormuleForm(data={**BASE, "reference_paiement": "price_quelconque"})

    assert form.is_valid(), form.errors

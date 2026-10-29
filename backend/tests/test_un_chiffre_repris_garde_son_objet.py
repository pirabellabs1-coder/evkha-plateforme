"""Le chapitre suivant sait ce que chaque chiffre déjà écrit COMPTE.

Cliente, 29/10/2026 : « 10 000 porteurs de projet » devenus « 10 000
entreprises créées ». Sur `99a142b0`, « 40 % des TPE-PME » écrit dans seize
chapitres, devenu « 40 % des TPE » au chapitre 22. Le contrôle du document
livré (`objet_des_chiffres`) le constate après coup ; ce registre le prévient :
chaque chapitre reçoit les couples valeur–objet déjà écrits par les précédents.

Rejoués sur le code d'avant (règle 6) : `chiffres_deja_ecrits` n'existait pas,
et la consigne du chapitre ne portait aucun objet — seulement des valeurs.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from django.test import override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres.configuration import type_document
from generation.chapitres.runner import construire_prompt_chapitre
from generation.memoire.services import memoire_du_job
from generation.models import GenerationJob
from generation.services import bootstrap_generation_job
from generation.socle import etablir_socle, socle_verrouille
from generation.verification.lecture import DocumentLu
from generation.verification.objet_des_chiffres import chiffres_deja_ecrits
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StubClaudeClient
from orders.models import Order

EM = DeliverableType.MARKET_STUDY
VARIABLES = {
    "SECTEUR": "conseil en intelligence artificielle pour TPE", "PAYS": "France",
    "ZONE": "Hauts-de-France", "PROJET": "consultant IA indépendant",
}
TITRE = "CHIFFRES DÉJÀ ÉCRITS DANS L'ÉTUDE"


def _document(*par_chapitre: tuple[int, str]) -> DocumentLu:
    return DocumentLu(
        chemin=Path("etude.docx"),
        paragraphes=[texte for _, texte in par_chapitre],
        chapitre_du_paragraphe=[numero for numero, _ in par_chapitre],
    )


# ── Le registre ─────────────────────────────────────────────────────────────


def test_chaque_couple_valeur_objet_garde_sa_premiere_forme() -> None:
    ecrits = chiffres_deja_ecrits(_document(
        (1, "40 % des TPE-PME utilisent l'IA (France Num)."),
        (2, "Rappel : 40 % des TPE-PME utilisent l'IA."),
        (2, "On compte 10 000 porteurs de projet."),
        (3, "Soit 40 % des tpe-pme du panel."),
    ))
    assert [(e.forme, e.chapitres) for e in ecrits] == [
        ("40 % des TPE-PME", (1, 2, 3)),
        ("10 000 porteurs", (2,)),
    ]


def test_une_meme_valeur_peut_compter_deux_populations() -> None:
    """« 30 % des femmes » et « 30 % des hommes » : deux statistiques, deux
    lignes — le registre ne choisit pas à la place du rédacteur."""
    ecrits = chiffres_deja_ecrits(_document(
        (1, "30 % des femmes achètent d'occasion."),
        (2, "30 % des hommes aussi."),
    ))
    assert [e.forme for e in ecrits] == ["30 % des femmes", "30 % des hommes"]
    assert {e.valeur for e in ecrits} == {"30 %"}


def test_ce_qui_n_est_pas_un_objet_n_entre_pas_au_registre() -> None:
    """Les mêmes contre-épreuves que le contrôle : il lit avec lui (règle 5)."""
    assert chiffres_deja_ecrits(_document(
        (1, "Le marché pèse 1 000 M€, soit 10 % du marché national."),
        (2, "100 % des documents sont prêts ; loyer de 10 000 FCFA."),
    )) == []


# ── Le bloc que reçoit le chapitre ──────────────────────────────────────────


def _dossier(suffixe: str) -> GenerationJob:
    offre, _ = Offer.objects.get_or_create(
        slug="em-chiffres-ecrits", defaults={"name": "EM", "deliverable_type": EM},
    )
    commande = Order.objects.create(
        systeme_order_id=f"cmd-chiffres-ecrits-{suffixe}",
        customer=Customer.objects.create(email=f"ecrits-{suffixe}@exemple.fr"),
        offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED, normalized_variables=VARIABLES,
    )
    with override_settings(EVKHA_MEMOIRE_ETUDE=True):
        job = bootstrap_generation_job(soumission)
    etablir_socle(job, client=StubClaudeClient(), variables=VARIABLES)
    return job


def _consigne(job: GenerationJob, numero: int) -> str:
    socle = socle_verrouille(job)
    assert socle is not None
    prompt, _ = construire_prompt_chapitre(
        job.chapters.get(chapter_number=numero), socle=socle,
        variables=VARIABLES, document=type_document(EM),
    )
    return prompt.par_chapitre


def _ecrire(job: GenerationJob, numero: int, contenu: str) -> None:
    job.chapters.filter(chapter_number=numero).update(content=contenu)


@pytest.mark.django_db
def test_le_chapitre_suivant_recoit_chaque_chiffre_avec_son_objet() -> None:
    job = _dossier("a")
    _ecrire(job, 1, "Côté TPE, 40 % des TPE-PME utilisent l'IA (France Num, 2026).")
    _ecrire(job, 2, "On compte 10 000 porteurs de projet.\n\n40 % des TPE-PME l'emploient.")

    consigne = _consigne(job, 3)
    assert TITRE in consigne
    assert "« 40 % des TPE-PME » (posé au chapitre 1, déjà repris dans 2 chapitres)" in consigne
    assert "« 10 000 porteurs » (chapitre 2)" in consigne


@pytest.mark.django_db
def test_un_glissement_deja_ecrit_est_montre_au_redacteur() -> None:
    """Le chapitre 22 de `99a142b0` : le 40 % a déjà deux populations. Le
    rédacteur suivant le lit, au lieu de recopier la seconde."""
    job = _dossier("b")
    _ecrire(job, 1, "40 % des TPE-PME utilisent l'IA.")
    _ecrire(job, 2, "Opportunité : 40 % des TPE utilisent l'IA.")

    consigne = _consigne(job, 3)
    assert "même valeur, autre objet : « 40 % des TPE » (chapitre 2)" in consigne


@pytest.mark.django_db
def test_une_ligne_de_tableau_se_lit_cellule_par_cellule() -> None:
    """« | 40 % | des TPE | » : deux cellules, pas une statistique."""
    job = _dossier("c")
    _ecrire(job, 1, "| Indicateur | Valeur |\n|---|---|\n| 40 % | des TPE |\n| 12 000 | clients |")
    assert TITRE not in _consigne(job, 2)


@pytest.mark.django_db
def test_le_registre_lit_la_valeur_que_le_lecteur_lira() -> None:
    """Un repère est remplacé par sa valeur avant lecture : `{{x}} des
    clientes` est, pour le lecteur, « 12,5 % des clientes »."""
    job = _dossier("d")
    memoire = memoire_du_job(job)
    assert memoire is not None
    taux = next(f for f in memoire.faits.values() if f.unite == "%")
    _ecrire(job, 1, f"Soit {{{{{taux.id}}}}} des clientes interrogées.")

    from generation.memoire.reperes import valeur_affichee

    attendu = valeur_affichee(taux).replace(" ", " ")
    assert f"« {attendu} des clientes » (chapitre 1)" in _consigne(job, 2)


@pytest.mark.django_db
def test_rien_a_reprendre_rien_a_dire() -> None:
    """Le premier chapitre, ou des chapitres sans statistique : pas de bloc
    vide qui inviterait à en inventer."""
    job = _dossier("e")
    assert TITRE not in _consigne(job, 1)
    _ecrire(job, 1, "Le marché pèse 1 000 M€ en 2026.")
    assert TITRE not in _consigne(job, 2)


@pytest.mark.django_db
def test_seuls_les_chapitres_precedents_comptent() -> None:
    job = _dossier("f")
    _ecrire(job, 4, "On compte 10 000 porteurs de projet.")
    assert TITRE not in _consigne(job, 3)


@pytest.mark.django_db
def test_une_panne_du_registre_n_arrete_pas_le_chapitre(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Une aide au rédacteur ne bloque jamais une étude : sans le bloc, le
    chapitre s'écrit comme avant."""
    job = _dossier("g")
    _ecrire(job, 1, "40 % des TPE-PME utilisent l'IA.")

    def en_panne(*_args: object) -> str:
        raise ValueError("imprévu")

    monkeypatch.setattr("generation.chapitres.runner._bloc_chiffres_ecrits", en_panne)
    consigne = _consigne(job, 2)
    assert TITRE not in consigne
    assert "CHAPITRE À RÉDIGER : 2" in consigne

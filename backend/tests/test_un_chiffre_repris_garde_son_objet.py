"""Le chapitre suivant sait ce que chaque chiffre déjà écrit COMPTE.

Cliente, 29/10/2026 : « 10 000 porteurs de projet » devenus « 10 000
entreprises créées ». Sur `99a142b0`, « 40 % des TPE-PME » écrit dans seize
chapitres, devenu « 40 % des TPE » au chapitre 22. Le contrôle du document
livré (`objet_des_chiffres`) le constate après coup ; ce registre le prévient :
chaque chapitre reçoit les couples valeur–objet déjà écrits par les autres.

Rejoués sur le code d'avant (règle 6) : la consigne du chapitre ne portait
aucun objet, seulement des valeurs. La relecture du 29/10/2026 a ajouté les
formes entières (« porteurs de projet », pas « porteurs »), la régénération,
l'emphase markdown et l'absence d'exemple étranger au dossier.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.test import override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres.configuration import type_document
from generation.chapitres.runner import construire_prompt_chapitre
from generation.memoire.services import memoire_du_job
from generation.models import ChapterStatus, GenerationJob
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
        ("40 % des TPE-PME utilisent l'IA", (1, 2, 3)),
        ("10 000 porteurs de projet", (2,)),
    ]


@pytest.mark.parametrize(
    ("phrase", "forme"),
    [
        # Relecture du 29/10/2026 : la forme s'arrêtait au premier mot.
        ("On compte 10 000 porteurs de projet accompagnés.",
         "10 000 porteurs de projet accompagnés"),
        ("Ainsi 40 % des TPE et PME utilisent l'IA.", "40 % des TPE et PME utilisent l'IA"),
        ("Soit 40 % des entreprises de moins de 10 salariés, selon l'Insee.",
         "40 % des entreprises de moins de 10 salariés"),
        # La suite est bornée : une forme, pas une phrase.
        ("Enfin 40 % des TPE-PME utilisent l'IA générative au quotidien pour "
         "rédiger leurs devis et leurs relances",
         "40 % des TPE-PME utilisent l'IA générative au quotidien …"),
        # Une conjonction suivie d'un nombre ouvre une autre statistique.
        ("Soit 40 % des TPE-PME et 25 % des ETI.", "40 % des TPE-PME"),
        # La virgule décimale ne coupe pas ; la virgule de phrase coupe.
        ("Soit 30 % des clientes en 2,5 ans, puis davantage.", "30 % des clientes en 2,5 ans"),
    ],
)
def test_la_forme_montree_porte_l_objet_entier(phrase: str, forme: str) -> None:
    ecrit = chiffres_deja_ecrits(_document((1, phrase)))[0]
    assert ecrit.forme == forme


def test_une_meme_valeur_peut_compter_deux_populations() -> None:
    """« 30 % des femmes » et « 30 % des hommes » : deux statistiques, deux
    lignes — le registre ne choisit pas à la place du rédacteur."""
    ecrits = chiffres_deja_ecrits(_document(
        (1, "30 % des femmes achètent d'occasion."),
        (2, "30 % des hommes aussi."),
    ))
    assert [e.forme for e in ecrits] == [
        "30 % des femmes achètent d'occasion", "30 % des hommes aussi",
    ]
    assert {e.valeur for e in ecrits} == {"30 %"}


def test_ce_qui_n_est_pas_un_objet_n_entre_pas_au_registre() -> None:
    """Les mêmes contre-épreuves que le contrôle : il lit avec lui (règle 5)."""
    assert chiffres_deja_ecrits(_document(
        (1, "Le marché pèse 1 000 M€, soit 10 % du marché national."),
        (2, "100 % des documents sont prêts ; loyer de 10 000 FCFA."),
    )) == []


# ── Le bloc que reçoit le chapitre ──────────────────────────────────────────


def _dossier(suffixe: str, variables: dict[str, str] | None = None) -> GenerationJob:
    variables = variables or VARIABLES
    offre, _ = Offer.objects.get_or_create(
        slug="em-chiffres-ecrits", defaults={"name": "EM", "deliverable_type": EM},
    )
    commande = Order.objects.create(
        systeme_order_id=f"cmd-chiffres-ecrits-{suffixe}",
        customer=Customer.objects.create(email=f"ecrits-{suffixe}@exemple.fr"),
        offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED, normalized_variables=variables,
    )
    with override_settings(EVKHA_MEMOIRE_ETUDE=True):
        job = bootstrap_generation_job(soumission)
    etablir_socle(job, client=StubClaudeClient(), variables=variables)
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
    job.chapters.filter(chapter_number=numero).update(
        content=contenu, status=ChapterStatus.DONE,
    )


@pytest.mark.django_db
def test_le_chapitre_suivant_recoit_chaque_chiffre_avec_son_objet() -> None:
    job = _dossier("a")
    _ecrire(job, 1, "Côté TPE, 40 % des TPE-PME utilisent l'IA (France Num, 2026).")
    _ecrire(job, 2, "On compte 10 000 porteurs de projet.\n\n40 % des TPE-PME utilisent l'IA.")

    consigne = _consigne(job, 3)
    assert TITRE in consigne
    assert (
        "« 40 % des TPE-PME utilisent l'IA » (chapitre 1, repris dans 1 autre chapitre)"
        in consigne
    )
    assert "« 10 000 porteurs de projet » (chapitre 2)" in consigne


@pytest.mark.django_db
def test_un_glissement_deja_ecrit_est_montre_au_redacteur() -> None:
    """Le chapitre 22 de `99a142b0` : le 40 % a déjà deux populations, et la
    plus reprise fait référence — pas la première écrite."""
    job = _dossier("b")
    _ecrire(job, 1, "40 % des TPE utilisent l'IA.")
    _ecrire(job, 2, "40 % des TPE-PME utilisent l'IA.")
    _ecrire(job, 3, "Rappel : 40 % des TPE-PME utilisent l'IA.")

    consigne = _consigne(job, 4)
    reference = consigne.index("« 40 % des TPE-PME utilisent l'IA » (chapitre 2")
    glissement = consigne.index("« 40 % des TPE utilisent l'IA » (chapitre 1) — même valeur")
    assert reference < glissement


@pytest.mark.django_db
def test_deux_statistiques_distinctes_ne_recoivent_pas_d_avertissement() -> None:
    """« 20 % des visites » et « 20 % des clients » : deux statistiques
    légitimes (vraies études locales) ; un avertissement répété inviterait le
    modèle à se justifier dans le texte."""
    job = _dossier("c")
    _ecrire(job, 1, "20 % des visites viennent du mobile.")
    _ecrire(job, 2, "20 % des clients reviennent.")

    consigne = _consigne(job, 3)
    assert "« 20 % des clients reviennent » (chapitre 2)" in consigne
    assert "même valeur" not in consigne


@pytest.mark.django_db
def test_une_reecriture_voit_les_chapitres_qui_suivent() -> None:
    """Réécrire le chapitre 2 (relance, `controle_final`) doit montrer ce que
    le chapitre 3 a déjà repris de lui."""
    job = _dossier("d")
    _ecrire(job, 1, "40 % des TPE-PME utilisent l'IA.")
    _ecrire(job, 3, "40 % des TPE-PME utilisent l'IA, rappelons-le.")

    consigne = _consigne(job, 2)
    assert "(chapitre 1, repris dans 1 autre chapitre)" in consigne


@pytest.mark.django_db
def test_un_chapitre_en_cours_n_entre_pas_au_registre() -> None:
    job = _dossier("e")
    job.chapters.filter(chapter_number=4).update(
        content="On compte 10 000 porteurs de projet.", status=ChapterStatus.RUNNING,
    )
    assert TITRE not in _consigne(job, 3)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "ligne",
    [
        "| Indicateur | 40 % des TPE-PME | 2026 |",
        "*40 %* des TPE-PME utilisent l'IA.",
        "**40 %** des TPE-PME utilisent l'IA.",
        "40 % des **TPE-PME** utilisent l'IA.",
    ],
)
def test_une_cellule_et_l_emphase_se_lisent(ligne: str) -> None:
    job = _dossier("f")
    _ecrire(job, 1, ligne)
    # La LIGNE du registre, avec son chapitre : l'ancienne consigne du résumé
    # portait « 40 % des TPE-PME » en dur, et une assertion plus lâche la
    # trouvait là.
    assert re.search(r"- « 40 % des TPE-PME[^»]*» \(chapitre 1\)", _consigne(job, 2))


@pytest.mark.django_db
def test_une_ligne_de_tableau_se_lit_cellule_par_cellule() -> None:
    """« | 40 % | des TPE | » : deux cellules, pas une statistique."""
    job = _dossier("g")
    _ecrire(job, 1, "| Indicateur | Valeur |\n|---|---|\n| 40 % | des TPE |\n| 12 000 | clients |")
    assert TITRE not in _consigne(job, 2)


@pytest.mark.django_db
def test_aucun_exemple_etranger_au_dossier() -> None:
    """Un chiffre montré au modèle est recopié (`rappel_des_reperes`). Une
    étude de joaillerie ne doit lire ni « TPE-PME » ni « porteurs de projet »
    dans sa consigne — ni avec un registre, ni sans."""
    joaillerie = {"SECTEUR": "joaillerie de créateurs", "PAYS": "France",
                  "ZONE": "Paris", "PROJET": "maison d'édition joaillière"}
    job = _dossier("h", joaillerie)
    assert "TPE-PME" not in _consigne(job, 2)

    _ecrire(job, 1, "Soit 35 % des acheteuses de bijoux en ligne.")
    consigne = _consigne(job, 2)
    assert "« 35 % des acheteuses de bijoux en ligne »" in consigne
    assert "TPE" not in consigne
    assert "porteurs de projet" not in consigne


@pytest.mark.django_db
def test_le_registre_lit_la_valeur_que_le_lecteur_lira() -> None:
    """Par précaution : en production, `_appliquer_memoire` a déjà écrit les
    repères en valeurs avant l'enregistrement. Si un `{{x}}` restait, il est
    lu comme le lecteur le lirait."""
    job = _dossier("i")
    memoire = memoire_du_job(job)
    assert memoire is not None
    taux = next(f for f in memoire.faits.values() if f.unite == "%")
    _ecrire(job, 1, f"Soit {{{{{taux.id}}}}} des clientes interrogées.")

    from generation.memoire.reperes import valeur_affichee

    attendu = valeur_affichee(taux).replace(" ", " ")
    assert f"« {attendu} des clientes interrogées » (chapitre 1)" in _consigne(job, 2)


@pytest.mark.django_db
def test_rien_a_reprendre_rien_a_dire() -> None:
    """Le premier chapitre, ou des chapitres sans statistique : pas de bloc
    vide qui inviterait à en inventer."""
    job = _dossier("j")
    assert TITRE not in _consigne(job, 1)
    _ecrire(job, 1, "Le marché pèse 1 000 M€ en 2026.")
    assert TITRE not in _consigne(job, 2)


@pytest.mark.django_db
def test_une_panne_du_registre_n_arrete_pas_le_chapitre(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Une aide au rédacteur ne bloque jamais une étude : sans le bloc, le
    chapitre s'écrit comme avant."""
    job = _dossier("k")
    _ecrire(job, 1, "40 % des TPE-PME utilisent l'IA.")

    def en_panne(*_args: object) -> str:
        raise ValueError("imprévu")

    monkeypatch.setattr("generation.chapitres.runner._bloc_chiffres_ecrits", en_panne)
    consigne = _consigne(job, 2)
    assert TITRE not in consigne
    assert "CHAPITRE À RÉDIGER : 2" in consigne


@pytest.mark.django_db
def test_une_population_elargie_par_et_est_un_glissement() -> None:
    """Contre-relecture du 29/10/2026 : « 40 % des TPE et PME » et « 40 % des
    TPE » partageaient la clé `tpe`, et la forme minoritaire, écrite la
    première, était montrée comme référence avec les quatre chapitres."""
    job = _dossier("l")
    _ecrire(job, 1, "40 % des TPE utilisent l'IA.")
    for numero in (2, 3, 4):
        _ecrire(job, numero, "40 % des TPE et PME utilisent l'IA.")

    consigne = _consigne(job, 5)
    reference = consigne.index("« 40 % des TPE et PME utilisent l'IA » (chapitre 2, repris dans 2")
    glissement = consigne.index("« 40 % des TPE utilisent l'IA » (chapitre 1) — même valeur")
    assert reference < glissement


@pytest.mark.django_db
def test_le_glissement_entre_deux_formes_minoritaires_est_nomme() -> None:
    """Avec `entreprises` en tête, `TPE-PME` et `TPE` ne se comparent pas qu'à
    elle — même règle que le contrôle du document livré."""
    job = _dossier("m")
    _ecrire(job, 1, "40 % des entreprises recrutent.")
    _ecrire(job, 2, "40 % des entreprises investissent.")
    _ecrire(job, 3, "40 % des TPE-PME utilisent l'IA.")
    _ecrire(job, 4, "40 % des TPE utilisent l'IA.")

    consigne = _consigne(job, 5)
    assert (
        "« 40 % des TPE utilisent l'IA » (chapitre 4) — même valeur, population plus "
        "large ou plus étroite que « 40 % des TPE-PME utilisent l'IA »"
    ) in consigne
    # La forme intermédiaire reste listée sans avertissement : elle n'est
    # incluse ni dans `entreprises`, ni l'inverse.
    assert "- « 40 % des TPE-PME utilisent l'IA » (chapitre 3)\n" in consigne


@pytest.mark.django_db
def test_le_bloc_est_borne_et_garde_les_plus_reprises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("generation.chapitres.runner._VALEURS_ECRITES_MAX", 1)
    job = _dossier("n")
    _ecrire(job, 1, "On compte 10 000 porteurs de projet.")
    _ecrire(job, 2, "40 % des TPE-PME utilisent l'IA.")
    _ecrire(job, 3, "Rappel : 40 % des TPE-PME utilisent l'IA.")

    consigne = _consigne(job, 4)
    assert "« 40 % des TPE-PME utilisent l'IA »" in consigne
    assert "porteurs de projet" not in consigne

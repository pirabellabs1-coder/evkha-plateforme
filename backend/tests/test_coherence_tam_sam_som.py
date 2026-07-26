"""Registre TAM / SAM / SOM et controle arithmetique (manuel p. 6).

Le manuel prescrit noir sur blanc, dans le tableau des chiffres-fondations,
une ligne « TAM / SAM / SOM | Annee — hypotheses | Formule et sources |
Ch. 2, 14, 15 ». Le registre ne la portait pas : les trois seuls chiffres que
le manuel nomme explicitement etaient les seuls qui n'etaient pas verrouilles.

Constat du run reel 010e3bf2 (WAOME, juillet 2026), chapitre 2, repris dans le
verdict d'Evangeline (« TAM, SAM et SOM incoherents », « erreurs de calcul
importantes ») :
  - deux valeurs pour le meme SAM regional (240 puis 250 kEUR) ;
  - un SOM annee 1 a 100-120 kEUR contre un SAM de 250 kEUR, soit ~44 % du
    marche accessible capte des la premiere annee, que le texte JUSTIFIE au
    lieu de le recalculer.

Ces tests verrouillent : l'extraction, l'emboitement TAM >= SAM >= SOM, le
plafond de plausibilite, et le blocage au gate de livraison.
"""
from __future__ import annotations

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.coherence import (
    anomalies_tam_sam_som,
    chiffres_fondations_as_table,
    extract_and_lock_chiffres_cles,
    locked_facts_as_context,
)
from generation.models import GenerationJob
from intake.models import IntakeStatus, IntakeSubmission
from orders.models import Order


@pytest.fixture
def em_job() -> GenerationJob:
    offer = Offer.objects.create(
        name="EM test", slug="em-test-tam",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="tam@b.c")
    order = Order.objects.create(systeme_order_id="o-tam", customer=customer, offer=offer)
    IntakeSubmission.objects.create(
        order=order, status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "x", "PAYS": "FR"},
    )
    return GenerationJob.objects.create(
        order=order, deliverable_type=DeliverableType.MARKET_STUDY
    )


@pytest.mark.django_db
def test_tam_sam_som_sont_verrouilles(em_job: GenerationJob) -> None:
    content = (
        "Le TAM atteint 90 millions d'euros. Le SAM ressort a 250 keur "
        "apres application du filtre geographique. Le SOM annee 1 vise "
        "20 keur, soit 8 % du marche accessible."
    )
    extract_and_lock_chiffres_cles(em_job, 2, content)
    facts = locked_facts_as_context(em_job)
    assert "tam = 90 millions" in facts
    assert "sam = 250 keur" in facts
    assert "som = 20 keur" in facts


@pytest.mark.django_db
def test_niveau_discrimine_la_cle(em_job: GenerationJob) -> None:
    # Meme logique que taille_marche_* : le qualificatif de zone present dans
    # la phrase discrimine la cle, sans quoi un TAM national ecraserait un
    # TAM mondial verrouille plus tot.
    extract_and_lock_chiffres_cles(
        em_job, 1, "A l'echelle mondiale, le TAM represente 12 milliards."
    )
    facts = locked_facts_as_context(em_job)
    assert "tam_mondial = 12 milliards" in facts


@pytest.mark.django_db
def test_premiere_mention_gagne_sur_le_sam(em_job: GenerationJob) -> None:
    # Le defaut exact du run 010e3bf2 : deux SAM dans un seul chapitre.
    # 240 vs 250 kEUR = 4 % d'ecart, sous la tolerance de 20 % : la premiere
    # valeur est conservee sans incident, mais UNE SEULE valeur circule.
    extract_and_lock_chiffres_cles(em_job, 2, "Le SAM est de 240 keur.")
    extract_and_lock_chiffres_cles(em_job, 2, "Le SAM retenu est de 250 keur.")
    facts = locked_facts_as_context(em_job)
    assert "sam = 240 keur" in facts
    assert "250 keur" not in facts


@pytest.mark.django_db
def test_som_trop_gros_face_au_sam_est_signale(em_job: GenerationJob) -> None:
    # Le cas WAOME : SOM 110 kEUR / SAM 250 kEUR = 44 %. Arithmetiquement
    # possible, commercialement invraisemblable en annee 1.
    extract_and_lock_chiffres_cles(
        em_job, 2, "Le SAM est de 250 keur. Le SOM annee 1 est de 110 keur."
    )
    anomalies = anomalies_tam_sam_som(em_job)
    assert len(anomalies) == 1
    assert "44%" in anomalies[0]
    assert "recalculer" in anomalies[0]


@pytest.mark.django_db
def test_emboitement_correct_ne_signale_rien(em_job: GenerationJob) -> None:
    # SOM = 1,2 % du SAM : l'ordre de grandeur d'une etude de reference.
    extract_and_lock_chiffres_cles(
        em_job, 2,
        "Le TAM est de 90 millions. Le SAM est de 250 keur. Le SOM annee 1 "
        "est de 3 keur.",
    )
    assert anomalies_tam_sam_som(em_job) == []


@pytest.mark.django_db
def test_sam_superieur_au_tam_est_signale(em_job: GenerationJob) -> None:
    # Erreur de calcul pure : le marche servi ne peut pas depasser le total.
    extract_and_lock_chiffres_cles(
        em_job, 2, "Le TAM est de 200 keur. Le SAM est de 800 keur."
    )
    anomalies = anomalies_tam_sam_som(em_job)
    assert any("superieur au TAM" in a for a in anomalies)


@pytest.mark.django_db
def test_som_superieur_au_sam_est_signale(em_job: GenerationJob) -> None:
    extract_and_lock_chiffres_cles(
        em_job, 2, "Le SAM est de 250 keur. Le SOM est de 400 keur."
    )
    anomalies = anomalies_tam_sam_som(em_job)
    assert any("superieur au SAM" in a for a in anomalies)


@pytest.mark.django_db
def test_unites_differentes_sont_resolues_avant_comparaison(em_job: GenerationJob) -> None:
    # `_numeric_gap` ne compare que des prefixes numeriques : « 3 millions »
    # et « 240 keur » y paraissent distants de 99 % alors que le premier vaut
    # douze fois le second. Le controle arithmetique doit resoudre l'unite.
    extract_and_lock_chiffres_cles(
        em_job, 2, "Le SAM est de 3 millions. Le SOM est de 240 keur."
    )
    anomalies = anomalies_tam_sam_som(em_job)
    # 240 kEUR / 3 MEUR = 8 % : sous le plafond, aucune anomalie.
    assert anomalies == []


@pytest.mark.django_db
def test_anomalie_cree_un_incident_pendant_la_generation(em_job: GenerationJob) -> None:
    # L'anomalie doit etre VISIBLE quand elle nait (dashboard admin), pas
    # seulement decouverte sur le document fini.
    from monitoring.models import OperationalIncident

    extract_and_lock_chiffres_cles(
        em_job, 2, "Le SAM est de 250 keur. Le SOM annee 1 est de 110 keur."
    )
    incidents = OperationalIncident.objects.filter(job=em_job)
    assert incidents.filter(title__startswith="Emboitement TAM/SAM/SOM").exists()


@pytest.mark.django_db
def test_gate_bloque_un_emboitement_faux(em_job: GenerationJob) -> None:
    from generation.gate import _check_arithmetique_marche

    extract_and_lock_chiffres_cles(
        em_job, 2, "Le TAM est de 200 keur. Le SAM est de 800 keur."
    )
    failures = _check_arithmetique_marche(em_job)
    assert failures
    assert all(f.check == "arithmetique_marche" for f in failures)
    # Le detail doit renvoyer au manuel : le relecteur humain doit savoir
    # quelle regle est violee, pas seulement qu'un check a echoue.
    assert "p. 6" in failures[0].detail


@pytest.mark.django_db
def test_table_fondations_rend_les_cinq_colonnes_du_manuel(em_job: GenerationJob) -> None:
    extract_and_lock_chiffres_cles(
        em_job, 2, "Le SAM est de 250 keur. Le SOM annee 1 est de 20 keur."
    )
    table = chiffres_fondations_as_table(em_job)
    entete = (
        "| Information | Valeur retenue | Perimetre / annee / unite "
        "| Source ou methode | Reutilisation |"
    )
    assert entete in table
    # Colonne « Reutilisation » recopiee du manuel p. 6 pour la ligne
    # TAM / SAM / SOM : les chapitres 14 et 15 doivent savoir que le chiffre
    # est deja fixe.
    assert "ch. 2, 14, 15" in table
    # Colonne « Perimetre / annee / unite » : l'unite vient de la valeur, et
    # l'annee manquante est signalee au lieu d'etre inventee.
    assert "keur" in table
    assert "annee a preciser" in table


def test_chapitre_2_est_genere_en_un_seul_appel() -> None:
    """Le chapitre 2 ne doit JAMAIS etre redecoupe en sections.

    Regression run 010e3bf2 : avec `sections=("em.02.a.national",
    "em.02.b.local")`, la section b ne voyait de la section a qu'un resume de
    1200 caracteres (`_SUMMARY_MAX_CHARS`). Elle recalculait donc le marche
    accessible, d'ou deux valeurs de SAM dans un seul chapitre et le verdict
    « TAM, SAM et SOM incoherents ». L'emboitement TAM > SAM > SOM est un
    raisonnement arithmetique continu : il tient dans un appel ou il ne tient
    pas.
    """
    from catalog.models import DeliverableType
    from generation.blueprints import get_blueprint

    bp = get_blueprint(DeliverableType.MARKET_STUDY, 2)
    assert bp is not None
    assert bp.sections == (), (
        "Le chapitre 2 est redecoupe : le calcul TAM/SAM/SOM va se dedoubler."
    )
    # Le volume attendu ne baisse pas avec la fusion : 1100 + 800 mots.
    assert bp.max_words == 1900


def test_prompt_chapitre_2_impose_le_calcul_explicite() -> None:
    # Findrax (etude de reference notee 8/10) ecrit son SOM avec sept variables
    # nommees et la formule posee. Notre chapitre 2 donnait le resultat seul,
    # invérifiable. Le prompt doit exiger le calcul, l'unite commune et le
    # refus de justifier un taux de capture invraisemblable.
    from generation.prompt_library import MARKET_STUDY_PROMPTS

    prompt = MARKET_STUDY_PROMPTS["em.02.marche_national_local"]
    assert "Ecris le calcul, pas seulement le resultat" in prompt
    assert "TAM > SAM > SOM" in prompt
    assert "refais le calcul" in prompt
    # Les chapitres 14 et 15 reutilisent ces valeurs (manuel p. 6) : le
    # redacteur du chapitre 2 doit le savoir.
    assert "chapitres 14" in prompt


def test_aucune_section_orpheline_dans_les_blueprints() -> None:
    # La fusion du chapitre 2 a supprime deux prompts de section. Si un
    # blueprint reference encore une cle inexistante, `prompt_instruction`
    # sert son repli generique : le chapitre se genere quand meme, sans aucune
    # de ses consignes metier. Panne silencieuse, la pire des deux.
    from generation.blueprints import _BLUEPRINTS
    from generation.prompt_library import (
        BUSINESS_PLAN_PROMPTS,
        BUSINESS_STRATEGY_PROMPTS,
        COMPETITOR_STUDY_PROMPTS,
        MARKET_STUDY_PROMPTS,
    )

    connues = (
        MARKET_STUDY_PROMPTS.keys()
        | COMPETITOR_STUDY_PROMPTS.keys()
        | BUSINESS_PLAN_PROMPTS.keys()
        | BUSINESS_STRATEGY_PROMPTS.keys()
    )
    manquantes = [
        section
        for chapitres in _BLUEPRINTS.values()
        for bp in chapitres
        for section in bp.sections
        if section not in connues
    ]
    assert manquantes == [], f"Sections sans prompt : {manquantes}"


def test_fiche_projet_em_nest_pas_sur_haiku() -> None:
    """La fiche projet EM doit tourner sur le modele principal, pas sur Haiku.

    Manuel p. 6 : la fiche projet est « la memoire de l'etude », relue avant
    chaque nouveau bloc, et c'est elle qui fixe les 4 a 5 questions du porteur
    auxquelles l'etude repond. Une lecture faible du questionnaire a cet
    endroit se propage aux 21 chapitres suivants — Findrax adapte ses titres de
    chapitre au questionnaire, notre run ne le faisait pas.

    `model=None` = herite de EVKHA_CLAUDE_MODEL (claude-sonnet).
    """
    from catalog.models import DeliverableType
    from generation.blueprints import get_blueprint

    bp = get_blueprint(DeliverableType.MARKET_STUDY, 0)
    assert bp is not None
    assert bp.model is None, f"fiche projet EM sur {bp.model}"

"""Phase 17 — Correctifs issus de l'audit independant (juillet 2026).

Chaque test verrouille un defaut trouve par une relecture externe de la
branche `fix/gate-etat-chiffre-client`. Ils sont ecrits pour ECHOUER sur le
code d'avant les correctifs.

Le fil rouge de l'audit, et la regle que ces tests defendent :

    « Un check qui n'a rien a comparer est un ECHEC, jamais un succes »
    — c'est la bonne regle, elle etait deja posee.
    Son symetrique manquait : un check qui compare a une donnee MAL EXTRAITE
    est PIRE qu'un check absent, parce qu'il produit un motif faux et envoie
    corriger un chiffre qui n'etait pas faux. C'est la boucle v3 -> v18.
"""
from __future__ import annotations

import pytest

from catalog.models import DeliverableType, Offer
from core.numbers import MONEY, SPACE_CLASS, amounts_in, parse_number
from customers.models import Customer
from generation.coherence import seed_locked_facts_from_variables
from generation.context import build_context
from generation.gate import run_delivery_gate
from generation.internal_labels import INTERNAL_LABEL_NAMES
from generation.models import ChapterStatus, GenerationJob, JobStatus
from generation.rendering import strip_internal_label_tokens
from generation.services import bootstrap_generation_job
from intake.financials import extract_financials_from_text
from intake.models import IntakeStatus, IntakeSubmission
from orders.models import Order

# Le format le plus naturel pour ecrire un previsionnel : une ligne par annee.
BRIEF_EN_PUCES = """Previsionnel SYNAPSES :
- Investissement total : 1 250 000 €
- Emprunt bancaire : 920 000 €
- CA previsionnel An1 : 250 272 €
- CA previsionnel An2 : 296 000 €
- CA previsionnel An3 : 318 400 €
- Resultat net An1 : 44 245 €
"""


def _submission(variables: dict[str, object], ref: str) -> IntakeSubmission:
    offer = Offer.objects.create(
        name="BP", slug=f"bp-{ref}", deliverable_type=DeliverableType.BUSINESS_PLAN
    )
    customer = Customer.objects.create(email=f"{ref}@example.com")
    order = Order.objects.create(systeme_order_id=ref, customer=customer, offer=offer)
    return IntakeSubmission.objects.create(
        order=order, status=IntakeStatus.NORMALIZED, normalized_variables=variables
    )


def _job(submission: IntakeSubmission, content_by_number: dict[int, str]) -> GenerationJob:
    job = bootstrap_generation_job(submission)
    seed_locked_facts_from_variables(job, submission.normalized_variables)
    for chapter in job.chapters.all():
        chapter.content = content_by_number.get(
            chapter.chapter_number, "Analyse chiffree et argumentee du projet."
        )
        chapter.status = ChapterStatus.DONE
        chapter.save(update_fields=["content", "status"])
    job.status = JobStatus.DONE
    job.save(update_fields=["status"])
    return job


# ── F1 : le gate bloquait des documents fideles, avec un motif mensonger ─────


def test_f1_brief_en_puces_capture_toute_la_trajectoire() -> None:
    """AVANT : `_SEGMENT_END` bornait au \\n -> seule l'An1 etait capturee."""
    found = extract_financials_from_text(BRIEF_EN_PUCES)

    assert found["CA_PREVISIONNEL"] == "250 272 € / 296 000 € / 318 400 €"
    assert found["INVESTISSEMENT_TOTAL"] == "1 250 000 €"
    # Le libelle voisin ne doit pas avoir vole les montants du CA.
    assert found["RESULTAT_NET_PREVISIONNEL"] == "44 245 €"


def test_f1_trajectoire_sur_une_seule_ligne_toujours_capturee() -> None:
    """Contre-epreuve : le format mono-ligne ne doit pas regresser."""
    texte = "CA previsionnel : 250 272 € en An1, 296 000 € en An2, 318 400 € en An3."

    found = extract_financials_from_text(texte)

    assert found["CA_PREVISIONNEL"] == "250 272 € / 296 000 € / 318 400 €"


@pytest.mark.django_db
def test_f1_bp_a_previsionnel_en_puces_n_est_plus_bloque_a_tort() -> None:
    """Le coeur de F1, via le vrai gate : document juste, brief juste."""
    variables: dict[str, object] = {
        "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
        "PROJET": BRIEF_EN_PUCES,
    }
    from intake.financials import enrich_variables_from_free_text

    enrich_variables_from_free_text(variables)
    submission = _submission(variables, "f1_puces")
    job = _job(
        submission,
        {
            3: "Le chiffre d'affaires d'annee 2 atteint 296 000 €.",
            15: "Le chiffre d'affaires d'annee 3 atteint 318 400 €.",
        },
    )

    report = run_delivery_gate(job)

    assert not [f for f in report.failures if f.check == "coherence_chiffree"], (
        "Le gate accuse un chiffre pourtant conforme au brief : "
        f"{[f.detail for f in report.failures]}"
    )


@pytest.mark.django_db
def test_f1_trajectoire_a_valeur_unique_n_accuse_pas() -> None:
    """Le brief ne donne que l'An1 : le gate ne peut pas juger l'An2.

    Exiger l'egalite stricte revient a declarer fautif un CA An2 legitime.
    Ne pas savoir juger n'autorise pas a accuser.
    """
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 €",  # An1 seulement
            "RESULTAT_NET_PREVISIONNEL": "44 245 €",
        },
        "f1_unique",
    )
    job = _job(submission, {15: "Le CA d'annee 2 atteint 296 000 €."})

    report = run_delivery_gate(job)

    assert not [f for f in report.failures if f.check == "coherence_chiffree"]


@pytest.mark.django_db
def test_f1_scalaire_reste_en_tolerance_zero() -> None:
    """Contre-epreuve : l'assouplissement ne concerne QUE les trajectoires.

    Un emprunt n'a qu'une valeur possible : 300 000 € au lieu de 920 000 €
    reste bloquant.
    """
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "EMPRUNT": "920 000 €",
            "CA_PREVISIONNEL": "250 272 € / 296 000 €",
            "RESULTAT_NET_PREVISIONNEL": "44 245 €",
        },
        "f1_scalaire",
    )
    job = _job(submission, {14: "Le plan repose sur un emprunt de 300 000 €."})

    report = run_delivery_gate(job)

    assert any(f.check == "coherence_chiffree" for f in report.failures)


# ── F2 : le label CHIFFRES_A_CITER rouvrait le defaut de fuite ───────────────


def test_f2_chiffres_a_citer_est_connu_de_la_source_unique() -> None:
    """Le label injecte par la Brique 1 doit etre couvert par les defenses."""
    assert "CHIFFRES_A_CITER" in INTERNAL_LABEL_NAMES


def test_f2_le_nettoyeur_neutralise_chiffres_a_citer() -> None:
    """AVANT : le label traversait le nettoyeur intact et partait au client."""
    fuite = "Le montant retenu figure dans CHIFFRES_A_CITER pour ce dossier."

    assert "CHIFFRES_A_CITER" not in strip_internal_label_tokens(fuite)


@pytest.mark.django_db
def test_f2_le_gate_bloque_la_fuite_de_chiffres_a_citer() -> None:
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 € / 296 000 €",
            "RESULTAT_NET_PREVISIONNEL": "44 245 €",
        },
        "f2_fuite",
    )
    job = _job(
        submission,
        {15: "Le resultat net est conforme aux CHIFFRES_A_CITER du dossier."},
    )

    report = run_delivery_gate(job)

    assert any(f.check == "contamination" for f in report.failures)


@pytest.mark.django_db
def test_f2_tout_label_du_contexte_est_couvert_par_les_defenses() -> None:
    """Test STRUCTUREL : c'est lui qui rend le prochain oubli impossible.

    Il ne verifie pas un label en particulier, mais que TOUT intitule
    MAJUSCULES_AVEC_UNDERSCORES reellement injecte dans le contexte du modele
    est connu de la source unique. Ajouter un bloc au contexte sans le
    declarer fera echouer ce test.
    """
    import re

    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES", "INVESTISSEMENT_TOTAL": "1 250 000 €",
        },
        "f2_struct",
    )
    job = bootstrap_generation_job(submission)
    seed_locked_facts_from_variables(job, submission.normalized_variables)
    chapter = job.chapters.first()
    assert chapter is not None

    contexte = build_context(chapter)

    # Le motif suit la convention posee par `internal_labels.py` : un intitule
    # de pipeline s'ecrit en MAJUSCULES_AVEC_UNDERSCORES. L'underscore est donc
    # exige — sinon on ramasse la prose du prompt (« REGLE : », « ROLE: »), qui
    # n'a rien d'un label interne.
    #
    # Le libelle peut etre suivi d'un ':' OU d'une parenthese explicative :
    #   VARIABLES_PROJET: {...}
    #   DONNEES_CLIENT (brief client, intangibles) :
    #   CHIFFRES_A_CITER (Brique 1 — substitution automatique) :
    # La premiere version de ce test exigeait un ':' colle : elle ne detectait
    # NI DONNEES_CLIENT NI CHIFFRES_A_CITER — le label meme pour lequel il avait
    # ete ecrit. Il passait a vide. Un test vert qui ne teste rien, exactement le
    # defaut qu'il pretendait interdire ; d'ou l'assertion de garde ci-dessous.
    labels = set(
        re.findall(r"^([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)\s*(?:\(|:)", contexte, re.MULTILINE)
    )
    assert "CHIFFRES_A_CITER" in labels, (
        "Le test ne voit plus le bloc de la Brique 1 : son motif de detection "
        "est desynchronise du format reel de context.py, et il repasserait a vide."
    )
    non_couverts = labels - set(INTERNAL_LABEL_NAMES)

    assert not non_couverts, (
        f"Labels injectes dans le contexte mais absents de la source unique "
        f"`internal_labels.py` : {sorted(non_couverts)}. Ils fuiteront chez le "
        f"client sans etre ni nettoyes ni detectes."
    )


# ── F3 : l'extraction inventait des valeurs, contre sa propre regle ──────────


def test_f3_un_investissement_publicitaire_n_est_pas_l_investissement_total() -> None:
    """AVANT : 5 000 € atterrissait dans INVESTISSEMENT_TOTAL.

    Consequence : le check 0 du gate etait satisfait par une valeur fausse.
    C'est le seul defaut du lot qui recreait une FAUSSE SECURITE — pire que
    le trou d'origine, parce qu'invisible.
    """
    texte = "Nous prevoyons un investissement publicitaire de 5 000 € par mois."

    assert "INVESTISSEMENT_TOTAL" not in extract_financials_from_text(texte)


def test_f3_un_libelle_explicite_reste_extrait() -> None:
    """Contre-epreuve : le durcissement ne casse pas le cas nominal."""
    for texte in (
        "Investissement total de 1 250 000 €.",
        "Le montant de l'investissement est de 1 250 000 €.",
        "Budget total du projet : 1 250 000 €.",
    ):
        found = extract_financials_from_text(texte)
        assert found["INVESTISSEMENT_TOTAL"] == "1 250 000 €", texte


def test_f3_investissement_nu_n_est_jamais_devine() -> None:
    """« investissement » seul est ambigu : enveloppe projet ? budget pub ?

    On n'extrait pas. Le check 0 du gate bloque alors et un humain saisit la
    valeur. Un blocage honnete vaut mieux qu'une reference inventee, qui
    satisferait le check 0 avec une valeur fausse — la fausse securite est le
    seul defaut PIRE que le trou d'origine.
    """
    for texte in (
        "Nous prevoyons un investissement de 5 000 € par mois en publicite.",
        "Un investissement de 5 000 € en publicite est prevu.",
        "Investissement de 1 250 000 €.",  # meme le cas plausible : on ne devine pas
    ):
        assert "INVESTISSEMENT_TOTAL" not in extract_financials_from_text(texte), texte


def test_f3_un_libelle_ambigu_ne_tranche_pas_par_l_ordre_du_texte() -> None:
    """Deux emprunts differents -> aucune extraction, pas « le premier gagne »."""
    texte = "Un emprunt de 300 000 € pour le local, puis un emprunt de 920 000 €."

    assert "EMPRUNT" not in extract_financials_from_text(texte)


def test_f3_recherche_et_developpement_reste_une_seule_verticale() -> None:
    """AVANT : deux verticales fantomes `recherche` / `developpement`.

    Une donnee client fausse injectee dans DONNEES_CLIENT est exactement ce
    que tout le dispositif cherche a empecher.
    """
    found = extract_financials_from_text(
        "Verticales : recherche et developpement, coworking."
    )

    assert found["VERTICALES"] == "recherche et developpement / coworking"


@pytest.mark.django_db
def test_f3_verticale_avec_et_reste_trouvable_dans_la_prose() -> None:
    """Contre-epreuve : ne pas decouper ne doit pas creer de faux positif.

    Le redacteur peut traiter « recherche » et « developpement » separement.
    """
    submission = _submission(
        {
            "SECTEUR": "tech", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 € / 296 000 €",
            "RESULTAT_NET_PREVISIONNEL": "44 245 €",
            "VERTICALES": "recherche et developpement",
        },
        "f3_vert",
    )
    job = _job(
        submission,
        {2: "L'effort de recherche structure l'offre ; le developpement suit."},
    )

    report = run_delivery_gate(job)

    assert not [f for f in report.failures if f.check == "verticales"]


# ── R1 : l'espace fine insecable de Word desarmait tout le check chiffre ────

NNBSP = " "  # U+202F : separateur de milliers insere par Word/Excel en francais


def test_r1_toutes_les_espaces_de_milliers_sont_lues() -> None:
    """`financials` acceptait U+202F, `gate` la rejetait : desaccord silencieux."""
    for space in (" ", " ", " "):
        assert parse_number(f"1{space}250{space}000") == 1_250_000, repr(space)


def test_r1_meme_lecture_des_deux_cotes() -> None:
    """La regle de fond : extraction et gate lisent avec la MEME fonction."""
    brief = f"Investissement total : 1{NNBSP}250{NNBSP}000 €."
    extrait = extract_financials_from_text(brief)["INVESTISSEMENT_TOTAL"]

    # Ce que l'extraction produit doit etre lisible par le gate, sans exception.
    assert amounts_in(extrait) == [1_250_000.0]


@pytest.mark.django_db
def test_r1_brief_colle_depuis_word_ne_desarme_plus_le_gate() -> None:
    """AVANT : passed=True, AUCUNE anomalie, sur l'emprunt divise par 3.

    Le nombre etait capture puis jete par float(), `expected` devenait vide,
    et `if not expected: continue` sautait le check EN SILENCE. Le defaut
    SYNAPSES exact, revenu par une autre porte.
    """
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": f"1{NNBSP}250{NNBSP}000 €",
            "EMPRUNT": f"920{NNBSP}000 €",
            "CA_PREVISIONNEL": f"250{NNBSP}272 € / 296{NNBSP}000 €",
            "RESULTAT_NET_PREVISIONNEL": f"44{NNBSP}245 €",
        },
        "r1_word",
    )
    job = _job(submission, {14: "Le plan repose sur un emprunt de 300 000 €."})

    report = run_delivery_gate(job)

    assert report.passed is False
    assert any(f.check == "coherence_chiffree" for f in report.failures)


# ── R2 : unites abregees — meme montant, blocage, motif mensonger ────────────


@pytest.mark.django_db
def test_r2_unite_abregee_n_est_plus_un_faux_positif() -> None:
    """Brief « 1,25 M€ », document « 1 250 000 € » : c'est le MEME montant."""
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1,25 M€",
            "CA_PREVISIONNEL": "250 272 € / 296 000 €",
            "RESULTAT_NET_PREVISIONNEL": "44 245 €",
        },
        "r2_unite",
    )
    job = _job(submission, {5: "L'investissement total de 1 250 000 € finance le projet."})

    report = run_delivery_gate(job)

    assert not [f for f in report.failures if f.check == "coherence_chiffree"], (
        f"Faux positif sur unite abregee : {[f.detail for f in report.failures]}"
    )


@pytest.mark.django_db
def test_r2_unite_abregee_reellement_divergente_bloque_toujours() -> None:
    """Contre-epreuve : normaliser ne doit pas aveugler le gate."""
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1,25 M€",
            "CA_PREVISIONNEL": "250 272 € / 296 000 €",
            "RESULTAT_NET_PREVISIONNEL": "44 245 €",
        },
        "r2_diverge",
    )
    job = _job(submission, {5: "L'investissement total de 3 000 000 € finance le projet."})

    report = run_delivery_gate(job)

    assert any(f.check == "coherence_chiffree" for f in report.failures)


# ── R3 : zone franc — garantie affichee, jamais assuree ─────────────────────


@pytest.mark.django_db
def test_r3_dossier_en_fcfa_est_reellement_verifie() -> None:
    """L'extraction acceptait FCFA/XOF, aucun motif du gate ne les lisait.

    Une douzaine de pays de la table des devises sont en zone franc : pour eux,
    l'etat chiffre etait verrouille puis jamais compare.
    """
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "Cote d'Ivoire", "ZONE": "Abidjan",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "820 000 000 FCFA",
            "CA_PREVISIONNEL": "164 000 000 FCFA / 194 000 000 FCFA",
            "RESULTAT_NET_PREVISIONNEL": "29 000 000 FCFA",
        },
        "r3_fcfa",
    )
    job = _job(
        submission,
        {5: "L'investissement total de 500 000 000 FCFA structure le projet."},
    )

    report = run_delivery_gate(job)

    assert any(f.check == "coherence_chiffree" for f in report.failures)


# ── R4 : « occupation » nu capturait n'importe quel pourcentage ──────────────


def test_r4_occupation_des_sols_n_est_pas_le_taux_d_occupation() -> None:
    """Le prefixe « taux d' » etait optionnel : tout « occupation ... % » passait."""
    texte = "L'occupation des sols est limitee a 60 % de la parcelle."

    assert "TAUX_OCCUPATION" not in extract_financials_from_text(texte)


def test_r4_le_vrai_taux_d_occupation_reste_extrait() -> None:
    """Contre-epreuve."""
    texte = "Le taux d'occupation passe de 55 % en An1 a 85 % en An5."

    assert extract_financials_from_text(texte)["TAUX_OCCUPATION"] == "55 % / 85 %"


# ── R14 : une verticale est traitee, pas recopiee mot pour mot ──────────────
#
# Faux positif constate sur le PREMIER vrai dossier genere : le gate a bloque
# le BP SYNAPSES en declarant « domiciliation d'entreprises » absente, alors
# que le document traite le sujet 48 fois — sous le nom « domiciliation
# commerciale », « domiciliation a 30 euros », « la domiciliation ». Exiger le
# libelle litteral du brief, c'est accuser un livrable correct.


@pytest.mark.django_db
def test_r14_verticale_nommee_autrement_est_reconnue() -> None:
    """Le client ecrit le libelle du brief, le redacteur ecrit du francais."""
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Beziers",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 € / 273 024 €",
            "VERTICALES": "domiciliation d'entreprises, hebergement de serveurs",
        },
        "r14_nomme",
    )
    job = _job(
        submission,
        {
            2: "La domiciliation commerciale est facturee 30 € par mois aux "
               "entreprises clientes.",
            3: "L'hebergement de serveurs mutualise complete l'offre.",
        },
    )

    report = run_delivery_gate(job)

    assert not [f for f in report.failures if f.check == "verticales"], (
        f"Le gate accuse une verticale pourtant traitee : "
        f"{[f.detail for f in report.failures]}"
    )


@pytest.mark.django_db
def test_r14_verticale_reellement_effacee_reste_bloquee() -> None:
    """Contre-epreuve : assouplir ne doit pas rendre le check inutile.

    C'est LE defaut SYNAPSES d'origine : trois verticales purement effacees au
    profit d'un coworking generique.
    """
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Beziers",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 € / 273 024 €",
            "VERTICALES": "coworking, hebergement de serveurs",
        },
        "r14_efface",
    )
    job = _job(
        submission,
        {2: "L'offre se concentre exclusivement sur le coworking et les bureaux."},
    )

    report = run_delivery_gate(job)

    assert any(f.check == "verticales" for f in report.failures)


# ── R13 : defauts trouves sur le VRAI brief SYNAPSES ────────────────────────
#
# Premiere confrontation du code a un brief reel, ecrit par la cliente. Il a
# casse l'extraction sur des formulations qu'aucun de mes tests n'imaginait.
# Ces deux cas ne sont pas hypothetiques : ils sont copies du brief.


def test_r13_besoin_total_est_un_investissement() -> None:
    """Le brief ecrit « Besoin total : 1 250 000 € HT », pas « investissement ».

    Le montant etait sous les yeux du gate, qui reclamait pourtant la donnee
    comme absente et bloquait le dossier.
    """
    texte = (
        "Besoin total : 1 250 000 € HT (terrain 70 000 € + construction "
        "~1 090 000 € + tresorerie de depart 90 000 €)."
    )

    assert extract_financials_from_text(texte)["INVESTISSEMENT_TOTAL"] == "1 250 000 €"


def test_r13_le_ca_theorique_ne_pollue_pas_la_trajectoire() -> None:
    """Le brief pose un « CA theorique a 100 % d'occupation » a cote du reel.

    Il etait avale comme premiere valeur : toutes les annees se decalaient
    (An1 devenait 455 040 au lieu de 250 272), et le gate accusait ensuite des
    chiffres justes en citant une reference fausse.
    """
    texte = (
        "CA theorique a 100 % d'occupation : 455 040 €/an.\n"
        "Chiffre d'affaires 250 272 € 273 024 € 295 776 € 341 280 € 386 784 €"
    )

    ca = extract_financials_from_text(texte)["CA_PREVISIONNEL"]

    assert "455 040" not in ca
    assert ca.startswith("250 272 €")


# ── R12 : l'annee est le discriminant ───────────────────────────────────────
#
# Defaut n°3 de la cliente : « Le resume executif dit resultat net An1 =
# 44 245 €. Le chapitre 15 dit resultat net An1 = 21 874 €. » MEME ANNEE, deux
# valeurs. Sauter toute trajectoire a valeur unique (correctif F1) evitait
# d'accuser a tort un CA An2 legitime, mais rouvrait CE defaut-la.


@pytest.mark.django_db
def test_r12_meme_annee_valeur_differente_est_bloquee() -> None:
    """Le defaut n°3, exactement : An1 = 44 245 € au brief, 21 874 € au doc."""
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 €",
            "RESULTAT_NET_PREVISIONNEL": "44 245 €",
        },
        "r12_meme_annee",
    )
    job = _job(submission, {15: "Le resultat net d'annee 1 atteint 21 874 €."})

    report = run_delivery_gate(job)

    assert any(f.check == "coherence_chiffree" for f in report.failures)


@pytest.mark.django_db
def test_r12_annee_hors_previsionnel_n_accuse_pas() -> None:
    """Le brief s'arrete a An2 ; le document parle d'An5 : non jugeable.

    Ne pas savoir juger n'autorise pas a accuser.
    """
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 € / 296 000 €",
        },
        "r12_hors",
    )
    job = _job(submission, {15: "Le CA d'annee 5 atteint 480 000 €."})

    report = run_delivery_gate(job)

    assert not [f for f in report.failures if f.check == "coherence_chiffree"]


@pytest.mark.django_db
def test_r12_bonne_annee_bonne_valeur_ne_bloque_pas() -> None:
    """Contre-epreuve : chaque annee comparee a SA valeur."""
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 € / 296 000 € / 318 400 €",
        },
        "r12_ok",
    )
    job = _job(
        submission,
        {
            3: "Le CA d'annee 1 atteint 250 272 €.",
            15: "Le CA d'annee 3 atteint 318 400 €.",
        },
    )

    report = run_delivery_gate(job)

    assert not [f for f in report.failures if f.check == "coherence_chiffree"]


@pytest.mark.django_db
def test_r12_ca_an2_legitime_n_est_pas_accuse() -> None:
    """Contre-epreuve F1 : le brief ne donne que l'An1, le doc parle de l'An2."""
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 €",  # An1 seulement
        },
        "r12_an2",
    )
    job = _job(submission, {15: "Le CA d'annee 2 atteint 296 000 €."})

    report = run_delivery_gate(job)

    assert not [f for f in report.failures if f.check == "coherence_chiffree"]


# ── R11 : on n'exige que les ENTREES, jamais les SORTIES ────────────────────
#
# Precision de la cliente (juillet 2026) : deux cas d'usage reels pour un BP.
#   1. elle construit le previsionnel (Excel) et en resume les chiffres dans le
#      brief -> le resultat net est une DONNEE ;
#   2. le porteur commande un BP SANS previsionnel et donne des estimations via
#      Tally -> le resultat net est ce que le BP doit CALCULER.
# Exiger le resultat net bloquait le cas 2 : on reclamait au client la reponse
# qu'il vient acheter.


@pytest.mark.django_db
def test_r11_bp_sans_resultat_net_fourni_est_livrable() -> None:
    """Cas 2 : le porteur donne ses estimations, le BP calcule le reste."""
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 € / 296 000 €",
            # Pas de RESULTAT_NET : c'est une sortie du business plan.
        },
        "r11_sortie",
    )
    job = _job(submission, {})

    report = run_delivery_gate(job)

    assert not [f for f in report.failures if f.check == "etat_chiffre_client"], (
        f"On reclame au client la reponse qu'il achete : "
        f"{[f.detail for f in report.failures]}"
    )


@pytest.mark.django_db
def test_r11_les_entrees_restent_exigees() -> None:
    """Contre-epreuve : sans investissement ni CA, le BP reste bloque.

    Ce que le business plan ne peut pas deviner sans le client : combien il
    investit et quel chiffre d'affaires il vise.
    """
    submission = _submission(
        {"SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy", "PROJET": "SYNAPSES"},
        "r11_entrees",
    )
    job = _job(submission, {})

    report = run_delivery_gate(job)

    assert any(f.check == "etat_chiffre_client" for f in report.failures)


@pytest.mark.django_db
def test_r11_un_resultat_net_fourni_reste_verifie() -> None:
    """Cas 1 : quand la cliente donne le resultat net, tolerance zero dessus."""
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 € / 296 000 €",
            "RESULTAT_NET_PREVISIONNEL": "44 245 €",
        },
        "r11_verifie",
    )
    job = _job(submission, {15: "Le resultat net d'annee 1 atteint 21 874 €."})

    report = run_delivery_gate(job)

    assert any(f.check == "coherence_chiffree" for f in report.failures)


# ── R10 : le trou d'entree n'etait ferme QUE pour le business plan ──────────
#
# Le previsionnel ignore et les trois verticales effacees decrits par la
# cliente portaient sur la STRATEGIE SYNAPSES, pas sur le BP. Or seul le BP
# exigeait un etat chiffre : pour une strategie, extraction ratee -> zero fait
# -> tous les checks se sautaient en silence.


def _job_typed(
    deliverable: str, variables: dict[str, object], ref: str, contents: dict[int, str]
) -> GenerationJob:
    offer = Offer.objects.create(name=ref, slug=f"o-{ref}", deliverable_type=deliverable)
    customer = Customer.objects.create(email=f"{ref}@example.com")
    order = Order.objects.create(systeme_order_id=ref, customer=customer, offer=offer)
    submission = IntakeSubmission.objects.create(
        order=order, status=IntakeStatus.NORMALIZED, normalized_variables=variables
    )
    return _job(submission, contents)


@pytest.mark.django_db
def test_r10_strategie_dont_le_previsionnel_n_a_pas_ete_lu_est_bloquee() -> None:
    """Le cas SYNAPSES exact, sur le type de livrable ou il s'est produit.

    Le brief ecrit « Investissement total 2026 : 1 250 000 € » — le millesime
    colle au libelle fait echouer l'extraction. AVANT : aucun fait verrouille,
    aucun check actif, le document partait avec des chiffres inventes.
    """
    job = _job_typed(
        DeliverableType.BUSINESS_STRATEGY,
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": (
                "Tiers-lieu SYNAPSES. Investissement total 2026 : 1 250 000 €. "
                "Emprunt bancaire 2026 : 920 000 €."
            ),
        },
        "r10_strat",
        {},
    )

    report = run_delivery_gate(job)

    assert report.passed is False
    assert any(f.check == "brief_non_lu" for f in report.failures)


@pytest.mark.django_db
def test_r10_verticales_non_lues_sont_bloquees_sur_tout_type() -> None:
    """« trois verticales du brief ont ete purement effacees a la generation »."""
    job = _job_typed(
        DeliverableType.BUSINESS_STRATEGY,
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            # « Verticales » annonce, mais sans le « : » attendu -> non extrait.
            "PROJET": "Les verticales retenues sont le coworking et le self-storage",
        },
        "r10_vert",
        {},
    )

    report = run_delivery_gate(job)

    assert any(
        f.check == "brief_non_lu" and "verticale" in f.detail.lower()
        for f in report.failures
    )


@pytest.mark.django_db
def test_r10_brief_correctement_lu_ne_bloque_pas() -> None:
    """Contre-epreuve : quand l'extraction fait son travail, aucun blocage."""
    variables: dict[str, object] = {
        "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
        "PROJET": (
            "Tiers-lieu SYNAPSES. Investissement total : 1 250 000 €. "
            "Emprunt bancaire : 920 000 €. "
            "Verticales : coworking, self-storage."
        ),
    }
    from intake.financials import enrich_variables_from_free_text

    enrich_variables_from_free_text(variables)
    job = _job_typed(
        DeliverableType.BUSINESS_STRATEGY,
        variables,
        "r10_ok",
        {1: "L'offre couvre le coworking et le self-storage sur la zone."},
    )

    report = run_delivery_gate(job)

    assert not [f for f in report.failures if f.check == "brief_non_lu"], (
        f"Blocage a tort : {[f.detail for f in report.failures]}"
    )


@pytest.mark.django_db
def test_r10_etude_de_marche_sans_previsionnel_reste_livrable() -> None:
    """Contre-epreuve : ne pas exiger un previsionnel de qui n'en a pas.

    Une etude de marche n'a legitimement aucun chiffre client : la regle
    « ecrit mais non lu » ne doit rien declencher.
    """
    job = _job_typed(
        DeliverableType.MARKET_STUDY,
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "Etude du marche du coworking sur le bassin annecien.",
        },
        "r10_em",
        {},
    )

    report = run_delivery_gate(job)

    assert not [f for f in report.failures if f.check == "brief_non_lu"]


@pytest.mark.django_db
def test_r10_un_prix_concurrent_n_est_pas_un_previsionnel() -> None:
    """Contre-epreuve : un montant sans libelle de previsionnel ne bloque pas.

    Sinon toute mention de prix dans un brief bloquerait le dossier.
    """
    job = _job_typed(
        DeliverableType.MARKET_STUDY,
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "Le concurrent principal facture 350 € par poste et par mois.",
        },
        "r10_prix",
        {},
    )

    report = run_delivery_gate(job)

    assert not [f for f in report.failures if f.check == "brief_non_lu"]


# ── R5 : liste fermee d'espaces -> valeurs bidon et blocage absurde ─────────


def test_r5_toute_espace_horizontale_unicode_est_lue() -> None:
    """La liste fermee de 4 caracteres etait le probleme, pas sa composition.

    U+2009 (espace fine des typographes) la traversait : « 1 250 000 € » etait
    lu [1.0, 250.0, 0.0], et le gate bloquait un document citant EXACTEMENT le
    montant du brief — « document dit 1 250 000, brief dit 1 250 000 € ».
    """
    for space in (" ", " ", " ", " ", " ", "\t"):
        assert amounts_in(f"1{space}250{space}000 €") == [1_250_000.0], repr(space)


def test_r5_un_montant_ne_deborde_pas_sur_la_ligne_suivante() -> None:
    """Contre-epreuve : le saut de ligne reste une frontiere."""
    assert amounts_in("1 250\n000 €") != [1_250_000.0]


# ── R6 : la source unique doit etre reellement unique ───────────────────────


def test_r6_extraction_et_gate_lisent_avec_la_meme_source() -> None:
    """financials gardait ses propres devises, deja divergentes (ni XAF ni CFA).

    Le gate savait lire un montant en XAF, l'extraction non : pour le Cameroun,
    le Gabon, le Tchad ou le Congo, aucun fait client n'etait verrouille.
    """
    from intake import financials

    assert financials._SP is SPACE_CLASS
    assert financials._AMOUNT is MONEY


def test_r6_zone_xaf_est_extraite() -> None:
    """Consequence concrete de la divergence, cote extraction."""
    found = extract_financials_from_text("Investissement total : 820 000 000 XAF.")

    assert found["INVESTISSEMENT_TOTAL"] == "820 000 000 XAF"


# ── R7 : la fourchette n'appartient qu'aux trajectoires ─────────────────────


@pytest.mark.django_db
def test_r7_un_scalaire_multi_valeurs_garde_la_tolerance_zero() -> None:
    """« 1 250 000 € (dont 300 000 € de travaux) » : deux nombres, un scalaire.

    `len(expected) > 1` suffisait a activer la fourchette : le gate acceptait
    alors TOUT investissement entre 300 000 et 1 250 000 € dans le document.
    La tolerance zero s'eteignait en silence.
    """
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 € (dont 300 000 € de travaux)",
            "CA_PREVISIONNEL": "250 272 € / 296 000 €",
            "RESULTAT_NET_PREVISIONNEL": "44 245 €",
        },
        "r7_scalaire",
    )
    job = _job(submission, {5: "L'investissement total de 800 000 € finance le projet."})

    report = run_delivery_gate(job)

    assert any(f.check == "coherence_chiffree" for f in report.failures)


@pytest.mark.django_db
def test_r7_une_trajectoire_garde_sa_fourchette_sans_annee() -> None:
    """Contre-epreuve : une mention SANS annee reste jugee en fourchette.

    C'est le seul cas ou la fourchette a encore un sens : le document parle du
    CA sans dire de quelle annee, une valeur intermediaire est plausible. Des
    que l'annee est nommee, la comparaison redevient exacte (cf. R12).
    """
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 € / 318 400 €",
        },
        "r7_traj",
    )
    job = _job(
        submission,
        {15: "Le chiffre d'affaires progresse pour atteindre 296 000 € a terme."},
    )

    report = run_delivery_gate(job)

    assert not [f for f in report.failures if f.check == "coherence_chiffree"]


# ── R8 : le motif d'echec doit etre trouvable dans le document ──────────────


@pytest.mark.django_db
def test_r8_le_motif_cite_le_texte_reel_et_le_montant_normalise() -> None:
    """AVANT : « document dit '3' » pour un document disant « 3 M€ ».

    Le lecteur cherchait un « 3 » introuvable, et l'ecart reel (3 000 000 vs
    1 250 000) n'apparaissait nulle part.
    """
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1,25 M€",
            "CA_PREVISIONNEL": "250 272 € / 296 000 €",
            "RESULTAT_NET_PREVISIONNEL": "44 245 €",
        },
        "r8_motif",
    )
    job = _job(submission, {5: "L'investissement total de 3 M€ finance le projet."})

    report = run_delivery_gate(job)

    detail = next(f.detail for f in report.failures if f.check == "coherence_chiffree")
    assert "3 M€" in detail  # le texte reel du document
    assert "3,000,000" in detail or "3000000" in detail  # l'ecart rendu lisible


# ── R9 : l'ordre de grandeur ne couvrait qu'un livrable sur quatre ──────────


@pytest.mark.django_db
def test_r9_erreur_unite_detectee_hors_business_plan() -> None:
    """La reference ne venait que de 2 cles exigees du seul BP.

    L'erreur « millions/milliers » est une faute de redaction, pas une
    specificite du business plan.
    """
    offer = Offer.objects.create(
        name="Etude de marche", slug="em-r9",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="r9@example.com")
    order = Order.objects.create(systeme_order_id="r9_em", customer=customer, offer=offer)
    submission = IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "CA_PREVISIONNEL": "250 272 €",
        },
    )
    job = _job(submission, {1: "Le CA du reseau atteint 420 millions d'euros en An7."})

    report = run_delivery_gate(job)

    assert any(f.check == "ordre_de_grandeur" for f in report.failures)


# ── F7 : angle mort du controle d'ordre de grandeur ──────────────────────────


@pytest.mark.django_db
def test_f7_erreur_unite_en_chiffres_pleins_est_detectee() -> None:
    """AVANT : seul « 420 millions » etait vu, pas « 420 000 000 € »."""
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 € / 296 000 €",
            "RESULTAT_NET_PREVISIONNEL": "44 245 €",
        },
        "f7_plein",
    )
    job = _job(submission, {18: "En annee 7, le reseau degage un EBE de 420 000 000 €."})

    report = run_delivery_gate(job)

    assert any(f.check == "ordre_de_grandeur" for f in report.failures)


@pytest.mark.django_db
def test_f7_montant_projet_normal_n_est_pas_bloque() -> None:
    """Contre-epreuve : un CA legitime ne doit pas devenir une erreur d'unite."""
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Annecy",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 € / 296 000 €",
            "RESULTAT_NET_PREVISIONNEL": "44 245 €",
        },
        "f7_normal",
    )
    job = _job(submission, {15: "Le chiffre d'affaires d'annee 2 atteint 296 000 €."})

    report = run_delivery_gate(job)

    assert not [f for f in report.failures if f.check == "ordre_de_grandeur"]


# ── R15 : un BP bancaire contient des SCENARIOS chiffres ────────────────────
#
# Faux positif du 2e vrai dossier : le gate a bloque les annexes sur
# « Une augmentation de l'emprunt de 59 000 € augmente l'annuite de 890 € ».
# 59 000 n'est pas le montant de l'emprunt : c'est de combien il varie. Un
# DELTA n'est pas une valeur. Et le brief SYNAPSES exige explicitement une
# analyse de sensibilite : la tolerance zero les interdisait toutes.


@pytest.mark.django_db
def test_r15_une_variation_n_est_pas_une_valeur() -> None:
    """« augmentation de l'emprunt de 59 000 € » : rien a comparer."""
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Beziers",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 € / 273 024 €",
            "EMPRUNT": "920 000 €",
        },
        "r15_delta",
    )
    job = _job(
        submission,
        {18: "Une augmentation de l'emprunt de 59 000 € augmente l'annuite de "
             "890 € par an, ce qui reduit la couverture de dette de 3,38 a 3,31."},
    )

    report = run_delivery_gate(job)

    assert not [f for f in report.failures if f.check == "coherence_chiffree"], (
        f"Le gate accuse une analyse de sensibilite : "
        f"{[f.detail for f in report.failures]}"
    )


@pytest.mark.django_db
def test_r15_un_scenario_qui_cite_le_brief_est_tolere() -> None:
    """Le document raisonne SUR le chiffre du brief, il ne le remplace pas."""
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Beziers",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 € / 273 024 €",
            "EMPRUNT": "920 000 €",
        },
        "r15_scenario",
    )
    job = _job(
        submission,
        {18: "Scenario degrade : emprunt porte de 920 000 € a 979 000 € "
             "(+6,4 %), soit un emprunt de 979 000 € au total."},
    )

    report = run_delivery_gate(job)

    assert not [f for f in report.failures if f.check == "coherence_chiffree"]


@pytest.mark.django_db
def test_r15_une_hallucination_reste_bloquee() -> None:
    """Contre-epreuve : tolerer les scenarios ne doit pas ouvrir une porte.

    Une hallucination pose son chiffre SEUL, sans jamais citer la vraie
    valeur — c'est ce qui la distingue d'un scenario.
    """
    submission = _submission(
        {
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Beziers",
            "PROJET": "SYNAPSES",
            "INVESTISSEMENT_TOTAL": "1 250 000 €",
            "CA_PREVISIONNEL": "250 272 € / 273 024 €",
            "EMPRUNT": "920 000 €",
        },
        "r15_hallu",
    )
    job = _job(
        submission,
        {14: "Le plan de financement repose sur un emprunt de 300 000 € sur 7 ans."},
    )

    report = run_delivery_gate(job)

    assert any(f.check == "coherence_chiffree" for f in report.failures)

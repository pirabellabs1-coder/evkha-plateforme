"""Phase 45 — Les trois faux positifs releves en generation reelle.

Job 4c573e40 (brief WAOME, 24/07/2026, EM complete en 22 chapitres). Le livrable
etait conforme, mais trois controles ont crie au loup :

1. CHECK 1 et CHECK FINAL rendus « fix » avec la note generique « Le relecteur a
   signale un defaut sans note explicite ». Cause : `_MAX_TOKENS_CHECK = 2000`
   alors qu'un CHECK a 5 questions consomme 1985 tokens de sortie. Le JSON
   arrivait coupe, `_extraire_json` rendait {}, le verdict retombait sur 'fix'
   par defaut -> regeneration de tout le bloc, puis blocage de la livraison.

2. Chapitre 6 signale « tronque » : il se termine par un encadre en italique,
   « ... engageant la structure.* ». Le point est la ; le « * » n'est qu'un
   delimiteur markdown, mais il etait teste comme dernier caractere.

3. Chapitre 16 signale `sentence_cut` : son dernier paragraphe ouvre sur du gras
   (« **Ce que cela signifie pour WAOME Studio.** ... »), l'encadre que le
   manuel prescrit a chaque chapitre. `_last_prose_line` le sautait comme une
   puce et remontait a une cellule de tableau bien plus haut.

Les trois etaient BLOQUANTS pour la livraison : un livrable conforme ne partait
pas. Ces tests figent les chaines exactes de la generation reelle.
"""
from __future__ import annotations

import pytest

from generation.checks_post_rendu import detecter_troncatures, sans_fioritures_finales
from generation.qa import _last_prose_line, detect_violations

# Fins de chapitre reellement produites par le job 4c573e40.
_FIN_CH6 = (
    "> *Aucune information contenue dans ce chapitre ne constitue un avis "
    "juridique, fiscal ou de conformite. Les dispositions reglementaires "
    "evoluent rapidement dans le domaine de l'IA ; une verification aupres "
    "d'un professionnel du droit ou d'un expert-comptable est indispensable "
    "avant toute decision engageant la structure.*"
)
_FIN_CH16 = (
    "| Concurrent | Position |\n"
    "| --- | --- |\n"
    "| PackshotCreator | Aucune specialisation decoration ; coherence "
    "d'enseigne non garantie |\n\n"
    "---\n\n"
    "**Ce que cela signifie pour WAOME Studio.** Le marche n'est pas sature : "
    "il est fragmente entre une offre technique sans accompagnement et un "
    "accompagnement sans maitrise de l'IA sectorielle. La fenetre pour s'y "
    "installer avant concentration des concurrents est identifiee a 2026-2027."
)


# ── 2. Encadre en italique en fin de chapitre ───────────────────────────────


def test_encadre_italique_final_n_est_pas_une_troncature() -> None:
    """« ... la structure.* » : le point est present, le « * » ferme l'italique."""
    troncatures = detecter_troncatures([(6, "Reglementation", _FIN_CH6)])

    assert troncatures == [], f"Faux positif : {[t.fin_capturee for t in troncatures]}"


def test_une_vraie_troncature_reste_detectee() -> None:
    """Le correctif ne doit pas rendre le detecteur aveugle.

    Chaine du bug WAOME v1 nomme par Evangeline (21/07/2026).
    """
    corps = "Le sondage a ete conduit aupres des prospects grandes mar"

    troncatures = detecter_troncatures([(21, "Annexe", corps)])

    assert len(troncatures) == 1


def test_sans_fioritures_ne_mange_pas_la_ponctuation_francaise() -> None:
    """« » et … sont des fins de phrase valides, pas des delimiteurs a retirer."""
    assert sans_fioritures_finales("Il a dit « oui »").endswith("»")
    assert sans_fioritures_finales("La suite plus tard…").endswith("…")
    assert sans_fioritures_finales("Fin du texte.**") == "Fin du texte."


# ── 3. Paragraphe ouvrant sur du gras ───────────────────────────────────────


def test_le_paragraphe_en_gras_est_bien_de_la_prose() -> None:
    """L'encadre « Ce que cela signifie pour X » du manuel n'est pas une puce."""
    ligne = _last_prose_line(_FIN_CH16)

    assert ligne.startswith("**Ce que cela signifie"), (
        f"Derniere phrase mal identifiee : {ligne[:80]!r}"
    )
    assert ligne.endswith("2026-2027.")


def test_chapitre_termine_par_un_encadre_gras_ne_declenche_pas_sentence_cut() -> None:
    corps = _FIN_CH16 + "\n" * 0
    violations = detect_violations(corps * 12, "em.16.offre_demande", 16)

    # Assertion forte plutot que « sentence_cut absent » : ce texte est propre,
    # aucun controle critique ne doit s'y declencher.
    critiques = [v.name for v in violations if v.severity == "critical"]
    assert critiques == [], f"Faux positifs sur un chapitre conforme : {critiques}"


def test_les_puces_restent_ignorees_comme_prose() -> None:
    """« * » et « - » suivis d'une espace sont toujours des puces."""
    texte = "Un paragraphe de prose complet et lisible ici.\n* une puce\n- une autre"

    assert _last_prose_line(texte).endswith("lisible ici.")


# ── 1. Cap de tokens du relecteur ───────────────────────────────────────────


def test_le_cap_de_tokens_du_check_couvre_la_consommation_reelle() -> None:
    """Mesure du 24/07/2026 : 1985 tokens de sortie pour un CHECK a 5 questions.

    Le cap doit garder une vraie marge, sinon le JSON se coupe et le verdict
    retombe silencieusement sur 'fix'.
    """
    from generation.checks_blocs import _MAX_TOKENS_CHECK

    assert _MAX_TOKENS_CHECK >= 4000, (
        f"Cap trop bas ({_MAX_TOKENS_CHECK}) : mesure reelle a 1985 tokens."
    )


# ── 4. La coupe de l'extrait ne doit pas passer pour un defaut du livrable ──


@pytest.mark.django_db
def test_l_extrait_du_relecteur_coupe_sur_une_ligne_entiere() -> None:
    """La coupe brute tombait au milieu d'un titre de source.

    Le relecteur signalait alors « le titre s'arrete a "Intelligen…" » comme
    une source incomplete du chapitre 21 : c'etait notre propre coupe.
    """
    from decimal import Decimal

    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.checks_blocs import _MAX_CONTENU_PAR_CHAPITRE, _extrait_chapitre
    from generation.models import ChapterGeneration, ChapterStatus, GenerationJob
    from orders.models import Order

    offer = Offer.objects.create(
        name="EM", slug="test-extrait-coupe",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="extrait@test.local")
    order = Order.objects.create(
        systeme_order_id="test-extrait-coupe-1", customer=customer, offer=offer,
    )
    job = GenerationJob.objects.create(
        order=order, deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=Decimal("3.20"),
    )
    ligne = (
        "- **Conseil national du numerique, « Intelligence artificielle et "
        "strategie industrielle europeenne »**, rapport 2024 | https://cnnumerique.fr/\n"
    )
    nb = (_MAX_CONTENU_PAR_CHAPITRE * 3) // len(ligne)
    chapitre = ChapterGeneration.objects.create(
        job=job, chapter_number=21, chapter_title="Sources et methodologie",
        prompt_key="em.21.sources", status=ChapterStatus.DONE,
        content=ligne * nb,
    )

    extrait = _extrait_chapitre(chapitre)

    assert "COUPE PAR L'OUTIL DE RELECTURE" in extrait
    # Le cadrage qui empeche le relecteur de rapporter notre coupe comme defaut.
    assert "PAS un defaut du livrable" in extrait
    # Aucune ligne de source ne doit etre coupee en plein milieu.
    for morceau in extrait.split("\n\n[... COUPE"):
        derniere = morceau.strip().splitlines()[-1] if morceau.strip() else ""
        if derniere.startswith("- **Conseil"):
            assert derniere.rstrip().endswith("https://cnnumerique.fr/"), (
                f"Ligne de source coupee en plein milieu : {derniere[-60:]!r}"
            )


# ── 5. La reparation « ajouter un point » masquait une vraie troncature ─────


def test_preposition_suivie_d_un_point_reste_une_troncature() -> None:
    """Chaine reelle de fin du chapitre 21 (job 4c573e40).

    La regle 1 (sentence_cut) repare en ajoutant un point. Sur une vraie
    coupure, cette reparation la rend invisible aux detecteurs deterministes :
    « ... redeployee vers des taches a. » est une phrase inachevee ponctuee.
    Seul le relecteur Sonnet l'avait vue.
    """
    corps = (
        "Cette estimation ne tient pas compte des economies secondaires "
        "(reduction des delais, recuperation de capacite interne redeployee "
        "vers des taches a."
    )

    codes = [v.name for v in detect_violations(corps * 20, "em.21.sources", 21)]

    assert "abrupt_ending" in codes, f"Troncature masquee par le point : {codes}"


def test_une_phrase_terminee_par_un_adverbe_n_est_pas_une_troncature() -> None:
    """« plus », « moins », « bien » terminent legitimement une phrase.

    Ils sont volontairement hors de la liste : les y mettre generait des
    regenerations inutiles sur du texte correct.
    """
    corps = (
        "Le marche est fragmente entre plusieurs acteurs specialises et "
        "generalistes, sans qu'aucun ne domine. Il n'en faut pas plus."
    )

    codes = [v.name for v in detect_violations(corps * 20, "em.16.offre_demande", 16)]

    assert "abrupt_ending" not in codes, f"Faux positif sur un adverbe : {codes}"


@pytest.mark.django_db
def test_une_reponse_illisible_fait_rejouer_le_check_sans_conclure() -> None:
    """Une reponse hors format ne doit pas valoir « defaut constate ».

    Avant : {} -> verdict 'fix' -> regeneration de tout le bloc + livraison
    bloquee, pour un defaut que personne n'avait vu.
    """
    from decimal import Decimal

    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.checks_blocs import BLOCS_PAR_IDENTIFIANT, check_bloc
    from generation.models import GenerationJob
    from integrations.claude import ClaudeResult
    from orders.models import Order

    offer = Offer.objects.create(
        name="EM", slug="test-check-illisible",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    customer = Customer.objects.create(email="illisible@test.local")
    order = Order.objects.create(
        systeme_order_id="test-check-illisible-1", customer=customer, offer=offer,
    )
    job = GenerationJob.objects.create(
        order=order, deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=Decimal("3.20"),
    )

    appels: list[int] = []

    class _ClientCoupePuisCorrect:
        def complete(self, *, system, prompt, max_tokens, model, **_kw):
            appels.append(1)
            if len(appels) == 1:
                # JSON tronque, exactement comme un depassement de max_tokens.
                contenu = '```json\n{"verdict": "pass", "reponses_questi'
            else:
                contenu = (
                    '```json\n{"verdict": "pass", "reponses_questions": [], '
                    '"note_corrective": "", "points_a_enrichir_fiche": []}\n```'
                )
            return ClaudeResult(
                content=contenu, model=model, input_tokens=10, output_tokens=10,
            )

    result = check_bloc(
        job, BLOCS_PAR_IDENTIFIANT["A"], [], client=_ClientCoupePuisCorrect(),
    )

    assert len(appels) == 2, "Le CHECK aurait du etre rejoue apres reponse illisible."
    assert result.est_ok, "Le second passage lisible dit 'pass' : pas de faux 'fix'."

"""Phase 46 — Le CHECK INITIAL repare la fiche avant de bloquer l'etude.

Mesure, pas supposition : premiere generation reelle lancee depuis l'espace
client (job `07745d4a`, 05/08/2026, commit `4415784`). L'etude est morte au
chapitre 0 pour **0,0127 EUR et aucun document**, sur cette note du relecteur :

    « Rediger integralement la fiche projet. Elle doit au minimum contenir :
      (1) une definition claire du marche etudie, (2) la zone geographique,
      (3) la devise, (4) la liste des questions/objectifs du client,
      (5) une section signalant explicitement les points non specifies par le
      client comme provisoires, (6) une precision sur le lecteur final vise et
      le niveau de langage attendu. »

Deux defauts distincts, et il faut les deux correctifs.

**1. Le relecteur reclamait ce que le redacteur n'avait jamais eu ordre
d'ecrire.** Le prompt de la fiche (manuel §2) prescrivait dix rubriques :
aucune ne portait la devise, aucune le lecteur final, et rien n'imposait de
signaler les points non specifies. Le CHECK INITIAL, lui, pose six questions
dont « Le niveau de langage et le type de lecteur final sont-ils bien
compris ? ». Le juge et le redacteur ne lisaient pas le meme cahier des
charges — c'est le judge-misalignment deja consigne au journal le 20/07/2026,
sur un autre controle.

**2. Le blocage etait une impasse.** Le code stoppait l'etude sans tenter la
moindre correction, au motif que « c'est la fiche projet — donc le brief du
client — qui est en cause », et invitait l'administrateur a corriger le brief.
Or aucune correction du brief n'aurait ajoute une ligne « devise » a la fiche :
la cause etait dans notre prompt. Le gate exigeait d'un humain une action sans
effet sur la cause (regle 1 : un controle qui ne peut pas etre satisfait).

Le manuel p.3 ouvre pourtant deux voies : « corriger la fiche OU demander la
precision necessaire ». Seule la seconde etait codee.

Contre-epreuve, verifiee ci-dessous : la trace n'est pas emoussee. Une fiche
qui reste refusee APRES correction ouvre toujours le meme incident HIGH — seule
la mort de l'etude a disparu, le 12/08/2026, sur decision cliente et sur une
mesure (`2b6cc7d6`, arrete a dix centimes pour une correction impossible).
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from generation.checks_blocs import CheckResult
from generation.models import ChapterStatus
from generation.runner import _after_chapter_hook
from monitoring.models import IncidentSeverity, OperationalIncident

_NOTE = "Fiche a completer : devise et lecteur final absents."


def _job_avec_fiche():
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import ChapterGeneration, GenerationJob
    from orders.models import Order

    offre = Offer.objects.create(
        name="EM", slug="test-check-initial-reprise",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="reprise@test.local")
    commande = Order.objects.create(
        systeme_order_id="test-check-initial-reprise-1", customer=client, offer=offre,
    )
    job = GenerationJob.objects.create(
        order=commande,
        deliverable_type=DeliverableType.MARKET_STUDY,
        budget_eur=Decimal("6.00"),
    )
    fiche = ChapterGeneration.objects.create(
        job=job, chapter_number=0, chapter_title="Fiche projet",
        prompt_key="em.00.fiche_projet", status=ChapterStatus.DONE,
        content="| Rubrique | Contenu |\n|---|---|\n| Projet | Joalie |",
    )
    return job, fiche


def _fix() -> CheckResult:
    return CheckResult(bloc_identifiant="INITIAL", verdict="fix", note_corrective=_NOTE)


def _pass() -> CheckResult:
    return CheckResult(bloc_identifiant="INITIAL", verdict="pass")


@pytest.mark.django_db
def test_la_fiche_refusee_est_regeneree_avec_la_note_du_relecteur() -> None:
    """Refus puis succes : l'etude continue, et la note a bien servi de consigne.

    Sur le code d'avant, `_after_chapter_hook` levait `CheckInitialBlockedError`
    des le premier refus : ce test echouait sur l'exception, et
    `regenerate_chapter` n'etait appele nulle part.
    """
    job, fiche = _job_avec_fiche()
    verdicts = [_fix(), _pass()]
    regenerations: list[tuple[int, str]] = []

    def _regenerer(job_, chapitre_, *, corrective_note="", client=None):
        regenerations.append((chapitre_.chapter_number, corrective_note))

    with patch("generation.runner.check_bloc", side_effect=lambda *a, **k: verdicts.pop(0)), \
         patch("generation.runner.regenerate_chapter", side_effect=_regenerer):
        _after_chapter_hook(job, fiche, client=object())  # ne doit PAS lever

    # La note du relecteur, SUIVIE de l'issue qu'il laisse implicite : retirer
    # un montant injustifiable est une reponse valide. Sans elle, le redacteur
    # tente la seule autre voie — inventer le calcul — et revient les mains
    # vides (business plan `2b6cc7d6`, 12/08/2026).
    assert len(regenerations) == 1
    assert regenerations[0][0] == 0
    assert regenerations[0][1].startswith(_NOTE)
    assert "RETIRE-le" in regenerations[0][1]
    assert not OperationalIncident.objects.filter(job=job).exists(), (
        "Une correction qui aboutit n'ouvre aucun incident."
    )


@pytest.mark.django_db
def test_une_fiche_toujours_refusee_laisse_la_redaction_continuer() -> None:
    """La fiche refusée ne tue plus l'étude.

    ## Ce que ce test verrouillait, et pourquoi il a changé

    Il gardait la protection du manuel p.2 — « on ne continue jamais par
    automatisme ». Décision cliente du 12/08/2026 : « quand il s'agit d'une
    incohérence, au lieu de mettre en échec, il faut plutôt corriger et mettre
    de la logique dedans ».

    La mesure qui la motive — business plan `2b6cc7d6` : le relecteur refuse la
    fiche parce qu'elle avance des montants absents du brief. Il a raison, et
    la correction qu'il réclame est IMPOSSIBLE : on ne justifie pas un chiffre
    qu'on n'a pas. La génération s'arrêtait à dix centimes, et la cliente
    n'avait rien — ni document, ni diagnostic exploitable.

    On ne continue pas par automatisme : on continue APRÈS avoir tenté la
    correction, en laissant une trace HIGH, et le gate juge le document à la
    fin. Un dossier livré avec un défaut nommé se corrige ; un dossier
    inexistant ne s'analyse même pas.
    """
    job, fiche = _job_avec_fiche()
    tentatives: list[int] = []

    def _regenerer(job_, chapitre_, *, corrective_note="", client=None):
        tentatives.append(chapitre_.chapter_number)

    with patch("generation.runner.check_bloc", return_value=_fix()), \
         patch("generation.runner.regenerate_chapter", side_effect=_regenerer):
        _after_chapter_hook(job, fiche, client=object())

    assert tentatives == [0], "Une seule tentative de correction, pas une boucle."

    fiche.refresh_from_db()
    assert fiche.status == ChapterStatus.DONE, (
        "La fiche reste DONE : c'est son contenu qui est en cause, pas sa production."
    )
    incidents = OperationalIncident.objects.filter(job=job)
    assert incidents.count() == 1
    assert incidents.first().severity == IncidentSeverity.HIGH


def test_le_prompt_de_la_fiche_couvre_les_questions_du_check_initial() -> None:
    """Le redacteur doit pouvoir repondre aux six questions qui le jugent.

    Ce test vise la CLASSE (regle 4) : ce n'est pas « la devise manquait », mais
    « le juge pose une question sur laquelle le redacteur n'a aucune consigne ».
    Il echoue sur le prompt d'avant, ou aucun des trois motifs n'apparaissait.
    """
    from generation.chapitres.configuration import RACINE_PROMPTS
    from generation.prompt_library import prompt_instruction

    vivant = (RACINE_PROMPTS / "etude_marche" / "chapitre_00.md").read_text(
        encoding="utf-8"
    )
    miroir = prompt_instruction("em.00.fiche_projet")

    # Question 6 du CHECK INITIAL : « Le niveau de langage et le type de lecteur
    # final sont-ils bien compris ? »
    # Question 5 : « Des contradictions ou informations critiques manquantes
    # doivent-elles etre clarifiees ? » — la fiche doit les DECLARER, ce que
    # l'addendum du relecteur accepte deja explicitement comme reponse valable.
    # La devise, elle, alimente le controle de devise a tolerance zero.
    for source, nom in ((vivant, "prompts/etude_marche/chapitre_00.md"),
                        (miroir, "prompt_library.em.00.fiche_projet")):
        minuscules = source.lower()
        for motif in ("devise", "lecteur final", "niveau de langage",
                      "points non specifies"):
            assert motif in minuscules, f"{nom} : « {motif} » absent."


def test_les_deux_sources_du_prompt_de_la_fiche_restent_d_accord() -> None:
    """Le `.md` est vivant pour l'EM, `prompt_library` en est le miroir.

    Les laisser diverger, c'est la regle 5 : deux sources pour une meme verite.
    Un export global avait deja ecrase les prompts vivants avec le miroir
    perime le 05/08/2026 au matin. Tant que la duplication existe, ce test la
    surveille.
    """
    from generation.chapitres.configuration import RACINE_PROMPTS
    from generation.prompt_library import prompt_instruction

    def _normaliser(texte: str) -> str:
        sans_bandeau = texte.split("-->", maxsplit=1)[-1]
        return " ".join(sans_bandeau.split())

    vivant = _normaliser(
        (RACINE_PROMPTS / "etude_marche" / "chapitre_00.md").read_text(encoding="utf-8")
    )
    miroir = _normaliser(prompt_instruction("em.00.fiche_projet"))
    assert vivant == miroir

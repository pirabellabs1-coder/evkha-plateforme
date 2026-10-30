"""La relecture finale corrige TOUT le document, et rejuge ce qu'elle a corrigé.

Mesuré sur l'étude IA `03ba4f93` (30/10/2026), 15,27 €, livraison bloquée par
22 motifs « CHECK de bloc non résolu » :

1. une seule passe corrigeait — la seconde constatait et s'arrêtait — et au
   plus huit chapitres, pris dans l'ordre des numéros : chapitres 1 à 8
   réécrits, 9 à 22 jamais. L'entonnoir faux du chapitre 9 (18,4 Md€ au-dessus
   de 4 Md€) et le revenu des années 1 à 3 du chapitre 22 sont restés ;
2. rien ne rejugeait un bloc après sa réécriture : les phrases reprochées au
   bloc E avaient quitté le document, et le bloc comptait toujours parmi les
   motifs de blocage. Le rejeu existait, derrière le seul bouton « corriger ».

Ces tests échouent sur le code d'avant. Les contre-épreuves vérifient qu'un
motif déjà tenté à l'identique ne fait pas repayer un chapitre, et qu'un bloc
que rien n'a touché n'est pas rejugé.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from generation import controle_final
from generation.verification.rapport import RapportControle

pytestmark = pytest.mark.django_db


@pytest.fixture
def job() -> Any:
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.services import bootstrap_generation_job
    from intake.models import IntakeStatus, IntakeSubmission
    from orders.models import Order

    offre = Offer.objects.create(
        name="Étude", slug="em-relecture-complete",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="relecture-complete@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id="cmd-relecture-complete", customer=client, offer=offre
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "conseil en IA", "PAYS": "France"},
    )
    return bootstrap_generation_job(soumission)


class _Livrable:
    controle = RapportControle()


def _bloc(chapitre: int, note: str = "aligner les chiffres") -> Any:
    from generation.gate import GateFailure

    return GateFailure(
        check="check_bloc_non_resolu",
        detail=f"CHECK non valide. Note du relecteur : ch. {chapitre}, {note}.",
        chapter_number=chapitre,
    )


def _monter(
    monkeypatch: pytest.MonkeyPatch, gate_par_passe: list[tuple[Any, ...]]
) -> tuple[list[int], list[list[int]]]:
    """Remplace assemblage, réécriture, gate et rejeu. Rend (réécrits, rejeux)."""
    from documents import livrable_word
    from generation import checks_blocs
    from generation import runner as moteur

    reecrits: list[int] = []
    rejeux: list[list[int]] = []
    lectures = list(gate_par_passe)

    def _gate(job: Any) -> tuple[Any, ...]:
        return lectures.pop(0) if len(lectures) > 1 else lectures[0]

    def _rejouer(job: Any, *, client: Any = None, chapitres_reecrits: Any = None) -> int:
        rejeux.append(sorted(chapitres_reecrits))
        return 0

    monkeypatch.setattr(livrable_word, "assembler_livrable_word", lambda j, **k: _Livrable())
    monkeypatch.setattr(livrable_word, "chaine_word_active", lambda j: True)
    monkeypatch.setattr(
        moteur, "regenerate_chapter",
        lambda j, chapitre, **k: reecrits.append(chapitre.chapter_number),
    )
    monkeypatch.setattr(controle_final, "_echecs_du_gate", _gate)
    monkeypatch.setattr(checks_blocs, "rejouer_les_checks_ouverts", _rejouer)
    return reecrits, rejeux


# ── 1. Tout le document est corrigé ──────────────────────────────────────────


def test_les_chapitres_au_dela_du_huitieme_sont_corriges(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LE cas de `03ba4f93` : douze chapitres fautifs, deux passes qui corrigent.

    Sur le code d'avant, seuls 1 à 8 étaient réécrits.
    """
    fautifs = tuple(_bloc(n) for n in range(1, 13))
    rafraichis = tuple(_bloc(n, "nouvelle note") for n in range(1, 13))
    reecrits, _ = _monter(monkeypatch, [fautifs, rafraichis, rafraichis])

    controle_final.relire_et_corriger(job)

    assert {9, 10, 11, 12} <= set(reecrits), reecrits


def test_a_la_seconde_passe_les_chapitres_jamais_corriges_passent_devant(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Les conclusions chiffrées, en fin de document, ne passent plus en dernier."""
    fautifs = tuple(_bloc(n) for n in range(1, 13))
    rafraichis = tuple(_bloc(n, "nouvelle note") for n in range(1, 13))
    reecrits, _ = _monter(monkeypatch, [fautifs, rafraichis, rafraichis])

    controle_final.relire_et_corriger(job)

    seconde_passe = reecrits[8:]
    assert seconde_passe[:4] == [9, 10, 11, 12], reecrits


# ── 2. Ce qui a été corrigé est rejugé ───────────────────────────────────────


def test_un_bloc_reecrit_est_rejuge_avant_la_lecture_suivante(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LE défaut du bloc E : corrigé dans le document, toujours compté bloquant.

    Sur le code d'avant, aucun rejeu : le blocage restait sur l'ancien verdict.
    """
    reecrits, rejeux = _monter(monkeypatch, [(_bloc(7),), ()])

    controle_final.relire_et_corriger(job)

    assert reecrits == [7]
    assert rejeux == [[7]]


def test_le_rejeu_ne_porte_que_sur_les_chapitres_de_la_passe(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fautifs = (_bloc(3), _bloc(9))
    rafraichi = (_bloc(9, "nouvelle note"),)
    _, rejeux = _monter(monkeypatch, [fautifs, rafraichi, ()])

    controle_final.relire_et_corriger(job)

    assert rejeux == [[3, 9], [9]]


def test_un_budget_epuise_ne_paie_pas_le_rejeu(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from generation import cost

    _, rejeux = _monter(monkeypatch, [(_bloc(7),), ()])
    soldes = iter([Decimal("5"), Decimal("5"), Decimal("0.05")])
    monkeypatch.setattr(cost, "budget_restant", lambda j: next(soldes, Decimal("0.05")))

    controle_final.relire_et_corriger(job)

    assert rejeux == []


# ── Contre-épreuves : ne pas repayer pour rien ───────────────────────────────


def test_un_motif_deja_tente_a_l_identique_ne_fait_pas_repayer(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le même reproche à la même version ne donne pas un autre texte."""
    reecrits, _ = _monter(monkeypatch, [(_bloc(3),)])

    rapport = controle_final.relire_et_corriger(job)

    assert reecrits == [3]
    assert "déjà été tentés à l'identique" in rapport.motif_d_arret


def test_une_note_rafraichie_relance_la_correction(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le relecteur rejugé donne une NOUVELLE consigne : elle mérite un essai."""
    reecrits, _ = _monter(
        monkeypatch, [(_bloc(3),), (_bloc(3, "nouvelle note"),), ()]
    )

    controle_final.relire_et_corriger(job)

    assert reecrits == [3, 3]


def test_la_derniere_lecture_verifie_sans_reecrire(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trois lectures, deux qui corrigent : la dernière ne paie rien."""
    lectures = [(_bloc(3, f"note {n}"),) for n in range(1, 6)]
    reecrits, _ = _monter(monkeypatch, lectures)

    rapport = controle_final.relire_et_corriger(job)

    assert reecrits == [3, 3]
    assert rapport.passes == 3
    assert "plafond de 3 passes" in rapport.motif_d_arret


# ── Le rejeu lui-même ────────────────────────────────────────────────────────


def _incident(job: Any, bloc: str) -> Any:
    from monitoring.models import IncidentSeverity, OperationalIncident

    return OperationalIncident.objects.create(
        title=f"CHECK bloc {bloc}",
        severity=IncidentSeverity.MEDIUM,
        job=job,
        order=job.order,
        details={"type": "check_bloc_non_resolu", "bloc": bloc, "note_corrective": "x"},
    )


def test_le_rejeu_borne_ne_juge_que_les_blocs_touches(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bloc E (7, 8) réécrit : il est rejugé et fermé ; le bloc A n'est pas payé."""
    from generation import checks_blocs
    from generation.models import ChapterStatus
    from monitoring.models import IncidentStatus

    job.chapters.filter(chapter_number__in=[1, 2, 7, 8]).update(status=ChapterStatus.DONE)
    bloc_a, bloc_e = _incident(job, "A"), _incident(job, "E")
    juges: list[str] = []

    def _check(job: Any, bloc: Any, chapitres: Any, *, client: Any = None) -> Any:
        juges.append(bloc.identifiant)
        return checks_blocs.CheckResult(bloc_identifiant=bloc.identifiant, verdict="pass")

    monkeypatch.setattr(checks_blocs, "check_bloc", _check)
    monkeypatch.setattr(checks_blocs, "get_claude_client", lambda: object())

    fermes = checks_blocs.rejouer_les_checks_ouverts(job, chapitres_reecrits=[7])

    assert juges == ["E"]
    assert fermes == 1
    bloc_a.refresh_from_db()
    bloc_e.refresh_from_db()
    assert bloc_e.status == IncidentStatus.RESOLVED
    assert bloc_a.status == IncidentStatus.OPEN


def test_sans_bloc_touche_aucun_client_n_est_cree(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTRE-ÉPREUVE : rien à rejuger, aucune connexion au modèle."""
    from generation import checks_blocs

    _incident(job, "A")

    def _interdit() -> Any:
        raise AssertionError("aucun client ne devait être créé")

    monkeypatch.setattr(checks_blocs, "get_claude_client", _interdit)

    assert checks_blocs.rejouer_les_checks_ouverts(job, chapitres_reecrits=[15]) == 0

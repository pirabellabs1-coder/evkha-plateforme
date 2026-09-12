"""Le document assemblé est relu, corrigé, puis refait — avant de partir.

Tout ce que ce dépôt contrôlait jusqu'ici jugeait la MATIÈRE du document : les
chapitres validés, le markdown rendu. Le `.docx` que le client ouvre n'était relu
par personne avant l'envoi — la seule passe qui le lisait tournait à l'intérieur
de l'assemblage, ne servait qu'à retenir l'envoi, et ne déclenchait aucune
correction. Ses réserves partaient avec le document.

Demande du 12/09/2026 : « une fois que le document est terminé, l'agent prend le
document, il valide, et s'il y a des zéros ou des incohérences dedans, il corrige ;
le document ressort ensuite en PDF, vraiment propre ».

Ces tests échouent sur le code d'avant : `generation.controle_final` n'existait
pas, et la tâche livrait sans jamais relire le fichier. Les contre-épreuves
vérifient qu'un document propre ne coûte RIEN, qu'un budget épuisé n'entame pas
une réécriture qu'il ne pourrait pas finir, et qu'un défaut de rendu — que
réécrire un chapitre ne réparerait pas — n'envoie personne au modèle.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from generation import controle_final
from generation.verification.rapport import Anomalie, Gravite, RapportControle

pytestmark = pytest.mark.django_db


@pytest.fixture
def job() -> Any:
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.services import bootstrap_generation_job
    from intake.models import IntakeStatus, IntakeSubmission
    from orders.models import Order

    offre = Offer.objects.create(
        name="Stratégie", slug="strat-relecture",
        deliverable_type=DeliverableType.BUSINESS_STRATEGY,
    )
    client = Customer.objects.create(email="relecture@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id="cmd-relecture", customer=client, offer=offre
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "assistance informatique", "PAYS": "France"},
    )
    return bootstrap_generation_job(soumission)


class _Livrable:
    """Ce que l'assemblage rend : un document et le contrôle de ce document."""

    def __init__(self, controle: RapportControle) -> None:
        self.controle = controle


def _controle(*anomalies: Anomalie) -> RapportControle:
    rapport = RapportControle()
    rapport.ajouter(*anomalies)
    return rapport


def _chiffre_hors_socle(chapitre: int | None = 7) -> Anomalie:
    return Anomalie(
        "chiffres_hors_socle", Gravite.AVERTISSEMENT,
        "« 900 M€ » n'a pas d'équivalent dans le socle.",
        chapitre=chapitre, extrait="un marché national estimé à 900 M€",
    )


def _monter(
    monkeypatch: pytest.MonkeyPatch, controles: list[RapportControle]
) -> tuple[list[bool], list[tuple[int, str]]]:
    """Remplace l'assemblage et la réécriture. Rend (assemblages, réécritures)."""
    from documents import livrable_word
    from generation import runner as moteur

    assemblages: list[bool] = []
    reecritures: list[tuple[int, str]] = []
    restants = list(controles)

    def _assembler(job: Any, **kwargs: Any) -> _Livrable:
        assemblages.append(bool(kwargs.get("ouvrir_incident", True)))
        return _Livrable(restants.pop(0) if restants else _controle())

    def _reecrire(job: Any, chapitre: Any, *, corrective_note: str, client: Any = None) -> None:
        reecritures.append((chapitre.chapter_number, corrective_note))

    monkeypatch.setattr(livrable_word, "assembler_livrable_word", _assembler)
    monkeypatch.setattr(livrable_word, "chaine_word_active", lambda job: True)
    monkeypatch.setattr(moteur, "regenerate_chapter", _reecrire)
    return assemblages, reecritures


def test_un_defaut_du_fichier_fait_reecrire_son_chapitre_puis_refaire_le_document(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LE test : lire le fichier, corriger le chapitre, REFAIRE le document."""
    assemblages, reecritures = _monter(
        monkeypatch, [_controle(_chiffre_hors_socle(7)), _controle()]
    )

    rapport = controle_final.relire_et_corriger(job)

    assert [n for n, _ in reecritures] == [7]
    assert len(assemblages) == 2, "le document est refait après la correction"
    assert rapport.chapitres_reecrits == [7]
    assert rapport.anomalies_au_depart == 1
    assert rapport.anomalies_restantes == 0


def test_la_consigne_donne_le_passage_a_corriger(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un motif doit être trouvable dans le document par qui doit le corriger."""
    _, reecritures = _monter(monkeypatch, [_controle(_chiffre_hors_socle(7))])

    controle_final.relire_et_corriger(job)

    (_, consigne) = reecritures[0]
    assert "900 M€" in consigne
    assert "un marché national estimé à 900 M€" in consigne
    # La consigne ne parle jamais au rédacteur de sa version précédente.
    for mot in ("version précédente", "refusé", "tentative"):
        assert mot not in consigne.lower()


def test_un_document_propre_ne_coute_rien(job: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """CONTRE-ÉPREUVE : rien à réparer, aucun appel au modèle, un seul assemblage."""
    assemblages, reecritures = _monter(monkeypatch, [_controle()])

    rapport = controle_final.relire_et_corriger(job)

    assert reecritures == []
    assert len(assemblages) == 1
    assert "aucune anomalie réparable" in rapport.motif_d_arret


def test_un_defaut_de_rendu_n_envoie_personne_au_modele(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un tableau vide ne se répare pas en réécrivant un chapitre : on le NOMME."""
    integrite = Anomalie(
        "integrite", Gravite.BLOQUANTE,
        "3 tableau(x) vide(s) : des lignes ont été perdues au rendu.",
    )
    _, reecritures = _monter(monkeypatch, [_controle(integrite)])

    rapport = controle_final.relire_et_corriger(job)

    assert reecritures == []
    assert rapport.anomalies_restantes == 1
    assert any("integrite" in ligne for ligne in rapport.restantes)


def test_un_budget_epuise_n_entame_pas_une_reecriture(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Une réécriture interrompue en cours laisserait un chapitre à moitié refait."""
    from generation import cost

    _, reecritures = _monter(monkeypatch, [_controle(_chiffre_hors_socle(7))])
    monkeypatch.setattr(cost, "budget_restant", lambda job: Decimal("0.05"))

    rapport = controle_final.relire_et_corriger(job)

    assert reecritures == []
    assert "budget" in rapport.motif_d_arret


def test_une_anomalie_sans_chapitre_ne_fait_rien_reecrire(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sans numéro, on ne sait pas quoi réécrire — et on ne devine pas."""
    _, reecritures = _monter(monkeypatch, [_controle(_chiffre_hors_socle(None))])

    rapport = controle_final.relire_et_corriger(job)

    assert reecritures == []
    assert rapport.anomalies_restantes == 1


def test_la_relecture_n_ouvre_aucun_incident_de_reserves(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C'est la livraison qui ouvre le sien, sur le fichier réellement envoyé.

    Un incident par passe en donnerait trois pour un seul document, dont deux
    décrivant des fichiers qui n'existent plus.
    """
    assemblages, _ = _monter(
        monkeypatch, [_controle(_chiffre_hors_socle(7)), _controle(_chiffre_hors_socle(7))]
    )

    controle_final.relire_et_corriger(job)

    assert assemblages == [False, False]


def test_un_assemblage_impossible_ne_tue_pas_la_livraison(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le client a payé un document : une panne de relecture ne le lui retire pas."""
    from documents import livrable_word

    def _casser(job: Any, **kwargs: Any) -> None:
        msg = "disque plein"
        raise OSError(msg)

    monkeypatch.setattr(livrable_word, "assembler_livrable_word", _casser)
    monkeypatch.setattr(livrable_word, "chaine_word_active", lambda job: True)

    rapport = controle_final.relire_et_corriger(job)

    assert "assemblage impossible" in rapport.motif_d_arret


def test_la_relecture_precede_l_envoi_dans_le_pipeline(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LE branchement : relu AVANT d'être envoyé, jamais après."""
    from generation import runner as moteur
    from generation import tasks
    from generation.models import JobStatus

    ordre: list[str] = []
    job.status = JobStatus.DONE
    job.save(update_fields=["status"])

    monkeypatch.setattr(moteur, "run_generation_job", lambda j: j)
    monkeypatch.setattr(tasks, "run_qa_pass", lambda j: None, raising=False)
    monkeypatch.setattr(tasks, "_controler_les_demandes_du_client", lambda j: None)
    monkeypatch.setattr(tasks, "_effacer_les_textes_orphelins", lambda: None)
    monkeypatch.setattr(
        tasks, "run_correction_loop",
        lambda j, **kw: type("R", (), {"passed": True, "failures": []})(),
        raising=False,
    )
    from generation import controle_final as relecture

    def _relire(j: Any, **kw: Any) -> relecture.RapportRelecture:
        ordre.append("relecture")
        return relecture.RapportRelecture()

    monkeypatch.setattr(relecture, "relire_avant_envoi", _relire)
    monkeypatch.setattr(tasks, "_livrer", lambda j: ordre.append("envoi"))

    tasks.run_generation_job_task(str(job.id))

    assert ordre == ["relecture", "envoi"]


# ── La densité, enfin réparable ──────────────────────────────────────────────


def test_le_mur_de_texte_nomme_ses_chapitres() -> None:
    """« 32 % des paragraphes dépassent 60 mots » ne dit pas lesquels réécrire.

    Mesuré sur la stratégie Zenitek (11/09/2026) : deux constats de densité,
    aucun chapitre, donc rien à corriger. Le même calcul chapitre par chapitre
    les nomme — et la cliente avait refusé une livraison entière pour ce seul
    défaut.
    """
    from generation.verification.controles import controler_densite
    from generation.verification.lecture import DocumentLu

    long = " ".join(["mot"] * 70)
    court = "Une phrase courte."
    document = DocumentLu(
        chemin=Path("livrable.docx"),
        paragraphes=[long, long, long, court, court, court],
        chapitre_du_paragraphe=[2, 2, 2, 5, 5, 5],
        cellules=["12 €"] * 40,
        chapitre_de_la_cellule=[2] * 40,
    )

    anomalies = controler_densite(document)
    par_chapitre = [a.chapitre for a in anomalies if a.chapitre]

    assert par_chapitre == [2], "seul le chapitre dense est renvoyé à la réécriture"
    assert any(a.chapitre is None for a in anomalies), "le constat d'ensemble reste"
    assert "densite" in controle_final.REPARABLES_PAR_CHAPITRE


def test_un_document_sans_numeros_de_chapitre_reste_controle() -> None:
    """Régression attrapée par trois tests existants, le 12/09/2026.

    En rattachant chaque passage à son chapitre, l'appariement rendait ZÉRO
    passage pour un document lu sans numéros — une doublure, la chaîne HTML
    héritée. Le contrôle des calculs annoncés cessait alors de regarder quoi
    que ce soit, sans rien dire (règle 1).
    """
    from generation.verification.controles import controler_les_calculs_annonces
    from generation.verification.lecture import DocumentLu

    document = DocumentLu(
        chemin=Path("livrable.docx"),
        paragraphes=["130 000 € sur 1 000 000 €, soit 42 %."],
    )

    anomalies = controler_les_calculs_annonces(document)

    assert len(anomalies) == 1
    assert anomalies[0].chapitre is None


# ── L'étape doit se VOIR ─────────────────────────────────────────────────────


def test_la_relecture_laisse_sa_trace_sur_le_dossier(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """« On doit voir l'agent contrôleur ici » (12/09/2026).

    L'étape tournait entre l'assemblage et l'envoi sans rien montrer : un
    document relu et corrigé se présentait comme un document jamais relu.
    """
    from generation.models import GenerationJob

    _monter(monkeypatch, [_controle(_chiffre_hors_socle(7)), _controle()])

    controle_final.relire_avant_envoi(job)

    trace = GenerationJob.objects.get(pk=job.pk).controle_final
    assert trace["chapitres_reecrits"] == [7]
    assert trace["anomalies_au_depart"] == 1
    assert trace["anomalies_restantes"] == 0


def test_la_console_montre_la_relecture(
    job: Any, client_admin: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _monter(monkeypatch, [_controle(_chiffre_hors_socle(7)), _controle()])
    controle_final.relire_avant_envoi(job)

    reponse = client_admin.get(f"/api/dashboard/jobs/{job.id}/")

    assert reponse.status_code == 200
    assert reponse.json()["controle_final"]["chapitres_reecrits"] == [7]


def test_un_dossier_jamais_relu_ne_montre_rien(job: Any, client_admin: Any) -> None:
    """CONTRE-ÉPREUVE : un dossier d'avant n'affiche pas une étape qu'il n'a pas eue."""
    reponse = client_admin.get(f"/api/dashboard/jobs/{job.id}/")
    assert reponse.json()["controle_final"] is None

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


def _calcul_faux(chapitre: int | None = 7) -> Anomalie:
    # Un défaut RÉPARABLE. Ces tests utilisaient « chiffre hors socle », qui ne
    # fait plus réécrire depuis le 14/09/2026 (trop peu précis, mesuré sur le
    # corpus) : ils jugent le mécanisme de réécriture, pas ce contrôle-là.
    return Anomalie(
        "calcul_faux", Gravite.AVERTISSEMENT,
        "« 900 M€ » : le calcul annoncé donne 90 M€.",
        chapitre=chapitre, extrait="un marché national estimé à 900 M€",
    )


def _monter(
    monkeypatch: pytest.MonkeyPatch,
    controles: list[RapportControle],
    echecs_du_gate: tuple[Any, ...] = (),
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
    # Le gate de livraison est relu par le contrôleur depuis le 13/09/2026. Ici
    # on le FIXE : ces tests jugent la lecture du fichier, pas le gate.
    monkeypatch.setattr(controle_final, "_echecs_du_gate", lambda job: echecs_du_gate)
    return assemblages, reecritures


def test_un_defaut_du_fichier_fait_reecrire_son_chapitre_puis_refaire_le_document(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LE test : lire le fichier, corriger le chapitre, REFAIRE le document."""
    assemblages, reecritures = _monter(
        monkeypatch, [_controle(_calcul_faux(7)), _controle()]
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
    _, reecritures = _monter(monkeypatch, [_controle(_calcul_faux(7))])

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

    _, reecritures = _monter(monkeypatch, [_controle(_calcul_faux(7))])
    monkeypatch.setattr(cost, "budget_restant", lambda job: Decimal("0.05"))

    rapport = controle_final.relire_et_corriger(job)

    assert reecritures == []
    assert "budget" in rapport.motif_d_arret


def test_une_anomalie_sans_chapitre_ne_fait_rien_reecrire(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sans numéro, on ne sait pas quoi réécrire — et on ne devine pas."""
    _, reecritures = _monter(monkeypatch, [_controle(_calcul_faux(None))])

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
        monkeypatch, [_controle(_calcul_faux(7)), _controle(_calcul_faux(7))]
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

    _monter(monkeypatch, [_controle(_calcul_faux(7)), _controle()])

    controle_final.relire_avant_envoi(job)

    trace = GenerationJob.objects.get(pk=job.pk).controle_final
    assert trace["chapitres_reecrits"] == [7]
    assert trace["anomalies_au_depart"] == 1
    assert trace["anomalies_restantes"] == 0


def test_la_console_montre_la_relecture(
    job: Any, client_admin: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _monter(monkeypatch, [_controle(_calcul_faux(7)), _controle()])
    controle_final.relire_avant_envoi(job)

    reponse = client_admin.get(f"/api/dashboard/jobs/{job.id}/")

    assert reponse.status_code == 200
    assert reponse.json()["controle_final"]["chapitres_reecrits"] == [7]


def test_un_dossier_jamais_relu_ne_montre_rien(job: Any, client_admin: Any) -> None:
    """CONTRE-ÉPREUVE : un dossier d'avant n'affiche pas une étape qu'il n'a pas eue."""
    reponse = client_admin.get(f"/api/dashboard/jobs/{job.id}/")
    assert reponse.json()["controle_final"] is None


# ── Ce que le premier vrai dossier a appris (12/09/2026) ─────────────────────


def test_les_passes_n_emploient_pas_libreoffice(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Convertir en PDF à chaque passe faisait tourner LibreOffice pour rien.

    Sur la reprise `655b0908` — deux cents pages — la tâche est morte à cette
    étape : ni document envoyé, ni trace, ni incident. Les passes vérifient le
    CONTENU ; c'est la livraison qui convertit.
    """
    from documents import livrable_word
    from generation import runner as moteur

    conversions: list[bool] = []

    def _assembler(job: Any, **kwargs: Any) -> _Livrable:
        conversions.append(bool(kwargs.get("convertir", True)))
        return _Livrable(_controle())

    monkeypatch.setattr(livrable_word, "assembler_livrable_word", _assembler)
    monkeypatch.setattr(livrable_word, "chaine_word_active", lambda job: True)
    monkeypatch.setattr(moteur, "regenerate_chapter", lambda *a, **k: None)

    controle_final.relire_et_corriger(job)

    assert conversions == [False]


def test_une_relecture_morte_en_cours_laisse_sa_trace(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Règle 1 : ce qui échoue ne se tait pas.

    Un worker tué pendant la relecture laissait un dossier identique à un
    dossier jamais relu. La trace s'ouvre donc AVANT la première passe.
    """
    from documents import livrable_word
    from generation.models import GenerationJob

    def _mourir(job: Any, **kwargs: Any) -> None:
        raise MemoryError

    monkeypatch.setattr(livrable_word, "assembler_livrable_word", _mourir)
    monkeypatch.setattr(livrable_word, "chaine_word_active", lambda job: True)

    controle_final.relire_et_corriger(job)

    assert GenerationJob.objects.get(pk=job.pk).controle_final["motif_d_arret"] == "en cours"


def test_une_relecture_qui_meurt_n_empeche_pas_la_livraison(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un perfectionnement qui emporte la livraison est pire que son absence.

    Le client a payé un document : une panne de relecture ne le lui retire pas.
    """
    from generation import controle_final as relecture
    from generation import runner as moteur
    from generation import tasks
    from generation.models import JobStatus
    from monitoring.models import OperationalIncident

    ordre: list[str] = []
    job.status = JobStatus.DONE
    job.save(update_fields=["status"])

    def _mourir(j: Any, **kw: Any) -> None:
        msg = "worker tué"
        raise RuntimeError(msg)

    monkeypatch.setattr(moteur, "run_generation_job", lambda j: j)
    monkeypatch.setattr(tasks, "run_qa_pass", lambda j: None, raising=False)
    monkeypatch.setattr(tasks, "_controler_les_demandes_du_client", lambda j: None)
    monkeypatch.setattr(tasks, "_effacer_les_textes_orphelins", lambda: None)
    monkeypatch.setattr(
        tasks, "run_correction_loop",
        lambda j, **kw: type("R", (), {"passed": True, "failures": []})(),
        raising=False,
    )
    monkeypatch.setattr(relecture, "relire_avant_envoi", _mourir)
    monkeypatch.setattr(tasks, "_livrer", lambda j: ordre.append("envoi"))

    tasks.run_generation_job_task(str(job.id))

    assert ordre == ["envoi"], "le document part malgré la panne"
    assert OperationalIncident.objects.filter(
        job=job, title__contains="Controle final"
    ).exists(), "et la panne se voit"


# ── Le gardien : ce qui meurt en silence finit par partir ────────────────────


def _vieillir(job: Any, minutes: int) -> None:
    from datetime import timedelta

    from django.utils import timezone

    from generation.models import GenerationJob

    GenerationJob.objects.filter(pk=job.pk).update(
        updated_at=timezone.now() - timedelta(minutes=minutes)
    )


def test_un_controle_tue_en_cours_finit_par_livrer(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le document était prêt, payé, et personne ne l'envoyait (12/09/2026).

    Un processus tué n'exécute aucun `except` : sortir le contrôle dans sa
    propre tâche réduit le risque, ce gardien le ferme.
    """
    from generation import tasks
    from generation.models import GenerationJob, JobStatus
    from monitoring.models import OperationalIncident

    envois: list[Any] = []
    GenerationJob.objects.filter(pk=job.pk).update(
        status=JobStatus.DONE, controle_final={"motif_d_arret": "en cours"}
    )
    _vieillir(job, 30)
    monkeypatch.setattr(tasks, "_livrer", lambda j: envois.append(j.id))

    assert tasks.livrer_les_dossiers_oublies() == 1
    assert envois == [job.id]
    assert OperationalIncident.objects.filter(job=job, title__contains="interrompu").exists()


def test_un_controle_termine_n_est_pas_relivre(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTRE-ÉPREUVE : un dossier relu jusqu'au bout ne repart pas."""
    from generation import tasks
    from generation.models import GenerationJob, JobStatus

    envois: list[Any] = []
    GenerationJob.objects.filter(pk=job.pk).update(
        status=JobStatus.DONE,
        controle_final={"motif_d_arret": "aucune anomalie réparable", "passes": 1},
    )
    _vieillir(job, 30)
    monkeypatch.setattr(tasks, "_livrer", lambda j: envois.append(j.id))

    assert tasks.livrer_les_dossiers_oublies() == 0
    assert envois == []


def test_un_controle_en_cours_depuis_deux_minutes_est_laisse_tranquille(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTRE-ÉPREUVE : une relecture qui travaille encore n'est pas doublée."""
    from generation import tasks
    from generation.models import GenerationJob, JobStatus

    envois: list[Any] = []
    GenerationJob.objects.filter(pk=job.pk).update(
        status=JobStatus.DONE, controle_final={"motif_d_arret": "en cours"}
    )
    _vieillir(job, 2)
    monkeypatch.setattr(tasks, "_livrer", lambda j: envois.append(j.id))

    assert tasks.livrer_les_dossiers_oublies() == 0


# ── Un SEUL agent corrige (13/09/2026) ───────────────────────────────────────
#
# Jusqu'au 13/09/2026, deux correcteurs se suivaient : la boucle de correction
# du gate, dans la tâche de génération, puis cette relecture finale. Sur la
# stratégie Zenitek `a678b10a`, la première a réécrit cinq chapitres pendant
# dix-huit minutes pour près de deux euros — sans fermer ses propres motifs —
# et la seconde a trouvé le budget vide : « budget du dossier épuisé », zéro
# chapitre corrigé, trente anomalies laissées. Le client avait demandé UN agent.


def _fourchette(chapitre: int) -> Any:
    from generation.gate import GateFailure

    return GateFailure(
        check="fourchette_interdite",
        detail="Fourchette detectee : « 60-75 € ». Le document doit citer un chiffre unique.",
        chapter_number=chapitre,
    )


def test_un_motif_du_gate_fait_reecrire_son_chapitre_par_le_controleur(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LE test : le contrôleur traite ce que la boucle du gate traitait.

    Sur le code d'avant, il ignorait le gate — la boucle supprimée, ces motifs
    seraient partis chez le client sans avoir été retentés.
    """
    _, reecritures = _monter(
        monkeypatch, [_controle(), _controle()], echecs_du_gate=(_fourchette(10),),
    )

    rapport = controle_final.relire_et_corriger(job)

    assert [n for n, _ in reecritures] == [10]
    assert "60-75 €" in reecritures[0][1]
    assert any("fourchette_interdite" in ligne for ligne in rapport.restantes)


def test_un_chapitre_n_est_reecrit_qu_une_fois_avec_TOUS_ses_motifs(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deux listes de motifs, un seul appel au modèle par chapitre.

    Deux réécritures du même chapitre — une par correcteur — payaient deux fois
    pour un texte dont la seconde version ignorait la première consigne.
    """
    _, reecritures = _monter(
        monkeypatch,
        [_controle(_calcul_faux(10)), _controle()],
        echecs_du_gate=(_fourchette(10),),
    )

    controle_final.relire_et_corriger(job)

    assert [n for n, _ in reecritures] == [10], reecritures
    consigne = reecritures[0][1]
    assert "900 M€" in consigne and "60-75 €" in consigne


def test_la_generation_ne_lance_plus_de_boucle_de_correction(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le premier correcteur affamait le second : il ne tourne plus.

    L'appel est COMPTÉ et non piégé par une exception : l'ancien pipeline
    avalait toute exception de la boucle, un piège n'aurait rien prouvé.
    """
    from documents import livrable_word
    from generation import correction, tasks
    from generation import runner as moteur
    from generation.models import JobStatus

    appels: list[str] = []
    job.status = JobStatus.DONE
    job.save(update_fields=["status"])
    monkeypatch.setattr(moteur, "run_generation_job", lambda j: j)
    monkeypatch.setattr(tasks, "run_generation_job", lambda j: j)
    monkeypatch.setattr(tasks, "_controler_les_demandes_du_client", lambda j: None)
    monkeypatch.setattr(tasks, "_effacer_les_textes_orphelins", lambda: None)
    monkeypatch.setattr("generation.qa.run_qa_pass", lambda j: None)
    # Chaîne Word ACTIVE : c'est là que le contrôleur final corrige. Hors chaîne
    # Word, la boucle reste le seul correcteur (test plus bas).
    monkeypatch.setattr(livrable_word, "chaine_word_active", lambda j: True)
    monkeypatch.setattr(
        correction, "run_correction_loop", lambda j, **kw: appels.append("boucle"),
    )
    monkeypatch.setattr(tasks.controler_puis_livrer_task, "delay", lambda *a, **k: None)

    tasks.run_generation_job_task(str(job.id))

    assert appels == []


def test_le_verdict_du_gate_est_rendu_APRES_la_correction(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un point « non résolu » doit l'être sur le document qui part.

    Rendu avant la correction, l'incident annonçait non résolus des motifs
    qu'on n'avait pas encore essayé de résoudre (règle 2).
    """
    from generation import tasks

    ordre: list[str] = []

    def _relire(j: Any, **kw: Any) -> controle_final.RapportRelecture:
        ordre.append("correction")
        return controle_final.RapportRelecture()

    monkeypatch.setattr(controle_final, "relire_avant_envoi", _relire)
    monkeypatch.setattr(tasks, "_rendre_le_verdict_du_gate", lambda j: ordre.append("verdict"))
    monkeypatch.setattr(tasks, "_livrer", lambda j: ordre.append("envoi"))
    monkeypatch.setattr(tasks, "_effacer_les_textes_orphelins", lambda: None)

    tasks.controler_puis_livrer_task(str(job.id))

    # L'envoi AVANT le verdict : un worker tué pendant le rendu du gate ne doit
    # pas priver le client de son document (relecture du 13/09/2026).
    assert ordre == ["correction", "envoi", "verdict"]


def test_un_verdict_en_panne_n_emporte_pas_l_envoi(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CONTRE-ÉPREUVE : un verdict n'est pas la livraison."""
    from generation import tasks

    def _panne(j: Any) -> None:
        raise RuntimeError("gate illisible")

    envois: list[str] = []
    monkeypatch.setattr(
        controle_final, "relire_avant_envoi", lambda j, **kw: controle_final.RapportRelecture(),
    )
    monkeypatch.setattr(tasks, "_rendre_le_verdict_du_gate", _panne)
    monkeypatch.setattr(tasks, "_livrer", lambda j: envois.append("envoi"))
    monkeypatch.setattr(tasks, "_effacer_les_textes_orphelins", lambda: None)

    tasks.controler_puis_livrer_task(str(job.id))

    assert envois == ["envoi"]
    # Et la panne ne se TAIT pas : sans verdict, le dossier ne peut pas
    # afficher le « passed » laissé par la passe QA (règle 1).
    from generation.models import GenerationJob, QAStatus
    from monitoring.models import IncidentSeverity, OperationalIncident

    assert GenerationJob.objects.get(pk=job.pk).qa_status == QAStatus.BLOCKED
    incident = OperationalIncident.objects.get(
        job=job, title__startswith="Verdict du gate impossible",
    )
    assert incident.severity == IncidentSeverity.HIGH


def _densite(chapitre: int) -> Anomalie:
    return Anomalie(
        "densite", Gravite.AVERTISSEMENT,
        f"Chapitre {chapitre} : paragraphe médian de 60 mots (plafond 25).",
        chapitre=chapitre,
    )


def test_le_plafond_de_chapitres_coupe_par_GRAVITE_pas_par_numero(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Neuf chapitres fautifs, huit places : l'incohérence chiffrée passe d'abord.

    Trié par numéro, le chapitre 9 — une incohérence chiffrée — n'était jamais
    réécrit, au profit de huit densités. Relecture du 13/09/2026.
    """
    from generation.gate import GateFailure

    incoherence = GateFailure(
        check="coherence_chiffree",
        detail="Le chapitre annonce 120 000 € quand le brief dit 250 000 €.",
        chapter_number=9,
    )
    _, reecritures = _monter(
        monkeypatch,
        [_controle(*(_densite(n) for n in range(1, 9))), _controle()],
        echecs_du_gate=(incoherence,),
    )

    controle_final.relire_et_corriger(job)

    reecrits = [n for n, _ in reecritures]
    assert reecrits[0] == 9, reecrits
    assert len(reecrits) == controle_final.MAX_CHAPITRES_PAR_PASSE


def test_un_gate_illisible_ne_passe_pas_pour_rien_a_reparer(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """« Impossible de savoir » n'est pas « rien à réparer » (règle 1)."""
    _monter(monkeypatch, [_controle()])
    monkeypatch.setattr(controle_final, "_echecs_du_gate", lambda job: None)

    rapport = controle_final.relire_et_corriger(job)

    assert "gate illisible" in rapport.motif_d_arret
    assert any("gate illisible" in ligne for ligne in rapport.restantes)


def test_hors_chaine_word_la_boucle_du_gate_reste_le_seul_correcteur(
    job: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sans contrôleur final, supprimer la boucle laissait partir le dossier
    sans qu'aucun motif ait été retenté (relecture du 13/09/2026)."""
    from documents import livrable_word
    from generation import correction, tasks
    from generation import runner as moteur
    from generation.models import JobStatus

    appels: list[str] = []
    job.status = JobStatus.DONE
    job.save(update_fields=["status"])
    monkeypatch.setattr(moteur, "run_generation_job", lambda j: j)
    monkeypatch.setattr(tasks, "run_generation_job", lambda j: j)
    monkeypatch.setattr(tasks, "_controler_les_demandes_du_client", lambda j: None)
    monkeypatch.setattr(tasks, "_effacer_les_textes_orphelins", lambda: None)
    monkeypatch.setattr("generation.qa.run_qa_pass", lambda j: None)
    monkeypatch.setattr(livrable_word, "chaine_word_active", lambda j: False)
    monkeypatch.setattr(
        correction, "run_correction_loop", lambda j, **kw: appels.append("boucle"),
    )
    monkeypatch.setattr(tasks.controler_puis_livrer_task, "delay", lambda *a, **k: None)

    tasks.run_generation_job_task(str(job.id))

    assert appels == ["boucle"]


def test_le_vert_du_gate_n_efface_pas_l_echec_de_la_passe_qa(job: Any) -> None:
    """Le gate ne juge pas ce que la passe QA a jugé : son vert ne vaut pas pour elle."""
    from unittest.mock import patch

    from generation import tasks
    from generation.models import GenerationJob, QAStatus

    GenerationJob.objects.filter(pk=job.pk).update(qa_status=QAStatus.FAILED)
    rapport_vert = type("R", (), {"passed": True, "failures": ()})()
    with patch("generation.gate.run_delivery_gate", return_value=rapport_vert):
        tasks._rendre_le_verdict_du_gate(job)

    assert GenerationJob.objects.get(pk=job.pk).qa_status == QAStatus.FAILED

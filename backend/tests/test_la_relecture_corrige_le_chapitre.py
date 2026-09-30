"""La relecture du texte corrige le chapitre avant rendu, et relit le PDF après.

30/09/2026 (business plan ÉCLORE `28a257bf`) : les contrôles de relecture
(`generation.relecture`) sont branchés sur la rédaction de CHAQUE dossier —
mémoire active ou non — et sur le PDF final :
- un constat grave fait reprendre le chapitre avec sa consigne précise ;
- au dernier essai, le chapitre est gardé et le constat tracé : l'étude ne
  s'arrête jamais ;
- sur le PDF rendu, ce qui reste est consigné et signalé, jamais bloquant.
Textes fictifs.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from django.test import override_settings

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres.services import produire_avec_reprises
from generation.chapitres.stub import chapitre_de_demonstration
from generation.models import ChapterGeneration, GenerationJob
from generation.services import bootstrap_generation_job
from generation.socle import etablir_socle
from intake.models import IntakeStatus, IntakeSubmission
from integrations.claude import StructuredResult, StubClaudeClient
from monitoring.models import OperationalIncident
from orders.models import Order

pytestmark = pytest.mark.django_db

BP = DeliverableType.BUSINESS_PLAN
VARIABLES = {
    "SECTEUR": "Ateliers. Il s'agit d'une prestation de services commerciale.",
    "PAYS": "France", "ZONE": "Île-de-France", "PROJET": "Projet test",
}
FAUX = "Le calcul est simple : 1 200 € ÷ 12 = 150 €."
JUSTE = "Le calcul est simple : 1 200 € ÷ 12 = 100 €."


def _dossier(suffixe: str) -> GenerationJob:
    offre, _ = Offer.objects.get_or_create(
        slug="bp-relecture", defaults={"name": "BP", "deliverable_type": BP},
    )
    client = Customer.objects.create(email=f"relecture-{suffixe}@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id=f"cmd-relecture-{suffixe}", customer=client, offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED, normalized_variables=VARIABLES,
    )
    with override_settings(EVKHA_MEMOIRE_ETUDE=False):
        job = bootstrap_generation_job(soumission)
    etablir_socle(job, client=StubClaudeClient(), variables=VARIABLES)
    return job


class ClientQuiCalculeFaux:
    """Écrit d'abord une opération fausse, puis (s'il se corrige) une opération juste."""

    def __init__(self, *, se_corrige: bool) -> None:
        self.appels = 0
        self.se_corrige = se_corrige
        self.prompts: list[str] = []

    def complete_structured(self, **kwargs: Any) -> StructuredResult:
        self.appels += 1
        contexte = f"{kwargs.get('system', '')}\n\n{kwargs['prompt']}"
        self.prompts.append(contexte)
        charge = chapitre_de_demonstration(contexte)
        texte = JUSTE if self.se_corrige and self.appels > 1 else FAUX
        charge["blocs"] = [*charge["blocs"], {"type": "paragraphe", "texte": texte}]  # type: ignore[misc]
        return StructuredResult(payload=charge, input_tokens=10, output_tokens=10, model="stub")


def test_un_calcul_faux_fait_reprendre_le_chapitre_avec_sa_consigne() -> None:
    """Sans la mémoire : la relecture vaut pour tous les dossiers."""
    job = _dossier("a")
    client = ClientQuiCalculeFaux(se_corrige=True)
    produire_avec_reprises(job, 16, client=client)
    assert client.appels == 2
    assert "[formule]" in client.prompts[1], "la reprise reçoit le constat précis"
    job.refresh_from_db()
    assert job.memoire_etude["relecture"]["16"]["graves"], "le constat est tracé"


def test_au_dernier_essai_le_chapitre_est_garde_et_le_constat_trace() -> None:
    job = _dossier("b")
    client = ClientQuiCalculeFaux(se_corrige=False)
    chapitre = produire_avec_reprises(job, 16, client=client)
    assert chapitre.status == "done"
    job.refresh_from_db()
    assert job.memoire_etude["relecture"]["16"]["garde_au_dernier_essai"] is True


def _pdf(lignes: list[str]) -> bytes:
    reportlab = pytest.importorskip("reportlab")
    del reportlab
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    tampon = io.BytesIO()
    page = canvas.Canvas(tampon, pagesize=A4)
    y = 800
    for ligne in lignes:
        page.drawString(60, y, ligne)
        y -= 18
    page.showPage()
    page.save()
    return tampon.getvalue()


def test_le_pdf_final_est_relu_et_ce_qui_reste_est_consigne(tmp_path: Path) -> None:
    from documents.livrable_word import _relire_le_texte_du_pdf

    job = _dossier("c")
    chemin = tmp_path / "livrable.pdf"
    chemin.write_bytes(_pdf(["1.1 Un calcul", "Le calcul est simple : 1200 / 12 = 150."]))
    _relire_le_texte_du_pdf(job, chemin)
    job.refresh_from_db()
    relecture = job.controle_final["relecture_texte"]
    assert relecture["graves"] >= 1 and relecture["par_classe"].get("formule")
    assert OperationalIncident.objects.filter(
        job=job, title__startswith="Relecture du texte"
    ).exists()


def test_un_pdf_juste_ne_laisse_rien(tmp_path: Path) -> None:
    """Contre-épreuve."""
    from documents.livrable_word import _relire_le_texte_du_pdf

    job = _dossier("d")
    chemin = tmp_path / "livrable.pdf"
    chemin.write_bytes(_pdf(["1.1 Un calcul", "Le calcul est simple : 1200 / 12 = 100."]))
    _relire_le_texte_du_pdf(job, chemin)
    job.refresh_from_db()
    # Le document de deux lignes n'est pas un business plan complet (sa
    # sensibilité manque, par exemple) : on juge ici l'opération seule.
    assert "formule" not in job.controle_final["relecture_texte"]["par_classe"]


def test_sans_memoire_la_consigne_de_reprise_porte_des_valeurs_et_non_des_reperes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Revue du 30/09/2026 : le rédacteur sans mémoire ne connaît aucun `{{repère}}`.

    Recopié, le repère s'imprime tel quel ; cité, il est puni comme inconnu. La
    consigne lui donne donc la VALEUR du fait.
    """
    from generation import relecture
    from generation.chapitres.runner import _relire_le_chapitre
    from generation.memoire.reperes import valeur_affichee
    from generation.memoire.services import memoire_de_relecture
    from generation.relecture import Constat

    job = _dossier("e")
    memoire = memoire_de_relecture(job)
    assert memoire is not None and memoire.faits
    identifiant, fait = next(iter(memoire.faits.items()))
    constat = Constat(
        "coherence", "16.1", "un chiffre", f"Le chiffre juste est {{{{{identifiant}}}}}.",
    )
    monkeypatch.setattr(relecture, "relire", lambda *_: [constat])
    monkeypatch.setattr(relecture, "document_du_chapitre", lambda _: None)

    motifs = _relire_le_chapitre(
        None, job, ChapterGeneration(chapter_number=16), None, derniere_tentative=False,
    )
    assert motifs and "{{" not in " ".join(motifs)
    assert valeur_affichee(fait) in motifs[0]


def test_avec_memoire_la_consigne_garde_le_repere(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contre-épreuve : le rédacteur qui a la mémoire cite le repère, pas la valeur."""
    from generation import relecture
    from generation.chapitres.runner import _relire_le_chapitre
    from generation.memoire.services import memoire_de_relecture
    from generation.relecture import Constat

    job = _dossier("f")
    memoire = memoire_de_relecture(job)
    assert memoire is not None and memoire.faits
    identifiant = next(iter(memoire.faits))
    constat = Constat("coherence", "16.1", "un chiffre", f"Cite {{{{{identifiant}}}}}.")
    monkeypatch.setattr(relecture, "relire", lambda *_: [constat])
    monkeypatch.setattr(relecture, "document_du_chapitre", lambda _: None)

    motifs = _relire_le_chapitre(
        None, job, ChapterGeneration(chapter_number=16), memoire, derniere_tentative=False,
    )
    assert f"{{{{{identifiant}}}}}" in motifs[0]


def test_la_relecture_du_texte_tourne_meme_si_le_controle_du_rendu_tombe(tmp_path: Path) -> None:
    """Revue du 30/09/2026 : la panne du contrôle de rendu sautait la relecture du texte.

    Ici le Word est illisible (absent) : le contrôle du rendu échoue, la
    relecture du texte consigne quand même.
    """
    from documents.livrable_word import _controler_le_pdf_rendu

    job = _dossier("g")
    chemin = tmp_path / "livrable.pdf"
    chemin.write_bytes(_pdf(["1.1 Un calcul", "Le calcul est simple : 1200 / 12 = 150."]))
    _controler_le_pdf_rendu(job, chemin, tmp_path / "absent.docx")
    job.refresh_from_db()
    assert "rendu_pdf" not in job.controle_final
    assert job.controle_final["relecture_texte"]["par_classe"].get("formule")

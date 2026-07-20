"""Phase 20 — Le rendu doit dire ce que le gate a valide.

Defaut reel, trouve par le client dans un document que je venais de lui
remettre en annoncant « aucune anomalie » (BP SYNAPSES, chapitre 18.8) :

    <table><thead><tr><th>Rubrique</th><th>Montant (€)</th></tr></thead>
    <tbody><></><></><></><></><></><></></tbody></table>

Toutes les lignes de donnees remplacees par des balises vides. Le markdown,
lui, contenait le tableau COMPLET : le gate passait, le document partait
ampute.

Cause : `chunk_long_tables` appelait `tbody.decompose()`, qui detruit
l'element ET SES ENFANTS, alors que la liste des lignes a recopier pointait
dessus. Ne frappait que les tableaux de plus de 12 lignes — donc les tableaux
financiers, les plus regardes dans un dossier bancaire. C'est la cause des
« tableaux tronques » signales de longue date.

Trois defenses, testees ici :
1. le bug est corrige (`extract()` detache sans detruire) ;
2. un correctif n'est pas une garantie : on CONTROLE la sortie du rendu ;
3. le controle refuse d'assembler un document ampute.

Regle de fond, la meme que pour Gamma : ce qui refait le document apres le
controle doit etre controle a son tour.
"""
from __future__ import annotations

import re

import pytest

from documents.rendu_fidelite import controler_rendu
from generation.models import GenerationJob
from generation.rendering import chunk_long_tables, render_client_document

_TABLEAU_LONG = (
    '<table class="chapter__body wide"><thead><tr><th>Rubrique</th>'
    "<th>Montant</th></tr></thead><tbody>"
    + "".join(f"<tr><td>Ligne {i}</td><td>{i * 1000} EUR</td></tr>" for i in range(1, 20))
    + "</tbody></table>"
)


# ── 1. Le bug d'origine ─────────────────────────────────────────────────────


def test_le_decoupage_ne_detruit_plus_les_lignes() -> None:
    """AVANT : `tbody.decompose()` transformait chaque ligne en `<></>`."""
    rendu = chunk_long_tables(_TABLEAU_LONG, max_rows=8)

    assert "<>" not in rendu
    assert rendu.count("<tr><td>Ligne") == 19  # aucune donnee perdue


def test_le_decoupage_produit_bien_des_sous_tableaux() -> None:
    """Contre-epreuve : la fonction doit toujours faire son travail."""
    rendu = chunk_long_tables(_TABLEAU_LONG, max_rows=8)

    assert rendu.count("<table") == 3  # 19 lignes / 8 -> 3 blocs
    assert rendu.count("page-break-before") == 2
    assert "chapter__body wide" in rendu  # le style du tableau survit
    assert rendu.count("<thead>") == 3  # entete repetee sur chaque page


def test_un_tableau_court_n_est_pas_touche() -> None:
    """Contre-epreuve : pas de decoupage inutile."""
    court = (
        "<table><thead><tr><th>A</th></tr></thead><tbody>"
        "<tr><td>1</td></tr><tr><td>2</td></tr></tbody></table>"
    )

    assert chunk_long_tables(court, max_rows=8) == court


# ── 2. Le controle de sortie ────────────────────────────────────────────────


def test_les_balises_vides_sont_refusees() -> None:
    """Le defaut exact vu par le client dans le document livre."""
    html = (
        "<table><thead><tr><th>Rubrique</th></tr></thead>"
        "<tbody><></><></><></></tbody></table>"
    )

    rapport = controler_rendu(html=html, markdown="| Rubrique |\n|---|\n| CA |")

    assert rapport.fidele is False
    assert "balise" in rapport.motif


def test_un_tableau_sans_donnees_est_refuse() -> None:
    """Une entete seule : le lecteur verrait des colonnes vides."""
    html = "<table><thead><tr><th>Rubrique</th><th>Montant</th></tr></thead></table>"

    rapport = controler_rendu(html=html, markdown="texte")

    assert rapport.fidele is False
    assert "AUCUNE donnee" in rapport.motif


def test_des_lignes_disparues_au_rendu_sont_refusees() -> None:
    """Le markdown a 10 lignes, le rendu 2 : des donnees ont saute."""
    markdown = "| Rubrique | Montant |\n|---|---|\n" + "".join(
        f"| Ligne {i} | {i}000 |\n" for i in range(1, 11)
    )
    html = (
        "<table><tbody><tr><td>Ligne 1</td></tr>"
        "<tr><td>Ligne 2</td></tr></tbody></table>"
    )

    rapport = controler_rendu(html=html, markdown=markdown)

    assert rapport.fidele is False
    assert "disparu" in rapport.motif


def test_un_rendu_fidele_est_accepte() -> None:
    """Contre-epreuve : le controle ne doit pas bloquer un rendu correct.

    Sinon on remplace un defaut par un autre : refuser tout, tout le temps.
    """
    markdown = "| Rubrique | Montant |\n|---|---|\n" + "".join(
        f"| Ligne {i} | {i}000 |\n" for i in range(1, 11)
    )
    html = chunk_long_tables(
        "<table><thead><tr><th>Rubrique</th><th>Montant</th></tr></thead><tbody>"
        + "".join(f"<tr><td>Ligne {i}</td><td>{i}000</td></tr>" for i in range(1, 11))
        + "</tbody></table>",
        max_rows=8,
    )

    rapport = controler_rendu(html=html, markdown=markdown)

    assert rapport.fidele is True, rapport.motif


def test_un_document_sans_tableau_passe() -> None:
    """Contre-epreuve : la plupart des chapitres n'ont aucun tableau."""
    rapport = controler_rendu(
        html="<p>Une analyse sans le moindre tableau.</p>",
        markdown="Une analyse sans le moindre tableau.",
    )

    assert rapport.fidele is True


# ── 2 bis. La prose, pas seulement les tableaux ─────────────────────────────
#
# Trouve en relisant `controler_rendu` a la grille du « Loop Doctor » de
# `Forward-Future/loopy` : un controle et sa reparation ne doivent pas juger
# sur la meme evidence. Les trois controles ci-dessus ne parlent que de
# tableaux — et la reparation aussi. Toute omission de TEXTE passait.


def test_un_paragraphe_escamote_est_refuse() -> None:
    """« Il n'y a pas d'omission de texte. » Avant : `fidele=True`."""
    markdown = (
        "## Chapitre\n\nUn paragraphe capital sur le financement.\n\n"
        "Un second paragraphe tout aussi capital.\n"
    )
    html = "<h2>Chapitre</h2><p>Un paragraphe capital sur le financement.</p>"

    rapport = controler_rendu(html=html, markdown=markdown)

    assert rapport.fidele is False
    assert "escamote" in rapport.motif
    assert "second" in rapport.exemples_mots_perdus  # le motif est trouvable


def test_une_prose_complete_est_acceptee() -> None:
    """Contre-epreuve : le HTML brande ajoute couverture et sommaire.

    Il contient donc PLUS de mots que le markdown (ratio mesure sur le dossier
    SYNAPSES : 1,029). Le controle ne doit compter que ce qui MANQUE.
    """
    markdown = "## Chapitre\n\nUn paragraphe capital sur le financement.\n"
    html = (
        "<h1>Business plan</h1><nav>Sommaire</nav>"
        "<h2>Chapitre</h2><p>Un paragraphe capital sur le financement.</p>"
    )

    assert controler_rendu(html=html, markdown=markdown).fidele is True


def test_les_marqueurs_d_encadre_ne_sont_pas_des_pertes() -> None:
    """Contre-epreuve : `[[UNDERSTAND]]` devient un cartouche stylise.

    Le marqueur disparait LEGITIMEMENT du HTML. 57 occurrences sur le dossier
    SYNAPSES : sans cette exception, tout livrable serait bloque.
    """
    markdown = "[[UNDERSTAND]] Ce qu il faut retenir du plan.\n"
    html = '<div class="callout"><p>Ce qu il faut retenir du plan.</p></div>'

    assert controler_rendu(html=html, markdown=markdown).fidele is True


def test_le_balisage_du_markdown_n_est_pas_compte_comme_prose() -> None:
    """Le markdown valide contient des tableaux HTML stylises en ligne.

    Sans depouillement des DEUX cotes, `px`, `td`, `padding` et `cccccc` sont
    comptes comme des mots perdus : 3 444 faux positifs mesures sur SYNAPSES,
    soit un ecart de 10 % entierement imaginaire. Un controle qui compare a une
    donnee mal extraite est PIRE qu'absent.
    """
    markdown = '<table style="border: 1px solid #cccccc"><tr><td>CA</td></tr></table>'
    html = "<table><tbody><tr><td>CA</td></tr></tbody></table>"

    rapport = controler_rendu(html=html, markdown=markdown)

    assert rapport.fidele is True, rapport.motif
    assert rapport.mots_perdus == 0


# ── 3. Le controle bloque l'assemblage ──────────────────────────────────────


def test_le_motif_du_controle_est_lisible() -> None:
    """Un motif que personne ne comprend ne sert a rien.

    Le gate a deja bloque avec « document dit '3' » pour un document disant
    « 3 M€ » : le lecteur cherchait un « 3 » introuvable.
    """
    html = "<table><thead><tr><th>A</th></tr></thead><tbody><></></tbody></table>"

    motif = controler_rendu(html=html, markdown="| A |\n|---|\n| 1 |").motif

    assert "balise" in motif
    assert re.search(r"\d", motif)  # le motif chiffre ce qu'il a trouve


# ── 4. La boucle : detecter -> reparer -> recontroler -> PDF ────────────────
#
# Un incident ne doit pas etre la premiere reponse a un defaut qu'on sait
# corriger. Le decoupage des tableaux est la SEULE etape du rendu qui reecrit
# la structure : c'est donc la seule qui peut en perdre. On la debraye et on
# recontrole avant de renoncer.


def _job_pret(slug: str) -> GenerationJob:
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import ChapterStatus, JobStatus
    from generation.services import bootstrap_generation_job
    from intake.models import IntakeStatus, IntakeSubmission
    from orders.models import Order

    offer = Offer.objects.create(
        name="BP", slug=slug, deliverable_type=DeliverableType.BUSINESS_PLAN
    )
    customer = Customer.objects.create(email=f"{slug}@example.com")
    order = Order.objects.create(systeme_order_id=slug, customer=customer, offer=offer)
    submission = IntakeSubmission.objects.create(
        order=order,
        status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "coworking", "PAYS": "France", "ZONE": "Beziers",
            "PROJET": "SYNAPSES",
        },
    )
    job = bootstrap_generation_job(submission)
    for chapter in job.chapters.all():
        chapter.content = "Analyse du projet."
        chapter.status = ChapterStatus.DONE
        chapter.save(update_fields=["content", "status"])
    job.status = JobStatus.DONE
    job.save(update_fields=["status"])
    return job


@pytest.mark.django_db
def test_le_rendu_casse_est_repare_puis_livre(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le decoupage casse le rendu -> on re-rend sans lui -> le PDF sort.

    C'est la boucle demandee : on corrige, on recontrole, et SEULEMENT ensuite
    on genere. Le document est complet ; il est juste moins bien pagine.
    """
    from documents import services as documents_services
    from documents.services import assemble_document
    from monitoring.models import OperationalIncident

    job = _job_pret("bp-repare")
    # La doublure doit rendre la prose du document, comme le vrai moteur :
    # sinon le controle la declare escamotee — et il a raison.
    prose = render_client_document(job).to_markdown()

    def rendu(
        _job: GenerationJob,
        *,
        branding: object = None,
        chunk_tables: bool = True,
    ) -> str:
        lignes = (
            "<></><></>"  # le decoupage detruit les lignes
            if chunk_tables
            else "<tr><td>CA</td></tr><tr><td>Resultat</td></tr>"
        )
        return (
            f"<html><body><div>{prose}</div><table><thead><tr><th>Rubrique"
            f"</th></tr></thead><tbody>{lignes}</tbody></table></body></html>"
        )

    monkeypatch.setattr(documents_services, "render_branded_html", rendu)

    assembly = assemble_document(job)  # ne leve pas : le rendu a ete repare

    assert assembly is not None
    incident = OperationalIncident.objects.filter(title__startswith="Rendu repare").first()
    assert incident is not None, "la reparation doit etre tracee, pas silencieuse"


@pytest.mark.django_db
def test_un_rendu_irreparable_bloque_avant_le_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contre-epreuve : si la reparation echoue, aucun PDF ne sort."""
    from documents import services as documents_services
    from documents.services import DocumentAssemblyError, assemble_document

    job = _job_pret("bp-irreparable")

    monkeypatch.setattr(
        documents_services,
        "render_branded_html",
        lambda _job, **_kw: (
            "<html><body><table><thead><tr><th>R</th></tr></thead>"
            "<tbody><></><></></tbody></table></body></html>"
        ),
    )

    with pytest.raises(DocumentAssemblyError, match="infidele"):
        assemble_document(job)


@pytest.mark.django_db
def test_un_chapitre_manquant_bloque_avant_le_pdf() -> None:
    """« Si elle dit 10 chapitres, 10 chapitres doivent etre faits. »

    `render_client_document` ne retient que les chapitres DONE : un chapitre
    absent disparait du livrable sans que rien ne le signale.
    """
    from documents.services import DocumentAssemblyError, assemble_document
    from generation.models import ChapterStatus

    job = _job_pret("bp-incomplet")
    orphelin = job.chapters.order_by("-chapter_number").first()
    assert orphelin is not None
    orphelin.status = ChapterStatus.FAILED
    orphelin.save(update_fields=["status"])

    with pytest.raises(DocumentAssemblyError, match="absent"):
        assemble_document(job)


@pytest.mark.django_db
def test_un_job_failed_reste_assemblable() -> None:
    """Contre-epreuve : le PDF de relecture admin d'un job FAILED.

    Il sert justement a relire ce qui a ete produit avant l'echec : exiger la
    completude le rendrait impossible a produire.
    """
    from documents.services import assemble_document
    from generation.models import ChapterStatus, JobStatus

    job = _job_pret("bp-failed")
    orphelin = job.chapters.order_by("-chapter_number").first()
    assert orphelin is not None
    orphelin.status = ChapterStatus.FAILED
    orphelin.save(update_fields=["status"])
    job.status = JobStatus.FAILED
    job.save(update_fields=["status"])

    assert assemble_document(job) is not None

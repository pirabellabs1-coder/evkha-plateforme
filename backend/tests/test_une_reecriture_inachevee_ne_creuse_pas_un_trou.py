"""Un chapitre resté « en cours » après la relecture finale, sur un dossier livré.

## Le défaut mesuré

Business plan `578c7024` (28/10/2026), relevé sur la fiche du dossier : statut
`done`, `qa_status: passed`, document livré, et **21 chapitres sur 22** — le
chapitre 12 « Organisation et moyens » bloqué en `running`.

La cause n'est pas la boucle de génération : `fermer_les_chapitres_inacheves`
y tourne déjà, depuis le business plan `2a8872d0` du 12/08/2026. C'est la
relecture FINALE, qui tourne dans sa propre tâche **après** que le dossier est
passé `done` : elle avait remis le chapitre 12 en réécriture — un contrôle
`valeur_nulle` sur une phrase pourtant juste — la réécriture n'a pas abouti, et
rien ne refermait l'état intermédiaire.

C'est la règle 3 mot pour mot : *ce qui refait le document APRÈS le contrôle
doit être contrôlé à son tour.*

## Pourquoi « passer en ÉCHEC » était le mauvais réflexe

`rendu_word.services.payloads_du_job` n'assemble que les chapitres `DONE`.
Marquer en échec un chapitre dont le payload est encore rendable le ferait donc
**disparaître du prochain assemblage** : la réparation creuserait le trou
qu'elle prétend signaler. Ce document-ci n'a gardé son chapitre 12 que parce
que le `.docx` avait été assemblé AVANT la réécriture — et les cinq
sous-sections 12.1 à 12.5 sont bien dans les 59 pages livrées.

La fermeture suit donc ce que le LECTEUR recevrait, le seul critère que ce
dépôt accepte : payload rendable → `DONE` avec son motif conservé ; rien à
rendre → `FAILED`, et le rattrapage le reprend.

Ces tests échouent sur le code d'avant : un chapitre avec payload devenait
`FAILED`, et aucune des deux fermetures d'après-contrôle n'existait.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.models import ChapterGeneration, ChapterStatus, GenerationJob
from orders.models import Order

#: Un payload minimal mais VRAI au sens du rendu : `payloads_du_job` ne teste
#: que sa présence, et c'est cette présence qui décide du sort du chapitre.
PAYLOAD_RENDABLE = {"titre": "Organisation et moyens", "sections": [{"titre": "12.1"}]}


@pytest.fixture
def job() -> GenerationJob:
    offre = Offer.objects.create(
        name="BP", slug="test-reecriture-inachevee",
        deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    client = Customer.objects.create(email="reecriture@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-reecriture", customer=client, offer=offre,
    )
    return GenerationJob.objects.create(
        order=commande, deliverable_type=DeliverableType.BUSINESS_PLAN,
    )


def _chapitre_en_reecriture(job: GenerationJob, **champs: object) -> ChapterGeneration:
    return ChapterGeneration.objects.create(
        job=job,
        chapter_number=12,
        chapter_title="Organisation et moyens",
        prompt_key="bp.12.organisation_moyens",
        status=ChapterStatus.RUNNING,
        error_message="[contrat] - « 0 € » : rien ne dit s'il est nul",
        **champs,
    )


# ---------------------------------------------------------------------------
# La règle de fermeture
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_un_chapitre_encore_rendable_part_dans_sa_version_precedente(
    job: GenerationJob, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Le cas de `578c7024`. Sur le code d'avant, il devenait FAILED.

    Et FAILED l'aurait retiré du prochain assemblage : le lecteur aurait perdu
    « Organisation et moyens » parce qu'on voulait signaler qu'il manquait.
    """
    from generation import runner

    monkeypatch.setattr(runner, "_moteur_structure", lambda _job: True)
    chapitre = _chapitre_en_reecriture(job, payload=PAYLOAD_RENDABLE)

    rendable = runner.fermer_le_chapitre_inacheve(job, chapitre)

    chapitre.refresh_from_db()
    assert rendable is True
    assert chapitre.status == ChapterStatus.DONE, (
        "un chapitre que le rendu sait encore lire doit rester assemblable"
    )
    # La CAUSE survit : sans elle, le motif du contrôle qui a déclenché la
    # réécriture serait effacé par la mention de son échec.
    assert "0 €" in chapitre.error_message
    assert "version précédente" in chapitre.error_message


@pytest.mark.django_db
def test_un_chapitre_sans_rien_a_rendre_reste_un_echec_rattrapable(
    job: GenerationJob, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CONTRE-ÉPREUVE : la permissivité ne doit pas avaler les vrais trous.

    Sans ce test, « rendre sa version précédente » reviendrait à déclarer
    terminé un chapitre qui n'a jamais rien produit — et `trou_a_combler`, qui
    ne reconnaît que les échecs, ne le reprendrait plus jamais.
    """
    from generation import runner

    monkeypatch.setattr(runner, "_moteur_structure", lambda _job: True)
    chapitre = _chapitre_en_reecriture(job)  # ni payload, ni content

    rendable = runner.fermer_le_chapitre_inacheve(job, chapitre)

    chapitre.refresh_from_db()
    assert rendable is False
    assert chapitre.status == ChapterStatus.FAILED
    assert "0 €" in chapitre.error_message


@pytest.mark.django_db
def test_le_critere_suit_le_moteur_actif_pas_l_autre_representation(
    job: GenerationJob, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Juger sur `content` quand le document est rendu depuis `payload`, c'est
    juger sur une évidence que le lecteur ne reçoit pas (règle 9).

    Ce chapitre a du markdown et AUCUN payload. Moteur structuré actif, le
    `.docx` n'en contiendrait rien : c'est donc un trou, malgré son texte.
    """
    from generation import runner

    monkeypatch.setattr(runner, "_moteur_structure", lambda _job: True)
    chapitre = _chapitre_en_reecriture(job, content="Un markdown que le Word ignore.")

    assert runner.fermer_le_chapitre_inacheve(job, chapitre) is False

    # Et l'inverse : ancien moteur, c'est `content` qui fait le document.
    chapitre.status = ChapterStatus.RUNNING
    chapitre.save(update_fields=["status"])
    monkeypatch.setattr(runner, "_moteur_structure", lambda _job: False)

    assert runner.fermer_le_chapitre_inacheve(job, chapitre) is True


@pytest.mark.django_db
def test_la_fermeture_groupee_ne_compte_que_les_vrais_trous(
    job: GenerationJob, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ce que la fonction RETOURNE sert à annoncer les trous : pas de faux trou."""
    from generation import runner

    monkeypatch.setattr(runner, "_moteur_structure", lambda _job: True)
    _chapitre_en_reecriture(job, payload=PAYLOAD_RENDABLE)
    ChapterGeneration.objects.create(
        job=job, chapter_number=13, chapter_title="Structure juridique",
        prompt_key="bp.13.structure_juridique", status=ChapterStatus.PENDING,
    )

    trous = runner.fermer_les_chapitres_inacheves(job)

    assert trous == [13], (
        "le chapitre 12 part dans sa version précédente : l'annoncer comme un "
        "trou enverrait le rattrapage repayer un chapitre que le client a déjà"
    )


# ---------------------------------------------------------------------------
# Les deux appels : une fonction peut exister sans être appelée
# ---------------------------------------------------------------------------


def _source(*chemin: str) -> str:
    return (Path(__file__).resolve().parents[1].joinpath(*chemin)).read_text(
        encoding="utf-8"
    )


def test_la_tache_de_relecture_referme_avant_de_livrer() -> None:
    """Le défaut n'était pas la règle, c'était son absence APRÈS le contrôle.

    `fermer_les_chapitres_inacheves` existait et tournait — mais seulement dans
    la tâche de génération. La relecture finale tourne dans SA tâche, après, et
    ne refermait rien. Et la fermeture doit précéder l'envoi : refermer après
    coup laisserait partir le document sans le chapitre.
    """
    source = _source("generation", "tasks.py")
    debut = source.index("def controler_puis_livrer_task")
    tache = source[debut:]

    fermeture = tache.index("fermer_les_chapitres_inacheves(job)")
    livraison = tache.index("_livrer(job)")
    assert fermeture < livraison


def test_aucun_appelant_ne_peut_laisser_un_chapitre_en_cours() -> None:
    """La garantie est dans la fonction, pas chez ses appelants (regles 4 et 5).

    Mesure qui l'a imposee : le chapitre 12 de `578c7024` est reste « en
    cours », j'ai repare l'appelant OBSERVE — la relecture finale — et le
    chapitre 1 de `7f737b7b`, meme brief relance, est reste « en cours » par
    un AUTRE appelant, la reparation des CHECK inter-blocs. Quatre appelants
    reecrivent un chapitre ; en nommer un etait la version incomplete du
    correctif.

    Ce test echoue sur le code d'avant : `regenerate_chapter` n'avait pas de
    `finally`, et le nombre d'appelants n'etait verifie nulle part.
    """
    source = _source("generation", "runner.py")
    corps = source[source.index("def regenerate_chapter"):]
    corps = corps[: corps.index("def _inline_qa_repair")]

    assert "finally:" in corps, (
        "sans `finally`, une reecriture qui leve laisse le chapitre « en "
        "cours », et payloads_du_job le retire du document sans erreur"
    )
    assert "fermer_le_chapitre_inacheve(job, chapter)" in corps


def test_les_quatre_appelants_passent_bien_par_la() -> None:
    """CONTRE-EPREUVE du compte : si un cinquieme chemin apparait, il est vu.

    Le `finally` ne protege que ce qui passe par `regenerate_chapter`. Le jour
    ou quelqu'un appelle `regenerer_chapitre` directement, la garantie saute
    en silence — et c'est exactement le defaut qu'on vient de corriger deux
    fois.
    """
    import subprocess  # noqa: PLC0415

    sortie = subprocess.run(
        ["git", "grep", "-n", "regenerer_chapitre(", "--", "backend"],
        capture_output=True, text=True, check=False,
        cwd=Path(__file__).resolve().parents[2],
    ).stdout

    hors_du_passage = [
        ligne for ligne in sortie.splitlines()
        if ligne and "backend/tests/" not in ligne
        and "chapitres/services.py" not in ligne
        and "generation/runner.py" not in ligne
    ]
    assert not hors_du_passage, (
        "un chemin de reecriture contourne `regenerate_chapter` et sa "
        "garantie : " + " | ".join(hors_du_passage)
    )

"""La passe de conformité refuse, fait recommencer, et sait s'arrêter.

Elle était écrite et branchée sur rien : `verifier_chapitre` mesurait très bien
l'écart au modèle, mais aucun chapitre n'était jamais refusé pour ce motif. Un
contrôle qu'on n'exécute pas ne garantit rien (règle 8 : le même défaut que
Gamma, intégré, testé, jamais lancé).

Le point délicat n'est pas de refuser — c'est de ne pas TROP refuser. Vingt-et-un
chapitres × trois tentatives, à environ deux euros la génération, pour finir en
`intervention_requise` sur un tableau de trop : la passe coûterait plus qu'elle
ne rapporte. D'où trois issues distinctes, et une seule qui dépend du compte des
tentatives.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from generation.modele.conformite import (
    Ecart,
    Gravite,
    RapportConformite,
    arbitrer,
)

CONTROLES = ["modele_present", "sequence_des_blocs", "volume"]


def _rapport(*ecarts: Ecart, controles: list[str] | None = None) -> RapportConformite:
    return RapportConformite(
        chapitre=1,
        ecarts=list(ecarts),
        controles_executes=CONTROLES if controles is None else controles,
    )


def _forme() -> Ecart:
    return Ecart("dosage_tableaux", Gravite.BLOQUANTE, "3 tableaux au lieu de 5")


def _redhibitoire() -> Ecart:
    return Ecart(
        "variable_non_resolue", Gravite.BLOQUANTE, "paragraphe 2 : {{client.nom}}"
    )


# ── Ce qui doit refuser ──────────────────────────────────────────────────────


def test_un_ecart_de_forme_fait_recommencer_tant_qu_il_reste_une_tentative() -> None:
    arbitrage = arbitrer(_rapport(_forme()), derniere_tentative=False)
    assert arbitrage.bloque
    assert "3 tableaux au lieu de 5" in arbitrage.refus[0]
    assert not arbitrage.acceptes


def test_un_ecart_redhibitoire_refuse_meme_a_la_derniere_tentative() -> None:
    """Un `{{client.nom}}` imprimé tel quel se voit à la première lecture.

    C'est la frontière de toute la passe : la forme se négocie, la justesse
    non. Sans cette distinction, « ne pas trop bloquer » finirait par livrer un
    document faux.
    """
    arbitrage = arbitrer(_rapport(_redhibitoire()), derniere_tentative=True)
    assert arbitrage.bloque
    assert not arbitrage.acceptes


def test_un_ecart_redhibitoire_emporte_les_ecarts_de_forme() -> None:
    """Le chapitre repart : autant lui redonner la liste complète."""
    arbitrage = arbitrer(
        _rapport(_redhibitoire(), _forme()), derniere_tentative=True
    )
    assert len(arbitrage.refus) == 2


def test_un_rapport_sans_controle_execute_refuse() -> None:
    """Règle 1 : ne rien avoir vérifié n'est pas avoir vérifié sans rien trouver."""
    arbitrage = arbitrer(_rapport(controles=[]), derniere_tentative=True)
    assert arbitrage.bloque


# ── Ce qui doit passer, en le disant ─────────────────────────────────────────


def test_un_ecart_de_forme_est_accepte_a_la_derniere_tentative() -> None:
    """Un chapitre un peu hors dosage reste lisible ; une étude bloquée n'est rien."""
    arbitrage = arbitrer(_rapport(_forme()), derniere_tentative=True)
    assert not arbitrage.bloque
    assert arbitrage.acceptes == ["dosage_tableaux : 3 tableaux au lieu de 5"]


def test_un_chapitre_conforme_ne_laisse_aucune_mention() -> None:
    """Contre-épreuve : la passe ne doit pas produire du bruit sur le cas normal."""
    arbitrage = arbitrer(_rapport(), derniere_tentative=False)
    assert not arbitrage.bloque
    assert not arbitrage.acceptes
    assert not arbitrage.non_controle


def test_un_chapitre_hors_modele_n_est_pas_juge_et_le_dit() -> None:
    """La fiche projet, numérotée 00, n'existe pas au modèle.

    Le rapport la déclare bloquante — il ne peut rien comparer, et c'est la
    bonne réponse de sa part. Mais bloquer l'étude sur un écart connu et
    documenté serait absurde : on le consigne et on avance.
    """
    hors = Ecart("modele_absent", Gravite.BLOQUANTE, "aucun chapitre 00 au modèle")
    arbitrage = arbitrer(_rapport(hors), derniere_tentative=False)
    assert not arbitrage.bloque
    assert arbitrage.non_controle == "aucun chapitre 00 au modèle"


def test_un_avertissement_ne_refuse_jamais() -> None:
    doux = Ecart("volume", Gravite.AVERTISSEMENT, "12 % sous la cible")
    arbitrage = arbitrer(_rapport(doux), derniere_tentative=False)
    assert not arbitrage.bloque
    assert not arbitrage.acceptes


# ── La trace laissée sur le chapitre ─────────────────────────────────────────


def test_l_ecart_accepte_est_ecrit_sur_le_chapitre() -> None:
    """Sans trace, « accepté » devient « passé inaperçu » (règle 1)."""
    from generation.chapitres.services import PREFIXE_ECARTS, _mention_arbitrage

    mention = _mention_arbitrage(arbitrer(_rapport(_forme()), derniere_tentative=True))
    assert mention.startswith(PREFIXE_ECARTS)
    assert "dosage_tableaux" in mention


def test_la_mention_ne_se_confond_pas_avec_un_refus() -> None:
    """`[contrat] ` est relu par la tentative suivante pour se corriger.

    Si l'écart accepté portait le même préfixe, il serait réinjecté dans le
    prompt d'une génération qui n'aura pas lieu — et surtout, un chapitre
    terminé serait relu comme un chapitre refusé.
    """
    from generation.chapitres.runner import _PREFIXE_MOTIFS, _motifs_stockes
    from generation.chapitres.services import _mention_arbitrage

    class FauxChapitre:
        error_message = _mention_arbitrage(
            arbitrer(_rapport(_forme()), derniere_tentative=True)
        )

    assert not FauxChapitre.error_message.startswith(_PREFIXE_MOTIFS)
    assert _motifs_stockes(FauxChapitre) is None  # type: ignore[arg-type]


def test_un_chapitre_conforme_n_ecrit_rien() -> None:
    from generation.chapitres.services import _mention_arbitrage

    assert _mention_arbitrage(arbitrer(_rapport(), derniere_tentative=True)) == ""
    assert _mention_arbitrage(None) == ""


# ── Le branchement réel ──────────────────────────────────────────────────────


def test_la_passe_est_bien_appelee_par_la_production_du_chapitre(
    monkeypatch: Any,
) -> None:
    """Le test qui manquait : la passe existait et n'était appelée nulle part.

    On ne vérifie pas ici QUE le verdict est bon — les tests ci-dessus s'en
    chargent — mais que `generer_chapitre` interroge bien la conformité. Sans
    lui, tous les autres peuvent rester verts sur un moteur qui ne contrôle
    rien (règle 8).
    """
    import inspect

    from generation.chapitres import runner

    source = inspect.getsource(runner.generer_chapitre)
    assert "_arbitrer_conformite" in source
    assert "arbitrage.refus" in source

    arbitre = inspect.getsource(runner._arbitrer_conformite)
    assert "verifier_chapitre" in arbitre
    assert "tentatives_max" in arbitre


# ── De bout en bout, sur la base ─────────────────────────────────────────────
#
# Les tests ci-dessus jugent l'arbitrage sur des rapports fabriqués. Celui-ci
# fait produire un vrai chapitre par la doublure, en lui faisant porter un
# défaut, et vérifie que la chaîne le refuse — puis qu'elle laisse passer le
# chapitre normal. Un test qui n'inspecte que du source resterait vert sur un
# branchement inversé.


@pytest.mark.django_db
def test_un_chapitre_faux_est_refuse_de_bout_en_bout(
    job_conformite: Any, monkeypatch: Any
) -> None:
    """Une variable de gabarit non résolue ne doit jamais atteindre le document."""
    from generation.chapitres import stub
    from generation.chapitres.runner import ChapitreInvalideError
    from generation.chapitres.services import produire_chapitre
    from generation.models import ChapterGeneration, ChapterStatus
    from integrations.claude import StubClaudeClient

    vrai = stub.chapitre_de_demonstration

    def truque(prompt: str) -> dict[str, object]:
        charge = vrai(prompt)
        blocs = charge["blocs"]
        assert isinstance(blocs, list)
        charge["blocs"] = [
            {"type": "paragraphe",
             "texte": "Étude réalisée pour {{client.nom}}, acteur du secteur."},
            *blocs,
        ]
        return charge

    monkeypatch.setattr(stub, "chapitre_de_demonstration", truque)

    with pytest.raises(ChapitreInvalideError) as leve:
        produire_chapitre(job_conformite, 1, client=StubClaudeClient())

    assert any("variable_non_resolue" in m for m in leve.value.motifs), leve.value.motifs
    chapitre = ChapterGeneration.objects.get(job=job_conformite, chapter_number=1)
    assert chapitre.status == ChapterStatus.FAILED
    assert not chapitre.payload, "un chapitre refusé ne doit rien laisser derrière lui"


@pytest.mark.django_db
def test_un_chapitre_conforme_passe_sans_mention(job_conformite: Any) -> None:
    """Contre-épreuve : la passe ne doit pas bloquer le cas normal."""
    from generation.chapitres.services import produire_chapitre
    from generation.models import ChapterStatus
    from integrations.claude import StubClaudeClient

    chapitre = produire_chapitre(job_conformite, 1, client=StubClaudeClient())
    assert chapitre.status == ChapterStatus.DONE
    assert chapitre.error_message == "", chapitre.error_message


@pytest.fixture
def job_conformite(db: object) -> Any:
    """Étude de marché prête à produire un chapitre : socle verrouillé, rien d'écrit.

    Le socle porte deux grandeurs de MÊME unité — la doublure ne peut demander
    un graphique qu'à cette condition, et un chapitre sans son graphique
    minimum serait refusé pour un défaut du décor, pas du moteur.
    """
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import SocleDonnees, SocleStatut
    from generation.services import bootstrap_generation_job
    from generation.socle.schema import Socle
    from intake.models import IntakeStatus, IntakeSubmission
    from orders.models import Order

    offre = Offer.objects.create(
        name="Étude de marché", slug="em-conformite",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="conformite@example.com")
    commande = Order.objects.create(
        systeme_order_id="order-conformite-01", customer=client, offer=offre
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED,
        normalized_variables={"SECTEUR": "automobile", "PAYS": "France"},
    )
    job = bootstrap_generation_job(soumission)

    socle = Socle.model_validate({
        "secteur": "automobile", "date_socle": "2026-07-30",
        "zone": {"pays": "France", "region": "Île-de-France", "ville": "Paris"},
        "donnees": [
            {"id": "marche_mondial_taille", "libelle": "Marché mondial",
             "valeur": 381.5, "unite": "MdEUR", "annee": 2025, "perimetre": "monde",
             "source": "Essai", "fiabilite": "observee", "derivee_de": []},
            {"id": "marche_france_taille", "libelle": "Marché France",
             "valeur": 6.1, "unite": "MdEUR", "annee": 2025, "perimetre": "national",
             "source": "Essai", "fiabilite": "observee", "derivee_de": []},
        ],
        "segments_clientele": [], "concurrents": [], "tendances": [], "risques": [],
    })
    SocleDonnees.objects.create(
        job=job, statut=SocleStatut.VALIDE, contenu=socle.model_dump(mode="json")
    )
    return job


# ── Le chemin qui tourne réellement ──────────────────────────────────────────
#
# Tout ce qui précède vérifie `arbitrer` en isolation. Le premier vrai dossier a
# montré que cela ne prouvait rien sur ce qui est exécuté : l'étude est morte au
# chapitre 1, sur un écart de VOLUME de 20 %, après 0,0574 €.
#
# Cause : `derniere_tentative` était déduit de `chapter.retry_count`, un
# compteur que **seule** la tâche Celery par chapitre incrémente. Le runner
# synchrone — celui que la production emprunte — appelle `produire_chapitre` UNE
# fois et propage l'exception. `retry_count` y reste donc à zéro, l'étage
# « accepter puis consigner » n'était jamais atteint, et chaque écart de forme
# était fatal au premier essai.
#
# La doublure produisait des chapitres conformes : la branche de refus n'a
# jamais tourné avant la première génération réelle (règles 7 et 9).


def _rapport_hors_dosage(regle: str) -> Any:
    """Rapport de conformité portant UN écart bloquant, et rien d'autre."""
    return _rapport(
        Ecart(regle, Gravite.BLOQUANTE, "volume : 2948 signes contre 2457"),
        controles=["volume"],
    )


@pytest.mark.django_db
def test_sans_reprise_un_ecart_de_forme_n_arrete_pas_l_etude(
    job_conformite: Any, monkeypatch: Any
) -> None:
    """Le test qui échoue sur le code d'avant.

    Quand l'appelant annonce qu'il ne réessaiera pas, un écart de dosage doit
    être accepté et consigné : un chapitre légèrement hors volume reste un
    chapitre lisible, une étude bloquée n'est rien.
    """
    from generation.chapitres.runner import _arbitrer_conformite

    monkeypatch.setattr(
        "generation.modele.conformite.verifier_chapitre",
        lambda *a, **k: _rapport_hors_dosage("volume"),
    )
    chapitre = job_conformite.chapters.get(chapter_number=1)
    document = SimpleNamespace(tentatives_max=3)

    arbitrage = _arbitrer_conformite(
        chapitre, object(), document, derniere_tentative=True
    )

    assert not arbitrage.bloque, (
        f"une etude est perdue sur un ecart de forme : {arbitrage.refus}"
    )
    assert arbitrage.acceptes, "l'ecart doit etre CONSIGNE, pas efface"


@pytest.mark.django_db
def test_avec_reprise_un_ecart_de_forme_fait_toujours_recommencer(
    job_conformite: Any, monkeypatch: Any
) -> None:
    """Contre-épreuve : on n'a pas transformé l'arbitrage en laissez-passer."""
    from generation.chapitres.runner import _arbitrer_conformite

    monkeypatch.setattr(
        "generation.modele.conformite.verifier_chapitre",
        lambda *a, **k: _rapport_hors_dosage("volume"),
    )
    chapitre = job_conformite.chapters.get(chapter_number=1)

    arbitrage = _arbitrer_conformite(
        chapitre, object(), SimpleNamespace(tentatives_max=3),
        derniere_tentative=False,
    )

    assert arbitrage.bloque


@pytest.mark.django_db
def test_un_ecart_redhibitoire_refuse_meme_sans_reprise(
    job_conformite: Any, monkeypatch: Any
) -> None:
    """La contre-épreuve qui compte : on n'a pas ouvert les vannes.

    Une variable non résolue reste une variable non résolue — le lecteur y
    verrait `{{ SECTEUR }}` en toutes lettres.
    """
    from generation.chapitres.runner import _arbitrer_conformite

    monkeypatch.setattr(
        "generation.modele.conformite.verifier_chapitre",
        lambda *a, **k: _rapport_hors_dosage("variable_non_resolue"),
    )
    chapitre = job_conformite.chapters.get(chapter_number=1)

    arbitrage = _arbitrer_conformite(
        chapitre, object(), SimpleNamespace(tentatives_max=3),
        derniere_tentative=True,
    )

    assert arbitrage.bloque


def test_le_runner_synchrone_annonce_qu_il_ne_reessaiera_pas() -> None:
    """La propriété structurelle, pas seulement le comportement de la fonction.

    Vérifier `_arbitrer_conformite` isolément est exactement ce qui a laissé
    passer le défaut : l'arbitrage était juste, et l'appelant ne lui disait pas
    la vérité (règle 7).
    """
    import inspect

    from generation import runner

    source = inspect.getsource(runner)
    debut = source.index("produire_chapitre(")
    appel = source[debut : source.index(")", debut + 400)]

    assert "derniere_tentative=True" in appel, (
        "le runner synchrone ne reessaie pas, mais ne le dit pas a l'arbitrage : "
        "tout ecart de forme redevient fatal au premier essai"
    )

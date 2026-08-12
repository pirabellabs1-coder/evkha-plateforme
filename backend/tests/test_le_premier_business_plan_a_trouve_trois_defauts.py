"""Le premier business plan réel, et les trois défauts qu'il a trouvés.

`2a8872d0`, 12/08/2026, compte cliente. Vingt chapitres sur vingt-deux,
3,27 € dépensés, aucun document produit — le gate a refusé de livrer un
business plan amputé, et il a eu raison. Les manquants sont les chapitres 6
(Analyse de marché) et 7 (Analyse concurrentielle).

Trois défauts distincts, un par section ci-dessous. Aucun n'était visible sur
la doublure : c'est la règle 7 du dépôt, mesurée une fois de plus — le vert
des tests ne prouve rien sur le document livré, et le premier vrai dossier
trouve ce que trois relectures n'avaient pas vu.
"""
from __future__ import annotations

import pytest

# ══════════════════════════════════════════════════════════════════════════
# 1. Un chapitre meurt d'un préfixe
# ══════════════════════════════════════════════════════════════════════════
#
# Chapitre 7, trois tentatives, zéro centime de contenu utile, trois motifs :
#
#     `critere_accessibilite_evkha` ne figure pas dans le socle verrouillé.
#
# Le modèle n'avait rien inventé. Il avait DÉCORÉ : un préfixe qui dit la
# nature, un suffixe qui dit la maison — au passage le nom de la marque dans
# un livrable en marque blanche.

CONNUS = frozenset({
    "accessibilite", "rapidite", "structuration", "prix", "prix_median",
    "taille_marche",
})


@pytest.mark.parametrize(
    ("declare", "attendu"),
    [
        # Les trois codes EXACTS qui ont tué le chapitre 7.
        ("critere_accessibilite_evkha", "accessibilite"),
        ("critere_rapidite_evkha", "rapidite"),
        ("critere_structuration_evkha", "structuration"),
        # La même classe, sous d'autres décorations.
        ("donnee_taille_marche", "taille_marche"),
        ("critere_accessibilité", "accessibilite"),
        ("CRITERE-PRIX-MEDIAN", "prix_median"),
        # Et l'identifiant nu, qui doit continuer de passer.
        ("accessibilite", "accessibilite"),
    ],
)
def test_un_identifiant_decore_est_ramene_au_socle(
    declare: str, attendu: str
) -> None:
    from generation.chapitres.schema import resoudre_identifiant

    assert resoudre_identifiant(declare, CONNUS) == attendu


def test_le_plus_long_gagne() -> None:
    """`prix_median` prime sur `prix` : deux jetons valent mieux qu'un.

    Sans cette préférence, `critere_prix_median` deviendrait ambigu et le
    chapitre serait refusé pour une raison qui n'en est pas une.
    """
    from generation.chapitres.schema import resoudre_identifiant

    assert resoudre_identifiant("critere_prix_median", CONNUS) == "prix_median"


def test_un_identifiant_invente_reste_refuse() -> None:
    """CONTRE-ÉPREUVE, et c'est la plus importante.

    La règle absolue du moteur — « un chapitre n'a jamais le droit de produire
    un chiffre » — tient à ce refus. Une résolution trop généreuse la
    dissoudrait en silence, ce qui serait bien pire que le défaut réparé.
    """
    from generation.chapitres.schema import resoudre_identifiant

    assert resoudre_identifiant("part_de_marche_estimee_maison", CONNUS) is None
    assert resoudre_identifiant("", CONNUS) is None


def test_deux_candidats_de_meme_longueur_ne_se_devinent_pas() -> None:
    """On ne tranche pas à pile ou face : mieux vaut redemander que deviner."""
    from generation.chapitres.schema import resoudre_identifiant

    ambigu = frozenset({"cout", "prix"})

    assert resoudre_identifiant("critere_prix_ou_cout", ambigu) is None


# ══════════════════════════════════════════════════════════════════════════
# 2. Un contrôle qui compare un montant à de la prose
# ══════════════════════════════════════════════════════════════════════════
#
# Chapitre 6. Motif rendu par le gate :
#
#     ca_previsionnel : le document dit "chiffre d'affaires prévisionnel de
#     348 890 euros" (soit 348,890), le brief client dit "pour année ( des
#     sept 26 à janvier 27 , je vise 8 abonnés// puis pour s1 2027 20
#     abonnés […] calcul à faire stp"
#
# La cliente a répondu en texte libre là où le système attend un montant. Le
# lecteur de nombres y a trouvé [26, 27, 8, 202720, 202735, 50] — dont un
# 202720 fabriqué en collant « 2027 » et « 20 » — et a comparé 348 890 € à
# cette plage. C'est la règle 2, mot pour mot : un contrôle qui compare à une
# donnée MAL EXTRAITE est PIRE qu'absent.

REPONSE_EN_TEXTE_LIBRE = (
    "pour année ( des sept 26 à janvier 27 , je vise 8 abonnés// puis pour "
    "s1 2027 20 abonnés / puis pour S2 2027 35 abonnés . calcul à faire stp"
)


def test_une_reponse_sans_montant_ne_sert_pas_de_reference() -> None:
    from generation.gate import _MONTANT_AVEC_DEVISE

    assert _MONTANT_AVEC_DEVISE.search(REPONSE_EN_TEXTE_LIBRE) is None


def test_une_reponse_chiffree_reste_une_reference() -> None:
    """CONTRE-ÉPREUVE : le contrôle doit continuer de juger ce qui est jugeable.

    Sans elle, on aurait débranché la vérification chiffrée en croyant la
    réparer — et c'est elle qui attrape les vraies incohérences.
    """
    from generation.gate import _MONTANT_AVEC_DEVISE

    for reponse in ("120 000 €", "1,25 M€", "85 000 euros", "60 kEUR"):
        assert _MONTANT_AVEC_DEVISE.search(reponse) is not None, reponse


def test_le_caractere_monetaire_se_deduit_des_motifs() -> None:
    """Pas de seconde liste de clés à tenir à jour (règle 5).

    Ajouter un fait monétaire à `_CLIENT_FACT_PATTERNS` doit suffire : si le
    caractère monétaire était recopié ailleurs, les deux divergeraient — c'est
    l'histoire des trois listes de labels de ce dépôt.
    """
    from generation.gate import _CLIENT_FACT_PATTERNS, _exige_une_devise

    assert _exige_une_devise(_CLIENT_FACT_PATTERNS["ca_previsionnel"])
    assert _exige_une_devise(_CLIENT_FACT_PATTERNS["investissement_total"])
    # Un taux n'est pas un montant : la règle ne doit pas déborder sur lui.
    assert not _exige_une_devise(_CLIENT_FACT_PATTERNS["taux_occupation"])


def test_le_motif_ne_recopie_pas_le_paragraphe_entier() -> None:
    """Un motif d'échec illisible ne se corrige pas (règle 2).

    Celui du 12/08 reproduisait mille signes de réponse client.
    """
    from generation.gate import _extrait

    court = _extrait(REPONSE_EN_TEXTE_LIBRE)

    assert len(court) < 120
    assert court.startswith("« ") and court.endswith(" »")
    assert "\n" not in court


# ══════════════════════════════════════════════════════════════════════════
# 3. Un chapitre laissé « en cours » sur un dossier « terminé »
# ══════════════════════════════════════════════════════════════════════════
#
# Le chapitre 6 est resté en `running`. Personne ne le reprendra jamais : le
# tableau de bord affiche 20/22 pour toujours, et le rattrapage ne reconnaît
# que les chapitres en ÉCHEC. Le seul recours était de repayer le dossier
# entier pour deux chapitres manquants.


@pytest.fixture
def job_avec_un_chapitre_en_cours():  # type: ignore[no-untyped-def]
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import ChapterGeneration, ChapterStatus, GenerationJob
    from orders.models import Order

    offre = Offer.objects.create(
        name="BP", slug="test-inacheve",
        deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    client = Customer.objects.create(email="inacheve@test.local")
    commande = Order.objects.create(
        systeme_order_id="cmd-inacheve", customer=client, offer=offre,
    )
    job = GenerationJob.objects.create(
        order=commande, deliverable_type=DeliverableType.BUSINESS_PLAN,
    )
    ChapterGeneration.objects.create(
        job=job, chapter_number=5, chapter_title="Fini",
        prompt_key="bp.05.positionnement_concept", status=ChapterStatus.DONE,
        content="Un chapitre abouti.",
    )
    ChapterGeneration.objects.create(
        job=job, chapter_number=6, chapter_title="Analyse de marché",
        prompt_key="bp.06.analyse_marche", status=ChapterStatus.RUNNING,
        error_message="[contrat] - Chiffre incohérent avec le prévisionnel client",
    )
    ChapterGeneration.objects.create(
        job=job, chapter_number=7, chapter_title="Analyse concurrentielle",
        prompt_key="bp.07.analyse_concurrentielle",
        status=ChapterStatus.PENDING,
    )
    return job


@pytest.mark.django_db
def test_un_chapitre_en_cours_devient_un_echec_rattrapable(
    job_avec_un_chapitre_en_cours,  # type: ignore[no-untyped-def]
) -> None:
    from generation.models import ChapterStatus
    from generation.runner import fermer_les_chapitres_inacheves

    fermes = fermer_les_chapitres_inacheves(job_avec_un_chapitre_en_cours)

    assert sorted(fermes) == [6, 7]
    statuts = {
        c.chapter_number: c.status
        for c in job_avec_un_chapitre_en_cours.chapters.all()
    }
    assert statuts[5] == ChapterStatus.DONE, "un chapitre abouti n'est pas touché"
    assert statuts[6] == ChapterStatus.FAILED
    assert statuts[7] == ChapterStatus.FAILED


@pytest.mark.django_db
def test_le_motif_d_origine_survit(
    job_avec_un_chapitre_en_cours,  # type: ignore[no-untyped-def]
) -> None:
    """L'écraser effacerait la CAUSE en signalant l'effet.

    Sur `2a8872d0`, le message du chapitre 6 portait le retour du contrôle
    qualité — la seule explication du trou.
    """
    from generation.runner import fermer_les_chapitres_inacheves

    fermer_les_chapitres_inacheves(job_avec_un_chapitre_en_cours)
    six = job_avec_un_chapitre_en_cours.chapters.get(chapter_number=6)

    assert "inachevé" in six.error_message
    assert "Chiffre incohérent" in six.error_message


@pytest.mark.django_db
def test_rejouer_la_fermeture_ne_change_rien(
    job_avec_un_chapitre_en_cours,  # type: ignore[no-untyped-def]
) -> None:
    """CONTRE-ÉPREUVE : idempotente, sinon le motif s'empilerait à chaque passage."""
    from generation.runner import fermer_les_chapitres_inacheves

    fermer_les_chapitres_inacheves(job_avec_un_chapitre_en_cours)
    avant = job_avec_un_chapitre_en_cours.chapters.get(chapter_number=6).error_message

    assert fermer_les_chapitres_inacheves(job_avec_un_chapitre_en_cours) == []
    apres = job_avec_un_chapitre_en_cours.chapters.get(chapter_number=6).error_message
    assert apres == avant


def test_la_fermeture_precede_le_passage_en_termine() -> None:
    """La cause, pas seulement la fonction.

    Elle pourrait exister sans être appelée — défaut mesuré sept fois sur ce
    projet. Et elle doit être appelée AVANT que le dossier ne passe `DONE`,
    sinon le trou existe encore au moment où le gate juge.
    """
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "generation" / "runner.py"
    ).read_text(encoding="utf-8")

    appel = source.index("fermer_les_chapitres_inacheves(job)")
    passage = source.index("job.status = JobStatus.DONE")
    assert appel < passage

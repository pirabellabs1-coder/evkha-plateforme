"""Chaque demande de la cliente est dans le prompt RÉELLEMENT envoyé.

## Pourquoi ce test interroge le prompt construit, jamais les constantes

Deux fois sur ce projet, une règle écrite, testée et commitée n'a JAMAIS
atteint la production : elle vivait dans un bloc que le moteur réel n'envoie
pas (`build_system_prompt`, moteur hérité), ou dans une forme qu'un livrable
ne recevait pas. Les tests unitaires étaient verts ; le document, inchangé.
C'est le script de vérification des prompts qui a trouvé les deux trous — en
construisant le prompt comme la production le construit, puis en y cherchant
chaque demande.

Ce script vivait dans un répertoire de brouillon. Rien ne le rejouait. Le
voici dans la suite : toute règle qui sort du prompt réel casse la CI, le
jour même, gratuitement.

## Lire une absence

Un échec ici ne dit pas « la règle a été supprimée » : il dit « la règle ne
PART plus ». La distinction est tout le sujet — écrit ne veut pas dire
transmis (règle 8, six occurrences mesurées sur ce projet).
"""
from __future__ import annotations

import datetime as dt
import uuid

import pytest

from catalog.models import DeliverableType, Offer
from customers.models import Customer
from generation.chapitres.configuration import type_document
from generation.chapitres.runner import _SYSTEME, construire_prompt_chapitre
from generation.services import bootstrap_generation_job
from generation.socle.prompt import construire_prompt_socle
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import (
    Concurrent,
    Critere,
    DonneeSocle,
    NoteConcurrent,
    Socle,
    Zone,
)
from intake.models import IntakeSource, IntakeStatus, IntakeSubmission
from orders.models import Order

VARIABLES: dict[str, str] = {
    "SECTEUR": "torréfaction artisanale de café",
    "PAYS": "France",
    "ZONE": "Lyon et sa métropole",
    "PROJET": "Atelier de torréfaction avec vente directe",
}

#: Un socle porteur de TOUT ce que les demandes exigent de voir transmis :
#: données chiffrées (unités lisibles), grille de notation, concurrents notés.
SOCLE = Socle(
    secteur="torréfaction artisanale de café",
    zone=Zone(pays="France"),
    date_socle=dt.date(2026, 8, 10),
    donnees=[
        DonneeSocle(
            id="tam", libelle="Marché total", valeur=1.2, unite="MdEUR",
            annee=2025, perimetre=Perimetre.NATIONAL,
            fiabilite=Fiabilite.OBSERVEE, source="Fevad, 2025",
        ),
        DonneeSocle(
            id="panier_moyen", libelle="Panier moyen", valeur=68.0, unite="EUR",
            annee=2025, perimetre=Perimetre.NATIONAL,
            fiabilite=Fiabilite.ESTIMEE,
        ),
    ],
    grille_notation=[
        Critere(code="prix", intitule="Accessibilité tarifaire",
                note_1="prime forte", note_5="prime faible"),
    ],
    concurrents=[
        Concurrent(nom="Acteur A", notes=[NoteConcurrent(critere="prix", note=4)]),
        Concurrent(nom="Acteur B", notes=[NoteConcurrent(critere="prix", note=2)]),
    ],
)

#: (famille, libellé de la demande, fragment cherché, où chercher)
#:   "S" = prompt système ; "P" = prompt d'un chapitre d'étude de marché ;
#:   "D" = prompt du DERNIER chapitre ; "E" = chapitre d'étude concurrentielle ;
#:   "SOCLE" = prompt de la passe 1 (socle) de l'étude concurrentielle.
DEMANDES: list[tuple[str, str, str, str]] = [
    # --- Retour V3 sur l'étude de marché ---
    ("V3", "Formulations prudentes interdites", "INTERDITES", "S"),
    ("V3", "« aucune donnée disponible » banni", "aucune donnée disponible", "S"),
    ("V3", "« reste à vérifier » banni", "reste à vérifier", "S"),
    ("V3", "« à confirmer avec un professionnel » banni", "professionnel", "S"),
    ("V3", "Remplacement : fourchette assumée", "hypothèse prudente comprise", "S"),
    ("V3", "Chaîne donnée → décision", "ordre de grandeur à retenir", "S"),
    ("V3", "Identifiants internes bannis", "`tam`", "S"),
    ("V3", "« à dire d'expert » banni", "dire d'expert", "S"),
    ("V3", "Accessibilité (novice)", "QUELQU'UN QUI DÉCOUVRE", "S"),
    ("V3", "Orthographe", "FRANÇAIS IRRÉPROCHABLE", "S"),
    ("V3", "Balisage interdit", "AUCUN FORMAT DE DONNÉES", "S"),
    ("V3", "Données brutes bannies", "points-virgules", "S"),
    ("V3", "SWOT conclusive", "CROISEMENT des cases", "P"),
    ("V3", "Unités lisibles dans le socle", "1.2 Md€", "P"),
    ("V3", "Quatre questions par chapitre", "QUATRE questions", "P"),
    ("V3", "Échelle de notation 1-5", "5 référence du secteur", "P"),
    ("V3", "Verdict de clôture (dernier chapitre)", "VERDICT DE CLÔTURE", "D"),
    ("V3", "Six axes du verdict", "Viabilité globale", "D"),
    # --- Retour sur l'étude concurrentielle ---
    ("EC", "Grille de notation demandée au socle", "grille_notation", "SOCLE"),
    ("EC", "Barème reproductible (1 et 5 définis)", "note_1", "SOCLE"),
    ("EC", "Chaque concurrent noté", "`notes`", "SOCLE"),
    ("EC", "Indicateurs observables", "OBSERVABLES", "E"),
    ("EC", "Comparaison tarifaire", "COMPARAISON TARIFAIRE", "E"),
    ("EC", "Coût réel par profil client", "profils de", "E"),
    ("EC", "Canaux d'acquisition", "trouve ses clients", "E"),
    ("EC", "Avis clients et réputation", "AVIS CLIENTS", "E"),
    ("EC", "Concurrents les plus dangereux", "plus dangereux", "E"),
    ("EC", "Zones saturées", "saturé", "E"),
    ("EC", "Erreurs à éviter", "erreurs", "E"),
    ("EC", "Priorités avant lancement", "priorités avant le lancement", "E"),
    ("EC", "Fourchette nue interdite (EC)", "jamais de fourchette nue", "E"),
    # --- Figures ---
    ("FIG", "Radar/carte peuvent comparer des acteurs", "CODES DE LA GRILLE", "P"),
    ("FIG", "Nature des identifiants", "[monetaire]", "P"),
    ("FIG", "Grandeurs de même nature", "MEME NATURE", "P"),
    ("FIG", "Deux identifiants minimum", "DEUX identifiants", "P"),
    ("FIG", "Crochets non recopiés", "CES CROCHETS SONT POUR TOI SEUL", "P"),
]


def _prompt(livrable: str, *, dernier: bool = False) -> str:
    offre, _ = Offer.objects.get_or_create(
        slug=f"verif-{livrable}",
        defaults={"name": f"Verif {livrable}", "deliverable_type": livrable},
    )
    contact, _ = Customer.objects.get_or_create(email=f"verif-{livrable}@test.local")
    commande = Order.objects.create(
        systeme_order_id=f"verif-{livrable}-{dernier}-{uuid.uuid4().hex[:8]}",
        customer=contact, offer=offre,
    )
    IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED,
        source=IntakeSource.MANUAL, normalized_variables=VARIABLES,
    )
    job = bootstrap_generation_job(commande.intake_submission)
    chapitres = job.chapters.order_by("chapter_number")
    chapitre = (
        chapitres.last() if dernier
        else chapitres.filter(chapter_number__gt=0).first()
    )
    assert chapitre is not None
    prompt, _ = construire_prompt_chapitre(
        chapitre,
        socle=SOCLE,
        variables=VARIABLES,
        document=type_document(livrable),
    )
    return str(prompt)


@pytest.fixture(scope="module")
def textes(django_db_setup: object, django_db_blocker: object) -> dict[str, str]:
    """Les prompts réels, construits UNE fois : 37 demandes, pas 37 montages."""
    with django_db_blocker.unblock():  # type: ignore[attr-defined]
        return {
            "S": _SYSTEME,
            "P": _prompt(DeliverableType.MARKET_STUDY),
            "D": _prompt(DeliverableType.MARKET_STUDY, dernier=True),
            "E": _prompt(DeliverableType.COMPETITOR_STUDY),
            "SOCLE": construire_prompt_socle(
                deliverable_type=DeliverableType.COMPETITOR_STUDY,
                variables=VARIABLES,
            ),
        }


@pytest.mark.parametrize(
    ("libelle", "fragment", "ou"),
    [(libelle, fragment, ou) for _, libelle, fragment, ou in DEMANDES],
    ids=[libelle for _, libelle, _, _ in DEMANDES],
)
def test_la_demande_est_dans_le_prompt_reellement_envoye(
    textes: dict[str, str], libelle: str, fragment: str, ou: str
) -> None:
    assert fragment in textes[ou], (
        f"« {libelle} » ne part plus : fragment « {fragment} » absent du "
        f"prompt {ou}. Écrit ne veut pas dire transmis (règle 8)."
    )


UNIVERSELLES: list[tuple[str, str]] = [
    ("Quatre questions", "QUATRE questions"),
    ("Échelle de notation 1-5", "5 référence du secteur"),
    ("Ton décisionnel (système)", "INTERDITES"),
    ("Unités lisibles", "Md€"),
    ("Nature des identifiants", "[monetaire]"),
    ("Règles de figures", "MEME NATURE"),
]


@pytest.mark.parametrize("livrable", list(DeliverableType.values))
def test_les_regles_de_fond_atteignent_chaque_livrable(
    django_db_blocker: object, livrable: str
) -> None:
    """Demande explicite du 09/08/2026 : les règles valent pour les QUATRE.

    Deux d'entre elles n'atteignaient pas l'étude de marché — le seul
    livrable sur lequel la cliente les avait demandées.
    """
    with django_db_blocker.unblock():  # type: ignore[attr-defined]
        texte = _prompt(livrable) + "\n" + _SYSTEME
    manquantes = [
        libelle for libelle, fragment in UNIVERSELLES if fragment not in texte
    ]
    assert manquantes == [], f"{livrable} ne reçoit pas : {', '.join(manquantes)}"


def test_aucune_fiche_n_exige_un_format_de_donnees() -> None:
    """La classe entière, verrouillée sur les fichiers SERVIS au modèle.

    Quatorze fiches exigeaient un « tableau HTML » et une exigeait du « CSV
    brut » — pendant que `_SYSTEME` interdisait l'un et l'autre dans le même
    prompt, et que la validation rejetait le chapitre obéissant. Le modèle ne
    pouvait pas gagner ; chaque obéissance était un chapitre repayé.

    Les fiches `chapitre_00` sont exclues : le cadrage est interne, jamais
    publié, et son tableau Markdown est parsé par la machine.
    """
    from generation.chapitres.fichiers_prompts import rendre_prompt  # noqa: PLC0415

    racine = __import__("pathlib").Path(rendre_prompt.__code__.co_filename)
    dossier_prompts = racine.parents[3] / "prompts"
    assert dossier_prompts.is_dir(), dossier_prompts

    exigences = ("tableau HTML", "HTML inline", "<table", "CSV brut", "version CSV")
    fautifs: list[str] = []
    for fiche in sorted(dossier_prompts.rglob("chapitre_*.md")):
        if fiche.stem == "chapitre_00":
            continue
        texte = fiche.read_text(encoding="utf-8")
        for exigence in exigences:
            if exigence in texte:
                fautifs.append(f"{fiche.parent.name}/{fiche.name} : « {exigence} »")
    assert fautifs == [], "\n".join(fautifs)

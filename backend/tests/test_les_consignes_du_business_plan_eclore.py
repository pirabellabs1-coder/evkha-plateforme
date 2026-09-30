"""Les consignes que le moteur structuré envoie VRAIMENT, après le business plan ÉCLORE.

Business plan ÉCLORE (dossier `cb59cede`, 29/09/2026, 107 pages). Le
diagnostic du même jour (§ 1, § 3.5 à 3.10) a trouvé la moitié de ses défauts
dans les consignes, pas chez le modèle :

- le chapitre 16 (prévisionnel) partait avec « Ne pas utiliser ce prompt
  directement » pour toute consigne — le moteur structuré ne découpe jamais un
  chapitre en sections ;
- le chapitre 13 tenait en une ligne, « régime fiscal » : la TVA obligatoire
  au-dessus du seuil a été présentée comme « un choix prudent » ;
- le chapitre 7 disait « 8 + 3 maximum » quand la base disait « ni plus ni
  moins », et « 13 acteurs », tiré de l'étude jointe par la cliente, a été
  présenté comme notre panel ;
- des numéros de chapitre en dur (« la bibliographie du chapitre 21 » pour les
  quatre livrables, « chapitre 13 », « chapitre 16 ») ;
- la règle « CHRONOLOGIE UNIQUE » n'atteignait que l'ancien moteur : cinq
  formulations pour une même date de départ ;
- l'annexe déclarait « traitée » sans preuve, et une règle y poussait.

Chaque test lit ce qui PART — le prompt rendu, le bloc construit, le système
capturé — et non la constante dans son module (règle 8 : écrit, testé, jamais
transmis). Tous échouent sur le code d'avant (29/09/2026).
"""
from __future__ import annotations

import contextlib
import re
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest

from catalog.models import DeliverableType
from generation.blueprints import chapters_for_deliverable, get_blueprint
from generation.chapitres.configuration import types_declares
from generation.chapitres.fichiers_prompts import (
    _BANDEAU,
    charger_prompt,
    nom_fichier,
    rendre_prompt,
)

BP = DeliverableType.BUSINESS_PLAN


def _valeurs(code: str, numero: int) -> dict[str, object]:
    """Les valeurs d'interpolation, construites comme `_valeurs_interpolation`."""
    from generation.chapitres.runner import renvois_du_plan

    plan = get_blueprint(code, numero)
    return {
        "secteur": "bien-être", "pays": "France", "zone": "Lyon",
        "projet": "atelier de bien-être", "numero_chapitre": numero,
        "titre_chapitre": plan.title if plan else "", "cible_mots": 900,
        "scenario_reference": "scénario de référence",
        **renvois_du_plan(code),
    }


def _prompt(code: str, numero: int) -> str:
    texte, manquantes = rendre_prompt(code, numero, _valeurs(code, numero))
    assert manquantes == [], manquantes
    return texte


# ── Le prévisionnel financier (chapitre 16) ─────────────────────────────────


def test_le_previsionnel_a_une_vraie_consigne() -> None:
    texte = _prompt(BP, 16)

    assert "Ne pas utiliser ce prompt" not in texte
    # Les identités du compte de résultat, écrites en toutes lettres.
    assert "chiffre d'affaires − charges (variables et fixes) = EBE" in texte
    assert "EBE − dotations aux amortissements − impôts = résultat net" in texte
    assert "CAF = résultat net + dotations aux amortissements" in texte
    assert "Résultat net et CAF ne se confondent JAMAIS" in texte
    # Le revenu du dirigeant, défini selon le statut.
    assert (
        "En micro-entreprise : chiffre d'affaires − charges réellement décaissées "
        "− cotisations sociales" in texte
    )
    assert "En société : la rémunération versée au dirigeant, plus les dividendes" in texte
    # Les dérivés se calculent sur le tableau ; les chiffres du client font foi.
    assert "Tout chiffre dérivé se calcule sur les lignes du tableau" in texte
    assert "se reproduit EXACTEMENT" in texte
    # Le compte de résultat couvre TOUS les exercices donnés.
    assert "sans en retirer aucun" in texte


def test_aucun_prompt_n_est_un_aiguillage_vers_des_sections() -> None:
    """La CLASSE : le moteur structuré lit le fichier du chapitre, et lui seul.

    Deux fichiers le disaient sur le code d'avant : le prévisionnel du business
    plan et l'approfondissement de l'étude concurrentielle (chapitre 3).
    """
    fautifs = [
        f"{document.dossier_prompts}/{nom_fichier(plan.number)}"
        for document in types_declares()
        for plan in document.chapitres()
        if re.search(
            r"ne pas utiliser ce prompt|sections distinctes",
            charger_prompt(document.code, plan.number),
            re.IGNORECASE,
        )
    ]
    assert fautifs == []


# ── La structure juridique (chapitre 13) ────────────────────────────────────


def test_la_tva_est_obligatoire_au_dessus_du_seuil() -> None:
    texte = _prompt(BP, 13)

    assert "37 500 €" in texte and "85 000 €" in texte
    assert "valeurs 2026" in texte
    assert "la TVA est OBLIGATOIRE" in texte
    assert "N'écris JAMAIS qu'une TVA obligatoire est appliquée « par choix »" in texte
    # Les plafonds de la micro-entreprise et la règle de sortie exacte.
    assert "83 600 €" in texte and "203 100 €" in texte
    assert "DEUX années civiles consécutives" in texte
    assert "Un seul dépassement ne fait pas sortir du régime" in texte
    # Le statut année par année, les cotisations en pourcentage du CA.
    assert "une ligne par exercice du prévisionnel" in texte
    assert "POURCENTAGE du chiffre d'affaires" in texte


# ── Le nombre de concurrents (chapitre 7 et base consolidée) ────────────────


def test_le_chapitre_7_suit_le_decompte_de_la_base_et_rien_d_autre() -> None:
    texte = _prompt(BP, 7)

    assert "maximum" not in texte
    assert not re.search(r"\b\d+\s+(?:directs|indirects|concurrents|acteurs)\b", texte)
    assert "ni plus ni moins" in texte
    assert "TOUJOURS le décompte de cette base" in texte
    assert "en l'attribuant explicitement à son document" in texte


def test_la_base_consolidee_attribue_au_client_son_propre_compte() -> None:
    """Le « 13 acteurs » d'ÉCLORE était au chapitre 1 : la règle doit être lue
    par CHAQUE chapitre, donc vivre dans le bloc de la base."""
    from generation.chapitres.runner import _bloc_concurrents
    from generation.socle.schema import Concurrent, Socle, Zone

    socle = Socle(
        secteur="bien-être", zone=Zone(pays="France"), date_socle=date(2026, 9, 29),
        concurrents=[
            Concurrent(nom="Studio A", type="direct", site_web="studio-a.fr"),
            Concurrent(nom="Studio B", type="indirect", site_web="studio-b.fr"),
        ],
    )
    bloc = _bloc_concurrents(socle)

    assert "ni plus ni moins" in bloc
    assert "ce nombre est le SIEN" in bloc
    assert "attribue-le explicitement à son document" in bloc


# ── Les renvois : lus dans le plan, jamais écrits en dur ────────────────────


@pytest.mark.parametrize(
    ("livrable", "attendu"),
    [
        (DeliverableType.BUSINESS_STRATEGY, "chapitre 20 « Sources et méthodologie »"),
        (DeliverableType.COMPETITOR_STUDY, "chapitre 9 « Sources et méthodologie »"),
        (DeliverableType.BUSINESS_PLAN, "chapitre 21 « Sources et méthodologie »"),
    ],
)
def test_le_bloc_des_sources_renvoie_au_chapitre_des_sources_du_livrable(
    livrable: str, attendu: str
) -> None:
    """« La bibliographie du chapitre 21 » était dit aux QUATRE livrables."""
    from generation.chapitres.runner import _bloc_sources

    dossier = SimpleNamespace(research_brief="Une source collectée.", deliverable_type=livrable)
    bloc = _bloc_sources(dossier, 3)  # type: ignore[arg-type]

    assert attendu in bloc
    if livrable != DeliverableType.BUSINESS_PLAN:
        assert "chapitre 21" not in bloc


def test_le_chapitre_des_sources_parle_de_sa_propre_bibliographie() -> None:
    from generation.chapitres.runner import _bloc_sources

    dossier = SimpleNamespace(
        research_brief="Une source collectée.", deliverable_type=DeliverableType.COMPETITOR_STUDY
    )
    bloc = _bloc_sources(dossier, 9)  # type: ignore[arg-type]

    assert "la bibliographie de CE chapitre" in bloc
    assert "chapitre 9" not in bloc


def test_un_renvoi_porte_le_numero_et_le_titre_du_plan() -> None:
    from generation.chapitres.runner import renvois_du_plan

    renvois = renvois_du_plan(BP)

    assert renvois["renvoi_previsionnel_financier"] == "chapitre 16 « Prévisionnel financier »"
    assert renvois["renvoi_structure_juridique"] == (
        "chapitre 13 « Structure juridique et réglementaire »"
    )
    # La fiche projet n'est pas publiée : on n'y renvoie jamais.
    assert "renvoi_fiche_projet" not in renvois
    assert renvois_du_plan("livrable_inconnu") == {}


_NUMERO_EN_DUR = re.compile(r"\bchapitres?\s+(\d+)", re.IGNORECASE)


def test_aucun_prompt_ne_cite_un_numero_de_chapitre_en_dur() -> None:
    """La CLASSE du défaut, sur les quatre livrables (règle 4).

    Seul l'intitulé du chapitre lui-même garde son numéro (« CHAPITRE 13 — …
    »). Tout renvoi vers un AUTRE chapitre passe par `{{ renvoi_<clé> }}`. Sur
    le code d'avant : business plan 14, 15 et 18, étude de marché 2, 11, 13
    et 18, étude concurrentielle 4, 5 et 6.
    """
    fautes: dict[str, list[str]] = {}
    for document in types_declares():
        for plan in document.chapitres():
            corps = charger_prompt(document.code, plan.number)
            autres = [
                n for n in _NUMERO_EN_DUR.findall(corps) if int(n) != plan.number
            ]
            if autres:
                fautes[f"{document.dossier_prompts}/{nom_fichier(plan.number)}"] = autres
    assert fautes == {}


def test_chaque_variable_de_chaque_prompt_se_resout() -> None:
    """Un renvoi vers un chapitre que le livrable n'a pas resterait un trou.

    Rendus avec les valeurs de `_valeurs_interpolation`, aucun prompt ne doit
    garder une variable : ce serait `{{ renvoi_… }}` imprimé tel quel dans la
    consigne du modèle.
    """
    trous: dict[str, list[str]] = {}
    for document in types_declares():
        for plan in document.chapitres():
            _texte, manquantes = rendre_prompt(
                document.code, plan.number, _valeurs(document.code, plan.number)
            )
            if manquantes:
                trous[f"{document.dossier_prompts}/{nom_fichier(plan.number)}"] = manquantes
    assert trous == {}


def test_la_garde_sait_encore_mordre() -> None:
    """CONTRE-ÉPREUVE : un renvoi en dur ajouté demain serait vu."""
    corps = _BANDEAU.sub("", "<!-- bandeau -->\nCohérence avec le chapitre 16.")
    assert _NUMERO_EN_DUR.findall(corps) == ["16"]


# ── L'annexe des demandes du client ─────────────────────────────────────────


def test_un_statut_traitee_se_prouve_par_le_chapitre_et_la_section() -> None:
    from generation.chapitres.runner import REGLES_DE_FOND

    for nom, texte in (("règles de fond", REGLES_DE_FOND), ("chapitre 20", _prompt(BP, 20))):
        plat = " ".join(texte.split())
        assert "le chapitre ET la section" in plat, nom
        assert "partiellement traitée" in plat, nom
        assert "Dans le doute" in plat, nom
        # CONTRE-ÉPREUVE : l'autre sens reste interdit — un sujet traité
        # ailleurs n'est jamais « non traité » (`demande_contredite`).
        assert "non traitée" in plat.lower() and "ailleurs" in plat, nom


# ── La chronologie, dans le prompt système du moteur structuré ──────────────


@pytest.fixture
def dossier_bp(db: object) -> Any:
    from catalog.models import Offer
    from customers.models import Customer
    from generation.services import bootstrap_generation_job
    from generation.socle import etablir_socle
    from intake.models import IntakeStatus, IntakeSubmission
    from integrations.claude import StubClaudeClient
    from orders.models import Order

    variables = {
        "SECTEUR": "bien-être", "PAYS": "France", "ZONE": "Lyon",
        "PROJET": "atelier de bien-être",
    }
    offre = Offer.objects.create(name="BP", slug="bp-chronologie", deliverable_type=BP)
    client = Customer.objects.create(email="chronologie@exemple.fr")
    commande = Order.objects.create(
        systeme_order_id="cmd-chronologie", customer=client, offer=offre
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED, normalized_variables=variables
    )
    dossier = bootstrap_generation_job(soumission)
    etablir_socle(dossier, client=StubClaudeClient(), variables=variables)
    return dossier


@pytest.mark.django_db
def test_la_chronologie_unique_part_vers_le_modele_et_dans_le_cache(dossier_bp: Any) -> None:
    """On lit le système ENVOYÉ, pas la constante : écrite, testée, jamais transmise."""
    from generation.chapitres import ChapitreInvalideError, produire_chapitre
    from integrations.claude import SYSTEM_CACHE_BREAK, StructuredResult, StubClaudeClient

    class _Espion(StubClaudeClient):
        def __init__(self) -> None:
            super().__init__()
            self.systemes: list[str] = []

        def complete_structured(self, **kwargs: Any) -> StructuredResult:
            self.systemes.append(str(kwargs.get("system", "")))
            return super().complete_structured(**kwargs)

    espion = _Espion()
    with contextlib.suppress(ChapitreInvalideError):
        produire_chapitre(dossier_bp, 1, client=espion)
    assert espion.systemes, "le chapitre n'a jamais appelé le modèle"
    systeme = espion.systemes[0]

    for regle in (
        "CHAQUE ÉVÉNEMENT A UNE SEULE DATE, CELLE DU BRIEF",
        "UNE DÉCISION DATÉE NE SE REFORMULE JAMAIS",
        "CE QUI EXISTE ET CE QUI EST VISÉ NE SE CONFONDENT PAS",
    ):
        assert regle in systeme, regle
        # Du côté CACHÉ du prompt : sinon repayée à chaque chapitre.
        assert systeme.index(regle) < systeme.index(SYSTEM_CACHE_BREAK), regle


def test_la_regle_de_chronologie_ne_montre_aucune_date_fautive() -> None:
    """L'exemple d'une faute se recopie : la règle dit la classe, sans année."""
    from generation.chapitres.runner import CHRONOLOGIE_ET_DECISIONS

    assert not re.search(r"\b20\d\d\b", CHRONOLOGIE_ET_DECISIONS)


def test_le_plan_du_business_plan_n_a_qu_un_chapitre_des_sources() -> None:
    """Hypothèse des renvois : une seule entrée `sources` par plan."""
    for code in (BP, DeliverableType.BUSINESS_STRATEGY, DeliverableType.COMPETITOR_STUDY):
        sources = [p for p in chapters_for_deliverable(code) if p.section_kind == "sources"]
        assert len(sources) == 1, code

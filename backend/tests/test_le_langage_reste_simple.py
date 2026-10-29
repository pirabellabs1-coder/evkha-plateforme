"""Un langage simple : les sigles d'analyse et le gras brut se réparent.

Cliente, 29/10/2026 : « c'est toujours très technique, avec des termes très
analytiques ». Les phrases ci-dessous sont celles des études `6832779f` et
`99a142b0`, telles que livrées.
"""
from __future__ import annotations

import pytest

from catalog.models import DeliverableType
from generation.chapitres.langage_simple import simplifier_le_langage, simplifier_texte
from generation.chapitres.schema import ChapitrePayload

# ── Le gras Markdown n'est jamais imprimé ───────────────────────────────────


def test_le_gras_markdown_disparait_le_texte_reste() -> None:
    brut = "**Formule et dérivation** — le calcul suit."
    assert simplifier_texte(brut, sigles_admis=True) == "Formule et dérivation — le calcul suit."


@pytest.mark.parametrize(
    "texte",
    [
        "Le prix × 2 * 3 reste une opération.",
        "Une note de bas de page*.",
        "Les fichiers __init__ et nom_de_fichier.",
    ],
)
def test_un_asterisque_seul_n_est_pas_du_gras(texte: str) -> None:
    assert simplifier_texte(texte, sigles_admis=False) == texte


# ── Les sigles hors du chapitre qui les pose ────────────────────────────────


@pytest.mark.parametrize(
    ("avant", "apres"),
    [
        ("Le marché accessible est estimé à 1,27 Md€, soit 27,6 % du TAM.",
         "Le marché accessible est estimé à 1,27 Md€, soit 27,6 % du marché total."),
        ("Ce taux s'applique au SAM de l'étude.",
         "Ce taux s'applique au marché accessible de l'étude."),
        ("SAM — TPE prêtes à payer un prestataire IA",
         "Marché accessible — TPE prêtes à payer un prestataire IA"),
        ("Emboîtement : 4,6 Md€ > 1,27 Md€. Le SOM année 1 tient.",
         "Emboîtement : 4,6 Md€ > 1,27 Md€. Le chiffre d'affaires visé année 1 tient."),
        ("Le marché total (TAM) vaut 1 000 M€.", "Le marché total vaut 1 000 M€."),
        ("TAM > SAM > SOM", "Marché total > marché accessible > chiffre d'affaires visé"),
    ],
)
def test_les_sigles_prennent_leur_nom_simple(avant: str, apres: str) -> None:
    assert simplifier_texte(avant, sigles_admis=False) == apres


@pytest.mark.parametrize(
    "texte",
    [
        # Le chapitre qui les pose les garde (cahier des charges).
        "Le TAM, le marché total, vaut 4,6 Md€.",
        # Un mot qui CONTIENT le sigle n'est pas le sigle.
        "Le SAMU, la SOMME, le TAMIS et la société SAM-Immo.",
    ],
)
def test_ce_qui_n_est_pas_un_sigle_a_remplacer_reste(texte: str) -> None:
    attendu = texte
    sigles_admis = texte.startswith("Le TAM")
    assert simplifier_texte(texte, sigles_admis=sigles_admis) == attendu


def test_la_reparation_est_idempotente() -> None:
    une = simplifier_texte("**Le SOM** et le SAM (SAM).", sigles_admis=False)
    assert simplifier_texte(une, sigles_admis=False) == une


# ── Sur un chapitre entier, selon son livrable et son numéro ────────────────


def _chapitre(numero: int, texte: str) -> ChapitrePayload:
    return ChapitrePayload.model_validate({
        "chapitre": numero,
        "titre": "Chapitre",
        "blocs": [
            {"type": "paragraphe", "texte": texte},
            {"type": "tableau", "tableau": {
                "entetes": ["Niveau", "Valeur"],
                "lignes": [["SAM — mode femme en ligne", "1,27 Md€"]],
                "source": "Source de test",
            }},
        ],
        "resume": "Résumé " * 160,
    })


def test_le_chapitre_deux_de_l_etude_de_marche_garde_ses_sigles() -> None:
    payload = _chapitre(2, "Le TAM vaut 4,6 Md€ ; **le SAM** en est une part.")
    simplifier_le_langage(payload, deliverable_type=DeliverableType.MARKET_STUDY)
    assert payload.paragraphes == ["Le TAM vaut 4,6 Md€ ; le SAM en est une part."]
    assert payload.tableaux[0].lignes[0][0] == "SAM — mode femme en ligne"


@pytest.mark.parametrize(
    ("livrable", "numero"),
    [
        (DeliverableType.MARKET_STUDY, 14),
        (DeliverableType.BUSINESS_PLAN, 2),
        (DeliverableType.COMPETITOR_STUDY, 2),
        (DeliverableType.BUSINESS_STRATEGY, 2),
    ],
)
def test_ailleurs_les_sigles_et_les_cellules_sont_simplifies(livrable: str, numero: int) -> None:
    payload = _chapitre(numero, "Le SOM reste une fraction du SAM.")
    retouches = simplifier_le_langage(payload, deliverable_type=livrable)
    assert payload.paragraphes == [
        "Le chiffre d'affaires visé reste une fraction du marché accessible."
    ]
    assert payload.tableaux[0].lignes[0][0] == "Marché accessible — mode femme en ligne"
    assert retouches == 2


# ── L'annexe des chiffres affiche les libellés du socle ─────────────────────


def test_l_annexe_affiche_le_nom_simple_et_le_socle_garde_son_sigle() -> None:
    """`6832779f`, annexe : « TAM – textile d'occasion… » imprimé tel quel. Le
    libellé STOCKÉ garde le sigle (la cohérence le lit) ; seul l'affiché change."""
    from generation.rendu_word.texte import libelle_court

    stocke = "TAM – textile d'occasion vendu en France, tous canaux. Source large."
    assert libelle_court(stocke) == "Marché total – textile d'occasion vendu en France, tous canaux"
    assert stocke.startswith("TAM")


# ── Les formes que l'ancienne consigne a installées (relecture du 29/10/2026) ─


@pytest.mark.parametrize(
    ("avant", "apres"),
    [
        # La parenthèse QUALIFIE un montant : elle reste, en nom simple.
        ("Le marché pèse 30 000 M€ (TAM), dont 2 400 M€ (SAM).",
         "Le marché pèse 30 000 M€ (marché total), dont 2 400 M€ (marché accessible)."),
        # Le nom n'est jamais écrit deux fois.
        ("Le SAM (marché accessible) vaut 1,27 Md€.", "Le marché accessible vaut 1,27 Md€."),
        ("Le marché accessible, ou SAM, vaut 1,27 Md€.", "Le marché accessible vaut 1,27 Md€."),
        # Pas de majuscule après un deux-points.
        ("Trois niveaux : TAM, puis SAM.", "Trois niveaux : marché total, puis marché accessible."),
    ],
)
def test_les_formes_installees_restent_justes(avant: str, apres: str) -> None:
    assert simplifier_texte(avant, sigles_admis=False) == apres


@pytest.mark.parametrize(
    "texte",
    [
        # Un remplacement mot à mot ferait une faute d'accord ou un doublon :
        # le sigle reste, la consigne et la relecture s'en chargent.
        "Les SOM An1 et An3 restent prudents.",
        "Le SOM visé reste prudent.",
        "Une SAM monégasque détient la marque.",
        # Un sigle dans une adresse n'est pas un sigle du texte.
        "https://exemple.fr/SAM/rapport",
    ],
)
def test_un_remplacement_qui_ferait_une_faute_n_est_pas_fait(texte: str) -> None:
    assert simplifier_texte(texte, sigles_admis=False) == texte


def test_au_dela_de_la_borne_le_gras_part_quand_meme() -> None:
    """Le nom simple ne tient pas dans la borne : les sigles restent, mais le
    gras, qui ne fait que raccourcir, part."""
    from generation.chapitres.langage_simple import _simplifier_champ
    from generation.chapitres.schema import CelluleKpi
    from generation.chapitres.typographie import _borne

    cellule = CelluleKpi.model_construct(libelle="", valeur="1", unite="")
    borne = _borne(cellule, "libelle")
    assert borne is not None
    texte = "**SOM**" + " SAM" * ((borne - 7) // 4)
    assert len(texte) <= borne
    cellule.libelle = texte
    assert _simplifier_champ(cellule, "libelle", False) == 1
    assert cellule.libelle == texte.replace("**", "")


# ── Les étiquettes de figures et le contrôle qui lit l'affiché ──────────────


def test_les_etiquettes_de_l_entonnoir_n_affichent_plus_de_sigle() -> None:
    from generation.rendu_word.donnees_graphiques import etiquettes_de
    from generation.socle.schema import DonneeSocle

    donnees = [
        DonneeSocle.model_validate({
            "id": cle, "libelle": f"{cle.upper()} — mode femme d'occasion", "valeur": v,
            "unite": "MEUR", "annee": 2025, "perimetre": "national",
            "source": "Source", "fiabilite": "estimee", "derivee_de": [],
        })
        for cle, v in (("tam", 4600.0), ("sam", 1270.0), ("som", 0.024))
    ]
    etiquettes = etiquettes_de(donnees)
    assert not [e for e in etiquettes if any(s in e for s in ("TAM", "SAM", "SOM"))], etiquettes


def test_un_nombre_du_libelle_affiche_reste_justifie() -> None:
    """Contre-épreuve : la ligne affichée « Chiffre d'affaires visé — 1 200
    articles… » cite le libellé stocké « SOM — 1 200 articles… »."""
    from generation.socle.schema import DonneeSocle, Socle
    from generation.verification.controles import _cite_un_libelle_du_socle
    from generation.verification.lecture import mesures_dans

    socle = Socle.model_construct(donnees=[DonneeSocle.model_validate({
        "id": "som", "libelle": "SOM — 1 200 articles × 20 € la pièce en année 1",
        "valeur": 24000.0, "unite": "EUR", "annee": 2027, "perimetre": "entreprise",
        "source": "", "fiabilite": "scenario", "derivee_de": [],
    })])
    phrase = "Chiffre d'affaires visé — 1 200 articles × 20 € la pièce en année 1 | 24 000 €"
    (vingt,) = [m for m in mesures_dans(phrase) if m.valeur == 20]
    assert _cite_un_libelle_du_socle(vingt, socle)


# ── Le câblage : la réparation tourne bien quand un chapitre est écrit ──────


def test_la_generation_d_un_chapitre_passe_par_la_simplification(
    db: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retirer l'appel dans `runner.generer_chapitre` doit faire tomber ce test
    (règle 6) : la logique testée plus haut ne sert à rien si rien ne l'appelle."""
    from catalog.models import Offer
    from customers.models import Customer
    from generation.chapitres import produire_chapitre
    from generation.services import bootstrap_generation_job
    from generation.socle import etablir_socle
    from intake.models import IntakeStatus, IntakeSubmission
    from integrations.claude import StubClaudeClient
    from orders.models import Order

    appels: list[tuple[int, str]] = []
    vraie = simplifier_le_langage

    def espion(payload: object, *, deliverable_type: str) -> int:
        appels.append((int(getattr(payload, "chapitre", -1)), deliverable_type))
        return vraie(payload, deliverable_type=deliverable_type)

    monkeypatch.setattr("generation.chapitres.runner.simplifier_le_langage", espion)
    variables = {"SECTEUR": "joaillerie de créateurs", "PAYS": "France",
                 "ZONE": "Paris", "PROJET": "maison d'édition joaillière"}
    offre = Offer.objects.create(
        name="EM", slug="em-langage", deliverable_type=DeliverableType.MARKET_STUDY
    )
    commande = Order.objects.create(
        systeme_order_id="order-langage-01",
        customer=Customer.objects.create(email="langage@example.com"), offer=offre,
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED, normalized_variables=variables
    )
    job = bootstrap_generation_job(soumission)
    etablir_socle(job, client=StubClaudeClient(), variables=variables)

    produire_chapitre(job, 4, client=StubClaudeClient())
    assert appels == [(4, DeliverableType.MARKET_STUDY)]

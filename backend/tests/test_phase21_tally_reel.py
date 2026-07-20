"""Phase 21 — Les libelles REELS des formulaires Tally de la cliente.

Juillet 2026 : la cliente refond ses quatre formulaires et ajoute enfin les
champs dedies que la Brique 1 reclamait (« 10.Investissement total »,
« 12.CA previsionnel (ou CA an1 a an5) », « 13. Previsionnel et tableaux
financier. »).

Passes tels quels dans `_canonical_key`, AUCUN des trois n'etait reconnu. Les
deux faits exiges par le gate pour un business plan — `investissement_total` et
`ca_previsionnel` — arrivaient en base et etaient jetes. Le dossier bloquait,
avec un motif accusant la cliente de ne pas avoir fourni les chiffres qu'elle
venait de rendre obligatoires.

Trois causes independantes, un seul motif : viser l'exemple au lieu de la
classe. Les tests ci-dessous partent tous des libelles exacts lus sur les
formulaires en ligne, jamais d'un libelle reecrit pour l'occasion.
"""
from __future__ import annotations

import pytest

from core.numbers import amounts_in
from intake.financials import extract_financials_from_text
from intake.services import _canonical_key, normalize_intake_variables

# ── Libelles copies des formulaires en ligne (scrape du 17/07/2026) ─────────
LIBELLE_INVESTISSEMENT = "10.Investissement total"
LIBELLE_CA = "12.CA prévisionnel (ou CA an1 à an5)"
LIBELLE_PREVISIONNEL = "13. Prévisionnel et tableaux financier."
LIBELLE_SECTEUR = "Secteur et domaine d’activité"


# ── 1. Reconnaissance des libelles ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("libelle", "attendu"),
    [
        (LIBELLE_INVESTISSEMENT, "INVESTISSEMENT_TOTAL"),
        (LIBELLE_CA, "CA_PREVISIONNEL"),
        (LIBELLE_PREVISIONNEL, "ETAT_CHIFFRE_LIBRE"),
        ("Nom de votre entreprise", "NOM_ENTREPRISE"),
        ("Logo de votre entreprise ( optionnel)", "LOGO_URL"),
        ("Couleur principale de votre charte graphique (optionnel)", "COULEUR_PRINCIPALE"),
        ("Couleur secondaire (optionnel)", "COULEUR_SECONDAIRE"),
        ("11. Besoins Financiers & Prévisions", "BESOINS_FINANCIERS"),
        # Les accents seuls suffisaient a faire tomber le libelle : la table
        # est ecrite sans accents et `_canonical_key` ne les enlevait pas,
        # alors que `_strip_accents` existe dans le meme fichier.
        ("CA prévisionnel", "CA_PREVISIONNEL"),
        ("Seuil de rentabilité", "SEUIL_RENTABILITE"),
        ("Verticales d’activité", "VERTICALES"),
    ],
)
def test_les_libelles_reels_sont_reconnus(libelle: str, attendu: str) -> None:
    assert _canonical_key(libelle) == attendu


@pytest.mark.parametrize(
    "libelle",
    [
        "Quelles tendances actuelles influencent votre marché ?",
        "Note à lire avant de commencer",
        "Submit",
        "",
        "   ",
    ],
)
def test_le_texte_ordinaire_n_est_pas_pris_pour_un_champ(libelle: str) -> None:
    """Contre-epreuve : normaliser ne doit pas rendre la table gloutonne."""
    assert _canonical_key(libelle) is None


# ── 2. Un libelle ne vole pas les montants du suivant ───────────────────────


def test_le_format_tirets_du_formulaire_ne_fusionne_pas_les_montants() -> None:
    """La consigne exacte du champ 13, telle que la cliente l'a ecrite.

    AVANT : resultat_net = « 145 000 € / 310 000 € / 640 000 € » — le resultat
    net, l'EBE et le seuil fusionnes en un seul fait CLIENT verrouille.
    """
    texte = (
        "Résultat net prévisionnel 145 000 €- EBE prévisionnel 310 000 €- "
        "Taux d'occupation 78%- Seuil de rentabilité 640 000 €"
    )

    trouve = extract_financials_from_text(texte)

    assert trouve["RESULTAT_NET_PREVISIONNEL"] == "145 000 €"
    assert trouve["EBE_PREVISIONNEL"] == "310 000 €"
    assert trouve["SEUIL_RENTABILITE"] == "640 000 €"
    assert trouve["TAUX_OCCUPATION"] == "78%"


def test_une_trajectoire_sur_une_ligne_reste_complete() -> None:
    """Contre-epreuve : borner ne doit pas amputer un CA multi-annees.

    Aucun autre libelle n'intervient ici : les trois annees se suivent.
    """
    trouve = extract_financials_from_text(
        "CA prévisionnel An1 : 250 272 €, An2 : 296 000 €, An3 : 318 400 €"
    )

    assert amounts_in(trouve["CA_PREVISIONNEL"]) == [250272.0, 296000.0, 318400.0]


def test_une_trajectoire_en_puces_reste_complete() -> None:
    """Contre-epreuve : le format qui avait motive `_values_after_every_label`."""
    trouve = extract_financials_from_text(
        "- CA prévisionnel An1 : 250 272 €\n"
        "- CA prévisionnel An2 : 296 000 €\n"
        "- CA prévisionnel An3 : 318 400 €"
    )

    assert amounts_in(trouve["CA_PREVISIONNEL"]) == [250272.0, 296000.0, 318400.0]


# ── 3. Un champ structure est de la prose, pas un nombre ────────────────────


def test_le_champ_ca_est_relu_et_non_gobe_brut() -> None:
    """Le champ dedie court-circuitait toutes les regles d'exclusion.

    Un champ structure gagne toujours sur l'extraction et sa valeur brute est
    verrouillee telle quelle en fait CLIENT. Le CA theorique — ecarte expres
    depuis le brief SYNAPSES — y redevenait un CA client legitime, et « 100 »,
    venu de « 100 % d'occupation », aussi.
    """
    payload = {
        "data": {
            "fields": [
                {
                    "label": LIBELLE_CA,
                    "type": "TEXTAREA",
                    "value": (
                        "CA prévisionnel An1 : 250 272 €, An2 : 296 000 €, "
                        "An3 : 318 400 €. CA théorique à 100 % d'occupation : "
                        "455 040 €/an"
                    ),
                }
            ]
        }
    }

    normalise, _ = normalize_intake_variables(payload)
    montants = amounts_in(str(normalise["CA_PREVISIONNEL"]))

    assert montants == [250272.0, 296000.0, 318400.0]
    assert 455040.0 not in montants, "le CA theorique n'est pas le previsionnel"
    assert 100.0 not in montants, "« 100 % » n'est pas un chiffre d'affaires"


def test_un_montant_nu_traverse_intact() -> None:
    """Contre-epreuve : sans libelle dans le champ, la valeur est deja propre.

    Relire ne doit pas vider un champ que le client a rempli correctement.
    """
    payload = {
        "data": {
            "fields": [
                {
                    "label": LIBELLE_INVESTISSEMENT,
                    "type": "TEXTAREA",
                    "value": "1 250 000 €",
                }
            ]
        }
    }

    normalise, _ = normalize_intake_variables(payload)

    assert amounts_in(str(normalise["INVESTISSEMENT_TOTAL"])) == [1250000.0]


# ── 4. Le formulaire complet, de bout en bout ───────────────────────────────


def test_le_formulaire_business_plan_livre_les_faits_exiges_par_le_gate() -> None:
    """`_REQUIRED_CLIENT_FACTS[BUSINESS_PLAN]` doit etre satisfait.

    C'est la raison d'etre de la refonte du formulaire : sans ces deux faits,
    le check 0 du gate bloque tout business plan.
    """
    payload = {
        "data": {
            "fields": [
                {
                    "label": LIBELLE_INVESTISSEMENT,
                    "type": "TEXTAREA",
                    "value": "Budget total de 1 250 000 € pour lancer le projet.",
                },
                {
                    "label": LIBELLE_CA,
                    "type": "TEXTAREA",
                    "value": "CA prévisionnel An1 : 920 000 €, An2 : 1 100 000 €",
                },
                {
                    "label": LIBELLE_PREVISIONNEL,
                    "type": "TEXTAREA",
                    "value": (
                        "Résultat net prévisionnel 145 000 €- Seuil de "
                        "rentabilité 640 000 €- Verticales d'activité : "
                        "coworking, domiciliation, événementiel"
                    ),
                },
                {"label": LIBELLE_SECTEUR, "type": "INPUT_TEXT", "value": "coworking"},
                {"label": "Nom de votre entreprise", "type": "INPUT_TEXT", "value": "SYNAPSES"},
            ]
        }
    }

    normalise, _ = normalize_intake_variables(payload)

    assert amounts_in(str(normalise["INVESTISSEMENT_TOTAL"])) == [1250000.0]
    assert amounts_in(str(normalise["CA_PREVISIONNEL"])) == [920000.0, 1100000.0]
    assert amounts_in(str(normalise["RESULTAT_NET_PREVISIONNEL"])) == [145000.0]
    assert amounts_in(str(normalise["SEUIL_RENTABILITE"])) == [640000.0]
    assert normalise["VERTICALES"] == "coworking / domiciliation / événementiel"
    assert normalise["SECTEUR"] == "coworking"
    assert normalise["NOM_ENTREPRISE"] == "SYNAPSES"


def test_pays_et_zone_sont_devines_faute_de_champ_dedie() -> None:
    """Constat, pas approbation : le fallback invente « France ».

    Aucun des quatre formulaires n'a de champ dedie au pays ni a la ville : ils
    sont noyes dans un encadre multi-questions. `_infer_missing_from_textareas`
    comble alors le trou par « France » — en silence, et faux des que le client
    n'est pas francais. La correction est cote formulaire, pas cote code : ce
    test existe pour que le jour ou la cliente ajoute les champs, personne ne
    s'etonne de le voir tomber.
    """
    normalise, manquantes = normalize_intake_variables(
        {
            "data": {
                "fields": [
                    {
                        "label": LIBELLE_SECTEUR,
                        "type": "INPUT_TEXT",
                        "value": "coworking",
                    }
                ]
            }
        }
    )

    assert normalise["PAYS"] == "France"
    assert normalise["ZONE"] == "France"
    assert "PROJET" in manquantes

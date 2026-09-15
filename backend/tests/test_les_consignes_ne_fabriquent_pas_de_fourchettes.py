"""Les consignes ne fabriquent plus — et ne montrent plus — les fourchettes qu'un contrôle refuse.

## Le défaut mesuré

Audit du 14/09/2026 (A1, A2, A3), corpus de production : `fourchette_interdite`
dans 3 business plans sur 7, 5 stratégies sur 12, et chaque chapitre signalé
est réécrit — donc repayé — par le correcteur. Or c'étaient nos propres
consignes qui produisaient ces plages :

- l'étude concurrentielle rendait OBLIGATOIRE une « fourchette basse / haute »
  que le gate interdisait (A1) ;
- le prompt système faisait écrire « une hypothèse prudente comprise entre X
  et Y » ; le libellé du socle recopiait la fourchette sous le chiffre ; la
  décision tarifaire STR demandait « fourchette ou prix cible » ;
- et les interdictions elles-mêmes MONTRAIENT la faute (« jamais de fourchette
  (« 100-120 k€ ») ») — la leçon du vocabulaire interne : le modèle reprend ce
  qu'on lui montre (A2).

Le détecteur, lui, se trompait dans les deux sens (A3) : il ne voyait pas
« de 60 à 65 € », et il prenait « An 1 — 120 000 € » pour une plage.

## Pourquoi un test de CLASSE

La liste des consignes grandit ; une plage ajoutée dans six mois ne sera pas
cherchée à la main. Le test passe donc le DÉTECTEUR LUI-MÊME — celui du gate —
sur tout ce qui part au modèle (règles 4 et 5).
"""
from __future__ import annotations

from typing import Any

import pytest

from generation.checks_evangeline import detecter_fourchettes

BP, EC, STR = "business_plan", "competitor_study", "business_strategy"


# ── Le détecteur ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("texte", [
    "Le prix se situe de 60 à 65 € par mois.",
    "un taux de 14-16 % observé",
    "entre 3 et 5 M€ de chiffre d'affaires",
])
def test_une_vraie_plage_est_vue(texte: str) -> None:
    """« à » accentué compris : « de 60 à 65 € » passait inaperçu."""
    assert detecter_fourchettes(1, texte, BP)


@pytest.mark.parametrize("texte", [
    "An 1 — 120 000 €",
    "Scénario 2 - 40 %",
    "N+1 - 250 000 €",
    "objectif 2027 — 250 000 €",
    "Mois 1 - 1 500 €",
    "Top 3 - 45 %",
    # Relecture du 14/09/2026, B1 : des TRAJECTOIRES datées, la forme même d'un
    # prévisionnel. Avec « à » accentué, « 2026 à 180 000 € » devenait une
    # fourchette, et le chapitre était réécrit — donc payé.
    "Le chiffre d'affaires passe de 120 000 € en 2026 à 180 000 € en 2027.",
    "La marge nette progresse de 3 % en 2026 à 5 % en 2028.",
    "La trésorerie passe de 12 000 € au 31/12/2026 à 48 000 € au 31/12/2027.",
    "Le seuil est atteint au mois 18 à 42 000 € de chiffre d'affaires mensuel.",
    # Corpus du 15/09/2026 : le numéro d'une étiquette devant « à ».
    "avec un top 3 régional à 35 % de part de marché et un top 5 à 50 %",
    "L'EBE progresse de 38 000 euros en exercice 1 à 84 000 euros en exercice 3.",
    "elle passe de 27 000 € à la fin de l'exercice 1 à 20 400 € à la fin de l'exercice 2",
    "un point de marge en moins ramènerait l'EBE de l'exercice 1 à environ 34 800 euros",
])
def test_une_etiquette_suivie_d_un_montant_n_est_pas_une_plage(texte: str) -> None:
    """CONTRE-ÉPREUVE : le motif rendu au client était faux (règle 2)."""
    assert detecter_fourchettes(1, texte, BP) == []


@pytest.mark.parametrize("texte", [
    # Relecture du 14/09/2026, I1 et I2 : la première version CACHAIT ces plages —
    # derrière une « étiquette » (offre, formule, niveau) ou un rapport de bornes
    # supérieur à 20 — alors que ce sont précisément les plages de prix que la
    # règle des prix refuse.
    "Nous recommandons pour l'offre entre 60 et 65 € par mois.",
    "La formule entre 49 et 59 € séduit les indépendants.",
    "Pour l'offre 60 à 65 € par mois.",
    "L'offre 49-59 € par mois reste la plus vendue.",
    "Le niveau 3-5 % de churn est acceptable.",
    "Un abonnement de 5-150 € par mois",
    "Un budget de 1-25 k€ par campagne",
    "Coût : 1,5-40 M€",
])
def test_une_plage_de_prix_derriere_une_etiquette_reste_vue(texte: str) -> None:
    assert detecter_fourchettes(1, texte, BP)


def test_en_ec_une_plage_suivie_de_sa_valeur_retenue_est_admise() -> None:
    """Le cahier des charges EC et la cliente, satisfaits ensemble (A1)."""
    texte = ("CA estimé entre 600 000 et 800 000 €, valeur retenue 700 000 €, "
             "sur la base de deux points de vente.")
    assert detecter_fourchettes(6, texte, EC) == []


@pytest.mark.parametrize("texte", [
    "CA estimé entre 600 000 et 800 000 €.",
    # La valeur retenue d'une AUTRE phrase ne vaut pas pour celle-ci (I3).
    "Dupont : CA entre 600 000 et 800 000 €. Martin : CA entre 1,2 et 1,5 M€, "
    "valeur retenue 1,35 M€.",
    # « retient » hors sujet.
    "CA estimé entre 600 000 et 800 000 €. Le projet retient la zone de Lyon.",
    # Une croissance reste une valeur unique, même en EC.
    "Le TCAC du segment est de 3 à 5 %, valeur retenue 4 %.",
])
def test_en_ec_une_plage_sans_sa_valeur_retenue_reste_refusee(texte: str) -> None:
    """CONTRE-ÉPREUVE : l'admission est étroite."""
    assert detecter_fourchettes(6, texte, EC)


def test_en_ec_retenue_a_accentue_vaut_valeur_retenue() -> None:
    """La même classe que le « à » du connecteur : « retenue à 700 000 € »."""
    texte = "CA estimé entre 600 000 et 800 000 €, retenue à 700 000 €."
    assert detecter_fourchettes(6, texte, EC) == []


def test_en_bp_meme_suivie_d_une_valeur_retenue_la_plage_reste_refusee() -> None:
    """CONTRE-ÉPREUVE : un prévisionnel tranche, sans exception."""
    texte = "Entre 600 000 et 800 000 €, valeur retenue 700 000 €."
    assert detecter_fourchettes(6, texte, BP)


# ── Tout ce qui part au modèle ───────────────────────────────────────────────


def _plages(texte: str, livrable: str) -> list[str]:
    return [f.extrait for f in detecter_fourchettes(0, texte, livrable)]


def test_le_prompt_systeme_et_ses_blocs_ne_montrent_aucune_plage() -> None:
    from generation.chapitres.runner import (
        _SYSTEME,
        COHERENCE_DES_CHIFFRES,
        PRIX_ET_MODELE_ECONOMIQUE,
        SOURCES_ET_TRACABILITE,
    )

    for nom, texte in (
        ("système", _SYSTEME), ("chiffres", COHERENCE_DES_CHIFFRES),
        ("sources", SOURCES_ET_TRACABILITE), ("prix", PRIX_ET_MODELE_ECONOMIQUE),
    ):
        assert _plages(texte, BP) == [], nom


@pytest.mark.parametrize("livrable", [BP, EC, STR])
def test_les_consignes_propres_au_livrable_ne_montrent_aucune_plage(livrable: str) -> None:
    from generation.chapitres.runner import _FORME_PAR_LIVRABLE
    from generation.prompts import _consigne_specifique_livrable

    assert _plages(_consigne_specifique_livrable(livrable), livrable) == []
    assert _plages(_FORME_PAR_LIVRABLE.get(livrable, ""), livrable) == []


def test_les_regles_du_socle_gardent_les_bornes_en_em_seulement() -> None:
    """Le `libelle` du socle repart dans chaque chapitre, à côté du chiffre.

    En BP / EC / STR, y recopier les bornes montrait la plage que le contrôle
    refuse ; en ÉTUDE DE MARCHÉ, les bornes disent la fiabilité de l'estimation
    et le chapitre 21 les demande (relecture du 14/09/2026, I6). On lit le
    prompt CONSTRUIT pour chaque livrable, pas la constante.
    """
    from generation.socle.prompt import _REGLES, construire_prompt_socle

    assert _plages(_REGLES, BP) == []
    variables = {"SECTEUR": "boulangerie", "PAYS": "France"}
    em = construire_prompt_socle(deliverable_type="market_study", variables=variables)
    bp = construire_prompt_socle(deliverable_type=BP, variables=variables)
    assert "Indique les deux bornes dans `libelle`" in str(em)
    assert "sans recopier les bornes" in str(bp)
    assert "Indique les deux bornes" not in str(bp)


def test_la_decision_tarifaire_str_n_appelle_plus_une_fourchette() -> None:
    from generation.checks_evangeline import DECISIONS_STRATEGIE

    libelles = [d.libelle for bloc in DECISIONS_STRATEGIE for d in bloc.decisions]
    assert not [x for x in libelles if "fourchette" in x.lower()]


def _fichiers(dossier: str) -> list[Any]:
    from generation.chapitres.configuration import RACINE_PROMPTS

    fichiers = sorted((RACINE_PROMPTS / dossier).glob("*.md"))
    assert fichiers, f"aucun prompt dans {dossier} : le test ne jugerait rien (règle 1)"
    return fichiers


@pytest.mark.parametrize(("dossier", "livrable"), [
    ("business_plan", BP), ("strategie_business", STR), ("etude_concurrence", EC),
])
def test_aucun_fichier_de_prompt_ne_montre_une_plage(dossier: str, livrable: str) -> None:
    from generation.chapitres.fichiers_prompts import _BANDEAU

    fautes = {
        f.name: _plages(_BANDEAU.sub("", f.read_text(encoding="utf-8")), livrable)
        for f in _fichiers(dossier)
    }
    assert {nom: p for nom, p in fautes.items() if p} == {}


def test_la_consigne_de_reecriture_ne_montre_pas_la_forme_refusee() -> None:
    """La seule consigne sur les fourchettes qui est PAYÉE (relecture, I4).

    Elle disait « écrire X à Y, médiane retenue Z » — la forme que le gate BP /
    STR refuse : la réécriture ne pouvait pas converger, et la fourchette
    « 60-75 € » de Zenitek est restée après deux passes.
    """
    from generation.correction import _CHECK_LABELS

    libelle = _CHECK_LABELS["fourchette_interdite"]
    assert "médiane retenue" not in libelle
    assert "seule valeur retenue" in libelle
    for livrable in (BP, STR):
        assert _plages(libelle, livrable) == []


def test_les_autres_sources_de_consigne_ne_montrent_aucune_plage() -> None:
    from generation.chapitres.runner import (
        CONSIGNE_DOCUMENTS_CHAPITRE,
        REGLES_DE_FOND,
        _forme_commune,
    )
    from generation.socle.prompt import CONSIGNE_DOCUMENTS_SOCLE, RELECTURE_DU_SOCLE

    for nom, texte in (
        ("fond", REGLES_DE_FOND), ("forme commune", _forme_commune()),
        ("documents (chapitre)", CONSIGNE_DOCUMENTS_CHAPITRE),
        ("documents (socle)", CONSIGNE_DOCUMENTS_SOCLE),
        ("relecture du socle", RELECTURE_DU_SOCLE),
    ):
        assert _plages(texte, BP) == [], nom


# ── Corpus re-mesuré après déploiement (14/09/2026) : 12 → 156 motifs ───────
#
# Lu dans les Word : la plupart étaient VRAIS — « Interventions de 60 à 75 €
# de l'heure » efface les trois prix du brief (60 € à distance, 65 € en
# atelier, 75 € à domicile). Restait une classe fausse : deux valeurs RELIÉES,
# pas une valeur hésitante.


@pytest.mark.parametrize("texte", [
    "Aucune justification du saut de 19 à 29 € par mois.",
    "Nombre d'abonnés ayant basculé de 19 à 29 €.",
    "Porter le chiffre d'affaires de 120 000 à 157 500 €.",
    "La confusion actuelle entre 19 et 29 euros persistera.",
    "L'écart entre 19 et 29 euros n'est pas justifié.",
])
def test_deux_valeurs_reliees_ne_sont_pas_une_plage(texte: str) -> None:
    assert detecter_fourchettes(9, texte, STR) == []


@pytest.mark.parametrize("texte", [
    "Interventions ponctuelles (60 à 75 € de l'heure).",
    "Trois paliers d'abonnement de 12 à 29 € par mois.",
    "Des frais de mise en service de 25 à 35 € sur toute nouvelle souscription.",
    "Une hausse de 3 à 5 % de la marge.",
    # CONTRE-ÉPREUVE du numéro d'étiquette : un nombre qui n'est pas un numéro.
    "Le palier 29 à 49 € par mois attire les indépendants.",
    "Pour l'offre 3 à 5 € par mois.",
])
def test_une_valeur_non_tranchee_reste_une_plage(texte: str) -> None:
    """CONTRE-ÉPREUVE : une plage qui efface des prix distincts, ou une grandeur hésitante."""
    assert detecter_fourchettes(9, texte, STR)


@pytest.mark.parametrize("livrable", [BP, EC, STR])
def test_la_consigne_interdit_de_resumer_des_prix_distincts_en_plage(livrable: str) -> None:
    """La cause des « 60 à 75 € de l'heure » : trois prix du brief résumés en une plage."""
    from generation.prompts import _consigne_specifique_livrable

    consigne = _consigne_specifique_livrable(livrable)
    assert "UN prix par variante" in consigne
    assert _plages(consigne, livrable) == []

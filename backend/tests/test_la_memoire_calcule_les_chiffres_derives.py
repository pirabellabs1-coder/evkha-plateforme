"""La mémoire de l'étude calcule les chiffres dérivés — le modèle ne les refait plus.

29/09/2026, business plan ÉCLORE (`cb59cede`) : 653 nombres sur 1 055 ne
venaient pas des données de référence ; le « revenu mensuel » (1 986,32 €)
était la CAF 2029 divisée par douze, écrit à côté d'un résultat net de
23 223,86 € ; la TVA était présentée « par choix » au-dessus du seuil.

Ce fichier verrouille le module de calcul (`generation.memoire`) :
1. les dérivés sont des IDENTITÉS, avec formule et définition, et ne se
   produisent pas quand un terme manque ;
2. le repère `{{identifiant}}` écrit la valeur au format français unique, et
   laisse visible un identifiant inconnu ;
3. les règles datées décident du régime de TVA et de la sortie du régime
   micro.
"""
from __future__ import annotations

from typing import Any

import pytest

from catalog.models import DeliverableType
from generation.memoire.faits import faits_de_l_etude
from generation.memoire.regles import Nature, depasse_le_plafond_micro, regime_de_tva
from generation.memoire.reperes import remplacer_les_reperes, reperes_cites, valeur_affichee
from generation.socle.prompt import construire_prompt_socle
from generation.socle.schema import Socle
from generation.socle.stub import socle_de_demonstration

BP = DeliverableType.BUSINESS_PLAN
BRIEF = {
    "SECTEUR": "ateliers bien-être", "PAYS": "France",
    "ZONE": "Île-de-France", "PROJET": "ÉCLORE",
}

#: Les séries réelles du prévisionnel d'ÉCLORE (réponse « Tableaux financiers »).
ECLORE = {
    "ca_previsionnel_an1": 24_852.0, "ca_previsionnel_an2": 51_132.5,
    "ca_previsionnel_an3": 97_060.0,
    "resultat_net_an1": 50.0, "resultat_net_an2": 8_040.11, "resultat_net_an3": 23_223.86,
    "caf_an1": 661.96, "caf_an2": 8_652.11, "caf_an3": 23_835.86,
}


def _socle(valeurs: dict[str, float] | None = None, retirer: tuple[str, ...] = ()) -> Socle:
    charge: dict[str, Any] = socle_de_demonstration(
        construire_prompt_socle(deliverable_type=BP, variables=BRIEF)
    )
    for donnee in charge["donnees"]:
        if valeurs and donnee["id"] in valeurs:
            donnee["valeur"], donnee["unite"] = valeurs[donnee["id"]], "EUR"
    charge["donnees"] = [d for d in charge["donnees"] if d["id"] not in retirer]
    return Socle.model_validate(charge)


# ── 1. Des identités, avec formule et définition ─────────────────────────────


def test_les_dotations_se_deduisent_de_la_caf_et_du_resultat() -> None:
    faits = faits_de_l_etude(_socle(ECLORE))
    assert faits["dotations_an3"].valeur == pytest.approx(612.0)
    assert faits["dotations_an3"].formule == "caf_an3 − resultat_net_an3"
    assert faits["dotations_an3"].origine == "calculee"


def test_le_mensuel_du_resultat_net_n_est_pas_celui_de_la_caf() -> None:
    """Le défaut d'ÉCLORE : 1 986,32 € était la CAF ÷ 12, pas le résultat net ÷ 12."""
    faits = faits_de_l_etude(_socle(ECLORE))
    assert faits["resultat_net_mensuel_an3"].valeur == pytest.approx(1_935.32)
    # La CAF n'a plus de moyenne mensuelle : elle était lue comme un revenu
    # mensuel (business plan ÉCLORE `28a257bf`, 30/09/2026).
    assert "caf_mensuel_an3" not in faits
    assert "PAS la CAF" in faits["resultat_net_an3"].definition
    assert "divisé par douze" in faits["resultat_net_mensuel_an3"].definition


def test_la_capacite_de_prelevement_est_la_caf_divisee_par_douze() -> None:
    """Dictionnaire d'indicateurs de la cliente (30/09/2026) : CAF ÷ 12, nommée sans ambiguïté.

    C'est un indicateur DISTINCT de la CAF mensuelle (qui, elle, n'existe pas :
    l'étiquette avait été lue comme le revenu de la dirigeante).
    """
    faits = faits_de_l_etude(_socle(ECLORE))
    assert faits["capacite_prelevement_mensuelle_an3"].valeur == pytest.approx(1_986.32, abs=0.01)
    assert faits["capacite_prelevement_mensuelle_an3"].formule == "caf_an3 ÷ 12"
    assert faits["capacite_prelevement_mensuelle_an3"].periode == "mois"
    definition = faits["capacite_prelevement_mensuelle_an3"].definition
    assert "ne se redivise pas" in definition and "ni le résultat" in definition
    assert "caf_mensuel_an3" not in faits, "toujours pas de « CAF mensuelle » ambiguë"


def test_les_evolutions_et_les_ecarts_sont_calcules_une_fois() -> None:
    faits = faits_de_l_etude(_socle(ECLORE))
    assert faits["ca_previsionnel_evolution_an1_an3"].valeur == pytest.approx(290.6)
    assert faits["ca_previsionnel_ecart_an1_an3"].valeur == pytest.approx(72_208.0)
    assert faits["ca_previsionnel_evolution_an1_an3"].unite == "%"


def test_un_stock_ne_se_mensualise_pas() -> None:
    faits = faits_de_l_etude(_socle(ECLORE))
    assert "tresorerie_fin_mensuel_an1" not in faits
    assert "dette_residuelle_mensuel_an1" not in faits


def test_un_derive_sans_terme_n_est_pas_produit() -> None:
    """Contre-épreuve : sans CAF, pas de dotations inventées."""
    faits = faits_de_l_etude(_socle(ECLORE, retirer=("caf_an3",)))
    assert "dotations_an3" not in faits
    assert "dotations_an2" in faits


def test_le_plan_de_financement_s_additionne() -> None:
    faits = faits_de_l_etude(_socle())
    attendu = sum(faits[i].valeur for i in ("apport", "emprunt", "autres_ressources"))
    assert faits["ressources_totales"].valeur == pytest.approx(attendu)
    assert faits["ecart_financement"].valeur == pytest.approx(
        attendu - faits["investissement_total"].valeur - faits["bfr"].valeur
    )


def test_le_calcul_est_deterministe_et_ne_touche_pas_au_socle() -> None:
    socle = _socle(ECLORE)
    avant = socle.model_dump()
    assert list(faits_de_l_etude(socle)) == list(faits_de_l_etude(socle))
    assert socle.model_dump() == avant


# ── 2. Les repères ───────────────────────────────────────────────────────────


def test_un_repere_ecrit_la_valeur_au_format_francais() -> None:
    faits = faits_de_l_etude(_socle(ECLORE))
    rendu = remplacer_les_reperes(
        "Résultat net {{resultat_net_an3}}, soit {{ resultat_net_mensuel_an3 }} par mois ; "
        "hausse de {{ca_previsionnel_evolution_an1_an3}}.",
        faits,
    )
    plat = rendu.texte.replace("\u00a0", " ")
    assert "23 223,86 €" in plat
    assert "1 935,32 €" in plat
    assert "290,6\u00a0%" in rendu.texte
    assert rendu.inconnus == []
    assert rendu.utilises == [
        "resultat_net_an3", "resultat_net_mensuel_an3", "ca_previsionnel_evolution_an1_an3",
    ]


def test_un_repere_inconnu_reste_visible_pour_le_controle() -> None:
    faits = faits_de_l_etude(_socle(ECLORE))
    rendu = remplacer_les_reperes("Revenu : {{revenu_invente}}.", faits)
    assert rendu.texte == "Revenu : {{revenu_invente}}."
    assert rendu.inconnus == ["revenu_invente"]
    assert reperes_cites("{{a_b}} et {{ c }}") == ["a_b", "c"]


def test_un_pourcentage_garde_une_decimale() -> None:
    faits = faits_de_l_etude(_socle(ECLORE))
    assert valeur_affichee(faits["marge_nette_an3"]) == "23,9\u00a0%"


# ── 3. Les règles datées ─────────────────────────────────────────────────────


def test_la_tva_est_obligatoire_au_dessus_du_seuil() -> None:
    """ÉCLORE 2028 : 51 132,5 € HT de prestations de services."""
    decision = regime_de_tva(51_132.5, 2028, Nature.SERVICES)
    assert decision is not None
    assert decision.valeur == "TVA obligatoire"
    assert "ce n'est pas un choix" in decision.justification


def test_la_franchise_reste_sous_le_seuil() -> None:
    decision = regime_de_tva(24_852.0, 2027, Nature.SERVICES)
    assert decision is not None and decision.valeur == "franchise en base"


def test_le_plafond_micro_est_signale() -> None:
    assert depasse_le_plafond_micro(97_060.0, 2029) is not None
    assert depasse_le_plafond_micro(51_132.5, 2028) is None


def test_une_annee_trop_ancienne_ne_rend_pas_un_seuil_faux() -> None:
    assert regime_de_tva(30_000.0, 2019) is None

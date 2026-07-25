"""Few-shot « etude de reference » (tache #13).

Ce que ces tests protegent, et pourquoi chacun existe :

1. LE CACHE. Le bloc fait ~1 600 tokens. Place apres SYSTEM_CACHE_BREAK ou
   rendu dependant du pays, il serait facture plein tarif sur les 30 appels
   d'un job (~0,13 EUR) au lieu d'etre mutualise entre jobs (~0,01 EUR). Deux
   tests verrouillent la position et l'invariance par pays.
2. LA CONTAMINATION. Le few-shot contient des chiffres reels d'un AUTRE
   secteur (79 141 avocats, 49,95 EUR/mois). Si l'interdiction de reprise
   passait apres les extraits, ou disparaissait, le modele pourrait injecter
   ces valeurs dans l'etude d'un client de la beaute au Benin.
3. LA PORTEE. Le manuel d'Evangeline ne couvre que l'EM ; BP/EC/STR attendent
   sa validation. Findrax est une EM : aucun de ses gestes ne doit fuir vers
   un dossier bancaire.
4. LA RECHUTE EN REGLES. `_RAPPEL_ANTI_RECHUTE_PIED` a ete supprime le 24/07
   parce que le modele recopiait ses formules dans le texte livre. Un test
   verifie que le few-shot ne reintroduit pas ces formulations.
"""

from __future__ import annotations

import pytest

from catalog.models import DeliverableType
from generation.prompt_library import (
    BUSINESS_PLAN_PROMPTS,
    COMPETITOR_STUDY_PROMPTS,
    MARKET_STUDY_PROMPTS,
)
from generation.prompts import build_system_prompt
from generation.reference_em import REFERENCE_EM, REFERENCE_SOM
from integrations.claude import SYSTEM_CACHE_BREAK

_MARQUEUR = "[ETUDE DE REFERENCE"


def _segments(deliverable_type: str, country: str = "", plan: str = "") -> tuple[str, str]:
    """Retourne (segment stable, segment propre au job)."""
    prompt = build_system_prompt(deliverable_type, country=country, plan=plan)
    if SYSTEM_CACHE_BREAK not in prompt:
        return prompt, ""
    stable, par_job = prompt.split(SYSTEM_CACHE_BREAK, 1)
    return stable, par_job


# --- 1. Placement dans le cache -------------------------------------------


def test_le_fewshot_est_dans_le_segment_cache_pas_dans_le_segment_par_job() -> None:
    stable, par_job = _segments(DeliverableType.MARKET_STUDY, country="Benin", plan="PLAN")

    assert _MARQUEUR in stable, "few-shot hors du prefixe cache : ~0,13 EUR/job de surcout"
    assert _MARQUEUR not in par_job


def test_le_segment_stable_em_est_identique_quel_que_soit_le_pays() -> None:
    # Le cache Anthropic est un prefixe STRICT : si le few-shot dependait du
    # pays ou du plan, chaque client paierait sa propre ecriture de cache.
    benin, _ = _segments(DeliverableType.MARKET_STUDY, country="Benin", plan="PLAN A")
    france, _ = _segments(DeliverableType.MARKET_STUDY, country="France", plan="PLAN B")

    assert benin == france


def test_le_fewshot_reste_dans_une_enveloppe_de_tokens_raisonnable() -> None:
    # Garde-fou anti-derive : un few-shot qui grossit sans fin finit par
    # diluer l'attention du modele et par ecraser la consigne du chapitre.
    # ~3,4 caracteres/token en francais.
    tokens_estimes = len(REFERENCE_EM) / 3.4
    assert 800 < tokens_estimes < 2200, f"{tokens_estimes:.0f} tokens estimes"


# --- 2. Garde-fou anti-contamination --------------------------------------


def test_l_interdiction_de_reprise_precede_les_extraits() -> None:
    # Ordre non cosmetique : le modele lit l'interdiction AVANT de rencontrer
    # les chiffres du secteur etranger.
    position_interdiction = REFERENCE_EM.index("INTERDICTION ABSOLUE")
    position_premier_extrait = REFERENCE_EM.index("--- EXTRAIT 1 ---")

    assert position_interdiction < position_premier_extrait


def test_l_interdiction_couvre_chiffres_noms_sources_et_secteur() -> None:
    debut = REFERENCE_EM[: REFERENCE_EM.index("--- EXTRAIT 1 ---")]

    for interdit in ("chiffre", "nom propre", "source", "taux", "prix", "sectoriel"):
        assert interdit in debut, f"« {interdit} » non couvert par l'interdiction"


def test_le_secteur_d_origine_est_nomme_avant_les_extraits() -> None:
    # Cacher la provenance rendrait la contamination plus probable, pas moins :
    # le modele doit savoir que « plateforme juridique / France » n'est pas son
    # dossier.
    debut = REFERENCE_EM[: REFERENCE_EM.index("--- EXTRAIT 1 ---")]

    assert "JURIDIQUE" in debut.upper()
    assert "FRANCE" in debut.upper()
    assert "ETRANGER" in debut.upper()


def test_l_interdiction_est_rappelee_apres_les_extraits() -> None:
    fin = REFERENCE_EM[REFERENCE_EM.index("--- EXTRAIT 4 ---") :]

    assert "n'appartiennent pas au dossier" in fin


@pytest.mark.parametrize(
    "chiffre_findrax",
    ["79 141", "11,4 %", "49,95", "5 000 et 8 000", "3,5 a 11,8"],
)
def test_les_chiffres_findrax_ne_sortent_jamais_du_bloc_de_reference(
    chiffre_findrax: str,
) -> None:
    # Ils sont legitimes DANS l'extrait cite, encadres par l'interdiction de
    # reprise. Partout ailleurs, une valeur d'un autre dossier promue en
    # consigne serait recopiee telle quelle dans l'etude du client.
    systeme = build_system_prompt(DeliverableType.MARKET_STUDY, country="Benin", plan="PLAN")
    hors_reference = systeme.replace(REFERENCE_EM, "")
    assert chiffre_findrax not in hors_reference, "fuite dans le system prompt EM"

    for cle, prompt in MARKET_STUDY_PROMPTS.items():
        hors_reference = prompt.replace(REFERENCE_SOM, "")
        assert chiffre_findrax not in hors_reference, f"{chiffre_findrax} fuit dans {cle}"


# --- 3. Portee : EM uniquement --------------------------------------------


@pytest.mark.parametrize(
    "deliverable_type",
    [
        DeliverableType.BUSINESS_PLAN,
        DeliverableType.COMPETITOR_STUDY,
        DeliverableType.BUSINESS_STRATEGY,
    ],
)
def test_le_fewshot_em_n_atteint_aucun_autre_livrable(deliverable_type: str) -> None:
    prompt = build_system_prompt(deliverable_type, country="France")

    assert _MARQUEUR not in prompt
    assert "Findrax" not in prompt


def test_le_fewshot_est_bien_present_pour_l_em() -> None:
    prompt = build_system_prompt(DeliverableType.MARKET_STUDY)

    assert _MARQUEUR in prompt


# --- 4. Les quatre gestes sont explicitement nommes -----------------------


def test_les_quatre_extraits_nomment_chacun_leur_mecanique() -> None:
    # Un extrait sans mecanique nommee, c'est un pastiche : le modele imite le
    # style sans savoir ce qu'on lui demande de reproduire.
    assert REFERENCE_EM.count("MECANIQUE A IMITER") == 4
    for numero in (1, 2, 3, 4):
        assert f"--- EXTRAIT {numero} ---" in REFERENCE_EM


def test_les_quatre_defauts_de_waome_sont_chacun_couverts() -> None:
    # Les quatre reproches d'Evangeline sur WAOME v4, dans l'ordre du bloc.
    assert "annonce le CONSTAT, pas le theme" in REFERENCE_EM       # sous-titres
    assert "consequence nommee pour le projet" in REFERENCE_EM      # constat sec
    assert "ASSUME et explique" in REFERENCE_EM                     # ratio maquille
    assert "se citent explicitement, par leur" in REFERENCE_EM      # 21 fiches


def test_le_fewshot_ne_reintroduit_pas_les_formules_regurgitees() -> None:
    # `_RAPPEL_ANTI_RECHUTE_PIED` (supprime le 24/07/2026) faisait recopier ces
    # tournures dans le texte livre. Elles ne doivent pas revenir par le
    # few-shot.
    tournures = (
        "mediane retenue",
        "borne conservatrice",
        "estimation construite par croisement",
    )
    for tournure in tournures:
        assert tournure not in REFERENCE_EM


# --- 5. Exemplaire SOM : chapitre 2 uniquement ----------------------------


def test_l_exemplaire_som_est_dans_la_consigne_du_chapitre_2() -> None:
    prompt = MARKET_STUDY_PROMPTS["em.02.marche_national_local"]

    assert REFERENCE_SOM in prompt


def test_l_exemplaire_som_ne_pollue_aucun_autre_chapitre() -> None:
    # Il est injecte dans le prompt UTILISATEUR, non cache : le mettre partout
    # se paierait 21 fois, et les 20 autres chapitres ne calculent pas de SOM.
    for cle, prompt in MARKET_STUDY_PROMPTS.items():
        if cle == "em.02.marche_national_local":
            continue
        assert "sept variables" not in prompt, f"exemplaire SOM fuit dans {cle}"


def test_l_exemplaire_som_ne_fuit_pas_vers_le_bp_ni_l_ec() -> None:
    for prompts in (BUSINESS_PLAN_PROMPTS, COMPETITOR_STUDY_PROMPTS):
        for cle, prompt in prompts.items():
            assert "sept variables" not in prompt, f"exemplaire SOM fuit dans {cle}"


def test_l_exemplaire_som_pose_la_formule_et_les_six_gestes() -> None:
    # Le defaut central du run 010e3bf2 : le SOM etait un resultat sans ses
    # variables, donc invérifiable et indiscutable.
    assert "POSE la formule en clair" in REFERENCE_SOM
    assert "(consultations x (1 - taux" in REFERENCE_SOM
    # La distinction actifs / inscrits est LA variable la plus sensible.
    assert "ACTIFS et non" in REFERENCE_SOM
    assert "INSCRITS" in REFERENCE_SOM
    for numero in range(1, 7):
        assert f"{numero}. " in REFERENCE_SOM


def test_l_exemplaire_som_porte_aussi_son_interdiction_de_reprise() -> None:
    # Injecte hors du system prompt, il ne beneficie pas du garde-fou global :
    # il doit porter le sien.
    assert "ne reprends ni ses chiffres" in REFERENCE_SOM
    assert "ETRANGER" in REFERENCE_SOM


# --- 6. Non-regression : le reste du prompt EM survit ---------------------


def test_la_charte_et_le_role_em_restent_dans_le_prefixe_stable() -> None:
    stable, _ = _segments(DeliverableType.MARKET_STUDY, country="Benin", plan="PLAN")

    assert "VOIX EVKHA" in stable
    assert "analyste senior en etude de marche" in stable
    # Ordre voulu : la charte (le manuel) precede le few-shot (l'illustration).
    assert stable.index("VOIX EVKHA") < stable.index(_MARQUEUR)


def test_les_regles_de_calcul_du_chapitre_2_precedent_l_exemplaire() -> None:
    # Les regles disent quoi faire, l'exemplaire montre a quoi ca ressemble.
    prompt = MARKET_STUDY_PROMPTS["em.02.marche_national_local"]

    assert prompt.index("REGLES DE CALCUL") < prompt.index(REFERENCE_SOM)

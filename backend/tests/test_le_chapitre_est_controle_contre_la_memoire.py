"""Chaque chapitre est contrôlé contre la mémoire de l'étude avant d'être validé.

29/09/2026, business plan ÉCLORE (`cb59cede`) : le contrôleur global relisait
tout à la fin, sans référence complète. Ce fichier verrouille le contrôle
CHAPITRE PAR CHAPITRE (`generation.memoire.controle`) sur les défauts réels :
chiffres calculés par le modèle, TVA « par choix », « 13 acteurs » contre 11,
« taux » en euros, repère inconnu — et le repli qui garantit qu'un chapitre est
toujours validé.
"""
from __future__ import annotations

from typing import Any

from catalog.models import DeliverableType
from generation.memoire.controle import (
    appliquer_les_reperes,
    controler_le_chapitre,
    replis_de_derniere_tentative,
)
from generation.memoire.etude import MemoireEtude
from generation.socle.prompt import construire_prompt_socle
from generation.socle.schema import Socle
from generation.socle.stub import socle_de_demonstration

BP = DeliverableType.BUSINESS_PLAN
VARIABLES: dict[str, object] = {
    "SECTEUR": "Ateliers. Il s'agit d'une prestation de services commerciale.",
    "PAYS": "France", "ZONE": "Île-de-France", "PROJET": "Projet test",
    "DATE_CREATION": "Trajectoire juridique : micro-entreprise de 2027 à 2029.",
}
ECLORE = {
    "ca_previsionnel_an1": 24_852.0, "ca_previsionnel_an2": 51_132.5,
    "ca_previsionnel_an3": 97_060.0,
    "resultat_net_an3": 23_223.86, "caf_an3": 23_835.86,
}


def _memoire() -> MemoireEtude:
    charge: dict[str, Any] = socle_de_demonstration(
        construire_prompt_socle(deliverable_type=BP, variables={
            "SECTEUR": "ateliers", "PAYS": "France", "ZONE": "IDF", "PROJET": "Projet test",
        })
    )
    for donnee in charge["donnees"]:
        if donnee["id"] in ECLORE:
            donnee["valeur"], donnee["unite"] = ECLORE[donnee["id"]], "EUR"
            if donnee["id"].startswith("ca_previsionnel_an"):
                donnee["annee"] = 2026 + int(donnee["id"][-1])
    return MemoireEtude.construire(Socle.model_validate(charge), VARIABLES)


def _chapitre(*paragraphes: str) -> dict[str, Any]:
    return {"titre": "Test", "sections": [{"titre": "S", "paragraphes": list(paragraphes)}]}


def test_un_chapitre_qui_cite_ses_reperes_passe() -> None:
    controle = controler_le_chapitre(
        _chapitre("Le résultat net atteint {{resultat_net_an3}} en 2029, soit "
                  "{{resultat_net_mensuel_an3}} par mois."),
        _memoire(),
    )
    assert controle.motifs == []
    assert controle.reperes_utilises == ["resultat_net_an3", "resultat_net_mensuel_an3"]
    assert controle.verifie, "un contrôle dit toujours ce qu'il a examiné"


def test_un_chiffre_calcule_par_le_modele_est_refuse() -> None:
    """« 8 576,08 € » : un dérivé écrit en clair, ni fait ni réponse du client."""
    controle = controler_le_chapitre(
        _chapitre("L'écart atteint 8 576,08 € sur la période."), _memoire()
    )
    assert any("8 576,08 €" in m for m in controle.motifs)


def test_un_chiffre_juste_ecrit_en_clair_passe() -> None:
    """Contre-épreuve : la valeur exacte d'un fait, recopiée, n'est pas une invention."""
    controle = controler_le_chapitre(
        _chapitre("Le chiffre d'affaires 2028 est de 51 132,5 €."), _memoire()
    )
    assert controle.motifs == []


def test_une_reponse_du_client_ecrite_en_clair_passe() -> None:
    controle = controler_le_chapitre(
        _chapitre("La soirée est vendue 39 € par participante."), _memoire(),
        nombres_du_client=[39.0],
    )
    assert controle.motifs == []


def test_la_tva_par_choix_au_dessus_du_seuil_est_refusee() -> None:
    controle = controler_le_chapitre(
        _chapitre("Franchise conservée en 2027 ; TVA appliquée par choix prudent dès 2028."),
        _memoire(),
    )
    assert any("OBLIGATOIRE" in m and "2028" in m for m in controle.motifs)


def test_un_autre_compte_de_concurrents_est_refuse_sauf_attribue_au_client() -> None:
    memoire = _memoire()
    faux = controler_le_chapitre(_chapitre("L'étude a analysé 13 acteurs du marché."), memoire)
    assert any("13 acteurs" in m for m in faux.motifs)
    attribue = controler_le_chapitre(
        _chapitre("Votre propre étude de la concurrence recensait 13 acteurs."), memoire
    )
    assert not [m for m in attribue.motifs if "acteurs" in m]


def test_un_taux_en_euros_est_refuse() -> None:
    controle = controler_le_chapitre(
        _chapitre("Le taux de capture atteint 0,05 € par habitante."), _memoire()
    )
    assert any("un taux s'exprime en %" in m for m in controle.motifs)


def test_un_repere_inconnu_est_refuse_puis_retire_au_dernier_essai() -> None:
    memoire = _memoire()
    chapitre = _chapitre(
        "Le revenu atteint {{revenu_invente}}. Le résultat net vaut {{resultat_net_an3}}."
    )
    controle = controler_le_chapitre(chapitre, memoire)
    assert any("revenu_invente" in m for m in controle.motifs)

    replie = replis_de_derniere_tentative(chapitre, memoire.faits)
    rendu, _, inconnus = appliquer_les_reperes(replie, memoire.faits)
    texte = rendu["sections"][0]["paragraphes"][0]
    assert inconnus == []
    assert "revenu" not in texte and "23 223,86" in texte.replace("\u00a0", " ")


def test_les_reperes_sont_remplaces_partout_dans_le_chapitre() -> None:
    memoire = _memoire()
    chapitre = {
        "sections": [{"paragraphes": ["CA {{ca_previsionnel_an1}}"]}],
        "tableaux": [{"entetes": ["Année", "CA"], "lignes": [["2027", "{{ca_previsionnel_an1}}"]]}],
        "graphiques": [{"donnees_ids": ["ca_previsionnel_an1"]}],
    }
    rendu, utilises, inconnus = appliquer_les_reperes(chapitre, memoire.faits)
    assert rendu["tableaux"][0]["lignes"][0][1].replace("\u00a0", " ") == "24 852 €"
    assert rendu["graphiques"][0]["donnees_ids"] == ["ca_previsionnel_an1"]
    assert utilises == ["ca_previsionnel_an1", "ca_previsionnel_an1"] and inconnus == []

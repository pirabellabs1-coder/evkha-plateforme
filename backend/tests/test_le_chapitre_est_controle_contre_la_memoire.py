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


def test_un_chiffre_calcule_par_le_modele_est_signale_sans_faire_reprendre() -> None:
    """« 8 576,08 € » : un dérivé écrit en clair — SIGNALÉ, pas un motif de reprise.

    Épreuve réelle du 29/09/2026 (`bf98827c`) : faire reprendre chaque chapitre
    pour ses chiffres en clair a épuisé le plafond de 8 € au chapitre 16.
    """
    controle = controler_le_chapitre(
        _chapitre("L'écart atteint 8 576,08 € sur la période."), _memoire()
    )
    assert any("8 576,08 €" in m for m in controle.signaux)
    assert controle.motifs == []


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


def test_le_repli_retire_un_paragraphe_vide_sans_casser_le_chapitre() -> None:
    """Une phrase retirée était la seule du paragraphe : le bloc part avec elle."""
    memoire = _memoire()
    chapitre = {"blocs": [
        {"type": "paragraphe", "texte": "Le revenu vaut {{revenu_invente}}"},
        {"type": "paragraphe", "texte": "Le CA vaut {{ca_previsionnel_an1}}."},
        {"type": "tableau", "tableau": {"lignes": [["A", "{{revenu_invente}}"]]}},
    ]}
    replie = replis_de_derniere_tentative(chapitre, memoire.faits)
    assert [b["type"] for b in replie["blocs"]] == ["paragraphe", "tableau"]
    assert replie["blocs"][1]["tableau"]["lignes"] == [["A", "—"]]



# ── Séries, dates, renvois (ÉCLORE : défauts n° 1, 5 et 7) ───────────────────


def _memoire_avec_calendrier() -> MemoireEtude:
    memoire = _memoire()
    variables = {**VARIABLES, "EQUIPE": "2029 : à temps plein, après avoir quitté son poste."}
    return MemoireEtude(
        faits=memoire.faits,
        decisions=MemoireEtude.construire(
            _socle_de(memoire), variables
        ).decisions,
    )


def _socle_de(memoire: MemoireEtude) -> Any:
    charge: dict[str, Any] = socle_de_demonstration(
        construire_prompt_socle(deliverable_type=BP, variables={
            "SECTEUR": "ateliers", "PAYS": "France", "ZONE": "IDF", "PROJET": "Projet test",
        })
    )
    return Socle.model_validate(charge)


def test_une_valeur_d_une_autre_serie_est_refusee() -> None:
    """« Résultat net de 23 835,86 € » : c'est la CAF 2029 d'ÉCLORE."""
    controle = controler_le_chapitre(
        _chapitre("Le résultat net atteint 23 835,86 € en 2029."), _memoire()
    )
    assert any("capacit" not in m and "caf" in m.lower() for m in controle.motifs)


def test_la_bonne_serie_passe() -> None:
    """Contre-épreuve : la CAF nommée CAF, le résultat net nommé résultat net."""
    memoire = _memoire()
    for phrase in ("La CAF atteint 23 835,86 € en 2029.",
                   "Le résultat net atteint 23 223,86 € en 2029."):
        assert controler_le_chapitre(_chapitre(phrase), memoire).motifs == []


def test_une_date_qui_contredit_le_client_est_refusee() -> None:
    memoire = _memoire_avec_calendrier()
    faux = controler_le_chapitre(_chapitre("Carine quitte son poste en 2028."), memoire)
    assert any("2028" in m and "2029" in m for m in faux.motifs)
    juste = controler_le_chapitre(_chapitre("Carine quitte son poste en 2029."), memoire)
    assert juste.motifs == []


def test_un_renvoi_vers_un_chapitre_absent_est_refuse() -> None:
    plan = range(0, 22)
    faux = controler_le_chapitre(
        _chapitre("Voir le chapitre 23 pour le détail."), _memoire(), chapitres_du_plan=plan
    )
    assert any("chapitre 23" in m for m in faux.motifs)
    juste = controler_le_chapitre(
        _chapitre("Voir le chapitre 13 pour le détail."), _memoire(), chapitres_du_plan=plan
    )
    assert juste.motifs == []


def test_l_annee_d_un_autre_evenement_ne_date_pas_le_depart() -> None:
    """Faux positif mesuré sur ÉCLORE : 2027 date le pilote, pas le départ."""
    memoire = _memoire_avec_calendrier()
    phrase = (
        "Chaque année porte son jalon, du pilote de janvier 2027 jusqu'à la bascule "
        "où elle passe à temps plein."
    )
    assert controler_le_chapitre(_chapitre(phrase), memoire).motifs == []


def test_une_annee_de_l_autre_borne_ne_date_pas_l_evenement() -> None:
    """ÉCLORE : « du pilote de janvier 2027 au passage en société »."""
    memoire = _memoire_avec_calendrier()
    phrase = "Le plan court du pilote de janvier 2027 au passage à temps plein."
    assert controler_le_chapitre(_chapitre(phrase), memoire).motifs == []



# ── Tableaux : un compte de résultat qui ne boucle pas (ÉCLORE, défaut n° 3) ──


def _compte(ca: str, charges: str, ebe: str, dot: str, rn: str, caf: str) -> dict[str, Any]:
    return {"blocs": [{"type": "tableau", "tableau": {
        "entetes": ["Poste", "2028"],
        "lignes": [
            ["Chiffre d'affaires", ca], ["Total des charges", charges], ["EBE", ebe],
            ["Dotations aux amortissements", dot], ["Résultat net", rn],
            ["Capacité d'autofinancement", caf],
        ],
    }}]}


def test_un_compte_de_resultat_qui_ne_boucle_pas_est_refuse() -> None:
    controle = controler_le_chapitre(
        _compte("51 132 €", "42 000 €", "9 132 €", "612 €", "8 040 €", "9 500 €"), _memoire()
    )
    assert any("CAF" in m and "ne boucle pas" in m for m in controle.motifs)


def test_un_ebe_faux_est_refuse() -> None:
    controle = controler_le_chapitre(
        _compte("51 132 €", "42 000 €", "12 000 €", "612 €", "11 388 €", "12 000 €"), _memoire()
    )
    assert any("EBE" in m and "ne boucle pas" in m for m in controle.motifs)


def test_un_compte_de_resultat_juste_passe() -> None:
    """Contre-épreuve : 51 132 − 42 000 = 9 132 ; 8 040 + 612 = 8 652."""
    controle = controler_le_chapitre(
        _compte("51 132 €", "42 000 €", "9 132 €", "612 €", "8 040 €", "8 652 €"), _memoire()
    )
    assert not [m for m in controle.motifs if "ne boucle pas" in m]


def test_un_tableau_en_reperes_n_est_pas_recalcule() -> None:
    """Des repères bouclent par construction : rien à refaire."""
    controle = controler_le_chapitre(
        _compte("{{ca_previsionnel_an2}}", "42 000 €", "9 132 €", "612 €",
                "{{resultat_net_an2}}", "{{caf_an2}}"), _memoire(),
    )
    assert not [m for m in controle.motifs if "ne boucle pas" in m]

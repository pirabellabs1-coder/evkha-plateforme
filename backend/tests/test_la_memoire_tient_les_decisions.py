"""La mémoire de l'étude tient les décisions : règles, compte de la base, phrases du client.

29/09/2026, business plan ÉCLORE (`cb59cede`) : un même départ daté de cinq
façons, « 13 acteurs » contre 11 dans notre base, la TVA « par choix » au-dessus
du seuil. Les chapitres ne recevaient aucune décision, seulement le brief brut.

Les phrases de brief ci-dessous reprennent la FORME du brief réel, sans ses
données (règle de confidentialité, décision D7 du diagnostic).
"""
from __future__ import annotations

from typing import Any

from catalog.models import DeliverableType
from generation.memoire.decisions import decisions_de_l_etude, nature_de_l_activite
from generation.memoire.etude import MemoireEtude
from generation.memoire.faits import faits_de_l_etude
from generation.memoire.regles import Nature
from generation.socle.prompt import construire_prompt_socle
from generation.socle.schema import Socle
from generation.socle.stub import socle_de_demonstration

BP = DeliverableType.BUSINESS_PLAN
VARIABLES: dict[str, object] = {
    "SECTEUR": "Ateliers en petit groupe. Il s'agit d'une prestation de services commerciale.",
    "PAYS": "France",
    "ZONE": "Île-de-France",
    "PROJET": "Projet test",
    "DATE_CREATION": (
        "Création : immatriculation en micro-entreprise (BIC, prestations de services, "
        "franchise de TVA) prévue fin 2026, pour un atelier pilote en janvier 2027. "
        "Trajectoire juridique : micro-entreprise de 2027 à 2029, puis passage en société "
        "fin 2029."
    ),
    "EQUIPE": "2027-2028 : en parallèle de son emploi salarié. 2029 : à temps plein, "
              "après avoir quitté son poste.",
}


def _socle(ca: tuple[float, float, float] = (24_852.0, 51_132.5, 97_060.0)) -> Socle:
    charge: dict[str, Any] = socle_de_demonstration(
        construire_prompt_socle(deliverable_type=BP, variables={
            "SECTEUR": "ateliers", "PAYS": "France", "ZONE": "IDF", "PROJET": "Projet test",
        })
    )
    for donnee in charge["donnees"]:
        for rang, valeur in enumerate(ca, start=1):
            if donnee["id"] == f"ca_previsionnel_an{rang}":
                donnee["valeur"], donnee["unite"], donnee["annee"] = valeur, "EUR", 2026 + rang
    return Socle.model_validate(charge)


def _decisions() -> list[Any]:
    socle = _socle()
    return decisions_de_l_etude(socle, VARIABLES, faits_de_l_etude(socle))


def test_la_tva_de_chaque_exercice_est_decidee_par_la_regle() -> None:
    tva = {d.annee: d.valeur for d in _decisions() if d.sujet == "regime_tva"}
    assert tva == {2027: "franchise en base", 2028: "TVA obligatoire", 2029: "TVA obligatoire"}


def test_la_sortie_du_regime_micro_est_signalee() -> None:
    sorties = [d for d in _decisions() if d.sujet == "sortie_micro"]
    assert [d.annee for d in sorties] == [2029]


def test_le_nombre_de_concurrents_est_celui_de_la_base() -> None:
    (concurrents,) = [d for d in _decisions() if d.sujet == "concurrents"]
    socle = _socle()
    # L'entreprise du dossier figure dans la base (type « projet ») : ce n'est
    # pas un concurrent, elle ne se compte pas.
    analyses = [a for a in socle.concurrents if a.type in ("direct", "indirect")]
    assert len(analyses) < len(socle.concurrents), "la doublure n'a plus d'acteur « projet »"
    assert concurrents.valeur.startswith(f"{len(analyses)} concurrents analysés")
    assert "s'attribue au client" in concurrents.justification


def test_les_phrases_de_calendrier_et_de_statut_sont_reprises_mot_pour_mot() -> None:
    du_brief = [d for d in _decisions() if d.source == "brief"]
    textes = [d.valeur for d in du_brief]
    trajectoire = "Trajectoire juridique : micro-entreprise de 2027 à 2029"
    assert any(t.startswith(trajectoire) for t in textes)
    assert any("après avoir quitté son poste" in t for t in textes)
    # La MÉMOIRE garde la phrase mot pour mot ; elle ne dit plus au rédacteur
    # de la recopier (30/09/2026 : une ligne du brief imprimée seule, et
    # l'étiquette « phrase du client » imprimée dans une cellule). Ni consigne
    # de recopie, ni clé de variable dans ce que le rédacteur lit.
    assert du_brief
    for decision in du_brief:
        assert "telle quelle" not in decision.justification
        assert "client" not in decision.justification
        assert not any(cle in decision.justification for cle in VARIABLES)


def test_la_nature_de_l_activite_suit_le_brief() -> None:
    assert nature_de_l_activite(VARIABLES) is Nature.SERVICES
    assert nature_de_l_activite({"OFFRE": "Vente de marchandises en ligne"}) is Nature.VENTES


def test_sans_micro_pas_de_sortie_du_regime() -> None:
    """Contre-épreuve : une société n'a pas de plafond micro à franchir."""
    socle = _socle()
    variables = {**VARIABLES, "DATE_CREATION": "Création d'une SAS en 2027."}
    decisions = decisions_de_l_etude(socle, variables, faits_de_l_etude(socle))
    assert not [d for d in decisions if d.sujet == "sortie_micro"]


def test_le_redacteur_recoit_les_reperes_et_les_decisions() -> None:
    memoire = MemoireEtude.construire(_socle(), VARIABLES)
    bloc = memoire.bloc_pour_le_redacteur()
    assert "{{ca_previsionnel_an2}}" in bloc
    assert "{{resultat_net_mensuel_an3}}" in bloc
    assert "N'effectue AUCUN calcul toi-même" in bloc
    assert "TVA obligatoire" in bloc
    # La décision se tient ; la phrase se rédige (30/09/2026, voir `decisions`).
    assert "ne se contredisent jamais" in bloc
    assert "aucune ligne de cette liste ne se recopie" in bloc
    assert "telles quelles" not in bloc


def test_la_memoire_se_stocke_en_json() -> None:
    import json

    dump = MemoireEtude.construire(_socle(), VARIABLES).en_dict()
    relu = json.loads(json.dumps(dump, ensure_ascii=False))
    assert relu["faits"]["ca_previsionnel_an1"]["origine"]
    assert {d["source"] for d in relu["decisions"]} >= {"regle", "socle", "brief"}

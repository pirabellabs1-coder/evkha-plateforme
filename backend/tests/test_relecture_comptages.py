"""Relecture, classe 6 : comptages faux et décisions écrites de deux façons.

30/09/2026, business plan ÉCLORE `28a257bf`. La cliente : « Toute phrase "N sur
M", "N concurrents", "N formats", "N familles", "N leviers" est vérifiée contre
la mémoire ou contre le tableau voisin. » Et une même décision (une date, un
statut, un moment de paiement, la règle de TVA) ne s'écrit que d'une façon.

Les textes, noms et chiffres ci-dessous sont FICTIFS (règle de
confidentialité) ; seuls les seuils légaux de TVA sont réels, parce que la règle
est celle de la loi (`memoire.regles.FRANCHISE_TVA`). Chaque test échoue sur le
code d'avant, où le contrôle rendait une liste vide ; chaque classe a sa
contre-épreuve.
"""
from __future__ import annotations

from typing import Any

import pytest

from generation.chapitres.schema import ChapitrePayload
from generation.memoire.decisions import JUSTIFICATION_DU_BRIEF
from generation.memoire.etude import MemoireEtude
from generation.memoire.regles import Decision
from generation.relecture import Document, Reference, Section, Tableau, comptages, relire
from generation.relecture.document import document_du_chapitre

#: La base de comparaison, telle que la mémoire la formule (`decisions`).
#: `test_la_base_se_lit_dans_la_vraie_memoire` vérifie que cette forme est bien
#: celle que la mémoire écrit.
_BASE = Decision(
    "concurrents", "13 concurrents analysés (9 directs, 4 indirects)", None,
    "compte de la base de référence", source="socle",
)


def _reference(*decisions: Decision) -> Reference:
    return Reference(memoire=MemoireEtude(faits={}, decisions=[_BASE, *decisions]))


def _section(numero: str, titre: str, *paragraphes: str, tableaux: Any = ()) -> Section:
    chapitre = int(numero.replace("ch. ", "").split(".")[0])
    return Section(numero=numero, titre=titre, chapitre=chapitre,
                   paragraphes=list(paragraphes), tableaux=list(tableaux))


def _constats(sections: list[Section], reference: Reference | None = None,
              classe: str | None = None) -> list[Any]:
    constats = comptages.controler(Document(sections=sections), reference or _reference())
    return [c for c in constats if classe is None or c.classe == classe]


# ── 1. « N sur M » contre la base de la mémoire ─────────────────────────────


def test_un_panel_sur_une_autre_base_est_faux() -> None:
    """« sept concurrents directs sur douze » quand la base en compte neuf."""
    constats = _constats([_section(
        "10.2", "Politique de prix",
        "Chaque prestation a un prix ferme — à l'inverse de sept concurrents directs sur "
        "douze qui restent sur devis.",
    )])
    assert [c.section for c in constats] == ["10.2"]
    assert "sur douze" in constats[0].detail and "9 directs" in constats[0].detail


@pytest.mark.parametrize("texte", [
    "Cinq concurrents directs sur neuf publient un prix ferme.",
    "Sur treize acteurs analysés, aucun ne propose de format court.",
    "Aucun des 9 concurrents directs n'atteint la note maximale.",
    # Une statistique de marché n'est pas le panel : ni « directs », ni « panel ».
    "Trois acteurs sur quatre du secteur vendent en ligne, selon la fédération.",
    "D'après la fédération, 300 acteurs sur 2 500 vendent en ligne.",
    # Des PARTIES du panel, pas la population entière (revue du 30/09/2026).
    "Surveiller les deux concurrents directs les plus proches sur la grille.",
    "L'un des deux concurrents directs implantés en centre-ville publie ses prix.",
    "Parmi les trois concurrents directs les plus proches, aucun n'ouvre le dimanche.",
    # Le marché, puis le panel : la phrase les distingue elle-même.
    "La zone compte 23 concurrents directs, dont 9 analysés dans la grille.",
])
def test_contre_epreuve_les_comptes_de_la_base_passent(texte: str) -> None:
    assert _constats([_section("7.1", "Concurrence", texte)]) == []


def test_la_population_entiere_a_le_compte_de_la_base() -> None:
    """« les 12 concurrents directs analysés » : la base en compte neuf."""
    constats = _constats([_section(
        "7.1", "Concurrence", "La grille couvre les 12 concurrents directs analysés.",
    )])
    assert [c.section for c in constats] == ["7.1"]
    assert "9 directs" in constats[0].detail


def test_la_base_se_lit_dans_la_vraie_memoire() -> None:
    """La base est relue dans la phrase que la mémoire ÉCRIT (`decisions_de_l_etude`).

    Si cette phrase change de forme, les comptes cesseraient d'être jugés en
    silence (règle 1) : ce test tombe avant.
    """
    from catalog.models import DeliverableType
    from generation.socle.prompt import construire_prompt_socle
    from generation.socle.schema import Socle
    from generation.socle.stub import socle_de_demonstration

    variables = {"SECTEUR": "ateliers", "PAYS": "France", "ZONE": "IDF", "PROJET": "Test"}
    socle = Socle.model_validate(socle_de_demonstration(construire_prompt_socle(
        deliverable_type=DeliverableType.BUSINESS_PLAN, variables=variables,
    )))
    directs = sum(1 for a in socle.concurrents if a.type == "direct")
    assert directs, "la doublure n'a plus de concurrent direct : le test ne jugerait rien"
    reference = Reference(memoire=MemoireEtude.construire(socle, variables))
    base = comptages._base(reference)
    assert base is not None and base.directs == directs
    faux = directs + 3
    constats = _constats([_section(
        "7.1", "Concurrence", f"Quatre concurrents directs sur {faux} publient un prix ferme.",
    )], reference)
    assert [c.section for c in constats] == ["7.1"]


def _grille() -> Tableau:
    return Tableau(
        entetes=("Acteur", "Accessibilité", "Accueil des personnes seules", "Offre combinée"),
        lignes=(
            ("Alpha", "3/5", "4/5", "4/5"),
            ("Bêta", "5/5", "2/5", "3/5"),
            ("Gamma", "4/5", "3/5", "3/5"),
            ("Delta", "2/5", "4/5", "2/5"),
            ("NOVA (positionnement visé)", "3/5", "4/5", "5/5"),
        ),
    )


_BASE_QUATRE = Decision(
    "concurrents", "6 concurrents analysés (4 directs, 2 indirects)", None, "base",
    source="socle",
)


def test_un_compte_que_la_grille_dement_est_faux() -> None:
    """Tous sont sous le niveau visé sur l'offre combinée : « trois sur quatre » est faux."""
    sections = [
        _section("5.1", "La grille", tableaux=[_grille()]),
        _section("5.2", "Ce que cela signifie",
                 "Trois concurrents directs sur quatre restent en dessous du niveau visé "
                 "sur l'accueil des personnes seules ou sur l'offre combinée."),
    ]
    reference = Reference(memoire=MemoireEtude(faits={}, decisions=[_BASE_QUATRE]))
    constats = _constats(sections, reference)
    assert [c.section for c in constats] == ["5.2"]
    assert "4 sur 4" in constats[0].detail and "(5.1)" in constats[0].detail


def test_contre_epreuve_le_compte_juste_de_la_grille_passe() -> None:
    """Sur l'accueil seul, deux sont en dessous (Bêta, Gamma) : « deux sur quatre » tient."""
    sections = [
        _section("5.1", "La grille", tableaux=[_grille()]),
        _section("5.2", "Ce que cela signifie",
                 "Deux concurrents directs sur quatre restent en dessous du niveau visé "
                 "sur l'accueil des personnes seules."),
    ]
    reference = Reference(memoire=MemoireEtude(faits={}, decisions=[_BASE_QUATRE]))
    assert _constats(sections, reference) == []


# ── 2. Une proportion qui contredit le compte écrit ailleurs ─────────────────


def _prix_fermes(proportion: str) -> list[Section]:
    return [
        _section("7.4", "Prix du panel", "Six concurrents directs publient un prix ferme."),
        _section("8.3", "Politique tarifaire",
                 "Sur le panel de concurrents directs, six prix sont publiés fermement."),
        _section("10.3", "Comparaison",
                 "Six concurrents directs publient un prix ferme en ligne."),
        _section("8.5", "Cohérence",
                 f"Publier un prix ferme réduit la friction : {proportion} des concurrents "
                 "directs renvoient encore vers une demande sur devis."),
    ]


def test_une_proportion_contraire_au_compte_ecrit_partout_est_fausse() -> None:
    """Six prix fermes sur neuf : trois sur devis — pas « la moitié »."""
    constats = _constats(_prix_fermes("la moitié"))
    assert [c.section for c in constats] == ["8.5"]
    assert "moitié" in constats[0].extrait
    assert "7.4, 8.3, 10.3" in constats[0].detail


def test_contre_epreuve_la_proportion_juste_passe() -> None:
    assert _constats(_prix_fermes("un tiers")) == []


def test_contre_epreuve_les_prix_du_projet_ne_comptent_pas_le_panel() -> None:
    """« Le projet affiche trois prix fermes » : les prix du PROJET, pas du panel."""
    sections = _prix_fermes("un tiers")[:3] + [_section(
        "8.5", "Cohérence",
        "Le projet affiche trois prix fermes, là où trois concurrents directs restent sur devis.",
    )]
    assert _constats(sections) == []


# ── 3. « N formats », « N familles » contre le tableau voisin ────────────────


def _formats() -> Tableau:
    return Tableau(
        entetes=("Univers", "Prestation", "Format"),
        lignes=(
            ("Rivages", "Atelier découverte", "Soirée 2 h"),
            ("Rivages", "Atelier complet", "Demi-journée 3 h"),
            ("Rivages", "Atelier signature", "Demi-journée 4 h"),
            ("Sommets", "Séjour", "Week-end 2 nuits"),
            ("Sommets", "Séjour long", "Semaine"),
        ),
    )


def test_un_compte_annonce_plus_grand_que_le_tableau_est_faux() -> None:
    """« Deux univers, six formats » au-dessus de cinq formats — dans l'accroche du chapitre."""
    sections = [
        _section("ch. 8", "OFFRE", "Deux univers, six formats, une seule logique de prix."),
        _section("8.1", "Ce qui est vendu : deux univers, six formats", tableaux=[_formats()]),
    ]
    constats = _constats(sections, classe="comptage")
    assert sorted(c.section for c in constats) == ["8.1", "ch. 8"]
    assert all(c.extrait == "six formats" and "5" in c.detail for c in constats)


@pytest.mark.parametrize("texte", [
    "Deux univers, cinq formats, une seule logique de prix.",
    # Un sous-ensemble : trois formats courts parmi les cinq.
    "Trois formats courts ouvrent la gamme.",
    # Un compte PAR ligne, pas un total.
    "Deux formats par univers au plus.",
    # Une fourchette.
    "De 2 à 3 formats par saison.",
])
def test_contre_epreuve_les_comptes_qui_tiennent_passent(texte: str) -> None:
    sections = [_section("8.1", "Ce qui est vendu", texte, tableaux=[_formats()])]
    assert _constats(sections, classe="comptage") == []


def _fournisseurs(avec_famille: bool) -> Tableau:
    lignes = (
        ("Animatrices", "Qualité", "Formation"),
        ("Coachs", "Crédibilité", "Diplôme"),
        ("Gîtes", "Marge", "Contrat"),
        ("Salles", "Accès", "Contrat"),
    )
    if avec_famille:
        familles = ("Intervenants", "Intervenants", "Lieux", "Lieux")
        return Tableau(
            entetes=("Fournisseur", "Enjeu", "Action", "Rattachement"),
            lignes=tuple((*ligne, f) for ligne, f in zip(lignes, familles, strict=True)),
        )
    return Tableau(entetes=("Fournisseur", "Enjeu", "Action"), lignes=lignes)


_FAMILLES = "Deux familles de fournisseurs portent la qualité : intervenants et lieux."


def test_des_familles_que_le_tableau_ne_range_pas_sont_signalees() -> None:
    """« Deux familles de fournisseurs » au-dessus de quatre lignes sans rangement."""
    sections = [_section("12.6", "Fournisseurs", _FAMILLES,
                         tableaux=[_fournisseurs(avec_famille=False)])]
    constats = _constats(sections, classe="comptage")
    assert [c.extrait for c in constats] == ["Deux familles de fournisseurs"]
    assert constats[0].grave is False  # un regroupement peut être juste : signalé seulement


def test_contre_epreuve_des_familles_rangees_dans_le_tableau_passent() -> None:
    sections = [_section("12.6", "Fournisseurs", _FAMILLES,
                         tableaux=[_fournisseurs(avec_famille=True)])]
    assert _constats(sections, classe="comptage") == []


def test_un_tableau_coupe_par_la_page_se_compte_en_entier() -> None:
    """Le PDF répète l'en-tête : 3 lignes puis 2, c'est un tableau de cinq."""
    haut = Tableau(entetes=_formats().entetes, lignes=_formats().lignes[:3])
    bas = Tableau(entetes=_formats().entetes, lignes=_formats().lignes[3:])
    sections = [_section("8.1", "Ce qui est vendu", "Les cinq formats se complètent.",
                         tableaux=[haut, bas])]
    assert _constats(sections, classe="comptage") == []


# ── 4. Une décision écrite de deux façons ────────────────────────────────────


def _offres() -> Section:
    return _section("4.1", "Ce qui est vendu", tableaux=[Tableau(
        entetes=("Univers", "Format"),
        lignes=(("Rivages", "Soirées"), ("Sommets", "Parcours de trois séances")),
    )])


def test_une_offre_lancee_a_deux_dates_est_une_contradiction() -> None:
    sections = [
        _offres(),
        _section("4.4", "Besoins", tableaux=[Tableau(
            entetes=("Besoin", "Format qui y répond", "Priorité au lancement"),
            lignes=(("Se ressourcer", "Rivages", "Oui"),
                    ("Changer de vie", "Sommets", "Non, phase 3")),
        )]),
        _section("11.4", "Phase 3 (2031) — Consolidation", "La phase de consolidation."),
        _section("12.2", "Équipe",
                 "Les coachs sont recrutées avant le lancement des Sommets à l'automne 2029."),
    ]
    constats = _constats(sections, classe="decision")
    assert sorted(c.section for c in constats) == ["12.2", "4.4"]
    assert any("phase 3" in c.extrait for c in constats)
    assert any("automne 2029" in c.extrait for c in constats)


def test_contre_epreuve_une_declinaison_datee_n_est_pas_le_lancement() -> None:
    """« Week-end Sommet (à partir de 2031) » date le week-end, pas l'offre."""
    sections = [
        _offres(),
        _section("8.1", "Gamme", tableaux=[Tableau(
            entetes=("Univers", "Prestation"),
            lignes=(("Sommets", "Week-end Sommet (à partir de 2031)"),
                    ("Sommets", "Parcours")),
        )]),
        _section("12.2", "Équipe",
                 "Les coachs sont recrutées avant le lancement des Sommets à l'automne 2029."),
        _section("10.4", "Visibilité", "Ouverture des Sommets à l'automne 2029."),
        # « à partir de » date ici un PRIX, pas le lancement (revue du 30/09/2026).
        _section("10.2", "Prix", "Le prix des Sommets est revalorisé de 3 % à partir de 2031."),
    ]
    assert _constats(sections, classe="decision") == []


def test_un_depart_date_autrement_que_la_decision_du_projet_est_signale() -> None:
    reference = _reference(Decision(
        "calendrier", "Départ du poste salarié prévu en 2031, après deux saisons pleines.",
        2031, JUSTIFICATION_DU_BRIEF, source="brief",
    ))
    sections = [
        _section("1.2", "Contexte", "Le départ du poste salarié est prévu en 2031."),
        _section("18.6", "Rémunération", tableaux=[Tableau(
            entetes=("Condition", "Seuil", "Effet"),
            lignes=(("Départ du poste salarié", "Fin 2031, après accord de l'employeur",
                     "Le revenu du projet devient la seule ressource"),),
        )]),
    ]
    constats = _constats(sections, reference, classe="decision")
    assert [c.section for c in constats] == ["18.6"]
    assert constats[0].extrait.startswith("Fin 2031")
    assert "« 2031 »" in constats[0].detail


def test_contre_epreuve_une_periode_ne_date_pas_le_depart() -> None:
    """« entre 2030 et 2031 » borne une progression ; elle ne date pas l'événement."""
    reference = _reference(Decision(
        "calendrier", "Départ du poste salarié prévu en 2031, après deux saisons pleines.",
        2031, JUSTIFICATION_DU_BRIEF, source="brief",
    ))
    sections = [
        _section("1.2", "Contexte", "Le départ du poste salarié est prévu en 2031."),
        _section("18.2", "Revenu", "La hausse, entre 2030 et 2031, coïncide avec le départ "
                 "du poste salarié."),
    ]
    assert _constats(sections, reference, classe="decision") == []


def test_un_apport_engage_ici_et_a_confirmer_ailleurs_est_signale() -> None:
    sections = [
        _section("15.2", "Ressources", tableaux=[Tableau(
            entetes=("Source de financement", "Montant", "Statut"),
            lignes=(("Apport personnel du dirigeant", "8 000 €", "Engagé au lancement"),
                    ("Emprunt bancaire", "aucun", "Non mobilisé")),
        )]),
        _section("15.3", "Apport", "Limite — cet apport reste une hypothèse à confirmer "
                 "avant l'immatriculation."),
        _section("15.5", "Équilibre", "Plan présentable, sous réserve de confirmer l'apport "
                 "avant l'immatriculation."),
    ]
    constats = _constats(sections, classe="decision")
    assert [(c.section, c.extrait) for c in constats] == [("15.2", "Engagé au lancement")]


def test_contre_epreuve_un_apport_complementaire_n_est_pas_l_apport() -> None:
    """« Confirme qu'aucun apport complémentaire… » : ni le sujet, ni un participe."""
    sections = [
        _section("14.5", "Trésorerie", "Confirme qu'aucun apport complémentaire n'est "
                 "nécessaire."),
        _section("15.3", "Apport", "Cet apport reste une hypothèse à confirmer."),
    ]
    assert _constats(sections, classe="decision") == []


def test_contre_epreuve_un_mot_voisin_ne_qualifie_pas_l_apport() -> None:
    """« l'apport … et les hypothèses de fréquentation » : l'hypothèse n'est pas l'apport."""
    sections = [
        _section("15.1", "Plan", "Le plan repose sur l'apport personnel de 8 000 € et sur les "
                 "hypothèses de fréquentation."),
        _section("15.3", "Apport", "L'apport personnel est versé à l'immatriculation."),
        _section("18.1", "Rémunération", "L'apport préserve un reste à vivre suffisant."),
    ]
    assert _constats(sections, classe="decision") == []


def test_des_fournisseurs_payes_apres_contre_des_acomptes_avant_est_signale() -> None:
    reserve = ("Réserve de trésorerie", "2 000 €",
               "Couvre les acomptes de salle et d'intervenante avant les premiers encaissements")
    sections = [
        _section("12.4", "Moyens", tableaux=[Tableau(
            entetes=("Poste", "Montant", "Ce qu'il couvre"), lignes=(reserve,),
        )]),
        _section("14.1", "Besoins", tableaux=[Tableau(
            entetes=("Poste", "Montant", "Pourquoi"), lignes=(reserve,),
        )]),
        _section("14.4", "BFR", tableaux=[Tableau(
            entetes=("Élément", "Situation retenue"),
            lignes=(("Délai de paiement des fournisseurs (salles, lieux)",
                     "Réglés après la session, une fois les places vendues"),),
        )]),
    ]
    constats = _constats(sections, classe="decision")
    assert [c.section for c in constats] == ["14.4"]
    assert "après la session" in constats[0].extrait


def test_contre_epreuve_l_acompte_de_la_cliente_n_est_pas_celui_des_fournisseurs() -> None:
    sections = [
        _section("14.4", "BFR", tableaux=[Tableau(
            entetes=("Élément", "Situation retenue"),
            lignes=(("Délai de paiement des fournisseurs (salles, lieux)",
                     "Réglés après la session"),),
        )]),
        _section("17.1", "Risques", tableaux=[Tableau(
            entetes=("Risque", "Levier"),
            lignes=(("Trésorerie tendue", "Acompte à la réservation"),),
        )]),
        _section("9.1", "Stock", "L'acompte de 30 % demandé à la commande finance le stock."),
    ]
    assert _constats(sections, classe="decision") == []


def test_contre_epreuve_un_acompte_puis_un_solde_est_une_seule_politique() -> None:
    sections = [
        _section("12.4", "Achats", "Un acompte de 30 % est versé au fournisseur à la commande."),
        _section("14.4", "BFR", "Le solde du fournisseur est réglé après la livraison."),
    ]
    assert _constats(sections, classe="decision") == []


def _tva(texte: str) -> list[Section]:
    payload = ChapitrePayload.model_validate({
        "chapitre": 11, "titre": "Développement", "accroche": "",
        "blocs": [
            {"type": "titre_sous_section", "numero": "11.3", "intitule": "Croissance"},
            {"type": "paragraphe", "texte": texte},
        ],
        "resume": "Résumé.",
    })
    return document_du_chapitre(payload).sections


def test_la_tva_des_le_seuil_de_franchise_n_est_pas_la_regle() -> None:
    constats = _constats(_tva(
        "La TVA devient obligatoire dès que les ventes HT franchissent le seuil de franchise "
        "(37 500 €)."
    ), classe="decision")
    assert [c.section for c in constats] == ["11.3"]
    assert "37 500" in constats[0].extrait and "41 250" in constats[0].detail


def test_la_regle_de_tva_prend_le_seuil_de_l_activite_du_projet() -> None:
    """Une activité de VENTE n'a pas les seuils d'une prestation de services."""
    from generation.memoire.regles import Nature, regime_de_tva

    tva = regime_de_tva(120_000, 2028, Nature.VENTES)
    assert tva is not None
    phrase = ("Pour ce commerce, la TVA devient obligatoire dès que le chiffre d'affaires "
              "dépasse le seuil de franchise.")
    (constat,) = _constats(_tva(phrase), _reference(tva), classe="decision")
    assert "93 500" in constat.detail and "41 250" not in constat.detail
    # Sans mémoire, la règle s'énonce sans montant : un seuil deviné serait faux.
    (sans,) = _constats(_tva(phrase), Reference(), classe="decision")
    assert "€" not in sans.detail and "majoré" in sans.detail.lower()


@pytest.mark.parametrize("texte", [
    "Au-delà du seuil majoré (41 250 €), la TVA s'applique immédiatement ; entre les deux "
    "seuils, au 1er janvier de l'année suivante.",
    "Le chiffre d'affaires dépasse le seuil de franchise de 37 500 € : TVA obligatoire.",
    "Une TVA qui s'applique dès qu'elle est due.",
])
def test_contre_epreuve_la_regle_exacte_de_tva_passe(texte: str) -> None:
    assert _constats([_section("13.4", "TVA", texte)], classe="decision") == []


def test_le_registre_relit_les_comptages() -> None:
    """Branché : `relire` passe par ce contrôle."""
    document = Document(sections=[_section(
        "10.2", "Prix", "Sept concurrents directs sur douze restent sur devis.")])
    assert [c.classe for c in relire(document, _reference()) if c.classe == "comptage"] == [
        "comptage"
    ]

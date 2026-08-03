"""La consigne envoyée au modèle de langage doit porter la forme DU chapitre.

Défaut visé, mesuré : la consigne de forme était la même pour les vingt-et-un
chapitres — « chaque section porte un tableau, un encadré au moins ». Elle
décrivait une moyenne. Le document validé par la cliente, lui, décrit
vingt-et-une formes différentes : le chapitre 09 aligne quatre grilles de
chiffres et n'a aucun paragraphe, le 19 enchaîne treize tableaux.

Un chapitre ne peut pas rendre une forme qu'on ne lui a pas demandée. Ces tests
échouent sur le code d'avant, où `_bloc_forme()` ne prenait aucun argument et
rendait la même chaîne quel que soit le chapitre (règle 6).
"""
from __future__ import annotations

from generation.modele.chargement import chapitre_du_modele, modele_couvre
from generation.modele.consigne import (
    EXEMPLE_SIGNES_MAX,
    chapitre_de_reference,
    exemple_de_reference,
    plan_du_chapitre,
)

# ── Le plan varie d'un chapitre à l'autre ────────────────────────────────────


def test_deux_chapitres_ne_recoivent_pas_le_meme_plan() -> None:
    """C'est la CLASSE du défaut : une consigne unique pour des formes multiples."""
    plans = {numero: plan_du_chapitre(numero) for numero in range(1, 22)}
    assert all(plans.values()), "un chapitre du modèle est sans plan"
    assert len(set(plans.values())) == 21, (
        "des chapitres reçoivent une consigne identique alors que le modèle "
        "leur donne des formes différentes"
    )


def test_le_plan_du_chapitre_09_demande_ses_quatre_grilles() -> None:
    """Le 09 est le cas extrême : que des chiffres, pas un paragraphe."""
    plan = plan_du_chapitre(9)
    assert plan.count("`grille_kpi`") == 4, plan
    assert "`paragraphe`" not in plan, (
        "le chapitre 09 du modèle ne porte aucun paragraphe ; la consigne ne "
        "doit pas en demander"
    )


def test_le_plan_annonce_l_ordre_et_les_longueurs() -> None:
    """Sans numérotation ni cible, « suivre le plan » n'est pas vérifiable."""
    plan = plan_du_chapitre(1)
    assert "DANS CET ORDRE" in plan
    modele = chapitre_du_modele(1)
    assert modele is not None
    premier = next(b for b in modele["blocs"] if b["type"] == "paragraphe")
    assert f"{premier['longueur_cible_signes']} signes" in plan


def test_le_plan_reprend_les_entetes_de_tableau_du_modele() -> None:
    """Sur TOUS les tableaux du modèle, pas sur un exemple choisi (règle 4)."""
    vus = 0
    for numero in range(1, 22):
        modele = chapitre_du_modele(numero)
        assert modele is not None
        plan = plan_du_chapitre(numero)
        for bloc in modele["blocs"]:
            if bloc["type"] != "tableau":
                continue
            vus += 1
            for entete in bloc["entetes"]:
                assert entete in plan, (
                    f"chapitre {numero} : en-tête « {entete} » absent de la consigne"
                )
    assert vus >= 40, f"seulement {vus} tableaux parcourus"


def test_le_plan_ne_demande_pas_les_blocs_produits_au_rendu() -> None:
    """`ligne_source` est écrite par le rendu sous un graphique.

    La demander au modèle de langage lui ferait produire un bloc que le contrat
    n'accepte pas : le chapitre serait rejeté pour une consigne fautive.
    """
    plans = "\n".join(plan_du_chapitre(n) for n in range(1, 22))
    assert "produit au rendu, ne pas rédiger" in plans
    assert "`ligne_source` —" not in plans


def test_un_chapitre_hors_modele_n_invente_pas_de_plan() -> None:
    """La fiche projet (chapitre 00) n'a pas d'équivalent dans le modèle."""
    assert chapitre_du_modele(0) is None
    assert plan_du_chapitre(0) == ""


# ── L'exemple de référence ───────────────────────────────────────────────────


def test_l_exemple_montre_le_chapitre_equivalent() -> None:
    exemple = exemple_de_reference(9)
    reference = chapitre_de_reference(9)
    assert reference is not None
    premiere = reference["blocs"][0]["cellules"][0]["contenu"].splitlines()[0]
    assert premiere in exemple


def test_l_exemple_interdit_d_en_reprendre_les_chiffres() -> None:
    """Sans cette phrase, l'exemple devient une source de chiffres hors socle."""
    exemple = exemple_de_reference(1)
    assert "AUCUN chiffre" in exemple
    assert "socle" in exemple


def test_un_exemple_abrege_le_dit() -> None:
    """Règle 1 : une troncature muette ferait calquer la longueur de l'extrait.

    Un budget d'un seul bloc force la coupe ; le texte doit l'annoncer, et
    renvoyer au plan pour la longueur.
    """
    exemple = exemple_de_reference(19, budget=400)
    assert "extrait abrégé" in exemple
    assert "PLAN IMPOSÉ qui fixe la longueur" in exemple


def test_un_exemple_complet_ne_s_annonce_pas_abrege() -> None:
    """Contre-épreuve : le marqueur ne doit pas apparaître à tort."""
    court = min(
        range(1, 22),
        key=lambda n: len(exemple_de_reference(n, budget=EXEMPLE_SIGNES_MAX * 10)),
    )
    exemple = exemple_de_reference(court, budget=EXEMPLE_SIGNES_MAX * 10)
    assert exemple
    assert "extrait abrégé" not in exemple


def test_l_exemple_tient_dans_son_budget() -> None:
    """Le chapitre 19 de la référence dépasse dix mille signes.

    Sans plafond, il ferait à lui seul l'essentiel de la consigne — et le coût
    du chapitre suivrait.
    """
    for numero in range(1, 22):
        exemple = exemple_de_reference(numero)
        # L'en-tête et le pied s'ajoutent au budget des blocs ; on laisse une
        # marge fixe plutôt qu'un seuil approximatif.
        assert len(exemple) < EXEMPLE_SIGNES_MAX + 1_500, numero


# ── Le modèle ne vaut que pour le livrable qu'il décrit ──────────────────────


def test_la_consigne_de_forme_varie_par_chapitre() -> None:
    """Le test qui échoue sur le code d'avant.

    Avant, `_bloc_forme()` ne prenait aucun argument : deux chapitres
    différents recevaient exactement la même consigne de forme. On compare donc
    les prompts DÉPOUILLÉS de tout ce qui varie déjà par ailleurs (numéro,
    titre, instruction du fichier de prompt) : ce qui reste, c'est la forme.
    """
    from generation.chapitres.runner import _blocs_du_modele

    formes = {
        numero: "\n\n".join(_blocs_du_modele("market_study", numero))
        for numero in (1, 9, 19)
    }
    assert len(set(formes.values())) == 3, "la consigne de forme ne varie pas"
    assert "PLAN IMPOSÉ DU CHAPITRE 09" in formes[9]
    assert formes[9].count("`grille_kpi`") == 4

    # Le livrable non décrit par le modèle retombe sur la consigne moyenne,
    # sans plan imposé — et sans planter.
    forme_bp = "\n\n".join(_blocs_du_modele("business_plan", 1))
    assert "PLAN IMPOSÉ" not in forme_bp
    assert "FORME ATTENDUE" in forme_bp


def test_le_modele_ne_couvre_que_l_etude_de_marche() -> None:
    """Un business plan ne doit pas hériter du plan d'une étude de marché."""
    assert modele_couvre("market_study")
    assert not modele_couvre("business_plan")
    assert not modele_couvre("business_strategy")
    assert not modele_couvre("competitor_study")


# ── Les visuels : une seule liste de types, celle du moteur ──────────────────


def test_le_modele_ne_nomme_aucun_type_de_graphique() -> None:
    """Le test qui échoue sur le code d'avant, et sur sa CLASSE (règle 4).

    Le modèle portait `types_autorises` : sept noms, dont `barres_verticales`,
    `courbe`, `pyramide` et `jauge` — quatre que `TypeGraphique` refuse. Le même
    prompt annonçait donc une liste « imposée » qui faisait échouer la
    validation plus d'une fois sur deux, et le catalogue correct quelques lignes
    plus bas. Il ne restait que trois types utilisables pour tout un document.

    On n'interdit pas ces quatre noms : on interdit qu'une liste de types vive
    ailleurs que dans le moteur qui dessine. Un nom ajouté demain au modèle
    retomberait sinon exactement dans le même piège.
    """
    from generation.chapitres.schema import TypeGraphique

    connus = {t.value for t in TypeGraphique}
    for numero in range(1, 22):
        chapitre = chapitre_du_modele(numero)
        assert chapitre is not None
        for bloc in chapitre["blocs"]:
            if bloc["type"] != "graphique":
                continue
            inconnus = {
                str(nom) for nom in bloc.get("types_autorises") or []
            } - connus
            assert not bloc.get("types_autorises"), (
                f"chapitre {numero} : le modèle nomme des types de graphique "
                f"({sorted(bloc['types_autorises'])}). La liste appartient au "
                f"moteur de rendu — dont {sorted(inconnus)} est absent."
            )


def test_le_plan_renvoie_au_catalogue_pour_le_type() -> None:
    """Contre-épreuve : retirer la liste ne doit pas laisser le modèle sans consigne."""
    plans = [plan_du_chapitre(n) for n in (1, 2, 13, 14, 15)]
    for plan in plans:
        assert "`graphique` — type à choisir dans le catalogue VISUELS" in plan
    assert "types admis" not in "\n".join(plans)


def test_le_plan_porte_le_visuel_attendu_par_le_manuel() -> None:
    """Le catalogue dit ce qu'on sait dessiner ; le manuel dit quoi montrer ICI.

    Sans cette ligne, les vingt-et-un chapitres choisissaient leur figure sur le
    seul profil sectoriel — donc la même, partout. Le manuel, lui, prescrit une
    courbe au chapitre 1 et une scorecard au 14.
    """
    attendus = {
        1: "Courbe historique et projection",
        13: "Matrice probabilité/impact",
        14: "Scorecard de viabilité",
        19: "Feuille de route 90 jours",
    }
    for numero, extrait in attendus.items():
        plan = plan_du_chapitre(numero)
        assert "Visuel attendu par le manuel" in plan, numero
        assert extrait in plan, f"chapitre {numero} : « {extrait} » absent du plan"

    # Et sur TOUS les chapitres, pas seulement ceux qu'on a choisis (règle 4).
    intentions = set()
    for numero in range(1, 22):
        chapitre = chapitre_du_modele(numero)
        assert chapitre is not None
        visuel = chapitre.get("visuel_attendu", "")
        assert visuel, f"chapitre {numero} : aucun visuel attendu déclaré"
        assert visuel in plan_du_chapitre(numero)
        intentions.add(visuel)
    assert len(intentions) == 21, "deux chapitres partagent la même intention visuelle"


def test_le_plan_annonce_l_epaisseur_en_pages_du_manuel() -> None:
    """Le manuel raisonne en pages ; le blueprint, en mots.

    Le modèle de langage ne voyait que la cible de mots, qui ne dit rien de ce
    que le lecteur tiendra en main.
    """
    assert "Épaisseur attendue : 4 à 5 pages" in plan_du_chapitre(1)
    assert "Épaisseur attendue : 5 à 6 pages" in plan_du_chapitre(2)
    for numero in range(1, 22):
        chapitre = chapitre_du_modele(numero)
        assert chapitre is not None
        mini, maxi = chapitre["volume_pages"]
        assert 2 <= mini <= maxi <= 6, f"chapitre {numero} : {mini}-{maxi} pages"


def test_le_plancher_des_volumes_produit_deja_une_etude_conforme() -> None:
    """« 55 à 70 pages utiles », « le document final ne dépasse pas 80 pages ».

    Les volumes du manuel sont indicatifs et NON additifs : leurs planchers
    cumulés font 63 pages, leurs plafonds 85 — soit cinq de plus que la limite
    que le manuel se donne lui-même, annexe non comprise. Écart réel du manuel,
    signalé à la cliente ; on ne récrit pas ses chiffres ici.

    Ce que le test verrouille, c'est la seule propriété dont la génération
    dépend : un chapitre écrit au plancher donne DÉJÀ une étude conforme. Sans
    elle, respecter le manuel chapitre par chapitre pourrait produire un
    document trop court, et personne ne le verrait avant la livraison.
    """
    bornes = [
        chapitre_du_modele(n)["volume_pages"]  # type: ignore[index]
        for n in range(1, 22)
    ]
    mini = sum(b[0] for b in bornes)
    assert 55 <= mini <= 70, (
        f"au plancher, l'étude ferait {mini} pages — hors des 55 à 70 pages "
        "utiles du manuel"
    )
    # Le plafond reste hors borne par construction. On l'enregistre pour que sa
    # dérive éventuelle se voie, sans prétendre qu'il est conforme.
    maxi = sum(b[1] for b in bornes)
    assert maxi <= 90, f"plafond cumulé {maxi} pages : dérive au-delà du manuel"

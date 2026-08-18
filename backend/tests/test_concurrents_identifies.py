"""Un concurrent est une entreprise, pas une catégorie de marché.

## Le dossier

Étude de concurrence `3a4df56c`, 17/08/2026, relue par la cliente le 18/08.
Son premier constat, et c'est le bon : « en réalité, l'étude ne compare pas
11 concurrents identifiés. Elle compare 5 offres/acteurs identifiés + 6
profils-types ».

Six des onze acteurs sont des categories : « Agence IA générique (Lyon) »,
« Cabinet de conseil IA packagé pour PME (Nantes) », « Intégrateur d'agents IA
pour PME (Bordeaux) », « Consultant indépendant IA/no-code », « Organisme de
formation IA », « ESN de taille intermédiaire (Lille) ». Le document l'écrit
lui-même dans sa colonne source — « non communiqué (recherche par catégorie) »
— et au chapitre Sources : « faute de nom individuel vérifiable ».

Et il leur donne quand meme tout ce qu'on donne a une entreprise observee :

    | Agence IA générique (Lyon) | 130 000 | 0,015 % |
    | Agence IA générique (Lyon) | 95 000 | 130 000 | +37 % |

Deuxieme constat : EY compte pour deux. « EY France - Conseil en Intelligence
Artificielle » et « EY France - Conseil en Intelligent Automation » sont deux
offres du meme cabinet, notees separement, aux parts de marche additionnees.

## La regle retenue

Un profil-type RESTE dans l'etude — il decrit une zone reelle du marche — mais
il ne porte AUCUN chiffre. On n'observe pas une categorie.
"""
from __future__ import annotations

import pytest

from generation.socle.schema import Concurrent, Socle, Zone

# `offres_du_meme_groupe` et `est_identifie` sont neufs : les importer en tete
# ferait echouer la COLLECTE du module sur le code d'avant, et les tests de
# COMPORTEMENT — ceux qui prouvent que la consigne a change — ne tourneraient
# jamais (regle 6).


def offres_du_meme_groupe(concurrents):  # noqa: ANN001, ANN201
    from generation.socle import schema  # noqa: PLC0415

    return schema.offres_du_meme_groupe(concurrents)

# Les valeurs EXACTES du dossier livre.
IDENTIFIES = [
    ("EY France - Conseil en Intelligence Artificielle",
     "ey.com, page conseil en intelligence artificielle"),
    ("Deloitte France - Conseil en Intelligence Artificielle",
     "https://www2.deloitte.com/fr/"),
    ("Findle", "findle.fr"),
    ("SIS International - Conseil en Automatisation et IA", "sisinternational.com"),
]
PROFILS = [
    ("Agence IA générique (Lyon)", "non communiqué (recherche par catégorie)"),
    ("Cabinet de conseil IA packagé pour PME (Nantes)", "non communiqué"),
    ("Intégrateur d'agents IA pour PME (Bordeaux)", "recherche par catégorie"),
    ("Consultant indépendant IA/no-code", ""),
    ("Organisme de formation IA (Paris et à distance)", "non communiqué"),
    ("ESN de taille intermédiaire (Lille)", "non communiqué"),
]


@pytest.mark.parametrize(("nom", "site"), IDENTIFIES)
def test_une_entreprise_avec_son_site_est_identifiee(nom: str, site: str) -> None:
    """Contre-epreuve : le correctif ne doit pas ecarter les VRAIS acteurs.

    Sans ce test, refuser tout le monde passerait pour une reussite (regle 1) —
    et c'est exactement ce qu'a fait la premiere version, dont la constante
    vivait dans le corps du modele pydantic.
    """
    assert Concurrent(nom=nom, site_web=site).est_identifie


@pytest.mark.parametrize(("nom", "site"), PROFILS)
def test_un_profil_type_n_est_pas_identifie(nom: str, site: str) -> None:
    """Echoue sur le code d'avant : rien ne distinguait ces acteurs d'EY."""
    assert not Concurrent(nom=nom, site_web=site).est_identifie


def test_deux_offres_du_meme_domaine_sont_un_seul_concurrent() -> None:
    """Le doublon EY, sur ses deux URL reelles.

    Echoue sur le code d'avant : `offres_du_meme_groupe` n'existait pas, et
    rien dans la chaine ne rapprochait ces deux lignes.
    """
    concurrents = [
        Concurrent(
            nom="EY France - Conseil en Intelligence Artificielle",
            site_web="https://www.ey.com/fr_fr/services/consulting/"
                     "artificial-intelligence-consulting-services",
        ),
        Concurrent(
            nom="EY France - Conseil en Intelligent Automation",
            site_web="https://www.ey.com/fr_fr/services/consulting/"
                     "intelligent-automation-consulting-services",
        ),
        Concurrent(nom="Deloitte France", site_web="https://www2.deloitte.com/fr/"),
    ]
    groupes = offres_du_meme_groupe(concurrents)
    assert len(groupes) == 1
    domaine, noms = groupes[0]
    assert "ey.com" in domaine
    assert len(noms) == 2


def test_le_meme_cabinet_ecrit_de_deux_facons_donne_le_meme_domaine() -> None:
    """Le defaut que la contre-epreuve a attrape avant la production.

    La base reelle ecrit EY des DEUX manieres : « ey.com, page conseil… » dans
    une colonne, l'URL complete « https://www.ey.com/fr_fr/… » dans le chapitre
    Sources. La premiere version du domaine rendait « ey.com » pour l'une et
    « www.ey » pour l'autre : le regroupement aurait echoue exactement sur le
    cas qui l'a fait ecrire.
    """
    court = Concurrent(nom="EY (colonne)", site_web="ey.com, page conseil en IA")
    long = Concurrent(
        nom="EY (sources)",
        site_web="https://www.ey.com/fr_fr/services/consulting/"
                 "artificial-intelligence-consulting-services",
    )
    assert court.domaine == long.domaine == "ey.com"

    # Et un sous-domaine ne fabrique pas une entreprise de plus.
    assert Concurrent(nom="D", site_web="https://www2.deloitte.com/fr/").domaine == (
        "deloitte.com"
    )
    assert len(offres_du_meme_groupe([court, long])) == 1


def test_deux_vrais_concurrents_ne_sont_pas_fusionnes() -> None:
    """Contre-epreuve : deux entreprises distinctes restent distinctes."""
    assert offres_du_meme_groupe([
        Concurrent(nom="Findle", site_web="findle.fr"),
        Concurrent(nom="Deloitte France", site_web="www2.deloitte.com/fr"),
        Concurrent(nom="SIS International", site_web="sisinternational.com"),
    ]) == []


def _socle(concurrents: list[Concurrent]) -> Socle:
    return Socle(
        secteur="conseil IA", zone=Zone(pays="France"),
        date_socle="2026-08-18", concurrents=concurrents,
    )


def test_la_consigne_interdit_tout_chiffre_sur_un_profil_type() -> None:
    """LE test qui compte : c'est cette phrase qui fabriquait les 130 000 €.

    Echoue sur le code d'avant : `_bloc_concurrents` envoyait « CA non publié —
    à estimer par : … » a TOUS les acteurs, profils-types compris.
    """
    from generation.chapitres.runner import _bloc_concurrents

    bloc = _bloc_concurrents(_socle([
        Concurrent(nom="Findle", type="direct", site_web="findle.fr",
                   methode_estimation="trafic et effectifs"),
        Concurrent(nom="Agence IA générique (Lyon)", type="direct",
                   site_web="non communiqué (recherche par catégorie)",
                   methode_estimation="volume de missions estimé"),
    ]))

    apres_profil = bloc.split("Agence IA générique (Lyon)", 1)[1]
    ligne_profil = apres_profil.split("\n", 1)[0]
    assert "à estimer par" not in ligne_profil, (
        f"Le profil-type reçoit encore une consigne d'estimation : {ligne_profil}"
    )
    assert "TYPE D'ACTEUR" in ligne_profil
    assert "NI part de marché" in ligne_profil

    # Contre-epreuve : l'entreprise identifiee garde la sienne.
    ligne_findle = bloc.split("- Findle", 1)[1].split("\n", 1)[0]
    assert "à estimer par" in ligne_findle


def test_la_consigne_nomme_les_offres_d_un_meme_groupe() -> None:
    """Echoue sur le code d'avant : le bloc ne disait rien du doublon."""
    from generation.chapitres.runner import _bloc_concurrents

    bloc = _bloc_concurrents(_socle([
        Concurrent(nom="EY France - Conseil en IA", type="direct",
                   site_web="ey.com/fr_fr/services/consulting/ai"),
        Concurrent(nom="EY France - Intelligent Automation", type="direct",
                   site_web="ey.com/fr_fr/services/consulting/automation"),
    ]))
    assert "MÊME entreprise" in bloc
    assert "n'additionne jamais leurs parts de marché" in bloc


def test_une_base_saine_ne_declenche_aucun_avertissement() -> None:
    """Contre-epreuve : pas de bruit sur une base correcte."""
    from generation.chapitres.runner import _bloc_concurrents

    bloc = _bloc_concurrents(_socle([
        Concurrent(nom="Findle", type="direct", site_web="findle.fr"),
        Concurrent(nom="Deloitte France", type="direct", site_web="www2.deloitte.com/fr"),
    ]))
    assert "MÊME entreprise" not in bloc
    assert "TYPE D'ACTEUR" not in bloc


def test_le_plafond_du_business_plan_couvre_ses_vingt_deux_chapitres() -> None:
    """Le chapitre 02 perdu, et la decision de la cliente du 18/08/2026.

    Le business plan `256e63d8` s'est arrete a 21 chapitres sur 22 : le
    sommaire livre passe de « 01 Résumé exécutif » a « 03 Genèse du projet ».
    Le plafond a fonctionne exactement comme prevu ; c'est sa valeur qui etait
    sous le cout reel du livrable.
    """
    from decimal import Decimal

    from catalog.models import DeliverableType
    from generation.cost import PLAFOND_PAR_LIVRABLE

    assert PLAFOND_PAR_LIVRABLE[DeliverableType.BUSINESS_PLAN] == Decimal("8.0000")

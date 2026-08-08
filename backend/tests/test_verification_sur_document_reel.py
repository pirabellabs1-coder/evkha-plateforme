"""La passe de vérification doit juger le document tel que le rendu l'écrit.

Défaut mesuré, et le plus coûteux trouvé sur ce dépôt : `controler_integrite_du_
document` cherchait « Chapitre 01 » là où `bandeau_chapitre` écrit « CHAPITRE 01 ».
La comparaison est sensible à la casse. Le contrôle déclarait donc les
vingt-trois chapitres ABSENTS d'un document qui les contient tous, en gravité
BLOQUANTE — et `delivery/services.py` retenait le livrable. **Aucune étude de
marché ne pouvait partir**, et le motif était introuvable dans le document par
qui l'ouvrait : la règle 2 mot pour mot.

Pourquoi la suite ne l'a pas vu : les tests du lot 4 passent au contrôle une
doublure construite à la main, qui écrit « Chapitre 01 » — c'est-à-dire la forme
que le contrôle attendait, pas celle que le rendu produit. Le vert des tests ne
prouve rien sur le document livré (règle 7).

Ce fichier ne prend donc AUCUNE doublure : il rend un vrai `.docx` et le relit.
Il échoue sur le code d'avant.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from generation.rendu_word.composants import marqueur_de_chapitre
from generation.rendu_word.depuis_json import rendre_etude
from generation.rendu_word.fixture import construire_fixture
from generation.verification.controles import controler_integrite_du_document
from generation.verification.lecture import lire_livrable
from generation.verification.rapport import Gravite

#: Quatre chapitres — le 0 (fiche projet, interne) et trois chapitres client.
#: Assez pour mettre la casse en évidence ; le rendu complet coûterait plusieurs
#: secondes de matplotlib pour rien de plus.
NOMBRE_CHAPITRES = 4

#: Ceux qui partent chez le client : tous sauf la fiche projet.
CLIENT = list(range(1, NOMBRE_CHAPITRES))


@pytest.fixture
def livrable(tmp_path: Path) -> Path:
    etude = construire_fixture(nombre_chapitres=NOMBRE_CHAPITRES)
    return rendre_etude(etude, tmp_path / "etude.docx")


def test_un_document_complet_ne_declare_aucun_chapitre_absent(livrable: Path) -> None:
    """Le test qui échoue sur le code d'avant : tous étaient déclarés absents."""
    anomalies = controler_integrite_du_document(lire_livrable(livrable), CLIENT)

    absents = [a for a in anomalies if "absent" in a.detail]
    assert not absents, (
        "le contrôle déclare absents des chapitres physiquement présents : "
        + " | ".join(a.detail for a in absents)
    )
    assert not [a for a in anomalies if a.gravite is Gravite.BLOQUANTE]


def test_le_marqueur_cherche_est_bien_celui_qui_est_ecrit(livrable: Path) -> None:
    """La CLASSE du défaut (règle 4) : deux modules décrivaient le même texte.

    On ne teste pas « la casse est la bonne » mais « le contrôle et le rendu
    parlent du même marqueur ». Une future petite capitale de style, un tiret
    ajouté, un numéro non paddé — tout cela retomberait dans le même piège si on
    s'était contenté d'un `.lower()`.
    """
    texte = lire_livrable(livrable).texte_integral
    for numero in CLIENT:
        assert marqueur_de_chapitre(numero) in texte, (
            f"le marqueur du chapitre {numero} n'est pas dans le document rendu"
        )


def test_la_fiche_projet_ne_part_pas_chez_le_client(livrable: Path) -> None:
    """Le chapitre 0 est la carte d'identité INTERNE de la commande.

    Il était exclu du sommaire et rendu dans le corps : l'étude s'ouvrait sur
    une section que sa propre table des matières ignore — reformulation du
    brief, questions implicites, budget, points sensibles. Le manuel exige que
    « les contrôles internes soient retirés du livrable client ».
    """
    texte = lire_livrable(livrable).texte_integral
    assert marqueur_de_chapitre(0) not in texte, (
        "la fiche projet interne est imprimée dans le document du client"
    )


def test_le_controle_ne_reclame_pas_la_fiche_projet() -> None:
    """Règle 3, dans l'autre sens : ne pas remplacer un défaut par un blocage.

    Cesser de rendre le chapitre 0 sans le retirer des chapitres ATTENDUS
    ferait échouer le contrôle d'intégrité sur toutes les livraisons — le
    défaut qu'on vient précisément de corriger, sous une autre forme.
    """
    from catalog.models import DeliverableType
    from generation.blueprints import SectionKind, chapters_for_deliverable
    from generation.verification.services import _chapitres_attendus

    class _Job:
        deliverable_type = str(DeliverableType.MARKET_STUDY)

    attendus = _chapitres_attendus(_Job())  # type: ignore[arg-type]
    ouvertures = [
        bp.number
        for bp in chapters_for_deliverable(str(DeliverableType.MARKET_STUDY))
        if bp.section_kind == SectionKind.OPENING
    ]
    assert ouvertures, "le livrable ne déclare aucune ouverture : test sans objet"
    for numero in ouvertures:
        assert numero not in attendus
    # Contre-épreuve : les chapitres du client, eux, restent exigés.
    assert 1 in attendus
    assert max(attendus) == 22


def test_un_chapitre_reellement_absent_reste_signale(tmp_path: Path) -> None:
    """Contre-épreuve : le correctif ne doit pas rendre le contrôle complaisant.

    Un contrôle qui ne bloque plus jamais ne vaut pas mieux que celui qui
    bloquait toujours.
    """
    etude = construire_fixture(nombre_chapitres=NOMBRE_CHAPITRES)
    rendu = rendre_etude(etude, tmp_path / "partielle.docx")

    attendus = list(range(NOMBRE_CHAPITRES + 2))  # deux chapitres jamais rendus
    anomalies = controler_integrite_du_document(lire_livrable(rendu), attendus)

    absents = [a for a in anomalies if "absent" in a.detail]
    assert absents, "un chapitre manquant n'est plus détecté"
    assert str(NOMBRE_CHAPITRES) in absents[0].detail
    assert absents[0].gravite is Gravite.BLOQUANTE

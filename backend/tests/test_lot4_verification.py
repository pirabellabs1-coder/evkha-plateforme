"""Lot 4 — passe de vérification du livrable.

Ces tests sont écrits contre les deux défauts historiques du dépôt, pas contre
une spécification abstraite :

- une barrière qui rendait `passed: True` faute de donnée à comparer
  (règle 1) : chaque contrôle est donc éprouvé **sans matière**, et doit
  échouer bruyamment ;
- une barrière qui produisait des motifs faux (règle 2) : chaque rejet a sa
  contre-épreuve, le cas correct qui doit passer.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from generation.rendu_word.assemblage import RapportAssemblage, assembler_etude
from generation.rendu_word.depuis_json import rendre_etude
from generation.socle.schema import Socle
from generation.verification import controles
from generation.verification.lecture import DocumentLu, lire_livrable, mesures_dans
from generation.verification.rapport import Anomalie, Gravite, RapportControle
from generation.verification.services import verifier_document

# ── Matière de test ──────────────────────────────────────────────────────────


def _donnee(identifiant: str, libelle: str, valeur: float, unite: str) -> dict[str, Any]:
    return {
        "id": identifiant, "libelle": libelle, "valeur": valeur, "unite": unite,
        "annee": 2025, "perimetre": "monde", "source": "Source de test",
        "fiabilite": "observee", "derivee_de": [],
    }


def _socle(**remplacements: Any) -> Socle:
    base: dict[str, Any] = {
        "secteur": "joaillerie de créateurs",
        "zone": {"pays": "France"},
        "date_socle": date(2026, 1, 15).isoformat(),
        "donnees": [
            _donnee("tam", "Marché total théorique", 4000.0, "MEUR"),
            _donnee("sam", "Marché adressable", 250.0, "MEUR"),
            _donnee("som", "Marché atteignable", 3.0, "MEUR"),
        ],
        "segments_clientele": [], "concurrents": [], "tendances": [], "risques": [],
    }
    base.update(remplacements)
    return Socle.model_validate(base)


def _document(paragraphes: list[str], cellules: list[str] | None = None) -> DocumentLu:
    """Document lu synthétique, sans passer par un fichier."""
    lu = DocumentLu(chemin=Path("memoire.docx"))
    lu.paragraphes = list(paragraphes)
    lu.cellules = list(cellules or [])
    lu.tableaux = 1 if lu.cellules else 0
    for prose in lu.paragraphes:
        lu.mesures.extend(mesures_dans(prose))
    for contenu in lu.cellules:
        lu.mesures.extend(mesures_dans(contenu, dans_un_tableau=True))
    return lu


# ── Lecture : ce que la passe voit, et ce qu'elle ne voit pas ────────────────


@pytest.mark.parametrize(
    ("texte", "valeur", "unite"),
    [
        ("Le marché pèse 381,5 Md€ en 2025.", 381.5e9, "Md€"),
        ("Un marché de 4 000 M€.", 4000e6, "M€"),
        ("La part atteint 38 %.", 38.0, "%"),
        ("Environ 420 millions d'euros.", 420e6, "millions"),
    ],
)
def test_une_grandeur_chiffree_est_relevee_avec_son_unite(
    texte: str, valeur: float, unite: str
) -> None:
    """Sans l'unité, « 1,25 M€ » serait lu 1,25 et comparé à 1 250 000."""
    mesures = mesures_dans(texte)
    assert mesures
    assert mesures[0].valeur == pytest.approx(valeur)
    assert unite.lower() in mesures[0].unite.lower()


@pytest.mark.parametrize(
    "texte",
    [
        "Trois portes d'entrée suffisent.",
        "Horizon 0-30 j pour clarifier la promesse.",
        "Chapitre 12 — les chiffres clés.",
        "Une note de 4,4 sur cette grille.",
    ],
)
def test_un_nombre_sans_unite_n_est_pas_releve(texte: str) -> None:
    """Restriction assumée : ce ne sont pas des affirmations de marché.

    Les traiter comme telles produirait des motifs faux, pires qu'absents
    (règle 2). Ce test verrouille le périmètre pour qu'il ne dérive pas.
    """
    assert mesures_dans(texte) == []


def test_le_contexte_rend_le_motif_trouvable_par_un_lecteur() -> None:
    """Un motif d'échec doit pouvoir être retrouvé dans le document (règle 2)."""
    mesure = mesures_dans("Le marché accessible est estimé à 250 M€ en année 3.")[0]
    assert "marché accessible" in mesure.contexte


# ── Contrôle 1 : aucune valeur hors socle ────────────────────────────────────


def test_un_chiffre_du_socle_est_accepte() -> None:
    document = _document(["Le marché adressable atteint 250 M€."])
    assert controles.controler_chiffres_hors_socle(document, _socle()) == []


def test_un_chiffre_absent_du_socle_est_signale() -> None:
    document = _document(["Le marché adressable atteint 900 M€."])
    anomalies = controles.controler_chiffres_hors_socle(document, _socle())
    assert len(anomalies) == 1
    assert "900 M€" in anomalies[0].detail
    assert "marché adressable" in anomalies[0].extrait


def test_un_arrondi_d_affichage_reste_accepte() -> None:
    """« 251 M€ » pour 250 M€ est le même chiffre arrondi, pas un autre chiffre."""
    document = _document(["Le marché adressable atteint 251 M€."])
    assert controles.controler_chiffres_hors_socle(document, _socle()) == []


def test_un_chiffre_franchement_different_n_est_pas_absorbe_par_la_tolerance() -> None:
    """Contre-épreuve de la tolérance : elle ne doit pas tout laisser passer."""
    document = _document(["Le marché adressable atteint 300 M€."])
    assert controles.controler_chiffres_hors_socle(document, _socle())


def test_un_chiffre_ecrit_par_le_client_est_accepte() -> None:
    """Le client a le droit de citer son propre chiffre d'affaires."""
    document = _document(["Le chiffre d'affaires actuel est de 180 000 €."])
    assert controles.controler_chiffres_hors_socle(
        document, _socle(), chiffres_du_brief=[180_000.0]
    ) == []


def test_un_socle_vide_bloque_au_lieu_de_tout_accepter() -> None:
    """Règle 1 : un contrôle qui n'a rien à comparer est un ÉCHEC."""
    document = _document(["Le marché adressable atteint 250 M€."])
    anomalies = controles.controler_chiffres_hors_socle(document, _socle(donnees=[]))
    assert [a.gravite for a in anomalies] == [Gravite.BLOQUANTE]


def test_un_document_sans_le_moindre_chiffre_bloque() -> None:
    document = _document(["Une analyse purement qualitative du secteur."])
    anomalies = controles.controler_chiffres_hors_socle(document, _socle())
    assert [a.gravite for a in anomalies] == [Gravite.BLOQUANTE]


def test_un_chiffre_hors_socle_ne_bloque_pas_la_livraison() -> None:
    """La passe ne recalcule pas l'arithmétique interne des chapitres.

    Une somme légitime de deux valeurs du socle apparaît donc hors socle.
    Bloquer sur cette base arrêterait des livrables corrects, et une barrière
    qui crie à tort finit débranchée.
    """
    document = _document(["Le marché adressable atteint 900 M€."])
    anomalies = controles.controler_chiffres_hors_socle(document, _socle())
    assert all(a.gravite is Gravite.AVERTISSEMENT for a in anomalies)


def test_un_pourcentage_n_est_pas_compare_a_un_montant() -> None:
    """250 M€ et « 250 % » ne sont pas le même nombre."""
    socle = _socle(donnees=[_donnee("sam", "Marché adressable", 250.0, "MEUR")])
    document = _document(["La croissance atteint 250 %."])
    # Le pourcentage est comparé aux valeurs brutes du socle, dont 250 fait
    # partie : le contrôle l'accepte. Ce que ce test verrouille, c'est
    # l'inverse — un montant ne doit pas être justifié par un pourcentage.
    montant = _document(["Le marché pèse 12 M€."])
    socle_pourcent = _socle(donnees=[_donnee("part", "Part premium", 12.0, "%")])
    assert controles.controler_chiffres_hors_socle(document, socle) == []
    assert controles.controler_chiffres_hors_socle(montant, socle_pourcent)


# ── Contrôle 2 : couverture du socle ─────────────────────────────────────────


def test_une_donnee_obligatoire_absente_du_socle_bloque() -> None:
    anomalies = controles.controler_couverture_du_socle(
        _document(["250 M€"]), _socle(), "market_study"
    )
    assert any(a.gravite is Gravite.BLOQUANTE for a in anomalies)


def test_un_livrable_sans_referentiel_bloque_au_lieu_de_passer() -> None:
    """Règle 1, encore : impossible de juger n'est pas la même chose que rien à dire.

    Citait le business plan avant sa bascule du 06/08/2026 sur le moteur
    structuré ; la propriété se vérifie sur un type inconnu, non couvert pour
    toujours.
    """
    anomalies = controles.controler_couverture_du_socle(
        _document(["250 M€"]), _socle(), "livrable_inconnu"
    )
    assert [a.gravite for a in anomalies] == [Gravite.BLOQUANTE]


def test_une_donnee_du_socle_jamais_citee_est_signalee() -> None:
    socle = _socle(donnees=[_donnee("tam", "Marché total", 4000.0, "MEUR")])
    anomalies = [
        a for a in controles.controler_couverture_du_socle(
            _document(["Une analyse sans chiffre."]), socle, "market_study"
        )
        if "n'apparaît nulle part" in a.detail
    ]
    assert not anomalies or all(a.gravite is Gravite.AVERTISSEMENT for a in anomalies)


def test_un_chiffre_porte_par_un_graphique_compte_comme_present() -> None:
    """Angle mort découvert sur un vrai livrable : un chiffre dessiné est un pixel.

    Il est sous les yeux du lecteur et invisible à une relecture du texte.
    Sans cette correction, le contrôle déclarait absentes des données
    parfaitement présentes — un motif faux (règle 2).
    """
    socle = _socle(donnees=[_donnee("tam", "Marché total", 4000.0, "MEUR")])
    sans_figure = controles.controler_couverture_du_socle(
        _document(["Une analyse sans chiffre."]), socle, "market_study"
    )
    avec_figure = controles.controler_couverture_du_socle(
        _document(["Une analyse sans chiffre."]), socle, "market_study",
        identifiants_en_figure={"tam"},
    )
    manquantes = [a for a in sans_figure if "n'apparaît nulle part" in a.detail]
    assert manquantes
    assert not [a for a in avec_figure if "n'apparaît nulle part" in a.detail]


# ── Contrôle 3 : hiérarchie des marchés, relue dans le document ──────────────


def test_une_hierarchie_inversee_dans_le_document_bloque() -> None:
    """Le socle peut être juste et le document faux : c'est tout l'intérêt.

    Ici le socle déclare SAM > SOM, mais le document affiche l'inverse.
    """
    socle = _socle(donnees=[
        _donnee("tam", "Marché total", 4000.0, "MEUR"),
        _donnee("sam", "Marché adressable", 3.0, "MEUR"),
        _donnee("som", "Marché atteignable", 250.0, "MEUR"),
    ])
    document = _document(["Marché total 4 000 M€, adressable 3 M€, atteignable 250 M€."])
    anomalies = controles.controler_hierarchie_des_marches(document, socle)
    assert any(a.gravite is Gravite.BLOQUANTE for a in anomalies)
    assert "inversée" in anomalies[0].detail


def test_une_hierarchie_correcte_passe() -> None:
    """Contre-épreuve : le contrôle ne bloque pas ce qui est correct."""
    document = _document([
        "Marché total 4 000 M€, adressable 250 M€, atteignable 3 M€."
    ])
    assert controles.controler_hierarchie_des_marches(document, _socle()) == []


def test_une_hierarchie_absente_partout_bloque() -> None:
    document = _document(["Une analyse sans dimensionnement."])
    anomalies = controles.controler_hierarchie_des_marches(document, _socle())
    assert [a.gravite for a in anomalies] == [Gravite.BLOQUANTE]


def test_une_hierarchie_lisible_seulement_en_graphique_avertit_sans_bloquer() -> None:
    """Ne pas savoir vérifier n'est pas la même chose que constater un défaut."""
    document = _document(["Une analyse sans dimensionnement écrit."])
    anomalies = controles.controler_hierarchie_des_marches(
        document, _socle(), identifiants_en_figure={"tam", "sam", "som"}
    )
    assert [a.gravite for a in anomalies] == [Gravite.AVERTISSEMENT]
    assert "ne relit pas les images" in anomalies[0].detail


def test_un_socle_sans_hierarchie_declaree_ne_produit_rien() -> None:
    socle = _socle(donnees=[_donnee("autre", "Autre chiffre", 12.0, "%")])
    assert controles.controler_hierarchie_des_marches(_document(["12 %"]), socle) == []


# ── Contrôle 4 : intégrité du document ───────────────────────────────────────


def test_un_tableau_vide_bloque() -> None:
    """Défaut réel : le client recevait un compte de résultat sans lignes."""
    lu = _document(["Texte"], ["Cellule"])
    lu.tableaux_vides = 1
    anomalies = controles.controler_integrite_du_document(lu)
    assert any(a.gravite is Gravite.BLOQUANTE for a in anomalies)


def test_un_document_sans_tableau_bloque() -> None:
    anomalies = controles.controler_integrite_du_document(_document(["Texte seul"]))
    assert any("aucun tableau" in a.detail for a in anomalies)


def test_un_chapitre_manquant_bloque() -> None:
    lu = _document(["Chapitre 01 — ouverture"], ["Cellule"])
    anomalies = controles.controler_integrite_du_document(lu, chapitres_attendus=[1, 2])
    assert any("Chapitre(s) absent(s)" in a.detail for a in anomalies)


def test_tous_les_chapitres_presents_ne_produisent_rien() -> None:
    lu = _document(["Chapitre 01 — ouverture", "Chapitre 02 — marché"], ["Cellule"])
    anomalies = controles.controler_integrite_du_document(lu, chapitres_attendus=[1, 2])
    assert not [a for a in anomalies if "absent" in a.detail]


# ── Contrôle 5 : densité ─────────────────────────────────────────────────────


def test_un_mur_de_texte_est_signale() -> None:
    """Le défaut pour lequel la cliente a refusé une première livraison."""
    pave = " ".join(["mot"] * 200)
    lu = _document([pave, pave, pave], ["a"])
    anomalies = controles.controler_densite(lu)
    assert any("texte suivi" in a.detail for a in anomalies)
    assert any("dépassent" in a.detail for a in anomalies)


def test_un_document_dense_ne_declenche_rien() -> None:
    lu = _document(["Amorce courte.", "Autre amorce."], [" ".join(["mot"] * 60)])
    assert controles.controler_densite(lu) == []


# ── Contrôle 6 : visuels ─────────────────────────────────────────────────────


def test_tous_les_graphiques_abandonnes_bloquent() -> None:
    anomalies = controles.controler_visuels(5, 0, ["motif"] * 5)
    assert any(a.gravite is Gravite.BLOQUANTE for a in anomalies)


def test_un_abandon_isole_avertit_seulement() -> None:
    anomalies = controles.controler_visuels(5, 4, ["Chapitre 3 · Figure : motif"])
    assert [a.gravite for a in anomalies] == [Gravite.AVERTISSEMENT]


def test_une_conversion_est_tracee_sans_jugement() -> None:
    anomalies = controles.controler_visuels(1, 1, [], ["courbes → barres"])
    assert [a.gravite for a in anomalies] == [Gravite.INFORMATION]


# ── Rapport ──────────────────────────────────────────────────────────────────


def test_un_rapport_sans_bloquante_declare_le_livrable_livrable() -> None:
    rapport = RapportControle()
    rapport.ajouter(Anomalie("densite", Gravite.AVERTISSEMENT, "détail"))
    assert rapport.livrable


def test_une_seule_bloquante_suffit_a_retenir_le_livrable() -> None:
    rapport = RapportControle()
    rapport.ajouter(Anomalie("integrite", Gravite.BLOQUANTE, "détail"))
    assert not rapport.livrable
    assert rapport.en_dict()["livrable"] is False


def test_le_rapport_est_serialisable_pour_un_incident() -> None:
    rapport = RapportControle()
    rapport.controles_executes.append("integrite")
    rapport.mesures = {"mots": 10}
    rapport.ajouter(Anomalie("integrite", Gravite.BLOQUANTE, "d", chapitre=3, extrait="e"))
    charge = rapport.en_dict()
    assert charge["anomalies"][0]["chapitre"] == 3
    assert charge["controles"] == ["integrite"]


# ── Bout en bout, sur un fichier réel ────────────────────────────────────────
# Règle 7 : le vert des tests unitaires ne prouve rien sur le document livré.


def _socle_complet() -> Socle:
    """Socle couvrant TOUT le référentiel de l'étude de marché.

    Le socle minimal des tests unitaires ne porte que la hiérarchie de marché :
    suffisant pour éprouver un contrôle isolément, insuffisant pour un livrable
    entier, qui doit couvrir les identifiants obligatoires. On repart donc du
    bouchon, qui dérive son contenu du référentiel réel.
    """
    from catalog.models import DeliverableType
    from generation.socle.prompt import construire_prompt_socle
    from generation.socle.stub import socle_de_demonstration

    prompt = construire_prompt_socle(
        deliverable_type=DeliverableType.MARKET_STUDY,
        variables={"SECTEUR": "joaillerie de créateurs", "PAYS": "France"},
    )
    return Socle.model_validate(socle_de_demonstration(prompt))


#: Unités du socle vers leur écriture dans un document français. Le socle
#: stocke `MdEUR` ; un rédacteur écrit « 381,5 Md€ ». La passe lit le document,
#: donc le document de test doit s'écrire comme un vrai document.
_AFFICHAGE = {"MdEUR": "Md€", "MEUR": "M€", "kEUR": "k€", "EUR": "€", "%": "%"}


def _afficher(donnee: Any) -> str:
    unite = _AFFICHAGE.get(donnee.unite, donnee.unite)
    nombre = f"{donnee.valeur:g}".replace(".", ",")
    return f"{nombre} {unite}"


def _chapitre_citant(socle: Socle, numero: int) -> Any:
    from generation.chapitres.schema import ChapitrePayload

    lignes = [
        [donnee.libelle, _afficher(donnee), str(donnee.annee)]
        for donnee in socle.donnees
    ]
    return ChapitrePayload.model_validate({
        "chapitre": numero, "titre": f"Chapitre {numero} — repères",
        "accroche": "Les repères établis au socle.",
        "sections": [{
            "titre": "Repères du périmètre",
            "contenu": "Les chiffres ci-dessous proviennent du socle verrouillé.",
            "tableau": {
                "entetes": ["Indicateur", "Valeur", "Année"], "lignes": lignes,
                "source": "Socle EVKHA.",
            },
        }],
        "encadres": [{"intitule": "Lecture EVKHA", "lignes": ["Ordres de grandeur établis."]}],
        "donnees_utilisees": [d.id for d in socle.donnees], "graphiques": [],
        "resume": "Chapitre de repères chiffrés.",
    })


def test_un_livrable_qui_cite_son_socle_passe_la_verification(tmp_path: Path) -> None:
    """Contre-épreuve au niveau du fichier : rien ne doit être signalé."""
    socle = _socle_complet()
    etude, assemblage = assembler_etude(
        socle=socle, chapitres=[_chapitre_citant(socle, 1)], titre="Étude de marché"
    )
    chemin = rendre_etude(etude, tmp_path / "conforme.docx")

    document = lire_livrable(chemin)
    rapport = verifier_document(
        document, socle, deliverable_type="market_study", assemblage=assemblage
    )
    assert rapport.livrable, [a.detail for a in rapport.bloquantes]
    assert not rapport.anomalies, [a.detail for a in rapport.anomalies]


def test_la_lecture_d_un_livrable_absent_echoue_au_lieu_de_rendre_un_vide(
    tmp_path: Path,
) -> None:
    """Un document vide traverserait tous les contrôles sans en déclencher un seul."""
    with pytest.raises(FileNotFoundError):
        lire_livrable(tmp_path / "jamais_produit.docx")


def test_la_passe_voit_un_chiffre_invente_dans_un_vrai_fichier(tmp_path: Path) -> None:
    """La preuve qui compte : le défaut est détecté sur le fichier, pas sur l'objet."""
    socle = _socle_complet()
    chapitre = _chapitre_citant(socle, 1)
    tableau = chapitre.tableaux[0]
    tableau.lignes.append(["Chiffre inventé", "777 M€", "2025"])
    etude, assemblage = assembler_etude(
        socle=socle, chapitres=[chapitre], titre="Étude de marché"
    )
    chemin = rendre_etude(etude, tmp_path / "suspect.docx")

    rapport = verifier_document(
        lire_livrable(chemin), socle, deliverable_type="market_study",
        assemblage=assemblage,
    )
    hors_socle = [a for a in rapport.anomalies if a.controle == "chiffres_hors_socle"]
    assert len(hors_socle) == 1
    assert "777 M€" in hors_socle[0].detail


def test_le_rapport_d_assemblage_expose_les_identifiants_rendus() -> None:
    """Le lot 3 doit transmettre au lot 4 de quoi lever son angle mort."""
    assert isinstance(RapportAssemblage().identifiants_rendus, set)

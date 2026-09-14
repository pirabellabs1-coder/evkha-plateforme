"""Une cellule de tableau se juge avec son en-tête et sa ligne, comme le lecteur la lit.

## Le défaut mesuré

Corpus du 14/09/2026 : 212 des 382 « chiffres hors socle » d'une étude
concurrentielle étaient des cellules du chapitre 6 jugées SEULES — « 250 000 € »,
« 0,029 % ». Or ce chapitre doit, par cahier des charges, estimer le chiffre
d'affaires et la part de chaque concurrent, et il le fait en tableau sous un
en-tête « CA estimé ». Le lecteur voit l'en-tête ; le contrôle ne le voyait pas,
et accusait d'invention une estimation déclarée (règle 2).

La correction ne crée aucune exception pour les tableaux : la cellule reçoit
pour « phrase » son en-tête et sa ligne, et les règles de la prose s'appliquent.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Zone
from generation.verification.controles import controler_chiffres_hors_socle
from generation.verification.lecture import lire_livrable


def _socle() -> Socle:
    return Socle(
        secteur="conseil", zone=Zone(pays="France"), date_socle=date(2026, 9, 14),
        donnees=[DonneeSocle(
            id="marche_national_taille", libelle="Marché national", valeur=850,
            unite="MEUR", annee=2025, perimetre=Perimetre.NATIONAL,
            fiabilite=Fiabilite.OBSERVEE, source="Xerfi",
        )],
    )


def _docx(tmp_path: Path, entetes: list[str], lignes: list[list[str]]) -> Path:
    from docx import Document

    document = Document()
    document.add_paragraph("Estimation des concurrents.")
    table = document.add_table(rows=1 + len(lignes), cols=len(entetes))
    for colonne, entete in enumerate(entetes):
        table.cell(0, colonne).text = entete
    for rang, ligne in enumerate(lignes, start=1):
        for colonne, valeur in enumerate(ligne):
            table.cell(rang, colonne).text = valeur
    chemin = tmp_path / "etude.docx"
    document.save(str(chemin))
    return chemin


def _signales(chemin: Path) -> set[str]:
    anomalies = controler_chiffres_hors_socle(lire_livrable(chemin), _socle())
    return {a.detail.split(" »")[0].lstrip("« ") for a in anomalies}


def test_une_estimation_en_tableau_n_est_pas_une_invention(tmp_path: Path) -> None:
    chemin = _docx(
        tmp_path,
        ["Concurrent", "CA estimé", "Part de marché estimée"],
        [["Cabinet de Nantes", "250 000 €", "0,029 %"],
         ["ESN de Lille", "350 000 €", "0,041 %"]],
    )
    assert _signales(chemin) == set()


def test_un_chiffre_d_affaires_sans_estimation_declaree_reste_signale(tmp_path: Path) -> None:
    """CONTRE-ÉPREUVE : l'en-tête n'excuse que ce qu'il déclare."""
    chemin = _docx(
        tmp_path,
        ["Concurrent", "Chiffre d'affaires", "Part de marché estimée"],
        [["Cabinet de Nantes", "250 000 €", "0,029 %"]],
    )
    assert "250 000 €" in _signales(chemin)
    assert "0,029 %" not in _signales(chemin)


def test_une_croissance_reste_un_fait_de_marche_meme_estimee(tmp_path: Path) -> None:
    """CONTRE-ÉPREUVE : comme en prose, une croissance ne se « déduit » pas."""
    chemin = _docx(
        tmp_path,
        ["Concurrent", "Croissance estimée"],
        [["Cabinet de Nantes", "12 %"]],
    )
    assert "12 %" in _signales(chemin)


def test_le_motif_montre_l_en_tete_et_la_ligne(tmp_path: Path) -> None:
    """Règle 2 : « 250 000 € » seul est introuvable dans un document à dix tableaux."""
    chemin = _docx(
        tmp_path, ["Concurrent", "Chiffre d'affaires"], [["Cabinet de Nantes", "250 000 €"]],
    )
    anomalies = controler_chiffres_hors_socle(lire_livrable(chemin), _socle())
    assert any("Chiffre d'affaires" in a.extrait and "Cabinet de Nantes" in a.extrait
               for a in anomalies)


# ── Re-mesure après déploiement : quatre classes de plus ────────────────────


def test_le_commentaire_d_une_autre_colonne_n_annule_pas_l_estimation(tmp_path: Path) -> None:
    """« Croissance proche du marché » en dernière colonne ne qualifie pas le CA estimé."""
    chemin = _docx(
        tmp_path,
        ["Acteur", "CA 2025 (estimé)", "CA médian 2026 (estimé)", "Lecture"],
        [["France d'Or", "7,3 M€", "8,5 M€", "Croissance proche du marché"]],
    )
    assert _signales(chemin) == set()


def test_une_part_calculee_dans_sa_ligne_n_est_pas_inventee(tmp_path: Path) -> None:
    """200 000 € / 850 M€ du socle = 0,024 %."""
    chemin = _docx(
        tmp_path,
        ["Acteur", "CA estimé", "Part du marché national (%)"],
        [["Intégrateur IA", "200 000 €", "0,024 %"]],
    )
    assert "0,024 %" not in _signales(chemin)


def test_une_part_qui_ne_tombe_pas_juste_reste_signalee(tmp_path: Path) -> None:
    """CONTRE-ÉPREUVE : 200 000 € / 850 M€ ne fait pas 3,7 %."""
    chemin = _docx(
        tmp_path,
        ["Acteur", "CA estimé", "Part du marché national (%)"],
        [["Intégrateur IA", "200 000 €", "3,7 %"]],
    )
    assert "3,7 %" in _signales(chemin)


def test_sans_en_tete_de_part_un_rapport_juste_ne_suffit_pas(tmp_path: Path) -> None:
    """CONTRE-ÉPREUVE : un taux quelconque ne devient pas une part par coïncidence."""
    chemin = _docx(
        tmp_path,
        ["Acteur", "CA estimé", "Taux de marge"],
        [["Intégrateur IA", "200 000 €", "0,024 %"]],
    )
    assert "0,024 %" in _signales(chemin)


def test_une_ligne_qui_porte_son_adresse_est_sourcee(tmp_path: Path) -> None:
    chemin = _docx(
        tmp_path,
        ["Organisme", "Adresse", "Donnée retenue"],
        [["Service Public Entreprendre", "https://entreprendre.service-public.gouv.fr/F38497",
          "Seuil de régime simplifié : 83 600 €"]],
    )
    assert "83 600 €" not in _signales(chemin)


def test_un_seuil_legal_cite_par_son_article_est_source(tmp_path: Path) -> None:
    from docx import Document

    document = Document()
    document.add_paragraph(
        "Le plafond de la micro-entreprise est de 77 700 € pour les prestations de "
        "services (article 50-0 du code général des impôts)."
    )
    chemin = tmp_path / "loi.docx"
    document.save(str(chemin))
    assert "77 700 €" not in _signales(chemin)


def test_une_cellule_qui_est_une_phrase_se_juge_aussi_par_elle_meme(tmp_path: Path) -> None:
    """Stratégie `0ad5155b` : l'estimation déclarée DANS la cellule compte."""
    chemin = _docx(
        tmp_path,
        ["Critère", "Verdict", "Pourquoi"],
        [["Marché porteur", "Modérément",
          "le marché national est estimé à 150 M€ sans source dédiée, et l'objectif "
          "à trois ans ne représente que 0,46 % de ce total"]],
    )
    assert "0,46 %" not in _signales(chemin)


# ── Les zéros d'un tableau ───────────────────────────────────────────────────


def _zeros(chemin: Path) -> set[str]:
    from generation.verification.controles import controler_les_valeurs_nulles

    return {a.extrait for a in controler_les_valeurs_nulles(lire_livrable(chemin))}


def test_un_ecart_nul_est_un_resultat_pas_une_donnee_manquante(tmp_path: Path) -> None:
    """« Écart | 27 600 € | 27 600 € | 0 € » vérifie l'équilibre du plan."""
    chemin = _docx(
        tmp_path, ["Écart", "Besoins", "Ressources", "Solde"],
        [["Total du plan", "27 600 €", "27 600 €", "0 €"]],
    )
    assert _zeros(chemin) == set()


def test_un_financement_ecarte_par_decision_assume_son_zero(tmp_path: Path) -> None:
    chemin = _docx(
        tmp_path, ["Ressource", "Montant", "Part du total", "Commentaire"],
        [["Emprunt bancaire", "0 €", "0 %", "Non priorisé dans le scénario central"]],
    )
    assert _zeros(chemin) == set()


def test_un_zero_pose_sur_une_donnee_manquante_reste_signale(tmp_path: Path) -> None:
    """CONTRE-ÉPREUVE : « non mesuré » ne devient pas « aucun » parce qu'un autre mot l'est."""
    chemin = _docx(
        tmp_path, ["Indicateur", "Valeur", "Commentaire"],
        [["Coût d'acquisition", "0 €", "non mesuré à ce jour, aucun suivi commercial"]],
    )
    assert _zeros(chemin)


def test_une_evolution_nulle_est_un_resultat(tmp_path: Path) -> None:
    """Corpus du 14/09/2026 : six études concurrentielles, « 0 % (stable) »."""
    chemin = _docx(
        tmp_path, ["Concurrent", "CA 2024", "CA 2025", "Évolution"],
        [["Boulangerie Bosc", "255 000 €", "255 000 €", "0,0 %"]],
    )
    assert _zeros(chemin) == set()


def test_un_ecart_nomme_par_la_ligne_est_un_resultat(tmp_path: Path) -> None:
    """« Montant : Écart | 0 € » : le mot nomme la ligne, pas la colonne."""
    chemin = _docx(
        tmp_path, ["Poste", "Montant"],
        [["Besoins", "27 600 €"], ["Ressources", "27 600 €"], ["Écart", "0 €"]],
    )
    assert _zeros(chemin) == set()


def test_un_zero_commente_dans_sa_cellule_est_assume(tmp_path: Path) -> None:
    chemin = _docx(
        tmp_path, ["Statut", "Chiffre d'affaires", "Budget associé", "Part récurrente"],
        [
            ["Micro-entreprise", "54 276 €", "0 € (déjà en place)", "0 % avant lancement"],
            ["Recrutement salarié", "Non engagé à ce stade", "0 €", "Absent du projet"],
        ],
    )
    assert _zeros(chemin) == set()


def test_un_zero_nu_ou_commente_d_un_manque_reste_signale(tmp_path: Path) -> None:
    """CONTRE-ÉPREUVE : un commentaire qui dit que la donnée MANQUE n'assume rien."""
    chemin = _docx(
        tmp_path, ["Indicateur", "Valeur", "Statut"],
        [
            ["Coût d'acquisition d'un abonné", "non mesuré (0 €)", "Estimée"],
            ["Taux de conversion", "0 %", "Estimée"],
        ],
    )
    assert len(_zeros(chemin)) == 2


# ── Les frontières de la règle du zéro commenté (relecture du 14/09/2026) ────


@pytest.mark.parametrize(
    ("valeur", "commentaire"),
    [
        ("0 € (non chiffré)", "Statut"),
        ("0 € (à déterminer)", "Statut"),
        ("0 € par client", "Statut"),
        ("0 % du CA", "Statut"),
    ],
)
def test_un_complement_d_unite_ou_un_manque_n_est_pas_un_commentaire(
    tmp_path: Path, valeur: str, commentaire: str,
) -> None:
    """CONTRE-ÉPREUVE : « par client », « du CA » complètent l'unité.

    « non chiffré », « à déterminer » disent que la donnée manque.
    """
    chemin = _docx(tmp_path, ["Indicateur", "Valeur", "Note"], [["Coût", valeur, commentaire]])
    assert _zeros(chemin)


def test_la_cellule_du_zero_se_trouve_par_sa_position(tmp_path: Path) -> None:
    """CONTRE-ÉPREUVE : « 0 % » est aussi dans « 40 % ».

    L'autre cellule ne commente pas le zéro.
    """
    chemin = _docx(
        tmp_path, ["Indicateur", "Objectif", "Valeur"],
        [["Taux de transformation", "Conversion, objectif 40 %", "0 %"]],
    )
    assert _zeros(chemin)


def test_des_absences_couvertes_assument_leur_zero(tmp_path: Path) -> None:
    chemin = _docx(
        tmp_path, ["Poste", "Montant", "Note"], [["Remplacement", "0 €", "absences couvertes"]],
    )
    assert _zeros(chemin) == set()


def test_un_poste_absent_du_projet_assume_son_zero(tmp_path: Path) -> None:
    """Business plan `b8da2640` : « Absent du projet | 0 € » — « absences » ne
    devait pas faire perdre « absent »."""
    chemin = _docx(
        tmp_path, ["Poste", "Situation", "Valorisation retenue"],
        [["Local ou droit au bail personnel", "Absent du projet", "0 €"]],
    )
    assert _zeros(chemin) == set()


# ── Une estimation établie en tableau, reprise en prose (corpus du 14/09/2026) ─


def _tableau_puis_prose(
    tmp_path: Path, entetes: list[str], ligne: list[str], prose: str,
) -> Path:
    from docx import Document

    document = Document()
    table = document.add_table(rows=2, cols=len(entetes))
    for colonne, (entete, valeur) in enumerate(zip(entetes, ligne, strict=True)):
        table.cell(0, colonne).text = entete
        table.cell(1, colonne).text = valeur
    document.add_paragraph(prose)
    chemin = tmp_path / "reprise.docx"
    document.save(str(chemin))
    return chemin


def test_une_estimation_etablie_en_tableau_peut_etre_reprise(tmp_path: Path) -> None:
    chemin = _tableau_puis_prose(
        tmp_path, ["Concurrent", "CA estimé", "Part de marché estimée"],
        ["Cabinet de Nantes", "250 000 €", "0,029 %"],
        "Le projet se placerait entre le cabinet de Nantes (250 000 euros, 0,029 %) "
        "et les grands acteurs.",
    )
    assert not _signales(chemin) & {"250 000 euros", "0,029 %"}


def test_une_valeur_voisine_ou_non_etablie_reste_signalee(tmp_path: Path) -> None:
    """CONTRE-ÉPREUVE : une autre valeur, un tableau sans estimation déclarée, un
    nombre à un chiffre significatif."""
    chemin = _tableau_puis_prose(
        tmp_path, ["Concurrent", "CA estimé", "Part de marché estimée"],
        ["Cabinet de Nantes", "250 000 €", "0,1 %"],
        "Un acteur à 260 000 euros détient 0,1 % du marché.",
    )
    assert {"260 000 euros", "0,1 %"} <= _signales(chemin)
    non_declare = _tableau_puis_prose(
        tmp_path, ["Concurrent", "CA", "Part de marché"],
        ["Cabinet de Nantes", "250 000 €", "0,029 %"],
        "Le cabinet de Nantes (250 000 euros) domine.",
    )
    # La PART reste établie : elle tombe juste sur 250 000 / 850 M€ du socle.
    # Le chiffre d'affaires, lui, n'a jamais été déclaré estimé.
    assert "250 000 euros" in _signales(non_declare)

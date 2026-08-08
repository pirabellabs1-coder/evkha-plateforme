"""Lot 3 — assemblage du livrable Word et conversion PDF.

Le test central de ce lot n'est pas qu'un document sorte : c'est qu'**aucune
valeur ne puisse être fabriquée au rendu**. Un graphique inventé est
indétectable à la lecture, contrairement à un graphique absent. Chaque cas où
le socle ne peut pas alimenter une figure est donc vérifié ici, avec sa
contre-épreuve : le cas nourrissable doit passer (règle 6).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from generation.chapitres.schema import ChapitrePayload
from generation.rendu_word import secteurs
from generation.rendu_word.assemblage import (
    MOTS_AMORCE_MAX,
    RapportAssemblage,
    assembler_etude,
)
from generation.rendu_word.depuis_json import rendre_etude
from generation.rendu_word.donnees_graphiques import resoudre
from generation.rendu_word.logo import charger_logo, format_image
from generation.socle.schema import Socle
from integrations.docx_pdf import BouchonConvertisseurDocx, ConversionPdfError

# ── Socles de test ───────────────────────────────────────────────────────────


def _donnee(
    identifiant: str,
    libelle: str,
    valeur: float,
    unite: str = "MdEUR",
    annee: int = 2025,
) -> dict[str, Any]:
    return {
        "id": identifiant, "libelle": libelle, "valeur": valeur, "unite": unite,
        "annee": annee, "perimetre": "monde", "source": "Source de test",
        "fiabilite": "observee", "derivee_de": [],
    }


def _socle(**remplacements: Any) -> Socle:
    base: dict[str, Any] = {
        "secteur": "joaillerie de créateurs",
        "zone": {"pays": "France", "region": "Île-de-France", "ville": "Paris"},
        "date_socle": date(2026, 1, 15).isoformat(),
        "donnees": [
            _donnee("marche_mondial", "Marché mondial", 381.5),
            _donnee("marche_continental", "Marché continental", 37.0),
            _donnee("marche_national", "Marché national", 5.9),
        ],
        "segments_clientele": [],
        "concurrents": [],
        "tendances": [],
        "risques": [],
    }
    base.update(remplacements)
    return Socle.model_validate(base)


@pytest.fixture
def socle() -> Socle:
    return _socle()


# ── Aucune valeur n'est fabriquée ────────────────────────────────────────────


def test_un_identifiant_absent_du_socle_abandonne_le_graphique(socle: Socle) -> None:
    """Le cœur du lot : pas de donnée, pas de figure. Jamais d'à-peu-près."""
    resolution = resoudre(socle, "barres", ["marche_mondial", "identifiant_fantome"])
    assert not resolution.retenu
    assert "identifiant_fantome" in resolution.motif


def test_un_identifiant_present_alimente_le_graphique(socle: Socle) -> None:
    """Contre-épreuve : le contrôle ne doit pas bloquer ce qui est correct."""
    resolution = resoudre(socle, "barres", ["marche_mondial", "marche_continental"])
    assert resolution.retenu
    assert resolution.donnees is not None
    assert resolution.donnees["valeurs"] == [381.5, 37.0]
    assert resolution.donnees["etiquettes"] == ["Marché mondial", "Marché continental"]


def test_des_unites_heterogenes_sont_refusees() -> None:
    """Deux grandeurs d'unités différentes sur un même axe font une figure fausse."""
    socle = _socle(donnees=[
        _donnee("marche_mondial", "Marché mondial", 381.5, "MdEUR"),
        _donnee("part_premium", "Part premium", 12.0, "%"),
    ])
    resolution = resoudre(socle, "barres", ["marche_mondial", "part_premium"])
    assert not resolution.retenu
    assert "unités hétérogènes" in resolution.motif


def test_un_seul_chiffre_ne_fait_pas_un_graphique(socle: Socle) -> None:
    resolution = resoudre(socle, "barres", ["marche_mondial"])
    assert not resolution.retenu


def test_une_part_negative_est_refusee_en_camembert() -> None:
    socle = _socle(donnees=[
        _donnee("a", "A", 60.0, "%"), _donnee("b", "B", -10.0, "%"),
    ])
    assert not resoudre(socle, "camembert", ["a", "b"]).retenu


def test_l_entonnoir_se_lit_du_plus_large_au_plus_etroit(socle: Socle) -> None:
    resolution = resoudre(
        socle, "entonnoir",
        ["marche_national", "marche_mondial", "marche_continental"],
    )
    assert resolution.donnees is not None
    valeurs = [valeur for _, valeur in resolution.donnees["etapes"]]
    assert valeurs == sorted(valeurs, reverse=True)


def test_une_courbe_sans_axe_temporel_devient_des_barres(socle: Socle) -> None:
    """Conversion plutôt qu'abandon : les chiffres sont bons, l'axe manque."""
    resolution = resoudre(
        socle, "courbes", ["marche_mondial", "marche_continental"]
    )
    assert resolution.retenu
    assert resolution.converti
    assert resolution.type_graphique == "barres"


def test_une_courbe_avec_plusieurs_annees_reste_une_courbe() -> None:
    socle = _socle(donnees=[
        _donnee("m1", "Marché mondial", 350.0, annee=2023),
        _donnee("m2", "Marché mondial", 366.0, annee=2024),
        _donnee("m3", "Marché mondial", 381.5, annee=2025),
    ])
    resolution = resoudre(socle, "courbes", ["m1", "m2", "m3"])
    assert resolution.retenu
    assert not resolution.converti
    assert resolution.donnees is not None
    assert resolution.donnees["abscisses"] == ["2023", "2024", "2025"]
    assert resolution.donnees["series"] == [("Marché mondial", [350.0, 366.0, 381.5])]


def test_une_serie_trouee_n_est_jamais_interpolee() -> None:
    """Une valeur manquante fait mentir la pente : la série est écartée."""
    socle = _socle(donnees=[
        _donnee("a1", "Mondial", 350.0, annee=2023),
        _donnee("a2", "Mondial", 366.0, annee=2024),
        _donnee("b1", "Continental", 31.0, annee=2023),
    ])
    resolution = resoudre(socle, "courbes", ["a1", "a2", "b1"])
    assert resolution.retenu
    assert resolution.donnees is not None
    assert [nom for nom, _ in resolution.donnees["series"]] == ["Mondial"]


def test_les_jauges_exigent_des_notes(socle: Socle) -> None:
    """Des milliards d'euros affichés sur une échelle de 1 à 5 seraient absurdes."""
    resolution = resoudre(
        socle, "jauges", ["marche_mondial", "marche_continental"]
    )
    assert not resolution.retenu
    assert "notes" in resolution.motif


def test_des_notes_alimentent_les_jauges() -> None:
    socle = _socle(donnees=[
        _donnee("n1", "Attractivité", 4.4, "note_sur_5"),
        _donnee("n2", "Différenciation", 4.6, "note_sur_5"),
    ])
    resolution = resoudre(socle, "jauges", ["n1", "n2"])
    assert resolution.retenu
    assert resolution.donnees is not None
    assert resolution.donnees["maximum"] == 5.0


def test_la_matrice_exige_des_risques_notes(socle: Socle) -> None:
    assert not resoudre(socle, "matrice_positionnement", []).retenu


def test_des_risques_notes_alimentent_la_matrice_et_la_carte() -> None:
    socle = _socle(risques=[
        {"intitule": "Notoriété", "probabilite": 4, "impact": 4, "description": ""},
        {"intitule": "Stock", "probabilite": 3, "impact": 5, "description": ""},
    ])
    matrice = resoudre(socle, "matrice_positionnement", [])
    chaleur = resoudre(socle, "carte_chaleur", [])
    assert matrice.retenu
    assert chaleur.retenu
    assert matrice.donnees is not None
    assert matrice.donnees["points"][0] == ("Notoriété", 4.0, 4.0)


def test_un_risque_sans_note_ne_compte_pas() -> None:
    """Règle 1 : ne pas juger avec une donnée absente plutôt que juger mal."""
    socle = _socle(risques=[
        {"intitule": "Notoriété", "probabilite": None, "impact": None,
         "description": ""},
        {"intitule": "Stock", "probabilite": 3, "impact": 5, "description": ""},
    ])
    assert not resoudre(socle, "matrice_positionnement", []).retenu


def test_la_pyramide_des_ages_est_declaree_inalimentable(socle: Socle) -> None:
    """Manque assumé du référentiel, tracé plutôt que contourné.

    Le socle du lot 1 ne porte aucune structure démographique. Le type existe
    au catalogue et les profils « santé » et « services à la personne » le
    privilégient : l'abandon doit donc être explicite et remonter dans le
    rapport, pour que la décision — étendre le référentiel ou retirer le type —
    soit prise sciemment.
    """
    resolution = resoudre(socle, "pyramide_ages", ["marche_mondial"])
    assert not resolution.retenu
    assert "démographique" in resolution.motif


def test_un_type_inconnu_est_refuse_et_non_devine(socle: Socle) -> None:
    assert not resoudre(socle, "camembert_3d", ["marche_mondial"]).retenu


# ── Assemblage ───────────────────────────────────────────────────────────────


def _chapitre(numero: int = 1, **remplacements: Any) -> ChapitrePayload:
    base: dict[str, Any] = {
        "chapitre": numero,
        "titre": "Marché mondial et continent pertinent",
        "accroche": "Un marché large, mais une niche définie.",
        "sections": [{
            "titre": "Deux périmètres à ne pas confondre",
            "contenu": "Le périmètre le plus proche du projet est la niche premium.",
            "tableau": {
                "entetes": ["Périmètre", "Valeur", "Source"],
                "lignes": [["Mondial", "381,5 Md€", "Grand View"],
                           ["Continental", "37 Md€", "Bain"]],
                "source": "Périmètres emboîtés.",
            },
        }],
        "encadres": [{
            "intitule": "Lecture EVKHA",
            "lignes": ["Opportunité — dynamique favorable.",
                       "Limite — le marché accessible est plus étroit."],
        }],
        "donnees_utilisees": ["marche_mondial", "marche_continental"],
        "graphiques": [{
            "type": "barres", "titre": "Poids des périmètres",
            "donnees_ids": ["marche_mondial", "marche_continental"],
            "commentaire": "Analyse EVKHA.",
        }],
        "resume": "Le marché mondial est large ; la niche est plus étroite.",
    }
    base.update(remplacements)
    return ChapitrePayload.model_validate(base)


def test_l_assemblage_produit_les_blocs_attendus(socle: Socle) -> None:
    etude, rapport = assembler_etude(
        socle=socle, chapitres=[_chapitre()], titre="Étude de marché"
    )
    types = [bloc["type"] for bloc in etude["chapitres"][0]["blocs"]]
    assert types[0] == "bandeau"
    assert "sous_titre" in types
    assert "tableau" in types
    assert "graphique" in types
    assert types[-1] == "encadre", (
        "le chapitre se ferme sur son verdict — une figure de complétion "
        "posée dessous le repousserait hors de vue"
    )
    # La figure DÉCLARÉE par le chapitre est rendue. Le total, lui, n'est plus
    # figé : l'assemblage complète depuis le socle jusqu'au plancher exigé par
    # la cliente (dix-sept figures), et cette maquette d'un seul chapitre en
    # déclenche donc quelques-unes. Ce que ce test tient, c'est la STRUCTURE
    # des blocs ; le plancher a son propre fichier.
    assert rapport.graphiques_rendus >= 1
    assert rapport.graphiques_rendus - len(rapport.graphiques_completes) == 1
    assert rapport.complet


def test_les_chapitres_sont_rendus_dans_l_ordre_de_lecture(socle: Socle) -> None:
    """La génération est parallèle ; la lecture ne l'est pas."""
    etude, _ = assembler_etude(
        socle=socle,
        chapitres=[_chapitre(7), _chapitre(2), _chapitre(4)],
        titre="Étude de marché",
    )
    assert [c["numero"] for c in etude["chapitres"]] == [2, 4, 7]


def test_un_graphique_abandonne_est_trace_et_le_document_reste_produit(
    socle: Socle,
) -> None:
    """Règle 1 : échouer bruyamment, sans perdre le livrable."""
    chapitre = _chapitre(graphiques=[{
        "type": "barres", "titre": "Figure impossible",
        "donnees_ids": ["marche_mondial", "identifiant_fantome"],
        "commentaire": "",
    }], donnees_utilisees=["marche_mondial", "identifiant_fantome"])
    etude, rapport = assembler_etude(
        socle=socle, chapitres=[chapitre], titre="Étude de marché"
    )
    assert rapport.graphiques_rendus == 0
    assert not rapport.complet
    assert "Figure impossible" in rapport.graphiques_abandonnes[0]
    assert etude["chapitres"][0]["blocs"], "Le chapitre doit rester rendu."


def test_un_type_hors_sujet_pour_le_secteur_est_ecarte() -> None:
    """La contrainte sectorielle vaut aussi à l'assemblage, pas seulement au prompt."""
    socle = _socle(secteur="cabinet de conseil en stratégie")
    profil = secteurs.profil_du_secteur(socle.secteur)
    assert "pyramide_ages" in profil.graphiques_a_eviter

    chapitre = _chapitre(graphiques=[{
        "type": "pyramide_ages", "titre": "Pyramide", "donnees_ids": ["marche_mondial"],
        "commentaire": "",
    }], donnees_utilisees=["marche_mondial"])
    _, rapport = assembler_etude(
        socle=socle, chapitres=[chapitre], titre="Étude de marché"
    )
    assert not rapport.complet
    assert "hors sujet" in rapport.graphiques_abandonnes[0]


def test_la_prose_d_une_section_est_ramenee_a_une_amorce(socle: Socle) -> None:
    """La densité validée par la cliente ne doit pas se perdre à l'assemblage."""
    pave = " ".join(["Le marché premium progresse nettement cette année."] * 30)
    chapitre = _chapitre(sections=[{
        "titre": "Section bavarde", "contenu": pave, "tableau": None,
    }])
    etude, _ = assembler_etude(
        socle=socle, chapitres=[chapitre], titre="Étude de marché"
    )
    paragraphes = [
        bloc["texte"] for bloc in etude["chapitres"][0]["blocs"]
        if bloc["type"] == "paragraphe"
    ]
    assert paragraphes
    assert len(paragraphes[0].split()) <= MOTS_AMORCE_MAX


def test_une_amorce_ne_coupe_pas_au_milieu_d_une_phrase(socle: Socle) -> None:
    pave = " ".join(["Le marché premium progresse nettement cette année."] * 30)
    chapitre = _chapitre(sections=[{
        "titre": "Section bavarde", "contenu": pave, "tableau": None,
    }])
    etude, _ = assembler_etude(
        socle=socle, chapitres=[chapitre], titre="Étude de marché"
    )
    amorce = next(
        bloc["texte"] for bloc in etude["chapitres"][0]["blocs"]
        if bloc["type"] == "paragraphe"
    )
    assert amorce.endswith(".")


def test_une_section_courte_n_est_pas_tronquee(socle: Socle) -> None:
    """Contre-épreuve : l'amorce ne doit pas mutiler ce qui est déjà court."""
    etude, _ = assembler_etude(
        socle=socle, chapitres=[_chapitre()], titre="Étude de marché"
    )
    amorce = next(
        bloc["texte"] for bloc in etude["chapitres"][0]["blocs"]
        if bloc["type"] == "paragraphe"
    )
    assert amorce == "Le périmètre le plus proche du projet est la niche premium."


def test_un_encadre_de_verdict_prend_le_fond_soutenu(socle: Socle) -> None:
    chapitre = _chapitre(encadres=[
        {"intitule": "Verdict — conditions", "lignes": ["Potentiel favorable."]},
        {"intitule": "Lecture EVKHA", "lignes": ["Opportunité réelle."]},
    ])
    etude, _ = assembler_etude(
        socle=socle, chapitres=[chapitre], titre="Étude de marché"
    )
    encadres = [
        bloc for bloc in etude["chapitres"][0]["blocs"] if bloc["type"] == "encadre"
    ]
    assert encadres[0]["verdict"] is True
    assert encadres[1]["verdict"] is False


def test_le_rapport_resume_ce_qui_a_ete_fait() -> None:
    rapport = RapportAssemblage(
        graphiques_demandes=3, graphiques_rendus=2, chapitres=22, tableaux=40,
        graphiques_abandonnes=["Chapitre 4 · Figure : motif"],
    )
    assert not rapport.complet
    assert "2/3 graphiques" in rapport.resume()


# ── Le document sort réellement ──────────────────────────────────────────────


def test_le_livrable_est_rendu_de_bout_en_bout(socle: Socle, tmp_path: Path) -> None:
    """Règle 7 : le vert des tests unitaires ne dit rien du fichier produit."""
    etude, _ = assembler_etude(
        socle=socle,
        chapitres=[_chapitre(numero) for numero in range(1, 6)],
        titre="Étude de marché",
        marque={"nom": "Joalie", "couleur_principale": "#3A132C",
                "couleur_secondaire": "#B98B4E", "couleur_fond": "#F1EEDB"},
    )
    chemin = rendre_etude(etude, tmp_path / "livrable.docx")
    assert chemin.is_file()
    assert chemin.stat().st_size > 20_000


def test_le_rendu_n_appelle_pas_le_reseau_quand_le_logo_est_fourni(
    socle: Socle, tmp_path: Path
) -> None:
    """Des octets fournis l'emportent sur l'URL : un test ne sort jamais du poste."""
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
        b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    etude, _ = assembler_etude(
        socle=socle, chapitres=[_chapitre()], titre="Étude de marché",
        marque={"nom": "Joalie", "logo_url": "https://exemple.invalide/logo.png"},
    )
    etude["logo"] = png
    assert rendre_etude(etude, tmp_path / "avec-logo.docx").is_file()


# ── Logo ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("contenu", "attendu"),
    [
        (b"\x89PNG\r\n\x1a\n reste", "png"),
        (b"\xff\xd8\xff\xe0 reste", "jpeg"),
        (b"GIF89a reste", "gif"),
        (b"<svg xmlns=...>", None),
        (b"<!doctype html>", None),
    ],
)
def test_le_format_du_logo_est_lu_dans_les_octets(
    contenu: bytes, attendu: str | None
) -> None:
    """Jamais dans l'en-tête `Content-Type`, qui n'engage que son émetteur."""
    assert format_image(contenu) == attendu


@pytest.mark.parametrize(
    "url", ["", "   ", "file:///etc/passwd", "data:image/png;base64,AAAA", "ftp://x/y.png"]
)
def test_une_url_de_logo_non_http_est_refusee_sans_appel_reseau(url: str) -> None:
    assert charger_logo(url) is None


# ── Chemin réel : depuis la base ─────────────────────────────────────────────
# Les tests précédents travaillent sur des objets en mémoire. Ceux-ci passent
# par le job, le socle verrouillé et les chapitres persistés — c'est le chemin
# que le client emprunte réellement.


@pytest.fixture
def job_rendu(db: object) -> Any:
    from catalog.models import DeliverableType, Offer
    from customers.models import Customer
    from generation.models import (
        ChapterGeneration,
        ChapterStatus,
        SocleDonnees,
        SocleStatut,
    )
    from generation.services import bootstrap_generation_job
    from intake.models import IntakeStatus, IntakeSubmission
    from orders.models import Order

    offre = Offer.objects.create(
        name="Étude de marché", slug="em-lot3",
        deliverable_type=DeliverableType.MARKET_STUDY,
    )
    client = Customer.objects.create(email="lot3@example.com")
    commande = Order.objects.create(
        systeme_order_id="order-lot3-01", customer=client, offer=offre
    )
    soumission = IntakeSubmission.objects.create(
        order=commande, status=IntakeStatus.NORMALIZED,
        normalized_variables={
            "SECTEUR": "joaillerie de créateurs", "PAYS": "France",
            "NOM_ENTREPRISE": "Joalie", "COULEUR_PRINCIPALE": "#3A132C",
            "COULEUR_SECONDAIRE": "#B98B4E",
        },
    )
    job = bootstrap_generation_job(soumission)

    SocleDonnees.objects.create(
        job=job, statut=SocleStatut.VALIDE,
        contenu=_socle().model_dump(mode="json"),
    )
    # `bootstrap_generation_job` crée déjà la ligne de chaque chapitre prévu :
    # on la complète, on ne la double pas.
    for numero in (1, 2, 3):
        ChapterGeneration.objects.update_or_create(
            job=job, chapter_number=numero,
            defaults={
                "chapter_title": f"Chapitre {numero}",
                "prompt_key": f"chapitre_{numero:02d}",
                "status": ChapterStatus.DONE,
                "payload": _chapitre(numero).model_dump(mode="json"),
            },
        )
    return job


def test_le_livrable_est_produit_depuis_la_base(job_rendu: Any, tmp_path: Path) -> None:
    from generation.rendu_word.services import produire_docx

    livrable = produire_docx(job_rendu, destination=tmp_path / "reel.docx")
    assert livrable.chemin.is_file()
    assert livrable.rapport.chapitres == 3
    assert livrable.rapport.complet
    assert livrable.etude["marque"]["nom"] == "Joalie"
    assert livrable.etude["marque"]["couleur_principale"] == "#3A132C"


def test_un_chapitre_sans_payload_structure_est_ignore(job_rendu: Any) -> None:
    """Mélanger l'ancien et le nouveau moteur produirait un document bâtard.

    Une incohérence de charte au milieu du document se voit ; une absence non.
    On préfère l'absence, tracée dans le journal.
    """
    from generation.models import ChapterGeneration, ChapterStatus
    from generation.rendu_word.services import payloads_du_job

    ChapterGeneration.objects.update_or_create(
        job=job_rendu, chapter_number=9,
        defaults={
            "chapter_title": "Ancien moteur", "prompt_key": "chapitre_09",
            "status": ChapterStatus.DONE, "payload": {},
            "content": "# Texte markdown de l'ancien moteur",
        },
    )
    assert [p.chapitre for p in payloads_du_job(job_rendu)] == [1, 2, 3]


def test_sans_socle_verrouille_le_rendu_echoue_au_lieu_d_inventer(
    job_rendu: Any, tmp_path: Path
) -> None:
    """Règle 1 : échouer bruyamment plutôt que produire un document sans chiffres."""
    from generation.models import SocleDonnees
    from generation.rendu_word.services import LivrableIncompletError, produire_docx

    SocleDonnees.objects.filter(job=job_rendu).delete()
    with pytest.raises(LivrableIncompletError):
        produire_docx(job_rendu, destination=tmp_path / "ko.docx")


def test_les_deux_artefacts_sont_enregistres(job_rendu: Any) -> None:
    from documents.livrable_word import assembler_livrable_word
    from documents.models import ArtifactKind, ArtifactStatus

    assemble = assembler_livrable_word(
        job_rendu, convertisseur=BouchonConvertisseurDocx()
    )
    assert assemble.docx.kind == ArtifactKind.DOCX
    assert assemble.docx.status == ArtifactStatus.READY
    assert assemble.docx.checksum_sha256
    assert assemble.pdf is not None
    assert assemble.pdf.status == ArtifactStatus.READY


def test_une_conversion_ratee_ne_perd_pas_le_word(job_rendu: Any) -> None:
    """Le client a payé pour un livrable, pas pour une chaîne d'outils."""
    from documents.livrable_word import assembler_livrable_word
    from documents.models import ArtifactStatus

    class ConvertisseurEnPanne:
        def convertir(self, source: Path, destination: Path) -> Any:
            msg = "LibreOffice absent."
            raise ConversionPdfError(msg)

    assemble = assembler_livrable_word(
        job_rendu, convertisseur=ConvertisseurEnPanne()
    )
    assert assemble.docx.status == ArtifactStatus.READY
    assert assemble.pdf is not None
    assert assemble.pdf.status == ArtifactStatus.FAILED


def test_l_assemblage_est_idempotent(job_rendu: Any) -> None:
    """Une relance met à jour les artefacts au lieu d'en empiler."""
    from documents.livrable_word import assembler_livrable_word
    from documents.models import DocumentArtifact

    for _ in range(2):
        assembler_livrable_word(job_rendu, convertisseur=BouchonConvertisseurDocx())
    assert DocumentArtifact.objects.filter(job=job_rendu).count() == 2


# ── La consigne parvient au modèle ───────────────────────────────────────────
# Le contrat autorise les tableaux et les quinze types de graphiques ; encore
# faut-il que le modèle sache qu'il doit s'en servir, et lesquels. Sans ces
# blocs, une génération réelle reproduirait le mur de texte refusé par la
# cliente — le schéma le permettrait, rien ne l'exigerait.


def test_le_prompt_impose_les_tableaux_et_l_amorce(job_rendu: Any) -> None:
    from generation.chapitres.configuration import type_document
    from generation.chapitres.runner import construire_prompt_chapitre
    from generation.models import ChapterGeneration
    from generation.socle.services import socle_verrouille

    chapitre = ChapterGeneration.objects.get(job=job_rendu, chapter_number=2)
    socle = socle_verrouille(job_rendu)
    assert socle is not None
    prompt, _ = construire_prompt_chapitre(
        chapitre, socle=socle, variables={"SECTEUR": socle.secteur},
        document=type_document(str(job_rendu.deliverable_type)),
    )
    # La consigne générique « FORME ATTENDUE » décrivait la MOYENNE des
    # vingt-et-un chapitres. Elle est remplacée, pour les livrables que le
    # modèle décrit, par le plan de CE chapitre — plus exigeant, et vérifiable :
    # le validateur de conformité juge sur le même fichier.
    assert "PLAN IMPOSÉ DU CHAPITRE 02" in prompt
    assert "DANS CET ORDRE" in prompt
    assert "`tableau`" in prompt
    assert "`encadre`" in prompt
    # Et l'exemple de rédaction, avec l'interdiction d'en reprendre les chiffres.
    assert "EXEMPLE — chapitre 02" in prompt
    assert "AUCUN chiffre" in prompt


def test_le_prompt_porte_le_catalogue_et_le_profil_du_secteur(job_rendu: Any) -> None:
    from generation.chapitres.configuration import type_document
    from generation.chapitres.runner import construire_prompt_chapitre
    from generation.models import ChapterGeneration
    from generation.socle.services import socle_verrouille

    chapitre = ChapterGeneration.objects.get(job=job_rendu, chapter_number=2)
    socle = socle_verrouille(job_rendu)
    assert socle is not None
    prompt, _ = construire_prompt_chapitre(
        chapitre, socle=socle, variables={"SECTEUR": socle.secteur},
        document=type_document(str(job_rendu.deliverable_type)),
    )
    profil = secteurs.profil_du_secteur(socle.secteur)
    assert profil.code == "luxe_joaillerie"
    assert profil.libelle in prompt
    assert "`entonnoir`" in prompt
    # Contre-épreuve : les types proscrits doivent être nommés comme tels.
    assert "pyramide_ages" in prompt
    assert "à ne pas employer" in prompt


def test_le_pont_markdown_ne_perd_pas_les_tableaux() -> None:
    """L'ancienne chaîne consomme ce markdown : un tableau perdu y serait muet."""
    from generation.chapitres.runner import payload_vers_markdown

    markdown = payload_vers_markdown(_chapitre())
    assert "| Périmètre | Valeur | Source |" in markdown
    assert "| Mondial | 381,5 Md€ | Grand View |" in markdown


# ── Conversion PDF ───────────────────────────────────────────────────────────


def test_le_bouchon_de_conversion_produit_un_fichier(tmp_path: Path) -> None:
    source = tmp_path / "livrable.docx"
    source.write_bytes(b"PK\x03\x04 contenu word simule")
    conversion = BouchonConvertisseurDocx().convertir(source, tmp_path / "out.pdf")
    assert conversion.chemin.is_file()
    assert conversion.chemin.read_bytes().startswith(b"%PDF-")


def test_le_bouchon_ne_pretend_pas_connaitre_le_nombre_de_pages(
    tmp_path: Path,
) -> None:
    """Zéro signifie « inconnu », jamais « conforme » (règle 1)."""
    source = tmp_path / "livrable.docx"
    source.write_bytes(b"PK\x03\x04")
    assert BouchonConvertisseurDocx().convertir(source, tmp_path / "o.pdf").pages == 0


def test_une_source_absente_echoue_au_lieu_de_produire_un_pdf_vide(
    tmp_path: Path,
) -> None:
    with pytest.raises(ConversionPdfError):
        BouchonConvertisseurDocx().convertir(
            tmp_path / "absent.docx", tmp_path / "o.pdf"
        )

"""Relecture, classe 7 : fuites internes et renvois de figures hors sujet.

30/09/2026, business plan ÉCLORE `28a257bf` : la cliente lisait des étiquettes
de notre chaîne (« phrase du client », « Données du socle vérifié »), un
document qui parle de sa source (« selon les termes du dossier », « précisé
dans le dossier », « le client n'a pas arbitré », « aucune ligne n'est
recalculée »), une ligne du cadrage recopiée avec son « AAAA : » de prise de
notes, et un renvoi « Figure présentée au chapitre 1 — … » vers une figure qui
parlait d'autre chose.

Les textes ci-dessous sont FICTIFS (règle de confidentialité) : ils reprennent
la FORME des défauts, jamais les noms ni les chiffres du dossier réel. Chaque
test échoue sur le code d'avant (les contrôles rendaient une liste vide, le
rendu écrivait toujours le renvoi et la légende « Données du socle vérifié ») ;
chaque classe a sa contre-épreuve.
"""
from __future__ import annotations

from datetime import date
from typing import Any, cast

import pytest

from generation.chapitres.schema import ChapitrePayload
from generation.memoire.decisions import JUSTIFICATION_DU_BRIEF
from generation.memoire.etude import MemoireEtude
from generation.memoire.regles import Decision
from generation.relecture import Document, Reference, Section, Tableau, fuites, relire
from generation.relecture.document import document_du_chapitre


def _section(numero: str, titre: str, *paragraphes: str, tableaux: Any = ()) -> Section:
    return Section(numero=numero, titre=titre, chapitre=int(numero.split(".")[0]),
                   paragraphes=list(paragraphes), tableaux=list(tableaux))


def _fuites(document: Document, reference: Reference | None = None) -> list[Any]:
    return [
        c for c in fuites.controler(document, reference or Reference())
        if c.classe == "fuite"
    ]


# ── 1. Le vocabulaire de la chaîne ───────────────────────────────────────────

_FUITES = [
    ("4.2", "Statut : acté pour 2031 | phrase du client, calendrier 2031", "phrase du client"),
    ("5.4", "Données du socle vérifié", "socle vérifié"),
    ("7.1", "Le solde correspond au revenu non prélevé, selon les termes du dossier.",
     "selon les termes du dossier"),
    ("7.2", "Rémunération : Non précisée dans le dossier", "précisée dans le dossier"),
    ("7.3", "Construire cette colonne exigerait des hypothèses que le client n'a pas arbitrées.",
     "le client n'a pas arbitrées"),
    ("7.4", "Le tableau reprend les montants déclarés : aucune ligne n'est recalculée.",
     "aucune ligne n'est recalculée"),
    ("7.5", "Le dossier ne fournit pas de tableau mensuel de trésorerie.",
     "Le dossier ne fournit pas"),
]


@pytest.mark.parametrize(("numero", "texte", "cite"), _FUITES)
def test_chaque_locution_de_la_chaine_est_une_fuite(numero: str, texte: str, cite: str) -> None:
    constats = _fuites(Document(sections=[_section(numero, "Une section", texte)]))
    assert [c.section for c in constats] == [numero], constats
    assert cite in constats[0].detail
    # L'extrait est trouvable tel quel dans le document (règle 2).
    assert constats[0].extrait in texte


def test_une_cellule_de_tableau_est_lue_aussi() -> None:
    """« phrase du client » était imprimé dans une CELLULE, pas dans la prose."""
    tableau = Tableau(
        entetes=("Décision", "Contenu", "Statut"),
        lignes=(("Situation", "Le dirigeant passe à temps plein", "phrase du client, 2031"),),
    )
    constats = _fuites(Document(sections=[_section("4.2", "Phases", tableaux=[tableau])]))
    assert [c.section for c in constats] == ["4.2"]


#: Du français de métier que les motifs frôlent. Relevé à la revue du
#: 30/09/2026 : la première version en refusait la moitié — à la validation des
#: chapitres, donc en payant une réécriture.
_FRANCAIS_DU_METIER = [
    "Le dossier de financement est déposé à la banque en mars.",
    "Les pièces demandées sont précisées dans le dossier d'inscription du salon.",
    "Les soins sont renseignés dans le dossier patient à chaque séance.",
    "Les antécédents sont mentionnés dans le dossier médical.",
    "Le prévisionnel est fourni au dossier bancaire.",
    "Chaque commande est détaillée dans le dossier client.",
    "Si le dossier de candidature ne précise pas le motif, il est refusé.",
    "Le socle de compétences du dirigeant couvre la vente et la gestion.",
    "Un client qui n'a pas acheté depuis six mois reçoit une relance.",
    "Tant que le client n'a pas communiqué ses mesures, la commande attend.",
    "Si la cliente n'a pas précisé sa taille, la retoucheuse la rappelle.",
    "Les prix sont recalculés chaque année sur l'inflation.",
    "Le tableau se met à jour sans qu'aucun recalcul manuel ne soit nécessaire.",
    "La phrase d'accroche de la marque tient en huit mots.",
    "Les phrases des clients interrogés reviennent sur l'accueil.",
    "La phrase du client la plus fréquente en entretien porte sur le prix.",
    "Les termes du contrat de bail sont négociés avant la signature.",
]


@pytest.mark.parametrize("texte", _FRANCAIS_DU_METIER)
def test_contre_epreuve_le_francais_du_metier_passe(texte: str) -> None:
    assert _fuites(Document(sections=[_section("3.1", "Le marché", texte)])) == []


@pytest.mark.parametrize("texte", _FRANCAIS_DU_METIER)
def test_contre_epreuve_la_validation_des_chapitres_le_laisse_passer(texte: str) -> None:
    """La MÊME liste refuse un chapitre payé : la contre-épreuve vaut aussi là."""
    from generation.chapitres.schema import motifs_de_balisage

    payload = ChapitrePayload.model_validate({
        "chapitre": 3, "titre": "Le marché", "accroche": "",
        "blocs": [{"type": "paragraphe", "texte": texte}], "resume": "Résumé.",
    })
    assert not [m for m in motifs_de_balisage(payload) if "DISPOSITIF" in m]


def test_l_extrait_se_retrouve_meme_pres_d_une_adresse() -> None:
    """L'adresse web est écartée à LONGUEUR ÉGALE : l'extrait reste celui du document."""
    texte = "Voir https://exemple.fr/page, selon les termes du dossier."
    (constat,) = _fuites(Document(sections=[_section("7.1", "Trésorerie", texte)]))
    assert constat.extrait in texte and "selon les termes du dossier" in constat.extrait


def test_la_validation_des_chapitres_refuse_ce_que_la_relecture_signale() -> None:
    """Une seule liste (règle 5) : le chapitre est refusé AVANT rendu, sur le même mot."""
    from generation.chapitres.schema import motifs_de_balisage

    payload = ChapitrePayload.model_validate({
        "chapitre": 7, "titre": "Prévisionnel", "accroche": "",
        "blocs": [{"type": "paragraphe",
                   "texte": "Le solde correspond au revenu non prélevé, selon les termes "
                            "du dossier."}],
        "resume": "Résumé.",
    })
    assert any("dossier cité comme source" in m for m in motifs_de_balisage(payload))
    assert _fuites(document_du_chapitre(payload))


# ── 2. Une ligne du cadrage recopiée telle quelle ────────────────────────────


def _reference(*phrases: str) -> Reference:
    return Reference(memoire=MemoireEtude(faits={}, decisions=[
        Decision("calendrier", phrase, 2031, JUSTIFICATION_DU_BRIEF, source="brief")
        for phrase in phrases
    ]))


_LIGNE = "2031 : à temps plein, après la cession de son fonds de commerce."


def test_une_ligne_du_cadrage_collee_est_une_fuite() -> None:
    document = Document(sections=[
        _section("12.1", "Le rôle du dirigeant", "Le dirigeant pilote seul le projet.", _LIGNE),
        _section("19.4", "Objectifs", tableaux=[Tableau(
            entetes=("Année", "Situation"), lignes=(("2031", _LIGNE),),
        )]),
    ])
    constats = _fuites(document, _reference(_LIGNE))
    assert sorted(c.section for c in constats) == ["12.1", "19.4"]
    assert all(c.extrait == _LIGNE.rstrip(".") for c in constats)
    assert all("« 2031 : »" in c.detail for c in constats)


def test_l_extrait_est_ecrit_comme_dans_le_document() -> None:
    """La mémoire écrit en minuscule, le document en majuscule : l'extrait suit le document."""
    ligne = "la trajectoire de statut : micro-entreprise, puis société en fin de période ;"
    document = Document(sections=[_section(
        "19.4", "Objectifs",
        "La trajectoire de statut : micro-entreprise, puis société en fin de période.",
    )])
    (constat,) = _fuites(document, _reference(ligne))
    assert constat.extrait == "La trajectoire de statut : micro-entreprise, puis société en fin" \
        " de période"


def test_la_cesure_du_pdf_ne_cache_pas_la_ligne_collee() -> None:
    """Le PDF rend « micro- entreprise » : la ligne se reconnaît quand même."""
    ligne = "Trajectoire : micro-entreprise de 2029 à 2031, puis passage en société."
    coupee = ligne.replace("micro-entreprise", "micro- entreprise")
    constats = _fuites(Document(sections=[_section("13.1", "Statut", coupee)]),
                       _reference(ligne))
    assert [c.section for c in constats] == ["13.1"]


def test_contre_epreuve_la_decision_redigee_passe() -> None:
    """La décision TENUE, avec les mots du document : c'est ce qu'on demande."""
    document = Document(sections=[_section(
        "12.1", "Le rôle du dirigeant",
        "En 2031, le dirigeant passe à temps plein, une fois son fonds de commerce cédé.",
    )])
    assert _fuites(document, _reference(_LIGNE)) == []


def test_contre_epreuve_un_fait_court_se_reprend_a_l_identique() -> None:
    """« TVA obligatoire » est une décision de quelques mots : la reprendre est juste."""
    document = Document(sections=[_section("13.1", "TVA", "TVA obligatoire")])
    assert _fuites(document, _reference("TVA obligatoire")) == []


def test_contre_epreuve_la_decision_tenue_dans_une_phrase_redigee_passe() -> None:
    """La décision citée à l'identique DANS une phrase : c'est ce que l'en-tête demande."""
    decision = "le passage en société au 1er janvier 2031"
    document = Document(sections=[_section(
        "13.1", "Statut",
        "Le passage en société au 1er janvier 2031 s'accompagne d'un changement de régime "
        "social pour le dirigeant.",
        # La justification reprise telle quelle : du français, pas une ligne collée.
        "La micro-entreprise est un choix déjà arrêté pour le projet.",
    )])
    assert _fuites(document, _reference(decision)) == []


def test_la_memoire_ne_dit_plus_de_recopier_ni_ne_montre_ses_etiquettes() -> None:
    """La source du défaut : l'en-tête et la justification lus par le rédacteur."""
    from generation.memoire.decisions import _phrases_decisives

    decisions = _phrases_decisives({"CALENDRIER_PERSO": _LIGNE})
    assert decisions and decisions[0].justification == JUSTIFICATION_DU_BRIEF
    bloc = MemoireEtude(faits={}, decisions=decisions).bloc_pour_le_redacteur()
    assert "CALENDRIER_PERSO" not in bloc
    assert "telle quelle" not in bloc and "telles quelles" not in bloc
    assert "phrase du client" not in bloc
    assert "DÉCISIONS DU DOSSIER" not in bloc
    # Et ce que le rédacteur lit ne porte aucune locution que la relecture punit.
    from generation.chapitres.schema import _VOCABULAIRE_INTERNE

    assert [n for n, m in _VOCABULAIRE_INTERNE if n != "identifiant technique"
            and m.search(bloc)] == []


# ── 3. Les renvois de figures ────────────────────────────────────────────────


def test_un_renvoi_vers_une_figure_hors_sujet_est_signale() -> None:
    section = _section(
        "6.1", "Taille et dynamique du marché régional",
        "Le marché régional croît de 4 % par an.",
        "Figure présentée au chapitre 1 — Trésorerie mensuelle du lancement",
        tableaux=[Tableau(entetes=("Périmètre", "Ordre de grandeur"), lignes=(("R", "1"),))],
    )
    constats = [c for c in fuites.controler(Document(sections=[section]), Reference())
                if c.classe == "renvoi_figure"]
    assert [c.section for c in constats] == ["6.1"]
    assert "chapitre 1" in constats[0].extrait
    assert constats[0].grave is False  # posé par le rendu : réécrire n'y changerait rien


def test_contre_epreuve_un_renvoi_a_propos_passe() -> None:
    """Le titre de la figure et celui de la section parlent de la même chose."""
    sections = [
        _section("7.2", "Grille de notation commune : quatre critères",
                 "Figure présentée au chapitre 3 — Notes des concurrents sur les quatre "
                 "critères de la", "grille"),
        # Le sujet se lit aussi dans les en-têtes des tableaux de la section.
        _section("8.4", "Le panier moyen pondéré", "Figure présentée au chapitre 4 — "
                 "Structure du chiffre d'affaires par gamme",
                 tableaux=[Tableau(entetes=("Gamme", "Part du chiffre d'affaires"),
                                   lignes=(("A", "40 %"), ("B", "60 %")))]),
    ]
    assert [c for c in fuites.controler(Document(sections=sections), Reference())
            if c.classe == "renvoi_figure"] == []


def test_contre_epreuve_un_titre_de_chapitre_en_capitales_a_un_sujet() -> None:
    """Le PDF imprime le titre du chapitre en capitales : ce ne sont pas des sigles."""
    section = Section(numero="ch. 6", titre="ANALYSE DE MARCHÉ", chapitre=6, paragraphes=[
        "Figure présentée au chapitre 1 — Taille du marché régional",
    ])
    assert [c for c in fuites.controler(Document(sections=[section]), Reference())
            if c.classe == "renvoi_figure"] == []


@pytest.mark.parametrize(("figure", "sujets", "attendu"), [
    ("Repères financiers du lancement", ["Taille et dynamique du marché"], False),
    ("Positionnement sur les cinq critères de la grille", ["Grille : cinq critères"], True),
    ("Montée en charge du chiffre d'affaires", ["Progression du chiffre d'affaires"], True),
    # Le nom du projet, en capitales, ne fait pas un sujet commun.
    ("Positionnement de NOVA face au panel", ["Ce que vend NOVA"], False),
    # Un titre, ou un sujet, sans mot porteur de sens ne se juge pas (règle 2).
    ("2027 – 2029", ["Taille du marché"], True),
    ("Repères financiers du lancement", [], True),
])
def test_le_sujet_d_un_renvoi(figure: str, sujets: list[str], attendu: bool) -> None:
    assert fuites.renvoi_sur_le_sujet(figure, sujets) is attendu


# ── 4. Le rendu : la source des deux défauts ─────────────────────────────────


def _socle(source: str = "Insee, 2025") -> Any:
    from generation.socle.referentiel import Fiabilite, Perimetre
    from generation.socle.schema import DonneeSocle, Socle, Zone

    def donnee(identifiant: str, libelle: str, valeur: float) -> DonneeSocle:
        return DonneeSocle(
            id=identifiant, libelle=libelle, valeur=valeur, unite="EUR", annee=2027,
            perimetre=Perimetre.ENTREPRISE, fiabilite=Fiabilite.DECLAREE, source=source,
        )

    return Socle(
        secteur="bien-être", zone=Zone(pays="France"), date_socle=date(2026, 9, 30),
        donnees=[
            donnee("ca_sejours", "Chiffre d'affaires des séjours", 120_000.0),
            donnee("ca_ateliers", "Chiffre d'affaires des ateliers", 45_000.0),
        ],
    )


def _chapitre(numero: int, intitule: str, titre_figure: str) -> ChapitrePayload:
    return ChapitrePayload.model_validate({
        "chapitre": numero, "titre": f"Chapitre {numero}", "accroche": "",
        "blocs": [
            {"type": "titre_sous_section", "numero": f"{numero}.1", "intitule": intitule},
            {"type": "paragraphe", "texte": "Un paragraphe."},
            {"type": "graphique", "graphique": {
                "type": "barres", "titre": titre_figure,
                "donnees_ids": ["ca_sejours", "ca_ateliers"]}},
        ],
        "resume": "Résumé.",
    })


def _renvois(etude: dict[str, Any], numero: int) -> list[str]:
    chapitre = next(c for c in etude["chapitres"] if c["numero"] == numero)
    return [b["texte"] for b in chapitre["blocs"] if b["type"] == "renvoi"]


def test_le_rendu_n_ecrit_pas_un_renvoi_hors_sujet() -> None:
    """La même image, demandée sous « Taille du marché régional » : pas de renvoi."""
    from generation.rendu_word.assemblage import assembler_etude

    etude, rapport = assembler_etude(
        socle=_socle(),
        chapitres=[
            _chapitre(1, "Repères du lancement", "Deux activités, deux moteurs"),
            _chapitre(6, "Taille du marché régional", "Poids du marché régional"),
        ],
        titre="Business plan",
    )
    assert _renvois(etude, 6) == []
    assert any("ni renvoi" in m for m in rapport.graphiques_en_double), (
        rapport.graphiques_en_double
    )


def test_contre_epreuve_le_rendu_garde_le_renvoi_a_propos() -> None:
    from generation.rendu_word.assemblage import assembler_etude

    etude, _ = assembler_etude(
        socle=_socle(),
        chapitres=[
            _chapitre(1, "Repères du lancement", "Deux activités, deux moteurs"),
            _chapitre(16, "Chiffre d'affaires par activité", "Chiffre d'affaires par activité"),
        ],
        titre="Business plan",
    )
    assert _renvois(etude, 16) == ["Figure présentée au chapitre 1 — Deux activités, deux moteurs"]


class _Payload:
    def __init__(self, numero: int, titre: str, donnees: list[str]) -> None:
        self.chapitre, self.titre, self.donnees_utilisees = numero, titre, donnees


class _Profil:
    libelle = "Test"
    graphiques_a_eviter: tuple[str, ...] = ()


def _legendes_de_completion(monkeypatch: pytest.MonkeyPatch, socle: Any) -> list[str]:
    from generation.rendu_word import assemblage
    from generation.rendu_word.donnees_graphiques import Resolution

    def resoudre(_socle: Any, type_graphique: str, ids: Any) -> Resolution:
        return Resolution(type_graphique=type_graphique,
                          donnees={"valeurs": [(str(i), 1.0) for i in ids]})

    monkeypatch.setattr(assemblage, "resoudre", resoudre)
    blocs: list[dict[str, Any]] = [{"numero": 2, "titre": "Offre", "blocs": []}]
    assemblage._completer_les_figures(
        blocs, [cast(Any, _Payload(2, "Offre", ["ca_sejours", "ca_ateliers"]))],
        socle, cast(Any, _Profil()),
        assemblage.RapportAssemblage(),
    )
    return [b["source"] for b in blocs[0]["blocs"] if b["type"] == "graphique"]


def test_la_figure_de_completion_dit_sa_source_pas_notre_entrepot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sur le code d'avant : « Données du socle vérifié » sous chaque figure ajoutée."""
    legendes = _legendes_de_completion(monkeypatch, _socle("Insee, 2025"))
    assert legendes, "aucune figure de complétion : le test ne jugerait rien (règle 1)"
    assert all("socle" not in legende.lower() for legende in legendes)
    assert all(legende.startswith("Source") and "Insee, 2025" in legende for legende in legendes)
    assert _fuites(Document(sections=[_section("5.4", "Offre", *legendes)])) == []


def test_contre_epreuve_sans_source_connue_pas_de_legende(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _legendes_de_completion(monkeypatch, _socle("")) == [""]


def test_le_registre_relit_les_fuites() -> None:
    """Branché : `relire` passe par ce contrôle (sinon rien ne serait signalé en production)."""
    document = Document(sections=[_section("7.1", "Trésorerie",
                                           "Selon les termes du dossier, le solde est positif.")])
    assert [c.classe for c in relire(document, Reference()) if c.classe == "fuite"] == ["fuite"]

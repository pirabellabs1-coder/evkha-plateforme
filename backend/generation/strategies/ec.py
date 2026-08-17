"""Strategy « Etude de concurrence » — le manuel EC.

Les controles issus des grilles de VERIFICATION FINALE du cahier des charges
(annexes, visuels, statuts des demandes) sont regroupes plus bas. Deux regles
structurelles vivent ici depuis l'origine (regle 4) :

  1. Cardinaux fiche 2 d'Evangeline : exactement 8 concurrents directs
     et 3 indirects dans le document livre. La logique de comptage
     reste dans `checks_evangeline.verifier_concurrents_dans_ec`
     (source unique partagee avec le prompt EC — regle 5). La strategy
     delegue simplement.

  2. Matrice HTML au chapitre 5 (`ec.05.matrice_positionnement`) : le
     prompt insiste (« ETAPE OBLIGATOIRE : le tableau HTML DOIT
     apparaitre ») mais rien ne verifiait qu'elle etait presente. Un
     modele qui decrit la matrice en prose passait le gate. Un
     banquier lit la matrice, pas la prose : sans tableau, le
     livrable est incomplet.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from catalog.models import DeliverableType
from generation.models import ChapterGeneration, GenerationJob
from generation.strategies.base import (
    ContexteSupplementaire,
    ProblemeCoherence,
)

# ══════════════════════════════════════════════════════════════════════════
# 1. Matrice HTML au chapitre 5
# ══════════════════════════════════════════════════════════════════════════

# Numero du chapitre matrice dans le blueprint EC. Constante liee au
# blueprint : si demain on renumerote, on corrige ici uniquement
# (regle 5, source unique). Un chapitre absent n'est PLUS silencieux : voir
# `verifier_matrice_positionnement`.
_CHAPITRE_MATRICE = 5

# Une matrice de positionnement necessite au moins 3 lignes utiles
# (en-tete + au moins 2 lignes de donnees). Un `<table>` avec une seule
# ligne n'est pas une matrice, c'est une pastille visuelle. Seuil bas
# volontaire : la vraie matrice-type du prompt fait 3 lignes minimum
# (haut, milieu, bas), donc 3 est le plancher legitime.
_MIN_LIGNES_MATRICE = 3

_TABLE_RE = re.compile(r"<table\b[^>]*>(.*?)</table>", re.IGNORECASE | re.DOTALL)
_TR_RE = re.compile(r"<tr\b[^>]*>", re.IGNORECASE)


def _matrice_dans_le_payload(job: GenerationJob | None) -> tuple[bool | None, str]:
    """Verdict depuis le payload STRUCTURÉ du chapitre 5. `None` = hors sujet.

    Le moteur structuré ne produit JAMAIS de HTML : sa matrice est un bloc
    `tableau` ou une figure `matrice_positionnement`, rendus par le moteur
    Word. Chercher `<table>` dans son corpus, c'est exiger du modèle ce que
    `_SYSTEME` lui interdit dans le même prompt — et le document `6cb0fab3`
    (10/08/2026) a été bloqué exactement là-dessus : chapitre 5 présent,
    matrice présente en bloc `tableau`, contrôle aveugle au contrat qu'il
    était censé servir.
    """
    if job is None:
        return None, ""
    chapitre = job.chapters.filter(chapter_number=_CHAPITRE_MATRICE).first()
    if chapitre is None or not chapitre.payload:
        return None, ""  # Moteur hérité, ou chapitre non produit : au corpus de juger.

    # Import paresseux : cycle strategies -> chapitres -> models -> strategies.
    from generation.chapitres.schema import ChapitrePayload  # noqa: PLC0415

    try:
        payload = ChapitrePayload.model_validate(chapitre.payload)
    except Exception:  # noqa: BLE001 — un payload illisible se juge au corpus
        return None, ""

    if any(g.type == "matrice_positionnement" for g in payload.graphiques):
        return True, ""
    for bloc in payload.blocs:
        tableau = getattr(bloc, "tableau", None)
        if tableau is not None and 1 + len(tableau.lignes) >= _MIN_LIGNES_MATRICE:
            return True, ""

    return False, (
        f"Matrice de positionnement absente du chapitre {_CHAPITRE_MATRICE} : "
        "ni figure `matrice_positionnement` (deux codes de la grille de "
        "notation en axes), ni bloc `tableau` d'au moins "
        f"{_MIN_LIGNES_MATRICE} lignes. Une description en prose n'est pas "
        "une matrice — un banquier lit la grille, pas le paragraphe."
    )


def verifier_matrice_positionnement(
    corpus_par_chapitre: dict[int, str],
    *,
    job: GenerationJob | None = None,
) -> list[str]:
    """Le chapitre matrice doit porter une matrice — dans le CONTRAT du moteur.

    Moteur structuré (payload présent) : un bloc `tableau` d'au moins 3
    lignes, ou une figure `matrice_positionnement`. Moteur hérité : un
    `<table>` d'au moins 3 `<tr>` dans le corpus, comme à l'origine.

    Trois branches, toutes signalantes :
      - Chapitre absent : on ne peut rien juger, donc on echoue (regle 1).
      - Chapitre present, aucune matrice : decrite en prose, signal.
      - Tableau trop court : pastille, pas matrice — signal.
    """
    verdict, motif = _matrice_dans_le_payload(job)
    if verdict is True:
        return []
    if verdict is False:
        return [motif]

    corps = corpus_par_chapitre.get(_CHAPITRE_MATRICE)
    if corps is None:
        # Le chapitre manque. Rendre [] ici, c'etait conclure au succes faute
        # de matiere a juger — precisement ce que la regle 1 du depot interdit.
        # Le commentaire d'origine parlait d'« eviter un faux positif si le
        # blueprint change » : un blueprint qui perd son chapitre matrice est un
        # evenement qui doit se voir, pas se taire.
        return [
            f"Chapitre {_CHAPITRE_MATRICE} (matrice de positionnement) absent "
            "du corpus : la matrice ne peut pas etre controlee. Le document en "
            "fait l'un de ses quatre visuels centraux."
        ]

    tables = _TABLE_RE.findall(corps)
    if not tables:
        return [
            "Matrice de positionnement concurrentiel absente du chapitre "
            f"{_CHAPITRE_MATRICE} : aucun tableau dans le corpus. Une "
            "description en prose n'est pas une matrice — un banquier "
            "lit la grille, pas le paragraphe."
        ]

    # On retient la plus grande table trouvee (il peut y avoir une petite
    # legende + la vraie matrice).
    max_lignes = max(len(_TR_RE.findall(t)) for t in tables)
    if max_lignes < _MIN_LIGNES_MATRICE:
        return [
            f"Matrice de positionnement chapitre {_CHAPITRE_MATRICE} : "
            f"tableau trouve avec {max_lignes} ligne(s) uniquement, "
            f"minimum attendu {_MIN_LIGNES_MATRICE} (grille 3x3 selon "
            "le prompt : axes + placement des acteurs)."
        ]

    return []


# ══════════════════════════════════════════════════════════════════════════
# 1 bis. Grilles de VERIFICATION FINALE du cahier des charges
# ══════════════════════════════════════════════════════════════════════════
#
# Le document ferme chacun de ses huit chapitres par une grille de verification
# — 63 points au total. Le depot en implementait DEUX : les cardinaux 8+3 et la
# presence d'un tableau au chapitre 5. Le gate rendait donc `passed` sur une
# etude a laquelle il manquait ses annexes, ses visuels ou le statut de chaque
# demande client.
#
# Tous les points du document ne sont pas mecanisables : « l'analyse est-elle
# strategique ? » ne se verifie pas par une expression reguliere, et pretendre
# le contraire produirait le defaut de la regle 2 — un motif faux, pire
# qu'absent. On implemente donc ce qui est COMPTABLE, et on le dit.

_CHAPITRE_ANNEXES = 4
_CHAPITRE_VISUELS = 7
_CHAPITRE_DEMANDES = 8

#: Le catalogue du document en propose six ; l'etape 4.2 en retient « 3 a 4 ».
_ANNEXES_MIN = 3
_ANNEXES_MAX = 4

#: « LISTE OBLIGATOIRE DES 4 VISUELS » — carte des implantations, parts de
#: marche, radar des 11 acteurs, repartition des canaux.
_VISUELS_ATTENDUS = 4

#: Le préfixe de numérotation est optionnel : le moteur structuré rend chaque
#: sous-titre en `## {numero} {intitule}` — « ## 4.1 Annexe A — Grille » — et
#: l'ancien motif exigeait « annexe » collé aux dièses. Un modèle qui titrait
#: ses annexes DANS la numérotation du contrat ne pouvait jamais être compté
#: (job réel `026fecea`, 10/08/2026 : « 0 annexe(s) titrée(s) » sur un
#: chapitre qui en portait).
_TITRE_ANNEXE_RE = re.compile(
    r"^#{2,4}\s*(?:\d[\w.]*\s+)?annexe\b", re.IGNORECASE | re.MULTILINE
)
#: Ce qui compte comme UN visuel, dans les deux moteurs.
#:
#: `<!-- graphique:` est le visuel du moteur structuré : un `BlocGraphique`
#: sérialisé par `payload_vers_markdown`, résolu en figure au rendu. Ne pas le
#: compter, c'était exiger du chapitre 7 des visuels dans un format que le
#: moteur ne produit jamais — la même cécité que la matrice HTML.
#:
#: Le SÉPARATEUR de tableau markdown (`| --- | --- |`) est arrivé ensuite, et
#: pour la même raison. La fiche du chapitre 7 demande explicitement deux de
#: ses quatre visuels « sous forme de tableau structuré » — la carte des
#: implantations, la répartition des canaux — et le moteur structuré rend un
#: `BlocTableau` en markdown, jamais en `<table>`. Le job réel `026fecea`
#: portait ses quatre visuels et n'en faisait compter que trois : sa carte
#: était un tableau, donc invisible. Le séparateur apparaît UNE fois par
#: tableau, ce qui compte des blocs et non des lignes.
_VISUEL_RE = re.compile(
    r"<table\b|```chart\b|!\[|<!--\s*graphique:|^\s*\|[\s:|-]*-{3,}[\s:|-]*\|",
    re.IGNORECASE | re.MULTILINE,
)
#: Etape 8.2 : chaque demande porte un statut sur trois.
_STATUT_RE = re.compile(
    r"\b(?:traitée?|traitee?|partiellement\s+traitée?|partiellement\s+traitee?"
    r"|non\s+traitée?|non\s+traitee?)\b",
    re.IGNORECASE,
)


def verifier_annexes_strategiques(corpus_par_chapitre: dict[int, str]) -> list[str]:
    """Le chapitre 4 doit porter 3 a 4 annexes titrees (etape 4.2)."""
    corps = corpus_par_chapitre.get(_CHAPITRE_ANNEXES)
    if corps is None:
        return [
            f"Chapitre {_CHAPITRE_ANNEXES} (positionnement et annexes) absent "
            "du corpus : le nombre d'annexes ne peut pas etre controle."
        ]

    trouvees = len(_TITRE_ANNEXE_RE.findall(corps))
    if _ANNEXES_MIN <= trouvees <= _ANNEXES_MAX:
        return []
    return [
        f"Chapitre {_CHAPITRE_ANNEXES} : {trouvees} annexe(s) titree(s) "
        f"trouvee(s), le document en attend {_ANNEXES_MIN} a {_ANNEXES_MAX}. "
        "Son catalogue en propose six et impose de choisir selon le secteur et "
        "le modele economique — « ne pas produire des annexes par principe »."
    ]


def verifier_visuels_du_chapitre_conclusion(
    corpus_par_chapitre: dict[int, str],
) -> list[str]:
    """Le chapitre 7 doit porter les quatre visuels de la liste obligatoire."""
    corps = corpus_par_chapitre.get(_CHAPITRE_VISUELS)
    if corps is None:
        return [
            f"Chapitre {_CHAPITRE_VISUELS} (conclusion analytique et graphiques) "
            "absent du corpus : les quatre visuels ne peuvent pas etre controles."
        ]

    trouves = len(_VISUEL_RE.findall(corps))
    if trouves >= _VISUELS_ATTENDUS:
        return []
    return [
        f"Chapitre {_CHAPITRE_VISUELS} : {trouves} visuel(s) detecte(s) pour "
        f"{_VISUELS_ATTENDUS} attendus. Le document en donne la liste "
        "obligatoire : carte des implantations, parts de marche, radar des "
        "onze acteurs, repartition des canaux."
    ]


def verifier_statuts_des_demandes(corpus_par_chapitre: dict[int, str]) -> list[str]:
    """L'annexe finale doit statuer sur chaque demande du client (etape 8.2)."""
    corps = corpus_par_chapitre.get(_CHAPITRE_DEMANDES)
    if corps is None:
        return [
            f"Chapitre {_CHAPITRE_DEMANDES} (annexe de validation des demandes) "
            "absent du corpus : les statuts ne peuvent pas etre controles. Le "
            "document en fait la preuve que rien n'a ete oublie."
        ]

    if _STATUT_RE.search(corps):
        return []
    return [
        f"Chapitre {_CHAPITRE_DEMANDES} : aucun statut de demande trouve. Le "
        "document impose, pour chaque demande recensee, l'un des trois statuts "
        "— traitee, partiellement traitee, non traitee — et une voie de "
        "complement OBLIGATOIRE des que le statut n'est pas « traitee »."
    ]


# ══════════════════════════════════════════════════════════════════════════
# 2. STRATEGY
# ══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ECStrategy:
    """Strategy pour l'etude de concurrence."""

    deliverable_type: ClassVar[str] = DeliverableType.COMPETITOR_STUDY

    def contexte_supplementaire(
        self, job: GenerationJob, chapter: ChapterGeneration
    ) -> ContexteSupplementaire | None:
        """Pas de contexte supplementaire specifique pour l'instant.

        La consigne des cardinaux et de la matrice est deja injectee
        dans le prompt via `prompt_library.py`. Le socle commun
        (client_facts_as_context) fournit le reste. Les prochaines
        iterations pourront injecter une base concurrents consolidee
        au moment du rendu du chapitre matrice.
        """
        return None

    def problemes_de_coherence(
        self, job: GenerationJob, corpus_par_chapitre: dict[int, str]
    ) -> list[ProblemeCoherence]:
        """Deux checks : cardinaux concurrents + matrice HTML."""
        # Import lazy : cycle strategies -> checks_evangeline -> models -> strategies.
        from generation.checks_evangeline import verifier_concurrents_dans_ec  # noqa: PLC0415

        problemes: list[ProblemeCoherence] = []

        # 1. Cardinaux 8 directs / 3 indirects (fiche 2 Evangeline).
        divergents = verifier_concurrents_dans_ec(
            list(corpus_par_chapitre.items())
        )
        for c in divergents:
            verbe = "manque(nt)" if c.trouves < c.attendus else "en trop"
            problemes.append(ProblemeCoherence(
                categorie="concurrents_ec",
                chapitre=c.chapitre,
                detail=(
                    f"Concurrents {c.type_} : {c.trouves} trouves, "
                    f"{c.attendus} attendus ({verbe}). Consigne fiche 2 : "
                    f"toujours {c.attendus} concurrents {c.type_}, ni plus "
                    "ni moins."
                ),
                valeur_attendue=str(c.attendus),
                valeur_trouvee=str(c.trouves),
            ))

        # 2. Matrice au chapitre 5 — payload structuré d'abord, corpus sinon.
        for detail in verifier_matrice_positionnement(corpus_par_chapitre, job=job):
            problemes.append(ProblemeCoherence(
                categorie="matrice_absente",
                chapitre=_CHAPITRE_MATRICE,
                detail=detail,
            ))

        # 3-5. Grilles de VERIFICATION FINALE du cahier des charges : ce qui est
        # comptable dans les 63 points du document (annexes, visuels, statuts).
        for verificateur, categorie, chapitre in (
            (verifier_annexes_strategiques, "annexes_ec", _CHAPITRE_ANNEXES),
            (verifier_visuels_du_chapitre_conclusion, "visuels_ec", _CHAPITRE_VISUELS),
            (verifier_statuts_des_demandes, "demandes_ec", _CHAPITRE_DEMANDES),
        ):
            for detail in verificateur(corpus_par_chapitre):
                problemes.append(ProblemeCoherence(
                    categorie=categorie,
                    chapitre=chapitre,
                    detail=detail,
                ))

        return problemes


def get_strategy() -> ECStrategy:
    """Point d'entree utilise par `strategies.base.get_strategy`."""
    return ECStrategy()

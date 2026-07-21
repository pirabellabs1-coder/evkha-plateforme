"""Strategy « Etude de concurrence » — le manuel EC.

Deux regles structurelles qui vivent maintenant ici (regle 4) :

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
# (regle 5, source unique). Le fallback dans le check ci-dessous rend
# le check silencieux si le chapitre disparait — pas de faux positif.
_CHAPITRE_MATRICE = 5

# Une matrice de positionnement necessite au moins 3 lignes utiles
# (en-tete + au moins 2 lignes de donnees). Un `<table>` avec une seule
# ligne n'est pas une matrice, c'est une pastille visuelle. Seuil bas
# volontaire : la vraie matrice-type du prompt fait 3 lignes minimum
# (haut, milieu, bas), donc 3 est le plancher legitime.
_MIN_LIGNES_MATRICE = 3

_TABLE_RE = re.compile(r"<table\b[^>]*>(.*?)</table>", re.IGNORECASE | re.DOTALL)
_TR_RE = re.compile(r"<tr\b[^>]*>", re.IGNORECASE)


def verifier_matrice_positionnement(
    corpus_par_chapitre: dict[int, str],
) -> list[str]:
    """Le chapitre matrice doit contenir un `<table>` avec >= 3 `<tr>`.

    Trois branches :
      - Chapitre absent : le blueprint a change, on ne signale rien.
      - Chapitre present, aucun `<table>` : matrice decrite en prose,
        signal (cas defaut le plus frequent).
      - Chapitre present, `<table>` avec < 3 `<tr>` : pastille, pas
        matrice — signal (le prompt exige une grille 3x3).
    """
    corps = corpus_par_chapitre.get(_CHAPITRE_MATRICE)
    if corps is None:
        return []

    tables = _TABLE_RE.findall(corps)
    if not tables:
        return [
            "Matrice de positionnement concurrentiel absente du chapitre "
            f"{_CHAPITRE_MATRICE}. Le prompt exige explicitement un tableau "
            "HTML (« ETAPE OBLIGATOIRE : le tableau HTML DOIT apparaitre »). "
            "Une description en prose n'est pas une matrice — un banquier "
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

        # 2. Matrice HTML au chapitre 5.
        for detail in verifier_matrice_positionnement(corpus_par_chapitre):
            problemes.append(ProblemeCoherence(
                categorie="matrice_absente",
                chapitre=_CHAPITRE_MATRICE,
                detail=detail,
            ))

        return problemes


def get_strategy() -> ECStrategy:
    """Point d'entree utilise par `strategies.base.get_strategy`."""
    return ECStrategy()

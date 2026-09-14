"""Un prompt ne doit jamais montrer au modèle le vocabulaire qu'on lui interdit.

## Le défaut mesuré

12/09/2026, reprise Zenitek `db0d9508` : deux chapitres MORTS sur le contrôle
du vocabulaire interne — dont `str.20.sources`, celui-là même qui devait
montrer si les nouvelles règles de traçabilité servaient à quelque chose. Les
quatre générations précédentes du même dossier en perdaient zéro ou un.

La cause tenait en deux endroits du prompt :

    en-tête du bloc de chiffres :  « SOCLE VERROUILLÉ — assistance… »
    consigne de rédaction :        « ni socle verrouillé ou bloqué, ni hors
                                     socle, ni pipeline système… »

L'un l'écrivait en capitales, l'autre le listait en toutes lettres sous
prétexte de l'interdire. Le modèle reprend ce qu'on lui montre — ce dépôt
l'avait déjà mesuré : vingt-deux occurrences d'un nom de plateforme recopiées
depuis une simple docstring.

C'est la règle 5 prise entre un prompt et un contrôle : l'un écrit ce que
l'autre punit. Et c'est la même histoire que `[[UNDERSTAND]]`, où le prompt
exigeait un marqueur que la validation sanctionnait, faisant payer chaque
chapitre deux fois.

## Pourquoi ce test vise la CLASSE

Corriger « socle verrouillé » seul laisserait « hors socle », puis la locution
suivante qu'on ajoutera au contrôle dans six mois sans penser au prompt. Le
test lit donc `_VOCABULAIRE_INTERNE` — la liste qui FAIT FOI — et l'applique à
tout ce qui part au modèle. Un motif ajouté là sera vérifié ici sans que
personne ait à y penser (règle 4).

Il échoue sur le code d'avant, sur les deux emplacements à la fois.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from generation.chapitres.schema import _VOCABULAIRE_INTERNE
from generation.socle.builder import OUTIL_DESCRIPTION
from generation.socle.referentiel import Fiabilite, Perimetre
from generation.socle.schema import DonneeSocle, Socle, Zone


def _socle() -> Socle:
    return Socle(
        secteur="assistance informatique",
        zone=Zone(pays="France", region="Île-de-France"),
        date_socle=date(2026, 9, 12),
        donnees=[
            DonneeSocle(
                id="ca_actuel", libelle="Chiffre d'affaires", valeur=120000,
                unite="EUR", annee=2026, perimetre=Perimetre.NATIONAL,
                fiabilite=Fiabilite.DECLAREE,
            ),
        ],
    )


#: La seule règle qu'un PROMPT a le droit d'enfreindre, et pourquoi.
#:
#: « identifiant technique » attrape toute forme `mot_mot` — `ca_actuel`,
#: `marche_national_taille`. C'est un défaut dans le document LIVRÉ ; c'est la
#: matière même du prompt, qui doit nommer les identifiants pour que le modèle
#: les emploie dans ses figures. Un test qui l'exigerait ici demanderait au
#: bloc de chiffres de ne pas citer ses chiffres.
#:
#: L'exclusion est nommée et bornée à ce motif : toute autre locution ajoutée
#: à `_VOCABULAIRE_INTERNE` reste vérifiée sans que personne y pense.
_MATIERE_DU_PROMPT = frozenset({"identifiant technique"})


def _fautes(texte: str) -> list[str]:
    """Les locutions punies que ce texte contient — vide si le texte est sain."""
    return [
        nom for nom, motif in _VOCABULAIRE_INTERNE
        if nom not in _MATIERE_DU_PROMPT and motif.search(texte)
    ]


def test_le_bloc_des_chiffres_n_ecrit_aucune_locution_punie() -> None:
    """Son en-tête portait « SOCLE VERROUILLÉ », en capitales, en tête du bloc.

    C'est la place la plus visible du prompt : celle que le modèle relit à
    chaque chapitre.
    """
    from generation.chapitres.runner import _bloc_socle

    bloc = _bloc_socle(_socle())
    assert _fautes(bloc) == [], f"le bloc des chiffres écrit : {_fautes(bloc)}"


def test_le_prompt_systeme_n_ecrit_aucune_locution_punie() -> None:
    """L'interdiction CITAIT ce qu'elle interdisait, en toutes lettres.

    Une consigne qui donne l'exemple de la faute l'enseigne. Elle s'énonce
    désormais sans écrire une seule des locutions punies.
    """
    from generation.chapitres.runner import (
        _SYSTEME,
        COHERENCE_DES_CHIFFRES,
        PRIX_ET_MODELE_ECONOMIQUE,
        SOURCES_ET_TRACABILITE,
    )

    for nom, texte in (
        ("système", _SYSTEME),
        ("chiffres", COHERENCE_DES_CHIFFRES),
        ("sources", SOURCES_ET_TRACABILITE),
        ("prix", PRIX_ET_MODELE_ECONOMIQUE),
    ):
        assert _fautes(texte) == [], f"bloc {nom} : {_fautes(texte)}"


def test_la_description_de_l_outil_du_socle_est_saine() -> None:
    """Elle part au modèle AVEC le schéma : c'est un prompt, pas un commentaire."""
    assert _fautes(OUTIL_DESCRIPTION) == []


def test_le_catalogue_des_figures_est_sain() -> None:
    """Ajouté le 12/09/2026 — donc jamais passé sous cette garde jusqu'ici."""
    from generation.rendu_word.catalogue_figures import bloc_figures_possibles

    assert _fautes(bloc_figures_possibles(_socle())) == []


def test_la_garde_sait_encore_mordre() -> None:
    """CONTRE-ÉPREUVE : un test qui ne détecte plus rien passerait sur tout.

    Sans elle, vider `_VOCABULAIRE_INTERNE` rendrait ce fichier entièrement
    vert — un contrôle qui n'a rien à comparer n'est pas un succès (règle 1).
    """
    assert _fautes("Le socle verrouillé du dossier, et les chiffres hors socle.")



# ── Tout ce qui part au modèle, pas seulement le prompt système ──────────────
#
# Audit du 14/09/2026 : le correctif du 12/09 avait retiré « SOCLE VERROUILLÉ »
# du prompt système — et la même faute restait AILLEURS dans ce qui est envoyé :
# « Aucun chiffre hors socle. » 135 fois dans le plan de l'étude de marché
# (injecté sous chaque paragraphe), « bloc SOCLE VERROUILLE » dans six fichiers
# de prompt, « identifiants du socle » dans la règle des figures envoyée à
# chaque chapitre. Ce test ne regardait que le prompt système : il vise
# désormais chaque source de consigne (règle 4).


def _fichiers_de_prompt() -> list[Any]:
    from generation.chapitres.configuration import RACINE_PROMPTS

    fichiers = sorted(RACINE_PROMPTS.rglob("*.md"))
    assert fichiers, "aucun fichier de prompt trouvé : le test ne jugerait rien (règle 1)"
    return fichiers


def test_aucun_fichier_de_prompt_n_ecrit_une_locution_punie() -> None:
    """Le fichier TEL QU'IL PART : sans son bandeau de documentation.

    Le bandeau (« Prompt du chapitre 0 — Fiche projet ») est retiré par le
    chargeur avant l'envoi ; le juger ferait crier le test à tort. Le retrait
    est celui du chargeur lui-même, importé (règle 5).
    """
    from generation.chapitres.fichiers_prompts import _BANDEAU

    fautes = {
        f.relative_to(f.parents[1]).as_posix():
            _fautes(_BANDEAU.sub("", f.read_text(encoding="utf-8")))
        for f in _fichiers_de_prompt()
    }
    assert {nom: liste for nom, liste in fautes.items() if liste} == {}


def test_le_plan_de_l_etude_de_marche_n_ecrit_aucune_locution_punie() -> None:
    """135 lignes « Aucun chiffre hors socle. », une sous chaque paragraphe."""
    from generation.modele.consigne import plan_du_chapitre

    plans = {numero: plan_du_chapitre(numero) for numero in range(0, 30)}
    assert any(plans.values()), "aucun plan lu : le test ne jugerait rien (règle 1)"
    assert {n: _fautes(t) for n, t in plans.items() if _fautes(t)} == {}


def test_la_regle_des_figures_envoyee_a_chaque_chapitre_est_saine() -> None:
    from generation.prompts import REGLES_IDENTIFIANTS_FIGURES

    assert _fautes(REGLES_IDENTIFIANTS_FIGURES) == []


def test_chaque_type_de_figure_nomme_dans_un_prompt_existe() -> None:
    """Un type inconnu fait refuser le chapitre par le contrat, et le repayer.

    Audit du 14/09/2026 : l'étude concurrentielle, chapitre 7, demandait une
    figure « de type `barres_verticales` ». Ce type n'existe pas dans
    `TypeGraphique` : la validation Pydantic refuse le chapitre avant tout
    arbitrage, et ce refus ne s'assouplit pas au dernier essai. La liste qui
    fait foi est l'énumération elle-même, importée (règle 5).
    """
    import re

    from generation.chapitres.fichiers_prompts import _BANDEAU
    from generation.chapitres.schema import TypeGraphique

    connus = {t.value for t in TypeGraphique}
    demande = re.compile(r"(?:figure|graphique)(?: de type)?\s+`([a-z_]+)`")
    inconnus = {
        f"{f.parent.name}/{f.name}": nom
        for f in _fichiers_de_prompt()
        for nom in demande.findall(_BANDEAU.sub("", f.read_text(encoding="utf-8")))
        if nom not in connus
    }
    assert inconnus == {}


def test_les_autres_sources_de_consigne_n_ecrivent_aucune_locution_punie() -> None:
    """Relecture du 14/09/2026 : sources que ce fichier ne lisait pas encore.

    Aucune faute trouvée à ce jour — c'était un trou de couverture, pas un
    défaut en ligne. Le trou se ferme ici.
    """
    from generation.chapitres.runner import (
        _FORME_PAR_LIVRABLE,
        CONSIGNE_DOCUMENTS_CHAPITRE,
        REGLES_DE_FOND,
        _forme_commune,
    )
    from generation.correction import _CHECK_LABELS
    from generation.prompts import _consigne_specifique_livrable
    from generation.socle.prompt import RELECTURE_DU_SOCLE

    sources = {
        "fond": REGLES_DE_FOND,
        "forme commune": _forme_commune(),
        "documents": CONSIGNE_DOCUMENTS_CHAPITRE,
        "relecture du socle": RELECTURE_DU_SOCLE,
        "consignes de réécriture": "\n".join(_CHECK_LABELS.values()),
        **{f"forme {k}": v for k, v in _FORME_PAR_LIVRABLE.items()},
        **{
            f"consigne {k}": _consigne_specifique_livrable(k)
            for k in ("market_study", "competitor_study", "business_plan", "business_strategy")
        },
    }
    assert {nom: _fautes(texte) for nom, texte in sources.items() if _fautes(texte)} == {}

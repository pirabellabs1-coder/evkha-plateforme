"""Les trois nombres qui disent si l'entraînement des prompts a servi.

    FIGURES    demandées par le modèle / obtenues
    SOURCES    extérieures sans adresse utilisable (celles du client à part)
    CHIFFRES   ceux que le document avance sans que le socle les porte

Aucun appel d'API, aucune écriture : la mesure re-rend le document depuis les
chapitres déjà payés, le relit, et compte. Elle coûte zéro centime, donc elle
vaut aussi pour les dossiers ANCIENS — c'est tout son intérêt : sans point de
comparaison, un nombre sur la prochaine génération ne voudrait rien dire.

## Pourquoi ce module plutôt que la commande seule

`mesurer_livrable` tourne sur la machine du développeur ; les dossiers du
client vivent en production. Une mesure qu'on ne peut pas prendre là où sont
les documents ne sert à rien. La commande et la vue du tableau de bord
appellent donc le même `mesurer()` : deux compteurs qui ne s'accorderaient pas
seraient pires qu'un seul (règle 5 — chaque défaut majeur de ce dépôt vient de
deux modules qui ne sont pas d'accord).

## Ce que la mesure refuse de faire

Elle ne rend jamais un beau zéro à la place d'un constat impossible. Pas de
chapitre Sources dans le document ? `sources` vaut `None`, et l'appelant doit
le dire. C'est la règle 1 du dépôt : un contrôle qui n'a rien à comparer est
un échec, jamais un succès.
"""
from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from generation.checks_post_rendu import (
    _SOURCE_DU_CLIENT_RE,
    _URL_RE,
    _sources_listees,
    _trouver_chapitre_sources,
    adresse_de_la_source,
)
from generation.models import GenerationJob

#: Le motif que porte une anomalie « ce chiffre n'est pas dans le socle ».
MOTIF_HORS_SOCLE = "chiffres_hors_socle"


@dataclass
class MesureDesSources:
    exterieures: int = 0
    #: Extérieures dont l'adresse manque, ou n'est pas utilisable. Une adresse
    #: inventée (`example.com`) compte ICI : elle est pire qu'une absence,
    #: puisqu'elle a l'apparence du sérieux et que le lecteur la suivra.
    sans_adresse: int = 0
    #: Le prévisionnel du client n'est pas publié et ne le sera jamais. Les
    #: compter comme « sans adresse » accuserait le document d'un défaut qu'il
    #: n'a pas — et un contrôle qui crie faux finit débranché (règle 2).
    du_client: int = 0
    #: Les lignes RETENUES comme sources, telles que la mesure les a lues. Les
    #: six études de marché du corpus rendaient toutes « 3 extérieures, 3 sans
    #: adresse » pour 19 à 70 adresses collectées : sans les lignes, impossible
    #: de dire si le document omet ses liens ou si la mesure lit le mauvais
    #: tableau (14/09/2026).
    lignes: list[str] = field(default_factory=list)


@dataclass
class Mesure:
    """Ce qui a été compté. `sources` à None = chapitre Sources introuvable."""

    figures_demandees: int = 0
    #: Obtenues PARMI les demandées. Les figures ajoutées par la passe de
    #: complétion sont exclues : les compter donnait un taux de 121 %,
    #: c'est-à-dire un motif faux — pire qu'absent (règle 2).
    figures_obtenues: int = 0
    figures_completees: int = 0
    #: Dessinées APRÈS réparation (`rendu_word.reparation_figures`) : dans le
    #: document, mais pas obtenues telles que le modèle les a demandées.
    figures_reparees: int = 0
    figures_en_tableau: int = 0
    figures_perdues: int = 0
    sources: MesureDesSources | None = None
    chiffres_hors_socle: list[str] = field(default_factory=list)
    autres_anomalies: int = 0
    #: Adresses DISTINCTES que la recherche web a rapportées au dossier. C'est
    #: le dénominateur qui manquait à la mesure des sources : « 0 adresse
    #: vérifiable » ne dit pas la même chose selon que le modèle en avait
    #: quarante sous les yeux ou aucune. Dans le premier cas il désobéit ; dans
    #: le second, aucune règle de prompt n'y peut rien (13/09/2026).
    adresses_collectees: int = 0
    #: CHAQUE défaut, par contrôle, avec des exemples — du fichier Word
    #: (`anomalies`) et du gate de livraison (`gate`).
    #:
    #: Trois nombres ne suffisent pas à conduire un travail de plusieurs jours :
    #: sans le détail, on corrige au hasard et on ne peut pas prouver qu'on
    #: avance (13/09/2026). Le corpus des dossiers déjà écrits se re-mesure à
    #: zéro centime ; c'est ce détail, agrégé, qui dit quelle CLASSE de défaut
    #: attaquer d'abord (règle 4).
    anomalies: dict[str, list[dict[str, object]]] = field(default_factory=dict)
    gate: dict[str, list[dict[str, object]]] = field(default_factory=dict)
    #: Chaque figure perdue, ses données et la raison de l'échec de sa
    #: réparation (`RapportAssemblage.diagnostic_des_abandons`).
    figures_abandonnees: list[dict[str, object]] = field(default_factory=list)
    #: Ce que le socle du dossier permet réellement de dessiner : nombre de
    #: figures du catalogue et formes distinctes. Le dénominateur de
    #: `figures_demandees` — la consigne en exigeait au moins 22 et 12 formes
    #: quel que soit le socle (14/09/2026).
    catalogue_figures: int = 0
    catalogue_formes: int = 0
    chiffres_hors_socle_en_contexte: list[dict[str, object]] = field(default_factory=list)
    #: Renseigné quand le document n'a pas pu être rendu. Ne pas pouvoir
    #: mesurer EST la mesure : on le dit, on ne rend pas des zéros.
    echec: str = ""

    @property
    def part_des_figures(self) -> int | None:
        if not self.figures_demandees:
            return None
        return 100 * self.figures_obtenues // self.figures_demandees

    def en_dict(self) -> dict[str, object]:
        sources = self.sources
        return {
            "echec": self.echec,
            "figures": {
                "demandees": self.figures_demandees,
                "obtenues": self.figures_obtenues,
                "part": self.part_des_figures,
                "completees": self.figures_completees,
                "reparees": self.figures_reparees,
                "en_tableau": self.figures_en_tableau,
                "perdues": self.figures_perdues,
            },
            # `null` et non zéro : le chapitre Sources était introuvable.
            "sources": None if sources is None else {
                "exterieures": sources.exterieures,
                "sans_adresse": sources.sans_adresse,
                "du_client": sources.du_client,
                "lignes": [ligne[:160] for ligne in sources.lignes[:12]],
            },
            "chiffres_hors_socle": self.chiffres_hors_socle,
            "autres_anomalies": self.autres_anomalies,
            "adresses_collectees": self.adresses_collectees,
            "anomalies": self.anomalies,
            "gate": self.gate,
            "figures_abandonnees": self.figures_abandonnees,
            "chiffres_hors_socle_en_contexte": self.chiffres_hors_socle_en_contexte,
            "catalogue": {
                "figures": self.catalogue_figures, "formes": self.catalogue_formes,
            },
        }


def sections_du_dossier(job: GenerationJob) -> list[tuple[int, str, str]]:
    """Les (numéro, titre, corps) du document, comme le gate les voit.

    ## Pourquoi on ne redécoupe pas le markdown soi-même

    La première version de cette mesure le faisait, en coupant sur les titres
    `#` du markdown assemblé. Elle n'a jamais trouvé le chapitre Sources d'une
    stratégie — et annonçait donc `sources: null` sur QUATRE dossiers Zenitek
    qui en avaient un (`str.20.sources`).

    La cause : le titre ainsi reconstruit portait son numéro (« 20. Sources »),
    alors que `_trouver_chapitre_sources` attend un titre qui COMMENCE par
    « sources ». Deux découpages du même document, pas d'accord entre eux —
    exactement le défaut que la règle 5 condamne. `render_client_document`
    rend le titre propre, et c'est lui que le gate emploie.
    """
    from generation.rendering import render_client_document

    document = render_client_document(job)
    return [(s.number, s.title, s.body) for s in document.sections]


def mesurer_les_sources(
    sections: list[tuple[int, str, str]],
) -> MesureDesSources | None:
    """None quand le document n'a pas de chapitre Sources — pas zéro."""
    section = _trouver_chapitre_sources(sections)
    if section is None:
        return None
    mesure = MesureDesSources()
    for ligne in _sources_listees(section[2]):
        mesure.lignes.append(ligne)
        if _SOURCE_DU_CLIENT_RE.search(ligne):
            mesure.du_client += 1
            continue
        mesure.exterieures += 1
        if adresse_de_la_source(ligne) is None:
            mesure.sans_adresse += 1
    return mesure


def adresses_collectees(job: GenerationJob) -> int:
    """Les URL distinctes du brief de recherche : ce que le modèle POUVAIT citer."""
    return len(set(_URL_RE.findall(job.research_brief or "")))


#: Exemples gardés par contrôle : assez pour juger si le motif est VRAI en le
#: retrouvant dans le document (règle 2), trop peu pour noyer le rapport.
_EXEMPLES_PAR_CONTROLE = 4


def _regrouper(
    elements: list[tuple[str, int | None, str, str]],
) -> dict[str, list[dict[str, object]]]:
    """(contrôle, chapitre, détail, extrait) → {contrôle: [exemples]}, avec le total."""
    groupes: dict[str, list[dict[str, object]]] = {}
    totaux: dict[str, int] = {}
    for controle, chapitre, detail, extrait in elements:
        totaux[controle] = totaux.get(controle, 0) + 1
        exemples = groupes.setdefault(controle, [])
        if len(exemples) < _EXEMPLES_PAR_CONTROLE:
            exemples.append({
                "chapitre": chapitre, "detail": detail[:300], "extrait": extrait[:1400],
            })
    for controle, exemples in groupes.items():
        exemples.insert(0, {"total": totaux[controle]})
    return groupes


#: Les contrôles du gate qui jugent la FIN d'un chapitre : sans elle, leur
#: motif ne dit pas si la phrase est coupée ou si c'est une étiquette qu'on a
#: prise pour une phrase (trois études de marché, 14/09/2026).
_JUGENT_LA_FIN = frozenset({"troncature"})


def _tableau_de_la_colonne(corps: str, detail: str) -> str:
    """Le tableau dont le motif nomme la colonne : « Colonne « Écart » : … ».

    Un total faux ne se juge pas sur son seul motif : il faut les lignes que le
    contrôle a additionnées pour dire s'il fallait les additionner.
    """
    from generation.arithmetique import totaux_faux

    blocs: list[list[str]] = [[]]
    for ligne in corps.splitlines():
        if ligne.lstrip().startswith("|"):
            blocs[-1].append(ligne.strip())
        elif blocs[-1]:
            blocs.append([])
    # Le bloc qui produit CE motif, pas le premier qui nomme la colonne : un
    # chapitre porte souvent plusieurs colonnes « Montant ».
    for bloc in blocs:
        if bloc and any(str(faute) == detail for faute in totaux_faux("\n".join(bloc))):
            return " / ".join(bloc)
    return ""


def _phrases_du_sujet(sections: list[tuple[int, str, str]], detail: str) -> str:
    """Les phrases du DOCUMENT qui parlent le plus du sujet de la décision absente.

    « le document ne pose nulle part les canaux secondaires » : sans les
    phrases qui parlent de canaux, on ne peut pas dire si la décision manque
    ou si elle est écrite sous une forme que le contrôle ne lit pas. Le
    contrôle lit tout le document ; la mesure aussi. Les phrases qui portent
    le plus de mots du sujet passent en premier — les quatre premières du
    chapitre porteur ne suffisaient pas (corpus du 14/09/2026).
    """
    sujet = re.search(r"nulle part (.+?)\.", detail)
    if sujet is None:
        return ""
    racines = {mot[:5].casefold() for mot in re.findall(r"[^\W\d_]{5,}", sujet.group(1))}
    if not racines:
        return ""
    candidates: list[tuple[int, int, str]] = []
    for numero, _titre, corps in sections:
        for phrase in re.split(r"(?<=[.!?])\s+|\n+", corps):
            touchees = sum(1 for racine in racines if racine in phrase.casefold())
            if touchees:
                candidates.append((touchees, numero, " ".join(phrase.split())[:200]))
    candidates.sort(key=lambda c: -c[0])
    return " / ".join(f"[ch. {numero}] {phrase}" for _, numero, phrase in candidates[:6])


def _echecs_du_gate(
    job: GenerationJob, sections: list[tuple[int, str, str]] | None = None,
) -> dict[str, list[dict[str, object]]]:
    """Le gate, en lecture seule. Une panne se DIT, elle ne rend pas un vide."""
    from generation.gate import run_delivery_gate

    try:
        rapport = run_delivery_gate(job)
    except Exception as exc:  # noqa: BLE001
        return {"gate_illisible": [{"total": 1}, {
            "chapitre": None, "detail": f"{type(exc).__name__} : {exc}"[:300], "extrait": "",
        }]}
    corps_par_numero = {numero: corps for numero, _, corps in sections or []}

    def extrait(echec: object) -> str:
        numero = getattr(echec, "chapter_number", None)
        corps = corps_par_numero.get(numero, "") if numero is not None else ""
        check, detail = getattr(echec, "check", ""), getattr(echec, "detail", "")
        if check in _JUGENT_LA_FIN:
            return corps.rstrip()[-200:]
        if check == "calcul_faux":
            return _tableau_de_la_colonne(corps, detail)
        if check.endswith("decision_absente"):
            return _phrases_du_sujet(sections or [], detail)
        return ""

    return _regrouper([
        (e.check, e.chapter_number, e.detail, extrait(e)) for e in rapport.failures
    ])


def mesurer(job: GenerationJob) -> Mesure:
    """Compte les trois défauts sur le livrable du dossier. N'écrit rien."""
    from generation.rendu_word.services import produire_docx
    from generation.verification.services import verifier_livrable

    with tempfile.TemporaryDirectory() as dossier:
        try:
            livrable = produire_docx(job, destination=Path(dossier) / "mesure.docx")
        except Exception as exc:  # noqa: BLE001
            return Mesure(echec=str(exc), adresses_collectees=adresses_collectees(job))
        rapport = livrable.rapport
        controle = verifier_livrable(
            job, livrable.chemin, assemblage=rapport, ouvrir_incident=False,
        )

    from generation.rendu_word.catalogue_figures import figures_possibles
    from generation.socle.services import socle_verrouille

    sections = sections_du_dossier(job)
    socle = socle_verrouille(job)
    catalogue = figures_possibles(socle) if socle is not None else []
    completees = len(rapport.graphiques_completes)
    reparees = len(rapport.graphiques_repares)
    hors_socle = [
        a.detail for a in controle.anomalies if a.controle == MOTIF_HORS_SOCLE
    ]
    # Avec leur phrase : 757 motifs sur le corpus, et quatre exemples par
    # dossier ne permettaient pas de séparer les calculs posés des inventions.
    hors_socle_en_contexte: list[dict[str, object]] = [
        {"chapitre": a.chapitre, "detail": a.detail[:160], "extrait": a.extrait[:240]}
        for a in controle.anomalies if a.controle == MOTIF_HORS_SOCLE
    ]
    return Mesure(
        figures_demandees=rapport.graphiques_demandes,
        figures_obtenues=max(rapport.graphiques_rendus - completees - reparees, 0),
        figures_completees=completees,
        figures_reparees=reparees,
        figures_en_tableau=len(rapport.graphiques_en_tableau),
        figures_perdues=len(rapport.graphiques_abandonnes),
        sources=mesurer_les_sources(sections),
        chiffres_hors_socle=hors_socle,
        autres_anomalies=len(controle.anomalies) - len(hors_socle),
        adresses_collectees=adresses_collectees(job),
        anomalies=_regrouper([
            (a.controle, a.chapitre, a.detail, a.extrait) for a in controle.anomalies
        ]),
        gate=_echecs_du_gate(job, sections),
        figures_abandonnees=list(rapport.diagnostic_des_abandons),
        chiffres_hors_socle_en_contexte=hors_socle_en_contexte,
        catalogue_figures=len(catalogue),
        catalogue_formes=len({proposition.type_graphique for proposition in catalogue}),
    )

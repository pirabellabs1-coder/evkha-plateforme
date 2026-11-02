"""Chaque demande du client reçoit un chapitre qui en a la charge.

## Le retour qui a créé ce module

Étude de marché `a6947890` (SUN TZU ORGANISATION, terroir français vendu en
Asie, 01/11/2026). Le brief demandait, en toutes lettres et « en priorité » :
le coût livré d'un lot de 25 €, le coût réel d'envoi d'une bière à l'unité, la
comparaison colis / envoi groupé / conteneur, le volume à partir duquel le
modèle devient rentable, des prix réels relevés sur les plateformes. Le
contrôle de couverture a compté **48 demandes insuffisamment traitées sur 54**,
dont toutes celles-là. Retour de la cliente : « il n'y a pas de calcul par lot,
pas de prix, pas d'estimation ».

Le brief partait pourtant ENTIER dans chaque chapitre (`BRIEF_CLIENT`, JSON
brut). Mais le plan d'une étude de marché est fixe — vingt-trois chapitres dont
aucun ne s'appelle « coût d'un lot » — et chaque chapitre écrit son propre
sujet. Une demande que le plan ne prévoit pas n'appartient à personne : tous la
voient, aucun ne la traite, et le chapitre qui s'en approche la renvoie « aux
premiers envois ». La couverture la constate APRÈS coup ; rien ne la
prévenait.

C'est la classe, pas l'instance (règle 4) : le même trou vaut pour les quatre
livrables, pour toute demande qu'un plan fixe ne nomme pas.

## Ce que ce module fait

Au lancement, APRÈS le socle et AVANT le premier chapitre, un appel structuré
lit le brief découpé en passages (le découpage de `couverture` — une seule
source, règle 5) et le plan du livrable, et confie chaque DEMANDE à UN
chapitre. Le résultat est gardé sur le dossier (`memoire_etude`), donc payé
une fois et identique pour tous les chapitres, reprises comprises.

Chaque chapitre reçoit alors, dans la partie de son prompt qui lui est propre,
les demandes dont il a la charge et ce que la réponse doit contenir. La table
complète, elle, va dans la partie commune (mise en cache) : un chapitre sait
qui traite quoi et ne double pas la réponse. Elle dit qui DOIT répondre, pas
qui a répondu — l'annexe des réponses au client ne peut pas s'en servir comme
preuve (business plan ÉCLORE, 29/09/2026 : « traité » prouvé par un simple
numéro de chapitre).

## Ce qu'il ne fait pas

Il ne juge pas le document : c'est `couverture`, après coup, sur le texte
assemblé — un contrôle et ce qu'il contrôle ne jugent pas sur la même
évidence (règle 9). Une répartition en échec n'arrête pas l'étude : les
chapitres retombent sur le brief brut, comme avant, et un incident le dit
(règle 1).
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from .couverture import Candidat, candidats_du_brief

_log = logging.getLogger(__name__)

OUTIL_NOM = "repartir_les_demandes"
OUTIL_DESCRIPTION = (
    "Confie chaque demande du brief au chapitre du plan qui doit y répondre."
)

#: Clé de la répartition dans `GenerationJob.memoire_etude`.
CLE = "repartition_des_demandes"

#: Borne de sortie de l'appel. Un plafond, pas une dépense : seul ce qui est
#: produit se paie.
MAX_TOKENS_PLAFOND = 16_000

#: Le même nombre d'essais que le socle.
ESSAIS_MAX = 3

#: Au-delà de cette part de passages sans verdict, la répartition ne conclut
#: pas. Même seuil que la couverture : les deux lisent le même découpage.
PART_NON_REPARTIE_MAX = 0.2

#: Au-delà, un chapitre ne peut pas répondre EN ENTIER à chacune : sa cible de
#: mots ne bouge pas. Dit au modèle ; les dépassements sont dans la trace
#: (`surcharges`).
DEMANDES_PAR_CHAPITRE_MAX = 4


# Le numéro, pas le texte : même leçon que `couverture.Reponse`.
class Affectation(BaseModel):
    """Une demande du brief et le chapitre qui en a la charge."""

    model_config = {"extra": "forbid"}

    n: int = Field(ge=1)
    chapitre: int = Field(ge=0)
    #: Ce que la réponse doit contenir pour que le client puisse décider.
    attendu: str = ""


# `demandes` avant `contexte` : une réponse coupée perd la fin du schéma.
class RepartitionDuModele(BaseModel):
    """Chaque numéro du brief figure dans l'une des deux listes."""

    model_config = {"extra": "forbid"}

    demandes: list[Affectation] = Field(default_factory=list)
    contexte: list[int] = Field(default_factory=list)


@dataclass(frozen=True)
class ChapitreDuPlan:
    numero: int
    titre: str
    sections: tuple[str, ...] = ()


@dataclass
class Repartition:
    #: (numéro du chapitre, champ, texte de la demande, attendu)
    demandes: list[tuple[int, str, str, str]] = field(default_factory=list)
    contexte: int = 0
    #: Passages sans verdict, ou confiés à un chapitre hors du plan.
    non_reparties: list[str] = field(default_factory=list)
    executee: bool = False
    motif: str = ""
    #: Consommation cumulée de tous les essais, payés même s'ils échouent.
    input_tokens: int = 0
    output_tokens: int = 0
    modele: str = ""
    essais: int = 0

    def surcharges(self) -> dict[str, int]:
        """Les chapitres qui ont reçu plus de demandes que le modèle n'en
        devait confier — mesure, pas refus."""
        comptes = Counter(c for c, _, _, _ in self.demandes)
        return {str(c): n for c, n in sorted(comptes.items()) if n > DEMANDES_PAR_CHAPITRE_MAX}

    def en_dict(self) -> dict[str, Any]:
        return {
            "executee": self.executee,
            "motif": self.motif,
            "essais": self.essais,
            "surcharges": self.surcharges(),
            "demandes": [
                {"chapitre": c, "champ": champ, "texte": t, "attendu": a}
                for c, champ, t, a in self.demandes
            ],
            "contexte": self.contexte,
            "non_reparties": list(self.non_reparties),
        }


def chapitres_eligibles(plan: Iterable[Any]) -> list[ChapitreDuPlan]:
    """Les chapitres de fond du plan : ni la fiche projet, ni les sources, ni
    les annexes. L'annexe « Réponses essentielles au client » RÉSUME les
    réponses ; lui confier une demande, c'est la faire traiter en une ligne."""
    from .blueprints import SectionKind  # noqa: PLC0415

    return [
        ChapitreDuPlan(int(c.number), str(c.title), tuple(getattr(c, "sections", ()) or ()))
        for c in plan
        if getattr(c, "section_kind", SectionKind.CHAPTER) == SectionKind.CHAPTER
    ]


_SYSTEME = (
    "Tu prépares la rédaction d'une étude — étude de marché, business plan, "
    "étude concurrentielle ou stratégie — dont le plan est FIXE. Le client a "
    "écrit un brief ; certaines de ses demandes ne correspondent à aucun "
    "titre du plan. Si personne ne s'en charge, aucun chapitre ne les traite.\n"
    "\n"
    "On te donne le brief découpé en passages NUMÉROTÉS, et le plan. Pour "
    "CHAQUE numéro, sans en omettre aucun :\n"
    "\n"
    "- `contexte` : le client décrit sa situation, son secteur, ses documents "
    "— rien qui appelle une réponse ;\n"
    "- `demande` : le client veut obtenir, savoir, chiffrer, comparer ou "
    "décider quelque chose. Tu la confies à UN chapitre du plan : celui dont "
    "le sujet est le plus proche, même s'il ne la nomme pas. Une demande de "
    "calcul (coût, prix, marge, volume de rentabilité, besoin de financement) "
    "va au chapitre qui raisonne en chiffres sur la viabilité ou l'économie "
    "du projet.\n"
    "\n"
    "Pour chaque demande, `attendu` dit en une phrase ce que la réponse doit "
    "CONTENIR pour que le client puisse décider : « un calcul poste par poste "
    "du coût livré d'un lot de 25 € : achat, transport, droits, commission, "
    "total » — pas « traiter la logistique ».\n"
    "\n"
    f"Répartis : pas plus de {DEMANDES_PAR_CHAPITRE_MAX} demandes par "
    "chapitre. Au-delà, confie la suivante au chapitre le plus proche qui en "
    "a moins. Deux passages qui disent la même chose vont au même chapitre.\n"
    "\n"
    "Désigne les passages et les chapitres par leur numéro ; ne recopie pas "
    "leur texte.\n"
    "\n"
    f"Tu réponds exclusivement par un appel de l'outil `{OUTIL_NOM}`."
)


def _prompt(candidats: list[Candidat], chapitres: list[ChapitreDuPlan]) -> str:
    plan = "\n".join(
        f"{c.numero} — {c.titre}"
        + (f" (sections : {' ; '.join(c.sections)})" if c.sections else "")
        for c in chapitres
    )
    brief = "\n".join(f"{c.numero}. [{c.champ}] {c.texte}" for c in candidats)
    return (
        f"PLAN DE L'ÉTUDE :\n{plan}\n\n"
        f"BRIEF DU CLIENT, PASSAGE PAR PASSAGE :\n{brief}\n\n"
        f"Classe CHACUN des {len(candidats)} numéros, sans en omettre."
    )


def repartir_les_demandes(
    *, client: Any, variables: Any, plan: Iterable[Any],
) -> Repartition:
    """Confie chaque demande du brief à un chapitre, en s'y reprenant jusqu'à
    `ESSAIS_MAX` fois. La consommation de TOUS les essais est portée par le
    résultat, pour que l'appelant la compte.

    Le vrai client rend une charge vide quand le modèle n'appelle pas l'outil
    (`tool_choice` automatique) : c'est l'aléa transitoire par excellence, et
    le socle s'y reprend déjà à trois fois. Un seul essai désactivait la
    répartition pour tout le dossier (revue du 02/11/2026).

    Ne lève jamais : une répartition impossible laisse les chapitres sur le
    brief brut, comme avant — elle ne fait pas mourir une étude.
    """
    repartition = Repartition()
    candidats = candidats_du_brief(variables)
    chapitres = chapitres_eligibles(plan)
    if not candidats:
        repartition.executee = True
        repartition.motif = "aucun passage de brief à répartir"
        return repartition
    if not chapitres:
        repartition.motif = "plan sans chapitre de fond"
        return repartition

    # Le plafond, pas une estimation : on ne paie que ce qui est produit, et
    # une réponse coupée au milieu de l'appel d'outil arrive VIDE — toute la
    # répartition perdue pour quelques jetons économisés (revue du 02/11).
    budget = MAX_TOKENS_PLAFOND
    for essai in range(1, ESSAIS_MAX + 1):
        repartition = Repartition(
            input_tokens=repartition.input_tokens,
            output_tokens=repartition.output_tokens,
            modele=repartition.modele,
            essais=essai,
        )
        try:
            resultat = client.complete_structured(
                system=_SYSTEME,
                prompt=_prompt(candidats, chapitres),
                outil_nom=OUTIL_NOM,
                outil_description=OUTIL_DESCRIPTION,
                schema=RepartitionDuModele.model_json_schema(),
                max_tokens=budget,
            )
        except Exception as erreur:  # noqa: BLE001 — une panne ici ne tue pas l'étude
            _log.exception("Répartition des demandes impossible (essai %s)", essai)
            repartition.motif = f"{type(erreur).__name__} : {erreur}"
            continue
        # Compté AVANT toute lecture : un appel payé reste payé, même si sa
        # réponse est illisible.
        repartition.input_tokens += int(getattr(resultat, "input_tokens", 0) or 0)
        repartition.output_tokens += int(getattr(resultat, "output_tokens", 0) or 0)
        repartition.modele = str(getattr(resultat, "model", "") or "") or repartition.modele
        _lire(repartition, dict(getattr(resultat, "payload", {}) or {}), candidats, chapitres)
        coupee = str(getattr(resultat, "stop_reason", "") or "") == "max_tokens"
        _conclure(repartition, len(candidats), coupee=coupee, budget=budget)
        if repartition.executee:
            break
    return repartition


def _lire(
    repartition: Repartition,
    charge: dict[str, Any],
    candidats: list[Candidat],
    chapitres: list[ChapitreDuPlan],
) -> None:
    """Lit la réponse LIGNE PAR LIGNE. Valider le tout d'un bloc faisait perdre
    la répartition entière pour une seule ligne fautive (`n: 0`, un champ en
    trop) : la ligne fautive tombe dans les non répartis, les autres restent."""
    par_numero: dict[int, Affectation] = {}
    for brute in charge.get("demandes") or []:
        try:
            lue = Affectation.model_validate(brute)
        except ValidationError:
            continue
        par_numero.setdefault(lue.n, lue)
    contexte = {n for n in charge.get("contexte") or [] if isinstance(n, int)}

    numeros = {c.numero for c in chapitres}
    for candidat in candidats:
        affectation = par_numero.get(candidat.numero)
        if affectation is not None and affectation.chapitre in numeros:
            repartition.demandes.append((
                affectation.chapitre, candidat.champ, candidat.texte,
                affectation.attendu.strip(),
            ))
        elif affectation is None and candidat.numero in contexte:
            repartition.contexte += 1
        else:
            # Ni contexte, ni demande confiée à un chapitre qui existe : la
            # répartition ne sait pas. Le dire, ne pas deviner.
            repartition.non_reparties.append(candidat.texte)


def _conclure(
    repartition: Repartition, total: int, *, coupee: bool, budget: int,
) -> None:
    """Conclut, ou dit pourquoi pas. Même non concluante, une répartition GARDE
    ce qu'elle a confié : une demande qui a reçu un chapitre vaut mieux qu'une
    demande sans personne."""
    manquants = len(repartition.non_reparties)
    if coupee and manquants:
        repartition.motif = (
            f"réponse coupée par le budget ({budget} jetons) : "
            f"{manquants} passage(s) sur {total} sans verdict"
        )
    elif manquants / total > PART_NON_REPARTIE_MAX:
        repartition.motif = (
            f"réponse incomplète : {manquants} passage(s) sur {total} non répartis"
        )
    else:
        repartition.motif = ""
        repartition.executee = True


# ─────────────────────────────────────────────────────────────────────────────
# Ce que les chapitres en reçoivent
# ─────────────────────────────────────────────────────────────────────────────


def _demandes(memoire_etude: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    trace = (memoire_etude or {}).get(CLE) or {}
    return [d for d in trace.get("demandes") or [] if isinstance(d, dict)]


def bloc_de_la_repartition(memoire_etude: Mapping[str, Any] | None) -> str:
    """La table complète, pour la partie COMMUNE du prompt (mise en cache).

    Identique pour tous les chapitres du dossier : elle est figée avant le
    premier. Vide pour un dossier sans répartition — rien ne change pour lui.
    """
    demandes = _demandes(memoire_etude)
    if not demandes:
        return ""
    lignes = [
        f"- chapitre {d['chapitre']} : {d['texte']}"
        for d in sorted(demandes, key=lambda d: int(d.get("chapitre", 0)))
    ]
    return (
        "RÉPARTITION DES DEMANDES DU CLIENT — chaque demande a UN chapitre "
        "qui en a la charge ; ne la traite pas à sa place. Cette table dit "
        "qui DOIT répondre, pas qui a répondu : elle ne prouve aucun statut. "
        "Le statut d'une demande se prouve par la section qui y répond, "
        "comme dit plus haut.\n" + "\n".join(lignes)
    )


def bloc_du_chapitre(memoire_etude: Mapping[str, Any] | None, numero: int) -> str:
    """Les demandes dont CE chapitre a la charge, pour sa partie propre."""
    siennes = [d for d in _demandes(memoire_etude) if d.get("chapitre") == numero]
    if not siennes:
        return ""
    lignes = []
    for i, d in enumerate(siennes, start=1):
        ligne = f"{i}. {d['texte']}"
        if d.get("attendu"):
            ligne += f"\n   Attendu : {d['attendu']}"
        lignes.append(ligne)
    return (
        "DEMANDES DU CLIENT CONFIÉES À CE CHAPITRE — tu en es le SEUL "
        "responsable dans toute l'étude ; aucun autre chapitre ne les "
        "traitera.\n"
        + "\n".join(lignes)
        + "\n\nChacune reçoit une réponse COMPLÈTE dans ce chapitre — une "
        "section ou un tableau dont l'intitulé reprend les mots du client. "
        "Une demande de calcul (coût, prix, marge, volume, rentabilité) "
        "reçoit un calcul POSÉ ICI : chaque poste, son montant, sa source ou "
        "l'hypothèse prudente qui le remplace, puis le résultat. Une "
        "hypothèse suit la règle des hypothèses — elle se dit hypothèse, "
        "nomme sa donnée de départ et son raisonnement — et dit ce qui la "
        "confirmera. Mais le calcul, lui, n'est jamais reporté : ni « aux "
        "premiers envois », ni « à une étude ultérieure », ni à un autre "
        "chapitre."
    )


def repartition_de_demonstration(contexte: str) -> dict[str, object]:
    """Pour la doublure : confie chaque passage, à tour de rôle, aux chapitres
    du plan lus dans le prompt. Assez pour que la répétition à blanc fasse
    passer le bloc dans les chapitres, sans rien juger."""
    chapitres = [int(n) for n in re.findall(r"(?m)^(\d+) — ", contexte)]
    passages = [int(n) for n in re.findall(r"(?m)^(\d+)\. \[", contexte)]
    if not chapitres:
        return {"demandes": [], "contexte": passages}
    return {
        "demandes": [
            {"n": n, "chapitre": chapitres[i % len(chapitres)], "attendu": ""}
            for i, n in enumerate(passages)
        ],
        "contexte": [],
    }

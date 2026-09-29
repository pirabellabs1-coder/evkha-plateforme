"""Les faits de l'étude : le socle, et tout ce qui s'en déduit par identité.

## Le défaut, mesuré

29/09/2026, business plan ÉCLORE : « revenu mensuel de 1 986,32 € » écrit à
côté d'un « résultat net de 23 223,86 € ». 1 986,32 × 12 = 23 835,86 : la CAF,
pas le résultat net. Le modèle avait refait la division lui-même, sur la
mauvaise série, et rien ne pouvait le voir — la mensualisation n'existait
nulle part ailleurs que dans sa phrase.

## Ce que ce module calcule, et ce qu'il refuse

Uniquement des IDENTITÉS, comme `socle/calculs.py` : un écart, une évolution
en pourcentage, une division par douze, une part, CAF − résultat net. Jamais
une estimation (« clientèle × panier = CA » suppose un achat par client et
par an : c'est une hypothèse, pas un calcul). Un dérivé dont un terme manque
n'est pas produit : l'absence se dit, un chiffre inventé se lit.

Chaque fait porte sa formule et sa définition : c'est ce qui permet au
rédacteur de citer le bon (« revenu mensuel » n'est pas « CAF ÷ 12 ») et au
contrôleur de juger une phrase.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from generation.socle.referentiel import Fiabilite
from generation.socle.schema import Socle, valeur_en_unites_de_base

#: Origine d'un fait, telle que le lecteur la lit dans l'annexe des chiffres.
ORIGINE_PAR_FIABILITE: dict[str, str] = {
    Fiabilite.DECLAREE: "declaree",
    Fiabilite.OBSERVEE: "sourcee",
    Fiabilite.ESTIMEE: "estimee",
    Fiabilite.SCENARIO: "hypothese",
}


@dataclass(frozen=True)
class Fait:
    """Un chiffre de l'étude, adressable par son identifiant."""

    id: str
    valeur: float
    unite: str
    libelle: str
    #: « declaree », « sourcee », « estimee », « hypothese » ou « calculee ».
    origine: str
    annee: int | None = None
    #: La formule, écrite pour un lecteur (« CAF − résultat net »). Vide pour
    #: une donnée du socle.
    formule: str = ""
    #: Les faits dont celui-ci découle.
    depuis: tuple[str, ...] = field(default_factory=tuple)
    #: Ce que l'indicateur MESURE — la phrase qui empêche de confondre deux
    #: séries voisines (résultat net et CAF).
    definition: str = ""


#: Ce que mesurent les séries du prévisionnel. Une définition par série, lue
#: par le rédacteur ET par le contrôleur : deux définitions du résultat net
#: dans le même dossier, c'est le défaut qu'on répare (règle 5).
DEFINITIONS: dict[str, str] = {
    "ca_previsionnel": "chiffre d'affaires hors taxes de l'exercice",
    "resultat_net": (
        "résultat net comptable : ce qui reste après toutes les charges, les "
        "dotations aux amortissements et l'impôt — ce n'est PAS la CAF"
    ),
    "caf": (
        "capacité d'autofinancement : résultat net + dotations aux "
        "amortissements — ressource dégagée par l'activité, ce n'est PAS un "
        "résultat ni un revenu"
    ),
    "ebe": "excédent brut d'exploitation : chiffre d'affaires − charges d'exploitation décaissées",
    "charges_fixes": "charges fixes annuelles de l'exercice",
    "remuneration_dirigeant": "rémunération annuelle du dirigeant prévue au prévisionnel",
    "masse_salariale": "masse salariale annuelle chargée",
    "tresorerie_fin": "trésorerie disponible au 31 décembre de l'exercice",
    "dette_residuelle": "capital restant dû sur les emprunts en fin d'exercice",
}

#: Le nom qu'une série porte dans une phrase.
NOMS: dict[str, str] = {
    "ca_previsionnel": "chiffre d'affaires",
    "resultat_net": "résultat net",
    "caf": "capacité d'autofinancement",
    "ebe": "excédent brut d'exploitation",
    "charges_fixes": "charges fixes",
    "remuneration_dirigeant": "rémunération du dirigeant",
    "masse_salariale": "masse salariale",
    "tresorerie_fin": "trésorerie de fin d'exercice",
    "dette_residuelle": "dette résiduelle",
}

#: Les séries qui sont des FLUX annuels : elles se mensualisent. Une
#: trésorerie de fin d'exercice ou une dette résiduelle est un STOCK — la
#: diviser par douze n'a aucun sens.
FLUX = frozenset({
    "ca_previsionnel", "resultat_net", "caf", "ebe", "charges_fixes",
    "remuneration_dirigeant", "masse_salariale",
})

_SERIE = re.compile(r"^(?P<serie>[a-z_]+?)_an(?P<rang>[1-9])$")


def _base(fait: Fait) -> tuple[float, str] | None:
    """La valeur ramenée à l'unité de base de sa devise, ou None hors monnaie."""
    return valeur_en_unites_de_base(fait.valeur, fait.unite)


def _faits_du_socle(socle: Socle) -> dict[str, Fait]:
    faits: dict[str, Fait] = {}
    for item in socle.donnees:
        serie = _SERIE.match(item.id)
        definition = DEFINITIONS.get(serie.group("serie"), "") if serie else ""
        faits[item.id] = Fait(
            id=item.id,
            valeur=item.valeur,
            unite=item.unite,
            libelle=item.libelle,
            origine=ORIGINE_PAR_FIABILITE.get(item.fiabilite, "estimee"),
            annee=item.annee,
            depuis=tuple(item.derivee_de),
            definition=definition,
        )
    return faits


def _series(faits: dict[str, Fait]) -> dict[str, dict[int, Fait]]:
    """Les séries annuelles du socle : `{"resultat_net": {1: fait, 2: …}}`."""
    series: dict[str, dict[int, Fait]] = {}
    for fait in faits.values():
        trouve = _SERIE.match(fait.id)
        if trouve:
            series.setdefault(trouve.group("serie"), {})[int(trouve.group("rang"))] = fait
    return series


def _monetaire(*termes: Fait) -> tuple[list[float], str] | None:
    """Les termes en unité de base, s'ils sont tous monétaires et de même devise."""
    bases = [_base(t) for t in termes]
    if any(b is None for b in bases):
        return None
    devises = {b[1] for b in bases if b is not None}
    if len(devises) != 1:
        return None
    return [b[0] for b in bases if b is not None], devises.pop()


def _arrondi_monetaire(valeur: float) -> float:
    return round(valeur, 2)


def _derive(
    produit: str,
    termes: Iterable[Fait],
    calcul: Callable[[list[float]], float | None],
    *,
    libelle: str,
    formule: str,
    unite: str | None = None,
    annee: int | None = None,
    definition: str = "",
) -> Fait | None:
    """Un dérivé monétaire (ou un pourcentage de termes monétaires)."""
    termes = tuple(termes)
    lus = _monetaire(*termes)
    if lus is None:
        return None
    valeurs, devise = lus
    resultat = calcul(valeurs)
    if resultat is None:
        return None
    if unite is None:
        unite, resultat = devise, _arrondi_monetaire(resultat)
    else:
        resultat = round(resultat, 1)
    return Fait(
        id=produit,
        valeur=resultat,
        unite=unite,
        libelle=libelle,
        origine="calculee",
        annee=annee,
        formule=formule,
        depuis=tuple(t.id for t in termes),
        definition=definition,
    )


def _evolution(valeurs: list[float]) -> float | None:
    depart, arrivee = valeurs
    if depart == 0:
        return None
    return (arrivee - depart) / abs(depart) * 100.0


def _part(valeurs: list[float]) -> float | None:
    partie, tout = valeurs
    if tout == 0:
        return None
    return partie / tout * 100.0


def faits_de_l_etude(socle: Socle) -> dict[str, Fait]:
    """Les faits du socle et leurs dérivés par identité, indexés par identifiant.

    Déterministe : le même socle donne toujours les mêmes faits, dans le même
    ordre — c'est ce qui permet de re-rendre un chapitre sans le réécrire.
    """
    faits = _faits_du_socle(socle)
    derives: list[Fait | None] = []
    series = _series(faits)

    for serie, par_rang in series.items():
        nom = NOMS.get(serie, serie.replace("_", " "))
        rangs = sorted(par_rang)
        # Évolutions et écarts entre exercices consécutifs, puis du premier au dernier.
        paires = list(zip(rangs, rangs[1:], strict=False))
        if len(rangs) > 2:
            paires.append((rangs[0], rangs[-1]))
        for a, b in paires:
            fa, fb = par_rang[a], par_rang[b]
            derives.append(_derive(
                f"{serie}_evolution_an{a}_an{b}", (fa, fb), _evolution,
                libelle=f"Évolution du {nom} de l'exercice {a} à l'exercice {b}",
                formule=f"({serie}_an{b} − {serie}_an{a}) ÷ |{serie}_an{a}| × 100",
                unite="%", annee=fb.annee,
            ))
            derives.append(_derive(
                f"{serie}_ecart_an{a}_an{b}", (fa, fb), lambda v: v[1] - v[0],
                libelle=f"Écart de {nom} entre l'exercice {a} et l'exercice {b}",
                formule=f"{serie}_an{b} − {serie}_an{a}", annee=fb.annee,
            ))
        if serie in FLUX:
            for rang, fait in par_rang.items():
                derives.append(_derive(
                    f"{serie}_mensuel_an{rang}", (fait,), lambda v: v[0] / 12.0,
                    libelle=f"{nom[0].upper()}{nom[1:]} mensuel moyen, exercice {rang}",
                    formule=f"{serie}_an{rang} ÷ 12", annee=fait.annee,
                    definition=(
                        f"moyenne mensuelle du {nom} — c'est "
                        f"{DEFINITIONS.get(serie, nom)} divisé par douze"
                    ),
                ))

    # CAF = résultat net + dotations : les dotations se déduisent, exactement.
    for rang, caf in series.get("caf", {}).items():
        resultat = series.get("resultat_net", {}).get(rang)
        if resultat is not None:
            derives.append(_derive(
                f"dotations_an{rang}", (caf, resultat), lambda v: v[0] - v[1],
                libelle=f"Dotations aux amortissements, exercice {rang}",
                formule=f"caf_an{rang} − resultat_net_an{rang}", annee=caf.annee,
                definition=(
                    "dotations aux amortissements, déduites de "
                    "CAF = résultat net + dotations"
                ),
            ))

    # Marges rapportées au chiffre d'affaires du même exercice.
    for rang, ca in series.get("ca_previsionnel", {}).items():
        for serie, nom in (("ebe", "marge d'EBE"), ("resultat_net", "marge nette")):
            terme = series.get(serie, {}).get(rang)
            if terme is not None:
                derives.append(_derive(
                    f"{'marge_ebe' if serie == 'ebe' else 'marge_nette'}_an{rang}",
                    (terme, ca), _part,
                    libelle=f"{nom[0].upper()}{nom[1:]}, exercice {rang}",
                    formule=f"{serie}_an{rang} ÷ ca_previsionnel_an{rang} × 100",
                    unite="%", annee=ca.annee,
                ))
        seuil = faits.get("seuil_rentabilite")
        if seuil is not None:
            derives.append(_derive(
                f"marge_securite_an{rang}", (ca, seuil),
                lambda v: (v[0] - v[1]) / v[0] * 100.0 if v[0] else None,
                libelle=f"Marge de sécurité sur le seuil de rentabilité, exercice {rang}",
                formule=(
                    f"(ca_previsionnel_an{rang} − seuil_rentabilite) "
                    f"÷ ca_previsionnel_an{rang} × 100"
                ),
                unite="%", annee=ca.annee,
            ))

    # Plan de financement : besoins et ressources, et leur écart.
    besoins = [faits[i] for i in ("investissement_total", "bfr") if i in faits]
    ressources = [faits[i] for i in ("apport", "emprunt", "autres_ressources") if i in faits]
    if besoins:
        derives.append(_derive(
            "besoins_totaux", besoins, sum,
            libelle="Besoins de financement totaux",
            formule=" + ".join(b.id for b in besoins),
        ))
    if ressources:
        derives.append(_derive(
            "ressources_totales", ressources, sum,
            libelle="Ressources de financement totales",
            formule=" + ".join(r.id for r in ressources),
        ))
        for ressource in ressources:
            derives.append(_derive(
                f"part_{ressource.id}", (ressource, *ressources),
                lambda v: v[0] / sum(v[1:]) * 100.0 if sum(v[1:]) else None,
                libelle=f"Part de {ressource.libelle.split(' —')[0].lower()} dans les ressources",
                formule=f"{ressource.id} ÷ ressources_totales × 100", unite="%",
            ))
    if besoins and ressources:
        derives.append(_derive(
            "ecart_financement", (*ressources, *besoins),
            lambda v: sum(v[:len(ressources)]) - sum(v[len(ressources):]),
            libelle="Écart entre ressources et besoins de financement",
            formule="ressources_totales − besoins_totaux",
        ))

    # Emboîtement du marché : chaque niveau rapporté au précédent.
    for petit, grand in (("som", "sam"), ("sam", "tam")):
        if petit in faits and grand in faits:
            derives.append(_derive(
                f"part_{petit}_dans_{grand}", (faits[petit], faits[grand]), _part,
                libelle=f"Part du {petit.upper()} dans le {grand.upper()}",
                formule=f"{petit} ÷ {grand} × 100", unite="%",
            ))

    for derive in derives:
        if derive is not None and derive.id not in faits:
            faits[derive.id] = derive
    return faits

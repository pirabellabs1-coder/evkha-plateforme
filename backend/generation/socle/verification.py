"""Vérifier chaque chiffre-fondation AVANT de le verrouiller.

## Pourquoi ce module existe

Le socle est le point unique de vérité d'une étude : ses chiffres sont repris
dans les vingt-trois chapitres, dans les figures, dans les tableaux. C'est sa
force — aucune contradiction interne n'est possible — et c'est exactement ce qui
rend une erreur initiale si coûteuse.

**Retour de la cliente, 09/08/2026, sur l'étude e-commerce animalier :** « Si un
chiffre initial est erroné, daté, issu d'un mauvais périmètre ou mal interprété,
il est actuellement répété dans toute l'étude. » Elle a raison, et rien ne le
regardait : `produire_socle` rendait le socle, `etablir_socle` le scellait
aussitôt en `VALIDE`.

## Ce qui est vérifié, et pourquoi ces sept points

Ce sont les sept façons dont un chiffre juste devient faux :

    la valeur      — recopiée de travers
    l'année        — le chiffre de 2019 présenté comme celui de 2026
    la zone        — un chiffre européen donné pour la France
    le périmètre   — le marché total pour le segment étudié
    l'unité        — des milliers lus comme des millions
    la nature      — une estimation présentée comme une donnée officielle
    la source      — l'organisme cité ne publie pas ce chiffre-là

## La règle qui gouverne tout le module : on DÉCLASSE, on ne supprime pas

Un chiffre qu'on ne peut pas confirmer ne disparaît pas — il passe de `observee`
à `estimee`, et la raison entre dans son `libelle`. Trois raisons :

1. **Supprimer casserait l'étude.** Le socle porte des emboîtements
   (TAM ≥ SAM ≥ SOM) : retirer une valeur rend les autres incalculables.
2. **Déclasser est la vérité.** Un chiffre non confirmé n'est pas faux ; il
   n'est simplement plus une donnée observée. Le document dira « estimation »
   au lieu de « publié par », ce qui est exactement ce qu'il est.
3. **Le lecteur le verra.** `fiabilite` remonte jusqu'au chapitre : la
   distinction entre observé et estimé est déjà écrite dans le document.

## Ce que ce module ne prétend pas faire

Il ne va pas chercher la source sur le web. Il compare le socle au brief de
recherche DÉJÀ collecté au lancement (`collect_research_brief`) — donc à des
sources réelles, mais à celles-là seulement. Une donnée dont la source n'est pas
dans le brief ne peut pas être confirmée : elle est déclassée, et c'est le bon
comportement (règle 1 — un contrôle qui n'a rien à comparer est un échec, jamais
un succès).

Le coût est d'UN appel pour tout le socle, pas d'un appel par chiffre.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from .schema import Fiabilite, Socle

_log = logging.getLogger(__name__)

OUTIL_NOM = "rendre_verification"
OUTIL_DESCRIPTION = (
    "Enregistre le verdict de vérification de chaque chiffre-fondation, "
    "confronté aux sources réellement collectées."
)

#: Jetons de sortie de la passe. Un verdict fait ~40 jetons ; un socle en porte
#: rarement plus de quarante. On double, la troncature coûtant plus cher que la
#: place (voir `motif_de_troncature`, corrigé le 08/08/2026).
MAX_TOKENS = 4000


class Verdict(BaseModel):
    """Ce que la vérification conclut pour UN identifiant."""

    model_config = {"extra": "forbid"}

    identifiant: str = Field(min_length=1)
    #: `confirmee` — la source collectée porte bien cette valeur, cette année,
    #: cette zone et ce périmètre.
    #: `declassee` — impossible de la confirmer : elle devient une estimation.
    statut: str = Field(pattern=r"^(confirmee|declassee)$")
    #: Obligatoire quand on déclasse : la raison entre dans le `libelle` de la
    #: donnée, donc dans le document. « Non vérifiable » n'est pas une raison.
    motif: str = ""


class RapportDuModele(BaseModel):
    model_config = {"extra": "forbid"}

    verdicts: list[Verdict] = Field(default_factory=list)


@dataclass
class RapportVerification:
    """Ce que la passe a fait, dit en clair pour le journal et l'incident."""

    confirmees: list[str] = field(default_factory=list)
    declassees: list[tuple[str, str]] = field(default_factory=list)
    #: Données déclassées SANS appel au modèle, sur un contrôle déterministe.
    declassees_sans_appel: list[tuple[str, str]] = field(default_factory=list)
    #: La passe a-t-elle pu interroger le modèle ?
    passe_executee: bool = False
    motif_non_executee: str = ""

    @property
    def total_declassees(self) -> int:
        return len(self.declassees) + len(self.declassees_sans_appel)

    def as_details(self) -> dict[str, Any]:
        return {
            "type": "verification_du_socle",
            "confirmees": len(self.confirmees),
            "declassees": [
                {"identifiant": i, "motif": m}
                for i, m in [*self.declassees_sans_appel, *self.declassees]
            ],
            "passe_executee": self.passe_executee,
            "motif_non_executee": self.motif_non_executee,
        }


def _declasser(donnee: Any, motif: str) -> None:
    """Passe une donnée en `estimee`. Le motif reste INTERNE.

    ## Pourquoi le motif ne va plus dans le libellé

    Première version : la raison du déclassement était écrite dans
    `donnee.libelle`, « pour que le lecteur sache ». Or `libelle` part dans le
    prompt de CHAQUE chapitre (`_bloc_socle`) : le modèle lisait donc nos
    réserves internes et les recopiait au client.

    Résultat mesuré sur la V2, et la cliente l'a nommé le 09/08/2026 :
    « l'étude passe son temps à dire données à définir, à vérifier — je n'aime
    pas cela, j'aime apporter de vraies réponses. » Des phrases comme « le socle
    ne documente pas », « cette donnée reste à vérifier » venaient de là.

    Le déclassement garde tout son sens sans cette fuite : `fiabilite` passe à
    `estimee`, et c'est exactement l'information utile — une estimation se
    présente comme une estimation, avec un ordre de grandeur assumé, pas comme
    un aveu d'ignorance.

    Le motif, lui, va au JOURNAL : l'incident du socle le porte, l'opérateur le
    lit, le client ne le voit pas. C'est sa place — ce qui aide à produire n'est
    pas ce qu'on livre.
    """
    donnee.fiabilite = Fiabilite.ESTIMEE


# ── Ce que ce module ne contrôle PAS, et pourquoi ────────────────────────────
#
# Une première version déclassait, sans appel au modèle, toute donnée `observee`
# dépourvue de source. Le contrôle n'aurait JAMAIS pu se déclencher :
# `DonneeSocle` porte un validateur qui refuse cette combinaison à la
# construction — « une donnée observée sans source est une estimation qui
# s'ignore ». Un socle en mémoire ne peut donc pas contenir ce cas.
#
# Écrit avant d'avoir lu le contrat (règle 8), il aurait vécu ici comme un
# garde-fou décoratif : lu comme une protection, incapable de protéger quoi que
# ce soit. C'est précisément le motif que ce dépôt traque partout ailleurs, et
# le laisser aurait été s'en donner un de plus.


def _bloc_a_verifier(socle: Socle) -> str:
    lignes = [
        f"- `{d.id}` = {d.valeur} {d.unite} ({d.annee}, {d.perimetre}) — "
        f"source déclarée : {d.source or 'AUCUNE'}"
        + (f" — {d.libelle}" if d.libelle else "")
        for d in socle.donnees
        if d.fiabilite == Fiabilite.OBSERVEE
    ]
    return "\n".join(lignes)


_SYSTEME = (
    "Tu vérifies des chiffres avant qu'ils ne soient verrouillés dans une étude "
    "de marché. Chacun sera ensuite repris dans une vingtaine de chapitres : "
    "une erreur ici se propage partout et ne se rattrape plus.\n"
    "\n"
    "Ton rôle n'est PAS de réécrire les chiffres. Il est de dire, pour chacun, "
    "si les sources fournies le confirment — ou non.\n"
    "\n"
    "CONFIRME uniquement si les sources fournies portent CE chiffre, pour CETTE "
    "année, sur CETTE zone et CE périmètre, dans CETTE unité. Les cinq doivent "
    "être vrais ensemble.\n"
    "\n"
    "DÉCLASSE dans tous les autres cas, et notamment :\n"
    "- les sources ne parlent pas de ce chiffre ;\n"
    "- elles donnent une autre valeur, une autre année ou une autre zone ;\n"
    "- le chiffre vient d'un périmètre PLUS LARGE que celui demandé — un "
    "panier moyen tous secteurs confondus n'est pas celui du secteur étudié ;\n"
    "- l'organisme cité existe mais ne publie pas cette donnée ;\n"
    "- tu ne peux pas trancher.\n"
    "\n"
    "Déclasser n'est pas une sanction : le chiffre reste dans l'étude, il y "
    "devient une estimation au lieu d'une donnée publiée. C'est la vérité, et "
    "c'est utile au lecteur. Confirmer par défaut, en revanche, fabrique une "
    "fausse certitude — c'est la seule faute possible ici.\n"
    "\n"
    "Le `motif` d'un déclassement est lu par un humain ET imprimé dans le "
    "document : écris ce qui manque, pas « non vérifiable ».\n"
    "\n"
    f"Tu réponds exclusivement par un appel de l'outil `{OUTIL_NOM}`."
)


def verifier_le_socle(
    socle: Socle,
    *,
    client: Any,
    brief_recherche: str = "",
) -> RapportVerification:
    """Confronte les données `observee` aux sources collectées. Modifie le socle.

    Retourne le rapport ; le socle est corrigé EN PLACE — les données non
    confirmées y passent en `estimee`, motif inscrit dans leur libellé.

    ## Pourquoi la passe ne fait pas échouer la génération quand elle échoue

    Une panne de la vérification ne rend pas les chiffres faux : elle rend leur
    contrôle impossible. Faire mourir l'étude sur ce point coûterait un dossier
    entier pour un incident transitoire. On journalise, on le porte au rapport,
    et le socle part avec ses données telles que le producteur les a rendues.

    C'est le seul endroit du module où l'on accepte de ne pas savoir — et il est
    NOMMÉ dans le rapport (`passe_executee`), de sorte qu'un socle non vérifié
    ne puisse pas se faire passer pour un socle vérifié (règle 1).
    """
    rapport = RapportVerification()
    a_verifier = _bloc_a_verifier(socle)
    if not a_verifier:
        rapport.passe_executee = True
        return rapport

    if not brief_recherche.strip():
        # Aucune source collectée : il n'y a RIEN à quoi comparer. On ne
        # confirme donc rien — et on le dit. Laisser passer « puisqu'on ne
        # peut pas juger » est exactement le défaut de la règle 1.
        motif = "aucune source collectée pour cette étude"
        for donnee in socle.donnees:
            if donnee.fiabilite == Fiabilite.OBSERVEE:
                _declasser(donnee, motif)
                rapport.declassees.append((donnee.id, motif))
        rapport.passe_executee = True
        return rapport

    prompt = (
        f"SECTEUR : {socle.secteur}\n"
        f"ZONE : {socle.zone.pays}"
        + (f" / {socle.zone.region}" if socle.zone.region else "")
        + (f" / {socle.zone.ville}" if socle.zone.ville else "")
        + "\n\n"
        "SOURCES COLLECTÉES — la seule matière dont tu disposes :\n"
        f"{brief_recherche}\n\n"
        "CHIFFRES À VÉRIFIER :\n"
        f"{a_verifier}\n\n"
        "Rends un verdict pour CHACUN, sans en omettre."
    )

    try:
        resultat = client.complete_structured(
            system=_SYSTEME,
            prompt=prompt,
            outil_nom=OUTIL_NOM,
            outil_description=OUTIL_DESCRIPTION,
            schema=RapportDuModele.model_json_schema(),
            max_tokens=MAX_TOKENS,
        )
        rendu = RapportDuModele.model_validate(dict(resultat.payload))
    except Exception as erreur:  # noqa: BLE001 — une panne ici ne tue pas l'étude
        _log.exception("Vérification du socle impossible")
        rapport.motif_non_executee = f"{type(erreur).__name__} : {erreur}"
        return rapport

    rapport.passe_executee = True
    verdicts = {v.identifiant: v for v in rendu.verdicts}

    for donnee in socle.donnees:
        if donnee.fiabilite != Fiabilite.OBSERVEE:
            continue
        verdict = verdicts.get(donnee.id)
        if verdict is None:
            # Un chiffre oublié par la vérification n'est pas un chiffre
            # vérifié. On le déclasse, comme tout ce qu'on n'a pas pu confirmer.
            motif = "non examiné par la passe de vérification"
            _declasser(donnee, motif)
            rapport.declassees.append((donnee.id, motif))
        elif verdict.statut == "declassee":
            motif = verdict.motif.strip() or "non confirmé par les sources collectées"
            _declasser(donnee, motif)
            rapport.declassees.append((donnee.id, motif))
        else:
            rapport.confirmees.append(donnee.id)

    return rapport

"""Chaque question du client a-t-elle reçu une réponse dans l'étude ?

## Le retour qui a créé ce module

Cliente, 09/08/2026 : « éviter d'avoir une étude très complète en apparence mais
qui laisse certaines questions initiales insuffisamment traitées ».

C'est un angle mort exact. Le gate vérifie la troncature, la contamination, la
cohérence chiffrée ; la conformité vérifie la forme ; la vérification du socle
vérifie les chiffres. **Personne ne relisait le brief du client pour se demander
si on lui avait répondu.** C'est la règle 9 dans sa forme la plus littérale : ce
que le contrôle ne regarde pas est exactement là où le manque vit.

## Trois statuts, et pourquoi PARTIEL existe

    OUI     — la question est traitée, avec de quoi décider.
    PARTIEL — le sujet est abordé, la réponse ne suffit pas à décider.
    NON     — la question n'est pas traitée.

Sans PARTIEL, tout deviendrait OUI : une étude de vingt-trois chapitres
« aborde » à peu près tout. C'est précisément l'illusion que la cliente décrit —
complète en apparence. Le statut qui fait le travail ici est celui du milieu.

## Ce que ce module fait, et ce qu'il ne fait PAS encore

Il MESURE et il NOMME. Chaque question insuffisamment traitée sort avec ce qui
manque, dans un incident lisible.

Il ne relance PAS encore un approfondissement automatique. Ce n'est pas un oubli
mais une décision : un approfondissement réécrit des chapitres, donc dépense, et
ce projet a appris quatre fois de suite qu'on règle mal ce qu'on n'a pas d'abord
mesuré. La première mesure sur un dossier réel dira combien de questions sont
concernées et lesquelles — et c'est elle qui doit dicter la reprise, pas une
intuition.

## La première mesure réelle, et ce qu'elle a montré

Stratégie du dossier `f7f2fad9` (08/09/2026). L'incident annonçait « 87 demandes
insuffisamment traitées » ; **aucune n'avait été examinée** — `traitees: 0`, et
chacune des 87 portait « question non examinée par le contrôle ». La cliente a
dû refaire à la main la vérification que ce module promettait, et y a trouvé ce
qu'il aurait dû trouver : la segmentation de la base d'abonnés, demandée et non
traitée. Trois défauts cumulés :

1. **Les mauvais champs.** La liste fermée lisait `ELEMENTS_A_RETENIR` —
   l'INVENTAIRE des documents joints — et en faisait des questions (« Un brief
   stratégique actuel consacré au projet »). Elle ignorait `OBJECTIF_STRATEGIQUE`
   et `ENJEUX`, où le client écrit ce qu'il veut, et `SAISONNALITE`, où il avait
   glissé la répartition des abonnés par formule. Une liste fermée de champs
   manque toujours celui où la demande se trouve (règle 4) : tout champ de texte
   libre est désormais candidat, et c'est le modèle qui sépare la DEMANDE du
   CONTEXTE.
2. **Le rapprochement par le texte.** La réponse du modèle était retrouvée par
   l'égalité exacte de la question. Une virgule reformulée, et la réponse était
   perdue. Le rapprochement se fait par NUMÉRO.
3. **Un budget de 3 000 jetons pour 87 verdicts**, soit trente-quatre jetons par
   ligne. Il suit maintenant le nombre de candidats.

Et un quatrième, dans le compte rendu : ce que le contrôle n'avait pas examiné
était déclaré « insuffisamment traité ». C'est un trou du CONTRÔLE, pas du
document ; il est désormais nommé comme tel, et au-delà d'un seuil la passe se
déclare non concluante plutôt que de publier un verdict qu'elle n'a pas rendu
(règle 1).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

_log = logging.getLogger(__name__)

OUTIL_NOM = "rendre_couverture"
OUTIL_DESCRIPTION = (
    "Enregistre, pour chaque passage du brief, s'il s'agit d'une demande du "
    "client et, si oui, si l'étude y répond."
)

#: Budget de réponse : un socle, plus de quoi rendre un verdict par candidat.
#: Il était fixé à 3 000 jetons quel que soit le brief — trente-quatre jetons
#: par ligne pour les 87 candidats du dossier `f7f2fad9`, réponse tronquée.
MAX_TOKENS_SOCLE = 1_500
#: Un numéro de contexte coûte deux ou trois jetons ; une demande, avec son
#: manque, une quarantaine. Seize par passage couvre un brief dont un sur trois
#: serait une demande. Estimation, pas mesure : c'est pourquoi une réponse
#: coupée par le budget est NOMMÉE comme telle (`stop_reason`), au lieu de
#: passer pour des oublis du modèle.
MAX_TOKENS_PAR_CANDIDAT = 16
MAX_TOKENS_PLAFOND = 16_000

#: Au-delà de cette part de candidats sans verdict, la passe ne conclut pas.
#: En dessous, les manquants sont nommés à part : un oubli ponctuel du modèle
#: ne doit pas faire perdre les verdicts qu'il a bien rendus.
PART_NON_EXAMINEE_MAX = 0.2

#: Ce qu'une valeur de brief est, quand elle n'est pas du texte à lire : une
#: adresse, un chemin de fichier, une couleur. Reconnus à leur FORME et non à
#: leur nom de champ — une liste de champs à écarter serait incomplète au
#: premier champ ajouté au formulaire (règle 4).
_PAS_DU_TEXTE = re.compile(r"^\s*(?:https?://|/|#[0-9a-fA-F]{3,8}\s*$)")

#: En dessous, ce n'est pas une question mais un mot-clé. Une « question » de
#: dix signes ne peut pas être jugée traitée ou non.
LONGUEUR_MINIMALE = 15


# Le numéro, et non le texte : rapprocher par l'égalité exacte de la question
# perdait toute réponse dont le modèle avait reformulé une virgule — c'est ce
# qui a produit « 87 non examinées » sur la stratégie du 08/09/2026. Ce récit
# est en commentaire et non en docstring : une docstring de modèle Pydantic part
# dans le schéma de l'outil, donc chez le modèle, pour tous les clients.
class Reponse(BaseModel):
    """Le verdict sur une demande, désignée par son numéro."""

    model_config = {"extra": "forbid"}

    n: int = Field(ge=1)
    statut: Literal["oui", "partiel", "non"]
    #: Obligatoire hors « oui » : ce qui manque, en une phrase utilisable.
    manque: str = ""


# Le contexte est une simple liste d'entiers, et non un verdict par passage :
# sur le brief du 08/09/2026, tout champ de texte libre donnait 433 passages, et
# un objet complet pour chacun aurait fait déborder la réponse. Rien n'est
# présumé pour autant : un numéro absent des deux listes reste un oubli du
# contrôle, compté et nommé.
#
# `demandes` est déclaré AVANT `contexte`. Le modèle suit l'ordre du schéma ;
# si la réponse est coupée par le budget, c'est la fin qui saute — mieux vaut
# perdre des numéros de contexte que des verdicts.
class RapportDuModele(BaseModel):
    """Chaque numéro du brief figure dans l'une des deux listes."""

    model_config = {"extra": "forbid"}

    demandes: list[Reponse] = Field(default_factory=list)
    contexte: list[int] = Field(default_factory=list)


@dataclass
class RapportCouverture:
    traitees: list[str] = field(default_factory=list)
    insuffisantes: list[tuple[str, str, str]] = field(default_factory=list)
    #: Candidats que le modèle n'a pas rendus. Un trou du CONTRÔLE, pas du
    #: document : les mêler aux « insuffisantes » a fait annoncer 87 demandes
    #: mal traitées sur le dossier `f7f2fad9` alors qu'aucune n'avait été lue.
    non_examinees: list[str] = field(default_factory=list)
    #: Passages du brief que le modèle a reconnus comme du contexte. Comptés
    #: plutôt qu'affichés : ils ne demandent rien, mais leur nombre dit ce que
    #: le contrôle a écarté.
    ecartees_comme_contexte: int = 0
    passe_executee: bool = False
    motif_non_executee: str = ""

    @property
    def toutes_traitees(self) -> bool:
        return (
            self.passe_executee and not self.insuffisantes and not self.non_examinees
        )

    def as_details(self) -> dict[str, Any]:
        return {
            "type": "couverture_des_demandes",
            "traitees": len(self.traitees),
            "insuffisantes": [
                {"question": q, "statut": s, "manque": m}
                for q, s, m in self.insuffisantes
            ],
            "non_examinees": list(self.non_examinees),
            "ecartees_comme_contexte": self.ecartees_comme_contexte,
            "passe_executee": self.passe_executee,
            "motif_non_executee": self.motif_non_executee,
        }


@dataclass(frozen=True)
class Candidat:
    """Un passage du brief à confronter au document, et le champ d'où il vient.

    Le champ est donné au modèle : « OBJECTIF_STRATEGIQUE — obtenir de nouveaux
    abonnés chaque mois » se reconnaît comme une demande bien plus sûrement
    que la même phrase sans son origine.
    """

    numero: int
    champ: str
    texte: str


def candidats_du_brief(variables: Any) -> list[Candidat]:
    """Tout passage de texte libre du brief, découpé en unités jugeables.

    Le brief écrit en vrac — une phrase, une liste à puces, trois lignes
    séparées par des points. On découpe sur la ponctuation forte, les points-
    virgules et les retours à la ligne, puis on écarte ce qui est trop court
    pour être jugé : sans cela, « RSE » sortirait comme une demande et serait
    déclaré « non couvert » à jamais (règle 2).

    Aucun champ n'est choisi par son nom. C'est ce qui a fait manquer au dossier `f7f2fad9`
    la répartition des abonnés par formule, glissée dans `SAISONNALITE` — un
    champ qu'on aurait classé « descriptif ». Le tri demande/contexte est confié
    au modèle, qui lit le sens ; ce qui n'est pas du texte (adresse, couleur)
    est écarté à sa forme.
    """
    if not isinstance(variables, dict):
        return []
    # Découper d'abord, filtrer ensuite. Le filtre était appliqué au champ
    # ENTIER : un champ qui commençait par une adresse — deux sites concurrents,
    # puis « Je veux savoir comment me différencier » — était écarté en bloc, et
    # la demande avec. Une liste passe par le même découpage qu'une chaîne.
    morceaux: list[tuple[str, str]] = []
    for champ, brut in variables.items():
        if isinstance(brut, str):
            textes = [brut]
        elif isinstance(brut, list):
            textes = [str(item) for item in brut]
        else:
            continue
        for texte in textes:
            for bout in re.split(r"[\n;]+|(?<=[.?!])\s+", texte):
                if not _PAS_DU_TEXTE.match(bout):
                    morceaux.append((str(champ), bout))

    vues: set[str] = set()
    candidats: list[Candidat] = []
    for champ, morceau in morceaux:
        texte = morceau.strip(" -•\t")
        # La clé de dédoublonnage ignore la ponctuation finale et la casse : le
        # brief écrit souvent la même demande deux fois, dans deux champs, à un
        # point près. Deux fois la même, c'est un verdict de plus à payer et un
        # incident qui compte double.
        cle = texte.casefold().rstrip(" .?!:;")
        if len(texte) >= LONGUEUR_MINIMALE and cle not in vues:
            vues.add(cle)
            candidats.append(Candidat(len(candidats) + 1, champ, texte))
    return candidats


def questions_du_brief(variables: Any) -> list[str]:
    """Le texte des candidats, dans l'ordre. Conservé pour les appelants
    qui n'ont besoin que de la liste des passages."""
    return [c.texte for c in candidats_du_brief(variables)]


_SYSTEME = (
    "Tu relis une étude terminée — étude de marché, business plan, étude "
    "concurrentielle ou stratégie — et tu vérifies qu'elle répond à ce que le "
    "client a demandé.\n"
    "\n"
    "On te donne le brief du client découpé en passages NUMÉROTÉS, chacun avec "
    "le champ du formulaire d'où il vient. Pour CHAQUE numéro, sans en omettre "
    "aucun :\n"
    "\n"
    "1. Sa nature :\n"
    "- `demande` : le client exprime ce qu'il veut obtenir, savoir, décider ou "
    "voir traité — une question, un objectif, un besoin, une donnée qu'il veut "
    "voir analysée ou actualisée ;\n"
    "- `contexte` : le client décrit sa situation, son secteur, son histoire, "
    "ses documents — rien qui appelle une réponse.\n"
    "\n"
    "2. Pour une `demande` seulement, un statut :\n"
    "- `oui` : l'étude y répond, avec de quoi DÉCIDER — un chiffre, un "
    "critère, une recommandation datée ;\n"
    "- `partiel` : le sujet est abordé, mais la réponse ne suffit pas à "
    "décider ;\n"
    "- `non` : la question n'est pas traitée.\n"
    "\n"
    "N'accorde pas `oui` parce que le sujet est mentionné. Une étude de vingt "
    "chapitres effleure à peu près tout : c'est exactement l'illusion qu'on "
    "cherche à percer. La question est « le lecteur repart-il avec sa "
    "réponse ? », pas « le mot apparaît-il ? ».\n"
    "\n"
    "Hors `oui`, `manque` dit ce qu'il faudrait ajouter, en une phrase "
    "utilisable par le rédacteur. « Insuffisant » n'aide personne.\n"
    "\n"
    "Réponds en deux listes : `contexte`, les numéros qui ne demandent rien ; "
    "`demandes`, un verdict {n, statut, manque} par demande. CHAQUE numéro doit "
    "figurer dans l'une des deux. Désigne les passages par leur numéro ; ne "
    "recopie pas leur texte.\n"
    "\n"
    f"Tu réponds exclusivement par un appel de l'outil `{OUTIL_NOM}`."
)


def controler_la_couverture(
    *,
    client: Any,
    variables: Any,
    document: str,
) -> RapportCouverture:
    """Confronte les demandes du client au document produit.

    `document` est le texte assemblé de l'étude — ce que le lecteur lira, pas le
    payload. Juger sur autre chose que ce qui part reviendrait à contrôler un
    document que personne ne recevra (règle 3).
    """
    rapport = RapportCouverture()
    candidats = candidats_du_brief(variables)
    if not candidats:
        # Aucune demande explicite : il n'y a rien à couvrir, et le dire est
        # différent de « tout est couvert ».
        rapport.passe_executee = True
        return rapport

    if not document.strip():
        rapport.motif_non_executee = "document vide : rien à relire"
        return rapport

    liste = "\n".join(f"{c.numero}. [{c.champ}] {c.texte}" for c in candidats)
    prompt = (
        f"BRIEF DU CLIENT, PASSAGE PAR PASSAGE :\n{liste}\n\n"
        f"ÉTUDE PRODUITE :\n{document}\n\n"
        f"Rends un verdict pour CHACUN des {len(candidats)} numéros, sans en "
        "omettre."
    )
    budget = min(
        MAX_TOKENS_PLAFOND,
        MAX_TOKENS_SOCLE + MAX_TOKENS_PAR_CANDIDAT * len(candidats),
    )

    try:
        resultat = client.complete_structured(
            system=_SYSTEME,
            prompt=prompt,
            outil_nom=OUTIL_NOM,
            outil_description=OUTIL_DESCRIPTION,
            schema=RapportDuModele.model_json_schema(),
            max_tokens=budget,
        )
        rendu = RapportDuModele.model_validate(dict(resultat.payload))
    except Exception as erreur:  # noqa: BLE001 — une panne ici ne tue pas l'étude
        _log.exception("Contrôle de couverture impossible")
        rapport.motif_non_executee = f"{type(erreur).__name__} : {erreur}"
        return rapport

    par_numero = {r.n: r for r in rendu.demandes}
    contexte = set(rendu.contexte)

    for candidat in candidats:
        reponse = par_numero.get(candidat.numero)
        if reponse is not None:
            if reponse.statut == "oui":
                rapport.traitees.append(candidat.texte)
            else:
                manque = reponse.manque.strip() or "la réponse ne permet pas de décider"
                rapport.insuffisantes.append((candidat.texte, reponse.statut, manque))
        elif candidat.numero in contexte:
            rapport.ecartees_comme_contexte += 1
        else:
            # Un candidat NON EXAMINÉ n'est ni traité, ni insuffisamment traité :
            # le contrôle ne sait pas. Le dire autrement serait publier un
            # verdict que personne n'a rendu.
            rapport.non_examinees.append(candidat.texte)

    coupee = str(getattr(resultat, "stop_reason", "") or "") == "max_tokens"
    part = len(rapport.non_examinees) / len(candidats)
    if coupee and rapport.non_examinees:
        # Le vrai motif, quand c'est lui. Sans ce test, une réponse coupée par
        # le budget se lisait « N passages non examinés » — comme si le modèle
        # les avait oubliés, et on aurait cherché la cause au mauvais endroit.
        rapport.motif_non_executee = (
            f"réponse coupée par le budget ({budget} jetons) : "
            f"{len(rapport.non_examinees)} passage(s) sur {len(candidats)} "
            "sans verdict"
        )
        return rapport
    if part > PART_NON_EXAMINEE_MAX:
        # Trop de silences pour conclure : on garde ce qui a été jugé, mais la
        # passe se déclare non concluante. Un incident qui annoncerait « tout
        # va bien » ou « tout manque » sur une lecture partielle serait faux
        # dans les deux cas (règle 1).
        rapport.motif_non_executee = (
            f"réponse incomplète du contrôle : {len(rapport.non_examinees)} "
            f"passage(s) sur {len(candidats)} non examiné(s)"
        )
        return rapport

    rapport.passe_executee = True
    return rapport

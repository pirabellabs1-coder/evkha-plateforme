"""Le contrôle d'UN chapitre contre la mémoire de l'étude — avant qu'il soit validé.

## Pourquoi ici, et pas à la fin

29/09/2026, business plan ÉCLORE : la relecture finale arrivait après les
vingt-deux chapitres, relisait tout d'un coup sans référence complète, et une
erreur du chapitre 1 avait déjà été recopiée par les vingt suivants. Le
contrôle se fait désormais chapitre par chapitre, contre la mémoire : un
chapitre n'est validé qu'une fois ses chiffres, ses décisions et ses repères
conformes — ou ajustés.

## Ce que ce module fait

1. `appliquer_les_reperes` remplace les `{{identifiant}}` d'un chapitre par
   leurs valeurs, dans toutes ses chaînes, et dit lesquels sont inconnus ;
2. `controler_le_chapitre` rend les MOTIFS qui le font reprendre : repère
   inconnu, TVA « par choix » quand la règle l'impose, compte de concurrents
   différent de la base, « taux » exprimé en euros, séries confondues, dates
   contredites, renvois hors plan, comptes de résultat faux — et les SIGNAUX,
   qui ne font pas reprendre à eux seuls : chiffre écrit en clair qui n'est ni
   un fait, ni une réponse du client, ni un seuil légal (épreuve réelle
   `bf98827c`, 29/09/2026) ;
3. `replis_de_derniere_tentative` : à la dernière tentative, ce qui ne peut
   pas partir est retiré (la phrase qui porte un repère inconnu) — le chapitre
   est TOUJOURS validé, l'étude ne s'arrête jamais.

Tout est déterministe, sans appel au modèle : ces contrôles ne coûtent rien.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .etude import MemoireEtude
from .faits import Fait
from .reperes import REPERE, remplacer_les_reperes

_ESP = "[ \u00a0\u202f]"
#: Un nombre écrit en français, avec son unité éventuelle.
_NOMBRE = re.compile(
    rf"(?<![\w.,{{])([+\-−]?\d{{1,3}}(?:{_ESP}\d{{3}})+(?:,\d+)?|[+\-−]?\d+(?:,\d+)?)"
    rf"(?:{_ESP}?(%|k€|M€|Md€|€))?"
)
_MULT = {"k€": 1e3, "M€": 1e6, "Md€": 1e9}
_PHRASE = re.compile(r"[^.!?\n]+[.!?]?")


@dataclass
class Controle:
    """Le verdict sur un chapitre : les motifs de reprise, et ce qui a été vu."""

    motifs: list[str] = field(default_factory=list)
    #: Ce qui ne fait PAS reprendre un chapitre à soi seul : un chiffre écrit
    #: en clair. Il accompagne une reprise déjà décidée pour un motif grave.
    #:
    #: Épreuve réelle du 29/09/2026 (reprise ÉCLORE `bf98827c`, mémoire
    #: active) : le modèle a cité 10 repères en 18 chapitres et écrit le reste
    #: en clair ; 45 motifs « chiffre écrit en clair » ont fait réécrire presque
    #: chaque chapitre deux ou trois fois, et le dossier s'est arrêté sur son
    #: plafond de 8 € au chapitre 16. Les motifs graves du même dossier —
    #: séries confondues (7), TVA « par choix » (2), date contredite (1) —
    #: justifient une reprise ; un chiffre en clair, non. C'est l'arbitrage déjà
    #: tranché pour les figures (`_motifs_de_figure`, 12/09/2026).
    signaux: list[str] = field(default_factory=list)
    reperes_utilises: list[str] = field(default_factory=list)
    reperes_inconnus: list[str] = field(default_factory=list)
    #: Ce que le contrôle a examiné — jamais « rien à signaler » sans dire quoi
    #: (règle 1 : un contrôle qui n'a rien comparé n'est pas un succès).
    verifie: list[str] = field(default_factory=list)


# ── Repères ──────────────────────────────────────────────────────────────────


def _parcourir(valeur: Any, transformer: Any) -> Any:
    if isinstance(valeur, str):
        return transformer(valeur)
    if isinstance(valeur, list):
        return [_parcourir(v, transformer) for v in valeur]
    if isinstance(valeur, dict):
        return {k: _parcourir(v, transformer) for k, v in valeur.items()}
    return valeur


def _chaines(valeur: Any) -> Iterable[str]:
    if isinstance(valeur, str):
        yield valeur
    elif isinstance(valeur, list):
        for v in valeur:
            yield from _chaines(v)
    elif isinstance(valeur, dict):
        for v in valeur.values():
            yield from _chaines(v)


def appliquer_les_reperes(
    payload: Any, faits: Mapping[str, Fait]
) -> tuple[Any, list[str], list[str]]:
    """Le chapitre avec ses repères remplacés ; les repères utilisés ; les inconnus."""
    utilises: list[str] = []
    inconnus: list[str] = []

    def _remplacer(texte: str) -> str:
        rendu = remplacer_les_reperes(texte, faits)
        utilises.extend(rendu.utilises)
        inconnus.extend(rendu.inconnus)
        return rendu.texte

    return _parcourir(payload, _remplacer), utilises, inconnus


# ── Chiffres écrits en clair ─────────────────────────────────────────────────


def _valeur(brut: str, unite: str | None) -> float:
    nombre = float(re.sub(_ESP, "", brut).replace(",", ".").replace("−", "-"))
    return nombre * _MULT.get(unite or "", 1.0)


def nombres_du_texte(texte: str) -> list[tuple[str, float, str | None]]:
    """Les nombres d'un texte : (écriture, valeur en unité de base, unité)."""
    trouves = []
    for m in _NOMBRE.finditer(texte or ""):
        try:
            trouves.append((m.group(0).strip(), _valeur(m.group(1), m.group(2)), m.group(2)))
        except ValueError:
            continue
    return trouves


def _en_liste_blanche(ecriture: str, valeur: float, unite: str | None, contexte: str) -> bool:
    """Années, numéros, petits compteurs de langue courante : pas des chiffres du projet."""
    if unite is None and valeur.is_integer():
        if 1990 <= valeur <= 2040 or 0 <= valeur <= 12:
            return True
    return bool(re.search(r"(?i)(chapitre|section|annexe|étape|phase|page)\s*$", contexte))


def _proche(valeur: float, references: Iterable[float]) -> bool:
    for ref in references:
        if ref == valeur or (ref and abs(valeur - ref) <= max(abs(ref) * 0.005, 0.5)):
            return True
    return False


def _seuils_des_regles() -> list[float]:
    """Les seuils légaux datés (`regles.SEUILS_LEGAUX`) : des chiffres sourcés.

    Reprise ÉCLORE `bf98827c` (29/09/2026) : « 37 500 € », la franchise de TVA
    des services (art. 293 B CGI), était signalé comme chiffre inventé au
    chapitre des risques.
    """
    from .regles import SEUILS_LEGAUX  # noqa: PLC0415

    valeurs: list[float] = []
    for table in SEUILS_LEGAUX:
        for seuil in table.values():
            valeurs.append(seuil.valeur)
            if seuil.majore is not None:
                valeurs.append(seuil.majore)
    return valeurs


def _valeurs_des_faits(faits: Mapping[str, Fait]) -> list[float]:
    from generation.socle.schema import valeur_en_unites_de_base  # noqa: PLC0415

    valeurs: list[float] = []
    for fait in faits.values():
        base = valeur_en_unites_de_base(fait.valeur, fait.unite)
        valeurs.append(base[0] if base else fait.valeur)
    return valeurs


# ── Le contrôle ──────────────────────────────────────────────────────────────

_TVA_CHOIX = re.compile(
    r"(?i)(TVA[^.]{0,90}\b(par choix|choisie?|optionnel\w*|en option|volontaire\w*|opt(e|er|é))\b"
    r"|\b(par choix|opte|opter|optant)\b[^.]{0,60}\bTVA\b)"
)
_COMPTE_CONCURRENTS = re.compile(r"\b(\d{1,3})\s+(concurrents?|acteurs?)\b", re.IGNORECASE)
#: « l'étude » n'attribue rien : ce peut être la nôtre. Seul un possessif, un
#: « recensait » ou un « selon » dit que le compte vient du client.
_ATTRIBUE_AU_CLIENT = re.compile(
    r"(?i)\b(votre|son|sa|leur|ses|leurs)\s+(propre\s+)?"
    r"(étude|analyse|recensement|document|travail)|\brecens\w*|\bselon (le|la|les|son|sa)\b"
)
_TAUX_EN_EUROS = re.compile(r"(?i)\btaux\b[^.%]{0,50}?\d[\d \u00a0\u202f,]*\s?€")


def controler_le_chapitre(
    payload: Any,
    memoire: MemoireEtude,
    nombres_du_client: Iterable[float] = (),
    *,
    chapitres_du_plan: Iterable[int] = (),
) -> Controle:
    """Les motifs qui empêchent de valider ce chapitre en l'état.

    `payload` est le chapitre TEL QUE LE MODÈLE L'A ÉCRIT (repères non
    remplacés) : un nombre écrit en clair s'y distingue d'un repère.
    """
    controle = Controle()
    brut = "\n".join(_chaines(payload))
    references = [*_valeurs_des_faits(memoire.faits), *_seuils_des_regles()]
    du_client = list(nombres_du_client)

    _, controle.reperes_utilises, controle.reperes_inconnus = appliquer_les_reperes(
        payload, memoire.faits
    )
    controle.verifie.append(f"{len(controle.reperes_utilises)} repère(s) cités")
    for inconnu in sorted(set(controle.reperes_inconnus)):
        controle.motifs.append(
            f"Repère inconnu {{{{{inconnu}}}}} : il n'existe pas dans la mémoire de "
            "l'étude. Utilise un identifiant de la liste, ou retire la phrase."
        )

    libres: list[str] = []
    sans_reperes = REPERE.sub(" ", brut)
    nombres = nombres_du_texte(sans_reperes)
    controle.verifie.append(f"{len(nombres)} nombre(s) écrits en clair examinés")
    for ecriture, valeur, unite in nombres:
        debut = sans_reperes.find(ecriture)
        contexte = sans_reperes[max(0, debut - 14):debut]
        if _en_liste_blanche(ecriture, valeur, unite, contexte):
            continue
        if _proche(valeur, references) or _proche(valeur, du_client):
            continue
        libres.append(ecriture)
    for ecriture in sorted(set(libres)):
        controle.signaux.append(
            f"Chiffre écrit en clair « {ecriture} » : ni un fait de la mémoire ni une "
            "réponse du client — c'est un calcul ou une invention. Cite le repère du fait "
            "voulu ({{…}}), ou retire le chiffre."
        )

    obligatoire = [
        d for d in memoire.decisions if d.sujet == "regime_tva" and "obligatoire" in d.valeur
    ]
    controle.verifie.append("régime de TVA confronté aux règles")
    if obligatoire and _TVA_CHOIX.search(brut):
        annees = ", ".join(str(d.annee) for d in obligatoire)
        controle.motifs.append(
            f"La TVA est présentée comme un choix alors qu'elle est OBLIGATOIRE ({annees}) : "
            "le chiffre d'affaires dépasse le seuil de franchise. Écris qu'elle s'applique, "
            "jamais qu'elle est choisie."
        )

    base = next((d for d in memoire.decisions if d.sujet == "concurrents"), None)
    controle.verifie.append("comptes de concurrents confrontés à la base")
    if base is not None:
        admis = {int(n) for n in re.findall(r"\d+", base.valeur)}
        for phrase in _PHRASE.findall(brut):
            for m in _COMPTE_CONCURRENTS.finditer(phrase):
                if int(m.group(1)) not in admis and not _ATTRIBUE_AU_CLIENT.search(phrase):
                    controle.motifs.append(
                        f"« {m.group(0)} » contredit la base ({base.valeur}). Un autre "
                        "compte trouvé dans un document du client s'attribue au client."
                    )

    controle.verifie.append("unités des taux")
    for m in _TAUX_EN_EUROS.finditer(brut):
        controle.motifs.append(
            f"« {m.group(0).strip()} » : un taux s'exprime en %, jamais en euros. "
            "Un montant par personne est un montant, pas un taux."
        )

    _controler_les_series(brut, memoire, controle)
    _controler_les_dates(brut, memoire, controle)
    _controler_les_tableaux(payload, controle)
    plan = set(chapitres_du_plan)
    if plan:
        controle.verifie.append("renvois confrontés au plan")
        for m in _RENVOI.finditer(brut):
            numero = int(m.group(1))
            if numero not in plan:
                controle.motifs.append(
                    f"« {m.group(0)} » renvoie à un chapitre qui n'existe pas dans le plan "
                    f"(chapitres {min(plan)} à {max(plan)}). Renvoie par le titre, ou retire."
                )
    return controle


# ── Séries, dates, renvois ───────────────────────────────────────────────────

#: Le nom qu'une phrase donne à une série, et l'identifiant de la série.
_NOMS_DE_SERIES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\br[ée]sultat net\b"), "resultat_net"),
    (re.compile(r"(?i)\b(capacit[ée] d.autofinancement|CAF)\b"), "caf"),
    (re.compile(r"(?i)\b(EBE|exc[ée]dent brut d.exploitation)\b"), "ebe"),
)
_RENVOI = re.compile(r"(?i)\bchapitre\s+(\d{1,2})\b")


def _series_du_fait(identifiant: str) -> str | None:
    for _, serie in _NOMS_DE_SERIES:
        if identifiant.startswith(serie + "_"):
            return serie
    return None


def _controler_les_series(brut: str, memoire: MemoireEtude, controle: Controle) -> None:
    """« Résultat net de 23 835,86 € » quand 23 835,86 € est la CAF : une série pour une autre.

    Le défaut n° 1 d'ÉCLORE, écrit en clair : la valeur existe bien dans la
    mémoire — mais sous un AUTRE nom. Le contrôle des chiffres en clair
    l'acceptait, puisqu'il ne jugeait que la valeur.
    """
    controle.verifie.append("séries nommées confrontées à leurs valeurs")
    par_serie: dict[str, list[float]] = {}
    for fait in memoire.faits.values():
        serie = _series_du_fait(fait.id)
        if serie is not None and fait.unite not in ("%",):
            par_serie.setdefault(serie, []).append(fait.valeur)
    for phrase in _PHRASE.findall(REPERE.sub(" ", brut)):
        nommees = [serie for motif, serie in _NOMS_DE_SERIES if motif.search(phrase)]
        if len(nommees) != 1:
            continue  # aucune série nommée, ou plusieurs : on ne sait pas attribuer
        nommee = nommees[0]
        for ecriture, valeur, unite in nombres_du_texte(phrase):
            if unite not in ("€", "k€", "M€", "Md€"):
                continue
            if _proche(valeur, par_serie.get(nommee, [])):
                continue
            autres = [
                s for s, valeurs in par_serie.items()
                if s != nommee and _proche(valeur, valeurs)
            ]
            if autres:
                controle.motifs.append(
                    f"« {ecriture} » est présenté comme {nommee.replace('_', ' ')} alors que "
                    f"c'est la valeur de la série « {autres[0].replace('_', ' ')} ». Cite le "
                    f"repère de la bonne série ({{{{{nommee}_anN}}}})."
                )


_EVENEMENT = re.compile(
    r"(?i)\b(quitt\w+ (son|mon|le) (poste|emploi)|d[ée]part du poste|temps plein|"
    r"passage en soci[ée]t[ée]|immatricul\w+|lancement)\b"
)
_ANNEE_SEULE = re.compile(r"\b(20[2-4]\d)\b")
#: Signes autour du mot de l'événement où son année est cherchée.
PORTEE_DATE = 25


def _controler_les_dates(brut: str, memoire: MemoireEtude, controle: Controle) -> None:
    """Une date d'événement qui contredit la phrase du client (cinq dates pour un départ).

    On ne compare que ce qui est comparable : le même événement (même mot
    clé), une année seule de part et d'autre, dans une même phrase. Une
    phrase qui porte plusieurs années ne date rien.
    """
    controle.verifie.append("dates d'événements confrontées aux décisions")
    reperes: dict[str, set[int]] = {}
    for decision in memoire.decisions:
        if decision.source != "brief":
            continue
        for phrase in _PHRASE.findall(decision.valeur):
            evenement = _EVENEMENT.search(phrase)
            annees = {int(a) for a in _ANNEE_SEULE.findall(phrase)}
            if evenement and len(annees) == 1:
                reperes.setdefault(_cle_d_evenement(evenement.group(0)), set()).update(annees)
    if not reperes:
        return
    for phrase in _PHRASE.findall(brut):
        evenement = _EVENEMENT.search(phrase)
        if not evenement:
            continue
        # L'année doit être PROCHE du mot de l'événement : dans « du pilote de
        # janvier 2027 au passage en société », 2027 date le pilote, pas le
        # passage (faux positif mesuré sur le texte réel d'ÉCLORE, 29/09/2026).
        annees = _annees_de_l_evenement(phrase, evenement)
        if len(annees) != 1:
            continue
        attendues = reperes.get(_cle_d_evenement(evenement.group(0)))
        if attendues and not annees & attendues:
            controle.motifs.append(
                f"« {phrase.strip()[:120]} » date l'événement en {annees.pop()} alors que "
                f"le client l'a fixé en {min(attendues)}. Reprends la date du client, "
                "telle quelle."
            )


#: Ce qui sépare les deux bornes d'un intervalle : une année placée AVANT
#: l'un de ces mots date l'autre borne, pas l'événement (« du pilote de
#: janvier 2027 au passage en société »).
_BORNE = re.compile(r"(?i)\b(au|aux|à|jusqu\w*|puis|avant|vers)\b")


def _annees_de_l_evenement(phrase: str, evenement: re.Match[str]) -> set[int]:
    """Les années qui datent CET événement : proches, et pas de l'autre côté d'une borne."""
    debut = max(0, evenement.start() - PORTEE_DATE)
    annees: set[int] = set()
    for m in _ANNEE_SEULE.finditer(phrase[debut:evenement.end() + PORTEE_DATE]):
        position = debut + m.start()
        if position < evenement.start():
            entre = phrase[position + 4:evenement.start()]
            if _BORNE.search(entre):
                continue
        annees.add(int(m.group(1)))
    return annees


def _cle_d_evenement(texte: str) -> str:
    texte = texte.lower()
    if "quitt" in texte or "départ" in texte or "depart" in texte or "temps plein" in texte:
        return "depart"
    if "société" in texte or "societe" in texte:
        return "societe"
    return texte.split()[0]


#: L'écriture citée dans un signal : « 8 576,08 € ».
_ECRITURE_CITEE = re.compile(r"«\s*(.+?)\s*»")
#: Au-delà, la liste des chiffres en clair est résumée : elle accompagne une
#: reprise, elle ne doit pas en évincer les autres motifs.
MAX_CHIFFRES_CITES = 12


def motif_des_signaux(signaux: Iterable[str]) -> str:
    """Les signaux d'un chapitre en UN motif, quand ils accompagnent une reprise.

    Un signal fait près de 190 caractères, et l'ensemble des motifs d'une
    reprise est coupé à 2 000 : une dizaine de signaux un par un évinçaient
    les motifs de figure qui les suivent (revue du 29/09/2026). La trace du
    chapitre garde, elle, chaque signal.
    """
    ecritures = [m.group(1) for s in signaux if (m := _ECRITURE_CITEE.search(s))]
    if not ecritures:
        return ""
    cites = ", ".join("« " + e + " »" for e in ecritures[:MAX_CHIFFRES_CITES])
    reste = len(ecritures) - MAX_CHIFFRES_CITES
    suite = f" (et {reste} autre(s))" if reste > 0 else ""
    return (
        "Chiffres écrits en clair hors de la mémoire : " + cites + suite + ". Cite le "
        "repère du fait voulu ({{…}}) ; s'il n'existe pas, retire le chiffre."
    )


def replis_de_derniere_tentative(payload: Any, faits: Mapping[str, Fait]) -> Any:
    """Niveau 3 : retire les phrases qui portent encore un repère inconnu.

    Une phrase dont le chiffre n'existe pas ne peut pas partir avec un trou ni
    avec `{{…}}` imprimé : on la retire. Le reste du chapitre est gardé — c'est
    la garantie qu'un chapitre est toujours validé.
    """

    def _nettoyer(texte: str) -> str:
        if not REPERE.search(texte):
            return texte
        gardees = []
        for phrase in _PHRASE.findall(texte):
            inconnus = [i for i in REPERE.findall(phrase) if i not in faits]
            if not inconnus:
                gardees.append(phrase)
        return "".join(gardees).strip()

    return _sans_blocs_vides(_parcourir(payload, _nettoyer))


def _sans_blocs_vides(valeur: Any) -> Any:
    """Retire un bloc dont le texte a été vidé par le repli.

    Une phrase retirée pouvait être la SEULE d'un paragraphe : le bloc restait,
    vide, et la validation le refusait — le chapitre échouait au dernier essai,
    exactement ce que le repli doit empêcher (test du 29/09/2026). Un bloc vidé
    part avec sa phrase ; une cellule de tableau vidée garde un tiret, pour que
    le tableau reste rectangulaire.
    """
    if isinstance(valeur, list):
        gardes = []
        for element in valeur:
            nettoye = _sans_blocs_vides(element)
            vide = isinstance(nettoye, dict) and "texte" in nettoye
            if vide and not str(nettoye["texte"]).strip():
                continue
            gardes.append("—" if nettoye == "" else nettoye)
        return gardes
    if isinstance(valeur, dict):
        return {k: _sans_blocs_vides(v) for k, v in valeur.items()}
    return valeur

# ── Tableaux : les identités du compte de résultat, colonne par colonne ──────

#: Les lignes qu'on sait reconnaître, et leur rôle dans les identités.
_LIGNES_DU_COMPTE: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ca", re.compile(r"(?i)^\s*(chiffre d.affaires|CA)\b(?!.*(cumul|mensuel|%))")),
    ("charges", re.compile(r"(?i)^\s*(total des charges|charges d.exploitation|total charges)\b")),
    ("ebe", re.compile(r"(?i)^\s*(EBE|exc[ée]dent brut d.exploitation)\b")),
    ("dotations", re.compile(r"(?i)^\s*dotations?\b")),
    ("impots", re.compile(r"(?i)^\s*(imp[ôo]ts?|IS\b|imp[ôo]t sur les soci[ée]t[ée]s)")),
    ("resultat_net", re.compile(r"(?i)^\s*r[ée]sultat net\b")),
    ("caf", re.compile(r"(?i)^\s*(CAF|capacit[ée] d.autofinancement)\b")),
)


def _tableaux(valeur: Any) -> Iterable[dict[str, Any]]:
    if isinstance(valeur, dict):
        if isinstance(valeur.get("lignes"), list) and isinstance(valeur.get("entetes"), list):
            yield valeur
        for v in valeur.values():
            yield from _tableaux(v)
    elif isinstance(valeur, list):
        for v in valeur:
            yield from _tableaux(v)


def _montant_de_cellule(cellule: object) -> float | None:
    trouves = nombres_du_texte(str(cellule))
    if len(trouves) != 1 or trouves[0][2] not in ("€", "k€", "M€", "Md€", None):
        return None
    return trouves[0][1]


def _egal(a: float, b: float) -> bool:
    return abs(a - b) <= max(1.0, abs(b) * 0.005)


def _controler_les_tableaux(payload: Any, controle: Controle) -> None:
    """Un compte de résultat se vérifie ligne à ligne : ses identités tiennent, ou non.

    29/09/2026, business plan ÉCLORE : « CA − charges ≠ résultat » en 2028 et
    2029, dans un tableau écrit par le modèle. Aucun contrôle ne refaisait une
    soustraction. On vérifie, pour chaque colonne où les lignes existent :
    CAF = résultat net + dotations ; EBE = CA − total des charges ; résultat
    net = EBE − dotations − impôts (seulement si la ligne d'impôt est là : sans
    elle, on ne sait pas si l'impôt est nul ou omis).
    """
    controle.verifie.append("identités des comptes de résultat")
    for tableau in _tableaux(payload):
        lignes: dict[str, list[object]] = {}
        for ligne in tableau["lignes"]:
            if not isinstance(ligne, list) or not ligne:
                continue
            for role, motif in _LIGNES_DU_COMPTE:
                if role not in lignes and motif.search(str(ligne[0])):
                    lignes[role] = ligne[1:]
                    break
        if len(lignes) < 3:
            continue
        entetes = [str(e) for e in tableau["entetes"][1:]]
        largeur = max(len(v) for v in lignes.values())
        for colonne in range(largeur):
            valeurs = {role: _cellule(lignes, role, colonne) for role, _ in _LIGNES_DU_COMPTE}
            nom = entetes[colonne] if colonne < len(entetes) else f"colonne {colonne + 1}"
            ecarts = _ecarts_d_identite(valeurs)
            for ecart in ecarts:
                controle.motifs.append(
                    f"Compte de résultat qui ne boucle pas, {nom} : "
                    f"{ecart.replace(',', ' ')}. Reprends les valeurs de la mémoire "
                    "(repères) : elles bouclent par construction."
                )


def _cellule(lignes: dict[str, list[object]], role: str, colonne: int) -> float | None:
    cellules = lignes.get(role)
    if cellules is None or colonne >= len(cellules):
        return None
    return _montant_de_cellule(cellules[colonne])


def _ecarts_d_identite(v: dict[str, float | None]) -> list[str]:
    """Les identités du compte de résultat qui ne tiennent pas sur une colonne."""
    ca, charges, ebe = v["ca"], v["charges"], v["ebe"]
    dotations, impots = v["dotations"], v["impots"]
    resultat, caf = v["resultat_net"], v["caf"]
    ecarts = []
    if caf is not None and resultat is not None and dotations is not None:
        if not _egal(caf, resultat + dotations):
            ecarts.append(
                f"CAF ({caf:,.0f}) ≠ résultat net ({resultat:,.0f}) + dotations ({dotations:,.0f})"
            )
    if ca is not None and charges is not None and ebe is not None:
        if not _egal(ebe, ca - charges):
            ecarts.append(f"EBE ({ebe:,.0f}) ≠ CA ({ca:,.0f}) − charges ({charges:,.0f})")
    if None not in (ebe, dotations, impots, resultat):
        assert ebe is not None and dotations is not None
        assert impots is not None and resultat is not None
        if not _egal(resultat, ebe - dotations - impots):
            ecarts.append(
                f"résultat net ({resultat:,.0f}) ≠ EBE ({ebe:,.0f}) − dotations "
                f"({dotations:,.0f}) − impôts ({impots:,.0f})"
            )
    return ecarts


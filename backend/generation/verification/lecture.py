"""Lecture du livrable produit, tel que le lecteur le verra (lot 4).

La passe de vérification ne relit pas les charges utiles des chapitres : elle
relit le **fichier livré**. C'est la leçon la plus chère du projet — le
markdown était propre, la barrière passait, et le document partait amputé parce
que quelque chose le refaisait après le contrôle (règle 3). Ce qui se vérifie
est ce qui se lit.

Le module ne juge rien. Il transforme un `.docx` en une matière comparable :
paragraphes hors tableaux, contenu des tableaux, et surtout **les grandeurs
chiffrées avec leur contexte**.
"""
from __future__ import annotations

import re
import statistics
import zipfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from core.numbers import (
    CURRENCY_ALTERNATION,
    MAGNITUDE_WORDS,
    NUMBER_BODY,
    SPACE_CLASS,
    parse_amount,
    parse_number,
)

#: Grandeur chiffrée : un nombre PORTANT une unité. Construit à partir des
#: briques de `core/numbers.py` plutôt que réécrit : la liste des devises n'a
#: qu'une seule source (règle 5). Le pourcentage y est ajouté ici, car
#: `core.numbers` ne le traite pas comme une unité monétaire.
_POURCENTAGE = r"%"
_GRANDEUR = re.compile(
    rf"(?<![A-Za-z\d])({NUMBER_BODY}){SPACE_CLASS}*"
    rf"({CURRENCY_ALTERNATION}|{MAGNITUDE_WORDS}|{_POURCENTAGE})",
    re.IGNORECASE,
)

#: Fenêtre de contexte reprise dans le motif d'anomalie. Un motif doit être
#: trouvable dans le document par le lecteur (règle 2) : sans le texte autour,
#: « 420 » est introuvable.
CONTEXTE = 60


@dataclass(frozen=True)
class Mesure:
    """Une grandeur chiffrée relevée dans le document livré."""

    valeur: float
    """Valeur ramenée à son unité de base : `1,25 M€` vaut 1 250 000."""
    unite: str
    """Unité telle qu'écrite dans le document."""
    texte: str
    """Le fragment exact, pour que le motif soit trouvable."""
    contexte: str
    """La phrase autour, pour situer le fragment."""
    dans_un_tableau: bool = False
    #: La PHRASE entière qui porte la grandeur, et la position de celle-ci dans
    #: la phrase. `contexte` (soixante caractères de part et d'autre) suffit à
    #: retrouver le fragment, pas à voir le calcul qui l'a produit : dans
    #: « 244 296 divisé par 269 721 donne 0,906, soit 90,6 % », les opérandes
    #: sont hors de la fenêtre (corpus de production, 13/09/2026).
    phrase: str = ""
    debut_dans_la_phrase: int = -1
    chapitre: int | None = None
    """Le chapitre où la grandeur a été relevée, quand le bandeau le dit.

    C'est lui qui rend une anomalie RÉPARABLE : sans numéro de chapitre, la
    boucle de correction ne sait pas quoi réécrire et laisse le défaut dans le
    document livré."""

    @property
    def est_un_pourcentage(self) -> bool:
        return self.unite.strip() == "%"

    @property
    def est_monetaire(self) -> bool:
        return not self.est_un_pourcentage and not self.est_une_magnitude_seule

    @property
    def est_une_magnitude_seule(self) -> bool:
        return self.unite.strip().lower() in ("million", "millions", "milliard", "milliards")


@dataclass
class DocumentLu:
    """Le livrable, ramené à ce qui est comparable."""

    chemin: Path
    paragraphes: list[str] = field(default_factory=list)
    """Prose hors tableaux."""
    cellules: list[str] = field(default_factory=list)
    """Contenu de toutes les cellules de tableau."""
    tableaux: int = 0
    tableaux_vides: int = 0
    images: int = 0
    mesures: list[Mesure] = field(default_factory=list)
    #: Le chapitre de chaque paragraphe et de chaque cellule, dans le même
    #: ordre que `paragraphes` et `cellules`. `None` avant le premier bandeau
    #: — couverture, sommaire — et pour un document lu sans bandeaux.
    chapitre_du_paragraphe: list[int | None] = field(default_factory=list)
    chapitre_de_la_cellule: list[int | None] = field(default_factory=list)
    #: Ce que le lecteur voit AVEC chaque cellule : l'en-tête de sa colonne, puis
    #: sa ligne entière. Même ordre que `cellules` ; vide pour les documents lus
    #: sans structure de tableau.
    #:
    #: Corpus du 14/09/2026 : 212 des 382 « chiffres hors socle » d'une étude
    #: concurrentielle étaient des cellules du chapitre 6 jugées seules —
    #: « 250 000 € », « 0,029 % » — sous un en-tête « CA estimé » que le
    #: contrôle ne voyait pas. Le lecteur, lui, lit les deux ensemble.
    contexte_de_la_cellule: list[str] = field(default_factory=list)

    @property
    def texte_integral(self) -> str:
        return "\n".join([*self.paragraphes, *self.cellules])

    @property
    def mots(self) -> int:
        return len(self.texte_integral.split())

    @property
    def mots_en_tableaux(self) -> int:
        return sum(len(cellule.split()) for cellule in self.cellules)

    @property
    def part_en_tableaux(self) -> float:
        return self.mots_en_tableaux / self.mots if self.mots else 0.0

    @property
    def mediane_paragraphe(self) -> float:
        longueurs = [len(p.split()) for p in self.paragraphes if p.strip()]
        return statistics.median(longueurs) if longueurs else 0.0

    @property
    def part_paragraphes_longs(self) -> float:
        longueurs = [len(p.split()) for p in self.paragraphes if p.strip()]
        if not longueurs:
            return 0.0
        return sum(1 for n in longueurs if n > 60) / len(longueurs)


#: Fin de phrase : ponctuation forte suivie d'une espace ou de la fin du texte.
#: La virgule décimale française n'y est pas prise — « 0,906. » termine bien.
_FIN_DE_PHRASE = re.compile(r"[.!?…](?=\s|$)")

#: Au-delà, une « phrase » est un bloc sans ponctuation (une cellule, une liste
#: écrite d'un trait) : on la borne pour ne pas combiner des nombres sans lien.
_PHRASE_MAX = 400


def _phrase(texte: str, debut: int, fin: int) -> tuple[str, int]:
    """La phrase qui contient [debut, fin[, et la position du début dedans."""
    ouverture = 0
    for correspondance in _FIN_DE_PHRASE.finditer(texte, 0, debut):
        ouverture = correspondance.end()
    suite = _FIN_DE_PHRASE.search(texte, fin)
    fermeture = suite.end() if suite else len(texte)
    ouverture = max(ouverture, debut - _PHRASE_MAX)
    fermeture = min(fermeture, fin + _PHRASE_MAX)
    phrase = texte[ouverture:fermeture]
    retrait = len(phrase) - len(phrase.lstrip())
    return phrase.strip(), debut - ouverture - retrait


def _contexte(texte: str, debut: int, fin: int) -> str:
    extrait = texte[max(debut - CONTEXTE, 0) : fin + CONTEXTE]
    return " ".join(extrait.split())


def mesures_dans(
    texte: str, *, dans_un_tableau: bool = False, chapitre: int | None = None
) -> list[Mesure]:
    """Toutes les grandeurs chiffrées d'un texte, avec leur contexte.

    Ne relève QUE les nombres portant une unité. C'est une restriction
    délibérée, et il faut la connaître pour savoir ce que la passe ne voit
    pas : « trois portes d'entrée », « 0-30 j », « chapitre 12 » ne sont pas
    des affirmations de marché, et les traiter comme telles produirait des
    motifs faux — pires qu'absents (règle 2).
    """
    relevees: list[Mesure] = []
    for correspondance in _GRANDEUR.finditer(texte):
        brut, unite = correspondance.group(1), correspondance.group(2)
        if unite.strip() == "%":
            valeur = parse_number(brut)
        else:
            valeur = parse_amount(brut, unite)
        if valeur is None:
            continue
        phrase, position = _phrase(texte, *correspondance.span())
        relevees.append(
            Mesure(
                valeur=valeur,
                unite=unite,
                texte=correspondance.group(0).strip(),
                contexte=_contexte(texte, *correspondance.span()),
                dans_un_tableau=dans_un_tableau,
                phrase=phrase,
                debut_dans_la_phrase=position,
                chapitre=chapitre,
            )
        )
    return relevees


def _dans_son_tableau(mesure: Mesure, contexte: str, contenu: str = "") -> Mesure:
    """La grandeur d'une cellule, jugée avec ce que le lecteur voit autour.

    La « phrase » devient `en-tête : ligne entière`, et la position de la
    grandeur y est recalculée : les règles de la prose — estimation déclarée,
    source nommée, calcul posé — s'appliquent alors telles quelles, sans
    exception propre aux tableaux.
    """
    if not contexte:
        return mesure
    # La position se cherche DANS SA CELLULE, et sur un nombre entier : « 0 % »
    # est aussi la fin de « 40 % », et la première occurrence de la ligne
    # plaçait le zéro dans la cellule voisine — qui le « commentait » alors
    # (relecture du 14/09/2026).
    debut_ligne = contexte.find(" : ") + 3
    position = -1
    curseur = debut_ligne
    for morceau in contexte[debut_ligne:].split(" | "):
        if contenu and morceau == contenu:
            trouve = re.search(r"(?<![\d,.])" + re.escape(mesure.texte), morceau)
            if trouve:
                position = curseur + trouve.start()
            break
        curseur += len(morceau) + 3
    if position < 0:
        position = contexte.find(mesure.texte, debut_ligne)
    if position < 0:
        return mesure
    return replace(
        mesure, phrase=contexte, debut_dans_la_phrase=position,
        contexte=" ".join(contexte.split())[:240],
    )


def lire_livrable(chemin: Path) -> DocumentLu:
    """Ouvre le `.docx` livré et en extrait la matière vérifiable.

    Lève si le fichier est absent ou illisible : un contrôle qui n'a rien à
    comparer est un échec, jamais un succès (règle 1).
    """
    from docx import Document  # noqa: PLC0415

    chemin = Path(chemin)
    if not chemin.is_file():
        msg = f"Livrable introuvable : {chemin}. Rien à vérifier."
        raise FileNotFoundError(msg)

    document = Document(str(chemin))
    lu = DocumentLu(chemin=chemin)
    _parcourir_le_corps(document, lu)

    with zipfile.ZipFile(chemin) as archive:
        lu.images = sum(
            1 for nom in archive.namelist() if nom.startswith("word/media/")
        )

    for prose, chapitre in zip(lu.paragraphes, lu.chapitre_du_paragraphe, strict=True):
        lu.mesures.extend(mesures_dans(prose, chapitre=chapitre))
    contextes = lu.contexte_de_la_cellule or [""] * len(lu.cellules)
    for contenu, chapitre, contexte in zip(
        lu.cellules, lu.chapitre_de_la_cellule, contextes, strict=True,
    ):
        lu.mesures.extend(
            _dans_son_tableau(mesure, contexte, contenu)
            for mesure in mesures_dans(contenu, dans_un_tableau=True, chapitre=chapitre)
        )

    return lu


#: Le bandeau qui ouvre un chapitre dans le `.docx`. Son texte vient de
#: `rendu_word.composants.marqueur_de_chapitre` — une seule source (règle 5) ;
#: ici on le RELIT, donc on décrit sa forme, pas son contenu.
_BANDEAU_RE = re.compile(r"^\s*CHAPITRE\s+(\d{1,3})\b", re.IGNORECASE)


def _parcourir_le_corps(document: Any, lu: DocumentLu) -> None:
    """Lit le document DANS SON ORDRE, en retenant le chapitre courant.

    `document.paragraphs` et `document.tables` sont deux flux séparés : lus
    l'un après l'autre, ils perdent l'entrelacement, donc le chapitre auquel
    chaque passage appartient. Or c'est ce numéro qui rend un défaut
    réparable — la boucle de correction réécrit un CHAPITRE, pas un document.
    On parcourt donc le corps lui-même, élément par élément.

    Le bandeau de chapitre est un tableau 1×1 (`composants.bandeau_chapitre`) :
    c'est sa première cellule qui porte « CHAPITRE 07 ».
    """
    from docx.table import Table  # noqa: PLC0415
    from docx.text.paragraph import Paragraph  # noqa: PLC0415

    courant: int | None = None
    for element in document.element.body.iterchildren():
        balise = element.tag.rsplit("}", 1)[-1]
        if balise == "p":
            texte = Paragraph(element, document).text.strip()
            if texte:
                lu.paragraphes.append(texte)
                lu.chapitre_du_paragraphe.append(courant)
            continue
        if balise != "tbl":
            continue
        table = Table(element, document)
        lu.tableaux += 1
        contenu_table: list[str] = []
        contextes_table: list[str] = []
        lignes = [[cellule.text.strip() for cellule in ligne.cells] for ligne in table.rows]
        entetes = lignes[0] if len(lignes) > 1 else []
        for rang, cellules in enumerate(lignes):
            texte_de_la_ligne = " | ".join(c for c in cellules if c)
            for colonne, texte in enumerate(cellules):
                if not texte:
                    continue
                contenu_table.append(texte)
                en_tete = entetes[colonne] if rang and colonne < len(entetes) else ""
                contextes_table.append(f"{en_tete} : {texte_de_la_ligne}" if en_tete else "")
        if not contenu_table:
            # Un tableau sans une seule cellule remplie est le symptôme exact
            # de la perte de lignes déjà constatée sur ce projet.
            lu.tableaux_vides += 1
        bandeau = _BANDEAU_RE.match(contenu_table[0]) if contenu_table else None
        if bandeau is not None:
            courant = int(bandeau.group(1))
        lu.cellules.extend(contenu_table)
        lu.chapitre_de_la_cellule.extend([courant] * len(contenu_table))
        lu.contexte_de_la_cellule.extend(contextes_table)


#: Balises dont le texte est de la PROSE. Les titres en font partie : le
#: contrôle d'intégrité cherche « CHAPITRE 07 » dans le texte intégral, et ce
#: marqueur vit dans un `<h…>`.
_BALISES_DE_PROSE = ("p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote")


def lire_livrable_html(html: str, *, chemin: Path | None = None) -> DocumentLu:
    """Même matière vérifiable, autre porte d'entrée : le document HTML.

    Le business plan et la stratégie tournent sur le moteur hérité : ils ne
    produisent ni socle ni `.docx`, donc `lire_livrable` — qui ouvre un `.docx`
    — ne peut rien lire chez eux. Deux des six contrôles du lot 4 ne dépendent
    pourtant pas du socle (intégrité et densité), et ce sont exactement ceux qui
    ont attrapé les désastres historiques du projet : tableaux vidés de leurs
    lignes, chapitres absents, document sans prose. Les priver de porte
    d'entrée revenait à ne pas les exécuter du tout.

    Deux précautions, toutes deux payées comptant sur ce dépôt :

    - **Les cellules sont relevées AVANT de détacher le tableau.** `decompose()`
      détruit l'élément ET ses enfants : c'est ce qui a envoyé un compte de
      résultat vide à un client (règle 3). On extrait, puis on détache — et avec
      `extract()`, qui détache sans détruire.
    - **On ne mesure pas notre propre balisage.** Le texte est pris balise par
      balise, jamais par un `get_text()` global : sans quoi `px`, `padding` et
      `cccccc` des styles en ligne entreraient dans la prose et fausseraient la
      densité — défaut réellement mesuré ici (corollaire de la règle 9).
    """
    from bs4 import BeautifulSoup  # noqa: PLC0415

    soupe = BeautifulSoup(html, "html.parser")
    for parasite in soupe(["script", "style", "head"]):
        parasite.decompose()

    lu = DocumentLu(chemin=chemin or Path("(document HTML)"))
    lu.images = len(soupe.find_all("img"))

    # Tableaux les plus extérieurs seulement : un tableau imbriqué verrait
    # sinon ses cellules comptées deux fois, et gonflerait la part en tableaux.
    tableaux = [t for t in soupe.find_all("table") if t.find_parent("table") is None]
    for tableau in tableaux:
        lu.tableaux += 1
        contenu = [
            cellule.get_text(" ", strip=True)
            for cellule in tableau.find_all(["td", "th"])
        ]
        contenu = [texte for texte in contenu if texte]
        if not contenu:
            lu.tableaux_vides += 1
        lu.cellules.extend(contenu)
        tableau.extract()

    for bloc in soupe.find_all(_BALISES_DE_PROSE):
        texte = bloc.get_text(" ", strip=True)
        if texte:
            lu.paragraphes.append(texte)

    for prose in lu.paragraphes:
        lu.mesures.extend(mesures_dans(prose))
    for contenu_cellule in lu.cellules:
        lu.mesures.extend(mesures_dans(contenu_cellule, dans_un_tableau=True))

    return lu

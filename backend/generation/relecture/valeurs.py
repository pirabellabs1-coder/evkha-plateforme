"""Les valeurs du document : nombres, phrases, et valeurs DATÉES d'une série.

Une seule lecture des nombres (règle 5) : celle de la mémoire
(`memoire.controle`). Ce module y ajoute la position de chaque nombre, et ce
que le texte en dit : quelle série il nomme (« seuil de rentabilité »), pour
quel exercice (« en 2028 », colonne « 2028 », « la troisième année »).
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from ..memoire.controle import _NOMBRE, _valeur
from ..memoire.etude import MemoireEtude
from ..memoire.faits import Fait
from .document import Document, Section, Tableau


@dataclass(frozen=True)
class Nombre:
    ecriture: str
    valeur: float
    unite: str | None
    debut: int
    fin: int

    @property
    def monetaire(self) -> bool:
        return self.unite in ("€", "k€", "M€", "Md€")

    @property
    def pourcentage(self) -> bool:
        return self.unite == "%"


def nombres(texte: str) -> list[Nombre]:
    trouves: list[Nombre] = []
    for m in _NOMBRE.finditer(texte or ""):
        try:
            valeur = _valeur(m.group(1), m.group(2))
        except ValueError:
            continue
        trouves.append(Nombre(m.group(0).strip(), valeur, m.group(2), m.start(), m.end()))
    return trouves


def est_une_annee(nombre: Nombre) -> bool:
    return nombre.unite is None and nombre.valeur.is_integer() and 1990 <= nombre.valeur <= 2060


_FIN_DE_PHRASE = re.compile(r"(?<=[.!?])\s+(?=[«A-ZÀ-ÖØ-Þ0-9])")


def phrases(texte: str) -> list[str]:
    """Les phrases d'un texte ; une virgule décimale (« 51,5 % ») ne coupe rien."""
    return [p.strip() for p in _FIN_DE_PHRASE.split(texte or "") if p.strip()]


def phrases_de(section: Section, *, cellules: bool = True) -> Iterator[str]:
    """Chaque phrase de la prose, puis chaque cellule longue d'un tableau.

    Une cellule se lit avec le libellé de sa ligne (« Marge de sécurité : 51,5 %
    en 2028 ») : sans lui, elle ne dit pas de quoi elle parle. Un encadré rendu
    en tableau d'une seule ligne n'a que des en-têtes : ils se lisent aussi.
    """
    for paragraphe in section.paragraphes:
        yield from phrases(paragraphe)
    if not cellules:
        return
    for tableau in section.tableaux:
        lignes = list(tableau.lignes) or [tableau.entetes]
        for ligne in lignes:
            for rang, cellule in enumerate(ligne):
                if len(cellule) <= 40:
                    continue
                prefixe = f"{ligne[0]} : " if rang > 0 and ligne[0] else ""
                for phrase in phrases(cellule):
                    yield f"{prefixe}{phrase}"


def proche(a: float, b: float, *, relatif: float = 0.01, absolu: float = 0.01) -> bool:
    return abs(a - b) <= max(abs(b) * relatif, absolu)


def extrait(texte: str, debut: int, fin: int, *, marge: int = 60) -> str:
    """Le passage autour d'un nombre, tel qu'écrit, coupé aux mots."""
    gauche = texte.rfind(" ", 0, max(0, debut - marge)) + 1
    droite = texte.find(" ", min(len(texte), fin + marge))
    return texte[gauche: droite if droite != -1 else len(texte)].strip()


# ── Séries nommées ──────────────────────────────────────────────────────────

#: Les séries que le texte nomme, dans l'ordre où les tester : la plus
#: précise d'abord (« marge de sécurité sur le seuil » est une marge, pas un
#: seuil). Chaque série a son unité : un montant ne se compare pas à un taux.
SERIES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"(?i)marge de s[ée]curit[ée]"), "marge_securite", "%"),
    (re.compile(r"(?i)seuil de rentabilit[ée]"), "seuil_rentabilite", "€"),
    (re.compile(r"(?i)capacit[ée] d.autofinancement|\bCAF\b"), "caf", "€"),
    (re.compile(r"(?i)exc[ée]dent brut|\bEBE\b"), "ebe", "€"),
    (re.compile(r"(?i)r[ée]sultat net|\br[ée]sultat\b(?! d.exploitation)"), "resultat_net", "€"),
    (re.compile(r"(?i)chiffre d.affaires"), "ca_previsionnel", "€"),
    (re.compile(r"(?i)charges fixes"), "charges_fixes", "€"),
    (re.compile(r"(?i)panier moyen"), "panier_moyen", "€"),
)
#: Ce qui fait d'un libellé autre chose que la série qu'il nomme : une marge
#: d'EBE est un taux, un « CA si −10 % » un scénario.
_PAS_LA_SERIE = re.compile(
    r"(?i)\bmarge (d.EBE|nette|brute)|\btaux\b|\bpart\b|\bévolution\b|\bécart\b|"
    r"\bmensuel|\bpar mois\b|[−-] ?\d+ ?%|\bsi\b|\bsans\b|\bnon retenu|\bvariante\b|"
    r"\balternati|\bscénario (bas|haut|pessimiste|optimiste|dégradé|de baisse)"
)


def serie_nommee(libelle: str, unite: str | None = None) -> str | None:
    """La série qu'un libellé nomme, de la bonne unité ; aucune s'il en nomme plusieurs."""
    if _PAS_LA_SERIE.search(libelle):
        return None
    for motif, serie, unite_serie in SERIES:
        if motif.search(libelle):
            if unite is None or (unite == "%") == (unite_serie == "%"):
                return serie
            return None
    return None


def series_nommees(texte: str) -> list[tuple[str, str]]:
    """Toutes les séries qu'un texte nomme, (série, unité), sans doublon."""
    vues: list[tuple[str, str]] = []
    for motif, serie, unite in SERIES:
        if motif.search(texte) and (serie, unite) not in vues:
            if serie == "seuil_rentabilite" and any(s == "marge_securite" for s, _ in vues):
                # « marge de sécurité sur le seuil » : la marge, pas le seuil.
                if len(re.findall(r"(?i)seuil de rentabilit", texte)) <= 1:
                    continue
            vues.append((serie, unite))
    return vues


# ── Valeurs datées ──────────────────────────────────────────────────────────

_ANNEE = re.compile(r"\b(19[9]\d|20[0-6]\d)\b")
_ORDINAL = re.compile(
    r"(?i)\b(premi[eè]re|deuxi[eè]me|seconde|troisi[eè]me|quatri[eè]me|cinqui[eè]me) ann[ée]e"
)
_RANG = {"premi": 1, "deuxi": 2, "second": 2, "troisi": 3, "quatri": 4, "cinqui": 5}


def annee_d_un_ordinal(texte: str, premiere_annee: int | None) -> int | None:
    """« la troisième année » → l'exercice correspondant, si l'on connaît le premier."""
    m = _ORDINAL.search(texte)
    if m is None or premiere_annee is None:
        return None
    mot = m.group(1).lower()
    rang = next((r for prefixe, r in _RANG.items() if mot.startswith(prefixe)), None)
    return premiere_annee + rang - 1 if rang else None


@dataclass(frozen=True)
class ValeurDatee:
    serie: str
    annee: int
    nombre: Nombre
    section: str
    #: Le passage tel qu'écrit (la phrase, ou « libellé · colonne · valeur »).
    passage: str


def _annee_unique(texte: str) -> int | None:
    annees = {int(a) for a in _ANNEE.findall(texte)}
    return annees.pop() if len(annees) == 1 else None


def _valeurs_d_un_tableau(tableau: Tableau, section: Section) -> Iterator[ValeurDatee]:
    entetes = list(tableau.entetes)
    annees_des_colonnes = [_annee_unique(e) for e in entetes]
    # Un tableau qui compare des variantes et en désigne une « retenue » : seule
    # celle-là porte les chiffres du prévisionnel.
    retenue = [
        ligne for ligne in tableau.lignes
        if ligne and re.search(r"(?i)\bretenue?\b", ligne[0])
        and not re.search(r"(?i)non retenu", ligne[0])
    ]
    colonne_annee = next(
        (j for j, e in enumerate(entetes) if re.fullmatch(r"(?i)\s*ann[ée]es?\s*", e)), None
    )
    for ligne in tableau.lignes:
        if not ligne or (retenue and ligne not in retenue):
            continue
        libelle = ligne[0]
        if _PAS_LA_SERIE.search(libelle):
            continue
        for j, cellule in enumerate(ligne[1:], start=1):
            valeurs = [n for n in nombres(cellule) if not est_une_annee(n)]
            if not valeurs:
                continue
            nombre = valeurs[0]
            entete = entetes[j] if j < len(entetes) else ""
            # La série : le libellé de la ligne, sinon l'en-tête de la colonne
            # (« Résultat 2029, scénario prudent »).
            serie = serie_nommee(libelle, nombre.unite) or serie_nommee(entete, nombre.unite)
            if serie is None:
                continue
            annee = (
                annees_des_colonnes[j] if j < len(annees_des_colonnes) else None
            ) or (
                _annee_unique(ligne[colonne_annee]) if colonne_annee is not None
                and colonne_annee < len(ligne) else None
            ) or _annee_unique(libelle)
            if annee is None:
                continue
            yield ValeurDatee(
                serie, annee, nombre, section.numero,
                f"{libelle} · {entete} · {cellule}",
            )


#: Une phrase qui reprend la série de la précédente : « Elle s'élargit ensuite… ».
_REPRISE = re.compile(r"(?i)^(elle|il|celle-ci|celui-ci|cette marge|ce seuil|ce r[ée]sultat)\b")


def _valeurs_d_une_phrase(
    phrase: str, section: Section, heritees: list[tuple[str, str]] | None = None,
) -> Iterator[ValeurDatee]:
    """« 51,5 % en 2028, 74,4 % en 2029 » quand la phrase nomme une marge de sécurité.

    Un nombre est rattaché à une série quand la phrase n'en nomme qu'une de
    son unité, et à l'année écrite JUSTE après lui (« en 2028 », « (2028) »),
    sans autre nombre entre les deux.
    """
    series = series_nommees(phrase)
    reprise = bool(heritees) and bool(_REPRISE.search(phrase))
    if not series and not reprise:
        return
    lus = nombres(phrase)
    for rang, nombre in enumerate(lus):
        if est_une_annee(nombre) or nombre.unite is None:
            continue
        candidates = [s for s, u in series if (u == "%") == nombre.pourcentage]
        if not candidates and reprise and heritees:
            # « Elle s'élargit ensuite : 51,5 % en 2028 » — la série de la phrase
            # précédente, pour l'unité que celle-ci ne nomme pas.
            candidates = [s for s, u in heritees if (u == "%") == nombre.pourcentage]
        if len(candidates) != 1:
            continue
        suivant = lus[rang + 1] if rang + 1 < len(lus) else None
        if suivant is None or not est_une_annee(suivant):
            continue
        entre = phrase[nombre.fin: suivant.debut]
        if not _ENTRE_NOMBRE_ET_ANNEE.fullmatch(entre) or _MENSUEL.search(entre):
            continue
        yield ValeurDatee(candidates[0], int(suivant.valeur), nombre, section.numero, phrase)


#: Ce qui peut séparer une valeur de SON année : « 51,5 % en 2028 »,
#: « 0,2 % du chiffre d'affaires en 2027 », « 24 802 € (2027) ». Une virgule,
#: une parenthèse fermée ou un deux-points annoncent une autre proposition :
#: « (37 500 €), et le reste en 2029 » ne date pas 37 500 €.
_ENTRE_NOMBRE_ET_ANNEE = re.compile(
    r"\s*\(\s*|\s+(?:[^,;:()]{0,30}?\s)?(?:en|pour|sur|au titre de)\s+", re.IGNORECASE
)
_MENSUEL = re.compile(r"(?i)par mois|/ ?mois|mensuel")


def valeurs_datees(document: Document) -> list[ValeurDatee]:
    trouvees: list[ValeurDatee] = []
    for section in document.sections:
        for tableau in section.tableaux:
            trouvees.extend(_valeurs_d_un_tableau(tableau, section))
        heritees: list[tuple[str, str]] = []
        for phrase in phrases_de(section):
            trouvees.extend(_valeurs_d_une_phrase(phrase, section, heritees))
            heritees = series_nommees(phrase) or (heritees if _REPRISE.search(phrase) else [])
    return trouvees


# ── La mémoire, lue par série et par exercice ───────────────────────────────


def fait_de(memoire: MemoireEtude | None, serie: str, annee: int) -> Fait | None:
    """Le fait `serie_anN` de l'exercice `annee`, s'il existe."""
    if memoire is None:
        return None
    for fait in memoire.faits.values():
        if fait.annee == annee and re.fullmatch(rf"{re.escape(serie)}_an\d", fait.id):
            return fait
    return None


def faits_de_la_serie(memoire: MemoireEtude | None, serie: str) -> list[Fait]:
    if memoire is None:
        return []
    return [
        f for f in memoire.faits.values() if re.fullmatch(rf"{re.escape(serie)}_an\d", f.id)
    ]


def en_euros(fait: Fait) -> float | None:
    """La valeur d'un fait monétaire en euros (les faits sont en unité de base)."""
    from ..socle.schema import valeur_en_unites_de_base  # noqa: PLC0415

    base = valeur_en_unites_de_base(fait.valeur, fait.unite)
    return base[0] if base else None


def valeurs_des_faits(faits: Iterable[Fait]) -> list[float]:
    valeurs: list[float] = []
    for fait in faits:
        euros = en_euros(fait)
        valeurs.append(euros if euros is not None else fait.valeur)
    return valeurs

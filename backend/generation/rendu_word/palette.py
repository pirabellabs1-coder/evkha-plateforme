"""Charte graphique du livrable, dérivée du formulaire client.

Le formulaire ne fournit que deux couleurs (principale et secondaire). Le
document, lui, en emploie quatre plus trois couleurs de texte — c'est ce qui
lui donne son allure de document professionnel plutôt que de page bicolore.

Ce module comble l'écart par des règles déterministes, et non par des valeurs
choisies à la main : le système doit produire un document lisible **quelle que
soit** la couleur saisie, y compris un jaune vif ou un noir.

Référence : « Etude_de_marche_Joalie_EVKHA_2026_v4.docx », dont la palette
mesurée est primaire `#3A132C`, fond `#F1EEDB`, fond alterné `#EDE6D0`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_HEX = re.compile(r"^#?([0-9A-Fa-f]{6})$")

#: Palette EVKHA, utilisée quand le client ne renseigne rien.
EVKHA_PRIMAIRE = "#1A1A1A"
EVKHA_SECONDAIRE = "#C9A227"

#: Texte du corps et des légendes : constants, jamais dérivés. Ils doivent
#: rester lisibles sur fond blanc quelle que soit la charte du client.
TEXTE_CORPS = "#202020"
TEXTE_LEGENDE = "#666666"

#: Ratio de contraste minimum entre un texte et son fond (WCAG AA, texte normal).
CONTRASTE_MINIMUM = 4.5


class CouleurInvalideError(ValueError):
    """La chaîne fournie n'est pas une couleur hexadécimale à six chiffres."""


def normaliser(couleur: str) -> str:
    """`3a132c` ou `#3A132C` -> `#3A132C`. Lève si la chaîne n'est pas une couleur."""
    correspondance = _HEX.match(couleur.strip())
    if correspondance is None:
        msg = f"Couleur invalide : {couleur!r}. Format attendu : #RRGGBB."
        raise CouleurInvalideError(msg)
    return "#" + correspondance.group(1).upper()


def est_une_couleur(couleur: str) -> bool:
    return bool(couleur) and _HEX.match(couleur.strip()) is not None


def vers_rvb(couleur: str) -> tuple[int, int, int]:
    valeur = normaliser(couleur)[1:]
    return int(valeur[0:2], 16), int(valeur[2:4], 16), int(valeur[4:6], 16)


def depuis_rvb(rouge: float, vert: float, bleu: float) -> str:
    def borner(canal: float) -> int:
        return max(0, min(255, round(canal)))

    return f"#{borner(rouge):02X}{borner(vert):02X}{borner(bleu):02X}"


def melanger(couleur: str, vers: str, proportion: float) -> str:
    """Mélange `couleur` vers `vers`. `proportion` 0 = inchangé, 1 = `vers`."""
    r1, v1, b1 = vers_rvb(couleur)
    r2, v2, b2 = vers_rvb(vers)
    p = max(0.0, min(1.0, proportion))
    return depuis_rvb(r1 + (r2 - r1) * p, v1 + (v2 - v1) * p, b1 + (b2 - b1) * p)


def _canal_lineaire(valeur: int) -> float:
    c = valeur / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(couleur: str) -> float:
    """Luminance relative WCAG, entre 0 (noir) et 1 (blanc)."""
    r, v, b = (_canal_lineaire(c) for c in vers_rvb(couleur))
    return 0.2126 * r + 0.7152 * v + 0.0722 * b


def contraste(couleur_a: str, couleur_b: str) -> float:
    """Ratio de contraste WCAG entre deux couleurs, de 1 à 21."""
    a, b = luminance(couleur_a), luminance(couleur_b)
    clair, sombre = max(a, b), min(a, b)
    return (clair + 0.05) / (sombre + 0.05)


def texte_lisible_sur(fond: str) -> str:
    """Blanc ou anthracite, celui qui contraste le plus avec `fond`.

    C'est la règle qui protège contre le cas réel : un client choisit un jaune
    vif comme couleur principale, et le texte blanc des bandeaux devient
    illisible. Ici, il passe automatiquement en anthracite.
    """
    return "#FFFFFF" if contraste("#FFFFFF", fond) >= contraste(TEXTE_CORPS, fond) else TEXTE_CORPS


def fond_lisible(couleur: str, cible: float = CONTRASTE_MINIMUM) -> str:
    """Assombrit ou éclaircit `couleur` jusqu'à ce qu'un texte y soit lisible.

    Certaines couleurs ne permettent AUCUN texte lisible : un gris moyen
    (`#7F7F7F`) plafonne à 4,07:1 avec du blanc comme avec de l'anthracite,
    sous le seuil WCAG AA de 4,5:1. Aucun choix de couleur de texte ne sauve ce
    cas — il faut déplacer le fond.

    On pousse donc la couleur dans la direction où elle est déjà engagée : un
    fond plutôt sombre devient plus sombre, un fond plutôt clair devient plus
    clair. La teinte du client est conservée, seule sa luminosité bouge.
    """
    if contraste(texte_lisible_sur(couleur), couleur) >= cible:
        return couleur

    destination = "#FFFFFF" if luminance(couleur) > 0.4 else "#000000"
    for etape in range(1, 21):
        candidat = melanger(couleur, destination, etape * 0.05)
        if contraste(texte_lisible_sur(candidat), candidat) >= cible:
            return candidat
    return destination


# ── Jetons de design du document de référence (lot 0) ───────────────────────
# Valeurs relevées dans « references/joalie_2026.docx ». Elles servent de
# défaut : un client qui ne renseigne rien obtient exactement cette charte.

REF_PRUNE = "#3A132C"          # couleur principale
REF_PRUNE_FONCE = "#241019"    # texte prune sur fond clair
REF_CREME = "#F1EEDB"          # fond des blocs
REF_CREME_ALT = "#EDE6D0"      # encadrés de verdict
REF_ROSE_PALE = "#E9DFE4"      # cellules de chiffres clés
REF_ROSE_GRISE = "#D8C7CF"     # séries secondaires
REF_OR_BRONZE = "#B98B4E"      # accent des graphiques
REF_FOND_GRAPHIQUE = "#FDFBF6"  # fond des figures matplotlib
BLANC = "#FFFFFF"


@dataclass(frozen=True)
class Palette:
    """Les couleurs dont le gabarit a besoin."""

    primaire: str
    secondaire: str
    #: Couleur réellement employée pour les aplats portant du texte (bandeaux,
    #: en-têtes de tableau). Égale à `primaire` dans l'immense majorité des cas ;
    #: ajustée seulement quand aucune couleur de texte n'y serait lisible.
    fond_bandeau: str
    fond_clair: str
    fond_clair_alt: str
    texte_corps: str
    texte_sur_primaire: str
    texte_legende: str
    #: Jetons secondaires du lot 0. Valeurs de référence par défaut ; dérivées
    #: de la couleur principale quand le client en fournit une autre.
    prune_fonce: str = REF_PRUNE_FONCE
    rose_pale: str = REF_ROSE_PALE
    rose_grise: str = REF_ROSE_GRISE
    or_bronze: str = REF_OR_BRONZE
    fond_graphique: str = REF_FOND_GRAPHIQUE

    @property
    def series_graphique(self) -> tuple[str, str, str, str]:
        """Ordre des séries des figures, imposé par le lot 0."""
        return (self.primaire, self.or_bronze, self.fond_clair_alt, self.rose_grise)

    @property
    def bandeau_ajuste(self) -> bool:
        """Vrai si la couleur du client a dû être assombrie ou éclaircie."""
        return self.fond_bandeau != self.primaire

    def contraste_bandeau(self) -> float:
        return contraste(self.texte_sur_primaire, self.fond_bandeau)

    def contraste_corps_sur_fond_clair(self) -> float:
        return contraste(self.texte_corps, self.fond_clair)


def construire_palette(
    *, primaire: str = "", secondaire: str = "", fond_clair: str = ""
) -> Palette:
    """Palette complète à partir de ce que le formulaire a fourni.

    Règles de dérivation :

    - une couleur absente ou invalide retombe sur la palette EVKHA, jamais sur
      une valeur au hasard ;
    - le **fond clair** est un mélange de la couleur principale vers le blanc à
      94 %. Il reste donc de la même famille chromatique que la charte du
      client — un prune donne un rosé très pâle, un bleu donne un bleu très
      pâle — au lieu d'un gris universel qui jurerait avec la moitié des
      chartes. Le client peut l'imposer via `fond_clair` s'il a une couleur de
      fond à lui (le crème `#F1EEDB` de Joalie, par exemple, qui n'est PAS un
      dérivé de son prune) ;
    - le **fond alterné** des tableaux est le même mélange à 88 %, soit un ton
      légèrement plus soutenu, comme dans le document de référence ;
    - le **texte sur la couleur principale** est choisi par contraste, pas
      décidé à l'avance.
    """
    principale = normaliser(primaire) if est_une_couleur(primaire) else REF_PRUNE
    accent = normaliser(secondaire) if est_une_couleur(secondaire) else REF_OR_BRONZE
    charte_de_reference = principale == REF_PRUNE

    if est_une_couleur(fond_clair):
        clair = normaliser(fond_clair)
        # Fond de référence imposé : on reprend son alternatif mesuré plutôt
        # qu'un dérivé, qui produirait une teinte voisine mais fausse.
        clair_alt = (
            REF_CREME_ALT if clair == REF_CREME else melanger(clair, principale, 0.06)
        )
    elif charte_de_reference:
        # Charte de référence : on reprend les jetons mesurés, pas des dérivés.
        clair, clair_alt = REF_CREME, REF_CREME_ALT
    else:
        clair = melanger(principale, BLANC, 0.94)
        clair_alt = melanger(principale, BLANC, 0.88)

    bandeau = fond_lisible(principale)

    return Palette(
        primaire=principale,
        secondaire=accent,
        fond_bandeau=bandeau,
        fond_clair=clair,
        fond_clair_alt=clair_alt,
        texte_corps=TEXTE_CORPS,
        texte_sur_primaire=texte_lisible_sur(bandeau),
        texte_legende=TEXTE_LEGENDE,
        prune_fonce=(
            REF_PRUNE_FONCE if charte_de_reference
            else melanger(principale, "#000000", 0.25)
        ),
        rose_pale=(
            REF_ROSE_PALE if charte_de_reference else melanger(principale, BLANC, 0.88)
        ),
        rose_grise=(
            REF_ROSE_GRISE if charte_de_reference else melanger(principale, BLANC, 0.72)
        ),
        or_bronze=accent,
        fond_graphique=REF_FOND_GRAPHIQUE if charte_de_reference else melanger(clair, BLANC, 0.55),
    )


def palette_du_job(job: object) -> Palette:
    """Palette d'un job, lue depuis les variables du formulaire client.

    Réutilise `extract_branding` : les champs Tally (`COULEUR_PRINCIPALE`,
    `COULEUR_SECONDAIRE`) sont déjà normalisés là-bas, et les dupliquer ici
    créerait deux lectures divergentes du même formulaire.
    """
    from ..rendering import extract_branding  # noqa: PLC0415

    marque = extract_branding(job)  # type: ignore[arg-type]
    return construire_palette(
        primaire=marque.color_primary,
        secondaire=marque.color_secondary,
    )

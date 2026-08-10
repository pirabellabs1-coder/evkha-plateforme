"""Schéma typé du socle de données. Toute réponse du modèle est validée ici.

Principe : une réponse invalide déclenche une nouvelle tentative, jamais un
passage en force. C'est la différence de fond avec le moteur actuel, qui
extrait ce qu'il peut de la prose et se tait sur le reste.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import date

from pydantic import BaseModel, Field, model_validator

from core.numbers import to_base_units

from .referentiel import (
    FamilleUnite,
    Fiabilite,
    Perimetre,
    definition,
    identifiants_obligatoires,
    identifiants_pour,
)

# ── Unités canoniques ────────────────────────────────────────────────────────
# La magnitude (k, M, Md) est traitée SÉPARÉMENT de la devise : c'est ce qui
# évite de redéclarer ici la liste des devises de `core/numbers.py`
# (CLAUDE.md, règle 5 : une seule source par vérité).

_DEVISES = ("EUR", "USD", "GBP", "CHF", "XOF", "XAF", "CAD", "AED", "MAD", "TND")
_MAGNITUDES: dict[str, float] = {"": 1.0, "k": 1e3, "M": 1e6, "Md": 1e9}

#: Unités acceptées hors monétaire.
_UNITES_NON_MONETAIRES: dict[FamilleUnite, tuple[str, ...]] = {
    FamilleUnite.POURCENTAGE: ("%",),
    FamilleUnite.EFFECTIF: ("unite", "millier", "million"),
    FamilleUnite.DUREE: ("jours", "mois", "annees"),
    FamilleUnite.RATIO: ("ratio", "note_sur_5", "note_sur_10"),
}


def unites_monetaires() -> tuple[str, ...]:
    """Toutes les combinaisons magnitude × devise, ex. `MdEUR`, `kEUR`, `USD`."""
    return tuple(
        f"{magnitude}{devise}"
        for devise in _DEVISES
        for magnitude in ("", "k", "M", "Md")
    )


#: Symbole d'affichage d'une devise. Seules celles qui en ont un y figurent :
#: le franc CFA s'écrit « FCFA », pas avec un signe, et inventer un symbole
#: serait pire que garder le code.
_SYMBOLE_DEVISE: dict[str, str] = {
    "EUR": "€", "USD": "$", "GBP": "£", "XOF": "FCFA", "XAF": "FCFA",
}

#: Unités non monétaires telles qu'un lecteur les lit.
_UNITE_LISIBLE: dict[str, str] = {
    "unite": "", "millier": "milliers", "million": "millions",
    "annees": "ans", "note_sur_5": "/5", "note_sur_10": "/10", "ratio": "",
}


def unite_lisible(unite: str) -> str:
    """L'unité telle qu'elle doit APPARAÎTRE dans le document.

    `MdEUR` → `Md€`, `MEUR` → `M€`, `kEUR` → `k€`, `annees` → `ans`.

    ## Pourquoi cette fonction existe

    Retour de la cliente du 09/08/2026 : « remplacer les unités techniques comme
    MEUR par des formats plus simples : 6,8 Md€, 1,02 Md€, 600 k€ ».

    `MdEUR` est une notation de STOCKAGE : elle sépare la magnitude de la devise
    pour que les conversions soient possibles sans ambiguïté. Elle n'a aucune
    raison d'atteindre le lecteur — pas plus que le nom d'un identifiant.

    Elle vit ICI, à côté des unités qu'elle traduit, et pas dans le rendu Word :
    la ligne du socle injectée dans le prompt en a besoin AUSSI, sinon le modèle
    recopie `MEUR` dans sa prose et aucun rendu ne le rattrape (règle 5).
    """
    decompose = _decomposer_unite_monetaire(unite)
    if decompose is not None:
        magnitude, devise = decompose
        return f"{magnitude}{_SYMBOLE_DEVISE.get(devise, devise)}"
    return _UNITE_LISIBLE.get(unite, unite)


def unites_autorisees(famille: FamilleUnite) -> tuple[str, ...]:
    if famille is FamilleUnite.MONETAIRE:
        return unites_monetaires()
    return _UNITES_NON_MONETAIRES[famille]


def famille_de_l_unite(unite: str) -> FamilleUnite | None:
    """Famille d'une unité, ou None si l'unité n'est pas reconnue.

    La question « ces chiffres sont-ils des notes ? » se pose au rendu comme à
    la validation. Elle se répond depuis l'unité elle-même, jamais depuis une
    seconde table : dupliquer la correspondance ferait diverger les deux
    lectures (règle 5).
    """
    for famille, unites in _UNITES_NON_MONETAIRES.items():
        if unite in unites:
            return famille
    return FamilleUnite.MONETAIRE if unite in unites_monetaires() else None


def unites_hint(famille: FamilleUnite) -> str:
    """Formulation courte des unités admises, destinée au prompt.

    La liste monétaire complète fait 40 entrées : l'énumérer en entier
    gonflerait le prompt sans rien apprendre au modèle.
    """
    if famille is FamilleUnite.MONETAIRE:
        return "montant — EUR, kEUR, MEUR, MdEUR (ou USD, GBP, CHF, XOF… même forme)"
    # Séparateur virgule, jamais la barre verticale : celle-ci délimite déjà
    # les colonnes de la ligne de référentiel dans le prompt.
    return ", ".join(_UNITES_NON_MONETAIRES[famille])


def _decomposer_unite_monetaire(unite: str) -> tuple[str, str] | None:
    """`MdEUR` -> (`Md`, `EUR`). None si l'unité n'est pas monétaire."""
    for devise in _DEVISES:
        if unite.endswith(devise):
            magnitude = unite[: -len(devise)]
            if magnitude in _MAGNITUDES:
                return magnitude, devise
    return None


def valeur_en_unites_de_base(valeur: float, unite: str) -> tuple[float, str] | None:
    """Ramène un montant à son unité de base. Retourne (valeur, devise).

    None si l'unité n'est pas monétaire : deux grandeurs non monétaires ne se
    comparent pas de la même façon.
    """
    decomposition = _decomposer_unite_monetaire(unite)
    if decomposition is None:
        return None
    magnitude, devise = decomposition
    # `to_base_units` porte la connaissance des magnitudes du pipeline ;
    # on lui délègue plutôt que de refaire la multiplication ici.
    mots = {"": None, "k": None, "M": "millions", "Md": "milliards"}[magnitude]
    base = to_base_units(valeur, mots) if mots else valeur * _MAGNITUDES[magnitude]
    return base, devise


# ── Blocs du socle ───────────────────────────────────────────────────────────


class Zone(BaseModel):
    """Zone géographique de l'étude. `pays` est la seule donnée obligatoire."""

    model_config = {"extra": "forbid"}

    pays: str = Field(min_length=1)
    region: str = ""
    ville: str = ""


class DonneeSocle(BaseModel):
    """Un chiffre de référence, adressable par son identifiant."""

    model_config = {"extra": "forbid"}

    id: str = Field(min_length=1)
    libelle: str = Field(min_length=1)
    valeur: float
    unite: str = Field(min_length=1)
    annee: int = Field(ge=1990, le=2100)
    perimetre: Perimetre
    source: str = ""
    fiabilite: Fiabilite
    #: Identifiants dont cette donnée découle. Vide pour une donnée primaire.
    #: Hypothèse validée le 29/07/2026 : les chiffres dérivés (ratios, seuils,
    #: scénarios) sont autorisés mais doivent déclarer leur filiation, sans quoi
    #: la passe de vérification du lot 4 ne peut pas les distinguer d'une
    #: hallucination.
    derivee_de: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _controler_source(self) -> DonneeSocle:
        if self.fiabilite is Fiabilite.OBSERVEE and not self.source.strip():
            msg = (
                f"`{self.id}` est déclarée observée mais n'a pas de source. "
                "Une donnée observée sans source est une estimation qui s'ignore."
            )
            raise ValueError(msg)
        if self.id in self.derivee_de:
            msg = f"`{self.id}` ne peut pas dériver d'elle-même."
            raise ValueError(msg)
        return self


class SegmentClientele(BaseModel):
    model_config = {"extra": "forbid"}

    nom: str = Field(min_length=1)
    description: str = ""
    besoin_dominant: str = ""
    part_estimee: float | None = Field(default=None, ge=0, le=100)


class Critere(BaseModel):
    """Un axe de notation, défini UNE FOIS pour toute l'étude.

    ## Pourquoi la définition des bornes est obligatoire

    La cliente a demandé « une échelle de notation reproductible de 1 à 5 ».
    Reproductible veut dire qu'un lecteur qui reprend la grille retrouve les
    mêmes notes. Une note sans barème n'est pas une mesure, c'est une opinion
    chiffrée — exactement le « chiffre inventé » que le socle entier existe
    pour empêcher.

    `note_1` et `note_5` sont donc exigés, et un socle qui note sans définir
    est refusé. C'est un coût de reprise assumé : une grille absente rend
    ininterprétables les quarante notes qui en dépendent.
    """

    model_config = {"extra": "forbid"}

    #: Code court cité par les figures (`prix`, `couverture_service`).
    code: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]{1,39}$")
    intitule: str = Field(min_length=1)
    #: Ce que vaut la note la plus basse, puis la plus haute. Le barème.
    note_1: str = Field(min_length=1)
    note_5: str = Field(min_length=1)


class Concurrent(BaseModel):
    """Un acteur de la base consolidée concurrents.

    Les champs suivent le POINT DE CONTRÔLE « BASE CONSOLIDÉE CONCURRENTS » du
    cahier des charges Étude de la concurrence, qui en impose neuf. Le modèle
    n'en portait que quatre — nom, type, positionnement, source — et le chapitre
    6 (estimation des chiffres d'affaires et parts de marché) était donc
    impossible par construction : il exige un CA par acteur, sa méthode
    d'estimation et son niveau de fiabilité, qu'aucun champ ne pouvait recevoir.

    `methode_estimation` est le champ porteur : c'est lui qui rend l'étape
    d'estimation exécutable pour un acteur dont le CA n'est pas publié.
    """

    model_config = {"extra": "forbid"}

    nom: str = Field(min_length=1)
    type: str = "direct"  # direct | indirect
    emplacement: str = ""
    structure: str = ""
    positionnement: str = ""
    site_web: str = ""
    #: Montant + année, ou la mention « non publié ». Jamais un chiffre nu.
    ca_connu: str = ""
    #: D'où vient le CA ci-dessus. Vide si non publié.
    ca_source: str = ""
    #: Comment estimer le CA quand il n'est pas publié : trafic, volume, prix
    #: moyen, nombre de points de vente... C'est l'entrée du chapitre 6.
    methode_estimation: str = ""
    fiabilite: str = ""
    source: str = ""
    #: Note de 1 à 5 par `code` de `Socle.grille_notation`.
    #:
    #: C'est CE champ qui alimente les radars et les cartes de positionnement.
    #: Sans lui, `donnees_graphiques` n'a aucune coordonnée à placer : le
    #: dossier `5892daa5` (10/08/2026) a perdu onze figures sur quinze pour
    #: cette seule raison, et s'est fait bloquer au plancher de figures avec
    #: quatre visuels pour dix-sept attendus.
    notes: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _controler_notes(self) -> Concurrent:
        hors_bornes = sorted(
            code for code, note in self.notes.items() if not 1 <= note <= 5
        )
        if hors_bornes:
            msg = (
                f"{self.nom} : notes hors de l'échelle 1-5 pour "
                f"{', '.join(hors_bornes)}."
            )
            raise ValueError(msg)
        return self


class Tendance(BaseModel):
    model_config = {"extra": "forbid"}

    intitule: str = Field(min_length=1)
    horizon: str = ""
    description: str = ""
    source: str = ""


class Risque(BaseModel):
    model_config = {"extra": "forbid"}

    intitule: str = Field(min_length=1)
    probabilite: int | None = Field(default=None, ge=1, le=5)
    impact: int | None = Field(default=None, ge=1, le=5)
    description: str = ""


class Socle(BaseModel):
    """Racine du socle. Immuable une fois validée (cf. `socle/services.py`)."""

    model_config = {"extra": "forbid"}

    secteur: str = Field(min_length=1)
    zone: Zone
    date_socle: date
    donnees: list[DonneeSocle] = Field(default_factory=list)
    segments_clientele: list[SegmentClientele] = Field(default_factory=list)
    concurrents: list[Concurrent] = Field(default_factory=list)
    tendances: list[Tendance] = Field(default_factory=list)
    risques: list[Risque] = Field(default_factory=list)
    #: Barème commun aux notes portées par les concurrents. Déclaré une fois,
    #: cité par code : c'est la source unique du sens des notes (règle 5).
    grille_notation: list[Critere] = Field(default_factory=list)

    # Champ de travail, non produit par le modèle : renseigné par le validateur
    # pour que les contrôles croisés connaissent le référentiel applicable.
    deliverable_type: str = Field(default="", exclude=True)

    def donnee(self, identifiant: str) -> DonneeSocle | None:
        for item in self.donnees:
            if item.id == identifiant:
                return item
        return None

    @property
    def identifiants(self) -> set[str]:
        return {item.id for item in self.donnees}

    def critere(self, code: str) -> Critere | None:
        for item in self.grille_notation:
            if item.code == code:
                return item
        return None

    def notes_sur(self, codes: Sequence[str]) -> list[tuple[str, list[float]]]:
        """Les concurrents notés sur TOUS ces critères, dans l'ordre demandé.

        Un acteur noté sur trois critères et muet sur le quatrième est écarté :
        le placer avec une coordonnée manquante produirait une figure fausse
        dont chaque note est juste — le défaut que `_harmoniser` évite déjà sur
        les unités.
        """
        retenus: list[tuple[str, list[float]]] = []
        for acteur in self.concurrents:
            if all(code in acteur.notes for code in codes):
                retenus.append(
                    (acteur.nom, [float(acteur.notes[code]) for code in codes])
                )
        return retenus


class SocleInvalideError(ValueError):
    """Le socle produit ne respecte pas le référentiel. Motifs consultables."""

    def __init__(self, motifs: list[str]) -> None:
        self.motifs = motifs
        super().__init__(" ; ".join(motifs))


def valider_socle(socle: Socle, deliverable_type: str) -> list[str]:
    """Contrôles croisés que Pydantic seul ne peut pas faire.

    Retourne la liste des motifs de rejet. Liste vide = socle recevable.
    Ces contrôles portent sur les relations ENTRE données, là où le schéma
    Pydantic ne voit qu'un champ à la fois.
    """
    motifs: list[str] = []
    connus = identifiants_pour(deliverable_type)

    if not connus:
        return [f"Aucun référentiel défini pour le livrable « {deliverable_type} »."]

    # 1. Tout identifiant appartient au référentiel fermé.
    for item in socle.donnees:
        if item.id not in connus:
            motifs.append(
                f"`{item.id}` est hors référentiel. Identifiants admis : "
                f"{', '.join(sorted(connus))}."
            )

    # 2. Aucun doublon : un identifiant ne porte qu'une valeur.
    vus: set[str] = set()
    for item in socle.donnees:
        if item.id in vus:
            motifs.append(f"`{item.id}` apparaît plusieurs fois. Une donnée, une valeur.")
        vus.add(item.id)

    # 3. Les données obligatoires sont présentes.
    manquantes = identifiants_obligatoires(deliverable_type) - socle.identifiants
    for identifiant in sorted(manquantes):
        motifs.append(f"`{identifiant}` est obligatoire et absent du socle.")

    # 4. Périmètre et unité conformes à la définition.
    for item in socle.donnees:
        attendue = definition(deliverable_type, item.id)
        if attendue is None:
            continue  # déjà signalé au point 1
        if item.perimetre != attendue.perimetre:
            motifs.append(
                f"`{item.id}` : périmètre « {item.perimetre} » alors que le "
                f"référentiel impose « {attendue.perimetre} »."
            )
        admises = unites_autorisees(attendue.famille_unite)
        if item.unite not in admises:
            motifs.append(
                f"`{item.id}` : unité « {item.unite} » incompatible avec une "
                f"grandeur {attendue.famille_unite}. Unités admises : "
                f"{', '.join(admises[:8])}…"
            )

    # 5. Toute filiation déclarée pointe vers une donnée présente.
    for item in socle.donnees:
        for parent in item.derivee_de:
            if parent not in socle.identifiants:
                motifs.append(
                    f"`{item.id}` déclare dériver de `{parent}`, absent du socle."
                )

    motifs.extend(_controler_emboitement_marche(socle))
    motifs.extend(_controler_equilibre_financier(socle))
    motifs.extend(_controler_grille_notation(socle))
    return motifs


def _controler_grille_notation(socle: Socle) -> list[str]:
    """Une note n'a de sens que rattachée à un barème déclaré.

    ## Ce qui a rendu ce contrôle nécessaire

    Le dossier `5892daa5` (étude concurrentielle, 10/08/2026) a été bloqué au
    plancher de figures : quatre visuels pour dix-sept attendus, onze abandons
    sur quinze pour « le socle ne porte pas deux [grandeurs] notées » ou « un
    radar exige au moins trois axes ». Le socle décrivait ses onze concurrents
    en texte libre — positionnement, structure, méthode d'estimation — et pas
    une note. Les radars et les cartes de positionnement n'avaient aucune
    coordonnée à placer.

    ## Trois motifs, et pourquoi chacun bloque

    Une note dont le critère n'existe pas est une coordonnée sans axe. Une
    grille sans aucune note est une promesse non tenue, et le lecteur y verrait
    un barème qui ne sert à rien. Un critère noté sur un seul acteur ne compare
    rien : c'est la règle 1 — un contrôle, ou ici une figure, qui n'a rien à
    comparer n'est pas un succès.
    """
    if not socle.grille_notation and not any(a.notes for a in socle.concurrents):
        return []  # Livrable sans notation : rien à contrôler, pas un défaut.

    motifs: list[str] = []
    codes = {critere.code for critere in socle.grille_notation}

    comptes = Counter(critere.code for critere in socle.grille_notation)
    for code in sorted(code for code, n in comptes.items() if n > 1):
        motifs.append(f"Le critère `{code}` est déclaré plusieurs fois dans la grille.")

    for acteur in socle.concurrents:
        inconnus = sorted(set(acteur.notes) - codes)
        if inconnus:
            motifs.append(
                f"{acteur.nom} est noté sur {', '.join(f'`{c}`' for c in inconnus)}, "
                "absent de `grille_notation`. Une note sans critère déclaré ne "
                "peut pas être placée sur une figure ni relue par le client."
            )

    for critere in socle.grille_notation:
        notes = sum(1 for a in socle.concurrents if critere.code in a.notes)
        if notes < 2:
            motifs.append(
                f"Le critère `{critere.code}` ne note que {notes} acteur(s) : "
                "un axe qui ne compare rien n'a pas sa place dans la grille. "
                "Note-le sur tous les concurrents, ou retire-le."
            )

    return motifs


def _controler_equilibre_financier(socle: Socle) -> list[str]:
    """Cohérences arithmétiques d'un prévisionnel. Trois règles, pas plus.

    Les identifiants contrôlés n'existent que dans le référentiel du business
    plan : sur une étude de marché, ces contrôles ne trouvent rien et se
    taisent — comme l'emboîtement TAM/SAM/SOM se tait sur une étude
    concurrentielle.

    La parcimonie est volontaire (leçon des runs 1-3 : chaque règle trop
    stricte a tué des études). Ne sont refusées que des impossibilités
    arithmétiques qu'un lecteur constaterait — pas des choix de scénario :

    - un premier exercice en perte est LÉGITIME (`resultat_net_an1` négatif) ;
    - un chiffre d'affaires qui ne croît pas est un scénario, pas une faute ;
    - la seule vraie exigence d'équilibre porte sur le plan de financement.
    """
    motifs: list[str] = []

    def montant(identifiant: str) -> tuple[float, str] | None:
        item = socle.donnee(identifiant)
        if item is None:
            return None
        return valeur_en_unites_de_base(item.valeur, item.unite)

    # 1. Le plan de financement couvre l'investissement. Tolérance de 2 % :
    #    les arrondis d'un montage réel ne sont pas une incohérence.
    investissement = montant("investissement_total")
    if investissement is not None:
        ressources = [
            r for r in (montant("apport"), montant("emprunt"), montant("autres_ressources"))
            if r is not None
        ]
        devises = {r[1] for r in ressources} | {investissement[1]}
        if ressources and len(devises) == 1:
            total = sum(r[0] for r in ressources)
            if total < investissement[0] * 0.98:
                motifs.append(
                    f"Le plan de financement ne couvre pas l'investissement : "
                    f"{total:,.0f} {investissement[1]} de ressources (apport + "
                    f"emprunt + autres) pour {investissement[0]:,.0f} "
                    f"{investissement[1]} d'emplois. Ajuste l'un ou l'autre, ou "
                    f"déclare la ressource manquante dans `autres_ressources`."
                )

    # 2. Un résultat net ne dépasse jamais le chiffre d'affaires du même
    #    exercice. Quand cela arrive, c'est presque toujours une erreur
    #    d'échelle (k€ contre €) — exactement ce qu'un contrôle attrape mieux
    #    qu'un lecteur.
    for annee in (1, 2, 3):
        ca = montant(f"ca_previsionnel_an{annee}")
        resultat = montant(f"resultat_net_an{annee}")
        if ca is None or resultat is None or ca[1] != resultat[1]:
            continue
        if resultat[0] > ca[0]:
            motifs.append(
                f"`resultat_net_an{annee}` ({resultat[0]:,.0f} {resultat[1]}) "
                f"dépasse `ca_previsionnel_an{annee}` ({ca[0]:,.0f} {ca[1]}) : "
                f"un résultat ne peut pas excéder le chiffre d'affaires. "
                f"Vérifie les échelles."
            )

    # 3. Le seuil de rentabilité reste dans l'ordre de grandeur du
    #    prévisionnel. Au-delà du chiffre d'affaires de l'exercice 3, ce n'est
    #    presque jamais un scénario assumé : c'est une confusion d'unités.
    seuil = montant("seuil_rentabilite")
    ca3 = montant("ca_previsionnel_an3")
    if seuil is not None and ca3 is not None and seuil[1] == ca3[1] and seuil[0] > ca3[0]:
        motifs.append(
            f"`seuil_rentabilite` ({seuil[0]:,.0f} {seuil[1]}) dépasse "
            f"`ca_previsionnel_an3` ({ca3[0]:,.0f} {ca3[1]}) : l'activité "
            f"n'atteindrait jamais son point mort sur l'horizon du plan. "
            f"Vérifie les échelles, ou assume ce scénario dans le libellé."
        )

    return motifs


def _controler_emboitement_marche(socle: Socle) -> list[str]:
    """TAM ≥ SAM ≥ SOM, et marché mondial ≠ marché continental.

    Ce contrôle existe parce que les deux défauts qu'il attrape ont été
    réellement constatés sur le pipeline actuel : « TAM, SAM et SOM
    incohérents » (run 010e3bf2) et la confusion mondial/continental, qui a
    imposé une consigne de rédaction dédiée dans le prompt du chapitre 1.
    """
    motifs: list[str] = []

    def montant(identifiant: str) -> tuple[float, str] | None:
        item = socle.donnee(identifiant)
        if item is None:
            return None
        return valeur_en_unites_de_base(item.valeur, item.unite)

    couples = (("tam", "sam"), ("sam", "som"))
    for grand, petit in couples:
        a, b = montant(grand), montant(petit)
        if a is None or b is None:
            continue
        if a[1] != b[1]:
            motifs.append(
                f"`{grand}` et `{petit}` sont exprimés dans deux devises "
                f"différentes ({a[1]} et {b[1]}) : ils ne sont pas comparables."
            )
            continue
        if b[0] > a[0]:
            motifs.append(
                f"`{petit}` ({b[0]:,.0f} {b[1]}) dépasse `{grand}` "
                f"({a[0]:,.0f} {a[1]}). L'emboîtement TAM ≥ SAM ≥ SOM est rompu."
            )

    mondial, continental = montant("marche_mondial_taille"), montant("marche_continental_taille")
    if mondial and continental and mondial[1] == continental[1]:
        if continental[0] > mondial[0]:
            motifs.append(
                "`marche_continental_taille` dépasse `marche_mondial_taille` : "
                "un continent ne peut pas être plus grand que le monde."
            )
        elif continental[0] == mondial[0]:
            motifs.append(
                "`marche_continental_taille` est identique à "
                "`marche_mondial_taille`. Ce sont deux périmètres distincts : "
                "c'est la confusion que le socle doit précisément empêcher."
            )
    return motifs

"""Les chiffres qui se DÉDUISENT ne s'écrivent plus : ils se calculent, une fois.

## Le défaut, mesuré sur un business plan réel

12/08/2026, retour de la cliente sur un dossier qu'elle venait de relire :

    seuil_rentabilite : 27 600 € au ch. 0 ; 18 667 € au ch. 2 ; 18 667 € au
    ch. 9 ; 18 667 € au ch. 12 ; 35 609 € au ch. 14 ; 54 276 € au ch. 15 ;
    18 667 € au ch. 15 ; 101 772 € au ch. 18 ; 18 667 € au ch. 18 ; 32 048 €
    au ch. 18 ; 18 667 € au ch. 19 ; 18 667 € au ch. 21

Douze mentions, six valeurs. Sept disent 18 667 € : le rédacteur n'est pas
incohérent par nature — il REFAIT le calcul à chaque chapitre, sans savoir
qu'il l'a déjà fait, et il dérive.

Le contrôle attrapait ces écarts APRÈS coup, les passes de correction
réécrivaient les chapitres, et la facture passait de 3,50 € à 5 €. On payait
pour rattraper ce qu'une division aurait donné exactement, gratuitement, avant
la première ligne.

## Ce que ce module fait, et ce qu'il refuse de faire

Un seuil de rentabilité est une DIVISION : charges fixes ÷ taux de marge. Ce
n'est pas de la rédaction, et un modèle de langage n'a rien à y apporter. Le
calcul est ici : exact, identique partout, instantané, sans un jeton.

Il ne dérive QUE des identités — des égalités vraies par définition. Beaucoup
de rapports entre les chiffres d'un dossier sont des estimations déguisées
(« le chiffre d'affaires, c'est la clientèle cible multipliée par le panier
moyen » suppose que chaque prospect achète une fois et une seule). Les
calculer donnerait à une hypothèse l'autorité du code, ce qui est pire qu'un
chiffre absent — c'est la règle 2 du dépôt, appliquée à l'arithmétique.

Deux rôles, donc, et le second compte autant que le premier :

- COMBLER un terme manquant quand tous les autres sont là ;
- VÉRIFIER l'identité quand tous les termes sont là, et signaler la
  contradiction AVANT le premier chapitre. Un socle qui se contredit produit
  vingt-deux chapitres qui se contredisent.

## Pourquoi seuls les identifiants du référentiel sont produits

Une donnée absente du référentiel est « hors socle » : les chapitres n'ont pas
le droit de la citer, et le contrôle la refuse. Fabriquer un identifiant que
personne n'attend reviendrait à alimenter le défaut qu'on répare.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .referentiel import identifiants_pour
from .schema import DonneeSocle, Fiabilite, Socle, valeur_en_unites_de_base

#: Écart relatif toléré avant de parler de contradiction.
#:
#: Deux pour cent : un plan d'affaires arrondit ses montants, et exiger
#: l'égalité au centime ferait crier sur « 18 667 » contre « 18 700 » — un
#: motif que personne ne peut corriger sans dégrader la lisibilité. Au-delà,
#: ce n'est plus un arrondi, c'est un autre calcul.
TOLERANCE = 0.02


@dataclass(frozen=True)
class Identite:
    """Une égalité vraie par définition, entre identifiants du référentiel."""

    #: L'identifiant que cette identité sait produire.
    produit: str
    #: Ceux dont il découle. Tous requis.
    depuis: tuple[str, ...]
    #: Le calcul, sur des valeurs déjà ramenées à leur unité de base.
    calcul: Callable[[dict[str, float]], float | None]
    #: La formule, écrite pour un lecteur. Part dans `libelle` — c'est elle qui
    #: rend le chiffre défendable devant un banquier.
    formule: str
    #: L'unité du résultat. `""` reprend celle du premier terme de `depuis`.
    unite: str = ""
    #: Les livrables concernés. Vide = tous ceux dont le référentiel a les
    #: identifiants.
    livrables: tuple[str, ...] = field(default_factory=tuple)


def _seuil_de_rentabilite(v: dict[str, float]) -> float | None:
    """Charges fixes ÷ taux de marge brute.

    Le taux arrive en pourcentage : un taux nul ou négatif n'a pas d'inverse,
    et un seuil de rentabilité n'existe alors pas — on ne rend rien plutôt
    qu'une division par zéro déguisée en chiffre.
    """
    taux = v["marge_brute_taux"] / 100.0
    if taux <= 0:
        return None
    return v["charges_fixes_an1"] / taux


def _ressources_complementaires(v: dict[str, float]) -> float | None:
    """Ce qu'il reste à financer une fois l'apport et l'emprunt posés.

    Identité du plan de financement : besoins = ressources. Un montant négatif
    signifie que le plan est SUR-financé — ce n'est pas une ressource
    complémentaire, c'est une erreur de saisie ou un excédent à expliquer. On
    ne le maquille pas en zéro.
    """
    reste = v["investissement_total"] + v["bfr"] - v["apport"] - v["emprunt"]
    return reste if reste >= 0 else None


def _transactions_annuelles(v: dict[str, float]) -> float | None:
    """Clientèle cible × fréquence d'achat. Vrai par définition des deux."""
    return v["taille_clientele_cible"] * v["frequence_achat"]


#: Les identités connues. Courtes et sûres plutôt que nombreuses et douteuses.
IDENTITES: tuple[Identite, ...] = (
    Identite(
        produit="seuil_rentabilite",
        depuis=("charges_fixes_an1", "marge_brute_taux"),
        calcul=_seuil_de_rentabilite,
        formule=(
            "seuil de rentabilité = charges fixes de l'exercice 1 ÷ taux de "
            "marge brute"
        ),
        livrables=("business_plan",),
    ),
    Identite(
        produit="autres_ressources",
        depuis=("investissement_total", "bfr", "apport", "emprunt"),
        calcul=_ressources_complementaires,
        formule=(
            "ressources complémentaires = (investissement total + besoin en "
            "fonds de roulement) − apport − emprunt ; le plan de financement "
            "s'équilibre"
        ),
        livrables=("business_plan",),
    ),
    Identite(
        produit="transactions_annuelles_cible",
        depuis=("taille_clientele_cible", "frequence_achat"),
        calcul=_transactions_annuelles,
        formule=(
            "transactions annuelles = clientèle cible × fréquence d'achat "
            "annuelle"
        ),
        livrables=("market_study",),
    ),
)


@dataclass(frozen=True)
class Contradiction:
    """Une identité que le socle viole. Nommée pour être corrigée."""

    identifiant: str
    valeur_du_socle: float
    valeur_calculee: float
    unite: str
    formule: str

    def __str__(self) -> str:
        ecart = abs(self.valeur_du_socle - self.valeur_calculee)
        return (
            f"`{self.identifiant}` vaut {self.valeur_du_socle:,.0f} {self.unite} "
            f"dans le socle, mais {self.formule} donne "
            f"{self.valeur_calculee:,.0f} {self.unite} "
            f"(écart de {ecart:,.0f}). Corrige l'un des deux : un chiffre "
            "qui ne découle pas de ses propres termes ne tiendra pas devant "
            "un lecteur qui refait l'addition."
        )


def _valeurs_de_base(socle: Socle, identifiants: tuple[str, ...]) -> dict[str, float] | None:
    """Les valeurs demandées, ramenées à leur unité de base. None si l'une manque.

    Un pourcentage n'est pas monétaire : il se prend tel quel. Un montant se
    ramène à sa devise de base — sans quoi « 18 k€ » et « 18 000 € » seraient
    deux chiffres différents.
    """
    par_id = {d.id: d for d in socle.donnees}
    sortie: dict[str, float] = {}
    for identifiant in identifiants:
        donnee = par_id.get(identifiant)
        if donnee is None:
            return None
        base = valeur_en_unites_de_base(donnee.valeur, donnee.unite)
        sortie[identifiant] = donnee.valeur if base is None else base[0]
    return sortie


def _unite_du_resultat(socle: Socle, identite: Identite) -> str:
    """L'unité du premier terme, sauf si l'identité en impose une."""
    if identite.unite:
        return identite.unite
    par_id = {d.id: d for d in socle.donnees}
    premier = par_id.get(identite.depuis[0])
    if premier is None:
        return ""
    base = valeur_en_unites_de_base(premier.valeur, premier.unite)
    return base[1] if base is not None else premier.unite


def appliquer(
    socle: Socle, deliverable_type: str
) -> tuple[list[DonneeSocle], list[Contradiction]]:
    """Complète le socle par calcul, et signale ce qui se contredit.

    Retourne `(données ajoutées, contradictions)`. Ne modifie pas le socle reçu :
    l'appelant décide quoi en faire, et un calcul qui réécrirait silencieusement
    un chiffre du client serait exactement ce qu'on veut éviter.
    """
    connus = identifiants_pour(deliverable_type)
    par_id = {d.id: d for d in socle.donnees}
    ajoutees: list[DonneeSocle] = []
    contradictions: list[Contradiction] = []

    for identite in IDENTITES:
        if identite.livrables and deliverable_type not in identite.livrables:
            continue
        # Un identifiant absent du référentiel serait « hors socle » : aucun
        # chapitre n'aurait le droit de le citer.
        if identite.produit not in connus:
            continue

        valeurs = _valeurs_de_base(socle, identite.depuis)
        if valeurs is None:
            continue
        calculee = identite.calcul(valeurs)
        if calculee is None:
            continue

        unite = _unite_du_resultat(socle, identite)
        existante = par_id.get(identite.produit)

        if existante is None:
            ajoutees.append(DonneeSocle(
                id=identite.produit,
                libelle=f"Calculé : {identite.formule}.",
                valeur=round(calculee, 2),
                unite=unite,
                annee=socle.date_socle.year,
                perimetre=socle.donnees[0].perimetre if socle.donnees else "national",
                # ESTIMEE, jamais OBSERVEE : le chiffre est exact au regard de
                # ses termes, mais il vaut ce que valent ces termes. Le
                # présenter comme observé lui prêterait une autorité qu'il n'a
                # pas (règle 2).
                fiabilite=Fiabilite.ESTIMEE,
                derivee_de=list(identite.depuis),
            ))
            continue

        base = valeur_en_unites_de_base(existante.valeur, existante.unite)
        valeur_socle = existante.valeur if base is None else base[0]
        reference = max(abs(calculee), 1.0)
        if abs(valeur_socle - calculee) / reference > TOLERANCE:
            contradictions.append(Contradiction(
                identifiant=identite.produit,
                valeur_du_socle=valeur_socle,
                valeur_calculee=calculee,
                unite=unite,
                formule=identite.formule,
            ))

    return ajoutees, contradictions

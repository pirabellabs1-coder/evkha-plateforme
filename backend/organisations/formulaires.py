"""Les quatre questionnaires EVKHA, repris des formulaires Tally (§9.3).

Source unique : c'est le serveur qui déclare les questions, l'interface se
contente de les afficher. Redéclarer les champs côté React les ferait diverger
au premier ajout de question, et c'est le défaut récurrent de ce dépôt
(règle 5). C'est aussi ce que demande le §10.3 : « un formulaire propre à chaque
type de document », modifiable sans redéploiement de l'interface.

## Fidélité aux formulaires Tally

Les intitulés sont repris **mot pour mot**. La note d'introduction aussi : elle
dit au client qu'un champ vide vaut « Je ne sais pas encore », et que plus le
formulaire est complet, plus l'étude est ciblée. Reformuler ces questions
reviendrait à changer la matière que le moteur reçoit — or les trames ont été
écrites pour ces réponses-là.

## Correspondance avec le moteur

Chaque champ porte l'identifiant de la **variable de prompt** qu'il alimente
(`SECTEUR`, `PROJET`, `CONCURRENTS`…). Ce sont ces noms que les trames
interpolent ; un champ dont l'identifiant ne correspond à rien n'atteindrait
jamais le modèle.

Les pièces jointes ne sont pas gérées ici : les questionnaires Tally demandent
déjà de **résumer** les documents en texte (« Merci de résumer vos études de
marché ou tout autre document »), et c'est ce résumé que le moteur exploite. Le
dépôt de fichiers reste à faire.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from catalog.models import DeliverableType


@dataclass(frozen=True)
class Champ:
    """Une question. `identifiant` est le nom de la variable de prompt."""

    identifiant: str
    libelle: str
    obligatoire: bool = False
    #: `texte` (une ligne), `zone` (plusieurs lignes), `nombres` (suite de
    #: valeurs séparées par des virgules, comme le demandent les formulaires
    #: financiers).
    type: str = "texte"
    aide: str = ""
    exemple: str = ""


@dataclass(frozen=True)
class Section:
    titre: str
    champs: tuple[Champ, ...]
    introduction: str = ""


@dataclass(frozen=True)
class Formulaire:
    type_document: str
    titre: str
    note: str
    sections: tuple[Section, ...] = field(default_factory=tuple)

    @property
    def champs(self) -> tuple[Champ, ...]:
        return tuple(champ for section in self.sections for champ in section.champs)

    @property
    def obligatoires(self) -> tuple[str, ...]:
        return tuple(c.identifiant for c in self.champs if c.obligatoire)


#: Note d'introduction commune, reprise des quatre formulaires Tally.
NOTE = (
    "Ce questionnaire a été conçu pour aider EVKHA à mieux comprendre votre "
    "projet et à construire un dossier complet, solide et aligné avec vos "
    "ambitions.\n\n"
    "Si vous ne pouvez pas répondre à tout, laissez les champs vides ou "
    "indiquez « Je ne sais pas encore » ou « À définir ».\n\n"
    "Sachez que plus le formulaire sera complet, plus votre étude sera ciblée "
    "sur vos attentes."
)

# ── Blocs communs ────────────────────────────────────────────────────────────
# Les quatre questionnaires ouvrent sur la même identification. La déclarer une
# fois évite qu'un intitulé change dans trois formulaires sur quatre.

_IDENTIFICATION = (
    Champ("PROJET", "Nom du projet ou de l'entreprise", obligatoire=True),
    Champ("SECTEUR", "Secteur d'activité", obligatoire=True),
    Champ("PAYS", "Pays", obligatoire=True),
    Champ("ZONE", "Ville ou zone géographique", obligatoire=True),
)

_DOCUMENTS = Champ(
    "ELEMENTS_A_RETENIR",
    "Disposez-vous de données ou documents internes à partager pour enrichir "
    "l'étude ? (retours clients, historique de ventes, site web, études déjà "
    "réalisées, présentation…)",
    obligatoire=True,
    type="zone",
    aide="Si oui, merci de résumer ici le contenu de ces documents.",
)


# ── Étude de marché ──────────────────────────────────────────────────────────

ETUDE_DE_MARCHE = Formulaire(
    type_document=DeliverableType.MARKET_STUDY.value,
    titre="Questionnaire — Étude de marché",
    note=NOTE,
    sections=(
        Section("Informations générales", _IDENTIFICATION),
        Section(
            "Description de votre projet ou activité",
            (
                Champ(
                    "DESCRIPTION_PROJET",
                    "Pouvez-vous décrire en détail votre projet ou "
                    "produit/service concerné par l'étude ?",
                    obligatoire=True,
                    type="zone",
                ),
                Champ(
                    "POSITIONNEMENT",
                    "Quel est le positionnement que vous souhaitez pour ce "
                    "projet ou produit ?",
                    obligatoire=True,
                    type="zone",
                    exemple="haut de gamme, accessible, innovant, low cost…",
                ),
                Champ(
                    "POINTS_FORTS",
                    "Quels sont, selon vous, les principaux avantages ou points "
                    "forts de votre produit/service ?",
                    obligatoire=True,
                    type="zone",
                ),
            ),
        ),
        Section(
            "Votre public cible",
            (
                Champ(
                    "CLIENTELE_CIBLE",
                    "Selon vous, qui sont vos clients cibles ?",
                    obligatoire=True,
                    type="zone",
                    exemple="âge, profession, localisation, besoins spécifiques",
                ),
                Champ(
                    "ZONE_CIBLE",
                    "Quelle est votre zone géographique cible ?",
                    obligatoire=True,
                    type="zone",
                    exemple="locale, nationale, internationale — précisez les "
                    "régions ou pays",
                ),
            ),
        ),
        Section(
            "Concurrence",
            (
                Champ(
                    "CONCURRENTS",
                    "Selon vous, quels sont les concurrents que vous avez "
                    "identifiés dans ce domaine ?",
                    obligatoire=True,
                    type="zone",
                ),
                Champ(
                    "DIFFERENCIATION",
                    "En quoi pensez-vous que votre produit ou service se "
                    "distingue de ceux de vos concurrents ?",
                    obligatoire=True,
                    type="zone",
                ),
            ),
        ),
        Section(
            "Résultats attendus",
            (
                Champ(
                    "RESULTATS_ATTENDUS",
                    "Quels résultats attendez-vous de cette étude ?",
                    obligatoire=True,
                    type="zone",
                ),
                Champ(
                    "DEMANDES_SPECIFIQUES",
                    "Quelles sont les questions les plus importantes pour vous, "
                    "auxquelles l'étude doit répondre ?",
                    obligatoire=True,
                    type="zone",
                    exemple="recommandations stratégiques, chiffres, clientèle, "
                    "analyse du marché, segmentation client, prévisions de ventes…",
                ),
                _DOCUMENTS,
            ),
        ),
    ),
)


# ── Étude de la concurrence ──────────────────────────────────────────────────

ETUDE_DE_CONCURRENCE = Formulaire(
    type_document=DeliverableType.COMPETITOR_STUDY.value,
    titre="Questionnaire — Étude de la concurrence",
    note=NOTE,
    sections=(
        Section(
            "Votre entreprise",
            (
                Champ(
                    "PROJET",
                    "Nom de l'entreprise (ou future) qui sera étudiée",
                    obligatoire=True,
                ),
                Champ("SECTEUR", "Secteur et domaine d'activité", obligatoire=True),
                Champ("PAYS", "Pays", obligatoire=True),
                Champ("ZONE", "Ville ou zone géographique", obligatoire=True),
                Champ(
                    "STADE_ACTUEL",
                    "À quel stade êtes-vous lorsque vous réalisez cette étude ?",
                    obligatoire=True,
                    exemple="en lancement, entreprise déjà créée…",
                ),
            ),
        ),
        Section(
            "Description de votre projet ou activité",
            (
                Champ(
                    "DESCRIPTION_PROJET",
                    "Pouvez-vous décrire en détail votre projet ou "
                    "produit/service concerné par l'étude ?",
                    obligatoire=True,
                    type="zone",
                ),
                Champ(
                    "POSITIONNEMENT",
                    "Quel est le positionnement que vous souhaitez pour ce "
                    "projet ou produit ?",
                    obligatoire=True,
                    type="zone",
                    exemple="haut de gamme, accessible, innovant, low cost…",
                ),
                Champ(
                    "POINTS_FORTS",
                    "Quels sont, selon vous, les principaux avantages ou points "
                    "forts de votre produit/service ?",
                    obligatoire=True,
                    type="zone",
                ),
            ),
        ),
        Section(
            "Votre public cible",
            (
                Champ(
                    "CLIENTELE_CIBLE",
                    "Selon vous, qui sont vos clients cibles ?",
                    obligatoire=True,
                    type="zone",
                    exemple="âge, profession, localisation, besoins spécifiques",
                ),
                Champ(
                    "ZONE_CIBLE",
                    "Quelle est votre zone géographique cible, et sur quelle "
                    "zone souhaitez-vous travailler ?",
                    obligatoire=True,
                    type="zone",
                ),
            ),
        ),
        Section(
            "Concurrence",
            (
                Champ(
                    "CONCURRENTS",
                    "Selon vous, quels sont les concurrents que vous avez "
                    "identifiés dans ce domaine ?",
                    obligatoire=True,
                    type="zone",
                ),
                Champ(
                    "DIFFERENCIATION",
                    "En quoi votre produit ou service se distingue-t-il de ceux "
                    "de vos concurrents ? Quelle est votre valeur ajoutée ?",
                    obligatoire=True,
                    type="zone",
                ),
            ),
        ),
        Section(
            "Résultats attendus",
            (
                Champ(
                    "DEMANDES_SPECIFIQUES",
                    "Quelles sont les questions les plus importantes pour vous, "
                    "auxquelles l'étude doit répondre ?",
                    obligatoire=True,
                    type="zone",
                    exemple="recommandations stratégiques, chiffres, "
                    "différenciation…",
                ),
                Champ(
                    "RESULTATS_ATTENDUS",
                    "Quels résultats attendez-vous de cette étude ?",
                    obligatoire=True,
                    type="zone",
                ),
                _DOCUMENTS,
            ),
        ),
    ),
)


# ── Business plan ────────────────────────────────────────────────────────────

BUSINESS_PLAN = Formulaire(
    type_document=DeliverableType.BUSINESS_PLAN.value,
    titre="Questionnaire — Business plan",
    note=NOTE,
    sections=(
        Section(
            "Informations générales",
            (
                *_IDENTIFICATION,
                Champ("PORTEUR_PROJET", "Nom du porteur de projet", obligatoire=True),
                Champ(
                    "PARCOURS_PORTEUR",
                    "Parcours pour l'histoire du projet, tranche d'âge",
                    obligatoire=True,
                    type="zone",
                ),
                Champ(
                    "CONTACT_PRO",
                    "Contact professionnel : téléphone, mail, site, réseaux sociaux",
                    obligatoire=True,
                    type="zone",
                ),
                Champ(
                    "DATE_CREATION",
                    "Date de création prévue / statut actuel",
                    obligatoire=True,
                ),
            ),
        ),
        Section(
            "Résumé exécutif",
            (
                Champ(
                    "RESUME_EXECUTIF",
                    "En une phrase, quelle est l'ambition principale du projet ? "
                    "Quel est l'objectif à atteindre dans les 12 premiers mois ? "
                    "Quelle est la promesse forte du projet (proposition de "
                    "valeur) ? Pourquoi maintenant est-il le bon moment ?",
                    obligatoire=True,
                    type="zone",
                    aide="Répondez aux quatre questions à la suite.",
                ),
            ),
        ),
        Section(
            "Présentation de l'offre",
            (
                Champ(
                    "OFFRE",
                    "Décrivez vos produits / services principaux (gammes, "
                    "options, exemples). Quelle est votre offre phare ? À quel "
                    "besoin concret répond-elle ? Qu'est-ce qui rend votre "
                    "solution unique ? Avez-vous prévu des offres premium, "
                    "options, abonnements ?",
                    obligatoire=True,
                    type="zone",
                ),
            ),
        ),
        Section(
            "Étude de marché et concurrence",
            (
                Champ(
                    "TENDANCES_MARCHE",
                    "Quelles tendances actuelles influencent votre marché ?",
                    obligatoire=True,
                    type="zone",
                ),
                Champ(
                    "CONCURRENTS",
                    "Qui sont vos principaux concurrents ?",
                    obligatoire=True,
                    type="zone",
                ),
            ),
        ),
        Section(
            "Cible et positionnement",
            (
                Champ(
                    "CLIENTELE_CIBLE",
                    "Qui sont vos clients cibles ? (âge, catégorie, besoins, "
                    "habitudes)",
                    obligatoire=True,
                    type="zone",
                ),
                Champ(
                    "POSITIONNEMENT",
                    "Quelle est votre zone géographique principale ? Par quels "
                    "canaux touchez-vous vos clients ? Quel est votre "
                    "positionnement prix (entrée de gamme, premium, accessible…) ?",
                    obligatoire=True,
                    type="zone",
                ),
            ),
        ),
        Section(
            "Stratégie marketing et commerciale",
            (
                Champ(
                    "STRATEGIE_COMMERCIALE",
                    "Quels sont vos canaux d'acquisition envisagés ? Prévoyez-vous "
                    "des campagnes (SEO, Google Ads, réseaux sociaux, "
                    "partenariats) ? Des actions en événementiel, "
                    "bouche-à-oreille, presse locale ? Comment fidélisez-vous "
                    "vos clients ?",
                    obligatoire=True,
                    type="zone",
                ),
                Champ(
                    "MOTIVATIONS",
                    "Pourquoi ce projet ? Quelles ont été et quelles sont vos "
                    "motivations ?",
                    obligatoire=True,
                    type="zone",
                ),
            ),
        ),
        Section(
            "Organisation et équipe",
            (
                Champ(
                    "EQUIPE",
                    "Qui est impliqué dans le projet actuellement (fonctions, "
                    "associés, freelances) ? Prévoyez-vous de recruter ou de "
                    "collaborer avec des prestataires ? Êtes-vous accompagné par "
                    "un réseau (CCI, BGE, Initiative…) ?",
                    obligatoire=True,
                    type="zone",
                ),
            ),
        ),
        Section(
            "Modèle économique et sources de revenus",
            (
                Champ(
                    "MODELE_REVENUS",
                    "Quelles sont vos différentes sources de revenus envisagées ? "
                    "Quel est votre panier moyen estimé ? Vendez-vous à l'unité, "
                    "en abonnement, en formule ? Proposez-vous des ventes en "
                    "ligne ?",
                    obligatoire=True,
                    type="zone",
                ),
            ),
        ),
        Section(
            "Objectifs de croissance et vision",
            (
                Champ(
                    "OBJECTIF_STRATEGIQUE",
                    "Où souhaitez-vous être dans 1 an ? Dans 3 ans ? Avez-vous "
                    "une stratégie d'évolution prévue ? Quels nouveaux services "
                    "comptez-vous développer ? En quoi votre projet est-il "
                    "durable ou à impact positif ?",
                    obligatoire=True,
                    type="zone",
                ),
            ),
        ),
        Section(
            "Besoins financiers et prévisions",
            (
                Champ(
                    "INVESTISSEMENT_TOTAL",
                    "Quel est le budget total estimé pour lancer / développer le "
                    "projet ? Vos besoins détaillés, les montants et les "
                    "ressources pour les financer",
                    type="nombres",
                    aide="Écrivez les valeurs dans l'ordre chronologique, "
                    "séparées par des virgules.",
                ),
                Champ(
                    "APPORT",
                    "De quels apports disposez-vous ? (apport personnel, love "
                    "money, prêt…) De quelles aides ou financements externes "
                    "allez-vous bénéficier ? Souhaitez-vous vous verser un "
                    "salaire ou avoir des employés, à quel montant ? Quels sont "
                    "vos postes de dépenses majeurs ?",
                    obligatoire=True,
                    type="zone",
                    aide="Écrivez les valeurs dans l'ordre chronologique, "
                    "séparées par des virgules.",
                ),
                Champ(
                    "CA_PREVISIONNEL",
                    "Quelle est votre estimation de chiffre d'affaires la "
                    "première année, et son évolution estimée sur 5 ans ? "
                    "Pourquoi ce calcul ?",
                    type="nombres",
                    aide="Écrivez les valeurs dans l'ordre chronologique, "
                    "séparées par des virgules.",
                ),
                Champ(
                    "TABLEAUX_FINANCIERS",
                    "Si vous avez réalisé un tableau prévisionnel (compte de "
                    "résultat, seuil de rentabilité), copiez-le ici. Sinon, "
                    "indiquez : RÉSULTAT NET PRÉVISIONNEL, EBE PRÉVISIONNEL, "
                    "TAUX D'OCCUPATION, SEUIL DE RENTABILITÉ, VERTICALES "
                    "D'ACTIVITÉS",
                    obligatoire=True,
                    type="zone",
                    aide="Recopiez chaque intitulé suivi de sa valeur. Exemple : "
                    "RÉSULTAT NET PRÉVISIONNEL : 10 000, EBE PRÉVISIONNEL : 2 500…",
                ),
            ),
        ),
        Section(
            "Annexes et informations supplémentaires",
            (
                Champ(
                    "ELEMENTS_A_RETENIR",
                    "Avez-vous des visuels, études, tableaux, présentations "
                    "existants ? Souhaitez-vous une version investisseur (levée "
                    "de fonds ou banque) ou institutionnelle (Initiative, BPI, "
                    "BGE…) ? D'autres éléments à faire figurer ?",
                    obligatoire=True,
                    type="zone",
                    aide="Merci de résumer vos études de marché ou tout autre "
                    "document si vous en avez.",
                ),
            ),
        ),
    ),
)


# ── Stratégie d'entreprise ───────────────────────────────────────────────────

STRATEGIE = Formulaire(
    type_document=DeliverableType.BUSINESS_STRATEGY.value,
    titre="Questionnaire — Stratégie business",
    note=(
        "Ce questionnaire a été conçu pour aider EVKHA à mieux comprendre votre "
        "entreprise et à construire une stratégie business solide, cohérente et "
        "réellement alignée avec votre situation actuelle et vos ambitions.\n\n"
        "Contrairement à une étude de marché qui regarde l'extérieur, la "
        "stratégie business regarde votre entreprise de l'intérieur : votre "
        "modèle, vos offres, votre rentabilité, votre organisation, vos "
        "priorités.\n\n"
        "Si vous ne pouvez pas répondre à tout, laissez les champs vides ou "
        "indiquez « Je ne sais pas encore » ou « À définir ». Plus le formulaire "
        "sera complet, plus votre stratégie sera ciblée sur vos enjeux réels."
    ),
    sections=(
        Section(
            "Votre entreprise",
            (
                Champ(
                    "PROJET",
                    "Nom de l'entreprise concernée par la stratégie",
                    obligatoire=True,
                ),
                Champ("SECTEUR", "Secteur et domaine d'activité", obligatoire=True),
                Champ("PAYS", "Pays", obligatoire=True),
                Champ("ZONE", "Ville ou zone géographique", obligatoire=True),
                Champ(
                    "STADE_ACTUEL",
                    "Depuis combien de temps l'entreprise existe-t-elle ? À quel "
                    "stade vous situez-vous aujourd'hui ?",
                    obligatoire=True,
                    type="zone",
                    exemple="début d'activité, en structuration, en croissance, "
                    "en repositionnement, en transition",
                ),
            ),
        ),
        Section(
            "Votre modèle économique actuel",
            (
                Champ(
                    "MODELE_REVENUS",
                    "Comment votre entreprise génère-t-elle ses revenus "
                    "aujourd'hui ? Décrivez vos principales sources de revenus "
                    "et les prestations que vous vendez.",
                    obligatoire=True,
                    type="zone",
                ),
                Champ(
                    "OFFRE",
                    "Quelles sont vos offres / prestations actuelles ? Lesquelles "
                    "sont les plus rentables ? Lesquelles sont les plus "
                    "chronophages ou peu rentables ?",
                    obligatoire=True,
                    type="zone",
                ),
                Champ(
                    "SAISONNALITE",
                    "Vos revenus sont-ils plutôt réguliers, irréguliers, "
                    "saisonniers, ou imprévisibles ? Pourquoi ?",
                    obligatoire=True,
                    type="zone",
                ),
            ),
        ),
        Section(
            "Votre positionnement et vos clients",
            (
                Champ(
                    "POSITIONNEMENT",
                    "Comment positionnez-vous votre entreprise aujourd'hui ? Qui "
                    "sont réellement vos clients aujourd'hui (profil, secteur, "
                    "taille, besoins) ?",
                    obligatoire=True,
                    type="zone",
                ),
                Champ(
                    "CLIENTELE_CIBLE",
                    "Avez-vous l'impression d'adresser trop de cibles "
                    "différentes, ou d'être bien ciblé ? Sur quels canaux "
                    "attirez-vous actuellement vos clients ?",
                    obligatoire=True,
                    type="zone",
                ),
            ),
        ),
        Section(
            "Votre quotidien de dirigeant",
            (
                Champ(
                    "EQUIPE",
                    "Combien d'heures par semaine consacrez-vous à votre "
                    "entreprise ? Sur quelles tâches passez-vous le plus de "
                    "temps ? Vous sentez-vous dispersé, surchargé, à l'équilibre ? "
                    "L'entreprise peut-elle fonctionner sans vous ? Êtes-vous "
                    "seul ou entouré (équipe, prestataires, associés) ?",
                    obligatoire=True,
                    type="zone",
                ),
            ),
        ),
        Section(
            "Vos ambitions et votre vision",
            (
                Champ(
                    "OBJECTIF_STRATEGIQUE",
                    "Où voulez-vous emmener votre entreprise dans les 12 à 24 "
                    "prochains mois ? Quelle est votre vision à 3-5 ans ? Quel "
                    "est votre rapport au risque ? Avez-vous des contraintes "
                    "spécifiques (temps, budget, famille, santé) ?",
                    obligatoire=True,
                    type="zone",
                ),
            ),
        ),
        Section(
            "Vos enjeux stratégiques",
            (
                Champ(
                    "ENJEUX",
                    "Quels sujets vous préoccupent réellement aujourd'hui ?",
                    obligatoire=True,
                    type="zone",
                    exemple="clarifier mon positionnement, mieux structurer mes "
                    "offres, augmenter ma rentabilité, réduire ma charge de "
                    "travail, attirer de meilleurs clients, préparer une montée "
                    "en gamme, industrialiser, diversifier mes revenus, "
                    "stabiliser mon activité…",
                ),
                Champ(
                    "DEMANDES_SPECIFIQUES",
                    "Si vous deviez résumer en une phrase la question "
                    "stratégique principale à laquelle cette stratégie doit "
                    "répondre, ce serait :",
                    obligatoire=True,
                    type="zone",
                    exemple="« Comment passer de prestataire débordée à "
                    "dirigeante d'un business scalable ? »",
                ),
                _DOCUMENTS,
            ),
        ),
    ),
)


FORMULAIRES: dict[str, Formulaire] = {
    formulaire.type_document: formulaire
    for formulaire in (ETUDE_DE_MARCHE, ETUDE_DE_CONCURRENCE, BUSINESS_PLAN, STRATEGIE)
}


def formulaire(type_document: str) -> Formulaire | None:
    return FORMULAIRES.get(type_document)


def en_dict(formulaire_demande: Formulaire) -> dict[str, Any]:
    """Formulaire sérialisé pour l'interface."""
    return {
        "type": formulaire_demande.type_document,
        "titre": formulaire_demande.titre,
        "note": formulaire_demande.note,
        "sections": [
            {
                "titre": section.titre,
                "introduction": section.introduction,
                "champs": [
                    {
                        "identifiant": champ.identifiant,
                        "libelle": champ.libelle,
                        "obligatoire": champ.obligatoire,
                        "type": champ.type,
                        "aide": champ.aide,
                        "exemple": champ.exemple,
                    }
                    for champ in section.champs
                ],
            }
            for section in formulaire_demande.sections
        ],
    }

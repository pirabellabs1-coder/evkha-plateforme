"""Construction du prompt de la passe 1 : produire le socle, rien d'autre.

Aucune rédaction n'est demandée. Le modèle ne remplit que des emplacements
déclarés dans le référentiel : c'est ce qui rend la sortie contrôlable.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import date

from catalog.models import DeliverableType

from .referentiel import DefinitionDonnee, definitions_pour
from .schema import unites_hint

# Base consolidée concurrents — POINT DE CONTRÔLE du cahier des charges
# « Étude de la concurrence ». Neuf colonnes imposées, et la sélection est figée
# à 8 acteurs directs + 3 indirects.
#
# `methode_estimation` est le champ qui porte tout le chapitre 6 : sans lui, un
# acteur dont le CA n'est pas publié ne peut pas être estimé, et l'étape reste
# lettre morte. Il est donc demandé même — surtout — quand le CA est absent.
_BASE_CONCURRENTS = (
    "BASE CONSOLIDÉE CONCURRENTS (obligatoire pour cette étude).\n"
    "Renseigne `concurrents` avec EXACTEMENT 8 acteurs de type `direct` et "
    "3 de type `indirect`, soit 11. Pour chacun :\n"
    "- `nom`, `emplacement` (adresse ou ville précise), `structure` "
    "(indépendant, chaîne, franchise, groupe...), `positionnement` ;\n"
    # `site_web` porte désormais une DÉCISION, et pas seulement une commodité.
    #
    # Étude `3a4df56c`, 17/08/2026 : six « concurrents » sur onze étaient des
    # catégories — « Agence IA générique (Lyon) », « ESN de taille intermédiaire
    # (Lille) » — et recevaient un chiffre d'affaires, une croissance et une part
    # de marché comme s'ils avaient été observés.
    #
    # Le code sait maintenant les reconnaître à l'absence de domaine
    # (`Concurrent.est_identifie`). Encore faut-il que cette absence VEUILLE dire
    # quelque chose : le champ n'était que « demandé », donc un vrai concurrent
    # mal renseigné se serait fait déclasser en catégorie — un motif faux, et ce
    # dépôt sait ce qu'ils coûtent (règle 2). La consigne le rend délibéré.
    "- `site_web` : l'URL OFFICIELLE de l'acteur. C'est ce qui fait la "
    "différence entre une entreprise et une catégorie. Si tu ne peux pas citer "
    "d'adresse officielle vérifiable, alors cet acteur n'est PAS une entreprise "
    "identifiée : laisse `site_web` vide, nomme-le comme un TYPE d'acteur "
    "(« agences d'automatisation no-code », au pluriel) et n'invente ni son "
    "chiffre d'affaires, ni sa part de marché ;\n"
    "- deux offres d'un MÊME groupe (même domaine) ne comptent que pour un "
    "acteur : ne les inscris pas deux fois ;\n"
    # La devise d'une source ne se réétiquette pas en silence.
    #
    # Étude de marché `f0064333`, relue par la cliente le 18/08/2026 : « ne pas
    # mélanger euros et dollars selon les chapitres. Une donnée source doit
    # conserver la même devise partout ou être convertie clairement une seule
    # fois. »
    #
    # Le document écrit « 6 800 000 M€ » pour le marché mondial du bien-être,
    # et l'attribue au Global Wellness Institute — qui publie en DOLLARS. Le
    # chiffre a donc changé de devise entre la source et le document, sans un
    # mot, sans un taux. Aucun contrôle ne pouvait le voir : le document ne
    # contient pas un seul « $ ». Ce n'est pas un mélange visible, c'est une
    # conversion muette, et c'est plus grave.
    "- la DEVISE d'un chiffre est celle de sa source. Si la source publie en "
    "dollars, écris la valeur en dollars, ou convertis-la en indiquant le taux "
    "et l'année dans `libelle` — jamais l'un pour l'autre en silence. Un "
    "montant du Global Wellness Institute, de la Banque mondiale ou de l'OCDE "
    "n'est pas en euros parce que l'étude est française ;\n"
    "- `ca_connu` : le chiffre d'affaires PUBLIÉ avec son année "
    "(« 1,4 M€ (2024) »), ou la mention exacte « non publié ». Ne devine "
    "jamais un montant ici ;\n"
    "- `ca_source` : d'où vient ce montant. Vide si non publié ;\n"
    "- `methode_estimation` : comment ce CA POURRA être estimé si tu ne l'as "
    "pas trouvé — nombre de points de vente, volume de clients, panier moyen, "
    "fréquence d'activité, volume visible, benchmark sectoriel. Ce champ est "
    "ce qui rend l'estimation possible plus loin : ne le laisse pas vide pour "
    "un acteur sans CA publié ;\n"
    "- `fiabilite` : `haute`, `moyenne` ou `faible`, selon la qualité de la "
    "source ou de la méthode.\n"
    "Un acteur que tu ne peux pas situer et sourcer n'entre pas dans la liste : "
    "mieux vaut le remplacer par un acteur vérifiable.\n"
    "\n"
    # L'ENTREPRISE ÉTUDIÉE EST UN ACTEUR DE LA BASE.
    #
    # Retour de la cliente du 13/08/2026 : « dans plusieurs graphiques de
    # concurrence, les concurrents apparaissent mais l'entreprise elle-même
    # n'est pas représentée. Le lecteur doit immédiatement pouvoir voir : où se
    # situe mon entreprise par rapport à ses concurrents ? »
    #
    # Elle a raison, et la cause est ici : `concurrents` ne contenait QUE des
    # concurrents. Un radar ne pouvait donc pas la placer, et lui demander de
    # l'ajouter au moment de la figure reviendrait à lui faire inventer des
    # notes — le défaut qu'on passe la journée à combattre.
    #
    # Elle est donc notée à la source, sur la MÊME grille, ce qui rend la
    # comparaison honnête : ses notes se défendent avec les mêmes barreaux que
    # celles de ses concurrents.
    "AJOUTE UN DOUZIÈME ACTEUR : l'entreprise du dossier client elle-même, "
    "avec `type` valant exactement `projet`.\n"
    "- son `nom` est celui de l'entreprise ou du projet tel qu'il figure dans "
    "le dossier ;\n"
    "- ses champs se remplissent depuis le dossier client, pas depuis le web : "
    "`ca_connu` porte le chiffre d'affaires qu'il annonce, ou « non publié » "
    "pour un projet en création ;\n"
    "- elle reçoit une note sur CHAQUE critère de la grille, au même titre que "
    "les autres. Note-la avec la même sévérité : une entreprise qui obtient 5 "
    "partout produit un graphique que personne ne croit, et qui dessert le "
    "dossier devant un financeur.\n"
    "Elle ne compte NI dans les 8 directs NI dans les 3 indirects : c'est le "
    "point de référence du lecteur, pas un concurrent de lui-même.\n"
    "\n"
    "GRILLE DE NOTATION (obligatoire, et c'est elle qui rend les figures "
    "possibles).\n"
    "Renseigne `grille_notation` avec 4 à 6 critères d'évaluation adaptés au "
    "secteur — par exemple accessibilité tarifaire, étendue de l'offre, "
    "notoriété, qualité de service, présence en ligne. Pour chacun :\n"
    "- `code` : identifiant court en minuscules (`prix`, `notoriete`) ;\n"
    "- `intitule` : le nom lisible, qui s'affichera sur les figures ;\n"
    "- `note_1` et `note_5` : ce que valent CONCRÈTEMENT la note la plus basse "
    "et la plus haute pour ce critère. C'est le barème, et il doit permettre à "
    "un lecteur de refaire la notation lui-même. « Faible » et « fort » ne sont "
    "pas des définitions : dis à quoi on les reconnaît.\n"
    "LES CRITÈRES NE SERVENT À RIEN SANS LES NOTES. Une grille sans notes ne "
    "produit aucune figure : c'est la moitié du travail, et c'est la moitié "
    "inutile. Note donc CHAQUE concurrent sur CHACUN des critères, dans son "
    "champ `notes`, une entrée par critère :\n"
    "`\"notes\": [{\"critere\": \"prix\", \"note\": 4}, "
    "{\"critere\": \"notoriete\", \"note\": 2}]`\n"
    "Onze acteurs et cinq critères font cinquante-cinq entrées : c'est "
    "attendu, ne les abrège pas. Un entier de 1 à 5, jamais une fourchette, "
    "jamais un vide.\n"
    "Ces notes sont des appréciations argumentées à partir de ce que tu as "
    "observé — offre affichée, tarifs publics, avis clients, couverture — et "
    "non des chiffres de source : c'est le seul endroit du socle où tu juges. "
    "Un critère noté sur un seul acteur ne compare rien et fait refuser le "
    "socle ; un acteur non noté disparaît de toutes les figures."
)

# Règles du prévisionnel — business plan uniquement. Le pendant de
# `_BASE_CONCURRENTS` : ce que ce livrable exige de son socle et que le
# référentiel seul ne dit pas.
_PREVISIONNEL_BP = (
    "PRÉVISIONNEL FINANCIER (obligatoire pour ce business plan).\n"
    "Le prévisionnel se construit sur TROIS exercices, portés par les "
    "identifiants `_an1`, `_an2`, `_an3` du référentiel.\n"
    "- Chaque valeur du prévisionnel est un `scenario` : une hypothèse "
    "explicite, jamais une prévision observée. Les montants venus du brief "
    "(apport, emprunt, investissement) sont `declaree`.\n"
    "- Le plan de financement s'équilibre : apport + emprunt + autres "
    "ressources couvrent l'investissement total. Un découvert de départ n'est "
    "pas un montage, c'est un refus de socle.\n"
    "- Un premier exercice en perte est un scénario légitime : n'embellis pas "
    "`resultat_net_an1` pour le rendre positif.\n"
    "- Le seuil de rentabilité est un NIVEAU DE CHIFFRE D'AFFAIRES, dérivé "
    "des charges fixes et du taux de marge : déclare `derivee_de`.\n"
    "- Cohérence d'échelle : tout le prévisionnel dans la même unité "
    "monétaire. Un résultat net ne dépasse jamais le chiffre d'affaires du "
    "même exercice."
)

# Cadrage chiffré — stratégie uniquement. Presque tout vient du brief : le
# socle d'une stratégie dit ce que l'entreprise EST, pas ce que le marché vaut.
_CADRAGE_STR = (
    "CADRAGE CHIFFRÉ (stratégie d'entreprise).\n"
    "L'essentiel de ce socle vient du BRIEF : chiffre d'affaires actuel, "
    "panier moyen, marges, conversion. Fiabilité `declaree`, et rien "
    "d'inventé — une stratégie bâtie sur des chiffres supposés se retourne "
    "contre son lecteur.\n"
    "- Un projet en création n'a pas de `ca_actuel` : OMETS l'identifiant "
    "plutôt que d'y mettre zéro ou un objectif.\n"
    "- `ca_objectif_horizon` est un `scenario`, jamais une promesse, et "
    "`horizon_feuille_de_route` dit à quelle échéance il s'entend.\n"
    "- Renseigne `segments_clientele` avec les verticales du projet : nom, "
    "besoin dominant, part estimée. C'est la matière des chapitres 7 à 11."
)

_ROLE = (
    "Tu es analyste de marché. Ta seule tâche ici est de produire le SOCLE DE "
    "DONNÉES chiffrées d'une étude : les chiffres de référence sur lesquels "
    "tous les chapitres s'appuieront ensuite.\n"
    "\n"
    "Tu ne rédiges RIEN. Pas d'analyse, pas de recommandation, pas de phrase "
    "d'introduction. Tu renseignes des emplacements chiffrés.\n"
    "\n"
    "Ce socle sera verrouillé : aucun chapitre n'aura le droit de produire un "
    "chiffre de marché qui ne s'y trouve pas. Un chiffre que tu omets ici sera "
    "définitivement absent de l'étude ; un chiffre que tu inventes ici "
    "contaminera les 21 chapitres. Préfère donc omettre une donnée que la "
    "deviner."
)

_REGLES = (
    "RÈGLES ABSOLUES\n"
    "1. N'utilise QUE les identifiants du référentiel ci-dessous. Un "
    "identifiant hors liste fait rejeter tout le socle.\n"
    "2. Un identifiant = une seule valeur. Jamais de doublon.\n"
    "3. Respecte le périmètre imposé par le référentiel pour chaque "
    "identifiant. Le marché mondial et le marché continental sont deux "
    "valeurs DIFFÉRENTES : ne mets jamais la même des deux côtés.\n"
    "4. Respecte la famille d'unité imposée. Un taux de croissance s'exprime "
    "en %, jamais en milliards.\n"
    "5. `fiabilite` vaut :\n"
    "   - `observee` : chiffre publié par une source identifiée. La `source` "
    "devient alors OBLIGATOIRE (organisme + année, ex. « Insee, 2025 »).\n"
    "   - `estimee` : ordre de grandeur construit par triangulation. Explique "
    "la méthode dans `libelle`.\n"
    "   - `scenario` : hypothèse explicite, pas une prévision.\n"
    "   - `declaree` : valeur fournie par le porteur de projet dans son brief.\n"
    "6. N'invente JAMAIS de source ni d'URL. Si tu ne connais pas la source "
    "exacte, passe la donnée en `estimee` et laisse `source` vide.\n"
    "6 bis. HIÉRARCHIE DES SOURCES. À chiffre égal, prends toujours la plus "
    "PRIMAIRE et la plus RÉCENTE, dans cet ordre : (1) statistiques publiques "
    "et organismes officiels — Insee, Banque de France, ministères, Eurostat ; "
    "(2) fédérations et syndicats professionnels du secteur ; (3) sites "
    "OFFICIELS des acteurs concernés — comptes publiés, tarifs affichés ; "
    "(4) études sectorielles et cabinets ; (5) presse et blogs, en dernier "
    "recours et JAMAIS pour un chiffre qu'une source des quatre premiers rangs "
    "pourrait donner. Un chiffre de 2023 cité par un article de 2026 reste un "
    "chiffre de 2023 : c'est l'année de la MESURE qui compte, pas celle de "
    "l'article, et c'est elle qui va dans `annee`.\n"
    "6 ter. LA SOURCE DOIT PORTER CE CHIFFRE-LÀ. Avant de l'inscrire, "
    "demande-toi : cette source donne-t-elle EXACTEMENT cette valeur, pour ce "
    "périmètre et cette année ? Une source qui traite du même sujet sans porter "
    "le chiffre n'est pas une source : c'est une lecture, et la citer "
    "transformerait ton estimation en fait publié. Dans ce cas la donnée passe "
    "en `estimee`, tu expliques dans `libelle` d'où part le raisonnement, et "
    "`source` reste VIDE.\n"
    "7. Une fourchette n'est pas une valeur. Si ta donnée est une fourchette, "
    "retiens la médiane dans `valeur` et indique la fourchette dans `libelle`.\n"
    "8. Emboîtement obligatoire : TAM ≥ SAM ≥ SOM, dans la même devise. Le "
    "SOM se calcule par le bas : transactions annuelles × panier moyen.\n"
    "8 bis. LE CALCUL PART DU MOTEUR ÉCONOMIQUE RÉEL, PAS D'UNE PART DE "
    "MARCHÉ. Identifie d'abord ce qui fait entrer l'argent dans CETTE "
    "activité, puis chiffre sur cette base :\n"
    "   - commerce ou lieu physique : zone de chalandise, population qui y "
    "vit ou y passe, taux de captation réaliste, panier moyen, fréquence de "
    "visite. Une part d'un marché NATIONAL ne dit rien d'une boutique de "
    "quartier : c'est la zone qui décide, et un point de vente ne s'adresse "
    "qu'à ceux qui peuvent s'y rendre ;\n"
    "   - commerce en ligne : trafic atteignable, taux de conversion, panier "
    "moyen, taux de réachat, coût d'acquisition. La zone compte peu, "
    "l'audience et la concurrence sur les mêmes requêtes décident ;\n"
    "   - services et conseil : nombre de missions réalisables compte tenu du "
    "temps disponible, prix moyen d'une mission, taux de remplissage, part "
    "récurrente. La CAPACITÉ est le plafond : une personne seule ne vend pas "
    "plus d'heures qu'elle n'en a ;\n"
    "   - abonnement : abonnés atteignables, prix mensuel, durée de vie "
    "moyenne d'un abonné, taux d'attrition. Le chiffre d'affaires se construit "
    "en STOCK qui s'accumule, pas en ventes indépendantes ;\n"
    "   - capacité d'accueil — restaurant, hébergement, salle : nombre de "
    "places, taux d'occupation, rotation, ticket moyen, saisonnalité.\n"
    "Si l'activité en combine plusieurs, chiffre chaque verticale avec SON "
    "moteur et additionne : un même taux appliqué à tout écrase ce qui les "
    "distingue. Explique le moteur retenu dans `libelle` — c'est lui qui rend "
    "l'estimation discutable, donc utile.\n"
    "9. `derivee_de` liste les identifiants dont un chiffre découle. Un SOM "
    "calculé à partir du panier moyen déclare `[\"panier_moyen\", "
    "\"transactions_annuelles_cible\"]`. Une donnée primaire laisse la liste vide.\n"
    "10. Toute donnée facultative que tu ne peux pas établir sérieusement doit "
    "être OMISE. Un socle court et juste vaut mieux qu'un socle complet et faux.\n"
    # Retour de la cliente du 09/08/2026 sur l'etude e-commerce animalier :
    # « eviter qu'une source secondaire devienne la source principale d'un
    # chiffre structurant lorsqu'une source officielle plus fiable existe ».
    # L'ordre n'INTERDIT pas les sources secondaires — il interdit qu'elles
    # priment quand mieux existe.
    "11. HIÉRARCHIE DES SOURCES. Quand plusieurs sources donnent le même "
    "chiffre, retiens TOUJOURS la plus haute de cet ordre : (1) organismes "
    "publics et statistique officielle — Insee, ministères, data.gouv.fr, "
    "EUR-Lex, Service-public, DGCCRF ; (2) fédérations et syndicats "
    "professionnels du secteur — Fevad, Facco, Fediaf, Francéclat et leurs "
    "équivalents ; (3) cabinets d'études reconnus ; (4) presse spécialisée et "
    "publications d'acteurs. Les niveaux 3 et 4 restent utiles quand rien "
    "au-dessus ne publie la donnée — ils ne doivent simplement jamais porter "
    "seuls un chiffre structurant qu'un organisme officiel publie.\n"
    # Meme retour : « un panier moyen du e-commerce francais tous secteurs
    # confondus ne doit pas devenir automatiquement le panier moyen du
    # e-commerce animalier ».
    "12. UN BENCHMARK GÉNÉRAL N'EST PAS UNE DONNÉE SECTORIELLE. Un chiffre "
    "mesuré sur un périmètre plus large que celui demandé ne peut pas être "
    "recopié comme s'il valait pour le secteur : le panier moyen de "
    "l'e-commerce français tous secteurs confondus n'est pas celui de "
    "l'e-commerce animalier. Deux options, jamais une troisième : soit tu "
    "trouves la donnée SUR LE BON PÉRIMÈTRE et elle est `observee`, soit tu la "
    "transposes et elle devient `estimee`, avec la méthode et le périmètre "
    "d'origine écrits dans `libelle`."
)


def _ligne_referentiel(item: DefinitionDonnee) -> str:
    marque = "OBLIGATOIRE" if item.obligatoire else "facultatif"
    ligne = (
        f"- `{item.identifiant}` — {item.libelle}\n"
        f"    périmètre imposé : {item.perimetre} | unité : {unites_hint(item.famille_unite)}"
        f" | {marque}"
    )
    if item.chapitres:
        ligne += f"\n    exploité par les chapitres : {', '.join(map(str, item.chapitres))}"
    if item.commentaire:
        ligne += f"\n    note : {item.commentaire}"
    return ligne


#: Un chapitre qui parle de concurrence se reconnaît à son intitulé. La
#: recherche est volontairement large — « concurrent », « concurrentiel »,
#: « concurrence » — et sur la RACINE, pas sur une liste de titres exacts : le
#: chapitrage évolue, et une liste fermée redeviendrait fausse en silence
#: (règle 4).
_CHAPITRE_DE_CONCURRENCE = re.compile(r"concurren", re.IGNORECASE)


def _le_livrable_analyse_la_concurrence(deliverable_type: str) -> bool:
    """Le chapitrage de ce livrable consacre-t-il un chapitre à la concurrence ?

    On le DÉDUIT du blueprint plutôt que de le déclarer une seconde fois : le
    blueprint est la seule source de ce que contient un livrable, et une liste
    de types recopiée ici aurait divergé du jour où le chapitrage change
    (règle 5). C'est d'ailleurs par une telle liste que le business plan s'est
    retrouvé avec un chapitre « Analyse concurrentielle » et un socle sans
    concurrents.
    """
    from generation.blueprints import chapters_for_deliverable  # noqa: PLC0415

    return any(
        _CHAPITRE_DE_CONCURRENCE.search(blueprint.title)
        for blueprint in chapters_for_deliverable(deliverable_type)
    )


def bloc_referentiel(deliverable_type: str) -> str:
    definitions = definitions_pour(deliverable_type)
    lignes = "\n".join(_ligne_referentiel(item) for item in definitions)
    return f"RÉFÉRENTIEL DES IDENTIFIANTS ({len(definitions)} emplacements)\n{lignes}"


def construire_prompt_socle(
    *,
    deliverable_type: str,
    variables: Mapping[str, object],
    brief_recherche: str = "",
    motifs_precedents: list[str] | None = None,
) -> str:
    """Prompt utilisateur de la passe 1.

    `motifs_precedents` : en cas de nouvelle tentative, les motifs exacts du
    refus précédent. On ne redemande pas « fais mieux » — on dit ce qui a été
    refusé et pourquoi.
    """
    blocs = [
        _ROLE,
        # La récence ne se souhaite pas, elle se CHERCHE puis se JUSTIFIE.
        #
        # Relevé par la cliente le 18/08/2026 : « je vois 2024, or je sais que
        # 2025 existe et est publié ». La consigne disait déjà « les plus
        # récents disponibles » — un vœu, que rien n'obligeait à vérifier.
        #
        # Un institut publie une édition par an, et la précédente reste en ligne :
        # se contenter du premier résultat trouvé donne un millésime périmé sans
        # que rien ne le signale. On demande donc deux choses vérifiables :
        # chercher l'édition la plus récente AVANT de retenir un chiffre, et
        # écrire noir sur blanc, quand le millésime retenu n'est pas l'un des
        # deux derniers, que c'est la publication la plus récente qui existe.
        # Un chiffre daté devient alors une décision assumée, pas un oubli.
        f"DATE_DU_JOUR : {date.today().isoformat()}.\n"
        "RÉCENCE — obligatoire. Pour CHAQUE chiffre, cherche d'abord l'édition "
        "la plus récente de la source avant d'en retenir une : la plupart des "
        "instituts publient chaque année et laissent les éditions antérieures "
        "en ligne. Le premier résultat trouvé n'est pas le plus récent.\n"
        "Si le millésime que tu retiens n'est ni l'année en cours ni la "
        "précédente, écris-le dans le `libelle` : « donnée 2024, publication la "
        "plus récente disponible ». Ne traite jamais une année antérieure comme "
        "l'année en cours.",
        f"BRIEF_CLIENT :\n{json.dumps(variables, ensure_ascii=False, sort_keys=True, indent=2)}",
    ]

    if brief_recherche.strip():
        blocs.append(
            "SOURCES_WEB (collectées automatiquement, à privilégier pour les "
            f"données `observee`) :\n{brief_recherche}"
        )
    else:
        blocs.append(
            "SOURCES_WEB : aucune source collectée. N'invente ni URL ni date de "
            "publication ; passe en `estimee` toute donnée que tu ne peux pas sourcer."
        )

    blocs.append(bloc_referentiel(deliverable_type))

    # Base consolidée concurrents — étude de la concurrence uniquement.
    #
    # Le référentiel EC annonce que « l'essentiel du socle EC vit dans
    # `concurrents` », et le schéma déclare bien cette liste. Mais RIEN ne la
    # demandait : ce prompt ne contenait aucune occurrence du mot concurrent.
    # La liste partait donc vide à chaque étude, et le chapitre 6 — estimation
    # des chiffres d'affaires et parts de marché — n'avait aucune matière.
    # La condition portait sur le TYPE de livrable, et elle avait tort d'un
    # livrable.
    #
    # Business plan `2a8872d0` (12/08/2026) : le chapitre 7 « Analyse
    # concurrentielle » est mort CINQ fois, pour 4,19 €, sur des identifiants
    # que le modèle inventait — `critere_accessibilite_evkha`, puis `ACC` et
    # `TAR`. Il n'avait rien à recopier : le socle d'un business plan ne
    # portait ni concurrents ni grille de notation, parce que ce bloc-ci ne
    # partait que pour l'étude concurrentielle. Un chapitre réclamait une
    # matière que personne n'avait demandée.
    #
    # C'est le défaut décrit six lignes plus haut, un livrable plus loin. La
    # condition se déduit donc du CHAPITRAGE, seule source de ce que contient
    # un livrable : celui qui consacre un chapitre à la concurrence a besoin
    # d'une base de concurrents. Vérifié sur les quatre — étude
    # concurrentielle et business plan oui, étude de marché et stratégie non,
    # qui n'en ont aucun chapitre et dont le socle ne s'alourdit pas.
    # À ROUVRIR AVEC LA CLIENTE : ce bloc impose « EXACTEMENT 8 directs et 3
    # indirects », cardinaux figés par le cahier des charges de l'ÉTUDE
    # CONCURRENTIELLE. Rien ne dit qu'un business plan en demande autant, et
    # onze acteurs alourdissent son socle. On ne devine pas un chiffre à sa
    # place : le business plan reçoit donc la même exigence que l'étude
    # concurrentielle jusqu'à ce qu'elle en arrête une autre. Mieux vaut un
    # socle trop riche qu'un chapitre mort — c'est ce qui vient de coûter
    # 4,19 €.
    if _le_livrable_analyse_la_concurrence(deliverable_type):
        blocs.append(_BASE_CONCURRENTS)

    # Des `if` INDÉPENDANTS, et la nuance a un coût mesuré : la chaîne `elif`
    # d'origine supposait qu'un livrable n'a qu'un seul besoin. Dès que le
    # business plan a rejoint la première branche, il a PERDU son prévisionnel
    # financier — attrapé par `test_le_prompt_socle_bp_exige_le_previsionnel`
    # à la minute où le correctif ci-dessus a été écrit. Un business plan
    # réclame les deux : des concurrents pour son chapitre 7, un prévisionnel
    # pour tout le reste.
    #
    # Même mécanisme que `_BASE_CONCURRENTS` : un bloc d'exigences propres au
    # métier du document, à côté du référentiel qui liste les emplacements.
    # Sans lui, un schéma déclaré que rien ne demande part vide à chaque étude.
    if deliverable_type == DeliverableType.BUSINESS_PLAN:
        blocs.append(_PREVISIONNEL_BP)
    if deliverable_type == DeliverableType.BUSINESS_STRATEGY:
        blocs.append(_CADRAGE_STR)

    blocs.append(_REGLES)

    if motifs_precedents:
        motifs = "\n".join(f"- {motif}" for motif in motifs_precedents)
        blocs.append(
            "TENTATIVE PRÉCÉDENTE REFUSÉE. Corrige EXACTEMENT ces points, sans "
            f"rien changer d'autre :\n{motifs}"
        )

    blocs.append(
        "Réponds en appelant l'outil `produire_socle`. N'écris aucun texte "
        "en dehors de l'appel d'outil."
    )
    return "\n\n".join(blocs)

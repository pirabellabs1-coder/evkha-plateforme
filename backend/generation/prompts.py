from __future__ import annotations

from catalog.models import DeliverableType
from intake.models import IntakeSubmission
from integrations.claude import SYSTEM_CACHE_BREAK

from .blueprints import SECTION_MAX_WORDS, get_blueprint
from .context import build_context
from .geography import geographic_consigne_for
from .models import ChapterGeneration
from .prompt_library import prompt_instruction
from .reference_em import REFERENCE_EM

# Charte editoriale EVKHA — Manuel d'etude de marche (Evangeline, juillet 2026).
# Source unique : « EVKHA_Systeme_Manuel_Etude_de_Marche_Simplifie.pdf »,
# sections 3 (voix + donnees) et 4 (coherence). Reprise VERBATIM, sans
# empilement de regles supplementaires. Toute exigence non presente dans le
# manuel a ete retiree : elle polluait le texte livre (WAOME v4, 22/07/2026).
# La memoire du dossier (fiche projet enrichie) est portee par le contexte
# `client_facts_as_context` / `generated_facts_as_context` (voir `coherence.py`).
# Les controles inter-blocs (CHECK 1 a 9 + INITIAL + FINAL) sont declenches
# APRES la generation par `checks_blocs.py` — pas dans le prompt.
_CHARTER = (
    "[VOIX EVKHA — §3 du manuel]\n"
    "Ton professionnel, neutre, credible, fluide, accessible a un novice. Le "
    "dossier doit donner l'impression d'avoir ete construit avec le porteur de "
    "projet et qu'il pourrait l'expliquer lui-meme. Redige de vrais paragraphes "
    "relies entre eux, jamais une succession de listes ou de blocs "
    "independants. Evite le jargon ; lorsqu'un terme technique est "
    "indispensable, definis-le simplement des sa premiere utilisation. "
    "N'emploie ni « tu » ni « vous ». Aucun emoji, aucun ton vendeur, aucune "
    "exageration, aucune formulation typique d'une IA. Ne parle jamais de "
    "prompt, de pipeline, de controle, de modele ou d'automatisation dans le "
    "livrable client.\n"
    "\n"
    "[DONNEES ET SOURCES — §3 du manuel]\n"
    "Utilise des sources fiables, actuelles, verifiables et adaptees au secteur "
    "et a la zone. Ne jamais inventer un chiffre, une source, un lien, un texte "
    "reglementaire ou une citation.\n"
    # « Fiable » ne se decrete pas : il fallait dire LESQUELLES priment. Mesure
    # du 05/08/2026 sur le livrable reel `18ce3fca` : le domaine le plus cite de
    # l'etude etait un site de modeles de business plan, la ou le document
    # valide par la cliente cite l'INSEE, economie.gouv.fr, la Commission
    # europeenne, Deloitte, Reuters et UBS. Aucune URL n'etait inventee — le
    # controle le verifiait deja — mais l'AUTORITE des sources n'etait
    # gouvernee par rien.
    "HIERARCHIE DES SOURCES, du plus fort au plus faible. Remonte toujours "
    "aussi haut que possible :\n"
    "  1. le PRODUCTEUR de la donnee : institut statistique national, banque "
    "centrale, ministere, douanes, registre officiel, texte reglementaire ;\n"
    "  2. l'organisation professionnelle du secteur, la federation, "
    "l'observatoire de branche ;\n"
    "  3. le cabinet d'etudes ou l'auditeur reconnu, le rapport annuel d'une "
    "entreprise cotee ;\n"
    "  4. la presse economique ou professionnelle etablie, quand elle cite "
    "elle-meme sa source.\n"
    "Ce classement est une PREFERENCE, pas une exigence : un cabinet sectoriel, "
    "un observatoire de branche ou la presse professionnelle sont de bonnes "
    "sources, et souvent les seules a couvrir un marche de niche. N'ecarte pas "
    "un chiffre utile faute d'institution.\n"
    "En revanche, un agregateur, un comparateur, un blog ou un site de modeles "
    "de documents ne fait que REPETER quelqu'un. Quand tu en rencontres un, "
    "remonte a celui qu'il repete et cite-le, lui — c'est presque toujours "
    "possible, et le chiffre y gagne en precision comme en date.\n"
    "Regle qui, elle, ne souffre pas d'exception : chaque source nommee porte "
    "QUI produit la donnee et QUAND. « Francelat, 2025 » ou « Xerfi, etude "
    "sectorielle 2024 », jamais « une etude recente ».\n"
    "Ne jamais afficher « donnees non "
    "disponibles » dans l'etude client : recherche des sources proches et "
    "solides, croise les indices, construis une estimation prudente et "
    "explique clairement la methode. Distingue une donnee observee, une "
    "estimation et une projection. Donne une fourchette lorsque la precision "
    # « chapitre 21 » etait code en dur : c'est le numero du chapitre Sources de
    # l'ETUDE DE MARCHE seule. Or cette charte est injectee dans les QUATRE
    # livrables, dont les chapitres Sources sont respectivement 21 (EM), 21 (BP),
    # 20 (STR) et 9 (EC). Trois livrables sur quatre recevaient donc l'ordre de
    # regrouper leurs sources dans un chapitre qui n'existe pas chez eux. On
    # nomme le chapitre au lieu de le numeroter (regle 4 : viser la classe).
    "exacte serait artificielle. Regroupe les sources completes dans le "
    "chapitre Sources du document. Sous un graphique, conserve seulement la mention courte "
    "necessaire a sa lecture.\n"
    "\n"
    "[COHERENCE D'UN BOUT A L'AUTRE — §4 du manuel]\n"
    "Un chiffre valide ne doit pas changer de definition, d'annee, d'unite ou "
    "de valeur au fil du document. Si un chapitre retient un marche selon un "
    "perimetre precis, les chapitres suivants utilisent la meme fondation. "
    "Reutilise les memes definitions du marche, de la cible et des zones. "
    "Evite de repeter les memes explications ; chaque chapitre doit apporter "
    "une avancee. Relie chaque analyse au projet presente dans la fiche "
    "initiale. Verifie regulierement que toutes les demandes du client "
    "restent couvertes.\n"
    "\n"
    "[FOURCHETTES ET TAUX — regle Evangeline 23/07/2026]\n"
    "Une fourchette est autorisee seulement si elle est SERREE et coherente "
    "(exemple : « entre 1 000 et 1 400 »). Une plage type « 0 a 5 000 » n'a "
    "aucun sens analytique : trancher. Les TAUX, POURCENTAGES et TCAC sont "
    "TOUJOURS une valeur fixe unique, jamais une plage. Si plusieurs sources "
    "divergent, arbitrer un taux unique assume.\n"
    "\n"
    "[RYTHME VISUEL — §4 du manuel]\n"
    "Respecte le logo fourni, le noir, le blanc et le jaune EVKHA. Prevois au "
    "moins un ancrage visuel utile tous les deux ou trois chapitres : "
    "graphique, tableau, schema, matrice, carte, frise ou encadre. Choisis le "
    "visuel en fonction de l'information ; n'ajoute pas un graphique pour "
    "decorer. Les chiffres du visuel correspondent exactement a ceux du texte "
    "et de la fiche enrichie. Mise en page aeree, sobre, lisible et homogene."
)

# ── Le format des graphiques depend du MOTEUR, pas de la charte ──────────────
#
# Ce bloc etait dans `_CHARTER`, donc injecte dans les QUATRE livrables. Il
# annoncait quatre types ('bar', 'hbar', 'pie', 'radar') dans un format de code
# fence, et fermait sur « n'insere un graphique que si la consigne du chapitre
# le demande explicitement ».
#
# C'est exact pour le business plan et la strategie, servis par le moteur
# herite, dont le rendu lit bien ces fences (`generation/charts.py`).
#
# C'est FAUX pour l'etude de marche et l'etude concurrentielle, servies par le
# moteur structure : elles ne rendent aucun fence, leur catalogue compte QUINZE
# types, et leur prompt de chapitre le leur presente deja avec la consigne
# sectorielle (`chapitres/runner._bloc_visuels`). Le modele recevait donc deux
# ordres contradictoires — quinze types d'un cote, quatre de l'autre — et,
# par-dessus, une invitation a la parcimonie.
#
# Mesure du 05/08/2026, livrable reel `18ce3fca` : DEUX figures pour vingt-trois
# chapitres, contre dix au document valide par la cliente. Deux sources pour une
# meme verite, et c'est celle qui restreint qui gagnait (regle 5).
_GRAPHIQUES_MOTEUR_HERITE = (
    "\n\nGRAPHIQUES : format code fence ```chart contenant un JSON compact. "
    "Types disponibles : 'bar', 'hbar', 'pie', 'radar'. Schema :\n"
    "```chart\n"
    "{\"type\":\"radar\",\"title\":\"Titre\","
    "\"labels\":[\"Axe 1\",\"Axe 2\",\"Axe 3\"],"
    "\"series\":[{\"name\":\"Projet\",\"values\":[4,5,3]}],\"unit\":\"\"}\n"
    "```\n"
    "Contraintes : valeurs numeriques uniquement (pas d'unite dans les "
    "nombres). Pour pie : une seule serie. Pour radar : minimum 3 axes, memes "
    "axes pour toutes les series. Conserve un paragraphe d'analyse avant et "
    "apres chaque bloc chart."
)

#: L'objectif chiffre de figures, en UN SEUL exemplaire.
#:
#: Il etait ecrit dans `_GRAPHIQUES_MOTEUR_STRUCTURE` — c'est-a-dire dans
#: `build_system_prompt`, que SEUL le moteur herite envoie (`runner.py:462`).
#: Le moteur structure, le seul qui rende des figures, envoie `_SYSTEME` et le
#: bloc visuels de `chapitres/runner.py` : l'objectif ne lui parvenait JAMAIS.
#:
#: C'est le motif Gamma, une fois de plus (regle 8) : une exigence ecrite,
#: testee — et jamais transmise a qui devait l'appliquer. Les onze figures sur
#: quinze demandees du dossier 9be9a422 s'expliquent d'autant mieux que les
#: quinze n'ont jamais ete demandees au modele : elles venaient du seul
#: entrainement du profil sectoriel.
#:
#: Les deux chartes lisent desormais CE bloc (regle 5). Le quota vient de la
#: cliente : « au moins 17 a 25 graphes par document, obligation absolue » —
#: on demande vingt-deux pour en obtenir dix-sept, le rendu refusant
#: legitimement les figures dont la donnee ne se prete pas (taux mesure : onze
#: rendues pour quinze demandees).
OBJECTIF_FIGURES_TEXTE = (
    "OBJECTIF DE L'ETUDE ENTIERE : au moins VINGT-DEUX figures, et au moins "
    "DOUZE FORMES DIFFERENTES. C'est une etude illustree, pas un rapport de "
    "texte : un chapitre sans figure doit etre l'exception, et il faut une "
    "raison — aucune donnee du socle ne s'y prete.\n"
    "Vise DEUX figures par chapitre des que deux idees distinctes s'y "
    "illustrent : c'est ce qui fait la difference entre une etude illustree "
    "et une etude ou l'on a colle une image par section."
)

_GRAPHIQUES_MOTEUR_STRUCTURE = (
    "\n\nGRAPHIQUES : le catalogue complet et les types pertinents pour CE "
    "secteur te sont donnes avec la consigne du chapitre.\n"
    + OBJECTIF_FIGURES_TEXTE + "\n"
    "Un chapitre qui porte une comparaison, une repartition, une progression "
    "dans le temps, un classement, une evaluation ou un passage d'un perimetre "
    "a un autre APPELLE sa figure. Deux figures dans un meme chapitre sont "
    "bienvenues quand deux idees distinctes s'illustrent.\n"
    "La consigne du chapitre te dit quelles formes l'etude a DEJA employees : "
    "prends-en une autre des que le propos s'y prete. Reprendre une forme est "
    "permis — deux entonnoirs de suite, non.\n"
    "Un graphique ne porte aucune valeur : il porte des identifiants du socle. "
    "Deux consequences pratiques — cite au moins DEUX identifiants (une figure "
    "a une seule barre n'apprend rien), et cite des grandeurs de MEME NATURE "
    "(des montants entre eux, des taux entre eux). Les echelles, elles, se "
    "melangent librement : euros, milliers, millions et milliards d'une meme "
    "monnaie sont ramenes a une echelle commune au rendu."
)

_EM_ROLE = (
    "Tu es un analyste senior en etude de marche, SPECIALISTE du secteur et "
    "de la zone etudies (manuel EVKHA §3, juillet 2026). Tu comprends les "
    "enjeux d'un porteur de projet, tu restes objectif, tu expliques "
    "clairement les donnees et tu TRANSFORMES CHAQUE CONSTAT EN CONSEQUENCE "
    "CONCRETE POUR LE PROJET. Tu maitrises la collecte de donnees "
    "internationales, continentales, nationales et locales, et tu croises "
    "des sources fiables (primaires et secondaires) pour identifier les "
    "dynamiques sectorielles, les tendances emergentes, les risques et "
    "opportunites avec precision."
)

_EC_ROLE = (
    "Tu es un expert mondial en strategie concurrentielle, specialise dans les "
    "marches internationaux et locaux. Tu maitrises les outils utilises par les "
    "cabinets d'analyse strategique : identification fine des concurrents, "
    "cartographie concurrentielle, analyse SWOT concurrentielle, estimation des "
    "parts de marche, benchmark digital, analyse de positionnement, veille "
    "innovation et strategie RSE, lecture des avis clients comme signal "
    "strategique. Tu produis des analyses exploitables et decisionnelles."
)

_BP_ROLE = (
    "Tu es un expert en creation d'entreprise et en business plans "
    "professionnels, capable de produire des livrables de niveau cabinet de "
    "conseil destines aux banques, investisseurs, incubateurs et partenaires "
    "institutionnels. Tu ecris le business plan comme si le porteur de projet "
    "en etait lui-meme l'auteur : le client doit pouvoir s'approprier le "
    "document sans reecriture, le presenter a son banquier en confiance, et y "
    "reconnaitre son projet, ses mots, sa vision. Tu construis un recit "
    "entrepreneurial coherent et finançable."
)

_STR_ROLE = (
    "Tu es un consultant senior en strategie d'entreprise, specialiste du "
    "pilotage strategique des TPE et PME. Tu produis des strategies business "
    "professionnelles qui aident un dirigeant a piloter avec une vision claire : "
    "sortir d'une logique reactive, prioriser les bons leviers, structurer une "
    "croissance coherente et soutenable. Ton approche est centree sur les "
    "arbitrages strategiques reels, pas sur des conseils generiques. "
    "Tu ecris comme un consultant experimente qui explique intelligemment, "
    "non comme un rapport academique."
)

_ROLES: dict[str, str] = {
    DeliverableType.MARKET_STUDY: _EM_ROLE,
    DeliverableType.COMPETITOR_STUDY: _EC_ROLE,
    DeliverableType.BUSINESS_PLAN: _BP_ROLE,
    DeliverableType.BUSINESS_STRATEGY: _STR_ROLE,
}


def _consigne_specifique_livrable(deliverable_type: str) -> str:
    """Consigne specifique injectee au prompt selon le livrable.

    EM : reduit a zero — la voix, les regles de sources et la coherence sont
    portees par `_CHARTER` (§3-4 du manuel Evangeline 07/2026). Tout le reste
    (les 21 chapitres, la fiche projet enrichie, les CHECK 1 a 9 + INITIAL +
    FINAL) est porte hors prompt : par le blueprint, `coherence.py` et
    `checks_blocs.py`. Empiler des regles dans le prompt a produit WAOME v4
    (style robotique, regles regurgitees dans le texte livre) — retour du
    22/07/2026.

    BP/EC/STR : conservent leurs regles historiques (le manuel Evangeline
    juillet 2026 ne couvre que l'EM).
    """
    from .checks_evangeline import (  # noqa: PLC0415
        ATTENDUS_CONCURRENTS,
        CRITERES_TRI_CONCURRENTS,
        PILIERS_STRATEGIE,
    )

    consigne_fourchettes_stricte = (
        "FOURCHETTES DU BRIEF (regle absolue) : chaque valeur du document est "
        "un chiffre unique, jamais une plage. Tu ne recopies JAMAIS une "
        "fourchette (« 180-280 kEUR », « entre 3 et 5 M€ », « 14-16 % ») : tu "
        "ne la recopies jamais, ni celles du brief, ni celles que tu serais "
        "tente de produire. Quand une "
        "donnee source est en fourchette, tu dois TRANCHER : mediane par "
        "defaut (« 14-16 % » -> « 15 % retenu »), ou borne conservatrice pour "
        "un usage bancaire (borne basse pour un revenu, borne haute pour un "
        "cout). Documente le choix dans l'encadre Methodologie du chapitre "
        "Sources.\n"
    )

    if deliverable_type == DeliverableType.MARKET_STUDY:
        return ""

    if deliverable_type == DeliverableType.COMPETITOR_STUDY:
        nd, ni = ATTENDUS_CONCURRENTS["directs"], ATTENDUS_CONCURRENTS["indirects"]
        criteres = "\n".join(
            f"  {i}. {c}" for i, c in enumerate(CRITERES_TRI_CONCURRENTS, start=1)
        )
        # EXCEPTION du 05/08/2026 — la regle stricte interdisait exactement ce que
        # le cahier des charges EC rend OBLIGATOIRE. Son etape 6.2, FORMAT
        # OBLIGATOIRE : « Pour chaque concurrent estime, le systeme doit produire
        # une fourchette basse / haute, les hypotheses retenues clairement
        # explicitees, le niveau de fiabilite de l'estimation, la methode
        # utilisee » ; et son etape 6.4 veut les parts de marche « accompagnees
        # d'une fourchette si pertinent ».
        #
        # Le prompt systeme bloquait donc le format de sortie impose par le
        # chapitre : quoi qu'ecrive le modele, il violait l'une des deux
        # consignes. On leve l'interdiction sur ce seul cas — un chiffre
        # d'affaires ESTIME, faute d'etre publie — et nulle part ailleurs : les
        # taux, pourcentages et TCAC restent des valeurs uniques.
        exception_ca_estime = (
            "EXCEPTION, et elle est etroite : le CHIFFRE D'AFFAIRES ESTIME d'un "
            "concurrent non reference se rend OBLIGATOIREMENT en fourchette "
            "basse / haute, accompagnee des hypotheses retenues, de la methode "
            "d'estimation et du niveau de fiabilite. Une part de marche estimee "
            "peut l'etre aussi. Un CA PUBLIE, lui, reste un chiffre unique avec "
            "son annee et sa source. Cette exception ne s'etend a rien d'autre : "
            "taux, pourcentages et TCAC restent des valeurs uniques.\n"
        )
        return (
            consigne_fourchettes_stricte +
            exception_ca_estime +
            f"CONSIGNE STRUCTURELLE (regle absolue) : le livrable doit contenir "
            f"EXACTEMENT {nd} concurrents directs et EXACTEMENT {ni} concurrents "
            f"indirects, ni plus, ni moins. Sous-sections dediees, listees comme :\n"
            f"## Concurrents directs\n- <Nom> — <analyse>\n(x{nd} entrees)\n"
            f"## Concurrents indirects\n- <Nom> — <analyse>\n(x{ni} entrees)\n"
            f"Le systeme est MAITRE de la selection. Si le client ne fournit "
            f"aucun concurrent, tu en cherches. Si le client fournit une liste "
            f"que tu juges inadequate, tu la corriges. Si tu n'en trouves que "
            f"{nd - 2}, tu completes avec les {nd - (nd - 2)} acteurs les plus "
            f"proches. Si tu en trouves {nd + 4}, tu retiens les {nd} plus "
            f"pertinents. Le nombre n'est jamais negociable.\n"
            f"CRITERES DE TRI (ordre imperatif) pour arbitrer entre "
            f"concurrents pertinents :\n{criteres}\n"
            f"Le premier critere prime toujours. On descend au suivant en cas "
            f"d'egalite."
        )

    if deliverable_type == DeliverableType.BUSINESS_STRATEGY:
        piliers = ", ".join(
            f"{intitule} ({cle})"
            for cle, (intitule, _motif) in PILIERS_STRATEGIE.items()
        )
        # Reprise verbatim du document methodologique EVKHA envoye par la
        # cliente (« Systeme EVKHA — Strategies Business Automatisees »,
        # juillet 2026). Le prompt STR precedent posait les 4 piliers mais
        # ignorait la posture, la logique d'interpretation du brief et les
        # interdictions verbatim. Cinq ajouts :
        #
        # 1. POSTURE : cabinet de conseil / DAF, lucide meme inconfortable,
        #    refus de la complaisance.
        # 2. CINQ OBJECTIFS transversaux : clarification, structuration,
        #    rentabilite, pilotage, developpement.
        # 3. INTERPRETATION du brief imparfait : « le desordre initial du
        #    dirigeant est normal ». Reconstruire la logique cohérente
        #    plutot que d'exiger un brief parfait.
        # 4. REDACTION : paragraphes developpes, listes reservees aux
        #    synthese, arbitrages, feuilles de route.
        # 5. INTERDITS VERBATIM du PDF EVKHA : phrases motivationnelles
        #    creuses, conseils generiques.
        return (
            consigne_fourchettes_stricte +
            "POSTURE (methode EVKHA Strategies) : tu es un consultant senior, "
            "posture cabinet de conseil / DAF / direction generale. Tu produis "
            "une analyse lucide, meme inconfortable. Tu refuses la complaisance : "
            "si une orientation semble incoherente, tu la signales et l'expliques. "
            "L'objectif n'est pas de rassurer, c'est de piloter.\n"
            "CINQ OBJECTIFS transversaux de toute strategie EVKHA : "
            "clarification (positionnement, offres, verticales, vision), "
            "structuration (modele economique, priorites, croissance, decisions), "
            "rentabilite (valeur creee, marges, activites peu rentables), "
            "pilotage (arbitrages, dispersion, ressources, soutenabilite), "
            "developpement (croissance securisee, differenciation, trajectoire "
            "long terme). Chaque analyse doit se rattacher a au moins un de "
            "ces cinq axes.\n"
            "CONSIGNE STRUCTURELLE (regle absolue) : la strategie repose sur "
            f"QUATRE PILIERS, TOUS traites, dans cet ordre : {piliers}.\n"
            "- PILIER 1 (Positionnement & Specialisation) : sortir de la "
            "confusion, clarifier la direction, affirmer ce qui rend unique.\n"
            "- PILIER 2 (Structuration de l'offre) : organiser le catalogue "
            "pour vendre mieux sans s'eparpiller.\n"
            "- PILIER 3 (Planning editorial) : creer une presence qui attire "
            "les bons clients.\n"
            "- PILIER 4 (Analyse de la tarification) : arreter de fixer les "
            "prix au hasard, vendre avec confiance.\n"
            "La conclusion doit livrer une vision strategique ET un plan "
            "d'action operationnel.\n"
            "INTERPRETATION DU BRIEF (le desordre du dirigeant est normal) : "
            "aucun brief client n'arrive parfaitement structure. Les "
            "informations peuvent etre incompletes, desorganisees, "
            "emotionnelles, contradictoires. Ta tache : identifier les "
            "problematiques implicites, regrouper les informations similaires, "
            "reconstituer les intentions reelles du dirigeant, distinguer les "
            "vraies priorites des idees secondaires. Ne JAMAIS demander un "
            "brief plus complet ; toujours travailler avec ce qui est fourni.\n"
            "REDACTION (methode EVKHA) : paragraphes developpes qui expliquent "
            "les implications de chaque decision, PAS d'accumulation de listes. "
            "Les listes a puces sont reservees aux synthese, arbitrages, "
            "feuilles de route, tableaux de priorites, indicateurs.\n"
            "INTERDICTIONS VERBATIM du systeme EVKHA : ne JAMAIS ecrire "
            "« il faut poster plus sur Instagram », « il faut etre present sur "
            "tous les reseaux », « le marche est tres porteur » sans analyse, "
            "« l'entreprise doit se demarquer » sans explication, « la strategie "
            "semble coherente » sans demonstration. Ces formules signalent un "
            "conseil generique deconnecte du projet reel du client."
        )

    if deliverable_type == DeliverableType.BUSINESS_PLAN:
        # Le BP est un dossier BANCAIRE : chaque chiffre unique, aucune
        # fourchette. La consigne stricte suffit (la structure du BP est
        # imposee par le blueprint et les faits CLIENT verrouilles depuis
        # le brief Tally).
        return consigne_fourchettes_stricte

    return ""


def build_system_prompt(
    deliverable_type: str,
    country: str = "",
    plan: str = "",
) -> str:
    """Assemble le system prompt en deux segments separes par SYSTEM_CACHE_BREAK.

    Ordre voulu, et il n'est pas cosmetique :

      [ role + charte + few-shot EM + consigne ]  <- STABLE
      SYSTEM_CACHE_BREAK
      [ consigne geographique + plan Phase 0 ]    <- PROPRE AU JOB

    Le cache Anthropic est un prefixe strict : tout ce qui precede un
    breakpoint reste valide tant qu'il est inchange. En placant la consigne
    geographique AVANT la consigne de livrable (l'ordre historique), le
    moindre changement de pays invalidait la charte et le role, qui sont
    pourtant identiques pour tous les clients. Les trois blocs stables
    representent l'essentiel du system prompt : ils sont desormais mutualises
    entre jobs du meme type dans la fenetre d'1 h.
    """
    role = _ROLES.get(deliverable_type, _EM_ROLE)
    # La consigne graphique suit le MOTEUR qui sert ce livrable, et cette
    # verite a une seule source : `livrable_couvert`, la meme que
    # `runner._moteur_structure` interroge pour choisir le chemin d'ecriture
    # (regle 5). Deux drapeaux distincts finiraient par se contredire, et
    # c'est exactement ce qui produisait deux figures au lieu de dix.
    from .socle.referentiel import livrable_couvert  # noqa: PLC0415

    graphiques = (
        _GRAPHIQUES_MOTEUR_STRUCTURE
        if livrable_couvert(deliverable_type)
        else _GRAPHIQUES_MOTEUR_HERITE
    )
    stables = [role, _CHARTER + graphiques]
    # Few-shot EM (tache #13) : place APRES la charte — le manuel dit quoi
    # traiter, les extraits Findrax montrent a quel niveau. Et place dans le
    # segment STABLE : identique pour tous les jobs EM, donc mutualise dans la
    # fenetre de cache d'1 h. Mesure : 0,014 EUR/job ici, contre 0,077 EUR si
    # le bloc etait injecte hors cache dans les 30 appels.
    if deliverable_type == DeliverableType.MARKET_STUDY:
        stables.append(REFERENCE_EM)
    consigne = _consigne_specifique_livrable(deliverable_type)
    if consigne:
        stables.append(consigne)

    par_job = []
    geo = geographic_consigne_for(country) if country else ""
    if geo:
        par_job.append(geo)
    if plan:
        # plan contient : concurrents client (liste verrouillée), exigences verbatim,
        # structure des sous-sections obligatoires — tout avec "RÈGLE ABSOLUE".
        par_job.append(plan)

    prefixe = "\n\n".join(stables)
    if not par_job:
        return prefixe
    return prefixe + SYSTEM_CACHE_BREAK + "\n\n".join(par_job)


def _country_for(chapter: ChapterGeneration) -> str:
    submission = IntakeSubmission.objects.filter(order=chapter.job.order).first()
    if submission is None:
        return ""
    return str(submission.normalized_variables.get("PAYS", "")).strip()


# _RAPPEL_ANTI_RECHUTE_PIED : SUPPRIME le 24/07/2026.
# Ce rappel etait injecte en pied de chaque prompt de chapitre pour rattraper
# 5 defauts recurrents. Il a produit exactement l'effet inverse : les regles
# se retrouvaient recopiees mot pour mot dans le texte livre (« fourchette de
# 100 a 120 kEUR, mediane retenue 110 kEUR », « estimation construite par
# croisement... ETI Bpifrance 2024 »). Evangeline a explicitement rejete
# WAOME v4 pour ce motif — voir memoire `project_evkha_refonte_prompts_2026-07-23`.
# La coherence des chiffres est desormais confiee a la fiche projet enrichie
# (coherence.py) + aux CHECKs Sonnet inter-blocs (checks_blocs.py).


def _word_limit_footer(max_words: int) -> str:
    """Contrainte de complétude + densité injectée en fin de prompt.

    La complétude et la concision ne s'opposent PAS : on traite tout, en
    condensant. L'ancienne formulation les opposait et tranchait en faveur de
    la longueur — « budget INDICATIF », « si la complétude nécessite
    légèrement plus, c'est ACCEPTABLE », « la complétude prime sur TOUTE autre
    contrainte ». Le modèle obéissait : +29 % sur l'ensemble du business plan,
    +101 % sur le prévisionnel (2 800 mots visés, 5 639 produits).

    Ce dépassement n'est pas cosmétique. Il casse la mise en page : Gamma borne
    une carte à ~500 mots et 60 cartes au total. À 33 000 mots le document ne
    rentre pas, Gamma le comprime et 74 % du texte disparaît. À la cible, il
    passe. Le dépassement coûte aussi en tokens de sortie, le poste le plus
    cher.

    L'intention d'origine reste juste et est conservée : ne JAMAIS couper une
    liste avant le dernier élément. On ne gagne pas de la place en supprimant
    un concurrent, on en gagne en supprimant du délayage.
    """
    if not max_words:
        return ""
    return (
        f"\n\n[CONSIGNE IMPÉRATIVE DE COMPLÉTUDE ET DE CONCISION]\n"
        f"PRIORITÉ 1 — COMPLÉTUDE : traite TOUS les éléments demandés dans "
        f"cette section (tous les concurrents, toutes les rubriques, toutes "
        f"les parties de la liste). Ne jamais interrompre une liste avant "
        f"le dernier élément.\n"
        f"PRIORITÉ 2 — LIMITE FERME : {max_words} mots MAXIMUM. Ce n'est pas "
        "une indication, c'est une borne. Le lecteur est un chargé de "
        "clientèle bancaire : il veut des conclusions, pas du volume.\n"
        "PRIORITÉ 3 — COMMENT TENIR LES DEUX : la complétude s'obtient par la "
        "densité, jamais par la longueur. Si ça ne rentre pas, supprime "
        "d'abord les phrases de transition, les reformulations, les rappels "
        "de ce qui a déjà été dit, les tournures d'introduction et de "
        "conclusion de paragraphe. Ne supprime JAMAIS un élément de fond, un "
        "chiffre ou un item de liste. Un paragraphe qui n'apporte ni "
        "conclusion, ni chiffre, ni décision est du remplissage : retire-le.\n"
        "PRIORITÉ 4 — CLÔTURE : ferme toujours toutes tes balises HTML "
        "avant de terminer. Ne laisse jamais une structure ouverte."
    )


def _corrective_footer(corrective_note: str) -> str:
    """Bloc de correction injecte lors d'une regeneration (boucle d'auto-correction).

    Place en fin de prompt pour maximiser sa priorite : ce sont les defauts
    exacts detectes par le gate sur la version precedente, a corriger sans faute.
    """
    if not corrective_note:
        return ""
    return (
        "\n\n[CORRECTION IMPERATIVE, PRIORITE ABSOLUE]\n"
        "Ta version precedente de ce chapitre a ete REJETEE par le controle "
        "qualite pour les raisons ci-dessous. Reprends integralement le chapitre "
        "en corrigeant CHACUN de ces points, sans en introduire de nouveaux :\n"
        f"{corrective_note}"
    )


def build_chapter_prompt(chapter: ChapterGeneration, corrective_note: str = "") -> str:
    """Compose le prompt utilisateur : contexte (Context Engine) + consigne chapitre."""
    context = build_context(chapter)
    instruction = prompt_instruction(chapter.prompt_key)
    bp = get_blueprint(chapter.job.deliverable_type, chapter.chapter_number)
    word_limit = _word_limit_footer(bp.max_words if bp else 0)
    return (
        f"{context}\n\n"
        "CONSIGNE_DU_CHAPITRE :\n"
        f"{instruction}"
        f"{word_limit}"
        f"{_corrective_footer(corrective_note)}\n\n"
        "Rends uniquement le contenu final destine au client, sans repeter ces "
        "consignes."
    )


def build_section_prompt(
    chapter: ChapterGeneration,
    section_key: str,
    previous_context: str = "",
    corrective_note: str = "",
) -> str:
    """Prompt pour une section d'un chapitre en mode chunk generation.

    Meme contexte que le chapitre complet, mais instruction ciblee sur
    un sous-perimetre precis pour maximiser la densite par appel API.

    Le budget max_words est d'abord cherche dans SECTION_MAX_WORDS (table
    de surcharge par cle de section) avant de fallback sur bp.max_words.
    Certaines sections (ec.02.a.directs, ec.03.a.directs) couvrent 8
    concurrents et necessitent un budget bien superieur au chapitre-parent.
    """
    context = build_context(chapter)
    instruction = prompt_instruction(section_key)
    bp = get_blueprint(chapter.job.deliverable_type, chapter.chapter_number)
    # Priorite : surcharge par section → budget chapitre → 0 (pas de contrainte)
    section_mw = SECTION_MAX_WORDS.get(section_key) or (bp.max_words if bp else 0)
    word_limit = _word_limit_footer(section_mw)
    previous_block = ""
    if previous_context:
        # Tail-slice : on garde la FIN (section précédente adjacente) qui est
        # celle que Claude risque le plus de répéter. `[:4000]` gardait le
        # début (section 1), invisible pour section 3 qui suit section 2.
        previous_block = (
            "\n\nSECTIONS_PRECEDENTES (déjà rédigées — ne pas répéter, "
            "assurer la continuité) :\n"
            + previous_context[-4000:]
            + "\n"
        )
    return (
        f"{context}\n\n"
        f"CHAPITRE_PARENT: {chapter.chapter_number}. {chapter.chapter_title}"
        f"{previous_block}\n\n"
        "SECTION_A_GENERER :\n"
        f"{instruction}"
        f"{word_limit}"
        f"{_corrective_footer(corrective_note)}\n\n"
        "Rends uniquement le contenu de cette section, destine au client. "
        "Ne repete pas les consignes ni les donnees deja traitees dans les "
        "sections precedentes de ce chapitre."
    )

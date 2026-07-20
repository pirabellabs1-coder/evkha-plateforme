from __future__ import annotations

from catalog.models import DeliverableType
from intake.models import IntakeSubmission

from .blueprints import SECTION_MAX_WORDS, get_blueprint
from .context import build_context
from .geography import geographic_consigne_for
from .models import ChapterGeneration
from .prompt_library import prompt_instruction

# Regles d'or editoriales communes (Consignes d'ecriture EVKHA). Le rendu doit
# rester "client" : aucun marqueur de pipeline ("Etape", "Point de controle",
# "Verification", "Prompt a utiliser"). Le Rendering Engine les filtre aussi,
# mais on l'interdit des l'amont.
_CHARTER = (
    "Charte editoriale EVKHA (a appliquer sans exception) :\n"
    "TON : Professionnel mais chaleureux. Expert qui explique sans jargon "
    "inutile. Mentor qui dit les verites sans complaisance. Concret et "
    "applicable. Direct sans etre familier. Le porteur doit reconnaitre le "
    "document comme personnalise a sa situation.\n"
    "HIERARCHIE DES SOURCES (regle imperative, brief client) : les chiffres "
    "du previsionnel client (bloc DONNEES_CLIENT du contexte : "
    "investissement, apport, emprunt, CA, EBE, resultat net, taux "
    "d'occupation, seuil de rentabilite) priment sur TOUTE moyenne "
    "sectorielle, benchmark ou estimation. Ne JAMAIS substituer un cas "
    "generique aux hypotheses reelles du client. Ne JAMAIS creer un 'fait "
    "verrouille du dossier' a partir d'une donnee absente du brief. Les "
    "donnees sectorielles sont citees avec source datee et presentees comme "
    "reperes externes, jamais comme des faits acquis du dossier. Chaque "
    "verticale d'activite listee par le client doit etre traitee dans les "
    "chapitres concernes : aucune ne disparait au profit d'un modele type.\n"
    "DONNEES : Chiffrees, sourcees, concretes et exploitables. Aucune "
    "generalite, aucune theorie inutile. Si une donnee est incertaine, "
    "declare la fourchette et la source. "
    "PERIODE DE REFERENCE OBLIGATOIRE : les donnees de marche doivent couvrir "
    "la periode 2021-2026. Inclure systematiquement des chiffres 2025 et 2026 "
    "(estimations et projections argumentees acceptees). Ne jamais s'arreter a "
    "2024 : les etudes livrees en 2026 doivent refleter la realite actuelle.\n"
    "COMPLETUDE ABSOLUE (regle prioritaire) : tu dois toujours traiter la "
    "TOTALITE des elements demandes dans une section — tous les concurrents, "
    "toutes les rubriques, toutes les parties d'une liste. Ne jamais interrompre "
    "une liste a mi-parcours ni passer a la suite avant d'avoir couvert le "
    "dernier element. Si la densite depasse la cible indicative, condense le "
    "style mais ne coupe jamais un developpement en cours. L'ordre de priorite "
    "est : completude > densite > limite de mots.\n"
    "DENSITE ET LONGUEUR : chaque chapitre doit etre substantiel (minimum 4 a 6 "
    "paragraphes ou equivalent). L'etude complete cible 80 pages. Ne jamais "
    "tronquer un developpement : si un point merite 3 paragraphes, les ecrire "
    "tous. Privilegier la profondeur a la survol.\n"
    "SOURCES : Une seule section Sources en toute fin de document. Ne jamais "
    "integrer les references au fil du texte, dans les paragraphes ou a la "
    "fin des sections intermediaires.\n"
    "ENCADRES MENTOR (a inserer en cloture des chapitres strategiques) : "
    "utilise EXCLUSIVEMENT les marqueurs parseables suivants (jamais de texte "
    "libre a la place) : `[[UNDERSTAND]] ... [[/UNDERSTAND]]` pour \"Ce qu'il "
    "faut comprendre\" (lecture directe de l'enjeu reel), `[[CONSIDER]] ... "
    "[[/CONSIDER]]` pour \"Ce qu'il faut envisager\" (piste d'action concrete), "
    "`[[ATTENTION]] ... [[/ATTENTION]]` pour un point de vigilance (le piege "
    "classique a eviter), `[[ACTION]] ... [[/ACTION]]` pour \"Action "
    "concrete\" (feuille de route Mois 1/2/3, vraie question a poser aux "
    "prospects, ou les 3 chiffres a retenir). Au moins un bloc par chapitre "
    "analytique. Pas plus de 3 encadres mentor d'affilee dans un meme "
    "chapitre.\n"
    "ACRONYMES (Bloc 3 Consignes) : definir chaque acronyme technique a sa "
    "PREMIERE mention seulement, puis utiliser l'acronyme seul partout "
    "ensuite, sans jamais repeter la definition. Exemples : 'taux de "
    "croissance annuel moyen (TCAC)' puis 'TCAC' ; TAM/SAM/SOM expliques "
    "brievement (marche total / accessible / captable) puis acronymes seuls.\n"
    "TCAC ET INDICATEURS COMPOSITES : quand plusieurs etudes donnent des "
    "valeurs differentes, retenir UNE moyenne finale assumee (ex : 'TCAC "
    "retenu : 6,8 %') plutot que d'enumerer les estimations de chaque "
    "source.\n"
    "FRAICHEUR DES SOURCES : au moins 2 sources datees dans les 6 derniers "
    "mois par rapport a DATE_DU_JOUR fournie dans le contexte. Si aucune "
    "source recente n'existe, dis-le explicitement.\n"
    "ANTI-GENERICITE : chaque paragraphe doit citer soit un acteur nomme "
    "(entreprise, institution, personne), soit un chiffre precis avec date "
    "(<= 24 mois), soit un evenement date. Aucun paragraphe interchangeable "
    "avec un autre projet. Si tu ne peux pas etre specifique, ne rediges pas.\n"
    "TABLEAUX : ne rends jamais un tableau vide. Si tu ne peux pas remplir un "
    "tableau, remplace-le par du texte structure. Termine toujours par une "
    "ponctuation.\n"
    "INTERDICTIONS ABSOLUES : jamais d'emojis, de ton vendeur, de "
    "formulations typiques IA conversationnelle ('il apparait que', 'on peut "
    "observer', 'il convient de noter', 'dynamique porteuse'). Jamais de "
    "vocabulaire pipeline interne ('Etape', 'Point de controle', 'Validation', "
    "'Verification finale', 'Prompt a utiliser', 'CONTEXTE A REINJECTER', "
    "'Cas 1', 'Livrable automatise', 'Pipeline').\n"
    "ESTIMATIONS ET SOURCES (regle de verite, sans exception) : ne JAMAIS "
    "inventer une source, une URL, une date de publication ou un chiffre "
    "'sectoriel' invérifiable. Le bloc SOURCES_WEB du contexte contient les "
    "seules URLs reelles verifiees : n'en cite JAMAIS une qui n'y figure pas. "
    "Quand une donnee precise n'est pas etablie par ces sources, produire une "
    "estimation argumentee EXPLICITEMENT presentee comme telle ('estimation "
    "construite a partir de...', avec le raisonnement), jamais presentee comme "
    "un fait source. INTERDICTION VERBATIM d'ecrire 'donnee non disponible', "
    "'information non trouvee', 'source manquante' ou toute variante : ces "
    "formules donnent au client l'impression d'un travail incomplet. A la place, "
    "construis l'hypothese par croisement des sources adjacentes (secteurs "
    "similaires, zone geographique proche, indicateur equivalent), presente-la "
    "avec sa methode d'estimation, et documente le raisonnement dans l'encadre "
    "'Methodologie' du chapitre des Sources. Une hypothese sourcee et "
    "argumentee vaut toujours mieux qu'un silence.\n"
    "FOURCHETTES DU BRIEF (regle absolue) : quand le brief client cite une "
    "plage monetaire (« 180-280 kEUR », « entre 3 et 5 M€ ») ou un pourcentage "
    "en fourchette (« 14-16 % »), tu dois TRANCHER : cite UNE valeur unique "
    "dans le document. Prends la mediane par defaut (« brief 14-16 % » -> "
    "« 15 % retenu, mediane de la fourchette fournie »), ou la borne "
    "conservatrice pour un usage bancaire (borne basse pour un revenu, borne "
    "haute pour un cout). Documente le choix en une ligne dans l'encadre "
    "Methodologie du chapitre Sources. Ne RECOPIE JAMAIS la fourchette telle "
    "quelle : un banquier n'accepte pas « environ 180 a 280 000 EUR de "
    "seuil », il attend un chiffre. Meme regle pour les fourchettes que "
    "tu serais tente de produire (« environ X a Y »).\n"
    "TYPOGRAPHIE (regle stricte) : JAMAIS d'em-dash (—) ni d'en-dash (–) "
    "dans la prose redigee. Ce sont des signatures IA immediatement reperees "
    "par les lecteurs professionnels. Utilise a la place : une virgule pour "
    "les incises courtes, un point-virgule pour les propositions liees, deux "
    "points pour introduire une precision, ou une nouvelle phrase. SEULE "
    "exception (Bloc 1 Consignes) : le tiret cadratin des sous-titres "
    "numerotes, au format 'X.Y — Titre'. Le tiret simple (-) reste autorise "
    "pour les mots composes uniquement.\n"
    "GRAPHIQUES (a inserer UNIQUEMENT si la consigne du chapitre le demande "
    "explicitement) : format code fence ```chart contenant un JSON compact. "
    "Types disponibles : 'bar' (histogramme vertical), 'hbar' (barres "
    "horizontales, ideal pour un classement), 'pie' (camembert), 'radar' "
    "(profil multi-critere, ideal comparaison concurrentielle). Schema :\n"
    "```chart\n"
    "{\"type\":\"radar\",\"title\":\"Titre affiche au-dessus\","
    "\"labels\":[\"Axe 1\",\"Axe 2\",\"Axe 3\",\"Axe 4\",\"Axe 5\"],"
    "\"series\":[{\"name\":\"Projet\",\"values\":[4,5,3,4,5]},"
    "{\"name\":\"Concurrent A\",\"values\":[5,3,5,4,3]}],\"unit\":\"\"}\n"
    "```\n"
    "Contraintes : valeurs numeriques uniquement (pas de texte, pas d'unite "
    "dans les nombres). Pour pie : une seule serie. Pour radar : minimum "
    "3 axes, memes axes pour toutes les series. Le graphique remplace le "
    "commentaire redactionnel : conserve toujours au moins un paragraphe "
    "d'analyse avant et un apres le bloc chart. N'insere JAMAIS de "
    "graphique en dehors des chapitres qui te le demandent."
)

_EM_ROLE = (
    "Tu es un analyste senior expert en etudes de marche, dote d'une capacite "
    "avancee a croiser des sources fiables (primaires et secondaires), a "
    "analyser en profondeur des donnees quantitatives et qualitatives, et a "
    "delivrer des recommandations strategiques concretes et actionnables. Tu "
    "maitrises la collecte de donnees internationales, europeennes et locales, "
    "et sais identifier les dynamiques sectorielles, les tendances emergentes, "
    "les risques et opportunites avec precision."
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
    """Consigne verbatim d'Evangeline injectee au prompt selon le livrable.

    Les CHIFFRES et LIBELLES sont importes depuis `checks_evangeline` : c'est
    la meme source que le gate, donc le prompt et le check ne peuvent pas
    diverger (regle 5 du CLAUDE.md). Si demain la cliente passe a 10 directs,
    la modification d'une seule constante propage a l'ecriture ET au controle.
    """
    from .checks_evangeline import (  # noqa: PLC0415
        ATTENDUS_CONCURRENTS,
        CRITERES_TRI_CONCURRENTS,
        PILIERS_STRATEGIE,
    )

    if deliverable_type == DeliverableType.COMPETITOR_STUDY:
        nd, ni = ATTENDUS_CONCURRENTS["directs"], ATTENDUS_CONCURRENTS["indirects"]
        criteres = "\n".join(
            f"  {i}. {c}" for i, c in enumerate(CRITERES_TRI_CONCURRENTS, start=1)
        )
        return (
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
    return ""


def build_system_prompt(
    deliverable_type: str,
    country: str = "",
    plan: str = "",
) -> str:
    role = _ROLES.get(deliverable_type, _EM_ROLE)
    geo = geographic_consigne_for(country) if country else ""
    parts = [role, _CHARTER]
    if geo:
        parts.append(geo)
    consigne = _consigne_specifique_livrable(deliverable_type)
    if consigne:
        parts.append(consigne)
    if plan:
        # plan contient : concurrents client (liste verrouillée), exigences verbatim,
        # structure des sous-sections obligatoires — tout avec "RÈGLE ABSOLUE".
        parts.append(plan)
    return "\n\n".join(parts)


def _country_for(chapter: ChapterGeneration) -> str:
    submission = IntakeSubmission.objects.filter(order=chapter.job.order).first()
    if submission is None:
        return ""
    return str(submission.normalized_variables.get("PAYS", "")).strip()


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

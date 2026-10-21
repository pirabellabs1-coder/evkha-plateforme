"""Le brief des cibles B2B d'EVKHA — la « formation » des agents de prospection.

Source : « Cibles B2B EVKHA », brief du 21/10/2026. Une seule vérité, ici :
les agents (recherche, qualification, rédaction) et l'assistant y puisent leur
connaissance des cibles, des signes d'intérêt, des exclusions et des règles de
rédaction. Modifier la cible, c'est modifier ce fichier — pas quatre prompts.
"""
from __future__ import annotations

PITCH = (
    "EVKHA est un logiciel qui, à partir d'un court questionnaire, génère en "
    "quelques minutes une étude de marché, une analyse de la concurrence, un "
    "business plan ou une stratégie business, prêts à remettre au client. "
    "Pour un professionnel B2B, il fait gagner du temps (moins d'heures de "
    "rédaction), du volume (plus de porteurs de projet suivis sans recruter) et "
    "de la qualité (des dossiers homogènes, mettables à sa propre marque — "
    "marque blanche). Modèle : abonnement mensuel avec des crédits "
    "(1 crédit = 1 dossier)."
)

CIBLES = (
    "Les agents cherchent des PROFESSIONNELS qui accompagnent des créateurs "
    "d'entreprise ou préparent des stratégies pour leurs clients. 5 cibles, la "
    "n°1 étant prioritaire :\n"
    "1. (PRIORITAIRE) Structures d'accompagnement à la création : réseaux de "
    "prêt d'honneur (Initiative France, Réseau Entreprendre, France Active, "
    "ADIE), BGE, couveuses, coopératives d'activité et d'emploi (CAE), "
    "incubateurs, pépinières, technopoles, CCI et CMA (service création), "
    "agences de développement économique, services économiques des "
    "communautés de communes et métropoles. Contacter : directeur/directrice, "
    "responsable création-reprise, chargé de mission/d'accompagnement/d'affaires, "
    "responsable d'incubateur. Signes d'intérêt : beaucoup de porteurs pour peu "
    "de conseillers, comités de financement réguliers, promotions d'incubation, "
    "offres d'emploi de chargés d'accompagnement. Argument : « Vos conseillers "
    "suivent plus de porteurs, avec des dossiers solides, sans y passer leurs "
    "soirées. »\n"
    "2. Organismes de formation et coachs création : OF proposant « créer son "
    "entreprise », prestataires France Travail (ateliers création), cabinets de "
    "reconversion et bilans de compétences, formateurs/coachs indépendants. "
    "Contacter : gérant(e), responsable pédagogique, coordinateur de formation, "
    "formateur indépendant. Signes : certification Qualiopi, formations sur "
    "Kairos/Carif-Oref, business plan ou étude de marché prévu dans la "
    "formation, sessions fréquentes. Argument : « Chaque stagiaire repart avec "
    "un vrai dossier professionnel, ce qui rend votre formation plus concrète. »\n"
    "3. Agences de communication et marketing (2 à 20 personnes) : communication, "
    "marketing digital, branding, création de sites. Contacter : fondateur/"
    "dirigeant, directeur conseil, responsable stratégie, chef de projet. Signes : "
    "clients startups/créateurs, lancements de produits, une étape « audit » ou "
    "« stratégie » dans leurs offres, pas de stratège en interne. Argument : "
    "EVKHA est un OUTIL INTERNE qui prépare l'étude de marché et l'analyse de la "
    "concurrence avant la stratégie — ne JAMAIS le présenter comme un produit à "
    "revendre.\n"
    "4. Experts-comptables, juristes, consultants : experts-comptables faisant "
    "des prévisionnels pour créateurs, avocats/juristes en droit des affaires, "
    "plateformes juridiques de création, courtiers en financement pro, "
    "conseillers bancaires créateurs, consultants en stratégie/levée de fonds. "
    "Contacter : associé, expert-comptable, responsable de l'offre création, "
    "consultant. Signes : page « création d'entreprise » ou « business plan » sur "
    "le site, forfaits dédiés aux créateurs. Argument : « Complétez votre "
    "prévisionnel avec l'étude de marché et la stratégie, sans y passer des "
    "heures. »\n"
    "5. (SEULEMENT si l'occasion se présente, après 1-4) Écosystème élargi : "
    "écoles/universités (chaires entrepreneuriat, PEPITE), réseaux "
    "d'entrepreneurs et clubs d'affaires, réseaux de femmes entrepreneures, "
    "plateformes de freelances et portage salarial avec volet accompagnement."
)

OU_CHERCHER = (
    "Zones, dans l'ordre : d'abord Hauts-de-France (Lille) et Île-de-France "
    "(Paris) — Evangeline y est déjà connue comme formatrice ; puis toute la "
    "France (l'offre est 100 % en ligne) ; plus tard Belgique et Suisse "
    "francophones. Où trouver les contacts : sites et annuaires des réseaux "
    "(Initiative France, BGE, CCI), LinkedIn (par intitulé de poste), annuaires "
    "Qualiopi et Carif-Oref, sites d'agences et de cabinets."
)

EXCLUSIONS = (
    "NE PAS contacter : les grands cabinets de conseil (Big Four, cabinets de "
    "stratégie) — ce sont des concurrents ; les particuliers et porteurs de "
    "projet en direct (ils relèvent du B2C) ; les structures sans aucune "
    "activité liée à la création d'entreprise ou à la stratégie ; les clients et "
    "partenaires actuels d'EVKHA."
)

REGLES_REDACTION = (
    "Règles de rédaction STRICTES :\n"
    "- RGPD : en B2B, on écrit à une adresse professionnelle si le message a un "
    "lien avec le métier de la personne. Indiquer brièvement d'où vient le "
    "contact (ex. « j'ai vu votre offre d'accompagnement à la création »). Le "
    "lien de désinscription est ajouté automatiquement — ne pas en rédiger.\n"
    "- Prix : NE JAMAIS annoncer de tarif. Le but d'un message est d'obtenir une "
    "démonstration de 10 minutes.\n"
    "- Ton : professionnel et chaleureux. Evangeline travaille SEULE : écrire à "
    "la première personne du singulier (« je »), JAMAIS « nous ».\n"
    "- Vocabulaire : dire « le logiciel génère », jamais « IA propriétaire ».\n"
    "- Signature : Evangeline, EVKHA Business & Formations, contact@evkha.fr, "
    "evkha.fr.\n"
    "- Adapter l'argument à la cible (voir les arguments par cible)."
)


def brief_recherche() -> str:
    """Pour l'agent de recherche : qui trouver, où, et qui exclure."""
    return f"{PITCH}\n\n{CIBLES}\n\n{OU_CHERCHER}\n\n{EXCLUSIONS}"


def brief_qualification() -> str:
    """Pour l'agent de qualification : juger l'adéquation à ces cibles."""
    return (
        f"{PITCH}\n\n{CIBLES}\n\n{EXCLUSIONS}\n\n"
        "Note haute pour une cible 1 nette avec des signes d'intérêt ; note "
        "basse, voire 0, pour un profil exclu (concurrent, B2C, sans lien avec "
        "la création d'entreprise). La priorité de la cible compte : 1 > 2 > 3 "
        "> 4 > 5."
    )


def brief_redaction() -> str:
    """Pour l'agent de rédaction : argument par cible + règles strictes."""
    return f"{PITCH}\n\n{CIBLES}\n\n{REGLES_REDACTION}"


def brief_assistant() -> str:
    """Pour l'assistant : connaître les cibles pour affiner avec l'utilisatrice."""
    return f"{PITCH}\n\n{CIBLES}\n\n{OU_CHERCHER}\n\n{EXCLUSIONS}"

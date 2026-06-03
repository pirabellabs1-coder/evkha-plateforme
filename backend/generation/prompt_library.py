from __future__ import annotations

# Bibliotheque d'instructions par chapitre (remplace le "parsing" des prompts
# proprietaires EVKHA). Source de verite : "PROMPT FINAL VERSION 3 EM_EC" +
# "Consignes d'ecriture EVKHA". Texte reformule, fidele a la methode, sans
# marqueurs internes (jamais "Etape", "Verification", "Prompt a utiliser"
# dans la sortie attendue). Les variables [SECTEUR]/[PAYS]/[ZONE]/[PROJET]
# sont injectees via le contexte, pas en dur ici.

# --- Etude de marche (EM) -------------------------------------------------

MARKET_STUDY_PROMPTS: dict[str, str] = {
    "em.00.fiche_projet": (
        "Redige la fiche projet d'ouverture : rappel synthetique du projet, du "
        "secteur, de la zone et du pays cibles, et de l'intention strategique. "
        "Ton mentor, concis, professionnel."
    ),
    "em.01.marche_mondial_europeen": (
        "Analyse chiffree du marche mondial et europeen : taille, croissance "
        "(TCAC), segments majeurs, dynamiques. Toutes les donnees chiffrees et "
        "sourcees, fourchettes assumees si incertitude."
    ),
    "em.02.marche_national_local": (
        "Analyse chiffree du marche national (pays cible) puis local/regional "
        "(zone cible) : taille, croissance, maturite, specificites locales."
    ),
    "em.03.segmentation": (
        "Segmentation approfondie du marche (criteres pertinents au secteur), "
        "poids relatif de chaque segment et attractivite."
    ),
    "em.04.avantages_inconvenients": (
        "Avantages et inconvenients structurels du secteur, de maniere "
        "equilibree et factuelle."
    ),
    "em.05.defis_opportunites": (
        "Defis et opportunites du marche, hierarchises et argumentes par des "
        "donnees."
    ),
    "em.06.reglementation": (
        "Analyse approfondie de la reglementation applicable (pays et zone) : "
        "cadre juridique, contraintes, obligations, evolutions prevues."
    ),
    "em.07.tendances_court_terme": (
        "Tendances du marche a court terme (12-24 mois), avec signaux et "
        "indicateurs chiffres."
    ),
    "em.08.perspectives_long_terme": (
        "Perspectives d'evolution a long terme (3-5 ans et au-dela), scenarios "
        "et facteurs structurants."
    ),
    "em.09.douze_chiffres_cles": (
        "Les 12 chiffres cles du marche, presentes de facon synthetique et "
        "memorisable, chacun source."
    ),
    "em.10.clientele_cible": (
        "Analyse approfondie de la clientele cible : besoins, comportements, "
        "capacite d'achat, criteres de decision."
    ),
    "em.11.personas": (
        "Personas detailles (2 a 4) representatifs de la clientele cible : "
        "profil, motivations, freins, parcours d'achat."
    ),
    "em.12.risques_plan_gestion": (
        "Analyse des risques et plan de gestion : risques identifies, "
        "probabilite, impact, mesures de mitigation."
    ),
    "em.13.cartographie_risques": (
        "Cartographie visuelle des risques externes (donnees structurees pretes "
        "a visualiser : risque, probabilite, impact)."
    ),
    "em.14.rentabilite_viabilite": (
        "Analyse de la rentabilite et de la viabilite du projet : hypotheses "
        "economiques, seuils, leviers."
    ),
    "em.15.graphiques_tableaux": (
        "Donnees structurees pour graphiques et tableaux visuels cles (format "
        "tableau exploitable), sans produire d'image."
    ),
    "em.16.offre_demande": (
        "Analyse croisee de l'offre et de la demande : equilibre, tensions, "
        "elasticite, zones de friction."
    ),
    "em.17.geographique_avancee": (
        "Analyse geographique avancee : zones propices ou a eviter dans la zone "
        "cible, avec justification chiffree."
    ),
    "em.18.swot": (
        "Analyse SWOT complete et specifique au projet (forces, faiblesses, "
        "opportunites, menaces), chaque point argumente."
    ),
    "em.19.recommandations": (
        "Analyse strategique et recommandations finales, concretes, priorisees "
        "et actionnables."
    ),
    "em.20.conclusion": (
        "Conclusion analytique et lecture synthetique de l'etude : enseignements "
        "majeurs et message strategique."
    ),
    "em.21.annexe_brief": (
        "Annexe : reponse explicite a chaque demande specifique du client "
        "(traite / partiellement / non traite + justification)."
    ),
    "em.22.sources": (
        "Liste structuree des sources et de la methodologie de l'etude (nom + "
        "URL), regroupee en fin de document."
    ),
}

# --- Etude de la concurrence (EC) ----------------------------------------

COMPETITOR_STUDY_PROMPTS: dict[str, str] = {
    "ec.00.fiche_projet": (
        "Fiche projet d'ouverture de l'etude concurrentielle : rappel du projet, "
        "du secteur, de la zone et du pays, et de l'objectif de benchmark."
    ),
    "ec.01.identification": (
        "Identification rigoureuse des concurrents directs (meme offre, meme "
        "cible) et indirects (substituts). Selectionne les 8 directs les plus "
        "influents et les 3 indirects les plus strategiques. Pour chacun : nom, "
        "emplacement precis, site web. Termine par une base consolidee (type, "
        "structure, positionnement, CA connu ou estime + fiabilite)."
    ),
    "ec.02.classement_qualitatif": (
        "Classement et analyse qualitative : presence geographique, structure, "
        "positionnement. Pour les 8 directs, 3 forces et 3 faiblesses + une "
        "valeur ajoutee differenciante pour le projet. Idem pour les 3 indirects."
    ),
    "ec.03.approfondissement": (
        "Approfondissement strategique par concurrent : positionnement global, "
        "synthese des avis clients (positifs/negatifs + enseignements), "
        "innovations, technologies (e-commerce, CRM, IA...), tendances suivies, "
        "initiatives RSE."
    ),
    "ec.04.positionnement_annexes": (
        "Positionnement differenciant recommande pour le projet face aux "
        "concurrents, puis 3 a 4 annexes strategiques pretes a inserer (canaux "
        "de communication, comparatif avis clients, analyse juridique, benchmark "
        "digital...)."
    ),
    "ec.05.matrice_positionnement": (
        "Matrice de positionnement concurrentiel : choisis 2 axes strategiques "
        "pertinents, fournis les coordonnees (tableau) des concurrents et du "
        "projet, puis interprete les zones saturees, espaces libres et risques "
        "de cannibalisation."
    ),
    "ec.06.parts_de_marche": (
        "Estimation des chiffres d'affaires et parts de marche : CA connus "
        "(annee + source + fiabilite), estimations argumentees pour les acteurs "
        "non references, projection des parts de marche locales et lecture "
        "(qui domine, qui emerge, qui recule)."
    ),
    "ec.07.conclusion_graphiques": (
        "Conclusion analytique : forces/faiblesses majeures du marche "
        "concurrentiel, axe strategique prioritaire pour le projet, leviers "
        "differenciants des le lancement. Fournis les donnees de 4 graphiques "
        "(carte des concurrents, parts de marche, radar forces/faiblesses, "
        "repartition des canaux)."
    ),
    "ec.08.annexe_brief": (
        "Annexe finale : pour chaque demande specifique du client, indique si "
        "elle est traitee, partiellement traitee ou non traitee, avec une phrase "
        "explicative le cas echeant."
    ),
}


# --- Business Plan (BP) --------------------------------------------------
# Structure BP France/Afrique francophone. A valider avec les documents
# specifiques EVKHA lorsque l'acces Drive sera configure.

BUSINESS_PLAN_PROMPTS: dict[str, str] = {
    "bp.00.fiche_projet": (
        "Fiche projet d'ouverture du business plan : synthese du projet, du "
        "porteur, du secteur, de la zone et du pays, de la forme juridique "
        "envisagee et du capital initial prevu."
    ),
    "bp.01.resume_executif": (
        "Resume executif percutant (1 page) : proposition de valeur, marche "
        "cible, modele de revenus, besoin de financement, chiffres cles "
        "projetes a 3 ans. Tout doit etre sourcable ou hypothese declaree."
    ),
    "bp.02.porteur_equipe": (
        "Presentation du porteur de projet (parcours, competences cles, "
        "motivations) et de l'equipe (roles, experience, complementarite). "
        "Si l'equipe est a constituer, decris le profil recherche."
    ),
    "bp.03.description_offre": (
        "Description precise du projet et de l'offre : produit/service, "
        "proposition de valeur differenciante, stade de developpement, "
        "propriete intellectuelle ou barriere a l'entree eventuelle."
    ),
    "bp.04.marche_cible": (
        "Analyse du marche cible : taille et croissance, segmentation, "
        "clientele prioritaire, personas, comportements d'achat. "
        "Synthese actionnable depuis l'etude de marche si disponible."
    ),
    "bp.05.concurrentielle": (
        "Analyse concurrentielle : principaux acteurs directs et indirects, "
        "positionnement du projet par rapport a la concurrence, avantage "
        "differenciant defendable."
    ),
    "bp.06.strategie_commerciale": (
        "Strategie commerciale et marketing : canaux d'acquisition, "
        "politique de prix, plan de communication, objectifs de vente "
        "annee 1/2/3, indicateurs de suivi."
    ),
    "bp.07.modele_economique": (
        "Modele economique et sources de revenus : description des flux de "
        "revenus (vente directe, abonnement, commission...), structure de "
        "couts principaux, marge brute estimee, point mort."
    ),
    "bp.08.plan_operationnel": (
        "Plan operationnel et organisationnel : processus cles, ressources "
        "humaines, locaux et equipements, fournisseurs strategiques, "
        "calendrier de demarrage."
    ),
    "bp.09.previsions_financieres": (
        "Previsions financieres sur 3 ans : compte de resultat previsionnel "
        "(CA, charges, EBITDA, resultat net), bilan simplifie, tableau de "
        "tresorerie, hypotheses clairement declarees et sensibilite."
    ),
    "bp.10.plan_financement": (
        "Plan de financement et besoins en capital : besoins identifies, "
        "sources envisagees (fonds propres, pret bancaire, subvention, "
        "investisseur), structure cible du capital, calendrier des appels "
        "de fonds."
    ),
    "bp.11.risques_contingence": (
        "Analyse des risques et plan de contingence : identification des "
        "risques majeurs (marche, financier, operationnel, juridique), "
        "probabilite/impact, mesures de mitigation pour chacun."
    ),
    "bp.12.calendrier_jalons": (
        "Calendrier de developpement et jalons : feuille de route sur 18 "
        "mois avec jalons cles (lancement, premier client, seuil de "
        "rentabilite, prochaine levee...), responsables et criteres de succes."
    ),
    "bp.13.annexes": (
        "Annexes : documents justificatifs, simulations complementaires, "
        "reponses aux demandes specifiques du client. "
        "Indique si chaque demande est traitee ou a completer."
    ),
}

# --- Strategie Business (STR) --------------------------------------------

BUSINESS_STRATEGY_PROMPTS: dict[str, str] = {
    "str.00.fiche_projet": (
        "Fiche projet d'ouverture de la strategie business : rappel du "
        "projet, du secteur, de la zone, du pays et de l'horizon de "
        "planification strategique vise."
    ),
    "str.01.diagnostic_interne": (
        "Diagnostic interne : forces et faiblesses de l'organisation ou du "
        "projet (ressources, competences, structure, finances, culture). "
        "Sources ou hypotheses declarees pour chaque element."
    ),
    "str.02.pestel": (
        "Analyse PESTEL de l'environnement externe (Politique, Economique, "
        "Socioculturel, Technologique, Environnemental, Legal) dans la zone "
        "et le pays cibles. Impacts identifies pour le projet."
    ),
    "str.03.concurrentielle": (
        "Analyse concurrentielle strategique : forces de Porter (5 forces), "
        "intensite de la rivalite, pouvoir des fournisseurs et clients, "
        "menace des substituts et entrants. Positionnement resultant."
    ),
    "str.04.vision_objectifs": (
        "Vision et objectifs strategiques : definition de la vision a 3-5 "
        "ans, mission, valeurs, objectifs SMART par horizon (1 an, 3 ans, "
        "5 ans), indicateurs de mesure."
    ),
    "str.05.positionnement": (
        "Choix de positionnement strategique : segmentation retenue, "
        "cible prioritaire, proposition de valeur centrale, "
        "positionnement vs concurrents (matrice perceptuelle)."
    ),
    "str.06.entree_marche": (
        "Strategie d'entree sur le marche : mode d'entree (organique, "
        "partenariat, acquisition...), zone geographique prioritaire, "
        "plan de lancement, ressources requises, quick wins identifies."
    ),
    "str.07.croissance": (
        "Strategie de croissance et developpement : options de croissance "
        "(Ansoff : penetration, developpement marche/produit, "
        "diversification), sequencement recommande, conditions de succes."
    ),
    "str.08.differentiation": (
        "Strategie de differentiation et avantage concurrentiel durable : "
        "source de l'avantage (cout, differenciation, focalisation), "
        "caractere defensable, risques d'erosion, plan de renforcement."
    ),
    "str.09.plan_action": (
        "Plan d'action operationnel : initiatives prioritaires (top 5-7), "
        "responsable, ressources, budget estime, calendrier, risques "
        "d'execution et dependances."
    ),
    "str.10.kpis": (
        "Indicateurs de performance (KPIs) : tableau de bord strategique "
        "(5-8 KPIs cles par axe : commercial, financier, operationnel, "
        "client), valeurs cibles par annee, frequence de suivi."
    ),
    "str.11.risques_scenarios": (
        "Risques strategiques et scenarios : top 5 risques avec matrice "
        "probabilite/impact, scenario optimiste, central et pessimiste "
        "avec impacts sur les KPIs, indicateurs avances d'alerte."
    ),
    "str.12.conclusion": (
        "Conclusion et recommandations strategiques prioritaires : synthese "
        "des 3 a 5 decisions strategiques cles, prochaines etapes "
        "concretes dans les 90 prochains jours, message de clôture mentor."
    ),
}


def prompt_instruction(prompt_key: str) -> str:
    """Renvoie l'instruction chapitre, ou une consigne generique de repli."""
    return (
        MARKET_STUDY_PROMPTS.get(prompt_key)
        or COMPETITOR_STUDY_PROMPTS.get(prompt_key)
        or BUSINESS_PLAN_PROMPTS.get(prompt_key)
        or BUSINESS_STRATEGY_PROMPTS.get(prompt_key)
        or (
            "Redige ce chapitre selon la methode EVKHA : donnees chiffrees, "
            "sourcees, concretes et exploitables, ton mentor."
        )
    )

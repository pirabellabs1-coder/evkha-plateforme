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


def prompt_instruction(prompt_key: str) -> str:
    """Renvoie l'instruction chapitre, ou une consigne generique de repli."""
    return (
        MARKET_STUDY_PROMPTS.get(prompt_key)
        or COMPETITOR_STUDY_PROMPTS.get(prompt_key)
        or (
            "Redige ce chapitre selon la methode EVKHA : donnees chiffrees, "
            "sourcees, concretes et exploitables, ton mentor."
        )
    )

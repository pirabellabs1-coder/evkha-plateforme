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
        "FORMAT STRICT (Bloc 5 Consignes EVKHA) : produis EXACTEMENT un tableau "
        "Markdown a 2 colonnes (Label | Valeur), AUCUN texte autour, AUCUNE "
        "introduction, AUCUN commentaire. Les 8 lignes obligatoires dans cet "
        "ordre exact :\n"
        "| Secteur | [valeur] |\n"
        "| Pays | [valeur] |\n"
        "| Projet | [description en 1-2 phrases] |\n"
        "| Zone | [valeur] |\n"
        "| Positionnement | [synthese 1 phrase] |\n"
        "| Clientele cible | [synthese 1 phrase] |\n"
        "| Modele economique | [synthese 1 phrase] |\n"
        "| Elements a retenir | [3 a 5 points cles separes par ' / '] |\n"
        "Apres le tableau, saute une ligne et ajoute UNE SEULE section "
        "intitulee '## Questions auxquelles cette etude repond' avec une liste "
        "a puces de 4 a 5 questions implicites du porteur (formulations "
        "directes, type 'Quel est le potentiel reel du marche cible ?'). "
        "Rien d'autre. Aucune phrase meta du type 'Voici la fiche projet'."
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
        "Exactement 2 personas detailles, representatifs de la clientele cible : "
        "profil, motivations, freins, parcours d'achat. Ne pas en generer plus "
        "ni moins de 2."
    ),
    "em.12.risques_plan_gestion": (
        "Analyse des risques et plan de gestion : risques identifies, "
        "probabilite, impact, mesures de mitigation."
    ),
    "em.13.cartographie_risques": (
        "Cartographie des risques externes. Produis d'abord 2 a 3 paragraphes "
        "d'analyse contextuelle des risques macro-environnementaux. "
        "Puis genere UNE SEULE matrice HTML inline (sans balises <html>/<body>) "
        "representant la cartographie Probabilite x Impact. "
        "Format exact a respecter — remplace les exemples par les vrais risques du projet :\n"
        "<table style=\"border-collapse:collapse;width:100%;margin:4mm 0;font-size:9.5pt\">\n"
        "<thead><tr>"
        "<th style=\"background:#1A1A1A;color:#fff;padding:2mm 3mm;text-align:left\">Risque</th>"
        "<th style=\"background:#1A1A1A;color:#fff;padding:2mm 3mm;text-align:center\">Probabilite</th>"  # noqa: E501
        "<th style=\"background:#1A1A1A;color:#fff;padding:2mm 3mm;text-align:center\">Impact</th>"
        "<th style=\"background:#1A1A1A;color:#fff;padding:2mm 3mm;text-align:center\">Niveau</th>"
        "<th style=\"background:#1A1A1A;color:#fff;padding:2mm 3mm;text-align:left\">Mitigation</th>"  # noqa: E501
        "</tr></thead>\n"
        "<tbody>\n"
        "<tr><td style=\"padding:2mm 3mm;border:0.5pt solid #EFEAD8\">Risque exemple 1</td>"
        "<td style=\"padding:2mm 3mm;text-align:center;border:0.5pt solid #EFEAD8\">Elevee</td>"
        "<td style=\"padding:2mm 3mm;text-align:center;border:0.5pt solid #EFEAD8\">Fort</td>"
        "<td style=\"padding:2mm 3mm;text-align:center;background:#B73E3E;color:#fff;border:0.5pt solid #EFEAD8\">CRITIQUE</td>"  # noqa: E501
        "<td style=\"padding:2mm 3mm;border:0.5pt solid #EFEAD8\">Action corrective</td></tr>\n"
        "<tr><td colspan=\"5\" style=\"background:#FBF8EF;padding:1mm\"></td></tr>\n"
        "</tbody></table>\n"
        "Niveaux de couleur : CRITIQUE = background:#B73E3E / ELEVE = background:#E65100 / "
        "MODERE = background:#C9A227 / FAIBLE = background:#2E7D4F. Tous en color:#fff. "
        "Identifie 8 a 12 risques reels propres au secteur et a la zone. "
        "Termine par un encadre mentor synthetisant le niveau de risque global."
    ),
    "em.14.rentabilite_viabilite": (
        "Analyse de la rentabilite et de la viabilite du projet : hypotheses "
        "economiques, seuils, leviers."
    ),
    "em.15.graphiques_tableaux": (
        "Produis les graphiques et tableaux visuels cles de l'etude. "
        "Chaque graphique est genere en HTML inline (sans <html>/<body>) a l'aide "
        "de tableaux HTML avec barres CSS. Voici le pattern a suivre pour un graphique en barres "
        "(adapte les donnees reelles du projet) :\n"
        "<h3 style=\"font-size:14pt;margin:4mm 0 2mm\">Graphique 1 — Titre du graphique</h3>\n"
        "<table style=\"border-collapse:collapse;width:100%;margin:3mm 0;font-size:9.5pt\">\n"
        "<tr><td style=\"padding:1.5mm 3mm;border-bottom:0.5pt solid #EFEAD8;width:35%\">Label A</td>"  # noqa: E501
        "<td style=\"padding:1.5mm 2mm;width:55%\">"
        "<div style=\"background:#C9A227;height:5mm;width:75%;display:inline-block\"></div></td>"
        "<td style=\"padding:1.5mm 2mm;font-weight:bold;color:#1A1A1A;width:10%\">75 %</td></tr>\n"
        "</table>\n"
        "Pour chaque graphique : titre H3, tableau barres avec valeurs reelles, "
        "legende courte sous le tableau en italique. Produis entre 4 et 6 graphiques "
        "couvrant : (1) evolution du marche 2021-2026, (2) repartition CA cible par segment, "
        "(3) croissance projetee 2026-2030, (4) repartition clientele cible, "
        "(5) comparaison positionnement prix concurrents si disponible. "
        "Utilise les donnees chiffrees reelles etablies dans les chapitres precedents. "
        "Couleur principale des barres : #C9A227 (or EVKHA). Barres secondaires : #1A1A1A."
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
        "Analyse SWOT complete et specifique au projet. "
        "Commence par 1 paragraphe d'introduction. "
        "Puis genere le tableau SWOT visuel 4 cases en HTML inline (sans <html>/<body>). "
        "IMPORTANT : dans chaque cellule <td>, remplace les exemples par les vrais elements "
        "du projet. Chaque <li> = 1 a 2 phrases concretes et chiffrees.\n"
        "<table style=\"border-collapse:collapse;width:100%;margin:4mm 0;font-size:9.5pt\">\n"
        "<tr>"
        "<th style=\"background:#2E7D4F;color:#fff;padding:3mm;text-align:center;width:50%"
        ";border:0.5pt solid #EFEAD8\">Forces</th>"
        "<th style=\"background:#B73E3E;color:#fff;padding:3mm;text-align:center;width:50%"
        ";border:0.5pt solid #EFEAD8\">Faiblesses</th>"
        "</tr>\n"
        "<tr>"
        "<td style=\"vertical-align:top;padding:3mm;border:0.5pt solid #EFEAD8\">"
        "<ul><li>Force 1 du projet : argument chiffre.</li>"
        "<li>Force 2 : avantage concret.</li>"
        "<li>Force 3 : atout specifique.</li></ul></td>"
        "<td style=\"vertical-align:top;padding:3mm;border:0.5pt solid #EFEAD8\">"
        "<ul><li>Faiblesse 1 : limite reelle a assumer.</li>"
        "<li>Faiblesse 2 : contrainte interne.</li>"
        "<li>Faiblesse 3 : risque structurel.</li></ul></td>"
        "</tr>\n"
        "<tr>"
        "<th style=\"background:#1565C0;color:#fff;padding:3mm;text-align:center"
        ";border:0.5pt solid #EFEAD8\">Opportunites</th>"
        "<th style=\"background:#E65100;color:#fff;padding:3mm;text-align:center"
        ";border:0.5pt solid #EFEAD8\">Menaces</th>"
        "</tr>\n"
        "<tr>"
        "<td style=\"vertical-align:top;padding:3mm;border:0.5pt solid #EFEAD8\">"
        "<ul><li>Opportunite 1 : tendance favorable chiffree.</li>"
        "<li>Opportunite 2 : marche non sature.</li>"
        "<li>Opportunite 3 : levier externe exploitable.</li></ul></td>"
        "<td style=\"vertical-align:top;padding:3mm;border:0.5pt solid #EFEAD8\">"
        "<ul><li>Menace 1 : risque sectoriel concret.</li>"
        "<li>Menace 2 : pression concurrentielle.</li>"
        "<li>Menace 3 : evolution reglementaire.</li></ul></td>"
        "</tr>\n"
        "</table>\n"
        "Remplis chaque cellule avec 5 a 7 points reels (Forces/Opportunites) ou 4 a 6 "
        "(Faiblesses/Menaces), specifiques au projet, pas generiques. "
        "Apres le tableau SWOT, ajoute une section : "
        "## Ce que le SWOT ne vous dit pas\n"
        "Cette section (3 a 4 paragraphes) devoile les angles morts de l'analyse SWOT : "
        "les vrais risques caches derriere les forces apparentes, "
        "les opportunites sous-estimees, les faiblesses qui peuvent devenir des forces, "
        "et la lecture strategique que le porteur doit absolument faire avant de se lancer. "
        "Ton direct, mentor, sans complaisance."
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
        "Liste les sources reellement utilisees pour cette etude, regroupees "
        "par thematique (Marche, Demographie, Reglementation, Concurrence, "
        "Documents client). Format simple et lisible :\n"
        "## Marche\n- Nom de la source - URL si disponible\n"
        "## Demographie\n- ...\n"
        "Pas plus de 4-6 sources par thematique. Ajoute un tres court "
        "paragraphe (3-4 lignes) en fin de chapitre intitule '## Methodologie' "
        "expliquant la demarche (croisement de sources, periode des donnees). "
        "Rester concis et structure."
    ),
    # --- Sections de generation par chunks (chapitres denses) ---------------
    # Chaque section est generee separement puis fusionnee en un seul chapitre.
    # Les prompts sont volontairement cibles sur un sous-perimetre pour eviter
    # la troncature et maximiser la densite informationnelle par appel.
    "em.01.a.mondial": (
        "Analyse UNIQUEMENT la dimension mondiale du marche : taille actuelle "
        "en valeur (Md$, Md EUR), TCAC mondial sur 5 ans, top 5 regions par "
        "part de marche, leaders mondiaux et leurs positionnements, segments "
        "porteurs a l'echelle globale. Toutes les donnees chiffrees et sourcees. "
        "Ne traite pas la dimension europeenne dans cette section."
    ),
    "em.01.b.europeen": (
        "Analyse UNIQUEMENT la dimension europeenne du marche : taille du marche "
        "UE et/ou Europe elargie, TCAC europeen, top 5 pays europeens par "
        "volume ou valeur, specificites reglementaires et culturelles europeennes, "
        "acteurs europeens dominants et parts de marche estimees. "
        "Toutes les donnees chiffrees et sourcees. Ne repete pas les chiffres "
        "mondiaux deja traites. "
        "En fin de section, genere UN graphique HTML en barres montrant l'evolution "
        "du marche europeen sur 2021-2026 (ou mondial si europeen indisponible), "
        "en utilisant ce pattern exact (adapte valeurs et etiquettes reelles) :\n"
        "<h3 style=\"font-size:13pt;margin:4mm 0 2mm\">Evolution du marche — 2021 a 2026</h3>\n"
        "<table style=\"border-collapse:collapse;width:100%;margin:3mm 0;font-size:9pt\">\n"
        "<tr><td style=\"padding:1.5mm 3mm;border-bottom:0.5pt solid #EFEAD8;width:12%\">2021</td>"
        "<td style=\"padding:1.5mm 2mm;width:78%\">"
        "<div style=\"background:#C9A227;height:5mm;width:60%;display:inline-block\"></div></td>"
        "<td style=\"padding:1.5mm 2mm;font-weight:bold;width:10%\">XX Md€</td></tr>\n"
        "<tr><td style=\"padding:1.5mm 3mm;border-bottom:0.5pt solid #EFEAD8\">2022</td>"
        "<td style=\"padding:1.5mm 2mm\">"
        "<div style=\"background:#C9A227;height:5mm;width:65%;display:inline-block\"></div></td>"
        "<td style=\"padding:1.5mm 2mm;font-weight:bold\">XX Md€</td></tr>\n"
        "<tr><td style=\"padding:1.5mm 3mm;border-bottom:0.5pt solid #EFEAD8\">2023</td>"
        "<td style=\"padding:1.5mm 2mm\">"
        "<div style=\"background:#C9A227;height:5mm;width:70%;display:inline-block\"></div></td>"
        "<td style=\"padding:1.5mm 2mm;font-weight:bold\">XX Md€</td></tr>\n"
        "<tr><td style=\"padding:1.5mm 3mm;border-bottom:0.5pt solid #EFEAD8\">2024</td>"
        "<td style=\"padding:1.5mm 2mm\">"
        "<div style=\"background:#C9A227;height:5mm;width:78%;display:inline-block\"></div></td>"
        "<td style=\"padding:1.5mm 2mm;font-weight:bold\">XX Md€</td></tr>\n"
        "<tr><td style=\"padding:1.5mm 3mm;border-bottom:0.5pt solid #EFEAD8\">2025</td>"
        "<td style=\"padding:1.5mm 2mm\">"
        "<div style=\"background:#1A1A1A;height:5mm;width:86%;display:inline-block\"></div></td>"
        "<td style=\"padding:1.5mm 2mm;font-weight:bold\">XX Md€ est.</td></tr>\n"
        "<tr><td style=\"padding:1.5mm 3mm\">2026</td>"
        "<td style=\"padding:1.5mm 2mm\">"
        "<div style=\"background:#1A1A1A;height:5mm;width:93%;display:inline-block\"></div></td>"
        "<td style=\"padding:1.5mm 2mm;font-weight:bold\">XX Md€ proj.</td></tr>\n"
        "</table>\n"
        "<p style=\"font-style:italic;font-size:8.5pt;color:#5A5A5A\">Sources : [cite tes sources]. "  # noqa: E501
        "Est. = estimation. Proj. = projection argumentee.</p>\n"
        "Remplace chaque XX par les vraies valeurs etablies dans l'analyse."
    ),
    "em.02.a.national": (
        "Analyse UNIQUEMENT le marche national du pays cible (extrait de "
        "VARIABLES_PROJET) : taille en valeur et/ou volume, TCAC national, "
        "maturite du marche, structure (acteurs dominants, concentration, "
        "distribution), specificites nationales (reglementation, habitudes "
        "de consommation). Chiffres et sources."
    ),
    "em.02.b.local": (
        "Analyse UNIQUEMENT la zone locale ou regionale cible (extraite de "
        "VARIABLES_PROJET) : taille estimee (valeur ou volume), dynamiques "
        "propres a cette zone (urbanisation, revenus locaux, demande latente), "
        "specificites geographiques pertinentes, estimations argumentees si "
        "donnees directes indisponibles. Ne repete pas les chiffres nationaux. "
        "En fin de section, genere UN graphique HTML en barres montrant la repartition "
        "ou la dynamique du marche local par segment ou par annee, en utilisant ce "
        "pattern exact (adapte valeurs et etiquettes au contexte reel) :\n"
        "<h3 style=\"font-size:13pt;margin:4mm 0 2mm\">Repartition du marche local — segments cles</h3>\n"  # noqa: E501
        "<table style=\"border-collapse:collapse;width:100%;margin:3mm 0;font-size:9pt\">\n"
        "<tr><td style=\"padding:1.5mm 3mm;border-bottom:0.5pt solid #EFEAD8;width:30%\">Segment A</td>"  # noqa: E501
        "<td style=\"padding:1.5mm 2mm;width:60%\">"
        "<div style=\"background:#C9A227;height:5mm;width:72%;display:inline-block\"></div></td>"
        "<td style=\"padding:1.5mm 2mm;font-weight:bold;width:10%\">XX %</td></tr>\n"
        "<tr><td style=\"padding:1.5mm 3mm;border-bottom:0.5pt solid #EFEAD8\">Segment B</td>"
        "<td style=\"padding:1.5mm 2mm\">"
        "<div style=\"background:#C9A227;height:5mm;width:50%;display:inline-block\"></div></td>"
        "<td style=\"padding:1.5mm 2mm;font-weight:bold\">XX %</td></tr>\n"
        "<tr><td style=\"padding:1.5mm 3mm\">Segment C</td>"
        "<td style=\"padding:1.5mm 2mm\">"
        "<div style=\"background:#1A1A1A;height:5mm;width:28%;display:inline-block\"></div></td>"
        "<td style=\"padding:1.5mm 2mm;font-weight:bold\">XX %</td></tr>\n"
        "</table>\n"
        "<p style=\"font-style:italic;font-size:8.5pt;color:#5A5A5A\">"
        "Source : [cite ta source]. Estimations argumentees sur la base des donnees disponibles.</p>\n"  # noqa: E501
        "Remplace Segment A/B/C et XX par les vraies donnees etablies dans l'analyse."
    ),
    "em.10.a.profil_besoins": (
        "Decris UNIQUEMENT le profil demographique et socio-economique de la "
        "clientele cible : tranche d'age dominante, genre, CSP, niveau de "
        "revenu, zone de residence. Puis identifie les besoins primaires (non "
        "couverts ou mal couverts) et secondaires, et les douleurs actuelles "
        "que le projet peut resoudre. Donne la taille estimee du segment "
        "cible en nombre ou en valeur."
    ),
    "em.10.b.comportements": (
        "Decris UNIQUEMENT les comportements d'achat de la clientele cible : "
        "canaux d'achat preferes (physique, digital, mixte), frequence d'achat, "
        "panier moyen, moments d'achat (saisonnalite, evenements declencheurs), "
        "parcours client type du besoin a l'acte d'achat, moments de verite cles."
    ),
    "em.10.c.criteres_decision": (
        "Analyse UNIQUEMENT les criteres de decision d'achat de la clientele "
        "cible, hierarchises : prix, qualite percue, confiance/marque, "
        "commodite, service apres-vente. Sensibilite au prix (elasticite), "
        "niveau d'exigence, fidelite habituelle au secteur ou au prestataire, "
        "barrieres au changement et leviers pour les surmonter."
    ),
    "em.14.a.hypotheses": (
        "Pose et justifie UNIQUEMENT les hypotheses economiques du projet : "
        "prix de vente retenu (et positionnement vs concurrents), volume "
        "cible annee 1/2/3, structure de couts (fixes et variables cles), "
        "marge brute estimee. Chaque hypothese doit etre declaree et "
        "argumentee (reference marche, benchmark, logique sectorielle)."
    ),
    "em.14.b.projections": (
        "Produis UNIQUEMENT les projections financieres sur 3 ans sous forme "
        "de tableau exploitable : chiffre d'affaires, charges d'exploitation, "
        "EBITDA, resultat net, point mort en quantite et en date, tresorerie "
        "previsionnelle. Scenario central + fourchette (optimiste/pessimiste). "
        "Ne repete pas les hypotheses deja exposees."
    ),
    "em.14.c.viabilite": (
        "Analyse UNIQUEMENT la viabilite et les leviers du projet : analyse de "
        "sensibilite (quelles variables impactent le plus la rentabilite), "
        "facteurs cles de succes economique, risques financiers principaux "
        "(delai de paiement, sous-capitalisation, saisonnalite) et mesures "
        "correctives concretes recommandees."
    ),
    "em.19.a.diagnostic": (
        "Produis UNIQUEMENT le diagnostic strategique synthetique : 3 a 5 "
        "enseignements majeurs de l'etude (chiffres cles qui changent la "
        "vision), lecture de la position concurrentielle du projet (force "
        "relative, gaps a combler), 3 tensions ou contradictions a resoudre "
        "avant de se lancer. Sois critique et direct, sans complaisance."
    ),
    "em.19.b.plan_action": (
        "Produis UNIQUEMENT les recommandations actionnables et priorisees : "
        "top 5 actions immediates (0-6 mois) avec responsable suggere et "
        "impact attendu, 3 orientations moyen terme (6-24 mois), 1 signal "
        "d'alerte a surveiller absolument. Pour chaque recommandation : quoi "
        "faire, pourquoi, et quel indicateur prouvera le succes."
    ),
}

# --- Etude de la concurrence (EC) ----------------------------------------

COMPETITOR_STUDY_PROMPTS: dict[str, str] = {
    "ec.00.fiche_projet": (
        "FORMAT STRICT (Bloc 5 Consignes EVKHA) : produis EXACTEMENT un tableau "
        "Markdown a 2 colonnes (Label | Valeur), AUCUN texte autour, AUCUNE "
        "introduction, AUCUN commentaire. Les 8 lignes obligatoires dans cet "
        "ordre exact :\n"
        "| Secteur | [valeur] |\n"
        "| Pays | [valeur] |\n"
        "| Projet | [description en 1-2 phrases] |\n"
        "| Zone | [valeur] |\n"
        "| Positionnement | [synthese 1 phrase] |\n"
        "| Clientele cible | [synthese 1 phrase] |\n"
        "| Modele economique | [synthese 1 phrase] |\n"
        "| Elements a retenir | [3 a 5 points cles separes par ' / '] |\n"
        "Apres le tableau, saute une ligne et ajoute UNE SEULE section "
        "intitulee '## Questions auxquelles cette etude repond' avec une liste "
        "a puces de 4 a 5 questions implicites du porteur orientees benchmark "
        "concurrentiel (type 'Qui sont les concurrents directs les plus serieux ?'). "
        "Rien d'autre."
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
        "pertinents (ex. prix / qualite percue, ou positionnement premium / "
        "accessible). "
        "ETAPE OBLIGATOIRE : le tableau HTML ci-dessous DOIT apparaitre dans ta "
        "reponse, rempli avec les donnees reelles. Ce n'est pas une option ni un "
        "exemple a paraphraser : une reponse qui decrit la matrice uniquement en "
        "texte, sans le tableau HTML, est un echec. Le contenu de chaque cellule "
        "reste court (une ligne, style fiche : nom de l'acteur + 3-6 mots de "
        "qualification), jamais un paragraphe complet — les paragraphes "
        "d'interpretation viennent APRES le tableau, pas dedans. "
        "Genere d'abord la matrice en HTML inline (sans <html>/<body>) sous forme "
        "de grille 3x3 representant les 4 quadrants autour d'un centre, chaque "
        "concurrent et le projet places dans la cellule correspondant a sa "
        "position reelle. Voici le pattern a suivre (adapte les libelles d'axes "
        "et le contenu des cellules aux donnees reelles) :\n"
        "<table style=\"border-collapse:collapse;width:100%;margin:4mm 0;"
        "font-size:9pt;table-layout:fixed\">\n"
        "<tr><td colspan=\"3\" style=\"text-align:center;padding:1mm;"
        "font-weight:bold;color:#1A1A1A\">Axe vertical (ex. Qualite percue +)</td>"
        "</tr>\n"
        "<tr>"
        "<td style=\"height:28mm;vertical-align:top;padding:2mm;"
        "border:0.5pt solid #EFEAD8;background:#FBF8EF\">Acteur A</td>"
        "<td style=\"height:28mm;vertical-align:top;padding:2mm;"
        "border:0.5pt solid #EFEAD8;background:#FBF8EF\">Acteur B</td>"
        "<td style=\"height:28mm;vertical-align:top;padding:2mm;"
        "border:0.5pt solid #EFEAD8;background:#FBF8EF\">Acteur C</td>"
        "</tr>\n"
        "<tr>"
        "<td style=\"height:28mm;vertical-align:top;padding:2mm;"
        "border:0.5pt solid #EFEAD8\">Acteur D</td>"
        "<td style=\"height:28mm;vertical-align:top;padding:2mm;"
        "border:0.5pt solid #EFEAD8;background:#C9A22733;font-weight:bold;"
        "color:#1A1A1A\">Projet (position visee)</td>"
        "<td style=\"height:28mm;vertical-align:top;padding:2mm;"
        "border:0.5pt solid #EFEAD8\">Acteur E</td>"
        "</tr>\n"
        "<tr>"
        "<td style=\"height:28mm;vertical-align:top;padding:2mm;"
        "border:0.5pt solid #EFEAD8;background:#FBF8EF\">Acteur F</td>"
        "<td style=\"height:28mm;vertical-align:top;padding:2mm;"
        "border:0.5pt solid #EFEAD8;background:#FBF8EF\">Acteur G</td>"
        "<td style=\"height:28mm;vertical-align:top;padding:2mm;"
        "border:0.5pt solid #EFEAD8;background:#FBF8EF\">Acteur H</td>"
        "</tr>\n"
        "<tr><td colspan=\"3\" style=\"text-align:center;padding:1mm;"
        "font-weight:bold;color:#1A1A1A\">Axe horizontal (ex. Prix bas -&gt; Prix eleve)</td>"
        "</tr>\n"
        "</table>\n"
        "Place chaque concurrent identifie dans les chapitres precedents dans la "
        "cellule qui correspond a sa position reelle sur les 2 axes (n'utilise pas "
        "obligatoirement les 9 cellules, ne remplis que celles pertinentes, "
        "laisse une cellule vide plutot que d'inventer un acteur). Mets le projet "
        "en surbrillance (couleur #C9A22733) dans la cellule visee. "
        "Apres la matrice, interprete en 2 a 3 paragraphes : zones saturees, "
        "espaces libres, risques de cannibalisation."
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
        "differenciants des le lancement. "
        "Avant la conclusion textuelle, genere 4 graphiques en HTML inline (sans "
        "<html>/<body>) a l'aide de tableaux HTML avec barres CSS, sur le meme "
        "modele que les graphiques du chapitre marche : titre H3, tableau barres "
        "avec valeurs reelles, legende courte en italique sous chaque tableau. "
        "Pattern a suivre pour chaque graphique en barres (adapte les donnees "
        "reelles) :\n"
        "<h3 style=\"font-size:14pt;margin:4mm 0 2mm\">Graphique 1 — Titre</h3>\n"
        "<table style=\"border-collapse:collapse;width:100%;margin:3mm 0;"
        "font-size:9.5pt\">\n"
        "<tr><td style=\"padding:1.5mm 3mm;border-bottom:0.5pt solid #EFEAD8;"
        "width:35%\">Label A</td>"
        "<td style=\"padding:1.5mm 2mm;width:55%\">"
        "<div style=\"background:#C9A227;height:5mm;width:75%;"
        "display:inline-block\"></div></td>"
        "<td style=\"padding:1.5mm 2mm;font-weight:bold;color:#1A1A1A;width:10%\">"
        "75 %</td></tr>\n"
        "</table>\n"
        "Les 4 graphiques a produire : "
        "(1) parts de marche des principaux concurrents identifies (barres, %), "
        "(2) repartition des canaux de distribution/acquisition du marche "
        "(barres, %), "
        "(3) comparatif forces/faiblesses des 2-3 concurrents principaux face au "
        "projet : une ligne par critere (prix, qualite, notoriete, digital...), "
        "une barre par acteur avec sa couleur propre (#C9A227 pour le projet, "
        "#1A1A1A pour les concurrents), "
        "(4) carte synthetique des concurrents par categorie (directs, indirects, "
        "emergents) sous forme de tableau a 3 colonnes listant les acteurs de "
        "chaque categorie. "
        "Utilise les donnees chiffrees reelles etablies dans les chapitres "
        "precedents, jamais de valeurs inventees sans base. "
        "Termine par la conclusion analytique textuelle demandee ci-dessus."
    ),
    "ec.08.annexe_brief": (
        "Annexe finale : pour chaque demande specifique du client, indique si "
        "elle est traitee, partiellement traitee ou non traitee, avec une phrase "
        "explicative le cas echeant."
    ),
    "ec.09.sources": (
        "Liste les sources reellement utilisees pour cette etude concurrentielle, "
        "regroupees par thematique (Concurrents identifies, Donnees de marche, "
        "Avis clients, Publications sectorielles). Format simple :\n"
        "## Concurrents identifies\n- Nom - URL si disponible\n"
        "## Donnees de marche\n- ...\n"
        "Pas plus de 4-6 sources par thematique. Ajoute un court paragraphe "
        "'## Methodologie' (3-4 lignes) expliquant la demarche de benchmark "
        "(perimetre, critere de selection des concurrents, periode des avis). "
        "Rester concis et structure."
    ),
}


# --- Business Plan (BP) --------------------------------------------------
# Prompts alignes avec la spec officielle EVKHA V1 (mai 2026).
# Chapitres 2-11 bases sur les objectifs de la spec ; chapitres 12-19
# bases sur le squelette FIRE EVENT valide. Ton : narratif, ecrit comme
# si le porteur s'exprimait lui-meme, credible pour un banquier/investisseur.
# Ne jamais ecrire "Etape", "Validation", "Pipeline" ni tout marqueur interne.

BUSINESS_PLAN_PROMPTS: dict[str, str] = {
    "bp.00.fiche_projet": (
        "FORMAT STRICT (Bloc 5 Consignes EVKHA) : produis EXACTEMENT un tableau "
        "Markdown a 2 colonnes (Label | Valeur), AUCUN texte autour, AUCUNE "
        "introduction, AUCUN commentaire. Les 8 lignes obligatoires dans cet "
        "ordre exact :\n"
        "| Secteur | [valeur] |\n"
        "| Pays | [valeur] |\n"
        "| Projet | [description en 1-2 phrases] |\n"
        "| Zone | [valeur] |\n"
        "| Positionnement | [synthese 1 phrase] |\n"
        "| Clientele cible | [synthese 1 phrase] |\n"
        "| Modele economique | [synthese 1 phrase] |\n"
        "| Elements a retenir | [3 a 5 points cles separes par ' / '] |\n"
        "Apres le tableau, saute une ligne et ajoute UNE SEULE section "
        "intitulee '## Questions auxquelles ce business plan repond' avec une "
        "liste a puces de 4 a 5 questions implicites du porteur orientees "
        "viabilite et financement (type 'Le projet est-il rentable des l'annee 1 ?'). "
        "Rien d'autre."
    ),
    "bp.01.resume_executif": (
        "Resume executif (1 page maximum) : presentation synthetique du "
        "projet et de son activite, historique et contexte du demarrage, "
        "objectifs de creation ou de structuration, chiffres cles "
        "previsionnels sur 3 ans, vision globale et message central. "
        "Percutant et clair, ecrit comme si le porteur s'exprimait."
    ),
    "bp.02.porteur_projet": (
        "Presente le porteur de projet de maniere a construire sa "
        "legitimite entrepreneuriale, professionnelle et humaine : parcours, "
        "experience metier dans le secteur, competences techniques et "
        "operationnelles, vision entrepreneuriale, implication personnelle. "
        "Redigez comme un dirigeant en construction, pas comme un CV."
    ),
    "bp.03.genese_projet": (
        "Raconte l'histoire du projet depuis son origine : pourquoi ce "
        "projet existe, comment il s'est construit dans le temps, quelles "
        "etapes ont valide la demarche, pourquoi ce moment est le bon pour "
        "franchir l'etape actuelle. Cree une trajectoire credible et assumee."
    ),
    "bp.04.activite": (
        "Presente l'activite de maniere claire et structuree : ce que vend "
        "reellement l'entreprise, comment fonctionne l'activite, a quels "
        "besoins elle repond, a qui elle s'adresse, comment elle genere ses "
        "revenus. Le lecteur doit comprendre sans connaissance prealable du secteur."
    ),
    "bp.05.positionnement_concept": (
        "Definit clairement le positionnement strategique : quelle place le "
        "projet occupe sur son marche, a quels besoins precis il repond, "
        "pourquoi des clients choisiraient cette offre plutot qu'une autre, "
        "comment le projet se distingue concretement de la concurrence."
    ),
    "bp.06.marche_synthese": (
        "Synthese strategique du marche cible : taille et dynamique, "
        "segments prioritaires, tendances favorables au projet, clientele "
        "cible et ses besoins. Produit une lecture business claire, pas une "
        "etude exhaustive. Relie systematiquement les donnees au projet concret."
    ),
    "bp.07.concurrentielle": (
        "Lecture strategique du paysage concurrentiel : acteurs directs et "
        "indirects identifies et analyses, positionnement du projet par "
        "rapport a la concurrence, espaces strategiques disponibles, "
        "avantage differenciant defendable du projet. Nombre limite de "
        "concurrents (8 directs + 3 indirects maximum), traites avec rigueur."
    ),
    "bp.08.offre_commerciale": (
        "Presente concretement l'offre : ce qui est vendu, comment l'offre "
        "est structuree (niveaux, gammes, options), politique tarifaire et "
        "logique de prix moyen, coherence entre l'offre et le positionnement. "
        "Demontre que l'offre a ete pensee et economiquement reflechie."
    ),
    "bp.09.modele_bmc": (
        "Presente la logique economique globale : comment l'entreprise cree "
        "de la valeur, comment elle genere du chiffre d'affaires, structure "
        "des couts principaux, marge brute estimee, point mort. "
        "Puis genere le Business Model Canvas en HTML inline (sans "
        "<html>/<body>) sous forme de grille visuelle a 9 blocs. IMPORTANT : "
        "remplace les exemples par le contenu reel du projet, 2 a 3 elements "
        "concrets par bloc.\n"
        "<table style=\"border-collapse:collapse;width:100%;margin:4mm 0;"
        "font-size:8.5pt;table-layout:fixed\">\n"
        "<tr>"
        "<td rowspan=\"2\" style=\"vertical-align:top;padding:2mm;"
        "border:0.5pt solid #EFEAD8;background:#FBF8EF\">"
        "<strong style=\"color:#1A1A1A\">Partenaires cles</strong>"
        "<ul><li>Element 1</li><li>Element 2</li></ul></td>"
        "<td style=\"vertical-align:top;padding:2mm;border:0.5pt solid #EFEAD8;"
        "background:#FBF8EF\"><strong style=\"color:#1A1A1A\">Activites cles"
        "</strong><ul><li>Element 1</li><li>Element 2</li></ul></td>"
        "<td rowspan=\"2\" style=\"vertical-align:top;padding:2mm;"
        "border:0.5pt solid #EFEAD8;background:#C9A22733\">"
        "<strong style=\"color:#1A1A1A\">Proposition de valeur</strong>"
        "<ul><li>Element 1</li><li>Element 2</li></ul></td>"
        "<td style=\"vertical-align:top;padding:2mm;border:0.5pt solid #EFEAD8;"
        "background:#FBF8EF\"><strong style=\"color:#1A1A1A\">Relation client"
        "</strong><ul><li>Element 1</li></ul></td>"
        "<td rowspan=\"2\" style=\"vertical-align:top;padding:2mm;"
        "border:0.5pt solid #EFEAD8;background:#FBF8EF\">"
        "<strong style=\"color:#1A1A1A\">Segments clients</strong>"
        "<ul><li>Element 1</li><li>Element 2</li></ul></td>"
        "</tr>\n"
        "<tr>"
        "<td style=\"vertical-align:top;padding:2mm;border:0.5pt solid #EFEAD8;"
        "background:#FBF8EF\"><strong style=\"color:#1A1A1A\">Ressources cles"
        "</strong><ul><li>Element 1</li></ul></td>"
        "<td style=\"vertical-align:top;padding:2mm;border:0.5pt solid #EFEAD8;"
        "background:#FBF8EF\"><strong style=\"color:#1A1A1A\">Canaux</strong>"
        "<ul><li>Element 1</li></ul></td>"
        "</tr>\n"
        "<tr>"
        "<td colspan=\"2\" style=\"vertical-align:top;padding:2mm;"
        "border:0.5pt solid #EFEAD8;background:#1A1A1A;color:#fff\">"
        "<strong>Structure de couts</strong><ul><li>Element 1</li>"
        "<li>Element 2</li></ul></td>"
        "<td colspan=\"3\" style=\"vertical-align:top;padding:2mm;"
        "border:0.5pt solid #EFEAD8;background:#1A1A1A;color:#fff\">"
        "<strong>Sources de revenus</strong><ul><li>Element 1</li>"
        "<li>Element 2</li></ul></td>"
        "</tr>\n"
        "</table>"
    ),
    "bp.10.strategie_commerciale": (
        "Strategie d'acquisition et de developpement commercial : canaux "
        "d'acquisition actuels et envisages, politique de prix assumee, "
        "plan de visibilite (reseaux, partenariats, bouche-a-oreille), "
        "objectifs commerciaux par annee, logique de fidelisation."
    ),
    "bp.11.strategie_developpement": (
        "Trajectoire de developpement du projet : phasage strategique sur "
        "3 ans (structuration / croissance maitrisee / consolidation), "
        "jalons cles par phase, logique de montee en charge progressive. "
        "La strategie doit etre financable et operationnellement realiste."
    ),
    "bp.12.organisation_moyens": (
        "Organisation humaine et moyens materiels : role du dirigeant, "
        "equipe actuelle et recrutements envisages, moyens materiels "
        "existants et a acquerir, locaux et equipements, fournisseurs "
        "strategiques. Coherent avec le stade de developpement du projet."
    ),
    "bp.13.structure_juridique": (
        "Structure juridique et reglementaire : forme juridique retenue et "
        "justification, regime fiscal, statut social du dirigeant, "
        "contraintes reglementaires specifiques au secteur et a la zone, "
        "protection de la marque ou propriete intellectuelle si applicable."
    ),
    "bp.14.investissements": (
        "Investissements et besoins au demarrage : nature et montant des "
        "investissements initiaux, apports en nature eventuels, besoin en "
        "fonds de roulement, tresorerie de securite minimale requise. "
        "Chiffres argumentes et coherents avec l'activite."
    ),
    "bp.15.plan_financement": (
        "Plan de financement initial : synthese des besoins de demarrage, "
        "ressources mobilisees (apports propres, emprunt bancaire, "
        "subventions, investisseurs), equilibre du plan. "
        "Logique financiere transparente et defensable. "
        "Puis genere en HTML inline (sans <html>/<body>) un graphique barres "
        "de la repartition des ressources de financement (adapte les donnees "
        "reelles), sur ce pattern :\n"
        "<h3 style=\"font-size:14pt;margin:4mm 0 2mm\">Repartition des ressources "
        "de financement</h3>\n"
        "<table style=\"border-collapse:collapse;width:100%;margin:3mm 0;"
        "font-size:9.5pt\">\n"
        "<tr><td style=\"padding:1.5mm 3mm;border-bottom:0.5pt solid #EFEAD8;"
        "width:35%\">Apport personnel</td>"
        "<td style=\"padding:1.5mm 2mm;width:55%\">"
        "<div style=\"background:#C9A227;height:5mm;width:40%;"
        "display:inline-block\"></div></td>"
        "<td style=\"padding:1.5mm 2mm;font-weight:bold;color:#1A1A1A;"
        "width:10%\">40 %</td></tr>\n"
        "</table>\n"
        "Une ligne par source de financement reelle du projet, legende courte "
        "en italique sous le tableau."
    ),
    "bp.16.previsionnel_financier": (
        "Previsionnel financier sur 3 ans : compte de resultat previsionnel "
        "(CA, charges fixes et variables, EBITDA, resultat net), hypotheses "
        "clairement declarees et argumentees, seuil de rentabilite, "
        "capacite d'autofinancement. Scenario central + sensibilite. "
        "Puis genere en HTML inline (sans <html>/<body>) un graphique barres "
        "de l'evolution du CA et de l'EBITDA sur les 3 annees, meme pattern "
        "que les graphiques barres EVKHA (titre H3, tableau, barre "
        "#C9A227 pour le CA, barre #1A1A1A pour l'EBITDA, valeurs reelles "
        "en euros, legende courte en italique)."
    ),
    "bp.17.budget_tresorerie": (
        "Budget de tresorerie mensuel : logique de tresorerie sur 12-24 "
        "mois, integration de la saisonnalite, evolution du solde, "
        "securisation financiere. Fournis un tableau exploitable mois par mois. "
        "Puis genere en HTML inline (sans <html>/<body>) un graphique barres "
        "de l'evolution du solde de tresorerie sur 6 mois representatifs "
        "(incluant le point bas et le point haut de l'annee), meme pattern "
        "que les graphiques barres EVKHA (titre H3, tableau, barre #C9A227, "
        "valeurs reelles en euros, legende courte en italique)."
    ),
    "bp.18.risques_securisation": (
        "Risques identifies et facteurs de securisation : principaux risques "
        "(saisonnalite, dependance, concurrence, reglementation), leur "
        "probabilite et impact, leviers de securisation concrets pour chacun. "
        "Lecture lucide sans dramatisation."
    ),
    "bp.19.conclusion": (
        "Conclusion strategique : synthese des points forts du projet, "
        "coherence economique et viabilite, adequation avec les objectifs "
        "du porteur, message final donnant confiance au lecteur. "
        "Ton positif et credible, pas commercial."
    ),
    "bp.20.annexes": (
        "Annexes : reponses explicites a chaque demande specifique du client "
        "(traitee / partiellement / non traitee + explication). "
        "Documents justificatifs et simulations complementaires si demandes."
    ),
    "bp.21.sources": (
        "Liste les sources utilisees pour construire ce business plan, "
        "regroupees par thematique (Donnees sectorielles, Reglementation, "
        "Financements et aides, Concurrence, Documents fournis par le porteur). "
        "Format simple :\n"
        "## Donnees sectorielles\n- Nom - URL si disponible\n"
        "## Reglementation\n- ...\n"
        "Pas plus de 4-6 sources par thematique. Ajoute un court paragraphe "
        "'## Methodologie' (3-4 lignes) precisant la demarche (periode des "
        "donnees, hypotheses financieres assumees). Rester concis et structure."
    ),
}

# --- Strategie Business (STR) --------------------------------------------
# Prompts alignes avec la spec officielle EVKHA V1 (mai 2026).
# 17 chapitres analytiques + sources. Logique : diagnostic -> choix ->
# action. Objectif : aider un dirigeant a piloter avec une vision claire.

BUSINESS_STRATEGY_PROMPTS: dict[str, str] = {
    "str.00.fiche_projet": (
        "FORMAT STRICT (Bloc 5 Consignes EVKHA) : produis EXACTEMENT un tableau "
        "Markdown a 2 colonnes (Label | Valeur), AUCUN texte autour, AUCUNE "
        "introduction, AUCUN commentaire. Les 8 lignes obligatoires dans cet "
        "ordre exact :\n"
        "| Secteur | [valeur] |\n"
        "| Pays | [valeur] |\n"
        "| Projet | [description en 1-2 phrases] |\n"
        "| Zone | [valeur] |\n"
        "| Positionnement | [synthese 1 phrase] |\n"
        "| Clientele cible | [synthese 1 phrase] |\n"
        "| Modele economique | [synthese 1 phrase] |\n"
        "| Elements a retenir | [3 a 5 points cles separes par ' / '] |\n"
        "Apres le tableau, saute une ligne et ajoute UNE SEULE section "
        "intitulee '## Questions auxquelles cette strategie repond' avec une "
        "liste a puces de 4 a 5 questions implicites du dirigeant orientees "
        "pilotage (type 'Quelles activites doivent devenir centrales et "
        "lesquelles abandonner ?'). Rien d'autre."
    ),
    "str.01.introduction": (
        "Introduction strategique generale : pose le cadre du document, "
        "explique pourquoi il existe et ce qu'il apportera concretement au "
        "dirigeant, distingue pilotage strategique et execution operationnelle. "
        "Transforme immediatement le livrable d'un rapport en outil de pilotage."
    ),
    "str.02.lecture_strategique": (
        "Lecture strategique du projet : analyse la situation reelle du "
        "business, son niveau de maturite, sa logique economique actuelle, "
        "ses enjeux de developpement. Produit un diagnostic de depart "
        "lucide qui sert de socle a tout le raisonnement strategique."
    ),
    "str.03.positionnement_actuel": (
        "Analyse du positionnement actuel : quelle place occupe reellement "
        "l'entreprise sur son marche, comment est-elle percue, coherence "
        "entre image / offre / cible / prix / ambition. Identifie les "
        "risques de dilution ou de confusion de positionnement."
    ),
    "str.04.forces_structurelles": (
        "Analyse des forces structurelles du business : identifie les "
        "veritables atouts internes (pas seulement des avantages de confort), "
        "evalue les ressources et avantages concurrentiels reels sur lesquels "
        "le developpement futur peut s'appuyer solidement. "
        "Puis genere en HTML inline (sans <html>/<body>) un encadre visuel "
        "listant les 4 a 5 forces principales avec un niveau de solidite "
        "(barre CSS), sur ce pattern (adapte au contenu reel) :\n"
        "<table style=\"border-collapse:collapse;width:100%;margin:3mm 0;"
        "font-size:9.5pt\">\n"
        "<tr><td style=\"padding:1.5mm 3mm;border-bottom:0.5pt solid #EFEAD8;"
        "width:45%\">Force 1 : libelle concret</td>"
        "<td style=\"padding:1.5mm 2mm;width:45%\">"
        "<div style=\"background:#2E7D4F;height:5mm;width:80%;"
        "display:inline-block\"></div></td>"
        "<td style=\"padding:1.5mm 2mm;font-weight:bold;color:#1A1A1A;"
        "width:10%\">Solide</td></tr>\n"
        "</table>"
    ),
    "str.05.contraintes_fragilites": (
        "Analyse des contraintes et fragilites structurelles : identifie "
        "les vulnerabilites reelles du business, les risques structurels, "
        "les dependances critiques, les limites du modele actuel. "
        "Lecture lucide sans dramatisation ni complaisance. "
        "Puis genere en HTML inline (sans <html>/<body>) un encadre visuel "
        "listant les 4 a 5 fragilites principales avec un niveau de criticite "
        "(barre CSS), meme pattern que le graphique du chapitre precedent mais "
        "en couleur #B73E3E (rouge) au lieu de #2E7D4F, avec des niveaux "
        "Critique / Elevee / Moderee au lieu de Solide."
    ),
    "str.06.enjeux_positionnement": (
        "Enjeux strategiques du positionnement : demontre pourquoi la "
        "clarification du positionnement est un levier central, risques "
        "d'un positionnement flou, prepare la logique de specialisation "
        "et de differenciation structuree."
    ),
    "str.07.verticales_strategiques": (
        "Definition et priorisation des verticales strategiques : quelles "
        "activites doivent devenir centrales, lesquelles restent secondaires, "
        "lesquelles risquent de nuire a la coherence. Transforme un ensemble "
        "d'activites multiples en architecture strategique structuree."
    ),
    "str.08.valeur_differenciation": (
        "Proposition de valeur et differenciation : formalise la proposition "
        "de valeur du business, identifie les elements differenciants reels, "
        "clarifie pourquoi les clients doivent choisir cette entreprise. "
        "Transforme des qualites implicites en differenciation strategique assumee."
    ),
    "str.09.offres_actuelles": (
        "Lecture strategique des offres actuelles : analyse les offres "
        "existantes, evalue leur coherence avec le positionnement et la "
        "rentabilite, identifie les problemes de structuration commerciale "
        "ou de lisibilite pour les clients."
    ),
    "str.10.architecture_offre": (
        "Architecture d'offre cible : construit une structure d'offres "
        "coherente (niveaux de gamme, roles de chaque offre, parcours de "
        "valeur client), transforme une offre dispersee en architecture "
        "lisible et hierarchisee."
    ),
    "str.11.montee_gamme": (
        "Logique de montee en gamme et valeur percue : analyse comment "
        "mieux valoriser le business, structurer la montee en gamme, "
        "ameliorer la rentabilite sans necessairement trouver plus de clients. "
        "Propose des leviers concrets et actionnables."
    ),
    "str.12.canaux_acquisition": (
        "Analyse des canaux et acquisition actuelle : quels canaux "
        "l'entreprise utilise pour attirer des clients, leur coherence "
        "strategique, leur efficacite reelle, les desequilibres eventuels "
        "entre les differentes sources d'opportunites."
    ),
    "str.13.strategie_visibilite": (
        "Strategie de visibilite et acquisition coherente : construit une "
        "strategie d'acquisition alignee avec le positionnement, les offres "
        "et les verticales. Tous les canaux proposes sont justifies et "
        "connectes a la logique strategique globale."
    ),
    "str.14.rentabilite_modele": (
        "Lecture economique et rentabilite du modele : analyse la logique "
        "economique reelle, identifie les activites reellement rentables, "
        "evalue la soutenabilite financiere, comprend comment l'entreprise "
        "cree vraiment de la valeur. Va au-dela du simple chiffre d'affaires. "
        "Puis genere en HTML inline (sans <html>/<body>) un graphique barres "
        "comparant la rentabilite reelle des differentes activites ou offres "
        "du business (meme pattern que les graphiques barres EVKHA : titre "
        "H3, tableau, barre #C9A227 pour les activites rentables, barre "
        "#B73E3E pour celles qui ne le sont pas, valeurs reelles en % ou en "
        "euros, legende courte en italique)."
    ),
    "str.15.arbitrages_ressources": (
        "Arbitrages strategiques et allocation des ressources : quelles "
        "priorites retenir, quelles opportunites ecarter meme si elles "
        "generent du CA a court terme, comment allouer les ressources "
        "limitees de maniere coherente avec la vision."
    ),
    "str.16.pilotage_soutenabilite": (
        "Pilotage strategique et soutenabilite du business : comment "
        "l'entreprise peut se developper sans se fragiliser, sortir d'une "
        "logique purement reactive, indicateurs de pilotage a mettre en "
        "place, conditions de la soutenabilite humaine et financiere."
    ),
    "str.17.feuille_route": (
        "Feuille de route strategique et priorisation : actions prioritaires "
        "a court terme (0-3 mois), orientations a moyen terme (3-12 mois), "
        "cap a long terme (1-3 ans). Pour chaque action : quoi faire, "
        "pourquoi, quel indicateur prouvera le succes. "
        "Avant le detail textuel, genere une frise chronologique visuelle en "
        "HTML inline (sans <html>/<body>) avec 3 blocs colores cote a cote, "
        "sur ce pattern (remplace les exemples par les actions reelles, 2 a 3 "
        "actions cle par bloc) :\n"
        "<table style=\"border-collapse:collapse;width:100%;margin:4mm 0;"
        "font-size:9pt;table-layout:fixed\">\n"
        "<tr>"
        "<th style=\"background:#C9A227;color:#1A1A1A;padding:2mm;"
        "text-align:center;border:0.5pt solid #EFEAD8\">Court terme "
        "(0-3 mois)</th>"
        "<th style=\"background:#1A1A1A;color:#fff;padding:2mm;"
        "text-align:center;border:0.5pt solid #EFEAD8\">Moyen terme "
        "(3-12 mois)</th>"
        "<th style=\"background:#2E7D4F;color:#fff;padding:2mm;"
        "text-align:center;border:0.5pt solid #EFEAD8\">Long terme "
        "(1-3 ans)</th>"
        "</tr>\n"
        "<tr>"
        "<td style=\"vertical-align:top;padding:2mm;border:0.5pt solid "
        "#EFEAD8;background:#FBF8EF\"><ul><li>Action 1</li><li>Action 2</li>"
        "</ul></td>"
        "<td style=\"vertical-align:top;padding:2mm;border:0.5pt solid "
        "#EFEAD8;background:#FBF8EF\"><ul><li>Action 1</li><li>Action 2</li>"
        "</ul></td>"
        "<td style=\"vertical-align:top;padding:2mm;border:0.5pt solid "
        "#EFEAD8;background:#FBF8EF\"><ul><li>Action 1</li><li>Action 2</li>"
        "</ul></td>"
        "</tr>\n"
        "</table>"
    ),
    "str.18.annexe_brief": (
        "Annexe finale (format identique aux annexes EM) : pour chaque demande "
        "specifique du brief client, fournis une reponse synthetique de 1-2 "
        "paragraphes suivie d'un encadre intitule 'Strategie bonus' contenant "
        "2-3 pistes operationnelles concretes. Numerotation A.1, A.2, A.3... "
        "Ton plus direct que les chapitres : conversation finale avec le "
        "dirigeant."
    ),
    "str.19.sources": (
        "Liste les sources utilisees pour construire cette strategie, "
        "regroupees par thematique (Donnees marche, Benchmarks sectoriels, "
        "Reglementation, Documents client). Format simple :\n"
        "## Donnees marche\n- Nom - URL si disponible\n"
        "## Benchmarks sectoriels\n- ...\n"
        "Pas plus de 4-6 sources par thematique. Ajoute un court paragraphe "
        "'## Methodologie' (3-4 lignes) precisant la demarche (croisement "
        "diagnostic / arbitrages / feuille de route). Rester concis et structure."
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

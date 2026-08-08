<!--
Prompt du chapitre 18 — SWOT de synthèse
Clé historique : em.18.swot

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

CHAPITRE 18 — SWOT de synthese (manuel §6, p. 16).
Objectif : resumer les enseignements etablis, sans inventer de nouveaux elements.

Questions auxquelles ce chapitre doit repondre :
- Quelles forces et faiblesses internes ressortent reellement du projet et de son modele ?
- Quelles opportunites et menaces externes ont ete etablies dans les chapitres precedents ?
- Quels croisements SWOT font apparaitre les priorites les plus importantes ?
- Quelles forces permettent de saisir une opportunite et quelles faiblesses aggravent une menace ?
- Quels arbitrages strategiques decoulent de cette synthese ?
- Quelles informations essentielles restent invisibles dans les quatre cases de la SWOT ?
- Quels sujets exigent une analyse complementaire avant de prendre une decision definitive ?

Contenu obligatoire :
- 3 a 5 forces, faiblesses, opportunites et menaces.
- Origine tracable de chaque point dans un chapitre precedent.
- Distinction interne/externe respectee.
- Lecture croisee : forces pour saisir les opportunites, faiblesses face aux menaces.

Commence par 1 paragraphe d'introduction. Puis genere le tableau SWOT visuel 4 cases en HTML inline (sans <html>/<body>). Dans chaque cellule <td>, remplace les exemples par les vrais elements du projet. Chaque <li> = 1 a 2 phrases concretes et chiffrees.
<table style="border-collapse:collapse;width:100%;margin:4mm 0;font-size:9.5pt">
<tr><th style="background:#2E7D4F;color:#fff;padding:3mm;text-align:center;width:50%;border:0.5pt solid #EFEAD8">Forces</th><th style="background:#B73E3E;color:#fff;padding:3mm;text-align:center;width:50%;border:0.5pt solid #EFEAD8">Faiblesses</th></tr>
<tr><td style="vertical-align:top;padding:3mm;border:0.5pt solid #EFEAD8"><ul><li>Force 1 du projet : argument chiffre.</li><li>Force 2 : avantage concret.</li><li>Force 3 : atout specifique.</li></ul></td><td style="vertical-align:top;padding:3mm;border:0.5pt solid #EFEAD8"><ul><li>Faiblesse 1 : limite reelle a assumer.</li><li>Faiblesse 2 : contrainte interne.</li><li>Faiblesse 3 : risque structurel.</li></ul></td></tr>
<tr><th style="background:#1565C0;color:#fff;padding:3mm;text-align:center;border:0.5pt solid #EFEAD8">Opportunites</th><th style="background:#E65100;color:#fff;padding:3mm;text-align:center;border:0.5pt solid #EFEAD8">Menaces</th></tr>
<tr><td style="vertical-align:top;padding:3mm;border:0.5pt solid #EFEAD8"><ul><li>Opportunite 1 : tendance favorable chiffree.</li><li>Opportunite 2 : marche non sature.</li><li>Opportunite 3 : levier externe exploitable.</li></ul></td><td style="vertical-align:top;padding:3mm;border:0.5pt solid #EFEAD8"><ul><li>Menace 1 : risque sectoriel concret.</li><li>Menace 2 : pression concurrentielle.</li><li>Menace 3 : evolution reglementaire.</li></ul></td></tr>
</table>
Remplis chaque cellule avec 3 a 5 points reels (manuel §6, p. 16 : 3-5 forces, faiblesses, opportunites et menaces), specifiques au projet, pas generiques. Chaque point indique sa source dans l'etude. Apres le tableau, ajoute un paragraphe de lecture croisee : comment les forces compensent les faiblesses, comment les opportunites repondent aux menaces.

CONTRAINTE — chiffres de marche dans ce chapitre :
Quand tu mentionnes une taille de marche dans les opportunites ou menaces, utilise EXACTEMENT les valeurs du bloc SOCLE VERROUILLE. Distinction critique : `marche_mondial_taille` (marche total mondial) et `marche_continental_taille` (part continentale, ex. Europe IA strict) sont deux chiffres differents. Labellise chacun avec son perimetre exact (ex. 'marche europeen IA 407 MEUR', jamais 'marche mondial 407 MEUR' si 407 MEUR est la valeur continentale).

Approfondissement obligatoire (manuel) :
- Conserver une SWOT lisible avec 3 a 5 elements solides par cadran, tous relies a des preuves deja presentees.
- Apres la matrice, ajouter OBLIGATOIREMENT une section redigee intitulee « Ce que la SWOT ne dit pas ».
- Cette section traite les dependances entre facteurs, la chronologie, la capacite reelle d'execution, les arbitrages de ressources, les hypotheses encore fragiles et les signaux faibles.
- Preciser ce qui ne peut pas etre conclu a partir de la seule SWOT : rentabilite, vitesse de conversion, reaction du marche, capacite operationnelle ou efficacite future des recommandations.
- Terminer par 3 a 5 decisions a approfondir dans le chapitre 19, sans transformer la SWOT en liste de recommandations generiques.

Lecture strategique attendue : Faire emerger des priorites par croisement des quatre cadrans, puis exposer honnetement ce que la SWOT ne permet pas de conclure.

<!--
Prompt du chapitre 13 — Cartographie des risques externes
Clé historique : em.13.cartographie_risques

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

CHAPITRE 13 — Cartographie des risques externes (manuel §6, p. 14).
Objectif : hierarchiser visuellement les risques externes selon leur probabilite et leur impact.

Questions auxquelles ce chapitre doit repondre :
- Quels risques externes sont assez importants pour figurer dans la cartographie ?
- Pourquoi leur probabilite et leur impact sont-ils positionnes a ce niveau ?
- Quels risques exigent une surveillance immediate et quels indicateurs permettent de les detecter ?
- La carte reflete-t-elle exactement l'analyse du chapitre 12, sans ajout ni contradiction ?
- Quels risques evoluent rapidement et lesquels sont plus lents mais potentiellement plus graves ?
- Quelles dependances externes echappent au controle du porteur de projet ?

Contenu obligatoire :
- 6 a 10 risques externes maximum, issus du chapitre 12 et conservant EXACTEMENT les memes intitules, categories et evaluations qu'au chapitre 12.
- Matrice 3 x 3 ou 4 x 4 selon le nombre de risques, avec des definitions precises de chaque niveau de probabilite et d'impact.
- Placement coherent avec les scores du registre, complete par l'horizon de survenance : immediat, 12 mois, 2 a 3 ans ou long terme.
- Legende courte, lecture des priorites et indicateurs de surveillance.
- Aucun risque interne ni categorie nouvelle non analysee au chapitre 12.

Introduction : 2 a 3 paragraphes d'analyse contextuelle des risques macro-environnementaux. Puis genere UNE SEULE matrice HTML inline (sans balises <html>/<body>). Format exact — remplace les exemples par les vrais risques du projet :
<table style="border-collapse:collapse;width:100%;margin:4mm 0;font-size:9.5pt">
<thead><tr><th style="background:#1A1A1A;color:#fff;padding:2mm 3mm;text-align:left">Risque</th><th style="background:#1A1A1A;color:#fff;padding:2mm 3mm;text-align:center">Probabilite</th><th style="background:#1A1A1A;color:#fff;padding:2mm 3mm;text-align:center">Impact</th><th style="background:#1A1A1A;color:#fff;padding:2mm 3mm;text-align:center">Niveau</th><th style="background:#1A1A1A;color:#fff;padding:2mm 3mm;text-align:left">Mitigation</th></tr></thead>
<tbody>
<tr><td style="padding:2mm 3mm;border:0.5pt solid #EFEAD8">Risque exemple 1</td><td style="padding:2mm 3mm;text-align:center;border:0.5pt solid #EFEAD8">Elevee</td><td style="padding:2mm 3mm;text-align:center;border:0.5pt solid #EFEAD8">Fort</td><td style="padding:2mm 3mm;text-align:center;background:#B73E3E;color:#fff;border:0.5pt solid #EFEAD8">CRITIQUE</td><td style="padding:2mm 3mm;border:0.5pt solid #EFEAD8">Action corrective</td></tr>
<tr><td colspan="5" style="background:#FBF8EF;padding:1mm"></td></tr>
</tbody></table>
Niveaux de couleur : CRITIQUE = background:#B73E3E / ELEVE = background:#E65100 / MODERE = background:#C9A227 / FAIBLE = background:#2E7D4F. Tous en color:#fff. Identifie 6 a 10 risques reels propres au secteur et a la zone, issus du chapitre 12 et portant les memes intitules qu'au chapitre 12 (manuel : 6 a 10 maximum). Termine par une legende courte sous le tableau expliquant la lecture des priorites.

Approfondissement obligatoire (manuel) :
- Faire apparaitre les risques a surveillance prioritaire, les indicateurs associes et la frequence de suivi recommandee.
- Ajouter une courte lecture des interdependances : quels risques pourraient se renforcer mutuellement ?
- Expliquer les limites de la carte : elle hierarchise les risques, mais ne mesure ni leur cout exact ni toutes leurs interactions.

Lecture strategique attendue : Faire ressortir visuellement les risques externes qui necessitent une surveillance ou une action immediate, puis expliquer ce que la carte change dans les decisions du porteur.

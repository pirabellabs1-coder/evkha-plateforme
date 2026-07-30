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
Contenu obligatoire :
- 5 a 8 risques externes maximum, issus du chapitre 12.
- Matrice 3 x 3 avec definitions explicites des axes.
- Placement coherent avec les scores du registre.
- Legende courte et lecture des priorites.
Visuel utile : matrice probabilite/impact haute resolution.

Introduction : 2 a 3 paragraphes d'analyse contextuelle des risques macro-environnementaux. Puis genere UNE SEULE matrice HTML inline (sans balises <html>/<body>). Format exact — remplace les exemples par les vrais risques du projet :
<table style="border-collapse:collapse;width:100%;margin:4mm 0;font-size:9.5pt">
<thead><tr><th style="background:#1A1A1A;color:#fff;padding:2mm 3mm;text-align:left">Risque</th><th style="background:#1A1A1A;color:#fff;padding:2mm 3mm;text-align:center">Probabilite</th><th style="background:#1A1A1A;color:#fff;padding:2mm 3mm;text-align:center">Impact</th><th style="background:#1A1A1A;color:#fff;padding:2mm 3mm;text-align:center">Niveau</th><th style="background:#1A1A1A;color:#fff;padding:2mm 3mm;text-align:left">Mitigation</th></tr></thead>
<tbody>
<tr><td style="padding:2mm 3mm;border:0.5pt solid #EFEAD8">Risque exemple 1</td><td style="padding:2mm 3mm;text-align:center;border:0.5pt solid #EFEAD8">Elevee</td><td style="padding:2mm 3mm;text-align:center;border:0.5pt solid #EFEAD8">Fort</td><td style="padding:2mm 3mm;text-align:center;background:#B73E3E;color:#fff;border:0.5pt solid #EFEAD8">CRITIQUE</td><td style="padding:2mm 3mm;border:0.5pt solid #EFEAD8">Action corrective</td></tr>
<tr><td colspan="5" style="background:#FBF8EF;padding:1mm"></td></tr>
</tbody></table>
Niveaux de couleur : CRITIQUE = background:#B73E3E / ELEVE = background:#E65100 / MODERE = background:#C9A227 / FAIBLE = background:#2E7D4F. Tous en color:#fff. Identifie 5 a 8 risques reels propres au secteur et a la zone, issus du chapitre 12 (manuel §6, p. 14 : 5-8 maximum). Termine par une legende courte sous le tableau expliquant la lecture des priorites.

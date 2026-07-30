<!--
Prompt du chapitre 17 — Feuille de route stratégique et priorisation
Clé historique : str.17.feuille_route

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

Feuille de route strategique et priorisation : actions prioritaires a court terme (0-3 mois), orientations a moyen terme (3-12 mois), cap a long terme (1-3 ans). Pour chaque action : quoi faire, pourquoi, quel indicateur prouvera le succes. Avant le detail textuel, genere une frise chronologique visuelle en HTML inline (sans <html>/<body>) avec 3 blocs colores cote a cote, sur ce pattern (remplace les exemples par les actions reelles, 2 a 3 actions cle par bloc) :
<table style="border-collapse:collapse;width:100%;margin:4mm 0;font-size:9pt;table-layout:fixed">
<tr><th style="background:#C9A227;color:#1A1A1A;padding:2mm;text-align:center;border:0.5pt solid #EFEAD8">Court terme (0-3 mois)</th><th style="background:#1A1A1A;color:#fff;padding:2mm;text-align:center;border:0.5pt solid #EFEAD8">Moyen terme (3-12 mois)</th><th style="background:#2E7D4F;color:#fff;padding:2mm;text-align:center;border:0.5pt solid #EFEAD8">Long terme (1-3 ans)</th></tr>
<tr><td style="vertical-align:top;padding:2mm;border:0.5pt solid #EFEAD8;background:#FBF8EF"><ul><li>Action 1</li><li>Action 2</li></ul></td><td style="vertical-align:top;padding:2mm;border:0.5pt solid #EFEAD8;background:#FBF8EF"><ul><li>Action 1</li><li>Action 2</li></ul></td><td style="vertical-align:top;padding:2mm;border:0.5pt solid #EFEAD8;background:#FBF8EF"><ul><li>Action 1</li><li>Action 2</li></ul></td></tr>
</table>

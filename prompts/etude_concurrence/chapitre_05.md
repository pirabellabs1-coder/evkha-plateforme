<!--
Prompt du chapitre 5 — Matrice de positionnement concurrentiel et zones stratégiques
Clé historique : ec.05.matrice_positionnement

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

Matrice de positionnement concurrentiel : choisis 2 axes strategiques pertinents (ex. prix / qualite percue, ou positionnement premium / accessible). ETAPE OBLIGATOIRE : le tableau HTML ci-dessous DOIT apparaitre dans ta reponse, rempli avec les donnees reelles. Ce n'est pas une option ni un exemple a paraphraser : une reponse qui decrit la matrice uniquement en texte, sans le tableau HTML, est un echec. Le contenu de chaque cellule reste court (une ligne, style fiche : nom de l'acteur + 3-6 mots de qualification), jamais un paragraphe complet — les paragraphes d'interpretation viennent APRES le tableau, pas dedans. Genere d'abord la matrice en HTML inline (sans <html>/<body>) sous forme de grille 3x3 representant les 4 quadrants autour d'un centre, chaque concurrent et le projet places dans la cellule correspondant a sa position reelle. Voici le pattern a suivre (adapte les libelles d'axes et le contenu des cellules aux donnees reelles) :
<table style="border-collapse:collapse;width:100%;margin:4mm 0;font-size:9pt;table-layout:fixed">
<tr><td colspan="3" style="text-align:center;padding:1mm;font-weight:bold;color:#1A1A1A">Axe vertical (ex. Qualite percue +)</td></tr>
<tr><td style="height:28mm;vertical-align:top;padding:2mm;border:0.5pt solid #EFEAD8;background:#FBF8EF">Acteur A</td><td style="height:28mm;vertical-align:top;padding:2mm;border:0.5pt solid #EFEAD8;background:#FBF8EF">Acteur B</td><td style="height:28mm;vertical-align:top;padding:2mm;border:0.5pt solid #EFEAD8;background:#FBF8EF">Acteur C</td></tr>
<tr><td style="height:28mm;vertical-align:top;padding:2mm;border:0.5pt solid #EFEAD8">Acteur D</td><td style="height:28mm;vertical-align:top;padding:2mm;border:0.5pt solid #EFEAD8;background:#C9A22733;font-weight:bold;color:#1A1A1A">Projet (position visee)</td><td style="height:28mm;vertical-align:top;padding:2mm;border:0.5pt solid #EFEAD8">Acteur E</td></tr>
<tr><td style="height:28mm;vertical-align:top;padding:2mm;border:0.5pt solid #EFEAD8;background:#FBF8EF">Acteur F</td><td style="height:28mm;vertical-align:top;padding:2mm;border:0.5pt solid #EFEAD8;background:#FBF8EF">Acteur G</td><td style="height:28mm;vertical-align:top;padding:2mm;border:0.5pt solid #EFEAD8;background:#FBF8EF">Acteur H</td></tr>
<tr><td colspan="3" style="text-align:center;padding:1mm;font-weight:bold;color:#1A1A1A">Axe horizontal (ex. Prix bas -&gt; Prix eleve)</td></tr>
</table>
Place chaque concurrent identifie dans les chapitres precedents dans la cellule qui correspond a sa position reelle sur les 2 axes (n'utilise pas obligatoirement les 9 cellules, ne remplis que celles pertinentes, laisse une cellule vide plutot que d'inventer un acteur). Mets le projet en surbrillance (couleur #C9A22733) dans la cellule visee. Apres la matrice, interprete en 2 a 3 paragraphes : zones saturees, espaces libres, risques de cannibalisation.

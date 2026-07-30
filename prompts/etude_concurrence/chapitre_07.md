<!--
Prompt du chapitre 7 — Conclusion analytique et graphiques
Clé historique : ec.07.conclusion_graphiques

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

Conclusion analytique : forces/faiblesses majeures du marche concurrentiel, axe strategique prioritaire pour le projet, leviers differenciants des le lancement. Avant la conclusion textuelle, genere 4 graphiques en HTML inline (sans <html>/<body>) a l'aide de tableaux HTML avec barres CSS, sur le meme modele que les graphiques du chapitre marche : titre H3, tableau barres avec valeurs reelles, legende courte en italique sous chaque tableau. Pattern a suivre pour chaque graphique en barres (adapte les donnees reelles) :
<h3 style="font-size:14pt;margin:4mm 0 2mm">Graphique 1 — Titre</h3>
<table style="border-collapse:collapse;width:100%;margin:3mm 0;font-size:9.5pt">
<tr><td style="padding:1.5mm 3mm;border-bottom:0.5pt solid #EFEAD8;width:35%">Label A</td><td style="padding:1.5mm 2mm;width:55%"><div style="background:#C9A227;height:5mm;width:75%;display:inline-block"></div></td><td style="padding:1.5mm 2mm;font-weight:bold;color:#1A1A1A;width:10%">75 %</td></tr>
</table>
Les 4 graphiques a produire : (1) parts de marche des principaux concurrents identifies (barres, %), (2) repartition des canaux de distribution/acquisition du marche (barres, %), (3) comparatif forces/faiblesses des 2-3 concurrents principaux face au projet : une ligne par critere (prix, qualite, notoriete, digital...), une barre par acteur avec sa couleur propre (#C9A227 pour le projet, #1A1A1A pour les concurrents), (4) carte synthetique des concurrents par categorie (directs, indirects, emergents) sous forme de tableau a 3 colonnes listant les acteurs de chaque categorie. Utilise les donnees chiffrees reelles etablies dans les chapitres precedents, jamais de valeurs inventees sans base. Termine par la conclusion analytique textuelle demandee ci-dessus.

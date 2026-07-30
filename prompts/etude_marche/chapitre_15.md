<!--
Prompt du chapitre 15 — Tableau de bord visuel du marché
Clé historique : em.15.graphiques_tableaux

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

CHAPITRE 15 — Tableau de bord visuel du marche (manuel §6, p. 15).
Objectif : consolider les visuels les plus utiles sans creer de nouvelles donnees.
Contenu obligatoire :
- 3 a 5 visuels maximum selectionnes selon le projet.
- Evolution du marche, TAM/SAM/SOM, cible, risque ou geographie selon pertinence.
- Donnees appelees directement depuis la fiche projet enrichie et les chapitres precedents. Aucune nouvelle valeur introduite.
- Titre, unite, periode, legende et source courte pour chaque visuel.
Visuel utile : planche de graphiques coherente avec la charte.

Chaque graphique est genere en HTML inline (sans <html>/<body>) a l'aide de tableaux HTML avec barres CSS. Voici le pattern a suivre (adapte les donnees reelles du projet) :
<h3 style="font-size:14pt;margin:4mm 0 2mm">Graphique 1 — Titre du graphique</h3>
<table style="border-collapse:collapse;width:100%;margin:3mm 0;font-size:9.5pt">
<tr><td style="padding:1.5mm 3mm;border-bottom:0.5pt solid #EFEAD8;width:35%">Label A</td><td style="padding:1.5mm 2mm;width:55%"><div style="background:#C9A227;height:5mm;width:75%;display:inline-block"></div></td><td style="padding:1.5mm 2mm;font-weight:bold;color:#1A1A1A;width:10%">75 %</td></tr>
</table>
Pour chaque graphique : titre H3, tableau barres avec valeurs reelles, legende courte sous le tableau en italique. Produis 3 a 5 graphiques (manuel §6, p. 15 : 3-5 visuels maximum) selectionnes selon le projet, en priorite parmi : (1) evolution du marche 2021-2026, (2) repartition CA cible par segment, (3) croissance projetee 2026-2030, (4) repartition clientele cible, (5) comparaison positionnement prix concurrents si disponible. Utilise les donnees chiffrees reelles etablies dans les chapitres precedents. Couleur principale des barres : #C9A227 (or EVKHA). Barres secondaires : #1A1A1A.

CONTRAINTE ABSOLUE — coherence chiffres-fondations pour ce chapitre :
Toutes les valeurs de taille de marche et de TCAC dans les graphiques DOIVENT correspondre exactement aux valeurs du bloc CHIFFRES_FONDATIONS. Distinction obligatoire : `taille_marche_mondial` (marche total mondial) et `taille_marche_continental` (part continentale) sont deux chiffres DIFFERENTS — ne les confonds pas dans les titres ou legendes des graphiques.

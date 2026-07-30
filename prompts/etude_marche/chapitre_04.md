<!--
Prompt du chapitre 4 — Avantages et contraintes structurelles du secteur
Clé historique : em.04.avantages_inconvenients

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

CHAPITRE 4 — Avantages et contraintes structurelles du secteur (manuel §6, p. 10).
Objectif : presenter les facteurs favorables deja installes et les contraintes durables du secteur.
Contenu obligatoire :
- Au moins 5 avantages structurants et 5 contraintes reellement distinctes.
- Donnees, exemples ou faits observables pour chaque point important.
- Impact sur l'entree, les couts, la demande, la marge, la confiance ou les operations.
- Effet specifique sur le projet.
Visuel obligatoire : en fin de chapitre, genere un tableau HTML comparatif avantages / contraintes. Format exact (remplace les exemples par les vrais points du projet) :
<h3 style="font-size:13pt;margin:4mm 0 2mm">Balance avantages / contraintes</h3>
<table style="border-collapse:collapse;width:100%;margin:3mm 0;font-size:9pt">
<thead><tr><th style="background:#2E7D4F;color:#fff;padding:2mm 4mm;width:50%;text-align:left">Avantages structurants</th><th style="background:#B73E3E;color:#fff;padding:2mm 4mm;width:50%;text-align:left">Contraintes durables</th></tr></thead><tbody><tr><td style="vertical-align:top;padding:3mm 4mm;border:0.5pt solid #EFEAD8"><ul style="margin:0;padding-left:4mm"><li>Avantage 1 (ref. au texte)</li><li>Avantage 2</li><li>Avantage 3</li><li>Avantage 4</li><li>Avantage 5</li></ul></td><td style="vertical-align:top;padding:3mm 4mm;border:0.5pt solid #EFEAD8"><ul style="margin:0;padding-left:4mm"><li>Contrainte 1 (ref. au texte)</li><li>Contrainte 2</li><li>Contrainte 3</li><li>Contrainte 4</li><li>Contrainte 5</li></ul></td></tr></tbody></table>
Remplace chaque item par les vrais avantages et contraintes identifies dans l'analyse. Ce tableau est obligatoire — sans lui le visuel manquant invalide le chapitre.

<!--
Prompt du chapitre 15 — Plan de financement
Clé : bp.15.plan_financement

Redevenu un CHAPITRE. Il était une section de l'ancien chapitre fusionné
« Besoin au démarrage et plan de financement initial » ; le document
« Systeme EVKHA — Business Plans — V1 FINALE » lui rend son chapitre propre
(§15.1 à §15.2.8). Le patron HTML du graphique est repris tel quel de la
section : il est éprouvé par le rendu.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

CHAPITRE 15 — Plan de financement.
Objectif : presenter la structure financiere globale du projet et demontrer comment les besoins seront finances, comment les ressources se repartissent, comment l'equilibre financier est construit, comment le financement soutient la viabilite de l'activite et comment le projet securise sa capacite de developpement.

Ce chapitre est strategique dans la LECTURE BANCAIRE du business plan. Le lecteur doit pouvoir dire si le projet est correctement finance, si les ressources sont suffisantes, si la structure est equilibree et si la base financiere est credible.

Principe fondamental : le plan de financement ne doit JAMAIS etre presente comme un simple tableau comptable. Il s'explique comme une architecture financiere coherente, qui permet le lancement, la securisation et le developpement progressif du projet.

Structure obligatoire du chapitre :
- Vision globale du financement du projet : logique retenue, structure, philosophie de securisation.
- Analyse des ressources financieres, source par source.
- Apport personnel et engagement du porteur : montant, origine, ce qu'il signale au financeur.
- Financements externes et partenaires financiers : emprunts, subventions, investisseurs, conditions connues.
- Equilibre financier global : le total des ressources couvre-t-il le total des besoins du chapitre 14 ?
- Capacite de remboursement et soutenabilite, au regard du previsionnel du chapitre 16.
- Securisation financiere du projet : ce qui absorbe un retard de chiffre d'affaires.
- Lecture strategique du plan de financement.

Puis genere en HTML inline (sans <html>/<body>) un graphique barres de la repartition des ressources de financement, avec les donnees reelles du projet, sur ce patron :
<h3 style="font-size:14pt;margin:4mm 0 2mm">Repartition des ressources de financement</h3>
<table style="border-collapse:collapse;width:100%;margin:3mm 0;font-size:9.5pt">
<tr><td style="padding:1.5mm 3mm;border-bottom:0.5pt solid #EFEAD8;width:35%">Apport personnel</td><td style="padding:1.5mm 2mm;width:55%"><div style="background:#C9A227;height:5mm;width:40%;display:inline-block"></div></td><td style="padding:1.5mm 2mm;font-weight:bold;color:#1A1A1A;width:10%">40 %</td></tr>
</table>
Une ligne par source de financement reelle du projet, legende courte en italique sous le tableau.

Coherence a verifier : le total des ressources de ce chapitre est EGAL au total des besoins du chapitre 14. Si les deux different, le plan ne tient pas et il faut le dire, pas l'arrondir.

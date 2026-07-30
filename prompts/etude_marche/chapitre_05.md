<!--
Prompt du chapitre 5 — Défis et opportunités 2026-2030
Clé historique : em.05.defis_opportunites

Exporté depuis generation/prompt_library.py. Ce fichier est désormais la
source de vérité : modifier le prompt ici, plus dans le code Python.

Variables interpolées disponibles ({{ nom }}) :
  {{ secteur }}   {{ pays }}   {{ zone }}   {{ projet }}
  {{ titre_chapitre }}   {{ numero_chapitre }}   {{ cible_mots }}
Une variable inconnue est laissée telle quelle et signalée à la génération.
-->

CHAPITRE 5 — Defis et opportunites 2026-2030 (manuel §6, p. 10).
Objectif : identifier les transformations a venir qui peuvent creer de la valeur ou fragiliser le projet.
Contenu obligatoire :
- Au moins 5 defis et 5 opportunites distincts.
- Horizon, probabilite, intensite et mecanisme d'impact.
- Signaux faibles ou changements emergents etayes.
- Leviers activables par le projet et points de vigilance.
Visuel obligatoire : en fin d'analyse (apres les 5 defis et 5 opportunites), genere UNE matrice HTML impact/horizon. Format exact :
<h3 style="font-size:13pt;margin:4mm 0 2mm">Matrice impact / horizon — defis et opportunites</h3>
<table style="border-collapse:collapse;width:100%;margin:3mm 0;font-size:9pt">
<thead><tr><th style="background:#1A1A1A;color:#fff;padding:2mm 3mm;width:40%">Item</th><th style="background:#1A1A1A;color:#fff;padding:2mm 3mm;text-align:center;width:15%">Type</th><th style="background:#1A1A1A;color:#fff;padding:2mm 3mm;text-align:center;width:20%">Horizon</th><th style="background:#1A1A1A;color:#fff;padding:2mm 3mm;text-align:center;width:25%">Intensite d'impact</th></tr></thead><tbody>
<tr><td style="padding:2mm 3mm;border:0.5pt solid #EFEAD8">Defi 1 — [libelle court]</td><td style="padding:2mm 3mm;text-align:center;border:0.5pt solid #EFEAD8;color:#B73E3E;font-weight:bold">DEFI</td><td style="padding:2mm 3mm;text-align:center;border:0.5pt solid #EFEAD8">2026-2027</td><td style="padding:2mm 3mm;text-align:center;border:0.5pt solid #EFEAD8;background:#B73E3E;color:#fff">Fort</td></tr>
</tbody></table>
<p style="font-style:italic;font-size:8.5pt;color:#5A5A5A">DEFI = contrainte externe ; OPPORT. = levier d'action. Intensite : Fort / Modere / Faible.</p>
Inclus les 10 items (5 defis + 5 opportunites) dans ce tableau, dans l'ordre decroissant d'intensite. Ce tableau est obligatoire — NE PAS ecrire 'le tableau ci-dessous' sans le generer immediatement apres.

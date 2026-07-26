"""Etude de reference EM injectee en few-shot (tache #13).

PROVENANCE. Les extraits sont VERBATIM de « Findrax_Etude_de_marche-2.docx »,
une etude de marche EVKHA reelle (plateforme de mise en relation juridique,
France). Evangeline a situe cette etude « autour de 8/10 » contre « environ
5/10 » pour notre WAOME v4 du 24/07/2026 : c'est le seul point de comparaison
note dont nous disposons, donc le seul etalon defendable.

POURQUOI DES EXTRAITS ET PAS DES REGLES. Nous avons deja essaye les regles.
`_RAPPEL_ANTI_RECHUTE_PIED` (supprime le 24/07, cf. prompts.py) enumerait les
memes exigences en imperatif ; le modele les recopiait mot pour mot dans le
texte livre (« fourchette de 100 a 120 kEUR, mediane retenue 110 kEUR »), et
Evangeline a rejete WAOME v4 pour ce motif precis. Une regle enonce un
resultat ; un extrait montre une mecanique. Le modele ne peut pas regurgiter
« montre ta methode » s'il n'a jamais lu la phrase, seulement le geste.

CE QUE LES EXTRAITS APPORTENT, ET QUE LE MANUEL NE PEUT PAS DONNER. Le manuel
d'Evangeline dit QUOI traiter (21 chapitres, §3 la voix, §4 la coherence). Il
ne montre pas a quoi ressemble un sous-titre qui annonce un constat, ni un SOM
pose variable par variable. Les quatre extraits ci-dessous isolent quatre
gestes que WAOME v4 ne faisait pas et que Findrax fait systematiquement.

RISQUE ASSUME, ET SA PARADE. Un few-shot chiffre dans un secteur etranger
invite a la contamination : le modele peut reprendre 79 141 avocats ou
49,95 EUR/mois dans une etude de beaute au Benin. Trois parades cumulees :
  1. le secteur d'origine est nomme des la premiere ligne, pas cache ;
  2. l'interdiction de reprise precede les extraits (elle est lue avant les
     chiffres, pas apres) et est rappelee a la fermeture du bloc ;
  3. `checks_blocs.py` verifie deja la coherence des chiffres inter-blocs, et
     le CHECK du bloc A porte precisement sur TAM/SAM/SOM.
Un test dedie (`tests/test_reference_em_fewshot.py`) verrouille la presence de
l'interdiction et l'absence du bloc pour BP/EC/STR.

COUT MESURE. `REFERENCE_EM` = ~950 tokens, place dans le SEGMENT STABLE du
system prompt (avant SYSTEM_CACHE_BREAK) : mutualise entre tous les jobs EM de
la fenetre d'1 h et relu a 10 % du tarif.
  - ecriture de cache 1 h (200 %)   : 0,0051 EUR / fenetre
  - 30 lectures a 10 %              : 0,0077 EUR / job
  - `REFERENCE_SOM`, non cache, x1  : 0,0015 EUR / job
  => ~0,014 EUR / job, contre 0,077 EUR pour le seul bloc EM s'il etait
     injecte non cache dans les 30 appels. Aucun relevement de budget
     necessaire : la marge de retry de l'EM est de ~0,46 EUR.

PORTEE. EM UNIQUEMENT. Le manuel d'Evangeline ne couvre que l'EM et BP/EC/STR
attendent sa validation (cf. memoire projet). Findrax est une EM : ses gestes
ne se transposent pas tels quels a un dossier bancaire.
"""

from __future__ import annotations

# Interdiction placee AVANT les extraits : le modele la lit avant les chiffres.
_GARDE_FOU = (
    "[ETUDE DE REFERENCE — NIVEAU ATTENDU]\n"
    "Les quatre extraits ci-dessous sont tires d'une etude de marche EVKHA "
    "reelle portant sur une PLATEFORME JURIDIQUE EN FRANCE — un secteur et un "
    "pays ETRANGERS a ceux que tu traites. Ils fixent le NIVEAU de redaction "
    "attendu, jamais le contenu.\n"
    "INTERDICTION ABSOLUE : ne reprends AUCUN chiffre, AUCUN nom propre, "
    "AUCUNE source, AUCUN taux, AUCUN prix et AUCUN element sectoriel de ces "
    "extraits. Ils ne concernent pas le projet de ton client. Tu imites "
    "uniquement la MECANIQUE de redaction decrite sous chaque extrait, "
    "appliquee aux donnees reelles du dossier que tu traites.\n"
)

_EXTRAITS = (
    "\n--- EXTRAIT 1 ---\n"
    "Titre de section : « Une profession encore peu specialisee, a "
    "concentration geographique marquee »\n"
    "MECANIQUE A IMITER : le sous-titre annonce le CONSTAT, pas le theme. "
    "« Le marche national », « Analyse de la demande », « Les tendances » sont "
    "des etiquettes : le lecteur ne sait pas encore ce qu'il va apprendre. "
    "Chacun de tes sous-titres doit pouvoir se lire seul et livrer une "
    "information. Un lecteur qui parcourt uniquement tes sous-titres doit "
    "deja connaitre tes conclusions.\n"
    "\n--- EXTRAIT 2 ---\n"
    "« seuls 11,4 % des avocats sont titulaires d'une mention de "
    "specialisation officielle [...] — un chiffre a retenir, car il borne "
    "directement le vivier de recrutement prioritaire de Findrax, meme si de "
    "nombreux avocats pratiquent ces matieres sans detenir la mention "
    "correspondante. »\n"
    "MECANIQUE A IMITER : le chiffre n'est jamais laisse seul. Dans la MEME "
    "phrase, il est rattache a une consequence nommee pour le projet du "
    "client, et la limite de l'interpretation est posee honnetement. Un "
    "chiffre sans consequence est un chiffre que le porteur de projet ne "
    "saura pas utiliser.\n"
    "\n--- EXTRAIT 3 ---\n"
    "« Ce marche accessible de 3,5 a 11,8 millions d'euros par an represente "
    "une fraction tres etroite du marche total de 1,5 a 1,8 milliard d'euros, "
    "de l'ordre de deux a huit dixiemes de pourcent selon les hypotheses "
    "retenues. Ce ratio [...] reflete fidelement le degre de specialisation du "
    "positionnement de Findrax : la plateforme ne vise ni l'ensemble du "
    "marche [...], mais un segment precis. »\n"
    "MECANIQUE A IMITER : un ratio inconfortable est ASSUME et explique, "
    "jamais maquille. Quand le marche accessible ne represente qu'une "
    "fraction infime du marche total, on l'ecrit et on dit pourquoi c'est "
    "coherent avec le positionnement. Gonfler le chiffre pour qu'il « fasse "
    "mieux » detruit la credibilite de tout le document.\n"
    "\n--- EXTRAIT 4 ---\n"
    "« Ce vivier, rappelons-le, compte entre 5 000 et 8 000 avocats [...] "
    "etabli au chapitre 3 » / « coherentes avec le modele de revenus "
    "recommande au chapitre 6 » / « developpee plus en detail au chapitre 17, "
    "mais elle doit deja etre integree a ce stade ».\n"
    "MECANIQUE A IMITER : les chapitres se citent explicitement, par leur "
    "numero, dans les deux sens — ce qui a ete etabli avant, ce qui sera "
    "developpe apres. C'est ce qui transforme 21 chapitres en un seul "
    "raisonnement au lieu de 21 fiches juxtaposees. Reprends une valeur deja "
    "etablie en nommant le chapitre qui l'a etablie, et ne la recalcule pas.\n"
    "\nRAPPEL : les chiffres, noms et sources de ces quatre extraits "
    "n'appartiennent pas au dossier de ton client. Seuls les quatre gestes de "
    "redaction sont a reproduire."
)

REFERENCE_EM = _GARDE_FOU + _EXTRAITS


# Exemplaire du SOM pose variable par variable. Injecte dans la CONSIGNE du
# chapitre 2 (prompt_library) et non dans le system prompt : il ne sert qu'a
# ce chapitre, et l'y placer eviterait de le faire lire aux 20 autres. Le
# chapitre 2 etant genere en un seul appel depuis la tache #9, le cout est
# paye une fois (~450 tokens non caches, ~0,001 EUR).
#
# C'est LE defaut central du run 010e3bf2 et le premier reproche d'Evangeline
# (« TAM, SAM et SOM incoherents ») : notre chapitre 2 livrait le resultat du
# SOM sans ses variables, donc invérifiable et impossible a discuter. Findrax
# nomme sept variables, definit chacune, puis POSE la formule.
REFERENCE_SOM = (
    "\n[EXEMPLE DE NIVEAU — SOM pose variable par variable]\n"
    "Extrait d'une etude EVKHA notee 8/10, secteur ETRANGER au tien "
    "(plateforme juridique, France) : ne reprends ni ses chiffres, ni son "
    "secteur, ni ses variables. Reprends sa MECANIQUE.\n"
    "« Le modele distingue sept variables. Le nombre d'avocats actifs "
    "correspond a la part des avocats inscrits qui utilisent effectivement la "
    "plateforme, et non au nombre brut d'inscriptions mis en avant dans les "
    "objectifs du porteur de projet. Le nombre de consultations reservees par "
    "mois et par avocat actif mesure l'intensite d'usage une fois l'avocat "
    "engage. [...] Le taux d'annulation ou de report retire du calcul les "
    "rendez-vous reserves mais non honores. [...] Le revenu mensuel moyen par "
    "avocat actif resulte du calcul : (consultations x (1 - taux "
    "d'annulation) x frais de service net) + (part abonnee x abonnement). »\n"
    "MECANIQUE A IMITER, point par point :\n"
    "1. ANNONCE le nombre de variables de ton modele avant de les derouler.\n"
    "2. DEFINIS chaque variable en une phrase, en la distinguant de la donnee "
    "voisine avec laquelle on la confondrait (ici : avocats ACTIFS et non "
    "avocats INSCRITS — l'ecart entre les deux est la variable la plus "
    "determinante du modele).\n"
    "3. POSE la formule en clair, avec le signe des operations, pour que le "
    "porteur de projet puisse la refaire avec ses propres hypotheses.\n"
    "4. DEDUIS les pertes reelles (annulations, defauts de paiement, "
    "commissions du prestataire) au lieu de raisonner sur un brut theorique.\n"
    "5. APPLIQUE une montee en charge progressive, pas un effectif constant "
    "sur l'annee : les clients arrivent au fil des mois.\n"
    "6. DESIGNE la variable la plus sensible du modele et dis en une phrase "
    "ce qui change si elle bouge.\n"
    "Un SOM qui ne montre pas ses variables est un chiffre que personne ne "
    "peut discuter, donc un chiffre que le porteur de projet ne defendra pas "
    "devant son banquier.\n"
)

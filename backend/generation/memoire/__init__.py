"""Mémoire de l'étude : ce que chaque chapitre sait, et d'où il le sait.

## Pourquoi ce paquet existe

29/09/2026, business plan ÉCLORE (`cb59cede`) : sur 1 055 nombres du document,
653 ne venaient pas des 37 données de référence — des écarts, des parts, des
mensualisations, des lignes entières de compte de résultat, recalculés par le
modèle chapitre après chapitre. Le résultat net 2029 y valait 23 223,86 € ou
23 835,86 € selon la page ; le « revenu mensuel » était la CAF divisée par
douze. Aucun contrôle ne pouvait trancher : il n'existait aucune référence
pour les chiffres dérivés (voir `docs/diagnostic.md`).

Ce paquet la construit, sur la structure existante :

- `faits` : les données du socle **et** leurs dérivés, calculés par le code,
  chacun avec sa formule et sa définition ;
- `reperes` : le rédacteur cite un fait par `{{identifiant}}`, le rendu écrit la
  valeur au format français unique — le mécanisme des figures (le modèle cite
  des identifiants, le code pose les valeurs), étendu à la prose ;
- `regles` : les règles métier datées (seuils de TVA, plafonds de la
  micro-entreprise) qui décident au lieu de laisser le modèle choisir.

Le socle reste le noyau : ce paquet n'invente aucune donnée, il ne dérive que
des identités (règle 2 du dépôt, `socle/calculs.py`).
"""

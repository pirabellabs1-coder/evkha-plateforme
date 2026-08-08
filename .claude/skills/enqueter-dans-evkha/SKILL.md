---
name: enqueter-dans-evkha
description: À lire avant de répondre à toute question de la forme « est-ce que X est implémenté / manquant / cassé ? » dans ce dépôt — audit, inventaire, revue de sécurité, cartographie, état d'un lot. Ce dépôt documente abondamment ses défauts PASSÉS au présent, et trois relectures s'y sont trompées le même jour. Donne les pièges nommés et la façon de vérifier chacun.
---

# Enquêter dans EVKHA sans se tromper d'artefact

Ce dépôt a une particularité qui piège tous les agents : **il raconte ses
défauts.** Commentaires, docstrings et messages de commit décrivent longuement
ce qui n'allait pas — souvent au présent, souvent sans dire que c'est réparé.
C'est délibéré et c'est précieux : ces textes expliquent *pourquoi* le code a
sa forme. Mais lus vite, ils se prennent pour un état actuel.

Le 8 août 2026, trois relectures successives ont conclu faux pour cette seule
raison :

| Conclusion rendue | Source lue | Réalité |
|---|---|---|
| « Les livrables sont téléchargeables sans contrôle d'accès » | commentaire de `evkha/urls.py` | Signature horodatée en place et testée depuis longtemps (`evkha/signatures.py`, 9 tests) |
| « Le déploiement ne peut pas démarrer » | `env-coolify.txt` | Le serveur porte d'autres valeurs ; la pile tourne |
| « Le cache ne s'active jamais, −40 % à récupérer » | `journal_generations.md` | Mesuré : 2 692 à 3 898 jetons contre un minimum de 1 024 |

Les trois auraient envoyé travailler sur un défaut inexistant. C'est la
règle 8 du `CLAUDE.md` : *une conclusion tirée du mauvais artefact est pire
qu'un silence.*

## La règle

**Aucune affirmation sur l'état du système ne se fonde sur de la prose.**
Un commentaire, une docstring, un tableau de documentation, une entrée de
journal : ce sont des indices sur *où regarder*, jamais des preuves. La preuve
est le code qui tourne, un test qui passe, une requête qui répond, une mesure.

Quand la prose et le code se contredisent, **le code gagne, et la prose est un
défaut à signaler** — un fichier qui se contredit lui-même est pire qu'un
fichier sans commentaire.

## Les quatre artefacts qui mentent le plus

**`env-coolify.txt`** — n'est pas suivi par git, a divergé du serveur en
27 points, et contient six secrets en clair identiques à ceux en production.
Il ne décrit **pas** la configuration en service. Pour celle-ci, lire l'API
Coolify (`/api/v1/applications/{uuid}/envs`). Voir aussi le point « secrets »
plus bas avant de l'ouvrir.

**`docs/00-cartographie.md`** — plusieurs entrées décrivent un état corrigé
depuis. Sa section 6.3 annonçait « Word depuis gabarit : inexistant » alors que
`documents/livrable_word.py` existe et tourne en production. Les entrées
corrigées portent une date ; les autres restent à vérifier.

**`journal_generations.md`** — les chiffres de coût y sont datés de leur
mesure et **ne sont pas re-mesurés**. Un « gain à récupérer » vieux de trois
jours peut être déjà acquis. Re-mesurer avant de s'en servir.

**Les commentaires de tête de module et de route.** Le style du dépôt est de
raconter l'incident qui a motivé le code. `evkha/urls.py`, `evkha/media.py`,
`organisations/checks.py` en sont pleins. Chercher le verbe : « n'existait
pas », « ne supprimait rien » décrivent le passé ; le présent qui suit dit ce
qui a été fait.

## Vérifier coûte moins cher qu'on croit

| Question | Vérification |
|---|---|
| « Cette protection existe-t-elle ? » | Chercher le module, puis **lancer ses tests** — `ls backend/tests/ \| grep <sujet>` |
| « Cette route est-elle protégée ? » | Écrire le fichier sur le disque, appeler l'URL, lire le code HTTP |
| « Ce réglage est-il posé en production ? » | API Coolify, jamais un fichier du dépôt |
| « Ce prompt tient en combien de jetons ? » | `client.messages.count_tokens(...)` — gratuit, ne génère rien. **Jamais `tiktoken`**, qui est le tokeniseur d'OpenAI |
| « Cette commande casse-t-elle le démarrage ? » | `DATABASE_URL="sqlite:///…" manage.py migrate` sur une base **vide** |
| « Ce test verrouille-t-il quelque chose ? » | Le rejouer sur le code d'avant. S'il passe, il ne verrouille rien |

## Ce que l'environnement local ne montre pas

La suite tourne sur **SQLite** avec **`DJANGO_DEBUG=true`**. Trois familles de
code ne sont donc jamais atteintes en local, et un agent qui conclut « ça
marche » depuis sa machine se trompe sur la production :

- tout ce qui suit `if connection.vendor != "postgresql"` ;
- les contrôles `evkha.C004` / `C005`, qui ne lèvent que hors `DEBUG` ;
- les drapeaux `EVKHA_USE_STUB_*`, qui valent `true` en local et `false` en
  production — un bouchon actif observe **un autre logiciel** que celui qui
  tourne chez la cliente.

## Les secrets : masquer par liste blanche

Ce dépôt et son serveur portent de vrais secrets de production, et deux ont
déjà fuité dans une conversation. En lisant des variables d'environnement, un
`.env`, ou la réponse de l'API Coolify : **n'afficher une valeur que si sa clé
figure dans une liste de variables explicitement anodines.** Pour toutes les
autres, n'imprimer que `<n signes>` ou un booléen de comparaison.

Énumérer les clés sensibles à masquer ne marche pas — c'est ainsi qu'un mot de
passe est passé. La liste des choses anodines, elle, est fermée.

## Avant de conclure quoi que ce soit

Les quatre contrôles, tous les quatre :

```bash
ruff check . && mypy backend && pytest && python manage.py makemigrations --check --dry-run
```

Deux repères pour les lire :

- **`mypy` rend ~156 erreurs préexistantes**, concentrées dans des fichiers de
  test anciens. Ce n'est pas une régression. Comparer le nombre, et surtout
  vérifier qu'aucune ne porte sur un fichier qu'on vient de toucher.
- **Pour le front, `tsc -b` — jamais `tsc --noEmit`**, qui ne vérifie aucun
  fichier et rend 0 quoi qu'il arrive :

```bash
cd frontend && npx tsc -b --force && npx eslint src --quiet
```

## Rendre compte

Dire d'où vient chaque affirmation. « `signature_valable` dans
`evkha/signatures.py`, plus les 9 tests de `test_media_signe.py` » se vérifie ;
« le contrôle d'accès est en place » ne se vérifie pas.

**Citer un symbole, pas un numéro de ligne.** Un `fichier.py:81` est faux à la
première insertion au-dessus — ce paragraphe en portait un, périmé de 46 lignes
avant même d'être commité. Un nom de fonction reste trouvable.

Quand une vérification n'a pas pu être faite, le dire. Un inventaire qui
présente une lecture de commentaire comme un constat de code fait perdre plus
de temps qu'un inventaire plus court.

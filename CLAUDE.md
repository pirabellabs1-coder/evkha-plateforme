# Règles de travail sur le dépôt EVKHA

Ce fichier gouverne tout agent (ou humain) qui modifie ce dépôt. Il est court
volontairement : chaque règle vient d'un défaut réel, daté, mesuré sur ce
projet. Aucune n'est théorique.

Il s'inspire des principes de `multica-ai/andrej-karpathy-skills`, en
particulier **Goal-Driven Execution** : transformer une tâche en critères de
succès *vérifiables*, et vérifier — plutôt qu'annoncer.

---

## 1. Un contrôle qui n'a rien à comparer est un ÉCHEC, jamais un succès

Le gate de livraison rendait `passed: True` sur des documents truffés
d'incohérences, parce que ses checks faisaient `continue` quand la donnée de
référence manquait. Il promettait une garantie qu'il n'assurait pas.

**Si vous ne pouvez pas juger, échouez bruyamment. Ne vous taisez pas.**

## 2. Un contrôle qui compare à une donnée MAL EXTRAITE est PIRE qu'absent

Il produit un motif faux et envoie corriger un chiffre qui n'était pas faux.
Constaté : le gate a bloqué un document en affirmant « document dit 1 250 000,
brief client dit 1 250 000 € » — deux chaînes identiques.

**Un motif d'échec doit être trouvable dans le document par le lecteur.**

## 3. Ce qui refait le document APRÈS le contrôle doit être contrôlé à son tour

Le gate valide le markdown. Puis quelque chose refait le document :

- **Gamma** en effaçait 74 % et cinq verticales sur dix — après validation ;
- **`chunk_long_tables`** détruisait les lignes des tableaux de plus de 12
  lignes (`tbody.decompose()` détruit l'élément ET ses enfants). Le client
  recevait `<tbody><></><></></tbody>` à la place du compte de résultat.

Dans les deux cas le markdown était propre, le gate passait, le document
partait amputé. **Vérifiez ce que le lecteur va lire, pas ce qu'on lui a
envoyé.**

## 4. Viser la CLASSE du défaut, pas l'exemple

Trois relectures successives ont trouvé le même défaut sous des formes
différentes, parce que je corrigeais l'instance :

- l'espace insécable, puis la fine insécable, puis l'espace fine des
  typographes → la **liste fermée** était le problème, pas sa composition ;
- le qualificatif avant le montant, puis après ;
- `LABEL:` mais pas `LABEL (…) :`.

**Si votre correctif énumère des cas, il est incomplet.**

## 5. Une seule source par vérité

Chaque défaut majeur de ce projet vient de deux modules qui ne sont pas
d'accord : trois listes de labels internes, trois listes de devises, deux
lectures des nombres, deux avis sur `[[UNDERSTAND]]` (le prompt l'exigeait, la
validation le punissait — chaque chapitre était payé deux fois).

**Voir `core/numbers.py` et `generation/internal_labels.py` : ne dupliquez pas
ces listes, importez-les.**

## 6. Un test doit échouer sur le code d'AVANT

Sinon il ne verrouille rien. Vécus sur ce dépôt :

- un test « structurel » censé rendre un oubli impossible ne détectait pas le
  label pour lequel il avait été écrit ;
- un test exigeait que `[[UNDERSTAND]]` soit signalé comme fuite : il
  verrouillait le bug qui doublait le coût ;
- la suite entière appelait la vraie API Anthropic dès qu'on passait
  `EVKHA_USE_STUB_AI=false` — lente et facturée.

**Rejouez le nouveau test contre le code d'avant. Et écrivez la
contre-épreuve : le correctif ne doit pas bloquer ce qui est correct.**

## 7. Le vert des tests ne prouve rien sur le document livré

Les tests tournent sur des doublures. Trois relectures de code n'ont trouvé ni
le double paiement, ni les tableaux détruits. **Le premier vrai dossier les a
trouvés en une fois.**

Ne dites jamais « c'est propre » sur la foi d'un test unitaire. La preuve, c'est
un dossier réel.

## 8. Chercher dans le dépôt avant de conclure

> **Avant tout audit, inventaire ou relecture : lire
> `.claude/skills/enqueter-dans-evkha/SKILL.md`.** Ce dépôt raconte ses défauts
> passés au présent, et le 08/08/2026 trois relectures s'y sont trompées le même
> jour — dont une qui a conclu que les livrables étaient accessibles sans
> contrôle alors que la signature horodatée était en place et testée. Le skill
> nomme les quatre artefacts qui mentent le plus et donne la vérification de
> chacun.


Gamma était intégré, testé, branché — et n'avait **jamais tourné** : flag
jamais activé, thème `evkha-default` inexistant, erreur qui masquait sa propre
cause. Le budget, les cibles de mots, la charte : tout est déjà écrit quelque
part.

**Lisez `main` avant de proposer. Une conclusion tirée du mauvais artefact est
pire qu'un silence.**

## 9. Un contrôle et sa réparation ne doivent pas juger sur la même évidence

Grille du *Loop Doctor* de `Forward-Future/loopy` : une boucle qui optimise et
valide contre la même mesure se donne raison toute seule.

Constaté ici le jour même. `controler_rendu` avait trois checks — balises
vides, tableaux sans données, lignes perdues : **tous des tableaux**. Et la
réparation (débrayer le découpage) ne parle que de tableaux. Un paragraphe
entier supprimé du HTML était donc déclaré « rendu fidèle ». Vérifié, pas
supposé.

**Demandez-vous ce que votre contrôle ne regarde pas — c'est exactement là que
votre réparation ne cherchera pas non plus.**

Corollaire de la règle 2, appris en le corrigeant : la première mesure de la
prose donnait 10 % de mots perdus sur un document intact, parce que le markdown
validé contient des tableaux HTML stylés en ligne et que `px`, `td`, `padding`,
`cccccc` étaient comptés comme de la prose. **Dépouillez les deux côtés, ou
vous mesurez votre propre balisage.**

## 10. Chaque génération réelle est une expérience — elle se logge

Inspiré de `karpathy/autoresearch` : un chercheur autonome ne progresse
que s'il tient un journal de ses expériences. Chaque tentative qui n'est
pas enregistrée est une leçon perdue.

Ici : **chaque dossier généré** est une expérience à **2,60 € à 4,00 €** selon
le livrable — plafond appliqué par `_BUDGET_EUR_BY_TYPE`
(`generation/services.py`), et deux études de marché complètes ont réellement
coûté 3,12 € et 3,32 €. Ce fichier annonçait « ~2 € » jusqu'au 08/08/2026 :
c'était le défaut du champ `budget_eur`, écrasé à la création du job. Une
expérience qui produit
une mesure (gate failures, retours cliente à posteriori). Cette mesure
doit être enregistrée dans `journal_generations.md` avec un verdict :

- **keep** : la génération a répondu à un défaut nommé, la cliente valide
  sur le document livré (pas juste les tests unitaires — règle 7).
- **discard** : la génération n'a pas amélioré ou a régressé.
- **blocked** : défaut identifié mais pas encore validé sur un doc réel.

Le journal cumule les leçons : on relie chaque correctif à la génération
qui l'a motivé. Sans ce lien, on refait les mêmes erreurs — pattern
observé quatre fois sur ce projet (« mêmes défauts qui reviennent »).

**Chaque correction propage à tous les livrables, pas au seul cas
observé** (règle 4). Un défaut sur un BP devient une correction qui vaut
aussi pour EM / EC / STR, sauf si le type de livrable impose autre chose
(cas des fourchettes : strict en BP/EC/STR, sourcée avec médiane en EM).

---

## Vérification obligatoire avant tout commit

```bash
ruff check .
mypy backend
pytest
python manage.py makemigrations --check --dry-run
```

Les quatre. La CI a été **rouge sur `main` pendant des mois** sans que
personne ne s'en serve : elle n'installait que `[dev]`, donc mypy ne voyait ni
`anthropic`, ni `httpx`, ni `bs4`.

### Et avant tout déploiement, la répétition à blanc

```bash
python manage.py repetition_a_blanc
```

La chaîne entière — socle, chapitres, gate — jouée sur la doublure pour les
quatre livrables. Zéro appel d'API, zéro centime. Le 10/08/2026, **trois
défauts sur cinq étaient des contradictions internes** (une consigne qui
ordonne ce qu'un contrôle interdit, une liste que l'autre moitié du code
ignore) et chacun a été découvert en payant une génération réelle — 5,22 €
d'essais pour voir ce que cette commande montre gratuitement en deux minutes.
`pytest` la rejoue aussi (`test_repetition_a_blanc.py`), mais l'exécuter
nommément avant de déployer force à en LIRE le rapport — y compris les échecs
de gate attendus sur la doublure, qui disent où le contenu réel sera jugé.

### Et pour le front, `tsc -b` — jamais `tsc --noEmit`

```bash
cd frontend && npx tsc -b --force && npx eslint src --quiet
```

`frontend/tsconfig.json` porte `"files": []` et ne fait que **référencer**
`tsconfig.app.json` et `tsconfig.node.json`. Un `npx tsc --noEmit` lancé à la
racine du front ne vérifie donc **aucun fichier** : il rend 0 quoi qu'il
arrive.

Mesuré le 06/08/2026 : `npx tsc --noEmit` a rendu « propre » sur un fichier
contenant `Cannot find name 'naviguer'`. `tsc -b` l'a trouvé du premier coup.
C'est la règle 1 appliquée à l'outillage — un contrôle qui n'a rien à comparer
n'est pas un succès, et celui-là s'était fait passer pour tel toute une
journée.

## Ne jamais faire

- **Contourner un hook** (`--no-verify`) ou masquer une erreur par un
  `type: ignore` de complaisance. Chaque erreur a une cause : `int.__pow__`
  renvoie `Any`, bs4 rend les attributs multi-valués en liste (vrai bug de
  rendu), une annotation qui ment.
- **Manipuler une clé d'API.** Elles vivent dans Coolify et dans le `.env`
  local, jamais dans le code, jamais dans une conversation.
- **Lancer une génération réelle sans accord.** Le plafond appliqué va de
  2,60 € (étude concurrentielle) à 4,00 € (étude de marché) selon le livrable,
  et deux études complètes ont coûté 3,12 € et 3,32 €. La liste qui fait foi est
  `_BUDGET_EUR_BY_TYPE` — ne pas recopier ces montants ailleurs.
- **Livrer par e-mail depuis un environnement de test** : les dossiers portent
  de vraies adresses client.
- **Déployer sans avoir vérifié qu'aucune génération ne tourne.** Un
  déploiement redémarre les conteneurs et TUE le processus qui produit les
  chapitres. Le dossier garde son statut `running` et n'est repris par
  personne.

  Constaté le 09/08/2026 : une cliente lance une étude à 06:22:59, un
  déploiement part à 06:25:56, deux autres suivent. Son dossier est resté
  « en cours » **soixante-seize minutes** à 2 chapitres sur 23, pendant qu'elle
  rafraîchissait sa page. Les journaux du serveur ne montraient qu'elle.

  La vérification tient en une requête, et elle est obligatoire avant tout
  déploiement :

  ```bash
  curl -s -H "Authorization: Bearer $EVKHA_DASHBOARD_TOKEN" https://api2.evkha.fr/api/dashboard/jobs/
  ```

  Aucun `"status": "running"` — on déploie. Sinon, on attend, ou on prévient.
  `generation.services.generation_interrompue` détecte après coup ; elle ne
  dispense pas de regarder avant.

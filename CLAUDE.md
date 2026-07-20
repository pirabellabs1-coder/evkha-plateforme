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

## Ne jamais faire

- **Contourner un hook** (`--no-verify`) ou masquer une erreur par un
  `type: ignore` de complaisance. Chaque erreur a une cause : `int.__pow__`
  renvoie `Any`, bs4 rend les attributs multi-valués en liste (vrai bug de
  rendu), une annotation qui ment.
- **Manipuler une clé d'API.** Elles vivent dans Coolify et dans le `.env`
  local, jamais dans le code, jamais dans une conversation.
- **Lancer une génération réelle sans accord** : ~2 € par dossier.
- **Livrer par e-mail depuis un environnement de test** : les dossiers portent
  de vraies adresses client.

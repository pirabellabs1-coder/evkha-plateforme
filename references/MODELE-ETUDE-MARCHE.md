# Modèle d'étude de marché — mode d'emploi

**Statut : modèle de référence définitif.** Toute génération d'étude de marché,
quelle que soit la niche du client, passe par ce modèle. Il n'existe pas d'autre
source de vérité sur la structure.

## Les fichiers

| Fichier | Rôle |
|---|---|
| `references/joalie_2026.docx` | Le document original. Sert uniquement à la comparaison visuelle finale. |
| `references/document_reference_v2.json` | L'extraction intégrale de l'original : tout le contenu, structuré en sections nommées. C'est l'**exemple complet** de ce que le moteur doit produire. |
| `references/modele_etude_marche.json` | Le **modèle variabilisé** : même structure, contenu remplacé par des variables et des consignes. C'est le **contrat de génération**. |
| `references/structurer.py` | L'extracteur de structure. À relancer sur le prochain document de référence (étude de concurrence, etc.) pour créer son modèle de la même façon. |

## Le principe en une phrase

Le modèle fixe la **charpente** (sections, séquence des blocs, dosage, longueurs
cibles) ; la niche du client ne fait varier que le **contenu** (textes, chiffres
du socle, graphiques). Le générateur remplit les emplacements du modèle, il
n'invente jamais la structure.

## Structure d'une étude — dans l'ordre, sans exception

1. **Page de garde** — fond pleine page à la couleur du client, logo, titre fixe
   « ÉTUDE DE MARCHÉ APPROFONDIE », sous-titre `{{niche.libelle}}`, encadré
   FINALITÉ, mentions.
2. **Synthèse exécutive** — introduction, tableau « Question / Réponse en une
   phrase » (5 lignes), encadré VERDICT, « Les six décisions structurantes »
   (6 paragraphes).
3. **Sommaire** — tableau 4 colonnes (Chap. / Intitulé × 2), **généré par le
   code** depuis la liste des chapitres. Jamais rédigé par le modèle de langage.
4. **Mode d'emploi de l'étude** — quasi fixe : tableau des statuts de donnée
   (Observée / Estimée), usage en comité de direction, encadré PRINCIPE DE
   LECTURE.
5. **21 chapitres** — voir ci-dessous.
6. **Quatrième de couverture** — fond pleine page, logo, `{{client.nom}}`,
   `{{client.baseline}}`, mention finale.

Les titres des 21 chapitres sont **fixes**. Seul le contenu change avec la niche.

## Le pipeline de génération

```
socle verrouillé (JSON)  ──►  pour chaque chapitre du modèle :
                                le LLM remplit les blocs du chapitre
                                (sortie JSON conforme au schéma de bloc)
                          ──►  validation : structure + data_refs
                          ──►  rendu docx : un composant par type de bloc
                          ──►  conversion PDF
```

1. **Charger** `modele_etude_marche.json`.
2. **Pour chaque chapitre**, construire le prompt avec : le socle complet, le
   chapitre du modèle (blocs + consignes + longueurs cibles), les résumés des
   chapitres déjà produits, et la fiche client (`client.*`, `niche.*`, `zone.*`).
3. **Exiger du LLM une sortie JSON** au même format que
   `document_reference_v2.json` : chaque bloc produit correspond à un bloc du
   modèle, dans le même ordre. `document_reference_v2.json` sert d'exemple
   few-shot — montrer le chapitre équivalent de Joalie dans le prompt améliore
   nettement la conformité.
4. **Valider avant rendu** (rejet + relance si échec) :
   - même séquence de types de blocs que le modèle (tolérance : ±1 tableau,
     ±1 paragraphe) ;
   - `graphiques ≥ graphiques_min` du chapitre ;
   - chaque chiffre porte un `data_ref` existant dans le socle ;
   - longueurs dans ±20 % des cibles, volume du chapitre dans ±15 %.
5. **Rendre** avec la bibliothèque de composants docx. Le renderer consomme le
   JSON, il ne reçoit jamais de texte libre.

## Les variables

Définies dans `variables_globales` du modèle. Les essentielles :

- `{{client.nom}}`, `{{client.logo}}`, `{{client.baseline}}` ;
- `{{client.couleur_principale}}` (remplace le prune `3A132C`),
  `{{client.couleur_secondaire}}` (remplace l'or `B98B4E`) — appliquées aux
  bandeaux, encadrés, tableaux, graphiques, fonds de couverture ;
- `{{niche.libelle}}`, `{{zone.*}}` — sous-titre et ancrage géographique des
  chapitres 1, 2 et 17 ;
- le **socle** — seule origine autorisée des chiffres, référencés par `data_ref`.

Aucune variable ne peut rester non résolue dans le document final : la
validation doit rejeter tout `{{` résiduel.

## Les graphiques

Le modèle impose `graphiques_min` par chapitre — **14 graphiques minimum** sur
l'étude (l'original en avait 8), dont 2 au chapitre 02 (marché national) et 2 au
chapitre 15 (tableau de bord visuel).

Chaque graphique est déclaré par le LLM en JSON, jamais dessiné par lui :

```json
{ "type": "graphique", "spec": {
    "type_graphique": "barres_verticales",
    "titre": "Taille du marché par périmètre",
    "data_refs": ["marche_mondial_taille", "marche_europe_taille"],
    "unite": "Md€" } }
```

Le code génère l'image avec matplotlib : palette `couleur_principale` /
`couleur_secondaire` / crème `F1EEDB` / rose `D8C7CF`, fond `FDFBF6`, pas de
grille verticale, étiquettes Aptos, 2000 px de large, 200 dpi. Types autorisés :
barres verticales, barres horizontales, courbe, camembert, pyramide, matrice de
positionnement, jauge. Le type se choisit selon les données : évolution →
courbe, comparaison → barres, répartition → camembert, deux dimensions →
matrice.

## Corrections à appliquer par rapport à la démo actuelle

La démo `demo_v3` est structurellement bonne (22 bandeaux, 39 encadrés, 4
grilles KPI — conformes). À corriger :

1. **Dosage** : 58 tableaux au lieu de 49, 38 sauts de page au lieu de 30, 233
   paragraphes au lieu de 200. La validation par comptage (étape 4) règle ça
   mécaniquement.
2. **Casse des titres** : la démo écrit les titres de chapitre en capitales dans
   les données. Les données portent la casse normale ; le composant bandeau
   applique les capitales au rendu.
3. **Typographie** : apostrophes typographiques (’) et non droites ('), espaces
   insécables avant `: ; ! ?`.
4. **Page de garde** : la démo n'a ni logo, ni encadré FINALITÉ, ni la
   composition de l'original. Suivre bloc à bloc la section `page_de_garde` du
   modèle.
5. **Chapitre 00 « Fiche projet »** : la démo l'ajoute en bandeau. Le modèle ne
   l'a pas — la synthèse exécutive et le mode d'emploi jouent ce rôle, sans
   numéro de chapitre.

## Règle finale

En cas de doute sur un rendu, la référence n'est ni ce guide ni le code : c'est
`references/joalie_2026.docx`, comparé page à page après rasterisation. Ce qui
diffère visuellement du modèle est un défaut, sauf si la différence vient d'une
variable client.

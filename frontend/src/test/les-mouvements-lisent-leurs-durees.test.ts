/** Chaque mouvement de `src` lit sa durée dans `tokens.css`.
 *
 * Le bloc `prefers-reduced-motion` de `tokens.css` remet les jetons de durée à
 * 0 ms : c'est ce qui arrête d'un coup toutes les animations qui les lisent.
 * Une durée écrite EN DUR lui échappe. Jusqu'au 26/09/2026, neuf animations et
 * deux transitions de `espace.css` étaient dans ce cas (`1.3s`, `1.6s`,
 * `2.8s`, `2.6s`, `2.2s`, `1.1s` deux fois, `520ms`, `0.22s`, `600ms`,
 * `0.12s`) : chacune ne s'arrêtait que si quelqu'un avait pensé à lui écrire
 * une règle `animation: none` nommée — et la transition de `transform` des
 * étoiles d'avis n'en avait aucune.
 *
 * Le verrou ne lisait que `espace.css`. Le même jour, hors de lui, la lame de
 * lumière du bouton de connexion (`public/Portail.css`, `1.3s`) et trois
 * transitions de la boutique admin (`admin/pages/BoutiqueAdmin.css`, `0.15s`
 * et `0.18s`) continuaient de tourner sous mouvement réduit. Les feuilles
 * sont désormais DÉCOUVERTES sous `src`, sous-dossiers compris (`charte.ts`),
 * `tokens.css` exclue.
 *
 * Trois verrous, des feuilles aux jetons :
 *
 * 1. aucune déclaration de mouvement d'aucune feuille (`animation`,
 *    `transition`, leurs `-duration` et `-delay`) n'écrit un temps littéral —
 *    la CLASSE du défaut (règle 4), pas la liste des valeurs ; et chaque
 *    `animation`/`transition` active lit un jeton de durée ;
 * 2. chaque jeton `--duree-*` du `:root` de `tokens.css` — et tout autre jeton
 *    dont la valeur est un temps, `--transition` ou `--decalage-reveal` — est
 *    remis à 0 dans son bloc de mouvement réduit. Un jeton ajouté sans sa
 *    remise à zéro rouvrirait le défaut par l'autre bout ;
 * 3. chaque `var(--duree-…)` lu par une feuille est déclaré : un nom mal
 *    orthographié invalide la déclaration entière, et l'animation disparaît
 *    sans un mot.
 *
 * 4. (19/11/2026) aucune feuille ne se fabrique une durée à elle : une
 *    propriété personnalisée valant un temps, déclarée hors de `tokens.css`,
 *    échappait aux trois verrous ci-dessus — elle n'est ni une déclaration
 *    de mouvement, ni un jeton de `tokens.css`. C'est par là que la page
 *    d'accueil avait posé des planchers `--acc-calme-*: 60s` que ce test ne
 *    voyait pas. Et l'exception qui les remplace est NOMMÉE : les jetons
 *    `--calme-*` de `tokens.css`, leurs feuilles, leur raison (`CALMES`), et
 *    la seule forme sous laquelle ils se lisent.
 *
 *    Le même jour, le socle de l'accueil a été mis en commun avec la page des
 *    études (`public/Site.css`) : les planchers se lisent désormais dans TROIS
 *    feuilles, et le registre dit, feuille par feuille, lesquels. Une feuille
 *    hors registre n'en lit aucun ; une feuille inscrite lit exactement les
 *    siens ; chaque plancher déclaré est lu quelque part. Rejoué par deux
 *    mutations : un plancher de plus lu par `NosEtudes.css`, puis un plancher
 *    lu par une feuille hors registre (`Boutique.css`) — rouge les deux fois.
 *
 * Contre-épreuve (règle 6) : les détecteurs laissent passer un jeton, une
 * courbe `cubic-bezier()` ou un nom d'images clés chiffré, et attrapent bien un
 * temps en dur ou un jeton oublié ; une feuille qui déclare `--x: 2s` ou qui
 * lit un `--calme-*` hors de son bloc est nommée.
 *
 * Rejoué sur les feuilles de `bdbd6e5` (sauvegarde, `git show`, restauration) :
 * rouge ; puis, élargi, sur celles de `4c88e22` : rouge sur `Portail.css` et
 * `BoutiqueAdmin.css` ; sur celles-ci : vert.
 *
 * jsdom ne calcule aucune mise en page ni aucune animation : on lit les
 * déclarations elles-mêmes, comme `un-bouton-ne-rogne-pas-son-libelle`.
 */
import { describe, expect, it } from "vitest";
import { feuillesSous, lireFeuille, sansCommentaires, SOURCE } from "./charte";

/** Feuilles pas encore passées aux jetons de durée, et pourquoi. À vider,
 *  jamais à allonger sans une raison écrite ici.
 *
 *  Vide depuis la sortie de Radix (26/09/2026) : `index.css`, seule
 *  exemptée, a perdu son `.sidebar-link` et son `0.12s` avec la console. */
const EN_ATTENTE = new Map<string, string>();

/** Le registre des planchers « calmes » : les SEULES durées de `tokens.css`
 *  qui ne tombent pas à zéro sous mouvement réduit. La liste est exacte —
 *  un jeton `--calme-*` déclaré sans y figurer, ou inscrit sans être lu, fait
 *  échouer le test. À ne jamais allonger sans une décision écrite ici.
 *
 *  `feuilles` : QUI les lit, et lesquels — liste exacte elle aussi. Trois
 *  feuilles depuis que le socle de l'accueil est partagé avec la page des
 *  études (19/11/2026) : le socle (`Site.css` — boutons, barre, menu,
 *  révélation, ruban), l'accueil (ce qui lui est propre : orbites, mur
 *  d'avis, bande finale, mot du titre, fil de la méthode) et la page des
 *  études (le survol de sa barre d'ancres). Une quatrième feuille qui lirait
 *  un plancher, ou l'une de ces trois qui en lirait un de plus, fait échouer
 *  le test : y inscrire une feuille demande une décision, écrite dans
 *  `raison`. */
const CALMES = {
  raison:
    "accueil et page des études, qui partagent le socle `Site.css` — décision du client du 19/11/2026, étendue à `/etudes` le même jour : le mouvement réduit réduit, il ne supprime pas ; un bouton pause arrête ce qui boucle",
  jetons: [
    "--calme-bande",
    "--calme-fondu",
    "--calme-mot",
    "--calme-mur",
    "--calme-mur-lent",
    "--calme-orbite",
    "--calme-ruban",
    "--calme-survol",
    "--calme-trait",
  ],
  feuilles: {
    "public/Accueil.css": [
      "--calme-bande",
      "--calme-fondu",
      "--calme-mot",
      "--calme-mur",
      "--calme-mur-lent",
      "--calme-orbite",
      "--calme-survol",
      "--calme-trait",
    ],
    "public/NosEtudes.css": ["--calme-survol"],
    "public/Site.css": ["--calme-fondu", "--calme-ruban", "--calme-survol"],
  } as Record<string, string[]>,
};

const TOUTES = feuillesSous().filter((f) => f !== SOURCE);
const VERROUILLEES = TOUTES.filter((f) => !EN_ATTENTE.has(f));

/** Une déclaration de mouvement : `animation`, `transition`, et leurs
 *  `-duration` / `-delay`, préfixe `-webkit-` compris. `animation-name` n'en
 *  est pas une — il ne porte pas de temps. */
const MOUVEMENT =
  /(?<![\w-])(?:-webkit-)?((?:animation|transition)(?:-duration|-delay)?)\s*:\s*([^;{}]*)/g;

/** Un temps écrit en dur : `1.3s`, `520ms`, `.5s`. Les bornes écartent les
 *  identifiants (`frise-2s`) et les nombres sans unité de temps
 *  (`cubic-bezier(0.22, 1, 0.36, 1)`, `12px`). */
const TEMPS_LITTERAL = /(?<![\w.-])\d*\.?\d+m?s(?![\w-])/g;

/** Un jeton qui porte une durée remise à zéro sous mouvement réduit. */
const JETON_DE_DUREE = /var\(\s*--(?:duree-[\w-]+|transition)\s*[,)]/;

interface Declaration {
  propriete: string;
  valeur: string;
}

function mouvements(css: string): Declaration[] {
  return [...sansCommentaires(css).matchAll(MOUVEMENT)].map((m) => ({
    propriete: m[1],
    valeur: m[2].replace(/\s+/g, " ").trim(),
  }));
}

function tempsLitteraux(valeur: string): string[] {
  return valeur.match(TEMPS_LITTERAL) ?? [];
}

/** Les mouvements d'une feuille qui écrivent un temps en dur. */
function mouvementsEnDur(css: string): string[] {
  return mouvements(css)
    .filter((d) => tempsLitteraux(d.valeur).length > 0)
    .map((d) => `${d.propriete}: ${d.valeur}`);
}

/** Les `animation`/`transition` actives d'une feuille qui ne lisent aucun
 *  jeton de durée. */
function mouvementsSansJeton(css: string): string[] {
  return mouvements(css)
    .filter((d) => !d.propriete.endsWith("-delay"))
    .filter((d) => d.valeur !== "none")
    .filter((d) => !JETON_DE_DUREE.test(d.valeur))
    .map((d) => `${d.propriete}: ${d.valeur}`);
}

/** Les jetons d'un bloc `:root`, nom → valeur. */
function jetons(bloc: string): Map<string, string> {
  const resultat = new Map<string, string>();
  for (const m of bloc.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
    resultat.set(m[1], m[2].replace(/\s+/g, " ").trim());
  }
  return resultat;
}

/** Le `:root` de base de `tokens.css` : celui qui précède tout `@media`. */
function racine(css: string): Map<string, string> {
  const avantMedia = sansCommentaires(css).split("@media")[0];
  const bloc = avantMedia.match(/:root\s*\{([^}]*)\}/);
  if (!bloc) throw new Error(":root introuvable dans tokens.css");
  return jetons(bloc[1]);
}

/** Le `:root` du bloc `prefers-reduced-motion: reduce` de `tokens.css`. */
function reduction(css: string): Map<string, string> {
  const bloc = sansCommentaires(css).match(
    /@media\s*\(\s*prefers-reduced-motion:\s*reduce\s*\)\s*\{\s*:root\s*\{([^}]*)\}/,
  );
  if (!bloc) throw new Error("bloc prefers-reduced-motion introuvable dans tokens.css");
  return jetons(bloc[1]);
}

/** Les jetons de durée qui ne tombent PAS à zéro sous mouvement réduit : tout
 *  `--duree-*`, et tout jeton dont la valeur est un temps. `exceptes` : les
 *  planchers du registre `CALMES`, qui existent précisément pour ne pas y
 *  tomber — vide par défaut, donc sans effet sur les contre-épreuves. */
function jetonsNonRemisAZero(css: string, exceptes: string[] = []): string[] {
  const reduits = reduction(css);
  const fautifs: string[] = [];
  for (const [nom, valeur] of racine(css)) {
    if (exceptes.includes(nom)) continue;
    const estUneDuree = nom.startsWith("--duree-") || tempsLitteraux(valeur).length > 0;
    if (!estUneDuree) continue;
    const remis = reduits.get(nom);
    if (remis === undefined || !/^(?:0+|0*\.0+)(?:ms|s)?$/.test(remis)) {
      fautifs.push(`${nom}: ${valeur} → ${remis ?? "absent du bloc"}`);
    }
  }
  return fautifs;
}

/** Les propriétés personnalisées d'une feuille dont la valeur est un temps,
 *  et toute redéclaration d'un `--calme-*`. Hors de `tokens.css`, ni l'une ni
 *  l'autre n'a le droit d'exister : une durée privée n'est remise à zéro par
 *  personne, et un plancher redéclaré localement sortirait du registre. */
function dureesPrivees(css: string): string[] {
  const fautives: string[] = [];
  for (const m of sansCommentaires(css).matchAll(/(?<![\w-])(--[\w-]+)\s*:\s*([^;{}]+)/g)) {
    const valeur = m[2].replace(/\s+/g, " ").trim();
    if (tempsLitteraux(valeur).length > 0 || m[1].startsWith("--calme-")) {
      fautives.push(`${m[1]}: ${valeur}`);
    }
  }
  return fautives;
}

/** Une feuille coupée en deux : ce qui est À L'INTÉRIEUR d'un bloc
 *  `@media (prefers-reduced-motion: reduce)`, et tout le reste. Les accolades
 *  sont comptées : un bloc contient des règles, donc des accolades. */
function selonLeMouvement(css: string): { reduit: string; ordinaire: string } {
  const texte = sansCommentaires(css);
  let reduit = "";
  let ordinaire = "";
  let curseur = 0;
  for (const m of texte.matchAll(/@media[^{]*prefers-reduced-motion:\s*reduce[^{]*\{/g)) {
    const debut = m.index;
    if (debut < curseur) continue;
    let fin = debut + m[0].length;
    let profondeur = 1;
    while (fin < texte.length && profondeur > 0) {
      if (texte[fin] === "{") profondeur += 1;
      else if (texte[fin] === "}") profondeur -= 1;
      fin += 1;
    }
    ordinaire += texte.slice(curseur, debut);
    reduit += `${texte.slice(debut + m[0].length, fin - 1)}\n`;
    curseur = fin;
  }
  ordinaire += texte.slice(curseur);
  return { reduit, ordinaire };
}

const LECTURE_CALME = /var\(\s*(--calme-[\w-]+)/g;
/** La seule forme admise : le plancher d'une durée tombée à zéro. */
const PLANCHER = /max\(\s*var\(\s*--duree-[\w-]+\s*\)\s*,\s*var\(\s*--calme-[\w-]+\s*\)\s*\)/g;

/** Les `--calme-*` qu'une feuille lit. */
function calmesLus(css: string): string[] {
  return [...new Set([...sansCommentaires(css).matchAll(LECTURE_CALME)].map((m) => m[1]))].sort();
}

/** Les lectures d'un `--calme-*` qui sortent de la règle : hors d'un bloc de
 *  mouvement réduit, ou dedans mais ailleurs que dans
 *  `max(var(--duree-…), var(--calme-…))`. */
function calmesMalLus(css: string): string[] {
  const { reduit, ordinaire } = selonLeMouvement(css);
  const fautes: string[] = [];
  for (const m of ordinaire.matchAll(LECTURE_CALME)) {
    fautes.push(`${m[1]} lu hors d'un bloc prefers-reduced-motion`);
  }
  for (const m of reduit.replace(PLANCHER, "").matchAll(LECTURE_CALME)) {
    fautes.push(`${m[1]} lu hors d'un max(var(--duree-…), var(--calme-…))`);
  }
  return fautes;
}

describe("les mouvements de src lisent leurs durées", () => {
  const tokens = lireFeuille(SOURCE);

  // Règle 1 : un contrôle qui n'a rien à comparer est un échec, pas un
  // succès. Si la découverte ou l'analyse ne trouvait rien, tout passerait.
  it("trouve les feuilles, leurs déclarations de mouvement et les jetons de durée", () => {
    expect(VERROUILLEES).toContain("theme/espace.css");
    expect(VERROUILLEES).toContain("public/Portail.css");
    expect(
      VERROUILLEES.filter((f) => f.startsWith("admin/")),
      "aucune feuille de admin/ découverte",
    ).not.toEqual([]);
    expect(mouvements(lireFeuille("theme/espace.css")).length).toBeGreaterThan(20);
    const total = VERROUILLEES.reduce((n, f) => n + mouvements(lireFeuille(f)).length, 0);
    expect(total).toBeGreaterThan(60);
    const duree = [...racine(tokens).keys()].filter((n) => n.startsWith("--duree-"));
    expect(duree.length).toBeGreaterThanOrEqual(3);
    expect(reduction(tokens).size).toBeGreaterThanOrEqual(duree.length);
  });

  it("l'exemption ne couvre que des feuilles qui existent et en ont besoin", () => {
    for (const [feuille, raison] of EN_ATTENTE) {
      expect(raison.length, `${feuille} exemptée sans raison écrite`).toBeGreaterThan(20);
      expect(TOUTES, `${feuille} exemptée mais absente`).toContain(feuille);
      const css = lireFeuille(feuille);
      expect(
        mouvementsEnDur(css).length + mouvementsSansJeton(css).length,
        `${feuille} lit ses durées dans les jetons : retirez-la de EN_ATTENTE`,
      ).toBeGreaterThan(0);
    }
  });

  it("aucune feuille n'écrit de temps en dur dans un mouvement", () => {
    const fautives = VERROUILLEES.flatMap((f) =>
      mouvementsEnDur(lireFeuille(f)).map((d) => `${f} — ${d}`),
    );
    expect(fautives).toEqual([]);
  });

  it("chaque animation et chaque transition active lit un jeton de durée", () => {
    const sansJeton = VERROUILLEES.flatMap((f) =>
      mouvementsSansJeton(lireFeuille(f)).map((d) => `${f} — ${d}`),
    );
    expect(sansJeton).toEqual([]);
  });

  it("chaque jeton de durée de tokens.css tombe à 0 sous mouvement réduit", () => {
    expect(jetonsNonRemisAZero(tokens, CALMES.jetons)).toEqual([]);
    // Sans le registre, ce sont EXACTEMENT ses jetons qui sont nommés : il
    // n'excuse rien d'autre, et il n'excuse rien qui n'existe pas.
    expect(jetonsNonRemisAZero(tokens).map((f) => f.split(":")[0]).sort()).toEqual(CALMES.jetons);
  });

  it("aucune feuille ne se fabrique une durée hors de tokens.css", () => {
    const privees = TOUTES.flatMap((f) => dureesPrivees(lireFeuille(f)).map((d) => `${f} — ${d}`));
    expect(privees).toEqual([]);
  });

  it("le registre des planchers calmes est exact, motivé, et borné à ses feuilles", () => {
    expect(CALMES.raison.length).toBeGreaterThan(40);
    const inscrites = Object.keys(CALMES.feuilles).sort();
    // Règle 1 : un registre sans feuille n'excuserait rien et ne vérifierait
    // rien. Chaque feuille inscrite existe, et lit au moins un plancher.
    expect(inscrites.length).toBeGreaterThan(0);
    for (const feuille of inscrites) {
      expect(TOUTES, `${feuille} inscrite mais absente`).toContain(feuille);
      expect(CALMES.feuilles[feuille], `${feuille} inscrite sans rien lire`).not.toEqual([]);
    }
    // Les jetons déclarés sont ceux du registre, ni plus ni moins, et aucun
    // n'est remis à zéro — il ne servirait alors plus à rien.
    const declares = [...racine(tokens).keys()].filter((n) => n.startsWith("--calme-")).sort();
    expect(declares).toEqual(CALMES.jetons);
    for (const nom of CALMES.jetons) {
      expect(tempsLitteraux(racine(tokens).get(nom) ?? ""), `${nom} n'est pas un temps`).toHaveLength(1);
      expect(reduction(tokens).has(nom), `${nom} est remis à zéro`).toBe(false);
    }
    // Seules les feuilles inscrites les lisent, et chacune lit EXACTEMENT les
    // siens : ni un de plus (l'exception s'étendrait sans décision), ni un de
    // moins (le registre mentirait sur ce que la feuille fait).
    for (const feuille of TOUTES) {
      expect(calmesLus(lireFeuille(feuille)), feuille).toEqual(CALMES.feuilles[feuille] ?? []);
    }
    // Et chaque plancher déclaré est lu quelque part : un plancher que
    // personne ne lit est une exception morte, à retirer.
    const lusQuelquePart = [...new Set(inscrites.flatMap((f) => CALMES.feuilles[f]))].sort();
    expect(lusQuelquePart).toEqual(CALMES.jetons);
  });

  it("un plancher calme ne se lit que dans max(var(--duree-…), var(--calme-…)), sous mouvement réduit", () => {
    for (const [feuille, attendus] of Object.entries(CALMES.feuilles)) {
      const css = lireFeuille(feuille);
      // Règle 1 : la feuille a bien un bloc de mouvement réduit, et il lit —
      // au moins une fois chacun des planchers qu'elle déclare lire.
      expect(
        [...selonLeMouvement(css).reduit.matchAll(PLANCHER)].length,
        `${feuille} : aucun plancher lu sous mouvement réduit`,
      ).toBeGreaterThanOrEqual(attendus.length);
    }
    // La forme est exigée de TOUTES les feuilles, inscrites ou non : une
    // lecture hors de sa règle est une faute où qu'elle soit.
    const malLus = TOUTES.flatMap((f) => calmesMalLus(lireFeuille(f)).map((d) => `${f} — ${d}`));
    expect(malLus).toEqual([]);
  });

  it("chaque var(--duree-…) lu par une feuille est déclaré dans tokens.css", () => {
    const declares = racine(tokens);
    const inconnus: string[] = [];
    let lus = 0;
    for (const feuille of TOUTES) {
      const noms = new Set(
        [...sansCommentaires(lireFeuille(feuille)).matchAll(/var\(\s*(--duree-[\w-]+)/g)].map(
          (m) => m[1],
        ),
      );
      lus += noms.size;
      for (const nom of noms) if (!declares.has(nom)) inconnus.push(`${feuille} : ${nom}`);
    }
    expect(lus).toBeGreaterThan(0);
    expect(inconnus).toEqual([]);
  });

  it("contre-épreuve : un jeton passe, un temps en dur ou un jeton oublié non", () => {
    // Ce qui est juste ne déclenche rien.
    expect(tempsLitteraux("bouton-balayage var(--duree-balayage) var(--ease-doux) infinite")).toEqual([]);
    expect(tempsLitteraux("transform var(--duree-micro) cubic-bezier(0.22, 1, 0.36, 1)")).toEqual([]);
    expect(tempsLitteraux("frise-2s-coulee var(--duree-coulee) steps(4) 12px")).toEqual([]);
    expect(JETON_DE_DUREE.test("grid-template-columns var(--transition)")).toBe(true);

    // Ce qui est faux est attrapé, sous toutes ses formes d'écriture.
    expect(tempsLitteraux("bouton-balayage 1.3s var(--ease-doux) infinite")).toEqual(["1.3s"]);
    expect(tempsLitteraux("frise-increment 520ms var(--ease-sortie) backwards")).toEqual(["520ms"]);
    expect(tempsLitteraux("annonce-entree .22s ease-out")).toEqual([".22s"]);
    expect(tempsLitteraux("color 0.12s, transform 0.12s")).toEqual(["0.12s", "0.12s"]);
    expect(JETON_DE_DUREE.test("souscription-battement 1s ease-in-out infinite")).toBe(false);
    expect(
      mouvements(".a { animation-name: x; animation-delay: 400ms; transition: none }"),
    ).toEqual([
      { propriete: "animation-delay", valeur: "400ms" },
      { propriete: "transition", valeur: "none" },
    ]);

    // Au niveau d'une feuille : une transition en dur est nommée par les deux
    // détecteurs, une transition sur jeton par aucun.
    const feuille = `
      .a { transition: background 0.15s, color 0.15s; }
      .b { transition: box-shadow var(--duree-micro), transform var(--duree-micro); }
      .c { animation: none; }`;
    expect(mouvementsEnDur(feuille)).toEqual(["transition: background 0.15s, color 0.15s"]);
    expect(mouvementsSansJeton(feuille)).toEqual(["transition: background 0.15s, color 0.15s"]);

    // Un jeton de durée oublié dans le bloc de réduction, ou remis à autre
    // chose que zéro, est nommé.
    const oublis = `
      :root { --duree-a: 1s; --duree-b: 2s; --pas: 4px; --decalage: 55ms; }
      @media (prefers-reduced-motion: reduce) {
        :root { --duree-a: 0ms; --duree-b: 100ms; }
      }`;
    expect(jetonsNonRemisAZero(oublis)).toEqual([
      "--duree-b: 2s → 100ms",
      "--decalage: 55ms → absent du bloc",
    ]);
    const justes = `
      :root { --duree-a: 1s; --transition: 140ms ease; --duree-b: 2s; }
      @media (prefers-reduced-motion: reduce) {
        :root { --duree-a: 0ms; --transition: 0s; --duree-b: 0; }
      }`;
    expect(jetonsNonRemisAZero(justes)).toEqual([]);
    const pasUnZero = `
      :root { --duree-a: 1s; }
      @media (prefers-reduced-motion: reduce) { :root { --duree-a: ms; } }`;
    expect(jetonsNonRemisAZero(pasUnZero)).toEqual(["--duree-a: 1s → ms"]);
  });

  it("contre-épreuve : une durée privée ou un plancher lu hors de sa règle est nommé", () => {
    // Une feuille qui se fabrique une durée, sous quelque nom que ce soit.
    expect(dureesPrivees(".a { --x: 2s; --acc-calme-ruban: 60s; --pas: 4px; --n: 3; }")).toEqual([
      "--x: 2s",
      "--acc-calme-ruban: 60s",
    ]);
    expect(dureesPrivees(".a { --calme-ruban: var(--duree-micro); }")).toEqual([
      "--calme-ruban: var(--duree-micro)",
    ]);
    // Ce qui n'en est pas une : un jeton lu, un repli dans `var()`, une taille.
    expect(dureesPrivees(".a { --delai: calc(var(--i, 0) * var(--decalage-reveal)); --r: 22px; }")).toEqual([]);

    // La forme admise, et elle seule.
    const juste = `
      .a { animation: tourne var(--duree-ruban) linear infinite; }
      @media (prefers-reduced-motion: reduce) {
        .a { animation-duration: max(var(--duree-ruban), var(--calme-ruban)); }
        .b { transition-duration: max( var(--duree-micro) , var(--calme-survol) ); }
      }`;
    expect(calmesMalLus(juste)).toEqual([]);
    expect(calmesLus(juste)).toEqual(["--calme-ruban", "--calme-survol"]);

    // Hors du bloc : le plancher s'appliquerait à tout le monde.
    const dehors = `
      .a { animation-duration: max(var(--duree-ruban), var(--calme-ruban)); }
      @media (prefers-reduced-motion: reduce) { .a { animation: none; } }
      .c { transition-duration: var(--calme-survol); }`;
    expect(calmesMalLus(dehors)).toEqual([
      "--calme-ruban lu hors d'un bloc prefers-reduced-motion",
      "--calme-survol lu hors d'un bloc prefers-reduced-motion",
    ]);

    // Dans le bloc, mais seul, ou sans la durée qu'il borne : ce n'est plus
    // un plancher, c'est une durée qui ne tombe jamais à zéro.
    const seul = `
      @media (prefers-reduced-motion: reduce) {
        .a { animation-duration: var(--calme-ruban); }
        .b { transition-duration: max(var(--calme-survol), var(--calme-fondu)); }
      }
      @media (prefers-reduced-motion: no-preference) {
        .c { animation-duration: max(var(--duree-ruban), var(--calme-ruban)); }
      }`;
    expect(calmesMalLus(seul)).toEqual([
      "--calme-ruban lu hors d'un bloc prefers-reduced-motion",
      "--calme-ruban lu hors d'un max(var(--duree-…), var(--calme-…))",
      "--calme-survol lu hors d'un max(var(--duree-…), var(--calme-…))",
      "--calme-fondu lu hors d'un max(var(--duree-…), var(--calme-…))",
    ]);
  });
});

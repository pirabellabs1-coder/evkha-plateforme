/** Écrit, après `vite build`, ce qu'un robot doit recevoir sans exécuter de
 * JavaScript : un fichier HTML complet par page publique, `sitemap.xml`,
 * `robots.txt` et `llms.txt`.
 *
 * Lancé par `npm run build` (voir `package.json`). Le pourquoi est en tête de
 * `src/prerendu.ts`.
 *
 * ## Ce que le script écrit dans `dist/`
 *
 *   accueil.html                    la page d'accueil
 *   etudes.html, blog/<slug>.html…  chaque page de `planDuSite.PAGES_DU_PLAN`
 *   sitemap.xml, robots.txt, llms.txt
 *
 * `index.html` N'EST PAS TOUCHÉ : il reste la coquille vide que nginx sert
 * aux routes de l'application (espace client, administration, fiches de la
 * boutique). Y écrire l'accueil ferait clignoter l'accueil sous chaque écran
 * de l'espace, et le servirait à un robot pour toute adresse inconnue.
 * `nginx.conf` sert `accueil.html` à `/` et `<chemin>.html` aux autres pages.
 *
 * ## Il échoue bruyamment (règle 1)
 *
 * Une page qui ne rend pas son titre, qui rend « introuvable », dont le
 * morceau n'est pas dans le manifeste, ou qui cite une image absente de
 * `dist/` : le script s'arrête avec un code d'erreur, la construction échoue,
 * et la version en ligne reste celle d'avant. Publier une page vide en la
 * croyant pré-rendue serait pire que de ne rien publier.
 */
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import { JSDOM } from "jsdom";

const RACINE = join(dirname(fileURLToPath(import.meta.url)), "..");
const DIST = join(RACINE, "dist");
const ENTREE = join(RACINE, "dist-prerendu", "prerendu.js");
const MANIFESTE = join(DIST, ".vite", "manifest.json");

/** Le temps laissé à une page pour se rendre. Très large : la première
 *  charge tout le site, et elle a mis 33 s dans l'image Docker sur une
 *  machine occupée (mesuré le 20/11/2026). Ce délai ne coûte rien quand tout
 *  va bien — il ne s'écoule que si une page ne se rend pas. */
const ATTENTE_MAX_MS = 180_000;
const PAS_MS = 25;

function echec(message) {
  console.error(`\nprerendre : ÉCHEC — ${message}\n`);
  process.exit(1);
}

for (const fichier of [join(DIST, "index.html"), ENTREE, MANIFESTE]) {
  if (!existsSync(fichier)) echec(`fichier attendu absent : ${fichier}`);
}

const coquille = readFileSync(join(DIST, "index.html"), "utf-8");
const manifeste = JSON.parse(readFileSync(MANIFESTE, "utf-8"));

// ── Un faux navigateur, posé AVANT de charger l'application ─────────────────
//
// `router.tsx` crée son routeur dès l'import, sur l'historique du navigateur :
// `window` doit exister à ce moment-là. L'adresse de départ est sans
// importance, chaque page pose la sienne.

const dom = new JSDOM(coquille, {
  url: "https://prerendu.invalid/",
  pretendToBeVisual: true,
});
const fenetre = dom.window;

// Tout ce que jsdom définit que Node n'a pas déjà : `window`, `document`,
// `HTMLElement`, `history`… Les globales de Node (`setTimeout`, `URL`,
// `fetch`) ne sont pas écrasées.
for (const nom of Object.getOwnPropertyNames(fenetre)) {
  if (nom in globalThis) continue;
  Object.defineProperty(globalThis, nom, {
    configurable: true,
    get: () => fenetre[nom],
  });
}
// Celles que Node définit lui aussi, selon sa version, et qui doivent être
// celles de la page : React lit `navigator`, la session lit le stockage.
for (const nom of ["navigator", "localStorage", "sessionStorage"]) {
  Object.defineProperty(globalThis, nom, { configurable: true, get: () => fenetre[nom] });
}

// Les écouteurs de la fenêtre sont hérités, pas définis sur elle : la boucle
// ci-dessus ne les voit pas, et le routeur les appelle sans préfixe.
for (const nom of ["addEventListener", "removeEventListener", "dispatchEvent"]) {
  globalThis[nom] = fenetre[nom].bind(fenetre);
}

// Le serveur ne répond pas : une promesse qui ne se résout jamais laisse
// chaque page dans son état d'ATTENTE — ni prix figé, ni message de panne
// écrit en dur dans le HTML.
const muet = () => new Promise(() => undefined);
globalThis.fetch = muet;
fenetre.fetch = muet;
fenetre.scrollTo = () => undefined;

const prerendu = await import(pathToFileURL(ENTREE).href);
const { INTERDIT_AUX_ROBOTS, ORIGINE_DU_SITE, PAGES_DU_PLAN, RUBRIQUES, monter } = prerendu;

// ── Les feuilles de style et le morceau d'une page ──────────────────────────

/** Les fichiers d'un module source et de tout ce qu'il importe : sa feuille de
 *  style à lier, son script à précharger. */
function fichiersDuModule(source) {
  const css = new Set();
  const vus = new Set();
  function visiter(cle) {
    if (vus.has(cle)) return;
    vus.add(cle);
    const entree = manifeste[cle];
    if (!entree) return;
    for (const feuille of entree.css ?? []) css.add(feuille);
    for (const importe of entree.imports ?? []) visiter(importe);
  }
  const entree = manifeste[source];
  if (!entree) echec(`« ${source} » n'est pas dans le manifeste de Vite — le chemin a changé ?`);
  visiter(source);
  return { script: entree.file, css: [...css] };
}

// ── Rendre une page ─────────────────────────────────────────────────────────

/** Les marques posées sur l'en-tête écrit. Les MÊMES noms que dans
 *  `src/enTetePrerendu.ts` — un test les tient d'accord. */
const MARQUE_AJOUTEE = "data-prerendu";
const MARQUE_CHANGEE = "data-origine";

const pause = (ms) => new Promise((resoudre) => setTimeout(resoudre, ms));

const TITRE_DE_LA_COQUILLE = fenetre.document.title;

/** Le nom du fichier d'une page : `/` → `accueil.html`, `/blog/x` →
 *  `blog/x.html`. `nginx.conf` fait le chemin inverse. */
function fichierDe(chemin) {
  return chemin === "/" ? "accueil.html" : `${chemin.slice(1)}.html`;
}

async function rendre(page) {
  const { document } = fenetre;
  const adresse = `${ORIGINE_DU_SITE}${page.chemin}`;
  dom.reconfigure({ url: adresse });

  // L'en-tête du gabarit, avant que la page n'y écrive : de quoi marquer
  // ensuite ce qu'elle a ajouté et ce qu'elle a changé (voir
  // `src/enTetePrerendu.ts`, qui défait ces marques dans le navigateur).
  const valeurDe = (balise) =>
    balise.tagName === "TITLE" ? balise.textContent : balise.getAttribute("content");
  const gabarit = new Map(Array.from(document.head.children, (balise) => [balise, valeurDe(balise)]));

  const conteneur = document.getElementById("root");
  const demonter = monter(conteneur);

  // La page est là quand elle a posé son titre, son adresse canonique et son
  // `h1`, et que son HTML ne bouge plus d'un passage à l'autre.
  const debut = Date.now();
  let precedent = "";
  for (;;) {
    await pause(PAS_MS);
    const canonique = document.head.querySelector('link[rel="canonical"]');
    const pret =
      conteneur.querySelector("h1") !== null &&
      canonique?.getAttribute("href") === adresse &&
      document.title !== TITRE_DE_LA_COQUILLE;
    const html = conteneur.innerHTML;
    if (pret && html === precedent) break;
    precedent = html;
    if (Date.now() - debut > ATTENTE_MAX_MS) {
      echec(`${page.chemin} ne s'est pas rendue en ${ATTENTE_MAX_MS / 1000} s (titre : « ${document.title} »)`);
    }
  }

  if (document.head.querySelector('meta[name="robots"][content*="noindex"]')) {
    echec(`${page.chemin} est dans le plan du site mais demande à ne pas être indexée`);
  }

  // Les fichiers que la page cite doivent exister : une image dont le nom
  // construit ici différerait de celui du site serait cassée pour le robot.
  for (const element of conteneur.querySelectorAll("[src]")) {
    const source = element.getAttribute("src") ?? "";
    if (!source.startsWith("/")) continue;
    if (!existsSync(join(DIST, decodeURIComponent(source.split(/[?#]/)[0])))) {
      echec(`${page.chemin} cite « ${source} », absent de dist/`);
    }
  }

  // Ce que la page a ajouté à l'en-tête, et ce qu'elle y a changé.
  const changees = [];
  for (const balise of document.head.children) {
    if (!gabarit.has(balise)) {
      balise.setAttribute(MARQUE_AJOUTEE, "");
    } else if (gabarit.get(balise) !== valeurDe(balise)) {
      balise.setAttribute(MARQUE_CHANGEE, gabarit.get(balise) ?? "");
      changees.push(balise);
    }
  }

  // La feuille de style et le script du morceau de la page, liés dans le
  // HTML écrit — puis retirés, pour ne pas suivre la page suivante. Posés
  // APRÈS le marquage : ils ne sont pas marqués, le navigateur les garde.
  const ajouts = [];
  if (page.module !== null) {
    const { script, css } = fichiersDuModule(page.module);
    for (const feuille of css) {
      // Déjà liée par la coquille (la feuille commune) : pas deux fois.
      if (document.head.querySelector(`link[rel="stylesheet"][href="/${feuille}"]`)) continue;
      const lien = document.createElement("link");
      lien.rel = "stylesheet";
      lien.href = `/${feuille}`;
      ajouts.push(lien);
    }
    const precharge = document.createElement("link");
    precharge.rel = "modulepreload";
    precharge.href = `/${script}`;
    ajouts.push(precharge);
  }
  document.head.append(...ajouts);
  // Le signe que la page est pré-rendue : `main.tsx` le lit pour ne pas
  // l'effacer avant d'avoir de quoi la remplacer.
  conteneur.setAttribute("data-prerendu", "");

  const html = dom.serialize();
  const titre = document.title;
  const description =
    document.head.querySelector('meta[name="description"]')?.getAttribute("content") ?? "";

  conteneur.removeAttribute("data-prerendu");
  for (const ajout of ajouts) ajout.remove();
  for (const balise of changees) balise.removeAttribute(MARQUE_CHANGEE);
  demonter();
  // Le démontage est asynchrone dans React : la page suivante ne doit pas
  // hériter des balises que celle-ci retire en partant.
  await pause(PAS_MS);
  conteneur.innerHTML = "";

  const destination = join(DIST, fichierDe(page.chemin));
  mkdirSync(dirname(destination), { recursive: true });
  writeFileSync(destination, html, "utf-8");
  return { ...page, titre, description, octets: Buffer.byteLength(html) };
}

const rendues = [];
for (const page of PAGES_DU_PLAN) {
  const rendue = await rendre(page);
  rendues.push(rendue);
  console.log(`prerendre : ${page.chemin.padEnd(44)} ${String(rendue.octets).padStart(7)} o  ${rendue.titre}`);
}

// Deux pages qui portent le même titre ou la même description : l'une des
// deux n'a pas posé les siens, et le robot lirait deux fois la même page.
for (const cle of ["titre", "description"]) {
  const vus = new Map();
  for (const page of rendues) {
    if (page[cle] === "") echec(`${page.chemin} n'a pas de ${cle}`);
    if (vus.has(page[cle])) {
      echec(`${page.chemin} et ${vus.get(page[cle])} portent le même ${cle} : « ${page[cle]} »`);
    }
    vus.set(page[cle], page.chemin);
  }
}

// ── sitemap.xml ─────────────────────────────────────────────────────────────

const xml = (texte) =>
  texte.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

writeFileSync(
  join(DIST, "sitemap.xml"),
  [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ...rendues.map((page) => `  <url><loc>${xml(ORIGINE_DU_SITE + page.chemin)}</loc></url>`),
    "</urlset>",
    "",
  ].join("\n"),
  "utf-8",
);

// ── robots.txt ──────────────────────────────────────────────────────────────
//
// Tous les robots sont admis sur les pages publiques, ceux des moteurs de
// réponse compris : c'est par eux que le site peut être cité. Seuls les
// espaces connectés et les pages de passage sont fermés.

writeFileSync(
  join(DIST, "robots.txt"),
  [
    "# EVKHA — https://evkha.fr",
    "# Écrit à la construction par scripts/prerendre.mjs : ne pas modifier à la main.",
    "",
    "User-agent: *",
    "Allow: /",
    ...INTERDIT_AUX_ROBOTS.map((prefixe) => `Disallow: ${prefixe}`),
    "",
    `Sitemap: ${ORIGINE_DU_SITE}/sitemap.xml`,
    "",
  ].join("\n"),
  "utf-8",
);

// ── llms.txt ────────────────────────────────────────────────────────────────
//
// Le plan du site pour les moteurs de réponse (llmstxt.org) : chaque page par
// son titre et sa description RÉELS, relus dans la page rendue.

const accueil = rendues.find((page) => page.chemin === "/");
if (!accueil) echec("l'accueil n'est pas dans le plan du site");
const sansMarque = (titre) => titre.replace(/\s+[—–|-]\s+EVKHA.*$/i, "").replace(/^EVKHA\s+[—–|-]\s+/i, "");

const lignes = ["# EVKHA Business & Formations", "", `> ${accueil.description}`, ""];
for (const rubrique of RUBRIQUES) {
  const pages = rendues.filter((page) => page.rubrique === rubrique);
  if (pages.length === 0) continue;
  lignes.push(`## ${rubrique}`, "");
  for (const page of pages) {
    lignes.push(`- [${sansMarque(page.titre)}](${ORIGINE_DU_SITE}${page.chemin}): ${page.description}`);
  }
  lignes.push("");
}
writeFileSync(join(DIST, "llms.txt"), lignes.join("\n"), "utf-8");

// Le manifeste et l'entrée du pré-rendu ont servi : ils ne partent pas en
// ligne.
rmSync(join(DIST, ".vite"), { recursive: true, force: true });
rmSync(join(RACINE, "dist-prerendu"), { recursive: true, force: true });

console.log(`prerendre : ${rendues.length} pages, sitemap.xml, robots.txt, llms.txt écrits dans dist/`);
// jsdom garde des minuteries ouvertes : on sort franchement.
process.exit(0);

/** Le visiteur de l'accueil ne télécharge que l'accueil.
 *
 * `router.tsx` importait tous les écrans : la page d'accueil arrivait avec
 * l'administration, l'espace client et les vingt-deux pages publiques — un
 * seul fichier de 957 Ko (mesuré le 19/11/2026 sur `b7c6ae7`). Chaque écran
 * hors de l'accueil est désormais importé quand sa route est ouverte
 * (`chargement.ts`, `ecranDiffere`).
 *
 * jsdom ne construit pas l'application : on ne mesure pas ici un poids, on
 * verrouille ce qui le FAIT — ce que le fichier d'entrée importe, et dans quel
 * ordre le routeur charge.
 *
 * 1. Les gardes d'accès passent AVANT le chargement : sans session, on est
 *    renvoyé à la connexion et le morceau de l'espace (ou de l'administration)
 *    n'a pas été demandé. Contre-épreuve : avec une session, il l'est.
 * 2. Ce que `main.tsx` importe statiquement, de proche en proche, ne contient
 *    ni l'administration, ni l'espace client, ni son client d'API, ni les
 *    gros textes (légaux, formations, packs, ressources, blog), ni aucune page
 *    publique autre que l'accueil. Contre-épreuve : en suivant aussi les
 *    imports à la demande, le même parcours les atteint tous.
 * 3. Chaque écran déclaré à la demande désigne un composant qui existe, et
 *    aucune route ne pose un composant importé statiquement, hors l'accueil.
 * 4. Un morceau qui ne vient pas est DIT, en français, avec « Recharger la
 *    page » — et la page n'est pas rechargée d'office. Contre-épreuve : le
 *    chargeur du routeur, laissé à lui-même, arme ce rechargement.
 * 5. L'attente est une page vide qui se dit à un lecteur d'écran, sans titre
 *    et sans un mot d'anglais.
 *
 * L'ORDRE des blocs compte pour le premier : les deux morceaux d'espace sont
 * remplacés par des doublures qui notent leur premier chargement, et ce
 * chargement n'a lieu qu'une fois par fichier. Le bloc 1 passe donc en tête,
 * ses refus avant ses contre-épreuves.
 *
 * Contre le code d'avant (`b7c6ae7`) : `chargement.ts`, `EtatsDuRouteur.tsx`
 * et les deux `ecrans.ts` n'existent pas, le fichier y échoue dès l'import —
 * ce qui ne prouve rien. La preuve utile est une mutation du code actuel, et
 * une seule a été jouée : `import { Packs } from "./public/Packs"` remis dans
 * `router.tsx` à la place de sa déclaration à la demande — quatre tests
 * rouges, dans les blocs 2 et 3. Les blocs 1, 4 et 5 n'ont pas été rejoués
 * par mutation ; les blocs 1 et 4 portent leur contre-épreuve, le 5 non.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { existsSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  lazyRouteComponent,
  RouterProvider,
} from "@tanstack/react-router";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { server } from "./server";

/** Les morceaux d'espace demandés depuis le début du fichier, dans l'ordre. */
const demandes = vi.hoisted(() => [] as string[]);

vi.mock("../admin/ecrans", async (original) => {
  demandes.push("administration");
  return await original();
});

vi.mock("../espace/ecrans", async (original) => {
  demandes.push("espace client");
  return await original();
});

const { EchecDeChargement, ecranDiffere } = await import("../chargement");
const { PageEnAttente, PageEnEchec } = await import("../EtatsDuRouteur");
const { creerRouteur } = await import("../router");
const { jeton } = await import("../espace/api");

const SRC = join(process.cwd(), "src");

// ── Outils ──────────────────────────────────────────────────────────────────

/** Aucun appel ne répond : ce fichier ne juge pas ce que les écrans chargent. */
function serveurMuet() {
  const muet = async () => {
    await delay("infinite");
    return new HttpResponse(null);
  };
  server.use(http.get(`${window.location.origin}/api/*`, muet));
}

/** Monte le VRAI routeur de l'application à une adresse. */
function ouvrir(adresse: string) {
  serveurMuet();
  window.history.pushState({}, "", adresse);
  const routeur = creerRouteur(createMemoryHistory({ initialEntries: [adresse] }));
  const requetes = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={requetes}>
      <RouterProvider router={routeur} />
    </QueryClientProvider>,
  );
  return routeur;
}

function source(chemin: string): string {
  return readFileSync(join(SRC, chemin), "utf-8").replace(/\r\n/g, "\n");
}

function sansCommentaires(code: string): string {
  return code.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

/** Les modules qu'un fichier importe. `statiques` : chargés avec lui.
 *  `aLaDemande` : `import("…")`, chargés quand on les appelle. Les imports de
 *  types (`import type`) ne pèsent rien : ils ne sont pas suivis. */
function imports(code: string): { statiques: string[]; aLaDemande: string[] } {
  const net = sansCommentaires(code);
  const statiques = [
    ...net.matchAll(/^[ \t]*import\s+(?!type\b)(?:[^"';]*?\sfrom\s+)?["']([^"']+)["']/gm),
    ...net.matchAll(/^[ \t]*export\s+(?!type\b)[^"';]*?\sfrom\s+["']([^"']+)["']/gm),
  ].map((m) => m[1]);
  const aLaDemande = [...net.matchAll(/\bimport\(\s*["']([^"']+)["']\s*\)/g)].map((m) => m[1]);
  return { statiques, aLaDemande };
}

/** Le fichier de `src` qu'un import relatif désigne, en chemin relatif à
 *  `src` écrit avec `/` ; `null` pour un paquet (`react`). */
function resoudre(depuis: string, cible: string): string | null {
  if (!cible.startsWith(".")) return null;
  const base = join(SRC, dirname(depuis), cible);
  for (const suffixe of ["", ".ts", ".tsx", "/index.ts", "/index.tsx"]) {
    const candidat = `${base}${suffixe}`;
    if (existsSync(candidat) && statSync(candidat).isFile()) {
      return relative(SRC, candidat).split(sep).join("/");
    }
  }
  // Règle 1 : un import qu'on ne sait pas suivre arrête le test — sinon tout
  // ce qu'il entraîne sortirait du parcours sans un mot.
  throw new Error(`import introuvable : ${cible} depuis ${depuis}`);
}

/** Tout ce qu'un fichier entraîne avec lui, de proche en proche. */
function entraine(depart: string, suivreLaDemande: boolean): Set<string> {
  const vus = new Set<string>([depart]);
  const file = [depart];
  while (file.length > 0) {
    const courant = file.pop() as string;
    if (!/\.tsx?$/.test(courant)) continue;
    const { statiques, aLaDemande } = imports(source(courant));
    for (const cible of suivreLaDemande ? [...statiques, ...aLaDemande] : statiques) {
      const fichier = resoudre(courant, cible);
      if (fichier !== null && !vus.has(fichier)) {
        vus.add(fichier);
        file.push(fichier);
      }
    }
  }
  return vus;
}

/** Ce que le visiteur de l'accueil ne doit PAS recevoir avec elle. */
function horsDeLEntree(fichier: string): boolean {
  if (/^(admin|pages)\//.test(fichier)) return true;
  if (/^espace\/(pages|composants)\//.test(fichier)) return true;
  if (["espace/Coquille.tsx", "espace/api.ts", "espace/ecrans.ts", "api.ts"].includes(fichier)) return true;
  if (/^public\/contenu(Legal|Formations|Packs|Ressources|Blog|Partenaires|Etudes)\.ts$/.test(fichier)) return true;
  if (/^viz\/.*\.tsx?$/.test(fichier)) return true;
  return false;
}

/** Les pages publiques que le fichier d'entrée a le droit d'importer : la page
 *  d'accueil, les trois pièces du socle qu'elle monte, et le formulaire des
 *  documents gratuits qu'elle porte (cliente, 24/11/2026). */
const PAGES_DE_L_ENTREE = [
  "public/Accueil.tsx",
  "public/EnTeteSite.tsx",
  "public/FormulaireAudience.tsx",
  "public/PiecesSite.tsx",
  "public/PiedSite.tsx",
];

/** Les écrans déclarés à la demande dans un fichier de routes : le nom du
 *  composant, le fichier d'où il vient, et l'export visé. */
function ecransDeclares(fichier: string): { nom: string; module: string; exporte: string }[] {
  const code = sansCommentaires(source(fichier));
  const importeurs = new Map(
    [...code.matchAll(/const (\w+) = \(\) => import\("([^"]+)"\);/g)].map((m) => [m[1], m[2]]),
  );
  const declares: { nom: string; module: string; exporte: string }[] = [];
  for (const m of code.matchAll(/const (\w+) = ecranDiffere\(\s*(\w+),\s*"(\w+)"\s*\);/g)) {
    const cible = importeurs.get(m[2]);
    if (cible === undefined) throw new Error(`${fichier} : importeur inconnu ${m[2]}`);
    declares.push({ nom: m[1], module: resoudre(fichier, cible) as string, exporte: m[3] });
  }
  for (const m of code.matchAll(
    /const (\w+) = ecranDiffere\(\s*\(\) => import\("([^"]+)"\),\s*"(\w+)"\s*\);/g,
  )) {
    declares.push({ nom: m[1], module: resoudre(fichier, m[2]) as string, exporte: m[3] });
  }
  return declares;
}

/** Les modules que les écrans désignent, chargeables un par un. Les clés sont
 *  relatives à ce fichier (`../public/Packs.tsx`). */
const MODULES = import.meta.glob<Record<string, unknown>>([
  "../admin/ecrans.ts",
  "../espace/ecrans.ts",
  "../pages/Login.tsx",
  "../public/*.tsx",
]);

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

afterEach(() => {
  cleanup();
  window.history.pushState({}, "", "/");
});

// ── 1. Les gardes passent avant le chargement ───────────────────────────────

describe("une garde d'accès refuse AVANT que le morceau ne soit demandé", () => {
  it("sans jeton d'administration : renvoyé à /login, l'administration n'est pas chargée", async () => {
    const routeur = ouvrir("/admin/jobs");
    await waitFor(() => expect(routeur.history.location.pathname).toBe("/login"));
    // La page de connexion, elle, est bien arrivée — dans son propre morceau.
    expect(await screen.findByRole("button", {}, { timeout: 8000 })).toBeInTheDocument();
    expect(demandes).not.toContain("administration");
  });

  it("sans session : renvoyé à /espace/connexion, l'espace client n'est pas chargé", async () => {
    const routeur = ouvrir("/espace/livrables");
    await waitFor(() => expect(routeur.history.location.pathname).toBe("/espace/connexion"));
    expect(
      await screen.findByRole("heading", { level: 1, name: "Accéder à votre espace" }, { timeout: 8000 }),
    ).toBeInTheDocument();
    expect(demandes).not.toContain("espace client");
    expect(demandes).not.toContain("administration");
  });

  it("l'accueil ne demande ni l'un ni l'autre", async () => {
    ouvrir("/");
    expect(await screen.findByRole("heading", { level: 1 }, { timeout: 8000 })).toBeInTheDocument();
    expect(demandes).toEqual([]);
  });

  it("contre-épreuve : avec un jeton, l'administration est demandée — et elle seule", async () => {
    localStorage.setItem("evkha_token", "jeton-d-administration");
    const routeur = ouvrir("/admin/jobs");
    await waitFor(() => expect(demandes).toContain("administration"), { timeout: 8000 });
    expect(routeur.history.location.pathname).toBe("/admin/jobs");
    expect(demandes).not.toContain("espace client");
  });

  it("contre-épreuve : avec une session, l'espace client est demandé", async () => {
    jeton.ecrire("session-ouverte");
    const routeur = ouvrir("/espace/livrables");
    await waitFor(() => expect(demandes).toContain("espace client"), { timeout: 8000 });
    expect(routeur.history.location.pathname).toBe("/espace/livrables");
  });
});

// ── 2. Ce que l'entrée entraîne ─────────────────────────────────────────────

describe("le fichier d'entrée n'entraîne que l'accueil", () => {
  const entree = entraine("main.tsx", false);
  const tout = entraine("main.tsx", true);

  it("le parcours voit l'application : le routeur, l'accueil, son texte, le socle", () => {
    // Règle 1 : un parcours qui ne trouverait rien ne condamnerait rien.
    for (const attendu of [
      "router.tsx",
      "chargement.ts",
      "EtatsDuRouteur.tsx",
      "espace/routes.tsx",
      "espace/jeton.ts",
      "public/Accueil.tsx",
      "public/contenuAccueil.ts",
      "public/contenuSite.ts",
      "public/Site.css",
      "public/Accueil.css",
    ]) {
      expect([...entree], attendu).toContain(attendu);
    }
    expect(entree.size).toBeGreaterThan(20);
  });

  it("ni l'administration, ni l'espace client, ni les gros textes ne viennent avec l'accueil", () => {
    expect([...entree].filter(horsDeLEntree).sort()).toEqual([]);
  });

  it("aucune page publique autre que l'accueil et le socle", () => {
    const pages = [...entree].filter((fichier) => /^public\/.*\.tsx$/.test(fichier)).sort();
    expect(pages).toEqual(PAGES_DE_L_ENTREE);
  });

  it("contre-épreuve : en suivant les imports à la demande, tout est atteint", () => {
    for (const attendu of [
      "admin/Coquille.tsx",
      "admin/pages/Prospection.tsx",
      "pages/Jobs.tsx",
      "pages/Login.tsx",
      "espace/Coquille.tsx",
      "espace/pages/Commander.tsx",
      "espace/api.ts",
      "public/contenuLegal.ts",
      "public/contenuFormations.ts",
      "public/contenuPacks.ts",
      "public/contenuRessources.ts",
      "public/contenuBlog.ts",
      "public/Portail.tsx",
      "public/Introuvable.tsx",
    ]) {
      expect([...tout], attendu).toContain(attendu);
      expect(entree.has(attendu), attendu).toBe(false);
    }
    // Et le détecteur nomme bien ce qu'il doit nommer.
    expect([...tout].filter(horsDeLEntree).length).toBeGreaterThan(40);
    expect(horsDeLEntree("public/Accueil.tsx")).toBe(false);
    expect(horsDeLEntree("espace/jeton.ts")).toBe(false);
    expect(horsDeLEntree("espace/engagement.ts")).toBe(false);
  });

  it("contre-épreuve : la lecture des imports distingue le statique de la demande", () => {
    const lu = imports(
      [
        'import { a } from "./a";',
        "import {",
        "  b,",
        "  c,",
        '} from "./b";',
        'import "./feuille.css";',
        'import type { T } from "./types";',
        'export { d } from "./d";',
        '// import { e } from "./commentaire";',
        'const f = () => import("./f");',
        'const g = ecranDiffere(() => import("./g"), "G");',
      ].join("\n"),
    );
    expect(lu.statiques).toEqual(["./a", "./b", "./feuille.css", "./d"]);
    expect(lu.aLaDemande).toEqual(["./f", "./g"]);
  });
});

// ── 3. Chaque écran déclaré existe ──────────────────────────────────────────

describe("chaque écran chargé à la demande désigne un composant qui existe", () => {
  const declares = [...ecransDeclares("router.tsx"), ...ecransDeclares("espace/routes.tsx")];

  it("les déclarations sont trouvées : une soixantaine d'écrans", () => {
    // Règle 1 : dix-sept écrans d'administration, quinze d'espace, et les
    // pages publiques.
    expect(declares.length).toBeGreaterThanOrEqual(60);
    expect(new Set(declares.map((ecran) => `${ecran.module}#${ecran.exporte}`)).size).toBe(declares.length);
    expect(declares.filter((ecran) => ecran.module === "admin/ecrans.ts").length).toBeGreaterThanOrEqual(17);
    expect(declares.filter((ecran) => ecran.module === "espace/ecrans.ts").length).toBeGreaterThanOrEqual(15);
  });

  it("chaque nom d'export est celui d'un composant du fichier désigné", async () => {
    const manquants: string[] = [];
    for (const ecran of declares) {
      const charger = MODULES[`../${ecran.module}`];
      if (charger === undefined) {
        manquants.push(`${ecran.module} : fichier hors de la liste du test`);
        continue;
      }
      const module = await charger();
      if (typeof module[ecran.exporte] !== "function") {
        manquants.push(`${ecran.module} n'exporte pas le composant ${ecran.exporte}`);
      }
    }
    expect(manquants).toEqual([]);
  }, 30000);

  it("aucune route ne pose un composant importé statiquement, hors l'accueil", () => {
    for (const fichier of ["router.tsx", "espace/routes.tsx"]) {
      const code = sansCommentaires(source(fichier));
      const poses = [...code.matchAll(/\bcomponent:\s*(\w+)/g)].map((m) => m[1]);
      expect(poses.length, fichier).toBeGreaterThanOrEqual(15);
      const aLaDemande = new Set(ecransDeclares(fichier).map((ecran) => ecran.nom));
      const statiques = poses.filter((nom) => !aLaDemande.has(nom));
      expect(statiques, fichier).toEqual(fichier === "router.tsx" ? ["GabaritRacine", "Accueil"] : []);
    }
  });

  it("le routeur porte l'écran d'attente, l'écran d'échec et la page introuvable", () => {
    const routeur = creerRouteur(createMemoryHistory());
    expect(routeur.options.defaultPendingComponent).toBe(PageEnAttente);
    expect(routeur.options.defaultErrorComponent).toBe(PageEnEchec);
    expect(routeur.options.defaultNotFoundComponent).toBeDefined();
  });
});

// ── 4 et 5. L'échec et l'attente ────────────────────────────────────────────

/** Un petit routeur d'une route, avec les deux écrans de l'application. */
function petitRouteur(composant: unknown, attenteMs = 1000) {
  const racine = createRootRoute();
  const route = createRoute({
    getParentRoute: () => racine,
    path: "/",
    component: composant as () => React.ReactElement,
  });
  return createRouter({
    routeTree: racine.addChildren([route]),
    history: createMemoryHistory({ initialEntries: ["/"] }),
    defaultPendingComponent: PageEnAttente,
    defaultErrorComponent: PageEnEchec,
    defaultPendingMs: attenteMs,
  });
}

/** Ce que rend le navigateur quand un fichier de l'application ne vient pas. */
const REFUS_DU_NAVIGATEUR =
  "Failed to fetch dynamically imported module: https://app.exemple/assets/Packs-abc123.js";

function importQuiEchoue(): Promise<{ Page: () => React.ReactElement }> {
  return Promise.reject(new TypeError(REFUS_DU_NAVIGATEUR));
}

function rechargementsArmes(): string[] {
  return Object.keys(sessionStorage).filter((cle) => cle.startsWith("tanstack_router_reload"));
}

describe("un morceau qui ne vient pas est dit, et la page n'est pas rechargée d'office", () => {
  beforeEach(() => {
    // React annonce dans la console l'erreur qu'une limite a attrapée : c'est
    // ce que ces tests provoquent.
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("l'écran d'échec explique, en français, et propose « Recharger la page »", async () => {
    render(<RouterProvider router={petitRouteur(ecranDiffere(importQuiEchoue, "Page"))} />);

    const bouton = await screen.findByRole("button", { name: "Recharger la page" });
    expect(bouton).toHaveAttribute("type", "button");
    const titres = screen.getAllByRole("heading", { level: 1 });
    expect(titres).toHaveLength(1);
    expect(titres[0]).toHaveTextContent("Cette page n'a pas pu être chargée.");
    expect(screen.getByRole("alert")).toHaveTextContent(/connexion a peut-être été coupée/);
    expect(screen.getByRole("alert")).toHaveTextContent(/vient d'être mis à jour/);
    expect(screen.getByRole("link", { name: "Revenir à l'accueil" })).toHaveAttribute("href", "/");
    // Ni le message anglais du routeur, ni celui du navigateur.
    expect(document.body.textContent).not.toMatch(/Something went wrong|Failed to fetch|Show Error/i);
    // Et rien n'a armé un rechargement automatique.
    expect(rechargementsArmes()).toEqual([]);
  });

  it("l'échec porte un type à nous, et garde l'erreur d'origine", async () => {
    const echec = await ecranDiffere(importQuiEchoue, "Page")
      .preload()
      .then(() => null);
    // Le chargeur n'échoue jamais lui-même : il garde l'erreur pour le rendu.
    expect(echec).toBeNull();
    expect(rechargementsArmes()).toEqual([]);

    const erreur = new EchecDeChargement(new TypeError(REFUS_DU_NAVIGATEUR));
    expect(erreur).toBeInstanceOf(Error);
    expect(erreur.message).not.toMatch(/^Failed to fetch dynamically imported module/);
    expect((erreur.origine as Error).message).toBe(REFUS_DU_NAVIGATEUR);
  });

  it("contre-épreuve : laissé à lui-même, le chargeur du routeur arme un rechargement", async () => {
    await lazyRouteComponent(importQuiEchoue, "Page").preload();
    expect(rechargementsArmes()).toEqual([`tanstack_router_reload:${REFUS_DU_NAVIGATEUR}`]);
  });

  it("une autre erreur d'affichage n'accuse pas le réseau, et donne l'adresse où écrire", async () => {
    function Casse(): React.ReactElement {
      throw new Error("TypeError: x is undefined");
    }
    render(<RouterProvider router={petitRouteur(Casse)} />);

    expect(await screen.findByRole("button", { name: "Recharger la page" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Un incident est survenu.");
    expect(screen.getByRole("alert")).not.toHaveTextContent(/connexion a peut-être été coupée/);
    expect(screen.getByRole("link", { name: "contact@evkha.fr" })).toHaveAttribute(
      "href",
      "mailto:contact@evkha.fr",
    );
    expect(document.body.textContent).not.toMatch(/x is undefined|Something went wrong/);
  });
});

describe("l'attente est une page vide, qui se dit à un lecteur d'écran", () => {
  it("seule : un état annoncé, en français, sans titre ni lien", () => {
    render(<PageEnAttente />);
    expect(screen.getByRole("status")).toHaveTextContent("Chargement de la page…");
    expect(screen.queryAllByRole("heading")).toEqual([]);
    expect(screen.queryAllByRole("link")).toEqual([]);
    expect(document.body.textContent).not.toMatch(/loading/i);
  });

  it("dans le routeur : affichée tant que le morceau n'est pas arrivé, puis remplacée par l'écran", async () => {
    let livrer: (module: { Page: () => React.ReactElement }) => void = () => undefined;
    const lent = new Promise<{ Page: () => React.ReactElement }>((resoudre) => {
      livrer = resoudre;
    });
    render(<RouterProvider router={petitRouteur(ecranDiffere(() => lent, "Page"), 0)} />);

    expect(await screen.findByRole("status")).toHaveTextContent("Chargement de la page…");
    expect(screen.queryByText("L'écran est arrivé")).toBeNull();

    livrer({ Page: () => <p>L'écran est arrivé</p> });
    expect(await screen.findByText("L'écran est arrivé", {}, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.queryByRole("status")).toBeNull();
  });
});

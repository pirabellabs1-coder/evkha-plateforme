/** Chaque lien du site a sa route, chaque route sa page, et une adresse
 * inconnue a la sienne.
 *
 * Les chemins du site public étaient écrits jusqu'à six fois : dans
 * `contenuSite.LIENS`, dans `contenuSite.CHEMINS`, dans les constantes
 * `ROUTES_*` de chaque fichier de contenu, dans `contenuLegal`, et dans
 * `router.tsx`. Rien ne tenait ces listes ensemble : un chemin renommé dans le
 * routeur laissait le menu pointer dans le vide, et aucun test ne montait le
 * VRAI routeur — chaque page était rendue seule, hors de lui.
 *
 * Il n'y a plus qu'une source, `contenuSite.CHEMINS`, que le routeur lit
 * (`path: CHEMINS.x`). Ce fichier monte l'arbre réel de `router.tsx`, par la
 * fabrique de l'application (`creerRouteur`), sur un historique en mémoire, et
 * verrouille :
 *
 * (a) chaque route publique du site rend sa page, avec exactement un `h1` —
 *     et ce n'est pas la page « introuvable » ;
 * (b) chaque ancienne adresse du site aboutit à sa cible, paramètres
 *     (`?utm_source=…`) et ancre CONSERVÉS ;
 * (c) une adresse inconnue rend la page « Page introuvable » du site, qui
 *     demande aux moteurs de ne pas l'indexer le temps de son affichage —
 *     « article introuvable » aussi ;
 * (d) chaque `href` interne du menu (`NAVIGATION`), du pied (`PIED`), de
 *     `LIENS`, de `CHEMINS` et de la page introuvable correspond à une route
 *     qui REND une page — pas à une ancienne adresse, qui ne fait que
 *     rediriger ;
 * (e) les fichiers qui recopiaient les chemins ne les écrivent plus : ils les
 *     lisent.
 *
 * Contre-épreuves (règle 6) : un chemin inventé n'a pas de route ; une
 * ancienne adresse n'est pas une page ; une vraie page ne porte pas
 * `noindex` ; le détecteur de chemin recopié voit un chemin écrit en dur.
 *
 * Les pages `/boutique` et `/partenaires` sont montées ici comme les autres :
 * ce fichier ne dit rien de leur contenu, seulement qu'elles ont une route et
 * un titre.
 *
 * ÉCRIT SANS ÊTRE JOUÉ : la consigne du lot interdisait de lancer `vitest`.
 * À rejouer contre `3ed3c1b` — où `creerRouteur`, `routeTree` et
 * `ANCIENNES_ADRESSES` n'existent pas : le fichier y échoue dès l'import, ce
 * qui ne prouve rien. La preuve utile se fait en retirant du routeur actuel
 * `search: true, hash: true` (b doit rougir), `defaultNotFoundComponent`
 * (c), et en renommant un chemin dans `router.tsx` seul (d, e).
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, within } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { ARTICLES, PAGE_ARTICLE } from "../public/contenuBlog";
import { ROUTES_FORMATIONS } from "../public/contenuFormations";
import { PAGES_LEGALES } from "../public/contenuLegal";
import { ROUTES_PACKS } from "../public/contenuPacks";
import { ROUTES_RESSOURCES } from "../public/contenuRessources";
import {
  adresseDeLArticle,
  APPEL_DE_LA_BARRE,
  CHEMINS,
  ESPACE_CLIENT,
  LIENS,
  NAVIGATION,
  PAGE_INTROUVABLE,
  PIED,
  PIED_DU_MENU,
  SLUG_IDEE_BUSINESS_VIABLE,
} from "../public/contenuSite";
import { cheminDe, titreDOnglet } from "../public/site";
import { ANCIENNES_ADRESSES, creerRouteur, routeTree } from "../router";
import { server } from "./server";

// ── Outils ──────────────────────────────────────────────────────────────────

/** Les catalogues ne répondent pas : ce test ne juge pas ce que les pages
 *  chargent, seulement qu'elles se rendent à leur adresse. */
function serveurMuet() {
  const muet = async () => {
    await delay("infinite");
    return new HttpResponse(null);
  };
  server.use(http.get(`${window.location.origin}/api/*`, muet));
}

/** L'attente d'un titre : large, la première page montée charge tout le site. */
const ATTENTE = { timeout: 8000 };

/** Monte le VRAI routeur de l'application à une adresse, sur un historique en
 *  mémoire, et attend le titre de la page. L'adresse est aussi posée sur la
 *  fenêtre : l'en-tête et le blog lisent `window.location`. */
async function ouvrir(adresse: string) {
  serveurMuet();
  window.history.pushState({}, "", adresse);
  const routeur = creerRouteur(createMemoryHistory({ initialEntries: [adresse] }));
  render(<RouterProvider router={routeur} />);
  await screen.findByRole("heading", { level: 1 }, ATTENTE);
  return routeur;
}

function titres(): HTMLElement[] {
  return screen.getAllByRole("heading", { level: 1 });
}

function balisesRobots(): string[] {
  return Array.from(document.querySelectorAll<HTMLMetaElement>('meta[name="robots"]')).map(
    (balise) => balise.content,
  );
}

const TITRE_INTROUVABLE = `${PAGE_INTROUVABLE.titre.avant} ${PAGE_INTROUVABLE.titre.fin}`;

// ── Les routes, lues dans l'arbre réel ──────────────────────────────────────

type Route = { fullPath: string; options: { component?: unknown; beforeLoad?: unknown } };

let ROUTES: Route[] | null = null;

/** Toutes les routes de l'arbre de l'application, lues une fois. */
function routes(): Route[] {
  ROUTES ??= Object.values(creerRouteur(createMemoryHistory()).routesById) as Route[];
  return ROUTES;
}

function segments(chemin: string): string[] {
  return chemin.split("/").filter((segment) => segment !== "");
}

/** Ce chemin est-il celui de ce gabarit de route ? Segment par segment ; un
 *  segment de gabarit qui commence par `$` accepte n'importe quelle valeur. */
function correspond(gabarit: string, chemin: string): boolean {
  const attendus = segments(gabarit);
  const ecrits = segments(chemin);
  return (
    attendus.length === ecrits.length &&
    attendus.every((attendu, k) => attendu.startsWith("$") || attendu === ecrits[k])
  );
}

/** Les routes qui RENDENT une page à ce chemin. Une ancienne adresse n'en
 *  est pas une : elle n'a pas de composant, elle redirige. */
function pagesA(chemin: string): Route[] {
  return routes().filter(
    (route) => route.options.component !== undefined && correspond(route.fullPath, chemin),
  );
}

// ── Ce que les données promettent ───────────────────────────────────────────

/** Une vraie page : ni gabarit de route (`$slug`), ni section (`#…`). */
function estUnePage(chemin: string): boolean {
  return !chemin.includes("$") && !chemin.includes("#");
}

/** Les pages publiques du site : tout `CHEMINS`, plus l'article relevé. La
 *  porte de l'espace client n'est pas une page du site vitrine — elle a sa
 *  coquille et ses tests ; (d) verrouille seulement qu'elle a une route. */
const PAGES_PUBLIQUES: { nom: string; adresse: string }[] = [
  ...Object.entries(CHEMINS)
    .filter(([cle, chemin]) => cle !== "espaceClient" && estUnePage(chemin))
    .map(([cle, chemin]) => ({ nom: cle, adresse: chemin as string })),
  { nom: "articleReleve", adresse: adresseDeLArticle(SLUG_IDEE_BUSINESS_VIABLE) },
];

/** Les pages dont ce lot tient le titre d'onglet. L'accueil garde le sien
 *  (marque en tête) ; la boutique et les partenaires ont leurs propres tests. */
const HORS_FORMAT_DU_TITRE = ["accueil", "boutique", "partenaires"];

/** Tous les liens internes que le site écrit, avec d'où ils viennent. */
function liensInternes(): { origine: string; lien: string }[] {
  const ecrits = [
    ...NAVIGATION.flatMap((rubrique) => [
      ...rubrique.liens.map((lien) => ({ origine: `menu « ${rubrique.libelle} »`, lien: lien.lien })),
      { origine: `mise en avant « ${rubrique.libelle} »`, lien: rubrique.enAvant.lien },
    ]),
    ...PIED.liens.map((lien) => ({ origine: "pied", lien: lien.lien })),
    ...[ESPACE_CLIENT, APPEL_DE_LA_BARRE, ...PIED_DU_MENU].map((entree) => ({
      origine: `barre « ${entree.libelle} »`,
      lien: entree.lien ?? "",
    })),
    ...Object.entries(CHEMINS).map(([cle, lien]) => ({ origine: `CHEMINS.${cle}`, lien: lien as string })),
    ...Object.entries(LIENS).map(([cle, lien]) => ({ origine: `LIENS.${cle}`, lien })),
    ...[PAGE_INTROUVABLE.accueil, ...PAGE_INTROUVABLE.portes].map((porte) => ({
      origine: `page introuvable « ${porte.libelle} »`,
      lien: porte.lien,
    })),
    ...Object.entries({ ...ROUTES_PACKS, ...ROUTES_FORMATIONS, ...ROUTES_RESSOURCES }).map(([cle, lien]) => ({
      origine: `ROUTES_*.${cle}`,
      lien: lien as string,
    })),
    ...PAGES_LEGALES.map((page) => ({ origine: `texte légal « ${page.titre} »`, lien: page.chemin as string })),
    ...ANCIENNES_ADRESSES.map(({ de, vers }) => ({ origine: `ancienne adresse ${de}`, lien: vers })),
  ];
  return ecrits.filter(({ lien }) => lien.startsWith("/"));
}

function source(chemin: string): string {
  return readFileSync(join(process.cwd(), "src", chemin), "utf-8");
}

/** Les commentaires citent les chemins entre accents graves (« `/blog` ») :
 *  ce ne sont pas des chemins écrits dans le code. */
function sansCommentaires(code: string): string {
  return code.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

/** Un chemin du site écrit EN DUR, seul dans une chaîne : `"/packs"`. Une
 *  ancienne adresse (`"/formation"`) ou un chemin plus long
 *  (`"/boutique/retour"`) n'en sont pas. L'accueil (`"/"`) est hors du
 *  détecteur : c'est aussi le chemin d'une route d'index (`/admin`). */
function cheminsRecopies(code: string): string[] {
  return Object.values(CHEMINS)
    .filter((chemin) => chemin !== CHEMINS.accueil)
    .filter((chemin) => ['"', "'", "`"].some((guillemet) => code.includes(`${guillemet}${chemin}${guillemet}`)));
}

afterEach(() => {
  cleanup();
  window.history.pushState({}, "", "/");
});

// ── (a) Chaque route publique rend sa page ──────────────────────────────────

describe("chaque route publique du site rend sa page", () => {
  it("la liste des pages publiques est celle du site : vingt pages", () => {
    // Règle 1 : une liste vide ferait passer toutes les boucles.
    expect(PAGES_PUBLIQUES.length).toBeGreaterThanOrEqual(20);
    expect(new Set(PAGES_PUBLIQUES.map((page) => page.adresse)).size).toBe(PAGES_PUBLIQUES.length);
    for (const attendue of [
      "/",
      "/etudes",
      "/boutique",
      "/partenaires",
      "/packs",
      "/packs/essentiel",
      "/packs/premium",
      "/formations",
      "/formations/creer-son-entreprise",
      "/formations/creer-sa-micro-entreprise",
      "/formations/methode-pop",
      "/boite-a-outils",
      "/blog",
      "/blog/idee-business-viable",
      "/contact",
      "/swapn",
      "/mentions-legales",
      "/rgpd",
      "/cgv",
      "/politique-de-confidentialite",
    ]) {
      expect(PAGES_PUBLIQUES.map((page) => page.adresse), attendue).toContain(attendue);
    }
    // L'article relevé existe bien dans la liste du blog.
    expect(ARTICLES.map((article) => article.slug)).toContain(SLUG_IDEE_BUSINESS_VIABLE);
  });

  for (const page of PAGES_PUBLIQUES) {
    it(`${page.adresse} : exactement un h1, et ce n'est pas la page introuvable`, async () => {
      const routeur = await ouvrir(page.adresse);

      expect(titres()).toHaveLength(1);
      expect((titres()[0].textContent ?? "").trim().length).toBeGreaterThan(3);
      expect(titres()[0]).not.toHaveTextContent(TITRE_INTROUVABLE);
      expect(titres()[0]).not.toHaveTextContent(
        `${PAGE_ARTICLE.introuvable.titre.avant} ${PAGE_ARTICLE.introuvable.titre.fin}`,
      );
      // Une vraie page se laisse indexer, et le routeur n'a rien redirigé.
      expect(balisesRobots()).toEqual([]);
      expect(routeur.history.location.pathname).toBe(page.adresse);
      // Elle porte la barre et le pied.
      expect(screen.getByRole("banner")).toBeInTheDocument();
      expect(screen.getByRole("contentinfo")).toBeInTheDocument();

      if (!HORS_FORMAT_DU_TITRE.includes(page.nom)) {
        // UN format : « Titre de la page — EVKHA ».
        expect(document.title, page.adresse).toMatch(/\S — EVKHA$/);
        expect(document.title, page.adresse).not.toMatch(/[–|]\s*EVKHA/);
        expect(titreDOnglet(document.title), page.adresse).toBe(document.title);
      }
    });
  }
});

// ── (b) Les anciennes adresses ──────────────────────────────────────────────

describe("chaque ancienne adresse aboutit à sa cible, paramètres et ancre conservés", () => {
  it("la liste des anciennes adresses est celle du routeur, et chaque cible est une page", () => {
    // Règle 1 : douze anciennes adresses, dont celle de l'article.
    expect(ANCIENNES_ADRESSES.length).toBeGreaterThanOrEqual(12);
    expect(new Set(ANCIENNES_ADRESSES.map(({ de }) => de)).size).toBe(ANCIENNES_ADRESSES.length);
    const table = Object.fromEntries(ANCIENNES_ADRESSES.map(({ de, vers }) => [de, vers]));
    expect(table["/formation"]).toBe("/formations");
    expect(table["/contacts"]).toBe("/contact");
    expect(table["/etude-achat-immediat"]).toBe("/boutique");
    expect(table["/boite-a-outils/idee-business-viable"]).toBe("/blog/idee-business-viable");
    for (const { de, vers } of ANCIENNES_ADRESSES) {
      expect(pagesA(vers).length, `${de} → ${vers}`).toBeGreaterThanOrEqual(1);
      // L'ancienne adresse elle-même a une route, et ce n'est pas une page.
      expect(routes().filter((route) => route.fullPath === de), de).toHaveLength(1);
      expect(pagesA(de), de).toEqual([]);
    }
  });

  for (const { de, vers } of ANCIENNES_ADRESSES) {
    it(`${de} → ${vers}, avec « ?utm_source=… » et « #… »`, async () => {
      const routeur = await ouvrir(`${de}?utm_source=lettre&utm_campaign=rentree#suite`);

      const arrivee = routeur.history.location;
      expect(arrivee.pathname).toBe(vers);
      const parametres = new URLSearchParams(arrivee.search);
      expect(parametres.get("utm_source")).toBe("lettre");
      expect(parametres.get("utm_campaign")).toBe("rentree");
      expect(Array.from(parametres.keys()).sort()).toEqual(["utm_campaign", "utm_source"]);
      expect(arrivee.hash).toBe("#suite");

      // Et c'est bien une page qui s'affiche, pas « introuvable ».
      expect(titres()).toHaveLength(1);
      expect(titres()[0]).not.toHaveTextContent(TITRE_INTROUVABLE);
      expect(balisesRobots()).toEqual([]);
    });
  }

  it("sans paramètre, la redirection n'en invente pas", async () => {
    const routeur = await ouvrir("/formation");
    expect(routeur.history.location.pathname).toBe("/formations");
    expect(routeur.history.location.search).toBe("");
    expect(routeur.history.location.hash).toBe("");
  });
});

// ── (c) Une adresse inconnue ────────────────────────────────────────────────

describe("une adresse inconnue rend la page introuvable du site", () => {
  for (const adresse of ["/cette-page-n-existe-pas", "/packs/inconnu", "/formations/creer/une/chose"]) {
    it(`${adresse} : « Page introuvable », dans la charte, avec ses portes de sortie`, async () => {
      await ouvrir(adresse);

      expect(titres()).toHaveLength(1);
      expect(titres()[0]).toHaveTextContent(TITRE_INTROUVABLE);
      // Ni le « Not Found » nu du routeur, ni une page sans barre.
      expect(document.body.textContent).not.toMatch(/Not Found/i);
      expect(screen.getByRole("banner")).toBeInTheDocument();
      expect(screen.getByRole("contentinfo")).toBeInTheDocument();
      expect(document.title).toBe(titreDOnglet(PAGE_INTROUVABLE.titreOnglet));
      expect(document.title).toBe("Page introuvable — EVKHA");

      // Le retour à l'accueil, puis les études, la boutique et le contact.
      const principal = screen.getByRole("main");
      const portes = Array.from(principal.querySelectorAll("a")).map((a) => a.getAttribute("href"));
      expect(portes).toEqual(["/", "/etudes", "/boutique", "/contact"]);
      for (const porte of [PAGE_INTROUVABLE.accueil, ...PAGE_INTROUVABLE.portes]) {
        expect(within(principal).getByRole("link", { name: new RegExp(porte.libelle) })).toHaveAttribute(
          "href",
          porte.lien,
        );
      }
      expect(principal.id).not.toBe("");
      expect(screen.getByRole("link", { name: "Aller au contenu" })).toHaveAttribute("href", `#${principal.id}`);
    });
  }

  it("elle demande de ne pas être indexée, le temps de son affichage seulement", async () => {
    expect(balisesRobots()).toEqual([]);
    await ouvrir("/cette-page-n-existe-pas");
    expect(balisesRobots()).toEqual(["noindex"]);
    cleanup();
    expect(balisesRobots()).toEqual([]);
  });

  it("« article introuvable » aussi, et un vrai article non", async () => {
    await ouvrir(adresseDeLArticle("nulle-part"));
    expect(titres()[0]).toHaveTextContent(
      `${PAGE_ARTICLE.introuvable.titre.avant} ${PAGE_ARTICLE.introuvable.titre.fin}`,
    );
    expect(balisesRobots()).toEqual(["noindex"]);
    expect(document.title).toBe(titreDOnglet(PAGE_ARTICLE.introuvable.titreOnglet));
    cleanup();
    expect(balisesRobots()).toEqual([]);

    // Contre-épreuve : un article qui existe se laisse indexer.
    await ouvrir(adresseDeLArticle(SLUG_IDEE_BUSINESS_VIABLE));
    expect(balisesRobots()).toEqual([]);
  });
});

// ── (d) Chaque lien interne a sa route ──────────────────────────────────────

describe("chaque lien interne du site correspond à une route du routeur", () => {
  it("l'arbre monté est celui de l'application", () => {
    expect(routeTree).toBeDefined();
    const chemins = routes().map((route) => route.fullPath);
    // Règle 1 : un arbre vide n'aurait aucune route à comparer.
    expect(chemins.length).toBeGreaterThan(50);
    expect(chemins).toContain("/blog/$slug");
    expect(chemins).toContain("/espace/connexion");
  });

  it("menu, pied, LIENS, CHEMINS, alias et page introuvable : chaque lien mène à une page", () => {
    const liens = liensInternes();
    // Règle 1 : des dizaines de liens internes sont écrits dans les données.
    expect(liens.length).toBeGreaterThan(70);
    const sansRoute = liens.filter(({ lien }) => {
      const chemin = cheminDe(lien);
      return chemin === null || pagesA(chemin).length === 0;
    });
    expect(sansRoute).toEqual([]);
  });

  it("chaque chemin de CHEMINS est, au caractère près, celui d'une route", () => {
    const chemins = routes().map((route) => route.fullPath);
    for (const [cle, chemin] of Object.entries(CHEMINS)) {
      if (chemin.includes("#")) continue;
      expect(chemins, `CHEMINS.${cle}`).toContain(chemin);
    }
    // La seule entrée à ancre vise une section d'une page qui a sa route.
    expect(Object.values(CHEMINS).filter((chemin) => chemin.includes("#"))).toEqual([CHEMINS.commentCaMarche]);
    expect(cheminDe(CHEMINS.commentCaMarche)).toBe(CHEMINS.etudes);
  });

  it("les alias des fichiers de contenu lisent CHEMINS", () => {
    expect(ROUTES_PACKS).toEqual({
      ensemble: CHEMINS.packs,
      essentiel: CHEMINS.packEssentiel,
      premium: CHEMINS.packPremium,
    });
    expect(ROUTES_FORMATIONS.catalogue).toBe(CHEMINS.formations);
    expect(ROUTES_FORMATIONS.societes).toBe(CHEMINS.formationSocietes);
    expect(ROUTES_FORMATIONS.micro).toBe(CHEMINS.formationMicro);
    expect(ROUTES_FORMATIONS.pop).toBe(CHEMINS.formationPop);
    expect(ROUTES_RESSOURCES.boiteAOutils).toBe(CHEMINS.boiteAOutils);
    expect(ROUTES_RESSOURCES.contact).toBe(CHEMINS.contact);
    expect(LIENS.packs).toBe(CHEMINS.packs);
    expect(LIENS.formations).toBe(CHEMINS.formations);
    expect(LIENS.outils).toBe(CHEMINS.boiteAOutils);
    expect(LIENS.article).toBe(adresseDeLArticle(SLUG_IDEE_BUSINESS_VIABLE));
    expect(PAGES_LEGALES.map((page) => page.chemin).sort()).toEqual(
      [CHEMINS.cgv, CHEMINS.mentionsLegales, CHEMINS.confidentialite, CHEMINS.rgpd].sort(),
    );
  });

  it("contre-épreuve : un chemin inventé n'a pas de route, une ancienne adresse n'est pas une page", () => {
    expect(pagesA("/nulle-part")).toEqual([]);
    expect(pagesA("/packs/inconnu")).toEqual([]);
    expect(pagesA("/formation")).toEqual([]);
    expect(pagesA("/packs").length).toBe(1);
    expect(pagesA("/blog/un-article-quelconque").length).toBe(1);

    expect(correspond("/blog/$slug", "/blog/idee-business-viable")).toBe(true);
    expect(correspond("/blog/$slug", "/blog")).toBe(false);
    expect(correspond("/blog/$slug", "/blog/a/b")).toBe(false);
    expect(correspond("/packs", "/packs/")).toBe(true);
    expect(correspond("/packs", "/pack")).toBe(false);
    expect(correspond("/", "/")).toBe(true);
    expect(correspond("/", "/etudes")).toBe(false);
  });
});

// ── (e) Une seule source ────────────────────────────────────────────────────

describe("les chemins du site ne sont écrits qu'une fois", () => {
  const LECTEURS = [
    "router.tsx",
    "public/contenuPacks.ts",
    "public/contenuFormations.ts",
    "public/contenuRessources.ts",
    "public/contenuBlog.ts",
    "public/contenuLegal.ts",
    "public/PagesLegales.tsx",
    "public/Blog.tsx",
    "public/Ressources.tsx",
    "public/Packs.tsx",
    "public/Formations.tsx",
    "public/Introuvable.tsx",
  ];

  for (const fichier of LECTEURS) {
    it(`${fichier} ne recopie aucun chemin du site`, () => {
      const code = source(fichier);
      // Règle 1 : un fichier vide ou introuvable ne « passe » pas.
      expect(code.length, fichier).toBeGreaterThan(1500);
      expect(cheminsRecopies(sansCommentaires(code)), fichier).toEqual([]);
    });
  }

  it("router.tsx lit CHEMINS pour les routes du site, et garde les paramètres des redirections", () => {
    const code = source("router.tsx");
    expect((code.match(/path: CHEMINS\.\w+/g) ?? []).length).toBeGreaterThanOrEqual(20);
    expect(code).toMatch(/search: true/);
    expect(code).toMatch(/hash: true/);
    expect(code).toContain("defaultNotFoundComponent: Introuvable");
    // Le slug de l'article n'est plus écrit dans une redirection.
    expect(code).toContain("params: { slug: SLUG_IDEE_BUSINESS_VIABLE }");
  });

  it("contre-épreuve : le détecteur voit un chemin écrit en dur, et lui seul", () => {
    expect(cheminsRecopies('path: "/packs",')).toEqual(["/packs"]);
    expect(cheminsRecopies("lien: '/formations/methode-pop'")).toEqual(["/formations/methode-pop"]);
    expect(cheminsRecopies("const a = `/blog`;")).toEqual(["/blog"]);
    expect(cheminsRecopies('ancienneAdresse("/formation", CHEMINS.formations)')).toEqual([]);
    expect(cheminsRecopies('path: "/boutique/retour",')).toEqual([]);
    expect(cheminsRecopies('path: "/",')).toEqual([]);
    expect(cheminsRecopies("path: CHEMINS.packs,")).toEqual([]);
    // La source, elle, les écrit — une fois chacun.
    const origine = source("public/contenuSite.ts");
    expect(cheminsRecopies(sansCommentaires(origine)).length).toBeGreaterThan(15);
    // Et un chemin cité dans un commentaire n'est pas un chemin recopié.
    expect(cheminsRecopies(sansCommentaires("/** La page `/blog`. */\n// vers `/packs`\nconst a = 1;"))).toEqual([]);
  });
});

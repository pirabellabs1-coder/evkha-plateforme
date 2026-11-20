/** Le plan du site n'oublie aucune page, et ce qui le sert aux robots est
 * branché de bout en bout.
 *
 * `planDuSite.PAGES_DU_PLAN` est la liste d'où sortent les pages pré-rendues,
 * `sitemap.xml` et `llms.txt`. Une page absente de cette liste reste, pour un
 * robot sans JavaScript, la coquille vide mesurée le 20/11/2026 — sans que
 * rien ne le signale. Ce fichier verrouille donc :
 *
 * (a) chaque chemin de `contenuSite.CHEMINS` est dans le plan, ou dans
 *     `HORS_DU_PLAN` avec sa raison — et chaque article du blog y est ;
 * (b) chaque page du plan nomme le fichier que le routeur charge VRAIMENT
 *     pour elle : c'est là que le pré-rendu lit la feuille de style à lier ;
 * (c) ce qui est interdit aux robots correspond à des routes réelles, et
 *     aucune page du plan n'est interdite ;
 * (d) la chaîne qui sert ces fichiers est entière : `npm run build` lance le
 *     pré-rendu, l'image Docker embarque son script, et nginx sert
 *     `<chemin>.html` — sans réintroduire le test de répertoire qui masquait
 *     `/partenaires` (voir `test_les_routes_ne_sont_pas_masquees_par_un_dossier`).
 *
 * Contre-épreuves (règle 6) : un chemin inventé n'est pas dans le plan ; une
 * route privée n'y est pas non plus.
 *
 * Il lit les FICHIERS de configuration : ce sont eux qui partent en
 * production. Ce que nginx sert réellement se prouve sur l'image construite
 * (`docs/referencement/etat-et-plan.md`), pas ici (règle 7).
 */
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { createMemoryHistory } from "@tanstack/react-router";
import { describe, expect, it } from "vitest";

import { ARTICLES } from "../public/contenuBlog";
import { adresseDeLArticle, CHEMINS } from "../public/contenuSite";
import {
  HORS_DU_PLAN,
  INTERDIT_AUX_ROBOTS,
  PAGES_DU_PLAN,
  RUBRIQUES,
} from "../public/planDuSite";
import { creerRouteur } from "../router";

const FRONT = join(__dirname, "..", "..");
const lire = (fichier: string) => readFileSync(join(FRONT, fichier), "utf-8");

const chemins = PAGES_DU_PLAN.map((page) => page.chemin);

describe("le plan du site", () => {
  it("(a) chaque chemin public est dans le plan, ou en est exclu avec sa raison", () => {
    for (const [nom, chemin] of Object.entries(CHEMINS)) {
      const dansLePlan = chemins.includes(chemin);
      const exclu = chemin in HORS_DU_PLAN;
      expect(dansLePlan || exclu, `CHEMINS.${nom} (${chemin}) n'est ni dans le plan ni exclu`).toBe(true);
      expect(dansLePlan && exclu, `CHEMINS.${nom} est à la fois dans le plan et exclu`).toBe(false);
    }
    for (const raison of Object.values(HORS_DU_PLAN)) expect(raison.length).toBeGreaterThan(10);
  });

  it("(a) chaque article du blog est dans le plan", () => {
    expect(ARTICLES.length).toBeGreaterThan(1);
    for (const article of ARTICLES) {
      expect(chemins, article.slug).toContain(adresseDeLArticle(article.slug));
    }
  });

  it("aucune adresse n'y figure deux fois, et chacune a une rubrique connue", () => {
    expect(new Set(chemins).size).toBe(chemins.length);
    for (const page of PAGES_DU_PLAN) {
      expect(RUBRIQUES, page.chemin).toContain(page.rubrique);
      expect(page.chemin.startsWith("/"), page.chemin).toBe(true);
      // Ni paramètre, ni ancre, ni barre finale : c'est l'adresse canonique.
      expect(page.chemin, page.chemin).not.toMatch(/[?#]|.\/$/);
    }
  });

  it("(b) chaque page nomme le fichier que le routeur charge pour elle", () => {
    const routeur = lire("src/router.tsx");
    const modules = new Set(PAGES_DU_PLAN.map((page) => page.module));
    expect(modules.size).toBeGreaterThan(5);
    for (const module of modules) {
      if (module === null) continue;
      expect(existsSync(join(FRONT, module)), module).toBe(true);
      const importe = `import("./${module.replace(/^src\//, "").replace(/\.tsx$/, "")}")`;
      expect(routeur, `router.tsx n'écrit pas ${importe}`).toContain(importe);
    }
    // L'accueil, seul, est livré avec l'application.
    expect(PAGES_DU_PLAN.filter((page) => page.module === null).map((page) => page.chemin)).toEqual([
      CHEMINS.accueil,
    ]);
  });

  it("(c) ce qui est interdit aux robots est une route réelle, et aucune page du plan ne l'est", () => {
    const routes = Object.values(creerRouteur(createMemoryHistory()).routesById).map(
      (route) => (route as { fullPath: string }).fullPath,
    );
    for (const prefixe of INTERDIT_AUX_ROBOTS) {
      if (prefixe === "/api/") continue; // servi par Django, hors du routeur
      expect(
        routes.some((route) => route === prefixe || route.startsWith(`${prefixe}/`)),
        `${prefixe} ne correspond à aucune route`,
      ).toBe(true);
      for (const chemin of chemins) {
        expect(chemin === prefixe || chemin.startsWith(`${prefixe}/`), `${chemin} est interdit`).toBe(false);
      }
    }
  });

  it("contre-épreuve : ni un chemin inventé ni une route privée ne sont dans le plan", () => {
    expect(chemins).not.toContain("/une-page-inventee");
    for (const prive of ["/admin", "/espace/connexion", "/login", "/inscription"]) {
      expect(chemins).not.toContain(prive);
    }
  });
});

describe("(d) la chaîne qui sert les pages pré-rendues est entière", () => {
  it("`npm run build` lance le pré-rendu après Vite", () => {
    const scripts = (JSON.parse(lire("package.json")) as { scripts: Record<string, string> }).scripts;
    expect(scripts.build).toMatch(/vite build && npm run prerendre$/);
    expect(scripts.prerendre).toContain("vite.prerendu.config.ts");
    expect(scripts.prerendre).toMatch(/&& node scripts\/prerendre\.mjs$/);
    for (const fichier of ["scripts/prerendre.mjs", "vite.prerendu.config.ts", "src/prerendu.ts"]) {
      expect(existsSync(join(FRONT, fichier)), fichier).toBe(true);
    }
  });

  it("l'image Docker embarque le script et sa configuration", () => {
    const docker = lire("Dockerfile");
    expect(docker).toContain("frontend/vite.prerendu.config.ts");
    expect(docker).toMatch(/COPY frontend\/scripts \.\/scripts\r?\n[\s\S]*RUN npm run build/);
  });

  it("le script écrit les fichiers aux noms que nginx sert", () => {
    const script = lire("scripts/prerendre.mjs");
    const nginx = lire("nginx.conf")
      .split("\n")
      .filter((ligne) => !ligne.trim().startsWith("#"))
      .join("\n");

    // `/etudes` → `etudes.html` : écrit par le script, servi par `$uri.html`.
    expect(script).toContain("`${chemin.slice(1)}.html`");
    expect(nginx).toMatch(/location \/ \{\s*try_files \$uri \$uri\.html \/index\.html;/);
    // L'accueil a son fichier : `index.html` reste la coquille de l'application.
    expect(script).toContain('"accueil.html"');
    expect(nginx).toMatch(/location = \/ \{\s*try_files \/accueil\.html \/index\.html;/);
    // Jamais de test de répertoire : il masquait `/partenaires` (403).
    expect(nginx).not.toMatch(/try_files[^;]*\$uri\/[\s;]/);
    // `robots.txt`, `sitemap.xml`, `llms.txt` : écrits par le script.
    for (const fichier of ["sitemap.xml", "robots.txt", "llms.txt"]) {
      expect(script).toContain(`"${fichier}"`);
    }
  });

  it("le gabarit porte toujours la preuve de propriété de la Search Console", () => {
    // Le pré-rendu part de `index.html` : la balise y est, elle est donc dans
    // chaque page écrite — dont l'accueil, où Google la relit.
    expect(lire("index.html")).toMatch(/<meta\s+name="google-site-verification"\s+content="[^"]{20,}"/);
  });
});

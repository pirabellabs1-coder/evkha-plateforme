/** nginx connaît chaque route de l'application, et répond 404 au reste.
 *
 * Jusqu'au 20/11/2026, le dernier recours de nginx était la coquille de
 * l'application, en 200 : `/nimporte-quoi` « existait » pour un moteur, et les
 * anciennes adresses du site n'étaient renvoyées que par le navigateur. Le
 * dernier recours est maintenant un 404. Ce qui doit répondre autre chose est
 * donc DIT dans `nginx.conf` — et une route ajoutée au routeur sans y être
 * dite répondrait 404 à un robot, en silence (règle 1). Ce fichier le
 * verrouille :
 *
 * (a) chaque route du routeur reçoit de nginx ce qu'elle doit recevoir : sa
 *     page pré-rendue, la coquille en 200, la fiche écrite par Django, ou un
 *     renvoi permanent vers la bonne page ;
 * (b) les anciennes adresses de `router.ANCIENNES_ADRESSES` et les renvois de
 *     nginx sont la même liste, vers les mêmes pages ;
 * (c) une adresse inconnue, un fichier pré-rendu demandé par son nom, un
 *     article qui n'existe pas : 404 ;
 * (d) le plan du site des fiches est servi, et `robots.txt` le déclare.
 *
 * `decider` relit les blocs `location` du VRAI fichier et applique l'ordre de
 * nginx : égalité stricte, puis expressions dans l'ordre du fichier, puis le
 * bloc général. Ce n'est pas nginx : ce que le serveur répond réellement se
 * prouve sur l'image construite (règle 7). Ce test empêche l'oubli.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createMemoryHistory } from "@tanstack/react-router";
import { describe, expect, it } from "vitest";

import { ARTICLES } from "../public/contenuBlog";
import { adresseDeLArticle } from "../public/contenuSite";
import { PAGES_DU_PLAN } from "../public/planDuSite";
import { ANCIENNES_ADRESSES, creerRouteur } from "../router";

const FRONT = join(__dirname, "..", "..");
const lire = (fichier: string) => readFileSync(join(FRONT, fichier), "utf-8");

/** `nginx.conf` sans ses commentaires. */
const sansCommentaires = lire("nginx.conf")
  .split("\n")
  .filter((ligne) => !ligne.trim().startsWith("#"))
  .join("\n");

/** Le renvoi de l'ancien nom `app2.` : la seule directive à accolades posée
 *  DANS un bloc. Elle est remplacée par un mot avant la lecture des blocs,
 *  que ce fichier découpe d'une accolade à la suivante. */
const RENVOI_DE_L_ANCIEN_NOM = "if ($domaine_nu) { return 301 https://$domaine_nu$request_uri; }";
const MARQUE_DU_RENVOI = "renvoi_de_l_ancien_nom;";

const nginx = sansCommentaires.split(RENVOI_DE_L_ANCIEN_NOM).join(MARQUE_DU_RENVOI);

type Reponse =
  | { quoi: "page" } // le fichier pré-rendu de la page
  | { quoi: "coquille" } // l'application, en 200
  | { quoi: "fiche" } // écrite par Django
  | { quoi: "plan-boutique" }
  | { quoi: "renvoi"; vers: string }
  | { quoi: "introuvable" }; // 404

function lireLeCorps(corps: string): Reponse | null {
  const renvoi = /return 301 (\S+?)(?:\$is_args\$args)?;/.exec(corps);
  if (renvoi) return { quoi: "renvoi", vers: renvoi[1] };
  if (/boutique\/plan\.xml/.test(corps)) return { quoi: "plan-boutique" };
  if (/proxy_pass/.test(corps)) return { quoi: "fiche" };
  if (/^\s*internal;\s*$/m.test(corps)) return { quoi: "introuvable" };
  if (/try_files \/index\.html =404;/.test(corps)) return { quoi: "coquille" };
  return null;
}

const egalites = new Map<string, string>();
for (const [, chemin, corps] of nginx.matchAll(/location = (\S+) \{([^}]*)\}/g)) {
  egalites.set(chemin, corps);
}
const expressions = Array.from(nginx.matchAll(/location ~ (\S+) \{([^}]*)\}/g), ([, motif, corps]) => ({
  motif: new RegExp(motif),
  corps,
}));

const pagesEcrites = new Set(PAGES_DU_PLAN.map((page) => page.chemin));

function decider(chemin: string): Reponse {
  const exact = egalites.get(chemin);
  if (exact !== undefined) {
    if (chemin === "/") return { quoi: "page" };
    const lu = lireLeCorps(exact);
    if (lu === null) throw new Error(`bloc « location = ${chemin} » illisible`);
    return lu;
  }
  for (const { motif, corps } of expressions) {
    if (!motif.test(chemin)) continue;
    const lu = lireLeCorps(corps);
    if (lu === null) throw new Error(`bloc « location ~ ${motif.source} » illisible`);
    return lu;
  }
  // Le bloc général : la barre finale renvoie, puis `$uri.html` ou 404.
  if (chemin.length > 1 && chemin.endsWith("/")) return { quoi: "renvoi", vers: chemin.slice(0, -1) };
  return pagesEcrites.has(chemin) ? { quoi: "page" } : { quoi: "introuvable" };
}

/** Les routes du routeur, un paramètre remplacé par une valeur d'exemple. */
const routes = Array.from(
  new Set(
    Object.values(creerRouteur(createMemoryHistory()).routesById)
      .map((route) => (route as { fullPath: string }).fullPath)
      .filter((chemin) => chemin !== "")
      .map((chemin) => (chemin.length > 1 ? chemin.replace(/\/$/, "") : chemin)),
  ),
);

const anciennes = new Map(ANCIENNES_ADRESSES.map(({ de, vers }) => [de, vers]));

describe("nginx connaît chaque route de l'application", () => {
  it("le fichier se lit : le bloc général finit par un 404 servi avec la coquille", () => {
    expect(nginx).toMatch(/location \/ \{[^}]*try_files \$uri \$uri\.html =404;/);
    expect(nginx).toMatch(/error_page 404 \/index\.html;/);
    expect(nginx).toMatch(/absolute_redirect off;/);
    expect(routes.length).toBeGreaterThan(50);
    expect(expressions.length).toBeGreaterThanOrEqual(3);
  });

  it("(a) chaque route reçoit sa page, la coquille, sa fiche ou son renvoi — jamais un 404", () => {
    for (const route of routes) {
      const chemin = route.replace(/\$[a-zA-Z]+/g, "exemple");
      const reponse = decider(chemin);

      if (anciennes.has(route)) {
        expect(reponse, route).toEqual({ quoi: "renvoi", vers: anciennes.get(route) });
      } else if (pagesEcrites.has(route)) {
        expect(reponse, route).toEqual({ quoi: "page" });
      } else if (route === "/boutique/$slug") {
        expect(reponse, route).toEqual({ quoi: "fiche" });
      } else if (route === "/blog/$slug") {
        // Un article qui n'existe pas n'a pas de fichier : 404. Ceux qui
        // existent sont dans le plan, et vérifiés plus bas.
        expect(reponse, route).toEqual({ quoi: "introuvable" });
      } else {
        expect(reponse, `${route} n'est pas dite dans nginx.conf`).toEqual({ quoi: "coquille" });
      }
    }
  });

  it("(a) chaque page du plan, article compris, a son fichier", () => {
    for (const chemin of pagesEcrites) expect(decider(chemin), chemin).toEqual({ quoi: "page" });
    for (const article of ARTICLES) {
      expect(decider(adresseDeLArticle(article.slug)), article.slug).toEqual({ quoi: "page" });
    }
  });

  it("(a) les retours de paiement ne sont pas pris pour une fiche ni pour une page", () => {
    expect(decider("/boutique/retour")).toEqual({ quoi: "coquille" });
    expect(decider("/formations/retour")).toEqual({ quoi: "coquille" });
    expect(decider("/acheter/retour")).toEqual({ quoi: "coquille" });
    expect(decider("/espace/livrables/une-reference")).toEqual({ quoi: "coquille" });
  });

  it("(b) les renvois de nginx sont exactement les anciennes adresses du routeur", () => {
    const bloc = /# anciennes-adresses\r?\n([\s\S]*?)# fin-des-anciennes-adresses/.exec(lire("nginx.conf"));
    expect(bloc, "le bloc des anciennes adresses est introuvable").not.toBeNull();
    const ecrites = new Map(
      Array.from(
        (bloc as RegExpExecArray)[1].matchAll(/location = (\S+) \{ return 301 (\S+)\$is_args\$args; \}/g),
        ([, de, vers]) => [de, vers] as const,
      ),
    );
    expect(anciennes.size).toBeGreaterThan(10);
    expect(Object.fromEntries(ecrites)).toEqual(Object.fromEntries(anciennes));
    // Aucun renvoi ne mène à une adresse elle-même renvoyée ou inconnue.
    for (const vers of ecrites.values()) expect(decider(vers), vers).toEqual({ quoi: "page" });
  });

  it("(c) contre-épreuves : ce qui n'existe pas répond 404", () => {
    for (const chemin of [
      "/nimporte-quoi",
      "/etudes.html",
      "/accueil.html",
      "/blog/un-article-qui-n-existe-pas",
      "/formations/une-formation-inventee",
      "/packs/inconnu",
      "/administration",
      "/espacement",
    ]) {
      expect(decider(chemin), chemin).toEqual({ quoi: "introuvable" });
    }
    // La coquille reste lisible par son nom : Django vient l'y prendre.
    expect(expressions.some(({ motif }) => motif.test("/index.html"))).toBe(false);
    // L'accueil n'a qu'une adresse, et la barre finale renvoie.
    expect(decider("/accueil")).toEqual({ quoi: "renvoi", vers: "/" });
    expect(decider("/etudes/")).toEqual({ quoi: "renvoi", vers: "/etudes" });
  });

  it("(c) le renvoi de la barre finale ne mène jamais hors du site", () => {
    const ecrit = /rewrite "([^"]+)" \/\$1 permanent;/.exec(nginx);
    expect(ecrit, "le renvoi de la barre finale est introuvable").not.toBeNull();
    const motif = new RegExp((ecrit as RegExpExecArray)[1]);
    // Ce qu'il renvoie : une adresse du site, barre finale en moins.
    expect(motif.exec("/etudes/")?.[1]).toBe("etudes");
    expect(motif.exec("/blog/idee-business-viable/")?.[1]).toBe("blog/idee-business-viable");
    // Ce qu'il ne touche pas. nginx DÉCODE l'adresse avant de la comparer :
    // `/%5Cevil.com/` arrive ici `/\\evil.com/`, et renvoyait vers
    // `/\\evil.com` — qu'un navigateur lit `//evil.com`, un autre site.
    for (const hostile of ["/\\evil.com/", "/\\\\evil.com/", "//evil.com/", "/ evil/", "/a\\b/", "/@evil.com/", "/%0d%0a/"]) {
      expect(motif.test(hostile), hostile).toBe(false);
    }
  });

  it("l'API et les fichiers de l'application passent avant toute expression", () => {
    expect(nginx).toMatch(/location \^~ \/api\/ \{/);
    expect(nginx).toMatch(/location \^~ \/assets\/ \{/);
  });

  it("l'ancien nom `app2.` renvoie ses pages publiques, jamais un écran de l'application", () => {
    // Le nom demandé, privé de son préfixe : aucun domaine n'est écrit.
    const regle = /map \$host \$domaine_nu \{\s*default "";\s*"~([^"]+)" \$reste;\s*\}/.exec(sansCommentaires);
    expect(regle, "la règle de l'ancien nom est introuvable").not.toBeNull();
    const motif = new RegExp((regle as RegExpExecArray)[1]);
    expect(motif.exec("app2.exemple.fr")?.groups?.reste).toBe("exemple.fr");
    for (const autre of ["exemple.fr", "www.exemple.fr", "api2.exemple.fr", "monapp2.exemple.fr"]) {
      expect(motif.test(autre), autre).toBe(false);
    }
    expect(sansCommentaires).not.toMatch(/evkha\.fr/);

    const blocs = Array.from(nginx.matchAll(/location ([^{]+) \{([^}]*)\}/g), ([, nom, corps]) => ({
      nom: nom.trim(),
      corps,
    }));
    const avecRenvoi = blocs.filter(({ corps }) => corps.includes(MARQUE_DU_RENVOI)).map(({ nom }) => nom);
    // Les pages publiques : le bloc général, les fiches, l'accueil.
    expect(avecRenvoi).toEqual(["/", "~ ^/boutique/(?<etude>[-a-zA-Z0-9_]+)$", "= /"]);
    // Le renvoi est la PREMIÈRE directive de chacun : rien n'est servi avant.
    for (const { corps } of blocs.filter((bloc) => avecRenvoi.includes(bloc.nom))) {
      expect(corps.trim().startsWith(MARQUE_DU_RENVOI)).toBe(true);
    }
    // Ni l'API, ni un écran de l'application, ni un retour de paiement : une
    // session y est ouverte sous l'ancien nom.
    expect(blocs.length).toBeGreaterThan(15);
    for (const { nom, corps } of blocs) {
      if (/api|admin|espace|retour|assets/.test(nom)) expect(corps, nom).not.toContain(MARQUE_DU_RENVOI);
    }
  });

  it("(d) le plan des fiches est servi par Django, et robots.txt le déclare", () => {
    expect(decider("/sitemap-boutique.xml")).toEqual({ quoi: "plan-boutique" });
    expect(lire("scripts/prerendre.mjs")).toContain("`Sitemap: ${ORIGINE_DU_SITE}/sitemap-boutique.xml`");
  });

  it("une panne de Django ne ferme pas la boutique : la coquille prend le relais", () => {
    const fiche = expressions.find(({ motif }) => motif.test("/boutique/une-etude"));
    expect(fiche?.corps).toMatch(/proxy_intercept_errors on;/);
    expect(fiche?.corps).toMatch(/error_page 500 502 503 504 =200 \/index\.html;/);
    // Une étude absente (404 sans corps de Django) : la coquille, avec le code.
    expect(fiche?.corps).toMatch(/error_page 404 \/index\.html;/);
    expect(fiche?.corps).toMatch(/proxy_read_timeout \d+s;/);
    expect(fiche?.corps).toMatch(/rewrite \^ \/api\/public\/boutique\/\$etude\/page\/ break;/);
  });
});

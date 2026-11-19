/**
 * Coller un jeton d'administration menait sur la page publique du site.
 *
 * Constaté par la cliente le 07/08/2026 : « pour l'espace admin, quand je mets
 * le token, ça m'amène sur la page publique du site ».
 *
 * La page de connexion redirigeait vers `/`. C'était juste au temps où `/`
 * servait le tableau de bord ; depuis que la racine rend `Partenaires` — une
 * page publique, la seule route de l'application sans garde —, l'administrateur
 * atterrissait sur le site vitrine. Rien n'échouait : le jeton était bien
 * enregistré, on n'arrivait simplement jamais à destination. Un défaut
 * silencieux, invisible à toute pile d'erreurs.
 *
 * Deux vérités s'étaient séparées : « où vit le tableau de bord » (le routeur,
 * qui dit `/admin`) et « où l'on va après connexion » (la page de connexion,
 * qui disait `/`). Ce test les rattache l'une à l'autre.
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { APRES_CONNEXION } from "../pages/Login";

const lire = (chemin: string) =>
  readFileSync(join(__dirname, "..", chemin), "utf8");

describe("atterrissage après connexion administrateur", () => {
  it("mène au tableau de bord, pas à la racine publique", () => {
    // Sur le code d'avant, cette constante n'existait pas et la page de
    // connexion écrivait `window.location.href = "/"` en dur.
    expect(APRES_CONNEXION).toBe("/admin");
  });

  it("vise une route que le routeur sert vraiment", () => {
    const routeur = lire("router.tsx");
    expect(routeur).toContain(`path: "${APRES_CONNEXION}"`);
  });

  it("ne vise pas la racine, qui est publique", () => {
    // La racine rend une page PUBLIQUE, sans garde d'accès : c'est le site
    // vitrine. Y envoyer un administrateur authentifié est précisément le
    // défaut corrigé. Cette page était `Partenaires` ; c'est `Accueil` depuis
    // le 19/11/2026 — publique elle aussi, donc le verrou tient pour la même
    // raison, et il n'attend plus un composant que la racine ne rend plus.
    const routeur = lire("router.tsx");
    //
    // On lit le BLOC ENTIER de `racine`, et non la ligne qui suit `path` :
    // une garde posée avant `path` ou après `component` échappait à
    // l'assertion d'avant, qui ne verrouillait donc rien.
    const bloc = routeur.match(/const racine = createRoute\(\{([\s\S]*?)\}\);/)?.[1];
    expect(bloc, "bloc `const racine = createRoute({…})` introuvable").toBeDefined();
    expect(bloc).toMatch(/path:\s*"\/"/);
    expect(bloc).toMatch(/component:\s*Accueil\b/);
    expect(bloc).not.toMatch(/beforeLoad/);
    expect(APRES_CONNEXION).not.toBe("/");
  });

  it("contre-épreuve : une garde posée n'importe où dans le bloc de la racine est vue", () => {
    const garde = `const racine = createRoute({
  beforeLoad: requireAuth,
  getParentRoute: () => rootRoute,
  path: "/",
  component: Accueil,
});`;
    const bloc = garde.match(/const racine = createRoute\(\{([\s\S]*?)\}\);/)?.[1];
    expect(bloc).toMatch(/beforeLoad/);
  });

  it("la page de connexion n'écrit plus de destination en dur", () => {
    const connexion = lire("pages/Login.tsx");
    expect(connexion).not.toContain('window.location.href = "/"');
    expect(connexion).toContain("window.location.href = APRES_CONNEXION");
  });
});

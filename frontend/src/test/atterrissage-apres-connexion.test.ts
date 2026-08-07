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
    // La racine rend `Partenaires`, sans garde d'accès : c'est le site vitrine.
    // Y envoyer un administrateur authentifié est précisément le défaut corrigé.
    const routeur = lire("router.tsx");
    expect(routeur).toMatch(/path:\s*"\/",\s*\n\s*component:\s*Partenaires/);
    expect(APRES_CONNEXION).not.toBe("/");
  });

  it("la page de connexion n'écrit plus de destination en dur", () => {
    const connexion = lire("pages/Login.tsx");
    expect(connexion).not.toContain('window.location.href = "/"');
    expect(connexion).toContain("window.location.href = APRES_CONNEXION");
  });
});

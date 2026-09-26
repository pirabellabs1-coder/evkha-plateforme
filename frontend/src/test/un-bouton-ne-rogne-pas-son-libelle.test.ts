import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// Vu le 26/09/2026 à 375 px sur l'écran de suivi : « Tous mes livrables »
// rendu « ous mes livrable ». La charte verre avait posé `overflow: hidden`
// sur TOUS les `.bouton` (pour le balayage de chargement) ; dans un conteneur
// flex, cela ramène `min-width: auto` à 0 et le bouton se laisse comprimer
// sous son texte, que l'`overflow` coupe ensuite des deux côtés. Le rognage
// ne sert qu'au balayage : il vit sur `.bouton-chargement`, et l'en-tête de
// carte passe à la ligne plutôt que d'écraser son action.
//
// jsdom ne calcule aucune mise en page : on verrouille donc les déclarations
// elles-mêmes, comme `vocabulaire-espace-client` verrouille des mots.
const FEUILLE = join(process.cwd(), "src", "theme", "espace.css");

/** Corps de la PREMIÈRE règle dont le sélecteur est exactement `selecteur`,
 *  commentaires retirés. */
function bloc(css: string, selecteur: string): string {
  const debut = css.indexOf(`\n${selecteur} {`);
  if (debut < 0) throw new Error(`règle introuvable : ${selecteur}`);
  const fin = css.indexOf("}", debut);
  return css.slice(debut, fin).replace(/\/\*[\s\S]*?\*\//g, "");
}

describe("un bouton ne rogne pas son libellé", () => {
  const css = readFileSync(FEUILLE, "utf-8").replace(/\r\n/g, "\n");

  it("le bouton de base ne coupe pas son débordement", () => {
    expect(bloc(css, ".bouton")).not.toMatch(/overflow:\s*hidden/);
  });

  it("le balayage de chargement est rogné par son propre bouton", () => {
    expect(bloc(css, ".bouton-chargement")).toMatch(/overflow:\s*hidden/);
  });

  it("l'en-tête de carte passe à la ligne plutôt que d'écraser son action", () => {
    expect(bloc(css, ".carte-entete")).toMatch(/flex-wrap:\s*wrap/);
  });

  it("le balayage de chargement s'arrête quand le mouvement est réduit", () => {
    // La durée passe par `--duree-balayage`, à 0 ms sous mouvement réduit
    // (`les-mouvements-lisent-leurs-durees`) ; la règle nommée dans un bloc
    // `prefers-reduced-motion` reste le filet, et ce test la garde.
    const blocs = css.match(
      /@media \(prefers-reduced-motion: reduce\) \{[\s\S]*?\n\}/g,
    );
    expect(blocs).not.toBeNull();
    const couvert = (blocs ?? []).some(
      (b) => /\.bouton-chargement::after\s*\{[^}]*animation:\s*none/.test(b),
    );
    expect(couvert).toBe(true);
  });
});

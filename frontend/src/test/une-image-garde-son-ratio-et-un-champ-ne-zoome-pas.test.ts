/** Deux défauts que jsdom ne voit pas, verrouillés sur les déclarations.
 *
 * 1. **Une image dimensionnée en attributs garde son ratio.** La refonte
 *    « verre » a posé `width`/`height` sur les photos de Partenaires pour
 *    réserver leur place. Mais l'attribut `height="800"` devient une
 *    déclaration `height: 800px` si aucune règle CSS ne dit `height` ; le
 *    `aspect-ratio` est alors ignoré et la photo montait à 800 px (1 200 pour
 *    le portrait) sur téléphone — mesuré le 26/09/2026, 345 × 800. Toute
 *    `<img>` publique qui porte `height=` doit donc avoir une classe, et
 *    cette classe une règle qui déclare `height`.
 *
 * 2. **Un champ de saisie public ne descend pas sous 16 px.** En dessous,
 *    Safari iOS zoome la page au focus et ne la dézoome pas. Les champs de
 *    connexion et d'inscription étaient à 0,85 rem (13,6 px) depuis avant la
 *    refonte ; ceux du tunnel d'achat sont passés à 15 px avec elle.
 *
 * jsdom ne calcule aucune mise en page : on lit les sources, comme
 * `un-bouton-ne-rogne-pas-son-libelle`.
 */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const PUBLIC = join(process.cwd(), "src", "public");
const THEME = join(process.cwd(), "src", "theme");

interface Regle {
  feuille: string;
  selecteur: string;
  corps: string;
}

function lire(chemin: string): string {
  return readFileSync(chemin, "utf-8").replace(/\r\n/g, "\n");
}

function sansCommentaires(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, "");
}

/** Toutes les règles `sélecteur { corps }` des feuilles publiques et de
 *  `espace.css`, @media compris (on ne garde que le bloc le plus intérieur). */
function regles(): Regle[] {
  const feuilles = [
    ...readdirSync(PUBLIC)
      .filter((f) => f.endsWith(".css"))
      .map((f) => join(PUBLIC, f)),
    join(THEME, "espace.css"),
  ];
  const sortie: Regle[] = [];
  for (const feuille of feuilles) {
    const css = sansCommentaires(lire(feuille));
    for (const m of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
      sortie.push({ feuille, selecteur: m[1].trim(), corps: m[2] });
    }
  }
  return sortie;
}

const REGLES = regles();

/** Une règle vise-t-elle cette classe (en tant que classe entière) ? */
function viseClasse(selecteur: string, classe: string): boolean {
  return new RegExp(`\\.${classe}(?![\\w-])`).test(selecteur);
}

/** `height` déclarée, et non `min-height`, `max-height`, `line-height`. */
const DECLARE_HAUTEUR = /(?<![\w-])height\s*:/;

/** Les balises `<img …>` des pages publiques, multi-lignes comprises. */
function images(): { page: string; balise: string }[] {
  const sortie: { page: string; balise: string }[] = [];
  for (const page of readdirSync(PUBLIC).filter((f) => f.endsWith(".tsx"))) {
    for (const m of lire(join(PUBLIC, page)).matchAll(/<img\b[\s\S]*?\/>/g)) {
      sortie.push({ page, balise: m[0] });
    }
  }
  return sortie;
}

/** Taille en px d'une valeur `font-size`, ou `null` si on ne sait pas lire.
 *  `max(1rem, …)` vaut au moins son premier terme. */
function enPixels(valeur: string): number | null {
  const v = valeur.trim();
  const plancher = v.match(/^max\(\s*([\d.]+)(rem|px)/);
  const simple = v.match(/^([\d.]+)(rem|px)$/);
  const m = plancher ?? simple;
  if (!m) return null;
  return m[2] === "rem" ? parseFloat(m[1]) * 16 : parseFloat(m[1]);
}

function tailleDe(regle: Regle | undefined): string {
  return regle?.corps.match(/font-size\s*:\s*([^;]+)/)?.[1]?.trim() ?? "";
}

describe("une image garde son ratio", () => {
  const avecHauteur = images().filter((i) => /\sheight=/.test(i.balise));

  // Règle 1 : un contrôle qui n'a rien à comparer n'est pas un succès.
  it("trouve des images dimensionnées en attributs", () => {
    expect(avecHauteur.length).toBeGreaterThan(0);
  });

  for (const { page, balise } of avecHauteur) {
    const classe = balise.match(/className="([^"]+)"/)?.[1] ?? "";
    it(`${page} : <img class="${classe}"> déclare sa hauteur en CSS`, () => {
      expect(classe, `${page} : une <img height=…> sans classe`).not.toBe("");
      const couverte = classe
        .split(/\s+/)
        .some((c) =>
          REGLES.some(
            (r) => viseClasse(r.selecteur, c) && DECLARE_HAUTEUR.test(r.corps),
          ),
        );
      expect(couverte, `${page} : .${classe} ne déclare pas height`).toBe(true);
    });
  }
});

describe("un champ public ne fait pas zoomer iOS", () => {
  it("aucune règle des feuilles publiques ne met un champ sous 16 px", () => {
    const champs = REGLES.filter(
      (r) =>
        r.feuille.startsWith(PUBLIC) &&
        /\b(input|textarea|select)\b|champ-saisie/.test(r.selecteur) &&
        /font-size\s*:/.test(r.corps),
    );
    expect(champs.length).toBeGreaterThan(0);
    for (const r of champs) {
      const valeur = tailleDe(r);
      const px = enPixels(valeur);
      expect(px, `${r.selecteur} : font-size ${valeur}`).not.toBeNull();
      expect(px as number, `${r.selecteur} : font-size ${valeur}`).toBeGreaterThanOrEqual(
        16,
      );
    }
  });

  it("les champs .champ-saisie des pages publiques sont relevés à 16 px", () => {
    const releve = REGLES.find((r) => r.selecteur === ".pp .champ-saisie");
    expect(releve, "règle .pp .champ-saisie absente").toBeDefined();
    expect(enPixels(tailleDe(releve)) ?? 0).toBeGreaterThanOrEqual(16);
  });

  it("contre-épreuve : la lecture des tailles distingue 13,6 px de 16 px", () => {
    expect(enPixels("0.85rem")).toBeCloseTo(13.6);
    expect(enPixels("max(1rem, var(--t-base))")).toBe(16);
    expect(enPixels("16px")).toBe(16);
    expect(enPixels("var(--t-base)")).toBeNull();
  });
});

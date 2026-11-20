/** « Ils me font confiance » : une référence sans logo s'affiche par son nom.
 *
 * La gérante a ajouté deux structures le 20/11/2026 — Orichi formation et
 * Althea Provence — sans en fournir le logo. Un logo ne se fabrique pas et ne
 * se prend pas sur le site d'un tiers : la bande les NOMME, en texte, à côté
 * des quatre logos. Ce fichier verrouille :
 *
 * (a) les deux références sont dans la liste, sans image, après les quatre
 *     logos ; aucun fichier de logo n'a été ajouté pour elles ;
 * (b) la bande les affiche par leur nom, en texte, et ne rend pour elles
 *     aucune `<img>` — ni vide, ni cassée ;
 * (c) la bande reste juste pour un lecteur d'écran : chaque référence est
 *     lue UNE fois (logo par son `alt`, nom par son texte), les deux copies
 *     qui font défiler la bande sont `aria-hidden`, et rien n'y prend le
 *     focus ;
 * (d) un logo existant garde son image, à ses dimensions, et son fichier
 *     existe.
 *
 * Contre-épreuve (règle 6) : rendue sur le code d'avant — `src={logo.image}`
 * sans condition —, une référence sans image produisait une `<img>` sans
 * `src` ; (b) le voit.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`.
 */
import React from "react";
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { cleanup, render, screen, within } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { Accueil } from "../public/Accueil";
import { CONFIANCE } from "../public/contenuAccueil";
import { server } from "./server";

const PUBLIC = join(process.cwd(), "public");

/** Une référence d'essai, SANS logo. Les six références du site ont le leur
 *  depuis que le client a fourni ceux d'Orichi et d'Althea (20/11/2026) : la
 *  règle « sans image, le nom » n'aurait plus rien à juger sans elle. Elle
 *  est ajoutée à la liste le temps de chaque test, puis retirée. */
const SANS_LOGO = ["Référence d'essai sans logo"];
const AVEC_LOGO = [
  "LegalPlace",
  "Réseau Initiative France",
  "Swapn",
  "Yyyours",
  "Orichi formation",
  "Althea Provence",
];

/** Les catalogues ne répondent pas : ce test ne juge pas les prix. */
beforeEach(() => {
  server.use(
    http.get(`${window.location.origin}/api/*`, async () => {
      await delay("infinite");
      return new HttpResponse(null);
    }),
  );
});

beforeEach(() => {
  CONFIANCE.logos.push({ nom: SANS_LOGO[0] });
});

afterEach(() => {
  cleanup();
  CONFIANCE.logos.pop();
});

function bande(): HTMLElement {
  return screen.getByRole("region", { name: CONFIANCE.titre });
}

function cases(): HTMLLIElement[] {
  return Array.from(bande().querySelectorAll("li"));
}

describe("ils me font confiance", () => {
  it("(a) six références du site, toutes avec leur logo, et leur fichier", () => {
    expect(CONFIANCE.logos.map((logo) => logo.nom)).toEqual([...AVEC_LOGO, ...SANS_LOGO]);
    for (const logo of CONFIANCE.logos) {
      expect(logo.image === undefined, logo.nom).toBe(SANS_LOGO.includes(logo.nom));
    }
    const fichiers = readdirSync(join(PUBLIC, "accueil")).join(" ").toLowerCase();
    for (const fichier of ["logo-legalplace", "logo-orichi", "logo-althea-provence"]) {
      expect(fichiers).toContain(fichier);
    }
  });

  it("(b) une référence sans logo s'affiche par son nom, en texte, sans image", () => {
    render(<Accueil />);

    const premiere = cases().slice(0, CONFIANCE.logos.length);
    expect(premiere).toHaveLength(7);
    for (const nom of SANS_LOGO) {
      const laCase = premiere.find((li) => li.textContent === nom);
      expect(laCase, nom).toBeDefined();
      expect(laCase?.querySelector(".acc-confiance-nom"), nom).toHaveTextContent(nom);
      expect(laCase?.querySelector("img"), nom).toBeNull();
      // Lue : la première copie n'est pas masquée.
      expect(laCase).not.toHaveAttribute("aria-hidden");
    }
    // Aucune image sans adresse, nulle part dans la bande.
    for (const image of Array.from(bande().querySelectorAll("img"))) {
      expect(image.getAttribute("src") ?? "", image.outerHTML).toMatch(/^\/accueil\/logo-.+\.webp$/);
    }
  });

  it("(c) chaque référence est lue une fois ; les copies se taisent et ne prennent pas le focus", () => {
    render(<Accueil />);

    const toutes = cases();
    // Trois copies bout à bout : la bande reste pleine sur un grand écran.
    expect(toutes).toHaveLength(3 * CONFIANCE.logos.length);
    const lues = toutes.filter((li) => li.getAttribute("aria-hidden") !== "true");
    const copies = toutes.filter((li) => li.getAttribute("aria-hidden") === "true");
    expect(lues).toHaveLength(CONFIANCE.logos.length);
    expect(copies).toHaveLength(2 * CONFIANCE.logos.length);

    // Ce qu'un lecteur d'écran entend : chaque nom, dans l'ordre, une fois.
    const entendus = lues.map((li) => li.querySelector("img")?.getAttribute("alt") ?? li.textContent);
    expect(entendus).toEqual([...AVEC_LOGO, ...SANS_LOGO]);
    // Les logos lus sont exposés comme des images nommées.
    expect(within(bande()).getAllByRole("img").map((image) => image.getAttribute("alt"))).toEqual(AVEC_LOGO);

    for (const copie of copies) {
      // Une image de copie est décorative ; un nom de copie est sous
      // `aria-hidden` — et rien de focalisable n'y vit.
      for (const image of Array.from(copie.querySelectorAll("img"))) {
        expect(image).toHaveAttribute("alt", "");
      }
      expect(copie.querySelector("a, button, [tabindex]")).toBeNull();
    }
    // La bande ne porte aucun lien : une cible qui défile ne se vise pas.
    expect(bande().querySelector("a")).toBeNull();
  });

  it("(d) un logo garde son image, à ses dimensions, et son fichier existe", () => {
    render(<Accueil />);

    for (const logo of CONFIANCE.logos) {
      if (!logo.image) continue;
      const image = within(bande()).getByAltText(logo.nom);
      expect(image).toHaveAttribute("src", logo.image.src);
      expect(image).toHaveAttribute("width", String(logo.image.largeur));
      expect(image).toHaveAttribute("height", String(logo.image.hauteur));
      expect(existsSync(join(PUBLIC, ...logo.image.src.split("/").filter(Boolean))), logo.image.src).toBe(true);
    }
    // Règle 1 : la boucle a bien eu six logos à juger.
    expect(CONFIANCE.logos.filter((logo) => logo.image)).toHaveLength(6);
  });
});

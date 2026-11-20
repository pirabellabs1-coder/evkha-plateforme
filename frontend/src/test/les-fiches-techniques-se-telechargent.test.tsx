/** Les fiches techniques des formations se téléchargent — même quand la
 * formation n'est pas en ligne.
 *
 * La gérante a transmis le 20/11/2026 un PDF par formation, « à télécharger
 * sous chaque formation ». Ce fichier verrouille :
 *
 * (a) chaque formation a SA fiche, et le fichier EXISTE dans `public/` — un
 *     lien vers un fichier absent répondrait 404, ou pire : la coquille du
 *     site, que le navigateur enregistrerait sous un nom en `.pdf` ;
 * (b) le poids annoncé est celui du fichier : remplacer un PDF sans relever
 *     son poids fait mentir le bouton ;
 * (c) chaque page de formation porte le bouton, avec `download`, le format et
 *     le poids — formation en ligne, HORS LIGNE (« Indisponible pour le
 *     moment », l'état des trois aujourd'hui), en attente ou en panne ;
 * (d) le catalogue porte un lien par carte, vers la fiche de SA formation, et
 *     leurs noms accessibles se distinguent ;
 * (e) l'adresse du fichier n'est écrite qu'une fois, dans le contenu.
 *
 * Contre-épreuves (règle 6) : un fichier qui n'existe pas est vu absent ; un
 * poids faux est vu faux ; le bouton d'INSCRIPTION, lui, reste neutralisé
 * hors ligne — ce test ne passe pas parce que tout serait devenu actif.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`.
 */
import React from "react";
import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import {
  ARTICULATION,
  FICHES_TECHNIQUES,
  PAGE_CATALOGUE,
  ROUTES_FORMATIONS,
  SLUGS_DES_FORMATIONS,
  type CleDeFormation,
} from "../public/contenuFormations";
import {
  FormationMicro,
  FormationPop,
  FormationSocietes,
  Formations,
} from "../public/Formations";
import { server } from "./server";

const PUBLIC = join(process.cwd(), "public");
const FORMATIONS_API = `${window.location.origin}/api/public/formations/`;

const CLES: CleDeFormation[] = ["societes", "micro", "pop"];

/** Les trois adresses, écrites ICI en toutes lettres : le test ne demande pas
 *  au contenu ce qu'il doit y trouver. */
const ATTENDUES: Record<CleDeFormation, string> = {
  societes: "/fiches-techniques/creer-son-entreprise.pdf",
  micro: "/fiches-techniques/creer-sa-micro-entreprise.pdf",
  pop: "/fiches-techniques/methode-pop.pdf",
};

const PAGES: Record<CleDeFormation, () => React.JSX.Element> = {
  societes: FormationSocietes,
  micro: FormationMicro,
  pop: FormationPop,
};

type Reponse = () => Response | Promise<Response>;

/** Les quatre états d'une formation, vus du serveur. */
const ETATS: [string, Reponse, string][] = [
  // L'état des trois formations aujourd'hui : aucune n'est publiée.
  ["hors ligne", () => HttpResponse.json({ formations: [] }), "Indisponible pour le moment"],
  [
    "en attente",
    async () => {
      await delay("infinite");
      return new HttpResponse(null);
    },
    "Tarif en cours de chargement",
  ],
  ["en panne", () => new HttpResponse("panne", { status: 500 }), "Tarif momentanément indisponible"],
];

/** Le fichier d'une adresse du site, dans `public/`. */
function fichierDe(adresse: string): string {
  return join(PUBLIC, ...adresse.split("/").filter(Boolean));
}

/** Le poids d'un fichier, comme le contenu l'écrit : au kilo-octet (1 000
 *  octets), arrondi. Calculé ICI, pas demandé au contenu. */
function poidsDe(adresse: string): string {
  return `${Math.round(statSync(fichierDe(adresse)).size / 1000)} Ko`;
}

function espaces(brut: string): string {
  return brut.replace(new RegExp(String.fromCharCode(0xa0), "g"), " ");
}

function boutonsDeFiche(): HTMLAnchorElement[] {
  return Array.from(screen.getByRole("main").querySelectorAll<HTMLAnchorElement>("a[download]"));
}

function afficher(cle: CleDeFormation, reponse: Reponse) {
  server.use(http.get(FORMATIONS_API, reponse));
  window.history.pushState({}, "", ROUTES_FORMATIONS[cle]);
  const Page = PAGES[cle];
  return render(<Page />);
}

afterEach(() => {
  cleanup();
  window.history.pushState({}, "", "/");
});

describe("les fiches techniques des formations", () => {
  it("(a) chaque formation a sa fiche, et le fichier existe : un vrai PDF", () => {
    expect(Object.keys(FICHES_TECHNIQUES).sort()).toEqual([...CLES].sort());
    for (const cle of CLES) {
      const { fichier } = FICHES_TECHNIQUES[cle];
      expect(fichier, cle).toBe(ATTENDUES[cle]);
      // Le nom du fichier est celui de la page de sa formation.
      expect(fichier, cle).toBe(`/fiches-techniques/${SLUGS_DES_FORMATIONS[cle]}.pdf`);
      expect(existsSync(fichierDe(fichier)), `${fichier} est absent de public/`).toBe(true);
      // Un PDF, pas un fichier vide ni une page HTML renommée.
      const octets = readFileSync(fichierDe(fichier));
      expect(octets.subarray(0, 5).toString("latin1"), fichier).toBe("%PDF-");
      expect(octets.length, fichier).toBeGreaterThan(10_000);
    }
    // Trois fichiers DIFFÉRENTS.
    expect(new Set(CLES.map((cle) => FICHES_TECHNIQUES[cle].fichier)).size).toBe(3);
  });

  it("(b) le poids annoncé est celui du fichier", () => {
    for (const cle of CLES) {
      const { fichier, poids } = FICHES_TECHNIQUES[cle];
      expect(poids, fichier).toBe(poidsDe(fichier));
    }
  });

  for (const cle of CLES) {
    for (const [etat, reponse, phrase] of ETATS) {
      it(`(c) ${cle}, ${etat} : le bouton de la fiche est là, et il télécharge`, async () => {
        afficher(cle, reponse);
        await waitFor(() => expect(screen.getByRole("main").textContent).toContain(phrase));

        const boutons = boutonsDeFiche();
        // Sous le prix de l'ouverture, et dans « En pratique ».
        expect(boutons).toHaveLength(2);
        for (const bouton of boutons) {
          expect(bouton).toHaveAttribute("href", ATTENDUES[cle]);
          expect(bouton).toHaveAttribute("download");
          expect(bouton).toHaveAttribute("type", "application/pdf");
          // Un vrai lien, au clavier comme à la souris — pas une pièce
          // neutralisée.
          expect(bouton).not.toHaveAttribute("aria-disabled");
          expect(bouton).not.toHaveAttribute("tabindex");
          expect(espaces(bouton.textContent ?? "")).toContain(
            `${ARTICULATION.ficheTechnique.telecharger} (PDF, ${poidsDe(ATTENDUES[cle])})`,
          );
          // La flèche est décorative : le nom du lien n'en dépend pas.
          expect(bouton.querySelector(".acc-btn-fleche")).toHaveAttribute("aria-hidden", "true");
        }
        expect(ARTICULATION.ficheTechnique.telecharger).toBe("Télécharger la fiche technique");
        // Le premier est dans l'ouverture, avec le prix.
        expect(boutons[0].closest(".for-ouverture")).not.toBeNull();
        expect(boutons[1].closest("#modalites")).not.toBeNull();
      });
    }
  }

  it("contre-épreuve : hors ligne, l'INSCRIPTION reste neutralisée — la fiche seule est active", async () => {
    afficher("societes", ETATS[0][1]);
    await waitFor(() => expect(screen.getByRole("main").textContent).toContain(ETATS[0][2]));

    expect(document.querySelectorAll("button.for-bouton-achat")).toHaveLength(0);
    expect(document.querySelectorAll(".for-bouton-achat.acc-btn-inactif")).toHaveLength(3);
    expect(boutonsDeFiche()).toHaveLength(2);
  });

  it("(c) en ligne aussi : la fiche reste à côté du bouton d'inscription", async () => {
    afficher("pop", () =>
      HttpResponse.json({
        formations: [
          {
            slug: SLUGS_DES_FORMATIONS.pop,
            titre: "Méthode",
            sous_titre: "",
            accroche: "",
            prix_cents: 91300,
            devise: "EUR",
            duree_heures: 11,
            heures_de_coaching: 0,
            nombre_de_modules: 0,
            modules: [],
          },
        ],
      }),
    );
    await waitFor(() => expect(document.querySelectorAll("button.for-bouton-achat")).toHaveLength(3));
    expect(boutonsDeFiche().map((bouton) => bouton.getAttribute("href"))).toEqual([
      ATTENDUES.pop,
      ATTENDUES.pop,
    ]);
  });

  it("(d) le catalogue : un lien par carte, vers la fiche de SA formation", async () => {
    server.use(http.get(FORMATIONS_API, ETATS[0][1]));
    window.history.pushState({}, "", ROUTES_FORMATIONS.catalogue);
    render(<Formations />);
    await waitFor(() => expect(screen.getByRole("main").textContent).toContain(ETATS[0][2]));

    const liens = boutonsDeFiche();
    expect(liens).toHaveLength(3);
    const cartes = PAGE_CATALOGUE.formations.cartes;
    expect(cartes.map((carte) => carte.cle)).toEqual(CLES);
    cartes.forEach((carte, k) => {
      const article = document.getElementById(`formation-${carte.cle}`) as HTMLElement;
      const lien = within(article).getByRole("link", { name: /Fiche technique/ });
      expect(lien).toBe(liens[k]);
      expect(lien).toHaveAttribute("href", ATTENDUES[carte.cle]);
      expect(lien).toHaveAttribute("download");
      expect(lien).toHaveTextContent("Fiche technique (PDF)");
      // Trois liens au même texte : le nom accessible porte le titre de la
      // formation, et commence par le texte visible.
      expect(lien).toHaveAccessibleName(`Fiche technique (PDF) ${carte.titre}`);
      // La carte garde son bouton vers la page de la formation.
      expect(within(article).getByRole("link", { name: /Je découvre/ })).toHaveAttribute(
        "href",
        ROUTES_FORMATIONS[carte.cle],
      );
    });
  });

  it("(e) l'adresse d'une fiche n'est écrite que dans le contenu", () => {
    const page = readFileSync(join(process.cwd(), "src", "public", "Formations.tsx"), "utf-8");
    expect(page.length).toBeGreaterThan(5000);
    expect(page).toContain("FICHES_TECHNIQUES[cle]");
    expect(page).not.toMatch(/fiches-techniques\/|\.pdf\b/);
  });

  it("contre-épreuve : un fichier absent est vu absent, un poids faux est vu faux", () => {
    expect(existsSync(fichierDe("/fiches-techniques/fiche-qui-n-existe-pas.pdf"))).toBe(false);
    const { fichier, poids } = FICHES_TECHNIQUES.societes;
    const octets = statSync(fichierDe(fichier)).size;
    expect(`${Math.round((octets + 5000) / 1000)} Ko`).not.toBe(poids);
    expect(poidsDe(FICHES_TECHNIQUES.micro.fichier)).not.toBe(poids);
  });
});

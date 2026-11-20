/** Ce que chaque page publique déclare aux moteurs est VRAI, et c'est le sien.
 *
 * Mesuré le 20/11/2026 sur la production, sans exécuter de JavaScript : toutes
 * les adresses rendaient le même fichier, titre « EVKHA — Espace client ».
 * Et même une fois les scripts exécutés, une page ne posait que son titre et
 * sa description : aucune adresse canonique, un aperçu de partage figé sur
 * celui du gabarit, aucune donnée structurée hors formations et blog.
 *
 * Ce fichier monte le VRAI routeur (`creerRouteur`) à chaque adresse du plan
 * du site (`planDuSite.PAGES_DU_PLAN`) et verrouille, pour TOUTES — la liste
 * n'est pas recopiée ici (règle 4) :
 *
 * (a) un titre et une description, que nulle autre page ne porte ;
 * (b) une adresse canonique : l'adresse publique de la page, sans paramètre ;
 * (c) un aperçu de partage (Open Graph, Twitter) qui dit la même chose que le
 *     titre et la description — une page ne peut pas en annoncer deux ;
 * (d) les questions fréquentes déclarées sont celles que la page AFFICHE, mot
 *     pour mot et en même nombre (règle 3) ;
 * (e) le fil d'Ariane d'une page rangée sous une rubrique finit sur elle ;
 * (f) l'identité déclarée est celle des mentions légales, sans téléphone ni
 *     note inventés.
 *
 * Contre-épreuves (règle 6) : une page introuvable ne se dit ni canonique ni
 * rangée dans un fil ; une page sans questions ne déclare pas de FAQ ; tout
 * est rendu au démontage ; une page de premier niveau n'a pas de fil.
 *
 * Rejoué contre le code d'avant par mutation, le 20/11/2026 — retirer de
 * `site.useTitreDePage` la pose de l'adresse canonique fait rougir (b) ;
 * retirer `useQuestionsStructurees` d'une page fait rougir (d).
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`.
 */
import React from "react";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { PAGES_LEGALES } from "../public/contenuLegal";
import { CHEMINS, IDENTITE, ORIGINE_DU_SITE } from "../public/contenuSite";
import { PAGES_DU_PLAN } from "../public/planDuSite";
import { filDAriane, organisationEtSite, questionsFrequentes } from "../public/referencement";
import { BLOCS_DU_SOCLE } from "../public/site";
import { creerRouteur } from "../router";
import { server } from "./server";

// ── Outils ──────────────────────────────────────────────────────────────────

const ATTENTE = { timeout: 8000 };

/** Les catalogues ne répondent pas, comme pendant le pré-rendu : la page est
 *  jugée dans l'état où un robot la reçoit. */
function serveurMuet() {
  const muet = async () => {
    await delay("infinite");
    return new HttpResponse(null);
  };
  server.use(http.get(`${window.location.origin}/api/*`, muet));
}

async function ouvrir(adresse: string) {
  serveurMuet();
  window.history.pushState({}, "", adresse);
  const routeur = creerRouteur(createMemoryHistory({ initialEntries: [adresse] }));
  const rendu = render(<RouterProvider router={routeur} />);
  await screen.findByRole("heading", { level: 1 }, ATTENTE);
  return rendu;
}

function contenu(selecteur: string, attribut = "content"): string | null {
  return document.head.querySelector(selecteur)?.getAttribute(attribut) ?? null;
}

type Bloc = Record<string, unknown>;

/** Les blocs JSON-LD de l'en-tête et du corps, lus tels qu'un moteur les lit. */
function blocs(): Bloc[] {
  return Array.from(
    document.querySelectorAll('script[type="application/ld+json"]'),
    (balise) => JSON.parse(balise.textContent ?? "") as Bloc,
  );
}

function blocsDeType(type: string): Bloc[] {
  return blocs().filter((bloc) => bloc["@type"] === type);
}

const enLigne = (texte: string) => texte.replace(/\s+/g, " ").trim();

afterEach(() => cleanup());

// ── Chaque page du plan ─────────────────────────────────────────────────────

describe("chaque page du plan du site se déclare elle-même", () => {
  const vus = { titres: new Map<string, string>(), descriptions: new Map<string, string>() };

  for (const page of PAGES_DU_PLAN) {
    it(`${page.chemin} : titre, description, adresse canonique et aperçu de partage`, async () => {
      await ouvrir(page.chemin);
      const adresse = `${ORIGINE_DU_SITE}${page.chemin}`;

      await waitFor(() => expect(contenu('link[rel="canonical"]', "href")).toBe(adresse));
      const titre = document.title;
      const description = contenu('meta[name="description"]') ?? "";

      // (a) Les siens, et pas ceux d'une autre page.
      expect(titre).toMatch(/EVKHA/);
      expect(titre).not.toBe("EVKHA — Espace client");
      expect(description.length).toBeGreaterThan(40);
      expect(vus.titres.get(titre), `titre déjà porté par ${vus.titres.get(titre)}`).toBeUndefined();
      expect(
        vus.descriptions.get(description),
        `description déjà portée par ${vus.descriptions.get(description)}`,
      ).toBeUndefined();
      vus.titres.set(titre, page.chemin);
      vus.descriptions.set(description, page.chemin);

      // (b) Une seule adresse canonique.
      expect(document.head.querySelectorAll('link[rel="canonical"]')).toHaveLength(1);

      // (c) L'aperçu de partage dit la même chose.
      expect(contenu('meta[property="og:title"]')).toBe(titre);
      expect(contenu('meta[name="twitter:title"]')).toBe(titre);
      expect(contenu('meta[property="og:description"]')).toBe(description);
      expect(contenu('meta[name="twitter:description"]')).toBe(description);
      expect(contenu('meta[property="og:url"]')).toBe(adresse);

      // Une page du plan s'indexe.
      expect(document.head.querySelector('meta[name="robots"]')).toBeNull();

      // (d) Les questions déclarées sont celles affichées.
      const affichees = Array.from(document.querySelectorAll(".acc-faq details"), (bloc) =>
        enLigne(bloc.querySelector("summary")?.textContent ?? ""),
      );
      const faq = blocsDeType("FAQPage");
      if (affichees.length === 0) {
        // Contre-épreuve : pas de questions, pas de bloc.
        expect(faq).toHaveLength(0);
      } else {
        expect(faq).toHaveLength(1);
        const declarees = faq[0].mainEntity as { name: string; acceptedAnswer: { text: string } }[];
        expect(declarees.map((question) => question.name)).toEqual(affichees);
        for (const [k, question] of declarees.entries()) {
          const bloc = document.querySelectorAll(".acc-faq details")[k];
          expect(question.acceptedAnswer.text.length).toBeGreaterThan(10);
          // La réponse déclarée est dans le texte que le visiteur lit.
          expect(enLigne(bloc.textContent ?? "")).toContain(question.acceptedAnswer.text);
        }
      }

      // (e) Le fil d'Ariane : seulement sous une rubrique, et il finit ici.
      const fils = blocsDeType("BreadcrumbList");
      const profondeur = page.chemin.split("/").filter(Boolean).length;
      if (profondeur < 2) {
        expect(fils).toHaveLength(0);
      } else {
        expect(fils).toHaveLength(1);
        const maillons = fils[0].itemListElement as { position: number; item: string; name: string }[];
        expect(maillons.map((maillon) => maillon.position)).toEqual([1, 2, 3]);
        expect(maillons[0].item).toBe(`${ORIGINE_DU_SITE}/`);
        expect(maillons[2].item).toBe(adresse);
        expect(maillons[2].name).not.toMatch(/EVKHA\s*$/);
        // Le maillon du milieu est une page du plan.
        expect(PAGES_DU_PLAN.map((p) => `${ORIGINE_DU_SITE}${p.chemin}`)).toContain(maillons[1].item);
      }
    });
  }

  it("le plan porte au moins une page à questions et une page rangée sous une rubrique", () => {
    // Sans cela, les branches (d) et (e) ci-dessus pourraient ne jamais
    // s'exécuter, et le test passerait à vide (règle 1).
    expect(PAGES_DU_PLAN.some((page) => page.chemin === CHEMINS.packEssentiel)).toBe(true);
    expect(PAGES_DU_PLAN.some((page) => page.chemin === CHEMINS.etudes)).toBe(true);
  });

  it("la page des études affiche des questions, donc en déclare", async () => {
    await ouvrir(CHEMINS.etudes);
    await waitFor(() => expect(blocsDeType("FAQPage")).toHaveLength(1));
    expect(document.querySelectorAll(".acc-faq details").length).toBeGreaterThan(2);
    expect(blocsDeType("Service")).toHaveLength(1);
  });
});

// ── Ce qui est rendu en partant, et ce qui ne se déclare pas ────────────────

describe("une page rend ce qu'elle a posé, et une page introuvable ne se déclare pas", () => {
  it("au démontage : plus d'adresse canonique, plus de bloc du socle, le titre d'avant", async () => {
    const titreDAvant = document.title;
    const rendu = await ouvrir(CHEMINS.packEssentiel);
    await waitFor(() => expect(blocsDeType("BreadcrumbList")).toHaveLength(1));
    rendu.unmount();
    expect(document.head.querySelector('link[rel="canonical"]')).toBeNull();
    expect(document.head.querySelector('meta[property="og:url"]')).toBeNull();
    expect(document.head.querySelectorAll("script[data-bloc]")).toHaveLength(0);
    expect(document.title).toBe(titreDAvant);
  });

  for (const adresse of ["/une-adresse-qui-n-existe-pas", "/blog/un-article-qui-n-existe-pas"]) {
    it(`${adresse} : noindex, ni adresse canonique ni fil d'Ariane`, async () => {
      await ouvrir(adresse);
      await waitFor(() =>
        expect(contenu('meta[name="robots"]')).toBe("noindex"),
      );
      expect(document.head.querySelector('link[rel="canonical"]')).toBeNull();
      expect(document.head.querySelector('meta[property="og:url"]')).toBeNull();
      expect(blocsDeType("BreadcrumbList")).toHaveLength(0);
    });
  }

  it("les blocs du socle sont marqués, ceux des pages ne le sont pas", async () => {
    await ouvrir(CHEMINS.packEssentiel);
    await waitFor(() => expect(blocsDeType("FAQPage")).toHaveLength(1));
    const marques = Array.from(
      document.head.querySelectorAll<HTMLScriptElement>("script[data-bloc]"),
      (balise) => balise.dataset.bloc,
    );
    expect(marques.sort()).toEqual([BLOCS_DU_SOCLE.fil, BLOCS_DU_SOCLE.questions].sort());
  });
});

// ── Les constructeurs ───────────────────────────────────────────────────────

describe("les blocs se construisent sans rien inventer", () => {
  it("le fil d'Ariane : rien pour une page de premier niveau ou un parent inconnu", () => {
    expect(filDAriane("/", "Accueil")).toBeNull();
    expect(filDAriane("/etudes", "Études")).toBeNull();
    expect(filDAriane("/inconnu/page", "Page")).toBeNull();
    expect(filDAriane("/packs/essentiel", "")).toBeNull();
    expect(filDAriane("/packs/essentiel", "Pack")).not.toBeNull();
  });

  it("les questions : aucun bloc sans question, et une question sans réponse est écartée", () => {
    expect(questionsFrequentes([])).toBeNull();
    expect(questionsFrequentes([{ question: "Q ?", reponse: "" }])).toBeNull();
    const bloc = JSON.parse(
      questionsFrequentes([
        { question: "Q ?", reponse: "R." },
        { question: "", reponse: "R." },
      ]) ?? "",
    ) as { mainEntity: unknown[] };
    expect(bloc.mainEntity).toHaveLength(1);
  });

  it("l'accueil déclare l'entreprise : le siège des mentions légales, ni téléphone ni note", async () => {
    // (f) Le siège écrit dans `IDENTITE` est celui que les mentions légales
    // publient : le bloc ne peut pas en annoncer un autre.
    const mentions = JSON.stringify(PAGES_LEGALES).toLowerCase();
    expect(mentions).toContain(IDENTITE.siege.rue.toLowerCase());
    expect(mentions).toContain(`${IDENTITE.siege.codePostal} ${IDENTITE.siege.ville}`.toLowerCase());

    await ouvrir(CHEMINS.accueil);
    const graphe = blocs().find((bloc) => "@graph" in bloc);
    expect(graphe).toBeDefined();
    const [entreprise, site] = graphe!["@graph"] as Bloc[];
    expect(entreprise["@type"]).toBe("ProfessionalService");
    expect(entreprise.url).toBe(`${ORIGINE_DU_SITE}/`);
    expect((entreprise.address as Bloc).streetAddress).toBe(IDENTITE.siege.rue);
    expect(site["@type"]).toBe("WebSite");

    // Rien de ce que le site ne publie pas.
    const brut = organisationEtSite("Une description.");
    for (const invente of ["telephone", "aggregateRating", "review", "openingHours", "priceRange"]) {
      expect(brut, invente).not.toContain(invente);
    }
    // Aucun montant : les prix sont lus au serveur.
    expect(brut).not.toMatch(/\d\s*(?:€|euros?\b)/i);
  });

  it("l'entreprise n'est déclarée que sur l'accueil", async () => {
    await ouvrir(CHEMINS.etudes);
    expect(blocs().some((bloc) => "@graph" in bloc)).toBe(false);
  });
});

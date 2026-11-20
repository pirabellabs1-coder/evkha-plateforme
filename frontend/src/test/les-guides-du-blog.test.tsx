/** Les guides du blog (`contenuGuides.ts`) : chacun a sa page, et aucun ne dit
 * ce que le site ne peut pas tenir.
 *
 * Trois guides ont été écrits pour la plateforme le 20/11/2026, pour répondre
 * directement aux questions des porteurs de projet. Ce ne sont pas des textes
 * relevés sur le site de la cliente : ils doivent rester prudents tant qu'elle
 * ne les a pas relus. Ce fichier verrouille, pour CHAQUE guide de la liste —
 * elle n'est pas recopiée ici (règle 4) :
 *
 * (a) le guide est publié par la liste du blog, après l'article de la
 *     cliente, qui reste à la une ;
 * (b) sa page se rend à son adresse, avec un seul `h1`, son sommaire, ses
 *     données structurées `Article`, et sans date de publication inventée ;
 * (c) il ne cite AUCUN montant et aucun des points non confirmés par la
 *     cliente (financement, CPF, Qualiopi, « à vie », paiement en plusieurs
 *     fois), ni chiffre sur EVKHA ;
 * (d) il commence par une réponse courte, et mène à la page des études.
 *
 * Contre-épreuve (règle 6) : le détecteur de (c) voit bien un montant et un
 * point non confirmé quand on lui en présente.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`.
 */
import React from "react";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { cleanup, render, screen } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { ARTICLES, composer, texteDeLArticle, THEMES } from "../public/contenuBlog";
import { GUIDES, GUIDES_PUBLIES } from "../public/contenuGuides";
import { adresseDeLArticle, CHEMINS, SLUG_IDEE_BUSINESS_VIABLE } from "../public/contenuSite";
import { creerRouteur } from "../router";
import { server } from "./server";

/** Un montant en euros, où qu'il soit — la règle du test des pages du blog. */
const MONTANT_ECRIT = /\d[\d\s.,]*(?:€|euros?\b)/i;

/** Ce que la cliente n'a pas confirmé, et un chiffre sur EVKHA. */
const NON_CONFIRME =
  /\bCPF\b|qualiopi|\bOPCO\b|à vie\b|plusieurs fois|sans frais|\d+\s*(?:ans d'expérience|clients|porteurs|entrepreneurs)|\d+\s*%|\d+\s*heures?|satisfait ou remboursé/i;

function toutLeTexte(guide: (typeof GUIDES)[number]): string {
  return [
    ...texteDeLArticle(guide),
    guide.entete.titreOnglet,
    guide.entete.description,
    guide.appel.titre,
    guide.appel.document,
    guide.appel.corps,
    guide.passerelle.titre.avant,
    guide.passerelle.titre.fin,
    guide.passerelle.corps,
  ].join("\n");
}

async function ouvrir(adresse: string) {
  server.use(
    http.get(`${window.location.origin}/api/*`, async () => {
      await delay("infinite");
      return new HttpResponse(null);
    }),
  );
  window.history.pushState({}, "", adresse);
  render(
    <RouterProvider router={creerRouteur(createMemoryHistory({ initialEntries: [adresse] }))} />,
  );
  await screen.findByRole("heading", { level: 1 }, { timeout: 8000 });
}

afterEach(() => cleanup());

/** Ce que la liste du blog porte À L'IMPORT, avant que ce fichier n'y touche :
 *  c'est ce qui partirait en ligne. */
const PUBLIES_A_L_IMPORT = ARTICLES.map((article) => article.slug);

// Les guides sont retenus tant que la cliente ne les a pas validés
// (`GUIDES_PUBLIES`). Pour juger leurs PAGES, ce fichier les inscrit lui-même
// dans la liste, comme elle le fera : c'est le seul geste de la publication.
if (!GUIDES_PUBLIES) ARTICLES.push(...GUIDES.map(composer));

describe("les guides du blog", () => {
  it("tant que la cliente ne les a pas validés, aucun guide n'est publié", () => {
    // Le drapeau et la liste disent la même chose : un guide ne peut pas
    // partir en ligne par un autre chemin.
    const guides = GUIDES.map((guide) => guide.slug);
    const publies = PUBLIES_A_L_IMPORT.filter((slug) => guides.includes(slug));
    expect(publies).toEqual(GUIDES_PUBLIES ? guides : []);
    expect(PUBLIES_A_L_IMPORT[0]).toBe(SLUG_IDEE_BUSINESS_VIABLE);
  });

  it("(a) une fois inscrits, ils suivent l'article de la cliente, qui reste à la une", () => {
    expect(GUIDES.length).toBeGreaterThanOrEqual(3);
    expect(ARTICLES[0].slug).toBe(SLUG_IDEE_BUSINESS_VIABLE);
    expect(ARTICLES.slice(1).map((article) => article.slug)).toEqual(GUIDES.map((guide) => guide.slug));
    expect(new Set(ARTICLES.map((article) => article.slug)).size).toBe(ARTICLES.length);
    for (const guide of GUIDES) {
      expect(guide.slug).toMatch(/^[a-z0-9]+(?:-[a-z0-9]+)*$/);
      expect(THEMES.map((theme) => theme.slug)).toContain(guide.theme);
    }
  });

  for (const guide of GUIDES) {
    it(`(b) « ${guide.slug} » : sa page, son titre, son sommaire, ses données structurées`, async () => {
      await ouvrir(adresseDeLArticle(guide.slug));

      const titres = screen.getAllByRole("heading", { level: 1 });
      expect(titres).toHaveLength(1);
      expect(titres[0]).toHaveTextContent(guide.titre);
      expect(document.head.querySelector('meta[name="robots"]')).toBeNull();

      // Le sommaire porte chaque partie, plus la conclusion.
      const sommaire = document.querySelector(".res-sommaire");
      expect(sommaire?.querySelectorAll("a")).toHaveLength(guide.sections.length + 1);

      const article = Array.from(
        document.querySelectorAll('script[type="application/ld+json"]'),
        (balise) => JSON.parse(balise.textContent ?? "") as Record<string, unknown>,
      ).find((bloc) => bloc["@type"] === "Article");
      expect(article?.headline).toBe(guide.titre);
      // Pas en ligne, donc pas de date : elle ne se suppose pas.
      expect(guide.publieLe).toBeNull();
      expect(article).not.toHaveProperty("datePublished");
      expect(document.querySelector("time")).toBeNull();
    });

    it(`(c) « ${guide.slug} » : aucun montant, aucun point non confirmé`, () => {
      const texte = toutLeTexte(guide);
      expect(texte.split(/\s+/).length).toBeGreaterThan(350);
      expect(texte.match(MONTANT_ECRIT)?.[0]).toBeUndefined();
      expect(texte.match(NON_CONFIRME)?.[0]).toBeUndefined();
    });

    it(`(d) « ${guide.slug} » : une réponse courte d'abord, et une porte vers les études`, () => {
      // Le premier paragraphe répond en une ou deux phrases : c'est lui qu'un
      // moteur de réponse reprend.
      const reponse = guide.chapo.paragraphes[0];
      expect(reponse.split(/\s+/).length).toBeLessThan(60);
      expect(guide.entete.description.length).toBeLessThanOrEqual(170);
      expect(guide.entete.titreOnglet.length).toBeLessThanOrEqual(60);
      expect(guide.passerelle.bouton.lien).toBe(CHEMINS.etudes);
      expect(guide.appel.bouton.lien).toBe(CHEMINS.boiteAOutils);
    });
  }

  it("contre-épreuve : le détecteur voit un montant et un point non confirmé", () => {
    for (const faute of ["dès 89 €", "à partir de 300 euros"]) {
      expect(faute, faute).toMatch(MONTANT_ECRIT);
    }
    for (const faute of [
      "finançable par le CPF",
      "certifié Qualiopi",
      "un accès à vie",
      "payable en plusieurs fois",
      "500 porteurs accompagnés",
      "100 % de réussite",
      "livré sous 24 heures",
    ]) {
      expect(faute, faute).toMatch(NON_CONFIRME);
    }
    for (const juste of ["les 6 étapes", "sur trois ans", "la première année"]) {
      expect(juste, juste).not.toMatch(NON_CONFIRME);
      expect(juste, juste).not.toMatch(MONTANT_ECRIT);
    }
  });
});

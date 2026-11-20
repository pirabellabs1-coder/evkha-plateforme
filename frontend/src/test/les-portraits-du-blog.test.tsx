/** Les portraits du blog : les porteurs de projet de « La Lettre des
 * Porteurs » (`contenuPortraits.ts`).
 *
 * La gérante a demandé le 20/11/2026 que les portraits de sa lettre
 * d'information paraissent sur le blog, et a transmis les deux premiers avec
 * leurs photos. Ce sont SES textes : ils sont publiés, contrairement aux
 * guides. Ce fichier verrouille, pour CHAQUE portrait de la liste — elle
 * n'est pas recopiée ici (règle 4) :
 *
 * (a) le portrait est publié par la liste du blog, dans le thème
 *     « Portraits », après l'article relevé, à son adresse ;
 * (b) il a SA photo : un fichier qui existe dans `public/`, un WebP aux
 *     dimensions déclarées, avec un texte alternatif — en tête de sa page
 *     (chargée tout de suite) et sur sa carte (chargée à l'approche) ;
 * (c) ses citations sont de vraies citations (`<blockquote>`), entre
 *     guillemets, avec leur auteur quand la lettre le dit ;
 * (d) son lien sortant s'ouvre dans un nouvel onglet, `noopener`, et son
 *     libellé dit où il mène ;
 * (e) les données structurées `Article` portent la photo, et aucune date :
 *     celle de la lettre n'est pas connue ;
 * (f) les chiffres de la lettre sont tous là, et aucun n'a été ajouté ;
 * (g) le lecteur est vouvoyé — seules les questions posées restent au « tu » ;
 * (h) il finit par l'invitation de la lettre (un courriel) et par UNE
 *     passerelle sans prix ; son titre d'onglet et sa description sont à lui.
 *
 * Contre-épreuves (règle 6) : l'article relevé, sans photo, n'a ni image ni
 * `image` dans ses données ; les détecteurs voient un tutoiement et un
 * montant quand on leur en présente.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`.
 */
import React from "react";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { Blog } from "../public/Blog";
import {
  ARTICLES,
  articleDuSlug,
  AUTEUR_DU_BLOG,
  BLOG,
  libelleDuTheme,
  texteDeLArticle,
  THEMES,
  type Article,
} from "../public/contenuBlog";
import { GUIDES, GUIDES_PUBLIES } from "../public/contenuGuides";
import { PORTRAITS } from "../public/contenuPortraits";
import type { ElementDArticle } from "../public/contenuRessources";
import { COORDONNEES } from "../public/contenuRessources";
import { adresseDeLArticle, CHEMINS, SLUG_IDEE_BUSINESS_VIABLE } from "../public/contenuSite";
import { creerRouteur } from "../router";
import { server } from "./server";

const PUBLIC = join(process.cwd(), "public");

const INSECABLE = String.fromCharCode(0xa0);

function espaces(brut: string): string {
  return brut.replace(new RegExp(INSECABLE, "g"), " ");
}

/** Un montant en euros, où qu'il soit — la règle du test des pages du blog. */
const MONTANT_ECRIT = /\d[\d\s.,]*(?:€|euros?\b)/i;

/** Un tutoiement du LECTEUR : pronom ou possessif de la deuxième personne du
 *  singulier, mot entier — ou élidé devant une voyelle (« t'aider »). */
const TUTOIEMENT = /(?<![\p{L}-])(?:(?:tu|toi|te|ton|ta|tes)(?![\p{L}])|t['’](?=\p{L}))/iu;

/** Ce que les deux lettres écrivent en chiffres, relevé À LA MAIN dans les
 *  courriels de la gérante — pas lu dans le contenu. */
const CHIFFRES_DES_LETTRES: Record<string, string[]> = {
  "portrait-jeffrey-yeye-mondossierptp": [],
  "portrait-lea-marie-le-cordier-le-boeuf-club": ["+101,5 %", "2 600", "10 700", "220 leads"],
};

/** Les adresses que les lettres donnent, relevées à la main. */
const LIENS_DES_LETTRES: Record<string, string> = {
  "portrait-jeffrey-yeye-mondossierptp": "https://www.mondossierptp.fr",
  "portrait-lea-marie-le-cordier-le-boeuf-club": "https://www.linkedin.com/company/le-boeuf-club/",
};

function elementsDe(article: Article): ElementDArticle[] {
  return [
    ...article.sections.flatMap((section) => [
      ...section.elements,
      ...(section.sousSections ?? []).flatMap((sous) => sous.elements),
    ]),
    ...article.conclusion.elements,
  ];
}

function citationsDe(article: Article) {
  return elementsDe(article).filter((element) => element.genre === "citation");
}

function liensDe(article: Article) {
  return elementsDe(article).filter((element) => element.genre === "lien");
}

/** Les questions POSÉES à la personne : les intertitres des sous-parties. */
function questionsPosees(article: Article): string[] {
  return article.sections.flatMap((section) => (section.sousSections ?? []).map((sous) => sous.intertitre));
}

/** Largeur et hauteur d'un WebP, lues dans son en-tête (formats `VP8 `,
 *  `VP8L` et `VP8X`) : le test ne croit pas le contenu sur parole. */
function dimensionsDuWebp(fichier: string): { largeur: number; hauteur: number } {
  const o = readFileSync(fichier);
  expect(o.subarray(0, 4).toString("latin1"), fichier).toBe("RIFF");
  expect(o.subarray(8, 12).toString("latin1"), fichier).toBe("WEBP");
  const format = o.subarray(12, 16).toString("latin1");
  if (format === "VP8 ") {
    return { largeur: o.readUInt16LE(26) & 0x3fff, hauteur: o.readUInt16LE(28) & 0x3fff };
  }
  if (format === "VP8L") {
    const bits = o.readUInt32LE(21);
    return { largeur: (bits & 0x3fff) + 1, hauteur: ((bits >> 14) & 0x3fff) + 1 };
  }
  if (format === "VP8X") {
    return { largeur: o.readUIntLE(24, 3) + 1, hauteur: o.readUIntLE(27, 3) + 1 };
  }
  throw new Error(`${fichier} : format WebP inconnu « ${format} »`);
}

function serveurMuet() {
  server.use(
    http.get(`${window.location.origin}/api/*`, async () => {
      await delay("infinite");
      return new HttpResponse(null);
    }),
  );
}

/** Monte le VRAI routeur à l'adresse de l'article. */
async function ouvrir(slug: string) {
  serveurMuet();
  const adresse = adresseDeLArticle(slug);
  window.history.pushState({}, "", adresse);
  render(<RouterProvider router={creerRouteur(createMemoryHistory({ initialEntries: [adresse] }))} />);
  await screen.findByRole("heading", { level: 1 }, { timeout: 8000 });
}

function donneesDeLArticle(): Record<string, unknown> {
  const bloc = Array.from(
    document.querySelectorAll('script[type="application/ld+json"]'),
    (balise) => JSON.parse(balise.textContent ?? "") as Record<string, unknown>,
  ).find((donnees) => donnees["@type"] === "Article");
  if (!bloc) throw new Error("aucune donnée structurée « Article » sur la page");
  return bloc;
}

function texteDuContenu(): string {
  return espaces(screen.getByRole("main").textContent ?? "");
}

afterEach(() => {
  cleanup();
  window.history.pushState({}, "", "/");
});

/** Les portraits tels que la liste du blog les publie. */
const PUBLIES = PORTRAITS.map((source) => {
  const article = articleDuSlug(source.slug);
  if (!article) throw new Error(`le portrait « ${source.slug} » n'est pas dans la liste du blog`);
  return article;
});

describe("les portraits du blog", () => {
  it("(a) deux portraits, publiés dans le thème « Portraits », après l'article relevé", () => {
    // Règle 1 : une liste vide ferait passer toutes les boucles.
    expect(PORTRAITS.map((portrait) => portrait.slug).sort()).toEqual([
      "portrait-jeffrey-yeye-mondossierptp",
      "portrait-lea-marie-le-cordier-le-boeuf-club",
    ]);
    expect(THEMES.map((theme) => theme.slug)).toContain("portraits");
    expect(libelleDuTheme("portraits")).toBe("Portraits");

    const slugs = ARTICLES.map((article) => article.slug);
    expect(slugs[0]).toBe(SLUG_IDEE_BUSINESS_VIABLE);
    expect(slugs.slice(1, 1 + PORTRAITS.length)).toEqual(PORTRAITS.map((portrait) => portrait.slug));
    expect(new Set(slugs).size).toBe(slugs.length);
    // Les guides, eux, restent retenus : ce lot ne les a pas publiés.
    expect(GUIDES_PUBLIES).toBe(false);
    for (const guide of GUIDES) expect(slugs).not.toContain(guide.slug);

    for (const portrait of PUBLIES) {
      expect(portrait.slug).toMatch(/^[a-z0-9]+(?:-[a-z0-9]+)*$/);
      expect(portrait.theme).toBe("portraits");
      // La date de parution de la lettre n'est pas connue : elle ne se
      // suppose pas.
      expect(portrait.publieLe).toBeNull();
      expect(portrait.conclusion.signature).toBe("Evangéline");
      expect(portrait.auteur).toBeUndefined();
      expect(portrait.tempsDeLecture).toBeGreaterThanOrEqual(1);
    }
  });

  it("(b) chaque portrait a sa photo : un fichier qui existe, aux dimensions déclarées", () => {
    for (const portrait of PUBLIES) {
      const image = portrait.image;
      expect(image, portrait.slug).toBeDefined();
      if (!image) continue;
      expect(image.src, portrait.slug).toMatch(/^\/blog\/[a-z0-9-]+\.webp$/);
      const fichier = join(PUBLIC, ...image.src.split("/").filter(Boolean));
      expect(existsSync(fichier), `${image.src} est absent de public/`).toBe(true);
      expect(dimensionsDuWebp(fichier), image.src).toEqual({
        largeur: image.largeur,
        hauteur: image.hauteur,
      });
      // Raisonnable : ni une vignette, ni l'original de plusieurs centaines
      // de kilo-octets.
      expect(image.largeur).toBeGreaterThanOrEqual(800);
      expect(image.largeur).toBeLessThanOrEqual(1200);
      expect(readFileSync(fichier).length, image.src).toBeLessThan(150_000);
      // Le texte alternatif nomme la personne, sobrement.
      expect(image.alt, portrait.slug).toBe(portrait.titre);
      expect(image.alt.length).toBeGreaterThan(15);
    }
    expect(new Set(PUBLIES.map((portrait) => portrait.image?.src)).size).toBe(PUBLIES.length);
  });

  it("(b) la liste du blog : la carte de chaque portrait porte sa photo, et le filtre « Portraits » répond", () => {
    window.history.pushState({}, "", CHEMINS.blog);
    render(<Blog />);

    const cartes = () => Array.from(document.querySelectorAll<HTMLElement>("article.res-article"));
    expect(cartes()).toHaveLength(ARTICLES.length);
    for (const portrait of PUBLIES) {
      const carte = cartes().find((c) => within(c).queryByRole("heading", { name: portrait.titre }));
      expect(carte, portrait.slug).toBeDefined();
      if (!carte || !portrait.image) continue;
      const photo = within(carte).getByRole("img", { name: portrait.image.alt });
      expect(photo).toHaveAttribute("src", portrait.image.src);
      expect(photo).toHaveAttribute("width", String(portrait.image.largeur));
      expect(photo).toHaveAttribute("height", String(portrait.image.hauteur));
      expect(photo).toHaveAttribute("loading", "lazy");
      expect(photo).toHaveAttribute("decoding", "async");
      // Le cadrage désigné par le contenu est appliqué : le visage reste en vue.
      expect(photo.style.objectPosition).toBe(portrait.image.cadrage);
      // UN lien par carte, porté par le titre : la photo n'en ajoute pas.
      const liens = within(carte).getAllByRole("link");
      expect(liens).toHaveLength(1);
      expect(liens[0]).toHaveAttribute("href", `/blog/${portrait.slug}`);
      // Le chapô court est une phrase DE l'article.
      expect(espaces(carte.textContent ?? "")).toContain(espaces(portrait.accroche));
      expect(texteDeLArticle(portrait).join("\n")).toContain(portrait.accroche);
    }
    // Contre-épreuve : la carte de l'article relevé, sans photo, n'a pas d'image.
    const releve = cartes().find((c) => c.querySelector(`a[href="/blog/${SLUG_IDEE_BUSINESS_VIABLE}"]`));
    expect(releve?.querySelector("img")).toBeNull();
    expect(releve).not.toHaveClass("res-article-illustre");

    // Le filtre « Portraits » n'est plus vide : il ne garde que les portraits.
    const filtre = within(screen.getByRole("group", { name: BLOG.filtres.nom })).getByRole("button", {
      name: "Portraits",
    }) as HTMLButtonElement;
    expect(filtre.disabled).toBe(false);
    fireEvent.click(filtre);
    expect(cartes()).toHaveLength(PUBLIES.length);
    expect(screen.getByRole("status")).toHaveTextContent(`${PUBLIES.length} articles — Portraits`);
    // Le premier de la liste filtrée passe à la une, avec sa photo.
    expect(cartes()[0].closest("li")).toHaveClass("res-article-rang-une");
    expect(cartes()[0].querySelector("img")).not.toBeNull();
  });

  for (const portrait of PUBLIES) {
    it(`« ${portrait.slug} » : sa page, sa photo, ses citations, son lien, ses données structurées`, async () => {
      await ouvrir(portrait.slug);
      const page = texteDuContenu();

      // L'aperçu d'un lien partagé montre la PERSONNE, à son adresse complète
      // et à ses dimensions — pas le logo du gabarit.
      const partage = (selecteur: string) =>
        document.head.querySelector(selecteur)?.getAttribute("content");
      expect(partage('meta[property="og:image"]')).toBe(`https://evkha.fr${portrait.image?.src}`);
      expect(partage('meta[name="twitter:image"]')).toBe(`https://evkha.fr${portrait.image?.src}`);
      expect(partage('meta[property="og:image:width"]')).toBe(String(portrait.image?.largeur));
      expect(partage('meta[property="og:image:height"]')).toBe(String(portrait.image?.hauteur));

      // Un seul h1, des titres sans saut, la page se laisse indexer.
      const titres = screen.getAllByRole("heading", { level: 1 });
      expect(titres).toHaveLength(1);
      expect(titres[0]).toHaveTextContent(portrait.titre);
      const niveaux = Array.from(document.querySelectorAll("main h1, main h2, main h3, main h4")).map((t) =>
        Number(t.tagName[1]),
      );
      niveaux.forEach((niveau, k) => {
        if (k > 0) expect(niveau - niveaux[k - 1], `saut de titre au rang ${k}`).toBeLessThanOrEqual(1);
      });
      expect(document.head.querySelector('meta[name="robots"]')).toBeNull();
      expect(document.title).toBe(`${portrait.entete.titreOnglet} — EVKHA`);

      // Tout ce que l'article écrit est affiché.
      const phrases = texteDeLArticle(portrait);
      expect(phrases.length).toBeGreaterThan(15);
      for (const phrase of phrases) {
        expect(page, `la page ne dit plus : « ${phrase} »`).toContain(espaces(phrase));
      }

      // (b) La photo, en tête de l'article : avant le texte, chargée tout de suite.
      const image = portrait.image;
      if (!image) throw new Error(`${portrait.slug} : pas de photo`);
      const photos = within(screen.getByRole("main")).getAllByRole("img");
      expect(photos).toHaveLength(1);
      const photo = photos[0];
      expect(photo).toHaveAttribute("src", image.src);
      expect(photo).toHaveAttribute("alt", image.alt);
      expect(photo).toHaveAttribute("width", String(image.largeur));
      expect(photo).toHaveAttribute("height", String(image.hauteur));
      expect(photo).toHaveAttribute("loading", "eager");
      expect(photo).toHaveAttribute("decoding", "async");
      expect(photo.style.objectPosition).toBe(image.cadrage);
      const prose = document.querySelector(".res-prose") as HTMLElement;
      expect(photo.compareDocumentPosition(prose) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      // Une photo verticale garde un cadre vertical : elle n'est pas rognée
      // en bandeau.
      expect(photo.closest(".res-photo")?.classList.contains("res-photo-verticale")).toBe(
        image.hauteur > image.largeur,
      );

      // (c) Les citations : de vraies citations, entre guillemets, signées
      // quand la lettre dit de qui elles sont.
      const citations = citationsDe(portrait);
      expect(citations.length, portrait.slug).toBeGreaterThanOrEqual(1);
      const blocs = Array.from(document.querySelectorAll<HTMLElement>("figure.res-citation"));
      expect(blocs).toHaveLength(citations.length);
      citations.forEach((citation, k) => {
        const paroles = blocs[k].querySelector("blockquote");
        expect(paroles?.textContent).toBe(`«${INSECABLE}${citation.texte}${INSECABLE}»`);
        // Le contenu écrit les paroles SANS guillemets : la page les pose.
        expect(citation.texte).not.toMatch(/^[«"]|[»"]$/);
        const legende = blocs[k].querySelector("figcaption");
        if (citation.auteur === undefined) expect(legende).toBeNull();
        else expect(legende).toHaveTextContent(citation.auteur);
      });
      // Au moins une citation est attribuée à la personne du portrait.
      expect(citations.some((citation) => citation.auteur && portrait.titre.startsWith(citation.auteur))).toBe(
        true,
      );

      // (d) Le lien sortant : celui de la lettre, dans un nouvel onglet.
      const liens = liensDe(portrait);
      expect(liens).toHaveLength(1);
      expect(liens[0].lien).toBe(LIENS_DES_LETTRES[portrait.slug]);
      const sortants = Array.from(prose.querySelectorAll<HTMLAnchorElement>('a[target="_blank"]'));
      expect(sortants).toHaveLength(1);
      expect(sortants[0]).toHaveAttribute("href", LIENS_DES_LETTRES[portrait.slug]);
      expect(sortants[0].getAttribute("rel")).toContain("noopener");
      expect(sortants[0]).toHaveTextContent(liens[0].libelle);
      expect(sortants[0]).toHaveTextContent("(nouvel onglet)");
      // Le libellé dit où il mène : pas « cliquez ici ».
      expect(liens[0].libelle).toMatch(/mondossierptp\.fr|LinkedIn/);
      // Aucun autre lien de la page ne sort du site.
      for (const lien of Array.from(screen.getByRole("main").querySelectorAll("a"))) {
        if (lien === sortants[0]) continue;
        expect(lien.getAttribute("href") ?? "", lien.outerHTML).toMatch(/^(\/|#|mailto:)/);
      }

      // (e) Les données structurées : la photo, à son adresse complète, et
      // aucune date.
      const donnees = donneesDeLArticle();
      expect(donnees.headline).toBe(portrait.titre);
      expect(donnees.articleSection).toBe("Portraits");
      expect(donnees.image).toEqual({
        "@type": "ImageObject",
        url: `${window.location.origin}${image.src}`,
        width: image.largeur,
        height: image.hauteur,
      });
      expect(donnees.author).toEqual({ "@type": "Person", name: AUTEUR_DU_BLOG });
      expect(Object.keys(donnees).filter((cle) => /date/i.test(cle))).toEqual([]);
      expect(document.querySelector("time")).toBeNull();

      // (h) L'invitation de la lettre : un courriel à l'adresse de contact.
      const bonus = document.querySelector(".res-bonus") as HTMLElement;
      expect(espaces(bonus.textContent ?? "")).toContain(
        "Vous souhaitez qu'on parle de vous dans la prochaine Lettre des Porteurs ?",
      );
      const courriel = within(bonus).getByRole("link");
      const href = courriel.getAttribute("href") ?? "";
      expect(href.startsWith(`mailto:${COORDONNEES.courriel}?subject=`), href).toBe(true);
      expect(decodeURIComponent(href.split("?subject=")[1] ?? "")).toMatch(/Lettre des Porteurs/);
      expect(courriel).toHaveTextContent(/e-mail/);
      // Puis UNE passerelle, sans prix, vers les études.
      const passerelles = screen.getByRole("main").querySelectorAll(".acc-fin");
      expect(passerelles).toHaveLength(1);
      expect(within(passerelles[0] as HTMLElement).getByRole("link")).toHaveAttribute("href", CHEMINS.etudes);
      expect(page).not.toMatch(MONTANT_ECRIT);
      // Aucun formulaire : la lettre n'en veut pas, la plateforme n'en a pas.
      expect(document.querySelectorAll("form, input, textarea, select")).toHaveLength(0);
    });

    it(`« ${portrait.slug} » : (f) les chiffres de la lettre, tous et eux seuls ; (g) le lecteur est vouvoyé`, () => {
      const texte = espaces(
        [
          ...texteDeLArticle(portrait),
          portrait.entete.titreOnglet,
          portrait.entete.description,
          portrait.appel.titre,
          portrait.appel.document,
          portrait.appel.corps,
          portrait.passerelle.titre.avant,
          portrait.passerelle.titre.fin,
          portrait.passerelle.corps,
        ].join("\n"),
      );

      // (f) Chaque chiffre de la lettre est là…
      const attendus = CHIFFRES_DES_LETTRES[portrait.slug];
      expect(attendus, portrait.slug).toBeDefined();
      for (const chiffre of attendus) expect(texte, chiffre).toContain(chiffre);
      // … et aucun autre nombre n'a été écrit : une fois ceux-là retirés, il
      // ne reste pas un chiffre dans le texte.
      const reste = attendus.reduce((courant, chiffre) => courant.split(chiffre).join(""), texte);
      expect(reste.match(/\d[\d\s.,%]*/g) ?? [], portrait.slug).toEqual([]);
      expect(texte).not.toMatch(MONTANT_ECRIT);

      // (g) Hors des questions posées et des paroles rapportées, personne
      // n'est tutoyé.
      const paroles = [...questionsPosees(portrait), ...citationsDe(portrait).map((c) => c.texte)];
      const narration = paroles.reduce((courant, parole) => courant.split(espaces(parole)).join(""), texte);
      expect(narration.match(TUTOIEMENT)?.[0], portrait.slug).toBeUndefined();
      expect(narration).toMatch(/\bvous\b|\bvotre\b|\bvos\b/i);

      // (h) Un titre d'onglet et une description à lui, de bonne longueur.
      expect(portrait.entete.titreOnglet.length).toBeLessThanOrEqual(60);
      expect(portrait.entete.description.length).toBeGreaterThan(80);
      expect(portrait.entete.description.length).toBeLessThanOrEqual(170);
    });
  }

  it("(h) aucun titre d'onglet, aucune description n'est partagé entre deux articles", () => {
    const titres = ARTICLES.map((article) => article.entete.titreOnglet);
    const descriptions = ARTICLES.map((article) => article.entete.description);
    expect(ARTICLES.length).toBeGreaterThanOrEqual(3);
    expect(new Set(titres).size).toBe(titres.length);
    expect(new Set(descriptions).size).toBe(descriptions.length);
    expect(titres).not.toContain(BLOG.titreOnglet);
    expect(descriptions).not.toContain(BLOG.description);
  });

  it("(g) les questions posées à Jeffrey restent au « tu », comme dans la lettre", () => {
    const jeffrey = PUBLIES.find((portrait) => portrait.slug.includes("jeffrey"));
    expect(jeffrey).toBeDefined();
    const questions = questionsPosees(jeffrey as Article);
    expect(questions).toHaveLength(3);
    for (const question of questions) expect(question, question).toMatch(TUTOIEMENT);
  });

  it("contre-épreuve : l'article relevé, sans photo, n'en affiche ni n'en déclare aucune", async () => {
    await ouvrir(SLUG_IDEE_BUSINESS_VIABLE);

    expect(articleDuSlug(SLUG_IDEE_BUSINESS_VIABLE)?.image).toBeUndefined();
    expect(screen.getByRole("main").querySelector("img")).toBeNull();
    expect(document.querySelector(".res-photo")).toBeNull();
    expect(donneesDeLArticle()).not.toHaveProperty("image");
    // Et aucune image de partage posée par la page : celle du gabarit reste.
    expect(document.head.querySelector('meta[property="og:image"]')).toBeNull();
    expect(document.querySelector("figure.res-citation")).toBeNull();
    expect(screen.getByRole("main").querySelector('a[target="_blank"]')).toBeNull();
  });

  it("contre-épreuve : les détecteurs voient un tutoiement, un montant, et laissent passer ce qui est juste", () => {
    for (const faute of ["le projet sort de ta tête", "Tu veux créer", "c'est à toi", "t'aider à avancer"]) {
      expect(faute, faute).toMatch(TUTOIEMENT);
    }
    for (const juste of ["sort de votre tête", "tout apprendre", "un statut", "une étude", "le site"]) {
      expect(juste, juste).not.toMatch(TUTOIEMENT);
    }
    expect("dès 89 €").toMatch(MONTANT_ECRIT);
    expect("+101,5 % de contacts").not.toMatch(MONTANT_ECRIT);
  });
});

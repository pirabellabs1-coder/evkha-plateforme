/** Les quatre pages légales disent tout leur texte, et rien que lui.
 *
 * `/mentions-legales`, `/rgpd`, `/cgv` et `/politique-de-confidentialite`
 * sont rendues par UN gabarit (`PageLegale`) à partir de `contenuLegal.ts`,
 * texte juridique repris mot pour mot du site de la cliente. Les verrous :
 *
 * 1. chaque page se rend, avec un seul h1 — son titre —, son titre d'onglet
 *    et sa description, uniques ;
 * 2. LE TEXTE EST ENTIER ET SEUL : le texte de l'élément qui le porte est
 *    ÉGAL à la mise bout à bout de l'introduction, des titres et des blocs du
 *    contenu, dans l'ordre. Une égalité, pas une suite de « contient » : un
 *    paragraphe perdu, déplacé, doublé ou AJOUTÉ la casse ;
 * 3. l'introduction est rendue AVANT la première section ;
 * 4. niveau 2 → `h2`, niveau 3 → `h3`, dans l'ordre, sans saut de niveau ;
 * 5. la date est écrite en casse normale, jour, mois et année inchangés ;
 * 6. le sommaire liste les sections de niveau 2, chaque lien vise le `h2`
 *    qui porte ce titre, et aucun identifiant n'est en double dans la page —
 *    y compris quand deux titres sont identiques ;
 * 7. la barre relie les quatre textes, et seul le texte affiché est
 *    « courant » ;
 * 8. une adresse écrite dans le texte est un lien, et le texte du paragraphe
 *    n'a pas changé ; la ponctuation qui la suit reste hors du lien ; un nom
 *    de marque en « .io » n'est pas une adresse ;
 * 9. AUCUN `pourquoi` de `POINTS_A_FAIRE_VALIDER` n'est dans le DOM : c'est
 *    une liste interne ;
 * 10. ni formulaire, ni bloc qui attend le défilement, ni bandeau défilant,
 *     ni adresse du CDN de l'ancien site, ni montant écrit dans le gabarit.
 *
 * Contre-épreuves (règle 6) : le détecteur de fuite voit un `pourquoi` qu'on
 * affiche exprès ; les détecteurs de sources voient ce qu'ils cherchent ; le
 * texte attendu n'est jamais vide (règle 1).
 *
 * ÉCRIT SANS ÊTRE LANCÉ le 19/11/2026 (consigne : ni `vitest` ni `tsc` pendant
 * la construction des pages). Il n'a donc pas encore été rejoué contre des
 * mutations du gabarit — à faire au premier passage : retirer le rendu de
 * l'introduction ; rendre un `h2` pour un niveau 3 ; retirer le
 * dédoublonnage de `ancres` ; inclure le point final dans un lien ; afficher
 * `POINTS_A_FAIRE_VALIDER`. Chacune doit rougir.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  PAGES_LEGALES,
  POINTS_A_FAIRE_VALIDER,
  type BlocLegal,
  type CheminLegal,
  type PageLegale as TexteLegal,
} from "../public/contenuLegal";
import {
  Cgv,
  MentionsLegales,
  PageLegale,
  PolitiqueDeConfidentialite,
  Rgpd,
} from "../public/PagesLegales";

/** Le composant de chaque chemin. Indexé par le type des chemins : une page
 *  sans composant ne compilerait pas. */
const COMPOSANTS: Record<CheminLegal, React.ComponentType> = {
  "/mentions-legales": MentionsLegales,
  "/rgpd": Rgpd,
  "/cgv": Cgv,
  "/politique-de-confidentialite": PolitiqueDeConfidentialite,
};

const NOMS_DANS_LA_BARRE: Record<CheminLegal, string> = {
  "/mentions-legales": "Mentions légales",
  "/rgpd": "RGPD",
  "/cgv": "CGV / CGU",
  "/politique-de-confidentialite": "Politique de confidentialité",
};

/** Les dates telles qu'elles doivent s'afficher. Écrites ici à la main, et
 *  non recalculées comme le fait la page : sinon le test répéterait le code
 *  qu'il vérifie. */
const DATES_AFFICHEES: Record<CheminLegal, string | null> = {
  "/mentions-legales": "Mise à jour le 28 avril 2026",
  "/rgpd": "Mise à jour le 28 avril 2026",
  "/cgv": null,
  "/politique-de-confidentialite": "Mise à jour le 28 octobre 2026",
};

// ── Outils ──────────────────────────────────────────────────────────────────

/** Toutes les espaces — insécables comprises — ramenées à une espace. Le
 *  rendu n'en ajoute ni n'en retire ; la normalisation ne sert qu'à ce qu'un
 *  écart d'espace ne masque pas un écart de mot dans le message d'échec. */
function normal(brut: string): string {
  return brut.replace(/\s+/g, " ").trim();
}

function texteDuBloc(bloc: BlocLegal): string {
  return bloc.type === "liste" ? bloc.elements.join("") : bloc.texte;
}

/** Le texte d'une page, mis bout à bout dans l'ordre où elle doit le dire. */
function texteAttendu(page: TexteLegal): string {
  return [
    ...page.introduction.map(texteDuBloc),
    ...page.sections.flatMap((section) => [
      section.titre,
      ...section.blocs.map(texteDuBloc),
    ]),
  ].join("");
}

function tousLesBlocs(page: TexteLegal): BlocLegal[] {
  return [...page.introduction, ...page.sections.flatMap((s) => s.blocs)];
}

function leTexte(): HTMLElement {
  const element = document.querySelector<HTMLElement>(".leg-texte");
  if (!element) throw new Error("l'élément qui porte le texte est introuvable");
  return element;
}

function lesTitres(): { niveau: number; titre: string; id: string }[] {
  return Array.from(leTexte().querySelectorAll("h2, h3")).map((t) => ({
    niveau: Number(t.tagName[1]),
    titre: t.textContent ?? "",
    id: t.id,
  }));
}

function leSommaire(): HTMLElement {
  return screen.getByRole("navigation", { name: "Sommaire" });
}

/** Les liens du sommaire, lus dans le DOM et non par rôle : repliés dans un
 *  `<details>` fermé, ils ne sont pas « accessibles » au sens de la
 *  bibliothèque de test. */
function liensDuSommaire(): HTMLAnchorElement[] {
  return Array.from(leSommaire().querySelectorAll<HTMLAnchorElement>("ol a"));
}

function identifiants(): string[] {
  return Array.from(document.querySelectorAll("[id]")).map((e) => e.id);
}

function doublons(liste: string[]): string[] {
  return liste.filter((valeur, k) => liste.indexOf(valeur) !== k);
}

/** Les `pourquoi` de la liste interne qui se retrouvent dans le DOM. */
function fuites(): string[] {
  const page = normal(document.body.textContent ?? "");
  return POINTS_A_FAIRE_VALIDER.map((point) => point.pourquoi).filter(
    (pourquoi) => page.includes(normal(pourquoi)),
  );
}

function occurrences(texte: string, motif: RegExp): number {
  return texte.match(motif)?.length ?? 0;
}

function source(fichier: string): string {
  return readFileSync(join(process.cwd(), "src", "public", fichier), "utf-8");
}

function sansCommentaires(code: string): string {
  return code.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

const MONTANT_ECRIT = /\d[\d\s.,]*(?:€|euros?\b)/i;
const REVELATION = /data-reveal|useReveler/;
const BOUCLE = /ruban|orbite/i;
const ANCIEN_CDN = /cloudfront|d1yei2z3i6k35z/i;
const FORMULAIRE = /<form\b/i;

/** Une page de texte montée de toutes pièces, pour ce que les quatre vraies
 *  ne contiennent pas forcément : deux titres identiques, un titre sans
 *  lettre, un titre qui viserait un identifiant du socle, et des adresses
 *  suivies de ponctuation. */
const PARAGRAPHE_A_ADRESSES =
  "Site : www.evkha.fr. Écrivez à contact@evkha.fr, voyez (evkha.fr) ou " +
  "WWW.EVKHA.FR ; Systeme.io (gestion), article L.221-18, 24h/24 et 7j/7.";

const FACTICE: TexteLegal = {
  chemin: "/cgv",
  titreOnglet: "Texte factice — onglet",
  metaDescription: "Texte factice — description",
  titre: "Texte factice",
  dateDeMiseAJour: "LE 1ER MARS 2027",
  introduction: [],
  sections: [
    {
      titre: "Article 1. Objet",
      niveau: 2,
      blocs: [{ type: "paragraphe", texte: PARAGRAPHE_A_ADRESSES }],
    },
    { titre: "Article 1. Objet", niveau: 3, blocs: [] },
    {
      titre: "Article 1 : Objet",
      niveau: 2,
      blocs: [{ type: "liste", elements: ["contact@evkha.fr", "sans adresse"] }],
    },
    { titre: "§ — !", niveau: 2, blocs: [] },
    { titre: "Acc contenu", niveau: 2, blocs: [] },
    { titre: "Article 1 Objet 2", niveau: 2, blocs: [] },
  ],
};

// ── Les quatre pages ────────────────────────────────────────────────────────

describe("les pages légales", () => {
  let description: HTMLMetaElement;

  beforeEach(() => {
    // Le gabarit HTML de l'application porte une description ; jsdom non.
    description = document.createElement("meta");
    description.name = "description";
    description.content = "description du gabarit";
    document.head.appendChild(description);
  });

  afterEach(() => {
    cleanup();
    description.remove();
    window.history.pushState({}, "", "/");
  });

  // Règle 1 : si la liste était vide, toutes les boucles ci-dessous
  // passeraient sans rien vérifier.
  it("le contenu porte quatre pages, une par composant, et chacune a du texte", () => {
    expect(PAGES_LEGALES.map((p) => p.chemin).sort()).toEqual(
      Object.keys(COMPOSANTS).sort(),
    );
    for (const page of PAGES_LEGALES) {
      expect(texteAttendu(page).length, page.chemin).toBeGreaterThan(2000);
      expect(page.sections.filter((s) => s.niveau === 2).length, page.chemin).toBeGreaterThan(3);
    }
    // Les deux pages qui ont une introduction, et les deux qui n'en ont pas :
    // les deux branches du gabarit sont jouées.
    expect(PAGES_LEGALES.filter((p) => p.introduction.length > 0)).toHaveLength(2);
    expect(POINTS_A_FAIRE_VALIDER.length).toBeGreaterThan(30);
  });

  for (const page of PAGES_LEGALES) {
    const Page = COMPOSANTS[page.chemin];

    describe(page.chemin, () => {
      beforeEach(() => window.history.pushState({}, "", page.chemin));

      it("se rend avec un seul h1, son titre d'onglet et sa description", () => {
        render(<Page />);

        const titres = screen.getAllByRole("heading", { level: 1 });
        expect(titres).toHaveLength(1);
        expect(titres[0].textContent).toBe(page.titre);
        expect(document.title).toBe(page.titreOnglet);
        expect(description.content).toBe(page.metaDescription);
      });

      it("dit tout son texte, mot pour mot, dans l'ordre, et rien d'autre", () => {
        render(<Page />);

        const attendu = normal(texteAttendu(page));
        expect(attendu.length).toBeGreaterThan(2000);
        expect(normal(leTexte().textContent ?? "")).toBe(attendu);

        // Chaque bloc, un par un : le message d'échec nomme alors le bloc.
        const blocs = tousLesBlocs(page);
        const paragraphes = Array.from(leTexte().querySelectorAll("p")).map((p) => p.textContent);
        expect(paragraphes).toEqual(
          blocs.flatMap((b) => (b.type === "paragraphe" ? [b.texte] : [])),
        );
        const listes = Array.from(leTexte().querySelectorAll("ul")).map((ul) =>
          Array.from(ul.querySelectorAll("li")).map((li) => li.textContent),
        );
        expect(listes).toEqual(
          blocs.flatMap((b) => (b.type === "liste" ? [b.elements] : [])),
        );
        expect(paragraphes.length + listes.length).toBe(blocs.length);
      });

      it("rend l'introduction avant la première section — ou n'en rend pas quand il n'y en a pas", () => {
        render(<Page />);

        const introduction = leTexte().querySelector(".leg-intro");
        if (page.introduction.length === 0) {
          expect(introduction).toBeNull();
          // Le texte s'ouvre alors sur son premier titre.
          expect(leTexte().textContent?.startsWith(page.sections[0].titre)).toBe(true);
          return;
        }
        expect(introduction).not.toBeNull();
        expect(normal(introduction?.textContent ?? "")).toBe(
          normal(page.introduction.map(texteDuBloc).join("")),
        );
        const premierTitre = leTexte().querySelector("h2, h3") as Element;
        expect(
          (introduction as Element).compareDocumentPosition(premierTitre) &
            Node.DOCUMENT_POSITION_FOLLOWING,
        ).toBeTruthy();
        // Et elle n'est pas rangée sous un titre de section.
        expect(introduction?.querySelector("h2, h3")).toBeNull();
      });

      it("donne à chaque section son titre, au bon niveau, sans saut", () => {
        render(<Page />);

        expect(lesTitres().map(({ niveau, titre }) => ({ niveau, titre }))).toEqual(
          page.sections.map((s) => ({ niveau: s.niveau, titre: s.titre })),
        );
        const niveaux = Array.from(document.querySelectorAll("h1, h2, h3, h4, h5, h6")).map(
          (t) => Number(t.tagName[1]),
        );
        expect(niveaux[0]).toBe(1);
        expect(niveaux).toHaveLength(page.sections.length + 1);
        niveaux.forEach((niveau, k) => {
          if (k > 0) expect(niveau - niveaux[k - 1], `saut de titre au rang ${k}`).toBeLessThanOrEqual(1);
        });
      });

      it("écrit la date en casse normale, sans la changer", () => {
        render(<Page />);

        const date = document.querySelector(".leg-date");
        const attendue = DATES_AFFICHEES[page.chemin];
        if (attendue === null) {
          expect(page.dateDeMiseAJour).toBeNull();
          expect(date).toBeNull();
          expect(document.body.textContent).not.toContain("Mise à jour le");
          return;
        }
        expect(normal(date?.textContent ?? "")).toBe(attendue);
        // Le jour, le mois et l'année sont ceux du contenu.
        expect(page.dateDeMiseAJour?.toLowerCase()).toContain(
          attendue.replace("Mise à jour le ", ""),
        );
      });

      it("a un sommaire des sections de niveau 2, dont chaque lien vise son titre, et des ancres uniques", () => {
        render(<Page />);

        const deNiveau2 = page.sections.filter((s) => s.niveau === 2);
        const liens = liensDuSommaire();
        expect(liens.map((a) => a.textContent)).toEqual(deNiveau2.map((s) => s.titre));
        for (const lien of liens) {
          const href = lien.getAttribute("href") ?? "";
          expect(href.startsWith("#"), href).toBe(true);
          const cible = document.getElementById(href.slice(1));
          expect(cible, href).not.toBeNull();
          expect(cible?.tagName, href).toBe("H2");
          expect(cible?.textContent, href).toBe(lien.textContent);
        }
        // Deux liens ne visent jamais la même ancre.
        expect(doublons(liens.map((a) => a.getAttribute("href") ?? ""))).toEqual([]);

        // Chaque titre de section a son ancre, et aucun identifiant de la
        // page — socle compris — n'est en double.
        const titres = lesTitres();
        expect(titres).toHaveLength(page.sections.length);
        for (const titre of titres) {
          expect(titre.id, titre.titre).toMatch(/^[a-z0-9]+(?:-[a-z0-9]+)*$/);
        }
        expect(identifiants().length).toBeGreaterThan(page.sections.length);
        expect(doublons(identifiants())).toEqual([]);

        // Sans `matchMedia` (jsdom), c'est la forme du téléphone : repliée.
        const volet = leSommaire().querySelector("details");
        expect(volet).not.toBeNull();
        expect(volet).not.toHaveAttribute("open");
        expect(volet?.querySelector("summary")?.textContent).toBe("Sommaire");
        // Le sommaire précède le texte.
        expect(
          leSommaire().compareDocumentPosition(leTexte()) & Node.DOCUMENT_POSITION_FOLLOWING,
        ).toBeTruthy();
      });

      it("les ancres sont stables d'un rendu à l'autre", () => {
        const premier = render(<Page />);
        const avant = lesTitres().map((t) => t.id);
        premier.unmount();
        render(<Page />);
        expect(lesTitres().map((t) => t.id)).toEqual(avant);
        expect(avant.length).toBe(page.sections.length);
      });

      it("relie les quatre textes, et seul celui-ci est « courant »", () => {
        render(<Page />);

        const barre = screen.getByRole("navigation", { name: "Textes légaux" });
        const liens = within(barre).getAllByRole("link");
        expect(liens.map((a) => a.getAttribute("href"))).toEqual(PAGES_LEGALES.map((p) => p.chemin));
        expect(liens.map((a) => a.textContent)).toEqual(
          PAGES_LEGALES.map((p) => NOMS_DANS_LA_BARRE[p.chemin]),
        );
        const courants = liens.filter((a) => a.getAttribute("aria-current") === "page");
        expect(courants.map((a) => a.getAttribute("href"))).toEqual([page.chemin]);
        expect(barre.querySelectorAll("[aria-current]")).toHaveLength(1);
      });

      it("rend cliquable chaque adresse écrite dans le texte, sans toucher au texte", () => {
        render(<Page />);

        // Bloc par bloc, séparés par un saut de ligne : mis bout à bout sans
        // séparateur, la fin d'un bloc collerait au début du suivant et
        // fausserait le compte.
        const ecrit = tousLesBlocs(page)
          .flatMap((b) => (b.type === "liste" ? b.elements : [b.texte]))
          .join("\n");
        const courriels = occurrences(ecrit, /contact@evkha\.fr/gi);
        // Le domaine écrit hors d'une adresse e-mail : « www.evkha.fr »,
        // « WWW.evkha.fr », « evkha.fr ».
        const sites = occurrences(ecrit, /(?<!@)(?<![a-z0-9.-])(?:www\.)?evkha\.fr/gi);
        // Règle 1 : chaque page cite au moins une adresse.
        expect(courriels + sites, "aucune adresse à vérifier").toBeGreaterThan(0);

        const liens = Array.from(leTexte().querySelectorAll("a"));
        const versCourriel = liens.filter((a) => a.getAttribute("href")?.startsWith("mailto:"));
        const versSite = liens.filter((a) => a.getAttribute("href")?.startsWith("https://"));
        expect(versCourriel).toHaveLength(courriels);
        expect(versSite).toHaveLength(sites);
        expect(liens).toHaveLength(courriels + sites);

        for (const lien of versCourriel) {
          expect(lien.textContent).toBe("contact@evkha.fr");
          expect(lien).toHaveAttribute("href", "mailto:contact@evkha.fr");
        }
        for (const lien of versSite) {
          expect(lien.textContent?.toLowerCase()).toMatch(/^(?:www\.)?evkha\.fr$/);
          expect(lien).toHaveAttribute("href", "https://www.evkha.fr");
        }
        // Un nom de prestataire n'est pas un lien, même terminé en « .io ».
        expect(liens.filter((a) => /systeme/i.test(a.textContent ?? ""))).toEqual([]);
      });

      it("n'affiche rien de la liste interne des points à faire valider", () => {
        render(<Page />);
        expect(fuites()).toEqual([]);
      });

      it("est une page de lecture : ni formulaire, ni bloc en attente, ni bandeau, et le clavier s'y retrouve", () => {
        render(<Page />);

        expect(document.querySelector("form")).toBeNull();
        expect(document.querySelector("[data-reveal]")).toBeNull();
        expect(document.querySelector(".acc-ruban")).toBeNull();

        const principal = screen.getByRole("main");
        expect(principal.id).not.toBe("");
        expect(screen.getByRole("link", { name: "Aller au contenu" })).toHaveAttribute(
          "href",
          `#${principal.id}`,
        );
        // « Retour en haut » ramène au contenu, et vit HORS du texte.
        const retour = screen.getByRole("link", { name: "Retour en haut" });
        expect(retour).toHaveAttribute("href", `#${principal.id}`);
        expect(leTexte().contains(retour)).toBe(false);
        // Rien de focalisable sous `aria-hidden`.
        for (const cache of Array.from(document.querySelectorAll("[aria-hidden='true']"))) {
          expect(
            cache.querySelector("a, button, input, select, textarea, summary, [tabindex]"),
            cache.className,
          ).toBeNull();
        }
        // La racine est celle des pages refondues.
        expect(document.querySelector(".acc.leg")).not.toBeNull();
      });
    });
  }

  it("les titres d'onglet et les descriptions sont uniques d'une page à l'autre", () => {
    expect(doublons(PAGES_LEGALES.map((p) => p.titreOnglet))).toEqual([]);
    expect(doublons(PAGES_LEGALES.map((p) => p.metaDescription))).toEqual([]);
  });

  // ── Le gabarit, sur un texte monté de toutes pièces ───────────────────────

  describe("le gabarit, sur un texte factice", () => {
    it("dédoublonne les ancres : deux titres identiques, un titre sans lettre, un identifiant du socle", () => {
      render(<PageLegale page={FACTICE} />);

      expect(lesTitres().map((t) => t.id)).toEqual([
        "article-1-objet",
        "article-1-objet-2",
        "article-1-objet-3",
        "section",
        // « acc-contenu » est l'identifiant du contenu principal.
        "acc-contenu-2",
        // « article-1-objet-2 » est déjà pris par le deuxième titre.
        "article-1-objet-2-2",
      ]);
      expect(doublons(identifiants())).toEqual([]);
      expect(screen.getByRole("main").id).toBe("acc-contenu");
      // Le sommaire : les cinq titres de niveau 2, chacun vers SON titre.
      const liens = liensDuSommaire();
      expect(liens.map((a) => a.getAttribute("href"))).toEqual([
        "#article-1-objet",
        "#article-1-objet-3",
        "#section",
        "#acc-contenu-2",
        "#article-1-objet-2-2",
      ]);
      for (const lien of liens) {
        const cible = document.getElementById((lien.getAttribute("href") ?? "").slice(1));
        expect(cible?.tagName).toBe("H2");
        expect(cible?.textContent).toBe(lien.textContent);
      }
    });

    it("découpe un paragraphe autour de ses adresses, ponctuation hors du lien", () => {
      render(<PageLegale page={FACTICE} />);

      const paragraphe = leTexte().querySelector("p") as HTMLElement;
      // Le texte n'a pas bougé d'un caractère.
      expect(paragraphe.textContent).toBe(PARAGRAPHE_A_ADRESSES);
      const liens = Array.from(paragraphe.querySelectorAll("a")).map((a) => [
        a.textContent,
        a.getAttribute("href"),
      ]);
      expect(liens).toEqual([
        ["www.evkha.fr", "https://www.evkha.fr"],
        ["contact@evkha.fr", "mailto:contact@evkha.fr"],
        ["evkha.fr", "https://www.evkha.fr"],
        ["WWW.EVKHA.FR", "https://www.evkha.fr"],
      ]);
      // Dans une liste aussi, et un élément sans adresse reste du texte nu.
      const elements = Array.from(leTexte().querySelectorAll("li"));
      expect(elements.map((li) => li.textContent)).toEqual(["contact@evkha.fr", "sans adresse"]);
      expect(elements[0].querySelector("a")).toHaveAttribute("href", "mailto:contact@evkha.fr");
      expect(elements[1].querySelector("a")).toBeNull();
      // Un titre n'est jamais découpé.
      expect(leTexte().querySelectorAll("h2 a, h3 a")).toHaveLength(0);
    });

    it("ramène « LE 1ER MARS 2027 » à une casse normale", () => {
      render(<PageLegale page={FACTICE} />);
      expect(normal(document.querySelector(".leg-date")?.textContent ?? "")).toBe(
        "Mise à jour le 1er mars 2027",
      );
    });

    it("sans section de niveau 2, il n'y a pas de sommaire vide", () => {
      render(<PageLegale page={{ ...FACTICE, sections: [] }} />);
      expect(screen.queryByRole("navigation", { name: "Sommaire" })).toBeNull();
      expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    });

    it("sur grand écran, le sommaire est une colonne ouverte, sans volet", () => {
      const avant = window.matchMedia;
      window.matchMedia = ((requete: string) => ({
        matches: requete.includes("min-width"),
        media: requete,
        addEventListener: () => undefined,
        removeEventListener: () => undefined,
      })) as unknown as typeof window.matchMedia;
      try {
        render(<PageLegale page={FACTICE} />);
        expect(leSommaire().querySelector("details")).toBeNull();
        expect(liensDuSommaire()).toHaveLength(5);
        expect(within(leSommaire()).getAllByRole("link")).toHaveLength(5);
        // Le mot « Sommaire » est le nom de la région ; son double visible
        // est masqué aux lecteurs d'écran et ne contient rien de focalisable.
        const titre = leSommaire().querySelector(".leg-sommaire-titre");
        expect(titre?.textContent).toBe("Sommaire");
        expect(titre).toHaveAttribute("aria-hidden", "true");
      } finally {
        cleanup();
        window.matchMedia = avant;
      }
    });

    it("contre-épreuve : le détecteur de fuite voit un « pourquoi » qu'on affiche exprès", () => {
      const pourquoi = POINTS_A_FAIRE_VALIDER[0].pourquoi;
      render(
        <PageLegale
          page={{
            ...FACTICE,
            sections: [
              { titre: "Fuite", niveau: 2, blocs: [{ type: "paragraphe", texte: pourquoi }] },
            ],
          }}
        />,
      );
      expect(fuites()).toEqual([pourquoi]);
    });
  });

  // ── Les sources du lot ────────────────────────────────────────────────────

  for (const fichier of ["PagesLegales.tsx", "PagesLegales.css"]) {
    it(`${fichier} ne pose ni révélation, ni boucle, ni formulaire, ni adresse de l'ancien CDN`, () => {
      // Commentaires COMPRIS : un mot laissé en commentaire revient au
      // prochain copier-coller.
      const brut = source(fichier);
      // Règle 1 : un fichier vide ou introuvable ne « passe » pas.
      expect(brut.length, fichier).toBeGreaterThan(2000);
      for (const motif of [REVELATION, BOUCLE, ANCIEN_CDN, FORMULAIRE]) {
        expect(brut.match(new RegExp(motif.source, "gi")) ?? [], `${fichier} : ${motif.source}`).toEqual([]);
      }
    });
  }

  it("PagesLegales.tsx n'écrit aucun montant et n'importe pas la liste interne", () => {
    const code = sansCommentaires(source("PagesLegales.tsx"));
    expect(code.length).toBeGreaterThan(2000);
    expect(code.match(new RegExp(MONTANT_ECRIT.source, "gi")) ?? []).toEqual([]);
    expect(code).not.toContain("POINTS_A_FAIRE_VALIDER");
    // Le texte vient du fichier de contenu, il n'est pas recopié.
    expect(code).toContain("PAGES_LEGALES");
  });

  it("contre-épreuve : les détecteurs de sources voient ce qu'ils cherchent, et rien d'autre", () => {
    expect('<div data-reveal="">').toMatch(REVELATION);
    expect("useReveler(page, cle)").toMatch(REVELATION);
    expect('<div className="acc-ruban">').toMatch(BOUCLE);
    expect("animation: leg-orbite").toMatch(BOUCLE);
    expect("https://d1yei2z3i6k35z.cloudfront.net/9890127/x.png").toMatch(ANCIEN_CDN);
    expect('<form action="/contact">').toMatch(FORMULAIRE);
    expect("frais de recouvrement de 40 € HT").toMatch(MONTANT_ECRIT);
    for (const juste of [
      '<div className="leg-texte">',
      "une page de lecture, en-tête et pied communs",
      "le format de la date",
      "28 avril 2026",
    ]) {
      for (const motif of [REVELATION, BOUCLE, ANCIEN_CDN, FORMULAIRE, MONTANT_ECRIT]) {
        expect(juste, `${juste} / ${motif.source}`).not.toMatch(motif);
      }
    }
    expect(doublons(["a", "b", "a"])).toEqual(["a"]);
    expect(normal(`a${String.fromCharCode(0xa0)}b \n c`)).toBe("a b c");
  });
});

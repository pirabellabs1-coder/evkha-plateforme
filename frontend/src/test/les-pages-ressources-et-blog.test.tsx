/** Les pages ressources et le blog : boîte à outils, contact, Swapn, liste du
 * blog, page d'un article.
 *
 * Cinq pages reprises du site de la cliente (`Ressources.tsx`, `Blog.tsx`),
 * portes d'entrée GRATUITES de la plateforme. Ce que ce fichier verrouille :
 *
 * 1. chaque page se rend, à son adresse, avec un seul h1, des titres sans
 *    saut, un lien d'évitement qui vise le contenu, rien de focalisable sous
 *    `aria-hidden`, un titre d'onglet à elle ;
 * 2. AUCUN formulaire, aucun champ : la plateforme n'a pas de service pour les
 *    recevoir. Chaque formulaire du site est devenu un lien `mailto:` vers
 *    l'adresse de contact, avec un objet qui dit ce qui est demandé ;
 * 3. RIEN de ce que les pages disaient n'a disparu : chaque phrase relevée est
 *    dans le DOM — au VOUS : là où le relevé tutoie, c'est `texteAuVous` qui
 *    s'affiche, et le tutoiement n'y est plus ;
 * 4. le blog se construit sur `contenuBlog.ARTICLES` : un article s'ajoute par
 *    une entrée de liste, et la liste, les filtres, la page, le temps de
 *    lecture (CALCULÉ) et les données structurées suivent ;
 * 5. un thème sans article est affiché DÉSACTIVÉ, et la page ne promet aucun
 *    article à venir ;
 * 6. les données structurées de l'article ne portent pas de date tant que la
 *    date de publication est inconnue ;
 * 7. l'offre de Swapn est attribuée à Swapn : ses promesses (« le mieux
 *    noté », « 0 € », « en 24h ») ne s'affichent que dans la figure qui dit
 *    « Selon Swapn » ;
 * 8. chaque page se termine par UNE passerelle vers l'étape payante la plus
 *    proche, sans prix ;
 * 9. aucun montant et aucune adresse du CDN de l'ancien site ne sont écrits
 *    dans les sources du lot — la classe du défaut (règle 4).
 *
 * Contre-épreuves (règle 6) : les détecteurs voient bien un montant et une
 * adresse du CDN ; le temps de lecture bouge quand le texte s'allonge ; un
 * article daté déclare sa date ; un slug inconnu rend « introuvable ».
 *
 * ÉCRIT SANS ÊTRE JOUÉ : la consigne du lot interdisait de lancer `vitest`.
 * Ce fichier n'a donc pas encore été vu rouge contre un code fautif.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ArticleDeBlog, Blog } from "../public/Blog";
import {
  ARTICLES,
  BLOG,
  compterLesMots,
  composer,
  minutesDeLecture,
  MOTS_PAR_MINUTE,
  PAGE_ARTICLE,
  premierePhrase,
  texteDeLArticle,
  THEMES,
} from "../public/contenuBlog";
import {
  ARTICLE_IDEE_BUSINESS_VIABLE,
  BOITE_A_OUTILS,
  CONTACT,
  COORDONNEES,
  FORMULAIRES,
  PAGE_BOITE_A_OUTILS,
  PAGE_CONTACT,
  PAGE_SWAPN,
  SWAPN,
} from "../public/contenuRessources";
import { BoiteAOutils, Contact, Swapn } from "../public/Ressources";

// ── Outils ──────────────────────────────────────────────────────────────────

/** Les espaces insécables, construites par leur code, jamais tapées : écrites
 *  en clair, elles sont invisibles à la relecture et un outil d'édition les
 *  change sans le dire. */
const INSECABLE = String.fromCharCode(0xa0);
const FINE_INSECABLE = String.fromCharCode(0x202f);
const INSECABLES = new RegExp(`[${INSECABLE}${FINE_INSECABLE}]`, "g");

function espaces(brut: string): string {
  return brut.replace(INSECABLES, " ");
}

function principal(): HTMLElement {
  return screen.getByRole("main");
}

/** Le texte du contenu principal : sans la barre ni le pied, communs. */
function texte(): string {
  return espaces(principal().textContent ?? "");
}

function texteDe(element: Element | null): string {
  return espaces(element?.textContent ?? "");
}

/** Un montant en euros, où qu'il soit. */
const MONTANT_ECRIT = /\d[\d\s.,]*(?:€|euros?\b)/i;

/** Le CDN et le domaine de l'ancien site. L'adresse de contact
 *  (`contact@evkha.fr`) n'est pas une adresse du site. */
const ANCIEN_SITE = /cloudfront\.net|systeme\.io|(?:www\.)?evkha\.fr\//i;

/** Un texte écrit en dur entre deux balises : `>Des mots<`. Les accolades
 *  (`>{a.titre}<`) et les signes seuls (`>→<`) n'en sont pas ; la flèche
 *  d'une fonction (`=> a.theme`) non plus. */
const TEXTE_EN_DUR = /(?<!=)>\s*[A-Za-zÀ-ÿ][^<>{}]*[A-Za-zÀ-ÿ]{3,}[^<>{}]*</;

function sansCommentaires(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

function source(fichier: string): string {
  return readFileSync(join(process.cwd(), "src", "public", fichier), "utf-8");
}

/** L'objet d'un lien `mailto:`, décodé — et la vérification que le lien vise
 *  bien l'adresse de contact. */
function objetDuCourriel(lien: Element | null): string {
  const href = lien?.getAttribute("href") ?? "";
  expect(href.startsWith(`mailto:${COORDONNEES.courriel}?subject=`), href).toBe(true);
  return decodeURIComponent(href.split("?subject=")[1] ?? "");
}

/** Rend une page À SON ADRESSE : l'en-tête déduit l'entrée courante du
 *  chemin, et la liste du blog lit son filtre dans l'adresse. */
function rendre(page: React.ReactElement, chemin: string) {
  window.history.pushState({}, "", chemin);
  return render(page);
}

/** La page d'un article lit son slug par le routeur : on lui en monte un, à
 *  la même route que l'application (`/blog/$slug`). */
async function rendreLArticle(slug: string) {
  const chemin = `/blog/${slug}`;
  window.history.pushState({}, "", chemin);
  const racine = createRootRoute();
  const route = createRoute({
    getParentRoute: () => racine,
    path: "/blog/$slug",
    component: ArticleDeBlog,
  });
  const routeur = createRouter({
    routeTree: racine.addChildren([route]),
    history: createMemoryHistory({ initialEntries: [chemin] }),
  });
  const rendu = render(<RouterProvider router={routeur} />);
  await screen.findByRole("heading", { level: 1 });
  return rendu;
}

const VIABLE = ARTICLES[0];

/** Un second article, pour prouver que le blog se construit sur la liste. Il
 *  est DATÉ, dans un thème aujourd'hui vide, et assez long pour ne pas se lire
 *  en une minute. */
const MOT = "marché ";
const ESSAI = composer({
  slug: "article-d-essai",
  titre: "Un article d'essai sur le financement",
  sousTitre: "Écrit pour le test, jamais publié",
  theme: "financement",
  publieLe: "2026-03-09",
  entete: {
    titreOnglet: "Article d'essai – EVKHA",
    description: "Un article d'essai, pour le test.",
  },
  chapo: {
    intertitre: "Le chapô de l'essai",
    paragraphes: ["La première phrase du chapô d'essai. Puis une seconde phrase."],
  },
  sections: [
    {
      intertitre: "La seule partie de l'essai",
      elements: [{ genre: "paragraphe", texte: MOT.repeat(2 * MOTS_PAR_MINUTE).trim() }],
    },
  ],
  conclusion: {
    intertitre: "La conclusion de l'essai",
    elements: [{ genre: "paragraphe", texte: "Le dernier paragraphe de l'essai." }],
    salut: "À bientôt",
    signature: "La rédaction d'essai",
  },
  appel: {
    titre: "L'appel de l'essai",
    document: "Le document de l'essai",
    corps: "Le corps de l'appel d'essai",
    bouton: { libelle: "Le bouton de l'appel d'essai", lien: "/boite-a-outils" },
  },
  passerelle: {
    titre: { avant: "La passerelle", fin: "de l'essai." },
    corps: "Le corps de la passerelle d'essai.",
    bouton: { libelle: "Le bouton de la passerelle d'essai", lien: "/etudes" },
  },
});

/** Joue `corps` avec l'article d'essai dans la liste, puis le retire — même
 *  si une attente échoue. */
async function avecUnSecondArticle(corps: () => void | Promise<void>) {
  ARTICLES.push(ESSAI);
  try {
    await corps();
  } finally {
    ARTICLES.splice(ARTICLES.indexOf(ESSAI), 1);
  }
}

/** Les cinq pages du lot, plus la page « introuvable ». */
const PAGES: { nom: string; chemin: string; rendre: () => unknown; montantAdmis?: boolean }[] = [
  { nom: "boîte à outils", chemin: "/boite-a-outils", rendre: () => rendre(<BoiteAOutils />, "/boite-a-outils") },
  { nom: "blog", chemin: "/blog", rendre: () => rendre(<Blog />, "/blog") },
  { nom: "article", chemin: `/blog/${VIABLE.slug}`, rendre: () => rendreLArticle(VIABLE.slug) },
  { nom: "article introuvable", chemin: "/blog/nulle-part", rendre: () => rendreLArticle("nulle-part") },
  { nom: "contact", chemin: "/contact", rendre: () => rendre(<Contact />, "/contact") },
  // Le « 0 € » de l'offre de Swapn : attribué, et vérifié plus bas.
  { nom: "Swapn", chemin: "/swapn", rendre: () => rendre(<Swapn />, "/swapn"), montantAdmis: true },
];

afterEach(() => {
  cleanup();
  window.history.pushState({}, "", "/");
});

// ── Ce que toutes les pages tiennent ────────────────────────────────────────

describe("les pages ressources et le blog se laissent conduire", () => {
  for (const page of PAGES) {
    it(`${page.nom} : un seul h1, des titres sans saut, un lien d'évitement, aucun formulaire`, async () => {
      await page.rendre();

      expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
      const niveaux = Array.from(document.querySelectorAll("h1, h2, h3, h4, h5, h6")).map((t) =>
        Number(t.tagName[1]),
      );
      expect(niveaux[0]).toBe(1);
      // Règle 1 : une page sans titres passerait la boucle sans rien vérifier.
      expect(niveaux.length).toBeGreaterThanOrEqual(2);
      niveaux.forEach((niveau, k) => {
        if (k > 0) expect(niveau - niveaux[k - 1], `saut de titre au rang ${k}`).toBeLessThanOrEqual(1);
      });

      expect(principal().id).not.toBe("");
      expect(screen.getByRole("link", { name: "Aller au contenu" })).toHaveAttribute(
        "href",
        `#${principal().id}`,
      );

      // Aucun formulaire qui n'envoie rien : ni balise, ni champ.
      expect(document.querySelectorAll("form, input, textarea, select")).toHaveLength(0);

      // Rien de focalisable sous `aria-hidden`.
      for (const cache of Array.from(document.querySelectorAll("[aria-hidden='true']"))) {
        expect(
          cache.querySelector("a, button, input, select, textarea, summary, [tabindex]"),
          cache.className,
        ).toBeNull();
      }
      // Chaque image dit ce qu'elle est, et réserve sa place.
      for (const image of Array.from(document.querySelectorAll("img"))) {
        expect(image.hasAttribute("alt"), image.getAttribute("src") ?? "").toBe(true);
        expect(Number(image.getAttribute("width"))).toBeGreaterThan(0);
        expect(Number(image.getAttribute("height"))).toBeGreaterThan(0);
      }
    });

    it(`${page.nom} : le contenu ne cite ni l'ancien site, ni un prix d'EVKHA, et finit par UNE passerelle`, async () => {
      await page.rendre();

      const adresses = Array.from(principal().querySelectorAll("[href], [src]")).map(
        (e) => e.getAttribute("href") ?? e.getAttribute("src") ?? "",
      );
      // Règle 1 : une page sans lien n'aurait rien à comparer.
      expect(adresses.length).toBeGreaterThan(0);
      for (const adresse of adresses) {
        expect(adresse, adresse).not.toMatch(ANCIEN_SITE);
      }

      if (!page.montantAdmis) expect(texte()).not.toMatch(MONTANT_ECRIT);

      // La passerelle : la dernière section du contenu, avec UN lien, vers
      // une page de la plateforme, sans montant.
      const sections = principal().querySelectorAll(".acc-fin");
      expect(sections).toHaveLength(1);
      const passerelle = sections[0] as HTMLElement;
      const liens = within(passerelle).getAllByRole("link");
      expect(liens).toHaveLength(1);
      expect(liens[0].getAttribute("href")).toMatch(/^\/(etudes|formations|packs)$/);
      expect(texteDe(passerelle)).not.toMatch(MONTANT_ECRIT);
      // Rien ne la suit dans le contenu, hormis les données structurées.
      const suivants = Array.from(principal().children).slice(
        Array.from(principal().children).indexOf(passerelle) + 1,
      );
      expect(suivants.every((e) => e.tagName === "SCRIPT")).toBe(true);
    });
  }

  it("chaque page a son titre d'onglet et sa description, différents des autres", async () => {
    const titres: string[] = [];
    const descriptions: string[] = [];
    const meta = document.createElement("meta");
    meta.name = "description";
    meta.content = "la description du gabarit";
    document.head.append(meta);
    try {
      for (const page of PAGES) {
        await page.rendre();
        titres.push(document.title);
        descriptions.push(meta.content);
        cleanup();
      }
    } finally {
      meta.remove();
    }
    expect(titres.every((titre) => titre.length > 10)).toBe(true);
    expect(new Set(titres).size, titres.join(" | ")).toBe(PAGES.length);
    expect(descriptions).not.toContain("la description du gabarit");
    expect(new Set(descriptions).size, descriptions.join(" | ")).toBe(PAGES.length);
    // Le contact n'a plus de formulaire : sa description ne l'annonce plus.
    expect(PAGE_CONTACT.description).not.toMatch(/formulaire/i);
    expect(PAGE_CONTACT.description).toContain("48h");
  });
});

// ── La boîte à outils ───────────────────────────────────────────────────────

describe("la boîte à outils", () => {
  it("dit tout ce que la page disait, au vous", () => {
    rendre(<BoiteAOutils />, "/boite-a-outils");
    const page = texte();
    const b = BOITE_A_OUTILS;

    const blocs = [
      ...b.ressources.flatMap((r) => [r.titre, ...r.paragraphes, ...(r.surtitre ? [r.surtitre] : [])]),
      ...FORMULAIRES.checklist.titre,
      ...FORMULAIRES.lexique.titre,
    ];
    // Règle 1 : une collecte vide ferait passer la boucle sans rien vérifier.
    expect(blocs.length).toBeGreaterThan(20);
    const tutoyes = blocs.filter((bloc) => bloc.texteAuVous !== undefined);
    expect(tutoyes.length).toBeGreaterThan(8);
    for (const bloc of blocs) {
      const attendu = bloc.texteAuVous ?? bloc.texte;
      expect(page, `la page ne dit plus : « ${attendu} »`).toContain(espaces(attendu));
    }
    // Le tutoiement du relevé n'est plus affiché.
    for (const bloc of tutoyes) {
      expect(page, `la page tutoie : « ${bloc.texte} »`).not.toContain(espaces(bloc.texte));
    }

    for (const phrase of [
      b.ouverture.titre,
      b.ouverture.corps,
      b.decouvrir.titre,
      ...b.decouvrir.points,
      b.decouvrir.suite,
      b.titreDesRessources,
    ]) {
      expect(page, `la page ne dit plus : « ${phrase} »`).toContain(espaces(phrase));
    }
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(b.ouverture.titre);
    expect(document.title).toBe(b.entete.titreOnglet?.texte);
  });

  it("trois ressources : deux documents demandés par courriel, un article lu sur le blog", () => {
    rendre(<BoiteAOutils />, "/boite-a-outils");

    const cartes = Array.from(document.querySelectorAll<HTMLElement>("article.res-ressource"));
    expect(cartes).toHaveLength(BOITE_A_OUTILS.ressources.length);
    expect(cartes).toHaveLength(3);

    // Les deux documents : UN lien par carte, un courriel dont l'objet nomme
    // la ressource — et pas la même pour les deux.
    const [checklist, lexique, article] = cartes;
    const lienChecklist = within(checklist).getAllByRole("link");
    const lienLexique = within(lexique).getAllByRole("link");
    expect(lienChecklist).toHaveLength(1);
    expect(lienLexique).toHaveLength(1);
    expect(lienChecklist[0]).toHaveTextContent(PAGE_BOITE_A_OUTILS.recevoir);
    expect(lienLexique[0]).toHaveTextContent("Recevoir par e-mail");
    expect(objetDuCourriel(lienChecklist[0])).toMatch(/checklist/i);
    expect(objetDuCourriel(lienChecklist[0])).toContain("micro-entreprise");
    expect(objetDuCourriel(lienLexique[0])).toMatch(/lexique/i);
    // Deux boutons au même libellé : leur nom accessible les distingue.
    expect(lienChecklist[0].textContent).not.toBe(lienLexique[0].textContent);

    // L'article : vers le blog de la plateforme, pas vers l'ancien site.
    const lienArticle = within(article).getAllByRole("link");
    expect(lienArticle).toHaveLength(1);
    expect(lienArticle[0]).toHaveAttribute("href", `/blog/${VIABLE.slug}`);
    expect(lienArticle[0]).toHaveAttribute("href", "/blog/idee-business-viable");
    expect(lienArticle[0]).toHaveTextContent("Lire la suite de l'article");

    // La passerelle de la boîte à outils : les formations.
    expect(document.querySelector(".acc-fin a")).toHaveAttribute("href", "/formations");
  });
});

// ── Le blog ─────────────────────────────────────────────────────────────────

describe("la liste du blog", () => {
  function filtres(): HTMLElement {
    return screen.getByRole("group", { name: BLOG.filtres.nom });
  }

  function filtre(nom: string): HTMLButtonElement {
    return within(filtres()).getByRole("button", { name: nom }) as HTMLButtonElement;
  }

  function cartes(): HTMLElement[] {
    return Array.from(document.querySelectorAll<HTMLElement>("article.res-article"));
  }

  it("la liste fermée des thèmes : création, statuts, étude de marché, financement, productivité", () => {
    expect(THEMES.map((theme) => theme.libelle)).toEqual([
      "Création",
      "Statuts",
      "Étude de marché",
      "Financement",
      "Productivité",
    ]);
    expect(new Set(THEMES.map((theme) => theme.slug)).size).toBe(5);
  });

  it("« Tous » par défaut ; un thème sans article est affiché désactivé, jamais masqué", () => {
    rendre(<Blog />, "/blog");

    const boutons = within(filtres()).getAllByRole("button");
    expect(boutons.map((b) => b.textContent)).toEqual(["Tous", ...THEMES.map((t) => t.libelle)]);
    expect(filtre("Tous")).toHaveAttribute("aria-pressed", "true");
    for (const theme of THEMES) {
      const bouton = filtre(theme.libelle);
      const vide = !ARTICLES.some((article) => article.theme === theme.slug);
      expect(bouton.disabled, theme.libelle).toBe(vide);
      expect(bouton).toHaveAttribute("aria-pressed", "false");
    }
    // Aujourd'hui : un seul thème a un article.
    expect(within(filtres()).getAllByRole("button").filter((b) => !(b as HTMLButtonElement).disabled)).toHaveLength(2);
    // Aucune promesse d'article à venir.
    expect(texte()).not.toMatch(/à venir|bientôt|prochainement|en préparation/i);
  });

  it("un seul article : mis en avant, avec son thème, son titre, son chapô court et son temps de lecture", () => {
    rendre(<Blog />, "/blog");

    expect(ARTICLES).toHaveLength(1);
    expect(cartes()).toHaveLength(1);
    const carte = cartes()[0];
    expect(carte.closest("li")).toHaveClass("res-article-rang-une");
    expect(texteDe(carte)).toContain("Étude de marché");
    expect(within(carte).getByRole("heading", { level: 3 })).toHaveTextContent(VIABLE.titre);
    expect(texteDe(carte)).toContain(VIABLE.sousTitre);
    expect(texteDe(carte)).toContain(VIABLE.accroche);
    expect(texteDe(carte)).toContain(`${VIABLE.tempsDeLecture} min de lecture`);
    // UN lien par carte, porté par le titre.
    const liens = within(carte).getAllByRole("link");
    expect(liens).toHaveLength(1);
    expect(liens[0]).toHaveAttribute("href", "/blog/idee-business-viable");
    expect(liens[0]).toHaveTextContent(VIABLE.titre);
    expect(screen.getByRole("status")).toHaveTextContent("1 article");
  });

  it("un article s'ajoute par une entrée de liste : la carte, le filtre et le compte suivent", async () => {
    await avecUnSecondArticle(() => {
      rendre(<Blog />, "/blog");

      expect(cartes()).toHaveLength(2);
      expect(screen.getByRole("status")).toHaveTextContent("2 articles");
      // Le premier de la liste reste à la une, le second ne l'est pas.
      expect(cartes()[0].closest("li")).toHaveClass("res-article-rang-une");
      expect(cartes()[1].closest("li")).not.toHaveClass("res-article-rang-une");

      // Le thème « Financement » n'est plus vide : son filtre répond.
      const financement = filtre("Financement");
      expect(financement.disabled).toBe(false);
      fireEvent.click(financement);
      expect(financement).toHaveAttribute("aria-pressed", "true");
      expect(filtre("Tous")).toHaveAttribute("aria-pressed", "false");
      expect(cartes()).toHaveLength(1);
      expect(texteDe(cartes()[0])).toContain(ESSAI.titre);
      expect(texteDe(cartes()[0])).toContain("La première phrase du chapô d'essai.");
      expect(texteDe(cartes()[0])).not.toContain("Puis une seconde phrase.");
      expect(screen.getByRole("status")).toHaveTextContent("1 article");
      // L'article filtré passe à la une : jamais de grille clairsemée.
      expect(cartes()[0].closest("li")).toHaveClass("res-article-rang-une");

      // Une bascule : un second clic revient à « Tous ».
      fireEvent.click(financement);
      expect(financement).toHaveAttribute("aria-pressed", "false");
      expect(filtre("Tous")).toHaveAttribute("aria-pressed", "true");
      expect(cartes()).toHaveLength(2);
    });
    // Contre-épreuve : l'article retiré, la page revient à un seul.
    cleanup();
    rendre(<Blog />, "/blog");
    expect(cartes()).toHaveLength(1);
    expect(filtre("Financement").disabled).toBe(true);
  });

  it("l'adresse présélectionne un thème qui a des articles, et ignore le reste", () => {
    rendre(<Blog />, `/blog?theme=${VIABLE.theme}`);
    expect(filtre("Étude de marché")).toHaveAttribute("aria-pressed", "true");
    expect(filtre("Tous")).toHaveAttribute("aria-pressed", "false");
    expect(cartes()).toHaveLength(1);
    cleanup();

    for (const adresse of ["/blog?theme=financement", "/blog?theme=nimporte", "/blog?theme="]) {
      rendre(<Blog />, adresse);
      expect(filtre("Tous"), adresse).toHaveAttribute("aria-pressed", "true");
      expect(cartes(), adresse).toHaveLength(1);
      cleanup();
    }
  });
});

describe("le temps de lecture est calculé, pas écrit", () => {
  it("il se déduit du nombre de mots de l'article", () => {
    const mots = compterLesMots(texteDeLArticle(VIABLE));
    // Règle 1 : un article sans texte donnerait « 1 min » quoi qu'il arrive.
    expect(mots).toBeGreaterThan(400);
    expect(VIABLE.nombreDeMots).toBe(mots);
    expect(VIABLE.tempsDeLecture).toBe(Math.ceil(mots / MOTS_PAR_MINUTE));
    expect(VIABLE.tempsDeLecture).toBeGreaterThan(1);
  });

  it("contre-épreuve : il bouge quand le texte s'allonge, et ne vaut jamais zéro", () => {
    expect(minutesDeLecture(0)).toBe(1);
    expect(minutesDeLecture(1)).toBe(1);
    expect(minutesDeLecture(MOTS_PAR_MINUTE)).toBe(1);
    expect(minutesDeLecture(MOTS_PAR_MINUTE + 1)).toBe(2);
    expect(minutesDeLecture(5 * MOTS_PAR_MINUTE)).toBe(5);
    // L'article d'essai porte deux minutes de texte dans sa seule partie,
    // plus ses titres : trois minutes.
    expect(ESSAI.tempsDeLecture).toBe(3);
    // Un signe de ponctuation isolé par la typographie n'est pas un mot.
    expect(compterLesMots(["Est-ce viable ?", "Oui : c'est sûr !"])).toBe(5);
  });

  it("aucun temps de lecture n'est écrit dans la source des articles", () => {
    const code = sansCommentaires(source("contenuBlog.ts"));
    expect(code.length).toBeGreaterThan(2000);
    expect(code).not.toMatch(/tempsDeLecture\s*:\s*\d/);
    expect(code).not.toMatch(/\b\d+\s*min\b/);
  });

  it("le chapô court d'une carte est la première phrase du chapô", () => {
    expect(VIABLE.accroche).toBe(premierePhrase(ARTICLE_IDEE_BUSINESS_VIABLE.chapo.paragraphes[0]));
    expect(VIABLE.accroche.endsWith("la raison.")).toBe(true);
    expect(premierePhrase("Une phrase. Une autre.")).toBe("Une phrase.");
    expect(premierePhrase("Vraiment ? Oui.")).toBe("Vraiment ?");
    expect(premierePhrase("Sans point final")).toBe("Sans point final");
  });
});

// ── La page d'un article ────────────────────────────────────────────────────

describe("la page d'un article", () => {
  function donneesStructurees(): Record<string, unknown> {
    const balises = document.querySelectorAll('script[type="application/ld+json"]');
    expect(balises).toHaveLength(1);
    return JSON.parse(balises[0].textContent ?? "") as Record<string, unknown>;
  }

  it("l'article réutilise le texte relevé, sans le recopier", () => {
    const releve = ARTICLE_IDEE_BUSINESS_VIABLE;
    expect(VIABLE.slug).toBe("idee-business-viable");
    expect(VIABLE.titre).toBe(releve.titre);
    expect(VIABLE.sections).toBe(releve.sections);
    expect(VIABLE.chapo).toBe(releve.chapo);
    expect(VIABLE.conclusion).toBe(releve.conclusion);
    expect(THEMES.map((theme) => theme.slug)).toContain(VIABLE.theme);
    expect(VIABLE.publieLe).toBeNull();
    // Le texte de l'article n'est pas dans `contenuBlog.ts`.
    expect(source("contenuBlog.ts")).not.toContain("Maya adore");
  });

  it("dit tout ce que l'article disait, dans une mise en page de lecture", async () => {
    await rendreLArticle(VIABLE.slug);
    const page = texte();

    const phrases = texteDeLArticle(VIABLE);
    // Règle 1 : une collecte vide ferait passer la boucle sans rien vérifier.
    expect(phrases.length).toBeGreaterThan(50);
    for (const phrase of phrases) {
      expect(page, `l'article ne dit plus : « ${phrase} »`).toContain(espaces(phrase));
    }
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(VIABLE.titre);
    expect(document.title).toBe(VIABLE.entete.titreOnglet);

    // Le fil d'Ariane : Blog › thème › titre, la page courante sans lien.
    const fil = screen.getByRole("navigation", { name: PAGE_ARTICLE.filDAriane });
    const etapes = Array.from(fil.querySelectorAll("li"));
    expect(etapes.map((e) => e.textContent)).toEqual(["Blog", "Étude de marché", VIABLE.titre]);
    expect(within(fil).getAllByRole("link").map((a) => a.getAttribute("href"))).toEqual([
      "/blog",
      "/blog?theme=etude-de-marche",
    ]);
    expect(etapes[2]).toHaveAttribute("aria-current", "page");

    // Le temps de lecture, calculé ; aucune date tant qu'elle est inconnue.
    expect(texteDe(document.querySelector(".res-meta"))).toContain(`${VIABLE.tempsDeLecture} min de lecture`);
    expect(document.querySelector("time")).toBeNull();
    expect(page).not.toContain(PAGE_ARTICLE.publieLe);

    // Le sommaire : une ancre par partie, plus la conclusion, vers un titre
    // qui EXISTE et qui porte le même texte.
    const sommaire = screen.getByRole("navigation", { name: PAGE_ARTICLE.sommaire });
    const ancres = within(sommaire).getAllByRole("link");
    expect(ancres).toHaveLength(VIABLE.sections.length + 1);
    expect(ancres.map((a) => a.textContent)).toEqual([
      ...VIABLE.sections.map((section) => section.intertitre),
      VIABLE.conclusion.intertitre,
    ]);
    for (const ancre of ancres) {
      const cible = document.querySelector(ancre.getAttribute("href") as string);
      expect(cible, ancre.textContent ?? "").not.toBeNull();
      expect(cible?.tagName).toBe("H2");
      expect(cible?.textContent).toBe(ancre.textContent);
    }

    // Les encadrés : autant de « Demandez-vous » et d'« Exemple » que le
    // texte en porte, chacun avec son amorce — c'est elle qui les distingue.
    const elements = VIABLE.sections.flatMap((section) => [
      ...section.elements,
      ...(section.sousSections ?? []).flatMap((sous) => sous.elements),
    ]);
    const questions = elements.filter((e) => e.genre === "question");
    const exemples = elements.filter((e) => e.genre === "exemple");
    expect(questions).toHaveLength(4);
    expect(exemples).toHaveLength(4);
    const encadresQuestion = Array.from(document.querySelectorAll(".res-encadre-question"));
    const encadresExemple = Array.from(document.querySelectorAll(".res-encadre-exemple"));
    expect(encadresQuestion).toHaveLength(questions.length);
    expect(encadresExemple).toHaveLength(exemples.length);
    for (const encadre of encadresQuestion) expect(encadre).toHaveTextContent("Demandez-vous :");
    for (const encadre of encadresExemple) expect(encadre).toHaveTextContent("Exemple :");
    // Les listes sont de vraies listes.
    const listes = [...elements, ...VIABLE.conclusion.elements].filter((e) => e.genre === "liste");
    expect(document.querySelectorAll("ul.res-liste")).toHaveLength(listes.length);
    expect(listes.length).toBeGreaterThanOrEqual(3);
    // La signature.
    expect(document.querySelector(".res-signature")).toHaveTextContent(VIABLE.conclusion.signature);
  });

  it("finit par la boîte à outils, puis par la passerelle vers l'étude de marché", async () => {
    await rendreLArticle(VIABLE.slug);

    const bonus = document.querySelector(".res-bonus") as HTMLElement;
    expect(texteDe(bonus)).toContain(ARTICLE_IDEE_BUSINESS_VIABLE.appel.titre);
    expect(texteDe(bonus)).toContain(ARTICLE_IDEE_BUSINESS_VIABLE.appel.document);
    expect(texteDe(bonus)).toContain(ARTICLE_IDEE_BUSINESS_VIABLE.appel.corps);
    expect(within(bonus).getByRole("link")).toHaveAttribute("href", "/boite-a-outils");

    const passerelle = document.querySelector(".acc-fin") as HTMLElement;
    expect(within(passerelle).getByRole("link")).toHaveAttribute("href", "/etudes");
    expect(texteDe(passerelle)).toMatch(/étude de marché/i);
    expect(bonus.compareDocumentPosition(passerelle) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("déclare des données structurées Article, sans date inventée", async () => {
    await rendreLArticle(VIABLE.slug);

    const donnees = donneesStructurees();
    expect(donnees["@context"]).toBe("https://schema.org");
    expect(donnees["@type"]).toBe("Article");
    expect(donnees.headline).toBe(VIABLE.titre);
    expect(donnees.articleSection).toBe("Étude de marché");
    expect(donnees.wordCount).toBe(VIABLE.nombreDeMots);
    expect(donnees.timeRequired).toBe(`PT${VIABLE.tempsDeLecture}M`);
    expect(donnees.url).toBe(`${window.location.origin}/blog/idee-business-viable`);
    expect(donnees.author).toEqual({ "@type": "Person", name: VIABLE.conclusion.signature });
    // Aucune date, sous aucun nom : ni publication, ni modification.
    expect(Object.keys(donnees).filter((cle) => /date/i.test(cle))).toEqual([]);
    expect(JSON.stringify(donnees)).not.toMatch(/\d{4}-\d{2}-\d{2}/);
  });

  it("contre-épreuve : un article daté affiche et déclare SA date", async () => {
    await avecUnSecondArticle(async () => {
      await rendreLArticle(ESSAI.slug);

      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(ESSAI.titre);
      const date = document.querySelector("time");
      expect(date).toHaveAttribute("datetime", "2026-03-09");
      expect(texteDe(date)).toBe("9 mars 2026");
      expect(donneesStructurees().datePublished).toBe("2026-03-09");
      expect(donneesStructurees().headline).toBe(ESSAI.titre);
      expect(texteDe(document.querySelector(".res-meta"))).toContain("3 min de lecture");
      // Le fil d'Ariane mène à SON thème.
      const fil = screen.getByRole("navigation", { name: PAGE_ARTICLE.filDAriane });
      expect(within(fil).getByRole("link", { name: "Financement" })).toHaveAttribute(
        "href",
        "/blog?theme=financement",
      );
    });
  });

  it("un slug inconnu rend « article introuvable », avec retour au blog", async () => {
    await rendreLArticle("nulle-part");

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Article introuvable.");
    expect(document.title).toBe(PAGE_ARTICLE.introuvable.titreOnglet);
    expect(screen.getByRole("link", { name: /Retour au blog/ })).toHaveAttribute("href", "/blog");
    // Ni article, ni données structurées d'un article qui n'existe pas.
    expect(document.querySelector('script[type="application/ld+json"]')).toBeNull();
    expect(document.querySelector(".res-prose")).toBeNull();
    expect(texte()).not.toContain(VIABLE.titre);
  });
});

// ── Le contact ──────────────────────────────────────────────────────────────

describe("la page de contact", () => {
  it("garde l'accroche et le délai de réponse relevés", () => {
    rendre(<Contact />, "/contact");
    const page = texte();

    for (const phrase of [
      CONTACT.accroche.titre,
      CONTACT.accroche.corps,
      FORMULAIRES.contact.titre[0].texte,
      COORDONNEES.delaiDeReponse.surLaPage,
      COORDONNEES.delaiDeReponse.dansLaDescription,
    ]) {
      expect(page, `la page ne dit plus : « ${phrase} »`).toContain(espaces(phrase));
    }
    expect(page).toMatch(/48 heures/);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(CONTACT.accroche.titre);
  });

  it("propose les moyens qui fonctionnent : écrire, prendre rendez-vous, les réseaux", () => {
    rendre(<Contact />, "/contact");

    // Écrire : un courriel à l'adresse de contact, objet prérempli, et
    // l'adresse en toutes lettres.
    const ecrire = screen.getByRole("link", { name: PAGE_CONTACT.moyens.ecrire.bouton });
    expect(objetDuCourriel(ecrire)).toBe(PAGE_CONTACT.moyens.ecrire.objet);
    expect(objetDuCourriel(ecrire).length).toBeGreaterThan(5);
    expect(texte()).toContain("contact@evkha.fr");

    // Rendez-vous : l'agenda en ligne.
    const rendezVous = screen.getByRole("link", { name: PAGE_CONTACT.moyens.rendezVous.bouton });
    expect(rendezVous).toHaveAttribute("href", COORDONNEES.rendezVous);
    expect(rendezVous.getAttribute("href")).toMatch(/^https:\/\/calendly\.com\//);

    // Les réseaux relevés, tous, chacun vers son adresse.
    expect(COORDONNEES.reseaux.length).toBeGreaterThanOrEqual(3);
    for (const reseau of COORDONNEES.reseaux) {
      expect(within(principal()).getByRole("link", { name: reseau.libelle })).toHaveAttribute("href", reseau.lien);
    }
    // Ni téléphone, ni horaires, ni adresse postale : le relevé n'en donne pas.
    expect(COORDONNEES.telephone).toBeNull();
    expect(principal().querySelector('a[href^="tel:"]')).toBeNull();
  });

  it("oriente vers les études, les packs, les formations et les partenaires avant d'écrire", () => {
    rendre(<Contact />, "/contact");

    const aide = document.getElementById("orientation") as HTMLElement;
    expect(within(aide).getAllByRole("link").map((a) => a.getAttribute("href"))).toEqual([
      "/etudes",
      "/packs",
      "/formations",
      "/partenaires",
    ]);
    expect(texteDe(aide)).not.toMatch(MONTANT_ECRIT);
  });
});

// ── Swapn ───────────────────────────────────────────────────────────────────

describe("la page du partenaire Swapn", () => {
  it("affiche le titre relevé, en écriture courante, et le logo à sa place réservée", () => {
    rendre(<Swapn />, "/swapn");

    const titre = screen.getByRole("heading", { level: 1 });
    expect(espaces(titre.textContent ?? "").toLocaleUpperCase("fr")).toBe(SWAPN.titre.join(" "));
    const logo = screen.getByRole("img", { name: "Swapn" });
    expect(logo).toHaveAttribute("src", "/accueil/logo-swapn.webp");
    expect(logo).toHaveAttribute("width", "404");
    expect(logo).toHaveAttribute("height", "402");
    expect(logo).toHaveClass("res-logo");
  });

  it("présente l'offre comme celle DU PARTENAIRE : ses promesses ne sortent pas de la figure attribuée", () => {
    rendre(<Swapn />, "/swapn");

    const figure = document.querySelector("figure.res-offre") as HTMLElement;
    const offre = SWAPN.texteLuDansLeVisuel;
    const phrases = [
      offre.accroche,
      offre.mention,
      ...offre.offre,
      ...offre.arguments.flatMap((argument) => [argument.titre, argument.corps]),
    ];
    expect(phrases.length).toBeGreaterThanOrEqual(11);
    for (const phrase of phrases) {
      expect(texteDe(figure), `l'offre ne dit plus : « ${phrase} »`).toContain(espaces(phrase));
    }
    // L'attribution : elle ouvre la carte, et la légende dit qui s'engage.
    expect(texteDe(figure)).toContain("Selon Swapn");
    expect(texteDe(figure.querySelector("figcaption"))).toMatch(/Swapn/);
    expect(texteDe(figure.querySelector("figcaption"))).toMatch(/non un engagement d'EVKHA/);

    // Hors de la figure, la page ne reprend à son compte aucune des trois
    // promesses du partenaire.
    const horsFigure = espaces(
      Array.from(principal().children)
        .map((bloc) => {
          const copie = bloc.cloneNode(true) as HTMLElement;
          copie.querySelector("figure.res-offre")?.remove();
          return copie.textContent ?? "";
        })
        .join(" "),
    );
    expect(horsFigure.length).toBeGreaterThan(200);
    expect(horsFigure).not.toMatch(/mieux noté/i);
    expect(horsFigure).not.toMatch(/24\s?h/i);
    expect(horsFigure).not.toMatch(MONTANT_ECRIT);
    // Contre-épreuve : dans la figure, elles y sont.
    expect(texteDe(figure)).toMatch(/mieux noté/i);
    expect(texteDe(figure)).toMatch(/24\s?h/i);
    expect(texteDe(figure)).toContain("0 €");
  });

  it("la mise en relation est un courriel à EVKHA, objet « Mise en relation avec Swapn »", () => {
    rendre(<Swapn />, "/swapn");

    const boutons = screen.getAllByRole("link", { name: PAGE_SWAPN.relation.bouton });
    expect(boutons.length).toBeGreaterThanOrEqual(1);
    for (const bouton of boutons) {
      expect(objetDuCourriel(bouton)).toBe("Mise en relation avec Swapn");
    }
    // Les deux phrases que le site adressait au visiteur dans son formulaire.
    const relation = document.getElementById("mise-en-relation") as HTMLElement;
    for (const nom of ["demande", "message"]) {
      const champ = FORMULAIRES.swapn.champs.find((c) => c.nom === nom);
      expect(champ, nom).toBeDefined();
      expect(texteDe(relation)).toContain(champ?.libelle ?? "");
    }
    // La page dit à qui les coordonnées seront transmises.
    expect(texteDe(relation)).toMatch(/transmettre votre nom et votre adresse e-mail à Swapn/);
  });
});

// ── La classe du défaut : un montant, une adresse de l'ancien site ──────────

describe("les sources du lot", () => {
  for (const fichier of ["Ressources.tsx", "Blog.tsx", "contenuBlog.ts"]) {
    it(`${fichier} n'écrit aucun montant`, () => {
      const code = sansCommentaires(source(fichier));
      // Règle 1 : un fichier vide ou introuvable ne « passe » pas.
      expect(code.length).toBeGreaterThan(2000);
      expect(code.match(new RegExp(MONTANT_ECRIT.source, "gi")) ?? []).toEqual([]);
    });
  }

  for (const fichier of ["Ressources.tsx", "Blog.tsx", "contenuBlog.ts", "Ressources.css"]) {
    it(`${fichier} ne pointe vers aucune adresse de l'ancien site`, () => {
      // Commentaires COMPRIS : une adresse en commentaire reviendrait au
      // prochain copier-coller.
      const brut = source(fichier);
      expect(brut.length).toBeGreaterThan(2000);
      expect(brut.match(new RegExp(ANCIEN_SITE.source, "gi")) ?? []).toEqual([]);
      expect(brut).not.toMatch(/https?:\/\/(?!schema\.org)/);
    });
  }

  it("aucun texte affiché n'est écrit dans les pages : elles lisent leurs fichiers de contenu", () => {
    for (const fichier of ["Ressources.tsx", "Blog.tsx"]) {
      const code = sansCommentaires(source(fichier));
      const enDur = code.match(new RegExp(TEXTE_EN_DUR.source, "g")) ?? [];
      expect(enDur, fichier).toEqual([]);
    }
  });

  it("contre-épreuve : les détecteurs voient un montant, une adresse du CDN et un texte en dur", () => {
    for (const faute of ["dès 89 €", "149€", "1 490 € TTC", "prix: 185 euros", "0 €"]) {
      expect(faute, faute).toMatch(MONTANT_ECRIT);
    }
    for (const juste of ["sous 48 heures", "100 % gratuit", "10 étapes", "le signe €", "4 questions"]) {
      expect(juste, juste).not.toMatch(MONTANT_ECRIT);
    }
    for (const faute of [
      "https://d1yei2z3i6k35z.cloudfront.net/9890127/68f603ab0d9dd_SWAPN.png",
      "https://www.evkha.fr/boite-a-outil",
      "https://evkha.fr/contacts",
    ]) {
      expect(faute, faute).toMatch(ANCIEN_SITE);
    }
    for (const juste of ["mailto:contact@evkha.fr?subject=Bonjour", "/boite-a-outils", "/accueil/logo-swapn.webp"]) {
      expect(juste, juste).not.toMatch(ANCIEN_SITE);
    }
    expect("<h2>Un titre en dur</h2>").toMatch(TEXTE_EN_DUR);
    expect("<p>\n  Des mots\n</p>").toMatch(TEXTE_EN_DUR);
    expect("<h2>{a.titre}</h2>").not.toMatch(TEXTE_EN_DUR);
    expect("liste.filter((a) => a.theme === theme); return ( <div>").not.toMatch(TEXTE_EN_DUR);
  });
});

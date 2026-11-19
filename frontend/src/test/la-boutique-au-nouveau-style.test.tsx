/** La boutique et le tunnel d'achat au nouveau langage visuel : la forme a
 * changé, pas ce que les pages disent ni ce qu'elles font.
 *
 * Refonte du 19/11/2026. Le catalogue (`Boutique`), la fiche (`FicheProduit`)
 * et le retour de paiement (`RetourBoutique`) sont passés au socle des pages
 * refondues ; la page d'achat (`Acheter`) et son retour (`RetourPaiement`)
 * n'ont changé que d'en-tête et de pied. L'ancien menu (`MenuSite`) renvoyait
 * vers l'ancien site, logo compris.
 *
 * Ce que ce fichier verrouille :
 *
 * 1. le catalogue et la fiche montent l'en-tête et le pied du SOCLE — mêmes
 *    rubriques que `contenuSite.NAVIGATION` —, un seul h1, des titres sans
 *    saut, un lien d'évitement qui vise le contenu ;
 * 2. les prix affichés sont ceux que l'API a rendus, et aucun montant n'est
 *    écrit dans les sources ;
 * 3. RIEN n'est affiché avant la réponse : ni prix, ni données structurées ;
 * 4. une panne est DITE, dans une région d'alerte, et ne se lit jamais comme
 *    un catalogue vide — y compris une réponse 200 sans la liste attendue ;
 * 5. un catalogue vide est dit, lui aussi, et ce n'est pas une alerte ;
 * 6. le JSON-LD de la fiche ne contient que ce que l'API a rendu : pas de
 *    note sans avis, pas de description vide, pas d'offre sans prix ;
 * 7. aucun lien vers l'ancien site dans les cinq pages — dans ce qu'elles
 *    rendent comme dans leurs sources ;
 * 8. la fiche se termine par la passerelle vers l'étude sur mesure
 *    (`/etudes`), sans prix ;
 * 9. le prix et l'achat restent à portée sans doubler le paiement : UN bouton
 *    ouvre le paiement, la barre du téléphone est un lien vers le panneau.
 *
 * Contre-épreuves (règle 6) : les détecteurs voient bien un montant et une
 * adresse de l'ancien site, et laissent passer l'adresse de contact ; une
 * fiche AVEC avis déclare sa note.
 *
 * ÉCRIT SANS ÊTRE JOUÉ : la consigne du lot interdisait de lancer `vitest`.
 * Ce fichier n'a donc pas encore été vu rouge contre le code d'avant ; tant
 * qu'il n'a pas tourné, il ne verrouille rien (règle 6). Contre le code
 * d'avant, les verrous 1, 6, 7 (le logo de `MenuSite`) et 8 doivent être
 * rouges.
 *
 * Le routeur est remplacé par un simulacre, comme dans
 * `un-achat-suit-le-compte-et-une-panne-n-est-pas-une-absence` : ces pages ne
 * lui demandent qu'un paramètre de route et des liens.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, render, screen, within } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NAVIGATION } from "../public/contenuSite";
import { server } from "./server";

const parametres = { slug: "foodtrucks", livrable: "etude-de-marche" };

vi.mock("@tanstack/react-router", () => ({
  useParams: () => parametres,
  useNavigate: () => () => undefined,
  Link: ({
    children,
    to,
    params,
    className,
  }: {
    children: React.ReactNode;
    to?: string;
    params?: { slug?: string };
    className?: string;
  }) => (
    <a href={(to ?? "#").replace("$slug", params?.slug ?? "")} className={className}>
      {children}
    </a>
  ),
}));

// Importées APRÈS le simulacre du routeur.
const { Boutique } = await import("../public/Boutique");
const { FicheProduit } = await import("../public/FicheProduit");
const { RetourBoutique } = await import("../public/RetourBoutique");
const { Acheter } = await import("../public/Acheter");
const { RetourPaiement } = await import("../public/RetourPaiement");

const ORIGINE = window.location.origin;
const PUBLIC = `${ORIGINE}/api/public`;

// ── Ce que le serveur rend ──────────────────────────────────────────────────
// Les formes sont celles de `catalogue.ts` (`ProduitResume`, `ProduitFiche`).

const FOODTRUCKS = {
  slug: "foodtrucks",
  titre: "Le marché des foodtrucks",
  theme: "Restauration",
  prix_cents: 8900,
  devise: "EUR",
  pages: 42,
  mise_a_jour: "2026-10-01",
  image: "",
  note: 0,
  nombre_d_avis: 0,
};

const COIFFURE = {
  slug: "salons-de-coiffure",
  titre: "Le marché des salons de coiffure",
  theme: "Beauté",
  prix_cents: 12950,
  devise: "EUR",
  pages: 38,
  mise_a_jour: "",
  image: "",
  note: 0,
  nombre_d_avis: 0,
};

const CATALOGUE = {
  produits: [FOODTRUCKS, COIFFURE],
  themes: ["Restauration", "Beauté"],
  avis: [],
};

const FICHE = {
  produit: {
    ...FOODTRUCKS,
    description: "Une étude déjà rédigée sur la restauration ambulante.",
    sommaire: ["Le marché", "Les acteurs"],
    apercu: null,
    editable: false,
    avis: [],
  },
  proches: [COIFFURE],
};

const AVIS = [
  {
    auteur: "Camille",
    qualite: "Restauratrice, Lyon",
    note: 5,
    texte: "Très utile pour mon dossier.",
    date: "2026-09-12",
  },
  {
    auteur: "Inès",
    qualite: "",
    note: 4,
    texte: "Des chiffres clairs.",
    date: "2026-08-02",
  },
];

const LIVRABLES = {
  livrables: [
    { slug: "etude-de-marche", libelle: "Étude de marché", type: "market_study", prix_cents: 14900 },
  ],
};

// ── Outils ──────────────────────────────────────────────────────────────────

/** Les espaces insécables, construites par leur code, jamais tapées. */
const INSECABLES = new RegExp(`[${String.fromCharCode(0xa0)}${String.fromCharCode(0x202f)}]`, "g");

function espaces(brut: string): string {
  return brut.replace(INSECABLES, " ");
}

function principal(): HTMLElement {
  return screen.getByRole("main");
}

/** Le texte du contenu principal, insécables ramenées à des espaces. */
function texte(): string {
  return espaces(principal().textContent ?? "");
}

/** Un montant en euros, où qu'il soit. */
const MONTANT = /\d[\d\s.,]*(?:€|euros?\b)/i;

/** Un prix AFFICHÉ : des chiffres, puis le signe. Le signe seul n'en est pas
 *  un — la promesse « Paiement unique » du catalogue porte un « € » décoratif. */
const PRIX_AFFICHE = /\d[\d\s.,]*€/;

/** Une adresse de l'ancien site ou de son CDN. L'adresse de contact
 *  (`contact@evkha.fr`) n'en est pas une. */
const ANCIEN_SITE = /cloudfront\.net|systeme\.io|www\.evkha\.fr|\/\/evkha\.fr|(?<!@)\bevkha\.fr\//i;

function sansCommentaires(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

function source(fichier: string): string {
  return readFileSync(join(process.cwd(), "src", "public", fichier), "utf-8");
}

const SOURCES = [
  "Boutique.tsx",
  "FicheProduit.tsx",
  "RetourBoutique.tsx",
  "Acheter.tsx",
  "RetourPaiement.tsx",
];

/** Un appel qui ne répond jamais : la page reste en attente. */
const muet = async () => {
  await delay("infinite");
  return new HttpResponse(null);
};

function servirLeCatalogue(reponse: () => Response | Promise<Response>) {
  server.use(http.get(`${PUBLIC}/boutique/`, reponse));
}

function servirLaFiche(reponse: () => Response | Promise<Response>) {
  server.use(http.get(`${PUBLIC}/boutique/foodtrucks/`, reponse));
}

function rendre(page: React.ReactElement, chemin: string) {
  window.history.pushState({}, "", chemin);
  return render(page);
}

async function rendreLeCatalogue(charge: object = CATALOGUE) {
  servirLeCatalogue(() => HttpResponse.json(charge));
  rendre(<Boutique />, "/boutique");
  await screen.findByRole("heading", { name: FOODTRUCKS.titre });
}

async function rendreLaFiche(charge: object = FICHE) {
  servirLaFiche(() => HttpResponse.json(charge));
  rendre(<FicheProduit />, "/boutique/foodtrucks");
  await screen.findByRole("heading", { level: 1, name: FOODTRUCKS.titre });
}

/** Le bloc JSON-LD de la page, ou `null` s'il n'y en a pas. */
function donneesStructurees(): Record<string, unknown> | null {
  const blocs = document.querySelectorAll('script[type="application/ld+json"]');
  expect(blocs.length).toBeLessThanOrEqual(1);
  const brut = blocs[0]?.textContent;
  return brut ? (JSON.parse(brut) as Record<string, unknown>) : null;
}

/** Les niveaux des titres du contenu, dans l'ordre du document. */
function niveaux(): number[] {
  return within(principal())
    .getAllByRole("heading")
    .map((titre) => Number(titre.tagName.slice(1)));
}

function sansSaut(liste: number[]): boolean {
  return liste.every((niveau, k) => k === 0 || niveau - liste[k - 1] <= 1);
}

/** Ce que le socle monte autour d'une page : la barre et ses rubriques, le
 *  pied, le lien d'évitement — et plus rien de l'ancien menu. */
function attendreLeSocle() {
  const barre = screen.getByRole("navigation", { name: "Principale" });
  expect(
    within(barre)
      .getAllByRole("button")
      .map((bouton) => bouton.textContent),
  ).toEqual(NAVIGATION.map((rubrique) => rubrique.libelle));
  expect(screen.getByRole("banner")).toContainElement(barre);
  expect(screen.getByRole("contentinfo")).toBeInTheDocument();
  expect(principal().id).not.toBe("");
  expect(screen.getByRole("link", { name: "Aller au contenu" })).toHaveAttribute(
    "href",
    `#${principal().id}`,
  );
  expect(document.querySelector(".pp-menu")).toBeNull();
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  window.history.pushState({}, "", "/");
});

// ── 1. Le socle ─────────────────────────────────────────────────────────────

describe("la boutique et la fiche montent l'en-tête et le pied du socle", () => {
  it("le catalogue : barre du socle, pied, un seul h1, titres sans saut", async () => {
    await rendreLeCatalogue();
    attendreLeSocle();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(niveaux()[0]).toBe(1);
    expect(sansSaut(niveaux())).toBe(true);
    // La racine est celle des pages refondues, plus celle de l'ancienne charte.
    expect(document.querySelector(".acc.bou")).not.toBeNull();
    expect(document.querySelector(".pp")).toBeNull();
    expect(document.title).toMatch(/EVKHA/);
  });

  it("la fiche : barre du socle, pied, un seul h1 — le titre de l'étude —, titres sans saut", async () => {
    await rendreLaFiche();
    attendreLeSocle();
    const titres = screen.getAllByRole("heading", { level: 1 });
    expect(titres).toHaveLength(1);
    expect(titres[0]).toHaveTextContent(FOODTRUCKS.titre);
    expect(sansSaut(niveaux())).toBe(true);
    expect(document.querySelector(".acc.bou")).not.toBeNull();
    expect(document.querySelector(".pp")).toBeNull();
    // Le titre d'onglet est celui de l'étude.
    expect(document.title).toContain(FOODTRUCKS.titre);
  });

  it("contre-épreuve : le détecteur de saut voit un titre qui en enjambe un autre", () => {
    expect(sansSaut([1, 2, 3, 2, 3])).toBe(true);
    expect(sansSaut([1, 3])).toBe(false);
  });
});

// ── 2. Les prix ─────────────────────────────────────────────────────────────

describe("les prix sont ceux de l'API", () => {
  it("le catalogue affiche le prix de chaque étude, et le plus bas dans l'ouverture", async () => {
    await rendreLeCatalogue();
    const cartes = within(principal()).getAllByRole("article");
    expect(cartes).toHaveLength(2);
    expect(espaces(cartes[0].textContent ?? "")).toContain("89 €");
    expect(espaces(cartes[1].textContent ?? "")).toContain("129,50 €");
    // Chaque carte mène à SA fiche, par son titre.
    expect(within(cartes[0]).getByRole("link", { name: FOODTRUCKS.titre })).toHaveAttribute(
      "href",
      "/boutique/foodtrucks",
    );
    expect(within(cartes[1]).getByRole("link", { name: COIFFURE.titre })).toHaveAttribute(
      "href",
      "/boutique/salons-de-coiffure",
    );
    // Le plancher : le plus petit des deux, calculé — pas écrit.
    expect(texte()).toContain("à partir de 89 € TTC");
    // Le prix de chaque carte, lu dans son emplacement : deux cartes, deux
    // prix, ceux de l'API. (Le texte mis bout à bout collerait la date de
    // mise à jour au montant : « 2026 » puis « 89 € ».)
    const prixDesCartes = Array.from(principal().querySelectorAll(".bou-carte-prix")).map((p) =>
      espaces(p.textContent ?? ""),
    );
    expect(prixDesCartes).toEqual(["89 €", "129,50 €"]);
  });

  it("un tarif qui change au serveur change sur la page", async () => {
    await rendreLeCatalogue({
      ...CATALOGUE,
      produits: [{ ...FOODTRUCKS, prix_cents: 9900 }, COIFFURE],
    });
    expect(texte()).toContain("à partir de 99 € TTC");
    expect(texte()).not.toContain("89 €");
  });

  it("la fiche affiche le prix de l'étude dans le panneau, sur le bouton et dans la barre", async () => {
    await rendreLaFiche();
    const panneau = screen.getByRole("complementary", { name: /Acheter cette étude/ });
    expect(espaces(panneau.textContent ?? "")).toContain("89 €");
    expect(
      espaces(screen.getByRole("button", { name: /Acheter/ }).textContent ?? ""),
    ).toContain("89 €");
    // Jamais d'espace ordinaire avant le signe : la mise en forme est celle
    // d'`Intl`, qui pose une insécable.
    expect(principal().textContent ?? "").not.toMatch(/\d €/);
  });

  it("aucun montant n'est écrit dans les sources des pages", () => {
    for (const fichier of SOURCES) {
      expect(sansCommentaires(source(fichier)), fichier).not.toMatch(MONTANT);
    }
    // Contre-épreuve : le détecteur voit un montant, sous ses formes.
    expect("dès 89 €").toMatch(MONTANT);
    expect("129,50€").toMatch(MONTANT);
    expect("quatre-vingt-neuf, soit 89 euros").toMatch(MONTANT);
    expect('signe: "€"').not.toMatch(MONTANT);
    expect("22 chapitres par étude").not.toMatch(MONTANT);
  });
});

// ── 3. Rien avant la réponse ────────────────────────────────────────────────

describe("rien n'est affiché avant la réponse", () => {
  it("le catalogue attend : ni prix, ni carte, ni alerte remplie", () => {
    servirLeCatalogue(muet);
    rendre(<Boutique />, "/boutique");
    expect(within(principal()).getByRole("status")).toHaveTextContent(/Chargement du catalogue/);
    expect(texte()).not.toMatch(PRIX_AFFICHE);
    expect(texte()).not.toMatch(/à partir de/);
    expect(within(principal()).queryAllByRole("article")).toEqual([]);
    expect(within(principal()).getByRole("alert")).toBeEmptyDOMElement();
    expect(texte()).not.toMatch(/Aucune étude/);
  });

  it("la fiche attend : ni prix, ni bouton d'achat, ni données structurées", () => {
    servirLaFiche(muet);
    rendre(<FicheProduit />, "/boutique/foodtrucks");
    expect(within(principal()).getByRole("status")).toHaveTextContent(/Chargement/);
    expect(texte()).not.toMatch(PRIX_AFFICHE);
    expect(screen.queryByRole("button", { name: /Acheter/ })).toBeNull();
    expect(donneesStructurees()).toBeNull();
    // L'en-tête et le pied, eux, n'attendent rien.
    attendreLeSocle();
  });
});

// ── 4 et 5. Une panne est dite, un catalogue vide aussi ─────────────────────

describe("une panne est dite, jamais lue comme un vide", () => {
  it("catalogue, 500 : l'alerte le dit, avec l'adresse de contact — et pas « aucune étude »", async () => {
    servirLeCatalogue(() => new HttpResponse("panne", { status: 500 }));
    rendre(<Boutique />, "/boutique");
    const alerte = within(principal()).getByRole("alert");
    await within(alerte).findByText(/momentanément indisponible/);
    expect(within(alerte).getByRole("link", { name: "contact@evkha.fr" })).toHaveAttribute(
      "href",
      "mailto:contact@evkha.fr",
    );
    expect(texte()).not.toMatch(/Aucune étude/);
    expect(texte()).not.toMatch(PRIX_AFFICHE);
    expect(within(principal()).queryByRole("status")).toBeNull();
  });

  it("catalogue, 200 sans la liste des produits : une panne, pas un catalogue vide", async () => {
    servirLeCatalogue(() => HttpResponse.json({}));
    rendre(<Boutique />, "/boutique");
    await within(within(principal()).getByRole("alert")).findByText(/momentanément indisponible/);
    expect(texte()).not.toMatch(/Aucune étude/);
  });

  it("catalogue vide : la page le dit, et ce n'est pas une alerte", async () => {
    servirLeCatalogue(() => HttpResponse.json({ produits: [], themes: [], avis: [] }));
    rendre(<Boutique />, "/boutique");
    expect(await screen.findByText(/Aucune étude n'est disponible pour le moment/)).toBeInTheDocument();
    expect(within(principal()).getByRole("alert")).toBeEmptyDOMElement();
    expect(texte()).not.toMatch(/momentanément indisponible/);
    expect(texte()).not.toMatch(PRIX_AFFICHE);
    expect(within(principal()).queryAllByRole("article")).toEqual([]);
  });

  it("fiche, 500 : une panne dite, un seul h1, aucune donnée structurée", async () => {
    servirLaFiche(() => new HttpResponse("panne", { status: 500 }));
    rendre(<FicheProduit />, "/boutique/foodtrucks");
    expect(await screen.findByRole("alert")).toHaveTextContent(/panne passagère/);
    expect(screen.getByRole("button", { name: /Réessayer/ })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(texte()).not.toMatch(/n'est pas disponible/);
    expect(donneesStructurees()).toBeNull();
    attendreLeSocle();
  });
});

// ── 6. Les données structurées ──────────────────────────────────────────────

describe("le JSON-LD de la fiche ne contient que ce que l'API a rendu", () => {
  const ADRESSE = `${ORIGINE}/boutique/foodtrucks`;

  it("sans avis ni couverture : le nom, la description, la catégorie, l'offre — rien d'autre", async () => {
    await rendreLaFiche();
    expect(donneesStructurees()).toEqual({
      "@context": "https://schema.org",
      "@type": "Product",
      name: FICHE.produit.titre,
      url: ADRESSE,
      description: FICHE.produit.description,
      category: FICHE.produit.theme,
      offers: {
        "@type": "Offer",
        price: "89.00",
        priceCurrency: "EUR",
        url: ADRESSE,
      },
    });
  });

  it("contre-épreuve — avec des avis et une couverture : la note, leur nombre et l'image y sont", async () => {
    await rendreLaFiche({
      ...FICHE,
      produit: {
        ...FICHE.produit,
        image: "https://api.exemple/media/boutique/foodtrucks.jpg",
        note: 4.5,
        nombre_d_avis: 2,
        avis: AVIS,
      },
    });
    const donnees = donneesStructurees();
    expect(donnees?.aggregateRating).toEqual({
      "@type": "AggregateRating",
      ratingValue: 4.5,
      reviewCount: 2,
    });
    expect(donnees?.image).toBe("https://api.exemple/media/boutique/foodtrucks.jpg");
    // Et la page montre ce qu'elle déclare.
    expect(texte()).toContain("4,5 sur 5");
    expect(within(principal()).getByRole("link", { name: "2 avis" })).toHaveAttribute("href", "#avis");
    expect(document.getElementById("avis")).not.toBeNull();
    expect(texte()).toContain("Camille");
  });

  it("une note sans avis publié, une description vide, un thème vide : aucun n'est déclaré", async () => {
    await rendreLaFiche({
      ...FICHE,
      produit: { ...FICHE.produit, description: "", theme: "", note: 4.8, nombre_d_avis: 3, avis: [] },
    });
    const donnees = donneesStructurees() ?? {};
    expect(Object.keys(donnees).sort()).toEqual(["@context", "@type", "name", "offers", "url"]);
  });

  it("un prix à zéro n'est pas une offre", async () => {
    await rendreLaFiche({ ...FICHE, produit: { ...FICHE.produit, prix_cents: 0 } });
    expect(donneesStructurees()).not.toHaveProperty("offers");
  });

  it("le bloc est construit par JSON.stringify, pas écrit à la main", () => {
    const code = sansCommentaires(source("FicheProduit.tsx"));
    expect(code).toMatch(/application\/ld\+json/);
    expect(code).toMatch(/JSON\.stringify\(donneesStructurees\(produit\)\)/);
    expect(code).not.toMatch(/dangerouslySetInnerHTML/);
  });
});

// ── 7. Plus aucun lien vers l'ancien site ───────────────────────────────────

describe("aucun lien vers l'ancien site dans les cinq pages", () => {
  const PAGES: { nom: string; rendre: () => Promise<unknown> }[] = [
    { nom: "catalogue", rendre: () => rendreLeCatalogue() },
    { nom: "fiche", rendre: () => rendreLaFiche() },
    {
      nom: "retour de boutique",
      rendre: () => {
        server.use(
          http.post(`${PUBLIC}/boutique/retour/`, () =>
            HttpResponse.json({
              jeton: null,
              connexion_requise: true,
              titre: FOODTRUCKS.titre,
              slug: FOODTRUCKS.slug,
              telechargement: "https://api.exemple/media/boutique/foodtrucks.pdf?s=abc",
              editable: "",
            }),
          ),
        );
        rendre(<RetourBoutique />, "/boutique/retour?session=cs_test_2");
        return screen.findByRole("link", { name: /Télécharger le PDF/ });
      },
    },
    {
      nom: "page d'achat",
      rendre: () => {
        server.use(http.get(`${PUBLIC}/livrables/`, () => HttpResponse.json(LIVRABLES)));
        rendre(<Acheter />, "/acheter/etude-de-marche");
        return screen.findByRole("button", { name: /Payer/ });
      },
    },
    {
      nom: "retour de paiement",
      // Sans identifiant de paiement : la page le dit, et reste affichée.
      rendre: () => {
        rendre(<RetourPaiement />, "/acheter/retour");
        return screen.findByRole("alert");
      },
    },
  ];

  for (const page of PAGES) {
    it(`${page.nom} : aucun lien rendu ne mène à l'ancien site, et le socle est monté`, async () => {
      await page.rendre();
      const liens = Array.from(document.querySelectorAll("a[href]")).map(
        (a) => a.getAttribute("href") ?? "",
      );
      // Règle 1 : la barre, le menu et le pied sont bien là.
      expect(liens.length, page.nom).toBeGreaterThan(40);
      expect(liens.filter((href) => ANCIEN_SITE.test(href)), page.nom).toEqual([]);
      // Les images non plus ne viennent pas de l'ancien site.
      for (const image of Array.from(document.querySelectorAll("img"))) {
        expect(image.getAttribute("src") ?? "", page.nom).not.toMatch(ANCIEN_SITE);
      }
      attendreLeSocle();
      expect(screen.getAllByRole("heading", { level: 1 }), page.nom).toHaveLength(1);
    });
  }

  it("aucune adresse de l'ancien site, ni l'ancien menu, dans les sources des cinq pages", () => {
    for (const fichier of SOURCES) {
      const code = sansCommentaires(source(fichier));
      expect(code.length, fichier).toBeGreaterThan(1000);
      expect(code, fichier).not.toMatch(ANCIEN_SITE);
      expect(code, fichier).not.toMatch(/MenuSite/);
      expect(code, fichier).toMatch(/EnTeteSite|CadreDeBoutique/);
    }
  });

  it("contre-épreuve : le détecteur voit l'ancien site, pas l'adresse de contact", () => {
    expect("https://www.evkha.fr/").toMatch(ANCIEN_SITE);
    expect("https://evkha.fr/etudedemarche").toMatch(ANCIEN_SITE);
    expect("evkha.fr/packs").toMatch(ANCIEN_SITE);
    expect("https://d1yei2z3i6k35z.cloudfront.net/9890127/logo.png").toMatch(ANCIEN_SITE);
    expect("mailto:contact@evkha.fr").not.toMatch(ANCIEN_SITE);
    expect("Écrivez-nous à contact@evkha.fr.").not.toMatch(ANCIEN_SITE);
    expect("/etudes").not.toMatch(ANCIEN_SITE);
  });
});

// ── 8 et 9. La passerelle, et l'achat à portée ──────────────────────────────

describe("la fiche mène à l'étude sur mesure, et garde l'achat à portée", () => {
  it("la passerelle vers /etudes existe, en fin de page, sans prix", async () => {
    await rendreLaFiche();
    const lien = within(principal()).getByRole("link", { name: /études sur mesure/ });
    expect(lien).toHaveAttribute("href", "/etudes");
    const passerelle = lien.closest("section");
    expect(passerelle).not.toBeNull();
    expect(passerelle).toHaveTextContent(/votre propre projet et votre propre zone/);
    expect(espaces(passerelle?.textContent ?? "")).not.toMatch(MONTANT);
    expect(within(passerelle as HTMLElement).getByRole("heading", { level: 2 })).toBeInTheDocument();
    // En fin de page : c'est la dernière section du contenu.
    const sections = principal().querySelectorAll("section");
    expect(sections[sections.length - 1]).toBe(passerelle);
  });

  it("la fiche se lit comme une page de contenu : ce qu'on achète, pour qui, le sommaire, le déroulé", async () => {
    await rendreLaFiche();
    const titres = within(principal())
      .getAllByRole("heading", { level: 2 })
      .map((titre) => titre.textContent);
    expect(titres).toEqual(
      expect.arrayContaining([
        "Ce que vous achetez",
        "À qui s'adresse cette étude",
        "Le sommaire",
        "Comment ça se passe",
        "Ces études peuvent aussi vous intéresser",
      ]),
    );
    expect(texte()).toContain(FICHE.produit.description);
    for (const ligne of FICHE.produit.sommaire) expect(texte()).toContain(ligne);
    // L'étude voisine, par sa carte, avec SON prix.
    expect(within(principal()).getByRole("link", { name: COIFFURE.titre })).toHaveAttribute(
      "href",
      "/boutique/salons-de-coiffure",
    );
    expect(texte()).toContain("129,50 €");
  });

  it("un seul bouton ouvre le paiement ; la barre du téléphone est un lien vers le panneau", async () => {
    await rendreLaFiche();
    expect(screen.getAllByRole("button", { name: /Acheter/ })).toHaveLength(1);
    const panneau = document.getElementById("bou-achat");
    expect(panneau).not.toBeNull();
    expect(panneau).toContainElement(screen.getByRole("button", { name: /Acheter/ }));
    const rappel = within(principal()).getByRole("link", { name: /Acheter cette étude/ });
    expect(rappel).toHaveAttribute("href", "#bou-achat");
    // En visiteur, l'adresse se saisit dans le panneau, à 16 px au moins
    // (`.champ-saisie`, verrouillé ailleurs).
    expect(within(panneau as HTMLElement).getByLabelText(/adresse e-mail/i)).toHaveClass("champ-saisie");
  });

  it("l'aperçu s'ouvre à l'adresse que l'API a rendue", async () => {
    const adresse = "https://api.exemple/api/public/boutique/foodtrucks/apercu/";
    await rendreLaFiche({
      ...FICHE,
      produit: { ...FICHE.produit, apercu: { pages: 12, adresse } },
    });
    const liens = within(principal())
      .getAllByRole("link")
      .filter((a) => a.getAttribute("href") === adresse);
    // Dans la lecture et dans le panneau d'achat.
    expect(liens).toHaveLength(2);
    for (const lien of liens) expect(lien).toHaveAttribute("target", "_blank");
    expect(texte()).toContain("Les 12 premières pages");
  });
});

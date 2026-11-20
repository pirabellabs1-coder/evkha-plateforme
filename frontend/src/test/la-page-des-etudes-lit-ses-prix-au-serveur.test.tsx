/** La page des études lit ses prix au serveur — et sa refonte n'a rien retiré.
 *
 * `/etudes` est la page de vente principale : le bouton « Commander une
 * étude » de l'accueil y mène. Refaite le 19/11/2026 dans le langage visuel de
 * l'accueil, elle garde les comportements que l'ancienne page tenait, et que
 * rien ne verrouillait :
 *
 * 1. les prix affichés sont ceux de l'API — servis ici à des montants que
 *    personne n'écrirait de mémoire (151 €, 93 €…), pour qu'un prix recopié ne
 *    puisse pas passer pour un prix lu ; la fourchette de l'ouverture est
 *    CALCULÉE dessus ;
 * 2. tant que l'API n'a pas répondu, aucun montant n'est dans le DOM ;
 * 3. une panne se dit — dans UNE région d'alerte — et ne se lit ni comme un
 *    prix ni comme un vide (règle 1) ; une réponse 200 mal formée est une
 *    panne, pas un catalogue vide ;
 * 4. les cartes sont dans l'ordre du PARCOURS (marché, concurrence, business
 *    plan, stratégie), quel que soit l'ordre du serveur, numérotées dans cet
 *    ordre, et chaque bouton de commande porte le slug de SA carte ;
 * 5. après chaque carte, une ligne nomme le document suivant — par le libellé
 *    du serveur, sans remise ni lot —, et se tait quand ce document n'est pas
 *    au catalogue ;
 * 6. RIEN de ce que la page disait n'a disparu : chaque phrase de
 *    `contenu.ETUDES_PAGE` et de `contenu.ETUDES` est dans le DOM ;
 * 7. l'organisme s'appelle France Travail depuis le 1er janvier 2024 : son
 *    ancien nom n'est plus écrit dans aucun fichier de contenu ;
 * 8. aucun montant n'est écrit dans les sources de la page — la classe du
 *    défaut (règle 4), pas la liste des prix d'aujourd'hui.
 *
 * Contre-épreuves (règle 6) : le reste de la page s'affiche sans prix ; une
 * offre sans argumentaire s'affiche quand même ; les détecteurs voient bien un
 * montant et l'ancien nom de l'organisme.
 *
 * Rejoué le 19/11/2026 contre le code d'avant (`NosEtudes.tsx`,
 * `NosEtudes.css` et `contenu.ts` restaurés depuis leur sauvegarde) : rouge,
 * 16 tests sur 23 — dont beaucoup parce que l'ancienne page n'a pas la forme
 * que ce test décrit, ce qui ne prouve rien sur chaque verrou. D'où sept
 * mutations de la NOUVELLE page, une à la fois, toutes rouges : `ordonnees`
 * qui rend l'ordre du serveur ; un « 149 € » écrit en dur dans la carte ; la
 * fourchette écrite en dur ; la ligne « ensuite » affichée sans regarder le
 * catalogue ; le pied des interrogations retiré ; la panne tue (alerte
 * muette) ; l'ancien nom de l'organisme remis dans une phrase de
 * `contenu.ts`.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { ETUDES, ETUDES_PAGE } from "../public/contenu";
import { NosEtudes } from "../public/NosEtudes";
import { server } from "./server";

// L'adresse que `donnees.ts` construit réellement : l'origine de jsdom, et
// non l'origine fixe de `server.ts`. Une requête sans gestionnaire partirait
// sur le réseau et échouerait — le cas « panne » passerait alors pour une
// mauvaise raison.
const LIVRABLES_API = `${window.location.origin}/api/public/livrables/`;

function livrable(slug: string, type: string, prix_cents: number, libelle: string) {
  return { slug, libelle, type, prix_cents };
}

/** Le catalogue, dans l'ordre où le serveur le rend : par prix croissant —
 *  donc PAS dans l'ordre du parcours. Les libellés sont ceux du serveur, avec
 *  un mot que la page n'écrit nulle part (« sectorielle », « bancaire »…) :
 *  s'il s'affiche, il vient d'ici. */
const CONCURRENCE = livrable("etude-concurrence", "competitor_study", 9300, "Étude de la concurrence locale");
const MARCHE = livrable("etude-marche", "market_study", 15100, "Étude de marché sectorielle");
const PLAN = livrable("business-plan", "business_plan", 18700, "Business plan bancaire");
const STRATEGIE = livrable("strategie-business", "business_strategy", 20300, "Stratégie business annuelle");
const DU_SERVEUR = [CONCURRENCE, MARCHE, PLAN, STRATEGIE];

/** L'ordre du parcours : celui de `contenu.ETUDES`. */
const PARCOURS = ["etude-marche", "etude-concurrence", "business-plan", "strategie-business"];

type Reponse = () => Response | Promise<Response>;

function servir(reponse: Reponse) {
  server.use(http.get(LIVRABLES_API, reponse));
}

const lesLivrables = (liste: object[]): Reponse => () => HttpResponse.json({ livrables: liste });
const panne: Reponse = () => new HttpResponse("panne", { status: 500 });
const muet: Reponse = async () => {
  await delay("infinite");
  return new HttpResponse(null);
};

/** Les deux espaces insécables qu'`Intl.NumberFormat` pose avant « € ».
 *  Construites par leur code, jamais tapées : écrites en clair, elles sont
 *  invisibles à la relecture et un outil d'édition les change sans le dire. */
const INSECABLE = String.fromCharCode(0xa0);
const FINE_INSECABLE = String.fromCharCode(0x202f);
const INSECABLES = new RegExp(`[${INSECABLE}${FINE_INSECABLE}]`, "g");

function espaces(brut: string): string {
  return brut.replace(INSECABLES, " ");
}

function texte(): string {
  return espaces(document.body.textContent ?? "");
}

function texteDe(element: Element | null): string {
  return espaces(element?.textContent ?? "");
}

function alerte(): HTMLElement {
  return screen.getByRole("alert");
}

/** Les cartes d'étude, dans l'ordre du DOM. */
function cartes(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>("article.etu-carte"));
}

function carte(slug: string): HTMLElement {
  const trouvee = document.getElementById(`carte-${slug}`);
  if (!trouvee) throw new Error(`carte introuvable : ${slug}`);
  return trouvee;
}

async function cartesChargees(nombre: number) {
  await waitFor(() => expect(cartes()).toHaveLength(nombre));
}

async function catalogueRepondu() {
  await waitFor(() => expect(screen.queryByText(/Chargement du catalogue/)).toBeNull());
}

/** Un montant en euros, où qu'il soit. */
const MONTANT = /\d\s*€/;
const MONTANT_ECRIT = /\d[\d\s.,]*(?:€|euros?\b)/i;

/** L'ancien nom de France Travail, sous ses écritures courantes : avec ou
 *  sans accent, avec ou sans majuscules, avec une espace insécable. */
const ANCIEN_NOM = new RegExp(`p[oô]le[\\s${INSECABLE}-]+emploi`, "i");

/** Les prix du site d'aujourd'hui et ceux de la maquette : aucun ne doit
 *  apparaître quand l'API en rend d'autres. */
const PRIX_CONNUS = ["89 €", "149 €", "185 €", "195 €", "129 €", "189 €", "249 €"];

function sansCommentaires(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

function source(fichier: string): string {
  return readFileSync(join(process.cwd(), "src", "public", fichier), "utf-8");
}

/** Toutes les phrases d'un objet de contenu, à plat. */
function phrases(valeur: unknown): string[] {
  if (typeof valeur === "string") return [valeur];
  if (Array.isArray(valeur)) return valeur.flatMap(phrases);
  if (valeur && typeof valeur === "object") return Object.values(valeur).flatMap(phrases);
  return [];
}

describe("la page des études lit ses prix au serveur", () => {
  // La page déduit l'entrée courante de la barre du chemin : on la rend à
  // son adresse.
  beforeEach(() => window.history.pushState({}, "", "/etudes"));
  afterEach(() => window.history.pushState({}, "", "/"));

  it("affiche les prix que l'API rend, et calcule sa fourchette dessus", async () => {
    servir(lesLivrables(DU_SERVEUR));
    render(<NosEtudes />);
    await cartesChargees(4);

    // La fourchette de l'ouverture : du moins cher au plus cher.
    const fourchette = document.querySelector(".etu-preuve-prix");
    expect(texteDe(fourchette)).toContain("de 93 € à 203 €");
    expect(texteDe(fourchette)).toContain("par étude");

    // Chaque carte : SON libellé (celui du serveur), SON prix, SON slug.
    const attendus: [string, string, string, string][] = [
      ["etude-marche", "Étude de marché sectorielle", "151 €", "/inscription?livrable=etude-marche"],
      ["etude-concurrence", "Étude de la concurrence locale", "93 €", "/inscription?livrable=etude-concurrence"],
      ["business-plan", "Business plan bancaire", "187 €", "/inscription?livrable=business-plan"],
      ["strategie-business", "Stratégie business annuelle", "203 €", "/inscription?livrable=strategie-business"],
    ];
    for (const [slug, libelle, prix, lien] of attendus) {
      const c = carte(slug);
      expect(within(c).getByRole("heading", { level: 3 })).toHaveTextContent(libelle);
      expect(texteDe(c.querySelector(".etu-prix")), slug).toContain(prix);
      // UN lien dans la carte : celui de la commande, avec le bon slug.
      const liens = within(c).getAllByRole("link");
      expect(liens, slug).toHaveLength(1);
      expect(liens[0], slug).toHaveAttribute("href", lien);
      expect(liens[0]).toHaveTextContent(ETUDES[slug].bouton);
    }

    for (const prix of PRIX_CONNUS) {
      expect(texte(), `« ${prix} » est écrit en dur quelque part`).not.toContain(prix);
    }
    expect(alerte()).toBeEmptyDOMElement();
    expect(texte()).not.toContain("momentanément indisponible");
    expect(document.querySelector(".acc-btn-inactif")).toBeNull();
    // L'appel final commande la PREMIÈRE étude du parcours, pas la moins chère.
    expect(document.querySelector("#commander a")).toHaveAttribute("href", "/inscription?livrable=etude-marche");
  });

  it("tant que l'API n'a pas répondu, aucun montant n'est dans le DOM", async () => {
    servir(muet);
    render(<NosEtudes />);

    expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(texte()).not.toMatch(MONTANT);
    // L'attente se dit, elle ne laisse pas un trou — et ce n'est pas une panne.
    expect(screen.getByRole("status")).toHaveTextContent(/Chargement du catalogue/);
    expect(texteDe(document.querySelector(".etu-preuve-prix"))).toContain("Tarif en cours de chargement");
    expect(alerte()).toBeEmptyDOMElement();
    expect(cartes()).toHaveLength(0);
    // Sans étude connue, pas de barre d'ancres vers des cartes qui n'existent
    // pas, et l'appel final mène aux cartes plutôt qu'à un lien mort.
    expect(screen.queryByRole("navigation", { name: ETUDES_PAGE.cartes.titre })).toBeNull();
    expect(document.querySelector("#commander a")).toHaveAttribute("href", "#nos-etudes");
    expect(document.getElementById("nos-etudes")).not.toBeNull();
  });

  it("si l'API échoue, la page le dit et n'affiche aucun prix", async () => {
    servir(panne);
    render(<NosEtudes />);

    await waitFor(() => expect(alerte()).toHaveTextContent(/catalogue est momentanément indisponible/));
    await catalogueRepondu();
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(alerte().querySelector("a")).toHaveAttribute("href", "mailto:contact@evkha.fr");
    expect(texteDe(document.querySelector(".etu-preuve-prix"))).toContain("Tarif momentanément indisponible");
    // La section des cartes reste et dit sa panne, sans carte ni phrase de vide.
    expect(document.querySelector("#nos-etudes .acc-panne")).toHaveTextContent(/momentanément indisponible/);
    expect(cartes()).toHaveLength(0);
    expect(texte()).not.toContain("Aucune étude n'est en vente");
    expect(texte()).not.toMatch(MONTANT);
    expect(texte()).not.toContain("∞");
  });

  // Une réponse 200 qui ne porte pas la liste attendue — `{}`, ou la page
  // d'un relais servie à la place de l'API — n'est pas un catalogue vide.
  for (const [nom, reponse] of [
    ["un objet sans la clé attendue", () => HttpResponse.json({})],
    ["une clé mal nommée", () => HttpResponse.json({ livrable: [] })],
    [
      "la page d'un relais",
      () => new HttpResponse("<!doctype html><title>EVKHA</title>", { headers: { "Content-Type": "text/html" } }),
    ],
  ] as [string, Reponse][]) {
    it(`une réponse 200 mal formée (${nom}) est une panne dite, pas un catalogue vide`, async () => {
      servir(reponse);
      render(<NosEtudes />);

      await waitFor(() => expect(alerte()).toHaveTextContent(/momentanément indisponible/));
      await catalogueRepondu();
      expect(texte()).not.toContain("Aucune étude n'est en vente");
      expect(texte()).not.toContain("Indisponible pour le moment");
      expect(texte()).not.toMatch(MONTANT);
    });
  }

  it("un catalogue reçu VIDE : ni prix, ni panne — la page dit qu'il n'y a rien en vente", async () => {
    servir(lesLivrables([]));
    render(<NosEtudes />);

    await catalogueRepondu();
    expect(await screen.findByText(/Aucune étude n'est en vente pour le moment/)).toBeInTheDocument();
    expect(alerte()).toBeEmptyDOMElement();
    expect(texteDe(document.querySelector(".etu-preuve-prix"))).toContain("Indisponible pour le moment");
    expect(texte()).not.toMatch(MONTANT);
    expect(texte()).not.toContain("∞");
    expect(document.querySelector("#commander a")).toHaveAttribute("href", "#nos-etudes");
  });

  // ── L'ordre du parcours ───────────────────────────────────────────────────

  for (const [nom, ordre] of [
    ["par prix croissant", DU_SERVEUR],
    ["à l'envers du parcours", [STRATEGIE, PLAN, CONCURRENCE, MARCHE]],
    ["mélangé", [PLAN, MARCHE, STRATEGIE, CONCURRENCE]],
  ] as [string, object[]][]) {
    it(`les cartes suivent le parcours, quel que soit l'ordre du serveur (${nom})`, async () => {
      servir(lesLivrables(ordre));
      render(<NosEtudes />);
      await cartesChargees(4);

      expect(cartes().map((c) => c.id)).toEqual(PARCOURS.map((slug) => `carte-${slug}`));
      // Numérotées 01 à 04 dans cet ordre.
      expect(cartes().map((c) => c.querySelector(".etu-carte-numero")?.textContent)).toEqual(["01", "02", "03", "04"]);
      // La barre d'ancres suit le même ordre, et chaque lien vise une carte
      // qui EXISTE.
      const ancres = within(screen.getByRole("navigation", { name: ETUDES_PAGE.cartes.titre })).getAllByRole("link");
      expect(ancres.map((a) => a.getAttribute("href"))).toEqual(PARCOURS.map((slug) => `#carte-${slug}`));
      expect(ancres.map((a) => texteDe(a))).toEqual(["01Marché", "02Concurrence", "03Business plan", "04Stratégie"]);
      for (const ancre of ancres) {
        expect(document.querySelector(ancre.getAttribute("href") as string), ancre.textContent ?? "").not.toBeNull();
      }
    });
  }

  it("après chaque carte, une ligne nomme le document suivant par son libellé du serveur — sauf après la dernière", async () => {
    servir(lesLivrables(DU_SERVEUR));
    render(<NosEtudes />);
    await cartesChargees(4);

    const suites = Array.from(document.querySelectorAll<HTMLElement>(".etu-suite"));
    expect(suites).toHaveLength(3);
    const attendus: [string, string, string][] = [
      ["etude-marche", "Étude de la concurrence locale", "#carte-etude-concurrence"],
      ["etude-concurrence", "Business plan bancaire", "#carte-business-plan"],
      ["business-plan", "Stratégie business annuelle", "#carte-strategie-business"],
    ];
    for (const [slug, suivant, lien] of attendus) {
      // La ligne est dans le même élément de liste que SA carte, après elle.
      const ligne = carte(slug).parentElement?.querySelector(".etu-suite");
      expect(ligne, slug).not.toBeNull();
      expect(carte(slug).compareDocumentPosition(ligne as Element) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      const ancre = within(ligne as HTMLElement).getByRole("link");
      expect(ancre).toHaveAttribute("href", lien);
      expect(ancre).toHaveTextContent(suivant);
      // Ni remise, ni lot, ni prix : la ligne dit ce qui vient après, rien d'autre.
      expect(texteDe(ligne as Element)).not.toMatch(MONTANT);
      expect(texteDe(ligne as Element)).not.toMatch(/remise|réduction|pack|lot\b|%|offert/i);
    }
    expect(carte("strategie-business").parentElement?.querySelector(".etu-suite")).toBeNull();
  });

  it("la ligne « ensuite » se tait quand le document suivant n'est pas au catalogue", async () => {
    // Sans business plan : l'étude de concurrence n'a plus de suite à nommer ;
    // l'étude de marché garde la sienne.
    servir(lesLivrables([CONCURRENCE, MARCHE, STRATEGIE]));
    render(<NosEtudes />);
    await cartesChargees(3);

    expect(carte("etude-marche").parentElement?.querySelector(".etu-suite a")).toHaveAttribute("href", "#carte-etude-concurrence");
    expect(carte("etude-concurrence").parentElement?.querySelector(".etu-suite")).toBeNull();
    expect(document.querySelectorAll(".etu-suite")).toHaveLength(1);
    expect(texte()).not.toContain("Business plan bancaire");
    // Trois cartes, numérotées sans trou.
    expect(cartes().map((c) => c.querySelector(".etu-carte-numero")?.textContent)).toEqual(["01", "02", "03"]);
  });

  it("contre-épreuve : une offre sans argumentaire s'affiche quand même, à la fin, avec son prix", async () => {
    servir(lesLivrables([livrable("previsionnel", "forecast", 11300, "Prévisionnel financier"), ...DU_SERVEUR]));
    render(<NosEtudes />);
    await cartesChargees(5);

    expect(cartes().map((c) => c.id)).toEqual([...PARCOURS.map((slug) => `carte-${slug}`), "carte-previsionnel"]);
    const sobre = carte("previsionnel");
    expect(within(sobre).getByRole("heading", { level: 3 })).toHaveTextContent("Prévisionnel financier");
    expect(texteDe(sobre)).toContain("113 €");
    expect(texteDe(sobre)).toContain("Un document complet, en Word et en PDF");
    const bouton = within(sobre).getByRole("link");
    expect(bouton).toHaveAttribute("href", "/inscription?livrable=previsionnel");
    expect(bouton).toHaveTextContent("Commander prévisionnel financier");
    // Elle entre dans la barre d'ancres sous son libellé complet.
    expect(screen.getByRole("link", { name: /Prévisionnel financier$/ })).toHaveAttribute("href", "#carte-previsionnel");
    // La fourchette la compte : c'est une étude en vente.
    expect(texteDe(document.querySelector(".etu-preuve-prix"))).toContain("de 93 € à 203 €");
  });

  it("une offre à zéro n'a pas de prix : ni « 0 € », ni bouton de commande", async () => {
    servir(lesLivrables([{ ...MARCHE, prix_cents: 0 }, CONCURRENCE, PLAN, STRATEGIE]));
    render(<NosEtudes />);
    await cartesChargees(4);

    expect(texte()).not.toMatch(/(?<!\d)0 €/);
    const gratuite = carte("etude-marche");
    expect(within(gratuite).getByText("Indisponible pour le moment")).toBeInTheDocument();
    expect(gratuite.querySelector(".acc-btn-inactif")).toHaveAttribute("aria-disabled", "true");
    expect(gratuite.querySelector("a")).toBeNull();
    // La fourchette l'ignore, et l'appel final commande la première étude
    // qui SE VEND.
    expect(texteDe(document.querySelector(".etu-preuve-prix"))).toContain("de 93 € à 203 €");
    expect(document.querySelector("#commander a")).toHaveAttribute("href", "/inscription?livrable=etude-concurrence");
  });

  // ── Rien de ce que la page disait n'a disparu ─────────────────────────────

  it("chaque phrase de contenu.ETUDES_PAGE et de contenu.ETUDES est dans la page", async () => {
    servir(lesLivrables(DU_SERVEUR));
    render(<NosEtudes />);
    await cartesChargees(4);

    const page = texte();
    // Tout le texte de la page, sauf l'adresse de l'image et son texte de
    // remplacement (vide : elle est décorative), qui ne sont pas des phrases.
    const { image, alt, ...ouverture } = ETUDES_PAGE.hero;
    const attendues = phrases({ ...ETUDES_PAGE, hero: ouverture });
    // Règle 1 : une collecte vide ferait passer la boucle sans rien vérifier.
    expect(attendues.length).toBeGreaterThan(60);
    for (const phrase of attendues) {
      expect(page, `la page ne dit plus : « ${phrase} »`).toContain(espaces(phrase));
    }
    // Les quatre argumentaires, nombre de chapitres compris.
    for (const slug of PARCOURS) {
      const argumentaire = ETUDES[slug];
      const c = texteDe(carte(slug));
      for (const phrase of phrases(argumentaire)) {
        expect(c, `${slug} ne dit plus : « ${phrase} »`).toContain(espaces(phrase));
      }
      expect(c).toContain(`${argumentaire.chapitres} ${argumentaire.chapeau}`);
      expect(c).toContain("Ce que vous obtenez :");
      expect(c).toContain("TTC · paiement unique");
    }
    // L'image de l'ouverture, à sa place réservée.
    const photo = document.querySelector<HTMLImageElement>("img.etu-image");
    expect(photo).toHaveAttribute("src", image);
    expect(photo).toHaveAttribute("alt", alt);
    expect(Number(photo?.getAttribute("width"))).toBeGreaterThan(0);
    expect(Number(photo?.getAttribute("height"))).toBeGreaterThan(0);
  });

  it("contre-épreuve : le reste de la page s'affiche même sans prix", async () => {
    servir(panne);
    render(<NosEtudes />);
    await waitFor(() => expect(alerte()).not.toBeEmptyDOMElement());

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Votre marché est-il rentable et viable ?");
    expect(document.title).toBe("Faire faire son étude de marché ou son business plan — EVKHA");
    // Les quatre étapes, dans l'ordre, dans une liste ordonnée.
    const etapes = Array.from(document.querySelectorAll("ol.etu-etapes > li h3")).map((t) => t.textContent);
    expect(etapes).toEqual(ETUDES_PAGE.etapes.map((e) => e.titre));
    // Les huit questions en <details>, la première ouverte.
    const questions = Array.from(document.querySelectorAll("#questions details"));
    expect(questions).toHaveLength(ETUDES_PAGE.faq.questions.length);
    expect(questions[0]).toHaveAttribute("open");
    expect(questions[1]).not.toHaveAttribute("open");
    // Le comparatif, en deux colonnes nommées.
    expect(screen.getByText("Ce que vous évitez").closest("article")).toHaveTextContent(ETUDES_PAGE.comparatif.generique.titre);
    expect(screen.getByText("Ce que vous recevez").closest("article")).toHaveTextContent(ETUDES_PAGE.comparatif.evkha.titre);
    // La passerelle : les deux autres portes, sans un prix.
    const passerelle = document.getElementById("autrement") as HTMLElement;
    expect(within(passerelle).getByRole("link", { name: /Voir la boutique/ })).toHaveAttribute("href", "/boutique");
    expect(within(passerelle).getByRole("link", { name: /Voir les abonnements/ })).toHaveAttribute("href", "/partenaires");
    expect(texteDe(passerelle)).not.toMatch(MONTANT_ECRIT);
    // Elle précède l'appel final.
    const fin = document.getElementById("commander") as HTMLElement;
    expect(passerelle.compareDocumentPosition(fin) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  // ── La page se laisse conduire ────────────────────────────────────────────

  it("un seul h1, des titres sans saut de niveau, un lien d'évitement qui vise le contenu", async () => {
    servir(lesLivrables(DU_SERVEUR));
    render(<NosEtudes />);
    await cartesChargees(4);

    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    const niveaux = Array.from(document.querySelectorAll("h1, h2, h3, h4, h5, h6")).map((t) => Number(t.tagName[1]));
    expect(niveaux[0]).toBe(1);
    expect(niveaux.length).toBeGreaterThan(15);
    niveaux.forEach((niveau, k) => {
      if (k > 0) expect(niveau - niveaux[k - 1], `saut de titre au rang ${k}`).toBeLessThanOrEqual(1);
    });

    const principal = screen.getByRole("main");
    expect(screen.getByRole("link", { name: "Aller au contenu" })).toHaveAttribute("href", `#${principal.id}`);
    expect(principal.id).not.toBe("");

    // Rien de focalisable sous `aria-hidden` : le clavier y entrerait sans
    // qu'un lecteur d'écran dise où il est.
    const caches = Array.from(document.querySelectorAll("[aria-hidden='true']"));
    expect(caches.length).toBeGreaterThan(10);
    for (const cache of caches) {
      expect(cache.querySelector("a, button, input, select, textarea, summary, [tabindex]"), cache.className).toBeNull();
    }
    // Chaque image dit ce qu'elle est, ou qu'elle est décorative.
    for (const image of Array.from(document.querySelectorAll("img"))) {
      expect(image.hasAttribute("alt"), image.getAttribute("src") ?? "").toBe(true);
    }
  });

  it("les deux boutons de pause partagent un seul état, qui arrête le ruban", async () => {
    servir(lesLivrables(DU_SERVEUR));
    const { container } = render(<NosEtudes />);
    await cartesChargees(4);

    const boutons = screen.getAllByRole("button", { name: "Mettre les animations en pause" });
    expect(boutons).toHaveLength(2);
    fireEvent.click(boutons[1]);
    expect(container.querySelector(".acc")).toHaveClass("acc-fige");
    for (const bouton of screen.getAllByRole("button", { name: "Relancer les animations" })) {
      expect(bouton).toHaveAttribute("aria-pressed", "true");
    }
    // Le ruban ne répète que ce que la page dit ailleurs : il est décoratif.
    expect(document.querySelector(".acc-ruban")).toHaveAttribute("aria-hidden", "true");
  });

  // ── France Travail ────────────────────────────────────────────────────────

  it("la page et ses fichiers de contenu n'écrivent plus l'ancien nom de France Travail", async () => {
    servir(lesLivrables(DU_SERVEUR));
    render(<NosEtudes />);
    await cartesChargees(4);

    expect(texte()).not.toMatch(ANCIEN_NOM);
    // Le nouveau nom, là où l'ancien était écrit : six fois dans `contenu.ts`.
    expect(texte().match(/France Travail/g)?.length).toBeGreaterThanOrEqual(6);

    for (const fichier of ["contenu.ts", "contenuAccueil.ts", "contenuEtudes.ts", "contenuSite.ts"]) {
      const brut = source(fichier);
      // Règle 1 : un fichier vide ou introuvable ne « passe » pas.
      expect(brut.length, fichier).toBeGreaterThan(2000);
      // Commentaires COMPRIS : un commentaire qui garde l'ancien nom le
      // ferait revenir au prochain copier-coller.
      expect(brut.match(new RegExp(ANCIEN_NOM.source, "gi")) ?? [], fichier).toEqual([]);
    }
    expect(source("contenu.ts").match(/France Travail/g)).toHaveLength(6);
  });

  // ── La classe du défaut : un montant écrit dans la page ───────────────────

  for (const fichier of ["NosEtudes.tsx", "contenuEtudes.ts", "contenuSite.ts"]) {
    it(`${fichier} n'écrit aucun montant`, () => {
      const code = sansCommentaires(source(fichier));
      // Règle 1 : un fichier vide ou introuvable ne « passe » pas.
      expect(code.length).toBeGreaterThan(2000);
      expect(code.match(new RegExp(MONTANT_ECRIT.source, "gi")) ?? []).toEqual([]);
    });
  }

  it("contre-épreuve : les détecteurs voient un montant et l'ancien nom, et rien d'autre", () => {
    for (const faute of ["dès 89 €", "149€", "1 490 € TTC", "64,50 €", "prix: 185 euros"]) {
      expect(faute, faute).toMatch(MONTANT_ECRIT);
    }
    for (const juste of ["sous 24 heures ouvrées", "15 à 20 minutes", "500+", "le signe €", "22 chapitres"]) {
      expect(juste, juste).not.toMatch(MONTANT_ECRIT);
    }
    expect(espaces(`de${INSECABLE}93${FINE_INSECABLE}€`)).toMatch(MONTANT);

    for (const faute of ["Pôle Emploi", "pôle emploi", "POLE EMPLOI", "Pole-Emploi", `Pôle${INSECABLE}Emploi`, "la BGE, Pôle Emploi et"]) {
      expect(faute, faute).toMatch(ANCIEN_NOM);
    }
    for (const juste of ["France Travail", "le pôle commercial", "un emploi salarié", "pôle de compétitivité, emploi local"]) {
      expect(juste, juste).not.toMatch(ANCIEN_NOM);
    }
    // Le collecteur de phrases descend dans les listes et les objets.
    expect(phrases({ a: "un", b: ["deux", { c: "trois", d: 4, e: null }] })).toEqual(["un", "deux", "trois"]);
  });
});

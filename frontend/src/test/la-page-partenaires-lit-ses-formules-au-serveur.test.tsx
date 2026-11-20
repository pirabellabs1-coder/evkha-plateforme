/** La page des partenaires lit ses formules au serveur — et sa refonte n'a
 * rien retiré.
 *
 * `/partenaires` vend les abonnements aux professionnels. Refaite le
 * 19/11/2026 dans le langage visuel de l'accueil et de la page des études
 * (`Partenaires.tsx`, `PartenairesPro.css`, `contenuPartenaires.ts`), elle
 * garde les comportements que l'ancienne page tenait, et que rien ne
 * verrouillait :
 *
 * 1. prix mensuel, crédits inclus, crédit supplémentaire et coût par livrable
 *    sont ceux de l'API — servis ici à des valeurs que personne n'écrirait de
 *    mémoire (137 €, 3 crédits…). Le coût par livrable servi n'est
 *    VOLONTAIREMENT PAS le quotient du prix par les crédits : une page qui le
 *    recalculerait afficherait autre chose que ce que le serveur a rendu ;
 *    la fourchette du « calcul » est déduite de ces coûts-là ;
 * 2. tant que l'API n'a pas répondu, aucun tarif n'est dans le DOM — les seuls
 *    montants de la page sont alors ceux que la cliente écrit dans son texte
 *    (`contenu.ts` : le droit d'entrée, le prix d'un cabinet) ;
 * 3. une panne se dit — dans UNE région d'alerte — et ne se lit ni comme un
 *    prix ni comme un vide (règle 1) ; une réponse 200 mal formée est une
 *    panne, pas un catalogue vide ;
 * 4. une formule à 0 € n'est pas affichée comme gratuite : ni « 0 € », ni
 *    bouton de souscription ; un coût ou un crédit supplémentaire à zéro se
 *    tait ;
 * 5. la formule que le serveur met en avant est MARQUÉE (par un texte, pas
 *    seulement par une couleur), et c'est elle que l'appel final propose ;
 * 6. chaque bouton de souscription porte le code de SA formule, à la même
 *    adresse qu'avant (`/inscription?formule=…`) ;
 * 7. RIEN de ce que la page disait n'a disparu : chaque phrase de `contenu.ts`
 *    attendue sur la page est dans le DOM, et les phrases que l'ancienne page
 *    écrivait dans son TSX aussi ;
 * 8. aucun lien ne mène à l'ancien site (`www.evkha.fr`), l'ancien menu et le
 *    pied propre à la page ont disparu : barre et pied sont ceux du socle ;
 * 9. aucun montant n'est écrit dans les sources de la page, et le coût par
 *    livrable n'y est pas recalculé — la classe du défaut (règle 4).
 *
 * Contre-épreuves (règle 6) : le reste de la page s'affiche sans tarif ; une
 * formule sans sous-titre ni avantage s'affiche quand même ; les détecteurs
 * voient bien un montant, une division, un lien vers l'ancien site.
 *
 * PAS ENCORE JOUÉ au moment de son écriture (machine à court de mémoire,
 * consigne du lot : ni `vitest` ni `tsc`) : ni contre la nouvelle page, ni
 * contre l'ancienne, ni par mutation. Tant qu'il n'a pas tourné, il ne
 * verrouille rien (règle 6). À rejouer, puis à éprouver par mutations de la
 * nouvelle page, une à la fois : un « 129 € » écrit en dur dans une carte ;
 * le coût recalculé (`prix / crédits`) ; la fourchette écrite en dur ; le
 * code `pro` remis en dur dans l'appel final ; la marque de mise en avant
 * retirée ; `lisible` retiré du prix (« 0 € » affiché) ; l'alerte muette ; le
 * bandeau du crédit retiré.
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

import {
  APPEL_FINAL,
  CALCUL,
  FAQ,
  FONDATRICE,
  FORMULES_SOUS_TITRES,
  HERO,
  POUR_QUI,
  PREUVES,
  PRINCIPE,
} from "../public/contenu";
import { DEMONSTRATION, FORMULES_PRO, OUVERTURE_PRO, PORTRAIT_PRO } from "../public/contenuPartenaires";
import { PIED } from "../public/contenuSite";
import { Partenaires } from "../public/Partenaires";
import { server } from "./server";

// L'adresse que `donnees.ts` construit réellement : l'origine de jsdom, et
// non l'origine fixe de `server.ts`. Une requête sans gestionnaire partirait
// sur le réseau et échouerait — le cas « panne » passerait alors pour une
// mauvaise raison.
const FORMULES_API = `${window.location.origin}/api/public/formules/`;

type Formule = {
  code: string;
  libelle: string;
  credits_par_echeance: number;
  prix_mensuel_cents: number;
  prix_credit_supplementaire_cents: number;
  cout_par_livrable_cents: number;
  devise: string;
  avantages: string[];
  mise_en_avant: boolean;
};

function formule(
  code: string,
  libelle: string,
  credits: number,
  prix: number,
  supplementaire: number,
  cout: number,
  avantages: string[],
  mise_en_avant = false,
): Formule {
  return {
    code,
    libelle,
    credits_par_echeance: credits,
    prix_mensuel_cents: prix,
    prix_credit_supplementaire_cents: supplementaire,
    cout_par_livrable_cents: cout,
    devise: "EUR",
    avantages,
    mise_en_avant,
  };
}

/** Le catalogue servi. Les libellés portent un mot que la page n'écrit nulle
 *  part (« Atelier », « Cabinet »…) : s'il s'affiche, il vient d'ici. Les
 *  coûts par livrable ne sont PAS prix ÷ crédits (137 ÷ 3 = 45,67 ; servi :
 *  47,10) : un coût recalculé par la page se verrait. */
const SOLO = formule("solo", "Solo Atelier", 3, 13700, 5300, 4710, ["Marque blanche Atelier", "Assistance par courriel"]);
const PRO = formule("pro", "Pro Cabinet", 5, 22300, 4700, 4390, ["Marque blanche Cabinet", "Assistance prioritaire"], true);
const PRO_PLUS = formule("pro-plus", "Pro+ Volume", 9, 39100, 4300, 4120, ["Marque blanche Volume", "Interlocuteur attitré"]);
const STRUCTURE = formule("structure", "Structure Réseau", 14, 61900, 4100, 3980, ["Marque blanche Réseau", "Comptes multiples"]);
const DU_SERVEUR = [SOLO, PRO, PRO_PLUS, STRUCTURE];

/** Ce que chaque carte doit afficher, écrit ICI en toutes lettres. */
const ATTENDUS: {
  formule: Formule;
  prix: string;
  credits: string;
  supplementaire: string;
  cout: string;
  recalcule: string;
}[] = [
  { formule: SOLO, prix: "137 €", credits: "3 crédits inclus chaque mois", supplementaire: "53 €", cout: "47,10 €", recalcule: "45,67 €" },
  { formule: PRO, prix: "223 €", credits: "5 crédits inclus chaque mois", supplementaire: "47 €", cout: "43,90 €", recalcule: "44,60 €" },
  { formule: PRO_PLUS, prix: "391 €", credits: "9 crédits inclus chaque mois", supplementaire: "43 €", cout: "41,20 €", recalcule: "43,44 €" },
  { formule: STRUCTURE, prix: "619 €", credits: "14 crédits inclus chaque mois", supplementaire: "41 €", cout: "39,80 €", recalcule: "44,21 €" },
];

type Reponse = () => Response | Promise<Response>;

function servir(reponse: Reponse) {
  server.use(http.get(FORMULES_API, reponse));
}

const lesFormules = (liste: object[]): Reponse => () => HttpResponse.json({ formules: liste });
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

/** Les cartes de formule, dans l'ordre du DOM. */
function cartes(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>(".pro-formule"));
}

function carte(code: string): HTMLElement {
  const trouvee = cartes().find((c) => c.dataset.code === code);
  if (!trouvee) throw new Error(`carte introuvable : ${code}`);
  return trouvee;
}

function section(id: string): HTMLElement {
  const trouvee = document.getElementById(id);
  if (!trouvee) throw new Error(`section introuvable : #${id}`);
  return trouvee;
}

/** L'emplacement du coût par livrable, dans la démonstration du calcul. */
function coutDuCalcul(): string {
  return texteDe(document.querySelector("#calcul .pro-demo-cout"));
}

async function cartesChargees(nombre: number) {
  await waitFor(() => expect(cartes()).toHaveLength(nombre));
}

async function catalogueRepondu() {
  await waitFor(() => expect(screen.queryByText(/Chargement des formules/)).toBeNull());
}

/** Un montant en euros, où qu'il soit. */
const MONTANT = /\d\s*€/;
const MONTANT_ECRIT = /\d[\d\s.,]*(?:€|euros?\b)/i;
/** « 0 € », et non la fin de « 130 € ». */
const ZERO_EURO = /(?<![\d,.])0 €/;

/** Tous les montants d'un texte, sans leurs espaces : « 47,10€ ». */
function montants(brut: string): string[] {
  return (espaces(brut).match(/\d[\d\s.,]*€/g) ?? []).map((m) => m.replace(/\s/g, ""));
}

/** Toutes les phrases d'un objet de contenu, à plat. */
function phrases(valeur: unknown): string[] {
  if (typeof valeur === "string") return [valeur];
  if (Array.isArray(valeur)) return valeur.flatMap(phrases);
  if (valeur && typeof valeur === "object") return Object.values(valeur).flatMap(phrases);
  return [];
}

/** Le texte de la cliente attendu sur la page. */
const TEXTE_DE_LA_CLIENTE = { HERO, PREUVES, PRINCIPE, POUR_QUI, CALCUL, FONDATRICE, FAQ, APPEL_FINAL };

/** Les montants que la cliente écrit dans SON texte (le droit d'entrée, le
 *  prix d'un cabinet) : les seuls que la page peut afficher sans les tenir du
 *  serveur. Lus dans `contenu.ts`, jamais recopiés ici. */
const MONTANTS_DE_LA_CLIENTE = new Set(phrases(TEXTE_DE_LA_CLIENTE).flatMap(montants));

/** Les prix du site d'aujourd'hui, cités par l'ancienne page : aucun ne doit
 *  apparaître quand l'API en rend d'autres. */
const PRIX_CONNUS = ["129 €", "42,90 €", "64,50 €"];

/** Un lien vers l'ancien site (pas une adresse de courriel `@evkha.fr`). */
const ANCIEN_SITE = /(?<!@)(?:www\.)?evkha\.fr(?![\w-])/i;
const ANCIEN_CDN = /cloudfront\.net|d1yei2z3i6k35z/i;

/** Le coût par livrable recalculé : le prix divisé, ou une division par les
 *  crédits. */
const RECALCUL = /prix_mensuel_cents\s*\/|\/\s*[\w.?]*credits_par_echeance/;

function sansCommentaires(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

function source(fichier: string): string {
  return readFileSync(join(process.cwd(), "src", "public", fichier), "utf-8");
}

const SOURCES_DU_LOT = ["Partenaires.tsx", "contenuPartenaires.ts", "PartenairesPro.css"];

describe("la page des partenaires lit ses formules au serveur", () => {
  // La page déduit l'entrée courante de la barre du chemin : on la rend à
  // son adresse.
  beforeEach(() => window.history.pushState({}, "", "/partenaires"));
  afterEach(() => window.history.pushState({}, "", "/"));

  // Règle 1 : les collectes sur lesquelles les tests s'appuient ne sont pas
  // vides.
  it("le texte de la cliente porte bien les montants qu'elle écrit elle-même", () => {
    // Le droit d'entrée (`PREUVES`) et le prix d'un cabinet (`CALCUL`) : lus
    // dans `contenu.ts`, pas recopiés ici.
    expect(MONTANTS_DE_LA_CLIENTE.size).toBeGreaterThanOrEqual(2);
    expect(DEMONSTRATION.cabinet).not.toBeNull();
    expect(MONTANTS_DE_LA_CLIENTE.has((DEMONSTRATION.cabinet?.montant ?? "").replace(/\s/g, ""))).toBe(true);
  });

  // ── Les chiffres viennent du serveur ──────────────────────────────────────

  it("affiche le prix, les crédits, le crédit supplémentaire et le coût par livrable que l'API rend", async () => {
    servir(lesFormules(DU_SERVEUR));
    render(<Partenaires />);
    await cartesChargees(4);

    // Dans l'ordre du serveur.
    expect(cartes().map((c) => c.dataset.code)).toEqual(DU_SERVEUR.map((f) => f.code));

    for (const attendu of ATTENDUS) {
      const { code, libelle, avantages } = attendu.formule;
      const c = carte(code);
      expect(within(c).getByRole("heading", { level: 3 }), code).toHaveTextContent(libelle);
      expect(texteDe(c.querySelector(".pro-prix")), code).toBe(`${attendu.prix} / mois`);
      // Le coût par livrable est celui du SERVEUR, pas prix ÷ crédits.
      expect(texteDe(c.querySelector(".pro-cout")), code).toBe(`Soit ${attendu.cout} par livrable inclus`);
      expect(texteDe(c), code).not.toContain(attendu.recalcule);
      expect(texteDe(c), code).toContain(attendu.credits);
      expect(texteDe(c), code).toContain(`Crédit supplémentaire : ${attendu.supplementaire}`);
      expect(texteDe(c), code).toContain(FORMULES_SOUS_TITRES[code]);
      expect(texteDe(c), code).toContain("Ce que vous obtenez :");
      for (const avantage of avantages) expect(texteDe(c), code).toContain(avantage);
      // Les montants de la carte sont EXACTEMENT les trois que l'API a rendus
      // pour elle.
      expect(montants(texteDe(c)).sort(), code).toEqual(
        [attendu.prix, attendu.cout, attendu.supplementaire].map((m) => m.replace(/\s/g, "")).sort(),
      );
    }

    // La fourchette du calcul : du coût le plus bas au plus haut.
    expect(coutDuCalcul()).toContain("de 39,80 € à 47,10 €");
    expect(coutDuCalcul()).toContain(CALCUL.colonnes[0].titre);

    // Sur toute la page : aucun montant qui ne vienne ni de l'API, ni du
    // texte de la cliente.
    const permis = new Set([
      ...MONTANTS_DE_LA_CLIENTE,
      ...ATTENDUS.flatMap((a) => [a.prix, a.cout, a.supplementaire]).map((m) => m.replace(/\s/g, "")),
    ]);
    const affiches = montants(texte());
    expect(affiches.length).toBeGreaterThanOrEqual(14);
    for (const montant of affiches) expect(permis.has(montant), `« ${montant} » ne vient de nulle part`).toBe(true);
    for (const prix of PRIX_CONNUS) {
      expect(texte(), `« ${prix} » est écrit en dur quelque part`).not.toContain(prix);
    }

    expect(alerte()).toBeEmptyDOMElement();
    expect(texte()).not.toContain("momentanément indisponible");
    expect(document.querySelector(".acc-btn-inactif")).toBeNull();
  });

  it("accorde « crédit » sur le nombre reçu, et se tait sur un nombre qui n'en est pas un", async () => {
    servir(
      lesFormules([
        { ...SOLO, credits_par_echeance: 1 },
        { ...PRO, credits_par_echeance: 0 },
        { ...PRO_PLUS, credits_par_echeance: null },
      ]),
    );
    render(<Partenaires />);
    await cartesChargees(3);

    expect(texteDe(carte("solo"))).toContain("1 crédit inclus chaque mois");
    expect(texteDe(carte("solo"))).not.toContain("crédits inclus");
    expect(texteDe(carte("pro"))).not.toMatch(/crédits? inclus/);
    expect(texteDe(carte("pro-plus"))).not.toMatch(/crédits? inclus/);
    expect(texteDe(carte("pro-plus"))).not.toMatch(/null|NaN|undefined/);
  });

  it("tant que l'API n'a pas répondu, aucun tarif n'est dans le DOM", async () => {
    servir(muet);
    render(<Partenaires />);

    expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
    // Les seuls montants de la page sont ceux du texte de la cliente.
    for (const montant of montants(texte())) {
      expect(MONTANTS_DE_LA_CLIENTE.has(montant), `« ${montant} » affiché avant la réponse`).toBe(true);
    }
    expect(texteDe(section("formules"))).not.toMatch(MONTANT);
    expect(coutDuCalcul()).not.toMatch(MONTANT);
    // L'attente se dit, elle ne laisse pas un trou — et ce n'est pas une panne.
    expect(screen.getByRole("status")).toHaveTextContent(/Chargement des formules/);
    expect(coutDuCalcul()).toContain("Tarif en cours de chargement");
    expect(alerte()).toBeEmptyDOMElement();
    expect(cartes()).toHaveLength(0);
    // Sans formule connue, l'appel final mène aux formules plutôt qu'à une
    // formule devinée.
    expect(document.querySelector("#souscrire a")).toHaveAttribute("href", "#formules");
    expect(document.querySelector("#souscrire a")).toHaveTextContent("Découvrir les formules");
    expect(texte()).not.toMatch(/inscription\?formule/);
    expect(document.querySelector('a[href*="/inscription"]')).toBeNull();
  });

  it("si l'API échoue, la page le dit et n'affiche aucun tarif", async () => {
    servir(panne);
    render(<Partenaires />);

    await waitFor(() => expect(alerte()).toHaveTextContent(/tarifs sont momentanément indisponibles/));
    await catalogueRepondu();
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(alerte().querySelector("a")).toHaveAttribute("href", "mailto:contact@evkha.fr");
    // La section des formules reste et dit sa panne, sans carte ni phrase de
    // vide.
    expect(document.querySelector("#formules .acc-panne")).toHaveTextContent(/momentanément indisponible/);
    expect(cartes()).toHaveLength(0);
    expect(texte()).not.toContain("Aucune formule");
    expect(coutDuCalcul()).toContain("Tarif momentanément indisponible");
    expect(texteDe(section("formules"))).not.toMatch(MONTANT);
    expect(coutDuCalcul()).not.toMatch(MONTANT);
    for (const montant of montants(texte())) {
      expect(MONTANTS_DE_LA_CLIENTE.has(montant), `« ${montant} » affiché pendant la panne`).toBe(true);
    }
    expect(texte()).not.toContain("∞");
    expect(document.querySelector("#souscrire a")).toHaveAttribute("href", "#formules");
  });

  // Une réponse 200 qui ne porte pas la liste attendue — `{}`, ou la page
  // d'un relais servie à la place de l'API — n'est pas un catalogue vide.
  for (const [nom, reponse] of [
    ["un objet sans la clé attendue", () => HttpResponse.json({})],
    ["une clé mal nommée", () => HttpResponse.json({ formule: [] })],
    ["une liste nue", () => HttpResponse.json([SOLO, PRO])],
    [
      "la page d'un relais",
      () => new HttpResponse("<!doctype html><title>EVKHA</title>", { headers: { "Content-Type": "text/html" } }),
    ],
  ] as [string, Reponse][]) {
    it(`une réponse 200 mal formée (${nom}) est une panne dite, pas un catalogue vide`, async () => {
      servir(reponse);
      render(<Partenaires />);

      await waitFor(() => expect(alerte()).toHaveTextContent(/momentanément indisponible/));
      await catalogueRepondu();
      expect(cartes()).toHaveLength(0);
      expect(texte()).not.toContain("Aucune formule");
      expect(texte()).not.toContain("Indisponible pour le moment");
      expect(texteDe(section("formules"))).not.toMatch(MONTANT);
      expect(coutDuCalcul()).not.toMatch(MONTANT);
    });
  }

  it("un catalogue reçu VIDE : ni tarif, ni panne — la page dit qu'il n'y a rien à souscrire", async () => {
    servir(lesFormules([]));
    render(<Partenaires />);

    await catalogueRepondu();
    expect(await screen.findByText(/Aucune formule n'est proposée pour le moment/)).toBeInTheDocument();
    expect(alerte()).toBeEmptyDOMElement();
    expect(coutDuCalcul()).toContain("Indisponible pour le moment");
    expect(coutDuCalcul()).not.toMatch(MONTANT);
    expect(texte()).not.toContain("∞");
    expect(document.querySelector("#souscrire a")).toHaveAttribute("href", "#formules");
  });

  // ── Une formule sans prix n'est pas gratuite ──────────────────────────────

  it("une formule à 0 € n'est pas affichée comme gratuite : ni « 0 € », ni bouton de souscription", async () => {
    // La formule à zéro est celle dont le coût par livrable est le plus bas :
    // la fourchette doit l'ignorer.
    servir(lesFormules([SOLO, PRO, PRO_PLUS, { ...STRUCTURE, prix_mensuel_cents: 0 }]));
    render(<Partenaires />);
    await cartesChargees(4);

    const gratuite = carte("structure");
    expect(within(gratuite).getByText("Indisponible pour le moment")).toBeInTheDocument();
    expect(gratuite.querySelector(".pro-prix")).toBeNull();
    expect(gratuite.querySelector(".pro-cout")).toBeNull();
    expect(gratuite.querySelector(".acc-btn-inactif")).toHaveAttribute("aria-disabled", "true");
    expect(gratuite.querySelector("a")).toBeNull();
    // Elle reste visible, avec son nom : une formule ne disparaît pas.
    expect(within(gratuite).getByRole("heading", { level: 3 })).toHaveTextContent("Structure Réseau");

    expect(texteDe(section("formules"))).not.toMatch(ZERO_EURO);
    expect(coutDuCalcul()).not.toMatch(ZERO_EURO);
    expect(texteDe(section("formules"))).not.toMatch(/gratuit|offert/i);
    expect(coutDuCalcul()).toContain("de 41,20 € à 47,10 €");
    // Les autres se vendent toujours.
    expect(carte("solo").querySelector("a")).toHaveAttribute("href", "/inscription?formule=solo");
  });

  for (const [nom, prix] of [
    ["négatif", -100],
    ["absent", undefined],
    ["nul", null],
    ["une chaîne", "129"],
  ] as [string, unknown][]) {
    it(`un prix ${nom} n'est pas un prix : la formule se dit indisponible`, async () => {
      servir(lesFormules([SOLO, { ...PRO, prix_mensuel_cents: prix }]));
      render(<Partenaires />);
      await cartesChargees(2);

      expect(texteDe(carte("pro"))).toContain("Indisponible pour le moment");
      expect(carte("pro").querySelector("a")).toBeNull();
      expect(texteDe(carte("pro"))).not.toMatch(/NaN|undefined|null|-1/);
      // La formule mise en avant ne se vend pas : l'appel final ne la propose
      // pas.
      expect(document.querySelector("#souscrire a")).toHaveAttribute("href", "#formules");
    });
  }

  it("un coût par livrable ou un crédit supplémentaire à zéro se tait, sans « 0 € »", async () => {
    servir(lesFormules([{ ...SOLO, cout_par_livrable_cents: 0, prix_credit_supplementaire_cents: 0 }, PRO]));
    render(<Partenaires />);
    await cartesChargees(2);

    const c = carte("solo");
    expect(texteDe(c.querySelector(".pro-prix"))).toBe("137 € / mois");
    expect(c.querySelector(".pro-cout")).toBeNull();
    expect(texteDe(c)).not.toContain("Crédit supplémentaire");
    expect(texteDe(c)).not.toContain("par livrable");
    expect(texteDe(section("formules"))).not.toMatch(ZERO_EURO);
    // Elle se vend quand même, et la fourchette ne compte que le coût connu.
    expect(c.querySelector("a")).toHaveAttribute("href", "/inscription?formule=solo");
    expect(coutDuCalcul()).toContain("43,90 €");
    expect(coutDuCalcul()).not.toContain("de ");
  });

  // ── La formule mise en avant ──────────────────────────────────────────────

  it("la formule que le serveur met en avant est marquée, par un texte, et c'est elle que l'appel final propose", async () => {
    servir(lesFormules(DU_SERVEUR));
    render(<Partenaires />);
    await cartesChargees(4);

    const marquees = cartes().filter((c) => c.classList.contains("pro-formule-avant"));
    expect(marquees.map((c) => c.dataset.code)).toEqual(["pro"]);
    expect(texteDe(marquees[0])).toContain(FORMULES_PRO.enAvant);
    for (const code of ["solo", "pro-plus", "structure"]) {
      expect(texteDe(carte(code)), code).not.toContain(FORMULES_PRO.enAvant);
    }

    const appel = document.querySelector("#souscrire a");
    expect(appel).toHaveAttribute("href", "/inscription?formule=pro");
    expect(appel).toHaveTextContent("Choisir la formule Pro Cabinet");
  });

  it("la marque suit le serveur : une autre formule mise en avant, ou aucune", async () => {
    servir(lesFormules([SOLO, { ...PRO, mise_en_avant: false }, PRO_PLUS, { ...STRUCTURE, mise_en_avant: true }]));
    const premiere = render(<Partenaires />);
    await cartesChargees(4);

    expect(cartes().filter((c) => c.classList.contains("pro-formule-avant")).map((c) => c.dataset.code)).toEqual(["structure"]);
    expect(texteDe(carte("pro"))).not.toContain(FORMULES_PRO.enAvant);
    expect(document.querySelector("#souscrire a")).toHaveAttribute("href", "/inscription?formule=structure");
    expect(document.querySelector("#souscrire a")).toHaveTextContent("Choisir la formule Structure Réseau");
    premiere.unmount();

    // Aucune : pas de marque, et l'appel final ne devine pas une formule.
    servir(lesFormules(DU_SERVEUR.map((f) => ({ ...f, mise_en_avant: false }))));
    render(<Partenaires />);
    await cartesChargees(4);
    expect(document.querySelector(".pro-formule-avant")).toBeNull();
    expect(texte()).not.toContain(FORMULES_PRO.enAvant);
    expect(document.querySelector("#souscrire a")).toHaveAttribute("href", "#formules");
  });

  // ── Les boutons de souscription ───────────────────────────────────────────

  it("chaque bouton de souscription porte le code de SA formule, à l'adresse d'avant", async () => {
    // Un code qui doit être encodé : il voyage dans l'adresse.
    const etrange = formule("pro plus&x=1", "Sur Mesure", 4, 17900, 4900, 4470, []);
    servir(lesFormules([...DU_SERVEUR, etrange]));
    render(<Partenaires />);
    await cartesChargees(5);

    for (const f of DU_SERVEUR) {
      // UN lien dans la carte : celui de la souscription.
      const liens = within(carte(f.code)).getAllByRole("link");
      expect(liens, f.code).toHaveLength(1);
      expect(liens[0], f.code).toHaveAttribute("href", `/inscription?formule=${f.code}`);
      expect(liens[0], f.code).toHaveTextContent(`Souscrire à ${f.libelle}`);
    }
    expect(within(carte(etrange.code)).getByRole("link")).toHaveAttribute(
      "href",
      "/inscription?formule=pro%20plus%26x%3D1",
    );
    // Autant de liens de souscription que de formules, plus celui de l'appel
    // final ; aucun ne mène à la connexion.
    const souscriptions = Array.from(document.querySelectorAll('a[href^="/inscription"]'));
    expect(souscriptions).toHaveLength(6);
    for (const lien of souscriptions) expect(lien.getAttribute("href")).toMatch(/^\/inscription\?formule=/);
  });

  it("contre-épreuve : une formule sans sous-titre ni avantage s'affiche quand même ; une entrée sans code, non", async () => {
    const sobre = { ...formule("decouverte", "Découverte", 2, 9700, 5900, 5010, []), avantages: undefined };
    servir(lesFormules([sobre, { libelle: "Sans code", prix_mensuel_cents: 100 }, null, PRO]));
    render(<Partenaires />);
    await cartesChargees(2);

    const c = carte("decouverte");
    expect(within(c).getByRole("heading", { level: 3 })).toHaveTextContent("Découverte");
    expect(texteDe(c.querySelector(".pro-prix"))).toBe("97 € / mois");
    expect(texteDe(c)).toContain("2 crédits inclus chaque mois");
    expect(c.querySelector(".pro-formule-cible")).toBeNull();
    expect(within(c).getByRole("link")).toHaveAttribute("href", "/inscription?formule=decouverte");
    expect(texte()).not.toContain("Sans code");
    // La fourchette la compte : c'est une formule en vente.
    expect(coutDuCalcul()).toContain("de 43,90 € à 50,10 €");
  });

  // ── Rien de ce que la page disait n'a disparu ─────────────────────────────

  it("chaque phrase de contenu.ts attendue sur la page y est", async () => {
    servir(lesFormules(DU_SERVEUR));
    render(<Partenaires />);
    await cartesChargees(4);

    const page = texte();
    const attendues = [...phrases(TEXTE_DE_LA_CLIENTE), ...phrases(FORMULES_SOUS_TITRES)];
    // Règle 1 : une collecte vide ferait passer la boucle sans rien vérifier.
    expect(attendues.length).toBeGreaterThan(60);
    for (const phrase of attendues) {
      expect(page, `la page ne dit plus : « ${phrase} »`).toContain(espaces(phrase));
    }

    // L'ouverture : le titre en TROIS lignes, dans le h1, dans l'ordre.
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1.querySelectorAll(".acc-ligne-titre")).toHaveLength(3);
    expect(texteDe(h1).replace(/\s+/g, " ").trim()).toBe(HERO.titre.join(" "));
    // La promesse faite au professionnel, dans les mots de la cliente.
    expect(texteDe(document.querySelector(".pro-promesse"))).toBe(HERO.corps[1]);
    expect(texteDe(document.querySelector(".pro-signature"))).toBe(HERO.signature);

    // Le principe : quatre étapes, dans l'ordre, dans une liste ordonnée ; le
    // bandeau du crédit, entier.
    const etapes = Array.from(document.querySelectorAll("ol.pro-etapes > li h3")).map((t) => t.textContent);
    expect(etapes).toEqual(PRINCIPE.etapes.map((e) => e.titre));
    expect(texteDe(document.querySelector(".pro-bandeau"))).toBe(PRINCIPE.bandeau);
    expect(texteDe(document.querySelector(".pro-bandeau strong"))).toBe("1 crédit = 1 livrable au choix");

    // Les trois preuves, les trois cibles, les trois colonnes du calcul.
    expect(document.querySelectorAll(".pro-preuves > li")).toHaveLength(PREUVES.length);
    expect(document.querySelectorAll(".pro-cibles > li")).toHaveLength(POUR_QUI.cibles.length);
    expect(document.querySelectorAll("#calcul h3")).toHaveLength(CALCUL.colonnes.length);
    // Ce qu'un cabinet facture est LU dans la phrase de la cliente.
    expect(CALCUL.colonnes[0].corps).toContain(DEMONSTRATION.cabinet?.montant ?? "introuvable");
    expect(texteDe(document.querySelector(".pro-demo-cabinet"))).toContain(
      espaces(`${DEMONSTRATION.cabinet?.avant} ${DEMONSTRATION.cabinet?.montant}`),
    );

    // Les questions en <details>, la première ouverte.
    const questions = Array.from(document.querySelectorAll("#questions details"));
    expect(questions).toHaveLength(FAQ.questions.length);
    expect(questions[0]).toHaveAttribute("open");
    expect(questions[1]).not.toHaveAttribute("open");

    // Ce que l'ancienne page écrivait dans son TSX.
    for (const phrase of [
      "Quatre formules, zéro droit d'entrée",
      "Abonnement mensuel avec crédits inclus.",
      "TVA non applicable, article 293 B du CGI.",
      "Engagement minimum de 3 mois, puis sans engagement.",
      "Crédits supplémentaires à tarif dégressif.",
    ]) {
      expect(page, `la page ne dit plus : « ${phrase} »`).toContain(phrase);
    }
    expect(screen.getByRole("link", { name: /Découvrir les formules/ })).toHaveAttribute("href", "#formules");
    expect(document.getElementById("formules")).not.toBeNull();
    expect(screen.getByRole("link", { name: /Créer son espace client/ })).toHaveAttribute("href", "/espace/connexion");

    // Le renvoi vers les études à l'unité.
    const passerelle = section("a-l-unite");
    expect(texteDe(passerelle)).toContain(CALCUL.liseré);
    expect(within(passerelle).getByRole("link")).toHaveAttribute("href", "/etudes");

    // Les deux images, à leur place réservée.
    for (const [selecteur, image] of [
      ["img.pro-image", OUVERTURE_PRO.image],
      ["img.pro-portrait", PORTRAIT_PRO],
    ] as [string, { adresse: string; alt: string }][]) {
      const photo = document.querySelector<HTMLImageElement>(selecteur);
      expect(photo, selecteur).toHaveAttribute("src", image.adresse);
      expect(image.adresse).toMatch(/^\/partenaires\//);
      expect(photo).toHaveAttribute("alt", image.alt);
      expect(image.alt.length).toBeGreaterThan(10);
      expect(Number(photo?.getAttribute("width"))).toBeGreaterThan(0);
      expect(Number(photo?.getAttribute("height"))).toBeGreaterThan(0);
    }
  });

  it("contre-épreuve : le reste de la page s'affiche même sans tarif", async () => {
    servir(panne);
    render(<Partenaires />);
    await waitFor(() => expect(alerte()).not.toBeEmptyDOMElement());

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(HERO.titre[0]);
    expect(document.title).toBe("Études et business plans sous votre marque, pour les pros — EVKHA");
    const page = texte();
    for (const phrase of phrases(TEXTE_DE_LA_CLIENTE)) {
      expect(page, `sans tarif, la page ne dit plus : « ${phrase} »`).toContain(espaces(phrase));
    }
    expect(document.querySelectorAll("#questions details")).toHaveLength(FAQ.questions.length);
    expect(within(section("a-l-unite")).getByRole("link")).toHaveAttribute("href", "/etudes");
  });

  // ── Barre et pied du socle, aucun lien vers l'ancien site ─────────────────

  it("aucun lien ne mène à l'ancien site ; la barre et le pied sont ceux du socle", async () => {
    servir(lesFormules(DU_SERVEUR));
    render(<Partenaires />);
    await cartesChargees(4);

    const liens = Array.from(document.querySelectorAll<HTMLAnchorElement>("a[href]"));
    expect(liens.length).toBeGreaterThan(30);
    for (const lien of liens) {
      const adresse = lien.getAttribute("href") ?? "";
      if (adresse.startsWith("mailto:")) continue;
      expect(adresse, lien.textContent ?? "").not.toMatch(ANCIEN_SITE);
      expect(adresse, lien.textContent ?? "").not.toMatch(ANCIEN_CDN);
    }
    for (const image of Array.from(document.querySelectorAll("img"))) {
      expect(image.getAttribute("src") ?? "").not.toMatch(ANCIEN_CDN);
    }

    // UN pied, celui du socle : les liens légaux y sont, lus dans `PIED`.
    const pieds = screen.getAllByRole("contentinfo");
    expect(pieds).toHaveLength(1);
    expect(PIED.liens.length).toBeGreaterThan(0);
    for (const { libelle, lien } of PIED.liens) {
      expect(within(pieds[0]).getByRole("link", { name: libelle })).toHaveAttribute("href", lien);
    }
    // L'ancienne charte n'est plus là : ni classe `pp-`, ni ancien menu.
    expect(document.querySelector('[class*="pp-"], .pp')).toBeNull();
    expect(document.querySelector(".acc.pro")).not.toBeNull();
    // Aucun formulaire qui n'envoie rien.
    expect(document.querySelector("form, input, textarea, select")).toBeNull();
  });

  for (const fichier of SOURCES_DU_LOT) {
    it(`${fichier} ne pointe ni vers l'ancien site, ni vers son CDN`, () => {
      const brute = source(fichier);
      // Règle 1 : un fichier vide ou introuvable ne « passe » pas.
      expect(brute.length, fichier).toBeGreaterThan(2000);
      // Commentaires COMPRIS pour `www.` et le CDN : une adresse citée
      // reviendrait au prochain copier-coller.
      expect(brute.match(/www\.evkha\.fr/gi) ?? [], fichier).toEqual([]);
      expect(brute.match(new RegExp(ANCIEN_CDN.source, "gi")) ?? [], fichier).toEqual([]);
    });
  }

  it("la page n'importe plus l'ancienne feuille ni l'ancien menu", () => {
    const code = sansCommentaires(source("Partenaires.tsx"));
    expect(code).toMatch(/import "\.\/Site\.css";\s*import "\.\/PartenairesPro\.css";/);
    expect(code).not.toMatch(/Partenaires\.css/);
    expect(code).not.toMatch(/MenuSite/);
    expect(code).not.toMatch(/<footer\b/);
    // La feuille de la page ne porte que des classes à elle.
    const feuille = source("PartenairesPro.css").replace(/\/\*[\s\S]*?\*\//g, "");
    expect(feuille).toMatch(/\.pro-formule\b/);
    expect(feuille.match(/\.pp-[\w-]+/g) ?? []).toEqual([]);
  });

  // ── La page se laisse conduire ────────────────────────────────────────────

  it("un seul h1, des titres sans saut de niveau, un lien d'évitement qui vise le contenu", async () => {
    servir(lesFormules(DU_SERVEUR));
    render(<Partenaires />);
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

    // Rien de focalisable sous `aria-hidden`.
    const caches = Array.from(document.querySelectorAll("[aria-hidden='true']"));
    expect(caches.length).toBeGreaterThan(10);
    for (const cache of caches) {
      expect(cache.querySelector("a, button, input, select, textarea, summary, [tabindex]"), cache.className).toBeNull();
    }
    // Chaque image dit ce qu'elle est.
    const images = Array.from(document.querySelectorAll("img"));
    expect(images.length).toBeGreaterThanOrEqual(2);
    for (const image of images) {
      expect(image.hasAttribute("alt"), image.getAttribute("src") ?? "").toBe(true);
    }
  });

  it("les deux boutons de pause partagent un seul état, qui arrête le ruban", async () => {
    servir(lesFormules(DU_SERVEUR));
    const { container } = render(<Partenaires />);
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

  // ── La classe du défaut : un montant écrit, un coût recalculé ─────────────

  for (const fichier of ["Partenaires.tsx", "contenuPartenaires.ts"]) {
    it(`${fichier} n'écrit aucun montant et ne recalcule pas le coût par livrable`, () => {
      const code = sansCommentaires(source(fichier));
      // Règle 1 : un fichier vide ou introuvable ne « passe » pas.
      expect(code.length).toBeGreaterThan(2000);
      expect(code.match(new RegExp(MONTANT_ECRIT.source, "gi")) ?? []).toEqual([]);
      expect(code.match(new RegExp(RECALCUL.source, "g")) ?? []).toEqual([]);
    });
  }

  it("la page lit bien le coût par livrable du serveur", () => {
    // Règle 1 : l'absence de recalcul ne prouve rien si le champ n'est pas lu.
    expect(sansCommentaires(source("Partenaires.tsx"))).toMatch(/cout_par_livrable_cents/);
    expect(sansCommentaires(source("Partenaires.tsx"))).toMatch(/chargerFormules/);
  });

  it("contre-épreuve : les détecteurs voient un montant, un recalcul, l'ancien site — et rien d'autre", () => {
    for (const faute of ["dès 129 €", "149€", "1 490 € TTC", "64,50 €", "prix: 185 euros"]) {
      expect(faute, faute).toMatch(MONTANT_ECRIT);
    }
    for (const juste of ["sous 24 h", "3 mois", "article 293 B du CGI", "250+", "le signe €", "/(jusqu'à)\\s+(\\d[\\d\\s]*€)/"]) {
      expect(juste, juste).not.toMatch(MONTANT_ECRIT);
    }
    expect(montants(`de${INSECABLE}39,80${FINE_INSECABLE}€ à 47,10 €`)).toEqual(["39,80€", "47,10€"]);
    expect(montants("5 étoiles0 €de droit d'entrée")).toEqual(["0€"]);

    for (const faute of ["0 €", "Soit 0 € par livrable", "(0 €)"]) expect(faute, faute).toMatch(ZERO_EURO);
    for (const juste of ["130 €", "47,10 €", "1290 €"]) expect(juste, juste).not.toMatch(ZERO_EURO);

    for (const faute of [
      "formule.prix_mensuel_cents / formule.credits_par_echeance",
      "Math.round(prix_mensuel_cents/ credits)",
      "total / f.credits_par_echeance",
      "total / formule?.credits_par_echeance",
    ]) {
      expect(faute, faute).toMatch(RECALCUL);
    }
    for (const juste of ["euros(formule.cout_par_livrable_cents)", "lisible(f.prix_mensuel_cents)", "formule.credits_par_echeance > 1"]) {
      expect(juste, juste).not.toMatch(RECALCUL);
    }

    for (const faute of ["https://www.evkha.fr/packs", "https://evkha.fr/", "//www.evkha.fr/contacts", "WWW.EVKHA.FR"]) {
      expect(faute, faute).toMatch(ANCIEN_SITE);
    }
    for (const juste of ["mailto:contact@evkha.fr", "/partenaires", "https://calendly.com/contact-evkha", "/etudes"]) {
      expect(juste, juste).not.toMatch(ANCIEN_SITE);
    }

    // Le collecteur de phrases descend dans les listes et les objets.
    expect(phrases({ a: "un", b: ["deux", { c: "trois", d: 4, e: null }] })).toEqual(["un", "deux", "trois"]);
  });
});

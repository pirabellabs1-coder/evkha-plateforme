/** L'accueil lit ses prix au serveur.
 *
 * La maquette de la page d'accueil portait ses tarifs en dur : « dès 89 € »,
 * des packs et des formations que la plateforme ne vend pas. Portée telle
 * quelle, elle aurait fait une seconde source de prix — celle qui contredit le
 * paiement au premier changement de tarif (règle 5). La page lit donc trois
 * catalogues (`livrables/`, `formules/`, `boutique/`) et CALCULE ses « dès »
 * et ses fourchettes sur ce qu'ils rendent.
 *
 * Les verrous :
 *
 * 1. les prix affichés sont ceux de l'API — servis ici à des montants que
 *    personne n'écrirait de mémoire (151 €, 93 €…), pour qu'un prix recopié
 *    ne puisse pas passer pour un prix lu ;
 * 2. tant que l'API n'a pas répondu, aucun montant n'est dans le DOM ;
 * 3. une panne se dit — dans UNE région d'alerte —, et ne se lit ni comme un
 *    prix ni comme un vide (règle 1) ; une réponse 200 mal formée est une
 *    panne, pas un catalogue vide ;
 * 4. un catalogue reçu vide, une offre à zéro, une formule retirée : la carte
 *    le dit et son bouton est neutralisé ;
 * 5. la carte des structures lit SA formule (par son code), avec le titre et
 *    les avantages du serveur — pas « la plus chère » ;
 * 6. aucun montant n'est écrit dans les sources de la page — la classe du
 *    défaut (règle 4), pas la liste des prix d'aujourd'hui.
 *
 * Contre-épreuves (règle 6) : le reste de la page s'affiche sans prix ; une
 * panne partielle n'éteint pas les prix qui, eux, sont arrivés ; le détecteur
 * de montants voit bien un montant. Rejoué le 19/11/2026 avec un « 149 € »
 * écrit en dur dans `prixDuLivrable` : rouge.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { Accueil } from "../public/Accueil";
import { ETUDES, ETUDES_PAGE } from "../public/contenu";
import { RELECTURE } from "../public/contenuAccueil";
import { server } from "./server";

// L'adresse que `donnees.ts` et `catalogue.ts` construisent réellement :
// l'origine de jsdom, et non l'origine fixe de `server.ts`. Une requête sans
// gestionnaire partirait sur le réseau et échouerait — le cas « panne »
// passerait alors pour une mauvaise raison.
const PUBLIC = `${window.location.origin}/api/public`;

function livrable(slug: string, type: string, prix_cents: number) {
  return { slug, libelle: slug, type, prix_cents };
}

const LIVRABLES = [
  livrable("etude-concurrence", "competitor_study", 9300),
  livrable("etude-marche", "market_study", 15100),
  livrable("business-plan", "business_plan", 18700),
  livrable("strategie-business", "business_strategy", 20300),
];

function formule(code: string, prix_mensuel_cents: number, libelle = code, avantages: string[] = []) {
  return {
    code,
    libelle,
    credits_par_echeance: 2,
    prix_mensuel_cents,
    prix_credit_supplementaire_cents: 5700,
    cout_par_livrable_cents: 6100,
    devise: "EUR",
    avantages,
    mise_en_avant: false,
  };
}

/** La formule des structures, telle que le serveur la décrit. Des mots que
 *  la page ne contient nulle part : s'ils s'affichent, ils viennent d'ici. */
const STRUCTURE = formule("structure", 43300, "Structure Horizon", [
  "Convention sur douze mois",
  "Une référente nommée",
]);

const FORMULES = [formule("pro", 19100), formule("solo", 13100), STRUCTURE];

function produit(slug: string, prix_cents: number, titre = slug) {
  return {
    slug,
    titre,
    theme: "",
    prix_cents,
    devise: "EUR",
    pages: 40,
    mise_a_jour: "",
    image: "",
    note: 0,
    nombre_d_avis: 0,
  };
}

const PRODUITS = [
  produit("foodtrucks", 9100, "Le marché des foodtrucks"),
  produit("chatbots", 7700, "Le marché des chatbots"),
];

type Reponse = () => Response | Promise<Response>;
type Routes = { livrables: Reponse; formules: Reponse; boutique: Reponse };

/** Branche les trois catalogues. Chaque route est donnée séparément, pour
 *  pouvoir en faire tomber une seule. */
function servir(routes: Routes) {
  server.use(
    http.get(`${PUBLIC}/livrables/`, routes.livrables),
    http.get(`${PUBLIC}/formules/`, routes.formules),
    http.get(`${PUBLIC}/boutique/`, routes.boutique),
  );
}

const lesLivrables = (liste: object[]): Reponse => () => HttpResponse.json({ livrables: liste });
const lesFormules = (liste: object[]): Reponse => () => HttpResponse.json({ formules: liste });
const laBoutique = (liste: object[]): Reponse => () =>
  HttpResponse.json({ produits: liste, themes: [], avis: [] });

const recu: Routes = {
  livrables: lesLivrables(LIVRABLES),
  formules: lesFormules(FORMULES),
  boutique: laBoutique(PRODUITS),
};
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

/** Le texte de la page, espaces insécables ramenées à des espaces simples :
 *  comparer sans normaliser ferait dépendre le test de la version d'ICU. */
function texte(): string {
  return espaces(document.body.textContent ?? "");
}

function texteDe(element: Element | null): string {
  return espaces(element?.textContent ?? "");
}

/** La région d'alerte. Elle est TOUJOURS dans le DOM, vide tant que tout va
 *  bien : c'est ce qui la fait annoncer quand une panne y arrive. */
function alerte(): HTMLElement {
  return screen.getByRole("alert");
}

/** Une carte d'offre, par son surtitre EXACT (qui, lui, ne vient jamais du
 *  serveur) : « Vous accompagnez » ouvre aussi une phrase de l'ouverture. */
function carteDOffre(surtitre: string): HTMLElement {
  const carte = screen.getByText(surtitre).closest("article");
  if (!carte) throw new Error(`carte d'offre introuvable : ${surtitre}`);
  return carte;
}

async function prixCharges() {
  await waitFor(() => expect(screen.queryByText(/Tarif en cours de chargement/)).toBeNull());
}

/** Un montant en euros, où qu'il soit. */
const MONTANT = /\d\s*€/;
const MONTANT_ECRIT = /\d[\d\s.,]*(?:€|euros?\b)/i;

/** Les prix du site d'aujourd'hui et ceux de la maquette : aucun ne doit
 *  apparaître quand l'API en rend d'autres. */
const PRIX_CONNUS = ["89 €", "149 €", "185 €", "195 €", "129 €", "189 €", "249 €", "429 €", "495 €", "995 €", "1 490 €", "850 €", "69 €"];

function sansCommentaires(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

describe("l'accueil lit ses prix au serveur", () => {
  it("affiche les prix que l'API rend, et calcule ses « dès » et ses fourchettes dessus", async () => {
    servir(recu);
    render(<Accueil />);

    // La fourchette des livrables sur mesure : du moins cher au plus cher.
    await waitFor(() => expect(texte()).toContain("de 93 € à 203 €"));
    // L'abonnement le moins cher, la formule des structures, et la boutique.
    await waitFor(() => expect(texte()).toContain("dès 131 €"));
    await waitFor(() => expect(texte()).toContain("dès 77 €"));
    expect(texte()).toContain("433 €");
    // Le « dès » de l'atelier est le plancher des livrables, pas un prix fixe.
    expect(texte()).toContain("dès 93 €");
    // La pastille en orbite porte le prix de SON livrable.
    expect(texte()).toContain("Étude de marché · 151 €");

    // Chaque marche du parcours : son prix, et son lien de commande par slug.
    const attendus: [RegExp, string, string][] = [
      [/Mon idée tient-elle/, "151 €", "/inscription?livrable=etude-marche"],
      [/Face à qui/, "93 €", "/inscription?livrable=etude-concurrence"],
      [/Convaincre la banque/, "187 €", "/inscription?livrable=business-plan"],
      [/Passer à l'action/, "203 €", "/inscription?livrable=strategie-business"],
    ];
    for (const [question, prix, lien] of attendus) {
      const marche = screen.getByRole("link", { name: question });
      expect(marche).toHaveAttribute("href", lien);
      expect(texteDe(marche)).toContain(prix);
    }

    for (const prix of PRIX_CONNUS) {
      expect(texte(), `« ${prix} » est écrit en dur quelque part`).not.toContain(prix);
    }
    expect(alerte()).toBeEmptyDOMElement();
    expect(texte()).not.toContain("momentanément indisponible");
    expect(document.querySelector(".acc-btn-inactif")).toBeNull();
  });

  it("tant que l'API n'a pas répondu, aucun montant n'est dans le DOM", async () => {
    servir({ livrables: muet, formules: muet, boutique: muet });
    render(<Accueil />);

    expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
    expect(texte()).not.toMatch(MONTANT);
    // L'attente se dit, elle ne laisse pas un trou — et ce n'est pas une panne.
    expect(screen.getAllByText(/Tarif en cours de chargement/).length).toBeGreaterThan(0);
    expect(alerte()).toBeEmptyDOMElement();
    // Sans slug connu, une marche mène à la page des études, pas à un lien mort.
    expect(screen.getByRole("link", { name: /Mon idée tient-elle/ })).toHaveAttribute("href", "/etudes");
    // Les études prêtes attendent, sous forme de gabarits sans un chiffre.
    const pretes = document.querySelector("#etudes-pretes");
    expect(pretes).not.toBeNull();
    expect(pretes?.querySelectorAll(".acc-prete-gabarit").length).toBeGreaterThan(0);
    expect(within(pretes as HTMLElement).getByRole("status")).toHaveTextContent(/Chargement des études prêtes/);
  });

  it("si l'API échoue, la page le dit et n'affiche aucun prix", async () => {
    servir({ livrables: panne, formules: panne, boutique: panne });
    render(<Accueil />);

    await waitFor(() => expect(alerte()).toHaveTextContent(/tarifs sont momentanément indisponibles/));
    await prixCharges();
    expect(screen.getAllByText(/Tarif momentanément indisponible/).length).toBeGreaterThanOrEqual(8);
    expect(texte()).not.toMatch(MONTANT);
    expect(texte()).not.toContain("∞");
    // Les études prêtes : la section reste et dit sa panne, sans carte.
    const pretes = document.querySelector("#etudes-pretes");
    expect(pretes).toHaveTextContent(/études prêtes sont momentanément indisponibles/);
    expect(pretes?.querySelector("a.acc-prete")).toBeNull();
  });

  // Une réponse 200 qui ne porte pas la liste attendue — `{}`, ou la page
  // d'un relais servie à la place de l'API — rendait `[]` : une panne lue
  // comme « rien à vendre », cartes éteintes et section effacée sans un mot.
  it("une réponse 200 sans la clé attendue est une panne dite, pas un catalogue vide", async () => {
    servir({
      livrables: () => HttpResponse.json({}),
      formules: () => HttpResponse.json({ formule: [] }),
      boutique: () => new HttpResponse("<!doctype html><title>EVKHA</title>", { headers: { "Content-Type": "text/html" } }),
    });
    render(<Accueil />);

    await waitFor(() => expect(alerte()).toHaveTextContent(/momentanément indisponibles/));
    await prixCharges();
    expect(screen.getAllByText(/Tarif momentanément indisponible/).length).toBeGreaterThanOrEqual(8);
    expect(screen.queryByText(/Indisponible pour le moment/)).toBeNull();
    expect(document.querySelector("#etudes-pretes")).toHaveTextContent(/momentanément indisponibles/);
    expect(texte()).not.toMatch(MONTANT);
  });

  it("une seule région d'alerte, stable, pour des pannes qui se suivent", async () => {
    servir({
      livrables: panne,
      formules: async () => {
        await delay(120);
        return new HttpResponse("panne", { status: 502 });
      },
      boutique: laBoutique(PRODUITS),
    });
    render(<Accueil />);

    // La région existe AVANT toute panne : c'est le même nœud qui se remplit.
    const region = alerte();
    expect(region).toBeEmptyDOMElement();
    await waitFor(() => expect(region).toHaveTextContent(/momentanément indisponibles/));
    expect(screen.getAllByRole("alert")).toHaveLength(1);

    // La seconde panne arrive : toujours une région, le même nœud, un message.
    await prixCharges();
    // Quatre marches, la bulle de l'atelier, la carte des livrables, et les deux
    // cartes d'abonnement arrivées avec la seconde panne.
    await waitFor(() => expect(screen.getAllByText(/Tarif momentanément indisponible/)).toHaveLength(8));
    expect(screen.getAllByRole("alert")).toEqual([region]);
    expect(region.querySelectorAll("p")).toHaveLength(1);
    expect(region.querySelector("a")).toHaveAttribute("href", "mailto:contact@evkha.fr");
  });

  it("contre-épreuve : une panne partielle n'éteint pas les prix arrivés", async () => {
    servir({ ...recu, formules: panne });
    render(<Accueil />);

    await waitFor(() => expect(texte()).toContain("de 93 € à 203 €"));
    await waitFor(() => expect(alerte()).toHaveTextContent(/momentanément indisponibles/));
    // Les deux cartes d'abonnement disent leur panne ; aucune n'invente un prix.
    await waitFor(() => expect(screen.getAllByText(/Tarif momentanément indisponible/)).toHaveLength(2));
    expect(texte()).not.toContain("par mois");
    expect(texte()).toContain("dès 77 €");
  });

  it("un catalogue reçu VIDE : ni prix, ni panne, boutons neutralisés, section des études prêtes absente", async () => {
    servir({ livrables: lesLivrables([]), formules: lesFormules([]), boutique: laBoutique([]) });
    render(<Accueil />);

    await prixCharges();
    expect(texte()).not.toMatch(MONTANT);
    expect(texte()).not.toContain("∞");
    expect(alerte()).toBeEmptyDOMElement();
    // L'ancien libellé renvoyait à une page où l'offre n'est pas non plus.
    expect(screen.queryByText(/Tarif indiqué sur la page/)).toBeNull();
    expect(screen.getAllByText(/Indisponible pour le moment/).length).toBeGreaterThanOrEqual(8);

    // Les quatre cartes d'offre : le bouton n'est plus un lien.
    for (const surtitre of ["Tout de suite", "Pour votre projet", "Vous accompagnez", "Réseaux et incubateurs"]) {
      const carte = carteDOffre(surtitre);
      expect(carte.querySelector(".acc-btn-inactif"), surtitre).toHaveAttribute("aria-disabled", "true");
      expect(carte.querySelector("a"), surtitre).toBeNull();
    }
    // Les quatre marches non plus.
    expect(screen.queryByRole("link", { name: /Mon idée tient-elle/ })).toBeNull();
    expect(screen.getByRole("heading", { level: 3, name: "Mon idée tient-elle ?" })).toBeInTheDocument();
    // Une vitrine vide n'apprend rien : la section n'existe pas.
    expect(document.querySelector("#etudes-pretes")).toBeNull();
  });

  it("une offre à zéro n'a pas de prix : ni « dès 0 € », ni marche à 0 €", async () => {
    servir({
      livrables: lesLivrables([livrable("etude-marche", "market_study", 0), ...LIVRABLES.filter((l) => l.type !== "market_study")]),
      formules: lesFormules([formule("essai", 0), ...FORMULES]),
      boutique: laBoutique([produit("gratuit", 0, "Une étude offerte"), ...PRODUITS]),
    });
    render(<Accueil />);

    await waitFor(() => expect(texte()).toContain("dès 131 €"));
    await waitFor(() => expect(texte()).toContain("dès 77 €"));
    expect(texte()).not.toMatch(/(?<!\d)0 €/);
    // Le livrable à zéro n'est pas vendable : sa marche le dit, sans lien.
    expect(screen.queryByRole("link", { name: /Mon idée tient-elle/ })).toBeNull();
    expect(texte()).toContain("de 93 € à 203 €");
    // Et l'étude à zéro n'entre pas dans la vitrine.
    expect(screen.queryByText("Une étude offerte")).toBeNull();
  });

  // ── La carte des structures ───────────────────────────────────────────────

  it("la carte des structures lit SA formule : prix, titre et avantages du serveur", async () => {
    // Une formule PLUS CHÈRE que « structure » : « la plus chère » aurait
    // affiché son prix sous le titre et les avantages d'une autre.
    servir({ ...recu, formules: lesFormules([...FORMULES, formule("reseau", 99900, "Réseau national", ["Tout illimité"])]) });
    render(<Accueil />);

    await waitFor(() => expect(texte()).toContain("433 €"));
    const carte = carteDOffre("Réseaux et incubateurs");
    expect(texteDe(carte)).toContain("433 € par mois");
    expect(within(carte).getByRole("heading", { level: 3 })).toHaveTextContent("Structure Horizon");
    expect(within(carte).getByText("Convention sur douze mois")).toBeInTheDocument();
    expect(within(carte).getByText("Une référente nommée")).toBeInTheDocument();
    expect(within(carte).getByRole("link")).toHaveAttribute("href", "/partenaires");
    expect(texte()).not.toContain("999 €");
    expect(texte()).not.toContain("Tout illimité");
    // Rien n'est recopié : ces deux points n'existent que si le serveur les rend.
    expect(texte()).not.toContain("Interlocutrice dédiée");
    expect(texte()).not.toContain("Convention-cadre");
  });

  it("sans formule « structure » au catalogue, la carte le dit et n'emprunte aucun prix", async () => {
    servir({ ...recu, formules: lesFormules([formule("solo", 13100), formule("reseau", 99900)]) });
    render(<Accueil />);

    await waitFor(() => expect(texte()).toContain("dès 131 €"));
    const carte = carteDOffre("Réseaux et incubateurs");
    expect(within(carte).getByText(/Indisponible pour le moment/)).toBeInTheDocument();
    expect(texteDe(carte)).not.toMatch(MONTANT);
    expect(carte.querySelector(".acc-btn-inactif")).not.toBeNull();
    expect(carte.querySelector("a")).toBeNull();
    expect(texte()).not.toContain("999 €");
    expect(alerte()).toBeEmptyDOMElement();
  });

  // ── Les études prêtes ─────────────────────────────────────────────────────

  it("les études prêtes sont les produits de la boutique : titres, prix et liens du serveur, six au plus", async () => {
    const huit = Array.from({ length: 8 }, (_, k) => produit(`etude-${k + 1}`, 7100 + k * 200, `Le marché numéro ${k + 1}`));
    servir({ ...recu, boutique: laBoutique(huit) });
    render(<Accueil />);

    await waitFor(() => expect(document.querySelectorAll("#etudes-pretes a.acc-prete")).toHaveLength(6));
    const pretes = document.querySelector("#etudes-pretes") as HTMLElement;
    const premiere = within(pretes).getByRole("link", { name: /Le marché numéro 1/ });
    expect(premiere).toHaveAttribute("href", "/boutique/etude-1");
    expect(texteDe(premiere)).toContain("71 €");
    expect(texteDe(pretes)).toContain("81 €");
    // La septième et la huitième sont dans la boutique, pas ici.
    expect(within(pretes).queryByText(/Le marché numéro 7/)).toBeNull();
    expect(within(pretes).getByRole("link", { name: /Voir toute la boutique/ })).toHaveAttribute("href", "/boutique");
    expect(pretes.querySelector(".acc-prete-gabarit")).toBeNull();
    // Le « dès » de la carte d'offre vient du MÊME appel : le moins cher des huit.
    expect(texteDe(carteDOffre("Tout de suite"))).toContain("dès 71 €");
  });

  // ── Ce qui ne dépend pas des prix ─────────────────────────────────────────

  it("contre-épreuve : le reste de la page s'affiche même sans prix", async () => {
    servir({ livrables: panne, formules: panne, boutique: panne });
    render(<Accueil />);
    await waitFor(() => expect(alerte()).not.toBeEmptyDOMElement());

    // Le titre, lu une fois, avec le premier des mots qui tournent.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/Transformez votre idée.*en entreprise qui tient debout/);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(document.title).toBe("EVKHA — De l'idée à l'entreprise");

    // Le parcours, dans l'ordre du projet.
    const questions = ["Mon idée tient-elle ?", "Face à qui ?", "Convaincre la banque", "Passer à l'action"];
    const marches = screen
      .getAllByRole("heading", { level: 3 })
      .map((titre) => titre.textContent)
      .filter((titre) => questions.includes(titre ?? ""));
    expect(marches).toEqual(questions);

    // Les dix avis du profil ComeUp, chacun lu une seule fois : son doublon est masqué.
    expect(screen.getByRole("group", { name: "Avis de clients" }).querySelectorAll("figure:not([aria-hidden])")).toHaveLength(10);
    expect(texte()).toContain("Très satisfait du travail d'Evangéline, comme à chaque fois :)");
    expect(texte()).toContain("Les dix derniers avis laissés à Evangeline sur ComeUp");
    expect(texte()).not.toContain("après leur commande");

    // Le second public, dès l'ouverture, et le contact à la place de la lettre.
    expect(screen.getByRole("link", { name: /EVKHA produit le dossier sous votre marque/ })).toHaveAttribute("href", "/partenaires");
    expect(document.querySelector("#contact a[href^='mailto:']")).toHaveAttribute("href", "mailto:contact@evkha.fr");
    expect(document.querySelector("form")).toBeNull();
    expect(texte()).not.toContain("Pôle Emploi");

    // Les sections reprises du site, sans un prix : elles ne se vendent pas ici.
    for (const nom of ["LegalPlace", "Réseau Initiative France", "Swapn", "Yyyours"]) {
      expect(screen.getByRole("img", { name: nom })).toBeInTheDocument();
    }
    expect(screen.getByRole("link", { name: /Voir les formations/ })).toHaveAttribute("href", "/formations");
    expect(screen.getByRole("link", { name: /Voir les packs/ })).toHaveAttribute("href", "/packs");
    expect(texte()).toContain("Ces offres se réservent sur evkha.fr.");
    expect(screen.getByRole("link", { name: /Lire l'article/ })).toHaveAttribute("href", "/blog/idee-business-viable");
    expect(screen.getByRole("link", { name: "LinkedIn" })).toHaveAttribute("rel", "noopener");
    expect(screen.getByRole("link", { name: /Méthode P\.O\.P et accompagnement/ })).toHaveAttribute("href", "/formations");
  });

  it("ce qui est écrit ailleurs n'est pas réécrit : chapitres, relecture, engagement", async () => {
    servir(recu);
    render(<Accueil />);
    await prixCharges();

    // Le nombre de chapitres vient de `contenu.ETUDES`, livrable par livrable.
    const feuille = document.querySelector(".acc-feuille") as HTMLElement;
    expect(ETUDES["etude-marche"].chapitres).toBe(22);
    expect(feuille).toHaveTextContent("22 chapitres");
    fireEvent.click(screen.getByRole("button", { name: /Business plan/ }));
    expect(feuille).toHaveTextContent(`${ETUDES["business-plan"].chapitres} chapitres`);
    expect(feuille).not.toHaveTextContent("22 chapitres");
    expect(texte()).toContain("L'étude de marché suit 22 chapitres");

    // La relecture : les mots de la page des études, et aucune opposition.
    expect(ETUDES_PAGE.comparatif.pied.startsWith(RELECTURE)).toBe(true);
    expect(texte()).toContain("relue avant envoi par Evangeline elle-même");
    expect(texte()).not.toMatch(/fait à l'IA|à la chaîne|\bIA\b/);

    // L'engagement : la phrase de `espace/engagement.ts`.
    expect(texte()).toContain("Engagement minimum de trois mois, puis arrêt sur simple demande");
  });

  // ── La page se laisse conduire ────────────────────────────────────────────

  it("les deux boutons de pause partagent un seul état", async () => {
    servir(recu);
    const { container } = render(<Accueil />);

    const boutons = screen.getAllByRole("button", { name: "Mettre les animations en pause" });
    expect(boutons).toHaveLength(2);
    fireEvent.click(boutons[0]);
    expect(container.querySelector(".acc")).toHaveClass("acc-fige");
    const relances = screen.getAllByRole("button", { name: "Relancer les animations" });
    expect(relances).toHaveLength(2);
    for (const bouton of relances) expect(bouton).toHaveAttribute("aria-pressed", "true");
    // Le second relance ce que le premier a arrêté.
    fireEvent.click(relances[1]);
    expect(container.querySelector(".acc")).not.toHaveClass("acc-fige");
    await prixCharges();
  });

  it("un lien de la barre referme le menu plein écran, et l'évitement vise le contenu", async () => {
    servir(recu);
    render(<Accueil />);

    const principal = screen.getByRole("main");
    expect(principal).toHaveAttribute("id", "acc-contenu");
    expect(screen.getByRole("link", { name: "Aller au contenu" })).toHaveAttribute("href", "#acc-contenu");

    const ouvrir = screen.getByRole("button", { name: "Ouvrir le menu" });
    fireEvent.click(ouvrir);
    expect(ouvrir).toHaveAttribute("aria-expanded", "true");
    expect(principal).toHaveAttribute("inert");
    // « Me contacter » est dans la barre, pas dans le menu : la page défilait
    // derrière le menu resté ouvert.
    fireEvent.click(screen.getByRole("link", { name: /Me contacter/ }));
    expect(ouvrir).toHaveAttribute("aria-expanded", "false");
    expect(principal).not.toHaveAttribute("inert");
    await prixCharges();
  });

  // ── La classe du défaut : un montant écrit dans la page ───────────────────

  for (const fichier of ["Accueil.tsx", "contenuAccueil.ts"]) {
    it(`${fichier} n'écrit aucun montant`, () => {
      const source = sansCommentaires(readFileSync(join(process.cwd(), "src", "public", fichier), "utf-8"));
      // Règle 1 : un fichier vide ou introuvable ne « passe » pas.
      expect(source.length).toBeGreaterThan(2000);
      expect(source.match(new RegExp(MONTANT_ECRIT.source, "gi")) ?? []).toEqual([]);
    });
  }

  it("contre-épreuve : le détecteur voit un montant, et pas une durée", () => {
    for (const faute of ["dès 89 €", "149€", "1 490 € TTC", "64,50 €", "prix: 185 euros"]) {
      expect(faute, faute).toMatch(MONTANT_ECRIT);
    }
    for (const juste of ["sous 24 heures ouvrées", "15 à 20 minutes", "500+", "le signe €"]) {
      expect(juste, juste).not.toMatch(MONTANT_ECRIT);
    }
    expect(espaces(`dès${INSECABLE}93${FINE_INSECABLE}€`)).toMatch(MONTANT);
  });
});

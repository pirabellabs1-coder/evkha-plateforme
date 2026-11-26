/** La coquille de l'administration : son plan, ses repères, son tiroir.
 *
 * La barre alignait quatorze entrées à plat, sous des caractères
 * typographiques en guise d'icônes (deux entrées portaient le même losange),
 * et l'en-tête ne disait ni où l'on était ni dans quel ensemble. Refaite le
 * 19/11/2026 : cinq groupes dans l'ordre du travail d'une gérante, des icônes
 * dessinées, un fil d'Ariane, un tiroir sur petit écran.
 *
 * Dix verrous, sur le rendu RÉEL de `CoquilleAdmin` dans un vrai routeur
 * (mémoire) — pas sur une doublure de `Link` : c'est `Link` qui pose
 * `aria-current`, et une doublure ne prouverait rien de l'entrée courante.
 *
 * 1. le plan : cinq groupes nommés, leurs entrées dans l'ordre, et les
 *    ADRESSES d'avant (`/admin/jobs` sous « Générations », `/admin/orders`
 *    sous « Commandes ») — seuls les libellés et le rangement ont changé ;
 * 2. l'entrée courante porte `aria-current="page"`, et elle seule ;
 * 3. plus aucun caractère-icône dans la barre : chaque entrée a son tracé ;
 * 4. un seul `h1`, un `main`, un lien d'évitement ;
 * 5. le fil d'Ariane d'une page de détail : groupe › écran (lien) › détail ;
 * 6. le tiroir : fermé il est inerte ; ouvert, c'est le CONTENU qui l'est, le
 *    focus y entre, Échap le ferme et rend le focus au bouton du menu.
 *    Contre-épreuve : sur grand écran, replier ne rend rien inerte ;
 * 7. la pastille des demandes : un nombre, rien, ou une PANNE — trois états
 *    qui ne se ressemblent pas. Une lecture en échec ne se lit pas « zéro » ;
 * 8. chaque chemin du plan (`GROUPES`) est une route de l'arbre RÉEL de
 *    l'application (`router.creerRouteur`) — c'est ce test, et non le
 *    compilateur, qui tient ces chemins (voir `Coquille.suivre`) ;
 * 9. un clic sur une entrée du rail change le chemin du routeur sans recharger
 *    la page ; Ctrl+clic est laissé au navigateur ; un clic sur l'écran
 *    courant n'ajoute rien à l'historique ;
 * 10. tiroir ouvert, le lien d'évitement est inerte comme le contenu qu'il vise.
 *
 * Contre le code d'avant (`Coquille.tsx` à plat) : 1, 3, 5, 6 et 7 échouent —
 * pas de liste nommée « Pilotage », des losanges dans la barre, pas de fil
 * d'Ariane, pas d'`inert`, et une panne des demandes sans aucun signe (non
 * rejoué contre ce code-là). Les verrous 8 à 10, eux, ont été vus rouges le
 * 20/11/2026 en défaisant chaque correctif : un chemin du plan renommé, le
 * clic qui ne pousse plus, Ctrl+clic pris, l'écran courant repoussé, le lien
 * d'évitement laissé actif.
 *
 * jsdom n'a pas de `matchMedia` : chaque test le pose (grand ou petit écran).
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique. Les gestionnaires MSW
 * visent `window.location.origin` (jsdom : http://localhost:3000).
 */
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CoquilleAdmin } from "../admin/Coquille";
import { GROUPES, positionDe } from "../admin/navigation";
import { creerRouteur } from "../router";
import { server } from "./server";

const DASH = `${window.location.origin}/api/dashboard`;

/** Le plan attendu : c'est la demande du client, recopiée ici À DESSEIN. Lire
 *  `GROUPES` pour savoir ce que `GROUPES` doit contenir ne vérifierait rien. */
const PLAN: { groupe: string; entrees: [libelle: string, adresse: string][] }[] = [
  {
    groupe: "Pilotage",
    entrees: [
      ["Tableau de bord", "/admin"],
      ["Transactions", "/admin/transactions"],
      ["Qualité", "/admin/qualite"],
    ],
  },
  {
    groupe: "Catalogue",
    entrees: [
      ["Livrables", "/admin/livrables"],
      ["Boutique", "/admin/boutique"],
      ["Formations", "/admin/formations"],
    ],
  },
  {
    groupe: "Clients",
    entrees: [
      ["Organisations", "/admin/organisations"],
      ["Clients", "/admin/clients"],
      ["Commandes", "/admin/orders"],
      ["Demandes", "/admin/demandes"],
      ["Signalements", "/admin/signalements"],
    ],
  },
  {
    groupe: "Production",
    entrees: [
      ["Générations", "/admin/jobs"],
      ["Incidents", "/admin/incidents"],
    ],
  },
  {
    groupe: "Communication",
    entrees: [
      ["Annonces", "/admin/annonces"],
      ["Prospection", "/admin/prospection"],
      ["Lettre", "/admin/lettre"],
      ["Audience", "/admin/audience"],
    ],
  },
];

/** Un caractère employé comme pictogramme : flèches, formes géométriques,
 *  symboles divers, dingbats. Les lettres, les chiffres et la ponctuation du
 *  français n'en sont pas. */
const CARACTERE_ICONE = /[\u2190-\u21ff\u2300-\u23ff\u25a0-\u25ff\u2600-\u27bf\u2b00-\u2bff]/u;

/** Une doublure de `matchMedia` : toute requête répond `large`. La coquille
 *  n'en pose qu'une — le seuil du grand écran (`useBarreLaterale`). */
function ecran(large: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((requete: string) => ({
      matches: large,
      media: requete,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    })),
  );
}

/** Les deux files que la coquille lit pour ses pastilles. */
function files({ demandes, signalements }: { demandes: number | "panne"; signalements: number }) {
  server.use(
    http.get(`${DASH}/supervision/demandes/`, () =>
      demandes === "panne"
        ? new HttpResponse("panne", { status: 500 })
        : HttpResponse.json({ demandes: [], ouvertes: demandes }),
    ),
    http.get(`${DASH}/signalements/`, () =>
      HttpResponse.json({ signalements: [], a_traiter: signalements, statuts: [] }),
    ),
  );
}

/** La coquille dans un vrai routeur, sur quelques routes de l'administration.
 *  Les écrans sont des doublures : c'est la coquille qu'on regarde. */
function ouvrir(chemin: string) {
  const racine = createRootRoute();
  const admin = createRoute({
    getParentRoute: () => racine,
    path: "/admin",
    component: CoquilleAdmin,
  });
  const ecranDe = (nom: string) => () => <p>écran : {nom}</p>;
  const arbre = racine.addChildren([
    admin.addChildren([
      createRoute({ getParentRoute: () => admin, path: "/", component: ecranDe("tableau de bord") }),
      createRoute({ getParentRoute: () => admin, path: "jobs", component: ecranDe("générations") }),
      createRoute({
        getParentRoute: () => admin,
        path: "jobs/$jobId",
        component: ecranDe("une génération"),
      }),
      createRoute({ getParentRoute: () => admin, path: "demandes", component: ecranDe("demandes") }),
    ]),
  ]);
  const routeur = createRouter({
    routeTree: arbre,
    history: createMemoryHistory({ initialEntries: [chemin] }),
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={routeur} />
    </QueryClientProvider>,
  );
  return routeur;
}

/** La barre, une fois rendue. Par son identifiant : fermé, le tiroir est
 *  `inert`, et l'on ne veut pas dépendre de ce que la bibliothèque de test
 *  décide d'un élément inerte. */
async function barre(): Promise<HTMLElement> {
  await screen.findByText(/^écran : /);
  const nav = document.getElementById("navigation-admin");
  if (!nav) throw new Error("barre de navigation introuvable");
  return nav;
}

function corps(): HTMLElement {
  const element = document.querySelector<HTMLElement>(".console-corps");
  if (!element) throw new Error("corps de la coquille introuvable");
  return element;
}

/** Le lien d'une entrée, par son adresse — le nom peut porter une pastille. */
function entree(nav: HTMLElement, adresse: string): HTMLElement {
  const lien = nav.querySelector<HTMLElement>(`a[href="${adresse}"]`);
  if (!lien) throw new Error(`entrée introuvable : ${adresse}`);
  return lien;
}

beforeEach(() => {
  localStorage.clear();
  ecran(true);
  files({ demandes: 0, signalements: 0 });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("la coquille de l'administration", () => {
  // ── 1. Le plan ────────────────────────────────────────────────────────────

  it("range les écrans en cinq groupes nommés, dans l'ordre du travail", async () => {
    ouvrir("/admin");
    const nav = await barre();

    const listes = within(nav).getAllByRole("list");
    expect(listes.map((liste) => liste.getAttribute("aria-labelledby"))).toHaveLength(PLAN.length);
    for (const { groupe, entrees } of PLAN) {
      const liste = within(nav).getByRole("list", { name: groupe });
      const liens = within(liste).getAllByRole("link");
      expect(
        liens.map((lien) => [lien.textContent?.trim(), lien.getAttribute("href")]),
        groupe,
      ).toEqual(entrees);
    }
    // Les groupes eux-mêmes sont dans l'ordre demandé.
    expect(
      listes.map((liste) => document.getElementById(liste.getAttribute("aria-labelledby") ?? "")?.textContent),
    ).toEqual(PLAN.map((groupe) => groupe.groupe));
  });

  it("le plan déclaré est celui qui est rendu, et « Formations » a son en-tête", () => {
    expect(
      GROUPES.map((groupe) => ({
        groupe: groupe.libelle,
        entrees: groupe.entrees.map((e) => [e.libelle, e.vers]),
      })),
    ).toEqual(PLAN);
    // Aucune adresse en double : deux entrées vers le même écran seraient
    // « courantes » ensemble.
    const adresses = GROUPES.flatMap((groupe) => groupe.entrees.map((e) => e.vers));
    expect(new Set(adresses).size).toBe(adresses.length);

    const formations = positionDe("/admin/formations");
    expect(formations?.groupe.libelle).toBe("Catalogue");
    expect(formations?.entree.titre).toBe("Formations");
    expect(formations?.entree.aide).toBe("Vos formations, leurs modules et leurs leçons.");
  });

  // ── 2. L'entrée courante ──────────────────────────────────────────────────

  it("l'entrée courante porte aria-current, et elle seule", async () => {
    ouvrir("/admin/jobs");
    const nav = await barre();

    await waitFor(() =>
      expect(entree(nav, "/admin/jobs")).toHaveAttribute("aria-current", "page"),
    );
    const courantes = [...nav.querySelectorAll('[aria-current="page"]')];
    expect(courantes.map((lien) => lien.getAttribute("href"))).toEqual(["/admin/jobs"]);
    // Le tableau de bord préfixe tous les chemins : il ne doit pas rester
    // « courant » partout.
    expect(entree(nav, "/admin")).not.toHaveAttribute("aria-current");
  });

  it("contre-épreuve : sur le tableau de bord, c'est lui qui est courant", async () => {
    ouvrir("/admin");
    const nav = await barre();

    await waitFor(() => expect(entree(nav, "/admin")).toHaveAttribute("aria-current", "page"));
    expect(nav.querySelectorAll('[aria-current="page"]')).toHaveLength(1);
  });

  // ── 3. Plus de caractère-icône ────────────────────────────────────────────

  it("aucun caractère typographique ne tient lieu d'icône dans la barre", async () => {
    ouvrir("/admin");
    const nav = await barre();

    expect(nav.textContent ?? "").not.toMatch(CARACTERE_ICONE);
    // Et chaque entrée a bien son icône : dessinée, et tue aux lecteurs d'écran.
    const liens = within(nav).getAllByRole("link");
    expect(liens.length).toBeGreaterThanOrEqual(15);
    for (const lien of liens) {
      const icone = lien.querySelector("svg");
      expect(icone, lien.textContent ?? "").not.toBeNull();
      expect(icone).toHaveAttribute("aria-hidden", "true");
    }
  });

  it("contre-épreuve : le détecteur voit les signes d'avant, pas le français", () => {
    for (const faute of ["◈ Tableau de bord", "◍", "▣ Livrables", "⚑ Signalements", "⚠", "Espace client ↗"]) {
      expect(CARACTERE_ICONE.test(faute), faute).toBe(true);
    }
    for (const juste of ["Tableau de bord", "Qualité — interne", "Générations (3)", "« Demandes »", "12 €"]) {
      expect(CARACTERE_ICONE.test(juste), juste).toBe(false);
    }
  });

  // ── 4. Les repères de la page ─────────────────────────────────────────────

  it("un seul h1, un main, un lien d'évitement qui y mène", async () => {
    ouvrir("/admin/jobs");
    await barre();

    const titres = screen.getAllByRole("heading", { level: 1 });
    expect(titres).toHaveLength(1);
    expect(titres[0]).toHaveTextContent("Générations");

    const contenu = screen.getByRole("main");
    expect(contenu).toHaveTextContent("écran : générations");

    const evitement = screen.getByRole("link", { name: "Aller au contenu" });
    expect(evitement).toHaveAttribute("href", `#${contenu.id}`);
    fireEvent.click(evitement);
    expect(document.activeElement).toBe(contenu);
  });

  // ── 5. Le fil d'Ariane ────────────────────────────────────────────────────

  it("sur une page de détail : groupe, écran en lien, puis le détail", async () => {
    ouvrir("/admin/jobs/9e38eb81");
    await barre();

    const fil = screen.getByRole("navigation", { name: "Fil d'Ariane" });
    const maillons = within(fil).getAllByRole("listitem");
    expect(maillons.map((maillon) => maillon.textContent?.trim())).toEqual([
      "Production",
      "Générations",
      "Fiche de la génération",
    ]);
    // L'écran parent est un lien — on en revient d'un clic ; le détail est la
    // page courante, et ne mène nulle part.
    expect(within(maillons[1]).getByRole("link", { name: "Générations" })).toHaveAttribute(
      "href",
      "/admin/jobs",
    );
    expect(within(maillons[2]).queryByRole("link")).toBeNull();
    expect(within(fil).getByText("Fiche de la génération")).toHaveAttribute("aria-current", "page");
    // Le titre dit la page de détail, pas la liste.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Fiche de la génération");
  });

  it("contre-épreuve : sur une liste, le fil s'arrête à l'écran, sans lien", async () => {
    ouvrir("/admin/jobs");
    await barre();

    const fil = screen.getByRole("navigation", { name: "Fil d'Ariane" });
    expect(within(fil).getAllByRole("listitem").map((m) => m.textContent?.trim())).toEqual([
      "Production",
      "Générations",
    ]);
    expect(within(fil).queryByRole("link")).toBeNull();
    expect(within(fil).getByText("Générations")).toHaveAttribute("aria-current", "page");
  });

  // ── 6. Le tiroir ──────────────────────────────────────────────────────────

  it("petit écran : le tiroir s'ouvre, rend le contenu inerte, et Échap rend le focus", async () => {
    ecran(false);
    ouvrir("/admin/jobs");
    const nav = await barre();
    const menu = screen.getByRole("button", { name: "Ouvrir le menu" });

    // Fermé : c'est le tiroir qui est inerte, pas la page.
    expect(nav).toHaveAttribute("inert");
    expect(corps()).not.toHaveAttribute("inert");
    expect(menu).toHaveAttribute("aria-expanded", "false");
    expect(menu).toHaveAttribute("aria-controls", nav.id);

    fireEvent.click(menu);

    // Ouvert : l'inverse. Et le focus est entré dans le tiroir.
    await waitFor(() => expect(corps()).toHaveAttribute("inert"));
    expect(nav).not.toHaveAttribute("inert");
    expect(menu).toHaveAttribute("aria-expanded", "true");
    const croix = within(nav).getByRole("button", { name: "Fermer le menu" });
    expect(document.activeElement).toBe(croix);

    fireEvent.keyDown(window, { key: "Escape" });

    // Refermé : la page revit, et le focus revient au bouton qui a ouvert.
    await waitFor(() => expect(corps()).not.toHaveAttribute("inert"));
    expect(nav).toHaveAttribute("inert");
    expect(menu).toHaveAttribute("aria-expanded", "false");
    expect(document.activeElement).toBe(menu);
  });

  it("petit écran : la croix du tiroir le ferme aussi", async () => {
    ecran(false);
    ouvrir("/admin/jobs");
    const nav = await barre();
    const menu = screen.getByRole("button", { name: "Ouvrir le menu" });

    fireEvent.click(menu);
    await waitFor(() => expect(corps()).toHaveAttribute("inert"));
    fireEvent.click(within(nav).getByRole("button", { name: "Fermer le menu" }));

    await waitFor(() => expect(corps()).not.toHaveAttribute("inert"));
    expect(document.activeElement).toBe(menu);
  });

  it("contre-épreuve — grand écran : replier fait un rail, et ne rend rien inerte", async () => {
    ouvrir("/admin/jobs");
    const nav = await barre();
    const racine = nav.closest(".console");

    expect(racine).not.toHaveClass("console-en-rail");
    fireEvent.click(screen.getByRole("button", { name: "Replier le menu" }));

    await waitFor(() => expect(racine).toHaveClass("console-en-rail"));
    expect(nav).not.toHaveAttribute("inert");
    expect(corps()).not.toHaveAttribute("inert");
    // En rail, les entrées gardent leur NOM : le libellé sort de la vue, pas
    // de la page.
    expect(within(nav).getByRole("link", { name: "Générations" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Déplier le menu" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    // Échap ne replie ni ne déplie rien sur grand écran.
    fireEvent.keyDown(window, { key: "Escape" });
    expect(racine).toHaveClass("console-en-rail");
  });

  // ── 7. La pastille des demandes ───────────────────────────────────────────

  it("des demandes en attente : la pastille dit combien", async () => {
    files({ demandes: 3, signalements: 0 });
    ouvrir("/admin");
    const nav = await barre();

    await waitFor(() => expect(entree(nav, "/admin/demandes")).toHaveTextContent("3"));
    expect(entree(nav, "/admin/demandes")).toHaveTextContent(/demandes à traiter/);
    expect(entree(nav, "/admin/demandes").querySelector(".console-pastille-panne")).toBeNull();
  });

  it("une lecture en panne ne se lit pas « zéro » : la pastille le dit", async () => {
    files({ demandes: "panne", signalements: 0 });
    ouvrir("/admin");
    const nav = await barre();

    await waitFor(() =>
      expect(entree(nav, "/admin/demandes")).toHaveTextContent(/nombre de demandes indisponible/),
    );
    const lien = entree(nav, "/admin/demandes");
    expect(lien.querySelector(".console-pastille-panne")).not.toBeNull();
    // Ni un zéro, ni un nombre inventé.
    expect(lien.textContent ?? "").not.toMatch(/\d/);
    // La panne d'une file ne déborde pas sur l'autre.
    expect(entree(nav, "/admin/signalements")).not.toHaveTextContent(/indisponible/);
  });

  it("contre-épreuve : zéro demande REÇU ne montre ni pastille ni panne", async () => {
    files({ demandes: 0, signalements: 2 });
    ouvrir("/admin");
    const nav = await barre();

    // On attend la preuve que les lectures sont revenues : la pastille des
    // signalements. Sans cela, « pas de pastille » serait vrai avant même la
    // réponse.
    await waitFor(() => expect(entree(nav, "/admin/signalements")).toHaveTextContent("2"));
    const lien = entree(nav, "/admin/demandes");
    expect(lien.querySelector(".console-pastille")).toBeNull();
    expect(lien).not.toHaveTextContent(/indisponible/);
    expect(lien.textContent?.trim()).toBe("Demandes");
  });

  // ── 8. Les chemins du plan, dans l'arbre réel ─────────────────────────────

  /** Les chemins des routes de l'application qui RENDENT un écran, lus dans
   *  l'arbre réel de `router.tsx` — sans barre finale (`/admin/` est l'index
   *  de `/admin`). */
  function ecransDuVraiRouteur(): string[] {
    const routes = Object.values(creerRouteur(createMemoryHistory()).routesById) as {
      fullPath: string;
      options: { component?: unknown };
    }[];
    return routes
      .filter((route) => route.options.component !== undefined)
      .map((route) => (route.fullPath.length > 1 ? route.fullPath.replace(/\/+$/, "") : route.fullPath));
  }

  it("chaque chemin du plan est une route du vrai routeur de l'application", () => {
    const ecrans = ecransDuVraiRouteur();
    const chemins = GROUPES.flatMap((groupe) => groupe.entrees.map((e) => e.vers));
    // Règle 1 : un arbre vide ou un plan vide n'auraient rien à comparer.
    expect(ecrans.length).toBeGreaterThan(50);
    expect(chemins.length).toBeGreaterThanOrEqual(15);
    expect(chemins.filter((chemin) => !ecrans.includes(chemin))).toEqual([]);
  });

  it("contre-épreuve : un chemin inventé, ou seulement voisin, est bien vu absent", () => {
    const ecrans = ecransDuVraiRouteur();
    for (const absent of ["/admin/nulle-part", "/admin/formation", "/admin/commandes", "/admin/jobs/"]) {
      expect(ecrans, absent).not.toContain(absent);
    }
    // Une route à paramètre n'est pas confondue avec sa liste.
    expect(ecrans).toContain("/admin/jobs/$jobId");
    expect(ecrans).toContain("/admin/formations");
  });

  // ── 9. Suivre une entrée ──────────────────────────────────────────────────

  /** Clique un lien et dit si le clic a été PRIS par la coquille
   *  (`preventDefault`). Un clic laissé au navigateur est neutralisé ici, après
   *  coup : jsdom ne sait pas naviguer et s'en plaindrait. */
  function cliquer(lien: HTMLElement, touches: { ctrlKey?: boolean } = {}): { pris: boolean } {
    const constat = { pris: false };
    const ecouter = (evenement: Event) => {
      constat.pris = evenement.defaultPrevented;
      evenement.preventDefault();
    };
    document.addEventListener("click", ecouter);
    fireEvent.click(lien, touches);
    document.removeEventListener("click", ecouter);
    return constat;
  }

  it("un clic sur une entrée change le chemin du routeur, sans recharger", async () => {
    const routeur = ouvrir("/admin/jobs");
    const nav = await barre();
    expect(routeur.state.location.pathname).toBe("/admin/jobs");

    expect(cliquer(entree(nav, "/admin/demandes")).pris).toBe(true);

    expect(await screen.findByText("écran : demandes")).toBeInTheDocument();
    expect(routeur.state.location.pathname).toBe("/admin/demandes");
    await waitFor(() =>
      expect(entree(nav, "/admin/demandes")).toHaveAttribute("aria-current", "page"),
    );
    // « Précédent » ramène à l'écran d'avant : c'est bien une entrée
    // d'historique, pas un remplacement.
    routeur.history.back();
    expect(await screen.findByText("écran : générations")).toBeInTheDocument();
  });

  it("Ctrl+clic est laissé au navigateur : le routeur ne bouge pas", async () => {
    const routeur = ouvrir("/admin/jobs");
    const nav = await barre();
    const avant = routeur.history.length;

    expect(cliquer(entree(nav, "/admin/demandes"), { ctrlKey: true }).pris).toBe(false);

    // On laisse à une navigation fautive le temps d'arriver.
    await new Promise((resoudre) => setTimeout(resoudre, 50));
    expect(routeur.state.location.pathname).toBe("/admin/jobs");
    expect(routeur.history.length).toBe(avant);
    expect(screen.getByText("écran : générations")).toBeInTheDocument();
  });

  it("un clic sur l'écran courant n'ajoute rien à l'historique", async () => {
    const routeur = ouvrir("/admin/jobs");
    const nav = await barre();
    const avant = routeur.history.length;

    // Le clic est pris — la page ne se recharge pas — mais rien n'est poussé.
    expect(cliquer(entree(nav, "/admin/jobs")).pris).toBe(true);
    expect(cliquer(entree(nav, "/admin/jobs")).pris).toBe(true);
    await new Promise((resoudre) => setTimeout(resoudre, 50));
    expect(routeur.history.length).toBe(avant);

    // Contre-épreuve : un autre écran, lui, ajoute bien UNE entrée.
    cliquer(entree(nav, "/admin/demandes"));
    await screen.findByText("écran : demandes");
    expect(routeur.history.length).toBe(avant + 1);
  });

  // ── 10. Le lien d'évitement, tiroir ouvert ────────────────────────────────

  it("tiroir ouvert, le lien d'évitement est inerte comme le contenu qu'il vise", async () => {
    ecran(false);
    ouvrir("/admin/jobs");
    await barre();
    const evitement = document.querySelector<HTMLElement>("a.console-saut");
    if (!evitement) throw new Error("lien d'évitement introuvable");

    // Fermé : le lien sert.
    expect(evitement).not.toHaveAttribute("inert");

    fireEvent.click(screen.getByRole("button", { name: "Ouvrir le menu" }));
    await waitFor(() => expect(corps()).toHaveAttribute("inert"));
    expect(evitement).toHaveAttribute("inert");

    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(corps()).not.toHaveAttribute("inert"));
    expect(evitement).not.toHaveAttribute("inert");
  });
});

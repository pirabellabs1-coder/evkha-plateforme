/** L'audience du site : les documents gratuits contre une adresse, la lettre,
 * et l'écran qui les montre à la gérante.
 *
 * Demande de la cliente du 24/11/2026 : téléchargement IMMÉDIAT des PDF (elle
 * ne veut plus les envoyer elle-même), qui récolte les adresses ; la lettre
 * sur le blog ; les porteurs de projet mis en avant.
 *
 * Ce que ce fichier verrouille :
 * 1. le formulaire d'un document POSTe l'adresse, la ressource et le choix de
 *    la case (DÉCOCHÉE par défaut), puis lance le téléchargement et laisse un
 *    lien de secours ;
 * 2. un lien rendu par le serveur qui ne vise pas `/ressources/…pdf` n'est
 *    JAMAIS suivi ;
 * 3. un refus du serveur se dit contre le champ, et rien ne se télécharge ;
 * 4. la lettre du blog POSTe l'adresse et confirme ;
 * 5. le blog s'ouvre sur les porteurs, chacun un lien vers son portrait ;
 * 6. l'écran « Audience » liste, exporte et désinscrit — et un échec de
 *    lecture ne se lit pas « aucune adresse » (règle 1).
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`.
 */
import React from "react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRouter,
} from "@tanstack/react-router";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AudienceAdmin } from "../admin/pages/Audience";
import { Blog } from "../public/Blog";
import { ARTICLES, BLOG, adresseDeLArticle } from "../public/contenuBlog";
import { RELEVES_DES_DOCUMENTS } from "../public/contenuAudience";
import { NAVIGATION } from "../public/contenuSite";
import {
  FormulaireLettre,
  FormulaireRessource,
  HOTE_DU_PRERENDU,
} from "../public/FormulaireAudience";
import { server } from "./server";

const ORIGINE = window.location.origin;
const DASH = `${ORIGINE}/api/dashboard`;
const CHECKLIST = "/ressources/checklist-creer-sa-micro-entreprise-en-10-etapes.pdf";

/** Les clics sur un lien `download` : jsdom ne navigue pas, on les relève. */
let liensCliques: string[] = [];

beforeEach(() => {
  liensCliques = [];
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    liensCliques.push(this.getAttribute("href") ?? "");
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  localStorage.clear();
});

function formulaireDeChecklist() {
  return render(
    <FormulaireRessource
      ressource="checklist"
      nom="la checklist"
      bouton="Je la veux"
      consentement="Oui, je souhaite recevoir les nouveautés EVKHA"
      mention="Votre email ne sera jamais partagé"
    />,
  );
}

function saisir(adresse: string) {
  fireEvent.change(screen.getByLabelText("Votre adresse e-mail"), { target: { value: adresse } });
}

// ── 1 à 3 : le formulaire d'un document ─────────────────────────────────────

describe("le formulaire d'un document gratuit", () => {
  it("envoie l'adresse et la ressource, case décochée, puis télécharge", async () => {
    let recu: unknown = null;
    server.use(
      http.post(`${ORIGINE}/api/public/ressources/`, async ({ request }) => {
        recu = await request.json();
        return HttpResponse.json({ lien: CHECKLIST });
      }),
    );
    formulaireDeChecklist();

    const case_ = screen.getByRole("checkbox") as HTMLInputElement;
    expect(case_.checked).toBe(false);
    saisir("marie@exemple.fr");
    fireEvent.click(screen.getByRole("button", { name: /Je la veux/ }));

    await waitFor(() => expect(liensCliques).toEqual([CHECKLIST]));
    expect(recu).toEqual({ email: "marie@exemple.fr", ressource: "checklist", lettre: false, site: "" });
    // Le lien de secours, si le navigateur a bloqué le téléchargement.
    expect(screen.getByRole("link", { name: "télécharger la checklist" })).toHaveAttribute("href", CHECKLIST);
    expect(screen.getByText(/Votre téléchargement a commencé/)).toBeInTheDocument();
  });

  it("la case cochée part avec la demande", async () => {
    let recu: Record<string, unknown> = {};
    server.use(
      http.post(`${ORIGINE}/api/public/ressources/`, async ({ request }) => {
        recu = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ lien: CHECKLIST });
      }),
    );
    formulaireDeChecklist();
    saisir("marie@exemple.fr");
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: /Je la veux/ }));
    await waitFor(() => expect(recu.lettre).toBe(true));
  });

  it("contre-épreuve : un lien rendu qui sort de /ressources/ n'est jamais suivi", async () => {
    server.use(
      http.post(`${ORIGINE}/api/public/ressources/`, () =>
        HttpResponse.json({ lien: "https://ailleurs.example/piege.pdf" }),
      ),
    );
    formulaireDeChecklist();
    saisir("marie@exemple.fr");
    fireEvent.click(screen.getByRole("button", { name: /Je la veux/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("momentanément indisponible");
    expect(liensCliques).toEqual([]);
    expect(document.querySelector("a[href*='ailleurs']")).toBeNull();
  });

  it("un refus du serveur se dit contre le champ, et rien ne se télécharge", async () => {
    server.use(
      http.post(`${ORIGINE}/api/public/ressources/`, () =>
        HttpResponse.json(
          { erreur: "Indiquez une adresse e-mail valide.", code: "adresse_invalide" },
          { status: 400 },
        ),
      ),
    );
    formulaireDeChecklist();
    saisir("marie@exemple.fr");
    fireEvent.click(screen.getByRole("button", { name: /Je la veux/ }));

    const alerte = await screen.findByRole("alert");
    expect(alerte).toHaveTextContent("Indiquez une adresse e-mail valide.");
    const champ = screen.getByLabelText("Votre adresse e-mail");
    expect(champ).toHaveAttribute("aria-invalid", "true");
    expect(champ.getAttribute("aria-describedby")).toContain(alerte.id);
    expect(liensCliques).toEqual([]);
  });

  it("une coupure réseau se dit aussi", async () => {
    server.use(http.post(`${ORIGINE}/api/public/ressources/`, () => HttpResponse.error()));
    formulaireDeChecklist();
    saisir("marie@exemple.fr");
    fireEvent.click(screen.getByRole("button", { name: /Je la veux/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("L'envoi n'a pas abouti");
  });

  it("le champ piège est hors du parcours et caché aux lecteurs d'écran", () => {
    formulaireDeChecklist();
    const piege = document.querySelector<HTMLInputElement>("input[name='site']");
    expect(piege).not.toBeNull();
    expect(piege?.tabIndex).toBe(-1);
    expect(piege?.closest("[aria-hidden='true']")).not.toBeNull();
    // Et la mention renvoie à la politique de confidentialité.
    expect(screen.getByRole("link", { name: "Politique de confidentialité" })).toHaveAttribute(
      "href",
      "/politique-de-confidentialite",
    );
  });
});

// ── 4 : la lettre ───────────────────────────────────────────────────────────

describe("l'inscription à la lettre", () => {
  it("envoie l'adresse et confirme", async () => {
    let recu: unknown = null;
    server.use(
      http.post(`${ORIGINE}/api/public/lettre/`, async ({ request }) => {
        recu = await request.json();
        return HttpResponse.json({ inscrit: true });
      }),
    );
    render(<FormulaireLettre bouton="Je m'abonne" mention="Je déteste le spam." />);
    saisir("lea@exemple.fr");
    fireEvent.click(screen.getByRole("button", { name: /Je m'abonne/ }));

    expect(await screen.findByText(/confirmez votre adresse/)).toBeInTheDocument();
    expect(recu).toEqual({ email: "lea@exemple.fr", site: "" });
  });
});

// ── 5 : le blog ─────────────────────────────────────────────────────────────

function rendreLeBlog() {
  window.history.pushState({}, "", "/blog");
  const racine = createRootRoute({ component: () => <Blog /> });
  const routeur = createRouter({
    routeTree: racine,
    history: createMemoryHistory({ initialEntries: ["/blog"] }),
  });
  return render(<RouterProvider router={routeur} />);
}

describe("le blog met en avant les porteurs et propose la lettre", () => {
  it("chaque portrait a sa carte de porteur, avec sa photo, vers son portrait", async () => {
    rendreLeBlog();
    const section = (await screen.findByRole("heading", { name: /Les porteurs de projet/ })).closest("section");
    expect(section).not.toBeNull();
    const portraits = ARTICLES.filter((article) => article.theme === "portraits");
    // Règle 1 : sans portrait, la boucle ne vérifierait rien.
    expect(portraits.length).toBeGreaterThanOrEqual(2);
    const cartes = section!.querySelectorAll("article.res-porteur");
    expect(cartes).toHaveLength(portraits.length);
    portraits.forEach((portrait, k) => {
      const carte = cartes[k] as HTMLElement;
      expect(within(carte).getByRole("link", { name: portrait.titre })).toHaveAttribute(
        "href",
        adresseDeLArticle(portrait.slug),
      );
      expect(carte.querySelector("img")?.getAttribute("src")).toBe(portrait.image?.src);
    });
    expect(section).toHaveTextContent("que j'accompagne ou avec qui je travaille");
  });

  it("la lettre ferme la liste, avant la passerelle", async () => {
    rendreLeBlog();
    const titre = await screen.findByRole("heading", { name: new RegExp(BLOG.lettre.titre.avant) });
    const section = titre.closest("section") as HTMLElement;
    expect(within(section).getByRole("form", { name: "Inscription à la newsletter" })).toBeInTheDocument();
    expect(within(section).getByRole("button", { name: /Je m'abonne/ })).toBeInTheDocument();
    // Après les articles, avant la fin dorée.
    const fin = document.querySelector(".res-fin") as HTMLElement;
    expect(section.compareDocumentPosition(fin) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

// ── 6 : l'écran de l'administration ─────────────────────────────────────────

const CONTACTS = [
  {
    id: "11111111-1111-1111-1111-111111111111",
    email: "marie@exemple.fr",
    premiere_demande_le: "2026-11-25T09:00:00+00:00",
    derniere_demande_le: "2026-11-25T10:00:00+00:00",
    demandes: ["Checklist", "Lexique"],
    inscrit_a_la_lettre: true,
    lettre_le: "2026-11-25T09:00:00+00:00",
    desinscrit_le: null,
  },
  {
    id: "22222222-2222-2222-2222-222222222222",
    email: "paul@exemple.fr",
    premiere_demande_le: "2026-11-24T09:00:00+00:00",
    derniere_demande_le: "2026-11-24T09:00:00+00:00",
    demandes: ["Lexique"],
    inscrit_a_la_lettre: false,
    lettre_le: null,
    desinscrit_le: null,
  },
];

function rendreLEcran() {
  localStorage.setItem("evkha_token", "jeton-d-administration");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AudienceAdmin />
    </QueryClientProvider>,
  );
}

describe("l'écran Audience", () => {
  it("liste les adresses, leurs demandes et la lettre", async () => {
    server.use(
      http.get(`${DASH}/audience/`, () =>
        HttpResponse.json({ contacts: CONTACTS, total: 2, inscrits_a_la_lettre: 1 }),
      ),
    );
    rendreLEcran();
    const marie = (await screen.findByText("marie@exemple.fr")).closest("tr") as HTMLElement;
    expect(marie).toHaveTextContent("Checklist, Lexique");
    expect(marie).toHaveTextContent(/Oui\s*depuis le/);
    const paul = screen.getByText("paul@exemple.fr").closest("tr") as HTMLElement;
    expect(paul).toHaveTextContent("Non");
    // Seule une personne inscrite se désinscrit ; chacune peut être effacée.
    expect(within(paul).queryByRole("button", { name: /Désinscrire/ })).toBeNull();
    expect(within(paul).getByRole("button", { name: "Effacer paul@exemple.fr et son historique" })).toBeInTheDocument();
    expect(within(marie).getByRole("button", { name: "Désinscrire marie@exemple.fr de la newsletter" })).toBeInTheDocument();
  });

  it("désinscrit après confirmation, et relit la liste", async () => {
    let appele = "";
    let lectures = 0;
    server.use(
      http.get(`${DASH}/audience/`, () => {
        lectures += 1;
        return HttpResponse.json({ contacts: CONTACTS, total: 2, inscrits_a_la_lettre: 1 });
      }),
      http.post(`${DASH}/audience/:id/desinscrire/`, ({ params }) => {
        appele = String(params.id);
        return HttpResponse.json({ contact: { ...CONTACTS[0], inscrit_a_la_lettre: false } });
      }),
    );
    vi.spyOn(window, "confirm").mockReturnValue(true);
    rendreLEcran();
    fireEvent.click(await screen.findByRole("button", { name: /Désinscrire marie/ }));

    await waitFor(() => expect(appele).toBe(CONTACTS[0].id));
    expect(await screen.findByText(/ne recevra plus la newsletter/)).toBeInTheDocument();
    await waitFor(() => expect(lectures).toBeGreaterThanOrEqual(2));
  });

  it("contre-épreuve : sans confirmation, rien ne part", async () => {
    let appele = false;
    server.use(
      http.get(`${DASH}/audience/`, () =>
        HttpResponse.json({ contacts: CONTACTS, total: 2, inscrits_a_la_lettre: 1 }),
      ),
      http.post(`${DASH}/audience/:id/desinscrire/`, () => {
        appele = true;
        return HttpResponse.json({});
      }),
    );
    vi.spyOn(window, "confirm").mockReturnValue(false);
    rendreLEcran();
    fireEvent.click(await screen.findByRole("button", { name: /Désinscrire marie/ }));
    await new Promise((fin) => setTimeout(fin, 50));
    expect(appele).toBe(false);
  });

  it("exporte les seuls inscrits à la lettre, sous le jeton", async () => {
    let autorisation = "";
    let demande = "";
    server.use(
      http.get(`${DASH}/audience/`, () =>
        HttpResponse.json({ contacts: CONTACTS, total: 2, inscrits_a_la_lettre: 1 }),
      ),
      http.get(`${DASH}/audience.csv`, ({ request }) => {
        autorisation = request.headers.get("Authorization") ?? "";
        demande = new URL(request.url).search;
        return new HttpResponse("Adresse e-mail;…", {
          headers: {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": 'attachment; filename="newsletter-evkha-inscrits.csv"',
          },
        });
      }),
    );
    // jsdom n'a pas d'URL d'objet.
    URL.createObjectURL = vi.fn(() => "blob:fichier");
    URL.revokeObjectURL = vi.fn();
    rendreLEcran();
    // Le bouton attend la liste : sans adresse, il n'y a rien à exporter.
    await screen.findByText("marie@exemple.fr");
    fireEvent.click(screen.getByRole("button", { name: /Inscrits à la newsletter/ }));

    await waitFor(() =>
      expect(document.querySelector(".bandeau")?.textContent ?? "").toMatch(/newsletter-evkha-inscrits\.csv/),
    );
    expect(demande).toBe("?lettre=1");
    expect(autorisation).toBe("Bearer jeton-d-administration");
    expect(liensCliques).toContain("blob:fichier");
  });

  it("efface une personne après confirmation", async () => {
    let appele = "";
    server.use(
      http.get(`${DASH}/audience/`, () =>
        HttpResponse.json({ contacts: CONTACTS, total: 2, inscrits_a_la_lettre: 1 }),
      ),
      http.post(`${DASH}/audience/:id/supprimer/`, ({ params }) => {
        appele = String(params.id);
        return HttpResponse.json({ supprime: true });
      }),
    );
    const confirmation = vi.spyOn(window, "confirm").mockReturnValue(true);
    rendreLEcran();
    fireEvent.click(await screen.findByRole("button", { name: /Effacer paul/ }));
    await waitFor(() => expect(appele).toBe(CONTACTS[1].id));
    expect(confirmation.mock.calls[0][0]).toMatch(/irréversible/);
    expect(await screen.findByText(/est effacée/)).toBeInTheDocument();
  });

  it("un échec de lecture ne se lit pas « aucune adresse » (règle 1)", async () => {
    server.use(http.get(`${DASH}/audience/`, () => HttpResponse.json({}, { status: 500 })));
    rendreLEcran();
    await waitFor(() => expect(document.querySelector(".bandeau")).not.toBeNull());
    expect(screen.queryByText(/Aucune adresse/)).toBeNull();
  });
});

// ── Ce que la relecture du 25/11/2026 a demandé ─────────────────────────────

describe("les formulaires de la page écrite", () => {
  it("portent method=\"post\" : un envoi natif ne met jamais l'adresse dans l'URL", () => {
    formulaireDeChecklist();
    render(<FormulaireLettre bouton="Je m'abonne" mention="Je déteste le spam." />);
    const formulaires = Array.from(document.querySelectorAll("form"));
    expect(formulaires).toHaveLength(2);
    for (const formulaire of formulaires) expect(formulaire.getAttribute("method")).toBe("post");
  });

  it("reconnaissent l'hôte du pré-rendu, celui qu'écrit le script", () => {
    const script = readFileSync(join(process.cwd(), "scripts", "prerendre.mjs"), "utf-8");
    expect(script).toContain(`url: "https://${HOTE_DU_PRERENDU}/"`);
    // Hors pré-rendu, les champs sont actifs.
    formulaireDeChecklist();
    expect(screen.getByLabelText("Votre adresse e-mail")).not.toBeDisabled();
  });
});

describe("les mots du site suivent le téléchargement", () => {
  it("le menu ne promet plus un envoi par e-mail de la checklist et du lexique", () => {
    const textes = JSON.stringify(NAVIGATION);
    expect(textes).not.toMatch(/checklist et un lexique à recevoir par e-mail/);
    expect(textes).toMatch(/checklist et un lexique à télécharger/);
  });

  it("la case de chaque document est celle du relevé, une seule source", () => {
    const source = readFileSync(join(process.cwd(), "src", "public", "contenuRessources.ts"), "utf-8");
    for (const releve of Object.values(RELEVES_DES_DOCUMENTS)) {
      // Le libellé n'est écrit qu'une fois : dans `contenuAudience`.
      expect(source).not.toContain(releve.consentement);
    }
  });
});

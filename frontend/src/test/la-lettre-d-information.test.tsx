/** L'écran « Lettre d'information » de l'administration (26/11/2026).
 *
 * Ce qu'il verrouille :
 * - l'éditeur enrichi est là, avec sa barre d'outils, et une image téléversée
 *   entre dans le texte enregistré par son adresse publique ;
 * - « Envoyer maintenant » enregistre PUIS programme, après confirmation, et
 *   rien ne part sans elle ;
 * - sans abonné, l'envoi est fermé ;
 * - l'essai part à l'adresse saisie, avec le contenu en cours ;
 * - une lettre envoyée se lit dans un cadre isolé et ne s'envoie plus ;
 * - un lien ne vise qu'une page web ou une adresse e-mail.
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
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LettreAdmin } from "../admin/pages/Lettre";
import { adresseDeLien } from "../admin/pages/lettre/outils";
import { server } from "./server";

const DASH = `${window.location.origin}/api/dashboard/lettre`;

// jsdom ne mesure rien : ProseMirror, en plaçant le curseur, demande la
// position d'une plage de texte et fait défiler la page. Sans ces doublures,
// l'erreur part hors de tout test et rend la suite rouge.
const RECT_VIDE = { x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0, toJSON: () => ({}) };
if (!Range.prototype.getClientRects) {
  Range.prototype.getClientRects = () =>
    Object.assign([], { item: () => null }) as unknown as DOMRectList;
  Range.prototype.getBoundingClientRect = () => RECT_VIDE as DOMRect;
}
if (!document.elementFromPoint) document.elementFromPoint = () => null;
window.scrollTo = () => undefined;
Element.prototype.scrollIntoView = () => undefined;

const ENVOIS = { a_envoyer: 0, en_cours: 0, envoye: 0, echec: 0, ignore: 0 };

function lettre(champs: Record<string, unknown> = {}) {
  return {
    id: "l1",
    objet: "Les nouveautés de décembre",
    apercu: "",
    corps_html: "<p>Bonjour à toutes et à tous</p>",
    statut: "brouillon",
    programmee_pour: null,
    lancee_le: null,
    terminee_le: null,
    cree_le: "2026-11-26T10:00:00Z",
    modifiee_le: "2026-11-26T10:00:00Z",
    envois: ENVOIS,
    ...champs,
  };
}

function servir({ inscrits = 3, fiche = lettre() } = {}) {
  server.use(
    http.get(`${DASH}/`, () =>
      HttpResponse.json({
        inscrits,
        en_attente_de_confirmation: 2,
        desinscrits: 1,
        declencheurs: [{ valeur: "inscription", libelle: "Confirmation de l'inscription" }],
      }),
    ),
    http.get(`${DASH}/lettres/`, () => HttpResponse.json({ lettres: [fiche], inscrits })),
    http.get(`${DASH}/lettres/l1/`, () => HttpResponse.json(fiche)),
    http.get(`${DASH}/modeles/`, () => HttpResponse.json({ modeles: [] })),
    // L'aperçu du serveur : le corps reçu, dans un gabarit reconnaissable.
    http.post(`${DASH}/apercu/`, async ({ request }) => {
      const corps = (await request.json()) as { corps_html: string };
      return HttpResponse.json({ html: `<html><body>GABARIT EVKHA ${corps.corps_html}</body></html>` });
    }),
  );
}

function rendre() {
  localStorage.setItem("evkha_token", "jeton-d-administration");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // Un routeur minimal : l'onglet Abonnés porte un lien vers l'écran Audience.
  const racine = createRootRoute({ component: () => <LettreAdmin /> });
  const routeur = createRouter({
    routeTree: racine.addChildren([
      createRoute({ getParentRoute: () => racine, path: "/admin/audience", component: () => null }),
    ]),
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
  // Mode strict, comme `main.tsx` : React démonte et remonte chaque composant,
  // ce qui détruit puis recrée l'éditeur — le cas qui faisait tomber l'écran.
  return render(
    <React.StrictMode>
      <QueryClientProvider client={client}>
        <RouterProvider router={routeur} />
      </QueryClientProvider>
    </React.StrictMode>,
  );
}

async function ouvrirLaLettre(libelle: RegExp = /Modifier/) {
  fireEvent.click(await screen.findByRole("button", { name: libelle }));
}

beforeEach(() => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("les liens de l'éditeur", () => {
  it("acceptent une page web ou une adresse e-mail", () => {
    expect(adresseDeLien("evkha.fr")).toBe("https://evkha.fr/");
    expect(adresseDeLien("https://evkha.fr/boite-a-outils")).toBe("https://evkha.fr/boite-a-outils");
    expect(adresseDeLien("contact@evkha.fr")).toBe("mailto:contact@evkha.fr");
  });

  it("contre-épreuve : refusent ce qui n'en est pas une", () => {
    for (const faux of ["javascript:alert(1)", "bonjour", "", "data:text/html,x"]) {
      expect(adresseDeLien(faux), faux).toBeNull();
    }
  });
});

describe("l'écran de la lettre", () => {
  it("dit qui reçoit la lettre et liste les lettres", async () => {
    servir();
    rendre();
    expect(await screen.findByText("Ont confirmé leur adresse")).toBeInTheDocument();
    expect(screen.getByText("Les nouveautés de décembre")).toBeInTheDocument();
    expect(screen.getByText("Brouillon")).toBeInTheDocument();
  });

  it("ouvre l'éditeur enrichi, avec sa barre d'outils", async () => {
    servir();
    rendre();
    await ouvrirLaLettre();
    const barre = await screen.findByRole("toolbar", { name: "Mise en forme du texte" }, { timeout: 5000 });
    for (const nom of ["Gras", "Italique", "Souligné", "Ajouter un lien", "Insérer une image", "Centrer"]) {
      expect(barre.querySelector(`[aria-label="${nom}"]`), nom).not.toBeNull();
    }
    expect(screen.getByRole("textbox", { name: "Texte de la newsletter" })).toHaveTextContent(
      "Bonjour à toutes et à tous",
    );
  });

  it("une image téléversée entre dans le texte par son adresse publique", async () => {
    servir();
    let recu: unknown = null;
    let appelImage = false;
    server.use(
      http.post(`${DASH}/images/`, () => {
        // Le FormData de jsdom n'est pas celui de `fetch` : son corps ne se
        // relit pas ici. Le téléversement lui-même est éprouvé côté serveur
        // (`test_une_image_televersee_est_publique_et_redessinee`).
        appelImage = true;
        return HttpResponse.json({ url: "https://api2.evkha.fr/media/lettre-vitrine/a.png" }, { status: 201 });
      }),
      http.put(`${DASH}/lettres/l1/`, async ({ request }) => {
        recu = await request.json();
        return HttpResponse.json(lettre());
      }),
    );
    const { container } = rendre();
    await ouvrirLaLettre();
    await screen.findByRole("toolbar", { name: "Mise en forme du texte" }, { timeout: 5000 });

    const champ = container.querySelector('input[type="file"]') as HTMLInputElement;
    const fichier = new File([new Uint8Array([137, 80, 78, 71])], "photo.png", { type: "image/png" });
    fireEvent.change(champ, { target: { files: [fichier] } });
    await waitFor(() => expect(appelImage).toBe(true));
    await waitFor(() =>
      expect(container.querySelector('.tiptap img[src="https://api2.evkha.fr/media/lettre-vitrine/a.png"]')).not.toBeNull(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Enregistrer le brouillon" }));
    await waitFor(() => expect(recu).not.toBeNull());
    expect((recu as { corps_html: string }).corps_html).toContain(
      'src="https://api2.evkha.fr/media/lettre-vitrine/a.png"',
    );
  });

  it("« Envoyer maintenant » enregistre puis programme, après confirmation", async () => {
    servir();
    const appels: string[] = [];
    let programme: unknown = null;
    server.use(
      http.put(`${DASH}/lettres/l1/`, () => {
        appels.push("enregistrer");
        return HttpResponse.json(lettre());
      }),
      http.post(`${DASH}/lettres/l1/programmer/`, async ({ request }) => {
        appels.push("programmer");
        programme = await request.json();
        return HttpResponse.json(
          lettre({ statut: "programmee", programmee_pour: new Date().toISOString(), destinataires_prevus: 3 }),
        );
      }),
    );
    rendre();
    await ouvrirLaLettre();
    fireEvent.click(await screen.findByRole("button", { name: "Envoyer maintenant" }));

    expect(await screen.findByText(/C'est parti : la newsletter part dans la minute à 3 inscrits/)).toBeInTheDocument();
    expect(appels).toEqual(["enregistrer", "programmer"]);
    expect(programme).toEqual({ quand: null });
    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("3 inscrits"));
  });

  it("contre-épreuve : sans confirmation, rien ne part", async () => {
    servir();
    vi.mocked(window.confirm).mockReturnValue(false);
    let programme = false;
    server.use(
      http.post(`${DASH}/lettres/l1/programmer/`, () => {
        programme = true;
        return HttpResponse.json(lettre());
      }),
    );
    rendre();
    await ouvrirLaLettre();
    fireEvent.click(await screen.findByRole("button", { name: "Envoyer maintenant" }));
    await new Promise((r) => setTimeout(r, 50));
    expect(programme).toBe(false);
  });

  it("sans abonné, l'envoi est fermé et le dit", async () => {
    servir({ inscrits: 0 });
    rendre();
    await ouvrirLaLettre();
    expect(await screen.findByRole("button", { name: "Envoyer maintenant" })).toBeDisabled();
    expect(screen.getByText(/Personne n'a encore confirmé son inscription/)).toBeInTheDocument();
  });

  it("l'essai part à l'adresse saisie, avec le contenu en cours", async () => {
    servir();
    let recu: Record<string, unknown> | null = null;
    server.use(
      http.post(`${DASH}/essai/`, async ({ request }) => {
        recu = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ envoye: true, adresse: "moi@exemple.fr" });
      }),
    );
    rendre();
    await ouvrirLaLettre();
    fireEvent.change(await screen.findByLabelText("S'envoyer un essai"), {
      target: { value: "moi@exemple.fr" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Envoyer l'essai" }));
    expect(await screen.findByText(/Exemplaire d'essai envoyé à moi@exemple.fr/)).toBeInTheDocument();
    expect(recu).toMatchObject({
      email: "moi@exemple.fr",
      objet: "Les nouveautés de décembre",
      corps_html: "<p>Bonjour à toutes et à tous</p>",
    });
  });

  it("une lettre envoyée se lit dans un cadre isolé, et ne s'envoie plus", async () => {
    servir({
      fiche: lettre({
        statut: "envoyee",
        terminee_le: "2026-11-26T11:00:00Z",
        envois: { ...ENVOIS, envoye: 41, echec: 1 },
      }),
    });
    const { container } = rendre();
    await ouvrirLaLettre(/Ouvrir/);
    expect(await screen.findByText(/41 reçues, 1 échec/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Envoyer maintenant" })).toBeNull();
    expect(screen.queryByRole("toolbar")).toBeNull();
    const cadre = await waitFor(() => {
      const trouve = container.querySelector('iframe[title="Aperçu du courriel"]');
      expect(trouve).not.toBeNull();
      return trouve;
    });
    expect(cadre).toHaveAttribute("sandbox", "");
  });

  it("retirer un message neuf garde le contenu de celui qui reste", async () => {
    servir();
    server.use(
      http.get(`${DASH}/automatisations/`, () => HttpResponse.json({ automatisations: [] })),
    );
    rendre();
    fireEvent.click(await screen.findByRole("button", { name: "Automatisations" }));
    fireEvent.click(await screen.findByRole("button", { name: /Nouvelle automatisation/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Ajouter un message" }));
    const objets = () => screen.getAllByLabelText(/^Objet/) as HTMLInputElement[];
    await waitFor(() => expect(objets()).toHaveLength(2));
    fireEvent.change(objets()[0], { target: { value: "Bienvenue" } });
    fireEvent.change(objets()[1], { target: { value: "Trois jours après" } });
    // L'état PROPRE à chaque message (ici l'adresse d'essai) : avec une clé
    // par position, le message restant hériterait de celui du disparu.
    const essais = () => screen.getAllByLabelText("S'envoyer un essai") as HTMLInputElement[];
    fireEvent.change(essais()[0], { target: { value: "premier@exemple.fr" } });

    fireEvent.click(screen.getAllByRole("button", { name: "Retirer" })[0]);
    await waitFor(() => expect(objets()).toHaveLength(1));
    expect(objets()[0].value).toBe("Trois jours après");
    expect(essais()[0].value).toBe("");
  });

  it("montre le courriel EN MÊME TEMPS que l'éditeur, tel que le serveur le rend", async () => {
    servir();
    const { container } = rendre();
    await ouvrirLaLettre();
    await screen.findByRole("toolbar", { name: "Mise en forme du texte" }, { timeout: 5000 });
    await waitFor(() => {
      const cadre = container.querySelector('iframe[title="Aperçu du courriel"]');
      expect(cadre?.getAttribute("srcdoc")).toContain("GABARIT EVKHA <p>Bonjour à toutes et à tous</p>");
    });
    expect(container.querySelector('iframe[title="Aperçu du courriel"]')).toHaveAttribute("sandbox", "");
  });

  it("chaque modèle se voit en vignette", async () => {
    servir();
    server.use(
      http.get(`${DASH}/modeles/`, () =>
        HttpResponse.json({
          modeles: [
            {
              id: "m1",
              nom: "Modèle EVKHA",
              objet: "Les nouvelles",
              apercu: "",
              corps_html: "<h1>Les nouvelles d'EVKHA</h1>",
              modifie_le: "2026-11-26T10:00:00Z",
            },
          ],
        }),
      ),
    );
    const { container } = rendre();
    fireEvent.click(await screen.findByRole("button", { name: "Modèles" }));
    expect(await screen.findByText("Modèle EVKHA")).toBeInTheDocument();
    await waitFor(() => {
      const vignette = container.querySelector('iframe[title="Aperçu du modèle Modèle EVKHA"]');
      expect(vignette?.getAttribute("srcdoc")).toContain("<h1>Les nouvelles d'EVKHA</h1>");
    });
  });

  it("ajoute des abonnés collés, seulement une fois l'accord coché", async () => {
    servir();
    let recu: unknown = null;
    server.use(
      http.post(`${DASH}/abonnes/`, async ({ request }) => {
        recu = await request.json();
        return HttpResponse.json({
          ajoutees: 2,
          deja_inscrites: 0,
          desinscrites_non_reinscrites: 1,
          lignes_ecartees: 0,
          invalides: [],
          invalides_total: 0,
          inscrits: 5,
        });
      }),
    );
    rendre();
    fireEvent.click(await screen.findByRole("button", { name: "Abonnés" }));
    const liste = "marie@exemple.fr\npaul@exemple.fr, partie@exemple.fr";
    fireEvent.change(await screen.findByLabelText("Adresses e-mail"), { target: { value: liste } });
    expect(screen.getByText("3 adresses repérées.")).toBeInTheDocument();
    // « élise@… » se compte une fois, comme un tout : jamais « lise@… » en plus.
    fireEvent.change(screen.getByLabelText("Adresses e-mail"), {
      target: { value: "élise@exemple.fr" },
    });
    expect(screen.getByText("1 adresse repérée.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Adresses e-mail"), { target: { value: liste } });
    const bouton = screen.getByRole("button", { name: "Ajouter à la newsletter" });
    const accord = screen.getByRole("checkbox", { name: /ont accepté de recevoir la newsletter/ });
    fireEvent.click(accord);
    // Sans provenance, rien ne part : c'est la trace de leur accord.
    expect(bouton).toBeDisabled();
    fireEvent.change(screen.getByLabelText("D'où vient cette liste ?"), {
      target: { value: "Export Systeme.io" },
    });
    fireEvent.click(bouton);
    expect(await screen.findByText(/2 adresses ajoutées ; 1 désinscrite laissée hors de la liste/)).toBeInTheDocument();
    expect(recu).toEqual({ texte: liste, provenance: "Export Systeme.io", consentement: true });
    // Chaque lot s'atteste à nouveau.
    expect(accord).not.toBeChecked();
  });

  it("écrire une newsletter depuis un modèle ouvre l'éditeur avec son texte", async () => {
    servir();
    server.use(
      http.get(`${DASH}/modeles/`, () =>
        HttpResponse.json({
          modeles: [
            {
              id: "m1",
              nom: "Modèle EVKHA",
              objet: "Les nouvelles",
              apercu: "",
              corps_html: "<h1>Les nouvelles d'EVKHA</h1>",
              modifie_le: "2026-11-26T10:00:00Z",
            },
          ],
        }),
      ),
    );
    rendre();
    fireEvent.click(await screen.findByRole("button", { name: "Modèles" }));
    fireEvent.click(await screen.findByRole("button", { name: "Écrire une newsletter" }));
    const texte = await screen.findByRole("textbox", { name: "Texte de la newsletter" }, { timeout: 5000 });
    await waitFor(() => expect(texte).toHaveTextContent("Les nouvelles d'EVKHA"));
    expect(screen.getByLabelText(/^Objet/)).toHaveValue("Les nouvelles");
  });
});

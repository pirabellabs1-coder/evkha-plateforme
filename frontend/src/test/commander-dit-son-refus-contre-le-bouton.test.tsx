/** Commander : le refus du serveur se lit contre le bouton, et l'écran dit la
 *  bonne charte.
 *
 * Audit du 19/11/2026, trois défauts du même écran.
 *
 * 1. **Le refus hors écran.** Abonnement inactif (402), solde insuffisant ou
 *    questionnaire incomplet (400), démarrage impossible (503) : le message du
 *    serveur n'était rendu qu'en TÊTE du questionnaire — vingt-quatre questions
 *    au-dessus du bouton « Lancer la génération ». On cliquait en bas, il ne se
 *    passait visiblement rien. Le même défaut que le dépôt de document, corrigé
 *    en août pour le dépôt seulement.
 *
 * 2. **La mauvaise charte.** Le récapitulatif écrivait toujours « repris de Ma
 *    marque ». Or une commande rattachée au projet d'une fiche client porte la
 *    charte de la FICHE (`commandes.charte_du_projet`), sans repli.
 *
 * 3. **Un échec lu comme un vide** : catalogue en panne = « Aucun crédit
 *    disponible », questionnaire en panne = squelette sans fin, bibliothèque
 *    en panne = « Aucun fichier déposé. ».
 *
 * Les refus ci-dessous sont ceux que rend `vues_espace.commander`, recopiés
 * du serveur (`{"error": …, "code": …}`).
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { jeton } from "../espace/api";
import { server } from "./server";

const navigations: unknown[] = [];

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => (cible: unknown) => {
    navigations.push(cible);
  },
  useRouterState: () => "",
  Link: ({ children }: { children: React.ReactNode }) => <a href="#">{children}</a>,
}));

// Importé APRÈS le simulacre du routeur.
const { Commander } = await import("../espace/pages/Commander");

const ESPACE = `${window.location.origin}/api/espace`;

const MOI = {
  acces_ouvert: true,
  assistance: false,
  utilisateur: {
    email: "eva@exemple.fr",
    prenom: "Eva",
    nom: "",
    role: "proprietaire",
    droits: ["commander", "consulter_livrables"],
  },
  organisation: {
    id: "org-1",
    raison_sociale: "Cabinet Eva",
    statut: "active",
    marque_blanche: true,
    validation_socle_par_client: false,
    type_de_compte: "abonne",
  },
  credits: { solde: 3, seuil_alerte: 1, alerte: false },
  abonnement: null,
  souscription_en_attente: null,
};

const CATALOGUE = {
  solde: 3,
  peut_commander: true,
  documents: [
    {
      type: "market_study",
      libelle: "Étude de marché",
      description: "Votre marché, chiffré et sourcé.",
      cout_credits: 1,
      questions: 2,
      couvert: true,
    },
  ],
};

const QUESTIONNAIRE = {
  type: "market_study",
  titre: "Questionnaire — Étude de marché",
  note: "Répondez avec vos mots.",
  sections: [
    {
      titre: "Votre projet",
      introduction: "",
      champs: [
        { identifiant: "PROJET", libelle: "Nom du projet", obligatoire: true, type: "texte", aide: "", exemple: "" },
        { identifiant: "SECTEUR", libelle: "Secteur d'activité", obligatoire: true, type: "texte", aide: "", exemple: "" },
      ],
    },
  ],
};

/** Les lectures de l'écran, toutes en état de marche. */
function espaceEnMarche() {
  server.use(
    http.get(`${ESPACE}/moi/`, () => HttpResponse.json(MOI)),
    http.get(`${ESPACE}/catalogue/`, () => HttpResponse.json(CATALOGUE)),
    http.get(`${ESPACE}/formulaire/market_study/`, () => HttpResponse.json(QUESTIONNAIRE)),
    http.get(`${ESPACE}/fichiers/`, () => HttpResponse.json({ pieces: [] })),
    http.get(`${ESPACE}/projets/p-1/reponses/market_study/`, () =>
      HttpResponse.json({
        projet: { id: "p-1", nom: "Dibitek Forge", archive: false },
        client: { id: "c-1", nom: "Dibitek" },
        reponses: { SECTEUR: "Métallurgie" },
      }),
    ),
  );
}

function rendre(recherche: string) {
  window.history.pushState({}, "", `/espace/commander${recherche}`);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Commander />
    </QueryClientProvider>,
  );
}

/** Le bouton de lancement, une fois CLIQUABLE.
 *
 *  Il reste désactivé tant que le compte n'est pas lu (c'est lui qui dit si
 *  le rôle permet de commander) : cliquer avant ne ferait rien, et le test
 *  passerait ou échouerait selon l'ordre d'arrivée des réponses. */
async function boutonPret(): Promise<HTMLElement> {
  const bouton = await screen.findByRole("button", { name: /Lancer la génération/ });
  await waitFor(() => expect(bouton).toBeEnabled());
  return bouton;
}

/** La carte qui porte le bouton de lancement. Lue AVANT tout clic : pendant
 *  l'envoi, le bouton s'appelle « Lancement… ». */
async function carteDuBouton(): Promise<HTMLElement> {
  return (await boutonPret()).closest("section") as HTMLElement;
}

async function remplirEtLancer(): Promise<HTMLElement> {
  const bouton = await boutonPret();
  const carte = bouton.closest("section") as HTMLElement;
  fireEvent.change(screen.getByLabelText(/Nom du projet/), { target: { value: "Forge" } });
  fireEvent.change(screen.getByLabelText(/Secteur d'activité/), { target: { value: "Métallurgie" } });
  fireEvent.click(bouton);
  return carte;
}

describe("commander dit son refus contre le bouton", () => {
  beforeEach(() => {
    localStorage.clear();
    jeton.ecrire("jeton-de-session");
    navigations.length = 0;
    // jsdom ne fait pas défiler : l'écran y recourt pour les champs manquants.
    Element.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    window.history.pushState({}, "", "/");
  });

  // ── 1. Le refus du serveur ────────────────────────────────────────────────

  it.each([
    [402, "souscription_requise", "Votre abonnement n'est pas actif. Activez-le pour commander un document."],
    [400, "commande_refusee", "Solde insuffisant : cette étude coûte 1 crédit."],
    [
      503,
      "demarrage_impossible",
      "Votre commande est enregistrée, mais son démarrage a échoué de notre côté. Rien n'a été débité.",
    ],
  ])("un refus %i (%s) s'affiche dans la carte du bouton", async (statut, code, message) => {
    espaceEnMarche();
    server.use(
      http.post(`${ESPACE}/commander/`, () =>
        HttpResponse.json({ error: message, code }, { status: statut }),
      ),
    );
    rendre("?livrable=market_study");
    const carte = await remplirEtLancer();

    // Contre le bouton : dans SA carte, et annoncé.
    const alerte = await within(carte).findByRole("alert");
    expect(alerte).toHaveTextContent(message);
    expect(navigations).toEqual([]);
  });

  it("contre-épreuve : une commande acceptée n'affiche aucun refus, et mène aux livrables", async () => {
    espaceEnMarche();
    server.use(
      http.post(`${ESPACE}/commander/`, () =>
        HttpResponse.json(
          { job_id: "job-1", statut: "pending", type: "market_study", cout_credits: 1 },
          { status: 202 },
        ),
      ),
    );
    rendre("?livrable=market_study");
    await remplirEtLancer();

    await waitFor(() => expect(navigations).toEqual([{ to: "/espace/livrables" }]));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("contre-épreuve : des réponses manquantes n'envoient rien, et ne se disent pas « refus »", async () => {
    espaceEnMarche();
    let envois = 0;
    server.use(
      http.post(`${ESPACE}/commander/`, () => {
        envois += 1;
        return HttpResponse.json({ error: "ne devrait pas partir", code: "x" }, { status: 400 });
      }),
    );
    rendre("?livrable=market_study");

    const bouton = await boutonPret();
    // Des espaces : le contrôle natif du navigateur (`required`) les laisse
    // passer, c'est celui de l'écran qui les arrête.
    fireEvent.change(screen.getByLabelText(/Nom du projet/), { target: { value: "  " } });
    fireEvent.change(screen.getByLabelText(/Secteur d'activité/), { target: { value: "  " } });
    fireEvent.click(bouton);
    expect(await screen.findByText(/2 réponse\(s\) manquante\(s\)/)).toBeInTheDocument();
    expect(within(bouton.closest("section") as HTMLElement).queryByRole("alert")).toBeNull();
    expect(envois).toBe(0);
  });

  // ── 2. La charte annoncée ─────────────────────────────────────────────────

  it("avec un projet de fiche client, le récapitulatif annonce la charte de la FICHE", async () => {
    espaceEnMarche();
    rendre("?livrable=market_study&projet=p-1");

    const carte = await carteDuBouton();
    expect(within(carte).getByText(/ceux de la fiche client « Dibitek »/)).toBeInTheDocument();
    expect(within(carte).queryByText(/sont repris de « Ma marque »/)).toBeNull();
    // La mention de confidentialité, elle, reste celle de l'abonnée.
    expect(within(carte).getByText(/mention de confidentialité/)).toBeInTheDocument();
  });

  it("contre-épreuve : sans projet, c'est bien « Ma marque » qui habille le document", async () => {
    espaceEnMarche();
    rendre("?livrable=market_study");

    const carte = await carteDuBouton();
    expect(within(carte).getByText(/sont repris de « Ma marque »/)).toBeInTheDocument();
    expect(within(carte).queryByText(/fiche client/)).toBeNull();
  });

  // ── 3. Un échec n'est pas un vide ─────────────────────────────────────────

  it("un catalogue en panne ne se lit pas « Aucun crédit disponible »", async () => {
    espaceEnMarche();
    server.use(http.get(`${ESPACE}/catalogue/`, () => new HttpResponse("panne", { status: 500 })));
    rendre("");

    expect(await screen.findByText(/Impossible de charger le catalogue/)).toBeInTheDocument();
    expect(screen.queryByText(/Aucun crédit disponible|Abonnement à activer|Aucune étude en attente/)).toBeNull();
    expect(screen.queryByText(/Solde : 0 crédit/)).toBeNull();
  });

  it("contre-épreuve : un solde nul REÇU dit bien ce qui manque", async () => {
    espaceEnMarche();
    server.use(
      http.get(`${ESPACE}/catalogue/`, () => HttpResponse.json({ ...CATALOGUE, solde: 0 })),
    );
    rendre("");

    expect(await screen.findByText(/Abonnement à activer/)).toBeInTheDocument();
    expect(screen.queryByText(/Impossible de charger/)).toBeNull();
  });

  it("un questionnaire en panne se dit, et rend la main", async () => {
    espaceEnMarche();
    server.use(
      http.get(`${ESPACE}/formulaire/market_study/`, () => new HttpResponse("panne", { status: 500 })),
    );
    rendre("?livrable=market_study");

    expect(await screen.findByText(/Impossible de charger le questionnaire/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Choisir un autre document/ }));
    expect(await screen.findByText(/Que souhaitez-vous produire/)).toBeInTheDocument();
  });

  it("une bibliothèque en panne ne se lit pas « Aucun fichier déposé »", async () => {
    espaceEnMarche();
    server.use(http.get(`${ESPACE}/fichiers/`, () => new HttpResponse("panne", { status: 500 })));
    rendre("?livrable=market_study");

    expect(await screen.findByText(/Impossible de charger vos documents déposés/)).toBeInTheDocument();
    expect(screen.queryByText(/Aucun fichier déposé/)).toBeNull();
  });

  it("contre-épreuve : une bibliothèque vide REÇUE dit bien « Aucun fichier déposé »", async () => {
    espaceEnMarche();
    rendre("?livrable=market_study");

    expect(await screen.findByText(/Aucun fichier déposé/)).toBeInTheDocument();
  });
});

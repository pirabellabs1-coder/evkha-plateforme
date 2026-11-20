/** Le suivi des élèves vu de l'administration : ce que la gérante PROUVE.
 *
 * Elle est certifiée Qualiopi. Pour une formation, un auditeur lui demande qui
 * l'a suivie, jusqu'où, et qui était présent à quelle séance. Le serveur
 * (`dashboard/suivi_des_formations.py`, `catalog/suivi.py`) calcule tout ;
 * l'écran `admin/pages/Formations.tsx` le montre. Les charges servies ici ont
 * la forme que ces vues écrivent, clé par clé.
 *
 * Ce que ce fichier verrouille :
 *
 * 1. la fiche : le champ « Durée d'accès », ce que veut dire zéro, ce que la
 *    fin d'accès ne ferme pas, et l'envoi de `duree_d_acces_mois` ;
 * 2. le tableau des élèves : le nom (ou l'adresse quand il est vide), l'état
 *    de l'accès et sa fin, la dernière connexion, la progression — barre ET
 *    texte —, le cas « non calculable », le présentiel signé en heures et
 *    minutes ;
 * 3. changer la date de fin d'un accès : un jour, ou « Sans limite » ; le
 *    refus du serveur contre le champ ; la ligne affichée est celle qu'il
 *    rend ;
 * 4. l'export : le fichier est demandé PAR `fetch`, sous l'autorisation, puis
 *    remis au navigateur sous le nom que le serveur donne ; une panne se dit ;
 * 5. les séances : la liste et ses états ; créer, annuler, rétablir, signer
 *    (après confirmation), noter une signature papier — et chaque refus du
 *    serveur affiché avec sa phrase ;
 * 6. la feuille d'émargement : ce qu'elle porte, « Imprimer », et la feuille
 *    de style d'impression qui ne garde qu'elle.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique. Les gestionnaires MSW visent
 * `window.location.origin` (jsdom : http://localhost:3000).
 *
 * jsdom n'a ni `showModal()` ni mise en page : les fenêtres s'ouvrent par le
 * repli de `Fenetre`, et les cartes du téléphone comme l'impression ne se
 * jugent ici que sur les déclarations de la feuille.
 */
import React from "react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { FormationAdmin } from "../admin/api";
import { FormationsAdmin } from "../admin/pages/Formations";
import { server } from "./server";

const DASH = `${window.location.origin}/api/dashboard`;
const FEUILLE_DE_STYLE = join(process.cwd(), "src", "admin", "pages", "Formations.css");

// ── Ce que le serveur rend ──────────────────────────────────────────────────

const FORMATION: FormationAdmin = {
  id: "f-1",
  slug: "creer-son-entreprise",
  titre: "Créer son entreprise de A à Z",
  sous_titre: "",
  accroche: "",
  description: "",
  prix_cents: 149_000,
  devise: "EUR",
  duree_heures: 18,
  heures_de_coaching: 2,
  duree_d_acces_mois: 12,
  lien_d_achat: "",
  image: "",
  en_ligne: true,
  rang: 0,
  publiable: true,
  manque: [],
  cree_le: "2026-11-19T09:00:00+00:00",
  modifie_le: "2026-11-19T09:00:00+00:00",
  nombre_de_modules: 0,
  modules: [],
};

/** Une ligne du tableau, telle que `suivi.tableau_des_eleves` l'écrit. */
function unEleve(surcharges: Record<string, unknown> = {}) {
  return {
    achat_id: "a-1",
    eleve_id: "e-1",
    nom: "Eva Martin",
    email: "eva@exemple.fr",
    organisation: "Cabinet Eva",
    achete_le: "2026-11-03T12:00:00+00:00",
    acces_jusqu_au: "2027-11-03",
    acces: "ouvert",
    derniere_connexion: "2026-11-19T12:00:00+00:00",
    derniere_activite: "2026-11-18T12:00:00+00:00",
    lecons_terminees: 3,
    lecons_total: 8,
    pourcent: 37,
    minutes_en_presentiel_signees: 210,
    ...surcharges,
  };
}

const EVA = unEleve();
/** Sans nom, sans limite, jamais connectée, et aucune leçon au programme. */
const SANS_NOM = unEleve({
  achat_id: "a-2",
  eleve_id: null,
  nom: "",
  email: "nord@exemple.fr",
  organisation: "Atelier Nord",
  acces_jusqu_au: null,
  derniere_connexion: null,
  derniere_activite: null,
  lecons_terminees: 0,
  lecons_total: 0,
  pourcent: null,
  minutes_en_presentiel_signees: 0,
});
const ECHUE = unEleve({
  achat_id: "a-3",
  eleve_id: "e-3",
  nom: "Léa Roux",
  email: "lea@exemple.fr",
  organisation: "Studio Roux",
  acces_jusqu_au: "2026-10-01",
  acces: "echu",
  lecons_terminees: 8,
  pourcent: 100,
  minutes_en_presentiel_signees: 45,
});

/** L'achat `a-1`, tel que `_vue_achat` le rend. */
function unAchat(surcharges: Record<string, unknown> = {}) {
  return {
    id: "a-1",
    organisation: "Cabinet Eva",
    organisation_id: "org-1",
    email: "eva@exemple.fr",
    montant_cents: 149_000,
    devise: "EUR",
    achete_le: "2026-11-03T12:00:00+00:00",
    revoque_le: null,
    motif_de_revocation: "",
    acces_jusqu_au: "2027-11-03",
    acces: "ouvert",
    reference_paiement: "pi_test_1",
    ...surcharges,
  };
}

/** Une séance, telle que `_vue_seance` l'écrit. Passée par défaut. */
function uneSeance(surcharges: Record<string, unknown> = {}) {
  return {
    id: "s-1",
    formation_id: "f-1",
    intitule: "Journée 1",
    debut: "2020-11-10T08:00:00+00:00",
    duree_minutes: 210,
    lieu: "Salle Colbert, Lille",
    nom_de_la_formatrice: "Evangéline Dupont",
    annulee_le: null,
    signee_par_la_formatrice_le: null,
    emargements: [] as object[],
    ...surcharges,
  };
}

const SIGNATURE_D_EVA = {
  id: "em-1",
  achat_id: "a-1",
  eleve_id: "e-1",
  nom: "Eva Martin",
  signe_le: "2020-11-10T08:05:00+00:00",
  mode: "en_ligne",
  nom_signe: "Eva Martin",
  adresse_ip: "203.0.113.7",
};

// ── Outils ──────────────────────────────────────────────────────────────────

type Reponse = () => Response | Promise<Response>;

function refus(erreur: string, code: string, champ?: string, statut = 400) {
  return HttpResponse.json({ erreur, code, ...(champ ? { champ } : {}) }, { status: statut });
}

/** Écoute une écriture : note chaque corps reçu, et répond. */
function ecouter(chemin: string, repondre: (corps: unknown) => Response): unknown[] {
  const recus: unknown[] = [];
  server.use(
    http.post(`${DASH}/formations/${chemin}`, async ({ request }) => {
      const corps: unknown = await request.json();
      recus.push(corps);
      return repondre(corps);
    }),
  );
  return recus;
}

function servirLesEleves(lignes: object[], achats: object[] = [unAchat()]): { lectures: number } {
  const compte = { lectures: 0 };
  server.use(
    http.get(`${DASH}/formations/f-1/eleves/`, () => {
      compte.lectures += 1;
      return HttpResponse.json({ eleves: lignes, lecons_total: 8 });
    }),
    http.get(`${DASH}/formations/f-1/achats/`, () => HttpResponse.json({ achats })),
  );
  return compte;
}

function servirLesSeances(reponse: Reponse) {
  server.use(http.get(`${DASH}/formations/f-1/seances/`, () => reponse()));
}

const seances = (...liste: object[]): Reponse => () => HttpResponse.json({ seances: liste });

/** Monte l'écran et ouvre la formation. */
async function ouvrirLaFormation(formation: FormationAdmin = FORMATION) {
  server.use(http.get(`${DASH}/formations/`, () => HttpResponse.json({ formations: [formation] })));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <FormationsAdmin />
    </QueryClientProvider>,
  );
  fireEvent.click(
    await screen.findByRole("button", { name: `Ouvrir la formation “${formation.titre}”` }),
  );
  await screen.findByRole("button", { name: "Toutes les formations" });
}

function carte(titre: string): HTMLElement {
  return screen.getByRole("heading", { level: 2, name: titre }).closest("section") as HTMLElement;
}

async function deplierLesEleves() {
  fireEvent.click(within(carte("Élèves")).getByRole("button", { name: "Afficher les élèves" }));
  return within(carte("Élèves")).findByRole("table");
}

async function deplierLesSeances() {
  fireEvent.click(
    within(carte("Séances en présentiel")).getByRole("button", { name: "Afficher les séances" }),
  );
  await waitFor(() =>
    expect(carte("Séances en présentiel").querySelector(".squelette-groupe")).toBeNull(),
  );
}

/** Une ligne du tableau, par son organisation ; toute espace ramenée à
 *  l'ordinaire. */
function ligne(organisation: string): { element: HTMLElement; texte: string; etat: string } {
  const element = within(carte("Élèves")).getByText(organisation).closest("tr") as HTMLElement;
  return {
    element,
    texte: (element.textContent ?? "").replace(/\s/g, " "),
    etat: element.querySelector(".pastille")?.textContent ?? "",
  };
}

/** Une séance de la liste, par son intitulé. */
function seance(intitule: string): { element: HTMLElement; texte: string; etat: string } {
  const element = within(carte("Séances en présentiel"))
    .getByRole("heading", { level: 3, name: intitule })
    .closest("li") as HTMLElement;
  return {
    element,
    texte: (element.textContent ?? "").replace(/\s/g, " "),
    etat: element.querySelector(".pastille")?.textContent ?? "",
  };
}

function erreurContre(champ: HTMLElement): string {
  return (champ.getAttribute("aria-describedby") ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .map((id) => document.getElementById(id))
    .filter((element) => element?.classList.contains("champ-erreur"))
    .map((element) => element?.textContent ?? "")
    .join(" ");
}

function aideContre(champ: HTMLElement): string {
  return (champ.getAttribute("aria-describedby") ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .map((id) => document.getElementById(id))
    .filter((element) => element?.classList.contains("champ-aide"))
    .map((element) => element?.textContent ?? "")
    .join(" ");
}

function saisir(champ: HTMLElement, valeur: string) {
  fireEvent.change(champ, { target: { value: valeur } });
}

function pause(ms = 50): Promise<void> {
  return new Promise((resoudre) => setTimeout(resoudre, ms));
}

// jsdom ne sait pas fabriquer l'adresse d'un fichier en mémoire. Les deux
// fonctions sont posées pour tout le fichier, et jamais retirées : l'adresse
// est relâchée par une minuterie, après la fin du test.
const adressesCreees: Blob[] = [];
URL.createObjectURL = (blob: Blob | MediaSource) => {
  adressesCreees.push(blob as Blob);
  return "blob:fichier-en-memoire";
};
URL.revokeObjectURL = () => undefined;

beforeEach(() => {
  localStorage.setItem("evkha_token", "jeton-d-administration");
  adressesCreees.length = 0;
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  localStorage.clear();
  document.body.className = "";
});

// ── 1. La durée d'accès, sur la fiche ───────────────────────────────────────

describe("la durée d'accès d'une formation", () => {
  it("le champ montre la durée rendue, dit ce que veut dire zéro, et ce que la fin d'accès ne ferme pas", async () => {
    await ouvrirLaFormation();

    const champ = screen.getByLabelText("Durée d'accès, en mois");
    expect(champ).toHaveValue("12");
    const aide = aideContre(champ);
    expect(aide).toMatch(/0, ou vide : sans limite de durée/);
    expect(aide).toContain(
      "Au terme de l'accès, le programme, les textes et les documents ne s'ouvrent plus dans l'espace de l'élève. Une vidéo hébergée ailleurs reste lisible par qui en a gardé l'adresse : réglez sa confidentialité chez votre hébergeur vidéo.",
    );
  });

  it("zéro s'affiche vide ; une durée saisie part seule, sous `duree_d_acces_mois`", async () => {
    const envois = ecouter("f-1/", () =>
      HttpResponse.json({ formation: { ...FORMATION, duree_d_acces_mois: 6 }, refuses: [] }),
    );
    await ouvrirLaFormation({ ...FORMATION, duree_d_acces_mois: 0 });

    const champ = screen.getByLabelText("Durée d'accès, en mois");
    expect(champ).toHaveValue("");
    saisir(champ, "6");
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer la fiche" }));

    await waitFor(() => expect(envois).toEqual([{ duree_d_acces_mois: "6" }]));
    expect(await screen.findByText("La fiche est enregistrée.")).toBeInTheDocument();
  });

  it("vidée, elle part à zéro — sans limite — ; un refus du serveur se pose contre le champ", async () => {
    const envois = ecouter("f-1/", () =>
      refus("Cette valeur dépasse le maximum admis (600).", "valeur_trop_grande", "duree_d_acces_mois"),
    );
    await ouvrirLaFormation();

    const champ = screen.getByLabelText("Durée d'accès, en mois");
    saisir(champ, "");
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer la fiche" }));
    await waitFor(() => expect(envois).toEqual([{ duree_d_acces_mois: "0" }]));

    await waitFor(() =>
      expect(erreurContre(champ)).toBe("Cette valeur dépasse le maximum admis (600)."),
    );
    expect(champ).toHaveAttribute("aria-invalid", "true");
  });
});

// ── 2. Le tableau des élèves ────────────────────────────────────────────────

describe("le tableau des élèves", () => {
  it("une ligne par élève : nom, accès et sa fin, dernière connexion, progression, présentiel signé", async () => {
    servirLesEleves([EVA, SANS_NOM, ECHUE]);
    await ouvrirLaFormation();
    const tableau = await deplierLesEleves();

    expect(within(tableau).getAllByRole("row")).toHaveLength(4);
    expect(within(carte("Élèves")).getByText(/3 lignes — une par personne et par achat/)).toBeInTheDocument();

    const eva = ligne("Cabinet Eva");
    expect(within(eva.element).getByRole("rowheader")).toHaveTextContent("Eva Martin");
    expect(eva.texte).toContain("eva@exemple.fr");
    expect(eva.texte).toContain("3 novembre 2026");
    expect(eva.etat).toBe("Ouvert");
    expect(eva.texte).toContain("jusqu'au 3 novembre 2027");
    expect(eva.texte).toContain("19 nov. 2026");
    expect(eva.texte).toContain("18 nov. 2026");
    // La progression : la barre, avec ses valeurs, ET la même chose écrite.
    const barre = within(eva.element).getByRole("progressbar", { name: "Progression de Eva Martin" });
    expect(barre).toHaveAttribute("aria-valuenow", "37");
    expect(barre).toHaveAttribute("aria-valuemin", "0");
    expect(barre).toHaveAttribute("aria-valuemax", "100");
    expect(eva.texte).toContain("3 / 8 leçons — 37 %");
    // 210 minutes signées : en heures et minutes.
    expect(eva.texte).toContain("3 h 30");

    // Chaque valeur porte le libellé de sa colonne : c'est lui que la carte
    // du téléphone affiche.
    const libelles = [...eva.element.querySelectorAll("td[data-libelle]")].map((cellule) =>
      cellule.getAttribute("data-libelle"),
    );
    expect(libelles).toEqual([
      "Organisation",
      "Acheté le",
      "Accès",
      "Dernière connexion",
      "Dernière activité",
      "Progression",
      "Présentiel signé",
    ]);

    const echue = ligne("Studio Roux");
    expect(echue.etat).toBe("Échu");
    expect(echue.texte).toContain("jusqu'au 1 octobre 2026");
    expect(echue.texte).toContain("8 / 8 leçons — 100 %");
    expect(echue.texte).toContain("45 min");
  });

  it("sans nom, l'adresse nomme la ligne ; sans leçon au programme, la progression est dite « non calculable »", async () => {
    servirLesEleves([EVA, SANS_NOM]);
    await ouvrirLaFormation();
    await deplierLesEleves();

    const sansNom = ligne("Atelier Nord");
    expect(within(sansNom.element).getByRole("rowheader")).toHaveTextContent("nord@exemple.fr");
    expect(
      within(sansNom.element).getByRole("button", { name: "Retirer l'accès de “nord@exemple.fr”" }),
    ).toBeInTheDocument();
    expect(sansNom.texte).toContain("sans limite");
    expect(sansNom.texte).toContain("jamais");
    expect(sansNom.texte).toContain("non calculable : aucune leçon au programme");
    // Ni barre, ni pourcentage inventé.
    expect(within(sansNom.element).queryByRole("progressbar")).toBeNull();
    expect(sansNom.texte).not.toMatch(/\d\s?%/);
    // Un vrai zéro de présentiel, lui, se dit.
    expect(sansNom.texte).toContain("0 min");
  });

  it("contre-épreuve : un pourcentage de zéro REÇU est une vraie progression, avec sa barre", async () => {
    servirLesEleves([unEleve({ lecons_terminees: 0, pourcent: 0 })]);
    await ouvrirLaFormation();
    await deplierLesEleves();

    const eva = ligne("Cabinet Eva");
    expect(within(eva.element).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");
    expect(eva.texte).toContain("0 / 8 leçons — 0 %");
    expect(eva.texte).not.toContain("non calculable");
  });

  it("sur téléphone les lignes sont des cartes : la feuille le déclare, et ne rend le tableau qu'à partir de 1100 px", () => {
    const css = readFileSync(FEUILLE_DE_STYLE, "utf-8").replace(/\r\n/g, "\n");
    const [avant, apres] = css.split("@media (min-width: 1100px)");
    expect(apres).toBeDefined();
    // Par défaut : des blocs, et le libellé de chaque valeur devant elle.
    expect(avant).toMatch(/\.tableau\.frm-eleves tbody td \{\s*display: block;/);
    expect(avant).toMatch(/td\[data-libelle\]::before \{\s*content: attr\(data-libelle\);/);
    // Sur grand écran : un vrai tableau.
    expect(apres).toMatch(/\.tableau\.frm-eleves \{\s*display: table;/);
  });
});

// ── 3. La date de fin d'un accès ────────────────────────────────────────────

describe("changer la date de fin d'un accès", () => {
  async function ouvrirLeGeste() {
    servirLesEleves([EVA]);
    await ouvrirLaFormation();
    await deplierLesEleves();
    const bouton = screen.getByRole("button", { name: "Changer la date de fin d'accès de “Eva Martin”" });
    fireEvent.click(bouton);
    const cadre = screen.getByRole("group", { name: /Date de fin d'accès de « Eva Martin »/ });
    return { bouton, cadre, champ: within(cadre).getByLabelText("Dernier jour d'accès") };
  }

  it("un jour choisi part en `acces_jusqu_au`, et la ligne montre la date que le serveur rend", async () => {
    const envois = ecouter("achats/a-1/", () =>
      HttpResponse.json({ achat: unAchat({ acces_jusqu_au: "2028-01-31" }) }),
    );
    const { bouton, cadre, champ } = await ouvrirLeGeste();

    // Le champ part de la date en place, et rien n'est envoyé à l'ouverture.
    expect(champ).toHaveAttribute("type", "date");
    expect(champ).toHaveValue("2027-11-03");
    expect(cadre).toHaveAccessibleDescription(/Aujourd'hui : jusqu'au 3 novembre 2027/);
    expect(envois).toEqual([]);

    saisir(champ, "2028-01-31");
    fireEvent.click(within(cadre).getByRole("button", { name: "Enregistrer la date" }));

    await waitFor(() => expect(screen.queryByRole("group", { name: /Date de fin/ })).toBeNull());
    // La date seule : ni `revoque`, ni motif.
    expect(envois).toEqual([{ acces_jusqu_au: "2028-01-31" }]);
    expect(ligne("Cabinet Eva").texte).toContain("jusqu'au 31 janvier 2028");
    expect(within(carte("Élèves")).getByRole("status")).toHaveTextContent(
      /L'accès de « Eva Martin » court maintenant jusqu'au 31 janvier 2028 inclus/,
    );
    expect(bouton).toHaveFocus();
  });

  it("« Sans limite » envoie `null`, et la ligne le dit", async () => {
    const envois = ecouter("achats/a-1/", () =>
      HttpResponse.json({ achat: unAchat({ acces_jusqu_au: null }) }),
    );
    const { cadre } = await ouvrirLeGeste();

    fireEvent.click(within(cadre).getByRole("button", { name: "Sans limite" }));

    await waitFor(() => expect(envois).toEqual([{ acces_jusqu_au: null }]));
    await waitFor(() => expect(ligne("Cabinet Eva").texte).toContain("sans limite"));
    expect(ligne("Cabinet Eva").texte).not.toContain("jusqu'au");
    expect(within(carte("Élèves")).getByRole("status")).toHaveTextContent(/sans limite de durée/);
  });

  it("une date passée ferme l'accès : l'état rendu (« Échu ») s'affiche, et l'annonce le dit", async () => {
    ecouter("achats/a-1/", () =>
      HttpResponse.json({ achat: unAchat({ acces_jusqu_au: "2026-01-01", acces: "echu" }) }),
    );
    const { cadre, champ } = await ouvrirLeGeste();

    saisir(champ, "2026-01-01");
    fireEvent.click(within(cadre).getByRole("button", { name: "Enregistrer la date" }));

    await waitFor(() => expect(ligne("Cabinet Eva").etat).toBe("Échu"));
    expect(within(carte("Élèves")).getByRole("status")).toHaveTextContent(/Cette date est passée : l'accès est échu/);
  });

  it("sans date : aucun envoi, et le champ dit quoi faire", async () => {
    const envois = ecouter("achats/a-1/", () => HttpResponse.json({ achat: unAchat() }));
    const { cadre, champ } = await ouvrirLeGeste();

    saisir(champ, "");
    fireEvent.click(within(cadre).getByRole("button", { name: "Enregistrer la date" }));

    expect(erreurContre(champ)).toMatch(/Choisissez une date, ou cliquez sur « Sans limite »/);
    await pause();
    expect(envois).toEqual([]);
  });

  it("le refus du serveur (400 `date_illisible`) se pose CONTRE le champ, et le cadre reste", async () => {
    const ILLISIBLE = "Cette date est illisible : écrivez-la sous la forme AAAA-MM-JJ.";
    ecouter("achats/a-1/", () => refus(ILLISIBLE, "date_illisible", "acces_jusqu_au"));
    const { cadre, champ } = await ouvrirLeGeste();

    saisir(champ, "2028-01-31");
    fireEvent.click(within(cadre).getByRole("button", { name: "Enregistrer la date" }));

    await waitFor(() => expect(erreurContre(champ)).toBe(ILLISIBLE));
    expect(champ).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("group", { name: /Date de fin/ })).toBeInTheDocument();
    expect(ligne("Cabinet Eva").texte).toContain("jusqu'au 3 novembre 2027");
    expect(within(carte("Élèves")).queryByRole("alert")).toBeNull();
  });

  it("contre-épreuve : « Annuler » n'envoie rien et rend le focus au bouton", async () => {
    const envois = ecouter("achats/a-1/", () => HttpResponse.json({ achat: unAchat() }));
    const { bouton, cadre } = await ouvrirLeGeste();

    fireEvent.click(within(cadre).getByRole("button", { name: "Annuler" }));

    expect(screen.queryByRole("group", { name: /Date de fin/ })).toBeNull();
    expect(bouton).toHaveFocus();
    await pause();
    expect(envois).toEqual([]);
  });
});

// ── 4. L'export pour l'auditeur ─────────────────────────────────────────────

describe("exporter le tableau des élèves", () => {
  it("le fichier est demandé par fetch SOUS l'autorisation, puis remis au navigateur sous le nom du serveur", async () => {
    const demandes: (string | null)[] = [];
    const CSV = "nom;adresse\nEva Martin;eva@exemple.fr\n";
    server.use(
      http.get(`${DASH}/formations/f-1/eleves.csv`, ({ request }) => {
        demandes.push(request.headers.get("Authorization"));
        return new HttpResponse(CSV, {
          headers: {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": 'attachment; filename="eleves-creer-son-entreprise.csv"',
          },
        });
      }),
    );
    servirLesEleves([EVA]);
    // Le lien que l'écran fabrique pour remettre le fichier.
    const liens: { nom: string; adresse: string }[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      liens.push({ nom: this.download, adresse: this.getAttribute("href") ?? "" });
    });
    await ouvrirLaFormation();
    await deplierLesEleves();

    // Un BOUTON, pas un lien vers le fichier : un lien ne porterait pas le jeton.
    expect(carte("Élèves").querySelector('a[href*="eleves.csv"]')).toBeNull();
    fireEvent.click(within(carte("Élèves")).getByRole("button", { name: "Exporter (CSV)" }));

    await waitFor(() => expect(liens).toHaveLength(1));
    expect(demandes).toEqual(["Bearer jeton-d-administration"]);
    expect(liens[0]).toEqual({ nom: "eleves-creer-son-entreprise.csv", adresse: "blob:fichier-en-memoire" });
    // C'est bien le fichier reçu qui est remis.
    expect(adressesCreees).toHaveLength(1);
    expect(adressesCreees[0].size).toBe(CSV.length);
    expect(adressesCreees[0].type).toContain("text/csv");
    expect(within(carte("Élèves")).getByRole("status")).toHaveTextContent(
      /« eleves-creer-son-entreprise\.csv » est prêt/,
    );
    // Le lien de passage ne reste pas dans la page.
    expect(document.querySelector("a[download]")).toBeNull();
  });

  it("sans nom lisible dans la réponse, le fichier porte le nom de la formation", async () => {
    server.use(
      http.get(`${DASH}/formations/f-1/eleves.csv`, () => new HttpResponse("nom\n", { headers: { "Content-Type": "text/csv" } })),
    );
    servirLesEleves([EVA]);
    const noms: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      noms.push(this.download);
    });
    await ouvrirLaFormation();
    await deplierLesEleves();

    fireEvent.click(within(carte("Élèves")).getByRole("button", { name: "Exporter (CSV)" }));

    await waitFor(() => expect(noms).toEqual(["eleves-creer-son-entreprise.csv"]));
  });

  it("une panne se dit, avec la phrase du serveur, et rien n'est remis au navigateur", async () => {
    server.use(
      http.get(`${DASH}/formations/f-1/eleves.csv`, () =>
        refus("Cette formation n'existe pas.", "formation_inconnue", undefined, 404),
      ),
    );
    servirLesEleves([EVA]);
    const clic = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    await ouvrirLaFormation();
    await deplierLesEleves();

    fireEvent.click(within(carte("Élèves")).getByRole("button", { name: "Exporter (CSV)" }));

    expect(await within(carte("Élèves")).findByRole("alert")).toHaveTextContent("Cette formation n'existe pas.");
    expect(clic).not.toHaveBeenCalled();
    expect(adressesCreees).toEqual([]);
    // On peut réessayer : le bouton n'est pas resté occupé.
    await waitFor(() =>
      expect(within(carte("Élèves")).getByRole("button", { name: "Exporter (CSV)" })).not.toHaveAttribute(
        "aria-disabled",
      ),
    );
  });
});

// ── 5. Les séances en présentiel ────────────────────────────────────────────

describe("les séances en présentiel", () => {
  const A_VENIR = uneSeance({ id: "s-2", intitule: "Journée 2", debut: "2099-06-01T07:30:00+00:00" });
  const SIGNEE = uneSeance({
    id: "s-3",
    intitule: "Journée 0",
    debut: "2020-11-03T08:00:00+00:00",
    signee_par_la_formatrice_le: "2020-11-03T12:00:00+00:00",
    emargements: [SIGNATURE_D_EVA, { ...SIGNATURE_D_EVA, id: "em-2", eleve_id: "e-3", nom: "Léa Roux", mode: "papier", nom_signe: "L. Roux" }],
  });
  const ANNULEE = uneSeance({ id: "s-4", intitule: "Journée annulée", annulee_le: "2020-11-09T10:00:00+00:00" });

  it("repliée par défaut ; ouverte, elle liste chaque séance avec son état et ses signatures", async () => {
    let lectures = 0;
    servirLesSeances(() => {
      lectures += 1;
      return HttpResponse.json({ seances: [SIGNEE, uneSeance(), ANNULEE, A_VENIR] });
    });
    await ouvrirLaFormation();
    await pause();
    expect(lectures).toBe(0);

    await deplierLesSeances();
    expect(lectures).toBe(1);

    const passee = seance("Journée 1");
    expect(passee.etat).toBe("À signer");
    // À l'heure de Paris, quel que soit le fuseau du poste.
    expect(passee.texte).toContain("10 novembre 2020 à 09:00");
    expect(passee.texte).toContain("3 h 30");
    expect(passee.texte).toContain("Salle Colbert, Lille");
    expect(passee.texte).toContain("Evangéline Dupont");
    expect(passee.texte).toContain("Aucune signature d'élève");

    const signee = seance("Journée 0");
    expect(signee.etat).toBe("Signée par la formatrice");
    expect(signee.texte).toContain("2 signatures d'élèves");
    expect(signee.texte).toContain("Signée par la formatrice le 3 novembre 2020 à 13:00");
    // Chaque signature : qui, quand, comment — et le nom signé s'il diffère.
    expect(signee.texte).toContain("Eva Martin · signé le 10 novembre 2020 à 09:05, en ligne");
    expect(signee.texte).toContain("Léa Roux · signé le 10 novembre 2020 à 09:05, sur papier, sous le nom « L. Roux »");
    // Signée : elle ne se modifie plus, et ne se signe pas deux fois.
    expect(within(signee.element).queryByRole("button", { name: /^Modifier/ })).toBeNull();
    expect(within(signee.element).queryByRole("button", { name: /en tant que formatrice/ })).toBeNull();

    const annulee = seance("Journée annulée");
    expect(annulee.etat).toBe("Annulée");
    expect(within(annulee.element).getByRole("button", { name: "Rétablir la séance “Journée annulée”" })).toBeInTheDocument();
    expect(within(annulee.element).queryByRole("button", { name: /signature papier/ })).toBeNull();

    const aVenir = seance("Journée 2");
    expect(aVenir.etat).toBe("À venir");
    expect(aVenir.texte).toContain("Les signatures s'ouvriront au début de la séance.");
    expect(within(aVenir.element).queryByRole("button", { name: /Signer/ })).toBeNull();
    expect(within(aVenir.element).getByRole("button", { name: "Modifier la séance “Journée 2”" })).toBeInTheDocument();

    // La règle est écrite, en une phrase.
    expect(carte("Séances en présentiel")).toHaveTextContent(
      /Une séance qui porte une signature — la vôtre ou celle d'un élève — ne se modifie plus/,
    );
    // Rien ne s'efface ici non plus.
    expect(carte("Séances en présentiel").textContent ?? "").not.toMatch(/supprim/i);
  });

  it("liste reçue et vide : dite ; une panne : dite comme une panne, jamais « Aucune séance »", async () => {
    servirLesSeances(seances());
    await ouvrirLaFormation();
    await deplierLesSeances();
    expect(within(carte("Séances en présentiel")).getByText("Aucune séance en présentiel")).toBeInTheDocument();
    cleanup();

    servirLesSeances(() => new HttpResponse("panne", { status: 500 }));
    await ouvrirLaFormation();
    await deplierLesSeances();
    expect(
      await within(carte("Séances en présentiel")).findByText(/Impossible de charger les séances/),
    ).toBeInTheDocument();
    expect(within(carte("Séances en présentiel")).queryByText(/Aucune séance/)).toBeNull();
    // Sans la liste, on ne propose pas d'en ajouter une à l'aveugle.
    expect(within(carte("Séances en présentiel")).queryByRole("button", { name: "Ajouter une séance" })).toBeNull();
  });

  it("créer une séance : les cinq champs partent, et la séance rendue rejoint la liste à son rang", async () => {
    servirLesSeances(seances(uneSeance()));
    const envois = ecouter("f-1/seances/", () =>
      HttpResponse.json({ seance: A_VENIR, refuses: [] }, { status: 201 }),
    );
    await ouvrirLaFormation();
    await deplierLesSeances();

    fireEvent.click(within(carte("Séances en présentiel")).getByRole("button", { name: "Ajouter une séance" }));
    const fenetre = screen.getByRole("dialog", { name: "Ajouter une séance en présentiel" });
    const debut = within(fenetre).getByLabelText("Date et heure de début");
    expect(debut).toHaveAttribute("type", "datetime-local");
    expect(aideContre(debut)).toMatch(/heure de Paris/);
    saisir(within(fenetre).getByLabelText("Intitulé de la séance"), "Journée 2");
    saisir(debut, "2099-06-01T09:30");
    saisir(within(fenetre).getByLabelText("Durée, en minutes"), "210");
    saisir(within(fenetre).getByLabelText("Lieu"), "Salle Colbert, Lille");
    saisir(within(fenetre).getByLabelText("Nom de la formatrice"), "Evangéline Dupont");
    fireEvent.click(within(fenetre).getByRole("button", { name: "Ajouter la séance" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(envois).toEqual([
      {
        intitule: "Journée 2",
        debut: "2099-06-01T09:30",
        duree_minutes: "210",
        lieu: "Salle Colbert, Lille",
        nom_de_la_formatrice: "Evangéline Dupont",
      },
    ]);
    const titres = within(carte("Séances en présentiel"))
      .getAllByRole("heading", { level: 3 })
      .map((titre) => titre.textContent);
    expect(titres).toEqual(["Journée 1", "Journée 2"]);
    expect(within(carte("Séances en présentiel")).getByRole("status")).toHaveTextContent(
      /La séance « Journée 2 » est ajoutée/,
    );
  });

  for (const [code, champ, libelle, phrase] of [
    ["debut_illisible", "debut", "Date et heure de début", "Cette date est illisible."],
    ["debut_hors_bornes", "debut", "Date et heure de début", "Cette date est trop lointaine."],
    ["intitule_manquant", "intitule", "Intitulé de la séance", "Donnez un intitulé à la séance."],
    ["duree_manquante", "duree_minutes", "Durée, en minutes", "Indiquez la durée de la séance."],
  ] as const) {
    it(`création refusée (400 \`${code}\`) : la phrase du serveur CONTRE le champ, la saisie reste, rien n'est ajouté`, async () => {
      servirLesSeances(seances());
      ecouter("f-1/seances/", () => refus(phrase, code, champ));
      await ouvrirLaFormation();
      await deplierLesSeances();

      fireEvent.click(within(carte("Séances en présentiel")).getByRole("button", { name: "Ajouter une séance" }));
      const fenetre = screen.getByRole("dialog");
      saisir(within(fenetre).getByLabelText("Lieu"), "Salle Colbert");
      fireEvent.click(within(fenetre).getByRole("button", { name: "Ajouter la séance" }));

      const vise = within(fenetre).getByLabelText(libelle);
      await waitFor(() => expect(erreurContre(vise)).toBe(phrase));
      expect(vise).toHaveFocus();
      expect(within(fenetre).getByLabelText("Lieu")).toHaveValue("Salle Colbert");
      expect(within(carte("Séances en présentiel")).queryAllByRole("heading", { level: 3 })).toEqual([]);
    });
  }

  it("modifier une séance : seul le champ changé part ; refusée car signée (409), la phrase du serveur s'affiche", async () => {
    servirLesSeances(seances(uneSeance()));
    const FIGEE =
      "Cette séance porte déjà une signature : son intitulé, sa date, sa durée, son lieu et le nom de la formatrice ne se modifient plus. Vous pouvez l'annuler et en créer une autre.";
    const envois = ecouter("seances/s-1/", () => refus(FIGEE, "seance_signee", undefined, 409));
    await ouvrirLaFormation();
    await deplierLesSeances();

    fireEvent.click(screen.getByRole("button", { name: "Modifier la séance “Journée 1”" }));
    const fenetre = screen.getByRole("dialog", { name: "Modifier la séance" });
    // Le début se relit à l'heure de Paris, telle qu'elle a été saisie.
    expect(within(fenetre).getByLabelText("Date et heure de début")).toHaveValue("2020-11-10T09:00");
    saisir(within(fenetre).getByLabelText("Lieu"), "Salle Vauban");
    fireEvent.click(within(fenetre).getByRole("button", { name: "Enregistrer la séance" }));

    expect(await within(fenetre).findByRole("alert")).toHaveTextContent(FIGEE);
    expect(envois).toEqual([{ lieu: "Salle Vauban" }]);
    expect(within(fenetre).getByLabelText("Lieu")).toHaveValue("Salle Vauban");
  });

  it("annuler puis rétablir : `annulee` vrai puis faux, et l'état affiché est celui que le serveur rend", async () => {
    servirLesSeances(seances(uneSeance()));
    const envois = ecouter("seances/s-1/", (corps) =>
      HttpResponse.json({
        seance: uneSeance({
          annulee_le: (corps as { annulee: boolean }).annulee ? "2020-11-09T10:00:00+00:00" : null,
        }),
        refuses: [],
      }),
    );
    await ouvrirLaFormation();
    await deplierLesSeances();

    fireEvent.click(screen.getByRole("button", { name: "Annuler la séance “Journée 1”" }));
    await waitFor(() => expect(seance("Journée 1").etat).toBe("Annulée"));
    expect(envois).toEqual([{ annulee: true }]);
    expect(within(carte("Séances en présentiel")).getByRole("status")).toHaveTextContent(
      /La séance « Journée 1 » est annulée\. Rien n'est effacé/,
    );
    // Le bouton cliqué n'est plus là : le focus va au titre de la séance.
    await waitFor(() =>
      expect(within(carte("Séances en présentiel")).getByRole("heading", { level: 3, name: "Journée 1" })).toHaveFocus(),
    );

    fireEvent.click(screen.getByRole("button", { name: "Rétablir la séance “Journée 1”" }));
    await waitFor(() => expect(seance("Journée 1").etat).toBe("À signer"));
    expect(envois).toEqual([{ annulee: true }, { annulee: false }]);
  });

  it("une réponse qui ne montre pas l'annulation n'est pas annoncée comme une annulation", async () => {
    servirLesSeances(seances(uneSeance()));
    ecouter("seances/s-1/", () => HttpResponse.json({ seance: uneSeance(), refuses: [] }));
    await ouvrirLaFormation();
    await deplierLesSeances();

    fireEvent.click(screen.getByRole("button", { name: "Annuler la séance “Journée 1”" }));

    expect(await within(seance("Journée 1").element).findByRole("alert")).toHaveTextContent(
      /n'apparaît pas dans la réponse du serveur/,
    );
    expect(within(carte("Séances en présentiel")).getByRole("status")).toBeEmptyDOMElement();
    expect(seance("Journée 1").etat).toBe("À signer");
  });

  it("signer en tant que formatrice : une confirmation d'abord, puis `signer: true`, puis l'état rendu", async () => {
    servirLesSeances(seances(uneSeance()));
    const envois = ecouter("seances/s-1/", () =>
      HttpResponse.json({
        seance: uneSeance({ signee_par_la_formatrice_le: "2020-11-10T12:00:00+00:00" }),
        refuses: [],
      }),
    );
    await ouvrirLaFormation();
    await deplierLesSeances();

    fireEvent.click(screen.getByRole("button", { name: "Signer la séance “Journée 1” en tant que formatrice" }));

    // Rien n'est parti : une signature ne se retire pas, on demande d'abord.
    const question = screen.getByRole("alertdialog", { name: /Signer « Journée 1 » au nom de Evangéline Dupont/ });
    expect(question).toHaveAccessibleDescription(/Une signature ne se retire\s+pas/);
    await pause();
    expect(envois).toEqual([]);

    fireEvent.click(within(question).getByRole("button", { name: "Oui, signer" }));

    await waitFor(() => expect(seance("Journée 1").etat).toBe("Signée par la formatrice"));
    expect(envois).toEqual([{ signer: true }]);
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(seance("Journée 1").texte).toContain("Signée par la formatrice le 10 novembre 2020 à 13:00");
    // Signée : plus de « Modifier ».
    expect(within(seance("Journée 1").element).queryByRole("button", { name: /^Modifier/ })).toBeNull();
  });

  it("contre-épreuve : « Ne pas signer » n'envoie rien", async () => {
    servirLesSeances(seances(uneSeance()));
    const envois = ecouter("seances/s-1/", () => HttpResponse.json({ seance: uneSeance(), refuses: [] }));
    await ouvrirLaFormation();
    await deplierLesSeances();

    fireEvent.click(screen.getByRole("button", { name: "Signer la séance “Journée 1” en tant que formatrice" }));
    fireEvent.click(screen.getByRole("button", { name: "Ne pas signer" }));

    expect(screen.queryByRole("alertdialog")).toBeNull();
    await pause();
    expect(envois).toEqual([]);
    expect(seance("Journée 1").etat).toBe("À signer");
  });

  for (const [code, phrase] of [
    [
      "formatrice_inconnue",
      "Indiquez le nom de la formatrice avant de signer la séance : une signature sans nom ne prouve rien.",
    ],
    ["seance_pas_commencee", "Cette séance n'a pas encore commencé."],
    ["seance_annulee", "Cette séance est annulée."],
  ] as const) {
    it(`signature refusée (409 \`${code}\`) : la phrase du serveur contre la séance, et l'état ne change pas`, async () => {
      servirLesSeances(seances(uneSeance({ nom_de_la_formatrice: "" })));
      ecouter("seances/s-1/", () => refus(phrase, code, undefined, 409));
      await ouvrirLaFormation();
      await deplierLesSeances();

      fireEvent.click(screen.getByRole("button", { name: "Signer la séance “Journée 1” en tant que formatrice" }));
      fireEvent.click(screen.getByRole("button", { name: "Oui, signer" }));

      expect(await within(seance("Journée 1").element).findByRole("alert")).toHaveTextContent(phrase);
      expect(seance("Journée 1").etat).toBe("À signer");
      expect(within(carte("Séances en présentiel")).getByRole("status")).toBeEmptyDOMElement();
    });
  }

  it("noter une signature papier : l'élève se choisit dans la liste, et son achat, lui et le nom signé partent", async () => {
    servirLesSeances(seances(uneSeance({ emargements: [{ ...SIGNATURE_D_EVA, eleve_id: "e-3", achat_id: "a-3", nom: "Léa Roux" }] })));
    const compte = servirLesEleves([EVA, SANS_NOM, ECHUE]);
    const envois = ecouter("seances/s-1/", () =>
      HttpResponse.json({
        seance: uneSeance({
          emargements: [{ ...SIGNATURE_D_EVA, mode: "papier", nom_signe: "Eva MARTIN" }],
        }),
        refuses: [],
      }),
    );
    await ouvrirLaFormation();
    // Le tableau des élèves est à l'écran : il devra suivre.
    await deplierLesEleves();
    await deplierLesSeances();

    fireEvent.click(screen.getByRole("button", { name: "Noter une signature papier pour la séance “Journée 1”" }));
    const cadre = screen.getByRole("group", { name: /Noter une signature papier — « Journée 1 »/ });
    const choix = await within(cadre).findByLabelText("Élève");
    // Ni la personne sans compte d'élève, ni celle qui a déjà signé.
    expect(within(choix).getAllByRole("option").map((option) => option.textContent)).toEqual([
      "Choisir un élève…",
      "Eva Martin — Cabinet Eva",
    ]);

    // Sans élève choisi : aucun envoi, et le champ le dit.
    fireEvent.click(within(cadre).getByRole("button", { name: "Enregistrer la signature" }));
    expect(erreurContre(choix)).toMatch(/Choisissez l'élève/);
    await pause();
    expect(envois).toEqual([]);

    saisir(choix, "a-1:e-1");
    // Le nom de la fiche est proposé, et se corrige.
    const nom = within(cadre).getByLabelText("Nom signé sur la feuille");
    expect(nom).toHaveValue("Eva Martin");
    saisir(nom, "Eva MARTIN");
    await pause();
    const luesAvant = compte.lectures;
    fireEvent.click(within(cadre).getByRole("button", { name: "Enregistrer la signature" }));

    await waitFor(() => expect(screen.queryByRole("group", { name: /signature papier/ })).toBeNull());
    expect(envois).toEqual([
      { emargement_papier: { achat_id: "a-1", eleve_id: "e-1", nom: "Eva MARTIN" } },
    ]);
    expect(seance("Journée 1").texte).toContain("1 signature d'élève");
    expect(seance("Journée 1").texte).toContain("sur papier, sous le nom « Eva MARTIN »");
    expect(within(carte("Séances en présentiel")).getByRole("status")).toHaveTextContent(
      /La signature papier de « Eva Martin » est notée/,
    );
    // Le temps de présentiel signé a changé : le tableau des élèves est relu.
    await waitFor(() => expect(compte.lectures).toBe(luesAvant + 1));
  });

  for (const [code, statut, phrase] of [
    ["deja_signe", 409, "Cet élève a déjà signé cette séance."],
    ["eleve_inconnu", 404, "Cet élève n'est pas inscrit à cette formation."],
    ["nom_manquant", 400, "Écrivez le nom signé : deux signes au moins."],
    ["nom_illisible", 400, "Ce nom est illisible."],
  ] as const) {
    it(`signature papier refusée (${statut} \`${code}\`) : la phrase du serveur s'affiche, le cadre et la saisie restent`, async () => {
      servirLesSeances(seances(uneSeance()));
      servirLesEleves([EVA]);
      ecouter("seances/s-1/", () => refus(phrase, code, undefined, statut));
      await ouvrirLaFormation();
      await deplierLesSeances();

      fireEvent.click(screen.getByRole("button", { name: "Noter une signature papier pour la séance “Journée 1”" }));
      const cadre = screen.getByRole("group", { name: /signature papier/ });
      saisir(await within(cadre).findByLabelText("Élève"), "a-1:e-1");
      fireEvent.click(within(cadre).getByRole("button", { name: "Enregistrer la signature" }));

      expect(await within(seance("Journée 1").element).findByRole("alert")).toHaveTextContent(phrase);
      expect(screen.getByRole("group", { name: /signature papier/ })).toBeInTheDocument();
      expect(seance("Journée 1").texte).toContain("Aucune signature d'élève");
    });
  }
});

// ── 6. La feuille d'émargement ──────────────────────────────────────────────

describe("la feuille d'émargement", () => {
  const FEUILLE = {
    formation: { id: "f-1", titre: "Créer son entreprise de A à Z" },
    seance: {
      id: "s-1",
      intitule: "Journée 1",
      debut: "2020-11-10T08:00:00+00:00",
      duree_minutes: 210,
      lieu: "Salle Colbert, Lille",
      annulee_le: null,
    },
    formatrice: { nom: "Evangéline Dupont", signee_le: "2020-11-10T12:00:00+00:00" },
    lignes: [
      {
        achat_id: "a-1",
        eleve_id: "e-1",
        nom: "Eva Martin",
        organisation: "Cabinet Eva",
        acces: "ouvert",
        signature: { signe_le: "2020-11-10T08:05:00+00:00", mode: "en_ligne", nom_signe: "Eva Martin" },
      },
      {
        achat_id: "a-3",
        eleve_id: "e-3",
        nom: "Léa Roux",
        organisation: "Studio Roux",
        acces: "ouvert",
        signature: { signe_le: "2020-11-10T15:00:00+00:00", mode: "papier", nom_signe: "L. Roux" },
      },
      { achat_id: "a-2", eleve_id: "e-2", nom: "Nora Petit", organisation: "Atelier Nord", acces: "ouvert", signature: null },
    ],
  };

  async function ouvrirLaFeuille(reponse: Reponse = () => HttpResponse.json({ feuille: FEUILLE })) {
    servirLesSeances(seances(uneSeance()));
    server.use(http.get(`${DASH}/formations/seances/s-1/feuille/`, () => reponse()));
    await ouvrirLaFormation();
    await deplierLesSeances();
    const bouton = screen.getByRole("button", { name: "Feuille d'émargement de la séance “Journée 1”" });
    // jsdom ne pose pas le focus au clic, un navigateur si.
    bouton.focus();
    fireEvent.click(bouton);
    return { bouton, fenetre: screen.getByRole("dialog", { name: "Feuille d'émargement" }) };
  }

  it("porte la formation, la séance, la formatrice et sa signature, et une ligne par élève — signée, ou à signer à la main", async () => {
    const { fenetre } = await ouvrirLaFeuille();

    const tableau = await within(fenetre).findByRole("table", { name: "Signatures des élèves" });
    const texte = (fenetre.textContent ?? "").replace(/\s/g, " ");
    expect(texte).toContain("Créer son entreprise de A à Z");
    expect(within(fenetre).getByRole("heading", { level: 3, name: "Journée 1" })).toBeInTheDocument();
    expect(texte).toContain("10 novembre 2020 à 09:00");
    expect(texte).toContain("3 h 30");
    expect(texte).toContain("Salle Colbert, Lille");
    expect(texte).toContain("Evangéline Dupont");
    expect(texte).toContain("Signée le 10 novembre 2020 à 13:00");

    expect(within(tableau).getAllByRole("columnheader").map((entete) => entete.textContent)).toEqual([
      "Nom",
      "Organisation",
      "Signature",
    ]);
    const lignes = within(tableau).getAllByRole("row").slice(1);
    expect(lignes).toHaveLength(3);
    const lu = (rang: number) => (lignes[rang].textContent ?? "").replace(/\s/g, " ");
    expect(lu(0)).toContain("Eva Martin");
    expect(lu(0)).toContain("Cabinet Eva");
    expect(lu(0)).toContain("Signé le 10 novembre 2020 à 09:05, en ligne");
    expect(lu(1)).toContain("L. Roux");
    expect(lu(1)).toContain("Signé le 10 novembre 2020 à 16:00, sur papier");
    // Pas de signature : une case vide, de la hauteur d'une signature.
    expect(lu(2)).toContain("Nora Petit");
    expect(lu(2)).not.toContain("Signé le");
    expect(lignes[2].querySelector(".frm-feuille-case")).not.toBeNull();
    expect(lignes[0].querySelector(".frm-feuille-case")).toBeNull();
  });

  it("sans signature de la formatrice : une case vide à sa place ; une séance annulée le dit", async () => {
    const { fenetre } = await ouvrirLaFeuille(() =>
      HttpResponse.json({
        feuille: {
          ...FEUILLE,
          seance: { ...FEUILLE.seance, annulee_le: "2020-11-09T10:00:00+00:00" },
          formatrice: { nom: "Evangéline Dupont", signee_le: null },
        },
      }),
    );

    await within(fenetre).findByRole("table");
    expect(fenetre.querySelector(".frm-feuille-formatrice .frm-feuille-case")).not.toBeNull();
    expect(fenetre.textContent ?? "").not.toContain("Signée le");
    expect((fenetre.textContent ?? "").replace(/\s/g, " ")).toContain("Séance annulée le 9 novembre 2020 à 11:00");
  });

  it("« Imprimer » lance l'impression du navigateur ; fermée, la feuille rend le focus et libère la page", async () => {
    const imprimer = vi.fn();
    vi.stubGlobal("print", imprimer);
    const { bouton, fenetre } = await ouvrirLaFeuille();

    // Tant que la feuille n'est pas là, il n'y a rien à imprimer.
    await within(fenetre).findByRole("table");
    // Posée directement sous `body`, qui le signale : c'est ce que la feuille
    // de style d'impression attend.
    expect(fenetre.parentElement).toBe(document.body);
    expect(fenetre).toHaveClass("frm-feuille-fenetre");
    expect(document.body).toHaveClass("frm-impression");

    fireEvent.click(within(fenetre).getByRole("button", { name: "Imprimer" }));
    expect(imprimer).toHaveBeenCalledTimes(1);

    fireEvent.click(within(fenetre).getByRole("button", { name: "Fermer" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.body).not.toHaveClass("frm-impression");
    expect(bouton).toHaveFocus();
    vi.unstubAllGlobals();
  });

  it("une panne se dit, et « Imprimer » reste au repos : on n'imprime pas une feuille vide", async () => {
    const { fenetre } = await ouvrirLaFeuille(() => new HttpResponse("panne", { status: 500 }));

    expect(await within(fenetre).findByText(/Impossible de charger la feuille/)).toBeInTheDocument();
    expect(within(fenetre).queryByRole("table")).toBeNull();
    expect(within(fenetre).getByRole("button", { name: "Imprimer" })).toBeDisabled();
  });

  it("la feuille de style d'impression ne garde que la feuille", () => {
    const css = readFileSync(FEUILLE_DE_STYLE, "utf-8").replace(/\r\n/g, "\n");
    const impression = css.slice(css.indexOf("@media print"));
    expect(css).toContain("@media print");
    // Tout autre enfant de `body` est écarté…
    expect(impression).toMatch(
      /body\.frm-impression > :not\(\.frm-feuille-fenetre\) \{\s*display: none;/,
    );
    // … les boutons de la fenêtre aussi…
    expect(impression).toMatch(/\.frm-feuille-fenetre \.frm-feuille-gestes \{\s*display: none;/);
    // … et la fenêtre quitte son cadre : pleine page, sans hauteur bornée.
    expect(impression).toMatch(/body\.frm-impression > \.frm-feuille-fenetre \{[^}]*position: static;/);
    expect(impression).toMatch(/body\.frm-impression > \.frm-feuille-fenetre \{[^}]*max-height: none;/);
  });
});

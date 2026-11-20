/** L'écran des formations : la gérante crée, écrit, ordonne, retire, publie.
 *
 * Les modules des formations vivaient dans un outil externe et leurs prix dans
 * le code des pages. L'écran `admin/pages/Formations.tsx` est le chemin par
 * lequel la gérante les tient elle-même, et le serveur
 * (`dashboard/formations.py`, `tests/test_formations.py`) fixe le contrat que
 * ces tests rejouent du côté de l'écran :
 *
 * 1. la liste montre ce que l'API rend — et compte les modules et les leçons
 *    PRÉSENTS, pas les retirés ;
 * 2. une panne se dit, et n'affiche aucun chiffre ; une liste vide REÇUE
 *    affiche l'état vide et de vrais zéros ;
 * 3. créer une formation envoie le titre, et l'écran montre la fiche rendue —
 *    sans relire la liste ;
 * 4. un champ écarté (`refuses`) est montré CONTRE son champ, la saisie reste,
 *    et seuls les champs modifiés sont partis ;
 * 5. une erreur de règle (`adresse_video_manquante`) est montrée contre le
 *    champ de l'adresse ; une coupure réseau se dit en bandeau, sans perdre
 *    la saisie ; la fenêtre rend le focus au bouton qui l'a ouverte ;
 * 6. retirer une leçon envoie `{"retire": true}` et la range sous
 *    « Retirés » ; rétablir envoie `false` ;
 * 7. monter un module envoie à `/ordre/` la liste exacte des modules PRÉSENTS
 *    dans le nouvel ordre, et annonce la nouvelle place ;
 * 8. mettre en ligne une formation incomplète montre ce qui manque, sans
 *    appeler ; le refus 409 du serveur s'affiche tel quel ; mettre hors ligne
 *    passe par une confirmation ;
 * 9. rien ne s'efface : aucun bouton « Supprimer », aucun bouton rouge, et
 *    aucun mot de technicien à l'écran ;
 * 10. la fiche dit vrai : la description n'est pas encore affichée sur le
 *     site ; aucun lien d'achat, ni montré ni envoyé ; l'aide de l'image et
 *     son `accept` nomment les mêmes formats ; une image part en multipart ;
 *     une écriture laisse intactes les autres formations ;
 * 11. les écritures d'une même formation arrivent au serveur l'une APRÈS
 *     l'autre ; hors connexion, l'envoi échoue tout de suite, le dit, et rend
 *     la main ;
 * 12. la fenêtre, par son chemin NATIF (`showModal`, `cancel`, `close`) :
 *     ouverture, Échap, fermeture refusée pendant un envoi, focus rendu, et
 *     pas de double fermeture en mode strict ;
 * 13. un refus qui dit l'écran périmé (ordre non reconnu, élément introuvable)
 *     fait relire la liste ;
 * 14. un module ajouté dont un champ est écarté se MODIFIE au second envoi ;
 * 15. le nombre d'inscrits que le serveur rend se dit — et rien quand il n'en
 *     dit rien ;
 * 16. la carte « Élèves » (l'ancienne « Inscrits ») : repliée, lue à
 *     l'ouverture ; chargement, liste vide et panne se distinguent ; un accès
 *     se retire après une confirmation qui demande un motif, et se rétablit ;
 *     l'état affiché est celui que le serveur rend. Le suivi lui-même est
 *     dans `le-suivi-des-eleves.test.tsx`.
 *
 * Chaque détecteur a sa contre-épreuve (règle 6).
 *
 * jsdom n'a pas `showModal()` : dans les blocs 1 à 11, la fenêtre s'ouvre par
 * le repli de `Fenetre` (l'attribut `open`). Le bloc 12 pose une doublure de
 * `showModal` / `close` pour jouer le chemin natif. Le mode modal lui-même —
 * le voile, l'inertie de la page — ne se voit que dans un navigateur.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique. Les gestionnaires MSW visent
 * `window.location.origin` (jsdom : http://localhost:3000).
 */
import React from "react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { onlineManager, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { FormationAdmin, LeconAdmin, ModuleAdmin } from "../admin/api";
import { FormationsAdmin } from "../admin/pages/Formations";
import { server } from "./server";

const DASH = `${window.location.origin}/api/dashboard`;
const PAGES = join(process.cwd(), "src", "admin", "pages");

// ── Ce que le serveur rend ──────────────────────────────────────────────────

function uneLecon(surcharges: Partial<LeconAdmin> = {}): LeconAdmin {
  return {
    id: "l-1",
    rang: 0,
    titre: "Choisir son statut",
    nature: "video",
    adresse_video: "https://vimeo.com/123456789",
    duree_minutes: 12,
    texte: "",
    fichier: "",
    fichier_nom: "",
    en_apercu_libre: false,
    retire: false,
    retire_le: "",
    ...surcharges,
  };
}

function unModule(surcharges: Partial<ModuleAdmin> = {}): ModuleAdmin {
  return {
    id: "m-1",
    rang: 0,
    titre: "Le statut",
    description: "",
    retire: false,
    retire_le: "",
    lecons: [],
    ...surcharges,
  };
}

function uneFormation(surcharges: Partial<FormationAdmin> = {}): FormationAdmin {
  return {
    id: "f-1",
    slug: "creer-son-entreprise",
    titre: "Créer son entreprise de A à Z",
    sous_titre: "De l'idée au premier client",
    accroche: "Dix-huit heures pour se lancer.",
    description: "Présentation longue.",
    prix_cents: 149_000,
    devise: "EUR",
    duree_heures: 18,
    heures_de_coaching: 2,
    lien_d_achat: "https://www.evkha.fr/paiement-formationsociete",
    image: "",
    en_ligne: true,
    rang: 0,
    publiable: true,
    manque: [],
    cree_le: "2026-11-19T09:00:00+00:00",
    modifie_le: "2026-11-19T09:00:00+00:00",
    nombre_de_modules: 0,
    modules: [],
    ...surcharges,
  };
}

const STATUT = uneLecon();
const REDIGER = uneLecon({
  id: "l-2",
  rang: 1,
  titre: "Rédiger ses statuts",
  nature: "texte",
  adresse_video: "",
  texte: "Le contenu rédigé.",
  duree_minutes: 0,
});
const LECON_RETIREE = uneLecon({
  id: "l-9",
  titre: "Ancienne leçon",
  retire: true,
  retire_le: "2026-11-01T10:00:00+00:00",
});

/** En ligne, complète : deux modules présents, deux leçons présentes — et un
 *  module et une leçon RETIRÉS, que les chiffres ne doivent pas compter. */
const SOCIETE = uneFormation({
  nombre_de_modules: 2,
  modules: [
    unModule({ lecons: [STATUT, REDIGER, LECON_RETIREE] }),
    unModule({ id: "m-2", rang: 1, titre: "Le financement" }),
    unModule({
      id: "m-9",
      rang: 0,
      titre: "Ancien module",
      retire: true,
      retire_le: "2026-11-01T10:00:00+00:00",
      lecons: [uneLecon({ id: "l-8", titre: "Leçon du module retiré" })],
    }),
  ],
});

/** Hors ligne, sans prix : le serveur dit ce qui manque. */
const POP = uneFormation({
  id: "f-2",
  slug: "methode-pop",
  titre: "Méthode P.O.P",
  sous_titre: "",
  accroche: "",
  description: "",
  prix_cents: 0,
  duree_heures: 0,
  heures_de_coaching: 0,
  lien_d_achat: "",
  en_ligne: false,
  rang: 1,
  publiable: false,
  manque: ["un prix"],
});

// ── Outils ──────────────────────────────────────────────────────────────────

/** Monte l'écran. `strict` : sous le mode strict de React, qui monte, démonte
 *  et remonte chaque composant — c'est là que la fenêtre se fermait deux fois. */
function rendre({ strict = false }: { strict?: boolean } = {}): QueryClient {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const arbre = (
    <QueryClientProvider client={client}>
      <FormationsAdmin />
    </QueryClientProvider>
  );
  render(strict ? <React.StrictMode>{arbre}</React.StrictMode> : arbre);
  return client;
}

/** Sert la liste, et compte combien de fois elle a été lue. */
function servirLaListe(formations: FormationAdmin[]): { lectures: number } {
  const compte = { lectures: 0 };
  server.use(
    http.get(`${DASH}/formations/`, () => {
      compte.lectures += 1;
      return HttpResponse.json({ formations });
    }),
  );
  return compte;
}

/** Sert une liste à la première lecture, une autre ensuite : ce qu'un autre
 *  onglet a changé entre-temps. */
function servirPuis(dAbord: FormationAdmin[], ensuite: FormationAdmin[]): { lectures: number } {
  const compte = { lectures: 0 };
  server.use(
    http.get(`${DASH}/formations/`, () => {
      compte.lectures += 1;
      return HttpResponse.json({ formations: compte.lectures === 1 ? dAbord : ensuite });
    }),
  );
  return compte;
}

/** Une écriture RETENUE : le serveur a reçu le corps, et ne répond que
 *  lorsqu'on ouvre la porte. `ensemble` dit combien d'envois ont été en vol
 *  en même temps, au plus. */
function retenir(chemin: string, repondre: (corps: unknown) => Response) {
  const suivi = { recus: [] as unknown[], portes: [] as (() => void)[], ensemble: 0 };
  let enVol = 0;
  server.use(
    http.post(`${DASH}/formations/${chemin}`, async ({ request }) => {
      const corps: unknown = await request.json();
      suivi.recus.push(corps);
      enVol += 1;
      suivi.ensemble = Math.max(suivi.ensemble, enVol);
      await new Promise<void>((ouvrirLaPorte) => suivi.portes.push(ouvrirLaPorte));
      enVol -= 1;
      return repondre(corps);
    }),
  );
  return suivi;
}

function pause(ms = 50): Promise<void> {
  return new Promise((resoudre) => setTimeout(resoudre, ms));
}

/** L'aide RELIÉE à un champ par `aria-describedby`. */
function aideContre(champ: HTMLElement): string {
  return (champ.getAttribute("aria-describedby") ?? "")
    .split(" ")
    .filter(Boolean)
    .map((id) => document.getElementById(id))
    .filter((element) => element?.classList.contains("champ-aide"))
    .map((element) => element?.textContent ?? "")
    .join(" ");
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

function ecriture(formation: FormationAdmin, plus: Record<string, unknown> = {}, statut = 200) {
  return HttpResponse.json({ formation, refuses: [], ...plus }, { status: statut });
}

function refus(erreur: string, code: string, champ?: string, statut = 400) {
  return HttpResponse.json({ erreur, code, ...(champ ? { champ } : {}) }, { status: statut });
}

/** La valeur d'un chiffre clé, ou `null` s'il n'est pas affiché. Par la carte
 *  et non par le texte : « En ligne » et « Modules » se lisent aussi sur les
 *  cartes des formations. */
function chiffre(libelle: string): string | null {
  for (const carte of document.querySelectorAll(".chiffre")) {
    if (carte.querySelector(".chiffre-libelle")?.textContent === libelle) {
      return carte.querySelector(".chiffre-valeur")?.textContent ?? null;
    }
  }
  return null;
}

/** Le message d'erreur RELIÉ à un champ par `aria-describedby`, ou une chaîne
 *  vide. Un message affiché ailleurs dans la page ne compte pas. */
function erreurContre(champ: HTMLElement): string {
  return (champ.getAttribute("aria-describedby") ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .map((id) => document.getElementById(id))
    .filter((element) => element?.classList.contains("champ-erreur"))
    .map((element) => element?.textContent ?? "")
    .join(" ");
}

async function ouvrir(titre: string) {
  fireEvent.click(await screen.findByRole("button", { name: `Ouvrir la formation “${titre}”` }));
  // La carte a quitté l'écran ; le titre est maintenant celui de la fiche.
  await screen.findByRole("button", { name: "Toutes les formations" });
  expect(screen.getByRole("heading", { level: 2, name: titre })).toBeInTheDocument();
}

function saisir(champ: HTMLElement, valeur: string) {
  fireEvent.change(champ, { target: { value: valeur } });
}

/** Les titres des modules présents, dans l'ordre de la page. */
function modulesALEcran(): string[] {
  return [...document.querySelectorAll(".frm-modules > li .frm-module-nom")].map(
    (element) => element.textContent ?? "",
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  // Un test qui coupe la connexion ne la laisse pas coupée au suivant.
  onlineManager.setOnline(true);
});

// ── 1 et 2. La liste ────────────────────────────────────────────────────────

describe("la liste des formations", () => {
  it("affiche ce que l'API rend : état, prix, durée, ce qui manque", async () => {
    servirLaListe([SOCIETE, POP]);
    rendre();

    const titre = await screen.findByRole("heading", { level: 2, name: SOCIETE.titre });
    const societe = titre.closest("li") as HTMLElement;
    expect(within(societe).getByText("En ligne")).toBeInTheDocument();
    expect(within(societe).getByText(/^1\s?490\s?€$/)).toBeInTheDocument();
    expect(within(societe).getByText(/^18\sh$/)).toBeInTheDocument();
    expect(within(societe).queryByText(/il manque/)).toBeNull();

    const pop = screen.getByRole("heading", { level: 2, name: POP.titre }).closest("li") as HTMLElement;
    expect(within(pop).getByText("Hors ligne")).toBeInTheDocument();
    expect(within(pop).getByText("À fixer")).toBeInTheDocument();
    // Ce qui manque est le texte du SERVEUR (`manque`), pas une déduction.
    expect(within(pop).getByText("Pour la mettre en ligne, il manque un prix.")).toBeInTheDocument();
  });

  it("compte les modules et les leçons PRÉSENTS, pas les retirés", async () => {
    servirLaListe([SOCIETE, POP]);
    rendre();

    await screen.findByRole("heading", { level: 2, name: SOCIETE.titre });
    expect(chiffre("Formations")).toBe("2");
    expect(chiffre("En ligne")).toBe("1");
    // Trois modules en base dont un retiré ; quatre leçons dont une retirée
    // et une dans un module retiré.
    expect(chiffre("Modules")).toBe("2");
    expect(chiffre("Leçons")).toBe("2");
  });

  it("une panne se dit, et n'affiche aucun chiffre", async () => {
    server.use(
      http.get(`${DASH}/formations/`, () => new HttpResponse("panne", { status: 500 })),
    );
    rendre();

    expect(await screen.findByText(/Impossible de charger les formations/)).toBeInTheDocument();
    expect(screen.getByText(/500/)).toBeInTheDocument();
    for (const libelle of ["Formations", "En ligne", "Modules", "Leçons"]) {
      expect(chiffre(libelle), libelle).toBeNull();
    }
    expect(document.querySelectorAll(".chiffre")).toHaveLength(0);
    expect(screen.queryByText("Aucune formation")).toBeNull();
  });

  it("contre-épreuve : une liste vide REÇUE affiche l'état vide et de vrais zéros", async () => {
    servirLaListe([]);
    rendre();

    expect(await screen.findByText("Aucune formation")).toBeInTheDocument();
    expect(chiffre("Formations")).toBe("0");
    expect(chiffre("Leçons")).toBe("0");
    expect(screen.queryByText(/Impossible de charger/)).toBeNull();
    // Et le détecteur de chiffres ne rend pas `null` à tout : il lit bien.
    expect(chiffre("Un libellé qui n'existe pas")).toBeNull();
  });
});

// ── 3. Créer ────────────────────────────────────────────────────────────────

describe("créer une formation", () => {
  it("envoie le titre, et montre la fiche rendue sans relire la liste", async () => {
    const liste = servirLaListe([SOCIETE]);
    const creee = uneFormation({
      id: "f-3",
      slug: "methode-pop",
      titre: "Méthode P.O.P",
      sous_titre: "",
      accroche: "",
      description: "",
      prix_cents: 0,
      duree_heures: 0,
      heures_de_coaching: 0,
      lien_d_achat: "",
      en_ligne: false,
      publiable: false,
      manque: ["un prix"],
    });
    const recus = ecouter("", () => ecriture(creee, {}, 201));
    rendre();

    fireEvent.click(await screen.findByRole("button", { name: "Ajouter une formation" }));
    saisir(screen.getByLabelText("Titre de la formation"), "Méthode P.O.P");
    fireEvent.click(screen.getByRole("button", { name: "Créer la formation" }));

    // La fiche de la formation créée est à l'écran, telle que rendue.
    expect(await screen.findByRole("heading", { level: 2, name: "Méthode P.O.P" })).toBeInTheDocument();
    expect(recus).toEqual([{ titre: "Méthode P.O.P" }]);
    expect(screen.getByLabelText("Titre")).toHaveValue("Méthode P.O.P");
    expect(screen.getByLabelText("Adresse publique")).toHaveValue("/formations/methode-pop");
    expect(screen.getByLabelText("Adresse publique")).toHaveAttribute("readonly");
    expect(screen.getByText(/cette adresse ne change plus/)).toBeInTheDocument();
    // Elle naît hors ligne.
    expect(screen.getByText("Hors ligne")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mettre en ligne" })).toBeInTheDocument();
    // Une seule source, la réponse : la liste n'a été lue qu'à l'arrivée.
    expect(liste.lectures).toBe(1);
  });

  it("contre-épreuve : sans titre, le refus du serveur se pose contre le champ", async () => {
    servirLaListe([SOCIETE]);
    const recus = ecouter("", () =>
      refus("Donnez un titre à la formation.", "titre_manquant", "titre"),
    );
    rendre();

    fireEvent.click(await screen.findByRole("button", { name: "Ajouter une formation" }));
    const titre = screen.getByLabelText("Titre de la formation");
    expect(erreurContre(titre)).toBe("");
    fireEvent.click(screen.getByRole("button", { name: "Créer la formation" }));

    await waitFor(() => expect(erreurContre(titre)).toBe("Donnez un titre à la formation."));
    expect(titre).toHaveAttribute("aria-invalid", "true");
    expect(recus).toEqual([{ titre: "" }]);
    // La fenêtre est restée ouverte, sur la liste.
    expect(screen.getByRole("button", { name: "Créer la formation" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Toutes les formations" })).toBeNull();
  });
});

// ── 4. La fiche ─────────────────────────────────────────────────────────────

describe("la fiche d'une formation", () => {
  it("un champ écarté par le serveur est montré contre son champ, la saisie reste", async () => {
    servirLaListe([SOCIETE]);
    const rendue = { ...SOCIETE, accroche: "Nouvelle accroche" };
    const recus = ecouter("f-1/", () =>
      HttpResponse.json({
        formation: rendue,
        refuses: [{ champ: "duree_heures", raison: "Un nombre entier est attendu." }],
      }),
    );
    rendre();
    await ouvrir(SOCIETE.titre);

    const duree = screen.getByLabelText("Durée, en heures");
    const accroche = screen.getByLabelText("Accroche");
    expect(duree).toHaveValue("18");
    saisir(duree, "12,5");
    saisir(accroche, "Nouvelle accroche");
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer la fiche" }));

    await waitFor(() => expect(erreurContre(duree)).toBe("Un nombre entier est attendu."));
    expect(duree).toHaveAttribute("aria-invalid", "true");
    // Ce qu'elle a tapé reste là, à corriger — le serveur, lui, a gardé 18.
    expect(duree).toHaveValue("12,5");
    await waitFor(() => expect(duree).toHaveFocus());
    // Seuls les champs modifiés sont partis : le prix et le titre n'ont pas
    // à être renvoyés pour être gardés.
    expect(recus).toEqual([{ accroche: "Nouvelle accroche", duree_heures: "12,5" }]);
    // Contre-épreuve : le champ accepté n'est pas accusé, et il est enregistré.
    expect(erreurContre(accroche)).toBe("");
    expect(accroche).not.toHaveAttribute("aria-invalid");
    expect(accroche).toHaveValue("Nouvelle accroche");
    expect(screen.getByText(/La fiche est enregistrée, sauf ce qui est signalé/)).toBeInTheDocument();
  });

  it("le prix part en euros (`prix_euros`), et une règle sur le prix revient contre lui", async () => {
    servirLaListe([SOCIETE]);
    const recus = ecouter("f-1/", () =>
      refus("Le prix ne peut pas être négatif.", "prix_negatif", "prix_cents"),
    );
    rendre();
    await ouvrir(SOCIETE.titre);

    const prix = screen.getByLabelText("Prix, en euros");
    expect(prix).toHaveValue("1490");
    saisir(prix, "-5");
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer la fiche" }));

    // Le serveur nomme le champ `prix_cents` : l'écran sait que c'est le sien.
    await waitFor(() => expect(erreurContre(prix)).toBe("Le prix ne peut pas être négatif."));
    expect(recus).toEqual([{ prix_euros: "-5" }]);
    expect(prix).toHaveValue("-5");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("contre-épreuve : sans modification, rien n'est envoyé", async () => {
    servirLaListe([SOCIETE]);
    const recus = ecouter("f-1/", () => ecriture(SOCIETE));
    rendre();
    await ouvrir(SOCIETE.titre);

    fireEvent.click(screen.getByRole("button", { name: "Enregistrer la fiche" }));

    expect(await screen.findByText("Aucune modification à enregistrer.")).toBeInTheDocument();
    expect(recus).toEqual([]);
  });
});

// ── 5. Une leçon, dans sa fenêtre ───────────────────────────────────────────

describe("la fenêtre d'une leçon", () => {
  const MESSAGE =
    "Une leçon vidéo a besoin de l'adresse de sa vidéo. Collez l'adresse https:// " +
    "de la vidéo, ou choisissez une autre nature.";

  it("une vidéo sans adresse : le refus du serveur est montré contre l'adresse", async () => {
    servirLaListe([SOCIETE]);
    const recus = ecouter("modules/m-1/lecons/", () =>
      refus(MESSAGE, "adresse_video_manquante", "adresse_video"),
    );
    rendre();
    await ouvrir(SOCIETE.titre);

    fireEvent.click(
      screen.getByRole("button", { name: "Ajouter une leçon au module “Le statut”" }),
    );
    const titre = screen.getByLabelText("Titre de la leçon");
    const adresse = screen.getByLabelText("Adresse de la vidéo");
    // Les natures se lisent en français et partent dans les mots du serveur.
    const nature = screen.getByLabelText("Nature de la leçon") as HTMLSelectElement;
    expect([...nature.options].map((o) => [o.textContent, o.value])).toEqual([
      ["Vidéo", "video"],
      ["Texte", "texte"],
      ["Document", "document"],
      ["Quiz", "quiz"],
    ]);
    expect(screen.getByText(/Aucune vidéo n'est stockée sur la plateforme\./)).toBeInTheDocument();
    saisir(titre, "Trouver son nom");
    fireEvent.click(screen.getByRole("button", { name: "Ajouter la leçon" }));

    await waitFor(() => expect(erreurContre(adresse)).toBe(MESSAGE));
    expect(adresse).toHaveAttribute("aria-invalid", "true");
    expect(recus).toEqual([
      { titre: "Trouver son nom", nature: "video", adresse_video: "", en_apercu_libre: false },
    ]);
    // Rien n'est perdu, la fenêtre est restée, et l'erreur n'est pas AUSSI
    // dite en bandeau ni contre le titre.
    expect(titre).toHaveValue("Trouver son nom");
    expect(erreurContre(titre)).toBe("");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("le contenu demandé suit la nature choisie", async () => {
    servirLaListe([SOCIETE]);
    rendre();
    await ouvrir(SOCIETE.titre);

    fireEvent.click(
      screen.getByRole("button", { name: "Ajouter une leçon au module “Le statut”" }),
    );
    const nature = screen.getByLabelText("Nature de la leçon");
    expect(screen.getByLabelText("Adresse de la vidéo")).toBeInTheDocument();

    fireEvent.change(nature, { target: { value: "texte" } });
    expect(screen.queryByLabelText("Adresse de la vidéo")).toBeNull();
    expect(screen.getByLabelText("Texte de la leçon")).toBeInTheDocument();

    fireEvent.change(nature, { target: { value: "document" } });
    expect(screen.queryByLabelText("Texte de la leçon")).toBeNull();
    expect(screen.getByLabelText("Document de la leçon")).toHaveAttribute("type", "file");

    expect(screen.getByLabelText("Durée, en minutes")).toBeInTheDocument();
    expect(screen.getByLabelText("Visible avant achat (aperçu libre)")).not.toBeChecked();
  });

  it("une coupure réseau se dit en bandeau, et ne perd pas la saisie", async () => {
    servirLaListe([SOCIETE]);
    server.use(http.post(`${DASH}/formations/lecons/l-1/`, () => HttpResponse.error()));
    rendre();
    await ouvrir(SOCIETE.titre);

    fireEvent.click(
      screen.getByRole("button", { name: "Modifier la leçon “Choisir son statut”" }),
    );
    const titre = screen.getByLabelText("Titre de la leçon");
    expect(titre).toHaveValue("Choisir son statut");
    saisir(titre, "Choisir son statut juridique");
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer la leçon" }));

    const bandeau = await screen.findByRole("alert");
    expect(bandeau).toHaveClass("bandeau", "bandeau-echec");
    expect(bandeau).toHaveTextContent(/Le serveur n'a pas répondu/);
    // Pas le message anglais du navigateur.
    expect(bandeau).not.toHaveTextContent(/Failed to fetch|NetworkError/i);
    expect(titre).toHaveValue("Choisir son statut juridique");
    expect(erreurContre(titre)).toBe("");
  });

  it("fermée, la fenêtre rend le focus au bouton qui l'a ouverte", async () => {
    servirLaListe([SOCIETE]);
    rendre();
    await ouvrir(SOCIETE.titre);

    const ouvreur = screen.getByRole("button", { name: "Modifier la leçon “Choisir son statut”" });
    ouvreur.focus();
    fireEvent.click(ouvreur);
    expect(screen.getByLabelText("Titre de la leçon")).toBeInTheDocument();
    // Le focus a quitté le bouton : sinon le retour ne prouverait rien.
    screen.getByLabelText("Titre de la leçon").focus();
    expect(ouvreur).not.toHaveFocus();

    fireEvent.click(screen.getByRole("button", { name: "Annuler" }));

    await waitFor(() => expect(screen.queryByLabelText("Titre de la leçon")).toBeNull());
    expect(ouvreur).toHaveFocus();
  });
});

// ── 6. Retirer, rétablir ────────────────────────────────────────────────────

describe("retirer et rétablir une leçon", () => {
  /** `SOCIETE`, la leçon « Choisir son statut » retirée ou non. Le serveur
   *  range les présentes d'abord, les retirées ensuite. */
  function avecStatut(retire: boolean): FormationAdmin {
    const statut = { ...STATUT, retire, retire_le: retire ? "2026-11-19T10:00:00+00:00" : "" };
    const premier = SOCIETE.modules[0];
    return {
      ...SOCIETE,
      modules: [
        // Retirée, elle passe après les présentes ; rétablie, elle revient
        // en FIN de module : dans les deux cas, après « Rédiger ses statuts ».
        { ...premier, lecons: [REDIGER, statut, LECON_RETIREE] },
        ...SOCIETE.modules.slice(1),
      ],
    };
  }

  /** Le groupe « Retirés » du premier module. */
  function retiresDuModule(): HTMLDetailsElement {
    const groupe = document.querySelector<HTMLDetailsElement>('[data-frm="retires-m-1"]');
    if (!groupe) throw new Error("groupe « Retirés » du module introuvable");
    return groupe;
  }

  it("retirer envoie {retire: true} et range la leçon sous « Retirés » ; rétablir envoie false", async () => {
    servirLaListe([SOCIETE]);
    const recus = ecouter("lecons/l-1/", (corps) =>
      ecriture(avecStatut((corps as { retire: boolean }).retire), { lecon_id: "l-1" }),
    );
    rendre();
    await ouvrir(SOCIETE.titre);

    // Avant : une leçon déjà retirée, sous un intitulé replié.
    expect(retiresDuModule().open).toBe(false);
    expect(within(retiresDuModule()).getByText("Retirés (1)")).toBeInTheDocument();
    expect(within(retiresDuModule()).queryByText("Choisir son statut")).toBeNull();

    fireEvent.click(
      screen.getByRole("button", { name: "Retirer la leçon “Choisir son statut”" }),
    );

    await waitFor(() =>
      expect(within(retiresDuModule()).getByText("Choisir son statut")).toBeInTheDocument(),
    );
    expect(recus).toEqual([{ retire: true }]);
    expect(within(retiresDuModule()).getByText("Retirés (2)")).toBeInTheDocument();
    // Elle n'est plus parmi les leçons en place : plus de geste pour la
    // retirer, la modifier ou la déplacer — seulement « Rétablir ».
    expect(document.querySelector(".frm-lecons")?.textContent).not.toMatch(/Choisir son statut/);
    expect(
      screen.queryByRole("button", { name: "Retirer la leçon “Choisir son statut”", hidden: true }),
    ).toBeNull();
    expect(document.querySelector(".frm-annonce")).toHaveTextContent(
      /La leçon « Choisir son statut » est retirée du module/,
    );

    // `hidden: true` : le groupe est replié, et l'on ne veut pas dépendre de
    // ce que jsdom décide du contenu d'un `<details>` fermé.
    const retablir = screen.getByRole("button", {
      name: "Rétablir la leçon “Choisir son statut”",
      hidden: true,
    });
    // Pendant un envoi, les gestes du programme ne sont pas re-cliquables :
    // on attend que le premier soit rendu.
    await waitFor(() => expect(retablir).toBeEnabled());
    fireEvent.click(retablir);

    await screen.findByRole("button", { name: "Retirer la leçon “Choisir son statut”" });
    expect(recus).toEqual([{ retire: true }, { retire: false }]);
    expect(within(retiresDuModule()).getByText("Retirés (1)")).toBeInTheDocument();
    expect(within(retiresDuModule()).queryByText("Choisir son statut")).toBeNull();
  });

  it("un module retiré se lit sous « Retirés », grisé, avec « Rétablir »", async () => {
    servirLaListe([SOCIETE]);
    const recus = ecouter("modules/m-9/", () => ecriture(SOCIETE, { module_id: "m-9" }));
    rendre();
    await ouvrir(SOCIETE.titre);

    const groupe = document.querySelector<HTMLDetailsElement>('[data-frm="retires-f-1"]');
    expect(groupe).not.toBeNull();
    expect(groupe?.open).toBe(false);
    expect(within(groupe as HTMLElement).getByText("Ancien module")).toBeInTheDocument();
    // Il n'est pas dans la liste ordonnée des modules en place.
    expect(modulesALEcran()).toEqual(["Le statut", "Le financement"]);

    fireEvent.click(
      screen.getByRole("button", { name: "Rétablir le module “Ancien module”", hidden: true }),
    );

    await waitFor(() => expect(recus).toEqual([{ retire: false }]));
  });
});

// ── 7. L'ordre ──────────────────────────────────────────────────────────────

describe("déplacer un module", () => {
  const OFFRE = unModule({ id: "m-a", rang: 0, titre: "Poser son offre" });
  const CLIENTS = unModule({ id: "m-b", rang: 1, titre: "Trouver ses clients" });
  const PRIX = unModule({ id: "m-c", rang: 2, titre: "Fixer ses prix" });
  const RETIRE = unModule({ id: "m-x", rang: 1, titre: "Module retiré", retire: true });
  const AVANT = uneFormation({ nombre_de_modules: 3, modules: [OFFRE, CLIENTS, PRIX, RETIRE] });
  const APRES = uneFormation({
    nombre_de_modules: 3,
    modules: [OFFRE, { ...PRIX, rang: 1 }, { ...CLIENTS, rang: 2 }, RETIRE],
  });

  it("monter envoie à /ordre/ la liste exacte des modules PRÉSENTS, dans le nouvel ordre", async () => {
    servirLaListe([AVANT]);
    const recus = ecouter("f-1/ordre/", () => ecriture(APRES));
    rendre();
    await ouvrir(AVANT.titre);
    expect(modulesALEcran()).toEqual(["Poser son offre", "Trouver ses clients", "Fixer ses prix"]);

    fireEvent.click(screen.getByRole("button", { name: "Monter le module “Fixer ses prix”" }));

    await waitFor(() =>
      expect(modulesALEcran()).toEqual(["Poser son offre", "Fixer ses prix", "Trouver ses clients"]),
    );
    // Les trois présents, tous, et pas le retiré : le serveur refuserait
    // sinon (`ordre_incomplet`, `ordre_etranger`).
    expect(recus).toEqual([{ modules: ["m-a", "m-c", "m-b"] }]);
    // La nouvelle place est annoncée, lue sur la fiche rendue.
    const annonce = document.querySelector(".frm-annonce") as HTMLElement;
    expect(annonce).toHaveAttribute("role", "status");
    expect(annonce).toHaveTextContent("« Fixer ses prix » est maintenant le module 2 sur 3.");
    // Et le focus est resté sur le bouton : on peut monter encore.
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Monter le module “Fixer ses prix”" })).toHaveFocus(),
    );
  });

  it("descendre envoie l'ordre inverse du même geste", async () => {
    servirLaListe([AVANT]);
    const recus = ecouter("f-1/ordre/", () => ecriture(AVANT));
    rendre();
    await ouvrir(AVANT.titre);

    fireEvent.click(screen.getByRole("button", { name: "Descendre le module “Poser son offre”" }));

    await waitFor(() => expect(recus).toEqual([{ modules: ["m-b", "m-a", "m-c"] }]));
  });

  it("contre-épreuve : en bout de liste, le bouton est au repos et n'envoie rien", async () => {
    servirLaListe([AVANT]);
    const recus = ecouter("f-1/ordre/", () => ecriture(AVANT));
    rendre();
    await ouvrir(AVANT.titre);

    const premier = screen.getByRole("button", { name: "Monter le module “Poser son offre”" });
    const dernier = screen.getByRole("button", { name: "Descendre le module “Fixer ses prix”" });
    expect(premier).toHaveAttribute("aria-disabled", "true");
    expect(dernier).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(premier);
    fireEvent.click(dernier);
    // Un bouton qui, lui, peut agir n'est pas marqué au repos.
    expect(
      screen.getByRole("button", { name: "Monter le module “Fixer ses prix”" }),
    ).not.toHaveAttribute("aria-disabled");
    // On laisse à un envoi fautif le temps d'arriver avant de conclure.
    await new Promise((resoudre) => setTimeout(resoudre, 50));
    expect(recus).toEqual([]);
  });

  it("les leçons se déplacent dans LEUR module, par la route du module", async () => {
    servirLaListe([SOCIETE]);
    const recus = ecouter("modules/m-1/ordre/", () => ecriture(SOCIETE));
    rendre();
    await ouvrir(SOCIETE.titre);

    fireEvent.click(
      screen.getByRole("button", { name: "Descendre la leçon “Choisir son statut”" }),
    );

    // Les deux leçons présentes, sans la retirée.
    await waitFor(() => expect(recus).toEqual([{ lecons: ["l-2", "l-1"] }]));
  });
});

// ── 8. En ligne, hors ligne ─────────────────────────────────────────────────

describe("mettre en ligne et hors ligne", () => {
  it("une formation incomplète : ce qui manque est expliqué AVANT tout appel", async () => {
    servirLaListe([POP]);
    const recus = ecouter("f-2/", () => ecriture({ ...POP, en_ligne: true }));
    rendre();
    await ouvrir(POP.titre);

    const bouton = screen.getByRole("button", { name: "Mettre en ligne" });
    // Dit dès l'arrivée, et relié au bouton : on le sait avant de cliquer.
    const dit = document.getElementById(bouton.getAttribute("aria-describedby") ?? "");
    expect(dit).toHaveTextContent("Pour la mettre en ligne, il manque un prix.");
    // Le bouton reste actionnable : c'est en cliquant qu'on obtient l'explication.
    expect(bouton).not.toBeDisabled();

    fireEvent.click(bouton);

    const explication = await screen.findByRole("alert");
    expect(explication).toHaveTextContent(/il lui manque un prix/);
    await new Promise((resoudre) => setTimeout(resoudre, 50));
    expect(recus).toEqual([]);
    expect(screen.getByText("Hors ligne")).toBeInTheDocument();
  });

  it("contre-épreuve : une formation complète part en ligne d'un clic", async () => {
    const prete = { ...POP, prix_cents: 85_000, publiable: true, manque: [] };
    servirLaListe([prete]);
    const recus = ecouter("f-2/", () => ecriture({ ...prete, en_ligne: true }));
    rendre();
    await ouvrir(prete.titre);

    fireEvent.click(screen.getByRole("button", { name: "Mettre en ligne" }));

    expect(await screen.findByRole("button", { name: "Mettre hors ligne" })).toBeInTheDocument();
    expect(recus).toEqual([{ en_ligne: true }]);
    expect(screen.getByText("En ligne")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("le refus 409 du serveur est affiché tel qu'il l'a écrit", async () => {
    const REFUS = "Cette formation ne peut pas être en ligne : il lui manque un prix.";
    // L'écran la croit complète ; le serveur, lui, sait qu'elle ne l'est plus.
    const crue = { ...POP, publiable: true, manque: [] };
    servirLaListe([crue]);
    const recus = ecouter("f-2/", () => refus(REFUS, "formation_incomplete", undefined, 409));
    rendre();
    await ouvrir(crue.titre);

    fireEvent.click(screen.getByRole("button", { name: "Mettre en ligne" }));

    const bandeau = await screen.findByRole("alert");
    expect(bandeau).toHaveTextContent(REFUS);
    expect(bandeau).toHaveClass("bandeau", "bandeau-echec");
    expect(recus).toEqual([{ en_ligne: true }]);
    expect(screen.getByText("Hors ligne")).toBeInTheDocument();
  });

  it("mettre HORS ligne demande une confirmation, qui dit la conséquence", async () => {
    servirLaListe([SOCIETE]);
    const recus = ecouter("f-1/", () => ecriture({ ...SOCIETE, en_ligne: false }));
    rendre();
    await ouvrir(SOCIETE.titre);

    fireEvent.click(screen.getByRole("button", { name: "Mettre hors ligne" }));

    const question = await screen.findByRole("alertdialog");
    expect(question).toHaveTextContent(`Mettre « ${SOCIETE.titre} » hors ligne ?`);
    expect(question).toHaveTextContent(/Elle disparaîtra de votre site/);
    expect(recus).toEqual([]);

    fireEvent.click(within(question).getByRole("button", { name: "Oui, la mettre hors ligne" }));

    expect(await screen.findByRole("button", { name: "Mettre en ligne" })).toBeInTheDocument();
    expect(recus).toEqual([{ en_ligne: false }]);
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });

  it("contre-épreuve : renoncer n'envoie rien", async () => {
    servirLaListe([SOCIETE]);
    const recus = ecouter("f-1/", () => ecriture({ ...SOCIETE, en_ligne: false }));
    rendre();
    await ouvrir(SOCIETE.titre);

    fireEvent.click(screen.getByRole("button", { name: "Mettre hors ligne" }));
    const question = await screen.findByRole("alertdialog");
    fireEvent.click(within(question).getByRole("button", { name: "Annuler" }));

    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    await new Promise((resoudre) => setTimeout(resoudre, 50));
    expect(recus).toEqual([]);
    expect(screen.getByText("En ligne")).toBeInTheDocument();
  });
});

// ── 9. Rien ne s'efface ─────────────────────────────────────────────────────

describe("rien ne s'efface, et l'écran parle comme la gérante", () => {
  /** Un geste d'effacement : le mot, ou le bouton rouge du langage commun. */
  const EFFACEMENT = /supprim|suppression|bouton-echec|method:\s*["']DELETE["']/i;
  /** Un mot de technicien. `\b` : « identifiant » ou « valider » n'en sont pas. */
  const JARGON = /\bslug\b|\bID\b|\bJSON\b|\bUUID\b|\bAPI\b/;

  it("aucun bouton « Supprimer », aucun bouton rouge — dans la liste comme dans la fiche", async () => {
    servirLaListe([SOCIETE, POP]);
    rendre();

    await screen.findByRole("heading", { level: 2, name: SOCIETE.titre });
    expect(document.body.textContent ?? "").not.toMatch(/supprim/i);
    expect(document.querySelector(".bouton-echec")).toBeNull();

    await ouvrir(SOCIETE.titre);
    fireEvent.click(
      screen.getByRole("button", { name: "Modifier la leçon “Choisir son statut”" }),
    );
    // Les gestes de retrait existent bien : le test ne passe pas sur un
    // écran vide.
    expect(
      screen.getAllByRole("button", { name: /^Retirer /, hidden: true }).length,
    ).toBeGreaterThanOrEqual(3);
    expect(screen.queryByRole("button", { name: /supprim/i, hidden: true })).toBeNull();
    expect(document.body.textContent ?? "").not.toMatch(/supprim/i);
    expect(document.querySelector(".bouton-echec")).toBeNull();
    for (const bouton of screen.getAllByRole("button", { name: /^Retirer /, hidden: true })) {
      expect(bouton).toHaveClass("bouton-discret");
    }
  });

  it("aucun mot de technicien à l'écran", async () => {
    servirLaListe([SOCIETE, POP]);
    rendre();

    await screen.findByRole("heading", { level: 2, name: SOCIETE.titre });
    expect(document.body.textContent ?? "").not.toMatch(JARGON);
    await ouvrir(SOCIETE.titre);
    fireEvent.click(
      screen.getByRole("button", { name: "Ajouter une leçon au module “Le statut”" }),
    );
    expect(document.body.textContent ?? "").not.toMatch(JARGON);
    expect(screen.getByLabelText("Adresse publique")).toBeInTheDocument();
  });

  it("le code de l'écran n'écrit ni le mot, ni le bouton rouge, ni la méthode", () => {
    const source = readFileSync(join(PAGES, "Formations.tsx"), "utf-8");
    expect(source.length).toBeGreaterThan(5000);
    expect(source).not.toMatch(EFFACEMENT);
  });

  it("contre-épreuve : les détecteurs voient ce qu'ils doivent voir", () => {
    // La boutique, elle, efface : le même motif l'y trouve.
    expect(readFileSync(join(PAGES, "BoutiqueAdmin.tsx"), "utf-8")).toMatch(EFFACEMENT);
    for (const faute of [
      "<button>Supprimer</button>",
      "Suppression impossible.",
      'className="bouton bouton-echec"',
      'method: "DELETE"',
    ]) {
      expect(EFFACEMENT.test(faute), faute).toBe(true);
    }
    for (const juste of ["Retirer", "Rétablir", 'className="bandeau bandeau-echec"', "Mettre hors ligne"]) {
      expect(EFFACEMENT.test(juste), juste).toBe(false);
    }

    for (const faute of ["Le slug de la formation", "ID du module", "Corps JSON illisible"]) {
      expect(JARGON.test(faute), faute).toBe(true);
    }
    for (const juste of ["Adresse publique", "Un identifiant", "Valider", "Vidéo", "Le rapide"]) {
      expect(JARGON.test(juste), juste).toBe(false);
    }

    // `erreurContre` ne lit que ce qui est RELIÉ au champ.
    const hote = document.createElement("div");
    hote.innerHTML =
      '<input id="c" aria-describedby="c-erreur c-aide">' +
      '<span class="champ-erreur" id="c-erreur">Refusé.</span>' +
      '<span class="champ-aide" id="c-aide">Une aide.</span>' +
      '<input id="d"><span class="champ-erreur" id="d-erreur">Non relié.</span>';
    document.body.append(hote);
    expect(erreurContre(hote.querySelector("#c") as HTMLElement)).toBe("Refusé.");
    expect(erreurContre(hote.querySelector("#d") as HTMLElement)).toBe("");
    hote.remove();
  });
});

// ── 10. La fiche dit vrai ───────────────────────────────────────────────────

describe("la fiche dit ce qui est", () => {
  /** Les formats que le serveur accepte, écrits À LA MAIN (`catalog/formations.py`). */
  const FORMATS: Record<string, string> = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WebP",
    "image/gif": "GIF",
  };

  it("la description : son aide dit qu'elle n'est pas encore affichée sur le site", async () => {
    servirLaListe([SOCIETE]);
    rendre();
    await ouvrir(SOCIETE.titre);

    const description = screen.getByLabelText("Description");
    expect(aideContre(description)).toMatch(/n'est pas encore affichée sur le site/);
    // Contre-épreuve : la phrase est celle de CE champ, pas de toute la fiche.
    expect(aideContre(screen.getByLabelText("Accroche"))).not.toMatch(/pas encore affichée/);
    expect(aideContre(screen.getByLabelText("Accroche"))).not.toBe("");
  });

  it("aucun lien d'achat : ni champ, ni envoi", async () => {
    servirLaListe([SOCIETE]);
    // Le serveur, lui, le rend encore.
    expect(SOCIETE.lien_d_achat).toMatch(/^https:/);
    const recus = ecouter("f-1/", () => ecriture({ ...SOCIETE, titre: "Créer sa société" }));
    rendre();
    await ouvrir(SOCIETE.titre);

    expect(screen.queryByLabelText(/lien d'achat/i)).toBeNull();
    expect(document.body.textContent ?? "").not.toMatch(/lien d'achat/i);
    for (const champ of document.querySelectorAll<HTMLInputElement>("input, textarea")) {
      expect(champ.value, champ.id).not.toBe(SOCIETE.lien_d_achat);
    }

    saisir(screen.getByLabelText("Titre"), "Créer sa société");
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer la fiche" }));

    await screen.findByText("La fiche est enregistrée.");
    expect(recus).toEqual([{ titre: "Créer sa société" }]);
    // Et l'écran n'en écrit plus le nom nulle part.
    expect(readFileSync(join(PAGES, "Formations.tsx"), "utf-8")).not.toMatch(/lien_d_achat/);
  });

  it("l'image : l'aide et le sélecteur nomment les mêmes formats, GIF compris", async () => {
    servirLaListe([SOCIETE]);
    rendre();
    await ouvrir(SOCIETE.titre);

    const image = screen.getByLabelText("Image de la formation");
    const acceptes = (image.getAttribute("accept") ?? "").split(",");
    expect(acceptes).toEqual(Object.keys(FORMATS));
    const aide = aideContre(image);
    for (const type of acceptes) expect(aide, type).toContain(FORMATS[type]);
    // Et l'aide n'annonce aucun format que le sélecteur refuserait.
    expect(aide).toMatch(/^JPEG, PNG, WebP ou GIF[.] /);
  });

  it("une image part en multipart : le corps est un FormData, et il porte le fichier", async () => {
    servirLaListe([SOCIETE]);
    // jsdom ne sait pas fabriquer l'adresse d'un aperçu.
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:apercu", revokeObjectURL: () => undefined }));
    const rendue = { ...SOCIETE, accroche: "Avec image", image: "https://media.exemple.test/f-1.png" };
    const envois: { adresse: string; init: RequestInit | undefined }[] = [];
    const vraiFetch = globalThis.fetch;
    vi.spyOn(globalThis, "fetch").mockImplementation((entree, init) => {
      const adresse = typeof entree === "string" ? entree : entree instanceof URL ? entree.href : entree.url;
      if (init?.method !== "POST") return vraiFetch(entree, init);
      envois.push({ adresse, init });
      return Promise.resolve(Response.json({ formation: rendue, refuses: [] }));
    });
    rendre();
    await ouvrir(SOCIETE.titre);

    const fichier = new File(["des octets"], "couverture.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("Image de la formation"), { target: { files: [fichier] } });
    expect(screen.getByText(/« couverture.png » remplacera l'image actuelle/)).toBeInTheDocument();
    saisir(screen.getByLabelText("Accroche"), "Avec image");
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer la fiche" }));

    await screen.findByText("La fiche est enregistrée.");
    expect(envois).toHaveLength(1);
    expect(new URL(envois[0].adresse, window.location.origin).href).toBe(`${DASH}/formations/f-1/`);
    const corps = envois[0].init?.body;
    expect(corps).toBeInstanceOf(FormData);
    const donnees = corps as FormData;
    expect(donnees.get("image")).toBe(fichier);
    expect(donnees.get("accroche")).toBe("Avec image");
    expect([...donnees.keys()].sort()).toEqual(["accroche", "image"]);
    // Pas de `Content-Type` : c'est le navigateur qui pose la frontière.
    expect(Object.keys(envois[0].init?.headers ?? {}).map((nom) => nom.toLowerCase())).not.toContain("content-type");
    // L'image rendue par le serveur est à l'écran, le sélecteur est vidé.
    expect(screen.getByAltText("Image actuelle de la formation")).toHaveAttribute("src", rendue.image);
    expect((screen.getByLabelText("Remplacer l'image") as HTMLInputElement).files).toHaveLength(0);
  });

  it("contre-épreuve : sans fichier, le corps part en JSON", async () => {
    servirLaListe([SOCIETE]);
    const envois: (RequestInit | undefined)[] = [];
    const vraiFetch = globalThis.fetch;
    vi.spyOn(globalThis, "fetch").mockImplementation((entree, init) => {
      if (init?.method !== "POST") return vraiFetch(entree, init);
      envois.push(init);
      return Promise.resolve(Response.json({ formation: { ...SOCIETE, accroche: "Sans image" }, refuses: [] }));
    });
    rendre();
    await ouvrir(SOCIETE.titre);

    saisir(screen.getByLabelText("Accroche"), "Sans image");
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer la fiche" }));

    await screen.findByText("La fiche est enregistrée.");
    expect(envois).toHaveLength(1);
    expect(envois[0]?.body).toBe(JSON.stringify({ accroche: "Sans image" }));
    expect(envois[0]?.headers).toMatchObject({ "Content-Type": "application/json" });
  });

  it("une écriture sur une formation laisse intactes les autres formations", async () => {
    const liste = servirLaListe([SOCIETE, POP]);
    const rendue = { ...SOCIETE, accroche: "Nouvelle accroche" };
    ecouter("f-1/", () => ecriture(rendue));
    const client = rendre();
    await ouvrir(SOCIETE.titre);
    const cle = ["admin", "formations"];
    const avant = client.getQueryData<{ formations: FormationAdmin[] }>(cle);
    expect(avant?.formations).toEqual([SOCIETE, POP]);

    saisir(screen.getByLabelText("Accroche"), "Nouvelle accroche");
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer la fiche" }));
    await screen.findByText("La fiche est enregistrée.");

    const apres = client.getQueryData<{ formations: FormationAdmin[] }>(cle);
    // Deux formations, dans le même ordre : la première est celle du serveur,
    // la seconde n'a pas été touchée — le même objet, pas une copie.
    expect(apres?.formations).toEqual([rendue, POP]);
    expect(apres?.formations[1]).toBe(avant?.formations[1]);
    expect(liste.lectures).toBe(1);

    // Et à l'écran : sa carte dit toujours ce qu'elle disait.
    fireEvent.click(screen.getByRole("button", { name: "Toutes les formations" }));
    const pop = (await screen.findByRole("heading", { level: 2, name: POP.titre })).closest("li") as HTMLElement;
    expect(within(pop).getByText("Hors ligne")).toBeInTheDocument();
    expect(within(pop).getByText("Pour la mettre en ligne, il manque un prix.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: SOCIETE.titre })).toBeInTheDocument();
  });
});

// ── 11. Les écritures en file ───────────────────────────────────────────────

describe("les écritures d'une même formation", () => {
  it("deux écritures lancées coup sur coup arrivent au serveur l'une après l'autre", async () => {
    servirLaListe([SOCIETE]);
    // Le serveur tient la fiche : chaque réponse porte TOUT ce qu'il a reçu.
    let tenue: FormationAdmin = SOCIETE;
    const serveur = retenir("f-1/", (corps) => {
      tenue = { ...tenue, ...(corps as Partial<FormationAdmin>) };
      return ecriture(tenue);
    });
    rendre();
    await ouvrir(SOCIETE.titre);

    // Première écriture : la fiche. Elle est en vol, le serveur ne répond pas.
    saisir(screen.getByLabelText("Accroche"), "Nouvelle accroche");
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer la fiche" }));
    await waitFor(() => expect(serveur.recus).toHaveLength(1));

    // Seconde écriture, pendant ce temps : mettre hors ligne.
    fireEvent.click(screen.getByRole("button", { name: "Mettre hors ligne" }));
    const question = await screen.findByRole("alertdialog");
    fireEvent.click(within(question).getByRole("button", { name: "Oui, la mettre hors ligne" }));

    // Elle ATTEND : on lui laisse le temps de partir à tort.
    await pause(150);
    expect(serveur.recus).toEqual([{ accroche: "Nouvelle accroche" }]);

    // La première réponse revient : la seconde part alors, et alors seulement.
    serveur.portes[0]();
    await waitFor(() => expect(serveur.recus).toHaveLength(2));
    expect(serveur.recus[1]).toEqual({ en_ligne: false });
    serveur.portes[1]();

    expect(await screen.findByRole("button", { name: "Mettre en ligne" })).toBeInTheDocument();
    expect(serveur.ensemble).toBe(1);
    // L'écran montre la DERNIÈRE fiche du serveur : hors ligne, accroche gardée.
    expect(screen.getByText("Hors ligne")).toBeInTheDocument();
    expect(screen.getByLabelText("Accroche")).toHaveValue("Nouvelle accroche");
  });

  it("contre-épreuve : deux formations différentes ne s'attendent pas", async () => {
    // La file est celle d'UNE formation : le détecteur d'envois simultanés
    // voit bien deux envois en vol quand ils ne partagent pas de file.
    const serveur = { ensemble: 0, enVol: 0, portes: [] as (() => void)[] };
    server.use(
      http.post(`${DASH}/formations/:id/`, async () => {
        serveur.enVol += 1;
        serveur.ensemble = Math.max(serveur.ensemble, serveur.enVol);
        await new Promise<void>((ouvrirLaPorte) => serveur.portes.push(ouvrirLaPorte));
        serveur.enVol -= 1;
        return ecriture(SOCIETE);
      }),
    );
    const jeton = { Accept: "application/json", "Content-Type": "application/json" };
    const envois = ["f-1", "f-2"].map((id) =>
      fetch(`${DASH}/formations/${id}/`, { method: "POST", headers: jeton, body: "{}" }),
    );
    await waitFor(() => expect(serveur.portes).toHaveLength(2));
    expect(serveur.ensemble).toBe(2);
    for (const porte of serveur.portes) porte();
    await Promise.all(envois);
  });

  it("hors connexion : l'envoi échoue tout de suite, le dit, et rend la main", async () => {
    servirLaListe([SOCIETE]);
    let tentatives = 0;
    server.use(
      http.post(`${DASH}/formations/lecons/l-1/`, () => {
        tentatives += 1;
        return HttpResponse.error();
      }),
    );
    rendre();
    await ouvrir(SOCIETE.titre);

    // La connexion tombe, comme le navigateur le signale.
    vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
    window.dispatchEvent(new Event("offline"));
    expect(navigator.onLine).toBe(false);
    expect(onlineManager.isOnline()).toBe(false);

    fireEvent.click(
      screen.getByRole("button", { name: "Modifier la leçon “Choisir son statut”" }),
    );
    const titre = screen.getByLabelText("Titre de la leçon");
    saisir(titre, "Choisir son statut juridique");
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer la leçon" }));

    // Dit, en français, dans la fenêtre.
    const bandeau = await screen.findByRole("alert");
    expect(bandeau).toHaveTextContent(/Le serveur n'a pas répondu/);
    expect(tentatives).toBe(1);
    // La main est rendue : le bouton n'est plus « Enregistrement… », la
    // saisie est là, et la fenêtre se ferme.
    const enregistrer = screen.getByRole("button", { name: "Enregistrer la leçon" });
    expect(enregistrer).toBeEnabled();
    expect(enregistrer).not.toHaveAttribute("aria-busy");
    expect(titre).toHaveValue("Choisir son statut juridique");
    fireEvent.click(screen.getByRole("button", { name: "Annuler" }));
    await waitFor(() => expect(screen.queryByLabelText("Titre de la leçon")).toBeNull());
  });
});

// ── 12. La fenêtre, par son chemin natif ────────────────────────────────────

describe("la fenêtre native", () => {
  /** Ce que la doublure a fait, dans l'ordre. */
  let journal: string[] = [];
  const prototype = HTMLDialogElement.prototype as unknown as Record<string, unknown>;
  const dOrigine = { showModal: prototype.showModal, close: prototype.close };

  /** Une doublure de la fenêtre du navigateur : `showModal` pose `open` et
   *  refuse une fenêtre déjà ouverte, `close` retire `open` et émet `close`
   *  PLUS TARD, comme un navigateur. */
  beforeEach(() => {
    journal = [];
    prototype.showModal = function (this: HTMLDialogElement) {
      if (this.hasAttribute("open")) throw new DOMException("fenêtre déjà ouverte", "InvalidStateError");
      journal.push("showModal");
      this.setAttribute("open", "");
      this.querySelector<HTMLElement>("input, select, textarea, button")?.focus();
    };
    prototype.close = function (this: HTMLDialogElement) {
      if (!this.hasAttribute("open")) return;
      journal.push("close");
      this.removeAttribute("open");
      setTimeout(() => this.dispatchEvent(new Event("close")), 0);
    };
  });

  afterEach(() => {
    prototype.showModal = dOrigine.showModal;
    prototype.close = dOrigine.close;
  });

  function fenetre(): HTMLDialogElement | null {
    return document.querySelector("dialog");
  }

  function fenetreOuverte(): HTMLDialogElement {
    const element = fenetre();
    if (!element) throw new Error("aucune fenêtre à l'écran");
    return element;
  }

  /** Échap, comme le navigateur : `cancel`, puis fermeture si rien ne s'y
   *  oppose. */
  function echap(element: HTMLDialogElement) {
    const annulation = new Event("cancel", { cancelable: true });
    element.dispatchEvent(annulation);
    if (!annulation.defaultPrevented) element.close();
  }

  /** Le second Échap de Chrome : la fenêtre se ferme SANS `cancel`. */
  function fermetureForcee(element: HTMLDialogElement) {
    element.close();
  }

  const ouvertures = () => journal.filter((geste) => geste === "showModal").length;
  const fermetures = () => journal.filter((geste) => geste === "close").length;

  async function ouvrirLaLecon(): Promise<HTMLElement> {
    await ouvrir(SOCIETE.titre);
    const ouvreur = screen.getByRole("button", { name: "Modifier la leçon “Choisir son statut”" });
    ouvreur.focus();
    fireEvent.click(ouvreur);
    return ouvreur;
  }

  it("s'ouvre par showModal ; la fermeture du mode strict n'est pas lue comme un geste", async () => {
    servirLaListe([SOCIETE]);
    rendre({ strict: true });
    await ouvrirLaLecon();

    expect(fenetreOuverte().open).toBe(true);
    expect(ouvertures()).toBeGreaterThanOrEqual(1);
    // Ouverte une fois de plus que fermée : la fenêtre est ouverte, une fois.
    expect(ouvertures() - fermetures()).toBe(1);
    // Le mode strict a bien démonté puis remonté : sinon ce test ne joue rien.
    expect(fermetures()).toBe(1);

    // L'événement `close` de ce démontage arrive APRÈS coup : il ne ferme rien.
    await pause();
    expect(fenetreOuverte().open).toBe(true);
    expect(screen.getByLabelText("Titre de la leçon")).toHaveValue("Choisir son statut");
  });

  it("Échap ferme, rend le focus à l'ouvreur, et ne ferme pas la fenêtre suivante", async () => {
    servirLaListe([SOCIETE]);
    rendre({ strict: true });
    const ouvreur = await ouvrirLaLecon();
    // La fenêtre a pris le focus : son retour prouvera quelque chose.
    expect(ouvreur).not.toHaveFocus();

    echap(fenetreOuverte());

    await waitFor(() => expect(fenetre()).toBeNull());
    expect(ouvreur).toHaveFocus();

    // Rouverte aussitôt : un `close` en retard de la première ne la referme pas.
    fireEvent.click(ouvreur);
    await pause();
    expect(fenetreOuverte().open).toBe(true);
    expect(screen.getByLabelText("Titre de la leçon")).toBeInTheDocument();
  });

  it("pendant un envoi, ni Échap ni une fermeture forcée ne ferment : le refus est vu", async () => {
    servirLaListe([SOCIETE]);
    const REFUS = "Donnez un titre à la leçon.";
    const serveur = retenir("lecons/l-1/", () => refus(REFUS, "titre_manquant", "titre"));
    rendre({ strict: true });
    await ouvrirLaLecon();
    const titre = screen.getByLabelText("Titre de la leçon");
    saisir(titre, " ");
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer la leçon" }));
    await waitFor(() => expect(serveur.recus).toHaveLength(1));
    expect(screen.getByRole("button", { name: "Enregistrement…" })).toBeDisabled();

    // Premier Échap : `cancel` est retenu, la fenêtre reste.
    echap(fenetreOuverte());
    await pause();
    expect(fenetreOuverte().open).toBe(true);

    // Second Échap, à la façon de Chrome : le navigateur ferme d'autorité.
    const avant = ouvertures();
    fermetureForcee(fenetreOuverte());
    expect(fenetreOuverte().open).toBe(false);
    await pause();
    // La fenêtre est toujours là, ROUVERTE, avec la saisie.
    expect(fenetreOuverte().open).toBe(true);
    expect(ouvertures()).toBe(avant + 1);
    expect(titre).toBeInTheDocument();

    // La réponse arrive : le champ refusé est montré, dans la fenêtre.
    serveur.portes[0]();
    await waitFor(() => expect(erreurContre(titre)).toBe(REFUS));
    expect(fenetreOuverte().open).toBe(true);
    expect(titre).toHaveValue(" ");
  });

  it("contre-épreuve : hors envoi, une fermeture forcée ferme bien, et l'état suit", async () => {
    servirLaListe([SOCIETE]);
    rendre({ strict: true });
    const ouvreur = await ouvrirLaLecon();
    await pause();

    fermetureForcee(fenetreOuverte());

    await waitFor(() => expect(fenetre()).toBeNull());
    expect(ouvreur).toHaveFocus();
    // Et l'on peut la rouvrir : l'état n'est pas resté sur « ouverte ».
    fireEvent.click(ouvreur);
    expect(fenetreOuverte().open).toBe(true);
  });
});

// ── 13. Un écran périmé se relit ────────────────────────────────────────────

describe("un refus qui dit l'écran périmé fait relire la liste", () => {
  const OFFRE = unModule({ id: "m-a", rang: 0, titre: "Poser son offre" });
  const CLIENTS = unModule({ id: "m-b", rang: 1, titre: "Trouver ses clients" });
  const AILLEURS = unModule({ id: "m-z", rang: 2, titre: "Ajouté depuis un autre onglet" });
  const VUE = uneFormation({ nombre_de_modules: 2, modules: [OFFRE, CLIENTS] });
  const VRAIE = uneFormation({ nombre_de_modules: 3, modules: [OFFRE, CLIENTS, AILLEURS] });

  const PERIMES: [code: string, statut: number, message: string][] = [
    ["ordre_incomplet", 400, "La liste ne contient pas tous les modules."],
    ["ordre_etranger", 400, "La liste contient un module d'une autre formation."],
    ["ordre_doublon", 400, "La liste contient deux fois le même élément."],
    ["formation_inconnue", 404, "Cette formation n'existe pas."],
  ];

  for (const [code, statut, message] of PERIMES) {
    it(`« ${code} » (${statut}) : le refus est dit, et le programme est relu`, async () => {
      const liste = servirPuis([VUE], [VRAIE]);
      const recus = ecouter("f-1/ordre/", () => refus(message, code, undefined, statut));
      rendre();
      await ouvrir(VUE.titre);
      expect(modulesALEcran()).toEqual(["Poser son offre", "Trouver ses clients"]);

      fireEvent.click(screen.getByRole("button", { name: "Monter le module “Trouver ses clients”" }));

      const bandeau = await screen.findByRole("alert");
      expect(bandeau).toHaveTextContent(message);
      expect(bandeau).toHaveTextContent(/il est relu en ce moment/);
      expect(recus).toEqual([{ modules: ["m-b", "m-a"] }]);
      // La liste a été relue, et le module ajouté ailleurs est à l'écran : le
      // geste suivant partira avec les trois.
      await waitFor(() =>
        expect(modulesALEcran()).toEqual([
          "Poser son offre",
          "Trouver ses clients",
          "Ajouté depuis un autre onglet",
        ]),
      );
      expect(liste.lectures).toBe(2);
    });
  }

  it("dans une fenêtre aussi : une leçon que le serveur ne trouve plus", async () => {
    const liste = servirPuis([SOCIETE], [SOCIETE]);
    ecouter("lecons/l-1/", () => refus("Cette leçon n'existe pas.", "lecon_inconnue", undefined, 404));
    rendre();
    await ouvrir(SOCIETE.titre);

    fireEvent.click(
      screen.getByRole("button", { name: "Modifier la leçon “Choisir son statut”" }),
    );
    saisir(screen.getByLabelText("Titre de la leçon"), "Autre titre");
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer la leçon" }));

    const bandeau = await screen.findByRole("alert");
    expect(bandeau).toHaveTextContent("Cette leçon n'existe pas.");
    await waitFor(() => expect(liste.lectures).toBe(2));
    // La saisie est restée.
    expect(screen.getByLabelText("Titre de la leçon")).toHaveValue("Autre titre");
  });

  it("contre-épreuve : un refus ordinaire ne relit rien", async () => {
    const liste = servirPuis([VUE], [VRAIE]);
    ecouter("f-1/ordre/", () => refus("Le serveur est occupé.", "indisponible", undefined, 503));
    rendre();
    await ouvrir(VUE.titre);

    fireEvent.click(screen.getByRole("button", { name: "Monter le module “Trouver ses clients”" }));

    const bandeau = await screen.findByRole("alert");
    expect(bandeau).toHaveTextContent("Le serveur est occupé.");
    expect(bandeau).not.toHaveTextContent(/relu/);
    await pause(100);
    expect(liste.lectures).toBe(1);
    expect(modulesALEcran()).toEqual(["Poser son offre", "Trouver ses clients"]);
  });
});

// ── 14. Un module ajouté, puis corrigé ──────────────────────────────────────

describe("la fenêtre d'un module", () => {
  const RAISON = "La description est trop longue.";
  const VENDRE = unModule({ id: "m-n", rang: 2, titre: "Vendre", description: "" });
  const AVEC = { ...SOCIETE, modules: [...SOCIETE.modules, VENDRE] };

  it("un module ajouté dont un champ est écarté : le second envoi le MODIFIE", async () => {
    servirLaListe([SOCIETE]);
    const creations = ecouter("f-1/modules/", () =>
      HttpResponse.json(
        { formation: AVEC, refuses: [{ champ: "description", raison: RAISON }], module_id: "m-n" },
        { status: 201 },
      ),
    );
    const modifications = ecouter("modules/m-n/", () =>
      ecriture({ ...AVEC, modules: [...SOCIETE.modules, { ...VENDRE, description: "Courte." }] }, { module_id: "m-n" }),
    );
    rendre();
    await ouvrir(SOCIETE.titre);

    fireEvent.click(screen.getByRole("button", { name: "Ajouter un module" }));
    expect(screen.getByRole("heading", { level: 2, name: "Ajouter un module" })).toBeInTheDocument();
    saisir(screen.getByLabelText("Titre du module"), "Vendre");
    const description = within(document.querySelector("dialog") as HTMLElement).getByLabelText("Description");
    saisir(description, "Beaucoup trop longue.");
    fireEvent.click(screen.getByRole("button", { name: "Ajouter le module" }));

    // Le module EXISTE : la fenêtre reste, et dit qu'elle le modifie désormais.
    await waitFor(() => expect(erreurContre(description)).toBe(RAISON));
    expect(creations).toEqual([{ titre: "Vendre", description: "Beaucoup trop longue." }]);
    expect(screen.getByRole("heading", { level: 2, name: "Modifier le module" })).toBeInTheDocument();
    expect(description).toHaveValue("Beaucoup trop longue.");
    expect(screen.getByText(/Le module est enregistré, sauf ce qui est signalé/)).toBeInTheDocument();

    saisir(description, "Courte.");
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer le module" }));

    await waitFor(() => expect(document.querySelector("dialog")).toBeNull());
    // Un seul module créé ; la correction est partie vers LUI, et elle seule.
    expect(creations).toHaveLength(1);
    expect(modifications).toEqual([{ description: "Courte." }]);
    expect(modulesALEcran().filter((nom) => nom === "Vendre")).toHaveLength(1);
  });

  it("contre-épreuve : sans champ écarté, la fenêtre se ferme au premier envoi", async () => {
    servirLaListe([SOCIETE]);
    const creations = ecouter("f-1/modules/", () => ecriture(AVEC, { module_id: "m-n" }, 201));
    rendre();
    await ouvrir(SOCIETE.titre);

    fireEvent.click(screen.getByRole("button", { name: "Ajouter un module" }));
    saisir(screen.getByLabelText("Titre du module"), "Vendre");
    fireEvent.click(screen.getByRole("button", { name: "Ajouter le module" }));

    await waitFor(() => expect(document.querySelector("dialog")).toBeNull());
    expect(creations).toEqual([{ titre: "Vendre", description: "" }]);
    expect(modulesALEcran()).toContain("Vendre");
  });
});

// ── 15. Les inscrits, et ce que dit la carte « La fiche » ───────────────────
//
// Depuis le 20/11/2026, une formation se paie sur la plateforme, et la fiche
// rendue par `dashboard/formations._vue` porte `nombre_d_achats`. L'écran
// l'affiche sur la carte de la liste et dans la bande d'état — et n'affiche
// RIEN quand le serveur ne le rend pas : un zéro inventé dirait « personne ne
// s'est inscrit » sur la foi d'une clé absente (règle 1).

describe("les inscrits d'une formation", () => {
  const INSCRITS = /inscrit/i;

  it("la carte de la liste dit le nombre d'inscrits que le serveur rend", async () => {
    servirLaListe([
      uneFormation({ id: "f-1", titre: "Formation suivie par trois", nombre_d_achats: 3 }),
      uneFormation({ id: "f-2", slug: "une", titre: "Formation suivie par une", nombre_d_achats: 1 }),
      uneFormation({ id: "f-3", slug: "zero", titre: "Personne encore", nombre_d_achats: 0 }),
    ]);
    rendre();

    const carte = async (titre: string) =>
      (await screen.findByRole("heading", { level: 2, name: titre })).closest("li") as HTMLElement;
    const lu = (element: HTMLElement) =>
      (within(element).getByText(INSCRITS).textContent ?? "").replace(/\s/g, " ");

    expect(lu(await carte("Formation suivie par trois"))).toBe("3 inscrits");
    // Le singulier s'accorde.
    expect(lu(await carte("Formation suivie par une"))).toBe("1 inscrit");
    // Un VRAI zéro, reçu, se dit — en toutes lettres.
    expect(lu(await carte("Personne encore"))).toBe("Aucun inscrit pour l'instant");
  });

  it("contre-épreuve : sans la clé, ou avec une valeur illisible, rien n'est affiché", async () => {
    const sansCle = uneFormation({ id: "f-1", titre: "Serveur d'avant" });
    expect("nombre_d_achats" in sansCle).toBe(false);
    servirLaListe([
      sansCle,
      uneFormation({ id: "f-2", slug: "nul", titre: "Valeur nulle", nombre_d_achats: null as unknown as number }),
      uneFormation({ id: "f-3", slug: "texte", titre: "Valeur en texte", nombre_d_achats: "3" as unknown as number }),
      uneFormation({ id: "f-4", slug: "negatif", titre: "Valeur négative", nombre_d_achats: -1 }),
    ]);
    rendre();

    await screen.findByRole("heading", { level: 2, name: "Serveur d'avant" });
    expect(screen.getAllByRole("listitem").length).toBeGreaterThanOrEqual(4);
    expect(screen.queryByText(INSCRITS)).toBeNull();
  });

  it("la bande d'état de la formation ouverte le dit aussi", async () => {
    servirLaListe([uneFormation({ nombre_d_achats: 7 })]);
    rendre();
    await ouvrir(SOCIETE.titre);

    const bande = screen.getByRole("heading", { level: 2, name: SOCIETE.titre }).closest("section") as HTMLElement;
    expect((within(bande).getByText(INSCRITS).textContent ?? "").replace(/\s/g, " ")).toBe("7 inscrits");
  });

  it("contre-épreuve : la bande d'état ne dit rien des inscrits quand le serveur n'en dit rien", async () => {
    servirLaListe([uneFormation()]);
    rendre();
    await ouvrir(SOCIETE.titre);

    // Dans la BANDE : depuis le 20/11/2026 la formation ouverte porte aussi
    // une carte « Élèves », dont le titre ne dit aucun nombre.
    const bande = screen.getByRole("heading", { level: 2, name: SOCIETE.titre }).closest("section") as HTMLElement;
    expect(within(bande).getByText(/Vos visiteurs la voient/)).toBeInTheDocument();
    expect(within(bande).queryByText(INSCRITS)).toBeNull();
    // Et nulle part l'écran n'avance un nombre d'inscrits.
    expect(document.body.textContent ?? "").not.toMatch(/\d+\s+inscrit|Aucun inscrit/);
  });

  it("la carte « La fiche » dit ce qui est repris sur le site, pas que tout y est lu", async () => {
    servirLaListe([uneFormation()]);
    rendre();
    await ouvrir(SOCIETE.titre);

    const fiche = screen.getByRole("heading", { level: 2, name: "La fiche" }).closest("section") as HTMLElement;
    expect(fiche).toHaveTextContent(/Le prix, les durées et le programme sont repris sur votre site/);
    expect(fiche).toHaveTextContent(/espace de vos apprenants/);
    // La phrase d'avant annonçait que les visiteurs lisaient toute la fiche.
    expect(document.body.textContent).not.toMatch(/Ce que vos visiteurs lisent/);
  });
});

// ── 16. Les élèves : qui est inscrit, et retirer un accès ───────────────────
//
// La carte « Inscrits » est devenue « Élèves » le 20/11/2026 : une ligne par
// PERSONNE et par achat (`GET formations/<id>/eleves/`), avec son suivi. Les
// gestes d'accès n'ont pas changé de contrat — RECOPIÉ de
// `dashboard/formations.py` (`achat`, `_vue_achat`) :
// `POST formations/achats/<id>/` (`{"revoque": true|false, "motif"?}`) rend
// `{"achat": <la ligne à jour>}` — ou `{"erreur", "code"}`, 409
// `formation_rachetee` quand rétablir est impossible.
// La date et le motif d'un retrait viennent toujours de
// `GET formations/<id>/achats/`, lue à côté.
// Un accès se RETIRE et se rétablit : l'achat et son paiement restent.
// Le suivi lui-même (progression, date de fin, export, séances) est verrouillé
// dans `le-suivi-des-eleves.test.tsx`.

describe("la carte « Élèves » d'une formation ouverte : les accès", () => {
  /** Les achats, tels que `_vue_achat` les rend. */
  const ACHAT_OUVERT = {
    id: "a-1",
    organisation: "Cabinet Eva",
    organisation_id: "org-1",
    email: "eva@exemple.fr",
    montant_cents: 149_000,
    devise: "EUR",
    achete_le: "2026-11-03T12:00:00+00:00",
    revoque_le: null,
    motif_de_revocation: "",
    acces_jusqu_au: null,
    acces: "ouvert",
    reference_paiement: "pi_test_1",
  };
  const ACHAT_RETIRE = {
    ...ACHAT_OUVERT,
    id: "a-2",
    organisation: "Atelier Nord",
    organisation_id: "org-2",
    email: "nord@exemple.fr",
    montant_cents: 131_950,
    achete_le: "2026-10-12T12:00:00+00:00",
    revoque_le: "2026-11-18T12:00:00+00:00",
    motif_de_revocation: "Remboursement",
    acces: "retire",
    reference_paiement: "pi_test_2",
  };

  /** Les lignes du tableau, telles que `suivi.tableau_des_eleves` les rend. */
  const OUVERT = {
    achat_id: "a-1",
    eleve_id: "e-1",
    nom: "Eva Martin",
    email: "eva@exemple.fr",
    organisation: "Cabinet Eva",
    achete_le: "2026-11-03T12:00:00+00:00",
    acces_jusqu_au: null,
    acces: "ouvert",
    derniere_connexion: null,
    derniere_activite: null,
    lecons_terminees: 0,
    lecons_total: 2,
    pourcent: 0,
    minutes_en_presentiel_signees: 0,
  };
  const RETIRE = {
    ...OUVERT,
    achat_id: "a-2",
    eleve_id: "e-2",
    nom: "Nora Petit",
    email: "nord@exemple.fr",
    organisation: "Atelier Nord",
    achete_le: "2026-10-12T12:00:00+00:00",
    acces: "retire",
  };

  type Reponse = () => Response | Promise<Response>;

  /** Sert les élèves de la formation `f-1` — et, à côté, ses achats — et
   *  compte les lectures des élèves. */
  function servirLesEleves(
    reponse: Reponse,
    achats: object[] = [ACHAT_OUVERT, ACHAT_RETIRE],
  ): { lectures: number } {
    const compte = { lectures: 0 };
    server.use(
      http.get(`${DASH}/formations/f-1/eleves/`, () => {
        compte.lectures += 1;
        return reponse();
      }),
      http.get(`${DASH}/formations/f-1/achats/`, () => HttpResponse.json({ achats })),
    );
    return compte;
  }

  const eleves = (...lignes: object[]): Reponse => () =>
    HttpResponse.json({ eleves: lignes, lecons_total: 2 });

  function carte(): HTMLElement {
    return screen.getByRole("heading", { level: 2, name: "Élèves" }).closest("section") as HTMLElement;
  }

  function deplier() {
    fireEvent.click(within(carte()).getByRole("button", { name: "Afficher les élèves" }));
  }

  /** Une ligne du tableau, son texte — toute espace ramenée à l'ordinaire —
   *  et l'état de son accès, lu sur la pastille. */
  function ligne(organisation: string): { element: HTMLElement; texte: string; etat: string } {
    const element = within(carte()).getByText(organisation).closest("tr") as HTMLElement;
    return {
      element,
      texte: (element.textContent ?? "").replace(/\s/g, " "),
      etat: element.querySelector(".pastille")?.textContent ?? "",
    };
  }

  async function ouvrirLaCarte(reponse: Reponse, achats?: object[]) {
    servirLaListe([SOCIETE]);
    const compte = servirLesEleves(reponse, achats);
    rendre();
    await ouvrir(SOCIETE.titre);
    return compte;
  }

  it("repliée par défaut : rien n'est lu avant l'ouverture, puis le tableau montre chaque élève", async () => {
    const compte = await ouvrirLaCarte(eleves(OUVERT, RETIRE));

    const bascule = within(carte()).getByRole("button", { name: "Afficher les élèves" });
    expect(bascule).toHaveAttribute("aria-expanded", "false");
    expect(document.getElementById(bascule.getAttribute("aria-controls") ?? "")).toHaveAttribute("hidden");
    await pause();
    expect(compte.lectures).toBe(0);
    expect(within(carte()).queryByRole("table")).toBeNull();

    deplier();

    const tableau = await within(carte()).findByRole("table");
    expect(compte.lectures).toBe(1);
    expect(within(carte()).getByRole("button", { name: "Masquer les élèves" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    // Le langage commun des tableaux.
    expect(tableau).toHaveClass("tableau");
    expect(tableau.parentElement).toHaveClass("tableau-cadre", "tableau-defile");
    const entetes = within(tableau).getAllByRole("columnheader");
    expect(entetes.map((entete) => entete.textContent)).toEqual([
      "Élève",
      "Organisation",
      "Acheté le",
      "Accès",
      "Dernière connexion",
      "Dernière activité",
      "Progression",
      "Présentiel signé",
      "Actions",
    ]);
    for (const entete of entetes) expect(entete).toHaveAttribute("scope", "col");

    const ouvert = ligne("Cabinet Eva");
    expect(ouvert.texte).toContain("Eva Martin");
    expect(ouvert.texte).toContain("eva@exemple.fr");
    expect(ouvert.texte).toContain("3 novembre 2026");
    expect(ouvert.etat).toBe("Ouvert");
    expect(within(ouvert.element).getByRole("button", { name: "Retirer l'accès de “Eva Martin”" })).toHaveClass(
      "bouton-discret",
    );

    const retire = ligne("Atelier Nord");
    expect(retire.etat).toBe("Retiré");
    // La date et le motif du retrait, lus sur l'achat.
    await waitFor(() =>
      expect(ligne("Atelier Nord").texte).toContain("Accès retiré le 18 novembre 2026 — Remboursement"),
    );
    expect(
      within(retire.element).getByRole("button", { name: "Rétablir l'accès de “Nora Petit”" }),
    ).toBeInTheDocument();
    expect(within(retire.element).queryByRole("button", { name: /Retirer/ })).toBeNull();

    // Rien ne s'efface ici non plus.
    expect(carte().textContent ?? "").not.toMatch(/supprim/i);
    expect(carte().querySelector(".bouton-echec")).toBeNull();
  });

  it("liste reçue et vide : « Aucun élève pour l'instant », sans tableau ni panne", async () => {
    await ouvrirLaCarte(eleves(), []);
    deplier();

    expect(await within(carte()).findByText("Aucun élève pour l'instant")).toBeInTheDocument();
    expect(within(carte()).queryByRole("table")).toBeNull();
    expect(within(carte()).queryByText(/Impossible de charger/)).toBeNull();
  });

  for (const [nom, reponse] of [
    ["500", () => new HttpResponse("panne", { status: 500 })],
    ["200 sans la liste", () => HttpResponse.json({})],
    ["200 avec une liste qui n'en est pas une", () => HttpResponse.json({ eleves: "aucun" })],
  ] as [string, Reponse][]) {
    it(`panne (${nom}) : dite comme une panne, jamais « Aucun élève »`, async () => {
      await ouvrirLaCarte(reponse);
      deplier();

      expect(await within(carte()).findByText(/Impossible de charger les élèves/)).toBeInTheDocument();
      expect(within(carte()).queryByText(/Aucun élève/)).toBeNull();
      expect(within(carte()).queryByRole("table")).toBeNull();
    });
  }

  it("pendant la lecture : un chargement annoncé, ni tableau ni « Aucun élève »", async () => {
    let liberer: () => void = () => undefined;
    const attente = new Promise<void>((resoudre) => {
      liberer = resoudre;
    });
    await ouvrirLaCarte(async () => {
      await attente;
      return HttpResponse.json({ eleves: [OUVERT], lecons_total: 2 });
    });
    deplier();

    await waitFor(() => expect(carte().querySelector(".squelette-groupe")).not.toBeNull());
    expect(within(carte()).queryByText(/Aucun élève/)).toBeNull();
    expect(within(carte()).queryByRole("table")).toBeNull();

    liberer();
    expect(await within(carte()).findByRole("table")).toBeInTheDocument();
    expect(carte().querySelector(".squelette-groupe")).toBeNull();
  });

  it("retirer un accès : une confirmation qui demande un motif, puis l'envoi, puis la ligne rendue", async () => {
    await ouvrirLaCarte(eleves(OUVERT, RETIRE));
    const envois = ecouter("achats/a-1/", (corps) =>
      HttpResponse.json({
        achat: {
          ...ACHAT_OUVERT,
          revoque_le: "2026-11-20T12:00:00+00:00",
          motif_de_revocation: (corps as { motif: string }).motif,
          acces: "retire",
        },
      }),
    );
    deplier();
    await within(carte()).findByRole("table");

    fireEvent.click(screen.getByRole("button", { name: "Retirer l'accès de “Eva Martin”" }));

    // Rien n'est parti : on demande d'abord.
    const question = screen.getByRole("alertdialog", { name: /Retirer l'accès de « Eva Martin »/ });
    expect(question).toHaveAccessibleDescription(/Rien\s+n'est effacé/);
    expect(question).toHaveAccessibleDescription(/rétablir l'accès à tout moment/);
    const motif = within(question).getByLabelText("Motif du retrait");
    expect(motif).toHaveFocus();
    expect(envois).toEqual([]);

    // Sans motif : aucun envoi, et le champ le dit.
    fireEvent.click(within(question).getByRole("button", { name: "Oui, retirer l'accès" }));
    expect(erreurContre(motif)).toMatch(/Indiquez le motif/);
    expect(motif).toHaveAttribute("aria-invalid", "true");
    await pause();
    expect(envois).toEqual([]);

    saisir(motif, "  Remboursement demandé  ");
    fireEvent.click(within(question).getByRole("button", { name: "Oui, retirer l'accès" }));

    await waitFor(() => expect(screen.queryByRole("alertdialog")).toBeNull());
    // Le corps que la route lit : `revoque` et `motif`, et rien d'autre.
    expect(envois).toEqual([{ revoque: true, motif: "Remboursement demandé" }]);
    // La ligne est celle que le serveur a rendue.
    const apres = ligne("Cabinet Eva");
    expect(apres.etat).toBe("Retiré");
    expect(apres.texte).toContain("Accès retiré le 20 novembre 2026 — Remboursement demandé");
    const retablir = within(apres.element).getByRole("button", { name: "Rétablir l'accès de “Eva Martin”" });
    expect(retablir).toHaveFocus();
    expect(within(carte()).getByRole("status")).toHaveTextContent(/L'accès de « Eva Martin » est retiré/);
    expect(within(carte()).queryByRole("alert")).toBeNull();
    // L'autre ligne n'a pas bougé.
    expect(ligne("Atelier Nord").texte).toContain("Accès retiré le 18 novembre 2026 — Remboursement");
  });

  it("un achat partagé : la confirmation dit que le retrait vaut pour toutes les personnes", async () => {
    const COLLEGUE = { ...OUVERT, eleve_id: "e-3", nom: "Léa Roux", email: "lea@exemple.fr" };
    await ouvrirLaCarte(eleves(OUVERT, COLLEGUE));
    deplier();
    await within(carte()).findByRole("table");

    fireEvent.click(screen.getByRole("button", { name: "Retirer l'accès de “Léa Roux”" }));
    expect(screen.getByRole("alertdialog")).toHaveAccessibleDescription(
      /partagé par 2 personnes de « Cabinet Eva » : le changement vaut pour toutes/,
    );
  });

  it("contre-épreuve : « Annuler » et Échap n'envoient rien, et rendent le focus au bouton", async () => {
    await ouvrirLaCarte(eleves(OUVERT));
    const envois = ecouter("achats/a-1/", () => HttpResponse.json({ achat: ACHAT_OUVERT }));
    deplier();
    await within(carte()).findByRole("table");
    const retirer = screen.getByRole("button", { name: "Retirer l'accès de “Eva Martin”" });

    fireEvent.click(retirer);
    // Seule sur son achat : la confirmation ne parle pas de partage.
    expect(screen.getByRole("alertdialog")).not.toHaveAccessibleDescription(/partagé/);
    fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Annuler" }));
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(retirer).toHaveFocus();

    fireEvent.click(retirer);
    saisir(screen.getByLabelText("Motif du retrait"), "Erreur");
    fireEvent.keyDown(screen.getByLabelText("Motif du retrait"), { key: "Escape" });
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(retirer).toHaveFocus();

    await pause();
    expect(envois).toEqual([]);
    expect(ligne("Cabinet Eva").etat).toBe("Ouvert");
    // Un motif abandonné ne revient pas à la confirmation suivante.
    fireEvent.click(retirer);
    expect(screen.getByLabelText("Motif du retrait")).toHaveValue("");
  });

  it("rétablir un accès : un seul geste, `revoque: false`, et la ligne rendue", async () => {
    await ouvrirLaCarte(eleves(OUVERT, RETIRE));
    // « Rétablir efface le motif » (`formations.achat`).
    const envois = ecouter("achats/a-2/", () =>
      HttpResponse.json({
        achat: { ...ACHAT_RETIRE, revoque_le: null, motif_de_revocation: "", acces: "ouvert" },
      }),
    );
    deplier();
    await within(carte()).findByRole("table");

    fireEvent.click(screen.getByRole("button", { name: "Rétablir l'accès de “Nora Petit”" }));

    await waitFor(() => expect(ligne("Atelier Nord").etat).toBe("Ouvert"));
    expect(envois).toEqual([{ revoque: false }]);
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(ligne("Atelier Nord").texte).not.toContain("Accès retiré");
    expect(within(carte()).getByRole("status")).toHaveTextContent(/L'accès de « Nora Petit » est rétabli/);
    expect(
      within(ligne("Atelier Nord").element).getByRole("button", { name: "Retirer l'accès de “Nora Petit”" }),
    ).toBeInTheDocument();
  });

  it("rétablir refusé (409) : la phrase du serveur en alerte, et la ligne ne change pas", async () => {
    await ouvrirLaCarte(eleves(RETIRE));
    // La phrase et le code que `formations.achat` écrit.
    const REFUS =
      "Cette organisation a racheté la formation depuis : elle y a déjà accès par son nouvel achat. Il n'y a rien à rétablir.";
    const envois = ecouter("achats/a-2/", () => refus(REFUS, "formation_rachetee", undefined, 409));
    deplier();
    await within(carte()).findByRole("table");

    fireEvent.click(screen.getByRole("button", { name: "Rétablir l'accès de “Nora Petit”" }));

    expect(await within(carte()).findByRole("alert")).toHaveTextContent(REFUS);
    expect(envois).toHaveLength(1);
    expect(ligne("Atelier Nord").etat).toBe("Retiré");
    expect(ligne("Atelier Nord").texte).toContain("Accès retiré le 18 novembre 2026 — Remboursement");
    expect(within(carte()).getByRole("status")).toBeEmptyDOMElement();
    // On peut réessayer : le bouton n'est pas resté occupé.
    const bouton = screen.getByRole("button", { name: "Rétablir l'accès de “Nora Petit”" });
    await waitFor(() => expect(bouton).not.toHaveAttribute("aria-disabled"));
  });

  it("une réponse qui ne montre pas le retrait n'est pas annoncée comme un retrait", async () => {
    await ouvrirLaCarte(eleves(OUVERT));
    // Le serveur répond 200, mais la ligne rendue a toujours son accès.
    ecouter("achats/a-1/", () => HttpResponse.json({ achat: ACHAT_OUVERT }));
    deplier();
    await within(carte()).findByRole("table");

    fireEvent.click(screen.getByRole("button", { name: "Retirer l'accès de “Eva Martin”" }));
    saisir(screen.getByLabelText("Motif du retrait"), "Remboursement");
    fireEvent.click(screen.getByRole("button", { name: "Oui, retirer l'accès" }));

    expect(await within(carte()).findByRole("alert")).toHaveTextContent(/n'apparaît pas dans la réponse du serveur/);
    expect(within(carte()).getByRole("status")).toBeEmptyDOMElement();
    expect(ligne("Cabinet Eva").etat).toBe("Ouvert");
  });

  it("motif refusé par le serveur (400 `motif_trop_long`) : sa phrase CONTRE le champ, la saisie reste", async () => {
    await ouvrirLaCarte(eleves(OUVERT));
    // La phrase, le code et le champ que `formations._motif` écrit.
    const TROP_LONG = "Le motif dépasse 200 caractères. Résumez-le.";
    const envois = ecouter("achats/a-1/", () => refus(TROP_LONG, "motif_trop_long", "motif"));
    deplier();
    await within(carte()).findByRole("table");

    fireEvent.click(screen.getByRole("button", { name: "Retirer l'accès de “Eva Martin”" }));
    const motif = screen.getByLabelText("Motif du retrait");
    // Le champ est borné à la limite du serveur.
    expect(motif).toHaveAttribute("maxlength", "200");
    saisir(motif, "Un motif que le serveur refuse");
    fireEvent.click(screen.getByRole("button", { name: "Oui, retirer l'accès" }));

    await waitFor(() => expect(erreurContre(motif)).toBe(TROP_LONG));
    expect(envois).toHaveLength(1);
    expect(motif).toHaveAttribute("aria-invalid", "true");
    expect(motif).toHaveFocus();
    // La confirmation reste, la saisie aussi ; rien n'est dit ailleurs.
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(motif).toHaveValue("Un motif que le serveur refuse");
    expect(within(carte()).queryByRole("alert")).toBeNull();
    expect(ligne("Cabinet Eva").etat).toBe("Ouvert");
  });

  it("contre-épreuve : un refus qui ne désigne pas le motif (404 `achat_inconnu`) se dit en alerte", async () => {
    await ouvrirLaCarte(eleves(OUVERT));
    ecouter("achats/a-1/", () => refus("Cet achat n'existe pas.", "achat_inconnu", undefined, 404));
    deplier();
    await within(carte()).findByRole("table");

    fireEvent.click(screen.getByRole("button", { name: "Retirer l'accès de “Eva Martin”" }));
    const motif = screen.getByLabelText("Motif du retrait");
    saisir(motif, "Remboursement");
    fireEvent.click(screen.getByRole("button", { name: "Oui, retirer l'accès" }));

    expect(await within(carte()).findByRole("alert")).toHaveTextContent("Cet achat n'existe pas.");
    expect(erreurContre(motif)).toBe("");
  });

  it("une réponse 200 sans la ligne : l'écran ne déduit rien, il RELIT la liste", async () => {
    servirLaListe([SOCIETE]);
    // Les listes, avant puis après le retrait — telles que le serveur les tient.
    const achatApres = {
      ...ACHAT_OUVERT,
      revoque_le: "2026-11-20T12:00:00+00:00",
      motif_de_revocation: "Remboursement",
      acces: "retire",
    };
    const compte = { lectures: 0, achats: 0 };
    server.use(
      http.get(`${DASH}/formations/f-1/eleves/`, () => {
        compte.lectures += 1;
        return HttpResponse.json({
          eleves: [compte.lectures === 1 ? OUVERT : { ...OUVERT, acces: "retire" }],
          lecons_total: 2,
        });
      }),
      http.get(`${DASH}/formations/f-1/achats/`, () => {
        compte.achats += 1;
        return HttpResponse.json({ achats: [compte.achats === 1 ? ACHAT_OUVERT : achatApres] });
      }),
    );
    // Ni `{"achat": …}` ni rien de lisible : la ligne nue d'un autre contrat.
    ecouter("achats/a-1/", () => HttpResponse.json(achatApres));
    rendre();
    await ouvrir(SOCIETE.titre);
    deplier();
    await within(carte()).findByRole("table");
    expect(compte.lectures).toBe(1);

    fireEvent.click(screen.getByRole("button", { name: "Retirer l'accès de “Eva Martin”" }));
    saisir(screen.getByLabelText("Motif du retrait"), "Remboursement");
    fireEvent.click(screen.getByRole("button", { name: "Oui, retirer l'accès" }));

    // L'état affiché vient de la RELECTURE, pas d'une déduction.
    await waitFor(() =>
      expect(ligne("Cabinet Eva").texte).toContain("Accès retiré le 20 novembre 2026 — Remboursement"),
    );
    expect(ligne("Cabinet Eva").etat).toBe("Retiré");
    expect(compte.lectures).toBe(2);
    expect(within(carte()).getByRole("status")).toHaveTextContent(/la liste est relue/);
    expect(within(carte()).getByRole("status")).not.toHaveTextContent(/est retiré/);
  });

  it("le détail des retraits en panne : les lignes restent, « Retiré » se lit, et la panne se dit", async () => {
    servirLaListe([SOCIETE]);
    server.use(
      http.get(`${DASH}/formations/f-1/eleves/`, () => HttpResponse.json({ eleves: [RETIRE], lecons_total: 2 })),
      http.get(`${DASH}/formations/f-1/achats/`, () => new HttpResponse("panne", { status: 500 })),
    );
    rendre();
    await ouvrir(SOCIETE.titre);
    deplier();

    await within(carte()).findByRole("table");
    expect(ligne("Atelier Nord").etat).toBe("Retiré");
    expect(await within(carte()).findByText(/Impossible de charger le détail des accès retirés/)).toBeInTheDocument();
    // Aucune date ni aucun motif inventés.
    expect(ligne("Atelier Nord").texte).not.toContain("Accès retiré le");
  });

  it("après un changement d'accès, la fiche est relue : le nombre d'inscrits de la bande suit le serveur", async () => {
    // `nombre_d_achats` ne compte que les achats qui DONNENT accès
    // (`formations._nombre_d_achats`) : il baisse quand un accès est retiré.
    const liste = servirPuis(
      [uneFormation({ nombre_d_achats: 2 })],
      [uneFormation({ nombre_d_achats: 1 })],
    );
    servirLesEleves(eleves(OUVERT));
    ecouter("achats/a-1/", () =>
      HttpResponse.json({
        achat: {
          ...ACHAT_OUVERT,
          revoque_le: "2026-11-20T12:00:00+00:00",
          motif_de_revocation: "Remboursement",
          acces: "retire",
        },
      }),
    );
    rendre();
    await ouvrir(SOCIETE.titre);
    const bande = screen.getByRole("heading", { level: 2, name: SOCIETE.titre }).closest("section") as HTMLElement;
    expect((within(bande).getByText(/inscrit/i).textContent ?? "").replace(/\s/g, " ")).toBe("2 inscrits");
    deplier();
    await within(carte()).findByRole("table");
    expect(liste.lectures).toBe(1);

    fireEvent.click(screen.getByRole("button", { name: "Retirer l'accès de “Eva Martin”" }));
    saisir(screen.getByLabelText("Motif du retrait"), "Remboursement");
    fireEvent.click(screen.getByRole("button", { name: "Oui, retirer l'accès" }));

    await waitFor(() =>
      expect((within(bande).getByText(/inscrit/i).textContent ?? "").replace(/\s/g, " ")).toBe("1 inscrit"),
    );
    expect(liste.lectures).toBe(2);
  });
});

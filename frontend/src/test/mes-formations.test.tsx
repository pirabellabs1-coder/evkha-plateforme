/** « Mes formations » dans l'espace client : la liste, et la lecture d'une
 *  formation achetée.
 *
 * `GET /api/espace/formations/` (`vues_espace.mes_formations`) rend les
 * formations que l'organisation a ACHETÉES, avec le contenu de leurs leçons.
 * La charge servie ici a la forme que cette vue écrit, clé par clé.
 *
 * Ce que ce fichier verrouille :
 *
 * 1. la liste : chaque formation, sa date d'achat, ses modules et ses leçons
 *    comptés sur le programme reçu ; l'appel part sous le jeton ;
 * 2. une liste REÇUE et vide accueille et mène aux formations ; une panne —
 *    500, ou une réponse 200 sans la liste — n'est JAMAIS dite « aucune
 *    formation » ;
 * 3. une formation ouverte : son programme, la leçon courante annoncée
 *    (`aria-current`), une seule à la fois ;
 * 4. la vidéo : lecteur intégré pour YouTube et Vimeo (adresse RECONSTRUITE,
 *    hôte comparé exactement), lecteur du navigateur pour un fichier, lien
 *    pour un autre site, rien pour ce qui n'est pas `https://` ;
 * 5. le texte : rendu comme du texte — une balise saisie s'affiche, elle ne
 *    devient pas un élément ;
 * 6. le document : le lien affiché n'est pas suivi ; au clic la liste est
 *    RELUE au serveur et c'est le lien frais qui s'ouvre ;
 * 7. précédente / suivante, le focus au titre de la leçon, la dernière leçon
 *    retenue dans ce navigateur — et un stockage refusé qui n'empêche rien ;
 * 8. un slug qui n'est pas dans la réponse : dit, avec ses portes de sortie —
 *    et distinct d'une panne ;
 * 9. la progression : la barre et « X leçons sur Y terminées », telles que le
 *    serveur les rend — et rien quand il n'en dit rien ; le dernier jour
 *    d'accès ;
 * 10. la trace d'une leçon : `{ouverte: true}` une fois à l'ouverture ;
 *     « Marquer comme terminée » et son annulation ; la barre et la coche
 *     suivent la RÉPONSE ; une trace ratée se dit sans bloquer la lecture ;
 * 11. un accès échu : la formation reste, sans programme, avec sa date de
 *     fin, son rachat et le contact ;
 * 12. les séances en présentiel : le formulaire de signature seulement quand
 *     le serveur dit la séance `signable`, ses autres états, la signature, et
 *     chaque refus affiché avec la phrase du serveur.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { hoteConnuDeLApi, jeton } from "../espace/api";
import { lecteurDe, lienDeDocument } from "../espace/lecteurVideo";
import { server } from "./server";

/** Le slug que la route « porte », changé par chaque test. */
const parametres = { slug: "creer-sa-micro-entreprise" };

vi.mock("@tanstack/react-router", () => ({
  useParams: () => parametres,
  useNavigate: () => () => undefined,
  Link: ({
    to,
    params,
    children,
    className,
    "aria-label": nom,
  }: {
    to: string;
    params?: Record<string, string>;
    children: React.ReactNode;
    className?: string;
    "aria-label"?: string;
  }) => (
    <a
      href={Object.entries(params ?? {}).reduce(
        (adresse, [cle, valeur]) => adresse.replace(`$${cle}`, valeur),
        to,
      )}
      className={className}
      aria-label={nom}
    >
      {children}
    </a>
  ),
}));

// Importés APRÈS le simulacre du routeur.
const { FormationSuivie, MesFormations } = await import("../espace/pages/MesFormations");

// Lue AVANT tout remplacement de `window.location`.
const ORIGINE = window.location.origin;
const FORMATIONS_API = `${ORIGINE}/api/espace/formations/`;

const INSECABLE = String.fromCharCode(0xa0);

/** Le texte, insécables ramenées à des espaces. */
function texteDe(element: Element | null): string {
  return (element?.textContent ?? "").split(INSECABLE).join(" ");
}

// ── La charge du serveur ────────────────────────────────────────────────────

const SLUG = "creer-sa-micro-entreprise";

function lecon(id: string, rang: number, surcharges: Record<string, unknown>) {
  return {
    id,
    rang,
    titre: `Leçon ${id}`,
    nature: "texte",
    duree_minutes: 0,
    adresse_video: "",
    texte: "",
    fichier: "",
    fichier_nom: "",
    ...surcharges,
  };
}

const YOUTUBE = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s";
const VIMEO = "https://vimeo.com/76979871";

/** Le texte d'une leçon, tel qu'une gérante peut le saisir : deux paragraphes,
 *  un retour à la ligne simple, et une balise — qui doit rester du texte. */
const TEXTE_SAISI =
  "Premier paragraphe de la leçon.\nSa seconde ligne.\n\n<script>window.pirate = true</script> <b>gras</b> & <img src=x onerror=alert(1)>";

const LIEN_AFFICHE = "https://api.exemple/media/formations/support.pdf?expire=100&signature=ancienne";
const LIEN_FRAIS = "https://api.exemple/media/formations/support.pdf?expire=999&signature=fraiche";

function laFormation(lienDuDocument: string) {
  return {
    slug: SLUG,
    titre: "Créer sa micro-entreprise d'essai",
    sous_titre: "Le parcours complet",
    accroche: "",
    image: "",
    duree_heures: 19,
    heures_de_coaching: 3,
    achetee_le: "2026-11-03T12:00:00+00:00",
    modules: [
      {
        rang: 1,
        titre: "Comprendre le régime",
        description: "Les bases, sans jargon.",
        lecons: [
          lecon("l-1", 1, { titre: "Bienvenue", nature: "video", duree_minutes: 12, adresse_video: YOUTUBE }),
          lecon("l-2", 2, { titre: "Le guide à lire", nature: "texte", duree_minutes: 75, texte: TEXTE_SAISI }),
          lecon("l-3", 3, {
            titre: "Le modèle de statuts",
            nature: "document",
            fichier: lienDuDocument,
            fichier_nom: "support.pdf",
          }),
        ],
      },
      {
        rang: 2,
        titre: "Passer à l'action",
        description: "",
        lecons: [
          lecon("l-4", 1, { titre: "Valider ses acquis", nature: "quiz" }),
          lecon("l-5", 2, { titre: "Le mot de la fin", nature: "video", adresse_video: VIMEO }),
        ],
      },
    ],
  };
}

const SANS_LECON = {
  slug: "methode-pop",
  titre: "Méthode P.O.P d'essai",
  sous_titre: "",
  accroche: "",
  image: "https://api.exemple/media/formations/pop.webp",
  duree_heures: 11,
  heures_de_coaching: 0,
  achetee_le: "2026-10-12T12:00:00+00:00",
  modules: [],
};

/** Ce que le serveur a reçu : une ligne par lecture de la liste. */
let lectures: (string | null)[];

/** Les traces de lecture reçues (`POST formations/lecons/<id>/`). */
const LECONS_API = `${ORIGINE}/api/espace/formations/lecons/:id/`;
let traces: { lecon: string; corps: unknown; jeton: string | null }[];

type Reponse = () => Response | Promise<Response>;

/** Sert la liste. Chaque lecture est notée ; `suites` sert les lectures
 *  d'après la première, dans l'ordre. */
function servir(premiere: Reponse, ...suites: Reponse[]) {
  server.use(
    http.get(FORMATIONS_API, ({ request }) => {
      lectures.push(request.headers.get("Authorization"));
      const suite = suites[lectures.length - 2];
      return lectures.length === 1 || suite === undefined ? premiere() : suite();
    }),
  );
}

const liste = (...formations: object[]): Reponse => () => HttpResponse.json({ formations });
const panne: Reponse = () => new HttpResponse("panne", { status: 500 });

function monter(ecran: React.ReactElement) {
  const requetes = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={requetes}>{ecran}</QueryClientProvider>);
}

async function ouvrirLaFormation(reponse: Reponse = liste(laFormation(LIEN_AFFICHE)), ...suites: Reponse[]) {
  parametres.slug = SLUG;
  servir(reponse, ...suites);
  const rendu = monter(<FormationSuivie />);
  await screen.findByRole("navigation", { name: "Programme" });
  return rendu;
}

/** Le bouton d'une leçon, dans le programme. */
function ligne(titre: string): HTMLElement {
  return within(screen.getByRole("navigation", { name: "Programme" })).getByRole("button", {
    name: new RegExp(titre),
  });
}

function courantes(): string[] {
  return Array.from(document.querySelectorAll('[aria-current="true"]')).map(
    (element) => element.querySelector(".frs-lecon-titre")?.textContent ?? "",
  );
}

function titreDeLecon(): HTMLElement {
  const trouve = document.querySelector<HTMLElement>(".frs-lecon-titre-ouvert");
  if (!trouve) throw new Error("aucune leçon ouverte");
  return trouve;
}

// ── L'adresse du navigateur ─────────────────────────────────────────────────
// jsdom ne navigue pas : on pose une adresse qui ENREGISTRE les départs.

const adresseDOrigine = Object.getOwnPropertyDescriptor(window, "location");
let departs: string[] = [];

function poserLAdresse(chemin: string) {
  departs = [];
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      origin: ORIGINE,
      pathname: chemin,
      search: "",
      get href() {
        return `${ORIGINE}${chemin}`;
      },
      set href(cible: string) {
        departs.push(cible);
      },
    },
  });
}

beforeEach(() => {
  localStorage.clear();
  jeton.ecrire("jeton-de-session");
  lectures = [];
  departs = [];
  traces = [];
  // Depuis le 20/11/2026, ouvrir une leçon envoie sa trace au serveur. Par
  // défaut il l'accepte, sans rien dire de la progression : les tests qui la
  // regardent posent leur propre réponse.
  server.use(
    http.post(LECONS_API, async ({ request, params }) => {
      traces.push({
        lecon: String(params.id),
        corps: await request.json(),
        jeton: request.headers.get("Authorization"),
      });
      return HttpResponse.json({
        lecon: {
          id: String(params.id),
          terminee: false,
          terminee_le: null,
          premiere_ouverture_le: "2026-11-20T09:00:00+00:00",
          derniere_ouverture_le: "2026-11-20T09:00:00+00:00",
        },
        formation: "une-autre-formation",
        progression: { terminees: 0, total: 0, pourcent: null },
      });
    }),
  );
});

afterEach(() => {
  cleanup();
  if (adresseDOrigine) Object.defineProperty(window, "location", adresseDOrigine);
  vi.restoreAllMocks();
});

// ── 1 et 2. La liste ────────────────────────────────────────────────────────

describe("la liste de mes formations", () => {
  it("montre chaque formation achetée : titre, date d'achat, modules et leçons comptés", async () => {
    servir(liste(laFormation(LIEN_AFFICHE), SANS_LECON));
    monter(<MesFormations />);

    const titre = await screen.findByRole("heading", { level: 2, name: "Créer sa micro-entreprise d'essai" });
    const carte = titre.closest("li") as HTMLElement;
    expect(texteDe(carte)).toContain("Achetée le 3 novembre 2026");
    expect(texteDe(carte)).toContain("2 modules · 5 leçons");
    expect(within(carte).getByRole("link", { name: /Ouvrir la formation/ })).toHaveAttribute(
      "href",
      `/espace/formations/${SLUG}`,
    );

    const seconde = screen.getByRole("heading", { level: 2, name: "Méthode P.O.P d'essai" }).closest("li") as HTMLElement;
    expect(texteDe(seconde)).toContain("Achetée le 12 octobre 2026");
    // Zéro s'accorde au singulier, et se dit : ce n'est pas un chiffre caché.
    expect(texteDe(seconde)).toContain("0 module · 0 leçon");
    expect(seconde.querySelector("img")).toHaveAttribute("src", SANS_LECON.image);
    expect(seconde.querySelector("img")).toHaveAttribute("alt", "");

    // Les titres : le `h1` « Mes formations » est celui de la coquille, et la
    // carte ne le REDIT pas. Une formation par `h2`, aucun niveau sauté.
    expect(screen.queryByRole("heading", { name: "Mes formations" })).toBeNull();
    expect(screen.queryByRole("heading", { level: 1 })).toBeNull();
    expect(screen.getAllByRole("heading").map((element) => element.tagName)).toEqual(["H2", "H2"]);
    // La phrase d'introduction, elle, est restée.
    expect(screen.getByText("Accessibles à tout moment, à votre rythme.")).toBeInTheDocument();
    // Un appel, sous le jeton du compte.
    expect(lectures).toEqual(["Bearer jeton-de-session"]);
    expect(screen.queryByText(/pas encore de formation/)).toBeNull();
  });

  it("liste reçue et vide : un accueil, et un lien vers les formations", async () => {
    servir(liste());
    monter(<MesFormations />);

    expect(await screen.findByText("Vous n'avez pas encore de formation")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Découvrir les formations" })).toHaveAttribute("href", "/formations");
    expect(screen.queryByText(/Impossible de charger/)).toBeNull();
    // Sans formation, la phrase d'introduction n'a rien à introduire.
    expect(screen.queryByText("Accessibles à tout moment, à votre rythme.")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Mes formations" })).toBeNull();
  });

  for (const [nom, reponse] of [
    ["500", panne],
    ["200 sans la liste", () => HttpResponse.json({})],
    ["200 avec une liste qui n'en est pas une", () => HttpResponse.json({ formations: "aucune" })],
    ["403 sans organisation", () => HttpResponse.json({ error: "Aucune organisation.", code: "sans_organisation" }, { status: 403 })],
  ] as [string, Reponse][]) {
    it(`panne (${nom}) : dite comme une panne, jamais « pas encore de formation »`, async () => {
      servir(reponse);
      monter(<MesFormations />);

      expect(await screen.findByText(/Impossible de charger vos formations/)).toBeInTheDocument();
      expect(screen.queryByText(/pas encore de formation/)).toBeNull();
      expect(screen.queryByRole("link", { name: "Découvrir les formations" })).toBeNull();
    });
  }
});

// ── 3. Une formation ouverte ────────────────────────────────────────────────

describe("une formation ouverte", () => {
  it("montre le programme, et annonce la leçon courante — une seule", async () => {
    await ouvrirLaFormation();

    expect(screen.getByRole("heading", { level: 2, name: "Créer sa micro-entreprise d'essai" })).toBeInTheDocument();
    const programme = screen.getByRole("navigation", { name: "Programme" });
    expect(within(programme).getAllByRole("button")).toHaveLength(5);
    expect(texteDe(programme)).toContain("Module 1");
    expect(texteDe(programme)).toContain("Comprendre le régime");
    expect(texteDe(programme)).toContain("Les bases, sans jargon.");
    // Nature et durée de chaque leçon.
    expect(texteDe(ligne("Bienvenue"))).toContain("Vidéo · 12 min");
    expect(texteDe(ligne("Le guide à lire"))).toContain("Texte · 1 h 15");
    // Une durée nulle ne s'affiche pas.
    expect(texteDe(ligne("Le modèle de statuts"))).not.toMatch(/\d/);

    // À l'ouverture : la première leçon, et le focus n'a pas bougé.
    expect(courantes()).toEqual(["Bienvenue"]);
    expect(titreDeLecon()).toHaveTextContent("Bienvenue");
    expect(titreDeLecon().tagName).toBe("H3");
    expect(document.activeElement).not.toBe(titreDeLecon());
    // Le retour à la liste.
    expect(screen.getByRole("link", { name: /Mes formations/ })).toHaveAttribute("href", "/espace/formations");
    expect(lectures).toHaveLength(1);
  });

  it("choisir une leçon la rend courante et porte le focus sur son titre", async () => {
    await ouvrirLaFormation();

    fireEvent.click(ligne("Valider ses acquis"));

    await waitFor(() => expect(courantes()).toEqual(["Valider ses acquis"]));
    expect(titreDeLecon()).toHaveTextContent("Valider ses acquis");
    expect(document.activeElement).toBe(titreDeLecon());
    expect(screen.getByText("Ce quiz sera bientôt disponible.")).toBeInTheDocument();
  });

  it("précédente / suivante parcourent le programme d'un module à l'autre, bornes comprises", async () => {
    await ouvrirLaFormation();
    const precedente = screen.getByRole("button", { name: /Leçon précédente/ });
    const suivante = screen.getByRole("button", { name: /Leçon suivante/ });

    expect(precedente).toBeDisabled();
    expect(suivante).not.toBeDisabled();

    const ordre = ["Le guide à lire", "Le modèle de statuts", "Valider ses acquis", "Le mot de la fin"];
    for (const attendue of ordre) {
      fireEvent.click(suivante);
      await waitFor(() => expect(courantes()).toEqual([attendue]));
      expect(document.activeElement).toBe(titreDeLecon());
    }
    expect(suivante).toBeDisabled();
    expect(precedente).not.toBeDisabled();

    fireEvent.click(precedente);
    await waitFor(() => expect(courantes()).toEqual(["Valider ses acquis"]));
  });

  it("la dernière leçon ouverte est retenue dans ce navigateur, et rien d'autre", async () => {
    const premier = await ouvrirLaFormation();
    fireEvent.click(ligne("Le guide à lire"));
    await waitFor(() => expect(courantes()).toEqual(["Le guide à lire"]));
    premier.unmount();

    // Une seule clé de plus que le jeton : pas de progression inventée.
    const cles = Object.keys(localStorage).filter((cle) => cle !== "evkha_espace_jeton");
    expect(cles).toHaveLength(1);
    expect(cles[0]).toContain(SLUG);
    expect(localStorage.getItem(cles[0])).toBe("l-2");

    // Rouverte : elle reprend là.
    lectures = [];
    await ouvrirLaFormation();
    expect(courantes()).toEqual(["Le guide à lire"]);
  });

  it("une leçon retenue qui n'existe plus : on repart de la première", async () => {
    localStorage.setItem(`evkha_formation_derniere_lecon:${SLUG}`, "lecon-retiree");
    await ouvrirLaFormation();
    expect(courantes()).toEqual(["Bienvenue"]);
  });

  it("un stockage refusé n'empêche ni d'ouvrir ni de changer de leçon", async () => {
    await ouvrirLaFormation();
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("quota", "QuotaExceededError");
    });

    // Une erreur levée dans un geste ne remonte pas à l'appelant : React la
    // remet à la fenêtre. C'est là qu'on l'attend.
    const erreurs: string[] = [];
    const noter = (evenement: ErrorEvent) => {
      erreurs.push(evenement.message);
      evenement.preventDefault();
    };
    window.addEventListener("error", noter);
    try {
      fireEvent.click(ligne("Le mot de la fin"));
      await waitFor(() => expect(courantes()).toEqual(["Le mot de la fin"]));
      expect(document.activeElement).toBe(titreDeLecon());
    } finally {
      window.removeEventListener("error", noter);
    }
    expect(erreurs).toEqual([]);
  });

  it("un stockage illisible n'empêche pas d'ouvrir la formation", async () => {
    const lire = Storage.prototype.getItem;
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(function (this: Storage, cle: string) {
      // Le jeton de session, lui, se lit : seul le souvenir de la leçon échoue.
      if (cle.startsWith("evkha_formation")) throw new DOMException("refusé", "SecurityError");
      return lire.call(this, cle);
    });
    await ouvrirLaFormation();
    expect(courantes()).toEqual(["Bienvenue"]);
  });

  it("une formation sans leçon le dit, sans programme vide ni bouton mort", async () => {
    parametres.slug = "methode-pop";
    servir(liste(laFormation(LIEN_AFFICHE), SANS_LECON));
    monter(<FormationSuivie />);

    expect(await screen.findByText("Le programme arrive")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Programme" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Leçon suivante/ })).toBeNull();
  });
});

// ── 4. La vidéo ─────────────────────────────────────────────────────────────

describe("la vidéo d'une leçon", () => {
  it("YouTube : un lecteur intégré, à une adresse reconstruite, sans rien décaler", async () => {
    await ouvrirLaFormation();

    const cadre = document.querySelector("iframe") as HTMLIFrameElement;
    expect(cadre).not.toBeNull();
    // L'adresse est RECONSTRUITE sur le seul identifiant : ni le `t=42s` ni
    // rien d'autre de l'adresse saisie n'y entre.
    expect(cadre).toHaveAttribute("src", "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ");
    expect((cadre.getAttribute("title") ?? "").split(INSECABLE).join(" ")).toBe(
      "Vidéo de la leçon « Bienvenue » (YouTube)",
    );
    expect(cadre).toHaveAttribute("loading", "lazy");
    expect(cadre).toHaveAttribute("referrerpolicy", "strict-origin-when-cross-origin");
    expect(cadre).toHaveAttribute("allow", "fullscreen; picture-in-picture");
    // Le cadre est BRIDÉ : les scripts du lecteur, son origine, la diffusion
    // sur un autre écran — et rien de plus. Aucune permission qui laisserait
    // le lecteur ouvrir une fenêtre, envoyer un formulaire ou faire naviguer
    // notre page.
    const permis = (cadre.getAttribute("sandbox") ?? "").split(/\s+/).filter(Boolean).sort();
    expect(permis).toEqual(["allow-presentation", "allow-same-origin", "allow-scripts"]);
    // Le plein écran reste demandable : il ne dépend pas de `sandbox`.
    expect(cadre).toHaveAttribute("allowfullscreen");
    expect(cadre.getAttribute("allow")).toMatch(/(^|;\s*)fullscreen(;|$)/);
    // Le cadre qui réserve le rapport 16/9.
    expect(cadre.parentElement).toHaveClass("frs-video");
    expect(document.querySelector("video")).toBeNull();
  });

  it("Vimeo : son lecteur, à une adresse reconstruite", async () => {
    await ouvrirLaFormation();
    fireEvent.click(ligne("Le mot de la fin"));

    await waitFor(() =>
      expect(document.querySelector("iframe")).toHaveAttribute("src", "https://player.vimeo.com/video/76979871"),
    );
    expect(document.querySelector("iframe")?.getAttribute("title")).toMatch(/Vimeo/);
    // Bridé comme celui de YouTube : c'est le même cadre.
    expect(document.querySelector("iframe")).toHaveAttribute(
      "sandbox",
      "allow-scripts allow-same-origin allow-presentation",
    );
  });

  /** Une formation d'une seule leçon vidéo, à l'adresse donnée. */
  async function avecLaVideo(adresse: string) {
    const formation = laFormation(LIEN_AFFICHE);
    formation.modules = [
      { ...formation.modules[0], lecons: [lecon("l-1", 1, { titre: "Bienvenue", nature: "video", adresse_video: adresse })] },
    ];
    return ouvrirLaFormation(liste(formation));
  }

  it("un fichier vidéo direct : le lecteur du navigateur", async () => {
    await avecLaVideo("https://media.exemple.fr/cours/bienvenue.mp4?jeton=abc");

    const video = document.querySelector("video") as HTMLVideoElement;
    expect(video).toHaveAttribute("src", "https://media.exemple.fr/cours/bienvenue.mp4?jeton=abc");
    expect(video).toHaveAttribute("controls");
    expect(video).toHaveAttribute("preload", "metadata");
    expect(video.parentElement).toHaveClass("frs-video");
    expect(document.querySelector("iframe")).toBeNull();
  });

  it("un autre site : ni cadre ni lecteur, un bouton « Ouvrir la vidéo » dans un nouvel onglet", async () => {
    await avecLaVideo("https://videos.exemple.fr/regarder/42");

    const lien = screen.getByRole("link", { name: /Ouvrir la vidéo/ });
    expect(lien).toHaveAttribute("href", "https://videos.exemple.fr/regarder/42");
    expect(lien).toHaveAttribute("target", "_blank");
    expect(lien).toHaveAttribute("rel", "noopener noreferrer");
    expect(document.querySelector("iframe, video")).toBeNull();
  });

  for (const adresse of [
    "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "//www.youtube.com/watch?v=dQw4w9WgXcQ",
    "pas une adresse",
    "",
  ]) {
    it(`pas en https (« ${adresse} ») : rien n'est rendu, la page le dit`, async () => {
      await avecLaVideo(adresse);

      expect(screen.getByText(/La vidéo de cette leçon n'est pas disponible/)).toBeInTheDocument();
      expect(document.querySelector("iframe, video")).toBeNull();
      expect(screen.queryByRole("link", { name: /Ouvrir la vidéo/ })).toBeNull();
      if (adresse !== "") expect(document.body.innerHTML).not.toContain(adresse.replace(/</g, "&lt;"));
    });
  }

  it("la lecture d'une adresse, cas par cas : liste fermée, hôte comparé exactement", () => {
    const YT = { genre: "integre", hebergeur: "YouTube", adresse: "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ" };
    for (const adresse of [
      "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      "https://youtube.com/watch?v=dQw4w9WgXcQ&list=PL123",
      "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
      "https://youtu.be/dQw4w9WgXcQ?si=abc",
      "https://www.youtube.com/embed/dQw4w9WgXcQ",
      "https://www.youtube.com/shorts/dQw4w9WgXcQ",
      "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
      "  https://WWW.YouTube.com/watch?v=dQw4w9WgXcQ  ",
    ]) {
      expect(lecteurDe(adresse), adresse).toEqual(YT);
    }
    expect(lecteurDe("https://vimeo.com/76979871")).toEqual({
      genre: "integre",
      hebergeur: "Vimeo",
      adresse: "https://player.vimeo.com/video/76979871",
    });
    // Une vidéo non répertoriée garde sa clé.
    expect(lecteurDe("https://vimeo.com/76979871/abcdef0123")).toEqual({
      genre: "integre",
      hebergeur: "Vimeo",
      adresse: "https://player.vimeo.com/video/76979871?h=abcdef0123",
    });
    expect(lecteurDe("https://player.vimeo.com/video/76979871?h=abcdef0123")).toEqual({
      genre: "integre",
      hebergeur: "Vimeo",
      adresse: "https://player.vimeo.com/video/76979871?h=abcdef0123",
    });

    // Ce qui RESSEMBLE à un hébergeur connu n'en est pas un : un lien, jamais
    // un cadre.
    for (const adresse of [
      "https://www.youtube.com.exemple.fr/watch?v=dQw4w9WgXcQ",
      "https://youtube.com@exemple.fr/watch?v=dQw4w9WgXcQ",
      "https://exemple.fr/www.youtube.com/watch?v=dQw4w9WgXcQ",
      "https://pasyoutube.com/watch?v=dQw4w9WgXcQ",
      "https://www.youtube.com:8443/watch?v=dQw4w9WgXcQ",
      "https://vimeo.com.exemple.fr/76979871",
      // Un identifiant qui n'en est pas un n'entre pas dans une adresse.
      "https://www.youtube.com/watch?v=dQw4w9WgXcQ%22onload%3D",
      "https://www.youtube.com/watch?v=court",
      "https://www.youtube.com/playlist?list=PL123",
      "https://vimeo.com/channels/staffpicks/76979871",
      "https://vimeo.com/76979871/pas-une-cle",
    ]) {
      expect(lecteurDe(adresse).genre, adresse).toBe("lien");
    }

    expect(lecteurDe("https://media.exemple.fr/a/b.webm")).toEqual({
      genre: "fichier",
      adresse: "https://media.exemple.fr/a/b.webm",
    });
    expect(lecteurDe("https://media.exemple.fr/a/b.MP4").genre).toBe("fichier");
    // L'extension se lit dans le CHEMIN, pas dans un paramètre.
    expect(lecteurDe("https://exemple.fr/page?fichier=b.mp4").genre).toBe("lien");
    expect(lecteurDe("http://media.exemple.fr/a/b.mp4")).toEqual({ genre: "aucun" });
    for (const rien of [null, undefined, 42, "", "   ", "ftp://exemple.fr/a.mp4"]) {
      expect(lecteurDe(rien), String(rien)).toEqual({ genre: "aucun" });
    }
  });
});

// ── 5. Le texte ─────────────────────────────────────────────────────────────

describe("le texte d'une leçon", () => {
  it("une balise saisie s'affiche comme du texte : aucun élément n'en naît", async () => {
    await ouvrirLaFormation();
    fireEvent.click(ligne("Le guide à lire"));
    await waitFor(() => expect(courantes()).toEqual(["Le guide à lire"]));

    const texte = document.querySelector(".frs-texte") as HTMLElement;
    const paragraphes = Array.from(texte.querySelectorAll("p"));
    // Une ligne vide sépare deux paragraphes ; un retour simple reste DANS le
    // sien (la feuille le rend par `white-space: pre-line`).
    expect(paragraphes).toHaveLength(2);
    expect(paragraphes[0].textContent).toBe("Premier paragraphe de la leçon.\nSa seconde ligne.");
    expect(paragraphes[1].textContent).toBe(
      "<script>window.pirate = true</script> <b>gras</b> & <img src=x onerror=alert(1)>",
    );
    // Rien de ce qui a été saisi n'est devenu un élément.
    expect(texte.querySelector("script, b, img")).toBeNull();
    expect(texte.querySelectorAll("*")).toHaveLength(2);
    expect((window as unknown as { pirate?: boolean }).pirate).toBeUndefined();
  });

  it("la page n'injecte aucun HTML", () => {
    const source = readFileSync(join(process.cwd(), "src", "espace", "pages", "MesFormations.tsx"), "utf-8");
    const code = source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
    // Règle 1 : le fichier est bien celui de l'écran.
    expect(code).toContain("export function FormationSuivie");
    expect(code).not.toMatch(/dangerouslySetInnerHTML|innerHTML|insertAdjacentHTML/);
  });
});

// ── 6. Le document ──────────────────────────────────────────────────────────

describe("le document d'une leçon", () => {
  async function surLeDocument(...suites: Reponse[]) {
    poserLAdresse(`/espace/formations/${SLUG}`);
    await ouvrirLaFormation(liste(laFormation(LIEN_AFFICHE)), ...suites);
    fireEvent.click(ligne("Le modèle de statuts"));
    return screen.findByRole("button", { name: "Télécharger support.pdf" });
  }

  it("au clic, la liste est relue au serveur et c'est le lien FRAIS qui s'ouvre", async () => {
    const bouton = await surLeDocument(liste(laFormation(LIEN_FRAIS)));
    // Avant le clic : une seule lecture, et le lien reçu n'est nulle part
    // dans la page — ni en lien, ni en attribut.
    expect(lectures).toHaveLength(1);
    expect(document.body.innerHTML).not.toContain("support.pdf?");
    expect(departs).toEqual([]);

    fireEvent.click(bouton);

    await waitFor(() => expect(departs).toEqual([LIEN_FRAIS]));
    expect(lectures).toEqual(["Bearer jeton-de-session", "Bearer jeton-de-session"]);
    // Le lien d'il y a une heure n'a pas servi.
    expect(departs).not.toContain(LIEN_AFFICHE);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("deux clics du même geste : une seule relecture, un seul départ", async () => {
    const bouton = await surLeDocument(liste(laFormation(LIEN_FRAIS)));

    // Dans UN seul lot de React : entre deux fireEvent, le bouton serait
    // redessiné désactivé, et le garde-fou de l'écran ne serait pas éprouvé.
    act(() => {
      bouton.click();
      bouton.click();
    });

    await waitFor(() => expect(departs).toEqual([LIEN_FRAIS]));
    expect(lectures).toHaveLength(2);
  });

  it("si la relecture échoue : une alerte, aucun départ — surtout pas vers l'ancien lien", async () => {
    const bouton = await surLeDocument(panne);

    fireEvent.click(bouton);

    expect(await screen.findByRole("alert")).toHaveTextContent(/n'a pas pu être préparé/);
    expect(departs).toEqual([]);
    // On peut réessayer.
    expect(screen.getByRole("button", { name: "Télécharger support.pdf" })).not.toBeDisabled();
  });

  it("si le document n'est plus là à la relecture : dit, sans départ", async () => {
    const bouton = await surLeDocument(liste(laFormation("")));

    fireEvent.click(bouton);

    // La liste relue remplace celle de l'écran : la leçon n'a plus de
    // document, et le dit ; le bouton a disparu avec lui.
    await waitFor(() =>
      expect(screen.getByText(/Le document de cette leçon n'est pas disponible/)).toBeInTheDocument(),
    );
    expect(screen.queryByRole("button", { name: /Télécharger/ })).toBeNull();
    expect(lectures).toHaveLength(2);
    expect(departs).toEqual([]);
  });

  it("un lien qui n'est pas une adresse web n'est jamais suivi", async () => {
    const bouton = await surLeDocument(liste(laFormation("javascript:alert(1)")));

    fireEvent.click(bouton);

    await waitFor(() => expect(lectures).toHaveLength(2));
    await screen.findByText(/n'est plus disponible/);
    expect(departs).toEqual([]);

    expect(lienDeDocument(LIEN_FRAIS)).toBe(LIEN_FRAIS);
    for (const refuse of ["javascript:alert(1)", "/media/formations/support.pdf", "", null, undefined]) {
      expect(lienDeDocument(refuse), String(refuse)).toBeNull();
    }
  });

  // 20/11/2026 — le lien vient de NOTRE serveur, ou il n'est pas suivi.

  it("un lien en http:// hors du poste de développement n'est jamais suivi", async () => {
    const enClair = LIEN_FRAIS.replace("https://", "http://");
    const bouton = await surLeDocument(liste(laFormation(enClair)));

    fireEvent.click(bouton);

    await waitFor(() => expect(lectures).toHaveLength(2));
    // L'alerte déjà prévue, et aucun départ.
    expect(await screen.findByRole("alert")).toHaveTextContent(/n'est plus disponible/);
    expect(departs).toEqual([]);
  });

  it("contre-épreuve : sur le poste de développement, le lien en http:// est suivi", async () => {
    const duPoste = "http://localhost:8000/media/formations/support.pdf?expire=999&signature=fraiche";
    const bouton = await surLeDocument(liste(laFormation(duPoste)));

    fireEvent.click(bouton);

    await waitFor(() => expect(departs).toEqual([duPoste]));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("le schéma, cas par cas : https partout, http seulement sur le poste, jamais d'identifiants", () => {
    const chemin = "/media/formations/support.pdf?expire=999&signature=fraiche";
    for (const suivi of [
      `https://api.exemple${chemin}`,
      `http://localhost:8000${chemin}`,
      `http://127.0.0.1:8000${chemin}`,
      `https://localhost${chemin}`,
    ]) {
      // Rendu TEL QUE REÇU : le lien est signé.
      expect(lienDeDocument(suivi, null), suivi).toBe(suivi);
    }
    for (const refuse of [
      `http://api.exemple${chemin}`,
      // Ce qui RESSEMBLE au poste n'est pas le poste.
      `http://localhost.exemple.fr${chemin}`,
      `http://127.0.0.1.exemple.fr${chemin}`,
      `http://localhost@exemple.fr${chemin}`,
      `https://api.exemple@ailleurs.exemple${chemin}`,
      `https://quelquun:secret@api.exemple${chemin}`,
      `//api.exemple${chemin}`,
      `ftp://api.exemple${chemin}`,
      `data:application/pdf;base64,JVBERi0=`,
    ]) {
      expect(lienDeDocument(refuse, null), refuse).toBeNull();
    }
  });

  it("l'hôte, quand le client connaît celui de l'API : exactement lui, rien qui lui ressemble", () => {
    const chemin = "/media/formations/support.pdf?expire=999&signature=fraiche";
    // L'hôte de l'API, tel que `hoteConnuDeLApi` le rend.
    const API = "api.exemple";

    expect(lienDeDocument(`https://api.exemple${chemin}`, API)).toBe(`https://api.exemple${chemin}`);
    // Le port n'est pas comparé (le relais de Vite, en développement).
    expect(lienDeDocument(`https://api.exemple:8443${chemin}`, API)).toBe(`https://api.exemple:8443${chemin}`);
    expect(lienDeDocument(`http://localhost:8000${chemin}`, "localhost")).toBe(`http://localhost:8000${chemin}`);

    for (const refuse of [
      `https://api.exemple.evil.tld${chemin}`,
      `https://pasapi.exemple${chemin}`,
      `https://exemple${chemin}`,
      `https://ailleurs.exemple/api.exemple${chemin}`,
      `https://api.exemple@ailleurs.exemple${chemin}`,
      // Le poste de développement n'est pas l'API d'un client construit pour
      // un autre hôte.
      `http://localhost:8000${chemin}`,
    ]) {
      expect(lienDeDocument(refuse, API), refuse).toBeNull();
    }
  });

  it("contre-épreuve : sans hôte connu (API jointe par un relais), l'hôte n'est pas comparé — et l'écran est dans ce cas", () => {
    const ailleurs = "https://fichiers.exemple/media/formations/support.pdf?expire=999&signature=fraiche";
    expect(lienDeDocument(ailleurs, null)).toBe(ailleurs);
    expect(lienDeDocument(ailleurs, "api.exemple")).toBeNull();
    // Ce jeu d'essai tourne sans `VITE_API_URL` : le client ne connaît pas
    // l'hôte de l'API, et le dit.
    expect(hoteConnuDeLApi()).toBeNull();
    expect(lienDeDocument(ailleurs)).toBe(ailleurs);
  });
});

// ── 8. Un slug inconnu ──────────────────────────────────────────────────────

describe("une formation qui n'est pas dans la réponse", () => {
  it("slug inconnu : dit, avec le retour à la liste et aux formations", async () => {
    parametres.slug = "formation-d-un-autre";
    servir(liste(laFormation(LIEN_AFFICHE)));
    monter(<FormationSuivie />);

    expect(await screen.findByText("Cette formation n'est pas dans votre espace")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Voir mes formations" })).toHaveAttribute("href", "/espace/formations");
    expect(screen.getByRole("link", { name: "Découvrir les formations" })).toHaveAttribute("href", "/formations");
    // Rien d'une AUTRE formation n'est montré à sa place.
    expect(screen.queryByRole("navigation", { name: "Programme" })).toBeNull();
    expect(screen.queryByText("Créer sa micro-entreprise d'essai")).toBeNull();
    expect(screen.queryByText(/Impossible de charger/)).toBeNull();
  });

  it("contre-épreuve : une panne n'est pas « pas dans votre espace »", async () => {
    parametres.slug = SLUG;
    servir(panne);
    monter(<FormationSuivie />);

    expect(await screen.findByText(/Impossible de charger votre formation/)).toBeInTheDocument();
    expect(screen.queryByText(/n'est pas dans votre espace/)).toBeNull();
    expect(screen.getByRole("link", { name: /Mes formations/ })).toHaveAttribute("href", "/espace/formations");
  });
});

// ── 9 à 12. Le suivi : progression, traces, accès échu, présence ────────────
//
// Depuis le 20/11/2026 le serveur tient le suivi de chaque personne
// (`catalog/suivi.py`, `vues_espace.mes_formations`) : chaque formation porte
// `acces`, `acces_jusqu_au`, `progression` et `seances`, chaque leçon
// `terminee`. Les charges ci-dessous ont cette forme, clé par clé.

/** Une séance, telle que `mes_formations` l'écrit. Passée par défaut. */
function seanceDEleve(surcharges: Record<string, unknown> = {}) {
  return {
    id: "s-1",
    intitule: "Journée 1",
    debut: "2020-11-10T08:00:00+00:00",
    duree_minutes: 210,
    lieu: "Salle Colbert, Lille",
    signee_le: null,
    annulee_le: null,
    signable: false,
    signature_jusqu_au: null,
    ...surcharges,
  };
}

/** La formation, avec son suivi : deux leçons terminées sur cinq. */
function formationSuivie(surcharges: Record<string, unknown> = {}) {
  const base = laFormation(LIEN_AFFICHE);
  return {
    ...base,
    modules: base.modules.map((module) => ({
      ...module,
      lecons: module.lecons.map((uneLecon) => ({
        ...uneLecon,
        terminee: uneLecon.id === "l-2" || uneLecon.id === "l-3",
      })),
    })),
    acces: "ouvert",
    acces_jusqu_au: "2027-11-03",
    progression: { terminees: 2, total: 5, pourcent: 40 },
    seances: [] as object[],
    ...surcharges,
  };
}

/** Ce que rend une trace de lecture. */
function suiviRendu(leconId: string, terminee: boolean, terminees: number) {
  return HttpResponse.json({
    lecon: {
      id: leconId,
      terminee,
      terminee_le: terminee ? "2026-11-20T10:00:00+00:00" : null,
      premiere_ouverture_le: "2026-11-20T09:00:00+00:00",
      derniere_ouverture_le: "2026-11-20T10:00:00+00:00",
    },
    formation: SLUG,
    progression: { terminees, total: 5, pourcent: Math.round((terminees / 5) * 100) },
  });
}

/** Les envois d'UN genre (`ouverte` ou `terminee`), dans l'ordre. */
function tracesDe(cle: "ouverte" | "terminee") {
  return traces.filter((trace) => cle in (trace.corps as Record<string, unknown>));
}

function barre(dans: HTMLElement = document.body): HTMLElement {
  return within(dans).getByRole("progressbar");
}

describe("la progression et la fin d'accès", () => {
  it("la liste : la barre, « X leçons sur Y terminées », et le dernier jour d'accès", async () => {
    servir(liste(formationSuivie()));
    monter(<MesFormations />);

    const carte = (await screen.findByRole("heading", { level: 2, name: "Créer sa micro-entreprise d'essai" })).closest(
      "li",
    ) as HTMLElement;
    const progression = barre(carte);
    expect(progression).toHaveAttribute("aria-valuenow", "40");
    expect(progression).toHaveAttribute("aria-valuemin", "0");
    expect(progression).toHaveAttribute("aria-valuemax", "100");
    expect(progression).toHaveAccessibleName(/Votre progression dans/);
    // La même chose, écrite : la barre ne se lit pas seule.
    expect(texteDe(carte)).toContain("2 leçons sur 5 terminées");
    expect(texteDe(carte)).toContain("Accès jusqu'au 3 novembre 2027");
    expect(within(carte).getByRole("link", { name: /Ouvrir la formation/ })).toBeInTheDocument();
  });

  it("le singulier s'accorde, et un accès sans limite ne dit aucune date", async () => {
    servir(
      liste(formationSuivie({ acces_jusqu_au: null, progression: { terminees: 1, total: 5, pourcent: 20 } })),
    );
    monter(<MesFormations />);

    const carte = (await screen.findByRole("heading", { level: 2 })).closest("li") as HTMLElement;
    expect(texteDe(carte)).toContain("1 leçon sur 5 terminée");
    expect(texteDe(carte)).not.toContain("terminées");
    expect(texteDe(carte)).not.toMatch(/Accès jusqu'au/);
  });

  it("contre-épreuve : un serveur qui ne dit rien de la progression n'obtient ni barre ni zéro inventé", async () => {
    servir(liste(laFormation(LIEN_AFFICHE), formationSuivie({ slug: "sans-lecon", titre: "Sans leçon", modules: [], progression: { terminees: 0, total: 0, pourcent: null } })));
    monter(<MesFormations />);

    await screen.findByRole("heading", { level: 2, name: "Créer sa micro-entreprise d'essai" });
    expect(screen.queryByRole("progressbar")).toBeNull();
    expect(texteDe(document.body)).not.toMatch(/sur \d+ terminée/);
  });

  it("une formation ouverte montre la même barre, et son dernier jour d'accès", async () => {
    await ouvrirLaFormation(liste(formationSuivie()));

    expect(barre()).toHaveAttribute("aria-valuenow", "40");
    expect(texteDe(document.body)).toContain("2 leçons sur 5 terminées");
    expect(texteDe(document.body)).toContain("Accès jusqu'au 3 novembre 2027");
    // Les leçons terminées sont cochées dans le programme — le signe ET le mot.
    expect(texteDe(ligne("Le guide à lire"))).toContain("✓ Terminée");
    expect(texteDe(ligne("Le modèle de statuts"))).toContain("✓ Terminée");
    expect(texteDe(ligne("Bienvenue"))).not.toContain("Terminée");
  });
});

describe("la trace d'une leçon ouverte", () => {
  it("ouvrir une leçon envoie {ouverte: true} UNE fois, sous le jeton — puis une fois pour la suivante", async () => {
    await ouvrirLaFormation(liste(formationSuivie()));

    await waitFor(() => expect(traces).toHaveLength(1));
    expect(traces[0]).toEqual({ lecon: "l-1", corps: { ouverte: true }, jeton: "Bearer jeton-de-session" });
    // Rien d'autre ne part tant qu'on reste sur la leçon.
    await new Promise((resoudre) => setTimeout(resoudre, 60));
    expect(traces).toHaveLength(1);

    fireEvent.click(ligne("Valider ses acquis"));
    await waitFor(() => expect(traces).toHaveLength(2));
    expect(traces[1]).toMatchObject({ lecon: "l-4", corps: { ouverte: true } });
  });

  it("sous le mode strict de React, qui rejoue les effets : toujours une seule trace", async () => {
    parametres.slug = SLUG;
    servir(liste(formationSuivie()));
    const requetes = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <React.StrictMode>
        <QueryClientProvider client={requetes}>
          <FormationSuivie />
        </QueryClientProvider>
      </React.StrictMode>,
    );
    await screen.findByRole("navigation", { name: "Programme" });

    await waitFor(() => expect(traces.length).toBeGreaterThanOrEqual(1));
    await new Promise((resoudre) => setTimeout(resoudre, 80));
    expect(traces).toHaveLength(1);
  });

  it("« Marquer comme terminée » envoie {terminee: true} ; la barre, le texte et la coche suivent la RÉPONSE", async () => {
    server.use(
      http.post(LECONS_API, async ({ request, params }) => {
        const corps = (await request.json()) as { ouverte?: true; terminee?: boolean };
        traces.push({ lecon: String(params.id), corps, jeton: request.headers.get("Authorization") });
        // Le serveur compte : trois terminées dès que celle-ci l'est.
        return corps.terminee === true ? suiviRendu("l-1", true, 3) : suiviRendu("l-1", false, 2);
      }),
    );
    await ouvrirLaFormation(liste(formationSuivie()));
    expect(barre()).toHaveAttribute("aria-valuenow", "40");

    fireEvent.click(screen.getByRole("button", { name: "Marquer comme terminée" }));

    await waitFor(() => expect(barre()).toHaveAttribute("aria-valuenow", "60"));
    expect(tracesDe("terminee")).toEqual([
      { lecon: "l-1", corps: { terminee: true }, jeton: "Bearer jeton-de-session" },
    ]);
    expect(texteDe(document.body)).toContain("3 leçons sur 5 terminées");
    expect(texteDe(ligne("Bienvenue"))).toContain("✓ Terminée");
    expect(screen.getByRole("status")).toHaveTextContent("Leçon marquée comme terminée.");
    // La liste n'a pas été relue : la réponse suffit.
    expect(lectures).toHaveLength(1);

    // Le même bouton défait le geste.
    fireEvent.click(screen.getByRole("button", { name: "Terminée — annuler" }));
    await waitFor(() => expect(barre()).toHaveAttribute("aria-valuenow", "40"));
    expect(tracesDe("terminee").map((trace) => trace.corps)).toEqual([{ terminee: true }, { terminee: false }]);
    expect(texteDe(ligne("Bienvenue"))).not.toContain("Terminée");
    expect(screen.getByRole("button", { name: "Marquer comme terminée" })).toBeInTheDocument();
  });

  it("une leçon déjà terminée s'ouvre sur « Terminée — annuler »", async () => {
    await ouvrirLaFormation(liste(formationSuivie()));
    fireEvent.click(ligne("Le guide à lire"));

    expect(await screen.findByRole("button", { name: "Terminée — annuler" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Marquer comme terminée" })).toBeNull();
  });

  it("une trace qui ne s'enregistre pas se DIT, et ne bloque pas la lecture", async () => {
    server.use(http.post(LECONS_API, () => new HttpResponse("panne", { status: 500 })));
    await ouvrirLaFormation(liste(formationSuivie()));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /Votre passage sur cette leçon n'a pas pu être enregistré\. Vous pouvez continuer votre lecture/,
    );
    // La leçon est là, et l'on passe à la suivante.
    expect(document.querySelector(".frs-video iframe")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Leçon suivante/ }));
    await waitFor(() => expect(courantes()).toEqual(["Le guide à lire"]));
    expect(texteDe(document.querySelector(".frs-texte"))).toContain("Premier paragraphe de la leçon.");
  });

  it("« Marquer comme terminée » refusé : une alerte, le bouton reste, la barre ne bouge pas", async () => {
    server.use(
      http.post(LECONS_API, async ({ request }) => {
        const corps = (await request.json()) as { terminee?: boolean };
        return "terminee" in corps ? new HttpResponse("panne", { status: 500 }) : suiviRendu("l-1", false, 2);
      }),
    );
    await ouvrirLaFormation(liste(formationSuivie()));

    fireEvent.click(screen.getByRole("button", { name: "Marquer comme terminée" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/Votre choix n'a pas pu être enregistré/);
    expect(barre()).toHaveAttribute("aria-valuenow", "40");
    expect(texteDe(ligne("Bienvenue"))).not.toContain("Terminée");
    const bouton = screen.getByRole("button", { name: "Marquer comme terminée" });
    await waitFor(() => expect(bouton).not.toHaveAttribute("aria-disabled"));
  });

  it("un accès échu entre-temps (403 `acces_echu`) : la phrase du serveur, et la liste est relue", async () => {
    const ECHU = "Votre accès à cette formation est terminé.";
    server.use(
      http.post(LECONS_API, () => HttpResponse.json({ error: ECHU, code: "acces_echu" }, { status: 403 })),
    );
    await ouvrirLaFormation(
      liste(formationSuivie()),
      liste(formationSuivie({ acces: "echu", acces_jusqu_au: "2026-11-19", modules: [] })),
    );

    // La relecture rend la formation échue : la page devient celle d'un
    // accès terminé, sans programme.
    expect(await screen.findByText(/Votre accès à cette formation s'est terminé le 19 novembre 2026/)).toBeInTheDocument();
    expect(lectures).toHaveLength(2);
    expect(screen.queryByRole("navigation", { name: "Programme" })).toBeNull();
  });
});

describe("un accès échu", () => {
  const ECHUE = () =>
    formationSuivie({ acces: "echu", acces_jusqu_au: "2026-10-01", modules: [], progression: { terminees: 0, total: 0, pourcent: null } });

  it("la liste : la formation reste, avec la date de fin, son rachat et le contact — sans « Ouvrir » ni programme compté", async () => {
    servir(liste(ECHUE()));
    monter(<MesFormations />);

    const carte = (await screen.findByRole("heading", { level: 2, name: "Créer sa micro-entreprise d'essai" })).closest(
      "li",
    ) as HTMLElement;
    expect(texteDe(carte)).toContain("Votre accès à cette formation s'est terminé le 1 octobre 2026.");
    expect(within(carte).getByRole("link", { name: /Racheter la formation/ })).toHaveAttribute(
      "href",
      `/formations/${SLUG}`,
    );
    expect(within(carte).getByRole("link", { name: "Nous contacter" })).toHaveAttribute("href", "/contact");
    expect(within(carte).queryByRole("link", { name: /Ouvrir la formation/ })).toBeNull();
    // Le serveur ne rend plus le programme : on ne compte pas « 0 module ».
    expect(texteDe(carte)).not.toMatch(/\d+ module/);
    expect(within(carte).queryByRole("progressbar")).toBeNull();
  });

  it("ouverte par son adresse : le même message, sans programme, sans « Le programme arrive », et aucune trace", async () => {
    parametres.slug = SLUG;
    servir(liste(ECHUE()));
    monter(<FormationSuivie />);

    expect(await screen.findByText(/Votre accès à cette formation s'est terminé le 1 octobre 2026/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Créer sa micro-entreprise d'essai" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Racheter la formation/ })).toHaveAttribute("href", `/formations/${SLUG}`);
    expect(screen.getByRole("link", { name: "Nous contacter" })).toHaveAttribute("href", "/contact");
    expect(screen.queryByRole("navigation", { name: "Programme" })).toBeNull();
    expect(screen.queryByText("Le programme arrive")).toBeNull();
    expect(screen.queryByRole("button", { name: /Marquer comme terminée/ })).toBeNull();
    expect(texteDe(document.body)).not.toMatch(/\d+ module/);
    await new Promise((resoudre) => setTimeout(resoudre, 60));
    expect(traces).toEqual([]);
  });

  it("contre-épreuve : un accès ouvert ne dit rien d'un accès terminé", async () => {
    await ouvrirLaFormation(liste(formationSuivie()));
    expect(screen.queryByText(/s'est terminé/)).toBeNull();
    expect(screen.queryByRole("link", { name: /Racheter/ })).toBeNull();
  });
});

describe("les séances en présentiel de l'élève", () => {
  const EMARGEMENT_API = `${ORIGINE}/api/espace/formations/seances/:id/emargement/`;
  const FERMEE =
    "La signature en ligne est fermée. Votre formatrice peut reporter votre signature sur la feuille d'émargement.";

  function carteDe(intitule: string): HTMLElement {
    return screen.getByRole("heading", { level: 4, name: intitule }).closest("li") as HTMLElement;
  }

  it("chaque séance dit sa date, sa durée, son lieu — et où en est la signature", async () => {
    await ouvrirLaFormation(
      liste(
        formationSuivie({
          seances: [
            seanceDEleve({ id: "s-1", intitule: "À signer", signable: true }),
            seanceDEleve({ id: "s-2", intitule: "Déjà signée", signee_le: "2020-11-10T08:05:00+00:00" }),
            seanceDEleve({ id: "s-3", intitule: "À venir", debut: "2099-06-01T07:30:00+00:00" }),
            seanceDEleve({ id: "s-4", intitule: "Annulée", annulee_le: "2020-11-09T10:00:00+00:00", signable: false }),
            seanceDEleve({ id: "s-5", intitule: "Trop tard" }),
          ],
        }),
      ),
    );

    expect(screen.getByRole("heading", { level: 3, name: "Séances en présentiel" })).toBeInTheDocument();
    // À l'heure de Paris, quel que soit le fuseau du poste.
    expect(texteDe(carteDe("À signer"))).toContain("10 novembre 2020 à 09:00 · 3 h 30 · Salle Colbert, Lille");

    // Signable : le formulaire, et lui seul.
    expect(within(carteDe("À signer")).getByLabelText("Votre nom et prénom")).toBeInTheDocument();
    expect(within(carteDe("À signer")).getByRole("button", { name: "Je signe ma présence" })).toBeInTheDocument();

    expect(texteDe(carteDe("Déjà signée"))).toContain("Présence signée le 10 novembre 2020 à 09:05");
    expect(texteDe(carteDe("À venir"))).toContain("La signature s'ouvrira au début de la séance.");
    expect(texteDe(carteDe("Annulée"))).toContain("Cette séance est annulée.");
    expect(texteDe(carteDe("Trop tard"))).toContain(FERMEE);

    // Un seul formulaire à l'écran : celui de la séance que le serveur ouvre.
    expect(screen.getAllByRole("button", { name: "Je signe ma présence" })).toHaveLength(1);
    for (const sans of ["Déjà signée", "À venir", "Annulée", "Trop tard"]) {
      expect(within(carteDe(sans)).queryByRole("textbox")).toBeNull();
    }
    expect(texteDe(carteDe("Annulée"))).not.toContain(FERMEE);
  });

  it("c'est le serveur qui ouvre la signature : une séance commencée qu'il ne dit pas signable n'a pas de formulaire", async () => {
    // Commencée, non annulée, non signée — et `signable` absent ou faux.
    const sansLeDire = seanceDEleve({ id: "s-1", intitule: "Sans le dire" });
    delete (sansLeDire as Record<string, unknown>).signable;
    await ouvrirLaFormation(
      liste(formationSuivie({ seances: [sansLeDire, seanceDEleve({ id: "s-2", intitule: "Refusée", signable: false })] })),
    );

    expect(screen.queryByRole("button", { name: "Je signe ma présence" })).toBeNull();
    expect(texteDe(carteDe("Sans le dire"))).toContain(FERMEE);
    expect(texteDe(carteDe("Refusée"))).toContain(FERMEE);
  });

  it("contre-épreuve : une séance À VENIR que le serveur dit signable montre bien le formulaire", async () => {
    await ouvrirLaFormation(
      liste(formationSuivie({ seances: [seanceDEleve({ debut: "2099-06-01T07:30:00+00:00", signable: true })] })),
    );
    expect(screen.getByRole("button", { name: "Je signe ma présence" })).toBeInTheDocument();
    expect(screen.queryByText(/s'ouvrira au début/)).toBeNull();
  });

  it("signer : le nom part sous le jeton, puis « Présence signée le … » à la date que le serveur rend", async () => {
    const envois: { seance: string; corps: unknown; jeton: string | null }[] = [];
    server.use(
      http.post(EMARGEMENT_API, async ({ request, params }) => {
        envois.push({
          seance: String(params.id),
          corps: await request.json(),
          jeton: request.headers.get("Authorization"),
        });
        return HttpResponse.json(
          {
            emargement: {
              seance_id: "s-1",
              signe_le: "2020-11-10T08:07:00+00:00",
              mode: "en_ligne",
              nom_signe: "Eva Martin",
            },
          },
          { status: 201 },
        );
      }),
    );
    await ouvrirLaFormation(liste(formationSuivie({ seances: [seanceDEleve({ signable: true })] })));
    const champ = screen.getByLabelText("Votre nom et prénom");

    // Sans nom : aucun envoi, et le champ le dit.
    fireEvent.click(screen.getByRole("button", { name: "Je signe ma présence" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/Écrivez votre nom et votre prénom/);
    expect(champ).toHaveAttribute("aria-invalid", "true");
    await new Promise((resoudre) => setTimeout(resoudre, 50));
    expect(envois).toEqual([]);

    fireEvent.change(champ, { target: { value: "  Eva Martin  " } });
    fireEvent.click(screen.getByRole("button", { name: "Je signe ma présence" }));

    const confirmation = await screen.findByText(/Présence signée le/);
    expect(envois).toEqual([{ seance: "s-1", corps: { nom: "Eva Martin" }, jeton: "Bearer jeton-de-session" }]);
    expect(texteDe(confirmation)).toContain("Présence signée le 10 novembre 2020 à 09:07");
    // Le formulaire a quitté l'écran : le focus va à la confirmation.
    expect(screen.queryByRole("button", { name: "Je signe ma présence" })).toBeNull();
    await waitFor(() => expect(confirmation).toHaveFocus());
    // La liste n'a pas été relue : la réponse suffit.
    expect(lectures).toHaveLength(1);
  });

  for (const [code, statut, phrase] of [
    ["seance_pas_commencee", 409, "Cette séance n'a pas encore commencé."],
    ["seance_annulee", 409, "Cette séance est annulée."],
    ["deja_signe", 409, "Vous avez déjà signé cette séance."],
    ["signature_fermee", 409, "La signature en ligne est fermée depuis plus de 24 heures."],
    ["seance_anterieure_a_l_achat", 409, "Cette séance a eu lieu avant votre inscription."],
    ["nom_manquant", 400, "Écrivez votre nom : deux signes au moins."],
    ["nom_illisible", 400, "Ce nom est illisible."],
    ["assistance_sans_trace", 403, "Une session d'assistance ne signe pas à la place de l'élève."],
  ] as const) {
    it(`signature refusée (${statut} \`${code}\`) : la phrase du serveur, telle quelle, contre le champ`, async () => {
      server.use(http.post(EMARGEMENT_API, () => HttpResponse.json({ error: phrase, code }, { status: statut })));
      await ouvrirLaFormation(liste(formationSuivie({ seances: [seanceDEleve({ signable: true })] })));

      const champ = screen.getByLabelText("Votre nom et prénom");
      fireEvent.change(champ, { target: { value: "Eva Martin" } });
      fireEvent.click(screen.getByRole("button", { name: "Je signe ma présence" }));

      const alerte = await screen.findByRole("alert");
      expect(alerte).toHaveTextContent(phrase);
      expect(alerte.textContent).toBe(phrase);
      expect((champ.getAttribute("aria-describedby") ?? "").split(" ")).toContain(alerte.id);
      expect(screen.queryByText(/Présence signée/)).toBeNull();
      // Un refus sur l'ÉTAT de la séance fait relire la liste ; une saisie
      // refusée, non.
      await waitFor(() => expect(lectures).toHaveLength(statut === 409 ? 2 : 1));
    });
  }

  it("une panne à la signature se dit, et la saisie reste", async () => {
    server.use(http.post(EMARGEMENT_API, () => new HttpResponse("panne", { status: 500 })));
    await ouvrirLaFormation(liste(formationSuivie({ seances: [seanceDEleve({ signable: true })] })));

    const champ = screen.getByLabelText("Votre nom et prénom");
    fireEvent.change(champ, { target: { value: "Eva Martin" } });
    fireEvent.click(screen.getByRole("button", { name: "Je signe ma présence" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/Votre signature n'a pas pu être enregistrée/);
    expect(champ).toHaveValue("Eva Martin");
    expect(screen.queryByText(/Présence signée/)).toBeNull();
  });

  it("contre-épreuve : une formation sans séance n'affiche pas la rubrique", async () => {
    await ouvrirLaFormation(liste(formationSuivie()));
    expect(screen.queryByRole("heading", { name: "Séances en présentiel" })).toBeNull();
  });
});

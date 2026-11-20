/** L'achat d'une formation par Stripe : le bouton, l'abandon, le retour.
 *
 * Décision de la cliente du 20/11/2026 : une formation se paie sur la
 * plateforme. Jusque-là, le bouton d'inscription ouvrait un courriel.
 *
 * Ce que ce fichier verrouille :
 *
 * 1. LA RÈGLE (`achat.payerUneFormation`) : par l'espace si un compte est
 *    ouvert, sinon en visiteur ; un 401 retombe en visiteur ; tout autre refus
 *    de l'espace (403) est rendu tel quel, jamais contourné par la route
 *    publique ; une réponse sans adresse est un refus ; et l'adresse rendue
 *    est celle de Stripe Checkout, hôte comparé EXACTEMENT — sinon personne
 *    ne part, et la page dit sa phrase de panne (bloc « 1 bis ») ;
 * 2. LE BOUTON (`Formations.BoutonDInscription`) : il envoie le slug de SA
 *    formation et rien d'autre, mène à l'adresse rendue, se dit occupé
 *    pendant l'appel, n'ouvre qu'UN paiement pour plusieurs clics — sur le
 *    même bouton comme sur un autre —, dit le refus du serveur sous le bouton
 *    cliqué, propose « Mes formations » quand la formation est déjà achetée,
 *    et dit une panne en français, avec l'adresse de contact ;
 * 3. L'ABANDON : `?paiement=abandon` se dit, dans un bandeau refermable ;
 * 4. LE RETOUR (`RetourFormation`) : confirmé, refusé, sans session, réponse
 *    illisible ; un jeton nul n'ouvre aucune session ; une session existante
 *    n'est jamais remplacée ; un seul appel en mode strict.
 *
 * Les corps attendus et les refus servis sont RECOPIÉS DU SERVEUR
 * (`vues_formations.acheter` / `retour`, `vues_espace.acheter_une_formation`,
 * `catalog.formations.a_vendre`) — pas dérivés du client, qui se comparerait
 * à lui-même (règle 9). Deux enveloppes de refus : `{"erreur", "code"}` pour
 * les routes publiques, `{"error", "code"}` pour celles de l'espace.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ErreurApi, jeton } from "../espace/api";
import {
  AdresseDePaiementRefusee,
  adresseDePaiementSure,
  HOTE_DE_PAIEMENT,
  payerUneFormation,
} from "../public/achat";
import { RefusInscription } from "../public/donnees";
import { server } from "./server";

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => () => undefined,
  Link: ({
    to,
    params,
    className,
    children,
  }: {
    to: string;
    params?: Record<string, string>;
    className?: string;
    children: React.ReactNode;
  }) => (
    <a
      href={Object.entries(params ?? {}).reduce(
        (adresse, [nom, valeur]) => adresse.replace(`$${nom}`, valeur),
        to,
      )}
      className={className}
    >
      {children}
    </a>
  ),
}));

// Importés APRÈS le simulacre du routeur.
const { Formations, FormationMicro, FormationPop, FormationSocietes } = await import(
  "../public/Formations"
);
const { RetourFormation } = await import("../public/RetourFormation");

// Lue AVANT tout remplacement de `window.location`.
const ORIGINE = window.location.origin;
const API = `${ORIGINE}/api`;

// L'hôte est le VRAI : depuis le 20/11/2026, `achat.ts` ne rend qu'une adresse
// de Stripe Checkout (`adresseDePaiementSure`). L'hôte inventé d'avant
// (`checkout.stripe.exemple`) est désormais refusé, et c'est voulu.
const STRIPE = "https://checkout.stripe.com/c/pay/cs_test_formation";

/** Le slug de la formation « micro-entreprise », écrit ICI en toutes lettres. */
const MICRO = "creer-sa-micro-entreprise";

// ── L'API, telle que le test la sert ────────────────────────────────────────

function formation(slug: string, prix_cents: number) {
  return {
    slug,
    titre: `Formation ${slug}`,
    sous_titre: "",
    accroche: "",
    prix_cents,
    devise: "EUR",
    duree_heures: 12,
    heures_de_coaching: 2,
    lien_d_achat: "",
    image: "",
    nombre_de_modules: 0,
    modules: [],
  };
}

const CATALOGUE = {
  formations: [
    formation("creer-son-entreprise", 123700),
    formation(MICRO, 131900),
    formation("methode-pop", 91300),
  ],
};

/** Ce qui est parti au serveur, route par route. */
type Appel = { corps: Record<string, unknown>; autorisation: string | null };
let appels: Record<"espace" | "visiteur", Appel[]>;

type Reponse = () => Response | Promise<Response>;
const adresseRendue: Reponse = () => HttpResponse.json({ adresse: STRIPE });

function brancher({
  espace = adresseRendue,
  visiteur = adresseRendue,
}: { espace?: Reponse; visiteur?: Reponse } = {}) {
  const noter = async (cle: keyof typeof appels, request: Request) => {
    appels[cle].push({
      corps: (await request.clone().json()) as Record<string, unknown>,
      autorisation: request.headers.get("Authorization"),
    });
  };
  server.use(
    http.get(`${API}/public/formations/`, () => HttpResponse.json(CATALOGUE)),
    http.post(`${API}/espace/formations/acheter/`, async ({ request }) => {
      await noter("espace", request);
      return espace();
    }),
    http.post(`${API}/public/formations/acheter/`, async ({ request }) => {
      await noter("visiteur", request);
      return visiteur();
    }),
  );
}

/** Les refus, tels que le serveur les écrit. */
const REFUS = {
  inconnue: () =>
    HttpResponse.json(
      { erreur: "Cette formation n'est pas disponible.", code: "formation_inconnue" },
      { status: 404 },
    ),
  sansProgramme: () =>
    HttpResponse.json(
      {
        erreur:
          "Cette formation n'est pas encore ouverte à l'achat : son programme est en cours de mise en ligne. Écrivez-nous à contact@evkha.fr pour être prévenu de son ouverture.",
        code: "formation_sans_programme",
      },
      { status: 409 },
    ),
  tropDeTentatives: () =>
    HttpResponse.json(
      {
        erreur:
          "Trop de paiements ouverts depuis cette connexion. Réessayez dans une heure, ou écrivez-nous à contact@evkha.fr.",
        code: "trop_de_tentatives",
      },
      { status: 429 },
    ),
  dejaAchetee: () =>
    HttpResponse.json(
      {
        error:
          "Vous avez déjà cette formation : elle est dans votre espace, dans « Mes formations ».",
        code: "formation_deja_achetee",
      },
      { status: 409 },
    ),
  assistance: () =>
    HttpResponse.json(
      {
        error:
          "Une session d'assistance ne peut engager aucune dépense au nom du client. Quittez l'assistance pour agir depuis votre propre compte.",
        code: "assistance_sans_depense",
      },
      { status: 403 },
    ),
  sessionPerimee: () =>
    HttpResponse.json({ error: "Authentification requise.", code: "unauthorized" }, { status: 401 }),
};

// ── L'adresse du navigateur ─────────────────────────────────────────────────
// jsdom ne navigue pas : on pose une adresse qui ENREGISTRE les départs.

const adresseDOrigine = Object.getOwnPropertyDescriptor(window, "location");
let departs: string[] = [];

function poserLAdresse(chemin: string, recherche = "") {
  departs = [];
  Object.defineProperty(window, "location", {
    configurable: true,
    value: {
      origin: ORIGINE,
      pathname: chemin,
      search: recherche,
      hash: "",
      get href() {
        return `${ORIGINE}${chemin}${recherche}`;
      },
      set href(cible: string) {
        departs.push(cible);
      },
    },
  });
}

function rendreLAdresse() {
  if (adresseDOrigine) Object.defineProperty(window, "location", adresseDOrigine);
}

// ── Outils ──────────────────────────────────────────────────────────────────

const LIBELLE = /JE REJOINS LA FORMATION/;
const ATTENTE = /Ouverture du paiement/;

/** Les trois boutons d'inscription de la page, une fois le catalogue lu. */
async function boutons(): Promise<HTMLButtonElement[]> {
  await waitFor(() =>
    expect(document.querySelectorAll("button.for-bouton-achat")).toHaveLength(3),
  );
  return Array.from(document.querySelectorAll<HTMLButtonElement>("button.for-bouton-achat"));
}

async function pageMicro() {
  poserLAdresse(`/formations/${MICRO}`);
  render(<FormationMicro />);
  return boutons();
}

/** Les refus affichés sous les boutons (la région d'alerte des tarifs, vide,
 *  n'en est pas un). */
function refusAffiches(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>(".for-refus"));
}

/** Une réponse que le test libère quand il veut : de quoi regarder l'écran
 *  PENDANT l'appel. */
function reponseRetenue(): { reponse: Reponse; liberer: () => void } {
  let liberer: () => void = () => undefined;
  const attente = new Promise<void>((resoudre) => {
    liberer = resoudre;
  });
  return {
    reponse: async () => {
      await attente;
      return HttpResponse.json({ adresse: STRIPE });
    },
    liberer,
  };
}

beforeEach(() => {
  localStorage.clear();
  appels = { espace: [], visiteur: [] };
});

afterEach(() => {
  cleanup();
  rendreLAdresse();
  vi.restoreAllMocks();
  window.history.pushState({}, "", "/");
});

// ── 1. La règle ─────────────────────────────────────────────────────────────

describe("payer une formation : par l'espace si un compte est ouvert, sinon en visiteur", () => {
  it("avec une session : la route de l'espace, sous le jeton, et le slug seul", async () => {
    brancher();
    jeton.ecrire("jeton-de-session");

    await expect(payerUneFormation(MICRO)).resolves.toBe(STRIPE);
    // Le corps que `acheter_une_formation` lit : `formation`. Ni prix, ni
    // adresse e-mail.
    expect(appels.espace).toEqual([
      { corps: { formation: MICRO }, autorisation: "Bearer jeton-de-session" },
    ]);
    expect(appels.visiteur).toEqual([]);
  });

  it("contre-épreuve — en visiteur : la route publique, sans jeton", async () => {
    brancher();

    await expect(payerUneFormation(MICRO)).resolves.toBe(STRIPE);
    expect(appels.visiteur).toEqual([{ corps: { formation: MICRO }, autorisation: null }]);
    expect(appels.espace).toEqual([]);
  });

  it("en visiteur, une adresse e-mail fournie part avec le slug", async () => {
    brancher();

    await payerUneFormation(MICRO, "eva@exemple.fr");
    expect(appels.visiteur[0].corps).toEqual({ formation: MICRO, email: "eva@exemple.fr" });
  });

  it("une session périmée (401) retombe en visiteur, sans renvoyer à la connexion", async () => {
    poserLAdresse(`/formations/${MICRO}`);
    brancher({ espace: REFUS.sessionPerimee });
    jeton.ecrire("jeton-perime");

    await expect(payerUneFormation(MICRO)).resolves.toBe(STRIPE);
    expect(appels.espace).toHaveLength(1);
    expect(appels.visiteur).toEqual([{ corps: { formation: MICRO }, autorisation: null }]);
    expect(jeton.present()).toBe(false);
    expect(departs).toEqual([]);
  });

  it("un refus de l'espace (403) est rendu tel quel, jamais contourné par la route publique", async () => {
    brancher({ espace: REFUS.assistance });
    jeton.ecrire("jeton-d-assistance");

    const refus = await payerUneFormation(MICRO).catch((cause: unknown) => cause);
    expect(refus).toBeInstanceOf(ErreurApi);
    expect((refus as ErreurApi).statut).toBe(403);
    expect((refus as ErreurApi).message).toMatch(/session d'assistance/);
    expect(appels.visiteur).toEqual([]);
    expect(jeton.lire()).toBe("jeton-d-assistance");
  });

  it("une réponse 200 sans adresse est un refus, pas une adresse vide", async () => {
    for (const charge of [{}, { adresse: "" }, { adresse: 12 }]) {
      brancher({ visiteur: () => HttpResponse.json(charge) });
      const refus = await payerUneFormation(MICRO).catch((cause: unknown) => cause);
      expect(refus, JSON.stringify(charge)).toBeInstanceOf(RefusInscription);
    }
    // Et par l'espace aussi.
    brancher({ espace: () => HttpResponse.json({}) });
    jeton.ecrire("jeton-de-session");
    await expect(payerUneFormation(MICRO)).rejects.toBeInstanceOf(RefusInscription);
  });
});

// ── 1 bis. L'adresse de paiement est celle de Stripe ────────────────────────
//
// Le navigateur part là où le serveur le dit. Une adresse qui n'est pas celle
// de Stripe Checkout — hôte qui lui ressemble, `http:`, identifiants, adresse
// relative — n'est jamais suivie : la page dit sa phrase de panne.

/** Les adresses qu'on ne suit pas, chacune avec ce qui la trahit. */
const HORS_DE_STRIPE: [string, string][] = [
  ["hôte qui ressemble", "https://checkout.stripe.com.evil.tld/c/pay/cs_test_1"],
  ["hôte en sous-domaine d'un autre", "https://checkout.stripe.com.exemple.fr/c/pay/cs_test_1"],
  ["autre hôte de Stripe", "https://stripe.com/c/pay/cs_test_1"],
  ["hôte inventé des anciens jeux d'essai", "https://checkout.stripe.exemple/c/pay/cs_test_1"],
  ["http:", "http://checkout.stripe.com/c/pay/cs_test_1"],
  ["Stripe en identifiant d'un autre hôte", "https://checkout.stripe.com@evil.tld/c/pay/cs_test_1"],
  ["identifiants dans l'adresse", "https://quelquun:secret@checkout.stripe.com/c/pay/cs_test_1"],
  ["port", "https://checkout.stripe.com:8443/c/pay/cs_test_1"],
  ["adresse relative", "/c/pay/cs_test_1"],
  ["adresse relative au schéma", "//checkout.stripe.com/c/pay/cs_test_1"],
  ["Stripe dans le chemin", "https://evil.tld/checkout.stripe.com/c/pay/cs_test_1"],
  ["javascript:", "javascript:alert(1)//checkout.stripe.com"],
];

describe("l'adresse de paiement est celle de Stripe", () => {
  it("la vraie adresse est rendue telle quelle, fragment compris", () => {
    expect(HOTE_DE_PAIEMENT).toBe("checkout.stripe.com");
    expect(adresseDePaiementSure(STRIPE)).toBe(STRIPE);
    const avecFragment = `${STRIPE}#fidkdWxOYHwnPyd1blpxYHZxWjA0`;
    expect(adresseDePaiementSure(avecFragment)).toBe(avecFragment);
  });

  for (const [nom, adresse] of HORS_DE_STRIPE) {
    it(`refus — ${nom} : « ${adresse} »`, () => {
      expect(adresseDePaiementSure(adresse)).toBeNull();
    });
  }

  it("refus — ce qui n'est pas une adresse", () => {
    for (const rien of ["", "   ", "pas une adresse", null, undefined, 12, {}]) {
      expect(adresseDePaiementSure(rien), String(rien)).toBeNull();
    }
  });

  it("payer une formation refuse une adresse hors de Stripe, par l'espace comme en visiteur", async () => {
    const ressemblant = () =>
      HttpResponse.json({ adresse: "https://checkout.stripe.com.evil.tld/c/pay/cs_test_1" });
    brancher({ visiteur: ressemblant, espace: ressemblant });

    await expect(payerUneFormation(MICRO)).rejects.toBeInstanceOf(AdresseDePaiementRefusee);
    expect(appels.visiteur).toHaveLength(1);

    jeton.ecrire("jeton-de-session");
    await expect(payerUneFormation(MICRO)).rejects.toBeInstanceOf(AdresseDePaiementRefusee);
    expect(appels.espace).toHaveLength(1);
  });

  /** Les quatre refus demandés, joués jusqu'au bouton. */
  const AU_BOUTON = [
    "hôte qui ressemble",
    "http:",
    "identifiants dans l'adresse",
    "adresse relative",
  ];
  const jouesAuBouton = HORS_DE_STRIPE.filter(([nom]) => AU_BOUTON.includes(nom));

  it("trouve les quatre refus à jouer au bouton (un contrôle sans rien à comparer échoue)", () => {
    expect(jouesAuBouton).toHaveLength(AU_BOUTON.length);
  });

  for (const [nom, adresse] of jouesAuBouton) {
    it(`le bouton ne part pas — ${nom} : la phrase de la panne, et le bouton se libère`, async () => {
      brancher({ visiteur: () => HttpResponse.json({ adresse }) });
      const [premier] = await pageMicro();

      fireEvent.click(premier);

      await waitFor(() => expect(refusAffiches()).toHaveLength(1));
      const [refus] = refusAffiches();
      // La MÊME phrase que pour une panne de paiement, avec l'adresse de contact.
      expect(refus).toHaveTextContent(/Le paiement n'a pas pu s'ouvrir/);
      expect(within(refus).getByRole("link", { name: "contact@evkha.fr" })).toBeInTheDocument();
      // L'adresse refusée n'est ni suivie, ni montrée.
      expect(departs).toEqual([]);
      expect(document.body.innerHTML).not.toContain("cs_test_1");
      expect(premier).not.toBeDisabled();
    });
  }

  it("contre-épreuve : la vraie adresse de Stripe est suivie, sans aucun refus", async () => {
    brancher();
    const [premier] = await pageMicro();

    fireEvent.click(premier);

    await waitFor(() => expect(departs).toEqual([STRIPE]));
    expect(refusAffiches()).toEqual([]);
  });
});

// ── 2. Le bouton ────────────────────────────────────────────────────────────

describe("le bouton d'inscription ouvre le paiement", () => {
  it("en visiteur : il envoie le slug de SA formation, puis mène à l'adresse rendue", async () => {
    brancher();
    const [premier] = await pageMicro();

    fireEvent.click(premier);

    await waitFor(() => expect(departs).toEqual([STRIPE]));
    expect(appels.visiteur).toEqual([{ corps: { formation: MICRO }, autorisation: null }]);
    expect(appels.espace).toEqual([]);
    expect(refusAffiches()).toEqual([]);
  });

  it("avec un compte ouvert : il passe par l'espace", async () => {
    brancher();
    jeton.ecrire("jeton-de-session");
    const [, deuxieme] = await pageMicro();

    fireEvent.click(deuxieme);

    await waitFor(() => expect(departs).toEqual([STRIPE]));
    expect(appels.espace).toEqual([
      { corps: { formation: MICRO }, autorisation: "Bearer jeton-de-session" },
    ]);
    expect(appels.visiteur).toEqual([]);
  });

  it("chaque page envoie le slug de sa propre formation", async () => {
    const pages: [string, () => React.JSX.Element][] = [
      ["creer-son-entreprise", FormationSocietes],
      [MICRO, FormationMicro],
      ["methode-pop", FormationPop],
    ];
    for (const [slug, Page] of pages) {
      appels = { espace: [], visiteur: [] };
      brancher();
      poserLAdresse(`/formations/${slug}`);
      const { unmount } = render(<Page />);
      const [premier] = await boutons();
      fireEvent.click(premier);
      await waitFor(() => expect(departs).toEqual([STRIPE]));
      expect(appels.visiteur.map((appel) => appel.corps), slug).toEqual([{ formation: slug }]);
      unmount();
    }
  });

  it("pendant l'appel : les trois boutons sont occupés, et le disent", async () => {
    const retenue = reponseRetenue();
    brancher({ visiteur: retenue.reponse });
    const tous = await pageMicro();
    // Au repos : actifs, leur libellé relevé.
    for (const bouton of tous) {
      expect(bouton).not.toBeDisabled();
      expect(bouton).toHaveTextContent(LIBELLE);
      expect(bouton).not.toHaveAttribute("aria-busy");
    }

    fireEvent.click(tous[0]);

    await waitFor(() => expect(tous[0]).toBeDisabled());
    for (const bouton of tous) {
      expect(bouton).toBeDisabled();
      expect(bouton).toHaveAttribute("aria-busy", "true");
      expect(bouton).toHaveTextContent(ATTENTE);
      expect(bouton).not.toHaveTextContent(LIBELLE);
    }
    expect(departs).toEqual([]);

    retenue.liberer();
    await waitFor(() => expect(departs).toEqual([STRIPE]));
  });

  it("plusieurs clics, sur le même bouton ou sur un autre : un seul paiement ouvert", async () => {
    const retenue = reponseRetenue();
    brancher({ visiteur: retenue.reponse });
    const tous = await pageMicro();

    // Deux clics du même geste, AVANT tout rendu : `disabled` n'est pas encore
    // posé, seul le garde-fou de la page les sépare.
    // Dans UN seul lot de React (`act`), sans passer par `fireEvent`, qui
    // redessine entre deux clics et laisserait `disabled` faire le travail.
    act(() => {
      tous[0].click();
      tous[0].click();
      tous[2].click();
    });
    await waitFor(() => expect(tous[1]).toBeDisabled());
    fireEvent.click(tous[1]);

    retenue.liberer();
    await waitFor(() => expect(departs).toEqual([STRIPE]));
    expect(appels.visiteur).toHaveLength(1);
  });

  it("un refus du serveur se dit sous le bouton cliqué, avec sa phrase, et le bouton se libère", async () => {
    brancher({ visiteur: REFUS.inconnue });
    const tous = await pageMicro();

    fireEvent.click(tous[1]);

    await waitFor(() => expect(refusAffiches()).toHaveLength(1));
    const [refus] = refusAffiches();
    expect(refus).toHaveAttribute("role", "alert");
    expect(refus).toHaveTextContent("Cette formation n'est pas disponible.");
    // Sous le bouton cliqué, et relié à lui.
    expect(tous[1].parentElement).toContainElement(refus);
    expect(tous[1]).toHaveAttribute("aria-describedby", refus.id);
    expect(tous[0]).not.toHaveAttribute("aria-describedby");
    // Personne n'est parti, et l'on peut réessayer.
    expect(departs).toEqual([]);
    for (const bouton of tous) {
      expect(bouton).not.toBeDisabled();
      expect(bouton).toHaveTextContent(LIBELLE);
    }
    // Ce refus-là ne parle pas de l'espace.
    expect(within(refus).queryByRole("link")).toBeNull();

    // Réessayer efface le refus et relance UN appel.
    fireEvent.click(tous[1]);
    await waitFor(() => expect(appels.visiteur).toHaveLength(2));
  });

  for (const [nom, reponse, attendu] of [
    ["409 sans programme", REFUS.sansProgramme, /programme est en cours de mise en ligne/],
    ["429 trop de tentatives", REFUS.tropDeTentatives, /Trop de paiements ouverts/],
  ] as const) {
    it(`refus ${nom} : la phrase du serveur, telle quelle`, async () => {
      brancher({ visiteur: reponse });
      const [premier] = await pageMicro();

      fireEvent.click(premier);

      await waitFor(() => expect(refusAffiches()).toHaveLength(1));
      expect(refusAffiches()[0]).toHaveTextContent(attendu);
      expect(within(refusAffiches()[0]).queryByRole("link")).toBeNull();
      expect(departs).toEqual([]);
    });
  }

  it("formation déjà achetée (409 de l'espace) : la phrase du serveur, et un lien vers « Mes formations »", async () => {
    brancher({ espace: REFUS.dejaAchetee });
    jeton.ecrire("jeton-de-session");
    const [premier] = await pageMicro();

    fireEvent.click(premier);

    await waitFor(() => expect(refusAffiches()).toHaveLength(1));
    const [refus] = refusAffiches();
    expect(refus).toHaveTextContent(/Vous avez déjà cette formation/);
    expect(within(refus).getByRole("link", { name: /Mes formations/ })).toHaveAttribute(
      "href",
      "/espace/formations",
    );
    // Le refus de l'espace n'est pas contourné : aucun paiement en visiteur.
    expect(appels.visiteur).toEqual([]);
    expect(departs).toEqual([]);
  });

  it("un 429 de l'espace (trop de paiements ouverts) : la phrase du serveur, sans repli sur la route publique", async () => {
    // La phrase et le code de `vues_espace` (enveloppe `{"error", "code"}`).
    brancher({
      espace: () =>
        HttpResponse.json(
          {
            error:
              "Vous avez ouvert beaucoup de paiements coup sur coup. Réessayez dans une heure, ou écrivez-nous à contact@evkha.fr.",
            code: "trop_de_tentatives",
          },
          { status: 429 },
        ),
    });
    jeton.ecrire("jeton-de-session");
    const [premier] = await pageMicro();

    fireEvent.click(premier);

    await waitFor(() => expect(refusAffiches()).toHaveLength(1));
    expect(refusAffiches()[0]).toHaveTextContent(/Vous avez ouvert beaucoup de paiements coup sur coup/);
    // Ni la phrase de panne de la page, ni un code nu.
    expect(refusAffiches()[0].textContent).not.toMatch(/Le paiement n'a pas pu s'ouvrir|429/);
    expect(appels.visiteur).toEqual([]);
    expect(departs).toEqual([]);
    expect(premier).not.toBeDisabled();
  });

  it("un 403 de l'espace est affiché tel quel, sans repli sur la route publique", async () => {
    brancher({ espace: REFUS.assistance });
    jeton.ecrire("jeton-d-assistance");
    const [premier] = await pageMicro();

    fireEvent.click(premier);

    await waitFor(() => expect(refusAffiches()).toHaveLength(1));
    expect(refusAffiches()[0]).toHaveTextContent(/session d'assistance ne peut engager aucune dépense/);
    expect(within(refusAffiches()[0]).queryByRole("link")).toBeNull();
    expect(appels.visiteur).toEqual([]);
    expect(departs).toEqual([]);
  });

  it("une session périmée (401) : le bouton paie quand même, en visiteur", async () => {
    brancher({ espace: REFUS.sessionPerimee });
    jeton.ecrire("jeton-perime");
    const [premier] = await pageMicro();

    fireEvent.click(premier);

    await waitFor(() => expect(departs).toEqual([STRIPE]));
    expect(appels.espace).toHaveLength(1);
    expect(appels.visiteur).toHaveLength(1);
    expect(refusAffiches()).toEqual([]);
  });

  for (const [nom, reponse] of [
    ["réseau coupé", () => HttpResponse.error()],
    [
      "page d'erreur d'un relais (502, sans code)",
      () => new HttpResponse("<html>Bad Gateway</html>", { status: 502 }),
    ],
    ["réponse 200 sans adresse", () => HttpResponse.json({})],
  ] as [string, Reponse][]) {
    it(`panne — ${nom} : une phrase française, l'adresse de contact, rien du navigateur`, async () => {
      brancher({ visiteur: reponse });
      const [premier] = await pageMicro();

      fireEvent.click(premier);

      await waitFor(() => expect(refusAffiches()).toHaveLength(1));
      const [refus] = refusAffiches();
      expect(refus).toHaveTextContent(/Le paiement n'a pas pu s'ouvrir/);
      expect(within(refus).getByRole("link", { name: "contact@evkha.fr" })).toHaveAttribute(
        "href",
        "mailto:contact@evkha.fr",
      );
      expect(refus.textContent).not.toMatch(/Failed to fetch|NetworkError|Erreur 502|\(502\)|Unexpected/i);
      expect(departs).toEqual([]);
      expect(premier).not.toBeDisabled();
    });
  }

  it("aucun lien d'inscription par courriel dans les trois pages", async () => {
    brancher();
    for (const [slug, Page] of [
      ["creer-son-entreprise", FormationSocietes],
      [MICRO, FormationMicro],
      ["methode-pop", FormationPop],
    ] as [string, () => React.JSX.Element][]) {
      poserLAdresse(`/formations/${slug}`);
      const { unmount } = render(<Page />);
      await boutons();
      const courriels = Array.from(document.querySelectorAll<HTMLAnchorElement>('a[href^="mailto:"]')).map(
        (lien) => lien.getAttribute("href") ?? "",
      );
      // Règle 1 : la page a bien des courriels (financement, présentiel) —
      // le balayage a quelque chose à lire.
      expect(courriels.length, slug).toBeGreaterThanOrEqual(2);
      expect(courriels.filter((adresse) => /inscri/i.test(decodeURIComponent(adresse))), slug).toEqual([]);
      // Et aucun bouton d'inscription n'est un lien.
      expect(document.querySelector("a.for-bouton-achat"), slug).toBeNull();
      unmount();
    }
  });
});

// ── 3. L'abandon ────────────────────────────────────────────────────────────

describe("un paiement abandonné se dit", () => {
  const PHRASE = "Votre paiement n'a pas été finalisé. Rien n'a été débité.";

  it("sur /formations?paiement=abandon : un bandeau discret, refermable pour de bon", async () => {
    brancher();
    window.history.pushState({}, "", "/formations?paiement=abandon&utm_source=lettre");
    render(<Formations />);

    const bandeau = screen.getByText(PHRASE).closest('[role="status"]');
    expect(bandeau).not.toBeNull();
    // Ce n'est pas une alerte : rien n'a échoué.
    expect(screen.getByRole("alert")).toBeEmptyDOMElement();

    fireEvent.click(screen.getByRole("button", { name: "Fermer ce message" }));

    expect(screen.queryByText(PHRASE)).toBeNull();
    // Le paramètre a quitté l'adresse — et lui seul.
    expect(window.location.pathname).toBe("/formations");
    expect(window.location.search).toBe("?utm_source=lettre");
  });

  it("une page de formation le dit aussi", async () => {
    brancher();
    window.history.pushState({}, "", `/formations/${MICRO}?paiement=abandon`);
    render(<FormationMicro />);
    expect(screen.getByText(PHRASE)).toBeInTheDocument();
  });

  it("contre-épreuve : sans le paramètre, ou avec une autre valeur, aucun bandeau", async () => {
    brancher();
    for (const adresse of ["/formations", "/formations?paiement=ok", "/formations?abandon=1"]) {
      window.history.pushState({}, "", adresse);
      const { unmount } = render(<Formations />);
      expect(screen.queryByText(PHRASE), adresse).toBeNull();
      expect(screen.queryByRole("button", { name: "Fermer ce message" }), adresse).toBeNull();
      unmount();
    }
  });
});

// ── 4. La page de retour ────────────────────────────────────────────────────

describe("le retour du paiement d'une formation", () => {
  /** `vues_formations.retour` : le compte vient de naître de ce paiement. */
  const AVEC_JETON = {
    jeton: "jeton-neuf",
    connexion_requise: false,
    titre: "Formation servie par le test",
    slug: MICRO,
  };
  /** Le compte existait : aucun jeton. */
  const SANS_JETON = { ...AVEC_JETON, jeton: null, connexion_requise: true };

  let confirmations: Record<string, unknown>[];

  function retour(reponse: Reponse, recherche = "?session=cs_test_9", strict = false) {
    window.history.pushState({}, "", `/formations/retour${recherche}`);
    server.use(
      http.post(`${API}/public/formations/retour/`, async ({ request }) => {
        confirmations.push((await request.clone().json()) as Record<string, unknown>);
        return reponse();
      }),
    );
    return render(
      strict ? (
        <React.StrictMode>
          <RetourFormation />
        </React.StrictMode>
      ) : (
        <RetourFormation />
      ),
    );
  }

  function robots(): string[] {
    return Array.from(document.querySelectorAll<HTMLMetaElement>('meta[name="robots"]')).map(
      (balise) => balise.content,
    );
  }

  beforeEach(() => {
    confirmations = [];
  });

  it("confirmé, compte né du paiement : la session s'ouvre, et l'on accède à SA formation", async () => {
    const { unmount } = retour(() => HttpResponse.json(AVEC_JETON));

    // D'abord l'attente, annoncée.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/Nous confirmons votre paiement/);
    expect(screen.getByRole("status")).toBeInTheDocument();

    const acces = await screen.findByRole("link", { name: /Accéder à ma formation/ });
    expect(acces).toHaveAttribute("href", `/espace/formations/${MICRO}`);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/votre formation\s+est à vous/);
    expect(screen.getByText(AVEC_JETON.titre)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByRole("link", { name: /Me connecter/ })).toBeNull();
    // La phrase de la connexion ne se dit qu'à qui doit se connecter.
    expect(screen.queryByText(/pas encore de mot de passe/)).toBeNull();

    expect(jeton.lire()).toBe("jeton-neuf");
    // Le corps que `retour` lit : `session`, tel que l'adresse le porte.
    expect(confirmations).toEqual([{ session: "cs_test_9" }]);
    // La page ne s'indexe pas — le temps de son affichage seulement.
    expect(robots()).toEqual(["noindex"]);
    unmount();
    expect(robots()).toEqual([]);
  });

  it("jeton nul : aucune session n'est ouverte, rien n'est écrit, la connexion est proposée", async () => {
    const ecritures = vi.spyOn(Storage.prototype, "setItem");
    retour(() => HttpResponse.json(SANS_JETON));

    const connexion = await screen.findByRole("link", { name: /Me connecter/ });
    expect(connexion).toHaveAttribute("href", "/espace/connexion");
    // Juste que le compte soit neuf ou ancien : la phrase n'AFFIRME plus qu'un
    // courriel est parti — un compte qui existait n'en reçoit pas.
    expect(
      screen.getByText(
        "Connectez-vous pour y accéder. Si vous n'avez pas encore de mot de passe, un courriel vient de vous être envoyé pour le choisir.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Un courriel vous a été envoyé pour choisir/)).toBeNull();
    expect(screen.getByText(/rattachée au compte/)).toBeInTheDocument();
    // « Accéder à ma formation » mènerait dans un espace sans session.
    expect(screen.queryByRole("link", { name: /Accéder à ma formation/ })).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();

    expect(ecritures).not.toHaveBeenCalled();
    expect(jeton.present()).toBe(false);
  });

  it("contre-épreuve : le même espion VOIT l'écriture d'un jeton reçu", async () => {
    const ecritures = vi.spyOn(Storage.prototype, "setItem");
    retour(() => HttpResponse.json(AVEC_JETON));

    await screen.findByRole("link", { name: /Accéder à ma formation/ });
    expect(ecritures).toHaveBeenCalledWith(expect.any(String), "jeton-neuf");
  });

  it("un jeton que le serveur dit de ne pas ouvrir, ou d'un autre type, n'ouvre rien", async () => {
    for (const charge of [
      { ...AVEC_JETON, connexion_requise: true },
      { ...AVEC_JETON, jeton: "" },
      { ...AVEC_JETON, jeton: 42 },
    ]) {
      const { unmount } = retour(() => HttpResponse.json(charge));
      await screen.findByRole("link", { name: /Me connecter/ });
      expect(jeton.present(), JSON.stringify(charge)).toBe(false);
      unmount();
    }
  });

  it("une session déjà ouverte est gardée, même si un jeton arrive", async () => {
    jeton.ecrire("session-existante");
    retour(() => HttpResponse.json({ ...AVEC_JETON, jeton: "jeton-d-un-autre-compte" }));

    expect(await screen.findByRole("link", { name: /Accéder à ma formation/ })).toHaveAttribute(
      "href",
      `/espace/formations/${MICRO}`,
    );
    expect(jeton.lire()).toBe("session-existante");
  });

  it("une session déjà ouverte est gardée quand aucun jeton n'arrive, et mène à l'espace", async () => {
    jeton.ecrire("session-existante");
    retour(() => HttpResponse.json(SANS_JETON));

    await screen.findByRole("link", { name: /Accéder à ma formation/ });
    expect(jeton.lire()).toBe("session-existante");
    expect(screen.queryByRole("link", { name: /Me connecter/ })).toBeNull();
  });

  it("refusé (409) : la phrase du serveur en alerte, une porte de sortie, aucune session", async () => {
    retour(() =>
      HttpResponse.json(
        { erreur: "Ce paiement ne concerne pas une formation.", code: "achat_autre" },
        { status: 409 },
      ),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Ce paiement ne concerne pas une formation.");
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("link", { name: /Revenir aux formations/ })).toHaveAttribute("href", "/formations");
    expect(screen.getByRole("link", { name: /contact@evkha\.fr/ })).toHaveAttribute(
      "href",
      "mailto:contact@evkha.fr",
    );
    expect(screen.queryByRole("link", { name: /Accéder à ma formation/ })).toBeNull();
    expect(screen.queryByText(/est à vous/)).toBeNull();
    expect(jeton.present()).toBe(false);
  });

  it("trop de tentatives (429) : la phrase du serveur en alerte, pas la panne — et rien n'est dit acquis", async () => {
    const PHRASE = "Trop de confirmations depuis cette connexion. Réessayez dans une heure, ou écrivez-nous à contact@evkha.fr.";
    retour(() => HttpResponse.json({ erreur: PHRASE, code: "trop_de_tentatives" }, { status: 429 }));

    const alerte = await screen.findByRole("alert");
    expect(alerte).toHaveTextContent(PHRASE);
    expect(alerte.textContent).not.toMatch(/Nous n'avons pas pu confirmer|429/);
    expect(screen.queryByText(/est à vous/)).toBeNull();
    expect(screen.getByRole("link", { name: /Revenir aux formations/ })).toBeInTheDocument();
    expect(jeton.present()).toBe(false);
  });

  it("sans session dans l'adresse : « Paiement introuvable », et aucun appel", async () => {
    retour(() => HttpResponse.json(AVEC_JETON), "");

    expect(await screen.findByRole("alert")).toHaveTextContent("Paiement introuvable.");
    expect(confirmations).toEqual([]);
    expect(jeton.present()).toBe(false);
  });

  for (const [nom, reponse] of [
    ["réseau coupé", () => HttpResponse.error()],
    ["réponse 200 qui ne nomme pas la formation", () => HttpResponse.json({})],
    [
      "page d'un relais",
      () => new HttpResponse("<!doctype html><title>EVKHA</title>", { headers: { "Content-Type": "text/html" } }),
    ],
  ] as [string, Reponse][]) {
    it(`${nom} : une panne dite en français — jamais « votre formation est à vous »`, async () => {
      retour(reponse);

      const alerte = await screen.findByRole("alert");
      expect(alerte).toHaveTextContent(/Nous n'avons pas pu confirmer votre paiement/);
      expect(alerte.textContent).not.toMatch(/Failed to fetch|Unexpected|NetworkError/i);
      expect(screen.queryByText(/est à vous/)).toBeNull();
      expect(screen.queryByRole("link", { name: /Accéder à ma formation|Me connecter/ })).toBeNull();
      expect(jeton.present()).toBe(false);
    });
  }

  it("en mode strict, la confirmation ne part qu'une fois", async () => {
    retour(() => HttpResponse.json(AVEC_JETON), "?session=cs_test_9", true);

    await screen.findByRole("link", { name: /Accéder à ma formation/ });
    expect(confirmations).toEqual([{ session: "cs_test_9" }]);
  });
});

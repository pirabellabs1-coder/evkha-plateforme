/** Le portail (connexion, inscription, mot de passe, nouvelle adresse) et le
 * tunnel d'achat (`Acheter`, `RetourPaiement`) sont des pages du socle.
 *
 * Ces écrans portaient l'ancienne charte des pages publiques (`.pp`,
 * `Partenaires.css`) : celui qui cliquait « Espace client » depuis l'accueil
 * refondu changeait de site sous ses yeux. Ils sont passés sous la racine
 * `.acc` le 19/11/2026, et l'ancienne feuille comme l'ancien menu ont été
 * supprimés. Seule la forme a changé — et c'est ce que ce fichier verrouille :
 *
 * 1. chaque écran du portail se tient sous `.acc.prt`, sans rien de l'ancienne
 *    charte, avec un seul `h1` dont le mot d'accent ne perd ni ne double aucun
 *    mot ;
 * 2. son en-tête est celui d'un TUNNEL : le logo et « Retour au site », qui
 *    mènent tous deux à l'accueil — ni méga-menu, ni menu plein écran, ni
 *    pied ;
 * 3. le formulaire reste PREMIER dans le document, avant le visuel, qui est
 *    masqué aux lecteurs d'écran et ne porte rien de focalisable ;
 * 4. les champs gardent leurs attributs `autocomplete`, leur libellé visible,
 *    et un refus est relié au champ par `aria-describedby` ;
 * 5. la page d'achat et son retour se tiennent sous UNE racine `.acc.ach` ;
 * 6. plus aucune source n'importe l'ancienne feuille ni l'ancien menu, les
 *    deux fichiers n'existent plus, et les feuilles du lot ne lisent plus les
 *    alias de `.pp` (`--or`, `--noir`, `--gris`, `--serif`), que plus rien ne
 *    déclare ;
 * 7. un champ fait au moins 48 px de haut.
 *
 * Contre-épreuve (règle 6) en fin de fichier : le détecteur d'alias voit un
 * alias de l'ancienne charte, et laisse passer un jeton.
 *
 * Rejoué contre le code d'avant (`b7c6ae7`, sources remises par `git stash`
 * puis rétablies) : 29 tests rouges sur 33 — la racine était `.pp.prt`, le
 * logo menait à `/partenaires`, aucun refus n'était relié à son champ. Parmi
 * les quatre restés verts, deux ont été lus : la liste des écrans, et les
 * attributs `autocomplete` du mot de passe — ils n'ont pas changé, et c'est
 * ce qu'on verrouille.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { server } from "./server";

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => () => undefined,
  useParams: () => ({ livrable: "etude-de-marche" }),
  Link: ({
    to,
    className,
    children,
  }: {
    to: string;
    className?: string;
    children: React.ReactNode;
  }) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}));

// Importés APRÈS le simulacre du routeur.
const { Connexion } = await import("../public/Connexion");
const { Inscription } = await import("../public/Inscription");
const { DefinirMotDePasse, MotDePasseOublie } = await import("../public/MotDePasse");
const { ConfirmerAdresse } = await import("../public/ConfirmerAdresse");
const { Acheter } = await import("../public/Acheter");
const { RetourPaiement } = await import("../public/RetourPaiement");

const API = `${window.location.origin}/api`;
const SRC = join(process.cwd(), "src");

const LIVRABLES = {
  livrables: [
    { slug: "etude-de-marche", libelle: "Étude de marché", type: "market_study", prix_cents: 14900 },
  ],
};

/** Ce que les écrans chargent en arrivant : Google éteint, aucun rappel de
 *  formule, le catalogue des études. */
function servirLesReglages() {
  server.use(
    http.get(`${API}/public/reglages/`, () =>
      HttpResponse.json({ google: { actif: false, client_id: "" } }),
    ),
    http.get(`${API}/public/formules/`, () => HttpResponse.json({ formules: [] })),
    http.get(`${API}/public/livrables/`, () => HttpResponse.json(LIVRABLES)),
  );
}

function rendre(page: React.ReactElement, adresse: string) {
  window.history.pushState({}, "", adresse);
  return render(page);
}

const ECRANS: { nom: string; adresse: string; titre: string; page: () => React.ReactElement }[] = [
  {
    nom: "connexion",
    adresse: "/espace/connexion",
    titre: "Accéder à votre espace",
    page: () => <Connexion />,
  },
  {
    nom: "inscription",
    adresse: "/inscription",
    titre: "Créer votre espace partenaire",
    page: () => <Inscription />,
  },
  {
    nom: "inscription pour une étude",
    adresse: "/inscription?livrable=etude-de-marche",
    titre: "Créer votre espace",
    page: () => <Inscription />,
  },
  {
    nom: "mot de passe oublié",
    adresse: "/mot-de-passe-oublie",
    titre: "Mot de passe oublié",
    page: () => <MotDePasseOublie />,
  },
  {
    nom: "définir son mot de passe",
    adresse: "/definir-mot-de-passe?id=1&jeton=abc",
    titre: "Choisir votre mot de passe",
    page: () => <DefinirMotDePasse />,
  },
  {
    // Sans jeton dans l'adresse : l'écran le dit, et n'appelle personne.
    nom: "nouvelle adresse",
    adresse: "/confirmer-adresse",
    titre: "Votre nouvelle adresse",
    page: () => <ConfirmerAdresse />,
  },
];

function source(chemin: string): string {
  return readFileSync(join(SRC, chemin), "utf-8").replace(/\r\n/g, "\n");
}

function sansCommentaires(code: string): string {
  return code.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

/** Tous les fichiers de `src` hors des tests, en chemins relatifs. */
function fichiersDeSrc(dossier = ""): string[] {
  return readdirSync(join(SRC, dossier), { withFileTypes: true }).flatMap((entree) => {
    const chemin = dossier === "" ? entree.name : `${dossier}/${entree.name}`;
    if (entree.isDirectory()) return chemin === "test" ? [] : fichiersDeSrc(chemin);
    return /\.(tsx?|css)$/.test(entree.name) ? [chemin] : [];
  });
}

/** Les alias que la racine `.pp` déclarait, et que plus rien ne déclare : une
 *  feuille qui en lirait un perdrait sa couleur ou sa police sans un mot. */
const ALIAS_DE_L_ANCIENNE_CHARTE = /var\(\s*--(?:or|or-fonce|noir|gris|creme|serif)\s*[,)]/g;

function aliasLus(css: string): string[] {
  return sansCommentaires(css).match(ALIAS_DE_L_ANCIENNE_CHARTE) ?? [];
}

/** La hauteur minimale, en pixels, que la PREMIÈRE règle au sélecteur exact
 *  `selecteur` déclare ; `null` si elle n'en déclare pas. */
function hauteurMinimale(css: string, selecteur: string): number | null {
  const regles = [...sansCommentaires(css).matchAll(/([^{}]+)\{([^{}]*)\}/g)];
  const regle = regles.find((m) => m[1].trim() === selecteur);
  const valeur = regle?.[2].match(/min-height\s*:\s*([\d.]+)px/)?.[1];
  return valeur === undefined ? null : Number(valeur);
}

const FOCALISABLES = "a[href], button, input, select, textarea, [tabindex]";

beforeEach(() => {
  localStorage.clear();
  servirLesReglages();
});

afterEach(() => {
  cleanup();
  window.history.pushState({}, "", "/");
});

// ── 1 à 3. La coquille ──────────────────────────────────────────────────────

describe("chaque écran du portail est une page du socle, avec l'en-tête d'un tunnel", () => {
  it("la liste des écrans couvre les cinq composants", () => {
    // Règle 1 : une liste vide ferait passer toutes les boucles.
    expect(ECRANS.length).toBeGreaterThanOrEqual(6);
    expect(new Set(ECRANS.map((ecran) => ecran.adresse)).size).toBe(ECRANS.length);
  });

  for (const ecran of ECRANS) {
    it(`${ecran.nom} : racine du socle, un seul h1, plus rien de l'ancienne charte`, () => {
      rendre(ecran.page(), ecran.adresse);

      expect(document.querySelector(".acc.prt")).not.toBeNull();
      expect(document.querySelector('.pp, [class*="pp-"], [class*="insc-"]')).toBeNull();

      const titres = screen.getAllByRole("heading", { level: 1 });
      expect(titres).toHaveLength(1);
      // Le mot d'accent est un morceau du titre : rien n'est perdu ni doublé.
      expect(titres[0].textContent).toBe(ecran.titre);
      const accents = titres[0].querySelectorAll(".acc-s");
      expect(accents).toHaveLength(1);
      expect((accents[0].textContent ?? "").trim().length).toBeGreaterThan(3);
      expect(ecran.titre).toContain(accents[0].textContent ?? "");
      expect(document.title).toBe(`${ecran.titre} — EVKHA`);
    });

    it(`${ecran.nom} : le logo et « Retour au site » mènent à l'accueil, sans menu ni pied`, () => {
      rendre(ecran.page(), ecran.adresse);

      const barre = screen.getByRole("banner");
      const liens = within(barre).getAllByRole("link");
      expect(liens.map((lien) => lien.getAttribute("href"))).toEqual(["/", "/"]);
      expect(within(barre).getByRole("link", { name: "EVKHA, accueil" })).toBe(liens[0]);
      expect(within(barre).getByRole("link", { name: /Retour au site/ })).toBe(liens[1]);
      // Rien qui distraie du formulaire : ni rubrique, ni menu plein écran.
      expect(within(barre).queryAllByRole("button")).toEqual([]);
      expect(screen.queryByRole("navigation", { name: "Principale" })).toBeNull();
      expect(screen.queryByRole("navigation", { name: "Menu" })).toBeNull();
      expect(screen.queryByRole("contentinfo")).toBeNull();

      // Le lien d'évitement est le premier lien du document, et vise le contenu.
      const principal = screen.getByRole("main");
      expect(principal.id).not.toBe("");
      const evitement = screen.getByRole("link", { name: "Aller au contenu" });
      expect(evitement).toHaveAttribute("href", `#${principal.id}`);
      expect(document.querySelector("a")).toBe(evitement);
    });

    it(`${ecran.nom} : le formulaire précède le visuel, qui se tait`, () => {
      rendre(ecran.page(), ecran.adresse);

      const principal = screen.getByRole("main");
      const blocs = Array.from(principal.children);
      expect(blocs.map((bloc) => bloc.tagName)).toEqual(["SECTION", "ASIDE"]);
      // Le titre et les onglets sont dans le premier bloc.
      expect(blocs[0]).toContainElement(screen.getByRole("heading", { level: 1 }));
      const onglets = within(blocs[0] as HTMLElement).getByRole("navigation", {
        name: "Accès à votre espace",
      });
      expect(
        within(onglets)
          .getAllByRole("link")
          .map((lien) => lien.getAttribute("href")),
      ).toEqual(["/inscription", "/espace/connexion"]);
      expect(within(onglets).getAllByRole("link").filter((lien) => lien.getAttribute("aria-current") === "page")).toHaveLength(1);

      // Le visuel argumente, il n'informe pas : masqué, et rien n'y prend le focus.
      expect(blocs[1]).toHaveAttribute("aria-hidden", "true");
      expect(blocs[1].querySelectorAll(FOCALISABLES)).toHaveLength(0);
      const photo = blocs[1].querySelector("img");
      expect(photo).not.toBeNull();
      expect(photo).toHaveAttribute("width");
      expect(photo).toHaveAttribute("height");
      expect(photo?.getAttribute("src") ?? "").toMatch(/^\/partenaires\//);
    });
  }
});

// ── 4. Les champs ───────────────────────────────────────────────────────────

describe("les champs gardent leur saisie automatique, et un refus est relié à son champ", () => {
  it("connexion : e-mail et mot de passe courant ; le refus est relié aux deux champs", async () => {
    server.use(http.post(`${API}/espace/connexion/`, () => HttpResponse.error()));
    rendre(<Connexion />, "/espace/connexion");

    const email = screen.getByLabelText("Adresse e-mail");
    const motDePasse = screen.getByLabelText("Mot de passe");
    expect(email).toHaveAttribute("type", "email");
    expect(email).toHaveAttribute("autocomplete", "email");
    expect(motDePasse).toHaveAttribute("type", "password");
    expect(motDePasse).toHaveAttribute("autocomplete", "current-password");
    // Avant tout refus, aucun champ ne renvoie à un message qui n'existe pas.
    expect(email).not.toHaveAttribute("aria-describedby");
    expect(motDePasse).not.toHaveAttribute("aria-describedby");

    fireEvent.change(email, { target: { value: "eva@exemple.fr" } });
    fireEvent.change(motDePasse, { target: { value: "un mot de passe" } });
    fireEvent.click(screen.getByRole("button", { name: "Se connecter" }));

    const alerte = await screen.findByRole("alert");
    expect((alerte.textContent ?? "").trim().length).toBeGreaterThan(10);
    expect(alerte.id).not.toBe("");
    expect(email).toHaveAttribute("aria-describedby", alerte.id);
    expect(motDePasse).toHaveAttribute("aria-describedby", alerte.id);
    expect(screen.getByRole("link", { name: "Mot de passe oublié ?" })).toHaveAttribute(
      "href",
      "/mot-de-passe-oublie",
    );
  });

  it("inscription : cinq champs, leur saisie automatique ; le champ refusé, et lui seul, est relié au refus", async () => {
    server.use(
      http.post(`${API}/public/inscription/`, () =>
        HttpResponse.json(
          { erreur: "Un compte existe déjà pour cette adresse.", code: "deja_membre" },
          { status: 409 },
        ),
      ),
    );
    rendre(<Inscription />, "/inscription");

    const champs = {
      raison: screen.getByLabelText("Raison sociale"),
      prenom: screen.getByLabelText("Prénom"),
      nom: screen.getByLabelText("Nom"),
      email: screen.getByLabelText("Adresse e-mail"),
      motDePasse: screen.getByLabelText(/^Mot de passe/),
    };
    expect(champs.raison).toHaveAttribute("autocomplete", "organization");
    expect(champs.prenom).toHaveAttribute("autocomplete", "given-name");
    expect(champs.nom).toHaveAttribute("autocomplete", "family-name");
    expect(champs.email).toHaveAttribute("autocomplete", "email");
    expect(champs.motDePasse).toHaveAttribute("autocomplete", "new-password");
    // L'ordre des champs dans le document n'a pas bougé.
    expect(Array.from(document.querySelectorAll("form input"))).toEqual([
      champs.raison,
      champs.prenom,
      champs.nom,
      champs.email,
      champs.motDePasse,
    ]);

    fireEvent.change(champs.raison, { target: { value: "Cabinet Eva" } });
    fireEvent.change(champs.email, { target: { value: "eva@exemple.fr" } });
    fireEvent.change(champs.motDePasse, { target: { value: "un mot de passe long" } });
    fireEvent.click(screen.getByRole("button", { name: "Créer mon compte" }));

    const alerte = await screen.findByRole("alert");
    expect(alerte).toHaveTextContent("Un compte existe déjà pour cette adresse.");
    expect(within(alerte).getByRole("link", { name: "Se connecter" })).toHaveAttribute(
      "href",
      "/espace/connexion",
    );
    expect(champs.email).toHaveAttribute("aria-invalid", "true");
    expect(champs.email).toHaveAttribute("aria-describedby", alerte.id);
    for (const autre of [champs.raison, champs.motDePasse]) {
      expect(autre).toHaveAttribute("aria-invalid", "false");
      expect(autre).not.toHaveAttribute("aria-describedby");
    }
  });

  it("mot de passe : la saisie automatique dit « nouveau », deux fois, puis « e-mail »", () => {
    rendre(<DefinirMotDePasse />, "/definir-mot-de-passe?id=1&jeton=abc");
    expect(screen.getByLabelText("Nouveau mot de passe")).toHaveAttribute("autocomplete", "new-password");
    expect(screen.getByLabelText("Confirmer le mot de passe")).toHaveAttribute("autocomplete", "new-password");
    cleanup();

    rendre(<MotDePasseOublie />, "/mot-de-passe-oublie");
    expect(screen.getByLabelText("Adresse e-mail")).toHaveAttribute("autocomplete", "email");
    expect(screen.getByRole("button", { name: "Recevoir un lien" })).toHaveAttribute("type", "submit");
  });
});

// ── 5. Le tunnel d'achat ────────────────────────────────────────────────────

describe("la page d'achat et son retour se tiennent sous une seule racine du socle", () => {
  const PAGES: { nom: string; rendre: () => Promise<unknown> }[] = [
    {
      nom: "page d'achat",
      rendre: () => {
        rendre(<Acheter />, "/acheter/etude-de-marche");
        return screen.findByRole("button", { name: /Payer/ });
      },
    },
    {
      nom: "retour de paiement",
      // Sans identifiant de paiement : la page le dit, et reste affichée.
      rendre: () => {
        rendre(<RetourPaiement />, "/acheter/retour");
        return screen.findByRole("alert");
      },
    },
  ];

  for (const page of PAGES) {
    it(`${page.nom} : une racine .acc.ach, qui contient la barre, la carte et le pied`, async () => {
      await page.rendre();

      const racines = document.querySelectorAll(".acc");
      expect(racines).toHaveLength(1);
      expect(racines[0]).toHaveClass("ach");
      expect(document.querySelector('.pp, [class*="pp-"], .ach-socle')).toBeNull();
      expect(racines[0]).toContainElement(screen.getByRole("banner"));
      expect(racines[0]).toContainElement(screen.getByRole("main"));
      expect(racines[0]).toContainElement(screen.getByRole("contentinfo"));
      expect(screen.getByRole("main").querySelector(".ach-carte")).not.toBeNull();
      expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    });
  }

  it("page d'achat : le champ garde son libellé, sa saisie automatique et son aide", async () => {
    rendre(<Acheter />, "/acheter/etude-de-marche");
    await screen.findByRole("button", { name: /Payer/ });

    const champ = screen.getByLabelText(/Votre adresse e-mail/);
    expect(champ).toHaveAttribute("type", "email");
    expect(champ).toHaveAttribute("autocomplete", "email");
    const aide = document.getElementById(champ.getAttribute("aria-describedby") ?? "");
    expect(aide).toHaveTextContent(/pré-remplir la page de paiement/);
  });
});

// ── 6 et 7. Les sources ─────────────────────────────────────────────────────

describe("l'ancienne feuille et l'ancien menu ont disparu", () => {
  it("les deux fichiers n'existent plus, et aucune source ne les importe", () => {
    expect(existsSync(join(SRC, "public", "Partenaires.css"))).toBe(false);
    expect(existsSync(join(SRC, "public", "MenuSite.tsx"))).toBe(false);

    const fichiers = fichiersDeSrc();
    // Règle 1 : la découverte voit bien les sources de l'application.
    expect(fichiers.length).toBeGreaterThan(80);
    expect(fichiers).toContain("public/Portail.tsx");
    expect(fichiers).toContain("router.tsx");
    const fautifs = fichiers.filter((fichier) =>
      /Partenaires\.css|MenuSite|MENU_SITE|LOGO_SITE/.test(sansCommentaires(source(fichier))),
    );
    expect(fautifs).toEqual([]);
  });

  for (const fichier of ["public/Portail.tsx", "public/Acheter.tsx", "public/RetourPaiement.tsx"]) {
    it(`${fichier} importe le socle, puis sa feuille`, () => {
      const code = sansCommentaires(source(fichier));
      expect(code.length, fichier).toBeGreaterThan(1000);
      expect(code, fichier).toMatch(/import "\.\/Site\.css";\s*import "\.\/(Portail|Acheter)\.css";/);
    });
  }

  for (const feuille of ["public/Portail.css", "public/Acheter.css"]) {
    it(`${feuille} ne lit plus les alias de l'ancienne charte, et ne vise plus ses classes`, () => {
      const css = source(feuille);
      expect(sansCommentaires(css).trim().length, feuille).toBeGreaterThan(1000);
      expect(aliasLus(css), feuille).toEqual([]);
      expect(sansCommentaires(css).match(/\.pp(?![\w])|\.pp-[\w-]+|\.insc-[\w-]+/g) ?? [], feuille).toEqual([]);
      // Elle lit les alias du socle, eux.
      expect(sansCommentaires(css), feuille).toMatch(/var\(--acc-/);
    });
  }

  it("un champ fait au moins 48 px de haut", () => {
    expect(hauteurMinimale(source("public/Portail.css"), ".prt input")).toBeGreaterThanOrEqual(48);
    expect(hauteurMinimale(source("public/Acheter.css"), ".ach .champ-saisie")).toBeGreaterThanOrEqual(48);
  });

  it("contre-épreuve : le détecteur voit un alias de l'ancienne charte, pas un jeton", () => {
    expect(aliasLus(".a { color: var(--or); background: var( --noir ); font-family: var(--serif, serif) }")).toHaveLength(3);
    expect(aliasLus(".a { color: var(--gris) }")).toEqual(["var(--gris)"]);
    expect(aliasLus(".a { color: var(--acc-or); border-color: var(--evkha-gris-doux); }")).toEqual([]);
    expect(aliasLus("/* var(--or) */ .a { color: var(--acc-gris) }")).toEqual([]);
    // Et la lecture d'une hauteur distingue 52 px d'une règle qui n'en dit rien.
    expect(hauteurMinimale(".a input { min-height: 52px; }", ".a input")).toBe(52);
    expect(hauteurMinimale(".a input { height: 30px; }", ".a input")).toBeNull();
    expect(hauteurMinimale(".a input { min-height: 40px; }", ".a input")).toBe(40);
  });
});

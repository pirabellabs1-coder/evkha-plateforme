/** L'en-tête et le pied sont les mêmes sur toutes les pages refondues, et le
 * menu est un méga-menu que l'on conduit au clic comme au clavier.
 *
 * La page d'accueil portait sa barre, son menu plein écran et son pied dans
 * ses propres fichiers ; la page des études portait l'ancien menu
 * (`MenuSite`), dont les entrées ne sont pas les mêmes. Le visiteur qui
 * cliquait « Commander une étude » changeait de menu en changeant de page.
 * Les pages montent désormais `EnTeteSite` et `PiedSite`, qui lisent UNE
 * constante (`contenuSite.NAVIGATION`) — règle 5.
 *
 * Depuis le méga-menu (19/11/2026), cette constante porte cinq RUBRIQUES ;
 * chacune a ses liens et sa carte de mise en avant. Trois lecteurs : la barre
 * (un bouton et un panneau par rubrique), le menu plein écran (un accordéon),
 * le pied (une colonne par rubrique).
 *
 * Les verrous :
 *
 * 1. mêmes rubriques, mêmes liens, même ordre, dans la barre, dans le menu
 *    plein écran ET dans le pied, sur l'accueil ET sur la page des études ;
 * 2. chaque rubrique de la barre est un bouton `aria-expanded="false"` au
 *    repos, relié à un panneau masqué (`hidden`) dont les liens sont hors de
 *    portée d'un lecteur d'écran ;
 * 3. un clic ouvre le panneau et ferme l'autre ; un second clic referme ;
 *    Échap ferme et rend le focus au bouton ; un appui hors de la barre
 *    ferme ; suivre un lien ferme ; le focus qui part vers une autre rubrique
 *    ferme ; les flèches vont d'une rubrique à l'autre ;
 * 4. la rubrique qui contient la page affichée porte `aria-current="true"`,
 *    le lien qui EST cette page `aria-current="page"` — DÉDUITS du chemin ;
 * 5. aucun lien du menu ne sort de la plateforme, sauf la prise de
 *    rendez-vous ; aucun ne mène à l'ancien site ; aucun prix n'y est écrit ;
 * 6. les ancres du menu vers la page des études désignent des sections et des
 *    études qui existent ;
 * 7. le menu plein écran : accordéon replié à l'ouverture, une rubrique à la
 *    fois, et tout ce qui marchait avant (page inerte, Échap, fermeture au
 *    clic d'un lien) ;
 * 8. le lien d'évitement vise le contenu principal de la page où il est.
 *
 * Contre-épreuves (règle 6) : une adresse externe ou une ancre n'est jamais
 * « courante » ; `/etudes/` est la même page que `/etudes` ; `/etudes-de-cas`
 * n'est pas sous `/etudes` ; un appui DANS le panneau ne le ferme pas ; les
 * collecteurs du test voient bien des rubriques et des liens.
 *
 * NON REJOUÉ. La version d'avant de ce test avait été rejouée contre le code
 * d'avant (rouge, 6 tests sur 9). Celle-ci a été écrite le 19/11/2026 SANS
 * être lancée — ni contre le méga-menu, ni contre la barre d'avant : la
 * machine manquait de mémoire pour `vitest`. Tant qu'elle n'a pas tourné, elle
 * ne verrouille rien (règle 6) : la lancer, puis la rejouer contre la barre à
 * liens simples, où les verrous 2 et 3 doivent être rouges.
 *
 * Le survol (ouverture après un délai d'intention, à la souris seulement)
 * n'est pas éprouvé ici : jsdom ne dit pas quel pointeur survole.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { Accueil } from "../public/Accueil";
import { PARCOURS_DES_ETUDES } from "../public/contenuEtudes";
import {
  APPEL_DE_LA_BARRE,
  ESPACE_CLIENT,
  LIENS,
  NAVIGATION,
  PIED,
  PIED_DU_MENU,
  type EntreeDeNavigation,
  type Rubrique,
} from "../public/contenuSite";
import { NosEtudes } from "../public/NosEtudes";
import { adresseDe, cheminDe, contientLaPage, estCourante, estLaPage } from "../public/site";
import { server } from "./server";

const PUBLIC = `${window.location.origin}/api/public`;

/** Les catalogues ne répondent pas : l'en-tête et le pied ne dépendent
 *  d'aucun d'eux, et c'est aussi ce que ce test établit. */
function catalogueMuet() {
  const muet = async () => {
    await delay("infinite");
    return new HttpResponse(null);
  };
  server.use(
    http.get(`${PUBLIC}/livrables/`, muet),
    http.get(`${PUBLIC}/formules/`, muet),
    http.get(`${PUBLIC}/boutique/`, muet),
  );
}

const PAGES = {
  accueil: { chemin: "/", page: <Accueil /> },
  etudes: { chemin: "/etudes", page: <NosEtudes /> },
};
const NOMS = ["accueil", "etudes"] as const;

/** Rend une page À SON ADRESSE : l'en-tête déduit tout du chemin. */
function rendre(nom: keyof typeof PAGES, chemin = PAGES[nom].chemin) {
  catalogueMuet();
  window.history.pushState({}, "", chemin);
  return render(PAGES[nom].page);
}

// ── Ce que les données promettent ───────────────────────────────────────────

const LIBELLES = NAVIGATION.map((rubrique) => rubrique.libelle);

/** Les adresses d'une rubrique, dans l'ordre où la barre et le menu plein
 *  écran les rendent : ses liens, puis sa carte de mise en avant. */
function adressesDe(rubrique: Rubrique): string[] {
  return [...rubrique.liens.map((lien) => lien.lien), rubrique.enAvant.lien];
}

/** Le pied, lui, ne rend que les liens : pas la carte. */
function adressesAuPied(rubrique: Rubrique): string[] {
  return rubrique.liens.map((lien) => lien.lien);
}

const ESPACE = adresseDe(ESPACE_CLIENT, "/");
const CONTACT = adresseDe(APPEL_DE_LA_BARRE, "/");

// ── Ce que la page rend ─────────────────────────────────────────────────────

type Lien = { texte: string; href: string | null; courant: string | null };

/** Tous les liens d'un conteneur, masqués compris. */
function liens(conteneur: HTMLElement): Lien[] {
  return within(conteneur)
    .queryAllByRole("link", { hidden: true })
    .map((a) => ({
      texte: a.textContent ?? "",
      href: a.getAttribute("href"),
      courant: a.getAttribute("aria-current"),
    }));
}

const adresses = (conteneur: HTMLElement) => liens(conteneur).map((lien) => lien.href);

function boutons(conteneur: HTMLElement): HTMLElement[] {
  return within(conteneur).queryAllByRole("button", { hidden: true });
}

/** La barre : la navigation « Principale ». */
function barre(): HTMLElement {
  return screen.getByRole("navigation", { name: "Principale" });
}

/** Le menu plein écran. Fermé, il est masqué par la feuille (que jsdom ne
 *  charge pas) : on le lit par son identifiant. */
function menu(): HTMLElement {
  const nav = document.getElementById("acc-menu");
  if (!nav) throw new Error("menu plein écran introuvable");
  return nav;
}

function pied(): HTMLElement {
  return screen.getByRole("contentinfo");
}

/** Ce qu'un bouton de rubrique commande : son panneau dans la barre, sa liste
 *  dans l'accordéon. */
function commande(bouton: HTMLElement): HTMLElement {
  const cible = document.getElementById(bouton.getAttribute("aria-controls") ?? "");
  if (!cible) throw new Error(`« ${bouton.textContent} » ne commande aucun élément`);
  return cible;
}

/** Ce qu'une page rend de son menu : rubrique par rubrique, puis lien par
 *  lien. C'est ce qui doit être identique d'une page à l'autre. */
function releve() {
  const parRubrique = (conteneur: HTMLElement) =>
    boutons(conteneur).map((bouton) => ({
      rubrique: bouton.textContent,
      adresses: adresses(commande(bouton)),
    }));
  return {
    barre: parRubrique(barre()),
    barreEntiere: adresses(barre()),
    menu: parRubrique(menu()),
    menuEntier: adresses(menu()),
    pied: liens(pied()).map((lien) => ({ texte: lien.texte, href: lien.href })),
  };
}

/** Retient un clic sur le lien lui-même : jsdom ne sait pas changer de page,
 *  et ce n'est pas la navigation qu'on éprouve, c'est la fermeture. */
function sansNaviguer(lien: HTMLElement): HTMLElement {
  lien.addEventListener("click", (evenement) => evenement.preventDefault());
  return lien;
}

describe("l'en-tête est le même sur toutes les pages refondues", () => {
  afterEach(() => {
    cleanup();
    window.history.pushState({}, "", "/");
  });

  // ── 1. Une seule structure, trois lecteurs, toutes les pages ──────────────

  it("mêmes rubriques, mêmes liens, même ordre, dans la barre, le menu et le pied, sur l'accueil et sur les études", () => {
    // Règle 1 : une constante vide ferait passer toutes les égalités.
    expect(LIBELLES).toEqual(["Études & livrables", "Accompagnement", "Formations", "Professionnels", "Ressources"]);
    for (const rubrique of NAVIGATION) {
      expect(rubrique.liens.length, rubrique.libelle).toBeGreaterThanOrEqual(2);
    }
    const attendues = NAVIGATION.map((rubrique) => ({ rubrique: rubrique.libelle, adresses: adressesDe(rubrique) }));

    rendre("accueil");
    const surAccueil = releve();
    cleanup();
    rendre("etudes");
    const surEtudes = releve();

    expect(surAccueil.barre).toEqual(attendues);
    expect(surAccueil.menu).toEqual(attendues);
    // Hors des panneaux : l'espace client, à droite de la barre et en bas du
    // menu plein écran.
    expect(surAccueil.barreEntiere).toEqual([...NAVIGATION.flatMap(adressesDe), ESPACE]);
    expect(surAccueil.menuEntier).toEqual([
      ...NAVIGATION.flatMap(adressesDe),
      ...PIED_DU_MENU.map((entree) => adresseDe(entree, "/")),
    ]);
    expect(PIED_DU_MENU).toContain(ESPACE_CLIENT);
    expect(surEtudes).toEqual(surAccueil);
  });

  it("chaque lien d'un panneau porte son titre et sa ligne de description", () => {
    rendre("accueil");
    for (const [k, bouton] of boutons(barre()).entries()) {
      const rubrique = NAVIGATION[k];
      const rendus = liens(commande(bouton));
      for (const [n, lien] of rubrique.liens.entries()) {
        expect(lien.description.length, lien.libelle).toBeGreaterThan(5);
        expect(rendus[n].texte, lien.libelle).toBe(`${lien.libelle}${lien.description}`);
      }
      // La carte de mise en avant : un message, et un bouton qui est un lien.
      expect(commande(bouton)).toHaveTextContent(rubrique.enAvant.titre);
      expect(commande(bouton)).toHaveTextContent(rubrique.enAvant.corps);
      expect(rendus[rubrique.liens.length].texte).toContain(rubrique.enAvant.bouton);
    }
  });

  it("le libellé court d'une rubrique est le début de son libellé", () => {
    const courts = NAVIGATION.filter((rubrique) => rubrique.court !== undefined);
    expect(courts.length).toBeGreaterThan(0);
    for (const rubrique of courts) {
      expect(rubrique.libelle.startsWith(rubrique.court as string), rubrique.libelle).toBe(true);
      expect(rubrique.court).not.toBe(rubrique.libelle);
    }
    // Rendu en deux morceaux, le bouton porte toujours le libellé entier.
    rendre("accueil");
    expect(boutons(barre()).map((bouton) => bouton.textContent)).toEqual(LIBELLES);
    expect(new Set(NAVIGATION.map((rubrique) => rubrique.id)).size).toBe(NAVIGATION.length);
  });

  // ── 2 et 3. Le méga-menu se conduit au clic et au clavier ─────────────────

  for (const nom of NOMS) {
    it(`${nom} : au repos, chaque rubrique est un bouton replié dont le panneau est masqué`, () => {
      rendre(nom);
      const rubriques = boutons(barre());
      expect(rubriques).toHaveLength(NAVIGATION.length);
      for (const bouton of rubriques) {
        expect(bouton.tagName).toBe("BUTTON");
        expect(bouton).toHaveAttribute("type", "button");
        expect(bouton).toHaveAttribute("aria-expanded", "false");
        expect(commande(bouton)).toHaveAttribute("hidden");
        // Le panneau suit son bouton dans le document : Tab parcourt ses
        // liens avant de passer à la rubrique suivante.
        expect(bouton.nextElementSibling).toBe(commande(bouton));
      }
      // Hors de portée d'un lecteur d'écran : seul l'espace client reste.
      expect(within(barre()).getAllByRole("link").map((a) => a.getAttribute("href"))).toEqual([ESPACE]);
      // Des liens de navigation, pas un menu d'application.
      expect(document.querySelector("[role='menu'], [role='menubar'], [role='menuitem']")).toBeNull();
    });

    it(`${nom} : un clic ouvre le panneau et ferme l'autre, un second clic referme`, () => {
      rendre(nom);
      const [premier, second] = boutons(barre());

      fireEvent.click(premier);
      expect(premier).toHaveAttribute("aria-expanded", "true");
      expect(commande(premier)).not.toHaveAttribute("hidden");
      expect(second).toHaveAttribute("aria-expanded", "false");
      // Ouvert, ses liens sont à portée.
      expect(within(commande(premier)).getAllByRole("link").map((a) => a.getAttribute("href"))).toEqual(
        adressesDe(NAVIGATION[0]),
      );

      fireEvent.click(second);
      expect(premier).toHaveAttribute("aria-expanded", "false");
      expect(commande(premier)).toHaveAttribute("hidden");
      expect(second).toHaveAttribute("aria-expanded", "true");
      expect(commande(second)).not.toHaveAttribute("hidden");
      expect(boutons(barre()).filter((b) => b.getAttribute("aria-expanded") === "true")).toHaveLength(1);

      fireEvent.click(second);
      expect(second).toHaveAttribute("aria-expanded", "false");
      expect(commande(second)).toHaveAttribute("hidden");
    });
  }

  it("Échap ferme le panneau et rend le focus à son bouton", () => {
    rendre("accueil");
    const [, second] = boutons(barre());

    // Sans panneau ouvert, Échap ne déplace rien.
    fireEvent.keyDown(window, { key: "Escape" });
    expect(second).not.toHaveFocus();

    fireEvent.click(second);
    expect(second).toHaveAttribute("aria-expanded", "true");
    // Une autre touche ne ferme rien.
    fireEvent.keyDown(window, { key: "a" });
    expect(second).toHaveAttribute("aria-expanded", "true");

    fireEvent.keyDown(window, { key: "Escape" });
    expect(second).toHaveAttribute("aria-expanded", "false");
    expect(commande(second)).toHaveAttribute("hidden");
    expect(second).toHaveFocus();
  });

  it("un appui hors de la barre ferme le panneau ; un appui dedans ne le ferme pas", () => {
    rendre("accueil");
    const [premier] = boutons(barre());
    fireEvent.click(premier);

    fireEvent.pointerDown(commande(premier));
    expect(premier).toHaveAttribute("aria-expanded", "true");

    fireEvent.pointerDown(screen.getByRole("main"));
    expect(premier).toHaveAttribute("aria-expanded", "false");
  });

  it("suivre un lien du panneau le referme", () => {
    rendre("etudes");
    const [premier] = boutons(barre());
    fireEvent.click(premier);

    fireEvent.click(sansNaviguer(within(commande(premier)).getAllByRole("link")[0]));
    expect(premier).toHaveAttribute("aria-expanded", "false");
    expect(commande(premier)).toHaveAttribute("hidden");
  });

  it("le focus qui part vers une autre rubrique ferme le panneau ; celui qui reste dedans, non", () => {
    rendre("accueil");
    const [premier, second] = boutons(barre());
    fireEvent.click(premier);
    const dedans = within(commande(premier)).getAllByRole("link")[0];

    fireEvent.blur(premier, { relatedTarget: dedans });
    expect(premier).toHaveAttribute("aria-expanded", "true");
    // Un focus qui ne va nulle part (clic sur une zone sans lien du panneau).
    fireEvent.blur(dedans, { relatedTarget: null });
    expect(premier).toHaveAttribute("aria-expanded", "true");

    fireEvent.blur(dedans, { relatedTarget: second });
    expect(premier).toHaveAttribute("aria-expanded", "false");
  });

  it("les flèches gauche et droite vont d'une rubrique à l'autre, en boucle", () => {
    rendre("accueil");
    const rubriques = boutons(barre());
    const [premier, second] = rubriques;
    const dernier = rubriques[rubriques.length - 1];

    premier.focus();
    fireEvent.keyDown(premier, { key: "ArrowRight" });
    expect(second).toHaveFocus();
    fireEvent.keyDown(second, { key: "ArrowLeft" });
    expect(premier).toHaveFocus();
    fireEvent.keyDown(premier, { key: "ArrowLeft" });
    expect(dernier).toHaveFocus();
    fireEvent.keyDown(dernier, { key: "ArrowRight" });
    expect(premier).toHaveFocus();
    // Les flèches déplacent le focus : elles n'ouvrent rien.
    expect(rubriques.filter((b) => b.getAttribute("aria-expanded") === "true")).toEqual([]);
  });

  // ── 4. La page courante, déduite du chemin ────────────────────────────────

  it("sur /etudes, « Études & livrables » est la rubrique courante — dans la barre et dans le menu, et elle seule", () => {
    rendre("etudes");
    for (const conteneur of [barre(), menu()]) {
      expect(
        boutons(conteneur)
          .filter((bouton) => bouton.getAttribute("aria-current") !== null)
          .map((bouton) => [bouton.textContent, bouton.getAttribute("aria-current")]),
      ).toEqual([["Études & livrables", "true"]]);
      // Un seul lien EST la page : celui de la carte de mise en avant. Les
      // liens à ancre (`/etudes#…`) désignent des sections, pas la page.
      expect(
        liens(conteneur)
          .filter((lien) => lien.courant !== null)
          .map((lien) => [lien.href, lien.courant]),
      ).toEqual([["/etudes", "page"]]);
    }
  });

  it("une barre oblique finale ne change pas la page courante", () => {
    rendre("etudes", "/etudes/");
    expect(
      boutons(barre())
        .filter((bouton) => bouton.getAttribute("aria-current") === "true")
        .map((bouton) => bouton.textContent),
    ).toEqual(["Études & livrables"]);
    expect(liens(barre()).filter((lien) => lien.courant === "page").map((lien) => lien.href)).toEqual(["/etudes"]);
  });

  it("sur l'accueil, rien n'est courant : aucune rubrique ne mène à l'accueil", () => {
    rendre("accueil");
    for (const conteneur of [barre(), menu()]) {
      expect(boutons(conteneur).filter((bouton) => bouton.getAttribute("aria-current") !== null)).toEqual([]);
      expect(liens(conteneur).filter((lien) => lien.courant !== null)).toEqual([]);
    }
  });

  // ── 5. Où mènent les liens, et ce qu'ils n'écrivent pas ───────────────────

  it("« Espace client » et « Me contacter » : à droite de la barre, aux mêmes adresses sur les deux pages", () => {
    expect(ESPACE).toBe("/espace/connexion");
    expect(CONTACT).toBe("/contact");
    for (const nom of NOMS) {
      rendre(nom);
      expect(within(barre()).getByRole("link", { name: "Espace client" })).toHaveAttribute("href", ESPACE);
      const appel = screen.getByRole("link", { name: /Me contacter/ });
      expect(appel).toHaveAttribute("href", CONTACT);
      expect(screen.getByRole("banner")).toContainElement(appel);
      // En bas du menu plein écran, hors de l'accordéon.
      const piedDuMenu = menu().querySelector<HTMLElement>(".acc-menu-pied");
      expect(piedDuMenu).not.toBeNull();
      expect(adresses(piedDuMenu as HTMLElement)).toEqual(PIED_DU_MENU.map((entree) => adresseDe(entree, "/")));
      cleanup();
    }
  });

  it("chaque lien du menu est interne, sauf la prise de rendez-vous ; aucun ne mène à l'ancien site", () => {
    const interne = (href: string | null) => href !== null && (href.startsWith("/") || href.startsWith("#"));

    // Dans les données.
    const ecrits = [...NAVIGATION.flatMap(adressesDe), ESPACE, CONTACT, ...PIED.liens.map((lien) => lien.lien)];
    expect(ecrits.length).toBeGreaterThan(25);
    expect(ecrits.filter((lien) => !interne(lien))).toEqual([LIENS.appel]);
    expect(LIENS.appel).toMatch(/^https:\/\/calendly\.com\//);

    // Et dans ce que chaque page rend.
    for (const nom of NOMS) {
      rendre(nom);
      const rendus = [
        ...liens(screen.getByRole("banner")),
        ...liens(menu()),
        ...liens(within(pied()).getByRole("navigation", { name: PIED.plan })),
        ...liens(within(pied()).getByRole("navigation", { name: PIED.navigation })),
      ];
      expect(rendus.length, nom).toBeGreaterThan(50);
      expect(new Set(rendus.filter((lien) => !interne(lien.href)).map((lien) => lien.href)), nom).toEqual(
        new Set([LIENS.appel]),
      );
      // Réseaux compris : plus rien ne pointe vers l'ancien site.
      for (const lien of [...rendus, ...liens(pied())]) {
        expect(lien.href, lien.texte).not.toMatch(/evkha\.fr/i);
      }
      // Sur une page, aucun lien de l'en-tête ne vise une ancre locale qui
      // n'existe pas.
      for (const lien of rendus) {
        if (lien.href?.startsWith("#")) {
          expect(document.querySelector(lien.href), lien.texte).not.toBeNull();
        }
      }
      cleanup();
    }
  });

  it("aucun prix dans le menu ni dans le pied", () => {
    const MONTANT = /€|\beuros?\b/i;
    // Dans les données : tout ce que le menu peut écrire.
    const ecrit = JSON.stringify([NAVIGATION, ESPACE_CLIENT, APPEL_DE_LA_BARRE, PIED]);
    expect(ecrit.length).toBeGreaterThan(2000);
    expect(ecrit).not.toMatch(MONTANT);

    for (const nom of NOMS) {
      rendre(nom);
      for (const zone of [screen.getByRole("banner"), menu(), pied()]) {
        expect((zone.textContent ?? "").length, nom).toBeGreaterThan(100);
        expect(zone.textContent, nom).not.toMatch(MONTANT);
      }
      cleanup();
    }
    // Contre-épreuve : le détecteur voit un prix.
    expect("dès 89 €").toMatch(MONTANT);
    expect("185 euros").toMatch(MONTANT);
    expect("Un projet, quatre documents").not.toMatch(MONTANT);
  });

  // ── 6. Les ancres vers la page des études ─────────────────────────────────

  it("les ancres du menu vers /etudes désignent des études du parcours et des sections qui existent", () => {
    const versLesEtudes = NAVIGATION.flatMap(adressesDe).filter((lien) => lien.startsWith(`${LIENS.etudes}#`));
    const PREFIXE = `${LIENS.etudes}#carte-`;
    const cartes = versLesEtudes.filter((lien) => lien.startsWith(PREFIXE)).map((lien) => lien.slice(PREFIXE.length));
    const sections = versLesEtudes.filter((lien) => !lien.startsWith(PREFIXE)).map((lien) => lien.split("#")[1]);

    // Les quatre documents sur mesure, dans l'ordre du parcours.
    expect(cartes).toHaveLength(4);
    expect(PARCOURS_DES_ETUDES.filter((slug) => cartes.includes(slug))).toEqual(cartes);

    // Les sections sont dans la page dès le premier rendu, catalogue muet. Les
    // cartes, elles, n'arrivent qu'avec le catalogue : leur identifiant
    // (`carte-<slug>`) est éprouvé par `la-page-des-etudes-lit-ses-prix-au-serveur`.
    expect(sections).toEqual(["comment-ca-marche"]);
    rendre("etudes");
    for (const section of sections) {
      expect(document.getElementById(section), section).not.toBeNull();
    }
  });

  // ── 7 et 8. Le menu plein écran, l'évitement ──────────────────────────────

  for (const nom of NOMS) {
    it(`${nom} : le logo mène à l'accueil, l'évitement au contenu, et un lien referme le menu`, () => {
      rendre(nom);
      expect(screen.getByRole("link", { name: "EVKHA, accueil" })).toHaveAttribute("href", "/");

      const principal = screen.getByRole("main");
      expect(principal.id).not.toBe("");
      expect(screen.getByRole("link", { name: "Aller au contenu" })).toHaveAttribute("href", `#${principal.id}`);
      // Le lien d'évitement est le PREMIER lien de la page.
      expect(document.querySelector("a")).toBe(screen.getByRole("link", { name: "Aller au contenu" }));

      const ouvrir = screen.getByRole("button", { name: "Ouvrir le menu" });
      expect(ouvrir).toHaveAttribute("aria-controls", "acc-menu");
      fireEvent.click(ouvrir);
      expect(ouvrir).toHaveAttribute("aria-expanded", "true");
      expect(screen.getByRole("button", { name: "Fermer le menu" })).toBe(ouvrir);
      // Derrière le menu ouvert, ni le contenu ni le pied ne prennent le focus.
      expect(principal).toHaveAttribute("inert");
      expect(screen.getByRole("contentinfo", { hidden: true })).toHaveAttribute("inert");
      // Échap referme et rend le focus au bouton.
      fireEvent.keyDown(window, { key: "Escape" });
      expect(ouvrir).toHaveAttribute("aria-expanded", "false");
      expect(ouvrir).toHaveFocus();
      // Un lien du menu le referme aussi.
      fireEvent.click(ouvrir);
      expect(ouvrir).toHaveAttribute("aria-expanded", "true");
      fireEvent.click(sansNaviguer(within(menu()).getAllByRole("link", { hidden: true })[0]));
      expect(ouvrir).toHaveAttribute("aria-expanded", "false");
      expect(principal).not.toHaveAttribute("inert");
    });

    it(`${nom} : le menu plein écran est un accordéon, replié à l'ouverture, une rubrique à la fois`, () => {
      rendre(nom);
      const ouvrir = screen.getByRole("button", { name: "Ouvrir le menu" });
      fireEvent.click(ouvrir);

      const rubriques = boutons(menu());
      expect(rubriques.map((bouton) => bouton.textContent)).toEqual(LIBELLES);
      for (const bouton of rubriques) {
        expect(bouton.tagName).toBe("BUTTON");
        expect(bouton).toHaveAttribute("aria-expanded", "false");
        expect(commande(bouton)).toHaveAttribute("hidden");
      }

      const [premier, second] = rubriques;
      fireEvent.click(premier);
      expect(premier).toHaveAttribute("aria-expanded", "true");
      expect(commande(premier)).not.toHaveAttribute("hidden");
      // Déplier une rubrique ne referme pas le menu : ce n'est pas un lien.
      expect(ouvrir).toHaveAttribute("aria-expanded", "true");

      fireEvent.click(second);
      expect(premier).toHaveAttribute("aria-expanded", "false");
      expect(commande(premier)).toHaveAttribute("hidden");
      expect(second).toHaveAttribute("aria-expanded", "true");

      fireEvent.click(second);
      expect(second).toHaveAttribute("aria-expanded", "false");

      // Refermé puis rouvert, le menu revient replié.
      fireEvent.click(second);
      fireEvent.click(ouvrir);
      fireEvent.click(ouvrir);
      expect(boutons(menu()).filter((b) => b.getAttribute("aria-expanded") === "true")).toEqual([]);
    });
  }

  // ── Le pied ───────────────────────────────────────────────────────────────

  it("le pied lit la même structure : une colonne par rubrique, puis les réseaux et les pages légales", () => {
    const attendus = [
      ...NAVIGATION.flatMap((rubrique) => rubrique.liens.map((lien) => ({ texte: lien.libelle, href: lien.lien }))),
      ...PIED.reseaux.map((lien) => ({ texte: lien.libelle, href: lien.lien })),
      ...PIED.liens.map((lien) => ({ texte: lien.libelle, href: lien.lien })),
    ];
    expect(PIED.reseaux.length).toBeGreaterThanOrEqual(3);
    // Les pages légales sont celles de la plateforme.
    expect(PIED.liens.map((lien) => lien.lien).sort()).toEqual(
      ["/cgv", "/mentions-legales", "/politique-de-confidentialite", "/rgpd"],
    );

    rendre("accueil");
    const surAccueil = liens(pied());
    const signature = pied().textContent;
    // Une colonne par rubrique : une liste nommée par son libellé.
    const plan = within(pied()).getByRole("navigation", { name: PIED.plan });
    for (const rubrique of NAVIGATION) {
      expect(adresses(within(plan).getByRole("list", { name: rubrique.libelle })), rubrique.libelle).toEqual(
        adressesAuPied(rubrique),
      );
    }
    // Les réseaux sortent de la plateforme sans lui laisser la main.
    for (const reseau of PIED.reseaux) {
      expect(within(pied()).getByRole("link", { name: reseau.libelle })).toHaveAttribute("rel", "noopener");
    }
    cleanup();
    rendre("etudes");

    expect(surAccueil.map(({ texte, href }) => ({ texte, href }))).toEqual(attendus);
    // Courant compris : le pied ne marque aucune page.
    expect(liens(pied())).toEqual(surAccueil);
    expect(surAccueil.filter((lien) => lien.courant !== null)).toEqual([]);
    expect(pied().textContent).toBe(signature);
    expect(signature).toContain(PIED.signature);
  });

  // ── Contre-épreuves ───────────────────────────────────────────────────────

  it("contre-épreuve : seule une page interne est « courante », et une ancre suit la page où l'on est", () => {
    const page: EntreeDeNavigation = { libelle: "Les études", lien: "/etudes" };
    const ancre: EntreeDeNavigation = { libelle: "La méthode", ancre: "methode" };
    const externe: EntreeDeNavigation = { libelle: "Formations", lien: "https://www.evkha.fr/etudes" };

    expect(estCourante(page, "/etudes")).toBe(true);
    expect(estCourante(page, "/")).toBe(false);
    expect(estCourante(page, "/etudes/detail")).toBe(false);
    expect(estCourante({ libelle: "x", lien: "/etudes/" }, "/etudes")).toBe(true);
    // Une ancre désigne une section, une adresse externe un autre site —
    // même quand son chemin ressemble à celui de la page.
    expect(estCourante(ancre, "/")).toBe(false);
    expect(estCourante(externe, "/etudes")).toBe(false);

    expect(adresseDe(page, "/")).toBe("/etudes");
    expect(adresseDe(page, "/boutique")).toBe("/etudes");
    expect(adresseDe(ancre, "/")).toBe("#methode");
    expect(adresseDe(ancre, "/etudes")).toBe("/#methode");
    // Le contact est désormais une page : la même adresse partout.
    expect(adresseDe(APPEL_DE_LA_BARRE, "/")).toBe("/contact");
    expect(adresseDe(APPEL_DE_LA_BARRE, "/etudes")).toBe("/contact");
  });

  it("contre-épreuve : un lien à ancre n'est pas la page, et une rubrique ne s'attribue que ses pages", () => {
    expect(estLaPage("/etudes", "/etudes")).toBe(true);
    expect(estLaPage("/etudes/", "/etudes")).toBe(true);
    expect(estLaPage("/etudes#comment-ca-marche", "/etudes")).toBe(false);
    expect(estLaPage("https://calendly.com/etudes", "/etudes")).toBe(false);

    expect(cheminDe("/etudes#carte-etude-marche")).toBe("/etudes");
    expect(cheminDe("/packs/essentiel/")).toBe("/packs/essentiel");
    expect(cheminDe("/")).toBe("/");
    expect(cheminDe("#contact")).toBeNull();
    expect(cheminDe(LIENS.appel)).toBeNull();

    const rubriqueDe = (ici: string) =>
      NAVIGATION.filter((rubrique) => contientLaPage(rubrique, ici)).map((rubrique) => rubrique.id);
    expect(rubriqueDe("/etudes")).toEqual(["etudes"]);
    // Une page SOUS une page du menu est dans sa rubrique.
    expect(rubriqueDe("/boutique/une-etude-prete")).toEqual(["etudes"]);
    expect(rubriqueDe("/packs/premium")).toEqual(["accompagnement"]);
    expect(rubriqueDe("/formations/methode-pop")).toEqual(["formations"]);
    expect(rubriqueDe("/partenaires")).toEqual(["professionnels"]);
    expect(rubriqueDe("/contact")).toEqual(["ressources"]);
    // Segment par segment : un chemin qui COMMENCE comme une page du menu
    // n'est pas sous elle. Et ni l'accueil ni l'espace client n'ont de rubrique.
    expect(rubriqueDe("/etudes-de-cas")).toEqual([]);
    expect(rubriqueDe("/")).toEqual([]);
    expect(rubriqueDe("/espace/connexion")).toEqual([]);
    // Chaque page du menu a UNE rubrique : aucune adresse interne n'est
    // partagée entre deux rubriques.
    for (const rubrique of NAVIGATION) {
      for (const lien of adressesDe(rubrique)) {
        const chemin = cheminDe(lien);
        if (chemin !== null) expect(rubriqueDe(chemin), lien).toEqual([rubrique.id]);
      }
    }
  });
});

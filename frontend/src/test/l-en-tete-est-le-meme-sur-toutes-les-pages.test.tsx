/** L'en-tête et le pied sont les mêmes sur toutes les pages refondues.
 *
 * La page d'accueil portait sa barre, son menu plein écran et son pied dans
 * ses propres fichiers ; la page des études portait l'ancien menu
 * (`MenuSite`), dont les entrées ne sont pas les mêmes. Le visiteur qui
 * cliquait « Commander une étude » changeait de menu en changeant de page.
 * Les deux pages montent désormais `EnTeteSite` et `PiedSite`, qui lisent UNE
 * constante (`contenuSite.NAVIGATION`, `contenuSite.PIED`) — règle 5.
 *
 * Les verrous :
 *
 * 1. mêmes entrées, même ordre, dans la barre ET dans le menu plein écran, sur
 *    l'accueil ET sur la page des études — celles de `NAVIGATION` ;
 * 2. l'entrée de la page affichée porte `aria-current="page"`, DÉDUITE du
 *    chemin : « Les études » sur `/etudes`, aucune sur l'accueil ;
 * 3. « La méthode » et « Me contacter » sont des sections de l'accueil : des
 *    ancres sur l'accueil, des liens vers l'accueil ailleurs — et ces sections
 *    EXISTENT sur l'accueil, sinon le lien ne mène nulle part ;
 * 4. le lien d'évitement vise le contenu principal de la page où il est ;
 * 5. le pied porte les mêmes liens sur les deux pages.
 *
 * Contre-épreuves (règle 6) : une adresse externe ou une ancre n'est jamais
 * « courante » ; `/etudes/` est la même page que `/etudes` ; les collecteurs
 * du test voient bien des entrées.
 *
 * Rejoué le 19/11/2026 contre le code d'avant (ancienne `NosEtudes.tsx`, qui
 * monte `MenuSite`) : rouge, 6 tests sur 9 — ni barre « Principale », ni
 * mêmes entrées, ni pied. Puis par mutation du socle : `aria-current` jamais
 * posé, rouge ; `adresseDe` qui rend toujours l'ancre nue, rouge (lien mort
 * `#contact` sur `/etudes`).
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { Accueil } from "../public/Accueil";
import { APPEL_DE_LA_BARRE, NAVIGATION, PIED, type EntreeDeNavigation } from "../public/contenuSite";
import { NosEtudes } from "../public/NosEtudes";
import { adresseDe, estCourante } from "../public/site";
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

/** Rend une page À SON ADRESSE : l'en-tête déduit tout du chemin. */
function rendre(nom: keyof typeof PAGES, chemin = PAGES[nom].chemin) {
  catalogueMuet();
  window.history.pushState({}, "", chemin);
  return render(PAGES[nom].page);
}

type Lien = { libelle: string; href: string | null; courant: string | null };

function liens(conteneur: HTMLElement): Lien[] {
  return within(conteneur)
    .getAllByRole("link", { hidden: true })
    .map((a) => ({
      libelle: a.textContent ?? "",
      href: a.getAttribute("href"),
      courant: a.getAttribute("aria-current"),
    }));
}

/** La barre : la navigation « Principale ». */
function barre(): Lien[] {
  return liens(screen.getByRole("navigation", { name: "Principale" }));
}

/** Le menu plein écran. Fermé, il est masqué par la feuille (que jsdom ne
 *  charge pas) : on le lit par son identifiant. */
function menu(): Lien[] {
  const nav = document.getElementById("acc-menu");
  if (!nav) throw new Error("menu plein écran introuvable");
  return liens(nav);
}

function pied(): Lien[] {
  return liens(screen.getByRole("contentinfo"));
}

const libelles = (entrees: Lien[]) => entrees.map((e) => e.libelle);

describe("l'en-tête est le même sur toutes les pages refondues", () => {
  afterEach(() => {
    cleanup();
    window.history.pushState({}, "", "/");
  });

  it("mêmes entrées, même ordre, dans la barre et dans le menu, sur l'accueil et sur les études", () => {
    const attendues = NAVIGATION.map((e) => e.libelle);
    // Règle 1 : une constante vide ferait passer toutes les égalités.
    expect(attendues.length).toBeGreaterThanOrEqual(4);

    rendre("accueil");
    const surAccueil = { barre: libelles(barre()), menu: libelles(menu()) };
    cleanup();
    rendre("etudes");
    const surEtudes = { barre: libelles(barre()), menu: libelles(menu()) };

    expect(surAccueil.barre).toEqual(attendues);
    expect(surAccueil.menu).toEqual(attendues);
    expect(surEtudes).toEqual(surAccueil);
  });

  it("sur /etudes, « Les études » est la page courante — dans la barre et dans le menu, et elle seule", () => {
    rendre("etudes");
    for (const entrees of [barre(), menu()]) {
      expect(entrees.filter((e) => e.courant !== null)).toEqual([
        { libelle: "Les études", href: "/etudes", courant: "page" },
      ]);
    }
  });

  it("une barre oblique finale ne change pas la page courante", () => {
    rendre("etudes", "/etudes/");
    expect(barre().filter((e) => e.courant === "page").map((e) => e.libelle)).toEqual(["Les études"]);
  });

  it("sur l'accueil, aucune entrée n'est courante : aucune ne mène à l'accueil", () => {
    rendre("accueil");
    expect(barre().filter((e) => e.courant !== null)).toEqual([]);
    expect(menu().filter((e) => e.courant !== null)).toEqual([]);
  });

  it("« La méthode » et « Me contacter » : des ancres sur l'accueil, des liens vers l'accueil ailleurs", () => {
    rendre("accueil");
    expect(screen.getByRole("navigation", { name: "Principale" })).toContainElement(
      screen.getAllByRole("link", { name: "La méthode" })[0],
    );
    expect(barre().find((e) => e.libelle === "La méthode")?.href).toBe("#methode");
    expect(menu().find((e) => e.libelle === "La méthode")?.href).toBe("#methode");
    expect(screen.getByRole("link", { name: /Me contacter/ })).toHaveAttribute("href", "#contact");
    // Ces sections EXISTENT sur l'accueil : c'est ce qui rend juste le lien
    // `/#methode` posé sur les autres pages.
    expect(document.getElementById("methode")).not.toBeNull();
    expect(document.getElementById("contact")).not.toBeNull();
    cleanup();

    rendre("etudes");
    expect(barre().find((e) => e.libelle === "La méthode")?.href).toBe("/#methode");
    expect(menu().find((e) => e.libelle === "La méthode")?.href).toBe("/#methode");
    expect(screen.getByRole("link", { name: /Me contacter/ })).toHaveAttribute("href", "/#contact");
    // Sur la page des études, aucun lien de l'en-tête ne vise une ancre
    // locale qui n'existe pas.
    for (const entree of [...barre(), ...menu()]) {
      if (entree.href?.startsWith("#")) {
        expect(document.querySelector(entree.href), entree.libelle).not.toBeNull();
      }
    }
    // Les autres entrées mènent au même endroit sur les deux pages.
    expect(barre().find((e) => e.libelle === "Boutique")?.href).toBe("/boutique");
    expect(barre().find((e) => e.libelle === "Espace client")?.href).toBe("/espace/connexion");
  });

  for (const nom of ["accueil", "etudes"] as const) {
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
      // Un lien du menu le referme aussi. Le clic est retenu sur le lien
      // lui-même : jsdom ne sait pas changer de page, et ce n'est pas la
      // navigation qu'on éprouve ici, c'est la fermeture.
      fireEvent.click(ouvrir);
      expect(ouvrir).toHaveAttribute("aria-expanded", "true");
      const premier = within(document.getElementById("acc-menu") as HTMLElement).getAllByRole("link", { hidden: true })[0];
      premier.addEventListener("click", (evenement) => evenement.preventDefault());
      fireEvent.click(premier);
      expect(ouvrir).toHaveAttribute("aria-expanded", "false");
      expect(principal).not.toHaveAttribute("inert");
    });
  }

  it("le pied porte les mêmes liens sur les deux pages : ceux de contenuSite.PIED", () => {
    const attendus = [...PIED.reseaux, ...PIED.liens].map((l) => ({ libelle: l.libelle, href: l.lien, courant: null }));
    expect(attendus.length).toBeGreaterThanOrEqual(6);

    rendre("accueil");
    const surAccueil = pied();
    const signature = screen.getByRole("contentinfo").textContent;
    cleanup();
    rendre("etudes");

    expect(surAccueil).toEqual(attendus);
    expect(pied()).toEqual(attendus);
    expect(screen.getByRole("contentinfo").textContent).toBe(signature);
    expect(signature).toContain(PIED.signature);
  });

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
    expect(adresseDe(APPEL_DE_LA_BARRE, "/etudes")).toBe("/#contact");
  });
});

/** La révélation au défilement n'oublie aucun bloc.
 *
 * `useReveler` décide SEUL si le contenu de vente est visible : un bloc
 * `data-reveal` naît à `opacity: 0` et ne s'allume que si un
 * IntersectionObserver le voit entrer. Le jour où un bloc est monté sans être
 * observé — une liste chargée après coup dont le changement n'est pas dans la
 * `cle`, par exemple —, il reste invisible en production, et aucun test ne le
 * voyait : jsdom n'a pas d'IntersectionObserver, le crochet y prend la branche
 * « tout visible » et 74 tests restaient verts (revue du 26/09/2026).
 *
 * D'où un faux observateur qui enregistre ses cibles SANS jamais rappeler, et
 * un invariant : chaque `[data-reveal]` du DOM est soit déjà révélé, soit
 * observé par un observateur encore branché. La contre-épreuve (règle 6) est
 * dans le fichier : sans clé, le bloc monté après coup n'est observé par
 * personne, et l'invariant le voit.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX
 * y est compilé en `React.createElement` classique, et sans l'import le
 * rendu échoue sur « React is not defined ».
 */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { act, render } from "@testing-library/react";
import React, { useRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useReveler } from "../public/reveler";

class FauxObservateur {
  static tous: FauxObservateur[] = [];
  readonly cibles = new Set<Element>();
  deconnecte = false;
  private readonly rappel: IntersectionObserverCallback;

  constructor(rappel: IntersectionObserverCallback) {
    this.rappel = rappel;
    FauxObservateur.tous.push(this);
  }

  observe(cible: Element): void {
    this.cibles.add(cible);
  }

  unobserve(cible: Element): void {
    this.cibles.delete(cible);
  }

  disconnect(): void {
    this.deconnecte = true;
    this.cibles.clear();
  }

  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }

  /** Simule l'entrée d'un bloc dans la fenêtre. */
  croise(cible: Element): void {
    this.rappel(
      [{ isIntersecting: true, target: cible } as IntersectionObserverEntry],
      this as unknown as IntersectionObserver,
    );
  }
}

function mediaQuery(reduit: boolean) {
  return (requete: string) => ({
    matches: reduit && requete.includes("reduce"),
    media: requete,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  });
}

/** Une page qui monte `n` blocs ; `avecCle` dit si leur nombre est la clé. */
function Page({ n, avecCle }: { n: number; avecCle: boolean }) {
  const racine = useRef<HTMLDivElement>(null);
  useReveler(racine, avecCle ? n : undefined);
  return (
    <div ref={racine}>
      {Array.from({ length: n }, (_, i) => (
        <p key={i} data-reveal="">
          bloc {i}
        </p>
      ))}
    </div>
  );
}

const page = (n: number, avecCle: boolean) => <Page n={n} avecCle={avecCle} />;

/** Les blocs qui resteraient effacés pour toujours. */
function oublies(conteneur: HTMLElement): Element[] {
  const observes = new Set<Element>();
  for (const o of FauxObservateur.tous) {
    if (!o.deconnecte) for (const c of o.cibles) observes.add(c);
  }
  return Array.from(conteneur.querySelectorAll("[data-reveal]")).filter(
    (bloc) => !bloc.classList.contains("est-revele") && !observes.has(bloc),
  );
}

describe("la révélation n'oublie aucun bloc", () => {
  beforeEach(() => {
    FauxObservateur.tous = [];
    vi.stubGlobal("IntersectionObserver", FauxObservateur);
    vi.stubGlobal("matchMedia", mediaQuery(false));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("observe les blocs présents au montage", () => {
    const { container } = render(page(2, true));
    expect(container.querySelectorAll("[data-reveal]")).toHaveLength(2);
    expect(oublies(container)).toHaveLength(0);
  });

  it("observe un bloc monté APRÈS coup quand la clé change", () => {
    const { container, rerender } = render(page(1, true));
    rerender(page(3, true));
    expect(container.querySelectorAll("[data-reveal]")).toHaveLength(3);
    expect(oublies(container)).toHaveLength(0);
  });

  it("contre-épreuve : sans clé, le bloc monté après coup est oublié — et l'invariant le voit", () => {
    const { container, rerender } = render(page(1, false));
    rerender(page(3, false));
    expect(oublies(container).length).toBeGreaterThan(0);
  });

  it("révèle un bloc qui entre dans la fenêtre, puis cesse de l'observer", () => {
    const { container } = render(page(1, true));
    const bloc = container.querySelector("[data-reveal]") as Element;
    const observateur = FauxObservateur.tous.find((o) => o.cibles.has(bloc));
    expect(observateur).toBeDefined();
    act(() => observateur?.croise(bloc));
    expect(bloc.classList.contains("est-revele")).toBe(true);
    expect(observateur?.cibles.has(bloc)).toBe(false);
  });

  it("débranche l'observateur au démontage", () => {
    const { unmount } = render(page(2, true));
    unmount();
    expect(FauxObservateur.tous.every((o) => o.deconnecte)).toBe(true);
  });

  it("sans IntersectionObserver, tout est visible d'emblée", () => {
    vi.stubGlobal("IntersectionObserver", undefined);
    const { container } = render(page(3, true));
    const blocs = Array.from(container.querySelectorAll("[data-reveal]"));
    expect(blocs.every((b) => b.classList.contains("est-revele"))).toBe(true);
  });

  it("sous prefers-reduced-motion, tout est visible d'emblée", () => {
    vi.stubGlobal("matchMedia", mediaQuery(true));
    const { container } = render(page(3, true));
    const blocs = Array.from(container.querySelectorAll("[data-reveal]"));
    expect(blocs.every((b) => b.classList.contains("est-revele"))).toBe(true);
    expect(FauxObservateur.tous).toHaveLength(0);
  });

  // Un fichier qui pose `data-reveal` sans appeler le crochet laisserait tous
  // ses blocs effacés : rien ne leur poserait jamais `est-revele`.
  it("chaque page publique qui pose data-reveal appelle useReveler", () => {
    const dossier = join(process.cwd(), "src", "public");
    const pages = readdirSync(dossier).filter((f) => f.endsWith(".tsx"));
    const avecBlocs = pages.filter((f) =>
      readFileSync(join(dossier, f), "utf-8").includes("data-reveal"),
    );
    expect(avecBlocs.length).toBeGreaterThan(0);
    for (const page of avecBlocs) {
      expect(readFileSync(join(dossier, page), "utf-8"), page).toMatch(
        /useReveler\(/,
      );
    }
  });
});

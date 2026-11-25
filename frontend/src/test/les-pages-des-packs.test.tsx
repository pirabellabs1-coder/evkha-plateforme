/** Les trois pages des packs d'accompagnement : `/packs`, `/packs/essentiel`,
 * `/packs/premium` (`public/Packs.tsx`).
 *
 * Elles reprennent trois pages du site de la cliente. Ce que ce test
 * verrouille :
 *
 * 1. chaque page se rend, a UN h1, des titres sans saut, un lien d'évitement,
 *    rien de focalisable sous `aria-hidden`, un titre d'onglet à elle ;
 * 2. les prix affichés sont ceux de `contenuPacks.TARIFS_PACKS`, et aucun
 *    montant n'est écrit dans `Packs.tsx` — ni sous la forme « 495 € », ni
 *    par ses seuls chiffres (la classe du défaut, règle 4) ;
 * 3. chaque bouton d'achat mène à la page de paiement de SON pack
 *    (`LIENS_PACKS`), « Voir le détail » à la page du pack ;
 * 4. aucun `<form>`, aucun champ : le formulaire de commande de Systeme.io
 *    (`formulaireDeCommande`) n'est pas rendu ;
 * 5. RIEN de ce que les pages d'origine disaient n'a disparu : chaque phrase
 *    du contenu est dans le DOM — sauf celles qu'un ACCORD a retouchées, dont
 *    le nombre est exact et la forme attendue écrite ici en toutes lettres ;
 * 6. les accords : jamais « 15 ans » ni « 16 ans » sans « plus de », le
 *    nombre d'étapes annoncé est celui des étapes affichées, le Premium
 *    n'annonce aucun nombre de livrables ;
 * 7. le comparatif est un vrai tableau : légende, en-têtes de colonne et de
 *    ligne, boîte nommée et focalisable ;
 * 8. les cartes du Premium sans chiffre s'affichent sans chiffre ;
 * 9. la stratégie : « réalisé par Evangeline » dès l'ouverture, une passerelle
 *    vers `/etudes` sans un prix ;
 * 10. aucune adresse du CDN de l'ancien site dans `Packs.tsx` ni `Packs.css`,
 *     ni dans le DOM ;
 * 11. la formation P.O.P IA offerte avec le Premium : sa « valeur » et sa durée
 *     sont celles que le SERVEUR rend pour `methode-pop`
 *     (`GET /api/public/formations/`), servies ici à des valeurs inhabituelles
 *     (913 €, 11 h). Tant que la réponse n'est pas arrivée, si l'appel échoue,
 *     si la réponse est mal formée ou si la formation n'est pas en ligne, les
 *     trois pages restent ENTIÈRES et la mention disparaît proprement de
 *     chaque phrase — ni « valeur  € », ni parenthèse vide ; ni le prix ni la
 *     durée de la formation ne sont écrits dans les sources.
 *
 * Contre-épreuves (règle 6) : les détecteurs voient bien un montant, une
 * ancienneté nue, une adresse du CDN, une durée écrite en dur, une phrase
 * amputée — et laissent passer ce qui est juste.
 *
 * PAS ENCORE JOUÉ au moment de son écriture ni de sa mise à jour du
 * 19/11/2026 (consigne du lot : ni `vitest` ni `tsc`) : ni contre la page, ni
 * par mutation. À rejouer, puis à éprouver par mutations — un montant en dur
 * dans une carte, un bouton d'achat croisé, le formulaire rendu, un `dire`
 * retiré de l'experte, la valeur de la P.O.P écrite en dur, un passage
 * facultatif dont on retire les crochets.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { composerTout, type Chiffres } from "../public/chiffres";
import {
  ARTICULATION_PACK_ESSENTIEL,
  ARTICULATION_PACK_PREMIUM,
  COMMUN_PACKS,
  COMPARATIF_PACKS,
  LIENS_PACKS,
  PAGE_PACKS,
  PAGE_PACK_ESSENTIEL,
  PAGE_PACK_PREMIUM,
  TARIFS_PACKS,
  chiffresDesPacks,
  compteRendu,
  pointDeListe,
  sansCompte,
  sansFleche,
} from "../public/contenuPacks";
import { LIENS } from "../public/contenuSite";
import type { FormationPublique } from "../public/donnees";
import { PackEssentiel, PackPremium, Packs } from "../public/Packs";
// L'ancienneté n'est plus une fonction des packs : packs et formations
// partagent celle du socle.
import { ancienneteSure, titreDOnglet } from "../public/site";
import { server } from "./server";

// ── L'API des formations, telle que le test la sert ─────────────────────────

// L'adresse que `donnees.ts` construit réellement : l'origine de jsdom.
const FORMATIONS_API = `${window.location.origin}/api/public/formations/`;

/** Une formation telle que le serveur la rend. Par défaut : la Méthode P.O.P IA,
 *  à un prix et une durée que personne n'écrirait de mémoire. */
function formation(surcharges: Partial<FormationPublique> = {}): FormationPublique {
  return {
    slug: "methode-pop",
    titre: "TITRE-DU-SERVEUR",
    sous_titre: "",
    accroche: "",
    prix_cents: 91300,
    devise: "EUR",
    duree_heures: 11,
    heures_de_coaching: 0,
    lien_d_achat: "",
    image: "",
    nombre_de_modules: 0,
    modules: [],
    ...surcharges,
  };
}

const POP_EN_LIGNE = formation();
/** Une AUTRE formation en ligne : la réponse n'est pas vide, mais la P.O.P
 *  n'y est pas. Son prix ne doit jamais passer pour la valeur de la P.O.P. */
const UNE_AUTRE = formation({ slug: "creer-son-entreprise", prix_cents: 123700, duree_heures: 23 });

/** Les chiffres que les phrases doivent citer, écrits à la main. */
const EN_LIGNE: Chiffres = { valeurPop: "913 €", valeurPopEntiere: 913, heuresPop: 11 };
const SANS: Chiffres = { valeurPop: null, valeurPopEntiere: null, heuresPop: null };

type Reponse = () => Response | Promise<Response>;

function servir(reponse: Reponse) {
  server.use(http.get(FORMATIONS_API, reponse));
}

const lesFormations = (liste: object[]): Reponse => () => HttpResponse.json({ formations: liste });
const panne: Reponse = () => new HttpResponse("panne", { status: 500 });
const malFormee: Reponse = () => HttpResponse.json({ formation: [] });
const muet: Reponse = async () => {
  await delay("infinite");
  return new HttpResponse(null);
};

// ── Outils ──────────────────────────────────────────────────────────────────

/** Les deux espaces insécables. Construites par leur code, jamais tapées :
 *  écrites en clair, elles sont invisibles à la relecture. */
const INSECABLE = String.fromCharCode(0xa0);
const FINE_INSECABLE = String.fromCharCode(0x202f);
const INSECABLES = new RegExp(`[${INSECABLE}${FINE_INSECABLE}]`, "g");

function espaces(brut: string): string {
  return brut.replace(INSECABLES, " ");
}

function brut(): string {
  return document.body.textContent ?? "";
}

function texte(): string {
  return espaces(brut());
}

function texteDe(element: Element | null): string {
  return espaces(element?.textContent ?? "");
}

/** Le prix tel qu'il doit s'afficher, calculé ICI sur la constante de tarifs —
 *  et non lu dans une chaîne déjà formée par le fichier de contenu. */
function prix(tarif: { centimes: number }): string {
  return `${tarif.centimes / 100} €`;
}

const PRIX_ESSENTIEL = prix(TARIFS_PACKS.essentiel);
const PRIX_PREMIUM = prix(TARIFS_PACKS.premium);

/** Un montant en euros, où qu'il soit. */
const MONTANT_ECRIT = /\d[\d\s.,]*(?:€|euros?\b)/i;

/** Les chiffres d'un tarif, seuls : « 495 » sans son symbole. Un prix recopié
 *  dans un nom de variable ou une chaîne sans « € » serait encore un prix. */
function chiffresDesTarifs(): RegExp {
  const montants = Object.values(TARIFS_PACKS).map((t) => String(t.centimes / 100));
  return new RegExp(`(?<!\\d)(?:${montants.join("|")})(?!\\d)`, "g");
}

/** Une ancienneté écrite sans « plus de ». */
const ANCIENNETE_NUE = /(?<!plus de )\b1[56] ans\b/;

/** Une adresse du CDN qui sert les images de l'ancien site. */
const ANCIEN_CDN = /cloudfront\.net|d1yei2z3i6k35z/i;

function sansCommentaires(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

function source(fichier: string): string {
  return readFileSync(join(process.cwd(), "src", "public", fichier), "utf-8");
}

/** Toutes les phrases d'un objet de contenu, à plat, sauf sous les clés
 *  `exclues`. */
function phrases(valeur: unknown, exclues: string[] = []): string[] {
  if (typeof valeur === "string") return [valeur];
  if (Array.isArray(valeur)) return valeur.flatMap((v) => phrases(v, exclues));
  if (valeur && typeof valeur === "object") {
    return Object.entries(valeur)
      .filter(([cle]) => !exclues.includes(cle))
      .flatMap(([, v]) => phrases(v, exclues));
  }
  return [];
}

/** Ce qui n'est pas une phrase à retrouver : le titre d'onglet et la
 *  description (vérifiés à part), les adresses, le formulaire non rendu. */
const HORS_PHRASES = ["titreDeLOnglet", "metaDescription", "lien", "formulaireDeCommande"];

/** Une phrase telle que la page l'affiche, HORS accords : l'étoile de tête
 *  devient la puce de la ligne, la flèche finale celle du bouton. */
function affichee(phrase: string): string {
  return espaces(sansFleche(pointDeListe(phrase).texte));
}

/** Une case du comparatif qui commence par un signe (« ✓ Standard », « — ») :
 *  rendue en deux morceaux, vérifiée dans le tableau. */
function estUnSigne(phrase: string): boolean {
  return COMPARATIF_PACKS.signes.some(
    (s) => phrase.startsWith(s.signe) && !pointDeListe(phrase).vedette,
  );
}

/** Les phrases du contenu que la page n'affiche pas mot pour mot — une fois
 *  les chiffres de la formation P.O.P IA posés (ou retirés) dans celles qui en
 *  citent. Une phrase que son chiffre manquant a vidée n'est pas attendue. */
function absentes(contenu: unknown, chiffres: Chiffres = EN_LIGNE): string[] {
  const page = texte();
  return phrases(composerTout(contenu, chiffres), HORS_PHRASES)
    .filter((phrase) => phrase !== "")
    .filter((phrase) => !estUnSigne(phrase))
    .filter((phrase) => !page.includes(affichee(phrase)));
}

/** Une durée de formation écrite en dur. */
const DUREE_EN_DUR = /\b\d+\s?h de formation/g;

/** Ce qu'une phrase amputée de son chiffre laisserait derrière elle. */
const PHRASE_AMPUTEE =
  /\(\s*\)|\(\s*valeur\s*\)|valeur\s+€|valeur de\s*,|VALEUR\s+EUROS|:\s+pour structurer|[{}]|\[\[|\]\]/i;

const PAGES = {
  ensemble: { chemin: "/packs", page: <Packs /> },
  essentiel: { chemin: "/packs/essentiel", page: <PackEssentiel /> },
  premium: { chemin: "/packs/premium", page: <PackPremium /> },
};

type NomDePage = keyof typeof PAGES;
const NOMS = Object.keys(PAGES) as NomDePage[];

function rendre(nom: NomDePage) {
  window.history.pushState({}, "", PAGES[nom].chemin);
  return render(PAGES[nom].page);
}

/** Rend la page et attend qu'elle ait LU la réponse du serveur. Sur ces pages,
 *  une formation hors ligne ou une panne ne change rien de visible : l'état de
 *  l'appel se lit sur la racine (`data-formations`). */
async function rendreLue(nom: NomDePage, etat: "recu" | "panne" = "recu") {
  const rendu = rendre(nom);
  await waitFor(() => expect(document.querySelector(".acc.pak")).toHaveAttribute("data-formations", etat));
  return rendu;
}

function liens(conteneur: ParentNode = document): HTMLAnchorElement[] {
  return Array.from(conteneur.querySelectorAll<HTMLAnchorElement>("a[href]"));
}

/** Les liens par lesquels on commande un pack.
 *
 *  Repérés par leur DESTINATION, lue dans `LIENS_PACKS`, et non par la forme
 *  de l'adresse : depuis la bascule du domaine (19/11/2026) la commande part
 *  par courriel, et le motif `/paiement-` ne voyait plus aucun bouton — le
 *  test comptait zéro lien là où la page en porte quatre. */
function liensDePaiement(): HTMLAnchorElement[] {
  const commandes: string[] = [LIENS_PACKS.commandeEssentiel, LIENS_PACKS.commandePremium];
  return liens().filter((a) => commandes.includes(a.getAttribute("href") ?? ""));
}

describe("les pages des packs", () => {
  // Par défaut, la Méthode P.O.P IA est en ligne ; un test qui veut un autre
  // état le sert lui-même.
  beforeEach(() => servir(lesFormations([UNE_AUTRE, POP_EN_LIGNE])));
  afterEach(() => {
    cleanup();
    window.history.pushState({}, "", "/");
  });

  // ── Chaque page se rend et se laisse conduire ─────────────────────────────

  for (const nom of NOMS) {
    it(`${nom} : un seul h1, des titres sans saut, un lien d'évitement, rien de focalisable sous aria-hidden`, () => {
      rendre(nom);

      expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
      const niveaux = Array.from(document.querySelectorAll("h1, h2, h3, h4, h5, h6")).map((t) => Number(t.tagName[1]));
      expect(niveaux[0]).toBe(1);
      expect(niveaux.length).toBeGreaterThan(8);
      niveaux.forEach((niveau, k) => {
        if (k > 0) expect(niveau - niveaux[k - 1], `saut de titre au rang ${k}`).toBeLessThanOrEqual(1);
      });

      const principal = screen.getByRole("main");
      expect(principal.id).not.toBe("");
      expect(screen.getByRole("link", { name: "Aller au contenu" })).toHaveAttribute("href", `#${principal.id}`);
      // Un seul pied de page, une barre : les cartes n'en fabriquent pas d'autres.
      expect(screen.getAllByRole("contentinfo")).toHaveLength(1);
      expect(screen.getByRole("navigation", { name: "Principale" })).toBeInTheDocument();

      const caches = Array.from(document.querySelectorAll("[aria-hidden='true']"));
      expect(caches.length).toBeGreaterThan(10);
      for (const cache of caches) {
        expect(cache.querySelector("a, button, input, select, textarea, summary, [tabindex]"), cache.className).toBeNull();
      }

      // Les images : un texte, des dimensions réservées, et le chargement
      // différé — aucune n'est en haut de page.
      const images = Array.from(document.querySelectorAll("img"));
      expect(images.length).toBeGreaterThan(0);
      for (const image of images) {
        expect(image.getAttribute("alt") ?? "", image.src).not.toBe("");
        expect(Number(image.getAttribute("width"))).toBeGreaterThan(0);
        expect(Number(image.getAttribute("height"))).toBeGreaterThan(0);
        expect(image).toHaveAttribute("loading", "lazy");
        expect(image.getAttribute("src")).toMatch(/^\/(accueil|partenaires)\//);
      }
    });

    it(`${nom} : aucun formulaire, aucun champ, aucune adresse de l'ancien CDN dans le DOM`, () => {
      rendre(nom);

      expect(document.querySelector("form")).toBeNull();
      expect(document.querySelector("input, select, textarea")).toBeNull();
      // Le formulaire de commande de Systeme.io n'est pas rendu.
      for (const page of [PAGE_PACK_ESSENTIEL, PAGE_PACK_PREMIUM]) {
        const formulaire = phrases(page.formulaireDeCommande);
        expect(formulaire.length).toBeGreaterThanOrEqual(6);
        for (const phrase of formulaire) {
          expect(texte(), `le formulaire est rendu : « ${phrase} »`).not.toContain(phrase);
        }
      }
      for (const element of Array.from(document.querySelectorAll("[src], [href]"))) {
        const adresse = element.getAttribute("src") ?? element.getAttribute("href") ?? "";
        expect(adresse, adresse).not.toMatch(ANCIEN_CDN);
      }
    });

    it(`${nom} : la typographie française tient dans le texte affiché`, () => {
      rendre(nom);

      // Texte BRUT : c'est l'espace ordinaire qu'on cherche.
      expect(brut()).toMatch(/€/);
      expect(brut()).not.toMatch(/ €/);
      expect(brut()).not.toMatch(/ [→←↗↓]|[→←↗↓] /);
      expect(texte()).not.toMatch(/\b(?:null|undefined|NaN)\b/);
    });

    it(`${nom} : plus de « réalisé par Evangeline » (cliente, 24/11/2026), et une passerelle vers les études sans un prix`, () => {
      rendre(nom);

      expect(texte()).not.toContain("Réalisé par Evangeline Khaili elle-même");
      expect(texte()).not.toContain("Un pack n'est pas produit par la plateforme");

      const passerelle = document.getElementById("autrement") as HTMLElement;
      expect(passerelle).not.toBeNull();
      expect(within(passerelle).getByRole("link", { name: /Voir les études/ })).toHaveAttribute("href", "/etudes");
      const porte = within(passerelle).getByRole("link", { name: /Voir les études/ }).closest("article");
      expect(texteDe(porte)).toContain("seul document ?");
      expect(texteDe(porte)).not.toMatch(MONTANT_ECRIT);
      // Elle précède l'appel final.
      const fin = document.getElementById("commander") as HTMLElement;
      expect(passerelle.compareDocumentPosition(fin) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      // L'appel gratuit est proposé sur chaque page.
      const appels = screen.getAllByRole("link", { name: new RegExp(COMMUN_PACKS.appelGratuit) });
      expect(appels.length).toBeGreaterThanOrEqual(1);
      for (const appel of appels) expect(appel).toHaveAttribute("href", LIENS.appel);
      expect(within(fin).getByRole("link", { name: new RegExp(COMMUN_PACKS.appelGratuit) })).toBeInTheDocument();
    });

    it(`${nom} : l'ancienneté ne s'écrit jamais sans « plus de »`, () => {
      rendre(nom);
      expect(texte()).toContain("plus de 16 ans");
      expect(texte()).not.toMatch(ANCIENNETE_NUE);
    });

    it(`${nom} : deux boutons de pause, un seul état, et un ruban décoratif`, () => {
      const { container } = rendre(nom);

      const boutons = screen.getAllByRole("button", { name: "Mettre les animations en pause" });
      expect(boutons).toHaveLength(2);
      fireEvent.click(boutons[1]);
      expect(container.querySelector(".acc")).toHaveClass("acc-fige");
      expect(container.querySelector(".acc")).toHaveClass("pak");
      for (const bouton of screen.getAllByRole("button", { name: "Relancer les animations" })) {
        expect(bouton).toHaveAttribute("aria-pressed", "true");
      }
      expect(document.querySelector(".acc-ruban")).toHaveAttribute("aria-hidden", "true");
    });
  }

  it("chaque page a son titre d'onglet et sa description, et aucun n'est le nom de travail du site", () => {
    const titres: string[] = [];
    for (const nom of NOMS) {
      rendre(nom);
      titres.push(document.title);
      expect(document.title, nom).not.toMatch(/PAGE DE PAIEMENT/i);
      // UN format sur tout le site : « Titre de la page — EVKHA ».
      expect(document.title, nom).toMatch(/\S — EVKHA$/);
      expect(document.title, nom).not.toMatch(/[–|]\s*EVKHA/);
      cleanup();
    }
    expect(new Set(titres).size).toBe(NOMS.length);
    // Le titre est celui du contenu, mis au format du site par `titreDOnglet`.
    expect(titres[0]).toBe(titreDOnglet(PAGE_PACKS.titreDeLOnglet));
    expect(titres[1]).toBe(titreDOnglet(ARTICULATION_PACK_ESSENTIEL.titreDeLOnglet));
    expect(titres[2]).toBe(titreDOnglet(ARTICULATION_PACK_PREMIUM.titreDeLOnglet));
    // Écrit à la main, pour ne pas juger la fonction avec elle-même.
    expect(titres[1]).toBe("Pack Création Essentiel : étude de marché, prévisionnel et business plan — EVKHA");
  });

  // ── Les prix ──────────────────────────────────────────────────────────────

  it("/packs affiche les deux prix de la constante de tarifs, chacun dans SA carte", async () => {
    await rendreLue("ensemble");

    const cartes = Array.from(document.querySelectorAll<HTMLElement>("article.pak-carte"));
    expect(cartes).toHaveLength(2);
    expect(within(cartes[0]).getByRole("heading", { level: 2 })).toHaveTextContent(PAGE_PACKS.packEssentiel.nom);
    expect(within(cartes[1]).getByRole("heading", { level: 2 })).toHaveTextContent(PAGE_PACKS.packPremium.nom);
    expect(texteDe(cartes[0].querySelector(".pak-prix"))).toBe(`Tarif : ${PRIX_ESSENTIEL}`);
    expect(texteDe(cartes[1].querySelector(".pak-prix"))).toBe(`Tarif : ${PRIX_PREMIUM}`);
    expect(texteDe(cartes[0].querySelector(".pak-prix"))).not.toContain(PRIX_PREMIUM);
    // Nom, prix, accroche, contenu, « sert à », durée : tout est dans la carte.
    for (const [carte, contenu] of [
      [cartes[0], PAGE_PACKS.packEssentiel],
      [cartes[1], PAGE_PACKS.packPremium],
    ] as const) {
      const attendues = phrases(composerTout(contenu, EN_LIGNE), HORS_PHRASES);
      expect(attendues.length).toBeGreaterThan(12);
      for (const phrase of attendues) {
        expect(texteDe(carte), `la carte ne dit plus : « ${phrase} »`).toContain(affichee(phrase));
      }
    }
  });

  for (const [nom, attendu, autre] of [
    ["essentiel", PRIX_ESSENTIEL, PRIX_PREMIUM],
    ["premium", PRIX_PREMIUM, PRIX_ESSENTIEL],
  ] as [NomDePage, string, string][]) {
    it(`${nom} : l'ouverture porte le prix de SON pack, lu dans la constante, et son délai`, () => {
      rendre(nom);

      const encart = document.querySelector(".pak-encart");
      expect(texteDe(encart?.querySelector(".pak-prix") ?? null)).toContain(attendu);
      expect(texteDe(encart)).not.toContain(autre);
      const duree = nom === "essentiel" ? PAGE_PACKS.packEssentiel.duree : PAGE_PACKS.packPremium.duree;
      expect(texteDe(encart)).toContain(duree);
    });
  }

  for (const fichier of ["Packs.tsx"]) {
    it(`${fichier} n'écrit aucun montant, ni les chiffres d'un tarif`, () => {
      const code = sansCommentaires(source(fichier));
      // Règle 1 : un fichier vide ou introuvable ne « passe » pas.
      expect(code.length).toBeGreaterThan(5000);
      expect(code.match(new RegExp(MONTANT_ECRIT.source, "gi")) ?? []).toEqual([]);
      expect(code.match(chiffresDesTarifs()) ?? []).toEqual([]);
    });
  }

  it("contenuPacks.ts n'écrit les chiffres d'un tarif qu'UNE fois : dans TARIFS_PACKS", () => {
    const code = sansCommentaires(source("contenuPacks.ts"));
    expect(code.length).toBeGreaterThan(5000);
    // « 49500 » n'est pas « 495 » : les montants en centimes de la constante
    // ne sont pas vus, et c'est voulu — c'est LA source.
    expect(code.match(chiffresDesTarifs()) ?? []).toEqual([]);
    // Les deux prix de vente des packs : écrits ICI, une fois.
    for (const tarif of [TARIFS_PACKS.essentiel, TARIFS_PACKS.premium]) {
      expect(code.split(String(tarif.centimes)).length - 1, String(tarif.centimes)).toBe(1);
    }
    // Et ce sont les SEULS tarifs de la constante : la valeur de la formation
    // P.O.P n'y est plus, elle vient du serveur.
    expect(Object.keys(TARIFS_PACKS)).toEqual(["essentiel", "premium"]);
  });

  // ── La formation P.O.P IA offerte : sa valeur et sa durée viennent du serveur ─

  for (const fichier of ["contenuPacks.ts", "Packs.tsx"]) {
    it(`${fichier} n'écrit ni le prix ni la durée de la formation P.O.P IA`, () => {
      const code = sansCommentaires(source(fichier));
      expect(code.length, fichier).toBeGreaterThan(5000);
      // Ni par ses chiffres — en euros comme en centimes —, ni par une durée,
      // ni par les constantes d'avant, qui n'existent plus.
      expect(code.match(/(?<!\d)(?:85000|850)(?!\d)/g) ?? [], fichier).toEqual([]);
      expect(code.match(DUREE_EN_DUR) ?? [], fichier).toEqual([]);
      for (const supprimee of ["TARIFS_FORMATIONS", "DUREES_POP", "HEURES_POP", "VALEUR_POP", "formationPop"]) {
        expect(code, supprimee).not.toContain(supprimee);
      }
    });
  }

  it("la valeur et la durée de la P.O.P se lisent dans la réponse du serveur, pour SA formation seulement", () => {
    const lus = chiffresDesPacks([UNE_AUTRE, POP_EN_LIGNE]);
    expect({ ...lus, valeurPop: espaces(String(lus.valeurPop)) }).toEqual(EN_LIGNE);
    // L'insécable devant « € » y est : c'est la fonction commune du site.
    expect(String(lus.valeurPop)).not.toMatch(/ €/);
    // Pas de réponse (attente, panne), pas de P.O.P dans la réponse, une
    // P.O.P sans prix lisible : aucun chiffre — jamais celui d'une autre.
    expect(chiffresDesPacks(null)).toEqual(SANS);
    expect(chiffresDesPacks([])).toEqual(SANS);
    expect(chiffresDesPacks([UNE_AUTRE])).toEqual(SANS);
    expect(chiffresDesPacks([formation({ prix_cents: 0 })])).toEqual(SANS);
    expect(chiffresDesPacks([formation({ devise: "USD" })])).toEqual(SANS);
    // Un prix qui ne tombe pas sur un euro rond : la forme « en euros
    // entiers » s'en passe, plutôt que d'arrondir.
    const nonRond = chiffresDesPacks([formation({ prix_cents: 91350 })]);
    expect(espaces(String(nonRond.valeurPop))).toBe("913,50 €");
    expect(nonRond.valeurPopEntiere).toBeNull();
    // Une durée d'une heure, ou nulle, ne s'écrit pas « 1h de formation ».
    expect(chiffresDesPacks([formation({ duree_heures: 1 })]).heuresPop).toBeNull();
    expect(chiffresDesPacks([formation({ duree_heures: 0 })]).heuresPop).toBeNull();
  });

  it("premium, P.O.P en ligne : chaque phrase cite la valeur et la durée du serveur", async () => {
    await rendreLue("premium");

    const page = texte();
    // Écrites ici à la main, telles que la page doit les dire.
    for (const phrase of [
      "Formation P.O.P IA incluse (valeur 913 €)",
      "BONUS : Formation P.O.P IA incluse (913 €)",
      "L'accès complet à la formation Méthode P.O.P IA d'EVKHA : 11h de formation pour structurer votre activité",
      "D'une valeur de 913 €, la formation P.O.P IA est habituellement vendue séparément.",
      "11h de formation digitale à votre rythme",
      "ET la formation P.O.P IA (valeur 913 €). Si vous visez un financement important",
    ]) {
      expect(page, phrase).toContain(phrase);
    }
    // La durée est annoncée trois fois : la carte du livrable (deux fois) et
    // celle de la formation offerte.
    expect(page.split("11h de formation").length - 1).toBeGreaterThanOrEqual(3);
    // La case du comparatif : l'étoile, sa lecture, puis la valeur.
    const ligne = Array.from(document.querySelectorAll("#comparatif tbody tr")).find(
      (rang) => rang.querySelector("th")?.textContent === "Formation P.O.P IA incluse",
    );
    expect(texteDe(ligne?.querySelectorAll("td")[1] ?? null)).toBe("★Bonus, Valeur 913 €");
    // Ni le prix ni la durée d'avant, ni le prix d'une AUTRE formation.
    expect(page).not.toMatch(/850|\b7\s?h\b|1 237/);
    expect(page).not.toMatch(PHRASE_AMPUTEE);
    expect(brut()).not.toMatch(/ €/);
    // Le texte du serveur ne remplace pas celui de la page.
    expect(page).not.toContain("TITRE-DU-SERVEUR");
  });

  it("ensemble et essentiel, P.O.P en ligne : la valeur du serveur, dans leurs phrases", async () => {
    await rendreLue("ensemble");
    const points = () => Array.from(document.querySelectorAll(".pak-points li > span:last-child")).map(texteDe);
    expect(points()).toContain("BONUS EXCEPTIONNEL : ACCÈS À LA FORMATION POP (VALEUR 913 EUROS)");
    expect(texte()).toContain("★Bonus, Valeur 913 €");
    expect(texte()).not.toMatch(/850|1 237/);
    cleanup();

    await rendreLue("essentiel");
    expect(texte()).toContain("ET la formation P.O.P IA incluse (valeur 913 €). Si vous visez un financement important");
    expect(texte()).toContain("et la formation P.O.P IA incluse (valeur 913 €). Pour les projets ambitieux");
    expect(texte()).not.toMatch(/850|1 237/);
  });

  it("un prix de la P.O.P qui n'est pas rond : la valeur s'affiche avec ses centimes, la phrase en euros entiers s'en passe", async () => {
    servir(lesFormations([formation({ prix_cents: 91350 })]));
    await rendreLue("ensemble");

    expect(texte()).toContain("★Bonus, Valeur 913,50 €");
    const points = Array.from(document.querySelectorAll(".pak-points li > span:last-child")).map(texteDe);
    expect(points).toContain("BONUS EXCEPTIONNEL : ACCÈS À LA FORMATION POP");
    expect(texte()).not.toMatch(/VALEUR/);
  });

  for (const [etat, reponse, lu] of [
    ["la réponse n'est pas arrivée", muet, null],
    ["l'appel échoue", panne, "panne"],
    ["la réponse est mal formée", malFormee, "panne"],
    ["la P.O.P n'est pas en ligne (réponse vide)", lesFormations([]), "recu"],
    ["la P.O.P n'est pas en ligne (une autre formation l'est)", lesFormations([UNE_AUTRE]), "recu"],
  ] as [string, Reponse, "recu" | "panne" | null][]) {
    it(`premium, quand ${etat} : la page reste entière, et la mention disparaît proprement`, async () => {
      servir(reponse);
      if (lu === null) rendre("premium");
      else await rendreLue("premium", lu);

      const page = texte();
      // Écrites ici à la main : chaque phrase, sans sa mention.
      for (const phrase of [
        "L'accès complet à la formation Méthode P.O.P IA d'EVKHA pour structurer votre activité, organiser votre temps",
        "La formation P.O.P IA est habituellement vendue séparément. Elle est intégralement offerte",
        "ET la formation P.O.P IA. Si vous visez un financement important",
        "Formation digitale à votre rythme",
      ]) {
        expect(page, phrase).toContain(phrase);
      }
      // Le titre du livrable, la ligne de l'encart, la case du comparatif :
      // exactement ce qu'il reste, pas un mot de plus.
      const livrables = Array.from(document.querySelectorAll("#contenu .pak-livrables > li > h3")).map(texteDe);
      expect(livrables[livrables.length - 1]).toBe("Formation P.O.P IA incluse");
      const encart = Array.from(document.querySelectorAll(".pak-encart-points li")).map(texteDe);
      expect(encart[encart.length - 1]).toBe("★BONUS : Formation P.O.P IA incluse");
      const ligne = Array.from(document.querySelectorAll("#comparatif tbody tr")).find(
        (rang) => rang.querySelector("th")?.textContent === "Formation P.O.P IA incluse",
      );
      expect(texteDe(ligne?.querySelectorAll("td")[1] ?? null)).toBe("★Bonus");
      expect(Array.from(document.querySelectorAll("#contenu .pak-etoiles li")).map(texteDe)).toContain("Formation digitale");

      // Ni phrase amputée, ni chiffre de la formation — d'ici ou d'ailleurs.
      expect(page).not.toMatch(PHRASE_AMPUTEE);
      expect(page.match(DUREE_EN_DUR)).toBeNull();
      expect(page).not.toMatch(/913|850|1 237|valeur de/i);
      expect(page).not.toMatch(/\b(?:null|undefined|NaN)\b/);

      // La page est entière : toutes ses sections, tout son texte, son prix de
      // pack — et aucune alerte, aucun prix de pack ne dépendant de cet appel.
      expect(Array.from(document.querySelectorAll("main section[id]")).map((s) => s.id)).toEqual([
        "pour-qui", "en-plus", "contenu", "formation-offerte", "processus", "comparatif", "experte", "questions", "autrement", "commander",
      ]);
      const p = PAGE_PACK_PREMIUM;
      expect(phrases(composerTout(p, SANS), HORS_PHRASES).length).toBeGreaterThan(150);
      expect(absentes(p, SANS)).toEqual([
        p.contenuDuPack.titre,
        p.processus.titre,
        p.processus.etapes[4].corps,
        p.appelFinal.corps,
      ]);
      expect(texteDe(document.querySelector(".pak-encart .pak-prix"))).toContain(PRIX_PREMIUM);
      expect(screen.queryByRole("alert")).toBeNull();
      expect(liensDePaiement()).toHaveLength(2);
      for (const bloc of Array.from(document.querySelectorAll("[data-reveal]"))) expect(bloc).toHaveClass("est-revele");
    });

    it(`ensemble et essentiel, quand ${etat} : leurs phrases se passent de la valeur`, async () => {
      servir(reponse);
      if (lu === null) rendre("ensemble");
      else await rendreLue("ensemble", lu);
      const points = Array.from(document.querySelectorAll(".pak-points li > span:last-child")).map(texteDe);
      expect(points).toContain("BONUS EXCEPTIONNEL : ACCÈS À LA FORMATION POP");
      expect(texte()).not.toMatch(PHRASE_AMPUTEE);
      expect(texte()).not.toMatch(/913|850|1 237|VALEUR/);
      expect(absentes(PAGE_PACKS, SANS)).toEqual([PAGE_PACKS.ouverture.corps[1]]);
      expect(screen.queryByRole("alert")).toBeNull();
      cleanup();

      if (lu === null) rendre("essentiel");
      else await rendreLue("essentiel", lu);
      expect(texte()).toContain("ET la formation P.O.P IA incluse. Si vous visez un financement important");
      expect(texte()).toContain("et la formation P.O.P IA incluse. Pour les projets ambitieux");
      expect(texte()).not.toMatch(PHRASE_AMPUTEE);
      expect(texte()).not.toMatch(/913|850|1 237/);
      expect(screen.queryByRole("alert")).toBeNull();
    });
  }

  it("contre-épreuve : les détecteurs voient un montant, des chiffres de tarif, une ancienneté nue, le CDN", () => {
    for (const faute of ["Tarif : 495 €", "995€", "1 490 € TTC", "valeur 850 euros"]) {
      expect(faute, faute).toMatch(MONTANT_ECRIT);
    }
    for (const juste of ["6 semaines de support", "30 pages", "2 × 45 min", "le signe €"]) {
      expect(juste, juste).not.toMatch(MONTANT_ECRIT);
    }
    expect("const PRIX = 495;".match(chiffresDesTarifs())).toEqual(["495"]);
    expect("centimes: 49500".match(chiffresDesTarifs())).toBeNull();
    expect("largeur: 798".match(chiffresDesTarifs())).toBeNull();

    for (const faute of ["une expertise de 15 ans", "depuis 16 ans,"]) {
      expect(faute, faute).toMatch(ANCIENNETE_NUE);
    }
    for (const juste of ["plus de 16 ans de terrain", "prévisionnel sur 3 ans", "sous 15 jours"]) {
      expect(juste, juste).not.toMatch(ANCIENNETE_NUE);
    }

    expect("https://d1yei2z3i6k35z.cloudfront.net/9890127/logo.png").toMatch(ANCIEN_CDN);
    expect("/partenaires/evangeline.jpg").not.toMatch(ANCIEN_CDN);
    expect(LIENS_PACKS.commandeEssentiel).not.toMatch(ANCIEN_CDN);

    // Le collecteur de phrases descend dans les listes et saute les clés exclues.
    expect(phrases({ a: "un", lien: "#", b: ["deux", { c: "trois", d: 4, e: null }] }, ["lien"])).toEqual(["un", "deux", "trois"]);
  });

  // ── Les boutons ───────────────────────────────────────────────────────────

  it("/packs : chaque bouton d'achat mène à la page de paiement de SON pack, « Voir le détail » à sa page", () => {
    rendre("ensemble");

    const [essentiel, premium] = Array.from(document.querySelectorAll<HTMLElement>("article.pak-carte"));
    const attendus: [HTMLElement, { libelle: string; lien: string }, string, string][] = [
      [essentiel, PAGE_PACKS.packEssentiel.bouton, LIENS_PACKS.commandeEssentiel, "/packs/essentiel"],
      [premium, PAGE_PACKS.packPremium.bouton, LIENS_PACKS.commandePremium, "/packs/premium"],
    ];
    for (const [carte, bouton, paiement, detail] of attendus) {
      expect(bouton.lien).toBe(paiement);
      const dansLaCarte = liens(carte);
      expect(dansLaCarte).toHaveLength(2);
      expect(within(carte).getByRole("link", { name: new RegExp(bouton.libelle) })).toHaveAttribute("href", paiement);
      // Deux « Voir le détail » sur la page : chacun dit de quel pack.
      const versLeDetail = within(carte).getByRole("link", { name: /Voir le détail/ });
      expect(versLeDetail).toHaveAttribute("href", detail);
      expect(texteDe(versLeDetail)).toContain(texteDe(within(carte).getByRole("heading", { level: 2 })));
    }
    // Sur toute la page, un lien de paiement porte le libellé de son pack.
    const paiements = liensDePaiement();
    expect(paiements.length).toBeGreaterThanOrEqual(4);
    for (const lien of paiements) {
      const href = lien.getAttribute("href");
      const libelle = href === LIENS_PACKS.commandeEssentiel ? /ESSENTIEL/ : /PREMIUM/;
      expect([LIENS_PACKS.commandeEssentiel, LIENS_PACKS.commandePremium]).toContain(href);
      expect(texteDe(lien), href ?? "").toMatch(libelle);
    }
    // L'appel final : l'appel gratuit et les deux achats.
    const fin = document.getElementById("commander") as HTMLElement;
    expect(liens(fin).map((a) => a.getAttribute("href"))).toEqual([
      LIENS.appel,
      LIENS_PACKS.commandeEssentiel,
      LIENS_PACKS.commandePremium,
    ]);
  });

  for (const [nom, paiement, autrePaiement, autrePage] of [
    ["essentiel", LIENS_PACKS.commandeEssentiel, LIENS_PACKS.commandePremium, "/packs/premium"],
    ["premium", LIENS_PACKS.commandePremium, LIENS_PACKS.commandeEssentiel, "/packs/essentiel"],
  ] as [NomDePage, string, string, string][]) {
    it(`${nom} : tous les boutons d'achat mènent à SA page de paiement, et un lien à l'autre pack`, () => {
      rendre(nom);

      const paiements = liensDePaiement();
      // L'ouverture et l'appel final.
      expect(paiements).toHaveLength(2);
      for (const lien of paiements) expect(lien).toHaveAttribute("href", paiement);
      expect(liens().map((a) => a.getAttribute("href"))).not.toContain(autrePaiement);
      expect(document.querySelector(".pak-ouverture a.acc-btn-noir")).toHaveAttribute("href", paiement);
      expect(document.querySelector("#commander a.acc-btn-noir")).toHaveAttribute("href", paiement);
      // Le renvoi vers l'autre pack mène à sa page, pas à « # ».
      expect(liens(screen.getByRole("main")).some((a) => a.getAttribute("href") === autrePage)).toBe(true);
      expect(liens().map((a) => a.getAttribute("href"))).not.toContain("#");
      // Et un retour vers la page d'ensemble.
      expect(screen.getByRole("link", { name: COMMUN_PACKS.voirLesDeuxPacks })).toHaveAttribute("href", "/packs");
    });
  }

  // ── Rien de ce que les pages disaient n'a disparu ─────────────────────────

  it("/packs : chaque phrase de PAGE_PACKS est dans la page, sauf l'ancienneté accordée", async () => {
    await rendreLue("ensemble");

    expect(phrases(PAGE_PACKS, HORS_PHRASES).length).toBeGreaterThan(30);
    expect(absentes(PAGE_PACKS)).toEqual([PAGE_PACKS.ouverture.corps[1]]);
    expect(texte()).toContain("une expertise de plus de 16 ans à vos côtés !");
    // Le rappel de l'experte, pris à la page de l'Essentiel.
    expect(texte()).toContain(PAGE_PACK_ESSENTIEL.experte.titre);
    // L'encart de la cliente du 24/11/2026.
    expect(texte()).toContain("Une seule interlocutrice, du début à la fin");
    expect(texte()).toContain("J'ai vu ce qui convainc une banque, les questions qu'elle pose et ce qui peut la freiner.");
  });

  it("/packs/essentiel : chaque phrase du contenu est dans la page, sauf quatre anciennetés accordées", async () => {
    await rendreLue("essentiel");

    const p = PAGE_PACK_ESSENTIEL;
    // Règle 1 : une collecte vide ferait passer la comparaison sans rien vérifier.
    expect(phrases(p, HORS_PHRASES).length).toBeGreaterThan(120);
    expect(absentes(p)).toEqual([
      p.seulOuAccompagne.avecLePack.points[5],
      p.aQuoiSertLePack.benefices[2].corps,
      p.appelFinal.corps,
    ]);
    const page = texte();
    expect(page).toContain("L'accompagnement d'une experte avec plus de 16 ans de terrain");
    expect(page).toContain("Bénéficier de plus de 16 ans d'expérience");
    expect(page).toContain("En plus de 16 ans, j'ai créé des entreprises en France et en Espagne");
    expect(page).toContain("et l'expertise de plus de 16 ans à votre service. Tout est inclus.");
    // Le compte de livrables de l'Essentiel tient : il reste affiché.
    expect(page).toContain("3 livrables stratégiques + accompagnement personnalisé");
    expect(page).toContain("3 livrables professionnels, 2 appels personnalisés");
  });

  it("/packs/premium : chaque phrase du contenu est dans la page, sauf cinq phrases accordées", async () => {
    await rendreLue("premium");

    const p = PAGE_PACK_PREMIUM;
    expect(phrases(p, HORS_PHRASES).length).toBeGreaterThan(150);
    expect(absentes(p)).toEqual([
      p.contenuDuPack.titre,
      p.processus.titre,
      p.processus.etapes[4].corps,
      p.appelFinal.corps,
    ]);
    const page = texte();
    expect(page).toContain("Livrables stratégiques + accompagnement renforcé");
    expect(page).toContain(`Un parcours en ${p.processus.etapes.length} étapes sur 3 semaines`);
    expect(page).toContain("Remise des livrables : étude premium, prévisionnel");
    expect(page).toContain("En plus de 16 ans, j'ai créé des entreprises en France et en Espagne");
    expect(page).toContain("Livrables stratégiques, 3 appels d'1h, 6 semaines de support");
  });

  for (const [nom, sections] of [
    [
      "essentiel",
      ["pour-qui", "seul-ou-accompagne", "contenu", "processus", "support", "a-quoi-sert-le-pack", "apercu", "experte", "questions", "autrement", "commander"],
    ],
    [
      "premium",
      ["pour-qui", "en-plus", "contenu", "formation-offerte", "processus", "comparatif", "experte", "questions", "autrement", "commander"],
    ],
  ] as [NomDePage, string[]][]) {
    it(`${nom} : les blocs sont dans l'ordre de la page d'origine`, () => {
      rendre(nom);
      const dansLaPage = Array.from(document.querySelectorAll("main section[id]")).map((s) => s.id);
      expect(dansLaPage).toEqual(sections);
    });
  }

  // ── Les accords ───────────────────────────────────────────────────────────

  for (const [nom, contenu] of [
    ["essentiel", PAGE_PACK_ESSENTIEL],
    ["premium", PAGE_PACK_PREMIUM],
  ] as const) {
    it(`${nom} : le nombre d'étapes annoncé est celui des étapes affichées`, () => {
      rendre(nom);

      const etapes = Array.from(document.querySelectorAll("ol.pak-etapes > li"));
      expect(etapes).toHaveLength(contenu.processus.etapes.length);
      expect(etapes.map((e) => e.querySelector("h3")?.textContent)).toEqual(contenu.processus.etapes.map((e) => e.titre));
      // Numérotées sans trou.
      expect(etapes.map((e) => e.querySelector(".pak-etape-numero")?.textContent)).toEqual(
        etapes.map((_, k) => String(k + 1).padStart(2, "0")),
      );
      const annonces = [...texteDe(document.getElementById("processus")).matchAll(/(\d+) étapes/g)].map((m) => Number(m[1]));
      // Règle 1 : les deux pages annoncent un nombre d'étapes.
      expect(annonces.length).toBeGreaterThanOrEqual(1);
      for (const annonce of annonces) expect(annonce).toBe(etapes.length);
    });
  }

  it("premium : aucun nombre de livrables n'est annoncé, et l'Essentiel garde le sien", () => {
    rendre("premium");
    // Le comparatif et la formation parlent de « livrables » sans les compter.
    expect(texte()).toMatch(/livrables/i);
    expect(texte()).not.toMatch(/\d+ livrables/);
    cleanup();

    rendre("essentiel");
    expect(texte()).toMatch(/3 livrables/);
  });

  it("contre-épreuve : les accords ne retouchent que ce qu'ils visent", () => {
    expect(ancienneteSure("une expertise de 15 ans à vos côtés")).toBe("une expertise de plus de 16 ans à vos côtés");
    expect(ancienneteSure("créateurs depuis 16 ans, qui")).toBe("créateurs depuis plus de 16 ans, qui");
    expect(ancienneteSure(`avec 16${INSECABLE}ans de terrain`)).toBe(`avec plus de 16${INSECABLE}ans de terrain`);
    for (const intact of ["plus de 16 ans de terrain", "Prévisionnel financier sur 3 ans", "1 à 2 semaines", "216 ans", "15 answers"]) {
      expect(ancienneteSure(intact), intact).toBe(intact);
    }

    expect(compteRendu("Un parcours en 5 étapes sur 3 semaines", "étapes", 6)).toBe("Un parcours en 6 étapes sur 3 semaines");
    expect(compteRendu("De votre commande à votre dossier finalisé", "étapes", 5)).toBe("De votre commande à votre dossier finalisé");
    expect(compteRendu("3 appels d'1h", "étapes", 6)).toBe("3 appels d'1h");

    expect(sansCompte("9 livrables stratégiques + accompagnement renforcé", "livrables")).toBe("Livrables stratégiques + accompagnement renforcé");
    expect(sansCompte("Remise des 9 livrables : étude premium", "livrables")).toBe("Remise des livrables : étude premium");
    expect(sansCompte("validation des livrables intermédiaires", "livrables")).toBe("validation des livrables intermédiaires");
    expect(sansCompte("livrables et 3 appels", "livrables")).toBe("livrables et 3 appels");

    expect(pointDeListe("★ BONUS : Formation P.O.P IA incluse")).toEqual({ texte: "BONUS : Formation P.O.P IA incluse", vedette: true });
    expect(pointDeListe("BONUS EXCEPTIONNEL : ACCÈS")).toEqual({ texte: "BONUS EXCEPTIONNEL : ACCÈS", vedette: true });
    expect(pointDeListe("2 appels de 45 minutes")).toEqual({ texte: "2 appels de 45 minutes", vedette: false });
    expect(sansFleche(`Découvrir le Premium${INSECABLE}→`)).toBe("Découvrir le Premium");
    expect(sansFleche("Voir les études")).toBe("Voir les études");
  });

  // ── Le comparatif ─────────────────────────────────────────────────────────

  for (const nom of ["ensemble", "premium"] as NomDePage[]) {
    it(`${nom} : le comparatif est un vrai tableau, nommé, à en-têtes de colonne et de ligne`, async () => {
      await rendreLue(nom);

      // Les lignes telles que la page les affiche : la case de la formation
      // P.O.P porte la valeur que le serveur rend.
      const lignes = composerTout(PAGE_PACK_PREMIUM.comparatif.lignes, EN_LIGNE);
      expect(lignes.length).toBeGreaterThanOrEqual(12);
      const tableau = screen.getByRole("table");
      expect(tableau.querySelector("caption")).toHaveTextContent(COMPARATIF_PACKS.legende);

      // La boîte qui peut défiler : nommée par la légende, et focalisable.
      const boite = tableau.closest("[role='region']") as HTMLElement;
      expect(boite).not.toBeNull();
      expect(boite).toHaveAttribute("tabindex", "0");
      expect(document.getElementById(boite.getAttribute("aria-labelledby") ?? "")).toBe(tableau.querySelector("caption"));

      const colonnes = Array.from(tableau.querySelectorAll("thead th"));
      expect(colonnes.map((c) => c.textContent)).toEqual([COMPARATIF_PACKS.colonneDesCriteres, "Essentiel", "Premium"]);
      for (const colonne of colonnes) expect(colonne).toHaveAttribute("scope", "col");

      const rangs = Array.from(tableau.querySelectorAll("tbody tr"));
      expect(rangs).toHaveLength(lignes.length);
      rangs.forEach((rang, k) => {
        const entete = rang.querySelector("th");
        expect(entete).toHaveAttribute("scope", "row");
        expect(entete).toHaveTextContent(lignes[k].critere);
        const cases = Array.from(rang.querySelectorAll("td"));
        expect(cases).toHaveLength(2);
        [lignes[k].essentiel, lignes[k].premium].forEach((valeur, c) => {
          const signe = COMPARATIF_PACKS.signes.find((s) => valeur.startsWith(s.signe));
          if (!signe) {
            expect(texteDe(cases[c]), lignes[k].critere).toBe(espaces(valeur));
            return;
          }
          // Le signe est affiché mais masqué aux lecteurs d'écran, qui
          // entendent sa lecture ; le reste de la case suit.
          expect(cases[c].querySelector("[aria-hidden='true']")).toHaveTextContent(signe.signe);
          expect(cases[c].querySelector(".pak-lu")).toHaveTextContent(signe.lecture);
          expect(texteDe(cases[c])).toContain(espaces(valeur.slice(signe.signe.length).trim()));
        });
      });
      // La ligne des prix lit la constante.
      const prixDuTableau = Array.from(rangs[rangs.length - 1].querySelectorAll("td")).map((c) => texteDe(c));
      expect(prixDuTableau).toEqual([PRIX_ESSENTIEL, PRIX_PREMIUM]);
    });
  }

  it("essentiel : pas de tableau — la page d'origine n'en a pas", () => {
    rendre("essentiel");
    expect(screen.queryByRole("table")).toBeNull();
    expect(document.getElementById("comparatif")).toBeNull();
  });

  // ── Les cartes sans chiffre, les questions, les aperçus ───────────────────

  it("premium : une carte dont le chiffre est null s'affiche sans chiffre", () => {
    rendre("premium");

    const attendues = PAGE_PACK_PREMIUM.cePlusDuPremium.cartes;
    expect(attendues.length).toBe(3);
    const cartes = Array.from(document.querySelectorAll("#en-plus .pak-plus > li"));
    expect(cartes).toHaveLength(attendues.length);
    cartes.forEach((carte, k) => {
      expect(carte.querySelector("h3")).toHaveTextContent(attendues[k].titre);
      expect(texteDe(carte)).toContain(attendues[k].corps);
      if (attendues[k].chiffre === null) {
        expect(carte.querySelector(".pak-plus-chiffre"), attendues[k].titre).toBeNull();
        // Rien d'inventé à la place : pas un chiffre avant le titre.
        expect(texteDe(carte).split(attendues[k].titre)[0]).not.toMatch(/\d|\+/);
      } else {
        expect(carte.querySelector(".pak-plus-chiffre")).toHaveTextContent(attendues[k].chiffre as string);
      }
    });
  });

  for (const [nom, contenu] of [
    ["essentiel", PAGE_PACK_ESSENTIEL],
    ["premium", PAGE_PACK_PREMIUM],
  ] as const) {
    it(`${nom} : ses vraies questions, en <details>, dans l'ordre, la première ouverte`, () => {
      rendre(nom);

      const questions = Array.from(document.querySelectorAll("#questions details"));
      expect(questions).toHaveLength(contenu.faq.questions.length);
      expect(questions.length).toBeGreaterThanOrEqual(8);
      expect(questions.map((q) => q.querySelector("summary")?.textContent)).toEqual(contenu.faq.questions.map((q) => q.question));
      expect(questions[0]).toHaveAttribute("open");
      expect(questions[1]).not.toHaveAttribute("open");
    });
  }

  it("essentiel : trois aperçus de documents, chacun avec sa vignette, son étiquette et son titre", () => {
    rendre("essentiel");

    const attendus = PAGE_PACK_ESSENTIEL.apercuDesDocuments.documents;
    const apercus = Array.from(document.querySelectorAll("#apercu .pak-documents > li"));
    expect(apercus).toHaveLength(attendus.length);
    expect(apercus.length).toBe(3);
    apercus.forEach((apercu, k) => {
      expect(texteDe(apercu.querySelector(".pak-vignette"))).toContain(attendus[k].vignette.titre);
      expect(texteDe(apercu.querySelector(".pak-vignette-volume"))).toBe(attendus[k].vignette.volume);
      expect(texteDe(apercu)).toContain(attendus[k].etiquette);
      expect(apercu.querySelector("h3")).toHaveTextContent(attendus[k].titre);
    });
  });

  // ── Les sources du lot ────────────────────────────────────────────────────

  for (const fichier of ["Packs.tsx", "Packs.css"]) {
    it(`${fichier} ne pointe vers aucune adresse de l'ancien CDN`, () => {
      // Commentaires COMPRIS : une adresse citée en commentaire reviendrait au
      // prochain copier-coller.
      const brute = source(fichier);
      expect(brute.length).toBeGreaterThan(5000);
      expect(brute.match(new RegExp(ANCIEN_CDN.source, "gi")) ?? []).toEqual([]);
    });
  }

  it("Packs.tsx ne recopie pas le texte : il l'importe de contenuPacks.ts", () => {
    const code = sansCommentaires(source("Packs.tsx"));
    // Quelques phrases du contenu, prises dans chaque page : aucune n'est
    // écrite dans le composant.
    for (const phrase of [
      PAGE_PACKS.ouverture.titre,
      PAGE_PACK_ESSENTIEL.ouverture.titre,
      PAGE_PACK_PREMIUM.experte.titre,
      COMMUN_PACKS.appelGratuit,
    ]) {
      expect(code, phrase).not.toContain(phrase);
    }
    expect(code).toContain('from "./contenuPacks"');
    // Les deux pages de pack sont jumelles : UN composant, deux contenus.
    expect(code.match(/<PageDePack\b/g)).toHaveLength(2);
    expect(code.match(/function PageDePack\b/g)).toHaveLength(1);
  });
});

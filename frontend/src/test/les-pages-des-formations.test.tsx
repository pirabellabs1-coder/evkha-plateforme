/** Les quatre pages de l'Académie : le catalogue des formations et les trois
 * pages de formation (`Formations.tsx`).
 *
 * Elles reprennent `evkha.fr/formation` et les trois pages `/achat-formation*`
 * dans la plateforme. Ce que ce fichier verrouille :
 *
 * 1. chaque page se rend, avec UN `h1`, des titres sans saut, son propre titre
 *    d'onglet et sa propre description ;
 * 2. les prix sont ceux de `TARIFS_FORMATIONS` — la page les LIT : un tarif
 *    changé dans la constante change la page (contre-épreuve d'un prix
 *    recopié), et aucun montant n'est écrit dans `Formations.tsx` ;
 * 3. chaque bouton d'achat mène au tunnel de paiement de SA formation, et le
 *    catalogue mène aux pages de la plateforme, jamais à un tunnel ;
 * 4. aucun formulaire : le présentiel et le financement passent par un
 *    courriel prérempli ;
 * 5. le programme affiche son titre, ses phrases et le NOMBRE de modules, sans
 *    liste tant que le tableau est vide — et la liste dès qu'il est rempli ;
 * 6. ce qui ne doit pas s'afficher ne s'affiche pas : la certification à
 *    confirmer, l'outillage de l'ancien site, la pastille « 9 modules » de la
 *    formation « sociétés », le bloc de commande de l'ancien tunnel ;
 * 7. les trois contradictions du relevé sont rendues comme décidé :
 *    « plus de 15 ans », l'assistant IA aux seules formations qui l'annoncent ;
 * 8. RIEN de ce que le relevé dit de chaque page n'a disparu ;
 * 9. la passerelle vers les packs et les études précède l'appel final, sans
 *    un prix ;
 * 10. aucune adresse du CDN de l'ancien site dans les sources du lot.
 *
 * NON REJOUÉ contre un code d'avant : ces pages sont nouvelles. Chaque verrou
 * de lecture de sources porte sa contre-épreuve (le détecteur voit bien ce
 * qu'il cherche), et le verrou des prix se prouve en changeant la constante.
 *
 * `React` est importé nommément : `src/test` est hors du `tsconfig`, le JSX y
 * est compilé en `React.createElement` classique.
 */
import React from "react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  ARTICULATION,
  ATOUTS_DES_FORMATIONS,
  ATTESTATION_AFFICHEE,
  CARTE_MICRO,
  CARTE_POP,
  CARTE_SOCIETES,
  COMMANDE_D_UNE_FORMATION,
  IMAGES_FORMATIONS_A_RAPATRIER,
  INCLUS_AFFICHE,
  LIENS_FORMATIONS,
  NOMBRE_DE_MODULES,
  ORGANISME_DE_FORMATION,
  PAGE_CATALOGUE,
  PAGE_MICRO,
  PAGE_POP,
  PAGE_SOCIETES,
  PRESENTIEL,
  PROMESSE_POP_AFFICHEE,
  QUESTIONS_DES_FORMATIONS,
  ROUTES_FORMATIONS,
  TARIFS_FORMATIONS,
  questionsAffichees,
  sansFleche,
  type CarteDeFormation,
  type CleDeFormation,
} from "../public/contenuFormations";
import {
  FormationMicro,
  FormationPop,
  FormationSocietes,
  Formations,
} from "../public/Formations";

// ── Outils ──────────────────────────────────────────────────────────────────

/** Les deux espaces insécables, construites par leur code, jamais tapées :
 *  écrites en clair, elles sont invisibles à la relecture et un outil
 *  d'édition les change sans le dire. */
const INSECABLE = String.fromCharCode(0xa0);
const FINE_INSECABLE = String.fromCharCode(0x202f);
const INSECABLES = new RegExp(`[${INSECABLE}${FINE_INSECABLE}]`, "g");

function espaces(brut: string): string {
  return brut.replace(INSECABLES, " ");
}

/** Le texte de la page, insécables ramenées à des espaces. */
function texte(): string {
  return espaces(document.body.textContent ?? "");
}

function texteDe(element: Element | null): string {
  return espaces(element?.textContent ?? "");
}

function section(id: string): HTMLElement {
  const trouvee = document.getElementById(id);
  if (!trouvee) throw new Error(`section introuvable : #${id}`);
  return trouvee;
}

/** Toutes les phrases d'un objet de contenu, à plat. */
function phrases(valeur: unknown): string[] {
  if (typeof valeur === "string") return [valeur];
  if (Array.isArray(valeur)) return valeur.flatMap(phrases);
  if (valeur && typeof valeur === "object") return Object.values(valeur).flatMap(phrases);
  return [];
}

function sansCommentaires(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

function source(fichier: string): string {
  return readFileSync(join(process.cwd(), "src", "public", fichier), "utf-8");
}

/** Un nombre entier écrit à la française, par groupes de trois : « 1 490 ».
 *  Écrit ICI à la main : le test ne demande pas son résultat à la fonction du
 *  site (`donnees.euros`) qu'il éprouve. */
function parMilliers(entier: number): string {
  return String(entier).replace(/\B(?=(\d{3})+$)/g, " ");
}

/** Le prix d'une formation, RECALCULÉ ici sur la constante de tarifs — et non
 *  demandé à `prixAffiche`, que la page appelle : le test ne doit pas juger la
 *  page avec la fonction de la page. Au format du reste du site : « 1 490 €
 *  TTC », séparateur de milliers compris. */
function prixAttendu(cle: CleDeFormation): string {
  const tarif = TARIFS_FORMATIONS[cle];
  return `${parMilliers(tarif.centimes / 100)} €${tarif.ttc ? " TTC" : ""}`;
}

/** Un montant en euros écrit dans une source. */
const MONTANT_ECRIT = /\d[\d\s.,]*(?:€|euros?\b)/i;

/** Une adresse du CDN de l'ancien site (systeme.io). */
const CDN = /cloudfront\.net|d1yei2z3i6k35z/i;

/** Une espace ORDINAIRE avant « € », ou collée à une flèche. */
const ESPACE_FAUTIVE = / €| [→←↗↓]|[→←↗↓] /;

const ANCIEN_NOM = new RegExp(`p[oô]le[\\s${INSECABLE}-]+emploi`, "i");

/** Ce qu'aucune des quatre pages ne doit afficher. */
const NON_AFFICHE = /qualiopi|canva|systeme\.io/i;

/** Une promesse de contenu à venir : la section du programme n'en fait pas. */
const A_VENIR = /bient[oô]t|prochainement|à venir|disponible/i;

// ── Les quatre pages ────────────────────────────────────────────────────────

type Page = {
  nom: string;
  route: string;
  Composant: () => React.JSX.Element;
  /** `null` : le catalogue. */
  cle: CleDeFormation | null;
};

const CATALOGUE: Page = {
  nom: "le catalogue",
  route: ROUTES_FORMATIONS.catalogue,
  Composant: Formations,
  cle: null,
};
const SOCIETES: Page = {
  nom: "la formation « sociétés »",
  route: ROUTES_FORMATIONS.societes,
  Composant: FormationSocietes,
  cle: "societes",
};
const MICRO: Page = {
  nom: "la formation « micro-entreprise »",
  route: ROUTES_FORMATIONS.micro,
  Composant: FormationMicro,
  cle: "micro",
};
const POP: Page = {
  nom: "la Méthode P.O.P",
  route: ROUTES_FORMATIONS.pop,
  Composant: FormationPop,
  cle: "pop",
};

const PAGES = [CATALOGUE, SOCIETES, MICRO, POP];
const FICHES = [SOCIETES, MICRO, POP];

const PAIEMENTS: Record<CleDeFormation, string> = {
  societes: LIENS_FORMATIONS.paiementSocietes,
  micro: LIENS_FORMATIONS.paiementMicro,
  pop: LIENS_FORMATIONS.paiementPop,
};

const BOUTONS_D_ACHAT: Record<CleDeFormation, string> = {
  societes: PAGE_SOCIETES.appelFinal.bouton.libelle,
  micro: PAGE_MICRO.appelFinal.bouton.libelle,
  pop: PAGE_POP.appelFinal.bouton.libelle,
};

function afficher(page: Page) {
  window.history.pushState({}, "", page.route);
  return render(<page.Composant />);
}

/** Les liens de la page, hors barre, menu et pied (le socle). */
function liensDuContenu(): HTMLAnchorElement[] {
  return Array.from(screen.getByRole("main").querySelectorAll("a"));
}

// ── Ce que le relevé dit de chaque page ─────────────────────────────────────

/** Ce qu'une carte du catalogue dit — sans sa clé ni l'adresse de son bouton,
 *  qui ne sont pas des phrases. */
function phrasesDeLaCarte(carte: CarteDeFormation): string[] {
  return phrases([
    carte.titre,
    carte.sousTitre,
    carte.accroche,
    carte.mention,
    carte.modalites,
    carte.corps,
    carte.titreDesAcquis,
    carte.acquis,
    sansFleche(carte.bouton.libelle),
  ]);
}

/** Les blocs communs : atouts, présentiel (sans sa fenêtre d'inscription, qui
 *  était un formulaire), financement. */
const COMMUN = phrases([
  ATOUTS_DES_FORMATIONS,
  PRESENTIEL.surtitre,
  PRESENTIEL.titre,
  PRESENTIEL.corps,
  PRESENTIEL.lieux,
  PRESENTIEL.points,
  PRESENTIEL.bouton.libelle,
  ORGANISME_DE_FORMATION.nda,
  ORGANISME_DE_FORMATION.financement,
  QUESTIONS_DES_FORMATIONS.surtitre,
  QUESTIONS_DES_FORMATIONS.titre,
]);

const coachingSocietes = PAGE_SOCIETES.modalites.coaching;
const coachingMicro = PAGE_MICRO.modalites.coaching;

const ATTENDU: Record<string, string[]> = {
  [CATALOGUE.route]: phrases([
    PAGE_CATALOGUE.ouverture,
    PAGE_CATALOGUE.pourquoi.titre,
    PAGE_CATALOGUE.pourquoi.paragraphes,
    PAGE_CATALOGUE.formations.titre,
    PAGE_CATALOGUE.formations.cartes.map(phrasesDeLaCarte),
    // La carte de la micro-entreprise n'a pas de repères relevés : la page
    // lui donne ceux de l'ouverture de sa page d'achat.
    PAGE_MICRO.ouvertureEnImage.pastilles,
    PAGE_CATALOGUE.pourQui,
    // Le TITRE de la section d'avis est retouché à l'affichage (voir le test
    // qui lui est propre) : seul le surtitre relevé s'affiche tel quel.
    PAGE_CATALOGUE.avis.surtitre,
    questionsAffichees("catalogue"),
    COMMUN,
  ]),
  [SOCIETES.route]: phrases([
    PAGE_SOCIETES.ouvertureEnImage.etiquette,
    PAGE_SOCIETES.ouvertureEnImage.titre,
    PAGE_SOCIETES.ouvertureEnImage.accroche,
    PAGE_SOCIETES.ouvertureEnImage.corps,
    PAGE_SOCIETES.ouvertureEnImage.statuts,
    PAGE_SOCIETES.ouvertureEnImage.pastilles,
    CARTE_SOCIETES.accroche,
    CARTE_SOCIETES.mention,
    CARTE_SOCIETES.modalites,
    CARTE_SOCIETES.titreDesAcquis,
    CARTE_SOCIETES.acquis,
    PAGE_SOCIETES.pourQui.surtitre,
    PAGE_SOCIETES.pourQui.titre,
    PAGE_SOCIETES.pourQui.argumentaire,
    PAGE_SOCIETES.pourQui.aQui,
    PAGE_SOCIETES.objectifs,
    PAGE_SOCIETES.programme.surtitre,
    PAGE_SOCIETES.programme.titre,
    PAGE_SOCIETES.programme.corps,
    PAGE_SOCIETES.statuts.surtitre,
    PAGE_SOCIETES.statuts.titre,
    PAGE_SOCIETES.statuts.corps.slice(1),
    PAGE_SOCIETES.statuts.formes,
    PAGE_SOCIETES.inclus.surtitre,
    PAGE_SOCIETES.inclus.titre,
    INCLUS_AFFICHE.societes,
    coachingSocietes.surtitre,
    coachingSocietes.titre,
    coachingSocietes.corps,
    coachingSocietes.captureDAchat,
    coachingSocietes.points,
    PAGE_SOCIETES.appelFinal.bouton.libelle,
    questionsAffichees("societes"),
    COMMUN,
  ]),
  [MICRO.route]: phrases([
    PAGE_MICRO.ouvertureEnImage,
    CARTE_MICRO.mention,
    CARTE_MICRO.titreDesAcquis,
    CARTE_MICRO.acquis,
    PAGE_MICRO.pourQui.surtitre,
    PAGE_MICRO.pourQui.titre,
    PAGE_MICRO.pourQui.argumentaire,
    PAGE_MICRO.pourQui.aQui,
    PAGE_MICRO.objectifs,
    PAGE_MICRO.programme.surtitre,
    PAGE_MICRO.programme.titre,
    PAGE_MICRO.programme.corps,
    PAGE_MICRO.inclus.surtitre,
    PAGE_MICRO.inclus.titre,
    INCLUS_AFFICHE.micro,
    coachingMicro.surtitre,
    coachingMicro.titre,
    coachingMicro.corps,
    coachingMicro.points,
    PAGE_MICRO.appelFinal.bouton.libelle,
    questionsAffichees("micro"),
    COMMUN,
  ]),
  [POP.route]: phrases([
    PAGE_POP.ouverture,
    PAGE_POP.pourQui.surtitre,
    PAGE_POP.pourQui.titre,
    PAGE_POP.pourQui.argumentaire,
    PAGE_POP.pourQui.public,
    PROMESSE_POP_AFFICHEE,
    PAGE_POP.objectifs,
    PAGE_POP.methode,
    PAGE_POP.inclus.surtitre,
    PAGE_POP.inclus.titre,
    INCLUS_AFFICHE.pop,
    PAGE_POP.modalites,
    CARTE_POP.sousTitre,
    CARTE_POP.accroche,
    CARTE_POP.corps,
    CARTE_POP.titreDesAcquis,
    CARTE_POP.acquis,
    PAGE_POP.appelFinal.bouton.libelle,
    questionsAffichees("pop"),
    COMMUN,
  ]),
};

describe("les pages des formations", () => {
  // `useTitreDePage` écrit la description dans la balise du gabarit HTML :
  // jsdom n'en a pas, on la pose.
  let meta: HTMLMetaElement;
  beforeEach(() => {
    meta = document.createElement("meta");
    meta.name = "description";
    meta.content = "gabarit";
    document.head.appendChild(meta);
  });
  afterEach(() => {
    meta.remove();
    window.history.pushState({}, "", "/");
  });

  // ── Chaque page se rend et se laisse conduire ─────────────────────────────

  for (const page of PAGES) {
    it(`${page.nom} : un seul h1, des titres sans saut, un lien d'évitement`, () => {
      afficher(page);

      expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
      const niveaux = Array.from(document.querySelectorAll("h1, h2, h3, h4, h5, h6")).map((t) =>
        Number(t.tagName[1]),
      );
      expect(niveaux[0]).toBe(1);
      expect(niveaux.length).toBeGreaterThan(12);
      niveaux.forEach((niveau, k) => {
        if (k > 0) expect(niveau - niveaux[k - 1], `saut de titre au rang ${k}`).toBeLessThanOrEqual(1);
      });

      const principal = screen.getByRole("main");
      expect(principal.id).not.toBe("");
      expect(screen.getByRole("link", { name: "Aller au contenu" })).toHaveAttribute("href", `#${principal.id}`);

      // Rien de focalisable sous `aria-hidden`.
      const caches = Array.from(document.querySelectorAll("[aria-hidden='true']"));
      expect(caches.length).toBeGreaterThan(10);
      for (const cache of caches) {
        expect(cache.querySelector("a, button, input, select, textarea, summary, [tabindex]"), cache.className).toBeNull();
      }
      // Les blocs à révéler le sont : sans observateur (jsdom), tout s'affiche.
      const blocs = Array.from(document.querySelectorAll("[data-reveal]"));
      expect(blocs.length).toBeGreaterThan(8);
      for (const bloc of blocs) expect(bloc).toHaveClass("est-revele");
    });

    it(`${page.nom} : aucun formulaire, aucun champ, aucune image de l'ancien site`, () => {
      afficher(page);

      expect(document.querySelector("form")).toBeNull();
      expect(document.querySelector("input, textarea, select")).toBeNull();
      for (const image of Array.from(document.querySelectorAll("img"))) {
        expect(image.hasAttribute("alt"), image.getAttribute("src") ?? "").toBe(true);
        expect(image.getAttribute("src") ?? "", "image hors de la plateforme").toMatch(/^\/(?!\/)/);
        expect(Number(image.getAttribute("width"))).toBeGreaterThan(0);
        expect(Number(image.getAttribute("height"))).toBeGreaterThan(0);
      }
      // Aucun lien du contenu ne mène au CDN ni aux pages de vente de
      // l'ancien site — seuls les tunnels de paiement y restent.
      const tunnels = Object.values(PAIEMENTS) as string[];
      for (const lien of liensDuContenu()) {
        const adresse = lien.getAttribute("href") ?? "";
        expect(adresse, texteDe(lien)).not.toMatch(CDN);
        if (/evkha\.fr/.test(adresse) && !adresse.startsWith("mailto:")) {
          expect(tunnels, texteDe(lien)).toContain(adresse);
        }
      }
    });

    it(`${page.nom} : rien de ce que le relevé dit n'a disparu`, () => {
      afficher(page);

      const attendues = ATTENDU[page.route];
      // Règle 1 : une collecte vide ferait passer la boucle sans rien vérifier.
      expect(attendues.length).toBeGreaterThan(55);
      const affiche = texte();
      for (const phrase of attendues) {
        expect(affiche, `${page.nom} ne dit plus : « ${phrase} »`).toContain(espaces(phrase));
      }
    });

    it(`${page.nom} : la typographie du texte affiché, et France Travail sous son nom`, () => {
      afficher(page);

      // Sur le texte BRUT : une insécable est juste, une espace ordinaire non.
      expect(document.body.textContent ?? "").not.toMatch(ESPACE_FAUTIVE);
      expect(texte()).not.toMatch(ANCIEN_NOM);
      expect(texteDe(section("financement"))).toContain("France Travail");
    });

    it(`${page.nom} : financement, présentiel et passerelle, sans formulaire ni prix`, () => {
      afficher(page);

      // Le numéro de déclaration d'activité, tel que la constante l'écrit.
      const financement = section("financement");
      expect(texteDe(financement.querySelector(".for-nda-numero"))).toBe(ORGANISME_DE_FORMATION.nda);
      expect(texteDe(financement)).toContain(ORGANISME_DE_FORMATION.financement.reponse);
      expect(texteDe(financement)).toContain("OPCO");
      const ecrire = within(financement).getByRole("link");
      expect(ecrire.getAttribute("href")).toMatch(/^mailto:contact@evkha\.fr\?subject=\S+$/);

      // Le présentiel : Lille ou Paris, et un courriel prérempli pour les
      // prochaines dates — pas la fenêtre d'inscription de l'ancien site.
      const presentiel = section("presentiel");
      expect(texteDe(presentiel)).toMatch(/LILLE ou PARIS/);
      const dates = within(presentiel).getByRole("link", { name: PRESENTIEL.bouton.libelle });
      expect(dates.getAttribute("href")).toBe(
        `mailto:contact@evkha.fr?subject=${encodeURIComponent(ARTICULATION.presentiel.objetDuCourriel)}`,
      );
      for (const phrase of phrases(PRESENTIEL.inscription)) {
        expect(texte(), phrase).not.toContain(phrase);
      }

      // La passerelle : les packs et les études, sans un prix, avant l'appel
      // final.
      const passerelle = section("autrement");
      const portes = within(passerelle).getAllByRole("link");
      expect(portes.map((porte) => porte.getAttribute("href"))).toEqual(["/packs", "/etudes"]);
      expect(texteDe(passerelle)).not.toMatch(MONTANT_ECRIT);
      const fin = document.querySelector(".acc-fin") as HTMLElement;
      expect(fin).not.toBeNull();
      expect(passerelle.compareDocumentPosition(fin) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

      // Les questions : en <details>, la première ouverte.
      const questions = Array.from(section("questions").querySelectorAll("details"));
      const cle = page.cle ?? "catalogue";
      expect(questions).toHaveLength(questionsAffichees(cle).length);
      expect(questions.length).toBeGreaterThanOrEqual(3);
      expect(questions[0]).toHaveAttribute("open");
      expect(questions[1]).not.toHaveAttribute("open");
    });

    it(`${page.nom} : ce qui n'est pas confirmé ne s'affiche pas`, () => {
      afficher(page);

      expect(texte()).not.toMatch(NON_AFFICHE);
      expect(texte()).not.toContain("16 ans");
      expect(texte()).not.toContain("(15 ans d'expérience)");
      expect(texte()).not.toContain("Chaque formation inclut");
      // Le bloc de commande de l'ancien tunnel n'est pas rendu.
      for (const phrase of phrases(COMMANDE_D_UNE_FORMATION)) {
        expect(texte(), phrase).not.toContain(phrase);
      }
      for (const commande of [PAGE_SOCIETES.commande, PAGE_MICRO.commande, PAGE_POP.commande]) {
        expect(texte()).not.toContain(commande.titre);
        expect(texte()).not.toContain(commande.bouton);
      }
    });

    it(`${page.nom} : deux boutons de pause, un seul état, un ruban décoratif`, () => {
      const { container } = afficher(page);

      const boutons = screen.getAllByRole("button", { name: "Mettre les animations en pause" });
      expect(boutons).toHaveLength(2);
      fireEvent.click(boutons[1]);
      expect(container.querySelector(".acc")).toHaveClass("acc-fige");
      for (const bouton of screen.getAllByRole("button", { name: "Relancer les animations" })) {
        expect(bouton).toHaveAttribute("aria-pressed", "true");
      }
      const ruban = document.querySelector(".acc-ruban") as HTMLElement;
      expect(ruban).toHaveAttribute("aria-hidden", "true");
      expect(ruban.querySelectorAll("span").length).toBeGreaterThanOrEqual(20);
    });
  }

  it("chaque page a son titre d'onglet et sa description, et les rend en partant", () => {
    const titres = new Set<string>();
    const descriptions = new Set<string>();
    for (const page of PAGES) {
      const { unmount } = afficher(page);
      // UN format sur tout le site : « Titre de la page — EVKHA ».
      expect(document.title, page.nom).toMatch(/\S — EVKHA$/);
      expect(document.title, page.nom).not.toMatch(/[–|]\s*EVKHA/);
      expect(meta.content, page.nom).not.toBe("gabarit");
      // Aucune page ne tutoie dans son onglet.
      expect(`${document.title} ${meta.content}`, page.nom).not.toMatch(/(?<!\p{L})(ton|ta|tes|toi)(?!\p{L})/iu);
      titres.add(document.title);
      descriptions.add(meta.content);
      unmount();
      expect(meta.content, page.nom).toBe("gabarit");
    }
    expect(titres.size).toBe(PAGES.length);
    expect(descriptions.size).toBe(PAGES.length);
  });

  // ── Les prix ──────────────────────────────────────────────────────────────

  it("le catalogue : chaque carte porte SON nom, SON prix, et mène à SA page", () => {
    afficher(CATALOGUE);

    const cartes = Array.from(document.querySelectorAll<HTMLElement>("article.for-carte"));
    expect(cartes.map((carte) => carte.id)).toEqual(["formation-societes", "formation-micro", "formation-pop"]);
    const attendus: [CarteDeFormation, string][] = [
      [CARTE_SOCIETES, "/formations/creer-son-entreprise"],
      [CARTE_MICRO, "/formations/creer-sa-micro-entreprise"],
      [CARTE_POP, "/formations/methode-pop"],
    ];
    attendus.forEach(([carte, route], k) => {
      const c = cartes[k];
      expect(within(c).getByRole("heading", { level: 3 })).toHaveTextContent(carte.titre);
      expect(texteDe(c.querySelector(".for-prix")), carte.cle).toBe(prixAttendu(carte.cle));
      // UN lien dans la carte : la page de la formation, sur la plateforme.
      const liens = within(c).getAllByRole("link");
      expect(liens, carte.cle).toHaveLength(1);
      expect(liens[0], carte.cle).toHaveAttribute("href", route);
      // La flèche du libellé relevé n'est pas doublée par celle du bouton.
      expect(texteDe(liens[0]).match(/→/g), carte.cle).toHaveLength(1);
      // Des repères de durée ou de format sur chacune.
      expect(c.querySelectorAll(".for-pastilles li").length, carte.cle).toBeGreaterThanOrEqual(2);
    });

    // Le catalogue ne vend rien lui-même : aucun lien vers un tunnel.
    const adresses = liensDuContenu().map((lien) => lien.getAttribute("href"));
    for (const tunnel of Object.values(PAIEMENTS)) expect(adresses).not.toContain(tunnel);
    expect(document.querySelector(".for-bouton-achat")).toBeNull();
    // Le bouton de l'ouverture mène aux cartes, qui existent.
    expect(document.querySelector(".for-ouverture a")).toHaveAttribute("href", "#nos-formations");
    expect(document.getElementById("nos-formations")).not.toBeNull();
    // L'appel final : un rendez-vous et un courriel.
    const fin = section("contact");
    expect(within(fin).getByRole("link", { name: /Réserver un appel/ })).toHaveAttribute("href", "https://calendly.com/contact-evkha");
    expect(within(fin).getByRole("link", { name: /Écrire à EVKHA/ }).getAttribute("href")).toMatch(/^mailto:contact@evkha\.fr\?subject=/);
  });

  it("le catalogue : le visuel est servi par la plateforme, à sa place réservée", () => {
    afficher(CATALOGUE);

    const visuel = document.querySelector<HTMLImageElement>("img.for-image");
    expect(visuel).toHaveAttribute("src", "/accueil/formations.webp");
    expect(visuel).toHaveAttribute("width", "1080");
    expect(visuel).toHaveAttribute("height", "1080");
    expect(visuel?.getAttribute("alt") ?? "").not.toBe("");
    // Les avis : le texte retranscrit, avec la phrase qui dit d'où ils viennent.
    expect(section("avis").querySelectorAll("figure").length).toBeGreaterThanOrEqual(6);
    expect(texteDe(section("avis"))).toContain("Recopiés tels qu'ils ont été écrits");
    // Les cinq profils, dans l'ordre de la page.
    const profils = Array.from(section("pour-qui").querySelectorAll(".for-publics li")).map((li) =>
      texteDe(li).replace(/^\d+/, ""),
    );
    expect(profils).toEqual(PAGE_CATALOGUE.pourQui.profils);
  });

  for (const page of FICHES) {
    const cle = page.cle as CleDeFormation;

    it(`${page.nom} : son prix est celui de la constante, ses boutons d'achat mènent à SON tunnel`, () => {
      afficher(page);

      const prix = Array.from(document.querySelectorAll(".for-prix, .for-fin-prix")).map(texteDe);
      // L'ouverture, « en pratique », l'appel final.
      expect(prix).toEqual([prixAttendu(cle), prixAttendu(cle), prixAttendu(cle)]);

      const achats = Array.from(document.querySelectorAll<HTMLAnchorElement>("a.for-bouton-achat"));
      expect(achats).toHaveLength(3);
      for (const achat of achats) {
        expect(achat).toHaveAttribute("href", PAIEMENTS[cle]);
        expect(achat).toHaveAttribute("rel", "noopener");
        expect(texteDe(achat)).toContain(BOUTONS_D_ACHAT[cle]);
      }
      // Un dans l'ouverture, un dans « en pratique », un dans l'appel final.
      expect(document.querySelector(".for-ouverture a.for-bouton-achat")).not.toBeNull();
      expect(section("modalites").querySelector("a.for-bouton-achat")).not.toBeNull();
      expect(section("rejoindre").querySelector("a.for-bouton-achat")).not.toBeNull();
      // Aucun lien vers le tunnel d'une AUTRE formation.
      const adresses = liensDuContenu().map((lien) => lien.getAttribute("href"));
      for (const [autre, tunnel] of Object.entries(PAIEMENTS)) {
        if (autre !== cle) expect(adresses, autre).not.toContain(tunnel);
      }
    });

    it(`${page.nom} : la carte de l'attestation porte la formulation du tunnel P.O.P`, () => {
      afficher(page);

      const inclus = section("inclus");
      const titres = Array.from(inclus.querySelectorAll("h3")).map(texteDe);
      expect(titres).toHaveLength(6);
      expect(titres).toEqual(INCLUS_AFFICHE[cle].map((carte) => carte.titre));
      expect(titres[5]).toBe(ATTESTATION_AFFICHEE);
      expect(ATTESTATION_AFFICHEE).toBe("Attestation de fin de formation");
    });
  }

  it("contre-épreuve : un tarif changé dans la constante change la page — le prix est LU", () => {
    // Un montant que personne n'écrirait de mémoire. `as const` ne fige que
    // le type : l'objet se laisse modifier, le temps du test.
    const tarif = TARIFS_FORMATIONS.societes as { centimes: number };
    const dAvant = tarif.centimes;
    const prixDAvant = prixAttendu("societes");
    tarif.centimes = 123700;
    try {
      afficher(SOCIETES);
      const prix = Array.from(document.querySelectorAll(".for-prix, .for-fin-prix")).map(texteDe);
      // Au format du site : le séparateur de milliers y est.
      expect(prix).toEqual(["1 237 € TTC", "1 237 € TTC", "1 237 € TTC"]);
      expect(texte()).not.toContain(prixDAvant);
      expect(texte()).not.toContain(`${dAvant / 100} €`);
    } finally {
      tarif.centimes = dAvant;
    }
    expect(prixAttendu("societes")).toBe(prixDAvant);
    expect(prixDAvant).toBe(`${parMilliers(dAvant / 100)} € TTC`);
  });

  it("les prix s'affichent comme sur le reste du site : milliers séparés, insécables aux bons endroits", () => {
    afficher(CATALOGUE);
    const bruts = Array.from(document.querySelectorAll("article.for-carte .for-prix")).map((e) => e.textContent ?? "");
    expect(bruts).toHaveLength(3);
    for (const brut of bruts) {
      // Une insécable avant « € », jamais une espace ordinaire ; et un
      // montant de quatre chiffres ne s'écrit pas d'un bloc.
      expect(brut).toMatch(new RegExp(`${INSECABLE}€`));
      expect(brut).not.toMatch(/\d{4}/);
      expect(brut).not.toMatch(/\d \d/);
    }
    // Le séparateur de milliers est une espace insécable — fine ou non, selon
    // la version des données de langue.
    const avecMilliers = bruts.filter((brut) => /\d[\u00a0\u202f]\d{3}/.test(brut));
    expect(avecMilliers.length).toBeGreaterThanOrEqual(2);
    // Contre-épreuves du calcul d'ici.
    expect(parMilliers(850)).toBe("850");
    expect(parMilliers(1490)).toBe("1 490");
    expect(parMilliers(12345)).toBe("12 345");
    expect(parMilliers(1234567)).toBe("1 234 567");
  });

  it("la section d'avis du catalogue dit de quoi parlent les avis : des études et de l'accompagnement", () => {
    afficher(CATALOGUE);
    const titre = section("avis").querySelector("h2");
    expect(texteDe(titre).replace(/\s+/g, " ").trim()).toBe("Avis sur les études et l'accompagnement d'Evangeline");
    // Sous un titre « Nos avis clients », au milieu des formations, ils se
    // lisaient comme des avis sur les formations.
    expect(texteDe(section("avis"))).not.toContain("Nos avis clients");
    expect(texteDe(titre)).not.toMatch(/formation/i);
    // Le relevé, lui, garde le titre de la cliente.
    expect(PAGE_CATALOGUE.avis.titre).toBe("Nos avis clients");
    // Et la phrase qui dit d'où viennent les avis est toujours là.
    expect(texteDe(section("avis"))).toContain("avis laissés à Evangeline sur ComeUp");
  });

  it("contre-épreuve : même preuve sur le catalogue, carte par carte", () => {
    const tarif = TARIFS_FORMATIONS.pop as { centimes: number };
    const dAvant = tarif.centimes;
    tarif.centimes = 91300;
    try {
      afficher(CATALOGUE);
      expect(texteDe(document.querySelector("#formation-pop .for-prix"))).toBe("913 € TTC");
      expect(texteDe(document.querySelector("#formation-societes .for-prix"))).toBe(prixAttendu("societes"));
    } finally {
      tarif.centimes = dAvant;
    }
  });

  // ── Le programme ──────────────────────────────────────────────────────────

  for (const [page, contenu, nombre] of [
    [SOCIETES, PAGE_SOCIETES.programme, NOMBRE_DE_MODULES.societes],
    [MICRO, PAGE_MICRO.programme, NOMBRE_DE_MODULES.micro],
  ] as [Page, { titre: string; corps: string[]; modules: string[] }, number][]) {
    it(`${page.nom} : tableau VIDE — le titre, les phrases et le nombre de modules, sans liste ni promesse`, () => {
      // Le relevé ne porte aucun intitulé : c'est l'état que ce test décrit.
      expect(contenu.modules).toEqual([]);
      afficher(page);

      const programme = section("programme");
      expect(within(programme).getByRole("heading", { level: 2 })).toHaveTextContent(contenu.titre);
      for (const phrase of contenu.corps) expect(texteDe(programme)).toContain(phrase);
      expect(texteDe(programme.querySelector(".for-programme-nombre b"))).toBe(String(nombre));
      expect(contenu.titre).toContain(String(nombre));

      expect(programme.querySelector(".for-modules")).toBeNull();
      expect(programme.querySelector("ol, ul")).toBeNull();
      expect(texteDe(programme)).not.toMatch(A_VENIR);
    });

    it(`${page.nom} : tableau REMPLI — la liste des modules s'affiche, dans l'ordre`, () => {
      const intitules = ["Module d'essai, premier", "Module d'essai, deuxième", "Module d'essai, troisième"];
      // Le tableau du contenu lui-même, rempli le temps du test : c'est lui
      // que l'administration remplira.
      contenu.modules.push(...intitules);
      try {
        afficher(page);
        const programme = section("programme");
        const lignes = Array.from(programme.querySelectorAll("ol.for-modules > li"));
        expect(lignes.map((ligne) => texteDe(ligne.lastElementChild))).toEqual(intitules);
        // Numérotées, le numéro masqué aux lecteurs d'écran (la liste
        // ordonnée le dit déjà).
        expect(lignes.map((ligne) => ligne.querySelector("[aria-hidden='true']")?.textContent)).toEqual(["01", "02", "03"]);
        // Le titre, les phrases et le nombre annoncé restent.
        expect(within(programme).getByRole("heading", { level: 2 })).toHaveTextContent(contenu.titre);
        expect(texteDe(programme.querySelector(".for-programme-nombre b"))).toBe(String(nombre));
        for (const phrase of contenu.corps) expect(texteDe(programme)).toContain(phrase);
      } finally {
        contenu.modules.length = 0;
      }
      expect(contenu.modules).toEqual([]);
    });
  }

  it("la Méthode P.O.P n'a ni programme module par module ni coaching, mais sa méthode en trois lettres", () => {
    afficher(POP);

    expect(document.getElementById("programme")).toBeNull();
    expect(document.getElementById("coaching")).toBeNull();
    expect(document.getElementById("formes-juridiques")).toBeNull();
    const lettres = Array.from(section("methode").querySelectorAll("article"));
    expect(lettres.map((lettre) => texteDe(lettre.querySelector("h3")))).toEqual(["Planifiez", "Organisez", "Produisez"]);
    expect(lettres.map((lettre) => texteDe(lettre.querySelector(".for-lettre-signe")))).toEqual(["P", "O", "P"]);
    // Six objectifs, numérotés, dans une liste ordonnée.
    expect(section("objectifs").querySelectorAll("ol.for-objectifs > li")).toHaveLength(PAGE_POP.objectifs.liste.length);
  });

  it("les blocs propres à une formation sont à leur place, dans l'ordre demandé", () => {
    afficher(SOCIETES);

    const ordre = Array.from(screen.getByRole("main").querySelectorAll("section[id]")).map((s) => s.id);
    expect(ordre).toEqual([
      "pourquoi",
      "pour-qui",
      "objectifs",
      "programme",
      "inclus",
      "coaching",
      "formes-juridiques",
      "modalites",
      "atouts",
      "financement",
      "presentiel",
      "questions",
      "autrement",
      "rejoindre",
    ]);
    // Huit objectifs numérotés ; quatre cartes pour les formes juridiques
    // (SASU et SAS partagent la dernière) ; quatre profils.
    expect(section("objectifs").querySelectorAll("ol.for-objectifs > li")).toHaveLength(8);
    expect(Array.from(section("formes-juridiques").querySelectorAll(".for-forme-sigle")).map(texteDe)).toEqual(["EI", "EURL", "SARL", "SASU / SAS"]);
    expect(section("pour-qui").querySelectorAll("article")).toHaveLength(4);
    // Le coaching : le grand chiffre vient des durées, pas d'une écriture.
    expect(texteDe(section("coaching").querySelector(".for-coaching-heures b"))).toBe("2 h");
    // La phrase retenue pour les formes juridiques est celle du tunnel.
    expect(texteDe(section("formes-juridiques"))).toContain("tableau comparatif");
    expect(texte()).not.toContain("tableau CMA");
  });

  // ── Les contradictions du relevé ──────────────────────────────────────────

  it("la pastille « 9 modules » contredite n'est pas sur la page « sociétés » ; celle de la micro, conforme, y est", () => {
    const { unmount } = afficher(SOCIETES);
    expect(PAGE_SOCIETES.ouvertureEnImage.pastilleContredite.texteDeLaCapture).toBe("9 modules");
    expect(texte()).not.toContain("9 modules");
    expect(texte()).toContain("10 modules");
    unmount();

    // Contre-épreuve : le même mot, là où il est juste, est bien vu.
    afficher(MICRO);
    expect(texteDe(document.querySelector(".for-ouverture"))).toContain("9 modules");
  });

  it("l'ancienneté s'écrit « plus de 15 ans », et « accès à vie » reste tel que la cliente l'écrit", () => {
    const { unmount } = afficher(CATALOGUE);
    expect(texte()).toContain("Depuis plus de 15 ans");
    expect(texte()).toContain(ATOUTS_DES_FORMATIONS.acces.titre);
    unmount();

    afficher(POP);
    expect(texte()).toContain("(plus de 15 ans d'expérience)");
    expect(PAGE_POP.pourQui.promesse).toContain("(15 ans d'expérience)");
    expect(texte()).toContain("Accès à vie");
  });

  it("l'assistant IA n'est attribué qu'aux formations dont le contenu l'annonce", () => {
    const question = "Comment fonctionne l'assistant IA ?";
    // Le relevé pose la question pour « chaque formation ».
    expect(QUESTIONS_DES_FORMATIONS.liste.find((q) => q.q === question)?.r).toContain("Chaque formation inclut");

    for (const page of [CATALOGUE, SOCIETES]) {
      const { unmount } = afficher(page);
      expect(texteDe(section("questions")), page.nom).not.toContain(question);
      unmount();
    }
    // La page « sociétés » parle de modules IA, jamais d'un assistant.
    const societes = afficher(SOCIETES);
    expect(texte()).not.toMatch(/(assistant|agent) IA/i);
    expect(texte()).toContain("Modules IA intégrés");
    societes.unmount();

    for (const page of [MICRO, POP]) {
      const { unmount } = afficher(page);
      const questions = section("questions");
      expect(texteDe(questions), page.nom).toContain(question);
      expect(texteDe(questions), page.nom).toContain("Cette formation inclut un accès à un assistant IA");
      // Et le contenu de la page l'annonce bien ailleurs.
      expect(texteDe(document.querySelector(".for-ouverture")), page.nom).toMatch(/Agent IA/);
      unmount();
    }
  });

  it("« (organisation et productivité) » décrit la Méthode P.O.P : la micro-entreprise ne le dit pas de son assistant", () => {
    const PARENTHESE = "(organisation et productivité)";
    // Le relevé le dit de « chaque formation ».
    expect(
      QUESTIONS_DES_FORMATIONS.liste.find((q) => q.q === "Comment fonctionne l'assistant IA ?")?.r,
    ).toContain(PARENTHESE);

    const micro = afficher(MICRO);
    expect(texteDe(section("questions"))).toContain(
      "un assistant IA spécialisé, formé sur la méthode EVKHA. Laissez-le vous guider",
    );
    expect(texte()).not.toContain(PARENTHESE);
    micro.unmount();

    // Sur la page de la P.O.P, c'est juste : elle la garde.
    afficher(POP);
    expect(texteDe(section("questions"))).toContain(`formé sur la méthode EVKHA ${PARENTHESE}.`);
  });

  it("les mentions d'outillage de la micro sont retirées, le sens reste", () => {
    afficher(MICRO);

    const inclus = texteDe(section("inclus"));
    expect(inclus).toContain("Vidéos courtes, slides pédagogiques");
    expect(inclus).toContain("traçabilité complète, suivi formateur");
    // Le relevé, lui, garde le texte d'origine pour le jour où il est tranché.
    expect(phrases(PAGE_MICRO.inclus).join(" ")).toMatch(/Canva/);
    expect(phrases(PAGE_MICRO.inclus).join(" ")).toMatch(/Systeme\.io/);
    expect(phrases(PAGE_MICRO.inclus).join(" ")).toMatch(/Qualiopi/);
  });

  // ── Les sources du lot ────────────────────────────────────────────────────

  it("Formations.tsx n'écrit aucun montant", () => {
    const code = sansCommentaires(source("Formations.tsx"));
    // Règle 1 : un fichier vide ou introuvable ne « passe » pas.
    expect(code.length).toBeGreaterThan(5000);
    expect(code.match(new RegExp(MONTANT_ECRIT.source, "gi")) ?? []).toEqual([]);
    // Les prix s'y lisent par la fonction de la constante de tarifs.
    expect(code).toMatch(/prixAffiche\(/);
  });

  for (const fichier of ["Formations.tsx", "Formations.css"]) {
    it(`${fichier} ne pointe vers aucune adresse du CDN de l'ancien site`, () => {
      // Commentaires COMPRIS : une adresse citée reviendrait au prochain
      // copier-coller.
      const brut = source(fichier);
      expect(brut.length, fichier).toBeGreaterThan(5000);
      expect(brut.match(new RegExp(CDN.source, "gi")) ?? [], fichier).toEqual([]);
    });
  }

  it("Formations.css ne lit aucun plancher calme et n'écrit que des classes du lot ou du socle", () => {
    const css = source("Formations.css").replace(/\/\*[\s\S]*?\*\//g, "");
    expect(css.length).toBeGreaterThan(5000);
    expect(css).not.toMatch(/--calme-/);
    const classes = Array.from(css.matchAll(/\.([a-z][\w-]*)(?=[\s,:.{>+~)])/g)).map((m) => m[1]);
    expect(classes.length).toBeGreaterThan(100);
    const etrangeres = classes.filter((classe) => !/^(for|acc)-/.test(classe));
    expect([...new Set(etrangeres)]).toEqual([]);
  });

  it("contre-épreuve : les détecteurs voient ce qu'ils cherchent, et rien d'autre", () => {
    for (const faute of ["dès 89 €", "1490€", "1 490 € TTC", "850 euros"]) {
      expect(faute, faute).toMatch(MONTANT_ECRIT);
    }
    for (const juste of ["18 heures en ligne", "2 séances d'1 heure", "le signe €", "10 modules", "100 % en ligne"]) {
      expect(juste, juste).not.toMatch(MONTANT_ECRIT);
    }

    // Le relevé garde les adresses du CDN (inventaire) : le détecteur les voit.
    expect(IMAGES_FORMATIONS_A_RAPATRIER.length).toBeGreaterThan(40);
    for (const image of IMAGES_FORMATIONS_A_RAPATRIER) expect(image.adresse).toMatch(CDN);
    expect("/accueil/formations.webp").not.toMatch(CDN);
    expect("https://www.evkha.fr/paiement-formationsociete").not.toMatch(CDN);

    for (const faute of ["1490 € TTC", "Je découvre →", "→ suite", "ensuite ↓"]) {
      expect(faute, faute).toMatch(ESPACE_FAUTIVE);
    }
    for (const juste of [`1490${INSECABLE}€ TTC`, `Je découvre${INSECABLE}→`, "Voir les packs→", "100 % en ligne"]) {
      expect(juste, juste).not.toMatch(ESPACE_FAUTIVE);
    }

    for (const faute of ["Attestation Qualiopi", "Vidéos courtes (Canva)", "traçabilité complète Systeme.io", "QUALIOPI"]) {
      expect(faute, faute).toMatch(NON_AFFICHE);
    }
    expect("Attestation de fin de formation").not.toMatch(NON_AFFICHE);

    for (const faute of ["Bientôt disponible", "Programme à venir", "prochainement"]) {
      expect(faute, faute).toMatch(A_VENIR);
    }
    expect("Un parcours progressif, du diagnostic de votre projet à votre stratégie commerciale.").not.toMatch(A_VENIR);

    expect("Pôle Emploi").toMatch(ANCIEN_NOM);
    expect("France Travail").not.toMatch(ANCIEN_NOM);

    // Le libellé relevé d'un bouton perd sa flèche, et seulement elle.
    expect(sansFleche(`Je découvre la formation${INSECABLE}→`)).toBe("Je découvre la formation");
    expect(sansFleche("JE REJOINS LA FORMATION !")).toBe("JE REJOINS LA FORMATION !");
    // Le collecteur de phrases descend dans les listes et les objets.
    expect(phrases({ a: "un", b: ["deux", { c: "trois", d: 4, e: null }] })).toEqual(["un", "deux", "trois"]);
  });
});

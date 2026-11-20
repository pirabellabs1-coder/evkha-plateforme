/** Les quatre pages de l'Académie : le catalogue des formations et les trois
 * pages de formation (`Formations.tsx`).
 *
 * Elles reprennent `evkha.fr/formation` et les trois pages `/achat-formation*`
 * dans la plateforme. Depuis le 19/11/2026, leurs CHIFFRES — prix, durée,
 * heures de coaching, nombre de modules, programme — viennent du serveur
 * (`GET /api/public/formations/`) ; le texte de vente reste celui du relevé.
 * Ce que ce fichier verrouille :
 *
 * 1. chaque page se rend, avec UN `h1`, des titres sans saut, son propre titre
 *    d'onglet et sa propre description ;
 * 2. les prix affichés sont ceux de l'API — servis ici à des montants que
 *    personne n'écrirait de mémoire (1 237 €, 913 €…) ; tant que l'API n'a pas
 *    répondu, ni montant ni durée ; une panne se dit UNE fois dans la région
 *    d'alerte et se rappelle dans la section ; une réponse 200 mal formée est
 *    une panne ;
 * 3. une formation absente de la réponse (pas encore mise en ligne) : la page
 *    garde tout son texte de vente, dit « Indisponible pour le moment »,
 *    neutralise ses boutons d'inscription et n'affiche ni chiffre ni liste ;
 * 4. le bouton d'inscription est un vrai bouton, qui porte le slug de SA
 *    formation et ouvre le paiement de la plateforme (ce qu'il envoie et ce
 *    qu'il fait des refus est éprouvé dans `l-achat-d-une-formation`) ; plus
 *    aucun courriel d'inscription ; un `lien_d_achat` rendu par le serveur
 *    n'est PAS suivi ; le catalogue mène aux pages de la plateforme ;
 * 5. le programme affiche les modules et les leçons que l'API rend, et le
 *    NOMBRE de modules est celui de cette liste ; sans module : le titre et
 *    les phrases, sans chiffre, sans liste, sans promesse ;
 * 6. les phrases de la cliente qui citent un chiffre le citent d'après le
 *    serveur, et s'en passent proprement quand il manque ;
 * 7. une page de formation en ligne pose ses données structurées (`Course`),
 *    et seulement elle ;
 * 8. aucun formulaire ; ce qui ne doit pas s'afficher ne s'affiche pas ; les
 *    contradictions du relevé sont rendues comme décidé ; RIEN de ce que le
 *    relevé dit de chaque page n'a disparu ;
 * 9. aucun montant, aucune durée de formation, aucun nombre de modules en dur
 *    dans les sources — la classe du défaut (règle 4), pas les valeurs
 *    d'aujourd'hui —, et aucune adresse du CDN de l'ancien site.
 *
 * Contre-épreuves (règle 6) : chaque détecteur voit ce qu'il cherche et laisse
 * passer ce qui est juste ; la composition des phrases est éprouvée à part.
 *
 * JOUÉ le 20/11/2026 (104 tests). Éprouvé par UNE mutation ce jour-là : le
 * bouton d'inscription qui suit de nouveau le lien du serveur (trois tests
 * rougissent). Restent à éprouver par mutations de la page : un prix écrit en
 * dur dans une carte ; `formationEnLigne` qui rend la première formation
 * venue ; le bouton laissé actif hors ligne ; `nombre_de_modules` affiché à
 * la place de `modules.length` ; l'alerte muette en cas de panne.
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

import { composer, composerTout, type Chiffres } from "../public/chiffres";
import * as contenu from "../public/contenuFormations";
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
  ORGANISME_DE_FORMATION,
  PAGE_CATALOGUE,
  PAGE_MICRO,
  PAGE_POP,
  PAGE_SOCIETES,
  PRESENTIEL,
  PROMESSE_POP_AFFICHEE,
  QUESTIONS_DES_FORMATIONS,
  ROUTES_FORMATIONS,
  SEANCES_DE_COACHING,
  SLUGS_DES_FORMATIONS,
  chiffresDeLaFormation,
  dureeDeLecon,
  formationEnLigne,
  natureDeLecon,
  questionsAffichees,
  sansFleche,
  type CarteDeFormation,
  type CleDeFormation,
} from "../public/contenuFormations";
import type { FormationPublique } from "../public/donnees";
import {
  FormationMicro,
  FormationPop,
  FormationSocietes,
  Formations,
} from "../public/Formations";
import { server } from "./server";

// ── L'API, telle que le test la sert ────────────────────────────────────────

// L'adresse que `donnees.ts` construit réellement : l'origine de jsdom. Une
// requête sans gestionnaire partirait sur le réseau et échouerait — le cas
// « panne » passerait alors pour une mauvaise raison.
const FORMATIONS_API = `${window.location.origin}/api/public/formations/`;

/** Les trois slugs du serveur, écrits ICI en toutes lettres : la page les
 *  déduit de ses adresses, le test ne les lui demande pas. */
const SLUGS: Record<CleDeFormation, string> = {
  societes: "creer-son-entreprise",
  micro: "creer-sa-micro-entreprise",
  pop: "methode-pop",
};

function lecon(titre: string, nature: string, duree_minutes: number, en_apercu_libre = false) {
  return { rang: 0, titre, nature, duree_minutes, en_apercu_libre };
}

function unModule(titre: string, description: string, lecons: ReturnType<typeof lecon>[] = []) {
  return {
    rang: 0,
    titre,
    description,
    lecons: lecons.map((ligne, k) => ({ ...ligne, rang: k + 1 })),
  };
}

/** Une formation telle que le serveur la rend. Le titre, le sous-titre et
 *  l'accroche portent un mot que la page n'écrit nulle part : le texte de
 *  vente reste celui du relevé, et s'ils s'affichaient, ils viendraient
 *  d'ici. */
function formation(cle: CleDeFormation, surcharges: Partial<FormationPublique>): FormationPublique {
  const modules = (surcharges.modules ?? []).map((m, k) => ({ ...m, rang: k + 1 }));
  return {
    slug: SLUGS[cle],
    titre: `TITRE-DU-SERVEUR ${cle}`,
    sous_titre: "SOUS-TITRE-DU-SERVEUR",
    accroche: "ACCROCHE-DU-SERVEUR",
    prix_cents: 100,
    devise: "EUR",
    duree_heures: 0,
    heures_de_coaching: 0,
    lien_d_achat: "",
    image: "",
    nombre_de_modules: modules.length,
    ...surcharges,
    modules,
  };
}

/** Le programme servi pour la formation « sociétés » : trois modules, de
 *  toutes les formes — avec et sans description, avec et sans leçon, les
 *  quatre natures, une nature inconnue, une leçon sans durée. */
const MODULES_SOCIETES = [
  unModule("Diagnostic du projet d'essai", "Poser les bases, sans jargon.", [
    lecon("Bienvenue dans le parcours", "video", 12, true),
    lecon("Le guide à lire", "texte", 0),
    lecon("Modèle de statuts", "document", 75),
    lecon("Valider ses acquis", "quiz", 120),
    lecon("Un format que la page ne connaît pas", "podcast", 5),
  ]),
  unModule("Choisir son statut d'essai", ""),
  unModule("Financer le lancement d'essai", "Aides, prêts et apports.", [
    lecon("Les aides à la création", "video", 9),
  ]),
];

const MODULES_MICRO = [
  unModule("Comprendre le régime d'essai", ""),
  unModule("Valider son idée d'essai", ""),
  unModule("S'immatriculer d'essai", ""),
  unModule("Trouver ses clients d'essai", ""),
];

/** Des montants et des durées que personne n'écrirait de mémoire. Le compteur
 *  `nombre_de_modules` de la première est FAUX exprès (99) : le nombre affiché
 *  doit être celui de la liste rendue. */
const SOCIETES_API = formation("societes", {
  prix_cents: 123700,
  duree_heures: 23,
  heures_de_coaching: 2,
  nombre_de_modules: 99,
  modules: MODULES_SOCIETES,
});
const LIEN_DU_SERVEUR = "https://paiement.exemple.test/inscription-micro";
const MICRO_API = formation("micro", {
  prix_cents: 131900,
  duree_heures: 19,
  heures_de_coaching: 3,
  lien_d_achat: LIEN_DU_SERVEUR,
  modules: MODULES_MICRO,
});
const POP_API = formation("pop", { prix_cents: 91300, duree_heures: 11 });
const TOUTES = [SOCIETES_API, MICRO_API, POP_API];

/** Les prix attendus, écrits à la main : le test ne demande pas son résultat à
 *  la fonction du site (`donnees.euros`) qu'il éprouve. */
const PRIX: Record<CleDeFormation, string> = {
  societes: "1 237 € TTC",
  micro: "1 319 € TTC",
  pop: "913 € TTC",
};

/** Les chiffres que les PHRASES doivent citer, écrits à la main. La micro a
 *  trois heures de coaching : le découpage relevé (2 séances d'1 heure) ne lui
 *  correspond pas, et ne doit pas être cité. */
const EN_LIGNE: Record<CleDeFormation, Chiffres> = {
  societes: { heures: 23, coaching: 2, modules: 3, seances: 2, heuresParSeance: 1 },
  micro: { heures: 19, coaching: 3, modules: 4, seances: null, heuresParSeance: null },
  pop: { heures: 11, coaching: null, modules: null, seances: null, heuresParSeance: null },
};
const SANS: Chiffres = { heures: null, coaching: null, modules: null, seances: null, heuresParSeance: null };
const AUCUN_CHIFFRE: Record<CleDeFormation, Chiffres> = { societes: SANS, micro: SANS, pop: SANS };

type Reponse = () => Response | Promise<Response>;

function servir(reponse: Reponse) {
  server.use(http.get(FORMATIONS_API, reponse));
}

const lesFormations = (liste: object[]): Reponse => () => HttpResponse.json({ formations: liste });
const panne: Reponse = () => new HttpResponse("panne", { status: 500 });
const muet: Reponse = async () => {
  await delay("infinite");
  return new HttpResponse(null);
};

/** Les réponses 200 qui ne portent pas la liste attendue. */
const MAL_FORMEES: [string, Reponse][] = [
  ["un objet sans la clé attendue", () => HttpResponse.json({})],
  ["une clé mal nommée", () => HttpResponse.json({ formation: [] })],
  ["une liste qui n'en est pas une", () => HttpResponse.json({ formations: "aucune" })],
  [
    "la page d'un relais",
    () => new HttpResponse("<!doctype html><title>EVKHA</title>", { headers: { "Content-Type": "text/html" } }),
  ],
];

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

/** L'insécable telle qu'une SOURCE l'écrit : en échappement. Le motif est
 *  construit par le code de la barre oblique inverse, pour que ce fichier-ci
 *  n'écrive jamais la suite de signes qu'un outil d'édition transforme. */
const INSECABLE_ECHAPPEE = new RegExp(`${String.fromCharCode(92, 92)}u00a0`, "g");

/** Le code d'un fichier, tel que les balayages le lisent : sans ses
 *  commentaires, et l'échappement de l'insécable rendu en espace — sinon son
 *  dernier chiffre, collé à la lettre qui suit, se lirait comme un nombre. */
function code(fichier: string): string {
  return sansCommentaires(source(fichier)).replace(INSECABLE_ECHAPPEE, " ");
}

/** Un montant en euros écrit dans une source, ou affiché. */
const MONTANT_ECRIT = /\d[\d\s.,]*(?:€|euros?\b)/i;
const MONTANT = /\d\s*€/;

/** Une durée en heures : « 18h », « 18 h », « 18 HEURES », « 7 heures ». */
const DUREE_ECRITE = /\d+\s?(?:h|heures?)\b/gi;

/** Les deux tournures du relevé qui portent un « h » sans être la durée d'une
 *  formation : la disponibilité (« accessibles 24h/24 ») et le délai de
 *  réponse du formateur (« sous 24-48h »). Retirées AVANT le balayage, et
 *  comptées : une exclusion qu'on ne compte pas devient un trou. */
const HORAIRES = /24h\/24|24-48h/g;

/** Un nombre de modules : « 9 modules », « 10 modules ». */
const MODULES_ECRITS = /\d+\s?modules?\b/gi;

/** Les prix d'avant, par leurs seuls chiffres — en euros comme en centimes :
 *  un prix recopié sans son symbole serait encore un prix. */
const ANCIENS_PRIX = /(?<!\d)(?:149000|85000|1490|850)(?!\d)/g;

/** Une marque ou un passage facultatif resté tel quel à l'écran. */
const MARQUE_NUE = /[{}]|\[\[|\]\]/;

/** Une adresse du CDN de l'ancien site (systeme.io). */
const CDN = /cloudfront\.net|d1yei2z3i6k35z/i;

/** Une espace ORDINAIRE avant « € », ou collée à une flèche. */
const ESPACE_FAUTIVE = / €| [→←↗↓]|[→←↗↓] /;

const ANCIEN_NOM = new RegExp(`p[oô]le[\\s${INSECABLE}-]+emploi`, "i");

/** Ce qu'aucune des quatre pages ne doit afficher. */
const NON_AFFICHE = /qualiopi|canva|systeme\.io/i;

/** Une promesse de contenu à venir : la section du programme n'en fait pas. */
const A_VENIR = /bient[oô]t|prochainement|à venir|disponible/i;

const ATTENTE = "Tarif en cours de chargement";
const PANNE = "Tarif momentanément indisponible";
const ABSENT = "Indisponible pour le moment";

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

/** Un courriel d'INSCRIPTION : un `mailto:` dont l'objet parle de s'inscrire.
 *  C'était la destination des boutons jusqu'au 20/11/2026 ; plus aucun lien
 *  des pages ne doit en être un. Les courriels de contact, de financement et
 *  de présentiel, eux, restent. */
const COURRIEL_D_INSCRIPTION = /^mailto:[^?]*\?.*inscri/i;

function courrielsDInscription(): string[] {
  return Array.from(screen.getByRole("main").querySelectorAll("a"))
    .map((lien) => lien.getAttribute("href") ?? "")
    .filter((adresse) => COURRIEL_D_INSCRIPTION.test(adresse));
}

/** Les boutons d'inscription ACTIFS : de vrais boutons. */
function boutonsQuiPaient(): HTMLButtonElement[] {
  return Array.from(document.querySelectorAll<HTMLButtonElement>("button.for-bouton-achat"));
}

const BOUTONS_D_ACHAT: Record<CleDeFormation, string> = {
  societes: PAGE_SOCIETES.appelFinal.bouton.libelle,
  micro: PAGE_MICRO.appelFinal.bouton.libelle,
  pop: PAGE_POP.appelFinal.bouton.libelle,
};

function afficher(page: Page) {
  window.history.pushState({}, "", page.route);
  return render(<page.Composant />);
}

/** La réponse du serveur est arrivée et la page l'a lue : plus aucun
 *  emplacement de prix ne dit qu'il attend. Vaut pour une panne aussi. */
async function reponseLue() {
  await waitFor(() => expect(texte()).not.toContain(ATTENTE));
}

async function afficherLue(page: Page) {
  const rendu = afficher(page);
  await reponseLue();
  return rendu;
}

/** Les liens de la page, hors barre, menu et pied (le socle). */
function liensDuContenu(): HTMLAnchorElement[] {
  return Array.from(screen.getByRole("main").querySelectorAll("a"));
}

/** Les emplacements de prix de la page : montants et phrases qui en tiennent
 *  lieu, dans l'ordre du DOM. */
function emplacementsDePrix(): string[] {
  return Array.from(
    document.querySelectorAll(".for-prix, .for-fin-prix, .for-prix-absent, .for-fin-sans-prix"),
  ).map(texteDe);
}

function boutonsDInscription(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>(".for-bouton-achat"));
}

function alerte(): HTMLElement {
  return screen.getByRole("alert");
}

function donneesStructurees(): HTMLScriptElement[] {
  // `:not([data-bloc])` : le bloc que la PAGE pose pour ce qu'elle vend. Le fil
  // d'Ariane et les questions fréquentes, posés par le socle sur toute page
  // (`site.BLOCS_DU_SOCLE`), sont jugés dans `le-referencement-dit-vrai`.
  return Array.from(
    document.head.querySelectorAll<HTMLScriptElement>('script[type="application/ld+json"]:not([data-bloc])'),
  );
}

/** Le texte du contenu principal, sans la phrase de l'argumentaire
 *  « sociétés » qui cite le coût d'un expert-comptable : c'est un exemple, pas
 *  le prix d'une offre, et le seul montant que ces pages écrivent d'elles-mêmes. */
const EXEMPLE_CHIFFRE = espaces(PAGE_SOCIETES.pourQui.argumentaire.constat.points[4]);

function contenuSansLExemple(): string {
  return texteDe(screen.getByRole("main")).split(EXEMPLE_CHIFFRE).join("");
}

/** Les durées en heures que la page affiche, hors des deux tournures qui n'en
 *  sont pas. Sur le catalogue, on ne regarde que les cartes : les avis clients
 *  parlent de délais de livraison. */
function dureesAffichees(page: Page): string[] {
  const zone = page.cle === null ? section("nos-formations") : screen.getByRole("main");
  return texteDe(zone).replace(HORAIRES, "").match(DUREE_ECRITE) ?? [];
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

/** Le relevé de chaque page de formation, phrases à marque comprises. */
const RELEVE: Record<CleDeFormation, unknown[]> = {
  societes: [
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
  ],
  micro: [
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
  ],
  pop: [
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
  ],
};

/** Les phrases qu'une page doit afficher, étant donné les chiffres de chaque
 *  formation. Une phrase que son chiffre manquant a vidée n'est pas attendue ;
 *  toutes les autres le sont — c'est « la page reste entière ». */
function attendues(page: Page, chiffres: Record<CleDeFormation, Chiffres>): string[] {
  const dites = (valeur: unknown, cle: CleDeFormation) => phrases(composerTout(valeur, chiffres[cle]));
  const liste =
    page.cle === null
      ? [
          ...phrases([
            PAGE_CATALOGUE.ouverture,
            PAGE_CATALOGUE.pourquoi.titre,
            PAGE_CATALOGUE.pourquoi.paragraphes,
            PAGE_CATALOGUE.formations.titre,
            PAGE_CATALOGUE.pourQui,
            // Le TITRE de la section d'avis est retouché à l'affichage (voir
            // le test qui lui est propre) : seul le surtitre s'affiche tel quel.
            PAGE_CATALOGUE.avis.surtitre,
            questionsAffichees("catalogue"),
          ]),
          ...PAGE_CATALOGUE.formations.cartes.flatMap((carte) => dites(phrasesDeLaCarte(carte), carte.cle)),
          // La carte de la micro-entreprise n'a pas de repères relevés : la
          // page lui donne ceux de l'ouverture de sa page d'achat.
          ...dites(PAGE_MICRO.ouvertureEnImage.pastilles, "micro"),
        ]
      : [...dites(RELEVE[page.cle], page.cle), ...phrases(questionsAffichees(page.cle))];
  return [...liste, ...COMMUN].filter((phrase) => phrase !== "");
}

describe("les pages des formations", () => {
  // `useTitreDePage` écrit la description dans la balise du gabarit HTML :
  // jsdom n'en a pas, on la pose. Par défaut, les trois formations sont en
  // ligne ; un test qui veut un autre état le sert lui-même.
  let meta: HTMLMetaElement;
  beforeEach(() => {
    meta = document.createElement("meta");
    meta.name = "description";
    meta.content = "gabarit";
    document.head.appendChild(meta);
    servir(lesFormations(TOUTES));
  });
  afterEach(() => {
    cleanup();
    meta.remove();
    window.history.pushState({}, "", "/");
  });

  // ── Chaque page se rend et se laisse conduire ─────────────────────────────

  for (const page of PAGES) {
    it(`${page.nom} : un seul h1, des titres sans saut, un lien d'évitement`, async () => {
      await afficherLue(page);

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
      // Les blocs à révéler le sont — y compris ceux que l'arrivée de la
      // réponse a montés : sans observateur (jsdom), tout s'affiche.
      const blocs = Array.from(document.querySelectorAll("[data-reveal]"));
      expect(blocs.length).toBeGreaterThan(8);
      for (const bloc of blocs) expect(bloc).toHaveClass("est-revele");
    });

    it(`${page.nom} : aucun formulaire, aucun champ, aucune image de l'ancien site`, async () => {
      await afficherLue(page);

      expect(document.querySelector("form")).toBeNull();
      expect(document.querySelector("input, textarea, select")).toBeNull();
      for (const image of Array.from(document.querySelectorAll("img"))) {
        expect(image.hasAttribute("alt"), image.getAttribute("src") ?? "").toBe(true);
        expect(image.getAttribute("src") ?? "", "image hors de la plateforme").toMatch(/^\/(?!\/)/);
        expect(Number(image.getAttribute("width"))).toBeGreaterThan(0);
        expect(Number(image.getAttribute("height"))).toBeGreaterThan(0);
      }
      // Aucun lien du contenu ne mène au CDN ni à une page de l'ancien site :
      // vers `evkha.fr`, il n'y a plus que des courriels.
      for (const lien of liensDuContenu()) {
        const adresse = lien.getAttribute("href") ?? "";
        expect(adresse, texteDe(lien)).not.toMatch(CDN);
        if (/evkha\.fr/.test(adresse)) expect(adresse, texteDe(lien)).toMatch(/^mailto:/);
      }
    });

    it(`${page.nom} : rien de ce que le relevé dit n'a disparu, et le texte du serveur ne le remplace pas`, async () => {
      await afficherLue(page);

      const phrasesAttendues = attendues(page, EN_LIGNE);
      // Règle 1 : une collecte vide ferait passer la boucle sans rien vérifier.
      expect(phrasesAttendues.length).toBeGreaterThan(55);
      const affiche = texte();
      for (const phrase of phrasesAttendues) {
        expect(affiche, `${page.nom} ne dit plus : « ${phrase} »`).toContain(espaces(phrase));
      }
      // Le texte de vente reste celui du relevé : le titre, le sous-titre et
      // l'accroche que le serveur rend ne s'affichent pas.
      expect(affiche).not.toMatch(/DU-SERVEUR/);
      // Aucune marque n'est restée telle quelle à l'écran.
      expect(affiche).not.toMatch(MARQUE_NUE);
    });

    it(`${page.nom} : la typographie du texte affiché, et France Travail sous son nom`, async () => {
      await afficherLue(page);

      // Sur le texte BRUT : une insécable est juste, une espace ordinaire non.
      expect(document.body.textContent ?? "").not.toMatch(ESPACE_FAUTIVE);
      expect(texte()).not.toMatch(ANCIEN_NOM);
      expect(texteDe(section("financement"))).toContain("France Travail");
      expect(texte()).not.toMatch(/\b(?:null|undefined|NaN)\b/);
    });

    it(`${page.nom} : financement, présentiel et passerelle, sans formulaire ni prix`, async () => {
      await afficherLue(page);

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

    it(`${page.nom} : ce qui n'est pas confirmé ne s'affiche pas`, async () => {
      await afficherLue(page);

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
      // Aucune page ne tutoie dans son onglet, et aucune n'y laisse une marque.
      expect(`${document.title} ${meta.content}`, page.nom).not.toMatch(/(?<!\p{L})(ton|ta|tes|toi)(?!\p{L})/iu);
      expect(`${document.title} ${meta.content}`, page.nom).not.toMatch(MARQUE_NUE);
      titres.add(document.title);
      descriptions.add(meta.content);
      unmount();
      expect(meta.content, page.nom).toBe("gabarit");
    }
    expect(titres.size).toBe(PAGES.length);
    expect(descriptions.size).toBe(PAGES.length);
  });

  // ── Les prix viennent du serveur ──────────────────────────────────────────

  it("chaque page retrouve SA formation par le slug que le serveur lui connaît", () => {
    // Écrits ici en toutes lettres : la page les lit dans ses adresses.
    expect(SLUGS_DES_FORMATIONS).toEqual(SLUGS);
    for (const cle of ["societes", "micro", "pop"] as CleDeFormation[]) {
      expect(ROUTES_FORMATIONS[cle], cle).toBe(`/formations/${SLUGS[cle]}`);
      expect(formationEnLigne(TOUTES, cle)?.slug, cle).toBe(SLUGS[cle]);
    }
    // Une formation d'un autre slug n'est celle d'aucune page.
    const etrangere = { ...SOCIETES_API, slug: "une-autre-formation" };
    expect(formationEnLigne([etrangere], "societes")).toBeNull();
    expect(formationEnLigne([], "pop")).toBeNull();
  });

  it("le catalogue : chaque carte porte SON nom, le prix de SA formation à l'API, et mène à SA page", async () => {
    await afficherLue(CATALOGUE);

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
      expect(texteDe(c.querySelector(".for-prix")), carte.cle).toBe(PRIX[carte.cle]);
      // UN lien dans la carte : la page de la formation, sur la plateforme.
      const liens = within(c).getAllByRole("link");
      expect(liens, carte.cle).toHaveLength(1);
      expect(liens[0], carte.cle).toHaveAttribute("href", route);
      // La flèche du libellé relevé n'est pas doublée par celle du bouton.
      expect(texteDe(liens[0]).match(/→/g), carte.cle).toHaveLength(1);
      // Des repères de durée ou de format sur chacune.
      expect(c.querySelectorAll(".for-pastilles li").length, carte.cle).toBeGreaterThanOrEqual(2);
    });
    // Les prix du site d'avant ne sont nulle part.
    expect(texte()).not.toMatch(/1[\s]?490|850 €/);
    expect(alerte()).toBeEmptyDOMElement();
    expect(texte()).not.toContain("momentanément indisponible");

    // Le catalogue n'inscrit personne lui-même : aucun bouton d'inscription.
    const adresses = liensDuContenu().map((lien) => lien.getAttribute("href"));
    expect(courrielsDInscription()).toEqual([]);
    expect(adresses).not.toContain(LIEN_DU_SERVEUR);
    expect(document.querySelector(".for-bouton-achat")).toBeNull();
    // Le bouton de l'ouverture mène aux cartes, qui existent.
    expect(document.querySelector(".for-ouverture a")).toHaveAttribute("href", "#nos-formations");
    expect(document.getElementById("nos-formations")).not.toBeNull();
    // L'appel final : un rendez-vous et un courriel.
    const fin = section("contact");
    expect(within(fin).getByRole("link", { name: /Réserver un appel/ })).toHaveAttribute("href", "https://calendly.com/contact-evkha");
    expect(within(fin).getByRole("link", { name: /Écrire à EVKHA/ }).getAttribute("href")).toMatch(/^mailto:contact@evkha\.fr\?subject=/);
  });

  it("le catalogue : chaque carte dit SON état — une formation en ligne à côté d'une qui ne l'est pas", async () => {
    // La micro-entreprise n'est pas dans la réponse : pas encore publiée.
    servir(lesFormations([SOCIETES_API, POP_API]));
    await afficherLue(CATALOGUE);

    expect(texteDe(document.querySelector("#formation-societes .for-prix"))).toBe(PRIX.societes);
    expect(texteDe(document.querySelector("#formation-pop .for-prix"))).toBe(PRIX.pop);
    const micro = section("formation-micro");
    expect(micro.querySelector(".for-prix")).toBeNull();
    expect(texteDe(micro.querySelector(".for-prix-absent"))).toBe(ABSENT);
    expect(texteDe(micro)).not.toMatch(MONTANT);
    // La carte reste entière, et son bouton mène toujours à sa page : la page
    // se lit même quand la formation n'est pas en ligne.
    expect(within(micro).getByRole("heading", { level: 3 })).toHaveTextContent(CARTE_MICRO.titre);
    expect(within(micro).getByRole("link")).toHaveAttribute("href", "/formations/creer-sa-micro-entreprise");
    expect(micro.querySelector(".acc-btn-inactif")).toBeNull();
    for (const acquis of CARTE_MICRO.acquis) expect(texteDe(micro)).toContain(acquis);
    // Ses repères chiffrés ne s'affichent pas ; les autres, si.
    expect(texteDe(micro)).not.toContain("19h");
    expect(micro.querySelectorAll(".for-pastilles li").length).toBeGreaterThanOrEqual(2);
    // Ce n'est pas une panne.
    expect(alerte()).toBeEmptyDOMElement();
    expect(document.querySelector(".acc-panne")).toBeNull();
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

    it(`${page.nom} : son prix est celui de l'API, à ses trois emplacements`, async () => {
      await afficherLue(page);

      // L'ouverture, « en pratique », l'appel final.
      expect(emplacementsDePrix()).toEqual([PRIX[cle], PRIX[cle], PRIX[cle]]);
      expect(document.querySelector(".for-ouverture .for-prix")).not.toBeNull();
      expect(section("modalites").querySelector(".for-prix")).not.toBeNull();
      expect(section("rejoindre").querySelector(".for-fin-prix")).not.toBeNull();
      // Ni le prix d'une autre formation, ni un prix du site d'avant.
      for (const [autre, prix] of Object.entries(PRIX)) {
        if (autre !== cle) expect(texte(), autre).not.toContain(prix.replace(" TTC", ""));
      }
      expect(contenuSansLExemple()).not.toMatch(/1[\s]?490|850 €/);
      // Ni panne, ni rappel, ni bouton neutralisé.
      expect(alerte()).toBeEmptyDOMElement();
      expect(document.querySelector(".acc-panne")).toBeNull();
      expect(document.querySelector(".acc-btn-inactif")).toBeNull();
    });

    it(`${page.nom} : tant que l'API n'a pas répondu, ni montant ni durée, et pas d'inscription`, async () => {
      servir(muet);
      afficher(page);

      expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
      // L'attente se dit à chaque emplacement de prix — et ce n'est pas une panne.
      expect(emplacementsDePrix()).toHaveLength(3);
      for (const emplacement of emplacementsDePrix()) expect(emplacement).toContain(ATTENTE);
      expect(document.querySelector(".for-prix, .for-fin-prix")).toBeNull();
      expect(contenuSansLExemple()).not.toMatch(MONTANT);
      expect(dureesAffichees(page)).toEqual([]);
      // `match`, pas `toMatch` : un motif global garde sa position d'un appel
      // à l'autre, et un `test` répété finirait par ne plus rien voir.
      expect(texteDe(screen.getByRole("main")).match(MODULES_ECRITS)).toBeNull();
      expect(alerte()).toBeEmptyDOMElement();
      expect(document.querySelector(".acc-panne")).toBeNull();
      // On ne s'inscrit pas à une formation dont le prix n'est pas affiché.
      expect(boutonsDInscription()).toHaveLength(3);
      for (const bouton of boutonsDInscription()) {
        expect(bouton.tagName).toBe("SPAN");
        expect(bouton).toHaveAttribute("aria-disabled", "true");
      }
      expect(donneesStructurees()).toHaveLength(0);
      expect(document.querySelector(".for-modules")).toBeNull();
      expect(texte()).not.toMatch(MARQUE_NUE);
    });

    it(`${page.nom} : si l'API échoue, la page le dit une fois, le rappelle, et n'affiche aucun prix`, async () => {
      servir(panne);
      afficher(page);

      await waitFor(() => expect(alerte()).toHaveTextContent(/tarifs sont momentanément indisponibles/));
      await reponseLue();
      expect(screen.getAllByRole("alert")).toHaveLength(1);
      expect(alerte().querySelector("a")).toHaveAttribute("href", "mailto:contact@evkha.fr");
      // Le rappel, dans la section du tarif.
      expect(section("modalites").querySelector(".acc-panne")).toHaveTextContent(/momentanément indisponibles/);
      expect(document.querySelectorAll(".acc-panne")).toHaveLength(1);
      expect(emplacementsDePrix()).toEqual([PANNE, PANNE, PANNE]);
      expect(contenuSansLExemple()).not.toMatch(MONTANT);
      expect(dureesAffichees(page)).toEqual([]);
      // Une panne n'est pas « pas en ligne ».
      expect(texte()).not.toContain(ABSENT);
      for (const bouton of boutonsDInscription()) expect(bouton).toHaveAttribute("aria-disabled", "true");
      expect(document.querySelector("a.for-bouton-achat")).toBeNull();
      expect(boutonsQuiPaient()).toEqual([]);
      expect(donneesStructurees()).toHaveLength(0);
      // Le texte de vente, lui, est là.
      for (const phrase of attendues(page, AUCUN_CHIFFRE)) {
        expect(texte(), phrase).toContain(espaces(phrase));
      }
    });

    it(`${page.nom} : formation hors ligne — « Indisponible », inscription neutralisée, page entière`, async () => {
      // Les deux AUTRES formations sont en ligne ; celle de la page, non.
      servir(lesFormations(TOUTES.filter((f) => f.slug !== SLUGS[cle])));
      await afficherLue(page);

      expect(emplacementsDePrix()).toEqual([ABSENT, ABSENT, ABSENT]);
      expect(document.querySelector(".for-prix, .for-fin-prix")).toBeNull();
      // Pas le prix d'une AUTRE formation, pas de montant du tout.
      expect(contenuSansLExemple()).not.toMatch(MONTANT);
      expect(dureesAffichees(page)).toEqual([]);

      // Les trois boutons d'inscription : la pièce neutralisée du socle, qui
      // n'est pas un lien, ne prend pas le focus et se dit indisponible.
      const boutons = boutonsDInscription();
      expect(boutons).toHaveLength(3);
      for (const bouton of boutons) {
        expect(bouton.tagName).toBe("SPAN");
        expect(bouton).toHaveClass("acc-btn-inactif");
        expect(bouton).toHaveAttribute("aria-disabled", "true");
        expect(bouton).not.toHaveAttribute("href");
        expect(bouton).not.toHaveAttribute("tabindex");
        expect(texteDe(bouton)).toContain(BOUTONS_D_ACHAT[cle]);
      }
      const adresses = liensDuContenu().map((lien) => lien.getAttribute("href"));
      expect(courrielsDInscription()).toEqual([]);
      expect(boutonsQuiPaient()).toEqual([]);
      expect(adresses).not.toContain(LIEN_DU_SERVEUR);

      // Ce n'est pas une panne : ni alerte, ni rappel.
      expect(alerte()).toBeEmptyDOMElement();
      expect(document.querySelector(".acc-panne")).toBeNull();
      expect(texte()).not.toContain("momentanément");

      // La page reste entière : tout son texte de vente, sans les chiffres.
      const phrasesAttendues = attendues(page, AUCUN_CHIFFRE);
      expect(phrasesAttendues.length).toBeGreaterThan(50);
      for (const phrase of phrasesAttendues) {
        expect(texte(), `${page.nom} ne dit plus : « ${phrase} »`).toContain(espaces(phrase));
      }
      expect(texte()).not.toMatch(MARQUE_NUE);
      expect(document.body.textContent ?? "").not.toMatch(ESPACE_FAUTIVE);
      // Pas de liste de modules, pas de données structurées.
      expect(document.querySelector(".for-modules")).toBeNull();
      expect(document.querySelector(".for-programme-nombre")).toBeNull();
      expect(donneesStructurees()).toHaveLength(0);
    });

    for (const [nom, reponse] of MAL_FORMEES) {
      it(`${page.nom} : une réponse 200 mal formée (${nom}) est une panne dite, pas une formation hors ligne`, async () => {
        servir(reponse);
        afficher(page);

        await waitFor(() => expect(alerte()).toHaveTextContent(/momentanément indisponibles/));
        await reponseLue();
        expect(emplacementsDePrix()).toEqual([PANNE, PANNE, PANNE]);
        expect(texte()).not.toContain(ABSENT);
        expect(contenuSansLExemple()).not.toMatch(MONTANT);
      });
    }

    it(`${page.nom} : la carte de l'attestation porte la formulation du tunnel P.O.P`, async () => {
      await afficherLue(page);

      const inclus = section("inclus");
      const titres = Array.from(inclus.querySelectorAll("h3")).map(texteDe);
      expect(titres).toHaveLength(6);
      expect(titres).toEqual(composerTout(INCLUS_AFFICHE[cle], EN_LIGNE[cle]).map((carte) => carte.titre));
      expect(titres[5]).toBe(ATTESTATION_AFFICHEE);
      expect(ATTESTATION_AFFICHEE).toBe("Attestation de fin de formation");
    });
  }

  it("le catalogue : attente, puis panne — aucun montant, et la panne dite une fois", async () => {
    servir(muet);
    const attente = afficher(CATALOGUE);
    expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
    const cartes = () => Array.from(document.querySelectorAll<HTMLElement>("article.for-carte"));
    // Les trois cartes sont là, chacune dit qu'elle attend.
    expect(cartes()).toHaveLength(3);
    for (const carte of cartes()) {
      expect(texteDe(carte.querySelector(".for-prix-absent"))).toContain(ATTENTE);
      expect(texteDe(carte)).not.toMatch(MONTANT);
    }
    expect(dureesAffichees(CATALOGUE)).toEqual([]);
    expect(alerte()).toBeEmptyDOMElement();
    attente.unmount();

    servir(panne);
    afficher(CATALOGUE);
    await waitFor(() => expect(alerte()).toHaveTextContent(/tarifs sont momentanément indisponibles/));
    await reponseLue();
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(section("nos-formations").querySelector(".acc-panne")).toHaveTextContent(/momentanément indisponibles/);
    expect(cartes()).toHaveLength(3);
    for (const carte of cartes()) {
      expect(texteDe(carte.querySelector(".for-prix-absent"))).toBe(PANNE);
      expect(texteDe(carte)).not.toMatch(MONTANT);
      // La page de la formation reste à un clic.
      expect(within(carte).getAllByRole("link")).toHaveLength(1);
    }
    expect(texte()).not.toContain(ABSENT);
  });

  for (const [nom, reponse] of MAL_FORMEES) {
    it(`le catalogue : une réponse 200 mal formée (${nom}) est une panne dite`, async () => {
      servir(reponse);
      afficher(CATALOGUE);

      await waitFor(() => expect(alerte()).toHaveTextContent(/momentanément indisponibles/));
      await reponseLue();
      expect(texte()).not.toContain(ABSENT);
      expect(document.querySelectorAll("article.for-carte .for-prix")).toHaveLength(0);
    });
  }

  for (const [nom, surcharge] of [
    ["un prix à zéro", { prix_cents: 0 }],
    ["un prix qui n'est pas un nombre", { prix_cents: "123700" as unknown as number }],
    ["une devise que la page ne sait pas écrire", { devise: "USD" }],
  ] as [string, Partial<FormationPublique>][]) {
    it(`une formation rendue avec ${nom} n'est pas vendue : la page n'invente pas son prix`, async () => {
      servir(lesFormations([{ ...SOCIETES_API, ...surcharge }, MICRO_API, POP_API]));
      await afficherLue(SOCIETES);

      expect(emplacementsDePrix()).toEqual([ABSENT, ABSENT, ABSENT]);
      expect(contenuSansLExemple()).not.toMatch(MONTANT);
      for (const bouton of boutonsDInscription()) expect(bouton).toHaveAttribute("aria-disabled", "true");
      expect(donneesStructurees()).toHaveLength(0);
    });
  }

  it("les prix s'affichent comme sur le reste du site : milliers séparés, insécables aux bons endroits", async () => {
    await afficherLue(CATALOGUE);
    const bruts = Array.from(document.querySelectorAll("article.for-carte .for-prix")).map((e) => e.textContent ?? "");
    expect(bruts).toHaveLength(3);
    for (const brut of bruts) {
      // Une insécable avant « € », jamais une espace ordinaire ; et un
      // montant de quatre chiffres ne s'écrit pas d'un bloc.
      expect(brut).toMatch(new RegExp(`[${INSECABLE}${FINE_INSECABLE}]€`));
      expect(brut).not.toMatch(/\d{4}/);
      expect(brut).not.toMatch(/\d \d/);
    }
    // Le séparateur de milliers est une espace insécable — fine ou non, selon
    // la version des données de langue.
    const milliers = new RegExp(`\\d[${INSECABLE}${FINE_INSECABLE}]\\d{3}`);
    expect(bruts.filter((brut) => milliers.test(brut)).length).toBeGreaterThanOrEqual(2);
  });

  // ── Où mène le bouton d'inscription ───────────────────────────────────────

  it("un lien d'achat rendu par le serveur n'est pas suivi : trois vrais boutons, qui ouvrent le paiement", async () => {
    // « micro » est servie AVEC un `lien_d_achat` https bien formé.
    expect(MICRO_API.lien_d_achat).toBe(LIEN_DU_SERVEUR);
    await afficherLue(MICRO);

    const boutons = boutonsQuiPaient();
    expect(boutons).toHaveLength(3);
    for (const bouton of boutons) {
      expect(bouton).toHaveAttribute("type", "button");
      expect(bouton).not.toHaveAttribute("href");
      expect(bouton).not.toBeDisabled();
      expect(bouton).not.toHaveAttribute("aria-disabled");
      expect(bouton).toHaveAttribute("data-formation", SLUGS.micro);
      expect(texteDe(bouton)).toContain(BOUTONS_D_ACHAT.micro);
    }
    // Plus aucun lien d'inscription : ni la pièce d'avant, ni un courriel.
    expect(document.querySelector("a.for-bouton-achat")).toBeNull();
    expect(courrielsDInscription()).toEqual([]);
    // Un dans l'ouverture, un dans « en pratique », un dans l'appel final.
    expect(document.querySelector(".for-ouverture button.for-bouton-achat")).not.toBeNull();
    expect(section("modalites").querySelector("button.for-bouton-achat")).not.toBeNull();
    expect(section("rejoindre").querySelector("button.for-bouton-achat")).not.toBeNull();
    // Au repos, aucun refus : la seule région d'alerte est celle des tarifs.
    expect(document.querySelector(".for-refus")).toBeNull();
    // L'adresse du serveur n'est nulle part dans la page — ni dans un lien,
    // ni dans les données structurées.
    expect(document.documentElement.innerHTML).not.toContain(LIEN_DU_SERVEUR);
  });

  it("chaque formation porte le slug de SA formation, et aucun courriel d'inscription", async () => {
    for (const page of FICHES) {
      const cle = page.cle as CleDeFormation;
      const { unmount } = await afficherLue(page);
      const boutons = boutonsQuiPaient();
      expect(boutons, cle).toHaveLength(3);
      for (const bouton of boutons) {
        expect(bouton, cle).toHaveAttribute("data-formation", SLUGS[cle]);
        expect(texteDe(bouton), cle).toContain(BOUTONS_D_ACHAT[cle]);
      }
      expect(courrielsDInscription(), cle).toEqual([]);
      expect(liensDuContenu().map((lien) => lien.getAttribute("href"))).not.toContain(LIEN_DU_SERVEUR);
      unmount();
    }
  });

  it("quoi que le serveur rende comme lien d'achat, le bouton n'en dépend pas", async () => {
    const rendus = ["javascript:alert(1)", "http://paiement.exemple.test/x", "https://paiement.exemple.test/autre", "   "];
    for (const rendu of rendus) {
      servir(lesFormations([{ ...MICRO_API, lien_d_achat: rendu }]));
      const { unmount } = await afficherLue(MICRO);
      expect(boutonsQuiPaient(), rendu).toHaveLength(3);
      expect(document.querySelector("a.for-bouton-achat"), rendu).toBeNull();
      if (rendu.trim() !== "") expect(document.documentElement.innerHTML, rendu).not.toContain(rendu);
      unmount();
    }
    // La page n'a qu'UN endroit qui ouvre un paiement, et trois boutons qui
    // passent par lui.
    const page = source("Formations.tsx");
    expect(sansCommentaires(page).match(/payerUneFormation\(/g) ?? []).toHaveLength(1);
    expect(page.match(/<BoutonDInscription\s/g) ?? []).toHaveLength(3);
    expect(sansCommentaires(page)).not.toMatch(/lien_d_achat/);
    expect(sansCommentaires(page)).not.toMatch(/inscri[^\n]*mailto:|mailto:[^\n]*inscri/i);
  });

  it("le contenu n'écrit plus aucun courriel d'inscription", () => {
    // Les adresses d'inscription par courriel ont quitté `LIENS_FORMATIONS`,
    // et les deux exports qui les servaient n'existent plus.
    for (const [cle, adresse] of Object.entries(LIENS_FORMATIONS)) {
      expect(String(adresse), cle).not.toMatch(/^mailto:/);
    }
    expect(Object.keys(contenu)).not.toContain("lienDInscription");
    expect(Object.keys(contenu)).not.toContain("PAIEMENT_DES_FORMATIONS");
    expect(sansCommentaires(source("contenuFormations.ts"))).not.toMatch(/mailto:/);
    for (const page of [PAGE_SOCIETES, PAGE_MICRO, PAGE_POP]) {
      expect(page.appelFinal.bouton.lien).toBeNull();
    }
  });

  it("contre-épreuve : le détecteur de courriel d'inscription voit ceux d'avant, et eux seuls", () => {
    // Deux des trois adresses que les boutons portaient jusqu'au 20/11/2026.
    for (const avant of [
      "mailto:contact@evkha.fr?subject=Je%20souhaite%20m%27inscrire%20%C3%A0%20la%20formation%20M%C3%A9thode%20P.O.P",
      "mailto:contact@evkha.fr?subject=Je%20souhaite%20m%27inscrire%20%C3%A0%20la%20formation%20%C2%AB%20Cr%C3%A9er%20sa%20micro-entreprise%20de%20A%20%C3%A0%20Z%20%C2%BB",
    ]) {
      expect(avant).toMatch(COURRIEL_D_INSCRIPTION);
    }
    for (const juste of [
      "mailto:contact@evkha.fr",
      `mailto:contact@evkha.fr?subject=${encodeURIComponent(ARTICULATION.presentiel.objetDuCourriel)}`,
      `mailto:contact@evkha.fr?subject=${encodeURIComponent(ARTICULATION.financement.objetDuCourriel)}`,
      "/formations/methode-pop",
    ]) {
      expect(juste).not.toMatch(COURRIEL_D_INSCRIPTION);
    }
  });

  // ── Le programme ──────────────────────────────────────────────────────────

  it("le programme : les modules et les leçons que l'API rend, dans son ordre, et leur NOMBRE", async () => {
    await afficherLue(SOCIETES);

    const programme = section("programme");
    // Le nombre affiché est celui de la liste rendue (3), pas le compteur que
    // le serveur annonce à côté (servi faux exprès : 99).
    expect(texteDe(programme.querySelector(".for-programme-nombre b"))).toBe("3");
    expect(texteDe(programme.querySelector(".for-programme-nombre span"))).toBe("modules");
    expect(texteDe(programme)).not.toContain("99");
    expect(texteDe(within(programme).getByRole("heading", { level: 2 })).replace(/\s+/g, " ").trim()).toBe(
      "Les 3 modules du parcours",
    );
    for (const phrase of PAGE_SOCIETES.programme.corps) expect(texteDe(programme)).toContain(phrase);

    const modules = Array.from(programme.querySelectorAll("ol.for-modules > li"));
    expect(modules).toHaveLength(3);
    expect(modules.map((m) => texteDe(m.querySelector("h3")))).toEqual(MODULES_SOCIETES.map((m) => m.titre));
    // Numérotés, le numéro masqué aux lecteurs d'écran (la liste ordonnée le
    // dit déjà).
    expect(modules.map((m) => m.querySelector(".for-module-numero")?.textContent)).toEqual(["01", "02", "03"]);
    for (const m of modules) expect(m.querySelector(".for-module-numero")).toHaveAttribute("aria-hidden", "true");

    // La description, quand il y en a une — et pas de paragraphe vide sinon.
    expect(texteDe(modules[0].querySelector(".for-module-description"))).toBe("Poser les bases, sans jargon.");
    expect(modules[1].querySelector(".for-module-description")).toBeNull();
    // Un module sans leçon n'a pas de liste de leçons.
    expect(modules[1].querySelector(".for-lecons")).toBeNull();

    // Les leçons du premier module : intitulé, nature en français, durée,
    // et l'étiquette d'aperçu libre sur celle qui l'est — et elle seule.
    const lecons = Array.from(modules[0].querySelectorAll("ol.for-lecons > li"));
    expect(lecons.map((l) => texteDe(l.querySelector(".for-lecon-titre")))).toEqual(
      MODULES_SOCIETES[0].lecons.map((l) => l.titre),
    );
    const reperes = lecons.map((l) => Array.from(l.querySelectorAll(".for-lecon-repere")).map(texteDe));
    expect(reperes).toEqual([
      ["Vidéo", "12 min"],
      // Une leçon sans durée s'affiche sans durée, pas avec une durée nulle.
      ["Texte"],
      ["Document", "1 h 15"],
      ["Quiz", "2 h"],
      // Une nature inconnue : son code n'est pas affiché à sa place.
      ["5 min"],
    ]);
    expect(texteDe(programme)).not.toContain("podcast");
    expect(lecons.map((l) => texteDe(l.querySelector(".for-lecon-apercu")))).toEqual(["Aperçu libre", "", "", "", ""]);
    // « Aperçu libre » est une étiquette : le programme ne porte aucun lien.
    expect(programme.querySelector("a")).toBeNull();
    expect(texteDe(modules[2])).toContain("Les aides à la création");
    expect(texteDe(programme)).not.toMatch(A_VENIR);
  });

  for (const [page, releve] of [
    [SOCIETES, PAGE_SOCIETES.programme],
    [MICRO, PAGE_MICRO.programme],
  ] as [Page, { titre: string; corps: string[] }][]) {
    const cle = page.cle as CleDeFormation;

    it(`${page.nom} : en ligne SANS module — le titre et les phrases, sans chiffre, sans liste ni promesse`, async () => {
      const sansModule = TOUTES.map((f) => (f.slug === SLUGS[cle] ? { ...f, modules: [], nombre_de_modules: 7 } : f));
      servir(lesFormations(sansModule));
      await afficherLue(page);

      // La formation est bien en ligne : c'est le programme seul qui est vide.
      expect(emplacementsDePrix()[0]).toBe(PRIX[cle]);
      const programme = section("programme");
      expect(texteDe(within(programme).getByRole("heading", { level: 2 })).replace(/\s+/g, " ").trim()).toBe(
        "Les modules du parcours",
      );
      for (const phrase of releve.corps) expect(texteDe(programme)).toContain(phrase);
      // Ni le grand chiffre, ni le compteur du serveur, ni une liste.
      expect(programme.querySelector(".for-programme-nombre")).toBeNull();
      expect(texteDe(programme)).not.toMatch(/\d/);
      expect(programme.querySelector("ol, ul")).toBeNull();
      expect(texteDe(programme)).not.toMatch(A_VENIR);
      // Et les pastilles de la page n'annoncent pas de nombre de modules.
      expect(texteDe(screen.getByRole("main")).match(MODULES_ECRITS)).toBeNull();
    });
  }

  it("un seul module : « 1 module » au singulier, et le titre ne compte pas", async () => {
    servir(lesFormations([{ ...MICRO_API, modules: [MODULES_MICRO[0]] }]));
    await afficherLue(MICRO);

    const programme = section("programme");
    expect(texteDe(programme.querySelector(".for-programme-nombre b"))).toBe("1");
    expect(texteDe(programme.querySelector(".for-programme-nombre span"))).toBe("module");
    expect(programme.querySelectorAll("ol.for-modules > li")).toHaveLength(1);
    expect(texte()).not.toContain("1 modules");
    expect(texteDe(within(programme).getByRole("heading", { level: 2 })).replace(/\s+/g, " ").trim()).toBe(
      "Les modules du parcours",
    );
  });

  it("la Méthode P.O.P n'a ni programme ni coaching tant que le serveur n'en rend pas, mais sa méthode en trois lettres", async () => {
    await afficherLue(POP);

    expect(document.getElementById("programme")).toBeNull();
    expect(document.getElementById("coaching")).toBeNull();
    expect(document.getElementById("formes-juridiques")).toBeNull();
    const lettres = Array.from(section("methode").querySelectorAll("article"));
    expect(lettres.map((lettre) => texteDe(lettre.querySelector("h3")))).toEqual(["Planifiez", "Organisez", "Produisez"]);
    expect(lettres.map((lettre) => texteDe(lettre.querySelector(".for-lettre-signe")))).toEqual(["P", "O", "P"]);
    // Six objectifs, numérotés, dans une liste ordonnée.
    expect(section("objectifs").querySelectorAll("ol.for-objectifs > li")).toHaveLength(PAGE_POP.objectifs.liste.length);
  });

  it("la Méthode P.O.P reçoit sa section de programme le jour où le serveur lui rend des modules", async () => {
    const modules = [unModule("Planifier d'essai", "", [lecon("Sa semaine type", "video", 8, true)]), unModule("Produire d'essai", "")];
    servir(lesFormations([{ ...POP_API, modules: modules.map((m, k) => ({ ...m, rang: k + 1 })) }]));
    await afficherLue(POP);

    const programme = section("programme");
    expect(texteDe(programme.querySelector(".for-programme-nombre b"))).toBe("2");
    expect(texteDe(within(programme).getByRole("heading", { level: 2 })).replace(/\s+/g, " ").trim()).toBe(
      "Les 2 modules de la méthode",
    );
    expect(Array.from(programme.querySelectorAll("ol.for-modules > li h3")).map(texteDe)).toEqual([
      "Planifier d'essai",
      "Produire d'essai",
    ]);
    expect(texteDe(programme.querySelector(".for-lecon-apercu"))).toBe("Aperçu libre");
    // À sa place : après les objectifs, avant « ce qui est inclus ».
    const ordre = Array.from(screen.getByRole("main").querySelectorAll("section[id]")).map((s) => s.id);
    expect(ordre.slice(ordre.indexOf("objectifs"), ordre.indexOf("inclus") + 1)).toEqual(["objectifs", "programme", "inclus"]);
  });

  it("les blocs propres à une formation sont à leur place, dans l'ordre demandé", async () => {
    await afficherLue(SOCIETES);

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
    // La phrase retenue pour les formes juridiques est celle du tunnel.
    expect(texteDe(section("formes-juridiques"))).toContain("tableau comparatif");
    expect(texte()).not.toContain("tableau CMA");
  });

  // ── Les chiffres dans les phrases de la cliente ───────────────────────────

  it("« sociétés » : les phrases citent la durée et le coaching du serveur, plus ceux du relevé", async () => {
    await afficherLue(SOCIETES);

    const page = texte();
    // Écrites ici à la main, telles que la page doit les dire.
    for (const phrase of [
      "23h de formation",
      "+ 2h accompagnement",
      "Format : 100 % en ligne 23 HEURES À VOTRE RYTHME",
      "2 HEURES D'accompagnements individuels pour travailler sur VOTRE projet.",
      "23h de formation digitale",
      "2h d'accompagnement premium",
      "2H D'accompagnement individuel premium en visio. Pour transformer",
      // Deux heures : le découpage relevé leur correspond, il est cité.
      "2H D'accompagnement individuel en visio, réparties en 2 séances d'1 heure.",
    ]) {
      expect(page, phrase).toContain(phrase);
    }
    // Le grand chiffre du coaching vient du serveur.
    expect(texteDe(section("coaching").querySelector(".for-coaching-heures b"))).toBe("2 h");
    // Les dix-huit heures du relevé ne sont plus nulle part.
    expect(page).not.toMatch(/18\s?(?:h|heures)/i);
  });

  it("« micro » : trois heures de coaching au serveur — le découpage relevé en deux séances n'est plus cité", async () => {
    await afficherLue(MICRO);

    const page = texte();
    for (const phrase of [
      "19h de formation",
      "+ 3h en visio",
      "4 modules",
      "19h de formation digitale",
      "3h d'accompagnement visio",
      "Bénéficier d'un accompagnement humain individuel de 3h",
      "Coaching individuel : analyse projet, prévisionnel, plan d'action.",
    ]) {
      expect(page, phrase).toContain(phrase);
    }
    expect(texteDe(section("coaching").querySelector(".for-coaching-heures b"))).toBe("3 h");
    // « 3H …, réparties en 2 séances d'1 heure » se contredirait.
    expect(page).not.toMatch(/séances d'1/);
    expect(SEANCES_DE_COACHING).toEqual({ nombre: 2, heuresParSeance: 1 });
    // La pastille du nombre de modules est celle du serveur, dans l'ouverture.
    expect(texteDe(document.querySelector(".for-ouverture"))).toContain("4 modules");
    expect(page).not.toMatch(/18\s?(?:h|heures)|9 modules/i);
  });

  it("« P.O.P » : onze heures au serveur, dites partout où le relevé en disait sept", async () => {
    await afficherLue(POP);

    const page = texte();
    for (const phrase of [
      "11h de formation",
      "Durée : 11h 00",
      "La formation P.O.P en 11 heures est une expérience immersive",
      "11h de formation digitale",
    ]) {
      expect(page, phrase).toContain(phrase);
    }
    expect(page).not.toMatch(/\b7\s?(?:h|heures)/i);
  });

  it("sans chiffre du serveur, les phrases s'en passent proprement : ni trou, ni « h » orphelin", async () => {
    servir(lesFormations([]));
    const societes = await afficherLue(SOCIETES);
    let page = texte();
    for (const phrase of [
      "Format : 100 % en ligne À VOTRE RYTHME",
      "Accompagnements individuels pour travailler sur VOTRE projet.",
      "Accompagnement individuel premium en visio. Pour transformer",
    ]) {
      expect(page, phrase).toContain(phrase);
    }
    // Les cartes « inclus » gardent leur titre, majuscule rétablie.
    expect(Array.from(section("inclus").querySelectorAll("h3")).map(texteDe).slice(0, 2)).toEqual([
      "Formation digitale",
      "Accompagnement premium",
    ]);
    // L'encart du coaching s'ouvre sans grand chiffre.
    expect(section("coaching").querySelector(".for-coaching-heures")).toBeNull();
    expect(page).not.toMatch(/séances d'/);
    // La pastille qui n'avait que son chiffre à dire n'est plus là ; celle qui
    // dit autre chose reste.
    const pastilles = Array.from(document.querySelectorAll(".for-ouverture .for-pastilles:not(.for-sigles) li")).map(texteDe);
    expect(pastilles).toEqual(["Outils financiers avancés"]);
    for (const pastille of Array.from(document.querySelectorAll(".for-pastilles li"))) {
      expect(texteDe(pastille).trim()).not.toBe("");
    }
    societes.unmount();

    const micro = await afficherLue(MICRO);
    page = texte();
    expect(page).toContain("Coaching individuel : analyse projet, prévisionnel, plan d'action.");
    expect(
      Array.from(section("pourquoi").querySelectorAll(".for-versus-promesse li")).map((li) => texteDe(li).replace(/^✓/, "")),
    ).toContain("Bénéficier d'un accompagnement humain individuel");
    micro.unmount();

    await afficherLue(POP);
    expect(texte()).toContain("La formation P.O.P est une expérience immersive et concrète");
    expect(texte()).not.toContain("Durée :");
  });

  // ── Les données structurées ───────────────────────────────────────────────

  for (const page of FICHES) {
    const cle = page.cle as CleDeFormation;

    it(`${page.nom} : en ligne, UN bloc Course — nom et description de la page, prix et devise du serveur`, async () => {
      const { unmount } = await afficherLue(page);

      await waitFor(() => expect(donneesStructurees()).toHaveLength(1));
      const donnees = JSON.parse(donneesStructurees()[0].textContent ?? "") as Record<string, unknown>;
      expect(donnees["@context"]).toBe("https://schema.org");
      expect(donnees["@type"]).toBe("Course");
      // Le nom est le titre que la page affiche ; la description, celle de
      // son onglet — tirées du texte de la page, pas de celui du serveur.
      expect(espaces(String(donnees.name))).toBe(
        texteDe(screen.getByRole("heading", { level: 1 })).replace(/\s+/g, " ").trim(),
      );
      expect(donnees.description).toBe(meta.content);
      expect(String(donnees.description).length).toBeGreaterThan(40);
      expect(JSON.stringify(donnees)).not.toMatch(/DU-SERVEUR/);
      // Une marque non remplie se cherche dans les TEXTES du bloc, pas dans sa
      // sérialisation : `JSON.stringify` écrit toujours des accolades, et
      // l'assertion d'origine ne pouvait donc jamais passer.
      expect(phrases(donnees).length).toBeGreaterThanOrEqual(6);
      expect(phrases(donnees).join(" ")).not.toMatch(MARQUE_NUE);
      // Contre-épreuve : une marque restée dans un texte, même enfoui, est vue.
      expect(phrases({ ...donnees, offers: { nom: "{heures}h de formation" } }).join(" ")).toMatch(MARQUE_NUE);
      expect(donnees.provider).toEqual({ "@type": "Organization", name: "EVKHA", url: window.location.origin });
      const offre = donnees.offers as Record<string, unknown>;
      expect(offre["@type"]).toBe("Offer");
      // Écrit à la main : le prix servi, en euros.
      expect(offre.price).toBe({ societes: 1237, micro: 1319, pop: 913 }[cle]);
      expect(offre.priceCurrency).toBe("EUR");
      expect(offre.url).toBe(`${window.location.origin}/formations/${SLUGS[cle]}`);

      // Rendu en partant : la page suivante n'hérite pas de l'offre.
      unmount();
      expect(donneesStructurees()).toHaveLength(0);
    });
  }

  it("le catalogue ne pose aucun bloc de données structurées", async () => {
    await afficherLue(CATALOGUE);
    expect(donneesStructurees()).toHaveLength(0);
  });

  // ── Les contradictions du relevé ──────────────────────────────────────────

  it("la pastille « 9 modules » de la capture « sociétés » n'est pas rendue : le nombre affiché est celui du serveur", async () => {
    const { unmount } = await afficherLue(SOCIETES);
    expect(PAGE_SOCIETES.ouvertureEnImage.pastilleContredite.texteDeLaCapture).toBe("9 modules");
    expect(PAGE_SOCIETES.ouvertureEnImage.pastilles.join(" ")).not.toMatch(/modules/);
    expect(texte()).not.toContain("9 modules");
    expect(texte()).not.toContain("10 modules");
    expect(texte()).toContain("Les 3 modules du parcours");
    unmount();

    // Contre-épreuve : sur la micro, la pastille existe et porte le nombre servi.
    await afficherLue(MICRO);
    expect(texteDe(document.querySelector(".for-ouverture"))).toContain("4 modules");
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

  it("les constantes de prix, de durée et de nombre de modules n'existent plus", () => {
    const exportes = Object.keys(contenu);
    // Règle 1 : le module est bien chargé.
    expect(exportes).toContain("PAGE_SOCIETES");
    for (const supprimee of ["TARIFS_FORMATIONS", "DUREES_SOCIETES", "DUREES_MICRO", "DUREES_POP", "NOMBRE_DE_MODULES", "prixAffiche"]) {
      expect(exportes, supprimee).not.toContain(supprimee);
      expect(code("contenuFormations.ts"), supprimee).not.toContain(supprimee);
      expect(code("Formations.tsx"), supprimee).not.toContain(supprimee);
    }
    // Le relevé ne porte plus de tableau de modules : ils viennent du serveur.
    expect(PAGE_SOCIETES.programme).not.toHaveProperty("modules");
    expect(PAGE_MICRO.programme).not.toHaveProperty("modules");
  });

  it("Formations.tsx n'écrit aucun montant, et lit ses prix au serveur", () => {
    const page = code("Formations.tsx");
    // Règle 1 : un fichier vide ou introuvable ne « passe » pas.
    expect(page.length).toBeGreaterThan(5000);
    expect(page.match(new RegExp(MONTANT_ECRIT.source, "gi")) ?? []).toEqual([]);
    expect(page.match(ANCIENS_PRIX) ?? []).toEqual([]);
    expect(page).toMatch(/useChargement\(chargerFormations\)/);
    expect(page).toMatch(/prixDeLaFormation\(/);
  });

  it("contenuFormations.ts n'écrit qu'UN montant : le coût d'expert-comptable cité en exemple", () => {
    const releve = code("contenuFormations.ts");
    expect(releve.length).toBeGreaterThan(5000);
    const montants = releve.split("\n").filter((ligne) => new RegExp(MONTANT_ECRIT.source, "i").test(ligne));
    expect(montants).toHaveLength(1);
    expect(montants[0]).toContain("expert-comptable");
    expect(releve.match(ANCIENS_PRIX) ?? []).toEqual([]);
  });

  for (const fichier of ["Formations.tsx", "contenuFormations.ts"]) {
    it(`${fichier} n'écrit aucune durée de formation ni aucun nombre de modules`, () => {
      const brut = code(fichier);
      expect(brut.length, fichier).toBeGreaterThan(5000);
      // Les deux tournures horaires du relevé, comptées avant d'être retirées.
      expect(brut.match(HORAIRES) ?? [], fichier).toHaveLength(fichier === "contenuFormations.ts" ? 4 : 0);
      expect(brut.replace(HORAIRES, "").match(DUREE_ECRITE) ?? [], fichier).toEqual([]);
      // Un seul nombre de modules écrit : le texte de la capture contredite,
      // gardé pour mémoire dans `pastilleContredite` et jamais affiché.
      expect(brut.match(MODULES_ECRITS) ?? [], fichier).toEqual(fichier === "contenuFormations.ts" ? ["9 modules"] : []);
    });
  }

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

  // ── Contre-épreuves ───────────────────────────────────────────────────────

  it("contre-épreuve : la composition ne retouche que ce qu'elle vise", () => {
    const titre = "[[{heures}h de ]]formation digitale";
    expect(composer(titre, { heures: 23 })).toBe("23h de formation digitale");
    // Le passage qui ouvrait la phrase disparaît : la majuscule est rétablie.
    expect(composer(titre, { heures: null })).toBe("Formation digitale");
    expect(composer("Les [[{modules} ]]modules du parcours", { modules: null })).toBe("Les modules du parcours");
    expect(composer("Les [[{modules} ]]modules du parcours", { modules: 6 })).toBe("Les 6 modules du parcours");
    // Une phrase qui n'avait que son chiffre à dire vaut « rien ».
    expect(composer("[[{heures}h de formation]]", { heures: null })).toBe("");
    // Un passage qui cite deux chiffres tombe dès que l'un manque.
    expect(composer("a[[ {x} et {y}]] b", { x: 1, y: null })).toBe("a b");
    expect(composer("a[[ {x} et {y}]] b", { x: 1, y: 2 })).toBe("a 1 et 2 b");
    // Une phrase sans marque n'est pas touchée.
    expect(composer("Accessibles 24h/24, sans jargon.", { heures: 3 })).toBe("Accessibles 24h/24, sans jargon.");
    // Une marque mal orthographiée ne s'affiche pas telle quelle : elle lève.
    expect(() => composer("{heure}h de formation", { heures: 3 })).toThrow(/heure/);
    // Tout un bloc : les formes sont gardées, la phrase vidée quitte sa liste.
    expect(composerTout(["a", "[[{x}]]", { t: "[[{x} ]]b", n: 4, v: null }], { x: null })).toEqual(["a", { t: "B", n: 4, v: null }]);
  });

  it("contre-épreuve : un chiffre n'entre dans une phrase que s'il est lisible et pluriel", () => {
    const avec = (surcharge: Partial<FormationPublique>) => chiffresDeLaFormation({ ...SOCIETES_API, ...surcharge });
    expect(chiffresDeLaFormation(SOCIETES_API)).toEqual(EN_LIGNE.societes);
    expect(chiffresDeLaFormation(MICRO_API)).toEqual(EN_LIGNE.micro);
    expect(chiffresDeLaFormation(POP_API)).toEqual(EN_LIGNE.pop);
    expect(chiffresDeLaFormation(null)).toEqual(SANS);
    // « 1 HEURES » ne s'écrit pas ; zéro ne s'annonce pas ; une valeur
    // illisible non plus.
    expect(avec({ duree_heures: 1 }).heures).toBeNull();
    expect(avec({ duree_heures: 0 }).heures).toBeNull();
    expect(avec({ duree_heures: "18" as unknown as number }).heures).toBeNull();
    expect(avec({ duree_heures: 12.5 }).heures).toBeNull();
    // Le découpage en séances n'est cité que s'il correspond au total.
    expect(avec({ heures_de_coaching: 2 }).seances).toBe(2);
    expect(avec({ heures_de_coaching: 4 }).seances).toBeNull();
    expect(avec({ heures_de_coaching: 4 }).coaching).toBe(4);
    // Une réponse sans liste de modules vaut « aucun module », pas une erreur.
    expect(avec({ modules: undefined as unknown as [] }).modules).toBeNull();

    expect(espaces(dureeDeLecon(12) ?? "")).toBe("12 min");
    expect(espaces(dureeDeLecon(75) ?? "")).toBe("1 h 15");
    expect(espaces(dureeDeLecon(120) ?? "")).toBe("2 h");
    expect(espaces(dureeDeLecon(65) ?? "")).toBe("1 h 05");
    expect(dureeDeLecon(0)).toBeNull();
    expect(dureeDeLecon("12")).toBeNull();
    // Les insécables y sont, jamais une espace ordinaire.
    expect(dureeDeLecon(75)).not.toContain(" ");

    expect(["video", "texte", "document", "quiz"].map(natureDeLecon)).toEqual(["Vidéo", "Texte", "Document", "Quiz"]);
    for (const inconnue of ["podcast", "", "constructor", "toString", null, 3]) {
      expect(natureDeLecon(inconnue), String(inconnue)).toBeNull();
    }
  });

  it("contre-épreuve : les détecteurs voient ce qu'ils cherchent, et rien d'autre", () => {
    for (const faute of ["dès 89 €", "1490€", "1 490 € TTC", "850 euros"]) {
      expect(faute, faute).toMatch(MONTANT_ECRIT);
    }
    for (const juste of ["18 heures en ligne", "2 séances d'1 heure", "le signe €", "10 modules", "100 % en ligne"]) {
      expect(juste, juste).not.toMatch(MONTANT_ECRIT);
    }

    for (const faute of ["18h de formation", "18 h", "18 HEURES À VOTRE RYTHME", "en 7 heures", "2H D'accompagnement", "séances d'1 heure"]) {
      expect(faute.match(DUREE_ECRITE), faute).not.toBeNull();
    }
    for (const juste of ["[[{heures}h de formation]]", "100 % en ligne", "12 min", "30/60/90 jours", "sur 30 jours", "SASU, SAS"]) {
      expect(juste.match(DUREE_ECRITE), juste).toBeNull();
    }
    // Les deux tournures horaires sont retirées, et elles seules.
    expect("accessibles 24h/24, suivi sous 24-48h".replace(HORAIRES, "").match(DUREE_ECRITE)).toBeNull();
    expect("accessibles 24h sur 24".replace(HORAIRES, "").match(DUREE_ECRITE)).toEqual(["24h"]);

    for (const faute of ["9 modules", "Les 10 modules du parcours", "1 module"]) {
      expect(faute.match(MODULES_ECRITS), faute).not.toBeNull();
    }
    for (const juste of ["[[{modules} modules]]", "Modules IA intégrés", "les modules du parcours"]) {
      expect(juste.match(MODULES_ECRITS), juste).toBeNull();
    }

    expect("centimes: 149000".match(ANCIENS_PRIX)).toEqual(["149000"]);
    expect("const PRIX = 850;".match(ANCIENS_PRIX)).toEqual(["850"]);
    expect("largeur: 1080, 18500".match(ANCIENS_PRIX)).toBeNull();

    // L'échappement de l'insécable, tel qu'une source l'écrit, est bien vu —
    // et son dernier chiffre ne se lit plus comme une durée.
    const echappee = `${String.fromCharCode(92)}u00a0`;
    expect(`\${heures}${echappee}h`.replace(INSECABLE_ECHAPPEE, " ").match(DUREE_ECRITE)).toBeNull();
    expect(`\${heures}${echappee}h`.match(DUREE_ECRITE)).not.toBeNull();
    expect(source("contenuFormations.ts").match(INSECABLE_ECHAPPEE)?.length ?? 0).toBeGreaterThan(3);

    for (const faute of ["{heures}h de formation", "[[18h]]", "reste ]]"]) expect(faute, faute).toMatch(MARQUE_NUE);
    expect("23h de formation (en ligne)").not.toMatch(MARQUE_NUE);

    // Le relevé garde les adresses du CDN (inventaire) : le détecteur les voit.
    expect(IMAGES_FORMATIONS_A_RAPATRIER.length).toBeGreaterThan(40);
    for (const image of IMAGES_FORMATIONS_A_RAPATRIER) expect(image.adresse).toMatch(CDN);
    expect("/accueil/formations.webp").not.toMatch(CDN);
    expect(LIEN_DU_SERVEUR).not.toMatch(CDN);

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

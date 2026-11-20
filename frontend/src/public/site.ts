/** Les crochets et les calculs que les pages publiques refondues partagent.
 *
 * Tout ce qui suit vivait dans `Accueil.tsx`. La page des études s'en sert à
 * son tour : plutôt que de le recopier, les deux pages l'importent d'ici
 * (règle 5). Chaque crochet défait ce qu'il a branché.
 *
 * Pas de composant dans ce fichier — ils sont dans `PiecesSite.tsx`,
 * `EnTeteSite.tsx` et `PiedSite.tsx` — pour que le rechargement à chaud de
 * Vite garde l'état des pages.
 */
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type CSSProperties,
  type MouseEvent,
  type RefObject,
} from "react";

import {
  ACCUEIL,
  adresseAbsolue,
  MARQUE,
  type EntreeDeNavigation,
  type Rubrique,
} from "./contenuSite";
import { filDAriane, questionsFrequentes } from "./referencement";

// ── Chargement d'un catalogue ───────────────────────────────────────────────

/** L'état d'un appel. Trois cas distincts, jamais une liste vide par défaut :
 *  c'est elle qui fait passer une panne pour « rien à vendre ». */
export type Chargement<T> =
  | { etat: "attente" }
  | { etat: "recu"; donnees: T }
  | { etat: "panne" };

/** `charger` doit être une fonction stable (définie hors du composant) :
 *  elle est la dépendance de l'effet. */
export function useChargement<T>(charger: () => Promise<T>): Chargement<T> {
  const [chargement, setChargement] = useState<Chargement<T>>({
    etat: "attente",
  });

  useEffect(() => {
    let vivant = true;
    charger()
      .then((donnees) => {
        if (vivant) setChargement({ etat: "recu", donnees });
      })
      .catch(() => {
        if (vivant) setChargement({ etat: "panne" });
      });
    return () => {
      vivant = false;
    };
  }, [charger]);

  return chargement;
}

// ── Les prix, calculés sur ce que l'API rend ────────────────────────────────

/** Ce qu'un emplacement de prix affiche : un montant connu, ou la raison pour
 *  laquelle il n'y en a pas. */
export type Tarif =
  | { etat: "connu"; texte: string }
  | { etat: "attente" | "panne" | "absent" };

/** Un montant qu'on peut afficher : un nombre fini et STRICTEMENT positif.
 *  Une offre créée à zéro (brouillon, erreur de saisie) n'a pas de prix : la
 *  laisser passer écrirait « dès 0 € par mois » sur une page de vente. */
export function lisible(cents: unknown): cents is number {
  return typeof cents === "number" && Number.isFinite(cents) && cents > 0;
}

/** Le plus petit et le plus grand montant d'une liste, ou `null` si elle ne
 *  porte aucun montant lisible. `Math.min()` d'une liste vide vaut l'infini :
 *  formaté, il s'afficherait « ∞ € ». */
export function bornes(cents: unknown[]): { bas: number; haut: number } | null {
  const lisibles = cents.filter(lisible);
  if (lisibles.length === 0) return null;
  return { bas: Math.min(...lisibles), haut: Math.max(...lisibles) };
}

export function tarifDe<T>(
  chargement: Chargement<T>,
  calcul: (donnees: T) => string | null,
): Tarif {
  if (chargement.etat !== "recu") return { etat: chargement.etat };
  const texte = calcul(chargement.donnees);
  return texte === null ? { etat: "absent" } : { etat: "connu", texte };
}

// ── Petits outils ───────────────────────────────────────────────────────────

/** Propriétés personnalisées posées en ligne (`--i`, `--n`…) : React les
 *  accepte, son type `CSSProperties` ne les connaît pas. */
export function variables(valeurs: Record<string, string | number>): CSSProperties {
  return valeurs as CSSProperties;
}

/** Le visiteur a-t-il demandé moins de mouvement ? Lu au moment de brancher
 *  un effet, pas au rendu : jsdom n'a pas de `matchMedia`. */
export function mouvementReduit(): boolean {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/** Une requête de média, suivie en direct. Sans `matchMedia` : faux. */
export function useMedia(requete: string): boolean {
  const abonner = useCallback(
    (rappel: () => void) => {
      if (typeof window.matchMedia !== "function") return () => undefined;
      const media = window.matchMedia(requete);
      media.addEventListener("change", rappel);
      return () => media.removeEventListener("change", rappel);
    },
    [requete],
  );
  return useSyncExternalStore(
    abonner,
    () =>
      typeof window.matchMedia === "function" &&
      window.matchMedia(requete).matches,
    () => false,
  );
}

// ── Navigation : où l'on est, où mène une entrée ────────────────────────────

/** Le chemin de la page affichée, sans barre oblique finale (`/etudes/` et
 *  `/etudes` sont la même page). */
export function cheminCourant(): string {
  return window.location.pathname.replace(/\/+$/, "") || ACCUEIL;
}

/** L'adresse d'une entrée de navigation, vue depuis la page `ici`.
 *
 *  Une entrée `ancre` désigne une section de l'ACCUEIL : sur l'accueil elle
 *  reste une ancre, et la page défile ; ailleurs elle mène à l'accueil, à
 *  cette section. Écrire `#contact` en dur sur une page qui n'a pas de section
 *  « contact » ferait un lien qui ne mène nulle part. */
export function adresseDe(entree: EntreeDeNavigation, ici: string): string {
  if (entree.lien !== undefined) return entree.lien;
  return ici === ACCUEIL ? `#${entree.ancre}` : `${ACCUEIL}#${entree.ancre}`;
}

/** L'entrée est-elle la page affichée ? Seul un lien interne peut l'être : une
 *  ancre désigne une section, une adresse externe un autre site. */
export function estCourante(entree: EntreeDeNavigation, ici: string): boolean {
  return entree.lien !== undefined && estLaPage(entree.lien, ici);
}

/** Cette adresse est-elle EXACTEMENT la page affichée ? Une adresse qui porte
 *  une ancre (`/etudes#comment-ca-marche`) désigne une section : elle n'est
 *  pas « la page », sinon les six liens d'un même panneau se diraient tous
 *  courants à la fois. */
export function estLaPage(lien: string, ici: string): boolean {
  return lien.startsWith("/") && (lien.replace(/\/+$/, "") || ACCUEIL) === ici;
}

/** Le chemin d'une adresse INTERNE, sans ancre ni barre oblique finale ;
 *  `null` pour une adresse externe (Calendly, un réseau). */
export function cheminDe(lien: string): string | null {
  if (!lien.startsWith("/")) return null;
  return lien.split("#")[0].replace(/\/+$/, "") || ACCUEIL;
}

/** La page affichée est-elle dans cette rubrique du menu ? Vrai quand l'un de
 *  ses liens — carte de mise en avant comprise — mène à cette page, à l'une de
 *  ses sections, ou à une page au-dessus d'elle (`/boutique` pour
 *  `/boutique/une-etude`). Déduit du chemin, jamais écrit dans les données.
 *
 *  La comparaison se fait segment par segment : `/etudes-de-cas` n'est pas
 *  sous `/etudes`. L'accueil n'est « au-dessus » de rien, sinon toute page
 *  serait dans la rubrique qui y mène. */
export function contientLaPage(rubrique: Rubrique, ici: string): boolean {
  return [...rubrique.liens, rubrique.enAvant].some(({ lien }) => {
    const chemin = cheminDe(lien);
    if (chemin === null) return false;
    if (chemin === ici) return true;
    return chemin !== ACCUEIL && ici.startsWith(`${chemin}/`);
  });
}

// ── Le titre de l'onglet et la description ──────────────────────────────────

/** Le gabarit HTML annonce « EVKHA — Espace client » et sa description parle
 *  de l'espace connecté : justes pour lui, faux pour une page publique que
 *  l'on partage par lien et que les moteurs indexent. Les deux sont rendus en
 *  partant. */
/** La marque telle qu'un titre RELEVÉ la porte à sa fin : « – EVKHA »,
 *  « | EVKHA », « – EVKHA Business & Formations ». Construite sur `MARQUE`. */
const MARQUE_EN_BOUT = new RegExp(
  `\\s+[–—|-]\\s+${MARQUE}(?:\\s+Business\\s*(?:&|et)\\s*Formations)?\\s*$`,
  "i",
);

/** LE format du titre d'onglet, pour toutes les pages du socle :
 *  « Titre de la page — EVKHA » (tiret long, marque à la fin).
 *
 *  Les titres relevés sur le site de la cliente ferment tantôt par
 *  « – EVKHA », tantôt par « | EVKHA », tantôt par le nom complet : la marque
 *  qu'un titre porte déjà à sa fin est retirée avant d'être reposée, pour
 *  qu'elle ne soit jamais écrite deux fois ni de deux façons. Le titre
 *  lui-même n'est pas touché. Appliquée deux fois, la fonction rend la même
 *  chose. */
export function titreDOnglet(titre: string): string {
  const nu = titre.trim().replace(MARQUE_EN_BOUT, "").trim();
  return nu === "" ? MARQUE : `${nu} — ${MARQUE}`;
}

/** Pose une valeur sur une balise de l'en-tête du document, en la créant si le
 *  gabarit ne la porte pas, et rend de quoi tout remettre comme avant. */
function poserDansLEnTete(
  selecteur: string,
  creer: () => HTMLElement,
  attribut: string,
  valeur: string,
): () => void {
  const existante = document.head.querySelector<HTMLElement>(selecteur);
  if (existante) {
    const avant = existante.getAttribute(attribut);
    existante.setAttribute(attribut, valeur);
    return () => {
      if (avant === null) existante.removeAttribute(attribut);
      else existante.setAttribute(attribut, avant);
    };
  }
  const balise = creer();
  balise.setAttribute(attribut, valeur);
  document.head.append(balise);
  return () => balise.remove();
}

function meta(cle: "name" | "property", nom: string): () => HTMLElement {
  return () => {
    const balise = document.createElement("meta");
    balise.setAttribute(cle, nom);
    return balise;
  };
}

/** Le titre de l'onglet, la description, et tout ce qui les RÉPÈTE à un
 *  moteur ou à un réseau : l'adresse canonique de la page, et les balises de
 *  partage (Open Graph, Twitter).
 *
 *  Jusqu'au 20/11/2026, seuls le titre et la description suivaient la page.
 *  L'aperçu de partage d'une formation annonçait donc « EVKHA — Business et
 *  formations », le titre figé du gabarit, et aucune page ne disait son
 *  adresse canonique : `/etudes?utm_source=lettre` et `/etudes` étaient deux
 *  pages pour un moteur. Tout part maintenant du MÊME couple titre /
 *  description (règle 5) — une page ne peut pas en annoncer deux.
 *
 *  L'adresse canonique est le chemin de la page, sans paramètre ni ancre, sur
 *  `ORIGINE_DU_SITE`. Tout est rendu en partant, comme avant.
 *
 *  `aSonAdresse` : faux pour une page qui n'est PAS celle de son adresse —
 *  « page introuvable », « article introuvable », le retour d'un paiement.
 *  Elle garde son titre et sa description, mais ne se dit ni canonique ni
 *  rangée dans un fil d'Ariane : ce serait déclarer aux moteurs, comme une
 *  vraie page, l'adresse fautive qu'on leur demande par ailleurs de ne pas
 *  indexer (`useSansIndexation`).
 *
 *  `image` : la photo de la page, pour l'aperçu d'un lien partagé. Absente,
 *  la page garde l'image du gabarit (le logo). Un portrait du blog partagé
 *  sur un réseau montrait le logo d'EVKHA, pas la personne dont il parle. */
export function useTitreDePage(
  titre: string,
  description: string,
  aSonAdresse: boolean = true,
  image?: { src: string; largeur: number; hauteur: number },
): void {
  const source = image?.src;
  const largeur = image?.largeur;
  const hauteur = image?.hauteur;
  useEffect(() => {
    const titreDAvant = document.title;
    document.title = titre;
    const defaire = [
      poserDansLEnTete('meta[name="description"]', meta("name", "description"), "content", description),
      poserDansLEnTete('meta[property="og:title"]', meta("property", "og:title"), "content", titre),
      poserDansLEnTete(
        'meta[property="og:description"]',
        meta("property", "og:description"),
        "content",
        description,
      ),
      poserDansLEnTete('meta[name="twitter:title"]', meta("name", "twitter:title"), "content", titre),
      poserDansLEnTete(
        'meta[name="twitter:description"]',
        meta("name", "twitter:description"),
        "content",
        description,
      ),
    ];
    if (source !== undefined) {
      const photo = adresseAbsolue(source);
      defaire.push(
        poserDansLEnTete('meta[property="og:image"]', meta("property", "og:image"), "content", photo),
        poserDansLEnTete('meta[name="twitter:image"]', meta("name", "twitter:image"), "content", photo),
        // Les dimensions du gabarit sont celles du logo : laissées telles
        // quelles, elles mentiraient sur la photo.
        poserDansLEnTete(
          'meta[property="og:image:width"]',
          meta("property", "og:image:width"),
          "content",
          String(largeur),
        ),
        poserDansLEnTete(
          'meta[property="og:image:height"]',
          meta("property", "og:image:height"),
          "content",
          String(hauteur),
        ),
      );
    }
    if (aSonAdresse) {
      const adresse = adresseAbsolue(cheminCourant());
      defaire.push(
        poserDansLEnTete(
          'link[rel="canonical"]',
          () => {
            const lien = document.createElement("link");
            lien.rel = "canonical";
            return lien;
          },
          "href",
          adresse,
        ),
        poserDansLEnTete('meta[property="og:url"]', meta("property", "og:url"), "content", adresse),
      );
      // Le fil d'Ariane des pages rangées sous une rubrique, déduit du
      // chemin : aucune page n'a à y penser (règle 4).
      const fil = filDAriane(cheminCourant(), titre.replace(MARQUE_EN_BOUT, "").trim());
      if (fil !== null) defaire.push(poserUnBlocStructure(fil, BLOCS_DU_SOCLE.fil));
    }
    return () => {
      document.title = titreDAvant;
      // Dans l'ordre inverse : une balise créée ici est retirée, une balise
      // du gabarit retrouve sa valeur.
      defaire.reverse().forEach((remettre) => remettre());
    };
  }, [titre, description, aSonAdresse, source, largeur, hauteur]);
}

/** Les blocs de données structurées que le SOCLE pose de lui-même sur toute
 *  page, marqués par `data-bloc`. Le bloc qu'une page pose pour ce qu'elle
 *  vend (`Course`, `Product`, `Article`) n'en porte pas : on les distingue
 *  sans lire leur contenu. */
export const BLOCS_DU_SOCLE = { fil: "fil-d-ariane", questions: "questions" } as const;

/** Pose un bloc de données structurées (JSON-LD) dans l'en-tête du document,
 *  et le retire au démontage ou quand il change — comme `useTitreDePage` rend
 *  le titre en partant. `null` : rien à poser.
 *
 *  Le contenu est écrit par `textContent`, jamais par du HTML : une chaîne qui
 *  contiendrait une balise ne peut pas en sortir. Les blocs se construisent
 *  dans `referencement.ts`. */
export function useDonneesStructurees(json: string | null): void {
  useEffect(() => {
    if (json === null) return undefined;
    return poserUnBlocStructure(json);
  }, [json]);
}

function poserUnBlocStructure(json: string, bloc?: string): () => void {
  const balise = document.createElement("script");
  balise.type = "application/ld+json";
  if (bloc !== undefined) balise.dataset.bloc = bloc;
  balise.textContent = json;
  document.head.append(balise);
  return () => balise.remove();
}

/** Les questions fréquentes d'une page, déclarées aux moteurs TELLES QUE LA
 *  PAGE LES AFFICHE.
 *
 *  Elles sont LUES DANS LE DOCUMENT (les `<details>` du bloc `.acc-faq`,
 *  commun à toutes les pages), pas dans les fichiers de contenu : plusieurs
 *  pages retouchent leurs réponses à l'affichage (`ancienneteSure`, les
 *  chiffres que le serveur rend pour une formation, une question masquée).
 *  Déclarer le texte source annoncerait à un moteur une réponse que le
 *  visiteur ne lit pas (règle 3 : juger ce que le lecteur va lire).
 *
 *  Sans tableau de dépendances : l'effet relit le bloc à chaque rendu de la
 *  page, et ne touche à l'en-tête que si le texte a changé. */
export function useQuestionsStructurees(page: RefObject<HTMLElement | null>): void {
  const pose = useRef<{ json: string; retirer: () => void } | null>(null);
  useEffect(() => {
    const blocs = page.current?.querySelectorAll(".acc-faq details") ?? [];
    const questions = Array.from(blocs, (bloc) => {
      const question = bloc.querySelector("summary")?.textContent ?? "";
      const reponse = Array.from(bloc.children)
        .filter((enfant) => enfant.tagName !== "SUMMARY")
        .map((enfant) => enfant.textContent ?? "")
        .join(" ");
      return { question: enLigne(question), reponse: enLigne(reponse) };
    });
    const json = questionsFrequentes(questions);
    if (json === (pose.current?.json ?? null)) return;
    pose.current?.retirer();
    pose.current = json === null ? null : { json, retirer: poserUnBlocStructure(json, BLOCS_DU_SOCLE.questions) };
  });
  // Au démontage seulement : le bloc part avec la page.
  useEffect(
    () => () => {
      pose.current?.retirer();
      pose.current = null;
    },
    [],
  );
}

/** Un texte relu dans le document, sur une ligne : les retours et les espaces
 *  de mise en page ne sont pas du texte. */
function enLigne(texte: string): string {
  return texte.replace(/\s+/g, " ").trim();
}

/** Une page qui n'a rien à faire dans un moteur de recherche — « page
 *  introuvable », « article introuvable » : l'application répond 200 à toute
 *  adresse, et sans cette balise un moteur indexerait la page d'erreur à
 *  l'adresse fautive. Posée à l'affichage, retirée au démontage : la page
 *  suivante, elle, s'indexe. */
export function useSansIndexation(): void {
  useEffect(() => {
    const balise = document.createElement("meta");
    balise.name = "robots";
    balise.content = "noindex";
    document.head.append(balise);
    return () => balise.remove();
  }, []);
}

// ── L'ancienneté ────────────────────────────────────────────────────────────

/** L'ancienneté d'Evangeline. Les pages relevées écrivent « 15 ans » ici et
 *  « 16 ans » là, et la cliente n'a pas tranché. À l'affichage, les deux
 *  deviennent « plus de 15 ans », vrai dans les deux cas — la même formule que
 *  l'accueil. UNE fonction, pour les packs comme pour les formations
 *  (règle 5) ; le texte relevé n'est pas touché.
 *
 *  Un nombre déjà précédé de « plus de » est laissé tel quel. Écrit SANS
 *  regard arrière (« lookbehind ») : Safari avant 16.4 refuse cette syntaxe au
 *  chargement du fichier, et toute l'application tombe avec lui. Le préfixe
 *  est donc capturé, puis remis en place. */
export function ancienneteSure(texte: string): string {
  return texte.replace(
    /(plus de )?\b1[56](?=\sans\b)/g,
    (trouve: string, dejaDit: string | undefined) =>
      dejaDit === undefined ? "plus de 15" : trouve,
  );
}

// ── Le menu plein écran ─────────────────────────────────────────────────────

/** L'état du menu, partagé entre la page et `EnTeteSite` : la page en a besoin
 *  pour rendre inerte ce qui est derrière le menu ouvert.
 *
 *  Que des valeurs et des fonctions, pas de référence à un élément : le
 *  bouton du menu appartient à `EnTeteSite`, qui lui rend le focus à la
 *  fermeture par Échap. */
export type Menu = {
  ouvert: boolean;
  basculer: () => void;
  fermer: () => void;
  /** Un clic sur un lien — de la barre comme du menu — referme le menu : sans
   *  cela, « Me contacter » faisait défiler la page DERRIÈRE le menu resté
   *  ouvert, et le visiteur ne voyait rien bouger. */
  fermerSurUnLien: (evenement: MouseEvent<HTMLElement>) => void;
};

/** Menu plein écran : la page derrière ne défile plus, et repasser en grand
 *  écran le referme — la barre montre alors les mêmes rubriques. Échap referme
 *  aussi : c'est `EnTeteSite` qui l'écoute, pour rendre le focus à son
 *  bouton. */
export function useMenu(): Menu {
  const [ouvert, setOuvert] = useState(false);
  const fermer = useCallback(() => setOuvert(false), []);

  useEffect(() => {
    if (!ouvert) return undefined;
    const racine = document.documentElement;
    const debordement = racine.style.overflow;
    racine.style.overflow = "hidden";

    const grandEcran =
      typeof window.matchMedia === "function"
        ? window.matchMedia("(min-width: 1001px)")
        : null;
    grandEcran?.addEventListener("change", fermer);
    return () => {
      racine.style.overflow = debordement;
      grandEcran?.removeEventListener("change", fermer);
    };
  }, [ouvert, fermer]);

  const basculer = useCallback(() => setOuvert((etat) => !etat), []);
  const fermerSurUnLien = useCallback(
    (evenement: MouseEvent<HTMLElement>) => {
      if ((evenement.target as Element).closest("a")) setOuvert(false);
    },
    [],
  );

  return { ouvert, basculer, fermer, fermerSurUnLien };
}

// ── La pause ────────────────────────────────────────────────────────────────

/** L'état des boutons de pause d'une page : un seul, quel que soit le nombre
 *  de boutons. La page pose `acc-fige` sur sa racine quand il est vrai, et la
 *  feuille arrête alors tout ce qui boucle (WCAG 2.2.2). */
export function usePause(): { fige: boolean; basculer: () => void } {
  const [fige, setFige] = useState(false);
  const basculer = useCallback(() => setFige((etat) => !etat), []);
  return { fige, basculer };
}

// ── Boutons aimantés ────────────────────────────────────────────────────────

/** Boutons aimantés : seulement avec une vraie souris, jamais sous mouvement
 *  réduit. Un seul écouteur sur la page (délégation) plutôt qu'un par bouton :
 *  les boutons montés après coup restent couverts. */
export function useAimants(page: RefObject<HTMLElement | null>): void {
  useEffect(() => {
    const racine = page.current;
    if (!racine || mouvementReduit()) return undefined;
    if (
      typeof window.matchMedia !== "function" ||
      !window.matchMedia("(hover: hover) and (pointer: fine)").matches
    ) {
      return undefined;
    }

    let aimante: HTMLElement | null = null;
    function relacher() {
      if (aimante) aimante.style.translate = "";
      aimante = null;
    }
    function auDeplacement(evenement: PointerEvent) {
      const cible =
        evenement.target instanceof Element
          ? evenement.target.closest<HTMLElement>("a.acc-btn")
          : null;
      if (cible !== aimante) relacher();
      if (!cible) return;
      aimante = cible;
      const r = cible.getBoundingClientRect();
      const x = (evenement.clientX - r.left - r.width / 2) * 0.16;
      const y = (evenement.clientY - r.top - r.height / 2) * 0.26;
      cible.style.translate = `${x}px ${y}px`;
    }
    racine.addEventListener("pointermove", auDeplacement);
    racine.addEventListener("pointerleave", relacher);
    return () => {
      racine.removeEventListener("pointermove", auDeplacement);
      racine.removeEventListener("pointerleave", relacher);
      relacher();
    };
  }, [page]);
}

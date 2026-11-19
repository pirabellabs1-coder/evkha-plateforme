/** Le texte que les pages publiques refondues ont en commun : la barre, le
 * menu, le pied, le bouton de pause, les phrases qui remplacent un prix.
 *
 * Il vivait dans `contenuAccueil.ts`. Depuis que la page des études porte la
 * même barre et le même pied (`EnTeteSite`, `PiedSite`), il est écrit ICI, une
 * fois, et les deux pages le lisent (règle 5) : une entrée de menu ajoutée
 * pour l'une apparaît sur l'autre sans qu'on y pense.
 *
 * Éditorial uniquement, comme `contenu.ts` : AUCUN PRIX n'est écrit ici. Le
 * test `la-page-des-etudes-lit-ses-prix-au-serveur` verrouille qu'aucun
 * montant en euros ne figure dans ce fichier.
 */
import { CONTACT_EMAIL } from "./contenu";

// ── Adresses ────────────────────────────────────────────────────────────────

/** Le chemin de la page d'accueil : celle dont les sections servent d'ancres
 *  à la barre (voir `EntreeDeNavigation`). */
export const ACCUEIL = "/";

export const LIENS = {
  etudes: "/etudes",
  boutique: "/boutique",
  partenaires: "/partenaires",
  espace: "/espace/connexion",
  appel: "https://calendly.com/contact-evkha",
  courriel: `mailto:${CONTACT_EMAIL}`,
  packs: "https://www.evkha.fr/packs",
  formations: "https://www.evkha.fr/formation",
  outils: "https://www.evkha.fr/boite-a-outil",
  article: "https://www.evkha.fr/boite-a-outils/idee-business-viable",
};

/** L'identifiant du contenu principal, visé par le lien d'évitement. Écrit une
 *  fois : le lien (`EnTeteSite`) et sa cible (`<main>` de chaque page) le
 *  lisent ici, et ne peuvent pas se désaccorder. */
export const ID_DU_CONTENU = "acc-contenu";

export const EVITEMENT = "Aller au contenu";

// ── Navigation ──────────────────────────────────────────────────────────────

/** Une entrée de la barre. Deux formes, jamais les deux à la fois :
 *
 *  - `lien` : une page. Elle est « courante » quand son chemin est celui de la
 *    page affichée — `EnTeteSite` le DÉDUIT de l'adresse, comme `MenuSite` :
 *    un drapeau écrit ici annoncerait « vous êtes ici » sur la mauvaise page.
 *  - `ancre` : une SECTION DE L'ACCUEIL, par son identifiant. Sur l'accueil,
 *    l'entrée reste une ancre (`#methode`) et la page défile ; ailleurs, elle
 *    mène à l'accueil, à cette section (`/#methode`). Voir `adresseDe`
 *    (`site.ts`). */
export type EntreeDeNavigation = {
  libelle: string;
  /** Cerclée dans la barre : c'est la porte des clients déjà inscrits. */
  compte?: boolean;
} & ({ lien: string; ancre?: undefined } | { ancre: string; lien?: undefined });

/** Les entrées de navigation, écrites UNE fois : la barre et le menu plein
 *  écran du téléphone lisent toutes deux cette liste, sur toutes les pages qui
 *  portent `EnTeteSite`. Six au plus — au-delà, la barre ne tient plus sur une
 *  ligne à 1100 px. */
export const NAVIGATION: EntreeDeNavigation[] = [
  { libelle: "Les études", lien: LIENS.etudes },
  { libelle: "Boutique", lien: LIENS.boutique },
  { libelle: "Partenaires PRO", lien: LIENS.partenaires },
  { libelle: "La méthode", ancre: "methode" },
  { libelle: "Espace client", lien: LIENS.espace, compte: true },
];

/** Le bouton noir de la barre. Le contact est une section de l'accueil. */
export const APPEL_DE_LA_BARRE: EntreeDeNavigation = {
  libelle: "Me contacter",
  ancre: "contact",
};

export const BARRE = {
  logo: "Evkha",
  /** Le nom accessible du logo : il mène à l'accueil. */
  nomDuLogo: "EVKHA, accueil",
  nomDeLaBarre: "Principale",
  nomDuMenu: "Menu",
  ouvrirLeMenu: "Ouvrir le menu",
  fermerLeMenu: "Fermer le menu",
};

/** Le bouton qui arrête tout ce qui tourne en boucle. Plusieurs exemplaires
 *  possibles sur une page, un seul état. */
export const PAUSE = {
  arreter: "Mettre les animations en pause",
  relancer: "Relancer les animations",
};

// ── Ce qu'une page écrit à la place d'un prix ───────────────────────────────

/** Ce que la page écrit à la place d'un prix qu'elle n'a pas. Trois états,
 *  trois phrases : un chargement, une panne et une absence ne se confondent
 *  pas (règle 1).
 *
 *  `absent` : le catalogue a répondu, et il ne porte pas cette offre. La
 *  carte le dit et son bouton est neutralisé — renvoyer vers une page où
 *  l'offre n'est pas non plus serait promettre un prix qui n'existe pas. */
export const TARIFS = {
  attente: "Tarif en cours de chargement…",
  panne: "Tarif momentanément indisponible",
  absent: "Indisponible pour le moment",
  alerte: "Les tarifs sont momentanément indisponibles.",
  alerteSuite: "Écrivez-nous à",
  /** Dans une section, sous l'alerte unique du haut de page. */
  rappel: "Tarifs momentanément indisponibles : la page les affichera dès leur retour.",
};

// ── Pied de page ────────────────────────────────────────────────────────────

export const PIED = {
  droits: "EVKHA. Tous droits réservés.",
  signature: "EVKHA Business & Formations · Lille",
  navigation: "Informations légales",
  liens: [
    {
      libelle: "Confidentialité",
      lien: "https://www.evkha.fr/politique-de-confidentialite",
    },
    { libelle: "Mentions légales", lien: "https://www.evkha.fr/mentions-legales" },
    { libelle: "RGPD", lien: "https://www.evkha.fr/rgpd" },
    { libelle: "CGV", lien: "https://www.evkha.fr/cgv" },
  ],
  /** Les réseaux de la cliente, relevés sur l'accueil de son site. */
  reseauxTitre: "Réseaux sociaux",
  reseaux: [
    {
      libelle: "LinkedIn",
      lien: "https://www.linkedin.com/in/evangeline-strobbe-khaili-54a2511b2/",
    },
    {
      libelle: "Instagram",
      lien: "https://www.instagram.com/evkha_business_formations/",
    },
    {
      libelle: "Facebook",
      lien: "https://www.facebook.com/profile.php?id=61577284710257",
    },
  ],
};

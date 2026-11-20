/** Le plan de l'administration : ses groupes, ses écrans, leurs en-têtes.
 *
 * UNE source (règle 5) pour la barre latérale, le fil d'Ariane, le titre de
 * page et sa phrase d'aide : tous lisent ce fichier (`Coquille.tsx`).
 *
 * Les raccourcis du tableau de bord, eux, ne le lisent PAS encore :
 * `pages/TableauDeBord.tsx` écrit ses six liens en dur, libellés et chemins
 * compris. Un écran renommé ici doit donc l'être là-bas à la main.
 *
 * ## Pourquoi des groupes
 *
 * La barre alignait quatorze entrées à plat, dans l'ordre où elles avaient été
 * écrites : « Annonces » avant « Transactions », « Qualité » entre
 * « Incidents » et « Commandes ». La gérante y cherchait chaque écran en
 * relisant toute la liste. Les groupes suivent son travail, dans l'ordre où il
 * se fait : ce qu'elle regarde d'abord (Pilotage), ce qu'elle vend
 * (Catalogue), ceux à qui elle vend (Clients), ce qui se fabrique
 * (Production), ce qu'elle envoie (Communication).
 *
 * ## Ce qui ne change pas
 *
 * Les ADRESSES. `/admin/jobs` s'appelle « Générations » à l'écran et
 * `/admin/orders` « Commandes », mais leurs chemins restent ceux de
 * `router.tsx` : un lien enregistré, un courriel d'incident, un test
 * continuent de mener au bon endroit.
 *
 * Fichier `.ts`, sans JSX : il ne porte que des données, et se lit aussi bien
 * depuis un test que depuis un écran.
 */
import type { NomIcone } from "./icones";

export interface EntreeDeNavigation {
  /** Le chemin de la route, tel que `router.tsx` le déclare. */
  vers: string;
  /** Le nom de l'écran dans la barre et dans le fil d'Ariane. */
  libelle: string;
  icone: NomIcone;
  /** Le titre de la page (`h1`). Souvent le libellé, parfois plus explicite. */
  titre: string;
  /** La phrase d'aide sous le titre : ce que l'écran permet, en une ligne. */
  aide: string;
  /** Vrai pour l'entrée d'index (`/admin`) : sans cela elle resterait
   *  « courante » sur tous les écrans, puisque tous commencent par `/admin`. */
  exact?: boolean;
  /** Le nom d'une page de détail (`/admin/jobs/<id>`), dernier maillon du fil
   *  d'Ariane. Absent : l'écran n'a pas de page de détail. */
  detail?: string;
}

export interface GroupeDeNavigation {
  cle: string;
  libelle: string;
  entrees: EntreeDeNavigation[];
}

export const GROUPES: GroupeDeNavigation[] = [
  {
    cle: "pilotage",
    libelle: "Pilotage",
    entrees: [
      {
        vers: "/admin",
        libelle: "Tableau de bord",
        icone: "tableau",
        titre: "Tableau de bord",
        aide: "Vos ventes, ce qui attend une réponse aujourd'hui et la production du moment.",
        exact: true,
      },
      {
        vers: "/admin/transactions",
        libelle: "Transactions",
        icone: "transactions",
        titre: "Transactions",
        aide: "Paiements aboutis, en cours et paniers abandonnés. Relance au cas par cas.",
      },
      {
        vers: "/admin/qualite",
        libelle: "Qualité",
        icone: "qualite",
        titre: "Qualité",
        aide: "Ce que la production a trouvé et corrigé, chapitre par chapitre. Interne.",
      },
    ],
  },
  {
    cle: "catalogue",
    libelle: "Catalogue",
    entrees: [
      {
        vers: "/admin/livrables",
        libelle: "Livrables",
        icone: "livrables",
        titre: "Livrables",
        aide: "Plan de chapitres, données collectées et charte du modèle, livrable par livrable.",
      },
      {
        vers: "/admin/boutique",
        libelle: "Boutique",
        icone: "boutique",
        titre: "Boutique",
        aide: "Les études déjà rédigées : fiche, fichier, prix et mise en ligne.",
      },
      {
        vers: "/admin/formations",
        libelle: "Formations",
        icone: "formations",
        titre: "Formations",
        aide: "Vos formations, leurs modules et leurs leçons.",
      },
    ],
  },
  {
    cle: "clients",
    libelle: "Clients",
    entrees: [
      {
        vers: "/admin/organisations",
        libelle: "Organisations",
        icone: "organisations",
        titre: "Organisations",
        aide: "Formule, solde, consommation et volumes, agence par agence.",
      },
      {
        vers: "/admin/clients",
        libelle: "Clients",
        icone: "clients",
        titre: "Clients",
        aide: "Les contacts et leurs abonnements.",
        detail: "Fiche client",
      },
      {
        vers: "/admin/orders",
        libelle: "Commandes",
        icone: "commandes",
        titre: "Commandes",
        aide: "Les commandes reçues et leur état.",
      },
      {
        vers: "/admin/demandes",
        libelle: "Demandes",
        icone: "demandes",
        titre: "Demandes à traiter",
        aide: "Changements de formule et achats de crédits venus des espaces clients.",
      },
      {
        vers: "/admin/signalements",
        libelle: "Signalements",
        icone: "signalements",
        titre: "Signalements",
        aide: "Les problèmes remontés depuis les espaces clients, et l'accès d'assistance.",
      },
    ],
  },
  {
    cle: "production",
    libelle: "Production",
    entrees: [
      {
        vers: "/admin/jobs",
        libelle: "Générations",
        icone: "generations",
        titre: "Générations",
        aide: "Suivi des études en cours et terminées. Relance en cas d'échec.",
        detail: "Fiche de la génération",
      },
      {
        vers: "/admin/incidents",
        libelle: "Incidents",
        icone: "incidents",
        titre: "Incidents",
        aide: "Ce qui demande une intervention.",
      },
    ],
  },
  {
    cle: "communication",
    libelle: "Communication",
    entrees: [
      {
        vers: "/admin/annonces",
        libelle: "Annonces",
        icone: "annonces",
        titre: "Annonces",
        aide: "Prévenir tous vos clients d'un livrable à venir ou disponible.",
      },
      {
        vers: "/admin/prospection",
        libelle: "Prospection",
        icone: "prospection",
        titre: "Prospection",
        aide: "Trouver des prospects, préparer les e-mails, valider avant l'envoi, suivre les résultats.",
      },
    ],
  },
];

/** Où l'on est : le groupe, l'écran, et — sur une page de détail — son nom. */
export interface Position {
  groupe: GroupeDeNavigation;
  entree: EntreeDeNavigation;
  /** Le dernier maillon du fil d'Ariane, ou `null` sur l'écran lui-même. */
  detail: string | null;
}

/** La position que désigne un chemin, ou `null` s'il n'est celui d'aucun
 *  écran déclaré.
 *
 * On retient l'entrée dont le chemin est le PLUS LONG préfixe du chemin
 * courant : `/admin/jobs/42` hérite ainsi de « Générations », et une
 * sous-route nouvelle est titrée sans avoir à être déclarée. Viser la classe,
 * pas les deux pages de détail connues (règle 4). L'entrée d'index ne préfixe
 * qu'elle-même : sinon `/admin/inconnu` s'intitulerait « Tableau de bord ».
 */
export function positionDe(chemin: string): Position | null {
  const propre = chemin.length > 1 ? chemin.replace(/\/+$/, "") : chemin;
  let trouvee: Position | null = null;
  for (const groupe of GROUPES) {
    for (const entree of groupe.entrees) {
      const exacte = propre === entree.vers;
      const dessous = !entree.exact && propre.startsWith(`${entree.vers}/`);
      if (!exacte && !dessous) continue;
      if (trouvee && trouvee.entree.vers.length >= entree.vers.length) continue;
      trouvee = {
        groupe,
        entree,
        detail: dessous ? (entree.detail ?? "Détail") : null,
      };
    }
  }
  return trouvee;
}

/** L'en-tête d'un chemin qu'aucune entrée ne couvre. Il se dit tel quel :
 *  reprendre le titre d'un autre écran ferait croire qu'on y est. */
export const ENTETE_PAR_DEFAUT = {
  titre: "Administration",
  aide: "Supervision de la plateforme.",
} as const;

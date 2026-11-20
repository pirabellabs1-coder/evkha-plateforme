/** Ce que le site DÉCLARE aux moteurs de recherche et aux moteurs de réponse :
 * les blocs de données structurées (schema.org, JSON-LD).
 *
 * Que des fonctions pures, qui rendent une chaîne JSON prête à poser par
 * `site.useDonneesStructurees`. Aucune ne lit le serveur, et AUCUNE n'écrit un
 * prix : un montant vient de l'API ou n'est pas déclaré (les formations
 * déclarent le leur dans `Formations.tsx`, une fois la réponse reçue).
 *
 * Rien n'est inventé. L'identité vient de `contenuSite.IDENTITE` — elle-même
 * tenue d'accord avec les mentions légales par le test
 * `le-referencement-dit-vrai` ; pas de téléphone, pas de note, pas de nombre
 * d'avis, pas d'horaires : le site n'en publie pas, ou les lit au serveur.
 *
 * Construit par `JSON.stringify` : aucune chaîne n'est collée à la main.
 */
import { CONTACT_EMAIL } from "./contenu";
import {
  adresseAbsolue,
  CHEMINS,
  IDENTITE,
  LIENS,
  MARQUE,
  NAVIGATION,
  ORIGINE_DU_SITE,
  RESEAUX_SOCIAUX,
} from "./contenuSite";

/** L'identifiant de l'entreprise dans le graphe : les autres blocs la citent
 *  par lui au lieu de la redécrire (règle 5). */
const ORGANISATION = `${ORIGINE_DU_SITE}/#organisation`;

const CONTEXTE = "https://schema.org";

/** L'entreprise et le site, posés sur la page d'accueil.
 *
 *  `ProfessionalService` est un `LocalBusiness` : le siège publié par les
 *  mentions légales lui donne une adresse réelle. */
export function organisationEtSite(description: string): string {
  return JSON.stringify({
    "@context": CONTEXTE,
    "@graph": [
      {
        "@type": "ProfessionalService",
        "@id": ORGANISATION,
        name: IDENTITE.nom,
        alternateName: MARQUE,
        url: adresseAbsolue(CHEMINS.accueil),
        logo: adresseAbsolue(IDENTITE.logo),
        image: adresseAbsolue(IDENTITE.imageDePartage),
        description,
        email: CONTACT_EMAIL,
        founder: { "@type": "Person", name: IDENTITE.fondatrice },
        address: {
          "@type": "PostalAddress",
          streetAddress: IDENTITE.siege.rue,
          postalCode: IDENTITE.siege.codePostal,
          addressLocality: IDENTITE.siege.ville,
          addressCountry: IDENTITE.siege.pays,
        },
        areaServed: { "@type": "Country", name: "France" },
        sameAs: RESEAUX_SOCIAUX.map((reseau) => reseau.lien),
      },
      {
        "@type": "WebSite",
        "@id": `${ORIGINE_DU_SITE}/#site`,
        url: adresseAbsolue(CHEMINS.accueil),
        name: IDENTITE.nom,
        inLanguage: "fr-FR",
        publisher: { "@id": ORGANISATION },
      },
    ],
  });
}

/** Les quatre documents produits sur le projet du client, déclarés sur la
 *  page des études. Leurs noms sont ceux du menu (`NAVIGATION`) : les liens
 *  de la première rubrique qui mènent à une carte de la page. Aucun prix. */
export function servicesDesEtudes(description: string): string {
  const rubrique = NAVIGATION.find((entree) => entree.id === "etudes");
  const documents = (rubrique?.liens ?? []).filter((lien) =>
    lien.lien.startsWith(`${LIENS.etudes}#carte-`),
  );
  // Sans document, le bloc annoncerait un catalogue vide : mieux vaut le dire
  // au chargement que le publier (règle 1).
  if (rubrique === undefined || documents.length === 0) {
    throw new Error("referencement : aucune étude trouvée dans le menu");
  }
  return JSON.stringify({
    "@context": CONTEXTE,
    "@type": "Service",
    name: "Études et livrables pour la création d'entreprise",
    description,
    url: adresseAbsolue(CHEMINS.etudes),
    provider: { "@id": ORGANISATION },
    areaServed: { "@type": "Country", name: "France" },
    hasOfferCatalog: {
      "@type": "OfferCatalog",
      name: rubrique.libelle,
      itemListElement: documents.map((document) => ({
        "@type": "Offer",
        itemOffered: {
          "@type": "Service",
          name: document.libelle,
          url: adresseAbsolue(document.lien),
        },
      })),
    },
  });
}

/** Les rubriques qui ont des pages SOUS elles, et le nom que le fil d'Ariane
 *  leur donne. Une page dont le parent n'est pas ici n'a pas de fil. */
const RUBRIQUES_DU_FIL: Record<string, string> = {
  [CHEMINS.packs]: "Packs d'accompagnement",
  [CHEMINS.formations]: "Formations",
  [CHEMINS.blog]: "Blog",
  [CHEMINS.boutique]: "Études prêtes à télécharger",
};

/** Le fil d'Ariane d'une page rangée sous une rubrique (`/packs/essentiel`,
 *  `/blog/<slug>`) : Accueil, la rubrique, la page. `null` pour toute autre
 *  page — un fil d'un seul maillon ne dit rien. */
export function filDAriane(chemin: string, nomDeLaPage: string): string | null {
  const coupe = chemin.lastIndexOf("/");
  const parent = coupe > 0 ? chemin.slice(0, coupe) : null;
  const rubrique = parent === null ? undefined : RUBRIQUES_DU_FIL[parent];
  if (parent === null || rubrique === undefined || nomDeLaPage === "") return null;
  const maillons = [
    { nom: "Accueil", adresse: adresseAbsolue(CHEMINS.accueil) },
    { nom: rubrique, adresse: adresseAbsolue(parent) },
    { nom: nomDeLaPage, adresse: adresseAbsolue(chemin) },
  ];
  return JSON.stringify({
    "@context": CONTEXTE,
    "@type": "BreadcrumbList",
    itemListElement: maillons.map((maillon, k) => ({
      "@type": "ListItem",
      position: k + 1,
      name: maillon.nom,
      item: maillon.adresse,
    })),
  });
}

/** Une question et sa réponse, telles que la page les AFFICHE. */
export type QuestionAffichee = { question: string; reponse: string };

/** Le bloc `FAQPage` des questions d'une page. `null` sans question : un bloc
 *  vide est une erreur pour un moteur. */
export function questionsFrequentes(questions: QuestionAffichee[]): string | null {
  const lisibles = questions.filter(
    (entree) => entree.question !== "" && entree.reponse !== "",
  );
  if (lisibles.length === 0) return null;
  return JSON.stringify({
    "@context": CONTEXTE,
    "@type": "FAQPage",
    mainEntity: lisibles.map((entree) => ({
      "@type": "Question",
      name: entree.question,
      acceptedAnswer: { "@type": "Answer", text: entree.reponse },
    })),
  });
}

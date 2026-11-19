/** Ouvrir un paiement en sachant QUI paie.
 *
 * Les pages de vente sont publiques : elles ouvraient donc toutes leur
 * paiement par la route publique, sans compte. Y compris quand la personne
 * venait d'ouvrir une session — juste après son inscription — ou arrivait de
 * son espace par « Ouvrir la boutique ».
 *
 * Or la route publique ne sait rien de celui qui paie. Elle rattache l'achat à
 * l'ADRESSE que Stripe collecte, et Stripe la laisse modifier sur sa propre
 * page : quelqu'un qui la corrige, ou qui règle avec l'adresse de sa société,
 * se voyait ouvrir un SECOND espace. Il avait payé, tout était en règle, et
 * son étude l'attendait dans un compte où il ne se connecterait jamais (audit
 * du 19/11/2026). Le bouton Google faisait pire : il transmettait l'adresse
 * tapée dans le formulaire — souvent vide, parfois une autre que celle du
 * compte Google.
 *
 * Les routes de l'espace existent depuis longtemps pour cela
 * (`acheter_une_etude`, `acheter_un_produit`, `backend/organisations/
 * vues_espace.py`) : elles portent l'ORGANISATION jusqu'au prestataire, et
 * c'est elle qui est créditée au retour, quelle que soit l'adresse saisie.
 * `acheterUnProduit` n'avait aucun appelant.
 *
 * ## La règle, à un seul endroit
 *
 * Une session d'espace est présente → la route de l'espace. Sinon → la route
 * publique. Quatre appelants (inscription par formulaire, inscription par
 * Google, page d'achat, fiche de boutique) : la décider chez chacun, c'est en
 * oublier un (règle 4).
 *
 * ## Ce qui retombe sur la route publique, et ce qui n'y retombe pas
 *
 * Un **401** veut dire que le jeton gardé par le navigateur ne vaut plus rien
 * (`appel` vient de l'effacer). La personne est alors un visiteur, et paie
 * comme tel : la renvoyer à un écran de connexion depuis une page de vente
 * lui ferait payer l'état d'un jeton oublié.
 *
 * Tout AUTRE refus est rendu tel quel, et surtout pas contourné : un rôle
 * « lecture seule » qui ne peut pas commander, une session d'assistance
 * d'EVKHA qui ne doit engager aucune dépense au nom d'un client (403). Se
 * rabattre sur la route publique dans ces cas ferait par la fenêtre ce que le
 * serveur vient d'interdire par la porte.
 */
import { ErreurApi, espaceApi, jeton } from "../espace/api";
import {
  ouvrirLePaiement as ouvrirLePaiementDeBoutique,
  RefusBoutique,
} from "./catalogue";
import {
  ouvrirLePaiement as ouvrirLePaiementDUneEtude,
  RefusInscription,
} from "./donnees";

async function parLEspaceSinonEnVisiteur(
  depuisLEspace: () => Promise<{ adresse: string }>,
  enVisiteur: () => Promise<string>,
): Promise<string> {
  if (!jeton.present()) return enVisiteur();
  try {
    return (await depuisLEspace()).adresse;
  } catch (cause) {
    if (cause instanceof ErreurApi && cause.statut === 401) return enVisiteur();
    throw cause;
  }
}

/** Une session d'espace est-elle présente dans ce navigateur ?
 *
 *  Sert aux pages de vente à ne pas demander une adresse e-mail dont le
 *  serveur ne se servira pas : avec une session, l'achat suit le compte. */
export function achatRattacheALEspace(): boolean {
  return jeton.present();
}

/** Adresse de paiement d'une ÉTUDE À PRODUIRE (`slug` de l'offre).
 *
 *  `email` ne sert qu'au visiteur, pour pré-remplir la page de Stripe ; avec
 *  une session, le serveur prend l'adresse du compte. */
export function payerUneEtude(slug: string, email = ""): Promise<string> {
  return parLEspaceSinonEnVisiteur(
    () => espaceApi.acheterUneEtude(slug),
    () => ouvrirLePaiementDUneEtude(slug, email),
  );
}

/** Adresse de paiement d'une ÉTUDE DE BOUTIQUE (`slug` du produit). */
export function payerUnProduit(slug: string, email = ""): Promise<string> {
  return parLEspaceSinonEnVisiteur(
    () => espaceApi.acheterUnProduit(slug),
    () => ouvrirLePaiementDeBoutique(slug, email),
  );
}

/** Le message d'un refus de paiement, d'où qu'il vienne.
 *
 *  Les deux routes ne lèvent pas la même classe d'erreur (`ErreurApi` pour
 *  l'espace, `RefusInscription` ou `RefusBoutique` pour le public), mais les
 *  trois portent la phrase que le SERVEUR a écrite pour la personne. Toute
 *  autre erreur — réseau coupé, réponse illisible — n'a rien à lui dire
 *  (« Failed to fetch », « Unexpected token < ») : on rend le repli. */
export function messageDuRefusDePaiement(cause: unknown, repli: string): string {
  if (
    cause instanceof ErreurApi ||
    cause instanceof RefusInscription ||
    cause instanceof RefusBoutique
  ) {
    return cause.message || repli;
  }
  return repli;
}

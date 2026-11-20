/** L'adresse de paiement est celle de Stripe, ou l'on ne part pas.
 *
 * Toutes les pages qui ouvrent un paiement reçoivent du serveur une adresse,
 * et y envoient le navigateur (`window.location.href = adresse`). Aucune ne
 * regardait OÙ menait cette adresse : une réponse altérée en chemin, un
 * serveur mal réglé ou une doublure oubliée auraient envoyé quelqu'un saisir
 * sa carte sur un autre site, depuis un bouton « Payer » d'EVKHA.
 *
 * ## La règle, à un seul endroit
 *
 * `https:`, et un hôte qui est EXACTEMENT celui de Stripe Checkout — pas un
 * hôte qui lui ressemble (`checkout.stripe.com.exemple.fr`), ni qui le porte
 * en identifiant (`https://checkout.stripe.com@exemple.fr/`). Ni port, ni
 * identifiants : Stripe n'en rend pas.
 *
 * Tout départ vers un paiement passe par `adresseDePaiementSure` : les pages
 * de vente à travers `public/achat.ts`, les écrans de l'espace directement
 * (règle 5 : une seule source ; règle 4 : la classe, pas une page).
 *
 * Ce fichier n'importe rien : l'espace client s'en sert sans tirer avec lui
 * le code des pages publiques.
 */

/** L'hôte de Stripe Checkout. Écrit ICI et nulle part ailleurs. */
export const HOTE_DE_PAIEMENT = "checkout.stripe.com";

/** L'adresse à suivre pour payer, ou `null` si elle ne mène pas chez Stripe.
 *
 *  Rend l'adresse telle que le navigateur la LIT (`URL.href`) : ce qui est
 *  vérifié est ce qui est suivi. */
export function adresseDePaiementSure(brut: unknown): string | null {
  if (typeof brut !== "string" || brut === "") return null;
  let adresse: URL;
  try {
    // Sans base : une adresse relative est illisible, donc refusée.
    adresse = new URL(brut);
  } catch {
    return null;
  }
  if (adresse.protocol !== "https:") return null;
  if (adresse.hostname !== HOTE_DE_PAIEMENT) return null;
  if (adresse.port !== "" || adresse.username !== "" || adresse.password !== "") {
    return null;
  }
  return adresse.href;
}
